"""Focused tests split from test_decision.py."""

from pathlib import Path

from scion.core.branch_lifecycle_policy import (
    BRANCH_LIFECYCLE_ARCHIVE_LINEAGE,
)

from .decision_test_support import *  # noqa: F401,F403

def test_decision_contract_fail():
    f = _features(contract_passed=False)
    out = _engine.decide(f)
    assert out.decision == Decision.ABANDON
    assert "CONTRACT_FAILED" in out.reason_codes


def test_decision_verification_fail():
    f = _features(verification_passed=False)
    out = _engine.decide(f)
    assert out.decision == Decision.ABANDON


def test_decision_canary_fail():
    f = _features(canary_passed=False)
    out = _engine.decide(f)
    assert out.decision == Decision.ABANDON


def test_decision_runtime_guard_timeout_vetoes_candidate():
    f = _features(runtime_guard_passed=False, runtime_guard_timeout=True)
    out = _engine.decide(f)
    assert out.decision == Decision.ABANDON
    assert "RUNTIME_GUARD_TIMEOUT" in out.reason_codes


def test_decision_candidate_runtime_failure_vetoes_objective_win():
    f = _features(
        stage="screening",
        win_rate=1.0,
        median_delta=100.0,
        candidate_failed_pairs=1,
    )
    out = _engine.decide(f)
    assert out.decision == Decision.ABANDON
    assert "CANDIDATE_RUNTIME_FAILURE" in out.reason_codes


def test_decision_candidate_runtime_failure_preempts_lifecycle_policy():
    class ExplodingLifecyclePolicy:
        def decide(self, *_args, **_kwargs):
            raise AssertionError("lifecycle policy should not run")

        def evidence_metadata(self, *_args, **_kwargs):
            raise AssertionError("lifecycle evidence should not be requested")

    engine = DecisionEngine(_cfg, lifecycle_policy=ExplodingLifecyclePolicy())
    f = _features(
        stage="screening",
        win_rate=0.0,
        median_delta=0.0,
        candidate_failed_pairs=1,
    )

    out = engine.decide(f)

    assert out.decision == Decision.ABANDON
    assert out.reason_codes == ("CANDIDATE_RUNTIME_FAILURE",)
    assert out.decision_layer_source == "stage_decision"


def test_decision_screening_champion_partial_evidence_blocks_validation_queue():
    f = _features(
        stage="screening",
        win_rate=1.0,
        median_delta=100.0,
        failed_pairs=1,
        champion_failed_pairs=1,
    )
    out = _engine.decide(f)
    assert out.decision == Decision.CONTINUE_EXPLORE
    assert out.reason_codes == ("SCREENING_PARTIAL_CHAMPION_EVIDENCE",)


def test_decision_runtime_regression_vetoes_objective_win():
    f = _features(
        stage="frozen",
        ci_low=10.0,
        ci_high=20.0,
        protocol_gate_outcome="pass",
        runtime_ratio_median=2.5,
    )
    out = _engine.decide(f)
    assert out.decision == Decision.ABANDON
    assert "RUNTIME_REGRESSION" in out.reason_codes


def test_decision_runtime_regression_threshold_comes_from_protocol_config():
    f = _features(
        stage="frozen",
        ci_low=10.0,
        ci_high=20.0,
        protocol_gate_outcome="pass",
        runtime_ratio_median=2.5,
    )
    engine = DecisionEngine(ProtocolConfig(runtime={"max_runtime_ratio": 3.0}))
    out = engine.decide(f)
    assert out.decision == Decision.PROMOTE
    assert "FROZEN_PASS" in out.reason_codes


def test_decision_frozen_protocol_gate_fail_cannot_promote():
    f = _features(
        stage="frozen",
        ci_low=10.0,
        ci_high=20.0,
        protocol_gate_outcome="fail",
    )
    out = _engine.decide(f)
    assert out.decision == Decision.ABANDON
    assert "FROZEN_PROTOCOL_GATE_NOT_PASS" in out.reason_codes


def test_decision_screening_high_win_positive_effect_queues_validation():
    f = _features(stage="screening", win_rate=0.7, median_delta=0.01)
    out = _engine.decide(f)
    assert out.decision == Decision.QUEUE_VALIDATE
    assert "SCREENING_PASS" in out.reason_codes


def test_decision_lifecycle_archive_abandon_has_structured_fields():
    f = _features(
        stage="screening",
        win_rate=0.4,
        median_delta=-0.01,
        ci_low=-0.02,
        ci_high=0.01,
    )

    out = _engine.decide(f)

    assert out.stage_decision == Decision.CONTINUE_EXPLORE
    assert out.decision == Decision.ABANDON
    assert out.final_decision == Decision.ABANDON
    assert out.lifecycle_action == "archive_lineage"
    assert out.lifecycle_reason_codes == (
        BRANCH_LIFECYCLE_ARCHIVE_LINEAGE,
        "SCREENING_SOFT_ABANDON_NEGATIVE_DELTA",
    )
    assert out.decision_layer_source == "stage_decision"
    assert out.lifecycle_policy_evidence["bookkeeping_role"] == (
        "screening_result_lifecycle_annotation"
    )
    assert out.lifecycle_policy_evidence["legacy_decision_layer_source"] == (
        "lifecycle_policy"
    )


def test_decision_screening_fail():
    f = _features(stage="screening", win_rate=0.3, median_delta=0.01)
    out = _engine.decide(f)
    assert out.decision == Decision.CONTINUE_EXPLORE


def test_decision_screening_runtime_tie_improvement_queues_validation():
    f = _features(
        stage="screening",
        win_rate=0.0,
        median_delta=0.0,
        ci_low=0.0,
        ci_high=0.0,
        runtime_ratio_median=0.25,
        runtime_delta_median_ms=-1000.0,
        runtime_pairs=4,
    )
    out = _engine.decide(f)
    assert out.decision == Decision.QUEUE_VALIDATE
    assert "SCREENING_PASS_RUNTIME_TIE_IMPROVEMENT" in out.reason_codes


def test_decision_runtime_tie_fresh_required_continues_without_promotion():
    f = _features(
        stage="screening",
        win_rate=0.0,
        median_delta=0.0,
        ci_low=0.0,
        ci_high=0.0,
        runtime_pairs=0,
        runtime_evidence_status="fresh_champion_required",
    )
    out = _engine.decide(f)
    assert out.decision == Decision.CONTINUE_EXPLORE
    assert out.reason_codes == ("RUNTIME_TIE_FRESH_CHAMPION_REQUIRED",)


def test_decision_screening_low_win_positive_effect_expands_screening():
    f = _features(stage="screening", win_rate=0.55, median_delta=0.01)
    out = _engine.decide(f)
    assert out.decision == Decision.EXPAND_SCREENING
    assert "SCREENING_EXPAND" in out.reason_codes


def test_decision_trajectory_divergent_low_snr_expands_below_half_win_rate():
    engine = DecisionEngine(
        ProtocolConfig.model_validate({"pairing_validity": "trajectory_divergent"})
    )
    f = _features(
        stage="screening",
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
    )

    out = engine.decide(f)

    assert out.decision == Decision.EXPAND_SCREENING
    assert out.reason_codes == (
        "SCREENING_EXPAND_LOW_SNR_TRAJECTORY_DIVERGENT",
    )


def test_decision_comparative_runtime_regression_rate_blocks_low_snr_expand():
    engine = DecisionEngine(
        ProtocolConfig.model_validate({"pairing_validity": "trajectory_divergent"})
    )
    f = _features(
        stage="screening",
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
        runtime_ratio_median=1.0,
        runtime_regression_rate=1.0,
        runtime_pairs=16,
    )

    out = engine.decide(f)

    assert out.decision == Decision.ABANDON
    assert "SCREENING_EXPAND_LOW_SNR_TRAJECTORY_DIVERGENT" not in out.reason_codes
    assert "SCREENING_SOFT_ABANDON_RUNTIME_REGRESSION_RATE" in out.reason_codes


def test_decision_budget_exhausting_runtime_regression_rate_does_not_block_low_snr_expand():
    engine = DecisionEngine(
        ProtocolConfig.model_validate(
            {
                "pairing_validity": "trajectory_divergent",
                "runtime": {"runtime_model": "budget_exhausting"},
            }
        )
    )
    f = _features(
        stage="screening",
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
        runtime_ratio_median=1.0,
        runtime_regression_rate=1.0,
        runtime_pairs=16,
    )

    out = engine.decide(f)

    assert out.decision == Decision.EXPAND_SCREENING
    assert out.reason_codes == (
        "SCREENING_EXPAND_LOW_SNR_TRAJECTORY_DIVERGENT",
    )


def test_decision_trajectory_stable_low_snr_shape_does_not_expand():
    f = _features(
        stage="screening",
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
    )

    out = _engine.decide(f)

    assert out.decision == Decision.CONTINUE_EXPLORE
    assert "SCREENING_EXPAND_LOW_SNR_TRAJECTORY_DIVERGENT" not in out.reason_codes


def test_decision_trajectory_divergent_loss_heavy_does_not_expand():
    engine = DecisionEngine(
        ProtocolConfig.model_validate({"pairing_validity": "trajectory_divergent"})
    )
    f = _features(
        stage="screening",
        wins=1,
        losses=7,
        ties=4,
        win_rate=1 / 12,
        median_delta=0.0,
        ci_low=-1.0,
        ci_high=2.0,
    )

    out = engine.decide(f)

    assert out.decision == Decision.CONTINUE_EXPLORE
    assert "SCREENING_EXPAND_LOW_SNR_TRAJECTORY_DIVERGENT" not in out.reason_codes


def test_decision_low_snr_expand_exhausted_continues_with_relaxed_lifecycle():
    engine = DecisionEngine(
        ProtocolConfig.model_validate({"pairing_validity": "trajectory_divergent"})
    )
    f = _features(
        stage="screening",
        wins=0,
        losses=0,
        ties=10,
        win_rate=0.0,
        median_delta=0.0,
        ci_low=0.0,
        ci_high=0.0,
        pair_wins=12,
        pair_losses=12,
        pair_ties=40,
    )
    from dataclasses import replace

    f = replace(f, screening_expand_count=1, lifecycle_zero_win_streak=2)

    out = engine.decide(f)

    assert out.decision == Decision.CONTINUE_EXPLORE
    assert "SCREENING_LOW_SNR_EXPAND_EXHAUSTED_CONTINUE" in out.reason_codes
    assert out.lifecycle_action == "retain_head"
    assert "SCREENING_ZERO_WIN_STREAK_EXHAUSTED" not in out.reason_codes


def test_decision_budget_exhausting_runtime_regression_rate_does_not_archive_low_snr_followup():
    engine = DecisionEngine(
        ProtocolConfig.model_validate(
            {
                "pairing_validity": "trajectory_divergent",
                "runtime": {"runtime_model": "budget_exhausting"},
            }
        )
    )
    f = _features(
        stage="screening",
        wins=0,
        losses=0,
        ties=10,
        win_rate=0.0,
        median_delta=0.0,
        ci_low=0.0,
        ci_high=0.0,
        pair_wins=12,
        pair_losses=12,
        pair_ties=40,
        runtime_ratio_median=1.0,
        runtime_regression_rate=1.0,
        runtime_pairs=16,
    )
    from dataclasses import replace

    f = replace(f, screening_expand_count=1, lifecycle_zero_win_streak=2)

    out = engine.decide(f)

    assert out.decision == Decision.CONTINUE_EXPLORE
    assert "SCREENING_LOW_SNR_EXPAND_EXHAUSTED_CONTINUE" in out.reason_codes
    assert out.lifecycle_action == "retain_head"
    assert "SCREENING_SOFT_ABANDON_RUNTIME_REGRESSION_RATE" not in out.reason_codes
    assert "SCREENING_ZERO_WIN_STREAK_EXHAUSTED" not in out.reason_codes


def test_decision_screening_expand_exhausted_borderline_positive_delta():
    """Default config does not advance below-threshold expanded screening results."""
    from scion.core.models import DecisionFeatures
    f = DecisionFeatures(
        branch_id=str(uuid.uuid4()),
        hypothesis_action="modify",
        stage="screening",
        contract_passed=True, verification_passed=True, canary_passed=True,
        n_cases=10, win_rate=0.63, median_delta=100.0,
        ci_low=None, ci_high=None,
        stale=False, recent_retry_count=0, recent_failure_codes=(),
        budget_remaining_ratio=1.0, screening_expand_count=1,
    )
    out = _engine.decide(f)
    assert out.stage_decision == Decision.CONTINUE_EXPLORE
    assert "SCREENING_EXPAND_EXHAUSTED" in out.reason_codes
    assert "SCREENING_EXPAND_EXHAUSTED_BORDERLINE_POLICY_PASS" not in out.reason_codes


def test_decision_screening_expand_exhausted_borderline_policy_queues_validation():
    """Explicit expanded-borderline policy can advance warehouse prod wr=0.50."""
    from scion.core.models import DecisionFeatures
    engine = DecisionEngine(
        ProtocolConfig(
            gates={
                "screening": {
                    "win_rate_min": 0.55,
                    "expanded_borderline_advance": {
                        "enabled": True,
                        "win_rate_window": 0.05,
                    },
                },
            },
        )
    )
    f = DecisionFeatures(
        branch_id=str(uuid.uuid4()),
        hypothesis_action="modify",
        stage="screening",
        contract_passed=True, verification_passed=True, canary_passed=True,
        n_cases=10, win_rate=0.50, median_delta=100.0,
        ci_low=None, ci_high=None,
        stale=False, recent_retry_count=0, recent_failure_codes=(),
        budget_remaining_ratio=1.0, screening_expand_count=1,
    )

    out = engine.decide(f)

    assert out.decision == Decision.QUEUE_VALIDATE
    assert "SCREENING_EXPAND_EXHAUSTED_BORDERLINE_POLICY_PASS" in out.reason_codes
    assert "SCREENING_BELOW_WIN_RATE_MIN_ALLOWED_BY_POLICY" in out.reason_codes


def test_decision_trajectory_divergent_pair_signal_after_expand_queues_diagnostic_validation():
    """CVRP-style pair-level signal can enter validation after expand is exhausted."""
    from scion.core.models import DecisionFeatures

    engine = DecisionEngine(
        ProtocolConfig.model_validate(
            {
                "pairing_validity": "trajectory_divergent",
                "gates": {
                    "screening": {
                        "win_rate_min": 0.60,
                        "expanded_borderline_advance": {
                            "enabled": True,
                            "win_rate_window": 0.10,
                            "require_median_delta_nonnegative": True,
                            "require_ci_low_nonnegative": True,
                            "allow_pair_level_signal": True,
                            "pair_win_rate_min": 0.50,
                            "min_pair_total": 16,
                            "min_pair_wins": 8,
                            "min_pair_win_loss_margin": 1,
                            "pair_non_tie_win_rate_min": 0.60,
                            "max_pair_loss_rate": 0.40,
                        },
                    },
                },
            }
        )
    )
    f = DecisionFeatures(
        branch_id=str(uuid.uuid4()),
        hypothesis_action="modify",
        stage="screening",
        contract_passed=True,
        verification_passed=True,
        canary_passed=True,
        n_cases=12,
        wins=5,
        losses=4,
        ties=3,
        win_rate=5 / 12,
        median_delta=16.75,
        ci_low=3.25,
        ci_high=36.5,
        stale=False,
        recent_retry_count=0,
        recent_failure_codes=(),
        budget_remaining_ratio=1.0,
        pair_wins=46,
        pair_losses=12,
        pair_ties=6,
        screening_expand_count=1,
    )

    out = engine.decide(f)

    assert out.decision == Decision.QUEUE_VALIDATE
    assert "SCREENING_EXPAND_EXHAUSTED_PAIR_SIGNAL_POLICY_PASS" in out.reason_codes
    assert "SCREENING_PAIR_LEVEL_SIGNAL_DIAGNOSTIC_VALIDATE" in out.reason_codes


def _warehouse_prod_engine_and_config():
    from scion.problem.bridge import load_problem_spec_v1_from_yaml

    repo_scion_dir = Path(__file__).resolve().parents[2]
    problem = load_problem_spec_v1_from_yaml(
        repo_scion_dir / "problems" / "warehouse_delivery" / "problem-v1.yaml"
    )
    config = ProtocolConfig.from_yaml(
        repo_scion_dir / "problems" / "warehouse_delivery" / "protocol_prod.yaml"
    ).with_problem_measurement(problem)
    return DecisionEngine(config), config


def _warehouse_expanded_screening_features(
    *,
    case_wins: int,
    case_losses: int,
    case_ties: int,
    pair_wins: int,
    pair_losses: int,
    pair_ties: int,
    median_delta: float,
    ci_low: float,
    ci_high: float,
):
    from scion.core.models import DecisionFeatures

    n_cases = case_wins + case_losses + case_ties
    return DecisionFeatures(
        branch_id=str(uuid.uuid4()),
        hypothesis_action="modify",
        stage="screening",
        contract_passed=True,
        verification_passed=True,
        canary_passed=True,
        n_cases=n_cases,
        wins=case_wins,
        losses=case_losses,
        ties=case_ties,
        win_rate=case_wins / n_cases,
        median_delta=median_delta,
        ci_low=ci_low,
        ci_high=ci_high,
        stale=False,
        recent_retry_count=0,
        recent_failure_codes=(),
        budget_remaining_ratio=1.0,
        pair_wins=pair_wins,
        pair_losses=pair_losses,
        pair_ties=pair_ties,
        screening_expand_count=1,
    )


def test_decision_warehouse_prod_field_gate_shape_a_queues_diagnostic_validation():
    """Expanded positive pair/case signal queues diagnostic validation."""

    engine, config = _warehouse_prod_engine_and_config()
    f = _warehouse_expanded_screening_features(
        case_wins=3,
        case_losses=1,
        case_ties=10,
        pair_wins=13,
        pair_losses=6,
        pair_ties=9,
        median_delta=300.0,
        ci_low=0.0,
        ci_high=875.0,
    )

    out = engine.decide(f)

    assert config.pairing_validity == "trajectory_divergent"
    assert out.decision == Decision.QUEUE_VALIDATE
    assert "SCREENING_EXPAND_EXHAUSTED_PAIR_SIGNAL_POLICY_PASS" in out.reason_codes
    assert "SCREENING_PAIR_LEVEL_SIGNAL_DIAGNOSTIC_VALIDATE" in out.reason_codes


def test_decision_warehouse_prod_field_gate_shape_b_fails_closed():
    """Expanded loss-regressive signal cannot queue validation."""

    engine, _config = _warehouse_prod_engine_and_config()
    f = _warehouse_expanded_screening_features(
        case_wins=4,
        case_losses=2,
        case_ties=10,
        pair_wins=14,
        pair_losses=12,
        pair_ties=6,
        median_delta=-50.0,
        ci_low=-200.0,
        ci_high=500.0,
    )

    out = engine.decide(f)

    assert out.stage_decision == Decision.CONTINUE_EXPLORE
    assert out.decision != Decision.QUEUE_VALIDATE
    assert "SCREENING_EXPAND_EXHAUSTED_BORDERLINE_NEGATIVE_DELTA" in out.reason_codes
    assert "SCREENING_PAIR_LEVEL_SIGNAL_DIAGNOSTIC_VALIDATE" not in out.reason_codes


def test_decision_warehouse_prod_field_gate_shape_c_does_not_validate():
    """Loss-dominated marginal shape remains below diagnostic validation."""

    engine, _config = _warehouse_prod_engine_and_config()
    f = _warehouse_expanded_screening_features(
        case_wins=1,
        case_losses=2,
        case_ties=3,
        pair_wins=3,
        pair_losses=4,
        pair_ties=5,
        median_delta=0.0,
        ci_low=-50.0,
        ci_high=50.0,
    )

    out = engine.decide(f)

    assert out.stage_decision == Decision.CONTINUE_EXPLORE
    assert out.decision != Decision.QUEUE_VALIDATE
    assert "SCREENING_FAIL_WIN_RATE" in out.reason_codes
    assert "SCREENING_PAIR_LEVEL_SIGNAL_DIAGNOSTIC_VALIDATE" not in out.reason_codes


def test_decision_warehouse_prod_pair_signal_after_expand_queues_diagnostic_validation():
    """Warehouse prod can diagnose low-SNR case ties with strong pair evidence."""
    from scion.core.models import DecisionFeatures
    from scion.problem.bridge import load_problem_spec_v1_from_yaml

    repo_scion_dir = Path(__file__).resolve().parents[2]
    problem = load_problem_spec_v1_from_yaml(
        repo_scion_dir / "problems" / "warehouse_delivery" / "problem-v1.yaml"
    )
    config = ProtocolConfig.from_yaml(
        repo_scion_dir / "problems" / "warehouse_delivery" / "protocol_prod.yaml"
    ).with_problem_measurement(problem)
    engine = DecisionEngine(config)
    f = DecisionFeatures(
        branch_id=str(uuid.uuid4()),
        hypothesis_action="modify",
        stage="screening",
        contract_passed=True,
        verification_passed=True,
        canary_passed=True,
        n_cases=6,
        wins=2,
        losses=0,
        ties=4,
        win_rate=2 / 6,
        median_delta=0.0,
        ci_low=-1.0,
        ci_high=1.0,
        stale=False,
        recent_retry_count=0,
        recent_failure_codes=(),
        budget_remaining_ratio=1.0,
        pair_wins=6,
        pair_losses=2,
        pair_ties=4,
        screening_expand_count=1,
    )

    out = engine.decide(f)

    assert config.pairing_validity == "trajectory_divergent"
    assert out.decision == Decision.QUEUE_VALIDATE
    assert "SCREENING_EXPAND_EXHAUSTED_PAIR_SIGNAL_POLICY_PASS" in out.reason_codes
    assert "SCREENING_PAIR_LEVEL_SIGNAL_DIAGNOSTIC_VALIDATE" in out.reason_codes


def test_decision_warehouse_prod_pair_signal_fails_closed_on_negative_median():
    """Pair-level diagnostic validation still requires non-negative effect."""
    from dataclasses import replace
    from scion.core.models import DecisionFeatures
    from scion.problem.bridge import load_problem_spec_v1_from_yaml

    repo_scion_dir = Path(__file__).resolve().parents[2]
    problem = load_problem_spec_v1_from_yaml(
        repo_scion_dir / "problems" / "warehouse_delivery" / "problem-v1.yaml"
    )
    config = ProtocolConfig.from_yaml(
        repo_scion_dir / "problems" / "warehouse_delivery" / "protocol_prod.yaml"
    ).with_problem_measurement(problem)
    engine = DecisionEngine(config)
    base = DecisionFeatures(
        branch_id=str(uuid.uuid4()),
        hypothesis_action="modify",
        stage="screening",
        contract_passed=True,
        verification_passed=True,
        canary_passed=True,
        n_cases=6,
        wins=2,
        losses=0,
        ties=4,
        win_rate=2 / 6,
        median_delta=0.0,
        ci_low=-1.0,
        ci_high=1.0,
        stale=False,
        recent_retry_count=0,
        recent_failure_codes=(),
        budget_remaining_ratio=1.0,
        pair_wins=6,
        pair_losses=2,
        pair_ties=4,
        screening_expand_count=1,
    )

    out = engine.decide(replace(base, median_delta=-0.1))

    assert out.stage_decision == Decision.CONTINUE_EXPLORE
    assert out.decision != Decision.QUEUE_VALIDATE
    assert "SCREENING_EXPAND_EXHAUSTED_BORDERLINE_NEGATIVE_DELTA" in out.reason_codes
    assert "SCREENING_PAIR_LEVEL_SIGNAL_DIAGNOSTIC_VALIDATE" not in out.reason_codes


def test_decision_warehouse_prod_pair_signal_fails_closed_when_loss_heavy():
    """Loss-heavy pair evidence cannot reach diagnostic validation."""
    from dataclasses import replace
    from scion.core.models import DecisionFeatures
    from scion.problem.bridge import load_problem_spec_v1_from_yaml

    repo_scion_dir = Path(__file__).resolve().parents[2]
    problem = load_problem_spec_v1_from_yaml(
        repo_scion_dir / "problems" / "warehouse_delivery" / "problem-v1.yaml"
    )
    config = ProtocolConfig.from_yaml(
        repo_scion_dir / "problems" / "warehouse_delivery" / "protocol_prod.yaml"
    ).with_problem_measurement(problem)
    engine = DecisionEngine(config)
    base = DecisionFeatures(
        branch_id=str(uuid.uuid4()),
        hypothesis_action="modify",
        stage="screening",
        contract_passed=True,
        verification_passed=True,
        canary_passed=True,
        n_cases=6,
        wins=2,
        losses=0,
        ties=4,
        win_rate=2 / 6,
        median_delta=0.0,
        ci_low=-1.0,
        ci_high=1.0,
        stale=False,
        recent_retry_count=0,
        recent_failure_codes=(),
        budget_remaining_ratio=1.0,
        pair_wins=6,
        pair_losses=2,
        pair_ties=4,
        screening_expand_count=1,
    )

    out = engine.decide(
        replace(base, pair_wins=4, pair_losses=6, pair_ties=2)
    )

    assert out.decision == Decision.CONTINUE_EXPLORE
    assert "SCREENING_PAIR_LEVEL_SIGNAL_DIAGNOSTIC_VALIDATE" not in out.reason_codes
    assert all("PASS" not in reason for reason in out.reason_codes)


def test_decision_pair_signal_after_expand_requires_explicit_policy():
    """Default trajectory-divergent policy continues after expand without pair policy."""
    from scion.core.models import DecisionFeatures

    engine = DecisionEngine(
        ProtocolConfig.model_validate({"pairing_validity": "trajectory_divergent"})
    )
    f = DecisionFeatures(
        branch_id=str(uuid.uuid4()),
        hypothesis_action="modify",
        stage="screening",
        contract_passed=True,
        verification_passed=True,
        canary_passed=True,
        n_cases=12,
        wins=5,
        losses=4,
        ties=3,
        win_rate=5 / 12,
        median_delta=16.75,
        ci_low=3.25,
        ci_high=36.5,
        stale=False,
        recent_retry_count=0,
        recent_failure_codes=(),
        budget_remaining_ratio=1.0,
        pair_wins=46,
        pair_losses=12,
        pair_ties=6,
        screening_expand_count=1,
    )

    out = engine.decide(f)

    assert out.decision == Decision.CONTINUE_EXPLORE
    assert "SCREENING_LOW_SNR_EXPAND_EXHAUSTED_CONTINUE" in out.reason_codes
    assert "SCREENING_PAIR_LEVEL_SIGNAL_DIAGNOSTIC_VALIDATE" not in out.reason_codes


def test_decision_pair_signal_after_expand_fails_closed_on_negative_ci_low():
    """Pair-level diagnostic validation still respects CI fail-closed policy."""
    from scion.core.models import DecisionFeatures

    engine = DecisionEngine(
        ProtocolConfig.model_validate(
            {
                "pairing_validity": "trajectory_divergent",
                "gates": {
                    "screening": {
                        "win_rate_min": 0.60,
                        "expanded_borderline_advance": {
                            "enabled": True,
                            "win_rate_window": 0.10,
                            "require_median_delta_nonnegative": True,
                            "require_ci_low_nonnegative": True,
                            "allow_pair_level_signal": True,
                            "pair_win_rate_min": 0.50,
                            "min_pair_total": 16,
                            "min_pair_wins": 8,
                            "min_pair_win_loss_margin": 1,
                            "pair_non_tie_win_rate_min": 0.60,
                            "max_pair_loss_rate": 0.40,
                        },
                    },
                },
            }
        )
    )
    f = DecisionFeatures(
        branch_id=str(uuid.uuid4()),
        hypothesis_action="modify",
        stage="screening",
        contract_passed=True,
        verification_passed=True,
        canary_passed=True,
        n_cases=12,
        wins=5,
        losses=4,
        ties=3,
        win_rate=5 / 12,
        median_delta=16.75,
        ci_low=-0.25,
        ci_high=36.5,
        stale=False,
        recent_retry_count=0,
        recent_failure_codes=(),
        budget_remaining_ratio=1.0,
        pair_wins=46,
        pair_losses=12,
        pair_ties=6,
        screening_expand_count=1,
    )

    out = engine.decide(f)

    assert out.decision == Decision.CONTINUE_EXPLORE
    assert "SCREENING_EXPAND_EXHAUSTED_BORDERLINE_NEGATIVE_CI_LOW" in out.reason_codes
    assert "SCREENING_PAIR_LEVEL_SIGNAL_DIAGNOSTIC_VALIDATE" not in out.reason_codes


def test_decision_pair_signal_after_expand_requires_min_pair_total():
    """Pair-level diagnostic validation is blocked by low pair sample size."""
    from scion.core.models import DecisionFeatures

    engine = DecisionEngine(
        ProtocolConfig.model_validate(
            {
                "pairing_validity": "trajectory_divergent",
                "gates": {
                    "screening": {
                        "win_rate_min": 0.60,
                        "expanded_borderline_advance": {
                            "enabled": True,
                            "win_rate_window": 0.10,
                            "require_median_delta_nonnegative": True,
                            "require_ci_low_nonnegative": True,
                            "allow_pair_level_signal": True,
                            "pair_win_rate_min": 0.50,
                            "min_pair_total": 16,
                            "min_pair_wins": 8,
                            "min_pair_win_loss_margin": 1,
                            "pair_non_tie_win_rate_min": 0.60,
                            "max_pair_loss_rate": 0.40,
                        },
                    },
                },
            }
        )
    )
    f = DecisionFeatures(
        branch_id=str(uuid.uuid4()),
        hypothesis_action="modify",
        stage="screening",
        contract_passed=True,
        verification_passed=True,
        canary_passed=True,
        n_cases=12,
        wins=5,
        losses=4,
        ties=3,
        win_rate=5 / 12,
        median_delta=16.75,
        ci_low=3.25,
        ci_high=36.5,
        stale=False,
        recent_retry_count=0,
        recent_failure_codes=(),
        budget_remaining_ratio=1.0,
        pair_wins=3,
        pair_losses=0,
        pair_ties=0,
        screening_expand_count=1,
    )

    out = engine.decide(f)

    assert out.decision == Decision.CONTINUE_EXPLORE
    assert "SCREENING_LOW_SNR_EXPAND_EXHAUSTED_CONTINUE" in out.reason_codes
    assert "SCREENING_PAIR_LEVEL_SIGNAL_DIAGNOSTIC_VALIDATE" not in out.reason_codes


def test_decision_pair_signal_after_expand_requires_non_tie_win_rate():
    """Pair-level diagnostic validation requires directional non-tie evidence."""
    from scion.core.models import DecisionFeatures

    engine = DecisionEngine(
        ProtocolConfig.model_validate(
            {
                "pairing_validity": "trajectory_divergent",
                "gates": {
                    "screening": {
                        "win_rate_min": 0.60,
                        "expanded_borderline_advance": {
                            "enabled": True,
                            "win_rate_window": 0.10,
                            "require_median_delta_nonnegative": True,
                            "require_ci_low_nonnegative": True,
                            "allow_pair_level_signal": True,
                            "pair_win_rate_min": 0.50,
                            "min_pair_total": 16,
                            "min_pair_wins": 8,
                            "min_pair_win_loss_margin": 1,
                            "pair_non_tie_win_rate_min": 0.60,
                            "max_pair_loss_rate": 0.50,
                        },
                    },
                },
            }
        )
    )
    f = DecisionFeatures(
        branch_id=str(uuid.uuid4()),
        hypothesis_action="modify",
        stage="screening",
        contract_passed=True,
        verification_passed=True,
        canary_passed=True,
        n_cases=12,
        wins=5,
        losses=4,
        ties=3,
        win_rate=5 / 12,
        median_delta=16.75,
        ci_low=3.25,
        ci_high=36.5,
        stale=False,
        recent_retry_count=0,
        recent_failure_codes=(),
        budget_remaining_ratio=1.0,
        pair_wins=20,
        pair_losses=18,
        pair_ties=2,
        screening_expand_count=1,
    )

    out = engine.decide(f)

    assert out.decision == Decision.CONTINUE_EXPLORE
    assert "SCREENING_LOW_SNR_EXPAND_EXHAUSTED_CONTINUE" in out.reason_codes
    assert "SCREENING_PAIR_LEVEL_SIGNAL_DIAGNOSTIC_VALIDATE" not in out.reason_codes


def test_decision_screening_expand_exhausted_borderline_policy_off_blocks_warehouse_case():
    """Warehouse prod wr=0.50 only advances when the protocol flag is explicit."""
    from scion.core.models import DecisionFeatures
    engine = DecisionEngine(
        ProtocolConfig(
            gates={
                "screening": {
                    "win_rate_min": 0.55,
                    "expanded_borderline_advance": {
                        "enabled": False,
                        "win_rate_window": 0.05,
                    },
                },
            },
        )
    )
    f = DecisionFeatures(
        branch_id=str(uuid.uuid4()),
        hypothesis_action="modify",
        stage="screening",
        contract_passed=True, verification_passed=True, canary_passed=True,
        n_cases=10, win_rate=0.50, median_delta=100.0,
        ci_low=None, ci_high=None,
        stale=False, recent_retry_count=0, recent_failure_codes=(),
        budget_remaining_ratio=1.0, screening_expand_count=1,
    )

    out = engine.decide(f)

    assert out.stage_decision == Decision.CONTINUE_EXPLORE
    assert "SCREENING_EXPAND_EXHAUSTED" in out.reason_codes
    assert "SCREENING_EXPAND_EXHAUSTED_BORDERLINE_POLICY_PASS" not in out.reason_codes


def test_decision_screening_expand_exhausted_borderline_negative_delta():
    """Explicit borderline policy fails closed for negative median_delta."""
    from scion.core.models import DecisionFeatures
    engine = DecisionEngine(
        ProtocolConfig(
            gates={
                "screening": {
                    "expanded_borderline_advance": {
                        "enabled": True,
                        "win_rate_window": 0.05,
                    },
                },
            },
        )
    )
    f = DecisionFeatures(
        branch_id=str(uuid.uuid4()),
        hypothesis_action="modify",
        stage="screening",
        contract_passed=True, verification_passed=True, canary_passed=True,
        n_cases=10, win_rate=0.63, median_delta=-1200.0,
        ci_low=None, ci_high=None,
        stale=False, recent_retry_count=0, recent_failure_codes=(),
        budget_remaining_ratio=1.0, screening_expand_count=1,
    )
    out = engine.decide(f)
    assert out.stage_decision == Decision.CONTINUE_EXPLORE
    assert "SCREENING_EXPAND_EXHAUSTED_BORDERLINE_NEGATIVE_DELTA" in out.reason_codes
    assert "SCREENING_BORDERLINE_POLICY_FAIL_CLOSED" in out.reason_codes


def test_decision_screening_expand_exhausted_borderline_loss_heavy_fails_closed():
    """Loss-heavy results below the borderline window do not use the policy path."""
    f = _features(
        stage="screening",
        wins=3,
        losses=7,
        ties=0,
        win_rate=0.30,
        median_delta=100.0,
    )
    from dataclasses import replace

    f = replace(f, screening_expand_count=1)
    engine = DecisionEngine(
        ProtocolConfig(
            gates={
                "screening": {
                    "win_rate_min": 0.55,
                    "expanded_borderline_advance": {
                        "enabled": True,
                        "win_rate_window": 0.05,
                    },
                },
            },
        )
    )

    out = engine.decide(f)

    assert out.stage_decision == Decision.CONTINUE_EXPLORE
    assert "SCREENING_FAIL_WIN_RATE" in out.reason_codes
    assert "SCREENING_EXPAND_EXHAUSTED_BORDERLINE_POLICY_PASS" not in out.reason_codes


def test_decision_screening_high_win_negative_effect_does_not_queue_validation():
    """wr >= threshold but md < 0 stays in exploration by default."""
    f = _features(stage="screening", win_rate=0.7, median_delta=-1000.0)
    out = _engine.decide(f)
    assert out.decision == Decision.CONTINUE_EXPLORE
    assert "SCREENING_INCONCLUSIVE_HIGH_WIN_NEGATIVE_EFFECT" in out.reason_codes
    assert all("PASS" not in reason for reason in out.reason_codes)


def test_decision_screening_high_win_negative_effect_ignores_screening_expand_count():
    """The high-win negative-effect decision is not an expand retry path."""
    from scion.core.models import DecisionFeatures
    f = DecisionFeatures(
        branch_id=str(uuid.uuid4()),
        hypothesis_action="modify",
        stage="screening",
        contract_passed=True, verification_passed=True, canary_passed=True,
        n_cases=10, win_rate=0.7, median_delta=-1500.0,
        ci_low=None, ci_high=None,
        stale=False, recent_retry_count=0, recent_failure_codes=(),
        budget_remaining_ratio=1.0, screening_expand_count=1,
    )
    out = _engine.decide(f)
    assert out.decision == Decision.CONTINUE_EXPLORE
    assert "SCREENING_INCONCLUSIVE_HIGH_WIN_NEGATIVE_EFFECT" in out.reason_codes
    assert all("PASS" not in reason for reason in out.reason_codes)


def test_decision_screening_high_win_negative_effect_ignores_validation_expand_count():
    """Validation expand history cannot promote a negative-effect screening result."""
    from scion.core.models import DecisionFeatures
    f = DecisionFeatures(
        branch_id=str(uuid.uuid4()),
        hypothesis_action="modify",
        stage="screening",
        contract_passed=True, verification_passed=True, canary_passed=True,
        n_cases=10, win_rate=0.7, median_delta=-1500.0,
        ci_low=None, ci_high=None,
        stale=False, recent_retry_count=0, recent_failure_codes=(),
        budget_remaining_ratio=1.0,
        screening_expand_count=0, validation_expand_count=1,
    )
    out = _engine.decide(f)
    assert out.decision == Decision.CONTINUE_EXPLORE
    assert "SCREENING_INCONCLUSIVE_HIGH_WIN_NEGATIVE_EFFECT" in out.reason_codes
    assert all("PASS" not in reason for reason in out.reason_codes)
