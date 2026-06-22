"""Telemetry/schema retry projection helpers for proposal prompts."""

from __future__ import annotations

import json
from typing import Any


def schema_retry_feedback_json(value: Any) -> str:
    """Render schema retry feedback without clipping its legal telemetry template."""

    try:
        return json.dumps(value, indent=2, sort_keys=True, default=str)
    except TypeError:
        return str(value)


def schema_retry_feedback_projection(
    *,
    retry_attempt: Any,
    retry_rule: Any,
    preview_rejections: Any,
) -> dict[str, Any]:
    if not isinstance(preview_rejections, list):
        preview_rejections = [preview_rejections]
    raw_items = [item for item in preview_rejections[-3:] if isinstance(item, dict)]
    compact_items = []
    for index, item in enumerate(raw_items):
        compact_items.append(
            _schema_retry_feedback_item(
                item,
                include_allowed_template=index == len(raw_items) - 1,
            )
        )
    latest = compact_items[-1] if compact_items else {}
    latest_failure_code = latest.get("failure_code")
    return _drop_empty(
        {
            "retry_attempt": retry_attempt,
            "attempt_kind": latest.get("attempt_kind")
            or "schema_accounting_repair",
            "repair_classification": latest.get("repair_classification"),
            "retry_mode": _retry_mode_for_failure_code(latest_failure_code),
            "final_task": latest.get("final_task")
            or _final_task_for_failure_code(latest_failure_code),
            "retry_rule": retry_rule,
            "protected_exact_identity": latest.get("protected_identity")
            or _protected_identity_from_preserve(latest.get("preserve_hypothesis")),
            "latest_failure_code": latest_failure_code,
            "required_mechanism_ids": latest.get("required_mechanism_ids"),
            "candidate_mechanism_ids": latest.get("candidate_mechanism_ids"),
            "candidate_target_file": latest.get("candidate_target_file"),
            "allowed_repair_shape": latest.get("allowed_repair_shape"),
            "allowed_top_level_categories": latest.get("allowed_top_level_categories"),
            "exact_allowed_top_level_categories": latest.get(
                "exact_allowed_top_level_categories"
            ),
            "declared_mechanism_ids": latest.get("declared_mechanism_ids"),
            "protected_mechanism_ids": latest.get("protected_mechanism_ids"),
            "template_mechanism_ids": latest.get("template_mechanism_ids"),
            "legal_mechanism_id_policy": latest.get("legal_mechanism_id_policy"),
            "allowed_expected_telemetry_template": latest.get(
                "allowed_expected_telemetry_template"
            ),
            "allowed_expected_telemetry_template_full": latest.get(
                "allowed_expected_telemetry_template_full"
            ),
            "preview_rejections": compact_items,
        }
    )


def _schema_retry_feedback_item(
    item: dict[str, Any],
    *,
    include_allowed_template: bool = True,
) -> dict[str, Any]:
    preserve = item.get("preserve_hypothesis")
    return _drop_empty(
        {
            "attempt": item.get("attempt"),
            "attempt_kind": item.get("attempt_kind"),
            "repair_classification": item.get("repair_classification"),
            "failure_code": item.get("failure_code"),
            "source": item.get("source"),
            "corrective_retry": item.get("corrective_retry"),
            "drift_fields": item.get("drift_fields"),
            "reason": _limit_text(str(item.get("reason") or ""), 900),
            "reason_full": item.get("reason_full"),
            "c11_detail_full": item.get("c11_detail_full"),
            "telemetry_detail_full": item.get("telemetry_detail_full"),
            "problem_telemetry_detail_full": item.get(
                "problem_telemetry_detail_full"
            ),
            "requested_activation_fields": _bounded_list(
                item.get("requested_activation_fields"),
                8,
            ),
            "offending_fields": _bounded_list(item.get("offending_fields"), 8),
            "offending_fields_full": item.get("offending_fields_full"),
            "allowed_top_level_categories": _bounded_list(
                item.get("allowed_top_level_categories"),
                16,
            ),
            "exact_allowed_top_level_categories": _bounded_list(
                item.get("exact_allowed_top_level_categories"),
                16,
            ),
            "declared_mechanism_ids": _bounded_list(
                item.get("declared_mechanism_ids"),
                16,
            ),
            "protected_mechanism_ids": _bounded_list(
                item.get("protected_mechanism_ids"),
                16,
            ),
            "template_mechanism_ids": _bounded_list(
                item.get("template_mechanism_ids"),
                16,
            ),
            "legal_mechanism_id_policy": _limit_text(
                str(item.get("legal_mechanism_id_policy") or ""),
                700,
            ),
            "allowed_expected_telemetry_template": (
                item.get("allowed_expected_telemetry_template")
                if include_allowed_template
                else None
            ),
            "allowed_expected_telemetry_template_full": (
                item.get("allowed_expected_telemetry_template_full")
                if include_allowed_template
                else None
            ),
            "required_mechanism_ids": _bounded_list(
                item.get("required_mechanism_ids"),
                16,
            ),
            "candidate_mechanism_ids": _bounded_list(
                item.get("candidate_mechanism_ids"),
                16,
            ),
            "candidate_target_file": item.get("candidate_target_file"),
            "allowed_repair_shape": item.get("allowed_repair_shape"),
            "final_task": item.get("final_task"),
            "protected_identity": item.get("protected_identity")
            or _protected_identity_from_preserve(preserve),
            "preserve_hypothesis": _compact_preserve_hypothesis(preserve),
            "retry_constraint": _limit_text(
                str(item.get("retry_constraint") or ""),
                700,
            ),
        }
    )


def _retry_mode_for_failure_code(failure_code: Any) -> str:
    if failure_code == "schema_retry_drift":
        return "identity_corrective"
    if failure_code == "launch_research_focus_required_mechanism":
        return "launch_focus_required_mechanism_repair"
    return "schema_telemetry_repair"


def _final_task_for_failure_code(failure_code: Any) -> str:
    if failure_code == "launch_research_focus_required_mechanism":
        return (
            "Rewrite the hypothesis around one prepared required_mechanism_ids "
            "value. Put that exact id in mechanism_changes and align expected "
            "telemetry refs to the same id; this launch-focus repair may "
            "replace the previous mechanism id."
        )
    return (
        "Repair expected_telemetry/schema fields for the same hypothesis. Do "
        "not explore, rename, retarget, or switch mechanism family during this "
        "schema retry. Treat this as telemetry/accounting repair, not "
        "algorithmic refinement."
    )


def _compact_preserve_hypothesis(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return _drop_empty(
        {
            "action": value.get("action"),
            "target_file": value.get("target_file"),
            "mechanism_changes": value.get("mechanism_changes"),
        }
    )


def _protected_identity_from_preserve(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    changes = value.get("mechanism_changes")
    mechanism_ids: list[str] = []
    if isinstance(changes, list):
        for change in changes:
            if isinstance(change, dict) and str(change.get("id") or "").strip():
                mechanism_ids.append(str(change.get("id")).strip())
    return _drop_empty(
        {
            "action": value.get("action"),
            "target_file": value.get("target_file"),
            "mechanism_change_ids": list(dict.fromkeys(mechanism_ids)),
            "mechanism_changes": changes,
        }
    )


def _limit_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - 3)] + "..."


def _bounded_list(value: Any, limit: int) -> list[Any]:
    if not isinstance(value, list):
        return []
    return value[:limit]


def _drop_empty(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if item not in ({}, [], None)}


__all__ = [
    "schema_retry_feedback_json",
    "schema_retry_feedback_projection",
]
