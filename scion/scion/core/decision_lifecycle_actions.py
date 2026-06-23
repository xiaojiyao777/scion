"""Branch lifecycle side-effect helpers for decision finalization."""

from __future__ import annotations

from datetime import datetime
from statistics import median
from typing import Any, Iterable, Mapping, Optional

from scion.core.branch_hygiene import (
    ACTIVATION_MISSING_OR_WIRING_SUSPECT,
    BRANCH_LIFECYCLE_NEW_MECHANISM_INELIGIBLE,
    BRANCH_LIFECYCLE_REROUTE_AFTER_POLICY_BLOCK,
    TELEMETRY_EFFECT_ZERO_OUTCOME,
    hard_telemetry_repair_reason_present,
    telemetry_effect_zero_reason_present,
)
from scion.core.branch_lifecycle_policy import (
    BRANCH_LIFECYCLE_ARCHIVE_LINEAGE,
    BRANCH_LIFECYCLE_PARK_LINEAGE,
    BRANCH_LIFECYCLE_RETAIN_CHECKPOINT,
    BRANCH_LIFECYCLE_ROLLBACK_TO_CHECKPOINT,
    generic_effect_status,
    generic_evidence_signature,
)
from scion.core.fresh_runtime_signals import fresh_runtime_actionable_loss_signal
from scion.core.mechanism_evidence_contract import (
    mechanism_evidence_contract_for_protocol,
)
from scion.core.models import Branch, BranchState, ProtocolResult
from scion.core.reason_code_groups import classify_reason_codes
from scion.core.runtime_budget_diagnostics import (
    BOTH_RUNTIME_BUDGET_SATURATION,
    CANDIDATE_RUNTIME_BUDGET_SATURATION,
    protocol_runtime_model,
    runtime_model_from_summary,
)
from scion.core.screening_visibility import (
    mechanism_evidence_for_protocol,
    runtime_aggregate_exclusion_for_protocol,
    runtime_evidence_policy_summary,
)


def lifecycle_action(
    decision_reason_codes: Optional[tuple[str, ...]],
) -> str:
    reason_set = set(decision_reason_codes or ())
    if BRANCH_LIFECYCLE_ROLLBACK_TO_CHECKPOINT in reason_set:
        return "rollback_to_checkpoint"
    if BRANCH_LIFECYCLE_PARK_LINEAGE in reason_set:
        return "park_lineage"
    if BRANCH_LIFECYCLE_RETAIN_CHECKPOINT in reason_set:
        return "retain_checkpoint"
    if BRANCH_LIFECYCLE_ARCHIVE_LINEAGE in reason_set:
        return "archive_lineage"
    return "retain_head"


def _current_telemetry_outcome(
    branch: Branch,
    *,
    reason_codes: Iterable[str] | None,
) -> str | None:
    if hard_telemetry_repair_reason_present(reason_codes):
        return ACTIVATION_MISSING_OR_WIRING_SUSPECT
    if telemetry_effect_zero_reason_present(reason_codes):
        return TELEMETRY_EFFECT_ZERO_OUTCOME
    return getattr(branch, "last_telemetry_outcome", None)


def update_branch_lifecycle_signal_state(
    branch: Branch,
    *,
    protocol_result: Optional[ProtocolResult],
    screening_feedback: object,
    telemetry_effect_zero: bool,
) -> None:
    if protocol_result is None or protocol_result.stats is None:
        return
    if getattr(protocol_result.stage, "value", protocol_result.stage) != "screening":
        return
    stats = protocol_result.stats
    pair_wins = max(0, int(getattr(screening_feedback, "pair_wins", 0) or 0))
    pair_losses = max(0, int(getattr(screening_feedback, "pair_losses", 0) or 0))
    effect_status = str(
        getattr(screening_feedback, "effect_status", "") or ""
    ).strip() or generic_effect_status(
        wins=max(0, int(getattr(stats, "wins", 0) or 0)),
        losses=max(0, int(getattr(stats, "losses", 0) or 0)),
        pair_wins=pair_wins,
        pair_losses=pair_losses,
        median_delta=getattr(stats, "median_delta", None),
        telemetry_effect_zero=telemetry_effect_zero,
        candidate_failed_pairs=max(
            0,
            int(getattr(stats, "candidate_failed_pairs", 0) or 0),
        ),
    )
    signature = generic_evidence_signature(
        wins=max(0, int(getattr(stats, "wins", 0) or 0)),
        losses=max(0, int(getattr(stats, "losses", 0) or 0)),
        ties=max(0, int(getattr(stats, "ties", 0) or 0)),
        median_delta=getattr(stats, "median_delta", None),
        ci_low=getattr(stats, "ci_low", None),
        ci_high=getattr(stats, "ci_high", None),
        runtime_ratio_median=getattr(stats, "runtime_ratio_median", None),
        runtime_delta_median_ms=getattr(stats, "runtime_delta_median_ms", None),
        runtime_regression_rate=getattr(stats, "runtime_regression_rate", None),
        runtime_pairs=max(0, int(getattr(stats, "runtime_pairs", 0) or 0)),
        effect_status=effect_status,
    )
    previous_signature = str(
        getattr(branch, "lifecycle_last_signal_signature", "") or ""
    )
    previous_repeat_count = max(
        0,
        int(getattr(branch, "lifecycle_signal_repeat_count", 0) or 0),
    )
    branch.lifecycle_last_signal_signature = signature
    branch.lifecycle_signal_repeat_count = (
        previous_repeat_count + 1
        if previous_signature and previous_signature == signature
        else 1
    )

    tier = str(getattr(screening_feedback, "tier", "") or "")
    if tier in {"marginal", "no_effect"}:
        branch.lifecycle_marginal_no_effect_streak = (
            max(
                0,
                int(
                    getattr(
                        branch,
                        "lifecycle_marginal_no_effect_streak",
                        0,
                    )
                    or 0
                ),
            )
            + 1
        )
    elif tier in {"weak_positive", "promotable"}:
        branch.lifecycle_marginal_no_effect_streak = 0

    if tier == "no_effect":
        prior_followups = max(
            0,
            int(
                getattr(branch, "lifecycle_no_effect_diagnostic_followups", 0)
                or 0
            ),
        )
        prior_status = str(getattr(branch, "branch_code_status", "") or "")
        prior_tier = str(getattr(branch, "last_screening_feedback_tier", "") or "")
        if prior_followups == 0 and (
            prior_status == "active_no_effect" or prior_tier == "no_effect"
        ):
            prior_followups = 1
        branch.lifecycle_no_effect_diagnostic_followups = prior_followups + 1
    elif tier in {"weak_positive", "marginal", "promotable"}:
        branch.lifecycle_no_effect_diagnostic_followups = 0


def update_branch_screening_evidence_summary(
    branch: Branch,
    *,
    protocol_result: Optional[ProtocolResult],
    screening_feedback: object | None,
    decision_reason_codes: Iterable[str] | None = None,
) -> None:
    """Persist compact generic screening evidence for branch cards."""
    if protocol_result is None or protocol_result.stats is None:
        return
    if getattr(protocol_result.stage, "value", protocol_result.stage) != "screening":
        return
    stats = protocol_result.stats
    mechanism_evidence = mechanism_evidence_for_protocol(protocol_result)
    mechanism_contract = mechanism_evidence_contract_for_protocol(protocol_result)
    runtime_aggregate_exclusion = runtime_aggregate_exclusion_for_protocol(
        protocol_result
    )
    reason_codes = tuple(
        dict.fromkeys(
            str(code).strip()
            for code in (
                tuple(decision_reason_codes or ())
                + tuple(getattr(protocol_result, "reason_codes", ()) or ())
            )
            if str(code).strip()
        )
    )
    reason_code_groups = classify_reason_codes(
        reason_codes,
        protocol_reason_codes=getattr(protocol_result, "reason_codes", ()) or (),
    )
    telemetry_outcome = _current_telemetry_outcome(
        branch,
        reason_codes=reason_codes,
    )
    gate_observation_reason_codes = _string_tuple(
        getattr(screening_feedback, "gate_observation_reason_codes", None)
    ) or tuple(reason_code_groups.gate_observation_reason_codes)
    gate_observation_reason_codes = tuple(
        dict.fromkeys(
            tuple(gate_observation_reason_codes)
            + tuple(_screening_gate_reason_codes(reason_codes))
        )
    )
    lifecycle_action_reason_codes = _string_tuple(
        getattr(screening_feedback, "lifecycle_action_reason_codes", None)
    ) or tuple(reason_code_groups.lifecycle_action_reason_codes)
    previous_summary = (
        dict(getattr(branch, "branch_evidence_summary", {}) or {})
        if isinstance(getattr(branch, "branch_evidence_summary", None), Mapping)
        else {}
    )
    case_level_winners = _compact_case_results(protocol_result, "win")
    case_level_losses = _compact_case_results(protocol_result, "loss")
    summary = {
        "stage": "screening",
        "tier": str(getattr(screening_feedback, "tier", "") or "").strip()
        or "unknown",
        "evidence_retention_status": "retained",
        "wins": max(0, int(getattr(stats, "wins", 0) or 0)),
        "losses": max(0, int(getattr(stats, "losses", 0) or 0)),
        "ties": max(0, int(getattr(stats, "ties", 0) or 0)),
        "pair_wins": max(0, int(getattr(screening_feedback, "pair_wins", 0) or 0)),
        "pair_losses": max(
            0,
            int(getattr(screening_feedback, "pair_losses", 0) or 0),
        ),
        "pair_ties": max(0, int(getattr(screening_feedback, "pair_ties", 0) or 0)),
        "median_delta": getattr(stats, "median_delta", None),
        "ci_low": getattr(stats, "ci_low", None),
        "ci_high": getattr(stats, "ci_high", None),
        "runtime_ratio_median": getattr(stats, "runtime_ratio_median", None),
        "runtime_delta_median_ms": getattr(stats, "runtime_delta_median_ms", None),
        "runtime_regression_rate": getattr(stats, "runtime_regression_rate", None),
        "runtime_pairs": max(0, int(getattr(stats, "runtime_pairs", 0) or 0)),
        "runtime_evidence_confidence": str(
            getattr(screening_feedback, "runtime_confidence", None)
            or getattr(protocol_result, "runtime_confidence", "")
            or "unknown"
        ),
        "runtime_evidence_status": str(
            getattr(protocol_result, "runtime_evidence_status", "")
            or getattr(stats, "runtime_evidence_status", "")
            or "sufficient"
        ),
        "phase_activation_summary": {
            "stage": "screening",
            "activation_status": str(
                getattr(screening_feedback, "activation_status", "") or "unknown"
            ),
            "effect_status": str(
                getattr(screening_feedback, "effect_status", "") or "unknown"
            ),
            "activation_evidence_status": str(
                mechanism_evidence.get("activation_evidence_status") or "unknown"
            ),
            "objective_effect_status": str(
                mechanism_evidence.get("objective_effect_status") or "unknown"
            ),
            "opportunity_status": str(
                getattr(screening_feedback, "opportunity_status", "")
                or getattr(protocol_result, "opportunity_status", "")
                or "unknown"
            ),
            "telemetry_outcome": telemetry_outcome,
        },
        "opportunity_diagnostics": list(
            _string_tuple(getattr(screening_feedback, "opportunity_diagnostics", None))
        ),
        "case_level_winners": case_level_winners,
        "case_level_losses": case_level_losses,
        "case_level_positive_cases": case_level_winners,
        "case_level_negative_cases": case_level_losses,
        "runtime_cache": {
            "champion_cache_hits": max(
                0,
                int(getattr(protocol_result, "champion_cache_hits", 0) or 0),
            ),
            "champion_cache_misses": max(
                0,
                int(getattr(protocol_result, "champion_cache_misses", 0) or 0),
            ),
            "champion_cached_runtime_pairs": max(
                0,
                int(
                    getattr(
                        protocol_result,
                        "champion_cached_runtime_pairs",
                        0,
                    )
                    or 0
                ),
            ),
        },
    }
    if mechanism_contract:
        summary["mechanism_evidence_contract"] = mechanism_contract
        summary["phase_activation_summary"]["mechanism_contract_status"] = (
            mechanism_contract.get("primary_status") or "unknown"
        )
        summary["phase_activation_summary"]["mechanism_followup_required"] = bool(
            mechanism_contract.get("followup_required")
        )
    phase_telemetry = getattr(
        protocol_result,
        "candidate_phase_telemetry_summary",
        None,
    )
    if isinstance(phase_telemetry, Mapping) and phase_telemetry:
        summary["phase_telemetry_summary"] = dict(phase_telemetry)
    if reason_codes:
        summary["decision_reason_codes"] = list(reason_codes)
        summary["reason_codes"] = list(reason_codes)
        summary["why_not_promoted_reason_codes"] = list(reason_codes)
    if gate_observation_reason_codes:
        summary["gate_observation_reason_codes"] = list(
            gate_observation_reason_codes
        )
    if lifecycle_action_reason_codes:
        summary["lifecycle_action_reason_codes"] = list(
            lifecycle_action_reason_codes
        )
    if runtime_aggregate_exclusion:
        summary["runtime_aggregate_exclusion"] = runtime_aggregate_exclusion
    runtime_model = protocol_runtime_model(protocol_result, default="")
    if runtime_model:
        summary["runtime_model"] = runtime_model
    runtime_policy = runtime_evidence_policy_summary(
        runtime_confidence=summary["runtime_evidence_confidence"],
        runtime_evidence_status=summary["runtime_evidence_status"],
        runtime_model=runtime_model,
        runtime_pairs=summary["runtime_pairs"],
        champion_cached_runtime_pairs=summary["runtime_cache"][
            "champion_cached_runtime_pairs"
        ],
        runtime_aggregate_excluded=_runtime_aggregate_excluded(summary),
        candidate_runtime_pair_evidence_count=(
            runtime_aggregate_exclusion.get(
                "candidate_runtime_pair_evidence_count",
                0,
            )
            if isinstance(runtime_aggregate_exclusion, Mapping)
            else 0
        ),
    )
    if runtime_policy:
        summary["runtime_evidence_policy"] = runtime_policy
    zero_effect_summary = _activation_zero_effect_summary(
        previous_summary,
        current_phase=summary["phase_activation_summary"],
    )
    if zero_effect_summary:
        summary["activation_zero_effect_summary"] = zero_effect_summary
        summary["activation_zero_effect_streak"] = zero_effect_summary["streak"]
    runtime_pressure_count = _runtime_evidence_pressure_count(
        previous_summary,
        current_summary=summary,
        reason_codes=reason_codes,
    )
    summary["runtime_evidence_pressure_count"] = runtime_pressure_count
    runtime_pressure = _runtime_evidence_pressure_observation(
        summary,
        reason_codes,
    )
    if runtime_pressure:
        runtime_pressure["count"] = runtime_pressure_count
        runtime_pressure["clean_fork_threshold"] = 2
        runtime_pressure["proposal_guidance_only"] = True
        runtime_pressure["decision_features_excluded"] = True
        summary["runtime_evidence_pressure"] = runtime_pressure
        pressure_history = _historical_runtime_pressure(
            previous_summary,
        )
        if pressure_history:
            summary["history_runtime_evidence_pressure"] = pressure_history
    fresh_replay_step = bool(getattr(branch, "fresh_runtime_replay_step", False))
    fresh_runtime_followup = (
        {}
        if fresh_replay_step
        else _fresh_runtime_followup_marker(
            summary,
            reason_codes=reason_codes,
        )
    )
    if fresh_runtime_followup:
        summary["fresh_runtime_followup"] = fresh_runtime_followup
        summary["fresh_runtime_pending"] = True
        summary["fresh_runtime_required"] = bool(
            fresh_runtime_followup.get("fresh_runtime_required")
        )
    elif fresh_replay_step:
        summary.update(_fresh_runtime_replay_closure(previous_summary, summary))
    plateau_gate = _plateau_gate_observation(
        previous_summary,
        current_summary=summary,
        reason_codes=reason_codes,
    )
    if plateau_gate:
        summary["plateau_gate"] = plateau_gate
    history_codes = _historical_reason_codes(previous_summary, reason_codes)
    if history_codes:
        summary["history_reason_codes"] = list(history_codes)
    history_phase_summaries = _historical_phase_activation_summaries(
        previous_summary,
        current_summary=summary,
    )
    if history_phase_summaries:
        summary["history_phase_activation_summaries"] = history_phase_summaries
    history_runtime_confidences = _historical_runtime_confidences(
        previous_summary,
        current_runtime_confidence=summary["runtime_evidence_confidence"],
    )
    if history_runtime_confidences:
        summary["history_runtime_evidence_confidences"] = list(
            history_runtime_confidences
        )
    best_checkpoint_codes = _best_checkpoint_reason_codes(
        branch,
        previous_summary=previous_summary,
        current_summary=summary,
        current_reason_codes=reason_codes,
    )
    if best_checkpoint_codes:
        summary["best_checkpoint_reason_codes"] = list(best_checkpoint_codes)
        summary.update(_best_checkpoint_summary_fields(previous_summary))
    branch.branch_evidence_summary = summary


def _summary_reason_codes(summary: Mapping[str, Any]) -> tuple[str, ...]:
    return _string_tuple(
        summary.get("why_not_promoted_reason_codes")
        or summary.get("decision_reason_codes")
        or summary.get("reason_codes")
    )


def _historical_reason_codes(
    previous_summary: Mapping[str, Any],
    current_reason_codes: tuple[str, ...],
) -> tuple[str, ...]:
    previous_history = _string_tuple(previous_summary.get("history_reason_codes"))
    previous_codes = _summary_reason_codes(previous_summary)
    codes: list[str] = list(previous_history)
    if previous_codes and previous_codes != current_reason_codes:
        codes.extend(previous_codes)
    return tuple(dict.fromkeys(codes))


def _best_checkpoint_reason_codes(
    branch: Branch,
    *,
    previous_summary: Mapping[str, Any],
    current_summary: Mapping[str, Any],
    current_reason_codes: tuple[str, ...],
) -> tuple[str, ...]:
    previous_best = _string_tuple(
        previous_summary.get("best_checkpoint_reason_codes")
    )
    if previous_best:
        return previous_best
    previous_codes = _summary_reason_codes(previous_summary)
    if not previous_codes or previous_codes == current_reason_codes:
        return ()
    if not getattr(branch, "best_quality_checkpoint_id", None):
        return ()
    if _screening_tier_rank(previous_summary.get("tier")) <= _screening_tier_rank(
        current_summary.get("tier")
    ):
        return ()
    return previous_codes


def _best_checkpoint_summary_fields(
    previous_summary: Mapping[str, Any],
) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    existing_generic = previous_summary.get("best_checkpoint_generic_evidence_summary")
    if isinstance(existing_generic, Mapping):
        fields["best_checkpoint_generic_evidence_summary"] = dict(existing_generic)
        existing_phase = previous_summary.get("best_checkpoint_phase_activation_summary")
        if isinstance(existing_phase, Mapping):
            fields["best_checkpoint_phase_activation_summary"] = dict(existing_phase)
        existing_runtime = str(
            previous_summary.get("best_checkpoint_runtime_evidence_confidence") or ""
        ).strip()
        if existing_runtime:
            fields["best_checkpoint_runtime_evidence_confidence"] = existing_runtime
        existing_telemetry = str(
            previous_summary.get("best_checkpoint_telemetry_outcome") or ""
        ).strip()
        if existing_telemetry:
            fields["best_checkpoint_telemetry_outcome"] = existing_telemetry
        return fields
    fields["best_checkpoint_generic_evidence_summary"] = _generic_evidence_payload(
        previous_summary
    )
    phase = previous_summary.get("phase_activation_summary")
    if isinstance(phase, Mapping):
        fields["best_checkpoint_phase_activation_summary"] = dict(phase)
    runtime_confidence = str(
        previous_summary.get("runtime_evidence_confidence") or ""
    ).strip()
    if runtime_confidence:
        fields["best_checkpoint_runtime_evidence_confidence"] = runtime_confidence
    telemetry_outcome = (
        fields.get("best_checkpoint_phase_activation_summary") or {}
    ).get("telemetry_outcome")
    if telemetry_outcome:
        fields["best_checkpoint_telemetry_outcome"] = telemetry_outcome
    return fields


def _generic_evidence_payload(summary: Mapping[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "tier": str(summary.get("tier") or "unknown"),
    }
    for key in ("wins", "losses", "ties"):
        if summary.get(key) is not None:
            payload[key] = summary.get(key)
    effect = {
        key: summary.get(key)
        for key in ("median_delta", "ci_low", "ci_high")
        if summary.get(key) is not None
    }
    if effect:
        payload["effect"] = effect
    runtime = {
        key: summary.get(key)
        for key in (
            "runtime_ratio_median",
            "runtime_delta_median_ms",
            "runtime_regression_rate",
            "runtime_pairs",
        )
        if summary.get(key) is not None
    }
    if runtime:
        payload["runtime"] = runtime
    runtime_confidence = str(
        summary.get("runtime_evidence_confidence") or ""
    ).strip()
    if runtime_confidence:
        payload["runtime_evidence_confidence"] = runtime_confidence
    return payload


def _historical_phase_activation_summaries(
    previous_summary: Mapping[str, Any],
    *,
    current_summary: Mapping[str, Any],
) -> list[dict[str, Any]]:
    history = [
        dict(item)
        for item in previous_summary.get("history_phase_activation_summaries") or ()
        if isinstance(item, Mapping)
    ]
    previous_phase = previous_summary.get("phase_activation_summary")
    current_phase = current_summary.get("phase_activation_summary")
    if (
        isinstance(previous_phase, Mapping)
        and previous_phase
        and previous_phase != current_phase
    ):
        history.append(dict(previous_phase))
    return _unique_mapping_history(history)


def _historical_runtime_confidences(
    previous_summary: Mapping[str, Any],
    *,
    current_runtime_confidence: Any,
) -> tuple[str, ...]:
    history = list(
        _string_tuple(previous_summary.get("history_runtime_evidence_confidences"))
    )
    previous_runtime = str(
        previous_summary.get("runtime_evidence_confidence") or ""
    ).strip()
    if previous_runtime and previous_runtime != str(current_runtime_confidence or ""):
        history.append(previous_runtime)
    return tuple(dict.fromkeys(history))


def _unique_mapping_history(items: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    unique: list[dict[str, Any]] = []
    seen: set[tuple[tuple[str, str], ...]] = set()
    for item in items:
        marker = tuple(sorted((str(key), str(value)) for key, value in item.items()))
        if marker in seen:
            continue
        seen.add(marker)
        unique.append(dict(item))
    return unique


def _screening_tier_rank(tier: Any) -> int:
    return {
        "promotable": 7,
        "weak_positive": 6,
        "marginal": 5,
        "last_valid": 4,
        "no_effect": 4,
        "diagnostic": 3,
        "regression": 2,
        "quality_regression": 2,
        "invalid": 1,
    }.get(str(tier or ""), 0)


def _screening_gate_reason_codes(reason_codes: Iterable[str]) -> tuple[str, ...]:
    return tuple(
        code
        for code in _string_tuple(tuple(reason_codes or ()))
        if _is_gate_observation_reason_code(code)
    )


def _runtime_evidence_pressure_count(
    previous_summary: Mapping[str, Any],
    *,
    current_summary: Mapping[str, Any],
    reason_codes: tuple[str, ...],
) -> int:
    if not _runtime_evidence_pressure_applicable(current_summary):
        return 0
    if not _runtime_evidence_pressure_detected(current_summary, reason_codes):
        return 0
    return (
        max(
            0,
            int(previous_summary.get("runtime_evidence_pressure_count") or 0),
        )
        + 1
    )


def _runtime_evidence_pressure_detected(
    summary: Mapping[str, Any],
    reason_codes: tuple[str, ...],
) -> bool:
    return bool(_runtime_evidence_pressure_observation(summary, reason_codes))


def _runtime_evidence_pressure_observation(
    summary: Mapping[str, Any],
    reason_codes: tuple[str, ...],
) -> dict[str, Any]:
    if not _runtime_evidence_pressure_applicable(summary):
        return {}
    confidence = str(
        summary.get("runtime_evidence_confidence") or ""
    ).strip().lower()
    status = str(summary.get("runtime_evidence_status") or "").strip().lower()
    triggers: list[str] = []
    if confidence.startswith("low") or "cached" in confidence:
        triggers.append("low_or_cached_runtime_confidence")
    if status in {
        "insufficient",
        "fresh_champion_required",
        "fresh_required",
        "incomplete",
    }:
        triggers.append(f"runtime_evidence_status:{status}")
    if _runtime_aggregate_excluded(summary):
        triggers.append("runtime_aggregate_excluded")
    reason_set = {str(code).upper() for code in reason_codes}
    saturation_reason = (
        "SCREENING_RUNTIME_BUDGET_SATURATION" in reason_set
        or "TINY_RUNTIME_BUDGET_SATURATION" in reason_set
        or CANDIDATE_RUNTIME_BUDGET_SATURATION in reason_set
        or BOTH_RUNTIME_BUDGET_SATURATION in reason_set
        or "SCREENING_RUNTIME_SATURATION_DIAGNOSTIC" in reason_set
    )
    if saturation_reason:
        wins = max(0, int(summary.get("wins") or 0))
        pair_wins = max(0, int(summary.get("pair_wins") or 0))
        median_delta = summary.get("median_delta")
        try:
            positive_delta = median_delta is not None and float(median_delta) > 1e-12
        except (TypeError, ValueError):
            positive_delta = False
        if wins == 0 and pair_wins == 0 and not positive_delta:
            triggers.append("runtime_saturation_without_objective_signal")
    if not triggers:
        return {}
    return {
        "triggers": list(dict.fromkeys(triggers)),
        "runtime_evidence_confidence": confidence or "unknown",
        "runtime_evidence_status": status or "unknown",
        "runtime_aggregate_excluded": _runtime_aggregate_excluded(summary),
        "runtime_signal_role": "audit_or_proposal_guidance_only",
        "standalone_optimization_signal": False,
    }


def _runtime_evidence_pressure_applicable(summary: Mapping[str, Any]) -> bool:
    return _runtime_evidence_pressure_runtime_model(summary) != "budget_exhausting"


def _runtime_evidence_pressure_runtime_model(summary: Mapping[str, Any]) -> str:
    runtime_model = runtime_model_from_summary(summary, default="")
    if runtime_model:
        return runtime_model
    policy = summary.get("runtime_evidence_policy")
    if isinstance(policy, Mapping):
        return runtime_model_from_summary(policy, default="")
    return ""


def _plateau_gate_observation(
    previous_summary: Mapping[str, Any],
    *,
    current_summary: Mapping[str, Any],
    reason_codes: tuple[str, ...],
) -> dict[str, Any]:
    tier = str(current_summary.get("tier") or "").strip().lower()
    if tier not in {"no_effect", "marginal"}:
        return {}
    runtime_pressure = current_summary.get("runtime_evidence_pressure")
    runtime_pressure_map = (
        runtime_pressure if isinstance(runtime_pressure, Mapping) else {}
    )
    runtime_pressure_count = max(
        0,
        int(current_summary.get("runtime_evidence_pressure_count") or 0),
    )
    reason_set = {str(code).strip().upper() for code in reason_codes}
    triggers = [f"tier:{tier}"]
    triggers.extend(
        str(item)
        for item in runtime_pressure_map.get("triggers", ())
        if str(item).strip()
    )
    if reason_set.intersection(
        {
            "SCREENING_RUNTIME_BUDGET_SATURATION",
            "TINY_RUNTIME_BUDGET_SATURATION",
            CANDIDATE_RUNTIME_BUDGET_SATURATION,
            BOTH_RUNTIME_BUDGET_SATURATION,
            "SCREENING_RUNTIME_SATURATION_DIAGNOSTIC",
            "SCREENING_RUNTIME_SATURATION_REROUTE",
            "SCREENING_RUNTIME_EVIDENCE_INCOMPLETE_PRESSURE",
        }
    ):
        triggers.append("runtime_budget_or_completeness_pressure")
    if reason_set.intersection(
        {
            "SCREENING_TELEMETRY_EFFECT_ZERO_DIAGNOSTIC",
            "SCREENING_TELEMETRY_EFFECT_ZERO_REROUTE",
            "SCREENING_TELEMETRY_DIAGNOSTIC_RETRY",
        }
    ):
        triggers.append("telemetry_or_activation_diagnostic")
    if not runtime_pressure_count and len(triggers) <= 1:
        return {}

    previous_gate = previous_summary.get("plateau_gate")
    previous_effective_count = 0
    previous_sampled = False
    if isinstance(previous_gate, Mapping):
        previous_sampled = bool(previous_gate.get("same_branch_refinement_sampled"))
        try:
            previous_effective_count = max(
                0,
                int(previous_gate.get("effective_screened_no_effect_count") or 0),
            )
        except (TypeError, ValueError):
            previous_effective_count = 0
    threshold = 2
    effective_count = previous_effective_count + 1
    threshold_met = (
        effective_count >= threshold
        and runtime_pressure_count >= threshold
        and tier in {"no_effect", "marginal"}
    )
    reason_codes_out = ["PLATEAU_GATE_LOW_SIGNAL_RUNTIME_PRESSURE"]
    if threshold_met:
        reason_codes_out.append("PLATEAU_GATE_THRESHOLD_MET")
    if "telemetry_or_activation_diagnostic" in triggers:
        reason_codes_out.append("PLATEAU_GATE_TELEMETRY_DIAGNOSTIC")
    return {
        "schema_version": "plateau_gate.v1",
        "stage": "screening",
        "tier": tier,
        "effective_screened_no_effect_count": effective_count,
        "effective_screened_no_effect_threshold": threshold,
        "runtime_evidence_pressure_count": runtime_pressure_count,
        "runtime_pressure_threshold": threshold,
        "threshold_met": threshold_met,
        "same_branch_refinement_sampled": previous_sampled,
        "scheduler_preference": (
            "same_branch_diagnostic_refinement"
            if threshold_met and not previous_sampled and effective_count == threshold
            else "clean_fork_material_difference_required"
            if threshold_met
            else "observe"
        ),
        "allowed_same_branch_actions": [
            "diagnostic",
            "observability",
            "refine",
            "repair",
            "parameterize",
            "telemetry_wiring",
        ],
        "clean_fork_metadata_requirement": (
            "material_difference_required" if threshold_met else "not_required"
        ),
        "reason_codes": reason_codes_out,
        "triggers": list(dict.fromkeys(triggers)),
        "proposal_guidance_only": True,
        "audit_only": True,
        "decision_features_excluded": True,
    }


def _runtime_aggregate_excluded(summary: Mapping[str, Any]) -> bool:
    exclusion = summary.get("runtime_aggregate_exclusion")
    if isinstance(exclusion, Mapping):
        if "excluded" in exclusion:
            return bool(exclusion.get("excluded"))
        return bool(exclusion)
    return bool(exclusion)


def _fresh_runtime_followup_marker(
    summary: Mapping[str, Any],
    *,
    reason_codes: tuple[str, ...],
) -> dict[str, Any]:
    if not _fresh_champion_runtime_required(summary, reason_codes):
        return {}
    pair_wins = max(0, int(summary.get("pair_wins") or 0))
    pair_losses = max(0, int(summary.get("pair_losses") or 0))
    losses = max(0, int(summary.get("losses") or 0))
    pair_win_no_loss = pair_wins > 0 and pair_losses == 0
    actionable_loss_signal = fresh_runtime_actionable_loss_signal(
        summary,
        reason_codes,
    )
    actionable_loss_diagnostic = (
        (losses > 0 or pair_losses > 0)
        and actionable_loss_signal.has_actionable_loss_signal
    )
    if not pair_win_no_loss and not actionable_loss_diagnostic:
        return {}
    trigger = (
        "pair_level_win_no_loss"
        if pair_win_no_loss
        else "actionable_loss_diagnostic"
    )
    required = pair_win_no_loss or actionable_loss_diagnostic
    marker = {
        "schema_version": "fresh_runtime_followup.v1",
        "stage": "screening",
        "queue_intent": "fresh_champion_runtime_replay",
        "scheduler_marker": "fresh_champion_runtime_replay_pending",
        "trigger": trigger,
        "fresh_runtime_pending": True,
        "fresh_runtime_required": required,
        "followup_recommended": True,
        "followup_required": required,
        "followup_policy": (
            "fresh_champion_runtime_required_before_runtime_based_escalation"
            if pair_win_no_loss
            else "fresh_champion_runtime_or_diagnostic_followup_required"
        ),
        "pair_summary": {
            "wins": pair_wins,
            "losses": pair_losses,
            "ties": max(0, int(summary.get("pair_ties") or 0)),
        },
        "case_summary": {
            "wins": max(0, int(summary.get("wins") or 0)),
            "losses": losses,
            "ties": max(0, int(summary.get("ties") or 0)),
        },
        "runtime_evidence_confidence": str(
            summary.get("runtime_evidence_confidence") or "unknown"
        ),
        "runtime_evidence_status": str(
            summary.get("runtime_evidence_status") or "unknown"
        ),
        "runtime_aggregate_excluded": _runtime_aggregate_excluded(summary),
        "reason_codes": [
            code
            for code in reason_codes
            if _fresh_runtime_followup_reason_code(code)
        ],
        "promotion_boundary": "not_a_promotion_or_validation_decision",
        "proposal_visibility_only": True,
        "decision_features_excluded": True,
    }
    if actionable_loss_diagnostic:
        marker["actionable_loss_signal"] = actionable_loss_signal.as_metadata()
    return marker


def _fresh_runtime_replay_closure(
    previous_summary: Mapping[str, Any],
    current_summary: Mapping[str, Any],
) -> dict[str, Any]:
    previous_marker = previous_summary.get("fresh_runtime_followup")
    marker = dict(previous_marker) if isinstance(previous_marker, Mapping) else {}
    cached_pairs = 0
    cache = current_summary.get("runtime_cache")
    if isinstance(cache, Mapping):
        cached_pairs = max(0, int(cache.get("champion_cached_runtime_pairs") or 0))
    status = str(
        current_summary.get("runtime_evidence_status") or ""
    ).strip().lower()
    if status in {"fresh_champion_required", "fresh_required"}:
        closure_status = "capped_reject_fresh_champion_still_required"
    elif cached_pairs > 0:
        closure_status = "capped_reject_still_cached_or_incomplete"
    else:
        closure_status = "fresh_evidence_recorded"
    marker.update(
        {
            "fresh_runtime_pending": False,
            "scheduler_marker": "fresh_champion_runtime_replay_closed",
            "closure_status": closure_status,
            "decision_features_excluded": True,
        }
    )
    return {
        "fresh_runtime_followup": marker,
        "fresh_runtime_pending": False,
        "fresh_runtime_required": False,
        "fresh_runtime_replay_closure": {
            "schema_version": "fresh_runtime_replay_closure.v1",
            "closure_status": closure_status,
            "runtime_evidence_status": status or "unknown",
            "runtime_evidence_confidence": str(
                current_summary.get("runtime_evidence_confidence") or "unknown"
            ),
            "cache_stats": dict(cache) if isinstance(cache, Mapping) else {},
            "decision_features_excluded": True,
        },
    }


def _fresh_champion_runtime_required(
    summary: Mapping[str, Any],
    reason_codes: tuple[str, ...],
) -> bool:
    if runtime_model_from_summary(summary, default="") == "budget_exhausting":
        return False
    status = str(summary.get("runtime_evidence_status") or "").strip().lower()
    policy = summary.get("runtime_evidence_policy")
    policy_fresh = (
        bool(policy.get("fresh_champion_required"))
        if isinstance(policy, Mapping)
        else False
    )
    reason_set = {str(code).strip().upper() for code in reason_codes}
    return bool(
        status in {"fresh_champion_required", "fresh_required"}
        or policy_fresh
        or "RUNTIME_TIE_FRESH_CHAMPION_REQUIRED" in reason_set
        or "RUNTIME_EVIDENCE_FRESH_CHAMPION_REQUIRED" in reason_set
    )


def _has_actionable_loss_diagnostic(
    summary: Mapping[str, Any],
    reason_codes: tuple[str, ...],
) -> bool:
    return fresh_runtime_actionable_loss_signal(
        summary,
        reason_codes,
    ).has_actionable_loss_signal


def _fresh_runtime_followup_reason_code(code: str) -> bool:
    text = str(code or "").strip().upper()
    return bool(
        text
        and (
            "FRESH_CHAMPION" in text
            or "DIAGNOSTIC" in text
            or text in {"SCREENING_ACTIVE_PAIR_WINS_BUT_CASE_FAIL"}
        )
    )


def _historical_runtime_pressure(
    previous_summary: Mapping[str, Any],
) -> list[dict[str, Any]]:
    history = [
        dict(item)
        for item in previous_summary.get("history_runtime_evidence_pressure") or ()
        if isinstance(item, Mapping)
    ]
    previous = previous_summary.get("runtime_evidence_pressure")
    if isinstance(previous, Mapping) and previous:
        history.append(dict(previous))
    return _unique_mapping_history(history)[-6:]


def _activation_zero_effect_summary(
    previous_summary: Mapping[str, Any],
    *,
    current_phase: Mapping[str, Any],
) -> dict[str, Any]:
    if not _activation_observed_zero_effect(current_phase):
        return {}
    previous_streak = 0
    previous_zero = previous_summary.get("activation_zero_effect_summary")
    if isinstance(previous_zero, Mapping):
        try:
            previous_streak = max(0, int(previous_zero.get("streak") or 0))
        except (TypeError, ValueError):
            previous_streak = 0
    elif _activation_observed_zero_effect(
        previous_summary.get("phase_activation_summary")
        if isinstance(previous_summary.get("phase_activation_summary"), Mapping)
        else {}
    ):
        previous_streak = 1
    return {
        "streak": previous_streak + 1,
        "activation_status": str(current_phase.get("activation_status") or "unknown"),
        "effect_status": str(current_phase.get("effect_status") or "unknown"),
        "activation_evidence_status": str(
            current_phase.get("activation_evidence_status") or "unknown"
        ),
        "objective_effect_status": str(
            current_phase.get("objective_effect_status") or "unknown"
        ),
        "slot_health": "low_value_after_repeated_zero_effect",
        "proposal_guidance_only": True,
        "decision_features_excluded": True,
    }


def _activation_observed_zero_effect(phase: Mapping[str, Any]) -> bool:
    activation = str(phase.get("activation_status") or "").strip().lower()
    activation_evidence = str(
        phase.get("activation_evidence_status") or ""
    ).strip().lower()
    effect = str(phase.get("effect_status") or "").strip().lower()
    objective_effect = str(
        phase.get("objective_effect_status") or ""
    ).strip().lower()
    activation_observed = activation == "observed" or activation_evidence in {
        "activation_observed",
        "observed",
    }
    zero_effect = effect in {
        "no_objective_effect",
        "telemetry_effect_zero",
        "runtime_budget_no_objective_effect",
        "zero",
    } or objective_effect in {
        "no_objective_effect",
        "zero",
    }
    return activation_observed and zero_effect


def _is_gate_observation_reason_code(code: str) -> bool:
    text = str(code or "").strip().upper()
    if not text:
        return False
    if text.startswith("BRANCH_LIFECYCLE_"):
        return False
    if any(
        token in text.lower()
        for token in (
            "proposal",
            "schema",
            "duplicate",
            "c11",
            "premise",
            "agent_quality",
            "agent_grounding",
            "mechanism_novelty",
        )
    ):
        return False
    return text.startswith(
        (
            "SCREENING_",
            "VALIDATION_",
            "FROZEN_",
            "CANARY_",
            "TELEMETRY_",
            "NO_SCREENING_STATS",
        )
    )


def _string_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,) if value else ()
    if isinstance(value, (list, tuple, set)):
        return tuple(str(item) for item in value if str(item))
    return (str(value),)


def _compact_case_results(
    protocol_result: ProtocolResult,
    dominant_result: str,
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    case_feedback = list(getattr(protocol_result, "case_feedback", ()) or ())
    items: list[dict[str, Any]] = []
    for feedback in case_feedback:
        result = str(getattr(feedback, "dominant_result", "") or "")
        if result != dominant_result:
            continue
        items.append(_case_feedback_item(feedback, protocol_result))
        if len(items) >= limit:
            return items
    if items:
        return items
    return _compact_pair_results(protocol_result, dominant_result, limit=limit)


def _case_feedback_item(
    feedback: object,
    protocol_result: ProtocolResult,
) -> dict[str, Any]:
    deltas = getattr(feedback, "median_deltas", {}) or {}
    return {
        "case_id": str(getattr(feedback, "case_id", "") or ""),
        "result": str(getattr(feedback, "dominant_result", "") or ""),
        "delta": _selected_case_delta(deltas, protocol_result),
        "effect_counters": {
            "wins": max(0, int(getattr(feedback, "wins", 0) or 0)),
            "losses": max(0, int(getattr(feedback, "losses", 0) or 0)),
            "ties": max(0, int(getattr(feedback, "ties", 0) or 0)),
            "pairs": max(0, int(getattr(feedback, "n_pairs", 0) or 0)),
        },
    }


def _compact_pair_results(
    protocol_result: ProtocolResult,
    dominant_result: str,
    *,
    limit: int,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[object]] = {}
    for item in getattr(protocol_result, "pair_feedback", ()) or ():
        case_id = str(getattr(item, "case_id", "") or "")
        if case_id:
            grouped.setdefault(case_id, []).append(item)
    results: list[dict[str, Any]] = []
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
        results.append(
            {
                "case_id": case_id,
                "result": result,
                "delta": median(deltas) if deltas else None,
                "effect_counters": {
                    "wins": wins,
                    "losses": losses,
                    "ties": ties,
                    "pairs": len(rows),
                },
            }
        )
        if len(results) >= limit:
            return results
    return results


def _selected_case_delta(
    deltas: Mapping[str, Any],
    protocol_result: ProtocolResult,
) -> float | None:
    if not isinstance(deltas, Mapping) or not deltas:
        return None
    normalized = {str(key): value for key, value in deltas.items()}
    metric = str(getattr(protocol_result.stats, "statistical_metric", "") or "")
    keys = [metric] if metric else []
    keys.extend(sorted(key for key in normalized if key not in keys))
    for key in keys:
        try:
            return float(normalized[key])
        except (KeyError, TypeError, ValueError):
            continue
    return None


def park_lineage(
    branch: Branch,
    *,
    reason_codes: tuple[str, ...],
    checkpoint_retained: bool,
) -> None:
    branch.state = BranchState.PARKED_LINEAGE
    branch.branch_code_status = "parked_lineage"
    branch.last_telemetry_outcome = (
        "checkpoint_retained"
        if checkpoint_retained
        else "parked_lineage"
    )
    branch.branch_lifecycle_new_mechanism_ineligible = True
    branch.branch_lifecycle_reroute_reason = (
        BRANCH_LIFECYCLE_REROUTE_AFTER_POLICY_BLOCK
    )
    branch.updated_at = datetime.now()
    merge_branch_lifecycle_block(
        branch,
        action="park_lineage",
        reason_codes=reason_codes,
    )


def merge_branch_lifecycle_block(
    branch: Branch,
    *,
    action: str,
    reason_codes: tuple[str, ...],
) -> None:
    existing = dict(getattr(branch, "last_branch_lifecycle_policy_block", {}) or {})
    block_count = int(
        existing.get("block_count")
        or getattr(branch, "branch_lifecycle_policy_blocks", 0)
        or 0
    ) + 1
    lifecycle_reason_codes = tuple(
        dict.fromkeys(
            [
                *tuple(existing.get("lifecycle_action_reason_codes") or ()),
                *tuple(reason_codes or ()),
            ]
        )
    )
    existing.update(
        {
            "reason": action,
            "block_count": block_count,
            "reroute_reason": BRANCH_LIFECYCLE_REROUTE_AFTER_POLICY_BLOCK,
            "new_mechanism_ineligible_reason": (
                BRANCH_LIFECYCLE_NEW_MECHANISM_INELIGIBLE
            ),
            "lifecycle_action_reason_codes": list(lifecycle_reason_codes),
            "rollback_count": int(getattr(branch, "rollback_count", 0) or 0),
            "lifecycle_marginal_no_effect_streak": int(
                getattr(branch, "lifecycle_marginal_no_effect_streak", 0) or 0
            ),
            "lifecycle_no_effect_diagnostic_followups": int(
                getattr(branch, "lifecycle_no_effect_diagnostic_followups", 0)
                or 0
            ),
            "lifecycle_signal_repeat_count": int(
                getattr(branch, "lifecycle_signal_repeat_count", 0) or 0
            ),
            "lifecycle_last_signal_signature": getattr(
                branch,
                "lifecycle_last_signal_signature",
                None,
            ),
            "best_quality_checkpoint_id": getattr(
                branch,
                "best_quality_checkpoint_id",
                None,
            ),
            "last_valid_checkpoint_id": getattr(
                branch,
                "last_valid_checkpoint_id",
                None,
            ),
        }
    )
    branch.branch_lifecycle_policy_blocks = block_count
    branch.last_branch_lifecycle_policy_block = existing


__all__ = [
    "lifecycle_action",
    "merge_branch_lifecycle_block",
    "park_lineage",
    "update_branch_screening_evidence_summary",
    "update_branch_lifecycle_signal_state",
]
