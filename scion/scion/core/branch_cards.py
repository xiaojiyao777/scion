"""Branch card and prompt-context rendering helpers."""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from scion.core.branch_hygiene import (
    BRANCH_LOCAL_FOLLOWUP_MODE,
    BRANCH_LOCAL_FOLLOWUP_OR_EXPLICIT_BRIDGE,
    CLEAN_FORK_REQUIRED_FOR_NEW_MECHANISM,
    NO_UNRELATED_MECHANISM_IDS,
    OPEN_EXPLORATION_ALLOWED,
    OPEN_EXPLORATION_MODE,
    PARKED_BRANCH_CODE_STATUSES,
    REPAIR_FIRST_SAME_MECHANISM_OR_CLEAN_FORK,
    RUNTIME_SATURATED_DIVERSITY_REROUTE_GUIDANCE,
    SAME_MECHANISM_ALLOWED_ACTIONS,
    SAME_MECHANISM_FOLLOWUP_ONLY,
    SAME_MECHANISM_ONLY_MODE,
    WIRING_SUSPECT_REQUIRES_REPAIR,
    branch_checkpoint_status,
    branch_code_status,
    branch_has_actionable_diagnostic,
    branch_has_retained_checkpoint,
    is_branch_lifecycle_policy_block,
    branch_is_parked_lineage,
    branch_lifecycle_reroute_context,
    branch_lineage_status,
    branch_mechanism_ids,
    branch_requires_repair_focus,
    branch_requires_same_mechanism_followup,
)
from scion.core.models import Branch
from scion.core.scheduler import (
    branch_runtime_evidence_clean_fork_pressure_summary,
    branch_active_slot_release_reason,
    branch_counts_toward_active_slots,
)


def branch_prompt_card(branch: Branch | None) -> str:
    """Compact generic branch card for APS prompts and sibling summaries."""
    context = branch_hygiene_context(branch)
    return branch_prompt_card_from_context(context)


def branch_prompt_card_from_context(context: Mapping[str, Any]) -> str:
    """Render an already reconciled generic branch-card context."""
    allowed = ",".join(_card_list(context.get("allowed_next_actions"))) or "none"
    forbidden = ",".join(_card_list(context.get("forbidden_next_actions"))) or "none"
    mechanism_ids = ",".join(_card_list(context.get("mechanism_ids"))) or "none"
    evidence = _format_evidence_summary(_card_mapping(context.get("generic_evidence_summary")))
    winners = _format_case_outcomes(_card_mapping_list(context.get("case_level_winners")))
    losses = _format_case_outcomes(_card_mapping_list(context.get("case_level_losses")))
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
        f"case_level_winners={winners} "
        f"case_level_losses={losses} "
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


def active_slot_inventory_from_branch_cards(
    cards: Iterable[Mapping[str, Any]],
    *,
    max_active_branches: int | None = None,
) -> dict[str, Any] | None:
    """Reconcile status/summary active-slot fields from branch card payloads."""
    active_ids: list[str] = []
    parked_ids: list[str] = []
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
    if not saw_slot_metadata:
        return None
    unique_active_ids = list(dict.fromkeys(active_ids))
    parked_ids = list(dict.fromkeys(parked_ids))
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
    }
    if overflow_ids:
        inventory["overflow_branch_ids"] = overflow_ids
        inventory["overflow_count"] = len(overflow_ids)
        inventory["reconciliation_required"] = True
        inventory["reconciliation_policy"] = "active_slot_hard_cap_reconciled"
    return inventory


def branch_hygiene_context(branch: Branch | None) -> dict[str, Any]:
    """Prompt/status payload that makes branch-code provenance explicit."""
    status = branch_code_status(branch)
    last_screening_feedback_tier = (
        getattr(branch, "last_screening_feedback_tier", None)
        if branch is not None
        else None
    )
    last_telemetry_outcome = (
        getattr(branch, "last_telemetry_outcome", None)
        if branch is not None
        else None
    )
    repair_focus_required = branch_requires_repair_focus(branch)
    same_mechanism_followup_required = branch_requires_same_mechanism_followup(
        branch
    )
    weak_positive_followup = (
        status == "active_weak_positive"
        or last_screening_feedback_tier == "weak_positive"
    )
    parked_lineage = branch_is_parked_lineage(branch)
    strict_same_mechanism_followup = (
        same_mechanism_followup_required and not weak_positive_followup
    )
    followup_policy = (
        "parked_lineage_clean_fork_only"
        if parked_lineage
        else
        BRANCH_LOCAL_FOLLOWUP_OR_EXPLICIT_BRIDGE
        if weak_positive_followup
        else
        SAME_MECHANISM_FOLLOWUP_ONLY
        if same_mechanism_followup_required
        else OPEN_EXPLORATION_ALLOWED
    )
    generation_mode = (
        "clean_fork_only"
        if parked_lineage
        else
        BRANCH_LOCAL_FOLLOWUP_MODE
        if weak_positive_followup
        else
        SAME_MECHANISM_ONLY_MODE
        if strict_same_mechanism_followup
        else OPEN_EXPLORATION_MODE
    )
    clean_fork_policy = (
        "parked_lineage_clean_fork_required"
        if parked_lineage
        else
        CLEAN_FORK_REQUIRED_FOR_NEW_MECHANISM
        if strict_same_mechanism_followup
        else None
    )
    protected_mechanism_ids = list(branch_mechanism_ids(branch))
    allowed_mechanism_ids = (
        list(protected_mechanism_ids)
        if strict_same_mechanism_followup
        else []
    )
    if repair_focus_required:
        baseline_policy = "champion_required_for_repair"
        repair_focus_reason = WIRING_SUSPECT_REQUIRES_REPAIR
    elif parked_lineage:
        baseline_policy = "parked_lineage_clean_fork_required"
        repair_focus_reason = None
    elif weak_positive_followup:
        baseline_policy = "branch_workspace_branch_local_followup"
        repair_focus_reason = None
    elif status.startswith("active_"):
        baseline_policy = "branch_workspace_same_mechanism_followup_only"
        repair_focus_reason = None
    else:
        baseline_policy = "clean"
        repair_focus_reason = None
    lineage_status = branch_lineage_status(branch)
    current_head_status = status
    state_value = _branch_state_value(branch)
    counts_toward_active_slots = (
        branch_counts_toward_active_slots(branch) if branch is not None else False
    )
    current_head_active_slot_release_reason = (
        branch_active_slot_release_reason(branch) if branch is not None else ""
    )
    runtime_evidence_pressure_count = _branch_runtime_evidence_pressure_count(branch)
    runtime_low_confidence_advisory = (
        _runtime_evidence_prompt_advisory_projection(
            branch_runtime_evidence_clean_fork_pressure_summary(branch)
        )
    )
    best_checkpoint_status = branch_checkpoint_status(branch)
    rollback_count = (
        max(0, int(getattr(branch, "rollback_count", 0) or 0))
        if branch is not None
        else 0
    )
    latest_head_failed = status in {
        "discarded",
        "regressed_followup",
        "quality_regression",
        "active_quality_regression",
    }
    lineage_retained_checkpoint = branch_has_retained_checkpoint(branch)
    allowed_next_actions = _branch_card_allowed_actions(
        branch,
        lineage_status=lineage_status,
        strict_same_mechanism_followup=strict_same_mechanism_followup,
        repair_focus_required=repair_focus_required,
    )
    forbidden_next_actions = _branch_card_forbidden_actions(
        branch,
        lineage_status=lineage_status,
        strict_same_mechanism_followup=strict_same_mechanism_followup,
        latest_head_failed=latest_head_failed,
        has_checkpoint=lineage_retained_checkpoint,
    )
    context = {
        "branch_id": getattr(branch, "branch_id", None) if branch is not None else None,
        "lineage_id": (
            getattr(branch, "lineage_id", None)
            or getattr(branch, "branch_id", None)
        )
        if branch is not None
        else None,
        "direction": getattr(branch, "direction", None) if branch is not None else None,
        "status": state_value,
        "branch_code_status": status,
        "lineage_status": lineage_status,
        "current_head_status": current_head_status,
        "active_slot_status": (
            "active_slot"
            if counts_toward_active_slots
            else "parked_lineage"
            if branch_is_parked_lineage(branch)
            else "inactive"
        ),
        "counts_toward_active_slots": counts_toward_active_slots,
        "current_head_active_slot_release_reason": (
            current_head_active_slot_release_reason
        ),
        "retained_checkpoint_no_effect_current_head_released": (
            current_head_active_slot_release_reason
            == "retained_checkpoint_no_effect_current_head"
        ),
        "best_checkpoint_status": best_checkpoint_status,
        "best_quality_checkpoint_id": (
            getattr(branch, "best_quality_checkpoint_id", None)
            if branch is not None
            else None
        ),
        "last_valid_checkpoint_id": (
            getattr(branch, "last_valid_checkpoint_id", None)
            if branch is not None
            else None
        ),
        "rollback_count": rollback_count,
        "last_rollback_reason": (
            getattr(branch, "last_rollback_reason", None)
            if branch is not None
            else None
        ),
        "allowed_next_actions": allowed_next_actions,
        "forbidden_next_actions": forbidden_next_actions,
        "latest_head_failed": latest_head_failed,
        "lineage_retained_checkpoint": lineage_retained_checkpoint,
        "mechanism_ids": list(protected_mechanism_ids),
        "generic_evidence_summary": _branch_generic_evidence_summary(
            branch,
            current_tier=last_screening_feedback_tier,
        ),
        "current_head_generic_evidence_summary": _branch_generic_evidence_summary(
            branch,
            current_tier=last_screening_feedback_tier,
        ),
        "case_level_winners": _branch_case_outcomes(branch, "case_level_winners"),
        "case_level_losses": _branch_case_outcomes(branch, "case_level_losses"),
        "phase_activation_summary": _branch_phase_activation_summary(branch),
        "current_head_phase_activation_summary": _branch_phase_activation_summary(
            branch
        ),
        "runtime_evidence_confidence": _branch_runtime_evidence_confidence(branch),
        "current_head_runtime_evidence_confidence": (
            _branch_runtime_evidence_confidence(branch)
        ),
        "gate_observation_reason_codes": _current_gate_observation_codes(branch),
        "lifecycle_action_reason_codes": _lifecycle_action_reason_codes(branch),
        "rollback_reason_codes": _branch_rollback_codes(branch),
        "why_not_promoted_reason_codes": _why_not_promoted_codes(branch),
        "best_checkpoint_reason_codes": _best_checkpoint_reason_codes(branch),
        "history_reason_codes": _history_reason_codes(branch),
        "best_checkpoint_generic_evidence_summary": (
            _best_checkpoint_mapping(branch, "best_checkpoint_generic_evidence_summary")
        ),
        "best_checkpoint_phase_activation_summary": (
            _best_checkpoint_mapping(branch, "best_checkpoint_phase_activation_summary")
        ),
        "best_checkpoint_runtime_evidence_confidence": _best_checkpoint_scalar(
            branch,
            "best_checkpoint_runtime_evidence_confidence",
        ),
        "best_checkpoint_telemetry_outcome": _best_checkpoint_scalar(
            branch,
            "best_checkpoint_telemetry_outcome",
        ),
        "history_phase_activation_summaries": _history_mapping_list(
            branch,
            "history_phase_activation_summaries",
        ),
        "history_runtime_evidence_confidences": _branch_evidence_codes(
            branch,
            "history_runtime_evidence_confidences",
        ),
        "proposal_block_reason_codes": _proposal_block_codes(branch),
        "why_abandoned_reason_codes": _why_abandoned_codes(branch),
        "last_screening_feedback_tier": last_screening_feedback_tier,
        "last_telemetry_outcome": last_telemetry_outcome,
        "repair_focus_required": repair_focus_required,
        "same_mechanism_followup_required": same_mechanism_followup_required,
        "hypothesis_generation_mode": generation_mode,
        "repair_focus_reason": repair_focus_reason,
        "repair_policy": (
            REPAIR_FIRST_SAME_MECHANISM_OR_CLEAN_FORK
            if repair_focus_required
            else None
        ),
        "branch_followup_policy": followup_policy,
        "weak_positive_followup": weak_positive_followup,
        "clean_fork_policy": clean_fork_policy,
        "branch_mechanism_ids": list(protected_mechanism_ids),
        "allowed_mechanism_ids": allowed_mechanism_ids,
        "protected_mechanism_ids": list(protected_mechanism_ids),
        "forbidden_mechanism_policy": (
            NO_UNRELATED_MECHANISM_IDS
            if strict_same_mechanism_followup
            else None
        ),
        "same_mechanism_allowed_actions": (
            list(SAME_MECHANISM_ALLOWED_ACTIONS)
            if strict_same_mechanism_followup
            else []
        ),
        "mechanism_change_policy": (
            "mechanism_changes_must_use_allowed_or_protected_ids"
            if strict_same_mechanism_followup
            else None
        ),
        "repair_mechanism_ids": list(
            getattr(branch, "telemetry_repair_mechanism_ids", ()) or ()
        )
        if branch is not None
        else [],
        "telemetry_repair_attempts": dict(
            getattr(branch, "telemetry_repair_attempts", {}) or {}
        )
        if branch is not None
        else {},
        "baseline_policy": baseline_policy,
    }
    if runtime_evidence_pressure_count is not None:
        context["runtime_evidence_pressure_count"] = runtime_evidence_pressure_count
        context["current_head_runtime_evidence_pressure_count"] = (
            runtime_evidence_pressure_count
        )
    if runtime_low_confidence_advisory:
        context["runtime_evidence_low_confidence_advisory"] = (
            runtime_low_confidence_advisory
        )
    context.update(branch_lifecycle_reroute_context(branch))
    diversity_guidance = _runtime_saturated_diversity_guidance(context)
    if diversity_guidance:
        context["diversity_reroute_guidance"] = diversity_guidance
    return context


def branch_hygiene_guidance(branch: Branch | None) -> str:
    """Human-readable branch hygiene guidance for prompts and diagnostics."""
    context = branch_hygiene_context(branch)
    card = branch_prompt_card(branch)
    status = context["branch_code_status"]
    outcome = context.get("last_telemetry_outcome") or "unknown"
    tier = context.get("last_screening_feedback_tier") or "unknown"
    if context["repair_focus_required"]:
        reroute_suffix = _branch_lifecycle_guidance_suffix(context)
        protected = _protected_mechanism_text(context)
        allowed_actions = _allowed_actions_text(context)
        return (
            f"{card}; "
            f"branch_code_status={status}; telemetry_outcome={outcome}; "
            f"screening_tier={tier}; "
            f"repair_focus={context['repair_focus_reason']}; "
            f"repair_policy={context['repair_policy']}; "
            f"hypothesis_generation_mode={context['hypothesis_generation_mode']}; "
            f"branch_followup_policy={context['branch_followup_policy']}; "
            f"clean_fork_policy={context['clean_fork_policy']}; "
            f"allowed_mechanism_ids={protected}; "
            f"protected_mechanism_ids={protected}; "
            f"forbidden_mechanism_policy={context['forbidden_mechanism_policy']}; "
            f"same_mechanism_allowed_actions={allowed_actions}; "
            "do not treat the existing branch workspace as a clean baseline. "
            "Continue only as a repair-focused attempt against champion code: "
            "fix declared telemetry activation/budget wiring or choose a new "
            f"branch instead of building on suspect code. Protected mechanism "
            f"ids for this branch: {protected}; do not add, drop, or rename "
            "them on this branch. Do not introduce unrelated mechanism_changes "
            "ids. Allowed actions here are only tune, integrate, repair, "
            "parameterize, or telemetry wiring within the protected mechanism. "
            "Those are branch research action labels, not mechanism_changes "
            "change_type values; map tune/parameterize to modify and "
            "telemetry_wiring to modify or integrate. "
            "If a different mechanism is needed, use a clean branch/fork "
            f"before drafting it.{reroute_suffix}"
        )
    if branch_is_parked_lineage(branch):
        return (
            f"{card}; "
            f"branch_code_status={status}; telemetry_outcome={outcome}; "
            f"screening_tier={tier}; baseline_policy="
            f"{context['baseline_policy']}; branch_followup_policy="
            f"{context['branch_followup_policy']}; clean_fork_policy="
            f"{context['clean_fork_policy']}; hypothesis_generation_mode="
            f"{context['hypothesis_generation_mode']}. "
            "This lineage is parked and must not consume an active branch "
            "slot or continue as open exploration. Start from a clean branch "
            "or clean fork for any next research direction."
        )
    if status.startswith("active_"):
        reroute_suffix = _branch_lifecycle_guidance_suffix(context)
        protected = _protected_mechanism_text(context)
        allowed_actions = _allowed_actions_text(context)
        if context.get("weak_positive_followup"):
            runtime_guidance = _runtime_evidence_low_confidence_advisory_sentence(
                context
            )
            return (
                f"{card}; "
                f"branch_code_status={status}; telemetry_outcome={outcome}; "
                f"screening_tier={tier}; baseline_policy="
                f"{context['baseline_policy']}; branch_followup_policy="
                f"{context['branch_followup_policy']}; clean_fork_policy="
                f"{context['clean_fork_policy']}; hypothesis_generation_mode="
                f"{context['hypothesis_generation_mode']}; "
                f"prior_mechanism_ids={protected}; "
                f"prior_touched_file_policy=prefer_branch_local_files. "
                "This is a weak-positive active branch. Default to a "
                "branch-local continuation that refines the prior mechanism, "
                "prior target/touched files, branch-created helpers, or the "
                "trigger, schedule, composition, budget allocation, or "
                "activation of the existing branch idea. If the next "
                "hypothesis changes target file, adds/renames a mechanism "
                "family, or moves work into a new module, it must explicitly "
                "bridge to the branch history: name which prior weak signal "
                "is preserved, which branch-local failure is being tested, "
                "and why the prior mechanism cannot be directly refined."
                f"{runtime_guidance}"
                f"{reroute_suffix}"
            )
        return (
            f"{card}; "
            f"branch_code_status={status}; telemetry_outcome={outcome}; "
            f"screening_tier={tier}; baseline_policy="
            f"{context['baseline_policy']}; branch_followup_policy="
            f"{context['branch_followup_policy']}; clean_fork_policy="
            f"{context['clean_fork_policy']}; hypothesis_generation_mode="
            f"{context['hypothesis_generation_mode']}; "
            f"allowed_mechanism_ids={protected}; "
            f"protected_mechanism_ids={protected}; "
            f"forbidden_mechanism_policy={context['forbidden_mechanism_policy']}; "
            f"same_mechanism_allowed_actions={allowed_actions}. "
            "This is an active branch outcome; "
            "reuse the branch workspace only for the same declared mechanism "
            f"ids: {protected}. The next hypothesis on this branch must keep "
            "those protected mechanism ids and may only tune, integrate, "
            "repair, parameterize, or wire telemetry for the same mechanism. "
            "These are branch research action labels, not mechanism_changes "
            "change_type values; map tune/parameterize to modify and "
            "telemetry_wiring to modify or integrate. "
            f"{_diversity_guidance_sentence(context)}"
            "Do not introduce unrelated mechanism_changes ids. A different "
            "or new mechanism requires a clean branch or clean fork before "
            "generation."
            f"{reroute_suffix}"
        )
    return ""


def _branch_lifecycle_guidance_suffix(context: Mapping[str, Any]) -> str:
    if not context.get("branch_lifecycle_new_mechanism_ineligible"):
        return ""
    return (
        " Prior branch-lifecycle policy blocks marked this branch ineligible "
        "for new-mechanism proposal selection; scheduler should use a clean "
        "branch/fork for new mechanisms, or continue here only under the same "
        "declared mechanism ids."
    )


def _runtime_saturated_diversity_guidance(
    context: Mapping[str, Any],
) -> dict[str, Any]:
    reason_text = " ".join(
        str(value or "")
        for value in (
            context.get("branch_code_status"),
            context.get("last_screening_feedback_tier"),
            context.get("last_telemetry_outcome"),
            context.get("branch_lifecycle_reroute_reason"),
            (
                (context.get("last_branch_lifecycle_policy_block") or {}).get(
                    "reason"
                )
                if isinstance(
                    context.get("last_branch_lifecycle_policy_block"),
                    Mapping,
                )
                else ""
            ),
            (
                (context.get("last_branch_lifecycle_policy_block") or {}).get(
                    "detail"
                )
                if isinstance(
                    context.get("last_branch_lifecycle_policy_block"),
                    Mapping,
                )
                else ""
            ),
        )
    ).lower()
    if not any(
        token in reason_text
        for token in (
            "runtime_saturation",
            "runtime saturation",
            "runtime_budget",
            "no_effect",
            "no effect",
            "zero_effect",
            "zero effect",
        )
    ):
        return {}
    return {
        "policy": RUNTIME_SATURATED_DIVERSITY_REROUTE_GUIDANCE,
        "guidance": (
            "Recent branch feedback is low-effect or runtime-saturated. Avoid "
            "continuing with another homogeneous high-cost variant on the same "
            "branch. Prefer a clean branch/fork or a materially different "
            "research direction that changes the mechanism family, trigger "
            "condition, budget allocation, or evaluation observability."
        ),
        "allowed_same_branch_followup": (
            "Only continue this branch when the follow-up reduces/redirects "
            "work or improves observability for the protected mechanism."
        ),
    }


def _diversity_guidance_sentence(context: Mapping[str, Any]) -> str:
    guidance = context.get("diversity_reroute_guidance")
    if not isinstance(guidance, Mapping) or not guidance:
        return ""
    return (
        "Runtime/no-effect lifecycle feedback is active: avoid another "
        "homogeneous high-cost variant here; prefer changing mechanism family, "
        "trigger condition, budget allocation, or evaluation observability, "
        "or use a clean branch/fork for a new direction. "
    )


def _runtime_evidence_low_confidence_advisory_sentence(
    context: Mapping[str, Any],
) -> str:
    guidance = (
        context.get("runtime_evidence_low_confidence_advisory")
        or context.get("runtime_evidence_clean_fork_guidance")
    )
    if not isinstance(guidance, Mapping) or not guidance:
        return ""
    reason = guidance.get("reason") or "runtime_evidence_completeness_clean_fork"
    return (
        " Low-confidence runtime evidence advisory is active: do not treat "
        "runtime saturation/pressure as a strong conclusion or branch-routing "
        "constraint. Need fresh champion runtime before runtime-based "
        "conclusions; same-branch follow-up may focus on improving runtime "
        "evidence completeness. This is tainted proposal guidance excluded "
        f"from DecisionFeatures; reason={reason}."
    )


def _runtime_evidence_prompt_advisory_projection(
    guidance: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(guidance, Mapping) or not guidance:
        return {}
    projected = dict(guidance)
    projected["policy"] = "fresh_runtime_advisory"
    projected["runtime_signal_role"] = "low_confidence_advisory"
    projected["strong_branch_constraint"] = False
    projected["proposal_guidance"] = (
        "Need fresh champion runtime before runtime-based conclusions; do not "
        "treat runtime saturation/pressure as a strong diagnostic when "
        "runtime aggregate evidence is excluded or low confidence."
    )
    projected["tainted_proposal_guidance"] = True
    projected["decision_features_excluded"] = True
    return projected


def _protected_mechanism_text(context: Mapping[str, Any]) -> str:
    ids = [
        str(item).strip()
        for item in (context.get("protected_mechanism_ids") or ())
        if str(item).strip()
    ]
    return ", ".join(ids) if ids else "unknown"


def _allowed_actions_text(context: Mapping[str, Any]) -> str:
    actions = [
        str(item).strip()
        for item in (context.get("same_mechanism_allowed_actions") or ())
        if str(item).strip()
    ]
    return ",".join(actions) if actions else "none"


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


def _branch_card_allowed_actions(
    branch: Branch | None,
    *,
    lineage_status: str,
    strict_same_mechanism_followup: bool,
    repair_focus_required: bool,
) -> list[str]:
    if branch_is_parked_lineage(branch):
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
    if strict_same_mechanism_followup:
        forbidden.append("unrelated_mechanism")
    if lineage_status == "active_no_effect" and not branch_has_actionable_diagnostic(
        branch
    ):
        forbidden.append("unchanged_repeat")
    if latest_head_failed and has_checkpoint:
        forbidden.append("treat_failed_head_as_lineage_failure")
    return list(dict.fromkeys(forbidden))


__all__ = [
    "branch_hygiene_context",
    "branch_hygiene_guidance",
    "branch_prompt_card",
]
