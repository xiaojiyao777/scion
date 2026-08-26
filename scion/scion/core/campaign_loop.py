"""Direct-only outer campaign loop."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Callable, Optional

from scion.core.canary_failure import CANARY_FAILURE_CATEGORY_CANDIDATE
from scion.core.execution_outcome import ExecutionOutcome
from scion.core.models import Decision
from scion.core.qualification import (
    QUALIFICATION_BOUNDARY_REACHED,
    QUALIFICATION_NOT_REACHED,
    QualificationOnlyConfig,
    QualificationProgress,
    QualificationProposalBudgetExhausted,
    QualificationRuntime,
)
from scion.core.run_validity import classify_run_validity
from scion.core.step_result import StepResult

_INITIAL_SCREENING_STUDY_DECISIONS = frozenset(
    {
        Decision.CONTINUE_EXPLORE,
        Decision.ABANDON,
        Decision.EXPAND_SCREENING,
        Decision.QUEUE_VALIDATE,
    }
)
_INITIAL_SCREENING_RETIREMENT_CALLBACK_UNAVAILABLE = (
    "initial screening retirement callback is unavailable"
)


@dataclass(frozen=True)
class CampaignRunResult:
    """One in-process terminal value for a campaign invocation."""

    requested_rounds: int
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
    qualification: QualificationProgress | None = None

    @property
    def completed(self) -> bool:
        if self.qualification is not None:
            return self.stop_reason in {
                QUALIFICATION_BOUNDARY_REACHED,
                QUALIFICATION_NOT_REACHED,
            }
        return self.evaluated_rounds >= self.requested_rounds

    @classmethod
    def empty(
        cls,
        requested_rounds: int,
        *,
        qualification: QualificationProgress | None = None,
    ) -> "CampaignRunResult":
        return cls(
            requested_rounds=max(1, int(requested_rounds)),
            evaluated_rounds=0,
            scheduled_calls=0,
            stop_reason="",
            failure_categories={},
            protocol_stage_counts={"screening": 0, "validation": 0, "frozen": 0},
            formal_screened_candidates=0,
            execution_outcome_counts={outcome.value: 0 for outcome in ExecutionOutcome},
            unknown_outcome_count=0,
            last_execution_outcome=None,
            qualification=qualification,
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
                completed=self.completed,
                execution_outcome_counts=self.execution_outcome_counts,
                completed_without_evaluated_outcome_is_valid=(
                    self.qualification is not None and self.completed
                ),
            ),
        }
        if self.qualification is not None:
            value["qualification"] = self.qualification.to_projection(
                stop_reason=self.stop_reason
            )
        if self.stop_reason:
            value["stop_reason"] = self.stop_reason
        if self.terminal_exception is not None:
            value["terminal_exception"] = dict(self.terminal_exception)
        return value


@dataclass
class CampaignLoop:
    """Run one scheduled call at a time until formal evaluated rounds complete."""

    write_status: Callable[..., None]
    drain_weight_opt_events: Callable[[], None]
    should_stop: Callable[[], bool]
    get_last_stop_reason: Callable[[], Optional[str]]
    set_last_stop_reason: Callable[[Optional[str]], None]
    run_one_step: Callable[[], StepResult]
    write_terminal_artifacts: Callable[[CampaignRunResult], None]
    get_final_wait_timeout: Callable[[], float]
    wait_weight_opt_all: Callable[[float], None]
    qualification_runtime: QualificationRuntime | None = None
    park_qualification_chain: Callable[[str], None] = lambda _branch_id: None
    retire_initial_screening_study_chain: Callable[[str, Decision], None] | None = None
    begin_async_stop_deferral: Callable[[], None] = lambda: None
    end_async_stop_deferral: Callable[[], None] = lambda: None
    current_result: CampaignRunResult | None = field(init=False, default=None)
    call_in_progress: bool = field(init=False, default=False)
    _post_return_deferral_active: bool = field(init=False, default=False)

    def _require_initial_screening_retirement_callback(
        self,
        qualification_config: QualificationOnlyConfig | None,
    ) -> None:
        if (
            qualification_config is not None
            and qualification_config.initial_screening_only
            and self.retire_initial_screening_study_chain is None
        ):
            raise RuntimeError(_INITIAL_SCREENING_RETIREMENT_CALLBACK_UNAVAILABLE)

    def _retire_initial_screening_decision(
        self,
        *,
        enabled: bool,
        branch_id: str,
        decision: Decision | None,
    ) -> bool:
        if not enabled or decision not in _INITIAL_SCREENING_STUDY_DECISIONS:
            return False
        assert decision is not None
        retire = self.retire_initial_screening_study_chain
        if retire is None:
            raise RuntimeError(_INITIAL_SCREENING_RETIREMENT_CALLBACK_UNAVAILABLE)
        retire(branch_id, decision)
        return True

    def _begin_post_return_deferral(self) -> None:
        if self._post_return_deferral_active:
            return
        self.begin_async_stop_deferral()
        self._post_return_deferral_active = True

    def _end_post_return_deferral(self) -> None:
        if not self._post_return_deferral_active:
            return
        self.end_async_stop_deferral()
        self._post_return_deferral_active = False

    def _apply_deferred_initial_only_stop(
        self,
        qualification_config: QualificationOnlyConfig | None,
        final_reason: str | None,
    ) -> str | None:
        if (
            qualification_config is None
            or not qualification_config.initial_screening_only
        ):
            return final_reason
        if not self.should_stop():
            return final_reason
        return self.get_last_stop_reason() or "termination condition met"

    def run(self, requested_rounds: int) -> CampaignRunResult:
        """Run and release every post-return signal deferral path."""

        try:
            return self._run(requested_rounds)
        finally:
            self._end_post_return_deferral()

    def _run(self, requested_rounds: int) -> CampaignRunResult:
        """Target formal evaluated rounds without retrying a provider outcome."""

        requested_rounds = max(1, int(requested_rounds))
        qualification_runtime = self.qualification_runtime
        qualification_config = (
            qualification_runtime.config if qualification_runtime is not None else None
        )
        self._require_initial_screening_retirement_callback(qualification_config)
        if qualification_runtime is not None:
            if qualification_runtime.started:
                if self.current_result is None or not self.current_result.stop_reason:
                    raise RuntimeError(
                        "qualification-only campaign is already in progress"
                    )
                return self.current_result
            qualification_runtime.begin_run()
        self.current_result = None
        self.call_in_progress = False
        evaluated_rounds = 0
        scheduled_calls = 0
        formal_screened_candidates = 0
        protocol_stage_counts = {"screening": 0, "validation": 0, "frozen": 0}
        failure_category_counts: dict[str, int] = {}
        execution_outcome_counts = {outcome.value: 0 for outcome in ExecutionOutcome}
        unknown_outcome_count = 0
        last_execution_outcome: dict[str, Any] | None = None
        final_reason: str | None = None

        def qualification_progress() -> QualificationProgress | None:
            if qualification_runtime is None:
                return None
            return qualification_runtime.progress()

        def snapshot(*, stop_reason: str = "") -> CampaignRunResult:
            value = CampaignRunResult(
                requested_rounds=requested_rounds,
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
                qualification=qualification_progress(),
            )
            self.current_result = value
            return value

        def park_chain(branch_id: str | None) -> None:
            if branch_id:
                self.park_qualification_chain(branch_id)

        def qualification_budget_stop() -> str | None:
            if qualification_runtime is None:
                return None
            stop = qualification_runtime.normal_stop_before_dispatch()
            if stop is None:
                return None
            reason, branch_id = stop
            park_chain(branch_id)
            return reason

        self.write_status(run_result=snapshot())
        while qualification_config is not None or evaluated_rounds < requested_rounds:
            self._end_post_return_deferral()
            self.drain_weight_opt_events()
            if self.should_stop():
                final_reason = (
                    self.get_last_stop_reason() or "termination condition met"
                )
                current = snapshot(stop_reason=final_reason)
                self.write_status(
                    run_result=current,
                )
                break

            budget_reason = qualification_budget_stop()
            if budget_reason is not None:
                final_reason = budget_reason
                self.write_status(run_result=snapshot(stop_reason=final_reason))
                break

            self.write_status(run_result=snapshot())
            expected_expansion_branch_id = (
                qualification_runtime.pending_expansion_branch_id
                if qualification_runtime is not None
                else None
            )
            self.call_in_progress = True
            snapshot()
            try:
                result = self.run_one_step()
            except QualificationProposalBudgetExhausted:
                self.call_in_progress = False
                final_reason = (
                    qualification_budget_stop()
                    or "qualification_proposal_budget_invariant"
                )
                self.write_status(run_result=snapshot(stop_reason=final_reason))
                break
            self._begin_post_return_deferral()
            self.call_in_progress = False
            outcome_record = result.execution_outcome
            outcome = outcome_record.outcome if outcome_record is not None else None
            if outcome_record is None:
                if qualification_config is not None:
                    scheduled_calls += 1
                    unknown_outcome_count += 1
                    final_reason = "execution_outcome_missing"
                    self.write_status(
                        last_result=result,
                        run_result=snapshot(stop_reason=final_reason),
                    )
                    break
                self.write_status(
                    last_result=result,
                    run_result=snapshot(),
                )
                continue

            scheduled_calls += 1
            execution_outcome_counts[outcome_record.outcome.value] += 1
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
            # From here onward policy callbacks can fail after the scheduled
            # result is already durable.  Keep the terminal base synchronized
            # with those completed local accounting mutations.
            snapshot()

            result_branch_id = str(result.branch_id or "").strip()
            if qualification_runtime is not None:
                if (
                    expected_expansion_branch_id is not None
                    and result_branch_id != expected_expansion_branch_id
                ):
                    final_reason = "qualification_expansion_branch_mismatch"
                if getattr(result, "verification_passed", None) is True:
                    try:
                        qualification_runtime.record_verified_candidate(
                            result_branch_id
                        )
                    except ValueError:
                        final_reason = "qualification_verified_candidate_invalid"
                    snapshot()

                if final_reason is not None:
                    self.write_status(
                        last_result=result,
                        run_result=snapshot(stop_reason=final_reason),
                    )
                    break

            if outcome is ExecutionOutcome.RESEARCH_REJECTED:
                if qualification_runtime is not None and (
                    expected_expansion_branch_id is not None
                ):
                    final_reason = "qualification_expansion_outcome_invalid"
                    self.write_status(
                        last_result=result,
                        run_result=snapshot(stop_reason=final_reason),
                    )
                    break
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
                if qualification_runtime is not None and _is_candidate_canary_rejection(
                    result
                ):
                    if (
                        result_branch_id
                        not in qualification_runtime.verified_candidate_branch_ids
                    ):
                        final_reason = "qualification_verified_candidate_fact_missing"
                        self.write_status(
                            last_result=result,
                            run_result=snapshot(stop_reason=final_reason),
                        )
                        break
                    park_chain(result_branch_id)
                    self.write_status(
                        last_result=result,
                        run_result=snapshot(),
                    )
                    continue
                final_reason = "evaluated_without_formal_protocol_result"
                self.write_status(
                    last_result=result,
                    run_result=snapshot(stop_reason=final_reason),
                )
                break

            if qualification_runtime is not None and protocol_stage != "screening":
                final_reason = "qualification_heldout_stage_observed"
                self.write_status(
                    last_result=result,
                    run_result=snapshot(stop_reason=final_reason),
                )
                break

            evaluated_rounds += 1
            protocol_stage_counts[protocol_stage] += 1
            if _is_formal_screened_candidate_result(result, protocol_stage):
                formal_screened_candidates += 1
            snapshot()

            if qualification_runtime is not None:
                try:
                    qualification_runtime.record_screening_stage(
                        result_branch_id,
                        expanded=expected_expansion_branch_id is not None,
                    )
                except ValueError:
                    final_reason = "qualification_screening_sequence_invalid"
                    self.write_status(
                        last_result=result,
                        run_result=snapshot(stop_reason=final_reason),
                    )
                    break
                snapshot()

                if self._retire_initial_screening_decision(
                    enabled=qualification_runtime.config.initial_screening_only,
                    branch_id=result_branch_id,
                    decision=result.decision,
                ):
                    self.write_status(
                        last_result=result,
                        run_result=snapshot(),
                    )
                    continue

                if result.decision is Decision.QUEUE_VALIDATE:
                    final_reason = QUALIFICATION_BOUNDARY_REACHED
                    self.write_status(
                        last_result=result,
                        run_result=snapshot(stop_reason=final_reason),
                    )
                    break
                if result.decision is Decision.EXPAND_SCREENING:
                    if expected_expansion_branch_id is None:
                        qualification_runtime.request_expansion(result_branch_id)
                    else:
                        park_chain(result_branch_id)
                    self.write_status(
                        last_result=result,
                        run_result=snapshot(),
                    )
                    continue
                if result.decision in {
                    Decision.CONTINUE_EXPLORE,
                    Decision.ABANDON,
                }:
                    park_chain(result_branch_id)
                    self.write_status(
                        last_result=result,
                        run_result=snapshot(),
                    )
                    continue
                final_reason = "qualification_screening_decision_invalid"
                self.write_status(
                    last_result=result,
                    run_result=snapshot(stop_reason=final_reason),
                )
                break

            self.write_status(
                last_result=result,
                run_result=snapshot(),
            )
            if result.stopped:
                final_reason = result.reason or "stopped"
                break

        self._end_post_return_deferral()
        final_reason = self._apply_deferred_initial_only_stop(
            qualification_config,
            final_reason,
        )
        if final_reason is None:
            final_reason = (
                QUALIFICATION_NOT_REACHED
                if qualification_config is not None
                else "requested_rounds_completed"
            )
        self.set_last_stop_reason(final_reason)
        self.wait_weight_opt_all(self.get_final_wait_timeout())
        self.drain_weight_opt_events()
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


def _is_candidate_canary_rejection(result: StepResult) -> bool:
    canary = result.canary_result
    return (
        result.decision is Decision.ABANDON
        and canary is not None
        and getattr(canary, "passed", None) is False
        and getattr(canary, "failure_category", "") == CANARY_FAILURE_CATEGORY_CANDIDATE
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
