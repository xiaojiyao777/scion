"""Quality-block ledger helpers for campaign accounting payloads."""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from scion.core.models import StepRecord
from scion.core.run_validity import failure_category_for_run_validity

QUALITY_BLOCK_KINDS = frozenset({"proposal_block", "schema_quality_block"})


def quality_block_ledger(
    *,
    steps: list[StepRecord],
    loop: Mapping[str, Any],
    state_map: Mapping[str, Any],
    quality_blocks: int,
) -> list[dict[str, Any]]:
    """Return normalized quality-block ledger entries for status and summary."""
    for source in (
        loop.get("quality_block_ledger"),
        state_map.get("quality_block_ledger"),
    ):
        ledger = _normalized_mapping_ledger(source)
        if ledger:
            return _complete_quality_block_ledger(ledger, quality_blocks)
    ledger = _quality_block_ledger_from_steps(steps)
    if ledger:
        return ledger
    if quality_blocks <= 0:
        return []
    return _aggregate_quality_block_entries(start=0, count=quality_blocks)


def _quality_block_ledger_from_steps(
    steps: Iterable[StepRecord],
) -> list[dict[str, Any]]:
    ledger: list[dict[str, Any]] = []
    for step in steps:
        attempt_kind = _attempt_kind(step)
        if attempt_kind not in QUALITY_BLOCK_KINDS:
            continue
        if not _is_countable_quality_block_step(step):
            continue
        sequence = len(ledger) + 1
        failure_reason = str(getattr(step, "failure_detail", "") or "")
        failure_stage = getattr(step, "failure_stage", None)
        ledger.append(
            {
                "schema_version": "quality_block_attempt.v1",
                "sequence": sequence,
                "index": sequence - 1,
                "branch_id": getattr(step, "branch_id", None),
                "hypothesis_id": getattr(step, "hypothesis_id", None),
                "attempt_kind": attempt_kind,
                "failure_stage": failure_stage,
                "failure_category": _step_failure_category(step),
                "failure_reason": failure_reason,
                "source_result_reason": failure_reason,
                "pre_protocol": getattr(step, "protocol_result", None) is None,
                "loop_step": getattr(step, "round_num", None),
                "source": "step_history",
                **_proposal_session_ref_fields(step),
            }
        )
    return ledger


def _complete_quality_block_ledger(
    items: list[dict[str, Any]],
    quality_blocks: int,
) -> list[dict[str, Any]]:
    normalized = _with_sequence(items)
    missing = max(0, int(quality_blocks) - len(normalized))
    if missing:
        normalized.extend(
            _aggregate_quality_block_entries(start=len(normalized), count=missing)
        )
    return _with_sequence(normalized)


def _aggregate_quality_block_entries(*, start: int, count: int) -> list[dict[str, Any]]:
    return [
        {
            "schema_version": "quality_block_attempt.v1",
            "sequence": index + 1,
            "index": index,
            "branch_id": None,
            "hypothesis_id": None,
            "attempt_kind": "proposal_or_schema_quality_block",
            "failure_stage": None,
            "failure_category": None,
            "failure_reason": "quality_block_record_missing_legacy_aggregate",
            "source_result_reason": "",
            "pre_protocol": True,
            "source": "aggregate_reconciliation",
        }
        for index in range(max(0, int(start)), max(0, int(start)) + max(0, int(count)))
    ]


def _normalized_mapping_ledger(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _with_sequence(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        entry = dict(item)
        entry.setdefault("sequence", index + 1)
        entry.setdefault("index", index)
        normalized.append(entry)
    return normalized


def _attempt_kind(step: StepRecord) -> str:
    return str(getattr(step, "attempt_kind", "") or "").strip()


def _is_countable_quality_block_step(step: StepRecord) -> bool:
    if _is_stale_source_step(step):
        return False
    stage = str(getattr(step, "failure_stage", "") or "").strip()
    category = str(_step_failure_category(step) or "").strip()
    detail = str(getattr(step, "failure_detail", "") or "").strip()
    if stage or category or detail:
        return True
    decision = str(getattr(step, "decision", "") or "").lower()
    if "continue_explore" in decision:
        return False
    return False


def _is_stale_source_step(step: StepRecord) -> bool:
    combined = " ".join(
        str(value or "")
        for value in (
            getattr(step, "failure_detail", None),
            getattr(step, "failure_category", None),
        )
    ).lower()
    return "stale_source" in combined


def _step_failure_category(step: StepRecord) -> str | None:
    detail = getattr(step, "failure_detail", None)
    stage = getattr(step, "failure_stage", None)
    if not detail and not stage:
        return None
    session_ref = getattr(step, "proposal_session_ref", None)
    category = None
    if isinstance(session_ref, Mapping):
        category = session_ref.get("failure_category")
    return failure_category_for_run_validity(
        detail,
        category=category,
        failure_stage=stage,
    )


def _proposal_session_ref_fields(step: StepRecord) -> dict[str, Any]:
    session_ref = getattr(step, "proposal_session_ref", None)
    if not isinstance(session_ref, Mapping):
        return {}
    primary = session_ref.get("primary_failure")
    if not isinstance(primary, Mapping):
        primary = {}
    rejection = session_ref.get("rejection_constraint")
    if not isinstance(rejection, Mapping):
        rejection = {}
    fields: dict[str, Any] = {}
    for key, value in (
        ("session_id", session_ref.get("session_id")),
        ("session_status", session_ref.get("status")),
        ("termination_reason", session_ref.get("termination_reason")),
        ("agent_block_reason", session_ref.get("agent_block_reason")),
        (
            "failure_code",
            session_ref.get("failure_code")
            or rejection.get("failure_code")
            or primary.get("code"),
        ),
        (
            "quality_gate_name",
            rejection.get("gate_name") or primary.get("gate_name"),
        ),
        ("retry_constraint", rejection.get("retry_constraint")),
    ):
        if value not in (None, "", [], {}, ()):
            fields[key] = value
    return fields
