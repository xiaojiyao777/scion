"""Compact ledger helpers for APS planner tool selections."""
from __future__ import annotations

import json
from typing import Any, Mapping

from scion.proposal.agentic_utils import (
    _drop_empty_dict,
    _enum_value,
    _sanitize_agentic_value,
)
from scion.proposal.prompt_manifest import stable_digest
from scion.proposal.tools import ProposalObservation

TOOL_SELECTION_LEDGER_SCHEMA_VERSION = "agentic-tool-selection-ledger.v1"
_DEFAULT_TRIAD_TOOLS = frozenset(
    {"memory.query", "feedback.query_screening", "feedback.query_runtime"}
)


def tool_selection_ledger_payload(state: Any, output: Any) -> dict[str, Any]:
    prompt_visibility = _tool_result_prompt_visibility(state)
    entries = []
    for entry in getattr(state, "tool_selection_ledger", ()):
        if not isinstance(entry, Mapping):
            continue
        compact = dict(entry)
        observation_id = str(compact.get("result_observation_id") or "").strip()
        if observation_id and observation_id in prompt_visibility:
            visible = prompt_visibility[observation_id]
            compact["result_in_final_prompt"] = bool(visible.get("visible"))
            compact["result_in_final_prompt_status"] = visible.get("status") or (
                "included" if visible.get("visible") else "omitted"
            )
            compact["result_prompt_manifest_call_kind"] = visible.get("call_kind")
        entries.append(_sanitize_agentic_value(compact))
    return {
        "schema_version": TOOL_SELECTION_LEDGER_SCHEMA_VERSION,
        "session_id": getattr(output, "session_id", "") or getattr(state, "session_id", ""),
        "campaign_id": getattr(output, "campaign_id", "")
        or getattr(state, "campaign_id", ""),
        "branch_id": getattr(output, "branch_id", "") or getattr(state, "branch_id", ""),
        "deterministic_prefetch_plan_id": (
            str(getattr(state, "deterministic_prefetch_plan_id", "") or "").strip()
            or "none"
        ),
        "default_triad_satisfied": _default_triad_satisfied(entries),
        "entry_count": len(entries),
        "entries": entries,
    }


def record_tool_selection_ledger_entry(
    state: Any,
    *,
    phase: str,
    source: str,
    status: str,
    tool_name: str | None = None,
    args: Mapping[str, Any] | None = None,
    planner_context: Mapping[str, Any] | None = None,
    planned: Any = None,
    skip_reason: str | None = None,
    deferred_selection_source: str | None = None,
    result_observation: ProposalObservation | None = None,
) -> int:
    """Append one compact, tainted planner-selection ledger row."""

    entry_index = len(getattr(state, "tool_selection_ledger", ())) + 1
    normalized_args = dict(args or {})
    llm_usage = _planner_usage_payload(planned)
    input_token_cost = _input_token_cost(llm_usage)
    entry = {
        "index": entry_index,
        "planner_call_index": entry_index,
        "phase": phase,
        "source": source,
        "selected_tool": tool_name or "stop",
        "tool_name": tool_name or "stop",
        "args_digest": stable_digest(normalized_args, length=16),
        "args_hash": stable_digest(normalized_args, length=16),
        "status": status,
        "executed": status == "executed",
        "skipped": status == "skipped",
        "deferred": status == "deferred",
        "skip_reason": skip_reason,
        "deferred_selection_source": deferred_selection_source,
        "input_token_cost": input_token_cost,
        "input_token_cost_source": (
            "llm_usage"
            if input_token_cost is not None
            else "unavailable_in_session; see linked llm_trace"
        ),
        "estimated_input_tokens": _estimated_input_tokens(planner_context),
        "planner_context_digest": (
            stable_digest(planner_context, length=16)
            if planner_context is not None
            else None
        ),
        "deterministic_prefetch_plan_id": (
            str(getattr(state, "deterministic_prefetch_plan_id", "") or "").strip()
            or "none"
        ),
        "default_triad_satisfied": _default_triad_satisfied(
            getattr(state, "tool_selection_ledger", ())
        ),
    }
    state.tool_selection_ledger.append(_sanitize_agentic_value(entry))
    if result_observation is not None:
        update_tool_selection_ledger_result(
            state,
            entry_index,
            result_observation,
            status=status,
        )
    return entry_index


def update_tool_selection_ledger_result(
    state: Any,
    entry_index: int | None,
    observation: ProposalObservation,
    *,
    status: str = "executed",
) -> None:
    if entry_index is None:
        return
    entries = getattr(state, "tool_selection_ledger", None)
    if not isinstance(entries, list):
        return
    for offset, entry in enumerate(entries):
        if not isinstance(entry, Mapping):
            continue
        if int(entry.get("index") or 0) != int(entry_index):
            continue
        result_digest = _tool_result_digest(observation)
        novelty = _tool_result_novelty(state, observation, result_digest)
        updated = dict(entry)
        updated.update(
            _drop_empty_dict(
                {
                    "status": status,
                    "executed": status == "executed",
                    "skipped": status == "skipped",
                    "deferred": status == "deferred",
                    "result_digest": result_digest,
                    "result_hash": result_digest,
                    "result_novelty": novelty,
                    "tool_result_novelty": novelty,
                    "result_observation_id": observation.observation_id,
                    "result_tool_call_id": observation.tool_call_id,
                    "result_observation_type": observation.observation_type,
                    "result_is_error": observation.is_error,
                    "result_failure_code": _enum_value(observation.failure_code),
                    "result_summary": _sanitize_agentic_value(observation.summary),
                    "result_in_final_prompt": False,
                    "result_in_final_prompt_status": "pending_prompt_manifest",
                }
            )
        )
        entries[offset] = _sanitize_agentic_value(updated)
        return


def _tool_result_prompt_visibility(state: Any) -> dict[str, dict[str, Any]]:
    visibility: dict[str, dict[str, Any]] = {}
    for attr in ("_latest_hypothesis_prompt_manifest", "_latest_code_prompt_manifest"):
        manifest = getattr(state, attr, None)
        if not isinstance(manifest, Mapping):
            continue
        call_kind = str(manifest.get("call_kind") or "")
        for item in manifest.get("tool_result_visibility_ledger") or ():
            if not isinstance(item, Mapping):
                continue
            observation_id = str(item.get("observation_id") or "").strip()
            if not observation_id:
                continue
            visible = bool(
                item.get("result_in_final_prompt")
                or item.get("rendered_visibility_flag")
            )
            visibility[observation_id] = {
                "visible": visible,
                "status": item.get("result_in_final_prompt_status")
                or ("included" if visible else "omitted"),
                "call_kind": call_kind,
            }
    return visibility


def _tool_result_digest(observation: ProposalObservation) -> str:
    payload = {
        "tool_name": observation.tool_name,
        "observation_type": observation.observation_type,
        "summary": observation.summary,
        "structured_payload": _sanitize_agentic_value(observation.structured_payload),
        "is_error": observation.is_error,
        "failure_code": _enum_value(observation.failure_code),
    }
    return stable_digest(payload, length=16)


def _tool_result_novelty(
    state: Any,
    observation: ProposalObservation,
    result_digest: str,
) -> str:
    payload = (
        observation.structured_payload
        if isinstance(observation.structured_payload, Mapping)
        else {}
    )
    if _result_payload_empty(observation, payload):
        novelty = "empty"
    elif _result_summary_only(observation, payload):
        novelty = "summary_only"
    else:
        seen = _seen_result_digests(state)
        novelty = "duplicate_same_digest" if result_digest in seen else "new"
        seen.add(result_digest)
        return novelty
    _seen_result_digests(state).add(result_digest)
    return novelty


def _seen_result_digests(state: Any) -> set[str]:
    seen = getattr(state, "_tool_result_seen_digests", None)
    if not isinstance(seen, set):
        seen = set()
        setattr(state, "_tool_result_seen_digests", seen)
    return seen


def _result_payload_empty(
    observation: ProposalObservation,
    payload: Mapping[str, Any],
) -> bool:
    if observation.tool_name == "feedback.query_screening":
        status = payload.get("screening_observation_status")
        if isinstance(status, Mapping):
            return not bool(status.get("usable"))
        return int(payload.get("matched_screening_step_count") or 0) <= 0
    if observation.tool_name == "feedback.query_runtime":
        status = payload.get("runtime_observation_status")
        if isinstance(status, Mapping):
            return not bool(status.get("usable"))
        return not any(
            payload.get(key)
            for key in (
                "runtime_feedback",
                "runtime_failure_guidance",
                "screening_runtime_attribution",
                "inactive_reference_runtime_attribution",
            )
        )
    if payload:
        return False
    return not str(observation.summary or "").strip()


def _result_summary_only(
    observation: ProposalObservation,
    payload: Mapping[str, Any],
) -> bool:
    if str(observation.observation_type or "") in {
        "already_read_ref",
        "already_observed",
        "tool_skipped",
    }:
        return True
    if not payload and str(observation.summary or "").strip():
        return True
    return set(payload).issubset({"summary", "status", "message", "note"})


def _planner_usage_payload(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    for key in ("llm_usage", "_llm_usage", "usage"):
        usage = value.get(key)
        if isinstance(usage, Mapping):
            return usage
    return {}


def _input_token_cost(usage: Mapping[str, Any]) -> int | None:
    for key in ("input_tokens", "prompt_tokens_total", "prompt_tokens"):
        try:
            value = usage.get(key)
            if value not in (None, ""):
                return int(value)
        except Exception:
            continue
    return None


def _estimated_input_tokens(context: Mapping[str, Any] | None) -> int | None:
    if context is None:
        return None
    rendered = json.dumps(
        _sanitize_agentic_value(dict(context)),
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return max(1, (len(rendered) + 3) // 4)


def _default_triad_satisfied(entries: Any) -> bool:
    satisfied = {
        str(entry.get("selected_tool") or entry.get("tool_name") or "")
        for entry in entries or ()
        if isinstance(entry, Mapping)
        and entry.get("status") == "executed"
        and not entry.get("result_is_error")
    }
    return _DEFAULT_TRIAD_TOOLS.issubset(satisfied)


__all__ = [
    "TOOL_SELECTION_LEDGER_SCHEMA_VERSION",
    "record_tool_selection_ledger_entry",
    "tool_selection_ledger_payload",
    "update_tool_selection_ledger_result",
]
