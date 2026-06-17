"""Branch-code hygiene helpers for proposal and workspace selection."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable, Mapping, MutableMapping

from scion.core.models import Branch
from scion.core.replay_identity_contract import formal_replay_identity_missing_keys


TELEMETRY_WIRING_SUSPECT = "telemetry_wiring_suspect"
TELEMETRY_INVALID = "telemetry_invalid"
ACTIVATION_MISSING_OR_WIRING_SUSPECT = "activation_missing_or_wiring_suspect"
TELEMETRY_EFFECT_ZERO_OUTCOME = "telemetry_effect_zero"
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
    "diagnostic",
    "observability",
    "refine",
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
BRANCH_FINAL_CLASSIFICATION_SCHEMA = "scion.branch_final_classification.v1"
FRESH_RUNTIME_REPLAY_BLOCKED_MISSING_IDENTITY = (
    "fresh_runtime_replay_blocked_missing_identity"
)
PARKED_BRANCH_CODE_STATUSES = frozenset(
    {
        "parked",
        "parked_lineage",
        "lineage_parked",
    }
)
HARD_TELEMETRY_REPAIR_REASON_CODES = frozenset(
    {
        "SCREENING_TELEMETRY_REPAIRABLE",
        "TELEMETRY_VALIDATION_REPAIRABLE",
        "VALIDATION_TELEMETRY_REPAIRABLE",
    }
)
NONBLOCKING_TELEMETRY_EFFECT_ZERO_REASON_CODES = frozenset(
    {
        "TELEMETRY_EFFECT_ZERO_DIAGNOSTIC",
        "SCREENING_TELEMETRY_EFFECT_ZERO_DIAGNOSTIC",
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


def hard_telemetry_repair_reason_present(reason_codes: Iterable[str] | None) -> bool:
    return bool(
        set(_clean_reason_codes(reason_codes)) & HARD_TELEMETRY_REPAIR_REASON_CODES
    )


def telemetry_effect_zero_reason_present(reason_codes: Iterable[str] | None) -> bool:
    return bool(
        set(_clean_reason_codes(reason_codes))
        & NONBLOCKING_TELEMETRY_EFFECT_ZERO_REASON_CODES
    )


def nonblocking_telemetry_effect_zero_reason_code(code: str) -> bool:
    return str(code).strip().upper() in NONBLOCKING_TELEMETRY_EFFECT_ZERO_REASON_CODES


def _clean_reason_codes(reason_codes: Iterable[str] | None) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            str(code).strip().upper()
            for code in (reason_codes or ())
            if str(code).strip()
        )
    )


def _branch_has_actionable_failure_codes(branch: Branch) -> bool:
    codes = _clean_reason_codes(getattr(branch, "failure_codes", None))
    if not codes:
        return False
    return any(not nonblocking_telemetry_effect_zero_reason_code(code) for code in codes)


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


def is_branch_lifecycle_policy_block(block: Mapping[str, Any] | None) -> bool:
    """Return true only for blocks created by lifecycle/reroute policy paths."""
    if not isinstance(block, Mapping) or not block:
        return False
    reroute_reason = str(block.get("reroute_reason") or "")
    if reroute_reason == BRANCH_LIFECYCLE_REROUTE_AFTER_POLICY_BLOCK:
        return True
    if block.get("diagnostic_kind") == "branch_routing_diagnostic":
        return True
    if (
        block.get("new_mechanism_ineligible_reason")
        == BRANCH_LIFECYCLE_NEW_MECHANISM_INELIGIBLE
    ):
        return True
    if isinstance(block.get("active_slot_reconciliation"), Mapping):
        return True
    if block.get("clean_fork_signal") is True:
        return True
    for key in (
        "lifecycle_action_reason_codes",
        "decision_reason_codes",
        "reason_codes",
    ):
        value = block.get(key)
        if isinstance(value, str):
            codes = (value,)
        elif isinstance(value, Iterable) and not isinstance(value, Mapping):
            codes = value
        else:
            codes = ()
        if any(str(code).startswith("BRANCH_LIFECYCLE_") for code in codes):
            return True
    return False


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
    if _branch_has_actionable_failure_codes(branch):
        return True
    if getattr(branch, "branch_lifecycle_policy_blocks", 0):
        return True
    return False


def branch_fresh_runtime_replay_blocked(branch: Branch | None) -> bool:
    return bool(_fresh_runtime_replay_blocked_diagnostic(branch))


def branch_lifecycle_closure_classification(
    branch: Branch | None,
) -> dict[str, Any]:
    """Return deterministic branch lifecycle/status classification for reports."""
    state = _branch_state_value(branch)
    blocked = _fresh_runtime_replay_blocked_diagnostic(branch)
    if branch is None:
        classification = "unknown"
        next_action = "inspect_branch_state"
        reason = "branch_missing"
        detail: dict[str, Any] = {}
    elif state == "abandoned":
        classification = "abandoned"
        next_action = "do_not_schedule"
        reason = "terminal_abandoned"
        detail = {}
    elif branch_is_parked_lineage(branch):
        classification = "parked"
        next_action = "clean_fork"
        reason = "parked_lineage"
        detail = {}
    elif blocked:
        classification = "replay_blocked"
        next_action = "clean_fork_or_restore_replay_identity"
        reason = FRESH_RUNTIME_REPLAY_BLOCKED_MISSING_IDENTITY
        detail = blocked
    else:
        followup = _fresh_runtime_followup_marker(branch)
        if _fresh_runtime_required(branch, followup) or bool(
            followup.get("followup_required")
        ):
            classification = "active_with_required_follow_up"
            next_action = "required_follow_up"
            reason = "fresh_runtime_or_diagnostic_followup_required"
            detail = {
                "fresh_runtime_required": bool(
                    followup.get("fresh_runtime_required")
                ),
                "fresh_runtime_pending": bool(
                    followup.get("fresh_runtime_pending")
                ),
            }
        elif state in {
            "explore",
            "explore_expand",
            "ready_validate",
            "validating",
            "validating_expand",
            "ready_frozen",
            "frozen_testing",
            "stale",
            "stale_weight_update",
            "blocked_infra",
        }:
            classification = "active"
            next_action = "normal_scheduler_policy"
            reason = "active_branch"
            detail = {}
        else:
            classification = "inactive"
            next_action = "do_not_schedule"
            reason = "inactive_or_unknown_state"
            detail = {}
    payload = {
        "schema_version": BRANCH_FINAL_CLASSIFICATION_SCHEMA,
        "classification": classification,
        "next_action": next_action,
        "reason": reason,
        "branch_state": state,
        "branch_code_status": branch_code_status(branch),
        "deterministic_lifecycle_status": True,
        "promotion_boundary": "not_a_promotion_or_validation_decision",
        "decision_features_excluded": True,
    }
    if detail:
        payload["detail"] = detail
    return payload


def campaign_remaining_branch_classification(
    branch_rows: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Aggregate report-facing remaining branch classifications from branch rows."""
    branches: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    ids_by_classification: dict[str, list[str]] = {}
    for row in branch_rows:
        if not isinstance(row, Mapping):
            continue
        card = row.get("branch_card")
        card_map = card if isinstance(card, Mapping) else row
        branch_id = str(
            card_map.get("branch_id")
            or row.get("id")
            or row.get("branch_id")
            or ""
        ).strip()
        if not branch_id:
            continue
        classification_payload = _classification_payload_from_card(card_map, row)
        classification = str(
            classification_payload.get("classification") or "unknown"
        )
        counts[classification] = counts.get(classification, 0) + 1
        ids_by_classification.setdefault(classification, []).append(branch_id)
        branches.append(
            {
                "branch_id": branch_id,
                "classification": classification,
                "next_action": classification_payload.get("next_action"),
                "reason": classification_payload.get("reason"),
                "branch_state": classification_payload.get("branch_state")
                or row.get("state")
                or card_map.get("status"),
                "branch_code_status": classification_payload.get(
                    "branch_code_status"
                )
                or row.get("branch_code_status")
                or card_map.get("branch_code_status"),
                "active_slot_status": card_map.get("active_slot_status"),
                "counts_toward_active_slots": card_map.get(
                    "counts_toward_active_slots"
                ),
            }
        )
    return {
        "schema_version": "scion.remaining_branch_classification.v1",
        "scope": "remaining_reportable_branches",
        "branch_count": len(branches),
        "counts": counts,
        "branch_ids_by_classification": ids_by_classification,
        "branches": branches,
        "decision_features_excluded": True,
    }


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
    if branch_fresh_runtime_replay_blocked(branch):
        return "replay_blocked"
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
    raw_last_block = (
        dict(getattr(branch, "last_branch_lifecycle_policy_block", {}) or {})
        if branch is not None
        and isinstance(
            getattr(branch, "last_branch_lifecycle_policy_block", None),
            Mapping,
        )
        else {}
    )
    last_block = (
        raw_last_block if is_branch_lifecycle_policy_block(raw_last_block) else {}
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


def _branch_state_value(branch: Branch | None) -> str:
    if branch is None:
        return "unknown"
    state = getattr(branch, "state", None)
    return str(getattr(state, "value", state) or "unknown")


def _classification_payload_from_card(
    card: Mapping[str, Any],
    row: Mapping[str, Any],
) -> dict[str, Any]:
    value = card.get("final_branch_classification")
    if isinstance(value, Mapping):
        return dict(value)
    state = str(card.get("status") or row.get("state") or "")
    lineage = str(card.get("lineage_status") or "")
    if state == "abandoned" or lineage == "abandoned":
        classification = "abandoned"
        next_action = "do_not_schedule"
        reason = "terminal_abandoned"
    elif state == "parked_lineage" or lineage == "parked":
        classification = "parked"
        next_action = "clean_fork"
        reason = "parked_lineage"
    elif lineage == "replay_blocked":
        classification = "replay_blocked"
        next_action = "clean_fork_or_restore_replay_identity"
        reason = FRESH_RUNTIME_REPLAY_BLOCKED_MISSING_IDENTITY
    elif bool(card.get("followup_required")):
        classification = "active_with_required_follow_up"
        next_action = "required_follow_up"
        reason = "fresh_runtime_or_diagnostic_followup_required"
    elif card.get("counts_toward_active_slots") is True:
        classification = "active"
        next_action = "normal_scheduler_policy"
        reason = "active_branch"
    else:
        classification = "inactive"
        next_action = "do_not_schedule"
        reason = "inactive_or_unknown_state"
    return {
        "classification": classification,
        "next_action": next_action,
        "reason": reason,
        "branch_state": state,
        "branch_code_status": card.get("branch_code_status")
        or row.get("branch_code_status"),
    }


def _fresh_runtime_replay_blocked_diagnostic(
    branch: Branch | None,
) -> dict[str, Any]:
    if branch is None:
        return {}
    state = _branch_state_value(branch)
    if state not in {"explore", "explore_expand"}:
        return {}
    summary = _branch_evidence_summary(branch)
    marker = _fresh_runtime_followup_marker(branch)
    if not _fresh_runtime_required(branch, marker):
        return {}
    if not _repeated_no_effect_tie(branch, summary):
        return {}
    if not (_runtime_low_or_fresh_required(summary, marker)):
        return {}
    missing_identity = _missing_replay_identity_keys(
        _summary_replay_identity(summary, marker)
    )
    materialization = marker.get("replay_materialization")
    materialized_identity_complete = (
        isinstance(materialization, Mapping)
        and materialization.get("materializable") is True
        and str(materialization.get("replay_identity_status") or "") == "complete"
    )
    if not missing_identity or materialized_identity_complete:
        return {}
    return {
        "schema_version": "scion.fresh_runtime_replay_block.v1",
        "reason": FRESH_RUNTIME_REPLAY_BLOCKED_MISSING_IDENTITY,
        "fresh_runtime_required": True,
        "fresh_runtime_pending": bool(marker.get("fresh_runtime_pending")),
        "runtime_evidence_confidence": str(
            summary.get("runtime_evidence_confidence") or "unknown"
        ),
        "runtime_evidence_status": str(
            summary.get("runtime_evidence_status") or "unknown"
        ),
        "missing_replay_identity_keys": missing_identity,
        "lifecycle_marginal_no_effect_streak": _nonnegative_int(
            getattr(branch, "lifecycle_marginal_no_effect_streak", 0)
        ),
        "lifecycle_no_effect_diagnostic_followups": _nonnegative_int(
            getattr(branch, "lifecycle_no_effect_diagnostic_followups", 0)
        ),
        "lifecycle_signal_repeat_count": _nonnegative_int(
            getattr(branch, "lifecycle_signal_repeat_count", 0)
        ),
        "runtime_evidence_pressure_count": _nonnegative_int(
            summary.get("runtime_evidence_pressure_count")
        ),
        "decision_features_excluded": True,
    }


def _branch_evidence_summary(branch: Branch | None) -> Mapping[str, Any]:
    if branch is None:
        return {}
    value = getattr(branch, "branch_evidence_summary", {}) or {}
    return value if isinstance(value, Mapping) else {}


def _fresh_runtime_followup_marker(branch: Branch | None) -> Mapping[str, Any]:
    summary = _branch_evidence_summary(branch)
    value = summary.get("fresh_runtime_followup")
    return value if isinstance(value, Mapping) else {}


def _fresh_runtime_required(
    branch: Branch | None,
    marker: Mapping[str, Any],
) -> bool:
    summary = _branch_evidence_summary(branch)
    runtime_status = str(summary.get("runtime_evidence_status") or "").lower()
    reason_codes = _summary_reason_codes(summary)
    return bool(
        summary.get("fresh_runtime_required")
        or marker.get("fresh_runtime_required")
        or marker.get("followup_required")
        or runtime_status in {"fresh_champion_required", "fresh_required"}
        or "RUNTIME_TIE_FRESH_CHAMPION_REQUIRED" in reason_codes
        or "RUNTIME_EVIDENCE_FRESH_CHAMPION_REQUIRED" in reason_codes
    )


def _runtime_low_or_fresh_required(
    summary: Mapping[str, Any],
    marker: Mapping[str, Any],
) -> bool:
    confidence = str(summary.get("runtime_evidence_confidence") or "").lower()
    status = str(summary.get("runtime_evidence_status") or "").lower()
    return bool(
        marker.get("fresh_runtime_required")
        or summary.get("fresh_runtime_required")
        or status in {"fresh_champion_required", "fresh_required"}
        or confidence.startswith("low")
        or "cached" in confidence
    )


def _repeated_no_effect_tie(
    branch: Branch,
    summary: Mapping[str, Any],
) -> bool:
    status = branch_code_status(branch)
    tier = str(getattr(branch, "last_screening_feedback_tier", "") or "")
    summary_tier = str(summary.get("tier") or "")
    no_effect = (
        status in {"active_no_effect", "active_neutral"}
        or tier in {"no_effect", "neutral"}
        or summary_tier in {"no_effect", "neutral"}
    )
    if not no_effect and not _summary_tie_no_effect(summary):
        return False
    return bool(
        _nonnegative_int(getattr(branch, "lifecycle_no_effect_diagnostic_followups", 0))
        >= 2
        or _nonnegative_int(getattr(branch, "lifecycle_marginal_no_effect_streak", 0))
        >= 2
        or _nonnegative_int(getattr(branch, "lifecycle_signal_repeat_count", 0)) >= 2
        or _nonnegative_int(summary.get("runtime_evidence_pressure_count")) >= 2
        or _activation_zero_effect_streak(summary) >= 2
    )


def _summary_tie_no_effect(summary: Mapping[str, Any]) -> bool:
    wins = _nonnegative_int(summary.get("wins"))
    losses = _nonnegative_int(summary.get("losses"))
    ties = _nonnegative_int(summary.get("ties"))
    pair_wins = _nonnegative_int(summary.get("pair_wins"))
    pair_losses = _nonnegative_int(summary.get("pair_losses"))
    pair_ties = _nonnegative_int(summary.get("pair_ties"))
    return bool(
        wins == 0
        and losses == 0
        and ties > 0
        and pair_wins == 0
        and pair_losses == 0
        and pair_ties >= 0
    )


def _activation_zero_effect_streak(summary: Mapping[str, Any]) -> int:
    zero_summary = summary.get("activation_zero_effect_summary")
    if isinstance(zero_summary, Mapping):
        return _nonnegative_int(zero_summary.get("streak"))
    return _nonnegative_int(summary.get("activation_zero_effect_streak"))


def _summary_replay_identity(
    summary: Mapping[str, Any],
    marker: Mapping[str, Any],
) -> Mapping[str, Any] | None:
    for key in (
        "replay_identity",
        "formal_replay_identity",
        "candidate_replay_identity",
    ):
        value = summary.get(key)
        if isinstance(value, Mapping):
            return value
    metadata = summary.get("replay_metadata")
    if isinstance(metadata, Mapping):
        value = metadata.get("replay_identity")
        if isinstance(value, Mapping):
            return value
    value = marker.get("replay_identity")
    if isinstance(value, Mapping):
        return value
    return None


def _missing_replay_identity_keys(
    replay_identity: Mapping[str, Any] | None,
) -> list[str]:
    return formal_replay_identity_missing_keys(replay_identity)


def _summary_reason_codes(summary: Mapping[str, Any]) -> set[str]:
    values: list[Any] = []
    for key in (
        "reason_codes",
        "decision_reason_codes",
        "why_not_promoted_reason_codes",
        "gate_observation_reason_codes",
    ):
        value = summary.get(key)
        if isinstance(value, str):
            values.append(value)
        elif isinstance(value, Iterable) and not isinstance(value, Mapping):
            values.extend(value)
    return {str(value).strip().upper() for value in values if str(value).strip()}


def _nonnegative_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


__all__ = [
    "ACTIVATION_MISSING_OR_WIRING_SUSPECT",
    "BRANCH_FINAL_CLASSIFICATION_SCHEMA",
    "BRANCH_LIFECYCLE_NEW_MECHANISM_INELIGIBLE",
    "BRANCH_LIFECYCLE_REROUTE_AFTER_POLICY_BLOCK",
    "BRANCH_LIFECYCLE_REROUTE_LOOP_LIMIT",
    "BRANCH_LOCAL_FOLLOWUP_OR_EXPLICIT_BRIDGE",
    "BRANCH_LOCAL_FOLLOWUP_MODE",
    "CLEAN_FORK_REQUIRED_FOR_NEW_MECHANISM",
    "FRESH_RUNTIME_REPLAY_BLOCKED_MISSING_IDENTITY",
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
    "TELEMETRY_EFFECT_ZERO_OUTCOME",
    "TELEMETRY_WIRING_SUSPECT",
    "WIRING_SUSPECT_REQUIRES_REPAIR",
    "branch_allows_clean_workspace_reuse",
    "branch_checkpoint_status",
    "branch_code_status",
    "branch_fresh_runtime_replay_blocked",
    "branch_has_actionable_diagnostic",
    "branch_has_retained_checkpoint",
    "branch_lifecycle_closure_classification",
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
    "campaign_remaining_branch_classification",
    "hard_telemetry_repair_reason_present",
    "is_branch_lifecycle_policy_block",
    "nonblocking_telemetry_effect_zero_reason_code",
    "record_branch_lifecycle_policy_block",
    "telemetry_effect_zero_reason_present",
]
