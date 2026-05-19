from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from scion.core.models import RunResult
from .values import (
    _as_truthy,
    _bounded_json_value,
    _coerce_number,
    _parse_int,
    _round_runtime_number,
    _safe_int,
)


def _surface_runtime_summary_template(
    *,
    selected_surface: str | None,
    required_fields: Sequence[str],
) -> dict[str, Any]:
    fields = tuple(str(field).strip() for field in required_fields if str(field).strip())
    surface = (selected_surface or "").strip()
    if not surface or not fields:
        return {}
    return {
        "selected_surface": surface,
        "required_runtime_fields": fields,
        "candidate_pairs": 0,
        "runtime_observed_pairs": 0,
        "runtime_missing_pairs": 0,
        "_fields": {
            field: {
                "present": 0,
                "missing": 0,
                "empty": 0,
                "failed": 0,
                "values": {},
            }
            for field in fields
        },
    }


def _record_surface_runtime_sample(
    result: RunResult,
    summary: dict[str, Any],
) -> None:
    if not summary:
        return
    summary["candidate_pairs"] += 1
    runtime = getattr(getattr(result, "output", None), "runtime", None)
    fields: dict[str, dict[str, Any]] = summary["_fields"]
    if not isinstance(runtime, dict):
        summary["runtime_missing_pairs"] += 1
        for field_summary in fields.values():
            field_summary["missing"] += 1
        return

    summary["runtime_observed_pairs"] += 1
    for field, field_summary in fields.items():
        if field not in runtime:
            field_summary["missing"] += 1
            continue
        value = runtime[field]
        if _is_empty_runtime_evidence_value(value):
            field_summary["empty"] += 1
        if _is_runtime_error_count_field(field):
            count = _parse_int(value)
            if count is None or count > 0:
                field_summary["failed"] += 1
        elif _is_runtime_true_evidence_field(field) and not _as_truthy(value):
            field_summary["failed"] += 1
        field_summary["present"] += 1
        value_key = _surface_runtime_value_key(value)
        values = field_summary["values"]
        values[value_key] = values.get(value_key, 0) + 1


def _finalize_surface_runtime_summary(summary: dict[str, Any]) -> dict[str, Any]:
    if not summary:
        return {}
    fields: dict[str, dict[str, Any]] = summary.get("_fields") or {}
    return {
        "selected_surface": summary.get("selected_surface"),
        "required_runtime_fields": list(summary.get("required_runtime_fields") or ()),
        "candidate_pairs": summary.get("candidate_pairs", 0),
        "runtime_observed_pairs": summary.get("runtime_observed_pairs", 0),
        "runtime_missing_pairs": summary.get("runtime_missing_pairs", 0),
        "fields": {
            field: {
                "present": field_summary.get("present", 0),
                "missing": field_summary.get("missing", 0),
                "empty": field_summary.get("empty", 0),
                "failed": field_summary.get("failed", 0),
                "numeric_summary": _surface_runtime_numeric_summary(
                    field_summary.get("values") or {}
                ),
                "values": [
                    {"value": value, "count": count}
                    for value, count in sorted(
                        (field_summary.get("values") or {}).items(),
                        key=lambda item: (-int(item[1]), item[0]),
                    )[:5]
                ],
            }
            for field, field_summary in fields.items()
        },
    }


def _surface_runtime_summary_with_guard(
    summary: dict[str, Any],
    telemetry_guard: Mapping[str, Any],
) -> dict[str, Any]:
    payload = _finalize_surface_runtime_summary(summary)
    if telemetry_guard and (
        payload
        or telemetry_guard.get("expected_telemetry_present")
        or telemetry_guard.get("failures")
        or telemetry_guard.get("warnings")
    ):
        payload["telemetry_guard"] = dict(telemetry_guard)
    return payload


def _surface_runtime_numeric_summary(values: dict[str, int]) -> dict[str, Any]:
    scalar = _numeric_scalar_summary(values)
    mapping = _numeric_mapping_summary(values)
    summary: dict[str, Any] = {}
    if scalar:
        summary["scalar"] = scalar
    if mapping:
        summary["mapping"] = mapping
    return summary


def _numeric_scalar_summary(values: dict[str, int]) -> dict[str, Any]:
    count = 0
    zero_count = 0
    nonzero_count = 0
    positive_count = 0
    negative_count = 0
    weighted_sum = 0.0
    minimum: float | None = None
    maximum: float | None = None
    for value_key, raw_count in values.items():
        parsed = _parse_surface_runtime_value(value_key)
        number = _coerce_number(parsed)
        if number is None:
            continue
        item_count = _safe_int(raw_count)
        if item_count <= 0:
            continue
        count += item_count
        weighted_sum += number * item_count
        minimum = number if minimum is None else min(minimum, number)
        maximum = number if maximum is None else max(maximum, number)
        if abs(number) <= 1e-12:
            zero_count += item_count
        else:
            nonzero_count += item_count
        if number > 0:
            positive_count += item_count
        if number < 0:
            negative_count += item_count
    if count == 0:
        return {}
    return {
        "observed_count": count,
        "weighted_sum": _round_runtime_number(weighted_sum),
        "min": _round_runtime_number(minimum),
        "max": _round_runtime_number(maximum),
        "zero_count": zero_count,
        "nonzero_count": nonzero_count,
        "positive_count": positive_count,
        "negative_count": negative_count,
    }


def _numeric_mapping_summary(values: dict[str, int]) -> dict[str, Any]:
    by_key: dict[str, dict[str, Any]] = {}
    for value_key, raw_count in values.items():
        parsed = _parse_surface_runtime_value(value_key)
        if not isinstance(parsed, dict):
            continue
        item_count = _safe_int(raw_count)
        if item_count <= 0:
            continue
        for key, raw_value in parsed.items():
            if len(by_key) >= 16 and str(key) not in by_key:
                continue
            number = _coerce_number(raw_value)
            if number is None:
                continue
            key_text = str(key)[:80]
            stats = by_key.setdefault(
                key_text,
                {
                    "observed_count": 0,
                    "weighted_sum": 0.0,
                    "min": None,
                    "max": None,
                    "zero_count": 0,
                    "nonzero_count": 0,
                    "positive_count": 0,
                    "negative_count": 0,
                },
            )
            stats["observed_count"] += item_count
            stats["weighted_sum"] += number * item_count
            stats["min"] = number if stats["min"] is None else min(stats["min"], number)
            stats["max"] = number if stats["max"] is None else max(stats["max"], number)
            if abs(number) <= 1e-12:
                stats["zero_count"] += item_count
            else:
                stats["nonzero_count"] += item_count
            if number > 0:
                stats["positive_count"] += item_count
            if number < 0:
                stats["negative_count"] += item_count
    compact: dict[str, Any] = {}
    for key, stats in by_key.items():
        compact[key] = {
            "observed_count": stats["observed_count"],
            "weighted_sum": _round_runtime_number(stats["weighted_sum"]),
            "min": _round_runtime_number(stats["min"]),
            "max": _round_runtime_number(stats["max"]),
            "zero_count": stats["zero_count"],
            "nonzero_count": stats["nonzero_count"],
            "positive_count": stats["positive_count"],
            "negative_count": stats["negative_count"],
        }
    return compact


def _parse_surface_runtime_value(value_key: str) -> Any:
    try:
        return json.loads(value_key)
    except (TypeError, ValueError):
        return value_key


def _surface_runtime_value_key(value: Any) -> str:
    bounded = _bounded_json_value(value, max_items=12, max_chars=240)
    try:
        text = json.dumps(bounded, sort_keys=True, separators=(",", ":"), default=str)
    except TypeError:
        text = str(bounded)
    if len(text) <= 240:
        return text
    return text[:237] + "..."


def _is_empty_runtime_evidence_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, dict, set, frozenset)):
        return len(value) == 0
    return False


def _is_runtime_error_count_field(field_name: str) -> bool:
    return field_name.endswith("_errors") or field_name.endswith("_error_count")


def _is_runtime_true_evidence_field(field_name: str) -> bool:
    return field_name.endswith("_loaded") or field_name.endswith("_executed")


__all__ = [
    "_finalize_surface_runtime_summary",
    "_is_empty_runtime_evidence_value",
    "_is_runtime_error_count_field",
    "_is_runtime_true_evidence_field",
    "_numeric_mapping_summary",
    "_numeric_scalar_summary",
    "_parse_surface_runtime_value",
    "_record_surface_runtime_sample",
    "_surface_runtime_numeric_summary",
    "_surface_runtime_summary_template",
    "_surface_runtime_summary_with_guard",
    "_surface_runtime_value_key",
]
