"""Campaign accounting helpers for status and summary payloads."""

from __future__ import annotations

import json
import logging
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

from scion.core.models import Decision, StepRecord
from scion.core.proposal_trajectory_attempts import read_proposal_attempt_transitions
from scion.core.evidence_recording.accounting_quality_blocks import (
    QUALITY_BLOCK_KINDS,
    quality_block_ledger as _quality_block_ledger,
)
from scion.core.public_refs import public_artifact_ref
from scion.core.telemetry_validation import (
    formal_screening_attempted,
    screened_experiment_effective,
)

logger = logging.getLogger(__name__)


DIRECT_CAMPAIGN_LOOP_SCHEMA = "scion.campaign_loop.direct_v1"


def is_direct_campaign_loop(loop_status: Mapping[str, Any] | None) -> bool:
    """Return whether *loop_status* is emitted by the direct-v3 loop."""

    return bool(
        isinstance(loop_status, Mapping)
        and loop_status.get("schema_version") == DIRECT_CAMPAIGN_LOOP_SCHEMA
    )


def direct_campaign_loop_facts(
    loop_status: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Project a direct-v3 loop status to unambiguous run facts only.

    The direct loop does not have APS proposal budgets, quality-block retry
    counters, or max-round consumption semantics.  Keeping those historical
    fields in current status artifacts makes a single scheduled provider path
    look like a retry controller.  Non-direct callers deliberately bypass this
    projection so old artifacts remain readable by the legacy accounting path.
    """

    if not is_direct_campaign_loop(loop_status):
        return dict(loop_status or {})
    loop = loop_status or {}
    stage_counts = _protocol_stage_counts_from_mapping(
        loop.get("protocol_stage_counts")
    )
    failure_categories = loop.get("failure_categories")
    facts: dict[str, Any] = {
        "schema_version": DIRECT_CAMPAIGN_LOOP_SCHEMA,
        "operator_requested_formal_rounds": _first_int(
            loop.get("operator_requested_formal_rounds"),
            loop.get("requested_rounds"),
            default=0,
        ),
        "completed_typed_protocol_rounds": _first_int(
            loop.get("completed_typed_protocol_rounds"),
            loop.get("effective_rounds_completed"),
            default=0,
        ),
        "scheduled_calls": _first_int(loop.get("scheduled_calls"), default=0),
        "formal_stage_counts": stage_counts,
        "formal_screened_candidates": _first_int(
            loop.get("formal_screened_candidates"), default=0
        ),
        "protocol_evaluated_candidates": _first_int(
            loop.get("protocol_evaluated_candidates"), default=0
        ),
    }
    # Stable fact aliases keep current readers working without reviving APS
    # budget semantics.  Each alias has exactly the direct meaning named above.
    facts["requested_rounds"] = facts["operator_requested_formal_rounds"]
    facts["effective_rounds_completed"] = facts[
        "completed_typed_protocol_rounds"
    ]
    facts["protocol_stage_counts"] = dict(facts["formal_stage_counts"])
    facts["protocol_metric_results"] = facts["protocol_evaluated_candidates"]
    if isinstance(failure_categories, Mapping):
        facts["failure_categories"] = {
            str(key): _first_int(value, default=0)
            for key, value in failure_categories.items()
        }
    else:
        facts["failure_categories"] = {}
    last_failure_category = str(loop.get("last_failure_category") or "")
    if last_failure_category:
        facts["last_failure_category"] = last_failure_category
    terminal_exception = loop.get("terminal_exception")
    if isinstance(terminal_exception, Mapping):
        facts["terminal_exception"] = dict(terminal_exception)
    return facts


def proposal_accounting_fields(
    *,
    campaign_dir: str | Path,
    steps: Iterable[StepRecord] = (),
    loop_status: Mapping[str, Any] | None = None,
    state: Mapping[str, Any] | None = None,
    round_num: int | None = None,
    screened_rounds: int | None = None,
) -> dict[str, Any]:
    """Return direct-only proposal accounting from durable attempt evidence."""
    step_list = list(steps)
    has_step_history = bool(step_list)
    loop = loop_status if isinstance(loop_status, Mapping) else {}
    state_map = state if isinstance(state, Mapping) else {}
    direct_attempts = _direct_attempt_accounting(campaign_dir)
    request_counts = dict(direct_attempts["request_kind_counts"])
    if is_direct_campaign_loop(loop):
        return _direct_campaign_accounting_fields(
            campaign_dir=campaign_dir,
            loop=loop,
            direct_attempts=direct_attempts,
            request_counts=request_counts,
        )
    campaign_steps = _first_int(
        loop.get("campaign_steps"),
        loop.get("loop_steps"),
        state_map.get("campaign_steps"),
        state_map.get("n_steps"),
        len(step_list) if step_list else None,
        round_num,
        default=0,
    )
    screened = _first_int(
        screened_rounds,
        state_map.get("screened_rounds"),
        state_map.get("screened_experiments"),
        default=0,
    )
    effective = _first_int(
        loop.get("effective_rounds_completed"),
        state_map.get("effective_rounds_completed"),
        default=sum(1 for step in step_list if _step_counts_effective(step))
        if has_step_history
        else 0,
    )
    unique_hypothesis_info = _unique_hypothesis_info(
        steps=step_list,
        loop=loop,
        state_map=state_map,
    )
    screened_not_effective = max(0, screened - effective)
    non_effective_screenings = _non_effective_screenings(
        steps=step_list,
        loop=loop,
        state_map=state_map,
        screened_not_effective=screened_not_effective,
    )
    quality_blocks = _first_int(
        loop.get("quality_blocks"),
        loop.get("proposal_quality_blocks_consumed"),
        state_map.get("quality_blocks"),
        default=0,
    )
    quality_block_ledger = _quality_block_ledger(
        steps=step_list,
        loop=loop,
        state_map=state_map,
        quality_blocks=quality_blocks,
    )
    active_slot_blocked_attempts = _first_int(
        loop.get("active_slot_blocked_attempts"),
        loop.get("scheduler_active_slot_blocked_attempts"),
        state_map.get("active_slot_blocked_attempts"),
        state_map.get("scheduler_active_slot_blocked_attempts"),
        # Legacy names retained only for reading older artifacts.
        loop.get("capacity_skip_attempts"),
        loop.get("scheduler_capacity_blocked_attempts"),
        state_map.get("scheduler_capacity_blocked_attempts"),
        default=0,
    )
    hypothesis_calls = _hypothesis_calls(request_counts)
    code_calls = _code_calls(request_counts)
    candidate_accounting = _candidate_accounting_fields(
        steps=step_list,
        loop=loop,
        state_map=state_map,
        campaign_steps=campaign_steps,
        round_num=round_num,
        screened_rounds=screened,
        campaign_dir=campaign_dir,
    )
    candidate_accounting["proposal_attempts_total"] = direct_attempts[
        "attempt_count"
    ]
    candidate_accounting["proposal_attempts_total_semantics"] = (
        "valid direct_v3 durable provider-call attempts from proposal attempt "
        "transitions; started-only interrupted calls are retained"
    )
    formal_candidate_artifact_count = candidate_accounting[
        "formal_candidate_artifact_count"
    ]
    research_accounting_breakdown = _research_accounting_breakdown(
        candidate_accounting=candidate_accounting,
        effective_rounds_completed=effective,
        unique_hypothesis_info=unique_hypothesis_info,
        hypothesis_calls=hypothesis_calls,
        code_calls=code_calls,
        request_counts=request_counts,
        quality_blocks=quality_blocks,
        quality_block_ledger_count=len(quality_block_ledger),
    )
    fields = {
        "campaign_accounting_schema_version": "campaign_accounting.v1",
        "campaign_steps": campaign_steps,
        "screened_rounds": screened,
        "screened_not_effective": screened_not_effective,
        "non_effective_screenings": non_effective_screenings,
        "non_effective_screening_count": len(non_effective_screenings),
        "quality_blocks": quality_blocks,
        "quality_block_ledger": quality_block_ledger,
        "quality_block_ledger_count": len(quality_block_ledger),
        "active_slot_blocked_attempts": active_slot_blocked_attempts,
        "scheduler_active_slot_blocked_attempts": active_slot_blocked_attempts,
        **candidate_accounting,
        "research_accounting_breakdown": research_accounting_breakdown,
        "unique_hypotheses": unique_hypothesis_info["count"],
        "unique_hypotheses_semantics": (
            "distinct hypothesis ids visible in step history or persisted "
            "state; unavailable means the artifact did not expose hypothesis "
            "identity, and this is not an LLM request/session counter"
        ),
        "formal_candidate_artifact_count": formal_candidate_artifact_count,
        "formal_candidate_artifact_count_semantics": (
            "formal_candidates/index.jsonl entries; this is a replayable "
            "formal candidate artifact subset, not the same as screening rows "
            "or legacy formal_screened_candidates"
        ),
        "hypothesis_calls": hypothesis_calls,
        "hypothesis_calls_semantics": (
            "durable direct hypothesis provider-call attempts"
        ),
        "code_calls": code_calls,
        "code_calls_semantics": (
            "durable direct code provider-call attempts"
        ),
        "llm_request_kind_counts": dict(request_counts),
        "llm_request_kind_counts_semantics": (
            "direct attempt-transition counts by provider-call phase; counts do "
            "not imply unique hypotheses, formal candidates, or protocol rows"
        ),
        "proposal_attempt_source": direct_attempts["source"],
        "unsupported_historical_sources": direct_attempts[
            "unsupported_historical_sources"
        ],
    }
    return fields


def _direct_attempt_accounting(campaign_dir: str | Path) -> dict[str, Any]:
    campaign_path = Path(campaign_dir)
    inventory = read_proposal_attempt_transitions(campaign_path / "scion.db")
    stats = inventory.get("stats") if isinstance(inventory, Mapping) else {}
    attempts = inventory.get("attempts") if isinstance(inventory, Mapping) else []
    attempts = attempts if isinstance(attempts, list) else []
    counts = Counter(
        str(attempt.get("terminal_phase") or "")
        for attempt in attempts
        if isinstance(attempt, Mapping)
        and str(attempt.get("terminal_phase") or "") in {"hypothesis", "code"}
    )
    return {
        "attempt_count": int((stats or {}).get("attempt_count") or 0),
        "request_kind_counts": {
            "hypothesis": counts["hypothesis"],
            "code": counts["code"],
        },
        "source": {
            "schema_version": "direct_proposal_accounting_source.v1",
            "artifact_ref": "scion.db",
            "event_kind": "proposal_attempt_transition",
            "status": str((stats or {}).get("source_status") or "missing"),
            "invalid_row_count": int((stats or {}).get("invalid_row_count") or 0),
        },
        "unsupported_historical_sources": [],
    }


def _direct_campaign_accounting_fields(
    *,
    campaign_dir: str | Path | None,
    loop: Mapping[str, Any],
    direct_attempts: Mapping[str, Any],
    request_counts: Mapping[str, int],
) -> dict[str, Any]:
    """Build the current direct-v3 accounting surface from durable facts."""

    loop_facts = direct_campaign_loop_facts(loop)
    index_info = _formal_candidates_index_info(campaign_dir)
    hypothesis_attempts = _hypothesis_calls(request_counts)
    code_attempts = _code_calls(request_counts)
    durable_attempts = int(direct_attempts.get("attempt_count") or 0)
    return {
        "campaign_accounting_schema_version": "campaign_accounting.direct_v1",
        **{
            key: value
            for key, value in loop_facts.items()
            if key != "schema_version"
        },
        "formal_candidate_artifact_count": index_info.get("count"),
        "durable_hypothesis_attempts": hypothesis_attempts,
        "durable_code_attempts": code_attempts,
        "durable_provider_call_attempts": durable_attempts,
        # Stable aliases retained because current report readers already use
        # them.  Their values are exclusively the durable direct-call facts.
        "hypothesis_calls": hypothesis_attempts,
        "code_calls": code_attempts,
        "proposal_attempts_total": durable_attempts,
        "llm_request_kind_counts": {
            "hypothesis": hypothesis_attempts,
            "code": code_attempts,
        },
        "proposal_attempt_source": direct_attempts["source"],
    }


def accounting_reconciliation_fields(
    *,
    steps: Iterable[StepRecord] = (),
    loop_status: Mapping[str, Any] | None = None,
    state: Mapping[str, Any] | None = None,
    round_num: int | None = None,
    screened_rounds: int | None = None,
    effective_rounds_completed: int | None = None,
    counted_experiment_steps: int | None = None,
    campaign_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Return a compact audit trail explaining run-level counter differences."""
    step_list = list(steps)
    has_step_history = bool(step_list)
    loop = loop_status if isinstance(loop_status, Mapping) else {}
    state_map = state if isinstance(state, Mapping) else {}
    if is_direct_campaign_loop(loop):
        direct_attempts = (
            _direct_attempt_accounting(campaign_dir)
            if campaign_dir is not None
            else {
                "attempt_count": 0,
                "request_kind_counts": {"hypothesis": 0, "code": 0},
                "source": {
                    "schema_version": "direct_proposal_accounting_source.v1",
                    "artifact_ref": "scion.db",
                    "event_kind": "proposal_attempt_transition",
                    "status": "missing",
                    "invalid_row_count": 0,
                },
            }
        )
        return {
            "schema_version": "campaign_accounting_reconciliation.direct_v1",
            **_direct_campaign_accounting_fields(
                campaign_dir=campaign_dir,
                loop=loop,
                direct_attempts=direct_attempts,
                request_counts=dict(direct_attempts["request_kind_counts"]),
            ),
        }
    failure_categories = _merged_failure_categories(loop, state_map)

    requested_rounds = _first_int(
        loop.get("requested_rounds"),
        state_map.get("requested_rounds"),
        default=0,
    )
    total_rounds = _first_int(
        loop.get("total_rounds"),
        state_map.get("total_rounds"),
        round_num,
        default=0,
    )
    campaign_steps = _first_int(
        loop.get("campaign_steps"),
        loop.get("loop_steps"),
        state_map.get("campaign_steps"),
        state_map.get("n_steps"),
        len(step_list) if step_list else None,
        default=0,
    )
    screened = _first_int(
        screened_rounds,
        state_map.get("screened_rounds"),
        state_map.get("screened_experiments"),
        default=0,
    )
    counted = _first_int(
        counted_experiment_steps,
        loop.get("effective_rounds_completed") if not has_step_history else None,
        state_map.get("effective_rounds_completed") if not has_step_history else None,
        default=(
            sum(1 for step in step_list if _step_counts_effective(step))
            if has_step_history
            else 0
        ),
    )
    effective = _first_int(
        effective_rounds_completed,
        loop.get("effective_rounds_completed"),
        state_map.get("effective_rounds_completed"),
        counted,
        default=0,
    )
    accepted = _first_int(
        state_map.get("accepted_experiments") if not has_step_history else None,
        default=sum(1 for step in step_list if _step_accepted(step)),
    )
    accepted_screening = _first_int(
        state_map.get("accepted_screening_experiments")
        if not has_step_history
        else None,
        default=sum(1 for step in step_list if _step_accepted_screening(step)),
    )
    promoted = _first_int(
        state_map.get("promoted_experiments") if not has_step_history else None,
        default=sum(
            1
            for step in step_list
            if _decision_value(step) == Decision.PROMOTE.value
        ),
    )
    model_repair_attempts = _first_int(
        loop.get("model_repair_attempts"),
        loop.get("code_repair_attempts"),
        state_map.get("model_repair_attempts"),
        state_map.get("code_repair_attempts"),
        default=0,
    )
    model_repair_failures = _model_repair_failures(failure_categories)
    quality_blocks = _first_int(
        loop.get("quality_blocks"),
        loop.get("proposal_quality_blocks_consumed"),
        state_map.get("quality_blocks"),
        default=sum(
            1 for step in step_list if _attempt_kind(step) in QUALITY_BLOCK_KINDS
        ),
    )
    quality_block_ledger = _quality_block_ledger(
        steps=step_list,
        loop=loop,
        state_map=state_map,
        quality_blocks=quality_blocks,
    )
    active_slot_blocked_attempts = _first_int(
        loop.get("active_slot_blocked_attempts"),
        loop.get("scheduler_active_slot_blocked_attempts"),
        state_map.get("active_slot_blocked_attempts"),
        state_map.get("scheduler_active_slot_blocked_attempts"),
        # Legacy names retained only for reading older artifacts.
        loop.get("capacity_skip_attempts"),
        loop.get("scheduler_capacity_blocked_attempts"),
        state_map.get("scheduler_capacity_blocked_attempts"),
        default=sum(
            1
            for step in step_list
            if _attempt_kind(step) == "scheduler_active_slot_blocked"
        ),
    )
    reconcile_lifecycle_steps = _first_int(
        loop.get("reconcile_lifecycle_steps"),
        state_map.get("reconcile_lifecycle_steps"),
        default=sum(
            1 for step in step_list if _attempt_kind(step) == "reconcile_lifecycle"
        ),
    )
    non_counted_lifecycle_steps = _first_int(
        loop.get("non_counted_lifecycle_steps"),
        state_map.get("non_counted_lifecycle_steps"),
        reconcile_lifecycle_steps,
        default=0,
    )
    screened_not_effective = max(0, screened - effective)
    non_effective_screenings = _non_effective_screenings(
        steps=step_list,
        loop=loop,
        state_map=state_map,
        screened_not_effective=screened_not_effective,
    )
    unique_hypothesis_info = _unique_hypothesis_info(
        steps=step_list,
        loop=loop,
        state_map=state_map,
    )
    loop_counted_delta = (
        effective - counted
        if has_step_history or counted_experiment_steps is not None
        else 0
    )
    state_screened_delta = (
        max(0, screened - sum(1 for step in step_list if _step_screened(step)))
        if has_step_history
        else 0
    )
    reconciliation_notes = _reconciliation_notes(
        screened_not_effective=screened_not_effective,
        loop_counted_delta=loop_counted_delta,
        state_screened_delta=state_screened_delta,
        quality_blocks=quality_blocks,
        non_counted_lifecycle_steps=non_counted_lifecycle_steps,
    )
    candidate_accounting = _candidate_accounting_fields(
        steps=step_list,
        loop=loop,
        state_map=state_map,
        campaign_steps=campaign_steps,
        round_num=round_num,
        screened_rounds=screened,
        campaign_dir=campaign_dir,
    )
    direct_attempts = (
        _direct_attempt_accounting(campaign_dir)
        if campaign_dir is not None
        else {
            "attempt_count": 0,
            "request_kind_counts": {"hypothesis": 0, "code": 0},
            "source": {
                "schema_version": "direct_proposal_accounting_source.v1",
                "artifact_ref": "scion.db",
                "event_kind": "proposal_attempt_transition",
                "status": "missing",
                "invalid_row_count": 0,
            },
            "unsupported_historical_sources": [],
        }
    )
    request_counts = dict(direct_attempts["request_kind_counts"])
    proposal_attempts = direct_attempts["attempt_count"]
    candidate_accounting["proposal_attempts_total"] = proposal_attempts
    candidate_accounting["proposal_attempts_total_semantics"] = (
        "valid direct_v3 durable provider-call attempts from proposal attempt "
        "transitions; started-only interrupted calls are retained"
    )
    hypothesis_calls = _hypothesis_calls(request_counts)
    code_calls = _code_calls(request_counts)
    research_accounting_breakdown = _research_accounting_breakdown(
        candidate_accounting=candidate_accounting,
        effective_rounds_completed=effective,
        unique_hypothesis_info=unique_hypothesis_info,
        hypothesis_calls=hypothesis_calls,
        code_calls=code_calls,
        request_counts=request_counts,
        quality_blocks=quality_blocks,
        quality_block_ledger_count=len(quality_block_ledger),
    )
    return {
        "schema_version": "campaign_accounting_reconciliation.v1",
        "requested_rounds": requested_rounds,
        "total_rounds": total_rounds,
        "campaign_steps": campaign_steps,
        "proposal_attempts": proposal_attempts,
        "proposal_attempts_consumed": proposal_attempts,
        "proposal_attempt_source": direct_attempts["source"],
        "unsupported_historical_sources": direct_attempts[
            "unsupported_historical_sources"
        ],
        **candidate_accounting,
        "research_accounting_breakdown": research_accounting_breakdown,
        "unique_hypotheses": unique_hypothesis_info["count"],
        "formal_candidate_artifact_count": candidate_accounting[
            "formal_candidate_artifact_count"
        ],
        "effective_rounds_completed": effective,
        "screened_rounds": screened,
        "screened_experiments": screened,
        "counted_experiment_steps": counted,
        "accepted_experiments": accepted,
        "accepted_screening_experiments": accepted_screening,
        "promoted_experiments": promoted,
        "screened_minus_effective": screened_not_effective,
        "non_effective_screenings": non_effective_screenings,
        "non_effective_screening_count": len(non_effective_screenings),
        "effective_minus_counted_step_records": loop_counted_delta,
        "state_screened_minus_step_screened": state_screened_delta,
        "model_repair_attempts": model_repair_attempts,
        "model_repair_failures": model_repair_failures,
        "quality_blocks": quality_blocks,
        "quality_block_ledger": quality_block_ledger,
        "quality_block_ledger_count": len(quality_block_ledger),
        "active_slot_blocked_attempts": active_slot_blocked_attempts,
        "scheduler_active_slot_blocked_attempts": active_slot_blocked_attempts,
        "reconcile_lifecycle_steps": reconcile_lifecycle_steps,
        "non_counted_lifecycle_steps": non_counted_lifecycle_steps,
        "attempt_breakdown": {
            "proposal_attempts_total": candidate_accounting[
                "proposal_attempts_total"
            ],
            "effective_protocol_rounds": candidate_accounting[
                "effective_protocol_rounds"
            ],
            "formal_screened_candidates": candidate_accounting[
                "formal_screened_candidates"
            ],
            "protocol_evaluated_candidates": candidate_accounting[
                "protocol_evaluated_candidates"
            ],
            "protocol_metric_results": candidate_accounting[
                "protocol_metric_results"
            ],
            "validation_protocol_results": candidate_accounting[
                "validation_protocol_results"
            ],
            "frozen_protocol_results": candidate_accounting[
                "frozen_protocol_results"
            ],
            "verification_consumed_candidates": candidate_accounting[
                "verification_consumed_candidates"
            ],
            "verification_failure_consumed_candidates": candidate_accounting[
                "verification_failure_consumed_candidates"
            ],
            "effective_screenings": effective,
            "screened_not_effective": screened_not_effective,
            "non_effective_screening_count": len(non_effective_screenings),
            "accepted": accepted,
            "model_repair": model_repair_attempts,
            "model_repair_failures": model_repair_failures,
            "proposal_quality_blocks": candidate_accounting[
                "proposal_quality_blocks"
            ],
            "quality_blocks": quality_blocks,
            "quality_block_ledger_count": len(quality_block_ledger),
            "active_slot_blocked_attempts": active_slot_blocked_attempts,
            "scheduler_active_slot_blocked_attempts": active_slot_blocked_attempts,
            "reconcile_lifecycle_steps": reconcile_lifecycle_steps,
        },
        "reconciliation": reconciliation_notes,
    }


_PROTOCOL_STAGE_KEYS = ("screening", "validation", "frozen")


def _non_effective_screenings(
    *,
    steps: list[StepRecord],
    loop: Mapping[str, Any],
    state_map: Mapping[str, Any],
    screened_not_effective: int,
) -> list[dict[str, Any]]:
    for source in (
        loop.get("non_effective_screenings"),
        state_map.get("non_effective_screenings"),
    ):
        ledger = _normalized_mapping_ledger(source)
        if ledger:
            return _complete_non_effective_screening_ledger(
                ledger,
                screened_not_effective,
            )
    ledger = _non_effective_screenings_from_steps(steps)
    if ledger:
        return ledger
    if screened_not_effective <= 0:
        return []
    return _aggregate_non_effective_screening_entries(
        start=0,
        count=screened_not_effective,
    )


def _non_effective_screenings_from_steps(
    steps: Iterable[StepRecord],
) -> list[dict[str, Any]]:
    ledger: list[dict[str, Any]] = []
    for step in steps:
        protocol = getattr(step, "protocol_result", None)
        if not formal_screening_attempted(protocol):
            continue
        if screened_experiment_effective(protocol):
            continue
        sequence = len(ledger) + 1
        reason_codes = list(getattr(protocol, "reason_codes", ()) or ())
        decision_codes = list(getattr(step, "decision_reason_codes", ()) or ())
        ledger.append(
            {
                "schema_version": "non_effective_screening.v1",
                "sequence": sequence,
                "index": sequence - 1,
                "branch_id": getattr(step, "branch_id", None),
                "hypothesis_id": getattr(step, "hypothesis_id", None),
                "reason_codes": list(dict.fromkeys([*reason_codes, *decision_codes])),
                "decision": _decision_value(step) or None,
                "protocol_stage": _stage_value(step),
                "raw_metrics_ref": getattr(protocol, "raw_metrics_ref", None),
                "effective": False,
                "attempt_kind": _attempt_kind(step),
                "loop_step": getattr(step, "round_num", None),
                "source": "step_history",
            }
        )
    return ledger


def _normalized_mapping_ledger(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _complete_non_effective_screening_ledger(
    items: list[dict[str, Any]],
    screened_not_effective: int,
) -> list[dict[str, Any]]:
    normalized = _with_sequence(items)
    missing = max(0, int(screened_not_effective) - len(normalized))
    if missing:
        normalized.extend(
            _aggregate_non_effective_screening_entries(
                start=len(normalized),
                count=missing,
            )
        )
    return _with_sequence(normalized)


def _aggregate_non_effective_screening_entries(
    *,
    start: int,
    count: int,
) -> list[dict[str, Any]]:
    return [
        {
            "schema_version": "non_effective_screening.v1",
            "sequence": index + 1,
            "index": index,
            "branch_id": None,
            "hypothesis_id": None,
            "reason_codes": [
                "screened_formal_results_excluded_from_effective_rounds"
            ],
            "decision": None,
            "protocol_stage": "screening",
            "raw_metrics_ref": None,
            "effective": False,
            "source": "aggregate_reconciliation",
        }
        for index in range(max(0, int(start)), max(0, int(start)) + max(0, int(count)))
    ]


def _with_sequence(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        entry = dict(item)
        entry.setdefault("sequence", index + 1)
        entry.setdefault("index", index)
        normalized.append(entry)
    return normalized


def _candidate_accounting_fields(
    *,
    steps: list[StepRecord],
    loop: Mapping[str, Any],
    state_map: Mapping[str, Any],
    campaign_steps: int,
    round_num: int | None,
    screened_rounds: int,
    campaign_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Return stable run-level candidate counters with explicit semantics."""
    has_step_history = bool(steps)
    step_protocol_stage_counts = _protocol_stage_counts_from_steps(steps)
    legacy_stage_count_fallbacks = (
        ()
        if has_step_history
        else (
            _protocol_stage_counts_from_mapping(state_map.get("protocol_stage_counts")),
            _protocol_stage_counts_from_mapping(loop.get("protocol_stage_counts")),
        )
    )
    protocol_metric_stage_counts = _merged_protocol_stage_counts(
        step_protocol_stage_counts,
        _protocol_stage_counts_from_mapping(
            state_map.get("protocol_metric_stage_counts")
        ),
        _protocol_stage_counts_from_mapping(loop.get("protocol_metric_stage_counts")),
        *legacy_stage_count_fallbacks,
    )
    stage_counts = _merged_protocol_stage_counts(
        step_protocol_stage_counts,
        _protocol_stage_counts_from_mapping(state_map.get("protocol_stage_counts")),
        _protocol_stage_counts_from_mapping(loop.get("protocol_stage_counts")),
    )
    step_protocol_count = sum(step_protocol_stage_counts.values())
    step_formal_screened = _formal_screened_candidate_count_from_steps(steps)
    protocol_metric_results = _first_int(
        loop.get("protocol_metric_results"),
        state_map.get("protocol_metric_results"),
        default=(
            step_protocol_count
            if has_step_history
            else sum(protocol_metric_stage_counts.values())
        ),
    )
    screening_protocol_results = _first_int(
        loop.get("screening_protocol_results"),
        state_map.get("screening_protocol_results"),
        default=protocol_metric_stage_counts["screening"],
    )
    validation_protocol_results = _first_int(
        loop.get("validation_protocol_results"),
        state_map.get("validation_protocol_results"),
        default=protocol_metric_stage_counts["validation"],
    )
    frozen_protocol_results = _first_int(
        loop.get("frozen_protocol_results"),
        state_map.get("frozen_protocol_results"),
        default=protocol_metric_stage_counts["frozen"],
    )
    legacy_attempts = _first_int(
        loop.get("proposal_attempts_consumed"),
        loop.get("proposal_attempts"),
        state_map.get("proposal_attempts_consumed"),
        state_map.get("proposal_attempts"),
        round_num,
        default=0,
    )
    proposal_attempts_total = _first_int(
        loop.get("proposal_attempts_total"),
        state_map.get("proposal_attempts_total"),
        default=max(legacy_attempts, campaign_steps),
    )
    if has_step_history:
        formal_default = step_formal_screened
    else:
        formal_default = screened_rounds
    formal_screened_candidates = _first_int(
        loop.get("formal_screened_candidates"),
        state_map.get("formal_screened_candidates"),
        default=formal_default,
    )
    legacy_formal_screened_candidates = formal_screened_candidates
    formal_screened_candidates = min(
        max(0, formal_screened_candidates),
        max(0, screening_protocol_results),
    )
    protocol_default = (
        max(step_protocol_count, protocol_metric_results)
        if has_step_history
        else max(sum(stage_counts.values()), protocol_metric_results)
    )
    protocol_evaluated_candidates = _first_int(
        loop.get("protocol_evaluated_candidates"),
        state_map.get("protocol_evaluated_candidates"),
        default=protocol_default,
    )
    legacy_protocol_evaluated_candidates = protocol_evaluated_candidates
    protocol_evaluated_candidates = min(
        max(0, protocol_evaluated_candidates),
        max(0, protocol_metric_results),
    )
    if protocol_evaluated_candidates > sum(stage_counts.values()):
        inferred_screening = max(
            stage_counts["screening"],
            protocol_evaluated_candidates
            - stage_counts["validation"]
            - stage_counts["frozen"],
        )
        stage_counts["screening"] = inferred_screening
    effective_rounds_completed = _first_int(
        loop.get("effective_rounds_completed"),
        state_map.get("effective_rounds_completed"),
        default=(
            sum(1 for step in steps if _step_counts_effective(step))
            if has_step_history
            else 0
        ),
    )
    effective_protocol_rounds = _first_int(
        loop.get("effective_protocol_rounds"),
        state_map.get("effective_protocol_rounds"),
        default=(
            sum(1 for step in steps if _step_counts_effective(step))
            if has_step_history
            else protocol_metric_results
        ),
    )
    verification_failure_consumed_candidates = _first_int(
        loop.get("verification_failure_consumed_candidates"),
        state_map.get("verification_failure_consumed_candidates"),
        default=sum(
            1
            for step in steps
            if _verification_failure_consumed_candidate(step)
        )
        if has_step_history
        else max(0, effective_rounds_completed - protocol_metric_results),
    )
    verification_consumed_candidates = _first_int(
        loop.get("verification_consumed_candidates"),
        state_map.get("verification_consumed_candidates"),
        default=(
            _verification_consumed_candidate_count_from_steps(steps)
            if has_step_history
            else effective_rounds_completed
        ),
    )
    proposal_quality_blocks = _first_int(
        loop.get("proposal_quality_blocks"),
        loop.get("proposal_quality_blocks_consumed"),
        loop.get("quality_blocks"),
        state_map.get("proposal_quality_blocks"),
        state_map.get("quality_blocks"),
        default=0,
    )
    formal_candidate_reconciliation = _formal_candidate_count_reconciliation(
        campaign_dir=campaign_dir,
        formal_screened_candidates=formal_screened_candidates,
        screening_protocol_results=screening_protocol_results,
        protocol_evaluated_candidates=protocol_evaluated_candidates,
        protocol_metric_results=protocol_metric_results,
    )
    formal_candidate_artifact_count = formal_candidate_reconciliation.get(
        "formal_candidates_index_count"
    )
    return {
        "proposal_attempts_total": proposal_attempts_total,
        "proposal_attempts_total_semantics": (
            "total proposal-attempt budget events reported by the campaign "
            "loop; includes proposal quality blocks and internal proposal "
            "retries when the loop accounts them, and is not a count of unique "
            "hypotheses, protocol metric rows, or formal candidate artifacts"
        ),
        "effective_protocol_rounds": effective_protocol_rounds,
        "effective_protocol_rounds_semantics": (
            "completed protocol rows that count toward the max-round budget; "
            "validation and frozen rows may be included when counted; "
            "verification-only failures are reported separately"
        ),
        "formal_screened_candidates": formal_screened_candidates,
        "protocol_evaluated_candidates": protocol_evaluated_candidates,
        "protocol_metric_results": protocol_metric_results,
        "screening_protocol_results": screening_protocol_results,
        "validation_protocol_results": validation_protocol_results,
        "frozen_protocol_results": frozen_protocol_results,
        "verification_consumed_candidates": verification_consumed_candidates,
        "verification_failure_consumed_candidates": (
            verification_failure_consumed_candidates
        ),
        "proposal_quality_blocks": proposal_quality_blocks,
        "protocol_metric_stage_counts": protocol_metric_stage_counts,
        "protocol_stage_counts": stage_counts,
        "formal_candidate_count_reconciliation": (
            formal_candidate_reconciliation
        ),
        "candidate_count_reconciliation": formal_candidate_reconciliation,
        "legacy_formal_screened_candidates_reported": (
            legacy_formal_screened_candidates
        ),
        "legacy_protocol_evaluated_candidates_reported": (
            legacy_protocol_evaluated_candidates
        ),
        "formal_candidate_artifact_count": formal_candidate_artifact_count,
        "max_rounds_budget_counter": "effective_rounds_completed",
        "effective_rounds_completed_semantics": (
            "legacy max-round completion counter; may include consumed "
            "verification-only candidate failures in addition to counted "
            "protocol rows, so use effective_protocol_rounds when comparing "
            "only protocol metrics"
        ),
        "max_rounds_semantics": (
            "requested_rounds limits effective_rounds_completed; proposal, "
            "quality-blocked proposal, validation, frozen, reconcile, and "
            "active-slot scheduler attempts are reported separately"
        ),
        "formal_screened_candidates_semantics": (
            "legacy screening candidate counter retained for compatibility; use "
            "screening_protocol_results for actual screening metrics rows and "
            "verification_consumed_candidates for max-round candidate attempts"
        ),
        "protocol_evaluated_candidates_semantics": (
            "legacy evaluated-candidate counter retained for compatibility and "
            "may include older run-loop candidate attempts; use "
            "protocol_metric_results as the actual protocol metric-row total "
            "and validation_protocol_results and frozen_protocol_results as "
            "explicit breakdowns"
        ),
        "protocol_metric_results_semantics": (
            "actual completed protocol metrics results/rows across screening, "
            "validation, and frozen; verification-only "
            "failures and proposal quality blocks are excluded"
        ),
        "verification_consumed_candidates_semantics": (
            "candidate attempts that consumed the effective max-round budget at "
            "or after verification; includes verification-only heavy failures "
            "attempts"
        ),
        "validation_protocol_results_semantics": (
            "validation-stage protocol metric results; not screening rounds"
        ),
        "frozen_protocol_results_semantics": (
            "frozen holdout protocol metric results; not screening rounds"
        ),
        "proposal_quality_blocks_semantics": (
            "proposal/schema quality blocks that consumed proposal attempts but "
            "did not produce verification or protocol metrics"
        ),
    }


def _research_accounting_breakdown(
    *,
    candidate_accounting: Mapping[str, Any],
    effective_rounds_completed: int,
    unique_hypothesis_info: Mapping[str, Any],
    hypothesis_calls: int,
    code_calls: int,
    request_counts: Mapping[str, int],
    quality_blocks: int,
    quality_block_ledger_count: int,
) -> dict[str, Any]:
    formal_reconciliation = candidate_accounting.get(
        "formal_candidate_count_reconciliation"
    )
    formal_reconciliation_map = (
        formal_reconciliation if isinstance(formal_reconciliation, Mapping) else {}
    )
    formal_candidate_artifact_count = candidate_accounting.get(
        "formal_candidate_artifact_count"
    )
    return {
        "schema_version": "research_accounting_breakdown.v1",
        "purpose": (
            "disambiguate proposal sessions, unique hypotheses, protocol rows, "
            "screening/holdout rows, and formal candidate artifacts"
        ),
        "proposal_attempts": {
            "proposal_attempts_total": candidate_accounting.get(
                "proposal_attempts_total"
            ),
            "quality_blocks": quality_blocks,
            "quality_block_ledger_count": quality_block_ledger_count,
            "semantics": candidate_accounting.get(
                "proposal_attempts_total_semantics"
            ),
        },
        "llm_requests": {
            "llm_request_kind_counts": dict(request_counts),
            "hypothesis_calls": hypothesis_calls,
            "code_calls": code_calls,
            "semantics": (
                "trace-level request counts; hypothesis/code retries and "
                "internal repair calls do not imply unique hypotheses or "
                "formal candidates"
            ),
        },
        "hypotheses": {
            "unique_hypotheses": unique_hypothesis_info.get("count"),
            "available": bool(unique_hypothesis_info.get("available")),
            "source": unique_hypothesis_info.get("source"),
            "unique_hypothesis_ids": list(unique_hypothesis_info.get("ids") or []),
            "semantics": (
                "distinct hypothesis identities when available; not inferred "
                "from LLM request counts or proposal session counts"
            ),
        },
        "protocol_rows": {
            "effective_protocol_rounds": candidate_accounting.get(
                "effective_protocol_rounds"
            ),
            "effective_rounds_completed": effective_rounds_completed,
            "protocol_metric_results": candidate_accounting.get(
                "protocol_metric_results"
            ),
            "screening_protocol_results": candidate_accounting.get(
                "screening_protocol_results"
            ),
            "validation_protocol_results": candidate_accounting.get(
                "validation_protocol_results"
            ),
            "frozen_protocol_results": candidate_accounting.get(
                "frozen_protocol_results"
            ),
            "protocol_metric_stage_counts": dict(
                candidate_accounting.get("protocol_metric_stage_counts") or {}
            ),
            "semantics": (
                "completed protocol metric rows, split by stage; validation and "
                "frozen rows are not new hypotheses"
            ),
        },
        "legacy_candidate_counters": {
            "formal_screened_candidates": candidate_accounting.get(
                "formal_screened_candidates"
            ),
            "protocol_evaluated_candidates": candidate_accounting.get(
                "protocol_evaluated_candidates"
            ),
            "verification_consumed_candidates": candidate_accounting.get(
                "verification_consumed_candidates"
            ),
            "verification_failure_consumed_candidates": candidate_accounting.get(
                "verification_failure_consumed_candidates"
            ),
            "semantics": (
                "backward-compatible counters; prefer protocol_rows and "
                "formal_candidate_artifacts for row/artifact comparisons"
            ),
        },
        "formal_candidate_artifacts": {
            "formal_candidate_artifact_count": formal_candidate_artifact_count,
            "status": formal_reconciliation_map.get(
                "formal_candidates_index_status"
            ),
            "artifact_ref": formal_reconciliation_map.get(
                "formal_candidates_index_ref"
            ),
            "semantics": (
                "formal_candidates/index.jsonl artifact entries; this is a "
                "replayable artifact subset and not equivalent to screening "
                "protocol rows or unique hypotheses"
            ),
        },
        "reconciliation_refs": {
            "formal_candidate_count_reconciliation": (
                "formal_candidate_count_reconciliation"
            ),
            "candidate_count_reconciliation": "candidate_count_reconciliation",
            "accounting_reconciliation": "accounting_reconciliation",
        },
    }


def _formal_candidate_count_reconciliation(
    *,
    campaign_dir: str | Path | None,
    formal_screened_candidates: int,
    screening_protocol_results: int,
    protocol_evaluated_candidates: int,
    protocol_metric_results: int,
) -> dict[str, Any]:
    """Explain count differences between loop, protocol rows, and artifacts."""
    index_info = _formal_candidates_index_info(campaign_dir)
    differences: list[dict[str, Any]] = []
    omitted_reasons: list[str] = []

    screening_delta = screening_protocol_results - formal_screened_candidates
    if screening_delta:
        differences.append(
            {
                "relation": (
                    "db_screening_rows_minus_warehouse_formal_screened_candidates"
                ),
                "delta": screening_delta,
                "primary_reason": (
                    "screening_protocol_results_include_non_effective_or_"
                    "non_counted_screening_rows"
                )
                if screening_delta > 0
                else "warehouse_counter_exceeds_visible_screening_protocol_rows",
            }
        )
        if screening_delta > 0:
            omitted_reasons.append(
                "formal_screened_candidates_excludes_non_effective_or_non_counted_screening_rows"
            )

    protocol_delta = protocol_evaluated_candidates - protocol_metric_results
    if protocol_delta:
        differences.append(
            {
                "relation": (
                    "protocol_evaluated_candidates_minus_protocol_metric_results"
                ),
                "delta": protocol_delta,
                "primary_reason": (
                    "legacy_protocol_evaluated_candidates_may_include_attempts_"
                    "without_completed_protocol_metric_rows"
                )
                if protocol_delta > 0
                else "protocol_metric_results_exceed_legacy_evaluated_candidate_counter",
            }
        )

    index_count = index_info["count"]
    if index_count is None:
        omitted_reasons.append(index_info["omitted_reason"])
    else:
        artifact_delta = index_count - formal_screened_candidates
        if artifact_delta:
            differences.append(
                {
                    "relation": (
                        "formal_candidates_index_entries_minus_"
                        "warehouse_formal_screened_candidates"
                    ),
                    "delta": artifact_delta,
                    "primary_reason": (
                        "formal_candidate_artifacts_record_only_replayable_"
                        "screening_patch_candidates"
                    )
                    if artifact_delta < 0
                    else (
                        "formal_candidate_index_contains_entries_outside_current_"
                        "warehouse_counter_scope"
                    ),
                }
            )
            if artifact_delta < 0:
                omitted_reasons.append(
                    "formal_candidate_patch_artifact_omitted_for_candidates_without_replayable_patch_or_passing_gates"
                )
        artifact_screening_delta = index_count - screening_protocol_results
        if artifact_screening_delta:
            differences.append(
                {
                    "relation": (
                        "formal_candidates_index_entries_minus_db_screening_rows"
                    ),
                    "delta": artifact_screening_delta,
                    "primary_reason": (
                        "formal_candidate_artifacts_are_a_replayable_patch_subset_"
                        "of_screening_rows"
                    )
                    if artifact_screening_delta < 0
                    else (
                        "formal_candidate_index_contains_entries_not_visible_in_"
                        "current_screening_row_scope"
                    ),
                }
            )
    if index_info["unreadable_rows"]:
        omitted_reasons.append("formal_candidates_index_has_unreadable_rows")

    return {
        "schema_version": "formal_candidate_count_reconciliation.v1",
        "warehouse_formal_screened_candidates": formal_screened_candidates,
        "db_screening_rows": screening_protocol_results,
        "protocol_evaluated_candidates": protocol_evaluated_candidates,
        "protocol_metric_results": protocol_metric_results,
        "formal_candidates_index_entries": index_count,
        "formal_candidates_index_count": index_count,
        "formal_candidates_index_status": index_info["status"],
        "formal_candidates_index_ref": index_info["artifact_ref"],
        "formal_candidates_index_unreadable_rows": index_info["unreadable_rows"],
        "sources": {
            "warehouse_formal_screened_candidates": {
                "count": formal_screened_candidates,
                "source": "campaign_loop.formal_screened_candidates",
            },
            "db_screening_rows": {
                "count": screening_protocol_results,
                "source": "protocol_metric_stage_counts.screening",
            },
            "protocol_metric_results": {
                "count": protocol_metric_results,
                "source": "completed_protocol_metric_rows",
            },
            "formal_candidates_index": {
                "count": index_count,
                "source": "artifacts/formal_candidates/index.jsonl",
                "status": index_info["status"],
                "artifact_ref": index_info["artifact_ref"],
            },
        },
        "differences": differences,
        "omitted_reasons": list(dict.fromkeys(omitted_reasons)),
    }


def _formal_candidates_index_info(
    campaign_dir: str | Path | None,
) -> dict[str, Any]:
    if campaign_dir is None:
        return {
            "count": None,
            "status": "unavailable",
            "artifact_ref": None,
            "unreadable_rows": 0,
            "omitted_reason": "campaign_dir_unavailable_for_formal_candidates_index",
        }
    index_path = Path(campaign_dir) / "artifacts" / "formal_candidates" / "index.jsonl"
    artifact_ref = public_artifact_ref(index_path, base_dir=campaign_dir)
    if not index_path.exists():
        return {
            "count": None,
            "status": "missing",
            "artifact_ref": artifact_ref,
            "unreadable_rows": 0,
            "omitted_reason": "formal_candidates_index_missing_or_not_written",
        }
    count = 0
    unreadable = 0
    try:
        with index_path.open(encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    unreadable += 1
                    continue
                if isinstance(payload, Mapping):
                    count += 1
                else:
                    unreadable += 1
    except OSError:
        return {
            "count": None,
            "status": "unavailable",
            "artifact_ref": artifact_ref,
            "unreadable_rows": unreadable,
            "omitted_reason": "formal_candidates_index_unreadable",
        }
    return {
        "count": count,
        "status": "available",
        "artifact_ref": artifact_ref,
        "unreadable_rows": unreadable,
        "omitted_reason": "",
    }


def _protocol_stage_counts_from_steps(steps: Iterable[StepRecord]) -> dict[str, int]:
    counts = _empty_protocol_stage_counts()
    for step in steps:
        if getattr(step, "protocol_result", None) is None:
            continue
        stage = _stage_value(step)
        if stage in counts:
            counts[stage] += 1
    return counts


def _formal_screened_candidate_count_from_steps(
    steps: Iterable[StepRecord],
) -> int:
    count = 0
    for step in steps:
        protocol = getattr(step, "protocol_result", None)
        if protocol is None or _stage_value(step) != "screening":
            continue
        if not _legacy_step_counts_toward_max_rounds(step):
            continue
        if not screened_experiment_effective(protocol):
            continue
        count += 1
    return count


def _verification_failure_consumed_candidate(step: StepRecord) -> bool:
    return (
        getattr(step, "protocol_result", None) is None
        and str(getattr(step, "failure_stage", "") or "") == "verification"
        and _legacy_step_counts_toward_max_rounds(step)
    )


def _verification_consumed_candidate_count_from_steps(
    steps: Iterable[StepRecord],
) -> int:
    return sum(
        1
        for step in steps
        if _legacy_step_counts_toward_max_rounds(step)
        and (
            getattr(step, "protocol_result", None) is not None
            or _verification_failure_consumed_candidate(step)
        )
    )


def _unique_hypothesis_info(
    *,
    steps: Iterable[StepRecord],
    loop: Mapping[str, Any],
    state_map: Mapping[str, Any],
) -> dict[str, Any]:
    ids = sorted(
        {
            str(getattr(step, "hypothesis_id", "") or "").strip()
            for step in steps
            if str(getattr(step, "hypothesis_id", "") or "").strip()
        }
    )
    if ids:
        return {
            "available": True,
            "count": len(ids),
            "ids": ids,
            "source": "step_history.hypothesis_id",
        }

    for source_name, source in (
        ("state.unique_hypothesis_ids", state_map.get("unique_hypothesis_ids")),
        ("campaign_loop.unique_hypothesis_ids", loop.get("unique_hypothesis_ids")),
    ):
        if not isinstance(source, Iterable) or isinstance(source, (str, bytes)):
            continue
        source_ids = sorted(
            {
                str(item or "").strip()
                for item in source
                if str(item or "").strip()
            }
        )
        if source_ids:
            return {
                "available": True,
                "count": len(source_ids),
                "ids": source_ids,
                "source": source_name,
            }

    for source_name, value in (
        ("state.unique_hypotheses", state_map.get("unique_hypotheses")),
        ("state.unique_hypothesis_count", state_map.get("unique_hypothesis_count")),
        ("campaign_loop.unique_hypotheses", loop.get("unique_hypotheses")),
        (
            "campaign_loop.unique_hypothesis_count",
            loop.get("unique_hypothesis_count"),
        ),
    ):
        count = _optional_nonnegative_int(value)
        if count is not None:
            return {
                "available": True,
                "count": count,
                "ids": [],
                "source": source_name,
            }

    return {
        "available": False,
        "count": None,
        "ids": [],
        "source": "unavailable",
    }


def _protocol_stage_counts_from_mapping(value: Any) -> dict[str, int]:
    counts = _empty_protocol_stage_counts()
    if not isinstance(value, Mapping):
        return counts
    for stage in _PROTOCOL_STAGE_KEYS:
        counts[stage] = _first_int(value.get(stage), default=0)
    return counts


def _merged_protocol_stage_counts(*items: Mapping[str, int]) -> dict[str, int]:
    merged = _empty_protocol_stage_counts()
    for item in items:
        for stage in _PROTOCOL_STAGE_KEYS:
            merged[stage] = max(merged[stage], _first_int(item.get(stage), default=0))
    return merged


def _empty_protocol_stage_counts() -> dict[str, int]:
    return {stage: 0 for stage in _PROTOCOL_STAGE_KEYS}


def _merged_failure_categories(
    loop: Mapping[str, Any],
    state_map: Mapping[str, Any],
) -> dict[str, int]:
    merged: dict[str, int] = {}
    for source in (state_map.get("failure_categories"), loop.get("failure_categories")):
        if not isinstance(source, Mapping):
            continue
        for key, value in source.items():
            try:
                count = max(0, int(value))
            except (TypeError, ValueError):
                continue
            name = str(key or "").strip()
            if not name:
                continue
            merged[name] = max(merged.get(name, 0), count)
    return merged


def _model_repair_failures(failure_categories: Mapping[str, int]) -> int:
    """Aggregate historical APS artifacts; direct-v3 has no repair call."""

    return sum(
        count
        for category, count in failure_categories.items()
        if "model_repair" in str(category or "")
    )


def _reconciliation_notes(
    *,
    screened_not_effective: int,
    loop_counted_delta: int,
    state_screened_delta: int,
    quality_blocks: int,
    non_counted_lifecycle_steps: int,
) -> list[dict[str, Any]]:
    notes: list[dict[str, Any]] = []
    if screened_not_effective > 0:
        notes.append(
            {
                "relation": "screened_rounds_minus_effective_rounds",
                "delta": screened_not_effective,
                "primary_reason": (
                    "screened_formal_results_excluded_from_effective_rounds"
                ),
            }
        )
    if loop_counted_delta:
        notes.append(
            {
                "relation": "loop_effective_rounds_minus_step_effective_records",
                "delta": loop_counted_delta,
                "primary_reason": "loop_status_and_step_history_reconciliation",
            }
        )
    if state_screened_delta > 0:
        notes.append(
            {
                "relation": "state_screened_rounds_minus_step_screened_records",
                "delta": state_screened_delta,
                "primary_reason": "state_provider_has_additional_screening_events",
            }
        )
    if quality_blocks > 0:
        notes.append(
            {
                "relation": "quality_blocks",
                "count": quality_blocks,
                "primary_reason": "proposal_or_schema_quality_blocks",
            }
        )
    if non_counted_lifecycle_steps > 0:
        notes.append(
            {
                "relation": "non_counted_lifecycle_steps",
                "count": non_counted_lifecycle_steps,
                "primary_reason": "scheduler_lifecycle_or_reconcile_steps",
            }
        )
    return notes


def _decision_value(step: StepRecord) -> str:
    decision = getattr(step, "decision", None)
    return str(getattr(decision, "value", decision) or "")


def _stage_value(step: StepRecord) -> str:
    protocol = getattr(step, "protocol_result", None)
    stage = getattr(protocol, "stage", "") if protocol is not None else ""
    return str(getattr(stage, "value", stage) or "")


def _attempt_kind(step: StepRecord) -> str:
    return str(getattr(step, "attempt_kind", "") or "").strip()


def _step_screened(step: StepRecord) -> bool:
    protocol = getattr(step, "protocol_result", None)
    return protocol is not None and _stage_value(step) == "screening"


def _step_counts_effective(step: StepRecord) -> bool:
    protocol = getattr(step, "protocol_result", None)
    return protocol is not None and _legacy_step_counts_toward_max_rounds(step)


def _legacy_step_counts_toward_max_rounds(step: StepRecord) -> bool:
    """Read pre-direct-v3 in-memory history without restoring write semantics."""

    return bool(getattr(step, "counts_toward_max_rounds", True))


def _step_accepted(step: StepRecord) -> bool:
    if getattr(step, "protocol_result", None) is None:
        return False
    return _decision_value(step) in {
        Decision.QUEUE_VALIDATE.value,
        Decision.QUEUE_FROZEN.value,
        Decision.PROMOTE.value,
    }


def _step_accepted_screening(step: StepRecord) -> bool:
    return _step_accepted(step) and _stage_value(step) == "screening"


def _hypothesis_calls(request_counts: Mapping[str, int]) -> int:
    return sum(
        int(request_counts.get(kind, 0) or 0)
        for kind in ("hypothesis", "generate_hypothesis")
    )


def _code_calls(request_counts: Mapping[str, int]) -> int:
    return sum(
        int(request_counts.get(kind, 0) or 0)
        for kind in ("code", "patch", "generate_code")
    )


def _request_kind(value: Any) -> str:
    return str(value or "").strip().lower()


def _first_int(*values: Any, default: int) -> int:
    for value in values:
        if value is None:
            continue
        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            continue
    return max(0, int(default))


def _optional_nonnegative_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return None
