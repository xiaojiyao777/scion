"""Independent frozen decoder for the private ProblemSpec declaration leaf."""

from __future__ import annotations

import ast
import math
import re
from dataclasses import dataclass
from typing import Any

from .study_manifest_controls_schema import _canonical_json_bytes, _freeze_json

_ERROR = (
    "STUDY_CONFIG_SUBSET_AND_REQUESTED_PROVIDER_POLICY_AND_"
    "PROBLEM_SPEC_DECLARATION_JOIN_INVALID"
)
_MAX_BYTES = 1 << 20
_MAX_JSON_DEPTH = 23
_SCHEMA_VERSION = "scion.initial_screening_problem_spec.declaration.v1"
_SCOPE = "PROBLEM_SPEC_DECLARATION_ONLY"
_LIMITATIONS = (
    "PROBLEM_ADAPTER_UNVERIFIED",
    "RESEARCH_INPUT_UNVERIFIED",
    "RUNTIME_RESEARCH_HISTORY_CONSUMPTION_UNVERIFIED",
    "VERIFICATION_CONFIG_AND_RUNTIME_UNVERIFIED",
    "SOURCE_CARRIER_UNVERIFIED",
    "B0_CONTENT_UNVERIFIED",
    "STUDY_MANIFEST_UNVERIFIED",
    "ROOT_LIFETIME_FRESHNESS_UNVERIFIED",
    "MATCHED_RESULT_UNAUTHORIZED",
    "LIVE_EXECUTION_UNAUTHORIZED",
    "STUDY_GO_UNAUTHORIZED",
)
_PROBLEM_KEYS = frozenset(
    {
        "spec_version",
        "id",
        "display_name",
        "description",
        "search_space",
        "solver",
        "parameter_search",
        "operator_interface",
        "research_surfaces",
        "objective_policy",
        "objectives",
        "measurement",
        "llm_hints",
        "family_taxonomy",
        "runtime_dependencies",
        "runtime_failure_guidance",
        "adapter",
        "operators_dir",
        "data_dir",
        "oracle_path",
        "solver_path",
        "canary_case_path",
        "unit_test_path",
        "regression_test_path",
        "development_unit_test_path",
        "development_regression_test_path",
        "development_unit_test_support_paths",
        "development_regression_test_support_paths",
        "development_workspace_paths",
        "development_problem_package_paths",
    }
)
_SURFACE_KINDS = frozenset(
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
_VALUE_TYPES = frozenset({"any", "str", "bool", "int", "number", "sequence", "mapping"})
_MECHANISM_ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_MECHANISM_DECLARATION_RE = re.compile(r"^[a-z0-9_*]{1,64}$")


class _StudyManifestProblemSpecDeclarationSchemaError(ValueError):
    """Fixed, body-free failure for one archived declaration-v1 leaf."""


@dataclass(frozen=True, repr=False)
class _NormalizedDeclaredProblemSpec:
    """Detached fields needed to join one declaration across ten roots."""

    canonical_bytes: bytes
    frozen: tuple[Any, ...]
    problem_id: str
    metric_specs: tuple[Any, ...]
    objective_policy: tuple[Any, ...]
    effect_metric: str
    protected_objectives: tuple[str, ...]
    pairing_validity: str
    runtime_model: str
    practical_delta_screen: float
    practical_delta_validate: float

    def __repr__(self) -> str:
        return "_NormalizedDeclaredProblemSpec(<redacted>)"

    __str__ = __repr__


def _normalize_declared_problem_spec(value: Any) -> _NormalizedDeclaredProblemSpec:
    """Normalize declaration-v1 without importing its live producer schema."""

    failed = False
    result: _NormalizedDeclaredProblemSpec | None = None
    try:
        result = _normalize_declared_problem_spec_unsafe(value)
    except Exception:  # noqa: BLE001 - sanitize the private schema boundary
        failed = True
    if failed or result is None:
        raise _StudyManifestProblemSpecDeclarationSchemaError(_ERROR)
    return result


def _normalize_declared_problem_spec_unsafe(
    value: Any,
) -> _NormalizedDeclaredProblemSpec:
    _validate_json_depth(value)
    canonical = _canonical_json_bytes(value, max_bytes=_MAX_BYTES)
    leaf = _exact_dict(
        value,
        {"schema_version", "scope", "limitations", "problem_spec_v1"},
    )
    if (
        leaf["schema_version"] != _SCHEMA_VERSION
        or leaf["scope"] != _SCOPE
        or tuple(_exact_list(leaf["limitations"])) != _LIMITATIONS
    ):
        raise ValueError
    problem = _exact_dict(leaf["problem_spec_v1"], _PROBLEM_KEYS)
    facts = _validate_problem(problem)
    measurement = facts[3]
    effect_scale = _exact_dict(
        measurement["effect_scale"],
        {
            "metric",
            "unit",
            "practical_delta_screen",
            "practical_delta_validate",
        },
    )
    return _NormalizedDeclaredProblemSpec(
        canonical_bytes=canonical,
        frozen=_freeze_json(value),
        problem_id=facts[0],
        metric_specs=_freeze_json(facts[1]),
        objective_policy=_freeze_json(facts[2]),
        effect_metric=effect_scale["metric"].strip(),
        protected_objectives=tuple(
            item.strip() for item in measurement["protected_objectives"] if item.strip()
        ),
        pairing_validity=measurement["pairing_validity"],
        runtime_model=measurement["runtime_model"],
        practical_delta_screen=effect_scale["practical_delta_screen"],
        practical_delta_validate=effect_scale["practical_delta_validate"],
    )


def _validate_json_depth(value: Any, depth: int = 0) -> None:
    if depth > _MAX_JSON_DEPTH:
        raise ValueError
    if type(value) is list:
        for item in value:
            _validate_json_depth(item, depth + 1)
    elif type(value) is dict:
        for item in value.values():
            _validate_json_depth(item, depth + 1)


def _validate_problem(
    problem: dict[str, Any],
) -> tuple[str, list[Any], dict[str, Any], dict[str, Any]]:
    if problem["spec_version"] != "problem-v1":
        raise ValueError
    problem_id = _string(problem["id"])
    for key in (
        "display_name",
        "description",
        "operators_dir",
        "data_dir",
        "oracle_path",
        "solver_path",
    ):
        _string(problem[key])
    if "\x00" in _string(problem["canary_case_path"]):
        raise ValueError
    _validate_search_space(problem["search_space"])
    _validate_solver(problem["solver"])
    _validate_parameter_search(problem["parameter_search"])
    _validate_operator_interface(problem["operator_interface"])
    _validate_surfaces(problem["research_surfaces"])
    objective_policy = _validate_objective_policy(problem["objective_policy"])
    objectives = _validate_objectives(problem["objectives"], objective_policy)
    measurement = _validate_measurement(problem["measurement"], objectives)
    _validate_llm_hints(problem["llm_hints"])
    _validate_family(problem["family_taxonomy"])
    _validate_runtime_dependencies(problem["runtime_dependencies"])
    _validate_runtime_failure_guidance(problem["runtime_failure_guidance"])
    _validate_adapter(problem["adapter"], problem_id=problem_id)
    _validate_development_paths(problem)
    return problem_id, objectives, objective_policy, measurement


def _validate_search_space(value: Any) -> None:
    fields = _exact_dict(value, {"editable", "frozen", "import_whitelist"})
    for item in fields.values():
        _string_list(item)


def _validate_solver(value: Any) -> None:
    fields = _exact_dict(value, {"time_limit_sec", "max_iter"})
    for item in fields.values():
        _integer(item)


def _validate_parameter_search(value: Any) -> None:
    fields = _exact_dict(
        value,
        {
            "enabled",
            "trigger",
            "target",
            "strategy",
            "n_initial_random",
            "n_iterations",
            "n_eval_seeds",
            "weight_bounds",
            "eval_cases",
        },
    )
    _boolean(fields["enabled"])
    if (
        fields["trigger"] != "on_promote"
        or fields["target"] != "operator_weights"
        or fields["strategy"] not in {"random_local", "bayesian"}
    ):
        raise ValueError
    for key in ("n_initial_random", "n_iterations", "n_eval_seeds"):
        _integer(fields[key])
    _float_pair(fields["weight_bounds"])
    _string_list(fields["eval_cases"])


def _validate_operator_interface(value: Any) -> None:
    fields = _exact_dict(
        value, {"base_class_import", "execute_signature", "categories"}
    )
    _string(fields["base_class_import"])
    _validate_execute_signature(fields["execute_signature"])
    for category in _exact_list(fields["categories"]):
        row = _exact_dict(category, {"name", "description"})
        _string(row["name"])
        _string(row["description"])


def _validate_surfaces(value: Any) -> None:
    if value is None:
        return
    names: list[str] = []
    for item in _exact_list(value):
        surface = _validate_surface(item)
        names.append(surface["name"])
    if len(names) != len(set(names)):
        raise ValueError


def _validate_surface(value: Any) -> dict[str, Any]:
    surface = _exact_dict(
        value,
        {
            "name",
            "kind",
            "description",
            "algorithm",
            "targets",
            "interface",
            "bounds",
            "evidence",
            "novelty",
            "prompt",
            "target_files",
            "prompt_hint",
            "required_functions",
            "create_new_allowed",
            "modify_allowed",
            "remove_allowed",
        },
    )
    _string(surface["name"])
    kind = _string(surface["kind"])
    if kind != kind.strip() or kind not in _SURFACE_KINDS:
        raise ValueError
    _string(surface["description"])
    _validate_optional_algorithm(surface["algorithm"])
    targets = _validate_targets(surface["targets"])
    interface = _validate_interface(surface["interface"])
    _validate_optional_bounds(surface["bounds"])
    _validate_optional_evidence(surface["evidence"])
    _validate_optional_novelty(surface["novelty"])
    _validate_prompt_join(surface["prompt"], surface["prompt_hint"])
    target_files = _string_list(surface["target_files"])
    required_functions = _string_list(surface["required_functions"])
    for key in ("create_new_allowed", "modify_allowed", "remove_allowed"):
        _boolean(surface[key])
    if (
        not target_files
        or target_files != tuple(targets["files"])
        or required_functions != tuple(interface["required_functions"])
        or surface["create_new_allowed"] != targets["create_new_allowed"]
        or surface["modify_allowed"] != targets["modify_allowed"]
        or surface["remove_allowed"] != targets["remove_allowed"]
    ):
        raise ValueError
    return surface


def _validate_optional_algorithm(value: Any) -> None:
    if value is None:
        return
    fields = _exact_dict(value, {"role", "invocation_point", "description"})
    for item in fields.values():
        _string(item)


def _validate_targets(value: Any) -> dict[str, Any]:
    fields = _exact_dict(
        value,
        {
            "files",
            "create_new_allowed",
            "modify_allowed",
            "remove_allowed",
            "singleton",
        },
    )
    _string_list(fields["files"])
    for key in (
        "create_new_allowed",
        "modify_allowed",
        "remove_allowed",
        "singleton",
    ):
        _boolean(fields[key])
    return fields


def _validate_interface(value: Any) -> dict[str, Any]:
    fields = _exact_dict(
        value,
        {
            "entrypoint_files",
            "support_files",
            "required_functions",
            "function_signatures",
            "return_contract",
            "return_values",
        },
    )
    for key in ("entrypoint_files", "support_files", "required_functions"):
        _string_list(fields[key])
    signatures = _exact_dict_any(fields["function_signatures"])
    for name, arguments in signatures.items():
        if not name or name != name.strip():
            raise ValueError
        args = _string_list(arguments)
        if any(not argument.isidentifier() for argument in args):
            raise ValueError
    _string(fields["return_contract"])
    for name, item in _exact_dict_any(fields["return_values"]).items():
        _string(name)
        _validate_return_value(item)
    return fields


def _validate_return_value(value: Any) -> None:
    fields = _exact_dict(
        value,
        {
            "value_type",
            "allowed_literals",
            "numeric_range",
            "allowed_keys",
            "required_keys",
            "value_numeric_range",
            "allow_static_unknown",
        },
    )
    if fields["value_type"] not in _VALUE_TYPES:
        raise ValueError
    for item in _exact_list(fields["allowed_literals"]):
        _validate_json_value(item)
    _optional_ordered_float_pair(fields["numeric_range"])
    _string_list(fields["allowed_keys"])
    _string_list(fields["required_keys"])
    _optional_ordered_float_pair(fields["value_numeric_range"])
    _boolean(fields["allow_static_unknown"])


def _validate_optional_bounds(value: Any) -> None:
    if value is None:
        return
    fields = _exact_dict(
        value,
        {"allowed_components", "numeric_ranges", "complexity_scale_terms"},
    )
    _string_list(fields["allowed_components"])
    for item in _exact_dict_any(fields["numeric_ranges"]).values():
        _float_pair(item)
    _string_list(fields["complexity_scale_terms"])


def _validate_optional_evidence(value: Any) -> None:
    if value is None:
        return
    fields = _exact_dict(
        value,
        {
            "required_runtime_fields",
            "optional_runtime_fields",
            "activity_runtime_fields",
            "activation_runtime_fields",
            "effect_probe_runtime_fields",
            "stage_budget_runtime_fields",
            "phase_runtime_fields",
            "phase_telemetry_buckets",
            "runtime_field_roles",
            "mechanism_telemetry",
            "fail_closed_on_zero_activity",
            "fail_closed_on_stage_budget_starvation",
        },
    )
    for key in (
        "required_runtime_fields",
        "optional_runtime_fields",
        "activity_runtime_fields",
        "effect_probe_runtime_fields",
        "stage_budget_runtime_fields",
        "phase_runtime_fields",
        "phase_telemetry_buckets",
    ):
        _string_list(fields[key])
    for key in ("activation_runtime_fields", "runtime_field_roles"):
        for item in _exact_dict_any(fields[key]).values():
            _string_list(item)
    for declaration, item in _exact_dict_any(fields["mechanism_telemetry"]).items():
        if not _valid_mechanism_declaration(declaration):
            raise ValueError
        row = _exact_dict(
            item,
            {"activation_runtime_fields", "effect_probe_runtime_fields"},
        )
        _string_list(row["activation_runtime_fields"])
        _string_list(row["effect_probe_runtime_fields"])
    _boolean(fields["fail_closed_on_zero_activity"])
    _boolean(fields["fail_closed_on_stage_budget_starvation"])


def _validate_optional_novelty(value: Any) -> None:
    if value is None:
        return
    fields = _exact_dict(value, {"strategy", "signature_fields"})
    _string(fields["strategy"])
    _string_list(fields["signature_fields"])


def _validate_prompt_join(value: Any, prompt_hint: Any) -> None:
    hint = _string(prompt_hint)
    if value is None:
        if hint:
            raise ValueError
        return
    fields = _exact_dict(
        value,
        {"hypothesis_guidance", "implementation_guidance", "anti_patterns"},
    )
    for item in fields.values():
        _string(item)
    if not hint and (
        fields["implementation_guidance"] or fields["hypothesis_guidance"]
    ):
        raise ValueError
    if hint and not fields["implementation_guidance"]:
        raise ValueError


def _validate_objective_policy(value: Any) -> dict[str, Any]:
    fields = _exact_dict(value, {"mode", "expose_weights_to_llm"})
    if fields["mode"] not in {"single", "lexicographic", "weighted_sum"}:
        raise ValueError
    _boolean(fields["expose_weights_to_llm"])
    return fields


def _validate_objectives(value: Any, policy: dict[str, Any]) -> list[Any]:
    objectives = _exact_list(value)
    if not objectives:
        raise ValueError
    names: list[str] = []
    priorities: list[int] = []
    missing_weight = False
    nonpositive_weight = False
    for item in objectives:
        row = _exact_dict(
            item,
            {"name", "direction", "priority", "tie_tolerance", "weight"},
        )
        names.append(_string(row["name"]))
        if row["direction"] not in {"minimize", "maximize"}:
            raise ValueError
        priorities.append(_integer(row["priority"]))
        _finite_float(row["tie_tolerance"])
        weight = _optional_float(row["weight"])
        missing_weight |= weight is None
        nonpositive_weight |= weight is not None and weight <= 0.0
    if (
        len(names) != len(set(names))
        or sorted(priorities) != list(range(1, len(priorities) + 1))
        or (policy["mode"] == "weighted_sum" and (missing_weight or nonpositive_weight))
    ):
        raise ValueError
    return objectives


def _validate_measurement(value: Any, objectives: list[Any]) -> dict[str, Any]:
    fields = _exact_dict(
        value,
        {
            "runtime_model",
            "pairing_validity",
            "effect_scale",
            "protected_objectives",
            "calibration_ref",
            "calibration_max_age_days",
            "readiness_summary",
        },
    )
    if fields["runtime_model"] not in {"comparative", "budget_exhausting"} or fields[
        "pairing_validity"
    ] not in {"trajectory_stable", "trajectory_divergent"}:
        raise ValueError
    effect = _exact_dict(
        fields["effect_scale"],
        {
            "metric",
            "unit",
            "practical_delta_screen",
            "practical_delta_validate",
        },
    )
    metric = _string(effect["metric"])
    if effect["unit"] not in {"raw_delta", "relative_pct"}:
        raise ValueError
    if (
        _finite_float(effect["practical_delta_screen"]) < 0.0
        or _finite_float(effect["practical_delta_validate"]) < 0.0
    ):
        raise ValueError
    names = {
        _string(
            _exact_dict(
                item, {"name", "direction", "priority", "tie_tolerance", "weight"}
            )["name"]
        )
        for item in objectives
    }
    if metric.strip() and metric.strip() not in names:
        raise ValueError
    protected = _string_list(fields["protected_objectives"])
    if len(protected) != len(set(protected)) or any(
        item not in names for item in protected
    ):
        raise ValueError
    _string(fields["calibration_ref"])
    if _integer(fields["calibration_max_age_days"]) < 0:
        raise ValueError
    _validate_readiness(fields["readiness_summary"])
    return fields


def _validate_readiness(value: Any) -> None:
    if value is None:
        return
    fields = _exact_dict(
        value,
        {
            "mde_at_power_80",
            "noise_band_p90_abs",
            "effect_to_mde_ratio",
            "signal_to_noise_tier",
            "n_pairs",
        },
    )
    for key in ("mde_at_power_80", "noise_band_p90_abs", "effect_to_mde_ratio"):
        number = _optional_float(fields[key])
        if number is not None and number < 0.0:
            raise ValueError
    if fields["signal_to_noise_tier"] not in {
        "ready",
        "marginal",
        "low_power",
        "unknown",
    }:
        raise ValueError
    if _integer(fields["n_pairs"]) < 0:
        raise ValueError


def _validate_llm_hints(value: Any) -> None:
    fields = _exact_dict(value, {"problem_summary", "operator_interface"})
    _string(fields["problem_summary"])
    _string(fields["operator_interface"])


def _validate_family(value: Any) -> None:
    if value is None:
        return
    fields = _exact_dict(value, {"version", "families", "aliases"})
    _string(fields["version"])
    _string_list(fields["families"])
    for item in _exact_dict_any(fields["aliases"]).values():
        _string_list(item)


def _validate_runtime_dependencies(value: Any) -> None:
    fields = _exact_dict(value, {"required_python_modules", "required_executables"})
    for item in fields.values():
        _normalized_unique_strings(item, allow_empty_list=True)


def _validate_runtime_failure_guidance(value: Any) -> None:
    for item in _exact_list(value):
        fields = _exact_dict(
            item,
            {
                "failure_categories",
                "applies_to_surfaces",
                "applies_to_surface_kinds",
                "min_category_fraction",
                "min_count",
                "recommended_surfaces",
                "discouraged_surfaces",
                "guidance",
            },
        )
        for key in (
            "failure_categories",
            "applies_to_surfaces",
            "applies_to_surface_kinds",
            "recommended_surfaces",
            "discouraged_surfaces",
        ):
            _normalized_unique_strings(fields[key], allow_empty_list=True)
        fraction = _finite_float(fields["min_category_fraction"])
        if not 0.0 <= fraction <= 1.0 or _integer(fields["min_count"]) < 1:
            raise ValueError
        _string(fields["guidance"])


def _validate_adapter(value: Any, *, problem_id: str) -> None:
    fields = _exact_dict(value, {"import_path", "api_version"})
    path = _string(fields["import_path"])
    if fields["api_version"] != "v1" or path.count(":") != 1:
        raise ValueError
    module_name, _class_name = path.split(":")
    if not module_name.startswith(f"scion.problems.{problem_id}."):
        raise ValueError


def _validate_development_paths(problem: dict[str, Any]) -> None:
    for key in (
        "unit_test_path",
        "regression_test_path",
        "development_unit_test_path",
        "development_regression_test_path",
    ):
        value = _string(problem[key])
        if value:
            _canonical_relative_path(value)
    for key in (
        "development_unit_test_support_paths",
        "development_regression_test_support_paths",
        "development_workspace_paths",
        "development_problem_package_paths",
    ):
        values = _string_list(problem[key])
        if len(values) != len(set(values)):
            raise ValueError
        for value in values:
            _canonical_relative_path(value)


def _validate_execute_signature(value: Any) -> None:
    signature = _string(value)
    if not signature:
        raise ValueError
    raw = signature.strip()
    if raw.startswith("def "):
        raw = raw[4:].strip()
    if raw.endswith(":"):
        raw = raw[:-1].strip()
    tree = ast.parse(f"def {raw}:\n    pass\n")
    if not tree.body or type(tree.body[0]) is not ast.FunctionDef:
        raise ValueError
    function = tree.body[0]
    if (
        function.name != "execute"
        or function.args.vararg is not None
        or function.args.kwarg is not None
        or function.args.kwonlyargs
        or function.args.defaults
    ):
        raise ValueError
    arguments = tuple(argument.arg for argument in function.args.args)
    if not arguments or arguments[0] != "self":
        raise ValueError


def _valid_mechanism_declaration(value: Any) -> bool:
    if type(value) is not str:
        return False
    declaration = value.strip()
    if _MECHANISM_ID_RE.fullmatch(declaration) or declaration == "*":
        return True
    return bool(
        "*" in declaration
        and _MECHANISM_DECLARATION_RE.fullmatch(declaration)
        and (declaration[0] == "*" or declaration[0].isalpha())
        and any(character != "*" for character in declaration)
    )


def _canonical_relative_path(value: str) -> None:
    if (
        not value
        or value != value.strip()
        or "\x00" in value
        or "\\" in value
        or value.startswith("/")
        or any(part in {"", ".", ".."} for part in value.split("/"))
        or any(character in value for character in "*?[")
    ):
        raise ValueError


def _normalized_unique_strings(
    value: Any, *, allow_empty_list: bool
) -> tuple[str, ...]:
    result = _string_list(value)
    if (not allow_empty_list and not result) or any(
        not item or item != item.strip() for item in result
    ):
        raise ValueError
    if len(result) != len(set(result)):
        raise ValueError
    return result


def _validate_json_value(value: Any) -> None:
    if value is None or type(value) in {str, bool, int}:
        return
    if type(value) is float:
        _finite_float(value)
        return
    if type(value) is list:
        for item in value:
            _validate_json_value(item)
        return
    if type(value) is dict:
        if any(type(key) is not str for key in value):
            raise TypeError
        for item in value.values():
            _validate_json_value(item)
        return
    raise TypeError


def _optional_ordered_float_pair(value: Any) -> None:
    if value is None:
        return
    lower, upper = _float_pair(value)
    if lower > upper:
        raise ValueError


def _float_pair(value: Any) -> tuple[float, float]:
    items = _exact_list(value)
    if len(items) != 2:
        raise ValueError
    return _finite_float(items[0]), _finite_float(items[1])


def _string_list(value: Any) -> tuple[str, ...]:
    return tuple(_string(item) for item in _exact_list(value))


def _exact_dict(value: Any, fields: set[str] | frozenset[str]) -> dict[str, Any]:
    if type(value) is not dict or any(type(key) is not str for key in value):
        raise TypeError
    if set(value) != fields:
        raise ValueError
    return value


def _exact_dict_any(value: Any) -> dict[str, Any]:
    if type(value) is not dict or any(type(key) is not str for key in value):
        raise TypeError
    return value


def _exact_list(value: Any) -> list[Any]:
    if type(value) is not list:
        raise TypeError
    return value


def _string(value: Any) -> str:
    if type(value) is not str:
        raise TypeError
    return value


def _boolean(value: Any) -> bool:
    if type(value) is not bool:
        raise TypeError
    return value


def _integer(value: Any) -> int:
    if type(value) is not int:
        raise TypeError
    return value


def _finite_float(value: Any) -> float:
    if type(value) is not float or not math.isfinite(value):
        raise TypeError
    return value


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return _finite_float(value)


__all__: tuple[str, ...] = ()
