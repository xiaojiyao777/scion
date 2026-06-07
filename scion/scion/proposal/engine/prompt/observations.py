"""Model-facing projections for agentic proposal tool observations."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from scion.proposal.engine.prompt.formatting import (
    _bounded_list,
    _drop_empty,
    _limit_text,
    _stable_short_digest,
)
from scion.proposal.engine.prompt.solver_context_receipts import (
    _algorithm_file_paths,
    _canonical_full_source_digest,
    _coerce_nonnegative_int,
    _compact_source_digest,
    _compact_static_solver_context_payload,
    _fact_ids,
    _fact_packet_digest,
    _is_full_algorithm_file_payload,
    _is_solver_design_surface_payload,
    _looks_like_sha256,
    _noncanonical_source_digest_hash,
    _same_fact_packet,
    _snapshot_digest,
    _solver_design_full_algorithm_file_reads,
)
from scion.proposal.engine.prompt.solver_map_receipts import (
    _active_solver_map_receipts_projection,
    _compact_integration_point,
    _compact_operator_ref,
    _compact_receipt,
    _compact_registry_ref,
    _compact_slice_ref,
    _compact_source_policy,
    _len_if_list,
    _unique_strings,
)
from scion.proposal.engine.prompt.tool_receipts import (
    _PREVIEW_TOOL_NAMES,
    _compact_list_surfaces_payload,
    _compact_preview_tool_payload,
    _compact_read_problem_payload,
    _compact_surface_payload,
    _surface_identity,
)
_ResearchDiagnosisProjection = Callable[..., Any]


def _tool_observations_model_projection(
    observations: Any,
    *,
    code_phase: bool,
    research_diagnosis_projection: _ResearchDiagnosisProjection | None = None,
) -> Any:
    if not isinstance(observations, list):
        return observations
    max_items = 40 if code_phase else 80
    compact_items = [
        _compact_tool_observation_for_model(
            item,
            research_diagnosis_projection=research_diagnosis_projection,
        )
        for item in observations
    ]
    compact_items = [item for item in compact_items if item]
    shown = compact_items[-max_items:]
    return _drop_empty(
        {
            "projection_kind": "agentic_tool_observations_projection.v1",
            "observation_count": len(compact_items),
            "shown_latest_count": len(shown),
            "omitted_older_count": max(0, len(compact_items) - len(shown)),
            "tool_counts": _tool_counts(compact_items),
            "file_read_receipts": _file_read_receipts(compact_items, limit=24),
            "preview_receipts": _preview_receipts(compact_items, limit=12),
            "observations": shown,
            "projection_note": (
                "This is a bounded model-facing projection. Exact source content "
                "for full reads appears in dedicated source sections; older raw "
                "observations remain in the audit ledger and should be queried "
                "through tools or read receipts when needed."
            ),
        }
    )


def _compact_tool_observation_for_model(
    value: Any,
    *,
    research_diagnosis_projection: _ResearchDiagnosisProjection | None = None,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {"value": _limit_text(str(value), 500)}
    payload = value.get("structured_payload")
    compact_payload = (
        _compact_payload_for_model(
            payload,
            research_diagnosis_projection=research_diagnosis_projection,
        )
        if isinstance(payload, dict)
        else payload
    )
    return _drop_empty(
        {
            "observation_id": value.get("observation_id"),
            "tool_name": value.get("tool_name"),
            "phase": value.get("phase"),
            "proposal_phase": value.get("proposal_phase"),
            "status": value.get("status"),
            "failure_code": value.get("failure_code"),
            "summary": _limit_text(str(value.get("summary") or ""), 700),
            "repair_hint": _limit_text(str(value.get("repair_hint") or ""), 700),
            "file_path": value.get("file_path"),
            "coverage": value.get("coverage"),
            "digest": value.get("digest"),
            "truncated": value.get("truncated"),
            "structured_payload": compact_payload,
        }
    )


def _compact_payload_for_model(
    payload: dict[str, Any],
    *,
    research_diagnosis_projection: _ResearchDiagnosisProjection | None = None,
) -> dict[str, Any]:
    if payload.get("projection_kind"):
        return payload
    keys_to_keep = (
        "schema_version",
        "projection_kind",
        "tool_name",
        "surface",
        "surface_id",
        "selected_surface",
        "problem_id",
        "problem_spec_hash",
        "file_path",
        "module",
        "coverage_status",
        "max_chars",
        "size_chars",
        "truncated",
        "digest",
        "sha256",
        "passed",
        "failure_code",
        "reason",
        "summary",
        "research_diagnosis",
        "runtime_feedback",
        "screening_feedback",
        "read_receipts",
        "read_receipt",
        "available",
        "subject_id",
        "snapshot_digest",
        "registry_id",
        "slice_id",
        "owner_file",
        "owner_symbol",
        "registry_kind",
        "symbols",
        "slice_kind",
        "line_start",
        "line_end",
        "content_digest",
        "source_policy_receipt",
        "active_algorithm_facts_ref",
        "content_preview_ref",
        "content_preview_omitted_from_generic_observations",
        "dedicated_context_sections",
    )
    compact = {key: payload.get(key) for key in keys_to_keep if key in payload}
    if "research_diagnosis" in compact and isinstance(
        compact["research_diagnosis"],
        dict,
    ) and research_diagnosis_projection is not None:
        compact["research_diagnosis"] = research_diagnosis_projection(
            compact["research_diagnosis"],
            code_phase=False,
        )
    for key in ("runtime_feedback", "screening_feedback", "read_receipts"):
        if isinstance(compact.get(key), list):
            compact[key] = _bounded_list(compact[key], 16)
    if not compact:
        compact = {
            "payload_digest": _stable_short_digest(payload),
            "payload_keys": list(payload)[:24],
        }
    else:
        compact["payload_digest"] = _stable_short_digest(payload)
    return _drop_empty(compact)


def _tool_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        tool_name = str(item.get("tool_name") or "unknown")
        counts[tool_name] = counts.get(tool_name, 0) + 1
    return counts


def _file_read_receipts(items: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    receipts: list[dict[str, Any]] = []
    for item in items:
        tool_name = str(item.get("tool_name") or "")
        if tool_name not in {
            "context.read_algorithm_file",
            "context.list_algorithm_files",
            "context.read_surface",
            "context.read_active_solver_map",
            "context.read_operator_registry",
            "context.read_algorithm_slice",
            "context.read_active_solver_design",
            "context.read_solver_call_graph",
        }:
            continue
        receipts.append(
            _drop_empty(
                {
                    "tool_name": tool_name,
                    "file_path": item.get("file_path"),
                    "registry_id": _payload_value(item, "registry_id"),
                    "slice_id": _payload_value(item, "slice_id"),
                    "target_id": _payload_receipt_value(item, "target_id"),
                    "coverage": item.get("coverage"),
                    "digest": item.get("digest"),
                    "summary": item.get("summary"),
                }
            )
        )
    return receipts[-limit:]


def _payload_value(item: dict[str, Any], key: str) -> Any:
    payload = item.get("structured_payload")
    if isinstance(payload, dict):
        return payload.get(key)
    return None


def _payload_receipt_value(item: dict[str, Any], key: str) -> Any:
    payload = item.get("structured_payload")
    if not isinstance(payload, dict):
        return None
    receipt = payload.get("read_receipt")
    if isinstance(receipt, dict):
        return receipt.get(key)
    return None


def _preview_receipts(items: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    receipts: list[dict[str, Any]] = []
    for item in items:
        if str(item.get("tool_name") or "") not in _PREVIEW_TOOL_NAMES:
            continue
        payload = item.get("structured_payload")
        payload_dict = payload if isinstance(payload, dict) else {}
        receipts.append(
            _drop_empty(
                {
                    "tool_name": item.get("tool_name"),
                    "status": item.get("status"),
                    "failure_code": item.get("failure_code")
                    or payload_dict.get("failure_code"),
                    "passed": payload_dict.get("passed"),
                    "summary": item.get("summary"),
                    "repair_hint": item.get("repair_hint"),
                }
            )
        )
    return receipts[-limit:]


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
