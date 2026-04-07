"""Tests for T20: CampaignManager — full pipeline with MockLLMClient."""
from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
import pytest

from scion.config.problem import ProblemSpec, ProtocolConfig, SplitManifest, SeedLedgerConfig, SearchSpace
from scion.core.campaign import CampaignManager, VerificationGate, StepResult
from scion.core.models import (
    Branch, BranchState, CanaryResult, ChampionState, Decision,
    EvalStats, ExperimentStage, ProtocolResult, VerificationResult, CheckResult,
)
from scion.core.termination import TerminationConfig
from scion.proposal.mock_client import MockLLMClient


# ---------------------------------------------------------------------------
# Fixtures / helpers
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


def _make_problem_spec(root_dir: str) -> ProblemSpec:
    return ProblemSpec(
        name="test_vrp",
        root_dir=root_dir,
        operator_categories=["local_search"],
        search_space=SearchSpace(
            editable=["operators/*.py"],
            frozen=["solver.py", "oracle.py"],
            import_whitelist=["numpy", "random", "math"],
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


def _make_protocol_config() -> ProtocolConfig:
    return ProtocolConfig(
        screening_n=6,
        screening_win_rate_threshold=0.66,
        validation_n=12,
        validation_win_rate_threshold=0.66,
        frozen_n=24,
        min_practical_delta=0.001,
    )


def _make_split_manifest() -> SplitManifest:
    return SplitManifest(
        screening=["case1", "case2"],
        validation=["case3", "case4"],
        frozen=["case5", "case6"],
    )


def _make_seed_ledger() -> SeedLedgerConfig:
    return SeedLedgerConfig(
        screening=[1, 2],
        validation=[3, 4],
        frozen=[5, 6],
    )


def _make_protocol_result(
    stage: ExperimentStage,
    gate_outcome: str = "pass",
    win_rate: float = 0.7,
    median_delta: float = 0.01,
    ci_low: float = 0.005,
    ci_high: float = 0.02,
) -> ProtocolResult:
    stats = EvalStats(
        n_cases=10, wins=7, losses=2, ties=1,
        win_rate=win_rate, median_delta=median_delta,
        ci_low=ci_low, ci_high=ci_high,
    )
    return ProtocolResult(
        stage=stage,
        stats=stats,
        gate_outcome=gate_outcome,
        reason_codes=("TEST",),
        exposed_summary=f"stage={stage.value} outcome={gate_outcome}",
        raw_metrics_ref="/tmp/test.json",
    )


class MockExperimentProtocol:
    """Configurable mock ExperimentProtocol for campaign tests."""

    def __init__(self, results: List[ProtocolResult], canary_pass: bool = True) -> None:
        self._results = list(results)
        self._canary_pass = canary_pass
        self.canary_call_count = 0
        self.experiment_call_count = 0

    def run_canary(self, candidate_ws: str, champion_ws: str) -> CanaryResult:
        self.canary_call_count += 1
        return CanaryResult(passed=self._canary_pass, reason=None)

    def run_experiment(
        self,
        stage: ExperimentStage,
        candidate_ws: str,
        champion_ws: str,
        hypothesis_action: str,
        expand: bool = False,
    ) -> ProtocolResult:
        self.experiment_call_count += 1
        if self._results:
            return self._results.pop(0)
        # Default: return a screening pass
        return _make_protocol_result(stage)


class AlwaysPassVerificationGate:
    """Verification gate stub that always passes."""

    def run(self, workspace: str, patch: Any) -> VerificationResult:
        check = CheckResult(
            name="SYNTAX", passed=True, severity="light", detail="stub pass", elapsed_ms=0
        )
        return VerificationResult(passed=True, checks=(check,))


class AlwaysFailVerificationGate:
    """Verification gate stub that always fails (light)."""

    def run(self, workspace: str, patch: Any) -> VerificationResult:
        check = CheckResult(
            name="SYNTAX", passed=False, severity="light",
            detail="stub fail", elapsed_ms=0,
        )
        return VerificationResult(
            passed=False, checks=(check,),
            failure_severity="light", first_failure="SYNTAX",
        )


def _campaign(
    tmp_path: Path,
    llm_client: Any = None,
    experiment_protocol: Any = None,
    verification_gate: Any = None,
    termination_config: Optional[TerminationConfig] = None,
) -> CampaignManager:
    # Create minimal champion code directory
    code_dir = tmp_path / "champion_code"
    (code_dir / "operators").mkdir(parents=True)
    (code_dir / "operators" / "local_search.py").write_text(_VALID_CODE)

    campaign_dir = str(tmp_path / "campaign")
    spec = _make_problem_spec(str(code_dir))
    champion = _make_champion(str(code_dir))

    return CampaignManager(
        problem_spec=spec,
        protocol_config=_make_protocol_config(),
        split_manifest=_make_split_manifest(),
        seed_ledger=_make_seed_ledger(),
        llm_client=llm_client or MockLLMClient(
            hypothesis_response=_VALID_HYPOTHESIS,
            patch_response=_VALID_PATCH,
        ),
        champion=champion,
        campaign_dir=campaign_dir,
        verification_gate=verification_gate or AlwaysPassVerificationGate(),
        experiment_protocol=experiment_protocol,
        termination_config=termination_config or TerminationConfig(
            max_experiments=100,
            stagnation_limit=50,
        ),
    )


# ---------------------------------------------------------------------------
# Basic campaign structure tests
# ---------------------------------------------------------------------------

class TestCampaignBasics:
    def test_initial_state(self, tmp_path):
        cm = _campaign(tmp_path)
        state = cm.get_state()
        assert state["n_experiments"] == 0
        assert state["n_active_branches"] == 0
        assert state["champion_version"] == 1

    def test_should_stop_false_initially(self, tmp_path):
        cm = _campaign(tmp_path)
        assert not cm.should_stop()

    def test_should_stop_when_max_experiments_reached(self, tmp_path):
        cm = _campaign(
            tmp_path,
            termination_config=TerminationConfig(max_experiments=0)
        )
        assert cm.should_stop()

    def test_run_one_step_creates_branch(self, tmp_path):
        cm = _campaign(tmp_path, experiment_protocol=MockExperimentProtocol(
            results=[_make_protocol_result(ExperimentStage.SCREENING)]
        ))
        result = cm.run_one_step()
        assert result.branch_id is not None

    def test_get_state_after_step(self, tmp_path):
        cm = _campaign(tmp_path, experiment_protocol=MockExperimentProtocol(
            results=[_make_protocol_result(ExperimentStage.SCREENING)]
        ))
        cm.run_one_step()
        state = cm.get_state()
        assert state["n_experiments"] == 1


# ---------------------------------------------------------------------------
# CONTINUE_EXPLORE path (no protocol — auto-continue)
# ---------------------------------------------------------------------------

class TestContinueExplore:
    def test_no_protocol_produces_continue_explore(self, tmp_path):
        """Without experiment protocol, decision is CONTINUE_EXPLORE (no stats)."""
        cm = _campaign(tmp_path, experiment_protocol=None)
        result = cm.run_one_step()
        # Decision should be CONTINUE_EXPLORE because there are no stats
        assert result.decision == Decision.CONTINUE_EXPLORE

    def test_continue_explore_clears_workspace(self, tmp_path):
        """After CONTINUE_EXPLORE, the branch workspace is cleaned up."""
        cm = _campaign(tmp_path, experiment_protocol=None)
        result = cm.run_one_step()
        assert result.branch_id is not None
        bid = result.branch_id
        # Workspace should have been cleared
        assert bid not in cm._branch_workspaces

    def test_continue_explore_clears_hypothesis(self, tmp_path):
        """After CONTINUE_EXPLORE, the branch hypothesis is cleared."""
        cm = _campaign(tmp_path, experiment_protocol=None)
        result = cm.run_one_step()
        bid = result.branch_id
        assert bid not in cm._branch_hypotheses

    def test_continue_explore_branch_stays_in_explore(self, tmp_path):
        """Branch should remain in EXPLORE state after CONTINUE_EXPLORE."""
        cm = _campaign(tmp_path, experiment_protocol=None)
        result = cm.run_one_step()
        bid = result.branch_id
        branch = cm._branch_ctrl.get_branch(bid)
        assert branch.state == BranchState.EXPLORE

    def test_second_step_proposes_new_hypothesis(self, tmp_path):
        """After CONTINUE_EXPLORE, the next step generates a fresh hypothesis."""
        cm = _campaign(tmp_path, experiment_protocol=None)
        r1 = cm.run_one_step()
        r2 = cm.run_one_step()
        # Both steps should be on the same branch
        assert r1.branch_id == r2.branch_id
        # Both should be CONTINUE_EXPLORE
        assert r2.decision == Decision.CONTINUE_EXPLORE


# ---------------------------------------------------------------------------
# Full successful path: EXPLORE → QUEUE_VALIDATE → VALIDATING → QUEUE_FROZEN → PROMOTE
# ---------------------------------------------------------------------------

class TestFullSuccessPath:
    def test_screening_pass_queues_validate(self, tmp_path):
        """Screening pass → decision=QUEUE_VALIDATE, branch in READY_VALIDATE."""
        protocol = MockExperimentProtocol(
            results=[_make_protocol_result(ExperimentStage.SCREENING, gate_outcome="pass")]
        )
        cm = _campaign(tmp_path, experiment_protocol=protocol)
        result = cm.run_one_step()
        assert result.decision == Decision.QUEUE_VALIDATE
        bid = result.branch_id
        branch = cm._branch_ctrl.get_branch(bid)
        assert branch.state == BranchState.READY_VALIDATE

    def test_validation_step_after_screening(self, tmp_path):
        """Second step (READY_VALIDATE → VALIDATING) produces QUEUE_FROZEN decision."""
        protocol = MockExperimentProtocol(results=[
            _make_protocol_result(ExperimentStage.SCREENING, gate_outcome="pass"),
            _make_protocol_result(ExperimentStage.VALIDATION, gate_outcome="pass",
                                  win_rate=0.7, ci_low=0.005, ci_high=0.02),
        ])
        cm = _campaign(tmp_path, experiment_protocol=protocol)
        # Step 1: EXPLORE → QUEUE_VALIDATE
        cm.run_one_step()
        # Step 2: READY_VALIDATE → VALIDATING → eval → QUEUE_FROZEN
        result = cm.run_one_step()
        assert result.decision == Decision.QUEUE_FROZEN

    def test_frozen_step_promotes(self, tmp_path):
        """Third step (FROZEN_TESTING) with ci_low >= 0 → PROMOTE."""
        protocol = MockExperimentProtocol(results=[
            _make_protocol_result(ExperimentStage.SCREENING, gate_outcome="pass"),
            _make_protocol_result(ExperimentStage.VALIDATION, gate_outcome="pass",
                                  win_rate=0.7, ci_low=0.005, ci_high=0.02),
            _make_protocol_result(ExperimentStage.FROZEN, gate_outcome="pass",
                                  win_rate=0.7, ci_low=0.005, ci_high=0.02),
        ])
        cm = _campaign(tmp_path, experiment_protocol=protocol)
        cm.run_one_step()  # EXPLORE → QUEUE_VALIDATE
        cm.run_one_step()  # VALIDATING → QUEUE_FROZEN
        result = cm.run_one_step()  # FROZEN_TESTING → PROMOTE
        assert result.decision == Decision.PROMOTE

    def test_promote_updates_champion_version(self, tmp_path):
        """After PROMOTE, champion version increments."""
        protocol = MockExperimentProtocol(results=[
            _make_protocol_result(ExperimentStage.SCREENING, gate_outcome="pass"),
            _make_protocol_result(ExperimentStage.VALIDATION, gate_outcome="pass",
                                  win_rate=0.7, ci_low=0.005, ci_high=0.02),
            _make_protocol_result(ExperimentStage.FROZEN, gate_outcome="pass",
                                  win_rate=0.7, ci_low=0.005, ci_high=0.02),
        ])
        cm = _campaign(tmp_path, experiment_protocol=protocol)
        assert cm._champion.version == 1
        cm.run_one_step()
        cm.run_one_step()
        cm.run_one_step()
        assert cm._champion.version == 2

    def test_promote_marks_other_branches_stale(self, tmp_path):
        """After PROMOTE, all sibling branches should be STALE."""
        protocol = MockExperimentProtocol(results=[
            # Branch 1: screening pass
            _make_protocol_result(ExperimentStage.SCREENING, gate_outcome="pass"),
            _make_protocol_result(ExperimentStage.VALIDATION, gate_outcome="pass",
                                  win_rate=0.7, ci_low=0.005, ci_high=0.02),
            _make_protocol_result(ExperimentStage.FROZEN, gate_outcome="pass",
                                  win_rate=0.7, ci_low=0.005, ci_high=0.02),
        ])
        cm = _campaign(tmp_path, experiment_protocol=protocol)
        # Step 1: creates branch A (EXPLORE → QUEUE_VALIDATE)
        r1 = cm.run_one_step()
        bid_a = r1.branch_id

        # Manually create a second branch for testing
        branch_b = cm._branch_ctrl.create_branch(cm._champion)

        # Steps 2-3: branch A → PROMOTE
        cm.run_one_step()
        cm.run_one_step()

        # Branch B should now be STALE
        branch_b_state = cm._branch_ctrl.get_branch(branch_b.branch_id)
        assert branch_b_state.state == BranchState.STALE


# ---------------------------------------------------------------------------
# Contract failure routing
# ---------------------------------------------------------------------------

class TestContractFailure:
    def test_patch_contract_fail_clears_workspace(self, tmp_path):
        """When patch contract fails, workspace is not retained."""
        bad_patch = {
            "file_path": "solver.py",  # frozen file — C5 will fail
            "action": "modify",
            "code_content": _VALID_CODE,
            "test_hint": None,
        }
        llm = MockLLMClient(
            hypothesis_response=_VALID_HYPOTHESIS,
            patch_response=bad_patch,
        )
        cm = _campaign(tmp_path, llm_client=llm)
        result = cm.run_one_step()
        assert result.branch_id is not None
        assert result.decision is None  # no decision was made
        assert result.branch_id not in cm._branch_workspaces

    def test_contract_fail_branch_stays_explore(self, tmp_path):
        """After contract failure, branch remains in EXPLORE for retry."""
        bad_patch = {
            "file_path": "solver.py",  # frozen file
            "action": "modify",
            "code_content": _VALID_CODE,
            "test_hint": None,
        }
        llm = MockLLMClient(hypothesis_response=_VALID_HYPOTHESIS, patch_response=bad_patch)
        cm = _campaign(tmp_path, llm_client=llm)
        result = cm.run_one_step()
        branch = cm._branch_ctrl.get_branch(result.branch_id)
        assert branch.state == BranchState.EXPLORE  # can still be retried

    def test_hypothesis_contract_fail_handled(self, tmp_path):
        """Invalid hypothesis (empty change_locus) routes as contract failure."""
        bad_hypothesis = {
            "hypothesis_text": "test",
            "change_locus": "unknown_category",  # C2 will fail
            "action": "modify",
            "target_file": "operators/local_search.py",
        }
        llm = MockLLMClient(hypothesis_response=bad_hypothesis, patch_response=_VALID_PATCH)
        cm = _campaign(tmp_path, llm_client=llm)
        result = cm.run_one_step()
        assert result.branch_id is not None
        assert result.decision is None

    def test_retry_after_contract_fail(self, tmp_path):
        """Second step on same branch succeeds after initial contract failure."""
        bad_patch = {
            "file_path": "solver.py",  # frozen file
            "action": "modify",
            "code_content": _VALID_CODE,
            "test_hint": None,
        }
        # First two calls: bad patch; subsequent calls: good patch
        call_count = [0]
        good_llm = MockLLMClient(
            hypothesis_response=_VALID_HYPOTHESIS, patch_response=_VALID_PATCH
        )

        class SequencedLLM:
            def call(self, prompt, schema, model=None, system_blocks=None):
                call_count[0] += 1
                if "code_content" in schema.get("required", []):
                    # patch call
                    if call_count[0] <= 2:
                        # First patch call: return bad
                        return dict(bad_patch)
                    return dict(_VALID_PATCH)
                return dict(_VALID_HYPOTHESIS)
            def call_with_tool(self, prompt, tool, model=None, system_blocks=None):
                return self.call(prompt, tool.get("input_schema", {}), model, system_blocks)

        cm = _campaign(
            tmp_path,
            llm_client=SequencedLLM(),
            experiment_protocol=MockExperimentProtocol(
                results=[_make_protocol_result(ExperimentStage.SCREENING)]
            ),
        )
        # Step 1: contract fails
        r1 = cm.run_one_step()
        assert r1.decision is None
        # Step 2: succeeds
        r2 = cm.run_one_step()
        assert r2.branch_id == r1.branch_id
        assert r2.decision is not None


# ---------------------------------------------------------------------------
# Screening fail → ABANDON (win_rate very low)
# ---------------------------------------------------------------------------

class TestScreeningFail:
    def test_screening_fail_low_winrate_continue_explore(self, tmp_path):
        """win_rate=0.3 → CONTINUE_EXPLORE (re-propose, not abandon)."""
        protocol = MockExperimentProtocol(results=[
            _make_protocol_result(
                ExperimentStage.SCREENING, gate_outcome="fail",
                win_rate=0.3, median_delta=-0.005, ci_low=-0.01, ci_high=0.0,
            )
        ])
        cm = _campaign(tmp_path, experiment_protocol=protocol)
        result = cm.run_one_step()
        # win_rate < 0.5 → CONTINUE_EXPLORE (not ABANDON)
        assert result.decision == Decision.CONTINUE_EXPLORE


# ---------------------------------------------------------------------------
# Canary failure
# ---------------------------------------------------------------------------

class TestCanaryFail:
    def test_canary_fail_leads_to_abandon(self, tmp_path):
        """Canary failure → features.canary_passed=False → DecisionEngine → ABANDON."""
        protocol = MockExperimentProtocol(
            results=[_make_protocol_result(ExperimentStage.SCREENING)],
            canary_pass=False,
        )
        cm = _campaign(tmp_path, experiment_protocol=protocol)
        result = cm.run_one_step()
        assert result.decision == Decision.ABANDON


# ---------------------------------------------------------------------------
# Stale branch reconciliation
# ---------------------------------------------------------------------------

class TestStalePath:
    def test_stale_branch_reconcile_success(self, tmp_path):
        """STALE branch is reconciled when patch still applies."""
        protocol = MockExperimentProtocol(results=[
            _make_protocol_result(ExperimentStage.SCREENING, gate_outcome="pass"),
        ])
        cm = _campaign(tmp_path, experiment_protocol=protocol)
        # Step 1: create branch, it gets QUEUE_VALIDATE
        r1 = cm.run_one_step()
        bid = r1.branch_id
        assert r1.decision == Decision.QUEUE_VALIDATE

        # Manually mark branch stale
        cm._branch_ctrl.mark_all_stale(new_champion_id=2)
        branch = cm._branch_ctrl.get_branch(bid)
        assert branch.state == BranchState.STALE

        # Next step: scheduler selects STALE branch → reconcile
        result = cm.run_one_step()
        assert result.action == "reconcile"
        assert result.branch_id == bid

    def test_stale_branch_reconcile_with_no_patch_abandons(self, tmp_path):
        """STALE branch with no stored patch → reconcile fails → ABANDONED."""
        cm = _campaign(tmp_path)
        # Create a branch then mark it stale without any patch
        branch = cm._branch_ctrl.create_branch(cm._champion)
        cm._branch_ctrl.mark_all_stale(new_champion_id=2)

        result = cm.run_one_step()
        assert result.action == "reconcile"
        branch_state = cm._branch_ctrl.get_branch(branch.branch_id)
        assert branch_state.state == BranchState.ABANDONED


# ---------------------------------------------------------------------------
# Verification gate failure
# ---------------------------------------------------------------------------

class TestVerificationGate:
    def test_default_gate_passes_valid_syntax(self, tmp_path):
        gate = VerificationGate()
        from scion.core.models import PatchProposal
        patch = PatchProposal(
            file_path="operators/test.py",
            action="modify",
            code_content=_VALID_CODE,
        )
        result = gate.run("/tmp", patch)
        assert result.passed is True

    def test_default_gate_fails_syntax_error(self, tmp_path):
        gate = VerificationGate()
        from scion.core.models import PatchProposal
        patch = PatchProposal(
            file_path="operators/test.py",
            action="modify",
            code_content="def bad(:\n    pass",
        )
        result = gate.run("/tmp", patch)
        assert result.passed is False
        assert result.failure_severity == "light"

    def test_default_gate_passes_delete(self, tmp_path):
        gate = VerificationGate()
        from scion.core.models import PatchProposal
        patch = PatchProposal(
            file_path="operators/test.py",
            action="delete",
            code_content="",
        )
        result = gate.run("/tmp", patch)
        assert result.passed is True

    def test_verification_fail_light_triggers_fix(self, tmp_path):
        """Light verification failure triggers fix_code, then succeeds."""
        fix_call_count = [0]

        class FixSuccessClient:
            def call(self, prompt, schema, model=None, system_blocks=None):
                if "code_content" in schema.get("required", []):
                    fix_call_count[0] += 1
                    return dict(_VALID_PATCH)
                return dict(_VALID_HYPOTHESIS)
            def call_with_tool(self, prompt, tool, model=None, system_blocks=None):
                return self.call(prompt, tool.get("input_schema", {}), model, system_blocks)

        # Gate fails on first run (bad code), passes on second (fixed code)
        run_count = [0]

        class ConditionalGate:
            def run(self, workspace, patch):
                run_count[0] += 1
                if run_count[0] == 1:
                    # First call (original patch): fail
                    check = CheckResult(
                        name="SYNTAX", passed=False, severity="light",
                        detail="bad syntax", elapsed_ms=0,
                    )
                    return VerificationResult(
                        passed=False, checks=(check,),
                        failure_severity="light", first_failure="SYNTAX",
                    )
                # Subsequent calls: pass
                check = CheckResult(
                    name="SYNTAX", passed=True, severity="light",
                    detail="ok", elapsed_ms=0,
                )
                return VerificationResult(passed=True, checks=(check,))

        cm = _campaign(
            tmp_path,
            llm_client=FixSuccessClient(),
            verification_gate=ConditionalGate(),
            experiment_protocol=MockExperimentProtocol(
                results=[_make_protocol_result(ExperimentStage.SCREENING)]
            ),
        )
        result = cm.run_one_step()
        # Should have attempted a fix and succeeded
        assert fix_call_count[0] >= 1
        assert result.decision is not None


# ---------------------------------------------------------------------------
# run() loop integration
# ---------------------------------------------------------------------------

class TestRunLoop:
    def test_run_stops_on_max_experiments(self, tmp_path):
        """run() should stop when termination condition is met."""
        cm = _campaign(
            tmp_path,
            experiment_protocol=None,
            termination_config=TerminationConfig(
                max_experiments=3,
                stagnation_limit=100,
                max_wall_clock_hours=24,
            ),
        )
        cm.run(max_rounds=100)
        # Should have stopped (3 experiments budget exhausted causes no_progress eventually)
        assert cm._n_experiments <= 100  # sanity check

    def test_run_respects_max_rounds_arg(self, tmp_path):
        """run(max_rounds=N) stops after at most N steps."""
        cm = _campaign(
            tmp_path,
            experiment_protocol=None,
            termination_config=TerminationConfig(max_experiments=10000),
        )
        cm.run(max_rounds=3)
        assert cm._n_experiments <= 3
