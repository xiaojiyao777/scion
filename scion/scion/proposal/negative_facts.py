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
            "## Do Not Claim Missing / Known Existing Mechanisms",
            (
                "Provider-owned facts and prior structured rejections below are "
                "hard grounding constraints for this hypothesis."
            ),
            *deduped,
        ]
    )


def _entry_from_rejection(payload: Mapping[str, Any]) -> str:
    if not isinstance(payload, Mapping):
        return ""
    fact_ids = _fact_ids(payload)
    if not fact_ids:
        return ""
    mechanism = _text(payload.get("mechanism")) or fact_ids[0]
    guidance = (
        _text(payload.get("allowed_variant_guidance"))
        or _text(payload.get("retry_constraint"))
        or _text(payload.get("reason"))
    )
    parts = [
        f"- fact_id={','.join(fact_ids[:3])}",
        f"mechanism={mechanism}",
        "do_not_claim_missing=true",
    ]
    if guidance:
        parts.append(f"allowed_variant_guidance={guidance}")
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
