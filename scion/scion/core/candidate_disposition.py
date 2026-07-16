"""Pure post-Decision candidate-disposition projection.

This module deliberately owns no branch, workspace, persistence, prompt, or
promotion side effects.  It projects a narrow immutable fact record from the
formal :class:`DecisionOutcome` and maps that record to one typed ownership
plan.  Later lifecycle slices may persist and apply the plan; D1 only defines
the truth table.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Final

from scion.core.models import (
    Decision,
    DecisionFeatures,
    DecisionOutcome,
    ExperimentStage,
)

__all__ = [
    "CandidateDisposition",
    "CandidateDispositionError",
    "CandidateDispositionMapper",
    "CandidateDispositionPlan",
    "CandidateDispositionRule",
    "CandidateHypothesisStatus",
    "ProtocolGateOutcome",
]


class CandidateDispositionError(ValueError):
    """The trusted Decision projection has no valid D1 disposition."""


class ProtocolGateOutcome(Enum):
    """Typed Protocol verdicts accepted by the post-Decision mapper."""

    PASS = "pass"
    FAIL = "fail"
    UNCLEAR = "unclear"
    EXPAND = "expand"
    CONTINUE = "continue"


class CandidateDisposition(Enum):
    """Code-ownership consequence of one completed Decision."""

    EXACT_REUSE = "exact_reuse"
    REJECT_TO_CODE_PARENT = "reject_to_code_parent"
    PROVISIONAL_HEAD = "provisional_head"
    REJECT_TERMINAL = "reject_terminal"
    PROMOTE_EXACT = "promote_exact"


class CandidateHypothesisStatus(Enum):
    """Typed hypothesis status implied by a candidate disposition."""

    REJECTED = "rejected"
    PROVISIONAL = "provisional"
    ADVANCED = "advanced"
    PROMOTED = "promoted"


class CandidateDispositionRule(Enum):
    """Stable audit name for the pure mapping rule that produced a plan."""

    EXACT_STAGE_REUSE = "exact_stage_reuse"
    PROTOCOL_FAIL_REJECT = "protocol_fail_reject"
    PROTOCOL_PROVISIONAL = "protocol_provisional"
    PARTIAL_CHAMPION_PROVISIONAL = "partial_champion_provisional"
    TERMINAL_REJECT = "terminal_reject"
    FROZEN_PROMOTION = "frozen_promotion"


_FACT_CONSTRUCTION_TOKEN: Final[object] = object()
_PLAN_CONSTRUCTION_TOKEN: Final[object] = object()
_PARTIAL_CHAMPION_REASON: Final[tuple[str, ...]] = (
    "SCREENING_PARTIAL_CHAMPION_EVIDENCE",
)


@dataclass(frozen=True, init=False)
class _CandidateDispositionFacts:
    """Narrow trusted facts projected only from a frozen DecisionOutcome.

    The constructor is intentionally sealed.  Callers cannot assemble these
    facts from a mutable ProtocolResult, Branch summary, artifact, or report.
    """

    decision: Decision
    stage: ExperimentStage
    gate_outcome: ProtocolGateOutcome | None
    decision_reason_codes: tuple[str, ...]
    candidate_failed_pairs: int
    champion_failed_pairs: int

    def __init__(
        self,
        *,
        _token: object,
        decision: Decision,
        stage: ExperimentStage,
        gate_outcome: ProtocolGateOutcome | None,
        decision_reason_codes: tuple[str, ...],
        candidate_failed_pairs: int,
        champion_failed_pairs: int,
    ) -> None:
        if _token is not _FACT_CONSTRUCTION_TOKEN:
            raise TypeError(
                "candidate disposition facts must come from DecisionOutcome"
            )
        object.__setattr__(self, "decision", decision)
        object.__setattr__(self, "stage", stage)
        object.__setattr__(self, "gate_outcome", gate_outcome)
        object.__setattr__(self, "decision_reason_codes", decision_reason_codes)
        object.__setattr__(self, "candidate_failed_pairs", candidate_failed_pairs)
        object.__setattr__(self, "champion_failed_pairs", champion_failed_pairs)

    @classmethod
    def from_decision_outcome(
        cls,
        outcome: DecisionOutcome,
    ) -> "_CandidateDispositionFacts":
        """Project the only facts D1 may consume from formal Decision output."""

        if type(outcome) is not DecisionOutcome:
            raise TypeError("candidate disposition requires a DecisionOutcome")
        features = outcome.features_snapshot
        if type(features) is not DecisionFeatures:
            raise TypeError(
                "candidate disposition requires an exact DecisionFeatures snapshot"
            )
        if not isinstance(outcome.decision, Decision):
            raise TypeError("candidate disposition Decision is invalid")
        if not features.contract_passed or not features.verification_passed:
            raise CandidateDispositionError(
                "candidate disposition requires a post-Verification candidate"
            )

        try:
            stage = ExperimentStage(features.stage)
        except (TypeError, ValueError) as exc:
            raise CandidateDispositionError(
                "candidate disposition Protocol stage is invalid"
            ) from exc

        raw_gate = features.protocol_gate_outcome
        if raw_gate is None:
            gate_outcome = None
        else:
            if not isinstance(raw_gate, str):
                raise CandidateDispositionError(
                    "candidate disposition Protocol gate is invalid"
                )
            try:
                gate_outcome = ProtocolGateOutcome(raw_gate)
            except ValueError as exc:
                raise CandidateDispositionError(
                    "candidate disposition Protocol gate is invalid"
                ) from exc

        reason_codes = outcome.reason_codes
        if not isinstance(reason_codes, tuple) or not reason_codes:
            raise CandidateDispositionError(
                "candidate disposition Decision reason codes are invalid"
            )
        if any(
            not isinstance(code, str) or not code or code != code.strip()
            for code in reason_codes
        ):
            raise CandidateDispositionError(
                "candidate disposition Decision reason codes are invalid"
            )

        candidate_failed_pairs = _failure_count(
            features.candidate_failed_pairs,
            label="candidate",
        )
        champion_failed_pairs = _failure_count(
            features.champion_failed_pairs,
            label="champion",
        )
        return cls(
            _token=_FACT_CONSTRUCTION_TOKEN,
            decision=outcome.decision,
            stage=stage,
            gate_outcome=gate_outcome,
            decision_reason_codes=reason_codes,
            candidate_failed_pairs=candidate_failed_pairs,
            champion_failed_pairs=champion_failed_pairs,
        )


@dataclass(frozen=True, init=False)
class CandidateDispositionPlan:
    """Immutable side-effect-free ownership plan for D2 to consume later."""

    facts: _CandidateDispositionFacts
    disposition: CandidateDisposition
    hypothesis_status: CandidateHypothesisStatus
    rule: CandidateDispositionRule

    def __init__(
        self,
        *,
        _token: object,
        facts: _CandidateDispositionFacts,
        disposition: CandidateDisposition,
        hypothesis_status: CandidateHypothesisStatus,
        rule: CandidateDispositionRule,
    ) -> None:
        if _token is not _PLAN_CONSTRUCTION_TOKEN:
            raise TypeError(
                "candidate disposition plans must come from CandidateDispositionMapper"
            )
        object.__setattr__(self, "facts", facts)
        object.__setattr__(self, "disposition", disposition)
        object.__setattr__(self, "hypothesis_status", hypothesis_status)
        object.__setattr__(self, "rule", rule)


_EXACT_REUSE_INPUTS: Final[
    frozenset[tuple[ExperimentStage, Decision, ProtocolGateOutcome]]
] = frozenset(
    {
        (
            ExperimentStage.SCREENING,
            Decision.EXPAND_SCREENING,
            ProtocolGateOutcome.EXPAND,
        ),
        (
            ExperimentStage.SCREENING,
            Decision.QUEUE_VALIDATE,
            ProtocolGateOutcome.PASS,
        ),
        (
            ExperimentStage.VALIDATION,
            Decision.EXPAND_VALIDATION,
            ProtocolGateOutcome.EXPAND,
        ),
        (
            ExperimentStage.VALIDATION,
            Decision.QUEUE_FROZEN,
            ProtocolGateOutcome.PASS,
        ),
    }
)


class CandidateDispositionMapper:
    """Map one immutable DecisionOutcome through the frozen D1 truth table."""

    @staticmethod
    def map(outcome: DecisionOutcome) -> CandidateDispositionPlan:
        facts = _CandidateDispositionFacts.from_decision_outcome(outcome)
        return _map_facts(facts)


def _map_facts(facts: _CandidateDispositionFacts) -> CandidateDispositionPlan:
    decision = facts.decision
    gate = facts.gate_outcome

    if decision is Decision.VALIDATION_REPAIR_REQUIRED:
        raise CandidateDispositionError(
            "VALIDATION_REPAIR_REQUIRED is legacy-only and has no D1 disposition"
        )

    # A post-Verification hard-safety abandon is terminal even when no usable
    # Protocol gate exists or the safety decision overrides another gate.
    if decision is Decision.ABANDON:
        return _plan(
            facts,
            CandidateDisposition.REJECT_TERMINAL,
            CandidateHypothesisStatus.REJECTED,
            CandidateDispositionRule.TERMINAL_REJECT,
        )

    if gate is None:
        raise _unsupported(facts)

    if (facts.stage, decision, gate) in _EXACT_REUSE_INPUTS:
        return _plan(
            facts,
            CandidateDisposition.EXACT_REUSE,
            CandidateHypothesisStatus.ADVANCED,
            CandidateDispositionRule.EXACT_STAGE_REUSE,
        )

    if decision is Decision.CONTINUE_EXPLORE:
        if gate is ProtocolGateOutcome.FAIL:
            return _plan(
                facts,
                CandidateDisposition.REJECT_TO_CODE_PARENT,
                CandidateHypothesisStatus.REJECTED,
                CandidateDispositionRule.PROTOCOL_FAIL_REJECT,
            )
        if gate in {
            ProtocolGateOutcome.UNCLEAR,
            ProtocolGateOutcome.CONTINUE,
        }:
            return _plan(
                facts,
                CandidateDisposition.PROVISIONAL_HEAD,
                CandidateHypothesisStatus.PROVISIONAL,
                CandidateDispositionRule.PROTOCOL_PROVISIONAL,
            )
        if gate in {ProtocolGateOutcome.PASS, ProtocolGateOutcome.EXPAND}:
            if _is_exact_partial_champion_exception(facts):
                return _plan(
                    facts,
                    CandidateDisposition.PROVISIONAL_HEAD,
                    CandidateHypothesisStatus.PROVISIONAL,
                    CandidateDispositionRule.PARTIAL_CHAMPION_PROVISIONAL,
                )
            raise _unsupported(facts)

    if (
        facts.stage is ExperimentStage.FROZEN
        and decision is Decision.PROMOTE
        and gate is ProtocolGateOutcome.PASS
    ):
        return _plan(
            facts,
            CandidateDisposition.PROMOTE_EXACT,
            CandidateHypothesisStatus.PROMOTED,
            CandidateDispositionRule.FROZEN_PROMOTION,
        )

    raise _unsupported(facts)


def _is_exact_partial_champion_exception(facts: _CandidateDispositionFacts) -> bool:
    return (
        facts.stage is ExperimentStage.SCREENING
        and facts.decision_reason_codes == _PARTIAL_CHAMPION_REASON
        and facts.candidate_failed_pairs == 0
        and facts.champion_failed_pairs > 0
    )


def _failure_count(value: object, *, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise CandidateDispositionError(
            f"candidate disposition {label} failure count is invalid"
        )
    return value


def _plan(
    facts: _CandidateDispositionFacts,
    disposition: CandidateDisposition,
    hypothesis_status: CandidateHypothesisStatus,
    rule: CandidateDispositionRule,
) -> CandidateDispositionPlan:
    return CandidateDispositionPlan(
        _token=_PLAN_CONSTRUCTION_TOKEN,
        facts=facts,
        disposition=disposition,
        hypothesis_status=hypothesis_status,
        rule=rule,
    )


def _unsupported(facts: _CandidateDispositionFacts) -> CandidateDispositionError:
    gate = facts.gate_outcome.value if facts.gate_outcome is not None else "none"
    return CandidateDispositionError(
        "unsupported candidate disposition input: "
        f"stage={facts.stage.value} decision={facts.decision.value} gate={gate}"
    )
