from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import pytest

from scion.core.models import RunResult
from scion.evidence import (
    CvrpFinalEvaluationConfig,
    build_cvrp_final_evidence_package,
    evaluate_cvrp_final_quality_records,
    write_cvrp_final_evidence_package,
)
from scion.problems.cvrp.adapter import CvrpAdapter


CVRP_DIR = Path(__file__).resolve().parents[3] / "problems" / "cvrp"
TINY_5 = CVRP_DIR / "data" / "tiny_5.json"
TINY_6 = CVRP_DIR / "data" / "tiny_6.json"

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


class _Spec:
    pass


@dataclass(frozen=True)
class _FakeRun:
    raw: Mapping[str, object] | None = None
    success: bool = True
    elapsed_ms: int = 100
    exit_code: int = 0
    error_category: str | None = None
    stderr: str = ""


class _FakeRunner:
    def __init__(
        self,
        tmp_path: Path,
        responses: Mapping[tuple[str, str, int], _FakeRun],
    ) -> None:
        self._tmp_path = tmp_path
        self._responses = dict(responses)
        self.calls: list[dict[str, object]] = []

    def run_solver(
        self,
        workdir: str,
        instance_path: str,
        seed: int,
        time_limit_sec: int,
        registry_path: str,
    ) -> RunResult:
        self.calls.append(
            {
                "workdir": workdir,
                "instance_path": instance_path,
                "seed": seed,
                "time_limit_sec": time_limit_sec,
                "registry_path": registry_path,
            }
        )
        key = (workdir, instance_path, seed)
        if key not in self._responses:
            raise AssertionError(f"unexpected runner call: {key!r}")
        response = self._responses[key]
        if response.success and response.raw is not None:
            output_path = self._tmp_path / f"run_{len(self.calls)}.json"
            output_path.write_text(
                json.dumps(response.raw),
                encoding="utf-8",
            )
            return RunResult(
                success=True,
                exit_code=response.exit_code,
                stdout="",
                stderr=response.stderr,
                elapsed_ms=response.elapsed_ms,
                output_path=str(output_path),
                error_category=None,
            )
        return RunResult(
            success=response.success,
            exit_code=response.exit_code if response.exit_code else 1,
            stdout="",
            stderr=response.stderr,
            elapsed_ms=response.elapsed_ms,
            output_path=None,
            error_category=response.error_category,  # type: ignore[arg-type]
        )


def _adapter() -> CvrpAdapter:
    return CvrpAdapter(_Spec())  # type: ignore[arg-type]


def _config(tmp_path: Path, **overrides: object) -> CvrpFinalEvaluationConfig:
    values: dict[str, object] = {
        "campaign_id": "cvrp-final",
        "baseline_workspace": tmp_path / "baseline",
        "candidate_workspace": tmp_path / "candidate",
        "case_paths": [TINY_5],
        "seeds": [11],
        "time_limit_sec": 30,
        "baseline_label": "baseline-v0",
        "candidate_label": "champion-v1",
    }
    values.update(overrides)
    return CvrpFinalEvaluationConfig(**values)  # type: ignore[arg-type]


def _responses(
    config: CvrpFinalEvaluationConfig,
    *,
    case_path: Path = TINY_5,
    seed: int = 11,
    baseline: _FakeRun,
    candidate: _FakeRun,
) -> dict[tuple[str, str, int], _FakeRun]:
    return {
        (str(config.baseline_workspace), str(case_path), seed): baseline,
        (str(config.candidate_workspace), str(case_path), seed): candidate,
    }


def _raw(
    routes: list[list[int]],
    *,
    reported_distance: float = 999.0,
    fleet_violation: int = 0,
    feasible: bool = True,
) -> dict[str, object]:
    return {
        "routes": routes,
        "objective": {
            "fleet_violation": fleet_violation,
            "total_distance": reported_distance,
            "routes": len(routes),
        },
        "feasible": feasible,
    }


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_successful_evaluation_maps_recomputed_cvrp_quality_fields(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    runner = _FakeRunner(
        tmp_path,
        _responses(
            config,
            baseline=_FakeRun(raw=_raw([[1, 3], [2, 4]], reported_distance=999.0)),
            candidate=_FakeRun(raw=_raw([[1, 2], [3, 4]], reported_distance=1.0)),
        ),
    )

    records = evaluate_cvrp_final_quality_records(
        config=config,
        runner=runner,
        adapter=_adapter(),
    )

    assert len(records) == 1
    record = records[0]
    assert record.case_id == "tiny_5"
    assert record.baseline_status == "ok"
    assert record.candidate_status == "ok"
    assert record.baseline_cost == 10.0
    assert record.candidate_cost == 8.0
    assert record.baseline_objective == 10.0
    assert record.candidate_objective == 8.0
    assert record.baseline_routes == 2
    assert record.candidate_routes == 2
    assert record.bks == 8.0
    assert record.bks_routes == 2
    assert record.baseline_route_gap == 0
    assert record.candidate_route_gap == 0
    assert record.baseline_gap_pct == pytest.approx(25.0)
    assert record.candidate_gap_pct == 0.0
    assert record.baseline_feasible is True
    assert record.candidate_feasible is True
    assert record.baseline_benchmark_feasible is True
    assert record.candidate_benchmark_feasible is True
    assert record.comparison is None


def test_candidate_lower_cost_with_same_route_limit_becomes_better(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    runner = _FakeRunner(
        tmp_path,
        _responses(
            config,
            baseline=_FakeRun(raw=_raw([[1, 3], [2, 4]])),
            candidate=_FakeRun(raw=_raw([[1, 2], [3, 4]])),
        ),
    )

    package = build_cvrp_final_evidence_package(
        config=config,
        runner=runner,
        adapter=_adapter(),
    )

    assert package.final_quality["better_vs_baseline"] == 1
    assert package.final_quality["equal_vs_baseline"] == 0
    assert package.final_quality["worse_vs_baseline"] == 0
    assert package.per_case_quality[0]["comparison"] == "better"


def test_candidate_with_more_routes_than_bks_routes_cannot_report_fake_win(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path, case_paths=[TINY_6])
    runner = _FakeRunner(
        tmp_path,
        _responses(
            config,
            case_path=TINY_6,
            baseline=_FakeRun(raw=_raw([[1, 6, 2], [3, 4, 5]])),
            candidate=_FakeRun(raw=_raw([[1, 2, 3], [4, 5], [6]])),
        ),
    )

    package = build_cvrp_final_evidence_package(
        config=config,
        runner=runner,
        adapter=_adapter(),
    )

    row = package.per_case_quality[0]
    assert row["baseline_cost"] == 19.0
    assert row["candidate_cost"] == 16.0
    assert row["candidate_routes"] == 3
    assert row["bks_routes"] == 2
    assert row["candidate_benchmark_feasible"] is False
    assert row["comparison"] == "not_comparable"
    assert package.final_quality["better_vs_baseline"] == 0
    assert package.final_quality["n_benchmark_incomparable"] == 1


@pytest.mark.parametrize("category", ["timeout", "crash"])
def test_timeout_or_crash_run_becomes_not_comparable_failure(
    tmp_path: Path,
    category: str,
) -> None:
    config = _config(tmp_path)
    runner = _FakeRunner(
        tmp_path,
        _responses(
            config,
            baseline=_FakeRun(raw=_raw([[1, 2], [3, 4]])),
            candidate=_FakeRun(
                success=False,
                exit_code=124 if category == "timeout" else 2,
                elapsed_ms=30_000,
                error_category=category,
                stderr=f"{category} failure",
            ),
        ),
    )

    package = build_cvrp_final_evidence_package(
        config=config,
        runner=runner,
        adapter=_adapter(),
    )

    row = package.per_case_quality[0]
    assert row["candidate_status"] == category
    assert row["comparison"] == "not_comparable"
    assert package.failure_summary["n_failures"] == 1
    assert package.failure_summary["failures"][0]["case_id"] == "tiny_5"
    assert category in package.failure_summary["failures"][0]["failure_categories"]


def test_candidate_operator_runtime_error_becomes_not_comparable_failure(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    raw = _raw([[1, 2], [3, 4]])
    raw["runtime"] = {
        "operator_errors": 1,
        "operator_events": [
            {"operator": "bad_cvrp_op", "status": "error", "detail": "boom"}
        ],
    }
    runner = _FakeRunner(
        tmp_path,
        _responses(
            config,
            baseline=_FakeRun(raw=_raw([[1, 2], [3, 4]])),
            candidate=_FakeRun(raw=raw),
        ),
    )

    package = build_cvrp_final_evidence_package(
        config=config,
        runner=runner,
        adapter=_adapter(),
    )

    row = package.per_case_quality[0]
    assert row["candidate_status"] == "error"
    assert row["comparison"] == "not_comparable"
    assert row["error_category"] == "operator_runtime_error"
    assert package.failure_summary["n_failures"] == 1


def test_infeasible_adapter_result_becomes_not_comparable(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    runner = _FakeRunner(
        tmp_path,
        _responses(
            config,
            baseline=_FakeRun(raw=_raw([[1, 2], [3, 4]])),
            candidate=_FakeRun(raw=_raw([[1, 2, 3], [4]])),
        ),
    )

    package = build_cvrp_final_evidence_package(
        config=config,
        runner=runner,
        adapter=_adapter(),
    )

    row = package.per_case_quality[0]
    assert row["candidate_status"] == "infeasible"
    assert row["candidate_feasible"] is False
    assert row["comparison"] == "not_comparable"
    assert package.final_quality["n_infeasible"] == 1
    assert package.failure_summary["counts_by_category"]["infeasible"] == 1


def test_missing_output_becomes_error_row_not_dropped(tmp_path: Path) -> None:
    config = _config(tmp_path)
    runner = _FakeRunner(
        tmp_path,
        _responses(
            config,
            baseline=_FakeRun(raw=_raw([[1, 2], [3, 4]])),
            candidate=_FakeRun(raw=None, success=True, elapsed_ms=50),
        ),
    )

    package = build_cvrp_final_evidence_package(
        config=config,
        runner=runner,
        adapter=_adapter(),
    )

    assert package.final_quality["n_cases"] == 1
    row = package.per_case_quality[0]
    assert row["candidate_status"] == "error"
    assert row["comparison"] == "not_comparable"
    assert row["error_category"] == "missing_output"
    assert package.failure_summary["counts_by_category"]["error"] == 1


def test_write_final_evidence_writes_all_six_artifacts_and_refs(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "evidence"
    config = _config(tmp_path, output_dir=output_dir)
    runner = _FakeRunner(
        tmp_path,
        _responses(
            config,
            baseline=_FakeRun(raw=_raw([[1, 3], [2, 4]])),
            candidate=_FakeRun(raw=_raw([[1, 2], [3, 4]])),
        ),
    )

    result = write_cvrp_final_evidence_package(
        config=config,
        runner=runner,
        adapter=_adapter(),
    )

    assert set(result.artifacts) == _ARTIFACT_KEYS
    assert {path.name for path in result.artifacts.values()} == _ARTIFACT_NAMES
    assert all(path.exists() for path in result.artifacts.values())
    assert result.artifacts["manifest"] == output_dir / "evidence_manifest.json"
    assert result.artifacts["final_quality_json"] == output_dir / "final_quality.json"
    assert result.artifacts["final_quality_csv"] == output_dir / "final_quality.csv"
    assert result.artifacts["per_case_quality_csv"] == output_dir / "per_case_quality.csv"
    assert result.artifacts["runtime_summary"] == output_dir / "runtime_summary.json"
    assert result.artifacts["failure_summary"] == output_dir / "failure_summary.json"

    final_quality = _read_json(output_dir / "final_quality.json")
    assert final_quality["better_vs_baseline"] == 1
    per_case_rows = _read_csv(output_dir / "per_case_quality.csv")
    assert per_case_rows[0]["comparison"] == "better"


def test_runner_receives_same_case_seed_and_time_limit_for_both_sides(
    tmp_path: Path,
) -> None:
    config = _config(
        tmp_path,
        case_paths=[TINY_5, TINY_6],
        seeds=[11, 29],
        time_limit_sec=17,
    )
    responses: dict[tuple[str, str, int], _FakeRun] = {}
    for case_path in (TINY_5, TINY_6):
        raw = _raw([[1, 2], [3, 4]]) if case_path == TINY_5 else _raw([[1, 2, 3], [4, 5, 6]])
        for seed in (11, 29):
            responses[(str(config.baseline_workspace), str(case_path), seed)] = _FakeRun(raw=raw)
            responses[(str(config.candidate_workspace), str(case_path), seed)] = _FakeRun(raw=raw)
    runner = _FakeRunner(tmp_path, responses)

    records = evaluate_cvrp_final_quality_records(
        config=config,
        runner=runner,
        adapter=_adapter(),
    )

    assert len(records) == 4
    assert len(runner.calls) == 8
    by_case_seed: dict[tuple[str, int], set[str]] = {}
    for call in runner.calls:
        assert call["time_limit_sec"] == 17
        key = (str(call["instance_path"]), int(call["seed"]))
        by_case_seed.setdefault(key, set()).add(str(call["workdir"]))
    assert by_case_seed == {
        (str(TINY_5), 11): {str(config.baseline_workspace), str(config.candidate_workspace)},
        (str(TINY_5), 29): {str(config.baseline_workspace), str(config.candidate_workspace)},
        (str(TINY_6), 11): {str(config.baseline_workspace), str(config.candidate_workspace)},
        (str(TINY_6), 29): {str(config.baseline_workspace), str(config.candidate_workspace)},
    }
