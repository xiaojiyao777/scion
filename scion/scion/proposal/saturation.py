"""ChampionSaturationAnalyzer — objective-wise improvement saturation signals (J2)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Literal, Optional

from scion.core.models import StepRecord


@dataclass
class SaturationSignal:
    """Saturation signal for one objective dimension."""
    objective: str                    # e.g. "subcategory_splits", "total_cost"
    improvement_ratio: float          # (initial - current) / initial, positive = improved
    saturation_level: Literal["low", "medium", "high"]
    opportunity_hint: str             # human-readable improvement hint


class ChampionSaturationAnalyzer:
    """Analyzes champion improvement saturation across objective dimensions.

    Computation:
        baseline = v1 champion metrics (computed once at campaign start)
        current  = latest champion metrics
        ratio    = (baseline - current) / baseline  (for minimization objectives)

    Saturation levels:
        low:    < 30% improvement
        medium: 30-70% improvement
        high:   > 70% improvement
    """

    def __init__(self, baseline_metrics: Dict[str, float]) -> None:
        self._baseline = baseline_metrics  # e.g. {"subcategory_splits": 10.0, "total_cost": 50000.0}

    def analyze(
        self,
        current_metrics: Dict[str, float],
    ) -> List[SaturationSignal]:
        """Compute saturation signals by comparing current champion to baseline.

        Args:
            current_metrics: Current champion's metrics (e.g. from latest frozen experiment).

        Returns:
            List of SaturationSignal, one per objective dimension.
        """
        signals = []
        for obj, baseline_val in self._baseline.items():
            current_val = current_metrics.get(obj)
            if current_val is None or baseline_val == 0:
                continue

            # For minimization objectives (splits, cost): improvement = baseline - current
            improvement_ratio = (baseline_val - current_val) / abs(baseline_val)
            improvement_ratio = max(0.0, min(1.0, improvement_ratio))

            if improvement_ratio > 0.70:
                level: Literal["low", "medium", "high"] = "high"
                hint = "接近局部最优"
            elif improvement_ratio > 0.30:
                level = "medium"
                hint = "有一定改进空间"
            else:
                level = "low"
                hint = "仍有较大空间"

            signals.append(SaturationSignal(
                objective=obj,
                improvement_ratio=improvement_ratio,
                saturation_level=level,
                opportunity_hint=hint,
            ))

        return signals


def render_saturation_signals(signals: List[SaturationSignal]) -> str:
    """Render saturation signals as text block for LLM injection."""
    if not signals:
        return ""

    lines = ["## Champion 当前状态与改善空间\n"]
    lines.append("目标饱和度（vs baseline v1 champion）：")

    high_saturated = []
    low_saturated = []

    for s in signals:
        pct = int(s.improvement_ratio * 100)
        marker = "←" if s.saturation_level == "low" else "→"
        lines.append(f"  {s.objective}: 改善 {pct}%（{s.saturation_level} saturation）{marker} {s.opportunity_hint}")
        if s.saturation_level == "high":
            high_saturated.append(s.objective)
        elif s.saturation_level == "low":
            low_saturated.append(s.objective)

    # Add suggestion if there's a clear direction switch opportunity
    if high_saturated and low_saturated:
        lines.append(
            f"\n搜索建议：{', '.join(high_saturated)} 改善空间已高度饱和，"
            f"建议探索 {', '.join(low_saturated)} 方向。"
        )

    return "\n".join(lines)


def extract_champion_metrics_from_step(step: StepRecord) -> Optional[Dict[str, float]]:
    """Extract champion-side metrics from a step's protocol result.

    Looks for champion_subcategory_splits and champion_total_cost
    in the objective_breakdown of pairwise case feedback.
    Returns averages across all pairs, or None if no data.
    """
    if step.protocol_result is None:
        return None
    if not step.protocol_result.pair_feedback:
        return None

    splits_sum = 0.0
    cost_sum = 0.0
    count = 0

    for pf in step.protocol_result.pair_feedback:
        ob = pf.objective_breakdown
        if ob.champion_subcategory_splits is not None:
            splits_sum += ob.champion_subcategory_splits
            cost_sum += (ob.champion_total_cost or 0.0)
            count += 1

    if count == 0:
        return None

    return {
        "subcategory_splits": splits_sum / count,
        "total_cost": cost_sum / count,
    }


def extract_candidate_metrics_from_step(step: StepRecord) -> Optional[Dict[str, float]]:
    """Extract candidate-side metrics from a step's protocol result."""
    if step.protocol_result is None:
        return None
    if not step.protocol_result.pair_feedback:
        return None

    splits_sum = 0.0
    cost_sum = 0.0
    count = 0

    for pf in step.protocol_result.pair_feedback:
        ob = pf.objective_breakdown
        if ob.candidate_subcategory_splits is not None:
            splits_sum += ob.candidate_subcategory_splits
            cost_sum += (ob.candidate_total_cost or 0.0)
            count += 1

    if count == 0:
        return None

    return {
        "subcategory_splits": splits_sum / count,
        "total_cost": cost_sum / count,
    }
