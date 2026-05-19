"""Runtime attribution compaction for screening feedback."""

from __future__ import annotations

from typing import Any, Mapping

from scion.core.models import StepRecord
from scion.proposal.tools.feedback.constants import (
    _RUNTIME_ATTRIBUTION_PRIORITY_SUFFIXES,
    _RUNTIME_ATTRIBUTION_SUFFIXES,
)
from scion.proposal.tools.feedback.stats import _eval_stats_payload
from scion.proposal.tools.surface.compaction import _drop_empty_items
from scion.proposal.tools.utils import _limit_text, _strip_forbidden_value


def _surface_runtime_attribution_payload(step: StepRecord) -> dict[str, Any]:
    protocol = step.protocol_result
    if protocol is None:
        return {}
    summary = protocol.candidate_surface_runtime_summary or {}
    if not isinstance(summary, Mapping):
        return {}
    fields = summary.get("fields")
    if not isinstance(fields, Mapping):
        return {}
    candidates: list[tuple[tuple[int, int, str], dict[str, Any]]] = []
    for field_name, field_summary in fields.items():
        if not isinstance(field_name, str) or not isinstance(field_summary, Mapping):
            continue
        if not _runtime_attribution_field_is_interesting(field_name, field_summary):
            continue
        candidates.append(
            (
                _runtime_attribution_sort_key(field_name, field_summary),
                {
                    "field": field_name,
                    "present": field_summary.get("present"),
                    "missing": field_summary.get("missing"),
                    "empty": field_summary.get("empty"),
                    "failed": field_summary.get("failed"),
                    "numeric_summary": _strip_forbidden_value(
                        field_summary.get("numeric_summary") or {}
                    ),
                    "values": _compact_runtime_attribution_values(
                        field_summary.get("values")
                    ),
                },
            )
        )
    candidates.sort(key=lambda item: item[0])
    highlights = [payload for _sort_key, payload in candidates[:12]]
    if not highlights:
        return {}
    return {
        "round_num": step.round_num,
        "branch_id": step.branch_id,
        "surface": step.hypothesis.change_locus,
        "target_file": step.hypothesis.target_file,
        "gate_outcome": protocol.gate_outcome,
        "reason_codes": list(protocol.reason_codes),
        "stats": _eval_stats_payload(protocol.stats),
        "runtime_field_highlights": highlights,
    }
def _runtime_highlight_is_all_zero_numeric(highlight: Mapping[str, Any]) -> bool:
    numeric = highlight.get("numeric_summary")
    if not isinstance(numeric, Mapping):
        return False
    summaries = _runtime_numeric_leaf_summaries(numeric)
    if not summaries:
        return False
    observed = False
    for summary in summaries:
        try:
            count = int(summary.get("observed_count") or 0)
        except (TypeError, ValueError):
            count = 0
        if count <= 0:
            continue
        observed = True
        if _safe_positive_int(summary.get("nonzero_count")):
            return False
        try:
            if abs(float(summary.get("weighted_sum") or 0.0)) > 1e-12:
                return False
        except (TypeError, ValueError):
            return False
    return observed
def _runtime_numeric_leaf_summaries(
    numeric: Mapping[str, Any],
) -> list[Mapping[str, Any]]:
    summaries: list[Mapping[str, Any]] = []
    stack: list[Any] = [numeric]
    while stack:
        value = stack.pop()
        if not isinstance(value, Mapping):
            continue
        if "observed_count" in value and (
            "nonzero_count" in value or "weighted_sum" in value
        ):
            summaries.append(value)
            continue
        stack.extend(value.values())
    return summaries
def _runtime_highlight_has_nonzero_numeric(highlight: Mapping[str, Any]) -> bool:
    numeric = highlight.get("numeric_summary")
    if not isinstance(numeric, Mapping):
        return False
    stack: list[Any] = [numeric]
    while stack:
        value = stack.pop()
        if isinstance(value, Mapping):
            for key, nested in value.items():
                if key in {"nonzero_count", "positive_count"} and _safe_positive_int(
                    nested
                ):
                    return True
                if key == "weighted_sum":
                    try:
                        if abs(float(nested or 0.0)) > 1e-12:
                            return True
                    except (TypeError, ValueError):
                        pass
                stack.append(nested)
        elif isinstance(value, list):
            stack.extend(value)
    return False
def _runtime_attribution_sort_key(
    field_name: str,
    field_summary: Mapping[str, Any],
) -> tuple[int, int, str]:
    has_issue = any(
        _safe_positive_int(field_summary.get(key))
        for key in ("missing", "empty", "failed")
    )
    priority = len(_RUNTIME_ATTRIBUTION_PRIORITY_SUFFIXES)
    for index, suffix in enumerate(_RUNTIME_ATTRIBUTION_PRIORITY_SUFFIXES):
        if field_name.endswith(suffix):
            priority = index
            break
    return (0 if has_issue else 1, priority, field_name)
def _runtime_attribution_field_is_interesting(
    field_name: str,
    field_summary: Mapping[str, Any],
) -> bool:
    for key in ("missing", "empty", "failed"):
        if _safe_positive_int(field_summary.get(key)):
            return True
    return any(field_name.endswith(suffix) for suffix in _RUNTIME_ATTRIBUTION_SUFFIXES)
def _safe_positive_int(value: Any) -> bool:
    try:
        return int(value or 0) > 0
    except (TypeError, ValueError):
        return False
def _compact_runtime_attribution_values(values: Any) -> list[dict[str, Any]]:
    if not isinstance(values, list):
        return []
    compact: list[dict[str, Any]] = []
    for item in values[:3]:
        if not isinstance(item, Mapping):
            continue
        compact.append(
            _drop_empty_items(
                {
                    "value": _limit_text(str(item.get("value", "")), 240),
                    "count": item.get("count"),
                }
            )
        )
    return compact

__all__ = [
    "_surface_runtime_attribution_payload",
    "_runtime_highlight_is_all_zero_numeric",
    "_runtime_numeric_leaf_summaries",
    "_runtime_highlight_has_nonzero_numeric",
    "_runtime_attribution_sort_key",
    "_runtime_attribution_field_is_interesting",
    "_safe_positive_int",
    "_compact_runtime_attribution_values",
]
