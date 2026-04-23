"""Sprint G2: Protocol Correctness tests.

Verifies:
- stats.n_cases is case count, not pair count
- case-level majority vote aggregation
- bootstrap CI uses case-level deltas
- canary uses independent canary split + canary seeds (not screening)
- expand increases case count, seed set unchanged
- screening respects action-specific case counts
- validation/frozen select configured case counts
- validation/frozen expose aggregate only (no per-case feedback)
"""
from __future__ import annotations

import os
from typing import List
from unittest.mock import MagicMock

import pytest

from scion.config.problem import ProtocolConfig, SplitManifest, SeedLedgerConfig
from scion.config.protocol_config import ScreeningConfig, ValidationConfig, FrozenConfig
from scion.core.models import (
    ExperimentStage, EvalStats, RunResult, SolverOutput, ObjectiveBreakdown,
    PairwiseCaseFeedback,
)
from scion.protocol.stats import compute_eval_stats, bootstrap_ci
from scion.protocol.experiment import (
    ExperimentProtocol, SplitManager, SeedLedger, _aggregate_pairs_to_case_level,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def minimal_config():
    """Protocol config with small case/seed counts for easy assertion."""
    return ProtocolConfig(
        version="test",
        screening=ScreeningConfig(
            n_cases_modify=3,
            n_cases_create=5,
            n_seeds=2,
            expand_to_modify=6,
            expand_to_create=8,
        ),
        validation=ValidationConfig(n_cases=4, n_seeds=2, expand_to=7),
        frozen=FrozenConfig(n_cases=3, n_seeds=2, max_uses_per_campaign=3),
    )


@pytest.fixture
def minimal_manifest():
    """Manifest with 8 screening, 7 validation, 3 frozen, 2 canary cases."""
    return SplitManifest(
        version="test",
        screening=[f"s{i}" for i in range(1, 9)],   # s1..s8
        validation=[f"v{i}" for i in range(1, 8)],  # v1..v7
        frozen=[f"f{i}" for i in range(1, 4)],      # f1..f3
        canary=["c1", "c2"],
    )


@pytest.fixture
def minimal_ledger():
    """Seed ledger with 2 screening seeds, 2 validation, 2 frozen, 1 canary."""
    return SeedLedgerConfig(
        version="test",
        screening=[10, 20],
        validation=[30, 40],
        frozen=[50, 60],
        canary=[99],
    )


def _win_result(splits=1, cost=900, feasible=True) -> RunResult:
    """Runner result for 'candidate is better' (fewer splits, lower cost)."""
    return RunResult(
        success=True, exit_code=0, stdout="", stderr="", elapsed_ms=10,
        output=SolverOutput(
            vehicles={}, assignment={},
            objective={"subcategory_splits": splits, "total_cost": cost},
            feasible=feasible,
        ),
    )


def _loss_result(splits=3, cost=1500, feasible=True) -> RunResult:
    """Runner result for 'candidate is worse' (more splits, higher cost)."""
    return RunResult(
        success=True, exit_code=0, stdout="", stderr="", elapsed_ms=10,
        output=SolverOutput(
            vehicles={}, assignment={},
            objective={"subcategory_splits": splits, "total_cost": cost},
            feasible=feasible,
        ),
    )


def _champ_result() -> RunResult:
    """Neutral champion result."""
    return RunResult(
        success=True, exit_code=0, stdout="", stderr="", elapsed_ms=10,
        output=SolverOutput(
            vehicles={}, assignment={},
            objective={"subcategory_splits": 2, "total_cost": 1000},
            feasible=True,
        ),
    )


def _make_pair_fb(case_id: str, seed: int, comparison: str, delta: float) -> PairwiseCaseFeedback:
    from scion.problem.objectives import ObjectiveComparison, MetricComparison
    oc = ObjectiveComparison(
        outcome=comparison, decisive_metric="subcategory_splits",
        scalar_delta=delta,
        metrics=(
            MetricComparison(name="subcategory_splits", candidate_value=1, champion_value=2,
                             signed_delta=1.0, relation="candidate", decisive=True),
            MetricComparison(name="total_cost", candidate_value=900.0, champion_value=1000.0,
                             signed_delta=100.0, relation="candidate"),
        ),
    )
    return PairwiseCaseFeedback(
        case_id=case_id, seed=seed,
        comparison=comparison, delta=delta,
        objective_comparison=oc,
        case_features={},
    )


def _make_proto(runner, config, manifest, ledger, tmp_path) -> ExperimentProtocol:
    return ExperimentProtocol(
        protocol_config=config,
        split_manager=SplitManager(manifest),
        seed_ledger=SeedLedger(ledger),
        runner=runner,
        time_limit_sec=10,
        metrics_dir=str(tmp_path / "metrics"),
    )


# ---------------------------------------------------------------------------
# T2: Case-level statistical unit
# ---------------------------------------------------------------------------

def test_stats_use_case_as_primary_unit():
    """n_cases equals the case count, not the pair count.

    3 cases × 2 seeds = 6 pairs → but stats.n_cases must be 3.
    """
    # These are case-level comparisons (post-aggregation)
    comparisons = ["win", "win", "loss"]
    deltas = [10.0, 5.0, -3.0]
    stats = compute_eval_stats(comparisons, deltas)
    assert stats.n_cases == 3, f"Expected n_cases=3 (case count), got {stats.n_cases}"
    assert stats.wins == 2
    assert stats.losses == 1


def test_case_level_majority_vote_aggregation():
    """Each case is aggregated across seeds via majority vote."""
    pairs = [
        # c1: 2 wins, 1 loss → majority = win
        _make_pair_fb("c1", 10, "win", 10.0),
        _make_pair_fb("c1", 20, "win", 8.0),
        _make_pair_fb("c1", 30, "loss", -2.0),
        # c2: 0 wins, 2 losses → majority = loss
        _make_pair_fb("c2", 10, "loss", -5.0),
        _make_pair_fb("c2", 20, "loss", -3.0),
        # c3: 1 win, 1 loss, 1 tie → no majority, defaults to tie
        _make_pair_fb("c3", 10, "win", 4.0),
        _make_pair_fb("c3", 20, "loss", -4.0),
        _make_pair_fb("c3", 30, "tie", 0.0),
    ]
    result = _aggregate_pairs_to_case_level(pairs)
    by_case = {r.case_id: r for r in result}

    assert by_case["c1"].comparison == "win"
    assert by_case["c2"].comparison == "loss"
    # c3: wins=1, losses=1, ties=1 — no majority, should be "tie"
    assert by_case["c3"].comparison == "tie"


def test_bootstrap_ci_on_case_level_deltas():
    """Bootstrap CI is computed from case-level delta list, not pair-level."""
    # 4 case-level deltas, all positive
    case_deltas = [10.0, 8.0, 5.0, 3.0]
    ci_low, ci_high = bootstrap_ci(case_deltas)
    assert ci_low > 0, f"All case deltas positive → ci_low must be > 0, got {ci_low}"
    assert ci_high > ci_low


# ---------------------------------------------------------------------------
# T3: Canary uses independent split and seeds
# ---------------------------------------------------------------------------

def test_canary_uses_canary_split_and_canary_seeds(
    minimal_config, minimal_manifest, minimal_ledger, tmp_path
):
    """run_canary() uses cases from manifest.canary, seeds from ledger.canary."""
    runner = MagicMock()
    runner.run_solver.return_value = _win_result()

    proto = _make_proto(runner, minimal_config, minimal_manifest, minimal_ledger, tmp_path)
    result = proto.run_canary("/cand", "/champ")

    assert result.passed
    called_instances = {
        call.kwargs["instance_path"] for call in runner.run_solver.call_args_list
    }
    # Canary cases are c1, c2
    assert "c1" in called_instances
    assert "c2" in called_instances
    # Screening cases (s1..s8) must NOT be used
    screening_cases = set(minimal_manifest.screening)
    assert called_instances.isdisjoint(screening_cases), (
        f"Canary must not use screening cases! Used: {called_instances & screening_cases}"
    )
    # Canary seed 99 must be used
    called_seeds = {call.kwargs["seed"] for call in runner.run_solver.call_args_list}
    assert 99 in called_seeds


def test_canary_does_not_use_screening_cases(
    minimal_config, minimal_manifest, minimal_ledger, tmp_path
):
    """Canary cases are disjoint from screening cases."""
    runner = MagicMock()
    runner.run_solver.return_value = _win_result()

    proto = _make_proto(runner, minimal_config, minimal_manifest, minimal_ledger, tmp_path)
    proto.run_canary("/cand", "/champ")

    called_instances = {
        call.kwargs["instance_path"] for call in runner.run_solver.call_args_list
    }
    assert called_instances.isdisjoint(set(minimal_manifest.screening))
    assert called_instances.isdisjoint(set(minimal_manifest.validation))


def test_canary_raises_if_not_configured(
    minimal_config, tmp_path
):
    """run_canary() raises ValueError when canary split/seeds are empty."""
    empty_manifest = SplitManifest(
        version="test",
        screening=["s1"],
        validation=["v1"],
        frozen=["f1"],
        canary=[],  # Empty!
    )
    ledger = SeedLedgerConfig(
        version="test",
        screening=[1], validation=[2], frozen=[3], canary=[99],
    )
    runner = MagicMock()
    proto = _make_proto(runner, minimal_config, empty_manifest, ledger, tmp_path)
    with pytest.raises(ValueError, match="canary"):
        proto.run_canary("/cand", "/champ")


# ---------------------------------------------------------------------------
# T4: expand increases cases, NOT seeds
# ---------------------------------------------------------------------------

def test_expand_increases_cases_not_seeds(
    minimal_config, minimal_manifest, minimal_ledger, tmp_path
):
    """expand=True adds more cases; seed set is unchanged between runs."""
    runner = MagicMock()
    runner.run_solver.return_value = _win_result()

    proto = _make_proto(runner, minimal_config, minimal_manifest, minimal_ledger, tmp_path)

    # Run without expand (n_cases_modify=3)
    runner.run_solver.reset_mock()
    proto.run_experiment(
        ExperimentStage.SCREENING, "/cand", "/champ", "modify", expand=False
    )
    no_expand_instances = {
        call.kwargs["instance_path"] for call in runner.run_solver.call_args_list
    }
    no_expand_seeds = {
        call.kwargs["seed"] for call in runner.run_solver.call_args_list
    }

    # Run with expand (expand_to_modify=6)
    runner.run_solver.reset_mock()
    proto.run_experiment(
        ExperimentStage.SCREENING, "/cand", "/champ", "modify", expand=True, expand_round=1
    )
    expand_instances = {
        call.kwargs["instance_path"] for call in runner.run_solver.call_args_list
    }
    expand_seeds = {
        call.kwargs["seed"] for call in runner.run_solver.call_args_list
    }

    assert len(expand_instances) > len(no_expand_instances), (
        "expand must increase case count"
    )
    assert expand_seeds == no_expand_seeds, (
        f"expand must NOT change seed set: {expand_seeds} != {no_expand_seeds}"
    )


def test_screening_expand_respects_action_specific_limits(
    minimal_config, minimal_manifest, minimal_ledger, tmp_path
):
    """modify uses expand_to_modify, create uses expand_to_create."""
    runner = MagicMock()
    runner.run_solver.return_value = _win_result()
    proto = _make_proto(runner, minimal_config, minimal_manifest, minimal_ledger, tmp_path)

    # Expand for modify: n_cases_modify=3 → expand_to_modify=6
    runner.run_solver.reset_mock()
    proto.run_experiment(
        ExperimentStage.SCREENING, "/cand", "/champ", "modify", expand=True, expand_round=1
    )
    # Each unique instance_path + workdir pair (cand and champ call same instances)
    modify_instances = {
        call.kwargs["instance_path"] for call in runner.run_solver.call_args_list
    }
    n_modify = len(modify_instances)

    # Expand for create: n_cases_create=5 → expand_to_create=8
    runner.run_solver.reset_mock()
    proto.run_experiment(
        ExperimentStage.SCREENING, "/cand", "/champ", "create_new", expand=True, expand_round=1
    )
    create_instances = {
        call.kwargs["instance_path"] for call in runner.run_solver.call_args_list
    }
    n_create = len(create_instances)

    # expand_to_create (8) > expand_to_modify (6)
    assert n_create >= n_modify, (
        f"create expand_to ({n_create}) should be >= modify expand_to ({n_modify})"
    )
    # Both must be more than their non-expand counterparts
    assert n_modify > minimal_config.screening.n_cases_modify  # 6 > 3
    assert n_create > minimal_config.screening.n_cases_create  # 8 > 5


# ---------------------------------------------------------------------------
# T5: screening/validation/frozen select case counts from config
# ---------------------------------------------------------------------------

def test_screening_selects_modify_case_count(
    minimal_config, minimal_manifest, minimal_ledger, tmp_path
):
    """modify/remove operations use n_cases_modify cases."""
    runner = MagicMock()
    runner.run_solver.return_value = _win_result()
    proto = _make_proto(runner, minimal_config, minimal_manifest, minimal_ledger, tmp_path)

    result = proto.run_experiment(
        ExperimentStage.SCREENING, "/cand", "/champ", "modify"
    )
    expected = min(
        minimal_config.screening.n_cases_modify, len(minimal_manifest.screening)
    )
    assert result.stats.n_cases == expected, (
        f"screening modify: expected n_cases={expected}, got {result.stats.n_cases}"
    )


def test_screening_selects_create_case_count(
    minimal_config, minimal_manifest, minimal_ledger, tmp_path
):
    """create_new operations use n_cases_create cases."""
    runner = MagicMock()
    runner.run_solver.return_value = _win_result()
    proto = _make_proto(runner, minimal_config, minimal_manifest, minimal_ledger, tmp_path)

    result = proto.run_experiment(
        ExperimentStage.SCREENING, "/cand", "/champ", "create_new"
    )
    expected = min(
        minimal_config.screening.n_cases_create, len(minimal_manifest.screening)
    )
    assert result.stats.n_cases == expected, (
        f"screening create: expected n_cases={expected}, got {result.stats.n_cases}"
    )
    # create should use more cases than modify (n_cases_create=5 > n_cases_modify=3)
    assert result.stats.n_cases >= minimal_config.screening.n_cases_modify


def test_validation_selects_configured_case_count(
    minimal_config, minimal_manifest, minimal_ledger, tmp_path
):
    """validation uses n_cases cases (not all validation split cases)."""
    runner = MagicMock()
    runner.run_solver.return_value = _win_result()
    proto = _make_proto(runner, minimal_config, minimal_manifest, minimal_ledger, tmp_path)

    result = proto.run_experiment(
        ExperimentStage.VALIDATION, "/cand", "/champ", "modify"
    )
    expected = min(
        minimal_config.validation.n_cases, len(minimal_manifest.validation)
    )
    assert result.stats.n_cases == expected, (
        f"validation: expected n_cases={expected}, got {result.stats.n_cases}"
    )
    # Manifest has 7 validation cases; config says n_cases=4 → must use 4
    assert result.stats.n_cases == minimal_config.validation.n_cases


def test_frozen_selects_configured_case_count(
    minimal_config, minimal_manifest, minimal_ledger, tmp_path
):
    """frozen uses n_cases cases (not all frozen split cases)."""
    runner = MagicMock()
    runner.run_solver.return_value = _win_result()
    proto = _make_proto(runner, minimal_config, minimal_manifest, minimal_ledger, tmp_path)

    result = proto.run_experiment(
        ExperimentStage.FROZEN, "/cand", "/champ", "modify"
    )
    expected = min(
        minimal_config.frozen.n_cases, len(minimal_manifest.frozen)
    )
    assert result.stats.n_cases == expected, (
        f"frozen: expected n_cases={expected}, got {result.stats.n_cases}"
    )
    # Manifest has 3 frozen cases; config says n_cases=3 → use 3
    assert result.stats.n_cases == minimal_config.frozen.n_cases


# ---------------------------------------------------------------------------
# Exposure control: validation/frozen expose aggregate only
# ---------------------------------------------------------------------------

def test_validation_exposes_aggregate_only(
    minimal_config, minimal_manifest, minimal_ledger, tmp_path
):
    """Validation result does not contain per-case or per-pair feedback."""
    runner = MagicMock()
    runner.run_solver.return_value = _win_result()
    proto = _make_proto(runner, minimal_config, minimal_manifest, minimal_ledger, tmp_path)

    result = proto.run_experiment(
        ExperimentStage.VALIDATION, "/cand", "/champ", "modify"
    )
    assert result.pair_feedback == (), "validation must not expose per-pair feedback"
    assert result.case_feedback == (), "validation must not expose per-case feedback"
    assert result.pattern_summary is None, "validation must not expose pattern summary"


def test_frozen_exposes_aggregate_only(
    minimal_config, minimal_manifest, minimal_ledger, tmp_path
):
    """Frozen result does not contain per-case or per-pair feedback."""
    runner = MagicMock()
    runner.run_solver.return_value = _win_result()
    proto = _make_proto(runner, minimal_config, minimal_manifest, minimal_ledger, tmp_path)

    result = proto.run_experiment(
        ExperimentStage.FROZEN, "/cand", "/champ", "modify"
    )
    assert result.pair_feedback == (), "frozen must not expose per-pair feedback"
    assert result.case_feedback == (), "frozen must not expose per-case feedback"
    assert result.pattern_summary is None, "frozen must not expose pattern summary"
