"""ChampionSaturationAnalyzer — objective-wise improvement saturation signals (J2)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Literal, Optional

from scion.core.models import StepRecord


@dataclass
class SaturationSignal:
    """Saturation signal for one objective dimension."""
    objective: str                    # problem-defined objective name
    improvement_ratio: float          # (initial - current) / initial, positive = improved
    saturation_level: Literal["low", "medium", "high"]
    opportunity_hint: str             # human-readable improvement hint
    at_absolute_minimum: bool = False  # baseline already at known lower bound
    saturation_type: Literal["hard", "soft", "none"] = "none"


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

    def __init__(
        self,
        baseline_metrics: Dict[str, float],
        *,
        lower_bounds: Optional[Dict[str, float]] = None,
    ) -> None:
        self._baseline = baseline_metrics
        self._lower_bounds = lower_bounds or {}

    def analyze(
        self,
        current_metrics: Dict[str, float],
    ) -> List[SaturationSignal]:
        """Compute saturation signals by comparing current champion to baseline.

        Args:
            current_metrics: Current champion metrics from the latest experiment.

        Returns:
            List of SaturationSignal, one per objective dimension.
        """
        signals = []
        _HARD_EPSILON = 0.5

        for obj, baseline_val in self._baseline.items():
            current_val = current_metrics.get(obj)
            if current_val is None or baseline_val == 0:
                continue

            # Hard saturation: baseline already at known lower bound
            lb = self._lower_bounds.get(obj)
            if lb is not None and baseline_val <= lb + _HARD_EPSILON:
                signals.append(SaturationSignal(
                    objective=obj,
                    improvement_ratio=0.0,
                    saturation_level="high",
                    opportunity_hint=f"at theoretical lower bound ({lb})",
                    at_absolute_minimum=True,
                    saturation_type="hard",
                ))
                continue

            # For minimization objectives: improvement = baseline - current.
            improvement_ratio = (baseline_val - current_val) / abs(baseline_val)
            improvement_ratio = max(0.0, min(1.0, improvement_ratio))

            if improvement_ratio > 0.70:
                level: Literal["low", "medium", "high"] = "high"
                hint = "接近局部最优"
                sat_type: Literal["hard", "soft", "none"] = "soft"
            elif improvement_ratio > 0.30:
                level = "medium"
                hint = "有一定改进空间"
                sat_type = "none"
            else:
                level = "low"
                hint = "仍有较大空间"
                sat_type = "none"

            signals.append(SaturationSignal(
                objective=obj,
                improvement_ratio=improvement_ratio,
                saturation_level=level,
                opportunity_hint=hint,
                saturation_type=sat_type,
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

    # Note objectives at absolute minimum (tendency, not prohibition)
    absolute_min_objs = [s.objective for s in signals if s.at_absolute_minimum]
    if absolute_min_objs:
        lines.append(
            f"\nNote: {', '.join(absolute_min_objs)} at theoretical lower bound. "
            f"Proposals targeting other objectives are strongly preferred."
        )

    return "\n".join(lines)


def extract_champion_metrics_from_step(step: StepRecord) -> Optional[Dict[str, float]]:
    """Extract champion-side metrics from a step's protocol result.

    Uses ObjectiveComparison.metrics when available (generic path), and can
    fall back to a generic ``case_features["champion_metrics"]`` mapping for
    compatibility fixtures that do not expose pair-level comparisons.
    Returns averages across all pairs/cases, or None if no data.
    """
    if step.protocol_result is None:
        return None

    # Method 1: from pair_feedback.objective_comparison (generic path)
    if step.protocol_result.pair_feedback:
        metric_sums: Dict[str, float] = {}
        count = 0
        for pf in step.protocol_result.pair_feedback:
            oc = getattr(pf, 'objective_comparison', None)
            if oc and hasattr(oc, 'metrics') and oc.metrics:
                for m in oc.metrics:
                    metric_sums[m.name] = metric_sums.get(m.name, 0.0) + m.champion_value
                count += 1
        if count > 0:
            return {name: total / count for name, total in metric_sums.items()}

    # Method 2: from generic case_feedback.case_features["champion_metrics"]
    if step.protocol_result.case_feedback:
        metric_sums: Dict[str, float] = {}
        count = 0
        for cf in step.protocol_result.case_feedback:
            feats = cf.case_features if hasattr(cf, "case_features") else None
            if not feats:
                continue
            champion_metrics = feats.get("champion_metrics")
            if not isinstance(champion_metrics, dict):
                continue
            included = False
            for name, value in champion_metrics.items():
                try:
                    metric_sums[str(name)] = metric_sums.get(str(name), 0.0) + float(value)
                    included = True
                except (TypeError, ValueError):
                    continue
            if included:
                count += 1
        if count > 0:
            return {name: total / count for name, total in metric_sums.items()}

    return None


def extract_candidate_metrics_from_step(step: StepRecord) -> Optional[Dict[str, float]]:
    """Extract candidate-side metrics from a step's protocol result."""
    if step.protocol_result is None:
        return None
    if not step.protocol_result.pair_feedback:
        return None

    metric_sums: Dict[str, float] = {}
    count = 0
    for pf in step.protocol_result.pair_feedback:
        oc = getattr(pf, 'objective_comparison', None)
        if oc and hasattr(oc, 'metrics') and oc.metrics:
            for m in oc.metrics:
                metric_sums[m.name] = metric_sums.get(m.name, 0.0) + m.candidate_value
            count += 1

    if count == 0:
        return None

    return {name: total / count for name, total in metric_sums.items()}
