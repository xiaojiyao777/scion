"""Structured response parsing for proposal-engine LLM outputs."""

from __future__ import annotations

from typing import Any, Dict, Sequence

from pydantic import ValidationError

from scion.core.models import (
    HypothesisProposal,
    PatchFileChange,
    PatchProposal,
)
from scion.proposal.schemas import (
    HypothesisProposalInput,
    PatchSchemaPreflightError,
    PatchProposalInput,
    preflight_patch_exact_replace_shape,
)
from scion.proposal.edit_protocol import (
    PatchEditProtocolError,
    normalize_patch_typed_edits,
)
from .exceptions import ProposalValidationError

_PATCH_TOP_LEVEL_FIELDS = frozenset(
    {
        "file_path",
        "action",
        "edit_intent",
        "old_string",
        "new_string",
        "replace_all",
        "content_after",
        "full_file_reason",
        "evidence_refs",
        "test_hint",
        "additional_changes",
    }
)
_PATCH_ADDITIONAL_CHANGE_FIELDS = frozenset(
    {
        "file_path",
        "action",
        "edit_intent",
        "old_string",
        "new_string",
        "replace_all",
        "content_after",
        "full_file_reason",
        "evidence_refs",
        "test_hint",
    }
)


def _parse_hypothesis(
    raw: Dict[str, Any],
    *,
    allowed_change_loci: Sequence[str] | None = None,
) -> HypothesisProposal:
    """Convert a validated LLM response dict into a HypothesisProposal."""
    try:
        validated = HypothesisProposalInput(**dict(raw))
    except ValidationError as exc:
        raise ProposalValidationError(str(exc)) from exc
    if (
        allowed_change_loci is not None
        and validated.change_locus not in allowed_change_loci
    ):
        raise ProposalValidationError(
            "change_locus must exactly match one provider-visible research "
            f"surface: {list(allowed_change_loci)}; got "
            f"{validated.change_locus!r}"
        )
    return HypothesisProposal(
        hypothesis_text=validated.hypothesis_text,
        change_locus=validated.change_locus,
        action=validated.action,  # type: ignore[arg-type]
        target_file=validated.target_file or None,
        predicted_direction=validated.predicted_direction,  # type: ignore[arg-type]
        target_weakness=validated.target_weakness,
        expected_effect=validated.expected_effect,
        suggested_weight=validated.suggested_weight,
    )


def _parse_patch(
    raw: Dict[str, Any],
    *,
    context: Dict[str, Any] | None = None,
) -> PatchProposal:
    """Convert a validated LLM response dict into a PatchProposal."""
    _preflight_patch_output_shape(raw)
    try:
        normalized_raw = normalize_patch_typed_edits(
            raw,
            context=context,
        )
    except PatchEditProtocolError as exc:
        raise ProposalValidationError(str(exc)) from exc
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
    )


def _preflight_patch_output_shape(raw: Dict[str, Any]) -> None:
    unknown_top = sorted(set(raw) - _PATCH_TOP_LEVEL_FIELDS)
    if unknown_top:
        raise ProposalValidationError(_unknown_patch_fields_message(unknown_top))
    additional_changes = raw.get("additional_changes")
    if isinstance(additional_changes, str) and additional_changes.strip():
        raise ProposalValidationError(
            "additional_changes must be a JSON array, not a JSON-encoded string. "
            "Emit additional_changes as an array of typed edit objects."
        )
    if isinstance(additional_changes, list):
        for index, item in enumerate(additional_changes):
            if not isinstance(item, dict):
                continue
            unknown = sorted(set(item) - _PATCH_ADDITIONAL_CHANGE_FIELDS)
            if unknown:
                raise ProposalValidationError(
                    _unknown_patch_fields_message(
                        unknown,
                        pointer=f"/additional_changes/{index}",
                    )
                )
    try:
        preflight_patch_exact_replace_shape(raw)
    except PatchSchemaPreflightError as exc:
        raise ProposalValidationError(str(exc)) from exc


def _unknown_patch_fields_message(
    fields: list[str],
    *,
    pointer: str = "/",
) -> str:
    rendered = ", ".join(fields)
    return (
        f"Unsupported patch field(s) at {pointer}: {rendered}. "
        "Do not emit ad hoc edit fields such as old_string2/new_string2. "
        "For extra file edits, put each edit object in additional_changes[]. "
        "Each file_path may appear once; express all changes to that file in "
        "one explicit typed edit."
    )
