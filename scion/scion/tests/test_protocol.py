"""Tests for scion/protocol/ — evaluation, stats, gates, experiment."""
from __future__ import annotations
import os
import uuid
import pytest
from unittest.mock import MagicMock
from datetime import datetime

from scion.core.models import (
    ExperimentStage, EvalStats, ProtocolResult, RunResult, SolverOutput, CanaryResult,
)
from scion.config.problem import ProtocolConfig, SplitManifest, SeedLedgerConfig
from scion.protocol.evaluation import lexicographic_compare, compute_delta
from scion.protocol.stats import compute_eval_stats, bootstrap_ci
from scion.protocol.gates import GateResult, screening_gate, validation_gate, frozen_gate
from scion.protocol.experiment import SplitManager, SeedLedger, ExperimentProtocol


# ─────────────────────────────────────────────────────────────────────────────
# evaluation.py
# ─────────────────────────────────────────────────────────────────────────────

def test_lexicographic_compare_win_by_splits():
    cand = {"subcategory_splits": 2, "total_cost": 1000}
    champ = {"subcategory_splits": 3, "total_cost": 500}
    assert lexicographic_compare(cand, champ) == "win"


def test_lexicographic_compare_loss_by_splits():
    cand = {"subcategory_splits": 4, "total_cost": 500}
    champ = {"subcategory_splits": 3, "total_cost": 1000}
    assert lexicographic_compare(cand, champ) == "loss"


def test_lexicographic_compare_win_by_cost():
    cand = {"subcategory_splits": 2, "total_cost": 900}
    champ = {"subcategory_splits": 2, "total_cost": 1000}
    assert lexicographic_compare(cand, champ) == "win"


def test_lexicographic_compare_tie():
    obj = {"subcategory_splits": 2, "total_cost": 1000}
    assert lexicographic_compare(obj, obj) == "tie"


def test_compute_delta_positive():
    cand = {"total_cost": 900}
    champ = {"total_cost": 1000}
    assert compute_delta(cand, champ) == pytest.approx(100.0)


def test_compute_delta_negative():
    cand = {"total_cost": 1100}
    champ = {"total_cost": 1000}
    assert compute_delta(cand, champ) == pytest.approx(-100.0)


# ─────────────────────────────────────────────────────────────────────────────
# stats.py
# ─────────────────────────────────────────────────────────────────────────────

def test_compute_eval_stats_basic():
    comparisons = ["win", "win", "loss", "tie", "win"]
    deltas = [100.0, 50.0, -20.0, 0.0, 30.0]
    stats = compute_eval_stats(comparisons, deltas)
    assert stats.n_cases == 5
    assert stats.wins == 3
    assert stats.losses == 1
    assert stats.ties == 1
    assert stats.win_rate == pytest.approx(0.6)
    assert stats.median_delta == pytest.approx(30.0)


def test_hierarchical_stats_primary_metric_wins_despite_cost_outliers():
    """Primary metric CI drives gate stats when metric details are available."""
    comparisons = ["win"] * 6
    scalar_deltas = [-10000.0, -8000.0, -500.0, 200.0, 1000.0, 1200.0]
    metric_rows = [
        {"subcategory_splits": 1.0, "total_cost": -20000.0},
        {"subcategory_splits": 1.0, "total_cost": -9000.0},
        {"subcategory_splits": 1.0, "total_cost": -5000.0},
        {"subcategory_splits": 2.0, "total_cost": 1000.0},
        {"subcategory_splits": 1.0, "total_cost": 2000.0},
        {"subcategory_splits": 3.0, "total_cost": 3000.0},
    ]
    stats = compute_eval_stats(
        comparisons,
        scalar_deltas,
        metric_deltas=metric_rows,
        metric_order=["subcategory_splits", "total_cost"],
    )

    assert stats.statistical_status == "positive"
    assert stats.statistical_metric == "subcategory_splits"
    assert stats.ci_low > 0
    assert stats.median_delta == pytest.approx(1.0)


def test_hierarchical_stats_falls_through_exact_primary_tie_to_cost():
    comparisons = ["win"] * 4
    metric_rows = [
        {"subcategory_splits": 0.0, "total_cost": 10.0},
        {"subcategory_splits": 0.0, "total_cost": 15.0},
        {"subcategory_splits": 0.0, "total_cost": 8.0},
        {"subcategory_splits": 0.0, "total_cost": 12.0},
    ]
    stats = compute_eval_stats(
        comparisons,
        [10.0, 15.0, 8.0, 12.0],
        metric_deltas=metric_rows,
        metric_order=["subcategory_splits", "total_cost"],
    )

    assert stats.statistical_status == "positive"
    assert stats.statistical_metric == "total_cost"
    assert stats.ci_low > 0


def test_bootstrap_ci_all_positive():
    """When all deltas are positive, ci_low should be > 0."""
    deltas = [10.0, 20.0, 15.0, 25.0, 18.0, 12.0]
    ci_low, ci_high = bootstrap_ci(deltas)
    assert ci_low > 0, f"Expected ci_low > 0 but got {ci_low}"
    assert ci_high > ci_low


def test_bootstrap_ci_all_negative():
    """When all deltas are negative, ci_high should be < 0."""
    deltas = [-10.0, -20.0, -15.0]
    ci_low, ci_high = bootstrap_ci(deltas)
    assert ci_high < 0, f"Expected ci_high < 0 but got {ci_high}"


def test_bootstrap_ci_empty():
    assert bootstrap_ci([]) == (0.0, 0.0)


# ─────────────────────────────────────────────────────────────────────────────
# gates.py
# ─────────────────────────────────────────────────────────────────────────────

def _make_stats(**kwargs) -> EvalStats:
    defaults = dict(
        n_cases=10, wins=7, losses=2, ties=1,
        win_rate=0.7, median_delta=0.01,
        ci_low=0.005, ci_high=0.02,
    )
    defaults.update(kwargs)
    return EvalStats(**defaults)


_cfg = ProtocolConfig()


def test_screening_gate_pass():
    stats = _make_stats(win_rate=0.7, median_delta=0.01)
    result = screening_gate(stats, _cfg)
    assert result.outcome == "pass"


def test_screening_gate_fail():
    stats = _make_stats(win_rate=0.4)
    result = screening_gate(stats, _cfg)
    assert result.outcome == "fail"


def test_screening_gate_expand():
    stats = _make_stats(win_rate=0.55, median_delta=0.01)
    result = screening_gate(stats, _cfg)
    assert result.outcome == "expand"


def test_screening_gate_unclear_delta_small():
    stats = _make_stats(win_rate=0.7, median_delta=0.0001)
    result = screening_gate(stats, _cfg)
    assert result.outcome == "unclear"


def test_validation_gate_pass():
    stats = _make_stats(win_rate=0.7, ci_low=0.005, ci_high=0.02)
    result = validation_gate(stats, _cfg)
    assert result.outcome == "pass"


def test_validation_gate_uses_hierarchical_status():
    stats = _make_stats(
        win_rate=1.0,
        ci_low=1.0,
        ci_high=2.0,
        statistical_status="positive",
        statistical_metric="subcategory_splits",
    )
    result = validation_gate(stats, _cfg)
    assert result.outcome == "pass"
    assert result.reason_codes == ("VALIDATION_PASS_HIERARCHICAL",)


def test_validation_gate_fail_ci_negative():
    stats = _make_stats(win_rate=0.7, ci_low=-0.02, ci_high=-0.001)
    result = validation_gate(stats, _cfg)
    assert result.outcome == "fail"


def test_validation_gate_expand():
    stats = _make_stats(win_rate=0.7, ci_low=-0.005, ci_high=0.02)
    result = validation_gate(stats, _cfg)
    assert result.outcome == "expand"


def test_frozen_gate_pass():
    stats = _make_stats(ci_low=0.005, ci_high=0.02)
    result = frozen_gate(stats, _cfg)
    assert result.outcome == "pass"


def test_frozen_gate_rejects_hierarchical_uncertain_even_if_legacy_ci_nonnegative():
    stats = _make_stats(
        ci_low=0.005,
        ci_high=0.02,
        statistical_status="uncertain",
        statistical_metric="subcategory_splits",
    )
    result = frozen_gate(stats, _cfg)
    assert result.outcome == "fail"
    assert result.reason_codes == ("FROZEN_FAIL_HIERARCHICAL_UNCERTAIN",)


def test_frozen_gate_fail_ci_negative():
    stats = _make_stats(ci_low=-0.02, ci_high=-0.001)
    result = frozen_gate(stats, _cfg)
    assert result.outcome == "fail"


def test_frozen_gate_fail_unclear():
    stats = _make_stats(ci_low=-0.005, ci_high=0.01)
    result = frozen_gate(stats, _cfg)
    assert result.outcome == "fail"


# ─────────────────────────────────────────────────────────────────────────────
# experiment.py — SplitManager, SeedLedger
# ─────────────────────────────────────────────────────────────────────────────

def _make_manifest():
    # canary cases must be disjoint from screening/validation/frozen
    return SplitManifest(
        version="test",
        screening=["case_a", "case_b"],
        validation=["case_c", "case_d"],
        frozen=["case_e", "case_f"],
        canary=["canary_x", "canary_y"],
    )


def _make_ledger():
    return SeedLedgerConfig(
        version="test",
        screening=[1, 2],
        validation=[3, 4],
        frozen=[5, 6],
        canary=[99],
    )


def test_split_manager_get_cases():
    sm = SplitManager(_make_manifest())
    assert sm.get_cases(ExperimentStage.SCREENING) == ["case_a", "case_b"]
    assert sm.get_cases(ExperimentStage.VALIDATION) == ["case_c", "case_d"]
    assert sm.get_cases(ExperimentStage.FROZEN) == ["case_e", "case_f"]


def test_seed_ledger_get_seeds():
    sl = SeedLedger(_make_ledger())
    assert sl.get_seeds(ExperimentStage.SCREENING) == [1, 2]
    assert sl.get_seeds(ExperimentStage.VALIDATION) == [3, 4]
    assert sl.get_seeds(ExperimentStage.FROZEN) == [5, 6]


def _make_run_result(splits: int, cost: float, feasible: bool = True) -> RunResult:
    return RunResult(
        success=True,
        exit_code=0,
        stdout="",
        stderr="",
        elapsed_ms=100,
        output=SolverOutput(
            vehicles={},
            assignment={},
            objective={"subcategory_splits": splits, "total_cost": cost},
            feasible=feasible,
        ),
    )


def _make_protocol(runner, tmp_path) -> ExperimentProtocol:
    return ExperimentProtocol(
        protocol_config=ProtocolConfig(),
        split_manager=SplitManager(_make_manifest()),
        seed_ledger=SeedLedger(_make_ledger()),
        runner=runner,
        time_limit_sec=10,
        metrics_dir=str(tmp_path / "metrics"),
    )


def test_run_experiment_screening_pass(tmp_path):
    """Candidate consistently better → screening pass.
    run_experiment calls: champ first, then cand (per pair).
    2 cases × 2 seeds = 4 pairs × 2 calls = 8 calls total.
    """
    runner = MagicMock()
    # champ=worse(splits=2, cost=1000), cand=better(splits=1, cost=900)
    pair = [_make_run_result(2, 1000), _make_run_result(1, 900)]
    runner.run_solver.side_effect = pair * 4  # 4 pairs
    proto = _make_protocol(runner, tmp_path)
    result = proto.run_experiment(
        ExperimentStage.SCREENING, "/cand", "/champ", "modify"
    )
    assert result.gate_outcome == "pass"
    assert result.stats.wins == result.stats.n_cases


def test_run_experiment_screening_fail(tmp_path):
    """Candidate always loses → fail.
    champ=better(splits=1, cost=900), cand=worse(splits=3, cost=1500).
    """
    runner = MagicMock()
    pair = [_make_run_result(1, 900), _make_run_result(3, 1500)]
    runner.run_solver.side_effect = pair * 4
    proto = _make_protocol(runner, tmp_path)
    result = proto.run_experiment(
        ExperimentStage.SCREENING, "/cand", "/champ", "modify"
    )
    assert result.gate_outcome == "fail"


def test_run_canary_pass(tmp_path):
    """Canary calls cand first, then champ. 2 cases × 1 seed = 4 calls."""
    runner = MagicMock()
    runner.run_solver.side_effect = [
        _make_run_result(2, 900, feasible=True),   # cand case_a seed1
        _make_run_result(2, 1000, feasible=True),  # champ case_a seed1
        _make_run_result(2, 900, feasible=True),   # cand case_b seed1
        _make_run_result(2, 1000, feasible=True),  # champ case_b seed1
    ]
    proto = _make_protocol(runner, tmp_path)
    result = proto.run_canary("/cand", "/champ")
    assert result.passed


def test_run_canary_fail_infeasible(tmp_path):
    """Candidate infeasible while champion feasible → veto."""
    runner = MagicMock()
    runner.run_solver.side_effect = [
        _make_run_result(2, 900, feasible=False),  # cand case_a infeasible
        _make_run_result(2, 1000, feasible=True),  # champ case_a feasible
    ]
    proto = _make_protocol(runner, tmp_path)
    result = proto.run_canary("/cand", "/champ")
    assert not result.passed


def test_run_canary_fail_solver_crash(tmp_path):
    runner = MagicMock()
    runner.run_solver.return_value = RunResult(
        success=False, exit_code=1, stdout="", stderr="crash",
        elapsed_ms=50, error_category="crash",
    )
    proto = _make_protocol(runner, tmp_path)
    result = proto.run_canary("/cand", "/champ")
    assert not result.passed
