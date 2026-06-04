from __future__ import annotations

from scion.core.branch import BranchController
from scion.core.branch_lifecycle_policy import (
    SCREENING_ACTIVE_PAIR_WINS_BUT_CASE_FAIL,
    SCREENING_WEAK_SIGNAL_CONTINUE,
)
from scion.core.decision_finalizer import DecisionFinalizer
from scion.core.models import (
    BranchState,
    CanaryResult,
    ChampionState,
    ContractResult,
    Decision,
    EvalStats,
    ExperimentStage,
    HypothesisProposal,
    HypothesisRecord,
    MechanismChange,
    PairwiseCaseFeedback,
    PatchProposal,
    ProtocolResult,
    VerificationResult,
)
from scion.core.telemetry_validation import (
    TELEMETRY_VALIDATION_REPAIRABLE,
    VALIDATION_TELEMETRY_REPAIRABLE,
)
from scion.tests.unit.core.decision_finalizer_lifecycle_test_support import (
    _HypothesisStore,
)


def test_win_skewed_weak_positive_screening_workspace_reason_is_positive() -> None:
    controller = BranchController()
    branch = controller.create_branch(
        ChampionState(
            version=1,
            operator_pool={},
            solver_config_hash="solver",
            code_snapshot_path="/tmp/champion",
            code_snapshot_hash="champion",
        )
    )
    hypothesis = HypothesisProposal(
        hypothesis_text="Tune a bounded repair ordering.",
        change_locus="repair",
        action="modify",
        mechanism_changes=(
            MechanismChange(id="repair_ordering", change_type="modify"),
        ),
    )
    h_record = HypothesisRecord(
        hypothesis_id="h-weak-positive",
        branch_id=branch.branch_id,
        change_locus="repair",
        action="modify",
        status="running",
    )
    patch = PatchProposal(
        file_path="solver.py",
        action="modify",
        code_content="# candidate\n",
    )
    workspaces = {branch.branch_id: "/tmp/workspace"}
    patches = {branch.branch_id: patch}
    hyp_store = _HypothesisStore()
    discarded: list[str] = []

    finalizer = DecisionFinalizer(
        branch_controller=controller,
        branch_store=None,
        hypothesis_store=hyp_store,
        branch_workspaces=workspaces,
        branch_hypotheses={branch.branch_id: hypothesis},
        branch_patches=patches,
        branch_current_hypothesis={branch.branch_id: h_record},
        branch_zero_win_streaks={},
        prepare_promoted_champion=lambda _branch: None,  # type: ignore[arg-type]
        require_promotable_branch=lambda _branch: None,
        commit_promote_plan=lambda _plan: None,
        handle_failure=lambda *_args, **_kwargs: None,
        record_hard_abandon=lambda *_args: None,
        record_step_lineage=lambda *_args, **_kwargs: None,
        decision_reason_codes_for=lambda *_args: None,
        discard_branch_workspace=lambda branch_id: discarded.append(branch_id),
        archive_workspace=lambda *_args: None,
        cleanup_workspace=lambda *_args: None,
        persist_branch_state=lambda _branch_id: None,
        reset_recent_abandoned_count=lambda: None,
    )
    protocol = ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=EvalStats(
            n_cases=12,
            wins=4,
            losses=1,
            ties=7,
            win_rate=1 / 3,
            median_delta=0.0,
            ci_low=0.0,
            ci_high=4.0,
            candidate_failed_pairs=0,
            runtime_pairs=12,
            runtime_ratio_median=1.0,
            runtime_regression_rate=0.0,
        ),
        gate_outcome="fail",
        reason_codes=("SCREENING_FAIL_WIN_RATE",),
        exposed_summary="win-skewed weak-positive follow-up",
        raw_metrics_ref="/tmp/metrics.json",
    )

    result = finalizer.apply(
        branch=branch,
        decision=Decision.CONTINUE_EXPLORE,
        hypothesis=hypothesis,
        h_record=h_record,
        protocol_result=protocol,
        canary_result=CanaryResult(passed=True),
        contract_result=ContractResult(passed=True, checks=()),
        verification_result=VerificationResult(passed=True, checks=()),
        action_label="screening",
        decision_reason_codes=(
            "SCREENING_FAIL_WIN_RATE",
            SCREENING_WEAK_SIGNAL_CONTINUE,
        ),
    )

    stored = controller.get_branch(branch.branch_id)

    assert result.decision == Decision.CONTINUE_EXPLORE
    assert "weak-positive screening signal" in result.reason
    assert stored.branch_code_status == "active_weak_positive"
    assert stored.last_screening_feedback_tier == "weak_positive"
    assert discarded == []
    assert hyp_store.statuses == [
        ("h-weak-positive", "screening_weak_positive_retained")
    ]


def test_pair_level_weak_positive_screening_workspace_is_retained() -> None:
    controller = BranchController()
    branch = controller.create_branch(
        ChampionState(
            version=1,
            operator_pool={},
            solver_config_hash="solver",
            code_snapshot_path="/tmp/champion",
            code_snapshot_hash="champion",
        )
    )
    hypothesis = HypothesisProposal(
        hypothesis_text="Tune a bounded decision lever.",
        change_locus="decision",
        action="modify",
        mechanism_changes=(
            MechanismChange(id="bounded_decision_lever", change_type="modify"),
        ),
    )
    h_record = HypothesisRecord(
        hypothesis_id="h-pair-weak-positive",
        branch_id=branch.branch_id,
        change_locus="decision",
        action="modify",
        status="running",
    )
    patch = PatchProposal(
        file_path="solver.py",
        action="modify",
        code_content="# candidate\n",
    )
    workspaces = {branch.branch_id: "/tmp/workspace"}
    hyp_store = _HypothesisStore()
    discarded: list[str] = []

    finalizer = DecisionFinalizer(
        branch_controller=controller,
        branch_store=None,
        hypothesis_store=hyp_store,
        branch_workspaces=workspaces,
        branch_hypotheses={branch.branch_id: hypothesis},
        branch_patches={branch.branch_id: patch},
        branch_current_hypothesis={branch.branch_id: h_record},
        branch_zero_win_streaks={},
        prepare_promoted_champion=lambda _branch: None,  # type: ignore[arg-type]
        require_promotable_branch=lambda _branch: None,
        commit_promote_plan=lambda _plan: None,
        handle_failure=lambda *_args, **_kwargs: None,
        record_hard_abandon=lambda *_args: None,
        record_step_lineage=lambda *_args, **_kwargs: None,
        decision_reason_codes_for=lambda *_args: None,
        discard_branch_workspace=lambda branch_id: discarded.append(branch_id),
        archive_workspace=lambda *_args: None,
        cleanup_workspace=lambda *_args: None,
        persist_branch_state=lambda _branch_id: None,
        reset_recent_abandoned_count=lambda: None,
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
            candidate_failed_pairs=0,
            runtime_pairs=4,
            runtime_ratio_median=1.0,
            runtime_regression_rate=0.0,
        ),
        gate_outcome="fail",
        reason_codes=("SCREENING_FAIL_WIN_RATE",),
        exposed_summary="pair-level weak-positive follow-up",
        raw_metrics_ref="/tmp/metrics.json",
        pair_feedback=(
            PairwiseCaseFeedback(case_id="case-a", seed=1, comparison="win", delta=1.0),
            PairwiseCaseFeedback(case_id="case-b", seed=1, comparison="tie", delta=0.0),
            PairwiseCaseFeedback(case_id="case-c", seed=1, comparison="tie", delta=0.0),
            PairwiseCaseFeedback(case_id="case-d", seed=1, comparison="tie", delta=0.0),
        ),
    )

    result = finalizer.apply(
        branch=branch,
        decision=Decision.CONTINUE_EXPLORE,
        hypothesis=hypothesis,
        h_record=h_record,
        protocol_result=protocol,
        canary_result=CanaryResult(passed=True),
        contract_result=ContractResult(passed=True, checks=()),
        verification_result=VerificationResult(passed=True, checks=()),
        action_label="screening",
        decision_reason_codes=(
            "SCREENING_FAIL_WIN_RATE",
            SCREENING_ACTIVE_PAIR_WINS_BUT_CASE_FAIL,
        ),
    )

    stored = controller.get_branch(branch.branch_id)

    assert result.decision == Decision.CONTINUE_EXPLORE
    assert "weak-positive screening signal" in result.reason
    assert stored.branch_code_status == "active_weak_positive"
    assert stored.last_screening_feedback_tier == "weak_positive"
    assert stored.branch_evidence_summary["runtime_evidence_pressure_count"] == 0
    assert discarded == []
    assert hyp_store.statuses == [
        ("h-pair-weak-positive", "screening_weak_positive_retained")
    ]


def test_continue_explore_discards_candidate_failed_screening_workspace() -> None:
    controller = BranchController()
    branch = controller.create_branch(
        ChampionState(
            version=1,
            operator_pool={},
            solver_config_hash="solver",
            code_snapshot_path="/tmp/champion",
            code_snapshot_hash="champion",
        )
    )
    hypothesis = HypothesisProposal(
        hypothesis_text="Tune a bounded repair ordering.",
        change_locus="repair",
        action="modify",
        mechanism_changes=(
            MechanismChange(id="repair_ordering", change_type="modify"),
        ),
    )
    h_record = HypothesisRecord(
        hypothesis_id="h-2",
        branch_id=branch.branch_id,
        change_locus="repair",
        action="modify",
        status="running",
    )
    patch = PatchProposal(
        file_path="solver.py",
        action="modify",
        code_content="# candidate\n",
    )
    workspaces = {branch.branch_id: "/tmp/workspace"}
    patches = {branch.branch_id: patch}
    hypotheses = {branch.branch_id: hypothesis}
    current_hypothesis = {branch.branch_id: h_record}
    zero_win_streaks: dict[str, int] = {}
    discarded: list[str] = []
    hyp_store = _HypothesisStore()

    finalizer = DecisionFinalizer(
        branch_controller=controller,
        branch_store=None,
        hypothesis_store=hyp_store,
        branch_workspaces=workspaces,
        branch_hypotheses=hypotheses,
        branch_patches=patches,
        branch_current_hypothesis=current_hypothesis,
        branch_zero_win_streaks=zero_win_streaks,
        prepare_promoted_champion=lambda _branch: None,  # type: ignore[arg-type]
        require_promotable_branch=lambda _branch: None,
        commit_promote_plan=lambda _plan: None,
        handle_failure=lambda *_args, **_kwargs: None,
        record_hard_abandon=lambda *_args: None,
        record_step_lineage=lambda *_args, **_kwargs: None,
        decision_reason_codes_for=lambda *_args: None,
        discard_branch_workspace=lambda branch_id: discarded.append(branch_id),
        archive_workspace=lambda *_args: None,
        cleanup_workspace=lambda *_args: None,
        persist_branch_state=lambda _branch_id: None,
        reset_recent_abandoned_count=lambda: None,
    )
    protocol = ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=EvalStats(
            n_cases=10,
            wins=4,
            losses=0,
            ties=6,
            win_rate=0.4,
            median_delta=0.0,
            ci_low=0.0,
            ci_high=0.0,
            runtime_ratio_median=1.0,
            valid_pairs=10,
            candidate_failed_pairs=1,
        ),
        gate_outcome="fail",
        reason_codes=("SCREENING_FAIL_WIN_RATE",),
        exposed_summary="candidate runtime failure",
        raw_metrics_ref="/tmp/metrics.json",
    )

    result = finalizer.apply(
        branch=branch,
        decision=Decision.CONTINUE_EXPLORE,
        hypothesis=hypothesis,
        h_record=h_record,
        protocol_result=protocol,
        canary_result=CanaryResult(passed=True),
        contract_result=ContractResult(passed=True, checks=()),
        verification_result=VerificationResult(passed=True, checks=()),
        action_label="screening",
        decision_reason_codes=(
            "SCREENING_FAIL_WIN_RATE",
            SCREENING_WEAK_SIGNAL_CONTINUE,
        ),
    )

    assert result.decision == Decision.CONTINUE_EXPLORE
    assert result.attempt_kind == "screening"
    assert discarded == [branch.branch_id]
    assert controller.get_branch(branch.branch_id).branch_code_status == "discarded"
    assert controller.get_branch(branch.branch_id).branch_mechanism_ids == (
        "repair_ordering",
    )
    assert branch.branch_id not in patches
    assert branch.branch_id in workspaces
    assert hyp_store.statuses == [("h-2", "rejected")]


def test_abandon_syncs_terminal_branch_evidence_before_lineage_and_persist() -> None:
    controller = BranchController()
    branch = controller.create_branch(
        ChampionState(
            version=1,
            operator_pool={},
            solver_config_hash="solver",
            code_snapshot_path="/tmp/champion",
            code_snapshot_hash="champion",
        )
    )
    hypothesis = HypothesisProposal(
        hypothesis_text="Try a bounded repair ordering.",
        change_locus="repair",
        action="modify",
        mechanism_changes=(
            MechanismChange(id="repair_ordering", change_type="modify"),
        ),
    )
    h_record = HypothesisRecord(
        hypothesis_id="h-abandon",
        branch_id=branch.branch_id,
        change_locus="repair",
        action="modify",
        status="running",
    )
    patch = PatchProposal(
        file_path="solver.py",
        action="modify",
        code_content="# candidate\n",
        mechanism_changes=(
            MechanismChange(id="candidate_filter_probe", change_type="modify"),
        ),
    )
    hyp_store = _HypothesisStore()
    persisted: list[dict] = []
    lineage_snapshots: list[tuple[str, dict]] = []

    class BranchStore:
        def save(self, saved_branch) -> None:
            persisted.append(dict(saved_branch.branch_evidence_summary))

    def record_lineage(*args, **_kwargs) -> None:
        recorded_branch = args[0]
        lineage_snapshots.append(
            (
                recorded_branch.branch_code_status,
                dict(recorded_branch.branch_evidence_summary),
            )
        )

    finalizer = DecisionFinalizer(
        branch_controller=controller,
        branch_store=BranchStore(),
        hypothesis_store=hyp_store,
        branch_workspaces={},
        branch_hypotheses={branch.branch_id: hypothesis},
        branch_patches={branch.branch_id: patch},
        branch_current_hypothesis={branch.branch_id: h_record},
        branch_zero_win_streaks={},
        prepare_promoted_champion=lambda _branch: None,  # type: ignore[arg-type]
        require_promotable_branch=lambda _branch: None,
        commit_promote_plan=lambda _plan: None,
        handle_failure=lambda *_args, **_kwargs: None,
        record_hard_abandon=lambda *_args: None,
        record_step_lineage=record_lineage,
        decision_reason_codes_for=lambda *_args: None,
        discard_branch_workspace=lambda _branch_id: None,
        archive_workspace=lambda *_args: None,
        cleanup_workspace=lambda *_args: None,
        persist_branch_state=lambda _branch_id: None,
        reset_recent_abandoned_count=lambda: None,
    )
    protocol = ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=EvalStats(
            n_cases=10,
            wins=0,
            losses=4,
            ties=6,
            win_rate=0.0,
            median_delta=-1.5,
            ci_low=-3.0,
            ci_high=-0.5,
        ),
        gate_outcome="fail",
        reason_codes=("SCREENING_FAIL_WIN_RATE",),
        exposed_summary="screening failed",
        raw_metrics_ref="/tmp/metrics.json",
    )

    result = finalizer.apply(
        branch=branch,
        decision=Decision.ABANDON,
        hypothesis=hypothesis,
        h_record=h_record,
        protocol_result=protocol,
        canary_result=CanaryResult(passed=True),
        contract_result=ContractResult(passed=True, checks=()),
        verification_result=VerificationResult(passed=True, checks=()),
        action_label="screening",
        decision_reason_codes=("SCREENING_FAIL_WIN_RATE",),
    )

    stored = controller.get_branch(branch.branch_id)
    assert result.decision == Decision.ABANDON
    assert stored.state == BranchState.ABANDONED
    assert stored.branch_code_status != "clean"
    assert stored.branch_mechanism_ids == (
        "repair_ordering",
        "candidate_filter_probe",
    )
    assert lineage_snapshots
    assert lineage_snapshots[0][0] == stored.branch_code_status
    assert lineage_snapshots[0][1]["terminal_reason"] == "SCREENING_FAIL_WIN_RATE"
    assert persisted[-1]["terminal_reason"] == "SCREENING_FAIL_WIN_RATE"
    assert persisted[-1]["losses"] == 4

def test_validation_telemetry_repairable_marks_wiring_suspect_without_reusing_workspace() -> None:
    controller = BranchController()
    branch = controller.create_branch(
        ChampionState(
            version=1,
            operator_pool={},
            solver_config_hash="solver",
            code_snapshot_path="/tmp/champion",
            code_snapshot_hash="champion",
        )
    )
    branch.state = BranchState.VALIDATING
    hypothesis = HypothesisProposal(
        hypothesis_text="Add missing activation telemetry.",
        change_locus="solver_design",
        action="modify",
        mechanism_changes=(
            MechanismChange(id="activation_probe", change_type="add"),
        ),
    )
    h_record = HypothesisRecord(
        hypothesis_id="h-3",
        branch_id=branch.branch_id,
        change_locus="solver_design",
        action="modify",
        status="running",
    )
    patch = PatchProposal(
        file_path="solver.py",
        action="modify",
        code_content="# candidate\n",
    )
    workspaces = {branch.branch_id: "/tmp/workspace"}
    patches = {branch.branch_id: patch}
    hypotheses = {branch.branch_id: hypothesis}
    current_hypothesis = {branch.branch_id: h_record}
    discarded: list[str] = []
    hyp_store = _HypothesisStore()

    finalizer = DecisionFinalizer(
        branch_controller=controller,
        branch_store=None,
        hypothesis_store=hyp_store,
        branch_workspaces=workspaces,
        branch_hypotheses=hypotheses,
        branch_patches=patches,
        branch_current_hypothesis=current_hypothesis,
        branch_zero_win_streaks={},
        prepare_promoted_champion=lambda _branch: None,  # type: ignore[arg-type]
        require_promotable_branch=lambda _branch: None,
        commit_promote_plan=lambda _plan: None,
        handle_failure=lambda *_args, **_kwargs: None,
        record_hard_abandon=lambda *_args: None,
        record_step_lineage=lambda *_args, **_kwargs: None,
        decision_reason_codes_for=lambda *_args: None,
        discard_branch_workspace=lambda branch_id: discarded.append(branch_id),
        archive_workspace=lambda *_args: None,
        cleanup_workspace=lambda *_args: None,
        persist_branch_state=lambda _branch_id: None,
        reset_recent_abandoned_count=lambda: None,
    )
    protocol = ProtocolResult(
        stage=ExperimentStage.VALIDATION,
        stats=EvalStats(
            n_cases=16,
            wins=0,
            losses=0,
            ties=16,
            win_rate=0.0,
            median_delta=0.0,
            ci_low=0.0,
            ci_high=0.0,
        ),
        gate_outcome="fail",
        reason_codes=(
            VALIDATION_TELEMETRY_REPAIRABLE,
            TELEMETRY_VALIDATION_REPAIRABLE,
            "TELEMETRY_MECHANISM_ACTIVATION_NOT_OBSERVED",
        ),
        exposed_summary="validation telemetry repairable",
        raw_metrics_ref="/tmp/metrics.json",
    )

    result = finalizer.apply(
        branch=branch,
        decision=Decision.VALIDATION_REPAIR_REQUIRED,
        hypothesis=hypothesis,
        h_record=h_record,
        protocol_result=protocol,
        canary_result=CanaryResult(passed=True),
        contract_result=ContractResult(passed=True, checks=()),
        verification_result=VerificationResult(passed=True, checks=()),
        action_label="validate",
        decision_reason_codes=(
            VALIDATION_TELEMETRY_REPAIRABLE,
            TELEMETRY_VALIDATION_REPAIRABLE,
        ),
    )

    assert result.decision == Decision.VALIDATION_REPAIR_REQUIRED
    assert result.counts_toward_max_rounds is False
    assert result.attempt_kind == "validation_repair_required"
    assert result.reason.startswith("VALIDATION_TELEMETRY_REPAIRABLE")
    assert "repair_policy=repair_first_same_mechanism_or_clean_fork" in result.reason
    assert "repair_mechanism_ids=activation_probe" in result.reason
    assert result.repair_mechanism_ids == ("activation_probe",)
    assert discarded == [branch.branch_id]
    assert branch.branch_id not in patches
    assert workspaces[branch.branch_id] == "/tmp/workspace"
    assert controller.get_branch(branch.branch_id).branch_code_status == (
        "telemetry_wiring_suspect"
    )
    assert controller.get_branch(branch.branch_id).last_telemetry_outcome == (
        "activation_missing_or_wiring_suspect"
    )
    assert controller.get_branch(branch.branch_id).telemetry_repair_mechanism_ids == (
        "activation_probe",
    )
    assert controller.get_branch(branch.branch_id).telemetry_repair_attempts == {
        "activation_probe": 1
    }
    assert hyp_store.statuses == [("h-3", "validation_telemetry_failed")]
    assert controller.get_branch(branch.branch_id).state == BranchState.EXPLORE

def test_screening_telemetry_repairable_marks_telemetry_failed_not_code_failed() -> None:
    controller = BranchController()
    branch = controller.create_branch(
        ChampionState(
            version=1,
            operator_pool={},
            solver_config_hash="solver",
            code_snapshot_path="/tmp/champion",
            code_snapshot_hash="champion",
        )
    )
    hypothesis = HypothesisProposal(
        hypothesis_text="Add missing activation telemetry.",
        change_locus="solver_design",
        action="modify",
        mechanism_changes=(
            MechanismChange(id="activation_probe", change_type="add"),
        ),
    )
    h_record = HypothesisRecord(
        hypothesis_id="h-4",
        branch_id=branch.branch_id,
        change_locus="solver_design",
        action="modify",
        status="running",
    )
    patch = PatchProposal(
        file_path="solver.py",
        action="modify",
        code_content="# candidate\n",
    )
    hyp_store = _HypothesisStore()
    discarded: list[str] = []

    finalizer = DecisionFinalizer(
        branch_controller=controller,
        branch_store=None,
        hypothesis_store=hyp_store,
        branch_workspaces={branch.branch_id: "/tmp/workspace"},
        branch_hypotheses={branch.branch_id: hypothesis},
        branch_patches={branch.branch_id: patch},
        branch_current_hypothesis={branch.branch_id: h_record},
        branch_zero_win_streaks={},
        prepare_promoted_champion=lambda _branch: None,  # type: ignore[arg-type]
        require_promotable_branch=lambda _branch: None,
        commit_promote_plan=lambda _plan: None,
        handle_failure=lambda *_args, **_kwargs: None,
        record_hard_abandon=lambda *_args: None,
        record_step_lineage=lambda *_args, **_kwargs: None,
        decision_reason_codes_for=lambda *_args: None,
        discard_branch_workspace=lambda branch_id: discarded.append(branch_id),
        archive_workspace=lambda *_args: None,
        cleanup_workspace=lambda *_args: None,
        persist_branch_state=lambda _branch_id: None,
        reset_recent_abandoned_count=lambda: None,
    )
    protocol = ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=EvalStats(
            n_cases=8,
            wins=0,
            losses=0,
            ties=8,
            win_rate=0.0,
            median_delta=0.0,
            ci_low=0.0,
            ci_high=0.0,
        ),
        gate_outcome="fail",
        reason_codes=(TELEMETRY_VALIDATION_REPAIRABLE,),
        exposed_summary="screening telemetry repairable",
        raw_metrics_ref="/tmp/metrics.json",
    )

    result = finalizer.apply(
        branch=branch,
        decision=Decision.CONTINUE_EXPLORE,
        hypothesis=hypothesis,
        h_record=h_record,
        protocol_result=protocol,
        canary_result=CanaryResult(passed=True),
        contract_result=ContractResult(passed=True, checks=()),
        verification_result=VerificationResult(passed=True, checks=()),
        action_label="screening",
        decision_reason_codes=(TELEMETRY_VALIDATION_REPAIRABLE,),
    )

    assert result.attempt_kind == "telemetry_repairable"
    assert result.counts_toward_max_rounds is False
    assert hyp_store.statuses == [("h-4", "screening_telemetry_failed")]
    assert discarded == [branch.branch_id]
