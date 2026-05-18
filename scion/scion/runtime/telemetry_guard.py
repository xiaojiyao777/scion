"""Generic runtime telemetry sanity guards for declared research surfaces."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from scion.runtime.audit import normalize_surface_name

EXPECTED_TELEMETRY_CATEGORIES = frozenset(
    {"activity", "activation", "effect", "budget"}
)

_ACTIVITY_SUFFIXES = (
    "_search_iterations",
    "_iterations",
    "_move_attempts",
    "_attempts",
)
_EFFECT_SUFFIXES = (
    "_improving_moves",
    "_best_improving_moves",
    "_best_delta",
    "_phase_delta_sum",
    "_phase_best_delta",
    "_phase_improvement_counts",
    "_improvement_counts",
)
_BUDGET_SUFFIXES = (
    "_stage_budget_ms",
    "_stage_budget_ratio",
    "_phase_budget_ms",
    "_phase_budget_ratio",
    "_phase_runtime_ms",
    "_runtime_ms",
    "_elapsed_ms",
)


def validate_expected_telemetry_contract(
    *,
    problem_spec: Any | None,
    selected_surface: str | None,
    expected_telemetry: Any,
) -> tuple[str, ...]:
    """Validate proposal-declared telemetry keys against adapter declarations."""

    claims = normalize_expected_telemetry(expected_telemetry)
    if not any(claims.values()):
        return ()

    surface_name = normalize_surface_name(selected_surface)
    if not surface_name:
        return ("expected_telemetry requires a selected research surface",)

    surface = find_research_surface(problem_spec, surface_name)
    if surface is None:
        return (
            f"selected research surface '{surface_name}' is not declared "
            "in problem_spec.research_surfaces",
        )

    allowed = declared_surface_telemetry_fields(surface)
    if not allowed:
        return (
            f"research surface '{surface_name}' does not declare telemetry "
            "fields in surface.evidence",
        )

    errors: list[str] = []
    for category, fields in claims.items():
        if category not in EXPECTED_TELEMETRY_CATEGORIES:
            errors.append(
                f"expected_telemetry category '{category}' is not supported; "
                f"expected one of {sorted(EXPECTED_TELEMETRY_CATEGORIES)}"
            )
            continue
        unknown = [field for field in fields if field not in allowed]
        if unknown:
            errors.append(
                f"expected_telemetry.{category} references undeclared "
                f"runtime field(s): {', '.join(sorted(unknown))}"
            )
    return tuple(errors)


def normalize_expected_telemetry(value: Any) -> dict[str, tuple[str, ...]]:
    """Return a category -> fields mapping from a flexible proposal payload."""

    claims: dict[str, list[str]] = {category: [] for category in EXPECTED_TELEMETRY_CATEGORIES}
    if value in (None, "", [], (), {}):
        return {category: () for category in sorted(EXPECTED_TELEMETRY_CATEGORIES)}

    if isinstance(value, str):
        _append_field(claims["effect"], value)
        return _freeze_claims(claims)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            _append_field(claims["effect"], item)
        return _freeze_claims(claims)
    if not isinstance(value, Mapping):
        return _freeze_claims(claims)

    for raw_category, raw_fields in value.items():
        category = str(raw_category or "").strip().lower()
        if not category:
            continue
        target = claims.setdefault(category, [])
        _append_fields(target, raw_fields)
    return _freeze_claims(claims)


def declared_surface_telemetry_fields(surface: Any | None) -> frozenset[str]:
    """Return all runtime telemetry fields a surface exposes for guard use."""

    evidence = _field(surface, "evidence")
    fields: set[str] = set()
    for name in (
        "required_runtime_fields",
        "optional_runtime_fields",
        "activity_runtime_fields",
        "effect_probe_runtime_fields",
        "stage_budget_runtime_fields",
    ):
        fields.update(_string_list(_field(evidence, name)))
    activation = _field(evidence, "activation_runtime_fields")
    if isinstance(activation, Mapping):
        for value in activation.values():
            fields.update(_string_list(value))
    else:
        fields.update(_string_list(activation))
    return frozenset(field for field in fields if field)


def declared_activity_runtime_fields(surface: Any | None) -> tuple[str, ...]:
    evidence = _field(surface, "evidence")
    explicit = _string_list(_field(evidence, "activity_runtime_fields"))
    if explicit:
        return tuple(explicit)
    declared = _string_list(_field(evidence, "required_runtime_fields"))
    return tuple(_fields_with_suffix(declared, _ACTIVITY_SUFFIXES))


def declared_effect_probe_runtime_fields(surface: Any | None) -> tuple[str, ...]:
    evidence = _field(surface, "evidence")
    explicit = _string_list(_field(evidence, "effect_probe_runtime_fields"))
    if explicit:
        return tuple(explicit)
    declared = _string_list(_field(evidence, "required_runtime_fields"))
    return tuple(_fields_with_suffix(declared, _EFFECT_SUFFIXES))


def declared_stage_budget_runtime_fields(surface: Any | None) -> tuple[str, ...]:
    evidence = _field(surface, "evidence")
    explicit = _string_list(_field(evidence, "stage_budget_runtime_fields"))
    if explicit:
        return tuple(explicit)
    declared = _string_list(_field(evidence, "required_runtime_fields"))
    return tuple(_fields_with_suffix(declared, _BUDGET_SUFFIXES))


def build_telemetry_guard_summary(
    *,
    candidate_runtimes: Sequence[Mapping[str, Any]],
    champion_runtimes: Sequence[Mapping[str, Any]] = (),
    problem_spec: Any | None,
    selected_surface: str | None,
    expected_telemetry: Any = None,
    implicit_activity_claim: bool = False,
) -> dict[str, Any]:
    """Build an aggregate, deterministic sanity summary for runtime telemetry."""

    surface_name = normalize_surface_name(selected_surface)
    surface = find_research_surface(problem_spec, surface_name)
    claims = normalize_expected_telemetry(expected_telemetry)
    expected_present = any(claims.values())
    evidence = _field(surface, "evidence")

    categories: dict[str, tuple[str, ...]] = {
        category: tuple(fields) for category, fields in claims.items() if fields
    }

    failures: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    field_summaries: dict[str, dict[str, Any]] = {}

    for category, fields in sorted(categories.items()):
        for field in fields:
            summary = _runtime_field_summary(
                field,
                candidate_runtimes=candidate_runtimes,
                champion_runtimes=champion_runtimes,
            )
            field_summaries[field] = summary
            if category == "budget" and summary["candidate_positive"] == 0:
                failures.append(
                    _guard_issue(
                        "TELEMETRY_BUDGET_STARVED",
                        category=category,
                        field=field,
                        severity="fail",
                        summary=summary,
                    )
                )
            elif summary["candidate_positive"] == 0:
                failures.append(
                    _guard_issue(
                        f"TELEMETRY_{category.upper()}_NOT_OBSERVED",
                        category=category,
                        field=field,
                        severity="fail",
                        summary=summary,
                    )
                )

    if not expected_present:
        activity_fields = declared_activity_runtime_fields(surface)
        if activity_fields:
            activity_positive = 0
            for field in activity_fields:
                summary = field_summaries.get(field)
                if summary is None:
                    summary = _runtime_field_summary(
                        field,
                        candidate_runtimes=candidate_runtimes,
                        champion_runtimes=champion_runtimes,
                    )
                    field_summaries[field] = summary
                activity_positive += int(summary["candidate_positive"])
            if candidate_runtimes and activity_positive == 0:
                issue = _guard_issue(
                    "TELEMETRY_ACTIVITY_NOT_OBSERVED",
                    category="activity",
                    field=",".join(activity_fields),
                    severity=(
                        "fail"
                        if implicit_activity_claim
                        or _as_bool(_field(evidence, "fail_closed_on_zero_activity"))
                        else "warn"
                    ),
                    summary={
                        "candidate_runs": len(candidate_runtimes),
                        "candidate_positive": 0,
                    },
                )
                (failures if issue["severity"] == "fail" else warnings).append(issue)

        budget_fields = declared_stage_budget_runtime_fields(surface)
        for field in budget_fields:
            if field in field_summaries:
                continue
            summary = _runtime_field_summary(
                field,
                candidate_runtimes=candidate_runtimes,
                champion_runtimes=champion_runtimes,
            )
            field_summaries[field] = summary
            if (
                candidate_runtimes
                and summary["candidate_positive"] == 0
                and summary["champion_positive"] > 0
            ):
                issue = _guard_issue(
                    "TELEMETRY_BUDGET_STARVED",
                    category="budget",
                    field=field,
                    severity=(
                        "fail"
                        if _as_bool(
                            _field(evidence, "fail_closed_on_stage_budget_starvation")
                        )
                        else "warn"
                    ),
                    summary=summary,
                )
                (failures if issue["severity"] == "fail" else warnings).append(issue)

    return {
        "schema": "scion.telemetry_guard.v1",
        "selected_surface": surface_name or None,
        "passed": not failures,
        "expected_telemetry_present": expected_present,
        "implicit_activity_claim": bool(implicit_activity_claim),
        "candidate_runs": len(candidate_runtimes),
        "champion_runs": len(champion_runtimes),
        "categories": {
            category: list(fields) for category, fields in sorted(categories.items())
        },
        "fields": field_summaries,
        "warnings": warnings,
        "failures": failures,
    }


def format_telemetry_guard_issue(summary: Mapping[str, Any]) -> str | None:
    failures = summary.get("failures")
    if not isinstance(failures, Sequence) or not failures:
        return None
    first = failures[0]
    if not isinstance(first, Mapping):
        return "telemetry guard failed"
    code = str(first.get("code") or "TELEMETRY_GUARD_FAILED")
    field = str(first.get("field") or "")
    category = str(first.get("category") or "telemetry")
    if code == "TELEMETRY_ACTIVITY_NOT_OBSERVED":
        activity_fields = []
        for item in failures:
            if (
                isinstance(item, Mapping)
                and item.get("code") == "TELEMETRY_ACTIVITY_NOT_OBSERVED"
            ):
                activity_fields.extend(
                    part.strip()
                    for part in str(item.get("field") or "").split(",")
                    if part.strip()
                )
        if activity_fields:
            field = ",".join(dict.fromkeys(activity_fields))
        field_zero_text = ", ".join(
            f"{item.strip()}=0" for item in field.split(",") if item.strip()
        )
        return (
            "telemetry guard observed zero active search effort: "
            f"{field_zero_text or field} had no positive runtime evidence across "
            f"{summary.get('candidate_runs', 0)} candidate run(s)"
        )
    if code == "TELEMETRY_BUDGET_STARVED":
        return (
            "telemetry guard observed stage budget starvation: "
            f"{field} had no positive candidate runtime evidence"
        )
    if code == "TELEMETRY_ACTIVATION_NOT_OBSERVED":
        return (
            "telemetry guard observed no activation evidence for declared "
            f"mechanism telemetry field {field}"
        )
    return (
        f"telemetry guard failed for {category} field {field}: "
        f"{code}"
    )


def find_research_surface(problem_spec: Any | None, name: str | None) -> Any | None:
    surface_name = normalize_surface_name(name)
    if not surface_name:
        return None
    for surface in _field(problem_spec, "research_surfaces") or ():
        if str(_field(surface, "name") or "").strip() == surface_name:
            return surface
    return None


def _runtime_field_summary(
    field: str,
    *,
    candidate_runtimes: Sequence[Mapping[str, Any]],
    champion_runtimes: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    candidate_present = 0
    candidate_positive = 0
    candidate_zero = 0
    candidate_missing = 0
    champion_positive = 0
    examples: list[Any] = []

    for runtime in candidate_runtimes:
        if field not in runtime:
            candidate_missing += 1
            continue
        candidate_present += 1
        value = runtime.get(field)
        if _positive_evidence(value):
            candidate_positive += 1
        elif not _empty_value(value):
            candidate_zero += 1
        if len(examples) < 3:
            examples.append(_bounded_value(value))

    for runtime in champion_runtimes:
        if field in runtime and _positive_evidence(runtime.get(field)):
            champion_positive += 1

    return {
        "candidate_present": candidate_present,
        "candidate_missing": candidate_missing,
        "candidate_positive": candidate_positive,
        "candidate_zero": candidate_zero,
        "champion_positive": champion_positive,
        "examples": examples,
    }


def _guard_issue(
    code: str,
    *,
    category: str,
    field: str,
    severity: str,
    summary: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "code": code,
        "severity": severity,
        "category": category,
        "field": field,
        "candidate_positive": summary.get("candidate_positive", 0),
        "candidate_present": summary.get("candidate_present", 0),
        "candidate_missing": summary.get("candidate_missing", 0),
        "champion_positive": summary.get("champion_positive", 0),
    }


def _append_fields(target: list[str], value: Any) -> None:
    if isinstance(value, Mapping):
        for item in value.values():
            _append_fields(target, item)
        return
    if isinstance(value, str):
        _append_field(target, value)
        return
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        for item in value:
            _append_fields(target, item)
        return
    _append_field(target, value)


def _append_field(target: list[str], value: Any) -> None:
    text = str(value or "").strip()
    if not text or text in target:
        return
    target.append(text)


def _freeze_claims(claims: Mapping[str, list[str]]) -> dict[str, tuple[str, ...]]:
    return {str(category): tuple(fields) for category, fields in sorted(claims.items())}


def _fields_with_suffix(fields: Sequence[str], suffixes: Sequence[str]) -> list[str]:
    return [
        field
        for field in fields
        if any(str(field).endswith(suffix) for suffix in suffixes)
    ]


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
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        result = []
        for item in value:
            text = str(item or "").strip()
            if text:
                result.append(text)
        return result
    text = str(value or "").strip()
    return [text] if text else []


def _positive_evidence(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value) > 0.0
    if isinstance(value, str):
        text = value.strip().lower()
        return bool(text) and text not in {
            "0",
            "false",
            "none",
            "null",
            "disabled",
            "off",
            "no",
            "unknown",
        }
    if isinstance(value, Mapping):
        return any(_positive_evidence(item) for item in value.values())
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return any(_positive_evidence(item) for item in value)
    return bool(value)


def _empty_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (Mapping, Sequence)) and not isinstance(value, (str, bytes, bytearray)):
        return len(value) == 0
    return False


def _bounded_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value[:160]
    if isinstance(value, Mapping):
        return {
            str(key)[:80]: _bounded_value(item)
            for key, item in list(value.items())[:8]
        }
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return [_bounded_value(item) for item in list(value)[:8]]
    return str(value)[:160]


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _field(obj: Any, name: str) -> Any:
    if obj is None:
        return None
    if isinstance(obj, Mapping):
        return obj.get(name)
    return getattr(obj, name, None)
