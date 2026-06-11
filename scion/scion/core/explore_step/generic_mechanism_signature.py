"""Generic proposal-side novelty signatures.

The helpers in this module intentionally use only compact structured metadata.
They do not inspect hypothesis prose or lesson text, and their output is meant
for proposal visibility/observability only.
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Mapping

from scion.core.models import mechanism_changes

_FAMILY_SUFFIXES = frozenset(
    {
        "attempt",
        "candidate",
        "experimental",
        "followup",
        "follow_up",
        "probe",
        "refine",
        "refined",
        "refinement",
        "retry",
        "test",
        "tuned",
        "variant",
    }
)
_EXPLICIT_FAMILY_FIELDS = (
    "mechanism_family",
    "mechanism_class",
    "generic_mechanism_family",
)
_ALGORITHM_FAMILY_FIELDS = (
    "algorithm_family",
)
_MECHANISM_ID_FIELDS = (
    "mechanism_id",
    "mechanism",
    "improvement_strategy",
    "operator_id",
)
_ACTIVATION_FIELDS = (
    "activation_path",
    "activation_strategy",
    "activation_trigger",
    "trigger_path",
)
_EFFECT_FIELDS = (
    "effect_path",
    "effect_strategy",
    "effect_channel",
    "expected_effect_path",
)
_RUNTIME_FIELDS = (
    "runtime_budget_strategy",
    "budget_strategy",
    "runtime_cap_strategy",
)


def generic_signature_key_from_hypothesis(
    hypothesis: Any,
    *,
    broad_family_ids: Iterable[str] = (),
) -> tuple[str, str, str, str]:
    """Return a compact near-duplicate key for a hypothesis proposal."""

    payload = generic_signature_payload_from_hypothesis(
        hypothesis,
        broad_family_ids=broad_family_ids,
    )
    return (
        str(payload.get("mechanism_family") or ""),
        str(payload.get("target_file") or ""),
        str(payload.get("action") or ""),
        str(payload.get("change_locus") or ""),
    )


def generic_signature_payload_from_hypothesis(
    hypothesis: Any,
    *,
    broad_family_ids: Iterable[str] = (),
) -> dict[str, str]:
    """Return structured signature metadata suitable for diagnostics."""

    novelty = getattr(hypothesis, "novelty_signature", None)
    signature = novelty if isinstance(novelty, Mapping) else {}
    target_file = clean_path(getattr(hypothesis, "target_file", None))
    action = clean_token(getattr(hypothesis, "action", None))
    change_locus = clean_token(getattr(hypothesis, "change_locus", None))
    mechanism_ids = [
        clean_token(change.id)
        for change in mechanism_changes(hypothesis)
        if clean_token(change.id)
    ]
    family = generic_mechanism_family_from_parts(
        mechanism_ids=mechanism_ids,
        signature=signature,
        target_file=target_file,
        change_locus=change_locus,
        broad_family_ids=broad_family_ids,
    )
    return _drop_empty(
        {
            "mechanism_family": family,
            "target_file": target_file,
            "action": action,
            "change_locus": change_locus,
            "activation_path": _first_signature_value(signature, _ACTIVATION_FIELDS),
            "effect_path": _first_signature_value(signature, _EFFECT_FIELDS),
            "runtime_budget_strategy": (
                _first_signature_value(signature, _RUNTIME_FIELDS)
                or clean_token(getattr(hypothesis, "runtime_budget_strategy", None))
            ),
        }
    )


def generic_signature_key_from_parts(
    *,
    mechanism_ids: Iterable[Any] = (),
    signature: Mapping[str, Any] | None = None,
    target_file: Any = None,
    action: Any = None,
    change_locus: Any = None,
    broad_family_ids: Iterable[str] = (),
) -> tuple[str, str, str, str]:
    """Return a compact near-duplicate key from already-projected metadata."""

    target = clean_path(target_file)
    action_token = clean_token(action)
    locus = clean_token(change_locus)
    family = generic_mechanism_family_from_parts(
        mechanism_ids=[clean_token(item) for item in mechanism_ids],
        signature=signature or {},
        target_file=target,
        change_locus=locus,
        broad_family_ids=broad_family_ids,
    )
    return (family, target, action_token, locus)


def generic_signature_payload_from_key(
    key: tuple[str, str, str, str],
) -> dict[str, str]:
    """Return JSON-safe diagnostic fields for a compact signature key."""

    family, target_file, action, change_locus = key
    return _drop_empty(
        {
            "mechanism_family": family,
            "target_file": target_file,
            "action": action,
            "change_locus": change_locus,
        }
    )


def generic_mechanism_family_from_parts(
    *,
    mechanism_ids: Iterable[Any] = (),
    signature: Mapping[str, Any] | None = None,
    target_file: str = "",
    change_locus: str = "",
    broad_family_ids: Iterable[str] = (),
) -> str:
    """Return a conservative generic mechanism family token."""

    signature = signature or {}
    broad = {clean_token(item) for item in broad_family_ids if clean_token(item)}
    explicit_values = [
        signature.get(field)
        for field in _EXPLICIT_FAMILY_FIELDS
        if clean_token(signature.get(field)) not in broad
    ]
    id_values = [
        signature.get(field)
        for field in _MECHANISM_ID_FIELDS
        if clean_token(signature.get(field))
    ]
    algorithm_values = [
        signature.get(field)
        for field in _ALGORITHM_FAMILY_FIELDS
        if clean_token(signature.get(field)) not in broad
    ]
    candidates = [*explicit_values, *mechanism_ids, *id_values, *algorithm_values]
    for candidate in candidates:
        family = normalize_mechanism_family(
            candidate,
            target_file=target_file,
            change_locus=change_locus,
        )
        if family and family != "unknown":
            return family
    return "unknown"


def normalize_mechanism_family(
    value: Any,
    *,
    target_file: str = "",
    change_locus: str = "",
) -> str:
    """Normalize a mechanism id/family into a generic near-duplicate family."""

    token = clean_token(value)
    if not token:
        return ""
    parts = [part for part in token.split("_") if part]
    if not parts:
        return ""
    target_token = clean_token(target_file)
    locus_token = clean_token(change_locus)
    grouped = _known_generic_group(parts, target_token=target_token, locus=locus_token)
    if grouped:
        return grouped
    trimmed = list(parts)
    while len(trimmed) > 1 and trimmed[-1] in _FAMILY_SUFFIXES:
        trimmed.pop()
    return "_".join(trimmed) if trimmed else "unknown"


def clean_token(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return "_".join(part for part in text.split("_") if part)


def clean_path(value: Any) -> str:
    return str(value or "").replace("\\", "/").lstrip("/").strip()


def _known_generic_group(
    parts: list[str],
    *,
    target_token: str,
    locus: str,
) -> str:
    part_set = set(parts)
    joined = "_".join(parts)
    surface = f"{target_token}_{locus}"
    if "seed" in part_set and (
        "selector" in part_set
        or "select" in part_set
        or "construction" in part_set
        or "constructive" in part_set
    ):
        return "construction_seed_selector"
    if (
        ({"exchange", "swap"} & part_set or "exchange" in joined)
        and ("local_search" in surface or "neighborhood" in surface)
    ):
        return "local_search_exchange"
    if "pairwise" in part_set and (
        {"merge", "repack", "packing", "pack"} & part_set
        or "merge" in joined
        or "repack" in joined
    ):
        return "pairwise_merge_repack"
    if (
        {"guard", "constraint", "feasibility"} & part_set
        and (
            {"strict", "refine", "refinement", "tighten", "tightened"} & part_set
            or "guard" in joined
        )
    ):
        return "guard_refinement"
    return ""


def _first_signature_value(
    signature: Mapping[str, Any],
    fields: Iterable[str],
) -> str:
    for field in fields:
        text = clean_token(signature.get(field))
        if text:
            return text
    return ""


def _drop_empty(value: Mapping[str, str]) -> dict[str, str]:
    return {key: item for key, item in value.items() if item}


__all__ = [
    "clean_path",
    "clean_token",
    "generic_mechanism_family_from_parts",
    "generic_signature_key_from_hypothesis",
    "generic_signature_key_from_parts",
    "generic_signature_payload_from_hypothesis",
    "generic_signature_payload_from_key",
    "normalize_mechanism_family",
]
