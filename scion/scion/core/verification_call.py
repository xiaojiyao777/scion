"""Compatibility helper for invoking VerificationGate-like objects."""
from __future__ import annotations

import inspect
from typing import Any


def run_verification_gate(
    gate: Any,
    candidate_workspace: str,
    champion_workspace: str,
    patch: Any,
    *,
    hypothesis: Any | None = None,
) -> Any:
    """Call real gates with hypothesis metadata while preserving old test stubs."""

    run = gate.run
    try:
        signature = inspect.signature(run)
    except (TypeError, ValueError):
        return run(candidate_workspace, champion_workspace, patch)

    accepts_kwargs = any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD
        for parameter in signature.parameters.values()
    )
    if accepts_kwargs or "hypothesis" in signature.parameters:
        return run(
            candidate_workspace,
            champion_workspace,
            patch,
            hypothesis=hypothesis,
        )
    return run(candidate_workspace, champion_workspace, patch)
