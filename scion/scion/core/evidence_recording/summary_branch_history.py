"""Branch history card rendering for campaign summaries."""
from __future__ import annotations

from typing import Any, Iterable, Mapping

from scion.core.branch_cards import branch_prompt_card_from_context
from scion.core.models import StepRecord
from scion.core.reason_code_groups import classify_reason_codes
from scion.core.screening_visibility import (
    mechanism_evidence_for_protocol,
    runtime_aggregate_exclusion_for_protocol,
    runtime_evidence_policy_for_protocol,
)
from scion.core.telemetry_validation import formal_telemetry_guard_failed

from .common import _stage_value


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
    cards_by_branch = {
        str(card.get("branch_id") or ""): dict(card)
        for card in active_cards
        if card.get("branch_id")
    }
    grouped: dict[str, list[StepRecord]] = {}
    for step in steps:
        grouped.setdefault(step.branch_id, []).append(step)
    for branch_id, branch_steps in grouped.items():
        latest, card = branch_steps[-1], dict(cards_by_branch.get(branch_id, {}))
        reason_codes, evidence = _step_reason_codes(latest), _step_generic_evidence(
            latest
        )
        status = _history_card_status(card, _step_status(latest))
        gate_observation_reason_codes = _step_gate_observation_reason_codes(latest)
        lifecycle_action_reason_codes = _step_lifecycle_action_reason_codes(latest)
        retained = bool(
            card.get("best_quality_checkpoint_id") or card.get("last_valid_checkpoint_id")
        )
        card.update(
            {
                "branch_id": branch_id,
                "direction": card.get("direction")
                or f"{latest.hypothesis.action}/{latest.hypothesis.change_locus}",
                "status": status,
                "mechanism_ids": card.get("mechanism_ids")
                or _step_mechanism_ids(branch_steps),
                "current_head_status": card.get("current_head_status")
                or evidence["tier"],
                "best_checkpoint_status": card.get("best_checkpoint_status", "none"),
                "best_quality_checkpoint_id": card.get("best_quality_checkpoint_id"),
                "last_valid_checkpoint_id": card.get("last_valid_checkpoint_id"),
                "rollback_count": int(card.get("rollback_count") or 0),
                "latest_head_failed": card.get(
                    "latest_head_failed",
                    status == "abandoned" or evidence["tier"] in {"regression", "invalid"},
                ),
                "lineage_retained_checkpoint": retained,
                "allowed_next_actions": card.get("allowed_next_actions")
                or ["clean_fork"],
                "forbidden_next_actions": card.get("forbidden_next_actions")
                or ["resume_abandoned_lineage_without_new_evidence"],
                "generic_evidence_summary": card.get("generic_evidence_summary")
                or evidence,
                "case_level_winners": card.get("case_level_winners")
                or _step_case_outcomes(latest, "win"),
                "case_level_losses": card.get("case_level_losses")
                or _step_case_outcomes(latest, "loss"),
                "phase_activation_summary": card.get("phase_activation_summary")
                or _step_phase_activation_summary(latest),
                "runtime_evidence_confidence": card.get(
                    "runtime_evidence_confidence"
                )
                or _step_runtime_evidence_confidence(latest),
                "gate_observation_reason_codes": card.get(
                    "gate_observation_reason_codes"
                )
                or gate_observation_reason_codes,
                "lifecycle_action_reason_codes": card.get(
                    "lifecycle_action_reason_codes"
                )
                or lifecycle_action_reason_codes,
                "why_not_promoted_reason_codes": card.get(
                    "why_not_promoted_reason_codes"
                )
                or reason_codes,
                "why_abandoned_reason_codes": card.get("why_abandoned_reason_codes")
                or (reason_codes if status == "abandoned" else []),
            }
        )
        card["branch_card_text"] = branch_prompt_card_from_context(card)
        cards_by_branch[branch_id] = card
    return list(cards_by_branch.values())


def _rollback_events(
    steps: Iterable[StepRecord],
    branch_cards: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for step in steps:
        codes = _step_reason_codes(step)
        if any("rollback" in code.lower() for code in codes):
            events.append(
                {
                    "branch_id": step.branch_id,
                    "round": step.round_num,
                    "reason_codes": codes,
                }
            )
    for card in branch_cards:
        rollback_count = int(card.get("rollback_count") or 0)
        if rollback_count:
            events.append(
                {
                    "branch_id": card.get("branch_id"),
                    "rollback_count": rollback_count,
                    "best_quality_checkpoint_id": card.get(
                        "best_quality_checkpoint_id"
                    ),
                    "last_valid_checkpoint_id": card.get("last_valid_checkpoint_id"),
                }
            )
    return events


def _step_mechanism_ids(steps: Iterable[StepRecord]) -> list[str]:
    ids: list[str] = []
    for step in steps:
        for source in (step.hypothesis, step.patch):
            for change in getattr(source, "mechanism_changes", ()) or ():
                value = str(getattr(change, "id", "") or "").strip()
                if value:
                    ids.append(value)
        ids.extend(str(item) for item in (step.repair_mechanism_ids or ()) if item)
    return list(dict.fromkeys(ids))


def _step_reason_codes(step: StepRecord) -> list[str]:
    codes = list(step.decision_reason_codes or ())
    if step.protocol_result is not None:
        codes.extend(step.protocol_result.reason_codes)
    detail = str(step.failure_detail or step.verification_detail or "").strip()
    if detail:
        codes.append(detail.split(":", 1)[0].split()[0])
    return list(dict.fromkeys(str(code) for code in codes if str(code)))


def _step_gate_observation_reason_codes(step: StepRecord) -> list[str]:
    groups = _step_reason_code_groups(step)
    return list(groups.gate_observation_reason_codes)


def _step_lifecycle_action_reason_codes(step: StepRecord) -> list[str]:
    groups = _step_reason_code_groups(step)
    return list(groups.lifecycle_action_reason_codes)


def _step_reason_code_groups(step: StepRecord):
    protocol_reason_codes: Iterable[str] = ()
    if step.protocol_result is not None:
        protocol_reason_codes = step.protocol_result.reason_codes
    return classify_reason_codes(
        _step_reason_codes(step),
        protocol_reason_codes=protocol_reason_codes,
    )


def _step_generic_evidence(step: StepRecord) -> dict[str, Any]:
    pr = step.protocol_result
    if pr is None:
        return {"tier": "invalid" if step.failure_stage else "unknown"}
    stats = pr.stats
    if stats.losses > stats.wins or stats.median_delta < 0:
        tier = "regression"
    elif stats.wins > stats.losses:
        tier = "weak_positive" if pr.gate_outcome == "pass" else "marginal"
    else:
        tier = "no_effect" if stats.wins == 0 and stats.losses == 0 else "marginal"
    evidence: dict[str, Any] = {
        "tier": tier,
        "wins": stats.wins,
        "losses": stats.losses,
        "ties": stats.ties,
        "effect": {
            "median_delta": stats.median_delta,
            "ci_low": stats.ci_low,
            "ci_high": stats.ci_high,
        },
    }
    if stats.runtime_ratio_median is not None or stats.runtime_regression_rate is not None:
        evidence["runtime"] = {
            "runtime_ratio_median": stats.runtime_ratio_median,
            "runtime_regression_rate": stats.runtime_regression_rate,
        }
    runtime_confidence = str(getattr(pr, "runtime_confidence", "") or "").strip()
    if runtime_confidence:
        evidence["runtime_evidence_confidence"] = runtime_confidence
    runtime_status = str(getattr(pr, "runtime_evidence_status", "") or "").strip()
    if runtime_status:
        evidence["runtime_evidence_status"] = runtime_status
    runtime_aggregate_exclusion = runtime_aggregate_exclusion_for_protocol(pr)
    if runtime_aggregate_exclusion:
        evidence["runtime_aggregate_exclusion"] = runtime_aggregate_exclusion
    runtime_evidence_policy = runtime_evidence_policy_for_protocol(pr)
    if runtime_evidence_policy:
        evidence["runtime_evidence_policy"] = runtime_evidence_policy
    return evidence


def _step_case_outcomes(step: StepRecord, dominant_result: str) -> list[dict[str, Any]]:
    pr = step.protocol_result
    if pr is None:
        return []
    outcomes: list[dict[str, Any]] = []
    for feedback in getattr(pr, "case_feedback", ()) or ():
        if str(getattr(feedback, "dominant_result", "") or "") != dominant_result:
            continue
        deltas = getattr(feedback, "median_deltas", {}) or {}
        outcomes.append(
            {
                "case_id": str(getattr(feedback, "case_id", "") or ""),
                "result": dominant_result,
                "delta": _case_delta_for_protocol(deltas, pr),
                "effect_counters": {
                    "wins": max(0, int(getattr(feedback, "wins", 0) or 0)),
                    "losses": max(0, int(getattr(feedback, "losses", 0) or 0)),
                    "ties": max(0, int(getattr(feedback, "ties", 0) or 0)),
                    "pairs": max(0, int(getattr(feedback, "n_pairs", 0) or 0)),
                },
            }
        )
        if len(outcomes) >= 5:
            return outcomes
    if outcomes:
        return outcomes
    return _step_pair_outcomes(pr, dominant_result)


def _step_pair_outcomes(
    protocol_result: Any,
    dominant_result: str,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[Any]] = {}
    for row in getattr(protocol_result, "pair_feedback", ()) or ():
        case_id = str(getattr(row, "case_id", "") or "")
        if case_id:
            grouped.setdefault(case_id, []).append(row)
    outcomes: list[dict[str, Any]] = []
    for case_id, rows in sorted(grouped.items()):
        wins = sum(1 for row in rows if getattr(row, "comparison", None) == "win")
        losses = sum(1 for row in rows if getattr(row, "comparison", None) == "loss")
        ties = len(rows) - wins - losses
        result = "win" if wins > losses else "loss" if losses > wins else "tie"
        if result != dominant_result:
            continue
        deltas = [
            float(getattr(row, "delta"))
            for row in rows
            if isinstance(getattr(row, "delta", None), (int, float))
        ]
        outcomes.append(
            {
                "case_id": case_id,
                "result": result,
                "delta": _median(deltas) if deltas else None,
                "effect_counters": {
                    "wins": wins,
                    "losses": losses,
                    "ties": ties,
                    "pairs": len(rows),
                },
            }
        )
        if len(outcomes) >= 5:
            return outcomes
    return outcomes


def _step_phase_activation_summary(step: StepRecord) -> dict[str, Any]:
    pr = step.protocol_result
    if pr is None:
        return {
            "stage": str(step.failure_stage or "unknown"),
            "activation_status": "unknown",
            "effect_status": "unknown",
            "activation_evidence_status": "unknown",
            "objective_effect_status": "unknown",
            "opportunity_status": "unknown",
            "telemetry_outcome": None,
        }
    stats = pr.stats
    mechanism_evidence = mechanism_evidence_for_protocol(pr)
    return {
        "stage": _stage_value(pr.stage),
        "activation_status": str(
            mechanism_evidence.get("primary_activation_status") or "unknown"
        ),
        "effect_status": str(
            mechanism_evidence.get("primary_effect_status")
            or (
                "observed"
                if max(0, int(getattr(stats, "wins", 0) or 0))
                or max(0, int(getattr(stats, "losses", 0) or 0))
                else "not_observed"
            )
        ),
        "activation_evidence_status": str(
            mechanism_evidence.get("activation_evidence_status") or "unknown"
        ),
        "objective_effect_status": str(
            mechanism_evidence.get("objective_effect_status") or "unknown"
        ),
        "opportunity_status": str(getattr(pr, "opportunity_status", "") or "unknown"),
        "telemetry_outcome": "failed"
        if formal_telemetry_guard_failed(pr)
        else pr.gate_outcome,
    }


def _step_runtime_evidence_confidence(step: StepRecord) -> str:
    pr = step.protocol_result
    if pr is None:
        return "unknown"
    return str(getattr(pr, "runtime_confidence", "") or "unknown")


def _case_delta_for_protocol(
    deltas: Mapping[str, Any],
    protocol_result: Any,
) -> float | None:
    if not isinstance(deltas, Mapping):
        return None
    metric = str(getattr(protocol_result.stats, "statistical_metric", "") or "")
    keys = [metric] if metric else []
    keys.extend(sorted(str(key) for key in deltas if str(key) not in keys))
    for key in keys:
        try:
            return float(deltas[key])
        except (KeyError, TypeError, ValueError):
            continue
    return None


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    size = len(ordered)
    midpoint = size // 2
    if size % 2:
        return ordered[midpoint]
    return (ordered[midpoint - 1] + ordered[midpoint]) / 2.0


def _step_status(step: StepRecord) -> str:
    decision = step.decision.value if getattr(step.decision, "value", None) else None
    return "abandoned" if decision == "abandon" else str(
        step.failure_stage or decision or "screened"
    )


def _history_card_status(card: Mapping[str, Any], step_status: str) -> str:
    card_status = str(card.get("status") or "").strip()
    current_head_status = str(card.get("current_head_status") or "").strip()
    branch_code_status = str(card.get("branch_code_status") or "").strip()
    active_slot_status = str(card.get("active_slot_status") or "").strip()
    terminal_statuses = {"abandoned", "archived", "parked_lineage", "promoted"}
    for status in (
        card_status,
        current_head_status,
        branch_code_status,
        active_slot_status,
    ):
        if status in terminal_statuses:
            return status
    if step_status == "abandoned":
        return step_status
    return card_status or step_status
