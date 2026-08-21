from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from scion.config.problem import ProblemSpec, SearchSpace
from scion.core.code_development import CodeDevelopmentEvaluator
from scion.core.code_research_limits import CodeResearchLimits
from scion.core.models import PatchProposal
from scion.runtime.workspace import WorkspaceMaterializer
from scion.verification.development import (
    BubblewrapDevelopmentSandbox,
    DevelopmentSandboxResult,
    DevelopmentSuiteManifest,
    copy_declared_development_files,
    copy_development_suite_closure,
    declared_development_problem_package_paths,
    declared_development_suites,
    declared_development_workspace_paths,
    validate_development_closure_boundary,
)


def _spec(problem_root: Path) -> ProblemSpec:
    return ProblemSpec(
        name="generic_subject",
        root_dir=str(problem_root),
        development_unit_test_path="tests/test_public.py",
        operator_categories=["generic"],
        search_space=SearchSpace(
            editable=["operators/*.py"],
            frozen=["tests/*.py"],
            import_whitelist=[],
        ),
    )


def _patch() -> PatchProposal:
    return PatchProposal(
        file_path="operators/main.py",
        action="modify",
        code_content="def improve(value):\n    return value + 1\n",
    )


def test_real_sandbox_uses_only_public_closure_and_cleans_scratch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    problem_root = tmp_path / "problem"
    (problem_root / "tests").mkdir(parents=True)
    host_sentinel = tmp_path / "heldout-sentinel"
    host_sentinel.write_text("private", encoding="utf-8")
    (problem_root / "tests/test_public.py").write_text(
        "from pathlib import Path\n"
        "from operators.main import improve\n"
        "def test_public():\n"
        "    assert improve(1) == 2\n"
        f"    assert not Path({str(host_sentinel)!r}).exists()\n"
        "    assert not Path('/opt/scion-runtime/scion/problems/cvrp').exists()\n"
        "    try:\n"
        "        Path('/work/source-mutation').write_text('x')\n"
        "    except OSError:\n"
        "        pass\n"
        "    else:\n"
        "        raise AssertionError('sandbox source tree was writable')\n",
        encoding="utf-8",
    )
    spec = _spec(problem_root)
    materializer = WorkspaceMaterializer(
        str(tmp_path / "campaign"), editable_patterns=("operators/*.py",)
    )
    suite = DevelopmentSuiteManifest(
        check_name="D3_unit_tests",
        source_root=str(problem_root),
        test_path="tests/test_public.py",
    )
    evaluator = CodeDevelopmentEvaluator(
        materializer=materializer,
        problem_spec=spec,
        suites=(suite,),
        workspace_paths=(),
        problem_package_paths=(),
        limits=CodeResearchLimits(
            max_test_suite_timeout_sec=10, max_test_total_timeout_sec=10
        ),
    )

    from scion.verification.gate import VerificationGate

    monkeypatch.setattr(
        VerificationGate,
        "run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("formal verification must not run")
        ),
    )
    run = evaluator.evaluate(
        source_corpus={
            "operators/__init__.py": "",
            "operators/main.py": "def improve(value):\n    return value\n",
        },
        patch=_patch(),
        selected_surface=None,
        total_timeout_sec=10.0,
    )

    assert run.outcome == "passed", run.provider_projection()
    assert [check.name for check in run.checks] == [
        "D1_syntax",
        "D1b_undefined_names",
        "D2_interface",
        "D3_unit_tests",
    ]
    candidate_root = tmp_path / "campaign/candidate_workspaces"
    assert list(candidate_root.iterdir()) == []
    assert host_sentinel.read_text(encoding="utf-8") == "private"


def test_real_sandbox_failure_returns_safe_public_diagnostic_only(
    tmp_path: Path,
) -> None:
    problem_root = tmp_path / "problem"
    (problem_root / "tests").mkdir(parents=True)
    (problem_root / "tests/test_public.py").write_text(
        "from operators.main import improve\n"
        "def test_public():\n"
        "    assert improve(1) == 999, 'CHILD_PRIVATE_DIAGNOSTIC'\n",
        encoding="utf-8",
    )
    materializer = WorkspaceMaterializer(
        str(tmp_path / "campaign"), editable_patterns=("operators/*.py",)
    )
    evaluator = CodeDevelopmentEvaluator(
        materializer=materializer,
        problem_spec=_spec(problem_root),
        suites=(
            DevelopmentSuiteManifest(
                check_name="D3_unit_tests",
                source_root=str(problem_root),
                test_path="tests/test_public.py",
            ),
        ),
        workspace_paths=(),
        problem_package_paths=(),
        limits=CodeResearchLimits(
            max_test_suite_timeout_sec=10,
            max_test_total_timeout_sec=10,
        ),
    )

    run = evaluator.evaluate(
        source_corpus={
            "operators/__init__.py": "",
            "operators/main.py": "def improve(value):\n    return value\n",
        },
        patch=_patch(),
        selected_surface=None,
        total_timeout_sec=10.0,
    )

    assert run.outcome == "failed"
    projection = run.provider_projection()
    assert projection["checks"][-1] == {
        "name": "D3_unit_tests",
        "outcome": "failed",
        "reason_code": "pytest_test_failure",
        "test_path": "tests/test_public.py",
    }
    assert "CHILD_PRIVATE_DIAGNOSTIC" not in repr(projection)
    assert str(problem_root) not in repr(projection)
    assert list((tmp_path / "campaign/candidate_workspaces").iterdir()) == []


def test_test_patch_falsifier_hides_framework_and_leaves_no_host_residue(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    problem_root = tmp_path / "problem"
    (problem_root / "tests").mkdir(parents=True)
    (problem_root / "tests/test_public.py").write_text(
        "from pathlib import Path\n"
        "def test_public():\n"
        "    assert not Path('/work/.scion-development-probe').exists()\n",
        encoding="utf-8",
    )
    framework_root = tmp_path / "host-framework"
    framework_sentinel = framework_root / "core/host_only_sentinel.py"
    framework_sentinel.parent.mkdir(parents=True)
    framework_sentinel.write_text("HOST_FRAMEWORK_SECRET = True\n", encoding="utf-8")
    (framework_root / "problems").mkdir()
    (framework_root / "tests").mkdir()
    host_sentinel = tmp_path / "host-only-sentinel"
    host_sentinel.write_text("HOST_ONLY_SECRET\n", encoding="utf-8")
    materializer = WorkspaceMaterializer(
        str(tmp_path / "campaign"), editable_patterns=("operators/*.py",)
    )

    class InspectingSandbox(BubblewrapDevelopmentSandbox):
        def run_pytest(self, *, workspace: str, **kwargs):
            assert not (Path(workspace) / ".scion-development-probe").exists()
            return super().run_pytest(workspace=workspace, **kwargs)

    evaluator = CodeDevelopmentEvaluator(
        materializer=materializer,
        problem_spec=_spec(problem_root),
        suites=(
            DevelopmentSuiteManifest(
                check_name="D3_unit_tests",
                source_root=str(problem_root),
                test_path="tests/test_public.py",
            ),
        ),
        workspace_paths=(),
        problem_package_paths=(),
        limits=CodeResearchLimits(),
        sandbox=InspectingSandbox(framework_root=framework_root),
    )

    from scion.contract.gate import ContractGate
    from scion.verification.gate import VerificationGate

    def formal_gate_called(*_args, **_kwargs):
        raise AssertionError("formal gates must not run during a development probe")

    monkeypatch.setattr(ContractGate, "validate_patch", formal_gate_called)
    monkeypatch.setattr(VerificationGate, "run", formal_gate_called)
    run = evaluator.evaluate(
        source_corpus={
            "operators/__init__.py": "",
            "operators/main.py": "def improve(value):\n    return value\n",
        },
        patch=_patch(),
        selected_surface=None,
        falsifier_source=(
            "from pathlib import Path\n"
            "from operators.main import improve\n"
            "def test_bounded_hint():\n"
            "    assert improve(1) == 2\n"
            "    assert not Path('/work/tests/test_public.py').exists()\n"
            "    assert not Path("
            "'/opt/scion-runtime/scion/core/host_only_sentinel.py').exists()\n"
            f"    assert not Path({str(host_sentinel)!r}).exists()\n"
        ),
        total_timeout_sec=10.0,
    )

    assert run.outcome == "passed", run.provider_projection()
    assert run.falsifier_outcome == "passed"
    assert "HOST" not in repr(run.provider_projection())
    assert list((tmp_path / "campaign/candidate_workspaces").iterdir()) == []
    assert framework_sentinel.read_text(encoding="utf-8").startswith("HOST_")
    assert host_sentinel.read_text(encoding="utf-8").startswith("HOST_")


def test_invalid_falsifier_is_inconclusive_but_host_checks_still_run(
    tmp_path: Path,
) -> None:
    problem_root = tmp_path / "problem"
    (problem_root / "tests").mkdir(parents=True)
    (problem_root / "tests/test_public.py").write_text(
        "def test_public(): pass\n", encoding="utf-8"
    )
    evaluator = CodeDevelopmentEvaluator(
        materializer=WorkspaceMaterializer(
            str(tmp_path / "campaign"), editable_patterns=("operators/*.py",)
        ),
        problem_spec=_spec(problem_root),
        suites=(
            DevelopmentSuiteManifest(
                check_name="D3_unit_tests",
                source_root=str(problem_root),
                test_path="tests/test_public.py",
            ),
        ),
        workspace_paths=(),
        problem_package_paths=(),
        limits=CodeResearchLimits(),
        sandbox=BubblewrapDevelopmentSandbox(),
    )

    run = evaluator.evaluate(
        source_corpus={"operators/main.py": "def improve(value):\n    return value\n"},
        patch=_patch(),
        selected_surface=None,
        falsifier_source="def test_broken(: pass",
        total_timeout_sec=10.0,
    )

    assert run.outcome == "passed"
    assert run.falsifier_outcome == "inconclusive"
    assert list((tmp_path / "campaign/candidate_workspaces").iterdir()) == []


class _RecordingSandbox:
    available = True

    def __init__(self, probe_outcome: str = "passed") -> None:
        self.probe_outcome = probe_outcome
        self.probe_calls = 0
        self.host_calls = 0

    def run_probe(self, **_kwargs):
        self.probe_calls += 1
        return self.probe_outcome

    def run_pytest(self, *, workspace: str, **_kwargs):
        self.host_calls += 1
        assert not (Path(workspace) / ".scion-development-probe").exists()
        return DevelopmentSandboxResult(outcome="passed")


def test_falsifier_without_copy_capacity_is_unavailable_and_host_runs(
    tmp_path: Path,
) -> None:
    problem_root = tmp_path / "problem"
    (problem_root / "tests").mkdir(parents=True)
    (problem_root / "tests/test_public.py").write_text(
        "def test_public(): pass\n", encoding="utf-8"
    )
    sandbox = _RecordingSandbox()
    evaluator = CodeDevelopmentEvaluator(
        materializer=WorkspaceMaterializer(
            str(tmp_path / "campaign"), editable_patterns=("operators/*.py",)
        ),
        problem_spec=_spec(problem_root),
        suites=(
            DevelopmentSuiteManifest(
                check_name="D3_unit_tests",
                source_root=str(problem_root),
                test_path="tests/test_public.py",
            ),
        ),
        workspace_paths=(),
        problem_package_paths=(),
        limits=CodeResearchLimits(max_test_copy_bytes=1_000),
        sandbox=sandbox,
    )
    run = evaluator.evaluate(
        source_corpus={"operators/main.py": "def improve(value):\n    return value\n"},
        patch=_patch(),
        selected_surface=None,
        falsifier_source="def test_hint():\n    assert True\n" + "#" * 1_000,
        total_timeout_sec=10.0,
    )

    assert run.outcome == "passed"
    assert run.falsifier_outcome == "unavailable"
    assert sandbox.probe_calls == 0
    assert sandbox.host_calls == 1
    assert list((tmp_path / "campaign/candidate_workspaces").iterdir()) == []


def test_falsifier_copy_charge_is_not_refunded_before_host_copy(
    tmp_path: Path,
) -> None:
    problem_root = tmp_path / "problem"
    (problem_root / "tests").mkdir(parents=True)
    (problem_root / "tests/test_public.py").write_text(
        "def test_public(): pass\n", encoding="utf-8"
    )
    sandbox = _RecordingSandbox()
    evaluator = CodeDevelopmentEvaluator(
        materializer=WorkspaceMaterializer(
            str(tmp_path / "campaign"), editable_patterns=("operators/*.py",)
        ),
        problem_spec=_spec(problem_root),
        suites=(
            DevelopmentSuiteManifest(
                check_name="D3_unit_tests",
                source_root=str(problem_root),
                test_path="tests/test_public.py",
            ),
        ),
        workspace_paths=(),
        problem_package_paths=(),
        limits=CodeResearchLimits(max_test_copy_bytes=1_000),
        sandbox=sandbox,
    )

    run = evaluator.evaluate(
        source_corpus={
            "operators/main.py": "def improve(value):\n    return value\n" + "#" * 920
        },
        patch=_patch(),
        selected_surface=None,
        falsifier_source="def test_hint(): assert True",
        total_timeout_sec=10.0,
    )

    assert run.outcome == "preflight_rejected"
    assert sandbox.probe_calls == 1
    assert sandbox.host_calls == 0


@pytest.mark.parametrize(
    "unsafe_source",
    [
        (
            "import subprocess\n"
            "def improve(value):\n"
            "    subprocess.run(['true'])\n"
            "    return value\n"
        ),
        "import definitely_not_whitelisted\ndef improve(value):\n    return value\n",
    ],
)
def test_unsafe_patch_never_dispatches_falsifier_or_formal_gates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    unsafe_source: str,
) -> None:
    problem_root = tmp_path / "problem"
    (problem_root / "tests").mkdir(parents=True)
    (problem_root / "tests/test_public.py").write_text(
        "def test_public(): pass\n", encoding="utf-8"
    )
    sandbox = _RecordingSandbox()
    evaluator = CodeDevelopmentEvaluator(
        materializer=WorkspaceMaterializer(
            str(tmp_path / "campaign"), editable_patterns=("operators/*.py",)
        ),
        problem_spec=_spec(problem_root),
        suites=(
            DevelopmentSuiteManifest(
                check_name="D3_unit_tests",
                source_root=str(problem_root),
                test_path="tests/test_public.py",
            ),
        ),
        workspace_paths=(),
        problem_package_paths=(),
        limits=CodeResearchLimits(),
        sandbox=sandbox,
    )
    from scion.contract.gate import ContractGate
    from scion.verification.gate import VerificationGate

    def formal_gate_called(*_args, **_kwargs):
        raise AssertionError("formal gates must not run during development")

    monkeypatch.setattr(ContractGate, "validate_patch", formal_gate_called)
    monkeypatch.setattr(VerificationGate, "run", formal_gate_called)
    run = evaluator.evaluate(
        source_corpus={"operators/main.py": "def improve(value):\n    return value\n"},
        patch=PatchProposal(
            file_path="operators/main.py",
            action="modify",
            code_content=unsafe_source,
        ),
        selected_surface=None,
        falsifier_source="def test_hint(): assert True",
        total_timeout_sec=10.0,
    )

    assert run.outcome == "preflight_rejected"
    assert sandbox.probe_calls == 0
    assert sandbox.host_calls == 0


def test_reserved_falsifier_suite_path_fails_before_dispatch(tmp_path: Path) -> None:
    problem_root = tmp_path / "problem"
    reserved = problem_root / ".scion-development-probe/test_probe.py"
    reserved.parent.mkdir(parents=True)
    reserved.write_text("def test_public(): pass\n", encoding="utf-8")
    sandbox = _RecordingSandbox()
    evaluator = CodeDevelopmentEvaluator(
        materializer=WorkspaceMaterializer(
            str(tmp_path / "campaign"), editable_patterns=("operators/*.py",)
        ),
        problem_spec=_spec(problem_root),
        suites=(
            DevelopmentSuiteManifest(
                check_name="D3_unit_tests",
                source_root=str(problem_root),
                test_path=".scion-development-probe/test_probe.py",
            ),
        ),
        workspace_paths=(),
        problem_package_paths=(),
        limits=CodeResearchLimits(),
        sandbox=sandbox,
    )

    run = evaluator.evaluate(
        source_corpus={"operators/main.py": "def improve(value):\n    return value\n"},
        patch=_patch(),
        selected_surface=None,
        falsifier_source="def test_hint(): assert True",
        total_timeout_sec=10.0,
    )

    assert run.outcome == "preflight_rejected"
    assert sandbox.probe_calls == 0
    assert sandbox.host_calls == 0


def test_manifest_rejects_absolute_traversal_and_symlink(tmp_path: Path) -> None:
    problem_root = tmp_path / "problem"
    (problem_root / "tests").mkdir(parents=True)
    outside = tmp_path / "outside.py"
    outside.write_text("def test_outside(): pass\n", encoding="utf-8")
    (problem_root / "tests/link.py").symlink_to(outside)
    spec = _spec(problem_root)
    object.__setattr__(spec, "development_unit_test_path", "tests/link.py")

    with pytest.raises(ValueError, match="symlink"):
        declared_development_suites(spec)

    object.__setattr__(spec, "development_unit_test_path", "../outside.py")
    with pytest.raises(ValueError):
        declared_development_suites(spec)


def test_formal_test_paths_never_fall_back_into_development() -> None:
    spec = ProblemSpec(
        name="generic_subject",
        root_dir="/does/not/need/to/exist",
        unit_test_path="tests/formal_unit.py",
        regression_test_path="tests/formal_regression.py",
        operator_categories=["generic"],
        search_space=SearchSpace(editable=["*.py"], frozen=[], import_whitelist=[]),
    )

    assert declared_development_suites(spec) == ()


def test_development_closure_rejects_relative_protocol_case_alias(
    tmp_path: Path,
) -> None:
    problem_root = tmp_path / "problem"
    (problem_root / "tests").mkdir(parents=True)
    (problem_root / "data").mkdir()
    (problem_root / "tests/test_public.py").write_text(
        "def test_public(): pass\n",
        encoding="utf-8",
    )
    (problem_root / "data/private.json").write_text("{}\n", encoding="utf-8")
    spec = _spec(problem_root)
    object.__setattr__(
        spec,
        "development_unit_test_support_paths",
        ["data/private.json"],
    )
    suites = declared_development_suites(spec)

    with pytest.raises(ValueError, match="overlaps Protocol/canary"):
        validate_development_closure_boundary(
            problem_spec=spec,
            suites=suites,
            workspace_paths=(),
            problem_package_paths=(),
            split_manifest=SimpleNamespace(
                screening=(),
                validation=("data/private.json",),
                frozen=(),
                canary=(),
                safe_data_roots=(),
            ),
            champion_root=str(problem_root),
        )

    with pytest.raises(ValueError, match="overlaps Protocol/canary"):
        validate_development_closure_boundary(
            problem_spec=spec,
            suites=suites,
            workspace_paths=(),
            problem_package_paths=(),
            split_manifest=SimpleNamespace(
                screening=(),
                validation=(str(problem_root / "data/private.json"),),
                frozen=(),
                canary=(),
                safe_data_roots=(),
            ),
            champion_root=str(problem_root),
        )


def test_sandbox_is_fail_closed_when_bwrap_is_missing(tmp_path: Path) -> None:
    sandbox = BubblewrapDevelopmentSandbox(bwrap_path=tmp_path / "missing-bwrap")

    assert sandbox.available is False


def test_suite_support_cannot_overwrite_frozen_source_corpus(tmp_path: Path) -> None:
    problem_root = tmp_path / "problem"
    (problem_root / "tests").mkdir(parents=True)
    (problem_root / "operators").mkdir()
    (problem_root / "tests/test_public.py").write_text(
        "def test_public(): pass\n",
        encoding="utf-8",
    )
    (problem_root / "operators/helper.py").write_text(
        "HOST_BASELINE = True\n",
        encoding="utf-8",
    )
    materializer = WorkspaceMaterializer(
        str(tmp_path / "campaign"),
        editable_patterns=("operators/*.py",),
    )
    evaluator = CodeDevelopmentEvaluator(
        materializer=materializer,
        problem_spec=_spec(problem_root),
        suites=(
            DevelopmentSuiteManifest(
                check_name="D3_unit_tests",
                source_root=str(problem_root),
                test_path="tests/test_public.py",
                support_paths=("operators/helper.py",),
            ),
        ),
        workspace_paths=(),
        problem_package_paths=(),
        limits=CodeResearchLimits(),
    )

    run = evaluator.evaluate(
        source_corpus={
            "operators/main.py": "def improve(value):\n    return value\n",
            "operators/helper.py": "FROZEN_RESEARCH_SOURCE = True\n",
        },
        patch=_patch(),
        selected_surface=None,
        total_timeout_sec=10.0,
    )

    assert run.outcome == "preflight_rejected"
    assert list((tmp_path / "campaign/candidate_workspaces").iterdir()) == []


def test_provider_projection_contains_only_enum_checks_and_counts() -> None:
    from scion.verification.development import (
        DevelopmentCheckObservation,
        DevelopmentCheckRun,
    )

    projection = DevelopmentCheckRun(
        outcome="failed",
        checks=(DevelopmentCheckObservation(name="D3_unit_tests", outcome="failed"),),
    ).provider_projection()

    assert projection == {
        "outcome": "failed",
        "checks": [{"name": "D3_unit_tests", "outcome": "failed"}],
        "counts": {"total": 1, "passed": 0, "failed": 1},
    }


def test_provider_projection_exposes_only_safe_actionable_test_diagnostics() -> None:
    from scion.verification.development import (
        DevelopmentCheckObservation,
        DevelopmentCheckRun,
    )

    projection = DevelopmentCheckRun(
        outcome="failed",
        checks=(
            DevelopmentCheckObservation(
                name="D4_regression_tests",
                outcome="failed",
                reason_code="pytest_test_failure",
                test_path="tests/test_public_regression.py",
            ),
        ),
    ).provider_projection()

    assert projection == {
        "outcome": "failed",
        "checks": [
            {
                "name": "D4_regression_tests",
                "outcome": "failed",
                "reason_code": "pytest_test_failure",
                "test_path": "tests/test_public_regression.py",
            }
        ],
        "counts": {"total": 1, "passed": 0, "failed": 1},
    }
    assert "stdout" not in repr(projection)
    assert "traceback" not in repr(projection)


def test_cvrp_declares_exact_public_development_closure() -> None:
    from scion.problem.bridge import load_problem_spec_v1_from_yaml

    root = Path(__file__).resolve().parents[2] / "problems/cvrp"
    spec = load_problem_spec_v1_from_yaml(root / "problem-v1.yaml")

    suites = declared_development_suites(spec)
    workspace_paths = declared_development_workspace_paths(spec)
    runtime_paths = declared_development_problem_package_paths(spec)

    assert [suite.check_name for suite in suites] == [
        "D3_unit_tests",
        "D4_regression_tests",
    ]
    assert suites[1].support_paths == ("data/tiny_development.json",)
    assert workspace_paths == (
        "policies/__init__.py",
        "policies/baseline_modules/__init__.py",
    )
    assert "data/tiny_canary.json" not in {
        path for suite in suites for path in suite.declared_paths
    }
    development_bytes = (root / "data/tiny_development.json").read_bytes()
    formal_canary_bytes = (root / "data/tiny_canary.json").read_bytes()
    assert development_bytes != formal_canary_bytes
    assert b"tiny_canary" not in development_bytes
    assert "solver_runtime/algorithm_runtime.py" in runtime_paths
    assert not any(path.startswith("controlled/") for path in runtime_paths)
    assert not any(path.startswith("formal/") for path in runtime_paths)


@pytest.mark.parametrize("problem_tree_parent", (2, 3))
def test_both_warehouse_specs_declare_public_development_closure(
    problem_tree_parent: int,
) -> None:
    from scion.problem.bridge import load_problem_spec_v1_from_yaml
    from scion.verification.development import declared_development_workspace_paths

    package_root = (
        Path(__file__).resolve().parents[problem_tree_parent]
        / "problems/warehouse_delivery"
    )
    spec = load_problem_spec_v1_from_yaml(package_root / "problem-v1.yaml")
    suites = declared_development_suites(spec)
    workspace_paths = declared_development_workspace_paths(spec)

    assert [suite.check_name for suite in suites] == [
        "D3_unit_tests",
        "D4_regression_tests",
    ]
    assert suites[1].test_path == "tests/test_development_solver.py"
    assert suites[1].support_paths == ("data/instance_development.json",)
    assert "data/instance_small_1.json" not in {
        path for suite in suites for path in suite.declared_paths
    }
    assert workspace_paths == (
        "config.py",
        "greedy_init.py",
        "models.py",
        "oracle.py",
        "pool.py",
        "solver.py",
        "vns.py",
        "operators/__init__.py",
        "operators/base.py",
    )
    assert declared_development_problem_package_paths(spec) == ()


def test_cvrp_development_scratch_excludes_formal_canary(tmp_path: Path) -> None:
    from scion.problem.bridge import load_problem_spec_v1_from_yaml

    root = Path(__file__).resolve().parents[2] / "problems/cvrp"
    spec = load_problem_spec_v1_from_yaml(root / "problem-v1.yaml")
    suites = declared_development_suites(spec)
    runtime_paths = declared_development_problem_package_paths(spec)
    materializer = WorkspaceMaterializer(str(tmp_path / "campaign"))
    scratch = materializer.create_empty_candidate_workspace()
    try:
        problems_root = Path(scratch) / ".scion-development-problems/cvrp"
        problems_root.mkdir(parents=True)
        copy_declared_development_files(
            source_root=root,
            paths=runtime_paths,
            destination_root=problems_root,
            max_files=64,
            max_bytes=5_000_000,
        )
        copy_development_suite_closure(
            suites,
            scratch,
            max_files=64,
            max_bytes=5_000_000,
        )

        formal_bytes = (root / "data/tiny_canary.json").read_bytes()
        assert not (Path(scratch) / "data/tiny_canary.json").exists()
        assert all(
            path.read_bytes() != formal_bytes
            for path in Path(scratch).rglob("*")
            if path.is_file()
        )
    finally:
        materializer.cleanup_candidate_workspace(scratch)


def test_real_cvrp_public_development_evaluator_passes_without_formal_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scion.core.research_surface_index import editable_patterns
    from scion.problem.bridge import (
        legacy_problem_spec_from_v1,
        load_problem_spec_v1_from_yaml,
    )
    from scion.verification.gate import VerificationGate

    root = Path(__file__).resolve().parents[2] / "problems/cvrp"
    spec_v1 = load_problem_spec_v1_from_yaml(root / "problem-v1.yaml")
    spec = legacy_problem_spec_from_v1(spec_v1)
    materializer = WorkspaceMaterializer(
        str(tmp_path / "campaign"),
        editable_patterns=editable_patterns(spec),
    )
    evaluator = CodeDevelopmentEvaluator(
        materializer=materializer,
        problem_spec=spec,
        suites=declared_development_suites(spec),
        workspace_paths=declared_development_workspace_paths(spec),
        problem_package_paths=declared_development_problem_package_paths(spec),
        limits=CodeResearchLimits(
            max_test_suite_timeout_sec=30,
            max_test_total_timeout_sec=60,
        ),
        operator_execute_signature=spec_v1.operator_interface.execute_signature,
    )
    source_corpus = {
        path.relative_to(root).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted((root / "policies").rglob("*.py"))
        if path.name != "__init__.py"
    }
    target = "policies/baseline_algorithm.py"
    formal_calls: list[int] = []
    monkeypatch.setattr(
        VerificationGate,
        "run",
        lambda *_args, **_kwargs: formal_calls.append(1),
    )

    run = evaluator.evaluate(
        source_corpus=source_corpus,
        patch=PatchProposal(
            file_path=target,
            action="modify",
            code_content=source_corpus[target],
        ),
        selected_surface="solver_design",
        total_timeout_sec=60.0,
    )

    assert run.outcome == "passed"
    assert [check.name for check in run.checks] == [
        "D1_syntax",
        "D1b_undefined_names",
        "D2_interface",
        "D3_unit_tests",
        "D4_regression_tests",
    ]
    assert formal_calls == []
    assert list((tmp_path / "campaign/candidate_workspaces").iterdir()) == []
