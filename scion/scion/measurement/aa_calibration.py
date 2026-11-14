"""A/A noise-floor calibration for problem-owned measurement diagnostics."""

from __future__ import annotations

import math
import random
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Literal, Mapping, Sequence

_CALIBRATION_RUNNER_TIMEOUT_GRACE_SEC = 15
_RUNTIME_BUDGET_HIT_RATIO = 0.98


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
    candidate_seed: int | None = None
    resolved_case_path: str | None = None
    case_resolution: Mapping[str, Any] | None = None
    champion_elapsed_ms: int | None = None
    candidate_elapsed_ms: int | None = None
    time_limit_sec: int | None = None


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


def estimate_combined_case_rule_null(
    records: Sequence[AAPairRecord | Mapping[str, Any]],
    *,
    case_equivalence_band: float,
    rule: Mapping[str, float | int],
    n_permutations: int = 400,
    ci_bootstrap_samples: int = 400,
    seed: int = 1729,
) -> dict[str, Any]:
    """Estimate a problem-owned case rule's null pass rate by label swaps.

    Paired effects are sign-flipped, then reduced to one median per case.
    """

    if n_permutations <= 0 or ci_bootstrap_samples <= 0:
        raise ValueError("null and CI sample counts must be positive")
    if case_equivalence_band < 0:
        raise ValueError("case_equivalence_band must be non-negative")

    by_case: dict[str, list[float]] = defaultdict(list)
    for record in records:
        is_record = isinstance(record, AAPairRecord)
        case_id = record.case_id if is_record else str(record["case"])
        delta = record.delta if is_record else float(record["delta"])
        by_case[str(case_id)].append(float(delta))

    rule_fields = (
        "min_net_case_score",
        "max_case_loss_rate",
        "median_delta_min",
        "bootstrap_ci_low_min",
    )
    canonical_rule = {key: float(rule[key]) for key in rule_fields}
    observed_effects = [statistics.median(v) for _, v in sorted(by_case.items())]
    observed = _combined_case_rule_stats(
        observed_effects, case_equivalence_band, canonical_rule,
        ci_bootstrap_samples, random.Random(seed ^ 0x5C10),
    )

    rng = random.Random(seed)
    null_passes = 0
    for _ in range(n_permutations):
        null_effects = [
            statistics.median(
                delta if rng.getrandbits(1) else -delta for delta in deltas)
            for _, deltas in sorted(by_case.items())
        ]
        null_stats = _combined_case_rule_stats(
            null_effects, case_equivalence_band, canonical_rule,
            ci_bootstrap_samples, rng,
        )
        null_passes += int(null_stats["passes_rule"])

    return {
        "schema": "scion.combined_case_rule_null.v1",
        "null_method": "independent_paired_label_swap",
        "case_aggregation": "paired_effect_median",
        "case_equivalence_band": float(case_equivalence_band),
        "rng_seed": int(seed),
        "null_samples": int(n_permutations),
        "ci_bootstrap_samples": int(ci_bootstrap_samples),
        "rule": canonical_rule,
        "observed": observed,
        "null_pass_count": null_passes,
        "null_pass_rate": round(null_passes / n_permutations, 6),
        "null_pass_rate_wilson_upper_95": round(
            _wilson_upper_95(null_passes, n_permutations), 6
        ),
    }


def _combined_case_rule_stats(
    effects: Sequence[float],
    case_equivalence_band: float,
    rule: Mapping[str, float | int],
    ci_bootstrap_samples: int,
    rng: random.Random,
) -> dict[str, Any]:
    n_cases = len(effects)
    wins = sum(effect > case_equivalence_band for effect in effects)
    losses = sum(effect < -case_equivalence_band for effect in effects)
    ties = n_cases - wins - losses
    median_delta = float(statistics.median(effects)) if effects else 0.0
    ci_low = _bootstrap_median_ci_low(effects, ci_bootstrap_samples, rng)
    decisive = wins + losses
    net_score = (wins - losses) / n_cases if n_cases else 0.0
    loss_rate = losses / n_cases if n_cases else 0.0
    passes = (
        net_score >= float(rule["min_net_case_score"])
        and loss_rate <= float(rule["max_case_loss_rate"])
        and median_delta >= float(rule["median_delta_min"])
        and ci_low >= float(rule["bootstrap_ci_low_min"])
    )
    return {
        "n_cases": n_cases,
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "decisive_cases": decisive,
        "net_case_score": round(net_score, 8),
        "case_loss_rate": round(loss_rate, 8),
        "median_delta": median_delta,
        "bootstrap_ci_low": ci_low,
        "passes_rule": passes,
    }


def _bootstrap_median_ci_low(
    effects: Sequence[float], n_boot: int, rng: random.Random
) -> float:
    if not effects:
        return 0.0
    medians = sorted(
        statistics.median(rng.choices(effects, k=len(effects)))
        for _ in range(n_boot)
    )
    return float(medians[int(0.025 * n_boot)])


def _wilson_upper_95(successes: int, trials: int) -> float:
    """Return the one-sided 95% Wilson upper bound for a binomial rate."""

    if trials <= 0:
        return 0.0
    z = 1.6448536269514722
    rate = successes / trials
    z2 = z * z
    center = rate + z2 / (2 * trials)
    margin = z * math.sqrt(
        rate * (1.0 - rate) / trials + z2 / (4 * trials * trials)
    )
    return min(1.0, (center + margin) / (1.0 + z2 / trials))


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
    selected_cases: Sequence[str] = (),
    selected_seeds: Sequence[int] = (),
    replicates: int | None = None,
    seed_offset: int | None = None,
    selected_surface: str | None = None,
    runtime_policy: Mapping[str, Any] | None = None,
    safe_data_roots: Sequence[str] = (),
    combined_case_rule: Mapping[str, float | int] | None = None,
) -> dict[str, Any]:
    """Return a JSON-safe A/A calibration artifact."""

    power = estimate_protocol_power(
        records,
        win_rate_min=win_rate_min,
        practical_delta=practical_delta,
        n_boot=n_boot,
    )
    selected_cases_payload = list(selected_cases)
    selected_seeds_payload = [int(seed) for seed in selected_seeds]
    runtime_policy_payload = dict(runtime_policy or {})
    safe_data_roots_payload = [str(root) for root in safe_data_roots]
    payload = {
        "schema": "scion.aa_noise_floor.v1",
        "problem_id": problem_id,
        "stage": stage,
        "measurement_metric": metric,
        "measurement_unit": unit,
        "calibrated_at": calibrated_at,
        "champion_version": champion_version,
        "protocol_version": protocol_version,
        "n_pairs": len(records),
        "selected_cases": selected_cases_payload,
        "selected_seeds": selected_seeds_payload,
        "replicate_count": replicates,
        "seed_offset": seed_offset,
        "bootstrap_samples": n_boot,
        "selected_surface": selected_surface,
        "runtime_policy": runtime_policy_payload,
        "safe_data_roots": safe_data_roots_payload,
        "calibration_run": {
            "selected_cases": selected_cases_payload,
            "selected_seeds": selected_seeds_payload,
            "replicate_count": replicates,
            "seed_offset": seed_offset,
            "bootstrap_samples": n_boot,
            "selected_surface": selected_surface,
            "runtime_policy": runtime_policy_payload,
            "safe_data_roots": safe_data_roots_payload,
        },
        "pair_evidence": [_pair_record_payload(record) for record in records],
        "per_case": summarize_aa_records(records),
        "protocol_power": power,
        "policy": "problem_owned_measurement_diagnostic",
    }
    if combined_case_rule is not None:
        payload["combined_case_rule_null"] = estimate_combined_case_rule_null(
            records,
            case_equivalence_band=float(combined_case_rule["case_equivalence_band"]),
            rule=combined_case_rule,
            n_permutations=n_boot, ci_bootstrap_samples=n_boot,
        )
    return payload


def runtime_policy_summary(
    *,
    protocol: Any,
    stage: Any,
    cases: Sequence[str],
    fallback_time_limit_sec: int,
    selected_policy: str,
) -> dict[str, Any]:
    """Summarize uniform vs protocol-resolved runtime budgets for calibration."""

    stage_key = str(getattr(stage, "value", stage) or "").strip().lower()
    formal_config = getattr(getattr(protocol, "runtime", None), "time_limits", None)
    formal_summary = (
        formal_config.summary(
            stage=stage_key,
            cases=tuple(cases),
            fallback_time_limit_sec=fallback_time_limit_sec,
        )
        if formal_config is not None
        else {
            "stage": stage_key,
            "fallback_time_limit_sec": max(1, int(fallback_time_limit_sec)),
            "resolved_min_sec": max(1, int(fallback_time_limit_sec)),
            "resolved_max_sec": max(1, int(fallback_time_limit_sec)),
            "resolved_unique_sec": [max(1, int(fallback_time_limit_sec))],
            "rules": [],
        }
    )
    uniform_limit = max(1, int(fallback_time_limit_sec))
    if selected_policy == "protocol_time_limits":
        runner_timeout = int(formal_summary.get("resolved_max_sec") or uniform_limit)
    else:
        runner_timeout = uniform_limit
    runner_timeout = runner_timeout + _CALIBRATION_RUNNER_TIMEOUT_GRACE_SEC
    return {
        "selected_policy": selected_policy,
        "uniform_time_limit_sec": uniform_limit,
        "formal_time_limits": formal_summary,
        "runner_timeout_grace_sec": _CALIBRATION_RUNNER_TIMEOUT_GRACE_SEC,
        "runner_timeout_sec": max(1, runner_timeout),
    }


def resolve_calibration_time_limit_sec(
    *,
    protocol: Any,
    stage: Any,
    case_path: str,
    fallback_time_limit_sec: int,
    runtime_policy: str,
) -> int:
    """Resolve one calibration pair's solver budget."""

    fallback = max(1, int(fallback_time_limit_sec))
    if runtime_policy != "protocol_time_limits":
        return fallback
    config = getattr(getattr(protocol, "runtime", None), "time_limits", None)
    if config is None:
        return fallback
    stage_key = str(getattr(stage, "value", stage) or "").strip().lower()
    return config.resolve(
        stage=stage_key,
        case_path=case_path,
        fallback_time_limit_sec=fallback,
    )


def _pair_record_payload(record: AAPairRecord) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "case": record.case_id,
        "ledger_seed": int(record.seed),
        "candidate_seed": (
            int(record.candidate_seed)
            if record.candidate_seed is not None
            else int(record.seed)
        ),
        "replicate": int(record.replicate),
        "outcome": record.outcome,
        "delta": float(record.delta),
        "raw_delta": float(record.raw_delta),
        "candidate_value": record.candidate_value,
        "champion_value": record.champion_value,
        "champion_elapsed_ms": record.champion_elapsed_ms,
        "candidate_elapsed_ms": record.candidate_elapsed_ms,
    }
    if record.resolved_case_path is not None:
        payload["resolved_case_path"] = record.resolved_case_path
    if record.case_resolution is not None:
        payload["case_resolution"] = dict(record.case_resolution)
    if record.time_limit_sec is not None:
        time_limit_sec = int(record.time_limit_sec)
        payload["time_limit_sec"] = time_limit_sec
        payload["champion_runtime_budget_ratio"] = _runtime_budget_ratio(
            record.champion_elapsed_ms,
            time_limit_sec,
        )
        payload["candidate_runtime_budget_ratio"] = _runtime_budget_ratio(
            record.candidate_elapsed_ms,
            time_limit_sec,
        )
        payload["champion_runtime_budget_hit"] = _runtime_budget_hit(
            record.champion_elapsed_ms,
            time_limit_sec,
        )
        payload["candidate_runtime_budget_hit"] = _runtime_budget_hit(
            record.candidate_elapsed_ms,
            time_limit_sec,
        )
    return payload


def _runtime_budget_ratio(
    elapsed_ms: int | None,
    time_limit_sec: int,
) -> float | None:
    if elapsed_ms is None or time_limit_sec <= 0:
        return None
    return round(float(elapsed_ms) / (float(time_limit_sec) * 1000.0), 4)


def _runtime_budget_hit(
    elapsed_ms: int | None,
    time_limit_sec: int,
) -> bool | None:
    ratio = _runtime_budget_ratio(elapsed_ms, time_limit_sec)
    if ratio is None:
        return None
    return ratio >= _RUNTIME_BUDGET_HIT_RATIO


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
