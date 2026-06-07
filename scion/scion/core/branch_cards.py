"""Branch card and prompt-context rendering helpers."""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from scion.core.branch_cards_evidence import (
    _best_checkpoint_mapping,
    _best_checkpoint_reason_codes,
    _best_checkpoint_scalar,
    _branch_block,
    _branch_block_codes,
    _branch_card_allowed_actions,
    _branch_card_forbidden_actions,
    _branch_case_outcomes,
    _branch_evidence_codes,
    _branch_evidence_summary,
    _branch_generic_evidence_summary,
    _branch_lifecycle_block,
    _branch_lifecycle_block_codes,
    _branch_phase_activation_summary,
    _branch_rollback_codes,
    _branch_runtime_evidence_confidence,
    _branch_runtime_evidence_pressure_count,
    _branch_state_value,
    _current_gate_observation_codes,
    _current_reason_codes,
    _history_mapping_list,
    _history_reason_codes,
    _is_current_gate_observation_code,
    _is_lifecycle_action_code,
    _is_proposal_block_code,
    _lifecycle_action_reason_codes,
    _mapping_codes,
    _metric_value,
    _optional_float,
    _optional_int,
    _proposal_block_codes,
    _tier_from_status,
    _why_abandoned_codes,
    _why_not_promoted_codes,
)
from scion.core.branch_cards_rendering import (
    _card_list,
    _card_mapping,
    _card_mapping_list,
    _compact_card_value,
    _format_case_outcomes,
    _format_evidence_summary,
    _format_phase_activation_history,
    _format_phase_activation_summary,
    branch_prompt_card_from_context as _render_branch_prompt_card_from_context,
)
from scion.core.branch_cards_runtime import (
    _diversity_guidance_sentence,
    _runtime_evidence_low_confidence_advisory_sentence,
    _runtime_evidence_prompt_advisory_projection,
    _runtime_saturated_diversity_guidance,
)
from scion.core.branch_hygiene import (
    BRANCH_LOCAL_FOLLOWUP_MODE,
    BRANCH_LOCAL_FOLLOWUP_OR_EXPLICIT_BRIDGE,
    CLEAN_FORK_REQUIRED_FOR_NEW_MECHANISM,
    NO_UNRELATED_MECHANISM_IDS,
    OPEN_EXPLORATION_ALLOWED,
    OPEN_EXPLORATION_MODE,
    REPAIR_FIRST_SAME_MECHANISM_OR_CLEAN_FORK,
    SAME_MECHANISM_ALLOWED_ACTIONS,
    SAME_MECHANISM_FOLLOWUP_ONLY,
    SAME_MECHANISM_ONLY_MODE,
    WIRING_SUSPECT_REQUIRES_REPAIR,
    branch_checkpoint_status,
    branch_code_status,
    branch_has_retained_checkpoint,
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
    return _render_branch_prompt_card_from_context(context)


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


__all__ = [
    "branch_hygiene_context",
    "branch_hygiene_guidance",
    "branch_prompt_card",
]
