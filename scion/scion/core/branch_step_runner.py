"""Branch-step execution boundary for CampaignManager."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Mapping, MutableMapping
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from scion.core.branch import BranchController, StateTransitionError
from scion.core.evaluation_orchestrator import EvaluationExecutionResult
from scion.core.execution_outcome import (
    ExecutionOutcome,
    ExecutionOutcomeRecord,
    block_branch_after_execution,
    disposition_failure_record,
    record_execution_outcome_event,
)
from scion.core.models import (
    AcceptedBranchChange,
    Branch,
    BranchState,
    ChampionState,
    ContractResult,
    HypothesisProposal,
    PatchProposal,
    StepRecord,
    VerificationResult,
    branch_base_source_ref,
    branch_changed_files,
)
from scion.core.scheduler import (
    Scheduler,
    SchedulerAction,
)
from scion.core.step_result import StepResult
from scion.core.verification_call import run_verification_gate
from scion.core.workspace_service import CandidateWorkspace

logger = logging.getLogger(__name__)

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
    create_reconcile_workspace: Callable[[str], str] | None = None
    reconcile_source_conflicts: (
        Callable[[str, AcceptedBranchChange], tuple[str, ...]] | None
    ) = None
    apply_reconcile_change: Callable[..., Any] | None = None
    seal_reconcile_candidate: Callable[..., CandidateWorkspace] | None = None
    verify_reconcile_candidate: (
        Callable[[CandidateWorkspace], CandidateWorkspace] | None
    ) = None
    discard_reconcile_workspace: Callable[[str], Any] | None = None

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

        if sched.action == "create_new":
            with self.champion_lock:
                champion = self.get_champion()
            branch = self.branch_controller.create_branch(champion)
            logger.info("Created new branch %s", branch.branch_id)
            result = self.run_explore_step(branch)
            result.action = "create_branch"
            return result

        branch = sched.branch
        assert branch is not None

        # EXPLORE branches share one research tier.  Advance service time before
        # H/C so rejected research returns to the back of the in-process queue.
        if branch.state == BranchState.EXPLORE:
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
        base_champion_version = branch.base_champion_id
        base_source_ref = branch_base_source_ref(branch)
        hypothesis = branch.hypothesis
        action_label = self._eval_action_label(branch)
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
                selected_hypothesis_research_basis=deepcopy(
                    branch.selected_hypothesis_research_basis
                ),
            )
            if hypothesis is not None:
                patch = self.branch_patches.get(bid)
                self.record_step(
                    StepRecord(
                        round_num=self.increment_round(),
                        branch_id=bid,
                        hypothesis=hypothesis,
                        patch=patch,
                        contract_passed=None,
                        verification_passed=None,
                        protocol_result=None,
                        decision=None,
                        failure_stage="evaluation_metadata",
                        failure_detail=outcome.detail,
                        execution_outcome=outcome,
                        selected_hypothesis_research_basis=deepcopy(
                            branch.selected_hypothesis_research_basis
                        ),
                        base_champion_version=base_champion_version,
                        base_source_ref=base_source_ref,
                        changed_files=branch_changed_files(branch, patch),
                    )
                )
            return StepResult(
                action=action_label,
                branch_id=bid,
                reason=outcome.detail,
                failure_stage="evaluation_metadata",
                failure_detail=outcome.detail,
                execution_outcome=outcome,
            )

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
                selected_hypothesis_research_basis=deepcopy(
                    branch.selected_hypothesis_research_basis
                ),
            )
            return StepResult(
                action=action_label,
                branch_id=bid,
                reason=outcome.detail,
                failure_stage="evaluation_metadata",
                failure_detail=outcome.detail,
                execution_outcome=outcome,
            )

        patch = self.branch_patches.get(bid)
        selected_hypothesis_research_basis = deepcopy(
            branch.selected_hypothesis_research_basis
        )
        source_fields = {
            "base_champion_version": base_champion_version,
            "base_source_ref": base_source_ref,
            "changed_files": branch_changed_files(branch, patch),
        }
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
                selected_hypothesis_research_basis=(
                    selected_hypothesis_research_basis
                ),
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
                    selected_hypothesis_research_basis=(
                        selected_hypothesis_research_basis
                    ),
                    **source_fields,
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
                selected_hypothesis_research_basis=(
                    selected_hypothesis_research_basis
                ),
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
                    selected_hypothesis_research_basis=(
                        selected_hypothesis_research_basis
                    ),
                    **source_fields,
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
        if branch.hypothesis is None and branch.state is BranchState.ABANDONED:
            branch.selected_hypothesis_research_basis = None
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
                selected_hypothesis_research_basis=(
                    selected_hypothesis_research_basis
                ),
                **source_fields,
            )
        )
        return result

    def run_reconcile_step(self, branch: Branch) -> StepResult:
        """Attempt to rebase a stale branch on the new champion."""
        bid = branch.branch_id
        accepted_changes = tuple(branch.accepted_changes)
        staging_workspace: str | None = None
        staging_handed_off = False
        staging_disposition_failed = False
        candidate: CandidateWorkspace | None = None
        replay_contract_checks: list[Any] = []

        def discard_staging(
            *,
            interrupted_outcome: ExecutionOutcomeRecord,
            selected_hypothesis_research_basis: dict[str, Any] | None,
        ) -> tuple[ExecutionOutcomeRecord, bool]:
            """Dispose staging before recording a pre-Decision terminal."""

            nonlocal staging_disposition_failed, staging_workspace
            if staging_workspace is None:
                return interrupted_outcome, False
            workspace = staging_workspace
            try:
                assert self.discard_reconcile_workspace is not None
                self.discard_reconcile_workspace(workspace)
            except Exception as exc:
                failed = disposition_failure_record(
                    reason_code="CANDIDATE_REJECT_FAILED",
                    error=exc,
                    operation="discard_reconcile_workspace",
                    interrupted_outcome=interrupted_outcome,
                )
                try:
                    self._record_execution_outcome(
                        branch,
                        failed,
                        event_kind="candidate_disposition_execution_outcome",
                        selected_hypothesis_research_basis=(
                            selected_hypothesis_research_basis
                        ),
                    )
                except Exception:
                    logger.exception(
                        "Branch %s: reconcile disposition outcome could not persist",
                        bid,
                    )
                block_branch_after_execution(branch, failed)
                staging_disposition_failed = True
                return failed, True
            staging_workspace = None
            return interrupted_outcome, False

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
            *,
            hypothesis: HypothesisProposal,
            patch: PatchProposal,
            selected_hypothesis_research_basis: dict[str, Any] | None,
            source_fields: Mapping[str, Any],
            reason_code: str = "RECONCILE_BRANCH_ABANDONED",
            failure_stage: str = "reconcile",
            contract_passed: bool | None = True,
            verification_passed: bool | None = None,
            contract_diagnostics: tuple[dict[str, Any], ...] = (),
            outcome_override: ExecutionOutcomeRecord | None = None,
            event_kind: str = "reconcile_research_rejection",
        ) -> StepResult:
            outcome = outcome_override or ExecutionOutcomeRecord(
                outcome=ExecutionOutcome.RESEARCH_REJECTED,
                reason_code=reason_code,
                detail=reason,
                provenance={
                    "stage": failure_stage,
                    "contract_checks": list(contract_diagnostics),
                },
            )
            outcome, disposition_failed = discard_staging(
                interrupted_outcome=outcome,
                selected_hypothesis_research_basis=(
                    selected_hypothesis_research_basis
                ),
            )
            actual_failure_stage = (
                "candidate_disposition" if disposition_failed else failure_stage
            )
            actual_failure_detail = outcome.detail or reason
            actual_reason = actual_failure_detail if disposition_failed else reason
            if not disposition_failed:
                close_stale()
            self._record_reconcile_failure(
                branch=branch,
                hypothesis=hypothesis,
                patch=patch,
                outcome=outcome,
                event_kind=event_kind,
                failure_stage=actual_failure_stage,
                failure_detail=actual_failure_detail,
                contract_passed=contract_passed,
                verification_passed=verification_passed,
                contract_diagnostics=contract_diagnostics,
                selected_hypothesis_research_basis=(
                    selected_hypothesis_research_basis
                ),
                source_fields=source_fields,
                event_already_recorded=disposition_failed,
            )
            return StepResult(
                action="reconcile",
                branch_id=bid,
                reason=actual_reason,
                failure_stage=actual_failure_stage,
                failure_category=outcome.outcome.value,
                failure_detail=actual_failure_detail,
                execution_outcome=outcome,
            )

        def preserve_stale(
            *,
            reason_code: str,
            detail: str,
            contract_passed: bool | None = None,
            verification_passed: bool | None = None,
        ) -> StepResult:
            outcome = self._non_evaluated_outcome(
                branch,
                reason_code=reason_code,
                detail=detail,
            )
            outcome, disposition_failed = discard_staging(
                interrupted_outcome=outcome,
                selected_hypothesis_research_basis=replay_head_basis,
            )
            if not disposition_failed:
                self._record_execution_outcome(
                    branch,
                    outcome,
                    event_kind="reconcile_not_evaluated_outcome",
                    selected_hypothesis_research_basis=replay_head_basis,
                )
            failure_stage = (
                "candidate_disposition"
                if disposition_failed
                else "evaluation_metadata"
            )
            failure_detail = outcome.detail if disposition_failed else detail
            replay_head = accepted_changes[-1]
            self.record_step(
                StepRecord(
                    round_num=self.increment_round(),
                    branch_id=bid,
                    hypothesis=replay_head.hypothesis,
                    patch=replay_head.patch,
                    contract_passed=contract_passed,
                    verification_passed=verification_passed,
                    protocol_result=None,
                    decision=None,
                    failure_stage=failure_stage,
                    failure_detail=failure_detail,
                    execution_outcome=outcome,
                    selected_hypothesis_research_basis=deepcopy(
                        replay_head_basis
                    ),
                    **reconcile_source_fields,
                )
            )
            return StepResult(
                action="reconcile",
                branch_id=bid,
                reason=failure_detail,
                failure_stage=failure_stage,
                failure_detail=failure_detail,
                execution_outcome=outcome,
            )

        if not accepted_changes:
            detail = "no accepted changes to reconcile"
            logger.info(
                "Branch %s: no accepted changes to reconcile - abandoning stale branch",
                bid,
            )
            close_stale()
            branch.selected_hypothesis_research_basis = None
            outcome = ExecutionOutcomeRecord(
                outcome=ExecutionOutcome.NOT_EVALUATED,
                reason_code="RECONCILE_NO_ACCEPTED_CHANGES",
                detail=detail,
                provenance={"stage": "reconcile"},
            )
            self._record_execution_outcome(
                branch,
                outcome,
                event_kind="reconcile_not_evaluated_outcome",
                selected_hypothesis_research_basis=None,
                hold_branch=False,
            )
            return StepResult(
                action="reconcile",
                branch_id=bid,
                reason=detail,
                failure_stage="reconcile",
                failure_category=ExecutionOutcome.NOT_EVALUATED.value,
                failure_detail=detail,
                execution_outcome=outcome,
            )

        replay_head_basis = deepcopy(
            accepted_changes[-1].selected_hypothesis_research_basis
        )

        with self.champion_lock:
            champion = self.get_champion()
        champion_workspace = champion.code_snapshot_path
        reconcile_source_fields = {
            "base_champion_version": champion.version,
            "base_source_ref": f"champion:v{champion.version}",
            "changed_files": branch_changed_files(branch),
        }

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
            self.create_reconcile_workspace,
            self.reconcile_source_conflicts,
            self.apply_reconcile_change,
            self.seal_reconcile_candidate,
            self.verify_reconcile_candidate,
            self.discard_reconcile_workspace,
        )
        if any(callback is None for callback in candidate_callbacks):
            return preserve_stale(
                reason_code="RECONCILE_WORKSPACE_UNAVAILABLE",
                detail="reconcile workspace service unavailable",
            )

        try:
            try:
                assert self.create_reconcile_workspace is not None
                staging_workspace = self.create_reconcile_workspace(
                    champion_workspace
                )
            except BaseException as exc:
                if not isinstance(exc, Exception):
                    raise
                return preserve_stale(
                    reason_code="RECONCILE_WORKSPACE_CREATE_FAILED",
                    detail=str(exc),
                )

            for change_index, accepted_change in enumerate(
                accepted_changes,
                start=1,
            ):
                hypothesis = accepted_change.hypothesis
                patch = accepted_change.patch
                contract_result = self.contract_gate.validate_patch(
                    patch,
                    approved_hypothesis=hypothesis,
                    base_snapshot_path=staging_workspace,
                )
                if not contract_result.passed:
                    logger.info(
                        "Branch %s: reconcile change %d failed contract gate: %s",
                        bid,
                        change_index,
                        contract_result.failure_reason,
                    )
                    reason = (
                        f"reconcile change {change_index} contract failed: "
                        f"{contract_result.failure_reason}"
                    )
                    checks = tuple(_contract_check_payload(contract_result))
                    outcome = _contract_rejection_outcome(contract_result, patch)
                    return abandon_stale(
                        reason,
                        hypothesis=hypothesis,
                        patch=patch,
                        selected_hypothesis_research_basis=deepcopy(
                            accepted_change.selected_hypothesis_research_basis
                        ),
                        source_fields=reconcile_source_fields,
                        reason_code="PATCH_CONTRACT_REJECTED",
                        failure_stage="patch_contract",
                        contract_passed=False,
                        contract_diagnostics=checks,
                        outcome_override=outcome,
                        event_kind="contract_fail",
                    )
                replay_contract_checks.extend(contract_result.checks)

                assert self.reconcile_source_conflicts is not None
                conflicts = self.reconcile_source_conflicts(
                    staging_workspace,
                    accepted_change,
                )
                if conflicts:
                    conflict_paths = ", ".join(conflicts)
                    logger.info(
                        "Branch %s: reconcile change %d conflicts at %s",
                        bid,
                        change_index,
                        conflict_paths,
                    )
                    return abandon_stale(
                        "accepted change "
                        f"{change_index} before-source conflict: {conflict_paths}",
                        hypothesis=hypothesis,
                        patch=patch,
                        selected_hypothesis_research_basis=deepcopy(
                            accepted_change.selected_hypothesis_research_basis
                        ),
                        source_fields=reconcile_source_fields,
                        reason_code="RECONCILE_SOURCE_CONFLICT",
                        failure_stage="reconcile_source",
                        contract_diagnostics=tuple(
                            _contract_check_payload(contract_result)
                        ),
                    )

                try:
                    assert self.apply_reconcile_change is not None
                    self.apply_reconcile_change(
                        staging_workspace,
                        patch,
                        hypothesis=hypothesis,
                    )
                except BaseException as exc:
                    if not isinstance(exc, Exception):
                        raise
                    logger.info(
                        "Branch %s: reconcile change %d apply_patch failed: %s",
                        bid,
                        change_index,
                        exc,
                    )
                    return abandon_stale(
                        "apply_patch failed for accepted change "
                        f"{change_index}: {exc}",
                        hypothesis=hypothesis,
                        patch=patch,
                        selected_hypothesis_research_basis=deepcopy(
                            accepted_change.selected_hypothesis_research_basis
                        ),
                        source_fields=reconcile_source_fields,
                        reason_code="RECONCILE_APPLY_FAILED",
                        failure_stage="reconcile_apply",
                        contract_diagnostics=tuple(
                            _contract_check_payload(contract_result)
                        ),
                    )

            hypothesis = accepted_changes[-1].hypothesis
            patch = accepted_changes[-1].patch
            contract_result = ContractResult(
                passed=True,
                checks=tuple(replay_contract_checks),
            )

            try:
                assert self.seal_reconcile_candidate is not None
                replayed_patch_files = tuple(
                    dict.fromkeys(
                        change.file_path
                        for accepted_change in accepted_changes
                        for change in accepted_change.patch.iter_file_changes()
                    )
                )
                candidate = self.seal_reconcile_candidate(
                    staging_workspace,
                    base_workspace=champion_workspace,
                    changed_files=replayed_patch_files,
                )
                reconcile_source_fields["changed_files"] = candidate.changed_files
            except BaseException as exc:
                if not isinstance(exc, Exception):
                    raise
                return preserve_stale(
                    reason_code="RECONCILE_BASELINE_DIGEST_FAILED",
                    detail=str(exc),
                    contract_passed=True,
                )

            workspace = candidate.workspace
            verification_result = run_verification_gate(
                self.verification_gate,
                workspace,
                champion_workspace,
                patch,
                hypothesis=hypothesis,
            )
            if not verification_result.passed:
                logger.info(
                    "Branch %s: reconcile verification failed: %s",
                    bid,
                    verification_result.first_failure,
                )
                reason = (
                    "reconcile verification failed: "
                    f"{verification_result.first_failure}"
                )
                return abandon_stale(
                    reason,
                    hypothesis=hypothesis,
                    patch=patch,
                    selected_hypothesis_research_basis=deepcopy(
                        accepted_changes[-1].selected_hypothesis_research_basis
                    ),
                    source_fields=reconcile_source_fields,
                    reason_code=(
                        "VERIFICATION_LIGHT_REJECTED"
                        if (verification_result.failure_severity or "light")
                        == "light"
                        else "VERIFICATION_HEAVY_REJECTED"
                    ),
                    failure_stage="verification",
                    contract_passed=True,
                    verification_passed=False,
                    contract_diagnostics=tuple(
                        _contract_check_payload(contract_result)
                    ),
                    outcome_override=_verification_rejection_outcome(
                        verification_result,
                        patch,
                    ),
                    event_kind="verification_fail",
                )

            with self.champion_lock:
                current_champion = self.get_champion()
            if not _same_champion_revision(champion, current_champion):
                return preserve_stale(
                    reason_code="RECONCILE_CHAMPION_DRIFTED",
                    detail="champion changed during reconcile verification",
                    contract_passed=True,
                    verification_passed=True,
                )

            try:
                assert self.verify_reconcile_candidate is not None
                candidate = self.verify_reconcile_candidate(candidate)
            except Exception as exc:
                return preserve_stale(
                    reason_code="RECONCILE_CANDIDATE_VERIFICATION_FAILED",
                    detail=str(exc),
                    contract_passed=True,
                    verification_passed=True,
                )
            workspace = candidate.workspace

            round_num = self.increment_round()
            evaluation = self.evaluate(
                branch,
                workspace,
                hypothesis,
                branch_state=BranchState.EXPLORE,
                screening_expand_count=0,
                validation_expand_count=0,
            )
            if not isinstance(evaluation, EvaluationExecutionResult):
                raise TypeError(
                    "evaluate callback must return EvaluationExecutionResult"
                )
            decision = evaluation.decision
            protocol_result = evaluation.protocol_result
            canary_result = evaluation.canary_result
            execution_outcome = evaluation.execution_outcome
            if execution_outcome.outcome is not ExecutionOutcome.EVALUATED:
                execution_outcome, disposition_failed = discard_staging(
                    interrupted_outcome=execution_outcome,
                    selected_hypothesis_research_basis=replay_head_basis,
                )
                if not disposition_failed:
                    self._record_execution_outcome(
                        branch,
                        execution_outcome,
                        event_kind="reconcile_evaluation_outcome",
                        selected_hypothesis_research_basis=replay_head_basis,
                    )
                failure_stage = (
                    "candidate_disposition"
                    if disposition_failed
                    else "evaluation"
                )
                result = StepResult(
                    action="reconcile",
                    branch_id=bid,
                    reason=(
                        execution_outcome.detail or execution_outcome.reason_code
                    ),
                    failure_stage=failure_stage,
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
                        patch=patch,
                        contract_passed=True,
                        verification_passed=True,
                        protocol_result=None,
                        decision=None,
                        failure_stage=failure_stage,
                        failure_detail=(
                            execution_outcome.detail
                            or execution_outcome.reason_code
                        ),
                        decision_reason_codes=None,
                        **provenance,
                        canary_result=canary_result,
                        execution_outcome=execution_outcome,
                        selected_hypothesis_research_basis=deepcopy(
                            replay_head_basis
                        ),
                        **reconcile_source_fields,
                    )
                )
                return result
            if decision is None:
                raise ValueError("evaluated result missing Decision")

            branch.selected_hypothesis_research_basis = deepcopy(
                replay_head_basis
            )
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
            staging_handed_off = (
                self.branch_workspaces.get(bid) == staging_workspace
            )
            if result.execution_outcome is None:
                result.protocol_result = protocol_result
                result.canary_result = canary_result
                result.execution_outcome = execution_outcome
            failure_stage, failure_detail = (
                (result.failure_stage, result.failure_detail)
                if result.execution_outcome.outcome
                is not ExecutionOutcome.EVALUATED
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
                    selected_hypothesis_research_basis=deepcopy(
                        replay_head_basis
                    ),
                    **reconcile_source_fields,
                ),
            )
            return result
        finally:
            if self.branch_workspaces.get(bid) == staging_workspace:
                staging_handed_off = True
            if (
                not staging_handed_off
                and not staging_disposition_failed
                and staging_workspace is not None
            ):
                try:
                    assert self.discard_reconcile_workspace is not None
                    self.discard_reconcile_workspace(staging_workspace)
                except Exception:
                    logger.exception(
                        "Branch %s: failed to discard interrupted reconcile staging",
                        bid,
                    )

    def _record_reconcile_failure(
        self,
        *,
        branch: Branch,
        hypothesis: HypothesisProposal,
        patch: PatchProposal,
        outcome: ExecutionOutcomeRecord,
        event_kind: str,
        failure_stage: str,
        failure_detail: str,
        contract_passed: bool | None,
        verification_passed: bool | None,
        contract_diagnostics: tuple[dict[str, Any], ...],
        selected_hypothesis_research_basis: dict[str, Any] | None,
        source_fields: Mapping[str, Any],
        event_already_recorded: bool = False,
    ) -> None:
        """Persist one non-Decision stale replay result as ordinary science."""

        base_champion_version = source_fields["base_champion_version"]
        base_source_ref = source_fields["base_source_ref"]
        changed_files = tuple(source_fields["changed_files"])
        if not event_already_recorded:
            record_execution_outcome_event(
                registry=self.registry,
                campaign_id=self.campaign_id,
                branch_id=branch.branch_id,
                record=outcome,
                event_kind=event_kind,
                selected_hypothesis_research_basis=(
                    selected_hypothesis_research_basis
                ),
                extra_fields={
                    "base_champion_version": base_champion_version,
                    "base_source_ref": base_source_ref,
                    "changed_files_json": json.dumps(list(changed_files)),
                    "hypothesis_text": hypothesis.hypothesis_text or "",
                    "patch_action": patch.action,
                    "patch_file": patch.file_path,
                    "contract_result": _gate_result_label(contract_passed),
                    "contract_diagnostics_json": json.dumps(
                        list(contract_diagnostics), sort_keys=True
                    ),
                    "verification_result": _gate_result_label(verification_passed),
                },
            )
        self.record_step(
            StepRecord(
                round_num=self.increment_round(),
                branch_id=branch.branch_id,
                hypothesis=hypothesis,
                patch=patch,
                contract_passed=contract_passed,
                verification_passed=verification_passed,
                protocol_result=None,
                decision=None,
                failure_stage=failure_stage,
                failure_detail=failure_detail,
                contract_diagnostics=contract_diagnostics,
                execution_outcome=outcome,
                selected_hypothesis_research_basis=deepcopy(
                    selected_hypothesis_research_basis
                ),
                base_champion_version=base_champion_version,
                base_source_ref=base_source_ref,
                changed_files=changed_files,
            )
        )

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
            selected_hypothesis_research_basis=deepcopy(
                branch.selected_hypothesis_research_basis
            ),
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
                    selected_hypothesis_research_basis=deepcopy(
                        branch.selected_hypothesis_research_basis
                    ),
                    base_champion_version=branch.base_champion_id,
                    base_source_ref=branch_base_source_ref(branch),
                    changed_files=branch_changed_files(
                        branch,
                        self.branch_patches.get(bid),
                    ),
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
        selected_hypothesis_research_basis: Mapping[str, Any] | None,
        hold_branch: bool = True,
    ) -> str | None:
        event_id = record_execution_outcome_event(
            registry=self.registry,
            campaign_id=self.campaign_id,
            branch_id=branch.branch_id,
            record=record,
            event_kind=event_kind,
            selected_hypothesis_research_basis=(
                selected_hypothesis_research_basis
            ),
        )
        if hold_branch and block_branch_after_execution(branch, record):
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


def _contract_check_payload(
    result: ContractResult,
) -> tuple[dict[str, Any], ...]:
    return tuple(
        {
            "name": check.name,
            "passed": check.passed,
            "severity": check.severity,
            "detail": check.detail,
            "elapsed_ms": check.elapsed_ms,
            "metadata": dict(check.metadata or {}),
        }
        for check in result.checks
    )


def _gate_result_label(value: bool | None) -> str:
    if value is None:
        return "not_run"
    return "passed" if value else "failed"


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
