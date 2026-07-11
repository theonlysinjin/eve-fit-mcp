"""Shared helpers for rack / item mutations."""

from __future__ import annotations

from typing import Literal

from eos import Charge, ModuleHigh, ModuleLow, ModuleMid, SlotTakenError, TypeFetchError

from eve_fit_mcp.errors import InvalidRackError, InvalidTypeError, SlotError
from eve_fit_mcp.state_map import parse_state
from eve_fit_mcp.typecheck import require_type

RackName = Literal["high", "mid", "low"]

_MODULE_CLS = {
    "high": ModuleHigh,
    "mid": ModuleMid,
    "low": ModuleLow,
}


def get_rack(fit, rack: str):
    key = rack.lower()
    if key not in _MODULE_CLS:
        raise InvalidRackError(rack)
    return getattr(fit.modules, key), key


def make_module(rack: str, type_id: int, state=None, charge_type_id: int | None = None):
    key = rack.lower()
    if key not in _MODULE_CLS:
        raise InvalidRackError(rack)
    cls = _MODULE_CLS[key]
    require_type(int(type_id), kind="module")
    charge = None
    if charge_type_id is not None:
        require_type(int(charge_type_id), kind="charge")
        try:
            charge = Charge(int(charge_type_id))
        except TypeFetchError as exc:
            raise InvalidTypeError(int(charge_type_id), "charge type not in data") from exc
    try:
        return cls(
            int(type_id),
            state=parse_state(state, default=parse_state("online")),
            charge=charge,
        )
    except TypeFetchError as exc:
        raise InvalidTypeError(int(type_id), "module type not in data") from exc


def equip_module(fit, rack: str, type_id: int, state=None, charge_type_id=None, index=None):
    rack_list, _ = get_rack(fit, rack)
    module = make_module(rack, type_id, state=state, charge_type_id=charge_type_id)
    try:
        if index is None:
            rack_list.equip(module)
        else:
            rack_list.place(int(index), module)
    except SlotTakenError as exc:
        raise SlotError(f"Slot {index} already occupied on {rack}", rack=rack, index=index) from exc
    except (TypeError, ValueError, IndexError) as exc:
        raise SlotError(str(exc), rack=rack, index=index) from exc
    return module


def replace_module(fit, rack: str, index: int, type_id: int, state=None, charge_type_id=None):
    rack_list, _ = get_rack(fit, rack)
    index = int(index)
    module = make_module(rack, type_id, state=state, charge_type_id=charge_type_id)
    # Free existing slot if present, then place
    try:
        if index < len(rack_list) and rack_list[index] is not None:
            rack_list.free(index)
    except IndexError:
        pass
    try:
        rack_list.place(index, module)
    except SlotTakenError as exc:
        raise SlotError(f"Slot {index} still occupied on {rack}", rack=rack, index=index) from exc
    except (TypeError, ValueError) as exc:
        raise SlotError(str(exc), rack=rack, index=index) from exc
    return module


def remove_module(fit, rack: str, index: int):
    rack_list, _ = get_rack(fit, rack)
    index = int(index)
    try:
        if index >= len(rack_list) or rack_list[index] is None:
            raise SlotError(f"No module at {rack}[{index}]", rack=rack, index=index)
        rack_list.free(index)
    except IndexError as exc:
        raise SlotError(f"No module at {rack}[{index}]", rack=rack, index=index) from exc


def set_module_state(fit, rack: str, index: int, state):
    rack_list, _ = get_rack(fit, rack)
    index = int(index)
    try:
        module = rack_list[index]
    except IndexError as exc:
        raise SlotError(f"No module at {rack}[{index}]", rack=rack, index=index) from exc
    if module is None:
        raise SlotError(f"No module at {rack}[{index}]", rack=rack, index=index)
    module.state = parse_state(state)


def set_charge(fit, rack: str, index: int, charge_type_id: int | None):
    rack_list, _ = get_rack(fit, rack)
    index = int(index)
    try:
        module = rack_list[index]
    except IndexError as exc:
        raise SlotError(f"No module at {rack}[{index}]", rack=rack, index=index) from exc
    if module is None:
        raise SlotError(f"No module at {rack}[{index}]", rack=rack, index=index)
    if charge_type_id is None:
        module.charge = None
        return
    require_type(int(charge_type_id), kind="charge")
    try:
        module.charge = Charge(int(charge_type_id))
    except TypeFetchError as exc:
        raise InvalidTypeError(int(charge_type_id), "charge type not in data") from exc
