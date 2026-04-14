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
    def test_low_baseline_splits_sets_at_absolute_minimum(self):
        """baseline_splits=0.2 (<1.0) → at_absolute_minimum=True, level=high."""
        analyzer = ChampionSaturationAnalyzer(
            {"subcategory_splits": 0.2, "total_cost": 50000.0}
        )
        signals = analyzer.analyze({"subcategory_splits": 0.2, "total_cost": 49000.0})
        splits_sig = next(s for s in signals if s.objective == "subcategory_splits")
        assert splits_sig.at_absolute_minimum is True
        assert splits_sig.saturation_level == "high"

    def test_normal_baseline_splits_not_at_minimum(self):
        """baseline_splits=5.0 (>=1.0) → at_absolute_minimum=False, normal calc."""
        analyzer = ChampionSaturationAnalyzer(
            {"subcategory_splits": 5.0, "total_cost": 50000.0}
        )
        signals = analyzer.analyze({"subcategory_splits": 4.0, "total_cost": 49000.0})
        splits_sig = next(s for s in signals if s.objective == "subcategory_splits")
        assert splits_sig.at_absolute_minimum is False
        # 20% improvement → low saturation
        assert splits_sig.saturation_level == "low"

    def test_at_minimum_improvement_ratio_is_zero(self):
        """Absolute minimum signal always has improvement_ratio=0.0."""
        analyzer = ChampionSaturationAnalyzer({"subcategory_splits": 0.5})
        signals = analyzer.analyze({"subcategory_splits": 0.3})
        splits_sig = next(s for s in signals if s.objective == "subcategory_splits")
        assert splits_sig.improvement_ratio == pytest.approx(0.0)


class TestRenderSaturationSignalsMandatoryConstraint:
    def test_at_minimum_generates_mandatory_constraint_text(self):
        """render_saturation_signals with at_absolute_minimum → MANDATORY CONSTRAINT."""
        signals = [
            SaturationSignal(
                objective="subcategory_splits",
                improvement_ratio=0.0,
                saturation_level="high",
                opportunity_hint="已达绝对下界",
                at_absolute_minimum=True,
            )
        ]
        text = render_saturation_signals(signals)
        assert "MANDATORY CONSTRAINT" in text
        assert "split" in text.lower() or "COST" in text

    def test_normal_signal_no_mandatory_constraint(self):
        """render_saturation_signals without at_absolute_minimum → no MANDATORY."""
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


class TestAbsMinConstraintInPrompt:
    def test_abs_min_constraint_injected_into_system_prompt(self):
        """abs_min_constraint field → appears in system blocks."""
        constraint_text = (
            "\n## MANDATORY CONSTRAINT — SPLITS AT MINIMUM\n"
            "Champion baseline splits ≈ 0. Splits CANNOT be reduced further.\n"
            "DO NOT propose subcategory-aware, split-reduction, or consolidation operators.\n"
            "ALL proposals MUST target COST reduction ONLY.\n"
        )
        ctx = _make_context(abs_min_constraint=constraint_text)
        text = _system_text(ctx)
        assert "MANDATORY CONSTRAINT" in text
        assert "COST reduction ONLY" in text

    def test_empty_abs_min_constraint_not_injected(self):
        """Empty abs_min_constraint → no MANDATORY CONSTRAINT in prompt."""
        ctx = _make_context(abs_min_constraint="")
        text = _system_text(ctx)
        assert "MANDATORY CONSTRAINT" not in text
