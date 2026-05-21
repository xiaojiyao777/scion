"""Declared expected-telemetry repair guidance."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from scion.runtime.audit import normalize_surface_name
from scion.runtime.telemetry_guard.declarations import (
    declared_runtime_field_roles,
    find_research_surface,
)
from scion.runtime.telemetry_guard.expected_schema import (
    normalize_declared_mechanisms,
)
from scion.runtime.telemetry_guard.mechanism_probes import (
    declared_mechanism_runtime_probes,
)


def expected_telemetry_template(
    *,
    problem_spec: Any | None,
    selected_surface: str | None,
    declared_mechanisms: Any = None,
    max_fields_per_category: int = 5,
) -> dict[str, Any]:
    """Return a surface-declared expected_telemetry template.

    The template is intentionally problem-agnostic: concrete field names come
    only from the selected surface evidence and provider/runtime role metadata.
    """

    surface_name = normalize_surface_name(selected_surface)
    mechanism_ids = normalize_declared_mechanisms(declared_mechanisms)
    template_mechanisms = mechanism_ids or ("<mechanism_id>",)
    surface = find_research_surface(problem_spec, surface_name)
    role_map = declared_runtime_field_roles(
        surface,
        problem_spec=problem_spec,
        declared_mechanisms=template_mechanisms,
    )
    probes = declared_mechanism_runtime_probes(
        problem_spec=problem_spec,
        surface=surface,
        declared_mechanisms=template_mechanisms,
    )
    probe_fields_by_category = {
        category: tuple(probe.field for probe in probes if probe.category == category)
        for category in ("activation", "effect", "budget")
    }

    expected = {
        "activity": _template_fields(
            role_map,
            ("activity", "mechanism_activity"),
            mechanisms=template_mechanisms,
            max_fields=max_fields_per_category,
        ),
        "activation": _template_fields(
            role_map,
            ("mechanism_activation", "mechanism_activity"),
            fallback=probe_fields_by_category.get("activation", ()),
            mechanisms=template_mechanisms,
            max_fields=max_fields_per_category,
            prefer_mechanism_specific=True,
        ),
        "budget": _template_fields(
            role_map,
            ("budget",),
            fallback=probe_fields_by_category.get("budget", ()),
            mechanisms=template_mechanisms,
            max_fields=max_fields_per_category,
            prefer_mechanism_specific=True,
        ),
        "effect": _template_fields(
            role_map,
            ("mechanism_effect", "effect"),
            fallback=probe_fields_by_category.get("effect", ()),
            mechanisms=template_mechanisms,
            max_fields=max_fields_per_category,
            prefer_mechanism_specific=True,
        ),
    }
    return {
        key: value
        for key, value in {
            "selected_surface": surface_name or None,
            "mechanism_id": template_mechanisms[0],
            "expected_telemetry": {
                category: fields
                for category, fields in expected.items()
                if fields
            },
        }.items()
        if value not in (None, "", {}, [], ())
    }


def expected_telemetry_guidance(
    *,
    problem_spec: Any | None,
    selected_surface: str | None,
    declared_mechanisms: Any = None,
    max_fields_per_category: int = 5,
) -> str:
    """Return a compact human-readable legal-field template."""

    template = expected_telemetry_template(
        problem_spec=problem_spec,
        selected_surface=selected_surface,
        declared_mechanisms=declared_mechanisms,
        max_fields_per_category=max_fields_per_category,
    )
    expected = template.get("expected_telemetry")
    if not isinstance(expected, Mapping) or not expected:
        return ""
    parts: list[str] = []
    for category in ("activation", "budget", "effect", "activity"):
        fields = expected.get(category)
        if isinstance(fields, Sequence) and not isinstance(fields, (str, bytes)):
            rendered = ", ".join(str(field) for field in fields if str(field or ""))
            if rendered:
                parts.append(f"{category}=[{rendered}]")
    if not parts:
        return ""
    surface = template.get("selected_surface") or selected_surface or "<surface>"
    mechanism = template.get("mechanism_id") or "<mechanism_id>"
    return (
        "Legal expected_telemetry template for "
        f"selected_surface={surface!r}, mechanism_id={mechanism!r}: "
        + "; ".join(parts)
    )


def _template_fields(
    role_map: Mapping[str, Any],
    roles: Sequence[str],
    *,
    fallback: Sequence[str] = (),
    mechanisms: Sequence[str],
    max_fields: int,
    prefer_mechanism_specific: bool = False,
) -> list[str]:
    fields: list[str] = []
    for role in roles:
        value = role_map.get(role)
        if isinstance(value, (list, tuple, set, frozenset)):
            role_fields = [str(field) for field in value if str(field or "")]
            fields.extend(sorted(role_fields))
    if not fields:
        fields.extend(str(field) for field in fallback if str(field or ""))
    fields = list(dict.fromkeys(fields))
    if prefer_mechanism_specific:
        specific = [
            field
            for field in fields
            if _field_mentions_declared_mechanism(field, mechanisms)
        ]
        if specific:
            fields = specific
    return fields[: max(1, int(max_fields))]


def _field_mentions_declared_mechanism(
    field: str,
    mechanisms: Sequence[str],
) -> bool:
    text = str(field or "")
    if "{mechanism}" in text or "<mechanism_id>" in text:
        return True
    return any(
        str(mechanism or "").strip()
        and str(mechanism or "").strip() in text
        for mechanism in mechanisms
    )
