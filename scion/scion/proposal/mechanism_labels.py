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
    preferred_label: str | None = None,
) -> str:
    """Extract a mechanism label using only problem-provided taxonomy data."""
    families = taxonomy_family_labels(taxonomy)
    if not families:
        return DEFAULT_MECHANISM_LABEL

    normalized = normalize_label_text(hypothesis_text or "")
    matches = _collect_family_matches(
        normalized,
        families,
        taxonomy_aliases(taxonomy),
    )
    preferred = _canonical_family(preferred_label, families)
    if preferred is not None and preferred in matches:
        return preferred
    if matches:
        return _best_family_match(matches)

    if DEFAULT_MECHANISM_LABEL in families:
        return DEFAULT_MECHANISM_LABEL
    return UNKNOWN_FAMILY_LABEL


def _match_family_label(text: str, families: list[str]) -> str | None:
    matches = _collect_family_matches(text, families, {})
    return _best_family_match(matches) if matches else None


def _match_family_alias(
    text: str,
    families: list[str],
    aliases: dict[str, list[str]],
) -> str | None:
    matches = _collect_family_matches(text, families, aliases, include_family_labels=False)
    return _best_family_match(matches) if matches else None


def _canonical_family(label: str | None, families: list[str]) -> str | None:
    if not label:
        return None
    normalized = normalize_label_text(label)
    for family in families:
        if normalize_label_text(family) == normalized:
            return family
    return None


def _collect_family_matches(
    text: str,
    families: list[str],
    aliases: dict[str, list[str]],
    *,
    include_family_labels: bool = True,
) -> dict[str, dict[str, int]]:
    matches: dict[str, dict[str, int]] = {}

    def add(family: str, phrase: str, *, explicit: bool = False) -> None:
        normalized_phrase = normalize_label_text(phrase)
        if not normalized_phrase:
            return
        positions = _phrase_positions(text, normalized_phrase)
        if not positions:
            return
        entry = matches.setdefault(
            family,
            {
                "score": 0,
                "best_len": 0,
                "earliest": 1_000_000_000,
                "count": 0,
            },
        )
        length = len(normalized_phrase)
        weight = length + (20 if explicit else 0)
        entry["score"] += weight * len(positions)
        entry["best_len"] = max(entry["best_len"], length)
        entry["earliest"] = min(entry["earliest"], min(positions))
        entry["count"] += len(positions)

    for family in families:
        if include_family_labels:
            add(family, family, explicit=True)
        for alias in aliases.get(family, []):
            add(family, alias)
    return matches


def _phrase_positions(text: str, phrase: str) -> list[int]:
    if not phrase:
        return []
    bounded = re.compile(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])")
    positions = [match.start() for match in bounded.finditer(text)]
    if positions:
        return positions

    # Some problem specs intentionally provide stem aliases. Preserve that
    # behavior without falling back to arbitrary substring matches.
    if " " not in phrase and len(phrase) >= 5:
        prefix = re.compile(rf"(?<![a-z0-9]){re.escape(phrase)}")
        return [match.start() for match in prefix.finditer(text)]
    return []


def _best_family_match(matches: dict[str, dict[str, int]]) -> str:
    return max(
        matches.items(),
        key=lambda item: (
            item[1]["score"],
            item[1]["best_len"],
            item[1]["count"],
            -item[1]["earliest"],
        ),
    )[0]
