"""LLM proposal lifecycle service for campaign explore steps."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, MutableMapping

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
from scion.core.status_reporter import is_provider_balance_exhausted_detail
from scion.proposal.agentic_session import AgenticProposalOutput
from scion.proposal.engine import ProposalValidationError
from scion.proposal.llm_client import (
    LLMBalanceError,
    LLMFormatError,
    LLMRetryExhaustedError,
    LLMTimeoutError,
)

from .agentic_lifecycle import AgenticLifecycleMixin
from .agentic_refs import AgenticRefsMixin
from .agentic_requests import AgenticRequestMixin
from .agentic_validation import AgenticValidationMixin
from .boundaries import (
    BoundaryValidationMixin,
    _active_problem_boundary_surfaces_for_runtime,
)
from .protocols import (
    AgenticProposalSessionLike,
    BranchControllerLike,
    CircuitBreakerLike,
    ClassifierLike,
    CreativeLayerLike,
    HypothesisStoreLike,
    ProblemRuntimeLike,
)
from .records import ProposalRecordMixin

logger = logging.getLogger(__name__)


@dataclass
class ProposalPipeline(
    AgenticLifecycleMixin,
    AgenticRefsMixin,
    AgenticRequestMixin,
    AgenticValidationMixin,
    BoundaryValidationMixin,
    ProposalRecordMixin,
):
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
    hypothesis_failure_details: MutableMapping[str, str] = field(default_factory=dict)
    use_agentic_proposal: bool = False
    agentic_session: AgenticProposalSessionLike | None = None
    agentic_artifact_dir: str | None = None
    agentic_session_timeout_sec: float | None = None
    lineage_registry: Any | None = None
    split_manifest: Any | None = None
    seed_ledger: Any | None = None
    campaign_id: str = ""
    problem_id: str | None = None
    problem_spec_hash: str | None = None
    persistent_forced_locus: str | None = None
    forced_surface_action: str | None = None
    forced_surface_target_file: str | None = None
    forced_surface_diagnostic: bool = False
    agentic_outputs: MutableMapping[str, AgenticProposalOutput] = field(
        default_factory=dict
    )
    agentic_session_refs: MutableMapping[str, Mapping[str, Any]] = field(
        default_factory=dict
    )
    agentic_recovery_reports: MutableMapping[str, Mapping[str, Any]] = field(
        default_factory=dict
    )

    def generate_hypothesis(
        self,
        branch: Branch,
    ) -> tuple[HypothesisProposal | None, HypothesisRecord | None]:
        bid = branch.branch_id
        self.hypothesis_failure_details.pop(bid, None)
        siblings = [
            b for b in self.branch_controller.get_active_branches()
            if b.branch_id != bid
        ]
        branch_workspace = self.branch_workspaces.get(bid)
        champ_snapshot = self._champion_snapshot()
        transient_forced_locus = self.consume_forced_locus()
        forced_locus = self.persistent_forced_locus or transient_forced_locus
        forced_action = self.forced_surface_action if forced_locus else None
        forced_target_file = (
            self.forced_surface_target_file if forced_locus else None
        )
        forced_diagnostic = self.forced_surface_diagnostic if forced_locus else False
        if (
            forced_locus
            and self.forced_surface_diagnostic
            and self.persistent_forced_locus is None
        ):
            self.forced_surface_action = None
            self.forced_surface_target_file = None
            self.forced_surface_diagnostic = False
        context = self.problem_runtime.build_hypothesis_context(
            branch=branch,
            champion=champ_snapshot,
            active_hypotheses=self.hypothesis_store.get_by_status("active"),
            blacklist=self.hypothesis_store.get_by_status("blacklisted"),
            rejected_hypotheses=self.hypothesis_store.get_by_status("rejected"),
            sibling_branches=siblings,
            step_history=self.step_history,
            branch_workspace=branch_workspace,
            failure_streak=dict(self.failure_streak),
            forced_locus=forced_locus,
            forced_action=forced_action,
            forced_target_file=forced_target_file,
            forced_surface_diagnostic=forced_diagnostic,
            search_memory=self.search_memory,
            saturation_signals=self._compute_saturation_signals(),
            weight_opt_result=self.get_latest_weight_opt_result(),
            research_log=self.research_log,
        )
        if self._agentic_enabled:
            return self._generate_agentic_hypothesis(
                branch=branch,
                champion=champ_snapshot,
                context=context,
            )
        try:
            hypothesis = self.creative.generate_hypothesis(context)
        except LLMBalanceError as exc:
            logger.critical(
                "Branch %s: API balance exhausted - stopping campaign: %s",
                bid,
                exc,
            )
            self.hypothesis_failure_details[bid] = str(exc)
            self.mark_balance_exhausted()
            self.circuit_breaker.record_failure(str(exc))
            return None, None
        except (
            LLMRetryExhaustedError,
            LLMFormatError,
            LLMTimeoutError,
            ProposalValidationError,
        ) as exc:
            if is_provider_balance_exhausted_detail(exc):
                logger.critical(
                    "Branch %s: API balance exhausted - stopping campaign: %s",
                    bid,
                    exc,
                )
                self.hypothesis_failure_details[bid] = str(exc)
                self.mark_balance_exhausted()
                self.circuit_breaker.record_failure(str(exc))
                return None, None
            logger.warning("Branch %s: hypothesis LLM error: %s", bid, exc)
            self.hypothesis_failure_details[bid] = str(exc)
            self.handle_failure(branch, FailureEvent(category="proposal", detail=str(exc)))
            self.circuit_breaker.record_failure(str(exc))
            return None, None

        forced_detail = self._forced_hypothesis_violation(
            hypothesis,
            forced_surface=forced_locus,
            forced_action=forced_action,
            forced_target_file=forced_target_file,
        )
        if forced_detail is not None:
            self.hypothesis_failure_details[bid] = forced_detail
            self.handle_failure(branch, FailureEvent(category="proposal", detail=forced_detail))
            self.circuit_breaker.record_failure(forced_detail)
            return None, None
        boundary_detail = self._active_problem_boundary_violation(
            hypothesis,
            active_problem_boundary_surfaces=(
                ()
                if forced_locus
                else _active_problem_boundary_surfaces_for_runtime(
                    self.problem_runtime,
                )
            ),
            forced_surface=forced_locus,
        )
        if boundary_detail is not None:
            self.hypothesis_failure_details[bid] = boundary_detail
            self.handle_failure(
                branch,
                FailureEvent(category="proposal", detail=boundary_detail),
            )
            self.circuit_breaker.record_failure(boundary_detail)
            return None, None

        self.circuit_breaker.record_success()
        return hypothesis, self._hypothesis_record(branch, hypothesis)

    def pop_hypothesis_failure_detail(self, branch_id: str) -> str | None:
        return self.hypothesis_failure_details.pop(branch_id, None)

    def generate_code(
        self,
        branch: Branch,
        hypothesis: HypothesisProposal,
        *,
        prior_failure: str | None = None,
    ) -> PatchProposal | None:
        bid = branch.branch_id
        if self._agentic_enabled:
            return self._generate_agentic_code(
                branch=branch,
                hypothesis=hypothesis,
                prior_failure=prior_failure,
            )
        context = self.problem_runtime.build_code_context(
            branch=branch,
            hypothesis=hypothesis,
            champion=self._champion_snapshot(),
            prior_failure=prior_failure,
            branch_workspace=self.branch_workspaces.get(branch.branch_id),
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
            self.hypothesis_failure_details[bid] = str(exc)
            self.mark_balance_exhausted()
            self.circuit_breaker.record_failure(str(exc))
            return None
        except (
            LLMRetryExhaustedError,
            LLMFormatError,
            LLMTimeoutError,
            ProposalValidationError,
        ) as exc:
            if is_provider_balance_exhausted_detail(exc):
                logger.critical(
                    "Branch %s: API balance exhausted - stopping campaign: %s",
                    bid,
                    exc,
                )
                self.hypothesis_failure_details[bid] = str(exc)
                self.mark_balance_exhausted()
                self.circuit_breaker.record_failure(str(exc))
                return None
            logger.warning("Branch %s: code LLM error: %s", bid, exc)
            self.hypothesis_failure_details[bid] = str(exc)
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
            if is_provider_balance_exhausted_detail(exc):
                logger.critical(
                    "Branch %s: API balance exhausted during fix - stopping campaign: %s",
                    branch.branch_id,
                    exc,
                )
                self.mark_balance_exhausted()
                self.circuit_breaker.record_failure(str(exc))
                return None
            logger.warning("Branch %s: fix LLM error: %s", branch.branch_id, exc)
            return None
