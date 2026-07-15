"""Read and compactly project durable proposal-attempt transitions.

This module is the sole owner of the attempt transition row schema, strict row
validation, grouped lifecycle validation, and report-only attempt inventory.
It does not join formal candidates or merge legacy agentic trajectories.
"""
from __future__ import annotations

import json
import math
import re
import sqlite3
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from scion.core.public_refs import contains_absolute_path


PROPOSAL_ATTEMPT_DB_REF = "scion.db"
_PROPOSAL_ATTEMPT_SCHEMA = "proposal-attempt-transition.v1"
_ATTEMPT_REQUIRED_FIELDS = frozenset(
    {
        "schema_version", "attempt_id", "campaign_id", "branch_id",
        "runtime_mode", "phase", "status", "transition_reason",
        "failure_lane", "hypothesis_id", "hypothesis_digest", "patch_digest",
        "prompt_call", "anchors", "tainted_artifact_refs",
    }
)
_ATTEMPT_OPTIONAL_FIELDS = frozenset(
    {
        "attempt_kind", "continuation_of_attempt_id", "trace_persistence_error",
        "proposal_fingerprint",
    }
)
_PROPOSAL_FINGERPRINT_FIELDS = frozenset(
    {"selected_surface", "action", "target_file"}
)
_PROPOSAL_ACTIONS = frozenset({"modify", "create_new", "remove"})
_PROPOSAL_SURFACE_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
_ATTEMPT_ANCHOR_FIELDS = frozenset(
    {
        "problem_id", "problem_spec_hash", "split_manifest_hash",
        "seed_ledger_hash", "champion_version", "champion_weight_revision",
        "champion_code_snapshot_hash", "branch_base_champion_id",
        "branch_base_champion_hash",
    }
)
_ATTEMPT_PROMPT_FIELDS = frozenset(
    {
        "request_kind", "context_digest", "prompt_hash", "trace_ref",
        "prompt_manifest_ref", "raw_response_ref", "provider_ok", "ok",
        "error_category", "error_type",
    }
)


def read_proposal_attempt_transitions(db_path: str | Path) -> dict[str, Any]:
    """Read and strictly project every v1 proposal-attempt transition."""

    path = Path(db_path)
    empty_stats: dict[str, Any] = {
        "source_status": "missing",
        "row_count": 0,
        "valid_row_count": 0,
        "invalid_row_count": 0,
        "invalid_group_count": 0,
        "invalid_group_row_count": 0,
        "attempt_count": 0,
        "unrecovered_in_flight_count": 0,
        "by_runtime_mode": {},
        "by_phase": {},
        "by_status": {},
        "by_failure_lane": {},
        "prompt_manifest_ref_count": 0,
        "invalid_by_reason": {},
    }
    if not path.exists():
        return {"attempts": [], "stats": empty_stats}
    try:
        with sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True) as conn:
            columns = {
                str(row[1])
                for row in conn.execute("PRAGMA table_info(experiment_events)")
            }
            if not {"event_kind", "audit_payload_json"}.issubset(columns):
                return {
                    "attempts": [],
                    "stats": {**empty_stats, "source_status": "unavailable"},
                }
            event_id_expr = "event_id" if "event_id" in columns else "''"
            rows = conn.execute(
                f"SELECT rowid, {event_id_expr}, audit_payload_json "
                "FROM experiment_events WHERE event_kind = ? ORDER BY rowid",
                ("proposal_attempt_transition",),
            ).fetchall()
    except sqlite3.DatabaseError as exc:
        return {
            "attempts": [],
            "stats": {
                **empty_stats,
                "source_status": "read_error",
                "read_error": f"{type(exc).__name__}: {exc}",
            },
        }

    invalid_reasons: Counter[str] = Counter()
    grouped_rows: dict[str, list[dict[str, Any]]] = {}
    strict_invalid_row_count = 0
    for rowid, event_id, raw_payload in rows:
        try:
            payload = _parse_proposal_attempt_payload(raw_payload)
        except ValueError as exc:
            invalid_reasons[str(exc)] += 1
            strict_invalid_row_count += 1
            continue
        if contains_absolute_path(_clean_str(event_id)):
            invalid_reasons["non_public_event_id"] += 1
            strict_invalid_row_count += 1
            continue
        transition = _proposal_attempt_transition_projection(
            payload,
            event_id=_clean_str(event_id),
        )
        if contains_absolute_path(transition):
            invalid_reasons["absolute_path_in_projection"] += 1
            strict_invalid_row_count += 1
            continue
        grouped_rows.setdefault(payload["attempt_id"], []).append(
            {"rowid": int(rowid), "payload": payload, "transition": transition}
        )

    valid_groups: dict[str, list[dict[str, Any]]] = {}
    invalid_group_count = 0
    invalid_group_row_count = 0
    for attempt_id, group_rows in grouped_rows.items():
        reason = _validate_proposal_attempt_group(group_rows)
        if reason:
            invalid_reasons[reason] += 1
            invalid_group_count += 1
            invalid_group_row_count += len(group_rows)
            continue
        valid_groups[attempt_id] = group_rows

    # A continuation is valid only while its append-only parent remains valid and
    # precedes it. Iterate so an invalid continuation cannot act as a parent for
    # another accepted group.
    while True:
        rejected: list[tuple[str, str]] = []
        for attempt_id, group_rows in valid_groups.items():
            payload = group_rows[0]["payload"]
            parent_id = _clean_str(payload.get("continuation_of_attempt_id"))
            if not parent_id:
                continue
            parent_rows = valid_groups.get(parent_id)
            if parent_rows is None:
                rejected.append((attempt_id, "missing_parent"))
            elif max(item["rowid"] for item in parent_rows) >= min(
                item["rowid"] for item in group_rows
            ):
                rejected.append((attempt_id, "phase_order_invalid"))
        if not rejected:
            break
        for attempt_id, reason in rejected:
            group_rows = valid_groups.pop(attempt_id, None)
            if group_rows is None:
                continue
            invalid_reasons[reason] += 1
            invalid_group_count += 1
            invalid_group_row_count += len(group_rows)

    attempts: list[dict[str, Any]] = []
    accepted_rows: list[dict[str, Any]] = []
    for group_rows in valid_groups.values():
        first_payload = group_rows[0]["payload"]
        phases = [item["transition"] for item in group_rows]
        attempt = {
            "attempt_id": first_payload["attempt_id"],
            "campaign_id": first_payload["campaign_id"],
            "branch_id": first_payload["branch_id"],
            "runtime_mode": first_payload["runtime_mode"],
            "attempt_kind": first_payload.get("attempt_kind") or "initial",
            "continuation_of_attempt_id": first_payload.get(
                "continuation_of_attempt_id"
            ),
            "phases": phases,
        }
        accepted_rows.extend(item["payload"] for item in group_rows)
        terminal = phases[-1] if phases else {}
        attempt["hypothesis_id"] = _clean_str(terminal.get("hypothesis_id"))
        attempt["terminal_phase"] = _clean_str(terminal.get("phase"))
        attempt["terminal_status"] = _clean_str(terminal.get("status"))
        attempt["terminal_failure_lane"] = _clean_str(
            terminal.get("failure_lane")
        )
        if attempt["terminal_status"] == "started":
            # Report-only classification for a provider call whose durable
            # terminal transition was never written (for example, SIGKILL or
            # host loss).  Do not forge a failed transition and do not retry.
            attempt["postrun_classification"] = "unrecovered_in_flight"
        attempts.append(_drop_empty(attempt))

    stats = {
        "source_status": "available",
        "row_count": len(rows),
        "valid_row_count": len(accepted_rows),
        "invalid_row_count": strict_invalid_row_count + invalid_group_row_count,
        "invalid_group_count": invalid_group_count,
        "invalid_group_row_count": invalid_group_row_count,
        "attempt_count": len(attempts),
        "unrecovered_in_flight_count": sum(
            1
            for attempt in attempts
            if attempt.get("postrun_classification") == "unrecovered_in_flight"
        ),
        "by_runtime_mode": dict(
            sorted(Counter(row["runtime_mode"] for row in accepted_rows).items())
        ),
        "by_phase": dict(
            sorted(Counter(row["phase"] for row in accepted_rows).items())
        ),
        "by_status": dict(
            sorted(Counter(row["status"] for row in accepted_rows).items())
        ),
        "by_failure_lane": dict(
            sorted(
                Counter(
                    row["failure_lane"]
                    for row in accepted_rows
                    if row.get("failure_lane")
                ).items()
            )
        ),
        "prompt_manifest_ref_count": sum(
            1
            for row in accepted_rows
            if _clean_str(_mapping(row.get("prompt_call")).get("prompt_manifest_ref"))
        ),
        "invalid_by_reason": dict(sorted(invalid_reasons.items())),
    }
    return {"attempts": attempts, "stats": stats}


def _validate_proposal_attempt_group(group_rows: list[dict[str, Any]]) -> str:
    """Return one stable rejection reason for an otherwise row-valid group."""

    payloads = [item["payload"] for item in group_rows]
    first = payloads[0]
    first_kind = first.get("attempt_kind") or "initial"
    immutable_identity = (
        first["campaign_id"],
        first["branch_id"],
        first["runtime_mode"],
        first["phase"],
        first_kind,
        _clean_str(first.get("continuation_of_attempt_id")),
        _clean_str(_mapping(first.get("prompt_call")).get("context_digest")),
        _clean_str(_mapping(first.get("prompt_call")).get("prompt_hash")),
        dict(first["anchors"]),
    )
    for payload in payloads[1:]:
        identity = (
            payload["campaign_id"],
            payload["branch_id"],
            payload["runtime_mode"],
            payload["phase"],
            payload.get("attempt_kind") or "initial",
            _clean_str(payload.get("continuation_of_attempt_id")),
            _clean_str(_mapping(payload.get("prompt_call")).get("context_digest")),
            _clean_str(_mapping(payload.get("prompt_call")).get("prompt_hash")),
            dict(payload["anchors"]),
        )
        if identity != immutable_identity:
            return "identity_conflict"

    statuses = [str(payload["status"]) for payload in payloads]
    if statuses not in (["started"], ["started", "generated"], ["started", "failed"]):
        return "attempt_status_order_invalid"
    if len(payloads) == 2:
        started, terminal = payloads
        if terminal["phase"] == "code" and (
            terminal.get("hypothesis_id") != started.get("hypothesis_id")
            or terminal.get("hypothesis_digest") != started.get("hypothesis_digest")
        ):
            return "identity_conflict"
        started_fingerprint = _mapping(started.get("proposal_fingerprint"))
        terminal_fingerprint = _mapping(terminal.get("proposal_fingerprint"))
        if (
            first["phase"] == "code"
            and terminal_fingerprint != started_fingerprint
        ) or (
            first["phase"] == "hypothesis"
            and started_fingerprint
            and terminal_fingerprint != started_fingerprint
        ):
            return "identity_conflict"
    if first["phase"] == "hypothesis":
        if first_kind != "initial" or first.get("continuation_of_attempt_id") is not None:
            return "phase_order_invalid"
    elif first_kind != "approved_code_continuation":
        return "phase_order_invalid"
    return ""


def _parse_proposal_attempt_payload(raw_payload: Any) -> dict[str, Any]:
    try:
        payload = json.loads(raw_payload) if isinstance(raw_payload, str) else raw_payload
    except json.JSONDecodeError as exc:
        raise ValueError("invalid_json") from exc
    if not isinstance(payload, Mapping):
        raise ValueError("payload_not_object")
    payload = dict(payload)
    allowed = _ATTEMPT_REQUIRED_FIELDS | _ATTEMPT_OPTIONAL_FIELDS
    if payload.keys() - allowed:
        raise ValueError("unsupported_top_level_fields")
    if _ATTEMPT_REQUIRED_FIELDS - payload.keys():
        raise ValueError("missing_required_fields")
    if payload.get("schema_version") != _PROPOSAL_ATTEMPT_SCHEMA:
        raise ValueError("unsupported_schema")
    for field in ("attempt_id", "campaign_id", "branch_id", "transition_reason"):
        if not _clean_str(payload.get(field)):
            raise ValueError(f"missing_{field}")
    if payload.get("runtime_mode") != "direct_v3":
        raise ValueError("invalid_runtime_mode")
    if payload.get("phase") not in {"hypothesis", "code"}:
        raise ValueError("invalid_phase")
    if payload.get("status") not in {"started", "generated", "failed"}:
        raise ValueError("invalid_status")
    lane = payload.get("failure_lane")
    # Preserve the old label for historical artifact reads only. Current
    # direct-v3 writes use ``invalid_response`` and stop the campaign call.
    if lane not in {None, "infra", "invalid_response", "proposal_repair"}:
        raise ValueError("invalid_failure_lane")
    if payload["status"] in {"started", "generated"} and lane is not None:
        raise ValueError("status_failure_lane_mismatch")
    if payload["status"] == "failed" and lane is None:
        raise ValueError("status_failure_lane_mismatch")
    continuation = payload.get("continuation_of_attempt_id")
    if continuation is not None and not _clean_str(continuation):
        raise ValueError("invalid_continuation")
    if continuation and _clean_str(continuation) == _clean_str(payload["attempt_id"]):
        raise ValueError("self_continuation")
    attempt_kind = payload.get("attempt_kind")
    if attempt_kind not in {None, "initial", "approved_code_continuation"}:
        raise ValueError("invalid_attempt_kind")
    if continuation is not None and (
        payload["phase"] != "code"
        or attempt_kind != "approved_code_continuation"
    ):
        raise ValueError("invalid_continuation_phase")
    if attempt_kind == "approved_code_continuation" and continuation is None:
        raise ValueError("continuation_id_missing")

    anchors = payload.get("anchors")
    if not isinstance(anchors, Mapping) or set(anchors) != _ATTEMPT_ANCHOR_FIELDS:
        raise ValueError("invalid_anchors")
    if any(not _is_json_scalar(value) for value in anchors.values()):
        raise ValueError("invalid_anchor_value")
    prompt_call = payload.get("prompt_call")
    if not isinstance(prompt_call, Mapping) or set(prompt_call) != _ATTEMPT_PROMPT_FIELDS:
        raise ValueError("invalid_prompt_call")
    if prompt_call.get("request_kind") != payload["phase"]:
        raise ValueError("prompt_phase_mismatch")
    fingerprint = payload.get("proposal_fingerprint")
    if fingerprint is not None:
        if not isinstance(fingerprint, Mapping) or set(fingerprint) != (
            _PROPOSAL_FINGERPRINT_FIELDS
        ):
            raise ValueError("invalid_proposal_fingerprint")
        if not _PROPOSAL_SURFACE_RE.fullmatch(
            _clean_str(fingerprint.get("selected_surface"))
        ):
            raise ValueError("invalid_proposal_fingerprint")
        if fingerprint.get("action") not in _PROPOSAL_ACTIONS:
            raise ValueError("invalid_proposal_fingerprint")
        if not _is_public_target_file(
            fingerprint.get("target_file"),
            allow_missing=fingerprint.get("action") == "create_new",
        ):
            raise ValueError("invalid_proposal_fingerprint")
    for field in ("context_digest", "prompt_hash"):
        if not _clean_str(prompt_call.get(field)):
            raise ValueError(f"missing_{field}")
    for field in ("trace_ref", "prompt_manifest_ref", "raw_response_ref"):
        ref = prompt_call.get(field)
        if ref not in (None, "") and not _is_public_attempt_ref(ref):
            raise ValueError("non_public_prompt_ref")
    refs = payload.get("tainted_artifact_refs")
    if not isinstance(refs, list) or any(
        not _is_public_attempt_ref(ref) for ref in refs
    ):
        raise ValueError("invalid_artifact_refs")
    trace_error = payload.get("trace_persistence_error")
    if trace_error is not None and (
        not isinstance(trace_error, Mapping)
        or set(trace_error) != {"stage", "error_type"}
        or payload["status"] != "failed"
        or trace_error.get("stage") not in {"start", "finish"}
        or not _clean_str(trace_error.get("error_type"))
    ):
        raise ValueError("invalid_trace_persistence_error")
    if payload["phase"] == "hypothesis" and payload.get("patch_digest") is not None:
        raise ValueError("hypothesis_patch_digest_present")
    if payload["status"] == "generated":
        if prompt_call.get("provider_ok") is not True or prompt_call.get("ok") is not True:
            raise ValueError("generated_prompt_not_successful")
        if any(not _clean_str(prompt_call.get(key)) for key in (
            "trace_ref", "prompt_manifest_ref", "raw_response_ref"
        )):
            raise ValueError("generated_prompt_ref_missing")
        if not _clean_str(payload.get("hypothesis_id")) or not _clean_str(
            payload.get("hypothesis_digest")
        ):
            raise ValueError("generated_hypothesis_identity_missing")
        if payload["phase"] == "code" and not _clean_str(payload.get("patch_digest")):
            raise ValueError("generated_patch_digest_missing")
    elif payload["status"] == "started":
        if payload.get("transition_reason") != "provider_call_started":
            raise ValueError("started_reason_invalid")
        if prompt_call.get("provider_ok") is not None or prompt_call.get("ok") is not None:
            raise ValueError("started_prompt_has_outcome")
        if prompt_call.get("error_category") is not None or prompt_call.get(
            "error_type"
        ) is not None:
            raise ValueError("started_prompt_has_error")
        if any(
            prompt_call.get(key) not in (None, "")
            for key in ("trace_ref", "prompt_manifest_ref", "raw_response_ref")
        ):
            raise ValueError("started_prompt_ref_present")
        if payload.get("patch_digest") is not None or refs:
            raise ValueError("started_artifact_present")
        if payload["phase"] == "hypothesis" and (
            payload.get("hypothesis_id") is not None
            or payload.get("hypothesis_digest") is not None
        ):
            raise ValueError("started_hypothesis_identity_present")
        if payload["phase"] == "hypothesis" and fingerprint is not None:
            raise ValueError("started_hypothesis_fingerprint_present")
        if payload["phase"] == "code" and (
            not _clean_str(payload.get("hypothesis_id"))
            or not _clean_str(payload.get("hypothesis_digest"))
        ):
            raise ValueError("started_code_identity_missing")
    return payload


def _proposal_attempt_transition_projection(
    payload: Mapping[str, Any],
    *,
    event_id: str,
) -> dict[str, Any]:
    prompt = _mapping(payload.get("prompt_call"))
    return _drop_empty(
        {
            "event_id": event_id,
            "phase": payload.get("phase"),
            "status": payload.get("status"),
            "transition_reason": payload.get("transition_reason"),
            "failure_lane": payload.get("failure_lane"),
            "hypothesis_id": payload.get("hypothesis_id"),
            "hypothesis_digest": payload.get("hypothesis_digest"),
            "patch_digest": payload.get("patch_digest"),
            "proposal_fingerprint": dict(
                _mapping(payload.get("proposal_fingerprint"))
            ),
            "prompt_fingerprint": {
                key: prompt.get(key) for key in _ATTEMPT_PROMPT_FIELDS
            },
            "anchors": dict(_mapping(payload.get("anchors"))),
            "artifact_refs": list(payload.get("tainted_artifact_refs") or ()),
            "trace_persistence_error": dict(
                _mapping(payload.get("trace_persistence_error"))
            ),
        }
    )


def _clean_str(value: Any) -> str:
    return str(value or "").strip()


def _is_json_scalar(value: Any) -> bool:
    if value is None or isinstance(value, (str, bool, int)):
        return True
    return isinstance(value, float) and math.isfinite(value)


def _is_public_attempt_ref(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    ref = value.strip()
    normalized = ref.replace("\\", "/")
    if ref.lower().startswith("file:"):
        return False
    if normalized.startswith("//"):
        return False
    if (
        len(normalized) >= 3
        and normalized[0].isalpha()
        and normalized[1:3] == ":/"
    ):
        return False
    if contains_absolute_path(ref):
        return False
    path_part = normalized.split("#", 1)[0].split("?", 1)[0]
    return all(part != ".." for part in path_part.split("/"))


def _is_public_target_file(value: Any, *, allow_missing: bool = False) -> bool:
    if value is None:
        return allow_missing
    if not isinstance(value, str) or not value.strip():
        return False
    target = value.strip().replace("\\", "/")
    if (
        len(target) > 1024
        or "#" in target
        or "?" in target
        or target.startswith("//")
    ):
        return False
    if contains_absolute_path(target):
        return False
    return all(part not in {"", ".", ".."} for part in target.split("/"))


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _drop_empty(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        str(key): value
        for key, value in payload.items()
        if value not in (None, "", (), [], {})
    }
