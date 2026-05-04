from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from scion.evidence import (
    CvrpEvidencePackageConfig,
    build_cvrp_evidence_package_from_csv,
    write_cvrp_evidence_package_from_csv,
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

_ARTIFACT_KEYS = {
    "manifest",
    "final_quality_json",
    "final_quality_csv",
    "per_case_quality_csv",
    "runtime_summary",
    "failure_summary",
}

_ARTIFACT_NAMES = {
    "evidence_manifest.json",
    "final_quality.json",
    "final_quality.csv",
    "per_case_quality.csv",
    "runtime_summary.json",
    "failure_summary.json",
}


def _config(**overrides: object) -> CvrpEvidencePackageConfig:
    values = {
        "campaign_id": "cvrp-package-smoke",
        "baseline_label": "baseline-v0",
        "candidate_label": "candidate-v1",
    }
    values.update(overrides)
    return CvrpEvidencePackageConfig(**values)


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


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_baseline_only_csv_writes_all_six_files_and_equal_self_comparison(
    tmp_path: Path,
) -> None:
    baseline_csv = tmp_path / "baseline.csv"
    output_dir = tmp_path / "evidence"
    _write_result_csv(
        baseline_csv,
        [
            _result_row(instance="case-a", cost="800"),
            _result_row(instance="case-b", cost="805"),
        ],
    )

    result = write_cvrp_evidence_package_from_csv(
        baseline_csv,
        config=_config(output_dir=output_dir),
    )

    assert set(result.artifacts) == _ARTIFACT_KEYS
    assert {path.name for path in result.artifacts.values()} == _ARTIFACT_NAMES
    assert all(path.exists() for path in result.artifacts.values())
    assert result.package.final_quality["equal_vs_baseline"] == 2
    assert result.package.final_quality["better_vs_baseline"] == 0
    assert result.package.final_quality["worse_vs_baseline"] == 0

    final_quality = _read_json(output_dir / "final_quality.json")
    assert final_quality["equal_vs_baseline"] == 2
    assert final_quality["n_cases"] == 2

    per_case_rows = _read_csv(output_dir / "per_case_quality.csv")
    assert [row["comparison"] for row in per_case_rows] == ["equal", "equal"]


def test_paired_csv_writes_better_and_worse_counts(tmp_path: Path) -> None:
    baseline_csv = tmp_path / "baseline.csv"
    candidate_csv = tmp_path / "candidate.csv"
    output_dir = tmp_path / "evidence"
    _write_result_csv(
        baseline_csv,
        [
            _result_row(instance="case-better", cost="100", wall_time="1.0"),
            _result_row(instance="case-worse", cost="100", wall_time="1.0"),
        ],
    )
    _write_result_csv(
        candidate_csv,
        [
            _result_row(instance="case-better", cost="90", wall_time="1.1"),
            _result_row(instance="case-worse", cost="110", wall_time="0.9"),
        ],
    )

    result = write_cvrp_evidence_package_from_csv(
        baseline_csv,
        candidate_csv,
        config=_config(output_dir=output_dir),
    )

    assert result.package.final_quality["better_vs_baseline"] == 1
    assert result.package.final_quality["worse_vs_baseline"] == 1
    assert result.package.final_quality["equal_vs_baseline"] == 0

    final_quality = _read_json(output_dir / "final_quality.json")
    assert final_quality["better_vs_baseline"] == 1
    assert final_quality["worse_vs_baseline"] == 1


def test_output_artifact_refs_are_returned_with_stable_keys(tmp_path: Path) -> None:
    baseline_csv = tmp_path / "baseline.csv"
    output_dir = tmp_path / "evidence"
    _write_result_csv(baseline_csv, [_result_row()])

    result = write_cvrp_evidence_package_from_csv(
        baseline_csv,
        config=_config(),
        output_dir=output_dir,
    )

    assert set(result.artifacts) == _ARTIFACT_KEYS
    assert result.artifacts["manifest"] == output_dir / "evidence_manifest.json"
    assert result.artifacts["final_quality_json"] == output_dir / "final_quality.json"
    assert result.artifacts["final_quality_csv"] == output_dir / "final_quality.csv"
    assert result.artifacts["per_case_quality_csv"] == output_dir / "per_case_quality.csv"
    assert result.artifacts["runtime_summary"] == output_dir / "runtime_summary.json"
    assert result.artifacts["failure_summary"] == output_dir / "failure_summary.json"


def test_opaque_csv_path_field_is_not_opened(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    baseline_csv = tmp_path / "baseline.csv"
    candidate_csv = tmp_path / "candidate.csv"
    output_dir = tmp_path / "evidence"
    opaque_path = tmp_path / "must-not-open.vrp"
    _write_result_csv(
        baseline_csv,
        [_result_row(instance="case-a", path=str(opaque_path), cost="100")],
    )
    _write_result_csv(
        candidate_csv,
        [_result_row(instance="case-a", path=str(opaque_path), cost="99")],
    )

    original_open = Path.open
    allowed_inputs = {baseline_csv, candidate_csv}

    def guarded_open(self: Path, *args: object, **kwargs: object):
        if self in allowed_inputs or self.parent == output_dir:
            return original_open(self, *args, **kwargs)
        raise AssertionError(f"unexpected open of {self}")

    monkeypatch.setattr(Path, "open", guarded_open)

    result = write_cvrp_evidence_package_from_csv(
        baseline_csv,
        candidate_csv,
        config=_config(output_dir=output_dir),
    )

    assert result.package.final_quality["better_vs_baseline"] == 1


def test_runtime_threshold_and_labels_propagate_to_outputs(tmp_path: Path) -> None:
    baseline_csv = tmp_path / "baseline.csv"
    candidate_csv = tmp_path / "candidate.csv"
    output_dir = tmp_path / "evidence"
    _write_result_csv(
        baseline_csv,
        [_result_row(instance="case-a", cost="100", wall_time="0.1")],
    )
    _write_result_csv(
        candidate_csv,
        [_result_row(instance="case-a", cost="99", wall_time="0.31")],
    )

    result = write_cvrp_evidence_package_from_csv(
        baseline_csv,
        candidate_csv,
        config=_config(
            campaign_id="campaign-final",
            baseline_label="baseline-snapshot",
            candidate_label="champion-v7",
            runtime_regression_threshold=3.0,
            objective_tolerance=0.01,
            output_dir=output_dir,
        ),
    )

    assert result.package.final_quality["campaign_id"] == "campaign-final"
    assert result.package.final_quality["baseline_label"] == "baseline-snapshot"
    assert result.package.final_quality["candidate_label"] == "champion-v7"
    assert result.package.runtime_summary["runtime_regression_threshold"] == 3.0
    assert result.package.runtime_summary["runtime_regressions"] == 1

    final_quality = _read_json(output_dir / "final_quality.json")
    runtime_summary = _read_json(output_dir / "runtime_summary.json")
    manifest = _read_json(output_dir / "evidence_manifest.json")
    assert final_quality["campaign_id"] == "campaign-final"
    assert final_quality["baseline_label"] == "baseline-snapshot"
    assert final_quality["candidate_label"] == "champion-v7"
    assert runtime_summary["runtime_regression_threshold"] == 3.0
    assert runtime_summary["runtime_regressions"] == 1
    assert manifest["problem_id"] == "cvrp"
    assert manifest["campaign_id"] == "campaign-final"
    assert manifest["baseline_label"] == "baseline-snapshot"
    assert manifest["candidate_label"] == "champion-v7"


def test_missing_bks_routes_remains_unknown_after_full_builder_path(
    tmp_path: Path,
) -> None:
    baseline_csv = tmp_path / "baseline.csv"
    output_dir = tmp_path / "evidence"
    _write_result_csv(
        baseline_csv,
        [_result_row(bks_routes="", benchmark_feasible="true")],
    )

    result = write_cvrp_evidence_package_from_csv(
        baseline_csv,
        config=_config(output_dir=output_dir),
    )

    assert result.package.per_case_quality[0]["baseline_benchmark_feasible"] is None
    assert result.package.per_case_quality[0]["candidate_benchmark_feasible"] is None
    assert result.package.final_quality["n_with_bks_routes"] == 0
    assert result.package.final_quality["baseline_benchmark_feasible"] is None
    assert result.package.final_quality["candidate_benchmark_feasible"] is None

    final_quality = _read_json(output_dir / "final_quality.json")
    per_case_rows = _read_csv(output_dir / "per_case_quality.csv")
    assert final_quality["n_with_bks_routes"] == 0
    assert final_quality["baseline_benchmark_feasible"] is None
    assert final_quality["candidate_benchmark_feasible"] is None
    assert per_case_rows[0]["baseline_benchmark_feasible"] == ""
    assert per_case_rows[0]["candidate_benchmark_feasible"] == ""


def test_build_path_returns_in_memory_package_without_writing(tmp_path: Path) -> None:
    baseline_csv = tmp_path / "baseline.csv"
    output_dir = tmp_path / "unused-output"
    _write_result_csv(baseline_csv, [_result_row()])

    package = build_cvrp_evidence_package_from_csv(
        baseline_csv,
        config=_config(output_dir=output_dir),
    )

    assert package.final_quality["problem_id"] == "cvrp"
    assert package.final_quality["equal_vs_baseline"] == 1
    assert not output_dir.exists()
