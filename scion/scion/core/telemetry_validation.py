"""Formal Protocol accounting predicates.

Runtime and mechanism observations live on ``ProtocolResult``.  They are
evidence, not a second host-side telemetry gate.
"""
from __future__ import annotations

from scion.core.models import ProtocolResult


def formal_screening_attempted(
    protocol_result: ProtocolResult | None,
) -> bool:
    if protocol_result is None:
        return False
    stage = getattr(protocol_result.stage, "value", protocol_result.stage)
    return str(stage or "").strip().lower() == "screening"


__all__ = ["formal_screening_attempted"]
