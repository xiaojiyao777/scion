"""Hypothesis target-intent preflight schema."""

from __future__ import annotations

from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class HypothesisTargetIntentInput(BaseModel):
    """Tainted, audit-only intent selected before final hypothesis generation."""

    model_config = ConfigDict(extra="forbid")

    change_locus: str = ""
    surface: Optional[str] = None
    action: Literal["modify", "create_new", "create", "remove"]
    target_file: Optional[str] = None
    mechanism_id: Optional[str] = None
    mechanism_family: Optional[str] = None
    mechanism_sketch: str = ""
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    notes: str = ""

    @field_validator("change_locus", "surface", "target_file", mode="before")
    @classmethod
    def normalize_optional_strings(cls, value: Any) -> Any:
        if value is None:
            return value
        return str(value).strip()

    @model_validator(mode="after")
    def validate_minimum_intent(self) -> "HypothesisTargetIntentInput":
        if not (self.change_locus or self.surface):
            raise ValueError("change_locus or surface is required")
        if not (self.target_file or "").strip():
            raise ValueError("target_file is required for target-intent preflight")
        if not (
            (self.mechanism_id or "").strip()
            or (self.mechanism_family or "").strip()
            or (self.mechanism_sketch or "").strip()
        ):
            raise ValueError(
                "mechanism_id, mechanism_family, or mechanism_sketch is required"
            )
        return self


HYPOTHESIS_TARGET_INTENT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": ["action", "target_file"],
    "additionalProperties": False,
    "properties": {
        "change_locus": {
            "type": "string",
            "description": "Declared research surface id/name for the likely final hypothesis.",
        },
        "surface": {
            "type": ["string", "null"],
            "description": "Alias for change_locus when the surrounding protocol uses surface wording.",
        },
        "action": {
            "type": "string",
            "enum": ["modify", "create_new", "create", "remove"],
            "description": (
                "Likely target action. Use modify/remove for existing targets; "
                "use create_new for a new target file. create is accepted as an alias."
            ),
        },
        "target_file": {
            "type": "string",
            "description": "Relative target path for the likely final hypothesis.",
        },
        "mechanism_id": {
            "type": ["string", "null"],
            "description": (
                "Compact candidate mechanism id if known. Prefer lowercase "
                "formal-safe ids matching ^[a-z][a-z0-9_]{0,63}$; host "
                "normalization preserves any nonconforming raw id as audit "
                "provenance and exposes a canonical formal id later."
            ),
        },
        "mechanism_family": {
            "type": ["string", "null"],
            "description": "Compact mechanism family when a precise id is premature.",
        },
        "mechanism_sketch": {
            "type": "string",
            "description": (
                "One or two sentences sketching the intended mechanism. Do not "
                "write the final hypothesis text here."
            ),
        },
        "confidence": {
            "type": ["number", "null"],
            "minimum": 0.0,
            "maximum": 1.0,
            "description": "Self-reported confidence that this is the right target.",
        },
        "notes": {
            "type": "string",
            "description": "Short audit note. This is tainted proposal context only.",
        },
    },
}


__all__ = [
    "HYPOTHESIS_TARGET_INTENT_SCHEMA",
    "HypothesisTargetIntentInput",
]
