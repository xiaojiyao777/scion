"""Shared utility helpers for proposal tool modules."""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import PurePosixPath
from typing import Any, Mapping

from scion.proposal.tools.models import (
    ProposalExposureLevel,
    ProposalObservation,
    ProposalToolContext,
    ProposalToolFailureCode,
)

def _strip_forbidden_payload_refs(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _strip_forbidden_value(payload)

def _strip_forbidden_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        cleaned = {}
        for key, item in value.items():
            key_text = str(key)
            if key_text in {
                "artifact_path",
                "audit_payload_json",
                "internal_audit_payload",
                "raw_metrics_path",
                "raw_metrics_public_ref",
                "raw_metrics_ref",
                "case_ids",
                "seed_set",
                "pair_feedback",
            }:
                continue
            cleaned[key_text] = _strip_forbidden_value(item)
        return cleaned
    if isinstance(value, tuple):
        return [_strip_forbidden_value(item) for item in value]
    if isinstance(value, list):
        return [_strip_forbidden_value(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    return value

def _error_observation(
    context: ProposalToolContext,
    *,
    tool_name: str,
    tool_call_id: str,
    failure_code: ProposalToolFailureCode,
    summary: str,
    structured_payload: Mapping[str, Any] | None = None,
    repair_hint: str | None = None,
) -> ProposalObservation:
    return ProposalObservation(
        observation_id=str(uuid.uuid4()),
        session_id=context.session_id,
        tool_name=tool_name,
        tool_call_id=tool_call_id,
        observation_type="tool_error",
        summary=summary,
        structured_payload=_strip_forbidden_payload_refs(structured_payload or {}),
        exposure_level=ProposalExposureLevel.NONE,
        is_error=True,
        failure_code=failure_code,
        repair_hint=repair_hint,
    )

def _model_payload(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        return _strip_forbidden_value(value.model_dump(mode="json"))
    if is_dataclass(value):
        return _strip_forbidden_value(asdict(value))
    if isinstance(value, Mapping):
        return _strip_forbidden_value(dict(value))
    if isinstance(value, tuple):
        return [_model_payload(item) for item in value]
    if isinstance(value, list):
        return [_model_payload(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    return value

def _attr(value: Any, name: str, default: Any = None) -> Any:
    if value is None:
        return default
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)

def _stage_value(stage: Any) -> str:
    return str(getattr(stage, "value", stage) or "")

def _normalize_rel_path(path: str) -> str | None:
    raw_path = str(path).replace(os.sep, "/")
    if raw_path.startswith("/"):
        return None
    raw = raw_path
    if not raw or raw in {".", ".."}:
        return None
    parts = PurePosixPath(raw).parts
    if any(part in {"..", ""} for part in parts):
        return None
    return "/".join(parts)

def _limit_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    suffix = "\n[truncated by proposal tool result budget]"
    return text[: max(0, max_chars - len(suffix))] + suffix

def _json_size(value: Any) -> int:
    return len(json.dumps(value, sort_keys=True, default=str))

__all__ = [
    "_attr",
    "_error_observation",
    "_json_size",
    "_limit_text",
    "_model_payload",
    "_normalize_rel_path",
    "_stage_value",
    "_strip_forbidden_payload_refs",
    "_strip_forbidden_value",
]
