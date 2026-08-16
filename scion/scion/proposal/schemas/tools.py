"""Provider tool definitions for the direct V3 proposal flow."""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any, Dict, Mapping

from .hypothesis import HYPOTHESIS_PROPOSAL_SCHEMA
from .patch import EXACT_LINE_REPLACE_EXAMPLE, PATCH_PROPOSAL_SCHEMA

_EXACT_LINE_REPLACE_EXAMPLE_JSON = json.dumps(
    EXACT_LINE_REPLACE_EXAMPLE,
    separators=(",", ":"),
)

HYPOTHESIS_TOOL: Dict[str, Any] = {
    "name": "generate_hypothesis",
    "description": (
        "Propose one concrete hypothesis for improving a declared research "
        "surface. Ground it in the visible champion source and evidence, name "
        "the current weakness, explain the proposed mechanism and measurable "
        "effect, preserve the problem-owned interface and safety semantics, "
        "and return only the declared minimal fields."
    ),
    "input_schema": HYPOTHESIS_PROPOSAL_SCHEMA,
}

PATCH_TOOL: Dict[str, Any] = {
    "name": "generate_patch",
    "description": (
        "Generate one complete typed edit set implementing the approved "
        "hypothesis. Keep the primary edit on its approved target and put every "
        "necessary same-mechanism support edit in additional_changes.\n\n"
        "- Choose exact_replace for an exact source block whose indentation is "
        "part of the selector. Choose "
        "exact_line_replace when the identical complete logical-line body repeats "
        "at different outer indentation depths; use an unindented, "
        "line-ending-free old_string and replace_all=true. Provide new_string "
        "as an LF-separated relative-indentation block without a terminal "
        "newline; the host replays each match's outer indentation and EOL. One "
        "example illustrating only the JSON shape, without requiring this edit "
        "intent, is: "
        f"{_EXACT_LINE_REPLACE_EXAMPLE_JSON}\n"
        "- Choose full_file for creates, broad rewrites, or an edit with no "
        "stable exact selector. Deletes declare the typed delete action.\n"
        "- Each file_path may appear exactly once. Express all intended changes "
        "to one file in that single typed edit; duplicate paths are rejected.\n"
        "- For exact_replace or exact_line_replace provide non-empty old_string, "
        'new_string, and replace_all. To delete text use new_string: ""; '
        "never omit new_string or set it to null. Do not emit unified diffs."
    ),
    "input_schema": PATCH_PROPOSAL_SCHEMA,
}


def bind_hypothesis_tool_to_context(
    context: Mapping[str, Any],
) -> tuple[Dict[str, Any], tuple[str, ...]]:
    """Bind the provider tool to the exact visible research-surface names."""

    surfaces = context.get("research_surfaces")
    if not isinstance(surfaces, (list, tuple)) or not surfaces:
        raise ValueError(
            "hypothesis provider context requires non-empty research_surfaces"
        )
    names: list[str] = []
    for index, surface in enumerate(surfaces):
        if not isinstance(surface, Mapping):
            raise ValueError(
                "hypothesis provider research surface must be a mapping at "
                f"index {index}"
            )
        name = surface.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(
                "hypothesis provider research surface requires a non-empty "
                f"name at index {index}"
            )
        if name != name.strip():
            raise ValueError(
                "hypothesis provider research surface name must not contain "
                f"leading or trailing whitespace at index {index}"
            )
        if name in names:
            raise ValueError(f"duplicate hypothesis provider research surface: {name}")
        names.append(name)

    tool = deepcopy(HYPOTHESIS_TOOL)
    locus_schema = tool["input_schema"]["properties"]["change_locus"]
    locus_schema["enum"] = list(names)
    locus_schema["description"] = (
        "Return exactly one declared research-surface name from this enum; "
        "do not append a mechanism description."
    )
    return tool, tuple(names)


__all__ = [
    "HYPOTHESIS_TOOL",
    "PATCH_TOOL",
    "bind_hypothesis_tool_to_context",
]
