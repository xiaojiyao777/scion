"""Declared mechanism runtime probe expansion."""
from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from scion.runtime.telemetry_guard.expected_schema import (
    EXPECTED_TELEMETRY_CATEGORIES,
    _GENERIC_FIELD_CONTAINER_KEYS,
    _WILDCARD_MECHANISM_KEYS,
    normalize_declared_mechanisms,
)
from scion.runtime.telemetry_guard.utils import _field, _string_list

_CATEGORY_PROBE_FIELD_NAMES: dict[str, tuple[str, ...]] = {
    "activation": (
        "activation_runtime_fields",
        "activation_runtime_paths",
        "activation_probe_runtime_fields",
        "mechanism_activation_runtime_fields",
        "mechanism_activation_runtime_paths",
    ),
    "effect": (
        "effect_probe_runtime_fields",
        "effect_probe_runtime_paths",
        "effect_runtime_fields",
        "effect_runtime_paths",
        "mechanism_effect_probe_runtime_fields",
        "mechanism_effect_probe_runtime_paths",
        "mechanism_effect_runtime_fields",
        "mechanism_effect_runtime_paths",
    ),
    "budget": (
        "stage_budget_runtime_fields",
        "stage_budget_runtime_paths",
        "budget_runtime_fields",
        "budget_runtime_paths",
        "mechanism_budget_runtime_fields",
        "mechanism_budget_runtime_paths",
        "mechanism_stage_budget_runtime_fields",
        "mechanism_stage_budget_runtime_paths",
    ),
}
_GENERIC_PROBE_CONTAINER_NAMES = (
    "mechanism_runtime_fields",
    "mechanism_runtime_paths",
    "mechanism_telemetry",
    "mechanism_probes",
    "runtime_mechanism_probes",
    "telemetry_mechanism_probes",
    "runtime_telemetry_probes",
    "telemetry_probes",
    "telemetry_guard_probes",
)


@dataclass(frozen=True)
class _MechanismProbe:
    mechanism: str
    category: str
    field: str
    source: str


def declared_mechanism_runtime_probes(
    *,
    problem_spec: Any | None,
    surface: Any | None,
    declared_mechanisms: Any = None,
) -> tuple[_MechanismProbe, ...]:
    """Expand adapter/surface declared mechanism probes into runtime paths."""

    mechanisms = normalize_declared_mechanisms(declared_mechanisms)
    if not mechanisms:
        return ()

    probes: list[_MechanismProbe] = []
    seen: set[tuple[str, str, str]] = set()
    for mechanism in mechanisms:
        for source_name, source in _mechanism_probe_sources(problem_spec, surface):
            for category in ("activation", "effect", "budget"):
                fields = _mechanism_probe_fields(source, mechanism, category)
                for field in fields:
                    key = (mechanism, category, field)
                    if key in seen:
                        continue
                    seen.add(key)
                    probes.append(
                        _MechanismProbe(
                            mechanism=mechanism,
                            category=category,
                            field=field,
                            source=source_name,
                        )
                    )
    return tuple(probes)


def _mechanism_probe_sources(
    problem_spec: Any | None,
    surface: Any | None,
) -> tuple[tuple[str, Any], ...]:
    evidence = _field(surface, "evidence")
    spec_evidence = _field(problem_spec, "evidence")
    sources: list[tuple[str, Any]] = []
    for name, source in (
        ("adapter", problem_spec),
        ("adapter.evidence", spec_evidence),
        ("adapter.telemetry_guard", _field(problem_spec, "telemetry_guard")),
        (
            "adapter.runtime_telemetry_guard",
            _field(problem_spec, "runtime_telemetry_guard"),
        ),
        ("adapter.telemetry_probes", _field(problem_spec, "telemetry_probes")),
        (
            "adapter.runtime_telemetry_probes",
            _field(problem_spec, "runtime_telemetry_probes"),
        ),
        ("surface", surface),
        ("surface.evidence", evidence),
        ("surface.telemetry_guard", _field(surface, "telemetry_guard")),
        (
            "surface.runtime_telemetry_guard",
            _field(surface, "runtime_telemetry_guard"),
        ),
        ("surface.telemetry_probes", _field(surface, "telemetry_probes")),
        (
            "surface.runtime_telemetry_probes",
            _field(surface, "runtime_telemetry_probes"),
        ),
        ("surface.evidence.telemetry_guard", _field(evidence, "telemetry_guard")),
        (
            "surface.evidence.runtime_telemetry_guard",
            _field(evidence, "runtime_telemetry_guard"),
        ),
    ):
        if source is not None:
            sources.append((name, source))
    return tuple(sources)


def _mechanism_probe_fields(
    source: Any,
    mechanism: str,
    category: str,
) -> tuple[str, ...]:
    fields: list[str] = []
    for field_name in _CATEGORY_PROBE_FIELD_NAMES.get(category, ()):
        fields.extend(
            _fields_for_mechanism(
                _field(source, field_name),
                mechanism=mechanism,
                category=category,
            )
        )
    for container_name in _GENERIC_PROBE_CONTAINER_NAMES:
        fields.extend(
            _fields_for_mechanism(
                _field(source, container_name),
                mechanism=mechanism,
                category=category,
            )
        )
    return tuple(dict.fromkeys(field for field in fields if field))


def _fields_for_mechanism(
    value: Any,
    *,
    mechanism: str,
    category: str | None,
) -> list[str]:
    if value in (None, "", [], (), {}):
        return []
    if isinstance(value, Mapping):
        fields: list[str] = []

        if category:
            for key in _category_field_keys(category):
                if key in value:
                    fields.extend(
                        _fields_for_mechanism(
                            value.get(key),
                            mechanism=mechanism,
                            category=None,
                        )
                    )

        for raw_key, raw_value in value.items():
            key = str(raw_key or "").strip()
            normalized_key = key.lower()
            if normalized_key in EXPECTED_TELEMETRY_CATEGORIES:
                continue
            if normalized_key in _GENERIC_FIELD_CONTAINER_KEYS:
                fields.extend(
                    _fields_for_mechanism(
                        raw_value,
                        mechanism=mechanism,
                        category=None,
                    )
                )
                continue
            if not _mechanism_probe_key_matches(key, mechanism):
                continue
            selected = raw_value
            if category and _has_category_probe_shape(selected):
                category_values: list[str] = []
                for category_key in _category_field_keys(category):
                    selected_value = _field(selected, category_key)
                    if selected_value is not None:
                        category_values.extend(
                            _fields_for_mechanism(
                                selected_value,
                                mechanism=mechanism,
                                category=None,
                            )
                        )
                if category_values:
                    fields.extend(category_values)
                continue
            fields.extend(
                _fields_for_mechanism(
                    selected,
                    mechanism=mechanism,
                    category=None,
                )
            )
        return _expand_mechanism_templates(fields, mechanism)
    return _expand_mechanism_templates(_string_list(value), mechanism)


def _category_field_keys(category: str) -> tuple[str, ...]:
    return (category, *_CATEGORY_PROBE_FIELD_NAMES.get(category, ()))


def _has_category_probe_shape(value: Any) -> bool:
    for category in ("activation", "effect", "budget"):
        for key in _category_field_keys(category):
            if _field(value, key) is not None:
                return True
    return False


def _mechanism_probe_key_matches(key: str, mechanism: str) -> bool:
    normalized_key = key.strip()
    if normalized_key == mechanism or normalized_key.lower() in _WILDCARD_MECHANISM_KEYS:
        return True
    if "*" not in normalized_key:
        return False
    pattern = re.escape(normalized_key).replace(r"\*", "[A-Za-z0-9_]*")
    return re.fullmatch(pattern, mechanism) is not None


def _expand_mechanism_templates(fields: Sequence[str], mechanism: str) -> list[str]:
    return [
        str(field).replace("{mechanism}", mechanism)
        for field in fields
        if str(field or "").strip()
    ]
