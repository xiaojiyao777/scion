"""Sprint H2 unit tests: FailureRouter stateful upgrade, CampaignManager counters,
StagnationDetector infra_loop, tiered evaluation routing, LLM context injection."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest

from scion.core.models import (
    Branch, BranchState, FailureEvent, HypothesisProposal, StepRecord,
)
from scion.core.stagnation import StagnationDetector
from scion.failure.router import EscalationConfig, FailureAction, FailureRouter, RetryConfig
from scion.proposal.context_manager import ContextManager, _build_failure_pattern_warning


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_branch(
    branch_id: str = "b1",
    retry_count: int = 0,
    state: BranchState = BranchState.EXPLORE,
) -> Branch:
    return Branch(
        branch_id=branch_id,
        state=state,
        base_champion_id=1,
        base_champion_hash="abc",
        retry_count=retry_count,
    )


def _light_failure(category: str = "contract") -> FailureEvent:
    return FailureEvent(category=category, detail="test")


def _heavy_failure(category: str = "verification_heavy") -> FailureEvent:
    return FailureEvent(category=category, detail="test")


# ---------------------------------------------------------------------------
# T2: FailureRouter stateful upgrade
# ---------------------------------------------------------------------------

class TestFailureRouterStateful:
    def test_default_no_streak_normal_routing(self):
        """Without streak, router behaves as before (backward compat)."""
        router = FailureRouter()
        branch = _make_branch()
        action = router.route(_light_failure("contract"), branch)
        assert action.action == "retry_llm"
        assert action.escalation_level == 0

    def test_light_failure_streak_below_threshold_normal(self):
        """Light failure with streak=2 (< 3) still routes normally."""
        router = FailureRouter()
        branch = _make_branch()
        action = router.route(_light_failure("contract"), branch, streak=2)
        assert action.action == "retry_llm"

    def test_light_failure_streak_at_threshold_infra_suspected(self):
        """Light failure streak >= 3 → infra_suspected."""
        router = FailureRouter()
        branch = _make_branch()
        action = router.route(_light_failure("contract"), branch, streak=3)
        assert action.action == "infra_suspected"
        assert action.consumes_budget is False
        assert action.escalation_level == 2

    def test_verification_light_streak_at_threshold(self):
        """verification_light streak >= 3 → infra_suspected."""
        router = FailureRouter()
        branch = _make_branch()
        action = router.route(_light_failure("verification_light"), branch, streak=3)
        assert action.action == "infra_suspected"

    def test_heavy_failure_streak_below_threshold_normal(self):
        """Heavy failure with streak=1 still routes normally."""
        router = FailureRouter()
        branch = _make_branch()
        action = router.route(_heavy_failure("verification_heavy"), branch, streak=1)
        assert action.action == "discard"

    def test_heavy_failure_streak_at_threshold_abandon_fast(self):
        """Heavy failure streak >= 2 → abandon_fast."""
        router = FailureRouter()
        branch = _make_branch()
        action = router.route(_heavy_failure("verification_heavy"), branch, streak=2)
        assert action.action == "abandon_fast"
        assert action.consumes_budget is False
        assert action.writes_hypothesis_memory is True

    def test_evaluation_streak_abandon_fast(self):
        """evaluation streak >= 2 → abandon_fast."""
        router = FailureRouter()
        branch = _make_branch()
        action = router.route(
            FailureEvent(category="evaluation", detail="exp error"),
            branch, streak=2,
        )
        assert action.action == "abandon_fast"

    def test_escalation_level_in_retry_llm(self):
        """retry_llm escalation_level matches min(2, streak)."""
        router = FailureRouter()
        branch = _make_branch()
        for streak, expected_level in [(0, 0), (1, 1), (2, 2)]:
            action = router.route(_light_failure("proposal"), branch, streak=streak)
            assert action.action == "retry_llm"
            assert action.escalation_level == expected_level, (
                f"streak={streak}: expected level {expected_level}, got {action.escalation_level}"
            )

    def test_custom_escalation_thresholds(self):
        """EscalationConfig thresholds are respected."""
        cfg = RetryConfig(escalation=EscalationConfig(
            light_streak_infra_suspected=5,
            heavy_streak_abandon_fast=4,
        ))
        router = FailureRouter(cfg)
        branch = _make_branch()

        # streak=3 should still be normal (threshold is 5)
        action = router.route(_light_failure("contract"), branch, streak=3)
        assert action.action == "retry_llm"

        # streak=5 → infra_suspected
        action = router.route(_light_failure("contract"), branch, streak=5)
        assert action.action == "infra_suspected"

    def test_infra_category_unaffected_by_streak(self):
        """infra category is not light/heavy → never escalates."""
        router = FailureRouter()
        branch = _make_branch()
        action = router.route(
            FailureEvent(category="infra", detail="timeout"),
            branch, streak=10,
        )
        assert action.action == "retry_infra"

    def test_framework_control_timeout_fail_closed_not_infra_suspected(self):
        """APS control timeouts fail closed instead of joining proposal/infra streaks."""
        router = FailureRouter()
        branch = _make_branch()
        action = router.route(
            FailureEvent(
                category="framework_control",
                detail="agentic_proposal:session_timeout: max_wall_time_sec=10",
            ),
            branch,
            streak=10,
        )
        assert action.action == "fail_closed"
        assert action.consumes_budget is False
        assert action.writes_hypothesis_memory is False
        assert action.max_retries_remaining == 0

    def test_backward_compat_no_streak_args(self):
        """Old call signature (no streak/total) still works."""
        router = FailureRouter()
        branch = _make_branch()
        # Should not raise
        action = router.route(FailureEvent(category="proposal", detail="err"), branch)
        assert action.action in ("retry_llm", "discard")


# ---------------------------------------------------------------------------
# T3: StagnationDetector infra_loop
# ---------------------------------------------------------------------------

def _make_step(
    failure_stage: Optional[str] = None,
    failure_detail: Optional[str] = None,
) -> StepRecord:
    hyp = HypothesisProposal(
        hypothesis_text="test",
        change_locus="order_level",
        action="modify",
    )
    return StepRecord(
        round_num=1,
        branch_id="b1",
        hypothesis=hyp,
        patch=None,
        contract_passed=True,
        verification_passed=True,
        protocol_result=None,
        decision=None,
        failure_stage=failure_stage,
        failure_detail=failure_detail,
    )


class TestStagnationDetectorInfraLoop:
    def test_infra_loop_detected_at_threshold(self):
        """Same failure_code streak >= 5 → infra_loop signal."""
        detector = StagnationDetector(window_size=5)
        steps = [_make_step("verification") for _ in range(3)]
        streak = {"verification_heavy": 5}
        signals = detector.check(steps, failure_streak=streak)
        kinds = {s.kind for s in signals}
        assert "infra_loop" in kinds

    def test_infra_loop_not_detected_below_threshold(self):
        """Streak < 5 → no infra_loop signal."""
        detector = StagnationDetector(window_size=5)
        steps = [_make_step() for _ in range(3)]
        streak = {"contract": 4}
        signals = detector.check(steps, failure_streak=streak)
        kinds = {s.kind for s in signals}
        assert "infra_loop" not in kinds

    def test_infra_loop_severity_critical(self):
        """infra_loop is always critical."""
        detector = StagnationDetector(window_size=5)
        steps = [_make_step() for _ in range(3)]
        streak = {"verification_light": 7}
        signals = detector.check(steps, failure_streak=streak)
        infra = [s for s in signals if s.kind == "infra_loop"]
        assert len(infra) == 1
        assert infra[0].severity == "critical"
        assert infra[0].suggested_action == "check_environment"

    def test_no_failure_streak_no_infra_loop(self):
        """Empty failure_streak → no infra_loop."""
        detector = StagnationDetector(window_size=5)
        steps = [_make_step() for _ in range(3)]
        signals = detector.check(steps, failure_streak={})
        kinds = {s.kind for s in signals}
        assert "infra_loop" not in kinds

    def test_no_failure_streak_param_backward_compat(self):
        """check() without failure_streak param still works."""
        detector = StagnationDetector(window_size=5)
        signals = detector.check([])
        assert signals == []

    def test_infra_loop_recommendation_check_environment(self):
        """diagnose() with infra_loop → recommendation=check_environment."""
        detector = StagnationDetector(window_size=5)
        steps = [_make_step() for _ in range(3)]
        streak = {"contract": 5}
        diagnosis = detector.diagnose(5, steps, failure_streak=streak)
        assert diagnosis is not None
        assert diagnosis.recommendation == "check_environment"

    def test_object_model_loop_overrides_generic_infra_loop(self):
        """Repeated code API misuse should not be classified as environment."""
        detector = StagnationDetector(
            window_size=5,
            object_model_loop_markers=(
                "_solution",
                "from_public",
                "solver_algorithm_errors=",
            ),
        )
        detail = (
            "agentic_proposal:code_generation_failed: _Solution.from_public "
            "missing; solver_algorithm_errors=1"
        )
        steps = [
            _make_step("code_generation", detail)
            for _ in range(5)
        ]
        streak = {"agentic_proposal:code_generation_failed": 5}

        signals = detector.check(steps, failure_streak=streak)
        kinds = {signal.kind for signal in signals}
        diagnosis = detector.diagnose(5, steps, failure_streak=streak)

        assert "object_model_loop" in kinds
        assert "infra_loop" not in kinds
        assert diagnosis is not None
        assert diagnosis.recommendation == "inspect_agent_trace"


# ---------------------------------------------------------------------------
# T5: Failure pattern warning in context
# ---------------------------------------------------------------------------

class TestFailurePatternWarning:
    def test_no_streak_empty_warning(self):
        """No streaks → empty warning string."""
        assert _build_failure_pattern_warning({}) == ""

    def test_low_streak_no_warning(self):
        """Streak < 2 → empty warning."""
        assert _build_failure_pattern_warning({"contract": 1}) == ""

    def test_streak_2_produces_warning(self):
        """Streak >= 2 → warning produced."""
        warning = _build_failure_pattern_warning({"contract": 2})
        assert "## Failure Pattern Warning" in warning
        assert "contract" in warning
        assert "2" in warning

    def test_verification_hint_in_warning(self):
        """verification failure → specific hint about interface."""
        warning = _build_failure_pattern_warning({"verification_light": 3})
        assert "verification" in warning.lower()
        assert "interface" in warning.lower() or "operator" in warning.lower()

    def test_build_hypothesis_context_includes_warning(self):
        """build_hypothesis_context passes failure_pattern_warning into result."""
        from scion.core.models import ChampionState
        from scion.config.problem import ProblemSpec, SearchSpace

        ss = SearchSpace(
            editable=["operators/*.py"],
            frozen=["solver.py"],
            import_whitelist=["copy"],
        )
        spec = ProblemSpec(
            name="test",
            root_dir="/tmp",
            canary_case_path="/tmp/c.json",
            operator_categories=["order_level"],
            search_space=ss,
        )
        champ = ChampionState(
            version=1,
            code_snapshot_path="/tmp",
            code_snapshot_hash="abc",
            operator_pool={},
            solver_config_hash="def",
        )
        branch = _make_branch()
        ctx_mgr = ContextManager()

        ctx = ctx_mgr.build_hypothesis_context(
            branch=branch,
            champion=champ,
            problem_spec=spec,
            active_hypotheses=[],
            blacklist=[],
            failure_streak={"verification_heavy": 3},
        )
        assert "failure_pattern_warning" in ctx
        assert "verification_heavy" in ctx["failure_pattern_warning"]

    def test_build_hypothesis_context_no_streak_empty_warning(self):
        """Without failure_streak, failure_pattern_warning is empty."""
        from scion.core.models import ChampionState
        from scion.config.problem import ProblemSpec, SearchSpace

        ss = SearchSpace(
            editable=["operators/*.py"],
            frozen=["solver.py"],
            import_whitelist=["copy"],
        )
        spec = ProblemSpec(
            name="test",
            root_dir="/tmp",
            canary_case_path="/tmp/c.json",
            operator_categories=["order_level"],
            search_space=ss,
        )
        champ = ChampionState(
            version=1,
            code_snapshot_path="/tmp",
            code_snapshot_hash="abc",
            operator_pool={},
            solver_config_hash="def",
        )
        branch = _make_branch()
        ctx_mgr = ContextManager()

        ctx = ctx_mgr.build_hypothesis_context(
            branch=branch,
            champion=champ,
            problem_spec=spec,
            active_hypotheses=[],
            blacklist=[],
        )
        assert ctx.get("failure_pattern_warning", "") == ""


# ---------------------------------------------------------------------------
# T1: Campaign-level failure counters (unit-level, no full CampaignManager)
# ---------------------------------------------------------------------------

class TestFailureCounterLogic:
    """Test counter update/reset logic in isolation (via router behaviour)."""

    def test_streak_counter_increments(self):
        """Streak increments across successive same-category failures."""
        router = FailureRouter(RetryConfig(
            escalation=EscalationConfig(light_streak_infra_suspected=3)
        ))
        branch = _make_branch()

        # Simulate campaign-level streak tracking
        failure_streak: Dict[str, int] = {}

        for i in range(1, 4):
            fcode = "contract"
            failure_streak[fcode] = failure_streak.get(fcode, 0) + 1
            action = router.route(
                FailureEvent(category="contract", detail="err"),
                branch,
                streak=failure_streak[fcode],
            )
            if i < 3:
                assert action.action == "retry_llm", f"at i={i}"
            else:
                assert action.action == "infra_suspected", f"at i={i}"

    def test_streak_reset_on_success(self):
        """After streak reset, router returns to normal routing."""
        router = FailureRouter()
        branch = _make_branch()
        failure_streak: Dict[str, int] = {"contract": 3}

        # Should be infra_suspected
        action = router.route(
            FailureEvent(category="contract", detail=""),
            branch, streak=failure_streak["contract"],
        )
        assert action.action == "infra_suspected"

        # Simulate success → reset
        failure_streak.clear()

        # After reset, normal routing resumes
        action = router.route(
            FailureEvent(category="contract", detail=""),
            branch, streak=failure_streak.get("contract", 0),
        )
        assert action.action == "retry_llm"


# ---------------------------------------------------------------------------
# T4: Tiered evaluation routing (logic tested via mock features)
# ---------------------------------------------------------------------------

class TestTieredEvaluationRouting:
    """Test the win_rate < 0.3 → abandon_fast logic.

    We test it indirectly through the router since the full campaign
    integration is tested via campaign_control_boundaries.
    """

    def test_abandon_fast_threshold(self):
        """abandon_fast triggered at correct threshold."""
        # This tests the router-level abandon_fast for heavy failures
        router = FailureRouter()
        branch = _make_branch()

        # 2 consecutive evaluation failures → abandon_fast
        action = router.route(
            FailureEvent(category="evaluation", detail="crash"),
            branch, streak=2,
        )
        assert action.action == "abandon_fast"

    def test_no_abandon_fast_at_streak_1(self):
        """Single evaluation failure → normal discard, not abandon_fast."""
        router = FailureRouter()
        branch = _make_branch()
        action = router.route(
            FailureEvent(category="evaluation", detail="crash"),
            branch, streak=1,
        )
        assert action.action == "discard"
