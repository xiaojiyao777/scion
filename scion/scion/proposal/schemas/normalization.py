"""Schema-level normalization helpers for proposal outputs."""

from __future__ import annotations

import json
from typing import Any, Mapping

from .shared import normalize_mechanism_changes_with_repair_attribution

_NOVELTY_SIGNATURE_SCALAR_MAX_CHARS = 120


def normalize_patch_output_with_repair_attribution(
    raw: Mapping[str, Any],
) -> tuple[dict[str, Any], tuple[dict[str, Any], ...]]:
    """Normalize host-repairable patch output shape issues and record why."""

    normalized = dict(raw)
    repairs: list[dict[str, Any]] = []
    if "mechanism_changes" in normalized:
        mechanism_changes, mechanism_repairs = (
            normalize_mechanism_changes_with_repair_attribution(
                normalized.get("mechanism_changes")
            )
        )
        normalized["mechanism_changes"] = mechanism_changes
        repairs.extend(mechanism_repairs)
    if "additional_changes" not in normalized:
        return normalized, tuple(repairs)

    value = normalized.get("additional_changes")
    if value in (None, ""):
        normalized["additional_changes"] = []
        repairs.append(
            {
                "field": "additional_changes",
                "repair_kind": "host_mechanical_normalization",
                "root_cause": "empty_or_null",
                "action": "normalized_to_empty_array",
            }
        )
        return normalized, tuple(repairs)

    if isinstance(value, str):
        return normalized, tuple(repairs)

    if isinstance(value, list):
        compacted: list[Any] = []
        removed_empty = 0
        removed_duplicates = 0
        seen: set[str] = set()
        for item in value:
            if item in (None, "", {}):
                removed_empty += 1
                continue
            fingerprint = json.dumps(item, sort_keys=True, default=str)
            if fingerprint in seen:
                removed_duplicates += 1
                continue
            seen.add(fingerprint)
            compacted.append(item)
        if removed_empty:
            repairs.append(
                {
                    "field": "additional_changes",
                    "repair_kind": "host_mechanical_normalization",
                    "root_cause": "empty_or_null_item",
                    "action": "dropped_empty_items",
                    "count": removed_empty,
                }
            )
        if removed_duplicates:
            repairs.append(
                {
                    "field": "additional_changes",
                    "repair_kind": "host_mechanical_normalization",
                    "root_cause": "exact_duplicate_item",
                    "action": "deduplicated_exact_items",
                    "count": removed_duplicates,
                }
            )
        if removed_empty or removed_duplicates:
            normalized["additional_changes"] = compacted
    return normalized, tuple(repairs)


def _normalize_novelty_signature(value: Any) -> Any:
    if value in (None, "", [], (), {}):
        return {}
    if isinstance(value, Mapping):
        return {
            str(key): _normalize_novelty_signature_item(item)
            for key, item in value.items()
            if str(key).strip()
        }
    return value


def _normalize_novelty_signature_item(value: Any) -> Any:
    if isinstance(value, str):
        return _compact_novelty_scalar(value)
    if isinstance(value, Mapping):
        return {
            str(key): _normalize_novelty_signature_item(item)
            for key, item in value.items()
            if str(key).strip()
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_normalize_novelty_signature_item(item) for item in value]
    return value


def _compact_novelty_scalar(value: str) -> str:
    text = " ".join(str(value or "").strip().split())
    if len(text) <= _NOVELTY_SIGNATURE_SCALAR_MAX_CHARS:
        return text
    return text[:_NOVELTY_SIGNATURE_SCALAR_MAX_CHARS].rstrip()


__all__ = [
    "normalize_patch_output_with_repair_attribution",
    "_compact_novelty_scalar",
    "_normalize_novelty_signature",
    "_normalize_novelty_signature_item",
]
