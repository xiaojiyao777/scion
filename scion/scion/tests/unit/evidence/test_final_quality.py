from __future__ import annotations

import csv
import json
from pathlib import Path

from scion.evidence import (
    FinalQualityConfig,
    QualityCaseRecord,
    build_final_quality_package,
    write_final_quality_package,
)


def _config(**overrides: object) -> FinalQualityConfig:
    values = {
        "problem_id": "cvrp",
        "campaign_id": "camp-final",
        "baseline_label": "baseline-v0",
        "candidate_label": "champion-v4",
    }
    values.update(overrides)
    return FinalQualityConfig(**values)


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def test_writes_all_six_files_and_aggregates_win_tie_loss(tmp_path: Path) -> None:
    records = [
        QualityCaseRecord(
            case_id="win",
            subset="screen",
            seed=11,
            baseline_objective=100.0,
            candidate_objective=90.0,
            baseline_elapsed_ms=100.0,
            candidate_elapsed_ms=120.0,
        ),
        QualityCaseRecord(
            case_id="tie",
            subset="screen",
            seed=11,
            baseline_objective=100.0,
            candidate_objective=100.0,
            baseline_elapsed_ms=100.0,
            candidate_elapsed_ms=100.0,
        ),
        QualityCaseRecord(
            case_id="loss",
            subset="screen",
            seed=11,
            baseline_objective=100.0,
            candidate_objective=110.0,
            baseline_elapsed_ms=100.0,
            candidate_elapsed_ms=80.0,
        ),
    ]
    package = build_final_quality_package(records, _config())

    paths = write_final_quality_package(package, tmp_path)

    assert {path.name for path in paths.values()} == {
        "evidence_manifest.json",
        "final_quality.json",
        "final_quality.csv",
        "per_case_quality.csv",
        "runtime_summary.json",
        "failure_summary.json",
    }
    assert all(path.exists() for path in paths.values())

    final_quality = _read_json(tmp_path / "final_quality.json")
    assert final_quality["better_vs_baseline"] == 1
    assert final_quality["equal_vs_baseline"] == 1
    assert final_quality["worse_vs_baseline"] == 1
    assert final_quality["n_ok"] == 3
    assert final_quality["primary_delta_sum"] == 0.0
    assert final_quality["primary_delta_median"] == 0.0

    final_quality_rows = _read_csv(tmp_path / "final_quality.csv")
    assert len(final_quality_rows) == 1
    assert final_quality_rows[0]["better_vs_baseline"] == "1"
    assert final_quality_rows[0]["equal_vs_baseline"] == "1"
    assert final_quality_rows[0]["worse_vs_baseline"] == "1"

    per_case_rows = _read_csv(tmp_path / "per_case_quality.csv")
    assert [row["comparison"] for row in per_case_rows] == [
        "better",
        "equal",
        "worse",
    ]


def test_failure_summary_preserves_timeout_crash_error_and_infeasible_rows(
    tmp_path: Path,
) -> None:
    records = [
        QualityCaseRecord(case_id="timeout", candidate_status="timeout"),
        QualityCaseRecord(case_id="crash", candidate_status="crash"),
        QualityCaseRecord(case_id="error", candidate_status="error"),
        QualityCaseRecord(case_id="infeasible", candidate_status="infeasible"),
        QualityCaseRecord(
            case_id="oom",
            comparison="better",
            error_category="oom",
        ),
    ]
    package = build_final_quality_package(records, _config())

    write_final_quality_package(package, tmp_path)

    final_quality = _read_json(tmp_path / "final_quality.json")
    assert final_quality["n_timeout"] == 1
    assert final_quality["n_error"] == 3
    assert final_quality["n_infeasible"] == 1
    assert final_quality["better_vs_baseline"] == 0
    assert final_quality["equal_vs_baseline"] == 0
    assert final_quality["worse_vs_baseline"] == 0

    failure_summary = _read_json(tmp_path / "failure_summary.json")
    assert failure_summary["counts_by_category"] == {
        "timeout": 1,
        "crash": 1,
        "error": 2,
        "infeasible": 1,
        "benchmark_incomparable": 0,
    }
    assert [row["case_id"] for row in failure_summary["failures"]] == [
        "timeout",
        "crash",
        "error",
        "infeasible",
        "oom",
    ]

    per_case_rows = _read_csv(tmp_path / "per_case_quality.csv")
    assert {row["case_id"]: row["comparison"] for row in per_case_rows} == {
        "timeout": "not_comparable",
        "crash": "not_comparable",
        "error": "not_comparable",
        "infeasible": "not_comparable",
        "oom": "not_comparable",
    }


def test_runtime_regression_threshold_is_configurable(tmp_path: Path) -> None:
    records = [
        QualityCaseRecord(
            case_id="under-threshold",
            baseline_objective=100.0,
            candidate_objective=99.0,
            baseline_elapsed_ms=100.0,
            candidate_elapsed_ms=149.0,
        ),
        QualityCaseRecord(
            case_id="over-threshold",
            baseline_objective=100.0,
            candidate_objective=99.0,
            baseline_elapsed_ms=100.0,
            candidate_elapsed_ms=151.0,
        ),
    ]
    package = build_final_quality_package(
        records,
        _config(runtime_regression_threshold=1.5),
    )

    write_final_quality_package(package, tmp_path)

    runtime_summary = _read_json(tmp_path / "runtime_summary.json")
    assert runtime_summary["runtime_regression_threshold"] == 1.5
    assert runtime_summary["runtime_regressions"] == 1
    assert runtime_summary["runtime_ratio_median"] == 1.5

    per_case_rows = _read_csv(tmp_path / "per_case_quality.csv")
    assert {row["case_id"]: row["runtime_regression"] for row in per_case_rows} == {
        "under-threshold": "false",
        "over-threshold": "true",
    }


def test_cvrp_fields_are_report_only_and_emitted(tmp_path: Path) -> None:
    records = [
        QualityCaseRecord(
            case_id="cvrp-a",
            comparison="tie",
            baseline_cost=120.0,
            candidate_cost=100.0,
            bks=100.0,
            baseline_routes=10,
            candidate_routes=9,
            bks_routes=10,
            baseline_feasible=True,
            candidate_feasible=True,
        )
    ]
    package = build_final_quality_package(records, _config())

    write_final_quality_package(package, tmp_path)

    final_quality = _read_json(tmp_path / "final_quality.json")
    assert final_quality["better_vs_baseline"] == 0
    assert final_quality["equal_vs_baseline"] == 1
    assert final_quality["worse_vs_baseline"] == 0
    assert final_quality["n_with_bks"] == 1
    assert final_quality["n_with_bks_routes"] == 1
    assert final_quality["mean_candidate_gap_pct"] == 0.0
    assert final_quality["mean_baseline_gap_pct"] == 20.0
    assert final_quality["candidate_benchmark_feasible"] is True
    assert final_quality["baseline_benchmark_feasible"] is True

    per_case_rows = _read_csv(tmp_path / "per_case_quality.csv")
    row = per_case_rows[0]
    assert row["bks"] == "100.0"
    assert row["baseline_gap_pct"] == "20.0"
    assert row["candidate_gap_pct"] == "0.0"
    assert row["baseline_route_gap"] == "0"
    assert row["candidate_route_gap"] == "-1"
    assert row["baseline_benchmark_feasible"] == "true"
    assert row["candidate_benchmark_feasible"] == "true"


def test_missing_bks_routes_does_not_mark_benchmark_comparable_true(
    tmp_path: Path,
) -> None:
    records = [
        QualityCaseRecord(
            case_id="missing-routes",
            comparison="tie",
            baseline_cost=100.0,
            candidate_cost=99.0,
            bks=95.0,
            baseline_routes=8,
            candidate_routes=8,
            bks_routes=None,
            baseline_feasible=True,
            candidate_feasible=True,
            baseline_benchmark_feasible=True,
            candidate_benchmark_feasible=True,
        )
    ]
    package = build_final_quality_package(records, _config())

    assert package.per_case_quality[0]["baseline_benchmark_feasible"] is None
    assert package.per_case_quality[0]["candidate_benchmark_feasible"] is None

    write_final_quality_package(package, tmp_path)

    final_quality = _read_json(tmp_path / "final_quality.json")
    assert final_quality["n_with_bks"] == 1
    assert final_quality["n_with_bks_routes"] == 0
    assert final_quality["n_benchmark_incomparable"] == 1
    assert final_quality["baseline_benchmark_feasible"] is None
    assert final_quality["candidate_benchmark_feasible"] is None

    per_case_rows = _read_csv(tmp_path / "per_case_quality.csv")
    assert per_case_rows[0]["baseline_benchmark_feasible"] == ""
    assert per_case_rows[0]["candidate_benchmark_feasible"] == ""


def test_benchmark_incomparable_cvrp_row_cannot_report_fake_win() -> None:
    records = [
        QualityCaseRecord(
            case_id="more-routes",
            comparison="better",
            baseline_objective=100.0,
            candidate_objective=90.0,
            baseline_cost=100.0,
            candidate_cost=90.0,
            bks=95.0,
            baseline_routes=5,
            candidate_routes=6,
            bks_routes=5,
            baseline_feasible=True,
            candidate_feasible=True,
        )
    ]

    package = build_final_quality_package(records, _config())

    row = package.per_case_quality[0]
    assert row["candidate_benchmark_feasible"] is False
    assert row["comparison"] == "not_comparable"
    assert package.final_quality["better_vs_baseline"] == 0
    assert package.final_quality["n_benchmark_incomparable"] == 1
