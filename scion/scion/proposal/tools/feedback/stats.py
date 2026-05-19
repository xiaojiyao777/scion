"""Safe aggregate statistics for feedback payloads."""

from __future__ import annotations

from typing import Any

from scion.proposal.tools.utils import _attr


def _eval_stats_payload(stats: Any) -> dict[str, Any]:
    allowed = {
        "n_cases",
        "wins",
        "losses",
        "ties",
        "win_rate",
        "median_delta",
        "ci_low",
        "ci_high",
        "statistical_status",
        "statistical_metric",
        "runtime_ratio_median",
        "runtime_delta_median_ms",
        "runtime_regression_rate",
        "runtime_pairs",
        "total_pairs",
        "attempted_pairs",
        "valid_pairs",
        "failed_pairs",
        "candidate_failed_pairs",
        "champion_failed_pairs",
    }
    return {name: _attr(stats, name) for name in allowed if hasattr(stats, name)}
def _screening_pair_stats(protocol: Any) -> dict[str, Any]:
    pair_feedback = list(getattr(protocol, "pair_feedback", ()) or ())
    wins = sum(1 for item in pair_feedback if getattr(item, "comparison", None) == "win")
    losses = sum(
        1 for item in pair_feedback if getattr(item, "comparison", None) == "loss"
    )
    ties = len(pair_feedback) - wins - losses
    total = wins + losses + ties
    return {
        "screening_pair_wins": wins,
        "screening_pair_losses": losses,
        "screening_pair_ties": ties,
        "screening_pair_total": total,
        "screening_pair_win_rate": wins / total if total else 0.0,
    }

__all__ = [
    "_eval_stats_payload",
    "_screening_pair_stats",
]
