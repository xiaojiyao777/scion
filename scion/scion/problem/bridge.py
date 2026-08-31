"""Legacy ProblemSpecV1 compatibility conversions.

New runtime code loads ProblemSpecV1 through :mod:`scion.problem.loader` and
passes the resulting adapter directly.  This module retains only the legacy
shape conversion API and a compatibility re-export of the V1 YAML loader.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from scion.config.problem import (
    ParameterSearchConfig,
    ProblemSpec,
    SearchSpace,
    SolverConfig,
)
from scion.problem.loader import load_problem_spec_v1_from_yaml
from scion.problem.spec import (
    ObjectiveMetricSpec,
    ObjectivePolicySpec,
    ProblemSpecV1,
)


@dataclass(frozen=True)
class ProblemSpecBridge:
    """Runtime bundle derived from a single ProblemSpecV1."""

    spec_v1: ProblemSpecV1
    problem_spec: ProblemSpec
    metric_specs: tuple[ObjectiveMetricSpec, ...]
    objective_policy: ObjectivePolicySpec
    operator_execute_signature: str


def bridge_problem_spec_v1(spec: ProblemSpecV1) -> ProblemSpecBridge:
    """Return campaign/runtime compatibility objects derived from *spec*."""

    return ProblemSpecBridge(
        spec_v1=spec,
        problem_spec=legacy_problem_spec_from_v1(spec),
        metric_specs=tuple(spec.objectives),
        objective_policy=spec.objective_policy,
        operator_execute_signature=spec.operator_interface.execute_signature,
    )


def legacy_problem_spec_from_v1(spec: ProblemSpecV1) -> ProblemSpec:
    """Convert ProblemSpecV1 to the legacy ProblemSpec used by campaign code."""

    root_dir = str(Path(spec.root_dir).expanduser().resolve())
    surface_categories = (
        [surface.name for surface in spec.research_surfaces]
        if spec.research_surfaces is not None
        else list(spec.operator_interface.category_names)
    )
    legacy = ProblemSpec(
        spec_version=spec.spec_version,
        name=spec.id,
        root_dir=root_dir,
        description=spec.description,
        adapter_import_path=spec.adapter.import_path,
        requires_adapter_for_runtime=True,
        operators_dir=spec.operators_dir,
        data_dir=spec.data_dir,
        oracle_path=spec.oracle_path,
        solver_path=spec.solver_path,
        canary_case_path=_resolve_optional_file(root_dir, spec.canary_case_path),
        unit_test_path=spec.unit_test_path,
        regression_test_path=spec.regression_test_path,
        development_unit_test_path=spec.development_unit_test_path,
        development_regression_test_path=spec.development_regression_test_path,
        development_unit_test_support_paths=list(
            spec.development_unit_test_support_paths
        ),
        development_regression_test_support_paths=list(
            spec.development_regression_test_support_paths
        ),
        development_workspace_paths=list(spec.development_workspace_paths),
        development_problem_package_paths=list(
            spec.development_problem_package_paths
        ),
        operator_categories=surface_categories,
        research_surfaces=list(spec.research_surfaces or []),
        runtime_failure_guidance=list(spec.runtime_failure_guidance or []),
        search_space=SearchSpace(**spec.search_space.model_dump()),
        solver=SolverConfig(**spec.solver.model_dump()),
        parameter_search=_parameter_search_from_v1(spec),
    )
    if spec.family_taxonomy is not None:
        object.__setattr__(legacy, "family_taxonomy", spec.family_taxonomy)
    object.__setattr__(legacy, "spec_v1", spec)
    object.__setattr__(legacy, "objectives", tuple(spec.objectives))
    object.__setattr__(legacy, "measurement", spec.measurement)
    object.__setattr__(legacy, "runtime_dependencies", spec.runtime_dependencies)
    return legacy


def _parameter_search_from_v1(spec: ProblemSpecV1) -> ParameterSearchConfig:
    values = spec.parameter_search.model_dump()
    allowed = set(ParameterSearchConfig.model_fields)
    return ParameterSearchConfig(
        **{key: value for key, value in values.items() if key in allowed}
    )


def _resolve_optional_file(root_dir: str, path: str) -> str:
    if not path:
        return ""
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = Path(root_dir) / candidate
    return str(candidate.resolve())


__all__: Sequence[str] = (
    "ProblemSpecBridge",
    "bridge_problem_spec_v1",
    "legacy_problem_spec_from_v1",
    "load_problem_spec_v1_from_yaml",
)
