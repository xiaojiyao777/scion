"""LLM proposal lifecycle service for campaign explore steps."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, MutableMapping, Sequence

from scion.core.models import (
    Branch,
    ChampionState,
    FailureEvent,
    HypothesisProposal,
    HypothesisRecord,
    PatchProposal,
    StepRecord,
)
from scion.core.execution_outcome import ExecutionOutcome, ExecutionOutcomeRecord
from scion.proposal.engine import (
    PromptCallReceipt,
    PromptTurnSnapshot,
    ProposalValidationError,
    build_prompt_turn_snapshot,
    prompt_call_receipt_from_error,
)
from scion.proposal.context_owner_maps import proposal_context_snapshot
from scion.proposal.context_snapshot import ProposalContextSnapshot
from scion.proposal.llm_client import (
    LLMAuthError,
    LLMBalanceError,
    LLMFormatError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMTransportError,
)

from .direct_attempt_lifecycle import DirectAttemptLifecycle
from .protocols import (
    BranchControllerLike,
    ClassifierLike,
    CreativeLayerLike,
    HypothesisStoreLike,
    ProblemRuntimeLike,
)
from .records import ProposalRecordMixin

logger = logging.getLogger(__name__)


@dataclass
class ProposalPipeline(ProposalRecordMixin):
    """Own the direct-v3 hypothesis and code provider interactions.

    The service may call the injected failure handler for proposal failures, but
    it does not mutate branch promotion/evaluation state. CampaignManager keeps
    orchestration; this class owns LLM context construction and tainted proposal
    parsing boundaries.
    """

    creative: CreativeLayerLike
    problem_runtime: ProblemRuntimeLike
    classifier: ClassifierLike
    branch_controller: BranchControllerLike
    hypothesis_store: HypothesisStoreLike
    branch_workspaces: Mapping[str, str]
    champion_lock: Any
    get_champion: Callable[[], ChampionState]
    step_history: list[StepRecord]
    handle_failure: Callable[[Branch, FailureEvent], None]
    mark_balance_exhausted: Callable[[], None]
    campaign_branches_provider: Callable[[], Sequence[Branch]] | None = None
    hypothesis_failure_details: MutableMapping[str, str] = field(default_factory=dict)
    lineage_registry: Any | None = None
    campaign_id: str = ""
    problem_id: str | None = None
    problem_spec_hash: str | None = None
    split_manifest_hash: str | None = None
    seed_ledger_hash: str | None = None
    persistent_forced_locus: str | None = None
    forced_surface_action: str | None = None
    forced_surface_target_file: str | None = None
    forced_surface_diagnostic: bool = False
    governance_envelopes: MutableMapping[str, Any] = field(default_factory=dict)
    _direct_attempts: DirectAttemptLifecycle = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._direct_attempts = DirectAttemptLifecycle(self)

    @property
    def prompt_call_receipts(self) -> MutableMapping[
        str,
        MutableMapping[str, PromptCallReceipt],
    ]:
        return self._direct_attempts.state.prompt_call_receipts

    @property
    def proposal_attempt_ids(self) -> MutableMapping[str, str]:
        return self._direct_attempts.state.attempt_ids

    @property
    def proposal_attempt_refs(self) -> MutableMapping[str, Mapping[str, Any]]:
        return self._direct_attempts.state.attempt_refs

    @property
    def approved_hypothesis_bindings(self) -> MutableMapping[
        str,
        Mapping[str, str],
    ]:
        return self._direct_attempts.state.approved_hypothesis_bindings

    def pop_proposal_attempt_ref(self, branch_id: str) -> Mapping[str, Any] | None:
        """Transfer the current direct attempt reference exactly once."""

        return self._direct_attempts.state.attempt_refs.pop(branch_id, None)


    def _generate_direct_hypothesis(
        self,
        branch_id: str,
        context_snapshot: ProposalContextSnapshot,
        prompt_snapshot: PromptTurnSnapshot,
        attempt_audit: Mapping[str, Any],
    ) -> HypothesisProposal:
        context = context_snapshot.inputs.provider_context(
            include_renderer_inputs=True
        )
        self._direct_attempts.clear_receipt(branch_id, "hypothesis")
        method = getattr(
            self.creative,
            "generate_direct_hypothesis_with_receipt",
            None,
        )
        if not callable(method):
            raise TypeError("direct hypothesis requires a receipt-aware API")
        hypothesis, receipt = method(
            context,
            prompt_snapshot,
            attempt_audit=attempt_audit,
        )
        self._direct_attempts.record_receipt(branch_id, "hypothesis", receipt)
        return hypothesis

    def _generate_direct_code(
        self,
        branch_id: str,
        context_snapshot: ProposalContextSnapshot,
        prompt_snapshot: PromptTurnSnapshot,
        attempt_audit: Mapping[str, Any],
    ) -> PatchProposal:
        context = context_snapshot.inputs.provider_context(
            include_renderer_inputs=True
        )
        self._direct_attempts.clear_receipt(branch_id, "code")
        method = getattr(
            self.creative,
            "generate_direct_code_with_receipt",
            None,
        )
        if not callable(method):
            raise TypeError("direct code requires a receipt-aware API")
        patch, receipt = method(
            context,
            prompt_snapshot,
            attempt_audit=attempt_audit,
        )
        self._direct_attempts.record_receipt(branch_id, "code", receipt)
        return patch

    def _complete_direct_hypothesis(
        self,
        *,
        branch: Branch,
        champion: ChampionState,
        hypothesis: HypothesisProposal,
        post_provider_stage: MutableMapping[str, str],
    ) -> tuple[HypothesisProposal | None, HypothesisRecord | None]:
        """Durably identify, bind, and publish one provider hypothesis."""

        bid = branch.branch_id
        hypothesis_digest = self._direct_attempts.hypothesis_digest(hypothesis)
        hypothesis_record = self._hypothesis_record(
            branch,
            hypothesis,
            champion=champion,
            proposal_digest=hypothesis_digest,
        )
        post_provider_stage["value"] = "hypothesis_store_write"
        self.hypothesis_store.save(hypothesis_record)
        post_provider_stage["value"] = "post_store_binding"
        self._direct_attempts.bind_approved_hypothesis(
            bid,
            hypothesis_id=hypothesis_record.hypothesis_id,
            hypothesis_digest=hypothesis_digest,
            hypothesis=hypothesis,
        )
        post_provider_stage["value"] = "hypothesis_transition_commit"
        if not self._direct_attempts.commit(
            branch=branch,
            champion=champion,
            phase="hypothesis",
            status="generated",
            transition_reason="generated",
            failure_lane=None,
            hypothesis=hypothesis,
            hypothesis_id=hypothesis_record.hypothesis_id,
            bound_hypothesis_digest=hypothesis_digest,
        ):
            self._direct_attempts.discard_approved_binding(bid)
            self.hypothesis_store.mark_status(
                hypothesis_record.hypothesis_id,
                "rejected",
            )
            return None, None
        return hypothesis, hypothesis_record

    def generate_hypothesis(
        self,
        branch: Branch,
    ) -> tuple[HypothesisProposal | None, HypothesisRecord | None]:
        bid = branch.branch_id
        self.hypothesis_failure_details.pop(bid, None)
        branch_workspace = self.branch_workspaces.get(bid)
        champ_snapshot = self._champion_snapshot()
        forced_locus = self.persistent_forced_locus
        forced_action = self.forced_surface_action if forced_locus else None
        forced_target_file = (
            self.forced_surface_target_file if forced_locus else None
        )
        forced_diagnostic = self.forced_surface_diagnostic if forced_locus else False
        context = self.problem_runtime.build_hypothesis_context(
            branch=branch,
            champion=champ_snapshot,
            step_history=self.step_history,
            campaign_branches=(
                tuple(self.campaign_branches_provider() or ())
                if self.campaign_branches_provider is not None
                else None
            ),
            branch_workspace=branch_workspace,
            forced_locus=forced_locus,
            forced_action=forced_action,
            forced_target_file=forced_target_file,
            forced_surface_diagnostic=forced_diagnostic,
        )
        try:
            authoritative_context = proposal_context_snapshot(
                "hypothesis",
                context,
            )
            prompt_snapshot = build_prompt_turn_snapshot(
                "hypothesis",
                authoritative_context,
            )
        except (TypeError, ValueError) as exc:
            detail = f"proposal_context_validation_failed:{type(exc).__name__}:{exc}"
            self._direct_attempts.fail_integrity(
                branch,
                detail,
                clear_approved_binding=True,
            )
            return None, None
        self.governance_envelopes[bid] = authoritative_context.governance_envelope
        if not self._direct_attempts.require_receipt_api(branch, "hypothesis"):
            return None, None
        attempt_audit = self._direct_attempts.start_provider_call(
            branch=branch,
            champion=champ_snapshot,
            phase="hypothesis",
            snapshot=prompt_snapshot,
        )
        if attempt_audit is None:
            return None, None
        try:
            hypothesis = self._generate_direct_hypothesis(
                bid,
                authoritative_context,
                prompt_snapshot,
                attempt_audit,
            )
        except KeyboardInterrupt as exc:
            self._direct_attempts.interrupt_provider_call(
                branch=branch,
                champion=champ_snapshot,
                phase="hypothesis",
                error=exc,
                hypothesis=None,
            )
            raise
        except LLMBalanceError as exc:
            receipt = prompt_call_receipt_from_error(exc)
            self._direct_attempts.record_receipt(
                bid,
                "hypothesis",
                receipt,
            )
            committed = self._direct_attempts.commit(
                branch=branch,
                champion=champ_snapshot,
                phase="hypothesis",
                status="failed",
                transition_reason=self._direct_attempts.failure_reason(exc, receipt),
                failure_lane="infra",
                hypothesis=None,
            )
            logger.critical(
                "Branch %s: API balance exhausted - stopping campaign: %s",
                bid,
                exc,
            )
            self.hypothesis_failure_details[bid] = str(exc)
            self.mark_balance_exhausted()
            if not committed:
                return None, None
            self._direct_attempts.record_execution_outcome(
                branch,
                phase="hypothesis",
                outcome=ExecutionOutcome.RESOURCE_EXHAUSTED,
                reason_code="PROVIDER_BALANCE_EXHAUSTED",
                detail=str(exc),
                error_type=type(exc).__name__,
                error_category=(receipt.error_category if receipt else None),
            )
            return None, None
        except (
            LLMAuthError,
            LLMFormatError,
            LLMProviderError,
            LLMTimeoutError,
            LLMTransportError,
            LLMRateLimitError,
            ProposalValidationError,
        ) as exc:
            receipt = prompt_call_receipt_from_error(exc)
            self._direct_attempts.record_receipt(
                bid,
                "hypothesis",
                receipt,
            )
            invalid_response = isinstance(
                exc,
                (LLMFormatError, ProposalValidationError),
            )
            category = "proposal" if invalid_response else "infra"
            committed = self._direct_attempts.commit(
                branch=branch,
                champion=champ_snapshot,
                phase="hypothesis",
                status="failed",
                transition_reason=self._direct_attempts.failure_reason(exc, receipt),
                failure_lane=(
                    "infra" if category == "infra" else "invalid_response"
                ),
                hypothesis=None,
            )
            if not committed:
                return None, None
            logger.warning("Branch %s: hypothesis LLM error: %s", bid, exc)
            self.hypothesis_failure_details[bid] = str(exc)
            self._direct_attempts.record_execution_outcome(
                branch,
                phase="hypothesis",
                outcome=(
                    ExecutionOutcome.NOT_EVALUATED
                    if invalid_response
                    else ExecutionOutcome.BLOCKED_INFRA
                ),
                reason_code=(
                    "PROPOSAL_RESPONSE_INVALID"
                    if invalid_response
                    else "PROVIDER_CALL_BLOCKED_INFRA"
                ),
                detail=str(exc),
                error_type=type(exc).__name__,
                error_category=(receipt.error_category if receipt else None),
            )
            if not invalid_response:
                self.handle_failure(
                    branch,
                    FailureEvent(category=category, detail=str(exc)),
                )
            return None, None
        except Exception as exc:
            if self._direct_attempts.handle_unexpected_receipt_exception(
                branch=branch,
                champion=champ_snapshot,
                phase="hypothesis",
                error=exc,
                hypothesis=None,
            ):
                return None, None
            raise

        post_provider_stage = {"value": "post_provider_processing"}
        try:
            result = self._complete_direct_hypothesis(
                branch=branch,
                champion=champ_snapshot,
                hypothesis=hypothesis,
                post_provider_stage=post_provider_stage,
            )
        except Exception as exc:
            transition_reason = (
                "hypothesis_store_write_failed"
                if post_provider_stage.get("value") == "hypothesis_store_write"
                else "post_provider_processing_failed"
            )
            if self._direct_attempts.handle_unexpected_receipt_exception(
                branch=branch,
                champion=champ_snapshot,
                phase="hypothesis",
                error=exc,
                hypothesis=hypothesis,
                transition_reason_override=transition_reason,
            ):
                return None, None
            raise
        return result

    def pop_hypothesis_failure_detail(self, branch_id: str) -> str | None:
        return self.hypothesis_failure_details.pop(branch_id, None)

    def pop_execution_outcome(
        self,
        branch_id: str,
    ) -> ExecutionOutcomeRecord | None:
        """Transfer one typed direct-provider outcome to Explore exactly once."""

        return self._direct_attempts.pop_execution_outcome(branch_id)

    def pop_governance_envelope(self, branch_id: str) -> Any | None:
        """Transfer the immutable host envelope to the outer Contract once."""

        return self.governance_envelopes.pop(branch_id, None)

    def generate_code(
        self,
        branch: Branch,
        hypothesis: HypothesisProposal,
    ) -> PatchProposal | None:
        bid = branch.branch_id
        if not self._direct_attempts.require_receipt_api(branch, "code"):
            return None
        bound_hypothesis_digest = None
        if self.lineage_registry is not None:
            bound_hypothesis_digest = self._direct_attempts.prepare_code(
                branch,
                hypothesis,
            )
            if bound_hypothesis_digest is None:
                return None
        champ_snapshot = self._champion_snapshot()
        context = self.problem_runtime.build_code_context(
            branch=branch,
            hypothesis=hypothesis,
            champion=champ_snapshot,
            branch_workspace=self.branch_workspaces.get(bid),
            step_history=self.step_history,
        )
        try:
            authoritative_context = proposal_context_snapshot("code", context)
            prompt_snapshot = build_prompt_turn_snapshot(
                "code",
                authoritative_context,
            )
        except (TypeError, ValueError) as exc:
            detail = f"proposal_context_validation_failed:{type(exc).__name__}:{exc}"
            self._direct_attempts.fail_integrity(
                branch,
                detail,
                clear_approved_binding=False,
            )
            return None
        result: PatchProposal | None = None
        attempt_audit = self._direct_attempts.start_provider_call(
            branch=branch,
            champion=champ_snapshot,
            phase="code",
            snapshot=prompt_snapshot,
        )
        if attempt_audit is None:
            return None
        try:
            result = self._generate_direct_code(
                bid,
                authoritative_context,
                prompt_snapshot,
                attempt_audit,
            )
            if not self._direct_attempts.commit(
                branch=branch,
                champion=champ_snapshot,
                phase="code",
                status="generated",
                transition_reason="generated",
                failure_lane=None,
                hypothesis=hypothesis,
                patch=result,
                bound_hypothesis_digest=bound_hypothesis_digest,
            ):
                return None
            return result
        except KeyboardInterrupt as exc:
            self._direct_attempts.interrupt_provider_call(
                branch=branch,
                champion=champ_snapshot,
                phase="code",
                error=exc,
                hypothesis=hypothesis,
                bound_hypothesis_digest=bound_hypothesis_digest,
            )
            raise
        except LLMBalanceError as exc:
            receipt = prompt_call_receipt_from_error(exc)
            self._direct_attempts.record_receipt(
                bid,
                "code",
                receipt,
            )
            committed = self._direct_attempts.commit(
                branch=branch,
                champion=champ_snapshot,
                phase="code",
                status="failed",
                transition_reason=self._direct_attempts.failure_reason(exc, receipt),
                failure_lane="infra",
                hypothesis=hypothesis,
                bound_hypothesis_digest=bound_hypothesis_digest,
            )
            logger.critical(
                "Branch %s: API balance exhausted - stopping campaign: %s",
                bid,
                exc,
            )
            self.hypothesis_failure_details[bid] = str(exc)
            self.mark_balance_exhausted()
            if not committed:
                return None
            self._direct_attempts.record_execution_outcome(
                branch,
                phase="code",
                outcome=ExecutionOutcome.RESOURCE_EXHAUSTED,
                reason_code="PROVIDER_BALANCE_EXHAUSTED",
                detail=str(exc),
                error_type=type(exc).__name__,
                error_category=(receipt.error_category if receipt else None),
            )
            return None
        except (
            LLMAuthError,
            LLMFormatError,
            LLMProviderError,
            LLMTimeoutError,
            LLMTransportError,
            LLMRateLimitError,
            ProposalValidationError,
        ) as exc:
            receipt = prompt_call_receipt_from_error(exc)
            self._direct_attempts.record_receipt(
                bid,
                "code",
                receipt,
            )
            invalid_response = isinstance(
                exc,
                (LLMFormatError, ProposalValidationError),
            )
            category = "proposal" if invalid_response else "infra"
            committed = self._direct_attempts.commit(
                branch=branch,
                champion=champ_snapshot,
                phase="code",
                status="failed",
                transition_reason=self._direct_attempts.failure_reason(exc, receipt),
                failure_lane=(
                    "infra" if category == "infra" else "invalid_response"
                ),
                hypothesis=hypothesis,
                bound_hypothesis_digest=bound_hypothesis_digest,
            )
            if not committed:
                return None
            logger.warning("Branch %s: code LLM error: %s", bid, exc)
            self.hypothesis_failure_details[bid] = str(exc)
            self._direct_attempts.record_execution_outcome(
                branch,
                phase="code",
                outcome=(
                    ExecutionOutcome.NOT_EVALUATED
                    if invalid_response
                    else ExecutionOutcome.BLOCKED_INFRA
                ),
                reason_code=(
                    "PROPOSAL_RESPONSE_INVALID"
                    if invalid_response
                    else "PROVIDER_CALL_BLOCKED_INFRA"
                ),
                detail=str(exc),
                error_type=type(exc).__name__,
                error_category=(receipt.error_category if receipt else None),
            )
            if not invalid_response:
                self.handle_failure(
                    branch,
                    FailureEvent(category=category, detail=str(exc)),
                )
            return None
        except Exception as exc:
            if self._direct_attempts.handle_unexpected_receipt_exception(
                branch=branch,
                champion=champ_snapshot,
                phase="code",
                error=exc,
                hypothesis=hypothesis,
                patch=result,
                bound_hypothesis_digest=bound_hypothesis_digest,
            ):
                return None
            raise
