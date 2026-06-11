"""A/A noise-floor calibration for problem-owned measurement diagnostics."""

from __future__ import annotations

import math
import random
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Iterable, Literal, Mapping, Sequence


@dataclass(frozen=True)
class AAPairRecord:
    """One champion-vs-champion calibration pair."""

    case_id: str
    seed: int
    replicate: int
    outcome: Literal["win", "loss", "tie"]
    delta: float
    raw_delta: float
    candidate_value: float | None = None
    champion_value: float | None = None


def summarize_aa_records(records: Sequence[AAPairRecord]) -> list[dict[str, Any]]:
    """Return per-case A/A noise summaries."""

    rows: list[dict[str, Any]] = []
    by_case: dict[str, list[AAPairRecord]] = defaultdict(list)
    for record in records:
        by_case[record.case_id].append(record)

    for case_id, case_records in sorted(by_case.items()):
        deltas = [record.delta for record in case_records]
        abs_deltas = [abs(value) for value in deltas]
        outcomes = Counter(record.outcome for record in case_records)
        rows.append(
            {
                "case": case_id,
                "n_pairs": len(case_records),
                "seed_var": _sample_variance(deltas),
                "pair_tie_rate": _rate(outcomes["tie"], case_records),
                "false_win_rate": _rate(outcomes["win"], case_records),
                "false_loss_rate": _rate(outcomes["loss"], case_records),
                "delta_p50_abs": _quantile(abs_deltas, 0.50),
                "delta_p90_abs": _quantile(abs_deltas, 0.90),
                "delta_max_abs": max(abs_deltas, default=0.0),
            }
        )
    return rows


def estimate_protocol_power(
    records: Sequence[AAPairRecord],
    *,
    win_rate_min: float,
    practical_delta: float,
    power_target: float = 0.80,
    n_boot: int = 400,
    seed: int = 1729,
) -> dict[str, Any]:
    """Estimate false-pass and MDE from observed A/A noise records.

    This intentionally stays problem-owned and numeric.  It does not change
    protocol gates or DecisionFeatures; it estimates whether the current
    protocol can detect a candidate effect in the declared effect units.
    """

    pairs = tuple(records)
    if not pairs:
        return {
            "false_pass_rate_at_current_gate": 0.0,
            "mde_at_power_80": None,
            "power_target": power_target,
            "power_curve": [],
            "recommended_min_seeds": 0,
            "recommended_min_effect": None,
        }

    rng = random.Random(seed)
    false_pass = _bootstrap_pass_rate(
        pairs,
        injected_effect=0.0,
        win_rate_min=win_rate_min,
        practical_delta=practical_delta,
        n_boot=n_boot,
        rng=rng,
    )
    grid = _effect_grid(pairs, practical_delta)
    curve: list[dict[str, float]] = []
    mde: float | None = None
    for effect in grid:
        power = _bootstrap_pass_rate(
            pairs,
            injected_effect=effect,
            win_rate_min=win_rate_min,
            practical_delta=practical_delta,
            n_boot=n_boot,
            rng=rng,
        )
        curve.append({"effect": effect, "power": power})
        if mde is None and power >= power_target:
            mde = effect

    distinct_seeds = {record.seed for record in pairs}
    recommended_seeds = len(distinct_seeds)
    if mde is not None and practical_delta > 0 and mde > practical_delta * 3:
        recommended_seeds = max(recommended_seeds + 1, int(math.ceil(recommended_seeds * 2)))

    return {
        "false_pass_rate_at_current_gate": false_pass,
        "mde_at_power_80": mde,
        "power_target": power_target,
        "power_curve": curve,
        "recommended_min_seeds": recommended_seeds,
        "recommended_min_effect": mde,
    }


def build_aa_noise_floor_payload(
    *,
    records: Sequence[AAPairRecord],
    problem_id: str,
    stage: str,
    metric: str,
    unit: str,
    win_rate_min: float,
    practical_delta: float,
    calibrated_at: str,
    champion_version: str = "",
    protocol_version: str = "",
    n_boot: int = 400,
) -> dict[str, Any]:
    """Return a JSON-safe A/A calibration artifact."""

    power = estimate_protocol_power(
        records,
        win_rate_min=win_rate_min,
        practical_delta=practical_delta,
        n_boot=n_boot,
    )
    return {
        "schema": "scion.aa_noise_floor.v1",
        "problem_id": problem_id,
        "stage": stage,
        "measurement_metric": metric,
        "measurement_unit": unit,
        "calibrated_at": calibrated_at,
        "champion_version": champion_version,
        "protocol_version": protocol_version,
        "n_pairs": len(records),
        "per_case": summarize_aa_records(records),
        "protocol_power": power,
        "decision_features_excluded": True,
        "policy": "problem_owned_measurement_diagnostic",
    }


def _bootstrap_pass_rate(
    records: Sequence[AAPairRecord],
    *,
    injected_effect: float,
    win_rate_min: float,
    practical_delta: float,
    n_boot: int,
    rng: random.Random,
) -> float:
    if not records or n_boot <= 0:
        return 0.0
    passes = 0
    n = len(records)
    for _ in range(n_boot):
        sample = [records[rng.randrange(n)] for _ in range(n)]
        deltas = [record.delta + injected_effect for record in sample]
        wins = sum(1 for value in deltas if value > 0)
        losses = sum(1 for value in deltas if value < 0)
        ties = n - wins - losses
        win_rate = wins / n if n else 0.0
        median_delta = statistics.median(deltas) if deltas else 0.0
        if win_rate >= win_rate_min and median_delta >= practical_delta:
            passes += 1
    return round(passes / n_boot, 4)


def _effect_grid(
    records: Sequence[AAPairRecord],
    practical_delta: float,
) -> list[float]:
    abs_noise = [abs(record.delta) for record in records]
    p90 = _quantile(abs_noise, 0.90)
    upper = max(practical_delta * 10, p90 * 6, practical_delta + p90, 1e-9)
    steps = 40
    return [round(upper * idx / steps, 8) for idx in range(steps + 1)]


def _quantile(values: Sequence[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return round(ordered[0], 8)
    position = (len(ordered) - 1) * q
    lo = int(math.floor(position))
    hi = int(math.ceil(position))
    if lo == hi:
        return round(ordered[lo], 8)
    weight = position - lo
    return round(ordered[lo] * (1 - weight) + ordered[hi] * weight, 8)


def _sample_variance(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    return round(statistics.variance(values), 8)


def _rate(count: int, values: Sequence[Any]) -> float:
    if not values:
        return 0.0
    return round(count / len(values), 4)
