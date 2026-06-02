"""Generic active solver-design snapshot facade for proposal grounding."""

from __future__ import annotations

import ast
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any, Mapping, Sequence

from scion.problem.providers import (
    ProblemProviderError,
    resolve_active_solver_design_provider,
)

if TYPE_CHECKING:
    from scion.proposal.tools.models import ProposalToolContext

_SOURCE_PREVIEW_CHARS = 12000
_DIGEST_CHARS = 16


def build_active_solver_snapshot(
    context: ProposalToolContext,
    *,
    include_file_previews: bool = False,
    max_file_chars: int = _SOURCE_PREVIEW_CHARS,
) -> dict[str, Any]:
    """Return a provenance-bearing snapshot of the active solver-design code."""

    inputs = _active_solver_inputs(context)
    files = inputs["files"]
    readable_files = [
        item for item in files if item.get("readable") and item.get("active")
    ]
    entrypoint = _entrypoint_payload(context, inputs)
    call_graph = _solver_call_graph_payload(context, inputs)
    mechanism_summary = _mechanism_summary(context, inputs)
    inputs_with_summary = {
        **inputs,
        "entrypoint": entrypoint,
        "call_graph": call_graph,
        "mechanism_summary": mechanism_summary,
    }
    fact_packet = _active_algorithm_facts_payload(context, inputs_with_summary)

    payload: dict[str, Any] = {
        "surface": "solver_design",
        "active_surface": {
            "name": "solver_design",
            "entrypoint": _entrypoint_id(entrypoint),
            "role": "problem_object_solver_algorithm",
        },
        "provenance": inputs["provenance"],
        "source_digest": inputs["source_digest"],
        "entrypoint": entrypoint,
        "active_files": [item for item in files if item.get("active")],
        "inactive_files": [item for item in files if not item.get("active")],
        "call_graph": call_graph,
        "mechanism_summary": mechanism_summary,
        "active_algorithm_facts": fact_packet,
        "legacy_inactive_surface_exclusion": legacy_inactive_surface_exclusion(
            context,
            inputs_with_summary,
        ),
        "grounding_guidance": {
            "active_evidence_rule": (
                "Treat provider-declared active_files from the current source "
                "as active solver evidence for solver_design."
            ),
            "fact_packet_rule": (
                "Use active_algorithm_facts for compact mechanism claims; read "
                "full files or symbols only when implementation details are "
                "needed."
            ),
            "legacy_exclusion_rule": (
                "Do not cite inactive or legacy surfaces as proof that an active "
                "solver mechanism is present or absent."
            ),
        },
    }
    if include_file_previews:
        payload["file_previews"] = [
            read_algorithm_file_payload(
                context,
                str(item["file_path"]),
                max_chars=max_file_chars,
            )
            for item in readable_files
        ]
    return payload


def solver_call_graph_payload(context: ProposalToolContext) -> dict[str, Any]:
    return _solver_call_graph_payload(context, _active_solver_inputs(context))


def list_algorithm_files_payload(
    context: ProposalToolContext,
    *,
    include_inactive: bool = False,
) -> list[dict[str, Any]]:
    inputs = _active_solver_inputs(context)
    files = inputs["files"]
    if include_inactive:
        return list(files)
    return [item for item in files if item.get("active")]


def read_algorithm_file_payload(
    context: ProposalToolContext,
    file_path: str,
    *,
    max_chars: int,
) -> dict[str, Any]:
    inputs = _active_solver_inputs(context)
    allowed_files = _allowed_algorithm_files(inputs["manifest"])
    rel_path = _normalize_algorithm_file(file_path, allowed_files)
    source_overrides = inputs.get("source_overrides")
    source_kind = _source_kind_for_path(inputs, rel_path)
    if rel_path is None:
        safe_path = _safe_rejected_file_path(file_path)
        return {
            "file_path": safe_path,
            "path_rejected": True,
            "readable": False,
            "reason": "file_not_allowlisted_for_solver_design",
            "allowed_files": sorted(allowed_files),
            "source": source_kind,
        }
    artifact = (
        _read_code_file_from_overrides(
            source_overrides,
            rel_path,
            max_chars=max(0, max_chars),
        )
        or _read_code_file_from_root(
            inputs["source_root"] or "",
            rel_path,
            max_chars=max(0, max_chars),
            source_kind=source_kind,
        )
    )
    text = _file_text(
        inputs["source_root"],
        str(inputs["source_kind"]),
        rel_path,
        source_overrides=source_overrides,
    )
    line_coverage = _line_coverage_payload(
        content_preview=str(artifact.get("content_preview") or ""),
        source=text,
        truncated=bool(artifact.get("truncated")),
    )
    artifact.update(
        {
            "active": _is_active_algorithm_file(rel_path, inputs["manifest"]),
            "role": _role_for_path(rel_path, inputs["manifest"]),
            "module": _module_name(rel_path),
            "sha256": _sha256(text) if text else None,
            "digest": _sha256(text)[:_DIGEST_CHARS] if text else None,
            "content_digest": _sha256(text) if text else None,
            **line_coverage,
            "provenance": inputs["provenance"],
        }
    )
    return artifact


def read_algorithm_symbol_payload(
    context: ProposalToolContext,
    file_path: str,
    symbol: str,
    *,
    max_chars: int,
) -> dict[str, Any]:
    file_payload = read_algorithm_file_payload(
        context,
        file_path,
        max_chars=max(_SOURCE_PREVIEW_CHARS, max_chars),
    )
    if not file_payload.get("readable"):
        return file_payload
    source = str(file_payload.get("content_preview") or "")
    extracted = _extract_symbol_source(source, symbol)
    if extracted is None:
        return {
            "file_path": file_payload.get("file_path"),
            "symbol": symbol,
            "readable": False,
            "reason": "symbol_not_found",
            "available_symbols": _python_symbols(source),
            "source": file_payload.get("source"),
            "provenance": file_payload.get("provenance"),
        }
    symbol_source, start_line, end_line = extracted
    return {
        "file_path": file_payload.get("file_path"),
        "symbol": symbol,
        "readable": True,
        "source": file_payload.get("source"),
        "active": file_payload.get("active"),
        "role": file_payload.get("role"),
        "line_start": start_line,
        "line_end": end_line,
        "content_preview": _limit_text(symbol_source, max_chars),
        "truncated": len(symbol_source) > max_chars,
        "sha256": _sha256(symbol_source),
        "digest": _sha256(symbol_source)[:_DIGEST_CHARS],
        "provenance": file_payload.get("provenance"),
    }


def active_solver_source_root(
    context: ProposalToolContext,
) -> tuple[str | Path | None, str]:
    branch_workspace = str(context.branch_workspace or "").strip()
    if branch_workspace and os.path.isdir(branch_workspace):
        return branch_workspace, "branch_workspace"
    champion_path = str(_attr(context.champion, "code_snapshot_path", "") or "").strip()
    if champion_path and os.path.isdir(champion_path):
        return champion_path, "champion_snapshot"
    root_dir = str(_attr(context.problem_spec, "root_dir", "") or "").strip()
    if root_dir and os.path.isdir(root_dir):
        return root_dir, "problem_spec_root"
    return None, "missing_snapshot"


def legacy_inactive_surface_exclusion(
    context: ProposalToolContext | None = None,
    snapshot_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if context is not None and snapshot_context is not None:
        provider_payload = _provider_mapping(
            context,
            snapshot_context,
            "legacy_inactive_surface_exclusion",
        )
        if provider_payload:
            return dict(provider_payload)
    return {
        "rule": (
            "The active solver_design object is defined by the problem-owned "
            "active solver design provider. Inactive or legacy surfaces are not "
            "part of active solver evidence."
        ),
        "excluded_surface_policy": (
            "Inactive surfaces are omitted from active solver_design context "
            "unless the problem provider declares them."
        ),
        "excluded_files_or_hooks": [],
    }


def _active_solver_inputs(context: ProposalToolContext) -> dict[str, Any]:
    source_root, source_kind = active_solver_source_root(context)
    source_overrides = _branch_current_source_overrides(context)
    manifest = _merge_branch_current_manifest(
        _algorithm_file_manifest(context),
        source_overrides,
    )
    files = _list_algorithm_files_from_manifest(
        source_root,
        source_kind,
        manifest,
        source_overrides=source_overrides,
    )
    file_texts = {
        str(item["file_path"]): _file_text(
            source_root,
            source_kind,
            str(item["file_path"]),
            source_overrides=source_overrides,
        )
        for item in files
        if item.get("file_path")
    }
    file_digests = {
        path: _sha256(text)
        for path, text in file_texts.items()
        if text
    }
    source_digest = {
        "algorithm": "sha256",
        "snapshot_digest": _aggregate_digest(file_digests),
        "files": file_digests,
    }
    symbols = {
        path: _python_symbols(text)
        for path, text in file_texts.items()
        if text
    }
    provenance = _provenance_payload(context, source_kind)
    return {
        "provider": _active_solver_provider(context),
        "source_root": source_root,
        "source_kind": source_kind,
        "source_overrides": source_overrides,
        "manifest": manifest,
        "files": files,
        "file_texts": file_texts,
        "file_digests": file_digests,
        "source_digest": source_digest,
        "symbols": symbols,
        "provenance": provenance,
    }


def _algorithm_file_manifest(context: ProposalToolContext) -> tuple[dict[str, Any], ...]:
    provider = _active_solver_provider(context)
    method = getattr(provider, "active_solver_algorithm_file_manifest", None)
    if not callable(method):
        return ()
    raw_manifest = method(context)
    if not isinstance(raw_manifest, Sequence):
        return ()
    manifest: list[dict[str, Any]] = []
    for raw_item in raw_manifest:
        item = raw_item if isinstance(raw_item, Mapping) else {}
        normalized = _normalize_rel_path(str(item.get("file_path") or ""))
        if normalized is None:
            continue
        manifest.append(
            {
                **{
                    str(key): value
                    for key, value in item.items()
                    if str(key) not in {"file_path", "role", "active"}
                },
                "file_path": normalized,
                "role": str(item.get("role") or "active_algorithm_file"),
                "active": bool(item.get("active", True)),
            }
        )
    return tuple(manifest)


def _branch_current_source_overrides(context: ProposalToolContext) -> dict[str, str]:
    raw = getattr(context, "branch_current_file_sources", None)
    if not isinstance(raw, Mapping):
        return {}
    overrides: dict[str, str] = {}
    for path, content in raw.items():
        normalized = _normalize_rel_path(str(path or ""))
        if normalized is None or not isinstance(content, str):
            continue
        overrides[normalized] = content
    return overrides


def _merge_branch_current_manifest(
    manifest: Sequence[Mapping[str, Any]],
    source_overrides: Mapping[str, str],
) -> tuple[dict[str, Any], ...]:
    rows = [dict(item) for item in manifest]
    existing_paths = {
        str(item.get("file_path") or "")
        for item in rows
        if str(item.get("file_path") or "")
    }
    for path in source_overrides:
        if path in existing_paths:
            continue
        rows.append(
            {
                "file_path": path,
                "role": "branch_current_algorithm_file",
                "active": True,
                "branch_current": True,
            }
        )
        existing_paths.add(path)
    return tuple(rows)


def _list_algorithm_files_from_manifest(
    source_root: str | Path | None,
    source_kind: str,
    manifest: Sequence[Mapping[str, Any]],
    *,
    source_overrides: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in manifest:
        rel_path = str(item.get("file_path") or "")
        artifact = (
            _read_code_file_from_overrides(
                source_overrides,
                rel_path,
                max_chars=0,
            )
            or _read_code_file_from_root(
                source_root or "",
                rel_path,
                max_chars=0,
                source_kind=source_kind,
            )
        )
        text = _file_text(
            source_root,
            source_kind,
            rel_path,
            source_overrides=source_overrides,
        )
        row = {
            **{
                str(key): value
                for key, value in item.items()
                if str(key) not in {"file_path", "role", "active"}
            },
            "file_path": rel_path,
            "module": _module_name(rel_path),
            "role": str(item.get("role") or ""),
            "active": bool(item.get("active")),
            "readable": bool(artifact.get("readable")),
            "reason": artifact.get("reason"),
            "source": artifact.get("source") or source_kind,
            "size_chars": len(text) if text else artifact.get("size_chars"),
            "sha256": _sha256(text) if text else None,
            "digest": _sha256(text)[:_DIGEST_CHARS] if text else None,
        }
        rows.append(row)
    return rows


def _entrypoint_payload(
    context: ProposalToolContext,
    snapshot_context: Mapping[str, Any],
) -> dict[str, Any]:
    provider_payload = _provider_mapping(
        context,
        snapshot_context,
        "active_solver_entrypoint_summary",
    )
    if provider_payload:
        return dict(provider_payload)
    return {
        "readable": False,
        "source": snapshot_context.get("source_kind"),
        "summary": "No problem-owned active solver entrypoint was declared.",
    }


def _solver_call_graph_payload(
    context: ProposalToolContext,
    snapshot_context: Mapping[str, Any],
) -> dict[str, Any]:
    symbols = snapshot_context.get("symbols")
    symbols = symbols if isinstance(symbols, Mapping) else {}
    edges = _provider_sequence(
        context,
        snapshot_context,
        "active_solver_call_graph_edges",
    )
    return {
        "surface": "solver_design",
        "provenance": snapshot_context.get("provenance"),
        "source_digest": {
            "algorithm": "sha256",
            "snapshot_digest": _snapshot_digest(snapshot_context),
        },
        "nodes": _call_graph_nodes(
            symbols,
            snapshot_context.get("manifest") or (),
        ),
        "edges": list(edges),
        "legacy_inactive_surface_exclusion": legacy_inactive_surface_exclusion(
            context,
            snapshot_context,
        ),
    }


def _mechanism_summary(
    context: ProposalToolContext,
    snapshot_context: Mapping[str, Any],
) -> dict[str, Any]:
    return dict(
        _provider_mapping(
            context,
            snapshot_context,
            "active_solver_mechanism_summary",
        )
    )


def _active_algorithm_facts_payload(
    context: ProposalToolContext,
    snapshot_context: Mapping[str, Any],
) -> dict[str, Any]:
    packet = dict(
        _provider_mapping(
            context,
            snapshot_context,
            "active_algorithm_facts",
        )
    )
    if not packet:
        return {}
    packet.setdefault("snapshot_digest", _snapshot_digest(snapshot_context))
    packet.setdefault("facts", [])
    packet.setdefault("fact_packet_digest", _fact_packet_digest(packet))
    return packet


def _provider_mapping(
    context: ProposalToolContext,
    snapshot_context: Mapping[str, Any],
    method_name: str,
) -> Mapping[str, Any]:
    provider = snapshot_context.get("provider") or _active_solver_provider(context)
    method = getattr(provider, method_name, None)
    if not callable(method):
        return {}
    payload = method(context, snapshot_context)
    return payload if isinstance(payload, Mapping) else {}


def _provider_sequence(
    context: ProposalToolContext,
    snapshot_context: Mapping[str, Any],
    method_name: str,
) -> Sequence[Any]:
    provider = snapshot_context.get("provider") or _active_solver_provider(context)
    method = getattr(provider, method_name, None)
    if not callable(method):
        return ()
    payload = method(context, snapshot_context)
    if isinstance(payload, (str, bytes)) or not isinstance(payload, Sequence):
        return ()
    return payload


def _active_solver_provider(context: ProposalToolContext) -> Any | None:
    try:
        return resolve_active_solver_design_provider(
            problem_spec=context.problem_spec,
            adapter=context.adapter,
        )
    except ProblemProviderError:
        return None


def _entrypoint_id(entrypoint: Mapping[str, Any]) -> str:
    file_path = str(entrypoint.get("file_path") or "").strip()
    symbol = str(entrypoint.get("symbol") or "").strip()
    if file_path and symbol:
        return f"{file_path}::{symbol}"
    return file_path or symbol or ""


def _snapshot_digest(snapshot_context: Mapping[str, Any]) -> str:
    source_digest = snapshot_context.get("source_digest")
    if isinstance(source_digest, Mapping):
        digest = source_digest.get("snapshot_digest")
        if digest:
            return str(digest)
    return ""


def _provenance_payload(
    context: ProposalToolContext,
    source_kind: str,
) -> dict[str, Any]:
    return {
        "source": source_kind,
        "branch_id": context.branch_id,
        "base_champion_id": _attr(context.branch, "base_champion_id"),
        "base_champion_hash": _attr(context.branch, "base_champion_hash"),
        "champion_version": _attr(context.champion, "version"),
        "champion_code_snapshot_hash": _attr(context.champion, "code_snapshot_hash"),
    }


def _call_graph_nodes(
    symbols: Mapping[str, list[str]],
    manifest: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    for item in manifest:
        if not item.get("active"):
            continue
        rel_path = str(item.get("file_path") or "")
        nodes.append(
            {
                "file_path": rel_path,
                "module": _module_name(rel_path),
                "role": str(item.get("role") or ""),
                "symbols": symbols.get(rel_path, []),
            }
        )
    return nodes


def _file_text(
    source_root: str | Path | None,
    source_kind: str,
    rel_path: str,
    *,
    source_overrides: Mapping[str, str] | None = None,
) -> str:
    normalized = _normalize_rel_path(rel_path)
    if normalized is not None and isinstance(source_overrides, Mapping):
        content = source_overrides.get(normalized)
        if isinstance(content, str):
            return content
    if source_root is None:
        return ""
    artifact = _read_code_file_from_root(
        source_root,
        rel_path,
        max_chars=10_000_000,
        source_kind=source_kind,
    )
    if not artifact.get("readable"):
        return ""
    return str(artifact.get("content_preview") or "")


def _source_kind_for_path(inputs: Mapping[str, Any], rel_path: str | None) -> str:
    if rel_path:
        overrides = inputs.get("source_overrides")
        if isinstance(overrides, Mapping) and rel_path in overrides:
            return "branch_current_file_sources"
    return str(inputs.get("source_kind") or "")


def _line_coverage_payload(
    *,
    content_preview: str,
    source: str,
    truncated: bool,
) -> dict[str, Any]:
    total_lines = len(source.splitlines()) if source else 0
    covered_lines = len(content_preview.splitlines()) if content_preview else 0
    if total_lines and content_preview.endswith("\n"):
        covered_lines = max(covered_lines, 1)
    if total_lines == 0:
        return {
            "coverage_status": "unreadable_or_empty",
            "line_start": None,
            "line_end": None,
            "covered_line_count": 0,
            "total_line_count": 0,
        }
    return {
        "coverage_status": "truncated" if truncated else "full",
        "line_start": 1 if covered_lines else None,
        "line_end": covered_lines if covered_lines else None,
        "covered_line_count": covered_lines,
        "total_line_count": total_lines,
    }


def _python_symbols(source: str) -> list[str]:
    if not source:
        return []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    symbols: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            symbols.append(node.name)
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    symbols.append(f"{node.name}.{child.name}")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            symbols.append(node.name)
    return symbols


def _extract_symbol_source(
    source: str,
    symbol: str,
) -> tuple[str, int, int] | None:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    wanted = str(symbol or "").strip()
    if not wanted:
        return None
    lines = source.splitlines()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        names = [node.name]
        parent_name = _parent_class_name(tree, node)
        if parent_name:
            names.append(f"{parent_name}.{node.name}")
        if wanted not in names:
            continue
        start = int(getattr(node, "lineno", 1))
        end = int(getattr(node, "end_lineno", start))
        return "\n".join(lines[start - 1 : end]), start, end
    return None


def _parent_class_name(tree: ast.AST, target: ast.AST) -> str | None:
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        if any(child is target for child in node.body):
            return node.name
    return None


def _normalize_algorithm_file(file_path: str, allowed_files: set[str]) -> str | None:
    normalized = str(file_path or "").replace(os.sep, "/").lstrip("/")
    if normalized in allowed_files:
        return normalized
    return None


def _allowed_algorithm_files(manifest: Sequence[Mapping[str, Any]]) -> set[str]:
    return {
        str(item.get("file_path"))
        for item in manifest
        if str(item.get("file_path") or "").strip()
    }


def _safe_rejected_file_path(file_path: str) -> str:
    normalized = _normalize_rel_path(file_path)
    if normalized is None:
        return "<path_rejected>"
    return normalized


def _normalize_rel_path(path: str) -> str | None:
    raw = str(path or "").strip().replace("\\", "/")
    if not raw:
        return None
    if raw.startswith(("/", "~")) or (len(raw) >= 2 and raw[1] == ":"):
        return None
    pure = PurePosixPath(raw)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        return None
    return pure.as_posix()


def _read_code_file_from_root(
    root_path: str | Path,
    target_file: str,
    *,
    max_chars: int,
    source_kind: str,
) -> dict[str, Any]:
    normalized = _normalize_rel_path(target_file)
    if normalized is None:
        return {
            "file_path": "<path_rejected>",
            "path_rejected": True,
            "readable": False,
            "reason": "unsafe_relative_path",
            "source": source_kind,
        }
    if not root_path:
        return {
            "file_path": normalized,
            "readable": False,
            "reason": "not_found",
            "source": source_kind,
        }
    root = Path(root_path).expanduser().resolve()
    unresolved_path = root / normalized
    if _path_has_symlink_component(root, normalized):
        return {
            "file_path": normalized,
            "readable": False,
            "reason": "symlink_not_allowed",
            "source": source_kind,
        }
    path = unresolved_path.resolve()
    if path != root and root not in path.parents:
        return {
            "file_path": normalized,
            "readable": False,
            "reason": "path_escapes_snapshot",
            "source": source_kind,
        }
    if not path.is_file():
        return {
            "file_path": normalized,
            "readable": False,
            "reason": "not_found",
            "source": source_kind,
        }
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        return {
            "file_path": normalized,
            "readable": False,
            "reason": f"unreadable:{exc}",
            "source": source_kind,
        }
    max_chars = max(0, int(max_chars))
    return {
        "file_path": normalized,
        "readable": True,
        "source": source_kind,
        "content_preview": _limit_text(content, max_chars),
        "truncated": len(content) > max_chars,
        "size_chars": len(content),
        "max_chars": max_chars,
    }


def _read_code_file_from_overrides(
    source_overrides: Mapping[str, str] | None,
    target_file: str,
    *,
    max_chars: int,
) -> dict[str, Any] | None:
    normalized = _normalize_rel_path(target_file)
    if normalized is None or not isinstance(source_overrides, Mapping):
        return None
    content = source_overrides.get(normalized)
    if not isinstance(content, str):
        return None
    max_chars = max(0, int(max_chars))
    return {
        "file_path": normalized,
        "readable": True,
        "source": "branch_current_file_sources",
        "content_preview": _limit_text(content, max_chars),
        "truncated": len(content) > max_chars,
        "size_chars": len(content),
        "max_chars": max_chars,
    }


def _path_has_symlink_component(root: Path, normalized_rel_path: str) -> bool:
    current = root
    for part in PurePosixPath(normalized_rel_path).parts:
        current = current / part
        if current.is_symlink():
            return True
    return False


def _attr(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _limit_text(text: Any, max_chars: int) -> str:
    value = str(text or "")
    max_chars = max(0, int(max_chars))
    if len(value) <= max_chars:
        return value
    if max_chars <= 3:
        return value[:max_chars]
    return value[: max_chars - 3].rstrip() + "..."


def _is_active_algorithm_file(
    rel_path: str,
    manifest: Sequence[Mapping[str, Any]],
) -> bool:
    return any(
        str(item.get("file_path") or "") == rel_path and bool(item.get("active"))
        for item in manifest
    )


def _role_for_path(rel_path: str, manifest: Sequence[Mapping[str, Any]]) -> str:
    for item in manifest:
        if str(item.get("file_path") or "") == rel_path:
            return str(item.get("role") or "")
    return ""


def _module_name(rel_path: str) -> str:
    path = rel_path.removesuffix(".py").replace("/", ".")
    return path


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _aggregate_digest(digests: Mapping[str, str]) -> str:
    joined = "\n".join(f"{path}:{digest}" for path, digest in sorted(digests.items()))
    return _sha256(joined) if joined else ""


def _fact_packet_digest(packet: Mapping[str, Any]) -> str:
    digest_payload = {
        key: value
        for key, value in packet.items()
        if key != "fact_packet_digest"
    }
    encoded = json.dumps(
        digest_payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


__all__ = [
    "active_solver_source_root",
    "build_active_solver_snapshot",
    "legacy_inactive_surface_exclusion",
    "list_algorithm_files_payload",
    "read_algorithm_file_payload",
    "read_algorithm_symbol_payload",
    "solver_call_graph_payload",
]
