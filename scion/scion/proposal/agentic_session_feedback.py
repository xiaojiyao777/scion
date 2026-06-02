"""Feedback query and compaction helpers for Agentic Proposal Sessions."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping

from scion.proposal.agentic_code_context import _observation_prompt_payload
from scion.proposal.agentic_diagnostics import _research_diagnosis_has_signal
from scion.proposal.agentic_utils import (
    _bounded_string_list,
    _drop_empty_mapping,
    _json_size,
    _limit_string,
)
from scion.proposal.tools import ProposalObservation, ProposalToolContext

_APS_FEEDBACK_OBSERVATION_TARGET_CHARS = 6000
_APS_FEEDBACK_TEXT_CHARS = 1200
_APS_FEEDBACK_LIST_ITEMS = 4
_APS_FEEDBACK_MAP_ITEMS = 16


def _compact_feedback_observation_for_budget(
    observation: ProposalObservation,
) -> ProposalObservation:
    if observation.is_error or observation.tool_name not in {
        "feedback.query_screening",
        "feedback.query_runtime",
    }:
        return observation
    payload = observation.structured_payload
    if not isinstance(payload, Mapping):
        return observation
    if observation.tool_name == "feedback.query_screening":
        compact_payload = _compact_screening_feedback_payload(payload)
    else:
        compact_payload = _compact_runtime_feedback_payload(payload)
    compact_observation = replace(
        observation,
        summary=_limit_string(observation.summary, 260) or "Returned compact feedback.",
        structured_payload=compact_payload,
        repair_hint=None,
    )
    if _json_size(_observation_prompt_payload(compact_observation)) <= _json_size(
        _observation_prompt_payload(observation)
    ):
        return compact_observation
    return observation


def _feedback_observation_canonical_scope(
    observation: ProposalObservation,
    *,
    default_surface: str = "",
) -> tuple[str, str, str] | None:
    if observation.tool_name not in {
        "feedback.query_screening",
        "feedback.query_runtime",
    }:
        return None
    payload = observation.structured_payload
    payload = payload if isinstance(payload, Mapping) else {}
    status = payload.get("runtime_observation_status")
    if isinstance(status, Mapping):
        scope = status.get("canonical_scope")
        if isinstance(scope, Mapping):
            return (
                observation.tool_name,
                str(scope.get("branch_id") or "").strip(),
                str(scope.get("surface") or default_surface or "").strip(),
            )
    return (
        observation.tool_name,
        str(payload.get("branch_id") or "").strip(),
        str(payload.get("surface") or default_surface or "").strip(),
    )


def _feedback_args_canonical_scope(
    tool_name: str,
    args: Mapping[str, Any],
    *,
    default_surface: str = "",
) -> tuple[str, str, str] | None:
    if tool_name not in {"feedback.query_screening", "feedback.query_runtime"}:
        return None
    return (
        tool_name,
        str(args.get("branch_id") or "").strip(),
        str(args.get("surface") or default_surface or "").strip(),
    )


def _has_equivalent_feedback_observation(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
    tool_name: str,
    args: Mapping[str, Any],
    *,
    default_surface: str = "",
) -> bool:
    requested_scope = _feedback_args_canonical_scope(
        tool_name,
        args,
        default_surface=default_surface,
    )
    if requested_scope is None:
        return False
    for observation in reversed(tuple(observations)):
        if observation.tool_name != tool_name:
            continue
        if not _observation_satisfies_compact_requirement(None, observation):
            continue
        observed_scope = _feedback_observation_canonical_scope(
            observation,
            default_surface=default_surface,
        )
        if _feedback_scopes_equivalent(requested_scope, observed_scope):
            return True
    return False


def _canonical_feedback_observations(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
    *,
    default_surface: str = "",
) -> list[ProposalObservation]:
    selected: list[ProposalObservation] = []
    index_by_scope: dict[tuple[str, str, str], int] = {}
    for observation in observations:
        if observation.tool_name != "feedback.query_runtime":
            selected.append(observation)
            continue
        scope = _feedback_observation_canonical_scope(
            observation,
            default_surface=default_surface,
        )
        if (
            scope is None
            or observation.is_error
            or not _observation_satisfies_compact_requirement(None, observation)
        ):
            selected.append(observation)
            continue
        previous_index = index_by_scope.get(scope)
        if previous_index is None:
            index_by_scope[scope] = len(selected)
            selected.append(observation)
        else:
            selected[previous_index] = observation
    return selected


def _feedback_scopes_equivalent(
    requested: tuple[str, str, str] | None,
    observed: tuple[str, str, str] | None,
) -> bool:
    if requested is None or observed is None:
        return False
    req_tool, req_branch, req_surface = requested
    obs_tool, obs_branch, obs_surface = observed
    if req_tool != obs_tool:
        return False
    if req_branch:
        if obs_branch and obs_branch != req_branch:
            return False
    elif obs_branch:
        return False
    if req_surface:
        if obs_surface and obs_surface != req_surface:
            return False
    elif obs_surface:
        return False
    return True


def _compact_screening_feedback_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    rows = payload.get("screening_steps")
    compact_rows = []
    if isinstance(rows, list):
        compact_rows = [
            _compact_screening_step_for_budget(row)
            for row in rows[:_APS_FEEDBACK_LIST_ITEMS]
            if isinstance(row, Mapping)
        ]
    compact = _drop_empty_mapping(
        {
            "branch_id": payload.get("branch_id"),
            "surface": payload.get("surface"),
            "provenance": _compact_feedback_value_for_budget(
                payload.get("provenance")
            ),
            "active_boundary_filter": _compact_feedback_value_for_budget(
                payload.get("active_boundary_filter")
            ),
            "query_scope": _compact_feedback_value_for_budget(
                payload.get("query_scope")
            ),
            "available_screening_step_count": payload.get(
                "available_screening_step_count"
            ),
            "matched_screening_step_count": payload.get("matched_screening_step_count"),
            "screening_steps": compact_rows,
            "inactive_reference_steps": [
                _compact_screening_step_for_budget(row)
                for row in (
                    payload.get("inactive_reference_steps")[:_APS_FEEDBACK_LIST_ITEMS]
                    if isinstance(payload.get("inactive_reference_steps"), list)
                    else []
                )
                if isinstance(row, Mapping)
            ],
            "metrics_file_ref_exposed": False,
            "payload_truncated": True,
            "compacted_for_agentic_budget": True,
        }
    )
    return _shrink_feedback_payload_to_target(compact)


def _compact_runtime_feedback_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    attribution = payload.get("screening_runtime_attribution")
    compact_attribution = []
    if isinstance(attribution, list):
        compact_attribution = [
            _compact_runtime_attribution_for_budget(row)
            for row in attribution[:_APS_FEEDBACK_LIST_ITEMS]
            if isinstance(row, Mapping)
        ]
    compact = _drop_empty_mapping(
        {
            "branch_id": payload.get("branch_id"),
            "surface": payload.get("surface"),
            "provenance": _compact_feedback_value_for_budget(
                payload.get("provenance")
            ),
            "active_boundary_filter": _compact_feedback_value_for_budget(
                payload.get("active_boundary_filter")
            ),
            "query_scope": _compact_feedback_value_for_budget(
                payload.get("query_scope")
            ),
            "runtime_observation_status": _compact_feedback_value_for_budget(
                payload.get("runtime_observation_status")
            ),
            "runtime_feedback": _limit_string(
                payload.get("runtime_feedback"),
                _APS_FEEDBACK_TEXT_CHARS,
            ),
            "runtime_failure_guidance": _limit_string(
                payload.get("runtime_failure_guidance"),
                _APS_FEEDBACK_TEXT_CHARS,
            ),
            "screening_runtime_attribution": compact_attribution,
            "inactive_reference_runtime_attribution": [
                _compact_runtime_attribution_for_budget(row)
                for row in (
                    payload.get("inactive_reference_runtime_attribution")[
                        :_APS_FEEDBACK_LIST_ITEMS
                    ]
                    if isinstance(
                        payload.get("inactive_reference_runtime_attribution"), list
                    )
                    else []
                )
                if isinstance(row, Mapping)
            ],
            "research_diagnosis": _compact_research_diagnosis_for_budget(
                payload.get("research_diagnosis")
            ),
            "screening_only": payload.get("screening_only"),
            "metrics_file_refs_exposed": False,
            "payload_truncated": True,
            "compacted_for_agentic_budget": True,
        }
    )
    return _shrink_feedback_payload_to_target(compact)


def _compact_screening_step_for_budget(row: Mapping[str, Any]) -> dict[str, Any]:
    return _drop_empty_mapping(
        {
            "round_num": row.get("round_num"),
            "branch_id": row.get("branch_id"),
            "surface": row.get("surface"),
            "provenance": _compact_feedback_value_for_budget(row.get("provenance")),
            "action": row.get("action"),
            "target_file": row.get("target_file"),
            "gate_outcome": row.get("gate_outcome"),
            "reason_codes": _bounded_string_list(row.get("reason_codes"), limit=6),
            "stats": _compact_eval_stats_for_budget(row.get("stats")),
            "candidate_runtime_failure_categories": _compact_counts_for_budget(
                row.get("candidate_runtime_failure_categories")
            ),
            "candidate_first_runtime_failure": _compact_feedback_value_for_budget(
                row.get("candidate_first_runtime_failure")
            ),
            "candidate_runtime_stop_reasons": _compact_counts_for_budget(
                row.get("candidate_runtime_stop_reasons")
            ),
            "telemetry_guard_failed": row.get("telemetry_guard_failed"),
            "telemetry_failure_categories": _bounded_string_list(
                row.get("telemetry_failure_categories"),
                limit=6,
            ),
            "telemetry_failure_details": _compact_feedback_value_for_budget(
                row.get("telemetry_failure_details")
            ),
            "candidate_surface_runtime_attribution": _compact_runtime_attribution_for_budget(
                row.get("candidate_surface_runtime_attribution")
            ),
        }
    )


def _compact_runtime_attribution_for_budget(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    highlights = value.get("runtime_field_highlights")
    compact_highlights = []
    if isinstance(highlights, list):
        compact_highlights = [
            _compact_runtime_highlight_for_budget(highlight)
            for highlight in highlights[: _APS_FEEDBACK_LIST_ITEMS * 2]
            if isinstance(highlight, Mapping)
        ]
    return _drop_empty_mapping(
        {
            "round_num": value.get("round_num"),
            "surface": value.get("surface"),
            "provenance": _compact_feedback_value_for_budget(
                value.get("provenance")
            ),
            "target_file": value.get("target_file"),
            "gate_outcome": value.get("gate_outcome"),
            "reason_codes": _bounded_string_list(value.get("reason_codes"), limit=6),
            "stats": _compact_eval_stats_for_budget(value.get("stats")),
            "telemetry_guard_failed": value.get("telemetry_guard_failed"),
            "telemetry_failure_categories": _bounded_string_list(
                value.get("telemetry_failure_categories"),
                limit=6,
            ),
            "telemetry_failure_details": _compact_feedback_value_for_budget(
                value.get("telemetry_failure_details")
            ),
            "runtime_field_highlights": compact_highlights,
        }
    )


def _compact_runtime_highlight_for_budget(value: Mapping[str, Any]) -> dict[str, Any]:
    return _drop_empty_mapping(
        {
            "field": value.get("field"),
            "present": value.get("present"),
            "missing": value.get("missing"),
            "empty": value.get("empty"),
            "failed": value.get("failed"),
            "numeric_summary": _compact_feedback_value_for_budget(
                value.get("numeric_summary")
            ),
        }
    )


def _compact_research_diagnosis_for_budget(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    recent_steps = value.get("recent_screening_steps")
    runtime_rows = value.get("runtime_signal_rows")
    return _drop_empty_mapping(
        {
            "schema_version": value.get("schema_version"),
            "screening_only": value.get("screening_only"),
            "screening_step_count": value.get("screening_step_count"),
            "reason_code_counts": _compact_counts_for_budget(
                value.get("reason_code_counts")
            ),
            "surface_counts": _compact_counts_for_budget(value.get("surface_counts")),
            "declared_solver_design_surfaces": _bounded_string_list(
                value.get("declared_solver_design_surfaces"),
                limit=6,
            ),
            "failed_solver_design_surfaces": _bounded_string_list(
                value.get("failed_solver_design_surfaces"),
                limit=6,
            ),
            "screening_failed_solver_design_surfaces": _bounded_string_list(
                value.get("screening_failed_solver_design_surfaces"),
                limit=6,
            ),
            "unselected_solver_design_surfaces": _bounded_string_list(
                value.get("unselected_solver_design_surfaces"),
                limit=6,
            ),
            "gate_outcome_counts": _compact_counts_for_budget(
                value.get("gate_outcome_counts")
            ),
            "failure_mode_tags": _bounded_string_list(
                value.get("failure_mode_tags"),
                limit=8,
            ),
            "runtime_signal_rows": [
                _compact_feedback_value_for_budget(row)
                for row in (
                    runtime_rows[:_APS_FEEDBACK_LIST_ITEMS]
                    if isinstance(runtime_rows, list)
                    else []
                )
            ],
            "recent_screening_steps": [
                _compact_screening_step_for_budget(row)
                for row in (
                    recent_steps[:_APS_FEEDBACK_LIST_ITEMS]
                    if isinstance(recent_steps, list)
                    else []
                )
                if isinstance(row, Mapping)
            ],
            "next_hypothesis_requirements": _bounded_string_list(
                value.get("next_hypothesis_requirements"),
                limit=6,
            ),
        }
    )


def _compact_eval_stats_for_budget(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    keys = (
        "n_cases",
        "wins",
        "losses",
        "ties",
        "win_rate",
        "median_delta",
        "runtime_ratio_median",
        "runtime_delta_median_ms",
        "runtime_regression_rate",
        "valid_pairs",
        "failed_pairs",
        "candidate_failed_pairs",
    )
    return _drop_empty_mapping({key: value.get(key) for key in keys})


def _compact_counts_for_budget(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    compact: dict[str, Any] = {}
    for index, (key, item) in enumerate(
        sorted(value.items(), key=lambda pair: str(pair[0]))
    ):
        if index >= _APS_FEEDBACK_MAP_ITEMS:
            compact["_truncated_items"] = len(value) - _APS_FEEDBACK_MAP_ITEMS
            break
        compact[str(key)] = item
    return _drop_empty_mapping(compact)


def _compact_feedback_value_for_budget(value: Any, *, depth: int = 0) -> Any:
    if depth > 4:
        return _limit_string(value, 200)
    if isinstance(value, Mapping):
        compact: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= _APS_FEEDBACK_MAP_ITEMS:
                compact["_truncated_items"] = len(value) - _APS_FEEDBACK_MAP_ITEMS
                break
            compact[str(key)] = _compact_feedback_value_for_budget(
                item,
                depth=depth + 1,
            )
        return _drop_empty_mapping(compact)
    if isinstance(value, tuple):
        value = list(value)
    if isinstance(value, list):
        items = [
            _compact_feedback_value_for_budget(item, depth=depth + 1)
            for item in value[:_APS_FEEDBACK_LIST_ITEMS]
        ]
        if len(value) > _APS_FEEDBACK_LIST_ITEMS:
            items.append({"_truncated_items": len(value) - _APS_FEEDBACK_LIST_ITEMS})
        return items
    if isinstance(value, str):
        return _limit_string(value, max(200, _APS_FEEDBACK_TEXT_CHARS // (depth + 1)))
    return value


def _shrink_feedback_payload_to_target(payload: dict[str, Any]) -> dict[str, Any]:
    if _json_size(payload) <= _APS_FEEDBACK_OBSERVATION_TARGET_CHARS:
        return payload
    shrunk = dict(payload)
    if "runtime_feedback" in shrunk:
        shrunk["runtime_feedback"] = _limit_string(shrunk.get("runtime_feedback"), 600)
    if "runtime_failure_guidance" in shrunk:
        shrunk["runtime_failure_guidance"] = _limit_string(
            shrunk.get("runtime_failure_guidance"),
            600,
        )
    for key in (
        "screening_steps",
        "screening_runtime_attribution",
        "runtime_signal_rows",
        "recent_screening_steps",
    ):
        value = shrunk.get(key)
        if isinstance(value, list) and len(value) > 2:
            shrunk[key] = value[:2] + [{"_truncated_items": len(value) - 2}]
    if _json_size(shrunk) <= _APS_FEEDBACK_OBSERVATION_TARGET_CHARS:
        return _drop_empty_mapping(shrunk)
    return _drop_empty_mapping(
        {
            "branch_id": payload.get("branch_id"),
            "surface": payload.get("surface"),
            "query_scope": payload.get("query_scope"),
            "available_screening_step_count": payload.get(
                "available_screening_step_count"
            ),
            "matched_screening_step_count": payload.get("matched_screening_step_count"),
            "runtime_observation_status": payload.get("runtime_observation_status"),
            "screening_steps": _minimal_screening_rows_for_budget(
                payload.get("screening_steps")
            ),
            "screening_only": payload.get("screening_only"),
            "research_diagnosis": payload.get("research_diagnosis"),
            "metrics_file_refs_exposed": False,
            "metrics_file_ref_exposed": False,
            "payload_truncated": True,
            "compacted_for_agentic_budget": True,
            "summary": "APS feedback payload was summarized to preserve preview budget.",
        }
    )


def _minimal_screening_rows_for_budget(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    rows: list[dict[str, Any]] = []
    for row in value[:2]:
        if not isinstance(row, Mapping):
            continue
        rows.append(
            _drop_empty_mapping(
                {
                    "round_num": row.get("round_num"),
                    "surface": row.get("surface"),
                    "target_file": row.get("target_file"),
                    "gate_outcome": row.get("gate_outcome"),
                    "reason_codes": _bounded_string_list(
                        row.get("reason_codes"),
                        limit=4,
                    ),
                    "stats": _compact_eval_stats_for_budget(row.get("stats")),
                }
            )
        )
    return rows


def _feedback_query_args(context: ProposalToolContext) -> dict[str, Any]:
    args: dict[str, Any] = {}
    if context.forced_surface:
        args["surface"] = context.forced_surface
    else:
        active_boundary = [
            str(surface or "").strip()
            for surface in context.active_problem_boundary_surfaces
            if str(surface or "").strip()
        ]
        if len(active_boundary) == 1:
            args["surface"] = active_boundary[0]
    return args


def _has_feedback_screening_history(context: ProposalToolContext) -> bool:
    forced_surface = str(context.forced_surface or "").strip()
    for step in context.step_history:
        if _step_stage_name(step) != "screening":
            continue
        if forced_surface and _step_surface_name(step) != forced_surface:
            continue
        return True
    return False


def _step_surface_name(step: Any) -> str:
    hypothesis = getattr(step, "hypothesis", None)
    return str(getattr(hypothesis, "change_locus", "") or "").strip()


def _step_stage_name(step: Any) -> str:
    protocol = getattr(step, "protocol_result", None)
    stage = getattr(protocol, "stage", None)
    value = getattr(stage, "value", stage)
    return str(value or "").strip().lower()


def _observation_satisfies_compact_requirement(
    context: ProposalToolContext | None,
    observation: ProposalObservation,
) -> bool:
    del context
    if observation.is_error:
        return False
    if observation.tool_name == "feedback.query_screening":
        return _screening_feedback_observation_has_rows(observation)
    if observation.tool_name == "feedback.query_runtime":
        return _runtime_feedback_observation_has_content(observation)
    return True


def _screening_feedback_observation_has_rows(
    observation: ProposalObservation,
) -> bool:
    payload = observation.structured_payload
    rows = payload.get("screening_steps") if isinstance(payload, Mapping) else None
    return isinstance(rows, list) and bool(rows)


def _runtime_feedback_observation_has_content(
    observation: ProposalObservation,
) -> bool:
    payload = observation.structured_payload
    if not isinstance(payload, Mapping):
        return False
    status = payload.get("runtime_observation_status")
    if isinstance(status, Mapping) and status.get("usable") is True:
        return True
    for key in ("runtime_feedback", "runtime_failure_guidance"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return True
    attribution = payload.get("screening_runtime_attribution")
    if isinstance(attribution, list) and bool(attribution):
        return True
    inactive_attribution = payload.get("inactive_reference_runtime_attribution")
    if isinstance(inactive_attribution, list) and bool(inactive_attribution):
        return True
    diagnosis = payload.get("research_diagnosis")
    return isinstance(diagnosis, Mapping) and _research_diagnosis_has_signal(diagnosis)
