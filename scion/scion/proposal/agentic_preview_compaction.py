"""Compaction helpers for APS preview observations."""
from __future__ import annotations

import json
from typing import Any, Mapping

from scion.proposal.agentic_utils import (
    _bounded_string_list,
    _drop_empty_mapping,
    _json_ready,
    _limit_string,
)


def _compact_contract_preview_section(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    failed_checks = _failed_preview_checks(value.get("checks"))
    if not failed_checks:
        failed_checks = _existing_failed_preview_checks(
            value.get("failed_checks"),
            limit=8,
        )
    compact = _drop_empty_mapping(
        {
            "passed": value.get("passed"),
            "issue_summary": _limit_string(value.get("issue_summary"), 700),
            "contract": _compact_contract_mapping(value.get("contract")),
            "needs_hypothesis": value.get("needs_hypothesis"),
            "errors": _bounded_string_list(value.get("errors"), limit=4),
            "issues": _bounded_string_list(value.get("issues"), limit=4),
            "failed_checks": failed_checks,
            "repair_templates": _compact_repair_templates(
                value.get("repair_templates")
            ),
            "problem_preview": _compact_problem_preview_mapping(
                value.get("problem_preview")
            ),
        }
    )
    return compact or None

def _minimal_contract_preview_section(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    failed_checks = _failed_preview_checks(value.get("checks"))
    if not failed_checks:
        failed_checks = _existing_failed_preview_checks(
            value.get("failed_checks"),
            limit=3,
        )
    compact = _drop_empty_mapping(
        {
            "passed": value.get("passed"),
            "issue_summary": _limit_string(value.get("issue_summary"), 360),
            "errors": _bounded_string_list(value.get("errors"), limit=2),
            "issues": _bounded_string_list(value.get("issues"), limit=2),
            "failed_checks": failed_checks[:3],
            "repair_templates": _compact_repair_templates(
                value.get("repair_templates"),
                limit=2,
            ),
        }
    )
    return compact or None


def _compact_repair_templates(
    value: Any,
    *,
    limit: int = 4,
) -> list[dict[str, Any]]:
    if not isinstance(value, (list, tuple)):
        return []
    templates: list[dict[str, Any]] = []
    for item in value[:limit]:
        if not isinstance(item, Mapping):
            continue
        templates.append(
            _drop_empty_mapping(
                {
                    "repair_type": item.get("repair_type"),
                    "check": item.get("check"),
                    "severity": item.get("severity"),
                    "missing_fields": _bounded_string_list(
                        item.get("missing_fields"),
                        limit=8,
                    ),
                    "observed": item.get("observed"),
                    "recommended_shape": item.get("recommended_shape"),
                    "required_template": item.get("required_template"),
                    "agent_instruction": _bounded_string_list(
                        item.get("agent_instruction"),
                        limit=4,
                    ),
                }
            )
        )
    return [template for template in templates if template]

def _minimal_algorithm_smoke_section(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    audit_failure = value.get("runtime_audit_failure")
    if isinstance(audit_failure, Mapping):
        audit_detail = audit_failure.get("detail") or audit_failure.get(
            "error_category"
        )
    else:
        audit_detail = audit_failure
    compact = _drop_empty_mapping(
        {
            "passed": value.get("passed"),
            "actionable_telemetry_feedback": _compact_actionable_telemetry_feedback(
                value.get("actionable_telemetry_feedback")
            ),
            "case": value.get("case"),
            "case_count": value.get("case_count"),
            "issues": _bounded_string_list(value.get("issues"), limit=2),
            "repair_guidance": _bounded_string_list(
                value.get("repair_guidance"),
                limit=4,
            ),
            "runtime_audit_failure": _limit_string(audit_detail, 180),
            "micro_benchmark": _compact_micro_benchmark_section(
                value.get("micro_benchmark")
            ),
        }
    )
    return compact or None

def _compact_algorithm_smoke_section(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    compact = _drop_empty_mapping(
        {
            "passed": value.get("passed"),
            "actionable_telemetry_feedback": _compact_actionable_telemetry_feedback(
                value.get("actionable_telemetry_feedback")
            ),
            "runtime_smoke_run": value.get("runtime_smoke_run"),
            "workspace_materialized": value.get("workspace_materialized"),
            "case": value.get("case"),
            "seed": value.get("seed"),
            "case_count": value.get("case_count"),
            "issues": _bounded_string_list(value.get("issues"), limit=4),
            "repair_guidance": _bounded_string_list(
                value.get("repair_guidance"),
                limit=6,
            ),
            "runtime_audit_failure": _compact_runtime_audit_failure_section(
                value.get("runtime_audit_failure")
            ),
            "micro_benchmark": _compact_micro_benchmark_section(
                value.get("micro_benchmark")
            ),
            "runtime": _compact_runtime_section(value.get("runtime")),
            "run": _compact_smoke_run_section(value.get("run")),
            "runs": _compact_smoke_runs(value.get("runs")),
        }
    )
    return compact or None

def _compact_actionable_telemetry_feedback(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, (list, tuple)):
        return []
    actions: list[dict[str, Any]] = []
    for item in value[:4]:
        if not isinstance(item, Mapping):
            continue
        actions.append(
            _drop_empty_mapping(
                {
                    "failure_code": item.get("failure_code"),
                    "failure_mechanism_id": (
                        item.get("failure_mechanism_id")
                        or item.get("mechanism_id")
                    ),
                    "mechanism_id": item.get("mechanism_id"),
                    "category": item.get("category"),
                    "delta_valued_fields": _bounded_string_list(
                        item.get("delta_valued_fields"),
                        limit=4,
                    ),
                    "expected_call_pattern": _limit_string(
                        item.get("expected_call_pattern"),
                        300,
                    ),
                    "invalid_call_summaries": _compact_invalid_call_summaries(
                        item.get("invalid_call_summaries")
                    ),
                    "declaration_alternative": _limit_string(
                        item.get("declaration_alternative"),
                        420,
                    ),
                }
            )
        )
    return [action for action in actions if action]


def _compact_invalid_call_summaries(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, (list, tuple)):
        return []
    summaries: list[dict[str, Any]] = []
    for item in value[:4]:
        if not isinstance(item, Mapping):
            continue
        summaries.append(
            _drop_empty_mapping(
                {
                    "file_path": item.get("file_path"),
                    "mechanism_id": item.get("mechanism_id"),
                    "helper": item.get("helper"),
                    "call": _limit_string(item.get("call"), 320),
                    "delta_status": item.get("delta_status"),
                    "delta_argument": _limit_string(
                        item.get("delta_argument"),
                        120,
                    ),
                    "accepted_argument": _limit_string(
                        item.get("accepted_argument"),
                        120,
                    ),
                    "best_improved_argument": _limit_string(
                        item.get("best_improved_argument"),
                        120,
                    ),
                    "reason": _limit_string(item.get("reason"), 300),
                }
            )
        )
    return [summary for summary in summaries if summary]


def _compact_runtime_audit_failure_section(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        text = _limit_string(value, 240)
        return {"detail": text} if text else None
    compact = {
        "error_category": _limit_string(value.get("error_category"), 80),
        "detail": _limit_string(value.get("detail"), 700),
        "failed_runtime_fields": _bounded_string_list(
            value.get("failed_runtime_fields"),
            limit=6,
        ),
        "solver_algorithm_errors": value.get("solver_algorithm_errors"),
    }
    events = value.get("solver_algorithm_events")
    if events not in (None, "", [], {}):
        compact["solver_algorithm_events"] = _limit_string(
            json.dumps(
                _json_ready(events),
                sort_keys=True,
                default=str,
            ),
            500,
        )
    return _drop_empty_mapping(compact)

def _compact_micro_benchmark_section(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    results = value.get("results")
    compact_results: list[dict[str, Any]] = []
    if isinstance(results, list):
        for item in results[:3]:
            if not isinstance(item, Mapping):
                continue
            compact_results.append(
                _drop_empty_mapping(
                    {
                        "label": item.get("label"),
                        "case": item.get("case"),
                        "comparison": item.get("comparison"),
                        "delta": item.get("delta"),
                        "decisive_metric": item.get("decisive_metric"),
                        "runtime_delta_ms": item.get("runtime_delta_ms"),
                    }
                )
            )
    return _drop_empty_mapping(
        {
            "non_promotional": value.get("non_promotional"),
            "tainted_debug": value.get("tainted_debug"),
            "comparable_cases": value.get("comparable_cases"),
            "wins": value.get("wins"),
            "losses": value.get("losses"),
            "ties": value.get("ties"),
            "results": compact_results,
        }
    )

def _compact_runtime_section(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    preferred_keys = (
        "solver_algorithm_loaded",
        "solver_algorithm_active",
        "solver_algorithm_errors",
        "solver_algorithm_elapsed_ms",
        "solver_algorithm_solution_valid",
        "solver_algorithm_search_iterations",
        "solver_algorithm_accepted_moves",
        "solver_algorithm_best_delta",
        "solver_algorithm_stop_reason",
    )
    extra_keys = sorted(
        key
        for key in value
        if str(key).startswith("solver_algorithm_")
        and key != "solver_algorithm_events"
        and key not in set(preferred_keys)
    )
    keys = (*preferred_keys, *extra_keys)
    compact = {key: value.get(key) for key in keys if key in value}
    events = value.get("solver_algorithm_events")
    if events not in (None, "", [], {}):
        compact["solver_algorithm_events"] = _limit_string(
            json.dumps(_json_ready(events), sort_keys=True, default=str),
            500,
        )
    return _drop_empty_mapping(compact)

def _compact_smoke_run_section(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    return _drop_empty_mapping(
        {
            "case": value.get("case"),
            "seed": value.get("seed"),
            "label": value.get("label"),
            "success": value.get("success"),
            "exit_code": value.get("exit_code"),
            "elapsed_ms": value.get("elapsed_ms"),
            "error_category": _limit_string(value.get("error_category"), 120),
            "detail": _limit_string(value.get("detail"), 320),
            "stderr": _limit_string(value.get("stderr"), 500),
            "stdout": _limit_string(value.get("stdout"), 240),
        }
    )

def _compact_smoke_runs(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, (list, tuple)):
        return []
    compact: list[dict[str, Any]] = []
    for item in value[:3]:
        if not isinstance(item, Mapping):
            continue
        run = _drop_empty_mapping(
            {
                "case": item.get("case"),
                "seed": item.get("seed"),
                "label": item.get("label"),
                "passed": item.get("passed"),
                "runtime_audit_failure": _compact_runtime_audit_failure_section(
                    item.get("runtime_audit_failure")
                ),
                "repair_guidance": _bounded_string_list(
                    item.get("repair_guidance"),
                    limit=4,
                ),
                "runtime": _compact_runtime_section(item.get("runtime")),
            }
        )
        if run:
            compact.append(run)
    return compact

def _compact_problem_preview_mapping(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    compact = _drop_empty_mapping(
        {
            "passed": value.get("passed"),
            "surface": value.get("surface"),
            "issues": _bounded_string_list(value.get("issues"), limit=8),
            "failed_checks": _failed_preview_checks(value.get("checks")),
        }
    )
    return compact or None

def _compact_contract_mapping(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    compact = _drop_empty_mapping(
        {
            "passed": value.get("passed"),
            "check_count": value.get("check_count"),
            "failed_checks": _bounded_string_list(
                value.get("failed_checks"),
                limit=8,
            ),
            "failure_reason": _limit_string(value.get("failure_reason"), 240),
        }
    )
    return compact or None

def _failed_preview_checks(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    failed: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping) or item.get("passed") is not False:
            continue
        failed.append(
            _drop_empty_mapping(
                {
                    "name": item.get("name"),
                    "passed": False,
                    "severity": item.get("severity"),
                    "detail": _limit_string(item.get("detail"), 700),
                }
            )
        )
        if len(failed) >= 8:
            break
    return failed

def _existing_failed_preview_checks(value: Any, *, limit: int) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    failed: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping):
            continue
        failed.append(
            _drop_empty_mapping(
                {
                    "name": item.get("name"),
                    "passed": False if item.get("passed") is False else None,
                    "severity": item.get("severity"),
                    "detail": _limit_string(item.get("detail"), 360),
                }
            )
        )
        if len(failed) >= limit:
            break
    return failed
