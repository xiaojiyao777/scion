"""Branch-code hygiene helpers for proposal and workspace selection."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable, Mapping, MutableMapping

from scion.core.models import Branch


TELEMETRY_WIRING_SUSPECT = "telemetry_wiring_suspect"
TELEMETRY_INVALID = "telemetry_invalid"
ACTIVATION_MISSING_OR_WIRING_SUSPECT = "activation_missing_or_wiring_suspect"
WIRING_SUSPECT_REQUIRES_REPAIR = "wiring_suspect_requires_repair"
REPAIR_FIRST_SAME_MECHANISM_OR_CLEAN_FORK = (
    "repair_first_same_mechanism_or_clean_fork"
)
SAME_MECHANISM_FOLLOWUP_ONLY = "same_mechanism_followup_only"
BRANCH_LOCAL_FOLLOWUP_OR_EXPLICIT_BRIDGE = (
    "branch_local_followup_or_explicit_bridge"
)
SAME_MECHANISM_ONLY_MODE = "same_mechanism_only"
BRANCH_LOCAL_FOLLOWUP_MODE = "branch_local_followup"
OPEN_EXPLORATION_MODE = "open_exploration"
CLEAN_FORK_REQUIRED_FOR_NEW_MECHANISM = (
    "clean_fork_required_for_new_mechanism"
)
OPEN_EXPLORATION_ALLOWED = "open_exploration_allowed"
NO_UNRELATED_MECHANISM_IDS = "no_unrelated_mechanism_ids"
SAME_MECHANISM_ALLOWED_ACTIONS = (
    "tune",
    "integrate",
    "repair",
    "parameterize",
    "telemetry_wiring",
)
BRANCH_LIFECYCLE_REROUTE_AFTER_POLICY_BLOCK = (
    "clean_fork_after_branch_lifecycle_policy_block"
)
BRANCH_LIFECYCLE_NEW_MECHANISM_INELIGIBLE = (
    "new_mechanism_ineligible_after_branch_lifecycle_policy_block"
)
BRANCH_LIFECYCLE_REROUTE_LOOP_LIMIT = 1
RUNTIME_SATURATED_DIVERSITY_REROUTE_GUIDANCE = (
    "runtime_saturated_diversity_reroute"
)
PARKED_BRANCH_CODE_STATUSES = frozenset(
    {
        "parked",
        "parked_lineage",
        "lineage_parked",
    }
)

SUSPECT_BRANCH_CODE_STATUSES = frozenset(
    {
        TELEMETRY_WIRING_SUSPECT,
        TELEMETRY_INVALID,
    }
)
FOLLOWUP_ONLY_BRANCH_CODE_STATUSES = frozenset(
    {
        *SUSPECT_BRANCH_CODE_STATUSES,
        "active_no_effect",
        "active_runtime_regression",
    }
)


def branch_code_status(branch: Branch | None) -> str:
    if branch is None:
        return "unknown"
    return str(getattr(branch, "branch_code_status", "clean") or "clean")


def branch_requires_repair_focus(branch: Branch | None) -> bool:
    if branch is None:
        return False
    telemetry_outcome = str(
        getattr(branch, "last_telemetry_outcome", "") or ""
    )
    return (
        branch_code_status(branch) in SUSPECT_BRANCH_CODE_STATUSES
        or telemetry_outcome == ACTIVATION_MISSING_OR_WIRING_SUSPECT
    )


def branch_requires_same_mechanism_followup(branch: Branch | None) -> bool:
    if branch is None:
        return False
    status = branch_code_status(branch)
    return (
        status in FOLLOWUP_ONLY_BRANCH_CODE_STATUSES
        or status.startswith("active_")
        or branch_requires_repair_focus(branch)
    )


def branch_mechanism_ids(branch: Branch | None) -> tuple[str, ...]:
    if branch is None:
        return ()
    ids = [
        str(item).strip()
        for item in (getattr(branch, "branch_mechanism_ids", ()) or ())
        if str(item).strip()
    ]
    if not ids:
        ids = [
            str(item).strip()
            for item in (
                getattr(branch, "telemetry_repair_mechanism_ids", ()) or ()
            )
            if str(item).strip()
        ]
    return tuple(dict.fromkeys(ids))


def branch_allows_clean_workspace_reuse(branch: Branch | None) -> bool:
    return not branch_requires_repair_focus(branch)


def branch_workspace_for_proposal(
    branch: Branch | None,
    branch_workspaces: Mapping[str, str] | MutableMapping[str, str],
) -> str | None:
    """Return the proposal-visible branch workspace, if it is safe to reuse."""
    if branch is None or branch_requires_repair_focus(branch):
        return None
    return branch_workspaces.get(branch.branch_id)


def branch_lifecycle_new_mechanism_ineligible(branch: Branch | None) -> bool:
    if branch is None:
        return False
    return bool(
        getattr(branch, "branch_lifecycle_new_mechanism_ineligible", False)
    )


def branch_is_parked_lineage(branch: Branch | None) -> bool:
    return branch_code_status(branch) in PARKED_BRANCH_CODE_STATUSES


def branch_has_retained_checkpoint(branch: Branch | None) -> bool:
    if branch is None:
        return False
    return bool(
        getattr(branch, "best_quality_checkpoint_id", None)
        or getattr(branch, "last_valid_checkpoint_id", None)
    )


def branch_has_actionable_diagnostic(branch: Branch | None) -> bool:
    if branch is None:
        return False
    if branch_requires_repair_focus(branch):
        return True
    status = branch_code_status(branch)
    if status in {
        "active_runtime_regression",
        "telemetry_wiring_suspect",
        "telemetry_invalid",
    }:
        return True
    if getattr(branch, "pending_retry", False):
        return True
    if getattr(branch, "failure_codes", None):
        return True
    if getattr(branch, "branch_lifecycle_policy_blocks", 0):
        return True
    return False


def branch_lineage_status(branch: Branch | None) -> str:
    status = branch_code_status(branch)
    tier = (
        str(getattr(branch, "last_screening_feedback_tier", "") or "")
        if branch is not None
        else ""
    )
    rollback_count = (
        max(0, int(getattr(branch, "rollback_count", 0) or 0))
        if branch is not None
        else 0
    )
    has_checkpoint = branch_has_retained_checkpoint(branch)
    if branch_is_parked_lineage(branch):
        return "parked"
    if rollback_count > 0 and has_checkpoint:
        if tier == "weak_positive" or status == "active_weak_positive":
            return "restored_weak_positive"
        return "restored_checkpoint"
    if status in {
        "discarded",
        "regressed_followup",
        "quality_regression",
        "active_quality_regression",
    }:
        return "diagnostic_repair"
    if status == "active_weak_positive" or tier == "weak_positive":
        return "active_weak_positive"
    if status == "active_marginal" or tier == "marginal":
        return "active_marginal"
    if status == "active_no_effect" or tier == "no_effect":
        return "active_no_effect"
    if branch_requires_repair_focus(branch):
        return "diagnostic_repair"
    if has_checkpoint:
        return "checkpoint_retained"
    return "open"


def branch_checkpoint_status(branch: Branch | None) -> str:
    if branch is None:
        return "none"
    if getattr(branch, "best_quality_checkpoint_id", None):
        return "best_quality_retained"
    if getattr(branch, "last_valid_checkpoint_id", None):
        return "last_valid_retained"
    return "none"


def branch_prompt_card(branch: Branch | None) -> str:
    """Compact generic branch card for APS prompts and sibling summaries."""
    context = branch_hygiene_context(branch)
    allowed = ",".join(context["allowed_next_actions"]) or "none"
    forbidden = ",".join(context["forbidden_next_actions"]) or "none"
    return (
        f"lineage_status={context['lineage_status']} "
        f"current_head_status={context['current_head_status']} "
        f"best_checkpoint_status={context['best_checkpoint_status']} "
        f"rollback_count={context['rollback_count']} "
        f"allowed_next_actions={allowed} "
        f"forbidden_next_actions={forbidden} "
        f"latest_head_failed={str(context['latest_head_failed']).lower()} "
        "lineage_retained_checkpoint="
        f"{str(context['lineage_retained_checkpoint']).lower()}"
    )


def record_branch_lifecycle_policy_block(
    branch: Branch | None,
    detail: str | None,
) -> dict[str, Any]:
    """Record a generic branch-lifecycle reroute marker on the branch."""
    if branch is None:
        return {}
    now = datetime.now()
    block_count = max(
        0,
        int(getattr(branch, "branch_lifecycle_policy_blocks", 0) or 0),
    ) + 1
    reason = _branch_lifecycle_reason(detail)
    block = {
        "reason": reason,
        "detail": _bounded_detail(detail),
        "recorded_at": now.isoformat(),
        "block_count": block_count,
        "reroute_reason": BRANCH_LIFECYCLE_REROUTE_AFTER_POLICY_BLOCK,
        "next_selection": (
            "clean_branch_or_clean_fork_unless_same_mechanism_followup_forced"
        ),
    }
    branch.branch_lifecycle_policy_blocks = block_count
    branch.branch_lifecycle_new_mechanism_ineligible = True
    branch.branch_lifecycle_reroute_reason = (
        BRANCH_LIFECYCLE_REROUTE_AFTER_POLICY_BLOCK
    )
    branch.last_branch_lifecycle_policy_block = block
    branch.updated_at = now
    return block


def branch_lifecycle_reroute_context(branch: Branch | None) -> dict[str, Any]:
    block_count = (
        max(
            0,
            int(getattr(branch, "branch_lifecycle_policy_blocks", 0) or 0),
        )
        if branch is not None
        else 0
    )
    ineligible = branch_lifecycle_new_mechanism_ineligible(branch)
    last_block = (
        dict(getattr(branch, "last_branch_lifecycle_policy_block", {}) or {})
        if branch is not None
        and isinstance(
            getattr(branch, "last_branch_lifecycle_policy_block", None),
            Mapping,
        )
        else {}
    )
    reroute_reason = (
        str(getattr(branch, "branch_lifecycle_reroute_reason", "") or "")
        if branch is not None
        else ""
    )
    return {
        "branch_lifecycle_policy_blocks": block_count,
        "branch_lifecycle_new_mechanism_ineligible": ineligible,
        "branch_lifecycle_reroute_reason": reroute_reason or None,
        "branch_lifecycle_reroute_loop_limit": (
            BRANCH_LIFECYCLE_REROUTE_LOOP_LIMIT
        ),
        "last_branch_lifecycle_policy_block": last_block,
        "next_branch_selection_policy": (
            "clean_branch_or_clean_fork_for_new_mechanism"
            if ineligible
            else "normal_scheduler_policy"
        ),
    }


def campaign_branch_lifecycle_reroute_status(
    branches: Iterable[Branch],
) -> dict[str, Any]:
    ineligible_branches: list[dict[str, Any]] = []
    last_blocks: list[dict[str, Any]] = []
    for branch in branches:
        context = branch_lifecycle_reroute_context(branch)
        if context["branch_lifecycle_new_mechanism_ineligible"]:
            ineligible_branches.append(
                {
                    "branch_id": branch.branch_id,
                    "branch_code_status": branch_code_status(branch),
                    "reason": context["branch_lifecycle_reroute_reason"],
                    "policy_blocks": context["branch_lifecycle_policy_blocks"],
                    "next_branch_selection_policy": context[
                        "next_branch_selection_policy"
                    ],
                }
            )
        block = context.get("last_branch_lifecycle_policy_block")
        if isinstance(block, Mapping) and block:
            last_blocks.append({"branch_id": branch.branch_id, **dict(block)})
    if not ineligible_branches and not last_blocks:
        return {}
    last_blocks.sort(key=lambda item: str(item.get("recorded_at") or ""))
    return {
        "policy": BRANCH_LIFECYCLE_REROUTE_AFTER_POLICY_BLOCK,
        "reroute_loop_limit": BRANCH_LIFECYCLE_REROUTE_LOOP_LIMIT,
        "ineligible_branch_ids": [
            item["branch_id"] for item in ineligible_branches
        ],
        "ineligible_branches": ineligible_branches,
        "last_policy_block": last_blocks[-1] if last_blocks else None,
        "next_branch_selection_policy": (
            "skip_new_mechanism_ineligible_research_branches_and_use_clean_fork"
        ),
    }


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
        "branch_code_status": status,
        "lineage_status": lineage_status,
        "current_head_status": current_head_status,
        "best_checkpoint_status": best_checkpoint_status,
        "rollback_count": rollback_count,
        "allowed_next_actions": allowed_next_actions,
        "forbidden_next_actions": forbidden_next_actions,
        "latest_head_failed": latest_head_failed,
        "lineage_retained_checkpoint": lineage_retained_checkpoint,
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


def _branch_lifecycle_reason(detail: str | None) -> str:
    text = str(detail or "").strip()
    if not text:
        return "branch_lifecycle_policy_block"
    if ":" in text:
        text = text.split(":", 1)[1].strip()
    if ";" in text:
        text = text.split(";", 1)[0].strip()
    return text or "branch_lifecycle_policy_block"


def _bounded_detail(detail: str | None) -> str:
    text = str(detail or "").strip()
    if len(text) <= 1600:
        return text
    return text[:1597].rstrip() + "..."


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
    "ACTIVATION_MISSING_OR_WIRING_SUSPECT",
    "BRANCH_LIFECYCLE_NEW_MECHANISM_INELIGIBLE",
    "BRANCH_LIFECYCLE_REROUTE_AFTER_POLICY_BLOCK",
    "BRANCH_LIFECYCLE_REROUTE_LOOP_LIMIT",
    "BRANCH_LOCAL_FOLLOWUP_OR_EXPLICIT_BRIDGE",
    "BRANCH_LOCAL_FOLLOWUP_MODE",
    "CLEAN_FORK_REQUIRED_FOR_NEW_MECHANISM",
    "FOLLOWUP_ONLY_BRANCH_CODE_STATUSES",
    "OPEN_EXPLORATION_ALLOWED",
    "PARKED_BRANCH_CODE_STATUSES",
    "REPAIR_FIRST_SAME_MECHANISM_OR_CLEAN_FORK",
    "NO_UNRELATED_MECHANISM_IDS",
    "OPEN_EXPLORATION_MODE",
    "SAME_MECHANISM_ALLOWED_ACTIONS",
    "SAME_MECHANISM_FOLLOWUP_ONLY",
    "SAME_MECHANISM_ONLY_MODE",
    "SUSPECT_BRANCH_CODE_STATUSES",
    "RUNTIME_SATURATED_DIVERSITY_REROUTE_GUIDANCE",
    "TELEMETRY_INVALID",
    "TELEMETRY_WIRING_SUSPECT",
    "WIRING_SUSPECT_REQUIRES_REPAIR",
    "branch_allows_clean_workspace_reuse",
    "branch_checkpoint_status",
    "branch_code_status",
    "branch_has_actionable_diagnostic",
    "branch_has_retained_checkpoint",
    "branch_lifecycle_new_mechanism_ineligible",
    "branch_lifecycle_reroute_context",
    "branch_hygiene_context",
    "branch_hygiene_guidance",
    "branch_is_parked_lineage",
    "branch_lineage_status",
    "branch_mechanism_ids",
    "branch_prompt_card",
    "branch_requires_repair_focus",
    "branch_requires_same_mechanism_followup",
    "branch_workspace_for_proposal",
    "campaign_branch_lifecycle_reroute_status",
    "record_branch_lifecycle_policy_block",
]
