"""Lossless hypothesis prompt rendering for the direct V3 proposal engine."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from enum import Enum
from typing import Any

from .prompt_common import _CACHE_5M

_DIRECT_V3_STATIC_CONTEXT_KEYS = frozenset(
    {
        "problem_summary",
        "problem_object",
        "solver_mechanics",
        "research_surfaces",
        "objective_policy_guidance",
        "problem_measurement_diagnostics",
        "available_actions",
        "existing_target_files",
        "create_path_patterns",
        "champion_operators_code",
        "champion_stats",
    }
)
_HOST_CONTROL_KEYS = frozenset(
    {
        "branch_id",
        "champion_version",
        "schema_version",
        "taint",
        "proposal_visibility_only",
        "decision_features_excluded",
        "llm_trace_excluded",
        "gate_influence",
    }
)


def _split_direct_v3_hypothesis_context(
    context: Mapping[str, Any],
) -> tuple[list[dict], str]:
    static_context = {
        key: _hypothesis_research_value(context[key], path=f"$.{key}")
        for key in _DIRECT_V3_STATIC_CONTEXT_KEYS
        if key in context
    }
    evidence_context = {
        key: _hypothesis_research_value(value, path=f"$.{key}")
        for key, value in context.items()
        if key not in _DIRECT_V3_STATIC_CONTEXT_KEYS and key not in _HOST_CONTROL_KEYS
    }

    system_blocks = [
        {
            "type": "text",
            "text": (
                "You are a research agent optimising declared research surfaces "
                "of a combinatorial optimisation solver. Propose one "
                "algorithmically material hypothesis that can improve solver "
                "quality."
            ),
            "cache_control": _CACHE_5M,
        },
        {
            "type": "text",
            "text": (
                "## Direct V3 Static Problem And Champion Context\n"
                f"{_direct_v3_canonical_json(static_context)}"
            ),
            "cache_control": _CACHE_5M,
        },
        {
            "type": "text",
            "text": (
                "## Direct V3 Canonical Hypothesis Evidence\n"
                f"{_direct_v3_canonical_json(evidence_context)}"
            ),
        },
    ]
    user_prompt = (
        "## Analysis And Output Instructions\n"
        "Identify the bottleneck; propose one evidence-grounded mechanism-level change or refinement. "
        "Preserve objectives; use only visible research surfaces, "
        "actions, and files. Return the hypothesis through the required tool schema."
    )
    return system_blocks, user_prompt


def _hypothesis_research_value(value: Any, *, path: str) -> Any:
    if isinstance(value, Mapping):
        return {
            key: _hypothesis_research_value(child, path=f"{path}.{key}")
            for key, child in value.items()
            if key not in _HOST_CONTROL_KEYS
            and not (key == "version" and path == "$.champion_stats")
            and not (key == "problem_family" and path == "$.research_question")
        }
    if isinstance(value, (list, tuple)):
        return type(value)(
            _hypothesis_research_value(child, path=f"{path}[{index}]")
            for index, child in enumerate(value)
        )
    return value


def _direct_v3_canonical_json(value: Mapping[str, Any]) -> str:
    normalized = _direct_v3_json_value(value, path="$", active_ids=set())
    return json.dumps(
        normalized,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    )


def _direct_v3_json_value(
    value: Any,
    *,
    path: str,
    active_ids: set[int],
) -> Any:
    """Return a deterministic, complete JSON representation or fail closed."""

    if isinstance(value, Enum):
        value_type = type(value)
        return {
            "__scion_enum__": f"{value_type.__module__}.{value_type.__qualname__}",
            "name": value.name,
            "value": _direct_v3_json_value(
                value.value,
                path=f"{path}.value",
                active_ids=active_ids,
            ),
        }
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise TypeError(f"non-finite float in direct-v3 context at {path}")
        return value
    if isinstance(value, bytes):
        return {"__scion_bytes_hex__": value.hex()}

    tracked_id = id(value)
    if tracked_id in active_ids:
        raise TypeError(f"cyclic direct-v3 context value at {path}")
    active_ids.add(tracked_id)
    try:
        if isinstance(value, Mapping):
            normalized: dict[str, Any] = {}
            for key, child in value.items():
                if not isinstance(key, str):
                    raise TypeError(
                        "non-string mapping key in direct-v3 context at "
                        f"{path}: {key!r}"
                    )
                normalized[key] = _direct_v3_json_value(
                    child,
                    path=f"{path}.{key}",
                    active_ids=active_ids,
                )
            return normalized
        if isinstance(value, list):
            return [
                _direct_v3_json_value(
                    child,
                    path=f"{path}[{index}]",
                    active_ids=active_ids,
                )
                for index, child in enumerate(value)
            ]
        if isinstance(value, tuple):
            return {
                "__scion_tuple__": [
                    _direct_v3_json_value(
                        child,
                        path=f"{path}[{index}]",
                        active_ids=active_ids,
                    )
                    for index, child in enumerate(value)
                ]
            }
        if isinstance(value, (set, frozenset)):
            children = [
                _direct_v3_json_value(
                    child,
                    path=f"{path}[]",
                    active_ids=active_ids,
                )
                for child in value
            ]
            children.sort(
                key=lambda child: json.dumps(
                    child,
                    ensure_ascii=True,
                    sort_keys=True,
                    allow_nan=False,
                )
            )
            tag = (
                "__scion_frozenset__"
                if isinstance(value, frozenset)
                else "__scion_set__"
            )
            return {tag: children}
        if is_dataclass(value) and not isinstance(value, type):
            value_type = type(value)
            return {
                "__scion_dataclass__": (
                    f"{value_type.__module__}.{value_type.__qualname__}"
                ),
                "fields": {
                    field.name: _direct_v3_json_value(
                        getattr(value, field.name),
                        path=f"{path}.{field.name}",
                        active_ids=active_ids,
                    )
                    for field in fields(value)
                },
            }
        if callable(value):
            raise TypeError(
                "unsupported callable direct-v3 context value at "
                f"{path}: {type(value).__module__}.{type(value).__qualname__}"
            )
        state = getattr(value, "__dict__", None)
        if isinstance(state, Mapping):
            value_type = type(value)
            return {
                "__scion_python_object__": (
                    f"{value_type.__module__}.{value_type.__qualname__}"
                ),
                "state": _direct_v3_json_value(
                    state,
                    path=f"{path}.__dict__",
                    active_ids=active_ids,
                ),
            }
        raise TypeError(
            "unsupported non-JSON direct-v3 context value at "
            f"{path}: {type(value).__module__}.{type(value).__qualname__}"
        )
    finally:
        active_ids.remove(tracked_id)


_split_hypothesis_context = _split_direct_v3_hypothesis_context


__all__ = [
    "_split_direct_v3_hypothesis_context",
    "_split_hypothesis_context",
]
