
"""Code-generation, patch validation, preview, and finalization phases."""
from __future__ import annotations

from collections import Counter
import re

from scion.core.models import mechanism_changes, patch_file_changes
from scion.core.paths import normalize_relative_patch_path
from scion.proposal.agentic_session_common import *

_SOURCE_FILE_RE = re.compile(
    r"^(?:###\s+|File:\s*)(?P<path>[^\n]+?)"
    r"(?:\s+\([^\n]*\))?\n"
    r"(?:[^\n]*\n)*?"
    r"```(?:python|py)?\n"
    r"(?P<content>.*?)"
    r"(?P<terminal_newline>\n)```",
    re.DOTALL | re.MULTILINE,
)
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
        active_algorithm_facts = _active_algorithm_facts_for_prompt_context(
            observations
        )
        if active_algorithm_facts:
            code_context["agentic_active_algorithm_facts"] = active_algorithm_facts
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

        invariant_issue = _code_stage_identity_issue(
            hypothesis,
            patch,
            code_context=code_context,
        )
        if invariant_issue is not None:
            patch, code_repair_attempts_used, output = self._repair_code_invariant_or_output(
                request=request,
                session_id=session_id,
                state=state,
                hypothesis=hypothesis,
                patch=patch,
                code_context=code_context,
                observations=observations,
                evidence=evidence,
                code_repair_attempts_used=code_repair_attempts_used,
                issue_detail=invariant_issue,
                note=(
                    "Patch generation violated code-stage mechanism identity "
                    "preservation."
                ),
            )
            if output is not None or patch is None:
                return patch, code_repair_attempts_used, output
            invariant_issue = _code_stage_identity_issue(
                hypothesis,
                patch,
                code_context=code_context,
            )
            if invariant_issue is not None:
                output = self._self_reported_issue_output(
                    request=request,
                    session_id=session_id,
                    state=state,
                    hypothesis=hypothesis,
                    observations=observations,
                    evidence=evidence,
                    issue_detail=invariant_issue,
                    source="code_stage_identity_repair_failed",
                    note=(
                        "Patch repair still violated code-stage mechanism "
                        "identity preservation."
                    ),
                    repair_attempt=code_repair_attempts_used,
                )
                return None, code_repair_attempts_used, output

        visibility_issue = _code_integration_visibility_issue(
            patch,
            getattr(state, "_latest_code_prompt_manifest", None),
        )
        if visibility_issue is not None:
            repair_context = _code_context_with_required_full_integration_files(
                code_context,
                visibility_issue.get("paths", ()),
            )
            patch, code_repair_attempts_used, output = self._repair_code_invariant_or_output(
                request=request,
                session_id=session_id,
                state=state,
                hypothesis=hypothesis,
                patch=patch,
                code_context=repair_context,
                observations=observations,
                evidence=evidence,
                code_repair_attempts_used=code_repair_attempts_used,
                issue_detail=str(visibility_issue["detail"]),
                note=(
                    "Patch generation attempted integration edits without "
                    "full API-visible integration file source."
                ),
            )
            if output is not None or patch is None:
                return patch, code_repair_attempts_used, output
            visibility_issue = _code_integration_visibility_issue(
                patch,
                getattr(state, "_latest_code_prompt_manifest", None),
            )
            if visibility_issue is not None:
                output = self._self_reported_issue_output(
                    request=request,
                    session_id=session_id,
                    state=state,
                    hypothesis=hypothesis,
                    observations=observations,
                    evidence=evidence,
                    issue_detail=str(visibility_issue["detail"]),
                    source="code_integration_visibility_repair_failed",
                    note=(
                        "Patch repair still attempted integration edits without "
                        "full API-visible integration source."
                    ),
                    repair_attempt=code_repair_attempts_used,
                )
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
                patch=patch,
                code_context=code_context,
                observations=observations,
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

    def _repair_code_invariant_or_output(
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
        issue_detail: str,
        note: str,
    ) -> tuple[PatchProposal | None, int, AgenticProposalOutput | None]:
        if (
            code_repair_attempts_used
            >= self._tool_loop_config.max_code_repair_attempts
            or self._session_timeout_reached(state)
        ):
            output = self._self_reported_issue_output(
                request=request,
                session_id=session_id,
                state=state,
                hypothesis=hypothesis,
                observations=observations,
                evidence=evidence,
                issue_detail=issue_detail,
                source="code_stage_invariant",
                note=note,
                repair_attempt=code_repair_attempts_used or None,
            )
            return None, code_repair_attempts_used, output
        patch = self._repair_patch_after_code_self_check(
            request=request,
            state=state,
            hypothesis=hypothesis,
            patch=patch,
            code_context=code_context,
            observations=observations,
            issue_detail=issue_detail,
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
            note="Patch invariant repair rejected the approved hypothesis after premise check.",
            repair_attempt=code_repair_attempts_used,
        )
        if output is not None:
            return None, code_repair_attempts_used, output
        return patch, code_repair_attempts_used, None

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
                patch=patch,
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
        if str(getattr(patch, "premise_check", "") or "") == "duplicate":
            state.note(
                AgenticProposalPhase.DRAFT_PATCH,
                "Patch premise duplicate diagnostic recorded; continuing without hard block.",
                metadata=_drop_empty_dict(
                    {
                        "source": source,
                        "premise_check": "duplicate",
                        "result_kind": "duplicate_diagnostic",
                        "gate_action": "diagnostic",
                        "diagnostic_kind": "duplicate_mechanism",
                        "reason": getattr(patch, "premise_check_reason", "") or "",
                        "repair_attempt": repair_attempt,
                    }
                ),
            )
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


def _code_stage_identity_issue(
    hypothesis: HypothesisProposal,
    patch: PatchProposal,
    *,
    code_context: Mapping[str, Any] | None = None,
) -> str | None:
    expected_ids = _mechanism_id_set(hypothesis)
    patch_ids = _mechanism_id_set(patch)
    if expected_ids or patch_ids:
        if expected_ids != patch_ids:
            return (
                "code_stage_identity_mismatch: patch mechanism_changes ids must "
                "exactly match the approved hypothesis. "
                f"expected={sorted(expected_ids)!r}; observed={sorted(patch_ids)!r}. "
                "Retry the same patch mechanism identity; do not add, drop, or "
                "rename mechanism ids."
            )
    telemetry_ids = _new_telemetry_mechanism_ids_from_patch(
        patch,
        code_context=code_context,
    )
    telemetry_identity_allowlist = _telemetry_identity_allowlist(code_context)
    unexpected_telemetry_ids = sorted(
        telemetry_ids - expected_ids - telemetry_identity_allowlist
    )
    if expected_ids and unexpected_telemetry_ids:
        return (
            "code_stage_telemetry_identity_mismatch: patch records telemetry "
            "for mechanism id(s) not declared by the approved hypothesis: "
            f"{unexpected_telemetry_ids!r}. Use the protected mechanism id(s) "
            f"{sorted(expected_ids)!r} or remove unrelated telemetry."
        )
    return None


def _telemetry_identity_allowlist(
    code_context: Mapping[str, Any] | None,
) -> set[str]:
    if not isinstance(code_context, Mapping):
        return set()
    taxonomy = code_context.get("active_subject_taxonomy")
    if not isinstance(taxonomy, Mapping):
        return set()
    return {
        str(item or "").strip()
        for item in taxonomy.get("telemetry_identity_allowlist", ()) or ()
        if str(item or "").strip()
    }


def _mechanism_id_set(proposal: HypothesisProposal | PatchProposal) -> set[str]:
    return {
        str(change.id).strip()
        for change in mechanism_changes(proposal)
        if str(change.id).strip()
    }


_TELEMETRY_CALL_RE = re.compile(
    r"(?:context|self\.context)\.record_(?:phase|iteration|move)\(\s*"
    r"['\"]([A-Za-z][A-Za-z0-9_]{1,63})['\"]"
)


def _new_telemetry_mechanism_ids_from_patch(
    patch: PatchProposal,
    *,
    code_context: Mapping[str, Any] | None = None,
) -> set[str]:
    before_sources = _code_context_source_by_path(code_context)
    ids: set[str] = set()
    for change in patch_file_changes(patch):
        after_counts = _telemetry_mechanism_counts(change.code_content)
        if not before_sources or change.action == "create":
            ids.update(after_counts)
            continue
        path = _normalize_patch_path(change.file_path)
        before_counts = _telemetry_mechanism_counts(before_sources.get(path, ""))
        for mechanism_id, after_count in after_counts.items():
            if after_count > before_counts.get(mechanism_id, 0):
                ids.add(mechanism_id)
    return ids


def _telemetry_mechanism_counts(source: Any) -> Counter[str]:
    return Counter(
        match.group(1)
        for match in _TELEMETRY_CALL_RE.finditer(str(source or ""))
    )


def _code_context_source_by_path(
    code_context: Mapping[str, Any] | None,
) -> dict[str, str]:
    if not isinstance(code_context, Mapping):
        return {}
    result: dict[str, str] = {}
    target_path = _normalize_patch_path(code_context.get("target_file"))
    target_source = code_context.get("target_file_code")
    if target_path and isinstance(target_source, str) and target_source.strip():
        parsed = _parse_markdown_source_files(target_source)
        result[target_path] = parsed.get(target_path, target_source)
    for key in (
        "agentic_required_full_integration_files",
        "solver_design_branch_current_integration_files",
    ):
        result.update(_parse_markdown_source_files(code_context.get(key)))
    result.update(
        _full_algorithm_read_sources(
            code_context.get("solver_design_full_algorithm_file_reads")
        )
    )
    result.update(
        _agentic_tool_observation_full_read_sources(
            code_context.get("agentic_tool_observations")
        )
    )
    return result


def _code_integration_visibility_issue(
    patch: PatchProposal,
    manifest: Any,
) -> dict[str, Any] | None:
    changed_paths = [
        _normalize_patch_path(change.file_path)
        for change in patch.additional_changes or ()
        if getattr(change, "action", None) != "create"
    ]
    changed_paths = [path for path in changed_paths if path]
    if not changed_paths:
        return None
    visible_paths = _full_visible_code_prompt_paths(manifest)
    missing = sorted(path for path in dict.fromkeys(changed_paths) if path not in visible_paths)
    if not missing:
        return None
    return {
        "paths": tuple(missing),
        "detail": (
            "code_integration_file_visibility_missing: additional_changes "
            "modify integration file(s) whose full current source was not "
            f"API-visible in the code prompt: {missing!r}. Retry with the same "
            "hypothesis and patch intent after projecting those files in full."
        ),
    }


def _full_visible_code_prompt_paths(manifest: Any) -> set[str]:
    if not isinstance(manifest, Mapping):
        return set()
    ledger = manifest.get("code_file_visibility_ledger")
    if not isinstance(ledger, Mapping):
        return set()
    paths: set[str] = set()
    target = ledger.get("target_file")
    if isinstance(target, Mapping) and target.get("full_content_visible_in_rendered_prompt"):
        path = _normalize_patch_path(target.get("file_path"))
        if path:
            paths.add(path)
    for record in ledger.get("integration_files") or ():
        if not isinstance(record, Mapping):
            continue
        if not record.get("full_content_visible_in_rendered_prompt"):
            continue
        path = _normalize_patch_path(record.get("file_path"))
        if path:
            paths.add(path)
    for record in ledger.get("algorithm_file_reads") or ():
        if not isinstance(record, Mapping):
            continue
        if not record.get("full_content_visible_in_rendered_prompt"):
            continue
        path = _normalize_patch_path(record.get("file_path"))
        if path:
            paths.add(path)
    return paths


def _code_context_with_required_full_integration_files(
    code_context: Mapping[str, Any],
    paths: Any,
) -> dict[str, Any]:
    retry_context = dict(code_context)
    source_files = _code_context_source_by_path(retry_context)
    required_sections: list[str] = []
    for path in paths or ():
        normalized = _normalize_patch_path(path)
        content = source_files.get(normalized)
        if not normalized or content is None:
            continue
        required_sections.append(
            f"### {normalized}\n"
            "Provenance: branch-current integration source required after "
            "code visibility invariant failure\n"
            f"```python\n{content}```"
        )
    if required_sections:
        retry_context["agentic_required_full_integration_files"] = "\n\n".join(
            required_sections
        )
    return retry_context


def _full_algorithm_read_sources(value: Any) -> dict[str, str]:
    if isinstance(value, Mapping):
        value = value.get("reads")
    if not isinstance(value, (list, tuple)):
        return {}
    sources: dict[str, str] = {}
    for item in value:
        if not isinstance(item, Mapping):
            continue
        path = _normalize_patch_path(item.get("file_path"))
        content = _full_algorithm_read_content(item)
        if path and content is not None:
            sources[path] = content
    return sources


def _agentic_tool_observation_full_read_sources(value: Any) -> dict[str, str]:
    if not isinstance(value, (list, tuple)):
        return {}
    sources: dict[str, str] = {}
    for item in value:
        if not isinstance(item, Mapping):
            continue
        if item.get("tool_name") != "context.read_algorithm_file":
            continue
        if bool(item.get("is_error")):
            continue
        payload = item.get("structured_payload")
        if not isinstance(payload, Mapping):
            continue
        path = _normalize_patch_path(payload.get("file_path"))
        content = _full_algorithm_read_content(payload)
        if path and content is not None:
            sources[path] = content
    return sources


def _full_algorithm_read_content(payload: Mapping[str, Any]) -> str | None:
    if payload.get("readable") is not True:
        return None
    if payload.get("active") is False:
        return None
    if bool(payload.get("truncated")):
        return None
    content = payload.get("content_preview")
    return content if isinstance(content, str) else None


def _parse_markdown_source_files(value: Any) -> dict[str, str]:
    if not isinstance(value, str):
        return {}
    files: dict[str, str] = {}
    for match in _SOURCE_FILE_RE.finditer(value):
        path = _normalize_patch_path(match.group("path"))
        content = match.group("content") + match.group("terminal_newline")
        if path:
            files[path] = content
    return files


def _normalize_patch_path(value: Any) -> str:
    try:
        return normalize_relative_patch_path(str(value or ""))
    except ValueError:
        text = str(value or "").replace("\\", "/").strip()
        while text.startswith("./"):
            text = text[2:]
        return text.lstrip("/")
