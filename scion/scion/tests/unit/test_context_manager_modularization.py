from __future__ import annotations

import inspect

from scion.proposal import context_manager as context_manager_module
from scion.proposal.context_builders import feedback_memory


def test_context_manager_facade_reexports_feedback_memory_builders() -> None:
    assert (
        context_manager_module._filter_hypothesis_prompt_steps
        is feedback_memory._filter_hypothesis_prompt_steps
    )
    assert (
        context_manager_module._build_experiment_history
        is feedback_memory._build_experiment_history
    )
    assert (
        context_manager_module._render_case_feedback
        is feedback_memory._render_case_feedback
    )
    assert (
        context_manager_module._build_champion_baselines
        is feedback_memory._build_champion_baselines
    )


def test_feedback_memory_builder_has_no_problem_package_semantics() -> None:
    source = inspect.getsource(feedback_memory).lower()
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
