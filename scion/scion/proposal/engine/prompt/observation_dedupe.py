"""Deduplication helpers for agentic proposal tool observations."""

from __future__ import annotations

from typing import Any

from scion.proposal.engine.prompt.formatting import _drop_empty
from scion.proposal.engine.prompt.solver_context_receipts import (
    _canonical_full_source_digest,
    _compact_static_solver_context_payload,
    _fact_ids,
    _fact_packet_digest,
    _is_solver_design_surface_payload,
    _noncanonical_source_digest_hash,
    _snapshot_digest,
)
from scion.proposal.engine.prompt.tool_receipts import (
    _PREVIEW_TOOL_NAMES,
    _compact_list_surfaces_payload,
    _compact_preview_tool_payload,
    _compact_read_problem_payload,
    _compact_surface_payload,
)


def _dedupe_tool_observations(
    observations: Any,
    *,
    active_algorithm_facts: Any,
    resume_context: Any,
    full_read_observation_ids: set[str] | None = None,
) -> Any:
    if not isinstance(observations, list):
        return observations
    active_digest = _fact_packet_digest(active_algorithm_facts)
    resume_active_digest = _fact_packet_digest(resume_context)
    full_read_observation_ids = full_read_observation_ids or set()
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
                tool_name=str(item.get("tool_name") or ""),
                observation_summary=str(item.get("summary") or ""),
                observation_failure_code=str(item.get("failure_code") or ""),
                observation_repair_hint=str(item.get("repair_hint") or ""),
                active_digest=active_digest,
                resume_active_digest=resume_active_digest,
                has_full_algorithm_reads=bool(full_read_observation_ids),
                omit_full_algorithm_content=(
                    str(item.get("observation_id") or "")
                    in full_read_observation_ids
                ),
            )
            item["structured_payload"] = payload
        compact.append(item)
    return compact


def _dedupe_observation_payload(
    payload: dict[str, Any],
    *,
    tool_name: str,
    observation_summary: str = "",
    observation_failure_code: str = "",
    observation_repair_hint: str = "",
    active_digest: str,
    resume_active_digest: str,
    has_full_algorithm_reads: bool = False,
    omit_full_algorithm_content: bool = False,
) -> dict[str, Any]:
    compact = dict(payload)
    if omit_full_algorithm_content and "content_preview" in compact:
        content_preview_ref = _drop_empty(
            {
                "section": "solver_design_full_algorithm_file_reads",
                "file_path": compact.get("file_path"),
                "content_preview_chars": len(str(compact.get("content_preview") or "")),
                "full_content_included_in_prompt_section": True,
            }
        )
        return _drop_empty(
            {
                "active": compact.get("active"),
                "coverage_status": "full",
                "content_preview_chars": len(
                    str(compact.get("content_preview") or "")
                ),
                "content_preview_ref": content_preview_ref,
                "content_preview_omitted_from_generic_observations": True,
                "digest": compact.get("digest"),
                "file_path": compact.get("file_path"),
                "max_chars": compact.get("max_chars"),
                "module": compact.get("module"),
                "readable": compact.get("readable"),
                "role": compact.get("role"),
                "sha256": compact.get("sha256"),
                "size_chars": compact.get("size_chars"),
                "source": compact.get("source"),
                "source_digest": _canonical_full_source_digest(compact),
                "source_digest_hash": _noncanonical_source_digest_hash(compact)
                or compact.get("digest"),
                "truncated": compact.get("truncated"),
            }
        )
    if active_digest and tool_name in {
        "context.read_active_solver_design",
        "context.read_solver_call_graph",
        "context.list_algorithm_files",
    }:
        return _compact_static_solver_context_payload(
            tool_name,
            compact,
            active_digest=active_digest,
            resume_active_digest=resume_active_digest,
        )
    if tool_name == "context.list_surfaces":
        return _compact_list_surfaces_payload(compact)
    if tool_name == "context.read_problem":
        return _compact_read_problem_payload(compact)
    if (
        active_digest
        and has_full_algorithm_reads
        and tool_name == "context.read_surface"
        and _is_solver_design_surface_payload(compact)
    ):
        return _compact_surface_payload(compact, active_digest=active_digest)
    if tool_name in _PREVIEW_TOOL_NAMES:
        return _compact_preview_tool_payload(
            tool_name=tool_name,
            payload=compact,
            observation_summary=observation_summary,
            observation_failure_code=observation_failure_code,
            observation_repair_hint=observation_repair_hint,
        )
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
