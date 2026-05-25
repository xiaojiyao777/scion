"""Outer campaign loop lifecycle."""
from __future__ import annotations

import logging
import os
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
    proposal_quality_loop_limit: int | None = None
    proposal_attempt_limit: int | None = None
    get_proposal_attempts: Callable[[], int] | None = None

    def run(self, max_rounds: int = 1000) -> None:
        """Run the campaign until a termination condition is met."""
        final_reason: str | None = None
        counted_rounds = 0
        loop_steps = 0
        bad_proposal_attempts = 0
        proposal_quality_blocked_attempts = 0
        telemetry_repairable_attempts = 0
        validation_repair_required_attempts = 0
        same_family_retry_attempts = 0
        requested_rounds = max(1, int(max_rounds))
        proposal_quality_loop_limit = _proposal_quality_loop_limit(
            requested_rounds,
            configured=self.proposal_quality_loop_limit,
        )
        attempt_limit = _proposal_attempt_limit(
            requested_rounds,
            configured=self.proposal_attempt_limit,
        )
        bad_proposal_limit = requested_rounds * 5 + 10
        telemetry_repairable_limit = requested_rounds * 2 + 4
        validation_repair_required_limit = requested_rounds + 2
        same_family_retry_limit = requested_rounds + 4
        # Non-round steps such as proposal blocks and telemetry-repairable
        # formal runs do not consume the screened-round budget.  Proposal
        # attempts still spend user-visible LLM budget, so they have a hard
        # cap independent of category-specific loop limits.
        loop_step_limit = (
            requested_rounds
            + proposal_quality_loop_limit
            + bad_proposal_limit
            + telemetry_repairable_limit
            + validation_repair_required_limit
            + same_family_retry_limit
        )

        def proposal_attempts_consumed() -> int:
            if self.get_proposal_attempts is None:
                return max(0, int(loop_steps))
            try:
                return max(0, int(self.get_proposal_attempts()))
            except Exception as exc:  # pragma: no cover - defensive status path
                logger.debug("Failed to read proposal attempt count: %s", exc)
                return max(0, int(loop_steps))

        def loop_status() -> dict[str, int]:
            return _campaign_loop_status(
                requested_rounds=requested_rounds,
                attempt_limit=attempt_limit,
                attempts=proposal_attempts_consumed(),
                loop_steps=loop_steps,
                loop_step_limit=loop_step_limit,
                counted_rounds=counted_rounds,
                telemetry_repairable_attempts=telemetry_repairable_attempts,
                validation_repair_required_attempts=(
                    validation_repair_required_attempts
                ),
                proposal_quality_loop_limit=proposal_quality_loop_limit,
                proposal_quality_blocked_attempts=proposal_quality_blocked_attempts,
            )

        self.write_status(loop_status=loop_status())
        while counted_rounds < requested_rounds:
            if proposal_attempts_consumed() >= attempt_limit:
                final_reason = "proposal_attempt_limit_exhausted"
                self.write_status(
                    stopped_reason=final_reason,
                    loop_status=loop_status(),
                )
                break
            if loop_steps >= loop_step_limit:
                final_reason = "attempt_limit_exhausted"
                self.write_status(
                    stopped_reason=final_reason,
                    loop_status=loop_status(),
                )
                break

            loop_steps += 1
            self.drain_weight_opt_events()
            if self.should_stop():
                final_reason = self.get_last_stop_reason() or "termination condition met"
                logger.info("Campaign terminated.")
                self.write_status(
                    stopped_reason=final_reason,
                    loop_status=loop_status(),
                )
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
                self.write_status(
                    stopped_reason="circuit_breaker",
                    loop_status=loop_status(),
                )
                break

            self.write_status(loop_status=loop_status())
            result = self.run_one_step()
            if getattr(result, "counts_toward_max_rounds", True):
                counted_rounds += 1
            else:
                kind = _attempt_kind(result)
                if kind == "validation_repair_required":
                    validation_repair_required_attempts += 1
                    if (
                        validation_repair_required_attempts
                        >= validation_repair_required_limit
                    ):
                        final_reason = "validation_repair_required_budget_exhausted"
                elif kind == "telemetry_repairable":
                    telemetry_repairable_attempts += 1
                    if telemetry_repairable_attempts >= telemetry_repairable_limit:
                        final_reason = "telemetry_repairable_budget_exhausted"
                elif kind == "same_family_retry":
                    same_family_retry_attempts += 1
                    if same_family_retry_attempts >= same_family_retry_limit:
                        final_reason = "same_family_retry_budget_exhausted"
                elif kind == "proposal_block":
                    proposal_quality_blocked_attempts += 1
                    if (
                        proposal_quality_blocked_attempts
                        >= proposal_quality_loop_limit
                    ):
                        final_reason = "proposal_quality_loop"
                else:
                    bad_proposal_attempts += 1
                    if bad_proposal_attempts >= bad_proposal_limit:
                        final_reason = "bad_proposal_budget_exhausted"
            if final_reason == "proposal_quality_loop":
                result.stopped = True
            if (
                final_reason is None
                and counted_rounds < requested_rounds
                and proposal_attempts_consumed() >= attempt_limit
            ):
                final_reason = "proposal_attempt_limit_exhausted"
            self.write_status(
                last_result=result,
                loop_status=loop_status(),
            )
            if result.stopped:
                final_reason = final_reason or result.reason or "stopped"
                break
            if final_reason is not None:
                break

            self.run_stagnation_check()
            self.check_soft_stagnation()
        if final_reason is None and counted_rounds >= requested_rounds:
            final_reason = "max_rounds_exhausted"
        elif final_reason is None and counted_rounds == 0:
            final_reason = "no_effective_round_loop"
        elif final_reason is None:
            final_reason = "attempt_limit_exhausted"

        self.set_last_stop_reason(final_reason)
        # A max-rounds stop closes this campaign invocation, not the research
        # branch lifecycle.  Keep active continue_explore/validation branches
        # resumable; status.json/campaign_summary carry the invocation stop
        # reason for audit.
        self.write_campaign_summary()
        final_wait_timeout = self.get_final_wait_timeout()
        self.wait_weight_opt_all(final_wait_timeout)
        self.drain_weight_opt_events()
        self.write_campaign_summary()
        self.write_status(
            stopped_reason=final_reason or "run_complete",
            loop_status=loop_status(),
        )


def _attempt_kind(result: StepResult) -> str:
    kind = str(getattr(result, "attempt_kind", "") or "")
    if kind and kind != "screening":
        return kind
    reason = str(getattr(result, "reason", "") or "").lower()
    if (
        "telemetry_validation_repairable" in reason
        or "validation_telemetry_repairable" in reason
    ):
        if "validation" in reason:
            return "validation_repair_required"
        return "telemetry_repairable"
    if "same_family" in reason or "semantic retry" in reason:
        return "same_family_retry"
    return "proposal_block"


def _proposal_quality_loop_limit(
    requested_rounds: int,
    *,
    configured: int | None,
) -> int:
    """Return the cumulative pre-screen agent-quality block cap."""
    if configured is not None:
        return max(1, int(configured))
    raw = os.environ.get("SCION_PROPOSAL_QUALITY_LOOP_LIMIT")
    if raw:
        try:
            return max(1, int(raw))
        except ValueError:
            logger.warning(
                "Ignoring invalid SCION_PROPOSAL_QUALITY_LOOP_LIMIT=%r",
                raw,
            )
    rounds = max(1, int(requested_rounds))
    return rounds + max(6, rounds * 2)


def _proposal_attempt_limit(
    requested_rounds: int,
    *,
    configured: int | None,
) -> int:
    """Return the user-visible LLM proposal attempt cap.

    ``--rounds`` is a controlled-run proposal attempt ceiling by default.  The
    explicit CLI/env override remains available for deliberately wider repair
    sweeps, but a short diagnostic run must not launch proposal round N+1.
    """
    if configured is not None:
        return max(1, int(configured))
    raw = os.environ.get("SCION_PROPOSAL_ATTEMPT_LIMIT")
    if raw:
        try:
            return max(1, int(raw))
        except ValueError:
            logger.warning(
                "Ignoring invalid SCION_PROPOSAL_ATTEMPT_LIMIT=%r",
                raw,
            )
    return max(1, int(requested_rounds))


def _campaign_loop_status(
    *,
    requested_rounds: int,
    attempt_limit: int,
    attempts: int,
    loop_steps: int,
    loop_step_limit: int,
    counted_rounds: int,
    telemetry_repairable_attempts: int,
    validation_repair_required_attempts: int,
    proposal_quality_loop_limit: int,
    proposal_quality_blocked_attempts: int,
) -> dict[str, int]:
    attempts_value = max(0, int(attempts))
    effective_rounds = max(0, int(counted_rounds))
    telemetry_diagnostic_attempts = max(
        0,
        int(telemetry_repairable_attempts)
        + int(validation_repair_required_attempts),
    )
    quality_blocks = max(0, int(proposal_quality_blocked_attempts))
    return {
        "requested_rounds": max(1, int(requested_rounds)),
        "attempt_limit": max(0, int(attempt_limit)),
        "proposal_attempt_limit": max(0, int(attempt_limit)),
        "attempts": attempts_value,
        "total_rounds": attempts_value,
        "proposal_attempts": attempts_value,
        "proposal_attempts_consumed": attempts_value,
        "loop_steps": max(0, int(loop_steps)),
        "loop_step_limit": max(0, int(loop_step_limit)),
        "effective_rounds_completed": effective_rounds,
        "telemetry_repairable_attempts": max(
            0,
            int(telemetry_repairable_attempts),
        ),
        "validation_repair_required_attempts": max(
            0,
            int(validation_repair_required_attempts),
        ),
        "telemetry_diagnostic_attempts": telemetry_diagnostic_attempts,
        "proposal_quality_loop_limit": max(1, int(proposal_quality_loop_limit)),
        "proposal_quality_limit": max(1, int(proposal_quality_loop_limit)),
        "proposal_quality_blocks_consumed": quality_blocks,
        "quality_blocks": quality_blocks,
        "blocked_attempts": quality_blocks,
        "proposal_quality_blocks_remaining": max(
            0,
            int(proposal_quality_loop_limit)
            - int(proposal_quality_blocked_attempts),
        ),
    }
