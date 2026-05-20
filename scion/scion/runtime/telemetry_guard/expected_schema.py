"""Expected telemetry schema normalization."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from scion.runtime.telemetry_guard.utils import (
    _append_field,
    _append_fields,
    _freeze_claims,
)

EXPECTED_TELEMETRY_CATEGORIES = frozenset(
    {"activity", "activation", "effect", "budget"}
)
_EXPECTED_TELEMETRY_META_KEYS = frozenset(
    {
        "mechanism",
        "mechanisms",
        "declared_mechanism",
        "declared_mechanisms",
        "declared_mechanism_change",
        "declared_mechanism_changes",
        "mechanism_change",
        "mechanism_changes",
    }
)
_MECHANISM_NOVELTY_KEYS = frozenset(
    {
        "mechanism",
        "mechanism_id",
        "mechanism_name",
        "declared_mechanism",
        "declared_mechanisms",
        "declared_mechanism_change",
        "declared_mechanism_changes",
    }
)
_WILDCARD_MECHANISM_KEYS = frozenset(
    {"*", "{mechanism}", "default", "__default__", "all", "__all__"}
)
_GENERIC_FIELD_CONTAINER_KEYS = frozenset(
    {
        "field",
        "fields",
        "path",
        "paths",
        "runtime_field",
        "runtime_fields",
        "runtime_path",
        "runtime_paths",
        "probes",
    }
)
_FRAMEWORK_RUNTIME_FIELD_EXACT_KEYS = frozenset(
    {
        "solver_algorithm_phase_runtime_ms",
        "solver_algorithm_context_records",
        "solver_algorithm_phase_delta_sum",
        "solver_algorithm_phase_best_delta",
        "solver_algorithm_phase_improvement_counts",
    }
)
_RUNTIME_FIELD_SUFFIXES = (
    "_runtime_ms",
    "_elapsed_ms",
    "_duration_ms",
    "_time_ms",
    "_iterations",
    "_attempts",
    "_moves",
    "_counts",
    "_records",
    "_delta",
    "_best_delta",
    "_objective",
    "_violation",
    "_routes",
    "_stop_reason",
)


def _expected_telemetry_category_errors(value: Any) -> tuple[str, ...]:
    if not isinstance(value, Mapping):
        return ()
    errors: list[str] = []
    for raw_category in value:
        category = str(raw_category or "").strip().lower()
        if not category or category in _EXPECTED_TELEMETRY_META_KEYS:
            continue
        if category not in EXPECTED_TELEMETRY_CATEGORIES:
            errors.append(
                f"expected_telemetry category '{category}' is not supported; "
                f"expected one of {sorted(EXPECTED_TELEMETRY_CATEGORIES)}"
            )
    return tuple(dict.fromkeys(errors))


def normalize_expected_telemetry(value: Any) -> dict[str, tuple[str, ...]]:
    """Return a category -> fields mapping from a flexible proposal payload."""

    claims: dict[str, list[str]] = {
        category: [] for category in EXPECTED_TELEMETRY_CATEGORIES
    }
    if value in (None, "", [], (), {}):
        return {category: () for category in sorted(EXPECTED_TELEMETRY_CATEGORIES)}

    if isinstance(value, str):
        _append_field(claims["effect"], value)
        return _freeze_claims(claims)
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
        for item in value:
            _append_field(claims["effect"], item)
        return _freeze_claims(claims)
    if not isinstance(value, Mapping):
        return _freeze_claims(claims)

    for raw_category, raw_fields in value.items():
        category = str(raw_category or "").strip().lower()
        if not category:
            continue
        if category in _EXPECTED_TELEMETRY_META_KEYS:
            continue
        target = claims.setdefault(category, [])
        _append_fields(target, raw_fields)
    return _freeze_claims(claims)


def normalize_declared_mechanisms(
    value: Any = None,
    *,
    expected_telemetry: Any = None,
    novelty_signature: Any = None,
) -> tuple[str, ...]:
    """Return stable mechanism ids declared by a proposal or telemetry payload."""

    mechanisms: list[str] = []
    _append_mechanisms(mechanisms, value)

    if isinstance(expected_telemetry, Mapping):
        for key, raw_value in expected_telemetry.items():
            normalized_key = str(key or "").strip().lower()
            if normalized_key in _EXPECTED_TELEMETRY_META_KEYS:
                _append_mechanisms(mechanisms, raw_value)
                continue
            if normalized_key not in EXPECTED_TELEMETRY_CATEGORIES:
                continue
            if not isinstance(raw_value, Mapping):
                continue
            for raw_mechanism in raw_value:
                mechanism = _clean_mechanism_name(raw_mechanism)
                if _is_explicit_mechanism_key(mechanism):
                    _append_mechanism(mechanisms, mechanism)

    if isinstance(novelty_signature, Mapping):
        for key, raw_value in novelty_signature.items():
            if str(key or "").strip().lower() in _MECHANISM_NOVELTY_KEYS:
                _append_mechanisms(mechanisms, raw_value)

    return tuple(dict.fromkeys(mechanisms))


def normalize_expected_telemetry_by_mechanism(
    value: Any,
) -> dict[str, dict[str, tuple[str, ...]]]:
    """Return mechanism -> category -> runtime fields for grouped claims."""

    if not isinstance(value, Mapping):
        return {}
    claims: dict[str, dict[str, list[str]]] = {}
    for raw_category, raw_fields in value.items():
        category = str(raw_category or "").strip().lower()
        if category not in EXPECTED_TELEMETRY_CATEGORIES:
            continue
        if not isinstance(raw_fields, Mapping):
            continue
        for raw_mechanism, mechanism_fields in raw_fields.items():
            mechanism = _clean_mechanism_name(raw_mechanism)
            if not _is_explicit_mechanism_key(mechanism):
                continue
            category_claims = claims.setdefault(
                mechanism,
                {name: [] for name in EXPECTED_TELEMETRY_CATEGORIES},
            )
            _append_fields(category_claims[category], mechanism_fields)
    return {
        mechanism: {
            category: tuple(fields)
            for category, fields in sorted(category_claims.items())
            if fields
        }
        for mechanism, category_claims in sorted(claims.items())
    }


def _append_mechanisms(target: list[str], value: Any) -> None:
    if value in (None, "", [], (), {}):
        return
    if isinstance(value, Mapping):
        for key in ("name", "mechanism", "id", "mechanism_id"):
            if key in value:
                _append_mechanisms(target, value.get(key))
                return
        for item in value.values():
            _append_mechanisms(target, item)
        return
    if isinstance(value, str):
        for part in value.split(","):
            _append_mechanism(target, part)
        return
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        for item in value:
            _append_mechanisms(target, item)
        return
    object_id = getattr(value, "id", None)
    if object_id is not None:
        _append_mechanisms(target, object_id)
        return
    _append_mechanism(target, value)


def _append_mechanism(target: list[str], value: Any) -> None:
    mechanism = _clean_mechanism_name(value)
    if not mechanism or mechanism in target:
        return
    target.append(mechanism)


def _clean_mechanism_name(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return text[:120]


def _is_explicit_mechanism_key(value: str) -> bool:
    key = str(value or "").strip().lower()
    return (
        bool(key)
        and key not in (
            _WILDCARD_MECHANISM_KEYS
            | _GENERIC_FIELD_CONTAINER_KEYS
            | EXPECTED_TELEMETRY_CATEGORIES
            | _EXPECTED_TELEMETRY_META_KEYS
        )
        and not _looks_like_runtime_field_key(key)
    )


def _looks_like_runtime_field_key(key: str) -> bool:
    if key in _FRAMEWORK_RUNTIME_FIELD_EXACT_KEYS:
        return True
    if "." in key or "[" in key or "]" in key:
        return True
    return key.startswith(("solver_", "runtime_", "candidate_", "champion_")) and (
        any(key.endswith(suffix) for suffix in _RUNTIME_FIELD_SUFFIXES)
    )
