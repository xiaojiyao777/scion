"""Generic mechanism label extraction for proposal/search context."""
from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

DEFAULT_MECHANISM_LABEL = "generic"
UNKNOWN_FAMILY_LABEL = "NEW_FAMILY"


def normalize_label_text(value: str) -> str:
    """Normalize free text and configured labels for robust matching."""
    return re.sub(
        r"\s+",
        " ",
        str(value)
        .lower()
        .replace("_", " ")
        .replace("-", " ")
        .replace("*", " ")
        .replace("/", " "),
    ).strip()


def taxonomy_family_labels(taxonomy: Any) -> list[str]:
    """Return candidate family labels from a problem taxonomy object or list."""
    if taxonomy is None:
        return []
    families = taxonomy.get("families") if isinstance(taxonomy, Mapping) else getattr(taxonomy, "families", taxonomy)
    if isinstance(families, (str, bytes)) or not isinstance(families, Iterable):
        return []
    return [str(label).strip() for label in families if str(label).strip()]


def taxonomy_aliases(taxonomy: Any) -> dict[str, list[str]]:
    """Return problem-provided family aliases keyed by canonical family label."""
    if taxonomy is None:
        return {}
    aliases = taxonomy.get("aliases") if isinstance(taxonomy, Mapping) else getattr(taxonomy, "aliases", None)
    if not isinstance(aliases, Mapping):
        return {}

    result: dict[str, list[str]] = {}
    for family, values in aliases.items():
        key = str(family).strip()
        if not key:
            continue
        if isinstance(values, (str, bytes)):
            cleaned = [str(values).strip()] if str(values).strip() else []
        elif isinstance(values, Iterable):
            cleaned = [str(value).strip() for value in values if str(value).strip()]
        else:
            cleaned = []
        if cleaned:
            result[key] = cleaned
    return result


def extract_mechanism_label(
    hypothesis_text: str,
    taxonomy: Any = None,
) -> str:
    """Extract a mechanism label using only problem-provided taxonomy data."""
    families = taxonomy_family_labels(taxonomy)
    if not families:
        return DEFAULT_MECHANISM_LABEL

    normalized = normalize_label_text(hypothesis_text or "")
    exact = _match_family_label(normalized, families)
    if exact is not None:
        return exact

    alias = _match_family_alias(normalized, families, taxonomy_aliases(taxonomy))
    if alias is not None:
        return alias

    if DEFAULT_MECHANISM_LABEL in families:
        return DEFAULT_MECHANISM_LABEL
    return UNKNOWN_FAMILY_LABEL


def _match_family_label(text: str, families: list[str]) -> str | None:
    for label in families:
        normalized_label = normalize_label_text(label)
        if normalized_label and normalized_label in text:
            return label
    return None


def _match_family_alias(
    text: str,
    families: list[str],
    aliases: dict[str, list[str]],
) -> str | None:
    matches: list[tuple[int, str]] = []
    for family in families:
        for alias in aliases.get(family, []):
            normalized_alias = normalize_label_text(alias)
            if normalized_alias and normalized_alias in text:
                matches.append((len(normalized_alias), family))
    if not matches:
        return None
    return max(matches, key=lambda item: item[0])[1]
