"""Resolve data directories for Phobos dumps and Eos caches."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def repo_root() -> Path:
    """eve-fit-mcp repository root, or the directory containing a frozen binary."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def data_dir() -> Path:
    """Writable runtime data root (downloads + cache)."""
    if env := os.environ.get("EOS_DATA_DIR"):
        return Path(env).expanduser().resolve()
    xdg = os.environ.get("XDG_CACHE_HOME")
    if xdg:
        return Path(xdg).expanduser().resolve() / "eve-fit-mcp"
    return Path.home() / ".cache" / "eve-fit-mcp"


def bundled_staticdata_dir() -> Path | None:
    """In-tree pyfa submodule staticdata, if present (dev checkouts only)."""
    if is_frozen():
        return None
    candidate = repo_root() / "pyfa" / "staticdata"
    if _looks_like_staticdata(candidate):
        return candidate
    return None


def cached_staticdata_dir() -> Path:
    return data_dir() / "staticdata"


def default_cache_path() -> Path:
    if env := os.environ.get("EOS_CACHE_PATH"):
        return Path(env).expanduser().resolve()
    return data_dir() / "eos_tq.json.bz2"


def _looks_like_staticdata(path: Path) -> bool:
    return (
        path.is_dir()
        and (path / "fsd_built").is_dir()
        and (path / "phobos").is_dir()
    )


def is_valid_staticdata(path: Path | str) -> bool:
    return _looks_like_staticdata(Path(path))
