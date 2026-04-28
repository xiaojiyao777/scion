"""Sprint L unit tests: L1 C10_novelty not infra + L2 splits at-minimum constraint."""
from __future__ import annotations

import uuid

import pytest

from scion.core.models import Branch, BranchState, FailureEvent
from scion.failure.router import FailureRouter, RetryConfig
from scion.proposal.saturation import (
    ChampionSaturationAnalyzer,
    SaturationSignal,
    render_saturation_signals,
)
from scion.proposal.engine import _split_hypothesis_context


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _branch(retry_count: int = 0) -> Branch:
    return Branch(
        branch_id=str(uuid.uuid4()),
        state=BranchState.EXPLORE,
        base_champion_id=0,
        base_champion_hash="hash0",
        retry_count=retry_count,
    )


def _failure(category: str, detail: str = "") -> FailureEvent:
    return FailureEvent(category=category, detail=detail)


_router = FailureRouter(RetryConfig(max_llm_retries=3, max_infra_retries=5))


def _make_context(**overrides):
    base = {
        "problem_summary": "Test problem",
        "operator_categories": "vehicle_level, order_level",
        "champion_operators_code": "# champion code",
        "champion_stats": "v1, 3 operators",
        "experiment_history": "R1: win_rate=0.5",
        "blacklist_summary": "(none)",
        "sibling_summary": "(none)",
        "branch_code": "",
        "branch_direction": "",
        "exploration_coverage": "",
        "strategy_guidance": "",
        "champion_baselines": "",
        "failure_pattern_warning": "",
        "locus_constraint": "",
        "abs_min_constraint": "",
        "objective_guidance": "",
        "search_memory": "",
        "saturation_signal": "",
        "weight_opt_feedback": "",
        "research_log": "",
        "active_hyp_summary": "",
    }
    base.update(overrides)
    return base


def _system_text(ctx):
    blocks, _ = _split_hypothesis_context(ctx)
    return " ".join(b["text"] for b in blocks)


# ===========================================================================
# L1: C10_novelty → search_guidance → retry_llm, no infra streak
# ===========================================================================

class TestC10NoveltyRoutedAsSearchGuidance:
    def test_search_guidance_returns_retry_llm(self):
        """C10_novelty failure (search_guidance category) → action=retry_llm."""
        fa = _router.route(_failure("search_guidance"), _branch())
        assert fa.action == "retry_llm"

    def test_search_guidance_no_budget_consumed(self):
        fa = _router.route(_failure("search_guidance"), _branch())
        assert fa.consumes_budget is False
        assert fa.writes_hypothesis_memory is False

    def test_search_guidance_escalation_level_zero(self):
        """search_guidance always escalation_level=0 regardless of streak."""
        fa = _router.route(_failure("search_guidance"), _branch(), streak=10)
        assert fa.escalation_level == 0

    def test_three_consecutive_c10_no_infra_suspected(self):
        """3 consecutive search_guidance failures must NOT trigger infra_suspected."""
        b = _branch()
        for _ in range(3):
            fa = _router.route(_failure("search_guidance"), b, streak=3)
            assert fa.action != "infra_suspected", (
                "search_guidance must never escalate to infra_suspected"
            )

    def test_contract_failure_still_counts_streak(self):
        """Non-C10 contract failure (C3_schema) at streak≥3 → infra_suspected."""
        b = _branch()
        fa = _router.route(_failure("contract"), b, streak=3)
        assert fa.action == "infra_suspected"

    def test_mixed_c10_and_contract_only_contract_counts(self):
        """search_guidance must not accumulate infra streak; plain contract does."""
        b = _branch()
        # search_guidance at streak=3 should NOT trigger infra
        fa_search = _router.route(_failure("search_guidance"), b, streak=3)
        assert fa_search.action != "infra_suspected"
        # contract at streak=3 SHOULD trigger infra
        fa_contract = _router.route(_failure("contract"), b, streak=3)
        assert fa_contract.action == "infra_suspected"


# ===========================================================================
# L2: splits at-minimum detection
# ===========================================================================

class TestAtAbsoluteMinimumDetection:
    def test_low_baseline_with_lower_bound_sets_at_absolute_minimum(self):
        """baseline_splits=0.2 at lower_bound=0.0 → at_absolute_minimum=True, level=high."""
        analyzer = ChampionSaturationAnalyzer(
            {"subcategory_splits": 0.2, "total_cost": 50000.0},
            lower_bounds={"subcategory_splits": 0.0},
        )
        signals = analyzer.analyze({"subcategory_splits": 0.2, "total_cost": 49000.0})
        splits_sig = next(s for s in signals if s.objective == "subcategory_splits")
        assert splits_sig.at_absolute_minimum is True
        assert splits_sig.saturation_level == "high"

    def test_no_lower_bounds_no_hard_saturation(self):
        """Without lower_bounds, no objective gets at_absolute_minimum=True."""
        analyzer = ChampionSaturationAnalyzer(
            {"subcategory_splits": 0.2, "total_cost": 50000.0}
        )
        signals = analyzer.analyze({"subcategory_splits": 0.2, "total_cost": 49000.0})
        for s in signals:
            assert s.at_absolute_minimum is False

    def test_normal_baseline_splits_not_at_minimum(self):
        """baseline_splits=5.0 (far from lower bound) → at_absolute_minimum=False."""
        analyzer = ChampionSaturationAnalyzer(
            {"subcategory_splits": 5.0, "total_cost": 50000.0},
            lower_bounds={"subcategory_splits": 0.0},
        )
        signals = analyzer.analyze({"subcategory_splits": 4.0, "total_cost": 49000.0})
        splits_sig = next(s for s in signals if s.objective == "subcategory_splits")
        assert splits_sig.at_absolute_minimum is False
        # 20% improvement → low saturation
        assert splits_sig.saturation_level == "low"

    def test_at_minimum_improvement_ratio_is_zero(self):
        """Absolute minimum signal always has improvement_ratio=0.0."""
        analyzer = ChampionSaturationAnalyzer(
            {"subcategory_splits": 0.3},
            lower_bounds={"subcategory_splits": 0.0},
        )
        signals = analyzer.analyze({"subcategory_splits": 0.2})
        splits_sig = next(s for s in signals if s.objective == "subcategory_splits")
        assert splits_sig.improvement_ratio == pytest.approx(0.0)

    def test_generic_lower_bound_any_objective(self):
        """Any objective with lower_bounds triggers hard saturation when baseline at bound."""
        analyzer = ChampionSaturationAnalyzer(
            {"total_cost": 90.3},
            lower_bounds={"total_cost": 90.0},
        )
        signals = analyzer.analyze({"total_cost": 90.0})
        cost_sig = next(s for s in signals if s.objective == "total_cost")
        assert cost_sig.at_absolute_minimum is True
        assert cost_sig.saturation_type == "hard"


class TestRenderSaturationSignalsTendency:
    def test_at_minimum_generates_tendency_text(self):
        """render_saturation_signals with at_absolute_minimum → tendency note, not prohibition."""
        signals = [
            SaturationSignal(
                objective="subcategory_splits",
                improvement_ratio=0.0,
                saturation_level="high",
                opportunity_hint="at theoretical lower bound (0)",
                at_absolute_minimum=True,
            )
        ]
        text = render_saturation_signals(signals)
        assert "strongly preferred" in text
        assert "MANDATORY" not in text
        assert "禁止" not in text

    def test_normal_signal_no_mandatory_constraint(self):
        """render_saturation_signals without at_absolute_minimum → no constraint."""
        signals = [
            SaturationSignal(
                objective="subcategory_splits",
                improvement_ratio=0.5,
                saturation_level="medium",
                opportunity_hint="有一定改进空间",
                at_absolute_minimum=False,
            )
        ]
        text = render_saturation_signals(signals)
        assert "MANDATORY CONSTRAINT" not in text


class TestObjectiveGuidanceInPrompt:
    def test_objective_guidance_injected_into_system_prompt(self):
        """objective_guidance field → appears in system blocks."""
        guidance_text = (
            "\n## Objective Improvement Guidance\n"
            "- splits: at or near its theoretical minimum. "
            "Focusing search effort on other objectives is strongly preferred."
        )
        ctx = _make_context(objective_guidance=guidance_text)
        text = _system_text(ctx)
        assert "Objective Improvement Guidance" in text
        assert "strongly preferred" in text

    def test_empty_objective_guidance_not_injected(self):
        """Empty objective_guidance → no guidance block in prompt."""
        ctx = _make_context(objective_guidance="")
        text = _system_text(ctx)
        assert "Objective Improvement Guidance" not in text
