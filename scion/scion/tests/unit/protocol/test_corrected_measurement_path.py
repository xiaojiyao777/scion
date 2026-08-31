from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from scion.config.problem import ProtocolConfig, SeedLedgerConfig, SplitManifest
from scion.core.models import (
    EvalStats,
    ExperimentStage,
    PairwiseCaseFeedback,
    RunResult,
    SolverOutput,
)
from scion.problem.objectives import MetricComparison, ObjectiveComparison
from scion.problem.spec import ObjectiveMetricSpec
from scion.proposal.context_manager.manager import _screening_projection
from scion.protocol.experiment import ExperimentProtocol, SeedLedger, SplitManager
from scion.protocol.experiment.feedback import (
    _aggregate_case_feedback,
    _aggregate_pairs_to_case_level,
    _build_pattern_summary,
    _protected_objective_regressions,
)
from scion.protocol.experiment.selection import select_seeds
from scion.protocol.gates import screening_gate
from scion.tests.protocol_adapter_test_support import protocol_test_adapter


def _pair(
    *,
    case: str,
    seed: int,
    effect: float,
    fleet_delta: float = 0.0,
) -> PairwiseCaseFeedback:
    fleet_relation = (
        "candidate"
        if fleet_delta > 0
        else ("champion" if fleet_delta < 0 else "tie")
    )
    effect_relation = (
        "candidate" if effect > 0 else ("champion" if effect < 0 else "tie")
    )
    comparison = "win" if effect > 0 else ("loss" if effect < 0 else "tie")
    objective = ObjectiveComparison(
        outcome=comparison,
        decisive_metric="total_distance" if effect else None,
        scalar_delta=fleet_delta + effect,
        metrics=(
            MetricComparison(
                name="fleet_violation",
                candidate_value=-fleet_delta,
                champion_value=0,
                signed_delta=fleet_delta,
                relation=fleet_relation,
            ),
            MetricComparison(
                name="total_distance",
                candidate_value=1000 - effect,
                champion_value=1000,
                signed_delta=effect,
                relation=effect_relation,
                decisive=effect != 0,
            ),
        ),
    )
    return PairwiseCaseFeedback(
        case_id=case,
        seed=seed,
        comparison=comparison,
        delta=fleet_delta + effect,
        objective_comparison=objective,
    )


def test_protocol_config_keeps_legacy_defaults_and_resolves_expanded_seeds() -> None:
    legacy = ProtocolConfig()
    assert legacy.case_aggregation == "seed_vote_majority"
    assert legacy.case_equivalence_band == 0.0
    assert legacy.screening.require_expanded_for_pass is False
    assert legacy.screening.effective_expand_n_seeds == legacy.screening.n_seeds

    corrected = ProtocolConfig.model_validate(
        {
            "case_aggregation": "paired_effect_median",
            "screening": {
                "n_seeds": 4,
                "expand_n_seeds": 8,
                "require_expanded_for_pass": True,
            },
        }
    )
    assert corrected.screening.effective_expand_n_seeds == 8

    with pytest.raises(ValueError, match="expand_n_seeds must be >= n_seeds"):
        ProtocolConfig.model_validate(
            {"screening": {"n_seeds": 4, "expand_n_seeds": 2}}
        )


def test_seed_selection_uses_declared_ledger_prefixes() -> None:
    config = ProtocolConfig.model_validate(
        {
            "screening": {"n_seeds": 2, "expand_n_seeds": 4},
            "validation": {"n_seeds": 3},
            "frozen": {"n_seeds": 1},
        }
    )
    ledger = SeedLedger(
        SeedLedgerConfig(
            screening=[11, 29, 43, 59, 71],
            validation=[3, 5, 7, 9],
            frozen=[101, 103],
        )
    )

    assert select_seeds(
        config=config,
        seed_ledger=ledger,
        stage=ExperimentStage.SCREENING,
    ) == [11, 29]
    assert select_seeds(
        config=config,
        seed_ledger=ledger,
        stage=ExperimentStage.SCREENING,
        expanded=True,
    ) == [11, 29, 43, 59]
    assert select_seeds(
        config=config,
        seed_ledger=ledger,
        stage=ExperimentStage.VALIDATION,
    ) == [3, 5, 7]
    assert select_seeds(
        config=config,
        seed_ledger=ledger,
        stage=ExperimentStage.FROZEN,
    ) == [101]


def test_seed_selection_preserves_complete_legacy_stage_ledgers() -> None:
    config = ProtocolConfig.model_validate(
        {
            "screening": {"n_seeds": 3},
            "validation": {"n_seeds": 3},
            "frozen": {"n_seeds": 3},
        }
    )
    ledger = SeedLedger(
        SeedLedgerConfig(
            screening=[11],
            validation=[47, 53],
            frozen=[61, 67],
        )
    )

    assert select_seeds(
        config=config,
        seed_ledger=ledger,
        stage=ExperimentStage.SCREENING,
    ) == [11]
    assert select_seeds(
        config=config,
        seed_ledger=ledger,
        stage=ExperimentStage.VALIDATION,
    ) == [47, 53]
    assert select_seeds(
        config=config,
        seed_ledger=ledger,
        stage=ExperimentStage.FROZEN,
    ) == [61, 67]


def test_seed_selection_fails_clearly_when_ledger_is_short() -> None:
    config = ProtocolConfig.model_validate(
        {"screening": {"n_seeds": 2, "expand_n_seeds": 4}}
    )
    ledger = SeedLedger(SeedLedgerConfig(screening=[11, 29, 43]))

    with pytest.raises(
        ValueError,
        match=r"insufficient screening seeds: required=4, available=3",
    ):
        select_seeds(
            config=config,
            seed_ledger=ledger,
            stage=ExperimentStage.SCREENING,
            expanded=True,
        )


def test_paired_effect_median_drives_formal_and_h_visible_case_direction() -> None:
    pairs = [
        _pair(case="c1", seed=11, effect=100.0),
        _pair(case="c1", seed=29, effect=100.0),
        _pair(case="c1", seed=43, effect=100.0),
        _pair(case="c1", seed=59, effect=100.0),
        _pair(case="c1", seed=73, effect=-1.0),
        _pair(case="c1", seed=79, effect=-1.0),
        _pair(case="c1", seed=97, effect=-1.0),
        _pair(case="c1", seed=103, effect=-1.0),
    ]

    legacy = _aggregate_pairs_to_case_level(pairs)
    formal = _aggregate_pairs_to_case_level(
        pairs,
        aggregation="paired_effect_median",
        effect_metric="total_distance",
    )
    visible = _aggregate_case_feedback(
        pairs,
        aggregation="paired_effect_median",
        effect_metric="total_distance",
    )

    assert legacy[0].comparison == "tie"
    assert formal[0].comparison == "win"
    assert formal[0].delta == pytest.approx(49.5)
    assert visible[0].dominant_result == formal[0].comparison
    assert (visible[0].wins, visible[0].losses) == (4, 4)
    assert visible[0].seed_pattern == "heterogeneous"
    assert visible[0].median_deltas["total_distance"] == pytest.approx(49.5)
    pattern = _build_pattern_summary(tuple(visible))
    assert pattern.winning_cases == 1
    assert pattern.mixed_cases == 1


def test_protected_regression_is_global_veto_not_case_estimator_mutation() -> None:
    pairs = [
        _pair(case="c1", seed=11, effect=10.0),
        _pair(case="c1", seed=29, effect=20.0, fleet_delta=-1.0),
    ]
    kwargs = {
        "aggregation": "paired_effect_median",
        "effect_metric": "total_distance",
    }

    formal = _aggregate_pairs_to_case_level(pairs, **kwargs)
    visible = _aggregate_case_feedback(pairs, **kwargs)

    assert formal[0].comparison == "win"
    assert formal[0].delta == pytest.approx(15.0)
    assert visible[0].dominant_result == "win"
    regressions = _protected_objective_regressions(
        pairs,
        ("fleet_violation",),
    )
    assert regressions == ("fleet_violation",)
    gate = screening_gate(
        EvalStats(
            n_cases=1,
            wins=1,
            losses=0,
            ties=0,
            win_rate=1.0,
            median_delta=15.0,
            ci_low=15.0,
            ci_high=15.0,
            protected_objective_regressions=regressions,
        ),
        ProtocolConfig(),
    )
    assert gate.outcome == "fail"
    assert gate.reason_codes == (
        "SCREENING_FAIL_PROTECTED_OBJECTIVE_REGRESSION",
    )


def test_paired_effect_equivalence_band_is_shared_by_formal_and_feedback() -> None:
    pairs = [
        _pair(case="c1", seed=11, effect=1.0),
        _pair(case="c1", seed=29, effect=3.0),
    ]
    kwargs = {
        "aggregation": "paired_effect_median",
        "effect_metric": "total_distance",
        "equivalence_band": 2.0,
    }

    formal = _aggregate_pairs_to_case_level(pairs, **kwargs)
    visible = _aggregate_case_feedback(pairs, **kwargs)

    assert formal[0].delta == pytest.approx(2.0)
    assert formal[0].comparison == "tie"
    assert visible[0].dominant_result == "tie"


def test_paired_effect_median_rejects_missing_effect_evidence() -> None:
    with pytest.raises(ValueError, match="effect_metric is absent"):
        _aggregate_pairs_to_case_level(
            [_pair(case="c1", seed=11, effect=10.0)],
            aggregation="paired_effect_median",
            effect_metric="missing_metric",
        )


def test_paired_effect_median_keeps_typed_candidate_failure_as_case_loss() -> None:
    failed_pair = PairwiseCaseFeedback(
        case_id="c1",
        seed=11,
        comparison="loss",
        delta=-1.0,
        objective_comparison=None,
    )
    successful_pair = _pair(case="c1", seed=29, effect=100.0)

    formal = _aggregate_pairs_to_case_level(
        [failed_pair, successful_pair],
        aggregation="paired_effect_median",
        effect_metric="total_distance",
    )

    assert formal[0].comparison == "loss"
    assert formal[0].delta == -1.0


def test_initial_pass_can_require_exact_expanded_confirmation() -> None:
    stats = EvalStats(
        n_cases=10,
        wins=7,
        losses=2,
        ties=1,
        win_rate=0.7,
        median_delta=3.0,
        ci_low=0.0,
        ci_high=6.0,
    )
    config = ProtocolConfig.model_validate(
        {
            "practical_delta_screen": 2.0,
            "screening": {"require_expanded_for_pass": True},
            "gates": {
                "screening": {
                    "win_rate_min": 0.6,
                    "median_delta_min": "practical_delta_screen",
                }
            },
        }
    )

    initial = screening_gate(stats, config, expanded=False)
    expanded = screening_gate(stats, config, expanded=True)

    assert initial.outcome == "expand"
    assert initial.reason_codes == ("SCREENING_EXPAND_REQUIRED_FOR_PASS",)
    assert expanded.outcome == "pass"
    assert expanded.reason_codes == ("SCREENING_PASS",)


def test_experiment_persists_recomputable_corrected_case_measurement(
    tmp_path: Path,
) -> None:
    config = ProtocolConfig.model_validate(
        {
            "case_aggregation": "paired_effect_median",
            "effect_metric": "total_distance",
            "practical_delta_screen": 2.0,
            "screening": {
                "n_cases_modify": 1,
                "n_cases_create": 1,
                "n_seeds": 4,
                "expand_n_seeds": 6,
                "expand_to_modify": 2,
                "expand_to_create": 2,
            },
            "gates": {
                "screening": {
                    "win_rate_min": 0.6,
                    "median_delta_min": "practical_delta_screen",
                }
            },
        }
    )
    runner = MagicMock()
    case_path = tmp_path / "case-a.vrp"
    case_path.write_text("NAME : case-a\n", encoding="utf-8")
    candidate_distances = {11: 900.0, 29: 900.0, 43: 1001.0, 59: 1001.0}

    def run_solver(**kwargs):
        distance = (
            1000.0
            if kwargs["workdir"] == "/champion"
            else candidate_distances[kwargs["seed"]]
        )
        return RunResult(
            success=True,
            exit_code=0,
            stdout="",
            stderr="",
            elapsed_ms=10,
            output=SolverOutput(
                objective={"fleet_violation": 0, "total_distance": distance},
                feasible=True,
            ),
        )

    runner.run_solver.side_effect = run_solver
    protocol = ExperimentProtocol(
        protocol_config=config,
        split_manager=SplitManager(
            SplitManifest(screening=[str(case_path)], safe_data_roots=[str(tmp_path)])
        ),
        seed_ledger=SeedLedger(
            SeedLedgerConfig(screening=[11, 29, 43, 59, 71, 73])
        ),
        runner=runner,
        time_limit_sec=10,
        metrics_dir=str(tmp_path / "metrics"),
        adapter=protocol_test_adapter(
            (
                ObjectiveMetricSpec(
                    name="fleet_violation", direction="minimize", priority=1
                ),
                ObjectiveMetricSpec(
                    name="total_distance", direction="minimize", priority=2
                ),
            ),
        ),
    )

    result = protocol.run_experiment(
        ExperimentStage.SCREENING,
        "/candidate",
        "/champion",
        "modify",
    )
    raw = json.loads(Path(result.raw_metrics_ref).read_text(encoding="utf-8"))

    assert result.seed_set == (11, 29, 43, 59)
    assert result.case_aggregation_method == "paired_effect_median"
    assert result.case_effect_metric == "total_distance"
    assert result.case_equivalence_band == 0.0
    assert result.stats.wins == 1
    assert result.gate_outcome == "pass"
    assert raw["seed_set"] == [11, 29, 43, 59]
    assert raw["case_aggregation"] == {
        "method": "paired_effect_median",
        "effect_metric": "total_distance",
        "equivalence_band": 0.0,
    }
    assert raw["case_level_results"] == [
        {
            "case_id": "case-a.vrp",
            "comparison": "win",
            "delta": 49.5,
            "metric_deltas": {
                "fleet_violation": 0.0,
                "total_distance": 49.5,
            },
        }
    ]
    proposal = _screening_projection(result)
    assert (
        proposal["objective_outcome"]["aggregation"]["method"]
        == "paired_effect_median"
    )
    assert proposal["objective_outcome"]["aggregation"]["effect_metric"] == (
        "total_distance"
    )
    assert proposal["objective_outcome"]["aggregation"]["equivalence_band"] == 0.0


def test_experiment_candidate_failure_remains_typed_measurement_evidence(
    tmp_path: Path,
) -> None:
    config = ProtocolConfig.model_validate(
        {
            "case_aggregation": "paired_effect_median",
            "effect_metric": "total_distance",
            "screening": {
                "n_cases_modify": 1,
                "n_cases_create": 1,
                "n_seeds": 1,
                "expand_to_modify": 2,
                "expand_to_create": 2,
            },
        }
    )
    runner = MagicMock()
    case_path = tmp_path / "case-a.vrp"
    case_path.write_text("NAME : case-a\n", encoding="utf-8")

    def run_solver(**kwargs):
        if kwargs["workdir"] == "/candidate":
            return RunResult(
                success=False,
                exit_code=1,
                stdout="",
                stderr="synthetic crash",
                elapsed_ms=10,
                error_category="crash",
            )
        return RunResult(
            success=True,
            exit_code=0,
            stdout="",
            stderr="",
            elapsed_ms=10,
            output=SolverOutput(
                objective={"fleet_violation": 0, "total_distance": 1000.0},
                feasible=True,
            ),
        )

    runner.run_solver.side_effect = run_solver
    protocol = ExperimentProtocol(
        protocol_config=config,
        split_manager=SplitManager(
            SplitManifest(screening=[str(case_path)], safe_data_roots=[str(tmp_path)])
        ),
        seed_ledger=SeedLedger(SeedLedgerConfig(screening=[11])),
        runner=runner,
        time_limit_sec=10,
        metrics_dir=str(tmp_path / "metrics"),
        adapter=protocol_test_adapter(
            (
                ObjectiveMetricSpec(
                    name="fleet_violation", direction="minimize", priority=1
                ),
                ObjectiveMetricSpec(
                    name="total_distance", direction="minimize", priority=2
                ),
            ),
        ),
    )

    result = protocol.run_experiment(
        ExperimentStage.SCREENING,
        "/candidate",
        "/champion",
        "modify",
    )
    raw = json.loads(Path(result.raw_metrics_ref).read_text(encoding="utf-8"))

    assert result.gate_outcome == "fail"
    assert result.stats.candidate_failed_pairs == 1
    assert result.stats.losses == 1
    assert raw["case_level_results"][0]["comparison"] == "loss"
    assert raw["case_level_results"][0]["delta"] == -1.0
