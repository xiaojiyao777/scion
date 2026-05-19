"""Telemetry guard summary construction."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from scion.runtime.audit import normalize_surface_name
from scion.runtime.telemetry_guard.declarations import (
    declared_activity_runtime_fields,
    declared_stage_budget_runtime_fields,
    find_research_surface,
)
from scion.runtime.telemetry_guard.evidence import _as_bool
from scion.runtime.telemetry_guard.expected_schema import (
    EXPECTED_TELEMETRY_CATEGORIES,
    normalize_declared_mechanisms,
    normalize_expected_telemetry,
    normalize_expected_telemetry_by_mechanism,
)
from scion.runtime.telemetry_guard.issues import _guard_issue
from scion.runtime.telemetry_guard.mechanism_probes import (
    declared_mechanism_runtime_probes,
)
from scion.runtime.telemetry_guard.observations import (
    _matches_protected_objective_field,
    _protected_objective_tokens,
    _runtime_field_summary,
)
from scion.runtime.telemetry_guard.runtime_paths import (
    _mechanism_field_summary_key,
)
from scion.runtime.telemetry_guard.utils import _field


def build_telemetry_guard_summary(
    *,
    candidate_runtimes: Sequence[Mapping[str, Any]],
    champion_runtimes: Sequence[Mapping[str, Any]] = (),
    problem_spec: Any | None,
    selected_surface: str | None,
    expected_telemetry: Any = None,
    declared_mechanisms: Any = None,
    protected_objectives: Sequence[str] = (),
    implicit_activity_claim: bool = False,
) -> dict[str, Any]:
    """Build an aggregate, deterministic sanity summary for runtime telemetry."""

    surface_name = normalize_surface_name(selected_surface)
    surface = find_research_surface(problem_spec, surface_name)
    claims = normalize_expected_telemetry(expected_telemetry)
    mechanism_claims = normalize_expected_telemetry_by_mechanism(expected_telemetry)
    mechanisms = normalize_declared_mechanisms(
        declared_mechanisms,
        expected_telemetry=expected_telemetry,
    )
    protected_tokens = _protected_objective_tokens(protected_objectives)
    if not mechanisms and mechanism_claims:
        mechanisms = tuple(mechanism_claims)
    expected_present = any(claims.values()) or bool(mechanisms)
    evidence = _field(surface, "evidence")

    categories: dict[str, tuple[str, ...]] = {
        category: tuple(fields) for category, fields in claims.items() if fields
    }

    failures: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    field_summaries: dict[str, dict[str, Any]] = {}
    mechanism_summaries: dict[str, dict[str, Any]] = {
        mechanism: {"categories": {}, "fields": {}, "passed": True}
        for mechanism in mechanisms
    }

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
            elif category == "effect" and _is_objective_outcome_effect_field(field):
                if summary["candidate_present"] == 0:
                    code = (
                        "TELEMETRY_PROTECTED_EFFECT_NOT_OBSERVED"
                        if _matches_protected_objective_field(
                            field,
                            protected_tokens,
                        )
                        else "TELEMETRY_EFFECT_NOT_OBSERVED"
                    )
                    failures.append(
                        _guard_issue(
                            code,
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

    mechanism_probe_categories: dict[str, dict[str, list[str]]] = {
        mechanism: {category: [] for category in EXPECTED_TELEMETRY_CATEGORIES}
        for mechanism in mechanisms
    }
    explicit_mechanism_fields: dict[str, dict[str, set[str]]] = {
        mechanism: {category: set() for category in EXPECTED_TELEMETRY_CATEGORIES}
        for mechanism in mechanisms
    }
    for mechanism, category_claims in mechanism_claims.items():
        categories_for_mechanism = mechanism_probe_categories.setdefault(
            mechanism,
            {category: [] for category in EXPECTED_TELEMETRY_CATEGORIES},
        )
        explicit_fields_for_mechanism = explicit_mechanism_fields.setdefault(
            mechanism,
            {category: set() for category in EXPECTED_TELEMETRY_CATEGORIES},
        )
        mechanism_summaries.setdefault(
            mechanism,
            {"categories": {}, "fields": {}, "passed": True},
        )
        for category, fields in category_claims.items():
            categories_for_mechanism.setdefault(category, [])
            explicit_fields_for_mechanism.setdefault(category, set())
            for field in fields:
                if field not in categories_for_mechanism[category]:
                    categories_for_mechanism[category].append(field)
                explicit_fields_for_mechanism[category].add(field)

    for probe in declared_mechanism_runtime_probes(
        problem_spec=problem_spec,
        surface=surface,
        declared_mechanisms=mechanisms,
    ):
        categories_for_mechanism = mechanism_probe_categories.setdefault(
            probe.mechanism,
            {category: [] for category in EXPECTED_TELEMETRY_CATEGORIES},
        )
        mechanism_summaries.setdefault(
            probe.mechanism,
            {"categories": {}, "fields": {}, "passed": True},
        )
        fields = categories_for_mechanism.setdefault(probe.category, [])
        if probe.field not in fields:
            fields.append(probe.field)

    for mechanism, category_fields in sorted(mechanism_probe_categories.items()):
        mechanism_summary = mechanism_summaries.setdefault(
            mechanism,
            {"categories": {}, "fields": {}, "passed": True},
        )
        for category, fields in sorted(category_fields.items()):
            fields = [field for field in fields if field]
            if not fields or category not in ("activation", "effect", "budget"):
                continue
            mechanism_summary["categories"][category] = list(fields)
            category_positive = 0
            category_present = 0
            category_missing = 0
            category_champion_positive = 0
            for field in fields:
                summary = _runtime_field_summary(
                    field,
                    candidate_runtimes=candidate_runtimes,
                    champion_runtimes=champion_runtimes,
                    mechanism=mechanism,
                )
                mechanism_summary["fields"][field] = summary
                field_summaries[_mechanism_field_summary_key(mechanism, field)] = (
                    summary
                )
                category_positive += int(summary["candidate_positive"])
                category_present += int(summary["candidate_present"])
                category_missing += int(summary["candidate_missing"])
                category_champion_positive += int(summary["champion_positive"])
            if category_positive > 0:
                continue
            code = (
                "TELEMETRY_MECHANISM_BUDGET_STARVED"
                if category == "budget"
                else f"TELEMETRY_MECHANISM_{category.upper()}_NOT_OBSERVED"
            )
            severity = "fail"
            if category == "effect" and not _has_explicit_mechanism_field(
                explicit_mechanism_fields,
                mechanism=mechanism,
                category=category,
                fields=fields,
            ):
                severity = "warn"
            issue = _guard_issue(
                code,
                category=category,
                field=",".join(fields),
                severity=severity,
                summary={
                    "candidate_positive": category_positive,
                    "candidate_present": category_present,
                    "candidate_missing": category_missing,
                    "champion_positive": category_champion_positive,
                },
                mechanism=mechanism,
            )
            if severity == "fail":
                failures.append(issue)
                mechanism_summary["passed"] = False
            else:
                warnings.append(issue)

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
        "declared_mechanisms": list(mechanisms),
        "protected_objectives": list(protected_tokens),
        "candidate_runs": len(candidate_runtimes),
        "champion_runs": len(champion_runtimes),
        "categories": {
            category: list(fields) for category, fields in sorted(categories.items())
        },
        "mechanisms": {
            mechanism: mechanism_summary
            for mechanism, mechanism_summary in sorted(mechanism_summaries.items())
            if mechanism_summary.get("categories") or mechanism_summary.get("fields")
        },
        "mechanism_diagnostics": _mechanism_diagnostics(mechanism_summaries),
        "fields": field_summaries,
        "warnings": warnings,
        "failures": failures,
    }


_OBJECTIVE_OUTCOME_EFFECT_FIELDS = frozenset(
    {
        "solver_algorithm_fleet_violation",
        "solver_algorithm_total_distance",
        "solver_algorithm_objective",
        "solver_algorithm_solution_routes",
    }
)


def _is_objective_outcome_effect_field(field: str) -> bool:
    return str(field or "").strip() in _OBJECTIVE_OUTCOME_EFFECT_FIELDS


def _has_explicit_mechanism_field(
    explicit_fields: Mapping[str, Mapping[str, set[str]]],
    *,
    mechanism: str,
    category: str,
    fields: Sequence[str],
) -> bool:
    category_fields = explicit_fields.get(mechanism, {}).get(category, set())
    return any(field in category_fields for field in fields)


def _mechanism_diagnostics(
    mechanism_summaries: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    for mechanism, summary in sorted(mechanism_summaries.items()):
        categories = summary.get("categories")
        fields = summary.get("fields")
        if not isinstance(categories, Mapping) or not isinstance(fields, Mapping):
            continue
        activation_fields = _category_fields(categories, "activation")
        effect_fields = _category_fields(categories, "effect")
        runtime_fields = _runtime_probe_fields(categories)
        activation = _observation_status(
            fields,
            activation_fields,
            positive_label="observed",
        )
        runtime = _observation_status(
            fields,
            runtime_fields,
            positive_label="observed",
        )
        effect = _observation_status(
            fields,
            effect_fields,
            positive_label="positive",
        )
        diagnostics.append(
            {
                "mechanism": mechanism,
                "activation_status": activation["status"],
                "runtime_status": runtime["status"],
                "effect_status": effect["status"],
                "activation_observed": activation["status"] == "observed",
                "runtime_observed": runtime["status"] == "observed",
                "effect_observed": effect["status"] == "positive",
                "activation": activation,
                "runtime": runtime,
                "effect": effect,
                "repair_guidance": _mechanism_repair_guidance(
                    mechanism=mechanism,
                    activation_status=activation["status"],
                    runtime_status=runtime["status"],
                    effect_status=effect["status"],
                ),
            }
        )
    return diagnostics


def _category_fields(categories: Mapping[str, Any], category: str) -> list[str]:
    value = categories.get(category)
    if not isinstance(value, Sequence) or isinstance(value, (bytes, bytearray, str)):
        return []
    return list(dict.fromkeys(str(field) for field in value if str(field or "")))


def _runtime_probe_fields(categories: Mapping[str, Any]) -> list[str]:
    fields: list[str] = []
    for category in ("budget", "activation", "effect"):
        for field in _category_fields(categories, category):
            if _looks_like_runtime_field(field):
                fields.append(field)
    return list(dict.fromkeys(fields))


def _looks_like_runtime_field(field: str) -> bool:
    normalized = str(field or "").strip().lower()
    return any(
        token in normalized
        for token in (
            "phase_runtime",
            "runtime_ms",
            "elapsed_ms",
            "budget",
            "duration",
            "wall_time",
        )
    )


def _observation_status(
    field_summaries: Mapping[str, Any],
    fields: Sequence[str],
    *,
    positive_label: str,
) -> dict[str, Any]:
    totals = {
        "candidate_positive": 0,
        "candidate_present": 0,
        "candidate_zero": 0,
        "candidate_missing": 0,
        "champion_positive": 0,
    }
    if not fields:
        return {"status": "not_declared", "fields": []} | totals
    for field in fields:
        summary = field_summaries.get(field)
        if not isinstance(summary, Mapping):
            continue
        for key in totals:
            totals[key] += int(summary.get(key, 0) or 0)
    if totals["candidate_positive"] > 0:
        status = positive_label
    elif totals["candidate_present"] > 0:
        status = "zero"
    else:
        status = "missing"
    return {"status": status, "fields": list(fields)} | totals


def _mechanism_repair_guidance(
    *,
    mechanism: str,
    activation_status: str,
    runtime_status: str,
    effect_status: str,
) -> list[str]:
    guidance: list[str] = []
    if activation_status in {"missing", "zero"}:
        guidance.append(
            "Add direct activation telemetry for declared mechanism "
            f"{mechanism}: context.record_iteration('{mechanism}', positive_count) "
            f"or context.record_phase('{mechanism}', positive_elapsed_ms)."
        )
    if runtime_status in {"missing", "zero"}:
        detail = "missing" if runtime_status == "missing" else "zero-valued"
        guidance.append(
            "Add positive phase/runtime telemetry for declared mechanism "
            f"{mechanism}; current runtime evidence is {detail}. Use "
            f"context.record_phase('{mechanism}', elapsed_ms_delta) on the "
            "mechanism path."
        )
    if effect_status == "missing":
        guidance.append(
            "Add effect telemetry for declared mechanism "
            f"{mechanism}: context.record_move('{mechanism}', attempted=1, "
            "accepted=accepted_flag, delta=objective_delta, "
            "best_improved=best_improved_flag)."
        )
    return guidance
