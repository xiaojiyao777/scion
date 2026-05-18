"""Active solver-design snapshot for controlled proposal grounding."""

from __future__ import annotations

import ast
import hashlib
import os
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any, Mapping

if TYPE_CHECKING:
    from scion.proposal.tools.models import ProposalToolContext

_SOURCE_PREVIEW_CHARS = 12000
_DIGEST_CHARS = 16

_ALGORITHM_FILE_ROLES: tuple[tuple[str, str, bool], ...] = (
    ("policies/baseline_algorithm.py", "active_entrypoint", True),
    ("policies/baseline_modules/scheduler.py", "active_scheduler_alns_vns", True),
    ("policies/baseline_modules/construction.py", "active_construction", True),
    ("policies/baseline_modules/destroy_repair.py", "active_destroy_repair", True),
    ("policies/baseline_modules/local_search.py", "active_local_search_vns", True),
    ("policies/baseline_modules/acceptance.py", "active_acceptance_weights", True),
    ("policies/baseline_modules/config.py", "active_runtime_config", True),
    ("policies/baseline_modules/state.py", "active_solution_state", True),
    ("policies/solver_algorithm.py", "compatibility_hook_not_primary", False),
)

_ALLOWED_ALGORITHM_FILES = frozenset(path for path, _, _ in _ALGORITHM_FILE_ROLES)


def build_active_solver_snapshot(
    context: ProposalToolContext,
    *,
    include_file_previews: bool = False,
    max_file_chars: int = _SOURCE_PREVIEW_CHARS,
) -> dict[str, Any]:
    """Return a provenance-bearing snapshot of the active solver-design code."""

    source_root, source_kind = active_solver_source_root(context)
    provenance = _provenance_payload(context, source_root, source_kind)
    files = list_algorithm_files_payload(context, include_inactive=True)
    readable_files = [
        item for item in files if item.get("readable") and item.get("active")
    ]
    digests = {
        str(item["file_path"]): str(item["sha256"])
        for item in files
        if item.get("sha256")
    }
    snapshot_digest = _aggregate_digest(digests)

    payload: dict[str, Any] = {
        "surface": "solver_design",
        "active_surface": {
            "name": "solver_design",
            "entrypoint": "policies/baseline_algorithm.py::solve",
            "role": "problem_object_solver_algorithm",
        },
        "provenance": provenance,
        "source_digest": {
            "algorithm": "sha256",
            "snapshot_digest": snapshot_digest,
            "files": digests,
        },
        "entrypoint": _entrypoint_payload(source_root, source_kind),
        "active_files": [item for item in files if item.get("active")],
        "inactive_files": [item for item in files if not item.get("active")],
        "call_graph": solver_call_graph_payload(context),
        "mechanism_summary": _mechanism_summary(source_root, source_kind),
        "legacy_inactive_surface_exclusion": legacy_inactive_surface_exclusion(),
        "grounding_guidance": {
            "active_evidence_rule": (
                "Treat branch_workspace or champion_snapshot code in active_files "
                "as active solver evidence for solver_design."
            ),
            "legacy_exclusion_rule": (
                "Do not cite compact component surfaces or compatibility hooks as "
                "proof that an active solver mechanism is absent."
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
    source_root, source_kind = active_solver_source_root(context)
    files = {
        path: _file_text(source_root, source_kind, path)
        for path, _, active in _ALGORITHM_FILE_ROLES
        if active
    }
    symbols = {
        path: _python_symbols(text)
        for path, text in files.items()
        if text
    }
    edges = [
        {
            "from": "policies/baseline_algorithm.py::solve",
            "to": "policies/baseline_modules/scheduler.py::_ALNSVNSSolver.__init__",
            "mechanism": "entrypoint wires config and context into scheduler",
            "evidence": ["baseline_algorithm.py imports _ALNSVNSSolver"],
        },
        {
            "from": "policies/baseline_algorithm.py::solve",
            "to": "policies/baseline_modules/scheduler.py::_ALNSVNSSolver.solve",
            "mechanism": "entrypoint delegates the active search and adapts output",
            "evidence": ["solver.solve(instance, rng)", "context.make_solution(...)"],
        },
        {
            "from": "scheduler._ALNSVNSSolver.solve",
            "to": "scheduler._ALNSVNSSolver._initial_solution",
            "mechanism": "seed construction before ALNS loop",
            "evidence": ["current = self._initial_solution(instance, reserve)"],
        },
        {
            "from": "scheduler._ALNSVNSSolver._initial_solution",
            "to": "construction",
            "mechanism": (
                "uses sweep for large instances, Clarke-Wright otherwise, "
                "capacity-balanced repair for route cap, nearest-neighbor fallback"
            ),
            "evidence": [
                "_sweep_construction",
                "_clarke_wright_savings",
                "_capacity_balanced_construction",
                "_nearest_neighbor",
            ],
        },
        {
            "from": "scheduler._ALNSVNSSolver.solve",
            "to": "acceptance._AdaptiveWeights",
            "mechanism": "adaptive destroy/repair operator choice, score, and update",
            "evidence": ["choose", "record", "update", "segment_length"],
        },
        {
            "from": "scheduler._ALNSVNSSolver.solve",
            "to": "destroy_repair",
            "mechanism": (
                "ALNS destroy/repair loop includes Shaw related removal: "
                "seed-based removal with distance, demand, and route relatedness"
            ),
            "evidence": [
                "_random_removal",
                "_worst_removal",
                "_shaw_removal",
                "seed-based related removal",
                "distance + demand + original-route relatedness",
                "_route_removal",
                "_greedy_insertion",
                "_regret2_insertion",
                "_regret3_insertion",
            ],
        },
        {
            "from": "scheduler._ALNSVNSSolver.solve",
            "to": "local_search._vns",
            "mechanism": "embedded local search when VNS is enabled and bounded",
            "evidence": ["_vns", "_default_vns_operators", "vns_embedded"],
        },
        {
            "from": "local_search._default_vns_operators",
            "to": "local_search operators",
            "mechanism": "VNS neighborhoods include intra and cross-route moves",
            "evidence": [
                "_two_opt_intra",
                "_relocate",
                "_or_opt_1",
                "_or_opt_2",
                "_or_opt_3",
                "_swap",
                "_two_opt_star",
            ],
        },
        {
            "from": "scheduler._ALNSVNSSolver.solve",
            "to": "acceptance._SimulatedAnnealing.accept",
            "mechanism": "accepts best, better, and bounded worse candidates",
            "evidence": ["SIGMA_BEST", "SIGMA_BETTER", "SIGMA_ACCEPTED", "accept"],
        },
    ]
    return {
        "surface": "solver_design",
        "provenance": _provenance_payload(context, source_root, source_kind),
        "source_digest": {
            "algorithm": "sha256",
            "snapshot_digest": _aggregate_digest(
                {
                    path: _sha256(text)
                    for path, text in files.items()
                    if text
                }
            ),
        },
        "nodes": _call_graph_nodes(symbols),
        "edges": edges,
        "legacy_inactive_surface_exclusion": legacy_inactive_surface_exclusion(),
    }


def list_algorithm_files_payload(
    context: ProposalToolContext,
    *,
    include_inactive: bool = False,
) -> list[dict[str, Any]]:
    source_root, source_kind = active_solver_source_root(context)
    rows: list[dict[str, Any]] = []
    for rel_path, role, active in _ALGORITHM_FILE_ROLES:
        if not active and not include_inactive:
            continue
        artifact = _read_code_file_from_root(
            source_root or "",
            rel_path,
            max_chars=0,
            source_kind=source_kind,
        )
        text = _file_text(source_root, source_kind, rel_path)
        rows.append(
            {
                "file_path": rel_path,
                "module": _module_name(rel_path),
                "role": role,
                "active": active,
                "readable": bool(artifact.get("readable")),
                "reason": artifact.get("reason"),
                "source": source_kind,
                "size_chars": len(text) if text else artifact.get("size_chars"),
                "sha256": _sha256(text) if text else None,
                "digest": _sha256(text)[:_DIGEST_CHARS] if text else None,
            }
        )
    return rows


def read_algorithm_file_payload(
    context: ProposalToolContext,
    file_path: str,
    *,
    max_chars: int,
) -> dict[str, Any]:
    rel_path = _normalize_algorithm_file(file_path)
    source_root, source_kind = active_solver_source_root(context)
    if rel_path is None:
        safe_path = _safe_rejected_file_path(file_path)
        return {
            "file_path": safe_path,
            "path_rejected": True,
            "readable": False,
            "reason": "file_not_allowlisted_for_solver_design",
            "allowed_files": sorted(_ALLOWED_ALGORITHM_FILES),
            "source": source_kind,
        }
    artifact = _read_code_file_from_root(
        source_root or "",
        rel_path,
        max_chars=max(0, max_chars),
        source_kind=source_kind,
    )
    text = _file_text(source_root, source_kind, rel_path)
    artifact.update(
        {
            "active": _is_active_algorithm_file(rel_path),
            "role": _role_for_path(rel_path),
            "module": _module_name(rel_path),
            "sha256": _sha256(text) if text else None,
            "digest": _sha256(text)[:_DIGEST_CHARS] if text else None,
            "provenance": _provenance_payload(context, source_root, source_kind),
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


def legacy_inactive_surface_exclusion() -> dict[str, Any]:
    return {
        "rule": (
            "The active solver_design evidence is the branch/champion algorithm "
            "code listed in active_files. Legacy or component surfaces may guide "
            "naming but must not be used as active evidence that a mechanism is "
            "present or absent."
        ),
        "excluded_surfaces": [
            "algorithm_blueprint",
            "alns_vns_policy",
            "destroy_repair_policy",
            "construction_policy",
            "local_search_policy",
            "acceptance_policy",
            "route_pair_candidate_policy",
        ],
        "excluded_files_or_hooks": [
            {
                "path": "policies/solver_algorithm.py",
                "reason": (
                    "compatibility hook; not primary entrypoint when "
                    "baseline_algorithm.py is present"
                ),
            },
            {
                "path": "vrp/",
                "reason": (
                    "legacy package implementation; active solver_design does "
                    "not import it"
                ),
            },
            {
                "path": "compact context.read_surface component defaults",
                "reason": "surface metadata is not active branch/champion code",
            },
        ],
    }


def _entrypoint_payload(
    source_root: str | Path | None,
    source_kind: str,
) -> dict[str, Any]:
    text = _file_text(source_root, source_kind, "policies/baseline_algorithm.py")
    return {
        "file_path": "policies/baseline_algorithm.py",
        "symbol": "solve",
        "call_target": "policies/baseline_modules/scheduler.py::_ALNSVNSSolver.solve",
        "source": source_kind,
        "readable": bool(text),
        "digest": _sha256(text)[:_DIGEST_CHARS] if text else None,
        "summary": (
            "solve(instance, rng, time_limit_sec, context) constructs "
            "_ALNSVNSSolver, delegates to solver.solve(instance, rng), records "
            "stop_reason, and returns context.make_solution(routes_as_tuples())."
        ),
    }


def _mechanism_summary(
    source_root: str | Path | None,
    source_kind: str,
) -> dict[str, Any]:
    scheduler = _file_text(
        source_root,
        source_kind,
        "policies/baseline_modules/scheduler.py",
    )
    local_search = _file_text(
        source_root,
        source_kind,
        "policies/baseline_modules/local_search.py",
    )
    acceptance = _file_text(
        source_root,
        source_kind,
        "policies/baseline_modules/acceptance.py",
    )
    destroy_repair = _file_text(
        source_root,
        source_kind,
        "policies/baseline_modules/destroy_repair.py",
    )
    return {
        "construction": {
            "active": "_initial_solution" in scheduler,
            "summary": (
                "_initial_solution chooses sweep construction above cw_threshold, "
                "Clarke-Wright otherwise, capacity-balanced construction if the "
                "route cap is exceeded, nearest-neighbor only as feasibility "
                "fallback, then optional vns_initial."
            ),
            "evidence_symbols": [
                "_initial_solution",
                "_sweep_construction",
                "_clarke_wright_savings",
                "_capacity_balanced_construction",
                "_nearest_neighbor",
                "vns_initial",
            ],
        },
        "alns_loop": {
            "active": "while self._within_budget" in scheduler,
            "summary": (
                "The main ALNS loop records iterations, samples destroy/repair "
                "operators through adaptive weights, applies destroy/repair, "
                "optionally embeds VNS, checks feasibility/route caps, scores "
                "best/better/accepted moves, and updates weights per segment."
            ),
            "evidence_symbols": [
                "record_iteration('alns')",
                "_AdaptiveWeights.choose",
                "destroy_op",
                "repair_op",
                "record_move('alns')",
                "segment_length",
            ],
        },
        "destroy_repair": {
            "active": (
                "_shaw_removal" in destroy_repair
                and '"shaw", _shaw_removal' in scheduler
            ),
            "summary": (
                "The destroy operator portfolio contains random, worst, Shaw "
                "related removal, and whole-route removal, wired through "
                "scheduler destroy_ops. _shaw_removal is a seed-based "
                "related/proximity-cluster destroy operator: it picks a seed "
                "customer, then removes customers ranked by distance, demand, "
                "and original-route relatedness, with stochastic p sampling."
            ),
            "evidence_symbols": [
                "_shaw_removal",
                '"shaw", _shaw_removal',
                "seed customer",
                "phi_dist",
                "phi_demand",
                "phi_route",
                "original_route",
                "distance(customer, ref)",
                "rng.random() ** p",
            ],
        },
        "local_search": {
            "active": "_default_vns_operators" in local_search,
            "summary": (
                "VNS uses _two_opt_intra, _relocate, _or_opt_1/_2/_3, _swap, "
                "and _two_opt_star. _or_opt skips same-route destinations, so "
                "length-2 and length-3 cross-route Or-opt already exist."
            ),
            "evidence_symbols": [
                "_vns",
                "_default_vns_operators",
                "_or_opt_2",
                "_or_opt_3",
                "_two_opt_star",
            ],
        },
        "acceptance": {
            "active": (
                "_SimulatedAnnealing" in acceptance
                and "_AdaptiveWeights" in acceptance
            ),
            "summary": (
                "_AdaptiveWeights starts uniform but records scores/usages and "
                "updates weights with the reaction factor. _SimulatedAnnealing "
                "accepts worsening moves with a cooling probability."
            ),
            "evidence_symbols": [
                "_AdaptiveWeights.choose",
                "_AdaptiveWeights.record",
                "_AdaptiveWeights.update",
                "_SimulatedAnnealing.accept",
            ],
        },
    }


def _provenance_payload(
    context: ProposalToolContext,
    source_root: str | Path | None,
    source_kind: str,
) -> dict[str, Any]:
    del source_root
    return {
        "source": source_kind,
        "branch_id": context.branch_id,
        "base_champion_id": _attr(context.branch, "base_champion_id"),
        "base_champion_hash": _attr(context.branch, "base_champion_hash"),
        "champion_version": _attr(context.champion, "version"),
        "champion_code_snapshot_hash": _attr(context.champion, "code_snapshot_hash"),
    }


def _call_graph_nodes(symbols: Mapping[str, list[str]]) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    for rel_path, role, active in _ALGORITHM_FILE_ROLES:
        if not active:
            continue
        nodes.append(
            {
                "file_path": rel_path,
                "module": _module_name(rel_path),
                "role": role,
                "symbols": symbols.get(rel_path, []),
            }
        )
    return nodes


def _file_text(
    source_root: str | Path | None,
    source_kind: str,
    rel_path: str,
) -> str:
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


def _normalize_algorithm_file(file_path: str) -> str | None:
    normalized = str(file_path or "").replace(os.sep, "/").lstrip("/")
    if normalized in _ALLOWED_ALGORITHM_FILES:
        return normalized
    return None


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


def _is_active_algorithm_file(rel_path: str) -> bool:
    return any(path == rel_path and active for path, _, active in _ALGORITHM_FILE_ROLES)


def _role_for_path(rel_path: str) -> str:
    for path, role, _active in _ALGORITHM_FILE_ROLES:
        if path == rel_path:
            return role
    return ""


def _module_name(rel_path: str) -> str:
    path = rel_path.removesuffix(".py").replace("/", ".")
    return path


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _aggregate_digest(digests: Mapping[str, str]) -> str:
    joined = "\n".join(f"{path}:{digest}" for path, digest in sorted(digests.items()))
    return _sha256(joined) if joined else ""


__all__ = [
    "active_solver_source_root",
    "build_active_solver_snapshot",
    "legacy_inactive_surface_exclusion",
    "list_algorithm_files_payload",
    "read_algorithm_file_payload",
    "read_algorithm_symbol_payload",
    "solver_call_graph_payload",
]
