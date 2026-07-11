"""Staticdata path helpers (no network)."""

from __future__ import annotations

from pathlib import Path

from eve_fit_mcp.paths import is_valid_staticdata
from eve_fit_mcp.staticdata import _find_staticdata_root, read_client_build


def test_is_valid_staticdata_false_for_empty(tmp_path: Path):
    assert not is_valid_staticdata(tmp_path)


def test_find_staticdata_nested(tmp_path: Path):
    root = tmp_path / "staticdata"
    (root / "fsd_built").mkdir(parents=True)
    (root / "phobos").mkdir()
    assert _find_staticdata_root(tmp_path) == root


def test_read_client_build(tmp_path: Path):
    meta = tmp_path / "phobos"
    meta.mkdir()
    (meta / "metadata.0.json").write_text(
        '[{"field_name": "client_build", "field_value": 42}]'
    )
    (tmp_path / "fsd_built").mkdir()
    assert read_client_build(tmp_path) == 42
