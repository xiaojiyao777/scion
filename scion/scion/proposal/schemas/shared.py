"""Shared schema helpers for proposal structured outputs."""

from __future__ import annotations

import re
from typing import Any, Dict, Literal

from pydantic import BaseModel, ConfigDict, field_validator

_MECHANISM_ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_MECHANISM_CHANGE_TYPES = ("add", "modify", "replace", "remove", "integrate")
_MECHANISM_CHANGE_TYPE_ALIASES = {
    "parameterize": "modify",
    "tune": "modify",
    "telemetry_wiring": "modify",
}
_MECHANISM_CHANGE_SELECTION_PRIORITY = {
    "integrate": 0,
    "modify": 1,
    "add": 2,
    "remove": 3,
    "replace": 4,
}
MECHANISM_SCHEMA_QUALITY_BLOCK = "schema_quality_block"
MECHANISM_DUPLICATE_ID_CONFLICT = "mechanism_changes_duplicate_id_conflict"
MECHANISM_CHANGE_TYPE_ALIAS_NORMALIZED = (
    "mechanism_change_type_alias_normalized"
)
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
    "expected_telemetry paths. Do not replace that declared mechanism id with "
    "a broad aggregate phase, family, or runtime bucket label. Declare "
    "delta-valued effect fields such as "
    "best_delta or delta_sum only when the mechanism can emit "
    "context.record_move with a positive improvement delta; activity-only or "
    "activation-only mechanisms must use activity/activation telemetry instead."
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
                    "description": (
                        "Generic mechanism change enum only. Branch research "
                        "action labels such as tune, repair, parameterize, or "
                        "telemetry_wiring are not change_type values; map "
                        "tune/parameterize to modify and telemetry_wiring to "
                        "modify or integrate."
                    ),
                },
            },
            "additionalProperties": False,
        },
    }


def _empty_mechanism_changes_to_list(value: Any) -> Any:
    return [] if value in (None, "") else value


def _normalize_mechanism_changes_preflight(value: Any) -> Any:
    """Deduplicate safely repairable mechanism rows before schema validation."""

    normalized, _repairs = normalize_mechanism_changes_with_repair_attribution(value)
    return normalized


def normalize_mechanism_changes_with_repair_attribution(
    value: Any,
    *,
    field: str = "mechanism_changes",
) -> tuple[Any, tuple[dict[str, Any], ...]]:
    """Normalize duplicate mechanism ids and return auditable repair records.

    Multiple rows for the same mechanism id are a JSON/schema shape problem, not
    an algorithm-quality signal.  The normalized shape keeps one row per id and
    deterministically selects the most specific generic action.
    """

    value = _empty_mechanism_changes_to_list(value)
    if not isinstance(value, list):
        return value, ()

    order: list[str] = []
    raw_by_id: dict[str, list[tuple[str, str, Any]]] = {}
    passthrough: list[Any] = []
    repairs: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        mechanism_id, change_type = _mechanism_change_identity(item)
        normalized_change_type = _normalize_mechanism_change_type_alias(change_type)
        if not _mechanism_change_item_is_normalizable(
            item,
            mechanism_id,
            normalized_change_type,
        ):
            passthrough.append(item)
            continue
        if normalized_change_type != change_type:
            repairs.append(
                _mechanism_change_type_alias_repair(
                    field=field,
                    index=index,
                    mechanism_id=mechanism_id,
                    original_change_type=change_type,
                    normalized_change_type=normalized_change_type,
                )
            )
        if mechanism_id not in raw_by_id:
            order.append(mechanism_id)
            raw_by_id[mechanism_id] = []
        raw_by_id[mechanism_id].append((change_type, normalized_change_type, item))

    if not raw_by_id:
        return value, ()

    normalized: list[Any] = []
    for mechanism_id in order:
        entries = raw_by_id[mechanism_id]
        original_change_types = [
            original_change_type
            for original_change_type, _change_type, _item in entries
        ]
        change_types = [change_type for _original, change_type, _item in entries]
        unique_change_types = sorted(
            dict.fromkeys(change_types),
            key=lambda item: (
                -_MECHANISM_CHANGE_SELECTION_PRIORITY.get(item, -1),
                item,
            ),
        )
        selected_change_type = unique_change_types[0]
        normalized.append(
            {"id": mechanism_id, "change_type": selected_change_type}
        )
        duplicate_count = len(entries) - 1
        if duplicate_count <= 0:
            continue
        if len(unique_change_types) > 1:
            repairs.append(
                {
                    "field": field,
                    "repair_kind": "host_mechanical_normalization",
                    "root_cause": "duplicate_id_multiple_change_types",
                    "diagnostic_code": MECHANISM_DUPLICATE_ID_CONFLICT,
                    "mechanism_id": mechanism_id,
                    "input_change_types": original_change_types,
                    "normalized_change_types": change_types,
                    "unique_change_types": unique_change_types,
                    "selected_change_type": selected_change_type,
                    "selection_policy": "strongest_generic_change_type",
                    "action": "coalesced_to_single_mechanism_change",
                    "schema_only_repair": True,
                    "quality_block": False,
                    "guidance": (
                        "Host normalized duplicate mechanism_changes rows only. "
                        "Do not rewrite algorithm assumptions for this repair."
                    ),
                }
            )
        else:
            repairs.append(
                {
                    "field": field,
                    "repair_kind": "host_mechanical_normalization",
                    "root_cause": "exact_duplicate_item",
                    "diagnostic_code": "mechanism_changes_exact_duplicate",
                    "mechanism_id": mechanism_id,
                    "selected_change_type": selected_change_type,
                    "duplicate_count": duplicate_count,
                    "action": "deduplicated_exact_items",
                    "schema_only_repair": True,
                    "quality_block": False,
                }
            )
    normalized.extend(passthrough)
    return normalized, tuple(repairs)


def _normalize_mechanism_change_type_alias(change_type: str) -> str:
    return _MECHANISM_CHANGE_TYPE_ALIASES.get(change_type, change_type)


def _mechanism_change_type_alias_repair(
    *,
    field: str,
    index: int,
    mechanism_id: str,
    original_change_type: str,
    normalized_change_type: str,
) -> dict[str, Any]:
    return {
        "field": field,
        "json_pointer": f"/{field}/{index}/change_type",
        "repair_kind": MECHANISM_CHANGE_TYPE_ALIAS_NORMALIZED,
        "root_cause": "branch_action_label_used_as_mechanism_change_type",
        "diagnostic_code": MECHANISM_CHANGE_TYPE_ALIAS_NORMALIZED,
        "mechanism_id": mechanism_id,
        "original_change_type": original_change_type,
        "normalized_change_type": normalized_change_type,
        "original_value": original_change_type,
        "normalized_value": normalized_change_type,
        "action": "normalized_change_type_alias",
        "schema_only_repair": True,
        "quality_block": False,
        "guidance": (
            "Host normalized a branch research action label to a legal "
            "mechanism_changes change_type. Do not treat this as an algorithm "
            "quality signal."
        ),
    }


def _mechanism_change_identity(item: Any) -> tuple[str, str]:
    if isinstance(item, dict):
        return (
            str(item.get("id") or "").strip(),
            str(item.get("change_type") or "").strip(),
        )
    return (
        str(getattr(item, "id", "") or "").strip(),
        str(getattr(item, "change_type", "") or "").strip(),
    )


def _mechanism_change_item_is_normalizable(
    item: Any,
    mechanism_id: str,
    change_type: str,
) -> bool:
    if not _MECHANISM_ID_RE.fullmatch(mechanism_id):
        return False
    if change_type not in _MECHANISM_CHANGE_TYPES:
        return False
    if isinstance(item, dict):
        return set(item).issubset({"id", "change_type"})
    return True


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
    "_normalize_mechanism_changes_preflight",
    "_mechanism_changes_json_schema",
    "_validate_unique_mechanism_change_ids",
    "normalize_mechanism_changes_with_repair_attribution",
    "MECHANISM_CHANGE_TYPE_ALIAS_NORMALIZED",
    "MECHANISM_DUPLICATE_ID_CONFLICT",
    "MECHANISM_SCHEMA_QUALITY_BLOCK",
]
