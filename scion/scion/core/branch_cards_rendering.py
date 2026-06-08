"""Branch-card text rendering helpers."""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from scion.core.branch_cards_evidence import _optional_int


def branch_prompt_card_from_context(context: Mapping[str, Any]) -> str:
    """Render an already reconciled generic branch-card context."""
    allowed = ",".join(_card_list(context.get("allowed_next_actions"))) or "none"
    forbidden = ",".join(_card_list(context.get("forbidden_next_actions"))) or "none"
    mechanism_ids = ",".join(_card_list(context.get("mechanism_ids"))) or "none"
    evidence = _format_evidence_summary(_card_mapping(context.get("generic_evidence_summary")))
    positive_cases = _format_case_outcomes(
        _card_mapping_list(
            context.get("case_level_positive_cases")
            or context.get("case_level_winners")
        )
    )
    negative_cases = _format_case_outcomes(
        _card_mapping_list(
            context.get("case_level_negative_cases")
            or context.get("case_level_losses")
        )
    )
    activation = _format_phase_activation_summary(
        _card_mapping(context.get("phase_activation_summary"))
    )
    best_checkpoint_evidence = _format_evidence_summary(
        _card_mapping(context.get("best_checkpoint_generic_evidence_summary"))
    )
    best_checkpoint_activation = _format_phase_activation_summary(
        _card_mapping(context.get("best_checkpoint_phase_activation_summary"))
    )
    history_activation = _format_phase_activation_history(
        _card_mapping_list(context.get("history_phase_activation_summaries"))
    )
    runtime_confidence = context.get("runtime_evidence_confidence") or "unknown"
    runtime_pressure_count = _optional_int(
        context.get("runtime_evidence_pressure_count")
    )
    code_retention = context.get("candidate_code_retention_status") or "unknown"
    evidence_retention = context.get("evidence_retention_status") or "unknown"
    fresh_runtime_followup = _card_mapping(context.get("fresh_runtime_followup"))
    why_not_promoted = (
        ",".join(_card_list(context.get("why_not_promoted_reason_codes"))) or "none"
    )
    proposal_blocks = (
        ",".join(_card_list(context.get("proposal_block_reason_codes"))) or "none"
    )
    why_abandoned = (
        ",".join(_card_list(context.get("why_abandoned_reason_codes"))) or "none"
    )
    optional_parts: list[str] = []
    if _card_mapping(context.get("best_checkpoint_generic_evidence_summary")):
        optional_parts.append(
            f"best_checkpoint_generic_evidence_summary={best_checkpoint_evidence}"
        )
    if _card_mapping(context.get("best_checkpoint_phase_activation_summary")):
        optional_parts.append(
            "best_checkpoint_phase_activation_summary="
            f"{best_checkpoint_activation}"
        )
    best_checkpoint_runtime_confidence = context.get(
        "best_checkpoint_runtime_evidence_confidence"
    )
    if best_checkpoint_runtime_confidence:
        optional_parts.append(
            "best_checkpoint_runtime_evidence_confidence="
            f"{best_checkpoint_runtime_confidence}"
        )
    current_head_release_reason = context.get(
        "current_head_active_slot_release_reason"
    )
    if current_head_release_reason:
        optional_parts.append(
            "current_head_active_slot_release_reason="
            f"{current_head_release_reason}"
        )
    if context.get("retained_checkpoint_no_effect_current_head_released"):
        optional_parts.append(
            "retained_checkpoint_no_effect_current_head_released=true"
        )
    if history_activation != "none":
        optional_parts.append(
            f"history_phase_activation_summaries={history_activation}"
        )
    if runtime_pressure_count is not None:
        optional_parts.append(
            f"runtime_evidence_pressure_count={runtime_pressure_count}"
        )
    if fresh_runtime_followup:
        trigger = fresh_runtime_followup.get("trigger") or "fresh_runtime_required"
        policy = fresh_runtime_followup.get("followup_policy") or "fresh_runtime"
        optional_parts.append(
            "fresh_runtime_followup="
            f"{_compact_card_value(trigger)}:{_compact_card_value(policy)}"
        )
    runtime_advisory = _card_mapping(
        context.get("runtime_evidence_low_confidence_advisory")
        or context.get("runtime_evidence_clean_fork_guidance")
    )
    if runtime_advisory:
        optional_parts.append(
            "runtime_evidence_low_confidence_advisory="
            f"{runtime_advisory.get('reason') or 'fresh_runtime_required'}"
        )
    optional_suffix = (
        " " + " ".join(optional_parts)
        if optional_parts
        else ""
    )
    return (
        f"branch_id={context.get('branch_id') or 'unknown'} "
        f"status={context.get('status') or 'unknown'} "
        f"direction={_compact_card_value(context.get('direction'))} "
        f"mechanism_ids={mechanism_ids} "
        f"lineage_status={context.get('lineage_status') or 'unknown'} "
        f"current_head_status={context.get('current_head_status') or 'unknown'} "
        f"candidate_code_retention={code_retention} "
        f"evidence_retention={evidence_retention} "
        "followup_recommended="
        f"{str(bool(context.get('followup_recommended'))).lower()} "
        "followup_required="
        f"{str(bool(context.get('followup_required'))).lower()} "
        "fresh_runtime_pending="
        f"{str(bool(context.get('fresh_runtime_pending'))).lower()} "
        "fresh_runtime_required="
        f"{str(bool(context.get('fresh_runtime_required'))).lower()} "
        f"best_checkpoint_status={context.get('best_checkpoint_status') or 'none'} "
        f"best_quality_checkpoint_id={context.get('best_quality_checkpoint_id') or 'none'} "
        f"last_valid_checkpoint_id={context.get('last_valid_checkpoint_id') or 'none'} "
        f"rollback_count={context.get('rollback_count') or 0} "
        f"allowed_next_actions={allowed} "
        f"forbidden_next_actions={forbidden} "
        f"latest_head_failed={str(bool(context.get('latest_head_failed'))).lower()} "
        "lineage_retained_checkpoint="
        f"{str(bool(context.get('lineage_retained_checkpoint'))).lower()} "
        f"generic_evidence_summary={evidence} "
        f"case_level_positive_cases={positive_cases} "
        f"case_level_negative_cases={negative_cases} "
        f"phase_activation_summary={activation} "
        f"runtime_evidence_confidence={runtime_confidence} "
        f"why_not_promoted_reason_codes={why_not_promoted} "
        f"proposal_block_reason_codes={proposal_blocks} "
        f"why_abandoned_reason_codes={why_abandoned}"
        f"{optional_suffix}"
    )


def _card_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value] if value else []
    if not isinstance(value, Iterable) or isinstance(value, Mapping):
        return []
    return [str(item) for item in value if str(item)]


def _card_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _card_mapping_list(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes, Mapping)):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _format_evidence_summary(summary: Mapping[str, Any]) -> str:
    parts = [f"tier:{summary.get('tier', 'unknown')}"]
    for key in ("wins", "losses", "ties"):
        if key in summary:
            parts.append(f"{key}:{summary[key]}")
    effect = summary.get("effect")
    if isinstance(effect, Mapping) and "median_delta" in effect:
        parts.append(f"effect:{effect['median_delta']}")
    runtime = summary.get("runtime")
    if isinstance(runtime, Mapping) and "runtime_ratio_median" in runtime:
        parts.append(f"runtime:{runtime['runtime_ratio_median']}")
    runtime_confidence = summary.get("runtime_evidence_confidence")
    if runtime_confidence:
        parts.append(f"runtime_confidence:{runtime_confidence}")
    runtime_pressure_count = _optional_int(
        summary.get("runtime_evidence_pressure_count")
    )
    if runtime_pressure_count is not None:
        parts.append(f"runtime_evidence_pressure_count:{runtime_pressure_count}")
    exclusion = summary.get("runtime_aggregate_exclusion")
    if isinstance(exclusion, Mapping) and exclusion.get("excluded"):
        reason = exclusion.get("reason") or exclusion.get("runtime_confidence")
        if reason:
            parts.append(f"runtime_aggregate_excluded:{reason}")
    if summary.get("fresh_runtime_pending"):
        trigger = summary.get("fresh_runtime_trigger") or "fresh_runtime_required"
        parts.append(f"fresh_runtime_pending:{trigger}")
    return ",".join(parts)


def _format_case_outcomes(outcomes: Iterable[Mapping[str, Any]]) -> str:
    parts: list[str] = []
    for item in outcomes:
        case_id = str(item.get("case_id") or "").strip()
        result = str(item.get("result") or "").strip()
        if not case_id or not result:
            continue
        delta = item.get("delta")
        counters = item.get("effect_counters")
        counter_text = ""
        if isinstance(counters, Mapping):
            counter_text = (
                f":w{counters.get('wins', 0)}"
                f"l{counters.get('losses', 0)}"
                f"t{counters.get('ties', 0)}"
            )
        delta_text = "" if delta is None else f":delta={delta}"
        parts.append(f"{case_id}:{result}{delta_text}{counter_text}")
    return "|".join(parts) if parts else "none"


def _format_phase_activation_summary(summary: Mapping[str, Any]) -> str:
    return ",".join(
        f"{key}:{_compact_card_value(summary.get(key))}"
        for key in (
            "stage",
            "activation_status",
            "effect_status",
            "activation_evidence_status",
            "objective_effect_status",
            "opportunity_status",
            "telemetry_outcome",
        )
        if summary.get(key) is not None
    ) or "none"


def _format_phase_activation_history(summaries: Iterable[Mapping[str, Any]]) -> str:
    parts = [
        _format_phase_activation_summary(summary)
        for summary in summaries
        if summary
    ]
    parts = [part for part in parts if part != "none"]
    return "|".join(parts) if parts else "none"


def _compact_card_value(value: Any) -> str:
    text = " ".join(str(value or "none").split())
    if len(text) > 96:
        text = text[:93].rstrip() + "..."
    return text.replace(" ", "_")
