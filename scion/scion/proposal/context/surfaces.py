"""Research-surface context rendering helpers.

The helpers in this module render problem-declared metadata only. They do not
encode problem-domain semantics; problem-specific nouns and mechanics must come
from the loaded problem spec or adapter.
"""

from __future__ import annotations

import json
from typing import Any, List

from scion.core.forced_surface import surface_action_allowed, surface_target_files
from scion.core.models import HypothesisRecord

_NONEMPTY_SEQUENCE_NOVELTY_FIELDS = frozenset(
    {
        "selected_components",
        "deep_components_selected",
    }
)


def _get_research_surfaces(problem_spec: Any, adapter_spec: Any = None) -> list[Any]:
    for spec in (problem_spec, adapter_spec):
        surfaces = getattr(spec, "research_surfaces", None)
        if surfaces:
            return list(surfaces)
    return []


def _find_research_surface(surfaces: list[Any], name: str) -> Any | None:
    for surface in surfaces:
        if getattr(surface, "name", None) == name:
            return surface
    return None


def _hypothesis_visible_research_surfaces(
    surfaces: list[Any],
    *,
    forced_surface: str | None,
    active_problem_boundary_surfaces: list[str],
) -> list[Any]:
    forced = str(forced_surface or "").strip()
    if forced:
        constrained = [
            surface
            for surface in surfaces
            if str(getattr(surface, "name", "") or "").strip() == forced
        ]
        return constrained or surfaces
    active = {
        str(surface or "").strip()
        for surface in active_problem_boundary_surfaces
        if str(surface or "").strip()
    }
    if not active:
        return surfaces
    constrained = [
        surface
        for surface in surfaces
        if str(getattr(surface, "name", "") or "").strip() in active
    ]
    return constrained or surfaces


def _build_inactive_surface_exclusion_block(
    surfaces: list[Any],
    *,
    visible_research_surfaces: list[Any],
    active_problem_boundary_surfaces: list[str],
) -> str:
    if not active_problem_boundary_surfaces:
        return ""
    visible = {
        str(getattr(surface, "name", "") or "").strip()
        for surface in visible_research_surfaces
    }
    inactive = [
        str(getattr(surface, "name", "") or "").strip()
        for surface in surfaces
        if str(getattr(surface, "name", "") or "").strip()
        and str(getattr(surface, "name", "") or "").strip() not in visible
    ]
    if not inactive:
        return ""
    return (
        "## Inactive/Legacy Surface Exclusion\n"
        "Active problem-boundary control is in force. The surfaces below are "
        "retained only for legacy compatibility, forced diagnostics, or "
        "regression coverage; they are omitted from active hypothesis grounding "
        "and must not replace the active solver-design research object:\n"
        + "- inactive/legacy: "
        + ", ".join(inactive)
    )


def _include_operator_files_for_research_code(surfaces: list[Any]) -> bool:
    if not surfaces:
        return True
    return any(
        str(getattr(surface, "kind", "") or "") == "operator"
        for surface in surfaces
    )


def _build_research_surfaces_block(surfaces: list[Any]) -> str:
    if not surfaces:
        return ""
    lines = [
        "## Research Surfaces",
        (
            "Metadata below is declared by the problem package. Framework core "
            "treats algorithm roles, invocation points, bounds, scale terms, "
            "runtime evidence, and novelty fields as problem-provided context."
        ),
    ]
    for surface in surfaces:
        name = getattr(surface, "name", "")
        kind = getattr(surface, "kind", "")
        description = getattr(surface, "description", "")
        lines.append(f"- {name} [{kind}]: {description}")
        _append_research_surface_metadata(lines, surface, prefix="  ")
    return "\n".join(lines)


def _build_research_surface_interface_spec(surface: Any) -> str:
    """Render a generic active-surface interface from declared metadata."""
    name = getattr(surface, "name", "")
    kind = getattr(surface, "kind", "")
    description = getattr(surface, "description", "")
    lines = [f"### Declared Research Surface: {name} [{kind}]"]
    if description:
        lines.append(description)
    _append_research_surface_metadata(lines, surface, prefix="")
    return "\n".join(lines)


def _build_forced_surface_constraint(
    *,
    surface: Any | None,
    surface_name: str,
    action: str | None,
    target_file: str | None,
    diagnostic: bool,
    blocking_hypotheses: List[HypothesisRecord] | None = None,
) -> str:
    lines = ["\n## MANDATORY SEARCH CONSTRAINT"]
    if diagnostic:
        lines.append(
            "A diagnostic experiment-control hook is active for the next "
            "hypothesis generation."
        )
    else:
        lines.append(
            "The campaign has detected saturation in the current search "
            "direction and is forcing locus diversification."
        )
    lines.extend(
        [
            f"Your hypothesis MUST target research surface `{surface_name}`.",
            f"Set `change_locus` to `{surface_name}`.",
        ]
    )
    if action:
        lines.append(f"Set `action` to `{action}`.")
    elif surface is not None:
        allowed = [
            candidate
            for candidate in ("create_new", "modify", "remove")
            if surface_action_allowed(surface, candidate)
        ]
        if allowed:
            lines.append(
                "Choose one legal action for that surface: "
                + ", ".join(allowed)
                + "."
            )
    if target_file:
        lines.append(f"Set `target_file` to `{target_file}`.")
    elif surface is not None:
        targets = surface_target_files(surface)
        if targets:
            lines.append("Declared target files: " + ", ".join(targets) + ".")
    lines.extend(
        _build_forced_surface_novelty_guidance(
            surface=surface,
            surface_name=surface_name,
            blocking_hypotheses=blocking_hypotheses or [],
        )
    )
    return "\n".join(lines) + "\n"


def _build_forced_surface_novelty_guidance(
    *,
    surface: Any | None,
    surface_name: str,
    blocking_hypotheses: List[HypothesisRecord],
) -> list[str]:
    if surface is None:
        return []
    novelty = getattr(surface, "novelty", None)
    strategy = str(getattr(novelty, "strategy", "") or "")
    fields = _coerce_text_list(getattr(novelty, "signature_fields", None))
    if strategy != "semantic_signature" or not fields:
        return []

    lines = [
        "This surface uses structured semantic novelty.",
        "C10 requires `novelty_signature` with distinct values for declared "
        f"`novelty.signature_fields`: {', '.join(fields)}.",
        "Do not use hypothesis prose as novelty identity; C10 ignores free text "
        "for this semantic signature.",
        "Use compact novelty_signature values; scalar strings longer than 120 "
        "characters are invalid.",
    ]
    sequence_fields = [
        field for field in fields if field in _NONEMPTY_SEQUENCE_NOVELTY_FIELDS
    ]
    if sequence_fields:
        lines.append(
            "These novelty_signature fields must be non-empty JSON arrays of "
            "component names, not null, false, empty strings, or empty arrays: "
            + ", ".join(sequence_fields)
            + "."
        )
    occupied = _summarise_surface_structured_signatures(
        blocking_hypotheses,
        surface_name=surface_name,
        fields=fields,
    )
    if occupied:
        lines.append("Occupied structured signatures for this surface:")
        lines.extend(f"  - {item}" for item in occupied)
    else:
        lines.append("Occupied structured signatures for this surface: (none)")
    return lines


def _summarise_surface_structured_signatures(
    active_hypotheses: List[HypothesisRecord],
    *,
    surface_name: str,
    fields: list[str],
) -> list[str]:
    summaries: list[str] = []
    for hypothesis in active_hypotheses:
        if hypothesis.change_locus != surface_name:
            continue
        signature: dict[str, Any] = {}
        for field in fields:
            if hasattr(hypothesis, field):
                value = getattr(hypothesis, field)
                if value not in (None, "", [], (), {}):
                    signature[field] = value
                    continue
            novelty_values = getattr(hypothesis, "novelty_signature", None)
            if isinstance(novelty_values, dict) and field in novelty_values:
                signature[field] = novelty_values[field]
        if signature:
            summaries.append(
                json.dumps(signature, sort_keys=True, default=str, separators=(",", ":"))
            )
        else:
            target = hypothesis.target_file or "(no target_file)"
            summaries.append(f"{target}: missing structured novelty_signature")
    return summaries


def _append_research_surface_metadata(
    lines: list[str],
    surface: Any,
    *,
    prefix: str,
) -> None:
    algorithm = getattr(surface, "algorithm", None)
    if algorithm is not None:
        _append_metadata_value(
            lines, prefix, "algorithm.role", getattr(algorithm, "role", "")
        )
        _append_metadata_value(
            lines,
            prefix,
            "algorithm.invocation_point",
            getattr(algorithm, "invocation_point", ""),
        )
        _append_metadata_value(
            lines,
            prefix,
            "algorithm.description",
            getattr(algorithm, "description", ""),
        )

    targets = getattr(surface, "targets", None)
    target_files = _coerce_text_list(
        getattr(targets, "files", None) if targets is not None else None
    ) or _coerce_text_list(getattr(surface, "target_files", None))
    if target_files:
        lines.append(f"{prefix}targets.files: {', '.join(target_files)}")

    if targets is not None or _has_any_attr(
        surface,
        ("create_new_allowed", "modify_allowed", "remove_allowed"),
    ):
        create_new_allowed = _get_nested_or_legacy_bool(
            targets, surface, "create_new_allowed"
        )
        modify_allowed = _get_nested_or_legacy_bool(targets, surface, "modify_allowed")
        remove_allowed = _get_nested_or_legacy_bool(targets, surface, "remove_allowed")
        lines.append(
            f"{prefix}action permissions: "
            f"create_new={_format_bool(create_new_allowed)}, "
            f"modify={_format_bool(modify_allowed)}, "
            f"remove={_format_bool(remove_allowed)}"
        )

    singleton = getattr(targets, "singleton", None) if targets is not None else None
    if singleton is not None:
        lines.append(f"{prefix}singleton: {_format_bool(bool(singleton))}")

    interface = getattr(surface, "interface", None)
    required_functions = _coerce_text_list(
        getattr(interface, "required_functions", None)
        if interface is not None
        else None
    ) or _coerce_text_list(getattr(surface, "required_functions", None))
    if required_functions:
        lines.append(
            f"{prefix}interface.required_functions: "
            f"{', '.join(required_functions)}"
        )
    if interface is not None:
        formatted_signatures = _format_function_signatures(
            getattr(interface, "function_signatures", None)
        )
        if formatted_signatures:
            lines.append(
                f"{prefix}interface.function_signatures: "
                f"{formatted_signatures}"
            )
        _append_metadata_value(
            lines,
            prefix,
            "interface.return_contract",
            getattr(interface, "return_contract", ""),
        )
        formatted_return_values = _format_return_values(
            getattr(interface, "return_values", None)
        )
        if formatted_return_values:
            lines.append(
                f"{prefix}interface.return_values: {formatted_return_values}"
            )

    bounds = getattr(surface, "bounds", None)
    if bounds is not None:
        allowed_components = _coerce_text_list(
            getattr(bounds, "allowed_components", None)
        )
        if allowed_components:
            lines.append(
                f"{prefix}bounds.allowed_components: "
                f"{', '.join(allowed_components)}"
            )
        numeric_ranges = getattr(bounds, "numeric_ranges", None) or {}
        formatted_ranges = _format_numeric_ranges(numeric_ranges)
        if formatted_ranges:
            lines.append(f"{prefix}bounds.numeric_ranges: {formatted_ranges}")
        complexity_terms = _coerce_text_list(
            getattr(bounds, "complexity_scale_terms", None)
        )
        if complexity_terms:
            lines.append(
                f"{prefix}bounds.complexity_scale_terms: "
                f"{', '.join(complexity_terms)}"
            )

    evidence = getattr(surface, "evidence", None)
    if evidence is not None:
        runtime_fields = _coerce_text_list(
            getattr(evidence, "required_runtime_fields", None)
        )
        if runtime_fields:
            lines.append(
                f"{prefix}evidence.required_runtime_fields: "
                f"{', '.join(runtime_fields)}"
            )
        mechanism_telemetry = getattr(evidence, "mechanism_telemetry", None)
        if mechanism_telemetry:
            lines.append(
                f"{prefix}evidence.mechanism_telemetry: "
                + json.dumps(
                    _json_ready_mechanism_telemetry(mechanism_telemetry),
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )

    novelty = getattr(surface, "novelty", None)
    if novelty is not None:
        _append_metadata_value(
            lines, prefix, "novelty.strategy", getattr(novelty, "strategy", "")
        )
        signature_fields = _coerce_text_list(
            getattr(novelty, "signature_fields", None)
        )
        if signature_fields:
            lines.append(
                f"{prefix}novelty.signature_fields: "
                f"{', '.join(signature_fields)}"
            )

    prompt = getattr(surface, "prompt", None)
    if prompt is not None:
        _append_metadata_value(
            lines,
            prefix,
            "prompt.hypothesis_guidance",
            getattr(prompt, "hypothesis_guidance", ""),
        )
        _append_metadata_value(
            lines,
            prefix,
            "prompt.implementation_guidance",
            getattr(prompt, "implementation_guidance", ""),
        )
        _append_metadata_value(
            lines,
            prefix,
            "prompt.anti_patterns",
            getattr(prompt, "anti_patterns", ""),
        )
    elif getattr(surface, "prompt_hint", ""):
        lines.append(f"{prefix}prompt.implementation_guidance: {surface.prompt_hint}")


def _append_metadata_value(
    lines: list[str],
    prefix: str,
    label: str,
    value: Any,
) -> None:
    text = str(value).strip() if value is not None else ""
    if text:
        lines.append(f"{prefix}{label}: {text}")


def _coerce_text_list(values: Any) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        return [values] if values else []
    try:
        return [str(value) for value in values if str(value)]
    except TypeError:
        return [str(values)] if str(values) else []


def _format_numeric_ranges(ranges: Any) -> str:
    if not isinstance(ranges, dict):
        return ""
    parts: list[str] = []
    for key in sorted(ranges):
        value = ranges[key]
        if isinstance(value, (list, tuple)) and len(value) == 2:
            parts.append(f"{key}=[{value[0]}, {value[1]}]")
        else:
            parts.append(f"{key}={value}")
    return "; ".join(parts)


def _format_function_signatures(signatures: Any) -> str:
    if not isinstance(signatures, dict):
        return ""
    parts: list[str] = []
    for name in sorted(signatures):
        args = _coerce_text_list(signatures[name])
        parts.append(f"{name}({', '.join(args)})")
    return "; ".join(parts)


def _format_return_values(return_values: Any) -> str:
    if not isinstance(return_values, dict):
        return ""
    parts: list[str] = []
    for name in sorted(return_values):
        spec = return_values[name]
        value_type = getattr(spec, "value_type", "")
        fragments: list[str] = []
        if value_type and value_type != "any":
            fragments.append(f"type={value_type}")
        allowed = _coerce_text_list(getattr(spec, "allowed_literals", None))
        if allowed:
            fragments.append("allowed=" + ",".join(allowed))
        numeric_range = getattr(spec, "numeric_range", None)
        if isinstance(numeric_range, (list, tuple)) and len(numeric_range) == 2:
            fragments.append(f"range=[{numeric_range[0]}, {numeric_range[1]}]")
        allowed_keys = _coerce_text_list(getattr(spec, "allowed_keys", None))
        if allowed_keys:
            fragments.append("keys=" + ",".join(allowed_keys))
        value_range = getattr(spec, "value_numeric_range", None)
        if isinstance(value_range, (list, tuple)) and len(value_range) == 2:
            fragments.append(f"value_range=[{value_range[0]}, {value_range[1]}]")
        if fragments:
            parts.append(f"{name}({'; '.join(fragments)})")
    return "; ".join(parts)


def _has_any_attr(obj: Any, names: tuple[str, ...]) -> bool:
    return any(hasattr(obj, name) for name in names)


def _get_nested_or_legacy_bool(nested: Any, legacy: Any, name: str) -> bool:
    if nested is not None and hasattr(nested, name):
        return bool(getattr(nested, name))
    return bool(getattr(legacy, name, False))


def _format_bool(value: bool) -> str:
    return "true" if value else "false"


def _surface_file_targets(research_surfaces: list[Any]) -> list[str]:
    files: set[str] = set()
    for surface in research_surfaces:
        if getattr(surface, "kind", None) == "operator":
            continue
        for target in surface_target_files(surface):
            target = str(target)
            if "*" not in target:
                files.add(target.lstrip("/"))
    return sorted(files)


def _solver_design_surface_names(research_surfaces: List[Any]) -> list[str]:
    names: list[str] = []
    for surface in research_surfaces:
        name = str(getattr(surface, "name", "") or "").strip()
        if not name:
            continue
        kind = str(getattr(surface, "kind", "") or "").strip().lower()
        role = str(getattr(getattr(surface, "algorithm", None), "role", "") or "").lower()
        if (
            kind in {"solver_design", "solver_algorithm"}
            or "solver_design" in role
            or "solver_algorithm" in role
        ):
            names.append(name)
    return names


def _surface_target_files_for_names(
    research_surfaces: List[Any],
    names: List[str],
) -> list[str]:
    allowed = {str(name or "").strip() for name in names if str(name or "").strip()}
    if not allowed:
        return []
    files: list[str] = []
    for surface in research_surfaces:
        name = str(getattr(surface, "name", "") or "").strip()
        if name not in allowed:
            continue
        for target in surface_target_files(surface):
            if target not in files:
                files.append(target)
    return sorted(files)


def _json_ready_mechanism_telemetry(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        try:
            items = value.items()
        except AttributeError:
            return {}
    else:
        items = value.items()
    payload: dict[str, Any] = {}
    for raw_key, raw_spec in items:
        key = str(raw_key or "").strip()
        if not key:
            continue
        if isinstance(raw_spec, dict):
            activation = raw_spec.get("activation_runtime_fields", [])
            effect = raw_spec.get("effect_probe_runtime_fields", [])
        else:
            activation = getattr(raw_spec, "activation_runtime_fields", [])
            effect = getattr(raw_spec, "effect_probe_runtime_fields", [])
        payload[key] = {
            "activation_runtime_fields": _coerce_text_list(activation),
            "effect_probe_runtime_fields": _coerce_text_list(effect),
        }
    return payload


def _is_solver_design_context_surface(surface_name: str, surface: Any) -> bool:
    name = str(surface_name or "").strip()
    kind = str(getattr(surface, "kind", "") or "").strip()
    return name in {"solver_design", "solver_algorithm"} or kind in {
        "solver_design",
        "solver_algorithm",
    }


__all__ = [
    name
    for name in globals()
    if not (name.startswith("__") and name.endswith("__"))
]
