from __future__ import annotations
import random
from typing import List, Literal, Tuple

from scion.core.models import EvalStats


def compute_eval_stats(
    comparisons: List[Literal["win", "loss", "tie"]],
    deltas: List[float],
    n_boot: int = 1000,
    alpha: float = 0.05,
) -> EvalStats:
    """Compute EvalStats from per-case comparisons and deltas."""
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

    return EvalStats(
        n_cases=n,
        wins=wins,
        losses=losses,
        ties=ties,
        win_rate=win_rate,
        median_delta=median_delta,
        ci_low=ci_low,
        ci_high=ci_high,
    )


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
