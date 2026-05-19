"""AgenticSessionHypothesis mixin."""
from __future__ import annotations

from scion.proposal.agentic_session_common import *


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
            max_attempts = 1 + _MAX_HYPOTHESIS_SEMANTIC_RETRIES
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
                            attempt=attempt,
                        )
                    )
                    self._record_prompt_manifest(
                        state,
                        call_kind=(
                            "hypothesis"
                            if attempt == 1
                            else "hypothesis_semantic_retry"
                            if semantic_rejections
                            else "hypothesis_preview_retry"
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
                    max_attempts=max_attempts,
                )
                if novelty_output is not None:
                    return None, novelty_output
                if len(semantic_rejections) >= attempt:
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
                    max_attempts=max_attempts,
                )
                if preview_output is not None:
                    return None, preview_output
                if len(preview_rejections) > preview_feedback_count:
                    continue
                return hypothesis, None
            return None, None

    def _hypothesis_prompt_context(
            self,
            *,
            request: AgenticProposalRequest,
            tool_context: ProposalToolContext | None,
            observations: list[ProposalObservation],
            semantic_rejections: list[Mapping[str, Any]],
            preview_rejections: list[Mapping[str, Any]],
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
                    "Choose a different mechanism family; do not relabel the same "
                    "premise, novelty text, or target mechanism."
                )
                hypothesis_context["agentic_hypothesis_retry_attempt"] = attempt
            if preview_rejections:
                hypothesis_context["agentic_hypothesis_preview_rejections"] = [
                    _sanitize_agentic_value(rejection)
                    for rejection in preview_rejections
                ]
                hypothesis_context["agentic_hypothesis_preview_retry_rule"] = (
                    "A schema/target preview rejected the previous hypothesis. "
                    "Repair the exact structured field named by the failed check; "
                    "do not change the research goal just to silence the preview."
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
                hypothesis_context["agentic_tool_observations"] = [
                    _observation_prompt_payload(observation)
                    for observation in prompt_observations
                ]
            else:
                prompt_observations = []
            return hypothesis_context, prompt_observations

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
            max_attempts: int,
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
            )
            if retry_feedback is not None and attempt < max_attempts:
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
            max_attempts: int,
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
            if attempt < max_attempts:
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
    c11_detail = _failed_schema_check_detail(
        hypothesis,
        "C11_expected_telemetry",
    )
    telemetry_detail = str(telemetry.get("detail") or "").strip()
    if bool(telemetry.get("passed")) is not False and not c11_detail:
        return None
    if "C11_expected_telemetry" not in (c11_detail or detail):
        return None

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
            "reason": _limit_string(telemetry_detail or c11_detail or detail, 1000),
            "requested_activation_fields": list(requested_activation),
            "declared_runtime_fields": _compact_preview_list(
                telemetry.get("declared_runtime_fields"),
                limit=20,
                max_chars=120,
            ),
            "declared_mechanism_runtime_fields": _compact_preview_list(
                telemetry.get("declared_mechanism_runtime_fields"),
                limit=20,
                max_chars=160,
            ),
            "retry_constraint": (
                "Repair expected_telemetry.activation with exact declared "
                "mechanism-specific activation records. Do not use existing "
                "phase names such as `.vns` unless that exact mechanism id is "
                "declared in mechanism_changes; prefer "
                "`solver_algorithm_context_records.<mechanism_id>_iterations` "
                "or `solver_algorithm_phase_runtime_ms.<mechanism_id>`."
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
