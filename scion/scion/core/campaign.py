"""CampaignManager — main loop integrating all Scion modules (Phase 5)."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from scion.config.problem import (
    ProblemSpec,
    ProtocolConfig,
    SeedLedgerConfig,
    SplitManifest,
)
from scion.core.branch import StateTransitionError
from scion.core.campaign_loop import CampaignRunResult
from scion.core.code_research_limits import CodeResearchLimits
from scion.core.evaluation_orchestrator import EvaluationExecutionResult
from scion.core.evidence_recording.common import reduced_measurement_readiness_payload
from scion.core.evidence_recording.status import project_last_result
from scion.core.execution_outcome import ExecutionOutcome, ExecutionOutcomeRecord
from scion.core.models import (
    Branch,
    BranchState,
    CanaryResult,
    ChampionState,
    ContractResult,
    Decision,
    ExperimentStage,
    HypothesisProposal,
    PatchProposal,
    ProtocolResult,
    StepRecord,
    VerificationResult,
)
from scion.core.promotion_service import PromotionResult
from scion.core.proposal_pipeline import ProposalAttempt
from scion.core.qualification import QualificationOnlyConfig, QualificationProgress
from scion.core.resource_envelope import ResourceEnvelope
from scion.core.scheduler import (
    active_slot_inventory,
)
from scion.core.step_result import StepResult
from scion.core.workspace_service import CandidateWorkspace

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
        experiment_protocol: Any,
        adapter: Any,
        verification_gate: Optional[Any] = None,
        operator_execute_signature: Optional[str] = None,
        research_input: Optional[Dict[str, Any]] = None,
        research_history: Sequence[Mapping[str, Any]] = (),
        resource_envelope: ResourceEnvelope | dict[str, Any] | None = None,
        code_research_limits: CodeResearchLimits | dict[str, Any] | None = None,
        qualification_only: (QualificationOnlyConfig | Mapping[str, Any] | None) = None,
        _initial_screening_study_controls: Any | None = None,
        _initial_screening_provider_policy: Any | None = None,
        _initial_screening_problem_spec: Any | None = None,
    ) -> None:
        from scion.core.campaign_composition import compose_campaign_services

        failed = False
        provider_policy_failed = False
        problem_spec_failed = False
        try:
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
                research_input=research_input,
                research_history=research_history,
                resource_envelope=resource_envelope,
                code_research_limits=code_research_limits,
                qualification_only=qualification_only,
                _initial_screening_study_controls=(_initial_screening_study_controls),
                _initial_screening_provider_policy=(_initial_screening_provider_policy),
                _initial_screening_problem_spec=(_initial_screening_problem_spec),
            )
        except Exception as error:
            from scion.core.initial_screening_study_provider_policy import (
                _InitialScreeningProviderPolicyError,
            )

            if _initial_screening_problem_spec is not None:
                from scion.core.initial_screening_problem_spec import (
                    _InitialScreeningProblemSpecError,
                )

                problem_spec_failed = type(error) is _InitialScreeningProblemSpecError
            provider_policy_failed = type(error) is _InitialScreeningProviderPolicyError
            if (
                _initial_screening_study_controls is None
                and _initial_screening_provider_policy is None
                and _initial_screening_problem_spec is None
                and not provider_policy_failed
                and not problem_spec_failed
            ):
                raise
            failed = True
        if failed:
            if problem_spec_failed or _initial_screening_problem_spec is not None:
                from scion.core.initial_screening_problem_spec import (
                    _ERROR,
                    _InitialScreeningProblemSpecError,
                )

                raise _InitialScreeningProblemSpecError(_ERROR)
            if provider_policy_failed or _initial_screening_provider_policy is not None:
                from scion.core.initial_screening_study_provider_policy import (
                    _ERROR,
                    _InitialScreeningProviderPolicyError,
                )

                raise _InitialScreeningProviderPolicyError(_ERROR)
            from scion.core.initial_screening_study_controls import (
                _ERROR,
                _InitialScreeningStudyControlsError,
            )

            raise _InitialScreeningStudyControlsError(_ERROR)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def _provide_experiment_protocol(self) -> Any:
        """Return the package-private protocol installed by composition."""

        return object.__getattribute__(self, "_experiment_protocol")

    def _record_step(self, step: StepRecord) -> None:
        """Append one durable step fact to the campaign history."""
        self._begin_async_stop_deferral()
        try:
            self._evidence_recorder.record_step(step, self._step_history)
        finally:
            self._end_async_stop_deferral()

    def _initial_screening_async_stop_deferral_enabled(self) -> bool:
        config = getattr(self, "_qualification_only_config", None)
        return bool(config is not None and config.initial_screening_only)

    def _begin_async_stop_deferral(self) -> None:
        """Defer an initial-only signal across one producer critical section."""

        if self._initial_screening_async_stop_deferral_enabled():
            self._async_stop_deferral_depth += 1

    def _end_async_stop_deferral(self) -> None:
        """Close one producer critical section without underflowing its latch."""

        if (
            self._initial_screening_async_stop_deferral_enabled()
            and self._async_stop_deferral_depth > 0
        ):
            self._async_stop_deferral_depth -= 1

    def _should_defer_async_stop_exception(self) -> bool:
        """Return whether a signal must wait for an initial-only safe boundary."""

        if not self._initial_screening_async_stop_deferral_enabled():
            return False
        loop = getattr(self, "_campaign_loop", None)
        current = getattr(loop, "current_result", None)
        if current is None:
            return False
        if self._async_stop_deferral_depth > 0:
            return True
        return len(self._step_history) > current.scheduled_calls

    def _async_stop_interrupted_hint(self, reason: str) -> bool | None:
        """Project whether an immediate CLI stop interrupted admitted work."""

        if not self._initial_screening_async_stop_deferral_enabled():
            return None
        loop = getattr(self, "_campaign_loop", None)
        if getattr(loop, "current_result", None) is None:
            return reason == "OUTER_HARDWALL_EXCEEDED"
        return bool(loop.call_in_progress)

    def _park_qualification_chain(self, branch_id: str) -> None:
        """Retire one failed chain without retaining an executable patch base."""

        branch = self._branch_ctrl.get_branch(branch_id)
        runtime = self._qualification_runtime
        if runtime is not None:
            runtime.validate_chain_retirement(branch_id)
        # Validate and make the branch unschedulable before touching the
        # carrier.  In particular, a READY_VALIDATE branch is a positive
        # qualification boundary and must survive an accidental park call.
        self._branch_ctrl.park_qualification_branch(branch_id)
        if runtime is not None:
            runtime.record_chain_retired(branch_id)
        try:
            self._workspace_service.discard_branch_workspace(branch_id)
        finally:
            # Workspace cleanup can fail after popping its mapping.  Authority
            # still has to be retired fail-closed so no later proposal can
            # inherit the failed candidate as a branch source.
            self._branch_workspaces.pop(branch_id, None)
            self._branch_patches.pop(branch_id, None)
            branch.current_code_hash = None
            branch.hypothesis = None
            branch.direction = None

    def _retire_initial_screening_study_chain(
        self,
        branch_id: str,
        decision: Decision,
    ) -> None:
        """Retire one initial-only candidate without downstream authority."""

        runtime = self._qualification_runtime
        if runtime is None:
            raise RuntimeError("initial screening retirement requires qualification")
        runtime.validate_initial_screening_retirement(branch_id)
        branch = self._branch_ctrl.get_branch(branch_id)
        self._branch_ctrl.park_initial_screening_study_branch(branch_id, decision)
        try:
            self._workspace_service.discard_branch_workspace(branch_id)
        finally:
            self._branch_workspaces.pop(branch_id, None)
            self._branch_patches.pop(branch_id, None)
            branch.current_code_hash = None
            branch.hypothesis = None
            branch.direction = None

    def _terminal_run_result(self, requested_rounds: int) -> CampaignRunResult:
        """Refresh in-flight qualification counters before terminalization."""

        current = self._campaign_loop.current_result or self._empty_run_result(
            requested_rounds
        )
        runtime = getattr(self, "_qualification_runtime", None)
        if runtime is not None:
            current = replace(current, qualification=runtime.progress())
        return current

    def _empty_run_result(self, requested_rounds: int) -> CampaignRunResult:
        runtime = getattr(self, "_qualification_runtime", None)
        config = getattr(self, "_qualification_only_config", None)
        qualification = (
            runtime.progress()
            if runtime is not None
            else QualificationProgress(config=config)
            if config is not None
            else None
        )
        return CampaignRunResult.empty(
            requested_rounds,
            qualification=qualification,
        )

    def run(self, requested_rounds: int):
        """Run toward the operator-selected number of formal evaluated rounds."""
        from scion.core.initial_screening_study_controls_validation import (
            _validate_initial_screening_requested_rounds,
        )

        _validate_initial_screening_requested_rounds(requested_rounds, self)
        self._requested_rounds = max(1, int(requested_rounds))
        try:
            self._run_research_environment_preflight()
            return self._campaign_loop.run(requested_rounds=self._requested_rounds)
        except Exception as exc:
            self._seal_proposal_runtime("unresolved")
            reason = (
                "preflight_exception"
                if not getattr(self, "_research_preflight_checked", False)
                else "unhandled_exception"
            )
            current = self._terminal_run_result(self._requested_rounds)
            terminal = current.terminalized(
                reason=reason,
                exception=exc,
                unresolved_attempt=self._campaign_loop.call_in_progress,
            )
            self._campaign_loop.current_result = terminal
            self._campaign_loop.call_in_progress = False
            self._finalize_unhandled_run_exception(run_result=terminal)
            raise

    def request_stop(self, reason: str = "external_stop_requested") -> None:
        """Request graceful campaign stop before starting more work."""
        self._external_stop_requested = True
        self._last_stop_reason = reason or "external_stop_requested"

    def finalize_requested_stop(
        self,
        reason: str | None = None,
        *,
        interrupted_override: bool | None = None,
    ) -> None:
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
                logger.exception("Failed to shut down weight opt after requested stop")
        current = self._terminal_run_result(getattr(self, "_requested_rounds", 1))
        interrupted = (
            self._campaign_loop.call_in_progress
            if interrupted_override is None
            else interrupted_override
        )
        terminal = current.terminalized(
            self._last_stop_reason,
            interrupted=interrupted,
        )
        self._seal_proposal_runtime("interrupted" if interrupted else "unresolved")
        self._campaign_loop.current_result = terminal
        self._campaign_loop.call_in_progress = False
        self._write_terminal_artifacts(terminal)

    def _finalize_unhandled_run_exception(
        self,
        *,
        run_result: CampaignRunResult,
    ) -> None:
        """Best-effort terminal campaign artifacts for unexpected run crashes."""
        self._last_stop_reason = run_result.stop_reason
        self._external_stop_requested = True
        coordinator = getattr(self, "_weight_opt_coord", None)
        if coordinator is not None:
            try:
                coordinator.wait_all(timeout=0.0)
            except Exception:
                logger.exception(
                    "Failed to shut down weight opt after %s",
                    run_result.stop_reason,
                )
        self._write_terminal_artifacts(run_result)

    def _run_research_environment_preflight(self) -> None:
        """Validate the complete problem environment once before proposal work."""
        if getattr(self, "_research_preflight_checked", False):
            return
        from scion.problem.preflight import run_research_environment_preflight

        run_research_environment_preflight(
            self._problem_runtime.spec,
            adapter=self._problem_runtime.adapter,
            verification_gate=self._vgate,
        )
        self._research_preflight_checked = True

    def run_one_step(self) -> StepResult:
        """Execute one campaign step and return a StepResult."""
        if self._qualification_only_config is not None:
            return StepResult(
                action="stopped",
                stopped=True,
                reason="qualification-only mode requires CampaignManager.run",
                failure_stage="campaign",
                failure_detail="qualification direct step dispatch blocked",
                execution_outcome=ExecutionOutcomeRecord(
                    outcome=ExecutionOutcome.NOT_EVALUATED,
                    reason_code="QUALIFICATION_OUTER_LOOP_REQUIRED",
                    provenance={"stage": "campaign"},
                ),
            )
        self._run_research_environment_preflight()
        return self._run_scheduled_step()

    def _run_scheduled_step(self) -> StepResult:
        """Execute one step after the owning outer loop has established policy."""

        return self._branch_step_runner.run_one_step()

    def should_stop(self) -> bool:
        if getattr(self, "_external_stop_requested", False):
            if not self._last_stop_reason:
                self._last_stop_reason = "external_stop_requested"
            return True
        return False

    def get_state(
        self,
        *,
        run_result: CampaignRunResult | None = None,
    ) -> Dict[str, Any]:
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
        protocol_config = getattr(self, "_protocol_config", None)
        measurement_readiness = reduced_measurement_readiness_payload(
            getattr(protocol_config, "measurement_readiness", None)
        )
        bounded_research = self._code_research_limits is not None
        proposal_runtime_mode = "direct_v3"
        if bounded_research:
            proposal_runtime_mode = (
                "bounded_hypothesis_candidates_v1"
                if self._code_research_limits.max_hypothesis_candidates == 2
                else "bounded_research_v1"
            )
        state = {
            "campaign_id": self._campaign_id,
            "proposal_runtime_mode": proposal_runtime_mode,
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
        }
        if self._qualification_only_config is not None:
            state["campaign_mode"] = "qualification_only"
        if measurement_readiness is not None:
            state["measurement_readiness"] = measurement_readiness
        weight_opt_status = self._weight_opt_coord.status_snapshot()
        if (
            weight_opt_status["pending_threads"]
            or weight_opt_status["active"]
            or weight_opt_status["runs"]
        ):
            state["weight_optimization"] = weight_opt_status
        if self._current_status_progress is not None:
            current_progress = _sync_branch_progress_from_rows(
                self._current_status_progress,
                branch_rows,
            )
            state["current_progress"] = current_progress
        if self._last_status_result is not None:
            state["last_result"] = dict(self._last_status_result)
        current_run = run_result
        if current_run is None:
            current_run = getattr(
                getattr(self, "_campaign_loop", None),
                "current_result",
                None,
            )
        if current_run is None:
            current_run = self._empty_run_result(getattr(self, "_requested_rounds", 1))
        if bounded_research:
            provider_calls = self._provider_call_budget.snapshot()
            runtime = self._proposal_runtime_telemetry
            state["proposal_runtime"] = runtime.snapshot(
                provider_calls,
                terminal=bool(current_run.stop_reason),
            ).to_primitive()
        state["run_result"] = current_run.to_projection()
        return state

    def _seal_proposal_runtime(self, state: str) -> None:
        """Defensively close a bounded attempt at an outer terminal edge."""

        runtime = getattr(self, "_proposal_runtime_telemetry", None)
        if runtime is not None:
            runtime.seal_active(state)

    def _write_status(
        self,
        *,
        last_result: StepResult | None = None,
        run_result: CampaignRunResult | None = None,
    ) -> None:
        if last_result is not None:
            self._last_status_result = project_last_result(last_result)
        state = self.get_state(run_result=run_result)
        self._evidence_recorder.write_status(
            state=state,
            run_result=state["run_result"],
        )

    def _on_protocol_progress(self, **payload: Any) -> None:
        """Progress hook called by ExperimentProtocol during long stages."""
        progress = self._evidence_recorder.record_protocol_progress(
            current_progress=self._current_status_progress,
            **payload,
        )
        self._current_status_progress = progress
        self._write_status()

    def _update_status_progress(self, payload: Dict[str, Any] | None) -> None:
        """Progress hook used by pre-protocol proposal and verification phases."""
        if payload is None:
            self._end_status_progress()
            return
        progress = dict(self._current_status_progress or {})
        progress.update(payload)
        progress["last_progress_at"] = datetime.now().isoformat()
        self._current_status_progress = progress
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
        self._write_status()

    def _end_status_progress(self) -> None:
        self._current_status_progress = None
        self._write_status()

    # ------------------------------------------------------------------
    # EXPLORE step (Round 1 + Round 2 + eval)
    # ------------------------------------------------------------------

    def _run_explore_step(self, branch: Branch) -> StepResult:
        """Full 14-step flow for an EXPLORE/EXPLORE_EXPAND branch."""
        return self._explore_step_pipeline.run(branch)

    # ------------------------------------------------------------------
    # EVAL-ONLY step (re-use workspace from EXPLORE)
    # ------------------------------------------------------------------

    def _run_eval_step(self, branch: Branch) -> StepResult:
        """Evaluation-only step for VALIDATING / FROZEN_TESTING branches."""
        return self._branch_step_runner.run_eval_step(branch)

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
        return self._branch_step_runner.run_reconcile_step(branch)

    # ------------------------------------------------------------------
    # Round 1: generate hypothesis
    # ------------------------------------------------------------------

    def _round1_generate_hypothesis(
        self, branch: Branch
    ) -> ProposalAttempt[HypothesisProposal]:
        return self._proposal_pipeline.generate_hypothesis(branch)

    # ------------------------------------------------------------------
    # Round 2: generate code
    # ------------------------------------------------------------------

    def _round2_generate_code(
        self,
        branch: Branch,
        hypothesis: HypothesisProposal,
    ) -> ProposalAttempt[PatchProposal]:
        return self._proposal_pipeline.generate_code(
            branch,
            hypothesis,
        )

    # ------------------------------------------------------------------
    # Workspace setup
    # ------------------------------------------------------------------

    def _setup_workspace(self, branch: Branch) -> Optional[str]:
        return self._workspace_service.setup_workspace(branch)

    # ------------------------------------------------------------------
    # Evaluate (canary + experiment)
    # ------------------------------------------------------------------

    def _evaluate(
        self,
        branch: Branch,
        workspace: str,
        hypothesis: HypothesisProposal,
        **stage_values: Any,
    ) -> EvaluationExecutionResult:
        if self._qualification_only_config is not None:
            effective_state = stage_values.get("branch_state") or branch.state
            allowed_states = {
                BranchState.EXPLORE,
                BranchState.EXPLORE_EXPAND,
            }
            if (
                branch.state not in allowed_states
                or effective_state not in allowed_states
            ):
                raise RuntimeError(
                    "qualification-only mode blocks validation/frozen evaluation"
                )
        return self._evaluation_orchestrator.evaluate(
            branch,
            workspace,
            hypothesis,
            **stage_values,
        )

    # ------------------------------------------------------------------
    # Lineage recording
    # ------------------------------------------------------------------

    def _record_step_lineage(
        self,
        branch: Branch,
        code_hash: str,
        hypothesis: HypothesisProposal,
        patch: Optional[PatchProposal],
        contract_result: Optional[ContractResult],
        verification_result: Optional[VerificationResult],
        canary_result: CanaryResult,
        protocol_result: Optional[ProtocolResult],
        decision: Decision,
        decision_reason_codes: Optional[tuple] = None,
        event_id: Optional[str] = None,
        strict: bool = False,
    ) -> None:
        """Write one experiment_event + one decision row to the registry."""
        self._evidence_recorder.record_step_lineage(
            branch=branch,
            code_hash=code_hash,
            hypothesis=hypothesis,
            patch=patch,
            contract_result=contract_result,
            verification_result=verification_result,
            canary_result=canary_result,
            protocol_result=protocol_result,
            decision=decision,
            champion=self._champion,
            decision_reason_codes=decision_reason_codes,
            event_id=event_id,
            strict=strict,
        )

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
        protocol_result: Optional[ProtocolResult],
        canary_result: CanaryResult,
        contract_result: Optional[ContractResult],
        verification_result: Optional[VerificationResult],
        action_label: str,
        decision_reason_codes: Optional[Tuple[str, ...]] = None,
        patch: Optional[PatchProposal] = None,
        candidate: CandidateWorkspace | None = None,
        reanchor_champion: ChampionState | None = None,
    ) -> StepResult:
        return self._decision_finalizer.apply(
            branch=branch,
            decision=decision,
            hypothesis=hypothesis,
            protocol_result=protocol_result,
            canary_result=canary_result,
            contract_result=contract_result,
            verification_result=verification_result,
            action_label=action_label,
            decision_reason_codes=decision_reason_codes,
            patch=patch,
            candidate=candidate,
            reanchor_champion=reanchor_champion,
        )

    # ------------------------------------------------------------------
    # Promote
    # ------------------------------------------------------------------

    def _promote_branch(self, branch: Branch) -> None:
        """Promote one accepted branch and launch optional weight search."""
        workspace = self._branch_workspaces.get(branch.branch_id)
        if workspace is None:
            raise FileNotFoundError(
                f"no workspace found for promoted branch {branch.branch_id}"
            )
        with self._champion_lock:
            champion = self._champion
        result = self._promotion_service.promote(
            branch_id=branch.branch_id,
            candidate_workspace=workspace,
            champion=champion,
        )
        logger.info(
            "Promoted branch %s to champion v%d; marked %d branches stale",
            branch.branch_id,
            result.champion.version,
            len(result.stale_branch_ids),
        )
        self._start_weight_optimization(result)

    def _require_promotable_branch(self, branch: Branch) -> None:
        current = self._branch_ctrl.get_branch(branch.branch_id)
        if current.state != BranchState.FROZEN_TESTING:
            raise StateTransitionError(
                f"promotion requires frozen branch state, got {current.state.value}"
            )

    def _transition_promoted_branch(
        self, branch_id: str, new_champion: ChampionState
    ) -> None:
        """Transition the promoted branch after champion persistence succeeds."""
        branch = self._branch_ctrl.get_branch(branch_id)
        if branch.state != BranchState.PROMOTED:
            self._branch_ctrl.apply_decision(branch_id, Decision.PROMOTE)
        branch.hypothesis = None

    def _set_promoted_champion(self, new_champion: ChampionState) -> None:
        """Install the promoted champion in campaign memory."""
        with self._champion_lock:
            self._champion = new_champion

    def _start_weight_optimization(self, result: PromotionResult) -> None:
        """Launch or run weight optimization for the promoted champion."""
        new_champion = result.champion
        weight_opt = self._weight_opt_coord
        try:
            if (
                getattr(
                    self._problem_runtime.spec.parameter_search,
                    "execution",
                    "async",
                )
                == "sync"
            ):
                logger.info(
                    "Champion v%d: running weight optimization synchronously",
                    new_champion.version,
                )
                weight_opt.run_for_promoted_champion_sync(
                    new_champion.code_snapshot_path,
                    new_champion.version,
                    dict(result.current_weights),
                    base_weight_revision=new_champion.weight_revision,
                )
                self._drain_weight_opt_events()
            else:
                weight_opt.spawn_for_promoted_champion(
                    new_champion.code_snapshot_path,
                    new_champion.version,
                    dict(result.current_weights),
                    base_weight_revision=new_champion.weight_revision,
                )
        except Exception as exc:
            logger.warning(
                "Failed to run weight optimization for champion v%d: %s",
                new_champion.version,
                exc,
            )

    def _drain_weight_opt_events(self) -> None:
        """Apply completed weight-optimization events on the campaign thread."""
        self._weight_opt_committer.drain()

    # ------------------------------------------------------------------
    # Campaign summary
    # ------------------------------------------------------------------

    def _write_campaign_summary(
        self,
        run_result: CampaignRunResult | None = None,
        *,
        state: Dict[str, Any] | None = None,
    ) -> None:
        """Write campaign_summary.json with per-step detail."""
        current_run = run_result
        if current_run is None:
            current_run = getattr(self._campaign_loop, "current_result", None)
        if current_run is None:
            current_run = self._empty_run_result(getattr(self, "_requested_rounds", 1))
        state_snapshot = state or self.get_state(run_result=current_run)
        self._evidence_recorder.write_campaign_summary(
            state=state_snapshot,
            run_result=state_snapshot["run_result"],
            step_history=self._step_history,
        )

    def _write_terminal_artifacts(self, run_result: CampaignRunResult) -> None:
        """Write status and summary from one terminal value and state snapshot."""

        self._seal_proposal_runtime("unresolved")
        state = self.get_state(run_result=run_result)
        projection = state["run_result"]
        try:
            self._evidence_recorder.write_status(
                state=state,
                run_result=projection,
            )
        except Exception:  # pragma: no cover - evidence is observational
            logger.exception("Failed to write terminal status")
        try:
            self._evidence_recorder.write_campaign_summary(
                state=state,
                run_result=projection,
                step_history=self._step_history,
            )
        except Exception:  # pragma: no cover - evidence is observational
            logger.exception("Failed to write terminal campaign summary")


def _branch_state_row(branch: Branch) -> Dict[str, Any]:
    return {
        "id": branch.branch_id,
        "state": branch.state.value,
        "base_champion_id": branch.base_champion_id,
        "current_code_hash": branch.current_code_hash,
        "weight_revision": getattr(branch, "weight_revision", 0),
        "direction": branch.direction,
        "failure_codes": list(branch.failure_codes or ()),
        "created_at": branch.created_at.isoformat(),
        "updated_at": branch.updated_at.isoformat(),
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
        merged["branch_state"] = row.get("state")
        break
    return merged
