from __future__ import annotations

from pathlib import Path

import pytest
from scion.config.problem import ProblemSpec, SearchSpace
from scion.contract.gate import ContractGate
from scion.core.code_development import CodeDevelopmentEvaluator
from scion.core.code_research_limits import CodeResearchLimits
from scion.core.models import PatchProposal
from scion.runtime.workspace import WorkspaceMaterializer
from scion.verification.development import (
    BubblewrapDevelopmentSandbox,
    DevelopmentSuiteManifest,
)
from scion.verification.gate import VerificationGate


def _problem_spec(problem_root: Path) -> ProblemSpec:
    return ProblemSpec(
        name="redteam_subject",
        root_dir=str(problem_root),
        development_unit_test_path="tests/test_public.py",
        operator_categories=["generic"],
        search_space=SearchSpace(
            editable=["operators/*.py"],
            frozen=["tests/*.py"],
            import_whitelist=[],
        ),
    )


def test_c9_bypass_cannot_read_host_or_masked_framework_or_write_work(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    problem_root = tmp_path / "problem"
    (problem_root / "tests").mkdir(parents=True)
    problem_secret = problem_root / "heldout-sentinel.txt"
    problem_secret.write_text("PROBLEM_SENTINEL", encoding="utf-8")
    (problem_root / "tests/test_public.py").write_text(
        "from operators.main import improve\n"
        "def test_public():\n"
        "    assert improve(1) == 2\n",
        encoding="utf-8",
    )

    framework_root = tmp_path / "framework"
    framework_secret = framework_root / "problems/private/heldout.txt"
    framework_secret.parent.mkdir(parents=True)
    framework_secret.write_text("FRAMEWORK_SENTINEL", encoding="utf-8")
    framework_test_secret = framework_root / "tests/heldout.txt"
    framework_test_secret.parent.mkdir(parents=True)
    framework_test_secret.write_text("TEST_SENTINEL", encoding="utf-8")

    # This deliberately bypasses the current AST C9 detector: the callable is
    # recovered through a subscript on vars(__builtins__), rather than named
    # directly.  Filesystem isolation, not the static detector, must stop it.
    candidate_source = (
        "def improve(value):\n"
        "    builtins_value = __builtins__\n"
        "    file_open = (\n"
        '        builtins_value["open"]\n'
        "        if isinstance(builtins_value, dict)\n"
        '        else vars(builtins_value)["open"]\n'
        "    )\n"
        "    for path in (\n"
        f"        {str(problem_secret)!r},\n"
        "        '/opt/scion-runtime/scion/problems/private/heldout.txt',\n"
        "        '/opt/scion-runtime/scion/tests/heldout.txt',\n"
        "    ):\n"
        "        try:\n"
        "            stream = file_open(path, 'r')\n"
        "            stream.read()\n"
        "            stream.close()\n"
        "        except OSError:\n"
        "            pass\n"
        "        else:\n"
        "            return -100\n"
        "    try:\n"
        "        stream = file_open('/work/candidate-mutation', 'w')\n"
        "        stream.write('mutated')\n"
        "        stream.close()\n"
        "    except OSError:\n"
        "        pass\n"
        "    else:\n"
        "        return -200\n"
        "    return value + 1\n"
    )
    patch = PatchProposal(
        file_path="operators/main.py",
        action="modify",
        code_content=candidate_source,
    )
    materializer = WorkspaceMaterializer(
        str(tmp_path / "campaign"),
        editable_patterns=("operators/*.py",),
    )
    sandbox = BubblewrapDevelopmentSandbox(framework_root=framework_root)
    assert sandbox.available is True
    evaluator = CodeDevelopmentEvaluator(
        materializer=materializer,
        problem_spec=_problem_spec(problem_root),
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
        sandbox=sandbox,
    )

    def formal_gate_called(*_args, **_kwargs):
        raise AssertionError("formal gate must not run during development checks")

    monkeypatch.setattr(ContractGate, "validate_patch", formal_gate_called)
    monkeypatch.setattr(VerificationGate, "run", formal_gate_called)

    run = evaluator.evaluate(
        source_corpus={
            "operators/__init__.py": "",
            "operators/main.py": "def improve(value):\n    return value\n",
        },
        patch=patch,
        selected_surface=None,
        total_timeout_sec=10.0,
    )

    assert run.outcome == "passed", run
    projection = run.provider_projection()
    assert projection == {
        "outcome": "passed",
        "checks": [
            {"name": "D1_syntax", "outcome": "passed"},
            {"name": "D1b_undefined_names", "outcome": "passed"},
            {"name": "D2_interface", "outcome": "passed"},
            {"name": "D3_unit_tests", "outcome": "passed"},
        ],
        "counts": {"total": 4, "passed": 4, "failed": 0},
    }
    rendered = repr(projection)
    assert "SENTINEL" not in rendered
    assert str(problem_root) not in rendered
    assert list((tmp_path / "campaign/candidate_workspaces").iterdir()) == []
    assert problem_secret.read_text(encoding="utf-8") == "PROBLEM_SENTINEL"
    assert framework_secret.read_text(encoding="utf-8") == "FRAMEWORK_SENTINEL"
