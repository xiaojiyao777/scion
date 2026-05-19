"""Focused tests split from test_campaign_control_boundaries.py."""

from .campaign_control_boundaries_test_support import *  # noqa: F401,F403

def test_campaign_run_preflights_missing_runtime_dependency_before_proposal(
    tmp_path: Path,
) -> None:
    missing = "scion_missing_campaign_preflight_dependency_987654321"
    cm = _campaign(tmp_path)
    object.__setattr__(
        cm._spec,
        "runtime_dependencies",
        RuntimeDependencySpec(required_python_modules=[missing]),
    )

    with pytest.raises(RuntimeDependencyPreflightError) as excinfo:
        cm.run(max_rounds=1)

    assert missing in str(excinfo.value)
    assert cm._round_num == 0
    assert cm._step_history == []


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

        validate_patch_calls: List[tuple[Any, Any]] = []
        original_validate = cm._contract_gate.validate_patch

        def spy_validate_patch(patch, *args, **kwargs):
            validate_patch_calls.append((patch, kwargs.get("approved_hypothesis")))
            return original_validate(patch, *args, **kwargs)

        cm._contract_gate.validate_patch = spy_validate_patch
        cm.run_one_step()
        # validate_patch called at least twice: once for original patch, once for fix patch
        assert len(validate_patch_calls) >= 2, (
            "fix patch should also be validated by ContractGate, "
            f"but validate_patch was only called {len(validate_patch_calls)} times"
        )
        assert all(
            approved_hypothesis is not None
            for _, approved_hypothesis in validate_patch_calls[:2]
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

        def fail_on_fix_validate(patch, *args, **kwargs):
            call_count[0] += 1
            if call_count[0] >= 2:
                return ContractResult(passed=False, checks=(), failure_reason="fix rejected")
            return original_validate(patch, *args, **kwargs)

        cm._contract_gate.validate_patch = fail_on_fix_validate
        cm.run_one_step()
        # apply_patch should only have been called ONCE (for the original patch),
        # not a second time for the rejected fix patch
        assert len(apply_calls) == 1, (
            f"fix patch must not be applied when ContractGate rejects it, "
            f"but apply_patch was called {len(apply_calls)} times"
        )


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

        def spy_validate_hypothesis(hyp, active, blacklist, rejected_hypotheses=None, current_champion_version=0):
            validate_hyp_calls[0] += 1
            return original_validate_hyp(hyp, active, blacklist, rejected_hypotheses=rejected_hypotheses,
                                         current_champion_version=current_champion_version)

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
