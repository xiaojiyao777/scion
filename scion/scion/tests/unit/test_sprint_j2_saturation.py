"""Sprint J2 unit tests: ChampionSaturationAnalyzer."""
from __future__ import annotations

import pytest

from scion.proposal.saturation import (
    ChampionSaturationAnalyzer,
    SaturationSignal,
    render_saturation_signals,
    extract_champion_metrics_from_step,
    extract_candidate_metrics_from_step,
)
from scion.core.models import (
    EvalStats, ExperimentStage, HypothesisProposal,
    ObjectiveBreakdown, PairwiseCaseFeedback, ProtocolResult, StepRecord,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_analyzer(splits: float = 10.0, cost: float = 50000.0):
    return ChampionSaturationAnalyzer({"subcategory_splits": splits, "total_cost": cost})


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSaturationAnalyzer:
    def test_baseline_computed_once(self):
        """Analyzer stores baseline at init, doesn't recompute."""
        a = _make_analyzer(splits=10.0, cost=50000.0)
        assert a._baseline == {"subcategory_splits": 10.0, "total_cost": 50000.0}

    def test_saturation_level_high(self):
        """82% improvement → high saturation."""
        a = _make_analyzer(splits=10.0, cost=50000.0)
        signals = a.analyze({"subcategory_splits": 1.8, "total_cost": 44000.0})
        splits_signal = [s for s in signals if s.objective == "subcategory_splits"][0]
        assert splits_signal.saturation_level == "high"
        assert splits_signal.improvement_ratio == pytest.approx(0.82, abs=0.01)

    def test_saturation_level_low(self):
        """12% improvement → low saturation."""
        a = _make_analyzer(splits=10.0, cost=50000.0)
        signals = a.analyze({"subcategory_splits": 1.8, "total_cost": 44000.0})
        cost_signal = [s for s in signals if s.objective == "total_cost"][0]
        assert cost_signal.saturation_level == "low"
        assert cost_signal.improvement_ratio == pytest.approx(0.12, abs=0.01)

    def test_saturation_level_medium(self):
        """50% improvement → medium saturation."""
        a = _make_analyzer(splits=10.0, cost=50000.0)
        signals = a.analyze({"subcategory_splits": 5.0, "total_cost": 25000.0})
        splits_signal = [s for s in signals if s.objective == "subcategory_splits"][0]
        assert splits_signal.saturation_level == "medium"
        cost_signal = [s for s in signals if s.objective == "total_cost"][0]
        assert cost_signal.saturation_level == "medium"

    def test_no_negative_ratio(self):
        """Regression (current worse than baseline) is clamped to 0."""
        a = _make_analyzer(splits=10.0)
        signals = a.analyze({"subcategory_splits": 15.0})
        splits_signal = [s for s in signals if s.objective == "subcategory_splits"][0]
        assert splits_signal.improvement_ratio == 0.0
        assert splits_signal.saturation_level == "low"

    def test_missing_metric_skipped(self):
        """Missing metric in current_metrics is skipped."""
        a = _make_analyzer(splits=10.0, cost=50000.0)
        signals = a.analyze({"subcategory_splits": 2.0})
        assert len(signals) == 1
        assert signals[0].objective == "subcategory_splits"


class TestSaturationRender:
    def test_render_empty(self):
        assert render_saturation_signals([]) == ""

    def test_render_contains_suggestion(self):
        """When high+low, suggestion to explore low-saturation direction."""
        signals = [
            SaturationSignal("subcategory_splits", 0.82, "high", "接近局部最优"),
            SaturationSignal("total_cost", 0.12, "low", "仍有较大空间"),
        ]
        rendered = render_saturation_signals(signals)
        assert "建议探索" in rendered
        assert "total_cost" in rendered

    def test_render_no_suggestion_when_all_same(self):
        """No suggestion when all at same level."""
        signals = [
            SaturationSignal("subcategory_splits", 0.50, "medium", "有一定改进空间"),
            SaturationSignal("total_cost", 0.50, "medium", "有一定改进空间"),
        ]
        rendered = render_saturation_signals(signals)
        assert "建议探索" not in rendered


class TestMetricExtraction:
    def test_extract_champion_metrics(self):
        """Extract champion metrics from pair feedback."""
        from scion.problem.objectives import ObjectiveComparison, MetricComparison
        oc = ObjectiveComparison(
            outcome="win", decisive_metric="subcategory_splits", scalar_delta=2000.0,
            metrics=(
                MetricComparison(name="subcategory_splits", candidate_value=3.0, champion_value=5.0,
                                 signed_delta=2.0, relation="candidate", decisive=True),
                MetricComparison(name="total_cost", candidate_value=28000.0, champion_value=30000.0,
                                 signed_delta=2000.0, relation="candidate"),
            ),
        )
        pf = PairwiseCaseFeedback(
            case_id="c1", seed=42, comparison="win", delta=2000.0,
            objective_comparison=oc,
        )
        step = StepRecord(
            round_num=1, branch_id="b1",
            hypothesis=HypothesisProposal(hypothesis_text="test", change_locus="vehicle_level", action="create_new"),
            patch=None, contract_passed=True, verification_passed=True,
            protocol_result=ProtocolResult(
                stage=ExperimentStage.SCREENING,
                stats=EvalStats(n_cases=1, wins=1, losses=0, ties=0, win_rate=1.0,
                               median_delta=0.0, ci_low=0.0, ci_high=0.0),
                gate_outcome="pass", reason_codes=(), exposed_summary="", raw_metrics_ref="",
                pair_feedback=(pf,),
            ),
            decision=None, failure_stage=None, failure_detail=None,
        )
        metrics = extract_champion_metrics_from_step(step)
        assert metrics is not None
        assert metrics["subcategory_splits"] == 5.0
        assert metrics["total_cost"] == 30000.0

    def test_extract_returns_none_without_feedback(self):
        step = StepRecord(
            round_num=1, branch_id="b1",
            hypothesis=HypothesisProposal(hypothesis_text="test", change_locus="vehicle_level", action="create_new"),
            patch=None, contract_passed=True, verification_passed=True,
            protocol_result=None, decision=None, failure_stage=None, failure_detail=None,
        )
        assert extract_champion_metrics_from_step(step) is None
