"""Minimal V3 hypothesis provider schema and prompt contract."""

from __future__ import annotations

from typing import Any, Dict, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class HypothesisProposalInput(BaseModel):
    """The one live provider-output contract for hypothesis generation."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "allOf": [
                {
                    "if": {
                        "properties": {
                            "action": {"enum": ["modify", "create_new", "remove"]},
                        },
                        "required": ["action"],
                    },
                    "then": {
                        "required": ["target_file"],
                        "properties": {
                            "target_file": {"type": "string", "minLength": 1},
                        },
                    },
                }
            ]
        },
    )

    hypothesis_text: str = Field(
        min_length=1,
        description=(
            "Explain one concrete research change, its mechanism, and why it "
            "could improve solver quality."
        ),
    )
    change_locus: str = Field(
        min_length=1,
        description="One declared research surface.",
    )
    action: Literal["modify", "create_new", "remove"]
    predicted_direction: Literal["improve", "tradeoff", "exploratory"] = Field(
        default="exploratory",
        description=(
            "Optional tainted research-intent label retained for lineage; "
            "defaults to exploratory and never drives Decision."
        ),
    )
    target_weakness: str = Field(
        min_length=1,
        description="The concrete weakness addressed by the hypothesis.",
    )
    expected_effect: str = Field(
        min_length=1,
        description="The measurable solver-quality effect expected.",
    )
    target_file: str | None = Field(
        default=None,
        description=(
            "Required for every action. This is the primary mechanism-owner "
            "anchor, not a limit on the complete patch; the code proposal may "
            "add necessary same-surface support files. For create_new, it names "
            "the new primary file."
        ),
    )
    suggested_weight: float | None = Field(
        default=None,
        description="Optional operator weight when relevant.",
    )

    @field_validator(
        "hypothesis_text",
        "change_locus",
        "target_weakness",
        "expected_effect",
    )
    @classmethod
    def must_not_be_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("field must not be empty")
        return value

    @model_validator(mode="after")
    def action_requires_target_file(self) -> "HypothesisProposalInput":
        if not (self.target_file and self.target_file.strip()):
            raise ValueError("target_file is required for every action")
        if self.target_file is not None and not self.target_file.strip():
            raise ValueError("target_file must be non-empty when provided")
        return self


HYPOTHESIS_PROPOSAL_SCHEMA: Dict[str, Any] = (
    HypothesisProposalInput.model_json_schema()
)


HYPOTHESIS_PROMPT_TEMPLATE = """\
Propose one concrete hypothesis for a declared research surface.

Return exactly one JSON object with:
- hypothesis_text
- change_locus
- action
- predicted_direction
- target_weakness
- expected_effect
- target_file naming the file bound to the subsequent code proposal
- suggested_weight only when relevant

Do not add undeclared fields.
"""


__all__ = [
    "HYPOTHESIS_PROMPT_TEMPLATE",
    "HYPOTHESIS_PROPOSAL_SCHEMA",
    "HypothesisProposalInput",
]
