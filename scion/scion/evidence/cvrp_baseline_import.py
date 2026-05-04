"""CVRP result CSV importer for final quality evidence.

The importer translates already-produced result tables into
``QualityCaseRecord`` rows. It treats source instance paths as opaque strings
and never reads CVRPLIB instance files.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

from scion.evidence.final_quality import QualityCaseRecord


__all__ = [
    "CvrpCsvResultRow",
    "build_cvrp_quality_records",
    "load_cvrp_quality_records",
    "load_cvrp_result_rows",
]

_MISSING_VALUES = {"", "na", "n/a", "nan", "none", "null"}
_VALID_STATUSES = {
    "ok",
    "success",
    "succeeded",
    "complete",
    "completed",
    "valid",
    "feasible",
    "passed",
}


@dataclass(frozen=True)
class CvrpCsvResultRow:
    """One parsed row from a CVRP result CSV artifact."""

    case_id: str
    subset: str | None = None
    source_path: str | None = None
    dimension: int | None = None
    bks: float | None = None
    bks_routes: int | None = None
    cost: float | None = None
    gap_pct: float | None = None
    routes: int | None = None
    route_gap: int | None = None
    iterations: int | None = None
    elapsed_ms: float | None = None
    time_limit_s: float | None = None
    seed: int | str | None = None
    feasible: bool | None = None
    benchmark_feasible: bool | None = None
    mode: str | None = None
    status: str = "ok"
    error: str | None = None

    @classmethod
    def from_csv_row(
        cls,
        row: Mapping[str, str | None],
        *,
        row_number: int | None = None,
    ) -> "CvrpCsvResultRow":
        """Parse one DictReader row into typed fields."""

        case_id = _required_text(row, "instance", row_number=row_number)
        feasible = _parse_bool(row.get("feasible"), field_name="feasible", row_number=row_number)
        status = _parse_status(row.get("status"), feasible=feasible)
        return cls(
            case_id=case_id,
            subset=_optional_text(row.get("subset")),
            source_path=_optional_text(row.get("path")),
            dimension=_parse_int(
                row.get("dimension"),
                field_name="dimension",
                row_number=row_number,
            ),
            bks=_parse_float(row.get("bks"), field_name="bks", row_number=row_number),
            bks_routes=_parse_int(
                row.get("bks_routes"),
                field_name="bks_routes",
                row_number=row_number,
            ),
            cost=_parse_float(row.get("cost"), field_name="cost", row_number=row_number),
            gap_pct=_parse_float(
                row.get("gap_pct"),
                field_name="gap_pct",
                row_number=row_number,
            ),
            routes=_parse_int(row.get("routes"), field_name="routes", row_number=row_number),
            route_gap=_parse_int(
                row.get("route_gap"),
                field_name="route_gap",
                row_number=row_number,
            ),
            iterations=_parse_int(
                row.get("iterations"),
                field_name="iterations",
                row_number=row_number,
            ),
            elapsed_ms=_parse_elapsed_ms(row, row_number=row_number),
            time_limit_s=_parse_float(
                row.get("time_limit"),
                field_name="time_limit",
                row_number=row_number,
            ),
            seed=_parse_seed(row.get("seed"), row_number=row_number),
            feasible=feasible,
            benchmark_feasible=_parse_bool(
                row.get("benchmark_feasible"),
                field_name="benchmark_feasible",
                row_number=row_number,
            ),
            mode=_optional_text(row.get("mode")),
            status=status,
            error=_optional_text(row.get("error")),
        )

    @property
    def key(self) -> tuple[str, int | str | None]:
        """Alignment key used for baseline-vs-candidate pairing."""

        return (self.case_id, _normalized_seed_key(self.seed))

    @property
    def instance(self) -> str:
        """Original CSV instance identifier."""

        return self.case_id

    @property
    def path(self) -> str | None:
        """Opaque source path string from the CSV artifact."""

        return self.source_path


def load_cvrp_result_rows(csv_path: str | Path) -> tuple[CvrpCsvResultRow, ...]:
    """Load typed CVRP result rows from a CSV artifact."""

    path = Path(csv_path)
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return tuple(
            CvrpCsvResultRow.from_csv_row(row, row_number=index)
            for index, row in enumerate(reader, start=2)
        )


def build_cvrp_quality_records(
    baseline_rows: Iterable[CvrpCsvResultRow],
    candidate_rows: Iterable[CvrpCsvResultRow] | None = None,
) -> tuple[QualityCaseRecord, ...]:
    """Build final-quality records from parsed baseline/candidate CVRP rows."""

    baselines = tuple(baseline_rows)
    if candidate_rows is None:
        return tuple(
            _quality_record(
                baseline=baseline,
                candidate=baseline,
                comparison="equal" if _is_valid_self_row(baseline) else None,
            )
            for baseline in baselines
        )

    baseline_by_key = _index_rows(baselines, side="baseline")
    candidates = tuple(candidate_rows)
    candidate_by_key = _index_rows(candidates, side="candidate")

    extra_candidate_keys = tuple(
        key for key in candidate_by_key if key not in baseline_by_key
    )
    if extra_candidate_keys:
        formatted = ", ".join(_format_key(key) for key in extra_candidate_keys)
        raise ValueError(f"candidate row has no matching baseline row for {formatted}")

    records: list[QualityCaseRecord] = []
    for baseline in baselines:
        candidate = candidate_by_key.get(baseline.key)
        if candidate is None:
            records.append(_missing_candidate_record(baseline))
        else:
            records.append(_quality_record(baseline=baseline, candidate=candidate))
    return tuple(records)


def load_cvrp_quality_records(
    baseline_csv: str | Path,
    candidate_csv: str | Path | None = None,
) -> tuple[QualityCaseRecord, ...]:
    """Load CVRP CSV artifact(s) and translate them into final-quality records."""

    baseline_rows = load_cvrp_result_rows(baseline_csv)
    candidate_rows = (
        None if candidate_csv is None else load_cvrp_result_rows(candidate_csv)
    )
    return build_cvrp_quality_records(baseline_rows, candidate_rows)


def _quality_record(
    *,
    baseline: CvrpCsvResultRow,
    candidate: CvrpCsvResultRow,
    comparison: str | None = None,
) -> QualityCaseRecord:
    return QualityCaseRecord(
        case_id=baseline.case_id,
        subset=baseline.subset,
        seed=baseline.seed,
        baseline_status=baseline.status,
        candidate_status=candidate.status,
        comparison=comparison,
        decisive_metric="cost",
        baseline_objective=baseline.cost,
        candidate_objective=candidate.cost,
        baseline_elapsed_ms=baseline.elapsed_ms,
        candidate_elapsed_ms=candidate.elapsed_ms,
        error_category=_merged_error(baseline.error, candidate.error),
        baseline_cost=baseline.cost,
        candidate_cost=candidate.cost,
        bks=baseline.bks if baseline.bks is not None else candidate.bks,
        baseline_gap_pct=baseline.gap_pct,
        candidate_gap_pct=candidate.gap_pct,
        baseline_routes=baseline.routes,
        candidate_routes=candidate.routes,
        bks_routes=baseline.bks_routes
        if baseline.bks_routes is not None
        else candidate.bks_routes,
        baseline_route_gap=baseline.route_gap,
        candidate_route_gap=candidate.route_gap,
        baseline_feasible=baseline.feasible,
        candidate_feasible=candidate.feasible,
        baseline_benchmark_feasible=baseline.benchmark_feasible,
        candidate_benchmark_feasible=candidate.benchmark_feasible,
    )


def _missing_candidate_record(baseline: CvrpCsvResultRow) -> QualityCaseRecord:
    return QualityCaseRecord(
        case_id=baseline.case_id,
        subset=baseline.subset,
        seed=baseline.seed,
        baseline_status=baseline.status,
        candidate_status="error",
        comparison=None,
        decisive_metric="cost",
        baseline_objective=baseline.cost,
        candidate_objective=None,
        baseline_elapsed_ms=baseline.elapsed_ms,
        candidate_elapsed_ms=None,
        error_category="missing_candidate",
        baseline_cost=baseline.cost,
        candidate_cost=None,
        bks=baseline.bks,
        baseline_gap_pct=baseline.gap_pct,
        candidate_gap_pct=None,
        baseline_routes=baseline.routes,
        candidate_routes=None,
        bks_routes=baseline.bks_routes,
        baseline_route_gap=baseline.route_gap,
        candidate_route_gap=None,
        baseline_feasible=baseline.feasible,
        candidate_feasible=None,
        baseline_benchmark_feasible=baseline.benchmark_feasible,
        candidate_benchmark_feasible=None,
    )


def _index_rows(
    rows: Iterable[CvrpCsvResultRow],
    *,
    side: str,
) -> dict[tuple[str, int | str | None], CvrpCsvResultRow]:
    indexed: dict[tuple[str, int | str | None], CvrpCsvResultRow] = {}
    for row in rows:
        if row.key in indexed:
            raise ValueError(f"duplicate {side} row for {_format_key(row.key)}")
        indexed[row.key] = row
    return indexed


def _merged_error(
    baseline_error: str | None,
    candidate_error: str | None,
) -> str | None:
    if baseline_error and candidate_error and baseline_error != candidate_error:
        return f"baseline:{baseline_error};candidate:{candidate_error}"
    return candidate_error or baseline_error


def _is_valid_self_row(row: CvrpCsvResultRow) -> bool:
    return (
        row.status.strip().lower() in _VALID_STATUSES
        and row.feasible is not False
        and row.cost is not None
        and row.error is None
    )


def _normalized_seed_key(seed: int | str | None) -> int | str | None:
    if not isinstance(seed, str):
        return seed
    text = seed.strip()
    try:
        number = float(text)
    except ValueError:
        return text
    if number.is_integer():
        return int(number)
    return text


def _parse_elapsed_ms(
    row: Mapping[str, str | None],
    *,
    row_number: int | None,
) -> float | None:
    seconds = _parse_float(
        row.get("wall_time"),
        field_name="wall_time",
        row_number=row_number,
    )
    if seconds is None:
        seconds = _parse_float(row.get("time"), field_name="time", row_number=row_number)
    if seconds is None:
        return None
    return seconds * 1000.0


def _parse_seed(value: str | None, *, row_number: int | None) -> int | str | None:
    text = _optional_text(value)
    if text is None:
        return None
    try:
        number = _parse_int(text, field_name="seed", row_number=row_number)
    except ValueError:
        return text
    return number if number is not None else text


def _parse_status(value: str | None, *, feasible: bool | None) -> str:
    text = _optional_text(value)
    if text is not None:
        return text
    if feasible is False:
        return "infeasible"
    return "ok"


def _required_text(
    row: Mapping[str, str | None],
    field_name: str,
    *,
    row_number: int | None,
) -> str:
    value = _optional_text(row.get(field_name))
    if value is None:
        raise ValueError(_field_error(field_name, row_number, "is required"))
    return value


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if text.lower() in _MISSING_VALUES:
        return None
    return text


def _parse_float(
    value: str | None,
    *,
    field_name: str,
    row_number: int | None,
) -> float | None:
    text = _optional_text(value)
    if text is None:
        return None
    try:
        return float(text)
    except ValueError as exc:
        raise ValueError(_field_error(field_name, row_number, f"invalid float {text!r}")) from exc


def _parse_int(
    value: str | None,
    *,
    field_name: str,
    row_number: int | None,
) -> int | None:
    text = _optional_text(value)
    if text is None:
        return None
    try:
        number = float(text)
    except ValueError as exc:
        raise ValueError(_field_error(field_name, row_number, f"invalid int {text!r}")) from exc
    if not number.is_integer():
        raise ValueError(_field_error(field_name, row_number, f"invalid int {text!r}"))
    return int(number)


def _parse_bool(
    value: str | None,
    *,
    field_name: str,
    row_number: int | None,
) -> bool | None:
    text = _optional_text(value)
    if text is None:
        return None
    normalized = text.lower()
    if normalized in {"1", "true", "t", "yes", "y"}:
        return True
    if normalized in {"0", "false", "f", "no", "n"}:
        return False
    raise ValueError(_field_error(field_name, row_number, f"invalid bool {text!r}"))


def _format_key(key: tuple[str, int | str | None]) -> str:
    return f"(case_id={key[0]!r}, seed={key[1]!r})"


def _field_error(
    field_name: str,
    row_number: int | None,
    message: str,
) -> str:
    if row_number is None:
        return f"{field_name} {message}"
    return f"row {row_number}: {field_name} {message}"
