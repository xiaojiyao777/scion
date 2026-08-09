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
    effect_metric: str | None = None,
) -> EvalStats:
    """Compute EvalStats from per-case comparisons and deltas.

    All declared metric rows are retained for analysis. When ``effect_metric``
    is provided, ``median_delta`` and its CI are selected from that predeclared
    problem-owned metric. Lexicographic direction remains represented by the
    case comparisons; a higher-priority nonzero row cannot shadow the declared
    practical-effect metric.
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

        metric_stats = tuple(metric_stats_list)
        normalized_effect_metric = str(effect_metric or "").strip()
        if normalized_effect_metric:
            selected = next(
                (
                    row
                    for row in metric_stats
                    if row.metric_name == normalized_effect_metric
                ),
                None,
            )
            if selected is None:
                raise ValueError(
                    "effect_metric is absent from computed metric statistics: "
                    f"{normalized_effect_metric!r}"
                )
            statistical_metric = selected.metric_name
            ci_low, ci_high = selected.ci_low, selected.ci_high
            median_delta = selected.median_delta
            statistical_status = _statistical_status(selected)

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


def _statistical_status(
    stats: MetricEvalStats,
) -> Literal["positive", "negative", "uncertain", "tie"]:
    if stats.median_delta > 0 and stats.ci_low >= 0:
        return "positive"
    if stats.median_delta < 0 and stats.ci_high <= 0:
        return "negative"
    if stats.median_delta == 0 and stats.ci_low == 0 and stats.ci_high == 0:
        return "tie"
    return "uncertain"


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
