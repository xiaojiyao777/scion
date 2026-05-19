"""CVRP ProblemAdapter implementation for Scion v0.4."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

from scion.problem.contracts import CheckReport, LowerBoundEstimate, SolverArtifact
from scion.problem.spec import ProblemSpecV1
from scion.problems.cvrp.cvrplib import load_cvrplib_instance
from scion.problems.cvrp.models import CvrpInstance, CvrpNode, CvrpSolution
from scion.problems.cvrp.solution_checks import (
    _as_solution,
    _extract_reported_objective,
    _normalize_route,
    check_feasibility as _check_feasibility,
    check_solution_consistency as _check_solution_consistency,
    deserialize_solver_output as _deserialize_solver_output,
    recompute_objective as _recompute_objective,
)
from scion.problems.cvrp.surface_schema import (
    _POLICY_PREVIEW_EXEC_TIMEOUT_SEC,
    _POLICY_PREVIEW_TIME_LIMIT_SEC,
)
from scion.problems.cvrp.surface_rendering import (
    render_operator_interface as _render_operator_interface,
    render_problem_object as _render_problem_object,
    render_problem_summary as _render_problem_summary,
    render_research_surface_interface as _render_research_surface_interface,
    render_solver_mechanics as _render_solver_mechanics,
)
from scion.problems.cvrp.preview import common as _preview_common
from scion.problems.cvrp.preview import synthetic as _preview_synthetic
from scion.problems.cvrp.preview.dispatch import (
    preview_research_surface_patch as _preview_research_surface_patch,
)
from scion.problems.cvrp.surface_policy import (
    ACTIVE_RESEARCH_SURFACE_NAMES,
    LEGACY_RESEARCH_SURFACE_NAMES,
    active_research_surfaces as _active_research_surfaces,
    is_active_research_surface as _is_active_research_surface,
    is_legacy_research_surface as _is_legacy_research_surface,
)


class CvrpAdapter:
    def __init__(self, spec: ProblemSpecV1) -> None:
        self._spec = spec

    @property
    def spec(self) -> ProblemSpecV1:
        return self._spec

    def mechanism_novelty_provider(self) -> Any:
        from scion.problems.cvrp.mechanism_novelty import (
            CvrpMechanismNoveltyProvider,
        )

        return CvrpMechanismNoveltyProvider()

    def contract_check_provider(self) -> Any:
        from scion.problems.cvrp.contract_checks import CvrpContractCheckProvider

        return CvrpContractCheckProvider()

    def solver_design_prompt_provider(self) -> Any:
        from scion.problems.cvrp.solver_design_provider import (
            CvrpSolverDesignProvider,
        )

        return CvrpSolverDesignProvider()

    def solver_design_smoke_provider(self) -> Any:
        from scion.problems.cvrp.solver_design_provider import (
            CvrpSolverDesignProvider,
        )

        return CvrpSolverDesignProvider()

    def active_research_surface_names(self) -> tuple[str, ...]:
        return ACTIVE_RESEARCH_SURFACE_NAMES

    def legacy_research_surface_names(self) -> tuple[str, ...]:
        return LEGACY_RESEARCH_SURFACE_NAMES

    def is_active_research_surface(self, surface_name: str) -> bool:
        return _is_active_research_surface(surface_name)

    def is_legacy_research_surface(self, surface_name: str) -> bool:
        return _is_legacy_research_surface(surface_name)

    def active_research_surfaces(self) -> tuple[Any, ...]:
        return _active_research_surfaces(self._spec.research_surfaces or [])

    def stagnation_object_model_markers(self) -> tuple[str, ...]:
        return (
            "_solution",
            "_route",
            "from_public",
            "from_cvrp_solution",
            "from_routes",
            "to_public",
            "cannot be coerced to cvrpsolution",
            "solver_algorithm_errors=",
            "object model",
        )

    def render_problem_summary(self) -> str:
        return _render_problem_summary()

    def render_problem_object(self) -> str:
        return _render_problem_object()

    def render_solver_mechanics(self) -> str:
        return _render_solver_mechanics()

    def render_research_surface_interface(self, surface_name: str) -> str:
        return _render_research_surface_interface(surface_name)

    def render_operator_interface(self) -> str:
        return _render_operator_interface()

    def preview_research_surface_patch(
        self,
        *,
        patch: Any,
        surface: Any | None = None,
    ) -> Mapping[str, Any]:
        _preview_common._POLICY_PREVIEW_TIME_LIMIT_SEC = (
            _POLICY_PREVIEW_TIME_LIMIT_SEC
        )
        _preview_synthetic._POLICY_PREVIEW_EXEC_TIMEOUT_SEC = (
            _POLICY_PREVIEW_EXEC_TIMEOUT_SEC
        )
        _preview_synthetic._POLICY_PREVIEW_TIME_LIMIT_SEC = (
            _POLICY_PREVIEW_TIME_LIMIT_SEC
        )
        return _preview_research_surface_patch(patch=patch, surface=surface)

    def load_instance(self, instance_path: str) -> Any:
        suffix = Path(instance_path).suffix.lower()
        if suffix == ".json":
            return CvrpInstance.from_json(instance_path)
        if suffix == ".vrp":
            return load_cvrplib_instance(instance_path)
        raise ValueError(f"unsupported CVRP instance file extension: {suffix or '<none>'}")

    def deserialize_solver_output(
        self,
        raw_output: Mapping[str, Any],
        instance: Any,
    ) -> SolverArtifact:
        return _deserialize_solver_output(raw_output, instance)

    def check_solution_consistency(
        self,
        artifact: SolverArtifact,
        instance: Any,
    ) -> CheckReport:
        return _check_solution_consistency(artifact, instance)

    def check_feasibility(
        self,
        artifact: SolverArtifact,
        instance: Any,
    ) -> CheckReport:
        return _check_feasibility(artifact, instance)

    def recompute_objective(
        self,
        artifact: SolverArtifact,
        instance: Any,
    ) -> Mapping[str, int | float]:
        return _recompute_objective(artifact, instance)

    def estimate_lower_bound(
        self,
        metric_name: str,
        instance_paths: Sequence[str],
    ) -> LowerBoundEstimate | None:
        return None
