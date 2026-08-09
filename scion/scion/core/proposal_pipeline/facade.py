"""Direct V3 hypothesis/code proposal service."""
from __future__ import annotations

import inspect
import logging
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Mapping, MutableMapping, Sequence

from scion.core.execution_outcome import (
    ExecutionOutcome,
    ExecutionOutcomeRecord,
    install_branch_execution_hold,
)
from scion.core.models import (
    Branch,
    ChampionState,
    FailureEvent,
    HypothesisProposal,
    HypothesisRecord,
    PatchProposal,
    StepRecord,
)
from scion.proposal.context_owner_maps import proposal_context_snapshot
from scion.proposal.context_snapshot import ProposalContextSnapshot
from scion.proposal.engine import (
    PromptTurnSnapshot,
    ProposalValidationError,
    ProviderCallDiagnostics,
    build_prompt_turn_snapshot,
    provider_call_diagnostics_from_error,
)
from scion.proposal.llm_client import (
    LLMAuthError,
    LLMBalanceError,
    LLMFormatError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMTransportError,
)
from scion.proposal.prompt_manifest import stable_digest

from .call_journal import ProposalCallJournal
from .protocols import (
    BranchControllerLike,
    ClassifierLike,
    CreativeLayerLike,
    HypothesisStoreLike,
    ProblemRuntimeLike,
)
from .records import ProposalRecordMixin

logger = logging.getLogger(__name__)

_KNOWN_PROVIDER_ERRORS = (
    LLMAuthError,
    LLMFormatError,
    LLMProviderError,
    LLMTimeoutError,
    LLMTransportError,
    LLMRateLimitError,
    ProposalValidationError,
)


@dataclass
class ProposalPipeline(ProposalRecordMixin):
    """Build complete contexts and make exactly one in-process H/C call."""

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
    _call_journal: ProposalCallJournal = field(init=False, repr=False)
    _call_refs: dict[str, Mapping[str, Any]] = field(
        init=False,
        repr=False,
        default_factory=dict,
    )
    _execution_outcomes: dict[str, ExecutionOutcomeRecord] = field(
        init=False,
        repr=False,
        default_factory=dict,
    )
    _consumed_code_hypotheses: set[str] = field(
        init=False,
        repr=False,
        default_factory=set,
    )

    def __post_init__(self) -> None:
        self._call_journal = ProposalCallJournal(
            self.lineage_registry,
            self.campaign_id,
        )

    def pop_proposal_attempt_ref(self, branch_id: str) -> Mapping[str, Any] | None:
        """Compatibility name for reading the current proposal-call ref."""

        return self._call_refs.get(branch_id)

    def pop_hypothesis_failure_detail(self, branch_id: str) -> str | None:
        return self.hypothesis_failure_details.pop(branch_id, None)

    def pop_execution_outcome(
        self,
        branch_id: str,
    ) -> ExecutionOutcomeRecord | None:
        return self._execution_outcomes.pop(branch_id, None)

    def discard_approved_hypothesis_binding(self, branch_id: str) -> None:
        """Forget only the in-process C-call consumption marker, if present."""

        for record in self.hypothesis_store.get_by_branch(branch_id):
            self._consumed_code_hypotheses.discard(record.hypothesis_id)

    def generate_hypothesis(
        self,
        branch: Branch,
    ) -> tuple[HypothesisProposal | None, HypothesisRecord | None]:
        branch_id = branch.branch_id
        self._reset_branch_result(branch_id)
        champion = self._champion_snapshot()
        try:
            context_snapshot, prompt_snapshot = self._hypothesis_snapshots(
                branch,
                champion,
            )
        except (TypeError, ValueError) as exc:
            self._record_local_failure(
                branch,
                phase="hypothesis",
                outcome=ExecutionOutcome.NOT_EVALUATED,
                reason_code="PROPOSAL_CONTEXT_INVALID",
                detail=f"proposal_context_validation_failed:{type(exc).__name__}:{exc}",
                error=exc,
                route_infra=False,
            )
            return None, None

        diagnostics: ProviderCallDiagnostics | None = None
        try:
            hypothesis, diagnostics = self._generate_hypothesis_call(
                branch_id,
                context_snapshot,
                prompt_snapshot,
            )
        except KeyboardInterrupt as exc:
            diagnostics = provider_call_diagnostics_from_error(exc)
            outcome = self._outcome(
                branch,
                phase="hypothesis",
                outcome=ExecutionOutcome.INTERRUPTED,
                reason_code="PROPOSAL_PROVIDER_INTERRUPTED",
                detail=f"provider_call_interrupted:{type(exc).__name__}",
                error=exc,
                diagnostics=diagnostics,
            )
            install_branch_execution_hold(branch, outcome)
            self._append_call(
                branch_id=branch_id,
                phase="hypothesis",
                status="interrupted",
                hypothesis_id=None,
                diagnostics=diagnostics,
                outcome=outcome,
            )
            raise
        except LLMBalanceError as exc:
            self._handle_provider_failure(branch, "hypothesis", exc, balance=True)
            return None, None
        except _KNOWN_PROVIDER_ERRORS as exc:
            self._handle_provider_failure(branch, "hypothesis", exc)
            return None, None
        except Exception as exc:
            self._record_unexpected_call_failure(branch, "hypothesis", exc)
            raise

        digest = _hypothesis_digest(hypothesis)
        record = self._hypothesis_record(
            branch,
            hypothesis,
            champion=champion,
            proposal_digest=digest,
        )
        try:
            self.hypothesis_store.save(record)
        except Exception as exc:
            outcome = self._outcome(
                branch,
                phase="hypothesis",
                outcome=ExecutionOutcome.BLOCKED_INFRA,
                reason_code="HYPOTHESIS_STORE_WRITE_FAILED",
                detail=f"hypothesis_store_write_failed:{type(exc).__name__}",
                error=exc,
                diagnostics=diagnostics,
            )
            self._append_call(
                branch_id=branch_id,
                phase="hypothesis",
                status="generated",
                hypothesis_id=record.hypothesis_id,
                diagnostics=diagnostics,
                outcome=outcome,
            )
            raise
        self._append_call(
            branch_id=branch_id,
            phase="hypothesis",
            status="generated",
            hypothesis_id=record.hypothesis_id,
            diagnostics=diagnostics,
            outcome=None,
        )
        return hypothesis, record

    def generate_code(
        self,
        branch: Branch,
        hypothesis: HypothesisProposal,
    ) -> PatchProposal | None:
        branch_id = branch.branch_id
        self._reset_branch_result(branch_id)
        record = self._consume_code_binding(branch, hypothesis)
        if record is None:
            return None
        champion = self._champion_snapshot()
        try:
            context = self.problem_runtime.build_code_context(
                branch=branch,
                hypothesis=hypothesis,
                champion=champion,
                branch_workspace=self.branch_workspaces.get(branch_id),
                step_history=self.step_history,
            )
            context_snapshot = proposal_context_snapshot("code", context)
            prompt_snapshot = build_prompt_turn_snapshot("code", context_snapshot)
        except (TypeError, ValueError) as exc:
            self._record_local_failure(
                branch,
                phase="code",
                outcome=ExecutionOutcome.NOT_EVALUATED,
                reason_code="PROPOSAL_CONTEXT_INVALID",
                detail=f"proposal_context_validation_failed:{type(exc).__name__}:{exc}",
                error=exc,
                route_infra=False,
            )
            return None

        try:
            patch, diagnostics = self._generate_code_call(
                branch_id,
                record.hypothesis_id,
                context_snapshot,
                prompt_snapshot,
            )
        except KeyboardInterrupt as exc:
            diagnostics = provider_call_diagnostics_from_error(exc)
            outcome = self._outcome(
                branch,
                phase="code",
                outcome=ExecutionOutcome.INTERRUPTED,
                reason_code="PROPOSAL_PROVIDER_INTERRUPTED",
                detail=f"provider_call_interrupted:{type(exc).__name__}",
                error=exc,
                diagnostics=diagnostics,
            )
            install_branch_execution_hold(branch, outcome)
            self._append_call(
                branch_id=branch_id,
                phase="code",
                status="interrupted",
                hypothesis_id=record.hypothesis_id,
                diagnostics=diagnostics,
                outcome=outcome,
            )
            raise
        except LLMBalanceError as exc:
            self._handle_provider_failure(
                branch,
                "code",
                exc,
                hypothesis_id=record.hypothesis_id,
                balance=True,
            )
            return None
        except _KNOWN_PROVIDER_ERRORS as exc:
            self._handle_provider_failure(
                branch,
                "code",
                exc,
                hypothesis_id=record.hypothesis_id,
            )
            return None
        except Exception as exc:
            self._record_unexpected_call_failure(
                branch,
                "code",
                exc,
                hypothesis_id=record.hypothesis_id,
            )
            raise

        self._append_call(
            branch_id=branch_id,
            phase="code",
            status="generated",
            hypothesis_id=record.hypothesis_id,
            diagnostics=diagnostics,
            outcome=None,
        )
        return patch

    def _hypothesis_snapshots(
        self,
        branch: Branch,
        champion: ChampionState,
    ) -> tuple[ProposalContextSnapshot, PromptTurnSnapshot]:
        context = self.problem_runtime.build_hypothesis_context(
            branch=branch,
            champion=champion,
            step_history=self.step_history,
            campaign_branches=(
                tuple(self.campaign_branches_provider() or ())
                if self.campaign_branches_provider is not None
                else None
            ),
            branch_workspace=self.branch_workspaces.get(branch.branch_id),
            last_research_rejection=self._latest_research_rejection_feedback(),
        )
        context_snapshot = proposal_context_snapshot("hypothesis", context)
        return context_snapshot, build_prompt_turn_snapshot(
            "hypothesis",
            context_snapshot,
        )

    def _latest_research_rejection_feedback(self) -> Mapping[str, str] | None:
        reader = getattr(
            self.lineage_registry,
            "get_latest_research_rejection_feedback",
            None,
        )
        if not callable(reader) or not self.campaign_id:
            return None
        return reader(campaign_id=self.campaign_id)

    def _generate_hypothesis_call(
        self,
        branch_id: str,
        context_snapshot: ProposalContextSnapshot,
        prompt_snapshot: PromptTurnSnapshot,
    ) -> tuple[HypothesisProposal, ProviderCallDiagnostics]:
        method = self.creative.generate_direct_hypothesis
        context = context_snapshot.inputs.provider_context(
            include_renderer_inputs=True
        )
        return method(
            context,
            prompt_snapshot,
            **_diagnostic_keyword(
                method,
                _call_context(self.campaign_id, branch_id, "hypothesis", None),
            ),
        )

    def _generate_code_call(
        self,
        branch_id: str,
        hypothesis_id: str,
        context_snapshot: ProposalContextSnapshot,
        prompt_snapshot: PromptTurnSnapshot,
    ) -> tuple[PatchProposal, ProviderCallDiagnostics]:
        method = self.creative.generate_direct_code
        context = context_snapshot.inputs.provider_context(
            include_renderer_inputs=True
        )
        return method(
            context,
            prompt_snapshot,
            **_diagnostic_keyword(
                method,
                _call_context(self.campaign_id, branch_id, "code", hypothesis_id),
            ),
        )

    def _consume_code_binding(
        self,
        branch: Branch,
        hypothesis: HypothesisProposal,
    ) -> HypothesisRecord | None:
        digest = _hypothesis_digest(hypothesis)
        records = self.hypothesis_store.get_by_branch(branch.branch_id)
        record = next(
            (
                item
                for item in reversed(records)
                if item.status == "active" and item.proposal_digest == digest
            ),
            None,
        )
        if record is None or record.branch_id != branch.branch_id:
            self._record_local_failure(
                branch,
                phase="code",
                outcome=ExecutionOutcome.NOT_EVALUATED,
                reason_code="APPROVED_HYPOTHESIS_BINDING_MISSING",
                detail="code call does not match an active Contract-approved H",
                route_infra=False,
            )
            return None
        if record.hypothesis_id in self._consumed_code_hypotheses:
            self._record_local_failure(
                branch,
                phase="code",
                outcome=ExecutionOutcome.NOT_EVALUATED,
                reason_code="CODE_CALL_ALREADY_CONSUMED",
                detail="the approved H has already entered its one C call",
                route_infra=False,
            )
            return None
        self._consumed_code_hypotheses.add(record.hypothesis_id)
        return record

    def _handle_provider_failure(
        self,
        branch: Branch,
        phase: str,
        error: Exception,
        *,
        hypothesis_id: str | None = None,
        balance: bool = False,
    ) -> None:
        diagnostics = provider_call_diagnostics_from_error(error)
        invalid = isinstance(error, (LLMFormatError, ProposalValidationError))
        outcome_value = (
            ExecutionOutcome.RESOURCE_EXHAUSTED
            if balance
            else ExecutionOutcome.RESEARCH_REJECTED
            if invalid
            else ExecutionOutcome.BLOCKED_INFRA
        )
        reason_code = (
            "PROVIDER_BALANCE_EXHAUSTED"
            if balance
            else "PROPOSAL_RESPONSE_INVALID"
            if invalid
            else "PROVIDER_CALL_BLOCKED_INFRA"
        )
        outcome = self._outcome(
            branch,
            phase=phase,
            outcome=outcome_value,
            reason_code=reason_code,
            detail=str(error),
            error=error,
            diagnostics=diagnostics,
        )
        self.hypothesis_failure_details[branch.branch_id] = str(error)
        self._append_call(
            branch_id=branch.branch_id,
            phase=phase,
            status="failed",
            hypothesis_id=hypothesis_id,
            diagnostics=diagnostics,
            outcome=outcome,
        )
        if balance:
            logger.critical("Branch %s: provider balance exhausted", branch.branch_id)
            self.mark_balance_exhausted()
        elif not invalid:
            self.handle_failure(
                branch,
                FailureEvent(category="infra", detail=str(error)),
            )

    def _record_unexpected_call_failure(
        self,
        branch: Branch,
        phase: str,
        error: Exception,
        *,
        hypothesis_id: str | None = None,
    ) -> None:
        diagnostics = provider_call_diagnostics_from_error(error)
        if diagnostics is None:
            return
        blocked = diagnostics.error_category == "provider_call_failed"
        outcome = self._outcome(
            branch,
            phase=phase,
            outcome=(
                ExecutionOutcome.BLOCKED_INFRA
                if blocked
                else ExecutionOutcome.NOT_EVALUATED
            ),
            reason_code=(
                "PROPOSAL_INFRA_BLOCKED"
                if blocked
                else "PROPOSAL_POST_PROVIDER_INVALID"
            ),
            detail=f"{diagnostics.error_category}:{type(error).__name__}",
            error=error,
            diagnostics=diagnostics,
        )
        self._append_call(
            branch_id=branch.branch_id,
            phase=phase,
            status="failed",
            hypothesis_id=hypothesis_id,
            diagnostics=diagnostics,
            outcome=outcome,
        )

    def _record_local_failure(
        self,
        branch: Branch,
        *,
        phase: str,
        outcome: ExecutionOutcome,
        reason_code: str,
        detail: str,
        error: BaseException | None = None,
        route_infra: bool,
    ) -> None:
        record = self._outcome(
            branch,
            phase=phase,
            outcome=outcome,
            reason_code=reason_code,
            detail=detail,
            error=error,
            diagnostics=None,
        )
        self.hypothesis_failure_details[branch.branch_id] = detail
        if route_infra:
            self.handle_failure(
                branch,
                FailureEvent(category="infra", detail=detail),
            )
        self._execution_outcomes[branch.branch_id] = record

    def _outcome(
        self,
        branch: Branch,
        *,
        phase: str,
        outcome: ExecutionOutcome,
        reason_code: str,
        detail: str,
        error: BaseException | None,
        diagnostics: ProviderCallDiagnostics | None,
    ) -> ExecutionOutcomeRecord:
        provenance: dict[str, Any] = {
            "owner": "proposal_pipeline",
            "stage": f"proposal_{phase}",
            "phase": phase,
        }
        if error is not None:
            provenance["error_type"] = type(error).__name__
        if diagnostics is not None and diagnostics.error_category:
            provenance["error_category"] = diagnostics.error_category
        record = ExecutionOutcomeRecord(
            outcome=outcome,
            reason_code=reason_code,
            detail=str(detail or ""),
            provenance=provenance,
        )
        self._execution_outcomes[branch.branch_id] = record
        return record

    def _append_call(
        self,
        *,
        branch_id: str,
        phase: str,
        status: str,
        hypothesis_id: str | None,
        diagnostics: ProviderCallDiagnostics | None,
        outcome: ExecutionOutcomeRecord | None,
    ) -> None:
        self._call_refs[branch_id] = self._call_journal.append(
            branch_id=branch_id,
            phase=phase,
            status=status,
            hypothesis_id=hypothesis_id,
            diagnostics=diagnostics,
            execution_outcome=outcome,
        )

    def _reset_branch_result(self, branch_id: str) -> None:
        self._call_refs.pop(branch_id, None)
        self._execution_outcomes.pop(branch_id, None)
        self.hypothesis_failure_details.pop(branch_id, None)


def _hypothesis_digest(hypothesis: HypothesisProposal) -> str:
    """Content equality used only for the V3 H-to-C binding."""

    return stable_digest(asdict(hypothesis), length=64)


def _call_context(
    campaign_id: str,
    branch_id: str,
    phase: str,
    hypothesis_id: str | None,
) -> dict[str, Any]:
    return {
        "schema_version": "proposal-call-context.v1",
        "campaign_id": campaign_id,
        "branch_id": branch_id,
        "phase": phase,
        "hypothesis_id": hypothesis_id,
    }


def _diagnostic_keyword(
    method: Callable[..., Any],
    context: Mapping[str, Any],
) -> dict[str, Mapping[str, Any]]:
    """Pass opaque call diagnostics when the provider surface accepts them."""

    try:
        parameters = inspect.signature(method).parameters
    except (TypeError, ValueError):
        parameters = {}
    if "call_context" in parameters or any(
        parameter.kind is inspect.Parameter.VAR_KEYWORD
        for parameter in parameters.values()
    ):
        return {"call_context": context}
    return {}


__all__ = ["ProposalPipeline"]
