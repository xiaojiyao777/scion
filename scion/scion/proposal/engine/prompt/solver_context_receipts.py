"""Static solver context and source receipt projections for prompts."""

from __future__ import annotations

import hashlib
from typing import Any

from scion.proposal.engine.prompt.formatting import (
    _drop_empty,
    _stable_short_digest,
)
from scion.proposal.engine.prompt.tool_receipts import _surface_identity


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
