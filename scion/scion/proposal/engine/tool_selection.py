"""Tool-selection prompt and response helpers."""

from __future__ import annotations

import json
from typing import Any, Dict

from pydantic import ValidationError

from scion.proposal.schemas import ToolSelectionInput

from .exceptions import ProposalValidationError
from .prompt_common import _CACHE_5M


_TOOL_SELECTION_SYSTEM_TEXT = (
    "You are selecting the next exposure-controlled Scion proposal tool.\n"
    "Scion controls boundaries and executes tools; you only return one "
    "plan_proposal_tool_call input naming an allowed tool and JSON args.\n"
    "Use read-only tools to inspect memory, branch state, runtime/screening "
    "feedback, and the declared problem research object before generating "
    "hypotheses or code. Do not include code_content, private rationale, raw "
    "metric references, validation/frozen details, holdout detail, or workspace "
    "writes in the tool plan. Stop when no more inspection is needed.\n"
    "For context.read_surface, choose surface only from the current "
    "context.list_surfaces observation values shown in tool_arg_guidance.\n"
    "Return exactly one plan_proposal_tool_call tool input. The selected "
    "tool_name must be present in allowed_tools."
)


def _split_tool_selection_context(
    context: Dict[str, Any],
) -> "tuple[list[dict], str]":
    safe_context = _sanitize_tool_selection_context(context)
    tool_catalog = _tool_selection_tool_catalog(safe_context)
    dynamic_context = dict(safe_context)
    dynamic_context.pop("allowed_tool_specs", None)
    dynamic_context.pop("allowed_tools", None)
    stable_context, dynamic_context = _split_tool_selection_cache_context(
        dynamic_context
    )

    stable_parts = [_TOOL_SELECTION_SYSTEM_TEXT]
    if tool_catalog:
        stable_parts.append(
            "## Tool Selection Catalog\n"
            f"{json.dumps(tool_catalog, indent=2, sort_keys=True, default=str)}"
        )
    if stable_context:
        stable_parts.append(
            "## Stable Tool Selection Context\n"
            "These fields are stable for this proposal phase and are cached so "
            "repeated tool planning calls do not resend unchanged research-object "
            "facts. Dynamic observations and remaining budgets are in the user "
            "message below.\n"
            f"{json.dumps(stable_context, indent=2, sort_keys=True, default=str)}"
        )
    system_blocks = [
        {
            "type": "text",
            "text": "\n\n".join(part for part in stable_parts if str(part).strip()),
            "cache_control": _CACHE_5M,
        }
    ]

    phase = "code" if bool(context.get("code_phase")) else "hypothesis"
    user_prompt = (
        f"## Tool Selection Phase\n{phase}\n\n"
        "## Dynamic Tool Selection Context\n"
        f"{json.dumps(dynamic_context, indent=2, sort_keys=True, default=str)}"
    )
    return system_blocks, user_prompt


_TOOL_SELECTION_CACHEABLE_CONTEXT_KEYS = frozenset(
    {
        "active_algorithm_facts_anchor",
        "hypothesis_constraints",
        "reserved_for_self_check",
        "tool_arg_guidance",
    }
)

_TOOL_SELECTION_VOLATILE_CACHE_KEYS = frozenset(
    {
        "branch_id",
        "evidence_ref",
        "request_id",
        "session_id",
        "source_observation_id",
        "source_tool_call_id",
        "step_id",
        "tool_call_id",
    }
)


def _split_tool_selection_cache_context(
    context: Dict[str, Any],
) -> "tuple[Dict[str, Any], Dict[str, Any]]":
    """Move stable planner context into the cacheable prefix.

    Tool-selection calls happen repeatedly while the observation list grows. If
    unchanged active facts and tool guidance stay in the user message, provider
    caching can only reuse the static catalog prefix. Keep observation history
    and step/budget counters dynamic, but cache the stable research-object
    anchors that are identical across calls in a phase.
    """
    stable: Dict[str, Any] = {}
    dynamic: Dict[str, Any] = {}
    for key, value in context.items():
        if key in _TOOL_SELECTION_CACHEABLE_CONTEXT_KEYS and value not in (
            None,
            "",
            [],
            {},
        ):
            stable[key] = _strip_tool_selection_cache_volatiles(value)
        else:
            dynamic[key] = value
    return stable, dynamic


def _strip_tool_selection_cache_volatiles(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _strip_tool_selection_cache_volatiles(item)
            for key, item in value.items()
            if str(key) not in _TOOL_SELECTION_VOLATILE_CACHE_KEYS
        }
    if isinstance(value, (list, tuple)):
        return [_strip_tool_selection_cache_volatiles(item) for item in value]
    return value


def _build_tool_selection_prompt(context: Dict[str, Any]) -> str:
    system_blocks, user_prompt = _split_tool_selection_context(context)
    system_text = "\n\n".join(
        str(block.get("text", "")) for block in system_blocks if isinstance(block, dict)
    )
    if bool(context.get("code_phase")):
        return (
            f"{system_text}\n\n"
            "Code-phase note: a hypothesis has already been approved; inspect "
            "only what is needed before writing the final patch.\n\n"
            f"{user_prompt}"
        )
    return f"{system_text}\n\n{user_prompt}"


def _tool_selection_tool_catalog(context: Dict[str, Any]) -> Dict[str, Any]:
    catalog: Dict[str, Any] = {}
    for key in ("allowed_tools", "allowed_tool_specs"):
        value = context.get(key)
        if value not in (None, "", [], {}):
            catalog[key] = value
    return catalog


def _sanitize_tool_selection_context(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if key_text in {
                "raw_metrics_ref",
                "raw_metrics_public_ref",
                "raw_metrics_path",
                "case_ids",
                "seed_set",
                "pair_feedback",
                "audit_payload_json",
                "internal_audit_payload",
                "artifact_path",
                "code",
                "code_content",
                "current_artifact",
                "target_file_code",
            }:
                continue
            cleaned[key_text] = _sanitize_tool_selection_context(item)
        return cleaned
    if isinstance(value, (list, tuple)):
        return [_sanitize_tool_selection_context(item) for item in value]
    if isinstance(value, str):
        forbidden_terms = (
            "raw_metrics_ref",
            "raw metrics",
            "validation",
            "frozen",
            "holdout",
        )
        lines = [
            line
            for line in value.splitlines()
            if not any(term in line.lower() for term in forbidden_terms)
        ]
        return "\n".join(lines)
    return value


def _parse_tool_selection(raw: Dict[str, Any]) -> Dict[str, Any]:
    try:
        validated = ToolSelectionInput(**raw)
    except ValidationError as exc:
        raise ProposalValidationError(str(exc)) from exc
    if validated.intent in {"stop", "final"}:
        return {"stop": True, "intent": validated.intent}
    return {
        "tool_name": validated.tool_name,
        "args": dict(validated.args or {}),
        "intent": validated.intent,
    }
