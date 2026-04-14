"""Sprint J3 unit tests: Prompt plumbing — all context fields injected into LLM prompt."""
from __future__ import annotations

import pytest

from scion.proposal.engine import _split_hypothesis_context, _split_code_context


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_context(**overrides):
    """Build a minimal hypothesis context dict with all expected keys."""
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
        "search_memory": "",
        "saturation_signal": "",
        "weight_opt_feedback": "",
    }
    base.update(overrides)
    return base


def _system_text(context):
    """Extract all system block text from hypothesis context."""
    blocks, _ = _split_hypothesis_context(context)
    return " ".join(b["text"] for b in blocks)


def _user_text(context):
    """Extract user prompt from hypothesis context."""
    _, user = _split_hypothesis_context(context)
    return user


# ---------------------------------------------------------------------------
# Tests: fields appear in system blocks (Block 3)
# ---------------------------------------------------------------------------

class TestExplorationCoverageInPrompt:
    def test_exploration_coverage_injected(self):
        ctx = _make_context(exploration_coverage="Family subcategory_consolidation: 5 attempts")
        text = _system_text(ctx)
        assert "Exploration Coverage" in text
        assert "subcategory_consolidation" in text

    def test_exploration_coverage_absent_when_empty(self):
        ctx = _make_context(exploration_coverage="")
        text = _system_text(ctx)
        assert "Exploration Coverage" not in text


class TestStrategyGuidanceInPrompt:
    def test_strategy_guidance_injected(self):
        ctx = _make_context(strategy_guidance="Switch to cost_reduction")
        text = _system_text(ctx)
        assert "Strategy Guidance" in text
        assert "cost_reduction" in text


class TestChampionBaselinesInPrompt:
    def test_champion_baselines_injected(self):
        ctx = _make_context(champion_baselines="case_001: splits=5")
        text = _system_text(ctx)
        assert "Champion Baseline Hints" in text
        assert "case_001" in text


class TestFailurePatternWarningInPrompt:
    def test_failure_pattern_injected(self):
        ctx = _make_context(failure_pattern_warning="verification_heavy streak=3")
        text = _system_text(ctx)
        assert "Failure Pattern Warning" in text
        assert "verification_heavy" in text


class TestSearchMemoryInPrompt:
    def test_search_memory_injected(self):
        ctx = _make_context(search_memory="## Campaign Search Memory\n### AVOID\nsubcategory_swap")
        text = _system_text(ctx)
        assert "Campaign Search Memory" in text
        assert "subcategory_swap" in text


class TestSaturationSignalInPrompt:
    def test_saturation_signal_injected(self):
        ctx = _make_context(saturation_signal="## Champion 当前状态\nsplits: 82% high")
        text = _system_text(ctx)
        assert "Champion 当前状态" in text


class TestWeightOptFeedbackInPrompt:
    def test_weight_opt_feedback_injected(self):
        ctx = _make_context(weight_opt_feedback="## 当前算子贡献估计\nsubcat_consolidate: 高贡献")
        text = _system_text(ctx)
        assert "当前算子贡献估计" in text


class TestLocusConstraintInPrompt:
    def test_locus_constraint_injected(self):
        ctx = _make_context(locus_constraint="## MANDATORY SEARCH CONSTRAINT\nMust target order_level")
        text = _system_text(ctx)
        assert "MANDATORY SEARCH CONSTRAINT" in text


class TestCodeContextPriorFailure:
    def test_prior_failure_in_user_prompt(self):
        ctx = {
            "problem_summary": "Test",
            "operator_interface_spec": "class Operator",
            "import_whitelist": "random, math",
            "champion_operators_code": "# code",
            "hypothesis_detail": "Add drain operator",
            "target_file_code": "# empty",
            "reference_operators": "",
            "editable_patterns": "operators/*.py",
            "frozen_patterns": "solver.py",
            "prior_code_failure": "SyntaxError line 42",
        }
        blocks, user = _split_code_context(ctx)
        assert "Previous Attempt Failed" in user
        assert "SyntaxError" in user

    def test_no_prior_failure_section_when_empty(self):
        ctx = {
            "problem_summary": "Test",
            "operator_interface_spec": "class Operator",
            "import_whitelist": "random, math",
            "champion_operators_code": "# code",
            "hypothesis_detail": "Add drain operator",
            "target_file_code": "# empty",
            "reference_operators": "",
            "editable_patterns": "operators/*.py",
            "frozen_patterns": "solver.py",
            "prior_code_failure": "",
        }
        blocks, user = _split_code_context(ctx)
        assert "Previous Attempt Failed" not in user
