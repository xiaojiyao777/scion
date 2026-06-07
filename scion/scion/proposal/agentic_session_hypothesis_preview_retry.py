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
