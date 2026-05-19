"""Formatting helpers for proposal contexts."""
from __future__ import annotations

import json

from scion.core.models import HypothesisProposal, mechanism_change_dicts

def _format_hypothesis(hypothesis: HypothesisProposal) -> str:
    """Format hypothesis fields for Round 2 prompt."""
    lines = [
        f"hypothesis_text: {hypothesis.hypothesis_text}",
        f"change_locus: {hypothesis.change_locus}",
        f"action: {hypothesis.action}",
        f"target_file: {hypothesis.target_file or 'N/A'}",
        f"predicted_direction: {hypothesis.predicted_direction}",
        f"target_weakness: {hypothesis.target_weakness}",
        f"expected_effect: {hypothesis.expected_effect}",
    ]
    if hypothesis.target_runtime_effect:
        lines.append(f"target_runtime_effect: {hypothesis.target_runtime_effect}")
    if hypothesis.complexity_claim:
        lines.append(f"complexity_claim: {hypothesis.complexity_claim}")
    if hypothesis.runtime_budget_strategy:
        lines.append(f"runtime_budget_strategy: {hypothesis.runtime_budget_strategy}")
    if getattr(hypothesis, "mechanism_changes", None):
        lines.append(
            "mechanism_changes: "
            + json.dumps(
                mechanism_change_dicts(hypothesis),
                sort_keys=True,
                separators=(",", ":"),
            )
        )
    expected_telemetry = getattr(hypothesis, "expected_telemetry", None)
    if expected_telemetry:
        lines.append(
            "expected_telemetry: "
            + json.dumps(
                expected_telemetry,
                sort_keys=True,
                separators=(",", ":"),
            )
        )
    if hypothesis.novelty_signature:
        lines.append(
            "hypothesis_metadata_novelty_signature: "
            + json.dumps(
                hypothesis.novelty_signature,
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        lines.append(
            "novelty_signature_implementation_rule: use this only as proposal "
            "identity; do not copy novelty_signature into code or returned "
            "policy/config dictionaries unless the surface interface explicitly "
            "declares that key."
        )
    if hypothesis.suggested_weight is not None:
        lines.append(f"suggested_weight: {hypothesis.suggested_weight}")
    if hypothesis.target_objectives:
        lines.append(f"target_objectives: {', '.join(hypothesis.target_objectives)}")
    if hypothesis.protected_objectives:
        lines.append(f"protected_objectives: {', '.join(hypothesis.protected_objectives)}")
    if hypothesis.objective_tradeoff_policy:
        lines.append(f"objective_tradeoff_policy: {hypothesis.objective_tradeoff_policy}")
    if hypothesis.no_op_condition:
        lines.append(f"no_op_condition: {hypothesis.no_op_condition}")
    if hypothesis.risk_to_higher_priority:
        lines.append(f"risk_to_higher_priority: {hypothesis.risk_to_higher_priority}")
    return "\n".join(lines)
