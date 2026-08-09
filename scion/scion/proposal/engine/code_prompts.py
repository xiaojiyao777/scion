"""Lossless code prompt rendering for the direct V3 proposal engine."""

from __future__ import annotations

from typing import Any, Dict

from .hypothesis_prompts import _direct_v3_canonical_json
from .prompt_common import _CACHE_5M


def _split_code_context(
    context: Dict[str, Any],
) -> tuple[list[dict], str]:
    """Render every supplied code-context field exactly once without size controls."""

    provider_context = _provider_code_context(context)

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
        "Read the complete canonical context and visible source before editing. "
        "Implement the approved hypothesis as one coherent patch, including every "
        "necessary file in the typed edit set. Keep the primary edit on the "
        "approved target and follow the tool schema's edit protocol. Do not "
        "substitute a nearby target, "
        "silently weaken the mechanism, or add unrelated cleanup. Use direct "
        "algorithmic Python constructs as needed, but do not use process, network, "
        "environment, dynamic-import, or file APIs. Return the "
        "patch through the required tool schema."
    )
    return system_blocks, user_prompt


def _provider_code_context(context: Dict[str, Any]) -> dict[str, Any]:
    """Hide source-binding bookkeeping while preserving every visible source."""

    projected = dict(context)
    ledger = context.get("proposal_source_ledger")
    if not isinstance(ledger, dict):
        return projected
    projected.pop("proposal_source_ledger", None)
    approved_target = str(ledger.get("approved_target") or "")
    sources: list[dict[str, Any]] = []
    for entry in ledger.get("entries") or ():
        if not isinstance(entry, dict):
            continue
        path = str(entry.get("path") or "")
        if not path:
            continue
        if entry.get("visibility") == "full_current":
            sources.append({"path": path, "content": entry.get("content")})
        elif path == approved_target:
            sources.append({"path": path, "content": None})
    projected["editable_source_context"] = {
        "approved_target": approved_target,
        "sources": sources,
        "target_api_guidance": str(ledger.get("target_api_guidance") or ""),
    }
    return projected


__all__ = ["_split_code_context"]
