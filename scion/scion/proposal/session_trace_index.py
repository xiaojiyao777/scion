"""Compact session-to-LLM-trace index helpers.

The trace files themselves may contain raw prompts.  This index stores only
stable ids, refs, hashes, counts, and final statuses so status/summary payloads
can point reviewers at the right traces without embedding trace contents.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from scion.core.public_refs import public_artifact_ref

SESSION_TRACE_INDEX_SCHEMA_VERSION = "agentic-session-trace-index.v1"
SESSION_TRACE_INDEX_NAME = "agentic_session_trace_index.json"


def attach_agentic_trace_context(
    context: Mapping[str, Any],
    *,
    session_id: str,
    request_id: str,
    branch_id: str,
    campaign_id: str,
    request_kind: str,
    call_kind: str,
    phase: str,
    attempt_number: int | None = None,
) -> dict[str, Any]:
    """Return a prompt context copy with trace-only audit metadata attached."""
    updated = dict(context)
    updated["_scion_trace_context"] = _drop_empty(
        {
            "session_id": session_id,
            "request_id": request_id,
            "branch_id": branch_id,
            "campaign_id": campaign_id,
            "request_kind": request_kind,
            "call_kind": call_kind,
            "phase": phase,
            "attempt_number": attempt_number,
        }
    )
    return updated


def attach_prompt_manifest_trace_context(
    context: Mapping[str, Any],
    *,
    artifact_ref: str | None,
    prompt_hash: str,
    visibility_ledger_digest: str,
    visibility_ledger_ref: str,
) -> None:
    """Mutate a dict-like prompt context with compact manifest refs when possible."""
    if not isinstance(context, dict):
        return
    context["_scion_prompt_manifest"] = _drop_empty(
        {
            "artifact_ref": artifact_ref,
            "prompt_hash": prompt_hash,
            "visibility_ledger_digest": visibility_ledger_digest,
            "visibility_ledger_ref": visibility_ledger_ref,
        }
    )


def session_trace_index_path_for_trace_dir(trace_dir: str | Path) -> Path:
    root = Path(trace_dir).resolve().parent
    return root / "agentic_sessions" / SESSION_TRACE_INDEX_NAME


def session_trace_index_path_for_artifact_dir(artifact_dir: str | Path) -> Path:
    return Path(artifact_dir).resolve() / SESSION_TRACE_INDEX_NAME


def record_trace_start(
    *,
    trace_dir: str | Path,
    trace_id: str,
    trace_path: str | Path,
    request_kind: str,
    model: str,
    prompt_hash: str,
    context: Mapping[str, Any],
    created_at: str,
) -> None:
    trace_context = trace_context_from_prompt_context(context)
    session_id = str(trace_context.get("session_id") or "").strip()
    if not session_id:
        return
    index_path = session_trace_index_path_for_trace_dir(trace_dir)
    base_dir = index_path.parent.parent
    prompt_manifest = _prompt_manifest_context(context)
    prompt_manifest_ref = _public_ref_with_anchor(
        prompt_manifest.get("artifact_ref"),
        base_dir=base_dir,
    )
    visibility_ledger_ref = _public_ref_with_anchor(
        prompt_manifest.get("visibility_ledger_ref"),
        base_dir=base_dir,
    )
    entry = _drop_empty(
        {
            "trace_id": trace_id,
            "request_kind": request_kind,
            "call_kind": trace_context.get("call_kind") or request_kind,
            "attempt_number": _int_or_none(trace_context.get("attempt_number")),
            "phase": trace_context.get("phase") or request_kind,
            "model": model,
            "prompt_hash": prompt_hash,
            "prompt_manifest_artifact_ref": prompt_manifest_ref,
            "prompt_visibility_ledger_ref": visibility_ledger_ref,
            "prompt_visibility_ledger_digest": prompt_manifest.get(
                "visibility_ledger_digest"
            ),
            "trace_ref": _public_ref(trace_path, base_dir=base_dir),
            "trace_path": _public_ref(trace_path, base_dir=base_dir),
            "created_at": created_at,
            "final_status": "pending",
            "ok": None,
        }
    )
    _upsert_trace_record(
        index_path=index_path,
        session_id=session_id,
        request_id=str(trace_context.get("request_id") or session_id),
        branch_id=str(trace_context.get("branch_id") or ""),
        campaign_id=str(trace_context.get("campaign_id") or ""),
        trace_entry=entry,
    )


def record_trace_finish(
    *,
    trace_dir: str | Path,
    trace_id: str,
    context: Mapping[str, Any],
    ok: bool,
    finished_at: str,
    error: str | None = None,
) -> None:
    trace_context = trace_context_from_prompt_context(context)
    session_id = str(trace_context.get("session_id") or "").strip()
    if not session_id:
        return
    index_path = session_trace_index_path_for_trace_dir(trace_dir)
    _upsert_trace_record(
        index_path=index_path,
        session_id=session_id,
        request_id=str(trace_context.get("request_id") or session_id),
        branch_id=str(trace_context.get("branch_id") or ""),
        campaign_id=str(trace_context.get("campaign_id") or ""),
        trace_entry=_drop_empty(
            {
                "trace_id": trace_id,
                "request_kind": context.get("request_kind"),
                "call_kind": trace_context.get("call_kind")
                or context.get("request_kind"),
                "attempt_number": _int_or_none(trace_context.get("attempt_number")),
                "phase": trace_context.get("phase") or context.get("request_kind"),
                "finished_at": finished_at,
                "final_status": "ok" if ok else "error",
                "ok": ok,
                "error_digest": _text_digest(error or "") if error else "",
            }
        ),
    )


def record_session_final(
    *,
    artifact_dir: str | Path,
    session_id: str,
    request_id: str,
    branch_id: str,
    campaign_id: str,
    phase: str,
    final_status: str,
    termination_reason: str,
    final_artifact_ref: str,
    final_artifact_path: str,
) -> None:
    if not str(session_id or "").strip():
        return
    index_path = session_trace_index_path_for_artifact_dir(artifact_dir)
    _upsert_session_final(
        index_path=index_path,
        session_id=session_id,
        request_id=request_id or session_id,
        branch_id=branch_id,
        campaign_id=campaign_id,
        final=_drop_empty(
            {
                "phase": phase,
                "final_status": final_status,
                "termination_reason": termination_reason,
                "final_artifact_ref": final_artifact_ref,
                "final_artifact_path": final_artifact_path,
                "updated_at": datetime.now().isoformat(),
            }
        ),
    )


def trace_context_from_prompt_context(context: Mapping[str, Any]) -> dict[str, Any]:
    raw = context.get("_scion_trace_context") if isinstance(context, Mapping) else {}
    if not isinstance(raw, Mapping):
        raw = {}
    session_id = raw.get("session_id") or context.get("session_id")
    return _drop_empty(
        {
            "session_id": session_id,
            "request_id": raw.get("request_id") or context.get("request_id"),
            "branch_id": raw.get("branch_id") or context.get("branch_id"),
            "campaign_id": raw.get("campaign_id") or context.get("campaign_id"),
            "request_kind": raw.get("request_kind"),
            "call_kind": raw.get("call_kind"),
            "phase": raw.get("phase") or context.get("phase"),
            "attempt_number": raw.get("attempt_number")
            or raw.get("attempt")
            or context.get("agentic_hypothesis_retry_attempt"),
        }
    )


def _prompt_manifest_context(context: Mapping[str, Any]) -> dict[str, Any]:
    raw = context.get("_scion_prompt_manifest") if isinstance(context, Mapping) else {}
    return dict(raw) if isinstance(raw, Mapping) else {}


def _upsert_trace_record(
    *,
    index_path: Path,
    session_id: str,
    request_id: str,
    branch_id: str,
    campaign_id: str,
    trace_entry: Mapping[str, Any],
) -> None:
    payload = _read_index(index_path)
    sessions = _sessions_by_id(payload)
    session = sessions.get(session_id) or _new_session(
        session_id=session_id,
        request_id=request_id,
        branch_id=branch_id,
        campaign_id=campaign_id,
    )
    for key, value in (
        ("request_id", request_id),
        ("branch_id", branch_id),
        ("campaign_id", campaign_id),
    ):
        if value:
            session[key] = value
    traces = [
        dict(item)
        for item in session.get("traces", [])
        if isinstance(item, Mapping)
    ]
    trace_id = str(trace_entry.get("trace_id") or "")
    merged = False
    for index, existing in enumerate(traces):
        if str(existing.get("trace_id") or "") != trace_id:
            continue
        updated = dict(existing)
        updated.update({k: v for k, v in trace_entry.items() if v not in (None, "")})
        traces[index] = _drop_empty(updated)
        merged = True
        break
    if not merged and trace_id:
        traces.append(_drop_empty(dict(trace_entry)))
    session["traces"] = sorted(
        traces,
        key=lambda item: (
            str(item.get("created_at") or ""),
            str(item.get("trace_id") or ""),
        ),
    )
    _refresh_session_trace_lists(session)
    sessions[session_id] = session
    _write_index(index_path, list(sessions.values()))


def _upsert_session_final(
    *,
    index_path: Path,
    session_id: str,
    request_id: str,
    branch_id: str,
    campaign_id: str,
    final: Mapping[str, Any],
) -> None:
    payload = _read_index(index_path)
    sessions = _sessions_by_id(payload)
    session = sessions.get(session_id) or _new_session(
        session_id=session_id,
        request_id=request_id,
        branch_id=branch_id,
        campaign_id=campaign_id,
    )
    for key, value in (
        ("request_id", request_id),
        ("branch_id", branch_id),
        ("campaign_id", campaign_id),
    ):
        if value:
            session[key] = value
    session.update(
        {key: value for key, value in final.items() if value not in (None, "")}
    )
    _refresh_session_trace_lists(session)
    sessions[session_id] = session
    _write_index(index_path, list(sessions.values()))


def _new_session(
    *,
    session_id: str,
    request_id: str,
    branch_id: str,
    campaign_id: str,
) -> dict[str, Any]:
    now = datetime.now().isoformat()
    return _drop_empty(
        {
            "session_id": session_id,
            "request_id": request_id,
            "branch_id": branch_id,
            "campaign_id": campaign_id,
            "kind": "agentic_proposal_session",
            "created_at": now,
            "updated_at": now,
            "final_status": "pending",
            "traces": [],
            "hypothesis_trace_ids": [],
            "code_trace_ids": [],
            "trace_ids_by_kind": {},
        }
    )


def _refresh_session_trace_lists(session: dict[str, Any]) -> None:
    by_kind: dict[str, list[str]] = {}
    for trace in session.get("traces", []) or []:
        if not isinstance(trace, Mapping):
            continue
        trace_id = str(trace.get("trace_id") or "")
        kind = str(trace.get("request_kind") or trace.get("call_kind") or "").strip()
        if not trace_id or not kind:
            continue
        by_kind.setdefault(kind, [])
        if trace_id not in by_kind[kind]:
            by_kind[kind].append(trace_id)
    session["trace_ids_by_kind"] = by_kind
    session["hypothesis_trace_ids"] = [
        trace_id
        for kind, trace_ids in by_kind.items()
        if "hypothesis" in kind
        for trace_id in trace_ids
    ]
    session["code_trace_ids"] = [
        trace_id
        for kind, trace_ids in by_kind.items()
        if kind in {"code", "patch", "generate_code"} or "code" in kind
        for trace_id in trace_ids
    ]
    session["trace_count"] = sum(len(trace_ids) for trace_ids in by_kind.values())
    session["updated_at"] = datetime.now().isoformat()


def _read_index(index_path: Path) -> dict[str, Any]:
    if not index_path.exists():
        return {
            "schema_version": SESSION_TRACE_INDEX_SCHEMA_VERSION,
            "artifact_kind": "agentic_session_trace_index",
            "sessions": [],
        }
    try:
        raw = json.loads(index_path.read_text(encoding="utf-8"))
    except Exception:
        return {
            "schema_version": SESSION_TRACE_INDEX_SCHEMA_VERSION,
            "artifact_kind": "agentic_session_trace_index",
            "sessions": [],
        }
    if isinstance(raw, Mapping):
        sessions = raw.get("sessions")
        return {
            "schema_version": SESSION_TRACE_INDEX_SCHEMA_VERSION,
            "artifact_kind": "agentic_session_trace_index",
            "sessions": sessions if isinstance(sessions, list) else [],
        }
    if isinstance(raw, list):
        return {
            "schema_version": SESSION_TRACE_INDEX_SCHEMA_VERSION,
            "artifact_kind": "agentic_session_trace_index",
            "sessions": raw,
        }
    return {
        "schema_version": SESSION_TRACE_INDEX_SCHEMA_VERSION,
        "artifact_kind": "agentic_session_trace_index",
        "sessions": [],
    }


def _sessions_by_id(payload: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    sessions: dict[str, dict[str, Any]] = {}
    for item in payload.get("sessions", []) or []:
        if not isinstance(item, Mapping):
            continue
        session_id = str(item.get("session_id") or "").strip()
        if session_id:
            sessions[session_id] = dict(item)
    return sessions


def _write_index(index_path: Path, sessions: list[Mapping[str, Any]]) -> None:
    sessions = sorted(
        (dict(session) for session in sessions),
        key=lambda item: (
            str(item.get("updated_at") or ""),
            str(item.get("session_id") or ""),
        ),
    )
    payload = {
        "schema_version": SESSION_TRACE_INDEX_SCHEMA_VERSION,
        "artifact_kind": "agentic_session_trace_index",
        "updated_at": datetime.now().isoformat(),
        "session_count": len(sessions),
        "trace_count": sum(
            int(session.get("trace_count") or 0) for session in sessions
        ),
        "sessions": sessions,
    }
    index_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = index_path.with_suffix(index_path.suffix + f".{os.getpid()}.tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True, default=str),
        encoding="utf-8",
    )
    os.replace(tmp, index_path)


def _public_ref(path: str | Path, *, base_dir: str | Path) -> str:
    return (
        public_artifact_ref(path, base_dir=base_dir, kind="artifact")
        or Path(path).name
    )


def _public_ref_with_anchor(value: Any, *, base_dir: str | Path) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    path_text, sep, anchor = text.partition("#")
    public_ref = public_artifact_ref(path_text, base_dir=base_dir, kind="artifact")
    if not public_ref:
        public_ref = Path(path_text).name
    return f"{public_ref}{sep}{anchor}" if sep else public_ref


def _text_digest(value: str) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()[:16]


def _int_or_none(value: Any) -> int | None:
    try:
        if value in (None, ""):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _drop_empty(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        str(key): item
        for key, item in value.items()
        if item not in (None, "", (), [], {})
    }


__all__ = [
    "SESSION_TRACE_INDEX_NAME",
    "SESSION_TRACE_INDEX_SCHEMA_VERSION",
    "attach_agentic_trace_context",
    "attach_prompt_manifest_trace_context",
    "record_session_final",
    "record_trace_finish",
    "record_trace_start",
    "session_trace_index_path_for_artifact_dir",
    "session_trace_index_path_for_trace_dir",
    "trace_context_from_prompt_context",
]
