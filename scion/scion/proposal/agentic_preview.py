"""Preview and self-check result helpers for agentic proposal sessions."""
from __future__ import annotations

from dataclasses import dataclass, replace
import json
from typing import Any, Mapping

from scion.proposal.agentic_utils import (
    _bounded_string_list,
    _drop_empty_mapping,
    _enum_value,
    _json_ready,
    _limit_string,
)
from scion.proposal.tools import (
    ProposalObservation,
    ProposalToolContext,
    ProposalToolFailureCode,
    ProposalToolPermission,
)

@dataclass(frozen=True)
class AgenticSelfCheck:
    schema_valid: bool = False
    schema_preview_codes: tuple[str, ...] = ()
    contract_preview_passed: bool | None = None
    contract_preview_codes: tuple[str, ...] = ()

def _self_check_from_previews(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
) -> AgenticSelfCheck:
    schema_valid = True
    schema_preview_evaluated = False
    schema_preview_codes: list[str] = []
    contract_preview_passed: bool | None = None
    contract_preview_codes: tuple[str, ...] = ()
    for observation in observations:
        if observation.is_error:
            if observation.tool_name in {
                "proposal.schema_preview",
                "proposal.target_permission_preview",
            }:
                schema_valid = False
                schema_preview_evaluated = True
                schema_preview_codes.extend(
                    code
                    for code in (
                        _enum_value(observation.failure_code),
                        observation.observation_type,
                    )
                    if code
                )
            if observation.tool_name == "proposal.contract_preview":
                if _non_evaluative_preview_error(observation):
                    continue
                contract_preview_codes = tuple(
                    code
                    for code in (
                        _enum_value(observation.failure_code),
                        observation.observation_type,
                    )
                    if code
                )
                budget_error = (
                    observation.failure_code == ProposalToolFailureCode.RESULT_TOO_LARGE
                )
                contract_preview_passed = None if budget_error else False
            continue
        payload = observation.structured_payload
        if observation.tool_name in {
            "proposal.schema_preview",
            "proposal.target_permission_preview",
        }:
            schema_preview_evaluated = True
            preview_passed = bool(payload.get("passed"))
            schema_valid = schema_valid and preview_passed
            if not preview_passed:
                schema_preview_codes.extend(_preview_codes(payload))
        if observation.tool_name == "proposal.contract_preview":
            contract_preview_passed = bool(payload.get("passed"))
            contract_preview_codes = _preview_codes(payload)
    return AgenticSelfCheck(
        schema_valid=schema_valid if schema_preview_evaluated else False,
        schema_preview_codes=tuple(dict.fromkeys(schema_preview_codes)),
        contract_preview_passed=contract_preview_passed,
        contract_preview_codes=contract_preview_codes,
    )


def _self_check_failure_detail(
    self_check: AgenticSelfCheck,
    *,
    require_schema_preview: bool,
    require_contract_preview: bool,
) -> str | None:
    if require_schema_preview and not self_check.schema_valid:
        codes = ", ".join(self_check.schema_preview_codes)
        suffix = f" ({codes})" if codes else ""
        return f"schema or target preview did not pass{suffix}"
    if require_contract_preview and self_check.contract_preview_passed is not True:
        codes = ", ".join(self_check.contract_preview_codes)
        suffix = f" ({codes})" if codes else ""
        return f"contract preview did not pass{suffix}"
    return None


def _preview_observation_passed(observation: ProposalObservation) -> bool:
    return (
        not observation.is_error
        and bool(observation.structured_payload.get("passed"))
    )


def _algorithm_smoke_failure_detail(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
) -> str | None:
    smoke_observations = [
        observation
        for observation in observations
        if observation.tool_name == "proposal.algorithm_smoke"
    ]
    if not smoke_observations:
        return None
    latest = smoke_observations[-1]
    if latest.is_error:
        if latest.failure_code == ProposalToolFailureCode.RESULT_TOO_LARGE:
            return "algorithm smoke result exceeded observation budget"
        codes = ", ".join(
            code
            for code in (
                _enum_value(latest.failure_code),
                latest.observation_type,
            )
            if code
        )
        suffix = f" ({codes})" if codes else ""
        return f"algorithm smoke did not run{suffix}"
    if bool(latest.structured_payload.get("passed")):
        return None
    codes = ", ".join(_preview_codes(latest.structured_payload))
    suffix = f" ({codes})" if codes else ""
    runtime_detail = _algorithm_smoke_runtime_failure_text(
        latest.structured_payload.get("runtime_smoke")
    )
    detail_suffix = f": {runtime_detail}" if runtime_detail else ""
    return f"algorithm smoke did not pass{suffix}{detail_suffix}"


def _latest_preview_failure_detail(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
) -> str | None:
    for observation in reversed(list(observations)):
        if _non_evaluative_preview_error(observation):
            continue
        if observation.tool_name == "proposal.algorithm_smoke":
            return _algorithm_smoke_failure_detail([observation])
        if observation.tool_name == "proposal.contract_preview":
            return _contract_preview_failure_detail(observation)
    return None


def _non_evaluative_preview_error(observation: ProposalObservation) -> bool:
    """Return true for preview-like tool calls that never evaluated the patch."""
    if observation.tool_name not in {
        "proposal.contract_preview",
        "proposal.algorithm_smoke",
    }:
        return False
    if not observation.is_error:
        return False
    return observation.failure_code in {
        ProposalToolFailureCode.PERMISSION_DENIED,
        ProposalToolFailureCode.UNSUPPORTED,
    }


def _contract_preview_failure_detail(
    observation: ProposalObservation,
) -> str | None:
    if observation.is_error:
        if observation.failure_code == ProposalToolFailureCode.RESULT_TOO_LARGE:
            return "contract preview result exceeded observation budget"
        codes = ", ".join(
            code
            for code in (
                _enum_value(observation.failure_code),
                observation.observation_type,
            )
            if code
        )
        suffix = f" ({codes})" if codes else ""
        return f"contract preview did not run{suffix}"
    if bool(observation.structured_payload.get("passed")):
        return None
    codes = ", ".join(_preview_codes(observation.structured_payload))
    suffix = f" ({codes})" if codes else ""
    return f"contract preview did not pass{suffix}"


def _algorithm_smoke_runtime_failure_text(value: Any) -> str | None:
    if not isinstance(value, Mapping):
        return None
    candidates: list[Any] = []
    issues = value.get("issues")
    if isinstance(issues, (list, tuple)):
        candidates.extend(
            issue
            for issue in issues
            if "solver_algorithm_errors=" not in str(issue)
        )
    runtime = value.get("runtime")
    if isinstance(runtime, Mapping):
        candidates.extend(
            [
                runtime.get("solver_algorithm_events"),
            ]
        )
    audit = value.get("runtime_audit_failure")
    if isinstance(audit, Mapping):
        candidates.extend(
            [
                audit.get("solver_algorithm_events"),
                audit.get("detail"),
                audit.get("error_category"),
            ]
        )
    run = value.get("run")
    if isinstance(run, Mapping):
        candidates.extend([run.get("detail"), run.get("stderr")])
    if isinstance(issues, (list, tuple)):
        candidates.extend(issues)
    if isinstance(runtime, Mapping):
        candidates.append(
            f"solver_algorithm_errors={runtime.get('solver_algorithm_errors')}"
            if runtime.get("solver_algorithm_errors") not in (None, "")
            else None
        )
    primary: str | None = None
    for candidate in candidates:
        text = _limit_string(candidate, 360)
        if text:
            primary = text
            break
    guidance_items = _bounded_string_list(value.get("repair_guidance"), limit=4)
    guidance = "; ".join(guidance_items)
    if primary and guidance:
        return _limit_string(f"{primary}; repair guidance: {guidance}", 1200)
    if primary:
        return primary
    if guidance:
        return _limit_string(f"repair guidance: {guidance}", 1200)
    return None


def _self_check_required(context: ProposalToolContext | None) -> bool:
    return bool(
        context is not None
        and context.policy.allows_permission(ProposalToolPermission.CONTRACT_PREVIEW)
    )


def _preview_codes(payload: Mapping[str, Any]) -> tuple[str, ...]:
    codes: list[str] = []

    def add(value: Any) -> None:
        text = _limit_string(value, 160)
        if text:
            codes.append(text)

    def visit(value: Any) -> None:
        if isinstance(value, Mapping):
            if value.get("issue_summary"):
                add(value.get("issue_summary"))
            if value.get("failure_reason"):
                add(value.get("failure_reason"))
            for key in ("errors", "issues"):
                raw_values = value.get(key)
                if isinstance(raw_values, list):
                    for raw in raw_values:
                        if isinstance(raw, Mapping):
                            location = ".".join(
                                str(part) for part in raw.get("loc", ()) or ()
                            )
                            message = raw.get("msg") or raw.get("message") or raw
                            add(f"{location}: {message}" if location else message)
                        else:
                            add(raw)
                elif raw_values:
                    add(raw_values)
            name = value.get("name")
            if name and "passed" in value and not value.get("passed"):
                detail = value.get("detail")
                add(f"{name}: {detail}" if detail else name)
            for item in value.values():
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(payload)
    return tuple(dict.fromkeys(codes))


def _compact_contract_preview_observation(
    observation: ProposalObservation,
) -> ProposalObservation | None:
    if observation.tool_name != "proposal.contract_preview" or observation.is_error:
        return None
    payload = observation.structured_payload
    if not isinstance(payload, Mapping):
        return None
    compact_payload = _drop_empty_mapping(
        {
            "passed": bool(payload.get("passed")),
            "static_only": payload.get("static_only"),
            "workspace_materialized": payload.get("workspace_materialized"),
            "verification_run": payload.get("verification_run"),
            "protocol_run": payload.get("protocol_run"),
            "decision_run": payload.get("decision_run"),
            "issue_summary": _limit_string(payload.get("issue_summary"), 320),
            "hypothesis": _compact_contract_preview_section(payload.get("hypothesis")),
            "patch": _compact_contract_preview_section(payload.get("patch")),
            "compact_due_to_budget": True,
        }
    )
    return replace(
        observation,
        summary=f"{observation.summary} Compact budget preview retained.",
        structured_payload=compact_payload,
        repair_hint=None,
    )


def _compact_algorithm_smoke_observation(
    observation: ProposalObservation,
) -> ProposalObservation | None:
    if observation.tool_name != "proposal.algorithm_smoke" or observation.is_error:
        return None
    payload = observation.structured_payload
    if not isinstance(payload, Mapping):
        return None
    compact_payload = _drop_empty_mapping(
        {
            "passed": bool(payload.get("passed")),
            "non_promotional": payload.get("non_promotional"),
            "tainted_debug": payload.get("tainted_debug"),
            "workspace_materialized": payload.get("workspace_materialized"),
            "verification_run": payload.get("verification_run"),
            "protocol_run": payload.get("protocol_run"),
            "decision_run": payload.get("decision_run"),
            "issue_summary": _limit_string(payload.get("issue_summary"), 240),
            "static_contract": _compact_contract_mapping(
                payload.get("static_contract")
            ),
            "hypothesis": _compact_contract_preview_section(payload.get("hypothesis")),
            "patch": _compact_contract_preview_section(payload.get("patch")),
            "problem_preview": _compact_problem_preview_mapping(
                payload.get("problem_preview")
            ),
            "runtime_smoke": _compact_algorithm_smoke_section(
                payload.get("runtime_smoke")
            ),
            "compact_due_to_budget": True,
        }
    )
    return replace(
        observation,
        summary=f"{observation.summary} Compact smoke preview retained.",
        structured_payload=compact_payload,
        repair_hint=None,
    )


def _compact_self_check_preview_observation(
    observation: ProposalObservation,
) -> ProposalObservation | None:
    if observation.tool_name == "proposal.contract_preview":
        return _compact_contract_preview_observation(observation)
    if observation.tool_name == "proposal.algorithm_smoke":
        return _compact_algorithm_smoke_observation(observation)
    return None


def _minimal_self_check_preview_observation(
    observation: ProposalObservation,
) -> ProposalObservation | None:
    if observation.is_error:
        return None
    payload = observation.structured_payload
    if not isinstance(payload, Mapping):
        return None
    if observation.tool_name == "proposal.contract_preview":
        compact_payload = _drop_empty_mapping(
            {
                "passed": bool(payload.get("passed")),
                "issue_summary": _limit_string(payload.get("issue_summary"), 160),
                "hypothesis": _minimal_contract_preview_section(
                    payload.get("hypothesis")
                ),
                "patch": _minimal_contract_preview_section(payload.get("patch")),
                "minimal_due_to_budget": True,
            }
        )
        summary = (
            "Static contract preview passed."
            if compact_payload.get("passed")
            else "Static contract preview found issues."
        )
        return replace(
            observation,
            summary=f"{summary} Minimal budget preview retained.",
            structured_payload=compact_payload,
            repair_hint=None,
        )
    if observation.tool_name == "proposal.algorithm_smoke":
        compact_payload = _drop_empty_mapping(
            {
                "passed": bool(payload.get("passed")),
                "issue_summary": _limit_string(payload.get("issue_summary"), 160),
                "patch": _minimal_contract_preview_section(payload.get("patch")),
                "runtime_smoke": _minimal_algorithm_smoke_section(
                    payload.get("runtime_smoke")
                ),
                "minimal_due_to_budget": True,
            }
        )
        summary = (
            "Algorithm smoke passed."
            if compact_payload.get("passed")
            else "Algorithm smoke found issues."
        )
        return replace(
            observation,
            summary=f"{summary} Minimal budget preview retained.",
            structured_payload=compact_payload,
            repair_hint=None,
        )
    return None


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
        }
    )
    return compact or None


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
    keys = (
        "solver_algorithm_loaded",
        "solver_algorithm_active",
        "solver_algorithm_errors",
        "solver_algorithm_elapsed_ms",
        "solver_algorithm_solution_valid",
        "solver_algorithm_total_distance",
        "solver_algorithm_fleet_violation",
        "solver_algorithm_search_iterations",
        "solver_algorithm_accepted_moves",
        "solver_algorithm_best_delta",
        "solver_algorithm_stop_reason",
    )
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
