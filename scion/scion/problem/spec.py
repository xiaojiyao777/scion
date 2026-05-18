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


class ResearchSurfaceAlgorithmSpec(_Strict):
    role: str = ""
    invocation_point: str = ""
    description: str = ""


class ResearchSurfaceTargetsSpec(_Strict):
    files: list[str] = Field(default_factory=list)
    create_new_allowed: bool = True
    modify_allowed: bool = True
    remove_allowed: bool = False
    singleton: bool = False


class ResearchSurfaceReturnValueSpec(_Strict):
    value_type: Literal[
        "any",
        "str",
        "bool",
        "int",
        "number",
        "sequence",
        "mapping",
    ] = "any"
    allowed_literals: list[Any] = Field(default_factory=list)
    numeric_range: tuple[float, float] | None = None
    allowed_keys: list[str] = Field(default_factory=list)
    required_keys: list[str] = Field(default_factory=list)
    value_numeric_range: tuple[float, float] | None = None
    allow_static_unknown: bool = True

    @field_validator("numeric_range", "value_numeric_range")
    @classmethod
    def _validate_numeric_range(
        cls,
        value: tuple[float, float] | None,
    ) -> tuple[float, float] | None:
        if value is None:
            return None
        lo, hi = float(value[0]), float(value[1])
        if lo > hi:
            raise ValueError("return value range lower bound exceeds upper bound")
        return (lo, hi)


class ResearchSurfaceInterfaceSpec(_Strict):
    required_functions: list[str] = Field(default_factory=list)
    function_signatures: dict[str, list[str]] = Field(default_factory=dict)
    return_contract: str = ""
    return_values: dict[str, ResearchSurfaceReturnValueSpec] = Field(default_factory=dict)

    @field_validator("function_signatures", mode="before")
    @classmethod
    def _validate_function_signatures(cls, value: Any) -> dict[str, list[str]]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise TypeError("function_signatures must be a mapping")
        normalized: dict[str, list[str]] = {}
        for raw_name, raw_args in value.items():
            name = str(raw_name).strip()
            if not name:
                raise ValueError("function_signatures contains an empty function name")
            normalized[name] = _coerce_function_signature_args(name, raw_args)
        return normalized


class ResearchSurfaceBoundsSpec(_Strict):
    allowed_components: list[str] = Field(default_factory=list)
    numeric_ranges: dict[str, tuple[float, float]] = Field(default_factory=dict)
    complexity_scale_terms: list[str] = Field(default_factory=list)


class ResearchSurfaceEvidenceSpec(_Strict):
    required_runtime_fields: list[str] = Field(default_factory=list)
    optional_runtime_fields: list[str] = Field(default_factory=list)
    activity_runtime_fields: list[str] = Field(default_factory=list)
    activation_runtime_fields: dict[str, list[str]] = Field(default_factory=dict)
    effect_probe_runtime_fields: list[str] = Field(default_factory=list)
    stage_budget_runtime_fields: list[str] = Field(default_factory=list)
    fail_closed_on_zero_activity: bool = False
    fail_closed_on_stage_budget_starvation: bool = False


class ResearchSurfaceNoveltySpec(_Strict):
    strategy: str = ""
    signature_fields: list[str] = Field(default_factory=list)


class ResearchSurfacePromptSpec(_Strict):
    hypothesis_guidance: str = ""
    implementation_guidance: str = ""
    anti_patterns: str = ""


class RuntimeFailureGuidanceSpec(_Strict):
    failure_categories: list[str] = Field(default_factory=list)
    applies_to_surfaces: list[str] = Field(default_factory=list)
    applies_to_surface_kinds: list[str] = Field(default_factory=list)
    min_category_fraction: float = Field(default=0.5, ge=0.0, le=1.0)
    min_count: int = Field(default=1, ge=1)
    recommended_surfaces: list[str] = Field(default_factory=list)
    discouraged_surfaces: list[str] = Field(default_factory=list)
    guidance: str = ""

    @field_validator(
        "failure_categories",
        "applies_to_surfaces",
        "applies_to_surface_kinds",
        "recommended_surfaces",
        "discouraged_surfaces",
    )
    @classmethod
    def _normalize_text_list(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for raw in value:
            text = str(raw).strip()
            if not text or text in seen:
                continue
            normalized.append(text)
            seen.add(text)
        return normalized


SUPPORTED_RESEARCH_SURFACE_KINDS = frozenset(
    {
        "operator",
        "policy",
        "config",
        "portfolio",
        "construction",
        "acceptance_restart",
        "solver_design",
    }
)


class ResearchSurfaceSpec(_Strict):
    name: str
    kind: str
    description: str = ""

    algorithm: ResearchSurfaceAlgorithmSpec | None = None
    targets: ResearchSurfaceTargetsSpec | None = None
    interface: ResearchSurfaceInterfaceSpec | None = None
    bounds: ResearchSurfaceBoundsSpec | None = None
    evidence: ResearchSurfaceEvidenceSpec | None = None
    novelty: ResearchSurfaceNoveltySpec | None = None
    prompt: ResearchSurfacePromptSpec | None = None

    # Legacy v1 surface fields.  These remain public compatibility attributes
    # for ContractGate, ContextManager, and older tests/configs.
    target_files: list[str] = Field(default_factory=list)
    prompt_hint: str = ""
    required_functions: list[str] = Field(default_factory=list)
    create_new_allowed: bool = True
    modify_allowed: bool = True
    remove_allowed: bool = False

    @field_validator("kind")
    @classmethod
    def _validate_kind(cls, value: str) -> str:
        kind = value.strip()
        if not kind:
            raise ValueError("research surface kind must not be empty")
        if kind not in SUPPORTED_RESEARCH_SURFACE_KINDS:
            allowed = ", ".join(sorted(SUPPORTED_RESEARCH_SURFACE_KINDS))
            raise ValueError(
                f"unsupported research surface kind '{kind}', expected one of: "
                f"{allowed}"
            )
        return kind

    @model_validator(mode="after")
    def _sync_legacy_and_v2_fields(self) -> ResearchSurfaceSpec:
        surface_fields = self.model_fields_set
        if self.targets is None:
            self.targets = ResearchSurfaceTargetsSpec(
                files=list(self.target_files),
                create_new_allowed=self.create_new_allowed,
                modify_allowed=self.modify_allowed,
                remove_allowed=self.remove_allowed,
            )
        else:
            target_fields = self.targets.model_fields_set
            if (
                "files" in target_fields
                and "target_files" in surface_fields
                and list(self.target_files) != list(self.targets.files)
            ):
                raise ValueError(
                    "research surface legacy target_files conflicts with "
                    "v2 targets.files"
                )
            if "files" in target_fields or not self.target_files:
                self.target_files = list(self.targets.files)
            else:
                self.targets.files = list(self.target_files)

            for attr in (
                "create_new_allowed",
                "modify_allowed",
                "remove_allowed",
            ):
                if (
                    attr in target_fields
                    and attr in surface_fields
                    and getattr(self, attr) != getattr(self.targets, attr)
                ):
                    raise ValueError(
                        f"research surface legacy {attr} conflicts with "
                        f"v2 targets.{attr}"
                    )
                if attr in target_fields:
                    setattr(self, attr, getattr(self.targets, attr))
                else:
                    setattr(self.targets, attr, getattr(self, attr))

        if not self.target_files:
            raise ValueError(
                "research surface must declare target_files or targets.files"
            )

        if self.interface is None:
            self.interface = ResearchSurfaceInterfaceSpec(
                required_functions=list(self.required_functions)
            )
        else:
            interface_fields = self.interface.model_fields_set
            if (
                "required_functions" in interface_fields
                and "required_functions" in surface_fields
                and list(self.required_functions)
                != list(self.interface.required_functions)
            ):
                raise ValueError(
                    "research surface legacy required_functions conflicts "
                    "with v2 interface.required_functions"
                )
            if "required_functions" in interface_fields or not self.required_functions:
                self.required_functions = list(self.interface.required_functions)
            else:
                self.interface.required_functions = list(self.required_functions)

        if self.prompt is None:
            if self.prompt_hint:
                self.prompt = ResearchSurfacePromptSpec(
                    implementation_guidance=self.prompt_hint
                )
        else:
            if not self.prompt_hint:
                self.prompt_hint = (
                    self.prompt.implementation_guidance
                    or self.prompt.hypothesis_guidance
                )
            elif not self.prompt.implementation_guidance:
                self.prompt.implementation_guidance = self.prompt_hint

        return self


class LLMHintsSpec(_Strict):
    problem_summary: str = ""
    operator_interface: str = ""


def _coerce_function_signature_args(name: str, value: Any) -> list[str]:
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        if "(" in text and ")" in text:
            start = text.index("(")
            end = text.rindex(")")
            declared_name = text[:start].strip()
            if declared_name.startswith("def "):
                declared_name = declared_name[4:].strip()
            if declared_name and declared_name != name:
                raise ValueError(
                    f"function_signatures key '{name}' conflicts with signature "
                    f"name '{declared_name}'"
                )
            text = text[start + 1 : end]
        if not text.strip():
            return []
        args = [part.strip() for part in text.split(",")]
    else:
        try:
            args = [str(part).strip() for part in value]
        except TypeError as exc:
            raise TypeError(
                f"function_signatures[{name!r}] must be a string or list"
            ) from exc

    normalized = [arg for arg in args if arg]
    for arg in normalized:
        if not arg.isidentifier():
            raise ValueError(
                f"function_signatures[{name!r}] contains invalid parameter "
                f"name '{arg}'"
            )
    return normalized


class FamilyTaxonomySpec(_Strict):
    version: str = "v1"
    families: list[str] = Field(default_factory=list)
    aliases: dict[str, list[str]] = Field(default_factory=dict)


class ProblemAdapterRef(_Strict):
    import_path: str
    api_version: Literal["v1"] = "v1"


class RuntimeDependencySpec(_Strict):
    required_python_modules: list[str] = Field(default_factory=list)
    required_executables: list[str] = Field(default_factory=list)

    @field_validator("required_python_modules", "required_executables")
    @classmethod
    def _validate_dependency_names(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for raw_name in value:
            name = str(raw_name).strip()
            if not name:
                raise ValueError("runtime dependency names must not be empty")
            if name in seen:
                continue
            normalized.append(name)
            seen.add(name)
        return normalized

    @property
    def has_checks(self) -> bool:
        return bool(self.required_python_modules or self.required_executables)


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
    runtime_dependencies: RuntimeDependencySpec = RuntimeDependencySpec()
    runtime_failure_guidance: list[RuntimeFailureGuidanceSpec] = Field(
        default_factory=list
    )
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
