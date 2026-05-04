from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from scion.config.problem import ProtocolConfig
from scion.core.decision import DecisionEngine
from scion.core.models import Decision, DecisionFeatures


@dataclass(frozen=True)
class CoordinatedDecision:
    decision: Decision
    reason_codes: Tuple[str, ...]
    rule: str
    features_snapshot: DecisionFeatures


class DecisionCoordinator:
    """Thin orchestration boundary around the deterministic decision engine."""

    def __init__(
        self,
        config: ProtocolConfig | None = None,
        *,
        engine: DecisionEngine | None = None,
    ) -> None:
        if engine is None and config is None:
            raise ValueError("config or engine is required")
        self._engine = engine or DecisionEngine(config)  # type: ignore[arg-type]

    def decide(self, features: DecisionFeatures) -> CoordinatedDecision:
        outcome = self._engine.decide(features)
        reason_codes = _normalize_reason_codes(
            outcome.reason_codes,
            outcome.decision,
        )
        return CoordinatedDecision(
            decision=outcome.decision,
            reason_codes=reason_codes,
            rule=_rule_name(features, outcome.decision, reason_codes),
            features_snapshot=outcome.features_snapshot,
        )


def _normalize_reason_codes(
    reason_codes: Tuple[str, ...],
    decision: Decision,
) -> Tuple[str, ...]:
    if reason_codes:
        return tuple(str(code) for code in reason_codes)
    return (f"{decision.value.upper()}_NO_REASON",)


def _rule_name(
    features: DecisionFeatures,
    decision: Decision,
    reason_codes: Tuple[str, ...],
) -> str:
    primary = reason_codes[0] if reason_codes else "NO_REASON"
    return f"{features.stage}:{primary}->{decision.value}"
