"""C11 expected-telemetry retry feedback helpers for hypothesis previews."""

from __future__ import annotations

from typing import Any, Mapping


CONTRACT_BOUNDARY_FAILURE = "contract_boundary_failure"


def expected_telemetry_retry_feedback(
    hypothesis: Mapping[str, Any],
    telemetry: Mapping[str, Any],
    problem_telemetry: Mapping[str, Any],
    *,
    detail: str,
    attempt: int,
    c11_detail: str,
    telemetry_detail: str,
    preserve_hypothesis: Mapping[str, Any],
    protected_identity: Mapping[str, Any],
) -> dict[str, Any]:
    allowed_template = telemetry.get("allowed_expected_telemetry_template")
    if not isinstance(allowed_template, Mapping):
        allowed_template = {}
    allowed_categories = _string_list_from_any(
        telemetry.get("exact_allowed_top_level_categories")
        or telemetry.get("allowed_top_level_categories")
        or telemetry.get("allowed_categories")
    )
    declared_mechanism_ids = _string_list_from_any(
        telemetry.get("declared_mechanism_ids")
    )
    template_mechanism_ids = _string_list_from_any(
        telemetry.get("template_mechanism_ids")
        or allowed_template.get("mechanism_ids")
        or allowed_template.get("mechanism_id")
    )
    requested_fields = telemetry.get("requested_fields")
    reason_full = (
        str(problem_telemetry.get("reason") or "")
        or telemetry_detail
        or c11_detail
        or detail
    )
    requested_activation = ()
    if isinstance(requested_fields, Mapping):
        activation = requested_fields.get("activation")
        if isinstance(activation, (list, tuple)):
            requested_activation = tuple(
                str(field).strip() for field in activation if str(field).strip()
            )
    offending_fields_full = _string_list_from_any(
        problem_telemetry.get("offending_fields_full")
        or problem_telemetry.get("offending_fields")
        or requested_activation
    )
    template_expected_fields = _template_expected_fields(allowed_template)
    telemetry_unsupported = _telemetry_unsupported_for_surface(
        reason_full,
        requested_fields=requested_fields,
        offending_fields=offending_fields_full,
        template_expected_fields=template_expected_fields,
    )
    clear_repair_shape = (
        {
            "expected_telemetry": {},
            "reason": (
                "selected surface declares no supported telemetry/evidence "
                "fields for expected_telemetry; clear the proposal telemetry "
                "claim instead of inventing runtime keys"
            ),
        }
        if telemetry_unsupported
        else {}
    )
    protected_mechanism_ids = sorted(
        dict.fromkeys(
            [
                *(
                    _string_list_from_any(
                        protected_identity.get("protected_mechanism_ids")
                    )
                ),
                *(
                    _string_list_from_any(
                        telemetry.get("protected_mechanism_ids")
                    )
                ),
                *(
                    _string_list_from_any(
                        (hypothesis.get("branch_continuation_guard") or {}).get(
                            "protected_mechanism_ids"
                        )
                        if isinstance(
                            hypothesis.get("branch_continuation_guard"),
                            Mapping,
                        )
                        else ()
                    )
                ),
            ]
        )
    )
    return _drop_empty_dict(
        {
            "attempt": attempt,
            "attempt_kind": "schema_accounting_repair",
            "repair_classification": "telemetry_schema_accounting_repair",
            "source": "hypothesis_preview_gate",
            "gate_name": "proposal.schema_preview",
            "failure_code": "C11_expected_telemetry",
            "failure_category": CONTRACT_BOUNDARY_FAILURE,
            "reason": _limit_string(reason_full, 1000),
            "reason_full": reason_full,
            "c11_detail_full": c11_detail,
            "telemetry_detail_full": telemetry_detail,
            "problem_telemetry_detail_full": problem_telemetry.get("reason"),
            "requested_activation_fields": list(requested_activation),
            "offending_fields": offending_fields_full[:8],
            "offending_fields_full": offending_fields_full,
            "allowed_top_level_categories": allowed_categories,
            "exact_allowed_top_level_categories": allowed_categories,
            "declared_mechanism_ids": declared_mechanism_ids,
            "protected_mechanism_ids": protected_mechanism_ids,
            "template_mechanism_ids": template_mechanism_ids,
            "legal_mechanism_id_policy": (
                "Expected telemetry paths for mechanism-specific evidence must "
                "use the exact declared/protected mechanism id. Do not replace "
                "that id with a broad aggregate phase, family, or runtime "
                "bucket label."
            ),
            "telemetry_category_guidance": problem_telemetry.get(
                "telemetry_category_guidance"
            ),
            "unsupported_expected_telemetry": telemetry_unsupported,
            "clear_expected_telemetry_allowed": telemetry_unsupported,
            "allowed_repair_shape": (
                problem_telemetry.get("allowed_repair_shape") or clear_repair_shape
            ),
            "forbidden_repair_shape": problem_telemetry.get("forbidden_repair_shape"),
            "final_task": (
                problem_telemetry.get("allowed_repair_shape")
                or clear_repair_shape
                or "Repair the expected_telemetry contract for the same mechanism."
            ),
            "allowed_expected_telemetry_template": (
                _compact_expected_telemetry_template(allowed_template)
            ),
            "allowed_expected_telemetry_template_full": dict(allowed_template),
            "preserve_hypothesis": dict(preserve_hypothesis),
            "protected_identity": dict(protected_identity),
            "retry_constraint": (
                "Repair only expected_telemetry/schema fields. Preserve the "
                "prior action, target_file, mechanism_changes ids/change_types, "
                "and telemetry activation mechanism refs; do not switch "
                "mechanisms or targets for a C11/schema retry. This is a "
                "schema/accounting repair, not a new algorithmic hypothesis. "
                "Natural-language hypothesis and novelty_signature wording may "
                "be clarified. If the selected surface declares no supported "
                "telemetry/evidence fields, set expected_telemetry to {} for "
                "this retry and keep the same mechanism and target."
            ),
        }
    )


def _template_expected_fields(value: Mapping[str, Any]) -> list[str]:
    expected = value.get("expected_telemetry")
    fields: list[str] = []
    if isinstance(expected, Mapping):
        for raw_fields in expected.values():
            if not isinstance(raw_fields, (list, tuple)):
                continue
            fields.extend(
                str(field).strip()
                for field in raw_fields
                if str(field).strip()
            )
    return sorted(dict.fromkeys(fields))


def _telemetry_unsupported_for_surface(
    reason: Any,
    *,
    requested_fields: Any,
    offending_fields: list[str],
    template_expected_fields: list[str],
) -> bool:
    reason_text = str(reason or "").lower()
    if "does not declare telemetry fields" in reason_text:
        return True
    if "does not declare telemetry" in reason_text:
        return True
    if "surface.evidence" in reason_text and not template_expected_fields:
        return True
    if template_expected_fields:
        return False
    if offending_fields:
        return True
    if isinstance(requested_fields, Mapping):
        return any(bool(fields) for fields in requested_fields.values())
    return False


def _compact_expected_telemetry_template(value: Mapping[str, Any]) -> dict[str, Any]:
    expected = value.get("expected_telemetry")
    compact_expected: dict[str, list[str]] = {}
    if isinstance(expected, Mapping):
        for category in ("activation", "budget", "effect", "activity"):
            fields = expected.get(category)
            if not isinstance(fields, (list, tuple)):
                continue
            compact_fields = [
                str(field).strip()
                for field in list(fields)
                if str(field).strip()
            ]
            if compact_fields:
                compact_expected[category] = compact_fields
    return _drop_empty_dict(
        {
            "selected_surface": value.get("selected_surface"),
            "mechanism_id": value.get("mechanism_id"),
            "mechanism_ids": _string_list_from_any(value.get("mechanism_ids")),
            "template_is_exact": value.get("template_is_exact"),
            "template_truncated": value.get("template_truncated"),
            "expected_telemetry": compact_expected,
        }
    )


def _string_list_from_any(value: Any) -> list[str]:
    if value in (None, "", (), [], {}):
        return []
    if isinstance(value, str):
        raw_items = [value]
    elif isinstance(value, Mapping):
        raw_items = list(value.values())
    else:
        try:
            raw_items = list(value)
        except TypeError:
            raw_items = [value]
    return sorted(
        dict.fromkeys(str(item).strip() for item in raw_items if str(item).strip())
    )


def _limit_string(value: Any, limit: int) -> str | None:
    if value in (None, ""):
        return None
    text = str(value)
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)] + "..."


def _drop_empty_dict(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if item not in ({}, [], None)}


__all__ = ["expected_telemetry_retry_feedback"]
