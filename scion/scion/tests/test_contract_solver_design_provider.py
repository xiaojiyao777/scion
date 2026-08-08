from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from scion.contract.gate import ContractGate
from scion.core.models import PatchFileChange, PatchProposal
from scion.problem.bridge import (
    legacy_problem_spec_from_v1,
    load_problem_spec_v1_from_yaml,
)
from scion.problems.cvrp.adapter import CvrpAdapter
from scion.tests.unit.research_surface_helpers import _CVRP_ROOT


def test_contract_gate_has_no_problem_shape_integration_gate() -> None:
    assert not hasattr(ContractGate, "_c9e_solver_design_integration")


def test_missing_problem_policy_provider_does_not_reject_candidate_patch() -> None:
    class Spec:
        search_space = SimpleNamespace(
            editable=("policies/*.py",),
            frozen=(),
            import_whitelist=(),
        )
        research_surfaces = (
            SimpleNamespace(
                name="solver_design",
                kind="solver_design",
                targets=SimpleNamespace(files=("policies/algorithm.py",)),
            ),
        )

    patch = PatchProposal(
        file_path="policies/algorithm.py",
        action="modify",
        code_content=(
            "def solve(instance, rng, time_limit_sec, context):\n"
            "    return None\n"
        ),
    )

    result = ContractGate(Spec()).validate_patch(
        patch,
        selected_surface="solver_design",
    )

    assert result.passed
    assert all(
        check.name not in {"C9e_solver_design_integration", "C9f_active_subject_provider"}
        for check in result.checks
    )


def test_contract_patch_does_not_resolve_problem_owned_gate_provider() -> None:
    factory_calls: list[str] = []

    class Spec:
        search_space = SimpleNamespace(
            editable=("policies/*.py",),
            frozen=(),
            import_whitelist=(),
        )
        research_surfaces = (
            SimpleNamespace(
                name="solver_design",
                kind="solver_design",
                targets=SimpleNamespace(files=("policies/*.py",)),
            ),
        )

        def contract_check_provider(self):
            factory_calls.append("contract_check_provider")
            return object()

    patch = PatchProposal(
        file_path="policies/algorithm.py",
        action="modify",
        code_content=(
            "def solve(instance, rng, time_limit_sec, context):\n"
            "    return None\n"
        ),
        additional_changes=(
            PatchFileChange(
                file_path="policies/helper.py",
                action="create",
                code_content="def helper():\n    return 1\n",
            ),
        ),
    )

    result = ContractGate(Spec()).validate_patch(
        patch,
        selected_surface="solver_design",
    )

    assert result.passed
    assert factory_calls == []


def test_cvrp_adapter_exposes_prompt_guidance_without_dead_gate_providers() -> None:
    spec_v1 = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    adapter = CvrpAdapter(spec_v1)

    provider = adapter.solver_design_prompt_provider()

    assert provider.__class__.__module__ == (
        "scion.problems.cvrp.solver_design_provider"
    )
    assert not hasattr(adapter, "contract_check_provider")
    assert not hasattr(adapter, "active_subject_policy_provider")
    assert not hasattr(adapter, "preview_research_surface_patch")


def test_context_baseline_prohibition_is_core_contract_not_provider_owned() -> None:
    spec_v1 = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    problem_spec = legacy_problem_spec_from_v1(spec_v1)
    gate = ContractGate(problem_spec)
    patch = PatchProposal(
        file_path="policies/baseline_algorithm.py",
        action="modify",
        code_content=(
            "def solve(instance, rng, time_limit_sec, context):\n"
            "    run = context.baseline\n"
            "    return run(time_limit_sec=time_limit_sec)\n"
        ),
    )

    result = gate.validate_patch(patch, selected_surface="solver_design")

    c9 = next(check for check in result.checks if check.name == "C9_sensitive_api")
    assert not c9.passed
    assert "context.baseline alias" in c9.detail


def test_cvrp_adapter_import_does_not_load_dead_preview_or_contract_modules() -> None:
    project_root = Path(__file__).resolve().parents[2]
    probe = """
import json
import sys
from scion.problems.cvrp.adapter import CvrpAdapter  # noqa: F401
print(json.dumps(sorted(
    name for name in sys.modules
    if name.startswith('scion.problems.cvrp.preview')
    or name.startswith('scion.problems.cvrp.contract_checks')
)))
"""
    completed = subprocess.run(
        (sys.executable, "-c", probe),
        cwd=project_root,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        shell=False,
        check=False,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == []
