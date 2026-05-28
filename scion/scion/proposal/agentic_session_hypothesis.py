"""AgenticSessionHypothesis mixin."""
from __future__ import annotations

import re
from typing import Any, Mapping

from scion.problem.providers import active_subject_taxonomy_payload
from scion.proposal.agentic_session_common import *
from scion.proposal.negative_facts import render_negative_fact_block
from scion.runtime.telemetry_guard import expected_telemetry_template


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
                + (
                    _MAX_HYPOTHESIS_GROUNDING_RETRIES
                    * _MAX_HYPOTHESIS_GROUNDING_TARGET_KEYS
                )
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
                        tool_context=tool_context,
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
            tool_context: ProposalToolContext | None,
            hypothesis: HypothesisProposal,
            evidence: list[AgenticEvidenceRef],
            preview_rejections: list[Mapping[str, Any]],
            attempt: int,
        ) -> AgenticProposalOutput | None:
            structural_activation_refs = _active_subject_telemetry_activation_refs(
                tool_context,
                surface=getattr(hypothesis, "change_locus", None),
            )
            drift = _schema_retry_preservation_drift(
                hypothesis,
                preview_rejections,
                attempt=attempt,
                structural_activation_refs=structural_activation_refs,
            )
            if drift is None:
                return None
            feedback = _schema_retry_drift_feedback(
                drift,
                hypothesis,
                attempt=attempt,
                structural_activation_refs=structural_activation_refs,
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
            telemetry_guidance = _expected_telemetry_guidance_for_hypothesis(
                tool_context,
            )
            if telemetry_guidance:
                hypothesis_context["agentic_expected_telemetry_guidance"] = (
                    telemetry_guidance
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
                elif _same_mechanism_preview_retry_pending(preview_rejections):
                    hypothesis_context["agentic_hypothesis_preview_retry_rule"] = (
                        "SAME-MECHANISM BRANCH RETRY. The selected branch is "
                        "same_mechanism_only, so replace any unrelated "
                        "mechanism_changes ids with one of the protected ids "
                        "from the feedback. The only valid task is tune, "
                        "integrate, repair, parameterize, or telemetry wiring "
                        "inside the protected mechanism. A genuinely different "
                        "mechanism requires a clean branch/fork before "
                        "hypothesis generation."
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
            active_grounding_rejections = _active_grounding_rejections_for_prompt(
                grounding_rejections,
                semantic_rejections=semantic_rejections,
                preview_rejections=preview_rejections,
            )
            if active_grounding_rejections:
                hypothesis_context["agentic_hypothesis_grounding_rejections"] = [
                    _sanitize_agentic_value(rejection)
                    for rejection in active_grounding_rejections
                ]
                latest_grounding = active_grounding_rejections[-1]
                target_file = str(latest_grounding.get("target_file") or "").strip()
                hypothesis_context["agentic_hypothesis_grounding_retry_rule"] = (
                    "The previous solver_design hypothesis selected an existing "
                    "target_file whose full source was not visible in the API "
                    "prompt that generated it. This grounding feedback is scoped "
                    f"to target_file={target_file!r}; do not use source from a "
                    "different target_file as grounding. The target file has now "
                    "been read and is projected into this API-visible prompt. "
                    "Redraft only after using that target-file observation. If "
                    "separate semantic feedback requires changing to a different "
                    "existing target_file, Scion must ground that new target in "
                    "a later prompt before approval."
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
            if _prompt_observations_include_sufficient_target_context(
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
            target_context = _target_context_summary_from_observations(
                observations,
                target_read_args,
            )
            target_context_key = _target_grounding_context_key(
                target_read_args,
                target_context,
            )
            target_retry_count = _grounding_rejection_count_for_target_context(
                grounding_rejections,
                target_context_key,
            )
            if (
                _observations_include_sufficient_target_context(
                    observations,
                    target_read_args,
                )
                and target_retry_count < _MAX_HYPOTHESIS_GROUNDING_RETRIES
                and _distinct_grounding_target_key_count(
                    grounding_rejections,
                    additional_key=target_context_key,
                )
                <= _MAX_HYPOTHESIS_GROUNDING_TARGET_KEYS
            ):
                grounding_rejections.append(
                    _solver_design_target_prompt_grounding_feedback(
                        hypothesis,
                        target_read_args,
                        attempt=attempt,
                        target_context=target_context,
                        target_context_key=target_context_key,
                        retry_count_for_target=target_retry_count + 1,
                    )
                )
                state.note(
                    AgenticProposalPhase.DRAFT_HYPOTHESIS,
                    "Solver-design target file was read after hypothesis generation; retrying with target source visible in the hypothesis prompt.",
                    metadata={
                        "attempt": attempt,
                        "target_file": target_read_args.get("file_path"),
                        "target_context_key": target_context_key,
                        "target_context_digest": target_context.get(
                            "content_digest"
                        ),
                        "target_retry_count": target_retry_count + 1,
                        "api_visible_in_latest_prompt": False,
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
                    "hypothesis prompt did not include a sufficiently complete "
                    "provider-declared target-file context observation for that "
                    "file. "
                    f"target_context_key={target_context_key!r}; "
                    f"target_context_digest={target_context.get('content_digest')!r}; "
                    "api_visible_in_latest_prompt=False; "
                    f"retry_count_for_target={target_retry_count}; "
                    f"distinct_grounding_target_count={_distinct_grounding_target_key_count(grounding_rejections)}."
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
                metadata={
                    "detail": detail,
                    "attempt": attempt,
                    "target_file": target_read_args.get("file_path"),
                    "target_context_key": target_context_key,
                    "target_context_digest": target_context.get("content_digest"),
                    "api_visible_in_latest_prompt": False,
                    "retry_count_for_target": target_retry_count,
                },
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
            if not result.is_hard_block:
                _record_mechanism_novelty_diagnostic(
                    state,
                    hypothesis=hypothesis,
                    result=result,
                    attempt=attempt,
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
            result = _MECHANISM_NOVELTY_GATE.evaluate(
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
) -> None:
    diagnostic = result.to_diagnostic(hypothesis)
    state.note(
        AgenticProposalPhase.DRAFT_HYPOTHESIS,
        "Mechanism duplicate diagnostic recorded; continuing without hard novelty block.",
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
            }
        ),
    )


def _expected_telemetry_guidance_for_hypothesis(
    context: ProposalToolContext | None,
) -> dict[str, Any]:
    if context is None:
        return {}
    surfaces: list[str] = []
    forced = str(getattr(context, "forced_surface", "") or "").strip()
    if forced:
        surfaces.append(forced)
    for surface in getattr(context, "active_problem_boundary_surfaces", ()) or ():
        text = str(surface or "").strip()
        if text and text not in surfaces:
            surfaces.append(text)
    if not surfaces:
        return {}
    templates: dict[str, Any] = {}
    for surface in surfaces[:4]:
        template = expected_telemetry_template(
            problem_spec=getattr(context, "problem_spec", None),
            selected_surface=surface,
            declared_mechanisms=("<mechanism_id>",),
            max_fields_per_category=4,
        )
        if template:
            templates[surface] = template
    if not templates:
        return {}
    return _drop_empty_dict(
        {
            "schema_version": "agentic-expected-telemetry-guidance.v1",
            "source": "adapter_declared_runtime_fields",
            "templates_by_surface": templates,
            "rule": (
                "Use only these top-level categories: activity, activation, "
                "effect, budget. Replace <mechanism_id> or {mechanism} with the "
                "exact mechanism_changes id before finalizing the hypothesis."
            ),
            "preview_helper": (
                "Use proposal.schema_preview if unsure; it returns the exact "
                "C11_expected_telemetry repair template without lowering schema "
                "strictness."
            ),
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
            "telemetry_category_guidance": problem_telemetry.get(
                "telemetry_category_guidance"
            ),
            "allowed_repair_shape": problem_telemetry.get("allowed_repair_shape"),
            "forbidden_repair_shape": problem_telemetry.get("forbidden_repair_shape"),
            "final_task": (
                problem_telemetry.get("allowed_repair_shape")
                or "Repair the expected_telemetry contract for the same mechanism."
            ),
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
                "and use a clean branch/fork before generation."
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


def _schema_retry_preservation_drift(
    hypothesis: HypothesisProposal,
    preview_rejections: list[Mapping[str, Any]],
    *,
    attempt: int,
    structural_activation_refs: set[str] | None = None,
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
        structural_activation_refs=structural_activation_refs,
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


def _same_mechanism_preview_retry_pending(
    preview_rejections: list[Mapping[str, Any]],
) -> bool:
    if not preview_rejections:
        return False
    return (
        str(preview_rejections[-1].get("failure_code") or "").strip()
        == "same_mechanism_only_violation"
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
        "novelty_signature_missing_fields",
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
    structural_activation_refs: set[str] | None = None,
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
            "observed_identity": _schema_retry_observed_identity(
                hypothesis,
                structural_activation_refs=structural_activation_refs,
            ),
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
        "schema_retry_drift: schema/novelty retry changed protected hypothesis "
        f"identity fields ({fields or 'unknown'}). Schema/telemetry/novelty retries "
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
    *,
    structural_activation_refs: set[str] | None = None,
) -> dict[str, Any]:
    anchor = _hypothesis_retry_anchor(hypothesis)
    return _drop_empty_dict(
        {
            "action": anchor.get("action"),
            "target_file": anchor.get("target_file"),
            "mechanism_changes": anchor.get("mechanism_changes"),
            "activation_refs": sorted(
                _telemetry_activation_mechanism_refs(
                    getattr(hypothesis, "expected_telemetry", {}) or {},
                    structural_activation_refs=structural_activation_refs,
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
    *,
    structural_activation_refs: set[str] | None = None,
) -> dict[str, Any]:
    protected_ids = _protected_mechanism_ids(expected_anchor)
    if not protected_ids:
        return {}
    observed_refs = _telemetry_activation_mechanism_refs(
        getattr(hypothesis, "expected_telemetry", {}) or {},
        structural_activation_refs=structural_activation_refs,
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


def _telemetry_activation_mechanism_refs(
    expected_telemetry: Any,
    *,
    structural_activation_refs: set[str] | None = None,
) -> set[str]:
    if not isinstance(expected_telemetry, Mapping):
        return set()
    activation = expected_telemetry.get("activation")
    text_items = _flatten_telemetry_activation_items(activation)
    refs: set[str] = set()
    for item in text_items:
        refs.update(_mechanism_refs_from_telemetry_path(item))
    structural_refs = structural_activation_refs or set()
    return {ref for ref in refs if ref not in structural_refs}


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


def _active_subject_telemetry_activation_refs(
    context: ProposalToolContext | None,
    *,
    surface: str | None,
) -> set[str]:
    if context is None:
        return set()
    taxonomy = active_subject_taxonomy_payload(
        context=context,
        problem_spec=getattr(context, "problem_spec", None),
        adapter=getattr(context, "adapter", None),
        surface=surface,
    )
    return {
        _mechanism_ref_token(item)
        for item in taxonomy.get("telemetry_activation_refs", ()) or ()
        if _mechanism_ref_token(item)
    }


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
    target_context: Mapping[str, Any] | None = None,
    target_context_key: str = "",
    retry_count_for_target: int = 0,
) -> dict[str, Any]:
    target_file = str(target_read_args.get("file_path") or "").strip()
    target_context = dict(target_context or {})
    coverage_status = str(target_context.get("coverage_status") or "").strip()
    retry_constraint = (
        "Use the newly visible full context.read_algorithm_file content "
        f"for {target_file}. Redraft the same target/mechanism only after "
        "checking that file; do not proceed from a read receipt or "
        "post-hoc grounding observation."
    )
    if coverage_status == "truncated":
        retry_constraint = (
            "Use the newly visible truncated context.read_algorithm_file "
            f"context for {target_file}, including its digest and line coverage. "
            "Acknowledge the visible line range and avoid claims that require "
            "unseen source; request a narrower symbol/slice later only if the "
            "visible target context is insufficient."
        )
    return _drop_empty_dict(
        {
            "attempt": attempt,
            "source": "solver_design_target_prompt_grounding",
            "failure_code": "solver_design_target_not_in_hypothesis_prompt",
            "failure_category": AgenticFailureCategory.CONTRACT_BOUNDARY_FAILURE.value,
            "target_file": target_file,
            "target_context_key": target_context_key,
            "target_context_digest": target_context.get("content_digest"),
            "api_visible_in_latest_prompt": False,
            "retry_count_for_target": retry_count_for_target,
            "reason": (
                "The previous solver_design hypothesis selected an existing "
                "target_file, but sufficiently complete target-file context was "
                "not included in the API-visible prompt that generated it."
            ),
            "target_context": target_context,
            "preserve_hypothesis": _hypothesis_retry_anchor(hypothesis),
            "retry_constraint": retry_constraint,
        }
    )


def _target_grounding_context_key(
    target_read_args: Mapping[str, Any],
    target_context: Mapping[str, Any] | None = None,
) -> str:
    target_file = _normalize_prompt_grounding_path(target_read_args.get("file_path"))
    context = target_context or {}
    digest = str(
        context.get("content_digest")
        or context.get("digest")
        or target_read_args.get("source_digest")
        or ""
    ).strip()
    if digest:
        return f"{target_file}@{digest}"
    coverage = str(context.get("coverage_status") or "").strip()
    size_chars = str(context.get("size_chars") or "").strip()
    max_chars = str(target_read_args.get("max_chars") or "").strip()
    return f"{target_file}@{coverage}:{size_chars}:{max_chars}"


def _grounding_rejection_count_for_target_context(
    grounding_rejections: list[Mapping[str, Any]],
    target_context_key: str,
) -> int:
    return sum(
        1
        for rejection in grounding_rejections
        if str(rejection.get("target_context_key") or "") == target_context_key
    )


def _distinct_grounding_target_key_count(
    grounding_rejections: list[Mapping[str, Any]],
    *,
    additional_key: str | None = None,
) -> int:
    keys = {
        str(rejection.get("target_context_key") or "").strip()
        for rejection in grounding_rejections
        if str(rejection.get("target_context_key") or "").strip()
    }
    if additional_key:
        keys.add(str(additional_key).strip())
    return len(keys)


def _active_grounding_rejections_for_prompt(
    grounding_rejections: list[Mapping[str, Any]],
    *,
    semantic_rejections: list[Mapping[str, Any]],
    preview_rejections: list[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    if not grounding_rejections:
        return []
    latest_semantic_or_preview_attempt = max(
        [
            int(rejection.get("attempt") or 0)
            for rejection in [*semantic_rejections, *preview_rejections]
        ]
        or [0]
    )
    active = [
        rejection
        for rejection in grounding_rejections
        if int(rejection.get("attempt") or 0) >= latest_semantic_or_preview_attempt
    ]
    return active[-1:] if active else []


def _prompt_observations_include_sufficient_target_context(
    prompt_observations: list[ProposalObservation],
    target_read_args: Mapping[str, Any],
) -> bool:
    return _observations_include_sufficient_target_context(
        prompt_observations,
        target_read_args,
    )


def _observations_include_sufficient_target_context(
    observations: list[ProposalObservation],
    target_read_args: Mapping[str, Any],
) -> bool:
    return (
        _observations_include_full_target_file(observations, target_read_args)
        or _observations_include_bounded_target_file_context(
            observations,
            target_read_args,
        )
        or _observations_include_full_target_slice_context(
            observations,
            target_file=target_read_args.get("file_path"),
        )
    )


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


def _observations_include_bounded_target_file_context(
    observations: list[ProposalObservation],
    target_read_args: Mapping[str, Any],
) -> bool:
    target_context = _target_context_summary_from_observations(
        observations,
        target_read_args,
    )
    if not target_context:
        return False
    if target_context.get("coverage_status") == "full":
        return True
    if target_context.get("coverage_status") != "truncated":
        return False
    return bool(
        target_context.get("content_digest")
        and target_context.get("line_start") == 1
        and target_context.get("line_end")
        and target_context.get("covered_line_count")
        and target_context.get("total_line_count")
    )


def _observations_include_full_target_slice_context(
    observations: list[ProposalObservation],
    *,
    target_file: Any,
) -> bool:
    target_path = _normalize_prompt_grounding_path(target_file)
    if not target_path:
        return False
    for observation in observations:
        if observation.is_error or observation.tool_name != "context.read_algorithm_slice":
            continue
        payload = observation.structured_payload
        if not isinstance(payload, Mapping):
            continue
        if not payload.get("available", True):
            continue
        if _normalize_prompt_grounding_path(payload.get("file_path")) != target_path:
            continue
        coverage_status = str(
            payload.get("coverage_status") or payload.get("coverage") or ""
        ).strip()
        if coverage_status == "full" and str(payload.get("content") or "").strip():
            return True
    return False


def _target_context_summary_from_observations(
    observations: list[ProposalObservation],
    target_read_args: Mapping[str, Any],
) -> dict[str, Any]:
    target_path = _normalize_prompt_grounding_path(target_read_args.get("file_path"))
    if not target_path:
        return {}
    for observation in reversed(observations):
        if observation.is_error or observation.tool_name != "context.read_algorithm_file":
            continue
        payload = observation.structured_payload
        if not isinstance(payload, Mapping):
            continue
        if _normalize_prompt_grounding_path(payload.get("file_path")) != target_path:
            continue
        content_preview = str(payload.get("content_preview") or "")
        if not bool(payload.get("readable")) or not content_preview:
            return {}
        truncated = bool(payload.get("truncated"))
        total_line_count = _coerce_nonnegative_int(payload.get("total_line_count"))
        covered_line_count = _coerce_nonnegative_int(payload.get("covered_line_count"))
        if total_line_count is None:
            total_line_count = len(content_preview.splitlines())
        if covered_line_count is None:
            covered_line_count = len(content_preview.splitlines())
        line_end = _coerce_nonnegative_int(payload.get("line_end"))
        if line_end is None and covered_line_count:
            line_end = covered_line_count
        content_digest = str(
            payload.get("content_digest")
            or payload.get("sha256")
            or payload.get("digest")
            or ""
        ).strip()
        return _drop_empty_dict(
            {
                "tool_name": observation.tool_name,
                "observation_id": observation.observation_id,
                "file_path": target_path,
                "coverage_status": "truncated" if truncated else "full",
                "truncated": truncated,
                "size_chars": payload.get("size_chars"),
                "max_chars": payload.get("max_chars"),
                "line_start": payload.get("line_start") or 1,
                "line_end": line_end,
                "covered_line_count": covered_line_count,
                "total_line_count": total_line_count,
                "content_digest": content_digest,
                "digest": payload.get("digest"),
                "source": payload.get("source"),
            }
        )
    return {}


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
