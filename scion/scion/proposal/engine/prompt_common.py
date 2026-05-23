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
_AGENTIC_ACTIVE_ALGORITHM_FACTS_CHARS = 16000
_AGENTIC_ACTIVE_SOLVER_MECHANISMS_CHARS = 4000
_AGENTIC_RESUME_CONTEXT_CHARS = 3600
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
    preview_rejections = context.get("agentic_hypothesis_preview_rejections")
    if preview_rejections:
        retry_payload = {
            "retry_attempt": context.get("agentic_hypothesis_retry_attempt"),
            "retry_rule": context.get("agentic_hypothesis_preview_retry_rule"),
            "preview_rejections": preview_rejections,
        }
        parts.append(
            "## Hypothesis Schema/Telemetry Retry Feedback\n"
            "The previous hypothesis was rejected by an audited schema/target "
            "preview. Use this feedback as a hard structured-output constraint: "
            "repair the named field exactly, keep the research premise grounded, "
            "and do not reuse invalid telemetry paths.\n\n"
            f"{_bounded_json(retry_payload, 6000)}"
        )
    resume_context = _resume_context_projection(context.get("agentic_resume_context"))
    if resume_context:
        parts.append(
            "## Agentic Resume Context\n"
            "This compact handoff summarizes the previous APS attempt. Read "
            "receipts are digests, not source contents; reread files when exact "
            "code is needed. Do not infer hidden raw ledger contents from this "
            "section.\n\n"
            f"{_bounded_json(resume_context, _AGENTIC_RESUME_CONTEXT_CHARS)}"
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
    active_algorithm_facts = context.get("agentic_active_algorithm_facts")
    if active_algorithm_facts:
        parts.append(
            "## Active Algorithm Facts\n"
            "These compact problem-adapter facts are the primary active-solver "
            "mechanism context. They are shared with deterministic semantic "
            "gates; use raw tool observations only as audit/support material.\n\n"
            f"{_bounded_json(active_algorithm_facts, _AGENTIC_ACTIVE_ALGORITHM_FACTS_CHARS)}"
        )
    active_solver_mechanisms = context.get("agentic_active_solver_mechanisms")
    if active_solver_mechanisms and not _same_fact_packet(
        active_algorithm_facts,
        active_solver_mechanisms,
    ):
        parts.append(
            "## Active Solver Mechanism Digest\n"
            "Compact mechanism evidence from the active-solver snapshot. Use it "
            "only when it adds information not already present in Active "
            "Algorithm Facts.\n\n"
            f"{_bounded_json(active_solver_mechanisms, _AGENTIC_ACTIVE_SOLVER_MECHANISMS_CHARS)}"
        )
    observations = context.get("agentic_tool_observations")
    if observations:
        observations = _dedupe_tool_observations(
            observations,
            active_algorithm_facts=active_algorithm_facts,
            resume_context=resume_context,
        )
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


def _resume_context_projection(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    resume = value.get("resume") if isinstance(value.get("resume"), dict) else value
    projection = resume.get("model_facing_projection")
    if isinstance(projection, dict):
        return projection
    compact = {
        "schema_version": "agentic-resume-model-projection.v1",
        "source": value.get("source") or "agentic_resume_context",
        "previous_session": _drop_empty(
            {
                "session_id": resume.get("session_id"),
                "termination_reason": resume.get("termination_reason"),
                "failure_category": resume.get("failure_category"),
                "transcript_digest": resume.get("transcript_digest"),
            }
        ),
        "active_fact_anchor": resume.get("active_fact_anchor"),
        "read_receipts": _bounded_list(resume.get("read_receipts"), 6),
        "tool_budget_used": resume.get("tool_budget_used"),
        "structured_rejection": resume.get("structured_rejection"),
    }
    return _drop_empty(compact)


def _dedupe_tool_observations(
    observations: Any,
    *,
    active_algorithm_facts: Any,
    resume_context: Any,
) -> Any:
    if not isinstance(observations, list):
        return observations
    active_digest = _fact_packet_digest(active_algorithm_facts)
    resume_active_digest = _fact_packet_digest(resume_context)
    compact: list[Any] = []
    for observation in observations:
        if not isinstance(observation, dict):
            compact.append(observation)
            continue
        item = dict(observation)
        payload = item.get("structured_payload")
        if isinstance(payload, dict):
            payload = _dedupe_observation_payload(
                payload,
                active_digest=active_digest,
                resume_active_digest=resume_active_digest,
            )
            item["structured_payload"] = payload
        compact.append(item)
    return compact


def _dedupe_observation_payload(
    payload: dict[str, Any],
    *,
    active_digest: str,
    resume_active_digest: str,
) -> dict[str, Any]:
    compact = dict(payload)
    facts = compact.get("active_algorithm_facts")
    facts_digest = _fact_packet_digest(facts)
    if facts_digest and facts_digest in {active_digest, resume_active_digest}:
        compact["active_algorithm_facts_ref"] = _drop_empty(
            {
                "fact_packet_digest": facts_digest,
                "snapshot_digest": _snapshot_digest(facts),
                "fact_ids": _fact_ids(facts),
                "omitted_from_raw_observation": (
                    "deduplicated; see Active Algorithm Facts / Resume Context"
                ),
            }
        )
        compact.pop("active_algorithm_facts", None)
    return compact


def _same_fact_packet(left: Any, right: Any) -> bool:
    left_digest = _fact_packet_digest(left)
    return bool(left_digest and left_digest == _fact_packet_digest(right))


def _fact_packet_digest(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    direct = value.get("fact_packet_digest")
    if direct:
        return str(direct)
    for key in (
        "active_algorithm_facts",
        "active_fact_anchor",
        "active_fact_digest",
    ):
        child = value.get(key)
        if isinstance(child, dict):
            digest = _fact_packet_digest(child)
            if digest:
                return digest
    return ""


def _snapshot_digest(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    direct = value.get("snapshot_digest")
    if direct:
        return str(direct)
    child = value.get("active_algorithm_facts")
    if isinstance(child, dict):
        return _snapshot_digest(child)
    return ""


def _fact_ids(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return []
    raw = value.get("fact_ids")
    if isinstance(raw, (list, tuple)):
        return [str(item) for item in raw[:20] if str(item)]
    child = value.get("active_algorithm_facts")
    if isinstance(child, dict):
        return _fact_ids(child)
    return []


def _bounded_list(value: Any, limit: int) -> list[Any]:
    if not isinstance(value, (list, tuple)):
        return []
    return list(value[: max(0, limit)])


def _drop_empty(value: dict[str, Any]) -> dict[str, Any]:
    return {
        key: item
        for key, item in value.items()
        if item not in (None, "", (), [], {})
    }
