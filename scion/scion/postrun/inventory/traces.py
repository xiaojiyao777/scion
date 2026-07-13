"""LLM trace inventory readers."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from scion.postrun.inventory.utils import (
    _branch_id,
    _first_string,
    _read_json,
)


def _read_llm_traces(
    trace_dir: Path,
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

    return {
        "trace_count": len(trace_files),
        "by_kind": by_kind,
        "by_status": by_status,
        "index_trace_count": 0,
        "index_session_count": 0,
        "traces_by_branch": file_traces_by_branch,
        "sessions_by_branch": Counter(),
    }


def _llm_trace_summary(llm_traces: dict[str, Any]) -> dict[str, Any]:
    return {
        "trace_count": llm_traces["trace_count"],
        "by_kind": dict(sorted(llm_traces["by_kind"].items())),
        "by_status": dict(sorted(llm_traces["by_status"].items())),
        "index_trace_count": 0,
        "index_session_count": 0,
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
    if value in {"hypothesis", "code"}:
        return value
    if "hypothesis" in name:
        return "hypothesis"
    if "code" in name:
        return "code"
    return "unknown"


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
