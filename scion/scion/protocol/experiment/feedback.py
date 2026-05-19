from __future__ import annotations

import os
import statistics
from collections import defaultdict
from typing import Any, Dict, List, Sequence

from scion.core.models import (
    CaseAggregateFeedback,
    PairwiseCaseFeedback,
    ScreeningPatternSummary,
)
from .types import CaseLevelResult


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


def _aggregate_pairs_to_case_level(
    pairs: List[PairwiseCaseFeedback],
) -> List[CaseLevelResult]:
    """For each case, aggregate across seeds: majority vote → win/loss/tie, median delta.

    T2: This is the core of the case-level statistical unit change.
    """
    by_case: Dict[str, List[PairwiseCaseFeedback]] = defaultdict(list)
    for p in pairs:
        by_case[p.case_id].append(p)

    result = []
    for case_id, case_pairs in by_case.items():
        wins = sum(1 for p in case_pairs if p.comparison == "win")
        losses = sum(1 for p in case_pairs if p.comparison == "loss")
        ties = len(case_pairs) - wins - losses

        # Majority vote across seeds
        if wins > losses and wins > ties:
            majority = "win"
        elif losses > wins and losses > ties:
            majority = "loss"
        else:
            # True tie in vote count (or ties dominate)
            majority = "tie"

        med_delta = statistics.median(p.delta for p in case_pairs)
        metric_deltas: dict[str, float] = {}
        metric_values: dict[str, list[float]] = defaultdict(list)
        for p in case_pairs:
            oc = p.objective_comparison
            if oc is not None and hasattr(oc, "metrics"):
                for m in oc.metrics:
                    metric_values[m.name].append(float(m.signed_delta))
        metric_deltas = {
            name: statistics.median(vals)
            for name, vals in metric_values.items()
            if vals
        }
        result.append(CaseLevelResult(
            case_id=case_id,
            comparison=majority,
            delta=med_delta,
            metric_deltas=metric_deltas,
        ))

    return result


def _extract_case_features(case_path: str) -> dict:
    """Extract lightweight features from instance path (MVP: path-level only)."""
    stem = os.path.splitext(os.path.basename(case_path))[0]
    size_bucket = "unknown"
    for tag in ("xlarge", "large", "medium", "small"):
        if tag in stem.lower():
            size_bucket = tag
            break
    return {"path_stem": stem, "size_bucket": size_bucket}


def _aggregate_case_feedback(
    pairs: List[PairwiseCaseFeedback],
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

        # Dominant result
        mx = max(wins, losses, ties)
        if wins == losses and wins > 0:
            dominant = "mixed"
        elif mx == wins:
            dominant = "win"
        elif mx == losses:
            dominant = "loss"
        else:
            dominant = "tie"

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
        metric_deltas: dict[str, list[float]] = defaultdict(list)
        for p in case_pairs:
            oc = p.objective_comparison
            if oc and hasattr(oc, 'metrics'):
                for m in oc.metrics:
                    metric_deltas[m.name].append(m.signed_delta)
        median_deltas = {
            name: statistics.median(vals) for name, vals in metric_deltas.items() if vals
        }

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
            case_features=case_pairs[0].case_features if case_pairs else {},
        ))
    return result


def _build_pattern_summary(
    case_feedback: tuple[CaseAggregateFeedback, ...],
) -> ScreeningPatternSummary:
    """Build code-generated pattern summary from case-level feedback."""
    winning = [c for c in case_feedback if c.dominant_result == "win"]
    losing = [c for c in case_feedback if c.dominant_result == "loss"]
    mixed = [c for c in case_feedback if c.dominant_result == "mixed"]

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
]
