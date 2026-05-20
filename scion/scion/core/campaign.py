"""CampaignManager — main loop integrating all Scion modules (Phase 5)."""
from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from scion.config.problem import ProtocolConfig, ProblemSpec, SplitManifest, SeedLedgerConfig
from scion.core.campaign_adapters import (
    _branch_step_runner_for,
    _evaluation_orchestrator_for,
    _explore_step_pipeline_for,
    _lookup_decision_reason_codes,
    _workspace_service_for,
)
from scion.core.campaign_governance import CampaignGovernanceService
from scion.core.circuit_breaker import CircuitBreaker, MAX_CONSECUTIVE_LLM_FAILURES
from scion.core.explore_step_pipeline import build_verification_detail
from scion.core.features import BudgetState
from scion.core.failure_lifecycle import FailureLifecycleService
from scion.core.models import (
    Branch, CanaryResult, ChampionState, ContractResult,
    Decision, ExperimentStage, FailureEvent, HypothesisProposal, HypothesisRecord,
    PatchProposal, ProtocolResult, StepRecord, VerificationResult,
)
from scion.core.promotion_service import PromotionPlan
from scion.core.step_result import StepResult
from scion.core.termination import TerminationConfig
from scion.core.workspace_lifecycle import WorkspaceLifecycleService
from scion.failure.router import RetryConfig
from scion.proposal.saturation import ChampionSaturationAnalyzer
from scion.verification.gate import VerificationGate

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Campaign Manager
# ---------------------------------------------------------------------------

class CampaignManager:
    """Orchestrates the full 14-step Scion campaign loop.

    Dependencies:
        problem_spec       — static problem definition
        protocol_config    — gate thresholds (screening/validation/frozen)
        split_manifest     — case splits
        seed_ledger        — RNG seeds per stage
        llm_client         — LLMClient or MockLLMClient
        champion           — initial ChampionState
        campaign_dir       — root directory for workspaces/snapshots

    Optional overrides (useful for testing):
        verification_gate  — custom VerificationGate; otherwise built from
                             problem/runtime configuration
        experiment_protocol — custom ExperimentProtocol; defaults to None (no runner)
        budget             — BudgetState; defaults to max_rounds budget
        termination_config — TerminationConfig; defaults to library defaults
        retry_config       — RetryConfig; defaults to library defaults
    """

    def __init__(
        self,
        problem_spec: ProblemSpec,
        protocol_config: ProtocolConfig,
        split_manifest: SplitManifest,
        seed_ledger: SeedLedgerConfig,
        llm_client: Any,
        champion: ChampionState,
        campaign_dir: str,
        *,
        verification_gate: Optional[Any] = None,
        experiment_protocol: Optional[Any] = None,
        budget: Optional[BudgetState] = None,
        termination_config: Optional[TerminationConfig] = None,
        retry_config: Optional[RetryConfig] = None,
        adapter: Optional[Any] = None,
        operator_execute_signature: Optional[str] = None,
        objective_lower_bounds: Optional[Dict[str, float]] = None,
        use_objective_lower_bounds_for_early_stop: bool = False,
        force_continue_early_stop: bool = False,
        allow_non_strict_runtime_verification: bool = False,
        use_agentic_proposal: bool = False,
        agentic_artifact_dir: Optional[str] = None,
        agentic_session_timeout_sec: Optional[float] = None,
        force_surface: Optional[str] = None,
        force_action: Optional[str] = None,
        force_target_file: Optional[str] = None,
    ) -> None:
        from scion.core.campaign_composition import compose_campaign_services
        from scion.core.forced_surface import validate_forced_surface_request

        forced_request = None
        if force_surface is not None:
            forced_request = validate_forced_surface_request(
                problem_spec,
                force_surface,
                action=force_action,
                target_file=force_target_file,
                adapter_spec=getattr(adapter, "spec", None)
                or getattr(adapter, "_spec", None),
            )

        compose_campaign_services(
            self,
            problem_spec=problem_spec,
            protocol_config=protocol_config,
            split_manifest=split_manifest,
            seed_ledger=seed_ledger,
            llm_client=llm_client,
            champion=champion,
            campaign_dir=campaign_dir,
            verification_gate=verification_gate,
            experiment_protocol=experiment_protocol,
            budget=budget,
            termination_config=termination_config,
            retry_config=retry_config,
            adapter=adapter,
            operator_execute_signature=operator_execute_signature,
            objective_lower_bounds=objective_lower_bounds,
            use_objective_lower_bounds_for_early_stop=use_objective_lower_bounds_for_early_stop,
            force_continue_early_stop=force_continue_early_stop,
            allow_non_strict_runtime_verification=allow_non_strict_runtime_verification,
            use_agentic_proposal=use_agentic_proposal,
            agentic_artifact_dir=agentic_artifact_dir,
            agentic_session_timeout_sec=agentic_session_timeout_sec,
            force_surface=forced_request.surface if forced_request else None,
            force_action=forced_request.action if forced_request else None,
            force_target_file=forced_request.target_file if forced_request else None,
        )

    # ------------------------------------------------------------------
    # Backward-compat properties for attributes now owned by PlateauController.
    # External callers (tests, branch_store) still read these by name.
    # ------------------------------------------------------------------

    @property
    def _rounds_since_last_promote(self) -> int:
        return self._plateau.rounds_since_last_promote

    @_rounds_since_last_promote.setter
    def _rounds_since_last_promote(self, value: int) -> None:
        self._plateau._rounds_since_last_promote = value

    @property
    def _forced_next_locus(self) -> Optional[str]:
        return self._plateau.forced_next_locus

    @_forced_next_locus.setter
    def _forced_next_locus(self, value: Optional[str]) -> None:
        self._plateau._forced_next_locus = value

    # ------------------------------------------------------------------
    # Backward-compat properties for attributes now owned by
    # AsyncWeightOptCoordinator (v0.3 B2). Tests and lineage paths read
    # these by name.
    # ------------------------------------------------------------------

    @property
    def _pending_weight_opt_threads(self) -> List[threading.Thread]:
        return self._weight_opt_coord.pending_threads

    @property
    def _latest_weight_opt_result(self) -> Optional[Any]:
        return self._weight_opt_coord.latest_result

    @_latest_weight_opt_result.setter
    def _latest_weight_opt_result(self, value: Optional[Any]) -> None:
        self._weight_opt_coord.latest_result = value

    # ------------------------------------------------------------------
    # Backward-compat properties for attributes now owned by
    # ProblemRuntime (v0.3 B3). Tests and internal code read these by
    # name (e.g. ``cm._spec``, ``cm._ctx_manager``).
    # ------------------------------------------------------------------

    @property
    def _spec(self):
        return self._problem_runtime.spec

    @_spec.setter
    def _spec(self, value):
        self._problem_runtime._spec = value

    @property
    def _adapter(self):
        return self._problem_runtime.adapter

    @_adapter.setter
    def _adapter(self, value):
        self._problem_runtime._adapter = value

    @property
    def _ctx_manager(self):
        return self._problem_runtime.ctx_manager

    @_ctx_manager.setter
    def _ctx_manager(self, value):
        self._problem_runtime._ctx_manager = value

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def _record_step(self, step: StepRecord) -> None:
        """Record a completed step and update search memory (J1)."""
        self._evidence_recorder.record_step(
            step,
            self._step_history,
            search_memory=self._search_memory,
        )
        # J2: Lazily initialize baseline metrics from first champion-side data
        if self._baseline_metrics is None and step.protocol_result is not None:
            from scion.proposal.saturation import extract_champion_metrics_from_step
            _pf_len = len(step.protocol_result.pair_feedback) if step.protocol_result.pair_feedback else 0
            logger.info("[SATURATION DEBUG] R%d stage=%s pair_feedback_len=%d", step.round_num, step.protocol_result.stage, _pf_len)
            metrics = extract_champion_metrics_from_step(step)
            if metrics:
                logger.info("[SATURATION] Baseline initialized: metrics=%s", metrics)
                self._baseline_metrics = metrics
                self._saturation_analyzer = ChampionSaturationAnalyzer(
                    metrics,
                    lower_bounds=(
                        self._objective_lower_bounds
                        if self._use_objective_lower_bounds_for_early_stop
                        else None
                    ),
                )
            else:
                logger.info("[SATURATION DEBUG] extract returned None for stage=%s", step.protocol_result.stage)

    def run(self, max_rounds: int = 1000) -> None:
        """Run the campaign until a termination condition is met."""
        self._run_runtime_preflight()
        self._campaign_loop.run(max_rounds=max_rounds)

    def _run_runtime_preflight(self) -> None:
        """Validate problem-owned runtime dependencies before proposal work."""
        if getattr(self, "_runtime_preflight_checked", False):
            return
        from scion.problem.preflight import run_runtime_preflight

        run_runtime_preflight(self._spec, adapter=self._adapter)
        self._runtime_preflight_checked = True

    def run_one_step(self) -> StepResult:
        """Execute one campaign step and return a StepResult."""
        return _branch_step_runner_for(self).run_one_step()

    def should_stop(self) -> bool:
        return self._governance.should_stop()

    @staticmethod
    def _has_pending_evaluation(branches: List[Branch]) -> bool:
        """Compatibility wrapper for budget-efficiency early-stop guard."""
        return CampaignGovernanceService.has_pending_evaluation(branches)

    def get_state(self) -> Dict[str, Any]:
        branches = self._branch_ctrl.get_active_branches()
        state = {
            "campaign_id": self._campaign_id,
            "n_experiments": self._n_experiments,
            "screened_experiments": self._n_experiments,
            "telemetry_failed_experiments": getattr(
                self,
                "_telemetry_failed_experiments",
                0,
            ),
            "total_rounds": self._round_num,
            "proposal_attempts": self._round_num,
            "n_steps": len(self._step_history),
            "n_active_branches": len(branches),
            "champion_version": self._champion.version,
            "champion_weight_revision": getattr(self._champion, "weight_revision", 0),
            "budget_remaining": self._budget.remaining_ratio,
            "balance_exhausted": self._balance_exhausted,
            "circuit_breaker_tripped": self._circuit_breaker.is_tripped,
            "frozen_budget": self._frozen_budget_ledger.snapshot(),
            "branches": [
                {
                    "id": b.branch_id,
                    "state": b.state.value,
                    "base_champion_id": b.base_champion_id,
                    "weight_revision": getattr(b, "weight_revision", 0),
                }
                for b in branches
            ],
        }
        weight_opt_status = self._weight_opt_coord.status_snapshot()
        if (
            weight_opt_status["pending_threads"]
            or weight_opt_status["active"]
            or weight_opt_status["runs"]
        ):
            state["weight_optimization"] = weight_opt_status
        if self._current_status_progress is not None:
            state["current_progress"] = self._current_status_progress
        return state

    def _write_status(
        self,
        *,
        last_result: StepResult | None = None,
        stopped_reason: str | None = None,
    ) -> None:
        self._evidence_recorder.current_status_progress = self._current_status_progress
        self._evidence_recorder.last_status_result = self._last_status_result
        self._evidence_recorder.write_status(
            last_result=last_result,
            stopped_reason=stopped_reason,
        )
        self._last_status_result = self._evidence_recorder.last_status_result

    def _on_protocol_progress(self, **payload: Any) -> None:
        """Progress hook called by ExperimentProtocol during long stages."""
        self._evidence_recorder.current_status_progress = self._current_status_progress
        progress = self._evidence_recorder.record_protocol_progress(**payload)
        self._current_status_progress = progress
        self._last_status_result = self._evidence_recorder.last_status_result

    def _begin_status_progress(
        self,
        *,
        branch: Branch,
        stage: ExperimentStage,
        hypothesis: HypothesisProposal,
        expand: bool,
        expand_round: int,
    ) -> None:
        self._current_status_progress = {
            "branch_id": branch.branch_id,
            "stage": stage.value,
            "target_file": hypothesis.target_file,
            "hypothesis_action": hypothesis.action,
            "base_champion_id": branch.base_champion_id,
            "branch_weight_revision": getattr(branch, "weight_revision", 0),
            "champion_version": self._champion.version,
            "champion_weight_revision": getattr(self._champion, "weight_revision", 0),
            "expand": expand,
            "expand_round": expand_round,
            "step_started_at": datetime.now().isoformat(),
            "last_progress_at": datetime.now().isoformat(),
        }
        self._evidence_recorder.current_status_progress = self._current_status_progress
        self._write_status()

    def _end_status_progress(self) -> None:
        self._current_status_progress = None
        self._evidence_recorder.current_status_progress = None
        self._write_status()

    def _persist_branch_state(self, branch_id: str) -> None:
        try:
            self._branch_store.save(self._branch_ctrl.get_branch(branch_id))
        except Exception as exc:
            logger.debug("BranchStore.save(%s) failed: %s", branch_id, exc)

    def _persist_all_branch_states(self) -> None:
        for branch in list(self._branch_ctrl._branches.values()):
            try:
                self._branch_store.save(branch)
            except Exception as exc:
                logger.debug("BranchStore.save(%s) failed: %s", branch.branch_id, exc)

    def _terminalize_active_branches(self, reason_code: str) -> None:
        """Close residual active branches for budget-driven campaign closeout."""
        for branch in list(self._branch_ctrl.get_active_branches()):
            if reason_code not in branch.failure_codes:
                branch.failure_codes.append(reason_code)
            try:
                self._branch_ctrl.apply_decision(branch.branch_id, Decision.ABANDON)
            except Exception as exc:
                logger.debug(
                    "Branch %s: max-round terminalize skipped: %s",
                    branch.branch_id,
                    exc,
                )
        self._persist_all_branch_states()

    # ------------------------------------------------------------------
    # EXPLORE step (Round 1 + Round 2 + eval)
    # ------------------------------------------------------------------

    def _run_explore_step(self, branch: Branch) -> StepResult:
        """Full 14-step flow for an EXPLORE/EXPLORE_EXPAND branch."""
        return _explore_step_pipeline_for(self).run(branch)

    # ------------------------------------------------------------------
    # EVAL-ONLY step (re-use workspace from EXPLORE)
    # ------------------------------------------------------------------

    def _run_eval_step(self, branch: Branch) -> StepResult:
        """Evaluation-only step for VALIDATING / FROZEN_TESTING branches."""
        return _branch_step_runner_for(self).run_eval_step(branch)

    # ------------------------------------------------------------------
    # STALE reconciliation
    # ------------------------------------------------------------------

    def _run_reconcile_step(self, branch: Branch) -> StepResult:
        """Attempt to rebase a STALE branch on the new champion.

        T06: Full reconcile pipeline — Contract → Verification → re-screening.
        A stale branch may only resume EXPLORE (→ READY_VALIDATE) if the patch
        passes all three gates against the new champion.
        If the VerificationGate or ExperimentProtocol is missing (skeleton mode),
        the stale branch is abandoned rather than silently passing.
        """
        return _branch_step_runner_for(self).run_reconcile_step(branch)

    # ------------------------------------------------------------------
    # Round 1: generate hypothesis
    # ------------------------------------------------------------------

    def _round1_generate_hypothesis(
        self, branch: Branch
    ) -> Tuple[Optional[HypothesisProposal], Optional[HypothesisRecord]]:
        return self._proposal_pipeline.generate_hypothesis(branch)

    def _proposal_failure_detail_for(self, branch_id: str) -> Optional[str]:
        return self._proposal_pipeline.pop_hypothesis_failure_detail(branch_id)

    def _proposal_session_ref_for(self, branch_id: str) -> Optional[Dict[str, Any]]:
        return self._proposal_pipeline.pop_agentic_session_ref(branch_id)

    # ------------------------------------------------------------------
    # Round 2: generate code
    # ------------------------------------------------------------------

    def _round2_generate_code(
        self, branch: Branch, hypothesis: HypothesisProposal,
        prior_failure: Optional[str] = None,
    ) -> Optional[PatchProposal]:
        return self._proposal_pipeline.generate_code(
            branch,
            hypothesis,
            prior_failure=prior_failure,
        )

    # ------------------------------------------------------------------
    # Fix code (verification_light retry)
    # ------------------------------------------------------------------

    def _attempt_fix(
        self, branch: Branch, patch: PatchProposal, vresult: VerificationResult
    ) -> Optional[PatchProposal]:
        return self._proposal_pipeline.attempt_fix(branch, patch, vresult)

    # ------------------------------------------------------------------
    # Workspace setup
    # ------------------------------------------------------------------

    def _setup_workspace(self, branch: Branch, force_champion: bool = False) -> Optional[str]:
        return _workspace_service_for(self).setup_workspace(
            branch,
            force_champion=force_champion,
        )

    def _workspace_service(self) -> WorkspaceLifecycleService:
        return _workspace_service_for(self)

    # ------------------------------------------------------------------
    # Evaluate (canary + experiment)
    # ------------------------------------------------------------------

    def _evaluate(
        self,
        branch: Branch,
        workspace: str,
        hypothesis: HypothesisProposal,
    ) -> Tuple[Decision, Optional[ProtocolResult], CanaryResult]:
        return _evaluation_orchestrator_for(self).evaluate(
            branch,
            workspace,
            hypothesis,
        )

    def _apply_soft_abandon(
        self,
        bid: str,
        branch: Branch,
        h_record: Optional[HypothesisRecord],
    ) -> None:
        """T4 soft-abandon: discard branch without affecting hard-stagnation counter.

        This path is for wr<0.3 'no signal' results — the branch couldn't beat the
        champion but there was no framework failure. Does NOT increment
        _recent_abandoned_count (which tracks framework-level stagnation only).
        """
        _evaluation_orchestrator_for(self).apply_soft_abandon(bid, branch, h_record)

    def _record_hard_abandon(self, branch_id: str, reason: str) -> None:
        """Count a non-T4 branch abandonment once for hard-stagnation logic."""
        counted = getattr(self, "_hard_abandon_counted_branches", None)
        if counted is None:
            counted = set()
            self._hard_abandon_counted_branches = counted
        if branch_id in counted:
            return
        counted.add(branch_id)
        self._recent_abandoned_count += 1
        logger.debug(
            "Branch %s: hard abandon counted (%s); recent_abandoned_count=%d",
            branch_id, reason, self._recent_abandoned_count,
        )

    # ------------------------------------------------------------------
    # Pool/registry sync
    # ------------------------------------------------------------------

    def _sync_pool_registry(
        self,
        workspace: str,
        hypothesis: HypothesisProposal,
        patch: PatchProposal,
    ) -> None:
        """Rebuild and export registry.yaml in workspace via PoolManager."""
        _workspace_service_for(self).sync_pool_registry(workspace, hypothesis, patch)

    # ------------------------------------------------------------------
    # Lineage recording
    # ------------------------------------------------------------------

    def _record_step_lineage(
        self,
        branch: Branch,
        hypothesis: HypothesisProposal,
        patch: Optional[PatchProposal],
        contract_result: ContractResult,
        verification_result: VerificationResult,
        canary_result: CanaryResult,
        protocol_result: Optional[ProtocolResult],
        decision: Decision,
        hypothesis_id: str = "",
        decision_reason_codes: Optional[tuple] = None,
        event_id: Optional[str] = None,
    ) -> None:
        """Write one experiment_event + one decision row to the registry."""
        self._evidence_recorder.record_step_lineage(
            branch=branch,
            hypothesis=hypothesis,
            patch=patch,
            contract_result=contract_result,
            verification_result=verification_result,
            canary_result=canary_result,
            protocol_result=protocol_result,
            decision=decision,
            champion=self._champion,
            hypothesis_id=hypothesis_id,
            decision_reason_codes=decision_reason_codes,
            event_id=event_id,
        )

    def _decision_reason_codes_for(
        self,
        branch_id: str,
        protocol_result: Optional[ProtocolResult],
    ) -> Optional[Tuple[str, ...]]:
        return _lookup_decision_reason_codes(self, branch_id, protocol_result)

    def _increment_round(self) -> int:
        self._round_num += 1
        return self._round_num

    def _increment_rounds_since_last_promote(self) -> None:
        self._rounds_since_last_promote += 1

    # ------------------------------------------------------------------
    # Apply decision and finalise
    # ------------------------------------------------------------------

    def _apply_decision_and_finalize(
        self,
        branch: Branch,
        decision: Decision,
        hypothesis: HypothesisProposal,
        h_record: HypothesisRecord,
        protocol_result: Optional[ProtocolResult],
        canary_result: CanaryResult,
        contract_result: ContractResult,
        verification_result: VerificationResult,
        action_label: str,
        decision_reason_codes: Optional[Tuple[str, ...]] = None,
    ) -> StepResult:
        return self._decision_finalizer.apply(
            branch=branch,
            decision=decision,
            hypothesis=hypothesis,
            h_record=h_record,
            protocol_result=protocol_result,
            canary_result=canary_result,
            contract_result=contract_result,
            verification_result=verification_result,
            action_label=action_label,
            decision_reason_codes=decision_reason_codes,
        )

    # ------------------------------------------------------------------
    # Promote
    # ------------------------------------------------------------------

    def _on_promote(self, branch: Branch) -> None:
        """Update champion immediately (pre-optimized weights) and launch bg weight opt.

        Compatibility helper for tests and old callers. The branch must already
        be in the normal frozen promotion state; this method does not provide a
        second semantic promotion path.
        """
        self._promotion_lifecycle.on_promote(branch)

    def _prepare_promoted_champion(self, branch: Branch) -> PromotionPlan:
        """Build and freeze the champion snapshot before any promote state commit."""
        return self._promotion_lifecycle.prepare_promoted_champion(branch)

    def _require_promotable_branch(self, branch: Branch) -> None:
        self._promotion_lifecycle.require_promotable_branch(branch)

    def _commit_promote_plan(self, plan: PromotionPlan) -> None:
        """Commit an already prepared champion snapshot and launch follow-up work."""
        self._promotion_lifecycle.commit_promote_plan(plan)

    def _transition_promoted_branch(self, branch_id: str, new_champion: ChampionState) -> None:
        """Transition the promoted branch after champion persistence succeeds."""
        self._promotion_lifecycle.transition_promoted_branch(branch_id, new_champion)

    def _begin_promotion_commit(self, plan: PromotionPlan) -> None:
        """Reset campaign-level stagnation counters for a new champion cycle."""
        self._promotion_lifecycle.begin_promotion_commit(plan)

    def _reset_promotion_counters(self, branch_id: str) -> None:
        """Reset campaign-level stagnation counters for a committed champion."""
        self._recent_abandoned_count = 0
        self._hard_abandon_counted_branches.clear()
        self._soft_abandon_streak = 0
        self._hard_stagnation_escape_used = False

    def _commit_promoted_champion_state(self, new_champion: ChampionState) -> None:
        """Install the promoted champion in campaign memory."""
        self._promotion_lifecycle.commit_promoted_champion_state(new_champion)

    def _record_promoted_branch(self, branch_id: str, new_champion: ChampionState) -> None:
        """Record promotion context in search memory."""
        self._promotion_lifecycle.record_promoted_branch(branch_id, new_champion)

    def _persist_promoted_champion(self, new_champion: ChampionState) -> None:
        """Persist the promoted champion before mutable promotion side effects."""
        self._promotion_lifecycle.persist_promoted_champion(new_champion)

    def _start_weight_optimization(self, plan: PromotionPlan) -> None:
        """Launch or run weight optimization for an already committed champion."""
        self._promotion_lifecycle.start_weight_optimization(plan)

    def _drain_weight_opt_events(self) -> None:
        """Apply completed weight-optimization events on the campaign thread."""
        self._promotion_lifecycle.drain_weight_opt_events()

    def _run_weight_optimization(
        self, champion_snapshot: str, version: int, current_weights: dict
    ):
        """Delegate to AsyncWeightOptCoordinator (v0.3 B2).

        Kept as a method on CampaignManager so existing tests that monkey-patch
        ``cm._run_weight_optimization`` continue to work — the coordinator's bg
        thread calls back through ``self._mgr._run_weight_optimization(...)``.
        """
        return self._weight_opt_coord.run_optimization(
            champion_snapshot, version, current_weights
        )

    # ------------------------------------------------------------------
    # Stagnation detection (T25/T23)
    # ------------------------------------------------------------------

    def _run_stagnation_check(self) -> None:
        """Check for stagnation signals after each round and log critical ones."""
        self._governance.run_stagnation_check()

    def _check_soft_stagnation(self) -> None:
        """If soft_abandon_streak hits limit, force the next branch to diversify locus.

        soft-stagnation means: champion is too strong in current locus, not that the
        framework is broken. Response = diversify search direction, NOT terminate.
        """
        self._governance.check_soft_stagnation()

    def _consume_forced_locus(self) -> Optional[str]:
        """Consume and return forced locus (set by soft/hard stagnation), or None."""
        return self._governance.consume_forced_locus()

    def _get_diversification_locus(self) -> Optional[str]:
        """Determine the best locus to diversify into, using StagnationDetector diagnosis."""
        return self._governance.get_diversification_locus()

    # ------------------------------------------------------------------
    # Failure handling
    # ------------------------------------------------------------------

    def _handle_failure(
        self,
        branch: Branch,
        failure: FailureEvent,
        hypothesis_already_recorded: bool = False,
    ) -> None:
        """Route failure and execute the appropriate recovery strategy."""
        lifecycle = getattr(self, "_failure_lifecycle", None)
        if lifecycle is None:
            lifecycle = FailureLifecycleService.from_owner(self)
        lifecycle.handle_failure(
            branch,
            failure,
            hypothesis_already_recorded=hypothesis_already_recorded,
        )

    def _tick_blocked_branches(self) -> None:
        """Increment blocked_rounds for every BLOCKED_INFRA branch; auto-unblock at 3 rounds."""
        lifecycle = getattr(self, "_failure_lifecycle", None)
        if lifecycle is None:
            lifecycle = FailureLifecycleService.from_owner(self)
        lifecycle.tick_blocked_branches()

    # ------------------------------------------------------------------
    # Workspace archiving
    # ------------------------------------------------------------------

    def _archive_failed_workspace(
        self, workspace: str, branch_id: str, round_num: int
    ) -> Optional[str]:
        """Archive operators/ from a failed workspace. Returns archive path or None."""
        tag = f"round_{round_num}_{branch_id[:8]}"
        try:
            return self._materializer.archive_workspace(workspace=workspace, branch_id=tag)
        except Exception as exc:
            logger.debug("Branch %s: archive_failed_workspace failed: %s", branch_id, exc)
            return None

    # ------------------------------------------------------------------
    # Campaign summary
    # ------------------------------------------------------------------

    def _write_campaign_summary(self) -> None:
        """Write campaign_summary.json with per-step detail."""
        self._evidence_recorder.write_campaign_summary(
            step_history=self._step_history,
            round_num=self._round_num,
            champion=self._champion,
            budget_used=self._budget.used,
            budget_total=self._budget.total,
            stopped_reason=self._last_stop_reason,
            balance_exhausted=self._balance_exhausted,
            circuit_breaker_tripped=self._circuit_breaker.is_tripped,
            stagnation_signals=self._stagnation_signals,
            diagnostics=self._diagnostics,
            frozen_budget=self._frozen_budget_ledger.snapshot(),
        )


def _build_verification_detail(vresult: VerificationResult) -> Optional[str]:
    """Compatibility wrapper for the extracted explore-step helper."""
    return build_verification_detail(vresult)
