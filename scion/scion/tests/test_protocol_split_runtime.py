"""Focused tests split from test_protocol.py."""

from .protocol_test_support import *  # noqa: F401,F403

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


def test_run_experiment_records_runtime_telemetry_for_successful_pairs(tmp_path):
    runner = MagicMock()
    pair = [_make_run_result(2, 1000, elapsed_ms=100), _make_run_result(1, 900, elapsed_ms=150)]
    runner.run_solver.side_effect = pair * 4
    proto = _make_protocol(runner, tmp_path)

    result = proto.run_experiment(
        ExperimentStage.SCREENING, "/cand", "/champ", "modify"
    )

    assert result.stats.runtime_pairs == 4
    assert result.stats.runtime_ratio_median == pytest.approx(1.5)
    assert result.stats.runtime_delta_median_ms == pytest.approx(50.0)
    assert result.stats.runtime_regression_rate == pytest.approx(1.0)
    assert result.stats.total_pairs == 4
    assert result.stats.attempted_pairs == 4
    assert result.stats.valid_pairs == 4
    assert result.stats.failed_pairs == 0
    assert "runtime_ratio_median=1.50" in result.exposed_summary
    raw = json.loads(open(result.raw_metrics_ref).read())
    assert raw["runtime_stats"]["runtime_pairs"] == 4
    assert raw["runtime_stats"]["runtime_ratio_median"] == pytest.approx(1.5)
    assert all(p["candidate_elapsed_ms"] == 150 for p in raw["pairs"])
    assert all(p["champion_elapsed_ms"] == 100 for p in raw["pairs"])
    assert all(p["runtime_ratio"] == pytest.approx(1.5) for p in raw["pairs"])


def test_run_experiment_screening_gate_sees_runtime_tie_improvement(tmp_path):
    runner = MagicMock()
    pair = [
        _make_run_result(1, 900, elapsed_ms=1000),
        _make_run_result(1, 900, elapsed_ms=100),
    ]
    runner.run_solver.side_effect = pair * 4
    proto = _make_protocol(runner, tmp_path)

    result = proto.run_experiment(
        ExperimentStage.SCREENING, "/cand", "/champ", "modify"
    )

    assert result.gate_outcome == "pass"
    assert result.reason_codes == ("SCREENING_PASS_RUNTIME_TIE_IMPROVEMENT",)
    assert result.stats.median_delta == pytest.approx(0.0)
    assert result.stats.runtime_ratio_median == pytest.approx(0.1)
