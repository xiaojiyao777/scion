"""ProblemSpecV1 — strict Pydantic schema for problem definitions.

All problem-specific configuration enters Scion through this schema.
``extra="forbid"`` ensures no unrecognised fields slip through.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from scion.core.operator_interface import parse_execute_signature


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ObjectiveMetricSpec(_Strict):
    name: str
    direction: Literal["minimize", "maximize"]
    priority: int
    tie_tolerance: float = 0.0
    weight: float | None = None


class OperatorCategorySpec(_Strict):
    name: str
    description: str = ""


class OperatorInterfaceSpec(_Strict):
    base_class_import: str
    execute_signature: str = "execute(self, solution, rng) -> Solution"
    categories: list[OperatorCategorySpec]

    @field_validator("execute_signature")
    @classmethod
    def _validate_execute_signature(cls, value: str) -> str:
        parse_execute_signature(value)
        return value

    @property
    def category_names(self) -> tuple[str, ...]:
        return tuple(c.name for c in self.categories)


class ResearchSurfaceSpec(_Strict):
    name: str
    kind: Literal["operator", "policy", "config"]
    description: str = ""
    target_files: list[str]
    prompt_hint: str = ""
    required_functions: list[str] = Field(default_factory=list)
    create_new_allowed: bool = True
    modify_allowed: bool = True
    remove_allowed: bool = False


class LLMHintsSpec(_Strict):
    problem_summary: str = ""
    operator_interface: str = ""


class FamilyTaxonomySpec(_Strict):
    version: str = "v1"
    families: list[str] = Field(default_factory=list)
    aliases: dict[str, list[str]] = Field(default_factory=dict)


class ProblemAdapterRef(_Strict):
    import_path: str
    api_version: Literal["v1"] = "v1"


class ObjectivePolicySpec(_Strict):
    mode: Literal["single", "lexicographic", "weighted_sum"] = "lexicographic"
    expose_weights_to_llm: bool = False


class SearchSpaceSpec(_Strict):
    editable: list[str]
    frozen: list[str]
    import_whitelist: list[str]


class SolverSpec(_Strict):
    time_limit_sec: int = 300
    max_iter: int = 1000


class ParameterSearchSpec(_Strict):
    enabled: bool = True
    trigger: Literal["on_promote"] = "on_promote"
    target: Literal["operator_weights"] = "operator_weights"
    strategy: Literal["random_local", "bayesian"] = "random_local"
    n_initial_random: int = 8
    n_iterations: int = 16
    n_eval_seeds: int = 2
    weight_bounds: tuple[float, float] = (0.05, 5.0)
    eval_cases: list[str] = []


class ProblemSpecV1(_Strict):
    spec_version: Literal["problem-v1"] = "problem-v1"

    id: str
    display_name: str
    root_dir: str
    description: str = ""

    search_space: SearchSpaceSpec
    solver: SolverSpec = SolverSpec()
    parameter_search: ParameterSearchSpec = ParameterSearchSpec()

    operator_interface: OperatorInterfaceSpec
    research_surfaces: list[ResearchSurfaceSpec] | None = None
    objective_policy: ObjectivePolicySpec = ObjectivePolicySpec()
    objectives: list[ObjectiveMetricSpec]
    llm_hints: LLMHintsSpec = LLMHintsSpec()
    family_taxonomy: FamilyTaxonomySpec | None = None
    adapter: ProblemAdapterRef

    # Legacy compatibility fields for pre-ProblemSpecV1 problem packages.
    operators_dir: str = "operators"
    data_dir: str = "data"
    oracle_path: str = "oracle.py"
    solver_path: str = "solver.py"
    canary_case_path: str = ""
    unit_test_path: str = ""
    regression_test_path: str = ""

    @model_validator(mode="after")
    def _validate_objectives(self) -> ProblemSpecV1:
        names = [m.name for m in self.objectives]
        if len(names) != len(set(names)):
            raise ValueError("objective metric names must be unique")

        if self.research_surfaces is not None:
            surface_names = [surface.name for surface in self.research_surfaces]
            if len(surface_names) != len(set(surface_names)):
                raise ValueError("research surface names must be unique")

        priorities = sorted(m.priority for m in self.objectives)
        expected = list(range(1, len(priorities) + 1))
        if priorities != expected:
            raise ValueError(
                f"objective priorities must be contiguous 1..N: got {priorities}"
            )

        if self.objective_policy.mode == "weighted_sum":
            missing_weights = [m.name for m in self.objectives if m.weight is None]
            if missing_weights:
                raise ValueError(
                    "weighted_sum objective policy requires weight on every objective: "
                    f"missing {missing_weights}"
                )
            non_positive = [
                m.name for m in self.objectives
                if m.weight is not None and m.weight <= 0
            ]
            if non_positive:
                raise ValueError(
                    "weighted_sum objective weights must be positive: "
                    f"{non_positive}"
                )

        module_part = self.adapter.import_path.split(":")[0]
        expected_prefix = f"scion.problems.{self.id}."
        if not module_part.startswith(expected_prefix):
            raise ValueError(
                f"adapter import_path module must start with "
                f"'{expected_prefix}', got '{module_part}'"
            )
        return self
