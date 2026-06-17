"""Generic canary failure taxonomy for evaluation evidence."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from typing import Any

from scion.core.models import CanaryResult

CANARY_FAILED = "CANARY_FAILED"
CANARY_CONFIG_ERROR = "CANARY_CONFIG_ERROR"

CANARY_FAILURE_CATEGORY_CANDIDATE = "candidate_failure"
CANARY_FAILURE_CATEGORY_CONFIG = "configuration_error"

_CONFIG_MARKERS = (
    "canary configuration error",
    "absolute_outside_roots",
    "outside workspace and safe_data_roots",
    "safe_data_roots",
    "canary split not configured",
    "experiment_protocol is required",
    "skeleton fallback disabled",
)


def canary_configuration_error(exc: BaseException) -> CanaryResult:
    """Create a structured fail-closed canary result for protocol config errors."""

    return CanaryResult(
        passed=False,
        reason=f"canary configuration error: {exc}",
        details={
            "schema_version": "scion.canary_result.v1",
            "failure_category": CANARY_FAILURE_CATEGORY_CONFIG,
            "reason_codes": [CANARY_CONFIG_ERROR],
        },
        failure_category=CANARY_FAILURE_CATEGORY_CONFIG,
        reason_codes=(CANARY_CONFIG_ERROR,),
    )


def normalize_canary_result(result: CanaryResult) -> CanaryResult:
    """Ensure failed canary results carry deterministic category/reason codes."""

    if result.passed:
        return result
    category = _category_for(result)
    codes = _reason_codes_for(result, category=category)
    details = dict(result.details or {})
    details.setdefault("schema_version", "scion.canary_result.v1")
    details.setdefault("failure_category", category)
    details.setdefault("reason_codes", list(codes))
    if result.failure_category == category and tuple(result.reason_codes or ()) == codes:
        if details == dict(result.details or {}):
            return result
    return replace(
        result,
        details=details,
        failure_category=category,
        reason_codes=codes,
    )


def public_canary_reason_codes(result: CanaryResult | None) -> tuple[str, ...]:
    """Return reason codes suitable for branch evidence and lifecycle memory.

    DecisionEngine stays intentionally blind to canary diagnostic text. This
    helper is used after DecisionFeatures have been evaluated so infrastructure
    canary vetoes do not become ordinary algorithm-failure lessons.
    """

    if result is None or result.passed:
        return ()
    normalized = normalize_canary_result(result)
    return tuple(normalized.reason_codes or (CANARY_FAILED,))


def decision_reason_codes_for_canary(
    existing: tuple[str, ...],
    result: CanaryResult | None,
) -> tuple[str, ...]:
    """Merge public canary codes into deterministic decision/evidence codes.

    Configuration errors are not algorithmic canary failures. They replace the
    generic DecisionEngine canary veto code so branch memory does not learn a
    false no-effect lesson from an invalid protocol setup.
    """

    reason_codes = public_canary_reason_codes(result)
    if not reason_codes:
        return tuple(existing or ())
    if is_canary_config_error(result):
        return reason_codes
    return tuple(dict.fromkeys([*tuple(existing or ()), *reason_codes]))


def is_canary_config_error(result: CanaryResult | None) -> bool:
    if result is None or result.passed:
        return False
    normalized = normalize_canary_result(result)
    if normalized.failure_category == CANARY_FAILURE_CATEGORY_CONFIG:
        return True
    return CANARY_CONFIG_ERROR in set(normalized.reason_codes or ())


def _category_for(result: CanaryResult) -> str:
    explicit = str(getattr(result, "failure_category", "") or "").strip()
    if explicit:
        return explicit
    details = result.details if isinstance(result.details, Mapping) else {}
    detail_category = str(details.get("failure_category") or "").strip()
    if detail_category:
        return detail_category
    if _looks_like_config_error(result.reason, details):
        return CANARY_FAILURE_CATEGORY_CONFIG
    return CANARY_FAILURE_CATEGORY_CANDIDATE


def _reason_codes_for(
    result: CanaryResult,
    *,
    category: str,
) -> tuple[str, ...]:
    codes = tuple(
        dict.fromkeys(
            str(code).strip()
            for code in tuple(getattr(result, "reason_codes", ()) or ())
            if str(code).strip()
        )
    )
    if codes:
        return codes
    details = result.details if isinstance(result.details, Mapping) else {}
    detail_codes = details.get("reason_codes")
    if isinstance(detail_codes, (list, tuple)):
        codes = tuple(
            dict.fromkeys(
                str(code).strip() for code in detail_codes if str(code).strip()
            )
        )
        if codes:
            return codes
    if category == CANARY_FAILURE_CATEGORY_CONFIG:
        return (CANARY_CONFIG_ERROR,)
    return (CANARY_FAILED,)


def _looks_like_config_error(reason: str | None, details: Mapping[str, Any]) -> bool:
    text_parts = [str(reason or "")]
    for key in (
        "failure_reason",
        "error",
        "error_code",
        "path_resolution_status",
        "case_resolution_status",
        "raw_metrics_unavailable_reason",
    ):
        value = details.get(key)
        if value:
            text_parts.append(str(value))
    text = " ".join(text_parts).lower()
    return any(marker.lower() in text for marker in _CONFIG_MARKERS)


__all__ = [
    "CANARY_FAILED",
    "CANARY_CONFIG_ERROR",
    "CANARY_FAILURE_CATEGORY_CANDIDATE",
    "CANARY_FAILURE_CATEGORY_CONFIG",
    "canary_configuration_error",
    "normalize_canary_result",
    "public_canary_reason_codes",
    "decision_reason_codes_for_canary",
    "is_canary_config_error",
]
