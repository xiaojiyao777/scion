"""Structured branch-card evidence extraction helpers."""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from scion.core.branch_hygiene import (
    PARKED_BRANCH_CODE_STATUSES,
    SAME_MECHANISM_ALLOWED_ACTIONS,
    branch_code_status,
    branch_has_actionable_diagnostic,
    branch_has_retained_checkpoint,
    branch_is_parked_lineage,
    is_branch_lifecycle_policy_block,
)
from scion.core.models import Branch


def _branch_state_value(branch: Branch | None) -> str:
    if branch is None:
        return "unknown"
    state = getattr(branch, "state", None)
    return str(getattr(state, "value", state) or "unknown")


def _branch_block(branch: Branch | None) -> Mapping[str, Any]:
    if branch is None:
        return {}
    block = getattr(branch, "last_branch_lifecycle_policy_block", {}) or {}
    return block if isinstance(block, Mapping) else {}


def _branch_lifecycle_block(branch: Branch | None) -> Mapping[str, Any]:
    block = _branch_block(branch)
    return block if is_branch_lifecycle_policy_block(block) else {}


def _branch_block_codes(branch: Branch | None, *keys: str) -> list[str]:
    block = _branch_block(branch)
    return _mapping_codes(block, *keys)


def _branch_lifecycle_block_codes(branch: Branch | None, *keys: str) -> list[str]:
    block = _branch_lifecycle_block(branch)
    return _mapping_codes(block, *keys)


def _branch_evidence_codes(branch: Branch | None, *keys: str) -> list[str]:
    evidence = _branch_evidence_summary(branch)
    return _mapping_codes(evidence, *keys)


def _best_checkpoint_mapping(branch: Branch | None, key: str) -> dict[str, Any]:
    value = _branch_evidence_summary(branch).get(key)
    return dict(value) if isinstance(value, Mapping) else {}


def _best_checkpoint_scalar(branch: Branch | None, key: str) -> Any:
    value = _branch_evidence_summary(branch).get(key)
    if isinstance(value, (Mapping, list, tuple, set)):
        return None
    return value


def _history_mapping_list(branch: Branch | None, key: str) -> list[dict[str, Any]]:
    value = _branch_evidence_summary(branch).get(key)
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes, Mapping)):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _mapping_codes(source: Mapping[str, Any], *keys: str) -> list[str]:
    codes: list[str] = []
    for key in keys:
        value = source.get(key)
        if isinstance(value, str):
            codes.extend([value] if value else [])
        elif isinstance(value, Iterable) and not isinstance(value, Mapping):
            codes.extend(str(item) for item in value if str(item))
    return list(dict.fromkeys(codes))


def _branch_rollback_codes(branch: Branch | None) -> list[str]:
    codes = _branch_lifecycle_block_codes(branch, "rollback_reason_codes")
    reason = (
        str(getattr(branch, "last_rollback_reason", "") or "")
        if branch is not None
        else ""
    )
    if reason:
        codes.append(reason)
    return list(dict.fromkeys(codes))


def _branch_evidence_summary(branch: Branch | None) -> Mapping[str, Any]:
    if branch is None:
        return {}
    value = getattr(branch, "branch_evidence_summary", {}) or {}
    return value if isinstance(value, Mapping) else {}


def _branch_case_outcomes(branch: Branch | None, key: str) -> list[dict[str, Any]]:
    evidence = _branch_evidence_summary(branch)
    block = _branch_block(branch)
    raw = evidence.get(key) or block.get(key) or []
    if not isinstance(raw, Iterable) or isinstance(raw, (str, bytes, Mapping)):
        return []
    outcomes: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, Mapping):
            continue
        case_id = str(item.get("case_id") or "").strip()
        result = str(item.get("result") or "").strip()
        if not case_id or result not in {"win", "loss", "tie", "mixed"}:
            continue
        entry: dict[str, Any] = {"case_id": case_id, "result": result}
        delta = _optional_float(item.get("delta"))
        if delta is not None:
            entry["delta"] = delta
        counters = item.get("effect_counters")
        if isinstance(counters, Mapping):
            compact = {
                name: _optional_int(counters.get(name))
                for name in ("wins", "losses", "ties", "pairs")
            }
            compact = {name: value for name, value in compact.items() if value is not None}
            if compact:
                entry["effect_counters"] = compact
        outcomes.append(entry)
    return outcomes[:5]


def _branch_phase_activation_summary(branch: Branch | None) -> dict[str, Any]:
    evidence = _branch_evidence_summary(branch)
    raw = evidence.get("phase_activation_summary")
    if isinstance(raw, Mapping):
        return {
            "stage": str(raw.get("stage") or "unknown"),
            "activation_status": str(
                raw.get("activation_status") or "unknown"
            ),
            "effect_status": str(raw.get("effect_status") or "unknown"),
            "activation_evidence_status": str(
                raw.get("activation_evidence_status") or "unknown"
            ),
            "objective_effect_status": str(
                raw.get("objective_effect_status") or "unknown"
            ),
            "opportunity_status": str(
                raw.get("opportunity_status") or "unknown"
            ),
            "telemetry_outcome": raw.get("telemetry_outcome"),
        }
    return {
        "stage": "unknown",
        "activation_status": "unknown",
        "effect_status": str(
            getattr(branch, "last_telemetry_outcome", None) or "unknown"
        ),
        "activation_evidence_status": "unknown",
        "objective_effect_status": "unknown",
        "opportunity_status": "unknown",
        "telemetry_outcome": (
            getattr(branch, "last_telemetry_outcome", None)
            if branch is not None
            else None
        ),
    }


def _branch_runtime_evidence_confidence(branch: Branch | None) -> str:
    evidence = _branch_evidence_summary(branch)
    for value in (
        evidence.get("runtime_evidence_confidence"),
        evidence.get("runtime_confidence"),
    ):
        text = str(value or "").strip()
        if text:
            return text
    return "unknown"


def _branch_runtime_evidence_pressure_count(branch: Branch | None) -> int | None:
    value = _branch_evidence_summary(branch).get("runtime_evidence_pressure_count")
    count = _optional_int(value)
    if count is None:
        return None
    return max(0, count)


def _branch_fresh_runtime_followup(branch: Branch | None) -> dict[str, Any]:
    evidence = _branch_evidence_summary(branch)
    value = evidence.get("fresh_runtime_followup")
    if isinstance(value, Mapping):
        return dict(value)
    reason_codes = {
        str(code).strip().upper()
        for code in _mapping_codes(
            evidence,
            "reason_codes",
            "decision_reason_codes",
            "why_not_promoted_reason_codes",
            "gate_observation_reason_codes",
        )
    }
    runtime_status = str(evidence.get("runtime_evidence_status") or "").lower()
    fresh_required = bool(
        evidence.get("fresh_runtime_required")
        or runtime_status in {"fresh_champion_required", "fresh_required"}
        or "RUNTIME_TIE_FRESH_CHAMPION_REQUIRED" in reason_codes
        or "RUNTIME_EVIDENCE_FRESH_CHAMPION_REQUIRED" in reason_codes
    )
    if not fresh_required:
        return {}
    pending = bool(evidence.get("fresh_runtime_pending"))
    return {
        "schema_version": "fresh_runtime_followup.v1",
        "queue_intent": "fresh_champion_runtime_replay",
        "scheduler_marker": (
            "fresh_champion_runtime_replay_pending"
            if pending
            else "fresh_champion_runtime_replay_pressure"
        ),
        "trigger": "fresh_runtime_required",
        "fresh_runtime_pending": pending,
        "fresh_runtime_required": True,
        "followup_recommended": True,
        "followup_required": True,
        "decision_features_excluded": True,
    }


def _branch_code_retention_status(branch: Branch | None) -> str:
    status = branch_code_status(branch)
    if status in {
        "discarded",
        "regressed_followup",
        "quality_regression",
        "active_quality_regression",
    }:
        return "discarded"
    if status.startswith("active_") or status.startswith("restored_"):
        return "retained"
    if branch_has_retained_checkpoint(branch):
        return "checkpoint_retained"
    if branch_is_parked_lineage(branch):
        return "parked"
    return "unknown"


def _branch_evidence_retention_status(branch: Branch | None) -> str:
    evidence = _branch_evidence_summary(branch)
    explicit = str(evidence.get("evidence_retention_status") or "").strip()
    if explicit:
        return explicit
    if evidence:
        return "retained"
    return "unknown"


def _current_reason_codes(branch: Branch | None) -> list[str]:
    return _branch_evidence_codes(
        branch,
        "why_not_promoted_reason_codes",
        "decision_reason_codes",
        "effective_reason_codes",
        "reason_codes",
    )


def _current_gate_observation_codes(branch: Branch | None) -> list[str]:
    codes = _branch_evidence_codes(branch, "gate_observation_reason_codes")
    codes.extend(
        code
        for code in _current_reason_codes(branch)
        if _is_current_gate_observation_code(code)
    )
    return list(dict.fromkeys(codes))


def _lifecycle_action_reason_codes(branch: Branch | None) -> list[str]:
    codes = _branch_evidence_codes(branch, "lifecycle_action_reason_codes")
    codes.extend(
        _branch_lifecycle_block_codes(
            branch,
            "lifecycle_action_reason_codes",
            "decision_reason_codes",
            "reason_codes",
        )
    )
    return list(dict.fromkeys(codes))


def _best_checkpoint_reason_codes(branch: Branch | None) -> list[str]:
    return _branch_evidence_codes(branch, "best_checkpoint_reason_codes")


def _history_reason_codes(branch: Branch | None) -> list[str]:
    codes = _branch_evidence_codes(branch, "history_reason_codes")
    block = _branch_block(branch)
    if block and not is_branch_lifecycle_policy_block(block):
        current = set(_current_reason_codes(branch))
        codes.extend(
            code
            for code in _mapping_codes(
                block,
                "gate_observation_reason_codes",
                "why_not_promoted_reason_codes",
                "decision_reason_codes",
                "reason_codes",
            )
            if code not in current
        )
    return list(dict.fromkeys(codes))


def _why_not_promoted_codes(branch: Branch | None) -> list[str]:
    if branch is None:
        return []
    codes = list(getattr(branch, "failure_codes", None) or ())
    codes.extend(_current_reason_codes(branch))
    codes.extend(_branch_evidence_codes(branch, "terminal_reason_codes"))
    if not codes:
        codes.extend(
            _branch_lifecycle_block_codes(
                branch,
                "lifecycle_action_reason_codes",
                "decision_reason_codes",
                "reason_codes",
            )
        )
    return list(
        dict.fromkeys(
            str(code)
            for code in codes
            if str(code) and not _is_proposal_block_code(str(code))
        )
    )


def _proposal_block_codes(branch: Branch | None) -> list[str]:
    if branch is None:
        return []
    codes = list(getattr(branch, "failure_codes", None) or ())
    codes.extend(
        _branch_evidence_codes(
            branch,
            "proposal_block_reason_codes",
            "schema_reason_codes",
            "proposal_quality_reason_codes",
            "reason_codes",
        )
    )
    return list(
        dict.fromkeys(str(code) for code in codes if _is_proposal_block_code(str(code)))
    )


def _why_abandoned_codes(branch: Branch | None) -> list[str]:
    if branch is None or _branch_state_value(branch) != "abandoned":
        return []
    codes = _why_not_promoted_codes(branch)
    return codes or ["abandoned_without_promotable_evidence"]


def _branch_generic_evidence_summary(
    branch: Branch | None,
    *,
    current_tier: Any,
) -> dict[str, Any]:
    evidence = _branch_evidence_summary(branch)
    source: Mapping[str, Any] = evidence
    status = branch_code_status(branch)
    tier = (
        str(current_tier or "").strip()
        or str(source.get("tier") or "").strip()
        or _tier_from_status(status)
    )
    summary: dict[str, Any] = {"tier": tier or "unknown"}
    metric_keys = {
        "wins": ("wins", "case_wins", "pair_wins", "screening_case_wins"),
        "losses": ("losses", "case_losses", "pair_losses", "screening_case_losses"),
        "ties": ("ties", "case_ties", "pair_ties", "screening_case_ties"),
    }
    for name, keys in metric_keys.items():
        value = _metric_value(source, keys, int)
        if value is not None:
            summary[name] = value
    for group, keys in {
        "effect": ("median_delta", "ci_low", "ci_high"),
        "runtime": (
            "runtime_ratio_median",
            "runtime_delta_median_ms",
            "runtime_regression_rate",
            "runtime_pairs",
        ),
    }.items():
        values = {key: _metric_value(source, (key,), float) for key in keys}
        values = {key: value for key, value in values.items() if value is not None}
        if values:
            summary[group] = values
    runtime_confidence = _branch_runtime_evidence_confidence(branch)
    if runtime_confidence != "unknown":
        summary["runtime_evidence_confidence"] = runtime_confidence
    runtime_pressure_count = _branch_runtime_evidence_pressure_count(branch)
    if runtime_pressure_count is not None:
        summary["runtime_evidence_pressure_count"] = runtime_pressure_count
    runtime_aggregate_exclusion = source.get("runtime_aggregate_exclusion")
    if isinstance(runtime_aggregate_exclusion, Mapping) and runtime_aggregate_exclusion:
        summary["runtime_aggregate_exclusion"] = dict(runtime_aggregate_exclusion)
    fresh_runtime_followup = _branch_fresh_runtime_followup(branch)
    if fresh_runtime_followup:
        summary["fresh_runtime_pending"] = bool(
            fresh_runtime_followup.get("fresh_runtime_pending")
        )
        summary["fresh_runtime_required"] = bool(
            fresh_runtime_followup.get("fresh_runtime_required")
        )
        summary["fresh_runtime_trigger"] = str(
            fresh_runtime_followup.get("trigger") or ""
        )
    return summary


def _tier_from_status(status: str) -> str:
    if status.startswith("active_"):
        return status.removeprefix("active_")
    if "regress" in status:
        return "regression"
    if status in PARKED_BRANCH_CODE_STATUSES:
        return "diagnostic"
    return "unknown"


def _metric_value(
    source: Mapping[str, Any],
    keys: Iterable[str],
    caster: Any,
) -> Any | None:
    for key in keys:
        value = source.get(key)
        if value is None:
            continue
        try:
            return caster(value)
        except (TypeError, ValueError):
            continue
    return None


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _is_proposal_block_code(code: str) -> bool:
    text = str(code or "").strip().lower()
    if not text:
        return False
    tokens = (
        "proposal",
        "schema",
        "duplicate",
        "c11",
        "premise",
        "agent_quality",
        "agent_grounding",
        "mechanism_novelty",
        "mechanism_changes_duplicate_id",
    )
    return any(token in text for token in tokens)


def _is_lifecycle_action_code(code: str) -> bool:
    return str(code or "").strip().upper().startswith("BRANCH_LIFECYCLE_")


def _is_current_gate_observation_code(code: str) -> bool:
    text = str(code or "").strip().upper()
    if not text:
        return False
    if _is_lifecycle_action_code(text) or _is_proposal_block_code(text):
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


def _branch_card_allowed_actions(
    branch: Branch | None,
    *,
    lineage_status: str,
    strict_same_mechanism_followup: bool,
    repair_focus_required: bool,
) -> list[str]:
    if branch_is_parked_lineage(branch):
        return ["clean_fork"]
    if lineage_status == "replay_blocked":
        return ["clean_fork"]
    if lineage_status == "active_no_effect" and not branch_has_actionable_diagnostic(
        branch
    ):
        return ["clean_fork"]
    actions: list[str] = []
    if repair_focus_required:
        actions.extend(["repair", "telemetry_wiring"])
    if lineage_status in {
        "active_weak_positive",
        "restored_weak_positive",
        "restored_checkpoint",
        "checkpoint_retained",
    }:
        actions.append("refine_checkpoint")
    if lineage_status in {
        "active_weak_positive",
        "restored_weak_positive",
        "active_marginal",
    }:
        actions.extend(["tune", "integrate", "parameterize"])
    if strict_same_mechanism_followup:
        actions.extend(SAME_MECHANISM_ALLOWED_ACTIONS)
    if lineage_status == "active_no_effect":
        actions.extend(["diagnose", "repair"])
    if not actions:
        actions.append("open_exploration")
    return list(dict.fromkeys(actions))


def _branch_card_forbidden_actions(
    branch: Branch | None,
    *,
    lineage_status: str,
    strict_same_mechanism_followup: bool,
    latest_head_failed: bool,
    has_checkpoint: bool,
) -> list[str]:
    forbidden: list[str] = []
    if branch_is_parked_lineage(branch):
        forbidden.append("consume_active_slot")
    if lineage_status == "replay_blocked":
        forbidden.extend(["consume_active_slot", "replay_without_identity"])
    if strict_same_mechanism_followup:
        forbidden.append("unrelated_mechanism")
    if lineage_status == "active_no_effect" and not branch_has_actionable_diagnostic(
        branch
    ):
        forbidden.append("unchanged_repeat")
    if latest_head_failed and has_checkpoint:
        forbidden.append("treat_failed_head_as_lineage_failure")
    return list(dict.fromkeys(forbidden))
