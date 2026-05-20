from __future__ import annotations

import uuid
from contextlib import nullcontext
from types import SimpleNamespace

from scion.config.problem import ProtocolConfig
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
