"""Surface metadata payload and interface-summary builders."""

from __future__ import annotations

import json
from typing import Any, Mapping

from scion.proposal.context_manager import _build_research_surface_interface_spec
from scion.proposal.tools.surface.compaction import (
    _coerce_compact_list,
    _compact_mapping_payload,
    _compact_text,
    _drop_empty_items,
)
from scion.proposal.tools.surface.constants import (
    _COMPACT_SURFACE_HINT_CHARS,
    _COMPACT_SURFACE_INTERFACE_CHARS,
    _COMPACT_SURFACE_LIST_ITEMS,
    _COMPACT_SURFACE_MAP_ITEMS,
    _COMPACT_SURFACE_SECTIONS,
    _COMPACT_SURFACE_TEXT_CHARS,
)
from scion.proposal.tools.surface.metadata import (
    _surface_allowed_actions,
    _surface_function_signatures,
    _surface_required_functions,
    _surface_return_values,
    _surface_target_files,
)
from scion.proposal.tools.utils import _attr, _limit_text, _model_payload


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
            ),
            "optional_runtime_fields": _coerce_compact_list(
                _attr(evidence, "optional_runtime_fields", [])
            ),
            "activity_runtime_fields": _coerce_compact_list(
                _attr(evidence, "activity_runtime_fields", [])
            ),
            "activation_runtime_fields": _compact_mapping_payload(
                _attr(evidence, "activation_runtime_fields", {})
            ),
            "effect_probe_runtime_fields": _coerce_compact_list(
                _attr(evidence, "effect_probe_runtime_fields", [])
            ),
            "stage_budget_runtime_fields": _coerce_compact_list(
                _attr(evidence, "stage_budget_runtime_fields", [])
            ),
            "mechanism_telemetry": _compact_mapping_payload(
                _attr(evidence, "mechanism_telemetry", {})
            ),
            "fail_closed_on_zero_activity": _attr(
                evidence, "fail_closed_on_zero_activity", False
            ),
            "fail_closed_on_stage_budget_starvation": _attr(
                evidence,
                "fail_closed_on_stage_budget_starvation",
                False,
            ),
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
        _append_compact_summary_line(
            lines,
            "evidence.mechanism_telemetry",
            evidence.get("mechanism_telemetry"),
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

__all__ = [
    "_surface_payload",
    "_surface_listing_payload",
    "_surface_read_payload",
    "_surface_compact_payload",
    "_compact_algorithm_payload",
    "_compact_targets_payload",
    "_compact_interface_payload",
    "_compact_bounds_payload",
    "_compact_evidence_payload",
    "_compact_novelty_payload",
    "_surface_contract_metadata",
    "_surface_section_paths",
    "_target_artifact_preview",
    "_surface_interface_summary",
    "_compact_surface_interface_summary",
    "_append_compact_summary_line",
]
