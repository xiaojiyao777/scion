"""Branch-card active-slot reconciliation helpers."""

from __future__ import annotations

from typing import Any, Iterable, Mapping


def active_slot_inventory_from_branch_cards(
    cards: Iterable[Mapping[str, Any]],
    *,
    max_active_branches: int | None = None,
) -> dict[str, Any] | None:
    """Reconcile status/summary active-slot fields from branch card payloads."""
    active_ids: list[str] = []
    parked_ids: list[str] = []
    released_ids: list[str] = []
    released_reasons: dict[str, str] = {}
    saw_slot_metadata = False
    for card in cards:
        if not isinstance(card, Mapping):
            continue
        branch_id = str(card.get("branch_id") or "").strip()
        if not branch_id:
            continue
        slot_status = str(card.get("active_slot_status") or "").strip()
        counts = card.get("counts_toward_active_slots")
        if counts is not None or slot_status:
            saw_slot_metadata = True
        if counts is True or slot_status == "active_slot":
            active_ids.append(branch_id)
        elif slot_status == "parked_lineage":
            parked_ids.append(branch_id)
        elif slot_status == "released_active_slot":
            released_ids.append(branch_id)
            reason = str(
                card.get("current_head_active_slot_release_reason")
                or card.get("branch_classification_reason")
                or ""
            ).strip()
            if reason:
                released_reasons[branch_id] = reason
    if not saw_slot_metadata:
        return None
    unique_active_ids = list(dict.fromkeys(active_ids))
    parked_ids = list(dict.fromkeys(parked_ids))
    released_ids = list(dict.fromkeys(released_ids))
    has_limit = max_active_branches is not None
    limit = max(0, int(max_active_branches or 0))
    overflow_ids: list[str] = []
    if has_limit and len(unique_active_ids) > limit:
        overflow_ids = unique_active_ids[limit:]
        unique_active_ids = unique_active_ids[:limit]
    used = len(unique_active_ids)
    inventory = {
        "used": used,
        "max": limit,
        "available": max(0, limit - used),
        "branch_ids": unique_active_ids,
        "parked_lineages": len(parked_ids),
        "parked_lineage_ids": parked_ids,
        "released_active_slots": len(released_ids),
        "released_active_slot_ids": released_ids,
    }
    if released_reasons:
        inventory["released_active_slot_reasons"] = released_reasons
    if overflow_ids:
        inventory["overflow_branch_ids"] = overflow_ids
        inventory["overflow_count"] = len(overflow_ids)
        inventory["reconciliation_required"] = True
        inventory["reconciliation_policy"] = "active_slot_hard_cap_reconciled"
    return inventory


__all__ = [
    "active_slot_inventory_from_branch_cards",
]
