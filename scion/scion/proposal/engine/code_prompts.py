"""Research-core code prompt rendering for the direct V3 proposal engine."""

from __future__ import annotations

from typing import Any, Dict

from .hypothesis_prompts import _direct_v3_canonical_json
from .prompt_common import _CACHE_5M


def _split_code_context(
    context: Dict[str, Any],
) -> tuple[list[dict], str]:
    """Render only the approved hypothesis and its frozen editable source."""

    provider_context = {
        "approved_hypothesis": context["approved_hypothesis"],
        "editable_source_context": context["editable_source_context"],
    }

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
                f"{_direct_v3_canonical_json(provider_context)}"
            ),
        },
    ]
    user_prompt = (
        "## Implementation And Output Instructions\n"
        "Implement the approved hypothesis from the current source and target API "
        "guidance as one coherent patch, including necessary companion edits; "
        "follow the tool schema's edit protocol and return the patch through the "
        "required tool schema."
    )
    return system_blocks, user_prompt


__all__ = ["_split_code_context"]
