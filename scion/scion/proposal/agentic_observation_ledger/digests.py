"""Source digest, normalized argument, and coverage helpers."""
from __future__ import annotations

import hashlib
from typing import Any, Mapping

from scion.proposal.active_solver_snapshot import (
    build_active_solver_snapshot,
    list_algorithm_files_payload,
    read_algorithm_symbol_payload,
    solver_call_graph_payload,
)
from scion.proposal.active_solver_map import (
    read_active_solver_map_payload,
    read_algorithm_slice_payload,
    read_operator_registry_payload,
)
from scion.proposal.agentic_utils import _drop_empty_dict, _sanitize_agentic_value
from scion.proposal.prompt_manifest import stable_digest
from scion.proposal.tools import ProposalToolContext

from scion.proposal.agentic_observation_ledger.utils import (
    coerce_int,
    normalize_path,
)

_SOLVER_SOURCE_READ_HEADROOM_CHARS = 96000


def normalize_tool_args(tool_name: str, args: Mapping[str, Any]) -> dict[str, Any]:
    raw = dict(args or {})
    if tool_name in {
        "context.read_active_solver_map",
        "context.read_operator_registry",
        "context.read_algorithm_slice",
        "context.read_active_solver_design",
        "context.read_solver_call_graph",
        "context.list_algorithm_files",
        "context.read_algorithm_file",
        "context.read_algorithm_symbol",
    }:
        if raw.get("surface") in (None, ""):
            raw.pop("surface", None)
    if tool_name == "context.read_active_solver_design":
        raw.setdefault("include_file_previews", False)
        raw.setdefault("max_file_chars", 6000)
    elif tool_name == "context.read_active_solver_map":
        pass
    elif tool_name == "context.read_operator_registry":
        pass
    elif tool_name == "context.read_algorithm_slice":
        raw.setdefault("max_chars", 12000)
    elif tool_name == "context.list_algorithm_files":
        raw.setdefault("include_inactive", True)
    elif tool_name in {"context.read_algorithm_file", "context.read_algorithm_symbol"}:
        raw["file_path"] = normalize_path(raw.get("file_path"))
        raw.setdefault("max_chars", _SOLVER_SOURCE_READ_HEADROOM_CHARS)
    elif tool_name == "context.read_surface":
        raw.setdefault("detail", "compact")
        raw.setdefault("section", "all")
        raw.setdefault("include_code", True)
        if "target_file" in raw:
            raw["target_file"] = normalize_path(raw.get("target_file"))
    return _sanitize_agentic_value(raw)


def coverage_payload(
    tool_name: str,
    payload: Mapping[str, Any],
    normalized_args: Mapping[str, Any],
) -> dict[str, Any]:
    if tool_name == "context.read_surface":
        artifact = payload.get("current_artifact")
        if isinstance(artifact, Mapping):
            return content_coverage_payload(
                artifact,
                requested_max=coerce_int(normalized_args.get("max_code_chars")),
            )
        return {"coverage_status": "metadata_only"}
    requested_max = requested_max_chars(tool_name, normalized_args)
    return content_coverage_payload(payload, requested_max=requested_max)


def content_coverage_payload(
    payload: Mapping[str, Any],
    *,
    requested_max: int | None,
) -> dict[str, Any]:
    content = payload.get("content_preview")
    if content is None:
        content = payload.get("content")
    preview_chars = len(str(content)) if content is not None else None
    size_chars = coerce_int(payload.get("size_chars"))
    max_chars = coerce_int(payload.get("max_chars"))
    if max_chars is None:
        max_chars = requested_max
    truncated = bool(payload.get("truncated"))
    if preview_chars is None:
        status = "metadata_only"
    elif not truncated and size_chars is not None and preview_chars >= size_chars:
        status = "full"
    elif not truncated:
        status = "sufficient_preview"
    else:
        status = "truncated_preview"
    return _drop_empty_dict(
        {
            "coverage_status": status,
            "max_chars": max_chars,
            "requested_max_chars": requested_max,
            "content_preview_chars": preview_chars,
            "size_chars": size_chars,
            "truncated": truncated,
        }
    )


def source_digest_payload(tool_name: str, payload: Mapping[str, Any]) -> Any:
    receipt = payload.get("read_receipt")
    if isinstance(receipt, Mapping):
        return _drop_empty_dict(
            {
                "digest": receipt.get("digest"),
                "snapshot_digest": receipt.get("snapshot_digest"),
                "content_digest": receipt.get("content_digest"),
                "source": tool_name,
            }
        )
    source_digest = payload.get("source_digest")
    if isinstance(source_digest, Mapping):
        return _sanitize_agentic_value(dict(source_digest))
    if tool_name == "context.list_algorithm_files":
        files = payload.get("files")
        if isinstance(files, (list, tuple)):
            return file_list_digest(files)
    if tool_name == "context.read_surface":
        artifact = payload.get("current_artifact")
        if isinstance(artifact, Mapping):
            return _drop_empty_dict(
                {
                    "digest": artifact.get("digest"),
                    "sha256": artifact.get("sha256"),
                    "source": artifact.get("source"),
                }
            )
    return _drop_empty_dict(
        {
            "digest": payload.get("digest"),
            "sha256": payload.get("sha256"),
            "source": payload.get("source"),
        }
    )


def file_list_digest(files: Any) -> dict[str, Any]:
    digests: dict[str, str] = {}
    if isinstance(files, (list, tuple)):
        for item in files:
            if not isinstance(item, Mapping):
                continue
            path = normalize_path(item.get("file_path"))
            digest = str(item.get("sha256") or item.get("digest") or "").strip()
            if path and digest:
                digests[path] = digest
    joined = "\n".join(f"{path}:{digest}" for path, digest in sorted(digests.items()))
    snapshot_digest = hashlib.sha256(joined.encode("utf-8")).hexdigest() if joined else ""
    return _drop_empty_dict(
        {
            "algorithm": "sha256",
            "snapshot_digest": snapshot_digest,
            "files": digests,
        }
    )


def primary_digest(payload: Mapping[str, Any], source_digest: Any) -> str:
    for key in ("digest", "sha256"):
        value = str(payload.get(key) or "").strip()
        if value:
            return value[:16] if key == "sha256" else value
    if isinstance(source_digest, Mapping):
        for key in ("snapshot_digest", "digest", "sha256"):
            value = str(source_digest.get(key) or "").strip()
            if value:
                return value[:16]
    return stable_digest(source_digest or payload, length=16)


def requested_max_chars(tool_name: str, args: Mapping[str, Any]) -> int:
    if tool_name == "context.read_surface":
        return coerce_int(args.get("max_code_chars")) or 0
    return coerce_int(args.get("max_chars")) or 0


def snapshot_digest_from_source(source_digest: Any) -> str:
    if not isinstance(source_digest, Mapping):
        return ""
    return str(source_digest.get("snapshot_digest") or "").strip()


def current_source_digest(
    context: ProposalToolContext,
    tool_name: str,
    normalized_args: Mapping[str, Any],
) -> Any:
    if tool_name == "context.read_active_solver_map":
        payload = read_active_solver_map_payload(
            context,
            surface=normalized_args.get("surface"),
            subject_id=normalized_args.get("subject_id"),
        )
        return source_digest_payload(tool_name, payload)
    if tool_name == "context.read_operator_registry":
        payload = read_operator_registry_payload(
            context,
            registry_id=str(normalized_args.get("registry_id") or ""),
            surface=normalized_args.get("surface"),
            subject_id=normalized_args.get("subject_id"),
        )
        return source_digest_payload(tool_name, payload)
    if tool_name == "context.read_algorithm_slice":
        payload = read_algorithm_slice_payload(
            context,
            slice_id=str(normalized_args.get("slice_id") or ""),
            surface=normalized_args.get("surface"),
            subject_id=normalized_args.get("subject_id"),
            max_chars=coerce_int(normalized_args.get("max_chars")) or 0,
        )
        return source_digest_payload(tool_name, payload)
    if tool_name == "context.read_active_solver_design":
        payload = build_active_solver_snapshot(context, include_file_previews=False)
        return source_digest_payload(tool_name, payload)
    if tool_name == "context.read_solver_call_graph":
        payload = solver_call_graph_payload(context)
        return source_digest_payload(tool_name, payload)
    if tool_name == "context.list_algorithm_files":
        files = list_algorithm_files_payload(context, include_inactive=True)
        return file_list_digest(files)
    if tool_name == "context.read_algorithm_file":
        path = normalize_path(normalized_args.get("file_path"))
        for item in list_algorithm_files_payload(context, include_inactive=True):
            if normalize_path(item.get("file_path")) == path:
                return {
                    "digest": item.get("digest"),
                    "sha256": item.get("sha256"),
                }
        return None
    if tool_name == "context.read_algorithm_symbol":
        payload = read_algorithm_symbol_payload(
            context,
            normalize_path(normalized_args.get("file_path")),
            str(normalized_args.get("symbol") or ""),
            max_chars=0,
        )
        return {
            "digest": payload.get("digest"),
            "sha256": payload.get("sha256"),
        }
    if tool_name == "context.read_surface":
        target_file = normalize_path(normalized_args.get("target_file"))
        if not target_file:
            return None
        for item in list_algorithm_files_payload(context, include_inactive=True):
            if normalize_path(item.get("file_path")) == target_file:
                return {
                    "digest": item.get("digest"),
                    "sha256": item.get("sha256"),
                }
    return None


__all__ = [
    "content_coverage_payload",
    "coverage_payload",
    "current_source_digest",
    "file_list_digest",
    "normalize_tool_args",
    "primary_digest",
    "requested_max_chars",
    "snapshot_digest_from_source",
    "source_digest_payload",
]
