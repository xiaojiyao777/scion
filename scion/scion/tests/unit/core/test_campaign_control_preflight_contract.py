"""Focused tests split from test_campaign_control_boundaries.py."""

from .campaign_control_boundaries_test_support import *  # noqa: F401,F403
import scion.verification.tests as verification_tests
from scion.verification.gate import VerificationGate


def test_explore_pipeline_production_wiring_uses_step_history_base_overrides(
    tmp_path: Path,
) -> None:
    cm = _campaign(tmp_path)
    branch = cm._branch_ctrl.create_branch(cm._champion)
    helper_path = "operators/branch_helper.py"
    helper_source = "def branch_helper(value):\n    return value + 1\n"
    cm._step_history.append(
        StepRecord(
            round_num=1,
            branch_id=branch.branch_id,
            hypothesis=HypothesisProposal(
                hypothesis_text="Create a generic branch helper.",
                change_locus="local_search",
                action="create_new",
                target_file=helper_path,
            ),
            patch=PatchProposal(
                file_path=helper_path,
                action="create",
                code_content=helper_source,
            ),
            contract_passed=True,
            verification_passed=True,
            protocol_result=None,
            decision=None,
            failure_stage=None,
            failure_detail=None,
        )
    )
    followup_hypothesis = HypothesisProposal(
        hypothesis_text="Refine the same helper on this branch.",
        change_locus="local_search",
        action="modify",
        target_file=helper_path,
    )
    followup_record = HypothesisRecord(
        hypothesis_id="followup-hyp",
        branch_id=branch.branch_id,
        change_locus=followup_hypothesis.change_locus,
        action=followup_hypothesis.action,
        status="active",
        target_file=helper_path,
        hypothesis_text=followup_hypothesis.hypothesis_text,
    )
    followup_patch = PatchProposal(
        file_path=helper_path,
        action="modify",
        code_content="def branch_helper(value):\n    return value + 2\n",
    )
    captured_overrides: list[dict[str, str]] = []

    assert cm._explore_step_pipeline.step_history is cm._step_history
    cm._explore_step_pipeline.generate_hypothesis = lambda _branch: (
        followup_hypothesis,
        followup_record,
    )
    cm._hyp_store.save(followup_record)
    cm._explore_step_pipeline.generate_code = (
        lambda _branch, _hypothesis: followup_patch
    )
    cm._contract_gate.validate_hypothesis = lambda *_args, **_kwargs: ContractResult(
        passed=True,
        checks=(CheckResult("H", True, "light", "ok", 0),),
    )

    def fail_patch_contract(patch, *args, **kwargs):
        captured_overrides.append(dict(kwargs.get("base_file_overrides") or {}))
        return ContractResult(
            passed=False,
            checks=(),
            failure_reason="forced patch contract stop",
        )

    cm._contract_gate.validate_patch = fail_patch_contract

    result = cm._explore_step_pipeline.run(branch)

    assert result.reason == "patch contract rejected"
    assert cm._step_history[-1].failure_stage == "patch_contract"
    assert captured_overrides
    assert captured_overrides[0][helper_path] == helper_source


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
        cm.run(requested_rounds=1)

    assert missing in str(excinfo.value)
    assert cm._round_num == 0
    assert cm._step_history == []


def test_campaign_run_preflights_missing_verification_pytest_before_proposal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cm = _campaign(tmp_path)
    tests_dir = Path(cm._spec.root_dir) / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_operators.py").write_text("def test_ok(): pass\n")
    cm._vgate = VerificationGate(problem_spec=cm._spec, runner=object())
    monkeypatch.setattr(
        verification_tests.importlib.util,
        "find_spec",
        lambda module_name: None if module_name == "pytest" else object(),
    )

    with pytest.raises(RuntimeDependencyPreflightError) as excinfo:
        cm.run(requested_rounds=1)

    assert "pytest" in str(excinfo.value)
    assert "verification runner" in str(excinfo.value)
    assert cm._round_num == 0
    assert cm._step_history == []




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
