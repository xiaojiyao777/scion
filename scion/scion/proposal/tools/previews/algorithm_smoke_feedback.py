"""Agent-facing algorithm-smoke payload assembly.

Algorithm smoke is tainted, non-promotional debug evidence. This module only
builds the bounded observation the proposal agent may see; runtime extraction,
static section summaries, and failure classification live in focused siblings.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping

from scion.proposal.tools.models import ProposalObservation
from scion.proposal.tools.previews.algorithm_smoke_activation_diagnostic import (
    _proposal_smoke_activation_diagnostic,
    _proposal_smoke_telemetry_diagnostics,
)
from scion.proposal.tools.previews.algorithm_smoke_feedback_diagnostics import (
    _algorithm_smoke_case_count,
    _algorithm_smoke_failed_checks,
    _algorithm_smoke_failure_class,
    _algorithm_smoke_primary_issue,
    _algorithm_smoke_repair_hints,
    _algorithm_smoke_selected_surface,
)
from scion.proposal.tools.previews.algorithm_smoke_feedback_runtime import (
    _algorithm_smoke_runtime_agent_section,
    _compact_algorithm_smoke_runtime_comparison,
    _compact_algorithm_smoke_runtime_counters,
    _compact_algorithm_smoke_subprocess,
    _compact_algorithm_smoke_telemetry_guard,
)
from scion.proposal.tools.previews.algorithm_smoke_feedback_static import (
    _algorithm_smoke_problem_preview,
    _algorithm_smoke_preview_section,
    _algorithm_smoke_static_preview,
    _algorithm_smoke_telemetry_static_preview,
)
from scion.proposal.tools.previews.algorithm_smoke_feedback_text import (
    _ALGORITHM_SMOKE_AGENT_SCHEMA,
    _ALGORITHM_SMOKE_AGENT_TEXT_CHARS,
    _algorithm_smoke_digest,
    _mapping_or_none,
)
from scion.proposal.tools.previews.telemetry_static import (
    _telemetry_static_diagnostic_passed,
    _telemetry_static_hard_failed,
)
from scion.proposal.tools.surface import _drop_empty_items
from scion.proposal.tools.utils import _json_size, _limit_text

_PROPOSAL_DIAGNOSTIC_TELEMETRY_CODES = frozenset(
    {
        "TELEMETRY_ACTIVITY_NOT_OBSERVED",
        "TELEMETRY_ACTIVATION_NOT_OBSERVED",
        "TELEMETRY_EFFECT_NOT_OBSERVED",
        "TELEMETRY_RUNTIME_NOT_OBSERVED",
        "TELEMETRY_MECHANISM_ACTIVITY_NOT_OBSERVED",
        "TELEMETRY_MECHANISM_ACTIVATION_NOT_OBSERVED",
        "TELEMETRY_MECHANISM_EFFECT_NOT_OBSERVED",
        "TELEMETRY_MECHANISM_RUNTIME_NOT_OBSERVED",
    }
)
_PROPOSAL_DIAGNOSTIC_TELEMETRY_CATEGORIES = frozenset(
    {"activity", "activation", "effect", "runtime"}
)


def compact_algorithm_smoke_observation_for_agent(
    observation: ProposalObservation,
) -> ProposalObservation | None:
    """Return a registry-safe agent-facing smoke observation when possible."""
    if observation.tool_name != "proposal.algorithm_smoke" or observation.is_error:
        return None
    if not isinstance(observation.structured_payload, Mapping):
        return None
    payload = _algorithm_smoke_agent_payload(observation.structured_payload)
    summary = (
        "Algorithm smoke emitted diagnostic guidance on compact tainted preview."
        if payload.get("status") == "diagnostic"
        else (
            "Algorithm smoke passed on compact tainted preview."
            if payload.get("passed")
            else "Algorithm smoke found issues in compact tainted preview."
        )
    )
    return replace(
        observation,
        summary=summary,
        structured_payload=payload,
        repair_hint=None,
    )


def _algorithm_smoke_agent_payload(raw_payload: Mapping[str, Any]) -> dict[str, Any]:
    runtime_smoke = _mapping_or_none(raw_payload.get("runtime_smoke"))
    evidence_diagnostics = _algorithm_smoke_evidence_diagnostics(runtime_smoke)
    if runtime_smoke is not None and evidence_diagnostics:
        runtime_smoke = {
            **runtime_smoke,
            "evidence_diagnostics": evidence_diagnostics,
        }
    runtime = runtime_smoke.get("runtime") if runtime_smoke else None
    run = runtime_smoke.get("run") if runtime_smoke else None
    telemetry_guard = _compact_algorithm_smoke_telemetry_guard(
        runtime_smoke.get("telemetry_guard") if runtime_smoke else None
    )
    activation_diagnostic = _proposal_smoke_activation_diagnostic(
        raw_payload,
        runtime_smoke=runtime_smoke,
        telemetry_guard=telemetry_guard,
    )
    telemetry_diagnostics = _proposal_smoke_telemetry_diagnostics(
        raw_payload,
        runtime_smoke=runtime_smoke,
        telemetry_guard=telemetry_guard,
        activation_diagnostic=activation_diagnostic,
    )
    runtime_counters = _compact_algorithm_smoke_runtime_counters(runtime)
    subprocess_tail = _compact_algorithm_smoke_subprocess(run)
    runtime_comparison = _compact_algorithm_smoke_runtime_comparison(runtime_smoke)
    primary_issue = _algorithm_smoke_primary_issue(
        raw_payload,
        runtime_smoke=runtime_smoke,
        telemetry_guard=telemetry_guard,
        subprocess_tail=subprocess_tail,
    )
    passed = bool(raw_payload.get("passed"))
    status = "passed" if passed else "failed"
    failure_class = _algorithm_smoke_failure_class(
        passed=passed,
        raw_payload=raw_payload,
        runtime_smoke=runtime_smoke,
        telemetry_guard=telemetry_guard,
        primary_issue=primary_issue,
        subprocess_tail=subprocess_tail,
    )
    hard_smoke_failure = _hard_smoke_failure_present(
        raw_payload,
        runtime_smoke=runtime_smoke,
        subprocess_tail=subprocess_tail,
    )
    if hard_smoke_failure and passed:
        passed = False
        status = "failed"
        failure_class = _algorithm_smoke_failure_class(
            passed=False,
            raw_payload=raw_payload,
            runtime_smoke=runtime_smoke,
            telemetry_guard=telemetry_guard,
            primary_issue=primary_issue,
            subprocess_tail=subprocess_tail,
        )
    if activation_diagnostic is not None and not hard_smoke_failure:
        failure_class = str(
            activation_diagnostic.get("code") or "proposal_activation_diagnostic"
        )
    non_blocking_activation_diagnostic = _non_blocking_activation_diagnostic(
        activation_diagnostic
    )
    non_blocking_telemetry_diagnostic = _non_blocking_runtime_telemetry_diagnostic(
        telemetry_guard
    )
    telemetry_static = _mapping_or_none(raw_payload.get("telemetry_static_preview"))
    non_blocking_static_diagnostic = _telemetry_static_diagnostic_passed(
        telemetry_static
    )
    activation_diagnostic_passed = (
        non_blocking_activation_diagnostic and not hard_smoke_failure
    )
    telemetry_diagnostic_passed = (
        non_blocking_telemetry_diagnostic and not hard_smoke_failure
    )
    static_diagnostic_passed = (
        non_blocking_static_diagnostic and not hard_smoke_failure
    )
    evidence_diagnostic_passed = (
        _provider_unavailable_evidence_diagnostic(evidence_diagnostics)
        and not hard_smoke_failure
    )
    if activation_diagnostic_passed:
        passed = True
        status = "diagnostic"
        failure_class = "activation_not_observed_diagnostic"
    elif telemetry_diagnostic_passed:
        passed = True
        status = "diagnostic"
        failure_class = "telemetry_not_observed_diagnostic"
    elif static_diagnostic_passed:
        passed = True
        status = "diagnostic"
        failure_class = "telemetry_static_diagnostic"
    elif evidence_diagnostic_passed:
        passed = True
        status = "diagnostic"
        failure_class = "provider_smoke_coverage_diagnostic"
    failure_code = _algorithm_smoke_failure_code(
        failure_class=failure_class,
        runtime_smoke=runtime_smoke,
        subprocess_tail=subprocess_tail,
    )
    repair_hints = _algorithm_smoke_repair_hints(
        raw_payload,
        runtime_smoke=runtime_smoke,
        telemetry_guard=telemetry_guard,
    )
    if activation_diagnostic is not None:
        repair_hints = list(
            dict.fromkeys(
                [
                    *repair_hints,
                    *[
                        str(item)
                        for item in activation_diagnostic.get("repair_guidance", [])
                        if str(item).strip()
                    ],
                ]
            )
        )[:8]
    failed_checks = _algorithm_smoke_failed_checks(
        raw_payload,
        runtime_smoke=runtime_smoke,
        primary_issue=primary_issue,
        failure_class=failure_class,
    )
    actionable_telemetry_feedback = _actionable_telemetry_feedback(
        raw_payload,
        telemetry_guard=telemetry_guard,
    )
    selected_surface = _algorithm_smoke_selected_surface(raw_payload, runtime_smoke)
    case_count = _algorithm_smoke_case_count(runtime_smoke)
    non_promotional = raw_payload.get("non_promotional", True)
    tainted_debug = raw_payload.get("tainted_debug", True)
    agent_summary = _agent_summary(
        passed=passed,
        status=status,
        failure_code=failure_code,
        failure_class=failure_class,
        primary_issue=primary_issue,
        selected_surface=selected_surface,
        case_count=case_count,
        non_promotional=non_promotional,
        tainted_debug=tainted_debug,
        repair_hints=repair_hints,
        failed_checks=failed_checks,
    )
    compact_payload = _drop_empty_items(
        {
            "schema": _ALGORITHM_SMOKE_AGENT_SCHEMA,
            "actionable_telemetry_feedback": actionable_telemetry_feedback,
            "passed": passed,
            "status": status,
            "failure_code": failure_code,
            "failure_class": failure_class,
            "diagnostic_passed": (
                activation_diagnostic_passed
                or telemetry_diagnostic_passed
                or static_diagnostic_passed
                or evidence_diagnostic_passed
                or None
            ),
            "primary_issue": primary_issue,
            "selected_surface": selected_surface,
            "case_count": case_count,
            "non_promotional": non_promotional,
            "tainted_debug": tainted_debug,
            "workspace_materialized": raw_payload.get("workspace_materialized"),
            "verification_run": raw_payload.get("verification_run"),
            "protocol_run": raw_payload.get("protocol_run"),
            "decision_run": raw_payload.get("decision_run"),
            "agent_summary": agent_summary,
            "repair_hints": repair_hints,
            "failed_checks": failed_checks,
            "evidence_diagnostics": evidence_diagnostics,
            "activation_diagnostic": activation_diagnostic,
            "telemetry_diagnostics": telemetry_diagnostics,
            "smoke_telemetry_diagnostic_kind": _primary_telemetry_diagnostic_kind(
                telemetry_diagnostics
            ),
            "telemetry_guard": telemetry_guard,
            "runtime_comparison": runtime_comparison,
            "subprocess": subprocess_tail,
            "static_preview": _algorithm_smoke_static_preview(raw_payload),
            "telemetry_static_preview": _algorithm_smoke_telemetry_static_preview(
                raw_payload.get("telemetry_static_preview")
            ),
            "hypothesis": _algorithm_smoke_preview_section(
                raw_payload.get("hypothesis")
            ),
            "patch": _algorithm_smoke_preview_section(raw_payload.get("patch")),
            "problem_preview": _algorithm_smoke_problem_preview(
                raw_payload.get("problem_preview")
            ),
            "runtime_smoke": _algorithm_smoke_runtime_agent_section(
                runtime_smoke,
                telemetry_guard=telemetry_guard,
                runtime_counters=runtime_counters,
                subprocess_tail=subprocess_tail,
                runtime_comparison=runtime_comparison,
                repair_hints=repair_hints,
            ),
            "issue_summary": _limit_text(
                str(raw_payload.get("issue_summary") or ""),
                _ALGORITHM_SMOKE_AGENT_TEXT_CHARS,
            ),
            "audit": _agent_audit(raw_payload),
        }
    )
    compact_payload["audit"]["agent_payload_digest"] = _algorithm_smoke_digest(
        {
            key: value
            for key, value in compact_payload.items()
            if key != "audit"
        }
    )
    compact_payload["audit"]["summary_ref"] = (
        "algorithm-smoke-summary:"
        f"{_algorithm_smoke_digest(compact_payload.get('agent_summary'))}"
    )
    return compact_payload


def _algorithm_smoke_evidence_diagnostics(
    runtime_smoke: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    if runtime_smoke is None:
        return []
    diagnostics: list[dict[str, Any]] = []
    for item in runtime_smoke.get("evidence_diagnostics", []) or []:
        if isinstance(item, Mapping):
            diagnostics.append(dict(item))
    provider_unavailable = bool(runtime_smoke.get("provider_unavailable"))
    if provider_unavailable and not any(
        item.get("code") == "solver_design_smoke_provider_unavailable"
        for item in diagnostics
    ):
        diagnostics.append(
            {
                "code": "solver_design_smoke_provider_unavailable",
                "severity": "warning",
                "detail": (
                    "No problem-owned solver-design smoke provider is registered, "
                    "so algorithm smoke cannot run provider representative cases."
                ),
                "provider_case_count": 0,
                "provider_case_attempted_count": 0,
                "case_count": runtime_smoke.get("case_count"),
            }
        )
    missing_fields = [
        field
        for field in (
            "provider_case_count",
            "provider_case_attempted_count",
            "case_execution_ledger",
        )
        if field not in runtime_smoke
        and not (field == "case_execution_ledger" and "cases" in runtime_smoke)
    ]
    if missing_fields and not provider_unavailable:
        diagnostics.append(
            {
                "code": "algorithm_smoke_provider_ledger_fields_missing",
                "severity": "warning",
                "detail": (
                    "Runtime smoke payload omitted provider case ledger/count "
                    "fields; persisted evidence may otherwise be canary-only."
                ),
                "missing_fields": missing_fields,
            }
        )
    provider_count = _int_or_none(runtime_smoke.get("provider_case_count"))
    provider_attempted = _int_or_none(
        runtime_smoke.get("provider_case_attempted_count")
    )
    selected_surface = str(runtime_smoke.get("selected_surface") or "").strip()
    if (
        runtime_smoke.get("runtime_smoke_run")
        and selected_surface == "solver_design"
        and (provider_count is None or provider_count <= 0)
        and not provider_unavailable
    ):
        diagnostics.append(
            {
                "code": "provider_representative_smoke_evidence_missing",
                "severity": "warning",
                "detail": (
                    "Algorithm smoke did not report provider representative "
                    "case execution; compact evidence may only show the canary."
                ),
                "provider_case_count": provider_count,
                "provider_case_attempted_count": provider_attempted,
                "case_count": runtime_smoke.get("case_count"),
            }
        )
    if (
        provider_count is not None
        and provider_attempted is not None
        and provider_count > 0
        and provider_attempted < provider_count
    ):
        diagnostics.append(
            {
                "code": "provider_representative_smoke_cases_not_fully_attempted",
                "severity": "warning",
                "detail": (
                    "Provider representative smoke cases were selected but not "
                    "all were attempted."
                ),
                "provider_case_count": provider_count,
                "provider_case_attempted_count": provider_attempted,
            }
        )
    return _dedupe_evidence_diagnostics(diagnostics)


def _dedupe_evidence_diagnostics(
    diagnostics: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in diagnostics:
        code = str(item.get("code") or item.get("detail") or item)
        if code in seen:
            continue
        seen.add(code)
        deduped.append(item)
    return deduped[:8]


def _provider_unavailable_evidence_diagnostic(
    diagnostics: list[dict[str, Any]],
) -> bool:
    return any(
        item.get("code") == "solver_design_smoke_provider_unavailable"
        for item in diagnostics
    )


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _primary_telemetry_diagnostic_kind(
    diagnostics: list[dict[str, Any]],
) -> str | None:
    for diagnostic in diagnostics:
        kind = str(diagnostic.get("diagnostic_type") or "").strip()
        if kind:
            return kind
    return None


def _algorithm_smoke_failure_code(
    *,
    failure_class: str,
    runtime_smoke: Mapping[str, Any] | None,
    subprocess_tail: Mapping[str, Any] | None,
) -> str:
    if failure_class == "passed":
        return ""
    if runtime_smoke is not None and runtime_smoke.get(
        "runtime_audit_failure"
    ) not in (None, "", {}, []):
        return "algorithm_smoke_runtime_failure"
    run = _mapping_or_none(runtime_smoke.get("run")) if runtime_smoke else None
    if run is not None and run.get("success") is False:
        return "algorithm_smoke_runtime_failure"
    if subprocess_tail is not None and subprocess_tail.get("error_category"):
        return "algorithm_smoke_runtime_failure"
    if failure_class in {
        "activation_not_observed_diagnostic",
        "telemetry_not_observed_diagnostic",
        "telemetry_static_diagnostic",
        "provider_smoke_coverage_diagnostic",
    }:
        return failure_class
    return failure_class or "algorithm_smoke_failure"


def _hard_smoke_failure_present(
    raw_payload: Mapping[str, Any],
    *,
    runtime_smoke: Mapping[str, Any] | None,
    subprocess_tail: Mapping[str, Any] | None,
) -> bool:
    telemetry_static = _mapping_or_none(raw_payload.get("telemetry_static_preview"))
    if _telemetry_static_hard_failed(telemetry_static):
        return True
    if runtime_smoke is not None:
        if runtime_smoke.get("runtime_audit_failure") not in (None, "", {}, []):
            return True
        run = _mapping_or_none(runtime_smoke.get("run"))
        if run is not None and run.get("success") is False:
            return True
    if subprocess_tail is not None and subprocess_tail.get("error_category"):
        return True
    return False


def _non_blocking_activation_diagnostic(
    activation_diagnostic: Mapping[str, Any] | None,
) -> bool:
    if activation_diagnostic is None:
        return False
    failure_code = str(
        activation_diagnostic.get("failure_code")
        or activation_diagnostic.get("telemetry_failure_code")
        or ""
    ).strip()
    if failure_code == "DECLARED_MECHANISM_ACTIVATION_MISSING":
        return True
    if str(activation_diagnostic.get("source") or "") != "runtime_smoke.telemetry_guard":
        return False
    if failure_code in {
        "TELEMETRY_ACTIVATION_NOT_OBSERVED",
        "TELEMETRY_MECHANISM_ACTIVATION_NOT_OBSERVED",
    }:
        return True
    kind = str(activation_diagnostic.get("activation_diagnostic_kind") or "").strip()
    return kind in {
        "path_not_reached",
        "trigger_not_reached",
        "smoke_budget_or_case_insufficient",
    }


def _non_blocking_runtime_telemetry_diagnostic(
    telemetry_guard: Mapping[str, Any] | None,
) -> bool:
    """Return true when proposal-smoke telemetry misses are diagnostic only."""
    if telemetry_guard is None or telemetry_guard.get("passed") is not False:
        return False
    failures = telemetry_guard.get("failures")
    if not isinstance(failures, (list, tuple)) or not failures:
        return False
    for failure in failures:
        if not isinstance(failure, Mapping):
            return False
        code = str(failure.get("code") or "").strip()
        category = str(failure.get("category") or "").strip().lower()
        if code.startswith("TELEMETRY_PROTECTED_"):
            return False
        if (
            code not in _PROPOSAL_DIAGNOSTIC_TELEMETRY_CODES
            and category not in _PROPOSAL_DIAGNOSTIC_TELEMETRY_CATEGORIES
        ):
            return False
    return True


def _agent_summary(**values: Any) -> dict[str, Any]:
    return _drop_empty_items(dict(values))


def _agent_audit(raw_payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "agent_payload_schema": _ALGORITHM_SMOKE_AGENT_SCHEMA,
        "raw_payload_digest": _algorithm_smoke_digest(raw_payload),
        "raw_payload_chars": _json_size(raw_payload),
        "full_runtime_payload_omitted": True,
        "raw_payload_omitted_from_agent": True,
    }


def _actionable_telemetry_feedback(
    raw_payload: Mapping[str, Any],
    *,
    telemetry_guard: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    telemetry_static = _mapping_or_none(raw_payload.get("telemetry_static_preview"))
    if telemetry_static is not None:
        actions.extend(
            _mapping_items(telemetry_static.get("actionable_telemetry_feedback"))
        )
    actions.extend(
        _runtime_delta_effect_actions(
            telemetry_guard,
            existing_actions=actions,
        )
    )
    return actions[:6]


def _runtime_delta_effect_actions(
    telemetry_guard: Mapping[str, Any] | None,
    *,
    existing_actions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if telemetry_guard is None:
        return []
    existing_keys = {
        (
            str(item.get("failure_code") or ""),
            str(item.get("failure_mechanism_id") or item.get("mechanism_id") or ""),
        )
        for item in existing_actions
    }
    actions: list[dict[str, Any]] = []
    for issue in _mapping_items(telemetry_guard.get("failures")):
        category = str(issue.get("category") or "").strip().lower()
        field = str(issue.get("field") or "").strip()
        mechanism = str(issue.get("mechanism") or "").strip()
        code = str(issue.get("code") or "").strip()
        if category != "effect" or not _delta_effect_field(field):
            continue
        if (code, mechanism) in existing_keys:
            continue
        actions.append(
            _drop_empty_items(
                {
                    "failure_code": code or "TELEMETRY_MECHANISM_EFFECT_NOT_OBSERVED",
                    "failure_mechanism_id": mechanism,
                    "mechanism_id": mechanism,
                    "category": "effect",
                    "delta_valued_fields": [field] if field else [],
                    "expected_call_pattern": (
                        f"context.record_move('{mechanism}', attempted=1, "
                        "accepted=1, delta=<positive_improvement_delta>, "
                        "best_improved=True)"
                        if mechanism
                        else (
                            "context.record_move('<mechanism>', attempted=1, "
                            "accepted=1, delta=<positive_improvement_delta>, "
                            "best_improved=True)"
                        )
                    ),
                    "invalid_call_summaries": _invalid_calls_from_existing_actions(
                        existing_actions,
                        mechanism,
                    ),
                    "declaration_alternative": (
                        "If this mechanism is intended to prove only activity "
                        "or activation, repair the hypothesis expected_telemetry "
                        "or mechanism declaration to use activity/activation "
                        "fields instead of a delta-valued effect field. Do not "
                        "emit fake positive deltas for a non-effect mechanism."
                    ),
                }
            )
        )
    return actions


def _invalid_calls_from_existing_actions(
    actions: list[dict[str, Any]],
    mechanism: str,
) -> list[dict[str, Any]]:
    for item in actions:
        item_mechanism = str(
            item.get("failure_mechanism_id") or item.get("mechanism_id") or ""
        ).strip()
        if mechanism and item_mechanism != mechanism:
            continue
        invalid = item.get("invalid_call_summaries")
        if isinstance(invalid, list):
            return [entry for entry in invalid if isinstance(entry, Mapping)][:4]
    return []


def _mapping_items(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, (list, tuple)):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _delta_effect_field(field: str) -> bool:
    lowered = str(field or "").lower()
    return "best_delta" in lowered or "delta_sum" in lowered


__all__ = [
    "compact_algorithm_smoke_observation_for_agent",
    "_algorithm_smoke_agent_payload",
    "_non_blocking_runtime_telemetry_diagnostic",
]
