"""Branch-step execution boundary for CampaignManager."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Mapping, MutableMapping, Optional

from scion.core.branch import BranchController, StateTransitionError
from scion.core.candidate_evaluation import (
    candidate_evaluation_kind,
    candidate_evaluation_pending,
    mark_candidate_evaluation_pending,
)
from scion.core.execution_outcome import (
    ExecutionOutcome,
    ExecutionOutcomeRecord,
    execution_outcome_projection_kwargs,
    install_branch_execution_hold,
    record_execution_outcome_event,
)
from scion.core.models import (
    Branch,
    BranchState,
    ChampionState,
    CheckResult,
    ContractResult,
    Decision,
    HypothesisProposal,
    HypothesisRecord,
    PatchProposal,
    StepRecord,
    VerificationResult,
)
from scion.core.evaluation_orchestrator import (
    EvaluationExecutionResult,
)
from scion.core.scheduler import (
    Scheduler,
    SchedulerAction,
    active_slot_capacity_block_metadata,
)
from scion.core.step_result import StepResult
from scion.core.telemetry_validation import screened_experiment_effective
from scion.core.verification_call import run_verification_gate

logger = logging.getLogger(__name__)


@dataclass
class BranchStepRunner:
    """Own branch dispatch, eval-only execution, and stale reconciliation."""

    branch_controller: BranchController
    scheduler: Scheduler
    champion_lock: Any
    get_champion: Callable[[], ChampionState]
    branch_store: Any
    branch_workspaces: MutableMapping[str, str]
    branch_hypotheses: MutableMapping[str, HypothesisProposal]
    branch_patches: MutableMapping[str, PatchProposal]
    branch_current_hypothesis: MutableMapping[str, HypothesisRecord]
    experiment_protocol_provider: Callable[[], Any]
    contract_gate: Any
    verification_gate: Any
    drain_weight_opt_events: Callable[[], None]
    should_stop: Callable[[], bool]
    get_last_stop_reason: Callable[[], Optional[str]]
    persist_branch_state: Callable[[str], None]
    setup_workspace: Callable[..., Optional[str]]
    apply_patch: Callable[..., Any]
    evaluate: Callable[
        [Branch, str, HypothesisProposal],
        EvaluationExecutionResult,
    ]
    apply_decision_and_finalize: Callable[..., StepResult]
    record_step: Callable[[StepRecord], None]
    decision_reason_codes_for: Callable[[str, Any], Optional[tuple[str, ...]]]
    run_explore_step: Callable[[Branch], StepResult]
    run_eval_step_callback: Callable[[Branch], StepResult]
    run_reconcile_step_callback: Callable[[Branch], StepResult]
    increment_round: Callable[[], int]
    hypothesis_store: Any
    record_scheduler_result: Optional[Callable[[StepResult], None]] = None
    decision_provenance_for: Callable[[str], dict[str, Any]] = lambda _branch_id: {}
    registry: Any = None
    campaign_id: str = ""
    apply_reconcile_candidate: Callable[..., Any] | None = None
    reject_reconcile_candidate: Callable[[Branch, str], Any] | None = None

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
                attempt_kind="other",
                execution_outcome=ExecutionOutcome.INTERRUPTED,
                execution_outcome_reason_code="EXTERNAL_STOP_REQUESTED",
            )

        active = self.branch_controller.get_active_branches()
        sched = self._select_next(active)

        def finalize(
            result: StepResult,
            *,
            capacity_block: dict[str, Any] | None = None,
        ) -> StepResult:
            return _finalize_scheduler_result(
                _attach_active_slot_audit(result, (), capacity_block=capacity_block),
                sched,
                self.record_scheduler_result,
            )

        if sched.action == "at_capacity":
            max_active_branches = _scheduler_max_active_branches(self.scheduler)
            capacity_block = (
                active_slot_capacity_block_metadata(
                    active,
                    max_active_branches=max_active_branches,
                )
                if max_active_branches is not None
                else None
            )
            return finalize(
                StepResult(
                    action="skip",
                    reason="max_active_branches reached",
                    attempt_kind="other",
                    execution_outcome=ExecutionOutcome.NOT_EVALUATED,
                    execution_outcome_reason_code="SCHEDULER_CAPACITY_BLOCKED",
                ),
                capacity_block=capacity_block,
            )

        if sched.action == "create_new":
            with self.champion_lock:
                champion = self.get_champion()
            branch = self.branch_controller.create_branch(champion)
            logger.info("Created new branch %s", branch.branch_id)
            try:
                self.branch_store.save(branch)
            except Exception as exc:
                logger.debug("BranchStore.save (create) failed: %s", exc)
            result = self.run_explore_step(branch)
            result.action = "create_branch"
            return finalize(result)

        branch = sched.branch
        assert branch is not None

        if branch.state in (BranchState.READY_VALIDATE, BranchState.READY_FROZEN):
            try:
                self.branch_controller.schedule_branch(branch.branch_id)
                self.persist_branch_state(branch.branch_id)
            except StateTransitionError as exc:
                logger.error("schedule_branch failed: %s", exc)
                return finalize(
                    StepResult(
                        action="skip",
                        branch_id=branch.branch_id,
                        reason=str(exc),
                        attempt_kind="other",
                        execution_outcome=ExecutionOutcome.NOT_EVALUATED,
                        execution_outcome_reason_code=(
                            "SCHEDULER_STATE_TRANSITION_REJECTED"
                        ),
                    )
                )

        branch = self.branch_controller.get_branch(branch.branch_id)

        if branch.state in (BranchState.STALE, BranchState.STALE_WEIGHT_UPDATE):
            return finalize(self.run_reconcile_step_callback(branch))

        if branch.state == BranchState.EXPLORE and candidate_evaluation_pending(branch):
            try:
                return finalize(self.run_eval_step_callback(branch))
            except RuntimeError as exc:
                return finalize(self._handle_eval_runtime_error(branch, exc))

        if branch.state == BranchState.EXPLORE:
            return finalize(self.run_explore_step(branch))

        if branch.state in (
            BranchState.EXPLORE_EXPAND,
            BranchState.VALIDATING,
            BranchState.VALIDATING_EXPAND,
            BranchState.FROZEN_TESTING,
        ):
            try:
                return finalize(self.run_eval_step_callback(branch))
            except RuntimeError as exc:
                return finalize(self._handle_eval_runtime_error(branch, exc))

        logger.warning(
            "Branch %s in unexpected state %s - skipping",
            branch.branch_id,
            branch.state.value,
        )
        return finalize(
            StepResult(
                action="skip",
                branch_id=branch.branch_id,
                reason=f"unhandled state {branch.state.value}",
                attempt_kind="other",
                execution_outcome=ExecutionOutcome.NOT_EVALUATED,
                execution_outcome_reason_code="SCHEDULER_STATE_UNHANDLED",
            )
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
                hypothesis_id=getattr(
                    self.branch_current_hypothesis.get(bid),
                    "hypothesis_id",
                    None,
                ),
                event_kind="eval_metadata_outcome",
            )
            return StepResult(
                action=self._eval_action_label(branch),
                branch_id=bid,
                reason=outcome.detail,
                attempt_kind="other",
                failure_stage="evaluation_metadata",
                failure_detail=outcome.detail,
                **execution_outcome_projection_kwargs(outcome),
            )

        hypothesis = self.branch_hypotheses.get(bid)
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
                hypothesis_id=getattr(
                    self.branch_current_hypothesis.get(bid),
                    "hypothesis_id",
                    None,
                ),
                event_kind="eval_metadata_outcome",
            )
            return StepResult(
                action=self._eval_action_label(branch),
                branch_id=bid,
                reason=outcome.detail,
                attempt_kind="other",
                failure_stage="evaluation_metadata",
                failure_detail=outcome.detail,
                **execution_outcome_projection_kwargs(outcome),
            )

        patch = self.branch_patches.get(bid)
        action_label = self._eval_action_label(branch)
        verification_result = _screening_verification_reuse_result(
            branch,
            action_label=action_label,
        )

        h_record = self.branch_current_hypothesis.get(bid)
        if h_record is None:
            outcome = self._non_evaluated_outcome(
                branch,
                reason_code="EVAL_HYPOTHESIS_RECORD_MISSING",
                detail=(
                    f"Branch {bid}: no canonical hypothesis record - "
                    "cannot proceed with eval"
                ),
            )
            self._record_execution_outcome(
                branch,
                outcome,
                hypothesis_id=None,
                event_kind="eval_metadata_outcome",
            )
            round_num = self.increment_round()
            self.record_step(
                StepRecord(
                    round_num=round_num,
                    branch_id=bid,
                    hypothesis=hypothesis,
                    patch=patch,
                    contract_passed=True,
                    verification_passed=verification_result.passed,
                    protocol_result=None,
                    decision=None,
                    failure_stage="evaluation_metadata",
                    failure_detail=outcome.detail,
                    attempt_kind="other",
                    **execution_outcome_projection_kwargs(outcome),
                )
            )
            return StepResult(
                action=action_label,
                branch_id=bid,
                reason=outcome.detail,
                attempt_kind="other",
                failure_stage="evaluation_metadata",
                failure_detail=outcome.detail,
                **execution_outcome_projection_kwargs(outcome),
            )

        contract_result = ContractResult(passed=True, checks=())
        if not verification_result.passed:
            logger.info(
                "Branch %s: eval verification reuse invariant failed: %s",
                bid,
                verification_result.first_failure,
            )
            outcome = self._non_evaluated_outcome(
                branch,
                reason_code="EVAL_VERIFICATION_REUSE_INVALID",
                detail=(
                    verification_result.first_failure or "verification reuse invalid"
                ),
            )
            self._record_execution_outcome(
                branch,
                outcome,
                hypothesis_id=h_record.hypothesis_id,
                event_kind="eval_verification_outcome",
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
                    verification_detail=_verification_result_detail(
                        verification_result
                    ),
                    hypothesis_id=h_record.hypothesis_id,
                    attempt_kind="other",
                    **execution_outcome_projection_kwargs(outcome),
                )
            )
            return StepResult(
                action=action_label,
                branch_id=bid,
                reason="verification reuse invalid",
                attempt_kind="other",
                failure_stage="verification",
                failure_detail=verification_result.first_failure,
                **execution_outcome_projection_kwargs(outcome),
            )

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
        self._record_execution_outcome(
            branch,
            execution_outcome,
            hypothesis_id=h_record.hypothesis_id,
            event_kind="branch_eval_outcome",
        )

        round_num = self.increment_round()
        if execution_outcome.outcome is not ExecutionOutcome.EVALUATED:
            non_evaluation_failure_stage = "evaluation"
            non_evaluation_failure_detail = (
                execution_outcome.detail or execution_outcome.reason_code
            )
            result = StepResult(
                action=action_label,
                branch_id=bid,
                reason=non_evaluation_failure_detail,
                attempt_kind="other",
                failure_stage=non_evaluation_failure_stage,
                failure_detail=non_evaluation_failure_detail,
                canary_result=canary_result,
                **execution_outcome_projection_kwargs(execution_outcome),
            )
            provenance = self.decision_provenance_for(bid)
            _attach_decision_provenance(result, provenance)
            self.record_step(
                StepRecord(
                    round_num=round_num,
                    branch_id=bid,
                    hypothesis=hypothesis,
                    patch=patch,
                    contract_passed=True,
                    verification_passed=True,
                    protocol_result=None,
                    decision=None,
                    failure_stage=non_evaluation_failure_stage,
                    failure_detail=non_evaluation_failure_detail,
                    verification_detail=_verification_result_detail(
                        verification_result
                    ),
                    hypothesis_id=h_record.hypothesis_id,
                    decision_reason_codes=None,
                    **provenance,
                    canary_result=canary_result,
                    attempt_kind="other",
                    **execution_outcome_projection_kwargs(execution_outcome),
                )
            )
            return result
        if decision is None:
            raise ValueError("evaluated result missing Decision")
        result = self.apply_decision_and_finalize(
            branch=branch,
            decision=decision,
            hypothesis=hypothesis,
            h_record=h_record,
            protocol_result=protocol_result,
            canary_result=canary_result,
            contract_result=contract_result,
            verification_result=verification_result,
            action_label=action_label,
        )
        _annotate_protocol_accounting(result, protocol_result)
        result.canary_result = canary_result
        for key, value in execution_outcome_projection_kwargs(
            execution_outcome
        ).items():
            setattr(result, key, value)
        failure_stage, failure_detail = _eval_failure_detail(
            protocol_result,
            canary_result=canary_result,
        )
        provenance = self.decision_provenance_for(bid)
        _attach_decision_provenance(result, provenance)
        self.record_step(
            StepRecord(
                round_num=round_num,
                branch_id=bid,
                hypothesis=hypothesis,
                patch=patch,
                contract_passed=True,
                verification_passed=True,
                protocol_result=protocol_result,
                decision=result.decision if decision is not None else None,
                failure_stage=failure_stage,
                failure_detail=failure_detail,
                verification_detail=_verification_result_detail(verification_result),
                hypothesis_id=h_record.hypothesis_id,
                decision_reason_codes=self.decision_reason_codes_for(
                    bid,
                    protocol_result,
                ),
                **provenance,
                canary_result=canary_result,
                attempt_kind=result.attempt_kind,
                repair_policy_reason=result.repair_policy_reason or None,
                repair_mechanism_ids=result.repair_mechanism_ids,
                **execution_outcome_projection_kwargs(execution_outcome),
            )
        )
        return result

    def run_reconcile_step(self, branch: Branch) -> StepResult:
        """Attempt to rebase a stale branch on the new champion."""
        bid = branch.branch_id
        patch = self.branch_patches.get(bid)
        h_record = self.branch_current_hypothesis.get(bid)

        def cleanup(hypothesis_status: str = "rejected") -> None:
            if h_record is not None:
                try:
                    self.hypothesis_store.mark_status(
                        h_record.hypothesis_id,
                        hypothesis_status,
                    )
                except Exception:
                    pass
                self.branch_current_hypothesis.pop(bid, None)

        def abandon_stale(
            reason: str,
            *,
            hypothesis_status: str = "rejected",
        ) -> StepResult:
            cleanup(hypothesis_status)
            self.branch_controller.reconcile_stale(
                bid,
                success=False,
                new_champion=self.get_champion(),
            )
            self.persist_branch_state(bid)
            return StepResult(
                action="reconcile",
                branch_id=bid,
                reason=reason,
                attempt_kind="reconcile_lifecycle",
                execution_outcome=ExecutionOutcome.RESEARCH_REJECTED,
                execution_outcome_reason_code="RECONCILE_BRANCH_ABANDONED",
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
                hypothesis_id=getattr(h_record, "hypothesis_id", None),
                event_kind="reconcile_not_evaluated_outcome",
            )
            return StepResult(
                action="reconcile",
                branch_id=bid,
                reason=detail,
                attempt_kind="reconcile_lifecycle",
                failure_stage="evaluation_metadata",
                failure_detail=detail,
                **execution_outcome_projection_kwargs(outcome),
            )

        if patch is None:
            logger.info(
                "Branch %s: no patch to reconcile - abandoning stale branch", bid
            )
            return abandon_stale("no patch to reconcile")

        hypothesis = self.branch_hypotheses.get(bid)
        if hypothesis is None or h_record is None:
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
            abandon_stale(reason, hypothesis_status="research_rejected")
            outcome = _contract_rejection_outcome(contract_result)
            checks = outcome.provenance.get("contract_checks", [])
            self.registry.record_contract_failure(
                campaign_id=self.campaign_id,
                branch_id=bid,
                hypothesis_id=h_record.hypothesis_id,
                hypothesis_text=hypothesis.hypothesis_text or "",
                change_locus=hypothesis.change_locus,
                action=patch.action,
                target_file=patch.file_path,
                failure_reason=contract_result.failure_reason or "",
                stage="patch_contract",
                reason_code="PATCH_CONTRACT_REJECTED",
                contract_checks=checks,
                provenance={"attempt_kind": "reconcile_lifecycle"},
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
                    hypothesis_id=h_record.hypothesis_id,
                    attempt_kind="reconcile_lifecycle",
                    **execution_outcome_projection_kwargs(outcome),
                )
            )
            return StepResult(
                action="reconcile",
                branch_id=bid,
                reason=reason,
                attempt_kind="reconcile_lifecycle",
                failure_stage="patch_contract",
                failure_detail=contract_result.failure_reason,
                failure_category=ExecutionOutcome.RESEARCH_REJECTED.value,
                **execution_outcome_projection_kwargs(outcome),
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

        transactional_callbacks = (
            self.apply_reconcile_candidate,
            self.reject_reconcile_candidate,
        )
        if any(callback is None for callback in transactional_callbacks):
            return preserve_stale(
                reason_code="RECONCILE_TRANSACTION_UNAVAILABLE",
                detail="transactional reconcile workspace service unavailable",
            )

        with self.champion_lock:
            champion = self.get_champion()
        champion_workspace = champion.code_snapshot_path
        # ``setup_workspace(force_champion=True)`` owns its own champion-lock
        # acquisition. Calling it while this non-reentrant lock is held would
        # deadlock the reconcile path.
        base_workspace = self.setup_workspace(branch, force_champion=True)
        if base_workspace is None:
            return preserve_stale(
                reason_code="RECONCILE_BASE_WORKSPACE_MISSING",
                detail="unable to materialize current champion base for reconcile",
            )
        previous_evidence_summary = dict(branch.branch_evidence_summary or {})
        workspace: str | None = None

        def reject_staging() -> None:
            nonlocal workspace
            if workspace is not None:
                assert self.reject_reconcile_candidate is not None
                self.reject_reconcile_candidate(branch, workspace)
                workspace = None
            branch.branch_evidence_summary = previous_evidence_summary

        try:
            assert self.apply_reconcile_candidate is not None
            applied = self.apply_reconcile_candidate(
                branch,
                base_workspace,
                patch,
                hypothesis=hypothesis,
                remember_patch=False,
                sync_registry=True,
            )
            workspace = applied.workspace
            code_hash = applied.code_hash
        except Exception as exc:
            logger.info("Branch %s: reconcile apply_patch failed: %s", bid, exc)
            return abandon_stale(f"apply_patch failed: {exc}")

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
            abandon_stale(reason, hypothesis_status="research_rejected")
            outcome = _verification_rejection_outcome(verification_result)
            record_execution_outcome_event(
                registry=self.registry,
                campaign_id=self.campaign_id,
                branch_id=bid,
                record=outcome,
                hypothesis_id=h_record.hypothesis_id,
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
                    verification_detail=_verification_result_detail(
                        verification_result
                    ),
                    hypothesis_id=h_record.hypothesis_id,
                    attempt_kind="reconcile_lifecycle",
                    **execution_outcome_projection_kwargs(outcome),
                )
            )
            return StepResult(
                action="reconcile",
                branch_id=bid,
                reason=reason,
                attempt_kind="reconcile_lifecycle",
                failure_stage="verification",
                failure_detail=verification_result.first_failure,
                failure_category=ExecutionOutcome.RESEARCH_REJECTED.value,
                **execution_outcome_projection_kwargs(outcome),
            )

        with self.champion_lock:
            current_champion = self.get_champion()
            if not _same_champion_identity(champion, current_champion):
                reject_staging()
                return preserve_stale(
                    reason_code="RECONCILE_CHAMPION_DRIFTED",
                    detail="champion changed during reconcile verification",
                )
            try:
                # Reconcile moves the branch's scientific base to the current
                # champion before evaluation, but its verified code remains
                # staging until the subsequent Protocol Decision accepts it.
                self.branch_controller.reconcile_stale(
                    bid,
                    success=True,
                    new_champion=champion,
                )
                mark_candidate_evaluation_pending(
                    branch,
                    hypothesis_id=h_record.hypothesis_id,
                    kind="reconcile",
                )
                self.persist_branch_state(bid)
            except BaseException:
                reject_staging()
                branch.branch_evidence_summary = previous_evidence_summary
                raise
        branch = self.branch_controller.get_branch(bid)
        if branch is None:
            return StepResult(
                action="reconcile",
                branch_id=bid,
                reason="branch disappeared after reconcile",
                attempt_kind="reconcile_lifecycle",
                execution_outcome=ExecutionOutcome.NOT_EVALUATED,
                execution_outcome_reason_code="RECONCILE_BRANCH_MISSING",
            )

        round_num = self.increment_round()
        setattr(branch, "reconcile_rescreening", True)
        try:
            evaluation = self.evaluate(
                branch,
                workspace,
                hypothesis,
            )
        finally:
            try:
                delattr(branch, "reconcile_rescreening")
            except AttributeError:
                pass
        if not isinstance(evaluation, EvaluationExecutionResult):
            raise TypeError("evaluate callback must return EvaluationExecutionResult")
        decision = evaluation.decision
        protocol_result = evaluation.protocol_result
        canary_result = evaluation.canary_result
        execution_outcome = evaluation.execution_outcome
        self._record_execution_outcome(
            branch,
            execution_outcome,
            hypothesis_id=h_record.hypothesis_id,
            event_kind="reconcile_evaluation_outcome",
        )
        if execution_outcome.outcome is not ExecutionOutcome.EVALUATED:
            result = StepResult(
                action="reconcile",
                branch_id=bid,
                reason=execution_outcome.detail or execution_outcome.reason_code,
                attempt_kind="reconcile_lifecycle",
                failure_stage="evaluation",
                failure_detail=(
                    execution_outcome.detail or execution_outcome.reason_code
                ),
                canary_result=canary_result,
                **execution_outcome_projection_kwargs(execution_outcome),
            )
            provenance = self.decision_provenance_for(bid)
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
                    hypothesis_id=h_record.hypothesis_id,
                    decision_reason_codes=None,
                    **provenance,
                    canary_result=canary_result,
                    attempt_kind="reconcile_lifecycle",
                    **execution_outcome_projection_kwargs(execution_outcome),
                )
            )
            return result
        if decision is None:
            raise ValueError("evaluated result missing Decision")
        result = self.apply_decision_and_finalize(
            branch=branch,
            decision=decision,
            hypothesis=hypothesis,
            h_record=h_record,
            protocol_result=protocol_result,
            canary_result=canary_result,
            contract_result=contract_result,
            verification_result=verification_result,
            action_label="reconcile",
        )
        _annotate_protocol_accounting(result, protocol_result)
        result.canary_result = canary_result
        for key, value in execution_outcome_projection_kwargs(
            execution_outcome
        ).items():
            setattr(result, key, value)
        failure_stage, failure_detail = _eval_failure_detail(
            protocol_result,
            canary_result=canary_result,
        )
        provenance = self.decision_provenance_for(bid)
        _attach_decision_provenance(result, provenance)
        self.record_step(
            StepRecord(
                round_num=round_num,
                branch_id=bid,
                hypothesis=hypothesis,
                patch=self.branch_patches.get(bid, patch),
                contract_passed=True,
                verification_passed=True,
                protocol_result=protocol_result,
                decision=result.decision if decision is not None else None,
                failure_stage=failure_stage,
                failure_detail=failure_detail,
                hypothesis_id=h_record.hypothesis_id,
                decision_reason_codes=self.decision_reason_codes_for(
                    bid,
                    protocol_result,
                ),
                **provenance,
                canary_result=canary_result,
                attempt_kind=result.attempt_kind,
                repair_policy_reason=result.repair_policy_reason or None,
                repair_mechanism_ids=result.repair_mechanism_ids,
                **execution_outcome_projection_kwargs(execution_outcome),
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
            hypothesis_id=getattr(
                self.branch_current_hypothesis.get(bid),
                "hypothesis_id",
                None,
            ),
            event_kind="eval_runtime_outcome",
        )
        hypothesis = self.branch_hypotheses.get(bid)
        if hypothesis is not None:
            h_record = self.branch_current_hypothesis.get(bid)
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
                    hypothesis_id=getattr(h_record, "hypothesis_id", None),
                    attempt_kind="other",
                    **execution_outcome_projection_kwargs(outcome),
                )
            )
        return StepResult(
            action=self._eval_action_label(branch),
            branch_id=branch.branch_id,
            reason=str(exc),
            attempt_kind="other",
            failure_stage="evaluation",
            failure_detail=str(exc),
            **execution_outcome_projection_kwargs(outcome),
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
                "owner": "branch_step_runner",
                "stage": _execution_stage_for_branch(branch),
            },
        )

    def _record_execution_outcome(
        self,
        branch: Branch,
        record: ExecutionOutcomeRecord,
        *,
        hypothesis_id: Optional[str],
        event_kind: str,
    ) -> Optional[str]:
        event_id = record_execution_outcome_event(
            registry=self.registry,
            campaign_id=self.campaign_id,
            branch_id=branch.branch_id,
            hypothesis_id=hypothesis_id,
            record=record,
            event_kind=event_kind,
        )
        if record.outcome is ExecutionOutcome.BLOCKED_INFRA:
            if branch.state is not BranchState.BLOCKED_INFRA:
                self.branch_controller.block_infra(branch.branch_id)
                self.persist_branch_state(branch.branch_id)
        elif install_branch_execution_hold(branch, record):
            self.persist_branch_state(branch.branch_id)
        return event_id

    @staticmethod
    def _eval_action_label(branch: Branch) -> str:
        if branch.state in (BranchState.EXPLORE, BranchState.EXPLORE_EXPAND):
            if candidate_evaluation_kind(branch) == "reconcile":
                return "reconcile"
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
        return None, None
    reason_codes = {
        str(code).lower() for code in getattr(protocol_result, "reason_codes", ()) or ()
    }
    if "evaluation_failed" in reason_codes:
        detail = str(getattr(canary_result, "reason", "") or "evaluation failed")
        return "evaluation", detail
    return None, None


def _annotate_protocol_accounting(
    result: StepResult,
    protocol_result: Any | None,
) -> None:
    if protocol_result is None:
        return
    stage_obj = getattr(protocol_result, "stage", "")
    stage = str(getattr(stage_obj, "value", stage_obj) or "")
    if stage not in {"screening", "validation", "frozen"}:
        return
    formal_evaluated = getattr(
        protocol_result, "stats", None
    ) is not None and screened_experiment_effective(protocol_result)
    result.protocol_stage = stage  # type: ignore[assignment]
    result.formal_protocol_evaluated = formal_evaluated
    result.screened_experiment_effective = stage == "screening" and formal_evaluated


def _screening_verification_reuse_result(
    branch: Branch,
    *,
    action_label: str,
) -> VerificationResult:
    current_hash = getattr(branch, "current_code_hash", None)
    last_clean_hash = getattr(branch, "last_clean_code_hash", None)
    code_status = str(getattr(branch, "branch_code_status", "clean") or "clean")
    code_hashes_present = bool(current_hash) and bool(last_clean_hash)
    code_hashes_equal = code_hashes_present and current_hash == last_clean_hash
    clean_status = code_status == "clean"
    reuse_allowed = code_hashes_equal and clean_status
    metadata: dict[str, Any] = {
        "verification_reused_from_screening": True,
        "verification_reuse_stage": action_label,
        "verification_reuse_source": "screening_or_reconcile",
        "current_code_hash": current_hash,
        "last_clean_code_hash": last_clean_hash,
        "branch_code_status": code_status,
        "code_hashes_present": code_hashes_present,
        "code_hashes_equal": code_hashes_equal,
        "clean_status": clean_status,
        "strict_checks_rerun": False,
    }
    if reuse_allowed:
        detail = (
            f"{action_label} reuses prior screening/reconcile verification; "
            "candidate code hashes are present and equal with clean status; "
            "V1-V8 were not rerun for this eval step"
        )
        return VerificationResult(
            passed=True,
            checks=(
                CheckResult(
                    name="V0_screening_verification_reuse",
                    passed=True,
                    severity="light",
                    detail=detail,
                    elapsed_ms=0,
                    metadata=metadata,
                ),
            ),
        )

    detail = (
        f"{action_label} cannot reuse screening/reconcile verification: "
        "current and last-clean code hashes must be present and equal, and "
        "branch code status must be clean"
    )
    return VerificationResult(
        passed=False,
        checks=(
            CheckResult(
                name="V0_screening_verification_reuse",
                passed=False,
                severity="heavy",
                detail=detail,
                elapsed_ms=0,
                metadata=metadata,
            ),
        ),
        failure_severity="heavy",
        first_failure="V0_screening_verification_reuse",
    )


def _protocol_cache_stats(protocol_result: Any | None) -> dict[str, int] | None:
    if protocol_result is None:
        return None
    return {
        "champion_cache_hits": max(
            0,
            int(getattr(protocol_result, "champion_cache_hits", 0) or 0),
        ),
        "champion_cache_misses": max(
            0,
            int(getattr(protocol_result, "champion_cache_misses", 0) or 0),
        ),
        "champion_cached_runtime_pairs": max(
            0,
            int(getattr(protocol_result, "champion_cached_runtime_pairs", 0) or 0),
        ),
    }


def _verification_result_detail(vresult: VerificationResult) -> str | None:
    if not vresult or not vresult.checks:
        return None
    failed = [check for check in vresult.checks if not check.passed]
    checks = failed if failed else list(vresult.checks)
    lines = []
    if failed:
        lines.append(
            f"severity={vresult.failure_severity or 'unknown'}  "
            f"first_failure={vresult.first_failure or 'N/A'}"
        )
    for check in checks:
        lines.append(f"  [{check.name}] ({check.severity}) {check.detail}")
    return "\n".join(lines) if lines else None


def _verification_rejection_outcome(
    vresult: VerificationResult,
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
            "owner": "verification_gate",
            "stage": "verification",
            "severity": severity,
            "verification_checks": checks,
            "attempt_kind": "reconcile_lifecycle",
        },
    )


def _contract_rejection_outcome(
    result: ContractResult,
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
            "owner": "outer_contract",
            "stage": "patch_contract",
            "contract_checks": checks,
            "attempt_kind": "reconcile_lifecycle",
        },
    )


def _same_champion_identity(left: ChampionState, right: ChampionState) -> bool:
    return (
        left.version,
        left.code_snapshot_hash,
        left.weight_revision,
    ) == (
        right.version,
        right.code_snapshot_hash,
        right.weight_revision,
    )


def _scheduler_max_active_branches(scheduler: Any) -> int | None:
    value = getattr(scheduler, "max_active_branches", None)
    if value is None:
        return None
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return None


def _attach_active_slot_audit(
    result: StepResult,
    reconciliations: list[dict[str, Any]],
    *,
    capacity_block: dict[str, Any] | None = None,
) -> StepResult:
    if not reconciliations and capacity_block is None:
        return result
    audit_metadata = dict(getattr(result, "scheduler_audit_metadata", None) or {})
    if reconciliations:
        audit_metadata["active_slot_reconciliations"] = list(reconciliations)
        audit_metadata["active_slot_reconciliation"] = dict(reconciliations[-1])
    if capacity_block is not None:
        audit_metadata["active_slot_hard_cap"] = dict(capacity_block)
    result.scheduler_audit_metadata = audit_metadata
    return result


def _with_scheduler_metadata(result: StepResult, sched: Any) -> StepResult:
    result.scheduler_slot = str(getattr(sched, "slot", "") or "")
    result.scheduler_reason = str(getattr(sched, "reason", "") or "")
    scheduler_action = str(getattr(sched, "action", "") or "")
    scheduled_branch = getattr(sched, "branch", None)
    scheduled_branch_id = str(getattr(scheduled_branch, "branch_id", "") or "")
    audit_metadata = dict(getattr(result, "scheduler_audit_metadata", None) or {})
    scheduler_audit = getattr(sched, "audit_metadata", None)
    if isinstance(scheduler_audit, Mapping):
        for key, value in scheduler_audit.items():
            audit_metadata.setdefault(str(key), value)
    if scheduler_action:
        audit_metadata.setdefault("scheduler_action", scheduler_action)
        audit_metadata.setdefault(
            "pre_finalizer_scheduler_action",
            scheduler_action,
        )
    if result.scheduler_slot:
        audit_metadata.setdefault("scheduler_slot", result.scheduler_slot)
        audit_metadata.setdefault(
            "pre_finalizer_scheduler_slot",
            result.scheduler_slot,
        )
    if result.scheduler_reason:
        audit_metadata.setdefault("scheduler_reason", result.scheduler_reason)
        audit_metadata.setdefault(
            "pre_finalizer_scheduler_reason",
            result.scheduler_reason,
        )
    if scheduled_branch_id:
        audit_metadata.setdefault(
            "pre_finalizer_selected_branch_id",
            scheduled_branch_id,
        )
    audit_metadata.setdefault("scheduler_semantics", "state_priority_fifo")
    result.scheduler_audit_metadata = audit_metadata
    return result


def _finalize_scheduler_result(
    result: StepResult,
    sched: Any,
    record_scheduler_result: Optional[Callable[[StepResult], None]] = None,
) -> StepResult:
    result = _with_scheduler_metadata(result, sched)
    if record_scheduler_result is not None:
        try:
            record_scheduler_result(result)
        except Exception as exc:  # pragma: no cover - persistence must not stop a step
            logger.debug("record_scheduler_result failed: %s", exc)
    return result


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
