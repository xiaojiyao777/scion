"""Provider-visible prompt manifests without storing raw prompts.

The manifest records the prompt after normal proposal-engine rendering.  Raw
``prompt_context`` is kept only as an audit digest; it is not counted as
provider-visible prompt text.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping

from scion.proposal.agentic_utils import _enum_value, _sanitize_agentic_value


MANIFEST_SCHEMA_VERSION = "api-visible-prompt-manifest.v2"
_SECTION_HEADING = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


def stable_digest(value: Any, *, length: int = 16) -> str:
    rendered = json.dumps(
        _sanitize_agentic_value(value),
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()[:length]


def build_api_visible_prompt_manifest(
    *,
    session_id: str,
    phase: str,
    call_kind: str,
    prompt_context: Mapping[str, Any],
    observations: tuple[Any, ...] | list[Any],
    call_index: int,
    system_blocks: tuple[Mapping[str, Any], ...] | list[Mapping[str, Any]] | None = None,
    user_prompt: str | None = None,
    render_error: str | None = None,
) -> dict[str, Any]:
    """Build an audit manifest for the rendered provider-visible prompt.

    ``prompt_context`` is the pre-render structured context.  It can contain
    live handles, large reusable ledgers, and helper-only fields, so it is never
    treated as the API-visible prompt.  Pass the exact ``system_blocks`` and
    ``user_prompt`` sent to the LLM client to populate the section projection.
    """
    safe_context = _sanitize_agentic_value(dict(prompt_context))
    rendered_system_blocks = tuple(system_blocks or ())
    rendered_user_prompt = "" if user_prompt is None else str(user_prompt)
    rendered_available = user_prompt is not None and render_error is None
    section_records = (
        _provider_visible_section_records(
            system_blocks=rendered_system_blocks,
            user_prompt=rendered_user_prompt,
        )
        if rendered_available
        else []
    )
    section_names = [record["name"] for record in section_records]
    section_statuses = {
        record["name"]: _section_status_record(record) for record in section_records
    }
    included_observations = [
        _observation_manifest_item(observation) for observation in observations
    ]
    system_chars = _system_text_chars(rendered_system_blocks)
    user_chars = len(rendered_user_prompt) if rendered_available else 0
    total_chars = system_chars + user_chars
    raw_context_digest = stable_digest(safe_context, length=64)
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "artifact_kind": "api_visible_prompt_manifest",
        "session_id": session_id,
        "phase": phase,
        "call_kind": call_kind,
        "call_index": call_index,
        "projection_source": (
            "rendered_provider_prompt" if rendered_available else "render_failed"
        ),
        "rendered_prompt_available": rendered_available,
        "render_error": str(render_error or "")[:500],
        "section_names": section_names,
        "char_budget": {
            "total_chars": total_chars,
            "provider_visible_total_chars": total_chars,
            "system_prompt_chars": system_chars,
            "user_prompt_chars": user_chars,
            "raw_context_json_chars_audit_only": _json_chars(safe_context),
            "sections": {
                record["name"]: record["char_count"] for record in section_records
            },
        },
        "provider_visible_prompt": {
            "system_block_count": len(rendered_system_blocks),
            "system_text_chars": system_chars,
            "user_prompt_chars": user_chars,
            "total_chars": total_chars,
            "section_count": len(section_records),
            "prompt_hash": (
                _provider_prompt_hash(rendered_system_blocks, rendered_user_prompt)
                if rendered_available
                else ""
            ),
        },
        "raw_context_audit": {
            "context_digest": raw_context_digest,
            "json_char_count": _json_chars(safe_context),
            "top_level_keys": list(safe_context),
            "api_visible_prompt": False,
            "note": (
                "Pre-render context digest for audit only; not counted as the "
                "provider-visible prompt projection."
            ),
        },
        "sections": section_records,
        "section_statuses": section_statuses,
        "included_observations": included_observations,
        "included_observation_ids": [
            item["observation_id"]
            for item in included_observations
            if item.get("observation_id")
        ],
        "included_observation_digests": [
            item["payload_digest"]
            for item in included_observations
            if item.get("payload_digest")
        ],
        "omitted_sections": [
            record["name"] for record in section_records if record["omitted"]
        ],
        "truncated_sections": [
            record["name"] for record in section_records if record["truncated"]
        ],
        "prompt_hash": (
            _provider_prompt_hash(rendered_system_blocks, rendered_user_prompt)
            if rendered_available
            else ""
        ),
        "raw_prompt_saved": False,
    }


def _provider_visible_section_records(
    *,
    system_blocks: tuple[Mapping[str, Any], ...] | list[Mapping[str, Any]],
    user_prompt: str,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen_names: dict[str, int] = {}
    for index, block in enumerate(system_blocks, start=1):
        text = str(block.get("text", "")) if isinstance(block, Mapping) else str(block)
        records.extend(
            _section_records_from_text(
                text,
                prompt_part="system",
                block_index=index,
                seen_names=seen_names,
            )
        )
    records.extend(
        _section_records_from_text(
            user_prompt,
            prompt_part="user",
            block_index=None,
            seen_names=seen_names,
        )
    )
    return records


def _section_records_from_text(
    text: str,
    *,
    prompt_part: str,
    block_index: int | None,
    seen_names: dict[str, int],
) -> list[dict[str, Any]]:
    if not text:
        return []
    matches = list(_SECTION_HEADING.finditer(text))
    chunks: list[tuple[str, str]] = []
    if not matches:
        label = (
            f"system_{block_index}_preamble"
            if block_index is not None
            else "user_preamble"
        )
        chunks.append((label, text))
    else:
        if matches[0].start() > 0 and text[: matches[0].start()].strip():
            label = (
                f"system_{block_index}_preamble"
                if block_index is not None
                else "user_preamble"
            )
            chunks.append((label, text[: matches[0].start()]))
        for offset, match in enumerate(matches):
            start = match.start()
            end = matches[offset + 1].start() if offset + 1 < len(matches) else len(text)
            chunks.append((match.group(1), text[start:end]))
    records: list[dict[str, Any]] = []
    for heading, chunk in chunks:
        if not chunk:
            continue
        base_name = _section_name(heading)
        name = _unique_section_name(base_name, seen_names)
        records.append(
            _section_record(
                name,
                chunk,
                heading=heading,
                prompt_part=prompt_part,
                block_index=block_index,
            )
        )
    return records


def _section_record(
    name: str,
    text: str,
    *,
    heading: str,
    prompt_part: str,
    block_index: int | None,
) -> dict[str, Any]:
    return {
        "name": name,
        "heading": heading,
        "prompt_part": prompt_part,
        "block_index": block_index,
        "char_count": len(text),
        "content_hash": _text_digest(text, length=16),
        "fact_packet_digest": _section_fact_packet_digest_from_text(text),
        "observation_ids": _section_observation_ids_from_text(text),
        "observation_digests": _section_observation_digests_from_text(text),
        "omitted": _text_has_marker(text, "omitted"),
        "truncated": _text_has_marker(text, "truncated"),
    }


def _section_status_record(section: Mapping[str, Any]) -> dict[str, Any]:
    if section.get("omitted"):
        status = "omitted"
    elif section.get("truncated"):
        status = "truncated"
    else:
        status = "included"
    return {
        "status": status,
        "present": True,
        "char_count": section.get("char_count", 0),
        "content_hash": section.get("content_hash", ""),
        "heading": section.get("heading", ""),
        "prompt_part": section.get("prompt_part", ""),
        "block_index": section.get("block_index"),
        "fact_packet_digest": section.get("fact_packet_digest", ""),
        "observation_id_count": len(section.get("observation_ids") or ()),
        "observation_digest_count": len(section.get("observation_digests") or ()),
    }


def _observation_manifest_item(observation: Any) -> dict[str, Any]:
    payload = _sanitize_agentic_value(getattr(observation, "structured_payload", {}))
    payload_digest = stable_digest(payload, length=16)
    provenance = _provenance_payload(payload)
    return {
        "observation_id": getattr(observation, "observation_id", ""),
        "tool_name": getattr(observation, "tool_name", ""),
        "tool_call_id": getattr(observation, "tool_call_id", ""),
        "observation_type": getattr(observation, "observation_type", ""),
        "payload_digest": payload_digest,
        "source_hash": stable_digest(provenance or payload, length=16),
        "source": provenance.get("source"),
        "artifact_ref_present": bool(getattr(observation, "artifact_ref", None)),
        "is_error": bool(getattr(observation, "is_error", False)),
        "failure_code": _enum_value(getattr(observation, "failure_code", None)),
        "exposure_level": _enum_value(getattr(observation, "exposure_level", None)),
    }


def _provenance_payload(value: Any) -> dict[str, Any]:
    found: dict[str, Any] = {}

    def visit(item: Any) -> None:
        if isinstance(item, Mapping):
            for key, child in item.items():
                key_text = str(key)
                if key_text in {"provenance", "source_digest"} and isinstance(
                    child, Mapping
                ):
                    found.setdefault(key_text, _sanitize_agentic_value(dict(child)))
                elif key_text in {
                    "source",
                    "digest",
                    "sha256",
                    "snapshot_digest",
                    "branch_id",
                    "base_champion_id",
                    "base_champion_hash",
                    "champion_version",
                    "champion_code_snapshot_hash",
                }:
                    found.setdefault(key_text, _sanitize_agentic_value(child))
                visit(child)
        elif isinstance(item, (list, tuple)):
            for child in item:
                visit(child)

    visit(value)
    return found


def _section_fact_packet_digest_from_text(text: str) -> str:
    match = re.search(r'"fact_packet_digest"\s*:\s*"([^"]+)"', text)
    return match.group(1) if match else ""


def _section_observation_ids_from_text(text: str) -> list[str]:
    return list(
        dict.fromkeys(
            match.group(1)
            for match in re.finditer(r'"observation_id"\s*:\s*"([^"]+)"', text)
        )
    )


def _section_observation_digests_from_text(text: str) -> list[str]:
    return list(
        dict.fromkeys(
            match.group(1)
            for match in re.finditer(
                r'"(?:digest|payload_digest)"\s*:\s*"([^"]+)"',
                text,
            )
        )
    )


def _json_chars(value: Any) -> int:
    return len(json.dumps(value, sort_keys=True, default=str))


def _system_text_chars(system_blocks: tuple[Mapping[str, Any], ...]) -> int:
    total = 0
    for block in system_blocks:
        if isinstance(block, Mapping):
            total += len(str(block.get("text", "")))
        else:
            total += len(str(block))
    return total


def _provider_prompt_hash(
    system_blocks: tuple[Mapping[str, Any], ...] | list[Mapping[str, Any]],
    user_prompt: str,
) -> str:
    blob = json.dumps(
        {"system_blocks": list(system_blocks), "user_prompt": user_prompt},
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _text_digest(value: str, *, length: int = 16) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def _section_name(heading: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", str(heading).strip().lower()).strip("_")
    return cleaned or "unnamed_section"


def _unique_section_name(base_name: str, seen_names: dict[str, int]) -> str:
    count = seen_names.get(base_name, 0) + 1
    seen_names[base_name] = count
    return base_name if count == 1 else f"{base_name}_{count}"


def _text_has_marker(text: str, marker: str) -> bool:
    lowered = text.lower()
    if marker == "truncated":
        return "truncated" in lowered or "<truncated" in lowered
    if marker == "omitted":
        return "omitted" in lowered or "<omitted" in lowered
    return marker.lower() in lowered


__all__ = ["MANIFEST_SCHEMA_VERSION", "build_api_visible_prompt_manifest", "stable_digest"]
