"""Tests for Sprint 4: CC-inspired context optimization.

Covers:
- StepRecord.verification_detail populated from VerificationResult
- Branch.direction set/cleared by _apply_decision_and_finalize
- _build_experiment_history includes verification_detail and diagnosis block
- build_hypothesis_context includes branch_direction key
- _build_consecutive_failure_diagnosis triggers at 3+ consecutive verification failures
"""
from __future__ import annotations

from typing import Any, List, Optional
from pathlib import Path

import pytest

from scion.core.models import (
    Branch, BranchState, CanaryResult, ChampionState, CheckResult,
    Decision, EvalStats, ExperimentStage, HypothesisProposal,
    HypothesisRecord, ProtocolResult, StepRecord, VerificationResult,
)
from scion.config.problem import ProblemSpec, ProtocolConfig, SplitManifest, SeedLedgerConfig, SearchSpace
from scion.core.campaign import CampaignManager
from scion.core.termination import TerminationConfig
from scion.proposal.context_manager import ContextManager, _build_experiment_history, _build_consecutive_failure_diagnosis, _build_branch_direction_prompt
from scion.proposal.mock_client import MockLLMClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_CODE = (
    "class LocalSearch:\n"
    "    def execute(self, solution, rng):\n"
    "        return solution\n"
)

_VALID_HYPOTHESIS = {
    "hypothesis_text": "Improve local search by trying 2-opt.",
    "change_locus": "local_search",
    "action": "modify",
    "target_file": "operators/local_search.py",
    "predicted_direction": "improve",
    "target_weakness": "slow convergence",
    "expected_effect": "better solutions",
    "suggested_weight": 0.3,
}

_VALID_PATCH = {
    "file_path": "operators/local_search.py",
    "action": "modify",
    "code_content": _VALID_CODE,
    "test_hint": None,
}


def _make_hypothesis(text: str = "some hypothesis", locus: str = "local_search") -> HypothesisProposal:
    return HypothesisProposal(
        hypothesis_text=text,
        change_locus=locus,
        action="modify",
        target_file="operators/local_search.py",
        predicted_direction="improve",
        target_weakness="slow",
        expected_effect="faster",
    )


def _make_step(
    branch_id: str,
    round_num: int,
    failure_stage: Optional[str] = None,
    failure_detail: Optional[str] = None,
    verification_detail: Optional[str] = None,
    win_rate: float = 0.0,
    hypothesis_text: str = "test hypothesis",
) -> StepRecord:
    protocol_result = None
    if failure_stage is None:
        stats = EvalStats(
            n_cases=6, wins=int(win_rate * 6), losses=6 - int(win_rate * 6), ties=0,
            win_rate=win_rate, median_delta=0.01 if win_rate > 0 else 0.0,
            ci_low=0.0, ci_high=0.02,
        )
        protocol_result = ProtocolResult(
            stage=ExperimentStage.SCREENING,
            stats=stats,
            gate_outcome="pass" if win_rate > 0.6 else "continue",
            reason_codes=("TEST",),
            exposed_summary="test",
            raw_metrics_ref="/tmp/test.json",
        )
    return StepRecord(
        round_num=round_num,
        branch_id=branch_id,
        hypothesis=_make_hypothesis(hypothesis_text),
        patch=None,
        contract_passed=True,
        verification_passed=(failure_stage is None),
        protocol_result=protocol_result,
        decision=Decision.CONTINUE_EXPLORE,
        failure_stage=failure_stage,
        failure_detail=failure_detail,
        verification_detail=verification_detail,
    )


def _make_problem_spec(root_dir: str) -> ProblemSpec:
    return ProblemSpec(
        name="test_vrp",
        root_dir=root_dir,
        operator_categories=["local_search"],
        search_space=SearchSpace(
            editable=["operators/*.py"],
            frozen=["solver.py"],
            import_whitelist=["numpy", "random"],
        ),
    )


def _make_champion(code_dir: str) -> ChampionState:
    return ChampionState(
        version=1,
        operator_pool={},
        solver_config_hash="abc123",
        code_snapshot_path=code_dir,
        code_snapshot_hash="deadbeef",
    )


def _make_branch(branch_id: str = "branch-001") -> Branch:
    return Branch(
        branch_id=branch_id,
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="deadbeef",
    )


class AlwaysPassVerificationGate:
    def run(self, workspace, champion_workspace, patch) -> VerificationResult:
        return VerificationResult(passed=True, checks=())


class FailWithDetailVerificationGate:
    """Returns a heavy verification failure with detailed check info."""
    def run(self, workspace, champion_workspace, patch) -> VerificationResult:
        check = CheckResult(
            name="V3_feasibility",
            passed=False,
            severity="heavy",
            detail="infeasible: H7 capacity violation on vehicle V_001",
            elapsed_ms=5,
        )
        return VerificationResult(
            passed=False,
            checks=(check,),
            failure_severity="heavy",
            first_failure="V3_feasibility",
        )


class MockProtocol:
    def __init__(self, win_rate: float = 0.0, gate_outcome: str = "continue") -> None:
        self._win_rate = win_rate
        self._gate_outcome = gate_outcome

    def run_canary(self, candidate_ws, champion_ws) -> CanaryResult:
        return CanaryResult(passed=True, reason=None)

    def run_experiment(self, stage, candidate_ws, champion_ws, hypothesis_action, **kw) -> ProtocolResult:
        stats = EvalStats(
            n_cases=6, wins=int(self._win_rate * 6), losses=6 - int(self._win_rate * 6), ties=0,
            win_rate=self._win_rate, median_delta=0.01 if self._win_rate > 0 else 0.0,
            ci_low=0.0, ci_high=0.02,
        )
        return ProtocolResult(
            stage=stage,
            stats=stats,
            gate_outcome=self._gate_outcome,
            reason_codes=("TEST",),
            exposed_summary="test",
            raw_metrics_ref="/tmp/test.json",
        )


def _campaign(tmp_path: Path, protocol=None, vgate=None) -> CampaignManager:
    code_dir = tmp_path / "champion_code"
    (code_dir / "operators").mkdir(parents=True)
    (code_dir / "operators" / "local_search.py").write_text(_VALID_CODE)

    campaign_dir = str(tmp_path / "campaign")
    spec = _make_problem_spec(str(code_dir))
    champion = _make_champion(str(code_dir))

    return CampaignManager(
        problem_spec=spec,
        protocol_config=ProtocolConfig(
            screening_n=6, screening_win_rate_threshold=0.66,
            validation_n=12, validation_win_rate_threshold=0.66,
            frozen_n=24, min_practical_delta=0.001,
        ),
        split_manifest=SplitManifest(screening=["c1", "c2"], validation=["c3"], frozen=["c4"]),
        seed_ledger=SeedLedgerConfig(screening=[1, 2], validation=[3], frozen=[4]),
        llm_client=MockLLMClient(
            hypothesis_response=_VALID_HYPOTHESIS,
            patch_response=_VALID_PATCH,
        ),
        champion=champion,
        campaign_dir=campaign_dir,
        verification_gate=vgate or AlwaysPassVerificationGate(),
        experiment_protocol=protocol or MockProtocol(),
        termination_config=TerminationConfig(max_experiments=100, stagnation_limit=50),
    )


# ---------------------------------------------------------------------------
# 1. StepRecord.verification_detail populated
# ---------------------------------------------------------------------------

class TestVerificationDetail:
    def test_verification_detail_in_step_record_heavy_failure(self, tmp_path):
        """Verification failure (heavy) should populate verification_detail."""
        cm = _campaign(tmp_path, vgate=FailWithDetailVerificationGate())
        cm.run_one_step()

        ver_steps = [s for s in cm._step_history if s.failure_stage == "verification"]
        assert ver_steps, "Expected at least one verification failure step"
        s = ver_steps[0]
        assert s.verification_detail is not None
        assert "V3_feasibility" in s.verification_detail
        assert "infeasible" in s.verification_detail

    def test_verification_detail_none_on_success(self, tmp_path):
        """Successful step should have verification_detail=None."""
        cm = _campaign(tmp_path, protocol=MockProtocol(win_rate=0.7, gate_outcome="continue"))
        cm.run_one_step()

        success_steps = [s for s in cm._step_history if s.failure_stage is None]
        assert success_steps
        assert all(s.verification_detail is None for s in success_steps)

    def test_build_verification_detail_helper(self):
        """_build_verification_detail from campaign module."""
        from scion.core.campaign import _build_verification_detail
        check = CheckResult(
            name="V3_feasibility", passed=False, severity="heavy",
            detail="infeasible: assignment mismatch", elapsed_ms=1,
        )
        vresult = VerificationResult(
            passed=False, checks=(check,),
            failure_severity="heavy", first_failure="V3_feasibility",
        )
        detail = _build_verification_detail(vresult)
        assert detail is not None
        assert "V3_feasibility" in detail
        assert "infeasible: assignment mismatch" in detail
        assert "heavy" in detail

    def test_build_verification_detail_none_on_pass(self):
        from scion.core.campaign import _build_verification_detail
        vresult = VerificationResult(passed=True, checks=())
        assert _build_verification_detail(vresult) is None


# ---------------------------------------------------------------------------
# 2. Branch.direction management
# ---------------------------------------------------------------------------

class TestBranchDirection:
    def test_direction_set_on_positive_signal(self, tmp_path):
        """First CONTINUE_EXPLORE with win_rate > 0 should set branch.direction.

        Uses win_rate=0.3: triggers CONTINUE_EXPLORE (wr < 0.5 path) with positive signal.
        """
        cm = _campaign(tmp_path, protocol=MockProtocol(win_rate=0.3, gate_outcome="continue"))
        cm.run_one_step()

        branch = cm._branch_ctrl.get_active_branches()[0]
        assert branch.direction is not None
        assert "local_search" in branch.direction  # change_locus
        assert "Improve local search" in branch.direction  # hypothesis_text prefix

    def test_direction_not_set_on_zero_win_rate(self, tmp_path):
        """win_rate == 0 → abandon_fast (T4): branch is abandoned, direction never set."""
        cm = _campaign(tmp_path, protocol=MockProtocol(win_rate=0.0, gate_outcome="continue"))
        cm.run_one_step()

        # T4: win_rate=0.0 < 0.3 → branch is fast-abandoned, not in active_branches
        active = cm._branch_ctrl.get_active_branches()
        assert len(active) == 0 or all(
            b.branch_id != cm._branch_ctrl._branches.get(list(cm._branch_ctrl._branches.keys())[0], None)
            for b in active
        ), "Branch with win_rate=0 should be abandoned"
        # Verify abandoned branch has direction=None
        from scion.core.models import BranchState
        all_branches = list(cm._branch_ctrl._branches.values())
        assert len(all_branches) == 1
        assert all_branches[0].state == BranchState.ABANDONED

    def test_direction_cleared_after_3_consecutive_zero_wins(self, tmp_path):
        """T4: once win_rate drops to 0 (<0.3), branch is fast-abandoned after 1 round."""
        # First round: positive signal (win_rate=0.3 → CONTINUE_EXPLORE) sets direction
        protocol = MockProtocol(win_rate=0.3, gate_outcome="continue")
        cm = _campaign(tmp_path, protocol=protocol)
        cm.run_one_step()

        branch = cm._branch_ctrl.get_active_branches()[0]
        assert branch.direction is not None  # direction set

        # Switch to zero-win: T4 abandons on first round (no need for 3 rounds)
        protocol._win_rate = 0.0
        cm.run_one_step()

        # Branch should be abandoned after the first zero-win round under T4
        from scion.core.models import BranchState
        assert branch.state == BranchState.ABANDONED

    def test_direction_not_cleared_after_only_2_zero_wins(self, tmp_path):
        """After 2 zero-win-rate rounds, branch.direction should be preserved."""
        protocol = MockProtocol(win_rate=0.3, gate_outcome="continue")
        cm = _campaign(tmp_path, protocol=protocol)
        cm.run_one_step()

        branch = cm._branch_ctrl.get_active_branches()[0]
        assert branch.direction is not None

        protocol._win_rate = 0.0
        for _ in range(2):
            cm.run_one_step()

        assert branch.direction is not None


# ---------------------------------------------------------------------------
# 3. _build_experiment_history — verification_detail in history
# ---------------------------------------------------------------------------

class TestExperimentHistoryVerificationDetail:
    def test_verification_detail_shown_in_history(self):
        """If failure_stage == 'verification', verification_detail should appear in history."""
        bid = "branch-abc"
        steps = [
            _make_step(
                bid, 1,
                failure_stage="verification",
                failure_detail="V3_feasibility: assignment mismatch",
                verification_detail="severity=heavy  first_failure=V3_feasibility\n  [V3_feasibility] (heavy) infeasible: H7 capacity violation",
            )
        ]
        history = _build_experiment_history(steps, bid)
        assert "infeasible: H7 capacity violation" in history

    def test_failure_detail_used_when_no_verification_detail(self):
        """If verification_detail is None, fall back to failure_detail."""
        bid = "branch-abc"
        steps = [
            _make_step(
                bid, 1,
                failure_stage="verification",
                failure_detail="V1_syntax: unexpected indent",
                verification_detail=None,
            )
        ]
        history = _build_experiment_history(steps, bid)
        assert "V1_syntax" in history

    def test_non_verification_failure_uses_failure_detail(self):
        """Non-verification failures still show failure_detail."""
        bid = "branch-abc"
        steps = [
            _make_step(
                bid, 1,
                failure_stage="code_generation",
                failure_detail="LLM code generation failed",
                verification_detail=None,
            )
        ]
        history = _build_experiment_history(steps, bid)
        assert "LLM code generation failed" in history


# ---------------------------------------------------------------------------
# 4. _build_consecutive_failure_diagnosis
# ---------------------------------------------------------------------------

class TestConsecutiveFailureDiagnosis:
    def _ver_steps(self, bid: str, n: int, vcode: str = "V3_feasibility") -> List[StepRecord]:
        detail = f"{vcode}: some detail"
        vdetail = f"severity=heavy  first_failure={vcode}\n  [{vcode}] (heavy) some detail"
        return [
            _make_step(bid, i + 1, failure_stage="verification", failure_detail=detail, verification_detail=vdetail)
            for i in range(n)
        ]

    def test_no_diagnosis_below_3(self):
        bid = "b1"
        steps = self._ver_steps(bid, 2)
        diag = _build_consecutive_failure_diagnosis(steps)
        assert diag == ""

    def test_diagnosis_at_exactly_3(self):
        bid = "b1"
        steps = self._ver_steps(bid, 3)
        diag = _build_consecutive_failure_diagnosis(steps)
        assert "Consecutive Failure Diagnosis" in diag
        assert "3" in diag
        assert "V3_feasibility" in diag

    def test_diagnosis_includes_suggestion_for_feasibility(self):
        bid = "b1"
        steps = self._ver_steps(bid, 3, vcode="V3_feasibility")
        diag = _build_consecutive_failure_diagnosis(steps)
        assert "assignment dict" in diag or "HQ40_DG" in diag

    def test_diagnosis_includes_suggestion_for_nondeterminism(self):
        bid = "b1"
        steps = self._ver_steps(bid, 3, vcode="V8_nondeterminism")
        diag = _build_consecutive_failure_diagnosis(steps)
        assert "deep_copy" in diag

    def test_diagnosis_not_injected_when_non_verification_step_breaks_streak(self):
        bid = "b1"
        steps = self._ver_steps(bid, 2)
        # Insert a success step in the middle
        success = _make_step(bid, 10, failure_stage=None, win_rate=0.5)
        steps.append(success)
        steps.extend(self._ver_steps(bid, 2))
        diag = _build_consecutive_failure_diagnosis(steps)
        # Streak broken by success — only 2 at the end, no diagnosis
        assert diag == ""

    def test_diagnosis_at_5_consecutive(self):
        bid = "b1"
        steps = self._ver_steps(bid, 5)
        diag = _build_consecutive_failure_diagnosis(steps)
        assert "5" in diag

    def test_history_includes_diagnosis_block(self):
        """_build_experiment_history should include diagnosis when 3+ ver failures."""
        bid = "b1"
        steps = [
            _make_step(bid, i, failure_stage="verification",
                       failure_detail="V3_feasibility: x",
                       verification_detail="severity=heavy  first_failure=V3_feasibility\n  [V3_feasibility] (heavy) x")
            for i in range(1, 4)
        ]
        history = _build_experiment_history(steps, bid)
        assert "Consecutive Failure Diagnosis" in history


# ---------------------------------------------------------------------------
# 5. build_hypothesis_context includes branch_direction
# ---------------------------------------------------------------------------

class TestBranchDirectionContext:
    def test_no_direction_returns_none_key(self, tmp_path):
        code_dir = tmp_path / "champion_code"
        (code_dir / "operators").mkdir(parents=True)
        (code_dir / "operators" / "local_search.py").write_text(_VALID_CODE)
        spec = _make_problem_spec(str(code_dir))
        champion = _make_champion(str(code_dir))
        branch = _make_branch()

        ctx_mgr = ContextManager()
        ctx = ctx_mgr.build_hypothesis_context(
            branch=branch,
            champion=champion,
            problem_spec=spec,
            active_hypotheses=[],
            blacklist=[],
        )
        assert "branch_direction" in ctx
        assert ctx["branch_direction"] is None

    def test_direction_set_returns_prompt_string(self, tmp_path):
        code_dir = tmp_path / "champion_code"
        (code_dir / "operators").mkdir(parents=True)
        (code_dir / "operators" / "local_search.py").write_text(_VALID_CODE)
        spec = _make_problem_spec(str(code_dir))
        champion = _make_champion(str(code_dir))
        branch = _make_branch()
        branch.direction = "local_search: Improve local search by trying 2-opt."

        ctx_mgr = ContextManager()
        ctx = ctx_mgr.build_hypothesis_context(
            branch=branch,
            champion=champion,
            problem_spec=spec,
            active_hypotheses=[],
            blacklist=[],
        )
        assert ctx["branch_direction"] is not None
        assert "Branch Direction" in ctx["branch_direction"]
        assert "local_search: Improve local search" in ctx["branch_direction"]
        assert "Only switch to a fundamentally different approach" in ctx["branch_direction"]


class TestBuildBranchDirectionPrompt:
    def test_none_when_no_direction(self):
        branch = _make_branch()
        result = _build_branch_direction_prompt(branch)
        assert result is None

    def test_returns_prompt_when_direction_set(self):
        branch = _make_branch()
        branch.direction = "routing: explore 2-opt improvements"
        result = _build_branch_direction_prompt(branch)
        assert result is not None
        assert "routing: explore 2-opt improvements" in result
        assert "Branch Direction" in result
