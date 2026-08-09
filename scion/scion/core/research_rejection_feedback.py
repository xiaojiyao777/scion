"""Compact, typed feedback from the latest pre-Protocol rejection."""
from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import PurePosixPath
from typing import Any

RESEARCH_REJECTION_FEEDBACK_KEYS = (
    "failure_stage",
    "failure_detail",
    "failing_symbol",
    "callsite",
)
_ELIGIBLE_STAGES = frozenset(
    {"hypothesis_contract", "patch_contract", "verification"}
)
_DETAIL_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
_SYMBOL_RE = re.compile(
    r"^[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*$",
    flags=re.ASCII,
)
_CALLSITE_RE = re.compile(r"^(?P<path>[^:\r\n]+):(?P<line>[1-9]\d*)$")
_MAX_DETAIL_LENGTH = 128
_MAX_SYMBOL_LENGTH = 128
_MAX_CALLSITE_LENGTH = 256


def compact_research_rejection_from_event(
    event: Mapping[str, Any],
) -> dict[str, str] | None:
    """Project one typed lineage row without exposing identity or prose."""

    if str(event.get("execution_outcome") or "") != "research_rejected":
        return None
    provenance = _json_mapping(event.get("execution_outcome_provenance_json"))
    stage = str(provenance.get("stage") or event.get("stage") or "").strip()
    checks_key = (
        "verification_checks" if stage == "verification" else "contract_checks"
    )
    failed_check = _first_failed_check(provenance.get(checks_key))
    metadata = (
        failed_check.get("metadata")
        if isinstance(failed_check, Mapping)
        else None
    )
    if not isinstance(metadata, Mapping):
        metadata = {}
    detail = (
        failed_check.get("name")
        if isinstance(failed_check, Mapping)
        else event.get("execution_outcome_reason_code")
    )
    return sanitize_research_rejection_feedback(
        {
            "failure_stage": stage,
            "failure_detail": detail,
            "failing_symbol": metadata.get("failing_symbol"),
            "callsite": metadata.get("callsite"),
        }
    )


def sanitize_research_rejection_feedback(
    value: Mapping[str, Any] | None,
) -> dict[str, str] | None:
    """Return exactly four bounded fields, or reject an unusable projection."""

    if not isinstance(value, Mapping):
        return None
    stage = str(value.get("failure_stage") or "").strip()
    detail = str(value.get("failure_detail") or "").strip()
    if (
        stage not in _ELIGIBLE_STAGES
        or len(detail) > _MAX_DETAIL_LENGTH
        or not _DETAIL_RE.fullmatch(detail)
    ):
        return None
    symbol = str(value.get("failing_symbol") or "").strip()
    if symbol and (
        len(symbol) > _MAX_SYMBOL_LENGTH or not _SYMBOL_RE.fullmatch(symbol)
    ):
        symbol = ""
    return {
        "failure_stage": stage,
        "failure_detail": detail,
        "failing_symbol": symbol,
        "callsite": _relative_callsite(value.get("callsite")),
    }


def _json_mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    try:
        decoded = json.loads(str(value or "{}"))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return decoded if isinstance(decoded, Mapping) else {}


def _first_failed_check(value: Any) -> Mapping[str, Any] | None:
    if not isinstance(value, (list, tuple)):
        return None
    return next(
        (
            check
            for check in value
            if isinstance(check, Mapping) and check.get("passed") is False
        ),
        None,
    )


def _relative_callsite(value: Any) -> str:
    text = str(value or "").strip().replace("\\", "/")
    if len(text) > _MAX_CALLSITE_LENGTH:
        return ""
    match = _CALLSITE_RE.fullmatch(text)
    if match is None:
        return ""
    path = PurePosixPath(match.group("path"))
    if path.is_absolute() or ".." in path.parts or "." in path.parts:
        return ""
    normalized = path.as_posix()
    if not normalized or normalized.startswith("/"):
        return ""
    return f"{normalized}:{match.group('line')}"


__all__ = [
    "RESEARCH_REJECTION_FEEDBACK_KEYS",
    "compact_research_rejection_from_event",
    "sanitize_research_rejection_feedback",
]
