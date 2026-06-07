"""Expected telemetry field summary checks."""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from scion.runtime.telemetry_guard.issues import _guard_issue
from scion.runtime.telemetry_guard.observations import (
    _matches_protected_objective_field,
    _runtime_field_summary,
)
from scion.runtime.telemetry_guard.summary_mechanisms import (
    _declared_effect_activation_observed,
    _field_is_mechanism_scoped,
    _is_objective_outcome_effect_field,
    _record_declared_field_issue_for_mechanisms,
)
from scion.runtime.telemetry_guard.summary_signals import (
    EFFECT_ATTRIBUTION_MISSING,
    MECHANISM_EXECUTED_NO_IMPROVEMENT,
)


def _record_expected_field_issues(
    *,
    categories: Mapping[str, Sequence[str]],
    candidate_runtimes: Sequence[Mapping[str, Any]],
    champion_runtimes: Sequence[Mapping[str, Any]],
    role_map: Mapping[str, Sequence[str] | frozenset[str]],
    protected_tokens: Sequence[str],
    mechanisms: Sequence[str],
    expected_field_mechanisms: Mapping[str, Sequence[str]],
    activation_probe_fields_by_mechanism: Mapping[str, Sequence[str]],
    effect_observation_required: bool,
    field_summaries: dict[str, dict[str, Any]],
    mechanism_summaries: dict[str, dict[str, Any]],
    failures: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
    zero_activity_issue_code: Callable[[str, Mapping[str, Any]], str],
) -> None:
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
                            True
                            if activation_observed and not protected_effect
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
                    zero_activity_issue_code(category, summary),
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
