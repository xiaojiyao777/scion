"""Screening and holdout row payload builders."""

from __future__ import annotations

from typing import Any, Mapping

from scion.core.models import StepRecord
from scion.proposal.tools.feedback.attribution import _surface_runtime_attribution_payload
from scion.proposal.tools.feedback.scope import _feedback_step_provenance
from scion.proposal.tools.feedback.stats import _eval_stats_payload, _screening_pair_stats
from scion.proposal.tools.models import HoldoutExposure, ProposalExposureLevel
from scion.proposal.tools.utils import _model_payload, _stage_value, _strip_forbidden_value


def _screening_step_payload(
    step: StepRecord,
    *,
    provenance: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    protocol = step.protocol_result
    assert protocol is not None
    stats = protocol.stats
    return {
        "round_num": step.round_num,
        "branch_id": step.branch_id,
        "surface": step.hypothesis.change_locus,
        "action": step.hypothesis.action,
        "target_file": step.hypothesis.target_file,
        "gate_outcome": protocol.gate_outcome,
        "reason_codes": list(protocol.reason_codes),
        "stats": _eval_stats_payload(stats),
        "screening_win_rate_scope": "case_level_gate",
        "screening_case_win_rate": stats.win_rate,
        "screening_gate_win_rate": stats.win_rate,
        **_screening_pair_stats(protocol),
        "candidate_runtime_failure_categories": dict(
            protocol.candidate_runtime_failure_categories or {}
        ),
        "candidate_first_runtime_failure": _strip_forbidden_value(
            protocol.candidate_first_runtime_failure or {}
        ),
        "candidate_operator_attempts": protocol.candidate_operator_attempts,
        "candidate_operator_accepted": protocol.candidate_operator_accepted,
        "candidate_operator_errors": protocol.candidate_operator_errors,
        "candidate_operator_invalid_outputs": (
            protocol.candidate_operator_invalid_outputs
        ),
        "candidate_policy_errors": protocol.candidate_policy_errors,
        "candidate_construction_errors": protocol.candidate_construction_errors,
        "candidate_portfolio_errors": protocol.candidate_portfolio_errors,
        "candidate_runtime_stop_reasons": dict(
            protocol.candidate_runtime_stop_reasons or {}
        ),
        "candidate_surface_runtime_summary": _strip_forbidden_value(
            protocol.candidate_surface_runtime_summary or {}
        ),
        "candidate_surface_runtime_attribution": _surface_runtime_attribution_payload(
            step
        ),
        "pattern_summary": _model_payload(protocol.pattern_summary),
        "case_feedback": [
            _model_payload(feedback) for feedback in (protocol.case_feedback or ())[:6]
        ],
        "metrics_file_ref_exposed": False,
        "provenance": dict(provenance or _feedback_step_provenance(
            step,
            boundary_surfaces=(),
            role="screening_evidence",
        )),
    }
def _holdout_step_payload(
    step: StepRecord,
    exposure: HoldoutExposure,
    level: ProposalExposureLevel,
) -> dict[str, Any]:
    protocol = step.protocol_result
    assert protocol is not None
    payload: dict[str, Any] = {
        "round_num": step.round_num,
        "branch_id": step.branch_id,
        "surface": step.hypothesis.change_locus,
        "stage": _stage_value(protocol.stage),
        "exposure_level": level.value,
        "gate_outcome": protocol.gate_outcome,
        "reason_codes": list(protocol.reason_codes),
        "candidate_runtime_failure_categories": dict(
            protocol.candidate_runtime_failure_categories or {}
        ),
        "candidate_first_runtime_failure": _strip_forbidden_value(
            protocol.candidate_first_runtime_failure or {}
        ),
        "candidate_operator_attempts": protocol.candidate_operator_attempts,
        "candidate_operator_accepted": protocol.candidate_operator_accepted,
        "candidate_operator_errors": protocol.candidate_operator_errors,
        "candidate_operator_invalid_outputs": (
            protocol.candidate_operator_invalid_outputs
        ),
        "candidate_policy_errors": protocol.candidate_policy_errors,
        "candidate_construction_errors": protocol.candidate_construction_errors,
        "candidate_portfolio_errors": protocol.candidate_portfolio_errors,
        "candidate_runtime_stop_reasons": dict(
            protocol.candidate_runtime_stop_reasons or {}
        ),
        "candidate_surface_runtime_summary": _strip_forbidden_value(
            protocol.candidate_surface_runtime_summary or {}
        ),
        "metrics_file_ref_exposed": False,
        "case_ids_exposed": False,
        "pair_feedback_exposed": False,
    }
    if exposure == HoldoutExposure.AGGREGATE:
        payload["stats"] = _eval_stats_payload(protocol.stats)
    return payload

__all__ = [
    "_screening_step_payload",
    "_holdout_step_payload",
]
