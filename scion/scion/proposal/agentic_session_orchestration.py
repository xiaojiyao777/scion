
"""Top-level APS orchestration phases."""
from __future__ import annotations

from scion.proposal.agentic_session_common import *


class AgenticSessionOrchestrationMixin:
    def _start_run_state(
        self,
        request: AgenticProposalRequest,
    ) -> tuple[str, AgenticProposalSessionState, list[AgenticEvidenceRef], list[ProposalObservation]]:
        session_id = str(uuid.uuid4())
        idempotency_key = self.idempotency_key_for_request(request)
        state = AgenticProposalSessionState(
            session_id=session_id,
            request_id=session_id,
            idempotency_key=idempotency_key,
            campaign_id=request.campaign_id,
            branch_id=request.branch.branch_id,
            tool_loop_config=_tool_loop_config_payload(self._tool_loop_config),
        )
        state.note(
            AgenticProposalPhase.ORIENT,
            "Loaded exposure-controlled proposal context.",
        )
        state.note(
            AgenticProposalPhase.DIAGNOSE,
            "Prepared deterministic APS-1 proposal path.",
        )
        return session_id, state, [], []

    def _prepare_tool_context_or_output(
        self,
        *,
        request: AgenticProposalRequest,
        session_id: str,
        state: AgenticProposalSessionState,
        evidence: list[AgenticEvidenceRef],
        observations: list[ProposalObservation],
    ) -> tuple[ProposalToolContext | None, AgenticProposalOutput | None]:
        if self._session_timeout_reached(state):
            output = self._timeout_output(request, state, evidence_used=tuple(evidence))
            state.status = output.status
            return None, self._persist(output, state)

        if self.tool_registry is None:
            return None, None

        if request.tool_context is None:
            output = self._failed_output(
                request=request,
                session_id=session_id,
                status=AgenticProposalStatus.FAILED,
                termination_reason=AgenticTerminationReason.UNHANDLED_ERROR,
                detail=(
                    "AgenticProposalSession requires ProposalToolContext "
                    "when a ProposalToolRegistry is configured"
                ),
            )
            state.status = output.status
            state.note(
                AgenticProposalPhase.FINALIZE,
                "Session failed before proposal generation because tool context was missing.",
            )
            return None, self._persist(output, state)

        tool_context = replace(
            request.tool_context,
            session_id=session_id,
            campaign_id=request.campaign_id,
            branch=request.branch,
            champion=request.champion,
            problem_id=request.problem_id or request.tool_context.problem_id,
            problem_spec_hash=(
                request.problem_spec_hash or request.tool_context.problem_spec_hash
            ),
        )
        initial_observations = self._run_initial_tool_loop(tool_context, state)
        observations.extend(initial_observations)
        evidence.extend(_evidence_from_observations(initial_observations))

        if state.loop_stop_reason == "session_timeout":
            output = self._timeout_output(request, state, evidence_used=tuple(evidence))
            state.status = output.status
            return tool_context, self._persist(output, state)

        fatal_observation_error = self._fatal_observation_error(observations)
        if fatal_observation_error is None:
            fatal_observation_error = self._missing_required_context_error(
                observations,
                context=tool_context,
            )
        if fatal_observation_error is None:
            return tool_context, None

        termination_reason = (
            AgenticTerminationReason.TOOL_LOOP_LIMIT
            if state.loop_stop_reason == "tool_loop_limit"
            else AgenticTerminationReason.HYPOTHESIS_GENERATION_FAILED
        )
        output = self._failed_output(
            request=request,
            session_id=session_id,
            status=AgenticProposalStatus.FAILED,
            termination_reason=termination_reason,
            detail=fatal_observation_error,
            evidence_used=tuple(evidence),
        )
        state.status = output.status
        state.note(
            AgenticProposalPhase.FINALIZE,
            "Session failed closed after required proposal tool observation error.",
            metadata={"detail": fatal_observation_error},
        )
        return tool_context, self._persist(output, state)

    def _preflight_output_or_none(
        self,
        *,
        request: AgenticProposalRequest,
        session_id: str,
        state: AgenticProposalSessionState,
    ) -> AgenticProposalOutput | None:
        if self._injected_output is not None:
            output = self._resolve_injected_output(request, session_id)
            state.status = output.status
            state.note(
                AgenticProposalPhase.FINALIZE,
                "Finalized injected agentic proposal output.",
                metadata={"status": _enum_value(output.status)},
            )
            return self._persist(output, state)

        if self._creative is not None:
            return None

        output = self._failed_output(
            request=request,
            session_id=session_id,
            status=AgenticProposalStatus.FAILED,
            termination_reason=AgenticTerminationReason.UNHANDLED_ERROR,
            detail="AgenticProposalSession requires a creative layer or injected output",
        )
        state.status = output.status
        state.note(
            AgenticProposalPhase.FINALIZE,
            "Session failed before proposal generation.",
        )
        return self._persist(output, state)

    def _prepare_hypothesis_or_output(
        self,
        *,
        request: AgenticProposalRequest,
        session_id: str,
        state: AgenticProposalSessionState,
        tool_context: ProposalToolContext | None,
        observations: list[ProposalObservation],
        evidence: list[AgenticEvidenceRef],
    ) -> tuple[HypothesisProposal | None, AgenticProposalOutput | None]:
        hypothesis = request.approved_hypothesis
        if hypothesis is None:
            hypothesis, early_output = self._generate_hypothesis_with_semantic_retries(
                request=request,
                session_id=session_id,
                state=state,
                tool_context=tool_context,
                observations=observations,
                evidence=evidence,
            )
            if early_output is not None:
                return None, early_output
            if hypothesis is None:
                output = self._failed_output(
                    request=request,
                    session_id=session_id,
                    status=AgenticProposalStatus.FAILED,
                    termination_reason=AgenticTerminationReason.HYPOTHESIS_GENERATION_FAILED,
                    detail="hypothesis generation failed",
                    evidence_used=tuple(evidence),
                    failure_category=AgenticFailureCategory.SCHEMA_OUTPUT_FAILURE,
                )
                state.status = output.status
                return None, self._persist(output, state)
            output = self._check_generated_hypothesis_and_maybe_pause(
                request=request,
                session_id=session_id,
                state=state,
                tool_context=tool_context,
                hypothesis=hypothesis,
                observations=observations,
                evidence=evidence,
            )
            return (None, output) if output is not None else (hypothesis, None)

        output = self._check_approved_hypothesis_before_code(
            request=request,
            session_id=session_id,
            state=state,
            tool_context=tool_context,
            hypothesis=hypothesis,
            observations=observations,
            evidence=evidence,
        )
        return (None, output) if output is not None else (hypothesis, None)

    def _check_generated_hypothesis_and_maybe_pause(
        self,
        *,
        request: AgenticProposalRequest,
        session_id: str,
        state: AgenticProposalSessionState,
        tool_context: ProposalToolContext | None,
        hypothesis: HypothesisProposal,
        observations: list[ProposalObservation],
        evidence: list[AgenticEvidenceRef],
    ) -> AgenticProposalOutput | None:
        if tool_context is not None:
            output = self._run_hypothesis_preview_gate(
                request=request,
                session_id=session_id,
                state=state,
                tool_context=tool_context,
                hypothesis=hypothesis,
                observations=observations,
                evidence=evidence,
                finalize_message="Hypothesis self-check failed closed before approval.",
            )
            if output is not None:
                return output

        if request.approve_hypothesis is None:
            output = self._partial_hypothesis_output(
                request=request,
                session_id=session_id,
                hypothesis=hypothesis,
                detail="hypothesis awaits ContractGate approval",
                termination_reason=AgenticTerminationReason.HYPOTHESIS_AWAITING_APPROVAL,
                evidence_used=tuple(evidence),
                self_check=self._self_check_from_authoritative_previews(
                    observations,
                    state,
                ),
                failure_category=AgenticFailureCategory.CONTRACT_BOUNDARY_FAILURE,
            )
            state.status = output.status
            state.note(
                AgenticProposalPhase.FINALIZE,
                "Session paused before code context until hypothesis approval.",
                metadata={
                    "selected_surface": hypothesis.change_locus,
                    "action": hypothesis.action,
                },
            )
            return self._persist(output, state)

        state.note(
            AgenticProposalPhase.SELF_CHECK,
            "Validating hypothesis before code context.",
            metadata={
                "selected_surface": hypothesis.change_locus,
                "action": hypothesis.action,
            },
        )
        try:
            approval = request.approve_hypothesis(hypothesis)
        except Exception as exc:
            output = self._partial_hypothesis_output(
                request=request,
                session_id=session_id,
                hypothesis=hypothesis,
                detail=str(exc),
                termination_reason=AgenticTerminationReason.HYPOTHESIS_APPROVAL_FAILED,
                evidence_used=tuple(evidence),
                self_check=self._self_check_from_authoritative_previews(
                    observations,
                    state,
                ),
            )
            state.status = output.status
            state.note(
                AgenticProposalPhase.FINALIZE,
                "Hypothesis approval failed before code context.",
                metadata={"error": type(exc).__name__},
            )
            return self._persist(output, state)

        if getattr(approval, "passed", False):
            return None

        output = self._partial_hypothesis_output(
            request=request,
            session_id=session_id,
            hypothesis=hypothesis,
            detail=getattr(approval, "failure_reason", None)
            or "hypothesis approval failed",
            termination_reason=AgenticTerminationReason.HYPOTHESIS_APPROVAL_FAILED,
            evidence_used=tuple(evidence),
            self_check=self._self_check_from_authoritative_previews(
                observations,
                state,
            ),
            failure_category=AgenticFailureCategory.CONTRACT_BOUNDARY_FAILURE,
        )
        state.status = output.status
        state.note(
            AgenticProposalPhase.FINALIZE,
            "Hypothesis approval rejected before code context.",
        )
        return self._persist(output, state)

    def _check_approved_hypothesis_before_code(
        self,
        *,
        request: AgenticProposalRequest,
        session_id: str,
        state: AgenticProposalSessionState,
        tool_context: ProposalToolContext | None,
        hypothesis: HypothesisProposal,
        observations: list[ProposalObservation],
        evidence: list[AgenticEvidenceRef],
    ) -> AgenticProposalOutput | None:
        if tool_context is None:
            return None

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
                "Approved hypothesis violated the forced research-surface constraint.",
                metadata={"detail": forced_violation},
            )
            return self._persist(output, state)

        if _is_solver_design_hypothesis(hypothesis):
            output = self._check_approved_solver_design_grounding(
                request=request,
                session_id=session_id,
                state=state,
                tool_context=tool_context,
                hypothesis=hypothesis,
                observations=observations,
                evidence=evidence,
            )
            if output is not None:
                return output

        return self._run_hypothesis_preview_gate(
            request=request,
            session_id=session_id,
            state=state,
            tool_context=tool_context,
            hypothesis=hypothesis,
            observations=observations,
            evidence=evidence,
            finalize_message=(
                "Approved hypothesis self-check failed closed before code context."
            ),
        )

    def _check_approved_solver_design_grounding(
        self,
        *,
        request: AgenticProposalRequest,
        session_id: str,
        state: AgenticProposalSessionState,
        tool_context: ProposalToolContext,
        hypothesis: HypothesisProposal,
        observations: list[ProposalObservation],
        evidence: list[AgenticEvidenceRef],
    ) -> AgenticProposalOutput | None:
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
                metadata={"detail": grounding_error},
            )
            return self._persist(output, state)

        return self._mechanism_novelty_failed_output(
            request=request,
            session_id=session_id,
            state=state,
            hypothesis=hypothesis,
            observations=observations,
            evidence_used=tuple(evidence),
        )

    def _run_hypothesis_preview_gate(
        self,
        *,
        request: AgenticProposalRequest,
        session_id: str,
        state: AgenticProposalSessionState,
        tool_context: ProposalToolContext,
        hypothesis: HypothesisProposal,
        observations: list[ProposalObservation],
        evidence: list[AgenticEvidenceRef],
        finalize_message: str,
    ) -> AgenticProposalOutput | None:
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
        self_check = self._self_check_from_authoritative_previews(observations, state)
        self_check_detail = _self_check_failure_detail(
            self_check,
            require_schema_preview=_self_check_required(tool_context),
            require_contract_preview=False,
        )
        if self_check_detail is None:
            return None

        _record_failure_ledger_entry(
            state,
            phase=AgenticProposalPhase.SELF_CHECK,
            category=_preview_failure_category(preview_observations),
            detail=self_check_detail,
            source="hypothesis_preview_failure",
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
            finalize_message,
            metadata={"detail": self_check_detail},
        )
        return self._persist(output, state)
