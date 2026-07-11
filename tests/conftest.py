"""Shared fixtures. Integration tests skip without a Phobos-format dump."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from pyfa_mcp.paths import bundled_staticdata_dir, default_cache_path

_REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EOS = _REPO_ROOT / "eos"


def _resolve_dump() -> Path | None:
    if env := os.environ.get("EOS_PHOBOS_PATH"):
        path = Path(env)
        if (path / "phobos").is_dir() and (path / "fsd_built").is_dir():
            return path
        return None
    return bundled_staticdata_dir()


def _phobos_available() -> bool:
    return _resolve_dump() is not None


@pytest.fixture(scope="session")
def eos_ready():
    dump = _resolve_dump()
    if dump is None:
        pytest.skip("EOS_PHOBOS_PATH / pyfa/staticdata not available")
    os.environ.setdefault("EOS_PHOBOS_PATH", str(dump))
    os.environ.setdefault("EOS_CACHE_PATH", str(default_cache_path()))
    os.environ.setdefault("EOS_PACKAGE_PATH", str(DEFAULT_EOS))
    from pyfa_mcp.eos_bootstrap import bootstrap_eos

    bootstrap_eos(allow_download=False)
    return True


@pytest.fixture
def store(eos_ready):
    from pyfa_mcp.fit_store import FitStore

    return FitStore()
