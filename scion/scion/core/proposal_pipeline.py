"""LLM proposal lifecycle service for campaign explore steps."""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Mapping, MutableMapping, Protocol

from scion.core.models import (
    Branch,
    ChampionState,
    FailureEvent,
    HypothesisProposal,
    HypothesisRecord,
    PatchProposal,
    StepRecord,
    VerificationResult,
)
from scion.proposal.engine import ProposalValidationError
from scion.proposal.llm_client import (
    LLMBalanceError,
    LLMFormatError,
    LLMRetryExhaustedError,
    LLMTimeoutError,
)

logger = logging.getLogger(__name__)


class CreativeLayerLike(Protocol):
    def generate_hypothesis(self, context: dict[str, Any]) -> HypothesisProposal:
        ...

    def generate_code(self, context: dict[str, Any]) -> PatchProposal:
        ...

    def fix_code(self, context: dict[str, Any]) -> PatchProposal | None:
        ...


class ProblemRuntimeLike(Protocol):
    def build_hypothesis_context(self, **kwargs: Any) -> dict[str, Any]:
        ...

    def build_code_context(self, **kwargs: Any) -> dict[str, Any]:
        ...

    def build_fix_context(self, **kwargs: Any) -> dict[str, Any]:
        ...


class BranchControllerLike(Protocol):
    def get_active_branches(self) -> list[Branch]:
        ...


class HypothesisStoreLike(Protocol):
    def get_by_status(self, status: str) -> list[HypothesisRecord]:
        ...


class ClassifierLike(Protocol):
    def classify(self, text: str) -> Any:
        ...


class CircuitBreakerLike(Protocol):
    def record_success(self) -> None:
        ...

    def record_failure(self, detail: str) -> bool:
        ...


@dataclass
class ProposalPipeline:
    """Own Round 1/Round 2/fix LLM proposal interactions.

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
    failure_streak: MutableMapping[str, int]
    consume_forced_locus: Callable[[], str | None]
    search_memory: Any
    get_saturation_analyzer: Callable[[], Any]
    get_baseline_metrics: Callable[[], dict[str, float] | None]
    get_latest_weight_opt_result: Callable[[], Any]
    research_log: Any
    handle_failure: Callable[[Branch, FailureEvent], None]
    circuit_breaker: CircuitBreakerLike
    mark_balance_exhausted: Callable[[], None]

    def generate_hypothesis(
        self,
        branch: Branch,
    ) -> tuple[HypothesisProposal | None, HypothesisRecord | None]:
        bid = branch.branch_id
        siblings = [
            b for b in self.branch_controller.get_active_branches()
            if b.branch_id != bid
        ]
        branch_workspace = self.branch_workspaces.get(bid)
        champ_snapshot = self._champion_snapshot()
        context = self.problem_runtime.build_hypothesis_context(
            branch=branch,
            champion=champ_snapshot,
            active_hypotheses=self.hypothesis_store.get_by_status("active"),
            blacklist=self.hypothesis_store.get_by_status("blacklisted"),
            sibling_branches=siblings,
            step_history=self.step_history,
            branch_workspace=branch_workspace,
            failure_streak=dict(self.failure_streak),
            forced_locus=self.consume_forced_locus(),
            search_memory=self.search_memory,
            saturation_signals=self._compute_saturation_signals(),
            weight_opt_result=self.get_latest_weight_opt_result(),
            research_log=self.research_log,
        )
        try:
            hypothesis = self.creative.generate_hypothesis(context)
        except LLMBalanceError as exc:
            logger.critical(
                "Branch %s: API balance exhausted - stopping campaign: %s",
                bid,
                exc,
            )
            self.mark_balance_exhausted()
            self.circuit_breaker.record_failure(str(exc))
            return None, None
        except (
            LLMRetryExhaustedError,
            LLMFormatError,
            LLMTimeoutError,
            ProposalValidationError,
        ) as exc:
            logger.warning("Branch %s: hypothesis LLM error: %s", bid, exc)
            self.handle_failure(branch, FailureEvent(category="proposal", detail=str(exc)))
            self.circuit_breaker.record_failure(str(exc))
            return None, None

        self.circuit_breaker.record_success()
        cls_result = self.classifier.classify(hypothesis.hypothesis_text or "")
        record = HypothesisRecord(
            hypothesis_id=str(uuid.uuid4()),
            branch_id=bid,
            change_locus=hypothesis.change_locus,
            action=hypothesis.action,
            status="active",
            target_file=hypothesis.target_file,
            suggested_weight=hypothesis.suggested_weight,
            hypothesis_text=hypothesis.hypothesis_text,
            family_id=cls_result.family_id,
            family_source=cls_result.source,
            taxonomy_version=cls_result.taxonomy_version,
        )
        return hypothesis, record

    def generate_code(
        self,
        branch: Branch,
        hypothesis: HypothesisProposal,
        *,
        prior_failure: str | None = None,
    ) -> PatchProposal | None:
        bid = branch.branch_id
        context = self.problem_runtime.build_code_context(
            branch=branch,
            hypothesis=hypothesis,
            champion=self._champion_snapshot(),
            prior_failure=prior_failure,
        )
        try:
            result = self.creative.generate_code(context)
            self.circuit_breaker.record_success()
            return result
        except LLMBalanceError as exc:
            logger.critical(
                "Branch %s: API balance exhausted - stopping campaign: %s",
                bid,
                exc,
            )
            self.mark_balance_exhausted()
            self.circuit_breaker.record_failure(str(exc))
            return None
        except (
            LLMRetryExhaustedError,
            LLMFormatError,
            LLMTimeoutError,
            ProposalValidationError,
        ) as exc:
            logger.warning("Branch %s: code LLM error: %s", bid, exc)
            self.handle_failure(branch, FailureEvent(category="proposal", detail=str(exc)))
            self.circuit_breaker.record_failure(str(exc))
            return None

    def attempt_fix(
        self,
        branch: Branch,
        patch: PatchProposal,
        verification_result: VerificationResult,
    ) -> PatchProposal | None:
        logger.info(
            "Branch %s: attempting fix_code after %s light verification failure",
            branch.branch_id,
            verification_result.first_failure or "unknown",
        )
        context = self.problem_runtime.build_fix_context(
            branch=branch,
            patch=patch,
            verification_result=verification_result,
            failure_streak=dict(self.failure_streak),
        )
        try:
            fixed = self.creative.fix_code(context)
            if fixed is None:
                logger.info("Branch %s: fix_code returned no patch", branch.branch_id)
            else:
                logger.info(
                    "Branch %s: fix_code produced patch for %s",
                    branch.branch_id,
                    fixed.file_path,
                )
            return fixed
        except LLMBalanceError as exc:
            logger.critical(
                "Branch %s: API balance exhausted during fix - stopping campaign: %s",
                branch.branch_id,
                exc,
            )
            self.mark_balance_exhausted()
            self.circuit_breaker.record_failure(str(exc))
            return None
        except (
            LLMRetryExhaustedError,
            LLMFormatError,
            LLMTimeoutError,
            ProposalValidationError,
        ) as exc:
            logger.warning("Branch %s: fix LLM error: %s", branch.branch_id, exc)
            return None

    def _champion_snapshot(self) -> ChampionState:
        with self.champion_lock:
            return self.get_champion()

    def _compute_saturation_signals(self) -> Any:
        analyzer = self.get_saturation_analyzer()
        if analyzer is None:
            return None

        from scion.proposal.saturation import extract_candidate_metrics_from_step

        current_metrics = self.get_baseline_metrics()
        for step in reversed(self.step_history):
            if step.decision is not None and step.decision.value == "promote":
                metrics = extract_candidate_metrics_from_step(step)
                if metrics:
                    current_metrics = metrics
                    break
        if current_metrics:
            return analyzer.analyze(current_metrics)
        return None
