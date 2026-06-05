"""Campaign accounting helpers for status and summary payloads."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Iterable, Mapping

from scion.core.models import Decision, StepRecord
from scion.core.public_refs import public_artifact_ref
from scion.proposal.session_trace_index import SESSION_TRACE_INDEX_NAME

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
    quality_blocks = _first_int(
        loop.get("quality_blocks"),
        loop.get("proposal_quality_blocks_consumed"),
        state_map.get("quality_blocks"),
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
    fields = {
        "campaign_steps": campaign_steps,
        "screened_rounds": screened,
        "quality_blocks": quality_blocks,
        "agentic_sessions": agentic_sessions,
        "hypothesis_calls": hypothesis_calls,
        "code_calls": code_calls,
        "llm_request_kind_counts": dict(request_counts),
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
            1 for step in step_list if _attempt_kind(step) in _QUALITY_BLOCK_KINDS
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
    return {
        "schema_version": "campaign_accounting_reconciliation.v1",
        "requested_rounds": requested_rounds,
        "total_rounds": total_rounds,
        "campaign_steps": campaign_steps,
        "proposal_attempts": proposal_attempts,
        "proposal_attempts_consumed": proposal_attempts,
        "effective_rounds_completed": effective,
        "screened_rounds": screened,
        "screened_experiments": screened,
        "counted_experiment_steps": counted,
        "accepted_experiments": accepted,
        "accepted_screening_experiments": accepted_screening,
        "promoted_experiments": promoted,
        "screened_minus_effective": screened_not_effective,
        "effective_minus_counted_step_records": loop_counted_delta,
        "state_screened_minus_step_screened": state_screened_delta,
        "model_repair_attempts": model_repair_attempts,
        "model_repair_failures": model_repair_failures,
        "telemetry_repair_attempts": telemetry_repair_attempts,
        "telemetry_repairable_attempts": telemetry_repairable_attempts,
        "validation_repair_required_attempts": validation_repair_required_attempts,
        "quality_blocks": quality_blocks,
        "branch_lifecycle_policy_blocks": branch_lifecycle_blocks,
        "reconcile_lifecycle_steps": reconcile_lifecycle_steps,
        "non_counted_lifecycle_steps": non_counted_lifecycle_steps,
        "telemetry_failed_experiments": telemetry_failed,
        "attempt_breakdown": {
            "effective_screenings": effective,
            "screened_not_effective": screened_not_effective,
            "accepted": accepted,
            "model_repair": model_repair_attempts,
            "model_repair_failures": model_repair_failures,
            "quality_blocks": quality_blocks,
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


_QUALITY_BLOCK_KINDS = frozenset({"proposal_block", "schema_quality_block"})


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
