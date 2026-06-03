"""Generic branch follow-up policy helpers for proposal-time context."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import PurePosixPath
from typing import Any, Mapping, Sequence

from scion.core.branch_repair_policy import (
    branch_continuation_mechanism_ids,
    mechanism_ids_for_repair,
)
from scion.core.models import (
    Branch,
    HypothesisProposal,
    PatchFileChange,
    StepRecord,
    patch_file_changes,
)


BRANCH_FOLLOWUP_POLICY_VIOLATION = "branch_followup_policy_violation"
WEAK_POSITIVE_FOLLOWUP_REQUIRES_BRIDGE = (
    "weak_positive_followup_requires_branch_local_bridge"
)

_BRIDGE_SIGNAL_TERMS = (
    "weak signal",
    "weak-positive",
    "weak positive",
    "prior signal",
    "observed signal",
    "screening signal",
)
_BRIDGE_CONTINUITY_TERMS = (
    "branch-local",
    "same branch",
    "prior",
    "previous",
    "existing mechanism",
    "old mechanism",
    "follow-up",
    "follow up",
    "preserve",
    "retaining",
    "bridge",
)
_BRIDGE_RATIONALE_TERMS = (
    "cannot directly",
    "can't directly",
    "unable to directly",
    "why",
    "because",
    "tests",
    "test",
    "diagnostic",
    "failure",
)


@dataclass(frozen=True)
class BranchFollowupCheck:
    allowed: bool
    reason: str = ""
    prior_mechanism_ids: tuple[str, ...] = ()
    proposed_mechanism_ids: tuple[str, ...] = ()
    prior_touched_files: tuple[str, ...] = ()
    branch_created_files: tuple[str, ...] = ()
    target_file: str = ""

    @property
    def detail(self) -> str:
        if self.allowed:
            return ""
        return "; ".join(
            (
                f"{BRANCH_FOLLOWUP_POLICY_VIOLATION}: {self.reason}",
                "required=branch_local_continuation_or_explicit_bridge",
                f"prior_mechanism_ids={_join_or_none(self.prior_mechanism_ids)}",
                f"proposed_mechanism_ids={_join_or_none(self.proposed_mechanism_ids)}",
                f"prior_touched_files={_join_or_none(self.prior_touched_files)}",
                f"branch_created_files={_join_or_none(self.branch_created_files)}",
                f"target_file={self.target_file or 'none'}",
            )
        )

    def structured_rejection(self) -> dict[str, Any]:
        if self.allowed:
            return {}
        return {
            "source": "branch_followup_policy",
            "gate_name": "weak_positive_followup",
            "failure_code": BRANCH_FOLLOWUP_POLICY_VIOLATION,
            "agent_block_reason": "agent_quality_blocked",
            "reason": self.reason,
            "retry_constraint": (
                "For this weak-positive branch, rewrite as a branch-local "
                "continuation: reuse or explicitly reference a prior mechanism "
                "id, prior target/touched file, or branch-created helper; if "
                "changing target or mechanism family, explain which prior weak "
                "signal is preserved, which branch-local failure is being "
                "tested, and why the prior mechanism cannot be directly refined."
            ),
            "prior_mechanism_ids": list(self.prior_mechanism_ids),
            "proposed_mechanism_ids": list(self.proposed_mechanism_ids),
            "prior_touched_files": list(self.prior_touched_files),
            "branch_created_files": list(self.branch_created_files),
            "target_file": self.target_file,
        }


def build_branch_followup_policy(
    branch: Branch,
    steps: Sequence[StepRecord],
) -> dict[str, Any]:
    """Return prompt-facing follow-up policy for active weak-positive branches."""
    if not _is_weak_positive_followup(branch):
        return {}
    branch_steps = _branch_steps(branch, steps)
    return _drop_empty(
        {
            "schema_version": "branch_followup_policy.v1",
            "taint": "proposal_guidance",
            "decision_input_policy": "excluded_from_decision_features",
            "source": "research_process_guidance",
            "guidance_ref": "branch_followup_policy.research_process_guidance",
            "guidance_schema_key": "research_process_guidance",
            "mode": "weak_positive_branch_local_followup",
            "default_action": "continue_branch_local_refinement",
            "allowed_continuations": [
                "refine_prior_mechanism_ids",
                "reuse_prior_target_or_touched_files",
                "use_branch_created_helpers",
                "adjust_trigger_schedule_composition_budget_allocation_or_activation",
            ],
            "research_process_guidance": {
                "principle": (
                    "weak_positive_followups_are_allowed_as_bounded_research_probes"
                ),
                "not_a_hard_stop": True,
                "followup_should_change_at_least_one": [
                    "trigger_or_activation_condition",
                    "budget_or_schedule",
                    "composition_or_integration_point",
                    "observability_or_expected_telemetry",
                    "loss_guard_or_no_op_condition",
                ],
                "must_state": [
                    "which_prior_signal_or_checkpoint_is_preserved",
                    "which prior loss, tie pattern, or missing effect is being tested",
                    "what evidence would justify another same-branch follow-up",
                    "what evidence would justify switching to a clean branch",
                ],
                "do_not": [
                    "repeat_the_same_mechanism_without_a_new_evidence_plan",
                    "treat_preview_or_tool_observations_as_promotion_evidence",
                ],
            },
            "bridge_required_when": [
                "changing_target_file",
                "adding_or_renaming_mechanism_family",
                "moving_work_to_a_new_module",
            ],
            "bridge_must_explain": [
                "which_prior_weak_signal_is_preserved",
                "which_branch_local_failure_is_being_tested",
                "why_the_prior_mechanism_cannot_be_directly_refined",
            ],
            "prior_mechanism_ids": list(
                branch_continuation_mechanism_ids(branch, branch_steps)
            ),
            "prior_touched_files": list(branch_touched_files(branch, branch_steps)),
            "branch_created_files": list(branch_created_files(branch, branch_steps)),
        }
    )


def render_branch_followup_policy(policy: Mapping[str, Any]) -> str:
    if not policy:
        return ""
    return (
        "This policy is proposal guidance for the current branch only; it is "
        "not promotion Decision input.\n"
        f"{json.dumps(dict(policy), indent=2, sort_keys=True, default=str)}"
    )


def validate_weak_positive_followup_hypothesis(
    branch: Branch | None,
    hypothesis: HypothesisProposal | None,
    *,
    step_history: Sequence[StepRecord] | None = None,
) -> BranchFollowupCheck:
    """Block unbridged weak-positive follow-ups that abandon branch lineage."""
    if branch is None or hypothesis is None or not _is_weak_positive_followup(branch):
        return BranchFollowupCheck(allowed=True)
    branch_steps = _branch_steps(branch, step_history or ())
    prior_mechanisms = branch_continuation_mechanism_ids(branch, branch_steps)
    prior_touched = branch_touched_files(branch, branch_steps)
    created = branch_created_files(branch, branch_steps)
    if not (prior_mechanisms or prior_touched or created):
        return BranchFollowupCheck(allowed=True)

    proposed = mechanism_ids_for_repair(hypothesis)
    target = _clean_path(getattr(hypothesis, "target_file", ""))
    text = _hypothesis_text(hypothesis)
    if set(proposed) & set(prior_mechanisms):
        return BranchFollowupCheck(allowed=True)
    if target and target in set(prior_touched) | set(created):
        return BranchFollowupCheck(allowed=True)
    if _mentions_any(text, prior_mechanisms) or _mentions_any_file(text, prior_touched):
        return BranchFollowupCheck(allowed=True)
    if _mentions_any_file(text, created):
        return BranchFollowupCheck(allowed=True)
    if _has_explicit_bridge(text):
        return BranchFollowupCheck(allowed=True)
    return BranchFollowupCheck(
        allowed=False,
        reason=WEAK_POSITIVE_FOLLOWUP_REQUIRES_BRIDGE,
        prior_mechanism_ids=prior_mechanisms,
        proposed_mechanism_ids=proposed,
        prior_touched_files=prior_touched,
        branch_created_files=created,
        target_file=target,
    )


def branch_created_files(
    branch: Branch | None,
    steps: Sequence[StepRecord] | None,
    *,
    max_files: int = 8,
) -> tuple[str, ...]:
    if branch is None:
        return ()
    files: list[str] = []
    for step in _branch_steps(branch, steps or ()):
        hypothesis = getattr(step, "hypothesis", None)
        if getattr(hypothesis, "action", None) == "create_new":
            _append_unique(files, _clean_path(getattr(hypothesis, "target_file", "")))
        patch = getattr(step, "patch", None)
        if patch is None:
            continue
        if getattr(patch, "action", None) == "create":
            _append_unique(files, _clean_path(getattr(patch, "file_path", "")))
        for change in getattr(patch, "additional_changes", ()) or ():
            if isinstance(change, PatchFileChange):
                action = change.action
                path = change.file_path
            elif isinstance(change, Mapping):
                action = change.get("action")
                path = change.get("file_path")
            else:
                action = getattr(change, "action", None)
                path = getattr(change, "file_path", "")
            if action == "create":
                _append_unique(files, _clean_path(path))
    return tuple(files[:max_files])


def branch_touched_files(
    branch: Branch | None,
    steps: Sequence[StepRecord] | None,
    *,
    max_files: int = 16,
) -> tuple[str, ...]:
    if branch is None:
        return ()
    files: list[str] = []
    for step in _branch_steps(branch, steps or ()):
        hypothesis = getattr(step, "hypothesis", None)
        _append_unique(files, _clean_path(getattr(hypothesis, "target_file", "")))
        patch = getattr(step, "patch", None)
        if patch is None:
            continue
        _append_unique(files, _clean_path(getattr(patch, "file_path", "")))
        for change in getattr(patch, "additional_changes", ()) or ():
            if isinstance(change, PatchFileChange):
                path = change.file_path
            elif isinstance(change, Mapping):
                path = change.get("file_path")
            else:
                path = getattr(change, "file_path", "")
            _append_unique(files, _clean_path(path))
    return tuple(files[:max_files])


def branch_current_file_sources(
    branch: Branch | None,
    steps: Sequence[StepRecord] | None,
    *,
    max_files: int = 32,
) -> dict[str, str]:
    if branch is None:
        return {}
    sources: dict[str, str] = {}
    for step in _branch_steps(branch, steps or ()):
        patch = getattr(step, "patch", None)
        if patch is None:
            continue
        try:
            changes = patch_file_changes(patch)
        except Exception:
            changes = ()
        for change in changes:
            path = _clean_path(getattr(change, "file_path", ""))
            action = str(getattr(change, "action", "") or "")
            if not path:
                continue
            if action == "delete":
                sources.pop(path, None)
                continue
            content = getattr(change, "code_content", None)
            if action in {"create", "modify"} and isinstance(content, str):
                sources[path] = content
    return dict(list(sources.items())[:max_files])


def _is_weak_positive_followup(branch: Branch) -> bool:
    status = str(getattr(branch, "branch_code_status", "") or "")
    tier = str(getattr(branch, "last_screening_feedback_tier", "") or "")
    return status == "active_weak_positive" or tier == "weak_positive"


def _branch_steps(
    branch: Branch,
    steps: Sequence[StepRecord],
) -> tuple[StepRecord, ...]:
    return tuple(step for step in steps if step.branch_id == branch.branch_id)


def _hypothesis_text(hypothesis: HypothesisProposal) -> str:
    fields = [
        getattr(hypothesis, "hypothesis_text", ""),
        getattr(hypothesis, "target_weakness", ""),
        getattr(hypothesis, "expected_effect", ""),
        getattr(hypothesis, "no_op_condition", ""),
        getattr(hypothesis, "risk_to_higher_priority", ""),
        getattr(hypothesis, "runtime_budget_strategy", ""),
        getattr(hypothesis, "target_file", ""),
        json.dumps(getattr(hypothesis, "novelty_signature", {}) or {}, default=str),
    ]
    return " ".join(str(field or "") for field in fields).lower()


def _has_explicit_bridge(text: str) -> bool:
    haystack = str(text or "").lower()
    categories = 0
    if any(term in haystack for term in _BRIDGE_SIGNAL_TERMS):
        categories += 1
    if any(term in haystack for term in _BRIDGE_CONTINUITY_TERMS):
        categories += 1
    if any(term in haystack for term in _BRIDGE_RATIONALE_TERMS):
        categories += 1
    return categories >= 2


def _mentions_any(text: str, values: Sequence[str]) -> bool:
    haystack = str(text or "").lower()
    return any(str(value).lower() in haystack for value in values if value)


def _mentions_any_file(text: str, values: Sequence[str]) -> bool:
    haystack = str(text or "").lower()
    for value in values:
        path = _clean_path(value).lower()
        if not path:
            continue
        name = PurePosixPath(path).name.lower()
        if path in haystack or (name and name in haystack):
            return True
    return False


def _clean_path(value: Any) -> str:
    return str(value or "").replace("\\", "/").lstrip("/")


def _append_unique(items: list[str], value: str) -> None:
    if value and value not in items:
        items.append(value)


def _join_or_none(values: Sequence[str]) -> str:
    return ",".join(value for value in values if value) or "none"


def _drop_empty(value: dict[str, Any]) -> dict[str, Any]:
    return {
        key: item
        for key, item in value.items()
        if item not in (None, "", [], {}, ())
    }


__all__ = [
    "BRANCH_FOLLOWUP_POLICY_VIOLATION",
    "WEAK_POSITIVE_FOLLOWUP_REQUIRES_BRIDGE",
    "BranchFollowupCheck",
    "branch_created_files",
    "branch_current_file_sources",
    "branch_touched_files",
    "build_branch_followup_policy",
    "render_branch_followup_policy",
    "validate_weak_positive_followup_hypothesis",
]
