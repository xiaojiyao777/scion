"""Lossless branch cards for status and lineage rendering."""
from __future__ import annotations

import json
from typing import Any, Mapping

from scion.core.models import Branch
from scion.core.scheduler import branch_scheduling_status
from scion.core.branch_cards_slots import active_slot_inventory_from_branch_cards


def branch_card_context(branch: Branch | None) -> dict[str, Any]:
    if branch is None:
        return {
            "branch_id": None,
            "branch_state": "missing",
            "scheduling_status": branch_scheduling_status(None).as_dict(),
        }
    summary = getattr(branch, "branch_evidence_summary", {}) or {}
    return {
        "branch_id": branch.branch_id,
        "lineage_id": branch.lineage_id,
        "branch_state": branch.state.value,
        "base_champion_id": branch.base_champion_id,
        "base_champion_hash": branch.base_champion_hash,
        "current_code_hash": branch.current_code_hash,
        "last_clean_code_hash": branch.last_clean_code_hash,
        "weight_revision": branch.weight_revision,
        "direction": branch.direction,
        "failure_codes": list(branch.failure_codes or ()),
        "created_at": branch.created_at.isoformat(),
        "updated_at": branch.updated_at.isoformat(),
        "scheduling_status": branch_scheduling_status(branch).as_dict(),
        "evidence_summary": dict(summary) if isinstance(summary, Mapping) else {},
    }


def branch_prompt_card(branch: Branch | None) -> str:
    return branch_prompt_card_from_context(branch_card_context(branch))


def branch_prompt_card_from_context(context: Mapping[str, Any]) -> str:
    """Render status facts without adding research guidance."""
    return json.dumps(dict(context), sort_keys=True, separators=(",", ":"), default=str)


__all__ = [
    "active_slot_inventory_from_branch_cards",
    "branch_card_context",
    "branch_prompt_card",
    "branch_prompt_card_from_context",
]
