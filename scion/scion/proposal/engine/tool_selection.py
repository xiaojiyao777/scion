"""Tool-selection prompt and response helpers."""

from __future__ import annotations

import json
from typing import Any, Dict

from pydantic import ValidationError

from scion.proposal.schemas import ToolSelectionInput

from .exceptions import ProposalValidationError


def _build_tool_selection_prompt(context: Dict[str, Any]) -> str:
    safe_context = _sanitize_tool_selection_context(context)
    if bool(context.get("code_phase")):
        return (
            "You are selecting the next exposure-controlled code-phase inspection "
            "tool for Scion after a hypothesis has already been approved.\n"
            "Scion controls boundaries and executes tools; you only return one "
            "plan_proposal_tool_call input naming an allowed tool and JSON args. "
            "Use these tools to inspect memory, branch state, runtime/screening "
            "feedback, and the declared problem research object before writing "
            "the final patch. Do not include code_content, private rationale, "
            "raw metric references, validation/frozen details, or workspace "
            "writes in the tool plan. Stop when no more inspection is needed.\n\n"
            "## Tool Selection Context\n"
            f"{json.dumps(safe_context, indent=2, sort_keys=True, default=str)}"
        )
    return (
        "You are selecting the next read-only proposal-context tool for Scion.\n"
        "Scion is a framework: use only the provided context and tool specs, "
        "without assuming any particular problem domain.\n"
        "Return exactly one plan_proposal_tool_call tool input. The selected "
        "tool_name must be present in allowed_tools. Do not execute tools. "
        "For context.read_surface, choose surface only from the current "
        "context.list_surfaces observation values shown in tool_arg_guidance. "
        "Do not include rationale, memory, private metric references, private "
        "evaluation details, or workspace target file code.\n\n"
        "## Tool Selection Context\n"
        f"{json.dumps(safe_context, indent=2, sort_keys=True, default=str)}"
    )


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
