"""Schema and semantic-signature helpers for contract validation."""
from __future__ import annotations

import json
import re
from typing import Any

from scion.core.models import (
    HypothesisProposal,
    HypothesisRecord,
    PatchProposal,
    mechanism_changes,
)

DIRECT_SIGNATURE_FIELDS = frozenset(
    {
        "predicted_direction",
        "target_objectives",
        "protected_objectives",
    }
)
WEAK_SIGNATURE_FIELDS = frozenset({"predicted_direction"})
NONEMPTY_SEQUENCE_SIGNATURE_FIELDS = frozenset(
    {
        "selected_components",
        "deep_components_selected",
    }
)
MAX_GENERIC_SIGNATURE_ITEMS = 16
MAX_GENERIC_SIGNATURE_STRING = 120
SIGNATURE_FIELD_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")

PREDICTED_DIRECTIONS = frozenset({"improve", "tradeoff", "exploratory"})
MAX_OBJECTIVE_SIGNATURE_ITEMS = 16
MECHANISM_ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
MECHANISM_CHANGE_TYPES = frozenset(
    {"add", "modify", "replace", "remove", "integrate"}
)


def supports_semantic_signature_field(field: str) -> bool:
    name = str(field).strip()
    return name in DIRECT_SIGNATURE_FIELDS or bool(SIGNATURE_FIELD_RE.fullmatch(name))


def objective_metric_names(problem_spec: Any) -> frozenset[str]:
    specs = getattr(problem_spec, "objectives", None)
    if specs is None:
        specs = getattr(problem_spec, "metric_specs", None)
    names: set[str] = set()
    for spec in specs or ():
        name = getattr(spec, "name", None)
        if isinstance(name, str) and name.strip():
            names.add(name.strip())
    return frozenset(names)


def objective_list_schema_error(
    h: HypothesisProposal,
    objective_names: frozenset[str],
) -> str | None:
    for field in ("target_objectives", "protected_objectives"):
        value = getattr(h, field)
        if value in (None, ()):
            continue
        if not isinstance(value, (list, tuple, set)):
            return f"{field} must be a list of objective metric names"
        if len(value) > MAX_OBJECTIVE_SIGNATURE_ITEMS:
            return (
                f"{field} has too many entries; max "
                f"{MAX_OBJECTIVE_SIGNATURE_ITEMS}"
            )
        seen: set[str] = set()
        for item in value:
            if not isinstance(item, str) or not item.strip():
                return f"{field} must contain non-empty objective metric names"
            name = item.strip()
            seen.add(name)
            if objective_names and name not in objective_names:
                allowed = ", ".join(sorted(objective_names))
                return (
                    f"{field} contains unknown objective '{name}', "
                    f"expected one of: {allowed}"
                )
        if objective_names and len(seen) > len(objective_names):
            return f"{field} has too many distinct objective names"
    return None


def mechanism_changes_schema_error(
    proposal: HypothesisProposal | PatchProposal | HypothesisRecord,
) -> str | None:
    try:
        changes = mechanism_changes(proposal)
    except (TypeError, AttributeError) as exc:
        return f"mechanism_changes must be a list of {{id, change_type}}: {exc}"
    ids: list[str] = []
    for change in changes:
        mechanism_id = str(change.id or "").strip()
        if not MECHANISM_ID_RE.fullmatch(mechanism_id):
            return "mechanism_changes id must match ^[a-z][a-z0-9_]{0,63}$"
        if str(change.change_type or "") not in MECHANISM_CHANGE_TYPES:
            allowed = ", ".join(sorted(MECHANISM_CHANGE_TYPES))
            return (
                f"mechanism_changes change_type '{change.change_type}' "
                f"is not supported; expected one of: {allowed}"
            )
        ids.append(mechanism_id)
    duplicates = sorted(
        {mechanism_id for mechanism_id in ids if ids.count(mechanism_id) > 1}
    )
    if duplicates:
        return "mechanism_changes must not repeat id values: " + ", ".join(duplicates)
    return None


def normalize_signature_field(
    field: str,
    h: HypothesisProposal | HypothesisRecord,
    *,
    objective_names: frozenset[str],
) -> str | None:
    if field in DIRECT_SIGNATURE_FIELDS:
        if not hasattr(h, field):
            return None
        return normalize_structured_signature_value(
            field,
            getattr(h, field),
            objective_names=objective_names,
        )
    if not SIGNATURE_FIELD_RE.fullmatch(field):
        return None
    values = getattr(h, "novelty_signature", None)
    if not isinstance(values, dict) or field not in values:
        return None
    if field in NONEMPTY_SEQUENCE_SIGNATURE_FIELDS:
        return normalize_nonempty_signature_sequence(values[field])
    return normalize_generic_signature_value(values[field])


def normalize_structured_signature_value(
    field: str,
    value: Any,
    *,
    objective_names: frozenset[str],
) -> str | None:
    if field == "predicted_direction":
        if not isinstance(value, str):
            return None
        direction = value.strip()
        return direction if direction in PREDICTED_DIRECTIONS else None
    if field in ("target_objectives", "protected_objectives"):
        return normalize_objective_signature_value(value, objective_names)
    return None


def normalize_objective_signature_value(
    value: Any,
    objective_names: frozenset[str],
) -> str | None:
    if not objective_names:
        return None
    if not isinstance(value, (list, tuple, set)):
        return None
    if len(value) > min(MAX_OBJECTIVE_SIGNATURE_ITEMS, len(objective_names)):
        return None

    items: list[str] = []
    for item in value:
        if not isinstance(item, str):
            return None
        name = item.strip()
        if not name or name not in objective_names:
            return None
        items.append(name)
    if not items:
        return None
    return ",".join(sorted(set(items)))


def normalize_nonempty_signature_sequence(value: Any) -> str | None:
    if not isinstance(value, (list, tuple, set, frozenset)) or not value:
        return None
    items: list[str] = []
    for item in value:
        token = normalize_text_token(item, max_length=MAX_GENERIC_SIGNATURE_STRING)
        if token is None:
            return None
        items.append(token)
    if not items:
        return None
    if isinstance(value, (set, frozenset)):
        items = sorted(items)
    return json.dumps(items, separators=(",", ":"), ensure_ascii=True)


def normalize_generic_signature_value(value: Any, *, depth: int = 0) -> str | None:
    if depth > 3:
        return None
    if value is None:
        return None
    if depth == 0 and value is False:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            return None
        return f"{value:.6g}"
    if isinstance(value, str):
        return normalize_text_token(value, max_length=MAX_GENERIC_SIGNATURE_STRING)
    if isinstance(value, (list, tuple, set, frozenset)):
        if not value:
            return None
        if len(value) > MAX_GENERIC_SIGNATURE_ITEMS:
            return None
        items = [
            normalize_generic_signature_value(item, depth=depth + 1)
            for item in value
        ]
        if any(item is None for item in items):
            return None
        if isinstance(value, (set, frozenset)):
            items = sorted(items)  # type: ignore[arg-type]
        return json.dumps(items, separators=(",", ":"), ensure_ascii=True)
    if isinstance(value, dict):
        if not value:
            return None
        if len(value) > MAX_GENERIC_SIGNATURE_ITEMS:
            return None
        normalized: dict[str, str] = {}
        for raw_key, raw_item in value.items():
            key = normalize_text_token(raw_key, max_length=64)
            item = normalize_generic_signature_value(raw_item, depth=depth + 1)
            if key is None or item is None:
                return None
            normalized[key] = item
        return json.dumps(
            normalized,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
    return None


def normalize_text_token(value: Any, *, max_length: int) -> str | None:
    if not isinstance(value, str):
        return None
    text = " ".join(value.strip().casefold().split())
    if not text or len(text) > max_length:
        return None
    return text
