"""Problem adapter hook helpers for proposal context assembly."""

from __future__ import annotations

import os
from typing import Any, Optional

from scion.config.problem import ProblemSpec
from scion.proposal.context.surfaces import (
    _build_research_surface_interface_spec,
    _find_research_surface,
    _get_research_surfaces,
)


def _get_adapter_problem_spec(adapter) -> Any:
    """Return optional ProblemSpecV1 exposed by an adapter."""
    if adapter is None:
        return None
    spec = getattr(adapter, "spec", None)
    if spec is not None:
        return spec
    return getattr(adapter, "_spec", None)


def _build_problem_summary(spec: ProblemSpec, *, adapter=None) -> str:
    """Build a structured summary of the problem specification.

    Delegates to adapter.render_problem_summary() when an adapter is available.
    Falls back to a generic minimal summary for legacy ProblemSpec without
    adapter.
    """
    if adapter is not None and hasattr(adapter, 'render_problem_summary'):
        return adapter.render_problem_summary()
    lines = [f"Name: {spec.name}"]
    if spec.description:
        lines.append(f"Description: {spec.description}")
    lines += [
        f"Research loci: {', '.join(spec.operator_categories)}",
        f"Editable files: {', '.join(spec.search_space.editable)}",
        f"Frozen files (do not modify): {', '.join(spec.search_space.frozen)}",
    ]
    return "\n".join(lines)


def _build_problem_object(*, adapter=None) -> str:
    """Render the problem-owned object model through the adapter boundary."""
    if adapter is not None and hasattr(adapter, "render_problem_object"):
        return str(adapter.render_problem_object())
    return ""


def _build_solver_mechanics(*, adapter=None) -> str:
    """Render problem-specific solver mechanics through the adapter boundary."""
    if adapter is not None and hasattr(adapter, "render_solver_mechanics"):
        return adapter.render_solver_mechanics()
    return ""


def _build_operator_interface_spec(
    spec: ProblemSpec,
    *,
    adapter=None,
    surface_name: Optional[str] = None,
) -> str:
    """Build the active research-surface interface specification.

    Delegates to adapter.render_operator_interface() when an adapter is
    available. Falls back to reading operators/base.py for legacy ProblemSpec
    without adapter.
    """
    if (
        adapter is not None
        and surface_name
        and hasattr(adapter, "render_research_surface_interface")
    ):
        return adapter.render_research_surface_interface(surface_name)
    surface = (
        _find_research_surface(_get_research_surfaces(spec), surface_name)
        if surface_name
        else None
    )
    if surface is not None and getattr(surface, "kind", "operator") != "operator":
        return _build_research_surface_interface_spec(surface)
    if adapter is not None and hasattr(adapter, "render_operator_interface"):
        return adapter.render_operator_interface()
    base_py_path = os.path.join(spec.root_dir, "operators", "base.py")
    try:
        with open(base_py_path, encoding="utf-8") as fh:
            base_class_src = fh.read()
    except OSError:
        base_class_src = (
            "class Operator(ABC):\n"
            "    @abstractmethod\n"
            "    def execute(self, solution: Solution, rng: Random) -> Solution:\n"
            "        ..."
        )
    return f"### Operator Base Class (from operators/base.py)\n```python\n{base_class_src}\n```"


__all__ = [
    name
    for name in globals()
    if not (name.startswith("__") and name.endswith("__"))
]
