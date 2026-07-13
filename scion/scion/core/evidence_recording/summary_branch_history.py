"""Lossless branch history projection for campaign summaries."""
from __future__ import annotations

from typing import Any, Iterable, Mapping

from scion.core.branch_cards import branch_prompt_card_from_context
from scion.core.models import StepRecord
from scion.core.reason_code_groups import classify_reason_codes


def _branch_cards_from_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        dict(row["branch_card"])
        for row in rows
        if isinstance(row.get("branch_card"), Mapping)
    ]


def _branch_history_cards(
    steps: Iterable[StepRecord],
    active_cards: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Attach observed protocol/Decision history without research recommendations."""

    cards_by_branch = {
        str(card.get("branch_id") or ""): dict(card)
        for card in active_cards
        if card.get("branch_id")
    }
    grouped: dict[str, list[StepRecord]] = {}
    for step in steps:
        grouped.setdefault(step.branch_id, []).append(step)
    for branch_id, branch_steps in grouped.items():
        latest = branch_steps[-1]
        card = dict(cards_by_branch.get(branch_id, {}))
        protocol = latest.protocol_result
        protocol_codes = tuple(protocol.reason_codes or ()) if protocol else ()
        decision_codes = tuple(latest.decision_reason_codes or ())
        groups = classify_reason_codes(
            (*decision_codes, *protocol_codes),
            protocol_reason_codes=protocol_codes,
        )
        card.update(
            {
                "branch_id": branch_id,
                "observed_step_count": len(branch_steps),
                "latest_round": latest.round_num,
                "latest_attempt_kind": latest.attempt_kind,
                "latest_execution_outcome": str(
                    getattr(
                        getattr(latest, "execution_outcome", None),
                        "value",
                        getattr(latest, "execution_outcome", ""),
                    )
                    or ""
                ),
                "latest_decision": (
                    latest.decision.value if latest.decision is not None else None
                ),
                "decision_reason_codes": list(decision_codes),
                "protocol_stage": (
                    getattr(protocol.stage, "value", protocol.stage)
                    if protocol is not None
                    else None
                ),
                "protocol_gate_outcome": (
                    protocol.gate_outcome if protocol is not None else None
                ),
                "protocol_reason_codes": list(protocol_codes),
                "gate_observation_reason_codes": list(
                    groups.gate_observation_reason_codes
                ),
            }
        )
        card["branch_card_text"] = branch_prompt_card_from_context(card)
        cards_by_branch[branch_id] = card
    return list(cards_by_branch.values())


def _rollback_events(
    steps: Iterable[StepRecord],
    branch_cards: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    del branch_cards
    events: list[dict[str, Any]] = []
    for step in steps:
        codes = [
            str(code)
            for code in (
                *(step.decision_reason_codes or ()),
                *((step.protocol_result.reason_codes or ()) if step.protocol_result else ()),
            )
            if "rollback" in str(code).lower()
        ]
        if codes:
            events.append(
                {"branch_id": step.branch_id, "round": step.round_num, "reason_codes": codes}
            )
    return events
