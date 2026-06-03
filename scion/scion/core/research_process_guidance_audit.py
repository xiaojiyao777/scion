"""Compact audit metadata for prompt-facing research process guidance."""
from __future__ import annotations

from typing import Any, Mapping


_AUDIT_FIELDS = (
    "schema_version",
    "taint",
    "decision_input_policy",
    "source",
    "guidance_ref",
    "guidance_schema_key",
)


def extract_research_process_guidance_audit(
    payload: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Return stable, non-text audit metadata for research process guidance."""
    if not isinstance(payload, Mapping):
        return {}
    existing = payload.get("research_process_guidance_audit")
    if isinstance(existing, Mapping):
        return _compact_audit(existing)
    policy = payload.get("branch_followup_policy_payload")
    if isinstance(policy, Mapping):
        return _compact_audit(policy)
    if payload.get("guidance_schema_key") == "research_process_guidance":
        return _compact_audit(payload)
    return {}


def _compact_audit(payload: Mapping[str, Any]) -> dict[str, Any]:
    audit = {
        key: payload.get(key)
        for key in _AUDIT_FIELDS
        if payload.get(key) not in (None, "", [], {})
    }
    guidance = payload.get("research_process_guidance")
    if isinstance(guidance, Mapping):
        for key in ("principle", "not_a_hard_stop"):
            value = guidance.get(key)
            if value not in (None, "", [], {}):
                audit[key] = value
    else:
        for key in ("principle", "not_a_hard_stop"):
            value = payload.get(key)
            if value not in (None, "", [], {}):
                audit[key] = value
    if audit.get("guidance_schema_key") != "research_process_guidance":
        return {}
    return audit
