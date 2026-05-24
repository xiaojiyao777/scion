"""Shared helpers for explore-step execution."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Mapping, Optional

from scion.core.models import HypothesisProposal, ProtocolResult, StepRecord, VerificationResult
from scion.core.step_result import StepResult


from scion.core.verification_call import run_verification_gate

logger = logging.getLogger(__name__)

_AGENT_QUALITY_BLOCKED = "agent_quality_blocked"
_PROPOSAL_PREMISE_CONTRADICTED = "proposal_premise_contradicted"
_AGENT_GROUNDING_FAILURE = "agent_grounding_failure"
_ALGORITHM_SMOKE_FAILURE = "algorithm_smoke_failure"
_PROPOSAL_ACTIVATION_DIAGNOSTIC = "proposal_activation_diagnostic"
_ACTIVATION_NOT_OBSERVED_DIAGNOSTIC = "activation_not_observed_diagnostic"
_DUPLICATE_MECHANISM = "duplicate_mechanism"
_MECHANISM_NOVELTY_REJECTED = "mechanism_novelty_rejected"
_AGENTIC_BUDGET_CONTROL = "agentic_budget_control"
_AGENTIC_SESSION_TIMEOUT = "agentic_session_timeout"


def _proposal_failure_hypothesis(detail: str) -> HypothesisProposal:
    return HypothesisProposal(
        hypothesis_text=f"Proposal generation failed: {detail}",
        change_locus="proposal",
        action="create_new",
        target_file=None,
        predicted_direction="exploratory",
        target_weakness="proposal_generation",
        expected_effect="no candidate generated",
    )


def _is_agent_quality_blocked_detail(detail: str | None) -> bool:
    text = str(detail or "")
    text_lower = text.lower()
    if _ACTIVATION_NOT_OBSERVED_DIAGNOSTIC in text_lower:
        return False
    return (
        _AGENT_QUALITY_BLOCKED in text
        or _PROPOSAL_PREMISE_CONTRADICTED in text
        or _AGENT_GROUNDING_FAILURE in text
        or _ALGORITHM_SMOKE_FAILURE in text
        or _PROPOSAL_ACTIVATION_DIAGNOSTIC in text
        or _DUPLICATE_MECHANISM in text
        or _MECHANISM_NOVELTY_REJECTED in text
        or "premise_check=duplicate" in text
        or "premise_check=contradicted" in text
        or "algorithm smoke did not pass" in text_lower
        or "runtime_smoke.telemetry_guard" in text_lower
    )


def _proposal_session_ref_primary_failure(
    ref: Mapping[str, Any] | None,
) -> Mapping[str, Any]:
    if not isinstance(ref, Mapping):
        return {}
    primary = ref.get("primary_failure")
    if isinstance(primary, Mapping):
        return primary
    return {}


def _proposal_session_ref_failure_code(ref: Mapping[str, Any] | None) -> str:
    if not isinstance(ref, Mapping):
        return ""
    primary = _proposal_session_ref_primary_failure(ref)
    for value in (
        primary.get("code"),
        primary.get("reason"),
        ref.get("failure_code"),
        ref.get("failure_category"),
    ):
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _proposal_session_ref_is_agent_quality_blocked(
    ref: Mapping[str, Any] | None,
) -> bool:
    if not isinstance(ref, Mapping):
        return False
    primary = _proposal_session_ref_primary_failure(ref)
    combined = " ".join(
        str(value or "")
        for value in (
            primary.get("stage"),
            primary.get("reason"),
            primary.get("category"),
            primary.get("code"),
            ref.get("agent_block_reason"),
            ref.get("failure_code"),
            ref.get("failure_category"),
            ref.get("termination_reason"),
        )
    )
    return _is_agent_quality_blocked_detail(combined)


def _agent_quality_failure_detail(
    default_detail: str | None,
    ref: Mapping[str, Any] | None,
) -> str:
    primary = _proposal_session_ref_primary_failure(ref)
    code = _proposal_session_ref_failure_code(ref) or _AGENT_QUALITY_BLOCKED
    category = str(primary.get("category") or ref.get("failure_category") or "").strip() if isinstance(ref, Mapping) else ""
    reason = str(primary.get("reason") or ref.get("termination_reason") or "").strip() if isinstance(ref, Mapping) else ""
    detail = str(primary.get("detail") or default_detail or "").strip()
    parts = [_AGENT_QUALITY_BLOCKED, code]
    if category and category != code:
        parts.append(category)
    prefix = ":".join(parts)
    if reason and reason not in {code, category}:
        prefix = f"{reason}: {prefix}"
    if detail:
        return f"{prefix}: {detail}"
    return prefix


def _is_agentic_control_timeout_detail(detail: str | None) -> bool:
    text = str(detail or "").lower()
    return (
        "agentic_budget_control" in text
        or "agentic_proposal:session_timeout" in text
        or ("max_wall_time_sec" in text and "agentic" in text)
        or "contract preview skipped by agentic session_timeout/budget control" in text
        or (
            "session_timeout" in text
            and ("agentic" in text or "budget control" in text)
        )
        or (
            "insufficient wall-time reserve" in text
            and "agentic" in text
        )
    )


def _proposal_failure_stage(detail: str | None, default: str) -> str:
    if _is_agent_quality_blocked_detail(detail):
        return _AGENT_QUALITY_BLOCKED
    if _is_agentic_control_timeout_detail(detail):
        return _AGENTIC_BUDGET_CONTROL
    return default


def _proposal_failure_reason(detail: str | None, default: str) -> str:
    if _is_agent_quality_blocked_detail(detail):
        return _AGENT_QUALITY_BLOCKED
    if _is_agentic_control_timeout_detail(detail):
        return _AGENTIC_SESSION_TIMEOUT
    return default


def _is_candidate_scoped_heavy_failure(
    hypothesis: HypothesisProposal,
    *,
    problem_spec: Any | None,
) -> bool:
    """Return whether a heavy failure should retire only this candidate.

    Top-level solver-design surfaces are problem-object boundaries, not narrow
    mechanisms. A single invalid implementation should not globally blacklist
    the boundary and push later proposal rounds back to component surfaces.
    """
    surface = _surface_for_hypothesis(problem_spec, hypothesis)
    if surface is None:
        return False
    kind = str(getattr(surface, "kind", "") or "").strip().lower()
    role = str(getattr(getattr(surface, "algorithm", None), "role", "") or "").lower()
    return (
        kind in {"solver_design", "solver_algorithm"}
        or "solver_design" in role
        or "solver_algorithm" in role
    )


def _surface_for_hypothesis(
    problem_spec: Any | None,
    hypothesis: HypothesisProposal,
) -> Any | None:
    if problem_spec is None:
        return None
    target_name = str(getattr(hypothesis, "change_locus", "") or "").strip()
    if not target_name:
        return None
    for surface in getattr(problem_spec, "research_surfaces", []) or []:
        if str(getattr(surface, "name", "") or "").strip() == target_name:
            return surface
    return None


@dataclass(frozen=True)
class _VerificationOutcome:
    step_result: Optional[StepResult]
    code_hash: str
    verification_result: VerificationResult
