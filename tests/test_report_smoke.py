"""Unit tests for FitReport serialization with mocked stats."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from eve_fit_mcp.report import build_report, collect_validation_errors


def test_build_report_smoke_mocked():
    fit = MagicMock()
    fit.ship = SimpleNamespace(_type_id=32311, attrs={37: 100.0})
    fit.stance = None
    fit.effect_beacon = None
    fit.skills = []
    fit.modules.high = []
    fit.modules.mid = []
    fit.modules.low = []
    fit.rigs = []
    fit.drones = []
    fit.fighters = []
    fit.implants = []
    fit.boosters = []
    fit.subsystems = []

    stats = fit.stats
    stats.cpu = SimpleNamespace(used=10.0, output=100.0)
    stats.powergrid = SimpleNamespace(used=20.0, output=200.0)
    stats.calibration = SimpleNamespace(used=0.0, output=400.0)
    stats.drone_bandwidth = SimpleNamespace(used=0.0, output=25.0)
    stats.dronebay = SimpleNamespace(used=0.0, output=50.0)
    for name in (
        "high_slots",
        "mid_slots",
        "low_slots",
        "rig_slots",
        "subsystem_slots",
        "turret_slots",
        "launcher_slots",
    ):
        setattr(stats, name, SimpleNamespace(used=0, total=5))

    dmg = SimpleNamespace(total=100.0, em=25.0, thermal=25.0, kinetic=25.0, explosive=25.0)
    stats.get_dps.return_value = dmg
    stats.get_volley.return_value = SimpleNamespace(total=200.0)
    stats.get_ehp.return_value = SimpleNamespace(total=1000.0, shield=400.0, armor=400.0, hull=200.0)
    stats.worst_case_ehp = SimpleNamespace(total=800.0)
    stats.get_armor_rps.return_value = 10.0
    stats.get_shield_rps.return_value = 5.0
    stats.agility_factor = 5.5
    stats.align_time = 6.0

    fit.validate.side_effect = None

    report = build_report("abc", fit, label="test")
    assert report["fit_id"] == "abc"
    assert report["ship_type_id"] == 32311
    assert report["valid"] is True
    assert report["resources"]["cpu"]["used"] == 10.0
    assert report["combat"]["dps"]["total"] == 100.0
    assert report["combat"]["ehp"]["total"] == 1000.0
    assert report["mobility"]["max_velocity"] == 100.0
    assert report["label"] == "test"


def test_collect_validation_errors_empty():
    fit = MagicMock()
    fit.validate.return_value = None
    assert collect_validation_errors(fit) == []
