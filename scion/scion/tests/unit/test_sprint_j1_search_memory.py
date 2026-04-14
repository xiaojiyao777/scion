"""Sprint J1 unit tests: CampaignSearchMemory."""
from __future__ import annotations

import pytest

from scion.core.models import (
    Decision, EvalStats, ExperimentStage, HypothesisProposal,
    PatchProposal, ProtocolResult, StepRecord,
)
from scion.proposal.search_memory import (
    CampaignSearchMemory, FamilyEntry, _extract_mechanism_label, _make_family_key,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_hypothesis(text: str = "subcategory swap", locus: str = "vehicle_level", action: str = "create_new"):
    return HypothesisProposal(
        hypothesis_text=text,
        change_locus=locus,
        action=action,
    )


def _make_step(
    hyp_text: str = "subcategory swap",
    locus: str = "vehicle_level",
    action: str = "create_new",
    win_rate: float = 0.0,
    failure_stage: str | None = None,
    failure_detail: str | None = None,
    decision: Decision | None = None,
    branch_id: str = "b1",
    round_num: int = 1,
) -> StepRecord:
    hyp = _make_hypothesis(hyp_text, locus, action)
    protocol_result = None
    if failure_stage is None:
        protocol_result = ProtocolResult(
            stage=ExperimentStage.SCREENING,
            stats=EvalStats(n_cases=5, wins=int(win_rate * 5), losses=5 - int(win_rate * 5),
                           ties=0, win_rate=win_rate, median_delta=0.0, ci_low=0.0, ci_high=0.0),
            gate_outcome="pass" if win_rate > 0.5 else "fail",
            reason_codes=(),
            exposed_summary="",
            raw_metrics_ref="",
        )
    return StepRecord(
        round_num=round_num,
        branch_id=branch_id,
        hypothesis=hyp,
        patch=None,
        contract_passed=failure_stage is None,
        verification_passed=failure_stage is None,
        protocol_result=protocol_result,
        decision=decision,
        failure_stage=failure_stage,
        failure_detail=failure_detail,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestMechanismLabel:
    def test_subcategory_swap(self):
        assert _extract_mechanism_label("subcategory swap") == "subcategory_consolidation"

    def test_destroy_rebuild(self):
        assert _extract_mechanism_label("destroy and rebuild") == "destroy_rebuild"

    def test_drain(self):
        assert _extract_mechanism_label("drain vehicle orders") == "intra_subcat_repack"

    def test_cost_reduction(self):
        assert _extract_mechanism_label("reduce cost by downsizing") == "cost_reduction"

    def test_generic(self):
        assert _extract_mechanism_label("random perturbation") == "generic"


class TestSearchMemoryUpdate:
    def test_update_on_abandon(self):
        """Abandoned step increments total_attempts and consecutive_fails."""
        sm = CampaignSearchMemory()
        step = _make_step(
            hyp_text="subcategory swap",
            failure_stage="verification",
            failure_detail="V5 failed",
        )
        sm.update(step)
        key = _make_family_key("subcategory_consolidation", "create_new", "vehicle_level")
        assert key in sm.families
        fam = sm.families[key]
        assert fam.total_attempts == 1
        assert fam.consecutive_fails == 1
        assert fam.last_failure_reason == "V5 failed"

    def test_update_on_screening_fail(self):
        """Low win_rate screening result increments consecutive_fails."""
        sm = CampaignSearchMemory()
        step = _make_step(hyp_text="subcategory swap", win_rate=0.20)
        sm.update(step)
        key = _make_family_key("subcategory_consolidation", "create_new", "vehicle_level")
        assert sm.families[key].consecutive_fails == 1
        assert sm.families[key].best_wr == 0.20

    def test_reset_on_promote(self):
        """Promote resets consecutive_fails."""
        sm = CampaignSearchMemory()
        # First: 3 failures
        for _ in range(3):
            sm.update(_make_step(hyp_text="subcategory swap", win_rate=0.10))
        key = _make_family_key("subcategory_consolidation", "create_new", "vehicle_level")
        assert sm.families[key].consecutive_fails == 3

        # Then: a promote
        sm.update(_make_step(
            hyp_text="subcategory swap", win_rate=0.80, decision=Decision.PROMOTE,
        ))
        assert sm.families[key].consecutive_fails == 0
        assert sm.families[key].promoted is True

    def test_exhausted_detection(self):
        """≥5 fails with best_wr<0.35 → is_exhausted=True."""
        sm = CampaignSearchMemory()
        for i in range(6):
            sm.update(_make_step(hyp_text="subcategory swap", win_rate=0.10, round_num=i))
        key = _make_family_key("subcategory_consolidation", "create_new", "vehicle_level")
        assert sm.families[key].is_exhausted is True

    def test_not_exhausted_if_good_wr(self):
        """5+ attempts but best_wr >= 0.35 → not exhausted."""
        sm = CampaignSearchMemory()
        for i in range(4):
            sm.update(_make_step(hyp_text="subcategory swap", win_rate=0.10, round_num=i))
        sm.update(_make_step(hyp_text="subcategory swap", win_rate=0.40, round_num=5))
        sm.update(_make_step(hyp_text="subcategory swap", win_rate=0.10, round_num=6))
        key = _make_family_key("subcategory_consolidation", "create_new", "vehicle_level")
        assert sm.families[key].is_exhausted is False
        assert sm.families[key].best_wr == 0.40


class TestSearchMemoryRender:
    def test_render_empty(self):
        sm = CampaignSearchMemory()
        assert sm.render() == ""

    def test_render_with_evolution(self):
        sm = CampaignSearchMemory()
        sm.record_champion_promotion("v1 → v2 (R3)", 2)
        rendered = sm.render()
        assert "Champion 演化" in rendered
        assert "v1 → v2" in rendered

    def test_render_within_budget(self):
        sm = CampaignSearchMemory()
        sm.record_champion_promotion("v1 → v2 (R3)", 2)
        for i in range(6):
            sm.update(_make_step(hyp_text="subcategory swap", win_rate=0.10, round_num=i))
        rendered = sm.render(available_tokens=10000)
        assert len(rendered) // 4 <= 10000

    def test_render_eviction(self):
        """Very small budget drops low-priority sections."""
        sm = CampaignSearchMemory()
        sm.record_champion_promotion("v1 → v2", 2)
        for i in range(6):
            sm.update(_make_step(hyp_text="subcategory swap", win_rate=0.10, round_num=i))
        # Very tight budget should still include evolution
        rendered = sm.render(available_tokens=50)
        assert "Champion" in rendered or "AVOID" in rendered

    def test_coverage_gaps_computed(self):
        """Heavy exploration of one combo shows '过度探索'."""
        sm = CampaignSearchMemory()
        for i in range(20):
            sm.update(_make_step(
                hyp_text="subcategory swap", locus="vehicle_level", action="create_new",
                win_rate=0.10, round_num=i,
            ))
        rendered = sm.render()
        assert "过度探索" in rendered

    def test_exhausted_in_avoid_list(self):
        """Exhausted families appear in AVOID section."""
        sm = CampaignSearchMemory()
        for i in range(6):
            sm.update(_make_step(hyp_text="subcategory swap", win_rate=0.10, round_num=i))
        rendered = sm.render()
        assert "AVOID" in rendered
        assert "subcategory_consolidation" in rendered


class TestSearchMemoryPromisingFamilies:
    def test_promising_detected(self):
        sm = CampaignSearchMemory()
        sm.update(_make_step(hyp_text="drain vehicle", win_rate=0.30))
        promising = sm.promising_families
        assert len(promising) >= 1
        assert promising[0].best_wr == 0.30
