"""Integration roundtrip against real Eos + Phobos (skipped if no data)."""

from __future__ import annotations

import pytest

from pyfa_mcp.errors import FitMcpError, InvalidRackError, InvalidTypeError
from pyfa_mcp import mutations


# Navy Typhoon; T2 Damage Control (skill-gated); Gyro II
SHIP_TYPHOON_NAVY = 32311
MODULE_DC_II = 2048
MODULE_GYRO_II = 519
MODULE_800MM = 2929


def test_create_equip_stats(store):
    created = store.create(SHIP_TYPHOON_NAVY, label="smoke")
    fit_id = created["fit_id"]
    assert created["report"]["ship_type_id"] == SHIP_TYPHOON_NAVY

    mutations.equip_module(
        store.get_fit(fit_id), "low", MODULE_GYRO_II, state="online"
    )
    report = store.report(fit_id)
    assert len(report["fit"]["modules"]["low"]) == 1
    assert report["fit"]["modules"]["low"][0]["type_id"] == MODULE_GYRO_II
    assert "dps" in report["combat"]
    assert "cpu" in report["resources"]


def test_skill_gate_then_ok(store):
    created = store.create(SHIP_TYPHOON_NAVY)
    fit_id = created["fit_id"]
    mutations.equip_module(
        store.get_fit(fit_id), "low", MODULE_DC_II, state="online"
    )
    before = store.report(fit_id)
    assert before["valid"] is False
    assert any(
        e["restriction"] == "skill_requirement" for e in before["validation_errors"]
    )

    # Mechanics 5 + Hull Upgrades 5 typically required for DC II
    store.set_skills(
        fit_id,
        {
            "3394": 5,  # Hull Upgrades
            "3392": 5,  # Mechanics
        },
    )
    after = store.report(fit_id)
    # May still fail other checks; skill_requirement for DC should be gone or reduced
    skill_errs = [
        e
        for e in after["validation_errors"]
        if e["restriction"] == "skill_requirement"
        and e["item_ref"]["type_id"] == MODULE_DC_II
    ]
    assert skill_errs == []


def test_invalid_type_leaves_fit_unchanged(store):
    created = store.create(SHIP_TYPHOON_NAVY)
    fit_id = created["fit_id"]
    before = store.report(fit_id)
    with pytest.raises(InvalidTypeError):
        mutations.equip_module(store.get_fit(fit_id), "high", 999999999, state="online")
    after = store.report(fit_id)
    assert after["fit"]["modules"] == before["fit"]["modules"]


def test_wrong_rack_error(store):
    created = store.create(SHIP_TYPHOON_NAVY)
    fit_id = created["fit_id"]
    with pytest.raises(InvalidRackError):
        mutations.equip_module(store.get_fit(fit_id), "cargo", MODULE_GYRO_II)


def test_swap_module_changes_report(store):
    created = store.create(SHIP_TYPHOON_NAVY)
    fit_id = created["fit_id"]
    fit = store.get_fit(fit_id)
    mutations.equip_module(fit, "low", MODULE_GYRO_II, state="online", index=0)
    r1 = store.report(fit_id)
    mutations.replace_module(fit, "low", 0, MODULE_DC_II, state="online")
    r2 = store.report(fit_id)
    assert r1["fit"]["modules"]["low"][0]["type_id"] == MODULE_GYRO_II
    assert r2["fit"]["modules"]["low"][0]["type_id"] == MODULE_DC_II
