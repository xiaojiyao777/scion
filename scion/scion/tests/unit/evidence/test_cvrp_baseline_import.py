from __future__ import annotations

import csv
from pathlib import Path

import pytest

from scion.evidence import (
    FinalQualityConfig,
    build_final_quality_package,
)
from scion.evidence.cvrp_baseline_import import (
    build_cvrp_quality_records,
    load_cvrp_quality_records,
    load_cvrp_result_rows,
)


_RESULT_FIELDS = [
    "instance",
    "subset",
    "path",
    "dimension",
    "bks",
    "bks_routes",
    "cost",
    "gap_pct",
    "routes",
    "route_gap",
    "iterations",
    "time",
    "time_limit",
    "seed",
    "feasible",
    "benchmark_feasible",
    "mode",
    "status",
    "error",
    "wall_time",
]


def _config(**overrides: object) -> FinalQualityConfig:
    values = {
        "problem_id": "cvrp",
        "campaign_id": "importer-smoke",
        "baseline_label": "baseline",
        "candidate_label": "candidate",
        "primary_metric": "cost",
    }
    values.update(overrides)
    return FinalQualityConfig(**values)


def _result_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "instance": "A-n32-k5",
        "subset": "A",
        "path": "vrp/cvrplib/A/A-n32-k5.vrp",
        "dimension": "32",
        "bks": "784",
        "bks_routes": "5",
        "cost": "800",
        "gap_pct": "2.0408163265",
        "routes": "5",
        "route_gap": "0",
        "iterations": "100",
        "time": "1.25",
        "time_limit": "30",
        "seed": "0",
        "feasible": "true",
        "benchmark_feasible": "true",
        "mode": "baseline",
        "status": "ok",
        "error": "",
        "wall_time": "1.5",
    }
    row.update(overrides)
    return row


def _write_result_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=_RESULT_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def test_single_csv_self_comparison_maps_key_fields_and_keeps_path_opaque(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    csv_path = tmp_path / "baseline.csv"
    source_path = "vrp/cvrplib/A/A-n32-k5.vrp"
    _write_result_csv(csv_path, [_result_row(path=source_path)])

    original_open = Path.open

    def guarded_open(self: Path, *args: object, **kwargs: object):
        if self != csv_path:
            raise AssertionError(f"unexpected open of {self}")
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)

    rows = load_cvrp_result_rows(csv_path)
    records = build_cvrp_quality_records(rows)

    assert rows[0].source_path == source_path
    assert len(records) == 1
    record = records[0]
    assert record.case_id == "A-n32-k5"
    assert record.subset == "A"
    assert record.seed == 0
    assert record.baseline_status == "ok"
    assert record.candidate_status == "ok"
    assert record.comparison == "equal"
    assert record.baseline_objective == 800.0
    assert record.candidate_objective == 800.0
    assert record.baseline_cost == 800.0
    assert record.candidate_cost == 800.0
    assert record.bks == 784.0
    assert record.baseline_gap_pct == 2.0408163265
    assert record.candidate_gap_pct == 2.0408163265
    assert record.baseline_routes == 5
    assert record.candidate_routes == 5
    assert record.bks_routes == 5
    assert record.baseline_route_gap == 0
    assert record.candidate_route_gap == 0
    assert record.baseline_feasible is True
    assert record.candidate_feasible is True
    assert record.baseline_benchmark_feasible is True
    assert record.candidate_benchmark_feasible is True
    assert record.baseline_elapsed_ms == 1500.0
    assert record.candidate_elapsed_ms == 1500.0


def test_elapsed_ms_prefers_wall_time_over_time(tmp_path: Path) -> None:
    csv_path = tmp_path / "baseline.csv"
    _write_result_csv(csv_path, [_result_row(time="999.0", wall_time="0.25")])

    rows = load_cvrp_result_rows(csv_path)
    records = build_cvrp_quality_records(rows)

    assert rows[0].elapsed_ms == 250.0
    assert records[0].baseline_elapsed_ms == 250.0
    assert records[0].candidate_elapsed_ms == 250.0


def test_missing_numeric_fields_become_none(tmp_path: Path) -> None:
    csv_path = tmp_path / "missing.csv"
    _write_result_csv(
        csv_path,
        [
            _result_row(
                dimension="",
                bks="",
                bks_routes="",
                cost="",
                gap_pct="",
                routes="",
                route_gap="",
                iterations="",
                time="",
                time_limit="",
                wall_time="",
            )
        ],
    )

    rows = load_cvrp_result_rows(csv_path)
    records = build_cvrp_quality_records(rows)

    row = rows[0]
    assert row.dimension is None
    assert row.bks is None
    assert row.bks_routes is None
    assert row.cost is None
    assert row.gap_pct is None
    assert row.routes is None
    assert row.route_gap is None
    assert row.iterations is None
    assert row.elapsed_ms is None
    assert row.time_limit_s is None

    record = records[0]
    assert record.baseline_objective is None
    assert record.candidate_objective is None
    assert record.baseline_elapsed_ms is None
    assert record.candidate_elapsed_ms is None


def test_missing_bks_routes_does_not_mark_benchmark_comparable_true(
    tmp_path: Path,
) -> None:
    csv_path = tmp_path / "baseline.csv"
    _write_result_csv(
        csv_path,
        [_result_row(bks_routes="", benchmark_feasible="true")],
    )

    records = load_cvrp_quality_records(csv_path)
    package = build_final_quality_package(records, _config())

    row = package.per_case_quality[0]
    assert row["baseline_benchmark_feasible"] is None
    assert row["candidate_benchmark_feasible"] is None
    assert package.final_quality["n_with_bks_routes"] == 0
    assert package.final_quality["n_benchmark_incomparable"] == 1
    assert package.final_quality["baseline_benchmark_feasible"] is None
    assert package.final_quality["candidate_benchmark_feasible"] is None


def test_paired_rows_align_by_case_and_seed_and_final_quality_computes_result(
    tmp_path: Path,
) -> None:
    baseline_csv = tmp_path / "baseline.csv"
    candidate_csv = tmp_path / "candidate.csv"
    _write_result_csv(
        baseline_csv,
        [
            _result_row(instance="case-worse", seed="7", cost="100"),
            _result_row(instance="case-better", seed="7", cost="100"),
        ],
    )
    _write_result_csv(
        candidate_csv,
        [
            _result_row(instance="case-better", seed="7", cost="90"),
            _result_row(instance="case-worse", seed="7", cost="110"),
        ],
    )

    records = load_cvrp_quality_records(baseline_csv, candidate_csv)
    package = build_final_quality_package(records, _config())

    assert [record.case_id for record in records] == ["case-worse", "case-better"]
    assert [record.comparison for record in records] == [None, None]
    comparisons = {
        row["case_id"]: row["comparison"] for row in package.per_case_quality
    }
    assert comparisons == {
        "case-worse": "worse",
        "case-better": "better",
    }
    assert package.final_quality["better_vs_baseline"] == 1
    assert package.final_quality["worse_vs_baseline"] == 1
    assert package.final_quality["equal_vs_baseline"] == 0


def test_missing_candidate_row_becomes_candidate_error_not_comparable(
    tmp_path: Path,
) -> None:
    baseline_csv = tmp_path / "baseline.csv"
    candidate_csv = tmp_path / "candidate.csv"
    _write_result_csv(
        baseline_csv,
        [
            _result_row(instance="case-present", seed="0", cost="100"),
            _result_row(instance="case-missing", seed="0", cost="100"),
        ],
    )
    _write_result_csv(
        candidate_csv,
        [_result_row(instance="case-present", seed="0", cost="90")],
    )

    records = load_cvrp_quality_records(baseline_csv, candidate_csv)
    package = build_final_quality_package(records, _config())

    missing = next(record for record in records if record.case_id == "case-missing")
    assert missing.candidate_status == "error"
    assert missing.error_category == "missing_candidate"
    assert missing.candidate_objective is None

    per_case = {row["case_id"]: row for row in package.per_case_quality}
    assert per_case["case-missing"]["candidate_status"] == "error"
    assert per_case["case-missing"]["comparison"] == "not_comparable"
    assert per_case["case-missing"]["error_category"] == "missing_candidate"
    assert package.failure_summary["counts_by_category"]["error"] == 1
    assert package.final_quality["n_error"] == 1


def test_candidate_without_baseline_fails_closed(tmp_path: Path) -> None:
    baseline_csv = tmp_path / "baseline.csv"
    candidate_csv = tmp_path / "candidate.csv"
    _write_result_csv(baseline_csv, [_result_row(instance="case-present")])
    _write_result_csv(
        candidate_csv,
        [
            _result_row(instance="case-present"),
            _result_row(instance="case-extra"),
        ],
    )

    with pytest.raises(ValueError, match="no matching baseline"):
        load_cvrp_quality_records(baseline_csv, candidate_csv)
