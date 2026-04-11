"""Sprint G1: Control boundary hardening + hypothesis lifecycle tests.

Verifies:
- fix patch re-passes Contract Gate before apply
- pending hypothesis re-passes hypothesis Contract Gate
- last_clean_code_hash only updated after verification pass
- eval-only steps reuse original hypothesis_id
- eval-only steps write StepRecord to step_history
- stale reconcile runs Contract → Verification → re-screening
- StepRecord.decision is None for early failures
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import MagicMock, patch as mock_patch

import pytest

from scion.config.problem import ProblemSpec, ProtocolConfig, SplitManifest, SeedLedgerConfig, SearchSpace
from scion.core.campaign import CampaignManager
from scion.core.models import (
    Branch, BranchState, CanaryResult, ChampionState, CheckResult,
    ContractResult, Decision, EvalStats, ExperimentStage, HypothesisProposal,
    HypothesisRecord, ProtocolResult, StepRecord, VerificationResult,
)
from scion.core.termination import TerminationConfig
from scion.proposal.mock_client import MockLLMClient


# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------

_VALID_CODE = (
    "class LocalSearch:\n"
    "    def execute(self, solution, rng):\n"
    "        return solution\n"
)

_VALID_HYPOTHESIS = {
    "hypothesis_text": "Improve by trying 2-opt.",
    "change_locus": "local_search",
    "action": "modify",
    "target_file": "operators/local_search.py",
    "predicted_direction": "improve",
    "target_weakness": "slow",
    "expected_effect": "better",
    "suggested_weight": 0.3,
}

_VALID_PATCH = {
    "file_path": "operators/local_search.py",
    "action": "modify",
    "code_content": _VALID_CODE,
    "test_hint": None,
}


def _make_spec(root_dir: str) -> ProblemSpec:
    return ProblemSpec(
        name="test_vrp",
        root_dir=root_dir,
        operator_categories=["local_search"],
        search_space=SearchSpace(
            editable=["operators/*.py"],
            frozen=["solver.py"],
            import_whitelist=["numpy", "random", "math"],
        ),
    )


def _make_champion(code_dir: str) -> ChampionState:
    return ChampionState(
        version=1,
        operator_pool={},
        solver_config_hash="abc123",
        code_snapshot_path=str(code_dir),
        code_snapshot_hash="deadbeef",
    )


def _make_protocol_result(
    gate_outcome: str = "pass",
    stage: ExperimentStage = ExperimentStage.SCREENING,
    win_rate: float = 0.7,
) -> ProtocolResult:
    stats = EvalStats(
        n_cases=6, wins=4, losses=2, ties=0,
        win_rate=win_rate, median_delta=0.01,
        ci_low=0.005, ci_high=0.02,
    )
    return ProtocolResult(
        stage=stage,
        stats=stats,
        gate_outcome=gate_outcome,
        reason_codes=("TEST",),
        exposed_summary=f"stage={stage.value}",
        raw_metrics_ref="/tmp/test.json",
    )


class _AlwaysPassVerification:
    def run(self, *args, **kwargs) -> VerificationResult:
        return VerificationResult(
            passed=True,
            checks=(CheckResult(name="SYNTAX", passed=True, severity="light", detail="ok", elapsed_ms=0),),
        )


class _AlwaysFailVerificationLight:
    def run(self, *args, **kwargs) -> VerificationResult:
        return VerificationResult(
            passed=False,
            checks=(CheckResult(name="SYNTAX", passed=False, severity="light", detail="fail", elapsed_ms=0),),
            failure_severity="light",
            first_failure="SYNTAX",
        )


class _MockProtocol:
    """Configurable mock ExperimentProtocol."""

    def __init__(
        self,
        results: Optional[List[ProtocolResult]] = None,
        canary_pass: bool = True,
    ) -> None:
        self._results = list(results or [])
        self._canary_pass = canary_pass
        self.canary_calls: List[Tuple] = []
        self.experiment_calls: List[Tuple] = []

    def run_canary(self, candidate_ws: str, champion_ws: str) -> CanaryResult:
        self.canary_calls.append((candidate_ws, champion_ws))
        return CanaryResult(passed=self._canary_pass)

    def run_experiment(
        self,
        stage: ExperimentStage,
        candidate_ws: str,
        champion_ws: str,
        hypothesis_action: str,
        expand: bool = False,
        expand_round: int = 1,
    ) -> ProtocolResult:
        self.experiment_calls.append((stage, candidate_ws, champion_ws, hypothesis_action))
        if self._results:
            return self._results.pop(0)
        return _make_protocol_result()


def _campaign(
    tmp_path: Path,
    llm_client: Any = None,
    experiment_protocol: Any = None,
    verification_gate: Any = None,
) -> CampaignManager:
    code_dir = tmp_path / "champion_code"
    (code_dir / "operators").mkdir(parents=True)
    (code_dir / "operators" / "local_search.py").write_text(_VALID_CODE)

    campaign_dir = str(tmp_path / "campaign")
    spec = _make_spec(str(code_dir))
    champion = _make_champion(code_dir)

    return CampaignManager(
        problem_spec=spec,
        protocol_config=ProtocolConfig(
            screening_n=6,
            screening_win_rate_threshold=0.66,
            validation_n=12,
            validation_win_rate_threshold=0.66,
            frozen_n=24,
            min_practical_delta=0.001,
        ),
        split_manifest=SplitManifest(
            screening=["c1", "c2"],
            validation=["c3", "c4"],
            frozen=["c5", "c6"],
        ),
        seed_ledger=SeedLedgerConfig(
            screening=[1, 2],
            validation=[3, 4],
            frozen=[5, 6],
        ),
        llm_client=llm_client or MockLLMClient(
            hypothesis_response=_VALID_HYPOTHESIS,
            patch_response=_VALID_PATCH,
        ),
        champion=champion,
        campaign_dir=campaign_dir,
        verification_gate=verification_gate or _AlwaysPassVerification(),
        experiment_protocol=experiment_protocol,
        termination_config=TerminationConfig(max_experiments=100, stagnation_limit=50),
    )


# ---------------------------------------------------------------------------
# Gate bypass — fix patch (T1)
# ---------------------------------------------------------------------------

class TestFixPatchContractGate:
    def test_fix_patch_must_pass_contract_gate(self, tmp_path):
        """fix_code() generated patch must be validated by ContractGate before apply."""
        from scion.core.models import PatchProposal
        fix_patch_obj = PatchProposal(
            file_path="operators/local_search.py",
            action="modify",
            code_content="class LocalSearch:\n    def execute(self, solution, rng):\n        return solution\n",
        )
        cm = _campaign(
            tmp_path,
            verification_gate=_AlwaysFailVerificationLight(),
        )
        # Mock fix_code to return a valid patch (bypass LLM)
        cm._creative.fix_code = MagicMock(return_value=fix_patch_obj)

        validate_patch_calls: List[Any] = []
        original_validate = cm._contract_gate.validate_patch

        def spy_validate_patch(patch):
            validate_patch_calls.append(patch)
            return original_validate(patch)

        cm._contract_gate.validate_patch = spy_validate_patch
        cm.run_one_step()
        # validate_patch called at least twice: once for original patch, once for fix patch
        assert len(validate_patch_calls) >= 2, (
            "fix patch should also be validated by ContractGate, "
            f"but validate_patch was only called {len(validate_patch_calls)} times"
        )

    def test_fix_patch_contract_fail_does_not_apply(self, tmp_path):
        """If fix patch fails ContractGate, it must NOT be applied to the workspace."""
        from scion.core.models import PatchProposal
        fix_patch_obj = PatchProposal(
            file_path="operators/local_search.py",
            action="modify",
            code_content="class LocalSearch:\n    def execute(self, solution, rng):\n        return solution\n",
        )
        cm = _campaign(
            tmp_path,
            verification_gate=_AlwaysFailVerificationLight(),
        )
        cm._creative.fix_code = MagicMock(return_value=fix_patch_obj)

        apply_calls: List[Any] = []
        original_apply = cm._materializer.apply_patch

        def spy_apply_patch(workspace, patch):
            apply_calls.append(patch)
            return original_apply(workspace, patch)

        cm._materializer.apply_patch = spy_apply_patch

        # Make validate_patch fail for the fix patch (second call)
        call_count = [0]
        original_validate = cm._contract_gate.validate_patch

        def fail_on_fix_validate(patch):
            call_count[0] += 1
            if call_count[0] >= 2:
                return ContractResult(passed=False, checks=(), failure_reason="fix rejected")
            return original_validate(patch)

        cm._contract_gate.validate_patch = fail_on_fix_validate
        cm.run_one_step()
        # apply_patch should only have been called ONCE (for the original patch),
        # not a second time for the rejected fix patch
        assert len(apply_calls) == 1, (
            f"fix patch must not be applied when ContractGate rejects it, "
            f"but apply_patch was called {len(apply_calls)} times"
        )


# ---------------------------------------------------------------------------
# Gate bypass — pending hypothesis (T2)
# ---------------------------------------------------------------------------

class TestPendingHypothesisContractGate:
    def test_pending_hypothesis_reruns_contract_gate(self, tmp_path):
        """A pending (code-retry) hypothesis must re-run validate_hypothesis() before Round 2."""
        # Step 1: hypothesis passes contract, code gen fails → pending
        # Step 2: pending hypothesis is retried → validate_hypothesis must be called again
        code_fail_patch = None  # simulate code gen failure by returning no patch

        call_count = [0]
        validate_hyp_calls = [0]
        original_validate_hyp = None

        llm = MockLLMClient(
            hypothesis_response=_VALID_HYPOTHESIS,
            patch_response=_VALID_PATCH,
        )
        cm = _campaign(tmp_path, llm_client=llm)
        original_validate_hyp = cm._contract_gate.validate_hypothesis

        def spy_validate_hypothesis(hyp, active, blacklist):
            validate_hyp_calls[0] += 1
            return original_validate_hyp(hyp, active, blacklist)

        cm._contract_gate.validate_hypothesis = spy_validate_hypothesis

        # Force code gen to fail on first step, succeed on second
        gen_code_calls = [0]
        original_generate_code = cm._creative.generate_code

        def fail_first_code_gen(ctx):
            gen_code_calls[0] += 1
            if gen_code_calls[0] == 1:
                from scion.proposal.engine import ProposalValidationError
                raise ProposalValidationError("forced code gen failure")
            return original_generate_code(ctx)

        cm._creative.generate_code = fail_first_code_gen

        # Step 1: hypothesis contract passes, code gen fails → pending
        cm.run_one_step()
        calls_after_step1 = validate_hyp_calls[0]
        assert calls_after_step1 >= 1, "validate_hypothesis must be called on step 1"

        # Step 2: pending retry — validate_hypothesis MUST be called again
        cm.run_one_step()
        assert validate_hyp_calls[0] > calls_after_step1, (
            "validate_hypothesis must be called again for pending hypothesis retry"
        )


# ---------------------------------------------------------------------------
# Clean-base (T3)
# ---------------------------------------------------------------------------

class TestLastCleanCodeHash:
    def test_last_clean_hash_updates_only_after_verification_pass(self, tmp_path):
        """After apply_patch, last_clean_code_hash must NOT be set before verification passes."""
        cm = _campaign(
            tmp_path,
            experiment_protocol=_MockProtocol(
                results=[_make_protocol_result("pass")]
            ),
        )
        branch_id_container: List[str] = []

        # Intercept record_candidate_code to capture state at that moment
        original_record_candidate = cm._branch_ctrl.record_candidate_code
        original_record_pass = cm._branch_ctrl.record_verification_pass
        candidate_clean_at_apply: List[Optional[str]] = []
        clean_after_verify: List[Optional[str]] = []

        def spy_record_candidate(bid, code_hash):
            branch = cm._branch_ctrl.get_branch(bid)
            candidate_clean_at_apply.append(branch.last_clean_code_hash)
            branch_id_container.append(bid)
            return original_record_candidate(bid, code_hash)

        def spy_record_pass(bid, code_hash):
            result = original_record_pass(bid, code_hash)
            branch = cm._branch_ctrl.get_branch(bid)
            clean_after_verify.append(branch.last_clean_code_hash)
            return result

        cm._branch_ctrl.record_candidate_code = spy_record_candidate
        cm._branch_ctrl.record_verification_pass = spy_record_pass

        cm.run_one_step()

        # last_clean_code_hash must be None when record_candidate_code is called
        assert candidate_clean_at_apply, "record_candidate_code must be called"
        assert candidate_clean_at_apply[0] is None, (
            "last_clean_code_hash must be None immediately after apply_patch "
            "(before verification); was set too early"
        )

    def test_verification_fail_preserves_last_clean_hash(self, tmp_path):
        """When verification fails, last_clean_code_hash must remain None (never updated)."""
        cm = _campaign(
            tmp_path,
            verification_gate=_AlwaysFailVerificationLight(),
        )
        # Make fix generation also fail so verification definitely fails
        cm._creative.fix_code = MagicMock(return_value=None)

        cm.run_one_step()

        # Find the branch that was created
        branches = cm._branch_ctrl.get_active_branches()
        all_branches = list(cm._branch_ctrl._branches.values())
        for b in all_branches:
            assert b.last_clean_code_hash is None, (
                f"last_clean_code_hash must stay None after verification failure, "
                f"but got {b.last_clean_code_hash!r} for branch {b.branch_id}"
            )


# ---------------------------------------------------------------------------
# Hypothesis lifecycle (T4)
# ---------------------------------------------------------------------------

class TestEvalStepHypothesisLifecycle:
    def test_eval_step_reuses_original_hypothesis_id(self, tmp_path):
        """Validation/frozen steps must reuse the same hypothesis_id from screening."""
        # NOTE: run_one_step() for READY_VALIDATE schedules AND runs the eval in one call.
        cm = _campaign(
            tmp_path,
            experiment_protocol=_MockProtocol(results=[
                _make_protocol_result("pass", stage=ExperimentStage.SCREENING, win_rate=0.85),
                _make_protocol_result("pass", stage=ExperimentStage.VALIDATION, win_rate=0.85),
            ]),
        )
        # Step 1: explore + screening → QUEUE_VALIDATE
        r1 = cm.run_one_step()
        assert r1.decision == Decision.QUEUE_VALIDATE

        # Get the hypothesis_id from the screening step record
        screening_steps = [s for s in cm._step_history if s.failure_stage is None and s.hypothesis_id]
        assert screening_steps, "should have at least one success step"
        screening_hyp_id = screening_steps[-1].hypothesis_id

        # Step 2: schedule READY_VALIDATE → VALIDATING + run eval (in same call)
        r2 = cm.run_one_step()
        assert r2.action == "validate", f"expected validate action, got {r2.action!r}"

        # Find the validation step record (must exist in step_history after screening)
        val_steps = [
            s for s in cm._step_history
            if s.verification_passed and s.failure_stage is None
            and s.hypothesis_id is not None
            and s.round_num > screening_steps[-1].round_num
        ]
        assert val_steps, "validation step must be in step_history"
        val_hyp_id = val_steps[-1].hypothesis_id
        assert val_hyp_id == screening_hyp_id, (
            f"validation step hypothesis_id {val_hyp_id!r} must match "
            f"screening step hypothesis_id {screening_hyp_id!r}"
        )

    def test_promote_marks_original_hypothesis_as_promoted(self, tmp_path):
        """After PROMOTE, the original screening HypothesisRecord status must be 'promoted'."""
        # Full happy path: screening → validation → frozen → promote
        cm = _campaign(
            tmp_path,
            experiment_protocol=_MockProtocol(results=[
                _make_protocol_result("pass", stage=ExperimentStage.SCREENING, win_rate=0.85),
                _make_protocol_result("pass", stage=ExperimentStage.VALIDATION, win_rate=0.85),
                _make_protocol_result("pass", stage=ExperimentStage.FROZEN, win_rate=0.90),
            ]),
        )
        # Run enough steps to get to PROMOTE
        for _ in range(10):
            result = cm.run_one_step()
            if result.decision == Decision.PROMOTE:
                break

        # Find the original hypothesis_id
        success_steps = [s for s in cm._step_history if s.failure_stage is None and s.hypothesis_id]
        assert success_steps, "must have at least one success step"
        original_hyp_id = success_steps[0].hypothesis_id

        # Check that the hypothesis_store has it as "promoted"
        promoted_records = cm._hyp_store.get_by_status("promoted")
        promoted_ids = [r.hypothesis_id for r in promoted_records]
        assert original_hyp_id in promoted_ids, (
            f"Original hypothesis {original_hyp_id!r} should be marked 'promoted', "
            f"but promoted ids are {promoted_ids}"
        )

    def test_abandon_marks_original_hypothesis_as_rejected(self, tmp_path):
        """After ABANDON via Decision Engine (canary fail), the original hypothesis must be 'rejected'."""
        # Canary failure causes CANARY_FAILED → ABANDON from the decision engine.
        # The hypothesis goes through screening (h_record stored in _branch_current_hypothesis),
        # then gets abandoned.
        cm = _campaign(
            tmp_path,
            experiment_protocol=_MockProtocol(
                results=[_make_protocol_result("pass", win_rate=0.85)],
                canary_pass=False,  # canary fail → ABANDON
            ),
        )
        r = cm.run_one_step()
        assert r.decision == Decision.ABANDON, (
            f"expected ABANDON from canary failure, got {r.decision!r}"
        )

        # The hypothesis that was stored in _branch_current_hypothesis during screening
        # should be marked rejected after ABANDON
        rejected = cm._hyp_store.get_by_status("rejected")
        assert rejected, "abandoned branch's hypothesis should be marked rejected"


# ---------------------------------------------------------------------------
# Eval-only step writes StepRecord (T5)
# ---------------------------------------------------------------------------

class TestEvalStepWritesStepRecord:
    def test_eval_step_writes_step_record(self, tmp_path):
        """Validation step must appear in step_history with verification_passed=True."""
        cm = _campaign(
            tmp_path,
            experiment_protocol=_MockProtocol(results=[
                _make_protocol_result("pass", stage=ExperimentStage.SCREENING, win_rate=0.85),
                _make_protocol_result("pass", stage=ExperimentStage.VALIDATION, win_rate=0.85),
            ]),
        )
        # screening → QUEUE_VALIDATE
        r1 = cm.run_one_step()
        assert r1.decision == Decision.QUEUE_VALIDATE
        steps_after_screen = len(cm._step_history)

        # schedule + validation eval
        cm.run_one_step()  # schedule READY_VALIDATE → VALIDATING
        cm.run_one_step()  # eval step

        new_steps = cm._step_history[steps_after_screen:]
        assert new_steps, "eval step must append to step_history"
        val_steps = [s for s in new_steps if s.verification_passed and s.failure_stage is None]
        assert val_steps, (
            "validation step must have verification_passed=True and failure_stage=None in step_history"
        )


# ---------------------------------------------------------------------------
# Stale reconcile (T6)
# ---------------------------------------------------------------------------

class TestStaleReconcile:
    def test_reconcile_reruns_contract_verification_screening(self, tmp_path):
        """_run_reconcile_step must call validate_patch, vgate.run, and run_experiment."""
        protocol = _MockProtocol(results=[
            _make_protocol_result("pass"),  # screening (step 1)
            _make_protocol_result("pass"),  # re-screening (reconcile)
        ])
        cm = _campaign(tmp_path, experiment_protocol=protocol)

        # Step 1: create branch, do an explore step → stores patch
        r = cm.run_one_step()
        assert r.branch_id is not None
        bid = r.branch_id

        # Manually put branch in STALE state (simulate champion change)
        branch = cm._branch_ctrl.get_branch(bid)
        from scion.core.branch import BranchController
        branch.state = BranchState.STALE

        validate_patch_calls = [0]
        original_validate_patch = cm._contract_gate.validate_patch

        def spy_validate_patch(patch):
            validate_patch_calls[0] += 1
            return original_validate_patch(patch)

        vgate_calls = [0]
        original_vgate_run = cm._vgate.run

        def spy_vgate_run(ws, champ_ws, patch):
            vgate_calls[0] += 1
            return original_vgate_run(ws, champ_ws, patch)

        cm._contract_gate.validate_patch = spy_validate_patch
        cm._vgate.run = spy_vgate_run

        cm.run_one_step()  # should be reconcile

        assert validate_patch_calls[0] >= 1, "reconcile must call validate_patch"
        assert vgate_calls[0] >= 1, "reconcile must call VerificationGate.run"
        assert len(protocol.experiment_calls) >= 2, (
            "reconcile must call run_experiment for re-screening"
        )

    def test_reconcile_fails_to_abandoned_when_rescreen_fails(self, tmp_path):
        """If re-screening fails, the stale branch must be ABANDONED."""
        protocol = _MockProtocol(results=[
            _make_protocol_result("pass"),  # initial screening
            _make_protocol_result("fail", win_rate=0.1),  # reconcile re-screening → fail
        ])
        cm = _campaign(tmp_path, experiment_protocol=protocol)

        # initial explore step
        r = cm.run_one_step()
        bid = r.branch_id

        # Put branch in STALE
        branch = cm._branch_ctrl.get_branch(bid)
        branch.state = BranchState.STALE

        cm.run_one_step()  # reconcile

        final_state = cm._branch_ctrl.get_branch(bid).state
        assert final_state == BranchState.ABANDONED, (
            f"stale branch should be ABANDONED after failed re-screening, "
            f"but state is {final_state.value!r}"
        )


# ---------------------------------------------------------------------------
# Decision=None for early failures (T7)
# ---------------------------------------------------------------------------

class TestContractFailStepRecord:
    def test_contract_fail_step_record_has_no_decision(self, tmp_path):
        """StepRecord.decision must be None (not ABANDON) for contract failures."""
        cm = _campaign(tmp_path)

        # Make validate_hypothesis always fail
        cm._contract_gate.validate_hypothesis = lambda hyp, active, blacklist: ContractResult(
            passed=False, checks=(), failure_reason="forced contract failure"
        )

        cm.run_one_step()

        contract_fail_steps = [
            s for s in cm._step_history
            if s.failure_stage == "hypothesis_contract"
        ]
        assert contract_fail_steps, "should have a hypothesis_contract failure step"
        for step in contract_fail_steps:
            assert step.decision is None, (
                f"StepRecord.decision should be None for contract failure, "
                f"but got {step.decision!r}"
            )
