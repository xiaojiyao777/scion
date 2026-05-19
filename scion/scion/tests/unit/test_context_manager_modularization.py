from __future__ import annotations

import inspect
from pathlib import Path

import scion.proposal.context as context_package
from scion.proposal import context_manager as context_manager_module
from scion.proposal.context import feedback
from scion.proposal.context import problem_adapter
from scion.proposal.context import surfaces
from scion.proposal.context_builders import feedback_memory as feedback_compat
from scion.proposal.context_builders import problem_adapter as problem_adapter_compat
from scion.proposal.context_builders import research_surfaces as surfaces_compat


def test_context_package_coexists_with_context_manager_facade() -> None:
    assert context_package.__name__ == "scion.proposal.context"
    assert hasattr(context_manager_module, "ContextManager")


def test_context_manager_facade_reexports_feedback_builders() -> None:
    assert (
        context_manager_module._filter_hypothesis_prompt_steps
        is feedback._filter_hypothesis_prompt_steps
    )
    assert (
        context_manager_module._build_experiment_history
        is feedback._build_experiment_history
    )
    assert (
        context_manager_module._render_case_feedback
        is feedback._render_case_feedback
    )
    assert (
        context_manager_module._build_champion_baselines
        is feedback._build_champion_baselines
    )


def test_context_builders_remain_compatibility_reexports() -> None:
    assert (
        feedback_compat._build_experiment_history
        is feedback._build_experiment_history
    )
    assert (
        problem_adapter_compat._build_problem_summary
        is problem_adapter._build_problem_summary
    )
    assert (
        surfaces_compat._build_research_surfaces_block
        is surfaces._build_research_surfaces_block
    )


def test_feedback_builder_has_no_problem_package_semantics() -> None:
    source = inspect.getsource(feedback).lower()
    forbidden = (
        "scion.problems",
        "cvrp",
        "warehouse",
        "customer",
        "vehicle",
        "depot",
        "route",
        "capacity",
        "alns",
        "vns",
        "_alnsvnssolver",
    )
    leaked = [term for term in forbidden if term in source]
    assert leaked == []


def test_context_manager_package_has_no_problem_package_semantics() -> None:
    package_root = Path(context_manager_module.__file__).parent
    source = "\n".join(
        path.read_text(encoding="utf-8").lower()
        for path in package_root.glob("*.py")
    )
    forbidden = (
        "scion.problems",
        "cvrp",
        "warehouse",
        "customer",
        "vehicle",
        "depot",
        "route",
        "capacity",
        "alns",
        "vns",
        "_alnsvnssolver",
        "baseline_modules",
        "solver_algorithm",
    )
    leaked = [term for term in forbidden if term in source]
    assert leaked == []
