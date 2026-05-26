"""Branch-code hygiene helpers for proposal and workspace selection."""

from __future__ import annotations

from typing import Any, Mapping, MutableMapping

from scion.core.models import Branch


TELEMETRY_WIRING_SUSPECT = "telemetry_wiring_suspect"
TELEMETRY_INVALID = "telemetry_invalid"
ACTIVATION_MISSING_OR_WIRING_SUSPECT = "activation_missing_or_wiring_suspect"
WIRING_SUSPECT_REQUIRES_REPAIR = "wiring_suspect_requires_repair"
REPAIR_FIRST_SAME_MECHANISM_OR_CLEAN_FORK = (
    "repair_first_same_mechanism_or_clean_fork"
)

SUSPECT_BRANCH_CODE_STATUSES = frozenset(
    {
        TELEMETRY_WIRING_SUSPECT,
        TELEMETRY_INVALID,
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
    if repair_focus_required:
        baseline_policy = "champion_required_for_repair"
        repair_focus_reason = WIRING_SUSPECT_REQUIRES_REPAIR
    elif status.startswith("active_"):
        baseline_policy = "branch_workspace_allowed_with_marker"
        repair_focus_reason = None
    else:
        baseline_policy = "clean"
        repair_focus_reason = None
    return {
        "branch_code_status": status,
        "last_screening_feedback_tier": last_screening_feedback_tier,
        "last_telemetry_outcome": last_telemetry_outcome,
        "repair_focus_required": repair_focus_required,
        "repair_focus_reason": repair_focus_reason,
        "repair_policy": (
            REPAIR_FIRST_SAME_MECHANISM_OR_CLEAN_FORK
            if repair_focus_required
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


def branch_hygiene_guidance(branch: Branch | None) -> str:
    """Human-readable branch hygiene guidance for prompts and diagnostics."""
    context = branch_hygiene_context(branch)
    status = context["branch_code_status"]
    outcome = context.get("last_telemetry_outcome") or "unknown"
    tier = context.get("last_screening_feedback_tier") or "unknown"
    if context["repair_focus_required"]:
        return (
            f"branch_code_status={status}; telemetry_outcome={outcome}; "
            f"screening_tier={tier}; "
            f"repair_focus={context['repair_focus_reason']}; "
            f"repair_policy={context['repair_policy']}; "
            "do not treat the existing branch workspace as a clean baseline. "
            "Continue only as a repair-focused attempt against champion code: "
            "fix declared telemetry activation/budget wiring or choose a new "
            "branch instead of building on suspect code."
        )
    if status.startswith("active_"):
        return (
            f"branch_code_status={status}; telemetry_outcome={outcome}; "
            f"screening_tier={tier}; baseline_policy="
            f"{context['baseline_policy']}. This is an active branch outcome, "
            "not telemetry wiring failure; branch workspace may be reused with "
            "the marker visible."
        )
    return ""


__all__ = [
    "ACTIVATION_MISSING_OR_WIRING_SUSPECT",
    "REPAIR_FIRST_SAME_MECHANISM_OR_CLEAN_FORK",
    "SUSPECT_BRANCH_CODE_STATUSES",
    "TELEMETRY_INVALID",
    "TELEMETRY_WIRING_SUSPECT",
    "WIRING_SUSPECT_REQUIRES_REPAIR",
    "branch_allows_clean_workspace_reuse",
    "branch_code_status",
    "branch_hygiene_context",
    "branch_hygiene_guidance",
    "branch_requires_repair_focus",
    "branch_workspace_for_proposal",
]
