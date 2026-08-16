"""Direct V3 hypothesis/code proposal service."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from scion.core.execution_outcome import (
    ExecutionOutcome,
    ExecutionOutcomeRecord,
)
from scion.core.models import (
    Branch,
    ChampionState,
    HypothesisProposal,
    PatchProposal,
    StepRecord,
)
from scion.proposal.context_snapshot import (
    ProposalContextSnapshot,
    freeze_proposal_context,
)
from scion.proposal.engine import (
    PromptTurnSnapshot,
    ProposalValidationError,
    build_prompt_turn_snapshot,
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

from .protocols import (
    CreativeLayerLike,
    ProblemRuntimeLike,
    ProposalAttempt,
)

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
class ProposalPipeline:
    """Build complete contexts and make exactly one in-process H/C call."""

    creative: CreativeLayerLike
    problem_runtime: ProblemRuntimeLike
    branch_workspaces: Mapping[str, str]
    champion_lock: Any
    get_champion: Callable[[], ChampionState]
    step_history: list[StepRecord]
    mark_balance_exhausted: Callable[[], None]

    def generate_hypothesis(
        self,
        branch: Branch,
    ) -> ProposalAttempt[HypothesisProposal]:
        champion = self._champion_snapshot()
        try:
            _context_snapshot, prompt_snapshot = self._hypothesis_snapshots(
                branch,
                champion,
            )
        except (TypeError, ValueError) as exc:
            return ProposalAttempt.failure(
                self._record_local_failure(
                    phase="hypothesis",
                    outcome=ExecutionOutcome.NOT_EVALUATED,
                    reason_code="PROPOSAL_CONTEXT_INVALID",
                    detail=(
                        f"proposal_context_validation_failed:{type(exc).__name__}:{exc}"
                    ),
                    error=exc,
                )
            )

        try:
            hypothesis = self.creative.generate_direct_hypothesis(prompt_snapshot)
        except LLMBalanceError as exc:
            return ProposalAttempt.failure(
                self._handle_provider_failure(branch, "hypothesis", exc, balance=True)
            )
        except _KNOWN_PROVIDER_ERRORS as exc:
            return ProposalAttempt.failure(
                self._handle_provider_failure(branch, "hypothesis", exc)
            )
        except Exception as exc:
            return ProposalAttempt.failure(
                self._record_unexpected_call_failure("hypothesis", exc)
            )
        return ProposalAttempt.success(hypothesis)

    def generate_code(
        self,
        branch: Branch,
        hypothesis: HypothesisProposal,
    ) -> ProposalAttempt[PatchProposal]:
        branch_id = branch.branch_id
        champion = self._champion_snapshot()
        try:
            context = self.problem_runtime.build_code_context(
                branch=branch,
                hypothesis=hypothesis,
                champion=champion,
                branch_workspace=self.branch_workspaces.get(branch_id),
                step_history=self.step_history,
            )
            context_snapshot = freeze_proposal_context("code", context)
            prompt_snapshot = build_prompt_turn_snapshot("code", context_snapshot)
        except (TypeError, ValueError) as exc:
            return ProposalAttempt.failure(
                self._record_local_failure(
                    phase="code",
                    outcome=ExecutionOutcome.NOT_EVALUATED,
                    reason_code="PROPOSAL_CONTEXT_INVALID",
                    detail=(
                        f"proposal_context_validation_failed:{type(exc).__name__}:{exc}"
                    ),
                    error=exc,
                )
            )

        try:
            patch = self.creative.generate_direct_code(prompt_snapshot)
        except LLMBalanceError as exc:
            return ProposalAttempt.failure(
                self._handle_provider_failure(
                    branch,
                    "code",
                    exc,
                    balance=True,
                )
            )
        except _KNOWN_PROVIDER_ERRORS as exc:
            return ProposalAttempt.failure(
                self._handle_provider_failure(
                    branch,
                    "code",
                    exc,
                )
            )
        except Exception as exc:
            return ProposalAttempt.failure(
                self._record_unexpected_call_failure(
                    "code",
                    exc,
                )
            )

        return ProposalAttempt.success(patch)

    def _hypothesis_snapshots(
        self,
        branch: Branch,
        champion: ChampionState,
    ) -> tuple[ProposalContextSnapshot, PromptTurnSnapshot]:
        context = self.problem_runtime.build_hypothesis_context(
            branch=branch,
            champion=champion,
            step_history=self.step_history,
            branch_workspace=self.branch_workspaces.get(branch.branch_id),
        )
        context_snapshot = freeze_proposal_context("hypothesis", context)
        return context_snapshot, build_prompt_turn_snapshot(
            "hypothesis",
            context_snapshot,
        )

    def _handle_provider_failure(
        self,
        branch: Branch,
        phase: str,
        error: Exception,
        *,
        balance: bool = False,
    ) -> ExecutionOutcomeRecord:
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
        record = self._outcome(
            phase=phase,
            outcome=outcome_value,
            reason_code=reason_code,
            detail=str(error),
            error=error,
        )
        if balance:
            logger.critical("Branch %s: provider balance exhausted", branch.branch_id)
            self.mark_balance_exhausted()
        return record

    def _record_unexpected_call_failure(
        self,
        phase: str,
        error: Exception,
    ) -> ExecutionOutcomeRecord:
        return self._outcome(
            phase=phase,
            outcome=ExecutionOutcome.BLOCKED_INFRA,
            reason_code="PROPOSAL_UNEXPECTED_FAILURE",
            detail=type(error).__name__,
            error=error,
        )

    def _record_local_failure(
        self,
        *,
        phase: str,
        outcome: ExecutionOutcome,
        reason_code: str,
        detail: str,
        error: BaseException | None = None,
    ) -> ExecutionOutcomeRecord:
        return self._outcome(
            phase=phase,
            outcome=outcome,
            reason_code=reason_code,
            detail=detail,
            error=error,
        )

    def _outcome(
        self,
        *,
        phase: str,
        outcome: ExecutionOutcome,
        reason_code: str,
        detail: str,
        error: BaseException | None,
    ) -> ExecutionOutcomeRecord:
        provenance: dict[str, Any] = {
            "stage": f"proposal_{phase}",
            "phase": phase,
        }
        if error is not None:
            provenance["exception_type"] = type(error).__name__
        record = ExecutionOutcomeRecord(
            outcome=outcome,
            reason_code=reason_code,
            detail=str(detail or ""),
            provenance=provenance,
        )
        return record

    def _champion_snapshot(self) -> ChampionState:
        with self.champion_lock:
            return self.get_champion()


__all__ = ["ProposalPipeline"]
