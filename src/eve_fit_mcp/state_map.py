"""Map MCP state strings ↔ eos.State."""

from __future__ import annotations

from eos import State

from eve_fit_mcp.errors import MutationError

_STATE_BY_NAME = {
    "offline": State.offline,
    "online": State.online,
    "active": State.active,
    "overload": State.overload,
}

_NAME_BY_STATE = {state: name for name, state in _STATE_BY_NAME.items()}


def parse_state(value: str | State | int | None, *, default: State = State.online) -> State:
    if value is None:
        return default
    if isinstance(value, State):
        return value
    if isinstance(value, int):
        try:
            return State(value)
        except ValueError as exc:
            raise MutationError(f"Invalid state int: {value}") from exc
    key = str(value).strip().lower()
    try:
        return _STATE_BY_NAME[key]
    except KeyError as exc:
        raise MutationError(
            f"Invalid state '{value}'; expected offline|online|active|overload"
        ) from exc


def state_name(state: State | int | None) -> str | None:
    if state is None:
        return None
    if isinstance(state, int) and not isinstance(state, State):
        try:
            state = State(state)
        except ValueError:
            return str(state)
    return _NAME_BY_STATE.get(state, str(state))
