"""CVRP fixed case manifest builder.

The builder consumes existing result CSV artifacts through typed result rows and
keeps CVRPLIB instance paths as opaque strings. It does not load instances or
run solvers.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from scion.evidence.cvrp_baseline_import import (
    CvrpCsvResultRow,
    load_cvrp_result_rows,
)


__all__ = [
    "CvrpCaseEntry",
    "CvrpCaseManifest",
    "CvrpCaseSelectionConfig",
    "build_cvrp_case_manifest_from_csv",
    "build_cvrp_case_manifest_from_rows",
    "load_cvrp_case_manifest",
    "write_cvrp_case_manifest",
]

_SCHEMA = "scion.cvrp_case_manifest.v1"
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
_REJECTION_REASONS = (
    "subset",
    "status",
    "feasible",
    "benchmark",
    "bks",
    "bks_routes",
    "missing_path",
)


@dataclass(frozen=True)
class CvrpCaseSelectionConfig:
    """Selection criteria for a fixed CVRP case manifest."""

    subsets: tuple[str, ...] | None = None
    seeds: tuple[int | str, ...] = (0,)
    require_bks: bool = True
    require_bks_routes: bool = True
    require_benchmark_feasible: bool = True
    max_cases_total: int | None = None
    max_cases_per_subset: int | None = None
    source_label: str = "cvrp_result_csv"

    def __post_init__(self) -> None:
        object.__setattr__(self, "subsets", _normalize_optional_tuple(self.subsets))
        object.__setattr__(self, "seeds", _normalize_tuple(self.seeds))
        if self.max_cases_total is not None and self.max_cases_total <= 0:
            raise ValueError("max_cases_total must be positive when provided")
        if self.max_cases_per_subset is not None and self.max_cases_per_subset <= 0:
            raise ValueError("max_cases_per_subset must be positive when provided")
        if not str(self.source_label).strip():
            raise ValueError("source_label must be non-empty")


@dataclass(frozen=True)
class CvrpCaseEntry:
    """One unique selected CVRP case."""

    case_id: str
    source_path: str
    subset: str | None = None
    dimension: int | None = None
    bks: float | None = None
    bks_routes: int | None = None

    def to_payload(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "source_path": self.source_path,
            "subset": self.subset,
            "dimension": self.dimension,
            "bks": self.bks,
            "bks_routes": self.bks_routes,
        }


@dataclass(frozen=True)
class CvrpCaseManifest:
    """Deterministic CVRP case manifest payload."""

    schema: str
    problem_id: str
    cases: tuple[CvrpCaseEntry, ...]
    config: dict[str, object]
    metadata: dict[str, object]

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "problem_id": self.problem_id,
            "config": dict(self.config),
            "metadata": dict(self.metadata),
            "cases": [case.to_payload() for case in self.cases],
        }


def build_cvrp_case_manifest_from_rows(
    rows: object,
    *,
    config: CvrpCaseSelectionConfig,
    source_path: str | Path | None = None,
    problem_id: str = "cvrp",
) -> CvrpCaseManifest:
    """Build a fixed CVRP case manifest from typed result rows."""

    source_rows = tuple(rows)
    rejection_counts = {reason: 0 for reason in _REJECTION_REASONS}
    rejected_rows = 0
    eligible_rows: list[CvrpCsvResultRow] = []

    for row in source_rows:
        reasons = _rejection_reasons(row, config)
        if reasons:
            rejected_rows += 1
            for reason in reasons:
                rejection_counts[reason] += 1
        else:
            eligible_rows.append(row)

    eligible_cases = _unique_case_entries(eligible_rows, config)
    selected_cases = _select_cases(eligible_cases, config)
    _validate_selected_cases(selected_cases)

    config_payload = _config_payload(config)
    source_path_text = None if source_path is None else str(source_path)
    metadata = {
        "source_label": config.source_label,
        "source_path": source_path_text,
        "subset_filters": config_payload["subsets"],
        "seed_list": config_payload["seeds"],
        "n_input_rows": len(source_rows),
        "n_eligible_rows": len(eligible_rows),
        "n_eligible_cases": len(eligible_cases),
        "n_selected_cases": len(selected_cases),
        "n_rejected_rows": rejected_rows,
        "rejection_counts_by_reason": rejection_counts,
    }
    return CvrpCaseManifest(
        schema=_SCHEMA,
        problem_id=problem_id,
        cases=selected_cases,
        config=config_payload,
        metadata=metadata,
    )


def build_cvrp_case_manifest_from_csv(
    csv_path: str | Path,
    *,
    config: CvrpCaseSelectionConfig,
    problem_id: str = "cvrp",
) -> CvrpCaseManifest:
    """Load a CVRP result CSV artifact and build a fixed case manifest."""

    rows = load_cvrp_result_rows(csv_path)
    return build_cvrp_case_manifest_from_rows(
        rows,
        config=config,
        source_path=csv_path,
        problem_id=problem_id,
    )


def write_cvrp_case_manifest(
    manifest: CvrpCaseManifest,
    output_path: str | Path,
) -> Path:
    """Write a stable JSON case manifest and return its path."""

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(manifest.to_payload(), handle, indent=2, sort_keys=True)
        handle.write("\n")
    return path


def load_cvrp_case_manifest(path: str | Path) -> CvrpCaseManifest:
    """Load a fixed CVRP case manifest JSON artifact."""

    manifest_path = Path(path)
    with manifest_path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("CVRP case manifest must be a JSON object")

    cases_payload = payload.get("cases")
    if not isinstance(cases_payload, list):
        raise ValueError("CVRP case manifest must contain a cases list")

    cases = tuple(_case_entry_from_payload(item) for item in cases_payload)
    config = payload.get("config") or {}
    metadata = payload.get("metadata") or {}
    if not isinstance(config, dict):
        raise ValueError("CVRP case manifest config must be an object")
    if not isinstance(metadata, dict):
        raise ValueError("CVRP case manifest metadata must be an object")

    return CvrpCaseManifest(
        schema=str(payload.get("schema", "")),
        problem_id=str(payload.get("problem_id", "")),
        cases=cases,
        config=dict(config),
        metadata=dict(metadata),
    )


def _rejection_reasons(
    row: CvrpCsvResultRow,
    config: CvrpCaseSelectionConfig,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if config.subsets is not None and row.subset not in config.subsets:
        reasons.append("subset")
    if str(row.status).strip().lower() not in _OK_STATUSES:
        reasons.append("status")
    if row.feasible is not True:
        reasons.append("feasible")
    if config.require_benchmark_feasible and row.benchmark_feasible is not True:
        reasons.append("benchmark")
    if config.require_bks and row.bks is None:
        reasons.append("bks")
    if config.require_bks_routes and row.bks_routes is None:
        reasons.append("bks_routes")
    if _source_path(row) is None:
        reasons.append("missing_path")
    return tuple(reasons)


def _unique_case_entries(
    rows: tuple[CvrpCsvResultRow, ...] | list[CvrpCsvResultRow],
    config: CvrpCaseSelectionConfig,
) -> tuple[CvrpCaseEntry, ...]:
    entries_by_case: dict[str, CvrpCaseEntry] = {}
    for row in sorted(rows, key=lambda item: _row_sort_key(item, config)):
        if row.case_id not in entries_by_case:
            entries_by_case[row.case_id] = _entry_from_row(row)
    return tuple(
        sorted(entries_by_case.values(), key=lambda item: _entry_sort_key(item, config))
    )


def _select_cases(
    entries: tuple[CvrpCaseEntry, ...],
    config: CvrpCaseSelectionConfig,
) -> tuple[CvrpCaseEntry, ...]:
    per_subset_counts: dict[str, int] = {}
    selected: list[CvrpCaseEntry] = []
    for entry in entries:
        subset_key = entry.subset or ""
        count = per_subset_counts.get(subset_key, 0)
        if config.max_cases_per_subset is not None and count >= config.max_cases_per_subset:
            continue
        selected.append(entry)
        per_subset_counts[subset_key] = count + 1
        if config.max_cases_total is not None and len(selected) >= config.max_cases_total:
            break
    return tuple(selected)


def _entry_from_row(row: CvrpCsvResultRow) -> CvrpCaseEntry:
    source_path = _source_path(row)
    if source_path is None:
        raise ValueError(f"selected case {row.case_id!r} has no source_path/path")
    return CvrpCaseEntry(
        case_id=row.case_id,
        source_path=source_path,
        subset=row.subset,
        dimension=row.dimension,
        bks=row.bks,
        bks_routes=row.bks_routes,
    )


def _case_entry_from_payload(payload: object) -> CvrpCaseEntry:
    if not isinstance(payload, dict):
        raise ValueError("CVRP case manifest case entries must be objects")
    return CvrpCaseEntry(
        case_id=str(payload.get("case_id", "")),
        source_path=str(payload.get("source_path", "")),
        subset=_optional_payload_text(payload.get("subset")),
        dimension=_optional_payload_int(payload.get("dimension")),
        bks=_optional_payload_float(payload.get("bks")),
        bks_routes=_optional_payload_int(payload.get("bks_routes")),
    )


def _optional_payload_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_payload_int(value: object) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    text = str(value).strip()
    if not text:
        return None
    number = float(text)
    if not number.is_integer():
        raise ValueError(f"manifest integer field has non-integer value: {value!r}")
    return int(number)


def _optional_payload_float(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    return float(text)


def _validate_selected_cases(entries: tuple[CvrpCaseEntry, ...]) -> None:
    for entry in entries:
        if not entry.source_path:
            raise ValueError(f"selected case {entry.case_id!r} has no source_path/path")


def _source_path(row: CvrpCsvResultRow) -> str | None:
    value = row.source_path or row.path
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _row_sort_key(
    row: CvrpCsvResultRow,
    config: CvrpCaseSelectionConfig,
) -> tuple[tuple[int, str], str, str, str]:
    return (
        _subset_sort_key(row.subset, config),
        row.case_id,
        _source_path(row) or "",
        _seed_sort_key(row.seed),
    )


def _entry_sort_key(
    entry: CvrpCaseEntry,
    config: CvrpCaseSelectionConfig,
) -> tuple[tuple[int, str], str, str]:
    return (
        _subset_sort_key(entry.subset, config),
        entry.case_id,
        entry.source_path,
    )


def _subset_sort_key(
    subset: str | None,
    config: CvrpCaseSelectionConfig,
) -> tuple[int, str]:
    subset_text = "" if subset is None else subset
    if config.subsets is None:
        return (0, subset_text)
    try:
        return (config.subsets.index(subset_text), subset_text)
    except ValueError:
        return (len(config.subsets), subset_text)


def _seed_sort_key(seed: int | str | None) -> str:
    if seed is None:
        return ""
    return str(seed)


def _config_payload(config: CvrpCaseSelectionConfig) -> dict[str, object]:
    return {
        "subsets": None if config.subsets is None else list(config.subsets),
        "seeds": list(config.seeds),
        "require_bks": config.require_bks,
        "require_bks_routes": config.require_bks_routes,
        "require_benchmark_feasible": config.require_benchmark_feasible,
        "max_cases_total": config.max_cases_total,
        "max_cases_per_subset": config.max_cases_per_subset,
        "source_label": config.source_label,
    }


def _normalize_optional_tuple(value: object) -> tuple[str, ...] | None:
    if value is None:
        return None
    normalized = tuple(item for item in _normalize_string_items(value) if item)
    return normalized or None


def _normalize_tuple(value: object) -> tuple[int | str, ...]:
    if value is None:
        return tuple()
    if isinstance(value, str):
        return (value,)
    try:
        return tuple(value)
    except TypeError:
        return (value,)


def _normalize_string_items(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value.strip(),)
    try:
        return tuple(str(item).strip() for item in value)
    except TypeError:
        return (str(value).strip(),)
