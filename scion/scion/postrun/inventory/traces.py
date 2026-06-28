"""LLM trace inventory readers."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from scion.postrun.inventory.utils import (
    _branch_id,
    _contains_key_fragment,
    _first_string,
    _max_counter,
    _read_json,
)


def _read_llm_traces(
    trace_dir: Path,
    *,
    trace_index: Any,
    session_index: Any,
) -> dict[str, Any]:
    by_kind: Counter[str] = Counter()
    by_status: Counter[str] = Counter()
    file_traces_by_branch: Counter[str] = Counter()
    trace_files = sorted(trace_dir.glob("*.json")) if trace_dir.exists() else []
    for path in trace_files:
        doc = _read_json(path)
        kind = _trace_kind(doc, path)
        status = _trace_status(doc)
        by_kind[kind] += 1
        by_status[status] += 1
        branch_id = _branch_id(doc)
        if branch_id:
            file_traces_by_branch[branch_id] += 1

    trace_entries = _trace_index_entries(trace_index)
    session_entries = _session_index_entries(session_index)

    index_traces_by_branch: Counter[str] = Counter()
    for entry in trace_entries:
        branch_id = _branch_id(entry)
        if branch_id:
            index_traces_by_branch[branch_id] += 1

    sessions_by_branch: Counter[str] = Counter()
    for entry in session_entries:
        branch_id = _branch_id(entry)
        if branch_id:
            sessions_by_branch[branch_id] += 1

    return {
        "trace_count": len(trace_files),
        "by_kind": by_kind,
        "by_status": by_status,
        "index_trace_count": len(trace_entries),
        "index_session_count": len(session_entries),
        "traces_by_branch": _max_counter(file_traces_by_branch, index_traces_by_branch),
        "sessions_by_branch": sessions_by_branch,
    }


def _llm_trace_summary(llm_traces: dict[str, Any]) -> dict[str, Any]:
    return {
        "trace_count": llm_traces["trace_count"],
        "by_kind": dict(sorted(llm_traces["by_kind"].items())),
        "by_status": dict(sorted(llm_traces["by_status"].items())),
        "index_trace_count": llm_traces["index_trace_count"],
        "index_session_count": llm_traces["index_session_count"],
    }


def _empty_llm_trace_summary() -> dict[str, Any]:
    return {
        "trace_count": 0,
        "by_kind": {},
        "by_status": {},
        "index_trace_count": 0,
        "index_session_count": 0,
    }


def _trace_kind(doc: Any, path: Path) -> str:
    name = path.name.lower()
    if "target_intent" in name:
        return "hypothesis_target_intent"
    value = _first_string(
        doc,
        keys=(
            "trace_kind",
            "request_kind",
            "call_kind",
            "kind",
            "stage",
            "phase",
            "llm_stage",
        ),
    )
    if value and "target_intent" in value.lower():
        return "hypothesis_target_intent"
    if value:
        return value
    if "hypothesis" in name:
        return "hypothesis"
    if "code" in name:
        return "code"
    return "unknown"


def _is_target_intent_trace(doc: Any, path: Path | None) -> bool:
    if path is not None and "target_intent" in path.name.lower():
        return True
    if not isinstance(doc, dict):
        return False
    value = _first_string(
        doc,
        keys=("trace_kind", "request_kind", "call_kind", "kind", "phase", "stage"),
    )
    if value and "target_intent" in value.lower():
        return True
    return _contains_key_fragment(doc, ("target_intent",))


def _prompt_manifest_ref_present(doc: Any) -> bool:
    if not isinstance(doc, dict):
        return False
    if _first_string(
        doc,
        keys=(
            "prompt_manifest_artifact_ref",
            "prompt_manifest_ref",
            "prompt_manifest",
        ),
    ):
        return True
    refs = doc.get("prompt_manifest_artifact_refs") or doc.get("prompt_manifest_refs")
    return isinstance(refs, list) and bool(refs)


def _trace_status(doc: Any) -> str:
    value = _first_string(
        doc,
        keys=("status", "final_status", "result_status", "termination_reason"),
    )
    if value:
        return value
    if isinstance(doc, dict):
        if doc.get("ok") is True:
            return "ok"
        if doc.get("ok") is False:
            return "failed"
        response = doc.get("response")
        if isinstance(response, dict) and response.get("status"):
            return str(response["status"])
    return "unknown"


def _trace_index_entries(index_doc: Any) -> list[Any]:
    if isinstance(index_doc, list):
        return index_doc
    if isinstance(index_doc, dict):
        value = index_doc.get("traces")
        if isinstance(value, list):
            return value
        sessions = index_doc.get("sessions")
        if isinstance(sessions, list):
            entries: list[Any] = []
            for session in sessions:
                if not isinstance(session, dict):
                    continue
                branch_id = _branch_id(session)
                traces = session.get("traces")
                if not isinstance(traces, list):
                    continue
                for trace in traces:
                    if isinstance(trace, dict) and branch_id and not _branch_id(trace):
                        trace = {**trace, "branch_id": branch_id}
                    entries.append(trace)
            return entries
        for key in ("entries", "items"):
            value = index_doc.get(key)
            if isinstance(value, list):
                return value
    return []


def _session_index_entries(index_doc: Any) -> list[Any]:
    if isinstance(index_doc, list):
        return index_doc
    if isinstance(index_doc, dict):
        for key in ("sessions", "entries", "items"):
            value = index_doc.get(key)
            if isinstance(value, list):
                return value
    return []
