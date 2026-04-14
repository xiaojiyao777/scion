from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal

from scion.core.models import FailureEvent, Branch


@dataclass
class EscalationConfig:
    """Thresholds for streak-based escalation in FailureRouter."""
    light_streak_infra_suspected: int = 3   # light failures → infra_suspected
    heavy_streak_abandon_fast: int = 2       # heavy failures → abandon_fast
    infra_loop_streak: int = 5              # infra_loop stagnation threshold


@dataclass
class RetryConfig:
    max_llm_retries: int = 3
    max_infra_retries: int = 5
    escalation: EscalationConfig = field(default_factory=EscalationConfig)


@dataclass(frozen=True)
class FailureAction:
    action: Literal["retry_llm", "retry_infra", "discard", "abandon",
                    "infra_suspected", "abandon_fast"]
    consumes_budget: bool
    writes_hypothesis_memory: bool
    max_retries_remaining: int
    escalation_level: int = 0  # 0=normal, 1=warning prompt, 2=strong warning


# Failure category → severity mapping
_LIGHT_CATS   = frozenset({"proposal", "contract", "verification_light"})
_HEAVY_CATS   = frozenset({"verification_heavy", "evaluation"})
_SEARCH_CATS  = frozenset({"search_guidance"})  # C10_novelty etc: retry_llm, never infra streak


class FailureRouter:
    """
    Routes failure events to appropriate actions based on failure category.

    Four-tier classification:
      proposal/contract    → retry_llm (no budget cost)
      verification_light   → retry_llm (no budget cost); discard if exhausted
      verification_heavy   → discard (consumes budget, records hypothesis memory)
      infra                → retry_infra (no budget cost)
      evaluation           → discard (consumes budget, records hypothesis memory)

    Streak-based escalation (stateful, requires caller to pass streak/total):
      light category streak >= light_streak_infra_suspected → infra_suspected
      heavy category streak >= heavy_streak_abandon_fast    → abandon_fast
      retry_llm: escalation_level reflects streak (0/1/2)
    """

    def __init__(self, retry_config: RetryConfig | None = None) -> None:
        self.retry_config = retry_config or RetryConfig()

    def route(
        self,
        failure: FailureEvent,
        branch: Branch,
        streak: int = 0,
        total: int = 0,
    ) -> FailureAction:
        cat = failure.category
        esc = self.retry_config.escalation

        # ----------------------------------------------------------------
        # search_guidance (C10_novelty etc): always retry_llm, never infra streak
        # ----------------------------------------------------------------
        if cat in _SEARCH_CATS:
            return FailureAction(
                action="retry_llm",
                consumes_budget=False,
                writes_hypothesis_memory=False,
                max_retries_remaining=self.retry_config.max_llm_retries,
                escalation_level=0,
            )

        # ----------------------------------------------------------------
        # Streak-based escalation (overrides normal routing)
        # ----------------------------------------------------------------
        if cat in _LIGHT_CATS and streak >= esc.light_streak_infra_suspected:
            return FailureAction(
                action="infra_suspected",
                consumes_budget=False,
                writes_hypothesis_memory=False,
                max_retries_remaining=0,
                escalation_level=2,
            )

        if cat in _HEAVY_CATS and streak >= esc.heavy_streak_abandon_fast:
            return FailureAction(
                action="abandon_fast",
                consumes_budget=False,
                writes_hypothesis_memory=True,
                max_retries_remaining=0,
                escalation_level=2,
            )

        # ----------------------------------------------------------------
        # Normal routing (unchanged logic, with escalation_level tagging)
        # ----------------------------------------------------------------
        if cat in ("proposal", "contract"):
            remaining = max(
                0, self.retry_config.max_llm_retries - branch.retry_count
            )
            if remaining > 0:
                return FailureAction(
                    action="retry_llm",
                    consumes_budget=False,
                    writes_hypothesis_memory=False,
                    max_retries_remaining=remaining,
                    escalation_level=min(2, streak),
                )
            return FailureAction(
                action="discard",
                consumes_budget=False,
                writes_hypothesis_memory=False,
                max_retries_remaining=0,
            )

        elif cat == "verification_light":
            remaining = max(
                0, self.retry_config.max_llm_retries - branch.retry_count
            )
            if remaining > 0:
                return FailureAction(
                    action="retry_llm",
                    consumes_budget=False,
                    writes_hypothesis_memory=False,
                    max_retries_remaining=remaining,
                    escalation_level=min(2, streak),
                )
            return FailureAction(
                action="discard",
                consumes_budget=True,
                writes_hypothesis_memory=True,
                max_retries_remaining=0,
            )

        elif cat == "verification_heavy":
            return FailureAction(
                action="discard",
                consumes_budget=True,
                writes_hypothesis_memory=True,
                max_retries_remaining=0,
            )

        elif cat == "infra":
            remaining = max(
                0, self.retry_config.max_infra_retries - branch.retry_count
            )
            return FailureAction(
                action="retry_infra",
                consumes_budget=False,
                writes_hypothesis_memory=False,
                max_retries_remaining=remaining,
            )

        elif cat == "evaluation":
            return FailureAction(
                action="discard",
                consumes_budget=True,
                writes_hypothesis_memory=True,
                max_retries_remaining=0,
            )

        # Unknown category — treat as heavy failure
        return FailureAction(
            action="discard",
            consumes_budget=True,
            writes_hypothesis_memory=True,
            max_retries_remaining=0,
        )
