"""Hypothesis payload extraction for CVRP mechanism novelty checks."""

from __future__ import annotations

from scion.core.models import HypothesisProposal

from scion.problems.cvrp.mechanism_novelty.text import (
    _flatten_leaf_strings,
    _normalize_text,
)


def _hypothesis_text(hypothesis: HypothesisProposal) -> str:
    parts: list[str] = [
        hypothesis.hypothesis_text,
        hypothesis.target_weakness,
        hypothesis.expected_effect,
        hypothesis.no_op_condition,
        hypothesis.risk_to_higher_priority,
        hypothesis.complexity_claim or "",
        hypothesis.runtime_budget_strategy or "",
    ]
    parts.extend(_flatten_leaf_strings(hypothesis.novelty_signature))
    return _normalize_text(" ".join(part for part in parts if part))
