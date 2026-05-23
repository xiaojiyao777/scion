from __future__ import annotations

import uuid
from contextlib import nullcontext
from dataclasses import replace
from types import SimpleNamespace

from scion.config.problem import ProtocolConfig
from scion.core.branch_lifecycle_policy import (
    SCREENING_TELEMETRY_DIAGNOSTIC_RETRY,
    TELEMETRY_DIAGNOSTIC_NEGATIVE_DELTA,
    TELEMETRY_DIAGNOSTIC_STREAK_EXHAUSTED,
)
from scion.core.decision_coordinator import DecisionCoordinator
from scion.core.evaluation_orchestrator import EvaluationOrchestrator
from scion.core.features import BudgetState, SafeFeatureExtractor
from scion.core.models import (
    Branch,
    BranchState,
    CanaryResult,
    ChampionState,
    Decision,
    EvalStats,
    ExperimentStage,
    HypothesisProposal,
    OperatorConfig,
    ProtocolResult,
)


def _champion() -> ChampionState:
    return ChampionState(
        version=1,
        operator_pool={
            "solver": OperatorConfig(
                name="solver",
                file_path="solver.py",
                category="solver",
                weight=1.0,
                class_name="Solver",
            )
        },
        solver_config_hash="solver-hash",
        code_snapshot_path="/tmp/champion",
        code_snapshot_hash="champion-hash",
    )


def _hypothesis() -> HypothesisProposal:
    return HypothesisProposal(
        hypothesis_text="Add ILS perturbation and declare activation telemetry.",
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/scheduler.py",
        mechanism_changes=(),
    )


class _BranchController:
    soft_abandoned = False

    def next_stage(self, _branch_id: str) -> ExperimentStage:
        return ExperimentStage.SCREENING

    def apply_decision(self, _branch_id: str, _decision) -> None:
        self.soft_abandoned = True


class _Protocol:
    def run_canary(self, *_args, **_kwargs) -> CanaryResult:
        return CanaryResult(passed=True)

    def run_experiment(self, **_kwargs) -> ProtocolResult:
        return ProtocolResult(
            stage=ExperimentStage.SCREENING,
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
            reason_codes=("SCREENING_FAIL_WIN_RATE",),
            exposed_summary="screening failed",
            raw_metrics_ref="/tmp/metrics.json",
            candidate_surface_runtime_summary={
                "selected_surface": "solver_design",
                "telemetry_guard": {
                    "passed": False,
                    "candidate_runs": 16,
                    "failures": [
                        {
                            "code": (
                                "TELEMETRY_MECHANISM_ACTIVATION_NOT_OBSERVED"
                            ),
                            "severity": "fail",
                            "category": "activation",
                            "mechanism": "iterated_local_search_perturbation",
                            "field": "solver_algorithm_phase_runtime_ms.ils",
                            "candidate_missing": 16,
                            "candidate_present": 0,
                            "candidate_positive": 0,
                        }
                    ],
                },
            },
        )


class _ActivityTelemetryFailureProtocol:
    def run_canary(self, *_args, **_kwargs) -> CanaryResult:
        return CanaryResult(passed=True)

    def run_experiment(self, **_kwargs) -> ProtocolResult:
        return ProtocolResult(
            stage=ExperimentStage.SCREENING,
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
                "TELEMETRY_GUARD_FAILED",
                "TELEMETRY_ACTIVITY_FIELD_ALL_ZERO",
            ),
            exposed_summary="formal activity telemetry failed",
            raw_metrics_ref="/tmp/metrics.json",
            candidate_surface_runtime_summary={
                "selected_surface": "solver_design",
                "telemetry_guard": {
                    "passed": False,
                    "candidate_runs": 16,
                    "failures": [
                        {
                            "code": "TELEMETRY_ACTIVITY_FIELD_ALL_ZERO",
                            "severity": "fail",
                            "category": "activity",
                            "mechanism": "adaptive_vns_scheduler",
                            "field": "solver_algorithm_neutral_accepted_moves",
                            "runtime_role": "activity",
                            "candidate_missing": 0,
                            "candidate_present": 16,
                            "candidate_positive": 0,
                            "champion_positive": 16,
                        }
                    ],
                },
            },
        )


class _ActivityTelemetryRegressionProtocol(_ActivityTelemetryFailureProtocol):
    def run_experiment(self, **_kwargs) -> ProtocolResult:
        result = super().run_experiment(**_kwargs)
        return replace(
            result,
            stats=replace(
                result.stats,
                losses=14,
                ties=2,
                median_delta=-8.0,
                ci_low=-38.0,
                ci_high=-5.25,
            ),
        )


class _ActivityProtectedTelemetryFailureProtocol(_ActivityTelemetryFailureProtocol):
    def run_experiment(self, **_kwargs) -> ProtocolResult:
        result = super().run_experiment(**_kwargs)
        surface_summary = dict(result.candidate_surface_runtime_summary or {})
        guard = dict(surface_summary.get("telemetry_guard") or {})
        guard["failures"] = [
            *list(guard.get("failures") or ()),
            {
                "code": "TELEMETRY_PROTECTED_EFFECT_NOT_OBSERVED",
                "severity": "fail",
                "category": "effect",
                "runtime_role": "protected_outcome",
                "field": "solver_algorithm_feasibility_violation",
                "candidate_missing": 16,
                "candidate_present": 0,
                "candidate_positive": 0,
                "champion_positive": 16,
            },
        ]
        surface_summary["telemetry_guard"] = guard
        return replace(
            result,
            candidate_surface_runtime_summary=surface_summary,
        )


class _EffectTelemetryZeroProtocol:
    def run_canary(self, *_args, **_kwargs) -> CanaryResult:
        return CanaryResult(passed=True)

    def run_experiment(self, **_kwargs) -> ProtocolResult:
        return ProtocolResult(
            stage=ExperimentStage.SCREENING,
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
            reason_codes=("TELEMETRY_GUARD_FAILED",),
            exposed_summary="formal effect telemetry zero",
            raw_metrics_ref="/tmp/metrics.json",
            candidate_surface_runtime_summary={
                "selected_surface": "solver_design",
                "telemetry_guard": {
                    "passed": False,
                    "candidate_runs": 16,
                    "failures": [
                        {
                            "code": "TELEMETRY_MECHANISM_EFFECT_NOT_OBSERVED",
                            "severity": "fail",
                            "category": "effect",
                            "mechanism": "iterated_local_search_perturbation",
                            "field": "solver_algorithm_best_delta.ils",
                            "candidate_missing": 0,
                            "candidate_present": 16,
                            "candidate_positive": 0,
                        }
                    ],
                },
            },
        )


class _WeakPositiveProtocol:
    def run_canary(self, *_args, **_kwargs) -> CanaryResult:
        return CanaryResult(passed=True)

    def run_experiment(self, **_kwargs) -> ProtocolResult:
        return ProtocolResult(
            stage=ExperimentStage.SCREENING,
            stats=EvalStats(
                n_cases=8,
                wins=1,
                losses=0,
                ties=7,
                win_rate=0.125,
                median_delta=0.0,
                ci_low=0.0,
                ci_high=0.0,
                runtime_ratio_median=1.001,
                runtime_regression_rate=0.56,
                runtime_pairs=8,
                valid_pairs=8,
            ),
            gate_outcome="fail",
            reason_codes=("SCREENING_FAIL_WIN_RATE",),
            exposed_summary="weak positive screening signal",
            raw_metrics_ref="/tmp/metrics.json",
            candidate_surface_runtime_summary={
                "selected_surface": "solver_design",
                "telemetry_guard": {"passed": True, "candidate_runs": 8},
            },
        )


class _RegressiveLowMidProtocol:
    def run_canary(self, *_args, **_kwargs) -> CanaryResult:
        return CanaryResult(passed=True)

    def run_experiment(self, **_kwargs) -> ProtocolResult:
        return ProtocolResult(
            stage=ExperimentStage.SCREENING,
            stats=EvalStats(
                n_cases=10,
                wins=4,
                losses=3,
                ties=3,
                win_rate=0.4,
                median_delta=-0.01,
                ci_low=-0.02,
                ci_high=0.01,
                runtime_ratio_median=1.0,
                runtime_regression_rate=0.0,
                runtime_pairs=10,
                valid_pairs=10,
            ),
            gate_outcome="fail",
            reason_codes=("SCREENING_FAIL_WIN_RATE",),
            exposed_summary="low-mid regressive screening signal",
            raw_metrics_ref="/tmp/metrics.json",
            candidate_surface_runtime_summary={
                "selected_surface": "solver_design",
                "telemetry_guard": {"passed": True, "candidate_runs": 10},
            },
        )


class _RuntimeSlowLowMidProtocol:
    def run_canary(self, *_args, **_kwargs) -> CanaryResult:
        return CanaryResult(passed=True)

    def run_experiment(self, **_kwargs) -> ProtocolResult:
        return ProtocolResult(
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
                runtime_ratio_median=1.2,
                runtime_regression_rate=0.95,
                runtime_pairs=10,
                valid_pairs=10,
            ),
            gate_outcome="fail",
            reason_codes=("SCREENING_FAIL_WIN_RATE",),
            exposed_summary="low-mid runtime regression",
            raw_metrics_ref="/tmp/metrics.json",
            candidate_surface_runtime_summary={
                "selected_surface": "solver_design",
                "telemetry_guard": {"passed": True, "candidate_runs": 10},
            },
        )


def test_telemetry_repairable_does_not_soft_abandon_or_count_screened() -> None:
    branch = Branch(str(uuid.uuid4()), BranchState.EXPLORE, 1, "champ")
    branch_controller = _BranchController()
    experiment_count = 0
    telemetry_count = 0
    budget_used = 0

    def increment_experiment_count() -> None:
        nonlocal experiment_count
        experiment_count += 1

    def increment_telemetry_count() -> None:
        nonlocal telemetry_count
        telemetry_count += 1

    def increment_budget_used() -> None:
        nonlocal budget_used
        budget_used += 1

    orchestrator = EvaluationOrchestrator(
        branch_controller=branch_controller,
        champion_lock=nullcontext(),
        get_champion=_champion,
        branch_patches={},
        branch_workspaces={branch.branch_id: "/tmp/candidate"},
        branch_hypotheses={},
        branch_current_hypothesis={},
        experiment_protocol_provider=_Protocol,
        feature_extractor=SafeFeatureExtractor(),
        get_budget=lambda: BudgetState(total=4, used=0),
        decision_coordinator=DecisionCoordinator(config=ProtocolConfig()),
        decision_reason_codes={},
        campaign_id="campaign",
        registry=SimpleNamespace(record_event=lambda payload: None),
        materializer=SimpleNamespace(
            archive_workspace=lambda *args, **kwargs: None,
            cleanup=lambda *args, **kwargs: None,
        ),
        hypothesis_store=SimpleNamespace(mark_status=lambda *args: None),
        persist_branch_state=lambda _branch_id: None,
        begin_status_progress=lambda **_kwargs: None,
        end_status_progress=lambda: None,
        handle_failure=lambda *_args, **_kwargs: None,
        increment_experiment_count=increment_experiment_count,
        increment_budget_used=increment_budget_used,
        increment_soft_abandon_streak=lambda: None,
        increment_telemetry_failed_count=increment_telemetry_count,
    )

    decision, protocol_result, _canary = orchestrator.evaluate(
        branch,
        "/tmp/candidate",
        _hypothesis(),
    )

    assert decision == Decision.CONTINUE_EXPLORE
    assert protocol_result is not None
    assert "TELEMETRY_VALIDATION_REPAIRABLE" in protocol_result.reason_codes
    assert branch_controller.soft_abandoned is False
    assert experiment_count == 0
    assert telemetry_count == 1
    assert budget_used == 0


def test_formal_activity_all_zero_is_branch_local_diagnostic_not_abandon() -> None:
    branch = Branch(str(uuid.uuid4()), BranchState.EXPLORE, 1, "champ")
    branch_controller = _BranchController()
    experiment_count = 0
    telemetry_count = 0
    budget_used = 0
    decision_reason_codes: dict[str, tuple[str, ...]] = {}
    diagnostic_streaks: dict[str, int] = {}

    def increment_experiment_count() -> None:
        nonlocal experiment_count
        experiment_count += 1

    def increment_telemetry_count() -> None:
        nonlocal telemetry_count
        telemetry_count += 1

    def increment_budget_used() -> None:
        nonlocal budget_used
        budget_used += 1

    orchestrator = EvaluationOrchestrator(
        branch_controller=branch_controller,
        champion_lock=nullcontext(),
        get_champion=_champion,
        branch_patches={},
        branch_workspaces={branch.branch_id: "/tmp/candidate"},
        branch_hypotheses={},
        branch_current_hypothesis={},
        experiment_protocol_provider=_ActivityTelemetryFailureProtocol,
        feature_extractor=SafeFeatureExtractor(),
        get_budget=lambda: BudgetState(total=4, used=0),
        decision_coordinator=DecisionCoordinator(config=ProtocolConfig()),
        decision_reason_codes=decision_reason_codes,
        campaign_id="campaign",
        registry=SimpleNamespace(record_event=lambda payload: None),
        materializer=SimpleNamespace(
            archive_workspace=lambda *args, **kwargs: None,
            cleanup=lambda *args, **kwargs: None,
        ),
        hypothesis_store=SimpleNamespace(mark_status=lambda *args: None),
        persist_branch_state=lambda _branch_id: None,
        begin_status_progress=lambda **_kwargs: None,
        end_status_progress=lambda: None,
        handle_failure=lambda *_args, **_kwargs: None,
        increment_experiment_count=increment_experiment_count,
        increment_budget_used=increment_budget_used,
        increment_soft_abandon_streak=lambda: None,
        increment_telemetry_failed_count=increment_telemetry_count,
        branch_telemetry_diagnostic_streaks=diagnostic_streaks,
    )

    decision, protocol_result, _canary = orchestrator.evaluate(
        branch,
        "/tmp/candidate",
        _hypothesis(),
    )

    assert decision == Decision.CONTINUE_EXPLORE
    assert protocol_result is not None
    assert "TELEMETRY_ACTIVITY_FIELD_ALL_ZERO" in protocol_result.reason_codes
    assert decision_reason_codes[branch.branch_id] == (
        "TELEMETRY_VALIDATION_REPAIRABLE",
        "SCREENING_TELEMETRY_REPAIRABLE",
        SCREENING_TELEMETRY_DIAGNOSTIC_RETRY,
    )
    assert branch_controller.soft_abandoned is False
    assert diagnostic_streaks[branch.branch_id] == 1
    assert experiment_count == 0
    assert telemetry_count == 1
    assert budget_used == 0


def test_activity_all_zero_with_quality_regression_still_abandons() -> None:
    branch = Branch(str(uuid.uuid4()), BranchState.EXPLORE, 1, "champ")
    branch_controller = _BranchController()
    workspaces = {branch.branch_id: "/tmp/candidate"}
    decision_reason_codes: dict[str, tuple[str, ...]] = {}

    orchestrator = EvaluationOrchestrator(
        branch_controller=branch_controller,
        champion_lock=nullcontext(),
        get_champion=_champion,
        branch_patches={},
        branch_workspaces=workspaces,
        branch_hypotheses={},
        branch_current_hypothesis={},
        experiment_protocol_provider=_ActivityTelemetryRegressionProtocol,
        feature_extractor=SafeFeatureExtractor(),
        get_budget=lambda: BudgetState(total=4, used=0),
        decision_coordinator=DecisionCoordinator(config=ProtocolConfig()),
        decision_reason_codes=decision_reason_codes,
        campaign_id="campaign",
        registry=SimpleNamespace(record_event=lambda payload: None),
        materializer=SimpleNamespace(
            archive_workspace=lambda *args, **kwargs: None,
            cleanup=lambda *args, **kwargs: None,
        ),
        hypothesis_store=SimpleNamespace(mark_status=lambda *args: None),
        persist_branch_state=lambda _branch_id: None,
        begin_status_progress=lambda **_kwargs: None,
        end_status_progress=lambda: None,
        handle_failure=lambda *_args, **_kwargs: None,
        increment_experiment_count=lambda: None,
        increment_budget_used=lambda: None,
        increment_soft_abandon_streak=lambda: None,
        increment_telemetry_failed_count=lambda: None,
    )

    decision, protocol_result, _canary = orchestrator.evaluate(
        branch,
        "/tmp/candidate",
        _hypothesis(),
    )

    assert decision == Decision.ABANDON
    assert protocol_result is not None
    assert branch_controller.soft_abandoned is True
    assert branch.branch_id not in workspaces
    assert decision_reason_codes[branch.branch_id] == (
        "TELEMETRY_VALIDATION_REPAIRABLE",
        "SCREENING_TELEMETRY_REPAIRABLE",
        TELEMETRY_DIAGNOSTIC_NEGATIVE_DELTA,
    )


def test_activity_all_zero_mixed_with_protected_failure_abandons_fail_closed() -> None:
    branch = Branch(str(uuid.uuid4()), BranchState.EXPLORE, 1, "champ")
    branch_controller = _BranchController()
    experiment_count = 0
    telemetry_count = 0
    budget_used = 0
    decision_reason_codes: dict[str, tuple[str, ...]] = {}

    def increment_experiment_count() -> None:
        nonlocal experiment_count
        experiment_count += 1

    def increment_telemetry_count() -> None:
        nonlocal telemetry_count
        telemetry_count += 1

    def increment_budget_used() -> None:
        nonlocal budget_used
        budget_used += 1

    orchestrator = EvaluationOrchestrator(
        branch_controller=branch_controller,
        champion_lock=nullcontext(),
        get_champion=_champion,
        branch_patches={},
        branch_workspaces={branch.branch_id: "/tmp/candidate"},
        branch_hypotheses={},
        branch_current_hypothesis={},
        experiment_protocol_provider=_ActivityProtectedTelemetryFailureProtocol,
        feature_extractor=SafeFeatureExtractor(),
        get_budget=lambda: BudgetState(total=4, used=0),
        decision_coordinator=DecisionCoordinator(config=ProtocolConfig()),
        decision_reason_codes=decision_reason_codes,
        campaign_id="campaign",
        registry=SimpleNamespace(record_event=lambda payload: None),
        materializer=SimpleNamespace(
            archive_workspace=lambda *args, **kwargs: None,
            cleanup=lambda *args, **kwargs: None,
        ),
        hypothesis_store=SimpleNamespace(mark_status=lambda *args: None),
        persist_branch_state=lambda _branch_id: None,
        begin_status_progress=lambda **_kwargs: None,
        end_status_progress=lambda: None,
        handle_failure=lambda *_args, **_kwargs: None,
        increment_experiment_count=increment_experiment_count,
        increment_budget_used=increment_budget_used,
        increment_soft_abandon_streak=lambda: None,
        increment_telemetry_failed_count=increment_telemetry_count,
    )

    decision, protocol_result, _canary = orchestrator.evaluate(
        branch,
        "/tmp/candidate",
        _hypothesis(),
    )

    assert decision == Decision.ABANDON
    assert protocol_result is not None
    assert "TELEMETRY_VALIDATION_REPAIRABLE" not in protocol_result.reason_codes
    assert experiment_count == 1
    assert telemetry_count == 1
    assert budget_used == 1
    assert decision_reason_codes[branch.branch_id] == ("SCREENING_TELEMETRY_FAILED",)


def test_formal_effect_zero_is_branch_local_diagnostic_not_abandon() -> None:
    branch = Branch(str(uuid.uuid4()), BranchState.EXPLORE, 1, "champ")
    branch_controller = _BranchController()
    experiment_count = 0
    telemetry_count = 0
    budget_used = 0
    decision_reason_codes: dict[str, tuple[str, ...]] = {}
    diagnostic_streaks: dict[str, int] = {}

    def increment_experiment_count() -> None:
        nonlocal experiment_count
        experiment_count += 1

    def increment_telemetry_count() -> None:
        nonlocal telemetry_count
        telemetry_count += 1

    def increment_budget_used() -> None:
        nonlocal budget_used
        budget_used += 1

    orchestrator = EvaluationOrchestrator(
        branch_controller=branch_controller,
        champion_lock=nullcontext(),
        get_champion=_champion,
        branch_patches={},
        branch_workspaces={branch.branch_id: "/tmp/candidate"},
        branch_hypotheses={},
        branch_current_hypothesis={},
        experiment_protocol_provider=_EffectTelemetryZeroProtocol,
        feature_extractor=SafeFeatureExtractor(),
        get_budget=lambda: BudgetState(total=4, used=0),
        decision_coordinator=DecisionCoordinator(config=ProtocolConfig()),
        decision_reason_codes=decision_reason_codes,
        campaign_id="campaign",
        registry=SimpleNamespace(record_event=lambda payload: None),
        materializer=SimpleNamespace(
            archive_workspace=lambda *args, **kwargs: None,
            cleanup=lambda *args, **kwargs: None,
        ),
        hypothesis_store=SimpleNamespace(mark_status=lambda *args: None),
        persist_branch_state=lambda _branch_id: None,
        begin_status_progress=lambda **_kwargs: None,
        end_status_progress=lambda: None,
        handle_failure=lambda *_args, **_kwargs: None,
        increment_experiment_count=increment_experiment_count,
        increment_budget_used=increment_budget_used,
        increment_soft_abandon_streak=lambda: None,
        increment_telemetry_failed_count=increment_telemetry_count,
        branch_telemetry_diagnostic_streaks=diagnostic_streaks,
    )

    decision, protocol_result, _canary = orchestrator.evaluate(
        branch,
        "/tmp/candidate",
        _hypothesis(),
    )

    assert decision == Decision.CONTINUE_EXPLORE
    assert protocol_result is not None
    assert "TELEMETRY_MECHANISM_EFFECT_NOT_OBSERVED" in protocol_result.reason_codes
    assert decision_reason_codes[branch.branch_id] == (
        "TELEMETRY_VALIDATION_REPAIRABLE",
        "SCREENING_TELEMETRY_REPAIRABLE",
        SCREENING_TELEMETRY_DIAGNOSTIC_RETRY,
    )
    assert branch_controller.soft_abandoned is False
    assert diagnostic_streaks[branch.branch_id] == 1
    assert experiment_count == 0
    assert telemetry_count == 1
    assert budget_used == 0


def test_repeated_telemetry_diagnostic_can_soft_abandon() -> None:
    branch = Branch(str(uuid.uuid4()), BranchState.EXPLORE, 1, "champ")
    branch_controller = _BranchController()
    workspaces = {branch.branch_id: "/tmp/candidate"}
    decision_reason_codes: dict[str, tuple[str, ...]] = {}
    diagnostic_streaks = {branch.branch_id: 2}

    orchestrator = EvaluationOrchestrator(
        branch_controller=branch_controller,
        champion_lock=nullcontext(),
        get_champion=_champion,
        branch_patches={},
        branch_workspaces=workspaces,
        branch_hypotheses={},
        branch_current_hypothesis={},
        experiment_protocol_provider=_EffectTelemetryZeroProtocol,
        feature_extractor=SafeFeatureExtractor(),
        get_budget=lambda: BudgetState(total=4, used=0),
        decision_coordinator=DecisionCoordinator(config=ProtocolConfig()),
        decision_reason_codes=decision_reason_codes,
        campaign_id="campaign",
        registry=SimpleNamespace(record_event=lambda payload: None),
        materializer=SimpleNamespace(
            archive_workspace=lambda *args, **kwargs: None,
            cleanup=lambda *args, **kwargs: None,
        ),
        hypothesis_store=SimpleNamespace(mark_status=lambda *args: None),
        persist_branch_state=lambda _branch_id: None,
        begin_status_progress=lambda **_kwargs: None,
        end_status_progress=lambda: None,
        handle_failure=lambda *_args, **_kwargs: None,
        increment_experiment_count=lambda: None,
        increment_budget_used=lambda: None,
        increment_soft_abandon_streak=lambda: None,
        increment_telemetry_failed_count=lambda: None,
        branch_telemetry_diagnostic_streaks=diagnostic_streaks,
    )

    decision, protocol_result, _canary = orchestrator.evaluate(
        branch,
        "/tmp/candidate",
        _hypothesis(),
    )

    assert decision == Decision.ABANDON
    assert protocol_result is not None
    assert branch_controller.soft_abandoned is True
    assert branch.branch_id not in workspaces
    assert decision_reason_codes[branch.branch_id] == (
        "TELEMETRY_VALIDATION_REPAIRABLE",
        "SCREENING_TELEMETRY_REPAIRABLE",
        TELEMETRY_DIAGNOSTIC_STREAK_EXHAUSTED,
    )


def test_weak_positive_low_win_screening_continues_without_soft_abandon() -> None:
    branch = Branch(str(uuid.uuid4()), BranchState.EXPLORE, 1, "champ")
    branch_controller = _BranchController()
    experiment_count = 0
    telemetry_count = 0
    budget_used = 0
    decision_reason_codes: dict[str, tuple[str, ...]] = {}

    def increment_experiment_count() -> None:
        nonlocal experiment_count
        experiment_count += 1

    def increment_telemetry_count() -> None:
        nonlocal telemetry_count
        telemetry_count += 1

    def increment_budget_used() -> None:
        nonlocal budget_used
        budget_used += 1

    orchestrator = EvaluationOrchestrator(
        branch_controller=branch_controller,
        champion_lock=nullcontext(),
        get_champion=_champion,
        branch_patches={},
        branch_workspaces={branch.branch_id: "/tmp/candidate"},
        branch_hypotheses={},
        branch_current_hypothesis={},
        experiment_protocol_provider=_WeakPositiveProtocol,
        feature_extractor=SafeFeatureExtractor(),
        get_budget=lambda: BudgetState(total=4, used=0),
        decision_coordinator=DecisionCoordinator(config=ProtocolConfig()),
        decision_reason_codes=decision_reason_codes,
        campaign_id="campaign",
        registry=SimpleNamespace(record_event=lambda payload: None),
        materializer=SimpleNamespace(
            archive_workspace=lambda *args, **kwargs: None,
            cleanup=lambda *args, **kwargs: None,
        ),
        hypothesis_store=SimpleNamespace(mark_status=lambda *args: None),
        persist_branch_state=lambda _branch_id: None,
        begin_status_progress=lambda **_kwargs: None,
        end_status_progress=lambda: None,
        handle_failure=lambda *_args, **_kwargs: None,
        increment_experiment_count=increment_experiment_count,
        increment_budget_used=increment_budget_used,
        increment_soft_abandon_streak=lambda: None,
        increment_telemetry_failed_count=increment_telemetry_count,
        branch_zero_win_streaks={},
    )

    decision, protocol_result, _canary = orchestrator.evaluate(
        branch,
        "/tmp/candidate",
        _hypothesis(),
    )

    assert decision == Decision.CONTINUE_EXPLORE
    assert protocol_result is not None
    assert branch_controller.soft_abandoned is False
    assert experiment_count == 1
    assert telemetry_count == 0
    assert budget_used == 1
    assert decision_reason_codes[branch.branch_id] == (
        "SCREENING_FAIL_WIN_RATE",
        "SCREENING_WEAK_SIGNAL_CONTINUE",
    )


def test_low_mid_regressive_screening_soft_abandons_and_discards_workspace() -> None:
    branch = Branch(str(uuid.uuid4()), BranchState.EXPLORE, 1, "champ")
    branch_controller = _BranchController()
    workspaces = {branch.branch_id: "/tmp/candidate"}
    decision_reason_codes: dict[str, tuple[str, ...]] = {}

    orchestrator = EvaluationOrchestrator(
        branch_controller=branch_controller,
        champion_lock=nullcontext(),
        get_champion=_champion,
        branch_patches={},
        branch_workspaces=workspaces,
        branch_hypotheses={},
        branch_current_hypothesis={},
        experiment_protocol_provider=_RegressiveLowMidProtocol,
        feature_extractor=SafeFeatureExtractor(),
        get_budget=lambda: BudgetState(total=4, used=0),
        decision_coordinator=DecisionCoordinator(config=ProtocolConfig()),
        decision_reason_codes=decision_reason_codes,
        campaign_id="campaign",
        registry=SimpleNamespace(record_event=lambda payload: None),
        materializer=SimpleNamespace(
            archive_workspace=lambda *args, **kwargs: None,
            cleanup=lambda *args, **kwargs: None,
        ),
        hypothesis_store=SimpleNamespace(mark_status=lambda *args: None),
        persist_branch_state=lambda _branch_id: None,
        begin_status_progress=lambda **_kwargs: None,
        end_status_progress=lambda: None,
        handle_failure=lambda *_args, **_kwargs: None,
        increment_experiment_count=lambda: None,
        increment_budget_used=lambda: None,
        increment_soft_abandon_streak=lambda: None,
        increment_telemetry_failed_count=lambda: None,
        branch_zero_win_streaks={},
    )

    decision, protocol_result, _canary = orchestrator.evaluate(
        branch,
        "/tmp/candidate",
        _hypothesis(),
    )

    assert decision == Decision.ABANDON
    assert protocol_result is not None
    assert branch_controller.soft_abandoned is True
    assert branch.branch_id not in workspaces
    assert decision_reason_codes[branch.branch_id] == (
        "SCREENING_FAIL_WIN_RATE",
        "SCREENING_SOFT_ABANDON_NEGATIVE_DELTA",
    )


def test_low_mid_runtime_regression_soft_abandons_and_discards_workspace() -> None:
    branch = Branch(str(uuid.uuid4()), BranchState.EXPLORE, 1, "champ")
    branch_controller = _BranchController()
    workspaces = {branch.branch_id: "/tmp/candidate"}
    decision_reason_codes: dict[str, tuple[str, ...]] = {}

    orchestrator = EvaluationOrchestrator(
        branch_controller=branch_controller,
        champion_lock=nullcontext(),
        get_champion=_champion,
        branch_patches={},
        branch_workspaces=workspaces,
        branch_hypotheses={},
        branch_current_hypothesis={},
        experiment_protocol_provider=_RuntimeSlowLowMidProtocol,
        feature_extractor=SafeFeatureExtractor(),
        get_budget=lambda: BudgetState(total=4, used=0),
        decision_coordinator=DecisionCoordinator(config=ProtocolConfig()),
        decision_reason_codes=decision_reason_codes,
        campaign_id="campaign",
        registry=SimpleNamespace(record_event=lambda payload: None),
        materializer=SimpleNamespace(
            archive_workspace=lambda *args, **kwargs: None,
            cleanup=lambda *args, **kwargs: None,
        ),
        hypothesis_store=SimpleNamespace(mark_status=lambda *args: None),
        persist_branch_state=lambda _branch_id: None,
        begin_status_progress=lambda **_kwargs: None,
        end_status_progress=lambda: None,
        handle_failure=lambda *_args, **_kwargs: None,
        increment_experiment_count=lambda: None,
        increment_budget_used=lambda: None,
        increment_soft_abandon_streak=lambda: None,
        increment_telemetry_failed_count=lambda: None,
        branch_zero_win_streaks={},
    )

    decision, protocol_result, _canary = orchestrator.evaluate(
        branch,
        "/tmp/candidate",
        _hypothesis(),
    )

    assert decision == Decision.ABANDON
    assert protocol_result is not None
    assert branch_controller.soft_abandoned is True
    assert branch.branch_id not in workspaces
    assert decision_reason_codes[branch.branch_id] == (
        "SCREENING_FAIL_WIN_RATE",
        "SCREENING_SOFT_ABANDON_RUNTIME_SLOWDOWN",
        "SCREENING_SOFT_ABANDON_RUNTIME_REGRESSION_RATE",
    )
