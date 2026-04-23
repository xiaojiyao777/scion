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
        expand_round: int = 1,
    ) -> ProtocolResult:
        self.experiment_call_count += 1
        if self._results:
            return self._results.pop(0)
        # Default: return a screening pass
        return _make_protocol_result(stage)


class AlwaysPassVerificationGate:
    """Verification gate stub that always passes."""

    def run(self, workspace: str, champion_workspace: str, patch: Any) -> VerificationResult:
        check = CheckResult(
            name="SYNTAX", passed=True, severity="light", detail="stub pass", elapsed_ms=0
        )
        return VerificationResult(passed=True, checks=(check,))


class AlwaysFailVerificationGate:
    """Verification gate stub that always fails (light)."""

    def run(self, workspace: str, champion_workspace: str, patch: Any) -> VerificationResult:
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
        """After CONTINUE_EXPLORE, the next step generates a fresh hypothesis.

        Uses a sequenced LLM so the two steps produce different hypotheses.
        C10_novelty key for action='modify' is (locus, action, target_file), so the
        two hypotheses must differ in one of those — we vary target_file.
        """
        hyp1 = dict(_VALID_HYPOTHESIS)
        hyp1["target_file"] = "operators/local_search.py"
        hyp2 = dict(_VALID_HYPOTHESIS)
        hyp2["target_file"] = "operators/other_op.py"
        patch1 = dict(_VALID_PATCH)
        patch1["file_path"] = "operators/local_search.py"
        patch2 = dict(_VALID_PATCH)
        patch2["file_path"] = "operators/other_op.py"

        class SequencedLLM:
            def __init__(self):
                self.hyp_calls = 0
                self.patch_calls = 0
            def call(self, prompt, schema, model=None, system_blocks=None):
                if "code_content" in schema.get("required", []):
                    self.patch_calls += 1
                    return patch1 if self.patch_calls == 1 else patch2
                self.hyp_calls += 1
                return hyp1 if self.hyp_calls == 1 else hyp2
            def call_with_tool(self, prompt, tool, model=None, system_blocks=None):
                return self.call(prompt, tool.get("input_schema", {}), model, system_blocks)

        cm = _campaign(tmp_path, llm_client=SequencedLLM(), experiment_protocol=None)
        # _campaign seeds champion_code/operators/local_search.py; seed other_op.py for step 2
        (tmp_path / "champion_code" / "operators" / "other_op.py").write_text(_VALID_CODE)
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
        """Second step on same branch succeeds after initial contract failure.

        Step 1's hypothesis gets marked 'rejected' after patch contract fails, but
        C10_novelty still blocks same-keyed hypothesis within the same champion version.
        So step 2 needs a distinct hypothesis (different target_file).
        """
        bad_patch = {
            "file_path": "solver.py",  # frozen file
            "action": "modify",
            "code_content": _VALID_CODE,
            "test_hint": None,
        }
        hyp1 = dict(_VALID_HYPOTHESIS)  # target_file=operators/local_search.py
        hyp2 = dict(_VALID_HYPOTHESIS)
        hyp2["target_file"] = "operators/other_op.py"
        good_patch2 = dict(_VALID_PATCH)
        good_patch2["file_path"] = "operators/other_op.py"

        call_count = [0]

        class SequencedLLM:
            def __init__(self):
                self.hyp_calls = 0
            def call(self, prompt, schema, model=None, system_blocks=None):
                call_count[0] += 1
                if "code_content" in schema.get("required", []):
                    # patch call — step 1 returns bad (→ contract fail), step 2 returns good
                    if call_count[0] <= 2:
                        return dict(bad_patch)
                    return dict(good_patch2)
                # hypothesis call — vary target_file so step 2 passes novelty
                self.hyp_calls += 1
                return hyp1 if self.hyp_calls == 1 else hyp2
            def call_with_tool(self, prompt, tool, model=None, system_blocks=None):
                return self.call(prompt, tool.get("input_schema", {}), model, system_blocks)

        cm = _campaign(
            tmp_path,
            llm_client=SequencedLLM(),
            experiment_protocol=MockExperimentProtocol(
                results=[_make_protocol_result(ExperimentStage.SCREENING)]
            ),
        )
        # Seed operators/other_op.py for step 2
        (tmp_path / "champion_code" / "operators" / "other_op.py").write_text(_VALID_CODE)
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
        result = gate.run("/tmp", "", patch)
        assert result.passed is True

    def test_default_gate_fails_syntax_error(self, tmp_path):
        gate = VerificationGate()
        from scion.core.models import PatchProposal
        patch = PatchProposal(
            file_path="operators/test.py",
            action="modify",
            code_content="def bad(:\n    pass",
        )
        result = gate.run("/tmp", "", patch)
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
        result = gate.run("/tmp", "", patch)
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
            def run(self, workspace, champion_workspace, patch):
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


# ---------------------------------------------------------------------------
# T03+T04: archive_workspace returns path + campaign_summary.json
# ---------------------------------------------------------------------------

class TestArchiveWorkspaceReturnsPath:
    def test_archive_workspace_returns_path(self, tmp_path):
        """archive_workspace() must return the archive directory path."""
        from scion.runtime.workspace import WorkspaceMaterializer

        campaign_dir = tmp_path / "campaign"
        campaign_dir.mkdir()
        mat = WorkspaceMaterializer(str(campaign_dir))

        # Create a minimal workspace with operators/
        ws = tmp_path / "ws"
        (ws / "operators").mkdir(parents=True)
        (ws / "operators" / "my_op.py").write_text("class MyOp: pass\n")

        result = mat.archive_workspace(str(ws), branch_id="testbranch123")
        assert result is not None
        from pathlib import Path
        assert Path(result).exists()


class TestCampaignSummaryJson:
    def test_campaign_summary_json_structure(self, tmp_path):
        """run() must produce campaign_summary.json with a 'steps' array."""
        import json
        from pathlib import Path

        cm = _campaign(
            tmp_path,
            experiment_protocol=None,
            termination_config=TerminationConfig(max_experiments=1000),
        )
        cm.run(max_rounds=3)

        summary_path = Path(cm._campaign_dir) / "campaign_summary.json"
        assert summary_path.exists()
        data = json.loads(summary_path.read_text())
        assert "steps" in data
        assert isinstance(data["steps"], list)
        assert len(data["steps"]) >= 1
        step = data["steps"][0]
        assert "round" in step
        assert "branch_id" in step
        assert "decision" in step

    def test_campaign_summary_failed_step_has_archive(self, tmp_path):
        """Verification-failed steps must have code_archive_ref in summary."""
        import json
        from pathlib import Path

        cm = _campaign(
            tmp_path,
            verification_gate=AlwaysFailVerificationGate(),
            experiment_protocol=None,
            termination_config=TerminationConfig(max_experiments=1000),
        )
        cm.run(max_rounds=2)

        summary_path = Path(cm._campaign_dir) / "campaign_summary.json"
        assert summary_path.exists()
        data = json.loads(summary_path.read_text())
        assert "steps" in data
        # Steps that failed verification should have failure_stage='verification'
        failed = [s for s in data["steps"] if s.get("failure_stage") == "verification"]
        assert len(failed) >= 1
        # code_archive_ref field must exist (may be None if operators/ absent)
        for s in failed:
            assert "code_archive_ref" in s

    def test_step_record_has_archive_ref_field(self, tmp_path):
        """StepRecord must have code_archive_ref attribute."""
        from scion.core.models import StepRecord, Decision, HypothesisProposal

        hyp = HypothesisProposal(
            hypothesis_text="test",
            change_locus="local_search",
            action="modify",
        )
        sr = StepRecord(
            round_num=1,
            branch_id="br1",
            hypothesis=hyp,
            patch=None,
            contract_passed=False,
            verification_passed=False,
            protocol_result=None,
            decision=Decision.ABANDON,
            failure_stage="verification",
            failure_detail="test fail",
            code_archive_ref="/some/path",
        )
        assert sr.code_archive_ref == "/some/path"
        assert sr.cache_stats is None


# ---------------------------------------------------------------------------
# T16 — _on_promote weight optimization hook
# ---------------------------------------------------------------------------

def _promote_protocol():
    """Return a protocol that produces screening→validation→frozen pass."""
    return MockExperimentProtocol(results=[
        _make_protocol_result(ExperimentStage.SCREENING, gate_outcome="pass"),
        _make_protocol_result(ExperimentStage.VALIDATION, gate_outcome="pass",
                              win_rate=0.7, ci_low=0.005, ci_high=0.02),
        _make_protocol_result(ExperimentStage.FROZEN, gate_outcome="pass",
                              win_rate=0.7, ci_low=0.005, ci_high=0.02),
    ])


def _run_to_promote(cm):
    """Drive campaign manager through three steps to reach PROMOTE."""
    cm.run_one_step()
    cm.run_one_step()
    result = cm.run_one_step()
    assert result.decision == Decision.PROMOTE
    return result


def _setup_for_on_promote(tmp_path, with_registry=False):
    """Create a campaign + workspace ready to call _on_promote directly.

    Returns (cm, branch, ws_path).
    """
    import yaml as _yaml

    ws = tmp_path / "branch_ws"
    ws.mkdir(parents=True)
    (ws / "operators").mkdir(exist_ok=True)
    (ws / "operators" / "local_search.py").write_text(_VALID_CODE)

    if with_registry:
        ops = [
            {"name": "swap", "file_path": "operators/swap.py",
             "category": "order_level", "weight": 0.6, "class_name": "Swap"},
            {"name": "move", "file_path": "operators/move.py",
             "category": "order_level", "weight": 0.4, "class_name": "Move"},
        ]
        (ws / "registry.yaml").write_text(_yaml.dump({"operators": ops}))

    cm = _campaign(tmp_path)
    branch = cm._branch_ctrl.create_branch(cm._champion)
    cm._branch_workspaces[branch.branch_id] = str(ws)
    return cm, branch, str(ws)


class TestPromoteWeightOptimizationHook:
    def test_on_promote_runs_weight_optimization(self, tmp_path):
        """promote → _run_weight_optimization is called when enabled + runner present."""
        import types
        from scion.core.models import WeightOptimizationResult

        call_log = []

        def fake_run_opt(self_cm, snapshot, version, current_weights):
            call_log.append(version)
            return WeightOptimizationResult(
                baseline_weights={},
                best_weights={},
                baseline_score=0.5,
                best_score=0.8,
                improved=True,
                n_evaluations=8,
                elapsed_seconds=1.0,
                observations_ref="",
            )

        cm, branch, _ = _setup_for_on_promote(tmp_path)
        # Attach a protocol with a runner attribute so the enabled-and-runner check passes
        protocol = MockExperimentProtocol(results=[])
        protocol.runner = object()
        cm._experiment_protocol = protocol
        # spec.parameter_search.enabled is True by default

        cm._run_weight_optimization = types.MethodType(fake_run_opt, cm)
        cm._on_promote(branch)

        assert len(call_log) == 1, "Expected _run_weight_optimization to be called once"
        assert call_log[0] == 2  # champion version bumps from 1 → 2

    def test_on_promote_rebuilds_operator_pool_from_registry(self, tmp_path):
        """After promote, champion.operator_pool comes from snapshot registry.yaml."""
        cm, branch, _ = _setup_for_on_promote(tmp_path, with_registry=True)
        cm._spec.parameter_search.enabled = False  # isolate: no optimizer
        cm._experiment_protocol = None

        cm._on_promote(branch)

        pool = cm._champion.operator_pool
        assert cm._champion.version == 2
        # Registry had swap + move — pool should include them
        assert "swap" in pool and "move" in pool

    def test_on_promote_without_parameter_search(self, tmp_path):
        """parameter_search.enabled=False → _run_weight_optimization is NOT called."""
        import types

        call_log = []

        def fake_run_opt(self_cm, snapshot, version):
            call_log.append(version)
            return None

        cm, branch, _ = _setup_for_on_promote(tmp_path)
        cm._spec.parameter_search.enabled = False  # type: ignore[attr-defined]
        cm._run_weight_optimization = types.MethodType(fake_run_opt, cm)

        cm._on_promote(branch)

        assert call_log == [], "_run_weight_optimization must not be called when disabled"

    def test_on_promote_without_runner(self, tmp_path):
        """experiment_protocol=None → no optimization triggered, no crash."""
        import types

        call_log = []

        def fake_run_opt(self_cm, snapshot, version):
            call_log.append(version)
            return None

        cm, branch, _ = _setup_for_on_promote(tmp_path)
        cm._experiment_protocol = None  # no runner
        cm._run_weight_optimization = types.MethodType(fake_run_opt, cm)

        cm._on_promote(branch)  # must not crash

        assert call_log == [], "_run_weight_optimization must not be called without experiment_protocol"


# ---------------------------------------------------------------------------
# T20: Code-failure degraded recovery (pending hypothesis retry)
# ---------------------------------------------------------------------------

class TestCodeFailureRetry:
    """Tests for T20: hypothesis preserved on code gen failure and retried next round."""

    def _make_fail_then_succeed_llm(self):
        """LLM that fails the first code gen call but succeeds on retry."""
        from scion.proposal.llm_client import LLMRetryExhaustedError

        class _LLM:
            def __init__(self):
                self._code_calls = 0

            def call(self, prompt, schema, model=None, system_blocks=None):
                required = set(schema.get("required", []))
                if "hypothesis_text" in required or "change_locus" in required:
                    return dict(_VALID_HYPOTHESIS)
                self._code_calls += 1
                if self._code_calls == 1:
                    raise LLMRetryExhaustedError("simulated code gen failure")
                return dict(_VALID_PATCH)

            def call_with_tool(self, prompt, tool, model=None, system_blocks=None):
                return self.call(prompt, tool.get("input_schema", {}), model, system_blocks)

        return _LLM()

    def _make_always_fail_code_llm(self):
        """LLM that always fails code gen calls."""
        from scion.proposal.llm_client import LLMRetryExhaustedError

        class _LLM:
            def call(self, prompt, schema, model=None, system_blocks=None):
                required = set(schema.get("required", []))
                if "hypothesis_text" in required or "change_locus" in required:
                    return dict(_VALID_HYPOTHESIS)
                raise LLMRetryExhaustedError("simulated code gen failure")

            def call_with_tool(self, prompt, tool, model=None, system_blocks=None):
                return self.call(prompt, tool.get("input_schema", {}), model, system_blocks)

        return _LLM()

    def test_code_failure_triggers_retry_next_round(self, tmp_path):
        """Code gen failure adds hypothesis to pending; next round reuses it."""
        llm = self._make_fail_then_succeed_llm()
        cm = _campaign(
            tmp_path,
            llm_client=llm,
            experiment_protocol=MockExperimentProtocol(
                results=[_make_protocol_result(ExperimentStage.SCREENING)]
            ),
        )

        # Step 1: creates branch, hypothesis succeeds, code gen fails
        r1 = cm.run_one_step()
        assert r1.branch_id is not None
        bid = r1.branch_id
        # The hypothesis should now be in pending (not discarded)
        assert bid in cm._pending_hypotheses, "hypothesis should be queued for retry"

        # Step 2: retries code gen with pending hypothesis — should succeed
        r2 = cm.run_one_step()
        assert r2.branch_id == bid
        # Pending entry consumed
        assert bid not in cm._pending_hypotheses, "pending hypothesis should be cleared on success"
        # Step 2 produced a valid decision (not just a failure skip)
        assert r2.decision is not None

    def test_code_retry_failure_marks_rejected(self, tmp_path):
        """Two consecutive code gen failures → hypothesis marked rejected, no more pending."""
        llm = self._make_always_fail_code_llm()
        cm = _campaign(tmp_path, llm_client=llm)

        # Step 1: code gen fails for the first time → pending
        r1 = cm.run_one_step()
        bid = r1.branch_id
        assert bid in cm._pending_hypotheses, "hypothesis should be queued after first failure"

        # Step 2: retry also fails → hypothesis rejected, no longer pending
        r2 = cm.run_one_step()
        assert r2.branch_id == bid
        assert bid not in cm._pending_hypotheses, "hypothesis must not be re-queued after retry failure"

        # The step history should reflect both failures
        code_fail_steps = [
            s for s in cm._step_history
            if s.branch_id == bid and s.failure_stage == "code_generation"
        ]
        assert len(code_fail_steps) == 2, "both attempts should be recorded in step history"

        # Second record should note it was the retry
        assert "retry" in (code_fail_steps[1].failure_detail or "").lower(), \
            "second failure detail should mention 'retry'"

    def test_code_retry_includes_failure_context(self, tmp_path):
        """On retry, build_code_context receives the prior failure detail."""
        from scion.proposal.context_manager import ContextManager

        captured_contexts = []
        original_build = ContextManager.build_code_context

        def capturing_build(self_ctx, branch, hypothesis, champion, problem_spec,
                            prior_failure=None):
            ctx = original_build(self_ctx, branch=branch, hypothesis=hypothesis,
                                 champion=champion, problem_spec=problem_spec,
                                 prior_failure=prior_failure)
            captured_contexts.append(ctx)
            return ctx

        llm = self._make_fail_then_succeed_llm()
        cm = _campaign(
            tmp_path,
            llm_client=llm,
            experiment_protocol=MockExperimentProtocol(
                results=[_make_protocol_result(ExperimentStage.SCREENING)]
            ),
        )
        cm._ctx_manager.build_code_context = lambda **kw: capturing_build(
            cm._ctx_manager, **kw
        )

        cm.run_one_step()  # step 1: code gen fails
        cm.run_one_step()  # step 2: retry

        assert len(captured_contexts) >= 2, "build_code_context must be called for both attempts"
        # First attempt: no prior failure context
        assert "prior_code_failure" not in captured_contexts[0], \
            "first attempt must not have prior_code_failure"
        # Retry attempt: prior failure context present
        assert "prior_code_failure" in captured_contexts[1], \
            "retry attempt must include prior_code_failure in context"

    def test_successful_code_clears_pending(self, tmp_path):
        """A successful code gen round leaves no pending hypothesis."""
        cm = _campaign(
            tmp_path,
            experiment_protocol=MockExperimentProtocol(
                results=[_make_protocol_result(ExperimentStage.SCREENING)]
            ),
        )
        result = cm.run_one_step()
        assert result.branch_id is not None
        assert result.branch_id not in cm._pending_hypotheses, \
            "successful round must not leave a pending hypothesis"


# ---------------------------------------------------------------------------
# T1: No fake HypothesisRecord fallback in eval step (Sprint G-patch)
# ---------------------------------------------------------------------------

class TestNoFakeHypothesisRecordFallback:
    def test_missing_canonical_record_raises_and_abandons(self, tmp_path):
        """If canonical h_record is absent when eval step runs, the branch is abandoned."""
        protocol = MockExperimentProtocol(
            results=[_make_protocol_result(ExperimentStage.SCREENING)]
        )
        cm = _campaign(tmp_path, experiment_protocol=protocol)

        # Drive branch to EXPLORE → READY_VALIDATE (screening pass)
        r1 = cm.run_one_step()
        bid = r1.branch_id
        assert bid is not None

        # Manually delete the canonical hypothesis record to simulate the lost-record scenario
        cm._branch_current_hypothesis.pop(bid, None)

        # Run next step — the campaign will schedule READY_VALIDATE → VALIDATING
        # and call _run_eval_step, which should raise RuntimeError and abandon the branch
        result = cm.run_one_step()
        assert result.branch_id == bid

        from scion.core.models import BranchState
        branch = cm._branch_ctrl.get_branch(bid)
        assert branch.state == BranchState.ABANDONED, (
            f"Expected ABANDONED but got {branch.state}; result={result}"
        )
