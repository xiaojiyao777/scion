"""Lossless code prompt rendering for the direct V3 proposal engine."""

from __future__ import annotations

from typing import Any, Dict

from .hypothesis_prompts import _direct_v3_canonical_json
from .prompt_common import _CACHE_5M


def _split_code_context(
    context: Dict[str, Any],
) -> tuple[list[dict], str]:
    """Render every supplied code-context field exactly once without size controls."""

    system_blocks = [
        {
            "type": "text",
            "text": (
                "You are implementing an approved research hypothesis for a "
                "combinatorial optimisation solver. Produce a source-bound typed "
                "edit set that preserves the problem-owned interface, feasibility, "
                "determinism, and declared higher-priority objectives."
            ),
            "cache_control": _CACHE_5M,
        },
        {
            "type": "text",
            "text": (
                "## Direct V3 Canonical Code Context\n"
                f"{_direct_v3_canonical_json(context)}"
            ),
        },
    ]
    user_prompt = (
        "## Implementation And Output Instructions\n"
        "Read the complete canonical context and visible source before editing. "
        "Implement the approved hypothesis as one coherent patch, including every "
        "necessary file in the typed edit set. Modify the approved target against "
        "the current visible source. For localized existing-file edits, prefer "
        "exact_replace so source outside the named selector is preserved. Reserve "
        "full_file for creates, broad rewrites, or an edit with no stable exact "
        "selector. For multiple edits to one file, repeat its path in application "
        "order and make each later old_string match the source produced by the "
        "earlier changes. Do not substitute a nearby target, "
        "silently weaken the mechanism, or add unrelated cleanup. Use direct "
        "algorithmic Python constructs as needed, but do not use process, network, "
        "environment, dynamic-import, or file APIs. Return the "
        "patch through the required tool schema."
    )
    return system_blocks, user_prompt


__all__ = ["_split_code_context"]
