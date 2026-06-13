"""Proposal-visible context ablation modes.

These modes control only what the tainted proposal prompt can see.  They do not
change protocol measurement governance, evaluation, DecisionFeatures, or
promotion semantics.
"""

from __future__ import annotations

from typing import Any, Literal

ProposalContextAblation = Literal[
    "full",
    "compact-measurement-diagnostics",
    "no-measurement-diagnostics",
    "minimal-research-context",
]

_VALID_MODES = {
    "full",
    "compact-measurement-diagnostics",
    "no-measurement-diagnostics",
    "minimal-research-context",
}

_ALIASES = {
    "none": "full",
    "off": "full",
    "default": "full",
    "compact_measurement_diagnostics": "compact-measurement-diagnostics",
    "measurement_diagnostics_compact": "compact-measurement-diagnostics",
    "measurement-diagnostics-compact": "compact-measurement-diagnostics",
    "no_measurement_diagnostics": "no-measurement-diagnostics",
    "measurement_diagnostics_off": "no-measurement-diagnostics",
    "measurement-diagnostics-off": "no-measurement-diagnostics",
    "minimal_research_context": "minimal-research-context",
    "research_context_off": "minimal-research-context",
    "research-context-off": "minimal-research-context",
}


def normalize_proposal_context_ablation(
    value: Any | None,
) -> ProposalContextAblation:
    text = "full" if value is None else str(value).strip().lower()
    text = _ALIASES.get(text, text)
    if text not in _VALID_MODES:
        raise ValueError(
            "proposal_context_ablation must be one of: "
            "full, compact-measurement-diagnostics, "
            "no-measurement-diagnostics, minimal-research-context"
        )
    return text  # type: ignore[return-value]


__all__ = [
    "ProposalContextAblation",
    "normalize_proposal_context_ablation",
]
