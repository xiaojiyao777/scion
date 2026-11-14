"""Generic final quality evidence package writer.

Callers provide already-evaluated case records. Problem-specific fields stay in
the extension payload supplied by the problem package; this module only writes
common artifact structure and aggregate outcome/runtime statistics.
"""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Mapping


__all__ = [
    "FinalQualityConfig",
    "FinalQualityPackage",
    "QualityCaseRecord",
    "build_final_quality_package",
    "write_final_quality_package",
]

COMPARISON_BETTER = "better"
COMPARISON_EQUAL = "equal"
COMPARISON_WORSE = "worse"
COMPARISON_NOT_COMPARABLE = "not_comparable"

_OK_STATUSES = {
    "ok",
    "success",
    "succeeded",
    "complete",
    "completed",
    "valid",
    "feasible",
    "passed",
}
_TIMEOUT_STATUSES = {"timeout", "timed_out"}
_CRASH_STATUSES = {"crash", "crashed"}
_ERROR_STATUSES = {"error", "failed", "failure", "invalid", "exception"}
_INFEASIBLE_STATUSES = {"infeasible"}

_COMMON_CASE_FIELDS = [
    "case_id",
    "subset",
    "seed",
    "baseline_status",
    "candidate_status",
    "comparison",
    "decisive_metric",
    "baseline_objective",
    "candidate_objective",
    "primary_delta",
    "metric_deltas",
    "baseline_elapsed_ms",
    "candidate_elapsed_ms",
    "runtime_ratio",
    "runtime_regression",
    "error_category",
    "problem_extension",
]

_FINAL_QUALITY_FIELDS = [
    "schema",
    "problem_id",
    "campaign_id",
    "baseline_label",
    "candidate_label",
    "n_cases",
    "n_ok",
    "n_timeout",
    "n_error",
    "n_infeasible",
    "better_vs_baseline",
    "equal_vs_baseline",
    "worse_vs_baseline",
    "primary_delta_sum",
    "primary_delta_median",
    "wall_time_total_ms",
    "wall_time_median_ms",
    "runtime_regressions",
    "problem_extension_schema",
    "problem_extension_summary",
]

_PACKAGE_FILES = {
    "manifest": "evidence_manifest.json",
    "final_quality_json": "final_quality.json",
    "final_quality_csv": "final_quality.csv",
    "per_case_quality_csv": "per_case_quality.csv",
    "runtime_summary": "runtime_summary.json",
    "failure_summary": "failure_summary.json",
}


@dataclass(frozen=True)
class QualityCaseRecord:
    """One baseline-vs-candidate final quality observation."""

    case_id: str
    subset: str | None = None
    seed: int | str | None = None
    baseline_status: str = "ok"
    candidate_status: str = "ok"
    comparison: str | None = None
    decisive_metric: str | None = None
    baseline_objective: float | None = None
    candidate_objective: float | None = None
    metric_deltas: Mapping[str, float] = field(default_factory=dict)
    baseline_elapsed_ms: float | None = None
    candidate_elapsed_ms: float | None = None
    error_category: str | None = None
    problem_extension: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FinalQualityConfig:
    """Configuration shared by all rows in a final quality package."""

    problem_id: str
    campaign_id: str
    baseline_label: str = "baseline"
    candidate_label: str = "candidate"
    runtime_regression_threshold: float = 2.0
    objective_sense: str = "minimize"
    primary_metric: str = "primary_objective"
    objective_tolerance: float = 1e-9
    problem_extension_schema: str | None = None
    problem_extension_summary: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FinalQualityPackage:
    """In-memory representation of the final evidence package."""

    manifest: Mapping[str, Any]
    final_quality: Mapping[str, Any]
    per_case_quality: tuple[Mapping[str, Any], ...]
    runtime_summary: Mapping[str, Any]
    failure_summary: Mapping[str, Any]


def build_final_quality_package(
    records: Iterable[QualityCaseRecord],
    config: FinalQualityConfig,
) -> FinalQualityPackage:
    """Build deterministic final quality evidence from evaluated case records."""

    _validate_config(config)
    internal_rows = tuple(_build_case_row(record, config) for record in records)
    runtime_summary = _build_runtime_summary(internal_rows, config)
    failure_summary = _build_failure_summary(internal_rows)
    final_quality = _build_final_quality_summary(
        per_case_rows=internal_rows,
        runtime_summary=runtime_summary,
        failure_summary=failure_summary,
        config=config,
    )
    per_case_rows = tuple(_public_payload(row) for row in internal_rows)
    manifest = {
        "schema": "scion.final_quality_manifest.v1",
        "package_type": "final_quality",
        "problem_id": config.problem_id,
        "campaign_id": config.campaign_id,
        "baseline_label": config.baseline_label,
        "candidate_label": config.candidate_label,
        "problem_extension_schema": config.problem_extension_schema,
        "n_cases": len(per_case_rows),
        "files": dict(_PACKAGE_FILES),
    }
    return FinalQualityPackage(
        manifest=manifest,
        final_quality=final_quality,
        per_case_quality=per_case_rows,
        runtime_summary=runtime_summary,
        failure_summary=failure_summary,
    )


def write_final_quality_package(
    package: FinalQualityPackage,
    output_dir: str | Path,
) -> dict[str, Path]:
    """Write the final quality package and return artifact paths by manifest key."""

    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)

    paths = {key: root / filename for key, filename in _PACKAGE_FILES.items()}
    _write_json(paths["manifest"], package.manifest)
    _write_json(paths["final_quality_json"], package.final_quality)
    _write_csv(paths["final_quality_csv"], [package.final_quality], _FINAL_QUALITY_FIELDS)
    _write_csv(paths["per_case_quality_csv"], list(package.per_case_quality), _COMMON_CASE_FIELDS)
    _write_json(paths["runtime_summary"], package.runtime_summary)
    _write_json(paths["failure_summary"], package.failure_summary)
    return paths


def _validate_config(config: FinalQualityConfig) -> None:
    if config.runtime_regression_threshold <= 0:
        raise ValueError("runtime_regression_threshold must be positive")
    if config.objective_sense not in {"minimize", "maximize"}:
        raise ValueError("objective_sense must be 'minimize' or 'maximize'")


def _build_case_row(
    record: QualityCaseRecord,
    config: FinalQualityConfig,
) -> dict[str, Any]:
    baseline_status = _normalize_status(record.baseline_status)
    candidate_status = _normalize_status(record.candidate_status)
    failure_categories = _failure_categories(record)
    runtime_ratio = _runtime_ratio(record.baseline_elapsed_ms, record.candidate_elapsed_ms)
    runtime_regression = (
        runtime_ratio is not None and runtime_ratio > config.runtime_regression_threshold
    )
    metric_deltas = dict(record.metric_deltas)
    primary_delta = _primary_delta(record, config)
    if primary_delta is not None and config.primary_metric not in metric_deltas:
        metric_deltas[config.primary_metric] = primary_delta

    comparison = _comparison(record, config, primary_delta, failure_categories)
    error_category = record.error_category or (
        failure_categories[0] if failure_categories else None
    )
    return {
        "case_id": record.case_id,
        "subset": record.subset,
        "seed": record.seed,
        "baseline_status": baseline_status,
        "candidate_status": candidate_status,
        "comparison": comparison,
        "decisive_metric": record.decisive_metric or config.primary_metric,
        "baseline_objective": record.baseline_objective,
        "candidate_objective": record.candidate_objective,
        "primary_delta": primary_delta,
        "metric_deltas": _stable_metric_deltas(metric_deltas),
        "baseline_elapsed_ms": record.baseline_elapsed_ms,
        "candidate_elapsed_ms": record.candidate_elapsed_ms,
        "runtime_ratio": runtime_ratio,
        "runtime_regression": runtime_regression,
        "error_category": error_category,
        "problem_extension": dict(record.problem_extension or {}),
        "_failure_categories": tuple(failure_categories),
    }


def _build_runtime_summary(
    rows: tuple[Mapping[str, Any], ...],
    config: FinalQualityConfig,
) -> dict[str, Any]:
    baseline_times = _number_values(row["baseline_elapsed_ms"] for row in rows)
    candidate_times = _number_values(row["candidate_elapsed_ms"] for row in rows)
    ratios = _number_values(row["runtime_ratio"] for row in rows)
    return {
        "schema": "scion.runtime_summary.v1",
        "runtime_regression_threshold": config.runtime_regression_threshold,
        "n_cases": len(rows),
        "n_with_runtime_ratio": len(ratios),
        "runtime_regressions": sum(1 for row in rows if row["runtime_regression"]),
        "baseline_elapsed_total_ms": _sum_or_none(baseline_times),
        "candidate_elapsed_total_ms": _sum_or_none(candidate_times),
        "baseline_elapsed_median_ms": _median_or_none(baseline_times),
        "candidate_elapsed_median_ms": _median_or_none(candidate_times),
        "runtime_ratio_median": _median_or_none(ratios),
    }


def _build_failure_summary(rows: tuple[Mapping[str, Any], ...]) -> dict[str, Any]:
    counts = {
        "timeout": 0,
        "crash": 0,
        "error": 0,
        "infeasible": 0,
    }
    failures: list[dict[str, Any]] = []
    for row in rows:
        categories = list(row["_failure_categories"])
        for category in categories:
            counts[category] = counts.get(category, 0) + 1
        if categories:
            failures.append(
                {
                    "case_id": row["case_id"],
                    "subset": row["subset"],
                    "seed": row["seed"],
                    "baseline_status": row["baseline_status"],
                    "candidate_status": row["candidate_status"],
                    "error_category": row["error_category"],
                    "failure_categories": categories,
                }
            )
    return {
        "schema": "scion.failure_summary.v1",
        "n_failures": len(failures),
        "counts_by_category": counts,
        "failures": failures,
    }


def _build_final_quality_summary(
    *,
    per_case_rows: tuple[Mapping[str, Any], ...],
    runtime_summary: Mapping[str, Any],
    failure_summary: Mapping[str, Any],
    config: FinalQualityConfig,
) -> dict[str, Any]:
    primary_deltas = _number_values(row["primary_delta"] for row in per_case_rows)
    candidate_times = _number_values(row["candidate_elapsed_ms"] for row in per_case_rows)
    failure_counts = failure_summary["counts_by_category"]
    return {
        "schema": "scion.final_quality.v1",
        "problem_id": config.problem_id,
        "campaign_id": config.campaign_id,
        "baseline_label": config.baseline_label,
        "candidate_label": config.candidate_label,
        "n_cases": len(per_case_rows),
        "n_ok": sum(1 for row in per_case_rows if _is_ok_case(row)),
        "n_timeout": failure_counts["timeout"],
        "n_error": failure_counts["crash"] + failure_counts["error"],
        "n_infeasible": failure_counts["infeasible"],
        "better_vs_baseline": sum(
            1 for row in per_case_rows if row["comparison"] == COMPARISON_BETTER
        ),
        "equal_vs_baseline": sum(
            1 for row in per_case_rows if row["comparison"] == COMPARISON_EQUAL
        ),
        "worse_vs_baseline": sum(
            1 for row in per_case_rows if row["comparison"] == COMPARISON_WORSE
        ),
        "primary_delta_sum": _sum_or_none(primary_deltas),
        "primary_delta_median": _median_or_none(primary_deltas),
        "wall_time_total_ms": _sum_or_none(candidate_times),
        "wall_time_median_ms": _median_or_none(candidate_times),
        "runtime_regressions": runtime_summary["runtime_regressions"],
        "problem_extension_schema": config.problem_extension_schema,
        "problem_extension_summary": dict(config.problem_extension_summary or {}),
    }


def _comparison(
    record: QualityCaseRecord,
    config: FinalQualityConfig,
    primary_delta: float | None,
    failure_categories: list[str],
) -> str:
    if failure_categories:
        return COMPARISON_NOT_COMPARABLE
    if record.comparison is not None:
        return _normalize_comparison(record.comparison)
    if primary_delta is None:
        return COMPARISON_NOT_COMPARABLE
    if primary_delta > config.objective_tolerance:
        return COMPARISON_BETTER
    if primary_delta < -config.objective_tolerance:
        return COMPARISON_WORSE
    return COMPARISON_EQUAL


def _primary_delta(
    record: QualityCaseRecord,
    config: FinalQualityConfig,
) -> float | None:
    if (
        not _is_ok_status(record.baseline_status)
        or not _is_ok_status(record.candidate_status)
        or record.baseline_objective is None
        or record.candidate_objective is None
    ):
        return None
    if config.objective_sense == "minimize":
        return record.baseline_objective - record.candidate_objective
    return record.candidate_objective - record.baseline_objective


def _failure_categories(record: QualityCaseRecord) -> list[str]:
    categories: list[str] = []
    for status in (record.baseline_status, record.candidate_status):
        status_category = _status_failure_category(status)
        if status_category and status_category not in categories:
            categories.append(status_category)
    if record.error_category:
        category = _normalize_failure_category(record.error_category)
        if category and category not in categories:
            categories.append(category)
    return categories


def _status_failure_category(status: str | None) -> str | None:
    normalized = _normalize_status(status)
    if normalized in _OK_STATUSES:
        return None
    if normalized in _TIMEOUT_STATUSES:
        return "timeout"
    if normalized in _CRASH_STATUSES:
        return "crash"
    if normalized in _INFEASIBLE_STATUSES:
        return "infeasible"
    if normalized in _ERROR_STATUSES:
        return "error"
    return "error"


def _normalize_failure_category(category: str) -> str | None:
    normalized = category.strip().lower()
    if normalized in _TIMEOUT_STATUSES:
        return "timeout"
    if normalized in _CRASH_STATUSES:
        return "crash"
    if normalized in _INFEASIBLE_STATUSES:
        return "infeasible"
    if normalized in _ERROR_STATUSES:
        return "error"
    return "error" if normalized else None


def _is_ok_status(status: str | None) -> bool:
    return _normalize_status(status) in _OK_STATUSES


def _normalize_status(status: str | None) -> str:
    return (status or "error").strip().lower()


def _normalize_comparison(comparison: str) -> str:
    normalized = comparison.strip().lower()
    if normalized in {"better", "win", "candidate_better", "improved"}:
        return COMPARISON_BETTER
    if normalized in {"equal", "tie", "same"}:
        return COMPARISON_EQUAL
    if normalized in {"worse", "loss", "candidate_worse", "regressed"}:
        return COMPARISON_WORSE
    if normalized in {"not_comparable", "no_comparison", "failed", "unknown"}:
        return COMPARISON_NOT_COMPARABLE
    return normalized


def _runtime_ratio(
    baseline_elapsed_ms: float | None,
    candidate_elapsed_ms: float | None,
) -> float | None:
    if (
        baseline_elapsed_ms is None
        or candidate_elapsed_ms is None
        or baseline_elapsed_ms <= 0
    ):
        return None
    return candidate_elapsed_ms / baseline_elapsed_ms


def _is_ok_case(row: Mapping[str, Any]) -> bool:
    categories = set(row["_failure_categories"])
    return not categories.intersection({"timeout", "crash", "error", "infeasible"})


def _stable_metric_deltas(metric_deltas: Mapping[str, float]) -> dict[str, float]:
    return {key: metric_deltas[key] for key in sorted(metric_deltas)}


def _number_values(values: Any) -> list[float]:
    return [float(value) for value in values if value is not None]


def _sum_or_none(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values)


def _median_or_none(values: list[float]) -> float | None:
    if not values:
        return None
    return float(median(values))


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(_public_payload(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_csv(
    path: Path,
    rows: list[Mapping[str, Any]],
    fieldnames: list[str],
) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_cell(row.get(field)) for field in fieldnames})


def _public_payload(payload: Any) -> Any:
    if isinstance(payload, Mapping):
        return {
            key: _public_payload(value)
            for key, value in payload.items()
            if not str(key).startswith("_")
        }
    if isinstance(payload, tuple):
        return [_public_payload(value) for value in payload]
    if isinstance(payload, list):
        return [_public_payload(value) for value in payload]
    return payload


def _csv_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (Mapping, list, tuple)):
        return json.dumps(_public_payload(value), sort_keys=True)
    return str(value)
