from __future__ import annotations

import statistics
from collections.abc import Mapping
from typing import Any, Sequence

from scion.core.models import EvalStats, RunResult
from .failures import _bounded_runtime_failure
from .values import _as_int, _bounded_json_value, _increment_category, _is_json_scalar


def _candidate_runtime_observation(result: RunResult) -> dict[str, Any]:
    runtime = getattr(getattr(result, "output", None), "runtime", None)
    if not isinstance(runtime, dict):
        return {"categories": {}, "counters": {}, "stop_reasons": {}}

    counters = {
        "operator_attempts": _as_int(runtime.get("operator_attempts")),
        "operator_accepted": _as_int(runtime.get("operator_accepted")),
        "operator_errors": _as_int(runtime.get("operator_errors")),
        "operator_invalid_outputs": _as_int(runtime.get("operator_invalid_outputs")),
        "policy_errors": _as_int(runtime.get("policy_errors")),
        "construction_errors": _as_int(runtime.get("construction_errors")),
        "portfolio_errors": _as_int(runtime.get("portfolio_errors")),
        "solver_algorithm_errors": _as_int(runtime.get("solver_algorithm_errors")),
        "solver_algorithm_search_iterations": _as_int(
            runtime.get("solver_algorithm_search_iterations")
        ),
        "solver_algorithm_move_attempts": _as_int(
            runtime.get("solver_algorithm_move_attempts")
        ),
        "solver_algorithm_accepted_moves": _as_int(
            runtime.get("solver_algorithm_accepted_moves")
        ),
        "solver_algorithm_improving_moves": _as_int(
            runtime.get("solver_algorithm_improving_moves")
        ),
        "solver_algorithm_neutral_accepted_moves": _as_int(
            runtime.get("solver_algorithm_neutral_accepted_moves")
        ),
        "solver_algorithm_baseline_calls": _as_int(
            runtime.get("solver_algorithm_baseline_calls")
        ),
        "solver_algorithm_baseline_errors": _as_int(
            runtime.get("solver_algorithm_baseline_errors")
        ),
    }
    categories: dict[str, int] = {}
    first_failure: dict[str, Any] | None = None

    for counter_name, category in (
        ("construction_errors", "construction_error"),
        ("portfolio_errors", "portfolio_error"),
        ("policy_errors", "policy_error"),
        ("solver_algorithm_errors", "solver_algorithm_error"),
        ("solver_algorithm_baseline_errors", "solver_algorithm_baseline_error"),
        ("operator_invalid_outputs", "invalid_output"),
        ("operator_errors", "operator_error"),
    ):
        count = counters[counter_name]
        if count <= 0:
            continue
        categories[category] = categories.get(category, 0) + count
        if first_failure is None:
            first_failure = _bounded_runtime_failure(
                category=category,
                code=counter_name,
                surface=None,
                component=counter_name.removesuffix("_errors"),
                detail_summary=f"solver runtime reported {counter_name}={count}",
            )

    if counters["operator_attempts"] > 0 and counters["operator_accepted"] == 0:
        categories["no_accepted_moves"] = categories.get("no_accepted_moves", 0) + 1

    stop_reasons: dict[str, int] = {}
    for key in ("operator_stop_reason", "solver_algorithm_stop_reason"):
        stop_reason = str(runtime.get(key) or "").strip()
        if stop_reason:
            stop_reasons[stop_reason] = stop_reasons.get(stop_reason, 0) + 1

    return {
        "categories": categories,
        "counters": counters,
        "stop_reasons": stop_reasons,
        "first_failure": first_failure,
    }


def _merge_runtime_observation(
    observation: dict[str, Any],
    *,
    categories: dict[str, int],
    counters: dict[str, int],
    stop_reasons: dict[str, int],
) -> None:
    for category, count in (observation.get("categories") or {}).items():
        _increment_category(categories, str(category), _as_int(count))
    for name, count in (observation.get("counters") or {}).items():
        if name in counters:
            counters[name] += _as_int(count)
    for reason, count in (observation.get("stop_reasons") or {}).items():
        reason_text = str(reason).strip()
        if reason_text:
            stop_reasons[reason_text] = stop_reasons.get(reason_text, 0) + _as_int(count)


def _runtime_fields(
    cand_r: RunResult | None,
    champ_r: RunResult | None,
    *,
    candidate_required_runtime_fields: Sequence[str] = (),
) -> dict:
    candidate_elapsed = getattr(cand_r, "elapsed_ms", None)
    champion_elapsed = getattr(champ_r, "elapsed_ms", None)
    fields = {
        "candidate_elapsed_ms": candidate_elapsed,
        "champion_elapsed_ms": champion_elapsed,
        "runtime_ratio": None,
        "runtime_delta_ms": None,
        "candidate_runtime": _runtime_audit_summary(
            cand_r,
            required_runtime_fields=candidate_required_runtime_fields,
        ),
        "champion_runtime": _runtime_audit_summary(champ_r),
    }
    if candidate_elapsed is None or champion_elapsed is None:
        return fields
    fields["runtime_delta_ms"] = int(candidate_elapsed) - int(champion_elapsed)
    if champion_elapsed > 0:
        fields["runtime_ratio"] = float(candidate_elapsed) / float(champion_elapsed)
    return fields


def _append_guard_runtime(
    target: list[Mapping[str, Any]],
    result: RunResult | None,
) -> None:
    runtime = getattr(getattr(result, "output", None), "runtime", None)
    if isinstance(runtime, Mapping):
        target.append(runtime)


def _runtime_audit_summary(
    result: RunResult | None,
    *,
    required_runtime_fields: Sequence[str] = (),
) -> dict:
    runtime = getattr(getattr(result, "output", None), "runtime", None)
    if not isinstance(runtime, dict):
        return {}
    summary = {
        key: value
        for key, value in runtime.items()
        if key.startswith((
            "baseline_",
            "operator_",
            "policy_",
            "construction_",
            "portfolio_",
            "solver_algorithm_",
        ))
        and key not in ("operator_events", "policy_events", "solver_algorithm_events")
        and _is_json_scalar(value)
    }
    for field in required_runtime_fields:
        if field in runtime:
            summary[field] = _bounded_json_value(runtime[field])
    events = runtime.get("operator_events")
    if isinstance(events, list):
        summary["operator_events"] = events[:5]
    policy_events = runtime.get("policy_events")
    if isinstance(policy_events, list):
        summary["policy_events"] = policy_events[:5]
    solver_algorithm_events = runtime.get("solver_algorithm_events")
    if isinstance(solver_algorithm_events, list):
        summary["solver_algorithm_events"] = solver_algorithm_events[:5]
    return summary


def _record_runtime_sample(
    fields: dict,
    ratios: list[float],
    deltas_ms: list[float],
) -> None:
    ratio = fields.get("runtime_ratio")
    delta = fields.get("runtime_delta_ms")
    if ratio is not None:
        ratios.append(float(ratio))
    if delta is not None:
        deltas_ms.append(float(delta))


def _build_runtime_stats(
    ratios: list[float],
    deltas_ms: list[float],
) -> dict:
    runtime_pairs = len(deltas_ms)
    regression_count = sum(1 for d in deltas_ms if d > 0)
    return {
        "runtime_ratio_median": statistics.median(ratios) if ratios else None,
        "runtime_delta_median_ms": statistics.median(deltas_ms) if deltas_ms else None,
        "runtime_regression_rate": (
            regression_count / runtime_pairs if runtime_pairs else None
        ),
        "runtime_pairs": runtime_pairs,
    }


def _format_runtime_summary(stats: EvalStats) -> str:
    ratio = (
        f"{stats.runtime_ratio_median:.2f}"
        if stats.runtime_ratio_median is not None
        else "NA"
    )
    delta = (
        f"{stats.runtime_delta_median_ms:.1f}"
        if stats.runtime_delta_median_ms is not None
        else "NA"
    )
    regression = (
        f"{stats.runtime_regression_rate:.2f}"
        if stats.runtime_regression_rate is not None
        else "NA"
    )
    return (
        f"runtime_pairs={stats.runtime_pairs} "
        f"runtime_ratio_median={ratio} "
        f"runtime_delta_median_ms={delta} "
        f"runtime_regression_rate={regression}"
    )


def _format_telemetry_guard_summary(summary: Mapping[str, Any]) -> str:
    if not summary:
        return ""
    if not (
        summary.get("selected_surface")
        or summary.get("expected_telemetry_present")
        or summary.get("failures")
        or summary.get("warnings")
    ):
        return ""
    failures = summary.get("failures")
    warnings = summary.get("warnings")
    failure_codes = [
        str(item.get("code"))
        for item in failures or []
        if isinstance(item, Mapping) and item.get("code")
    ]
    warning_codes = [
        str(item.get("code"))
        for item in warnings or []
        if isinstance(item, Mapping) and item.get("code")
    ]
    if not failure_codes and not warning_codes:
        return " telemetry_guard=pass"
    parts = []
    if failure_codes:
        parts.append("failures=" + ",".join(failure_codes[:4]))
    if warning_codes:
        parts.append("warnings=" + ",".join(warning_codes[:4]))
    return " telemetry_guard=" + ";".join(parts)


__all__ = [
    "_append_guard_runtime",
    "_build_runtime_stats",
    "_candidate_runtime_observation",
    "_format_runtime_summary",
    "_format_telemetry_guard_summary",
    "_merge_runtime_observation",
    "_record_runtime_sample",
    "_runtime_audit_summary",
    "_runtime_fields",
]
