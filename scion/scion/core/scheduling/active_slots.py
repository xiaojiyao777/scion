"""Active-slot accounting and reconciliation for scheduler resource policy."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Iterable, Literal, Mapping, Protocol

from scion.core.branch_hygiene import (
    BRANCH_LIFECYCLE_NEW_MECHANISM_INELIGIBLE,
    BRANCH_LIFECYCLE_REROUTE_AFTER_POLICY_BLOCK,
    branch_is_parked_lineage,
)
from scion.core.branch_lifecycle_policy import BRANCH_LIFECYCLE_PARK_LINEAGE
from scion.core.models import Branch, BranchState


ACTIVE_SLOT_HARD_CAP_RECONCILED = "active_slot_hard_cap_reconciled"
ACTIVE_SLOT_RECLAIMED_FOR_NEW_BRANCH = "active_slot_reclaimed_for_new_branch"
ACTIVE_SLOT_HARD_CAP_BLOCKED = "active_slot_hard_cap_blocked"
SCHEDULER_ACTIVE_SLOT_RECLAIM_PARK_LINEAGE = (
    "SCHEDULER_ACTIVE_SLOT_RECLAIM_PARK_LINEAGE"
)

_TERMINAL_STATES = frozenset({
    BranchState.PROMOTED,
    BranchState.ABANDONED,
    BranchState.PARKED_LINEAGE,
})


class ActiveSlotPolicy(Protocol):
    scheduler_owned_release_reason: Callable[[Branch | None], str]
    eligible_new_branch_reclaim: Callable[[Branch], bool]
    reclaim_sort_key: Callable[[Branch], tuple[Any, ...]]


@dataclass(frozen=True)
class ActiveSlotReconciliation:
    mode: Literal["overflow", "new_branch_reclaim"]
    reason: str
    before_used: int
    after_used: int
    max_active_branches: int
    parked_branch_ids: tuple[str, ...] = ()
    candidate_branch_ids: tuple[str, ...] = ()
    marker_missing_branch_ids: tuple[str, ...] = ()
    scheduler_origin_parked_branch_ids: tuple[str, ...] = ()

    @property
    def changed(self) -> bool:
        return bool(self.parked_branch_ids)

    @property
    def blocked(self) -> bool:
        return bool(self.marker_missing_branch_ids)

    def as_audit_metadata(self) -> dict[str, Any]:
        metadata: dict[str, Any] = {
            "mode": self.mode,
            "reason": self.reason,
            "before_used": self.before_used,
            "after_used": self.after_used,
            "max_active_branches": self.max_active_branches,
            "parked_branch_ids": list(self.parked_branch_ids),
        }
        if self.candidate_branch_ids:
            metadata["candidate_branch_ids"] = list(self.candidate_branch_ids)
        if self.marker_missing_branch_ids:
            metadata.update(
                {
                    "decision_origin_marker_required": True,
                    "blocked_reason": (
                        "decision_origin_lifecycle_marker_missing"
                    ),
                    "marker_missing_branch_ids": list(
                        self.marker_missing_branch_ids
                    ),
                }
            )
        if self.parked_branch_ids:
            scheduler_origin_ids = set(self.scheduler_origin_parked_branch_ids)
            lifecycle_origin = (
                "scheduler_active_slot_reclaim"
                if scheduler_origin_ids
                else "decision_lifecycle"
            )
            reason_codes = [BRANCH_LIFECYCLE_PARK_LINEAGE]
            if scheduler_origin_ids:
                reason_codes.append(SCHEDULER_ACTIVE_SLOT_RECLAIM_PARK_LINEAGE)
            metadata.update(
                {
                    "lifecycle_action": "park_lineage",
                    "lifecycle_action_origin": lifecycle_origin,
                    "lifecycle_action_reason_codes": reason_codes,
                    "reclaimed_branch_ids": list(self.parked_branch_ids),
                }
            )
            if scheduler_origin_ids:
                metadata["scheduler_origin_reclaimed_branch_ids"] = list(
                    self.scheduler_origin_parked_branch_ids
                )
        return metadata


def branch_counts_toward_active_slots(
    branch: Branch,
    *,
    policy: ActiveSlotPolicy,
) -> bool:
    """Return whether ``branch`` consumes a reported active lineage slot."""
    if branch.state in _TERMINAL_STATES:
        return False
    if (
        branch_is_parked_lineage(branch)
        and branch_has_decision_origin_park_marker(branch)
    ):
        return False
    if policy.scheduler_owned_release_reason(branch):
        return False
    return True


def branch_active_slot_release_reason(
    branch: Branch | None,
    *,
    policy: ActiveSlotPolicy,
) -> str:
    """Return why ``branch`` is excluded from active-slot accounting, if known."""
    if branch is None:
        return ""
    if branch.state in _TERMINAL_STATES:
        if branch_is_parked_lineage(branch):
            return "parked_lineage"
        return "terminal_state"
    if (
        branch_is_parked_lineage(branch)
        and branch_has_decision_origin_park_marker(branch)
    ):
        return "parked_lineage"
    release_reason = policy.scheduler_owned_release_reason(branch)
    if release_reason:
        return release_reason
    return ""


def branch_has_decision_origin_park_marker(branch: Branch | None) -> bool:
    return bool(branch_decision_origin_park_reason_codes(branch))


def branch_decision_origin_park_reason_codes(
    branch: Branch | None,
) -> tuple[str, ...]:
    if branch is None:
        return ()
    codes: list[str] = []
    block = getattr(branch, "last_branch_lifecycle_policy_block", {}) or {}
    if isinstance(block, Mapping):
        codes.extend(_decision_origin_park_codes_from_block(block))
    summary = getattr(branch, "branch_evidence_summary", {}) or {}
    if isinstance(summary, Mapping):
        codes.extend(
            _park_reason_codes_from_mapping(
                summary,
                include_lifecycle_action_codes=True,
            )
        )
    return tuple(dict.fromkeys(codes))


def active_slot_branches(
    branches: Iterable[Branch],
    *,
    policy: ActiveSlotPolicy,
) -> list[Branch]:
    """Filter branches to the active-slot limit pool."""
    return [
        branch
        for branch in branches
        if branch_counts_toward_active_slots(branch, policy=policy)
    ]


def active_slot_inventory(
    branches: Iterable[Branch],
    *,
    max_active_branches: int,
    policy: ActiveSlotPolicy,
) -> dict[str, Any]:
    """Build a status/summary inventory for active scheduling slots."""
    branch_list = list(branches)
    active = active_slot_branches(branch_list, policy=policy)
    parked = [
        branch
        for branch in branch_list
        if branch_active_slot_release_reason(branch, policy=policy)
        == "parked_lineage"
    ]
    released = [
        branch
        for branch in branch_list
        if branch_active_slot_release_reason(branch, policy=policy)
        and branch_active_slot_release_reason(branch, policy=policy)
        != "parked_lineage"
    ]
    limit = max(0, int(max_active_branches))
    used = len(active)
    return {
        "used": used,
        "max": limit,
        "available": max(0, limit - used),
        "branch_ids": [branch.branch_id for branch in active],
        "parked_lineages": len(parked),
        "parked_lineage_ids": [branch.branch_id for branch in parked],
        "released_active_slots": len(released),
        "released_active_slot_ids": [branch.branch_id for branch in released],
        "released_active_slot_reasons": {
            branch.branch_id: branch_active_slot_release_reason(
                branch,
                policy=policy,
            )
            for branch in released
        },
    }


def reconcile_active_slot_overflow(
    branches: Iterable[Branch],
    *,
    max_active_branches: int,
    policy: ActiveSlotPolicy,
) -> ActiveSlotReconciliation:
    """Persist Decision-marked parked lineages until active slots fit the cap."""
    branch_list = list(branches)
    limit = max(0, int(max_active_branches))
    return _reconcile_active_slots(
        branch_list,
        max_active_branches=limit,
        target_used=limit,
        mode="overflow",
        reason=ACTIVE_SLOT_HARD_CAP_RECONCILED,
        reclaim_filter=lambda _branch: True,
        policy=policy,
    )


def reclaim_active_slot_for_new_branch(
    branches: Iterable[Branch],
    *,
    max_active_branches: int,
    policy: ActiveSlotPolicy,
) -> ActiveSlotReconciliation:
    """Persist one Decision-marked parked lineage before admitting a clean fork."""
    branch_list = list(branches)
    limit = max(0, int(max_active_branches))
    active = active_slot_branches(branch_list, policy=policy)
    if limit <= 0 or len(active) < limit:
        return ActiveSlotReconciliation(
            mode="new_branch_reclaim",
            reason=ACTIVE_SLOT_RECLAIMED_FOR_NEW_BRANCH,
            before_used=len(active),
            after_used=len(active),
            max_active_branches=limit,
        )
    return _reconcile_active_slots(
        branch_list,
        max_active_branches=limit,
        target_used=limit - 1,
        mode="new_branch_reclaim",
        reason=ACTIVE_SLOT_RECLAIMED_FOR_NEW_BRANCH,
        reclaim_filter=policy.eligible_new_branch_reclaim,
        policy=policy,
    )


def active_slot_capacity_block_metadata(
    branches: Iterable[Branch],
    *,
    max_active_branches: int,
    policy: ActiveSlotPolicy,
) -> dict[str, Any]:
    active = active_slot_branches(list(branches), policy=policy)
    limit = max(0, int(max_active_branches))
    return {
        "reason": ACTIVE_SLOT_HARD_CAP_BLOCKED,
        "used": len(active),
        "max_active_branches": limit,
        "branch_ids": [branch.branch_id for branch in active],
    }


def _decision_origin_park_codes_from_block(block: Mapping[str, Any]) -> tuple[str, ...]:
    codes = list(
        _park_reason_codes_from_mapping(
            block,
            include_lifecycle_action_codes=False,
        )
    )
    action = str(block.get("action") or block.get("reason") or "").strip()
    if action == "park_lineage":
        codes.extend(
            _park_reason_codes_from_mapping(
                block,
                include_lifecycle_action_codes=True,
            )
        )
    return tuple(dict.fromkeys(codes))


def _park_reason_codes_from_mapping(
    source: Mapping[str, Any],
    *,
    include_lifecycle_action_codes: bool,
) -> tuple[str, ...]:
    keys = ["decision_reason_codes", "terminal_reason_codes"]
    if include_lifecycle_action_codes:
        keys.append("lifecycle_action_reason_codes")
    codes: list[str] = []
    for key in keys:
        for code in _structured_reason_codes(source.get(key)):
            if code == BRANCH_LIFECYCLE_PARK_LINEAGE:
                codes.append(code)
    return tuple(dict.fromkeys(codes))


def _structured_reason_codes(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        raw_values: Iterable[Any] = (value,)
    elif isinstance(value, Iterable) and not isinstance(value, Mapping):
        raw_values = value
    else:
        raw_values = ()
    return tuple(
        str(code).strip()
        for code in raw_values
        if str(code).strip()
    )


def _reconcile_active_slots(
    branches: list[Branch],
    *,
    max_active_branches: int,
    target_used: int,
    mode: Literal["overflow", "new_branch_reclaim"],
    reason: str,
    reclaim_filter: Callable[[Branch], bool],
    policy: ActiveSlotPolicy,
) -> ActiveSlotReconciliation:
    active = active_slot_branches(branches, policy=policy)
    before_used = len(active)
    target = max(0, int(target_used))
    if before_used <= target:
        return ActiveSlotReconciliation(
            mode=mode,
            reason=reason,
            before_used=before_used,
            after_used=before_used,
            max_active_branches=max_active_branches,
        )

    candidates = sorted(
        [branch for branch in active if reclaim_filter(branch)],
        key=policy.reclaim_sort_key,
    )
    candidate_ids = tuple(branch.branch_id for branch in candidates)
    parked: list[str] = []
    scheduler_origin_parked: list[str] = []
    marker_missing: list[str] = []
    for branch in candidates:
        if len(active_slot_branches(branches, policy=policy)) <= target:
            break
        has_decision_marker = branch_has_decision_origin_park_marker(branch)
        if not has_decision_marker and mode != "new_branch_reclaim":
            marker_missing.append(branch.branch_id)
            continue
        parked_branch = _park_active_slot_branch(
            branch,
            reason=reason,
            mode=mode,
            max_active_branches=max_active_branches,
            before_used=before_used,
            scheduler_origin=not has_decision_marker,
        )
        if parked_branch:
            parked.append(branch.branch_id)
            if not has_decision_marker:
                scheduler_origin_parked.append(branch.branch_id)
    after_used = len(active_slot_branches(branches, policy=policy))
    return ActiveSlotReconciliation(
        mode=mode,
        reason=reason,
        before_used=before_used,
        after_used=after_used,
        max_active_branches=max_active_branches,
        parked_branch_ids=tuple(parked),
        candidate_branch_ids=candidate_ids,
        marker_missing_branch_ids=tuple(marker_missing),
        scheduler_origin_parked_branch_ids=tuple(scheduler_origin_parked),
    )


def _park_active_slot_branch(
    branch: Branch,
    *,
    reason: str,
    mode: str,
    max_active_branches: int,
    before_used: int,
    scheduler_origin: bool = False,
) -> bool:
    if not scheduler_origin and not branch_has_decision_origin_park_marker(branch):
        return False
    now = datetime.now()
    existing = dict(getattr(branch, "last_branch_lifecycle_policy_block", {}) or {})
    block_count = int(
        existing.get("block_count")
        or getattr(branch, "branch_lifecycle_policy_blocks", 0)
        or 0
    )
    lifecycle_codes = list(
        dict.fromkeys(
            [
                *list(existing.get("lifecycle_action_reason_codes") or ()),
                *branch_decision_origin_park_reason_codes(branch),
                BRANCH_LIFECYCLE_PARK_LINEAGE,
                *(
                    [SCHEDULER_ACTIVE_SLOT_RECLAIM_PARK_LINEAGE]
                    if scheduler_origin
                    else []
                ),
            ]
        )
    )
    existing.update(
        {
            "reason": existing.get("reason") or "park_lineage",
            "action": existing.get("action") or "park_lineage",
            "lifecycle_action_origin": (
                existing.get("lifecycle_action_origin")
                or (
                    "scheduler_active_slot_reclaim"
                    if scheduler_origin
                    else "decision_lifecycle"
                )
            ),
            "detail": (
                f"{reason}: active_slots.used={before_used} "
                f"max_active_branches={max_active_branches}"
            ),
            "recorded_at": now.isoformat(),
            "block_count": block_count,
            "reroute_reason": BRANCH_LIFECYCLE_REROUTE_AFTER_POLICY_BLOCK,
            "new_mechanism_ineligible_reason": (
                BRANCH_LIFECYCLE_NEW_MECHANISM_INELIGIBLE
            ),
            "lifecycle_action_reason_codes": lifecycle_codes,
            "active_slot_reconciliation": {
                "mode": mode,
                "before_used": before_used,
                "max_active_branches": max_active_branches,
                "reason": reason,
                "scheduler_origin_reclaim": scheduler_origin,
            },
            "active_slot_status": "parked_lineage",
            "next_selection": "excluded_from_active_slot_pool",
        }
    )
    branch.state = BranchState.PARKED_LINEAGE
    branch.branch_code_status = "parked_lineage"
    branch.last_telemetry_outcome = reason
    branch.branch_lifecycle_policy_blocks = block_count
    branch.branch_lifecycle_new_mechanism_ineligible = True
    branch.branch_lifecycle_reroute_reason = (
        BRANCH_LIFECYCLE_REROUTE_AFTER_POLICY_BLOCK
    )
    branch.last_branch_lifecycle_policy_block = existing
    branch.updated_at = now
    return True
