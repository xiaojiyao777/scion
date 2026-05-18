"""Shared helpers for bounded agentic proposal sessions.

This module contains pure serialization, sanitization, and compacting primitives
used by the session state machine and its prompt/preview helper modules.
"""
from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any, Mapping

def _bounded_string_list(value: Any, *, limit: int) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    out: list[str] = []
    for item in value:
        text = _limit_string(item, 320)
        if text:
            out.append(text)
        if len(out) >= limit:
            break
    return out


def _limit_string(value: Any, limit: int) -> str | None:
    if value in (None, ""):
        return None
    text = str(value)
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)] + "..."


def _drop_empty_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        str(key): item
        for key, item in value.items()
        if item not in (None, "", [], {}, ())
    }

def _enum_value(value: Any) -> Any:
    return value.value if isinstance(value, Enum) else value

def _drop_empty_dict(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if item not in ({}, [], None)}

def _json_ready(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return _json_ready(asdict(value))
    if isinstance(value, Mapping):
        return {str(k): _json_ready(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [_json_ready(v) for v in value]
    if isinstance(value, list):
        return [_json_ready(v) for v in value]
    return value


def _json_size(value: Any) -> int:
    return len(json.dumps(_json_ready(value), sort_keys=True, default=str))

def _sanitize_agentic_value(value: Any) -> Any:
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
            cleaned[key_text] = _sanitize_agentic_value(item)
        return cleaned
    if isinstance(value, tuple):
        return [_sanitize_agentic_value(item) for item in value]
    if isinstance(value, list):
        return [_sanitize_agentic_value(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return _sanitize_agentic_value(asdict(value))
    if isinstance(value, str):
        return _sanitize_agentic_text(value)
    return value


def _sanitize_agentic_text(text: str) -> str:
    forbidden_terms = (
        "raw_metrics_ref",
        "raw metrics",
        "validation",
        "frozen",
        "holdout",
    )
    safe_lines = []
    for line in text.splitlines():
        lowered = line.lower()
        if any(term in lowered for term in forbidden_terms):
            continue
        safe_lines.append(line)
    return "\n".join(safe_lines)
