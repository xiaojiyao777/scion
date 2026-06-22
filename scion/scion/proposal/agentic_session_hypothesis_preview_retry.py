"""Preview-gate retry feedback helpers for agentic hypothesis sessions."""
from __future__ import annotations

from typing import Any, Mapping

from scion.core.models import HypothesisProposal
from scion.proposal.agentic_models import AgenticFailureCategory
from scion.proposal.agentic_utils import _drop_empty_dict, _limit_string
from scion.proposal.hypothesis_telemetry_retry import (
    expected_telemetry_retry_feedback as _expected_telemetry_retry_feedback,
)
from scion.proposal.agentic_session_hypothesis_schema_retry import (
    _hypothesis_retry_anchor,
    _schema_retry_protected_identity,
)
from scion.proposal.tools import ProposalObservation


def _hypothesis_preview_retry_feedback(
    preview_observations: list[ProposalObservation],
    *,
    detail: str,
    attempt: int,
    previous_hypothesis: HypothesisProposal,
) -> dict[str, Any] | None:
    schema_observation = _latest_tool_observation(
        preview_observations,
        "proposal.schema_preview",
    )
    if schema_observation is None or schema_observation.is_error:
        return None
    payload = schema_observation.structured_payload
    if not isinstance(payload, Mapping):
        return None
    hypothesis = payload.get("hypothesis")
    if not isinstance(hypothesis, Mapping):
        return None
    target_action_feedback = _target_action_permission_preview_retry_feedback(
        preview_observations,
        hypothesis,
        detail=detail,
        attempt=attempt,
        previous_hypothesis=previous_hypothesis,
    )
    if target_action_feedback is not None:
        return target_action_feedback
    launch_required_feedback = _launch_focus_required_mechanism_retry_feedback(
        hypothesis,
        detail=detail,
        attempt=attempt,
    )
    if launch_required_feedback is not None:
        return launch_required_feedback
    same_mechanism_feedback = _same_mechanism_preview_retry_feedback(
        hypothesis,
        detail=detail,
        attempt=attempt,
    )
    if same_mechanism_feedback is not None:
        return same_mechanism_feedback
    novelty_feedback = _novelty_signature_preview_retry_feedback(
        hypothesis,
        detail=detail,
        attempt=attempt,
        previous_hypothesis=previous_hypothesis,
    )
    if novelty_feedback is not None:
        return novelty_feedback
    telemetry = hypothesis.get("expected_telemetry_contract")
    if not isinstance(telemetry, Mapping):
        return None
    problem_telemetry = hypothesis.get("problem_expected_telemetry_preview")
    if not isinstance(problem_telemetry, Mapping):
        problem_telemetry = {}
    c11_detail = _failed_schema_check_detail(
        hypothesis,
        "C11_expected_telemetry",
    )
    telemetry_detail = str(
        telemetry.get("detail_full") or telemetry.get("detail") or ""
    ).strip()
    problem_telemetry_failed = problem_telemetry.get("passed") is False
    if (
        bool(telemetry.get("passed")) is not False
        and not c11_detail
        and not problem_telemetry_failed
    ):
        return None
    if (
        "C11_expected_telemetry" not in (c11_detail or detail)
        and str(problem_telemetry.get("failure_code") or "")
        != "C11_expected_telemetry"
    ):
        return None

    preserve_hypothesis = _hypothesis_retry_anchor(previous_hypothesis)
    protected_identity = _schema_retry_protected_identity(preserve_hypothesis)
    return _expected_telemetry_retry_feedback(
        hypothesis,
        telemetry,
        problem_telemetry,
        detail=detail,
        attempt=attempt,
        c11_detail=c11_detail,
        telemetry_detail=telemetry_detail,
        preserve_hypothesis=preserve_hypothesis,
        protected_identity=protected_identity,
    )


def _target_action_permission_preview_retry_feedback(
    preview_observations: list[ProposalObservation],
    hypothesis: Mapping[str, Any],
    *,
    detail: str,
    attempt: int,
    previous_hypothesis: HypothesisProposal,
) -> dict[str, Any] | None:
    guard = hypothesis.get("target_action_guard")
    if not isinstance(guard, Mapping) or guard.get("passed") is not False:
        guard = _target_permission_guard_from_observations(preview_observations)
    if not isinstance(guard, Mapping) or guard.get("passed") is not False:
        return None
    failure_code = str(
        guard.get("failure_code")
        or guard.get("reason")
        or ""
    ).strip()
    if failure_code != "existing_file_create_new_rejected":
        return None

    anchor = _hypothesis_retry_anchor(previous_hypothesis)
    corrected_anchor = dict(anchor)
    corrected_anchor["action"] = "modify"
    target_file = str(
        guard.get("target_file")
        or anchor.get("target_file")
        or getattr(previous_hypothesis, "target_file", "")
        or ""
    ).strip()
    if target_file:
        corrected_anchor["target_file"] = target_file
    protected_identity = _schema_retry_protected_identity(corrected_anchor)
    protected_identity.pop("action", None)
    protected_identity["target_action_repair"] = {
        "invalid_file_action": "create_new",
        "required_file_action": "modify",
        "target_file": target_file,
    }
    return _drop_empty_dict(
        {
            "attempt": attempt,
            "attempt_kind": "target_action_permission_repair",
            "repair_classification": "target_action_permission_repair",
            "source": "hypothesis_preview_target_action_guard",
            "gate_name": "proposal.schema_preview",
            "failure_code": "existing_file_create_new_rejected",
            "check": "target_action_permission",
            "failure_category": AgenticFailureCategory.CONTRACT_BOUNDARY_FAILURE.value,
            "reason": _limit_string(
                str(guard.get("detail") or guard.get("reason") or "") or detail,
                1000,
            ),
            "target_file": target_file,
            "requested_action": "create_new",
            "required_action": "modify",
            "source_digest": guard.get("source_digest"),
            "allowed_file_action": {
                "action": "modify",
                "edit_intent": "exact_replace",
                "source_digest": guard.get("source_digest"),
                "target_file": target_file,
            },
            "allowed_mechanism_semantics": (
                "The mechanism-level hypothesis may still describe adding or "
                "integrating a new mechanism inside the existing target file. "
                "Only the file-level action must change: existing files require "
                "action=modify with typed exact_replace/source_digest."
            ),
            "forbidden_preservation_fields": {
                "action": "Do not preserve invalid file action create_new for an existing target_file.",
            },
            "preserve_hypothesis": corrected_anchor,
            "protected_identity": protected_identity,
            "final_task": (
                "Rewrite the hypothesis for the same target_file with "
                "file-level action=modify. Keep the mechanism id/intent if it "
                "is still the same research idea, but do not keep "
                "action=create_new for an existing file."
            ),
            "retry_constraint": (
                "Target/action repair: set hypothesis action to modify for the "
                "same existing target_file and plan code as typed exact_replace "
                "using source_digest. Preserve target_file and mechanism_changes "
                "ids/change_types unless another preview explicitly rejects "
                "them. Do not preserve the invalid file-level action=create_new. "
                "Mechanism-level wording may say add or integrate a new "
                "mechanism inside that existing file."
            ),
        }
    )


def _target_permission_guard_from_observations(
    preview_observations: list[ProposalObservation],
) -> Mapping[str, Any] | None:
    observation = _latest_tool_observation(
        preview_observations,
        "proposal.target_permission_preview",
    )
    if observation is None or observation.is_error:
        return None
    payload = observation.structured_payload
    if not isinstance(payload, Mapping) or payload.get("passed") is not False:
        return None
    issues = payload.get("issues")
    if not isinstance(issues, list):
        return None
    if not any(
        "existing_file_create_new_rejected" in str(issue)
        for issue in issues
    ):
        return None
    requested = payload.get("requested")
    if not isinstance(requested, Mapping):
        requested = {}
    return {
        "passed": False,
        "reason": "existing_file_create_new_rejected",
        "detail": next(
            (
                str(issue)
                for issue in issues
                if "existing_file_create_new_rejected" in str(issue)
            ),
            "existing_file_create_new_rejected",
        ),
        "target_file": requested.get("target_file"),
    }


def _launch_focus_required_mechanism_retry_feedback(
    hypothesis: Mapping[str, Any],
    *,
    detail: str,
    attempt: int,
) -> dict[str, Any] | None:
    guard = hypothesis.get("launch_research_focus_required_mechanism_guard")
    if not isinstance(guard, Mapping):
        return None
    if guard.get("passed") is not False:
        return None
    if (
        str(guard.get("failure_code") or "").strip()
        != "launch_research_focus_required_mechanism"
    ):
        return None

    required_ids = [
        str(item).strip()
        for item in (guard.get("required_mechanism_ids") or ())
        if str(item).strip()
    ]
    candidate_ids = [
        str(item).strip()
        for item in (guard.get("candidate_mechanism_ids") or ())
        if str(item).strip()
    ]
    target_file = str(guard.get("candidate_target_file") or "").strip()
    return _drop_empty_dict(
        {
            "attempt": attempt,
            "attempt_kind": "launch_focus_required_mechanism_repair",
            "repair_classification": "launch_focus_required_mechanism_repair",
            "source": "hypothesis_preview_launch_focus_guard",
            "gate_name": "proposal.schema_preview",
            "failure_code": "launch_research_focus_required_mechanism",
            "check": "launch_research_focus_required_mechanism",
            "failure_category": AgenticFailureCategory.CONTRACT_BOUNDARY_FAILURE.value,
            "reason": _limit_string(
                str(guard.get("reason") or "") or detail,
                1200,
            ),
            "required_mechanism_ids": required_ids,
            "candidate_mechanism_ids": candidate_ids,
            "candidate_target_file": target_file,
            "candidate_change_locus": guard.get("candidate_change_locus"),
            "allowed_repair_shape": {
                "mechanism_changes": [
                    {"id": mechanism_id, "change_type": "modify"}
                    for mechanism_id in required_ids
                ],
                "target_file": target_file,
            },
            "protected_identity": {
                "required_mechanism_ids": required_ids,
                "candidate_mechanism_ids": candidate_ids,
                "target_file": target_file,
            },
            "final_task": (
                "Rewrite the hypothesis around the prepared launch-focus "
                "required mechanism id. This launch-focus repair may replace "
                "the previous mechanism id instead of preserving it."
            ),
            "retry_constraint": (
                guard.get("retry_constraint")
                or "Use one required_mechanism_ids value exactly in "
                "mechanism_changes and align expected telemetry refs to that "
                "same mechanism id."
            ),
        }
    )


def _same_mechanism_preview_retry_feedback(
    hypothesis: Mapping[str, Any],
    *,
    detail: str,
    attempt: int,
) -> dict[str, Any] | None:
    guard = hypothesis.get("branch_continuation_guard")
    if not isinstance(guard, Mapping):
        return None
    if guard.get("passed") is not False:
        return None
    if str(guard.get("failure_code") or "") != "same_mechanism_only_violation":
        return None
    protected_ids = [
        str(item).strip()
        for item in (guard.get("protected_mechanism_ids") or ())
        if str(item).strip()
    ]
    proposed_ids = [
        str(item).strip()
        for item in (guard.get("proposed_mechanism_ids") or ())
        if str(item).strip()
    ]
    allowed_ids = [
        str(item).strip()
        for item in (guard.get("allowed_mechanism_ids") or protected_ids)
        if str(item).strip()
    ]
    allowed_actions = [
        str(item).strip()
        for item in (guard.get("allowed_actions") or ())
        if str(item).strip()
    ]
    return _drop_empty_dict(
        {
            "attempt": attempt,
            "attempt_kind": "schema_accounting_repair",
            "repair_classification": "branch_followup_schema_repair",
            "source": "hypothesis_preview_gate",
            "gate_name": "proposal.schema_preview",
            "failure_code": "same_mechanism_only_violation",
            "check": "same_mechanism_only_branch_guard",
            "failure_category": AgenticFailureCategory.CONTRACT_BOUNDARY_FAILURE.value,
            "reason": _limit_string(
                str(guard.get("reason") or "") or detail,
                1000,
            ),
            "branch_followup_policy": guard.get("branch_followup_policy"),
            "hypothesis_generation_mode": guard.get("hypothesis_generation_mode"),
            "protected_mechanism_ids": protected_ids,
            "allowed_mechanism_ids": allowed_ids,
            "proposed_mechanism_ids": proposed_ids,
            "forbidden_mechanism_policy": guard.get(
                "forbidden_mechanism_policy"
            ),
            "allowed_actions": allowed_actions,
            "allowed_repair_shape": guard.get("allowed_repair_shape"),
            "candidate_routing": guard.get("candidate_routing"),
            "proposal_failure_accounting": guard.get(
                "proposal_failure_accounting"
            ),
            "clean_fork_signal": guard.get("clean_fork_signal"),
            "protected_identity": {
                "protected_mechanism_ids": protected_ids,
                "allowed_mechanism_ids": allowed_ids,
                "allowed_actions": allowed_actions,
            },
            "final_task": (
                "Rewrite the hypothesis as a same-mechanism follow-up on a "
                "protected id. Do not introduce unrelated mechanism ids."
            ),
            "retry_constraint": (
                "Use only protected_mechanism_ids in mechanism_changes and "
                "keep the work to tune, integrate, repair, parameterize, or "
                "telemetry wiring within that protected mechanism. If the "
                "intended idea is a new mechanism, stop this branch attempt "
                "and use a clean branch/fork before generation. Treat that as "
                "a branch-routing signal, not as a code or screening failure."
            ),
        }
    )


def _novelty_signature_preview_retry_feedback(
    hypothesis: Mapping[str, Any],
    *,
    detail: str,
    attempt: int,
    previous_hypothesis: HypothesisProposal,
) -> dict[str, Any] | None:
    guidance = hypothesis.get("novelty_signature_guidance")
    if not isinstance(guidance, Mapping):
        return None
    missing_fields = [
        str(field).strip()
        for field in guidance.get("missing_fields") or ()
        if str(field).strip()
    ]
    if not missing_fields:
        return None
    repair_template = guidance.get("repair_template")
    if not isinstance(repair_template, Mapping):
        return None
    anchor = _hypothesis_retry_anchor(previous_hypothesis)
    return _drop_empty_dict(
        {
            "attempt": attempt,
            "source": "hypothesis_preview_gate",
            "gate_name": "proposal.schema_preview",
            "failure_code": "novelty_signature_missing_fields",
            "check": "C10_novelty",
            "failure_category": AgenticFailureCategory.CONTRACT_BOUNDARY_FAILURE.value,
            "reason": _limit_string(
                str(guidance.get("detail") or "") or detail,
                1000,
            ),
            "missing_fields": missing_fields,
            "required_fields": list(guidance.get("signature_fields") or ()),
            "repair_template": repair_template,
            "required_template": repair_template.get("required_template"),
            "mechanism_id_consistency": repair_template.get(
                "mechanism_id_consistency"
            ),
            "preserve_hypothesis": anchor,
            "protected_identity": _schema_retry_protected_identity(anchor),
            "retry_constraint": (
                "Repair only novelty_signature/schema fields named by the C10 "
                "template. Preserve the prior action, target_file, "
                "mechanism_changes ids/change_types, and telemetry activation "
                "mechanism refs; do not switch mechanisms or targets for a "
                "C10 missing-fields retry. If a strategy is unchanged, state "
                "unchanged and name the active solver map or baseline component "
                "used as the reference."
            ),
        }
    )


def _latest_tool_observation(
    observations: list[ProposalObservation],
    tool_name: str,
) -> ProposalObservation | None:
    for observation in reversed(observations):
        if observation.tool_name == tool_name:
            return observation
    return None


def _failed_schema_check_detail(
    section: Mapping[str, Any],
    check_name: str,
) -> str:
    checks = section.get("checks")
    if not isinstance(checks, list):
        return ""
    for check in checks:
        if not isinstance(check, Mapping):
            continue
        if str(check.get("name") or "") != check_name:
            continue
        if bool(check.get("passed")):
            continue
        detail = str(check.get("detail") or "").strip()
        return f"{check_name}: {detail}" if detail else check_name
    return ""


def _compact_preview_list(
    value: Any,
    *,
    limit: int,
    max_chars: int,
) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    return [
        text
        for text in (
            _limit_string(str(item).strip(), max_chars)
            for item in list(value)[: max(0, limit)]
        )
        if text
    ]
