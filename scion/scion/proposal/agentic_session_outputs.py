"""AgenticSessionOutput mixin."""
from __future__ import annotations

from scion.proposal.agentic_session_common import *


class AgenticSessionOutputMixin:
    def _resolve_injected_output(
            self,
            request: AgenticProposalRequest,
            session_id: str,
        ) -> AgenticProposalOutput:
            injected = self._injected_output
            assert injected is not None
            output = injected(request) if callable(injected) else injected
            return replace(
                output,
                session_id=output.session_id or session_id,
                campaign_id=output.campaign_id or request.campaign_id,
                branch_id=output.branch_id or request.branch.branch_id,
                champion_version=(
                    output.champion_version
                    if output.champion_version is not None
                    else _champion_version(request.champion)
                ),
                champion_weight_revision=(
                    output.champion_weight_revision
                    if output.champion_weight_revision is not None
                    else _champion_weight_revision(request.champion)
                ),
                problem_id=output.problem_id or request.problem_id,
                problem_spec_hash=output.problem_spec_hash or request.problem_spec_hash,
                idempotency_key=output.idempotency_key
                or self.idempotency_key_for_request(request),
                termination_reason=(
                    output.termination_reason
                    if output.termination_reason != AgenticTerminationReason.UNHANDLED_ERROR
                    else AgenticTerminationReason.INJECTED_OUTPUT
                ),
            )

    def _completed_output(
            self,
            *,
            request: AgenticProposalRequest,
            session_id: str,
            hypothesis: HypothesisProposal,
            patch: PatchProposal,
            evidence_used: tuple[AgenticEvidenceRef, ...] = (),
            self_check: AgenticSelfCheck | None = None,
        ) -> AgenticProposalOutput:
            return AgenticProposalOutput(
                status=AgenticProposalStatus.COMPLETED,
                session_id=session_id,
                campaign_id=request.campaign_id,
                branch_id=request.branch.branch_id,
                idempotency_key=self._idempotency_key_for_hypothesis(
                    request,
                    hypothesis,
                ),
                champion_version=_champion_version(request.champion),
                champion_weight_revision=_champion_weight_revision(request.champion),
                problem_id=request.problem_id,
                problem_spec_hash=request.problem_spec_hash,
                selected_surface=hypothesis.change_locus,
                action=hypothesis.action,
                hypothesis=hypothesis,
                patch=patch,
                evidence_used=evidence_used,
                self_check=self_check
                or AgenticSelfCheck(
                    schema_valid=True,
                    schema_preview_codes=(),
                    contract_preview_passed=None,
                    contract_preview_codes=(),
                ),
                termination_reason=AgenticTerminationReason.COMPLETED,
            )

    def _partial_hypothesis_output(
            self,
            *,
            request: AgenticProposalRequest,
            session_id: str,
            hypothesis: HypothesisProposal,
            detail: str,
            termination_reason: AgenticTerminationReason = (
                AgenticTerminationReason.CODE_GENERATION_FAILED
            ),
            evidence_used: tuple[AgenticEvidenceRef, ...] = (),
            self_check: AgenticSelfCheck | None = None,
            failure_category: AgenticFailureCategory | str | None = None,
        ) -> AgenticProposalOutput:
            return AgenticProposalOutput(
                status=AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY,
                session_id=session_id,
                campaign_id=request.campaign_id,
                branch_id=request.branch.branch_id,
                idempotency_key=self._idempotency_key_for_hypothesis(
                    request,
                    hypothesis,
                ),
                champion_version=_champion_version(request.champion),
                champion_weight_revision=_champion_weight_revision(request.champion),
                problem_id=request.problem_id,
                problem_spec_hash=request.problem_spec_hash,
                selected_surface=hypothesis.change_locus,
                action=hypothesis.action,
                hypothesis=hypothesis,
                patch=None,
                evidence_used=evidence_used,
                self_check=self_check or AgenticSelfCheck(schema_valid=True),
                termination_reason=termination_reason,
                failure_detail=detail,
                failure_category=failure_category,
            )

    def _structured_rejection_output(
            self,
            *,
            request: AgenticProposalRequest,
            session_id: str,
            hypothesis: HypothesisProposal,
            rejection: Mapping[str, Any],
            evidence_used: tuple[AgenticEvidenceRef, ...] = (),
            self_check: AgenticSelfCheck | None = None,
        ) -> AgenticProposalOutput:
            rejection_payload = _normalized_structured_rejection(rejection)
            detail = (
                f"premise_check={rejection_payload.get('premise_check')}: "
                f"{rejection_payload.get('reason') or 'code phase rejected premise'}"
            )
            return AgenticProposalOutput(
                status=AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY,
                session_id=session_id,
                campaign_id=request.campaign_id,
                branch_id=request.branch.branch_id,
                idempotency_key=self._idempotency_key_for_hypothesis(
                    request,
                    hypothesis,
                ),
                champion_version=_champion_version(request.champion),
                champion_weight_revision=_champion_weight_revision(request.champion),
                problem_id=request.problem_id,
                problem_spec_hash=request.problem_spec_hash,
                selected_surface=hypothesis.change_locus,
                action=hypothesis.action,
                hypothesis=hypothesis,
                patch=None,
                evidence_used=evidence_used,
                self_check=self_check or AgenticSelfCheck(schema_valid=True),
                termination_reason=_rejection_termination_reason(rejection_payload),
                failure_detail=detail,
                failure_category=str(rejection_payload.get("failure_category") or ""),
                structured_rejection=rejection_payload,
            )

    def _self_check_failed_output(
            self,
            *,
            request: AgenticProposalRequest,
            session_id: str,
            hypothesis: HypothesisProposal,
            detail: str,
            termination_reason: AgenticTerminationReason,
            evidence_used: tuple[AgenticEvidenceRef, ...] = (),
            self_check: AgenticSelfCheck | None = None,
            failure_category: AgenticFailureCategory | str | None = None,
        ) -> AgenticProposalOutput:
            return AgenticProposalOutput(
                status=AgenticProposalStatus.FAILED,
                session_id=session_id,
                campaign_id=request.campaign_id,
                branch_id=request.branch.branch_id,
                idempotency_key=self._idempotency_key_for_hypothesis(
                    request,
                    hypothesis,
                ),
                champion_version=_champion_version(request.champion),
                champion_weight_revision=_champion_weight_revision(request.champion),
                problem_id=request.problem_id,
                problem_spec_hash=request.problem_spec_hash,
                selected_surface=hypothesis.change_locus,
                action=hypothesis.action,
                hypothesis=hypothesis,
                patch=None,
                evidence_used=evidence_used,
                self_check=self_check or AgenticSelfCheck(schema_valid=False),
                termination_reason=termination_reason,
                failure_detail=detail,
                failure_category=failure_category,
            )

    def _idempotency_key_for_hypothesis(
            self,
            request: AgenticProposalRequest,
            hypothesis: HypothesisProposal,
        ) -> str:
            return compute_agentic_idempotency_key(
                replace(request, approved_hypothesis=hypothesis),
                self._tool_loop_config,
            )

    def _failed_output(
            self,
            *,
            request: AgenticProposalRequest,
            session_id: str,
            status: AgenticProposalStatus,
            termination_reason: AgenticTerminationReason,
            detail: str,
            evidence_used: tuple[AgenticEvidenceRef, ...] = (),
            failure_category: AgenticFailureCategory | str | None = None,
        ) -> AgenticProposalOutput:
            return AgenticProposalOutput(
                status=status,
                session_id=session_id,
                campaign_id=request.campaign_id,
                branch_id=request.branch.branch_id,
                idempotency_key=self.idempotency_key_for_request(request),
                champion_version=_champion_version(request.champion),
                champion_weight_revision=_champion_weight_revision(request.champion),
                problem_id=request.problem_id,
                problem_spec_hash=request.problem_spec_hash,
                evidence_used=evidence_used,
                self_check=AgenticSelfCheck(schema_valid=False),
                termination_reason=termination_reason,
                failure_detail=detail,
                failure_category=failure_category,
            )

    def _timeout_output(
            self,
            request: AgenticProposalRequest,
            state: AgenticProposalSessionState,
            *,
            evidence_used: tuple[AgenticEvidenceRef, ...] = (),
        ) -> AgenticProposalOutput:
            self._record_loop_stop(state, "session_timeout", error_code="session_timeout")
            return self._failed_output(
                request=request,
                session_id=state.session_id,
                status=AgenticProposalStatus.FAILED,
                termination_reason=AgenticTerminationReason.SESSION_TIMEOUT,
                detail=(
                    "agentic proposal session exceeded max_wall_time_sec="
                    f"{self._tool_loop_config.max_wall_time_sec}"
                ),
                evidence_used=evidence_used,
            )

    def _persist(
            self,
            output: AgenticProposalOutput,
            state: AgenticProposalSessionState,
        ) -> AgenticProposalOutput:
            terminal_category = _terminal_failure_category(output, state)
            if (
                output.status != AgenticProposalStatus.COMPLETED
                and terminal_category
                and not state.failure_ledger
            ):
                _record_failure_ledger_entry(
                    state,
                    phase=state.phase,
                    category=terminal_category,
                    detail=output.failure_detail,
                    source="terminal_output",
                )
            ledger = _failure_ledger_payload(state.failure_ledger)
            compact_transcript = _compact_transcript(tuple(state.transcript))
            transcript_digest = _transcript_digest(compact_transcript)
            output = replace(
                output,
                schema_version=AGENTIC_SESSION_SCHEMA_VERSION,
                request_id=output.request_id or state.request_id or state.session_id,
                idempotency_key=output.idempotency_key or state.idempotency_key,
                transcript=tuple(state.transcript),
                tool_loop_config=_tool_loop_config_payload(self._tool_loop_config),
                tool_budget_used=_tool_budget_used_payload(state),
                transcript_digest=transcript_digest,
                failure_category=terminal_category,
                failure_ledger=ledger,
            )
            state.idempotency_key = output.idempotency_key or state.idempotency_key
            if self._artifact_store is None:
                return output
            output = replace(
                output,
                tainted_artifact_refs=tuple(
                    dict.fromkeys((*output.tainted_artifact_refs, *state.scratch_artifact_refs))
                ),
            )
            transcript_ref = self._artifact_store.write_transcript(state)
            output_with_transcript = replace(
                output,
                tainted_artifact_refs=tuple(
                    dict.fromkeys((*output.tainted_artifact_refs, transcript_ref))
                ),
            )
            output_ref = self._artifact_store.write_output(output_with_transcript)
            return replace(
                output_with_transcript,
                tainted_artifact_refs=tuple(
                    dict.fromkeys(
                        (*output_with_transcript.tainted_artifact_refs, output_ref)
                    )
                ),
            )
