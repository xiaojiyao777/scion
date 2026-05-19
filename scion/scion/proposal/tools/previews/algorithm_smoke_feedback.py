"""Agent-facing algorithm-smoke payload assembly.

Algorithm smoke is tainted, non-promotional debug evidence. This module only
builds the bounded observation the proposal agent may see; runtime extraction,
static section summaries, and failure classification live in focused siblings.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping

from scion.proposal.tools.models import ProposalObservation
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
from scion.proposal.tools.surface import _drop_empty_items
from scion.proposal.tools.utils import _json_size, _limit_text


def compact_algorithm_smoke_observation_for_agent(
    observation: ProposalObservation,
) -> ProposalObservation | None:
    """Return a registry-safe agent-facing smoke observation when possible."""
    if observation.tool_name != "proposal.algorithm_smoke" or observation.is_error:
        return None
    if not isinstance(observation.structured_payload, Mapping):
        return None
    payload = _algorithm_smoke_agent_payload(observation.structured_payload)
    return replace(
        observation,
        summary=(
            "Algorithm smoke passed on compact tainted preview."
            if payload.get("passed")
            else "Algorithm smoke found issues in compact tainted preview."
        ),
        structured_payload=payload,
        repair_hint=None,
    )


def _algorithm_smoke_agent_payload(raw_payload: Mapping[str, Any]) -> dict[str, Any]:
    runtime_smoke = _mapping_or_none(raw_payload.get("runtime_smoke"))
    runtime = runtime_smoke.get("runtime") if runtime_smoke else None
    run = runtime_smoke.get("run") if runtime_smoke else None
    telemetry_guard = _compact_algorithm_smoke_telemetry_guard(
        runtime_smoke.get("telemetry_guard") if runtime_smoke else None
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
    repair_hints = _algorithm_smoke_repair_hints(
        raw_payload,
        runtime_smoke=runtime_smoke,
        telemetry_guard=telemetry_guard,
    )
    failed_checks = _algorithm_smoke_failed_checks(
        raw_payload,
        runtime_smoke=runtime_smoke,
        primary_issue=primary_issue,
        failure_class=failure_class,
    )
    selected_surface = _algorithm_smoke_selected_surface(raw_payload, runtime_smoke)
    case_count = _algorithm_smoke_case_count(runtime_smoke)
    non_promotional = raw_payload.get("non_promotional", True)
    tainted_debug = raw_payload.get("tainted_debug", True)
    agent_summary = _agent_summary(
        passed=passed,
        status=status,
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
            "passed": passed,
            "status": status,
            "failure_class": failure_class,
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


__all__ = [
    "compact_algorithm_smoke_observation_for_agent",
    "_algorithm_smoke_agent_payload",
]
