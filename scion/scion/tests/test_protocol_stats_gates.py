"""Focused tests split from test_protocol.py."""

from .protocol_test_support import *  # noqa: F401,F403

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


def test_legacy_evaluation_source_is_problem_agnostic():
    import scion.protocol.evaluation as evaluation

    src = inspect.getsource(evaluation)
    assert "DEPRECATED" in src
    for forbidden in ("subcategory_splits", "total_cost", "warehouse"):
        assert forbidden not in src


def test_lexicographic_compare_uses_generic_key_order():
    cand = {"primary_metric": 2, "secondary_metric": 1000}
    champ = {"primary_metric": 3, "secondary_metric": 10}
    assert lexicographic_compare(cand, champ) == "win"

    cand = {"primary_metric": 3, "secondary_metric": 5}
    champ = {"primary_metric": 3, "secondary_metric": 10}
    assert lexicographic_compare(cand, champ) == "win"


def test_compute_delta_weights_first_decisive_generic_metric():
    cand = {"primary_metric": 2, "secondary_metric": 1000}
    champ = {"primary_metric": 3, "secondary_metric": 10}
    assert compute_delta(cand, champ) == pytest.approx(100000.0)


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


def test_screening_gate_pass():
    stats = _make_stats(win_rate=0.7, median_delta=0.01)
    result = screening_gate(stats, _cfg)
    assert result.outcome == "pass"


def test_screening_gate_fail():
    stats = _make_stats(win_rate=0.4)
    result = screening_gate(stats, _cfg)
    assert result.outcome == "fail"


def test_screening_gate_passes_runtime_tie_improvement():
    stats = _make_stats(
        wins=0,
        losses=0,
        ties=10,
        win_rate=0.0,
        median_delta=0.0,
        ci_low=0.0,
        ci_high=0.0,
        runtime_ratio_median=0.5,
        runtime_delta_median_ms=-1000.0,
        runtime_pairs=10,
    )
    result = screening_gate(stats, _cfg)
    assert result.outcome == "pass"
    assert result.reason_codes == ("SCREENING_PASS_RUNTIME_TIE_IMPROVEMENT",)


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


def test_validation_gate_passes_runtime_tie_improvement():
    stats = _make_stats(
        wins=0,
        losses=0,
        ties=10,
        win_rate=0.0,
        median_delta=0.0,
        ci_low=0.0,
        ci_high=0.0,
        statistical_status="tie",
        runtime_ratio_median=0.5,
        runtime_delta_median_ms=-1000.0,
        runtime_pairs=10,
    )
    result = validation_gate(stats, _cfg)
    assert result.outcome == "pass"
    assert result.reason_codes == ("VALIDATION_PASS_RUNTIME_TIE_IMPROVEMENT",)


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


def test_frozen_gate_passes_runtime_tie_improvement():
    stats = _make_stats(
        wins=0,
        losses=0,
        ties=10,
        win_rate=0.0,
        median_delta=0.0,
        ci_low=0.0,
        ci_high=0.0,
        statistical_status="tie",
        runtime_ratio_median=0.5,
        runtime_delta_median_ms=-1000.0,
        runtime_pairs=10,
    )
    result = frozen_gate(stats, _cfg)
    assert result.outcome == "pass"
    assert result.reason_codes == ("FROZEN_PASS_RUNTIME_TIE_IMPROVEMENT",)


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
