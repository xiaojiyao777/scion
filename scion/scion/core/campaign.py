"""CampaignManager — main loop integrating all Scion modules (Phase 5)."""
from __future__ import annotations

import json
import logging
import threading
from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional, Tuple

from scion.config.problem import ProtocolConfig, ProblemSpec, SplitManifest, SeedLedgerConfig
from scion.core.campaign_adapters import (
    _branch_step_runner_for,
    _evaluation_orchestrator_for,
    _explore_step_pipeline_for,
    _lookup_decision_provenance,
    _lookup_decision_reason_codes,
    _workspace_service_for,
)
from scion.core.branch_cards import (
    branch_card_context,
    branch_prompt_card,
)
from scion.core.evaluation_orchestrator import EvaluationExecutionResult
from scion.core.execution_outcome import (
    branch_execution_hold,
    clear_branch_execution_hold,
)
from scion.core.failure_lifecycle import FailureLifecycleService
from scion.core.models import (
    Branch, CanaryResult, ChampionState, ContractResult,
    Decision, ExperimentStage, FailureEvent,
    HypothesisProposal, HypothesisRecord, PatchProposal, ProtocolResult,
    StepRecord, VerificationResult,
)
from scion.core.promotion_service import PromotionPlan
from scion.core.evidence_recording.accounting import proposal_accounting_fields
from scion.core.evidence_recording.common import reduced_measurement_readiness_payload
from scion.core.scheduler import (
    active_slot_inventory,
)
from scion.core.step_result import StepResult
from scion.core.workspace_lifecycle import WorkspaceLifecycleService
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Campaign Manager
# ---------------------------------------------------------------------------

class CampaignManager:
    """Orchestrate the direct V3 campaign path.

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
        adapter: Optional[Any] = None,
        operator_execute_signature: Optional[str] = None,
        allow_non_strict_runtime_verification: bool = False,
        allow_skeleton_mode: bool = False,
    ) -> None:
        from scion.core.campaign_composition import compose_campaign_services

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
            adapter=adapter,
            operator_execute_signature=operator_execute_signature,
            allow_non_strict_runtime_verification=allow_non_strict_runtime_verification,
            allow_skeleton_mode=allow_skeleton_mode,
        )

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
        """Append one durable step fact to the campaign history."""
        self._evidence_recorder.record_step(step, self._step_history)
        from scion.proposal.context_manager.manager import (
            persist_canonical_screening_record,
        )

        branch = self._branch_ctrl._branches.get(step.branch_id)
        if branch is not None and persist_canonical_screening_record(branch, step):
            self._persist_branch_state(step.branch_id)

    def _record_scheduler_result(self, result: StepResult) -> None:
        """Persist scheduler metadata after a branch step returns its result."""
        self._evidence_recorder.record_scheduler_result(result, self._step_history)

    def run(self, requested_rounds: int) -> None:
        """Run toward the operator-selected number of formal evaluated rounds."""
        try:
            self._run_research_environment_preflight()
            self._campaign_loop.run(requested_rounds=requested_rounds)
        except Exception as exc:
            reason = (
                "preflight_exception"
                if not getattr(self, "_research_preflight_checked", False)
                else "unhandled_exception"
            )
            self._finalize_unhandled_run_exception(
                reason=reason,
                exc=exc,
                requested_rounds=requested_rounds,
            )
            raise

    def request_stop(self, reason: str = "external_stop_requested") -> None:
        """Request graceful campaign stop before starting more work."""
        self._external_stop_requested = True
        self._last_stop_reason = reason or "external_stop_requested"
        self._write_status(stopped_reason=self._last_stop_reason)

    def finalize_requested_stop(self, reason: str | None = None) -> None:
        """Write final artifacts for an externally requested stop."""
        self._external_stop_requested = True
        if reason:
            self._last_stop_reason = reason
        elif not self._last_stop_reason:
            self._last_stop_reason = "external_stop_requested"
        coordinator = getattr(self, "_weight_opt_coord", None)
        if coordinator is not None:
            try:
                coordinator.wait_all(timeout=0.0)
            except Exception:
                logger.exception(
                    "Failed to shut down weight opt after requested stop"
                )
        self._persist_all_branch_states()
        self._write_campaign_summary()
        self._write_status(stopped_reason=self._last_stop_reason)

    def _finalize_unhandled_run_exception(
        self,
        *,
        reason: str,
        exc: Exception,
        requested_rounds: int,
    ) -> None:
        """Best-effort terminal campaign artifacts for unexpected run crashes."""
        self._last_stop_reason = reason
        self._external_stop_requested = True
        coordinator = getattr(self, "_weight_opt_coord", None)
        if coordinator is not None:
            try:
                coordinator.wait_all(timeout=0.0)
            except Exception:
                logger.exception("Failed to shut down weight opt after %s", reason)
        loop_status = self._crashed_campaign_loop_status(
            reason=reason,
            exc=exc,
            requested_rounds=requested_rounds,
        )
        try:
            self._write_status(
                stopped_reason=reason,
                loop_status=loop_status,
            )
            self._write_campaign_summary()
            self._write_status(
                stopped_reason=reason,
                loop_status=loop_status,
            )
        except Exception:
            logger.exception(
                "Failed to write terminal campaign artifacts after %s",
                reason,
            )

    def _crashed_campaign_loop_status(
        self,
        *,
        reason: str,
        exc: Exception,
        requested_rounds: int,
    ) -> Dict[str, Any]:
        existing = getattr(self._evidence_recorder, "campaign_loop_status", None)
        loop_status: Dict[str, Any] = (
            dict(existing) if isinstance(existing, dict) else {}
        )
        requested_rounds = _positive_int(
            loop_status.get("requested_rounds"),
            requested_rounds,
            default=1,
        )
        loop_steps = _nonnegative_int(
            loop_status.get("loop_steps", loop_status.get("campaign_steps")),
            default=len(getattr(self, "_step_history", ()) or ()),
        )
        effective_rounds = _nonnegative_int(
            loop_status.get("effective_rounds_completed"),
            default=0,
        )
        scheduled_calls = _nonnegative_int(
            loop_status.get("scheduled_calls"),
            default=loop_steps,
        )
        failure_categories = dict(loop_status.get("failure_categories") or {})
        failure_categories[reason] = _nonnegative_int(
            failure_categories.get(reason),
            default=0,
        ) + 1
        loop_status.update(
            {
                "requested_rounds": requested_rounds,
                "total_rounds": _nonnegative_int(
                    loop_status.get("total_rounds"),
                    default=getattr(self, "_round_num", 0),
                ),
                "scheduled_calls": scheduled_calls,
                "loop_steps": loop_steps,
                "campaign_steps": _nonnegative_int(
                    loop_status.get("campaign_steps"),
                    default=loop_steps,
                ),
                "effective_rounds_completed": effective_rounds,
                "failure_categories": failure_categories,
                "last_failure_category": reason,
                "terminal_exception": {
                    "reason": reason,
                    "type": type(exc).__name__,
                    "message": str(exc),
                },
            }
        )
        return loop_status

    def _run_research_environment_preflight(self) -> None:
        """Validate the complete problem environment once before proposal work."""
        if getattr(self, "_research_preflight_checked", False):
            return
        from scion.problem.preflight import run_research_environment_preflight

        run_research_environment_preflight(
            self._spec,
            adapter=self._adapter,
            verification_gate=self._vgate,
        )
        self._research_preflight_checked = True

    def run_one_step(self) -> StepResult:
        """Execute one campaign step and return a StepResult."""
        self._run_research_environment_preflight()
        return _branch_step_runner_for(self).run_one_step()

    def should_stop(self) -> bool:
        if getattr(self, "_external_stop_requested", False):
            if not self._last_stop_reason:
                self._last_stop_reason = "external_stop_requested"
            return True
        return False

    def get_state(self) -> Dict[str, Any]:
        branches = self._branch_ctrl.get_reportable_branches()
        max_active_branches = int(
            getattr(self._scheduler, "max_active_branches", 0) or 0
        )
        active_slots = active_slot_inventory(
            branches,
            max_active_branches=max_active_branches,
        )
        screened_experiments = sum(
            1
            for step in self._step_history
            if step.protocol_result is not None
            and step.protocol_result.stage == ExperimentStage.SCREENING
        )
        branch_rows = [_branch_state_row(b) for b in branches]
        branch_cards = [row["branch_card"] for row in branch_rows]
        try:
            from scion.core.evidence_recording.summary import _branch_history_cards

            branch_history_cards = _branch_history_cards(
                self._step_history,
                branch_cards,
            )
        except Exception as exc:  # pragma: no cover - status is best-effort
            logger.debug("branch history card projection failed: %s", exc)
            branch_history_cards = branch_cards
        protocol_config = getattr(self, "_protocol_config", None)
        measurement_readiness = reduced_measurement_readiness_payload(
            getattr(protocol_config, "measurement_readiness", None)
        )
        state = {
            "campaign_id": self._campaign_id,
            "proposal_runtime_mode": "direct_v3",
            "n_experiments": self._n_experiments,
            "screened_experiments": screened_experiments,
            "total_rounds": self._round_num,
            "n_steps": len(self._step_history),
            "n_active_branches": active_slots["used"],
            "active_slots": active_slots,
            "champion_version": self._champion.version,
            "champion_weight_revision": getattr(self._champion, "weight_revision", 0),
            "balance_exhausted": self._balance_exhausted,
            "branches": branch_rows,
            "branch_cards": branch_cards,
            "branch_history_cards": branch_history_cards,
        }
        if measurement_readiness is not None:
            state["measurement_readiness"] = measurement_readiness
        accounting = proposal_accounting_fields(
            campaign_dir=self._campaign_dir,
            steps=self._step_history,
            loop_status=getattr(
                self._evidence_recorder,
                "campaign_loop_status",
                None,
            ),
            state=state,
            round_num=self._round_num,
            screened_rounds=screened_experiments,
        )
        state.update(accounting)
        state["proposal_accounting"] = dict(accounting)
        weight_opt_status = self._weight_opt_coord.status_snapshot()
        if (
            weight_opt_status["pending_threads"]
            or weight_opt_status["active"]
            or weight_opt_status["runs"]
        ):
            state["weight_optimization"] = weight_opt_status
        if self._current_status_progress is not None:
            state["current_progress"] = _sync_branch_progress_from_rows(
                self._current_status_progress,
                branch_rows,
            )
        return state

    def get_state_snapshot(self) -> Dict[str, Any]:
        """Read-only state projection for evidence/status generation."""
        return self.get_state()

    def _write_status(
        self,
        *,
        last_result: StepResult | None = None,
        stopped_reason: str | None = None,
        loop_status: Dict[str, Any] | None = None,
    ) -> None:
        effective_stopped_reason = stopped_reason
        if effective_stopped_reason is None and self._last_stop_reason:
            effective_stopped_reason = self._last_stop_reason
        self._evidence_recorder.current_status_progress = self._current_status_progress
        self._evidence_recorder.last_status_result = self._last_status_result
        self._evidence_recorder.write_status(
            last_result=last_result,
            stopped_reason=effective_stopped_reason,
            loop_status=loop_status,
        )
        self._last_status_result = self._evidence_recorder.last_status_result
        self._current_status_progress = self._evidence_recorder.current_status_progress

    def _on_protocol_progress(self, **payload: Any) -> None:
        """Progress hook called by ExperimentProtocol during long stages."""
        self._evidence_recorder.current_status_progress = self._current_status_progress
        progress = self._evidence_recorder.record_protocol_progress(**payload)
        self._current_status_progress = progress
        self._last_status_result = self._evidence_recorder.last_status_result

    def _update_status_progress(self, payload: Dict[str, Any] | None) -> None:
        """Progress hook used by pre-protocol proposal and verification phases."""
        if payload is None:
            self._end_status_progress()
            return
        from scion.core.evidence_recording.artifact_refs import (
            _in_flight_protocol_snapshot,
        )

        progress = dict(self._current_status_progress or {})
        progress.update(payload)
        progress["last_progress_at"] = datetime.now().isoformat()
        self._current_status_progress = progress
        self._evidence_recorder.current_status_progress = progress
        self._evidence_recorder.in_flight_protocol = _in_flight_protocol_snapshot(
            progress
        )
        self._write_status()

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
            "phase": f"{stage.value}_protocol",
            "protocol_state": "running",
            "complete": False,
            "attempted_pairs": 0,
            "target_file": hypothesis.target_file,
            "hypothesis_action": hypothesis.action,
            "hypothesis_text": hypothesis.hypothesis_text,
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
        from scion.core.evidence_recording.artifact_refs import (
            _in_flight_protocol_snapshot,
        )

        self._evidence_recorder.in_flight_protocol = _in_flight_protocol_snapshot(
            self._current_status_progress
        )
        self._write_status()

    def _end_status_progress(self) -> None:
        preserve_in_flight = bool(getattr(self, "_external_stop_requested", False))
        self._current_status_progress = None
        self._evidence_recorder.current_status_progress = None
        if not preserve_in_flight:
            self._evidence_recorder.in_flight_protocol = None
        self._write_status()

    def _persist_branch_state(self, branch_id: str) -> None:
        self._branch_store.save(self._branch_ctrl.get_branch(branch_id))

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

    def _proposal_execution_outcome_for(self, branch_id: str) -> Any | None:
        return self._proposal_pipeline.pop_execution_outcome(branch_id)

    def _proposal_session_ref_for(self, branch_id: str) -> Optional[Dict[str, Any]]:
        return self._proposal_pipeline.pop_proposal_attempt_ref(branch_id)

    # ------------------------------------------------------------------
    # Round 2: generate code
    # ------------------------------------------------------------------

    def _round2_generate_code(
        self, branch: Branch, hypothesis: HypothesisProposal,
    ) -> Optional[PatchProposal]:
        return self._proposal_pipeline.generate_code(branch, hypothesis)

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
    ) -> EvaluationExecutionResult:
        return _evaluation_orchestrator_for(self).evaluate(
            branch,
            workspace,
            hypothesis,
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
        strict: bool = False,
    ) -> None:
        """Write one experiment_event + one decision row to the registry."""
        decision_features = None
        if protocol_result is not None and decision is not None:
            decision_features = getattr(self, "_decision_feature_snapshots", {}).get(
                branch.branch_id
            )
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
            decision_features=decision_features,
            event_id=event_id,
            strict=strict,
        )

    def _decision_reason_codes_for(
        self,
        branch_id: str,
        protocol_result: Optional[ProtocolResult],
    ) -> Optional[Tuple[str, ...]]:
        return _lookup_decision_reason_codes(self, branch_id, protocol_result)

    def _decision_provenance_for(self, branch_id: str) -> Dict[str, Any]:
        return _lookup_decision_provenance(self, branch_id)

    def _increment_round(self) -> int:
        self._round_num += 1
        return self._round_num

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
        proposal_attempt_ref: Mapping[str, Any] | None = None,
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
            proposal_attempt_ref=proposal_attempt_ref,
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



    def _commit_promoted_champion_state(self, new_champion: ChampionState) -> None:
        """Install the promoted champion in campaign memory."""
        self._promotion_lifecycle.commit_promoted_champion_state(new_champion)

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

    def operator_resume_infra(
        self,
        branch_id: str,
        *,
        operator_reason: str,
        operator_ack: str,
        failed_attempt_id: str | None = None,
    ) -> bool:
        """Resume one BLOCKED_INFRA branch through the sole operator API."""

        lifecycle = getattr(self, "_failure_lifecycle", None)
        if lifecycle is None:
            lifecycle = FailureLifecycleService.from_owner(self)
        return lifecycle.operator_resume_infra(
            branch_id,
            operator_reason=operator_reason,
            operator_ack=operator_ack,
            failed_attempt_id=failed_attempt_id,
        )

    def operator_resume_execution_hold(
        self,
        branch_id: str,
        *,
        operator_reason: str,
        operator_ack: str,
    ) -> bool:
        """Release a non-infra execution hold after a durable operator event."""

        reason = str(operator_reason or "").strip()
        ack = str(operator_ack or "").strip()
        if not reason or not ack:
            raise ValueError("operator_reason and operator_ack are required")
        branch = self._branch_ctrl.get_branch(branch_id)
        if branch is None:
            raise KeyError(f"unknown branch: {branch_id}")
        marker = branch_execution_hold(branch)
        if marker is None:
            raise ValueError(f"branch {branch_id} has no active execution hold")

        event_id = self._registry.record_event(
            {
                "campaign_id": self._campaign_id,
                "branch_id": branch_id,
                "event_kind": "operator_resume_execution_hold",
                "stage": "operator",
                "decision_reason": reason,
                "audit_payload_json": json.dumps(
                    {
                        "schema": "operator-resume-execution-hold.v1",
                        "operator_reason": reason,
                        "operator_ack": ack,
                        "released_execution_hold": marker,
                    },
                    sort_keys=True,
                ),
            }
        )
        clear_branch_execution_hold(branch)
        try:
            self._persist_branch_state(branch_id)
        except Exception:
            branch.branch_evidence_summary["execution_hold"] = marker
            raise
        logger.info(
            "Branch %s: operator released execution hold via event %s",
            branch_id,
            event_id,
        )
        return True

    # ------------------------------------------------------------------
    # Campaign summary
    # ------------------------------------------------------------------

    def _write_campaign_summary(self) -> None:
        """Write campaign_summary.json with per-step detail."""
        self._evidence_recorder.write_campaign_summary(
            step_history=self._step_history,
            round_num=self._round_num,
            champion=self._champion,
            stopped_reason=self._last_stop_reason,
            balance_exhausted=self._balance_exhausted,
            measurement_readiness=reduced_measurement_readiness_payload(
                getattr(
                    getattr(self, "_protocol_config", None),
                    "measurement_readiness",
                    None,
                )
            ),
            proposal_runtime_mode="direct_v3",
        )


def _nonnegative_int(*values: Any, default: int = 0) -> int:
    for value in values:
        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            continue
    return max(0, int(default))


def _positive_int(*values: Any, default: int = 1) -> int:
    for value in values:
        try:
            return max(1, int(value))
        except (TypeError, ValueError):
            continue
    return max(1, int(default))


def _branch_state_row(branch: Branch) -> Dict[str, Any]:
    card = dict(branch_card_context(branch))
    card["branch_card_text"] = branch_prompt_card(branch)
    return {
        "id": branch.branch_id,
        "state": branch.state.value,
        "base_champion_id": branch.base_champion_id,
        "weight_revision": getattr(branch, "weight_revision", 0),
        "branch_card": card,
        "branch_card_text": card["branch_card_text"],
    }


def _sync_branch_progress_from_rows(
    progress: Dict[str, Any],
    branch_rows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    branch_id = str(progress.get("branch_id") or "")
    merged = dict(progress)
    for row in branch_rows:
        if str(row.get("id") or "") != branch_id:
            continue
        card = dict(row.get("branch_card") or {})
        merged["branch_card"] = card
        for key in (
            "branch_state",
            "scheduling_status",
            "evidence_summary",
        ):
            if key in card:
                merged[key] = card[key]
        break
    return merged
