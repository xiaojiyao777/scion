"""Deterministic CVRP solver-design patch interface checks."""

from __future__ import annotations

import re

from scion.core.models import HypothesisProposal, PatchProposal, patch_file_changes
from scion.core.paths import normalize_relative_patch_path


def static_smoke_issue(
    *,
    patch: PatchProposal,
    hypothesis: HypothesisProposal | None,
) -> str | None:
    del hypothesis
    changes = _patch_contents_by_path(patch)
    return _unknown_context_helper_issue(changes)


def _unknown_context_helper_issue(changes: dict[str, str]) -> str | None:
    code = "\n".join(changes.values())
    match = re.search(
        r"(?:context|self\.context)\.record_context\s*\(\s*['\"]"
        r"([A-Za-z][A-Za-z0-9_]{1,63})_iterations['\"]",
        code,
    )
    if not match and not re.search(
        r"(?:context|self\.context)\.record_context\s*\(",
        code,
    ):
        return None
    example_mechanism = match.group(1) if match else "<mechanism>"
    return (
        "solver_design static smoke rejected unknown telemetry helper "
        "`context.record_context(...)`. The active solver context exposes "
        "`context.record_phase(name, elapsed_ms)`, "
        "`context.record_iteration(phase, count)`, and "
        "`context.record_move(phase, attempted=..., accepted=..., delta=..., "
        "best_improved=...)`. To populate "
        "`solver_algorithm_context_records.<mechanism>_iterations`, call "
        f"`context.record_iteration('{example_mechanism}', count)`."
    )


def _patch_contents_by_path(patch: PatchProposal) -> dict[str, str]:
    contents: dict[str, str] = {}
    for change in patch_file_changes(patch):
        try:
            path = normalize_relative_patch_path(change.file_path)
        except ValueError:
            path = str(change.file_path or "")
        if path:
            contents[path] = str(change.code_content or "")
    return contents


__all__ = ["static_smoke_issue"]
