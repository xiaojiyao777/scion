"""Protocol screening projections used by lineage and summaries."""

from __future__ import annotations

from typing import Any, Dict

from scion.core.models import ProtocolResult

from .common import _stage_value

def _screening_pair_counts(protocol_result: ProtocolResult | None) -> Dict[str, Any]:
    if protocol_result is None or _stage_value(protocol_result.stage) != "screening":
        return {}
    wins = losses = ties = 0
    for feedback in protocol_result.pair_feedback or ():
        comparison = str(getattr(feedback, "comparison", "") or "")
        if comparison == "win":
            wins += 1
        elif comparison == "loss":
            losses += 1
        else:
            ties += 1
    total = wins + losses + ties
    return {
        "screening_pair_wins": wins,
        "screening_pair_losses": losses,
        "screening_pair_ties": ties,
        "screening_pair_total": total,
        "screening_pair_win_rate": wins / total if total else 0.0,
    }


def _screening_rate_fields(
    protocol_result: ProtocolResult | None,
) -> Dict[str, Any]:
    if protocol_result is None or _stage_value(protocol_result.stage) != "screening":
        return {}
    stats = protocol_result.stats
    wins = stats.wins
    losses = stats.losses
    ties = stats.ties
    total = wins + losses + ties
    win_rate = stats.win_rate
    return {
        "screening_case_wins": wins,
        "screening_case_losses": losses,
        "screening_case_ties": ties,
        "screening_case_total": total,
        "screening_case_win_rate": win_rate,
        **_screening_pair_counts(protocol_result),
    }
