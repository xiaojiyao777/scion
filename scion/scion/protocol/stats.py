from __future__ import annotations
import random
from typing import Mapping, Sequence, List, Literal, Tuple

from scion.core.models import EvalStats, MetricEvalStats


def compute_eval_stats(
    comparisons: List[Literal["win", "loss", "tie"]],
    deltas: List[float],
    n_boot: int = 1000,
    alpha: float = 0.05,
    *,
    metric_deltas: Sequence[Mapping[str, float]] | None = None,
    metric_order: Sequence[str] | None = None,
) -> EvalStats:
    """Compute EvalStats from per-case comparisons and deltas.

    When ``metric_deltas`` and ``metric_order`` are provided, ``ci_low`` /
    ``ci_high`` become the priority-aware hierarchical CI used by promotion
    gates. Legacy callers without metric details keep the old scalar-delta CI.
    """
    n = len(comparisons)
    wins = comparisons.count("win")
    losses = comparisons.count("loss")
    ties = comparisons.count("tie")
    win_rate = wins / n if n > 0 else 0.0

    if deltas:
        sorted_d = sorted(deltas)
        mid = len(sorted_d) // 2
        if len(sorted_d) % 2 == 0:
            median_delta = (sorted_d[mid - 1] + sorted_d[mid]) / 2.0
        else:
            median_delta = sorted_d[mid]
    else:
        median_delta = 0.0

    ci_low, ci_high = bootstrap_ci(deltas, n_boot=n_boot, alpha=alpha)
    statistical_status = None
    statistical_metric = None
    metric_stats: tuple[MetricEvalStats, ...] = ()

    if metric_deltas is not None and metric_order:
        metric_stats_list: list[MetricEvalStats] = []
        selected: MetricEvalStats | None = None
        selected_status: Literal["positive", "negative", "uncertain", "tie"] = "tie"

        for metric_name in metric_order:
            vals = [
                float(row[metric_name])
                for row in metric_deltas
                if metric_name in row
            ]
            if not vals:
                continue
            med = _median(vals)
            lo, hi = bootstrap_ci(vals, n_boot=n_boot, alpha=alpha)
            row = MetricEvalStats(
                metric_name=metric_name,
                median_delta=med,
                ci_low=lo,
                ci_high=hi,
                n_cases=len(vals),
            )
            metric_stats_list.append(row)

            if lo > 0:
                selected = row
                selected_status = "positive"
                break
            if hi < 0:
                selected = row
                selected_status = "negative"
                break
            if lo == 0 and hi == 0 and med == 0:
                # Exact tie on this priority level; continue to the next metric.
                continue
            selected = row
            selected_status = "uncertain"
            break

        metric_stats = tuple(metric_stats_list)
        if selected is None:
            statistical_status = "tie"
            statistical_metric = metric_stats[-1].metric_name if metric_stats else None
            ci_low, ci_high = 0.0, 0.0
            median_delta = 0.0
        else:
            statistical_status = selected_status
            statistical_metric = selected.metric_name
            ci_low, ci_high = selected.ci_low, selected.ci_high
            median_delta = selected.median_delta

    return EvalStats(
        n_cases=n,
        wins=wins,
        losses=losses,
        ties=ties,
        win_rate=win_rate,
        median_delta=median_delta,
        ci_low=ci_low,
        ci_high=ci_high,
        statistical_status=statistical_status,
        statistical_metric=statistical_metric,
        metric_stats=metric_stats,
    )


def _median(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    sorted_d = sorted(values)
    mid = len(sorted_d) // 2
    if len(sorted_d) % 2 == 0:
        return (sorted_d[mid - 1] + sorted_d[mid]) / 2.0
    return sorted_d[mid]


def bootstrap_ci(
    deltas: List[float],
    n_boot: int = 1000,
    alpha: float = 0.05,
    seed: int = 42,
) -> Tuple[float, float]:
    """Bootstrap confidence interval for the median delta."""
    if not deltas:
        return (0.0, 0.0)

    rng = random.Random(seed)
    n = len(deltas)
    boot_medians: List[float] = []

    for _ in range(n_boot):
        sample = [rng.choice(deltas) for _ in range(n)]
        sample.sort()
        mid = n // 2
        if n % 2 == 0:
            m = (sample[mid - 1] + sample[mid]) / 2.0
        else:
            m = sample[mid]
        boot_medians.append(m)

    boot_medians.sort()
    lo_idx = int(alpha / 2 * n_boot)
    hi_idx = int((1.0 - alpha / 2) * n_boot) - 1
    ci_low = boot_medians[max(0, lo_idx)]
    ci_high = boot_medians[min(len(boot_medians) - 1, hi_idx)]
    return (ci_low, ci_high)
