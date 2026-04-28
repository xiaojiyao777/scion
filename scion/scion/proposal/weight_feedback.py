"""Weight-opt feedback for LLM context injection (W10).

Provides coarse-grained, tentative parameter signals — which operators
are stable/unstable in recent weight optimizations. Never injected into
Decision layer (tainted metadata boundary).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from scion.core.models import WeightOptimizationResult


@dataclass(frozen=True)
class OperatorWeightSignal:
    operator_name: str
    current_weight: float
    baseline_weight: float
    direction: str  # "stable" | "increased" | "decreased"


def extract_weight_signals(
    result: Optional[WeightOptimizationResult],
) -> List[OperatorWeightSignal]:
    if result is None or not result.improved:
        return []

    signals = []
    for name in result.best_weights:
        best = result.best_weights[name]
        baseline = result.baseline_weights.get(name, best)
        if baseline == 0:
            direction = "stable"
        else:
            ratio = best / baseline
            if ratio > 1.2:
                direction = "increased"
            elif ratio < 0.8:
                direction = "decreased"
            else:
                direction = "stable"
        signals.append(OperatorWeightSignal(
            operator_name=name,
            current_weight=round(best, 3),
            baseline_weight=round(baseline, 3),
            direction=direction,
        ))
    return signals


def render_weight_feedback(
    result: Optional[WeightOptimizationResult],
) -> str:
    """Render weight-opt feedback as text for Round 1 prompt injection."""
    signals = extract_weight_signals(result)
    if not signals:
        return ""

    lines = ["## Parameter Search Feedback (tentative)"]
    increased = [s for s in signals if s.direction == "increased"]
    decreased = [s for s in signals if s.direction == "decreased"]
    stable = [s for s in signals if s.direction == "stable"]

    if increased:
        names = ", ".join(s.operator_name for s in increased)
        lines.append(f"  Operators with increased weight: {names}")
    if decreased:
        names = ", ".join(s.operator_name for s in decreased)
        lines.append(f"  Operators with decreased weight: {names}")
    if stable:
        names = ", ".join(s.operator_name for s in stable)
        lines.append(f"  Stable operators: {names}")

    lines.append("  (These signals are coarse-grained and tentative.)")
    return "\n".join(lines)
