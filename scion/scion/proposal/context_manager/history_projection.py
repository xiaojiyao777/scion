"""Provider-facing V3 projection of ordinary in-process research history."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from scion.core.execution_outcome import ExecutionOutcome
from scion.core.models import StepRecord

_PRE_PROTOCOL_STAGES = frozenset(
    {"hypothesis_contract", "patch_contract", "verification"}
)
_STAGE_REASON_CODES = {
    "hypothesis_contract": frozenset({"HYPOTHESIS_CONTRACT_REJECTED"}),
    "patch_contract": frozenset({"PATCH_CONTRACT_REJECTED"}),
    "verification": frozenset(
        {"VERIFICATION_LIGHT_REJECTED", "VERIFICATION_HEAVY_REJECTED"}
    ),
}
_SAFE_CHECK_NAME = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$")
_PATCH_ACTIONS = frozenset({"modify", "create", "delete"})

_SCREENING_EVAL_STAT_FIELDS = (
    "n_cases",
    "wins",
    "losses",
    "ties",
    "win_rate",
    "median_delta",
    "ci_low",
    "ci_high",
    "statistical_status",
    "statistical_metric",
    "metric_stats",
    "protected_objective_regressions",
    "runtime_ratio_median",
    "runtime_delta_median_ms",
    "runtime_regression_rate",
    "runtime_pairs",
    "total_pairs",
    "attempted_pairs",
    "valid_pairs",
    "failed_pairs",
    "candidate_failed_pairs",
    "champion_failed_pairs",
    "shared_failed_pairs",
    "bilateral_failed_pairs",
    "pair_wins",
    "pair_losses",
    "pair_ties",
)


def proposal_screening_history(
    canonical_records: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Project every visible screening into safe, lossless H memory.

    Branch and attempt identifiers are storage details, not scientific facts.
    They must not decide which observations survive into later research
    context.  Each screening is therefore projected once, in ordinary round
    order, without recent-N compaction or sibling overwrites.
    """

    records: list[dict[str, Any]] = []
    for raw in canonical_records:
        record = dict(raw)
        relation = str(record.get("relation") or "").strip()
        if relation not in {"current", "sibling"}:
            raise ValueError("screening proposal relation is invalid")
        evidence = record.get("experiment_evidence")
        if not isinstance(evidence, Mapping) or evidence.get("stage") != "screening":
            raise ValueError("provider history accepts screening evidence only")
        records.append(record)

    records.sort(key=lambda item: int(item["round_num"]))
    return [_screening(record) for record in records]


def proposal_pre_protocol_observations(
    steps: Sequence[StepRecord],
) -> list[dict[str, Any]]:
    """Project ordinary pre-Protocol rejection facts for the next H call.

    ``steps`` is already the append-ordered in-process campaign record.  Keep
    every eligible observation in that order and never query a second durable
    source or compact repeated attempts.  Free-form failure prose, patch source,
    paths, metadata, and identities deliberately remain outside this boundary.
    """

    observations: list[dict[str, Any]] = []
    for step in steps:
        outcome = step.execution_outcome
        stage = step.failure_stage
        if (
            outcome is None
            or outcome.outcome is not ExecutionOutcome.RESEARCH_REJECTED
            or stage not in _PRE_PROTOCOL_STAGES
        ):
            continue
        observations.append(
            {
                "hypothesis": _pre_protocol_hypothesis(step),
                "patch": _pre_protocol_patch(step),
                "outcome": _pre_protocol_outcome(step),
            }
        )
    return observations


def _pre_protocol_hypothesis(step: StepRecord) -> dict[str, Any]:
    hypothesis = step.hypothesis
    return _without_empty(
        {
            "hypothesis_text": hypothesis.hypothesis_text,
            "change_locus": hypothesis.change_locus,
            "action": hypothesis.action,
            "predicted_direction": hypothesis.predicted_direction,
            "target_weakness": hypothesis.target_weakness,
            "expected_effect": hypothesis.expected_effect,
            "suggested_weight": hypothesis.suggested_weight,
        }
    )


def _pre_protocol_patch(step: StepRecord) -> dict[str, Any]:
    patch = step.patch
    if patch is None:
        return {"present": False}
    changes: list[Any] = [patch]
    additional = getattr(patch, "additional_changes", ()) or ()
    if isinstance(additional, (list, tuple)):
        changes.extend(additional)
    actions = sorted(
        {
            action
            for change in changes
            if (action := _change_action(change)) in _PATCH_ACTIONS
        }
    )
    return {
        "present": True,
        "change_count": len(changes),
        "actions": actions,
    }


def _change_action(change: Any) -> str:
    if isinstance(change, Mapping):
        value = change.get("action")
    else:
        value = getattr(change, "action", None)
    return str(value or "").strip()


def _pre_protocol_outcome(step: StepRecord) -> dict[str, Any]:
    outcome = step.execution_outcome
    assert outcome is not None  # guarded by proposal_pre_protocol_observations
    stage = str(step.failure_stage)
    projection: dict[str, Any] = {
        "stage": stage,
        "reason_code": _safe_reason_code(stage, outcome.reason_code),
    }
    provenance = outcome.provenance
    if stage == "verification":
        severity = provenance.get("severity")
        if severity in {"light", "heavy"}:
            projection["severity"] = severity
    checks_key = "verification_checks" if stage == "verification" else "contract_checks"
    projection["checks"] = _safe_checks(provenance.get(checks_key))
    return projection


def _safe_reason_code(stage: str, value: Any) -> str:
    reason_code = str(value or "").strip()
    if reason_code in _STAGE_REASON_CODES.get(stage, ()):
        return reason_code
    return ExecutionOutcome.RESEARCH_REJECTED.value.upper()


def _safe_checks(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, (list, tuple)):
        return []
    projected: list[dict[str, Any]] = []
    for check in value:
        if not isinstance(check, Mapping):
            continue
        name = check.get("name")
        passed = check.get("passed")
        severity = check.get("severity")
        if (
            not isinstance(name, str)
            or _SAFE_CHECK_NAME.fullmatch(name) is None
            or not isinstance(passed, bool)
            or severity not in {"light", "heavy"}
        ):
            continue
        projected.append(
            {
                "name": name,
                "passed": passed,
                "severity": severity,
            }
        )
    return projected


def _screening(record: Mapping[str, Any]) -> dict[str, Any]:
    evidence = record.get("experiment_evidence")
    if not isinstance(evidence, Mapping):
        raise TypeError("screening proposal evidence is invalid")
    hypothesis = record.get("hypothesis")
    payload: dict[str, Any] = {
        "relation": str(record["relation"]),
        "summary_level": "full",
        "latest_round": int(record["round_num"]),
        "proposal_intent": _proposal_intent(hypothesis),
        **_patch_execution(record.get("candidate_composition")),
        "candidate_composition": _composition(record.get("candidate_composition")),
        "experiment_evidence": _full(evidence),
    }
    return _without_empty(payload)


def _proposal_intent(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return _without_empty(
        {
            key: _plain(value.get(key))
            for key in (
                "hypothesis_text",
                "change_locus",
                "action",
                "target_file",
                "predicted_direction",
                "target_weakness",
                "expected_effect",
                "suggested_weight",
            )
        }
    )


def _patch_execution(value: Any) -> dict[str, Any]:
    """Project only recorded current-step patch facts, never mechanism meaning."""

    if not isinstance(value, Mapping):
        return {}
    change_scope = value.get("current_step_change_scope")
    if change_scope == "eval_only_reuse":
        return {"patch_present": False}
    if change_scope != "incremental_patch":
        return {}
    execution: dict[str, Any] = {"patch_present": True}
    current_step = value.get("current_step")
    target_files = (
        current_step.get("target_files")
        if isinstance(current_step, Mapping)
        else None
    )
    if isinstance(target_files, (list, tuple)):
        execution["executed_patch_files"] = _plain(target_files)
    return execution


def _composition(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    projected = _plain(value)
    return projected


def _full(value: Mapping[str, Any]) -> dict[str, Any]:
    projected = {
        key: _plain(value[key])
        for key in (
            "stage",
            "protocol_outcome",
            "runtime_model",
            "runtime_errors",
            "mechanism_evidence",
            "decision_outcome",
        )
        if key in value
    }
    objective = value.get("objective_outcome")
    if isinstance(objective, Mapping):
        projected_objective = _plain(objective)
        aggregate = objective.get("aggregate")
        if isinstance(projected_objective, dict) and isinstance(aggregate, Mapping):
            projected_objective["aggregate"] = screening_eval_stats(aggregate)
        projected["objective_outcome"] = projected_objective
    cases = value.get("case_outcomes")
    feedback = cases.get("case_feedback") or () if isinstance(cases, Mapping) else ()
    projected["case_outcomes"] = {
        "case_feedback": [
            _case_feedback(item) for item in feedback if isinstance(item, Mapping)
        ]
    }
    return projected


def screening_eval_stats(value: Mapping[str, Any]) -> dict[str, Any]:
    """Project only measured EvalStats fields into screening memory."""

    return _drop_empty(
        {
            key: _plain(value[key])
            for key in _SCREENING_EVAL_STAT_FIELDS
            if key in value
        }
    )


def _case_feedback(value: Mapping[str, Any]) -> dict[str, Any]:
    features = value.get("case_features")
    safe_features = (
        {
            str(key): _plain(item)
            for key, item in features.items()
            if str(key) not in {"case_id", "path", "path_stem"}
        }
        if isinstance(features, Mapping)
        else {}
    )
    return _drop_empty(
        {
            **{
                key: _plain(value.get(key))
                for key in (
                    "n_pairs",
                    "wins",
                    "losses",
                    "ties",
                    "win_rate",
                    "dominant_result",
                    "seed_pattern",
                    "median_deltas",
                    "decisive_metric",
                    "seed_consistency",
                )
            },
            "case_features": safe_features,
        }
    )


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (set, frozenset)):
        return [_plain(item) for item in sorted(value, key=repr)]
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


def _drop_empty(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): projected
            for key, item in value.items()
            if (projected := _drop_empty(item)) not in (None, "", [], {})
        }
    if isinstance(value, list):
        return [_drop_empty(item) for item in value]
    return value


def _without_empty(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        str(key): item
        for key, item in value.items()
        if item not in (None, "", [], {})
    }


__all__ = [
    "proposal_pre_protocol_observations",
    "proposal_screening_history",
    "screening_eval_stats",
]
