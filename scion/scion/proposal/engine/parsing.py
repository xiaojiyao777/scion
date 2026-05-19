"""Structured response parsing for proposal-engine LLM outputs."""

from __future__ import annotations

from typing import Any, Dict

from pydantic import ValidationError

from scion.core.models import (
    HypothesisProposal,
    MechanismChange,
    PatchFileChange,
    PatchProposal,
)
from scion.proposal.schemas import (
    HypothesisProposalInput,
    PatchProposalInput,
    normalize_patch_output_with_repair_attribution,
)

from .exceptions import ProposalValidationError


def _parse_hypothesis(raw: Dict[str, Any]) -> HypothesisProposal:
    """Convert a validated LLM response dict into a HypothesisProposal."""
    try:
        validated = HypothesisProposalInput(**raw)
    except ValidationError as exc:
        raise ProposalValidationError(str(exc)) from exc
    return HypothesisProposal(
        hypothesis_text=validated.hypothesis_text,
        change_locus=validated.change_locus,
        action=validated.action,  # type: ignore[arg-type]
        target_file=validated.target_file or None,
        predicted_direction=validated.predicted_direction,  # type: ignore[arg-type]
        target_weakness=validated.target_weakness,
        expected_effect=validated.expected_effect,
        suggested_weight=validated.suggested_weight,
        target_objectives=tuple(validated.target_objectives or ()),
        protected_objectives=tuple(validated.protected_objectives or ()),
        objective_tradeoff_policy=validated.objective_tradeoff_policy,
        no_op_condition=validated.no_op_condition,
        risk_to_higher_priority=validated.risk_to_higher_priority,
        target_runtime_effect=validated.target_runtime_effect,
        complexity_claim=validated.complexity_claim,
        runtime_budget_strategy=validated.runtime_budget_strategy,
        expected_telemetry=dict(validated.expected_telemetry or {}),
        novelty_signature=dict(validated.novelty_signature or {}),
        mechanism_changes=tuple(
            MechanismChange(id=change.id, change_type=change.change_type)
            for change in validated.mechanism_changes
        ),
    )


def _parse_patch(raw: Dict[str, Any]) -> PatchProposal:
    """Convert a validated LLM response dict into a PatchProposal."""
    normalized_raw, repair_attribution = normalize_patch_output_with_repair_attribution(
        raw
    )
    try:
        validated = PatchProposalInput(**normalized_raw)
    except ValidationError as exc:
        raise ProposalValidationError(str(exc)) from exc
    return PatchProposal(
        file_path=validated.file_path,
        action=validated.action,  # type: ignore[arg-type]
        code_content=validated.code_content,
        test_hint=validated.test_hint or None,
        additional_changes=tuple(
            PatchFileChange(
                file_path=change.file_path,
                action=change.action,  # type: ignore[arg-type]
                code_content=change.code_content,
                test_hint=change.test_hint or None,
            )
            for change in validated.additional_changes
        ),
        premise_check=validated.premise_check,
        premise_check_reason=validated.premise_check_reason,
        repair_attribution=repair_attribution,
        mechanism_changes=tuple(
            MechanismChange(id=change.id, change_type=change.change_type)
            for change in validated.mechanism_changes
        ),
    )


def _to_float_or_none(v: Any) -> "float | None":
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
