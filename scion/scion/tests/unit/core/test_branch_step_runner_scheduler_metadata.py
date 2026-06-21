from __future__ import annotations

from contextlib import nullcontext
from types import SimpleNamespace
from typing import Callable

from scion.core.branch import BranchController
from scion.core.branch_step_runner import BranchStepRunner
from scion.core.branch_lifecycle_policy import (
    BRANCH_LIFECYCLE_PARK_LINEAGE,
    BRANCH_LIFECYCLE_RETAIN_CHECKPOINT,
)
from scion.core.models import (
    Branch,
    BranchState,
    CanaryResult,
    ChampionState,
    Decision,
    EvalStats,
    ExperimentStage,
    HypothesisProposal,
    HypothesisRecord,
    PatchProposal,
    ProtocolResult,
)
from scion.core.scheduler import (
    ACTIVE_SLOT_RECLAIMED_FOR_NEW_BRANCH,
    Scheduler,
    SchedulerAction,
    active_slot_inventory,
)
from scion.core.step_result import StepResult


def _branch(
    branch_id: str = "branch-1",
    state: BranchState = BranchState.EXPLORE,
) -> Branch:
    return Branch(
        branch_id=branch_id,
        state=state,
        base_champion_id=1,
        base_champion_hash="champion-hash",
    )


def _champion() -> ChampionState:
    return ChampionState(
        version=1,
        operator_pool={},
        solver_config_hash="solver",
        code_snapshot_path="/tmp/champion",
        code_snapshot_hash="champion-hash",
    )


def _complete_replay_identity(code_hash: str = "candidate-hash") -> dict[str, object]:
    return {
        "schema": "scion.formal_replay_identity.v1",
        "problem_spec_hash": "problem-hash",
        "split_manifest_hash": "split-hash",
        "seed_ledger_hash": "seed-hash",
        "patch_digest": "patch-digest",
        "patch_hash": "patch-digest",
        "selected_surface": "generic_surface",
        "protocol_version": "protocol-v3",
        "raw_metrics_ref": "metrics/screening.json",
        "code_hash": code_hash,
        "identity_status": "complete",
        "status": "complete",
        "missing_identity_keys": [],
        "missing_keys": [],
    }


def _runner(
    *,
    scheduler_action: SchedulerAction,
    branch: Branch | None = None,
    recorded_scheduler_results: list[StepResult] | None = None,
    explore_result: StepResult | None = None,
    run_explore_step: Callable[[Branch], StepResult] | None = None,
) -> BranchStepRunner:
    selected_branch = branch or _branch()
    recorded = (
        recorded_scheduler_results
        if recorded_scheduler_results is not None
        else []
    )
    branch_controller = SimpleNamespace(
        get_active_branches=lambda: [selected_branch] if branch is not None else [],
        create_branch=lambda champion: selected_branch,
        get_branch=lambda branch_id: selected_branch,
        schedule_branch=lambda branch_id: None,
        apply_decision=lambda branch_id, decision: None,
    )
    scheduler = SimpleNamespace(select_next=lambda active: scheduler_action)
    branch_store = SimpleNamespace(save=lambda branch: None)
    selected_explore_result = explore_result or StepResult(
        action="explore",
        branch_id=selected_branch.branch_id,
        reason="screening complete",
    )
    return BranchStepRunner(
        branch_controller=branch_controller,
        scheduler=scheduler,
        champion_lock=nullcontext(),
        get_champion=lambda: SimpleNamespace(version=1),
        branch_store=branch_store,
        branch_workspaces={},
        branch_hypotheses={},
        branch_patches={},
        branch_current_hypothesis={},
        experiment_protocol_provider=lambda: None,
        contract_gate=None,
        verification_gate=None,
        drain_weight_opt_events=lambda: None,
        should_stop=lambda: False,
        get_last_stop_reason=lambda: None,
        tick_blocked_branches=lambda: None,
        persist_branch_state=lambda branch_id: None,
        record_hard_abandon=lambda branch_id, reason: None,
        setup_workspace=lambda *args, **kwargs: None,
        apply_patch=lambda *args, **kwargs: None,
        record_verification_pass=lambda branch, code_hash: None,
        evaluate=lambda branch, workspace, hypothesis: None,
        apply_decision_and_finalize=lambda **kwargs: StepResult(action="explore"),
        record_step=lambda step: None,
        decision_reason_codes_for=lambda branch_id, protocol_result: None,
        run_explore_step=(
            run_explore_step
            if run_explore_step is not None
            else lambda branch: selected_explore_result
        ),
        run_eval_step_callback=lambda branch: StepResult(
            action="validate",
            branch_id=branch.branch_id,
            reason="evaluation complete",
        ),
        run_reconcile_step_callback=lambda branch: StepResult(
            action="reconcile",
            branch_id=branch.branch_id,
            reason="reconcile complete",
        ),
        increment_round=lambda: 1,
        increment_rounds_since_last_promote=lambda: None,
        hypothesis_store=None,
        record_scheduler_result=recorded.append,
    )


def test_create_new_scheduler_metadata_reaches_result_and_callback() -> None:
    branch = _branch("new-branch")
    recorded: list[StepResult] = []
    runner = _runner(
        scheduler_action=SchedulerAction(
            action="create_new",
            slot="explore_new",
            reason="clean_fork_required_for_new_mechanism",
        ),
        branch=branch,
        recorded_scheduler_results=recorded,
    )

    result = runner.run_one_step()

    assert result.action == "create_branch"
    assert result.decision is None
    assert result.branch_id == "new-branch"
    assert result.scheduler_slot == "explore_new"
    assert result.scheduler_reason == "clean_fork_required_for_new_mechanism"
    metadata = result.scheduler_audit_metadata
    assert metadata["scheduler_action"] == "create_new"
    assert metadata["pre_finalizer_scheduler_action"] == "create_new"
    assert metadata["pre_finalizer_scheduler_slot"] == "explore_new"
    assert metadata["scheduler_slot_semantics"] == (
        "pre_finalizer_scheduler_preference"
    )
    assert metadata["actual_branch_action"] == "explore_new_clean_fork"
    assert metadata["post_finalizer_actual_branch_action"] == (
        "explore_new_clean_fork"
    )
    assert metadata["post_finalizer_next_proposal_policy"] == "clean_fork_selected"
    assert metadata["clean_fork_selected"] is True
    assert metadata["same_branch_refinement_not_selected_reason"] == (
        "clean_fork_required_for_new_mechanism"
    )
    justification = metadata["same_mechanism_clean_fork_justification"]
    assert justification == {
        "reason": "new_mechanism_requires_clean_fork",
        "selected_policy": "clean_fork_selected",
        "clean_fork_reason": "clean_fork_required_for_new_mechanism",
        "same_branch_refinement_not_selected_reason": (
            "clean_fork_required_for_new_mechanism"
        ),
        "active_branch_cap_context": {
            "scheduler_slot": "explore_new",
            "scheduler_reason": "clean_fork_required_for_new_mechanism",
            "pre_finalizer_scheduler_action": "create_new",
        },
    }
    assert "improve the same branch" not in result.reason
    assert recorded == [result]


def test_create_new_material_difference_requirement_reaches_branch_metadata() -> None:
    branch = _branch("new-branch")
    requirement = {
        "schema_version": "material_difference_requirement.v1",
        "record_type": "material_difference_requirement",
        "record_id": "material_difference_requirement:test",
        "record_digest": "sha256:test",
        "required_for": "clean_fork_new_branch",
        "proposal_visibility_only": True,
        "decision_features_excluded": True,
    }
    runner = _runner(
        scheduler_action=SchedulerAction(
            action="create_new",
            slot="explore_new",
            reason="plateau_gate_material_difference_required",
            audit_metadata={
                "material_difference_required": True,
                "material_difference_required_for": "clean_fork_new_branch",
                "material_difference_requirement": requirement,
                "low_value_clean_fork_material_difference_candidates": [
                    {
                        "branch_id": "retained-no-effect",
                        "release_reason": (
                            "retained_checkpoint_no_effect_current_head"
                        ),
                        "branch_code_status": "active_no_effect",
                        "screening_tier": "no_effect",
                    }
                ],
            },
        ),
        branch=branch,
    )

    result = runner.run_one_step()

    assert result.action == "create_branch"
    assert branch.branch_evidence_summary["material_difference_required"] is True
    assert branch.branch_evidence_summary[
        "material_difference_required_for"
    ] == "clean_fork_new_branch"
    assert branch.branch_evidence_summary[
        "material_difference_requirement"
    ] == requirement
    assert branch.branch_evidence_summary["material_difference_audit_records"] == [
        requirement
    ]
    assert branch.branch_evidence_summary[
        "material_difference_requirement_candidates"
    ] == [
        {
            "branch_id": "retained-no-effect",
            "release_reason": "retained_checkpoint_no_effect_current_head",
            "branch_code_status": "active_no_effect",
            "screening_tier": "no_effect",
            "candidate_source": (
                "low_value_clean_fork_material_difference_candidates"
            ),
        }
    ]


def test_clean_fork_selected_instead_of_same_branch_has_explicit_justification() -> None:
    branch = _branch("sibling-branch")
    runner = _runner(
        scheduler_action=SchedulerAction(
            action="create_new",
            slot="explore_new",
            reason="new_exploration_slot_available",
        ),
        branch=branch,
    )

    result = runner.run_one_step()

    justification = result.scheduler_audit_metadata[
        "same_mechanism_clean_fork_justification"
    ]
    assert result.action == "create_branch"
    assert result.decision is None
    assert justification["reason"] == "clean_fork_selected_instead_of_same_branch"
    assert justification["selected_policy"] == "clean_fork_selected"
    assert justification["clean_fork_reason"] == "new_exploration_slot_available"
    assert justification["same_branch_refinement_not_selected_reason"] == (
        "new_exploration_slot_available"
    )


def test_scheduler_action_audit_metadata_reaches_result() -> None:
    branch = _branch("weak-positive-branch")
    runner = _runner(
        scheduler_action=SchedulerAction(
            action="run_existing",
            branch=branch,
            slot="exploit_weak_positive",
            reason="weak_positive_signal_followup",
            audit_metadata={
                "runtime_evidence_clean_fork_suppression": (
                    "weak_positive_exception"
                ),
                "runtime_evidence_clean_fork_reason": (
                    "runtime_evidence_completeness_clean_fork"
                ),
                "runtime_evidence_pressure_count": 2,
                "case_wins": 1,
                "case_losses": 0,
            },
        ),
        branch=branch,
    )

    result = runner.run_one_step()

    metadata = result.scheduler_audit_metadata
    assert metadata["runtime_evidence_clean_fork_suppression"] == (
        "weak_positive_exception"
    )
    assert metadata["runtime_evidence_clean_fork_reason"] == (
        "runtime_evidence_completeness_clean_fork"
    )
    assert metadata["runtime_evidence_pressure_count"] == 2
    assert metadata["case_wins"] == 1
    assert metadata["case_losses"] == 0
    assert metadata["scheduler_action"] == "run_existing"


def test_fresh_runtime_replay_scheduler_action_skips_proposal_and_is_non_counted() -> None:
    branch = _branch("fresh-replay-branch")
    branch.branch_code_status = "active_weak_positive"
    branch.last_screening_feedback_tier = "weak_positive"
    branch.current_code_hash = "candidate-hash"
    branch.last_clean_code_hash = "candidate-hash"
    branch.branch_evidence_summary = {
        "protocol_stage": "screening",
        "replay_identity": _complete_replay_identity(),
        "fresh_runtime_followup": {
            "schema_version": "fresh_runtime_followup.v1",
            "queue_intent": "fresh_champion_runtime_replay",
            "scheduler_marker": "fresh_champion_runtime_replay_pending",
            "fresh_runtime_pending": True,
            "decision_features_excluded": True,
        }
    }
    hypothesis = HypothesisProposal(
        hypothesis_text="Replay the current candidate against fresh champion runtime.",
        change_locus="generic_surface",
        action="modify",
    )
    h_record = HypothesisRecord(
        hypothesis_id="h-fresh-replay",
        branch_id=branch.branch_id,
        change_locus="generic_surface",
        action="modify",
        status="running",
    )
    patch = PatchProposal(
        file_path="solver.py",
        action="modify",
        code_content="# candidate\n",
    )
    protocol = ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=EvalStats(
            n_cases=4,
            wins=0,
            losses=0,
            ties=4,
            win_rate=0.0,
            median_delta=0.0,
            ci_low=0.0,
            ci_high=0.0,
        ),
        gate_outcome="fail",
        reason_codes=("SCREENING_WEAK_SIGNAL_CONTINUE",),
        exposed_summary="fresh replay complete",
        raw_metrics_ref="/tmp/fresh-replay.json",
        champion_cache_hits=0,
        champion_cache_misses=8,
        champion_cached_runtime_pairs=0,
        runtime_confidence="high",
        runtime_evidence_status="sufficient",
    )
    steps = []
    evaluated = []

    def fail_proposal(selected: Branch) -> StepResult:
        raise AssertionError("fresh replay must not call proposal explore")

    def evaluate(
        selected: Branch,
        workspace: str,
        replay_hypothesis: HypothesisProposal,
    ):
        evaluated.append(
            (
                selected.branch_id,
                workspace,
                replay_hypothesis.hypothesis_text,
                getattr(selected, "fresh_runtime_replay_step", False),
            )
        )
        return Decision.CONTINUE_EXPLORE, protocol, CanaryResult(passed=True)

    def finalize(**kwargs):
        selected = kwargs["branch"]
        selected.branch_evidence_summary["fresh_runtime_followup"] = {
            "scheduler_marker": "fresh_champion_runtime_replay_closed",
            "fresh_runtime_pending": False,
            "decision_features_excluded": True,
        }
        selected.branch_evidence_summary["fresh_runtime_replay_closure"] = {
            "schema_version": "fresh_runtime_replay_closure.v1",
            "closure_status": "fresh_evidence_recorded",
            "decision_features_excluded": True,
        }
        return StepResult(
            action="explore",
            branch_id=selected.branch_id,
            decision=Decision.CONTINUE_EXPLORE,
            reason="fresh replay complete",
        )

    runner = _runner(
        scheduler_action=SchedulerAction(
            action="replay_existing",
            branch=branch,
            slot="exploit_weak_positive",
            reason="fresh_champion_runtime_replay_followup",
        ),
        branch=branch,
        run_explore_step=fail_proposal,
    )
    runner.branch_workspaces[branch.branch_id] = "/tmp/workspace"
    runner.branch_hypotheses[branch.branch_id] = hypothesis
    runner.branch_current_hypothesis[branch.branch_id] = h_record
    runner.branch_patches[branch.branch_id] = patch
    runner.evaluate = evaluate
    runner.apply_decision_and_finalize = finalize
    runner.record_step = steps.append

    result = runner.run_one_step()

    assert evaluated == [
        (
            branch.branch_id,
            "/tmp/workspace",
            "Replay the current candidate against fresh champion runtime.",
            True,
        )
    ]
    assert result.action == "replay"
    assert result.counts_toward_max_rounds is False
    assert result.attempt_kind == "fresh_runtime_replay"
    assert result.scheduler_audit_metadata["scheduler_action"] == "replay_existing"
    assert result.scheduler_audit_metadata["fresh_runtime_replay_selected"] is True
    assert result.scheduler_audit_metadata["fresh_runtime_replay"][
        "closure_status"
    ] == "fresh_evidence_recorded"
    assert steps[0].attempt_kind == "fresh_runtime_replay"
    assert steps[0].counts_toward_max_rounds is False
    assert steps[0].cache_stats == {
        "champion_cache_hits": 0,
        "champion_cache_misses": 8,
        "champion_cached_runtime_pairs": 0,
    }
    assert (
        branch.branch_evidence_summary["fresh_runtime_followup"][
            "fresh_runtime_pending"
        ]
        is False
    )


def test_fresh_runtime_replay_selected_without_identity_blocks_materialization() -> None:
    branch = _branch("fresh-replay-missing-identity")
    branch.branch_code_status = "active_weak_positive"
    branch.last_screening_feedback_tier = "weak_positive"
    branch.current_code_hash = "candidate-hash"
    branch.branch_evidence_summary = {
        "protocol_stage": "screening",
        "fresh_runtime_followup": {
            "schema_version": "fresh_runtime_followup.v1",
            "queue_intent": "fresh_champion_runtime_replay",
            "scheduler_marker": "fresh_champion_runtime_replay_pending",
            "fresh_runtime_pending": True,
            "fresh_runtime_required": True,
            "decision_features_excluded": True,
        },
    }
    hypothesis = HypothesisProposal(
        hypothesis_text="Replay current candidate against fresh champion runtime.",
        change_locus="generic_surface",
        action="modify",
    )
    h_record = HypothesisRecord(
        hypothesis_id="h-fresh-replay-missing-identity",
        branch_id=branch.branch_id,
        change_locus="generic_surface",
        action="modify",
        status="running",
    )
    patch = PatchProposal(
        file_path="solver.py",
        action="modify",
        code_content="# candidate\n",
    )
    persisted: list[str] = []

    def fail_proposal(selected: Branch) -> StepResult:
        raise AssertionError("fresh replay must not call proposal explore")

    def fail_evaluate(*_args, **_kwargs):
        raise AssertionError("missing replay identity must block evaluation")

    runner = _runner(
        scheduler_action=SchedulerAction(
            action="replay_existing",
            branch=branch,
            slot="exploit_weak_positive",
            reason="fresh_champion_runtime_replay_followup",
        ),
        branch=branch,
        run_explore_step=fail_proposal,
    )
    runner.branch_workspaces[branch.branch_id] = "/tmp/workspace"
    runner.branch_hypotheses[branch.branch_id] = hypothesis
    runner.branch_current_hypothesis[branch.branch_id] = h_record
    runner.branch_patches[branch.branch_id] = patch
    runner.evaluate = fail_evaluate
    runner.persist_branch_state = persisted.append

    result = runner.run_one_step()
    replay_metadata = result.scheduler_audit_metadata["fresh_runtime_replay"]
    closure = branch.branch_evidence_summary["fresh_runtime_replay_closure"]

    assert result.action == "replay"
    assert result.counts_toward_max_rounds is False
    assert result.failure_stage == "fresh_runtime_replay"
    assert replay_metadata["closure_status"] == (
        "blocked_missing_replay_materialization"
    )
    assert replay_metadata["missing_materialization_keys"] == ["replay_identity"]
    assert replay_metadata["missing_replay_identity_keys"] == ["replay_identity"]
    assert replay_metadata["non_replayable_reason"] == (
        "fresh_runtime_replay:missing_replay_identity"
    )
    assert closure["closure_status"] == "blocked_missing_replay_materialization"
    assert branch.branch_evidence_summary["fresh_runtime_pending"] is False
    assert branch.branch_evidence_summary["fresh_runtime_non_replayable"][
        "reason"
    ] == "fresh_runtime_replay:missing_replay_identity"
    assert persisted == [branch.branch_id]


def test_fresh_runtime_replay_with_artifact_but_no_live_state_blocks_materialization() -> None:
    branch = _branch("fresh-replay-artifact-only")
    branch.branch_evidence_summary = {
        "fresh_runtime_followup": {
            "schema_version": "fresh_runtime_followup.v1",
            "queue_intent": "fresh_champion_runtime_replay",
            "scheduler_marker": "fresh_champion_runtime_replay_pending",
            "fresh_runtime_pending": True,
            "fresh_runtime_required": True,
            "decision_features_excluded": True,
        },
        "formal_candidate_patch_artifact_ref": (
            "artifacts/formal_candidates/branch/screening-h/candidate.patch.json"
        ),
    }
    persisted: list[str] = []

    def fail_proposal(selected: Branch) -> StepResult:
        raise AssertionError("fresh replay must not call proposal explore")

    runner = _runner(
        scheduler_action=SchedulerAction(
            action="replay_existing",
            branch=branch,
            slot="exploit_weak_positive",
            reason="fresh_champion_runtime_replay_followup",
        ),
        branch=branch,
        run_explore_step=fail_proposal,
    )
    runner.persist_branch_state = persisted.append

    result = runner.run_one_step()

    replay_metadata = result.scheduler_audit_metadata["fresh_runtime_replay"]
    closure = branch.branch_evidence_summary["fresh_runtime_replay_closure"]

    assert result.action == "replay"
    assert result.counts_toward_max_rounds is False
    assert result.attempt_kind == "fresh_runtime_replay"
    assert result.failure_stage == "fresh_runtime_replay"
    assert "formal_candidate_patch_artifact_ref present" in result.reason
    assert replay_metadata["closure_status"] == (
        "blocked_missing_replay_materialization"
    )
    assert replay_metadata["formal_candidate_patch_artifact_ref"].endswith(
        "candidate.patch.json"
    )
    assert replay_metadata["missing_live_state"] == [
        "workspace",
        "hypothesis",
        "hypothesis_record",
        "patch",
    ]
    assert "patch_from_candidate_patch_json" in replay_metadata[
        "missing_replay_materialization"
    ]
    assert closure["closure_status"] == "blocked_missing_replay_materialization"
    assert "formal_candidate_patch_artifact_ref present" in closure["detail"]
    assert branch.branch_evidence_summary["fresh_runtime_pending"] is False
    assert branch.branch_evidence_summary["fresh_runtime_followup"][
        "fresh_runtime_pending"
    ] is False
    assert branch.branch_evidence_summary["fresh_runtime_followup"][
        "closure_status"
    ] == "blocked_missing_replay_materialization"
    assert persisted == [branch.branch_id]


def test_fresh_runtime_replay_drain_step_does_not_execute_non_replay_action() -> None:
    branch = _branch("ordinary-branch")
    recorded: list[StepResult] = []

    def fail_proposal(selected: Branch) -> StepResult:
        raise AssertionError("replay drain must not execute ordinary proposal")

    runner = _runner(
        scheduler_action=SchedulerAction(
            action="run_existing",
            branch=branch,
            slot="exploit_weak_positive",
            reason="weak_positive_signal_followup",
        ),
        branch=branch,
        recorded_scheduler_results=recorded,
        run_explore_step=fail_proposal,
    )

    result = runner.run_fresh_runtime_replay_drain_step()

    assert result.action == "skip"
    assert result.counts_toward_max_rounds is False
    assert result.attempt_kind == "other"
    assert result.scheduler_audit_metadata["scheduler_action"] == "run_existing"
    assert result.scheduler_audit_metadata["fresh_runtime_replay_drain"][
        "executed"
    ] is False
    assert recorded == []


def test_fresh_runtime_replay_drain_materializes_pair_win_pressure_and_prefers_replay() -> None:
    branch = _branch("fresh-pressure-materializable")
    branch.branch_code_status = "active_weak_positive"
    branch.last_screening_feedback_tier = "weak_positive"
    branch.current_code_hash = "candidate-hash"
    branch.last_clean_code_hash = "candidate-hash"
    branch.branch_evidence_summary = {
        "tier": "weak_positive",
        "pair_wins": 1,
        "pair_losses": 0,
        "pair_ties": 3,
        "runtime_evidence_status": "fresh_champion_required",
        "fresh_runtime_required": True,
        "fresh_runtime_pending": False,
        "runtime_evidence_pressure_count": 2,
        "reason_codes": ["RUNTIME_TIE_FRESH_CHAMPION_REQUIRED"],
        "protocol_stage": "screening",
        "replay_identity": _complete_replay_identity(),
    }
    hypothesis = HypothesisProposal(
        hypothesis_text="Replay current candidate against fresh champion runtime.",
        change_locus="generic_surface",
        action="modify",
    )
    h_record = HypothesisRecord(
        hypothesis_id="h-fresh-pressure-materializable",
        branch_id=branch.branch_id,
        change_locus="generic_surface",
        action="modify",
        status="running",
    )
    patch = PatchProposal(
        file_path="solver.py",
        action="modify",
        code_content="# candidate\n",
    )
    protocol = ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=EvalStats(
            n_cases=4,
            wins=0,
            losses=0,
            ties=4,
            win_rate=0.0,
            median_delta=0.0,
            ci_low=0.0,
            ci_high=0.0,
        ),
        gate_outcome="fail",
        reason_codes=("SCREENING_WEAK_SIGNAL_CONTINUE",),
        exposed_summary="fresh replay complete",
        raw_metrics_ref="/tmp/fresh-replay.json",
        champion_cache_hits=0,
        champion_cache_misses=8,
        champion_cached_runtime_pairs=0,
        runtime_confidence="high",
        runtime_evidence_status="sufficient",
    )
    evaluated_pending_markers: list[dict[str, object]] = []
    persisted: list[str] = []

    def fail_proposal(selected: Branch) -> StepResult:
        raise AssertionError("replay drain must prefer replay over create_new")

    def evaluate(selected: Branch, workspace: str, replay_hypothesis: HypothesisProposal):
        evaluated_pending_markers.append(
            dict(selected.branch_evidence_summary["fresh_runtime_followup"])
        )
        return Decision.CONTINUE_EXPLORE, protocol, CanaryResult(passed=True)

    def finalize(**kwargs):
        selected = kwargs["branch"]
        selected.branch_evidence_summary["fresh_runtime_followup"][
            "fresh_runtime_pending"
        ] = False
        selected.branch_evidence_summary["fresh_runtime_followup"][
            "scheduler_marker"
        ] = "fresh_champion_runtime_replay_closed"
        selected.branch_evidence_summary["fresh_runtime_replay_closure"] = {
            "schema_version": "fresh_runtime_replay_closure.v1",
            "closure_status": "fresh_evidence_recorded",
            "decision_features_excluded": True,
        }
        return StepResult(
            action="explore",
            branch_id=selected.branch_id,
            decision=Decision.CONTINUE_EXPLORE,
            reason="fresh replay complete",
        )

    runner = _runner(
        scheduler_action=SchedulerAction(
            action="create_new",
            branch=None,
            slot="explore_new",
            reason="runtime_evidence_completeness_clean_fork",
        ),
        branch=branch,
        run_explore_step=fail_proposal,
    )
    runner.branch_workspaces[branch.branch_id] = "/tmp/workspace"
    runner.branch_hypotheses[branch.branch_id] = hypothesis
    runner.branch_current_hypothesis[branch.branch_id] = h_record
    runner.branch_patches[branch.branch_id] = patch
    runner.evaluate = evaluate
    runner.apply_decision_and_finalize = finalize
    runner.persist_branch_state = persisted.append

    result = runner.run_fresh_runtime_replay_drain_step()
    metadata = result.scheduler_audit_metadata

    assert result.action == "replay"
    assert result.counts_toward_max_rounds is False
    assert result.attempt_kind == "fresh_runtime_replay"
    assert metadata["scheduler_action"] == "replay_existing"
    assert metadata["fresh_runtime_replay_selected"] is True
    assert metadata["fresh_runtime_replay_drain_override"] == (
        "materializable_pending_replay_preferred"
    )
    assert metadata["fresh_runtime_pending_materialized"][0]["branch_id"] == (
        branch.branch_id
    )
    assert (
        metadata["fresh_runtime_pending_materialized"][0][
            "decision_features_excluded"
        ]
        is True
    )
    assert metadata["fresh_runtime_replay"]["decision_features_excluded"] is True
    assert evaluated_pending_markers[0]["fresh_runtime_pending"] is True
    assert evaluated_pending_markers[0]["scheduler_marker"] == (
        "fresh_champion_runtime_replay_pending"
    )
    assert evaluated_pending_markers[0]["trigger"] == "pair_level_win_no_loss"
    assert evaluated_pending_markers[0]["decision_features_excluded"] is True
    assert persisted == [branch.branch_id]


def test_fresh_runtime_replay_drain_does_not_materialize_no_effect_runtime_tie() -> None:
    branch = _branch("fresh-pressure-no-effect")
    branch.branch_code_status = "active_no_effect"
    branch.last_screening_feedback_tier = "no_effect"
    branch.current_code_hash = "candidate-hash"
    branch.last_clean_code_hash = "candidate-hash"
    branch.branch_evidence_summary = {
        "tier": "no_effect",
        "wins": 0,
        "losses": 0,
        "ties": 4,
        "pair_wins": 0,
        "pair_losses": 0,
        "pair_ties": 8,
        "median_delta": 0,
        "runtime_model": "budget_exhausting",
        "runtime_evidence_status": "fresh_champion_required",
        "fresh_runtime_required": True,
        "fresh_runtime_pending": False,
        "runtime_evidence_pressure_count": 2,
        "reason_codes": ["RUNTIME_TIE_FRESH_CHAMPION_REQUIRED"],
        "protocol_stage": "screening",
        "replay_identity": _complete_replay_identity(),
    }
    hypothesis = HypothesisProposal(
        hypothesis_text="No-effect runtime tie should clean-fork instead of replay.",
        change_locus="generic_surface",
        action="modify",
    )
    h_record = HypothesisRecord(
        hypothesis_id="h-fresh-pressure-no-effect",
        branch_id=branch.branch_id,
        change_locus="generic_surface",
        action="modify",
        status="running",
    )
    patch = PatchProposal(
        file_path="solver.py",
        action="modify",
        code_content="# candidate\n",
    )
    evaluated: list[str] = []
    persisted: list[str] = []

    def fail_proposal(selected: Branch) -> StepResult:
        return StepResult(
            action="explore",
            branch_id=selected.branch_id,
            reason="clean fork would be proposed by normal scheduling",
        )

    def evaluate(*_args):
        evaluated.append("called")
        raise AssertionError("no-effect runtime tie must not run replay")

    runner = _runner(
        scheduler_action=SchedulerAction(
            action="create_new",
            branch=None,
            slot="explore_new",
            reason="runtime_evidence_completeness_clean_fork",
        ),
        branch=branch,
        run_explore_step=fail_proposal,
    )
    runner.branch_workspaces[branch.branch_id] = "/tmp/workspace"
    runner.branch_hypotheses[branch.branch_id] = hypothesis
    runner.branch_current_hypothesis[branch.branch_id] = h_record
    runner.branch_patches[branch.branch_id] = patch
    runner.evaluate = evaluate
    runner.persist_branch_state = persisted.append

    result = runner.run_fresh_runtime_replay_drain_step()
    drain = result.scheduler_audit_metadata["fresh_runtime_replay_drain"]

    assert result.action == "skip"
    assert result.counts_toward_max_rounds is False
    assert result.attempt_kind == "other"
    assert evaluated == []
    assert persisted == []
    assert branch.branch_evidence_summary["fresh_runtime_pending"] is False
    assert "fresh_runtime_pending_materialized" not in drain


def test_fresh_runtime_replay_drain_ignores_budget_exhausting_marker() -> None:
    branch = _branch("fresh-pressure-budget-exhausting")
    branch.branch_code_status = "active_weak_positive"
    branch.last_screening_feedback_tier = "weak_positive"
    branch.current_code_hash = "candidate-hash"
    branch.last_clean_code_hash = "candidate-hash"
    branch.branch_evidence_summary = {
        "tier": "weak_positive",
        "wins": 1,
        "losses": 0,
        "ties": 3,
        "pair_wins": 1,
        "pair_losses": 0,
        "pair_ties": 3,
        "runtime_model": "budget_exhausting",
        "runtime_evidence_status": "fresh_champion_required",
        "fresh_runtime_required": True,
        "fresh_runtime_pending": False,
        "runtime_evidence_pressure_count": 2,
        "reason_codes": ["RUNTIME_TIE_FRESH_CHAMPION_REQUIRED"],
        "protocol_stage": "screening",
        "replay_identity": _complete_replay_identity(),
    }
    hypothesis = HypothesisProposal(
        hypothesis_text="Weak positive budget-exhausting runtime tie should not replay.",
        change_locus="generic_surface",
        action="modify",
    )
    h_record = HypothesisRecord(
        hypothesis_id="h-fresh-pressure-budget-exhausting",
        branch_id=branch.branch_id,
        change_locus="generic_surface",
        action="modify",
        status="running",
    )
    patch = PatchProposal(
        file_path="solver.py",
        action="modify",
        code_content="# candidate\n",
    )
    evaluated: list[str] = []
    persisted: list[str] = []

    def fail_proposal(selected: Branch) -> StepResult:
        return StepResult(
            action="explore",
            branch_id=selected.branch_id,
            reason="normal clean fork remains available",
        )

    def evaluate(*_args):
        evaluated.append("called")
        raise AssertionError("budget-exhausting runtime marker must not replay")

    runner = _runner(
        scheduler_action=SchedulerAction(
            action="create_new",
            branch=None,
            slot="explore_new",
            reason="runtime_evidence_completeness_clean_fork",
        ),
        branch=branch,
        run_explore_step=fail_proposal,
    )
    runner.branch_workspaces[branch.branch_id] = "/tmp/workspace"
    runner.branch_hypotheses[branch.branch_id] = hypothesis
    runner.branch_current_hypothesis[branch.branch_id] = h_record
    runner.branch_patches[branch.branch_id] = patch
    runner.evaluate = evaluate
    runner.persist_branch_state = persisted.append

    result = runner.run_fresh_runtime_replay_drain_step()
    drain = result.scheduler_audit_metadata["fresh_runtime_replay_drain"]

    assert result.action == "skip"
    assert result.counts_toward_max_rounds is False
    assert result.attempt_kind == "other"
    assert evaluated == []
    assert persisted == []
    assert "fresh_runtime_pending_materialized" not in drain
    assert "pressure_no_schedulable_replay_candidate" not in drain
    assert branch.branch_evidence_summary["fresh_runtime_pending"] is False


def test_fresh_runtime_replay_drain_reports_stale_materializable_as_unschedulable() -> None:
    branch = _branch("fresh-pressure-stale-materializable", state=BranchState.STALE)
    branch.branch_code_status = "active_no_effect"
    branch.last_screening_feedback_tier = "no_effect"
    branch.current_code_hash = "candidate-hash"
    branch.last_clean_code_hash = "candidate-hash"
    branch.branch_evidence_summary = {
        "runtime_evidence_status": "fresh_champion_required",
        "fresh_runtime_required": True,
        "fresh_runtime_pending": False,
        "runtime_evidence_pressure_count": 2,
        "reason_codes": ["RUNTIME_TIE_FRESH_CHAMPION_REQUIRED"],
        "protocol_stage": "screening",
        "replay_identity": _complete_replay_identity(),
    }
    hypothesis = HypothesisProposal(
        hypothesis_text="Replay current candidate against fresh champion runtime.",
        change_locus="generic_surface",
        action="modify",
    )
    h_record = HypothesisRecord(
        hypothesis_id="h-fresh-pressure-stale-materializable",
        branch_id=branch.branch_id,
        change_locus="generic_surface",
        action="modify",
        status="running",
    )
    patch = PatchProposal(
        file_path="solver.py",
        action="modify",
        code_content="# candidate\n",
    )

    def fail_proposal(selected: Branch) -> StepResult:
        raise AssertionError("replay drain must not execute ordinary proposal")

    runner = _runner(
        scheduler_action=SchedulerAction(
            action="create_new",
            branch=None,
            slot="explore_new",
            reason="runtime_evidence_completeness_clean_fork",
        ),
        branch=branch,
        run_explore_step=fail_proposal,
    )
    runner.branch_workspaces[branch.branch_id] = "/tmp/workspace"
    runner.branch_hypotheses[branch.branch_id] = hypothesis
    runner.branch_current_hypothesis[branch.branch_id] = h_record
    runner.branch_patches[branch.branch_id] = patch

    result = runner.run_fresh_runtime_replay_drain_step()
    metadata = result.scheduler_audit_metadata
    candidate = metadata["fresh_runtime_replay"][
        "fresh_runtime_pressure_candidates"
    ][0]

    assert result.action == "skip"
    assert result.counts_toward_max_rounds is False
    assert metadata["scheduler_action"] == "create_new"
    assert metadata["fresh_runtime_replay"]["closure_status"] == (
        "pressure_no_schedulable_replay_candidate"
    )
    assert metadata["fresh_runtime_replay_drain"][
        "pressure_no_schedulable_replay_candidate"
    ] is True
    assert "pressure_no_replayable_candidate" not in (
        metadata["fresh_runtime_replay_drain"]
    )
    assert "materializable" not in metadata["fresh_runtime_replay"]["detail"]
    assert candidate["branch_id"] == branch.branch_id
    assert candidate["branch_state"] == "stale"
    assert candidate["replay_materializable"] is True
    assert candidate["replay_schedulable"] is False
    assert candidate["blocked_by_state"] == "stale"
    assert "blocked_by_state:stale" in candidate[
        "replay_schedulable_block_reasons"
    ]
    assert candidate["missing_materialization_keys"] == []
    assert candidate["missing_replay_identity_keys"] == []


def test_fresh_runtime_pressure_missing_replay_identity_marks_non_replayable() -> None:
    branch = _branch("fresh-pressure-missing-identity")
    branch.branch_code_status = "active_weak_positive"
    branch.last_screening_feedback_tier = "weak_positive"
    branch.current_code_hash = "candidate-hash"
    branch.branch_evidence_summary = {
        "tier": "weak_positive",
        "pair_wins": 1,
        "pair_losses": 0,
        "pair_ties": 3,
        "runtime_evidence_status": "fresh_champion_required",
        "fresh_runtime_required": True,
        "fresh_runtime_pending": False,
        "runtime_evidence_pressure_count": 2,
        "reason_codes": ["RUNTIME_TIE_FRESH_CHAMPION_REQUIRED"],
        "protocol_stage": "screening",
    }
    hypothesis = HypothesisProposal(
        hypothesis_text="Replay current candidate against fresh champion runtime.",
        change_locus="generic_surface",
        action="modify",
    )
    h_record = HypothesisRecord(
        hypothesis_id="h-fresh-pressure-missing-identity",
        branch_id=branch.branch_id,
        change_locus="generic_surface",
        action="modify",
        status="running",
    )
    patch = PatchProposal(
        file_path="solver.py",
        action="modify",
        code_content="# candidate\n",
    )
    persisted: list[str] = []

    def fail_proposal(selected: Branch) -> StepResult:
        raise AssertionError("replay drain must not execute ordinary proposal")

    runner = _runner(
        scheduler_action=SchedulerAction(
            action="create_new",
            branch=None,
            slot="explore_new",
            reason="runtime_evidence_completeness_clean_fork",
        ),
        branch=branch,
        run_explore_step=fail_proposal,
    )
    runner.branch_workspaces[branch.branch_id] = "/tmp/workspace"
    runner.branch_hypotheses[branch.branch_id] = hypothesis
    runner.branch_current_hypothesis[branch.branch_id] = h_record
    runner.branch_patches[branch.branch_id] = patch
    runner.persist_branch_state = persisted.append

    result = runner.run_fresh_runtime_replay_drain_step()
    metadata = result.scheduler_audit_metadata
    marker = branch.branch_evidence_summary["fresh_runtime_followup"]
    non_replayable = branch.branch_evidence_summary["fresh_runtime_non_replayable"]
    candidate = metadata["fresh_runtime_replay"][
        "fresh_runtime_pressure_candidates"
    ][0]

    assert result.action == "skip"
    assert result.counts_toward_max_rounds is False
    assert marker["fresh_runtime_pending"] is False
    assert marker["scheduler_marker"] == (
        "fresh_champion_runtime_replay_non_replayable"
    )
    assert marker["non_replayable_reason"] == (
        "fresh_runtime_replay:missing_replay_identity"
    )
    assert non_replayable["missing_materialization_keys"] == ["replay_identity"]
    assert non_replayable["missing_replay_identity_keys"] == ["replay_identity"]
    assert metadata["fresh_runtime_replay_drain"][
        "fresh_runtime_non_replayable_marked"
    ][0]["branch_id"] == branch.branch_id
    assert candidate["replay_materializable"] is False
    assert candidate["missing_materialization_keys"] == ["replay_identity"]
    assert candidate["non_replayable_reason"] == (
        "fresh_runtime_replay:missing_replay_identity"
    )
    assert persisted == [branch.branch_id]


def test_fresh_runtime_replay_drain_step_reports_pressure_without_pending_candidate() -> None:
    branch = _branch("fresh-pressure-no-pending")
    branch.branch_code_status = "active_no_effect"
    branch.last_screening_feedback_tier = "no_effect"
    branch.branch_evidence_summary = {
        "runtime_evidence_status": "fresh_champion_required",
        "fresh_runtime_required": True,
        "fresh_runtime_pending": False,
        "runtime_evidence_pressure_count": 2,
        "reason_codes": ["RUNTIME_TIE_FRESH_CHAMPION_REQUIRED"],
    }

    def fail_proposal(selected: Branch) -> StepResult:
        raise AssertionError("replay drain must not execute ordinary proposal")

    runner = _runner(
        scheduler_action=SchedulerAction(
            action="create_new",
            branch=None,
            slot="explore_new",
            reason="runtime_evidence_completeness_clean_fork",
        ),
        branch=branch,
        run_explore_step=fail_proposal,
    )

    result = runner.run_fresh_runtime_replay_drain_step()
    metadata = result.scheduler_audit_metadata

    assert result.action == "skip"
    assert result.counts_toward_max_rounds is False
    assert metadata["scheduler_action"] == "create_new"
    assert metadata["fresh_runtime_replay"]["closure_status"] == (
        "pressure_no_schedulable_replay_candidate"
    )
    assert metadata["fresh_runtime_replay_drain"][
        "pressure_no_schedulable_replay_candidate"
    ] is True
    assert metadata["fresh_runtime_replay"][
        "fresh_runtime_pressure_candidates"
    ][0]["branch_id"] == "fresh-pressure-no-pending"
    candidate = metadata["fresh_runtime_replay"][
        "fresh_runtime_pressure_candidates"
    ][0]
    assert candidate["replay_materializable"] is False
    assert candidate["replay_schedulable"] is False
    assert candidate["blocked_by_pending_marker"] == (
        "fresh_champion_runtime_replay_pending_missing"
    )
    assert candidate["blocked_by_materialization"] == (
        "missing_materialization_keys"
    )
    assert set(candidate["missing_materialization_keys"]) == {
        "candidate_workspace",
        "hypothesis",
        "hypothesis_record",
        "patch",
        "candidate_hash",
        "protocol_stage",
        "replay_identity",
    }
    assert metadata["fresh_runtime_replay"]["missing_materialization_keys"] == (
        candidate["missing_materialization_keys"]
    )
    assert metadata["fresh_runtime_replay"]["decision_features_excluded"] is True


def test_capacity_full_low_signal_without_decision_marker_runs_existing_branch() -> None:
    champion = _champion()
    controller = BranchController()
    stale_branches = []
    for index in range(3):
        branch = controller.create_branch(champion)
        branch.direction = f"solver: no-effect follow-up {index}"
        branch.branch_code_status = "active_no_effect"
        branch.last_screening_feedback_tier = "no_effect"
        branch.branch_mechanism_ids = (f"probe-{index}",)
        branch.best_quality_checkpoint_id = f"checkpoint-{index}"
        branch.last_valid_checkpoint_id = f"checkpoint-{index}"
        stale_branches.append(branch)
    reclaim_target = stale_branches[0]
    recorded: list[StepResult] = []
    saved: list[tuple[str, BranchState]] = []

    def save_branch(branch: Branch) -> None:
        saved.append((branch.branch_id, branch.state))

    runner = BranchStepRunner(
        branch_controller=controller,
        scheduler=Scheduler(max_active_branches=3),
        champion_lock=nullcontext(),
        get_champion=lambda: champion,
        branch_store=SimpleNamespace(save=save_branch),
        branch_workspaces={},
        branch_hypotheses={},
        branch_patches={},
        branch_current_hypothesis={},
        experiment_protocol_provider=lambda: None,
        contract_gate=None,
        verification_gate=None,
        drain_weight_opt_events=lambda: None,
        should_stop=lambda: False,
        get_last_stop_reason=lambda: None,
        tick_blocked_branches=lambda: None,
        persist_branch_state=lambda branch_id: save_branch(
            controller.get_branch(branch_id)
        ),
        record_hard_abandon=lambda branch_id, reason: None,
        setup_workspace=lambda *args, **kwargs: None,
        apply_patch=lambda *args, **kwargs: None,
        record_verification_pass=lambda branch, code_hash: None,
        evaluate=lambda branch, workspace, hypothesis: None,
        apply_decision_and_finalize=lambda **kwargs: StepResult(action="explore"),
        record_step=lambda step: None,
        decision_reason_codes_for=lambda branch_id, protocol_result: None,
        run_explore_step=lambda branch: StepResult(
            action="explore",
            branch_id=branch.branch_id,
            reason="screening complete",
        ),
        run_eval_step_callback=lambda branch: StepResult(action="validate"),
        run_reconcile_step_callback=lambda branch: StepResult(action="reconcile"),
        increment_round=lambda: 1,
        increment_rounds_since_last_promote=lambda: None,
        hypothesis_store=None,
        record_scheduler_result=recorded.append,
    )

    result = runner.run_one_step()
    inventory = active_slot_inventory(
        controller.get_reportable_branches(),
        max_active_branches=3,
    )

    assert result.action == "explore"
    assert result.branch_id == reclaim_target.branch_id
    assert result.scheduler_slot == "repair_diagnostic"
    assert result.scheduler_reason == "no_effect_same_mechanism_followup"
    assert result.reason != "max_active_branches reached"
    assert reclaim_target.state == BranchState.EXPLORE
    assert inventory["used"] == 3
    assert inventory["parked_lineage_ids"] == []
    assert len(controller.get_reportable_branches()) == 3
    assert saved == []
    assert "active_slot_reconciliation" not in result.scheduler_audit_metadata
    assert "active_slot_hard_cap" not in result.scheduler_audit_metadata
    assert recorded == [result]


def test_clean_fork_reclaims_decision_marked_slot_before_create_new() -> None:
    champion = _champion()
    controller = BranchController()
    stale_low_signal = controller.create_branch(champion)
    stale_low_signal.direction = "solver: no-effect follow-up"
    stale_low_signal.branch_code_status = "active_no_effect"
    stale_low_signal.last_screening_feedback_tier = "no_effect"
    stale_low_signal.branch_mechanism_ids = ("probe",)
    stale_low_signal.last_branch_lifecycle_policy_block = {
        "reason": "park_lineage",
        "block_count": 1,
        "lifecycle_action_reason_codes": [BRANCH_LIFECYCLE_PARK_LINEAGE],
    }
    stale_low_signal.branch_lifecycle_policy_blocks = 1
    recorded: list[StepResult] = []
    saved: list[tuple[str, BranchState]] = []

    def save_branch(branch: Branch) -> None:
        saved.append((branch.branch_id, branch.state))

    runner = BranchStepRunner(
        branch_controller=controller,
        scheduler=Scheduler(max_active_branches=1),
        champion_lock=nullcontext(),
        get_champion=lambda: champion,
        branch_store=SimpleNamespace(save=save_branch),
        branch_workspaces={},
        branch_hypotheses={},
        branch_patches={},
        branch_current_hypothesis={},
        experiment_protocol_provider=lambda: None,
        contract_gate=None,
        verification_gate=None,
        drain_weight_opt_events=lambda: None,
        should_stop=lambda: False,
        get_last_stop_reason=lambda: None,
        tick_blocked_branches=lambda: None,
        persist_branch_state=lambda branch_id: save_branch(
            controller.get_branch(branch_id)
        ),
        record_hard_abandon=lambda branch_id, reason: None,
        setup_workspace=lambda *args, **kwargs: None,
        apply_patch=lambda *args, **kwargs: None,
        record_verification_pass=lambda branch, code_hash: None,
        evaluate=lambda branch, workspace, hypothesis: None,
        apply_decision_and_finalize=lambda **kwargs: StepResult(action="explore"),
        record_step=lambda step: None,
        decision_reason_codes_for=lambda branch_id, protocol_result: None,
        run_explore_step=lambda branch: StepResult(
            action="explore",
            branch_id=branch.branch_id,
            reason="screening complete",
        ),
        run_eval_step_callback=lambda branch: StepResult(action="validate"),
        run_reconcile_step_callback=lambda branch: StepResult(action="reconcile"),
        increment_round=lambda: 1,
        increment_rounds_since_last_promote=lambda: None,
        hypothesis_store=None,
        record_scheduler_result=recorded.append,
    )

    result = runner.run_one_step()
    inventory = active_slot_inventory(
        controller.get_reportable_branches(),
        max_active_branches=1,
    )

    assert result.action == "create_branch"
    assert result.branch_id != stale_low_signal.branch_id
    assert stale_low_signal.state == BranchState.PARKED_LINEAGE
    assert inventory["used"] == 1
    assert inventory["parked_lineage_ids"] == [stale_low_signal.branch_id]
    assert len(controller.get_reportable_branches()) == 2
    assert saved[0] == (stale_low_signal.branch_id, BranchState.PARKED_LINEAGE)
    lifecycle_codes = stale_low_signal.last_branch_lifecycle_policy_block[
        "lifecycle_action_reason_codes"
    ]
    assert lifecycle_codes == [BRANCH_LIFECYCLE_PARK_LINEAGE]
    assert ACTIVE_SLOT_RECLAIMED_FOR_NEW_BRANCH not in lifecycle_codes
    assert result.scheduler_audit_metadata["active_slot_reconciliation"][
        "mode"
    ] == "new_branch_reclaim"
    assert recorded == [result]


def test_run_existing_scheduler_metadata_reaches_result_and_callback() -> None:
    branch = _branch("existing-branch")
    recorded: list[StepResult] = []
    runner = _runner(
        scheduler_action=SchedulerAction(
            action="run_existing",
            branch=branch,
            slot="refine_active",
            reason="existing_branch_selected",
        ),
        branch=branch,
        recorded_scheduler_results=recorded,
    )

    result = runner.run_one_step()

    assert result.action == "explore"
    assert result.branch_id == "existing-branch"
    assert result.scheduler_slot == "refine_active"
    assert result.scheduler_reason == "existing_branch_selected"
    metadata = result.scheduler_audit_metadata
    assert metadata["scheduler_action"] == "run_existing"
    assert metadata["pre_finalizer_scheduler_action"] == "run_existing"
    assert metadata["pre_finalizer_scheduler_slot"] == "refine_active"
    assert metadata["pre_finalizer_selected_branch_id"] == "existing-branch"
    assert metadata["scheduler_slot_semantics"] == (
        "pre_finalizer_scheduler_preference"
    )
    assert metadata["actual_branch_action"] == "continue_same_branch"
    assert metadata["post_finalizer_actual_branch_action"] == "continue_same_branch"
    assert metadata["post_finalizer_next_proposal_policy"] == (
        "same_branch_eligible"
    )
    assert metadata["post_finalizer_branch_id"] == "existing-branch"
    assert metadata["post_finalizer_branch_state"] == "explore"
    assert metadata["post_finalizer_counts_toward_active_slots"] is True
    assert metadata["same_branch_refinement_selected"] is True
    assert metadata["pre_finalizer_same_branch_refinement_selected"] is True
    assert metadata["same_mechanism_clean_fork_justification"] == {
        "reason": "not_applicable",
        "selected_policy": "same_branch_eligible",
        "clean_fork_reason": "",
        "same_branch_refinement_not_selected_reason": "",
        "active_branch_cap_context": {
            "scheduler_slot": "refine_active",
            "scheduler_reason": "existing_branch_selected",
            "pre_finalizer_scheduler_action": "run_existing",
        },
    }
    assert metadata["post_refine_decision_reason"] == "screening complete"
    assert recorded == [result]


def test_parked_lineage_records_post_finalizer_release_not_continue_same_branch() -> None:
    branch = _branch("parked-after-refine")
    branch.best_quality_checkpoint_id = "checkpoint-best"
    branch.last_valid_checkpoint_id = "checkpoint-best"
    recorded: list[StepResult] = []

    def park_lineage(selected: Branch) -> StepResult:
        selected.state = BranchState.PARKED_LINEAGE
        selected.branch_code_status = "parked_lineage"
        selected.last_branch_lifecycle_policy_block = {
            "lifecycle_action_reason_codes": [
                BRANCH_LIFECYCLE_PARK_LINEAGE,
                BRANCH_LIFECYCLE_RETAIN_CHECKPOINT,
            ],
        }
        return StepResult(
            action="explore",
            branch_id=selected.branch_id,
            reason="CONTINUE_EXPLORE: park_lineage; improve the same branch",
        )

    runner = _runner(
        scheduler_action=SchedulerAction(
            action="run_existing",
            branch=branch,
            slot="refine_active",
            reason="active_branch_refinement",
        ),
        branch=branch,
        recorded_scheduler_results=recorded,
        run_explore_step=park_lineage,
    )

    result = runner.run_one_step()
    metadata = result.scheduler_audit_metadata
    next_selection = Scheduler(max_active_branches=3).select_next([branch])

    assert metadata["pre_finalizer_scheduler_slot"] == "refine_active"
    assert metadata["pre_finalizer_selected_branch_id"] == "parked-after-refine"
    assert metadata["scheduler_slot_semantics"] == (
        "pre_finalizer_scheduler_preference"
    )
    assert metadata["actual_branch_action"] == "parked_lineage_released"
    assert metadata["post_finalizer_actual_branch_action"] == (
        "parked_lineage_released"
    )
    assert metadata["post_finalizer_actual_branch_action"] != (
        "continue_same_branch"
    )
    assert metadata["same_branch_refinement_selected"] is False
    assert metadata["pre_finalizer_same_branch_refinement_selected"] is True
    assert metadata["post_finalizer_lifecycle_action"] == "park_lineage"
    assert metadata["post_finalizer_active_slot_release_reason"] == "parked_lineage"
    assert metadata["post_finalizer_counts_toward_active_slots"] is False
    assert metadata["post_finalizer_next_proposal_policy"] == (
        "clean_fork_or_other_branch_required"
    )
    assert "release the branch slot" in result.reason
    assert next_selection.action == "create_new"
    assert next_selection.branch is None
    assert recorded == [result]


def test_same_branch_repair_soft_abandon_metadata_and_reason_are_aligned() -> None:
    branch = _branch("repair-branch")
    recorded: list[StepResult] = []
    runner = _runner(
        scheduler_action=SchedulerAction(
            action="run_existing",
            branch=branch,
            slot="repair_diagnostic",
            reason="effect_diagnostic_followup",
        ),
        branch=branch,
        recorded_scheduler_results=recorded,
        explore_result=StepResult(
            action="soft_abandon",
            branch_id="repair-branch",
            reason=(
                "CONTINUE_EXPLORE: weak-positive screening signal; "
                "improve the same branch"
            ),
        ),
    )

    result = runner.run_one_step()

    assert result.action == "soft_abandon"
    assert result.branch_id == "repair-branch"
    assert "repair/refine the same branch" in result.reason
    assert "improve the same branch" not in result.reason
    metadata = result.scheduler_audit_metadata
    assert metadata["scheduler_action"] == "run_existing"
    assert metadata["pre_finalizer_scheduler_slot"] == "repair_diagnostic"
    assert metadata["actual_branch_action"] == "soft_abandon"
    assert metadata["post_finalizer_actual_branch_action"] == "soft_abandon"
    assert metadata["post_finalizer_next_proposal_policy"] == (
        "same_branch_not_selected"
    )
    assert metadata["same_branch_refinement_selected"] is False
    assert metadata["pre_finalizer_same_branch_refinement_selected"] is True
    assert metadata["post_refine_abandon_reason"] == (
        "CONTINUE_EXPLORE: weak-positive screening signal; "
        "repair/refine the same branch"
    )
    assert recorded == [result]


def test_same_branch_low_signal_sample_metadata_keeps_refine_slot() -> None:
    branch = _branch("low-signal-sample")
    recorded: list[StepResult] = []
    runner = _runner(
        scheduler_action=SchedulerAction(
            action="run_existing",
            branch=branch,
            slot="refine_active",
            reason="same_branch_low_signal_observation_sample",
            audit_metadata={
                "same_branch_refinement_sampling": True,
                "same_branch_refinement_reason": "no_effect_observation",
                "clean_fork_suppressed_for_same_branch_sample": True,
            },
        ),
        branch=branch,
        recorded_scheduler_results=recorded,
        explore_result=StepResult(
            action="explore",
            branch_id="low-signal-sample",
            reason=(
                "CONTINUE_EXPLORE: low-signal observation sample; "
                "improve the same branch"
            ),
        ),
    )

    result = runner.run_one_step()

    assert result.action == "explore"
    assert result.branch_id == "low-signal-sample"
    assert result.scheduler_slot == "refine_active"
    assert result.scheduler_reason == "same_branch_low_signal_observation_sample"
    assert "refine the same branch" in result.reason
    assert "repair/refine" not in result.reason
    metadata = result.scheduler_audit_metadata
    assert metadata["pre_finalizer_scheduler_slot"] == "refine_active"
    assert metadata["same_branch_refinement_sampling"] is True
    assert metadata["same_branch_refinement_selected"] is True
    assert metadata["post_finalizer_next_proposal_policy"] == (
        "same_branch_eligible"
    )
    assert metadata["same_mechanism_clean_fork_justification"] == {
        "reason": "not_applicable",
        "selected_policy": "same_branch_eligible",
        "clean_fork_reason": "",
        "same_branch_refinement_not_selected_reason": "",
        "active_branch_cap_context": {
            "scheduler_slot": "refine_active",
            "scheduler_reason": "same_branch_low_signal_observation_sample",
            "pre_finalizer_scheduler_action": "run_existing",
        },
    }
    assert recorded == [result]


def test_at_capacity_scheduler_metadata_reaches_result_and_callback() -> None:
    recorded: list[StepResult] = []
    runner = _runner(
        scheduler_action=SchedulerAction(
            action="at_capacity",
            slot="capacity_blocked",
            reason="active_branch_limit_reached",
        ),
        recorded_scheduler_results=recorded,
    )

    result = runner.run_one_step()

    assert result.action == "skip"
    assert result.branch_id is None
    assert result.counts_toward_max_rounds is False
    assert result.attempt_kind == "scheduler_active_slot_blocked"
    assert result.scheduler_slot == "capacity_blocked"
    assert result.scheduler_reason == "active_branch_limit_reached"
    assert result.scheduler_audit_metadata[
        "same_mechanism_clean_fork_justification"
    ] == {
        "reason": "not_applicable",
        "selected_policy": "at_capacity",
        "clean_fork_reason": "",
        "same_branch_refinement_not_selected_reason": "",
        "active_branch_cap_context": {
            "scheduler_slot": "capacity_blocked",
            "scheduler_reason": "active_branch_limit_reached",
            "pre_finalizer_scheduler_action": "at_capacity",
        },
    }
    assert recorded == [result]
