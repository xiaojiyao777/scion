from __future__ import annotations

import os
import re
import statistics
from collections import defaultdict
from collections.abc import Sequence
from typing import Any, Dict, List, Literal

from scion.core.models import (
    CaseAggregateFeedback,
    PairwiseCaseFeedback,
    ScreeningPatternSummary,
)

from .types import CaseLevelResult


_CVRPLIB_DIMENSION_RE = re.compile(r"(?:^|-)n(?P<dimension>\d+)(?:-|$)", re.I)


def _pair_feedback_counts(pairs: Sequence[PairwiseCaseFeedback]) -> dict[str, Any]:
    wins = sum(1 for pair in pairs if pair.comparison == "win")
    losses = sum(1 for pair in pairs if pair.comparison == "loss")
    ties = len(pairs) - wins - losses
    total = wins + losses + ties
    return {
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "total": total,
        "win_rate": wins / total if total else 0.0,
    }


def _protected_objective_regressions(
    pairs: Sequence[PairwiseCaseFeedback],
    protected_objectives: Sequence[str],
) -> tuple[str, ...]:
    """Return declared protected metrics worsened on any complete A/B pair."""

    protected = {
        str(name).strip()
        for name in protected_objectives
        if str(name).strip()
    }
    regressions: set[str] = set()
    if not protected:
        return ()
    for pair in pairs:
        comparison = pair.objective_comparison
        for metric in getattr(comparison, "metrics", ()) or ():
            name = str(getattr(metric, "name", "") or "").strip()
            if name in protected and getattr(metric, "relation", None) == "champion":
                regressions.add(name)
    return tuple(sorted(regressions))


def _aggregate_pairs_to_case_level(
    pairs: List[PairwiseCaseFeedback],
    *,
    aggregation: Literal[
        "seed_vote_majority",
        "paired_effect_median",
    ] = "seed_vote_majority",
    effect_metric: str = "",
    equivalence_band: float = 0.0,
) -> List[CaseLevelResult]:
    """Reduce each case's paired seeds using the preregistered method.

    T2: This is the core of the case-level statistical unit change.
    """
    by_case: Dict[str, List[PairwiseCaseFeedback]] = defaultdict(list)
    for p in pairs:
        by_case[p.case_id].append(p)

    result = []
    for case_id, case_pairs in by_case.items():
        comparison, med_delta = _case_direction_and_delta(
            case_pairs,
            aggregation=aggregation,
            effect_metric=effect_metric,
            equivalence_band=equivalence_band,
        )
        metric_deltas = _median_metric_deltas(case_pairs)
        if (
            aggregation == "paired_effect_median"
            and effect_metric
            and any(_is_typed_candidate_failure(pair) for pair in case_pairs)
        ):
            # Keep the same conservative typed loss in the declared effect row
            # so downstream statistics remain complete and auditable.
            metric_deltas[effect_metric] = med_delta
        result.append(CaseLevelResult(
            case_id=case_id,
            comparison=comparison,
            delta=med_delta,
            metric_deltas=metric_deltas,
        ))

    return result


def _case_direction_and_delta(
    case_pairs: Sequence[PairwiseCaseFeedback],
    *,
    aggregation: str,
    effect_metric: str,
    equivalence_band: float,
) -> tuple[Literal["win", "loss", "tie"], float]:
    """Return one auditable direction and delta for a complete case row."""

    if not case_pairs:
        raise ValueError("case aggregation requires at least one paired result")
    if aggregation == "seed_vote_majority":
        wins = sum(1 for pair in case_pairs if pair.comparison == "win")
        losses = sum(1 for pair in case_pairs if pair.comparison == "loss")
        ties = len(case_pairs) - wins - losses
        if wins > losses and wins > ties:
            direction: Literal["win", "loss", "tie"] = "win"
        elif losses > wins and losses > ties:
            direction = "loss"
        else:
            direction = "tie"
        return direction, float(statistics.median(pair.delta for pair in case_pairs))

    if aggregation != "paired_effect_median":
        raise ValueError(f"unknown case aggregation method: {aggregation!r}")

    metric = str(effect_metric or "").strip()
    if not metric:
        raise ValueError("paired_effect_median requires a declared effect_metric")

    # Candidate process/audit failures are already typed as conservative pair
    # losses by the Protocol runner and have no objective vector.  They must not
    # turn a measured rejection into an aggregation exception.  Other missing
    # objective evidence remains invalid rather than being guessed.
    missing_objective = [
        pair for pair in case_pairs if pair.objective_comparison is None
    ]
    if missing_objective:
        if all(_is_typed_candidate_failure(pair) for pair in missing_objective):
            return "loss", -1.0
        first = missing_objective[0]
        raise ValueError(
            "paired_effect_median effect evidence is absent from paired "
            f"objective evidence: case={first.case_id!r}, seed={first.seed}"
        )

    effect_deltas = [
        _declared_effect_delta(pair, effect_metric=metric)
        for pair in case_pairs
    ]
    median_effect = float(statistics.median(effect_deltas))
    band = float(equivalence_band)
    if band < 0.0:
        raise ValueError("case equivalence band must be non-negative")
    if median_effect > band:
        direction = "win"
    elif median_effect < -band:
        direction = "loss"
    else:
        direction = "tie"

    return direction, median_effect


def _is_typed_candidate_failure(pair: PairwiseCaseFeedback) -> bool:
    return (
        pair.objective_comparison is None
        and pair.comparison == "loss"
        and float(pair.delta) == -1.0
    )


def _declared_effect_delta(
    pair: PairwiseCaseFeedback,
    *,
    effect_metric: str,
) -> float:
    if effect_metric == "weighted_sum":
        return float(pair.delta)
    comparison = pair.objective_comparison
    for metric in getattr(comparison, "metrics", ()) or ():
        if str(getattr(metric, "name", "") or "") == effect_metric:
            return float(metric.signed_delta)
    raise ValueError(
        "paired_effect_median effect_metric is absent from paired objective "
        f"evidence: metric={effect_metric!r}, case={pair.case_id!r}, seed={pair.seed}"
    )


def _median_metric_deltas(
    case_pairs: Sequence[PairwiseCaseFeedback],
) -> dict[str, float]:
    metric_values: dict[str, list[float]] = defaultdict(list)
    for pair in case_pairs:
        comparison = pair.objective_comparison
        for metric in getattr(comparison, "metrics", ()) or ():
            metric_values[metric.name].append(float(metric.signed_delta))
    return {
        name: float(statistics.median(values))
        for name, values in metric_values.items()
        if values
    }


def _extract_case_features(case_path: str) -> dict:
    """Extract observational path facts for proposal feedback."""
    stem = os.path.splitext(os.path.basename(case_path))[0]
    size_bucket = "unknown"
    for tag in ("xlarge", "large", "medium", "small"):
        if tag in stem.lower():
            size_bucket = tag
            break
    features: dict[str, Any] = {"path_stem": stem, "size_bucket": size_bucket}
    dimension_match = _CVRPLIB_DIMENSION_RE.search(stem)
    if dimension_match is not None:
        dimension = int(dimension_match.group("dimension"))
        features["dimension"] = dimension
        if dimension <= 100:
            features["size_bucket"] = "n_le_100"
        elif dimension <= 149:
            features["size_bucket"] = "n_101_149"
        elif dimension <= 250:
            features["size_bucket"] = "n_150_250"
        else:
            features["size_bucket"] = "n_ge_251"
    return features


def _aggregate_case_feedback(
    pairs: List[PairwiseCaseFeedback],
    *,
    aggregation: Literal[
        "seed_vote_majority",
        "paired_effect_median",
    ] = "seed_vote_majority",
    effect_metric: str = "",
    equivalence_band: float = 0.0,
) -> List[CaseAggregateFeedback]:
    """Group pair feedback by case_id and compute per-case aggregates."""
    by_case: dict[str, list[PairwiseCaseFeedback]] = defaultdict(list)
    for p in pairs:
        by_case[p.case_id].append(p)

    result = []
    for case_id, case_pairs in by_case.items():
        n = len(case_pairs)
        wins = sum(1 for p in case_pairs if p.comparison == "win")
        losses = sum(1 for p in case_pairs if p.comparison == "loss")
        ties = n - wins - losses
        wr = wins / n if n > 0 else 0.0

        mx = max(wins, losses, ties)
        dominant, _ = _case_direction_and_delta(
            case_pairs,
            aggregation=aggregation,
            effect_metric=effect_metric,
            equivalence_band=equivalence_band,
        )
        nonzero_outcomes = sum(count > 0 for count in (wins, losses, ties))
        seed_pattern: Literal["uniform", "heterogeneous"] = (
            "heterogeneous" if nonzero_outcomes > 1 else "uniform"
        )

        # Dominant decisive metric (generic)
        decisive_counts: dict[str, int] = defaultdict(int)
        for p in case_pairs:
            oc = p.objective_comparison
            dm = (oc.decisive_metric if oc and hasattr(oc, 'decisive_metric') else None) or "tie"
            decisive_counts[dm] += 1
        dominant_decisive = max(decisive_counts, key=decisive_counts.get)  # type: ignore
        if len(set(decisive_counts.values())) == 1 and len(decisive_counts) > 1:
            dominant_decisive = "mixed"

        # Median deltas per metric (generic)
        median_deltas = _median_metric_deltas(case_pairs)

        result.append(CaseAggregateFeedback(
            case_id=case_id,
            n_pairs=n,
            wins=wins,
            losses=losses,
            ties=ties,
            win_rate=wr,
            dominant_result=dominant,
            decisive_metric=dominant_decisive,
            median_deltas=median_deltas,
            seed_consistency=mx / n if n > 0 else 0.0,
            seed_pattern=seed_pattern,
            case_features=case_pairs[0].case_features if case_pairs else {},
        ))
    return result


def _build_pattern_summary(
    case_feedback: tuple[CaseAggregateFeedback, ...],
) -> ScreeningPatternSummary:
    """Build code-generated pattern summary from case-level feedback."""
    winning = [c for c in case_feedback if c.dominant_result == "win"]
    losing = [c for c in case_feedback if c.dominant_result == "loss"]
    mixed = [
        c
        for c in case_feedback
        if c.seed_pattern == "heterogeneous"
        or c.dominant_result == "mixed"
        or sum(count > 0 for count in (c.wins, c.losses, c.ties)) > 1
    ]

    wins_by_obj: dict[str, int] = defaultdict(int)
    losses_by_obj: dict[str, int] = defaultdict(int)
    wins_by_size: dict[str, int] = defaultdict(int)
    losses_by_size: dict[str, int] = defaultdict(int)

    for c in winning:
        wins_by_obj[c.decisive_metric] += 1
        wins_by_size[c.case_features.get("size_bucket", "unknown")] += 1
    for c in losing:
        losses_by_obj[c.decisive_metric] += 1
        losses_by_size[c.case_features.get("size_bucket", "unknown")] += 1

    # Generate key observations (rule-based, generic metric names)
    observations: list[str] = []
    for metric, count in losses_by_obj.items():
        if count >= 2 and metric != "tie":
            observations.append(
                f"Most losses decided by {metric}: candidate often worsened this objective."
            )

    # Size pattern
    win_sizes = set(wins_by_size.keys())
    loss_sizes = set(losses_by_size.keys())
    if win_sizes and loss_sizes and not win_sizes.intersection(loss_sizes):
        observations.append(
            f"Candidate wins on {', '.join(sorted(win_sizes))} but loses on {', '.join(sorted(loss_sizes))}."
        )

    if mixed:
        observations.append(
            f"{len(mixed)} case(s) showed seed-sensitive behavior; treat gains there as unstable."
        )

    consistent_wins = tuple(c.case_id for c in winning if c.seed_consistency >= 0.99)
    consistent_losses = tuple(c.case_id for c in losing if c.seed_consistency >= 0.99)
    if consistent_wins:
        observations.append(f"Consistent wins: {', '.join(consistent_wins)}.")
    if consistent_losses:
        observations.append(f"Consistent losses: {', '.join(consistent_losses)}.")

    return ScreeningPatternSummary(
        total_cases=len(case_feedback),
        winning_cases=len(winning),
        losing_cases=len(losing),
        mixed_cases=len(mixed),
        wins_by_decisive_objective=dict(wins_by_obj),
        losses_by_decisive_objective=dict(losses_by_obj),
        wins_by_size_bucket=dict(wins_by_size),
        losses_by_size_bucket=dict(losses_by_size),
        consistent_win_cases=consistent_wins,
        consistent_loss_cases=consistent_losses,
        key_observations=tuple(observations),
    )


__all__ = [
    "_aggregate_case_feedback",
    "_aggregate_pairs_to_case_level",
    "_build_pattern_summary",
    "_extract_case_features",
    "_pair_feedback_counts",
    "_protected_objective_regressions",
]
