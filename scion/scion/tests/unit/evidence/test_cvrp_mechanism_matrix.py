from __future__ import annotations

import csv
import importlib.util
import json
import sys
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
                    },
                    {
                        "case_id": "P-n76-k4",
                        "source_path": "cvrplib/P/P-n76-k4.vrp",
                        "subset": "P",
                        "dimension": 76,
                        "bks": 593.0,
                        "bks_routes": 4,
                    },
                    {
                        "case_id": "CMT4",
                        "source_path": "cvrplib/CMT/CMT4.vrp",
                        "subset": "CMT",
                        "dimension": 151,
                        "bks": 1028.0,
                        "bks_routes": 12,
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


def test_available_mechanisms_include_focused_vns_diagnostics() -> None:
    mechanisms = {item.mechanism_id: item for item in available_cvrp_mechanisms()}

    assert set(mechanisms) >= {
        "canonical_alns_vns",
        "alns_only",
        "size70_two_opt_candidate",
        "initial_vns_disabled",
        "embedded_vns_disabled",
        "pure_alns_no_polish",
        "adaptive_embedded_vns_cadence4",
        "adaptive_embedded_vns_cadence2",
        "adaptive_embedded_vns_early8_cadence2",
        "adaptive_embedded_vns_share60_cadence2",
        "adaptive_embedded_vns_improve_only",
    }
    assert mechanisms["initial_vns_disabled"].overlays == (
        "config_disable_initial_vns",
    )
    assert mechanisms["embedded_vns_disabled"].overlays == (
        "config_disable_embedded_vns",
    )
    assert mechanisms["pure_alns_no_polish"].overlays == (
        "config_use_vns_false",
        "config_disable_size70_two_opt",
    )
    assert mechanisms["adaptive_embedded_vns_cadence4"].overlays == (
        "config_adaptive_embedded_vns_cadence4",
    )
    assert mechanisms["adaptive_embedded_vns_cadence2"].overlays == (
        "config_adaptive_embedded_vns_cadence2",
    )
    assert mechanisms["adaptive_embedded_vns_early8_cadence2"].overlays == (
        "config_adaptive_embedded_vns_early8_cadence2",
    )
    assert mechanisms["adaptive_embedded_vns_share60_cadence2"].overlays == (
        "config_adaptive_embedded_vns_share60_cadence2",
    )
    assert mechanisms["adaptive_embedded_vns_improve_only"].overlays == (
        "config_adaptive_embedded_vns_improve_only",
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
    assert alns_result["phase_telemetry"]["objective_probes"] == [
        {"name": "vns_initial_before", "total_distance": 1530.0},
        {"name": "vns_initial_after", "total_distance": 1510.0},
    ]
    assert alns_result["phase_telemetry"]["alns_iteration_trace"] == [
        {
            "iteration": 1,
            "q": 8,
            "destroy_operator": "shaw",
            "repair_operator": "regret3",
            "accepted": True,
            "acceptance_reason": "new_best",
        }
    ]
    assert alns_result["runtime_phase_split"]["phase_runtime_ms"] == {
        "construction": 10,
        "alns_core": 12,
        "alns": 70,
        "vns": 20,
        "vns_initial": 5,
        "vns_embedded": 30,
    }

    tool = _load_tool()
    summary_path = tmp_path / "summary.csv"
    tool._write_summary_csv(summary_path, [alns_result])
    rows = list(csv.DictReader(summary_path.open(encoding="utf-8")))
    assert rows[0]["alns_iterations"] == "4"
    assert rows[0]["alns_iteration_trace_count"] == "1"
    assert rows[0]["alns_core_runtime_ms"] == "12"
    assert rows[0]["vns_initial_runtime_ms"] == "5"
    assert rows[0]["vns_embedded_runtime_ms"] == "30"


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


def test_case_id_filter_selects_exact_cases_before_case_limit(tmp_path: Path) -> None:
    manifest_path = tmp_path / "cases.json"
    _case_manifest(manifest_path)

    cases = load_case_entries(
        manifest_path,
        case_id_filter=("P-n76-k4", "CMT4"),
        case_limit=1,
    )

    assert [case.case_id for case in cases] == ["P-n76-k4"]


def test_cli_dry_run_accepts_repeatable_case_id_filter(tmp_path: Path) -> None:
    manifest_path = tmp_path / "cases.json"
    _case_manifest(manifest_path)
    output_dir = tmp_path / "matrix"
    tool = _load_tool()

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
            "--case-id",
            "P-n76-k4",
            "--case-id",
            "CMT4",
            "--case-limit",
            "2",
            "--seed",
            "11",
            "--time-budget-sec",
            "1",
            "--dry-run",
        ]
    )

    assert status == 0
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert [case["case_id"] for case in manifest["cases"]] == ["P-n76-k4", "CMT4"]
    assert {job["case"]["case_id"] for job in manifest["jobs"]} == {
        "P-n76-k4",
        "CMT4",
    }


def test_cli_dry_run_accepts_focused_mechanism_selection(tmp_path: Path) -> None:
    manifest_path = tmp_path / "cases.json"
    _case_manifest(manifest_path)
    output_dir = tmp_path / "matrix"
    tool = _load_tool()

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
            "--mechanism",
            "initial_vns_disabled",
            "--mechanism",
            "pure_alns_no_polish",
            "--mechanism",
            "adaptive_embedded_vns_cadence4",
            "--mechanism",
            "adaptive_embedded_vns_cadence2",
            "--mechanism",
            "adaptive_embedded_vns_early8_cadence2",
            "--mechanism",
            "adaptive_embedded_vns_share60_cadence2",
            "--mechanism",
            "adaptive_embedded_vns_improve_only",
            "--seed",
            "11",
            "--time-budget-sec",
            "1",
            "--dry-run",
        ]
    )

    assert status == 0
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert [job["mechanism_id"] for job in manifest["jobs"]] == [
        "initial_vns_disabled",
        "pure_alns_no_polish",
        "adaptive_embedded_vns_cadence4",
        "adaptive_embedded_vns_cadence2",
        "adaptive_embedded_vns_early8_cadence2",
        "adaptive_embedded_vns_share60_cadence2",
        "adaptive_embedded_vns_improve_only",
    ]


def test_early8_cadence2_overlay_patches_config(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    config_dir = workspace / "policies" / "baseline_modules"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.py"
    config_path.write_text(
        "\n".join(
            [
                "EMBEDDED_VNS_CADENCE = 1",
                "EMBEDDED_VNS_EARLY_ALWAYS_ITERATIONS = 0",
                "EMBEDDED_VNS_MIN_RUNTIME_SHARE = 0.0",
                "EMBEDDED_VNS_RUN_ON_REPAIR_IMPROVEMENT = False",
                "",
            ]
        ),
        encoding="utf-8",
    )
    tool = _load_tool()

    tool._apply_mechanism_overlays(
        workspace,
        ("config_adaptive_embedded_vns_early8_cadence2",),
    )

    text = config_path.read_text(encoding="utf-8")
    assert "EMBEDDED_VNS_CADENCE = 2" in text
    assert "EMBEDDED_VNS_EARLY_ALWAYS_ITERATIONS = 8" in text
    assert "EMBEDDED_VNS_RUN_ON_REPAIR_IMPROVEMENT = True" in text


def test_share60_cadence2_overlay_patches_config(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    config_dir = workspace / "policies" / "baseline_modules"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.py"
    config_path.write_text(
        "\n".join(
            [
                "EMBEDDED_VNS_CADENCE = 1",
                "EMBEDDED_VNS_MIN_RUNTIME_SHARE = 0.0",
                "EMBEDDED_VNS_RUN_ON_REPAIR_IMPROVEMENT = False",
                "",
            ]
        ),
        encoding="utf-8",
    )
    tool = _load_tool()

    tool._apply_mechanism_overlays(
        workspace,
        ("config_adaptive_embedded_vns_share60_cadence2",),
    )

    text = config_path.read_text(encoding="utf-8")
    assert "EMBEDDED_VNS_CADENCE = 2" in text
    assert "EMBEDDED_VNS_MIN_RUNTIME_SHARE = 0.60" in text
    assert "EMBEDDED_VNS_RUN_ON_REPAIR_IMPROVEMENT = True" in text


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
            "solver_algorithm_alns_iteration_trace": [
                {
                    "iteration": 1,
                    "q": 8,
                    "destroy_operator": "shaw",
                    "repair_operator": "regret3",
                    "accepted": True,
                    "acceptance_reason": "new_best",
                }
            ],
            "solver_algorithm_objective_probes": [
                {
                    "name": "vns_initial_before",
                    "total_distance": total_distance + 20.0,
                },
                {"name": "vns_initial_after", "total_distance": total_distance},
            ],
            "solver_algorithm_phase_move_attempts": {"alns": 8, "vns": 3},
            "solver_algorithm_phase_delta_sum": {"alns": 7.0, "vns": 2.0},
            "solver_algorithm_phase_best_delta": {"alns": 4.0, "vns": 2.0},
            "solver_algorithm_phase_improvement_counts": {"alns": 2, "vns": 1},
            "solver_algorithm_phase_runtime_ms": {
                "construction": 10,
                "alns_core": 12,
                "alns": 70,
                "vns": 20,
                "vns_initial": 5,
                "vns_embedded": 30,
            },
            "solver_algorithm_actionability_summary": {
                "phases": {"alns": {"iterations": 4}},
            },
            "solver_algorithm_stop_reason": "time_limit",
            "solver_algorithm_runtime_budget_hit": True,
        },
    }
