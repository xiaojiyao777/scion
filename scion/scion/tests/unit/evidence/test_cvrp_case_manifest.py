from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from scion.evidence.cvrp_baseline_import import CvrpCsvResultRow
from scion.evidence.cvrp_case_manifest import (
    CvrpCaseSelectionConfig,
    build_cvrp_case_manifest_from_csv,
    build_cvrp_case_manifest_from_rows,
    write_cvrp_case_manifest,
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


def _row(**overrides: object) -> CvrpCsvResultRow:
    values = {
        "case_id": "A-n32-k5",
        "subset": "A",
        "source_path": "vrp/cvrplib/A/A-n32-k5.vrp",
        "dimension": 32,
        "bks": 784.0,
        "bks_routes": 5,
        "cost": 800.0,
        "gap_pct": 2.0,
        "routes": 5,
        "route_gap": 0,
        "iterations": 100,
        "elapsed_ms": 1000.0,
        "time_limit_s": 30.0,
        "seed": 0,
        "feasible": True,
        "benchmark_feasible": True,
        "mode": "baseline",
        "status": "ok",
        "error": None,
    }
    values.update(overrides)
    return CvrpCsvResultRow(**values)


def _csv_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "instance": "A-n32-k5",
        "subset": "A",
        "path": "vrp/cvrplib/A/A-n32-k5.vrp",
        "dimension": "32",
        "bks": "784",
        "bks_routes": "5",
        "cost": "800",
        "gap_pct": "2.0",
        "routes": "5",
        "route_gap": "0",
        "iterations": "100",
        "time": "1.0",
        "time_limit": "30",
        "seed": "0",
        "feasible": "true",
        "benchmark_feasible": "true",
        "mode": "baseline",
        "status": "ok",
        "error": "",
        "wall_time": "1.0",
    }
    row.update(overrides)
    return row


def _write_result_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=_RESULT_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def test_filters_by_subset_and_comparability_requirements() -> None:
    config = CvrpCaseSelectionConfig(
        subsets=("A", "B"),
        require_bks=True,
        require_bks_routes=True,
        require_benchmark_feasible=True,
    )
    manifest = build_cvrp_case_manifest_from_rows(
        [
            _row(case_id="B-case", subset="B", source_path="opaque/B-case.vrp"),
            _row(case_id="A-case", subset="A", source_path="opaque/A-case.vrp"),
            _row(case_id="X-case", subset="X", source_path="opaque/X-case.vrp"),
            _row(case_id="A-no-bks", subset="A", source_path="opaque/A-no-bks.vrp", bks=None),
            _row(
                case_id="A-no-routes",
                subset="A",
                source_path="opaque/A-no-routes.vrp",
                bks_routes=None,
            ),
            _row(
                case_id="A-benchmark-bad",
                subset="A",
                source_path="opaque/A-benchmark-bad.vrp",
                benchmark_feasible=False,
            ),
        ],
        config=config,
        source_path="results.csv",
    )

    assert [case.case_id for case in manifest.cases] == ["A-case", "B-case"]
    assert [case.source_path for case in manifest.cases] == [
        "opaque/A-case.vrp",
        "opaque/B-case.vrp",
    ]
    assert manifest.metadata["n_eligible_rows"] == 2
    assert manifest.metadata["n_selected_cases"] == 2
    assert manifest.metadata["rejection_counts_by_reason"]["subset"] == 1
    assert manifest.metadata["rejection_counts_by_reason"]["bks"] == 1
    assert manifest.metadata["rejection_counts_by_reason"]["bks_routes"] == 1
    assert manifest.metadata["rejection_counts_by_reason"]["benchmark"] == 1


def test_selects_deterministically_with_per_subset_and_total_limits() -> None:
    config = CvrpCaseSelectionConfig(
        subsets=("A", "B"),
        max_cases_per_subset=2,
        max_cases_total=3,
    )

    manifest = build_cvrp_case_manifest_from_rows(
        [
            _row(case_id="B-02", subset="B", source_path="opaque/B-02.vrp"),
            _row(case_id="A-02", subset="A", source_path="opaque/A-02.vrp"),
            _row(case_id="B-01", subset="B", source_path="opaque/B-01.vrp"),
            _row(case_id="A-03", subset="A", source_path="opaque/A-03.vrp"),
            _row(case_id="A-01", subset="A", source_path="opaque/A-01.vrp"),
        ],
        config=config,
    )

    assert [case.case_id for case in manifest.cases] == ["A-01", "A-02", "B-01"]
    assert manifest.metadata["n_eligible_cases"] == 5
    assert manifest.metadata["n_selected_cases"] == 3


def test_rejection_counts_cover_all_filter_reasons() -> None:
    config = CvrpCaseSelectionConfig(subsets=("A",))
    manifest = build_cvrp_case_manifest_from_rows(
        [
            _row(case_id="selected", subset="A", source_path="opaque/selected.vrp"),
            _row(case_id="bad-subset", subset="X", source_path="opaque/bad-subset.vrp"),
            _row(case_id="bad-status", subset="A", source_path="opaque/bad-status.vrp", status="timeout"),
            _row(case_id="bad-feasible", subset="A", source_path="opaque/bad-feasible.vrp", feasible=False),
            _row(
                case_id="bad-benchmark",
                subset="A",
                source_path="opaque/bad-benchmark.vrp",
                benchmark_feasible=False,
            ),
            _row(case_id="bad-bks", subset="A", source_path="opaque/bad-bks.vrp", bks=None),
            _row(
                case_id="bad-bks-routes",
                subset="A",
                source_path="opaque/bad-bks-routes.vrp",
                bks_routes=None,
            ),
            _row(case_id="bad-path", subset="A", source_path=None),
        ],
        config=config,
    )

    counts = manifest.metadata["rejection_counts_by_reason"]
    assert manifest.metadata["n_rejected_rows"] == 7
    assert counts == {
        "subset": 1,
        "status": 1,
        "feasible": 1,
        "benchmark": 1,
        "bks": 1,
        "bks_routes": 1,
        "missing_path": 1,
    }


def test_write_cvrp_case_manifest_writes_stable_json_with_opaque_paths(
    tmp_path: Path,
) -> None:
    manifest = build_cvrp_case_manifest_from_rows(
        [_row(case_id="A-case", source_path="vrp/cvrplib/A/A-case.vrp")],
        config=CvrpCaseSelectionConfig(seeds=(0, 1)),
        source_path="baseline.csv",
    )
    output_path = tmp_path / "manifest.json"

    written_path = write_cvrp_case_manifest(manifest, output_path)

    assert written_path == output_path
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["schema"] == "scion.cvrp_case_manifest.v1"
    assert payload["metadata"]["source_path"] == "baseline.csv"
    assert payload["metadata"]["seed_list"] == [0, 1]
    assert payload["cases"] == [
        {
            "bks": 784.0,
            "bks_routes": 5,
            "case_id": "A-case",
            "dimension": 32,
            "source_path": "vrp/cvrplib/A/A-case.vrp",
            "subset": "A",
        }
    ]
    expected = json.dumps(manifest.to_payload(), indent=2, sort_keys=True) + "\n"
    assert output_path.read_text(encoding="utf-8") == expected


def test_path_field_is_not_opened(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    csv_path = tmp_path / "baseline.csv"
    manifest_path = tmp_path / "manifest.json"
    opaque_case_path = "vrp/cvrplib/A/A-n32-k5.vrp"
    _write_result_csv(csv_path, [_csv_row(path=opaque_case_path)])
    original_open = Path.open

    def guarded_open(self: Path, *args: object, **kwargs: object):
        if self not in {csv_path, manifest_path}:
            raise AssertionError(f"unexpected open of {self}")
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)

    manifest = build_cvrp_case_manifest_from_csv(
        csv_path,
        config=CvrpCaseSelectionConfig(subsets=("A",)),
    )
    write_cvrp_case_manifest(manifest, manifest_path)

    assert manifest.cases[0].source_path == opaque_case_path


def test_build_from_rows_and_csv_produce_equivalent_selected_cases(
    tmp_path: Path,
) -> None:
    csv_path = tmp_path / "baseline.csv"
    _write_result_csv(
        csv_path,
        [
            _csv_row(instance="B-case", subset="B", path="opaque/B-case.vrp"),
            _csv_row(instance="A-case", subset="A", path="opaque/A-case.vrp"),
            _csv_row(instance="X-case", subset="X", path="opaque/X-case.vrp"),
        ],
    )
    config = CvrpCaseSelectionConfig(subsets=("A", "B"), seeds=(0, 1))
    rows = (
        _row(case_id="B-case", subset="B", source_path="opaque/B-case.vrp"),
        _row(case_id="A-case", subset="A", source_path="opaque/A-case.vrp"),
        _row(case_id="X-case", subset="X", source_path="opaque/X-case.vrp"),
    )

    from_rows = build_cvrp_case_manifest_from_rows(rows, config=config)
    from_csv = build_cvrp_case_manifest_from_csv(csv_path, config=config)

    assert from_rows.cases == from_csv.cases
    assert from_rows.metadata["n_selected_cases"] == from_csv.metadata["n_selected_cases"]
