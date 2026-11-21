"""Direct-only outer campaign loop."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Callable, Optional

from scion.core.execution_outcome import ExecutionOutcome
from scion.core.run_validity import classify_run_validity
from scion.core.step_result import StepResult
from scion.core.research_lifecycle import validate_run_intent


@dataclass(frozen=True)
class CampaignRunResult:
    """One in-process terminal value for a campaign invocation."""

    requested_rounds: int | None
    evaluated_rounds: int
    scheduled_calls: int
    stop_reason: str
    failure_categories: dict[str, int]
    protocol_stage_counts: dict[str, int]
    formal_screened_candidates: int
    execution_outcome_counts: dict[str, int]
    unknown_outcome_count: int
    last_execution_outcome: dict[str, Any] | None
    terminal_exception: dict[str, str] | None = None
    run_intent: str = "formal_target"
    formal_stage_limit: int | None = None
    conclusion_ref: str | None = None
    unexecuted_work: list[dict[str, Any]] = field(default_factory=list)

    @property
    def completed(self) -> bool:
        if self.run_intent == "investigation":
            return self.stop_reason in {"research_concluded", "formal_stage_limit_reached"}
        return self.evaluated_rounds >= self.requested_rounds

    @classmethod
    def empty(cls, requested_rounds: int | None, *, run_intent="formal_target", formal_stage_limit=None) -> "CampaignRunResult":
        return cls(
            requested_rounds=max(1, int(requested_rounds)) if run_intent == "formal_target" else None,
            run_intent=run_intent, formal_stage_limit=formal_stage_limit,
            evaluated_rounds=0,
            scheduled_calls=0,
            stop_reason="",
            failure_categories={},
            protocol_stage_counts={"screening": 0, "validation": 0, "frozen": 0},
            formal_screened_candidates=0,
            execution_outcome_counts={outcome.value: 0 for outcome in ExecutionOutcome
                if run_intent == "investigation" or outcome is not ExecutionOutcome.RESEARCH_CONCLUDED},
            unknown_outcome_count=0,
            last_execution_outcome=None,
        )

    def terminalized(
        self,
        reason: str,
        *,
        exception: BaseException | None = None,
        unresolved_attempt: bool = False,
        interrupted: bool = False,
    ) -> "CampaignRunResult":
        outcome_counts = dict(self.execution_outcome_counts)
        unknown = self.unknown_outcome_count
        last = self.last_execution_outcome
        if interrupted:
            outcome_counts[ExecutionOutcome.INTERRUPTED.value] += 1
            last = {
                "outcome": ExecutionOutcome.INTERRUPTED.value,
                "reason_code": (
                    "OUTER_HARDWALL_EXCEEDED"
                    if reason == "OUTER_HARDWALL_EXCEEDED"
                    else "EXTERNAL_STOP_REQUESTED"
                ),
                "stage": "campaign",
            }
        elif unresolved_attempt:
            unknown += 1
        terminal_exception = None
        if exception is not None:
            terminal_exception = {
                "reason": reason,
                "type": type(exception).__name__,
                "message": str(exception),
            }
        return replace(
            self,
            scheduled_calls=(
                self.scheduled_calls + 1
                if interrupted or unresolved_attempt
                else self.scheduled_calls
            ),
            stop_reason=reason,
            execution_outcome_counts=outcome_counts,
            unknown_outcome_count=unknown,
            last_execution_outcome=(dict(last) if last is not None else None),
            terminal_exception=terminal_exception,
        )

    def to_projection(self) -> dict[str, Any]:
        """Return the sole ordinary run-state projection used by reporters."""

        terminal = bool(self.stop_reason)
        value: dict[str, Any] = {
            "status": (
                "completed"
                if terminal and self.completed
                else "stopped"
                if terminal
                else "running"
            ),
            "requested_rounds": self.requested_rounds,
            "evaluated_rounds": self.evaluated_rounds,
            "scheduled_calls": self.scheduled_calls,
            "formal_screened_candidates": self.formal_screened_candidates,
            "protocol_stage_counts": dict(self.protocol_stage_counts),
            "failure_categories": dict(self.failure_categories),
            "execution_outcome_counts": dict(self.execution_outcome_counts),
            "unknown_outcome_count": self.unknown_outcome_count,
            "last_execution_outcome": _last_outcome_projection(
                self.last_execution_outcome
            ),
            "run_validity": classify_run_validity(
                terminal=terminal,
                completed=self.completed if self.run_intent == "formal_target" else False,
                execution_outcome_counts=self.execution_outcome_counts,
            ),
        }
        if self.stop_reason:
            value["stop_reason"] = self.stop_reason
        if self.run_intent == "investigation":
            value.update(run_intent=self.run_intent, formal_stage_limit=self.formal_stage_limit,
                         conclusion_ref=self.conclusion_ref, unexecuted_work=list(self.unexecuted_work))
        if self.terminal_exception is not None:
            value["terminal_exception"] = dict(self.terminal_exception)
        return value


@dataclass
class CampaignLoop:
    """Run scheduled calls under the operator's explicit invocation intent."""

    write_status: Callable[..., None]
    drain_weight_opt_events: Callable[[], None]
    should_stop: Callable[[], bool]
    get_last_stop_reason: Callable[[], Optional[str]]
    set_last_stop_reason: Callable[[Optional[str]], None]
    run_one_step: Callable[[], StepResult]
    write_terminal_artifacts: Callable[[CampaignRunResult], None]
    get_final_wait_timeout: Callable[[], float]
    wait_weight_opt_all: Callable[[float], None]
    get_termination_outcome: Callable[[], Any] = lambda: None
    get_conclusion_ref: Callable[[], str | None] = lambda: None
    get_unexecuted_work: Callable[[], list[dict[str, Any]]] = lambda: []
    current_result: CampaignRunResult | None = field(init=False, default=None)
    call_in_progress: bool = field(init=False, default=False)

    def run(self, requested_rounds: int | None = None, *, run_intent="formal_target", formal_stage_limit=None) -> CampaignRunResult:
        """Apply the formal target or investigation ceiling and typed conclusion."""

        validate_run_intent(run_intent, formal_stage_limit)
        investigation = run_intent == "investigation"
        if investigation and requested_rounds is not None:
            raise ValueError("investigation does not accept requested_rounds")
        requested_rounds = None if investigation else max(1, int(requested_rounds))
        self.current_result = None
        self.call_in_progress = False
        evaluated_rounds = 0
        scheduled_calls = 0
        formal_screened_candidates = 0
        protocol_stage_counts = {"screening": 0, "validation": 0, "frozen": 0}
        failure_category_counts: dict[str, int] = {}
        execution_outcome_counts = {outcome.value: 0 for outcome in ExecutionOutcome
            if investigation or outcome is not ExecutionOutcome.RESEARCH_CONCLUDED}
        unknown_outcome_count = 0
        last_execution_outcome: dict[str, Any] | None = None
        final_reason: str | None = None
        conclusion_ref: str | None = None

        def snapshot(*, stop_reason: str = "") -> CampaignRunResult:
            value = CampaignRunResult(
                requested_rounds=requested_rounds,
                run_intent=run_intent, formal_stage_limit=formal_stage_limit,
                conclusion_ref=(self.get_conclusion_ref() or conclusion_ref) if investigation else None,
                unexecuted_work=self.get_unexecuted_work() if investigation and stop_reason else [],
                evaluated_rounds=evaluated_rounds,
                scheduled_calls=scheduled_calls,
                stop_reason=stop_reason,
                failure_categories=dict(failure_category_counts),
                protocol_stage_counts=dict(protocol_stage_counts),
                formal_screened_candidates=formal_screened_candidates,
                execution_outcome_counts=dict(execution_outcome_counts),
                unknown_outcome_count=unknown_outcome_count,
                last_execution_outcome=(
                    dict(last_execution_outcome)
                    if last_execution_outcome is not None
                    else None
                ),
            )
            self.current_result = value
            return value

        self.write_status(run_result=snapshot())
        def terminal_fault():
            nonlocal last_execution_outcome
            record = self.get_termination_outcome() if investigation else None
            if record is not None:
                execution_outcome_counts[record.outcome.value] += 1
                last_execution_outcome = {"outcome": record.outcome.value, "reason_code": record.reason_code,
                                          "stage": "campaign"}
                return f"execution_{record.outcome.value}"
            return None

        while (investigation and (formal_stage_limit == 0 or evaluated_rounds < formal_stage_limit)) or (
                not investigation and evaluated_rounds < requested_rounds):
            self.drain_weight_opt_events()
            fault = terminal_fault()
            if fault:
                final_reason = fault
                break
            if self.should_stop():
                final_reason = (
                    self.get_last_stop_reason() or "termination condition met"
                )
                current = snapshot(stop_reason=final_reason)
                self.write_status(
                    run_result=current,
                )
                break

            self.write_status(run_result=snapshot())
            self.call_in_progress = True
            snapshot()
            result = self.run_one_step()
            self.call_in_progress = False
            outcome_record = result.execution_outcome
            outcome = outcome_record.outcome if outcome_record is not None else None
            if outcome_record is None:
                self.write_status(
                    last_result=result,
                    run_result=snapshot(),
                )
                continue
            if _is_non_attempt_reconcile_housekeeping(result):
                self.write_status(
                    last_result=result,
                    run_result=snapshot(),
                )
                continue

            scheduled_calls += 1
            execution_outcome_counts[outcome_record.outcome.value] = execution_outcome_counts.get(outcome_record.outcome.value, 0) + 1
            last_execution_outcome = {
                "outcome": outcome_record.outcome.value,
                "reason_code": outcome_record.reason_code,
            }
            stage = outcome_record.provenance.get("stage")
            if isinstance(stage, str) and stage.strip():
                last_execution_outcome["stage"] = stage.strip()

            failure_category = _result_failure_category(result)
            if failure_category:
                failure_category_counts[failure_category] = (
                    failure_category_counts.get(failure_category, 0) + 1
                )

            if outcome is ExecutionOutcome.RESEARCH_REJECTED:
                self.write_status(
                    last_result=result,
                    run_result=snapshot(),
                )
                continue

            if outcome is ExecutionOutcome.RESEARCH_CONCLUDED:
                ref = outcome_record.provenance.get("conclusion_ref")
                conclusion_ref = ref if isinstance(ref, str) else None
                final_reason = ("research_concluded" if investigation and isinstance(ref, str) and ref
                    and outcome_record.provenance.get("stage") == "proposal_hypothesis"
                    else "unexpected_research_conclusion")
                break

            if _is_cleaned_stale_explore_attempt(result):
                self.write_status(
                    last_result=result,
                    run_result=snapshot(),
                )
                continue

            if outcome is not ExecutionOutcome.EVALUATED:
                final_reason = (
                    f"execution_{outcome.value}"
                    if isinstance(outcome, ExecutionOutcome)
                    else "execution_outcome_missing"
                )
                self.write_status(
                    last_result=result,
                    run_result=snapshot(stop_reason=final_reason),
                )
                break

            protocol_stage = _protocol_stage_for_result(result)
            if not protocol_stage:
                final_reason = "evaluated_without_formal_protocol_result"
                self.write_status(
                    last_result=result,
                    run_result=snapshot(stop_reason=final_reason),
                )
                break

            evaluated_rounds += 1
            protocol_stage_counts[protocol_stage] += 1
            if _is_formal_screened_candidate_result(result, protocol_stage):
                formal_screened_candidates += 1

            self.write_status(
                last_result=result,
                run_result=snapshot(),
            )
            if result.stopped:
                final_reason = result.reason or "stopped"
                break

        if final_reason is None:
            final_reason = "formal_stage_limit_reached" if investigation else "requested_rounds_completed"
        self.set_last_stop_reason(final_reason)
        self.wait_weight_opt_all(self.get_final_wait_timeout())
        self.drain_weight_opt_events()
        if investigation and final_reason in {"research_concluded", "formal_stage_limit_reached"}:
            final_reason = terminal_fault() or final_reason
            self.set_last_stop_reason(final_reason)
        terminal = snapshot(stop_reason=final_reason)
        self.write_terminal_artifacts(terminal)
        return terminal


def _last_outcome_projection(
    value: dict[str, Any] | None,
) -> dict[str, str] | None:
    if value is None:
        return None
    projection = {
        "outcome": str(value.get("outcome") or ""),
        "reason_code": str(value.get("reason_code") or ""),
    }
    stage = value.get("stage")
    if isinstance(stage, str) and stage.strip():
        projection["stage"] = stage.strip()
    return projection


def _protocol_stage_for_result(result: StepResult) -> str:
    protocol_result = result.protocol_result
    if protocol_result is None or protocol_result.stats is None:
        return ""
    stage = str(getattr(protocol_result.stage, "value", protocol_result.stage) or "")
    return stage if stage in {"screening", "validation", "frozen"} else ""


def _is_formal_screened_candidate_result(result: StepResult, stage: str) -> bool:
    return stage == "screening" and result.protocol_result is not None


def _is_non_attempt_reconcile_housekeeping(result: StepResult) -> bool:
    record = result.execution_outcome
    return bool(
        result.action == "reconcile"
        and record is not None
        and record.outcome is ExecutionOutcome.NOT_EVALUATED
        and record.reason_code == "RECONCILE_NO_ACCEPTED_CHANGES"
    )


def _is_cleaned_stale_explore_attempt(result: StepResult) -> bool:
    record = result.execution_outcome
    return bool(
        record is not None
        and record.outcome is ExecutionOutcome.NOT_EVALUATED
        and record.reason_code == "BRANCH_STALE_DURING_EXPLORE"
    )


def _result_failure_category(result: StepResult) -> str:
    if not getattr(result, "failure_stage", None) and not getattr(
        result,
        "failure_detail",
        None,
    ):
        return ""
    if result.execution_outcome is not None:
        outcome = result.execution_outcome.outcome
        if outcome not in {
            ExecutionOutcome.EVALUATED,
            ExecutionOutcome.RESEARCH_REJECTED,
        }:
            return outcome.value
    return str(
        getattr(result, "failure_category", None)
        or getattr(result, "failure_stage", None)
        or ""
    ).strip()
