"""Bridge ProblemSpecV1 into the legacy campaign runtime shape.

ProblemSpecV1 is the authoritative problem schema.  CampaignManager and
VerificationGate still consume the older ProblemSpec, so this module provides a
single narrow compatibility path instead of hand-built dual specs in runners
and tests.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import yaml

from scion.config.problem import (
    ParameterSearchConfig,
    ProblemSpec,
    SearchSpace,
    SolverConfig,
)
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


def load_problem_spec_v1_from_yaml(path: str | Path) -> ProblemSpecV1:
    """Load ProblemSpecV1, resolving root_dir relative to the YAML file."""
    spec_path = Path(path).expanduser().resolve()
    with open(spec_path, encoding="utf-8") as fh:
        payload = yaml.safe_load(fh) or {}
    root_dir = str(payload.get("root_dir") or "").strip()
    if not root_dir or root_dir == "PLACEHOLDER":
        payload["root_dir"] = str(spec_path.parent)
    else:
        root_path = Path(root_dir).expanduser()
        if not root_path.is_absolute():
            payload["root_dir"] = str((spec_path.parent / root_path).resolve())
    return ProblemSpecV1(**payload)


def legacy_problem_spec_from_v1(spec: ProblemSpecV1) -> ProblemSpec:
    """Convert ProblemSpecV1 to the legacy ProblemSpec used by campaign code."""

    root_dir = str(Path(spec.root_dir).expanduser().resolve())
    legacy = ProblemSpec(
        name=spec.id,
        root_dir=root_dir,
        description=spec.description,
        operators_dir=spec.operators_dir,
        data_dir=spec.data_dir,
        oracle_path=spec.oracle_path,
        solver_path=spec.solver_path,
        canary_case_path=_resolve_optional_file(root_dir, spec.canary_case_path),
        unit_test_path=spec.unit_test_path,
        regression_test_path=spec.regression_test_path,
        operator_categories=list(spec.operator_interface.category_names),
        search_space=SearchSpace(**spec.search_space.model_dump()),
        solver=SolverConfig(**spec.solver.model_dump()),
        parameter_search=_parameter_search_from_v1(spec),
    )
    if spec.family_taxonomy is not None:
        object.__setattr__(legacy, "family_taxonomy", spec.family_taxonomy)
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
