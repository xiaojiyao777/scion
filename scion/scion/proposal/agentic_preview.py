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
from scion.proposal.agentic_preview_compaction import (
    _compact_algorithm_smoke_section,
    _compact_contract_mapping,
    _compact_contract_preview_section,
    _compact_problem_preview_mapping,
    _minimal_algorithm_smoke_section,
    _minimal_contract_preview_section,
)
from scion.proposal.tools import (
    ProposalObservation,
    ProposalToolContext,
    ProposalToolFailureCode,
    ProposalToolPermission,
)

_HYPOTHESIS_CONTRACT_SELF_CHECKS = frozenset(
    {
        "C1_schema",
        "C11_expected_telemetry",
        "C12_mechanism_binding",
    }
)
_AGENTIC_BUDGET_CONTROL_SKIP_REASONS = frozenset(
    {
        "tool_loop_limit",
        "observation_budget_exhausted",
        "session_timeout",
    }
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
    schema_preview_evaluated = False
    schema_preview_codes_by_source: dict[str, tuple[str, ...]] = {}
    schema_passed_by_source: dict[str, bool] = {}
    contract_preview_passed: bool | None = None
    contract_preview_codes: tuple[str, ...] = ()
    for observation in observations:
        if observation.is_error:
            if observation.tool_name in {
                "proposal.schema_preview",
                "proposal.target_permission_preview",
            }:
                schema_preview_evaluated = True
                schema_passed_by_source[observation.tool_name] = False
                schema_preview_codes_by_source[observation.tool_name] = tuple(
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
            schema_passed_by_source[observation.tool_name] = preview_passed
            if not preview_passed:
                schema_preview_codes_by_source[observation.tool_name] = (
                    _preview_codes(payload)
                )
            else:
                schema_preview_codes_by_source.pop(observation.tool_name, None)
        if observation.tool_name == "proposal.contract_preview":
            contract_preview_passed = bool(payload.get("passed"))
            contract_preview_codes = _preview_codes(payload)
            hypothesis_codes = _hypothesis_contract_self_check_codes(payload)
            if hypothesis_codes:
                schema_preview_evaluated = True
                schema_passed_by_source["proposal.contract_preview.hypothesis"] = False
                schema_preview_codes_by_source[
                    "proposal.contract_preview.hypothesis"
                ] = hypothesis_codes
            elif contract_preview_passed:
                schema_passed_by_source["proposal.contract_preview.hypothesis"] = True
                schema_preview_codes_by_source.pop(
                    "proposal.contract_preview.hypothesis",
                    None,
                )
    schema_valid = (
        all(schema_passed_by_source.values()) if schema_preview_evaluated else False
    )
    schema_preview_codes: list[str] = []
    for codes in schema_preview_codes_by_source.values():
        schema_preview_codes.extend(codes)
    return AgenticSelfCheck(
        schema_valid=schema_valid,
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
        if _preview_skip_is_agentic_budget_control(latest):
            return _preview_budget_control_detail("algorithm smoke", latest)
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
    runtime_detail = _algorithm_smoke_agent_failure_text(latest.structured_payload)
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
        if _preview_skip_is_agentic_budget_control(observation):
            return _preview_budget_control_detail("contract preview", observation)
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


def _preview_skip_is_agentic_budget_control(
    observation: ProposalObservation,
) -> bool:
    if observation.tool_name not in {
        "proposal.contract_preview",
        "proposal.algorithm_smoke",
    }:
        return False
    if not observation.is_error:
        return False
    payload = observation.structured_payload
    if isinstance(payload, Mapping) and bool(payload.get("agentic_budget_control")):
        return True
    if observation.observation_type != "tool_skipped":
        return False
    skip_reason = ""
    if isinstance(payload, Mapping):
        skip_reason = str(payload.get("skip_reason") or "")
    failure_code = str(_enum_value(observation.failure_code) or "")
    return (
        skip_reason in _AGENTIC_BUDGET_CONTROL_SKIP_REASONS
        or failure_code in _AGENTIC_BUDGET_CONTROL_SKIP_REASONS
        or failure_code.startswith("tool_loop_limit_before_")
    )


def _preview_budget_control_detail(
    label: str,
    observation: ProposalObservation,
) -> str:
    payload = observation.structured_payload
    skip_reason = ""
    if isinstance(payload, Mapping):
        skip_reason = str(payload.get("skip_reason") or "").strip()
    failure_code = str(_enum_value(observation.failure_code) or "").strip()
    reason = skip_reason or failure_code
    if reason == "session_timeout":
        return f"{label} skipped by agentic session_timeout/budget control"
    return f"{label} skipped by agentic budget control"


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


def _algorithm_smoke_agent_failure_text(value: Any) -> str | None:
    if not isinstance(value, Mapping):
        return None
    candidates: list[Any] = []
    agent_summary = value.get("agent_summary")
    if isinstance(agent_summary, Mapping):
        candidates.extend(
            [
                agent_summary.get("primary_issue"),
                value.get("primary_issue"),
            ]
        )
    else:
        candidates.append(value.get("primary_issue"))
    telemetry = value.get("telemetry_guard")
    if isinstance(telemetry, Mapping):
        candidates.append(_algorithm_smoke_telemetry_failure_text(telemetry))
    subprocess = value.get("subprocess")
    if isinstance(subprocess, Mapping):
        candidates.extend(
            [
                subprocess.get("detail"),
                subprocess.get("stderr_tail"),
                subprocess.get("stdout_tail"),
            ]
        )
    candidates.append(
        _algorithm_smoke_runtime_failure_text(value.get("runtime_smoke"))
    )
    primary: str | None = None
    for candidate in candidates:
        text = _limit_string(candidate, 500)
        if text:
            primary = text
            break
    guidance_items: list[str] = []
    if isinstance(agent_summary, Mapping):
        guidance_items.extend(
            _bounded_string_list(agent_summary.get("repair_hints"), limit=4)
        )
    guidance_items.extend(_bounded_string_list(value.get("repair_hints"), limit=4))
    guidance = "; ".join(dict.fromkeys(guidance_items))
    if primary and guidance:
        return _limit_string(f"{primary}; repair guidance: {guidance}", 1200)
    if primary:
        return primary
    if guidance:
        return _limit_string(f"repair guidance: {guidance}", 1200)
    return None


def _algorithm_smoke_telemetry_failure_text(value: Mapping[str, Any]) -> str | None:
    failure = _first_mapping(value.get("failures"))
    code = _limit_string(value.get("failure_code"), 120)
    mechanism = _limit_string(value.get("mechanism"), 120)
    category = _limit_string(value.get("category"), 120)
    field = _limit_string(value.get("field"), 240)
    counters = value.get("counters")
    if failure is not None:
        code = code or _limit_string(failure.get("code"), 120)
        mechanism = mechanism or _limit_string(failure.get("mechanism"), 120)
        category = category or _limit_string(failure.get("category"), 120)
        field = field or _limit_string(failure.get("field"), 240)
        counters = counters or failure.get("counters")
    parts = [f"code={code}" if code else ""]
    if mechanism:
        parts.append(f"mechanism={mechanism}")
    if category:
        parts.append(f"category={category}")
    if field:
        parts.append(f"field={field}")
    if isinstance(counters, Mapping):
        parts.extend(
            f"{key}={counters[key]}"
            for key in sorted(counters)
            if counters[key] not in (None, "")
        )
    text = "; ".join(part for part in parts if part)
    return f"telemetry guard failed: {text}" if text else None


def _first_mapping(value: Any) -> Mapping[str, Any] | None:
    if isinstance(value, (list, tuple)):
        for item in value:
            if isinstance(item, Mapping):
                return item
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


def _hypothesis_contract_self_check_codes(payload: Mapping[str, Any]) -> tuple[str, ...]:
    hypothesis = payload.get("hypothesis")
    if not isinstance(hypothesis, Mapping):
        return ()
    codes: list[str] = []

    def add(value: Any) -> None:
        text = _limit_string(value, 240)
        if text:
            codes.append(text)

    failure_reason = hypothesis.get("failure_reason")
    if failure_reason and _is_hypothesis_self_check_failure(failure_reason):
        add(failure_reason)

    contract = hypothesis.get("contract")
    if isinstance(contract, Mapping):
        for check_name in contract.get("failed_checks") or ():
            if str(check_name) in _HYPOTHESIS_CONTRACT_SELF_CHECKS:
                add(check_name)

    checks = hypothesis.get("checks")
    if isinstance(checks, list):
        for check in checks:
            if not isinstance(check, Mapping):
                continue
            name = str(check.get("name") or "")
            if name not in _HYPOTHESIS_CONTRACT_SELF_CHECKS:
                continue
            if bool(check.get("passed")):
                continue
            detail = check.get("detail")
            add(f"{name}: {detail}" if detail else name)
    return tuple(dict.fromkeys(codes))


def _is_hypothesis_self_check_failure(value: Any) -> bool:
    text = str(value or "")
    return any(name in text for name in _HYPOTHESIS_CONTRACT_SELF_CHECKS)


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
