"""Focused tests split from test_campaign_control_boundaries.py."""

from .campaign_control_boundaries_test_support import *  # noqa: F401,F403
import hashlib
from scion.core.models import DecisionFeatures
import scion.verification.tests as verification_tests
from scion.problem.preflight import ResearchEnvironmentPreflightError
from scion.verification.gate import VerificationGate


def test_explore_pipeline_production_wiring_uses_step_history_base_overrides(
    tmp_path: Path,
) -> None:
    helper_path = "operators/branch_helper.py"
    helper_source = "def branch_helper(value):\n    return value + 1\n"
    cm = _campaign(
        tmp_path,
        llm_client=MockLLMClient(
            hypothesis_response={
                "hypothesis_text": "Refine the same helper on this branch.",
                "change_locus": "local_search",
                "action": "modify",
                "target_file": helper_path,
                "predicted_direction": "improve",
                "target_weakness": "helper is conservative",
                "expected_effect": "increase helper response",
                "suggested_weight": 0.3,
            },
            patch_response={
                "file_path": helper_path,
                "action": "modify",
                "edit_intent": "exact_replace",
                "source_digest": hashlib.sha256(
                    helper_source.encode("utf-8")
                ).hexdigest(),
                "old_string": "    return value + 1\n",
                "new_string": "    return value + 2\n",
                "test_hint": None,
            },
        ),
    )
    branch = cm._branch_ctrl.create_branch(cm._champion)
    cm._branch_store.save(branch)
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
            decision=Decision.CONTINUE_EXPLORE,
            failure_stage=None,
            failure_detail=None,
            decision_reason_codes=("SCREENING_UNCLEAR",),
            decision_features_snapshot=DecisionFeatures(
                branch_id=branch.branch_id,
                hypothesis_action="create_new",
                stage="screening",
                contract_passed=True,
                verification_passed=True,
                canary_passed=True,
                n_cases=1,
                win_rate=0.0,
                median_delta=0.0,
                ci_low=0.0,
                ci_high=0.0,
                stale=False,
                recent_failure_codes=(),
                protocol_gate_outcome="unclear",
                protocol_reason_codes=("SCREENING_UNCLEAR",),
            ),
        )
    )
    captured_overrides: list[dict[str, str]] = []

    assert cm._explore_step_pipeline.step_history is cm._step_history
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

    with pytest.raises(ResearchEnvironmentPreflightError) as excinfo:
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

    with pytest.raises(ResearchEnvironmentPreflightError) as excinfo:
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

        # A fresh branch has no accepted branch head yet.  The candidate hash
        # only becomes clean once the formal Decision accepts its staging tree.
        assert candidate_clean_at_apply, "record_candidate_code must be called"
        assert candidate_clean_at_apply[0] is None
        assert clean_after_verify
        assert clean_after_verify[-1] != candidate_clean_at_apply[0]

    def test_verification_fail_preserves_last_clean_hash(self, tmp_path):
        """A verification failure restores the actual clean base workspace hash."""
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
            assert b.last_clean_code_hash is not None
            assert b.current_code_hash == b.last_clean_code_hash
