"""Generic repair-first policy for telemetry-suspect branches."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Sequence

from scion.core.branch_hygiene import (
    REPAIR_FIRST_SAME_MECHANISM_OR_CLEAN_FORK,
    WIRING_SUSPECT_REQUIRES_REPAIR,
    branch_requires_repair_focus,
)
from scion.core.models import (
    Branch,
    HypothesisProposal,
    PatchProposal,
    StepRecord,
    mechanism_changes,
)


REPAIR_FIRST_POLICY_VIOLATION = "repair_first_policy_violation"
REPAIR_INTENT_REQUIRED = "telemetry_wiring_trigger_repair_intent_required"
NEW_MECHANISM_REQUIRES_CLEAN_FORK = "new_mechanism_requires_clean_fork"
MISSING_DECLARED_REPAIR_MECHANISM = "missing_declared_repair_mechanism"

_TELEMETRY_REPAIR_TERMS = frozenset(
    {
        "telemetry",
        "wiring",
        "wire",
        "activation",
        "activate",
        "trigger",
        "instrument",
        "instrumentation",
        "diagnostic",
        "repair",
    }
)


@dataclass(frozen=True)
class RepairPolicyCheck:
    allowed: bool
    reason: str = ""
    protected_mechanism_ids: tuple[str, ...] = ()
    proposed_mechanism_ids: tuple[str, ...] = ()

    @property
    def detail(self) -> str:
        if self.allowed:
            return ""
        protected = ",".join(self.protected_mechanism_ids) or "unknown"
        proposed = ",".join(self.proposed_mechanism_ids) or "none"
        return (
            f"{REPAIR_FIRST_POLICY_VIOLATION}: {self.reason}; "
            f"repair_focus={WIRING_SUSPECT_REQUIRES_REPAIR}; "
            f"repair_policy={REPAIR_FIRST_SAME_MECHANISM_OR_CLEAN_FORK}; "
            f"protected_mechanism_ids={protected}; "
            f"proposed_mechanism_ids={proposed}"
        )


def mechanism_ids_for_repair(proposal: Any | None) -> tuple[str, ...]:
    """Return stable declared mechanism ids from a proposal-like object."""
    if proposal is None:
        return ()
    ids = [
        str(change.id).strip()
        for change in mechanism_changes(proposal)
        if str(change.id).strip()
    ]
    return tuple(dict.fromkeys(ids))


def branch_repair_mechanism_ids(
    branch: Branch | None,
    step_history: Sequence[StepRecord] | None = None,
) -> tuple[str, ...]:
    """Return mechanism ids that a telemetry-suspect branch is allowed to repair."""
    if branch is None:
        return ()
    stored = tuple(
        str(item).strip()
        for item in (getattr(branch, "telemetry_repair_mechanism_ids", ()) or ())
        if str(item).strip()
    )
    if stored:
        return tuple(dict.fromkeys(stored))
    if not step_history:
        return ()
    for step in reversed(tuple(step_history)):
        if getattr(step, "branch_id", None) != branch.branch_id:
            continue
        if not _step_has_repairable_telemetry(step):
            continue
        ids = mechanism_ids_for_repair(getattr(step, "hypothesis", None))
        if ids:
            return ids
    return ()


def validate_repair_focused_hypothesis(
    branch: Branch | None,
    hypothesis: HypothesisProposal | None,
    *,
    step_history: Sequence[StepRecord] | None = None,
) -> RepairPolicyCheck:
    """Enforce repair-only hypothesis generation on telemetry-suspect branches."""
    if not branch_requires_repair_focus(branch):
        return RepairPolicyCheck(allowed=True)
    protected = branch_repair_mechanism_ids(branch, step_history)
    proposed = mechanism_ids_for_repair(hypothesis)
    if not protected:
        return RepairPolicyCheck(
            allowed=False,
            reason=MISSING_DECLARED_REPAIR_MECHANISM,
            protected_mechanism_ids=protected,
            proposed_mechanism_ids=proposed,
        )
    if not proposed:
        return RepairPolicyCheck(
            allowed=False,
            reason=MISSING_DECLARED_REPAIR_MECHANISM,
            protected_mechanism_ids=protected,
            proposed_mechanism_ids=proposed,
        )
    if not set(proposed).issubset(set(protected)):
        return RepairPolicyCheck(
            allowed=False,
            reason=NEW_MECHANISM_REQUIRES_CLEAN_FORK,
            protected_mechanism_ids=protected,
            proposed_mechanism_ids=proposed,
        )
    if not _has_repair_intent(hypothesis):
        return RepairPolicyCheck(
            allowed=False,
            reason=REPAIR_INTENT_REQUIRED,
            protected_mechanism_ids=protected,
            proposed_mechanism_ids=proposed,
        )
    return RepairPolicyCheck(
        allowed=True,
        protected_mechanism_ids=protected,
        proposed_mechanism_ids=proposed,
    )


def validate_repair_focused_patch(
    branch: Branch | None,
    hypothesis: HypothesisProposal | None,
    patch: PatchProposal | None,
    *,
    step_history: Sequence[StepRecord] | None = None,
) -> RepairPolicyCheck:
    """Enforce repair-only code output on telemetry-suspect branches."""
    hypothesis_check = validate_repair_focused_hypothesis(
        branch,
        hypothesis,
        step_history=step_history,
    )
    if not hypothesis_check.allowed or not branch_requires_repair_focus(branch):
        return hypothesis_check
    protected = hypothesis_check.protected_mechanism_ids
    patch_ids = mechanism_ids_for_repair(patch)
    if patch_ids and not set(patch_ids).issubset(set(protected)):
        return RepairPolicyCheck(
            allowed=False,
            reason=NEW_MECHANISM_REQUIRES_CLEAN_FORK,
            protected_mechanism_ids=protected,
            proposed_mechanism_ids=patch_ids,
        )
    return hypothesis_check


def repair_attempt_key(
    branch_id: str | None,
    mechanism_ids: Iterable[str] | None,
) -> tuple[str, str]:
    ids = tuple(str(item).strip() for item in (mechanism_ids or ()) if str(item).strip())
    mechanism = "+".join(dict.fromkeys(ids)) if ids else "unknown"
    return (str(branch_id or "unknown"), mechanism)


def repair_attempt_key_label(branch_id: str | None, mechanism_ids: Iterable[str] | None) -> str:
    branch, mechanism = repair_attempt_key(branch_id, mechanism_ids)
    return f"{branch}:{mechanism}"


def _step_has_repairable_telemetry(step: StepRecord) -> bool:
    codes = {
        str(code).lower()
        for code in (getattr(step, "decision_reason_codes", ()) or ())
    }
    if any("telemetry_repairable" in code for code in codes):
        return True
    protocol = getattr(step, "protocol_result", None)
    protocol_codes = {
        str(code).lower()
        for code in (getattr(protocol, "reason_codes", ()) or ())
    }
    return any("telemetry_repairable" in code for code in protocol_codes)


def _has_repair_intent(hypothesis: HypothesisProposal | None) -> bool:
    if hypothesis is None:
        return False
    fields = [
        getattr(hypothesis, "hypothesis_text", ""),
        getattr(hypothesis, "change_locus", ""),
        getattr(hypothesis, "target_weakness", ""),
        getattr(hypothesis, "expected_effect", ""),
        getattr(hypothesis, "no_op_condition", ""),
        getattr(hypothesis, "risk_to_higher_priority", ""),
    ]
    haystack = " ".join(str(field).lower() for field in fields)
    return any(term in haystack for term in _TELEMETRY_REPAIR_TERMS)


__all__ = [
    "MISSING_DECLARED_REPAIR_MECHANISM",
    "NEW_MECHANISM_REQUIRES_CLEAN_FORK",
    "REPAIR_FIRST_POLICY_VIOLATION",
    "REPAIR_INTENT_REQUIRED",
    "RepairPolicyCheck",
    "branch_repair_mechanism_ids",
    "mechanism_ids_for_repair",
    "repair_attempt_key",
    "repair_attempt_key_label",
    "validate_repair_focused_hypothesis",
    "validate_repair_focused_patch",
]
