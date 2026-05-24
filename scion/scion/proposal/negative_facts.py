"""Prompt-facing negative fact rendering.

The inputs are provider-owned fact packets or structured rejection payloads.
This module only formats their already-supplied identifiers and guidance.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

_MAX_ENTRIES = 8
_MAX_TEXT = 260


def render_negative_fact_block(
    *,
    active_algorithm_facts: Mapping[str, Any] | None = None,
    structured_rejections: Sequence[Mapping[str, Any]] = (),
    prior_quality_blocks: Sequence[Mapping[str, Any]] = (),
) -> str:
    """Render compact "do not claim missing" facts for hypothesis prompts."""
    entries: list[str] = []
    for payload in (*tuple(structured_rejections or ()), *tuple(prior_quality_blocks or ())):
        entry = _entry_from_rejection(payload)
        if entry:
            entries.append(entry)
        if len(entries) >= _MAX_ENTRIES:
            break
    if len(entries) < _MAX_ENTRIES:
        for entry in _entries_from_active_facts(active_algorithm_facts):
            entries.append(entry)
            if len(entries) >= _MAX_ENTRIES:
                break
    if not entries:
        return ""
    deduped = list(dict.fromkeys(entries))
    return "\n".join(
        [
            "## Do Not Claim Missing / Near-Field Mechanism Memory",
            (
                "Provider-owned facts and prior structured rejections below are "
                "near-field grounding constraints for this hypothesis. Treat "
                "contradicted premises as blacklisted, but use allowed variant "
                "guidance to preserve legitimate follow-up variants."
            ),
            *deduped,
        ]
    )


def _entry_from_rejection(payload: Mapping[str, Any]) -> str:
    if not isinstance(payload, Mapping):
        return ""
    fact_ids = _fact_ids(payload)
    mechanism = _text(payload.get("mechanism")) or (fact_ids[0] if fact_ids else "")
    failure_code = _text(payload.get("failure_code"))
    premise_check = _text(payload.get("premise_check"))
    if not fact_ids and not _near_field_memory_worthy(payload, mechanism):
        return ""
    guidance = (
        _text(payload.get("allowed_variant_guidance"))
        or _text(payload.get("retry_constraint"))
        or _text(payload.get("reason"))
    )
    parts = [
        (
            f"- fact_id={','.join(fact_ids[:3])}"
            if fact_ids
            else "- fact_id=unstructured_prior_feedback"
        ),
        f"mechanism={mechanism}",
    ]
    if _blacklists_missing_premise(payload):
        parts.append("do_not_claim_missing=true")
    else:
        parts.append("repeat_unchanged_mechanism=false")
    target = _text(payload.get("target_file"))
    if target:
        parts.append(f"target_file={target}")
    if premise_check:
        parts.append(f"premise_check={premise_check}")
    if failure_code:
        parts.append(f"failure_code={failure_code}")
    if guidance:
        parts.append(f"allowed_variant_guidance={guidance}")
    for key in (
        "contradicted_premise",
        "active_fact_digest",
        "diagnostic_type",
        "activation_status",
        "effect_status",
        "why_not_promoted",
        "screening_pair_case_split",
    ):
        value = _text(payload.get(key))
        if value:
            parts.append(f"{key}={value}")
    fact_packet_digest = _text(
        payload.get("fact_packet_digest")
        or payload.get("source_fact_digest")
    )
    snapshot_digest = _text(payload.get("snapshot_digest"))
    if fact_packet_digest:
        parts.append(f"fact_packet_digest={fact_packet_digest}")
    if snapshot_digest:
        parts.append(f"snapshot_digest={snapshot_digest}")
    return "; ".join(parts)


def _near_field_memory_worthy(payload: Mapping[str, Any], mechanism: str) -> bool:
    if mechanism:
        return True
    failure_code = _text(payload.get("failure_code")).lower()
    premise_check = _text(payload.get("premise_check")).lower()
    diagnostic_type = _text(payload.get("diagnostic_type")).lower()
    return any(
        marker
        for marker in (
            failure_code,
            premise_check,
            diagnostic_type,
        )
        if marker
    )


def _blacklists_missing_premise(payload: Mapping[str, Any]) -> bool:
    failure_code = _text(payload.get("failure_code"))
    premise_check = _text(payload.get("premise_check"))
    category = _text(payload.get("failure_category"))
    return (
        failure_code == "proposal_premise_contradicted"
        or premise_check == "contradicted"
        or category == "agent_grounding_failure"
    )


def _entries_from_active_facts(value: Mapping[str, Any] | None) -> list[str]:
    if not isinstance(value, Mapping):
        return []
    packet = value.get("active_algorithm_facts")
    if not isinstance(packet, Mapping):
        packet = value
    facts = packet.get("facts")
    if not isinstance(facts, Sequence) or isinstance(facts, (str, bytes, bytearray)):
        return []
    entries: list[str] = []
    packet_digest = _text(packet.get("fact_packet_digest"))
    for item in facts[:_MAX_ENTRIES]:
        if not isinstance(item, Mapping):
            continue
        fact_id = _text(item.get("fact_id"))
        if not fact_id:
            continue
        mechanism = _text(item.get("mechanism")) or fact_id
        guidance = (
            _text(item.get("allowed_variant_guidance"))
            or "Only propose a materially distinct variant with new observable behavior."
        )
        claim = _text(item.get("claim"))
        parts = [
            f"- fact_id={fact_id}",
            f"mechanism={mechanism}",
            "do_not_claim_missing=true",
            f"allowed_variant_guidance={guidance}",
        ]
        if claim:
            parts.append(f"known_fact={claim}")
        if packet_digest:
            parts.append(f"fact_digest={packet_digest}")
        entries.append("; ".join(parts))
    return entries


def _fact_ids(payload: Mapping[str, Any]) -> list[str]:
    raw = (
        payload.get("fact_ids")
        or payload.get("contradicted_fact_ids")
        or payload.get("matched_fact_ids")
    )
    if isinstance(raw, str):
        return [_text(raw)] if _text(raw) else []
    if isinstance(raw, Sequence):
        return [_text(item) for item in raw if _text(item)]
    return []


def _text(value: Any) -> str:
    text = str(value or "").strip().replace("\n", " ")
    if len(text) > _MAX_TEXT:
        return text[: _MAX_TEXT - 3] + "..."
    return text


__all__ = ["render_negative_fact_block"]
