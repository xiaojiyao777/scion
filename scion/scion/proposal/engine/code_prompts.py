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
        "necessary file in the typed edit set. Bind modifications to the supplied "
        "source owner, provenance, and digest. Do not substitute a nearby target, "
        "silently weaken the mechanism, or add unrelated cleanup. Use direct "
        "attribute access: do not use "
        "setattr, delattr, dynamic-name getattr, globals, locals, or vars, and do not "
        "use process, network, environment, dynamic-import, or file APIs. Return the "
        "patch through the required tool schema."
    )
    return system_blocks, user_prompt


__all__ = ["_split_code_context"]
