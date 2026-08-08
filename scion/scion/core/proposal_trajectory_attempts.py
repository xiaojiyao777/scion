"""Read minimal append-only proposal-call events for diagnostics."""
from __future__ import annotations

import json
import sqlite3
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from scion.core.public_refs import contains_absolute_path


PROPOSAL_ATTEMPT_DB_REF = "scion.db"  # Compatibility export for report callers.


def read_proposal_calls(db_path: str | Path) -> dict[str, Any]:
    path = Path(db_path)
    empty = _stats("missing", [])
    if not path.exists():
        return {"attempts": [], "calls": [], "stats": empty}
    try:
        with sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True) as conn:
            rows = conn.execute(
                "SELECT event_id, campaign_id, branch_id, hypothesis_id, "
                "audit_payload_json FROM experiment_events "
                "WHERE event_kind = 'proposal_call' ORDER BY rowid"
            ).fetchall()
    except sqlite3.DatabaseError as exc:
        stats = _stats("read_error", [])
        stats["read_error"] = f"{type(exc).__name__}: {exc}"
        return {"attempts": [], "calls": [], "stats": stats}

    calls: list[dict[str, Any]] = []
    invalid: Counter[str] = Counter()
    for event_id, campaign_id, branch_id, hypothesis_id, raw in rows:
        try:
            payload = json.loads(raw)
            call = _call_projection(
                payload,
                event_id=str(event_id or ""),
                campaign_id=str(campaign_id or ""),
                branch_id=str(branch_id or ""),
                hypothesis_id=str(hypothesis_id or "") or None,
            )
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            invalid[type(exc).__name__] += 1
            continue
        calls.append(call)
    stats = _stats("available", calls)
    stats.update(
        {
            "row_count": len(rows),
            "valid_row_count": len(calls),
            "invalid_row_count": len(rows) - len(calls),
            "invalid_by_reason": dict(sorted(invalid.items())),
        }
    )
    # ``attempts`` remains a read-only compatibility key while report surfaces
    # migrate to the scientifically accurate term ``calls``.
    return {"attempts": calls, "calls": calls, "stats": stats}


def read_proposal_attempt_transitions(db_path: str | Path) -> dict[str, Any]:
    """Compatibility alias; no attempt transitions are reconstructed."""

    return read_proposal_calls(db_path)


def _call_projection(
    payload: Any,
    *,
    event_id: str,
    campaign_id: str,
    branch_id: str,
    hypothesis_id: str | None,
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise TypeError("proposal call payload is not a mapping")
    if payload.get("schema_version") != "proposal-call.v1":
        raise ValueError("unsupported proposal call schema")
    phase = str(payload.get("phase") or "")
    status = str(payload.get("status") or "")
    if phase not in {"hypothesis", "code"}:
        raise ValueError("invalid proposal call phase")
    if status not in {"generated", "failed", "interrupted"}:
        raise ValueError("invalid proposal call status")
    if not campaign_id or not branch_id:
        raise ValueError("proposal call campaign/branch is missing")
    receipt = payload.get("receipt")
    if receipt is not None and not isinstance(receipt, Mapping):
        raise TypeError("proposal call receipt is not a mapping")
    receipt_map = dict(receipt or {})
    for key in ("trace_ref", "prompt_manifest_ref", "raw_response_ref"):
        ref = receipt_map.get(key)
        if ref and contains_absolute_path(ref):
            raise ValueError("proposal call contains an absolute artifact ref")
    return {
        "call_event_id": event_id,
        "campaign_id": campaign_id,
        "branch_id": branch_id,
        "hypothesis_id": hypothesis_id,
        "terminal_phase": phase,
        "terminal_status": status,
        "prompt_fingerprint": receipt_map,
        "execution_outcome": payload.get("execution_outcome"),
    }


def _stats(source_status: str, calls: list[dict[str, Any]]) -> dict[str, Any]:
    phases = Counter(str(call.get("terminal_phase") or "") for call in calls)
    statuses = Counter(str(call.get("terminal_status") or "") for call in calls)
    return {
        "source_status": source_status,
        "row_count": len(calls),
        "valid_row_count": len(calls),
        "invalid_row_count": 0,
        "invalid_group_count": 0,
        "invalid_group_row_count": 0,
        "attempt_count": len(calls),
        "call_count": len(calls),
        "unrecovered_in_flight_count": 0,
        "by_runtime_mode": {},
        "by_phase": dict(sorted(phases.items())),
        "by_status": dict(sorted(statuses.items())),
        "by_failure_lane": {},
        "prompt_manifest_ref_count": sum(
            bool(dict(call.get("prompt_fingerprint") or {}).get("prompt_manifest_ref"))
            for call in calls
        ),
        "invalid_by_reason": {},
    }


__all__ = [
    "PROPOSAL_ATTEMPT_DB_REF",
    "read_proposal_attempt_transitions",
    "read_proposal_calls",
]
