"""Focused tests split from test_campaign_control_boundaries.py."""

from .campaign_control_boundaries_test_support import *  # noqa: F401,F403
import scion.verification.tests as verification_tests
from scion.problem.preflight import ResearchEnvironmentPreflightError
from scion.verification.gate import VerificationGate


def test_explore_pipeline_contract_reads_current_branch_workspace(
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
                "old_string": "    return value + 1\n",
                "new_string": "    return value + 2\n",
                "test_hint": None,
            },
        ),
    )
    branch = cm._branch_ctrl.create_branch(cm._champion)
    workspace = cm._setup_workspace(branch)
    assert workspace is not None
    (Path(workspace) / helper_path).write_text(helper_source)
    captured_inputs: list[tuple[str | None, dict[str, str]]] = []

    assert cm._explore_step_pipeline.step_history is cm._step_history
    cm._contract_gate.validate_hypothesis = lambda *_args, **_kwargs: ContractResult(
        passed=True,
        checks=(CheckResult("H", True, "light", "ok", 0),),
    )

    def fail_patch_contract(patch, *args, **kwargs):
        captured_inputs.append(
            (
                kwargs.get("base_snapshot_path"),
                dict(kwargs.get("base_file_overrides") or {}),
            )
        )
        return ContractResult(
            passed=False,
            checks=(),
            failure_reason="forced patch contract stop",
        )

    cm._contract_gate.validate_patch = fail_patch_contract

    result = cm._explore_step_pipeline.run(branch)

    assert result.reason == "patch contract rejected"
    assert cm._step_history[-1].failure_stage == "patch_contract"
    assert captured_inputs == [(workspace, {})]


def test_campaign_run_preflights_missing_runtime_dependency_before_proposal(
    tmp_path: Path,
) -> None:
    missing = "scion_missing_campaign_preflight_dependency_987654321"
    cm = _campaign(tmp_path)
    object.__setattr__(
        cm._problem_runtime.spec,
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
    tests_dir = Path(cm._problem_runtime.spec.root_dir) / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_operators.py").write_text("def test_ok(): pass\n")
    cm._vgate = VerificationGate(
        problem_spec=cm._problem_runtime.spec,
        runner=object(),
    )
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




class TestAcceptedBranchCodeHash:
    def test_candidate_hash_becomes_current_only_after_disposition_accepts(
        self,
        tmp_path: Path,
    ) -> None:
        protocol = _MockProtocol(results=[_make_protocol_result("pass")])
        cm = _campaign(
            tmp_path,
            experiment_protocol=protocol,
        )
        observed_during_protocol: list[tuple[str | None, str, str]] = []
        original_run_experiment = protocol.run_experiment

        def observe_candidate(*args, **kwargs):
            candidate_workspace = kwargs.get("candidate_ws")
            if candidate_workspace is None:
                candidate_workspace = args[1]
            branch = next(iter(cm._branch_ctrl._branches.values()))
            observed_during_protocol.append(
                (
                    branch.current_code_hash,
                    cm._branch_workspaces[branch.branch_id],
                    candidate_workspace,
                )
            )
            return original_run_experiment(*args, **kwargs)

        protocol.run_experiment = observe_candidate

        cm.run_one_step()

        assert len(observed_during_protocol) == 1
        current_during_protocol, durable_during_protocol, candidate_workspace = (
            observed_during_protocol[0]
        )
        assert current_during_protocol is None
        assert durable_during_protocol != candidate_workspace
        branch = next(iter(cm._branch_ctrl._branches.values()))
        assert branch.current_code_hash is not None
        durable_workspace = cm._branch_workspaces[branch.branch_id]
        assert cm._materializer.compute_code_hash(durable_workspace) == (
            branch.current_code_hash
        )

    def test_verification_failure_never_writes_current_code_hash(
        self,
        tmp_path: Path,
    ) -> None:
        cm = _campaign(
            tmp_path,
            verification_gate=_AlwaysFailVerificationLight(),
        )
        # Make fix generation also fail so verification definitely fails
        cm._creative.fix_code = MagicMock(return_value=None)

        cm.run_one_step()

        assert cm._branch_ctrl._branches
        assert all(
            branch.current_code_hash is None
            for branch in cm._branch_ctrl._branches.values()
        )
