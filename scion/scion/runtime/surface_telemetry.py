"""Problem-declared runtime telemetry helpers.

Generic runtime/protocol layers use this module to consume telemetry fields
declared by a problem surface without knowing the concrete field namespace.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

TELEMETRY_FIELD_ROLES = frozenset(
    {
        "activity",
        "aggregate_activity",
        "aggregate_effect",
        "budget",
        "diagnostic",
        "effect",
        "mechanism_activity",
        "mechanism_activation",
        "mechanism_effect",
        "objective_outcome",
        "outcome",
        "protected_outcome",
    }
)
_ROLE_MAPPING_FIELD_NAMES = (
    "runtime_field_roles",
    "telemetry_field_roles",
    "runtime_telemetry_roles",
    "field_roles",
)


def normalize_surface_name(name: str | None) -> str:
    surface_name = str(name or "").strip()
    if surface_name == "solver_algorithm":
        return "solver_design"
    return surface_name


def find_research_surface(problem_spec: Any | None, name: str | None) -> Any | None:
    surface_name = normalize_surface_name(name)
    if not surface_name:
        return None
    for surface in _field(problem_spec, "research_surfaces") or ():
        if str(_field(surface, "name") or "").strip() == surface_name:
            return surface
    return None


def declared_surface_telemetry_fields(
    surface: Any | None,
    *,
    problem_spec: Any | None = None,
    declared_mechanisms: Sequence[str] = (),
    include_templates: bool = False,
) -> frozenset[str]:
    """Return all runtime fields declared by a research surface."""

    evidence = _field(surface, "evidence")
    fields: set[str] = set()
    for name in (
        "required_runtime_fields",
        "optional_runtime_fields",
        "activity_runtime_fields",
        "effect_probe_runtime_fields",
        "phase_runtime_fields",
        "stage_budget_runtime_fields",
    ):
        fields.update(_string_list(_field(evidence, name)))
    fields.update(_string_list(_field(evidence, "activation_runtime_fields")))
    for telemetry in _mechanism_telemetry_values(evidence):
        fields.update(_string_list(_field(telemetry, "activation_runtime_fields")))
        fields.update(_string_list(_field(telemetry, "effect_probe_runtime_fields")))
    for role_fields in declared_runtime_field_roles(
        surface,
        problem_spec=problem_spec,
        declared_mechanisms=declared_mechanisms,
        include_templates=include_templates,
    ).values():
        fields.update(role_fields)
    return frozenset(
        field
        for field in fields
        if _is_runtime_field_declaration(
            field,
            include_templates=include_templates,
        )
    )


def declared_runtime_field_roles(
    surface: Any | None,
    *,
    problem_spec: Any | None = None,
    declared_mechanisms: Sequence[str] = (),
    include_templates: bool = False,
) -> dict[str, frozenset[str]]:
    """Return role -> runtime fields declared by the selected surface."""

    evidence = _field(surface, "evidence")
    roles: dict[str, set[str]] = {}
    _add_role_fields(
        roles,
        "activity",
        _string_list(_field(evidence, "activity_runtime_fields")),
        declared_mechanisms=declared_mechanisms,
        include_templates=include_templates,
    )
    _add_role_fields(
        roles,
        "mechanism_activation",
        _string_list(_field(evidence, "activation_runtime_fields")),
        declared_mechanisms=declared_mechanisms,
        include_templates=include_templates,
    )
    _add_role_fields(
        roles,
        "effect",
        _string_list(_field(evidence, "effect_probe_runtime_fields")),
        declared_mechanisms=declared_mechanisms,
        include_templates=include_templates,
    )
    _add_role_fields(
        roles,
        "budget",
        _string_list(_field(evidence, "stage_budget_runtime_fields")),
        declared_mechanisms=declared_mechanisms,
        include_templates=include_templates,
    )
    for telemetry in _mechanism_telemetry_values(evidence):
        _add_role_fields(
            roles,
            "mechanism_activation",
            _string_list(_field(telemetry, "activation_runtime_fields")),
            declared_mechanisms=declared_mechanisms,
            include_templates=include_templates,
        )
        _add_role_fields(
            roles,
            "mechanism_effect",
            _string_list(_field(telemetry, "effect_probe_runtime_fields")),
            declared_mechanisms=declared_mechanisms,
            include_templates=include_templates,
        )

    for source in _role_mapping_sources(
        surface=surface,
        evidence=evidence,
        problem_spec=problem_spec,
    ):
        _merge_role_mapping(
            roles,
            source,
            declared_mechanisms=declared_mechanisms,
            include_templates=include_templates,
        )
    return {
        role: frozenset(fields)
        for role, fields in sorted(roles.items())
        if role and fields
    }


def runtime_field_roles_for(
    field: str,
    role_map: Mapping[str, Sequence[str] | frozenset[str]],
) -> frozenset[str]:
    field_text = str(field or "").strip()
    if not field_text:
        return frozenset()
    roles = [
        role
        for role, fields in role_map.items()
        if field_text in {str(item) for item in fields}
    ]
    return frozenset(roles)


def declared_error_runtime_fields(
    surface: Any | None,
    *,
    problem_spec: Any | None = None,
) -> tuple[str, ...]:
    role_map = declared_runtime_field_roles(surface, problem_spec=problem_spec)
    if not role_map:
        return ()
    fields = declared_surface_telemetry_fields(surface, problem_spec=problem_spec)
    result = [
        field
        for field in sorted(fields)
        if _is_error_count_field(field)
        and "diagnostic" in runtime_field_roles_for(field, role_map)
    ]
    return tuple(dict.fromkeys(result))


def declared_stop_reason_fields(
    surface: Any | None,
    *,
    problem_spec: Any | None = None,
) -> tuple[str, ...]:
    fields = declared_surface_telemetry_fields(surface, problem_spec=problem_spec)
    return tuple(
        field
        for field in sorted(fields)
        if str(field or "").strip().replace(".", "_").endswith("stop_reason")
    )


def declared_phase_runtime_fields(
    surface: Any | None,
    *,
    problem_spec: Any | None = None,
) -> tuple[str, ...]:
    """Return adapter-declared runtime fields that carry phase/bucket timings."""

    evidence = _field(surface, "evidence")
    fields: list[str] = []
    fields.extend(_string_list(_field(evidence, "phase_runtime_fields")))
    fields.extend(
        field
        for field in declared_surface_telemetry_fields(
            surface,
            problem_spec=problem_spec,
        )
        if str(field or "").strip().replace(".", "_").endswith("phase_runtime_ms")
    )
    return tuple(dict.fromkeys(field for field in fields if _is_concrete_runtime_field(field)))


def declared_phase_telemetry_buckets(
    surface: Any | None,
    *,
    problem_spec: Any | None = None,
) -> tuple[str, ...]:
    """Return adapter-declared phase/bucket names for summary projection."""

    evidence = _field(surface, "evidence")
    buckets: list[str] = []
    for owner in (
        _field(problem_spec, "evidence"),
        problem_spec,
        evidence,
        surface,
    ):
        buckets.extend(_string_list(_field(owner, "phase_telemetry_buckets")))
        buckets.extend(_string_list(_field(owner, "runtime_phase_buckets")))
        buckets.extend(_string_list(_field(owner, "phase_runtime_buckets")))
    return tuple(dict.fromkeys(bucket for bucket in buckets if bucket))


def declared_counter_runtime_fields(
    surface: Any | None,
    *,
    problem_spec: Any | None = None,
) -> tuple[str, ...]:
    role_map = declared_runtime_field_roles(surface, problem_spec=problem_spec)
    fields = declared_surface_telemetry_fields(surface, problem_spec=problem_spec)
    blocked_roles = {"objective_outcome", "outcome", "protected_outcome"}
    counter_roles = {
        "activity",
        "aggregate_activity",
        "aggregate_effect",
        "budget",
        "diagnostic",
        "effect",
        "mechanism_activity",
        "mechanism_activation",
        "mechanism_effect",
    }
    result: list[str] = []
    for field in sorted(fields):
        roles = runtime_field_roles_for(field, role_map)
        if roles & blocked_roles:
            continue
        if roles and not roles & counter_roles:
            continue
        if _is_runtime_counter_field(field) or roles & counter_roles:
            result.append(field)
    return tuple(dict.fromkeys(result))


def declared_event_fields_for(
    runtime: Mapping[str, Any],
    field: str,
) -> tuple[str, ...]:
    component = component_from_runtime_field(field)
    candidates = [
        f"{component}_events" if component else "",
        f"{component}.events" if component else "",
        field.removesuffix("_errors") + "_events"
        if field.endswith("_errors")
        else "",
        field.removesuffix(".errors") + ".events"
        if field.endswith(".errors")
        else "",
    ]
    return tuple(
        dict.fromkeys(
            candidate
            for candidate in candidates
            if candidate and runtime_path_present(runtime, candidate)
        )
    )


def declared_sibling_field(
    runtime: Mapping[str, Any],
    field: str,
    suffix: str,
) -> str | None:
    component = component_from_runtime_field(field)
    if not component:
        return None
    candidates = (f"{component}_{suffix}", f"{component}.{suffix}")
    for candidate in candidates:
        if runtime_path_present(runtime, candidate):
            return candidate
    return None


def component_from_runtime_field(field: str) -> str:
    text = str(field or "").strip()
    for suffix in (
        "_errors",
        ".errors",
        "_error_count",
        ".error_count",
        "_invalid_outputs",
        ".invalid_outputs",
    ):
        if text.endswith(suffix):
            return text[: -len(suffix)]
    for suffix in (
        "_elapsed_ms",
        ".elapsed_ms",
        "_phase_runtime_ms",
        ".phase_runtime_ms",
        "_runtime_ms",
        ".runtime_ms",
    ):
        if text.endswith(suffix):
            return text[: -len(suffix)]
    if "." in text:
        return text.rsplit(".", 1)[0]
    if "_" in text:
        return text.rsplit("_", 1)[0]
    return text


def runtime_path_value(runtime: Mapping[str, Any], field: str) -> Any:
    text = str(field or "").strip()
    if not text:
        return None
    if text in runtime:
        return runtime[text]
    current: Any = runtime
    for part in text.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return None
        current = current[part]
    return current


def runtime_path_present(runtime: Mapping[str, Any], field: str) -> bool:
    text = str(field or "").strip()
    if not text:
        return False
    if text in runtime:
        return True
    current: Any = runtime
    for part in text.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return False
        current = current[part]
    return True


def _role_mapping_sources(
    *,
    surface: Any | None,
    evidence: Any | None,
    problem_spec: Any | None,
) -> tuple[Any, ...]:
    sources: list[Any] = []
    for owner in (
        _field(problem_spec, "telemetry_guard"),
        _field(problem_spec, "runtime_telemetry_guard"),
        _field(problem_spec, "telemetry_probes"),
        _field(problem_spec, "runtime_telemetry_probes"),
        _field(_field(problem_spec, "evidence"), "telemetry_guard"),
        _field(_field(problem_spec, "evidence"), "runtime_telemetry_guard"),
        evidence,
        surface,
        _field(evidence, "telemetry_guard"),
        _field(evidence, "runtime_telemetry_guard"),
        _field(surface, "telemetry_guard"),
        _field(surface, "runtime_telemetry_guard"),
    ):
        if owner is None:
            continue
        for field_name in _ROLE_MAPPING_FIELD_NAMES:
            source = _field(owner, field_name)
            if source is not None:
                sources.append(source)
    return tuple(sources)


def _merge_role_mapping(
    roles: dict[str, set[str]],
    value: Any,
    *,
    declared_mechanisms: Sequence[str],
    include_templates: bool,
) -> None:
    if not isinstance(value, Mapping):
        return
    for raw_key, raw_value in value.items():
        key = str(raw_key or "").strip()
        normalized_key = key.lower()
        if normalized_key in TELEMETRY_FIELD_ROLES:
            _add_role_fields(
                roles,
                normalized_key,
                _string_list(raw_value),
                declared_mechanisms=declared_mechanisms,
                include_templates=include_templates,
            )
            continue
        for role in _string_list(raw_value):
            normalized_role = str(role or "").strip().lower()
            if normalized_role not in TELEMETRY_FIELD_ROLES:
                continue
            _add_role_fields(
                roles,
                normalized_role,
                [key],
                declared_mechanisms=declared_mechanisms,
                include_templates=include_templates,
            )


def _add_role_fields(
    roles: dict[str, set[str]],
    role: str,
    fields: Sequence[str],
    *,
    declared_mechanisms: Sequence[str],
    include_templates: bool,
) -> None:
    normalized_role = str(role or "").strip().lower()
    if normalized_role not in TELEMETRY_FIELD_ROLES:
        return
    target = roles.setdefault(normalized_role, set())
    for field in fields:
        for expanded in _expand_mechanism_templates(
            field,
            declared_mechanisms,
            include_templates=include_templates,
        ):
            if _is_runtime_field_declaration(
                expanded,
                include_templates=include_templates,
            ):
                target.add(expanded)


def _expand_mechanism_templates(
    field: str,
    declared_mechanisms: Sequence[str],
    *,
    include_templates: bool = False,
) -> tuple[str, ...]:
    text = str(field or "").strip()
    if not text:
        return ()
    if "{mechanism}" not in text:
        return (text,)
    mechanisms = [str(item).strip() for item in declared_mechanisms if str(item).strip()]
    if not mechanisms:
        return (text,) if include_templates else ()
    return tuple(text.replace("{mechanism}", mechanism) for mechanism in mechanisms)


def _mechanism_telemetry_values(evidence: Any | None) -> tuple[Any, ...]:
    telemetry = _field(evidence, "mechanism_telemetry")
    if not isinstance(telemetry, Mapping):
        return ()
    return tuple(telemetry.values())


def _field(obj: Any, name: str) -> Any:
    if obj is None:
        return None
    if isinstance(obj, Mapping):
        return obj.get(name)
    return getattr(obj, name, None)


def _string_list(value: Any) -> list[str]:
    if value in (None, "", [], (), {}):
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, Mapping):
        result: list[str] = []
        for item in value.values():
            result.extend(_string_list(item))
        return result
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
        result = []
        for item in value:
            text = str(item or "").strip()
            if text:
                result.append(text)
        return result
    text = str(value or "").strip()
    return [text] if text else []


def _is_concrete_runtime_field(field: str) -> bool:
    text = str(field or "").strip()
    return bool(text) and "{" not in text and "}" not in text


def _is_runtime_field_declaration(
    field: str,
    *,
    include_templates: bool,
) -> bool:
    text = str(field or "").strip()
    if _is_concrete_runtime_field(text):
        return True
    if not include_templates:
        return False
    if "{mechanism}" not in text:
        return False
    return _is_concrete_runtime_field(text.replace("{mechanism}", "mechanism"))


def _is_error_count_field(field: str) -> bool:
    text = str(field or "").strip()
    return text.endswith("_errors") or text.endswith(".errors")


def _looks_diagnostic_field(field: str) -> bool:
    text = str(field or "").strip().replace(".", "_")
    return text.endswith(("_errors", "_loaded", "_active", "_stop_reason"))


def _is_runtime_counter_field(field: str) -> bool:
    text = str(field or "").strip().replace(".", "_")
    return text.endswith(
        (
            "_errors",
            "_iterations",
            "_attempts",
            "_moves",
            "_calls",
            "_elapsed_ms",
            "_runtime_ms",
            "_best_delta",
            "_delta_sum",
            "_improvement_counts",
        )
    )
