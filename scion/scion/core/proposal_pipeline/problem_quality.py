"""Adapter-owned proposal quality checks for hypothesis generation."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class ProblemHypothesisQualityCheck:
    allowed: bool
    detail: str = ""
    structured_rejection: Mapping[str, Any] = field(default_factory=dict)


def validate_problem_hypothesis_quality(
    problem_runtime: Any,
    branch: Any,
    hypothesis: Any,
    *,
    step_history: Sequence[Any] | None = None,
) -> ProblemHypothesisQualityCheck:
    """Run an optional adapter-owned proposal quality hook.

    The hook is proposal-only: it may reject or ask for a retry before code
    generation, but it does not produce DecisionFeatures or alter protocol
    thresholds.
    """

    adapter = _runtime_attr(problem_runtime, "adapter")
    if adapter is None:
        adapter = _runtime_attr(problem_runtime, "_adapter")
    hook = getattr(adapter, "validate_hypothesis_quality", None)
    if not callable(hook):
        return ProblemHypothesisQualityCheck(allowed=True)
    try:
        raw = hook(
            branch=branch,
            hypothesis=hypothesis,
            step_history=tuple(step_history or ()),
        )
    except Exception as exc:
        return ProblemHypothesisQualityCheck(
            allowed=False,
            detail=f"agent_quality_blocked:problem_hypothesis_quality_hook_failed: {exc}",
            structured_rejection={
                "source": "problem_adapter",
                "gate_name": "problem_hypothesis_quality",
                "failure_code": "problem_hypothesis_quality_hook_failed",
                "agent_block_reason": "agent_quality_blocked",
            },
        )
    return _normalize_problem_quality_result(raw)


def _runtime_attr(runtime: Any, name: str) -> Any:
    return getattr(runtime, name, None) if runtime is not None else None


def _normalize_problem_quality_result(raw: Any) -> ProblemHypothesisQualityCheck:
    if isinstance(raw, ProblemHypothesisQualityCheck):
        return raw
    if raw is None or raw is True:
        return ProblemHypothesisQualityCheck(allowed=True)
    if raw is False:
        return ProblemHypothesisQualityCheck(
            allowed=False,
            detail="problem_hypothesis_quality_rejected",
        )
    if isinstance(raw, Mapping):
        allowed = bool(raw.get("allowed", raw.get("passed", True)))
        detail = str(raw.get("detail") or raw.get("reason") or "").strip()
        if not allowed and not detail:
            detail = "problem_hypothesis_quality_rejected"
        structured = raw.get("structured_rejection")
        if not isinstance(structured, Mapping):
            structured = {}
        return ProblemHypothesisQualityCheck(
            allowed=allowed,
            detail=detail,
            structured_rejection=dict(structured),
        )
    return ProblemHypothesisQualityCheck(allowed=True)


__all__ = [
    "ProblemHypothesisQualityCheck",
    "validate_problem_hypothesis_quality",
]
