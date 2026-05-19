"""Shared prompt rendering helpers for proposal-engine requests."""

from __future__ import annotations

import json
from typing import Any, Dict


class _DefaultDict(dict):
    """dict subclass that returns '' for missing keys (safe format_map)."""

    def __missing__(self, key: str) -> str:
        return ""


_CACHE_5M = {"type": "ephemeral"}
_AGENTIC_RESEARCH_DIAGNOSIS_CHARS = 12000
_AGENTIC_TOOL_OBSERVATIONS_CHARS = 24000
_AGENTIC_CODE_RESEARCH_DIAGNOSIS_CHARS = 6000
_AGENTIC_CODE_TOOL_OBSERVATIONS_CHARS = 6000


def _agentic_research_context_block(
    context: Dict[str, Any],
    *,
    code_phase: bool = False,
) -> str:
    parts: list[str] = []
    semantic_rejections = context.get("agentic_hypothesis_semantic_rejections")
    if semantic_rejections:
        retry_payload = {
            "retry_attempt": context.get("agentic_hypothesis_retry_attempt"),
            "retry_rule": context.get("agentic_hypothesis_retry_rule"),
            "semantic_rejections": semantic_rejections,
        }
        parts.append(
            "## Hypothesis Semantic Retry Feedback\n"
            "The previous hypothesis was rejected by an audited semantic gate. "
            "Use this feedback as a hard constraint: choose a different "
            "mechanism family or repair the contradicted premise before "
            "drafting the next hypothesis.\n\n"
            f"{_bounded_json(retry_payload, 6000)}"
        )
    diagnosis = context.get("agentic_research_diagnosis")
    if diagnosis:
        heading = (
            "## Evidence Diagnosis Behind This Hypothesis"
            if code_phase
            else "## Agentic Research Diagnosis"
        )
        parts.append(
            f"{heading}\n"
            "Screening/runtime observations below are tainted proposal context, "
            "not Decision input. Use them to explain which declared surface "
            "evidence should change and why the next mechanism differs from "
            "prior failed attempts.\n\n"
            f"{_bounded_json(diagnosis, _agentic_research_diagnosis_chars(code_phase))}"
        )
    observations = context.get("agentic_tool_observations")
    if observations:
        parts.append(
            "## Agentic Proposal Tool Observations\n"
            "These are exposure-controlled tool observations gathered before "
            "generation. Use screening/runtime feedback and selected-surface "
            "metadata when forming the hypothesis or implementing the approved "
            "change; do not treat raw refs or holdout detail as available.\n\n"
            f"{_bounded_json(observations, _agentic_observation_chars(code_phase))}"
        )
    return "\n\n".join(parts)


def _format_bulleted_section(title: str, lines: list[str]) -> str:
    return f"## {title}\n{_format_bullets(lines)}"


def _format_bullets(lines: list[str]) -> str:
    return "".join(f"- {line}\n" for line in lines)


def _limit_code_phase_text(text: str, max_chars: int, *, label: str) -> str:
    if not text or len(text) <= max_chars:
        return text
    suffix = f"\n... <truncated {label} for compact code generation>"
    return text[: max(0, max_chars - len(suffix))] + suffix


def _agentic_research_diagnosis_chars(code_phase: bool) -> int:
    return (
        _AGENTIC_CODE_RESEARCH_DIAGNOSIS_CHARS
        if code_phase
        else _AGENTIC_RESEARCH_DIAGNOSIS_CHARS
    )


def _agentic_observation_chars(code_phase: bool) -> int:
    return (
        _AGENTIC_CODE_TOOL_OBSERVATIONS_CHARS
        if code_phase
        else _AGENTIC_TOOL_OBSERVATIONS_CHARS
    )


def _bounded_json(value: Any, max_chars: int) -> str:
    try:
        rendered = json.dumps(value, indent=2, sort_keys=True, default=str)
    except TypeError:
        rendered = str(value)
    if len(rendered) <= max_chars:
        return rendered
    return rendered[: max(0, max_chars - 80)] + "\n... <truncated agentic context>"
