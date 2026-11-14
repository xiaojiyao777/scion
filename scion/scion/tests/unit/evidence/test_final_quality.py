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
        "problem_id": "generic-problem",
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


def test_problem_extension_is_report_only_and_emitted(tmp_path: Path) -> None:
    records = [
        QualityCaseRecord(
            case_id="case-a",
            comparison="tie",
            baseline_objective=120.0,
            candidate_objective=100.0,
            problem_extension={"domain_metric": 3, "domain_flag": True},
        )
    ]
    package = build_final_quality_package(
        records,
        _config(
            problem_extension_schema="example.extension.v1",
            problem_extension_summary={"domain_metric_total": 3},
        ),
    )

    write_final_quality_package(package, tmp_path)

    final_quality = _read_json(tmp_path / "final_quality.json")
    assert final_quality["better_vs_baseline"] == 0
    assert final_quality["equal_vs_baseline"] == 1
    assert final_quality["worse_vs_baseline"] == 0
    assert final_quality["problem_extension_schema"] == "example.extension.v1"
    assert final_quality["problem_extension_summary"] == {"domain_metric_total": 3}

    per_case_rows = _read_csv(tmp_path / "per_case_quality.csv")
    row = per_case_rows[0]
    assert json.loads(row["problem_extension"]) == {
        "domain_flag": True,
        "domain_metric": 3,
    }
