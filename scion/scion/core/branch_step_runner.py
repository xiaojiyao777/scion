"""Branch-step execution boundary for CampaignManager."""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, MutableMapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from scion.core.branch import BranchController, StateTransitionError
from scion.core.evaluation_orchestrator import EvaluationExecutionResult
from scion.core.execution_outcome import (
    ExecutionOutcome,
    ExecutionOutcomeRecord,
    block_branch_after_execution,
    record_execution_outcome_event,
)
from scion.core.models import (
    Branch,
    BranchState,
    ChampionState,
    ContractResult,
    HypothesisProposal,
    PatchProposal,
    StepRecord,
    VerificationResult,
)
from scion.core.qualification import QualificationProposalBudgetExhausted
from scion.core.scheduler import (
    Scheduler,
    SchedulerAction,
)
from scion.core.step_result import StepResult
from scion.core.verification_call import run_verification_gate
from scion.core.workspace_service import CandidateWorkspace

logger = logging.getLogger(__name__)

_QUALIFICATION_HELDOUT_STATES = frozenset(
    {
        BranchState.READY_VALIDATE,
        BranchState.VALIDATING,
        BranchState.VALIDATING_EXPAND,
        BranchState.READY_FROZEN,
        BranchState.FROZEN_TESTING,
    }
)


@dataclass
class BranchStepRunner:
    """Own branch dispatch, eval-only execution, and stale reconciliation."""

    branch_controller: BranchController
    scheduler: Scheduler
    champion_lock: Any
    get_champion: Callable[[], ChampionState]
    branch_workspaces: MutableMapping[str, str]
    branch_patches: MutableMapping[str, PatchProposal]
    experiment_protocol_provider: Callable[[], Any]
    contract_gate: Any
    verification_gate: Any
    drain_weight_opt_events: Callable[[], None]
    should_stop: Callable[[], bool]
    get_last_stop_reason: Callable[[], str | None]
    setup_workspace: Callable[..., str | None]
    evaluate: Callable[
        [Branch, str, HypothesisProposal],
        EvaluationExecutionResult,
    ]
    apply_decision_and_finalize: Callable[..., StepResult]
    record_step: Callable[[StepRecord], None]
    run_explore_step: Callable[[Branch], StepResult]
    run_eval_step_callback: Callable[[Branch], StepResult]
    run_reconcile_step_callback: Callable[[Branch], StepResult]
    increment_round: Callable[[], int]
    registry: Any = None
    campaign_id: str = ""
    apply_reconcile_candidate: Callable[..., Any] | None = None
    verify_reconcile_candidate: (
        Callable[[CandidateWorkspace], CandidateWorkspace] | None
    ) = None
    reject_reconcile_candidate: Callable[[CandidateWorkspace], Any] | None = None
    qualification_only: bool = False
    qualification_runtime: Any = None
    discard_branch_workspace: Callable[[str], None] = lambda _branch_id: None

    def _select_next(self, active: list[Branch]) -> SchedulerAction:
        return self.scheduler.select_next(active)

    def run_one_step(self) -> StepResult:
        """Execute one campaign step and return a StepResult."""
        self.drain_weight_opt_events()
        if self.should_stop():
            return StepResult(
                action="stopped",
                stopped=True,
                reason=self.get_last_stop_reason() or "termination condition met",
                execution_outcome=ExecutionOutcomeRecord(
                    outcome=ExecutionOutcome.INTERRUPTED,
                    reason_code="EXTERNAL_STOP_REQUESTED",
                    provenance={"stage": "scheduler"},
                ),
            )

        active = self.branch_controller.get_active_branches()
        sched = self._select_next(active)

        if sched.action == "at_capacity":
            return StepResult(
                action="skip",
                reason="max_active_branches reached",
                execution_outcome=ExecutionOutcomeRecord(
                    outcome=ExecutionOutcome.NOT_EVALUATED,
                    reason_code="SCHEDULER_CAPACITY_BLOCKED",
                    provenance={"stage": "scheduler"},
                ),
            )

        pending_expansion_branch_id = (
            self.qualification_runtime.pending_expansion_branch_id
            if self.qualification_runtime is not None
            else None
        )
        if pending_expansion_branch_id is not None and sched.action != "run_existing":
            return StepResult(
                action="skip",
                branch_id=pending_expansion_branch_id,
                reason="qualification pending expansion dispatch mismatch",
                failure_stage="scheduler",
                failure_detail="qualification pending expansion dispatch blocked",
                execution_outcome=ExecutionOutcomeRecord(
                    outcome=ExecutionOutcome.NOT_EVALUATED,
                    reason_code="QUALIFICATION_PENDING_EXPANSION_MISMATCH",
                    provenance={"stage": "scheduler"},
                ),
            )

        if sched.action == "create_new":
            if (
                self.qualification_runtime is not None
                and not self.qualification_runtime.can_start_proposal()
            ):
                raise QualificationProposalBudgetExhausted(
                    "qualification-only proposal budget exhausted"
                )
            with self.champion_lock:
                champion = self.get_champion()
            branch = self.branch_controller.create_branch(champion)
            logger.info("Created new branch %s", branch.branch_id)
            result = self.run_explore_step(branch)
            result.action = "create_branch"
            return result

        branch = sched.branch
        assert branch is not None

        if pending_expansion_branch_id is not None and (
            branch.branch_id != pending_expansion_branch_id
            or branch.state is not BranchState.EXPLORE_EXPAND
        ):
            return StepResult(
                action="skip",
                branch_id=branch.branch_id,
                reason="qualification pending expansion dispatch mismatch",
                failure_stage="scheduler",
                failure_detail="qualification pending expansion dispatch blocked",
                execution_outcome=ExecutionOutcomeRecord(
                    outcome=ExecutionOutcome.NOT_EVALUATED,
                    reason_code="QUALIFICATION_PENDING_EXPANSION_MISMATCH",
                    provenance={"stage": "scheduler"},
                ),
            )

        if self.qualification_only and branch.state in _QUALIFICATION_HELDOUT_STATES:
            return StepResult(
                action="skip",
                branch_id=branch.branch_id,
                reason="qualification-only mode blocks heldout stage dispatch",
                failure_stage="scheduler",
                failure_detail="qualification heldout stage dispatch blocked",
                execution_outcome=ExecutionOutcomeRecord(
                    outcome=ExecutionOutcome.NOT_EVALUATED,
                    reason_code="QUALIFICATION_HELDOUT_DISPATCH_BLOCKED",
                    provenance={"stage": "scheduler"},
                ),
            )

        if (
            self.qualification_runtime is not None
            and branch.state is BranchState.EXPLORE_EXPAND
            and not self.qualification_runtime.authorize_expansion(branch.branch_id)
        ):
            return StepResult(
                action="skip",
                branch_id=branch.branch_id,
                reason="qualification expansion branch is not pending",
                failure_stage="scheduler",
                failure_detail="qualification expansion dispatch blocked",
                execution_outcome=ExecutionOutcomeRecord(
                    outcome=ExecutionOutcome.NOT_EVALUATED,
                    reason_code="QUALIFICATION_EXPANSION_DISPATCH_BLOCKED",
                    provenance={"stage": "scheduler"},
                ),
            )

        # EXPLORE branches share one research tier.  Advance service time before
        # H/C so rejected research returns to the back of the in-process queue.
        if branch.state == BranchState.EXPLORE:
            if self.qualification_runtime is not None:
                if (
                    branch.current_code_hash is not None
                    or branch.hypothesis is not None
                    or branch.branch_id in self.branch_patches
                    or branch.direction is not None
                ):
                    return StepResult(
                        action="skip",
                        branch_id=branch.branch_id,
                        reason="qualification proposal base is not clean B0",
                        failure_stage="scheduler",
                        failure_detail="qualification proposal base is not clean B0",
                        execution_outcome=ExecutionOutcomeRecord(
                            outcome=ExecutionOutcome.NOT_EVALUATED,
                            reason_code="QUALIFICATION_PROPOSAL_BASE_NOT_CLEAN",
                            provenance={"stage": "scheduler"},
                        ),
                    )
                if branch.branch_id in self.branch_workspaces:
                    try:
                        self.discard_branch_workspace(branch.branch_id)
                    except Exception:
                        self.branch_workspaces.pop(branch.branch_id, None)
                        return StepResult(
                            action="skip",
                            branch_id=branch.branch_id,
                            reason="qualification proposal base cleanup failed",
                            failure_stage="workspace",
                            failure_detail=(
                                "qualification proposal base cleanup failed"
                            ),
                            execution_outcome=ExecutionOutcomeRecord(
                                outcome=ExecutionOutcome.BLOCKED_INFRA,
                                reason_code=(
                                    "QUALIFICATION_PROPOSAL_BASE_CLEANUP_FAILED"
                                ),
                                provenance={"stage": "workspace"},
                            ),
                        )
                if branch.branch_id in self.branch_workspaces:
                    return StepResult(
                        action="skip",
                        branch_id=branch.branch_id,
                        reason="qualification proposal base is not clean B0",
                        failure_stage="scheduler",
                        failure_detail="qualification proposal base is not clean B0",
                        execution_outcome=ExecutionOutcomeRecord(
                            outcome=ExecutionOutcome.NOT_EVALUATED,
                            reason_code="QUALIFICATION_PROPOSAL_BASE_NOT_CLEAN",
                            provenance={"stage": "scheduler"},
                        ),
                    )
                if not self.qualification_runtime.can_start_proposal():
                    raise QualificationProposalBudgetExhausted(
                        "qualification-only proposal budget exhausted"
                    )
            branch.updated_at = datetime.now()  # noqa: DTZ005

        if branch.state in (BranchState.READY_VALIDATE, BranchState.READY_FROZEN):
            try:
                self.branch_controller.schedule_branch(branch.branch_id)
            except StateTransitionError as exc:
                logger.error("schedule_branch failed: %s", exc)
                return StepResult(
                    action="skip",
                    branch_id=branch.branch_id,
                    reason=str(exc),
                    execution_outcome=ExecutionOutcomeRecord(
                        outcome=ExecutionOutcome.NOT_EVALUATED,
                        reason_code="SCHEDULER_STATE_TRANSITION_REJECTED",
                        detail=str(exc),
                        provenance={"stage": "scheduler"},
                    ),
                )

        branch = self.branch_controller.get_branch(branch.branch_id)

        if branch.state in (BranchState.STALE, BranchState.STALE_WEIGHT_UPDATE):
            return self.run_reconcile_step_callback(branch)

        if branch.state == BranchState.EXPLORE:
            return self.run_explore_step(branch)

        if branch.state in (
            BranchState.EXPLORE_EXPAND,
            BranchState.VALIDATING,
            BranchState.VALIDATING_EXPAND,
            BranchState.FROZEN_TESTING,
        ):
            try:
                return self.run_eval_step_callback(branch)
            except RuntimeError as exc:
                return self._handle_eval_runtime_error(branch, exc)

        logger.warning(
            "Branch %s in unexpected state %s - skipping",
            branch.branch_id,
            branch.state.value,
        )
        return StepResult(
            action="skip",
            branch_id=branch.branch_id,
            reason=f"unhandled state {branch.state.value}",
            execution_outcome=ExecutionOutcomeRecord(
                outcome=ExecutionOutcome.NOT_EVALUATED,
                reason_code="SCHEDULER_STATE_UNHANDLED",
                provenance={"stage": "scheduler"},
            ),
        )

    def run_eval_step(self, branch: Branch) -> StepResult:
        """Evaluation-only step for validation/frozen branches."""
        bid = branch.branch_id
        logger.debug(
            "_run_eval_step start bid=%s state=%s workspaces=%s",
            bid,
            branch.state.value,
            list(self.branch_workspaces.keys()),
        )
        workspace = self.branch_workspaces.get(bid)
        if workspace is None:
            logger.warning("Branch %s: no workspace for eval step", bid)
            outcome = self._non_evaluated_outcome(
                branch,
                reason_code="EVAL_WORKSPACE_MISSING",
                detail="workspace not found",
            )
            self._record_execution_outcome(
                branch,
                outcome,
                event_kind="eval_metadata_outcome",
            )
            return StepResult(
                action=self._eval_action_label(branch),
                branch_id=bid,
                reason=outcome.detail,
                failure_stage="evaluation_metadata",
                failure_detail=outcome.detail,
                execution_outcome=outcome,
            )

        hypothesis = branch.hypothesis
        if hypothesis is None:
            logger.warning("Branch %s: no hypothesis for eval step", bid)
            outcome = self._non_evaluated_outcome(
                branch,
                reason_code="EVAL_HYPOTHESIS_MISSING",
                detail="hypothesis not found",
            )
            self._record_execution_outcome(
                branch,
                outcome,
                event_kind="eval_metadata_outcome",
            )
            return StepResult(
                action=self._eval_action_label(branch),
                branch_id=bid,
                reason=outcome.detail,
                failure_stage="evaluation_metadata",
                failure_detail=outcome.detail,
                execution_outcome=outcome,
            )

        patch = self.branch_patches.get(bid)
        action_label = self._eval_action_label(branch)

        if not branch.current_code_hash:
            detail = "accepted branch source is missing"
            outcome = self._non_evaluated_outcome(
                branch,
                reason_code="EVAL_ACCEPTED_SOURCE_MISSING",
                detail=detail,
            )
            self._record_execution_outcome(
                branch,
                outcome,
                event_kind="eval_metadata_outcome",
            )
            round_num = self.increment_round()
            self.record_step(
                StepRecord(
                    round_num=round_num,
                    branch_id=bid,
                    hypothesis=hypothesis,
                    patch=patch,
                    contract_passed=None,
                    verification_passed=None,
                    protocol_result=None,
                    decision=None,
                    failure_stage="evaluation_metadata",
                    failure_detail=detail,
                    execution_outcome=outcome,
                )
            )
            return StepResult(
                action=action_label,
                branch_id=bid,
                reason=detail,
                failure_stage="evaluation_metadata",
                failure_detail=detail,
                execution_outcome=outcome,
            )

        contract_result = None
        verification_result = None

        evaluation = self.evaluate(
            branch,
            workspace,
            hypothesis,
        )
        if not isinstance(evaluation, EvaluationExecutionResult):
            raise TypeError("evaluate callback must return EvaluationExecutionResult")
        decision = evaluation.decision
        protocol_result = evaluation.protocol_result
        canary_result = evaluation.canary_result
        execution_outcome = evaluation.execution_outcome

        round_num = self.increment_round()
        if execution_outcome.outcome is not ExecutionOutcome.EVALUATED:
            self._record_execution_outcome(
                branch,
                execution_outcome,
                event_kind="branch_eval_outcome",
            )
            non_evaluation_failure_stage = "evaluation"
            non_evaluation_failure_detail = (
                execution_outcome.detail or execution_outcome.reason_code
            )
            result = StepResult(
                action=action_label,
                branch_id=bid,
                reason=non_evaluation_failure_detail,
                failure_stage=non_evaluation_failure_stage,
                failure_detail=non_evaluation_failure_detail,
                canary_result=canary_result,
                execution_outcome=execution_outcome,
            )
            provenance = _evaluation_reason_provenance(evaluation)
            _attach_decision_provenance(result, provenance)
            self.record_step(
                StepRecord(
                    round_num=round_num,
                    branch_id=bid,
                    hypothesis=hypothesis,
                    patch=patch,
                    contract_passed=None,
                    verification_passed=None,
                    protocol_result=None,
                    decision=None,
                    failure_stage=non_evaluation_failure_stage,
                    failure_detail=non_evaluation_failure_detail,
                    decision_reason_codes=None,
                    **provenance,
                    canary_result=canary_result,
                    execution_outcome=execution_outcome,
                )
            )
            return result
        if decision is None:
            raise ValueError("evaluated result missing Decision")
        result = self.apply_decision_and_finalize(
            branch=branch,
            decision=decision,
            hypothesis=hypothesis,
            protocol_result=protocol_result,
            canary_result=canary_result,
            contract_result=contract_result,
            verification_result=verification_result,
            action_label=action_label,
            decision_reason_codes=evaluation.decision_reason_codes,
        )
        if result.execution_outcome is None:
            result.protocol_result = protocol_result
            result.canary_result = canary_result
            result.execution_outcome = execution_outcome
        failure_stage, failure_detail = (
            (result.failure_stage, result.failure_detail)
            if result.execution_outcome.outcome is not ExecutionOutcome.EVALUATED
            else _eval_failure_detail(
                result.protocol_result,
                canary_result=result.canary_result,
            )
        )
        provenance = _evaluation_reason_provenance(evaluation)
        _attach_decision_provenance(result, provenance)
        self.record_step(
            StepRecord(
                round_num=round_num,
                branch_id=bid,
                hypothesis=hypothesis,
                patch=patch,
                contract_passed=None,
                verification_passed=None,
                protocol_result=result.protocol_result,
                decision=result.decision,
                failure_stage=failure_stage,
                failure_detail=failure_detail,
                decision_reason_codes=(
                    evaluation.decision_reason_codes
                    if result.decision is not None
                    else None
                ),
                **provenance,
                canary_result=result.canary_result,
                execution_outcome=result.execution_outcome,
            )
        )
        return result

    def run_reconcile_step(self, branch: Branch) -> StepResult:
        """Attempt to rebase a stale branch on the new champion."""
        bid = branch.branch_id
        patch = self.branch_patches.get(bid)
        hypothesis = branch.hypothesis

        def cleanup() -> None:
            branch.hypothesis = None

        def close_stale() -> None:
            cleanup()
            self.branch_controller.reconcile_stale(
                bid,
                success=False,
                new_champion=self.get_champion(),
            )

        def abandon_stale(
            reason: str,
        ) -> StepResult:
            close_stale()
            outcome = ExecutionOutcomeRecord(
                outcome=ExecutionOutcome.RESEARCH_REJECTED,
                reason_code="RECONCILE_BRANCH_ABANDONED",
                detail=reason,
                provenance={"stage": "reconcile"},
            )
            record_execution_outcome_event(
                registry=self.registry,
                campaign_id=self.campaign_id,
                branch_id=bid,
                record=outcome,
                event_kind="reconcile_research_rejection",
            )
            return StepResult(
                action="reconcile",
                branch_id=bid,
                reason=reason,
                execution_outcome=outcome,
            )

        def preserve_stale(
            *,
            reason_code: str,
            detail: str,
        ) -> StepResult:
            outcome = self._non_evaluated_outcome(
                branch,
                reason_code=reason_code,
                detail=detail,
            )
            self._record_execution_outcome(
                branch,
                outcome,
                event_kind="reconcile_not_evaluated_outcome",
            )
            return StepResult(
                action="reconcile",
                branch_id=bid,
                reason=detail,
                failure_stage="evaluation_metadata",
                failure_detail=detail,
                execution_outcome=outcome,
            )

        if patch is None:
            logger.info(
                "Branch %s: no patch to reconcile - abandoning stale branch", bid
            )
            close_stale()
            return StepResult(
                action="reconcile",
                branch_id=bid,
                reason="no patch to reconcile",
            )

        if hypothesis is None:
            logger.info(
                "Branch %s: missing hypothesis metadata for reconcile",
                bid,
            )
            return preserve_stale(
                reason_code="RECONCILE_HYPOTHESIS_METADATA_MISSING",
                detail="missing hypothesis metadata for reconcile",
            )
        contract_result = self.contract_gate.validate_patch(
            patch,
            approved_hypothesis=hypothesis,
        )
        if not contract_result.passed:
            logger.info(
                "Branch %s: reconcile patch failed contract gate: %s",
                bid,
                contract_result.failure_reason,
            )
            reason = f"reconcile contract failed: {contract_result.failure_reason}"
            close_stale()
            outcome = _contract_rejection_outcome(contract_result, patch)
            checks = outcome.provenance.get("contract_checks", [])
            record_execution_outcome_event(
                registry=self.registry,
                campaign_id=self.campaign_id,
                branch_id=bid,
                record=outcome,
                event_kind="contract_fail",
            )
            round_num = self.increment_round()
            self.record_step(
                StepRecord(
                    round_num=round_num,
                    branch_id=bid,
                    hypothesis=hypothesis,
                    patch=patch,
                    contract_passed=False,
                    verification_passed=False,
                    protocol_result=None,
                    decision=None,
                    failure_stage="patch_contract",
                    failure_detail=contract_result.failure_reason,
                    contract_diagnostics=tuple(checks),
                    execution_outcome=outcome,
                )
            )
            return StepResult(
                action="reconcile",
                branch_id=bid,
                reason=reason,
                failure_stage="patch_contract",
                failure_detail=contract_result.failure_reason,
                failure_category=ExecutionOutcome.RESEARCH_REJECTED.value,
                execution_outcome=outcome,
            )

        if self.experiment_protocol_provider() is None:
            logger.info(
                "Branch %s: no experiment protocol for reconcile re-screening",
                bid,
            )
            return preserve_stale(
                reason_code="RECONCILE_PROTOCOL_MISSING",
                detail="no experiment protocol for re-screening",
            )

        candidate_callbacks = (
            self.apply_reconcile_candidate,
            self.verify_reconcile_candidate,
            self.reject_reconcile_candidate,
        )
        if any(callback is None for callback in candidate_callbacks):
            return preserve_stale(
                reason_code="RECONCILE_WORKSPACE_UNAVAILABLE",
                detail="reconcile workspace service unavailable",
            )

        with self.champion_lock:
            champion = self.get_champion()
        champion_workspace = champion.code_snapshot_path
        # Reconcile is evaluated from an isolated candidate copy of the current
        # champion.  The accepted branch workspace remains untouched until a
        # subsequent Decision accepts the candidate.
        base_workspace = champion_workspace
        candidate: CandidateWorkspace | None = None

        def reject_staging() -> None:
            nonlocal candidate
            if candidate is not None:
                assert self.reject_reconcile_candidate is not None
                self.reject_reconcile_candidate(candidate)
                candidate = None

        try:
            assert self.apply_reconcile_candidate is not None
            candidate = self.apply_reconcile_candidate(
                base_workspace,
                patch,
                hypothesis=hypothesis,
                sync_registry=True,
            )
        except Exception as exc:
            logger.info("Branch %s: reconcile apply_patch failed: %s", bid, exc)
            return abandon_stale(f"apply_patch failed: {exc}")

        workspace = candidate.workspace

        try:
            verification_result = run_verification_gate(
                self.verification_gate,
                workspace,
                champion_workspace,
                patch,
                hypothesis=hypothesis,
            )
        except BaseException:
            reject_staging()
            raise
        if not verification_result.passed:
            logger.info(
                "Branch %s: reconcile verification failed: %s",
                bid,
                verification_result.first_failure,
            )
            reject_staging()
            reason = (
                f"reconcile verification failed: {verification_result.first_failure}"
            )
            close_stale()
            outcome = _verification_rejection_outcome(verification_result, patch)
            record_execution_outcome_event(
                registry=self.registry,
                campaign_id=self.campaign_id,
                branch_id=bid,
                record=outcome,
                event_kind="verification_fail",
            )
            round_num = self.increment_round()
            self.record_step(
                StepRecord(
                    round_num=round_num,
                    branch_id=bid,
                    hypothesis=hypothesis,
                    patch=patch,
                    contract_passed=True,
                    verification_passed=False,
                    protocol_result=None,
                    decision=None,
                    failure_stage="verification",
                    failure_detail=verification_result.first_failure,
                    execution_outcome=outcome,
                )
            )
            return StepResult(
                action="reconcile",
                branch_id=bid,
                reason=reason,
                failure_stage="verification",
                failure_detail=verification_result.first_failure,
                failure_category=ExecutionOutcome.RESEARCH_REJECTED.value,
                execution_outcome=outcome,
            )

        with self.champion_lock:
            current_champion = self.get_champion()
            if not _same_champion_revision(champion, current_champion):
                reject_staging()
                return preserve_stale(
                    reason_code="RECONCILE_CHAMPION_DRIFTED",
                    detail="champion changed during reconcile verification",
                )

        try:
            assert self.verify_reconcile_candidate is not None
            candidate = self.verify_reconcile_candidate(candidate)
        except Exception as exc:
            reject_staging()
            return preserve_stale(
                reason_code="RECONCILE_CANDIDATE_VERIFICATION_FAILED",
                detail=str(exc),
            )
        workspace = candidate.workspace

        round_num = self.increment_round()
        try:
            evaluation = self.evaluate(
                branch,
                workspace,
                hypothesis,
                branch_state=BranchState.EXPLORE,
                screening_expand_count=0,
                validation_expand_count=0,
            )
        except BaseException:
            reject_staging()
            raise
        if not isinstance(evaluation, EvaluationExecutionResult):
            reject_staging()
            raise TypeError("evaluate callback must return EvaluationExecutionResult")
        decision = evaluation.decision
        protocol_result = evaluation.protocol_result
        canary_result = evaluation.canary_result
        execution_outcome = evaluation.execution_outcome
        if execution_outcome.outcome is not ExecutionOutcome.EVALUATED:
            reject_staging()
            self._record_execution_outcome(
                branch,
                execution_outcome,
                event_kind="reconcile_evaluation_outcome",
            )
            result = StepResult(
                action="reconcile",
                branch_id=bid,
                reason=execution_outcome.detail or execution_outcome.reason_code,
                failure_stage="evaluation",
                failure_detail=(
                    execution_outcome.detail or execution_outcome.reason_code
                ),
                canary_result=canary_result,
                execution_outcome=execution_outcome,
            )
            provenance = _evaluation_reason_provenance(evaluation)
            _attach_decision_provenance(result, provenance)
            self.record_step(
                StepRecord(
                    round_num=round_num,
                    branch_id=bid,
                    hypothesis=hypothesis,
                    patch=self.branch_patches.get(bid, patch),
                    contract_passed=True,
                    verification_passed=True,
                    protocol_result=None,
                    decision=None,
                    failure_stage="evaluation",
                    failure_detail=(
                        execution_outcome.detail or execution_outcome.reason_code
                    ),
                    decision_reason_codes=None,
                    **provenance,
                    canary_result=canary_result,
                    execution_outcome=execution_outcome,
                )
            )
            return result
        if decision is None:
            reject_staging()
            raise ValueError("evaluated result missing Decision")
        result = self.apply_decision_and_finalize(
            branch=branch,
            decision=decision,
            hypothesis=hypothesis,
            protocol_result=protocol_result,
            canary_result=canary_result,
            contract_result=contract_result,
            verification_result=verification_result,
            action_label="reconcile",
            decision_reason_codes=evaluation.decision_reason_codes,
            patch=patch,
            candidate=candidate,
            reanchor_champion=champion,
        )
        if result.execution_outcome is None:
            result.protocol_result = protocol_result
            result.canary_result = canary_result
            result.execution_outcome = execution_outcome
        failure_stage, failure_detail = (
            (result.failure_stage, result.failure_detail)
            if result.execution_outcome.outcome is not ExecutionOutcome.EVALUATED
            else _eval_failure_detail(
                result.protocol_result,
                canary_result=result.canary_result,
            )
        )
        provenance = _evaluation_reason_provenance(evaluation)
        _attach_decision_provenance(result, provenance)
        self.record_step(
            StepRecord(
                round_num=round_num,
                branch_id=bid,
                hypothesis=hypothesis,
                patch=self.branch_patches.get(bid, patch),
                contract_passed=True,
                verification_passed=True,
                protocol_result=result.protocol_result,
                decision=result.decision,
                failure_stage=failure_stage,
                failure_detail=failure_detail,
                decision_reason_codes=(
                    evaluation.decision_reason_codes
                    if result.decision is not None
                    else None
                ),
                **provenance,
                canary_result=result.canary_result,
                execution_outcome=result.execution_outcome,
            )
        )
        return result

    def _handle_eval_runtime_error(
        self,
        branch: Branch,
        exc: RuntimeError,
    ) -> StepResult:
        logger.error("Branch %s: eval step aborted - %s", branch.branch_id, exc)
        bid = branch.branch_id
        outcome = self._non_evaluated_outcome(
            branch,
            reason_code="EVAL_RUNTIME_ERROR",
            detail=str(exc),
        )
        self._record_execution_outcome(
            branch,
            outcome,
            event_kind="eval_runtime_outcome",
        )
        hypothesis = branch.hypothesis
        if hypothesis is not None:
            self.record_step(
                StepRecord(
                    round_num=self.increment_round(),
                    branch_id=bid,
                    hypothesis=hypothesis,
                    patch=self.branch_patches.get(bid),
                    contract_passed=True,
                    verification_passed=False,
                    protocol_result=None,
                    decision=None,
                    failure_stage="evaluation",
                    failure_detail=str(exc),
                    execution_outcome=outcome,
                )
            )
        return StepResult(
            action=self._eval_action_label(branch),
            branch_id=branch.branch_id,
            reason=str(exc),
            failure_stage="evaluation",
            failure_detail=str(exc),
            execution_outcome=outcome,
        )

    @staticmethod
    def _non_evaluated_outcome(
        branch: Branch,
        *,
        reason_code: str,
        detail: str,
        outcome: ExecutionOutcome = ExecutionOutcome.NOT_EVALUATED,
    ) -> ExecutionOutcomeRecord:
        return ExecutionOutcomeRecord(
            outcome=outcome,
            reason_code=reason_code,
            detail=detail,
            provenance={
                "stage": _execution_stage_for_branch(branch),
            },
        )

    def _record_execution_outcome(
        self,
        branch: Branch,
        record: ExecutionOutcomeRecord,
        *,
        event_kind: str,
    ) -> str | None:
        event_id = record_execution_outcome_event(
            registry=self.registry,
            campaign_id=self.campaign_id,
            branch_id=branch.branch_id,
            record=record,
            event_kind=event_kind,
        )
        if block_branch_after_execution(branch, record):
            logger.info(
                "Branch %s blocked after %s",
                branch.branch_id,
                record.reason_code,
            )
        return event_id

    @staticmethod
    def _eval_action_label(branch: Branch) -> str:
        if branch.state in (BranchState.EXPLORE, BranchState.EXPLORE_EXPAND):
            return "explore"
        if branch.state in (BranchState.VALIDATING, BranchState.VALIDATING_EXPAND):
            return "validate"
        return "frozen"


def _execution_stage_for_branch(branch: Branch) -> str:
    if branch.state in (BranchState.VALIDATING, BranchState.VALIDATING_EXPAND):
        return "validation"
    if branch.state == BranchState.FROZEN_TESTING:
        return "frozen"
    return "screening"


def _eval_failure_detail(
    protocol_result: Any | None,
    *,
    canary_result: Any | None = None,
) -> tuple[str | None, str | None]:
    if protocol_result is None:
        if canary_result is not None and not canary_result.passed:
            canary_reason_codes = tuple(canary_result.reason_codes or ())
            return (
                "canary",
                canary_reason_codes[0] if canary_reason_codes else "CANARY_FAILED",
            )
        return None, None
    reason_codes = {
        str(code).lower() for code in getattr(protocol_result, "reason_codes", ()) or ()
    }
    if "evaluation_failed" in reason_codes:
        detail = str(getattr(canary_result, "reason", "") or "evaluation failed")
        return "evaluation", detail
    return None, None


def _verification_rejection_outcome(
    vresult: VerificationResult,
    patch: PatchProposal,
) -> ExecutionOutcomeRecord:
    severity = vresult.failure_severity or "light"
    reason_code = (
        "VERIFICATION_LIGHT_REJECTED"
        if severity == "light"
        else "VERIFICATION_HEAVY_REJECTED"
    )
    checks = [
        {
            "name": check.name,
            "passed": check.passed,
            "severity": check.severity,
            "detail": check.detail,
            "elapsed_ms": check.elapsed_ms,
            "metadata": dict(check.metadata or {}),
        }
        for check in vresult.checks
    ]
    return ExecutionOutcomeRecord(
        outcome=ExecutionOutcome.RESEARCH_REJECTED,
        reason_code=reason_code,
        detail=vresult.first_failure or "",
        provenance={
            "stage": "verification",
            "severity": severity,
            "verification_checks": checks,
            "patch": {
                "action": patch.action,
                "files": [change.file_path for change in patch.iter_file_changes()],
            },
        },
    )


def _contract_rejection_outcome(
    result: ContractResult,
    patch: PatchProposal,
) -> ExecutionOutcomeRecord:
    checks = [
        {
            "name": check.name,
            "passed": check.passed,
            "severity": check.severity,
            "detail": check.detail,
            "elapsed_ms": check.elapsed_ms,
            "metadata": dict(check.metadata or {}),
        }
        for check in result.checks
    ]
    return ExecutionOutcomeRecord(
        outcome=ExecutionOutcome.RESEARCH_REJECTED,
        reason_code="PATCH_CONTRACT_REJECTED",
        detail=result.failure_reason or "",
        provenance={
            "stage": "patch_contract",
            "contract_checks": checks,
            "patch": {
                "action": patch.action,
                "files": [change.file_path for change in patch.iter_file_changes()],
            },
        },
    )


def _same_champion_revision(left: ChampionState, right: ChampionState) -> bool:
    return (
        left.version,
        left.weight_revision,
    ) == (
        right.version,
        right.weight_revision,
    )


def _attach_decision_provenance(
    result: StepResult,
    provenance: Mapping[str, Any],
) -> None:
    for key in (
        "decision_engine_reason_codes",
        "diagnostic_reason_codes",
        "bypass_reason_codes",
    ):
        if key in provenance:
            setattr(result, key, provenance[key])


def _evaluation_reason_provenance(
    evaluation: EvaluationExecutionResult,
) -> dict[str, tuple[str, ...]]:
    return {
        "decision_engine_reason_codes": evaluation.decision_engine_reason_codes,
        "diagnostic_reason_codes": evaluation.diagnostic_reason_codes,
        "bypass_reason_codes": evaluation.bypass_reason_codes,
    }
