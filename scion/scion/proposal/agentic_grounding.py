"""Required context and active solver grounding helpers for APS."""

from __future__ import annotations

from typing import Any, Mapping

from scion.core.models import HypothesisProposal
from scion.proposal.agentic_models import (
    AgenticProposalPhase,
    AgenticProposalSessionState,
)
from scion.proposal.agentic_session_tools import (
    _algorithm_file_path_guidance,
    _algorithm_file_paths_from_observations,
    _is_solver_design_algorithm_target,
    _has_successful_reusable_observation,
    _has_successful_tool,
)
from scion.proposal.agentic_utils import (
    _drop_empty_dict,
    _limit_string,
)
from scion.proposal.tools import ProposalObservation, ProposalToolContext

_SOLVER_DESIGN_SURFACE_NAMES = frozenset({"solver_design", "solver_algorithm"})
_SOLVER_DESIGN_GROUNDING_TOOLS = (
    "context.read_active_solver_design",
    "context.read_solver_call_graph",
)
_SOLVER_DESIGN_FILE_DISCOVERY_TOOLS = ("context.list_algorithm_files",)
_APS_TARGET_ALGORITHM_FILE_READ_CHARS = 24000


def _required_context_tool_names(
    context: ProposalToolContext | None,
) -> tuple[str, ...]:
    del context
    return ("context.list_surfaces", "context.read_problem")


def _fallback_required_context_tool_names(
    context: ProposalToolContext | None,
) -> tuple[str, ...]:
    names = ["context.list_surfaces", "context.read_problem"]
    if _context_requires_solver_design_grounding(context):
        names.extend(_SOLVER_DESIGN_FILE_DISCOVERY_TOOLS)
        names.extend(_SOLVER_DESIGN_GROUNDING_TOOLS)
    return tuple(names)


def _context_requires_solver_design_grounding(
    context: ProposalToolContext | None,
) -> bool:
    if context is None:
        return False
    forced_surface = str(context.forced_surface or "").strip()
    if forced_surface in _SOLVER_DESIGN_SURFACE_NAMES:
        return True
    boundary = {
        str(surface or "").strip()
        for surface in context.active_problem_boundary_surfaces
        if str(surface or "").strip()
    }
    return bool(boundary) and boundary.issubset(_SOLVER_DESIGN_SURFACE_NAMES)


def _is_solver_design_hypothesis(hypothesis: HypothesisProposal) -> bool:
    return str(hypothesis.change_locus or "").strip() in _SOLVER_DESIGN_SURFACE_NAMES


def _missing_solver_design_grounding_error(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
    *,
    hypothesis: HypothesisProposal,
    context: ProposalToolContext | None = None,
) -> str | None:
    if not _is_solver_design_hypothesis(hypothesis):
        return None
    boundary_error = _solver_design_target_boundary_error(
        hypothesis,
        context=context,
        observations=observations,
    )
    if boundary_error is not None:
        return boundary_error
    observed_ok = {
        observation.tool_name
        for observation in observations
        if not observation.is_error
    }
    if _has_active_solver_embedded_call_graph(observations):
        observed_ok.add("context.read_solver_call_graph")
    missing = [
        tool_name
        for tool_name in _SOLVER_DESIGN_FILE_DISCOVERY_TOOLS
        if tool_name not in observed_ok
    ]
    missing.extend(
        tool_name
        for tool_name in _SOLVER_DESIGN_GROUNDING_TOOLS
        if tool_name not in observed_ok
    )
    target_read_args = _solver_design_target_file_read_args(
        hypothesis,
        context=context,
        observations=observations,
    )
    if target_read_args is not None and not _has_successful_reusable_observation(
        observations,
        "context.read_algorithm_file",
        target_read_args,
        forced_surface=hypothesis.change_locus,
    ):
        missing.append(
            "context.read_algorithm_file"
            f"({target_read_args.get('file_path')})"
        )
    if not missing:
        return None
    return (
        "missing required solver_design grounding tools before hypothesis approval: "
        + ", ".join(missing)
    )


def _solver_design_target_file_read_args(
    hypothesis: HypothesisProposal | None,
    *,
    context: ProposalToolContext | None = None,
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation] = (),
) -> dict[str, Any] | None:
    if hypothesis is None:
        return None
    target_file = _normalize_solver_design_target_file(hypothesis.target_file)
    if not _is_solver_design_algorithm_target(target_file):
        return None
    existing_paths = _existing_algorithm_file_paths(
        context=context,
        observations=observations,
    )
    if existing_paths and target_file not in set(existing_paths):
        return None
    if not existing_paths and _target_declared_for_solver_design_surface(
        context,
        target_file,
    ):
        return None
    return {
        "surface": "solver_design",
        "file_path": target_file,
        "max_chars": _APS_TARGET_ALGORITHM_FILE_READ_CHARS,
    }


def _solver_design_target_boundary_error(
    hypothesis: HypothesisProposal,
    *,
    context: ProposalToolContext | None,
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
) -> str | None:
    target_file = _normalize_solver_design_target_file(hypothesis.target_file)
    if not target_file or context is None:
        return None
    existing_paths = _existing_algorithm_file_paths(
        context=context,
        observations=observations,
    )
    if target_file in set(existing_paths):
        return None
    if _target_declared_for_solver_design_surface(context, target_file):
        return None
    return (
        "solver_design target_file is outside declared patch paths: "
        f"{target_file}"
    )


def _normalize_solver_design_target_file(target_file: Any) -> str:
    return str(target_file or "").replace("\\", "/").lstrip("/").strip()


def _existing_algorithm_file_paths(
    *,
    context: ProposalToolContext | None,
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
) -> list[str]:
    paths = _algorithm_file_paths_from_observations(observations)
    if paths:
        return paths
    if context is None:
        return []
    guidance = _algorithm_file_path_guidance(context, observations)
    allowed = guidance.get("allowed_file_paths", ())
    if not isinstance(allowed, (list, tuple)):
        return []
    return list(
        dict.fromkeys(
            _normalize_solver_design_target_file(path)
            for path in allowed
            if _normalize_solver_design_target_file(path)
        )
    )


def _target_declared_for_solver_design_surface(
    context: ProposalToolContext | None,
    target_file: str,
) -> bool:
    if context is None or not target_file:
        return False
    from scion.proposal.tools.surface import (
        _find_surface,
        _surface_target_files,
        _target_declared,
    )

    surface = _find_surface(context, "solver_design")
    if surface is None:
        return False
    return _target_declared(target_file, _surface_target_files(surface))


def _solver_design_grounding_call_satisfied(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
    name: str,
    args: Mapping[str, Any],
) -> bool:
    if name == "context.read_solver_call_graph":
        return _has_successful_solver_call_graph_grounding(observations)
    if name == "context.read_algorithm_file":
        return _has_successful_reusable_observation(
            observations,
            name,
            args,
            forced_surface="solver_design",
        )
    return _has_successful_tool(observations, name)


def _has_successful_solver_call_graph_grounding(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
) -> bool:
    return _has_successful_tool(
        observations,
        "context.read_solver_call_graph",
    ) or _has_active_solver_embedded_call_graph(observations)


def _has_active_solver_embedded_call_graph(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
) -> bool:
    for observation in reversed(tuple(observations)):
        if observation.is_error:
            continue
        if observation.tool_name != "context.read_active_solver_design":
            continue
        payload = observation.structured_payload
        if not isinstance(payload, Mapping):
            continue
        call_graph = payload.get("call_graph")
        if not isinstance(call_graph, Mapping):
            continue
        if any(
            key in call_graph
            for key in (
                "edges",
                "edge_count",
                "nodes",
                "node_count",
                "source_digest",
                "provenance",
            )
        ):
            return True
    return False


def _run_required_context_preface(
    runner: Any,
    context: ProposalToolContext,
    state: AgenticProposalSessionState,
) -> list[ProposalObservation]:
    calls: list[tuple[str, Mapping[str, Any]]] = [
        ("context.list_surfaces", {}),
        ("context.read_problem", {}),
    ]
    if _context_requires_solver_design_grounding(context):
        calls.extend(
            [
                (
                    "context.list_algorithm_files",
                    {"surface": "solver_design", "include_inactive": True},
                ),
                (
                    "context.read_active_solver_design",
                    {"surface": "solver_design"},
                ),
                (
                    "context.read_solver_call_graph",
                    {"surface": "solver_design"},
                ),
            ]
        )

    observations: list[ProposalObservation] = []
    for name, args in calls:
        if _has_successful_reusable_observation(
            observations,
            name,
            args,
            forced_surface=context.forced_surface,
        ):
            continue
        if runner._tool_loop_limit_reached(state):
            runner._record_loop_stop(state, runner._current_loop_stop_reason(state))
            break
        observations.append(
            runner._call_tool(
                context,
                state,
                AgenticProposalPhase.DIAGNOSE,
                name,
                args,
                selection_source="required_context_preface",
            )
        )
        if state.loop_stop_reason in {"session_timeout", "repeated_tool_call"}:
            break

    state.note(
        AgenticProposalPhase.DIAGNOSE,
        "Collected required proposal context preface.",
        metadata={
            "tool_names": [observation.tool_name for observation in observations],
            "error_count": sum(
                1 for observation in observations if observation.is_error
            ),
            "solver_design_grounding": _context_requires_solver_design_grounding(
                context
            ),
        },
    )
    return observations


def _run_solver_design_grounding_tools(
    runner: Any,
    context: ProposalToolContext,
    state: AgenticProposalSessionState,
    prior_observations: list[ProposalObservation],
    *,
    selection_source: str,
    hypothesis: HypothesisProposal | None = None,
) -> list[ProposalObservation]:
    observations: list[ProposalObservation] = []
    calls: list[tuple[str, Mapping[str, Any]]] = [
        (
            "context.list_algorithm_files",
            {"surface": "solver_design", "include_inactive": True},
        ),
        ("context.read_active_solver_design", {"surface": "solver_design"}),
        ("context.read_solver_call_graph", {"surface": "solver_design"}),
    ]
    target_read_args = _solver_design_target_file_read_args(
        hypothesis,
        context=context,
        observations=prior_observations,
    )
    if target_read_args is not None:
        calls.append(("context.read_algorithm_file", target_read_args))
    for name, args in calls:
        current_observations = [*prior_observations, *observations]
        if _solver_design_grounding_call_satisfied(
            current_observations,
            name,
            args,
        ):
            state.note(
                AgenticProposalPhase.DIAGNOSE,
                "Skipped solver_design grounding tool already completed successfully.",
                metadata={
                    "tool_name": name,
                    "status": "skipped",
                    "selection_source": selection_source,
                    "skip_reason": "already_succeeded",
                },
            )
            continue
        if name == "context.read_solver_call_graph" and (
            _has_active_solver_embedded_call_graph(current_observations)
        ):
            state.note(
                AgenticProposalPhase.DIAGNOSE,
                "Skipped solver_design grounding tool already covered by active solver snapshot.",
                metadata={
                    "tool_name": name,
                    "status": "skipped",
                    "selection_source": selection_source,
                    "skip_reason": "active_solver_snapshot_includes_call_graph",
                },
            )
            continue
        if runner._tool_loop_limit_reached(state):
            runner._record_loop_stop(state, runner._current_loop_stop_reason(state))
            break
        observations.append(
            runner._call_tool(
                context,
                state,
                AgenticProposalPhase.DIAGNOSE,
                name,
                args,
                selection_source=selection_source,
            )
        )
    return observations


def _run_selected_surface_observation_tool(
    runner: Any,
    context: ProposalToolContext,
    hypothesis: HypothesisProposal,
    state: AgenticProposalSessionState,
    observations: list[ProposalObservation],
) -> list[ProposalObservation]:
    from scion.proposal.agentic_session_tools import (
        _APS_SURFACE_READ_CODE_CHARS,
        _has_successful_surface_read,
    )

    if _has_successful_surface_read(observations, hypothesis.change_locus):
        state.note(
            AgenticProposalPhase.INSPECT_INTERFACE,
            "Skipped selected-surface read already completed successfully.",
            metadata={
                "tool_name": "context.read_surface",
                "status": "skipped",
                "selection_source": "selected_surface_required",
                "skip_reason": "already_succeeded",
            },
        )
        return []
    if runner._tool_loop_limit_reached(state):
        runner._record_loop_stop(state, runner._current_loop_stop_reason(state))
        return []
    args: dict[str, Any] = {
        "surface": hypothesis.change_locus,
        "detail": "compact",
        "max_code_chars": _APS_SURFACE_READ_CODE_CHARS,
    }
    if hypothesis.target_file:
        args["target_file"] = hypothesis.target_file
    observation = runner._call_tool(
        context,
        state,
        AgenticProposalPhase.INSPECT_INTERFACE,
        "context.read_surface",
        args,
        selection_source="selected_surface_required",
    )
    return [observation]


def _compact_active_solver_observation_for_budget(
    observation: ProposalObservation,
) -> ProposalObservation | None:
    from dataclasses import replace

    if observation.is_error or observation.tool_name not in {
        "context.read_active_solver_design",
        "context.read_solver_call_graph",
        "context.list_algorithm_files",
        "context.read_algorithm_file",
        "context.read_algorithm_symbol",
    }:
        return None
    payload = observation.structured_payload
    if not isinstance(payload, Mapping):
        return None
    if observation.tool_name == "context.read_active_solver_design":
        compact_payload = _compact_active_solver_design_payload(payload)
    elif observation.tool_name == "context.read_solver_call_graph":
        compact_payload = _compact_solver_call_graph_payload(payload)
    elif observation.tool_name == "context.list_algorithm_files":
        compact_payload = _compact_algorithm_file_list_payload(payload)
    else:
        compact_payload = _compact_algorithm_read_payload(payload)
    return replace(
        observation,
        summary=_limit_string(observation.summary, 220)
        or "Returned compact active solver evidence.",
        structured_payload=compact_payload,
        repair_hint=None,
    )


def _compact_active_solver_design_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    call_graph = payload.get("call_graph")
    return _drop_empty_dict(
        {
            "surface": payload.get("surface"),
            "active_surface": payload.get("active_surface"),
            "provenance": payload.get("provenance"),
            "source_digest": _compact_source_digest(payload.get("source_digest")),
            "entrypoint": payload.get("entrypoint"),
            "active_files": _compact_algorithm_files(payload.get("active_files")),
            "inactive_files": _compact_algorithm_files(payload.get("inactive_files")),
            "call_graph": (
                _compact_solver_call_graph_payload(call_graph)
                if isinstance(call_graph, Mapping)
                else None
            ),
            "mechanism_summary": _compact_mechanism_summary(
                payload.get("mechanism_summary")
            ),
            "mechanism_keys": sorted(
                str(key) for key in (payload.get("mechanism_summary") or {}).keys()
            )
            if isinstance(payload.get("mechanism_summary"), Mapping)
            else None,
            "compacted_for_agentic_budget": True,
        }
    )


def _compact_solver_call_graph_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    edges = payload.get("edges")
    nodes = payload.get("nodes")
    compact_edges: list[dict[str, Any]] = []
    if isinstance(edges, list):
        for edge in edges[:12]:
            if not isinstance(edge, Mapping):
                continue
            compact_edges.append(
                _drop_empty_dict(
                    {
                        "from": edge.get("from"),
                        "to": edge.get("to"),
                        "mechanism": _limit_string(edge.get("mechanism"), 260),
                        "evidence": _compact_string_list(edge.get("evidence"), 8, 120),
                    }
                )
            )
    return _drop_empty_dict(
        {
            "surface": payload.get("surface"),
            "provenance": payload.get("provenance"),
            "source_digest": _compact_source_digest(payload.get("source_digest")),
            "node_count": len(nodes) if isinstance(nodes, list) else None,
            "edge_count": len(edges) if isinstance(edges, list) else None,
            "edges": compact_edges,
            "compacted_for_agentic_budget": True,
        }
    )


def _compact_algorithm_file_list_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    return _drop_empty_dict(
        {
            "surface": payload.get("surface"),
            "allowlist_only": payload.get("allowlist_only"),
            "file_count": payload.get("file_count"),
            "files": _compact_algorithm_files(payload.get("files")),
            "compacted_for_agentic_budget": True,
        }
    )


def _compact_algorithm_read_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    return _drop_empty_dict(
        {
            "file_path": payload.get("file_path"),
            "symbol": payload.get("symbol"),
            "readable": payload.get("readable"),
            "reason": payload.get("reason"),
            "source": payload.get("source"),
            "active": payload.get("active"),
            "role": payload.get("role"),
            "module": payload.get("module"),
            "line_start": payload.get("line_start"),
            "line_end": payload.get("line_end"),
            "sha256": payload.get("sha256"),
            "digest": payload.get("digest"),
            "truncated": payload.get("truncated"),
            "provenance": payload.get("provenance"),
            "content_preview": _limit_string(payload.get("content_preview"), 1600),
            "compacted_for_agentic_budget": True,
        }
    )


def _compact_algorithm_files(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    files: list[dict[str, Any]] = []
    for item in value[:12]:
        if not isinstance(item, Mapping):
            continue
        files.append(
            _drop_empty_dict(
                {
                    "file_path": item.get("file_path"),
                    "module": item.get("module"),
                    "role": item.get("role"),
                    "active": item.get("active"),
                    "readable": item.get("readable"),
                    "reason": item.get("reason"),
                    "source": item.get("source"),
                    "digest": item.get("digest"),
                }
            )
        )
    return files


def _compact_source_digest(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    files = value.get("files")
    compact_files = {}
    if isinstance(files, Mapping):
        compact_files = {
            str(path): str(digest)[:16]
            for path, digest in list(files.items())[:12]
        }
    return _drop_empty_dict(
        {
            "algorithm": value.get("algorithm"),
            "snapshot_digest": value.get("snapshot_digest"),
            "files": compact_files,
        }
    )


def _compact_mechanism_summary(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    summary: dict[str, Any] = {}
    for key, item in value.items():
        if not isinstance(item, Mapping):
            continue
        summary[str(key)] = _drop_empty_dict(
            {
                "active": item.get("active"),
                "summary": _limit_string(item.get("summary"), 600),
                "evidence_symbols": _compact_string_list(
                    item.get("evidence_symbols"),
                    12,
                    140,
                ),
            }
        )
    return _drop_empty_dict(summary)


def _compact_string_list(value: Any, limit: int, max_chars: int) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    result: list[str] = []
    for item in list(value)[: max(0, limit)]:
        text = _limit_string(item, max_chars)
        if text:
            result.append(text)
    return result


def _active_solver_mechanism_evidence_for_code_context(
    observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
) -> dict[str, Any]:
    for observation in reversed(tuple(observations)):
        if observation.is_error:
            continue
        if observation.tool_name != "context.read_active_solver_design":
            continue
        payload = observation.structured_payload
        if not isinstance(payload, Mapping):
            continue
        mechanisms = _compact_mechanism_summary(payload.get("mechanism_summary"))
        if not mechanisms:
            continue
        source_digest = payload.get("source_digest")
        snapshot_digest = (
            source_digest.get("snapshot_digest")
            if isinstance(source_digest, Mapping)
            else None
        )
        return _drop_empty_dict(
            {
                "source": "context.read_active_solver_design",
                "snapshot_digest": snapshot_digest,
                "mechanism_summary": mechanisms,
                "premise_check_rule": (
                    "Before returning premise_check='supported', compare the "
                    "hypothesis against the active algorithm mechanisms exposed "
                    "by this surface snapshot."
                ),
            }
        )
    return {}
