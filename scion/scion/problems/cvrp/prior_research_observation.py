"""Safe CVRP projection for ordinary prior research observations."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from typing import Any

_INPUT_SCHEMA = "scion.cvrp.prior_research_observation.input.v1"
_OUTPUT_SCHEMA = "scion.cvrp.prior_research_observation.v1"
_TOKEN = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]{0,127}$")
_MAX_COMPLETED_STAGES = 16
_MAX_DIAGNOSTICS = 32

_OBSERVATION_FIELDS = frozenset(
    {
        "schema_version",
        "observation_kind",
        "completed_stages",
        "terminal",
        "observed_outputs",
        "claim_context",
    }
)
_STAGE_FIELDS = frozenset(
    {
        "stage",
        "block",
        "valid_pairs",
        "planned_pairs",
        "subject_failures",
        "fleet_regressions",
        "gate_outcome",
        "decision",
        "case_outcomes",
    }
)
_CASE_OUTCOME_FIELDS = frozenset(
    {"wins", "losses", "ties", "median_delta", "ci_low", "ci_high"}
)
_TERMINAL_FIELDS = frozenset(
    {
        "stage",
        "terminal_code",
        "arm",
        "case_id",
        "seed",
        "failure",
        "stage_metrics_produced",
    }
)
_FAILURE_FIELDS = frozenset({"category", "count", "diagnostics"})
_DIAGNOSTIC_FIELDS = frozenset({"name", "value"})
_OBSERVED_OUTPUT_FIELDS = frozenset(
    {
        "validation_stage_metrics",
        "validation_safe_features",
        "validation_decision",
        "frozen_stage_metrics",
        "promotion",
        "retained_baseline_comparison",
    }
)
_CLAIM_CONTEXT_FIELDS = frozenset(
    {
        "evidence_scope",
        "candidate_selection_outcome_known",
        "candidate_discovery_independent",
        "incremental_effect_isolated",
        "population_selection_outcome_blind_relative_to_exact_estimand",
        "exact_candidate_outcome_overlap_count",
        "globally_case_unseen",
        "mde_at_power_80",
    }
)


class _InvalidObservation(ValueError):
    """Internal validation error normalized at the adapter boundary."""


class CvrpPriorResearchObservationProvider:
    """Validate and project a CVRP observation without adding a diagnosis."""

    def project_prior_research_observation(
        self,
        *,
        observation: Mapping[str, Any],
    ) -> Mapping[str, Any] | None:
        try:
            return _project_observation(observation)
        except (KeyError, TypeError, _InvalidObservation) as exc:
            raise ValueError("invalid CVRP prior research observation") from exc


def _project_observation(observation: Mapping[str, Any]) -> dict[str, Any]:
    _exact_fields(observation, _OBSERVATION_FIELDS)
    if observation["schema_version"] != _INPUT_SCHEMA:
        raise _InvalidObservation("unsupported schema")

    completed = observation["completed_stages"]
    if not isinstance(completed, list) or len(completed) > _MAX_COMPLETED_STAGES:
        raise _InvalidObservation("completed_stages must be a bounded list")
    projected_stages = [_project_stage(stage) for stage in completed]

    terminal = _project_terminal(observation["terminal"])
    observed_outputs = _project_observed_outputs(observation["observed_outputs"])
    claim_context = _project_claim_context(observation["claim_context"])

    return {
        "schema_version": _OUTPUT_SCHEMA,
        "observation_kind": _token(observation["observation_kind"]),
        "completed_stages": projected_stages,
        "terminal": terminal,
        "observed_outputs": observed_outputs,
        "claim_context": claim_context,
    }


def _project_stage(value: Any) -> dict[str, Any]:
    stage = _mapping(value)
    _exact_fields(stage, _STAGE_FIELDS)
    valid_pairs = _nonnegative_int(stage["valid_pairs"])
    planned_pairs = _nonnegative_int(stage["planned_pairs"])
    if valid_pairs > planned_pairs:
        raise _InvalidObservation("valid_pairs exceeds planned_pairs")

    outcomes = _mapping(stage["case_outcomes"])
    _exact_fields(outcomes, _CASE_OUTCOME_FIELDS)
    wins = _nonnegative_int(outcomes["wins"])
    losses = _nonnegative_int(outcomes["losses"])
    ties = _nonnegative_int(outcomes["ties"])
    ci_low = _number(outcomes["ci_low"])
    ci_high = _number(outcomes["ci_high"])
    if ci_low > ci_high:
        raise _InvalidObservation("ci_low exceeds ci_high")

    block = stage["block"]
    if block is not None:
        block = _token(block)
    return {
        "stage": _token(stage["stage"]),
        "block": block,
        "valid_pairs": valid_pairs,
        "planned_pairs": planned_pairs,
        "subject_failures": _nonnegative_int(stage["subject_failures"]),
        "fleet_regressions": _nonnegative_int(stage["fleet_regressions"]),
        "gate_outcome": _token(stage["gate_outcome"]),
        "decision": _token(stage["decision"]),
        "case_outcomes": {
            "wins": wins,
            "losses": losses,
            "ties": ties,
            "median_delta": _number(outcomes["median_delta"]),
            "ci_low": ci_low,
            "ci_high": ci_high,
        },
    }


def _project_terminal(value: Any) -> dict[str, Any]:
    terminal = _mapping(value)
    _exact_fields(terminal, _TERMINAL_FIELDS)
    failure = _mapping(terminal["failure"])
    _exact_fields(failure, _FAILURE_FIELDS)
    diagnostics = failure["diagnostics"]
    if not isinstance(diagnostics, list) or len(diagnostics) > _MAX_DIAGNOSTICS:
        raise _InvalidObservation("diagnostics must be a bounded list")

    projected_diagnostics: list[dict[str, Any]] = []
    diagnostic_names: set[str] = set()
    for raw_diagnostic in diagnostics:
        diagnostic = _mapping(raw_diagnostic)
        _exact_fields(diagnostic, _DIAGNOSTIC_FIELDS)
        name = _token(diagnostic["name"])
        if name in diagnostic_names:
            raise _InvalidObservation("diagnostic names must be unique")
        diagnostic_names.add(name)
        projected_diagnostics.append(
            {"name": name, "value": _diagnostic_value(diagnostic["value"])}
        )

    seed = terminal["seed"]
    if type(seed) is int:
        seed = _nonnegative_int(seed)
    else:
        seed = _token(seed)
    return {
        "stage": _token(terminal["stage"]),
        "terminal_code": _token(terminal["terminal_code"]),
        "arm": _token(terminal["arm"]),
        "case_id": _token(terminal["case_id"]),
        "seed": seed,
        "failure": {
            "category": _token(failure["category"]),
            "count": _positive_int(failure["count"]),
            "diagnostics": projected_diagnostics,
        },
        "stage_metrics_produced": _boolean(terminal["stage_metrics_produced"]),
    }


def _project_observed_outputs(value: Any) -> dict[str, bool]:
    outputs = _mapping(value)
    _exact_fields(outputs, _OBSERVED_OUTPUT_FIELDS)
    return {
        "terminal_stage_metrics": _boolean(outputs["validation_stage_metrics"]),
        "terminal_safe_features": _boolean(outputs["validation_safe_features"]),
        "terminal_decision": _boolean(outputs["validation_decision"]),
        "later_stage_metrics": _boolean(outputs["frozen_stage_metrics"]),
        "promotion": _boolean(outputs["promotion"]),
        "retained_baseline_comparison": _boolean(
            outputs["retained_baseline_comparison"]
        ),
    }


def _project_claim_context(value: Any) -> dict[str, Any]:
    context = _mapping(value)
    _exact_fields(context, _CLAIM_CONTEXT_FIELDS)
    mde = context["mde_at_power_80"]
    if mde is not None:
        mde = _number(mde)
    return {
        "evidence_scope": _token(context["evidence_scope"]),
        "candidate_selection_outcome_known": _boolean(
            context["candidate_selection_outcome_known"]
        ),
        "candidate_discovery_independent": _boolean(
            context["candidate_discovery_independent"]
        ),
        "incremental_effect_isolated": _boolean(context["incremental_effect_isolated"]),
        "population_selection_outcome_blind_relative_to_exact_estimand": _boolean(
            context["population_selection_outcome_blind_relative_to_exact_estimand"]
        ),
        "exact_candidate_outcome_overlap_count": _nonnegative_int(
            context["exact_candidate_outcome_overlap_count"]
        ),
        "globally_case_unseen": _boolean(context["globally_case_unseen"]),
        "mde_at_power_80": mde,
    }


def _mapping(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise _InvalidObservation("expected mapping")
    return value


def _exact_fields(value: Mapping[str, Any], expected: frozenset[str]) -> None:
    if set(value) != expected or any(not isinstance(key, str) for key in value):
        raise _InvalidObservation("mapping fields do not match schema")


def _token(value: Any) -> str:
    if not isinstance(value, str) or _TOKEN.fullmatch(value) is None:
        raise _InvalidObservation("expected bounded token")
    return value


def _boolean(value: Any) -> bool:
    if type(value) is not bool:
        raise _InvalidObservation("expected boolean")
    return value


def _nonnegative_int(value: Any) -> int:
    if type(value) is not int or value < 0:
        raise _InvalidObservation("expected nonnegative integer")
    return value


def _positive_int(value: Any) -> int:
    result = _nonnegative_int(value)
    if result == 0:
        raise _InvalidObservation("expected positive integer")
    return result


def _number(value: Any) -> int | float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise _InvalidObservation("expected finite number")
    return value


def _diagnostic_value(value: Any) -> str | int | float | bool | None:
    if value is None or type(value) is bool:
        return value
    if type(value) is int:
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise _InvalidObservation("expected finite diagnostic number")
        return value
    return _token(value)


__all__ = ["CvrpPriorResearchObservationProvider"]
