"""Public-safe in-memory accounting for bounded proposal attempts."""

from __future__ import annotations

import threading
from contextlib import AbstractContextManager
from dataclasses import dataclass
from types import TracebackType
from typing import Any, Literal

from scion.core.resource_envelope import (
    ProviderCallBudget,
    ProviderCallBudgetSnapshot,
)

ProposalAttemptAccountingState = Literal[
    "active",
    "closed",
    "interrupted",
    "unresolved",
]
_TERMINAL_ACCOUNTING_STATES = frozenset({"closed", "interrupted", "unresolved"})


@dataclass(frozen=True)
class ProposalAttemptRuntimeSnapshot:
    """One body-free attempt row derived from atomic provider snapshots."""

    round_num: int
    accounting_state: ProposalAttemptAccountingState
    budget_admitted: int
    by_request_kind: tuple[tuple[str, int], ...]
    hypothesis_candidates_completed: int
    hypothesis_candidates_selected: int
    hypotheses_exported: int
    patches_completed: int
    code_candidates_ready: int

    def to_primitive(self) -> dict[str, Any]:
        return {
            "round_num": self.round_num,
            "accounting_state": self.accounting_state,
            "provider_calls": {
                "budget_admitted": self.budget_admitted,
                "by_request_kind": dict(self.by_request_kind),
            },
            "hypothesis_candidates_completed": self.hypothesis_candidates_completed,
            "hypothesis_candidates_selected": self.hypothesis_candidates_selected,
            "hypotheses_exported": self.hypotheses_exported,
            "patches_completed": self.patches_completed,
            "code_candidates_ready": self.code_candidates_ready,
        }


@dataclass(frozen=True)
class ProposalRuntimeSnapshot:
    """One immutable aggregate plus its ordered attempt attribution."""

    provider_calls: ProviderCallBudgetSnapshot
    attempts: tuple[ProposalAttemptRuntimeSnapshot, ...]

    def to_primitive(self) -> dict[str, Any]:
        return {
            "provider_calls": self.provider_calls.to_primitive(),
            "attempts": [attempt.to_primitive() for attempt in self.attempts],
        }


@dataclass
class _Attempt:
    round_num: int
    start: ProviderCallBudgetSnapshot
    end: ProviderCallBudgetSnapshot | None = None
    accounting_state: ProposalAttemptAccountingState = "active"
    hypothesis_candidates_completed: int = 0
    hypothesis_candidates_selected: int = 0
    hypotheses_exported: int = 0
    patches_completed: int = 0
    code_candidates_ready: int = 0
    faulted: bool = False


class _AttemptScope(AbstractContextManager[None]):
    def __init__(self, runtime: ProposalRuntimeTelemetry, round_num: int) -> None:
        self._runtime = runtime
        self._round_num = round_num
        self._started = False

    def __enter__(self) -> None:
        self._started = self._runtime._begin(self._round_num)

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        _exc: BaseException | None,
        _traceback: TracebackType | None,
    ) -> Literal[False]:
        if self._started:
            state: ProposalAttemptAccountingState
            if exc_type is None:
                state = "closed"
            elif issubclass(exc_type, (KeyboardInterrupt, SystemExit)):
                state = "interrupted"
            else:
                state = "unresolved"
            self._runtime._finish(state)
        return False


class ProposalRuntimeTelemetry:
    """Single-active-attempt telemetry with count-only, no-throw hooks."""

    def __init__(
        self,
        provider_call_budget: ProviderCallBudget,
        *,
        max_hypothesis_candidates: int,
    ) -> None:
        if type(max_hypothesis_candidates) is not int or (
            max_hypothesis_candidates not in {1, 2}
        ):
            raise ValueError("proposal runtime candidate count must be 1 or 2")
        self._provider_call_budget = provider_call_budget
        self._max_hypothesis_candidates = max_hypothesis_candidates
        self._attempts: list[_Attempt] = []
        self._active: _Attempt | None = None
        self._lock = threading.Lock()

    def attempt_scope(self, round_num: int) -> AbstractContextManager[None]:
        """Return one scope for an admitted proposal attempt."""

        return _AttemptScope(self, round_num)

    def record_hypothesis_candidate_completed(self) -> None:
        with self._lock:
            attempt = self._active
            if attempt is None:
                return
            if (
                attempt.hypothesis_candidates_completed
                >= self._max_hypothesis_candidates
            ):
                attempt.faulted = True
                return
            attempt.hypothesis_candidates_completed += 1

    def record_hypothesis_candidate_selected(self) -> None:
        with self._lock:
            attempt = self._active
            if attempt is None:
                return
            if (
                attempt.hypothesis_candidates_selected != 0
                or attempt.hypothesis_candidates_completed
                != self._max_hypothesis_candidates
            ):
                attempt.faulted = True
                return
            attempt.hypothesis_candidates_selected = 1

    def record_hypothesis_exported(self) -> None:
        with self._lock:
            attempt = self._active
            if attempt is None:
                return
            if (
                attempt.hypotheses_exported != 0
                or attempt.hypothesis_candidates_selected != 1
            ):
                attempt.faulted = True
                return
            attempt.hypotheses_exported = 1

    def record_patch_completed(self) -> None:
        with self._lock:
            attempt = self._active
            if attempt is None:
                return
            if attempt.patches_completed != 0 or attempt.hypotheses_exported != 1:
                attempt.faulted = True
                return
            attempt.patches_completed = 1

    def record_code_candidate_ready(self) -> None:
        with self._lock:
            attempt = self._active
            if attempt is None:
                return
            if attempt.code_candidates_ready != 0 or attempt.patches_completed != 1:
                attempt.faulted = True
                return
            attempt.code_candidates_ready = 1

    def seal_active(self, state: ProposalAttemptAccountingState) -> None:
        """Idempotently close an unexpectedly live attempt at a terminal edge."""

        if state not in {"interrupted", "unresolved"}:
            return
        self._finish(state)

    def snapshot(
        self,
        provider_calls: ProviderCallBudgetSnapshot,
        *,
        terminal: bool,
    ) -> ProposalRuntimeSnapshot:
        """Project all rows against the exact aggregate snapshot supplied."""

        with self._lock:
            active = self._active
            attempts = tuple(
                _attempt_snapshot(
                    attempt,
                    end=(provider_calls if attempt is active else attempt.end),
                )
                for attempt in self._attempts
            )
        value = ProposalRuntimeSnapshot(
            provider_calls=provider_calls,
            attempts=attempts,
        )
        _validate_runtime_snapshot(value, terminal=terminal)
        return value

    def _begin(self, round_num: int) -> bool:
        start = self._provider_call_budget.snapshot()
        with self._lock:
            if (
                type(round_num) is not int
                or round_num <= 0
                or self._active is not None
                or any(attempt.round_num == round_num for attempt in self._attempts)
            ):
                if self._active is not None:
                    self._active.faulted = True
                return False
            attempt = _Attempt(round_num=round_num, start=start)
            self._active = attempt
            self._attempts.append(attempt)
            return True

    def _finish(self, state: ProposalAttemptAccountingState) -> None:
        if state not in _TERMINAL_ACCOUNTING_STATES:
            return
        end = self._provider_call_budget.snapshot()
        with self._lock:
            attempt = self._active
            if attempt is None:
                return
            attempt.end = end
            attempt.accounting_state = "unresolved" if attempt.faulted else state
            self._active = None


def _attempt_snapshot(
    attempt: _Attempt,
    *,
    end: ProviderCallBudgetSnapshot | None,
) -> ProposalAttemptRuntimeSnapshot:
    if end is None:
        raise RuntimeError("closed proposal attempt is missing an end snapshot")
    if attempt.start.cap != end.cap:
        raise RuntimeError("proposal provider cap changed during an attempt")
    start_by_kind = dict(attempt.start.by_request_kind)
    end_by_kind = dict(end.by_request_kind)
    if tuple(start_by_kind) != tuple(end_by_kind):
        raise RuntimeError("proposal provider request-kind schema changed")
    by_request_kind = tuple(
        (kind, end_by_kind[kind] - start_by_kind[kind]) for kind in end_by_kind
    )
    budget_admitted = end.budget_admitted - attempt.start.budget_admitted
    if budget_admitted < 0 or any(value < 0 for _kind, value in by_request_kind):
        raise RuntimeError("proposal provider accounting delta is negative")
    if sum(value for _kind, value in by_request_kind) != budget_admitted:
        raise RuntimeError("proposal provider accounting delta is inconsistent")
    return ProposalAttemptRuntimeSnapshot(
        round_num=attempt.round_num,
        accounting_state=attempt.accounting_state,
        budget_admitted=budget_admitted,
        by_request_kind=by_request_kind,
        hypothesis_candidates_completed=attempt.hypothesis_candidates_completed,
        hypothesis_candidates_selected=attempt.hypothesis_candidates_selected,
        hypotheses_exported=attempt.hypotheses_exported,
        patches_completed=attempt.patches_completed,
        code_candidates_ready=attempt.code_candidates_ready,
    )


def _validate_runtime_snapshot(
    value: ProposalRuntimeSnapshot,
    *,
    terminal: bool,
) -> None:
    for attempt in value.attempts:
        if not (
            attempt.hypothesis_candidates_selected
            <= attempt.hypothesis_candidates_completed
            <= 2
            and 0 <= attempt.hypothesis_candidates_selected <= 1
            and 0 <= attempt.hypotheses_exported <= 1
            and 0 <= attempt.patches_completed <= 1
            and 0 <= attempt.code_candidates_ready <= 1
        ):
            raise RuntimeError("proposal attempt counters violate their bounds")
        if attempt.budget_admitted != sum(
            count for _kind, count in attempt.by_request_kind
        ):
            raise RuntimeError("proposal attempt provider totals are inconsistent")
    if terminal:
        if any(attempt.accounting_state == "active" for attempt in value.attempts):
            raise RuntimeError("terminal proposal telemetry contains an active attempt")
        if sum(attempt.budget_admitted for attempt in value.attempts) != (
            value.provider_calls.budget_admitted
        ):
            raise RuntimeError("terminal proposal rows do not sum to the aggregate")
        aggregate_by_kind = dict(value.provider_calls.by_request_kind)
        for kind, aggregate in aggregate_by_kind.items():
            if sum(
                dict(attempt.by_request_kind)[kind] for attempt in value.attempts
            ) != (aggregate):
                raise RuntimeError(
                    "terminal proposal request-kind rows do not sum to the aggregate"
                )


__all__ = [
    "ProposalAttemptAccountingState",
    "ProposalAttemptRuntimeSnapshot",
    "ProposalRuntimeSnapshot",
    "ProposalRuntimeTelemetry",
]
