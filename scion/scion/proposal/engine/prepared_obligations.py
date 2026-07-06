"""Prepared research-obligation projection for proposal prompts."""

from __future__ import annotations

import json
from typing import Any, Mapping


_OBLIGATION_KEYS = (
    "current_question",
    "next_required_direction",
    "required_mechanism_ids",
    "target_intent_required_mechanism_ids",
    "required_evidence",
    "evidence_requirements",
    "required_mechanism_contracts",
)
_CONSTRAINT_KEYS = (
    "case_protection_requirements",
    "resume_continuity_requirements",
)


def prepared_research_obligations_payload(
    context: Mapping[str, Any],
) -> dict[str, Any]:
    """Project prepared focus into the research obligations prompts must preserve."""

    focus = _research_focus_payload(context)
    if not focus:
        return {}
    existing_target_intents = focus.get("target_intent_contracts")
    target_intents = (
        _json_safe(existing_target_intents)
        if isinstance(existing_target_intents, Mapping)
        else {}
    )
    target_intents.update({
        key: _json_safe(value)
        for key, value in focus.items()
        if isinstance(key, str)
        and key.endswith("_target_intent")
        and _json_safe(value) not in (None, "", [], {})
    })
    constraints = {
        key: _json_safe(focus.get(key))
        for key in _CONSTRAINT_KEYS
        if _json_safe(focus.get(key)) not in (None, "", [], {})
    }
    payload = {
        "schema_version": "scion.prepared_research_obligations_prompt.v1",
        "decision_input_policy": "excluded_from_decision_features",
        "prompt_contract": (
            "Prepared launch obligations are not historical notes. Preserve "
            "applicable target-intent, implementation, telemetry, and case "
            "protection obligations unless a hard boundary or API contradiction "
            "is reported explicitly."
        ),
    }
    for key in _OBLIGATION_KEYS:
        value = _json_safe(focus.get(key))
        if value not in (None, "", [], {}):
            payload[key] = value
    if target_intents:
        payload["target_intent_contracts"] = target_intents
    if constraints:
        payload["protection_and_continuity_contracts"] = constraints
    return {
        key: value
        for key, value in payload.items()
        if value not in (None, "", [], {})
    }


def prepared_research_obligations_section(
    context: Mapping[str, Any],
    *,
    code_phase: bool = False,
) -> str:
    payload = prepared_research_obligations_payload(context)
    if not payload:
        return ""
    phase_rule = (
        "Code-generation must implement or preserve the telemetry and "
        "case-protection obligations below when they apply to the approved "
        "mechanism or target file. The shorter hypothesis brief cannot omit "
        "or weaken them."
        if code_phase
        else "Use these obligations when selecting target intent and drafting "
        "the formal hypothesis; do not compress them into vague evidence claims."
    )
    rendered = json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2)
    return (
        "## Prepared Research Obligations\n"
        f"{phase_rule}\n\n"
        f"{rendered}"
    )


def _research_focus_payload(context: Mapping[str, Any]) -> Mapping[str, Any]:
    focus = context.get("launch_research_focus")
    if not isinstance(focus, Mapping):
        return {}
    research_focus = focus.get("research_focus")
    if isinstance(research_focus, Mapping):
        return research_focus
    return focus


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        projected = {
            str(key): child
            for key, item in value.items()
            if isinstance(key, str)
            and (child := _json_safe(item)) not in (None, "", [], {})
        }
        return projected
    if isinstance(value, (list, tuple)):
        return [
            child
            for item in value
            if (child := _json_safe(item)) not in (None, "", [], {})
        ]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value.strip() if isinstance(value, str) else value
    return str(value).strip()
