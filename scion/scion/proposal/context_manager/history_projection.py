"""Provider-facing V3 screening-memory projection."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

_FULL_CURRENT_ATTEMPTS = 3
_COMPACT_AGGREGATE_FIELDS = (
    "n_cases",
    "wins",
    "losses",
    "ties",
    "win_rate",
    "median_delta",
    "ci_low",
    "ci_high",
    "statistical_metric",
    "statistical_status",
    "valid_pairs",
    "candidate_failed_pairs",
    "metric_stats",
)
_FAILURE_KINDS = {
    "V1_syntax": "syntax",
    "V1b_undefined_names": "syntax",
    "V2_interface": "interface",
    "V3_unit_tests": "unit_test",
    "V4_regression_tests": "regression_test",
    "V5_solution_consistency": "state",
    "V6_feasibility": "feasibility",
    "V7_objective": "objective",
    "V8_nondeterminism": "state",
    "V9_perf_guard": "runtime",
}
_PYTHON_FRAME_RE = re.compile(
    r'^\s*File "(?P<path>[^"]+)", line (?P<line>\d+), in (?P<function>.+?)\s*$'
)
_PYTHON_EXCEPTION_RE = re.compile(
    r"^(?P<type>[A-Za-z_][A-Za-z0-9_.]*(?:Error|Exception)):\s*(?P<message>.*)$"
)


def proposal_screening_history(
    canonical_records: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Project durable records into fixed semantic H memory."""

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for raw in canonical_records:
        record = dict(raw)
        relation = str(record.get("relation") or "").strip()
        source = str(record.get("source_branch_id") or "").strip()
        attempt = str(record.get("attempt_id") or "").strip()
        if relation not in {"current", "sibling"} or not source or not attempt:
            raise ValueError("screening proposal ownership is invalid")
        evidence = record.get("experiment_evidence")
        if not isinstance(evidence, Mapping) or evidence.get("stage") != "screening":
            raise ValueError("provider history accepts screening evidence only")
        group = grouped.setdefault((source, attempt), [])
        if group and group[0].get("relation") != relation:
            raise ValueError("screening proposal relation changed within an attempt")
        group.append(record)

    attempts = [
        (
            str(records[-1]["relation"]),
            source,
            attempt,
            sorted(records, key=lambda item: int(item["round_num"])),
        )
        for (source, attempt), records in grouped.items()
    ]
    attempts.sort(
        key=lambda item: (int(item[3][-1]["round_num"]), item[1], item[2])
    )
    current = [item for item in attempts if item[0] == "current"]
    projected = [
        _attempt(
            records,
            level=(
                "full"
                if index >= len(current) - _FULL_CURRENT_ATTEMPTS
                else "compact"
            ),
        )
        for index, (_relation, _source, _attempt_id, records) in enumerate(current)
    ]

    # A sibling contributes one latest attempt, enough to avoid retrying it.
    siblings = {
        source: item
        for item in attempts
        if item[0] == "sibling"
        for source in (item[1],)
    }
    projected.extend(
        _attempt(records, level="sibling_brief")
        for _relation, _source, _attempt_id, records in sorted(
            siblings.values(),
            key=lambda item: (int(item[3][-1]["round_num"]), item[1], item[2]),
        )
    )
    return projected


def verification_failure_projection(check: Mapping[str, Any]) -> dict[str, str]:
    """Return one typed, semantic failure event rather than a verification log."""

    code = str(check.get("name") or "").strip()
    detail = str(check.get("detail") or "").strip()
    traceback = _python_traceback_projection(detail)
    if traceback:
        return _without_empty(
            {
                "check_code": code,
                "failure_kind": _FAILURE_KINDS.get(code, "verification"),
                **traceback,
            }
        )
    segments = [
        segment.strip()
        for line in detail.splitlines()
        for segment in line.split(" | ")
        if segment.strip()
    ]
    preferred = next(
        (
            segment
            for segment in segments
            if segment.startswith(("FAILED ", "ERROR ", "SyntaxError:"))
        ),
        segments[0] if segments else "",
    )
    return _without_empty(
        {
            "check_code": code,
            "failure_kind": _FAILURE_KINDS.get(code, "verification"),
            "summary": preferred,
        }
    )


def _python_traceback_projection(detail: str) -> dict[str, str]:
    """Keep one actionable Python root cause without exposing workspace paths."""

    lines = [line.rstrip() for line in detail.splitlines()]
    exception: re.Match[str] | None = None
    for line in reversed(lines):
        match = _PYTHON_EXCEPTION_RE.match(line.strip())
        if match:
            exception = match
            break
    if exception is None:
        return {}

    frames: list[re.Match[str]] = []
    for line in lines:
        match = _PYTHON_FRAME_RE.match(line)
        if match:
            frames.append(match)
    last_frame = frames[-1] if frames else None
    exception_type = exception.group("type")
    message = exception.group("message").strip()
    projection = {
        "summary": f"{exception_type}: {message}".rstrip(": "),
        "exception_type": exception_type,
        "message": message,
    }
    if last_frame is not None:
        projection.update(
            {
                "location_file": _relative_source_path(last_frame.group("path")),
                "location_line": last_frame.group("line"),
                "location_function": last_frame.group("function").strip(),
            }
        )
    return _without_empty(projection)


def _relative_source_path(raw_path: str) -> str:
    normalized = raw_path.replace("\\", "/")
    parts = [part for part in normalized.split("/") if part]
    for marker in ("operators", "policies"):
        if marker in parts:
            return "/".join(parts[parts.index(marker) :])
    return parts[-1] if parts else ""


def _attempt(
    records: Sequence[Mapping[str, Any]],
    *,
    level: str,
) -> dict[str, Any]:
    latest = records[-1]
    evidence = latest.get("experiment_evidence")
    if not isinstance(evidence, Mapping):
        raise TypeError("screening proposal evidence is invalid")
    hypothesis = latest.get("hypothesis")
    payload: dict[str, Any] = {
        "relation": str(latest["relation"]),
        "summary_level": level,
        "latest_round": int(latest["round_num"]),
        "proposal_intent": _proposal_intent(hypothesis),
        **_patch_execution(latest.get("candidate_composition")),
        "screening_trajectory": [
            {
                "round_num": int(record["round_num"]),
                **_compact(record["experiment_evidence"]),
            }
            # The latest stage is represented below by experiment_evidence.
            # Keeping only earlier stages here preserves the complete attempt
            # trajectory without presenting the same latest compact facts
            # twice to the hypothesis provider.
            for record in records[:-1]
        ],
    }
    if level == "full":
        payload["candidate_composition"] = _composition(
            latest.get("candidate_composition")
        )
        payload["experiment_evidence"] = _full(evidence)
    else:
        payload["experiment_evidence"] = _compact(evidence)
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
    current_step = projected.get("current_step")
    if isinstance(current_step, dict):
        current_step.pop("hypothesis_id", None)
        if not current_step:
            projected.pop("current_step", None)
    return projected


def _full(value: Mapping[str, Any]) -> dict[str, Any]:
    projected = {
        key: _plain(value[key])
        for key in (
            "stage",
            "protocol_outcome",
            "objective_outcome",
            "runtime_errors",
            "runtime_evidence_policy",
            "mechanism_evidence",
            "decision_outcome",
        )
        if key in value
    }
    cases = value.get("case_outcomes")
    feedback = cases.get("case_feedback") or () if isinstance(cases, Mapping) else ()
    projected["case_outcomes"] = {
        "case_feedback": [
            _case_feedback(item) for item in feedback if isinstance(item, Mapping)
        ]
    }
    return projected


def _compact(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    objective = value.get("objective_outcome")
    aggregate = objective.get("aggregate") if isinstance(objective, Mapping) else None
    return _drop_empty(
        {
            "protocol_outcome": _plain(value.get("protocol_outcome")),
            "objective_outcome": {
                "semantics": (
                    _plain(objective.get("semantics"))
                    if isinstance(objective, Mapping)
                    else None
                ),
                "aggregate": (
                    {
                        key: _plain(aggregate.get(key))
                        for key in _COMPACT_AGGREGATE_FIELDS
                    }
                    if isinstance(aggregate, Mapping)
                    else {}
                ),
                "aggregation": (
                    _plain(objective.get("aggregation"))
                    if isinstance(objective, Mapping)
                    else None
                ),
            },
            "runtime_errors": _plain(value.get("runtime_errors")),
            "decision_outcome": _plain(value.get("decision_outcome")),
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


__all__ = ["proposal_screening_history", "verification_failure_projection"]
