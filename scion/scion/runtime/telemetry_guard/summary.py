"""Telemetry guard summary construction."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from scion.runtime.audit import normalize_surface_name
from scion.runtime.telemetry_guard.declarations import (
    declared_activity_runtime_fields,
    declared_runtime_field_roles,
    declared_stage_budget_runtime_fields,
    find_research_surface,
    runtime_field_roles_for,
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

MECHANISM_EXECUTED_NO_IMPROVEMENT = "mechanism_executed_no_improvement"
EFFECT_ATTRIBUTION_MISSING = "effect_attribution_missing"
ACTIVATION_MISSING_OR_WIRING_SUSPECT = "activation_missing_or_wiring_suspect"
NOT_EVALUATED_OR_TRIGGERED = "not_evaluated/not_triggered"
EVALUATED_NO_EFFECT = "evaluated_no_effect"
ACTIVATED_NO_POSITIVE_EFFECT = "activated_no_positive_effect"
RUNTIME_BUDGET_ZERO_OR_SUBMS = "runtime_budget_zero_or_subms"
WIRING_SUSPECT = "wiring_suspect"


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

    for category, fields in sorted(categories.items()):
        for field in fields:
            summary = _runtime_field_summary(
                field,
                candidate_runtimes=candidate_runtimes,
                champion_runtimes=champion_runtimes,
            )
            field_summaries[field] = summary
            if category in {"activation", "budget"} and _field_is_mechanism_scoped(
                field,
                mechanisms=mechanisms,
                field_mechanisms=expected_field_mechanisms,
            ):
                continue
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
            elif category == "effect" and _is_objective_outcome_effect_field(
                field,
                role_map=role_map,
            ):
                if summary["candidate_present"] == 0:
                    protected_effect = _matches_protected_objective_field(
                        field,
                        protected_tokens,
                    )
                    activation_observed = _declared_effect_activation_observed(
                        field,
                        mechanisms=mechanisms,
                        field_mechanisms=expected_field_mechanisms,
                        activation_probe_fields=activation_probe_fields_by_mechanism,
                        candidate_runtimes=candidate_runtimes,
                        champion_runtimes=champion_runtimes,
                    )
                    code = (
                        "TELEMETRY_PROTECTED_EFFECT_NOT_OBSERVED"
                        if protected_effect
                        else "TELEMETRY_EFFECT_NOT_OBSERVED"
                    )
                    issue = _guard_issue(
                        code,
                        category=category,
                        field=field,
                        severity=(
                            "fail"
                            if protected_effect
                            or (effect_observation_required and not activation_observed)
                            else "warn"
                        ),
                        summary=summary,
                        diagnostic_type=(
                            EFFECT_ATTRIBUTION_MISSING
                            if activation_observed and not protected_effect
                            else None
                        ),
                        telemetry_outcome=(
                            "effect_attribution_missing"
                            if activation_observed and not protected_effect
                            else None
                        ),
                        repairable=(
                            True if activation_observed and not protected_effect else None
                        ),
                    )
                    _record_declared_field_issue_for_mechanisms(
                        mechanism_summaries,
                        mechanisms=mechanisms,
                        category=category,
                        field=field,
                        issue=issue,
                    )
                    (failures if issue["severity"] == "fail" else warnings).append(
                        issue
                    )
            elif summary["candidate_positive"] == 0:
                activation_observed = category == "effect" and (
                    _declared_effect_activation_observed(
                        field,
                        mechanisms=mechanisms,
                        field_mechanisms=expected_field_mechanisms,
                        activation_probe_fields=activation_probe_fields_by_mechanism,
                        candidate_runtimes=candidate_runtimes,
                        champion_runtimes=champion_runtimes,
                    )
                )
                issue = _guard_issue(
                    _zero_activity_issue_code(category, summary),
                    category=category,
                    field=field,
                    severity=(
                        "warn"
                        if category == "effect"
                        and (not effect_observation_required or activation_observed)
                        else "fail"
                    ),
                    summary=summary,
                    diagnostic_type=(
                        (
                            MECHANISM_EXECUTED_NO_IMPROVEMENT
                            if int(summary.get("candidate_present", 0) or 0) > 0
                            else EFFECT_ATTRIBUTION_MISSING
                        )
                        if activation_observed
                        else None
                    ),
                    telemetry_outcome=(
                        (
                            "no_effect"
                            if int(summary.get("candidate_present", 0) or 0) > 0
                            else "effect_attribution_missing"
                        )
                        if activation_observed
                        else None
                    ),
                    repairable=(
                        int(summary.get("candidate_present", 0) or 0) == 0
                        if activation_observed
                        else None
                    ),
                )
                _record_declared_field_issue_for_mechanisms(
                    mechanism_summaries,
                    mechanisms=mechanisms,
                    category=category,
                    field=field,
                    issue=issue,
                )
                (failures if issue["severity"] == "fail" else warnings).append(issue)

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
        activity_fields = declared_activity_runtime_fields(surface)
        if activity_fields:
            activity_positive = 0
            activity_present = 0
            activity_missing = 0
            activity_champion_positive = 0
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
                activity_present += int(summary["candidate_present"])
                activity_missing += int(summary["candidate_missing"])
                activity_champion_positive += int(summary["champion_positive"])
            if candidate_runtimes and activity_positive == 0:
                issue = _guard_issue(
                    _zero_activity_issue_code(
                        "activity",
                        {
                            "candidate_present": activity_present,
                            "candidate_missing": activity_missing,
                            "candidate_positive": activity_positive,
                        },
                    ),
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
                        "candidate_positive": activity_positive,
                        "candidate_present": activity_present,
                        "candidate_missing": activity_missing,
                        "champion_positive": activity_champion_positive,
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


_OBJECTIVE_OUTCOME_EFFECT_ROLES = frozenset(
    {"objective_outcome", "outcome", "protected_outcome"}
)


def _expected_field_mechanisms(
    mechanism_claims: Mapping[str, Mapping[str, Sequence[str]]],
) -> dict[str, list[str]]:
    field_mechanisms: dict[str, list[str]] = {}
    for mechanism, category_claims in mechanism_claims.items():
        for fields in category_claims.values():
            for field in fields:
                field_text = str(field or "").strip()
                mechanism_text = str(mechanism or "").strip()
                if not field_text or not mechanism_text:
                    continue
                field_mechanisms.setdefault(field_text, [])
                if mechanism_text not in field_mechanisms[field_text]:
                    field_mechanisms[field_text].append(mechanism_text)
    return field_mechanisms


def _field_is_mechanism_scoped(
    field: str,
    *,
    mechanisms: Sequence[str],
    field_mechanisms: Mapping[str, Sequence[str]],
) -> bool:
    field_text = str(field or "").strip()
    if not field_text:
        return False
    if field_mechanisms.get(field_text):
        return True
    return any(
        _field_mentions_mechanism(field_text, mechanism) for mechanism in mechanisms
    )


def _declared_effect_activation_observed(
    field: str,
    *,
    mechanisms: Sequence[str],
    field_mechanisms: Mapping[str, Sequence[str]],
    activation_probe_fields: Mapping[str, Sequence[str]],
    candidate_runtimes: Sequence[Mapping[str, Any]],
    champion_runtimes: Sequence[Mapping[str, Any]],
) -> bool:
    matched_mechanisms = list(field_mechanisms.get(field) or ())
    if not matched_mechanisms:
        matched_mechanisms = [
            mechanism
            for mechanism in mechanisms
            if _field_mentions_mechanism(field, mechanism)
        ]
    for mechanism in matched_mechanisms:
        for activation_field in activation_probe_fields.get(mechanism, ()):
            summary = _runtime_field_summary(
                activation_field,
                candidate_runtimes=candidate_runtimes,
                champion_runtimes=champion_runtimes,
                mechanism=mechanism,
            )
            if int(summary.get("candidate_positive", 0) or 0) > 0:
                return True
    return False


def _is_objective_outcome_effect_field(
    field: str,
    *,
    role_map: Mapping[str, Sequence[str] | frozenset[str]],
) -> bool:
    return bool(
        runtime_field_roles_for(field, role_map) & _OBJECTIVE_OUTCOME_EFFECT_ROLES
    )


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


def _has_explicit_mechanism_field(
    explicit_fields: Mapping[str, Mapping[str, set[str]]],
    *,
    mechanism: str,
    category: str,
    fields: Sequence[str],
) -> bool:
    category_fields = explicit_fields.get(mechanism, {}).get(category, set())
    return any(field in category_fields for field in fields)


def _record_declared_field_issue_for_mechanisms(
    mechanism_summaries: Mapping[str, dict[str, Any]],
    *,
    mechanisms: Sequence[str],
    category: str,
    field: str,
    issue: Mapping[str, Any],
) -> None:
    matched = [
        mechanism
        for mechanism in mechanisms
        if _field_mentions_mechanism(field, mechanism)
    ]
    for mechanism in matched:
        summary = mechanism_summaries.get(mechanism)
        if not isinstance(summary, dict):
            continue
        key = (
            "declared_field_failures"
            if issue.get("severity") == "fail"
            else "declared_field_warnings"
        )
        entries = summary.setdefault(key, [])
        if isinstance(entries, list):
            entries.append(
                {
                    "category": category,
                    "field": field,
                    "code": issue.get("code"),
                    "severity": issue.get("severity"),
                }
            )
        if issue.get("severity") == "fail":
            summary["passed"] = False


def _field_mentions_mechanism(field: str, mechanism: str) -> bool:
    field_text = str(field or "")
    mechanism_text = str(mechanism or "").strip()
    if not field_text or not mechanism_text:
        return False
    if "{mechanism}" in field_text:
        return True
    return mechanism_text in field_text


def _mechanism_diagnostics(
    mechanism_summaries: Mapping[str, Mapping[str, Any]],
    *,
    effect_observation_required: bool,
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
        declared_field_failures = list(summary.get("declared_field_failures") or [])
        declared_field_warnings = list(summary.get("declared_field_warnings") or [])
        effect_declared_failures = _declared_field_issues_for_category(
            declared_field_failures,
            "effect",
        )
        effect_declared_warnings = _declared_field_issues_for_category(
            declared_field_warnings,
            "effect",
        )
        if effect_declared_failures and effect["status"] == "positive":
            effect = {
                **effect,
                "aggregate_status": effect["status"],
                "status": "declared_field_failed",
                "declared_field_failures": effect_declared_failures,
            }
        elif effect_declared_warnings and effect["status"] == "positive":
            effect = {
                **effect,
                "aggregate_status": effect["status"],
                "status": "declared_field_warning",
                "declared_field_warnings": effect_declared_warnings,
            }
        diagnostic_type = _mechanism_diagnostic_type(
            activation_status=activation["status"],
            runtime_status=runtime["status"],
            effect_status=effect["status"],
        )
        diagnostic_kind = _mechanism_diagnostic_kind(
            activation=activation,
            runtime=runtime,
            effect=effect,
            effect_observation_required=effect_observation_required,
        )
        diagnostic_signals = _mechanism_diagnostic_signals(
            activation=activation,
            runtime=runtime,
            effect=effect,
            effect_observation_required=effect_observation_required,
        )
        diagnostics.append(
            {
                "mechanism": mechanism,
                "passed": bool(summary.get("passed", True)),
                "diagnostic_type": diagnostic_type,
                "diagnostic_kind": diagnostic_kind,
                "diagnostic_signals": diagnostic_signals,
                "branch_repair_signal": diagnostic_kind,
                "telemetry_outcome": _legacy_telemetry_outcome_for_kind(
                    diagnostic_kind
                )
                or _mechanism_telemetry_outcome(diagnostic_type),
                "activation_status": activation["status"],
                "runtime_status": runtime["status"],
                "effect_status": effect["status"],
                "activation_observed": activation["status"] == "observed",
                "runtime_observed": runtime["status"] == "observed",
                "effect_observed": effect["status"] == "positive",
                "declared_field_failures": declared_field_failures,
                "declared_field_warnings": declared_field_warnings,
                "activation": activation,
                "runtime": runtime,
                "effect": effect,
                "repair_guidance": _mechanism_repair_guidance(
                    mechanism=mechanism,
                    activation_status=activation["status"],
                    runtime_status=runtime["status"],
                    effect_status=effect["status"],
                    diagnostic_kind=diagnostic_kind,
                    diagnostic_signals=diagnostic_signals,
                    declared_field_failures=(
                        declared_field_failures + declared_field_warnings
                    ),
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


def _runtime_zero_or_subms_signal(
    category_totals: Mapping[str, Mapping[str, Any]],
) -> bool:
    runtime_present = sum(
        int(totals.get("runtime_present", 0) or 0)
        for totals in category_totals.values()
    )
    runtime_positive = sum(
        int(totals.get("runtime_positive", 0) or 0)
        for totals in category_totals.values()
    )
    runtime_zero = sum(
        int(totals.get("runtime_zero", 0) or 0)
        for totals in category_totals.values()
    )
    if runtime_present <= 0 or runtime_positive > 0 or runtime_zero <= 0:
        return False
    return _non_time_activation_or_evaluation_evidence(category_totals)


def _non_time_activation_or_evaluation_evidence(
    category_totals: Mapping[str, Mapping[str, Any]],
) -> bool:
    activation = category_totals.get("activation") or {}
    effect = category_totals.get("effect") or {}
    return (
        int(activation.get("non_runtime_positive", 0) or 0) > 0
        or int(effect.get("candidate_present", 0) or 0) > 0
        or int(effect.get("candidate_positive", 0) or 0) > 0
    )


def _runtime_zero_summary(
    category_totals: Mapping[str, Mapping[str, Any]],
) -> dict[str, int]:
    return {
        "candidate_positive": sum(
            int(totals.get("runtime_positive", 0) or 0)
            for totals in category_totals.values()
        ),
        "candidate_present": sum(
            int(totals.get("runtime_present", 0) or 0)
            for totals in category_totals.values()
        ),
        "candidate_zero": sum(
            int(totals.get("runtime_zero", 0) or 0)
            for totals in category_totals.values()
        ),
        "candidate_missing": 0,
        "champion_positive": 0,
    }


def _runtime_fields_for_mechanism_categories(categories: Any) -> list[str]:
    if not isinstance(categories, Mapping):
        return []
    fields: list[str] = []
    for category in ("budget", "activation", "effect"):
        for field in _category_fields(categories, category):
            if _looks_like_runtime_field(field):
                fields.append(field)
    return list(dict.fromkeys(fields))


def _mechanism_category_diagnostic_kind(
    *,
    category: str,
    category_totals: Mapping[str, Mapping[str, Any]],
    effect_observation_required: bool,
) -> str | None:
    activation = category_totals.get("activation") or {}
    effect = category_totals.get("effect") or {}
    runtime_zero = _runtime_zero_or_subms_signal(category_totals)
    activation_positive = int(activation.get("candidate_positive", 0) or 0) > 0
    effect_present = int(effect.get("candidate_present", 0) or 0) > 0
    effect_positive = int(effect.get("candidate_positive", 0) or 0) > 0
    if runtime_zero and category in {"activation", "budget"}:
        return RUNTIME_BUDGET_ZERO_OR_SUBMS
    if category in {"activation", "budget"} and effect_positive:
        return None
    if category == "effect":
        if effect_present and not effect_positive:
            return EVALUATED_NO_EFFECT
        if activation_positive:
            return ACTIVATED_NO_POSITIVE_EFFECT
        return (
            NOT_EVALUATED_OR_TRIGGERED
            if not effect_observation_required
            else WIRING_SUSPECT
        )
    if effect_present and not effect_positive:
        return EVALUATED_NO_EFFECT
    if not effect_observation_required:
        return NOT_EVALUATED_OR_TRIGGERED
    return WIRING_SUSPECT


def _mechanism_issue_severity(
    *,
    category: str,
    diagnostic_kind: str | None,
    effect_observation_required: bool,
    has_explicit_effect_field: bool,
) -> str:
    if diagnostic_kind in {
        RUNTIME_BUDGET_ZERO_OR_SUBMS,
        EVALUATED_NO_EFFECT,
        ACTIVATED_NO_POSITIVE_EFFECT,
        NOT_EVALUATED_OR_TRIGGERED,
    }:
        return "warn"
    if category == "effect" and (
        not effect_observation_required or not has_explicit_effect_field
    ):
        return "warn"
    return "fail"


def _legacy_diagnostic_type_for_kind(diagnostic_kind: str | None) -> str | None:
    if diagnostic_kind == ACTIVATED_NO_POSITIVE_EFFECT:
        return EFFECT_ATTRIBUTION_MISSING
    if diagnostic_kind == EVALUATED_NO_EFFECT:
        return MECHANISM_EXECUTED_NO_IMPROVEMENT
    if diagnostic_kind in {
        RUNTIME_BUDGET_ZERO_OR_SUBMS,
        NOT_EVALUATED_OR_TRIGGERED,
        WIRING_SUSPECT,
    }:
        return ACTIVATION_MISSING_OR_WIRING_SUSPECT
    return None


def _legacy_telemetry_outcome_for_kind(diagnostic_kind: str | None) -> str | None:
    if diagnostic_kind == ACTIVATED_NO_POSITIVE_EFFECT:
        return "effect_attribution_missing"
    if diagnostic_kind == EVALUATED_NO_EFFECT:
        return "no_effect"
    if diagnostic_kind == RUNTIME_BUDGET_ZERO_OR_SUBMS:
        return RUNTIME_BUDGET_ZERO_OR_SUBMS
    if diagnostic_kind == NOT_EVALUATED_OR_TRIGGERED:
        return NOT_EVALUATED_OR_TRIGGERED
    if diagnostic_kind == WIRING_SUSPECT:
        return "activation_missing"
    return None


def _repairable_for_kind(diagnostic_kind: str | None) -> bool | None:
    if diagnostic_kind in {
        RUNTIME_BUDGET_ZERO_OR_SUBMS,
        NOT_EVALUATED_OR_TRIGGERED,
        WIRING_SUSPECT,
        ACTIVATED_NO_POSITIVE_EFFECT,
    }:
        return True
    if diagnostic_kind == EVALUATED_NO_EFFECT:
        return False
    return None


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


def _mechanism_diagnostic_type(
    *,
    activation_status: str,
    runtime_status: str,
    effect_status: str,
) -> str | None:
    if effect_status in {"zero", "declared_field_warning"}:
        return MECHANISM_EXECUTED_NO_IMPROVEMENT
    if activation_status in {"missing", "zero"}:
        return ACTIVATION_MISSING_OR_WIRING_SUSPECT
    if effect_status == "missing" and (
        activation_status == "observed" or runtime_status == "observed"
    ):
        return EFFECT_ATTRIBUTION_MISSING
    return None


def _mechanism_diagnostic_kind(
    *,
    activation: Mapping[str, Any],
    runtime: Mapping[str, Any],
    effect: Mapping[str, Any],
    effect_observation_required: bool,
) -> str | None:
    signals = _mechanism_diagnostic_signals(
        activation=activation,
        runtime=runtime,
        effect=effect,
        effect_observation_required=effect_observation_required,
    )
    if not signals:
        return None
    for preferred in (
        WIRING_SUSPECT,
        RUNTIME_BUDGET_ZERO_OR_SUBMS,
        ACTIVATED_NO_POSITIVE_EFFECT,
        EVALUATED_NO_EFFECT,
        NOT_EVALUATED_OR_TRIGGERED,
    ):
        if preferred in signals:
            return preferred
    return signals[0]


def _mechanism_diagnostic_signals(
    *,
    activation: Mapping[str, Any],
    runtime: Mapping[str, Any],
    effect: Mapping[str, Any],
    effect_observation_required: bool,
) -> list[str]:
    signals: list[str] = []
    activation_status = str(activation.get("status") or "")
    runtime_status = str(runtime.get("status") or "")
    effect_status = str(effect.get("status") or "")
    activation_positive = activation_status == "observed"
    runtime_zero = runtime_status == "zero"
    effect_present = int(effect.get("candidate_present", 0) or 0) > 0
    effect_positive = effect_status == "positive"
    if runtime_zero and (activation_positive or effect_present):
        signals.append(RUNTIME_BUDGET_ZERO_OR_SUBMS)
    if effect_present and not effect_positive:
        signals.append(EVALUATED_NO_EFFECT)
    elif activation_positive and effect_status in {
        "missing",
        "zero",
        "declared_field_warning",
    }:
        signals.append(ACTIVATED_NO_POSITIVE_EFFECT)
    elif activation_status in {"missing", "zero"} and not effect_positive:
        if not effect_observation_required:
            signals.append(NOT_EVALUATED_OR_TRIGGERED)
        elif runtime_status in {"missing", "zero"} and not effect_present:
            signals.append(WIRING_SUSPECT)
        else:
            signals.append(NOT_EVALUATED_OR_TRIGGERED)
    return signals


def _mechanism_telemetry_outcome(diagnostic_type: str | None) -> str | None:
    if diagnostic_type == MECHANISM_EXECUTED_NO_IMPROVEMENT:
        return "no_effect"
    if diagnostic_type == EFFECT_ATTRIBUTION_MISSING:
        return "effect_attribution_missing"
    if diagnostic_type == ACTIVATION_MISSING_OR_WIRING_SUSPECT:
        return "activation_missing"
    return None


def _declared_field_issues_for_category(
    issues: Sequence[Any],
    category: str,
) -> list[dict[str, Any]]:
    category_text = str(category or "").strip().lower()
    result: list[dict[str, Any]] = []
    for item in issues:
        if not isinstance(item, Mapping):
            continue
        if str(item.get("category") or "").strip().lower() != category_text:
            continue
        result.append(dict(item))
    return result


def _mechanism_repair_guidance(
    *,
    mechanism: str,
    activation_status: str,
    runtime_status: str,
    effect_status: str,
    diagnostic_kind: str | None = None,
    diagnostic_signals: Sequence[str] = (),
    declared_field_failures: Sequence[Any] = (),
) -> list[str]:
    guidance: list[str] = []
    effect_field_failures = _declared_field_issues_for_category(
        declared_field_failures,
        "effect",
    )
    if effect_field_failures:
        fields = ", ".join(
            dict.fromkeys(
                str(item.get("field") or "").strip()
                for item in effect_field_failures
                if str(item.get("field") or "").strip()
            )
        )
        observed_prefix = ""
        if activation_status == "observed" and runtime_status == "observed":
            observed_prefix = "Activation and runtime telemetry are observed; "
        guidance.append(
            f"{observed_prefix}declared effect field(s) "
            f"{fields or 'unknown'} for mechanism {mechanism} are not positive. "
            "This is not activation missing; repair effect telemetry attribution "
            "or make the mechanism produce true positive evidence for the "
            "declared effect field(s)."
        )
    if diagnostic_kind == NOT_EVALUATED_OR_TRIGGERED:
        guidance.append(
            f"Mechanism {mechanism} was not evaluated or its trigger did not "
            "fire in this short run. Do not fake activation or force "
            "unconditional execution; instrument the natural decision/evaluation "
            "branch and, for rare triggers, use a canary-scoped threshold or "
            "declare a more appropriate conditional telemetry expectation."
        )
    if WIRING_SUSPECT in diagnostic_signals or diagnostic_kind == WIRING_SUSPECT:
        guidance.append(
            f"No mechanism-local context/evaluation evidence was observed for "
            f"{mechanism}. Check that the declared mechanism is wired into the "
            "active solve/search path and that the exact mechanism id is used "
            "by telemetry helpers."
        )
    if RUNTIME_BUDGET_ZERO_OR_SUBMS in diagnostic_signals:
        guidance.append(
            f"Runtime/budget telemetry for {mechanism} is zero-valued while "
            "non-time activation or evaluation evidence exists. Treat this as "
            "zero/sub-ms timer granularity unless other evidence is missing; "
            "do not repair it by adding sleeps, max(..., 1), or fake positive "
            "runtime. Keep context/evaluation instrumentation on the natural "
            "path and record phase duration only from the measured delta."
        )
    if activation_status in {"missing", "zero"}:
        guidance.append(
            "Add direct activation telemetry for declared mechanism "
            f"{mechanism}: record a context/iteration/evaluation counter on "
            "the natural mechanism path, for example "
            f"context.record_iteration('{mechanism}', positive_count). Use "
            "phase runtime as supporting budget evidence, not as the only proof "
            "of activation. Do not unconditionally trigger the mechanism only "
            "to satisfy telemetry; instrument its natural trigger/evaluation "
            "path, use a canary-scoped threshold, or revise expected telemetry "
            "for a conditional mechanism."
        )
    if runtime_status in {"missing", "zero"}:
        detail = "missing" if runtime_status == "missing" else "zero-valued"
        guidance.append(
            "Runtime/budget telemetry for declared mechanism "
            f"{mechanism} is {detail}. Prefer non-time activation/evaluation "
            "evidence to prove the mechanism ran; use "
            f"context.record_phase('{mechanism}', elapsed_ms_delta) only with a "
            "measured phase-duration delta on the natural path. Do not add "
            "unconditional execution, sleeps, or fake positive elapsed time only "
            "to make runtime telemetry positive."
        )
    if (
        effect_status == "zero"
        and activation_status == "observed"
        and not effect_field_failures
    ):
        guidance.append(
            "Mechanism executed but declared effect stayed zero. Treat this as "
            "a no-effect performance outcome, not missing activation; use a "
            "different trigger, schedule, threshold, composition, or mechanism "
            "instead of repeating the unchanged change."
        )
    if effect_status == "missing":
        prefix = (
            "Activation was observed but effect attribution is missing. "
            if activation_status == "observed" or runtime_status == "observed"
            else ""
        )
        guidance.append(
            prefix
            + "Add effect telemetry for declared mechanism "
            f"{mechanism}: context.record_move('{mechanism}', attempted=1, "
            "accepted=accepted_flag, delta=objective_delta, "
            "best_improved=best_improved_flag)."
        )
    return guidance
