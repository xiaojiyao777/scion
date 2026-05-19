"""Runtime smoke summaries for algorithm-smoke agent feedback."""

from __future__ import annotations

from typing import Any, Mapping

from scion.proposal.tools.previews.algorithm_smoke_feedback_text import (
    _ALGORITHM_SMOKE_AGENT_COUNTER_ITEMS,
    _ALGORITHM_SMOKE_AGENT_TEXT_CHARS,
    _compact_agent_text,
    _compact_agent_text_list,
    _first_mapping,
    _mapping_or_none,
    _runtime_event_text,
    _tail_text,
)
from scion.proposal.tools.surface import _drop_empty_items
from scion.proposal.tools.utils import _limit_text


def _algorithm_smoke_runtime_agent_section(
    runtime_smoke: Mapping[str, Any] | None,
    *,
    telemetry_guard: Mapping[str, Any] | None,
    runtime_counters: Mapping[str, Any] | None,
    subprocess_tail: Mapping[str, Any] | None,
    runtime_comparison: Mapping[str, Any] | None,
    repair_hints: list[str],
) -> dict[str, Any] | None:
    if runtime_smoke is None:
        return None
    compact = _drop_empty_items(
        {
            "passed": runtime_smoke.get("passed"),
            "runtime_smoke_run": runtime_smoke.get("runtime_smoke_run"),
            "workspace_materialized": runtime_smoke.get("workspace_materialized"),
            "selected_surface": runtime_smoke.get("selected_surface"),
            "case": runtime_smoke.get("case"),
            "case_path_ref": runtime_smoke.get("case_path_ref"),
            "data_root_source": runtime_smoke.get("data_root_source"),
            "data_root_status": runtime_smoke.get("data_root_status"),
            "provenance": _compact_runtime_provenance(runtime_smoke.get("provenance")),
            "seed": runtime_smoke.get("seed"),
            "case_count": runtime_smoke.get("case_count"),
            "issues": _compact_agent_text_list(runtime_smoke.get("issues")),
            "repair_guidance": repair_hints,
            "runtime_audit_failure": _compact_runtime_audit_failure_for_agent(
                runtime_smoke.get("runtime_audit_failure")
            ),
            "telemetry_guard": telemetry_guard,
            "runtime_counters": runtime_counters,
            "subprocess": subprocess_tail,
            "micro_benchmark": runtime_comparison,
        }
    )
    return compact or None


def _compact_runtime_provenance(value: Any) -> dict[str, Any] | None:
    provenance = _mapping_or_none(value)
    if provenance is None:
        return None
    return _drop_empty_items(
        {
            "source": provenance.get("source"),
            "case_ref": provenance.get("case_ref"),
            "data_root_source": provenance.get("data_root_source"),
            "data_root_status": provenance.get("data_root_status"),
            "absolute_paths_exposed": provenance.get("absolute_paths_exposed"),
        }
    )


def _compact_runtime_audit_failure_for_agent(value: Any) -> dict[str, Any] | None:
    audit = _mapping_or_none(value)
    if audit is None:
        text = _compact_agent_text(value)
        return {"detail": text} if text else None
    event_text = _runtime_event_text(audit.get("solver_algorithm_events"))
    compact = _drop_empty_items(
        {
            "error_category": _compact_agent_text(
                audit.get("error_category"),
                max_chars=160,
            ),
            "detail": _compact_agent_text(audit.get("detail")),
            "failed_runtime_fields": _compact_agent_text_list(
                audit.get("failed_runtime_fields")
            ),
            "solver_algorithm_errors": audit.get("solver_algorithm_errors"),
            "event_tail": event_text,
        }
    )
    return compact or None


def _compact_algorithm_smoke_runtime_counters(value: Any) -> dict[str, Any] | None:
    runtime = _mapping_or_none(value)
    if runtime is None:
        return None
    keys = (
        "solver_algorithm_path",
        "solver_algorithm_loaded",
        "solver_algorithm_active",
        "solver_algorithm_errors",
        "solver_algorithm_elapsed_ms",
        "solver_algorithm_solution_valid",
        "solver_algorithm_total_distance",
        "solver_algorithm_fleet_violation",
        "solver_algorithm_baseline_calls",
        "solver_algorithm_baseline_errors",
        "solver_algorithm_search_iterations",
        "solver_algorithm_move_attempts",
        "solver_algorithm_accepted_moves",
        "solver_algorithm_improving_moves",
        "solver_algorithm_best_delta",
        "solver_algorithm_phase_delta_sum",
        "solver_algorithm_stop_reason",
    )
    compact: dict[str, Any] = {}
    for key in keys:
        if key not in runtime:
            continue
        if key == "solver_algorithm_path":
            path = str(runtime.get(key) or "")
            if path.startswith("/"):
                continue
            compact[key] = path
            continue
        compact[key] = runtime.get(key)
        if len(compact) >= _ALGORITHM_SMOKE_AGENT_COUNTER_ITEMS:
            break
    return _drop_empty_items(compact) or None


def _compact_algorithm_smoke_subprocess(value: Any) -> dict[str, Any] | None:
    run = _mapping_or_none(value)
    if run is None:
        return None
    compact = _drop_empty_items(
        {
            "success": run.get("success"),
            "exit_code": run.get("exit_code"),
            "elapsed_ms": run.get("elapsed_ms"),
            "error_category": _compact_agent_text(
                run.get("error_category"),
                max_chars=160,
            ),
            "detail": _compact_agent_text(run.get("detail")),
            "stderr_tail": _tail_text(run.get("stderr")),
            "stdout_tail": _tail_text(run.get("stdout")),
        }
    )
    return compact or None


def _compact_algorithm_smoke_runtime_comparison(
    runtime_smoke: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    if runtime_smoke is None:
        return None
    benchmark = _mapping_or_none(runtime_smoke.get("micro_benchmark"))
    if benchmark is None:
        return None
    representative = _representative_micro_result(
        benchmark.get("results"),
        runtime_smoke.get("runs"),
    )
    compact = _drop_empty_items(
        {
            "non_promotional": benchmark.get("non_promotional", True),
            "tainted_debug": benchmark.get("tainted_debug", True),
            "comparable_cases": benchmark.get("comparable_cases"),
            "wins": benchmark.get("wins"),
            "losses": benchmark.get("losses"),
            "ties": benchmark.get("ties"),
            "representative_case": representative,
        }
    )
    return compact or None


def _representative_micro_result(results: Any, runs: Any) -> dict[str, Any] | None:
    selected: Mapping[str, Any] | None = None
    if isinstance(results, (list, tuple)):
        for item in results:
            if isinstance(item, Mapping) and item.get("comparison") == "loss":
                selected = item
                break
        if selected is None:
            selected = next((item for item in results if isinstance(item, Mapping)), None)
    raw_run_micro: Mapping[str, Any] | None = None
    raw_objective: Mapping[str, Any] | None = None
    if isinstance(runs, (list, tuple)):
        for run in runs:
            if not isinstance(run, Mapping):
                continue
            micro = _mapping_or_none(run.get("micro_benchmark"))
            if selected is None and micro is not None:
                selected = micro
            if selected is not None and micro is not None:
                raw_run_micro = micro
                raw_objective = _mapping_or_none(run.get("objective"))
                break
    if selected is None:
        return None
    raw_run_micro = raw_run_micro or selected
    compact = _drop_empty_items(
        {
            "label": selected.get("label"),
            "case": selected.get("case"),
            "seed": selected.get("seed"),
            "comparison": selected.get("comparison"),
            "delta": selected.get("delta"),
            "decisive_metric": selected.get("decisive_metric"),
            "runtime_delta_ms": selected.get("runtime_delta_ms"),
            "candidate_objective": _compact_objective(
                raw_run_micro.get("candidate_objective") or raw_objective
            ),
            "champion_objective": _compact_objective(
                raw_run_micro.get("champion_objective")
            ),
        }
    )
    return compact or None


def _compact_objective(value: Any) -> dict[str, Any] | None:
    objective = _mapping_or_none(value)
    if objective is None:
        return None
    return _drop_empty_items(
        {
            key: objective.get(key)
            for key in ("fleet_violation", "total_distance")
            if key in objective
        }
    ) or None


def _compact_algorithm_smoke_telemetry_guard(value: Any) -> dict[str, Any] | None:
    guard = _mapping_or_none(value)
    if guard is None:
        return None
    failures = _compact_telemetry_issues(guard.get("failures"))
    warnings = _compact_telemetry_issues(guard.get("warnings"), limit=3)
    first_failure = failures[0] if failures else None
    compact = _drop_empty_items(
        {
            "triggered": bool(failures),
            "passed": guard.get("passed"),
            "selected_surface": guard.get("selected_surface"),
            "failure_code": first_failure.get("code") if first_failure else None,
            "mechanism": first_failure.get("mechanism") if first_failure else None,
            "category": first_failure.get("category") if first_failure else None,
            "field": first_failure.get("field") if first_failure else None,
            "counters": first_failure.get("counters") if first_failure else None,
            "candidate_runs": guard.get("candidate_runs"),
            "champion_runs": guard.get("champion_runs"),
            "expected_telemetry_present": guard.get("expected_telemetry_present"),
            "implicit_activity_claim": guard.get("implicit_activity_claim"),
            "protected_objectives": _compact_agent_text_list(
                guard.get("protected_objectives")
            ),
            "declared_mechanisms": _compact_agent_text_list(
                guard.get("declared_mechanisms")
            ),
            "mechanism_diagnostics": _compact_mechanism_diagnostics(
                guard.get("mechanism_diagnostics")
            ),
            "failures": failures,
            "warnings": warnings,
        }
    )
    return compact or None


def _compact_telemetry_issues(value: Any, *, limit: int = 4) -> list[dict[str, Any]]:
    if not isinstance(value, (list, tuple)):
        return []
    issues: list[dict[str, Any]] = []
    for item in value[:limit]:
        if not isinstance(item, Mapping):
            continue
        counters = {
            key: item.get(key)
            for key in (
                "candidate_positive",
                "candidate_present",
                "candidate_zero",
                "candidate_missing",
                "champion_positive",
            )
            if key in item
        }
        issues.append(
            _drop_empty_items(
                {
                    "code": item.get("code"),
                    "severity": item.get("severity"),
                    "mechanism": item.get("mechanism"),
                    "category": item.get("category"),
                    "field": item.get("field"),
                    "counters": counters,
                }
            )
        )
    return issues


def _compact_mechanism_diagnostics(value: Any, *, limit: int = 6) -> list[dict[str, Any]]:
    if not isinstance(value, (list, tuple)):
        return []
    diagnostics: list[dict[str, Any]] = []
    for item in value[:limit]:
        if not isinstance(item, Mapping):
            continue
        diagnostics.append(
            _drop_empty_items(
                {
                    "mechanism": item.get("mechanism"),
                    "activation_status": item.get("activation_status"),
                    "runtime_status": item.get("runtime_status"),
                    "effect_status": item.get("effect_status"),
                    "activation_observed": item.get("activation_observed"),
                    "runtime_observed": item.get("runtime_observed"),
                    "effect_observed": item.get("effect_observed"),
                    "activation": _compact_status_block(item.get("activation")),
                    "runtime": _compact_status_block(item.get("runtime")),
                    "effect": _compact_status_block(item.get("effect")),
                    "repair_guidance": _compact_agent_text_list(
                        item.get("repair_guidance"),
                        limit=3,
                    ),
                }
            )
        )
    return diagnostics


def _compact_status_block(value: Any) -> dict[str, Any] | None:
    block = _mapping_or_none(value)
    if block is None:
        return None
    counters = {
        key: block.get(key)
        for key in (
            "candidate_positive",
            "candidate_present",
            "candidate_zero",
            "candidate_missing",
        )
        if key in block
    }
    compact = _drop_empty_items(
        {
            "status": block.get("status"),
            "fields": _compact_agent_text_list(block.get("fields"), limit=3),
            "counters": counters,
        }
    )
    return compact or None


def _telemetry_guard_primary_issue(value: Mapping[str, Any] | None) -> str | None:
    if value is None:
        return None
    first = _first_mapping(value.get("failures"))
    if not first:
        return None
    parts = ["telemetry guard failed"]
    for label, key in (
        ("code", "code"),
        ("mechanism", "mechanism"),
        ("category", "category"),
        ("field", "field"),
    ):
        if first.get(key):
            parts.append(f"{label}={first.get(key)}")
    counters = _mapping_or_none(first.get("counters"))
    if counters:
        parts.extend(f"{key}={counters[key]}" for key in sorted(counters))
    return _limit_text("; ".join(parts), _ALGORITHM_SMOKE_AGENT_TEXT_CHARS)


__all__ = [
    "_algorithm_smoke_runtime_agent_section",
    "_compact_algorithm_smoke_runtime_comparison",
    "_compact_algorithm_smoke_runtime_counters",
    "_compact_algorithm_smoke_subprocess",
    "_compact_algorithm_smoke_telemetry_guard",
    "_telemetry_guard_primary_issue",
]
