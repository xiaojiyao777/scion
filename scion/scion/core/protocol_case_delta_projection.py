"""Report-only projection of protocol raw metrics into case-level deltas.

The projection is intentionally problem-neutral and lossless: problem-owned
postrun reviewers receive every public case pair and metric without core
teaching problem semantics or substituting a bounded summary for evidence.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

def protocol_case_level_deltas(
    protocol: Mapping[str, Any],
    *,
    campaign_path: Path,
) -> dict[str, Any]:
    """Return complete case -> metric-delta evidence from public metrics refs."""

    metrics_path = _resolve_public_metrics_path(protocol, campaign_path=campaign_path)
    if metrics_path is None:
        return {}
    metrics = _read_json_mapping(metrics_path)
    pairs = metrics.get("pairs")
    if not isinstance(pairs, list):
        return {}

    case_pairs: dict[str, list[Mapping[str, Any]]] = {}
    for pair in pairs:
        if not isinstance(pair, Mapping):
            continue
        case = _case_name(pair)
        if not case:
            continue
        metric_deltas = _numeric_mapping(pair.get("metric_deltas"))
        scalar_delta = _float_or_none(pair.get("delta"))
        if scalar_delta is None and not metric_deltas:
            continue
        case_pairs.setdefault(case, []).append(pair)

    return {
        case: _case_delta_summary(
            case,
            pairs_for_case,
        )
        for case, pairs_for_case in case_pairs.items()
    }


def _resolve_public_metrics_path(
    protocol: Mapping[str, Any],
    *,
    campaign_path: Path,
) -> Path | None:
    ref = _public_metrics_ref(protocol)
    if not ref:
        return None
    ref_path = Path(ref)
    if ref_path.is_absolute():
        return None
    root = campaign_path.expanduser().resolve()
    candidate = (root / ref_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    if not candidate.is_file():
        return None
    return candidate


def _public_metrics_ref(protocol: Mapping[str, Any]) -> str:
    public_ref = _clean_str(protocol.get("raw_metrics_public_ref"))
    if public_ref:
        return public_ref
    raw_ref = _clean_str(protocol.get("raw_metrics_ref"))
    if not raw_ref:
        return ""
    if _clean_str(protocol.get("raw_metrics_ref_scope")) == "public_artifact_ref":
        return raw_ref
    if not Path(raw_ref).is_absolute():
        return raw_ref
    return ""


def _read_json_mapping(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _case_delta_summary(
    case: str,
    pairs: list[Mapping[str, Any]],
) -> dict[str, Any]:
    scalar_deltas: list[float] = []
    metric_values: dict[str, list[float]] = {}
    comparison_counts: Counter[str] = Counter()
    samples: list[dict[str, Any]] = []

    for pair in pairs:
        scalar_delta = _float_or_none(pair.get("delta"))
        if scalar_delta is not None:
            scalar_deltas.append(scalar_delta)
        comparison = _clean_str(pair.get("comparison"))
        if comparison:
            comparison_counts[comparison] += 1
        metric_deltas = _numeric_mapping(pair.get("metric_deltas"))
        for metric, value in metric_deltas.items():
            metric_values.setdefault(metric, []).append(value)
        sample = _pair_sample(pair, scalar_delta, metric_deltas)
        if sample:
            samples.append(sample)

    summary: dict[str, Any] = {
        "case": case,
        "pair_count": len(pairs),
    }
    if scalar_deltas:
        summary["delta_median"] = _median(scalar_deltas)
    if comparison_counts:
        summary["comparison_counts"] = dict(sorted(comparison_counts.items()))
    if metric_values:
        summary["metric_delta_metric_count"] = len(metric_values)
        summary["metric_delta_medians"] = {
            metric: _median(values)
            for metric, values in sorted(metric_values.items())
            if values
        }
    if samples:
        summary["sample_pairs"] = samples
    return summary


def _pair_sample(
    pair: Mapping[str, Any],
    scalar_delta: float | None,
    metric_deltas: Mapping[str, float],
) -> dict[str, Any]:
    sample: dict[str, Any] = {}
    seed = pair.get("seed")
    if seed is not None:
        sample["seed"] = seed
    comparison = _clean_str(pair.get("comparison"))
    if comparison:
        sample["comparison"] = comparison
    if scalar_delta is not None:
        sample["delta"] = scalar_delta
    if metric_deltas:
        sample["metric_deltas"] = dict(sorted(metric_deltas.items()))
    return sample


def _case_name(pair: Mapping[str, Any]) -> str:
    return _clean_str(
        pair.get("case"),
        pair.get("case_id"),
        pair.get("instance"),
        pair.get("instance_id"),
    )


def _numeric_mapping(value: Any) -> dict[str, float]:
    if not isinstance(value, Mapping):
        return {}
    result: dict[str, float] = {}
    for key, item in value.items():
        number = _float_or_none(item)
        if number is not None:
            result[str(key)] = number
    return result


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    count = len(ordered)
    mid = count // 2
    if count % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def _clean_str(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _float_or_none(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None
