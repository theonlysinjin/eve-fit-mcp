"""Load Eos SourceManager once from environment variables."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from pyfa_mcp.paths import default_cache_path
from pyfa_mcp.phobos_data import PhobosJsonDataHandler
from pyfa_mcp.staticdata import resolve_staticdata_path

_BOOTSTRAPPED = False
_DATA_HANDLER: PhobosJsonDataHandler | None = None


def _ensure_eos_importable() -> None:
    if "eos" in sys.modules:
        return
    # PyInstaller onefile unpack dir
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        sys.path.insert(0, str(meipass))
    env_path = os.environ.get("EOS_PACKAGE_PATH")
    candidates = []
    if env_path:
        candidates.append(Path(env_path))
    here = Path(__file__).resolve()
    # …/pyfa-mcp/src/pyfa_mcp → …/pyfa-mcp/eos
    try:
        candidates.append(here.parents[2] / "eos")
        candidates.append(here.parents[2].parent / "eos")
    except IndexError:
        pass
    for candidate in candidates:
        if (candidate / "eos" / "__init__.py").is_file():
            sys.path.insert(0, str(candidate))
            return
    try:
        import eos  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "Cannot import eos. Set EOS_PACKAGE_PATH to the eos repo root "
            "(the directory that contains the eos/ package), or install Eos."
        ) from exc


def bootstrap_eos(
    *,
    phobos_path: str | None = None,
    cache_path: str | None = None,
    source_alias: str | None = None,
    force: bool = False,
    allow_download: bool = True,
) -> PhobosJsonDataHandler:
    """Initialize SourceManager from env / args. Fail fast on load errors."""
    global _BOOTSTRAPPED, _DATA_HANDLER

    if _BOOTSTRAPPED and not force:
        assert _DATA_HANDLER is not None
        return _DATA_HANDLER

    _ensure_eos_importable()
    from eos import JsonCacheHandler, SourceManager

    if phobos_path:
        phobos = phobos_path
    elif os.environ.get("EOS_PHOBOS_PATH"):
        phobos = os.environ["EOS_PHOBOS_PATH"]
    else:
        phobos = str(resolve_staticdata_path(allow_download=allow_download))

    cache = cache_path or str(default_cache_path())
    alias = source_alias or os.environ.get("EOS_SOURCE_ALIAS", "tq")

    if not os.path.isdir(phobos):
        raise RuntimeError(f"EOS_PHOBOS_PATH is not a directory: {phobos}")

    cache_dir = os.path.dirname(os.path.abspath(cache))
    if cache_dir and not os.path.isdir(cache_dir):
        os.makedirs(cache_dir, exist_ok=True)

    data_handler = PhobosJsonDataHandler(phobos)
    version = data_handler.get_version()
    if version is None:
        raise RuntimeError(
            f"Phobos metadata missing client_build under {phobos}/phobos/"
        )

    cache_handler = JsonCacheHandler(cache)
    if alias in SourceManager.list():
        SourceManager.remove(alias)
    SourceManager.add(alias, data_handler, cache_handler, make_default=True)

    # Keep env consistent for tools / later refreshes
    os.environ.setdefault("EOS_PHOBOS_PATH", phobos)
    os.environ.setdefault("EOS_CACHE_PATH", cache)

    _DATA_HANDLER = data_handler
    _BOOTSTRAPPED = True
    return data_handler


def get_data_handler() -> PhobosJsonDataHandler:
    if _DATA_HANDLER is None:
        return bootstrap_eos()
    return _DATA_HANDLER


def skill_type_ids() -> set[int]:
    """All published skill type IDs (category 16) from Phobos groups/types."""
    handler = get_data_handler()
    skill_groups = {
        row["groupID"]
        for row in handler.get_evegroups()
        if row.get("categoryID") == 16
    }
    return {
        row["typeID"]
        for row in handler.get_evetypes()
        if row.get("groupID") in skill_groups
    }
