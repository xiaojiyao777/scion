"""Runtime telemetry observation aggregation."""
from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from scion.runtime.telemetry_guard.evidence import (
    _bounded_value,
    _empty_value,
    _positive_evidence,
)
from scion.runtime.telemetry_guard.runtime_paths import _runtime_path_observation


def _runtime_field_summary(
    field: str,
    *,
    candidate_runtimes: Sequence[Mapping[str, Any]],
    champion_runtimes: Sequence[Mapping[str, Any]],
    mechanism: str | None = None,
) -> dict[str, Any]:
    candidate_present = 0
    candidate_positive = 0
    candidate_zero = 0
    candidate_missing = 0
    champion_positive = 0
    examples: list[Any] = []

    for runtime in candidate_runtimes:
        observation = _runtime_path_observation(runtime, field, mechanism=mechanism)
        if not observation["present"]:
            candidate_missing += 1
            continue
        candidate_present += 1
        value = observation["value"]
        if _positive_evidence(value):
            candidate_positive += 1
        elif not _empty_value(value):
            candidate_zero += 1
        if len(examples) < 3:
            examples.append(_bounded_value(value))

    for runtime in champion_runtimes:
        observation = _runtime_path_observation(runtime, field, mechanism=mechanism)
        if observation["present"] and _positive_evidence(observation["value"]):
            champion_positive += 1

    return {
        "candidate_present": candidate_present,
        "candidate_missing": candidate_missing,
        "candidate_positive": candidate_positive,
        "candidate_zero": candidate_zero,
        "champion_positive": champion_positive,
        "examples": examples,
    }


def _protected_objective_tokens(protected_objectives: Sequence[str]) -> tuple[str, ...]:
    tokens: list[str] = []
    for objective in protected_objectives:
        token = str(objective or "").strip().lower()
        if token:
            tokens.append(token)
    return tuple(dict.fromkeys(tokens))


def _matches_protected_objective_field(
    field: str,
    protected_tokens: Sequence[str],
) -> bool:
    if not protected_tokens:
        return False
    normalized_field = re.sub(r"[^a-z0-9]+", "_", str(field or "").lower()).strip("_")
    if not normalized_field:
        return False
    padded = f"_{normalized_field}_"
    for token in protected_tokens:
        normalized_token = re.sub(r"[^a-z0-9]+", "_", token).strip("_")
        if normalized_token and f"_{normalized_token}_" in padded:
            return True
    return False
