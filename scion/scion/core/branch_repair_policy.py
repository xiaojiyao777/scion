"""Generic branch continuation policy for non-clean branches."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Sequence

from scion.core.branch_hygiene import (
    BRANCH_LOCAL_FOLLOWUP_OR_EXPLICIT_BRIDGE,
    CLEAN_FORK_REQUIRED_FOR_NEW_MECHANISM,
    REPAIR_FIRST_SAME_MECHANISM_OR_CLEAN_FORK,
    SAME_MECHANISM_FOLLOWUP_ONLY,
    WIRING_SUSPECT_REQUIRES_REPAIR,
    branch_mechanism_ids,
    branch_requires_repair_focus,
    branch_requires_same_mechanism_followup,
)
from scion.core.models import (
    Branch,
    HypothesisProposal,
    PatchProposal,
    StepRecord,
    mechanism_changes,
)


REPAIR_FIRST_POLICY_VIOLATION = "repair_first_policy_violation"
BRANCH_LIFECYCLE_POLICY_VIOLATION = "branch_lifecycle_policy_violation"
REPAIR_INTENT_REQUIRED = "telemetry_wiring_trigger_repair_intent_required"
NEW_MECHANISM_REQUIRES_CLEAN_FORK = "new_mechanism_requires_clean_fork"
MISSING_DECLARED_REPAIR_MECHANISM = "missing_declared_repair_mechanism"
MISSING_DECLARED_BRANCH_MECHANISM = "missing_declared_branch_mechanism"
_POLICY_CHECK_VIOLATION_CODES = frozenset(
    {
        BRANCH_LIFECYCLE_POLICY_VIOLATION,
        REPAIR_FIRST_POLICY_VIOLATION,
    }
)

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
class BranchLifecyclePolicyBlockSignal:
    """Typed signal from an exact branch-lifecycle policy-check detail."""

    reason: str
    violation_code: str = BRANCH_LIFECYCLE_POLICY_VIOLATION
    branch_followup_policy: str = ""
    clean_fork_policy: str = ""
    protected_mechanism_ids: tuple[str, ...] = ()
    proposed_mechanism_ids: tuple[str, ...] = ()
    candidate_routing: str = ""
    clean_fork_signal: bool = False


@dataclass(frozen=True)
class RepairPolicyCheck:
    allowed: bool
    reason: str = ""
    protected_mechanism_ids: tuple[str, ...] = ()
    proposed_mechanism_ids: tuple[str, ...] = ()
    violation_code: str = REPAIR_FIRST_POLICY_VIOLATION
    branch_followup_policy: str = SAME_MECHANISM_FOLLOWUP_ONLY

    @property
    def detail(self) -> str:
        if self.allowed:
            return ""
        protected = ",".join(self.protected_mechanism_ids) or "unknown"
        proposed = ",".join(self.proposed_mechanism_ids) or "none"
        parts = [f"{self.violation_code}: {self.reason}"]
        if self.violation_code == REPAIR_FIRST_POLICY_VIOLATION:
            parts.append(f"repair_focus={WIRING_SUSPECT_REQUIRES_REPAIR}")
            parts.append(
                f"repair_policy={REPAIR_FIRST_SAME_MECHANISM_OR_CLEAN_FORK}"
            )
        else:
            parts.append("repair_focus_required=false")
        parts.extend(
            [
                f"branch_followup_policy={self.branch_followup_policy}",
                f"clean_fork_policy={CLEAN_FORK_REQUIRED_FOR_NEW_MECHANISM}",
                f"protected_mechanism_ids={protected}",
                f"proposed_mechanism_ids={proposed}",
            ]
        )
        return "; ".join(parts)

    @property
    def lifecycle_block_signal(self) -> BranchLifecyclePolicyBlockSignal | None:
        if (
            self.allowed
            or self.violation_code != BRANCH_LIFECYCLE_POLICY_VIOLATION
        ):
            return None
        return branch_lifecycle_policy_block_signal_from_detail(self.detail)


def branch_lifecycle_policy_block_signal_from_detail(
    detail: str | None,
) -> BranchLifecyclePolicyBlockSignal | None:
    """Parse only the exact machine-generated lifecycle policy-check detail."""
    text = _policy_check_detail_payload(detail)
    if text is None:
        return None
    violation_code, separator, payload = text.partition(":")
    if (
        separator != ":"
        or violation_code.strip() != BRANCH_LIFECYCLE_POLICY_VIOLATION
    ):
        return None
    segments = [segment.strip() for segment in payload.split(";")]
    if not segments or not segments[0]:
        return None
    values: dict[str, str] = {}
    for segment in segments[1:]:
        if not segment:
            continue
        key, key_separator, value = segment.partition("=")
        if key_separator != "=":
            return None
        values[key.strip()] = value.strip()
    required_keys = {
        "branch_followup_policy",
        "clean_fork_policy",
        "protected_mechanism_ids",
        "proposed_mechanism_ids",
    }
    if not required_keys.issubset(values):
        return None
    clean_fork_policy = values["clean_fork_policy"]
    if clean_fork_policy != CLEAN_FORK_REQUIRED_FOR_NEW_MECHANISM:
        return None
    reason = segments[0]
    clean_fork_signal = reason == NEW_MECHANISM_REQUIRES_CLEAN_FORK
    return BranchLifecyclePolicyBlockSignal(
        reason=reason,
        branch_followup_policy=values["branch_followup_policy"],
        clean_fork_policy=clean_fork_policy,
        protected_mechanism_ids=_detail_mechanism_ids(
            values["protected_mechanism_ids"]
        ),
        proposed_mechanism_ids=_detail_mechanism_ids(
            values["proposed_mechanism_ids"]
        ),
        candidate_routing=(
            "new_mechanism_requires_clean_fork_signal"
            if clean_fork_signal
            else ""
        ),
        clean_fork_signal=clean_fork_signal,
    )


def repair_policy_check_violation_code_from_detail(
    detail: str | None,
) -> str | None:
    """Return the violation code from an exact machine policy-check detail."""
    text = _policy_check_detail_payload(detail)
    if text is None:
        return None
    violation_code, separator, payload = text.partition(":")
    violation_code = violation_code.strip()
    if separator != ":" or violation_code not in _POLICY_CHECK_VIOLATION_CODES:
        return None
    segments = [segment.strip() for segment in payload.split(";")]
    if not segments or not segments[0]:
        return None
    keys: set[str] = set()
    for segment in segments[1:]:
        if not segment:
            continue
        key, key_separator, _value = segment.partition("=")
        if key_separator != "=":
            return None
        keys.add(key.strip())
    required_keys = {
        "branch_followup_policy",
        "clean_fork_policy",
        "protected_mechanism_ids",
        "proposed_mechanism_ids",
    }
    if not required_keys.issubset(keys):
        return None
    if violation_code == REPAIR_FIRST_POLICY_VIOLATION and not {
        "repair_focus",
        "repair_policy",
    }.issubset(keys):
        return None
    if (
        violation_code == BRANCH_LIFECYCLE_POLICY_VIOLATION
        and "repair_focus_required" not in keys
    ):
        return None
    return violation_code


def _policy_check_detail_payload(detail: str | None) -> str | None:
    raw_text = str(detail or "").strip()
    if any(
        raw_text.startswith(f"{code}:")
        for code in _POLICY_CHECK_VIOLATION_CODES
    ):
        return raw_text
    prefix, prefix_separator, suffix = raw_text.partition(": ")
    if (
        prefix_separator != ": "
        or not prefix.startswith("agentic_proposal:")
        or not any(
            suffix.startswith(f"{code}:")
            for code in _POLICY_CHECK_VIOLATION_CODES
        )
    ):
        return None
    return suffix


def _detail_mechanism_ids(value: str) -> tuple[str, ...]:
    text = str(value or "").strip()
    if text in {"", "none", "unknown"}:
        return ()
    return tuple(
        dict.fromkeys(item.strip() for item in text.split(",") if item.strip())
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


def branch_continuation_mechanism_ids(
    branch: Branch | None,
    step_history: Sequence[StepRecord] | None = None,
) -> tuple[str, ...]:
    """Return mechanism ids already attributed to a non-clean branch."""
    if branch is None:
        return ()
    stored = branch_mechanism_ids(branch)
    if stored:
        return stored
    repair_ids = branch_repair_mechanism_ids(branch, step_history)
    if repair_ids:
        return repair_ids
    if not step_history:
        return ()
    ids: list[str] = []
    for step in tuple(step_history):
        if getattr(step, "branch_id", None) != branch.branch_id:
            continue
        if getattr(step, "protocol_result", None) is None:
            continue
        for mechanism_id in mechanism_ids_for_repair(
            getattr(step, "hypothesis", None)
        ):
            ids.append(mechanism_id)
    return tuple(dict.fromkeys(ids))


def validate_branch_continuation_hypothesis(
    branch: Branch | None,
    hypothesis: HypothesisProposal | None,
    *,
    step_history: Sequence[StepRecord] | None = None,
) -> RepairPolicyCheck:
    """Enforce same-mechanism continuation on non-clean branches."""
    if branch_requires_repair_focus(branch):
        return _validate_repair_focused_hypothesis(
            branch,
            hypothesis,
            step_history=step_history,
        )
    if _is_weak_positive_branch(branch):
        return RepairPolicyCheck(
            allowed=True,
            protected_mechanism_ids=branch_continuation_mechanism_ids(
                branch,
                step_history,
            ),
            proposed_mechanism_ids=mechanism_ids_for_repair(hypothesis),
            violation_code=BRANCH_LIFECYCLE_POLICY_VIOLATION,
            branch_followup_policy=BRANCH_LOCAL_FOLLOWUP_OR_EXPLICIT_BRIDGE,
        )
    if not branch_requires_same_mechanism_followup(branch):
        return RepairPolicyCheck(allowed=True)

    protected = branch_continuation_mechanism_ids(branch, step_history)
    proposed = mechanism_ids_for_repair(hypothesis)
    if not protected:
        return RepairPolicyCheck(
            allowed=False,
            reason=MISSING_DECLARED_BRANCH_MECHANISM,
            protected_mechanism_ids=protected,
            proposed_mechanism_ids=proposed,
            violation_code=BRANCH_LIFECYCLE_POLICY_VIOLATION,
        )
    if not proposed:
        return RepairPolicyCheck(
            allowed=False,
            reason=MISSING_DECLARED_BRANCH_MECHANISM,
            protected_mechanism_ids=protected,
            proposed_mechanism_ids=proposed,
            violation_code=BRANCH_LIFECYCLE_POLICY_VIOLATION,
        )
    if not set(proposed).issubset(set(protected)):
        return RepairPolicyCheck(
            allowed=False,
            reason=NEW_MECHANISM_REQUIRES_CLEAN_FORK,
            protected_mechanism_ids=protected,
            proposed_mechanism_ids=proposed,
            violation_code=BRANCH_LIFECYCLE_POLICY_VIOLATION,
        )
    return RepairPolicyCheck(
        allowed=True,
        protected_mechanism_ids=protected,
        proposed_mechanism_ids=proposed,
        violation_code=BRANCH_LIFECYCLE_POLICY_VIOLATION,
    )


def validate_repair_focused_hypothesis(
    branch: Branch | None,
    hypothesis: HypothesisProposal | None,
    *,
    step_history: Sequence[StepRecord] | None = None,
) -> RepairPolicyCheck:
    """Backward-compatible wrapper for branch continuation hypothesis policy."""
    return validate_branch_continuation_hypothesis(
        branch,
        hypothesis,
        step_history=step_history,
    )


def _validate_repair_focused_hypothesis(
    branch: Branch | None,
    hypothesis: HypothesisProposal | None,
    *,
    step_history: Sequence[StepRecord] | None = None,
) -> RepairPolicyCheck:
    """Enforce repair-only hypothesis generation on telemetry-suspect branches."""
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


def validate_branch_continuation_patch(
    branch: Branch | None,
    hypothesis: HypothesisProposal | None,
    patch: PatchProposal | None,
    *,
    step_history: Sequence[StepRecord] | None = None,
) -> RepairPolicyCheck:
    """Enforce branch-continuation code output on non-clean branches."""
    hypothesis_check = validate_branch_continuation_hypothesis(
        branch,
        hypothesis,
        step_history=step_history,
    )
    if (
        not hypothesis_check.allowed
        or not branch_requires_same_mechanism_followup(branch)
    ):
        return hypothesis_check
    if _is_weak_positive_branch(branch):
        return hypothesis_check
    protected = hypothesis_check.protected_mechanism_ids
    patch_ids = mechanism_ids_for_repair(patch)
    if patch_ids and not set(patch_ids).issubset(set(protected)):
        return RepairPolicyCheck(
            allowed=False,
            reason=NEW_MECHANISM_REQUIRES_CLEAN_FORK,
            protected_mechanism_ids=protected,
            proposed_mechanism_ids=patch_ids,
            violation_code=hypothesis_check.violation_code,
        )
    return hypothesis_check


def validate_repair_focused_patch(
    branch: Branch | None,
    hypothesis: HypothesisProposal | None,
    patch: PatchProposal | None,
    *,
    step_history: Sequence[StepRecord] | None = None,
) -> RepairPolicyCheck:
    """Backward-compatible wrapper for branch continuation patch policy."""
    return validate_branch_continuation_patch(
        branch,
        hypothesis,
        patch,
        step_history=step_history,
    )


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


def is_branch_lifecycle_policy_block_detail(detail: str | None) -> bool:
    text = str(detail or "").lower()
    return (
        BRANCH_LIFECYCLE_POLICY_VIOLATION in text
        or NEW_MECHANISM_REQUIRES_CLEAN_FORK in text
    )


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


def _is_weak_positive_branch(branch: Branch | None) -> bool:
    if branch is None:
        return False
    status = str(getattr(branch, "branch_code_status", "") or "")
    tier = str(getattr(branch, "last_screening_feedback_tier", "") or "")
    return status == "active_weak_positive" or tier == "weak_positive"


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
    "MISSING_DECLARED_BRANCH_MECHANISM",
    "NEW_MECHANISM_REQUIRES_CLEAN_FORK",
    "BRANCH_LIFECYCLE_POLICY_VIOLATION",
    "REPAIR_FIRST_POLICY_VIOLATION",
    "REPAIR_INTENT_REQUIRED",
    "BranchLifecyclePolicyBlockSignal",
    "RepairPolicyCheck",
    "branch_lifecycle_policy_block_signal_from_detail",
    "branch_continuation_mechanism_ids",
    "branch_repair_mechanism_ids",
    "mechanism_ids_for_repair",
    "repair_policy_check_violation_code_from_detail",
    "is_branch_lifecycle_policy_block_detail",
    "repair_attempt_key",
    "repair_attempt_key_label",
    "validate_branch_continuation_hypothesis",
    "validate_branch_continuation_patch",
    "validate_repair_focused_hypothesis",
    "validate_repair_focused_patch",
]
