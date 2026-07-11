"""Load Eos SourceManager once from environment variables."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from eve_fit_mcp.phobos_data import PhobosJsonDataHandler

_BOOTSTRAPPED = False
_DATA_HANDLER: PhobosJsonDataHandler | None = None


def _ensure_eos_importable() -> None:
    if "eos" in sys.modules:
        return
    env_path = os.environ.get("EOS_PACKAGE_PATH")
    candidates = []
    if env_path:
        candidates.append(Path(env_path))
    # eve-fit/src/eve_fit_mcp → workspace/eos
    here = Path(__file__).resolve()
    candidates.append(here.parents[2].parent / "eos")
    candidates.append(here.parents[3] / "eos")
    for candidate in candidates:
        if (candidate / "eos" / "__init__.py").is_file():
            sys.path.insert(0, str(candidate))
            return
    # Last resort: hope site-packages has it
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
) -> PhobosJsonDataHandler:
    """Initialize SourceManager from env / args. Fail fast on load errors."""
    global _BOOTSTRAPPED, _DATA_HANDLER

    if _BOOTSTRAPPED and not force:
        assert _DATA_HANDLER is not None
        return _DATA_HANDLER

    _ensure_eos_importable()
    from eos import JsonCacheHandler, SourceManager

    phobos = phobos_path or os.environ.get("EOS_PHOBOS_PATH")
    cache = cache_path or os.environ.get("EOS_CACHE_PATH")
    alias = source_alias or os.environ.get("EOS_SOURCE_ALIAS", "tq")

    if not phobos:
        raise RuntimeError("EOS_PHOBOS_PATH is required (Phobos dump directory)")
    if not cache:
        raise RuntimeError(
            "EOS_CACHE_PATH is required (e.g. path to eos_tq.json.bz2)"
        )
    if not os.path.isdir(phobos):
        raise RuntimeError(f"EOS_PHOBOS_PATH is not a directory: {phobos}")

    cache_dir = os.path.dirname(os.path.abspath(cache))
    if cache_dir and not os.path.isdir(cache_dir):
        os.makedirs(cache_dir, exist_ok=True)

    data_handler = PhobosJsonDataHandler(phobos)
    # Touch version early so missing metadata fails clearly
    version = data_handler.get_version()
    if version is None:
        raise RuntimeError(
            f"Phobos metadata missing client_build under {phobos}/phobos/"
        )

    cache_handler = JsonCacheHandler(cache)
    if alias in SourceManager.list():
        SourceManager.remove(alias)
    SourceManager.add(alias, data_handler, cache_handler, make_default=True)

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
