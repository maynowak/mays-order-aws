from __future__ import annotations

from typing import Dict, List

TRANSITIONS: Dict[str, List[str]] = {
    "PENDING": ["CONFIRMED", "CANCELLED"],
    "CONFIRMED": ["PROCESSING", "CANCELLED"],
    "PROCESSING": ["SHIPPED"],
    "SHIPPED": ["DELIVERED"],
    "DELIVERED": [],
    "CANCELLED": [],
}


def can_transition(from_status: str, to_status: str) -> bool:
    if from_status == to_status:
        return False
    return to_status in TRANSITIONS.get(from_status, [])
