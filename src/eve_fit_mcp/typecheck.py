"""Validate type IDs against the loaded Eos source before mutating."""

from __future__ import annotations

from eos import SourceManager, TypeFetchError

from eve_fit_mcp.errors import InvalidTypeError


def require_type(type_id: int, *, kind: str = "type") -> None:
    """Raise InvalidTypeError if type_id is missing from the default source."""
    source = SourceManager.default
    if source is None:
        raise RuntimeError("Eos SourceManager has no default source; bootstrap first")
    try:
        source.cache_handler.get_type(int(type_id))
    except TypeFetchError as exc:
        raise InvalidTypeError(int(type_id), f"{kind} not in data") from exc
