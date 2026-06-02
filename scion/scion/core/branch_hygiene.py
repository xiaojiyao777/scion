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
    if branch is None:
        return False
    state = getattr(branch, "state", None)
    if str(getattr(state, "value", state) or "") == "parked_lineage":
        return True
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
    from scion.core.branch_cards import branch_prompt_card as _branch_prompt_card

    return _branch_prompt_card(branch)


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
        "diagnostic_kind": "branch_routing_diagnostic",
        "reason": reason,
        "detail": _bounded_detail(detail),
        "recorded_at": now.isoformat(),
        "block_count": block_count,
        "failure_accounting": "not_run_validity_failure",
        "reroute_reason": BRANCH_LIFECYCLE_REROUTE_AFTER_POLICY_BLOCK,
        "next_selection": (
            "clean_branch_or_clean_fork_unless_same_mechanism_followup_forced"
        ),
    }
    if "new_mechanism_requires_clean_fork" in str(detail or "").lower():
        block["candidate_routing"] = "new_mechanism_requires_clean_fork_signal"
        block["clean_fork_signal"] = True
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
    from scion.core.branch_cards import branch_hygiene_context as _branch_context

    return _branch_context(branch)


def branch_hygiene_guidance(branch: Branch | None) -> str:
    from scion.core.branch_cards import branch_hygiene_guidance as _branch_guidance

    return _branch_guidance(branch)


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
