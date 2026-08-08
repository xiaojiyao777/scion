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


def test_screening_gate_does_not_advance_below_practical_delta():
    stats = _make_stats(win_rate=0.7, median_delta=0.01)
    config = ProtocolConfig.model_validate({"practical_delta_screen": 2.0})

    result = screening_gate(stats, config)

    assert result.outcome == "expand"
    assert result.reason_codes == ("SCREENING_EXPAND_CASE_LEVEL_UNCERTAIN",)


def test_screening_gate_high_win_negative_effect_is_not_pass():
    stats = _make_stats(win_rate=0.7, median_delta=-0.01)

    result = screening_gate(stats, _cfg)

    assert result.outcome == "expand"
    assert result.reason_codes == ("SCREENING_EXPAND_CASE_LEVEL_UNCERTAIN",)


def test_screening_gate_fail():
    stats = _make_stats(win_rate=0.4)
    result = screening_gate(stats, _cfg)
    assert result.outcome == "fail"


def test_screening_runtime_tie_does_not_replace_objective_improvement():
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
    assert result.outcome == "fail"
    assert result.reason_codes == ("SCREENING_FAIL_WIN_RATE",)


def test_cached_runtime_is_diagnostic_not_a_screening_gate():
    stats = _make_stats(
        wins=0,
        losses=0,
        ties=10,
        win_rate=0.0,
        median_delta=0.0,
        ci_low=0.0,
        ci_high=0.0,
        runtime_ratio_median=None,
        runtime_delta_median_ms=None,
        runtime_pairs=0,
        champion_cached_runtime_pairs=10,
    )

    result = screening_gate(stats, _cfg)

    assert result.outcome == "fail"
    assert result.reason_codes == ("SCREENING_FAIL_WIN_RATE",)


def test_budget_exhausting_cached_runtime_tie_does_not_require_fresh_runtime():
    stats = _make_stats(
        wins=0,
        losses=0,
        ties=10,
        win_rate=0.0,
        median_delta=0.0,
        ci_low=0.0,
        ci_high=0.0,
        runtime_ratio_median=None,
        runtime_delta_median_ms=None,
        runtime_pairs=0,
        champion_cached_runtime_pairs=10,
    )
    config = ProtocolConfig.model_validate(
        {"runtime": {"runtime_model": "budget_exhausting"}}
    )

    result = screening_gate(stats, config)

    assert result.reason_codes != ("RUNTIME_TIE_FRESH_CHAMPION_REQUIRED",)
    assert "RUNTIME_TIE_FRESH_CHAMPION_REQUIRED" not in result.reason_codes


def test_budget_exhausting_runtime_tie_does_not_pass_screening():
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
    config = ProtocolConfig.model_validate(
        {"runtime": {"runtime_model": "budget_exhausting"}}
    )

    result = screening_gate(stats, config)

    assert result.outcome == "fail"
    assert result.reason_codes == ("SCREENING_FAIL_WIN_RATE",)


@pytest.mark.parametrize("gate_func", (validation_gate, frozen_gate))
def test_validation_and_frozen_cached_runtime_tie_cannot_pass(gate_func):
    stats = _make_stats(
        wins=0,
        losses=0,
        ties=10,
        win_rate=0.0,
        median_delta=0.0,
        ci_low=0.0,
        ci_high=0.0,
        statistical_status="tie",
        runtime_ratio_median=None,
        runtime_delta_median_ms=None,
        runtime_pairs=0,
        champion_cached_runtime_pairs=10,
    )

    result = gate_func(stats, _cfg)

    assert result.outcome == "fail"
    assert "RUNTIME_TIE_FRESH_CHAMPION_REQUIRED" not in result.reason_codes


def test_screening_gate_expand():
    stats = _make_stats(win_rate=0.55, median_delta=0.01)
    result = screening_gate(stats, _cfg)
    assert result.outcome == "expand"


def test_pair_signal_cannot_override_case_win_rate():
    stats = _make_stats(
        wins=3,
        losses=4,
        ties=9,
        win_rate=3 / 16,
        median_delta=0.0,
        ci_low=-1.0,
        ci_high=2.0,
        pair_wins=14,
        pair_losses=11,
        pair_ties=32,
        valid_pairs=57,
    )
    config = ProtocolConfig.model_validate(
        {"pairing_validity": "trajectory_divergent"}
    )

    result = screening_gate(stats, config)

    assert result.outcome == "fail"
    assert result.reason_codes == ("SCREENING_FAIL_WIN_RATE",)


def test_all_case_ties_do_not_advance_screening():
    stats = _make_stats(
        wins=0,
        losses=0,
        ties=16,
        win_rate=0.0,
        median_delta=0.0,
        ci_low=0.0,
        ci_high=0.0,
        pair_wins=0,
        pair_losses=0,
        pair_ties=64,
        valid_pairs=64,
    )
    config = ProtocolConfig.model_validate(
        {"pairing_validity": "trajectory_divergent"}
    )

    result = screening_gate(stats, config)

    assert result.outcome == "fail"
    assert result.reason_codes == ("SCREENING_FAIL_WIN_RATE",)


def test_trajectory_stable_tie_heavy_screening_still_fails_below_half_win_rate():
    stats = _make_stats(
        wins=3,
        losses=4,
        ties=9,
        win_rate=3 / 16,
        median_delta=0.0,
        ci_low=-1.0,
        ci_high=2.0,
        pair_wins=14,
        pair_losses=11,
        pair_ties=32,
        valid_pairs=57,
    )

    result = screening_gate(stats, _cfg)

    assert result.outcome == "fail"
    assert result.reason_codes == ("SCREENING_FAIL_WIN_RATE",)


def test_budget_exhausting_runtime_does_not_override_case_failure():
    stats = _make_stats(
        wins=3,
        losses=4,
        ties=9,
        win_rate=3 / 16,
        median_delta=0.0,
        ci_low=-1.0,
        ci_high=2.0,
        pair_wins=14,
        pair_losses=11,
        pair_ties=32,
        valid_pairs=57,
        runtime_regression_rate=1.0,
    )
    config = ProtocolConfig.model_validate(
        {
            "pairing_validity": "trajectory_divergent",
            "runtime": {"runtime_model": "budget_exhausting"},
        }
    )

    result = screening_gate(stats, config)

    assert result.outcome == "fail"
    assert result.reason_codes == ("SCREENING_FAIL_WIN_RATE",)


def test_budget_exhausting_runtime_ratio_does_not_override_case_failure():
    stats = _make_stats(
        wins=3,
        losses=4,
        ties=9,
        win_rate=3 / 16,
        median_delta=0.0,
        ci_low=-1.0,
        ci_high=2.0,
        pair_wins=14,
        pair_losses=11,
        pair_ties=32,
        valid_pairs=57,
        runtime_ratio_median=2.0,
        runtime_regression_rate=0.0,
        runtime_pairs=16,
    )
    config = ProtocolConfig.model_validate(
        {
            "pairing_validity": "trajectory_divergent",
            "runtime": {"runtime_model": "budget_exhausting"},
        }
    )

    result = screening_gate(stats, config)

    assert result.outcome == "fail"
    assert result.reason_codes == ("SCREENING_FAIL_WIN_RATE",)


@pytest.mark.parametrize("gate_func", (screening_gate, validation_gate, frozen_gate))
def test_generic_runtime_ratio_does_not_override_problem_objective(gate_func):
    stats = _make_stats(
        win_rate=1.0,
        median_delta=10.0,
        ci_low=1.0,
        ci_high=20.0,
        runtime_ratio_median=3.0,
        runtime_pairs=10,
    )

    result = gate_func(stats, _cfg)

    assert result.outcome == "pass"
    assert "RUNTIME_REGRESSION" not in result.reason_codes


def test_budget_exhausting_protocol_does_not_apply_comparative_runtime_threshold():
    stats = _make_stats(
        win_rate=1.0,
        median_delta=10.0,
        ci_low=1.0,
        ci_high=20.0,
        runtime_ratio_median=99.0,
        runtime_pairs=10,
    )
    config = ProtocolConfig.model_validate(
        {"runtime": {"runtime_model": "budget_exhausting"}}
    )

    result = frozen_gate(stats, config)

    assert result.outcome == "pass"
    assert result.reason_codes == ("FROZEN_PASS",)


def test_expanded_screening_cannot_advance_below_case_threshold():
    stats = _make_stats(
        win_rate=0.50,
        median_delta=100.0,
        ci_low=0.0,
        ci_high=200.0,
    )
    config = ProtocolConfig.model_validate(
        {
            "gates": {
                "screening": {
                    "win_rate_min": 0.55,
                }
            }
        }
    )

    initial = screening_gate(stats, config)
    expanded = screening_gate(stats, config, expanded=True)

    assert initial.outcome == "expand"
    assert expanded.outcome == "unclear"
    assert expanded.reason_codes == (
        "SCREENING_EXPAND_EXHAUSTED_CASE_LEVEL_UNCERTAIN",
    )


def test_expanded_screening_pair_signal_cannot_advance_candidate():
    stats = _make_stats(
        wins=5,
        losses=4,
        ties=3,
        win_rate=5 / 12,
        median_delta=16.75,
        ci_low=3.25,
        ci_high=36.5,
        pair_wins=46,
        pair_losses=12,
        pair_ties=6,
    )
    config = ProtocolConfig.model_validate(
        {
            "pairing_validity": "trajectory_divergent",
            "gates": {
                "screening": {
                    "win_rate_min": 0.60,
                }
            },
        }
    )

    result = screening_gate(stats, config, expanded=True)

    assert result.outcome == "fail"
    assert result.reason_codes == ("SCREENING_FAIL_WIN_RATE",)


@pytest.mark.parametrize("median_delta", (5.0, -5.0))
def test_expanded_validation_protocol_owns_final_verdict(
    median_delta,
):
    stats = _make_stats(
        win_rate=0.70,
        median_delta=median_delta,
        ci_low=-0.01,
        ci_high=0.02,
    )

    result = validation_gate(stats, _cfg, expanded=True)

    assert result.outcome == "fail"
    assert result.reason_codes == (
        "VALIDATION_EXPAND_EXHAUSTED_INSUFFICIENT_EVIDENCE",
    )


def test_budget_exhausting_high_runtime_ratio_does_not_override_case_failure():
    stats = _make_stats(
        wins=3,
        losses=4,
        ties=9,
        win_rate=3 / 16,
        median_delta=0.0,
        ci_low=-1.0,
        ci_high=2.0,
        pair_wins=14,
        pair_losses=11,
        pair_ties=32,
        valid_pairs=57,
        runtime_ratio_median=9.0,
        runtime_regression_rate=1.0,
        runtime_pairs=16,
    )
    config = ProtocolConfig.model_validate(
        {
            "pairing_validity": "trajectory_divergent",
            "runtime": {"runtime_model": "budget_exhausting"},
        }
    )

    result = screening_gate(stats, config)

    assert result.outcome == "fail"
    assert result.reason_codes == ("SCREENING_FAIL_WIN_RATE",)


def test_trajectory_divergent_negative_delta_still_fails_screening():
    stats = _make_stats(
        wins=3,
        losses=4,
        ties=9,
        win_rate=3 / 16,
        median_delta=-0.01,
        ci_low=-1.0,
        ci_high=2.0,
        pair_wins=14,
        pair_losses=11,
        pair_ties=32,
        valid_pairs=57,
    )
    config = ProtocolConfig.model_validate(
        {"pairing_validity": "trajectory_divergent"}
    )

    result = screening_gate(stats, config)

    assert result.outcome == "fail"
    assert result.reason_codes == ("SCREENING_FAIL_WIN_RATE",)


def test_trajectory_divergent_loss_heavy_screening_still_fails():
    stats = _make_stats(
        wins=1,
        losses=7,
        ties=4,
        win_rate=1 / 12,
        median_delta=0.0,
        ci_low=-1.0,
        ci_high=2.0,
        valid_pairs=12,
    )
    config = ProtocolConfig.model_validate(
        {"pairing_validity": "trajectory_divergent"}
    )

    result = screening_gate(stats, config)

    assert result.outcome == "fail"
    assert result.reason_codes == ("SCREENING_FAIL_WIN_RATE",)


def test_trajectory_divergent_candidate_failure_still_fails_screening():
    stats = _make_stats(
        wins=3,
        losses=4,
        ties=9,
        win_rate=3 / 16,
        median_delta=0.0,
        ci_low=-1.0,
        ci_high=2.0,
        pair_wins=14,
        pair_losses=11,
        pair_ties=32,
        valid_pairs=57,
        failed_pairs=1,
        candidate_failed_pairs=1,
    )
    config = ProtocolConfig.model_validate(
        {"pairing_validity": "trajectory_divergent"}
    )

    result = screening_gate(stats, config)

    assert result.outcome == "fail"
    assert result.reason_codes == ("SCREENING_FAIL_WIN_RATE",)


def test_screening_gate_small_nonnegative_delta_does_not_pass():
    stats = _make_stats(win_rate=0.7, median_delta=0.0001)
    result = screening_gate(stats, _cfg)
    assert result.outcome == "expand"
    assert result.reason_codes == ("SCREENING_EXPAND_CASE_LEVEL_UNCERTAIN",)


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


def test_validation_runtime_tie_does_not_replace_objective_improvement():
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
    assert result.outcome == "fail"
    assert result.reason_codes == ("VALIDATION_FAIL_NO_HIERARCHICAL_GAIN",)


def test_validation_gate_fail_ci_negative():
    stats = _make_stats(win_rate=0.7, ci_low=-0.02, ci_high=-0.001)
    result = validation_gate(stats, _cfg)
    assert result.outcome == "fail"


def test_validation_gate_expand():
    stats = _make_stats(win_rate=0.7, ci_low=-0.005, ci_high=0.02)
    result = validation_gate(stats, _cfg)
    assert result.outcome == "expand"


def test_validation_gate_expands_reachable_no_loss_hierarchical_uncertainty():
    config = ProtocolConfig.model_validate(
        {
            "validation": {"n_cases": 8, "n_seeds": 4, "expand_to": 12},
            "gates": {"validation": {"win_rate_min": 0.66}},
        }
    )
    stats = _make_stats(
        n_cases=8,
        wins=4,
        losses=0,
        ties=4,
        win_rate=0.5,
        median_delta=11.75,
        ci_low=0.0,
        ci_high=79.75,
        statistical_status="uncertain",
        statistical_metric="total_distance",
        pair_wins=20,
        pair_losses=5,
        pair_ties=7,
    )

    result = validation_gate(stats, config)

    assert result.outcome == "expand"
    assert result.reason_codes == (
        "VALIDATION_EXPAND_HIERARCHICAL_UNCERTAIN",
    )


def test_expanded_validation_does_not_repeat_no_loss_reachability_exception():
    config = ProtocolConfig.model_validate(
        {
            "validation": {"n_cases": 8, "n_seeds": 4, "expand_to": 12},
            "gates": {"validation": {"win_rate_min": 0.66}},
        }
    )
    stats = _make_stats(
        n_cases=8,
        wins=4,
        losses=0,
        ties=4,
        win_rate=0.5,
        median_delta=11.75,
        ci_low=0.0,
        ci_high=79.75,
        statistical_status="uncertain",
        statistical_metric="total_distance",
        pair_wins=20,
        pair_losses=5,
        pair_ties=7,
    )

    result = validation_gate(stats, config, expanded=True)

    assert result.outcome == "fail"
    assert result.reason_codes == ("VALIDATION_FAIL_WIN_RATE",)


def test_validation_gate_does_not_expand_when_win_threshold_is_unreachable():
    config = ProtocolConfig.model_validate(
        {
            "validation": {"n_cases": 8, "n_seeds": 4, "expand_to": 12},
            "gates": {"validation": {"win_rate_min": 0.66}},
        }
    )
    stats = _make_stats(
        n_cases=8,
        wins=3,
        losses=0,
        ties=5,
        win_rate=3 / 8,
        median_delta=1.0,
        ci_low=0.0,
        ci_high=10.0,
        statistical_status="uncertain",
        statistical_metric="total_distance",
    )

    result = validation_gate(stats, config)

    assert result.outcome == "fail"
    assert result.reason_codes == ("VALIDATION_FAIL_WIN_RATE",)


def test_validation_gate_hierarchical_tie_has_no_gain_and_negative_stays_negative():
    tie_stats = _make_stats(
        n_cases=8,
        wins=0,
        losses=0,
        ties=8,
        win_rate=0.0,
        median_delta=0.0,
        ci_low=0.0,
        ci_high=0.0,
        statistical_status="tie",
        statistical_metric="total_distance",
    )
    negative_stats = _make_stats(
        n_cases=8,
        wins=3,
        losses=1,
        ties=4,
        win_rate=3 / 8,
        median_delta=-1.0,
        ci_low=-10.0,
        ci_high=-0.1,
        statistical_status="negative",
        statistical_metric="total_distance",
    )

    tie_result = validation_gate(tie_stats, _cfg)
    negative_result = validation_gate(negative_stats, _cfg)

    assert tie_result.outcome == "fail"
    assert tie_result.reason_codes == ("VALIDATION_FAIL_NO_HIERARCHICAL_GAIN",)
    assert negative_result.outcome == "fail"
    assert negative_result.reason_codes == (
        "VALIDATION_FAIL_HIERARCHICAL_NEGATIVE",
    )


def test_frozen_gate_pass():
    stats = _make_stats(ci_low=0.005, ci_high=0.02)
    result = frozen_gate(stats, _cfg)
    assert result.outcome == "pass"


def test_frozen_runtime_tie_does_not_replace_objective_improvement():
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
    assert result.outcome == "fail"
    assert result.reason_codes == ("FROZEN_FAIL_NO_HIERARCHICAL_GAIN",)


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
