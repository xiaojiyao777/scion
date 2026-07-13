"""Provider tool definitions for the direct V3 proposal flow."""

from __future__ import annotations

from typing import Any, Dict

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
        "- Existing files may use exact_replace or full_file when the edit is "
        "bound to visible source, its owner attribution, and source_digest.\n"
        "- Creates use full_file content and deletes declare the typed delete action.\n"
        "- For exact_replace provide source_digest, non-empty old_string, "
        "new_string, and replace_all. To delete text use new_string: \"\"; "
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

__all__ = [
    "HYPOTHESIS_TOOL",
    "PATCH_TOOL",
]
