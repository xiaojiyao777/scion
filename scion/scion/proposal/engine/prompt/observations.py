"""Model-facing projections for agentic proposal tool observations."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from typing import Any

from scion.proposal.engine.prompt.formatting import (
    _bounded_list,
    _drop_empty,
    _limit_text,
    _stable_short_digest,
)

_PREVIEW_TOOL_NAMES = frozenset(
    {
        "proposal.schema_preview",
        "proposal.target_permission_preview",
        "proposal.contract_preview",
        "proposal.algorithm_smoke",
    }
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


def _active_solver_map_receipts_projection(observations: Any) -> dict[str, Any]:
    if not isinstance(observations, list):
        return {}
    map_reads: list[dict[str, Any]] = []
    registry_reads: list[dict[str, Any]] = []
    slice_reads: list[dict[str, Any]] = []
    already_visible_source: list[dict[str, Any]] = []
    for item in observations:
        if not isinstance(item, dict):
            continue
        tool_name = str(item.get("tool_name") or "")
        payload = item.get("structured_payload")
        if not isinstance(payload, dict):
            continue
        if tool_name == "context.read_active_solver_map":
            registry_refs = _bounded_list(payload.get("operator_registries"), 16)
            slice_refs = _bounded_list(payload.get("algorithm_slices"), 24)
            map_reads.append(
                _drop_empty(
                    {
                        "observation_id": item.get("observation_id"),
                        "available": payload.get("available"),
                        "surface": payload.get("surface"),
                        "subject_id": payload.get("subject_id"),
                        "snapshot_digest": payload.get("snapshot_digest"),
                        "read_receipt": _compact_receipt(payload.get("read_receipt")),
                        "available_registry_ids": [
                            str(ref.get("registry_id"))
                            for ref in registry_refs
                            if isinstance(ref, dict) and ref.get("registry_id")
                        ],
                        "available_slice_ids": [
                            str(ref.get("slice_id"))
                            for ref in slice_refs
                            if isinstance(ref, dict) and ref.get("slice_id")
                        ],
                        "operator_registries": [
                            _compact_registry_ref(ref)
                            for ref in registry_refs
                            if isinstance(ref, dict)
                        ],
                        "algorithm_slices": [
                            _compact_slice_ref(ref)
                            for ref in slice_refs
                            if isinstance(ref, dict)
                        ],
                        "source_policy": _compact_source_policy(
                            payload.get("source_policy")
                        ),
                    }
                )
            )
        elif tool_name == "context.read_operator_registry":
            registry_reads.append(
                _drop_empty(
                    {
                        "observation_id": item.get("observation_id"),
                        "available": payload.get("available"),
                        "registry_id": payload.get("registry_id"),
                        "surface": payload.get("surface"),
                        "subject_id": payload.get("subject_id"),
                        "snapshot_digest": payload.get("snapshot_digest"),
                        "owner_file": payload.get("owner_file"),
                        "owner_symbol": payload.get("owner_symbol"),
                        "registry_kind": payload.get("registry_kind"),
                        "operator_count": _len_if_list(payload.get("operators")),
                        "operators": [
                            _compact_operator_ref(ref)
                            for ref in _bounded_list(payload.get("operators"), 16)
                            if isinstance(ref, dict)
                        ],
                        "integration_points": [
                            _compact_integration_point(ref)
                            for ref in _bounded_list(
                                payload.get("integration_points"),
                                8,
                            )
                            if isinstance(ref, dict)
                        ],
                        "read_receipt": _compact_receipt(payload.get("read_receipt")),
                    }
                )
            )
        elif tool_name == "context.read_algorithm_slice":
            content = str(payload.get("content") or "")
            slice_reads.append(
                _drop_empty(
                    {
                        "observation_id": item.get("observation_id"),
                        "available": payload.get("available"),
                        "slice_id": payload.get("slice_id"),
                        "surface": payload.get("surface"),
                        "subject_id": payload.get("subject_id"),
                        "snapshot_digest": payload.get("snapshot_digest"),
                        "file_path": payload.get("file_path"),
                        "symbols": payload.get("symbols"),
                        "slice_kind": payload.get("slice_kind"),
                        "line_start": payload.get("line_start"),
                        "line_end": payload.get("line_end"),
                        "token_estimate": payload.get("token_estimate"),
                        "content_digest": payload.get("content_digest"),
                        "content_preview": _limit_text(content, 2200),
                        "content_chars": len(content) if content else None,
                        "truncated": payload.get("truncated"),
                        "max_chars": payload.get("max_chars"),
                        "why_visible": _limit_text(
                            str(payload.get("why_visible") or ""),
                            500,
                        ),
                        "source_policy_receipt": _compact_receipt(
                            payload.get("source_policy_receipt")
                        ),
                        "read_receipt": _compact_receipt(payload.get("read_receipt")),
                    }
                )
            )
            already_visible_source.append(
                _drop_empty(
                    {
                        "tool_name": tool_name,
                        "slice_id": payload.get("slice_id"),
                        "file_path": payload.get("file_path"),
                        "symbols": payload.get("symbols"),
                        "line_start": payload.get("line_start"),
                        "line_end": payload.get("line_end"),
                        "content_digest": payload.get("content_digest"),
                        "visibility": "bounded_algorithm_slice",
                    }
                )
            )
        elif tool_name == "context.read_algorithm_file":
            file_path = payload.get("file_path")
            if file_path:
                already_visible_source.append(
                    _drop_empty(
                        {
                            "tool_name": tool_name,
                            "file_path": file_path,
                            "coverage": (
                                "full"
                                if payload.get("truncated") is False
                                else "truncated"
                            ),
                            "digest": payload.get("digest")
                            or payload.get("sha256"),
                            "max_chars": payload.get("max_chars"),
                        }
                    )
                )
    if not (map_reads or registry_reads or slice_reads):
        return {}
    return _drop_empty(
        {
            "projection_kind": "active_solver_map_receipts.v1",
            "map_reads": map_reads[-4:],
            "registry_reads": registry_reads[-8:],
            "slice_reads": slice_reads[-8:],
            "available_registry_ids": _unique_strings(
                registry_id
                for read in map_reads
                for registry_id in read.get("available_registry_ids", ())
            ),
            "available_slice_ids": _unique_strings(
                slice_id
                for read in map_reads
                for slice_id in read.get("available_slice_ids", ())
            ),
            "already_visible_source": already_visible_source[-16:],
            "receipt_rule": (
                "Map/registry/slice receipts identify provider-approved source "
                "handles. Exact full-file source remains separate and should be "
                "requested only when a bounded slice is insufficient."
            ),
        }
    )


def _compact_receipt(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return _drop_empty(
        {
            "tool_name": value.get("tool_name"),
            "surface": value.get("surface"),
            "subject_id": value.get("subject_id"),
            "target_id": value.get("target_id"),
            "snapshot_digest": value.get("snapshot_digest"),
            "digest": value.get("digest"),
            "content_digest": value.get("content_digest"),
            "available": value.get("available"),
            "allowed": value.get("allowed"),
            "reason": _limit_text(str(value.get("reason") or ""), 300),
            "remaining_budget": value.get("remaining_budget"),
        }
    )


def _compact_registry_ref(value: dict[str, Any]) -> dict[str, Any]:
    return _drop_empty(
        {
            "registry_id": value.get("registry_id"),
            "owner_file": value.get("owner_file"),
            "owner_symbol": value.get("owner_symbol"),
            "registry_kind": value.get("registry_kind"),
            "operator_count": _len_if_list(value.get("operators")),
        }
    )


def _compact_operator_ref(value: dict[str, Any]) -> dict[str, Any]:
    return _drop_empty(
        {
            "id": value.get("id"),
            "symbol": value.get("symbol"),
            "file_path": value.get("file_path"),
            "order": value.get("order"),
            "role": value.get("role"),
            "summary": _limit_text(str(value.get("summary") or ""), 300),
            "mechanism_tags": _bounded_list(value.get("mechanism_tags"), 6),
            "telemetry_ids": _bounded_list(value.get("telemetry_ids"), 6),
        }
    )


def _compact_integration_point(value: dict[str, Any]) -> dict[str, Any]:
    return _drop_empty(
        {
            "file_path": value.get("file_path"),
            "symbol": value.get("symbol"),
            "insert_policy": _limit_text(str(value.get("insert_policy") or ""), 300),
            "required_telemetry_pattern": _limit_text(
                str(value.get("required_telemetry_pattern") or ""),
                300,
            ),
        }
    )


def _compact_slice_ref(value: dict[str, Any]) -> dict[str, Any]:
    return _drop_empty(
        {
            "slice_id": value.get("slice_id"),
            "file_path": value.get("file_path"),
            "symbols": value.get("symbols"),
            "purpose": _limit_text(str(value.get("purpose") or ""), 360),
            "exposure_level": value.get("exposure_level"),
            "source_digest": value.get("source_digest"),
            "token_estimate": value.get("token_estimate"),
            "redaction_reason": _limit_text(
                str(value.get("redaction_reason") or ""),
                240,
            ),
        }
    )


def _compact_source_policy(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return _drop_empty(
        {
            "max_total_tokens": value.get("max_total_tokens"),
            "max_body_tokens_per_tool_call": value.get(
                "max_body_tokens_per_tool_call"
            ),
            "allowed_files_digest": value.get("allowed_files_digest"),
            "redaction_policy": value.get("redaction_policy"),
        }
    )


def _len_if_list(value: Any) -> int | None:
    if isinstance(value, (list, tuple)):
        return len(value)
    return None


def _unique_strings(values: Any) -> list[str]:
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in result:
            result.append(text)
    return result


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


def _compact_preview_tool_payload(
    *,
    tool_name: str,
    payload: dict[str, Any],
    observation_summary: str,
    observation_failure_code: str,
    observation_repair_hint: str,
) -> dict[str, Any]:
    passed = _preview_passed(payload)
    failed_checks = _preview_failed_checks(payload)
    failure_reason = _preview_failure_reason(payload)
    compact = {
        "projection_kind": "preview_tool_receipt.v1",
        "tool_payload_omitted_from_generic_observations": True,
        "tool_name": tool_name,
        "passed": passed,
        "failure_code": observation_failure_code or payload.get("failure_code"),
        "summary": _limit_text(observation_summary, 360),
        "failure_reason": _limit_text(failure_reason, 700),
        "failed_checks": failed_checks[:10],
        "repair_templates": _preview_repair_templates(payload),
        "repair_hint": _limit_text(
            observation_repair_hint or str(payload.get("repair_hint") or ""),
            700,
        ),
        "payload_digest": _stable_short_digest(payload),
        "payload_sections_present": [
            str(key)
            for key in payload
            if key not in {"hypothesis_object", "patch_object"}
        ][:16],
        "requested": _compact_preview_requested(payload),
        "permission": _compact_preview_permission(payload),
        "workspace_materialized": payload.get("workspace_materialized"),
        "static_only": payload.get("static_only"),
        "dedicated_feedback_section": _preview_feedback_section(tool_name),
        "audit_ref": (
            "Full preview payload is omitted from the agent-facing observation; "
            "use the raw observation ledger/session artifact for audit detail."
        ),
    }
    return _drop_empty(compact)


def _compact_list_surfaces_payload(payload: dict[str, Any]) -> dict[str, Any]:
    surfaces = payload.get("surfaces")
    compact_surfaces: list[dict[str, Any]] = []
    if isinstance(surfaces, list):
        for surface in surfaces[:16]:
            if not isinstance(surface, dict):
                continue
            targets = surface.get("targets") if isinstance(surface.get("targets"), dict) else {}
            compact_surfaces.append(
                _drop_empty(
                    {
                        "name": surface.get("name"),
                        "kind": surface.get("kind"),
                        "target_files": surface.get("target_files")
                        or targets.get("files"),
                        "allowed_actions": targets.get("allowed_actions"),
                    }
                )
            )
    return _drop_empty(
        {
            "projection_kind": "surface_list_receipt.v1",
            "tool_payload_omitted_from_generic_observations": True,
            "surface_count": payload.get("surface_count")
            or len(compact_surfaces),
            "total_declared_surface_count": payload.get(
                "total_declared_surface_count"
            ),
            "surfaces": compact_surfaces,
            "forced_surface_constraint": payload.get("forced_surface_constraint"),
            "active_problem_boundary_constraint": payload.get(
                "active_problem_boundary_constraint"
            ),
            "payload_digest": _stable_short_digest(payload),
        }
    )


def _compact_read_problem_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return _drop_empty(
        {
            "projection_kind": "problem_context_receipt.v1",
            "tool_payload_omitted_from_generic_observations": True,
            "problem_id": payload.get("problem_id"),
            "problem_spec_hash": payload.get("problem_spec_hash"),
            "summary": _limit_text(str(payload.get("summary") or ""), 700),
            "problem_object_chars": len(str(payload.get("problem_object") or "")),
            "solver_mechanics_chars": len(str(payload.get("solver_mechanics") or "")),
            "problem_object_omitted_from_generic_observations": bool(
                payload.get("problem_object")
            ),
            "solver_mechanics_omitted_from_generic_observations": bool(
                payload.get("solver_mechanics")
            ),
            "dedicated_context_sections": [
                "problem_summary",
                "problem_object",
                "research_surfaces",
            ],
            "payload_digest": _stable_short_digest(payload),
        }
    )


def _compact_surface_payload(
    payload: dict[str, Any],
    *,
    active_digest: str,
) -> dict[str, Any]:
    surface = payload.get("surface")
    surface_payload = surface if isinstance(surface, dict) else {}
    current_artifact = _artifact_receipt(payload.get("current_artifact"))
    support_artifacts = [
        artifact
        for artifact in (
            _artifact_receipt(item)
            for item in _bounded_list(payload.get("support_artifacts"), 64)
        )
        if artifact
    ]
    readable_support_count = sum(
        1 for artifact in support_artifacts if artifact.get("readable") is True
    )
    unreadable_support_count = sum(
        1 for artifact in support_artifacts if artifact.get("readable") is False
    )
    compact: dict[str, Any] = {
        "projection_kind": "surface_interface_receipt.v1",
        "tool_payload_omitted_from_generic_observations": True,
        "dedicated_context_sections": [
            "active_algorithm_facts",
            "solver_design_full_algorithm_file_reads",
        ],
        "surface": _drop_empty(
            {
                "id": surface_payload.get("id") or payload.get("surface_id"),
                "name": surface_payload.get("name") or payload.get("name"),
                "kind": surface_payload.get("kind") or payload.get("kind"),
                "section": surface_payload.get("section") or payload.get("section"),
                "selected": surface_payload.get("selected") or payload.get("selected"),
                "active": surface_payload.get("active") or payload.get("active"),
            }
        ),
        "target_file": payload.get("target_file")
        or current_artifact.get("file_path"),
        "declared_targets": payload.get("declared_targets"),
        "surface_digest": _stable_short_digest(
            _drop_empty(
                {
                    "surface": _surface_identity(payload),
                    "surface_contract": payload.get("surface_contract"),
                    "declared_targets": payload.get("declared_targets"),
                    "target_file": payload.get("target_file"),
                }
            )
        ),
        "provenance": payload.get("provenance"),
        "active_algorithm_facts_ref": {
            "fact_packet_digest": active_digest,
            "omitted_from_raw_observation": (
                "deduplicated; see Active Algorithm Facts and full algorithm "
                "file read sections"
            ),
        },
        "current_artifact": _drop_empty(
            {
                "file_path": current_artifact.get("file_path"),
                "readable": current_artifact.get("readable"),
                "source": current_artifact.get("source"),
            }
        ),
        "support_artifact_count": len(support_artifacts),
        "support_artifact_paths": [
            artifact["file_path"]
            for artifact in support_artifacts
            if artifact.get("file_path")
        ],
        "support_artifact_readable_count": readable_support_count,
        "support_artifact_unreadable_count": unreadable_support_count,
        "source_pointer": (
            "Full solver-design source and active facts are projected in "
            "dedicated cacheable prompt sections; artifact previews and API "
            "summaries are omitted from generic tool observations."
        ),
    }
    contract = payload.get("surface_contract")
    if isinstance(contract, dict):
        compact["surface_contract"] = _drop_empty(
            {
                "schema_version": contract.get("schema_version"),
                "detail": contract.get("detail"),
                "section": contract.get("section"),
                "available_sections": contract.get("available_sections"),
                "target_preview": _target_preview_receipt(
                    contract.get("target_preview")
                ),
            }
        )
    return _drop_empty(compact)


def _artifact_receipt(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {
        key: item
        for key, item in {
            "file_path": value.get("file_path") or value.get("path"),
            "readable": value.get("readable"),
            "source": value.get("source"),
            "read_receipt": "content/API summary omitted; see dedicated source sections",
        }.items()
        if item not in (None, "", (), [], {})
    }


def _target_preview_receipt(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {
        key: item
        for key, item in {
            "file_path": value.get("file_path"),
            "readable": value.get("readable"),
            "read_receipt": "target preview omitted; see dedicated source sections",
        }.items()
        if item not in (None, "", (), [], {})
    }


def _preview_feedback_section(tool_name: str) -> str:
    if tool_name == "proposal.schema_preview":
        return "hypothesis_schema_telemetry_retry_feedback"
    if tool_name in {"proposal.contract_preview", "proposal.algorithm_smoke"}:
        return "latest_preview_repair_feedback"
    if tool_name == "proposal.target_permission_preview":
        return "hypothesis_schema_telemetry_retry_feedback"
    return ""


def _preview_passed(payload: Any) -> bool | None:
    if isinstance(payload, dict) and "passed" in payload:
        return bool(payload.get("passed"))
    return None


def _preview_failed_checks(value: Any) -> list[str]:
    failed: list[str] = []

    def visit(item: Any) -> None:
        if len(failed) >= 20:
            return
        if isinstance(item, dict):
            name = item.get("name")
            if name and item.get("passed") is False:
                failed.append(str(name))
            contract = item.get("contract")
            if isinstance(contract, dict):
                raw_failed = contract.get("failed_checks")
                if isinstance(raw_failed, list):
                    failed.extend(str(check) for check in raw_failed[:20])
            for child in item.values():
                visit(child)
        elif isinstance(item, list):
            for child in item[:40]:
                visit(child)

    visit(value)
    return list(dict.fromkeys(item for item in failed if item))[:20]


def _preview_repair_templates(value: Any) -> list[dict[str, Any]]:
    templates: list[dict[str, Any]] = []

    def visit(item: Any) -> None:
        if len(templates) >= 4:
            return
        if isinstance(item, dict):
            raw_templates = item.get("repair_templates")
            if isinstance(raw_templates, list):
                for template in raw_templates:
                    if isinstance(template, dict):
                        templates.append(_compact_preview_repair_template(template))
                        if len(templates) >= 4:
                            return
            raw_template = item.get("repair_template")
            if isinstance(raw_template, dict):
                templates.append(_compact_preview_repair_template(raw_template))
                if len(templates) >= 4:
                    return
            for child in item.values():
                visit(child)
        elif isinstance(item, list):
            for child in item[:40]:
                visit(child)

    visit(value)
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for template in templates:
        key = json.dumps(template, sort_keys=True, default=str)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(template)
    return deduped[:4]


def _compact_preview_repair_template(template: dict[str, Any]) -> dict[str, Any]:
    return _drop_empty(
        {
            "repair_type": template.get("repair_type"),
            "check": template.get("check"),
            "severity": template.get("severity"),
            "missing_fields": template.get("missing_fields"),
            "observed": template.get("observed"),
            "required_template": template.get("required_template"),
            "recommended_shape": template.get("recommended_shape"),
            "agent_instruction": template.get("agent_instruction"),
        }
    )


def _preview_failure_reason(value: Any) -> str:
    reasons: list[str] = []

    def add(text: Any) -> None:
        reason = str(text or "").strip()
        if reason and reason not in reasons:
            reasons.append(reason)

    def visit(item: Any) -> None:
        if len(reasons) >= 8:
            return
        if isinstance(item, dict):
            for key in ("failure_reason", "issue_summary", "repair_hint"):
                value_for_key = item.get(key)
                add(value_for_key)
            errors = item.get("errors")
            if isinstance(errors, list):
                for error in errors[:4]:
                    if isinstance(error, dict):
                        add(error.get("msg") or error.get("message") or error)
                    else:
                        add(error)
            issues = item.get("issues")
            if isinstance(issues, list):
                for issue in issues[:4]:
                    add(issue)
            for child in item.values():
                visit(child)
        elif isinstance(item, list):
            for child in item[:20]:
                visit(child)

    visit(value)
    return "; ".join(reasons[:6])


def _compact_preview_requested(payload: dict[str, Any]) -> dict[str, Any]:
    requested = payload.get("requested")
    if isinstance(requested, dict):
        return _drop_empty(
            {
                "change_locus": requested.get("change_locus"),
                "action": requested.get("action"),
                "target_file": requested.get("target_file"),
            }
        )
    hypothesis = payload.get("hypothesis")
    if isinstance(hypothesis, dict):
        summary = hypothesis.get("hypothesis")
        if isinstance(summary, dict):
            return _drop_empty(
                {
                    "change_locus": summary.get("change_locus"),
                    "action": summary.get("action"),
                    "target_file": summary.get("target_file"),
                    "mechanism_changes": summary.get("mechanism_changes"),
                }
            )
    patch = payload.get("patch")
    if isinstance(patch, dict):
        summary = patch.get("patch")
        if isinstance(summary, dict):
            return _drop_empty(
                {
                    "file_path": summary.get("file_path"),
                    "action": summary.get("action"),
                }
            )
    return {}


def _compact_preview_permission(payload: dict[str, Any]) -> dict[str, Any]:
    permission = payload.get("permission")
    if not isinstance(permission, dict):
        return {}
    return _drop_empty(
        {
            "surface_known": permission.get("surface_known"),
            "action_allowed": permission.get("action_allowed"),
            "target_required": permission.get("target_required"),
            "target_path_safe": permission.get("target_path_safe"),
            "target_declared": permission.get("target_declared"),
        }
    )


def _compact_static_solver_context_payload(
    tool_name: str,
    payload: dict[str, Any],
    *,
    active_digest: str,
    resume_active_digest: str,
) -> dict[str, Any]:
    facts = payload.get("active_algorithm_facts")
    facts_digest = _fact_packet_digest(facts)
    source_digest = _compact_source_digest(payload.get("source_digest"))
    compact: dict[str, Any] = {
        "projection_kind": "static_solver_context_receipt.v1",
        "tool_payload_omitted_from_generic_observations": True,
        "dedicated_context_sections": [
            section
            for section in (
                "active_algorithm_facts" if active_digest else "",
                "solver_design_full_algorithm_file_reads",
            )
            if section
        ],
        "surface": payload.get("surface"),
        "source": payload.get("source"),
        "snapshot_digest": _snapshot_digest(payload),
        "source_digest": source_digest,
    }
    if facts_digest:
        compact["active_algorithm_facts_ref"] = _drop_empty(
            {
                "fact_packet_digest": facts_digest,
                "snapshot_digest": _snapshot_digest(facts),
                "fact_ids": _fact_ids(facts),
                "omitted_from_raw_observation": (
                    "deduplicated; see Active Algorithm Facts / Resume Context"
                    if facts_digest in {active_digest, resume_active_digest}
                    else "deduplicated; see static solver context sections"
                ),
            }
        )
    if tool_name == "context.list_algorithm_files":
        paths = _algorithm_file_paths(payload.get("files"))
        compact.update(
            {
                "file_count": len(paths),
                "file_paths": paths,
            }
        )
    elif tool_name == "context.read_solver_call_graph":
        edges = payload.get("edges")
        nodes = payload.get("nodes")
        compact.update(
            {
                "edge_count": len(edges) if isinstance(edges, list) else None,
                "node_count": len(nodes) if isinstance(nodes, list) else None,
                "call_graph_ref": "deduplicated; see Active Algorithm Facts / solver execution model",
            }
        )
    elif tool_name == "context.read_active_solver_design":
        paths = _algorithm_file_paths(payload.get("files"))
        if not paths and isinstance(payload.get("source_digest"), dict):
            files = payload["source_digest"].get("files")
            if isinstance(files, dict):
                paths = [str(path) for path in files if str(path).strip()]
        compact.update(
            {
                "entrypoint": payload.get("entrypoint"),
                "file_count": len(paths),
                "file_paths": paths[:16],
                "active_solver_snapshot_ref": "deduplicated; see Active Algorithm Facts and full algorithm file reads",
            }
        )
    return _drop_empty(compact)


def _is_solver_design_surface_payload(payload: dict[str, Any]) -> bool:
    identity = _surface_identity(payload)
    return any(value == "solver_design" for value in identity.values())


def _surface_identity(payload: dict[str, Any]) -> dict[str, str]:
    raw_surface = payload.get("surface")
    surface = raw_surface if isinstance(raw_surface, dict) else {}
    candidates = {
        "id": surface.get("id") or payload.get("surface_id"),
        "name": surface.get("name") or payload.get("name"),
        "kind": surface.get("kind") or payload.get("kind"),
    }
    if isinstance(raw_surface, str):
        candidates["surface"] = raw_surface
    summary = payload.get("interface_summary")
    if isinstance(summary, str) and "Declared Research Surface: solver_design" in summary:
        candidates["interface_summary_surface"] = "solver_design"
    return {
        key: str(value).strip()
        for key, value in candidates.items()
        if str(value or "").strip()
    }


def _algorithm_file_paths(value: Any) -> list[str]:
    if isinstance(value, dict):
        return [str(path) for path in value if str(path).strip()]
    if not isinstance(value, list):
        return []
    paths: list[str] = []
    for item in value:
        if isinstance(item, dict):
            path = str(item.get("file_path") or item.get("path") or "").strip()
        else:
            path = str(item or "").strip()
        if path:
            paths.append(path)
    return list(dict.fromkeys(paths))


def _compact_source_digest(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    files = value.get("files")
    file_count = len(files) if isinstance(files, dict) else None
    return _drop_empty(
        {
            "algorithm": value.get("algorithm"),
            "snapshot_digest": value.get("snapshot_digest"),
            "file_count": file_count,
            "digest": _stable_short_digest(value),
        }
    )


def _solver_design_full_algorithm_file_reads(observations: Any) -> list[dict[str, Any]]:
    if not isinstance(observations, list):
        return []
    reads: list[dict[str, Any]] = []
    for observation in observations:
        if not isinstance(observation, dict):
            continue
        if observation.get("tool_name") != "context.read_algorithm_file":
            continue
        if bool(observation.get("is_error")):
            continue
        payload = observation.get("structured_payload")
        if not isinstance(payload, dict):
            continue
        if not _is_full_algorithm_file_payload(payload):
            continue
        reads.append(
            _drop_empty(
                {
                    "observation_id": observation.get("observation_id"),
                    "tool_name": observation.get("tool_name"),
                    "observation_digest": observation.get("digest"),
                    "file_path": payload.get("file_path"),
                    "active": payload.get("active"),
                    "role": payload.get("role"),
                    "module": payload.get("module"),
                    "readable": payload.get("readable"),
                    "source": payload.get("source"),
                    "source_digest": _canonical_full_source_digest(payload),
                    "source_digest_hash": _noncanonical_source_digest_hash(payload)
                    or payload.get("digest"),
                    "sha256": payload.get("sha256"),
                    "truncated": payload.get("truncated"),
                    "size_chars": payload.get("size_chars"),
                    "max_chars": payload.get("max_chars"),
                    "content_preview": payload.get("content_preview"),
                }
            )
        )
    return reads


def _canonical_full_source_digest(payload: dict[str, Any]) -> str:
    for key in ("source_digest", "sha256"):
        value = payload.get(key)
        if _looks_like_sha256(value):
            return str(value)
    content = payload.get("content_preview")
    if isinstance(content, str) and content and _is_full_algorithm_file_payload(payload):
        return hashlib.sha256(content.encode("utf-8")).hexdigest()
    return ""


def _noncanonical_source_digest_hash(payload: dict[str, Any]) -> Any:
    value = payload.get("source_digest_hash") or payload.get("source_digest")
    if _looks_like_sha256(value):
        return ""
    return value


def _looks_like_sha256(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    return all(ch in "0123456789abcdefABCDEF" for ch in value)


def _is_full_algorithm_file_payload(payload: dict[str, Any]) -> bool:
    if payload.get("readable") is not True:
        return False
    if payload.get("already_observed"):
        return False
    if payload.get("active") is False:
        return False
    content_preview = payload.get("content_preview")
    if content_preview is None:
        return False
    if bool(payload.get("truncated")):
        return False
    preview_chars = len(str(content_preview))
    size_chars = _coerce_nonnegative_int(payload.get("size_chars"))
    max_chars = _coerce_nonnegative_int(payload.get("max_chars"))
    if size_chars is not None and max_chars is not None and max_chars >= size_chars:
        return True
    if size_chars is not None:
        return preview_chars >= size_chars
    if max_chars is not None:
        return preview_chars >= max_chars
    return True


def _coerce_nonnegative_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except Exception:
        return None
    return parsed if parsed >= 0 else None


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
