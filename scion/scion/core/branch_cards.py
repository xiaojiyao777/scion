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
    branch_is_parked_lineage,
    branch_lifecycle_reroute_context,
    branch_lineage_status,
    branch_mechanism_ids,
    branch_requires_repair_focus,
    branch_requires_same_mechanism_followup,
)
from scion.core.models import Branch


def branch_prompt_card(branch: Branch | None) -> str:
    """Compact generic branch card for APS prompts and sibling summaries."""
    context = branch_hygiene_context(branch)
    allowed = ",".join(context["allowed_next_actions"]) or "none"
    forbidden = ",".join(context["forbidden_next_actions"]) or "none"
    mechanism_ids = ",".join(context["mechanism_ids"]) or "none"
    evidence = _format_evidence_summary(context["generic_evidence_summary"])
    why_not_promoted = (
        ",".join(context["why_not_promoted_reason_codes"]) or "none"
    )
    why_abandoned = ",".join(context["why_abandoned_reason_codes"]) or "none"
    return (
        f"branch_id={context['branch_id']} "
        f"status={context['status']} "
        f"direction={_compact_card_value(context['direction'])} "
        f"mechanism_ids={mechanism_ids} "
        f"lineage_status={context['lineage_status']} "
        f"current_head_status={context['current_head_status']} "
        f"best_checkpoint_status={context['best_checkpoint_status']} "
        f"best_quality_checkpoint_id={context['best_quality_checkpoint_id'] or 'none'} "
        f"last_valid_checkpoint_id={context['last_valid_checkpoint_id'] or 'none'} "
        f"rollback_count={context['rollback_count']} "
        f"allowed_next_actions={allowed} "
        f"forbidden_next_actions={forbidden} "
        f"latest_head_failed={str(context['latest_head_failed']).lower()} "
        "lineage_retained_checkpoint="
        f"{str(context['lineage_retained_checkpoint']).lower()} "
        f"generic_evidence_summary={evidence} "
        f"why_not_promoted_reason_codes={why_not_promoted} "
        f"why_abandoned_reason_codes={why_abandoned}"
    )


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
    strict_same_mechanism_followup = (
        same_mechanism_followup_required and not weak_positive_followup
    )
    followup_policy = (
        BRANCH_LOCAL_FOLLOWUP_OR_EXPLICIT_BRIDGE
        if weak_positive_followup
        else
        SAME_MECHANISM_FOLLOWUP_ONLY
        if same_mechanism_followup_required
        else OPEN_EXPLORATION_ALLOWED
    )
    generation_mode = (
        BRANCH_LOCAL_FOLLOWUP_MODE
        if weak_positive_followup
        else
        SAME_MECHANISM_ONLY_MODE
        if strict_same_mechanism_followup
        else OPEN_EXPLORATION_MODE
    )
    clean_fork_policy = (
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
        "status": _branch_state_value(branch),
        "branch_code_status": status,
        "lineage_status": lineage_status,
        "current_head_status": current_head_status,
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
        "gate_observation_reason_codes": _branch_block_codes(
            branch,
            "gate_observation_reason_codes",
            "reason_codes",
        ),
        "lifecycle_action_reason_codes": _branch_block_codes(
            branch,
            "lifecycle_action_reason_codes",
            "decision_reason_codes",
            "reason_codes",
        ),
        "rollback_reason_codes": _branch_rollback_codes(branch),
        "why_not_promoted_reason_codes": _why_not_promoted_codes(branch),
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
            "If a different mechanism is needed, use a clean branch/fork "
            f"before drafting it.{reroute_suffix}"
        )
    if status.startswith("active_"):
        reroute_suffix = _branch_lifecycle_guidance_suffix(context)
        protected = _protected_mechanism_text(context)
        allowed_actions = _allowed_actions_text(context)
        if context.get("weak_positive_followup"):
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


def _branch_block_codes(branch: Branch | None, *keys: str) -> list[str]:
    block = _branch_block(branch)
    codes: list[str] = []
    for key in keys:
        value = block.get(key)
        if isinstance(value, str):
            codes.extend([value] if value else [])
        elif isinstance(value, Iterable):
            codes.extend(str(item) for item in value if str(item))
    return list(dict.fromkeys(codes))


def _branch_rollback_codes(branch: Branch | None) -> list[str]:
    codes = _branch_block_codes(branch, "rollback_reason_codes")
    reason = (
        str(getattr(branch, "last_rollback_reason", "") or "")
        if branch is not None
        else ""
    )
    if reason:
        codes.append(reason)
    return list(dict.fromkeys(codes))


def _why_not_promoted_codes(branch: Branch | None) -> list[str]:
    if branch is None:
        return []
    codes = list(getattr(branch, "failure_codes", None) or ())
    codes.extend(
        _branch_block_codes(
            branch,
            "why_not_promoted_reason_codes",
            "lifecycle_action_reason_codes",
            "decision_reason_codes",
            "reason_codes",
        )
    )
    return list(dict.fromkeys(str(code) for code in codes if str(code)))


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
    block = _branch_block(branch)
    status = branch_code_status(branch)
    tier = str(current_tier or "").strip() or _tier_from_status(status)
    summary: dict[str, Any] = {"tier": tier or "unknown"}
    metric_keys = {
        "wins": ("wins", "case_wins", "pair_wins", "screening_case_wins"),
        "losses": ("losses", "case_losses", "pair_losses", "screening_case_losses"),
        "ties": ("ties", "case_ties", "pair_ties", "screening_case_ties"),
    }
    for name, keys in metric_keys.items():
        value = _metric_value(block, keys, int)
        if value is not None:
            summary[name] = value
    for group, keys in {
        "effect": ("median_delta", "ci_low", "ci_high"),
        "runtime": ("runtime_ratio_median", "runtime_regression_rate"),
    }.items():
        values = {key: _metric_value(block, (key,), float) for key in keys}
        values = {key: value for key, value in values.items() if value is not None}
        if values:
            summary[group] = values
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
    return ",".join(parts)


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
