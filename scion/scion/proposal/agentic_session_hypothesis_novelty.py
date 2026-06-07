"""Hypothesis-phase mechanism novelty diagnostics and retries."""
from __future__ import annotations

import sys
from typing import Any, Mapping

from scion.proposal.agentic_session_common import *


class AgenticSessionHypothesisNoveltyMixin:
    def _solver_design_semantic_rejection_or_retry(
            self,
            *,
            request: AgenticProposalRequest,
            session_id: str,
            state: AgenticProposalSessionState,
            tool_context: ProposalToolContext | None,
            hypothesis: HypothesisProposal,
            observations: list[ProposalObservation],
            evidence: list[AgenticEvidenceRef],
            semantic_rejections: list[Mapping[str, Any]],
            attempt: int,
        ) -> AgenticProposalOutput | None:
            if tool_context is None or not _is_solver_design_hypothesis(hypothesis):
                return None
            grounding_observations = self._run_solver_design_grounding_tools(
                tool_context,
                state,
                observations,
                selection_source="solver_design_grounding_required",
                hypothesis=hypothesis,
            )
            observations.extend(grounding_observations)
            evidence.extend(_evidence_from_observations(grounding_observations))
            grounding_error = _missing_solver_design_grounding_error(
                observations,
                hypothesis=hypothesis,
                context=tool_context,
            )
            if grounding_error is not None:
                output = self._failed_output(
                    request=request,
                    session_id=session_id,
                    status=AgenticProposalStatus.FAILED,
                    termination_reason=AgenticTerminationReason.HYPOTHESIS_GENERATION_FAILED,
                    detail=grounding_error,
                    evidence_used=tuple(evidence),
                    failure_category=AgenticFailureCategory.CONTRACT_BOUNDARY_FAILURE,
                )
                state.status = output.status
                state.note(
                    AgenticProposalPhase.FINALIZE,
                    "Session failed closed before solver_design hypothesis approval because active solver grounding was missing.",
                    metadata={"detail": grounding_error, "attempt": attempt},
                )
                return self._persist(output, state)

            result = _mechanism_novelty_gate().evaluate(
                hypothesis,
                context=tool_context,
                observations=observations,
            )
            if result is None:
                return None
            if not result.is_hard_block:
                _record_mechanism_novelty_diagnostic(
                    state,
                    hypothesis=hypothesis,
                    result=result,
                    attempt=attempt,
                    observations=observations,
                )
                return None
            parity_feedback = _mechanism_novelty_gate_prompt_parity_feedback(
                result,
                getattr(state, "_latest_hypothesis_prompt_manifest", None),
                attempt=attempt,
            )
            if parity_feedback is not None:
                if len(semantic_rejections) < _MAX_HYPOTHESIS_SEMANTIC_RETRIES:
                    semantic_rejections.append(parity_feedback)
                    state.note(
                        AgenticProposalPhase.DRAFT_HYPOTHESIS,
                        "Mechanism novelty gate facts were not visible in the hypothesis prompt; retrying with gate/prompt parity feedback.",
                        metadata={
                            "attempt": attempt,
                            "failure_code": parity_feedback.get("failure_code"),
                            "fact_packet_digest": parity_feedback.get(
                                "fact_packet_digest"
                            ),
                            "prompt_fact_packet_digest": parity_feedback.get(
                                "prompt_fact_packet_digest"
                            ),
                        },
                    )
                    return None
                detail = str(parity_feedback.get("reason") or "")
                _record_failure_ledger_entry(
                    state,
                    phase=AgenticProposalPhase.DRAFT_HYPOTHESIS,
                    category=AgenticFailureCategory.CONTRACT_BOUNDARY_FAILURE,
                    detail=detail,
                    source="mechanism_novelty_gate_prompt_parity",
                    attempt=attempt,
                    failure_code=str(parity_feedback.get("failure_code") or ""),
                )
                output = self._failed_output(
                    request=request,
                    session_id=session_id,
                    status=AgenticProposalStatus.FAILED,
                    termination_reason=AgenticTerminationReason.HYPOTHESIS_GENERATION_FAILED,
                    detail=detail,
                    evidence_used=tuple(evidence),
                    failure_category=AgenticFailureCategory.CONTRACT_BOUNDARY_FAILURE,
                )
                state.status = output.status
                state.note(
                    AgenticProposalPhase.FINALIZE,
                    "Session failed closed because mechanism novelty gate facts were not API-visible to hypothesis generation.",
                    metadata=parity_feedback,
                )
                return self._persist(output, state)
            if len(semantic_rejections) < _MAX_HYPOTHESIS_SEMANTIC_RETRIES:
                rejection = result.to_rejection(hypothesis)
                semantic_rejections.append(
                    _hypothesis_semantic_retry_rejection_payload(rejection, attempt)
                )
                state.note(
                    AgenticProposalPhase.DRAFT_HYPOTHESIS,
                    "Mechanism novelty gate rejected hypothesis; retrying with structured semantic feedback.",
                    metadata={
                        "attempt": attempt,
                        "premise_check": result.premise_check,
                        "failure_category": result.failure_category,
                        "mechanism": result.mechanism,
                        "source": "mechanism_novelty_gate",
                    },
                )
                return None
            return self._mechanism_novelty_failed_output(
                request=request,
                session_id=session_id,
                state=state,
                hypothesis=hypothesis,
                tool_context=tool_context,
                observations=observations,
                evidence_used=tuple(evidence),
            )

    def _mechanism_novelty_failed_output(
            self,
            *,
            request: AgenticProposalRequest,
            session_id: str,
            state: AgenticProposalSessionState,
            hypothesis: HypothesisProposal,
            observations: list[ProposalObservation],
            tool_context: ProposalToolContext | None = None,
            evidence_used: tuple[AgenticEvidenceRef, ...] = (),
        ) -> AgenticProposalOutput | None:
            result = _mechanism_novelty_gate().evaluate(
                hypothesis,
                context=tool_context,
                observations=observations,
            )
            if result is None:
                return None
            if not result.is_hard_block:
                _record_mechanism_novelty_diagnostic(
                    state,
                    hypothesis=hypothesis,
                    result=result,
                    attempt=None,
                    observations=observations,
                )
                return None
            parity_feedback = _mechanism_novelty_gate_prompt_parity_feedback(
                result,
                getattr(state, "_latest_hypothesis_prompt_manifest", None),
                attempt=None,
            )
            if parity_feedback is not None:
                detail = str(parity_feedback.get("reason") or "")
                _record_failure_ledger_entry(
                    state,
                    phase=AgenticProposalPhase.DRAFT_HYPOTHESIS,
                    category=AgenticFailureCategory.CONTRACT_BOUNDARY_FAILURE,
                    detail=detail,
                    source="mechanism_novelty_gate_prompt_parity",
                    failure_code=str(parity_feedback.get("failure_code") or ""),
                )
                output = self._failed_output(
                    request=request,
                    session_id=session_id,
                    status=AgenticProposalStatus.FAILED,
                    termination_reason=AgenticTerminationReason.HYPOTHESIS_GENERATION_FAILED,
                    detail=detail,
                    evidence_used=evidence_used,
                    failure_category=AgenticFailureCategory.CONTRACT_BOUNDARY_FAILURE,
                )
                state.status = output.status
                state.note(
                    AgenticProposalPhase.FINALIZE,
                    "Mechanism novelty rejection withheld because gate facts were not API-visible in the hypothesis prompt.",
                    metadata=parity_feedback,
                )
                return self._persist(output, state)
            rejection = result.to_rejection(hypothesis)
            _record_failure_ledger_entry(
                state,
                phase=AgenticProposalPhase.DRAFT_HYPOTHESIS,
                category=result.failure_category,
                detail=result.reason,
                source="mechanism_novelty_gate",
            )
            output = self._structured_rejection_output(
                request=request,
                session_id=session_id,
                hypothesis=hypothesis,
                rejection=rejection,
                evidence_used=evidence_used,
                self_check=AgenticSelfCheck(schema_valid=True),
            )
            state.status = output.status
            state.note(
                AgenticProposalPhase.FINALIZE,
                "Mechanism novelty gate rejected the solver_design hypothesis before code context.",
                metadata={
                    "premise_check": result.premise_check,
                    "failure_category": result.failure_category,
                    "mechanism": result.mechanism,
                },
            )
            return self._persist(output, state)


def _record_mechanism_novelty_diagnostic(
    state: AgenticProposalSessionState,
    *,
    hypothesis: HypothesisProposal,
    result: Any,
    attempt: int | None,
    observations: list[ProposalObservation] | None = None,
) -> None:
    diagnostic = result.to_diagnostic(hypothesis)
    warning = _mechanism_novelty_warning_payload(diagnostic, attempt=attempt)
    state.note(
        AgenticProposalPhase.DRAFT_HYPOTHESIS,
        "Mechanism novelty diagnostic recorded; continuing without hard novelty block.",
        metadata=_drop_empty_dict(
            {
                "attempt": attempt,
                "result_kind": diagnostic.get("result_kind"),
                "gate_action": diagnostic.get("gate_action"),
                "diagnostic_kind": diagnostic.get("diagnostic_kind"),
                "premise_check": diagnostic.get("premise_check"),
                "failure_category": diagnostic.get("failure_category"),
                "mechanism": diagnostic.get("mechanism"),
                "fact_ids": diagnostic.get("fact_ids"),
                "fact_packet_digest": diagnostic.get("fact_packet_digest"),
                "reason": diagnostic.get("reason"),
                "diagnostic": diagnostic,
                "warning": warning,
            }
        ),
    )
    if observations is not None:
        observations.append(
            ProposalObservation(
                observation_id=(
                    f"mechanism-novelty-diagnostic-{len(observations) + 1:04d}"
                ),
                session_id=state.session_id,
                tool_name="proposal.mechanism_novelty_diagnostic",
                tool_call_id=(
                    f"mechanism-novelty-diagnostic-{len(observations) + 1:04d}"
                ),
                observation_type="diagnostic",
                summary=str(warning.get("summary") or "Mechanism novelty warning."),
                structured_payload=warning,
                exposure_level=ProposalExposureLevel.PUBLIC_SPEC,
                is_error=False,
            )
    )


def _mechanism_novelty_gate() -> Any:
    facade = sys.modules.get("scion.proposal.agentic_session_hypothesis")
    if facade is not None:
        return getattr(facade, "_MECHANISM_NOVELTY_GATE", _MECHANISM_NOVELTY_GATE)
    return _MECHANISM_NOVELTY_GATE


def _mechanism_novelty_warning_payload(
    diagnostic: Mapping[str, Any],
    *,
    attempt: int | None,
) -> dict[str, Any]:
    diagnostic_kind = str(diagnostic.get("diagnostic_kind") or "").strip()
    mechanism = str(diagnostic.get("mechanism") or "").strip()
    reason = str(diagnostic.get("reason") or "").strip()
    guidance = (
        str(diagnostic.get("allowed_variant_guidance") or "").strip()
        or (
            "Existing near-field mechanism evidence may overlap with this "
            "proposal. Continue only by acknowledging the existing mechanism "
            "and stating the material trigger, scoring, schedule, or behavior "
            "difference; do not change direction merely to satisfy novelty "
            "wording."
        )
    )
    if "material" not in guidance.lower():
        guidance = (
            f"{guidance} Acknowledge the existing mechanism and state the "
            "material trigger, scoring, schedule, or behavior difference."
        )
    return _drop_empty_dict(
        {
            "artifact_kind": "agentic_mechanism_novelty_warning",
            "source": diagnostic.get("source") or "mechanism_novelty_gate",
            "gate_name": diagnostic.get("gate_name"),
            "attempt": attempt,
            "warning_kind": diagnostic_kind or "novelty_warning",
            "diagnostic_kind": diagnostic_kind or "novelty_warning",
            "premise_check": diagnostic.get("premise_check"),
            "failure_category": diagnostic.get("failure_category"),
            "mechanism": mechanism,
            "selected_surface": diagnostic.get("selected_surface"),
            "target_file": diagnostic.get("target_file"),
            "reason": reason,
            "fact_ids": diagnostic.get("fact_ids"),
            "fact_packet_digest": diagnostic.get("fact_packet_digest"),
            "snapshot_digest": diagnostic.get("snapshot_digest"),
            "matched_span": diagnostic.get("matched_span"),
            "summary": (
                f"Novelty warning for {mechanism or 'candidate mechanism'}: "
                "an existing or near-field mechanism may overlap; material "
                "difference should be stated before implementation."
            ),
            "agent_guidance": guidance,
            "blocking": False,
            "quality_block": False,
        }
    )


def _mechanism_novelty_gate_prompt_parity_feedback(
    result: Any,
    manifest: Mapping[str, Any] | None,
    *,
    attempt: int | None,
) -> dict[str, Any] | None:
    """Return retry feedback when a gate rejection used non-visible facts."""
    fact_packet_digest = str(getattr(result, "fact_packet_digest", "") or "").strip()
    if not fact_packet_digest:
        return None
    manifest_map = manifest if isinstance(manifest, Mapping) else {}
    statuses = manifest_map.get("section_statuses")
    facts_status = (
        statuses.get("active_algorithm_facts")
        if isinstance(statuses, Mapping)
        else None
    )
    if not isinstance(facts_status, Mapping):
        return _gate_prompt_parity_payload(
            fact_packet_digest=fact_packet_digest,
            prompt_fact_packet_digest="",
            prompt_status="missing",
            attempt=attempt,
        )
    prompt_fact_packet_digest = str(
        facts_status.get("fact_packet_digest") or ""
    ).strip()
    prompt_status = str(facts_status.get("status") or "").strip() or "missing"
    if (
        prompt_status == "included"
        and prompt_fact_packet_digest
        and prompt_fact_packet_digest == fact_packet_digest
    ):
        return None
    return _gate_prompt_parity_payload(
        fact_packet_digest=fact_packet_digest,
        prompt_fact_packet_digest=prompt_fact_packet_digest,
        prompt_status=prompt_status,
        attempt=attempt,
    )


def _gate_prompt_parity_payload(
    *,
    fact_packet_digest: str,
    prompt_fact_packet_digest: str,
    prompt_status: str,
    attempt: int | None,
) -> dict[str, Any]:
    return {
        "source": "mechanism_novelty_gate_prompt_parity",
        "failure_code": "gate_prompt_parity_retry_required",
        "failure_category": "contract_boundary_failure",
        "agent_block_reason": "framework_control",
        "fact_packet_digest": fact_packet_digest,
        "prompt_fact_packet_digest": prompt_fact_packet_digest,
        "prompt_fact_status": prompt_status,
        "attempt": attempt,
        "reason": (
            "Mechanism novelty gate prepared a rejection using active algorithm "
            f"fact_packet_digest={fact_packet_digest}, but that exact fact packet "
            f"was not included in the API-visible hypothesis prompt "
            f"(prompt_status={prompt_status!r}, "
            f"prompt_fact_packet_digest={prompt_fact_packet_digest!r}). Retry "
            "only after the same adapter-owned active_algorithm_facts packet is "
            "rendered to the agent before hypothesis generation; a gate must not "
            "be better informed than the proposal agent."
        ),
        "retry_constraint": (
            "Use the now-visible active_algorithm_facts packet to verify the "
            "premise before restating the same novelty claim."
        ),
    }
