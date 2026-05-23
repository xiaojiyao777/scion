"""Shared schema helpers for proposal structured outputs."""

from __future__ import annotations

import re
from typing import Any, Dict, Literal

from pydantic import BaseModel, ConfigDict, field_validator

_MECHANISM_ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_MECHANISM_CHANGE_TYPES = ("add", "modify", "replace", "remove", "integrate")
_EXPECTED_TELEMETRY_CATEGORIES = ("activity", "activation", "effect", "budget")
_EXPECTED_TELEMETRY_CATEGORY_TEXT = ", ".join(_EXPECTED_TELEMETRY_CATEGORIES)
_EXPECTED_TELEMETRY_DESCRIPTION = (
    "Structured runtime telemetry probes expected to show candidate activity, "
    "activation, effect, or budget allocation. Top-level keys must be telemetry "
    f"categories only: {_EXPECTED_TELEMETRY_CATEGORY_TEXT}. Values must be "
    "exact runtime telemetry field strings declared by the selected research "
    "surface evidence contract; do not put explanatory prose in these values. "
    "Use JSON arrays of field strings, or mechanism-keyed maps whose values "
    "are still field strings/arrays. Do not use runtime field names, suffixes, "
    "or metrics such as best_delta, improvement_counts, phase_runtime, or "
    "runtime_ms as top-level categories; put those declared runtime fields "
    "under the matching category instead. Activation must be mechanism-specific "
    "activity evidence, not objective/outcome fields. Aggregate outcome or "
    "activity fields show effect or activity, not activation. For mapping "
    "telemetry, use a mechanism-specific path containing the declared "
    "mechanism id; the whole map field alone is not activation evidence. If a "
    "proposal modifies an existing phase or component, name the modified lever "
    "as a mechanism id in mechanism_changes and use that same id in "
    "expected_telemetry paths."
)

MechanismChangeType = Literal["add", "modify", "replace", "remove", "integrate"]


class MechanismChangeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    change_type: MechanismChangeType

    @field_validator("id")
    @classmethod
    def valid_mechanism_id(cls, value: str) -> str:
        mechanism_id = str(value or "").strip()
        if not _MECHANISM_ID_RE.fullmatch(mechanism_id):
            raise ValueError(
                "mechanism id must match ^[a-z][a-z0-9_]{0,63}$"
            )
        return mechanism_id


def _mechanism_changes_json_schema() -> Dict[str, Any]:
    return {
        "type": "array",
        "description": (
            "Problem-neutral mechanism bindings touched by this proposal. "
            "Use stable lowercase ids matching ^[a-z][a-z0-9_]{0,63}$ and "
            "generic change_type values."
        ),
        "items": {
            "type": "object",
            "required": ["id", "change_type"],
            "properties": {
                "id": {
                    "type": "string",
                    "pattern": r"^[a-z][a-z0-9_]{0,63}$",
                },
                "change_type": {
                    "type": "string",
                    "enum": list(_MECHANISM_CHANGE_TYPES),
                },
            },
            "additionalProperties": False,
        },
    }


def _empty_mechanism_changes_to_list(value: Any) -> Any:
    return [] if value in (None, "") else value


def _validate_unique_mechanism_change_ids(
    changes: list[MechanismChangeInput],
) -> None:
    ids = [change.id for change in changes]
    duplicates = sorted(
        {mechanism_id for mechanism_id in ids if ids.count(mechanism_id) > 1}
    )
    if duplicates:
        raise ValueError(
            "mechanism_changes must not repeat id values: " + ", ".join(duplicates)
        )


__all__ = [
    "MechanismChangeInput",
    "MechanismChangeType",
    "_EXPECTED_TELEMETRY_DESCRIPTION",
    "_empty_mechanism_changes_to_list",
    "_mechanism_changes_json_schema",
    "_validate_unique_mechanism_change_ids",
]
