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

from scion.proposal.agentic_models import AGENTIC_CODE_PHASE_CONTEXT_PROFILE
from scion.proposal.agentic_utils import _enum_value, _sanitize_agentic_value
from scion.proposal.prompt_manifest_accounting import (
    _cacheability_summary,
    _json_chars,
    _provider_prompt_hash,
    _system_block_records,
    _system_text_chars,
    _text_digest,
)
from scion.proposal.prompt_manifest_source_visibility import (
    _code_file_visibility_ledger,
    _hypothesis_target_source_visibility_ledger,
    _material_difference_requirement_visibility_ledger,
)
from scion.proposal.prompt_manifest_visibility import (
    VISIBILITY_LEDGER_SCHEMA_VERSION,
    _projection_diagnostics,
    _section_block_family,
    _section_inclusion_reason,
    _section_prompt_block_profile,
    _tool_result_visibility_ledger,
    _visibility_ledger,
)


MANIFEST_SCHEMA_VERSION = "api-visible-prompt-manifest.v3"
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
    provider_prompt_text = _provider_prompt_text(
        rendered_system_blocks,
        rendered_user_prompt,
    )
    observation_prompt_text = _provider_section_text(
        rendered_system_blocks,
        rendered_user_prompt,
        section_names={"agentic_proposal_tool_observations"},
    )
    if not observation_prompt_text:
        observation_prompt_text = provider_prompt_text
    dedicated_source_prompt_text = _provider_section_text(
        rendered_system_blocks,
        rendered_user_prompt,
        section_names={
            "solver_design_full_algorithm_file_reads",
            "approved_target_file_current_content",
            "branch_current_integration_files",
            "required_full_integration_edit_sources",
        },
    )
    system_block_records = _system_block_records(rendered_system_blocks)
    cacheability_summary = _cacheability_summary(
        system_block_records=system_block_records,
        user_prompt_chars=len(rendered_user_prompt) if rendered_available else 0,
    )
    included_observations = [
        _observation_manifest_item(
            observation,
            provider_prompt_text=provider_prompt_text if rendered_available else "",
            observation_prompt_text=(
                observation_prompt_text if rendered_available else ""
            ),
            dedicated_source_prompt_text=(
                dedicated_source_prompt_text if rendered_available else ""
            ),
        )
        for observation in observations
    ]
    code_file_visibility_ledger = _code_file_visibility_ledger(
        safe_context,
        provider_prompt_text=provider_prompt_text if rendered_available else "",
        section_statuses=section_statuses,
        call_kind=call_kind,
    )
    hypothesis_target_source_visibility_ledger = (
        _hypothesis_target_source_visibility_ledger(
            safe_context,
            provider_prompt_text=provider_prompt_text if rendered_available else "",
            included_observations=included_observations,
            section_statuses=section_statuses,
            call_kind=call_kind,
        )
    )
    material_difference_requirement_visibility_ledger = (
        _material_difference_requirement_visibility_ledger(
            safe_context,
            provider_prompt_text=provider_prompt_text if rendered_available else "",
            section_statuses=section_statuses,
            call_kind=call_kind,
        )
    )
    system_chars = _system_text_chars(rendered_system_blocks)
    user_chars = len(rendered_user_prompt) if rendered_available else 0
    total_chars = system_chars + user_chars
    raw_context_digest = stable_digest(safe_context, length=64)
    context_profile = _context_profile_from_safe_context(safe_context)
    visibility_ledger = _visibility_ledger(
        section_records=section_records,
        included_observations=included_observations,
        code_file_visibility_ledger=code_file_visibility_ledger,
        material_difference_requirement_visibility_ledger=(
            material_difference_requirement_visibility_ledger
        ),
    )
    projection_diagnostics = _projection_diagnostics(
        section_records=section_records,
        included_observations=included_observations,
    )
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "artifact_kind": "api_visible_prompt_manifest",
        "session_id": session_id,
        "phase": phase,
        "call_kind": call_kind,
        "call_index": call_index,
        "context_profile": context_profile,
        "context_profile_metadata": safe_context.get("context_profile_metadata"),
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
            "estimated_cacheable_chars": cacheability_summary[
                "estimated_cacheable_chars"
            ],
            "estimated_non_cache_chars": cacheability_summary[
                "estimated_non_cache_chars"
            ],
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
            "cacheability": cacheability_summary,
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
        "tool_result_visibility_ledger": _tool_result_visibility_ledger(
            included_observations
        ),
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
        "code_file_visibility_ledger": code_file_visibility_ledger,
        "hypothesis_target_source_visibility_ledger": (
            hypothesis_target_source_visibility_ledger
        ),
        "material_difference_requirement_visibility_ledger": (
            material_difference_requirement_visibility_ledger
        ),
        "material_difference_requirement_visible": bool(
            material_difference_requirement_visibility_ledger.get("visible")
        ),
        "material_difference_requirement_visible_count": (
            1 if material_difference_requirement_visibility_ledger.get("visible") else 0
        ),
        "material_difference_requirement_source": (
            material_difference_requirement_visibility_ledger.get(
                "requirement_source",
                "",
            )
        ),
        "visibility_ledger": visibility_ledger,
        "visibility_ledger_summary": {
            "schema_version": visibility_ledger["schema_version"],
            "entry_count": visibility_ledger["entry_count"],
            "status_counts": dict(visibility_ledger["status_counts"]),
            "ledger_digest": stable_digest(visibility_ledger, length=16),
        },
        "projection_diagnostics": projection_diagnostics,
        "bounded_tool_projection_count": projection_diagnostics[
            "bounded_tool_projection_count"
        ],
        "prompt_section_truncation_count": projection_diagnostics[
            "prompt_section_truncation_count"
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


def _context_profile_from_safe_context(context: Mapping[str, Any]) -> str:
    profile = str(context.get("context_profile") or "").strip()
    if profile in {"algorithm", "repair", AGENTIC_CODE_PHASE_CONTEXT_PROFILE}:
        return profile
    metadata = context.get("context_profile_metadata")
    if isinstance(metadata, Mapping):
        profile = str(metadata.get("profile") or "").strip()
        if profile in {"algorithm", "repair", AGENTIC_CODE_PHASE_CONTEXT_PROFILE}:
            return profile
    return ""


def _provider_visible_section_records(
    *,
    system_blocks: tuple[Mapping[str, Any], ...] | list[Mapping[str, Any]],
    user_prompt: str,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen_names: dict[str, int] = {}
    for index, block in enumerate(system_blocks, start=1):
        text = str(block.get("text", "")) if isinstance(block, Mapping) else str(block)
        cache_control = block.get("cache_control") if isinstance(block, Mapping) else None
        records.extend(
            _section_records_from_text(
                text,
                prompt_part="system",
                block_index=index,
                seen_names=seen_names,
                cache_control=cache_control,
            )
        )
    records.extend(
        _section_records_from_text(
            user_prompt,
            prompt_part="user",
            block_index=None,
            seen_names=seen_names,
            cache_control=None,
        )
    )
    return records


def _section_records_from_text(
    text: str,
    *,
    prompt_part: str,
    block_index: int | None,
    seen_names: dict[str, int],
    cache_control: Any,
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
                cache_control=cache_control,
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
    cache_control: Any,
) -> dict[str, Any]:
    block_family = _section_block_family(name)
    inclusion_reason = _section_inclusion_reason(name, prompt_part=prompt_part)
    prompt_block_profile = _section_prompt_block_profile(name)
    return {
        "name": name,
        "heading": heading,
        "block_family": block_family,
        "prompt_block_profile": prompt_block_profile,
        "inclusion_reason": inclusion_reason,
        "prompt_part": prompt_part,
        "block_index": block_index,
        "cacheable": bool(prompt_part == "system" and cache_control),
        "cache_control": _sanitize_agentic_value(cache_control) if cache_control else {},
        "char_count": len(text),
        "content_hash": _text_digest(text, length=16),
        "fact_packet_digest": _section_fact_packet_digest_from_text(text),
        "observation_ids": _section_observation_ids_from_text(text),
        "observation_digests": _section_observation_digests_from_text(text),
        "receipt_count": _section_receipt_count_from_text(text),
        "digest_reference_count": _section_digest_reference_count_from_text(text),
        "provenance_reference_count": _section_provenance_reference_count_from_text(
            text
        ),
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
        "block_family": section.get("block_family", ""),
        "prompt_block_profile": section.get("prompt_block_profile", ""),
        "inclusion_reason": section.get("inclusion_reason", ""),
        "prompt_part": section.get("prompt_part", ""),
        "block_index": section.get("block_index"),
        "cacheable": bool(section.get("cacheable")),
        "cache_control": section.get("cache_control") or {},
        "fact_packet_digest": section.get("fact_packet_digest", ""),
        "observation_id_count": len(section.get("observation_ids") or ()),
        "observation_digest_count": len(section.get("observation_digests") or ()),
        "receipt_count": section.get("receipt_count", 0),
        "digest_reference_count": section.get("digest_reference_count", 0),
        "provenance_reference_count": section.get(
            "provenance_reference_count",
            0,
        ),
    }


def _observation_manifest_item(
    observation: Any,
    *,
    provider_prompt_text: str,
    observation_prompt_text: str,
    dedicated_source_prompt_text: str,
) -> dict[str, Any]:
    payload = _sanitize_agentic_value(getattr(observation, "structured_payload", {}))
    payload_digest = stable_digest(payload, length=16)
    provenance = _provenance_payload(payload)
    observation_id = str(getattr(observation, "observation_id", "") or "")
    tool_name = str(getattr(observation, "tool_name", "") or "")
    observation_id_visible = _rendered_contains_literal(
        provider_prompt_text,
        observation_id,
    )
    tool_name_visible = _rendered_contains_literal(provider_prompt_text, tool_name)
    item = {
        "observation_id": observation_id,
        "stable_observation_id": observation_id,
        "tool_name": tool_name,
        "stable_name": tool_name,
        "tool_call_id": getattr(observation, "tool_call_id", ""),
        "observation_type": getattr(observation, "observation_type", ""),
        "payload_digest": payload_digest,
        "payload_hash": payload_digest,
        "source_hash": stable_digest(provenance or payload, length=16),
        "source": provenance.get("source"),
        "status": "error" if bool(getattr(observation, "is_error", False)) else "ok",
        "artifact_ref_present": bool(getattr(observation, "artifact_ref", None)),
        "is_error": bool(getattr(observation, "is_error", False)),
        "failure_code": _enum_value(getattr(observation, "failure_code", None)),
        "exposure_level": _enum_value(getattr(observation, "exposure_level", None)),
        "included_in_prompt_for_call": bool(
            provider_prompt_text
            and (observation_id_visible if observation_id else tool_name_visible)
        ),
        "observation_id_visible_in_rendered_prompt": observation_id_visible,
        "tool_name_visible_in_rendered_prompt": tool_name_visible,
        "payload_truncated": (
            payload.get("truncated") if isinstance(payload, Mapping) else None
        ),
    }
    item.update(
        _observation_visible_text_audit(
            observation_id=observation_id,
            tool_name=tool_name,
            payload_digest=payload_digest,
            provider_prompt_text=provider_prompt_text,
            observation_prompt_text=observation_prompt_text,
        )
    )
    item.update(
        _observation_prompt_inclusion_fields(
            payload,
            provider_prompt_text=provider_prompt_text,
            observation_prompt_text=observation_prompt_text,
            dedicated_source_prompt_text=dedicated_source_prompt_text,
        )
    )
    item["rendered_visibility_flag"] = bool(
        item.get("included_in_prompt_for_call")
        or item.get("visible_text_chars", 0)
        or item.get("content_preview_visible_in_rendered_prompt")
        or item.get("full_content_visible_in_rendered_prompt")
    )
    item["omitted_from_rendered_prompt"] = not bool(item["rendered_visibility_flag"])
    if item["omitted_from_rendered_prompt"]:
        item["omitted_reason"] = "observation_id_tool_name_and_content_not_rendered"
    return item


def _observation_prompt_inclusion_fields(
    payload: Any,
    *,
    provider_prompt_text: str,
    observation_prompt_text: str,
    dedicated_source_prompt_text: str,
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {}
    content_projections = _payload_content_projections(payload)
    content_preview = (
        content_projections[0]["content"] if content_projections else None
    )
    content_preview_chars = (
        len(str(content_preview)) if content_preview is not None else 0
    )
    projection_records = [
        _content_projection_record(
            projection,
            provider_prompt_text=provider_prompt_text,
            observation_prompt_text=observation_prompt_text,
            dedicated_source_prompt_text=dedicated_source_prompt_text,
        )
        for projection in content_projections
    ]
    content_preview_visible_anywhere = any(
        record["visible_anywhere_in_rendered_prompt"]
        for record in projection_records
    )
    content_preview_visible_in_observation = any(
        record["visible_in_observation_section"]
        for record in projection_records
    )
    content_preview_visible_in_dedicated_source = any(
        record["visible_in_dedicated_source_section"]
        for record in projection_records
    )
    full_content_included = any(
        record["full_content_included"] for record in projection_records
    )
    full_content_visible_anywhere = any(
        record["full_content_visible_anywhere_in_rendered_prompt"]
        for record in projection_records
    )
    full_content_visible_in_observation = any(
        record["full_content_visible_in_observation_section"]
        for record in projection_records
    )
    full_content_visible_in_dedicated_source = any(
        record["full_content_visible_in_dedicated_source_section"]
        for record in projection_records
    )
    size_chars = _coerce_int(payload.get("size_chars"))
    max_chars = _coerce_int(payload.get("max_chars"))
    read_receipt_only = (
        not content_projections
        or (
            bool(payload.get("already_observed"))
            and not content_preview_visible_anywhere
        )
    )
    return {
        "file_path": payload.get("file_path"),
        "target_file": payload.get("target_file"),
        "source_provenance": payload.get("source"),
        "symbol": payload.get("symbol"),
        "slice_id": payload.get("slice_id"),
        "readable": payload.get("readable"),
        "truncated": payload.get("truncated"),
        "size_chars": size_chars,
        "max_chars": max_chars,
        "content_preview_chars": content_preview_chars,
        "content_preview_included": bool(content_projections),
        "content_preview_hash": (
            _text_digest(str(content_preview), length=16)
            if content_preview is not None
            else ""
        ),
        "content_preview_visible_in_rendered_prompt": (
            content_preview_visible_anywhere
        ),
        "content_preview_visible_anywhere_in_rendered_prompt": (
            content_preview_visible_anywhere
        ),
        "content_preview_visible_in_dedicated_source_section": (
            content_preview_visible_in_dedicated_source
        ),
        "content_projection_count": len(content_projections),
        "visible_content_projection_count": sum(
            1
            for record in projection_records
            if record["visible_anywhere_in_rendered_prompt"]
        ),
        "content_projections": projection_records,
        "read_receipt_only": read_receipt_only,
        "full_content_included_in_prompt": bool(
            full_content_included and full_content_visible_anywhere
        ),
        "full_content_visible_in_rendered_prompt": bool(
            full_content_visible_anywhere
        ),
        "full_content_visible_anywhere_in_rendered_prompt": bool(
            full_content_visible_anywhere
        ),
        "full_content_visible_in_dedicated_source_section": bool(
            full_content_visible_in_dedicated_source
        ),
        "prompt_visibility_status": _observation_prompt_visibility_status(
            full_content_included=full_content_included,
            content_preview_visible_anywhere=content_preview_visible_anywhere,
            content_preview_visible_in_observation=(
                content_preview_visible_in_observation
            ),
            dedicated_source_visible=content_preview_visible_in_dedicated_source,
            read_receipt_only=read_receipt_only,
        ),
    }


def _payload_content_projections(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    projections: list[dict[str, Any]] = []

    def add_projection(
        *,
        label: str,
        content: Any,
        source: Mapping[str, Any],
        file_path: Any = None,
    ) -> None:
        if content is None:
            return
        text = str(content)
        if not text:
            return
        projections.append(
            {
                "label": label,
                "content": text,
                "file_path": file_path or source.get("file_path"),
                "target_file": source.get("target_file"),
                "symbol": source.get("symbol"),
                "slice_id": source.get("slice_id"),
                "readable": source.get("readable"),
                "truncated": source.get("truncated"),
                "size_chars": _coerce_int(source.get("size_chars")),
                "max_chars": _coerce_int(source.get("max_chars")),
                "already_observed": bool(source.get("already_observed")),
            }
        )

    add_projection(
        label="content_preview",
        content=payload.get("content_preview"),
        source=payload,
    )
    add_projection(
        label="algorithm_slice_content",
        content=payload.get("content"),
        source=payload,
    )
    for key in ("current_artifact", "target_artifact"):
        value = payload.get(key)
        if isinstance(value, Mapping):
            add_projection(
                label=f"{key}.content_preview",
                content=value.get("content_preview"),
                source=value,
                file_path=value.get("file_path") or payload.get("target_file"),
            )
    support_artifacts = payload.get("support_artifacts")
    if isinstance(support_artifacts, list):
        for index, artifact in enumerate(support_artifacts):
            if not isinstance(artifact, Mapping):
                continue
            add_projection(
                label=f"support_artifacts[{index}].content_preview",
                content=artifact.get("content_preview"),
                source=artifact,
            )
    return projections


def _content_projection_record(
    projection: Mapping[str, Any],
    *,
    provider_prompt_text: str,
    observation_prompt_text: str,
    dedicated_source_prompt_text: str,
) -> dict[str, Any]:
    content = str(projection.get("content") or "")
    visible_anywhere = _rendered_contains_text(provider_prompt_text, content)
    visible_observation = _rendered_contains_text(observation_prompt_text, content)
    visible_dedicated = _rendered_contains_text(
        dedicated_source_prompt_text,
        content,
    )
    full_content_included = _projection_full_content_included(projection, content)
    return {
        "label": projection.get("label"),
        "file_path": projection.get("file_path"),
        "target_file": projection.get("target_file"),
        "symbol": projection.get("symbol"),
        "slice_id": projection.get("slice_id"),
        "content_chars": len(content),
        "content_hash": _text_digest(content, length=16),
        "visible_anywhere_in_rendered_prompt": visible_anywhere,
        "visible_in_observation_section": visible_observation,
        "visible_in_dedicated_source_section": visible_dedicated,
        "full_content_included": full_content_included,
        "full_content_visible_anywhere_in_rendered_prompt": bool(
            full_content_included and visible_anywhere
        ),
        "full_content_visible_in_observation_section": bool(
            full_content_included and visible_observation
        ),
        "full_content_visible_in_dedicated_source_section": bool(
            full_content_included and visible_dedicated
        ),
    }


def _projection_full_content_included(
    projection: Mapping[str, Any],
    content: str,
) -> bool:
    if projection.get("truncated") is True:
        return False
    size_chars = _coerce_int(projection.get("size_chars"))
    max_chars = _coerce_int(projection.get("max_chars"))
    content_chars = len(content)
    if size_chars is not None:
        return content_chars >= max(0, size_chars - 1)
    if max_chars is not None:
        return content_chars >= max(0, max_chars - 1)
    if projection.get("label") == "algorithm_slice_content":
        return True
    return bool(projection.get("readable") is True and not projection.get("already_observed"))


def _provider_prompt_text(
    system_blocks: tuple[Mapping[str, Any], ...] | list[Mapping[str, Any]],
    user_prompt: str,
) -> str:
    system_text = "\n".join(
        str(block.get("text", "")) if isinstance(block, Mapping) else str(block)
        for block in system_blocks
    )
    return system_text + "\n" + str(user_prompt or "")


def _provider_section_text(
    system_blocks: tuple[Mapping[str, Any], ...] | list[Mapping[str, Any]],
    user_prompt: str,
    *,
    section_names: set[str],
) -> str:
    chunks: list[str] = []
    for block in system_blocks:
        text = str(block.get("text", "")) if isinstance(block, Mapping) else str(block)
        chunks.extend(_matching_section_chunks(text, section_names=section_names))
    chunks.extend(_matching_section_chunks(str(user_prompt or ""), section_names=section_names))
    return "\n".join(chunks)


def _matching_section_chunks(text: str, *, section_names: set[str]) -> list[str]:
    if not text:
        return []
    matches = list(_SECTION_HEADING.finditer(text))
    if not matches:
        return []
    chunks: list[str] = []
    for offset, match in enumerate(matches):
        heading_name = _section_name(match.group(1))
        start = match.start()
        end = matches[offset + 1].start() if offset + 1 < len(matches) else len(text)
        if heading_name in section_names:
            chunks.append(text[start:end])
    return chunks


def _rendered_contains_literal(rendered_prompt: str, value: Any) -> bool:
    text = str(value or "")
    return bool(text and text in rendered_prompt)


def _rendered_contains_text(rendered_prompt: str, value: Any) -> bool:
    if value is None:
        return False
    text = str(value)
    if not text:
        return False
    if text in rendered_prompt:
        return True
    encoded = json.dumps(text)
    if encoded in rendered_prompt:
        return True
    if len(encoded) >= 2 and encoded[1:-1] in rendered_prompt:
        return True
    return False


def _observation_visible_text_audit(
    *,
    observation_id: str,
    tool_name: str,
    payload_digest: str,
    provider_prompt_text: str,
    observation_prompt_text: str,
) -> dict[str, Any]:
    anchors = tuple(
        item
        for item in (observation_id, payload_digest, tool_name)
        if str(item or "").strip()
    )
    for source_name, text in (
        ("agentic_proposal_tool_observations", observation_prompt_text),
        ("provider_visible_prompt", provider_prompt_text),
    ):
        source_text = str(text or "")
        if not source_text:
            continue
        if not any(anchor in source_text for anchor in anchors):
            continue
        visible_text = _visible_observation_window(source_text, anchors)
        return {
            "visible_text_chars": len(visible_text),
            "visible_text_hash": _text_digest(visible_text, length=16),
            "rendered_visibility_source": source_name,
            "visible_text_windowed": len(visible_text) < len(source_text),
        }
    return {
        "visible_text_chars": 0,
        "visible_text_hash": "",
        "rendered_visibility_source": "",
        "visible_text_windowed": False,
    }


def _visible_observation_window(text: str, anchors: tuple[str, ...]) -> str:
    indexes = [text.find(anchor) for anchor in anchors if anchor and anchor in text]
    if not indexes:
        return ""
    start = max(0, min(indexes) - 1600)
    end = min(len(text), max(indexes) + 2400)
    return text[start:end]


def _observation_prompt_visibility_status(
    *,
    full_content_included: bool,
    content_preview_visible_anywhere: bool,
    content_preview_visible_in_observation: bool,
    dedicated_source_visible: bool,
    read_receipt_only: bool,
) -> str:
    if read_receipt_only:
        return "read_receipt_only_or_no_content"
    if full_content_included and content_preview_visible_in_observation:
        return "full_content_visible_in_rendered_prompt"
    if full_content_included and dedicated_source_visible:
        return "full_content_visible_in_dedicated_source_section"
    if full_content_included and content_preview_visible_anywhere:
        return "full_content_visible_in_rendered_prompt"
    if full_content_included:
        return "full_content_payload_not_visible_in_rendered_prompt"
    if content_preview_visible_anywhere:
        return "partial_content_visible_in_rendered_prompt"
    return "content_not_visible_in_rendered_prompt"


def _coerce_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except Exception:
        return None
    return parsed if parsed >= 0 else None


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


def _section_receipt_count_from_text(text: str) -> int:
    return len(
        re.findall(
            r"\b(?:read_receipt|source_policy_receipt|receipt_rule)\b",
            text,
        )
    )


def _section_digest_reference_count_from_text(text: str) -> int:
    return len(
        re.findall(
            r"\b(?:digest|content_digest|snapshot_digest|payload_digest)\b",
            text,
        )
    )


def _section_provenance_reference_count_from_text(text: str) -> int:
    return len(
        re.findall(
            r"\b(?:provenance|source_policy|subject_id|tool_name|snapshot_digest)\b",
            text,
        )
    )


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
        return bool(
            "<truncated" in lowered
            or "truncated agentic context" in lowered
            or "truncated for compact" in lowered
        )
    if marker == "omitted":
        return "<omitted" in lowered or "... <omitted" in lowered
    return marker.lower() in lowered


__all__ = [
    "MANIFEST_SCHEMA_VERSION",
    "VISIBILITY_LEDGER_SCHEMA_VERSION",
    "build_api_visible_prompt_manifest",
    "stable_digest",
]
