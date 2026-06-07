"""Active solver map receipt projections for proposal prompts."""

from __future__ import annotations

from typing import Any

from scion.proposal.engine.prompt.formatting import (
    _bounded_list,
    _drop_empty,
    _limit_text,
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
