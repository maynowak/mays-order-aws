from __future__ import annotations

from typing import Any, Dict, Optional

VALIDATION_ERROR = "VALIDATION_ERROR"
ORDER_NOT_FOUND = "ORDER_NOT_FOUND"
INVALID_TRANSITION = "INVALID_TRANSITION"
CONFLICTED_UPDATE = "CONFLICTED_UPDATE"
INTERNAL_ERROR = "INTERNAL_ERROR"


class OrderError(Exception):
    """Fehler mit HTTP-Status und optionalen Details (api/endpoints.md §3)."""

    def __init__(
        self,
        code: str,
        message: str,
        http_status: int,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
        self.details = details


def validation_error(message: str, details: Optional[Dict[str, Any]] = None) -> OrderError:
    return OrderError(VALIDATION_ERROR, message, 400, details)


def order_not_found(order_id: str) -> OrderError:
    return OrderError(ORDER_NOT_FOUND, f"Order '{order_id}' does not exist", 404)


def invalid_transition(current: str, requested: str) -> OrderError:
    return OrderError(
        INVALID_TRANSITION,
        f"Transition from {current} to {requested} is not allowed",
        409,
        {"currentStatus": current, "requestedStatus": requested},
    )


def conflicted_update() -> OrderError:
    return OrderError(
        CONFLICTED_UPDATE,
        "Concurrent update lost; the order status changed while the update was in flight",
        409,
    )


def internal_error(message: str = "Internal error") -> OrderError:
    return OrderError(INTERNAL_ERROR, message, 500)


def error_body(error: OrderError) -> Dict[str, Any]:
    body: Dict[str, Any] = {"code": error.code, "message": error.message}
    if error.details is not None:
        body["details"] = error.details
    return {"error": body}
