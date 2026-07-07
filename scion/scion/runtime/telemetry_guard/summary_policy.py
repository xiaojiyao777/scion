"""Problem-owned telemetry summary policy application."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from scion.problem.providers import (
    ProblemProviderError,
    resolve_mechanism_evidence_policy_provider,
)


def apply_problem_mechanism_evidence_policy(
    summary: dict[str, Any],
    *,
    problem_spec: Any | None = None,
    adapter: Any | None = None,
    context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply optional problem-owned mechanism evidence interpretation."""

    try:
        provider = resolve_mechanism_evidence_policy_provider(
            problem_spec=problem_spec,
            adapter=adapter,
        )
    except ProblemProviderError:
        return summary
    if provider is None:
        return summary
    method = getattr(provider, "apply_mechanism_evidence_policy", None)
    if not callable(method):
        return summary
    try:
        rewritten = method(summary, context=dict(context or {}))
    except TypeError:
        rewritten = method(summary)
    if rewritten is None:
        return summary
    if not isinstance(rewritten, Mapping):
        return summary
    if rewritten is summary:
        return summary
    return dict(rewritten)


__all__ = ["apply_problem_mechanism_evidence_policy"]
