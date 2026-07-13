"""Active-slot inventory reconstructed from raw branch cards."""
from __future__ import annotations

from typing import Any, Iterable, Mapping


def active_slot_inventory_from_branch_cards(
    cards: Iterable[Mapping[str, Any]],
    *,
    max_active_branches: int | None,
) -> dict[str, Any] | None:
    if max_active_branches is None:
        return None
    card_list = [dict(card) for card in cards]
    active_ids: list[str] = []
    released_ids: list[str] = []
    released_reasons: dict[str, str] = {}
    for card in card_list:
        branch_id = str(card.get("branch_id") or "")
        status = card.get("scheduling_status")
        status_map = status if isinstance(status, Mapping) else {}
        if bool(status_map.get("consumes_active_slot")):
            if branch_id:
                active_ids.append(branch_id)
        elif branch_id:
            released_ids.append(branch_id)
            released_reasons[branch_id] = str(status_map.get("release_reason") or "")
    limit = max(0, int(max_active_branches))
    return {
        "used": len(active_ids),
        "max": limit,
        "available": max(0, limit - len(active_ids)),
        "branch_ids": active_ids,
        "released_active_slots": len(released_ids),
        "released_active_slot_ids": released_ids,
        "released_active_slot_reasons": released_reasons,
    }


__all__ = ["active_slot_inventory_from_branch_cards"]
