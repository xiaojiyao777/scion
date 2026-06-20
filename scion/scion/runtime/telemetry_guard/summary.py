"""Telemetry guard summary construction."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from scion.runtime.audit import normalize_surface_name
from scion.runtime.telemetry_guard.declarations import (
    declared_runtime_field_roles,
    find_research_surface,
)
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
    _protected_objective_tokens,
    _runtime_field_summary,
)
from scion.runtime.telemetry_guard.runtime_paths import (
    _mechanism_field_summary_key,
)
from scion.runtime.telemetry_guard.summary_fallbacks import (
    _record_no_expected_telemetry_fallbacks,
)
from scion.runtime.telemetry_guard.summary_fields import _record_expected_field_issues
from scion.runtime.telemetry_guard.summary_mechanisms import (
    _expected_field_mechanisms,
    _has_explicit_mechanism_field,
    _legacy_diagnostic_type_for_kind,
    _legacy_telemetry_outcome_for_kind,
    _looks_like_runtime_field,
    _mechanism_category_diagnostic_kind,
    _mechanism_diagnostics,
    _mechanism_issue_severity,
    _repairable_for_kind,
    _runtime_fields_for_mechanism_categories,
    _runtime_zero_or_subms_signal,
    _runtime_zero_summary,
)
from scion.runtime.telemetry_guard.summary_signals import (
    ACTIVATION_MISSING_OR_WIRING_SUSPECT,
    RUNTIME_BUDGET_ZERO_OR_SUBMS,
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
    effect_observation_required: bool = True,
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
    role_map = declared_runtime_field_roles(
        surface,
        problem_spec=problem_spec,
        declared_mechanisms=mechanisms,
    )
    protected_tokens = _protected_objective_tokens(protected_objectives)
    if not mechanisms and mechanism_claims:
        mechanisms = tuple(mechanism_claims)
    expected_present = any(claims.values()) or bool(mechanisms)
    evidence = _field(surface, "evidence")
    declared_probe_fields = tuple(
        declared_mechanism_runtime_probes(
            problem_spec=problem_spec,
            surface=surface,
            declared_mechanisms=mechanisms,
        )
    )
    activation_probe_fields_by_mechanism: dict[str, list[str]] = {}
    for probe in declared_probe_fields:
        if probe.category != "activation":
            continue
        activation_probe_fields_by_mechanism.setdefault(probe.mechanism, [])
        if probe.field not in activation_probe_fields_by_mechanism[probe.mechanism]:
            activation_probe_fields_by_mechanism[probe.mechanism].append(probe.field)
    expected_field_mechanisms = _expected_field_mechanisms(mechanism_claims)

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

    _record_expected_field_issues(
        categories=categories,
        candidate_runtimes=candidate_runtimes,
        champion_runtimes=champion_runtimes,
        role_map=role_map,
        protected_tokens=protected_tokens,
        mechanisms=mechanisms,
        expected_field_mechanisms=expected_field_mechanisms,
        activation_probe_fields_by_mechanism=activation_probe_fields_by_mechanism,
        effect_observation_required=effect_observation_required,
        field_summaries=field_summaries,
        mechanism_summaries=mechanism_summaries,
        failures=failures,
        warnings=warnings,
        zero_activity_issue_code=_zero_activity_issue_code,
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

    for probe in declared_probe_fields:
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
        category_totals: dict[str, dict[str, Any]] = {}
        for category, fields in sorted(category_fields.items()):
            fields = [field for field in fields if field]
            if not fields or category not in ("activation", "effect", "budget"):
                continue
            mechanism_summary["categories"][category] = list(fields)
            category_positive = 0
            category_present = 0
            category_zero = 0
            category_false = 0
            category_missing = 0
            category_champion_positive = 0
            runtime_positive = 0
            runtime_present = 0
            runtime_zero = 0
            non_runtime_positive = 0
            non_runtime_present = 0
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
                category_zero += int(summary.get("candidate_zero", 0) or 0)
                category_false += int(summary.get("candidate_false", 0) or 0)
                category_missing += int(summary["candidate_missing"])
                category_champion_positive += int(summary["champion_positive"])
                if _looks_like_runtime_field(field):
                    runtime_positive += int(summary["candidate_positive"])
                    runtime_present += int(summary["candidate_present"])
                    runtime_zero += int(summary.get("candidate_zero", 0) or 0)
                else:
                    non_runtime_positive += int(summary["candidate_positive"])
                    non_runtime_present += int(summary["candidate_present"])
            category_totals[category] = {
                "candidate_positive": category_positive,
                "candidate_present": category_present,
                "candidate_zero": category_zero,
                "candidate_false": category_false,
                "candidate_missing": category_missing,
                "champion_positive": category_champion_positive,
                "runtime_positive": runtime_positive,
                "runtime_present": runtime_present,
                "runtime_zero": runtime_zero,
                "non_runtime_positive": non_runtime_positive,
                "non_runtime_present": non_runtime_present,
                "fields": list(fields),
            }

        for category in ("activation", "budget", "effect"):
            totals = category_totals.get(category)
            if totals is None:
                continue
            fields = list(totals.get("fields") or ())
            category_positive = int(totals.get("candidate_positive", 0) or 0)
            if category_positive > 0:
                if (
                    category == "activation"
                    and _runtime_zero_or_subms_signal(category_totals)
                    and "budget" not in category_totals
                ):
                    runtime_fields = _runtime_fields_for_mechanism_categories(
                        mechanism_summary.get("categories")
                    )
                    warnings.append(
                        _guard_issue(
                            "TELEMETRY_MECHANISM_BUDGET_STARVED",
                            category="budget",
                            field=",".join(runtime_fields) or ",".join(fields),
                            severity="warn",
                            summary=_runtime_zero_summary(category_totals),
                            mechanism=mechanism,
                            diagnostic_type=ACTIVATION_MISSING_OR_WIRING_SUSPECT,
                            diagnostic_kind=RUNTIME_BUDGET_ZERO_OR_SUBMS,
                            branch_repair_signal=RUNTIME_BUDGET_ZERO_OR_SUBMS,
                            telemetry_outcome=RUNTIME_BUDGET_ZERO_OR_SUBMS,
                            repairable=True,
                        )
                    )
                continue
            code = (
                "TELEMETRY_MECHANISM_BUDGET_STARVED"
                if category == "budget"
                else f"TELEMETRY_MECHANISM_{category.upper()}_NOT_OBSERVED"
            )
            diagnostic_kind = _mechanism_category_diagnostic_kind(
                category=category,
                category_totals=category_totals,
                effect_observation_required=effect_observation_required,
            )
            if diagnostic_kind is None:
                continue
            severity = _mechanism_issue_severity(
                category=category,
                diagnostic_kind=diagnostic_kind,
                effect_observation_required=effect_observation_required,
                has_explicit_effect_field=(
                    _has_explicit_mechanism_field(
                        explicit_mechanism_fields,
                        mechanism=mechanism,
                        category=category,
                        fields=fields,
                    )
                    if category == "effect"
                    else False
                ),
            )
            diagnostic_type = _legacy_diagnostic_type_for_kind(diagnostic_kind)
            telemetry_outcome = _legacy_telemetry_outcome_for_kind(diagnostic_kind)
            repairable = _repairable_for_kind(diagnostic_kind)
            issue = _guard_issue(
                code,
                category=category,
                field=",".join(fields),
                severity=severity,
                summary={
                    "candidate_positive": totals.get("candidate_positive", 0),
                    "candidate_present": totals.get("candidate_present", 0),
                    "candidate_zero": totals.get("candidate_zero", 0),
                    "candidate_false": totals.get("candidate_false", 0),
                    "candidate_missing": totals.get("candidate_missing", 0),
                    "champion_positive": totals.get("champion_positive", 0),
                },
                mechanism=mechanism,
                diagnostic_type=diagnostic_type,
                diagnostic_kind=diagnostic_kind,
                branch_repair_signal=diagnostic_kind,
                telemetry_outcome=telemetry_outcome,
                repairable=repairable,
            )
            if severity == "fail":
                failures.append(issue)
                mechanism_summary["passed"] = False
            else:
                warnings.append(issue)

    if not expected_present:
        _record_no_expected_telemetry_fallbacks(
            surface=surface,
            evidence=evidence,
            candidate_runtimes=candidate_runtimes,
            champion_runtimes=champion_runtimes,
            implicit_activity_claim=implicit_activity_claim,
            field_summaries=field_summaries,
            failures=failures,
            warnings=warnings,
            zero_activity_issue_code=_zero_activity_issue_code,
        )

    return {
        "schema": "scion.telemetry_guard.v1",
        "selected_surface": surface_name or None,
        "passed": not failures,
        "expected_telemetry_present": expected_present,
        "implicit_activity_claim": bool(implicit_activity_claim),
        "effect_observation_required": bool(effect_observation_required),
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
        "mechanism_diagnostics": _mechanism_diagnostics(
            mechanism_summaries,
            effect_observation_required=effect_observation_required,
        ),
        "fields": field_summaries,
        "warnings": warnings,
        "failures": failures,
    }


def _zero_activity_issue_code(category: str, summary: Mapping[str, Any]) -> str:
    if str(category or "").lower() != "activity":
        return f"TELEMETRY_{category.upper()}_NOT_OBSERVED"
    try:
        present = int(summary.get("candidate_present", 0) or 0)
        missing = int(summary.get("candidate_missing", 0) or 0)
        positive = int(summary.get("candidate_positive", 0) or 0)
    except (TypeError, ValueError):
        return "TELEMETRY_ACTIVITY_NOT_OBSERVED"
    if present > 0 and missing == 0 and positive == 0:
        return "TELEMETRY_ACTIVITY_FIELD_ALL_ZERO"
    return "TELEMETRY_ACTIVITY_NOT_OBSERVED"
