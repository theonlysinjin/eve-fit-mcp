"""Download / refresh Phobos-format staticdata release assets."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pyfa_mcp.paths import (
    bundled_staticdata_dir,
    cached_staticdata_dir,
    data_dir,
    default_cache_path,
    is_valid_staticdata,
)

DEFAULT_STATICDATA_URL = (
    "https://github.com/theonlysinjin/eve-fit-mcp/releases/download/"
    "staticdata/staticdata-tq.tar.gz"
)

# (bytes_done, bytes_total|None, message)
ProgressCb = Callable[[int, int | None, str], None]


def staticdata_url() -> str:
    return os.environ.get("EOS_STATICDATA_URL", DEFAULT_STATICDATA_URL)


def read_client_build(staticdata: Path) -> int | None:
    meta = staticdata / "phobos" / "metadata.0.json"
    if not meta.is_file():
        return None
    rows = json.loads(meta.read_text())
    for row in rows:
        if row.get("field_name") == "client_build":
            try:
                return int(row["field_value"])
            except (TypeError, ValueError):
                return None
    return None


def resolve_staticdata_path(*, allow_download: bool = True) -> Path:
    """Pick EOS_PHOBOS_PATH, bundled pyfa/, cache, or download."""
    if env := os.environ.get("EOS_PHOBOS_PATH"):
        path = Path(env).expanduser().resolve()
        if not is_valid_staticdata(path):
            raise RuntimeError(
                f"EOS_PHOBOS_PATH is set but is not a valid dump: {path}"
            )
        return path

    bundled = bundled_staticdata_dir()
    if bundled is not None:
        return bundled

    cached = cached_staticdata_dir()
    if is_valid_staticdata(cached):
        return cached

    if not allow_download:
        raise RuntimeError(
            "No staticdata found. Set EOS_PHOBOS_PATH, init the pyfa submodule, "
            "or call refresh_static_data."
        )
    result = refresh_staticdata(force=True, on_progress=_stderr_progress)
    return Path(result["staticdata_path"])


def refresh_staticdata(
    *,
    force: bool = True,
    on_progress: ProgressCb | None = None,
) -> dict[str, Any]:
    """Download the release archive into the cache data dir and replace staticdata."""
    url = staticdata_url()
    dest = cached_staticdata_dir()
    data_dir().mkdir(parents=True, exist_ok=True)
    progress = on_progress or (lambda *_a: None)

    if is_valid_staticdata(dest) and not force:
        progress(0, 0, "Staticdata already present; skip download")
        return {
            "ok": True,
            "downloaded": False,
            "staticdata_path": str(dest),
            "client_build": read_client_build(dest),
            "url": url,
            "cache_path": str(default_cache_path()),
        }

    archive = data_dir() / "staticdata-tq.tar.gz"
    progress(0, None, f"Downloading {url}")
    t0 = time.monotonic()
    bytes_done, bytes_total = _download(url, archive, on_progress=progress)
    elapsed = time.monotonic() - t0
    progress(
        bytes_done,
        bytes_total,
        f"Download complete ({_fmt_bytes(bytes_done)} in {elapsed:.1f}s)",
    )

    progress(0, None, "Extracting archive…")
    staging = Path(tempfile.mkdtemp(prefix="pyfa-mcp-staticdata-", dir=str(data_dir())))
    try:
        _extract_tar_gz(archive, staging)
        extracted = _find_staticdata_root(staging)
        if extracted is None:
            raise RuntimeError(
                f"Archive from {url} did not contain a staticdata/ dump tree"
            )
        if dest.exists():
            shutil.rmtree(dest)
        shutil.move(str(extracted), str(dest))
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    progress(0, None, f"Extracted to {dest}")

    cache = default_cache_path()
    if cache.is_file():
        cache.unlink()
        progress(0, None, "Cleared Eos cache (will rebuild on bootstrap)")

    build = read_client_build(dest)
    return {
        "ok": True,
        "downloaded": True,
        "staticdata_path": str(dest),
        "client_build": build,
        "url": url,
        "cache_path": str(cache),
        "archive_sha256": _sha256(archive),
        "bytes_downloaded": bytes_done,
        "bytes_total": bytes_total,
        "download_seconds": round(elapsed, 2),
    }


def _find_staticdata_root(root: Path) -> Path | None:
    if is_valid_staticdata(root):
        return root
    candidate = root / "staticdata"
    if is_valid_staticdata(candidate):
        return candidate
    for child in root.iterdir():
        if child.is_dir() and is_valid_staticdata(child):
            return child
    return None


def _download(
    url: str,
    dest: Path,
    *,
    on_progress: ProgressCb | None = None,
) -> tuple[int, int | None]:
    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_suffix(dest.suffix + ".partial")
    progress = on_progress or (lambda *_a: None)
    try:
        with urllib.request.urlopen(url, timeout=120) as resp, partial.open("wb") as out:
            total = resp.headers.get("Content-Length")
            total_n = int(total) if total and total.isdigit() else None
            done = 0
            last_report = -1.0
            chunk_size = 256 * 1024
            while True:
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                out.write(chunk)
                done += len(chunk)
                # Throttle: every ~2% or every 2 MiB if size unknown
                if total_n:
                    pct = 100.0 * done / total_n
                    if pct - last_report >= 2.0 or done >= total_n:
                        last_report = pct
                        progress(
                            done,
                            total_n,
                            f"Downloading… {pct:.0f}% ({_fmt_bytes(done)}/{_fmt_bytes(total_n)})",
                        )
                elif done - max(last_report, 0) >= 2 * 1024 * 1024:
                    last_report = float(done)
                    progress(done, None, f"Downloading… {_fmt_bytes(done)}")
        partial.replace(dest)
        if total_n:
            progress(done, total_n, f"Downloading… 100% ({_fmt_bytes(done)}/{_fmt_bytes(total_n)})")
        return done, total_n
    except urllib.error.HTTPError as exc:
        partial.unlink(missing_ok=True)
        raise RuntimeError(
            f"Failed to download staticdata from {url}: HTTP {exc.code}"
        ) from exc
    except Exception:
        partial.unlink(missing_ok=True)
        raise


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _extract_tar_gz(archive: Path, staging: Path) -> None:
    with tarfile.open(archive, "r:gz") as tar:
        try:
            tar.extractall(staging, filter="data")
        except TypeError:
            tar.extractall(staging)


def _fmt_bytes(n: int) -> str:
    size = float(n)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if size < 1024.0 or unit == "GiB":
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{n} B"


def _stderr_progress(done: int, total: int | None, message: str) -> None:
    print(f"pyfa-mcp: {message}", file=sys.stderr, flush=True)
