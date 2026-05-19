
"""Code-generation, patch validation, preview, and finalization phases."""
from __future__ import annotations

from scion.proposal.agentic_session_common import *


class AgenticSessionPatchFlowMixin:
    def _build_initial_patch_or_output(
        self,
        *,
        request: AgenticProposalRequest,
        session_id: str,
        state: AgenticProposalSessionState,
        tool_context: ProposalToolContext | None,
        hypothesis: HypothesisProposal,
        observations: list[ProposalObservation],
        evidence: list[AgenticEvidenceRef],
    ) -> tuple[PatchProposal | None, dict[str, Any] | None, int, AgenticProposalOutput | None]:
        state.note(
            AgenticProposalPhase.INSPECT_INTERFACE,
            "Building code context for approved hypothesis.",
            metadata={
                "selected_surface": hypothesis.change_locus,
                "action": hypothesis.action,
            },
        )
        try:
            if self._session_timeout_reached(state):
                output = self._timeout_output(
                    request,
                    state,
                    evidence_used=tuple(evidence),
                )
                state.status = output.status
                return None, None, 0, self._persist(output, state)

            code_context = dict(request.build_code_context(hypothesis))
            if request.resume_context is not None:
                code_context["agentic_resume_context"] = _sanitize_agentic_value(
                    request.resume_context
                )
            if tool_context is not None:
                code_phase_observations = self._run_code_context_tool_loop(
                    tool_context,
                    state,
                    hypothesis,
                    observations,
                    code_context,
                )
                observations.extend(code_phase_observations)
                evidence.extend(_evidence_from_observations(code_phase_observations))
            if observations:
                self._attach_observations_to_code_context(code_context, observations)

            code_context = _with_code_scope_control(
                code_context,
                hypothesis,
                timeout_retry=False,
            )
            if tool_context is not None and self._code_phase_wall_time_reserved(state):
                detail = (
                    "insufficient wall-time reserve before code generation for "
                    "mandatory contract preview and algorithm smoke"
                )
                output = self._partial_hypothesis_output(
                    request=request,
                    session_id=session_id,
                    hypothesis=hypothesis,
                    detail=detail,
                    evidence_used=tuple(evidence),
                    self_check=self._self_check_from_authoritative_previews(
                        observations,
                        state,
                    ),
                    failure_category=AgenticFailureCategory.AGENTIC_BUDGET_CONTROL,
                )
                state.status = output.status
                state.note(
                    AgenticProposalPhase.FINALIZE,
                    "Stopped before code generation to preserve mandatory preview wall-time reserve.",
                    metadata={
                        "detail": detail,
                        "remaining_wall_time_sec": self._remaining_wall_time_sec(
                            state
                        ),
                    },
                )
                return None, code_context, 0, self._persist(output, state)

            state.note(AgenticProposalPhase.DRAFT_PATCH, "Generating patch proposal.")
            patch = self._generate_code_with_timeout_retry(
                state=state,
                hypothesis=hypothesis,
                code_context=code_context,
                observations=observations,
            )
            return patch, code_context, 0, None
        except self._SESSION_ERROR_TYPES as exc:
            failure_category = _structured_output_failure_category(exc)
            output = self._partial_hypothesis_output(
                request=request,
                session_id=session_id,
                hypothesis=hypothesis,
                detail=str(exc),
                evidence_used=tuple(evidence),
                self_check=self._self_check_from_authoritative_previews(
                    observations,
                    state,
                ),
                failure_category=failure_category,
            )
            state.status = output.status
            state.note(
                AgenticProposalPhase.FINALIZE,
                "Patch generation failed after hypothesis draft.",
                metadata={"error": type(exc).__name__},
            )
            return None, None, 0, self._persist(output, state)

    def _attach_observations_to_code_context(
        self,
        code_context: dict[str, Any],
        observations: list[ProposalObservation],
    ) -> None:
        research_diagnosis = _research_diagnosis_from_observations(observations)
        if research_diagnosis:
            code_context["agentic_research_diagnosis"] = research_diagnosis
        code_context["agentic_tool_observations"] = [
            _code_observation_prompt_payload(observation)
            for observation in _code_prompt_observations(observations)
        ]
        active_mechanisms = _active_solver_mechanism_evidence_for_code_context(
            observations
        )
        if active_mechanisms:
            code_context["agentic_active_solver_mechanisms"] = active_mechanisms

    def _validate_patch_or_output(
        self,
        *,
        request: AgenticProposalRequest,
        session_id: str,
        state: AgenticProposalSessionState,
        hypothesis: HypothesisProposal,
        patch: PatchProposal,
        code_context: Mapping[str, Any],
        observations: list[ProposalObservation],
        evidence: list[AgenticEvidenceRef],
        code_repair_attempts_used: int,
    ) -> tuple[PatchProposal | None, int, AgenticProposalOutput | None]:
        if self._session_timeout_reached(state):
            output = self._timeout_output(
                request,
                state,
                evidence_used=tuple(evidence),
            )
            state.status = output.status
            return None, code_repair_attempts_used, self._persist(output, state)

        output = self._premise_rejection_output_if_needed(
            request=request,
            session_id=session_id,
            state=state,
            hypothesis=hypothesis,
            patch=patch,
            evidence=evidence,
            observations=observations,
            source="premise_check",
            note="Code phase rejected the approved hypothesis after premise check.",
            repair_attempt=None,
        )
        if output is not None:
            return None, code_repair_attempts_used, output

        self_reported_issue = _patch_self_reported_unresolved_issue(patch)
        if (
            self_reported_issue is not None
            and code_repair_attempts_used
            < self._tool_loop_config.max_code_repair_attempts
            and not self._session_timeout_reached(state)
        ):
            patch = self._repair_patch_after_code_self_check(
                request=request,
                state=state,
                hypothesis=hypothesis,
                code_context=code_context,
                observations=observations,
                patch=patch,
                issue_detail=self_reported_issue,
                repair_attempt=code_repair_attempts_used + 1,
            )
            code_repair_attempts_used += 1
            output = self._premise_rejection_output_if_needed(
                request=request,
                session_id=session_id,
                state=state,
                hypothesis=hypothesis,
                patch=patch,
                evidence=evidence,
                observations=observations,
                source="premise_check",
                note="Patch repair rejected the approved hypothesis after premise check.",
                repair_attempt=code_repair_attempts_used,
            )
            if output is not None:
                return None, code_repair_attempts_used, output
            self_reported_issue = _patch_self_reported_unresolved_issue(patch)

        if self_reported_issue is None:
            return patch, code_repair_attempts_used, None

        output = self._self_reported_issue_output(
            request=request,
            session_id=session_id,
            state=state,
            hypothesis=hypothesis,
            observations=observations,
            evidence=evidence,
            issue_detail=self_reported_issue,
            source="patch_self_reported_issue",
            note=(
                "Patch generation failed because generated patch self-reported "
                "an unresolved code issue."
            ),
            repair_attempt=None,
        )
        return None, code_repair_attempts_used, output

    def _run_patch_preview_repair_loop(
        self,
        *,
        request: AgenticProposalRequest,
        session_id: str,
        state: AgenticProposalSessionState,
        tool_context: ProposalToolContext,
        hypothesis: HypothesisProposal,
        patch: PatchProposal,
        code_context: Mapping[str, Any],
        observations: list[ProposalObservation],
        evidence: list[AgenticEvidenceRef],
        code_repair_attempts_used: int,
    ) -> tuple[PatchProposal | None, int, AgenticProposalOutput | None]:
        while True:
            patch_preview = self._run_contract_preview_tool(
                tool_context,
                hypothesis,
                patch,
                state,
            )
            observations.append(patch_preview)
            evidence.extend(_evidence_from_observations((patch_preview,)))
            if not _preview_observation_passed(patch_preview):
                result = self._handle_failed_patch_preview(
                    request=request,
                    session_id=session_id,
                    state=state,
                    hypothesis=hypothesis,
                    patch=patch,
                    code_context=code_context,
                    observations=observations,
                    evidence=evidence,
                    failed_preview=patch_preview,
                    repair_attempts_used=code_repair_attempts_used,
                    wall_time_message=(
                        "Stopped Contract-preview repair to preserve mandatory "
                        "preview wall-time reserve."
                    ),
                    budget_message=(
                        "Skipped Contract preview repair because APS budget "
                        "control reserved self-check execution."
                    ),
                    repair_failure_message=(
                        "Patch repair generation failed after Contract preview feedback."
                    ),
                )
                patch, code_repair_attempts_used, output, should_continue = result
                if output is not None:
                    return None, code_repair_attempts_used, output
                if should_continue:
                    continue
                break

            smoke_preview = self._run_algorithm_smoke_tool(
                tool_context,
                hypothesis,
                patch,
                state,
            )
            observations.append(smoke_preview)
            evidence.extend(_evidence_from_observations((smoke_preview,)))
            if _preview_observation_passed(smoke_preview):
                break
            result = self._handle_failed_patch_preview(
                request=request,
                session_id=session_id,
                state=state,
                hypothesis=hypothesis,
                patch=patch,
                code_context=code_context,
                observations=observations,
                evidence=evidence,
                failed_preview=smoke_preview,
                repair_attempts_used=code_repair_attempts_used,
                wall_time_message=(
                    "Stopped algorithm-smoke repair to preserve mandatory "
                    "preview wall-time reserve."
                ),
                budget_message=(
                    "Skipped algorithm-smoke repair because APS budget control "
                    "reserved self-check execution."
                ),
                repair_failure_message=(
                    "Patch repair generation failed after algorithm-smoke feedback."
                ),
            )
            patch, code_repair_attempts_used, output, should_continue = result
            if output is not None:
                return None, code_repair_attempts_used, output
            if should_continue:
                continue
            break
        return patch, code_repair_attempts_used, None

    def _handle_failed_patch_preview(
        self,
        *,
        request: AgenticProposalRequest,
        session_id: str,
        state: AgenticProposalSessionState,
        hypothesis: HypothesisProposal,
        patch: PatchProposal,
        code_context: Mapping[str, Any],
        observations: list[ProposalObservation],
        evidence: list[AgenticEvidenceRef],
        failed_preview: ProposalObservation,
        repair_attempts_used: int,
        wall_time_message: str,
        budget_message: str,
        repair_failure_message: str,
    ) -> tuple[PatchProposal, int, AgenticProposalOutput | None, bool]:
        _record_failure_ledger_entry(
            state,
            phase=AgenticProposalPhase.SELF_CHECK,
            category=_preview_failure_category([failed_preview]),
            detail=_latest_preview_failure_detail([failed_preview]) or failed_preview.summary,
            source="preview_failure",
            tool_name=failed_preview.tool_name,
            observation=failed_preview,
            repair_attempt=repair_attempts_used,
        )
        if self._code_phase_wall_time_reserved(state):
            state.note(
                AgenticProposalPhase.SELF_CHECK,
                wall_time_message,
                metadata={
                    "tool_name": failed_preview.tool_name,
                    "skip_reason": "preview_repair_wall_time_reserved",
                    "repair_attempts_used": repair_attempts_used,
                    "remaining_wall_time_sec": self._remaining_wall_time_sec(state),
                },
            )
            return patch, repair_attempts_used, None, False
        if _preview_skip_is_agentic_budget_control(failed_preview):
            state.note(
                AgenticProposalPhase.SELF_CHECK,
                budget_message,
                metadata={
                    "tool_name": failed_preview.tool_name,
                    "skip_reason": "agentic_budget_control",
                    "repair_attempts_used": repair_attempts_used,
                },
            )
            return patch, repair_attempts_used, None, False
        if (
            repair_attempts_used >= self._tool_loop_config.max_code_repair_attempts
            or self._session_timeout_reached(state)
        ):
            return patch, repair_attempts_used, None, False

        try:
            patch = self._repair_patch_after_preview(
                request=request,
                state=state,
                hypothesis=hypothesis,
                code_context=code_context,
                observations=observations,
                failed_preview=failed_preview,
                repair_attempt=repair_attempts_used + 1,
            )
            repair_attempts_used += 1
        except self._SESSION_ERROR_TYPES as exc:
            output = self._partial_hypothesis_output(
                request=request,
                session_id=session_id,
                hypothesis=hypothesis,
                detail=str(exc),
                evidence_used=tuple(evidence),
                self_check=self._self_check_from_authoritative_previews(
                    observations,
                    state,
                ),
                failure_category=_structured_output_failure_category(exc),
            )
            state.status = output.status
            state.note(
                AgenticProposalPhase.FINALIZE,
                repair_failure_message,
                metadata={"error": type(exc).__name__},
            )
            return patch, repair_attempts_used, self._persist(output, state), False

        output = self._premise_rejection_output_if_needed(
            request=request,
            session_id=session_id,
            state=state,
            hypothesis=hypothesis,
            patch=patch,
            observations=observations,
            evidence=evidence,
            source="premise_check",
            note="Patch repair rejected the approved hypothesis after premise check.",
            repair_attempt=repair_attempts_used,
        )
        if output is not None:
            return patch, repair_attempts_used, output, False

        self_reported_issue = _patch_self_reported_unresolved_issue(patch)
        if self_reported_issue is None:
            return patch, repair_attempts_used, None, True

        output = self._self_reported_issue_output(
            request=request,
            session_id=session_id,
            state=state,
            hypothesis=hypothesis,
            observations=observations,
            evidence=evidence,
            issue_detail=self_reported_issue,
            source="patch_self_reported_issue",
            note=(
                "Patch repair failed because generated patch self-reported an "
                "unresolved code issue."
            ),
            repair_attempt=repair_attempts_used,
        )
        return patch, repair_attempts_used, output, False

    def _premise_rejection_output_if_needed(
        self,
        *,
        request: AgenticProposalRequest,
        session_id: str,
        state: AgenticProposalSessionState,
        hypothesis: HypothesisProposal,
        patch: PatchProposal,
        observations: list[ProposalObservation],
        evidence: list[AgenticEvidenceRef],
        source: str,
        note: str,
        repair_attempt: int | None,
    ) -> AgenticProposalOutput | None:
        premise_rejection = _patch_premise_rejection(patch, hypothesis)
        if premise_rejection is None:
            return None
        ledger_kwargs: dict[str, Any] = {}
        if repair_attempt is None:
            ledger_kwargs["attempt"] = 1
        else:
            ledger_kwargs["repair_attempt"] = repair_attempt
        _record_failure_ledger_entry(
            state,
            phase=AgenticProposalPhase.DRAFT_PATCH,
            category=str(premise_rejection["failure_category"]),
            detail=str(premise_rejection.get("reason") or ""),
            source=source,
            **ledger_kwargs,
        )
        output = self._structured_rejection_output(
            request=request,
            session_id=session_id,
            hypothesis=hypothesis,
            rejection=premise_rejection,
            evidence_used=tuple(evidence),
            self_check=self._self_check_from_authoritative_previews(
                observations,
                state,
            ),
        )
        state.status = output.status
        state.note(
            AgenticProposalPhase.FINALIZE,
            note,
            metadata={
                "premise_check": premise_rejection["premise_check"],
                "failure_category": premise_rejection["failure_category"],
                "structured_rejection": premise_rejection if repair_attempt is None else None,
            },
        )
        return self._persist(output, state)

    def _self_reported_issue_output(
        self,
        *,
        request: AgenticProposalRequest,
        session_id: str,
        state: AgenticProposalSessionState,
        hypothesis: HypothesisProposal,
        observations: list[ProposalObservation],
        evidence: list[AgenticEvidenceRef],
        issue_detail: str,
        source: str,
        note: str,
        repair_attempt: int | None,
    ) -> AgenticProposalOutput:
        ledger_kwargs: dict[str, Any] = {}
        if repair_attempt is not None:
            ledger_kwargs["repair_attempt"] = repair_attempt
        _record_failure_ledger_entry(
            state,
            phase=AgenticProposalPhase.DRAFT_PATCH,
            category=AgenticFailureCategory.MODEL_REPAIR_FAILED,
            detail=issue_detail,
            source=source,
            **ledger_kwargs,
        )
        output = self._partial_hypothesis_output(
            request=request,
            session_id=session_id,
            hypothesis=hypothesis,
            detail=issue_detail,
            evidence_used=tuple(evidence),
            self_check=self._self_check_from_authoritative_previews(
                observations,
                state,
            ),
            failure_category=AgenticFailureCategory.MODEL_REPAIR_FAILED,
        )
        state.status = output.status
        state.note(
            AgenticProposalPhase.FINALIZE,
            note,
            metadata={"detail": issue_detail},
        )
        return self._persist(output, state)

    def _finalize_patch_output(
        self,
        *,
        request: AgenticProposalRequest,
        session_id: str,
        state: AgenticProposalSessionState,
        tool_context: ProposalToolContext | None,
        hypothesis: HypothesisProposal,
        patch: PatchProposal,
        observations: list[ProposalObservation],
        evidence: list[AgenticEvidenceRef],
    ) -> AgenticProposalOutput:
        state.note(AgenticProposalPhase.SELF_CHECK, "Recorded APS-1 schema self-check.")
        self_check = (
            self._self_check_from_authoritative_previews(observations, state)
            if tool_context is not None
            else AgenticSelfCheck(schema_valid=True)
        )
        preview_failure_detail = self._latest_authoritative_preview_failure_detail(
            observations,
            state,
        )
        if preview_failure_detail is not None:
            authoritative_previews = _authoritative_preview_observations(
                observations,
                state,
            )
            output = self._self_check_failed_output(
                request=request,
                session_id=session_id,
                hypothesis=hypothesis,
                detail=preview_failure_detail,
                termination_reason=AgenticTerminationReason.CODE_GENERATION_FAILED,
                evidence_used=tuple(evidence),
                self_check=self_check,
                failure_category=_preview_failure_category(authoritative_previews),
            )
            state.status = output.status
            state.note(
                AgenticProposalPhase.FINALIZE,
                "Patch self-check failed closed after latest preview failure.",
                metadata={"detail": preview_failure_detail},
            )
            return self._persist(output, state)

        self_check_detail = _self_check_failure_detail(
            self_check,
            require_schema_preview=_self_check_required(tool_context),
            require_contract_preview=_self_check_required(tool_context),
        )
        if self_check_detail is not None:
            output = self._self_check_failed_output(
                request=request,
                session_id=session_id,
                hypothesis=hypothesis,
                detail=self_check_detail,
                termination_reason=AgenticTerminationReason.CODE_GENERATION_FAILED,
                evidence_used=tuple(evidence),
                self_check=self_check,
                failure_category=AgenticFailureCategory.CONTRACT_BOUNDARY_FAILURE,
            )
            state.status = output.status
            state.note(
                AgenticProposalPhase.FINALIZE,
                "Patch self-check failed closed before completed output.",
                metadata={"detail": self_check_detail},
            )
            return self._persist(output, state)

        output = self._completed_output(
            request=request,
            session_id=session_id,
            hypothesis=hypothesis,
            patch=patch,
            evidence_used=tuple(evidence),
            self_check=self_check,
        )
        state.status = output.status
        state.note(AgenticProposalPhase.FINALIZE, "Session completed.")
        return self._persist(output, state)
