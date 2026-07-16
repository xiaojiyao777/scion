from __future__ import annotations

import uuid
from contextlib import nullcontext
from dataclasses import replace
from types import SimpleNamespace

import pytest

from scion.config.problem import ProtocolConfig
from scion.core.decision_coordinator import DecisionCoordinator
from scion.core.evaluation_orchestrator import (
    EvaluationInfrastructureError,
    EvaluationOrchestrator,
    _branch_followup_priority_cases,
)
from scion.core.execution_outcome import ExecutionOutcome
from scion.core.features import SafeFeatureExtractor
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
from scion.core.runtime_budget_diagnostics import (
    CANDIDATE_RUNTIME_BUDGET_SATURATION,
    SCREENING_RUNTIME_BUDGET_SATURATION,
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
    )


def test_branch_followup_priority_cases_prefer_losses_then_winners() -> None:
    branch = Branch(
        branch_id=str(uuid.uuid4()),
        state=BranchState.EXPLORE_EXPAND,
        base_champion_id=1,
        base_champion_hash="champion-hash",
    )
    branch.branch_evidence_summary = {
        "case_level_negative_cases": [
            {"case_id": "CMT2.vrp"},
            {"case_id": "CMT4.vrp"},
        ],
        "case_level_losses": [{"case_id": "CMT2.vrp"}],
        "case_level_positive_cases": [
            {"case_id": "A-n64-k9.vrp"},
            "E-n101-k14.vrp",
        ],
    }

    assert _branch_followup_priority_cases(branch) == (
        "CMT2.vrp",
        "CMT4.vrp",
        "A-n64-k9.vrp",
        "E-n101-k14.vrp",
    )


class _BranchController:
    def next_stage(self, _branch_id: str) -> ExperimentStage:
        return ExperimentStage.SCREENING

    def apply_decision(self, _branch_id: str, _decision) -> None:
        pass


class _FrozenBranchController(_BranchController):
    def next_stage(self, _branch_id: str) -> ExperimentStage:
        return ExperimentStage.FROZEN


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
                            "code": ("TELEMETRY_MECHANISM_ACTIVATION_NOT_OBSERVED"),
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


class _RecordingExpandProtocol:
    def __init__(self, events: list[tuple[object, ...]]) -> None:
        self.events = events

    def run_canary(self, *_args, **_kwargs) -> CanaryResult:
        return CanaryResult(passed=True)

    def run_experiment(self, **kwargs) -> ProtocolResult:
        stage = kwargs["stage"]
        self.events.append(
            (
                "evaluate",
                kwargs["expand"],
                kwargs["expand_round"],
                stage,
            )
        )
        return ProtocolResult(
            stage=stage,
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
            reason_codes=(
                "VALIDATION_FAIL_WIN_RATE"
                if stage is ExperimentStage.VALIDATION
                else "SCREENING_FAIL_WIN_RATE",
            ),
            exposed_summary="record expanded evaluation request",
            raw_metrics_ref="/tmp/metrics.json",
        )


class _RaisingProtocol:
    def run_canary(self, *_args, **_kwargs) -> CanaryResult:
        return CanaryResult(passed=True)

    def run_experiment(self, **_kwargs) -> ProtocolResult:
        raise RuntimeError("protocol boom")


class _InfraRaisingProtocol(_RaisingProtocol):
    def run_experiment(self, **_kwargs) -> ProtocolResult:
        raise EvaluationInfrastructureError("runner transport unavailable")


class _ChampionEvidenceBlockedProtocol:
    candidate_failed_pairs = 0
    champion_failed_pairs = 1

    def run_canary(self, *_args, **_kwargs) -> CanaryResult:
        return CanaryResult(passed=True)

    def run_experiment(self, **_kwargs) -> ProtocolResult:
        return ProtocolResult(
            stage=ExperimentStage.FROZEN,
            stats=EvalStats(
                n_cases=8,
                wins=5,
                losses=0,
                ties=3,
                win_rate=0.625,
                median_delta=81.5,
                ci_low=0.0,
                ci_high=337.0,
                total_pairs=24,
                attempted_pairs=24,
                valid_pairs=23,
                failed_pairs=1,
                candidate_failed_pairs=self.candidate_failed_pairs,
                champion_failed_pairs=self.champion_failed_pairs,
            ),
            gate_outcome="fail",
            reason_codes=(
                "INCOMPLETE_EVIDENCE",
                (
                    "CANDIDATE_RUNTIME_FAILURE"
                    if self.candidate_failed_pairs
                    else "CHAMPION_RUNTIME_FAILURE"
                ),
            ),
            exposed_summary="later-stage evidence incomplete",
            raw_metrics_ref="/tmp/frozen-partial-metrics.json",
        )


class _CandidateEvidenceFailureProtocol(_ChampionEvidenceBlockedProtocol):
    candidate_failed_pairs = 1
    champion_failed_pairs = 0


class _PathSafetyCanaryProtocol:
    def run_canary(self, *_args, **_kwargs) -> CanaryResult:
        return CanaryResult(
            passed=False,
            reason=(
                "canary configuration error: Unsafe case path in strict "
                "ExperimentProtocol: absolute_outside_roots outside workspace "
                "and safe_data_roots"
            ),
        )

    def run_experiment(self, **_kwargs) -> ProtocolResult:
        raise AssertionError("screening should not run after canary config failure")


class _OrdinaryFailingCanaryProtocol:
    def run_canary(self, *_args, **_kwargs) -> CanaryResult:
        return CanaryResult(
            passed=False,
            reason="Candidate infeasible on canary_x (champion was feasible)",
        )

    def run_experiment(self, **_kwargs) -> ProtocolResult:
        raise AssertionError("screening should not run after canary failure")


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
            reason_codes=("SCREENING_FAIL_WIN_RATE",),
            exposed_summary="formal effect telemetry zero with activation observed",
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
                            "diagnostic_type": ("mechanism_executed_no_improvement"),
                            "telemetry_outcome": "no_effect",
                            "repairable": False,
                            "candidate_missing": 0,
                            "candidate_present": 16,
                            "candidate_positive": 0,
                        }
                    ],
                    "mechanism_diagnostics": [
                        {
                            "mechanism": "iterated_local_search_perturbation",
                            "passed": True,
                            "diagnostic_type": ("mechanism_executed_no_improvement"),
                            "telemetry_outcome": "no_effect",
                            "activation_status": "observed",
                            "runtime_status": "observed",
                            "effect_status": "zero",
                            "activation_observed": True,
                            "runtime_observed": True,
                            "effect_observed": False,
                            "repair_guidance": [
                                "Mechanism executed but declared effect stayed zero."
                            ],
                        }
                    ],
                },
            },
        )


class _BudgetTelemetryStarvedProtocol:
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
            exposed_summary="formal budget telemetry starved",
            raw_metrics_ref="/tmp/metrics.json",
            candidate_surface_runtime_summary={
                "selected_surface": "solver_design",
                "telemetry_guard": {
                    "passed": False,
                    "candidate_runs": 16,
                    "failures": [
                        {
                            "code": "TELEMETRY_BUDGET_STARVED",
                            "severity": "fail",
                            "category": "budget",
                            "runtime_role": "budget",
                            "mechanism": "sa_reheat_on_stagnation",
                            "field": (
                                "solver_algorithm_phase_runtime_ms."
                                "sa_reheat_on_stagnation"
                            ),
                            "candidate_missing": 13,
                            "candidate_present": 3,
                            "candidate_positive": 0,
                            "champion_positive": 0,
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


class _RuntimeBudgetSaturationProtocol(_WeakPositiveProtocol):
    def run_experiment(self, **_kwargs) -> ProtocolResult:
        result = super().run_experiment(**_kwargs)
        surface_summary = dict(result.candidate_surface_runtime_summary or {})
        surface_summary["runtime_budget_diagnostic"] = {
            "schema": "scion.runtime_budget_diagnostic.v1",
            "code": SCREENING_RUNTIME_BUDGET_SATURATION,
            "stage": "screening",
            "severity": "warn",
            "repairable": True,
            "total_pairs": 8,
            "threshold_ratio": 0.9,
            "saturation_ratio": 0.96,
            "saturated_side": "candidate",
            "reason_codes": [CANDIDATE_RUNTIME_BUDGET_SATURATION],
        }
        return replace(
            result,
            candidate_surface_runtime_summary=surface_summary,
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


@pytest.mark.parametrize(
    (
        "branch_state",
        "initial_screening_count",
        "initial_validation_count",
        "effective_screening_count",
        "effective_validation_count",
        "expected_expand",
        "expected_expand_round",
        "expected_stage",
    ),
    (
        (BranchState.EXPLORE_EXPAND, 2, 4, 3, 4, True, 3, ExperimentStage.SCREENING),
        (
            BranchState.VALIDATING_EXPAND,
            2,
            4,
            2,
            5,
            True,
            5,
            ExperimentStage.VALIDATION,
        ),
        (BranchState.EXPLORE, 2, 4, 2, 4, False, 1, ExperimentStage.SCREENING),
    ),
)
def test_expand_uses_effective_count_without_mutating_persisted_source(
    branch_state: BranchState,
    initial_screening_count: int,
    initial_validation_count: int,
    effective_screening_count: int,
    effective_validation_count: int,
    expected_expand: bool,
    expected_expand_round: int,
    expected_stage: ExperimentStage,
) -> None:
    branch = Branch(
        str(uuid.uuid4()),
        branch_state,
        1,
        "champ",
        screening_expand_count=initial_screening_count,
        validation_expand_count=initial_validation_count,
    )
    events: list[tuple[object, ...]] = []
    protocol = _RecordingExpandProtocol(events)

    def persist_branch_state(branch_id: str) -> None:
        assert branch_id == branch.branch_id
        events.append(
            (
                "persist",
                branch.screening_expand_count,
                branch.validation_expand_count,
                branch.weight_revision,
            )
        )

    orchestrator = EvaluationOrchestrator(
        branch_controller=_BranchController(),
        champion_lock=nullcontext(),
        get_champion=lambda: replace(_champion(), weight_revision=7),
        branch_patches={},
        branch_workspaces={branch.branch_id: "/tmp/candidate"},
        branch_hypotheses={},
        branch_current_hypothesis={},
        experiment_protocol_provider=lambda: protocol,
        feature_extractor=SafeFeatureExtractor(),
        decision_coordinator=DecisionCoordinator(config=ProtocolConfig()),
        decision_reason_codes={},
        campaign_id="campaign",
        registry=SimpleNamespace(),
        materializer=SimpleNamespace(),
        hypothesis_store=SimpleNamespace(),
        persist_branch_state=persist_branch_state,
        begin_status_progress=lambda **_kwargs: None,
        end_status_progress=lambda: None,
        increment_experiment_count=lambda: None,
    )

    result = orchestrator.evaluate(branch, "/tmp/candidate", _hypothesis())

    assert result.execution_outcome.outcome is ExecutionOutcome.EVALUATED
    assert events == [
        (
            "persist",
            initial_screening_count,
            initial_validation_count,
            7,
        ),
        ("evaluate", expected_expand, expected_expand_round, expected_stage),
    ]
    assert branch.screening_expand_count == initial_screening_count
    assert branch.validation_expand_count == initial_validation_count
    features = orchestrator.decision_feature_snapshots[branch.branch_id]
    assert features.screening_expand_count == effective_screening_count
    assert features.validation_expand_count == effective_validation_count


def test_explicit_evaluation_infra_cause_is_blocked_infra() -> None:
    branch = Branch(str(uuid.uuid4()), BranchState.EXPLORE, 1, "champ")
    orchestrator = EvaluationOrchestrator(
        branch_controller=_BranchController(),
        champion_lock=nullcontext(),
        get_champion=_champion,
        branch_patches={},
        branch_workspaces={branch.branch_id: "/tmp/candidate"},
        branch_hypotheses={},
        branch_current_hypothesis={},
        experiment_protocol_provider=_InfraRaisingProtocol,
        feature_extractor=SafeFeatureExtractor(),
        decision_coordinator=DecisionCoordinator(config=ProtocolConfig()),
        decision_reason_codes={},
        campaign_id="campaign",
        registry=SimpleNamespace(),
        materializer=SimpleNamespace(),
        hypothesis_store=SimpleNamespace(),
        persist_branch_state=lambda _branch_id: None,
        begin_status_progress=lambda **_kwargs: None,
        end_status_progress=lambda: None,
        increment_experiment_count=lambda: None,
    )

    result = orchestrator.evaluate(branch, "/tmp/candidate", _hypothesis())

    assert result.execution_outcome.outcome is ExecutionOutcome.BLOCKED_INFRA
    assert result.execution_outcome.reason_code == "EVALUATION_INFRA_BLOCKED"
    assert result.protocol_result is None
    assert result.decision is None


def _later_stage_orchestrator(
    branch: Branch,
    protocol_type,
) -> EvaluationOrchestrator:
    return EvaluationOrchestrator(
        branch_controller=_FrozenBranchController(),
        champion_lock=nullcontext(),
        get_champion=_champion,
        branch_patches={},
        branch_workspaces={branch.branch_id: "/tmp/candidate"},
        branch_hypotheses={},
        branch_current_hypothesis={},
        experiment_protocol_provider=protocol_type,
        feature_extractor=SafeFeatureExtractor(),
        decision_coordinator=DecisionCoordinator(config=ProtocolConfig()),
        decision_reason_codes={},
        campaign_id="campaign",
        registry=SimpleNamespace(),
        materializer=SimpleNamespace(),
        hypothesis_store=SimpleNamespace(),
        persist_branch_state=lambda _branch_id: None,
        begin_status_progress=lambda **_kwargs: None,
        end_status_progress=lambda: None,
        increment_experiment_count=lambda: None,
    )


def test_later_stage_champion_evidence_failure_blocks_before_decision() -> None:
    branch = Branch(
        str(uuid.uuid4()),
        BranchState.FROZEN_TESTING,
        1,
        "champ",
    )
    orchestrator = _later_stage_orchestrator(
        branch,
        _ChampionEvidenceBlockedProtocol,
    )

    result = orchestrator.evaluate(branch, "/tmp/candidate", _hypothesis())

    assert result.execution_outcome.outcome is ExecutionOutcome.BLOCKED_INFRA
    assert (
        result.execution_outcome.reason_code == "EVALUATION_CHAMPION_EVIDENCE_BLOCKED"
    )
    assert result.decision is None
    assert result.protocol_result is None
    assert result.canary_result is not None
    assert result.canary_result.passed is True
    assert result.execution_outcome.provenance == {
        "owner": "evaluation_orchestrator",
        "stage": "frozen",
        "failure_scope": "champion_or_shared",
        "raw_metrics_ref": "/tmp/frozen-partial-metrics.json",
        "protocol_gate_outcome": "fail",
        "protocol_reason_codes": [
            "INCOMPLETE_EVIDENCE",
            "CHAMPION_RUNTIME_FAILURE",
        ],
        "total_pairs": 24,
        "valid_pairs": 23,
        "failed_pairs": 1,
        "candidate_failed_pairs": 0,
        "champion_failed_pairs": 1,
        "operator_resume_required": True,
    }
    assert orchestrator.decision_engine_reason_codes[branch.branch_id] == ()
    assert orchestrator.bypass_reason_codes[branch.branch_id] == (
        "EVALUATION_CHAMPION_EVIDENCE_BLOCKED",
    )
    assert branch.branch_id not in orchestrator.decision_feature_snapshots


def test_later_stage_candidate_failure_remains_evaluated_abandon() -> None:
    branch = Branch(
        str(uuid.uuid4()),
        BranchState.FROZEN_TESTING,
        1,
        "champ",
    )
    orchestrator = _later_stage_orchestrator(
        branch,
        _CandidateEvidenceFailureProtocol,
    )

    result = orchestrator.evaluate(branch, "/tmp/candidate", _hypothesis())

    assert result.execution_outcome.outcome is ExecutionOutcome.EVALUATED
    assert result.decision is Decision.ABANDON
    assert result.protocol_result is not None
    assert result.protocol_result.reason_codes == (
        "INCOMPLETE_EVIDENCE",
        "CANDIDATE_RUNTIME_FAILURE",
    )


def test_canary_config_failure_rewrites_public_reason_without_changing_decision_boundary() -> (
    None
):
    branch = Branch(str(uuid.uuid4()), BranchState.EXPLORE, 1, "champ")
    branch_controller = _BranchController()
    decision_reason_codes: dict[str, tuple[str, ...]] = {}

    orchestrator = EvaluationOrchestrator(
        branch_controller=branch_controller,
        champion_lock=nullcontext(),
        get_champion=_champion,
        branch_patches={},
        branch_workspaces={branch.branch_id: "/tmp/candidate"},
        branch_hypotheses={},
        branch_current_hypothesis={},
        experiment_protocol_provider=_PathSafetyCanaryProtocol,
        feature_extractor=SafeFeatureExtractor(),
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
        increment_experiment_count=lambda: None,
    )

    evaluation = orchestrator.evaluate(
        branch,
        "/tmp/candidate",
        _hypothesis(),
    )
    decision = evaluation.decision
    protocol_result = evaluation.protocol_result
    canary_result = evaluation.canary_result

    assert decision == Decision.ABANDON
    assert protocol_result is None
    assert canary_result.passed is False
    assert canary_result.failure_category == "configuration_error"
    assert canary_result.reason_codes == ("CANARY_CONFIG_ERROR",)
    assert decision_reason_codes[branch.branch_id] == ("CANARY_CONFIG_ERROR",)
    assert orchestrator.decision_engine_reason_codes[branch.branch_id] == (
        "CANARY_FAILED",
    )
    assert orchestrator.diagnostic_reason_codes[branch.branch_id] == (
        "CANARY_CONFIG_ERROR",
    )


def test_ordinary_canary_failure_keeps_public_algorithm_reason() -> None:
    branch = Branch(str(uuid.uuid4()), BranchState.EXPLORE, 1, "champ")
    branch_controller = _BranchController()
    decision_reason_codes: dict[str, tuple[str, ...]] = {}

    orchestrator = EvaluationOrchestrator(
        branch_controller=branch_controller,
        champion_lock=nullcontext(),
        get_champion=_champion,
        branch_patches={},
        branch_workspaces={branch.branch_id: "/tmp/candidate"},
        branch_hypotheses={},
        branch_current_hypothesis={},
        experiment_protocol_provider=_OrdinaryFailingCanaryProtocol,
        feature_extractor=SafeFeatureExtractor(),
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
        increment_experiment_count=lambda: None,
    )

    evaluation = orchestrator.evaluate(
        branch,
        "/tmp/candidate",
        _hypothesis(),
    )
    decision = evaluation.decision
    protocol_result = evaluation.protocol_result
    canary_result = evaluation.canary_result

    assert decision == Decision.ABANDON
    assert protocol_result is None
    assert canary_result.failure_category == "candidate_failure"
    assert canary_result.reason_codes == ("CANARY_FAILED",)
    assert decision_reason_codes[branch.branch_id] == ("CANARY_FAILED",)
    assert orchestrator.decision_engine_reason_codes[branch.branch_id] == (
        "CANARY_FAILED",
    )
    assert orchestrator.diagnostic_reason_codes[branch.branch_id] == ()
