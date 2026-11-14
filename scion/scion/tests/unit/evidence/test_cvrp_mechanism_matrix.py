from __future__ import annotations

import json
from pathlib import Path

from scion.problems.cvrp.evidence.mechanism_matrix import (
    CvrpMatrixCase,
    available_cvrp_mechanisms,
    build_cvrp_mechanism_matrix_manifest,
    build_jobs,
    default_cvrp_mechanisms,
    load_case_entries,
    planned_result_for_job,
    summarize_solver_output_for_job,
)


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
                    },
                    {
                        "case_id": "P-n76-k4",
                        "source_path": "cvrplib/P/P-n76-k4.vrp",
                        "subset": "P",
                        "dimension": 76,
                        "bks": 593.0,
                        "bks_routes": 4,
                    },
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )


def test_mechanism_roster_keeps_scientific_variants_without_runner_authority() -> None:
    defaults = default_cvrp_mechanisms()
    available = {item.mechanism_id for item in available_cvrp_mechanisms()}

    assert [item.mechanism_id for item in defaults] == [
        "canonical_alns_vns",
        "alns_only",
        "size70_two_opt_candidate",
    ]
    assert {
        "initial_vns_disabled",
        "embedded_vns_disabled",
        "pure_alns_no_polish",
        "adaptive_embedded_vns_cadence4",
    } <= available


def test_matrix_manifest_is_an_ordinary_scientific_plan(tmp_path: Path) -> None:
    case = CvrpMatrixCase(
        case_id="A-n64-k9",
        source_path="cvrplib/A/A-n64-k9.vrp",
        case_family="A",
        case_slice="size_le_70",
        dimension=64,
        bks=1401.0,
        bks_routes=9,
    )

    manifest = build_cvrp_mechanism_matrix_manifest(
        cases=(case,),
        mechanisms=default_cvrp_mechanisms(),
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
    assert len(manifest["jobs"]) == 3
    assert manifest["jobs"][0]["case"]["case_family"] == "A"


def test_planned_and_completed_rows_keep_quality_measurements(tmp_path: Path) -> None:
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

    assert planned_result_for_job(jobs[0])["status"] == "planned"
    reference = summarize_solver_output_for_job(
        _solver_output(distance=1500.0, routes=9),
        job=jobs[0],
    )
    candidate = summarize_solver_output_for_job(
        _solver_output(distance=1510.0, routes=10),
        job=jobs[1],
        reference=reference,
    )

    assert candidate["quality"]["quality_delta_total_distance_vs_reference"] == 10.0
    assert candidate["route_fleet_regression_flags"][
        "route_count_regressed_vs_reference"
    ] is True
    assert candidate["accepted_moves"]["by_phase"] == {"alns": 5, "vns": 2}


def test_case_selection_remains_problem_owned(tmp_path: Path) -> None:
    manifest_path = tmp_path / "cases.json"
    _case_manifest(manifest_path)

    cases = load_case_entries(
        manifest_path,
        case_id_filter=("P-n76-k4",),
    )

    assert [case.case_id for case in cases] == ["P-n76-k4"]


def _solver_output(*, distance: float, routes: int) -> dict[str, object]:
    return {
        "objective": {
            "total_distance": distance,
            "fleet_violation": 0.0,
            "routes": routes,
        },
        "runtime": {
            "solver_algorithm_total_distance": distance,
            "solver_algorithm_solution_routes": routes,
            "solver_algorithm_fleet_violation": 0.0,
            "solver_algorithm_accepted_moves": 7,
            "solver_algorithm_phase_accepted_moves": {"alns": 5, "vns": 2},
            "solver_algorithm_phase_runtime_ms": {"alns": 70, "vns": 20},
        },
    }
