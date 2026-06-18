"""Mechanism-scoped telemetry summary diagnostics."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from scion.runtime.telemetry_guard.declarations import runtime_field_roles_for
from scion.runtime.telemetry_guard.observations import _runtime_field_summary
from scion.runtime.telemetry_guard.summary_repair import (
    _declared_field_issues_for_category,
    _mechanism_repair_guidance,
)
from scion.runtime.telemetry_guard.summary_signals import (
    ACTIVATED_NO_POSITIVE_EFFECT,
    ACTIVATION_MISSING_OR_WIRING_SUSPECT,
    EFFECT_ATTRIBUTION_MISSING,
    EVALUATED_NO_EFFECT,
    MECHANISM_EXECUTED_NO_IMPROVEMENT,
    NOT_EVALUATED_OR_TRIGGERED,
    RUNTIME_BUDGET_ZERO_OR_SUBMS,
    WIRING_SUSPECT,
)

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
                "declared_field_warning_status": "declared_field_warning",
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
