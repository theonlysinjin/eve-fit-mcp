"""Structured errors for hard Eos failures (fit left unchanged)."""

from __future__ import annotations

from typing import Any


class FitMcpError(Exception):
    """Base error for the MCP server."""

    def __init__(self, message: str, *, code: str = "error", details: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
            }
        }


class FitNotFoundError(FitMcpError):
    def __init__(self, fit_id: str):
        super().__init__(
            f"Fit not found: {fit_id}",
            code="fit_not_found",
            details={"fit_id": fit_id},
        )


class InvalidTypeError(FitMcpError):
    def __init__(self, type_id: int, reason: str | None = None):
        msg = f"Invalid or unknown type_id: {type_id}"
        if reason:
            msg = f"{msg} ({reason})"
        super().__init__(msg, code="invalid_type", details={"type_id": type_id})


class InvalidRackError(FitMcpError):
    def __init__(self, rack: str):
        super().__init__(
            f"Invalid rack '{rack}'; expected high|mid|low",
            code="invalid_rack",
            details={"rack": rack},
        )


class SlotError(FitMcpError):
    def __init__(self, message: str, **details: Any):
        super().__init__(message, code="slot_error", details=details)


class MutationError(FitMcpError):
    def __init__(self, message: str, **details: Any):
        super().__init__(message, code="mutation_error", details=details)
