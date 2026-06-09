"""Campaign accounting helpers for status and summary payloads."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Iterable, Mapping

from scion.core.models import Decision, StepRecord
from scion.core.evidence_recording.accounting_quality_blocks import (
    QUALITY_BLOCK_KINDS,
    quality_block_ledger as _quality_block_ledger,
)
from scion.core.public_refs import public_artifact_ref
from scion.core.telemetry_validation import (
    formal_screening_attempted,
    screened_experiment_effective,
)
from scion.proposal.session_trace_index import SESSION_TRACE_INDEX_NAME

from .summary_cache import _campaign_llm_accounting

logger = logging.getLogger(__name__)


def proposal_accounting_fields(
    *,
    campaign_dir: str | Path,
    steps: Iterable[StepRecord] = (),
    loop_status: Mapping[str, Any] | None = None,
    state: Mapping[str, Any] | None = None,
    round_num: int | None = None,
    screened_rounds: int | None = None,
    agentic_artifact_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Return explicit counters that disambiguate legacy proposal attempts."""
    step_list = list(steps)
    has_step_history = bool(step_list)
    loop = loop_status if isinstance(loop_status, Mapping) else {}
    state_map = state if isinstance(state, Mapping) else {}
    llm_accounting = _campaign_llm_accounting(campaign_dir)
    request_counts = {
        str(kind): _first_int(value, default=0)
        for kind, value in (
            llm_accounting.get("request_kind_counts") or {}
        ).items()
    }
    if not request_counts:
        request_counts = llm_request_kind_counts(campaign_dir)
    if not request_counts and isinstance(
        state_map.get("llm_request_kind_counts"),
        Mapping,
    ):
        request_counts = {
            str(kind): _first_int(value, default=0)
            for kind, value in state_map["llm_request_kind_counts"].items()
        }
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
    computed_agentic_sessions = agentic_session_count(
        campaign_dir=campaign_dir,
        steps=step_list,
        agentic_artifact_dir=agentic_artifact_dir,
    )
    agentic_sessions = (
        computed_agentic_sessions
        if computed_agentic_sessions > 0
        else _first_int(state_map.get("agentic_sessions"), default=0)
    )
    hypothesis_calls = _hypothesis_calls(request_counts)
    if hypothesis_calls == 0:
        hypothesis_calls = _first_int(state_map.get("hypothesis_calls"), default=0)
    code_calls = _code_calls(request_counts)
    if code_calls == 0:
        code_calls = _first_int(state_map.get("code_calls"), default=0)
    candidate_accounting = _candidate_accounting_fields(
        steps=step_list,
        loop=loop,
        state_map=state_map,
        campaign_steps=campaign_steps,
        round_num=round_num,
        screened_rounds=screened,
        campaign_dir=campaign_dir,
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
        "agentic_sessions": agentic_sessions,
        "hypothesis_calls": hypothesis_calls,
        "code_calls": code_calls,
        "llm_request_kind_counts": dict(request_counts),
        "llm_model_counts": dict(llm_accounting.get("model_counts") or {}),
        "llm_provider_counts": dict(llm_accounting.get("provider_counts") or {}),
        "llm_token_sums": dict(llm_accounting.get("token_sums") or {}),
        "llm_token_field_availability": dict(
            llm_accounting.get("token_field_availability") or {}
        ),
        "llm_accounting": llm_accounting,
    }
    trace_index = agentic_session_trace_index_artifact(
        campaign_dir=campaign_dir,
        agentic_artifact_dir=agentic_artifact_dir,
    )
    if trace_index:
        fields["agentic_session_trace_index"] = trace_index
    return fields


def accounting_reconciliation_fields(
    *,
    steps: Iterable[StepRecord] = (),
    loop_status: Mapping[str, Any] | None = None,
    state: Mapping[str, Any] | None = None,
    round_num: int | None = None,
    screened_rounds: int | None = None,
    effective_rounds_completed: int | None = None,
    counted_experiment_steps: int | None = None,
    telemetry_failed_experiments: int | None = None,
    campaign_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Return a compact audit trail explaining run-level counter differences."""
    step_list = list(steps)
    has_step_history = bool(step_list)
    loop = loop_status if isinstance(loop_status, Mapping) else {}
    state_map = state if isinstance(state, Mapping) else {}
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
    proposal_attempts = _first_int(
        loop.get("proposal_attempts_consumed"),
        loop.get("proposal_attempts"),
        state_map.get("proposal_attempts_consumed"),
        state_map.get("proposal_attempts"),
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
    telemetry_repair_attempts = _first_int(
        loop.get("telemetry_repair_attempts"),
        state_map.get("telemetry_repair_attempts"),
        default=sum(
            1
            for step in step_list
            if _attempt_kind(step)
            in {
                "telemetry_repair",
                "telemetry_repairable",
                "validation_repair_required",
            }
        ),
    )
    telemetry_repairable_attempts = _first_int(
        loop.get("telemetry_repairable_attempts"),
        state_map.get("telemetry_repairable_attempts"),
        default=sum(
            1 for step in step_list if _attempt_kind(step) == "telemetry_repairable"
        ),
    )
    validation_repair_required_attempts = _first_int(
        loop.get("validation_repair_required_attempts"),
        state_map.get("validation_repair_required_attempts"),
        default=sum(
            1
            for step in step_list
            if _attempt_kind(step) == "validation_repair_required"
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
    branch_lifecycle_blocks = _first_int(
        loop.get("branch_lifecycle_policy_blocks"),
        state_map.get("branch_lifecycle_policy_blocks"),
        default=sum(
            1 for step in step_list if _attempt_kind(step) == "branch_lifecycle_policy"
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
        branch_lifecycle_blocks + reconcile_lifecycle_steps,
        default=0,
    )
    telemetry_failed = _first_int(
        telemetry_failed_experiments,
        state_map.get("telemetry_failed_experiments"),
        default=0,
    )
    screened_not_effective = max(0, screened - effective)
    non_effective_screenings = _non_effective_screenings(
        steps=step_list,
        loop=loop,
        state_map=state_map,
        screened_not_effective=screened_not_effective,
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
        telemetry_failed=telemetry_failed,
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
    return {
        "schema_version": "campaign_accounting_reconciliation.v1",
        "requested_rounds": requested_rounds,
        "total_rounds": total_rounds,
        "campaign_steps": campaign_steps,
        "proposal_attempts": proposal_attempts,
        "proposal_attempts_consumed": proposal_attempts,
        **candidate_accounting,
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
        "telemetry_repair_attempts": telemetry_repair_attempts,
        "telemetry_repairable_attempts": telemetry_repairable_attempts,
        "validation_repair_required_attempts": validation_repair_required_attempts,
        "quality_blocks": quality_blocks,
        "quality_block_ledger": quality_block_ledger,
        "quality_block_ledger_count": len(quality_block_ledger),
        "active_slot_blocked_attempts": active_slot_blocked_attempts,
        "scheduler_active_slot_blocked_attempts": active_slot_blocked_attempts,
        "branch_lifecycle_policy_blocks": branch_lifecycle_blocks,
        "reconcile_lifecycle_steps": reconcile_lifecycle_steps,
        "non_counted_lifecycle_steps": non_counted_lifecycle_steps,
        "telemetry_failed_experiments": telemetry_failed,
        "attempt_breakdown": {
            "proposal_attempts_total": candidate_accounting[
                "proposal_attempts_total"
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
            "fresh_runtime_replay_protocol_results": candidate_accounting[
                "fresh_runtime_replay_protocol_results"
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
            "branch_lifecycle_policy_blocks": branch_lifecycle_blocks,
            "reconcile_lifecycle_steps": reconcile_lifecycle_steps,
        },
        "reconciliation": reconciliation_notes,
    }


def llm_request_kind_counts(campaign_dir: str | Path) -> dict[str, int]:
    """Count LLM trace records by normalized request kind."""
    llm_dir = Path(campaign_dir) / "llm_traces"
    counts: dict[str, int] = {}
    if not llm_dir.exists():
        return counts
    for trace_path in sorted(llm_dir.glob("*.json")):
        try:
            payload = json.loads(trace_path.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover - best-effort status path
            logger.debug("failed to read llm trace accounting %s: %s", trace_path, exc)
            continue
        usage = payload.get("llm_usage")
        usage_map = usage if isinstance(usage, Mapping) else {}
        kind = _request_kind(
            payload.get("request_kind") or usage_map.get("request_kind")
        )
        if not kind:
            continue
        counts[kind] = counts.get(kind, 0) + 1
    return counts


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
                "counts_toward_max_rounds": bool(
                    getattr(step, "counts_toward_max_rounds", True)
                ),
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
    step_fresh_replay_protocol_count = _fresh_runtime_replay_protocol_count_from_steps(
        steps
    )
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
    fresh_runtime_replay_protocol_results = _first_int(
        loop.get("fresh_runtime_replay_protocol_results"),
        state_map.get("fresh_runtime_replay_protocol_results"),
        default=step_fresh_replay_protocol_count if has_step_history else 0,
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
    protocol_default = (
        max(step_protocol_count, formal_screened_candidates)
        if has_step_history
        else max(sum(stage_counts.values()), formal_screened_candidates)
    )
    protocol_evaluated_candidates = _first_int(
        loop.get("protocol_evaluated_candidates"),
        state_map.get("protocol_evaluated_candidates"),
        default=protocol_default,
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
    return {
        "proposal_attempts_total": proposal_attempts_total,
        "formal_screened_candidates": formal_screened_candidates,
        "protocol_evaluated_candidates": protocol_evaluated_candidates,
        "protocol_metric_results": protocol_metric_results,
        "screening_protocol_results": screening_protocol_results,
        "fresh_runtime_replay_protocol_results": (
            fresh_runtime_replay_protocol_results
        ),
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
        "max_rounds_budget_counter": "effective_rounds_completed",
        "max_rounds_semantics": (
            "requested_rounds limits effective_rounds_completed; proposal, "
            "quality-blocked proposal, non-counted replay, validation, frozen, "
            "lifecycle, and active-slot scheduler attempts are reported separately"
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
            "and validation_protocol_results, frozen_protocol_results, and "
            "fresh_runtime_replay_protocol_results as explicit breakdowns"
        ),
        "protocol_metric_results_semantics": (
            "actual completed protocol metrics results/rows across screening, "
            "validation, frozen, and fresh-runtime replay; verification-only "
            "failures and proposal quality blocks are excluded"
        ),
        "verification_consumed_candidates_semantics": (
            "candidate attempts that consumed the effective max-round budget at "
            "or after verification; includes verification-only heavy failures "
            "but excludes non-counted fresh-runtime replays"
        ),
        "fresh_runtime_replay_protocol_results_semantics": (
            "non-counted fresh-runtime replay attempts with completed protocol "
            "metrics; included in protocol_metric_results but not in "
            "effective_rounds_completed"
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
        if not bool(getattr(step, "counts_toward_max_rounds", True)):
            continue
        if not screened_experiment_effective(protocol):
            continue
        count += 1
    return count


def _fresh_runtime_replay_protocol_count_from_steps(
    steps: Iterable[StepRecord],
) -> int:
    return sum(
        1
        for step in steps
        if getattr(step, "protocol_result", None) is not None
        and _attempt_kind(step) == "fresh_runtime_replay"
    )


def _verification_failure_consumed_candidate(step: StepRecord) -> bool:
    return (
        getattr(step, "protocol_result", None) is None
        and str(getattr(step, "failure_stage", "") or "") == "verification"
        and bool(getattr(step, "counts_toward_max_rounds", True))
    )


def _verification_consumed_candidate_count_from_steps(
    steps: Iterable[StepRecord],
) -> int:
    return sum(
        1
        for step in steps
        if bool(getattr(step, "counts_toward_max_rounds", True))
        and (
            getattr(step, "protocol_result", None) is not None
            or _verification_failure_consumed_candidate(step)
        )
    )


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
    telemetry_failed: int,
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
                "telemetry_failed_experiments": telemetry_failed,
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
    return protocol is not None and bool(
        getattr(step, "counts_toward_max_rounds", True)
    )


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


def agentic_session_count(
    *,
    campaign_dir: str | Path,
    steps: Iterable[StepRecord] = (),
    agentic_artifact_dir: str | Path | None = None,
) -> int:
    """Count distinct agentic proposal sessions from step refs and the APS index."""
    session_ids: set[str] = set()
    anonymous_refs = 0
    for step in steps:
        ref = getattr(step, "proposal_session_ref", None)
        if not isinstance(ref, Mapping) or not ref:
            continue
        session_id = str(ref.get("session_id") or "").strip()
        if session_id:
            session_ids.add(session_id)
        else:
            anonymous_refs += 1

    for item in _agentic_index_items(
        campaign_dir=campaign_dir,
        agentic_artifact_dir=agentic_artifact_dir,
    ):
        session_id = str(item.get("session_id") or "").strip()
        if session_id:
            session_ids.add(session_id)
        elif item:
            anonymous_refs += 1
    return len(session_ids) + anonymous_refs


def _agentic_index_items(
    *,
    campaign_dir: str | Path,
    agentic_artifact_dir: str | Path | None,
) -> list[Mapping[str, Any]]:
    index_dir = (
        Path(agentic_artifact_dir)
        if agentic_artifact_dir
        else Path(campaign_dir) / "agentic_sessions"
    )
    index_path = index_dir / "agentic_session_index.json"
    if not index_path.exists():
        return []
    try:
        raw = json.loads(index_path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - best-effort status path
        logger.debug("failed to read agentic session index %s: %s", index_path, exc)
        return []
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, Mapping)]


def agentic_session_trace_index_artifact(
    *,
    campaign_dir: str | Path,
    agentic_artifact_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Return a public ref/digest summary for the compact session trace index."""
    index_dir = (
        Path(agentic_artifact_dir)
        if agentic_artifact_dir
        else Path(campaign_dir) / "agentic_sessions"
    )
    index_path = index_dir / SESSION_TRACE_INDEX_NAME
    if not index_path.exists():
        return {}
    try:
        raw_bytes = index_path.read_bytes()
        payload = json.loads(raw_bytes.decode("utf-8"))
    except Exception as exc:  # pragma: no cover - best-effort status path
        logger.debug(
            "failed to read agentic session trace index %s: %s",
            index_path,
            exc,
        )
        return {}
    if not isinstance(payload, Mapping):
        return {}
    public_ref = public_artifact_ref(
        index_path,
        base_dir=campaign_dir,
        kind="artifact",
    )
    return {
        "artifact_kind": "agentic_session_trace_index",
        "artifact_ref": public_ref or index_path.name,
        "artifact_path": public_ref or index_path.name,
        "digest": hashlib.sha256(raw_bytes).hexdigest(),
        "digest_algorithm": "sha256",
        "schema_version": str(payload.get("schema_version") or ""),
        "session_count": _first_int(payload.get("session_count"), default=0),
        "trace_count": _first_int(payload.get("trace_count"), default=0),
    }


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
