"""Canonical ordinary projection of a selected hypothesis research basis."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

_REQUIRED_FIELDS = frozenset(
    {
        "read_refs",
        "nearest_prior_refs",
        "material_delta",
        "alternatives_considered",
        "observable_prediction",
        "falsification_condition",
    }
)
_FIELDS = _REQUIRED_FIELDS | {"history_review"}
_MAX_REFS = 64
_MAX_REF_CHARS = 64
_MAX_ALTERNATIVES = 8
_MAX_TEXT_CHARS = 4000


def normalize_selected_hypothesis_research_basis(
    value: Any,
) -> dict[str, Any] | None:
    """Return the strict six-required-field JSON-primitive basis, or ``None``.

    This is an ordinary tainted research artifact.  Normalization makes the
    StepRecord, lineage SQLite row, campaign summary, and research-history
    JSONL projections byte-shape compatible without making it a Protocol or
    Decision input.
    """

    if value is None:
        return None
    if not isinstance(value, Mapping) or not _REQUIRED_FIELDS <= set(value) <= _FIELDS:
        raise ValueError(
            "selected hypothesis research basis must contain the six required "
            "fields and only the optional history_review field"
        )
    read_refs = _normalize_refs(value["read_refs"], field="read_refs", required=True)
    nearest_prior_refs = _normalize_refs(
        value["nearest_prior_refs"],
        field="nearest_prior_refs",
        required=False,
    )
    if not set(nearest_prior_refs).issubset(read_refs):
        raise ValueError(
            "selected hypothesis nearest_prior_refs must also appear in read_refs"
        )
    alternatives = value["alternatives_considered"]
    if (
        not isinstance(alternatives, (list, tuple))
        or not 1 <= len(alternatives) <= _MAX_ALTERNATIVES
    ):
        raise ValueError(
            "selected hypothesis alternatives_considered must be bounded and nonempty"
        )
    normalized = {
        "read_refs": list(read_refs),
        "nearest_prior_refs": list(nearest_prior_refs),
        "material_delta": _normalize_text(
            value["material_delta"], field="material_delta"
        ),
        "alternatives_considered": [
            _normalize_text(item, field="alternatives_considered item")
            for item in alternatives
        ],
        "observable_prediction": _normalize_text(
            value["observable_prediction"], field="observable_prediction"
        ),
        "falsification_condition": _normalize_text(
            value["falsification_condition"], field="falsification_condition"
        ),
    }
    if "history_review" in value:
        history_review = _normalize_history_review(value["history_review"])
        used_refs = {
            item["ref"] for item in history_review if item["disposition"] == "used"
        }
        rejected_refs = {
            item["ref"] for item in history_review if item["disposition"] == "rejected"
        }
        if not used_refs.issubset(nearest_prior_refs):
            raise ValueError(
                "selected hypothesis used history_review refs must appear in "
                "nearest_prior_refs"
            )
        if rejected_refs.intersection(nearest_prior_refs):
            raise ValueError(
                "selected hypothesis rejected history_review refs cannot appear "
                "in nearest_prior_refs"
            )
        normalized["history_review"] = history_review
    return normalized


def canonical_selected_hypothesis_research_basis_json(value: Any) -> str | None:
    """Return canonical JSON for durable lineage storage."""

    normalized = normalize_selected_hypothesis_research_basis(value)
    if normalized is None:
        return None
    return json.dumps(
        normalized,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    )


def _normalize_refs(
    value: Any,
    *,
    field: str,
    required: bool,
) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)) or len(value) > _MAX_REFS:
        raise ValueError(f"selected hypothesis {field} must be a bounded array")
    refs = tuple(_normalize_ref(item, field=f"{field} item") for item in value)
    if (required and not refs) or len(refs) != len(set(refs)):
        raise ValueError(
            f"selected hypothesis {field} must contain unique nonempty refs"
        )
    return refs


def _normalize_ref(value: Any, *, field: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"selected hypothesis {field} must be text")
    normalized = value.strip()
    if not normalized or len(normalized) > _MAX_REF_CHARS:
        raise ValueError(f"selected hypothesis {field} is invalid")
    return normalized


def _normalize_text(value: Any, *, field: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"selected hypothesis {field} must be text")
    normalized = value.strip()
    if not normalized or len(normalized) > _MAX_TEXT_CHARS:
        raise ValueError(f"selected hypothesis {field} is invalid")
    return normalized


def _normalize_history_review(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, (list, tuple)) or not 1 <= len(value) <= _MAX_REFS:
        raise ValueError(
            "selected hypothesis history_review must be bounded and nonempty"
        )
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, Mapping):
            raise TypeError("selected hypothesis history_review items must be mappings")
        disposition = item.get("disposition")
        expected = (
            {"ref", "disposition"}
            if disposition == "used"
            else {"ref", "disposition", "reason"}
        )
        if set(item) != expected or disposition not in {"used", "rejected"}:
            raise ValueError("selected hypothesis history_review item is invalid")
        ref = _normalize_ref(item["ref"], field="history_review ref")
        if ref in seen:
            raise ValueError("selected hypothesis history_review refs must be unique")
        normalized: dict[str, str] = {
            "ref": ref,
            "disposition": disposition,
        }
        if disposition == "rejected":
            normalized["reason"] = _normalize_text(
                item["reason"], field="history_review reason"
            )
        seen.add(ref)
        result.append(normalized)
    return result


__all__ = [
    "canonical_selected_hypothesis_research_basis_json",
    "normalize_selected_hypothesis_research_basis",
]
