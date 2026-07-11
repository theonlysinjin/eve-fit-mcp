"""Build FitReport snapshots from Eos Fit objects."""

from __future__ import annotations

from typing import Any

from eos import DmgProfile, Restriction, ValidationError
from eos.const.eve import AttrId
from eos.item_filter import (
    drone_filter,
    missile_filter,
    sentry_drone_filter,
    turret_filter,
)

from pyfa_mcp.state_map import state_name

DPS_FILTERS = {
    "turret": turret_filter,
    "missile": missile_filter,
    "drone": drone_filter,
    "sentry": sentry_drone_filter,
}


def _resource(stat) -> dict[str, float | None]:
    used = getattr(stat, "used", None)
    output = getattr(stat, "output", None)
    return {
        "used": _num(used),
        "output": _num(output),
    }


def _slots(stat) -> dict[str, int]:
    return {
        "used": int(getattr(stat, "used", 0) or 0),
        "total": int(getattr(stat, "total", 0) or 0),
    }


def _num(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _dmg_stats(stats_obj, *, reload: bool = False) -> dict[str, Any]:
    if stats_obj is None:
        return {
            "total": 0.0,
            "em": 0.0,
            "thermal": 0.0,
            "kinetic": 0.0,
            "explosive": 0.0,
            "reload": reload,
        }
    return {
        "total": _num(getattr(stats_obj, "total", 0)) or 0.0,
        "em": _num(getattr(stats_obj, "em", 0)) or 0.0,
        "thermal": _num(getattr(stats_obj, "thermal", 0)) or 0.0,
        "kinetic": _num(getattr(stats_obj, "kinetic", 0)) or 0.0,
        "explosive": _num(getattr(stats_obj, "explosive", 0)) or 0.0,
        "reload": reload,
    }


def _ehp_stats(ehp) -> dict[str, float]:
    if ehp is None:
        return {"total": 0.0, "shield": 0.0, "armor": 0.0, "hull": 0.0}
    return {
        "total": _num(getattr(ehp, "total", 0)) or 0.0,
        "shield": _num(getattr(ehp, "shield", 0)) or 0.0,
        "armor": _num(getattr(ehp, "armor", 0)) or 0.0,
        "hull": _num(getattr(ehp, "hull", 0)) or 0.0,
    }


def _module_entry(index: int, module) -> dict[str, Any] | None:
    if module is None:
        return None
    charge = getattr(module, "charge", None)
    return {
        "index": index,
        "type_id": int(module._type_id),
        "state": state_name(getattr(module, "state", None)),
        "charge_type_id": int(charge._type_id) if charge is not None else None,
    }


def _rack_modules(rack) -> list[dict[str, Any]]:
    entries = []
    for index, module in enumerate(rack):
        entry = _module_entry(index, module)
        if entry is not None:
            entries.append(entry)
    return entries


def _set_items(container, *, with_state: bool = False) -> list[dict[str, Any]]:
    items = sorted(container, key=lambda item: (item._type_id, id(item)))
    result = []
    for index, item in enumerate(items):
        row: dict[str, Any] = {"index": index, "type_id": int(item._type_id)}
        if with_state:
            row["state"] = state_name(getattr(item, "state", None))
        result.append(row)
    return result


def _item_ref(item) -> dict[str, Any]:
    ref: dict[str, Any] = {
        "type_id": int(getattr(item, "_type_id", 0) or 0),
        "class": type(item).__name__,
    }
    if hasattr(item, "state"):
        ref["state"] = state_name(item.state)
    return ref


def _detail_to_dict(detail: Any) -> Any:
    if detail is None:
        return None
    if hasattr(detail, "_asdict"):
        return {k: _detail_to_dict(v) for k, v in detail._asdict().items()}
    if isinstance(detail, dict):
        return {str(k): _detail_to_dict(v) for k, v in detail.items()}
    if isinstance(detail, (list, tuple, set)):
        return [_detail_to_dict(v) for v in detail]
    if isinstance(detail, (str, int, float, bool)) or detail is None:
        return detail
    return str(detail)


def collect_validation_errors(fit, skip_checks: list[str] | None = None) -> list[dict[str, Any]]:
    skip = ()
    if skip_checks:
        resolved = []
        for name in skip_checks:
            try:
                resolved.append(Restriction[name])
            except KeyError:
                # Allow numeric strings
                try:
                    resolved.append(Restriction(int(name)))
                except (ValueError, KeyError):
                    continue
        skip = tuple(resolved)

    try:
        fit.validate(skip_checks=skip)
        return []
    except ValidationError as exc:
        errors: list[dict[str, Any]] = []
        for item, restrictions in exc.data.items():
            for restriction, detail in restrictions.items():
                if isinstance(restriction, Restriction):
                    restriction_name = restriction.name
                else:
                    try:
                        restriction_name = Restriction(restriction).name
                    except Exception:
                        restriction_name = str(restriction)
                errors.append(
                    {
                        "item_ref": _item_ref(item),
                        "restriction": restriction_name,
                        "detail": _detail_to_dict(detail),
                    }
                )
        return errors


def build_report(
    fit_id: str,
    fit,
    *,
    label: str | None = None,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    options = options or {}
    dps_reload = bool(options.get("dps_reload", False))
    dmg_profile_opts = options.get("dmg_profile") or {
        "em": 25,
        "thermal": 25,
        "kinetic": 25,
        "explosive": 25,
    }
    dmg_profile = DmgProfile(
        em=float(dmg_profile_opts.get("em", 25)),
        thermal=float(dmg_profile_opts.get("thermal", 25)),
        kinetic=float(dmg_profile_opts.get("kinetic", 25)),
        explosive=float(dmg_profile_opts.get("explosive", 25)),
    )

    tgt_resists = None
    if options.get("tgt_resists"):
        from eos import ResistProfile

        tr = options["tgt_resists"]
        tgt_resists = ResistProfile(
            em=float(tr.get("em", 0)),
            thermal=float(tr.get("thermal", 0)),
            kinetic=float(tr.get("kinetic", 0)),
            explosive=float(tr.get("explosive", 0)),
        )

    stats = fit.stats
    dps = stats.get_dps(reload=dps_reload, tgt_resists=tgt_resists)
    volley = stats.get_volley(tgt_resists=tgt_resists)
    ehp = stats.get_ehp(dmg_profile)
    worst = stats.worst_case_ehp

    dps_by_filter: dict[str, Any] = {}
    for name in options.get("dps_filters") or []:
        filt = DPS_FILTERS.get(name)
        if filt is None:
            continue
        filtered = stats.get_dps(filt, reload=dps_reload, tgt_resists=tgt_resists)
        dps_by_filter[name] = _dmg_stats(filtered, reload=dps_reload)

    max_velocity = None
    if fit.ship is not None:
        try:
            max_velocity = _num(fit.ship.attrs[AttrId.max_velocity])
        except (AttributeError, KeyError):
            max_velocity = None

    try:
        armor_rps = _num(stats.get_armor_rps(dmg_profile))
    except Exception:
        armor_rps = 0.0
    try:
        shield_rps = _num(stats.get_shield_rps(dmg_profile))
    except Exception:
        shield_rps = 0.0

    validation_errors = collect_validation_errors(fit)

    ship_type_id = int(fit.ship._type_id) if fit.ship is not None else None
    stance_type_id = int(fit.stance._type_id) if fit.stance is not None else None
    beacon = fit.effect_beacon
    beacon_type_id = int(beacon._type_id) if beacon is not None else None

    return {
        "fit_id": fit_id,
        "label": label,
        "ship_type_id": ship_type_id,
        "valid": len(validation_errors) == 0,
        "validation_errors": validation_errors,
        "resources": {
            "cpu": _resource(stats.cpu),
            "powergrid": _resource(stats.powergrid),
            "calibration": _resource(stats.calibration),
            "drone_bandwidth": _resource(stats.drone_bandwidth),
            "dronebay": _resource(stats.dronebay),
        },
        "slots": {
            "high": _slots(stats.high_slots),
            "mid": _slots(stats.mid_slots),
            "low": _slots(stats.low_slots),
            "rig": _slots(stats.rig_slots),
            "subsystem": _slots(stats.subsystem_slots),
            "turret": _slots(stats.turret_slots),
            "launcher": _slots(stats.launcher_slots),
        },
        "combat": {
            "dps": _dmg_stats(dps, reload=dps_reload),
            "dps_by_filter": dps_by_filter,
            "volley": {"total": _num(getattr(volley, "total", 0)) or 0.0},
            "ehp": _ehp_stats(ehp),
            "worst_case_ehp": {
                "total": _num(getattr(worst, "total", 0)) or 0.0,
            },
            "armor_rps": armor_rps or 0.0,
            "shield_rps": shield_rps or 0.0,
        },
        "mobility": {
            "max_velocity": max_velocity,
            "agility_factor": _num(stats.agility_factor),
            "align_time": _num(stats.align_time),
        },
        "fit": {
            "skills_count": len(fit.skills),
            "modules": {
                "high": _rack_modules(fit.modules.high),
                "mid": _rack_modules(fit.modules.mid),
                "low": _rack_modules(fit.modules.low),
            },
            "rigs": _set_items(fit.rigs),
            "drones": _set_items(fit.drones, with_state=True),
            "fighters": _set_items(fit.fighters, with_state=True),
            "implants": _set_items(fit.implants),
            "boosters": _set_items(fit.boosters),
            "subsystems": _set_items(fit.subsystems),
            "stance": stance_type_id,
            "effect_beacon": beacon_type_id,
        },
    }
