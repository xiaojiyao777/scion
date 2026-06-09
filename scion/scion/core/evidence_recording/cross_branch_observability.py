"""Compact cross-branch proposal-context observability counters."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Iterable, Mapping

from scion.core.explore_step.branch_lesson_usage import (
    branch_lesson_usage_missing_block_prefix,
    branch_lesson_usage_reason_prefixes,
    branch_lesson_usage_requirement_diagnostic,
    branch_lesson_usage_requirement_from_records,
    branch_lesson_usage_requirement_satisfied,
)
from scion.core.explore_step.generic_mechanism_signature import (
    generic_signature_key_from_hypothesis,
    generic_signature_key_from_parts,
    generic_signature_payload_from_key,
)
from scion.core.models import StepRecord

_SCHEMA_VERSION = "cross_branch_research_observability.v1"
_POLICY = "proposal_observability_only"
_DECISION_INPUT_POLICY = "excluded_from_decision_features"
_SAFE_PRE_PROTOCOL_FAILURE_STAGES = {
    "agent_quality_blocked",
    "proposal",
    "hypothesis_contract",
    "code_generation",
    "code_generation_failed",
    "patch_contract",
    "workspace",
    "verification",
}
_NON_POSITIVE_OUTCOMES = {
    "abandoned",
    "blocked",
    "no_effect",
    "parked",
    "pre_protocol_failure",
    "regression",
}
_REPEATED_CONTRACT_REROUTE_REASON = "repeated_contract_signature_reroute"


def build_cross_branch_research_observability(
    *,
    steps: Iterable[StepRecord] = (),
    branch_rows: Iterable[Mapping[str, Any]] = (),
    scheduler_records: Iterable[Mapping[str, Any]] = (),
    context_records: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Return proposal-context counters without exposing proposal text.

    This is a summary/status artifact helper only. It does not build or mutate
    proposal context, scheduler state, or DecisionFeatures.
    """

    step_list = [step for step in steps if isinstance(step, StepRecord)]
    step_scope = _step_scope_counts(step_list)
    safe_steps = [
        step
        for step in step_list
        if _is_safe_observability_step(step)
        and _counts_toward_observability_scope(step)
    ]
    branch_row_list = [row for row in branch_rows if isinstance(row, Mapping)]
    scheduler_record_list = [
        row for row in scheduler_records if isinstance(row, Mapping)
    ]
    context_record_list = [row for row in context_records if isinstance(row, Mapping)]
    scheduler_metadata = _scheduler_metadata(safe_steps, scheduler_record_list)
    material_difference_requirement_count = _material_difference_requirement_count(
        context_records=context_record_list,
        scheduler_metadata=scheduler_metadata,
        branch_rows=branch_row_list,
    )
    branch_lesson_record_count = _branch_lesson_record_count(
        context_records=context_record_list,
        scheduler_metadata=scheduler_metadata,
        branch_rows=branch_row_list,
    )
    branch_lesson_usage_requirement_count = _branch_lesson_usage_requirement_count(
        context_records=context_record_list,
        scheduler_metadata=scheduler_metadata,
        branch_rows=branch_row_list,
    )
    branch_lesson_usage_stats = _branch_lesson_usage_stats(
        safe_steps=safe_steps,
        all_steps=step_list,
    )
    signature_groups = _signature_groups(safe_steps, branch_row_list)
    near_duplicate_count = _near_duplicate_count(signature_groups)
    saturated_signature_count = _saturated_signature_count(signature_groups)
    near_duplicate_diagnostics = _signature_group_diagnostics(
        signature_groups,
        diagnostic_kind="near_duplicate_signature",
    )
    saturated_signature_diagnostics = _signature_group_diagnostics(
        signature_groups,
        diagnostic_kind="saturated_signature",
        saturated_only=True,
    )
    avoid_signature_count = saturated_signature_count
    same_branch_refinement_allowance_count = _same_branch_refinement_allowance_count(
        safe_steps, scheduler_metadata
    )
    same_branch_refinement_not_selected_count = (
        _same_branch_refinement_not_selected_count(scheduler_metadata)
    )
    repeated_contract_reroute_count = _repeated_contract_reroute_count(
        safe_steps,
        branch_row_list,
        scheduler_metadata,
    )
    reason_code_counts = _compact_reason_code_counts(
        safe_steps,
        branch_row_list,
        scheduler_metadata,
    )
    novelty_pressure_seen_count = sum(
        1
        for value in (
            near_duplicate_count,
            saturated_signature_count,
            avoid_signature_count,
            material_difference_requirement_count,
            branch_lesson_usage_requirement_count,
            same_branch_refinement_allowance_count,
            same_branch_refinement_not_selected_count,
        )
        if value
    )
    cross_branch_map_seen_count = len(safe_steps)

    return {
        "schema_version": _SCHEMA_VERSION,
        "policy": _POLICY,
        "decision_input_policy": _DECISION_INPUT_POLICY,
        "step_history_scope": (
            "screening_and_counted_pre_protocol_failures" if step_list else "none"
        ),
        "branch_state_scope": "branch_rows_snapshot" if branch_row_list else "none",
        "scheduler_record_scope": (
            "scheduler_audit_metadata" if scheduler_record_list else "none"
        ),
        "context_record_scope": (
            "proposal_context_audit_records" if context_record_list else "none"
        ),
        "includes_failed_pre_protocol_steps": bool(
            step_scope["counted_pre_protocol_failure_steps"]
        ),
        "includes_non_counted_steps": False,
        "excludes_non_counted_steps": bool(step_scope["non_counted_steps"]),
        "source_counts": {
            **step_scope,
            "observable_step_count": len(safe_steps),
            "branch_row_count": len(branch_row_list),
            "scheduler_record_count": len(scheduler_record_list),
            "context_record_count": len(context_record_list),
        },
        "observable_step_count": len(safe_steps),
        "near_duplicate_count": near_duplicate_count,
        "saturated_signature_count": saturated_signature_count,
        "avoid_signature_count": avoid_signature_count,
        "near_duplicate_diagnostics": near_duplicate_diagnostics,
        "saturated_signature_diagnostics": saturated_signature_diagnostics,
        "material_difference_requirement_count": material_difference_requirement_count,
        "branch_lesson_record_count": branch_lesson_record_count,
        "branch_lesson_usage_requirement_count": (
            branch_lesson_usage_requirement_count
        ),
        "branch_lesson_usage_present_count": (branch_lesson_usage_stats["present"]),
        "branch_lesson_usage_satisfied_count": (branch_lesson_usage_stats["satisfied"]),
        "branch_lesson_usage_present_not_semantic_count": (
            branch_lesson_usage_stats["present_not_semantic"]
        ),
        "branch_lesson_usage_missing_block_count": (
            branch_lesson_usage_stats["missing_block"]
        ),
        "branch_lesson_usage_metadata_only_count": (
            branch_lesson_usage_stats["metadata_only"]
        ),
        "branch_lesson_usage_metadata_only_block_count": (
            branch_lesson_usage_stats["metadata_only_block"]
        ),
        "branch_lesson_usage_linkage_unrecognized_count": (
            branch_lesson_usage_stats["linkage_unrecognized"]
        ),
        "branch_lesson_usage_linkage_unrecognized_block_count": (
            branch_lesson_usage_stats["linkage_unrecognized_block"]
        ),
        "branch_lesson_usage_semantic_mismatch_count": (
            branch_lesson_usage_stats["semantic_mismatch"]
        ),
        "branch_lesson_usage_semantic_mismatch_block_count": (
            branch_lesson_usage_stats["semantic_mismatch_block"]
        ),
        "borrowed_lesson_count": branch_lesson_usage_stats["borrowed"],
        "avoided_lesson_count": branch_lesson_usage_stats["avoided"],
        "contrasted_lesson_count": branch_lesson_usage_stats["contrasted"],
        "preserved_same_branch_lesson_count": (branch_lesson_usage_stats["preserved"]),
        "clean_fork_contrast_satisfied_count": (
            branch_lesson_usage_stats["clean_fork_contrast_satisfied"]
        ),
        "weak_positive_transfer_count": (
            branch_lesson_usage_stats["weak_positive_transfer"]
        ),
        "weak_positive_transfer_reject_count": (
            branch_lesson_usage_stats["weak_positive_reject"]
        ),
        "same_branch_refinement_allowance_count": (
            same_branch_refinement_allowance_count
        ),
        "same_branch_refinement_not_selected_count": (
            same_branch_refinement_not_selected_count
        ),
        "repeated_contract_reroute_count": repeated_contract_reroute_count,
        "novelty_pressure_seen_count": novelty_pressure_seen_count,
        "cross_branch_map_seen_count": cross_branch_map_seen_count,
        "reason_code_counts": reason_code_counts,
    }


def _is_safe_observability_step(step: StepRecord) -> bool:
    protocol = step.protocol_result
    if protocol is not None:
        stage = getattr(protocol.stage, "value", protocol.stage)
        return str(stage) == "screening"
    return str(step.failure_stage or "") in _SAFE_PRE_PROTOCOL_FAILURE_STAGES


def _counts_toward_observability_scope(step: StepRecord) -> bool:
    return bool(getattr(step, "counts_toward_max_rounds", True))


def _step_scope_counts(steps: Iterable[StepRecord]) -> dict[str, int]:
    counts = {
        "step_history_total": 0,
        "protocol_screening_steps": 0,
        "non_screening_protocol_steps": 0,
        "counted_pre_protocol_failure_steps": 0,
        "safe_pre_protocol_failure_steps": 0,
        "unsafe_pre_protocol_failure_steps": 0,
        "non_counted_steps": 0,
        "non_counted_protocol_steps": 0,
        "non_counted_pre_protocol_failure_steps": 0,
    }
    for step in steps:
        counts["step_history_total"] += 1
        counts_toward = _counts_toward_observability_scope(step)
        if not counts_toward:
            counts["non_counted_steps"] += 1
        protocol = step.protocol_result
        if protocol is not None:
            stage = getattr(protocol.stage, "value", protocol.stage)
            if str(stage) == "screening":
                counts["protocol_screening_steps"] += 1
            else:
                counts["non_screening_protocol_steps"] += 1
            if not counts_toward:
                counts["non_counted_protocol_steps"] += 1
            continue
        if step.failure_stage:
            failure_stage = str(step.failure_stage or "")
            if failure_stage in _SAFE_PRE_PROTOCOL_FAILURE_STAGES:
                counts["safe_pre_protocol_failure_steps"] += 1
                if counts_toward:
                    counts["counted_pre_protocol_failure_steps"] += 1
                else:
                    counts["non_counted_pre_protocol_failure_steps"] += 1
            else:
                counts["unsafe_pre_protocol_failure_steps"] += 1
    return counts


def _scheduler_metadata(
    steps: Iterable[StepRecord],
    records: Iterable[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    metadata: list[Mapping[str, Any]] = []
    for step in steps:
        value = getattr(step, "scheduler_audit_metadata", None)
        if isinstance(value, Mapping):
            metadata.append(value)
    for record in records:
        if not isinstance(record, Mapping):
            continue
        value = record.get("scheduler_audit_metadata")
        metadata.append(value if isinstance(value, Mapping) else record)
    return metadata


def _signature_groups(
    steps: Iterable[StepRecord],
    branch_rows: Iterable[Mapping[str, Any]],
) -> dict[tuple[str, str, str, str], list[str]]:
    groups: dict[tuple[str, str, str, str], list[str]] = defaultdict(list)
    seen: set[tuple[str, tuple[str, str, str, str]]] = set()
    for step in steps:
        key = _step_signature_key(step)
        if not any(key):
            continue
        seen_key = (step.branch_id, key)
        if seen_key in seen:
            continue
        seen.add(seen_key)
        groups[key].append(_outcome_pattern(step))
    for row in branch_rows:
        key = _row_signature_key(row)
        if not any(key):
            continue
        branch_id = str(row.get("id") or row.get("branch_id") or "")
        seen_key = (branch_id, key)
        if seen_key in seen:
            continue
        seen.add(seen_key)
        groups[key].append(_row_outcome_pattern(row))
    return groups


def _step_signature_key(step: StepRecord) -> tuple[str, str, str, str]:
    hypothesis = step.hypothesis
    key = generic_signature_key_from_hypothesis(hypothesis)
    return key if _signature_key_usable(key) else ("", "", "", "")


def _row_signature_key(row: Mapping[str, Any]) -> tuple[str, str, str, str]:
    card = row.get("branch_card")
    card_map = card if isinstance(card, Mapping) else {}
    mechanism_ids = row.get("branch_mechanism_ids") or card_map.get("mechanism_ids")
    mechanism_id = ""
    if isinstance(mechanism_ids, (list, tuple)) and mechanism_ids:
        mechanism_id = _clean_token(mechanism_ids[0])
    direction = str(card_map.get("direction") or row.get("direction") or "")
    action = ""
    change_locus = ""
    if "/" in direction:
        action, change_locus = direction.split("/", 1)
    target_files = card_map.get("target_files") or row.get("target_files")
    target_file = ""
    if isinstance(target_files, (list, tuple)) and target_files:
        target_file = _clean_path(target_files[0])
    action = _clean_token(action)
    change_locus = _clean_token(change_locus)
    if not any((mechanism_id, target_file, action, change_locus)):
        return ("", "", "", "")
    key = generic_signature_key_from_parts(
        mechanism_ids=[mechanism_id] if mechanism_id else (),
        signature=_row_signature_mapping(row, card_map),
        target_file=target_file,
        action=action,
        change_locus=change_locus,
    )
    return key if _signature_key_usable(key) else ("", "", "", "")


def _row_signature_mapping(
    row: Mapping[str, Any],
    card_map: Mapping[str, Any],
) -> Mapping[str, Any]:
    for value in (
        row.get("generic_mechanism_signature"),
        row.get("shared_signature"),
        card_map.get("generic_mechanism_signature"),
        card_map.get("shared_signature"),
    ):
        if isinstance(value, Mapping):
            return value
    return {}


def _signature_key_usable(key: tuple[str, str, str, str]) -> bool:
    return bool(key[0] and key[0] != "unknown" and (key[1] or key[2]))


def _outcome_pattern(step: StepRecord) -> str:
    protocol = step.protocol_result
    if protocol is None:
        return "pre_protocol_failure" if step.failure_stage else "unknown"
    stats = getattr(protocol, "stats", None)
    if stats is None:
        return "unknown"
    gate_outcome = str(getattr(protocol, "gate_outcome", "") or "")
    if getattr(stats, "losses", 0) > getattr(stats, "wins", 0):
        return "regression"
    if getattr(stats, "median_delta", 0.0) < 0:
        return "regression"
    if getattr(stats, "wins", 0) > getattr(stats, "losses", 0):
        return "positive" if gate_outcome == "pass" else "weak_positive"
    if getattr(stats, "wins", 0) == 0 and getattr(stats, "losses", 0) == 0:
        return "no_effect"
    return "unknown"


def _row_outcome_pattern(row: Mapping[str, Any]) -> str:
    card = row.get("branch_card")
    card_map = card if isinstance(card, Mapping) else {}
    evidence = card_map.get("generic_evidence_summary")
    if not isinstance(evidence, Mapping):
        evidence = row.get("generic_evidence_summary")
    if isinstance(evidence, Mapping):
        tier = _clean_token(evidence.get("tier"))
        if tier:
            if tier == "weak_positive":
                return "weak_positive"
            if tier in _NON_POSITIVE_OUTCOMES:
                return tier
            if tier in {"positive", "promising"}:
                return "positive"
    state = _clean_token(row.get("state") or card_map.get("status"))
    if state in {"abandoned", "parked", "parked_lineage"}:
        return "parked" if state == "parked_lineage" else state
    return "unknown"


def _near_duplicate_count(
    groups: Mapping[tuple[str, str, str, str], list[str]],
) -> int:
    return sum(1 for outcomes in groups.values() if len(outcomes) >= 2)


def _saturated_signature_count(
    groups: Mapping[tuple[str, str, str, str], list[str]],
) -> int:
    return sum(
        1
        for outcomes in groups.values()
        if sum(1 for outcome in outcomes if outcome in _NON_POSITIVE_OUTCOMES) >= 2
    )


def _signature_group_diagnostics(
    groups: Mapping[tuple[str, str, str, str], list[str]],
    *,
    diagnostic_kind: str,
    saturated_only: bool = False,
    limit: int = 8,
) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    for key, outcomes in sorted(groups.items()):
        non_positive = sum(
            1 for outcome in outcomes if outcome in _NON_POSITIVE_OUTCOMES
        )
        if saturated_only:
            if non_positive < 2:
                continue
        elif len(outcomes) < 2:
            continue
        outcome_counts = Counter(outcomes)
        diagnostics.append(
            {
                "diagnostic_kind": diagnostic_kind,
                "proposal_visibility_only": True,
                "advisory_only": True,
                "decision_features_excluded": True,
                "signature": generic_signature_payload_from_key(key),
                "signature_observation_count": len(outcomes),
                "non_positive_outcome_count": non_positive,
                "outcome_pattern_counts": dict(sorted(outcome_counts.items())),
            }
        )
        if len(diagnostics) >= limit:
            break
    return diagnostics


def _same_branch_refinement_allowance_count(
    steps: Iterable[StepRecord],
    metadata: Iterable[Mapping[str, Any]],
) -> int:
    selected = sum(
        1
        for item in metadata
        if item.get("same_branch_refinement_selected") is True
        or item.get("pre_finalizer_same_branch_refinement_selected") is True
        or str(item.get("post_finalizer_actual_branch_action") or "")
        == "continue_same_branch"
    )
    if selected:
        return selected
    return len(
        {step.branch_id for step in steps if _outcome_pattern(step) == "weak_positive"}
    )


def _same_branch_refinement_not_selected_count(
    metadata: Iterable[Mapping[str, Any]],
) -> int:
    count = 0
    for item in metadata:
        reason = str(item.get("same_branch_refinement_not_selected_reason") or "")
        if reason or item.get("clean_fork_selected") is True:
            count += 1
    return count


def _repeated_contract_reroute_count(
    steps: Iterable[StepRecord],
    branch_rows: Iterable[Mapping[str, Any]],
    metadata: Iterable[Mapping[str, Any]],
) -> int:
    branch_ids: set[str] = set()
    for row in branch_rows:
        if _row_has_repeated_contract_reroute(row):
            branch_id = str(row.get("id") or row.get("branch_id") or "")
            branch_ids.add(branch_id or f"row:{len(branch_ids)}")
    for step in steps:
        if any(
            _REPEATED_CONTRACT_REROUTE_REASON in str(value)
            for value in (
                step.failure_detail,
                step.verification_detail,
                *list(step.decision_reason_codes or ()),
            )
        ):
            branch_ids.add(step.branch_id)
    for item in metadata:
        if any(
            _REPEATED_CONTRACT_REROUTE_REASON in str(value) for value in item.values()
        ):
            branch_ids.add(str(item.get("branch_id") or f"metadata:{len(branch_ids)}"))
    return len(branch_ids)


def _material_difference_requirement_count(
    *,
    context_records: Iterable[Mapping[str, Any]],
    scheduler_metadata: Iterable[Mapping[str, Any]],
    branch_rows: Iterable[Mapping[str, Any]],
) -> int:
    record_ids: set[str] = set()
    fallback_digests: set[str] = set()
    for record in _iter_material_difference_records(
        context_records,
        scheduler_metadata,
        branch_rows,
    ):
        if not _is_material_difference_record(record):
            continue
        record_id = str(record.get("record_id") or "").strip()
        if record_id:
            record_ids.add(record_id)
            continue
        digest = str(
            record.get("record_digest") or record.get("requirement_digest") or ""
        ).strip()
        if digest:
            fallback_digests.add(digest)
    return len(record_ids) + len(fallback_digests)


def _iter_material_difference_records(
    context_records: Iterable[Mapping[str, Any]],
    scheduler_metadata: Iterable[Mapping[str, Any]],
    branch_rows: Iterable[Mapping[str, Any]],
) -> Iterable[Mapping[str, Any]]:
    for record in context_records:
        if isinstance(record, Mapping):
            yield record
    for item in scheduler_metadata:
        yield from _records_from_mapping(item)
    for row in branch_rows:
        yield from _records_from_mapping(row)
        card = row.get("branch_card")
        if isinstance(card, Mapping):
            yield from _records_from_mapping(card)


def _records_from_mapping(item: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
    direct = item.get("material_difference_requirement")
    if isinstance(direct, Mapping):
        yield direct

    for key in (
        "material_difference_audit_records",
        "cross_branch_research_audit_records",
    ):
        values = item.get(key)
        if isinstance(values, (list, tuple)):
            for value in values:
                if isinstance(value, Mapping):
                    yield value

    payload = item.get("cross_branch_research_payload")
    if isinstance(payload, Mapping):
        for value in payload.get("material_difference_audit_records", []) or []:
            if isinstance(value, Mapping):
                yield value
        novelty = payload.get("novelty_pressure")
        if isinstance(novelty, Mapping):
            for value in novelty.get("material_difference_audit_records", []) or []:
                if isinstance(value, Mapping):
                    yield value

    novelty = item.get("novelty_pressure")
    if isinstance(novelty, Mapping):
        for value in novelty.get("material_difference_audit_records", []) or []:
            if isinstance(value, Mapping):
                yield value


def _is_material_difference_record(record: Mapping[str, Any]) -> bool:
    if record.get("record_type") == "material_difference_requirement":
        return True
    if record.get("schema_version") == "material_difference_requirement.v1":
        return bool(record.get("record_id") or record.get("record_digest"))
    return False


def _branch_lesson_record_count(
    *,
    context_records: Iterable[Mapping[str, Any]],
    scheduler_metadata: Iterable[Mapping[str, Any]],
    branch_rows: Iterable[Mapping[str, Any]],
) -> int:
    lesson_ids: set[str] = set()
    fallback_digests: set[str] = set()
    for record in _iter_branch_lesson_records(
        context_records,
        scheduler_metadata,
        branch_rows,
    ):
        if not _is_branch_lesson_record(record):
            continue
        lesson_id = str(record.get("lesson_id") or "").strip()
        if lesson_id:
            lesson_ids.add(lesson_id)
            continue
        digest = str(record.get("record_digest") or "").strip()
        if digest:
            fallback_digests.add(digest)
    return len(lesson_ids) + len(fallback_digests)


def _branch_lesson_usage_requirement_count(
    *,
    context_records: Iterable[Mapping[str, Any]],
    scheduler_metadata: Iterable[Mapping[str, Any]],
    branch_rows: Iterable[Mapping[str, Any]],
) -> int:
    record_ids: set[str] = set()
    fallback_digests: set[str] = set()
    for record in _iter_branch_lesson_usage_requirement_records(
        context_records,
        scheduler_metadata,
        branch_rows,
    ):
        if not _is_branch_lesson_usage_requirement(record):
            continue
        record_id = str(record.get("record_id") or "").strip()
        if record_id:
            record_ids.add(record_id)
            continue
        digest = str(record.get("record_digest") or "").strip()
        if digest:
            fallback_digests.add(digest)
    return len(record_ids) + len(fallback_digests)


def _iter_branch_lesson_usage_requirement_records(
    context_records: Iterable[Mapping[str, Any]],
    scheduler_metadata: Iterable[Mapping[str, Any]],
    branch_rows: Iterable[Mapping[str, Any]],
) -> Iterable[Mapping[str, Any]]:
    for item in _iter_observability_mappings(
        context_records,
        scheduler_metadata,
        branch_rows,
    ):
        direct = item.get("branch_lesson_usage_requirement")
        direct_seen = False
        if isinstance(direct, Mapping):
            yield direct
            direct_seen = True
        if _is_branch_lesson_usage_requirement(item):
            yield item
            direct_seen = True

        if not direct_seen:
            records = item.get("branch_lesson_records") or item.get("branch_lessons")
            derived = branch_lesson_usage_requirement_from_records(records)
            if derived:
                yield derived

        payload = item.get("cross_branch_research_payload")
        if isinstance(payload, Mapping):
            direct = payload.get("branch_lesson_usage_requirement")
            payload_direct_seen = False
            if isinstance(direct, Mapping):
                yield direct
                payload_direct_seen = True
            if not payload_direct_seen:
                derived = branch_lesson_usage_requirement_from_records(
                    payload.get("branch_lesson_records")
                )
                if derived:
                    yield derived


def _iter_branch_lesson_records(
    context_records: Iterable[Mapping[str, Any]],
    scheduler_metadata: Iterable[Mapping[str, Any]],
    branch_rows: Iterable[Mapping[str, Any]],
) -> Iterable[Mapping[str, Any]]:
    for item in _iter_observability_mappings(
        context_records,
        scheduler_metadata,
        branch_rows,
    ):
        if _is_branch_lesson_record(item):
            yield item
        for key in ("branch_lesson_records", "branch_lessons"):
            values = item.get(key)
            if isinstance(values, (list, tuple)):
                for value in values:
                    if isinstance(value, Mapping):
                        yield value
        payload = item.get("cross_branch_research_payload")
        if isinstance(payload, Mapping):
            for value in payload.get("branch_lesson_records", []) or []:
                if isinstance(value, Mapping):
                    yield value


def _iter_observability_mappings(
    context_records: Iterable[Mapping[str, Any]],
    scheduler_metadata: Iterable[Mapping[str, Any]],
    branch_rows: Iterable[Mapping[str, Any]],
) -> Iterable[Mapping[str, Any]]:
    for record in context_records:
        if isinstance(record, Mapping):
            yield record
    for item in scheduler_metadata:
        if isinstance(item, Mapping):
            yield item
    for row in branch_rows:
        if isinstance(row, Mapping):
            yield row
            summary = row.get("branch_evidence_summary")
            if isinstance(summary, Mapping):
                yield summary
            card = row.get("branch_card")
            if isinstance(card, Mapping):
                yield card


def _is_branch_lesson_record(record: Mapping[str, Any]) -> bool:
    return record.get("schema_version") == "branch_lesson.v1" and bool(
        record.get("lesson_id") or record.get("record_digest")
    )


def _is_branch_lesson_usage_requirement(record: Mapping[str, Any]) -> bool:
    if record.get("schema_version") != "branch_lesson_usage_requirement.v1":
        return False
    if record.get("required") is False:
        return False
    return bool(
        record.get("required") is True
        or str(record.get("record_id") or "").strip()
        or str(record.get("record_digest") or "").strip()
    )


def _branch_lesson_usage_stats(
    *,
    safe_steps: Iterable[StepRecord],
    all_steps: Iterable[StepRecord],
) -> dict[str, int]:
    counts = {
        "present": 0,
        "satisfied": 0,
        "present_not_semantic": 0,
        "missing_block": 0,
        "metadata_only": 0,
        "metadata_only_block": 0,
        "linkage_unrecognized": 0,
        "linkage_unrecognized_block": 0,
        "semantic_mismatch": 0,
        "semantic_mismatch_block": 0,
        "borrowed": 0,
        "avoided": 0,
        "contrasted": 0,
        "preserved": 0,
        "clean_fork_contrast_satisfied": 0,
        "weak_positive_transfer": 0,
        "weak_positive_reject": 0,
    }
    reason_prefixes = branch_lesson_usage_reason_prefixes()
    missing_prefix = branch_lesson_usage_missing_block_prefix()
    for step in all_steps:
        if _step_has_branch_lesson_missing_block(step, missing_prefix):
            counts["missing_block"] += 1
        if _step_has_branch_lesson_missing_block(
            step,
            reason_prefixes["metadata_only"],
        ):
            counts["metadata_only_block"] += 1
        if _step_has_branch_lesson_missing_block(
            step,
            reason_prefixes["linkage_unrecognized"],
        ):
            counts["linkage_unrecognized_block"] += 1
        if _step_has_branch_lesson_missing_block(
            step,
            reason_prefixes["semantic_mismatch"],
        ):
            counts["semantic_mismatch_block"] += 1

    for step in safe_steps:
        usage = getattr(step.hypothesis, "branch_lesson_usage", None)
        if not isinstance(usage, Mapping):
            continue
        if _usage_mapping_present(usage):
            counts["present"] += 1
        counts["borrowed"] += _lesson_usage_item_count(usage.get("borrowed_lessons"))
        counts["avoided"] += _lesson_usage_item_count(usage.get("avoided_lessons"))
        counts["contrasted"] += _lesson_usage_item_count(
            usage.get("contrasted_lessons")
        )
        counts["preserved"] += _preserved_usage_count(
            usage.get("preserved_same_branch_lesson")
        )
        metadata = _step_branch_lesson_requirement_metadata(step)
        diagnostic = "missing"
        semantic_satisfied = False
        if metadata:
            diagnostic = branch_lesson_usage_requirement_diagnostic(
                usage,
                metadata=metadata,
                hypothesis=step.hypothesis,
            )
            semantic_satisfied = diagnostic == "satisfied"
        if semantic_satisfied:
            counts["satisfied"] += 1
        elif _usage_mapping_present(usage):
            counts["present_not_semantic"] += 1
            if diagnostic in {
                "metadata_only",
                "linkage_unrecognized",
                "semantic_mismatch",
            }:
                counts[diagnostic] += 1
        clean_fork_metadata = {
            "schema_version": "branch_lesson_usage_requirement.v1",
            "required": True,
            "required_fors": ["clean_fork_new_branch"],
        }
        if branch_lesson_usage_requirement_satisfied(
            usage,
            metadata=clean_fork_metadata,
            hypothesis=step.hypothesis,
        ):
            counts["clean_fork_contrast_satisfied"] += 1
        if _weak_positive_transfer_usage_present(
            usage,
            metadata,
            hypothesis=step.hypothesis,
        ):
            counts["weak_positive_transfer"] += 1
        elif _weak_positive_transfer_required_and_rejected(
            usage,
            metadata,
            hypothesis=step.hypothesis,
        ):
            counts["weak_positive_reject"] += 1
    return counts


def _step_has_branch_lesson_missing_block(
    step: StepRecord,
    missing_prefix: str,
) -> bool:
    if missing_prefix in str(step.failure_detail or ""):
        return True
    ref = (
        step.proposal_session_ref
        if isinstance(step.proposal_session_ref, Mapping)
        else {}
    )
    primary = ref.get("primary_failure") if isinstance(ref, Mapping) else {}
    if isinstance(primary, Mapping) and any(
        missing_prefix in str(primary.get(key) or "")
        for key in ("code", "reason", "category", "detail")
    ):
        return True
    return any(missing_prefix in str(ref.get(key) or "") for key in ref)


def _step_branch_lesson_requirement_metadata(step: StepRecord) -> Mapping[str, Any]:
    ref = (
        step.proposal_session_ref
        if isinstance(step.proposal_session_ref, Mapping)
        else {}
    )
    if isinstance(ref.get("branch_lesson_usage_requirement"), Mapping):
        return ref["branch_lesson_usage_requirement"]
    derived = branch_lesson_usage_requirement_from_records(
        ref.get("branch_lesson_records")
    )
    if derived:
        return derived
    payload = ref.get("cross_branch_research_payload")
    if isinstance(payload, Mapping):
        if isinstance(payload.get("branch_lesson_usage_requirement"), Mapping):
            return payload["branch_lesson_usage_requirement"]
        derived = branch_lesson_usage_requirement_from_records(
            payload.get("branch_lesson_records")
        )
        if derived:
            return derived
    scheduler = (
        step.scheduler_audit_metadata
        if isinstance(step.scheduler_audit_metadata, Mapping)
        else {}
    )
    if isinstance(scheduler.get("branch_lesson_usage_requirement"), Mapping):
        return scheduler["branch_lesson_usage_requirement"]
    derived = branch_lesson_usage_requirement_from_records(
        scheduler.get("branch_lesson_records")
    )
    if derived:
        return derived
    return {}


def _lesson_usage_item_count(value: Any) -> int:
    if isinstance(value, Mapping):
        return 1 if _usage_mapping_present(value) else 0
    if not isinstance(value, (list, tuple)):
        return 0
    return sum(
        1
        for item in value
        if isinstance(item, Mapping) and _usage_mapping_present(item)
    )


def _preserved_usage_count(value: Any) -> int:
    if isinstance(value, Mapping):
        return 1 if _usage_mapping_present(value) else 0
    if not isinstance(value, (list, tuple)):
        return 0
    return sum(
        1
        for item in value
        if isinstance(item, Mapping) and _usage_mapping_present(item)
    )


def _weak_positive_transfer_usage_present(
    usage: Mapping[str, Any],
    metadata: Mapping[str, Any],
    *,
    hypothesis: Any,
) -> bool:
    if not _borrowed_weak_positive_lesson_present(
        usage.get("borrowed_lessons")
    ) and not _metadata_weak_positive_transfer(metadata):
        return False
    transfer_metadata = dict(metadata or {})
    transfer_metadata.update(
        {
            "schema_version": "branch_lesson_usage_requirement.v1",
            "required": True,
            "required_fors": ["clean_fork_new_branch"],
            "requirement_source": "weak_positive_transfer",
        }
    )
    return branch_lesson_usage_requirement_satisfied(
        usage,
        metadata=transfer_metadata,
        hypothesis=hypothesis,
        allow_machine_reject=False,
    )


def _weak_positive_transfer_required_and_rejected(
    usage: Mapping[str, Any],
    metadata: Mapping[str, Any],
    *,
    hypothesis: Any,
) -> bool:
    if not _metadata_weak_positive_transfer(metadata):
        return False
    if not (
        _lesson_usage_item_count(usage.get("rejected_weak_positive_lessons"))
        or _lesson_usage_item_count(usage.get("rejected_lessons"))
    ):
        return False
    transfer_metadata = dict(metadata or {})
    transfer_metadata.update(
        {
            "schema_version": "branch_lesson_usage_requirement.v1",
            "required": True,
            "required_fors": ["clean_fork_new_branch"],
            "requirement_source": "weak_positive_transfer",
        }
    )
    return branch_lesson_usage_requirement_satisfied(
        usage,
        metadata=transfer_metadata,
        hypothesis=hypothesis,
    )


def _borrowed_weak_positive_lesson_present(value: Any) -> bool:
    if isinstance(value, Mapping):
        return _mapping_mentions_weak_positive_lesson(value)
    if not isinstance(value, (list, tuple)):
        return False
    return any(
        isinstance(item, Mapping) and _mapping_mentions_weak_positive_lesson(item)
        for item in value
    )


def _mapping_mentions_weak_positive_lesson(value: Mapping[str, Any]) -> bool:
    for key in (
        "lesson_type",
        "source_lesson_type",
        "borrowed_lesson_type",
        "borrowed_signal",
    ):
        token = _clean_token(value.get(key))
        if token in {"weak_positive", "weak_positive_signal"}:
            return True
    return False


def _metadata_weak_positive_transfer(value: Mapping[str, Any]) -> bool:
    if not isinstance(value, Mapping):
        return False
    if _clean_token(value.get("requirement_source")) == "weak_positive_transfer":
        return True
    lesson_types = {
        _clean_token(item) for item in value.get("candidate_lesson_types", []) or []
    }
    lesson_roles = {
        _clean_token(item) for item in value.get("candidate_lesson_roles", []) or []
    }
    return "weak_positive" in lesson_types and "borrow" in lesson_roles


def _usage_mapping_present(value: Mapping[str, Any]) -> bool:
    return any(
        child not in (None, "", [], {}, ())
        for key, child in value.items()
        if str(key).strip().lower() not in {"metadata", "audit"}
    )


def _row_has_repeated_contract_reroute(row: Mapping[str, Any]) -> bool:
    direct = str(row.get("branch_lifecycle_reroute_reason") or "")
    if direct == _REPEATED_CONTRACT_REROUTE_REASON:
        return True
    card = row.get("branch_card")
    if isinstance(card, Mapping):
        card_reason = str(card.get("branch_lifecycle_reroute_reason") or "")
        if card_reason == _REPEATED_CONTRACT_REROUTE_REASON:
            return True
        block = card.get("last_branch_lifecycle_policy_block")
        if isinstance(block, Mapping):
            return str(block.get("reroute_reason") or "") == (
                _REPEATED_CONTRACT_REROUTE_REASON
            )
    block = row.get("last_branch_lifecycle_policy_block")
    if isinstance(block, Mapping):
        return str(block.get("reroute_reason") or "") == (
            _REPEATED_CONTRACT_REROUTE_REASON
        )
    return False


def _compact_reason_code_counts(
    steps: Iterable[StepRecord],
    branch_rows: Iterable[Mapping[str, Any]],
    metadata: Iterable[Mapping[str, Any]],
) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for step in steps:
        for code in _step_reason_codes(step):
            if _is_observability_reason_code(code):
                counts[code] += 1
    for row in branch_rows:
        _add_reason_codes_from_mapping(counts, row)
        card = row.get("branch_card")
        if isinstance(card, Mapping):
            _add_reason_codes_from_mapping(counts, card)
    for item in metadata:
        _add_reason_codes_from_mapping(counts, item)
    repeated_contract_count = _repeated_contract_reroute_count(
        steps,
        branch_rows,
        metadata,
    )
    if repeated_contract_count:
        counts[_REPEATED_CONTRACT_REROUTE_REASON] = max(
            counts.get(_REPEATED_CONTRACT_REROUTE_REASON, 0),
            repeated_contract_count,
        )
    return dict(sorted(counts.items()))


def _step_reason_codes(step: StepRecord) -> list[str]:
    codes = [str(code) for code in (step.decision_reason_codes or ()) if str(code)]
    if step.protocol_result is not None:
        codes.extend(
            str(code)
            for code in getattr(step.protocol_result, "reason_codes", ())
            if str(code)
        )
    return list(dict.fromkeys(codes))


def _add_reason_codes_from_mapping(
    counts: Counter[str],
    item: Mapping[str, Any],
) -> None:
    for key in (
        "reason_codes",
        "decision_reason_codes",
        "gate_observation_reason_codes",
        "lifecycle_action_reason_codes",
        "why_not_promoted_reason_codes",
        "why_abandoned_reason_codes",
    ):
        values = item.get(key)
        if not isinstance(values, (list, tuple)):
            continue
        for value in values:
            code = str(value)
            if _is_observability_reason_code(code):
                counts[code] += 1
    reason = str(item.get("branch_lifecycle_reroute_reason") or "")
    if reason and _is_observability_reason_code(reason):
        counts[reason] += 1


def _is_observability_reason_code(code: str) -> bool:
    upper = code.upper()
    lower = code.lower()
    return (
        any(
            marker in upper
            for marker in (
                "CROSS_BRANCH",
                "DUPLICATE",
                "MATERIAL_DIFFERENCE",
                "NOVELTY",
                "REFINEMENT",
                "REROUTE",
                "SIGNATURE",
            )
        )
        or lower == _REPEATED_CONTRACT_REROUTE_REASON
    )


def _clean_token(value: Any) -> str:
    text = str(value or "").strip().lower()
    cleaned = "".join(char if char.isalnum() else "_" for char in text)
    return "_".join(part for part in cleaned.split("_") if part)


def _clean_path(value: Any) -> str:
    text = str(value or "").strip()
    return text.replace("\\", "/")


__all__ = ["build_cross_branch_research_observability"]
