"""Outer campaign loop lifecycle."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Mapping, Optional

from scion.core.branch_repair_policy import repair_attempt_key_label
from scion.core.run_validity import failure_category_for_run_validity
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
    run_fresh_runtime_replay_drain_step: Callable[[], StepResult] | None = None
    run_stage_transition_drain_step: Callable[[], StepResult] | None = None
    proposal_quality_loop_limit: int | None = None
    proposal_attempt_limit: int | None = None
    telemetry_repair_attempt_limit: int | None = None
    fresh_runtime_replay_drain_limit: int | None = None
    stage_transition_drain_limit: int | None = None
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
        telemetry_repair_attempts = 0
        telemetry_repair_attempt_counts: dict[str, int] = {}
        failure_category_counts: dict[str, int] = {}
        last_failure_category = ""
        same_family_retry_attempts = 0
        branch_lifecycle_policy_blocks = 0
        reconcile_lifecycle_steps = 0
        scheduler_active_slot_blocked_attempts = 0
        fresh_runtime_replay_drain_attempts = 0
        fresh_runtime_replay_drain_executed = 0
        fresh_runtime_replay_drain_skipped = 0
        fresh_runtime_replay_drain_stop_reason = ""
        fresh_runtime_replay_drain_last_metadata: dict[str, Any] = {}
        fresh_runtime_replay_drain_accepted_metadata: dict[str, Any] = {}
        fresh_runtime_replay_drain_final_metadata: dict[str, Any] = {}
        stage_transition_drain_attempts = 0
        stage_transition_drain_executed = 0
        stage_transition_drain_skipped = 0
        stage_transition_drain_stop_reason = ""
        stage_transition_drain_last_metadata: dict[str, Any] = {}
        stage_transition_drain_accepted_metadata: dict[str, Any] = {}
        stage_transition_drain_final_metadata: dict[str, Any] = {}
        formal_screened_candidates = 0
        protocol_evaluated_candidates = 0
        quality_block_ledger: list[dict[str, Any]] = []
        protocol_stage_counts: dict[str, int] = {
            "screening": 0,
            "validation": 0,
            "frozen": 0,
        }
        requested_rounds = max(1, int(max_rounds))
        proposal_quality_loop_limit = _proposal_quality_loop_limit(
            requested_rounds,
            configured=self.proposal_quality_loop_limit,
        )
        attempt_limit = _proposal_attempt_limit(
            requested_rounds,
            configured=self.proposal_attempt_limit,
        )
        telemetry_repair_attempt_limit = _telemetry_repair_attempt_limit(
            configured=self.telemetry_repair_attempt_limit,
        )
        bad_proposal_limit = requested_rounds * 5 + 10
        telemetry_repairable_limit = requested_rounds * 2 + 4
        validation_repair_required_limit = requested_rounds + 2
        same_family_retry_limit = requested_rounds + 4
        branch_lifecycle_policy_block_limit = requested_rounds + 4
        reconcile_lifecycle_step_limit = requested_rounds + 4
        scheduler_active_slot_blocked_attempt_limit = (
            _scheduler_active_slot_blocked_attempt_limit(requested_rounds)
        )
        fresh_runtime_replay_drain_limit = _fresh_runtime_replay_drain_limit(
            requested_rounds,
            configured=self.fresh_runtime_replay_drain_limit,
        )
        stage_transition_drain_limit = _stage_transition_drain_limit(
            requested_rounds,
            configured=self.stage_transition_drain_limit,
        )
        # Non-round steps such as proposal blocks and telemetry-repairable
        # formal runs do not consume the screened-round budget.  Ordinary
        # proposal attempts have a hard cap; telemetry repair/diagnostic
        # attempts instead use a separate per-branch/per-mechanism cap so they
        # cannot exhaust requested effective rounds.
        loop_step_limit = (
            requested_rounds
            + proposal_quality_loop_limit
            + bad_proposal_limit
            + telemetry_repairable_limit
            + validation_repair_required_limit
            + same_family_retry_limit
            + branch_lifecycle_policy_block_limit
            + reconcile_lifecycle_step_limit
            + scheduler_active_slot_blocked_attempt_limit
        )

        proposal_attempts_consumed_count = _initial_proposal_attempts(
            self.get_proposal_attempts,
            fallback=0,
        )

        def proposal_attempts_consumed() -> int:
            return max(0, int(proposal_attempts_consumed_count))

        def consume_proposal_attempt() -> None:
            nonlocal proposal_attempts_consumed_count
            proposal_attempts_consumed_count += 1

        def record_repair_attempt(result: StepResult) -> int:
            nonlocal telemetry_repair_attempts
            telemetry_repair_attempts += 1
            key = repair_attempt_key_label(
                getattr(result, "branch_id", None),
                getattr(result, "repair_mechanism_ids", ()) or (),
            )
            telemetry_repair_attempt_counts[key] = (
                telemetry_repair_attempt_counts.get(key, 0) + 1
            )
            return telemetry_repair_attempt_counts[key]

        def legacy_external_attempts() -> int:
            if self.get_proposal_attempts is None:
                return max(0, int(loop_steps))
            try:
                return max(0, int(self.get_proposal_attempts()))
            except Exception as exc:  # pragma: no cover - defensive status path
                logger.debug("Failed to read proposal attempt count: %s", exc)
                return max(0, int(loop_steps))

        def loop_status() -> dict[str, Any]:
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
                telemetry_repair_attempts=telemetry_repair_attempts,
                telemetry_repair_attempt_limit=telemetry_repair_attempt_limit,
                telemetry_repair_attempt_counts=telemetry_repair_attempt_counts,
                branch_lifecycle_policy_blocks=branch_lifecycle_policy_blocks,
                branch_lifecycle_policy_block_limit=(
                    branch_lifecycle_policy_block_limit
                ),
                reconcile_lifecycle_steps=reconcile_lifecycle_steps,
                reconcile_lifecycle_step_limit=reconcile_lifecycle_step_limit,
                scheduler_active_slot_blocked_attempts=(
                    scheduler_active_slot_blocked_attempts
                ),
                scheduler_active_slot_blocked_attempt_limit=(
                    scheduler_active_slot_blocked_attempt_limit
                ),
                fresh_runtime_replay_drain_attempts=(
                    fresh_runtime_replay_drain_attempts
                ),
                fresh_runtime_replay_drain_executed=(
                    fresh_runtime_replay_drain_executed
                ),
                fresh_runtime_replay_drain_skipped=(
                    fresh_runtime_replay_drain_skipped
                ),
                fresh_runtime_replay_drain_limit=fresh_runtime_replay_drain_limit,
                fresh_runtime_replay_drain_stop_reason=(
                    fresh_runtime_replay_drain_stop_reason
                ),
                fresh_runtime_replay_drain_last_metadata=(
                    fresh_runtime_replay_drain_last_metadata
                ),
                fresh_runtime_replay_drain_accepted_metadata=(
                    fresh_runtime_replay_drain_accepted_metadata
                ),
                fresh_runtime_replay_drain_final_metadata=(
                    fresh_runtime_replay_drain_final_metadata
                ),
                stage_transition_drain_attempts=stage_transition_drain_attempts,
                stage_transition_drain_executed=stage_transition_drain_executed,
                stage_transition_drain_skipped=stage_transition_drain_skipped,
                stage_transition_drain_limit=stage_transition_drain_limit,
                stage_transition_drain_stop_reason=stage_transition_drain_stop_reason,
                stage_transition_drain_last_metadata=(
                    stage_transition_drain_last_metadata
                ),
                stage_transition_drain_accepted_metadata=(
                    stage_transition_drain_accepted_metadata
                ),
                stage_transition_drain_final_metadata=(
                    stage_transition_drain_final_metadata
                ),
                proposal_quality_loop_limit=proposal_quality_loop_limit,
                proposal_quality_blocked_attempts=proposal_quality_blocked_attempts,
                legacy_total_rounds=legacy_external_attempts(),
                formal_screened_candidates=formal_screened_candidates,
                protocol_evaluated_candidates=protocol_evaluated_candidates,
                protocol_stage_counts=protocol_stage_counts,
                quality_block_ledger=quality_block_ledger,
                failure_categories=failure_category_counts,
                last_failure_category=last_failure_category,
            )

        def record_protocol_result(result: StepResult) -> None:
            nonlocal formal_screened_candidates, protocol_evaluated_candidates
            protocol_stage = _protocol_stage_for_result(result)
            if protocol_stage:
                protocol_evaluated_candidates += 1
                protocol_stage_counts[protocol_stage] = (
                    protocol_stage_counts.get(protocol_stage, 0) + 1
                )
                if _is_formal_screened_candidate_result(result, protocol_stage):
                    formal_screened_candidates += 1

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
            record_protocol_result(result)
            result_failure_category = _result_failure_category(result)
            if result_failure_category:
                last_failure_category = result_failure_category
                failure_category_counts[result_failure_category] = (
                    failure_category_counts.get(result_failure_category, 0) + 1
                )
            kind = _attempt_kind(result)
            if getattr(result, "counts_toward_max_rounds", True):
                counted_rounds += 1
                consume_proposal_attempt()
            else:
                if kind == "validation_repair_required":
                    validation_repair_required_attempts += 1
                    repair_count = record_repair_attempt(result)
                    if (
                        validation_repair_required_attempts
                        >= validation_repair_required_limit
                    ):
                        final_reason = "validation_repair_required_budget_exhausted"
                    elif repair_count >= telemetry_repair_attempt_limit:
                        final_reason = "telemetry_repair_attempt_budget_exhausted"
                elif kind == "telemetry_repairable":
                    telemetry_repairable_attempts += 1
                    repair_count = record_repair_attempt(result)
                    if telemetry_repairable_attempts >= telemetry_repairable_limit:
                        final_reason = "telemetry_repairable_budget_exhausted"
                    elif repair_count >= telemetry_repair_attempt_limit:
                        final_reason = "telemetry_repair_attempt_budget_exhausted"
                elif kind == "telemetry_repair":
                    repair_count = record_repair_attempt(result)
                    if repair_count >= telemetry_repair_attempt_limit:
                        final_reason = "telemetry_repair_attempt_budget_exhausted"
                elif kind == "branch_lifecycle_policy":
                    branch_lifecycle_policy_blocks += 1
                    if (
                        branch_lifecycle_policy_blocks
                        >= branch_lifecycle_policy_block_limit
                    ):
                        final_reason = "branch_lifecycle_policy_loop"
                elif kind == "reconcile_lifecycle":
                    reconcile_lifecycle_steps += 1
                    if reconcile_lifecycle_steps >= reconcile_lifecycle_step_limit:
                        final_reason = "reconcile_lifecycle_loop"
                elif kind == "scheduler_active_slot_blocked":
                    scheduler_active_slot_blocked_attempts += 1
                    if (
                        scheduler_active_slot_blocked_attempts
                        >= scheduler_active_slot_blocked_attempt_limit
                    ):
                        final_reason = "scheduler_active_slot_blocked"
                elif kind == "same_family_retry":
                    consume_proposal_attempt()
                    same_family_retry_attempts += 1
                    if same_family_retry_attempts >= same_family_retry_limit:
                        final_reason = "same_family_retry_budget_exhausted"
                elif kind == "proposal_diagnostic":
                    consume_proposal_attempt()
                elif kind == "proposal_block":
                    consume_proposal_attempt()
                    proposal_quality_blocked_attempts += 1
                    quality_block_ledger.append(
                        _quality_block_ledger_entry(
                            result,
                            sequence=proposal_quality_blocked_attempts,
                            loop_step=loop_steps,
                            attempt_kind=kind,
                        )
                    )
                    if (
                        proposal_quality_blocked_attempts
                        >= proposal_quality_loop_limit
                    ):
                        final_reason = "proposal_quality_loop"
                elif kind == "schema_quality_block":
                    proposal_quality_blocked_attempts += 1
                    quality_block_ledger.append(
                        _quality_block_ledger_entry(
                            result,
                            sequence=proposal_quality_blocked_attempts,
                            loop_step=loop_steps,
                            attempt_kind=kind,
                        )
                    )
                    if (
                        proposal_quality_blocked_attempts
                        >= proposal_quality_loop_limit
                    ):
                        final_reason = "proposal_quality_loop"
                else:
                    consume_proposal_attempt()
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
            drain_step = self.run_stage_transition_drain_step
            if drain_step is not None:
                while stage_transition_drain_executed < stage_transition_drain_limit:
                    self.drain_weight_opt_events()
                    if self.should_stop():
                        stage_transition_drain_stop_reason = (
                            self.get_last_stop_reason()
                            or "termination condition met"
                        )
                        break
                    circuit_breaker = self.get_circuit_breaker()
                    if circuit_breaker.is_tripped:
                        stage_transition_drain_stop_reason = "circuit_breaker"
                        break
                    stage_transition_drain_attempts += 1
                    self.write_status(loop_status=loop_status())
                    result = drain_step()
                    if not _is_stage_transition_drain_result(result):
                        stage_transition_drain_skipped += 1
                        stage_transition_drain_final_metadata = (
                            _stage_transition_drain_result_metadata(result)
                        )
                        stage_transition_drain_stop_reason = (
                            str(result.reason or "")
                            or "no_stage_transition_pending"
                        )
                        stage_transition_drain_last_metadata = dict(
                            stage_transition_drain_final_metadata
                        )
                        break
                    stage_transition_drain_executed += 1
                    record_protocol_result(result)
                    stage_transition_drain_accepted_metadata = (
                        _stage_transition_drain_result_metadata(result)
                    )
                    stage_transition_drain_final_metadata = dict(
                        stage_transition_drain_accepted_metadata
                    )
                    stage_transition_drain_last_metadata = dict(
                        stage_transition_drain_accepted_metadata
                    )
                    self.write_status(
                        last_result=result,
                        loop_status=loop_status(),
                    )
                    if result.stopped:
                        stage_transition_drain_stop_reason = (
                            result.reason or "stage_transition_drain_stopped"
                        )
                        break
                else:
                    stage_transition_drain_stop_reason = (
                        "stage_transition_drain_cap_exhausted"
                    )
                    stage_transition_drain_final_metadata = {
                        **stage_transition_drain_final_metadata,
                        "cap_exhausted": True,
                        "stopped_reason": stage_transition_drain_stop_reason,
                    }
                    stage_transition_drain_last_metadata = dict(
                        stage_transition_drain_final_metadata
                    )
        if final_reason is None and counted_rounds >= requested_rounds:
            drain_step = self.run_fresh_runtime_replay_drain_step
            if drain_step is not None:
                while (
                    fresh_runtime_replay_drain_executed
                    < fresh_runtime_replay_drain_limit
                ):
                    self.drain_weight_opt_events()
                    if self.should_stop():
                        fresh_runtime_replay_drain_stop_reason = (
                            self.get_last_stop_reason()
                            or "termination condition met"
                        )
                        break
                    circuit_breaker = self.get_circuit_breaker()
                    if circuit_breaker.is_tripped:
                        fresh_runtime_replay_drain_stop_reason = "circuit_breaker"
                        break
                    fresh_runtime_replay_drain_attempts += 1
                    self.write_status(loop_status=loop_status())
                    result = drain_step()
                    if not _is_fresh_runtime_replay_drain_result(result):
                        fresh_runtime_replay_drain_skipped += 1
                        fresh_runtime_replay_drain_final_metadata = (
                            _fresh_runtime_replay_drain_result_metadata(result)
                        )
                        fresh_runtime_replay_drain_stop_reason = (
                            _fresh_runtime_replay_closure_status(
                                fresh_runtime_replay_drain_final_metadata
                            )
                            or "no_fresh_runtime_replay_pending"
                        )
                        fresh_runtime_replay_drain_last_metadata = dict(
                            fresh_runtime_replay_drain_final_metadata
                        )
                        break
                    fresh_runtime_replay_drain_executed += 1
                    fresh_runtime_replay_drain_accepted_metadata = (
                        _fresh_runtime_replay_drain_result_metadata(result)
                    )
                    fresh_runtime_replay_drain_final_metadata = dict(
                        fresh_runtime_replay_drain_accepted_metadata
                    )
                    fresh_runtime_replay_drain_last_metadata = dict(
                        fresh_runtime_replay_drain_accepted_metadata
                    )
                    self.write_status(
                        last_result=result,
                        loop_status=loop_status(),
                    )
                    if result.stopped:
                        fresh_runtime_replay_drain_stop_reason = (
                            result.reason or "fresh_runtime_replay_stopped"
                        )
                        break
                else:
                    fresh_runtime_replay_drain_stop_reason = (
                        "fresh_runtime_replay_drain_cap_exhausted"
                    )
                    fresh_runtime_replay_drain_final_metadata = {
                        **fresh_runtime_replay_drain_final_metadata,
                        "cap_exhausted": True,
                        "stopped_reason": fresh_runtime_replay_drain_stop_reason,
                    }
                    fresh_runtime_replay_drain_last_metadata = dict(
                        fresh_runtime_replay_drain_final_metadata
                    )
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
        self.write_status(
            stopped_reason=final_reason or "run_complete",
            loop_status=loop_status(),
        )
        self.write_campaign_summary()
        self.write_status(
            stopped_reason=final_reason or "run_complete",
            loop_status=loop_status(),
        )


def _attempt_kind(result: StepResult) -> str:
    kind = str(getattr(result, "attempt_kind", "") or "")
    if kind in {"proposal_block", "schema_quality_block"} and (
        _is_soft_proposal_diagnostic(result)
        or not _is_countable_quality_block_result(result)
    ):
        return "proposal_diagnostic"
    if kind and kind != "screening":
        return kind
    if getattr(result, "action", None) == "reconcile":
        return "reconcile_lifecycle"
    if _is_scheduler_active_slot_blocked(result):
        return "scheduler_active_slot_blocked"
    reason = str(getattr(result, "reason", "") or "").lower()
    if "branch_lifecycle_policy_violation" in reason:
        return "branch_lifecycle_policy"
    if "repair_first_policy_violation" in reason:
        return "telemetry_repair"
    if (
        "telemetry_validation_repairable" in reason
        or "validation_telemetry_repairable" in reason
    ):
        if "validation" in reason:
            return "validation_repair_required"
        return "telemetry_repairable"
    if "same_family" in reason or "semantic retry" in reason:
        return "same_family_retry"
    if (
        "schema_quality_block" in reason
        or "mechanism_changes_duplicate_id_conflict" in reason
    ):
        return "schema_quality_block"
    if _is_soft_proposal_diagnostic(result):
        return "proposal_diagnostic"
    return "proposal_block"


def _is_fresh_runtime_replay_drain_result(result: StepResult) -> bool:
    if bool(getattr(result, "counts_toward_max_rounds", True)):
        return False
    if _attempt_kind(result) == "fresh_runtime_replay":
        return True
    return (
        str(getattr(result, "action", "") or "") == "replay"
        and _scheduler_action_for_result(result) == "replay_existing"
    )


def _is_stage_transition_drain_result(result: StepResult) -> bool:
    if bool(getattr(result, "counts_toward_max_rounds", True)):
        return False
    return _protocol_stage_for_result(result) in {"validation", "frozen"}


def _scheduler_action_for_result(result: StepResult) -> str:
    metadata = getattr(result, "scheduler_audit_metadata", None) or {}
    if not isinstance(metadata, dict):
        metadata = {}
    return str(
        metadata.get("pre_finalizer_scheduler_action")
        or metadata.get("scheduler_action")
        or ""
    )


def _fresh_runtime_replay_drain_result_metadata(
    result: StepResult,
) -> dict[str, Any]:
    metadata = getattr(result, "scheduler_audit_metadata", None) or {}
    replay_metadata = (
        metadata.get("fresh_runtime_replay")
        if isinstance(metadata, dict)
        else None
    )
    return {
        "schema_version": "fresh_runtime_replay_drain_result.v1",
        "branch_id": getattr(result, "branch_id", None),
        "action": str(getattr(result, "action", "") or ""),
        "attempt_kind": _attempt_kind(result),
        "counts_toward_max_rounds": bool(
            getattr(result, "counts_toward_max_rounds", True)
        ),
        "scheduler_action": _scheduler_action_for_result(result),
        "scheduler_slot": str(getattr(result, "scheduler_slot", "") or ""),
        "scheduler_reason": str(getattr(result, "scheduler_reason", "") or ""),
        "reason": str(getattr(result, "reason", "") or ""),
        "failure_stage": getattr(result, "failure_stage", None),
        "failure_category": getattr(result, "failure_category", None),
        "failure_detail": (
            str(getattr(result, "failure_detail", ""))[:1000]
            if getattr(result, "failure_detail", None)
            else None
        ),
        "accepted_for_drain": _is_fresh_runtime_replay_drain_result(result),
        "fresh_runtime_replay": (
            dict(replay_metadata) if isinstance(replay_metadata, dict) else {}
        ),
    }


def _stage_transition_drain_result_metadata(
    result: StepResult,
) -> dict[str, Any]:
    metadata = getattr(result, "scheduler_audit_metadata", None) or {}
    drain_metadata = (
        metadata.get("stage_transition_drain")
        if isinstance(metadata, dict)
        else None
    )
    return {
        "schema_version": "stage_transition_drain_result.v1",
        "branch_id": getattr(result, "branch_id", None),
        "action": str(getattr(result, "action", "") or ""),
        "attempt_kind": _attempt_kind(result),
        "counts_toward_max_rounds": bool(
            getattr(result, "counts_toward_max_rounds", True)
        ),
        "scheduler_action": _scheduler_action_for_result(result),
        "scheduler_slot": str(getattr(result, "scheduler_slot", "") or ""),
        "scheduler_reason": str(getattr(result, "scheduler_reason", "") or ""),
        "reason": str(getattr(result, "reason", "") or ""),
        "protocol_stage": str(getattr(result, "protocol_stage", "") or ""),
        "formal_protocol_evaluated": bool(
            getattr(result, "formal_protocol_evaluated", False)
        ),
        "decision": (
            getattr(getattr(result, "decision", None), "value", None)
            or str(getattr(result, "decision", "") or "")
        ),
        "failure_stage": getattr(result, "failure_stage", None),
        "failure_category": getattr(result, "failure_category", None),
        "failure_detail": (
            str(getattr(result, "failure_detail", ""))[:1000]
            if getattr(result, "failure_detail", None)
            else None
        ),
        "accepted_for_drain": _is_stage_transition_drain_result(result),
        "stage_transition_drain": (
            dict(drain_metadata) if isinstance(drain_metadata, dict) else {}
        ),
    }


def _is_scheduler_active_slot_blocked(result: StepResult) -> bool:
    if str(getattr(result, "action", "") or "") != "skip":
        return False
    slot = str(getattr(result, "scheduler_slot", "") or "")
    scheduler_reason = str(getattr(result, "scheduler_reason", "") or "")
    reason = str(getattr(result, "reason", "") or "")
    return (
        slot == "capacity_blocked"
        or scheduler_reason == "active_branch_limit_reached"
        or "max_active_branches" in reason
    )


def _protocol_stage_for_result(result: StepResult) -> str:
    """Best-effort protocol stage classification for loop-only accounting."""
    explicit_stage = str(getattr(result, "protocol_stage", "") or "")
    if explicit_stage in {"screening", "validation", "frozen"}:
        if bool(getattr(result, "formal_protocol_evaluated", False)):
            return explicit_stage
        return ""
    return ""


def _is_formal_screened_candidate_result(result: StepResult, stage: str) -> bool:
    explicit_stage = str(getattr(result, "protocol_stage", "") or "")
    if explicit_stage:
        return stage == "screening" and bool(
            getattr(result, "screened_experiment_effective", False)
        )
    raw_kind = str(getattr(result, "attempt_kind", "") or "")
    return (
        stage == "screening"
        and raw_kind in {"", "screening"}
        and bool(getattr(result, "counts_toward_max_rounds", True))
    )


def _is_soft_proposal_diagnostic(result: StepResult) -> bool:
    combined = " ".join(
        str(value or "")
        for value in (
            getattr(result, "reason", None),
            getattr(result, "failure_detail", None),
            getattr(result, "failure_category", None),
        )
    ).lower()
    return any(
        marker in combined
        for marker in (
            "mechanism_premise_warning",
            "mechanism_novelty_warning",
            "mechanism_novelty_rejected",
            "mechanism_novelty_diagnostic",
            "duplicate_mechanism",
            "duplicate_risk",
            "novelty_warning",
        )
    )


def _is_countable_quality_block_result(result: StepResult) -> bool:
    if _is_stale_source_failure(result):
        return False
    stage = str(getattr(result, "failure_stage", "") or "").strip()
    category = str(getattr(result, "failure_category", "") or "").strip()
    detail = str(getattr(result, "failure_detail", "") or "").strip()
    if stage or category or detail:
        return True
    reason = str(getattr(result, "reason", "") or "").strip().lower()
    if not reason:
        return False
    if "continue_explore" in reason:
        return False
    return any(
        marker in reason
        for marker in (
            "agent_quality_blocked",
            "schema_quality_block",
            "branch_lesson_usage_",
            "code generation failed",
            "hypothesis generation failed",
            "material_difference_required_missing",
            "proposal block",
        )
    )


def _is_stale_source_failure(result: StepResult) -> bool:
    combined = " ".join(
        str(value or "")
        for value in (
            getattr(result, "reason", None),
            getattr(result, "failure_detail", None),
            getattr(result, "failure_category", None),
        )
    ).lower()
    return "stale_source" in combined


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


def _quality_block_ledger_entry(
    result: StepResult,
    *,
    sequence: int,
    loop_step: int,
    attempt_kind: str,
) -> dict[str, Any]:
    failure_reason = str(
        getattr(result, "failure_detail", None)
        or getattr(result, "reason", None)
        or ""
    )
    return {
        "schema_version": "quality_block_attempt.v1",
        "sequence": max(1, int(sequence)),
        "index": max(0, int(sequence) - 1),
        "branch_id": getattr(result, "branch_id", None),
        "hypothesis_id": getattr(result, "hypothesis_id", None),
        "attempt_kind": attempt_kind,
        "failure_stage": getattr(result, "failure_stage", None),
        "failure_category": (
            getattr(result, "failure_category", None)
            or _result_failure_category(result)
            or None
        ),
        "failure_reason": failure_reason,
        "source_result_reason": str(getattr(result, "reason", "") or ""),
        "counts_toward_max_rounds": bool(
            getattr(result, "counts_toward_max_rounds", True)
        ),
        "pre_protocol": _protocol_stage_for_result(result) == "",
        "loop_step": max(0, int(loop_step)),
        "recorded_at": datetime.now().isoformat(),
    }


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

    ``--rounds`` is the requested effective screened-round target, not the
    proposal-attempt ceiling.  By default the proposal cap includes bounded
    headroom for pre-screen repair/quality loops while still preventing
    unbounded proposal cycling.
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
    rounds = max(1, int(requested_rounds))
    return rounds + max(6, rounds * 2)


def _telemetry_repair_attempt_limit(
    *,
    configured: int | None,
) -> int:
    """Return the per-branch/per-mechanism telemetry repair cap."""
    if configured is not None:
        return max(1, int(configured))
    raw = os.environ.get("SCION_TELEMETRY_REPAIR_ATTEMPT_LIMIT")
    if raw:
        try:
            return max(1, int(raw))
        except ValueError:
            logger.warning(
                "Ignoring invalid SCION_TELEMETRY_REPAIR_ATTEMPT_LIMIT=%r",
                raw,
            )
    return 2


def _scheduler_active_slot_blocked_attempt_limit(requested_rounds: int) -> int:
    """Return the short cap for active-slot scheduler skips.

    Active-slot skips are resource-pressure observations, not research rounds.
    A tiny headroom lets slot reconciliation run without allowing a full
    campaign invocation to spin on a saturated scheduler.
    """
    return max(2, min(3, max(1, int(requested_rounds))))


def _fresh_runtime_replay_drain_limit(
    requested_rounds: int,
    *,
    configured: int | None,
) -> int:
    if configured is not None:
        return max(1, int(configured))
    raw = os.environ.get("SCION_FRESH_RUNTIME_REPLAY_DRAIN_LIMIT")
    if raw:
        try:
            return max(1, int(raw))
        except ValueError:
            logger.warning(
                "Ignoring invalid SCION_FRESH_RUNTIME_REPLAY_DRAIN_LIMIT=%r",
                raw,
            )
    return max(1, min(4, max(1, int(requested_rounds))))


def _stage_transition_drain_limit(
    requested_rounds: int,
    *,
    configured: int | None,
) -> int:
    if configured is not None:
        return max(0, int(configured))
    raw = os.environ.get("SCION_STAGE_TRANSITION_DRAIN_LIMIT")
    if raw:
        try:
            return max(0, int(raw))
        except ValueError:
            logger.warning(
                "Ignoring invalid SCION_STAGE_TRANSITION_DRAIN_LIMIT=%r",
                raw,
            )
    return max(1, min(4, max(1, int(requested_rounds))))


def _initial_proposal_attempts(
    getter: Callable[[], int] | None,
    *,
    fallback: int,
) -> int:
    if getter is None:
        return max(0, int(fallback))
    try:
        return max(0, int(getter()))
    except Exception as exc:  # pragma: no cover - defensive status path
        logger.debug("Failed to read initial proposal attempt count: %s", exc)
        return max(0, int(fallback))


def _fresh_runtime_replay_closure_status(result_metadata: Mapping[str, Any]) -> str:
    replay = result_metadata.get("fresh_runtime_replay")
    if isinstance(replay, Mapping):
        closure_status = str(replay.get("closure_status") or replay.get("status") or "")
        if closure_status:
            return closure_status
    failure_stage = str(result_metadata.get("failure_stage") or "")
    if failure_stage:
        return failure_stage
    return ""


_FRESH_RUNTIME_NO_SCHEDULABLE_REPLAY_CANDIDATE = (
    "pressure_no_schedulable_replay_candidate"
)
_LEGACY_FRESH_RUNTIME_NO_REPLAYABLE_CANDIDATE = "pressure_no_replayable_candidate"
_FRESH_RUNTIME_PRESSURE_NO_REPLAY_CANDIDATE_STATUSES = {
    _FRESH_RUNTIME_NO_SCHEDULABLE_REPLAY_CANDIDATE,
    _LEGACY_FRESH_RUNTIME_NO_REPLAYABLE_CANDIDATE,
}


def _fresh_runtime_replay_blocked_count(result_metadata: Mapping[str, Any]) -> int:
    if not result_metadata:
        return 0
    closure_status = _fresh_runtime_replay_closure_status(result_metadata)
    if (
        closure_status.startswith("blocked_")
        or closure_status in _FRESH_RUNTIME_PRESSURE_NO_REPLAY_CANDIDATE_STATUSES
    ):
        return 1
    return 0


def _fresh_runtime_replay_unresolved_closures(
    result_metadata: Mapping[str, Any],
) -> list[dict[str, Any]]:
    if _fresh_runtime_replay_blocked_count(result_metadata) == 0:
        return []
    replay = result_metadata.get("fresh_runtime_replay")
    replay_mapping = replay if isinstance(replay, Mapping) else {}
    closure_status = _fresh_runtime_replay_closure_status(result_metadata)
    return [
        {
            "branch_id": result_metadata.get("branch_id"),
            "closure_status": closure_status or "failed",
            "detail": (
                replay_mapping.get("detail")
                or result_metadata.get("failure_detail")
                or result_metadata.get("reason")
                or ""
            ),
            "attempt_kind": result_metadata.get("attempt_kind"),
            "scheduler_reason": result_metadata.get("scheduler_reason"),
        }
    ]


def _fresh_runtime_replay_drain_status(
    *,
    attempts: int,
    executed: int,
    skipped: int,
    stopped_reason: str,
    accepted_replay_last_result: Mapping[str, Any],
    final_attempt_last_result: Mapping[str, Any],
    blocked_count: int,
) -> str:
    if executed > 0:
        if blocked_count > 0:
            return "selected_blocked"
        closure_status = _fresh_runtime_replay_closure_status(
            accepted_replay_last_result
        )
        if closure_status in {
            "fresh_evidence_recorded",
            "closed",
            "complete",
            "completed",
            "succeeded",
            "success",
        }:
            return "selected_succeeded"
        if accepted_replay_last_result.get("failure_stage") or (
            accepted_replay_last_result.get("failure_detail")
        ):
            return "selected_failed"
        return "selected_executed"
    closure_status = _fresh_runtime_replay_closure_status(final_attempt_last_result)
    if closure_status in _FRESH_RUNTIME_PRESSURE_NO_REPLAY_CANDIDATE_STATUSES:
        return _FRESH_RUNTIME_NO_SCHEDULABLE_REPLAY_CANDIDATE
    if skipped > 0 or str(stopped_reason or "") == "no_fresh_runtime_replay_pending":
        return "not_selected_no_pending"
    if attempts > 0:
        return "not_selected"
    return "not_started"


def _stage_transition_drain_status(
    *,
    attempts: int,
    executed: int,
    skipped: int,
    stopped_reason: str,
    accepted_last_result: Mapping[str, Any],
    final_attempt_last_result: Mapping[str, Any],
) -> str:
    if executed > 0:
        if str(stopped_reason or "") == "stage_transition_drain_cap_exhausted":
            return "selected_cap_exhausted"
        if accepted_last_result.get("failure_stage") or (
            accepted_last_result.get("failure_detail")
        ):
            return "selected_failed"
        return "selected_executed"
    if skipped > 0:
        return "not_selected_no_pending"
    if str(stopped_reason or ""):
        return str(stopped_reason)
    if attempts > 0:
        return "not_selected"
    return "not_started"


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
    telemetry_repair_attempts: int,
    telemetry_repair_attempt_limit: int,
    telemetry_repair_attempt_counts: dict[str, int],
    branch_lifecycle_policy_blocks: int,
    branch_lifecycle_policy_block_limit: int,
    reconcile_lifecycle_steps: int,
    reconcile_lifecycle_step_limit: int,
    scheduler_active_slot_blocked_attempts: int,
    scheduler_active_slot_blocked_attempt_limit: int,
    fresh_runtime_replay_drain_attempts: int,
    fresh_runtime_replay_drain_executed: int,
    fresh_runtime_replay_drain_skipped: int,
    fresh_runtime_replay_drain_limit: int,
    fresh_runtime_replay_drain_stop_reason: str,
    fresh_runtime_replay_drain_last_metadata: dict[str, Any],
    fresh_runtime_replay_drain_accepted_metadata: dict[str, Any],
    fresh_runtime_replay_drain_final_metadata: dict[str, Any],
    stage_transition_drain_attempts: int,
    stage_transition_drain_executed: int,
    stage_transition_drain_skipped: int,
    stage_transition_drain_limit: int,
    stage_transition_drain_stop_reason: str,
    stage_transition_drain_last_metadata: dict[str, Any],
    stage_transition_drain_accepted_metadata: dict[str, Any],
    stage_transition_drain_final_metadata: dict[str, Any],
    proposal_quality_loop_limit: int,
    proposal_quality_blocked_attempts: int,
    legacy_total_rounds: int,
    formal_screened_candidates: int,
    protocol_evaluated_candidates: int,
    protocol_stage_counts: dict[str, int],
    quality_block_ledger: list[dict[str, Any]],
    failure_categories: dict[str, int],
    last_failure_category: str,
) -> dict[str, Any]:
    attempts_value = max(0, int(attempts))
    effective_rounds = max(0, int(counted_rounds))
    telemetry_diagnostic_attempts = max(
        0,
        int(telemetry_repairable_attempts)
        + int(validation_repair_required_attempts),
    )
    quality_blocks = max(0, int(proposal_quality_blocked_attempts))
    branch_lifecycle_blocks = max(0, int(branch_lifecycle_policy_blocks))
    reconcile_steps = max(0, int(reconcile_lifecycle_steps))
    active_slot_blocks = max(0, int(scheduler_active_slot_blocked_attempts))
    fresh_replay_drain_attempts = max(0, int(fresh_runtime_replay_drain_attempts))
    fresh_replay_drain_executed = max(0, int(fresh_runtime_replay_drain_executed))
    fresh_replay_drain_skipped = max(0, int(fresh_runtime_replay_drain_skipped))
    fresh_replay_drain_limit = max(1, int(fresh_runtime_replay_drain_limit))
    stage_drain_attempts = max(0, int(stage_transition_drain_attempts))
    stage_drain_executed = max(0, int(stage_transition_drain_executed))
    stage_drain_skipped = max(0, int(stage_transition_drain_skipped))
    stage_drain_limit = max(0, int(stage_transition_drain_limit))
    accepted_replay_last_result = dict(fresh_runtime_replay_drain_accepted_metadata)
    final_attempt_last_result = dict(fresh_runtime_replay_drain_final_metadata)
    legacy_last_result = dict(fresh_runtime_replay_drain_last_metadata)
    accepted_stage_last_result = dict(stage_transition_drain_accepted_metadata)
    final_stage_attempt_last_result = dict(stage_transition_drain_final_metadata)
    legacy_stage_last_result = dict(stage_transition_drain_last_metadata)
    closure_source_result = (
        accepted_replay_last_result
        if accepted_replay_last_result
        else final_attempt_last_result
    )
    fresh_replay_blocked_count = _fresh_runtime_replay_blocked_count(
        closure_source_result
    )
    fresh_replay_unresolved_closures = _fresh_runtime_replay_unresolved_closures(
        closure_source_result
    )
    fresh_replay_drain_status = _fresh_runtime_replay_drain_status(
        attempts=fresh_replay_drain_attempts,
        executed=fresh_replay_drain_executed,
        skipped=fresh_replay_drain_skipped,
        stopped_reason=fresh_runtime_replay_drain_stop_reason,
        accepted_replay_last_result=accepted_replay_last_result,
        final_attempt_last_result=final_attempt_last_result,
        blocked_count=fresh_replay_blocked_count,
    )
    stage_drain_status = _stage_transition_drain_status(
        attempts=stage_drain_attempts,
        executed=stage_drain_executed,
        skipped=stage_drain_skipped,
        stopped_reason=stage_transition_drain_stop_reason,
        accepted_last_result=accepted_stage_last_result,
        final_attempt_last_result=final_stage_attempt_last_result,
    )
    proposal_attempts_total = max(max(0, int(loop_steps)), attempts_value)
    protocol_stage_counts_value = {
        "screening": max(0, int(protocol_stage_counts.get("screening", 0))),
        "validation": max(0, int(protocol_stage_counts.get("validation", 0))),
        "frozen": max(0, int(protocol_stage_counts.get("frozen", 0))),
    }
    return {
        "requested_rounds": max(1, int(requested_rounds)),
        "attempt_limit": max(0, int(attempt_limit)),
        "proposal_attempt_limit": max(0, int(attempt_limit)),
        "attempts": attempts_value,
        "total_rounds": max(0, int(legacy_total_rounds)),
        "proposal_attempts": attempts_value,
        "proposal_attempts_consumed": attempts_value,
        "proposal_attempts_total": proposal_attempts_total,
        "loop_steps": max(0, int(loop_steps)),
        "campaign_steps": max(0, int(loop_steps)),
        "loop_step_limit": max(0, int(loop_step_limit)),
        "effective_rounds_completed": effective_rounds,
        "formal_screened_candidates": max(0, int(formal_screened_candidates)),
        "protocol_evaluated_candidates": max(
            0,
            int(protocol_evaluated_candidates),
        ),
        "protocol_stage_counts": protocol_stage_counts_value,
        "stage_transition_drain": {
            "schema_version": "stage_transition_drain.v1",
            "status": stage_drain_status,
            "attempts": stage_drain_attempts,
            "executed": stage_drain_executed,
            "skipped": stage_drain_skipped,
            "limit": stage_drain_limit,
            "stopped_reason": str(stage_transition_drain_stop_reason or ""),
            "last_result": legacy_stage_last_result,
            "accepted_stage_last_result": accepted_stage_last_result,
            "final_attempt_last_result": final_stage_attempt_last_result,
            "counts_toward_max_rounds": False,
            "generates_new_hypothesis": False,
        },
        "stage_transition_drain_status": stage_drain_status,
        "stage_transition_drain_attempts": stage_drain_attempts,
        "stage_transition_drain_executed": stage_drain_executed,
        "stage_transition_drain_skipped": stage_drain_skipped,
        "stage_transition_drain_limit": stage_drain_limit,
        "stage_transition_drain_stopped_reason": str(
            stage_transition_drain_stop_reason or ""
        ),
        "stage_transition_drain_accepted_stage_last_result": (
            accepted_stage_last_result
        ),
        "stage_transition_drain_final_attempt_last_result": (
            final_stage_attempt_last_result
        ),
        "max_rounds_budget_counter": "effective_rounds_completed",
        "max_rounds_semantics": (
            "requested_rounds limits effective_rounds_completed; "
            "proposal, repair, lifecycle, and active-slot scheduler attempts use "
            "separate counters"
        ),
        "telemetry_repairable_attempts": max(
            0,
            int(telemetry_repairable_attempts),
        ),
        "validation_repair_required_attempts": max(
            0,
            int(validation_repair_required_attempts),
        ),
        "telemetry_diagnostic_attempts": telemetry_diagnostic_attempts,
        "telemetry_repair_attempts": max(0, int(telemetry_repair_attempts)),
        "telemetry_repair_attempt_limit": max(
            1,
            int(telemetry_repair_attempt_limit),
        ),
        "telemetry_repair_attempts_by_branch_mechanism": dict(
            telemetry_repair_attempt_counts
        ),
        "branch_lifecycle_policy_blocks": branch_lifecycle_blocks,
        "branch_lifecycle_policy_block_limit": max(
            1,
            int(branch_lifecycle_policy_block_limit),
        ),
        "reconcile_lifecycle_steps": reconcile_steps,
        "reconcile_lifecycle_step_limit": max(
            1,
            int(reconcile_lifecycle_step_limit),
        ),
        "non_counted_lifecycle_steps": branch_lifecycle_blocks + reconcile_steps,
        "scheduler_active_slot_blocked_attempts": active_slot_blocks,
        "active_slot_blocked_attempts": active_slot_blocks,
        "scheduler_active_slot_blocked_attempt_limit": max(
            1,
            int(scheduler_active_slot_blocked_attempt_limit),
        ),
        "active_slot_blocked_attempt_limit": max(
            1,
            int(scheduler_active_slot_blocked_attempt_limit),
        ),
        "fresh_runtime_replay_drain": {
            "schema_version": "fresh_runtime_replay_drain.v1",
            "status": fresh_replay_drain_status,
            "attempts": fresh_replay_drain_attempts,
            "executed": fresh_replay_drain_executed,
            "skipped": fresh_replay_drain_skipped,
            "limit": fresh_replay_drain_limit,
            "stopped_reason": str(fresh_runtime_replay_drain_stop_reason or ""),
            "last_result": legacy_last_result,
            "accepted_replay_last_result": accepted_replay_last_result,
            "final_attempt_last_result": final_attempt_last_result,
            "blocked_count": fresh_replay_blocked_count,
            "unresolved_closures": fresh_replay_unresolved_closures,
            "counts_toward_max_rounds": False,
            "decision_features_excluded": True,
        },
        "fresh_runtime_replay_drain_status": fresh_replay_drain_status,
        "fresh_runtime_replay_drain_attempts": fresh_replay_drain_attempts,
        "fresh_runtime_replay_drain_executed": fresh_replay_drain_executed,
        "fresh_runtime_replay_drain_skipped": fresh_replay_drain_skipped,
        "fresh_runtime_replay_drain_limit": fresh_replay_drain_limit,
        "fresh_runtime_replay_drain_stopped_reason": str(
            fresh_runtime_replay_drain_stop_reason or ""
        ),
        "fresh_runtime_replay_drain_accepted_replay_last_result": (
            accepted_replay_last_result
        ),
        "fresh_runtime_replay_drain_final_attempt_last_result": (
            final_attempt_last_result
        ),
        "fresh_runtime_replay_drain_blocked_count": fresh_replay_blocked_count,
        "fresh_runtime_replay_drain_unresolved_closures": (
            fresh_replay_unresolved_closures
        ),
        "proposal_quality_loop_limit": max(1, int(proposal_quality_loop_limit)),
        "proposal_quality_limit": max(1, int(proposal_quality_loop_limit)),
        "proposal_quality_blocks_consumed": quality_blocks,
        "quality_blocks": quality_blocks,
        "quality_block_ledger": [dict(item) for item in quality_block_ledger],
        "quality_block_ledger_count": len(quality_block_ledger),
        "blocked_attempts": quality_blocks,
        "proposal_quality_blocks_remaining": max(
            0,
            int(proposal_quality_loop_limit)
            - int(proposal_quality_blocked_attempts),
        ),
        "failure_categories": dict(failure_categories),
        "infra_failure_attempts": sum(
            count
            for category, count in failure_categories.items()
            if category == "infra"
        ),
        "noninfra_failure_attempts": sum(
            count
            for category, count in failure_categories.items()
            if category != "infra"
        ),
        "last_failure_category": last_failure_category,
    }
