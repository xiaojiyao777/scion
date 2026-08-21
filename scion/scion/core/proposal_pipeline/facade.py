"""Direct V3 hypothesis/code proposal service."""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from scion.core.code_research_limits import CodeResearchLimits
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
from scion.core.resource_envelope import ProviderCallCapExhausted
from scion.proposal.code_research_session import (
    CodeResearchAbandon,
    CodeResearchSession,
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
from scion.proposal.hypothesis_research_session import (
    HypothesisResearchAbstain,
    HypothesisResearchContextError,
    HypothesisResearchFinalized,
    HypothesisResearchSession,
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

_ORDINARY_HYPOTHESIS_REJECTION_REASONS = frozenset(
    {
        "HYPOTHESIS_PROPOSAL_INVALID",
        "HYPOTHESIS_RESEARCH_ABSTAINED",
    }
)
_HYPOTHESIS_RESEARCH_RESOURCE_REASONS = frozenset(
    {
        "HYPOTHESIS_RESEARCH_RESULT_CAP_EXHAUSTED",
        "HYPOTHESIS_RESEARCH_TRANSCRIPT_EXHAUSTED",
        "HYPOTHESIS_RESEARCH_TURN_CAP_EXHAUSTED",
    }
)
_HYPOTHESIS_REJECTION_COUNT_LIMIT = 99


@dataclass
class ProposalPipeline:
    """Build complete contexts for direct H/C and optional bounded C research."""

    creative: CreativeLayerLike
    problem_runtime: ProblemRuntimeLike
    branch_workspaces: Mapping[str, str]
    champion_lock: Any
    get_champion: Callable[[], ChampionState]
    step_history: list[StepRecord]
    mark_balance_exhausted: Callable[[], None]
    code_research_limits: CodeResearchLimits | None = None
    code_development_evaluator: Any | None = None
    _hypothesis_rejection_counts: dict[str, int] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )
    _last_hypothesis_rejection_reason: str | None = field(
        default=None,
        init=False,
        repr=False,
    )

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
            public_sources: tuple[Mapping[str, Any], ...] = ()
            source_prefixes: tuple[str, ...] = ()
            if self.code_research_limits is not None:
                public_sources = tuple(
                    self.problem_runtime.hypothesis_research_public_sources()
                )
                source_prefixes = tuple(
                    self.problem_runtime.hypothesis_research_source_prefixes()
                )
        except (TypeError, ValueError) as exc:
            return self._hypothesis_failure(
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
            if self.code_research_limits is None:
                hypothesis = self.creative.generate_direct_hypothesis(prompt_snapshot)
            else:
                research_result = HypothesisResearchSession(
                    self.creative,
                    self.code_research_limits,
                ).run(
                    prompt_snapshot,
                    public_sources=public_sources,
                    qualified_prefixes=source_prefixes,
                )
                if isinstance(research_result, HypothesisResearchAbstain):
                    return self._hypothesis_failure(
                        self._record_local_failure(
                            phase="hypothesis",
                            outcome=ExecutionOutcome.RESEARCH_REJECTED,
                            reason_code="HYPOTHESIS_RESEARCH_ABSTAINED",
                            detail=research_result.reason,
                        )
                    )
                if not isinstance(research_result, HypothesisResearchFinalized):
                    raise TypeError("hypothesis research returned an invalid result")
                hypothesis = research_result.hypothesis
        except HypothesisResearchContextError as exc:
            return self._hypothesis_failure(
                self._record_local_failure(
                    phase="hypothesis",
                    outcome=ExecutionOutcome.NOT_EVALUATED,
                    reason_code="PROPOSAL_CONTEXT_INVALID",
                    detail=str(exc),
                    error=exc,
                )
            )
        except ProviderCallCapExhausted as exc:
            return self._hypothesis_failure(
                self._handle_provider_failure(branch, "hypothesis", exc)
            )
        except LLMBalanceError as exc:
            return self._hypothesis_failure(
                self._handle_provider_failure(branch, "hypothesis", exc, balance=True)
            )
        except _KNOWN_PROVIDER_ERRORS as exc:
            return self._hypothesis_failure(
                self._handle_provider_failure(branch, "hypothesis", exc)
            )
        except Exception as exc:  # noqa: BLE001 - return one typed proposal outcome
            return self._hypothesis_failure(
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
            if self.code_research_limits is None:
                patch = self.creative.generate_direct_code(prompt_snapshot)
            else:
                test_patch = None
                if self.code_development_evaluator is not None:
                    selected_surface = getattr(hypothesis, "change_locus", None)

                    def test_patch(
                        patch: PatchProposal,
                        remaining_timeout_sec: float,
                        source_corpus: Mapping[str, str],
                        falsifier_source: str | None,
                    ) -> dict[str, Any]:
                        run = self.code_development_evaluator.evaluate(
                            source_corpus=source_corpus,
                            patch=patch,
                            selected_surface=selected_surface,
                            total_timeout_sec=remaining_timeout_sec,
                            falsifier_source=falsifier_source,
                        )
                        return run.provider_projection()

                research_result = CodeResearchSession(
                    self.creative,
                    self.code_research_limits,
                    test_patch=test_patch,
                ).run(prompt_snapshot)
                if isinstance(research_result, CodeResearchAbandon):
                    return ProposalAttempt.failure(
                        self._record_local_failure(
                            phase="code",
                            outcome=ExecutionOutcome.RESEARCH_REJECTED,
                            reason_code="CODE_RESEARCH_ABANDONED",
                            detail=research_result.reason,
                        )
                    )
                patch = research_result
        except ProviderCallCapExhausted as exc:
            return ProposalAttempt.failure(
                self._handle_provider_failure(branch, "code", exc)
            )
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
        except Exception as exc:  # noqa: BLE001 - return one typed proposal outcome
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
        if "hypothesis_rejection_summary" in context:
            raise ValueError("hypothesis rejection summary is pipeline-owned")
        rejection_summary = self._hypothesis_rejection_summary()
        if rejection_summary is not None:
            context = dict(context)
            context["hypothesis_rejection_summary"] = rejection_summary
        context_snapshot = freeze_proposal_context("hypothesis", context)
        return context_snapshot, build_prompt_turn_snapshot(
            "hypothesis",
            context_snapshot,
        )

    def _hypothesis_failure(
        self,
        record: ExecutionOutcomeRecord,
    ) -> ProposalAttempt[HypothesisProposal]:
        eligible = (
            record.outcome is ExecutionOutcome.RESEARCH_REJECTED
            and record.reason_code in _ORDINARY_HYPOTHESIS_REJECTION_REASONS
        )
        if eligible:
            reason_code = record.reason_code
            self._hypothesis_rejection_counts[reason_code] = min(
                self._hypothesis_rejection_counts.get(reason_code, 0) + 1,
                _HYPOTHESIS_REJECTION_COUNT_LIMIT,
            )
            self._last_hypothesis_rejection_reason = reason_code
        return ProposalAttempt.failure(record)

    def _hypothesis_rejection_summary(self) -> dict[str, Any] | None:
        if self._last_hypothesis_rejection_reason is None:
            return None
        return {
            "reason_counts": {
                reason_code: self._hypothesis_rejection_counts[reason_code]
                for reason_code in sorted(self._hypothesis_rejection_counts)
            },
            "last_reason": self._last_hypothesis_rejection_reason,
        }

    def _handle_provider_failure(
        self,
        branch: Branch,
        phase: str,
        error: Exception,
        *,
        balance: bool = False,
    ) -> ExecutionOutcomeRecord:
        call_cap_exhausted = isinstance(error, ProviderCallCapExhausted)
        invalid = isinstance(error, (LLMFormatError, ProposalValidationError))
        validation_reason = (
            _proposal_validation_reason_code(error, phase=phase) if invalid else None
        )
        h_research_resource_exhausted = (
            phase == "hypothesis"
            and validation_reason in _HYPOTHESIS_RESEARCH_RESOURCE_REASONS
        )
        outcome_value = (
            ExecutionOutcome.RESOURCE_EXHAUSTED
            if balance or call_cap_exhausted or h_research_resource_exhausted
            else ExecutionOutcome.RESEARCH_REJECTED
            if invalid
            else ExecutionOutcome.BLOCKED_INFRA
        )
        reason_code = (
            "PROVIDER_BALANCE_EXHAUSTED"
            if balance
            else "PROVIDER_CALL_CAP_EXHAUSTED"
            if call_cap_exhausted
            else validation_reason
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
        elif call_cap_exhausted:
            logger.error("Branch %s: provider call cap exhausted", branch.branch_id)
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


def _proposal_validation_reason_code(error: Exception, *, phase: str) -> str:
    if not isinstance(error, ProposalValidationError):
        return "PROPOSAL_RESPONSE_INVALID"
    message = str(error).lower()
    if phase == "hypothesis":
        if "transcript exceeds max_transcript_chars" in message:
            return "HYPOTHESIS_RESEARCH_TRANSCRIPT_EXHAUSTED"
        if "turn cap exhausted" in message or "local provider call cap" in message:
            return "HYPOTHESIS_RESEARCH_TURN_CAP_EXHAUSTED"
        if "tool results exceed" in message:
            return "HYPOTHESIS_RESEARCH_RESULT_CAP_EXHAUSTED"
        return "HYPOTHESIS_PROPOSAL_INVALID"
    if phase == "code":
        if "transcript exceeds max_transcript_chars" in message:
            return "CODE_RESEARCH_TRANSCRIPT_EXHAUSTED"
        if "local provider call cap exhausted" in message:
            return "CODE_RESEARCH_TURN_CAP_EXHAUSTED"
        if "test results exceed" in message or "tool results exceed" in message:
            return "CODE_RESEARCH_RESULT_CAP_EXHAUSTED"
        return "PATCH_PROPOSAL_INVALID"
    return "PROPOSAL_RESPONSE_INVALID"
