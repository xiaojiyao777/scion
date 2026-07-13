"""Audit grouping for formal protocol and Decision reason codes."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


_GATE_OBSERVATION_PREFIXES = (
    "SCREENING_",
    "VALIDATION_",
    "FROZEN_",
    "CANARY_",
    "NO_SCREENING_STATS",
    "RUNTIME_",
    "CANDIDATE_RUNTIME_FAILURE",
    "INCOMPLETE_RUNTIME_EVIDENCE",
)


@dataclass(frozen=True)
class ReasonCodeGroups:
    gate_observation_reason_codes: tuple[str, ...] = ()


def classify_reason_codes(
    reason_codes: Iterable[str] | None,
    *,
    protocol_reason_codes: Iterable[str] | None = None,
) -> ReasonCodeGroups:
    protocol_set = set(_clean_codes(protocol_reason_codes))
    gate = [
        code
        for code in _clean_codes(reason_codes)
        if code in protocol_set or code.upper().startswith(_GATE_OBSERVATION_PREFIXES)
    ]
    return ReasonCodeGroups(
        gate_observation_reason_codes=tuple(dict.fromkeys(gate)),
    )


def _clean_codes(codes: Iterable[str] | None) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(str(code).strip() for code in codes or () if str(code).strip())
    )


__all__ = ["ReasonCodeGroups", "classify_reason_codes"]
