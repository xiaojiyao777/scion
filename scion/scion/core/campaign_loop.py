"""Direct-only outer campaign loop lifecycle."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

from scion.core.execution_outcome import ExecutionOutcome
from scion.core.run_validity import failure_category_for_run_validity
from scion.core.step_result import StepResult

@dataclass
class CampaignLoop:
    """Run one scheduled call at a time until formal evaluated rounds complete."""

    write_status: Callable[..., None]
    drain_weight_opt_events: Callable[[], None]
    should_stop: Callable[[], bool]
    get_last_stop_reason: Callable[[], Optional[str]]
    set_last_stop_reason: Callable[[Optional[str]], None]
    run_one_step: Callable[[], StepResult]
    write_campaign_summary: Callable[[], None]
    get_final_wait_timeout: Callable[[], float]
    wait_weight_opt_all: Callable[[float], None]

    def run(self, requested_rounds: int) -> None:
        """Target formal evaluated rounds without retrying a provider outcome."""

        requested_rounds = max(1, int(requested_rounds))
        evaluated_rounds = 0
        scheduled_calls = 0
        formal_screened_candidates = 0
        protocol_evaluated_candidates = 0
        protocol_stage_counts = {"screening": 0, "validation": 0, "frozen": 0}
        failure_category_counts: dict[str, int] = {}
        last_failure_category = ""
        final_reason: str | None = None

        def loop_status() -> dict[str, Any]:
            completed = evaluated_rounds >= requested_rounds
            return {
                "schema_version": "scion.campaign_loop.direct_v1",
                "requested_rounds": requested_rounds,
                "effective_rounds_completed": evaluated_rounds,
                "completed_requested_rounds": completed,
                "effective_rounds_completed_semantics": (
                    "typed formal protocol evaluated rounds"
                ),
                "scheduled_calls": scheduled_calls,
                "campaign_steps": scheduled_calls,
                "loop_steps": scheduled_calls,
                "formal_screened_candidates": formal_screened_candidates,
                "protocol_evaluated_candidates": protocol_evaluated_candidates,
                "protocol_metric_results": protocol_evaluated_candidates,
                "protocol_stage_counts": dict(protocol_stage_counts),
                "failure_categories": dict(failure_category_counts),
                "last_failure_category": last_failure_category,
                "round_target_policy": "formal_evaluated_only",
            }

        self.write_status(loop_status=loop_status())
        while evaluated_rounds < requested_rounds:
            self.drain_weight_opt_events()
            if self.should_stop():
                final_reason = self.get_last_stop_reason() or "termination condition met"
                self.write_status(stopped_reason=final_reason, loop_status=loop_status())
                break

            self.write_status(loop_status=loop_status())
            result = self.run_one_step()
            scheduled_calls += 1
            outcome = getattr(result, "execution_outcome", None)

            failure_category = _result_failure_category(result)
            if failure_category:
                last_failure_category = failure_category
                failure_category_counts[failure_category] = (
                    failure_category_counts.get(failure_category, 0) + 1
                )

            if outcome is not ExecutionOutcome.EVALUATED:
                final_reason = (
                    f"execution_{outcome.value}"
                    if isinstance(outcome, ExecutionOutcome)
                    else "execution_outcome_missing"
                )
                self.write_status(
                    last_result=result,
                    stopped_reason=final_reason,
                    loop_status=loop_status(),
                )
                break

            protocol_stage = _protocol_stage_for_result(result)
            if not protocol_stage:
                final_reason = "evaluated_without_formal_protocol_result"
                self.write_status(
                    last_result=result,
                    stopped_reason=final_reason,
                    loop_status=loop_status(),
                )
                break

            evaluated_rounds += 1
            protocol_evaluated_candidates += 1
            protocol_stage_counts[protocol_stage] += 1
            if _is_formal_screened_candidate_result(result, protocol_stage):
                formal_screened_candidates += 1

            self.write_status(last_result=result, loop_status=loop_status())
            if result.stopped:
                final_reason = result.reason or "stopped"
                break

        if final_reason is None:
            final_reason = "requested_rounds_completed"
        self.set_last_stop_reason(final_reason)
        self.write_campaign_summary()
        self.wait_weight_opt_all(self.get_final_wait_timeout())
        self.drain_weight_opt_events()
        self.write_status(stopped_reason=final_reason, loop_status=loop_status())
        self.write_campaign_summary()
        self.write_status(stopped_reason=final_reason, loop_status=loop_status())


def _attempt_kind(result: StepResult) -> str:
    """Expose the explicit result kind without inferring retry control from prose."""

    kind = str(getattr(result, "attempt_kind", "") or "")
    return kind or "other"


def _protocol_stage_for_result(result: StepResult) -> str:
    explicit_stage = str(getattr(result, "protocol_stage", "") or "")
    if (
        explicit_stage in {"screening", "validation", "frozen"}
        and bool(getattr(result, "formal_protocol_evaluated", False))
    ):
        return explicit_stage
    return ""


def _is_formal_screened_candidate_result(result: StepResult, stage: str) -> bool:
    return stage == "screening" and bool(
        getattr(result, "screened_experiment_effective", False)
    )


def _result_failure_category(result: StepResult) -> str:
    if not getattr(result, "failure_stage", None) and not getattr(
        result,
        "failure_detail",
        None,
    ):
        return ""
    return failure_category_for_run_validity(
        getattr(result, "failure_detail", None),
        category=getattr(result, "failure_category", None),
        failure_stage=getattr(result, "failure_stage", None),
    )
