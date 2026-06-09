"""Branch-step execution boundary for CampaignManager."""
from __future__ import annotations

import copy
import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Any, Callable, Mapping, MutableMapping, Optional

from scion.core.branch import BranchController, StateTransitionError
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
from scion.core.scheduler import (
    Scheduler,
    SchedulerAction,
    branch_active_slot_release_reason,
    branch_counts_toward_active_slots,
    active_slot_capacity_block_metadata,
    reclaim_active_slot_for_new_branch,
    reconcile_active_slot_overflow,
)
from scion.core.evidence_recording.replay_identity import (
    formal_replay_identity_missing_keys,
)
from scion.core.branch_lifecycle_policy import (
    BRANCH_LIFECYCLE_ARCHIVE_LINEAGE,
    BRANCH_LIFECYCLE_PARK_LINEAGE,
    BRANCH_LIFECYCLE_RETAIN_CHECKPOINT,
    BRANCH_LIFECYCLE_ROLLBACK_TO_CHECKPOINT,
)
from scion.core.step_result import StepResult
from scion.core.frozen_budget import FROZEN_BUDGET_EXHAUSTED
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
    tick_blocked_branches: Callable[[], None]
    persist_branch_state: Callable[[str], None]
    record_hard_abandon: Callable[[str, str], None]
    setup_workspace: Callable[..., Optional[str]]
    apply_patch: Callable[..., Any]
    record_verification_pass: Callable[[Branch, str], None]
    evaluate: Callable[
        [Branch, str, HypothesisProposal],
        tuple[Optional[Decision], Any, Any],
    ]
    apply_decision_and_finalize: Callable[..., StepResult]
    record_step: Callable[[StepRecord], None]
    decision_reason_codes_for: Callable[[str, Any], Optional[tuple[str, ...]]]
    run_explore_step: Callable[[Branch], StepResult]
    run_eval_step_callback: Callable[[Branch], StepResult]
    run_reconcile_step_callback: Callable[[Branch], StepResult]
    increment_round: Callable[[], int]
    increment_rounds_since_last_promote: Callable[[], None]
    hypothesis_store: Any
    record_scheduler_result: Optional[Callable[[StepResult], None]] = None
    decision_provenance_for: Callable[[str], dict[str, Any]] = lambda _branch_id: {}

    def run_one_step(self) -> StepResult:
        """Execute one campaign step and return a StepResult."""
        self.drain_weight_opt_events()
        if self.should_stop():
            return StepResult(
                action="stopped",
                stopped=True,
                reason=self.get_last_stop_reason() or "termination condition met",
            )

        self.tick_blocked_branches()
        max_active_branches = _scheduler_max_active_branches(self.scheduler)
        active_slot_reconciliations: list[dict[str, Any]] = []

        active = self.branch_controller.get_active_branches()
        if max_active_branches is not None:
            reconciliation = reconcile_active_slot_overflow(
                active,
                max_active_branches=max_active_branches,
            )
            if reconciliation.changed or reconciliation.blocked:
                self._persist_active_slot_reconciliation(reconciliation)
                active_slot_reconciliations.append(
                    reconciliation.as_audit_metadata()
                )
                if reconciliation.changed:
                    active = self.branch_controller.get_active_branches()

        sched = self.scheduler.select_next(active)
        if sched.action == "at_capacity" and max_active_branches is not None:
            reconciliation = reclaim_active_slot_for_new_branch(
                active,
                max_active_branches=max_active_branches,
            )
            if reconciliation.changed or reconciliation.blocked:
                self._persist_active_slot_reconciliation(reconciliation)
                active_slot_reconciliations.append(
                    reconciliation.as_audit_metadata()
                )
                if reconciliation.changed:
                    active = self.branch_controller.get_active_branches()
                    sched = self.scheduler.select_next(active)

        def finalize(
            result: StepResult,
            *,
            capacity_block: dict[str, Any] | None = None,
        ) -> StepResult:
            return _finalize_scheduler_result(
                _attach_active_slot_audit(
                    result,
                    active_slot_reconciliations,
                    capacity_block=capacity_block,
                ),
                sched,
                self.record_scheduler_result,
            )

        if sched.action == "at_capacity":
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
                    counts_toward_max_rounds=False,
                    attempt_kind="scheduler_active_slot_blocked",
                ),
                capacity_block=capacity_block,
            )

        if sched.action == "create_new":
            with self.champion_lock:
                champion = self.get_champion()
            branch = self.branch_controller.create_branch(champion)
            _attach_material_difference_requirement_metadata(
                branch,
                getattr(sched, "audit_metadata", None),
            )
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
                    )
                )

        branch = self.branch_controller.get_branch(branch.branch_id)

        if branch.state in (BranchState.STALE, BranchState.STALE_WEIGHT_UPDATE):
            return finalize(self.run_reconcile_step_callback(branch))

        if branch.state == BranchState.EXPLORE:
            if str(getattr(sched, "action", "") or "") == "replay_existing":
                return finalize(self.run_fresh_runtime_replay_step(branch))
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
            )
        )

    def run_fresh_runtime_replay_drain_step(self) -> StepResult:
        """Execute one post-max-round fresh-runtime replay, if selected."""
        self.drain_weight_opt_events()
        if self.should_stop():
            return StepResult(
                action="stopped",
                stopped=True,
                reason=self.get_last_stop_reason() or "termination condition met",
                counts_toward_max_rounds=False,
                attempt_kind="other",
            )

        active = self.branch_controller.get_active_branches()
        non_replayable_marked = (
            _mark_non_materializable_fresh_runtime_candidates(
                active,
                branch_workspaces=self.branch_workspaces,
                branch_hypotheses=self.branch_hypotheses,
                branch_current_hypothesis=self.branch_current_hypothesis,
                branch_patches=self.branch_patches,
            )
        )
        pending_materialized = _materialize_fresh_runtime_pending_markers(
            active,
            branch_workspaces=self.branch_workspaces,
            branch_hypotheses=self.branch_hypotheses,
            branch_current_hypothesis=self.branch_current_hypothesis,
            branch_patches=self.branch_patches,
        )
        for entry in [*pending_materialized, *non_replayable_marked]:
            branch_id = str(entry.get("branch_id") or "")
            if branch_id:
                self.persist_branch_state(branch_id)
        sched = self.scheduler.select_next(active)
        branch = getattr(sched, "branch", None)
        if pending_materialized:
            scheduler_audit = dict(getattr(sched, "audit_metadata", None) or {})
            scheduler_audit.setdefault(
                "fresh_runtime_pending_materialized",
                pending_materialized,
            )
            if non_replayable_marked:
                scheduler_audit.setdefault(
                    "fresh_runtime_non_replayable_marked",
                    non_replayable_marked,
                )
            sched_action = str(getattr(sched, "action", "") or "run_existing")
            if sched_action not in {
                "run_existing",
                "replay_existing",
                "create_new",
                "at_capacity",
            }:
                sched_action = "run_existing"
            sched_slot = str(getattr(sched, "slot", "") or "refine_active")
            if sched_slot not in {
                "explore_new",
                "exploit_weak_positive",
                "repair_diagnostic",
                "refine_active",
                "capacity_blocked",
            }:
                sched_slot = "refine_active"
            sched = SchedulerAction(
                action=sched_action,  # type: ignore[arg-type]
                branch=branch,
                reason=str(getattr(sched, "reason", "") or ""),
                slot=sched_slot,  # type: ignore[arg-type]
                audit_metadata=scheduler_audit,
            )
        materializable_pending = _materializable_fresh_runtime_pending_branch(
            active,
            branch_workspaces=self.branch_workspaces,
            branch_hypotheses=self.branch_hypotheses,
            branch_current_hypothesis=self.branch_current_hypothesis,
            branch_patches=self.branch_patches,
        )
        if (
            str(getattr(sched, "action", "") or "") != "replay_existing"
            and materializable_pending is not None
        ):
            sched = SchedulerAction(
                action="replay_existing",
                branch=materializable_pending,
                reason="fresh_champion_runtime_replay_followup",
                slot="exploit_weak_positive",
                audit_metadata={
                    "fresh_runtime_replay_drain_override": (
                        "materializable_pending_replay_preferred"
                    ),
                    "fresh_runtime_pending_materialized": pending_materialized,
                    "fresh_runtime_non_replayable_marked": non_replayable_marked,
                    "decision_features_excluded": True,
                },
            )
            branch = materializable_pending

        def skip(reason: str) -> StepResult:
            pressure_without_candidate = (
                _fresh_runtime_pressure_without_replayable_candidate(
                    active,
                    branch_workspaces=self.branch_workspaces,
                    branch_hypotheses=self.branch_hypotheses,
                    branch_current_hypothesis=self.branch_current_hypothesis,
                    branch_patches=self.branch_patches,
                )
            )
            drain_metadata = {
                "schema_version": "fresh_runtime_replay_drain.v1",
                "executed": False,
                "skip_reason": reason,
                "decision_features_excluded": True,
            }
            if pending_materialized:
                drain_metadata["fresh_runtime_pending_materialized"] = (
                    pending_materialized
                )
            if non_replayable_marked:
                drain_metadata["fresh_runtime_non_replayable_marked"] = (
                    non_replayable_marked
                )
            if pressure_without_candidate:
                drain_metadata["pressure_no_replayable_candidate"] = True
                drain_metadata["fresh_runtime_pressure_candidates"] = (
                    pressure_without_candidate
                )
            replay_metadata: dict[str, Any] = {}
            if pressure_without_candidate:
                replay_metadata = {
                    "schema_version": "fresh_runtime_replay.v1",
                    "closure_status": "pressure_no_replayable_candidate",
                    "detail": (
                        "fresh champion runtime pressure exists but no "
                        "structured replay pending candidate is materializable"
                    ),
                    "fresh_runtime_pressure_candidates": (
                        pressure_without_candidate
                    ),
                    "missing_materialization_keys": (
                        _aggregate_missing_materialization_keys(
                            pressure_without_candidate
                        )
                    ),
                    "counts_toward_max_rounds": False,
                    "decision_features_excluded": True,
                }
            result = StepResult(
                action="skip",
                branch_id=getattr(branch, "branch_id", None),
                reason=reason,
                counts_toward_max_rounds=False,
                attempt_kind="other",
                scheduler_audit_metadata={
                    "fresh_runtime_replay_drain": drain_metadata,
                    **(
                        {"fresh_runtime_replay": replay_metadata}
                        if replay_metadata
                        else {}
                    ),
                },
            )
            return _with_scheduler_metadata(result, sched)

        if str(getattr(sched, "action", "") or "") != "replay_existing":
            return skip(
                "fresh runtime replay drain skipped: scheduler did not select replay_existing"
            )
        if branch is None:
            return skip(
                "fresh runtime replay drain skipped: scheduler selected no branch"
            )

        selected = self.branch_controller.get_branch(branch.branch_id)
        if selected.state != BranchState.EXPLORE:
            return skip(
                "fresh runtime replay drain skipped: selected branch is not explore"
            )
        return _finalize_scheduler_result(
            self.run_fresh_runtime_replay_step(selected),
            sched,
            self.record_scheduler_result,
        )

    def _persist_active_slot_reconciliation(self, reconciliation: Any) -> None:
        for branch_id in getattr(reconciliation, "parked_branch_ids", ()) or ():
            try:
                self.persist_branch_state(str(branch_id))
            except Exception as exc:  # pragma: no cover - persistence is best-effort
                logger.debug(
                    "Branch %s: active-slot reconciliation persist failed: %s",
                    branch_id,
                    exc,
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
            logger.warning("Branch %s: no workspace for eval step - abandoning", bid)
            self._reject_current_hypothesis(bid)
            self.branch_controller.apply_decision(bid, Decision.ABANDON)
            self.record_hard_abandon(bid, "eval_workspace_missing")
            return StepResult(action="validate", branch_id=bid, reason="workspace not found")

        hypothesis = self.branch_hypotheses.get(bid)
        if hypothesis is None:
            logger.warning("Branch %s: no hypothesis for eval step - abandoning", bid)
            self._reject_current_hypothesis(bid)
            self.branch_controller.apply_decision(bid, Decision.ABANDON)
            self.record_hard_abandon(bid, "eval_hypothesis_missing")
            return StepResult(action="validate", branch_id=bid, reason="hypothesis not found")

        patch = self.branch_patches.get(bid)
        action_label = self._eval_action_label(branch)
        verification_result = _screening_verification_reuse_result(
            branch,
            action_label=action_label,
        )

        h_record = self.branch_current_hypothesis.get(bid)
        if h_record is None:
            raise RuntimeError(
                f"Branch {bid}: no canonical hypothesis record - cannot proceed with eval"
            )

        contract_result = ContractResult(passed=True, checks=())
        if not verification_result.passed:
            logger.info(
                "Branch %s: eval verification reuse invariant failed: %s",
                bid,
                verification_result.first_failure,
            )
            self._reject_current_hypothesis(bid)
            self.branch_controller.apply_decision(bid, Decision.ABANDON)
            self.record_hard_abandon(bid, "eval_verification_reuse_invalid")
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
                    counts_toward_max_rounds=False,
                    attempt_kind="other",
                )
            )
            return StepResult(
                action=action_label,
                branch_id=bid,
                reason="verification reuse invalid",
                counts_toward_max_rounds=False,
                attempt_kind="other",
                failure_stage="verification",
                failure_detail=verification_result.first_failure,
            )

        decision, protocol_result, canary_result = self.evaluate(
            branch,
            workspace,
            hypothesis,
        )
        finalizer_decision = decision or Decision.ABANDON

        round_num = self.increment_round()
        if action_label == "explore":
            self.increment_rounds_since_last_promote()
        result = self.apply_decision_and_finalize(
            branch=branch,
            decision=finalizer_decision,
            hypothesis=hypothesis,
            h_record=h_record,
            protocol_result=protocol_result,
            canary_result=canary_result,
            contract_result=contract_result,
            verification_result=verification_result,
            action_label=action_label,
        )
        _annotate_protocol_accounting(result, protocol_result)
        failure_stage, failure_detail = _eval_failure_detail(
            protocol_result,
            canary_result=canary_result,
        )
        if decision is None:
            result.decision = None
            result.failure_stage = failure_stage or "evaluation"
            result.failure_detail = failure_detail or "evaluation failed"
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
                verification_detail=_verification_result_detail(
                    verification_result
                ),
                hypothesis_id=h_record.hypothesis_id,
                decision_reason_codes=self.decision_reason_codes_for(
                    bid,
                    protocol_result,
                ),
                **provenance,
                counts_toward_max_rounds=result.counts_toward_max_rounds,
                attempt_kind=result.attempt_kind,
                repair_policy_reason=result.repair_policy_reason or None,
                repair_mechanism_ids=result.repair_mechanism_ids,
            )
        )
        return result

    def run_fresh_runtime_replay_step(self, branch: Branch) -> StepResult:
        """Fresh champion replay for screening evidence closure.

        This path deliberately reuses the current branch candidate and does not
        call hypothesis/code proposal generation.
        """
        bid = branch.branch_id
        workspace = self.branch_workspaces.get(bid)
        hypothesis = self.branch_hypotheses.get(bid)
        h_record = self.branch_current_hypothesis.get(bid)
        patch = self.branch_patches.get(bid)
        if (
            workspace is None
            or hypothesis is None
            or h_record is None
            or patch is None
        ):
            missing = [
                name
                for name, value in (
                    ("workspace", workspace),
                    ("hypothesis", hypothesis),
                    ("hypothesis_record", h_record),
                    ("patch", patch),
                )
                if value is None
            ]
            materialization = _fresh_runtime_replay_materialization_block(
                branch,
                missing_live_state=missing,
            )
            closure_status = materialization["closure_status"]
            detail = str(materialization["detail"])
            _close_fresh_runtime_replay_marker(
                branch,
                closure_status=closure_status,
                detail=detail,
            )
            self.persist_branch_state(bid)
            return StepResult(
                action="replay",
                branch_id=bid,
                reason=detail,
                counts_toward_max_rounds=False,
                attempt_kind="fresh_runtime_replay",
                failure_stage="fresh_runtime_replay",
                failure_detail=detail,
                scheduler_audit_metadata={
                    "fresh_runtime_replay": {
                        "schema_version": "fresh_runtime_replay.v1",
                        "closure_status": closure_status,
                        "missing": missing,
                        **materialization["metadata"],
                        "counts_toward_max_rounds": False,
                    }
                },
            )

        materialization = _fresh_runtime_replay_materialization_diagnostic(
            branch,
            branch_workspaces=self.branch_workspaces,
            branch_hypotheses=self.branch_hypotheses,
            branch_current_hypothesis=self.branch_current_hypothesis,
            branch_patches=self.branch_patches,
        )
        if materialization["missing_materialization_keys"]:
            summary = getattr(branch, "branch_evidence_summary", {}) or {}
            evidence = summary if isinstance(summary, Mapping) else {}
            marked = _mark_non_materializable_fresh_runtime_candidates(
                [branch],
                branch_workspaces=self.branch_workspaces,
                branch_hypotheses=self.branch_hypotheses,
                branch_current_hypothesis=self.branch_current_hypothesis,
                branch_patches=self.branch_patches,
            )
            closure_status = "blocked_missing_replay_materialization"
            detail = (
                "fresh runtime replay missing replay materialization: "
                + ",".join(materialization["missing_materialization_keys"])
            )
            _close_fresh_runtime_replay_marker(
                branch,
                closure_status=closure_status,
                detail=detail,
            )
            self.persist_branch_state(bid)
            return StepResult(
                action="replay",
                branch_id=bid,
                reason=detail,
                counts_toward_max_rounds=False,
                attempt_kind="fresh_runtime_replay",
                failure_stage="fresh_runtime_replay",
                failure_detail=detail,
                scheduler_audit_metadata={
                    "fresh_runtime_replay": {
                        "schema_version": "fresh_runtime_replay.v1",
                        "closure_status": closure_status,
                        "missing_materialization_keys": list(
                            materialization["missing_materialization_keys"]
                        ),
                        "missing_replay_identity_keys": list(
                            materialization["missing_replay_identity_keys"]
                        ),
                        "replay_identity_status": materialization[
                            "replay_identity_status"
                        ],
                        "protocol_stage": materialization["protocol_stage"],
                        "candidate_code_hash": materialization[
                            "candidate_code_hash"
                        ],
                        "non_replayable_reason": _fresh_runtime_non_replayable_reason(
                            evidence,
                            materialization,
                        ),
                        "fresh_runtime_non_replayable_marked": marked,
                        "counts_toward_max_rounds": False,
                        "decision_features_excluded": True,
                    }
                },
            )

        verification_result = _screening_verification_reuse_result(
            branch,
            action_label="fresh_runtime_replay",
            require_clean_status=False,
        )
        contract_result = ContractResult(passed=True, checks=())
        round_num = self.increment_round()
        setattr(branch, "fresh_runtime_replay_step", True)
        try:
            if not verification_result.passed:
                decision = None
                protocol_result = None
                canary_result = None
                result = StepResult(
                    action="replay",
                    branch_id=bid,
                    reason="fresh runtime replay verification reuse invalid",
                    counts_toward_max_rounds=False,
                    attempt_kind="fresh_runtime_replay",
                    failure_stage="verification",
                    failure_detail=verification_result.first_failure,
                )
            else:
                decision, protocol_result, canary_result = self.evaluate(
                    branch,
                    workspace,
                    hypothesis,
                )
                finalizer_decision = decision or Decision.ABANDON
                result = self.apply_decision_and_finalize(
                    branch=branch,
                    decision=finalizer_decision,
                    hypothesis=hypothesis,
                    h_record=h_record,
                    protocol_result=protocol_result,
                    canary_result=canary_result,
                    contract_result=contract_result,
                    verification_result=verification_result,
                    action_label="fresh_runtime_replay",
                )
                result.action = "replay"
                if decision is None:
                    failure_stage, failure_detail = _eval_failure_detail(
                        protocol_result,
                        canary_result=canary_result,
                    )
                    result.decision = None
                    result.failure_stage = failure_stage or "evaluation"
                    result.failure_detail = failure_detail or "evaluation failed"
            result.counts_toward_max_rounds = False
            result.attempt_kind = "fresh_runtime_replay"
            _annotate_protocol_accounting(result, protocol_result)
            provenance = self.decision_provenance_for(bid)
            _attach_decision_provenance(result, provenance)
            closure = _fresh_runtime_replay_result_metadata(
                protocol_result,
                verification_result=verification_result,
                failure_detail=result.failure_detail,
            )
            audit_metadata = dict(result.scheduler_audit_metadata or {})
            audit_metadata["fresh_runtime_replay"] = closure
            result.scheduler_audit_metadata = audit_metadata
            self.record_step(
                StepRecord(
                    round_num=round_num,
                    branch_id=bid,
                    hypothesis=hypothesis,
                    patch=patch,
                    contract_passed=True,
                    verification_passed=verification_result.passed,
                    protocol_result=protocol_result,
                    decision=result.decision if decision is not None else None,
                    failure_stage=result.failure_stage,
                    failure_detail=result.failure_detail,
                    verification_detail=_verification_result_detail(
                        verification_result
                    ),
                    cache_stats=_protocol_cache_stats(protocol_result),
                    hypothesis_id=h_record.hypothesis_id,
                    decision_reason_codes=self.decision_reason_codes_for(
                        bid,
                        protocol_result,
                    ),
                    **provenance,
                    counts_toward_max_rounds=False,
                    attempt_kind="fresh_runtime_replay",
                )
            )
            return result
        finally:
            try:
                delattr(branch, "fresh_runtime_replay_step")
            except AttributeError:
                pass

    def run_reconcile_step(self, branch: Branch) -> StepResult:
        """Attempt to rebase a stale branch on the new champion."""
        bid = branch.branch_id
        patch = self.branch_patches.get(bid)
        h_record = self.branch_current_hypothesis.get(bid)

        def cleanup() -> None:
            if h_record is not None:
                try:
                    self.hypothesis_store.mark_status(h_record.hypothesis_id, "rejected")
                except Exception:
                    pass
                self.branch_current_hypothesis.pop(bid, None)

        def abandon_stale(reason: str) -> StepResult:
            cleanup()
            self.branch_controller.reconcile_stale(
                bid,
                success=False,
                new_champion=self.get_champion(),
            )
            self.persist_branch_state(bid)
            self.record_hard_abandon(bid, reason)
            return StepResult(
                action="reconcile",
                branch_id=bid,
                reason=reason,
                counts_toward_max_rounds=False,
                attempt_kind="reconcile_lifecycle",
            )

        if patch is None:
            logger.info("Branch %s: no patch to reconcile - abandoning stale branch", bid)
            return abandon_stale("no patch to reconcile")

        hypothesis = self.branch_hypotheses.get(bid)
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
            return abandon_stale(
                f"reconcile contract failed: {contract_result.failure_reason}"
            )

        workspace = self.setup_workspace(branch, force_champion=True)
        if workspace is None:
            return abandon_stale("workspace setup failed")

        try:
            applied = self.apply_patch(
                branch,
                workspace,
                patch,
                remember_patch=False,
            )
            code_hash = applied.code_hash
        except Exception as exc:
            logger.info("Branch %s: reconcile apply_patch failed: %s", bid, exc)
            return abandon_stale(f"apply_patch failed: {exc}")

        champion_workspace = self.get_champion().code_snapshot_path
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
            return abandon_stale(
                f"reconcile verification failed: {verification_result.first_failure}"
            )

        self.record_verification_pass(branch, code_hash)

        if self.experiment_protocol_provider() is None:
            logger.info(
                "Branch %s: no experiment protocol for reconcile re-screening - abandoning stale branch",
                bid,
            )
            return abandon_stale("no experiment protocol for re-screening")

        h_record = self.branch_current_hypothesis.get(bid)
        if hypothesis is None or h_record is None:
            logger.info(
                "Branch %s: missing hypothesis metadata for reconcile - abandoning stale branch",
                bid,
            )
            return abandon_stale("missing hypothesis metadata for reconcile")

        self.branch_controller.reconcile_stale(
            bid,
            success=True,
            new_champion=self.get_champion(),
        )
        self.persist_branch_state(bid)
        branch = self.branch_controller.get_branch(bid)
        if branch is None:
            return StepResult(
                action="reconcile",
                branch_id=bid,
                reason="branch disappeared after reconcile",
                counts_toward_max_rounds=False,
                attempt_kind="reconcile_lifecycle",
            )

        round_num = self.increment_round()
        self.increment_rounds_since_last_promote()
        setattr(branch, "reconcile_rescreening", True)
        try:
            decision, protocol_result, canary_result = self.evaluate(
                branch,
                workspace,
                hypothesis,
            )
        finally:
            try:
                delattr(branch, "reconcile_rescreening")
            except AttributeError:
                pass
        finalizer_decision = decision or Decision.ABANDON
        result = self.apply_decision_and_finalize(
            branch=branch,
            decision=finalizer_decision,
            hypothesis=hypothesis,
            h_record=h_record,
            protocol_result=protocol_result,
            canary_result=canary_result,
            contract_result=contract_result,
            verification_result=verification_result,
            action_label="reconcile",
        )
        _annotate_protocol_accounting(result, protocol_result)
        failure_stage, failure_detail = _eval_failure_detail(
            protocol_result,
            canary_result=canary_result,
        )
        if decision is None:
            result.decision = None
            result.failure_stage = failure_stage or "evaluation"
            result.failure_detail = failure_detail or "evaluation failed"
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
                counts_toward_max_rounds=result.counts_toward_max_rounds,
                attempt_kind=result.attempt_kind,
                repair_policy_reason=result.repair_policy_reason or None,
                repair_mechanism_ids=result.repair_mechanism_ids,
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
        self._reject_current_hypothesis(bid)
        self.branch_controller.apply_decision(branch.branch_id, Decision.ABANDON)
        self.persist_branch_state(branch.branch_id)
        self.record_hard_abandon(branch.branch_id, "eval_runtime_error")
        return StepResult(action="validate", branch_id=branch.branch_id, reason=str(exc))

    def _reject_current_hypothesis(self, branch_id: str) -> None:
        h_record = self.branch_current_hypothesis.get(branch_id)
        if h_record is not None:
            try:
                self.hypothesis_store.mark_status(h_record.hypothesis_id, "rejected")
            except Exception:
                pass
            self.branch_current_hypothesis.pop(branch_id, None)

    @staticmethod
    def _eval_action_label(branch: Branch) -> str:
        if branch.state == BranchState.EXPLORE_EXPAND:
            return "explore"
        if branch.state in (BranchState.VALIDATING, BranchState.VALIDATING_EXPAND):
            return "validate"
        return "frozen"


def _eval_failure_detail(
    protocol_result: Any | None,
    *,
    canary_result: Any | None = None,
) -> tuple[str | None, str | None]:
    if protocol_result is None:
        return None, None
    reason_codes = {
        str(code).lower()
        for code in getattr(protocol_result, "reason_codes", ()) or ()
    }
    if "evaluation_failed" in reason_codes:
        detail = str(getattr(canary_result, "reason", "") or "evaluation failed")
        return "evaluation", detail
    if FROZEN_BUDGET_EXHAUSTED in reason_codes:
        return "frozen_budget", FROZEN_BUDGET_EXHAUSTED
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
    formal_evaluated = (
        getattr(protocol_result, "stats", None) is not None
        and screened_experiment_effective(protocol_result)
    )
    result.protocol_stage = stage  # type: ignore[assignment]
    result.formal_protocol_evaluated = formal_evaluated
    result.screened_experiment_effective = stage == "screening" and formal_evaluated


def _screening_verification_reuse_result(
    branch: Branch,
    *,
    action_label: str,
    require_clean_status: bool = True,
) -> VerificationResult:
    current_hash = getattr(branch, "current_code_hash", None)
    last_clean_hash = getattr(branch, "last_clean_code_hash", None)
    code_status = str(getattr(branch, "branch_code_status", "clean") or "clean")
    hash_available = bool(current_hash) and bool(last_clean_hash)
    matches_verified_hash = (
        hash_available
        and current_hash == last_clean_hash
        and (code_status == "clean" or not require_clean_status)
    )
    reuse_allowed = matches_verified_hash or not (current_hash or last_clean_hash)
    source_detail = (
        "screening/reconcile VerificationGate pass for "
        f"code_hash={last_clean_hash or 'missing'}"
    )
    metadata: dict[str, Any] = {
        "verification_reused_from_screening": True,
        "verification_reuse_stage": action_label,
        "verification_reuse_source": "screening_or_reconcile",
        "original_verification_audit_detail": source_detail,
        "current_code_hash": current_hash,
        "last_clean_code_hash": last_clean_hash,
        "branch_code_status": code_status,
        "verification_reuse_requires_clean_status": require_clean_status,
        "verification_reuse_hash_available": hash_available,
        "current_matches_original_verification": matches_verified_hash,
        "strict_checks_rerun": False,
    }
    audit_hash_payload = json.dumps(metadata, sort_keys=True, default=str)
    metadata["original_verification_audit_hash"] = hashlib.sha256(
        audit_hash_payload.encode("utf-8")
    ).hexdigest()[:16]
    if reuse_allowed:
        detail = (
            f"{action_label} reuses prior screening/reconcile verification; "
            "V1-V9 were not rerun for this eval step; "
            f"original_verification_audit_hash="
            f"{metadata['original_verification_audit_hash']}"
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
        "current code hash/status does not match the last verified clean hash"
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


def _fresh_runtime_replay_result_metadata(
    protocol_result: Any | None,
    *,
    verification_result: VerificationResult,
    failure_detail: str | None,
) -> dict[str, Any]:
    cache_stats = _protocol_cache_stats(protocol_result) or {}
    status = (
        "verification_reuse_failed"
        if not verification_result.passed
        else "evaluation_failed"
        if protocol_result is None
        else "fresh_evidence_recorded"
        if cache_stats.get("champion_cached_runtime_pairs", 0) == 0
        else "capped_reject_still_cached_or_incomplete"
    )
    runtime_status = str(
        getattr(protocol_result, "runtime_evidence_status", "") or "unknown"
    )
    if runtime_status in {"fresh_champion_required", "fresh_required"}:
        status = "capped_reject_fresh_champion_still_required"
    return {
        "schema_version": "fresh_runtime_replay.v1",
        "closure_status": status,
        "counts_toward_max_rounds": False,
        "decision_features_excluded": True,
        "protocol_stage": str(
            getattr(getattr(protocol_result, "stage", ""), "value", "")
            or getattr(protocol_result, "stage", "")
            or ""
        ),
        "runtime_evidence_status": runtime_status,
        "runtime_evidence_confidence": str(
            getattr(protocol_result, "runtime_confidence", "") or "unknown"
        ),
        "cache_stats": cache_stats,
        "failure_detail": failure_detail or "",
        "reason_codes": [
            str(code)
            for code in getattr(protocol_result, "reason_codes", ()) or ()
            if str(code)
        ],
    }


def _fresh_runtime_pressure_without_replayable_candidate(
    branches: Any,
    *,
    branch_workspaces: Mapping[str, str] | None = None,
    branch_hypotheses: Mapping[str, HypothesisProposal] | None = None,
    branch_current_hypothesis: Mapping[str, HypothesisRecord] | None = None,
    branch_patches: Mapping[str, PatchProposal] | None = None,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for branch in branches or ():
        summary = getattr(branch, "branch_evidence_summary", {}) or {}
        if not isinstance(summary, Mapping):
            continue
        marker = summary.get("fresh_runtime_followup")
        marker_payload = marker if isinstance(marker, Mapping) else {}
        scheduler_marker = str(marker_payload.get("scheduler_marker") or "")
        pending_marker = (
            bool(marker_payload.get("fresh_runtime_pending"))
            and scheduler_marker == "fresh_champion_runtime_replay_pending"
        )
        state = getattr(branch, "state", "")
        state_value = str(getattr(state, "value", state) or "")
        if pending_marker and state_value == BranchState.EXPLORE.value:
            continue
        reason_codes = _summary_reason_codes(summary)
        runtime_status = str(summary.get("runtime_evidence_status") or "").lower()
        fresh_required = (
            bool(summary.get("fresh_runtime_required"))
            or bool(marker_payload.get("fresh_runtime_required"))
            or bool(marker_payload.get("followup_required"))
            or runtime_status in {"fresh_champion_required", "fresh_required"}
            or "RUNTIME_TIE_FRESH_CHAMPION_REQUIRED" in reason_codes
            or "RUNTIME_EVIDENCE_FRESH_CHAMPION_REQUIRED" in reason_codes
        )
        if not fresh_required:
            continue
        materialization = _fresh_runtime_replay_materialization_diagnostic(
            branch,
            branch_workspaces=branch_workspaces,
            branch_hypotheses=branch_hypotheses,
            branch_current_hypothesis=branch_current_hypothesis,
            branch_patches=branch_patches,
        )
        candidates.append(
            {
                "branch_id": getattr(branch, "branch_id", None),
                "branch_state": state_value,
                "branch_code_status": str(
                    getattr(branch, "branch_code_status", "") or ""
                ),
                "screening_tier": str(
                    getattr(branch, "last_screening_feedback_tier", "") or ""
                ),
                "runtime_evidence_status": runtime_status or "unknown",
                "fresh_runtime_required": True,
                "fresh_runtime_pending": bool(
                    summary.get("fresh_runtime_pending")
                    or marker_payload.get("fresh_runtime_pending")
                ),
                "scheduler_marker": scheduler_marker,
                "runtime_evidence_pressure_count": _nonnegative_int(
                    summary.get("runtime_evidence_pressure_count")
                ),
                "replay_materializable": not bool(
                    materialization["missing_materialization_keys"]
                ),
                "missing_materialization_keys": list(
                    materialization["missing_materialization_keys"]
                ),
                "missing_replay_identity_keys": list(
                    materialization["missing_replay_identity_keys"]
                ),
                "replay_identity_status": materialization["replay_identity_status"],
                "protocol_stage": materialization["protocol_stage"],
                "candidate_code_hash": materialization["candidate_code_hash"],
                "formal_candidate_artifact_status": str(
                    summary.get("formal_candidate_artifact_status") or ""
                ),
                "artifact_omitted_reason": str(
                    summary.get("artifact_omitted_reason") or ""
                ),
                "non_replayable_reason": _summary_non_replayable_reason(
                    summary,
                    marker_payload,
                ),
            }
        )
    return candidates


def _mark_non_materializable_fresh_runtime_candidates(
    branches: Any,
    *,
    branch_workspaces: Mapping[str, str],
    branch_hypotheses: Mapping[str, HypothesisProposal],
    branch_current_hypothesis: Mapping[str, HypothesisRecord],
    branch_patches: Mapping[str, PatchProposal],
) -> list[dict[str, Any]]:
    marked: list[dict[str, Any]] = []
    for branch in branches or ():
        summary = (
            dict(getattr(branch, "branch_evidence_summary", {}) or {})
            if isinstance(getattr(branch, "branch_evidence_summary", None), Mapping)
            else {}
        )
        if not summary:
            continue
        marker = summary.get("fresh_runtime_followup")
        marker_payload = dict(marker) if isinstance(marker, Mapping) else {}
        if not _summary_fresh_runtime_required(summary, marker_payload):
            continue
        state = getattr(branch, "state", "")
        if str(getattr(state, "value", state) or "") != BranchState.EXPLORE.value:
            continue
        materialization = _fresh_runtime_replay_materialization_diagnostic(
            branch,
            branch_workspaces=branch_workspaces,
            branch_hypotheses=branch_hypotheses,
            branch_current_hypothesis=branch_current_hypothesis,
            branch_patches=branch_patches,
        )
        if not materialization["missing_materialization_keys"]:
            continue
        reason = _fresh_runtime_non_replayable_reason(summary, materialization)
        non_replayable = {
            "schema_version": "fresh_runtime_non_replayable.v1",
            "reason": reason,
            "missing_materialization_keys": list(
                materialization["missing_materialization_keys"]
            ),
            "missing_replay_identity_keys": list(
                materialization["missing_replay_identity_keys"]
            ),
            "replay_identity_status": materialization["replay_identity_status"],
            "protocol_stage": materialization["protocol_stage"],
            "candidate_code_hash": materialization["candidate_code_hash"],
            "artifact_omitted_reason": str(
                summary.get("artifact_omitted_reason") or ""
            ),
            "decision_features_excluded": True,
        }
        if summary.get("fresh_runtime_non_replayable") == non_replayable:
            continue
        marker_payload.update(
            {
                "schema_version": "fresh_runtime_followup.v1",
                "queue_intent": "fresh_champion_runtime_replay",
                "scheduler_marker": "fresh_champion_runtime_replay_non_replayable",
                "trigger": marker_payload.get("trigger")
                or "fresh_runtime_required",
                "fresh_runtime_pending": False,
                "fresh_runtime_required": True,
                "followup_recommended": True,
                "followup_required": True,
                "non_replayable": True,
                "non_replayable_reason": reason,
                "replay_materialization": {
                    "schema_version": "fresh_runtime_materialization.v1",
                    "materializable": False,
                    **non_replayable,
                },
                "decision_features_excluded": True,
            }
        )
        summary["fresh_runtime_followup"] = marker_payload
        summary["fresh_runtime_pending"] = False
        summary["fresh_runtime_required"] = True
        summary["fresh_runtime_non_replayable"] = non_replayable
        summary["non_replayable"] = True
        summary["non_replayable_reason"] = reason
        branch.branch_evidence_summary = summary
        marked.append(
            {
                "branch_id": getattr(branch, "branch_id", None),
                "reason": reason,
                "missing_materialization_keys": list(
                    materialization["missing_materialization_keys"]
                ),
                "missing_replay_identity_keys": list(
                    materialization["missing_replay_identity_keys"]
                ),
                "replay_identity_status": materialization[
                    "replay_identity_status"
                ],
                "artifact_omitted_reason": str(
                    summary.get("artifact_omitted_reason") or ""
                ),
                "decision_features_excluded": True,
            }
        )
    return marked


def _materialize_fresh_runtime_pending_markers(
    branches: Any,
    *,
    branch_workspaces: Mapping[str, str],
    branch_hypotheses: Mapping[str, HypothesisProposal],
    branch_current_hypothesis: Mapping[str, HypothesisRecord],
    branch_patches: Mapping[str, PatchProposal],
) -> list[dict[str, Any]]:
    materialized: list[dict[str, Any]] = []
    for branch in branches or ():
        summary = (
            dict(getattr(branch, "branch_evidence_summary", {}) or {})
            if isinstance(getattr(branch, "branch_evidence_summary", None), Mapping)
            else {}
        )
        if not summary:
            continue
        marker = summary.get("fresh_runtime_followup")
        marker_payload = dict(marker) if isinstance(marker, Mapping) else {}
        if (
            bool(marker_payload.get("fresh_runtime_pending"))
            and str(marker_payload.get("scheduler_marker") or "")
            == "fresh_champion_runtime_replay_pending"
        ):
            continue
        if not _summary_fresh_runtime_required(summary, marker_payload):
            continue
        state = getattr(branch, "state", "")
        if str(getattr(state, "value", state) or "") != BranchState.EXPLORE.value:
            continue
        materialization = _fresh_runtime_replay_materialization_diagnostic(
            branch,
            branch_workspaces=branch_workspaces,
            branch_hypotheses=branch_hypotheses,
            branch_current_hypothesis=branch_current_hypothesis,
            branch_patches=branch_patches,
        )
        if materialization["missing_materialization_keys"]:
            continue
        marker_payload.update(
            {
                "schema_version": "fresh_runtime_followup.v1",
                "queue_intent": "fresh_champion_runtime_replay",
                "scheduler_marker": "fresh_champion_runtime_replay_pending",
                "trigger": marker_payload.get("trigger")
                or "fresh_runtime_required",
                "fresh_runtime_pending": True,
                "fresh_runtime_required": True,
                "followup_recommended": True,
                "followup_required": True,
                "counts_toward_max_rounds": False,
                "decision_features_excluded": True,
                "replay_materialization": {
                    "schema_version": "fresh_runtime_materialization.v1",
                    "materializable": True,
                    "candidate_code_hash": materialization["candidate_code_hash"],
                    "protocol_stage": materialization["protocol_stage"],
                    "replay_identity_status": (
                        materialization["replay_identity_status"]
                    ),
                    "decision_features_excluded": True,
                },
            }
        )
        summary["fresh_runtime_followup"] = marker_payload
        summary["fresh_runtime_pending"] = True
        summary["fresh_runtime_required"] = True
        summary.pop("fresh_runtime_non_replayable", None)
        if str(summary.get("non_replayable_reason") or "").startswith(
            "fresh_runtime_replay:"
        ):
            summary.pop("non_replayable_reason", None)
            summary.pop("non_replayable", None)
        branch.branch_evidence_summary = summary
        materialized.append(
            {
                "branch_id": getattr(branch, "branch_id", None),
                "scheduler_marker": "fresh_champion_runtime_replay_pending",
                "candidate_code_hash": materialization["candidate_code_hash"],
                "protocol_stage": materialization["protocol_stage"],
                "replay_identity_status": materialization["replay_identity_status"],
                "counts_toward_max_rounds": False,
                "decision_features_excluded": True,
            }
        )
    return materialized


def _materializable_fresh_runtime_pending_branch(
    branches: Any,
    *,
    branch_workspaces: Mapping[str, str],
    branch_hypotheses: Mapping[str, HypothesisProposal],
    branch_current_hypothesis: Mapping[str, HypothesisRecord],
    branch_patches: Mapping[str, PatchProposal],
) -> Branch | None:
    for branch in branches or ():
        summary = getattr(branch, "branch_evidence_summary", {}) or {}
        marker = (
            summary.get("fresh_runtime_followup")
            if isinstance(summary, Mapping)
            else {}
        )
        if not isinstance(marker, Mapping):
            continue
        state = getattr(branch, "state", "")
        if str(getattr(state, "value", state) or "") != BranchState.EXPLORE.value:
            continue
        if not (
            bool(marker.get("fresh_runtime_pending"))
            and str(marker.get("scheduler_marker") or "")
            == "fresh_champion_runtime_replay_pending"
        ):
            continue
        materialization = _fresh_runtime_replay_materialization_diagnostic(
            branch,
            branch_workspaces=branch_workspaces,
            branch_hypotheses=branch_hypotheses,
            branch_current_hypothesis=branch_current_hypothesis,
            branch_patches=branch_patches,
        )
        if not materialization["missing_materialization_keys"]:
            return branch
    return None


def _summary_fresh_runtime_required(
    summary: Mapping[str, Any],
    marker_payload: Mapping[str, Any],
) -> bool:
    reason_codes = _summary_reason_codes(summary)
    runtime_status = str(summary.get("runtime_evidence_status") or "").lower()
    return bool(
        summary.get("fresh_runtime_required")
        or marker_payload.get("fresh_runtime_required")
        or marker_payload.get("followup_required")
        or runtime_status in {"fresh_champion_required", "fresh_required"}
        or "RUNTIME_TIE_FRESH_CHAMPION_REQUIRED" in reason_codes
        or "RUNTIME_EVIDENCE_FRESH_CHAMPION_REQUIRED" in reason_codes
    )


def _fresh_runtime_non_replayable_reason(
    summary: Mapping[str, Any],
    materialization: Mapping[str, Any],
) -> str:
    artifact_omitted_reason = str(summary.get("artifact_omitted_reason") or "")
    if artifact_omitted_reason:
        return f"formal_candidate_artifact_omitted:{artifact_omitted_reason}"
    if materialization.get("missing_replay_identity_keys"):
        return "fresh_runtime_replay:missing_replay_identity"
    return "fresh_runtime_replay:missing_materialization_state"


def _summary_non_replayable_reason(
    summary: Mapping[str, Any],
    marker_payload: Mapping[str, Any],
) -> str:
    for value in (
        summary.get("non_replayable_reason"),
        marker_payload.get("non_replayable_reason"),
    ):
        text = str(value or "").strip()
        if text:
            return text
    non_replayable = summary.get("fresh_runtime_non_replayable")
    if isinstance(non_replayable, Mapping):
        return str(non_replayable.get("reason") or "")
    return ""


def _fresh_runtime_replay_materialization_diagnostic(
    branch: Branch,
    *,
    branch_workspaces: Mapping[str, str] | None,
    branch_hypotheses: Mapping[str, HypothesisProposal] | None,
    branch_current_hypothesis: Mapping[str, HypothesisRecord] | None,
    branch_patches: Mapping[str, PatchProposal] | None,
) -> dict[str, Any]:
    bid = str(getattr(branch, "branch_id", "") or "")
    summary = getattr(branch, "branch_evidence_summary", {}) or {}
    evidence = summary if isinstance(summary, Mapping) else {}
    missing: list[str] = []
    if branch_workspaces is not None and not branch_workspaces.get(bid):
        missing.append("candidate_workspace")
    if branch_hypotheses is not None and branch_hypotheses.get(bid) is None:
        missing.append("hypothesis")
    if (
        branch_current_hypothesis is not None
        and branch_current_hypothesis.get(bid) is None
    ):
        missing.append("hypothesis_record")
    if branch_patches is not None and branch_patches.get(bid) is None:
        missing.append("patch")
    candidate_code_hash = _candidate_code_hash(branch, evidence)
    if not candidate_code_hash:
        missing.append("candidate_hash")
    protocol_stage = _summary_protocol_stage(evidence)
    if not protocol_stage:
        missing.append("protocol_stage")
    replay_identity = _summary_replay_identity(evidence)
    missing_identity_keys = _missing_replay_identity_keys(replay_identity)
    if replay_identity is None:
        missing.append("replay_identity")
    else:
        missing.extend(
            f"replay_identity.{key}" for key in missing_identity_keys
        )
    return {
        "missing_materialization_keys": list(dict.fromkeys(missing)),
        "missing_replay_identity_keys": missing_identity_keys,
        "replay_identity_status": (
            str(
                replay_identity.get("identity_status")
                or replay_identity.get("status")
                or "complete"
            )
            if replay_identity is not None and not missing_identity_keys
            else "missing"
            if replay_identity is None
            else "degraded"
        ),
        "protocol_stage": protocol_stage,
        "candidate_code_hash": candidate_code_hash,
    }


def _candidate_code_hash(branch: Branch, summary: Mapping[str, Any]) -> str:
    for value in (
        getattr(branch, "current_code_hash", None),
        summary.get("candidate_code_hash"),
        summary.get("code_hash"),
        summary.get("current_code_hash"),
        getattr(branch, "last_clean_code_hash", None),
        summary.get("last_clean_code_hash"),
    ):
        text = str(value or "").strip()
        if text and text != "unknown":
            return text
    return ""


def _summary_protocol_stage(summary: Mapping[str, Any]) -> str:
    for value in (
        summary.get("protocol_stage"),
        summary.get("stage"),
        summary.get("experiment_stage"),
    ):
        text = str(getattr(value, "value", value) or "").strip()
        if text and text != "unknown":
            return text
    return ""


def _summary_replay_identity(summary: Mapping[str, Any]) -> Mapping[str, Any] | None:
    for key in (
        "replay_identity",
        "formal_replay_identity",
        "candidate_replay_identity",
    ):
        value = summary.get(key)
        if isinstance(value, Mapping):
            return value
    metadata = summary.get("replay_metadata")
    if isinstance(metadata, Mapping):
        value = metadata.get("replay_identity")
        if isinstance(value, Mapping):
            return value
    marker = summary.get("fresh_runtime_followup")
    if isinstance(marker, Mapping):
        value = marker.get("replay_identity")
        if isinstance(value, Mapping):
            return value
    return None


def _missing_replay_identity_keys(
    replay_identity: Mapping[str, Any] | None,
) -> list[str]:
    return formal_replay_identity_missing_keys(
        dict(replay_identity) if replay_identity is not None else None
    )


def _aggregate_missing_materialization_keys(
    candidates: list[dict[str, Any]],
) -> list[str]:
    keys: list[str] = []
    for candidate in candidates:
        value = candidate.get("missing_materialization_keys")
        if isinstance(value, str):
            keys.append(value)
        elif isinstance(value, (list, tuple, set)):
            keys.extend(str(item) for item in value if str(item))
    return list(dict.fromkeys(keys))


def _summary_reason_codes(summary: Mapping[str, Any]) -> set[str]:
    values: list[Any] = []
    for key in (
        "reason_codes",
        "decision_reason_codes",
        "why_not_promoted_reason_codes",
        "gate_observation_reason_codes",
    ):
        value = summary.get(key)
        if isinstance(value, str):
            values.append(value)
        elif isinstance(value, (list, tuple, set)):
            values.extend(value)
    return {str(value).strip().upper() for value in values if str(value).strip()}


def _nonnegative_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _fresh_runtime_replay_materialization_block(
    branch: Branch,
    *,
    missing_live_state: list[str],
) -> dict[str, Any]:
    summary = getattr(branch, "branch_evidence_summary", {}) or {}
    if not isinstance(summary, Mapping):
        summary = {}
    materialization = _fresh_runtime_replay_materialization_diagnostic(
        branch,
        branch_workspaces=None,
        branch_hypotheses=None,
        branch_current_hypothesis=None,
        branch_patches=None,
    )
    artifact_ref = str(summary.get("formal_candidate_patch_artifact_ref") or "")
    if artifact_ref:
        return {
            "closure_status": "blocked_missing_replay_materialization",
            "detail": (
                "fresh runtime replay missing live "
                + ",".join(missing_live_state)
                + "; formal_candidate_patch_artifact_ref present but replay "
                + f"materialization is unavailable: {artifact_ref}"
            ),
            "metadata": {
                "formal_candidate_patch_artifact_ref": artifact_ref,
                "missing_live_state": list(missing_live_state),
                "missing_materialization_keys": list(
                    materialization["missing_materialization_keys"]
                ),
                "missing_replay_identity_keys": list(
                    materialization["missing_replay_identity_keys"]
                ),
                "replay_identity_status": materialization[
                    "replay_identity_status"
                ],
                "protocol_stage": materialization["protocol_stage"],
                "candidate_code_hash": materialization["candidate_code_hash"],
                "missing_replay_materialization": [
                    "workspace_from_formal_candidate_patch_artifact",
                    "hypothesis_from_candidate_metadata_or_store",
                    "hypothesis_record_from_candidate_metadata_or_store",
                    "patch_from_candidate_patch_json",
                ],
                "decision_features_excluded": True,
            },
        }
    return {
        "closure_status": "blocked_missing_candidate_state",
        "detail": "fresh runtime replay missing " + ",".join(missing_live_state),
        "metadata": {
            "missing_live_state": list(missing_live_state),
            "missing_materialization_keys": list(
                materialization["missing_materialization_keys"]
            ),
            "missing_replay_identity_keys": list(
                materialization["missing_replay_identity_keys"]
            ),
            "replay_identity_status": materialization["replay_identity_status"],
            "protocol_stage": materialization["protocol_stage"],
            "candidate_code_hash": materialization["candidate_code_hash"],
            "decision_features_excluded": True,
        },
    }


def _close_fresh_runtime_replay_marker(
    branch: Branch,
    *,
    closure_status: str,
    detail: str = "",
) -> None:
    summary = (
        dict(getattr(branch, "branch_evidence_summary", {}) or {})
        if isinstance(getattr(branch, "branch_evidence_summary", None), Mapping)
        else {}
    )
    marker = summary.get("fresh_runtime_followup")
    marker_payload = dict(marker) if isinstance(marker, Mapping) else {}
    marker_payload.update(
        {
            "fresh_runtime_pending": False,
            "scheduler_marker": "fresh_champion_runtime_replay_closed",
            "closure_status": closure_status,
            "detail": detail,
            "decision_features_excluded": True,
        }
    )
    summary["fresh_runtime_followup"] = marker_payload
    summary["fresh_runtime_pending"] = False
    summary["fresh_runtime_replay_closure"] = {
        "schema_version": "fresh_runtime_replay_closure.v1",
        "closure_status": closure_status,
        "detail": detail,
        "decision_features_excluded": True,
    }
    branch.branch_evidence_summary = summary


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
    if result.scheduler_slot:
        audit_metadata.setdefault(
            "scheduler_slot_semantics",
            "pre_finalizer_scheduler_preference",
        )
    aligned_reason = _scheduler_aligned_result_reason(
        result.reason,
        actual_branch_action=(
            "explore_new_clean_fork"
            if (
                scheduler_action == "create_new"
                and result.scheduler_slot == "explore_new"
            )
            else ""
        ),
        scheduler_slot=result.scheduler_slot,
    )
    if scheduler_action == "create_new" and result.scheduler_slot == "explore_new":
        audit_metadata.update(
            {
                "clean_fork_selected": True,
                "clean_fork_reason": result.scheduler_reason,
                "same_branch_refinement_not_selected_reason": (
                    result.scheduler_reason
                    or "scheduler_selected_clean_exploration_branch"
                ),
                "actual_branch_action": "explore_new_clean_fork",
                "post_finalizer_actual_branch_action": "explore_new_clean_fork",
                "post_finalizer_next_proposal_policy": "clean_fork_selected",
            }
        )
    elif (
        scheduler_action in {"run_existing", "replay_existing"}
        and scheduled_branch is not None
    ):
        branch_id = str(
            getattr(scheduled_branch, "branch_id", "") or result.branch_id or ""
        )
        actual_action = _post_finalizer_actual_branch_action(
            result,
            scheduled_branch,
        )
        post_metadata = _post_finalizer_branch_metadata(
            scheduled_branch,
            actual_branch_action=actual_action,
        )
        audit_metadata.update(
            {
                "same_branch_refinement_selected": (
                    actual_action == "continue_same_branch"
                    and scheduler_action == "run_existing"
                ),
                "pre_finalizer_same_branch_refinement_selected": (
                    scheduler_action == "run_existing"
                ),
                "fresh_runtime_replay_selected": (
                    scheduler_action == "replay_existing"
                ),
                "refined_branch_id": branch_id,
                "actual_branch_action": actual_action,
                "post_finalizer_actual_branch_action": actual_action,
                **post_metadata,
            }
        )
        aligned_reason = _scheduler_aligned_result_reason(
            result.reason,
            actual_branch_action=actual_action,
            scheduler_slot=result.scheduler_slot,
        )
        if result.action == "soft_abandon":
            audit_metadata["post_refine_abandon_reason"] = aligned_reason
        elif actual_action != "continue_same_branch":
            audit_metadata["post_refine_release_reason"] = aligned_reason
        else:
            audit_metadata["post_refine_decision_reason"] = aligned_reason
    audit_metadata.setdefault(
        "same_mechanism_clean_fork_justification",
        _same_mechanism_clean_fork_justification(audit_metadata),
    )
    result.scheduler_audit_metadata = audit_metadata
    result.reason = aligned_reason
    return result


def _same_mechanism_clean_fork_justification(
    audit_metadata: dict[str, Any],
) -> dict[str, Any]:
    selected_policy = str(
        audit_metadata.get("post_finalizer_next_proposal_policy")
        or audit_metadata.get("scheduler_action")
        or ""
    )
    clean_fork_selected = bool(audit_metadata.get("clean_fork_selected"))
    not_selected_reason = str(
        audit_metadata.get("same_branch_refinement_not_selected_reason") or ""
    )
    clean_fork_reason = str(audit_metadata.get("clean_fork_reason") or "")
    active_branch_cap_context = {
        "scheduler_slot": str(
            audit_metadata.get("pre_finalizer_scheduler_slot")
            or audit_metadata.get("scheduler_slot")
            or ""
        ),
        "scheduler_reason": str(
            audit_metadata.get("pre_finalizer_scheduler_reason")
            or audit_metadata.get("scheduler_reason")
            or ""
        ),
        "pre_finalizer_scheduler_action": str(
            audit_metadata.get("pre_finalizer_scheduler_action")
            or audit_metadata.get("scheduler_action")
            or ""
        ),
    }
    active_slot_hard_cap = audit_metadata.get("active_slot_hard_cap")
    if isinstance(active_slot_hard_cap, dict):
        active_branch_cap_context["active_slot_hard_cap"] = dict(
            active_slot_hard_cap
        )
    active_slot_reconciliation = audit_metadata.get("active_slot_reconciliation")
    if isinstance(active_slot_reconciliation, dict):
        active_branch_cap_context["active_slot_reconciliation"] = dict(
            active_slot_reconciliation
        )
    if not clean_fork_selected:
        reason = "not_applicable"
    elif not_selected_reason == "clean_fork_required_for_new_mechanism":
        reason = "new_mechanism_requires_clean_fork"
    elif not_selected_reason:
        reason = "clean_fork_selected_instead_of_same_branch"
    else:
        reason = "no_active_same_mechanism_branch"
    return {
        "reason": reason,
        "selected_policy": selected_policy,
        "clean_fork_reason": clean_fork_reason,
        "same_branch_refinement_not_selected_reason": not_selected_reason,
        "active_branch_cap_context": active_branch_cap_context,
    }


def _post_finalizer_actual_branch_action(
    result: StepResult,
    branch: Branch,
) -> str:
    if result.action == "soft_abandon":
        return "soft_abandon"
    release_reason = branch_active_slot_release_reason(branch)
    if release_reason:
        return f"{release_reason}_released"
    if not branch_counts_toward_active_slots(branch):
        return "inactive_after_finalizer"
    return "continue_same_branch"


def _post_finalizer_branch_metadata(
    branch: Branch,
    *,
    actual_branch_action: str,
) -> dict[str, Any]:
    release_reason = branch_active_slot_release_reason(branch)
    counts_toward_active_slots = branch_counts_toward_active_slots(branch)
    metadata: dict[str, Any] = {
        "post_finalizer_branch_id": str(getattr(branch, "branch_id", "") or ""),
        "post_finalizer_branch_state": _branch_state_value(branch),
        "post_finalizer_branch_code_status": str(
            getattr(branch, "branch_code_status", "") or ""
        ),
        "post_finalizer_counts_toward_active_slots": counts_toward_active_slots,
        "post_finalizer_next_proposal_policy": (
            "same_branch_eligible"
            if actual_branch_action == "continue_same_branch"
            else "same_branch_not_selected"
            if actual_branch_action == "soft_abandon"
            else "clean_fork_or_other_branch_required"
        ),
    }
    if release_reason:
        metadata["post_finalizer_active_slot_release_reason"] = release_reason
    lifecycle_action = _post_finalizer_lifecycle_action(
        branch,
        release_reason=release_reason,
    )
    if lifecycle_action:
        metadata["post_finalizer_lifecycle_action"] = lifecycle_action
    lifecycle_codes = _branch_lifecycle_action_reason_codes(branch)
    if lifecycle_codes:
        metadata["post_finalizer_lifecycle_action_reason_codes"] = list(
            lifecycle_codes
        )
    return metadata


def _post_finalizer_lifecycle_action(
    branch: Branch,
    *,
    release_reason: str,
) -> str:
    reason_set = set(_branch_lifecycle_action_reason_codes(branch))
    if BRANCH_LIFECYCLE_ARCHIVE_LINEAGE in reason_set:
        return "archive_lineage"
    if BRANCH_LIFECYCLE_PARK_LINEAGE in reason_set:
        return "park_lineage"
    if BRANCH_LIFECYCLE_ROLLBACK_TO_CHECKPOINT in reason_set:
        return "rollback_to_checkpoint"
    if BRANCH_LIFECYCLE_RETAIN_CHECKPOINT in reason_set:
        return "retain_checkpoint"
    if release_reason == "parked_lineage":
        return "park_lineage"
    if release_reason == "retained_checkpoint_no_effect_current_head":
        return "retain_checkpoint"
    return ""


def _branch_lifecycle_action_reason_codes(branch: Branch) -> tuple[str, ...]:
    block = getattr(branch, "last_branch_lifecycle_policy_block", {}) or {}
    if not isinstance(block, dict):
        return ()
    codes = block.get("lifecycle_action_reason_codes")
    if isinstance(codes, str):
        return (codes,) if codes else ()
    if not isinstance(codes, (list, tuple, set)):
        return ()
    return tuple(dict.fromkeys(str(code) for code in codes if str(code)))


def _branch_state_value(branch: Branch) -> str:
    state = getattr(branch, "state", "")
    return str(getattr(state, "value", state) or "")


def _scheduler_aligned_result_reason(
    reason: str,
    *,
    actual_branch_action: str,
    scheduler_slot: str,
) -> str:
    text = str(reason or "")
    stale_phrase = "improve the same branch"
    if stale_phrase not in text:
        return text
    if actual_branch_action == "explore_new_clean_fork":
        replacement = "create a clean fork"
    elif actual_branch_action.endswith("_released"):
        replacement = "release the branch slot"
    elif scheduler_slot == "repair_diagnostic":
        replacement = "repair/refine the same branch"
    else:
        replacement = "refine the same branch"
    return text.replace(stale_phrase, replacement)


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


def _attach_material_difference_requirement_metadata(
    branch: Branch,
    scheduler_audit: Any,
) -> None:
    if not isinstance(scheduler_audit, Mapping):
        return
    requirement = scheduler_audit.get("material_difference_requirement")
    if not isinstance(requirement, Mapping):
        return
    summary = dict(getattr(branch, "branch_evidence_summary", {}) or {})
    record = copy.deepcopy(dict(requirement))
    summary["material_difference_required"] = True
    summary["material_difference_required_for"] = str(
        record.get("required_for")
        or scheduler_audit.get("material_difference_required_for")
        or "unspecified"
    )
    summary["material_difference_requirement"] = record
    records = [
        copy.deepcopy(dict(item))
        for item in summary.get("material_difference_audit_records", []) or []
        if isinstance(item, Mapping)
    ]
    record_id = str(record.get("record_id") or "")
    if not any(str(item.get("record_id") or "") == record_id for item in records):
        records.append(copy.deepcopy(record))
    summary["material_difference_audit_records"] = records
    candidates = _material_difference_requirement_candidates(scheduler_audit)
    if candidates:
        summary["material_difference_requirement_candidates"] = candidates
    branch.branch_evidence_summary = summary


def _material_difference_requirement_candidates(
    scheduler_audit: Mapping[str, Any],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for key in (
        "low_value_clean_fork_material_difference_candidates",
        "plateau_gate_clean_fork_candidates",
        "low_value_active_slot_release_candidates",
    ):
        values = scheduler_audit.get(key)
        if not isinstance(values, list):
            continue
        for value in values:
            if not isinstance(value, Mapping):
                continue
            item = _material_difference_candidate_summary(value, source_key=key)
            if not item:
                continue
            dedupe_key = (
                str(item.get("branch_id") or ""),
                str(
                    item.get("release_reason")
                    or item.get("scheduler_preference")
                    or ""
                ),
            )
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            candidates.append(item)
    return candidates


def _attach_decision_provenance(
    result: StepResult,
    provenance: Mapping[str, Any],
) -> None:
    for key in (
        "decision_layer_source",
        "decision_engine_reason_codes",
        "diagnostic_reason_codes",
        "bypass_reason_codes",
        "lifecycle_reason_codes",
    ):
        if key in provenance:
            setattr(result, key, provenance[key])


def _material_difference_candidate_summary(
    candidate: Mapping[str, Any],
    *,
    source_key: str,
) -> dict[str, Any]:
    return {
        key: value
        for key, value in {
            "branch_id": str(candidate.get("branch_id") or "").strip(),
            "release_reason": str(candidate.get("release_reason") or "").strip(),
            "scheduler_preference": str(
                candidate.get("scheduler_preference") or ""
            ).strip(),
            "lineage_status": str(candidate.get("lineage_status") or "").strip(),
            "branch_state": str(candidate.get("branch_state") or "").strip(),
            "branch_code_status": str(
                candidate.get("branch_code_status") or ""
            ).strip(),
            "screening_tier": str(candidate.get("screening_tier") or "").strip(),
            "candidate_source": source_key,
        }.items()
        if value not in ("", None, [], {}, ())
    }
