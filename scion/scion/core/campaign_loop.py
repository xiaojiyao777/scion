"""Outer campaign loop lifecycle."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Optional

from scion.core.step_result import StepResult

logger = logging.getLogger(__name__)


@dataclass
class CampaignLoop:
    """Own campaign run/finalization without owning branch-step execution."""

    write_status: Callable[..., None]
    drain_weight_opt_events: Callable[[], None]
    should_stop: Callable[[], bool]
    get_last_stop_reason: Callable[[], Optional[str]]
    set_last_stop_reason: Callable[[Optional[str]], None]
    get_circuit_breaker: Callable[[], Any]
    circuit_breaker_threshold: int
    run_one_step: Callable[[], StepResult]
    run_stagnation_check: Callable[[], None]
    check_soft_stagnation: Callable[[], None]
    write_campaign_summary: Callable[[], None]
    terminalize_active_branches: Callable[[str], None]
    get_final_wait_timeout: Callable[[], float]
    wait_weight_opt_all: Callable[[float], None]

    def run(self, max_rounds: int = 1000) -> None:
        """Run the campaign until a termination condition is met."""
        self.write_status()
        final_reason: str | None = None
        counted_rounds = 0
        attempts = 0
        # Non-round steps such as pending code retries should not consume the
        # exploration round budget, but still need a hard guard against loops.
        attempt_limit = max(1, int(max_rounds)) * 3 + 10
        while counted_rounds < max_rounds and attempts < attempt_limit:
            attempts += 1
            self.drain_weight_opt_events()
            if self.should_stop():
                final_reason = self.get_last_stop_reason() or "termination condition met"
                logger.info("Campaign terminated.")
                self.write_status(stopped_reason=final_reason)
                break

            circuit_breaker = self.get_circuit_breaker()
            if circuit_breaker.is_tripped:
                final_reason = "circuit_breaker"
                logger.critical(
                    "Circuit breaker tripped after %d consecutive LLM failures; "
                    "stopping campaign. Last error: %s",
                    self.circuit_breaker_threshold,
                    circuit_breaker.last_failure_detail,
                )
                self.write_status(stopped_reason="circuit_breaker")
                break

            result = self.run_one_step()
            if getattr(result, "counts_toward_max_rounds", True):
                counted_rounds += 1
            self.write_status(last_result=result)
            if result.stopped:
                final_reason = result.reason or "stopped"
                break

            self.run_stagnation_check()
            self.check_soft_stagnation()
        if final_reason is None and counted_rounds >= max_rounds:
            final_reason = "max_rounds_exhausted"
        elif final_reason is None:
            final_reason = "attempt_limit_exhausted"

        self.set_last_stop_reason(final_reason)
        if final_reason == "max_rounds_exhausted":
            self.terminalize_active_branches("MAX_ROUNDS_EXHAUSTED")
        self.write_campaign_summary()
        final_wait_timeout = self.get_final_wait_timeout()
        self.wait_weight_opt_all(final_wait_timeout)
        self.drain_weight_opt_events()
        self.write_campaign_summary()
        self.write_status(stopped_reason=final_reason or "run_complete")
