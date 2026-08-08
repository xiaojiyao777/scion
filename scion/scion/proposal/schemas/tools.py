"""Provider tool definitions for the direct V3 proposal flow."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Mapping

from .hypothesis import HYPOTHESIS_PROPOSAL_SCHEMA
from .patch import PATCH_PROPOSAL_SCHEMA


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
        "Generate a typed edit set implementing an approved hypothesis.\n\n"
        "Usage:\n"
        "- For localized existing-file edits, prefer exact_replace so source "
        "outside the named selector is preserved.\n"
        "- Reserve full_file for creates, broad rewrites, or an edit with no "
        "stable exact selector. Deletes declare the typed delete action.\n"
        "- When one existing file needs multiple non-contiguous edits, emit "
        "multiple ordered exact_replace change objects for the same file_path "
        "in application order. Repeat file_path, and make each later old_string "
        "match the source produced by the earlier changes. The host binds, "
        "applies, and composes them serially. Do not mix same-file exact_replace edits "
        "with create, delete, or full_file; use one full_file change instead.\n"
        "- For exact_replace provide non-empty old_string, new_string, and "
        "replace_all. To delete text use new_string: \"\"; "
        "never omit new_string or set it to null.\n"
        "- Do not emit unified diffs; the host derives audit diffs from before/after content.\n"
        "- Study the champion research-surface files for style, data model usage, and import patterns.\n"
        "- Follow the problem-specific research-surface interface EXACTLY.\n\n"
        "Code quality requirements:\n"
        "- Preserve every feasibility and consistency invariant described in the interface spec.\n"
        "- For operator surfaces, use the provided `rng` argument for ALL randomness.\n"
        "- NEVER use `list(set(...))` or iterate over set/dict in order-dependent ways — "
        "use `sorted()` for determinism.\n"
        "- Choose algorithmic scope from the hypothesis, visible source, problem "
        "semantics, and measured evidence; Scion does not impose a search-size cap.\n"
        "- Return a valid solution/artifact according to the problem adapter contract when implementing an operator surface.\n\n"
        "Common rejection causes:\n"
        "- Feasibility or solution consistency violation.\n"
        "- Non-determinism: iterating over sets without sorting.\n"
        "- Import violation: using modules not in the whitelist.\n"
        "- Interface mismatch: wrong method signature, missing module-level policy function, or missing deep copy."
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
            raise ValueError(
                f"duplicate hypothesis provider research surface: {name}"
            )
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
