"""Surface discovery and read helpers for proposal tools."""

from __future__ import annotations

import ast
import json
import os
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from pydantic import BaseModel

from scion.core.models import ChampionState, HypothesisProposal
from scion.core.path_match import normalize_relative_glob_pattern, segment_glob_match
from scion.proposal.context_manager import (
    _build_research_surface_interface_spec,
    _get_adapter_problem_spec,
    _get_research_surfaces,
)
from scion.proposal.tools.base import _BaseReadOnlyTool
from scion.proposal.tools.models import (
    ProposalExposureLevel,
    ProposalObservation,
    ProposalToolContext,
    ProposalToolFailureCode,
    ProposalToolPermission,
    ReadSurfaceInput,
)
from scion.proposal.tools.utils import (
    _attr,
    _limit_text,
    _model_payload,
    _normalize_rel_path,
)

_COMPACT_SURFACE_CODE_CHARS = 1200
_FULL_SURFACE_CODE_CHARS = 12000
_COMPACT_SURFACE_TEXT_CHARS = 600
_COMPACT_SURFACE_HINT_CHARS = 240
_COMPACT_SURFACE_INTERFACE_CHARS = 2400
_COMPACT_SURFACE_LIST_ITEMS = 32
_COMPACT_SURFACE_MAP_ITEMS = 32
_SEMANTIC_SIGNATURE_SCALAR_STRING_CHARS = 120
_NONEMPTY_SEQUENCE_NOVELTY_FIELDS = frozenset(
    {
        "selected_components",
        "deep_components_selected",
    }
)
_COMPACT_SURFACE_SECTIONS = (
    "summary",
    "interface",
    "bounds",
    "evidence",
    "novelty",
    "target_preview",
)
_SOLVER_DESIGN_SUPPORT_PRIORITY = (
    "policies/baseline_modules/state.py",
    "policies/baseline_algorithm.py",
    "policies/baseline_modules/scheduler.py",
    "policies/baseline_modules/local_search.py",
    "policies/baseline_modules/construction.py",
    "policies/baseline_modules/destroy_repair.py",
    "policies/baseline_modules/acceptance.py",
    "policies/baseline_modules/config.py",
    "policies/solver_algorithm.py",
)

class ContextReadSurfaceTool(_BaseReadOnlyTool):
    name = "context.read_surface"
    input_schema = ReadSurfaceInput
    permission = ProposalToolPermission.READ_CHAMPION_ARTIFACT

    def call(
        self,
        args: ReadSurfaceInput,
        context: ProposalToolContext,
    ) -> ProposalObservation:
        surface = _find_surface(context, args.surface)
        if surface is None:
            available_surfaces = [
                str(_attr(candidate, "name") or _attr(candidate, "id") or "")
                for candidate in _surfaces(context)
            ]
            return self._error(
                context,
                failure_code=ProposalToolFailureCode.NOT_FOUND,
                summary=f"Research surface not found: {args.surface}",
                structured_payload={
                    "requested_surface": args.surface,
                    "available_surfaces": [
                        surface_name
                        for surface_name in available_surfaces
                        if surface_name
                    ],
                },
                repair_hint="Use context.list_surfaces and select a declared surface.",
            )
        target_files = _surface_target_files(surface)
        target_file = args.target_file or _first_concrete_target(target_files)
        if target_file is not None and not _target_declared(target_file, target_files):
            return self._error(
                context,
                failure_code=ProposalToolFailureCode.PERMISSION_DENIED,
                summary=(
                    f"Target file {target_file!r} is not declared for surface "
                    f"{args.surface!r}."
                ),
                structured_payload={
                    "surface": args.surface,
                    "declared_targets": target_files,
                    "requested_target": target_file,
                },
                repair_hint="Read only files declared by the selected research surface.",
            )

        detail = args.detail
        code_char_limit = _surface_code_char_limit(
            detail=detail,
            requested_max=args.max_code_chars,
        )
        code_payload: dict[str, Any] | None = None
        support_artifacts: list[dict[str, Any]] = []
        if args.include_code and target_file:
            if context.champion is None:
                return self._error(
                    context,
                    failure_code=ProposalToolFailureCode.NOT_FOUND,
                    summary="No champion snapshot is available for surface read.",
                )
            source_root, source_kind = _surface_code_read_root(context)
            code_payload = _read_code_file_from_root(
                source_root,
                target_file,
                max_chars=code_char_limit,
                source_kind=source_kind,
            )
            if _surface_name(surface) == "solver_design" and args.section in {
                "all",
                "target_preview",
            }:
                support_artifacts = _read_solver_design_support_artifacts(
                    source_root,
                    target_files,
                    primary_target=target_file,
                    detail=detail,
                    primary_code_char_limit=code_char_limit,
                    source_kind=source_kind,
                )

        payload = {
            "surface": _surface_read_payload(
                surface,
                detail=detail,
                section=args.section,
            ),
            "surface_contract": _surface_contract_metadata(
                surface,
                detail=detail,
                section=args.section,
                current_artifact=code_payload,
            ),
            "interface_summary": _surface_interface_summary(
                surface,
                detail=detail,
                section=args.section,
            ),
            "detail": detail,
            "section": args.section,
            "declared_targets": target_files,
            "target_file": target_file,
            "current_artifact": code_payload,
            "support_artifacts": support_artifacts,
        }
        return self._observation(
            context,
            observation_type="surface_interface",
            summary=f"Returned declared interface for surface {args.surface}.",
            structured_payload=payload,
            exposure_level=ProposalExposureLevel.CHAMPION_CODE,
        )

def _surface_allowed_actions(surface: Any | None) -> list[str]:
    if surface is None:
        return []
    targets = _attr(surface, "targets")
    allowed = []
    action_attrs = (
        ("create_new", "create_new_allowed"),
        ("modify", "modify_allowed"),
        ("remove", "remove_allowed"),
    )
    for action, attr in action_attrs:
        value = _attr(targets, attr, _attr(surface, attr, True))
        if value:
            allowed.append(action)
    return allowed

def _surface_permission_summary(
    surface: Any,
    *,
    allowed_actions: list[str],
    declared_targets: list[str],
) -> dict[str, Any]:
    return {
        "name": _attr(surface, "name"),
        "kind": _attr(surface, "kind"),
        "allowed_actions": list(allowed_actions),
        "declared_targets": list(declared_targets),
    }

def _surface_required_functions(surface: Any | None) -> list[str]:
    if surface is None:
        return []
    interface = _attr(surface, "interface")
    required = _attr(interface, "required_functions", None)
    if required is None:
        required = _attr(surface, "required_functions", [])
    return [str(name) for name in (required or [])]

def _surface_function_signatures(surface: Any | None) -> dict[str, list[str]]:
    if surface is None:
        return {}
    interface = _attr(surface, "interface")
    signatures = _attr(interface, "function_signatures", None)
    if not isinstance(signatures, dict):
        return {}
    normalized: dict[str, list[str]] = {}
    for raw_name, raw_args in signatures.items():
        name = str(raw_name).strip()
        if not name:
            continue
        if isinstance(raw_args, str):
            args = [arg.strip() for arg in raw_args.split(",") if arg.strip()]
        else:
            try:
                args = [str(arg).strip() for arg in raw_args if str(arg).strip()]
            except TypeError:
                args = []
        normalized[name] = args
    return normalized

def _surface_return_values(surface: Any | None) -> dict[str, Any]:
    if surface is None:
        return {}
    interface = _attr(surface, "interface")
    values = _attr(interface, "return_values", None) if interface is not None else None
    if not isinstance(values, Mapping):
        return {}
    return _compact_mapping_payload(values)

def _surface_for_patch_path(
    context: ProposalToolContext,
    file_path: str,
) -> Any | None:
    normalized = _normalize_rel_path(file_path)
    if normalized is None:
        return None
    for surface in _surfaces(context):
        if _target_declared(normalized, _surface_target_files(surface)):
            return surface
    return None

def _surface_for_hypothesis(
    context: ProposalToolContext,
    hypothesis: HypothesisProposal,
) -> Any | None:
    surface = _find_surface(context, hypothesis.change_locus)
    if surface is not None:
        return surface
    if hypothesis.target_file:
        return _surface_for_patch_path(context, hypothesis.target_file)
    return None

def _surface_novelty_signature_requirement(surface: Any | None) -> dict[str, Any]:
    if surface is None:
        return {}
    novelty = _attr(surface, "novelty")
    strategy = str(_attr(novelty, "strategy", "") or "")
    fields = _coerce_compact_list(_attr(novelty, "signature_fields", []))
    if strategy != "semantic_signature" or not fields:
        return {}
    return _drop_empty_items(
        {
            "strategy": strategy,
            "required_fields": fields,
            "nonempty_sequence_fields": [
                field for field in fields if field in _NONEMPTY_SEQUENCE_NOVELTY_FIELDS
            ],
            "rule": (
                "Provide every required novelty_signature field. Fields listed "
                "under nonempty_sequence_fields must be non-empty arrays of "
                "component names, not null, false, empty strings, or empty arrays. "
                "Scalar string values must be at most "
                f"{_SEMANTIC_SIGNATURE_SCALAR_STRING_CHARS} characters."
            ),
            "compact_example": (
                {
                    "algorithm_family": "alns_vns",
                    "construction_strategy": "cw_seed",
                    "improvement_strategy": "bounded_oropt",
                    "acceptance_strategy": "sa_threshold",
                    "runtime_budget_strategy": "time_checked_caps",
                }
                if str(_attr(surface, "name") or "") == "solver_design"
                else None
            ),
        }
    )

def _surface_for_selected_or_patch_path(
    context: ProposalToolContext,
    file_path: str,
    selected_surface: str | None,
) -> Any | None:
    selected = str(selected_surface or "").strip()
    if selected:
        surface = _find_surface(context, selected)
        if surface is not None:
            return surface
    return _surface_for_patch_path(context, file_path)

def _surfaces(context: ProposalToolContext) -> list[Any]:
    adapter_spec = _get_adapter_problem_spec(context.adapter)
    return _get_research_surfaces(context.problem_spec, adapter_spec)

def _surface_list_for_context(
    context: ProposalToolContext,
    surfaces: list[Any],
) -> list[Any]:
    forced_surface = str(context.forced_surface or "").strip()
    if forced_surface:
        constrained = [
            surface
            for surface in surfaces
            if str(_attr(surface, "name") or "").strip() == forced_surface
        ]
        return constrained or surfaces
    boundary = {
        str(surface or "").strip()
        for surface in context.active_problem_boundary_surfaces
        if str(surface or "").strip()
    }
    if not boundary:
        return surfaces
    constrained = [
        surface
        for surface in surfaces
        if str(_attr(surface, "name") or "").strip() in boundary
    ]
    return constrained or surfaces

def _find_surface(context: ProposalToolContext, name: str) -> Any | None:
    for surface in _surfaces(context):
        if _attr(surface, "name") == name:
            return surface
    return None

def _surface_name(surface: Any) -> str:
    return str(_attr(surface, "name") or "").strip()

def _surface_payload(surface: Any) -> dict[str, Any]:
    payload = _model_payload(surface)
    payload.setdefault("name", _attr(surface, "name"))
    payload.setdefault("kind", _attr(surface, "kind"))
    payload.setdefault("description", _attr(surface, "description", ""))
    return payload

def _surface_listing_payload(surface: Any) -> dict[str, Any]:
    target_files = _surface_target_files(surface)
    algorithm = _attr(surface, "algorithm")
    bounds = _attr(surface, "bounds")
    targets = _attr(surface, "targets")
    return _drop_empty_items(
        {
            "name": _attr(surface, "name"),
            "kind": _attr(surface, "kind"),
            "description": _compact_text(_attr(surface, "description", ""), 240),
            "algorithm": _drop_empty_items(
                {
                    "role": _attr(algorithm, "role") if algorithm is not None else None,
                    "invocation_point": (
                        _attr(algorithm, "invocation_point")
                        if algorithm is not None
                        else None
                    ),
                }
            ),
            "targets": _drop_empty_items(
                {
                    "files": target_files,
                    "allowed_actions": _surface_allowed_actions(surface),
                    "singleton": _attr(targets, "singleton"),
                }
            ),
            "target_files": target_files,
            "interface": _drop_empty_items(
                {"required_functions": _surface_required_functions(surface)}
            ),
            "bounds": _drop_empty_items(
                {
                    "allowed_components": _coerce_compact_list(
                        _attr(bounds, "allowed_components", [])
                        if bounds is not None
                        else []
                    ),
                    "numeric_ranges": _model_payload(
                        _attr(bounds, "numeric_ranges", {})
                        if bounds is not None
                        else {}
                    ),
                }
            ),
        }
    )

def _surface_read_payload(
    surface: Any,
    *,
    detail: str,
    section: str = "all",
) -> dict[str, Any]:
    if detail == "full" and section == "all":
        return _surface_payload(surface)
    return _surface_compact_payload(surface, section=section)

def _surface_compact_payload(surface: Any, *, section: str = "all") -> dict[str, Any]:
    target_files = _surface_target_files(surface)
    payload: dict[str, Any] = {
        "name": _attr(surface, "name"),
        "kind": _attr(surface, "kind"),
        "section": section,
    }
    if section in {"all", "summary"}:
        payload.update(
            {
                "description": _compact_text(_attr(surface, "description", "")),
                "algorithm": _compact_algorithm_payload(surface),
                "targets": _compact_targets_payload(surface, target_files),
                "target_files": target_files,
            }
        )
        prompt_hint = _compact_text(
            _attr(surface, "prompt_hint", ""),
            _COMPACT_SURFACE_HINT_CHARS,
        )
        if prompt_hint:
            payload["prompt_hint"] = prompt_hint
    if section in {"all", "interface"}:
        payload["interface"] = _compact_interface_payload(surface)
    if section in {"all", "bounds"}:
        payload["bounds"] = _compact_bounds_payload(surface)
    if section in {"all", "evidence"}:
        payload["evidence"] = _compact_evidence_payload(surface)
    if section in {"all", "novelty"}:
        payload["novelty"] = _compact_novelty_payload(surface)
    if section == "target_preview":
        payload["targets"] = _compact_targets_payload(surface, target_files)
        payload["target_files"] = target_files
    return _drop_empty_items(payload)

def _compact_algorithm_payload(surface: Any) -> dict[str, Any]:
    algorithm = _attr(surface, "algorithm")
    if algorithm is None:
        return {}
    return _drop_empty_items(
        {
            "role": _attr(algorithm, "role"),
            "invocation_point": _attr(algorithm, "invocation_point"),
            "description": _compact_text(_attr(algorithm, "description", "")),
        }
    )

def _compact_targets_payload(
    surface: Any,
    target_files: list[str],
) -> dict[str, Any]:
    targets = _attr(surface, "targets")
    return _drop_empty_items(
        {
            "files": target_files,
            "create_new_allowed": _attr(
                targets,
                "create_new_allowed",
                _attr(surface, "create_new_allowed"),
            ),
            "modify_allowed": _attr(
                targets,
                "modify_allowed",
                _attr(surface, "modify_allowed"),
            ),
            "remove_allowed": _attr(
                targets,
                "remove_allowed",
                _attr(surface, "remove_allowed"),
            ),
            "singleton": _attr(targets, "singleton"),
            "allowed_actions": _surface_allowed_actions(surface),
        }
    )

def _compact_interface_payload(surface: Any) -> dict[str, Any]:
    interface = _attr(surface, "interface")
    return _drop_empty_items(
        {
            "required_functions": _surface_required_functions(surface),
            "function_signatures": _surface_function_signatures(surface),
            "return_contract": _compact_text(
                _attr(interface, "return_contract", "") if interface is not None else ""
            ),
            "return_values": _surface_return_values(surface),
        }
    )

def _compact_bounds_payload(surface: Any) -> dict[str, Any]:
    bounds = _attr(surface, "bounds")
    if bounds is None:
        return {}
    return _drop_empty_items(
        {
            "allowed_components": _coerce_compact_list(
                _attr(bounds, "allowed_components", [])
            ),
            "numeric_ranges": _compact_mapping_payload(
                _attr(bounds, "numeric_ranges", {})
            ),
            "complexity_scale_terms": _coerce_compact_list(
                _attr(bounds, "complexity_scale_terms", [])
            ),
        }
    )

def _compact_evidence_payload(surface: Any) -> dict[str, Any]:
    evidence = _attr(surface, "evidence")
    if evidence is None:
        return {}
    return _drop_empty_items(
        {
            "required_runtime_fields": _coerce_compact_list(
                _attr(evidence, "required_runtime_fields", [])
            )
        }
    )

def _compact_novelty_payload(surface: Any) -> dict[str, Any]:
    novelty = _attr(surface, "novelty")
    if novelty is None:
        return {}
    return _drop_empty_items(
        {
            "strategy": _attr(novelty, "strategy"),
            "signature_fields": _coerce_compact_list(
                _attr(novelty, "signature_fields", [])
            ),
        }
    )

def _surface_contract_metadata(
    surface: Any,
    *,
    detail: str,
    section: str,
    current_artifact: Mapping[str, Any] | None,
) -> dict[str, Any]:
    contract: dict[str, Any] = {
        "schema_version": "surface-contract.v1",
        "detail": detail,
        "section": section,
        "available_sections": list(_COMPACT_SURFACE_SECTIONS),
        "cap": {
            "text_chars_per_field": _COMPACT_SURFACE_TEXT_CHARS,
            "hint_chars": _COMPACT_SURFACE_HINT_CHARS,
            "list_items_per_field": _COMPACT_SURFACE_LIST_ITEMS,
            "map_items_per_field": _COMPACT_SURFACE_MAP_ITEMS,
        },
        "omitted_from_compact": [
            "prompt.hypothesis_guidance",
            "prompt.implementation_guidance",
            "prompt.anti_patterns",
            "full_target_file_content",
        ],
    }
    if detail == "compact":
        contract["section_paths"] = _surface_section_paths(section)
        target_preview = _target_artifact_preview(current_artifact)
        if target_preview:
            contract["target_preview"] = target_preview
    return _drop_empty_items(contract)

def _surface_section_paths(section: str) -> dict[str, list[str]]:
    sections = {
        "summary": [
            "surface.description",
            "surface.algorithm",
            "surface.targets",
            "surface.prompt_hint",
        ],
        "interface": ["surface.interface"],
        "bounds": ["surface.bounds"],
        "evidence": ["surface.evidence"],
        "novelty": ["surface.novelty"],
        "target_preview": ["surface_contract.target_preview", "current_artifact"],
    }
    if section == "all":
        return sections
    selected = sections.get(section, [])
    return {section: selected}

def _target_artifact_preview(
    current_artifact: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if not current_artifact:
        return {}
    return _drop_empty_items(
        {
            "file_path": current_artifact.get("file_path"),
            "readable": current_artifact.get("readable"),
            "reason": current_artifact.get("reason"),
            "size_chars": current_artifact.get("size_chars"),
            "content_preview_chars": len(
                str(current_artifact.get("content_preview", ""))
            ),
            "truncated": current_artifact.get("truncated"),
            "max_chars": current_artifact.get("max_chars"),
        }
    )

def _surface_interface_summary(
    surface: Any,
    *,
    detail: str,
    section: str = "all",
) -> str:
    if detail == "full":
        return _build_research_surface_interface_spec(surface)
    return _compact_surface_interface_summary(surface, section=section)

def _compact_surface_interface_summary(surface: Any, *, section: str = "all") -> str:
    compact = _surface_compact_payload(surface, section=section)
    lines = [
        (
            f"### Declared Research Surface: {compact.get('name', '')} "
            f"[{compact.get('kind', '')}]"
        )
    ]
    lines.append(
        "compact_contract_sections: "
        + ", ".join([section] if section != "all" else list(_COMPACT_SURFACE_SECTIONS))
    )
    description = compact.get("description")
    if description:
        lines.append(str(description))
    algorithm = compact.get("algorithm")
    if isinstance(algorithm, Mapping):
        _append_compact_summary_line(lines, "algorithm.role", algorithm.get("role"))
        _append_compact_summary_line(
            lines,
            "algorithm.invocation_point",
            algorithm.get("invocation_point"),
        )
        _append_compact_summary_line(
            lines,
            "algorithm.description",
            algorithm.get("description"),
        )
    targets = compact.get("targets")
    if isinstance(targets, Mapping):
        _append_compact_summary_line(lines, "targets.files", targets.get("files"))
        _append_compact_summary_line(
            lines,
            "targets.allowed_actions",
            targets.get("allowed_actions"),
        )
        _append_compact_summary_line(
            lines,
            "targets.singleton",
            targets.get("singleton"),
        )
    interface = compact.get("interface")
    if isinstance(interface, Mapping):
        _append_compact_summary_line(
            lines,
            "interface.required_functions",
            interface.get("required_functions"),
        )
        _append_compact_summary_line(
            lines,
            "interface.function_signatures",
            interface.get("function_signatures"),
        )
        _append_compact_summary_line(
            lines,
            "interface.return_contract",
            interface.get("return_contract"),
        )
        _append_compact_summary_line(
            lines,
            "interface.return_values",
            interface.get("return_values"),
        )
    bounds = compact.get("bounds")
    if isinstance(bounds, Mapping):
        _append_compact_summary_line(
            lines,
            "bounds.allowed_components",
            bounds.get("allowed_components"),
        )
        _append_compact_summary_line(
            lines,
            "bounds.numeric_ranges",
            bounds.get("numeric_ranges"),
        )
        _append_compact_summary_line(
            lines,
            "bounds.complexity_scale_terms",
            bounds.get("complexity_scale_terms"),
        )
    evidence = compact.get("evidence")
    if isinstance(evidence, Mapping):
        _append_compact_summary_line(
            lines,
            "evidence.required_runtime_fields",
            evidence.get("required_runtime_fields"),
        )
    novelty = compact.get("novelty")
    if isinstance(novelty, Mapping):
        _append_compact_summary_line(
            lines,
            "novelty.strategy",
            novelty.get("strategy"),
        )
        _append_compact_summary_line(
            lines,
            "novelty.signature_fields",
            novelty.get("signature_fields"),
        )
    _append_compact_summary_line(lines, "prompt_hint", compact.get("prompt_hint"))
    return _limit_text("\n".join(lines), _COMPACT_SURFACE_INTERFACE_CHARS)

def _append_compact_summary_line(
    lines: list[str],
    label: str,
    value: Any,
) -> None:
    if value in (None, "", [], {}):
        return
    if isinstance(value, (Mapping, list, tuple)):
        rendered = json.dumps(_model_payload(value), sort_keys=True, default=str)
    else:
        rendered = str(value)
    lines.append(f"{label}: {_compact_text(rendered)}")

def _surface_code_char_limit(
    *,
    detail: str,
    requested_max: int | None,
) -> int:
    if requested_max is not None:
        return requested_max
    if detail == "full":
        return _FULL_SURFACE_CODE_CHARS
    return _COMPACT_SURFACE_CODE_CHARS

def _compact_text(value: Any, max_chars: int = _COMPACT_SURFACE_TEXT_CHARS) -> str:
    text = str(value).strip() if value is not None else ""
    return _limit_text(text, max_chars) if text else ""

def _coerce_compact_list(
    values: Any,
    *,
    max_items: int = _COMPACT_SURFACE_LIST_ITEMS,
) -> list[str]:
    if values is None:
        return []
    try:
        items = [str(value) for value in values if str(value)]
    except TypeError:
        return []
    return items[:max_items]

def _compact_mapping_payload(
    value: Any,
    *,
    max_items: int = _COMPACT_SURFACE_MAP_ITEMS,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    compact: dict[str, Any] = {}
    for idx, (key, item) in enumerate(
        sorted(value.items(), key=lambda pair: str(pair[0]))
    ):
        if idx >= max_items:
            break
        compact[str(key)] = _model_payload(item)
    return compact

def _drop_empty_items(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        str(key): value
        for key, value in payload.items()
        if value not in (None, "", [], {})
    }

def _surface_target_files(surface: Any) -> list[str]:
    targets = _attr(surface, "targets")
    files = _attr(targets, "files", None) if targets is not None else None
    if files is None:
        files = _attr(surface, "target_files", [])
    return [str(path) for path in (files or []) if str(path)]

def _first_concrete_target(target_files: list[str]) -> str | None:
    for target in target_files:
        if not any(ch in target for ch in "*?["):
            return target
    return None

def _target_declared(target_file: str, declared_targets: list[str]) -> bool:
    normalized = _normalize_rel_path(target_file)
    if normalized is None:
        return False
    for pattern in declared_targets:
        try:
            pattern = normalize_relative_glob_pattern(pattern)
        except ValueError:
            continue
        if pattern == normalized:
            return True
        if segment_glob_match(normalized, pattern):
            return True
    return False

def _read_solver_design_support_artifacts(
    source_root: str | Path,
    target_files: list[str],
    *,
    primary_target: str,
    detail: str,
    primary_code_char_limit: int,
    source_kind: str,
) -> list[dict[str, Any]]:
    root = Path(source_root).expanduser().resolve()
    primary = _normalize_rel_path(primary_target) or ""
    per_file_limit = min(primary_code_char_limit, _COMPACT_SURFACE_CODE_CHARS)
    if primary in {"policies/baseline_algorithm.py", "policies/solver_algorithm.py"}:
        total_limit = 6500 if detail == "full" else 7000
    else:
        total_limit = 11000 if detail == "full" else 9000
    artifacts: list[dict[str, Any]] = []
    remaining = total_limit
    for rel, path in _solver_design_support_candidate_paths(
        root,
        target_files,
        primary=primary,
    ):
        if len(artifacts) >= 12 or remaining <= 0:
            return artifacts
        read_limit = max(0, min(per_file_limit, remaining))
        artifact = _read_code_file_from_root(
            root,
            rel,
            max_chars=read_limit,
            source_kind=source_kind,
        )
        api_summary = _python_api_summary_for_file(path)
        if api_summary:
            artifact["python_api_summary"] = api_summary
        artifacts.append(artifact)
        if artifact.get("readable"):
            remaining -= len(str(artifact.get("content_preview", "")))
            remaining -= len(str(artifact.get("python_api_summary", "")))
    return artifacts

def _solver_design_support_candidate_paths(
    root: Path,
    target_files: list[str],
    *,
    primary: str,
) -> list[tuple[str, Path]]:
    declared: dict[str, Path] = {}
    for raw_pattern in target_files:
        try:
            pattern = normalize_relative_glob_pattern(raw_pattern)
        except ValueError:
            continue
        if not (
            pattern in {"policies/baseline_algorithm.py", "policies/solver_algorithm.py"}
            or pattern.startswith("policies/baseline_modules/")
        ):
            continue
        if not any(ch in pattern for ch in "*?["):
            candidates = [root / pattern]
        else:
            candidates = sorted(root.glob(pattern))
        for path in candidates:
            if not path.is_file():
                continue
            try:
                rel = path.relative_to(root).as_posix()
            except ValueError:
                continue
            if rel == primary or rel.endswith("/__init__.py"):
                continue
            declared.setdefault(rel, path)

    priority = {rel: idx for idx, rel in enumerate(_SOLVER_DESIGN_SUPPORT_PRIORITY)}
    return sorted(
        declared.items(),
        key=lambda item: (
            priority.get(item[0], len(priority)),
            item[0],
        ),
    )

def _python_api_summary_for_file(path: Path, *, max_chars: int = 1800) -> str:
    if path.suffix != ".py":
        return ""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return ""
    lines: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            methods = [
                _python_function_signature(child)
                for child in node.body
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]
            if methods:
                lines.append(f"class {node.name}: " + "; ".join(methods[:14]))
            else:
                lines.append(f"class {node.name}")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            lines.append("def " + _python_function_signature(node))
        if len(lines) >= 28:
            break
    if path.name == "state.py" and path.parent.name == "baseline_modules":
        lines.append(
            "state model note: _Solution has no from_routes/from_public/"
            "from_cvrp_solution/to_public bridge methods; use construction.py "
            "helpers or _Solution(instance, [_Route(instance, route) for route "
            "in routes]) and return via routes_as_tuples()."
        )
    if not lines:
        return ""
    return _limit_text("\n".join(lines), max_chars)

def _python_function_signature(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> str:
    args = node.args
    parts: list[str] = []
    for arg in [*args.posonlyargs, *args.args]:
        parts.append(arg.arg)
    if args.vararg is not None:
        parts.append("*" + args.vararg.arg)
    elif args.kwonlyargs:
        parts.append("*")
    for arg in args.kwonlyargs:
        parts.append(arg.arg)
    if args.kwarg is not None:
        parts.append("**" + args.kwarg.arg)
    return f"{node.name}({', '.join(parts)})"

def _read_champion_file(
    champion: ChampionState,
    target_file: str,
    *,
    max_chars: int,
) -> dict[str, Any]:
    return _read_code_file_from_root(
        champion.code_snapshot_path,
        target_file,
        max_chars=max_chars,
        source_kind="champion_snapshot",
    )

def _surface_code_read_root(context: ProposalToolContext) -> tuple[str | Path, str]:
    branch_workspace = str(context.branch_workspace or "").strip()
    if branch_workspace and os.path.isdir(branch_workspace):
        return branch_workspace, "branch_workspace"
    if context.champion is None:
        return "", "missing_snapshot"
    return context.champion.code_snapshot_path, "champion_snapshot"

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
            "file_path": target_file,
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

__all__ = [
    "ContextReadSurfaceTool",
    "_coerce_compact_list",
    "_compact_mapping_payload",
    "_compact_text",
    "_drop_empty_items",
    "_find_surface",
    "_first_concrete_target",
    "_read_champion_file",
    "_read_code_file_from_root",
    "_surface_allowed_actions",
    "_surface_for_hypothesis",
    "_surface_for_patch_path",
    "_surface_for_selected_or_patch_path",
    "_surface_function_signatures",
    "_surface_interface_summary",
    "_surface_list_for_context",
    "_surface_listing_payload",
    "_surface_name",
    "_surface_novelty_signature_requirement",
    "_surface_payload",
    "_surface_permission_summary",
    "_surface_read_payload",
    "_surface_required_functions",
    "_surface_return_values",
    "_surface_target_files",
    "_surfaces",
    "_target_declared",
]
