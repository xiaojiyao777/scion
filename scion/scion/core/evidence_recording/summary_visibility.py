"""Visibility audit rendering helpers for campaign summaries."""
from __future__ import annotations

from typing import Any, Iterable, Mapping

from scion.core.models import StepRecord

_VISIBILITY_AUDIT_RECORD_KEYS = {
    "schema_version",
    "record_type",
    "record_id",
    "record_digest",
    "requirement_digest",
    "requirement_id",
    "status",
    "requirement_status",
    "source",
    "source_ref",
    "artifact_ref",
    "digest",
    "reason_codes",
    "policy",
    "proposal_visibility_only",
    "decision_features_excluded",
    "decision_input_policy",
    "material_difference_required",
}

_VISIBILITY_AUDIT_CONTAINER_KEYS = {
    "cross_branch_research_audit_records",
    "material_difference_audit_records",
    "material_difference_requirement",
    "material_difference_requirement_ref",
    "material_difference_requirement_status",
    "cross_branch_research_payload",
    "cross_branch_research_status",
    "cross_branch_research_audit_ref",
    "novelty_pressure",
}


def _step_visibility_audit(
    step: StepRecord,
    *,
    candidate_intent_visibility: Mapping[str, Any],
    observability_value_visibility: Mapping[str, Any],
) -> dict[str, Any]:
    cross_branch_records, material_records = _step_cross_branch_material_records(step)
    return {
        "schema_version": "step_visibility_audit.v1",
        "proposal_visibility_only": True,
        "decision_features_excluded": True,
        "candidate_intent_visibility": {
            "status": "derived" if candidate_intent_visibility else "missing",
            "ref": "candidate_intent_visibility",
            "candidate_intent": candidate_intent_visibility.get(
                "candidate_intent",
                "unknown",
            ),
            "reason_codes": list(
                candidate_intent_visibility.get(
                    "candidate_intent_reason_codes",
                    (),
                )
                or ()
            ),
        },
        "observability_value_visibility": {
            "status": "derived" if observability_value_visibility else "missing",
            "ref": "observability_value_visibility",
            "observability_value_status": observability_value_visibility.get(
                "observability_value_status",
                "missing",
            ),
            "reason_codes": list(
                observability_value_visibility.get("reason_codes", ()) or ()
            ),
        },
        "cross_branch_research_visibility": {
            "status": "available" if cross_branch_records else "missing",
            "record_count": len(cross_branch_records),
            "records": cross_branch_records,
        },
        "material_difference_requirement_visibility": {
            "status": "available" if material_records else "missing",
            "record_count": len(material_records),
            "records": material_records,
        },
    }


def _step_cross_branch_material_records(
    step: StepRecord,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cross_branch_records: list[dict[str, Any]] = []
    material_records: list[dict[str, Any]] = []
    for source, value in (
        ("scheduler_audit_metadata", getattr(step, "scheduler_audit_metadata", {})),
        ("proposal_session_ref", getattr(step, "proposal_session_ref", {}) or {}),
    ):
        if not isinstance(value, Mapping):
            continue
        for kind, record in _visibility_records_from_mapping(value, source=source):
            if kind == "material":
                material_records.append(record)
            else:
                cross_branch_records.append(record)
    return (
        _dedupe_visibility_records(cross_branch_records),
        _dedupe_visibility_records(material_records),
    )


def _visibility_records_from_mapping(
    item: Mapping[str, Any],
    *,
    source: str,
) -> Iterable[tuple[str, dict[str, Any]]]:
    for key in (
        "cross_branch_research_audit_records",
        "material_difference_audit_records",
    ):
        values = item.get(key)
        if not isinstance(values, (list, tuple)):
            continue
        kind = "material" if key.startswith("material") else "cross_branch"
        for value in values:
            record = _compact_visibility_audit_record(value, source=source)
            if record:
                yield kind, record

    material_requirement = item.get("material_difference_requirement")
    if isinstance(material_requirement, Mapping):
        record = _compact_visibility_audit_record(
            material_requirement,
            source=source,
        )
        if record:
            yield "material", record

    for key in (
        "material_difference_requirement_ref",
        "material_difference_requirement_status",
        "cross_branch_research_audit_ref",
        "cross_branch_research_status",
    ):
        value = item.get(key)
        if value in (None, "", (), []):
            continue
        kind = "material" if key.startswith("material") else "cross_branch"
        yield kind, {
            "source": source,
            "record_type": key,
            "status": str(value) if "status" in key else "available",
            **({"source_ref": str(value)} if "ref" in key else {}),
        }

    for key in ("cross_branch_research_payload", "novelty_pressure"):
        payload = item.get(key)
        if not isinstance(payload, Mapping):
            continue
        for nested_kind, nested_record in _visibility_records_from_mapping(
            payload,
            source=f"{source}.{key}",
        ):
            yield nested_kind, nested_record


def _compact_visibility_audit_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        compact: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if key_text in _VISIBILITY_AUDIT_RECORD_KEYS:
                compact_item = _compact_visibility_scalar_or_list(item)
                if compact_item not in (None, [], {}):
                    compact[key_text] = compact_item
                continue
            if key_text in _VISIBILITY_AUDIT_CONTAINER_KEYS:
                compact_item = _compact_visibility_audit_value(item)
                if compact_item not in (None, [], {}):
                    compact[key_text] = compact_item
        return compact
    if isinstance(value, (list, tuple)):
        records = [
            _compact_visibility_audit_value(item)
            for item in value
            if isinstance(item, Mapping)
        ]
        return [record for record in records if record]
    return _compact_visibility_scalar_or_list(value)


def _compact_visibility_audit_record(
    value: Any,
    *,
    source: str,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    compact = _compact_visibility_audit_value(value)
    if not isinstance(compact, dict):
        return {}
    compact["source"] = str(compact.get("source") or source)
    if "status" not in compact:
        compact["status"] = "available"
    return compact


def _compact_visibility_scalar_or_list(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        compact: list[Any] = []
        for item in value:
            if isinstance(item, (str, int, float, bool)):
                compact.append(item)
        return compact
    if isinstance(value, Mapping):
        return _compact_visibility_audit_value(value)
    return None


def _dedupe_visibility_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str, str]] = set()
    deduped: list[dict[str, Any]] = []
    for record in records:
        key = (
            str(record.get("record_id") or ""),
            str(record.get("record_digest") or ""),
            str(record.get("source_ref") or ""),
            str(record.get("record_type") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(record)
    return deduped
