"""Prompt projection for typed problem opportunity summaries."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping

from scion.opportunity.summary import redact_problem_opportunity_payload


_ITEM_LIMIT = 8
_SEQUENCE_LIMIT = 8
_TEXT_CHARS = 260
_MEASUREMENT_FIELDS = (
    "schema_version",
    "problem_family",
    "measurement_declared",
    "readiness_status",
    "readiness_reason_code",
    "runtime_model",
    "pairing_validity",
    "effect_metric",
    "effect_unit",
    "practical_delta_screen",
    "practical_delta_validate",
    "mde_at_power_80",
    "noise_band_p90_abs",
    "effect_to_mde_ratio",
    "signal_to_noise_tier",
    "calibration_freshness",
    "evidence_depth",
    "decision_features_excluded",
)


def compact_problem_opportunity_summary(payload: Any) -> str:
    """Return a bounded proposal-visible rendering of an opportunity summary."""

    if not isinstance(payload, Mapping):
        return ""
    redacted = redact_problem_opportunity_payload(dict(payload))
    if not isinstance(redacted, Mapping):
        return ""
    compact = _drop_empty(
        {
            "schema_version": (
                redacted.get("schema_version")
                or "scion.problem_opportunity_summary.v1"
            ),
            "problem_family": _project_scalar(redacted.get("problem_family")),
            "objective": _project_scalar(redacted.get("objective")),
            "proposal_visibility_only": True,
            "decision_features_excluded": True,
            "decision_input_policy": "excluded_from_decision_features",
            "residual_opportunity": _project_items(
                redacted.get("residual_opportunity"),
                fields=("axis_id", "metric", "status", "summary", "reason_codes"),
            ),
            "mechanism_evidence": _project_items(
                redacted.get("mechanism_evidence"),
                fields=(
                    "mechanism_family",
                    "evidence_status",
                    "opportunity_status",
                    "effect_status",
                    "summary",
                    "recommended_action",
                    "reason_codes",
                ),
            ),
            "protected_cases": _project_items(
                redacted.get("protected_cases"),
                fields=("case_id", "reason", "required_evidence"),
            ),
            "measurement": _project_mapping(
                redacted.get("measurement"),
                fields=_MEASUREMENT_FIELDS,
            ),
            "default_avoid": _project_items(
                redacted.get("default_avoid"),
                fields=("mechanism_family", "reason"),
            ),
        }
    )
    if len(compact) <= 5:
        return ""
    rendered = json.dumps(compact, indent=2, sort_keys=True, default=str)
    return (
        "Problem-owned solver opportunity summary for proposal planning only. "
        "This summary is tainted proposal context, excluded from DecisionFeatures, "
        "and must not be treated as Protocol evidence or an acceptance signal. "
        "Raw pairs, raw calibration rows, validation/frozen/holdout details, "
        "BKS/case-gap data, prompt ratios, and LLM prose are intentionally "
        "omitted.\n"
        f"{rendered}"
    )


def _project_items(value: Any, *, fields: tuple[str, ...]) -> list[dict[str, Any]]:
    if not isinstance(value, (list, tuple)):
        return []
    items: list[dict[str, Any]] = []
    for raw in value:
        projected = _project_mapping(raw, fields=fields)
        if projected:
            items.append(projected)
    if len(items) > _ITEM_LIMIT:
        omitted = len(items) - _ITEM_LIMIT
        items = items[:_ITEM_LIMIT]
        items.append(
            {
                "omitted_item_count": omitted,
                "omitted_reason": "additional_problem_opportunity_items_distilled",
            }
        )
    return items


def _project_mapping(value: Any, *, fields: tuple[str, ...]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return _drop_empty(
        {
            field: _project_value(value.get(field))
            for field in fields
            if field in value
        }
    )


def _project_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _drop_empty(
            {str(key): _project_value(child) for key, child in value.items()}
        )
    if isinstance(value, (list, tuple)):
        projected = [_project_value(item) for item in list(value)[:_SEQUENCE_LIMIT]]
        result = [item for item in projected if item not in ("", None, [], {}, ())]
        if len(value) > _SEQUENCE_LIMIT:
            result.append({"omitted_item_count": len(value) - _SEQUENCE_LIMIT})
        return result
    if isinstance(value, str):
        return _short_text(value)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return _short_text(str(value))


def _project_scalar(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return _project_value(value)
    return _short_text(str(value))


def _short_text(value: str) -> str:
    text = re.sub(r"\s+", " ", value).strip()
    if len(text) <= _TEXT_CHARS:
        return text
    head = text[:_TEXT_CHARS].rstrip()
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    omitted = len(text) - len(head)
    return f"{head} [omitted_chars={omitted} text_digest={digest}]"


def _drop_empty(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        str(key): value
        for key, value in payload.items()
        if value not in ("", None, [], {}, ())
    }
