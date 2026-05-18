"""API-visible prompt manifests without storing raw prompts."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from scion.proposal.agentic_utils import _enum_value, _sanitize_agentic_value


MANIFEST_SCHEMA_VERSION = "api-visible-prompt-manifest.v1"


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
) -> dict[str, Any]:
    safe_context = _sanitize_agentic_value(dict(prompt_context))
    section_names = list(safe_context)
    section_records = [
        _section_record(name, safe_context.get(name)) for name in section_names
    ]
    section_statuses = {
        record["name"]: _section_status_record(record) for record in section_records
    }
    included_observations = [
        _observation_manifest_item(observation) for observation in observations
    ]
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "artifact_kind": "api_visible_prompt_manifest",
        "session_id": session_id,
        "phase": phase,
        "call_kind": call_kind,
        "call_index": call_index,
        "section_names": section_names,
        "char_budget": {
            "total_chars": _json_chars(safe_context),
            "sections": {
                record["name"]: record["char_count"] for record in section_records
            },
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
        "prompt_hash": stable_digest(safe_context, length=64),
        "raw_prompt_saved": False,
    }


def _section_record(name: str, value: Any) -> dict[str, Any]:
    return {
        "name": name,
        "char_count": _json_chars(value),
        "content_hash": stable_digest(value, length=16),
        "observation_ids": _section_observation_ids(value),
        "observation_digests": _section_observation_digests(value),
        "omitted": _contains_key_fragment(value, "omitted"),
        "truncated": _contains_key_fragment(value, "truncated"),
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


def _section_observation_ids(value: Any) -> list[str]:
    ids: list[str] = []
    for item in _iter_mappings(value):
        observation_id = item.get("observation_id")
        if observation_id:
            ids.append(str(observation_id))
    return list(dict.fromkeys(ids))


def _section_observation_digests(value: Any) -> list[str]:
    digests: list[str] = []
    for item in _iter_mappings(value):
        digest = item.get("digest") or item.get("payload_digest")
        if digest:
            digests.append(str(digest))
    return list(dict.fromkeys(digests))


def _iter_mappings(value: Any) -> list[Mapping[str, Any]]:
    mappings: list[Mapping[str, Any]] = []
    if isinstance(value, Mapping):
        mappings.append(value)
        for child in value.values():
            mappings.extend(_iter_mappings(child))
    elif isinstance(value, (list, tuple)):
        for child in value:
            mappings.extend(_iter_mappings(child))
    return mappings


def _contains_key_fragment(value: Any, fragment: str) -> bool:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if fragment in str(key):
                return True
            if _contains_key_fragment(child, fragment):
                return True
    elif isinstance(value, (list, tuple)):
        return any(_contains_key_fragment(child, fragment) for child in value)
    return False


def _json_chars(value: Any) -> int:
    return len(json.dumps(value, sort_keys=True, default=str))


__all__ = ["MANIFEST_SCHEMA_VERSION", "build_api_visible_prompt_manifest", "stable_digest"]
