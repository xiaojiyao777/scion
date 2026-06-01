"""Model-facing APS resume projection helpers."""
from __future__ import annotations

import json
from typing import Any, Mapping

from scion.proposal.agentic_utils import _drop_empty_dict, _limit_string


def compact_failure_ledger_for_resume(value: Mapping[str, Any]) -> dict[str, Any]:
    entries = value.get("entries")
    latest_entry: Mapping[str, Any] = {}
    if isinstance(entries, (list, tuple)):
        for item in reversed(entries):
            if isinstance(item, Mapping):
                latest_entry = item
                break
    return _drop_empty_dict(
        {
            "schema_version": value.get("schema_version"),
            "entry_count": value.get("entry_count"),
            "first_root_cause": value.get("first_root_cause"),
            "first_failure_phase": value.get("first_failure_phase"),
            "latest_failure": value.get("latest_failure"),
            "latest_failure_phase": value.get("latest_failure_phase"),
            "latest_entry": _drop_empty_dict(
                {
                    "phase": latest_entry.get("phase"),
                    "category": latest_entry.get("category"),
                    "source": latest_entry.get("source"),
                    "attempt": latest_entry.get("attempt"),
                    "root_cause": latest_entry.get("root_cause"),
                    "detail": _limit_string(latest_entry.get("detail"), 500),
                    "detail_full_ref": latest_entry.get("detail_full_ref"),
                    "diagnostic_ref": latest_entry.get("diagnostic_ref"),
                    "diagnostic_failure_code": (
                        (latest_entry.get("diagnostic_payload") or {}).get(
                            "failure_code"
                        )
                        if isinstance(latest_entry.get("diagnostic_payload"), Mapping)
                        else None
                    ),
                }
            ),
        }
    )


def build_agentic_resume_model_projection(
    *,
    payload: Mapping[str, Any],
    compact_budget: Mapping[str, Any],
    failure_ledger: Mapping[str, Any],
    observation_ledger: Mapping[str, Any],
    tool_steps: list[Mapping[str, Any]],
    max_chars: int,
) -> dict[str, Any]:
    active_anchor = (
        observation_ledger.get("active_fact_anchor")
        if isinstance(observation_ledger.get("active_fact_anchor"), Mapping)
        else {}
    )
    projection = _drop_empty_dict(
        {
            "schema_version": "agentic-resume-model-projection.v1",
            "projection_policy": (
                "bounded_model_facing_handoff_no_raw_observation_ledger"
            ),
            "previous_session": _drop_empty_dict(
                {
                    "session_id": payload.get("session_id"),
                    "request_id": payload.get("request_id"),
                    "status": payload.get("status"),
                    "termination_reason": payload.get("termination_reason"),
                    "failure_category": payload.get("failure_category"),
                    "transcript_digest": payload.get("transcript_digest"),
                }
            ),
            "previous_failure": _resume_failure_summary(payload, failure_ledger),
            "active_fact_digest": _drop_empty_dict(
                {
                    "fact_packet_digest": active_anchor.get("fact_packet_digest"),
                    "snapshot_digest": active_anchor.get("snapshot_digest"),
                    "fact_ids": list(active_anchor.get("fact_ids") or ())[:12],
                    "source_observation_id": active_anchor.get(
                        "source_observation_id"
                    ),
                }
            ),
            "read_file_digests": _resume_read_file_digests(observation_ledger),
            "read_receipts": _resume_read_receipts(observation_ledger),
            "tool_steps": _resume_tool_steps(tool_steps),
            "previous_patch_summary": _resume_patch_summary(payload.get("patch")),
            "tool_budget_used": dict(compact_budget),
            "reuse_note": (
                "Read receipts prove prior bounded reads by digest only. Reuse "
                "them for orientation; request a fresh read before relying on "
                "exact source content."
            ),
        }
    )
    return _fit_resume_projection(projection, max_chars=max(1200, min(max_chars, 3600)))


def _resume_failure_summary(
    payload: Mapping[str, Any],
    failure_ledger: Mapping[str, Any],
) -> dict[str, Any]:
    structured = (
        payload.get("structured_rejection")
        if isinstance(payload.get("structured_rejection"), Mapping)
        else {}
    )
    return _drop_empty_dict(
        {
            "type": (
                payload.get("failure_category")
                or failure_ledger.get("latest_failure")
                or payload.get("termination_reason")
            ),
            "termination_reason": payload.get("termination_reason"),
            "latest_failure": failure_ledger.get("latest_failure"),
            "latest_failure_phase": failure_ledger.get("latest_failure_phase"),
            "detail": _limit_string(payload.get("failure_detail"), 600),
            "structured_failure_code": structured.get("failure_code"),
            "structured_gate": structured.get("gate_name") or structured.get("source"),
            "structured_reason": _limit_string(structured.get("reason"), 500),
        }
    )


def _resume_read_file_digests(
    observation_ledger: Mapping[str, Any],
    *,
    limit: int = 8,
) -> list[dict[str, Any]]:
    entries = observation_ledger.get("observations")
    if not isinstance(entries, (list, tuple)):
        return []
    result: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, Mapping):
            continue
        tool_name = str(entry.get("tool_name") or "")
        if tool_name not in {
            "context.read_algorithm_file",
            "context.read_algorithm_symbol",
            "context.read_surface",
        }:
            continue
        result.append(
            _drop_empty_dict(
                {
                    "tool_name": tool_name,
                    "file_path": entry.get("file_path"),
                    "symbol": entry.get("symbol"),
                    "digest": entry.get("digest"),
                    "source_digest_hash": entry.get("source_digest_hash"),
                    "max_chars": entry.get("max_chars"),
                    "truncated": entry.get("truncated"),
                    "observation_id": entry.get("observation_id"),
                }
            )
        )
        if len(result) >= limit:
            break
    return result


def _resume_read_receipts(
    observation_ledger: Mapping[str, Any],
    *,
    limit: int = 8,
) -> list[dict[str, Any]]:
    receipts = observation_ledger.get("read_receipts")
    if not isinstance(receipts, (list, tuple)):
        return []
    compact: list[dict[str, Any]] = []
    for item in receipts[:limit]:
        if not isinstance(item, Mapping):
            continue
        compact.append(
            _drop_empty_dict(
                {
                    "observation_id": item.get("observation_id"),
                    "tool_name": item.get("tool_name"),
                    "file_path": item.get("file_path"),
                    "symbol": item.get("symbol"),
                    "digest": item.get("digest"),
                    "source_digest_hash": item.get("source_digest_hash"),
                    "fact_packet_digest": item.get("fact_packet_digest"),
                    "snapshot_digest": item.get("snapshot_digest"),
                    "max_chars": item.get("max_chars"),
                    "truncated": item.get("truncated"),
                    "coverage_status": item.get("coverage_status"),
                }
            )
        )
    return compact


def _resume_tool_steps(
    tool_steps: list[Mapping[str, Any]],
    *,
    limit: int = 8,
) -> list[dict[str, Any]]:
    return [
        _drop_empty_dict(
            {
                "tool_name": step.get("tool_name"),
                "status": step.get("status"),
                "error_code": step.get("error_code"),
                "evidence_ref": step.get("evidence_ref"),
                "result_summary": _limit_string(step.get("result_summary"), 220),
            }
        )
        for step in tool_steps[:limit]
        if isinstance(step, Mapping)
    ]


def _resume_patch_summary(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    additional = []
    for item in list(value.get("additional_changes") or ())[:6]:
        if not isinstance(item, Mapping):
            continue
        additional.append(
            _drop_empty_dict(
                {
                    "file_path": item.get("file_path"),
                    "action": item.get("action"),
                    "patch_body_chars": item.get("patch_body_chars"),
                    "patch_body_omitted": item.get("patch_body_omitted"),
                }
            )
        )
    return _drop_empty_dict(
        {
            "premise_check": value.get("premise_check"),
            "premise_check_reason": _limit_string(
                value.get("premise_check_reason"),
                360,
            ),
            "file_path": value.get("file_path"),
            "action": value.get("action"),
            "patch_body_chars": value.get("patch_body_chars"),
            "patch_body_omitted": value.get("patch_body_omitted"),
            "additional_changes": additional,
            "test_hint": _limit_string(value.get("test_hint"), 240),
        }
    )


def _fit_resume_projection(
    projection: dict[str, Any],
    *,
    max_chars: int,
) -> dict[str, Any]:
    fitted = dict(projection)
    for receipts_limit, file_limit, steps_limit in (
        (8, 8, 8),
        (6, 6, 6),
        (4, 4, 4),
        (2, 2, 2),
        (0, 2, 0),
    ):
        if _json_chars(fitted) <= max_chars:
            return fitted
        if "read_receipts" in fitted:
            fitted["read_receipts"] = list(fitted["read_receipts"][:receipts_limit])
        if "read_file_digests" in fitted:
            fitted["read_file_digests"] = list(
                fitted["read_file_digests"][:file_limit]
            )
        if "tool_steps" in fitted:
            fitted["tool_steps"] = list(fitted["tool_steps"][:steps_limit])
    if _json_chars(fitted) > max_chars:
        fitted.pop("tool_steps", None)
        fitted.pop("read_receipts", None)
    if _json_chars(fitted) > max_chars:
        previous_failure = fitted.get("previous_failure")
        if isinstance(previous_failure, Mapping):
            fitted["previous_failure"] = _drop_empty_dict(
                {
                    key: (
                        _limit_string(value, 180)
                        if isinstance(value, str)
                        else value
                    )
                    for key, value in previous_failure.items()
                }
            )
    return fitted


def _json_chars(value: Any) -> int:
    return len(json.dumps(value, sort_keys=True, default=str))


__all__ = [
    "build_agentic_resume_model_projection",
    "compact_failure_ledger_for_resume",
]
