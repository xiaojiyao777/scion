"""AgenticSessionHypothesis mixin."""
from __future__ import annotations

import re
from typing import Mapping

from scion.proposal.agentic_session_common import *
from scion.proposal.negative_facts import render_negative_fact_block


class AgenticSessionHypothesisMixin:
    def _forced_hypothesis_violation(
            self,
            context: ProposalToolContext | None,
            hypothesis: HypothesisProposal,
            *,
            request: AgenticProposalRequest | None = None,
        ) -> str | None:
            forced_surface = str(
                getattr(context, "forced_surface", None)
                or (
                    (request.hypothesis_context or {}).get("forced_surface")
                    if request is not None and request.hypothesis_context is not None
                    else ""
                )
                or ""
            ).strip()
            if not forced_surface:
                boundary = tuple(
                    str(surface or "").strip()
                    for surface in getattr(
                        context,
                        "active_problem_boundary_surfaces",
                        (),
                    )
                    if str(surface or "").strip()
                )
                if not boundary and request is not None and request.hypothesis_context:
                    constraints = request.hypothesis_context.get(
                        "agentic_hypothesis_constraints"
                    )
                    if isinstance(constraints, Mapping):
                        raw = constraints.get("active_problem_boundary_surfaces")
                        if isinstance(raw, str):
                            boundary = tuple(
                                item.strip() for item in raw.split(",") if item.strip()
                            )
                        elif isinstance(raw, (list, tuple)):
                            boundary = tuple(
                                str(item).strip() for item in raw if str(item).strip()
                            )
                if boundary:
                    actual_surface = str(hypothesis.change_locus or "").strip()
                    if actual_surface not in set(boundary):
                        return (
                            "active_problem_boundary_constraint: change_locus must "
                            f"stay within {list(boundary)!r}; got "
                            f"{actual_surface!r}. Component policies are "
                            "implementation hooks or attribution evidence, not "
                            "replacement research goals."
                        )
                return None
            actual_surface = str(hypothesis.change_locus or "").strip()
            if actual_surface != forced_surface:
                return (
                    "forced_surface_constraint: change_locus must be "
                    f"{forced_surface!r}, got {actual_surface!r}"
                )
            forced_action = str(
                getattr(context, "forced_action", None)
                or (
                    (request.hypothesis_context or {}).get("forced_action")
                    if request is not None and request.hypothesis_context is not None
                    else ""
                )
                or ""
            ).strip()
            if forced_action and str(hypothesis.action or "").strip() != forced_action:
                return (
                    "forced_surface_constraint: action must be "
                    f"{forced_action!r}, got {str(hypothesis.action or '').strip()!r}"
                )
            forced_target = str(
                getattr(context, "forced_target_file", None)
                or (
                    (request.hypothesis_context or {}).get("forced_target_file")
                    if request is not None and request.hypothesis_context is not None
                    else ""
                )
                or ""
            ).strip()
            if forced_target and str(hypothesis.target_file or "").strip() != forced_target:
                return (
                    "forced_surface_constraint: target_file must be "
                    f"{forced_target!r}, got {str(hypothesis.target_file or '').strip()!r}"
                )
            return None

    def _generate_hypothesis_with_semantic_retries(
            self,
            *,
            request: AgenticProposalRequest,
            session_id: str,
            state: AgenticProposalSessionState,
            tool_context: ProposalToolContext | None,
            observations: list[ProposalObservation],
            evidence: list[AgenticEvidenceRef],
        ) -> tuple[HypothesisProposal | None, AgenticProposalOutput | None]:
            semantic_rejections: list[Mapping[str, Any]] = []
            preview_rejections: list[Mapping[str, Any]] = []
            grounding_rejections: list[Mapping[str, Any]] = []
            max_attempts = (
                1
                + _MAX_HYPOTHESIS_SEMANTIC_RETRIES
                + _MAX_HYPOTHESIS_PREVIEW_RETRIES
                + _MAX_HYPOTHESIS_GROUNDING_RETRIES
            )
            for attempt in range(1, max_attempts + 1):
                if self._session_timeout_reached(state):
                    output = self._timeout_output(
                        request,
                        state,
                        evidence_used=tuple(evidence),
                    )
                    state.status = output.status
                    return None, self._persist(output, state)
                state.note(
                    AgenticProposalPhase.CHOOSE_SURFACE,
                    "Delegating hypothesis generation.",
                    metadata={"attempt": attempt},
                )
                state.note(
                    AgenticProposalPhase.DRAFT_HYPOTHESIS,
                    "Generating hypothesis proposal.",
                    metadata={"attempt": attempt},
                )
                try:
                    hypothesis_context, prompt_observations = (
                        self._hypothesis_prompt_context(
                            request=request,
                            tool_context=tool_context,
                            observations=observations,
                            semantic_rejections=semantic_rejections,
                            preview_rejections=preview_rejections,
                            grounding_rejections=grounding_rejections,
                            attempt=attempt,
                        )
                    )
                    self._record_prompt_manifest(
                        state,
                        call_kind=_hypothesis_prompt_call_kind(
                            attempt=attempt,
                            semantic_rejections=semantic_rejections,
                            preview_rejections=preview_rejections,
                            grounding_rejections=grounding_rejections,
                        ),
                        prompt_context=hypothesis_context,
                        observations=prompt_observations,
                    )
                    assert self._creative is not None
                    hypothesis = self._creative.generate_hypothesis(hypothesis_context)
                except self._SESSION_ERROR_TYPES as exc:
                    failure_category = _structured_output_failure_category(exc)
                    _record_failure_ledger_entry(
                        state,
                        phase=AgenticProposalPhase.DRAFT_HYPOTHESIS,
                        category=failure_category,
                        detail=str(exc),
                        source="hypothesis_generation_exception",
                        attempt=attempt,
                    )
                    output = self._failed_output(
                        request=request,
                        session_id=session_id,
                        status=AgenticProposalStatus.FAILED,
                        termination_reason=AgenticTerminationReason.HYPOTHESIS_GENERATION_FAILED,
                        detail=str(exc),
                        evidence_used=tuple(evidence),
                        failure_category=failure_category,
                    )
                    state.status = output.status
                    state.note(
                        AgenticProposalPhase.FINALIZE,
                        "Hypothesis generation failed.",
                        metadata={"error": type(exc).__name__, "attempt": attempt},
                    )
                    return None, self._persist(output, state)

                if self._session_timeout_reached(state):
                    output = self._timeout_output(
                        request,
                        state,
                        evidence_used=tuple(evidence),
                    )
                    state.status = output.status
                    return None, self._persist(output, state)

                forced_violation = self._forced_hypothesis_violation(
                    tool_context,
                    hypothesis,
                    request=request,
                )
                if forced_violation is not None:
                    output = self._failed_output(
                        request=request,
                        session_id=session_id,
                        status=AgenticProposalStatus.FAILED,
                        termination_reason=AgenticTerminationReason.HYPOTHESIS_GENERATION_FAILED,
                        detail=forced_violation,
                        evidence_used=tuple(evidence),
                        failure_category=AgenticFailureCategory.CONTRACT_BOUNDARY_FAILURE,
                    )
                    state.status = output.status
                    state.note(
                        AgenticProposalPhase.FINALIZE,
                        "Hypothesis generation violated the forced research-surface constraint.",
                        metadata={"detail": forced_violation, "attempt": attempt},
                    )
                    return None, self._persist(output, state)

                preview_preservation_count = len(preview_rejections)
                preview_preservation_output = (
                    self._hypothesis_preview_preservation_drift_or_retry(
                        request=request,
                        session_id=session_id,
                        state=state,
                        hypothesis=hypothesis,
                        evidence=evidence,
                        preview_rejections=preview_rejections,
                        attempt=attempt,
                    )
                )
                if preview_preservation_output is not None:
                    return None, preview_preservation_output
                if len(preview_rejections) > preview_preservation_count:
                    continue

                grounding_feedback_count = len(grounding_rejections)
                grounding_output = self._solver_design_target_prompt_grounding_retry(
                    request=request,
                    session_id=session_id,
                    state=state,
                    tool_context=tool_context,
                    hypothesis=hypothesis,
                    prompt_observations=prompt_observations,
                    observations=observations,
                    evidence=evidence,
                    grounding_rejections=grounding_rejections,
                    attempt=attempt,
                )
                if grounding_output is not None:
                    return None, grounding_output
                if len(grounding_rejections) > grounding_feedback_count:
                    continue

                semantic_feedback_count = len(semantic_rejections)
                novelty_output = self._solver_design_semantic_rejection_or_retry(
                    request=request,
                    session_id=session_id,
                    state=state,
                    tool_context=tool_context,
                    hypothesis=hypothesis,
                    observations=observations,
                    evidence=evidence,
                    semantic_rejections=semantic_rejections,
                    attempt=attempt,
                )
                if novelty_output is not None:
                    return None, novelty_output
                if len(semantic_rejections) > semantic_feedback_count:
                    continue

                preview_feedback_count = len(preview_rejections)
                preview_output = self._hypothesis_preview_rejection_or_retry(
                    request=request,
                    session_id=session_id,
                    state=state,
                    tool_context=tool_context,
                    hypothesis=hypothesis,
                    observations=observations,
                    evidence=evidence,
                    preview_rejections=preview_rejections,
                    attempt=attempt,
                )
                if preview_output is not None:
                    return None, preview_output
                if len(preview_rejections) > preview_feedback_count:
                    continue
                return hypothesis, None
            return None, None

    def _hypothesis_preview_preservation_drift_or_retry(
            self,
            *,
            request: AgenticProposalRequest,
            session_id: str,
            state: AgenticProposalSessionState,
            hypothesis: HypothesisProposal,
            evidence: list[AgenticEvidenceRef],
            preview_rejections: list[Mapping[str, Any]],
            attempt: int,
        ) -> AgenticProposalOutput | None:
            drift = _schema_retry_preservation_drift(
                hypothesis,
                preview_rejections,
                attempt=attempt,
            )
            if drift is None:
                return None
            feedback = _schema_retry_drift_feedback(
                drift,
                hypothesis,
                attempt=attempt,
            )
            if not _schema_retry_corrective_retry_already_used(preview_rejections):
                preview_rejections.append(feedback)
                state.note(
                    AgenticProposalPhase.DRAFT_HYPOTHESIS,
                    "Hypothesis schema retry changed protected research identity; issuing one identity-corrective retry.",
                    metadata={
                        "attempt": attempt,
                        "failure_code": "schema_retry_drift",
                        "drift_fields": drift.get("drift_fields", ()),
                        "corrective_retry": True,
                    },
                )
                return None

            detail = _schema_retry_drift_failure_detail(drift)
            _record_failure_ledger_entry(
                state,
                phase=AgenticProposalPhase.DRAFT_HYPOTHESIS,
                category=AgenticFailureCategory.CONTRACT_BOUNDARY_FAILURE,
                detail=detail,
                source="hypothesis_preview_retry_preservation_gate",
                attempt=attempt,
                failure_code="schema_retry_drift",
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
                "Hypothesis schema retry failed closed because protected research identity drifted.",
                metadata={
                    "detail": detail,
                    "attempt": attempt,
                    "failure_code": "schema_retry_drift",
                    "drift_fields": drift.get("drift_fields", ()),
                    "corrective_retry_exhausted": True,
                },
            )
            return self._persist(output, state)

    def _hypothesis_prompt_context(
            self,
            *,
            request: AgenticProposalRequest,
            tool_context: ProposalToolContext | None,
            observations: list[ProposalObservation],
            semantic_rejections: list[Mapping[str, Any]],
            preview_rejections: list[Mapping[str, Any]],
            grounding_rejections: list[Mapping[str, Any]],
            attempt: int,
        ) -> tuple[dict[str, Any], list[ProposalObservation]]:
            hypothesis_context = dict(
                _sanitize_agentic_value(request.hypothesis_context or {})
            )
            if request.resume_context is not None:
                hypothesis_context["agentic_resume_context"] = (
                    _sanitize_agentic_value(request.resume_context)
                )
            constraints = self._hypothesis_constraints(tool_context)
            if constraints:
                hypothesis_context["agentic_hypothesis_constraints"] = (
                    _sanitize_agentic_value(constraints)
                )
            if semantic_rejections:
                hypothesis_context["agentic_hypothesis_semantic_rejections"] = [
                    _sanitize_agentic_value(rejection)
                    for rejection in semantic_rejections
                ]
                hypothesis_context["agentic_hypothesis_retry_rule"] = (
                    "A mechanism novelty gate rejected the previous hypothesis. "
                    "If the rejection is premise_contradicted, repair the "
                    "contradicted factual premise or explicitly acknowledge the "
                    "existing mechanism while stating the material in-family "
                    "variant. If it is duplicate/no material novelty, choose a "
                    "different mechanism family or a materially different "
                    "variant; do not merely relabel the same premise."
                )
                hypothesis_context["agentic_hypothesis_retry_attempt"] = attempt
            if preview_rejections:
                hypothesis_context["agentic_hypothesis_preview_rejections"] = [
                    _sanitize_agentic_value(rejection)
                    for rejection in preview_rejections
                ]
                if _schema_retry_corrective_retry_already_used(preview_rejections):
                    hypothesis_context["agentic_hypothesis_preview_retry_rule"] = (
                        "IDENTITY CORRECTIVE RETRY for a schema/telemetry "
                        "repair. Restore the exact protected identity from the "
                        "feedback: action, target_file, mechanism_changes ids/"
                        "change_types, and telemetry activation refs. The final "
                        "task is only to repair expected_telemetry/schema fields "
                        "for that same hypothesis; do not explore, rename, or "
                        "choose a different mechanism."
                    )
                else:
                    hypothesis_context["agentic_hypothesis_preview_retry_rule"] = (
                        "A schema/target preview rejected the previous hypothesis. "
                        "This is a structured-field repair, not a semantic novelty "
                        "rejection. Preserve the previous action, target_file, "
                        "mechanism_changes ids/change_types, and telemetry "
                        "activation mechanism; repair only the exact field named "
                        "by the failed check unless the preview explicitly says "
                        "that surface/action/target is invalid. Natural-language "
                        "hypothesis and novelty_signature wording may be clarified "
                        "without changing the mechanism."
                    )
                hypothesis_context["agentic_hypothesis_retry_attempt"] = attempt
            if grounding_rejections:
                hypothesis_context["agentic_hypothesis_grounding_rejections"] = [
                    _sanitize_agentic_value(rejection)
                    for rejection in grounding_rejections
                ]
                hypothesis_context["agentic_hypothesis_grounding_retry_rule"] = (
                    "The previous solver_design hypothesis selected an existing "
                    "target_file whose full source was not visible in that "
                    "hypothesis API prompt. The target file has now been read. "
                    "Redraft the same target/mechanism only after using the full "
                    "target-file observation now present in agentic_tool_observations."
                )
                hypothesis_context["agentic_hypothesis_retry_attempt"] = attempt
            if observations:
                prompt_observations = _hypothesis_prompt_observations(
                    observations,
                    tool_context,
                )
                research_diagnosis = _research_diagnosis_from_observations(observations)
                if research_diagnosis:
                    hypothesis_context["agentic_research_diagnosis"] = (
                        research_diagnosis
                    )
                active_algorithm_facts = _active_algorithm_facts_for_prompt_context(
                    observations
                )
                if active_algorithm_facts:
                    hypothesis_context["agentic_active_algorithm_facts"] = (
                        active_algorithm_facts
                    )
                hypothesis_context["agentic_tool_observations"] = [
                    _observation_prompt_payload(observation)
                    for observation in prompt_observations
                ]
                negative_fact_block = render_negative_fact_block(
                    active_algorithm_facts=active_algorithm_facts,
                    structured_rejections=semantic_rejections,
                    prior_quality_blocks=tuple(
                        block
                        for block in hypothesis_context.get(
                            "agentic_prior_quality_blocks",
                            (),
                        )
                        if isinstance(block, Mapping)
                    ),
                )
                if negative_fact_block:
                    existing = str(
                        hypothesis_context.get("agentic_negative_fact_block") or ""
                    ).strip()
                    hypothesis_context["agentic_negative_fact_block"] = (
                        existing + "\n" + negative_fact_block
                        if existing
                        else negative_fact_block
                    )
            else:
                prompt_observations = []
            return hypothesis_context, prompt_observations

    def _solver_design_target_prompt_grounding_retry(
            self,
            *,
            request: AgenticProposalRequest,
            session_id: str,
            state: AgenticProposalSessionState,
            tool_context: ProposalToolContext | None,
            hypothesis: HypothesisProposal,
            prompt_observations: list[ProposalObservation],
            observations: list[ProposalObservation],
            evidence: list[AgenticEvidenceRef],
            grounding_rejections: list[Mapping[str, Any]],
            attempt: int,
        ) -> AgenticProposalOutput | None:
            if tool_context is None or not _is_solver_design_hypothesis(hypothesis):
                return None
            target_read_args = _solver_design_target_file_read_args(
                hypothesis,
                context=tool_context,
                observations=observations,
            )
            if target_read_args is None:
                return None
            if _prompt_observations_include_full_target_file(
                prompt_observations,
                target_read_args,
            ):
                return None

            grounding_observations = self._run_solver_design_grounding_tools(
                tool_context,
                state,
                observations,
                selection_source="solver_design_target_prompt_grounding_required",
                hypothesis=hypothesis,
            )
            observations.extend(grounding_observations)
            evidence.extend(_evidence_from_observations(grounding_observations))
            grounding_error = _missing_solver_design_grounding_error(
                observations,
                hypothesis=hypothesis,
                context=tool_context,
            )
            if (
                grounding_error is None
                and _observations_include_full_target_file(
                    observations,
                    target_read_args,
                )
                and len(grounding_rejections) < _MAX_HYPOTHESIS_GROUNDING_RETRIES
            ):
                grounding_rejections.append(
                    _solver_design_target_prompt_grounding_feedback(
                        hypothesis,
                        target_read_args,
                        attempt=attempt,
                    )
                )
                state.note(
                    AgenticProposalPhase.DRAFT_HYPOTHESIS,
                    "Solver-design target file was read after hypothesis generation; retrying with target source visible in the hypothesis prompt.",
                    metadata={
                        "attempt": attempt,
                        "target_file": target_read_args.get("file_path"),
                        "failure_code": "solver_design_target_not_in_hypothesis_prompt",
                    },
                )
                return None

            if grounding_error is not None:
                detail = grounding_error
            else:
                detail = (
                    "solver_design target-file grounding invariant failed: "
                    "hypothesis selected existing target_file "
                    f"{target_read_args.get('file_path')!r}, but the API-visible "
                    "hypothesis prompt did not include a full context.read_algorithm_file "
                    "observation for that file and Scion could not collect one before "
                    "retry."
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
                "Session failed closed before solver_design hypothesis approval because target-file source was not API-visible to hypothesis generation.",
                metadata={"detail": detail, "attempt": attempt},
            )
            return self._persist(output, state)

    def _hypothesis_preview_rejection_or_retry(
            self,
            *,
            request: AgenticProposalRequest,
            session_id: str,
            state: AgenticProposalSessionState,
            tool_context: ProposalToolContext | None,
            hypothesis: HypothesisProposal,
            observations: list[ProposalObservation],
            evidence: list[AgenticEvidenceRef],
            preview_rejections: list[Mapping[str, Any]],
            attempt: int,
        ) -> AgenticProposalOutput | None:
            if tool_context is None:
                return None

            selected_surface_observations = self._run_selected_surface_observation_tool(
                tool_context,
                hypothesis,
                state,
                observations,
            )
            observations.extend(selected_surface_observations)
            evidence.extend(_evidence_from_observations(selected_surface_observations))

            preview_observations = self._run_hypothesis_preview_tools(
                tool_context,
                hypothesis,
                state,
            )
            observations.extend(preview_observations)
            evidence.extend(_evidence_from_observations(preview_observations))
            self_check = _self_check_from_previews(preview_observations)
            self_check_detail = _self_check_failure_detail(
                self_check,
                require_schema_preview=_self_check_required(tool_context),
                require_contract_preview=False,
            )
            if self_check_detail is None:
                return None

            retry_feedback = _hypothesis_preview_retry_feedback(
                preview_observations,
                detail=self_check_detail,
                attempt=attempt,
                previous_hypothesis=hypothesis,
            )
            if (
                retry_feedback is not None
                and len(preview_rejections) < _MAX_HYPOTHESIS_PREVIEW_RETRIES
            ):
                preview_rejections.append(retry_feedback)
                state.note(
                    AgenticProposalPhase.DRAFT_HYPOTHESIS,
                    "Hypothesis preview gate rejected hypothesis; retrying with structured schema feedback.",
                    metadata={
                        "attempt": attempt,
                        "failure_code": retry_feedback.get("failure_code"),
                        "source": retry_feedback.get("source"),
                    },
                )
                return None

            _record_failure_ledger_entry(
                state,
                phase=AgenticProposalPhase.SELF_CHECK,
                category=_preview_failure_category(preview_observations),
                detail=self_check_detail,
                source="hypothesis_preview_failure",
                attempt=attempt,
                failure_code=(
                    str(retry_feedback.get("failure_code"))
                    if retry_feedback is not None
                    else None
                ),
            )
            output = self._self_check_failed_output(
                request=request,
                session_id=session_id,
                hypothesis=hypothesis,
                detail=self_check_detail,
                termination_reason=AgenticTerminationReason.HYPOTHESIS_GENERATION_FAILED,
                evidence_used=tuple(evidence),
                self_check=self_check,
                failure_category=AgenticFailureCategory.CONTRACT_BOUNDARY_FAILURE,
            )
            state.status = output.status
            state.note(
                AgenticProposalPhase.FINALIZE,
                "Hypothesis self-check failed closed before approval.",
                metadata={"detail": self_check_detail, "attempt": attempt},
            )
            return self._persist(output, state)

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

            result = _MECHANISM_NOVELTY_GATE.evaluate(
                hypothesis,
                context=tool_context,
                observations=observations,
            )
            if result is None:
                return None
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
            result = _MECHANISM_NOVELTY_GATE.evaluate(
                hypothesis,
                context=tool_context,
                observations=observations,
            )
            if result is None:
                return None
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
    telemetry_detail = str(telemetry.get("detail") or "").strip()
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

    allowed_template = telemetry.get("allowed_expected_telemetry_template")
    if not isinstance(allowed_template, Mapping):
        allowed_template = {}
    requested_fields = telemetry.get("requested_fields")
    requested_activation = ()
    if isinstance(requested_fields, Mapping):
        activation = requested_fields.get("activation")
        if isinstance(activation, (list, tuple)):
            requested_activation = tuple(
                str(field).strip() for field in activation if str(field).strip()
            )
    return _drop_empty_dict(
        {
            "attempt": attempt,
            "source": "hypothesis_preview_gate",
            "gate_name": "proposal.schema_preview",
            "failure_code": "C11_expected_telemetry",
            "failure_category": AgenticFailureCategory.CONTRACT_BOUNDARY_FAILURE.value,
            "reason": _limit_string(
                str(problem_telemetry.get("reason") or "")
                or telemetry_detail
                or c11_detail
                or detail,
                1000,
            ),
            "requested_activation_fields": list(requested_activation),
            "offending_fields": list(
                problem_telemetry.get("offending_fields") or ()
            ),
            "allowed_repair_shape": problem_telemetry.get("allowed_repair_shape"),
            "forbidden_repair_shape": problem_telemetry.get("forbidden_repair_shape"),
            "allowed_expected_telemetry_template": (
                _compact_expected_telemetry_template(allowed_template)
            ),
            "preserve_hypothesis": _hypothesis_retry_anchor(previous_hypothesis),
            "protected_identity": _schema_retry_protected_identity(
                _hypothesis_retry_anchor(previous_hypothesis)
            ),
            "retry_constraint": (
                "Repair only expected_telemetry/schema fields. Preserve the "
                "prior action, target_file, mechanism_changes ids/change_types, "
                "and telemetry activation mechanism refs; do not switch "
                "mechanisms or targets for a C11/schema retry. Natural-language "
                "hypothesis and novelty_signature wording may be clarified."
            ),
        }
    )


def _schema_retry_preservation_drift(
    hypothesis: HypothesisProposal,
    preview_rejections: list[Mapping[str, Any]],
    *,
    attempt: int,
) -> dict[str, Any] | None:
    rejection = _latest_schema_preservation_rejection(
        preview_rejections,
        attempt=attempt,
    )
    if rejection is None:
        return None
    expected = rejection.get("preserve_hypothesis")
    if not isinstance(expected, Mapping):
        return None
    observed = _hypothesis_retry_anchor(hypothesis)
    drift_fields: list[str] = []
    for field in (
        "action",
        "target_file",
        "mechanism_changes",
    ):
        if _canonical_retry_identity_value(expected.get(field)) != (
            _canonical_retry_identity_value(observed.get(field))
        ):
            drift_fields.append(field)
    activation_drift = _schema_retry_activation_identity_drift(
        expected,
        hypothesis,
    )
    if activation_drift:
        drift_fields.append("expected_telemetry.activation")
    if not drift_fields:
        return None
    return _drop_empty_dict(
        {
            "source": "hypothesis_preview_retry_preservation_gate",
            "failure_code": "schema_retry_drift",
            "failure_category": AgenticFailureCategory.CONTRACT_BOUNDARY_FAILURE.value,
            "retry_source": rejection.get("source"),
            "retry_failure_code": rejection.get("failure_code"),
            "attempt": attempt,
            "drift_fields": drift_fields,
            "expected": {
                field: (
                    activation_drift.get("expected")
                    if field == "expected_telemetry.activation"
                    else expected.get(field)
                )
                for field in drift_fields
            },
            "observed": {
                field: (
                    activation_drift.get("observed")
                    if field == "expected_telemetry.activation"
                    else observed.get(field)
                )
                for field in drift_fields
            },
            "preserve_hypothesis": expected,
            "protected_identity": _schema_retry_protected_identity(expected),
        }
    )


def _schema_retry_corrective_retry_already_used(
    preview_rejections: list[Mapping[str, Any]],
) -> bool:
    return any(
        str(rejection.get("failure_code") or "").strip() == "schema_retry_drift"
        for rejection in preview_rejections
        if isinstance(rejection, Mapping)
    )


def _latest_schema_preservation_rejection(
    preview_rejections: list[Mapping[str, Any]],
    *,
    attempt: int,
) -> Mapping[str, Any] | None:
    if not preview_rejections:
        return None
    previous_attempt = attempt - 1
    rejection = preview_rejections[-1]
    try:
        rejection_attempt = int(rejection.get("attempt") or 0)
    except Exception:
        rejection_attempt = 0
    if rejection_attempt != previous_attempt:
        return None
    failure_code = str(rejection.get("failure_code") or "").strip()
    if failure_code not in {
        "C11_expected_telemetry",
        "schema_retry_drift",
    }:
        return None
    if not isinstance(rejection.get("preserve_hypothesis"), Mapping):
        return None
    return rejection


def _schema_retry_drift_feedback(
    drift: Mapping[str, Any],
    hypothesis: HypothesisProposal,
    *,
    attempt: int,
) -> dict[str, Any]:
    return _drop_empty_dict(
        {
            "attempt": attempt,
            "source": "hypothesis_preview_retry_preservation_gate",
            "gate_name": "schema_retry_preservation_gate",
            "failure_code": "schema_retry_drift",
            "failure_category": AgenticFailureCategory.CONTRACT_BOUNDARY_FAILURE.value,
            "reason": _schema_retry_drift_failure_detail(drift),
            "corrective_retry": True,
            "drift_fields": list(drift.get("drift_fields") or ()),
            "observed_identity": _schema_retry_observed_identity(hypothesis),
            "preserve_hypothesis": drift.get("preserve_hypothesis"),
            "protected_identity": drift.get("protected_identity")
            or _schema_retry_protected_identity(
                drift.get("preserve_hypothesis")
                if isinstance(drift.get("preserve_hypothesis"), Mapping)
                else {}
            ),
            "retry_constraint": (
                "Identity-corrective C11/schema retry: restore the exact "
                "target_file, action, mechanism_changes ids/change_types, and "
                "telemetry activation refs listed in protected_identity. Repair "
                "only expected_telemetry/schema fields for the same hypothesis. "
                "Do not explore, rename, or choose a different mechanism."
            ),
        }
    )


def _schema_retry_drift_failure_detail(drift: Mapping[str, Any]) -> str:
    fields = ", ".join(str(field) for field in drift.get("drift_fields") or ())
    expected = _limit_string(
        json.dumps(drift.get("expected") or {}, sort_keys=True, default=str),
        800,
    )
    observed = _limit_string(
        json.dumps(drift.get("observed") or {}, sort_keys=True, default=str),
        800,
    )
    return (
        "schema_retry_drift: C11/schema retry changed protected hypothesis "
        f"identity fields ({fields or 'unknown'}). Schema/telemetry retries "
        "must preserve action, target_file, mechanism_changes ids/change_types, "
        "and telemetry activation mechanism refs; free-text hypothesis and "
        f"novelty_signature wording may change. expected={expected}; "
        f"observed={observed}"
    )


def _schema_retry_protected_identity(anchor: Mapping[str, Any]) -> dict[str, Any]:
    mechanism_changes = anchor.get("mechanism_changes")
    protected = _drop_empty_dict(
        {
            "action": anchor.get("action"),
            "target_file": anchor.get("target_file"),
            "mechanism_changes": mechanism_changes,
            "protected_mechanism_ids": sorted(_protected_mechanism_ids(anchor)),
        }
    )
    return protected


def _schema_retry_observed_identity(
    hypothesis: HypothesisProposal,
) -> dict[str, Any]:
    anchor = _hypothesis_retry_anchor(hypothesis)
    return _drop_empty_dict(
        {
            "action": anchor.get("action"),
            "target_file": anchor.get("target_file"),
            "mechanism_changes": anchor.get("mechanism_changes"),
            "activation_refs": sorted(
                _telemetry_activation_mechanism_refs(
                    getattr(hypothesis, "expected_telemetry", {}) or {}
                )
            ),
        }
    )


def _canonical_retry_identity_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _canonical_retry_identity_value(val)
            for key, val in sorted(value.items(), key=lambda item: str(item[0]))
            if val not in (None, "", [], (), {})
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_canonical_retry_identity_value(item) for item in value]
    if isinstance(value, str):
        return value.strip()
    return value


def _schema_retry_activation_identity_drift(
    expected_anchor: Mapping[str, Any],
    hypothesis: HypothesisProposal,
) -> dict[str, Any]:
    protected_ids = _protected_mechanism_ids(expected_anchor)
    if not protected_ids:
        return {}
    observed_refs = _telemetry_activation_mechanism_refs(
        getattr(hypothesis, "expected_telemetry", {}) or {}
    )
    observed_refs = {
        ref
        for ref in observed_refs
        if _is_structural_activation_ref(ref, protected_ids)
    }
    if not observed_refs:
        return {}
    if any(
        _mechanism_ref_matches(ref, protected)
        for ref in observed_refs
        for protected in protected_ids
    ):
        return {}
    return {
        "expected": {"protected_mechanism_ids": sorted(protected_ids)},
        "observed": {"activation_mechanism_refs": sorted(observed_refs)},
    }


def _protected_mechanism_ids(anchor: Mapping[str, Any]) -> set[str]:
    changes = anchor.get("mechanism_changes")
    ids: set[str] = set()
    if isinstance(changes, (list, tuple)):
        for change in changes:
            if not isinstance(change, Mapping):
                continue
            mechanism_id = _mechanism_ref_token(change.get("id"))
            if mechanism_id:
                ids.add(mechanism_id)
    return ids


def _telemetry_activation_mechanism_refs(expected_telemetry: Any) -> set[str]:
    if not isinstance(expected_telemetry, Mapping):
        return set()
    activation = expected_telemetry.get("activation")
    text_items = _flatten_telemetry_activation_items(activation)
    refs: set[str] = set()
    for item in text_items:
        refs.update(_mechanism_refs_from_telemetry_path(item))
    return {ref for ref in refs if ref not in _GENERIC_TELEMETRY_ACTIVATION_REFS}


def _flatten_telemetry_activation_items(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        items: list[str] = []
        for key, child in value.items():
            items.append(str(key))
            items.extend(_flatten_telemetry_activation_items(child))
        return items
    if isinstance(value, (list, tuple, set, frozenset)):
        items: list[str] = []
        for child in value:
            items.extend(_flatten_telemetry_activation_items(child))
        return items
    return []


_GENERIC_TELEMETRY_ACTIVATION_REFS = {
    "search",
    "solver",
    "construction",
    "destroy",
    "repair",
    "acceptance",
    "local_search",
    "phase",
    "runtime",
    "elapsed",
    "iterations",
}


def _is_structural_activation_ref(ref: str, protected_ids: set[str]) -> bool:
    token = _mechanism_ref_token(ref)
    if not token:
        return False
    if any(_mechanism_ref_matches(token, protected) for protected in protected_ids):
        return True
    return "_" in token


def _mechanism_refs_from_telemetry_path(path: Any) -> set[str]:
    text = str(path or "").strip()
    if not text:
        return set()
    refs: set[str] = set()
    candidate = text.rsplit(".", 1)[-1] if "." in text else text
    parts = [part for part in re.split(r"[\[\]/:\s]+", candidate) if part]
    for part in parts:
        token = _mechanism_ref_token(part)
        if token:
            refs.add(token)
    return refs


def _mechanism_ref_token(value: Any) -> str:
    token = str(value or "").strip().lower().replace("-", "_")
    if not token:
        return ""
    if token.startswith("solver_algorithm_"):
        return ""
    for suffix in (
        "_iterations",
        "_iteration",
        "_calls",
        "_call",
        "_events",
        "_event",
        "_runtime_ms",
        "_elapsed_ms",
        "_activation",
        "_activations",
        "_count",
        "_counts",
    ):
        if token.endswith(suffix):
            token = token[: -len(suffix)]
            break
    return token.strip("_")


def _mechanism_ref_matches(observed: str, protected: str) -> bool:
    observed = _mechanism_ref_token(observed)
    protected = _mechanism_ref_token(protected)
    return bool(
        observed
        and protected
        and (
            observed == protected
            or observed.startswith(f"{protected}_")
            or protected.startswith(f"{observed}_")
        )
    )


def _compact_expected_telemetry_template(value: Mapping[str, Any]) -> dict[str, Any]:
    expected = value.get("expected_telemetry")
    compact_expected: dict[str, list[str]] = {}
    if isinstance(expected, Mapping):
        for category in ("activation", "budget", "effect", "activity"):
            fields = expected.get(category)
            if not isinstance(fields, (list, tuple)):
                continue
            compact_fields = [
                str(field).strip()
                for field in list(fields)[:4]
                if str(field).strip()
            ]
            if compact_fields:
                compact_expected[category] = compact_fields
    return _drop_empty_dict(
        {
            "selected_surface": value.get("selected_surface"),
            "mechanism_id": value.get("mechanism_id"),
            "expected_telemetry": compact_expected,
        }
    )


def _solver_design_target_prompt_grounding_feedback(
    hypothesis: HypothesisProposal,
    target_read_args: Mapping[str, Any],
    *,
    attempt: int,
) -> dict[str, Any]:
    target_file = str(target_read_args.get("file_path") or "").strip()
    return _drop_empty_dict(
        {
            "attempt": attempt,
            "source": "solver_design_target_prompt_grounding",
            "failure_code": "solver_design_target_not_in_hypothesis_prompt",
            "failure_category": AgenticFailureCategory.CONTRACT_BOUNDARY_FAILURE.value,
            "target_file": target_file,
            "reason": (
                "The previous solver_design hypothesis selected an existing "
                "target_file, but the full target-file read observation was not "
                "included in the API-visible prompt that generated it."
            ),
            "preserve_hypothesis": _hypothesis_retry_anchor(hypothesis),
            "retry_constraint": (
                "Use the newly visible full context.read_algorithm_file content "
                f"for {target_file}. Redraft the same target/mechanism only after "
                "checking that file; do not proceed from a read receipt or "
                "post-hoc grounding observation."
            ),
        }
    )


def _prompt_observations_include_full_target_file(
    prompt_observations: list[ProposalObservation],
    target_read_args: Mapping[str, Any],
) -> bool:
    return _observations_include_full_target_file(prompt_observations, target_read_args)


def _observations_include_full_target_file(
    observations: list[ProposalObservation],
    target_read_args: Mapping[str, Any],
) -> bool:
    target_path = _normalize_prompt_grounding_path(target_read_args.get("file_path"))
    if not target_path:
        return False
    requested_max_chars = _coerce_nonnegative_int(
        target_read_args.get("max_chars"),
        default=_APS_TARGET_ALGORITHM_FILE_READ_CHARS,
    )
    for observation in observations:
        if observation.is_error or observation.tool_name != "context.read_algorithm_file":
            continue
        payload = observation.structured_payload
        if not isinstance(payload, Mapping):
            continue
        if _normalize_prompt_grounding_path(payload.get("file_path")) != target_path:
            continue
        if _algorithm_file_payload_full_content_visible(
            payload,
            requested_max_chars=requested_max_chars,
        ):
            return True
    return False


def _algorithm_file_payload_full_content_visible(
    payload: Mapping[str, Any],
    *,
    requested_max_chars: int,
) -> bool:
    if payload.get("readable") is not True:
        return False
    if payload.get("already_observed"):
        return False
    content_preview = payload.get("content_preview")
    if content_preview is None:
        return False
    if bool(payload.get("truncated")):
        return False
    preview_chars = len(str(content_preview))
    size_chars = _coerce_nonnegative_int(payload.get("size_chars"))
    max_chars = _coerce_nonnegative_int(payload.get("max_chars"))
    if (
        size_chars is not None
        and max_chars is not None
        and max_chars >= size_chars
    ):
        return True
    if size_chars is not None:
        return preview_chars >= min(size_chars, requested_max_chars)
    if max_chars is not None:
        return preview_chars >= min(max_chars, requested_max_chars)
    return not bool(payload.get("compacted_for_agentic_budget"))


def _normalize_prompt_grounding_path(value: Any) -> str:
    return str(value or "").replace("\\", "/").lstrip("/").strip()


def _coerce_nonnegative_int(value: Any, *, default: int | None = None) -> int | None:
    try:
        parsed = int(value)
    except Exception:
        return default
    if parsed < 0:
        return default
    return parsed


def _hypothesis_retry_anchor(hypothesis: HypothesisProposal) -> dict[str, Any]:
    return _drop_empty_dict(
        {
            "change_locus": hypothesis.change_locus,
            "action": hypothesis.action,
            "target_file": hypothesis.target_file,
            "predicted_direction": hypothesis.predicted_direction,
            "target_objectives": list(hypothesis.target_objectives or ()),
            "protected_objectives": list(hypothesis.protected_objectives or ()),
            "target_runtime_effect": hypothesis.target_runtime_effect,
            "mechanism_changes": [
                _mechanism_change_anchor(change)
                for change in getattr(hypothesis, "mechanism_changes", ()) or ()
            ],
            "novelty_signature": dict(hypothesis.novelty_signature or {}),
            "hypothesis_text_excerpt": _limit_string(
                hypothesis.hypothesis_text,
                360,
            ),
            "target_weakness_excerpt": _limit_string(
                hypothesis.target_weakness,
                240,
            ),
            "expected_effect_excerpt": _limit_string(
                hypothesis.expected_effect,
                240,
            ),
        }
    )


def _mechanism_change_anchor(change: Any) -> dict[str, str]:
    if isinstance(change, Mapping):
        raw = change
        return _drop_empty_identity_fields(
            {
                "id": str(raw.get("id") or ""),
                "name": str(raw.get("name") or ""),
                "change_type": str(raw.get("change_type") or raw.get("action") or ""),
                "target": str(raw.get("target") or raw.get("target_file") or ""),
            }
        )
    return _drop_empty_identity_fields(
        {
            "id": str(getattr(change, "id", "") or ""),
            "name": str(getattr(change, "name", "") or ""),
            "change_type": str(
                getattr(change, "change_type", "")
                or getattr(change, "action", "")
                or ""
            ),
            "target": str(
                getattr(change, "target", "")
                or getattr(change, "target_file", "")
                or ""
            ),
        }
    )


def _drop_empty_identity_fields(value: dict[str, str]) -> dict[str, str]:
    return {
        key: item
        for key, item in value.items()
        if item not in (None, "", [], {}, ())
    }


def _hypothesis_prompt_call_kind(
    *,
    attempt: int,
    semantic_rejections: list[Mapping[str, Any]],
    preview_rejections: list[Mapping[str, Any]],
    grounding_rejections: list[Mapping[str, Any]] | None = None,
) -> str:
    if attempt <= 1:
        return "hypothesis"
    previous_attempt = attempt - 1
    grounding_rejections = grounding_rejections or []
    if grounding_rejections and int(grounding_rejections[-1].get("attempt") or 0) == (
        previous_attempt
    ):
        return "hypothesis_grounding_retry"
    if preview_rejections and int(preview_rejections[-1].get("attempt") or 0) == (
        previous_attempt
    ):
        return "hypothesis_preview_retry"
    if semantic_rejections and int(semantic_rejections[-1].get("attempt") or 0) == (
        previous_attempt
    ):
        return "hypothesis_semantic_retry"
    if preview_rejections:
        return "hypothesis_preview_retry"
    if semantic_rejections:
        return "hypothesis_semantic_retry"
    if grounding_rejections:
        return "hypothesis_grounding_retry"
    return "hypothesis_retry"


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
