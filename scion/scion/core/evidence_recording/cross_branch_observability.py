"""Compact cross-branch proposal-context observability counters."""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Iterable, Mapping

from scion.core.models import StepRecord, mechanism_changes


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
_FAMILY_SUFFIXES = {
    "attempt",
    "candidate",
    "experimental",
    "followup",
    "probe",
    "refine",
    "refined",
    "refinement",
    "retry",
    "test",
    "tuned",
    "variant",
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
    signature_groups = _signature_groups(safe_steps, branch_row_list)
    near_duplicate_count = _near_duplicate_count(signature_groups)
    saturated_signature_count = _saturated_signature_count(signature_groups)
    avoid_signature_count = saturated_signature_count
    same_branch_refinement_allowance_count = (
        _same_branch_refinement_allowance_count(safe_steps, scheduler_metadata)
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
            "screening_and_counted_pre_protocol_failures"
            if step_list
            else "none"
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
        "material_difference_requirement_count": material_difference_requirement_count,
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
    mechanism_ids = [
        _clean_token(item.id)
        for item in mechanism_changes(hypothesis)
        if _clean_token(item.id)
    ]
    mechanism_family = _mechanism_family(
        mechanism_ids[0] if mechanism_ids else "",
        _clean_token(getattr(hypothesis, "change_locus", None)),
        _clean_path(getattr(hypothesis, "target_file", None)),
    )
    return (
        mechanism_family,
        _clean_path(getattr(hypothesis, "target_file", None)),
        _clean_token(getattr(hypothesis, "action", None)),
        _clean_token(getattr(hypothesis, "change_locus", None)),
    )


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
    return (
        _mechanism_family(mechanism_id, change_locus, target_file),
        target_file,
        action,
        change_locus,
    )


def _mechanism_family(
    mechanism_id: str,
    change_locus: str,
    target_file: str,
) -> str:
    source = mechanism_id or change_locus or target_file or "unknown"
    tokens = [token for token in _clean_token(source).split("_") if token]
    while len(tokens) > 1 and tokens[-1] in _FAMILY_SUFFIXES:
        tokens.pop()
    return "_".join(tokens) if tokens else "unknown"


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
        {
            step.branch_id
            for step in steps
            if _outcome_pattern(step) == "weak_positive"
        }
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
            _REPEATED_CONTRACT_REROUTE_REASON in str(value)
            for value in item.values()
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
            record.get("record_digest")
            or record.get("requirement_digest")
            or ""
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
    return any(
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
    ) or lower == _REPEATED_CONTRACT_REROUTE_REASON


def _clean_token(value: Any) -> str:
    text = str(value or "").strip().lower()
    cleaned = "".join(char if char.isalnum() else "_" for char in text)
    return "_".join(part for part in cleaned.split("_") if part)


def _clean_path(value: Any) -> str:
    text = str(value or "").strip()
    return text.replace("\\", "/")


__all__ = ["build_cross_branch_research_observability"]
