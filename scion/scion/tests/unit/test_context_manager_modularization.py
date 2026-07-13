from __future__ import annotations

from pathlib import Path

import scion.proposal.context as context_package
from scion.proposal import context_manager as context_manager_module


def test_context_package_coexists_with_context_manager_facade() -> None:
    assert context_package.__name__ == "scion.proposal.context"
    assert hasattr(context_manager_module, "ContextManager")


def test_context_manager_facade_exports_only_direct_manager() -> None:
    assert context_manager_module.__all__ == ["ContextManager"]


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
