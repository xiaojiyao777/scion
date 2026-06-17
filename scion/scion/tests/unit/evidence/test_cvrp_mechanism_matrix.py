from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from scion.problems.cvrp.evidence.mechanism_matrix import (
    CvrpMatrixCase,
    build_cvrp_mechanism_matrix_manifest,
    build_jobs,
    default_cvrp_mechanisms,
    load_case_entries,
    planned_result_for_job,
    summarize_solver_output_for_job,
)


TOOL_PATH = Path(__file__).resolve().parents[4] / "tools" / "cvrp_mechanism_matrix.py"


def _load_tool():
    spec = importlib.util.spec_from_file_location("cvrp_mechanism_matrix", TOOL_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _case_manifest(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "schema": "scion.cvrp_case_manifest.v1",
                "problem_id": "cvrp",
                "config": {"seeds": [11]},
                "metadata": {"stage": "screening"},
                "cases": [
                    {
                        "case_id": "A-n64-k9",
                        "source_path": "cvrplib/A/A-n64-k9.vrp",
                        "subset": "A",
                        "dimension": 64,
                        "bks": 1401.0,
                        "bks_routes": 9,
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )


def test_default_mechanisms_cover_required_cvrp_surfaces() -> None:
    mechanisms = default_cvrp_mechanisms()

    assert [mechanism.mechanism_id for mechanism in mechanisms] == [
        "canonical_alns_vns",
        "alns_only",
        "size70_two_opt_candidate",
    ]
    assert mechanisms[0].overlays == ()
    assert mechanisms[1].overlays == ("config_use_vns_false",)
    assert mechanisms[2].overlays == (
        "config_vns_threshold_70",
        "local_search_two_opt_only",
    )


def test_matrix_manifest_reserves_problem_owned_diagnostic_fields(
    tmp_path: Path,
) -> None:
    cases = (
        CvrpMatrixCase(
            case_id="A-n64-k9",
            source_path="cvrplib/A/A-n64-k9.vrp",
            case_family="A",
            case_slice="size_le_70",
            dimension=64,
            bks=1401.0,
            bks_routes=9,
        ),
    )
    mechanisms = default_cvrp_mechanisms()

    manifest = build_cvrp_mechanism_matrix_manifest(
        cases=cases,
        mechanisms=mechanisms,
        seeds=(11,),
        time_budget_sec=1,
        output_dir=tmp_path,
        repo_root="/repo",
        workspace="/repo/scion/scion/problems/cvrp",
        data_root="/repo/vrp",
        python="python",
        selected_surface="solver_design",
        dry_run=True,
    )

    assert manifest["schema_version"] == "scion.cvrp_mechanism_matrix.v1"
    assert manifest["diagnostic_policy"]["generic_decision_inputs_changed"] is False
    assert "must not enter generic DecisionFeatures" in (
        manifest["diagnostic_policy"]["decision_boundary"]
    )
    assert len(manifest["jobs"]) == 3
    job = manifest["jobs"][0]
    assert job["case"]["case_family"] == "A"
    assert job["case"]["case_slice"] == "size_le_70"
    assert "accepted_moves" in job["reserved_result_fields"]
    assert "runtime_phase_split" in job["reserved_result_fields"]


def test_planned_result_and_summary_keep_quality_and_phase_diagnostics(
    tmp_path: Path,
) -> None:
    case = CvrpMatrixCase(
        case_id="A-n64-k9",
        source_path="cvrplib/A/A-n64-k9.vrp",
        case_family="A",
        case_slice="size_le_70",
        dimension=64,
        bks=1401.0,
        bks_routes=9,
    )
    canonical, alns_only, _candidate = default_cvrp_mechanisms()
    jobs = build_jobs(
        cases=(case,),
        mechanisms=(canonical, alns_only),
        seeds=(11,),
        time_budget_sec=1,
        output_dir=tmp_path,
    )
    planned = planned_result_for_job(jobs[0])

    assert planned["status"] == "planned"
    assert planned["quality"]["bks"] == 1401.0
    assert planned["accepted_moves"]["by_phase"] == {}

    canonical_raw = _raw_solver_output(total_distance=1500.0, routes=9)
    canonical_result = summarize_solver_output_for_job(canonical_raw, job=jobs[0])
    alns_raw = _raw_solver_output(total_distance=1510.0, routes=10)
    alns_result = summarize_solver_output_for_job(
        alns_raw,
        job=jobs[1],
        reference=canonical_result,
    )

    assert canonical_result["quality"]["bks_gap_pct"] == (
        (1500.0 - 1401.0) * 100.0 / 1401.0
    )
    assert alns_result["quality"]["quality_delta_total_distance_vs_reference"] == 10.0
    assert alns_result["route_fleet_regression_flags"][
        "route_count_exceeds_bks_routes"
    ] is True
    assert alns_result["route_fleet_regression_flags"][
        "route_count_regressed_vs_reference"
    ] is True
    assert alns_result["accepted_moves"]["total"] == 7
    assert alns_result["accepted_moves"]["by_phase"] == {"alns": 5, "vns": 2}
    assert alns_result["best_update_telemetry"]["best_update_count"] == 3
    assert alns_result["phase_telemetry"]["phase_best_delta"] == {
        "alns": 4.0,
        "vns": 2.0,
    }
    assert alns_result["runtime_phase_split"]["phase_runtime_ms"] == {
        "construction": 10,
        "alns": 70,
        "vns": 20,
    }


def test_load_cases_and_cli_dry_run_write_manifest_and_results(
    tmp_path: Path,
) -> None:
    manifest_path = tmp_path / "cases.json"
    _case_manifest(manifest_path)
    output_dir = tmp_path / "matrix"
    tool = _load_tool()

    cases = load_case_entries(manifest_path, case_limit=1)
    assert cases[0].case_family == "A"
    assert cases[0].case_slice == "size_le_70"

    status = tool.main(
        [
            "--workspace",
            str(tmp_path / "workspace"),
            "--repo-root",
            str(tmp_path / "repo"),
            "--data-root",
            str(tmp_path / "vrp"),
            "--case-manifest",
            str(manifest_path),
            "--output-dir",
            str(output_dir),
            "--seed",
            "11",
            "--time-budget-sec",
            "1",
            "--dry-run",
        ]
    )

    assert status == 0
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    results = json.loads((output_dir / "results.json").read_text(encoding="utf-8"))
    assert len(manifest["jobs"]) == 3
    assert len(results["jobs"]) == 3
    assert {row["status"] for row in results["jobs"]} == {"planned"}
    assert (output_dir / "summary.csv").exists()


def _raw_solver_output(*, total_distance: float, routes: int) -> dict[str, object]:
    return {
        "objective": {
            "total_distance": total_distance,
            "fleet_violation": 0.0,
            "routes": routes,
        },
        "runtime": {
            "elapsed_s": 1.0,
            "solver_algorithm_elapsed_ms": 100,
            "solver_algorithm_total_distance": total_distance,
            "solver_algorithm_solution_routes": routes,
            "solver_algorithm_fleet_violation": 0.0,
            "solver_algorithm_accepted_moves": 7,
            "solver_algorithm_move_attempts": 11,
            "solver_algorithm_improving_moves": 4,
            "solver_algorithm_neutral_accepted_moves": 3,
            "solver_algorithm_phase_accepted_moves": {"alns": 5, "vns": 2},
            "solver_algorithm_best_delta": 4.0,
            "solver_algorithm_best_update_summary": {"best_update_count": 3},
            "solver_algorithm_best_update_trace": [
                {"phase": "alns", "total_distance": total_distance}
            ],
            "solver_algorithm_phase_move_attempts": {"alns": 8, "vns": 3},
            "solver_algorithm_phase_delta_sum": {"alns": 7.0, "vns": 2.0},
            "solver_algorithm_phase_best_delta": {"alns": 4.0, "vns": 2.0},
            "solver_algorithm_phase_improvement_counts": {"alns": 2, "vns": 1},
            "solver_algorithm_phase_runtime_ms": {
                "construction": 10,
                "alns": 70,
                "vns": 20,
            },
            "solver_algorithm_stop_reason": "time_limit",
            "solver_algorithm_runtime_budget_hit": True,
        },
    }
