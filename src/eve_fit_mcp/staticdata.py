"""Download / refresh Phobos-format staticdata release assets."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tarfile
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from eve_fit_mcp.paths import (
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
    result = refresh_staticdata(force=True)
    return Path(result["staticdata_path"])


def refresh_staticdata(*, force: bool = True) -> dict[str, Any]:
    """Download the release archive into the cache data dir and replace staticdata."""
    url = staticdata_url()
    dest = cached_staticdata_dir()
    data_dir().mkdir(parents=True, exist_ok=True)

    if is_valid_staticdata(dest) and not force:
        return {
            "ok": True,
            "downloaded": False,
            "staticdata_path": str(dest),
            "client_build": read_client_build(dest),
            "url": url,
            "cache_path": str(default_cache_path()),
        }

    archive = data_dir() / "staticdata-tq.tar.gz"
    _download(url, archive)

    staging = Path(tempfile.mkdtemp(prefix="eve-fit-staticdata-", dir=str(data_dir())))
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

    # Force Eos to rebuild cache on next bootstrap
    cache = default_cache_path()
    if cache.is_file():
        cache.unlink()

    build = read_client_build(dest)
    return {
        "ok": True,
        "downloaded": True,
        "staticdata_path": str(dest),
        "client_build": build,
        "url": url,
        "cache_path": str(cache),
        "archive_sha256": _sha256(archive),
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


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_suffix(dest.suffix + ".partial")
    try:
        with urllib.request.urlopen(url, timeout=120) as resp, partial.open("wb") as out:
            shutil.copyfileobj(resp, out)
        partial.replace(dest)
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
        # filter= added in 3.12; keep 3.10/3.11 working
        try:
            tar.extractall(staging, filter="data")
        except TypeError:
            tar.extractall(staging)
