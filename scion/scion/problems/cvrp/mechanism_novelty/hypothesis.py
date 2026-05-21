"""Hypothesis payload extraction for CVRP mechanism novelty checks."""

from __future__ import annotations

from scion.core.models import HypothesisProposal

from scion.problems.cvrp.mechanism_novelty.text import (
    _flatten_leaf_strings,
    _normalize_text,
)


def _hypothesis_text(hypothesis: HypothesisProposal) -> str:
    # Premise gates should inspect the proposed research claim, not safety
    # caveats or budgeting prose. Risk/no-op/runtime fields often mention
    # protected constraints as mitigation; treating those as positive claims
    # caused false premise contradictions in short experiments.
    parts: list[str] = [
        hypothesis.hypothesis_text,
        hypothesis.target_weakness,
        hypothesis.expected_effect,
    ]
    parts.extend(_flatten_leaf_strings(hypothesis.novelty_signature))
    for change in getattr(hypothesis, "mechanism_changes", ()) or ():
        parts.append(str(getattr(change, "id", "") or ""))
    return _normalize_text(" ".join(part for part in parts if part))
