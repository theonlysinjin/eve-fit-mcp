"""Shared fixtures. Integration tests skip without EOS_PHOBOS_PATH."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

DEFAULT_PHOBOS = Path("/home/sinjin/workspace/Pyfa/staticdata")
DEFAULT_CACHE = Path("/home/sinjin/workspace/eve-fit-mcp/.cache/eos_tq.json.bz2")


def _phobos_available() -> bool:
    phobos = Path(os.environ.get("EOS_PHOBOS_PATH", DEFAULT_PHOBOS))
    return (phobos / "phobos").is_dir() and (phobos / "fsd_built").is_dir()


@pytest.fixture(scope="session")
def eos_ready():
    if not _phobos_available():
        pytest.skip("EOS_PHOBOS_PATH / Phobos dump not available")
    os.environ.setdefault("EOS_PHOBOS_PATH", str(DEFAULT_PHOBOS))
    os.environ.setdefault("EOS_CACHE_PATH", str(DEFAULT_CACHE))
    os.environ.setdefault("EOS_PACKAGE_PATH", str(Path("/home/sinjin/workspace/eos")))
    from eve_fit_mcp.eos_bootstrap import bootstrap_eos

    bootstrap_eos()
    return True


@pytest.fixture
def store(eos_ready):
    from eve_fit_mcp.fit_store import FitStore

    return FitStore()
