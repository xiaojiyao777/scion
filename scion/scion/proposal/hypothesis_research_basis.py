"""Validated tainted basis returned by bounded hypothesis research."""

from __future__ import annotations

from collections.abc import Collection, Mapping
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from scion.core.models import HypothesisProposal
from scion.proposal.bounded_research import nonempty_text, require_exact_keys
from scion.proposal.engine.exceptions import ProposalValidationError

MAX_HYPOTHESIS_RESEARCH_REF_CHARS = 64
_MAX_TEXT_CHARS = 4000
_MAX_REFS = 64
_MAX_ALTERNATIVES = 8


@dataclass(frozen=True)
class HypothesisResearchBasis:
    """Creative evidence basis; never a Protocol or Decision input."""

    read_refs: tuple[str, ...]
    nearest_prior_refs: tuple[str, ...]
    material_delta: str
    alternatives_considered: tuple[str, ...]
    observable_prediction: str


@dataclass(frozen=True)
class HypothesisResearchFinalized:
    hypothesis: HypothesisProposal
    research_basis: HypothesisResearchBasis


def hypothesis_research_basis_schema(
    *,
    visible_refs: Collection[str] | None = None,
    visible_history_refs: Collection[str] | None = None,
) -> dict[str, Any]:
    """Return a basis schema bound to evidence revealed in this H session."""

    if visible_refs is not None and not visible_refs:
        raise ValueError(
            "a dynamic research_basis schema requires at least one visible ref"
        )

    def ref_array(
        visible: Collection[str] | None,
        *,
        description: str,
    ) -> dict[str, Any]:
        allowed = None if visible is None else sorted(set(visible))
        items: dict[str, Any] = {
            "type": "string",
            "minLength": 1,
            "maxLength": MAX_HYPOTHESIS_RESEARCH_REF_CHARS,
        }
        if allowed:
            items["enum"] = allowed
        return {
            "type": "array",
            "description": description,
            "items": items,
            "uniqueItems": True,
            "maxItems": _MAX_REFS if allowed is None else min(_MAX_REFS, len(allowed)),
        }

    read_ref_array = ref_array(
        visible_refs,
        description=(
            "Refs revealed by successful read_source or read_history actions in "
            "this session. Use only this turn's enumerated refs."
        ),
    )
    nearest_ref_array = ref_array(
        visible_history_refs,
        description=(
            "Nearest prior refs must come only from successful read_history "
            "actions in this session and must also appear in read_refs. Use [] "
            "when no history ref is enumerated."
        ),
    )
    text = {"type": "string", "minLength": 1, "maxLength": _MAX_TEXT_CHARS}
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "read_refs",
            "nearest_prior_refs",
            "material_delta",
            "alternatives_considered",
            "observable_prediction",
        ],
        "properties": {
            "read_refs": {**read_ref_array, "minItems": 1},
            "nearest_prior_refs": nearest_ref_array,
            "material_delta": deepcopy(text),
            "alternatives_considered": {
                "type": "array",
                "items": deepcopy(text),
                "minItems": 1,
                "maxItems": _MAX_ALTERNATIVES,
            },
            "observable_prediction": deepcopy(text),
        },
    }


def parse_hypothesis_research_basis(
    raw: Mapping[str, Any],
    *,
    visible_refs: set[str],
    visible_history_refs: set[str],
) -> HypothesisResearchBasis:
    fields = {
        "read_refs",
        "nearest_prior_refs",
        "material_delta",
        "alternatives_considered",
        "observable_prediction",
    }
    require_exact_keys(raw, fields, label="research_basis")
    read_refs = _ref_list(raw["read_refs"], field="read_refs", require_one=True)
    nearest = _ref_list(raw["nearest_prior_refs"], field="nearest_prior_refs")
    if not set(read_refs) <= visible_refs:
        raise ProposalValidationError(
            "research_basis read_refs must reference sources or histories read "
            "in this session"
        )
    if not set(nearest) <= visible_history_refs or not set(nearest) <= set(read_refs):
        raise ProposalValidationError(
            "research_basis nearest_prior_refs must reference histories read "
            "and cited by this session"
        )
    alternatives = raw["alternatives_considered"]
    if (
        not isinstance(alternatives, list)
        or not 1 <= len(alternatives) <= _MAX_ALTERNATIVES
    ):
        raise ProposalValidationError(
            "research_basis alternatives_considered must be a bounded nonempty array"
        )
    return HypothesisResearchBasis(
        read_refs=read_refs,
        nearest_prior_refs=nearest,
        material_delta=nonempty_text(
            raw["material_delta"], field="material_delta", maximum=_MAX_TEXT_CHARS
        ),
        alternatives_considered=tuple(
            nonempty_text(
                item,
                field="alternatives_considered item",
                maximum=_MAX_TEXT_CHARS,
            )
            for item in alternatives
        ),
        observable_prediction=nonempty_text(
            raw["observable_prediction"],
            field="observable_prediction",
            maximum=_MAX_TEXT_CHARS,
        ),
    )


def _ref_list(value: Any, *, field: str, require_one: bool = False) -> tuple[str, ...]:
    if not isinstance(value, list) or len(value) > _MAX_REFS:
        raise ProposalValidationError(f"research_basis {field} must be a bounded array")
    refs = tuple(
        nonempty_text(
            item,
            field=f"{field} item",
            maximum=MAX_HYPOTHESIS_RESEARCH_REF_CHARS,
        )
        for item in value
    )
    if (require_one and not refs) or len(refs) != len(set(refs)):
        raise ProposalValidationError(
            f"research_basis {field} must contain unique visible refs"
        )
    return refs


__all__ = [
    "MAX_HYPOTHESIS_RESEARCH_REF_CHARS",
    "HypothesisResearchBasis",
    "HypothesisResearchFinalized",
    "hypothesis_research_basis_schema",
    "parse_hypothesis_research_basis",
]
