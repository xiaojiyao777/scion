from __future__ import annotations

import json
from pathlib import Path
import stat
from typing import Any, Iterator

import pytest

from scion.problems.cvrp.evidence import f1_analysis
from scion.problems.cvrp.evidence import f1_contract as contract
from scion.problems.cvrp.evidence import f1_io
from scion.problems.cvrp.evidence import f1_preparation
from scion.problems.cvrp.evidence import f1_runner
from scion.problems.cvrp.evidence.f1_ancestry import (
    CvrpF1Error,
    prepare_f1_root,
    run_f1_root,
    verify_f1_root,
)
from scion.problems.cvrp.evidence.f1_preparation import F1Plan

REPO_ROOT = Path(__file__).resolve().parents[5]
CLAW_PYTHON = Path("/home/clawd/miniconda3/envs/claw/bin/python")


def _make_writable(root: Path) -> None:
    if not root.exists():
        return
    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts)):
        try:
            path.chmod(path.stat().st_mode | stat.S_IWUSR | stat.S_IXUSR)
        except FileNotFoundError:
            pass
    root.chmod(root.stat().st_mode | stat.S_IWUSR | stat.S_IXUSR)


@pytest.fixture(scope="module")
def dry_plan(tmp_path_factory: pytest.TempPathFactory) -> Iterator[F1Plan]:
    if not contract.F1_SOURCE_ROOT.is_dir() or not CLAW_PYTHON.is_file():
        pytest.skip("accepted R11c authority or claw Python is absent on this host")
    root = tmp_path_factory.mktemp("cvrp-f1") / "dry-root"
    plan = prepare_f1_root(
        repo_root=REPO_ROOT,
        output_root=root,
        python=CLAW_PYTHON,
        dry_run=True,
    )
    try:
        yield plan
    finally:
        _make_writable(root)


def test_f1_materializes_exact_ancestry_population(dry_plan: F1Plan) -> None:
    manifest = dry_plan.manifest
    assert manifest["schema_version"] == contract.F1_SCHEMA
    assert [row["arm"] for row in manifest["arms"]] == list(contract.F1_ARM_ORDER)
    assert {
        row["arm"]: row["editable_hash"] for row in manifest["arms"]
    } == contract.F1_ARM_HASH
    assert manifest["cell_count"] == 64
    assert manifest["job_count"] == 256
    assert len(manifest["jobs"]) == 256
    assert manifest["input_snapshot"]["file_count"] == 32
    assert len(manifest["input_snapshot"]["inventory"]) == 32
    assert all(
        {item["kind"] for item in case["pair_files"]} == {"vrp", "sol"}
        for case in manifest["cases"]
    )
    assert all(
        case["parsed_facts"]["solution_validity_smoke"]["consistency_passed"]
        and case["parsed_facts"]["solution_validity_smoke"]["feasibility_passed"]
        for case in manifest["cases"]
    )
    runtime_root = dry_plan.root / "runtime_snapshots"
    assert stat.S_IMODE(runtime_root.stat().st_mode) == 0o555
    for arm in manifest["arms"]:
        package_root = dry_plan.root / arm["package_root"]
        assert stat.S_IMODE(package_root.parent.stat().st_mode) == 0o555
        assert stat.S_IMODE(package_root.stat().st_mode) == 0o555
        assert all(row["path"].startswith("scion/") for row in arm["runtime_inventory"])
    assert not list(dry_plan.root.rglob("__pycache__"))
    assert not list(dry_plan.root.rglob("*.pyc"))
    assert not list(dry_plan.root.rglob("*.pyo"))


def test_f1_williams_balance_is_exact(dry_plan: F1Plan) -> None:
    jobs = dry_plan.manifest["jobs"]
    for stage in ("screening", "validation"):
        stage_jobs = [row for row in jobs if row["stage"] == stage]
        position_counts = {arm: [0, 0, 0, 0] for arm in contract.F1_ARM_ORDER}
        adjacency = {
            (left, right): 0
            for left in contract.F1_ARM_ORDER
            for right in contract.F1_ARM_ORDER
            if left != right
        }
        for cell in range(32):
            quartet = stage_jobs[cell * 4 : cell * 4 + 4]
            assert "".join(row["arm_symbol"] for row in quartet) == (
                contract.F1_WILLIAMS[cell % 4]
            )
            for position, row in enumerate(quartet):
                position_counts[row["arm"]][position] += 1
            for left, right in zip(quartet, quartet[1:]):
                adjacency[(left["arm"], right["arm"])] += 1
        assert all(value == [8, 8, 8, 8] for value in position_counts.values())
        assert all(value == 8 for value in adjacency.values())


def test_f1_repeated_verify_is_byte_and_membership_stable(
    dry_plan: F1Plan,
) -> None:
    before = f1_io._inventory(dry_plan.root)
    first = verify_f1_root(dry_plan.root)
    second = verify_f1_root(dry_plan.root)
    assert first.manifest_sha256 == second.manifest_sha256
    assert f1_io._inventory(dry_plan.root) == before


def test_f1_verify_rejects_generated_bytecode_and_recovers(
    dry_plan: F1Plan,
) -> None:
    package = dry_plan.root / dry_plan.manifest["arms"][0]["package_root"] / "scion"
    cache = package / "__pycache__"
    original_mode = stat.S_IMODE(package.stat().st_mode)
    package.chmod(0o755)
    cache.mkdir()
    bytecode = cache / "escape.pyc"
    bytecode.write_bytes(b"not-bytecode-authority")
    try:
        with pytest.raises(CvrpF1Error, match="generated bytecode"):
            verify_f1_root(dry_plan.root)
    finally:
        bytecode.unlink()
        cache.rmdir()
        package.chmod(original_mode)
    verify_f1_root(dry_plan.root)


def test_f1_verify_rejects_package_root_injection_and_writable_parent(
    dry_plan: F1Plan,
) -> None:
    package_root = dry_plan.root / dry_plan.manifest["arms"][0]["package_root"]
    arm_root = package_root.parent
    injected = package_root / "injected_top_level.py"
    package_root.chmod(0o755)
    injected.write_text("INJECTED = True\n", encoding="utf-8")
    injected.chmod(0o444)
    package_root.chmod(0o555)
    try:
        with pytest.raises(CvrpF1Error, match="runtime complete inventory drift"):
            verify_f1_root(dry_plan.root)
    finally:
        package_root.chmod(0o755)
        injected.unlink()
        package_root.chmod(0o555)
    arm_root.chmod(0o755)
    try:
        with pytest.raises(CvrpF1Error, match="sealed path mode drift"):
            verify_f1_root(dry_plan.root)
    finally:
        arm_root.chmod(0o555)
    verify_f1_root(dry_plan.root)


def test_f1_verify_rederives_job_command_and_identity(
    dry_plan: F1Plan,
) -> None:
    manifest_path = dry_plan.manifest_path
    original = manifest_path.read_bytes()
    original_mode = stat.S_IMODE(manifest_path.stat().st_mode)
    manifest_path.chmod(0o644)
    payload = json.loads(original)
    payload["jobs"][0]["environment"]["UNDECLARED"] = "1"
    manifest_path.write_bytes(f1_io._canonical_pretty_bytes(payload))
    manifest_path.chmod(original_mode)
    try:
        with pytest.raises(CvrpF1Error, match="job binding drift"):
            verify_f1_root(dry_plan.root)
    finally:
        manifest_path.chmod(0o644)
        manifest_path.write_bytes(original)
        manifest_path.chmod(original_mode)
    verify_f1_root(dry_plan.root)


def test_f1_dry_root_cannot_start_solver(dry_plan: F1Plan) -> None:
    with pytest.raises(CvrpF1Error, match="dry root"):
        run_f1_root(dry_plan.root)
    assert not (dry_plan.root / "raw").exists()
    assert not (dry_plan.root / "terminal.json").exists()


def test_f1_dry_root_cannot_publish_scientific_closure(
    dry_plan: F1Plan,
) -> None:
    with pytest.raises(CvrpF1Error, match="dry root"):
        f1_analysis.close_f1_root(dry_plan.root)
    assert not (dry_plan.root / f1_analysis.REPORT_NAME).exists()
    assert not (dry_plan.root / f1_analysis.RECEIPT_NAME).exists()


def test_f1_prepare_requires_absent_root(tmp_path: Path) -> None:
    existing = tmp_path / "exists"
    existing.mkdir()
    with pytest.raises(CvrpF1Error, match="must be absent"):
        prepare_f1_root(
            repo_root=REPO_ROOT,
            output_root=existing,
            python=CLAW_PYTHON,
            dry_run=True,
        )


def test_f1_formal_prepare_requires_committed_implementation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "formal"
    monkeypatch.setattr(
        f1_preparation,
        "_git_context",
        lambda _repo, _design: {
            "git_commit_context": "fixed",
            "tracked_at_git_commit": True,
        },
    )
    monkeypatch.setattr(
        f1_preparation,
        "_implementation_source_identities",
        lambda _repo: [
            {
                "path": "uncommitted.py",
                "sha256": "0" * 64,
                "tracked_at_git_commit": False,
            }
        ],
    )
    with pytest.raises(CvrpF1Error, match="committed design and implementation"):
        prepare_f1_root(
            repo_root=REPO_ROOT,
            output_root=root,
            python=CLAW_PYTHON,
            dry_run=False,
        )
    assert not root.exists()


def _row(
    *,
    stage: str,
    case_path: str,
    seed: int,
    arm: str,
    distance: float,
    fleet: int = 0,
) -> dict[str, object]:
    return {
        "job_id": f"{stage}-{Path(case_path).stem}-{seed}-{arm}",
        "stage": stage,
        "case_path": case_path,
        "seed": seed,
        "arm": arm,
        "status": "validated_solver",
        "validity": {
            "status": "present",
            "solution_valid": True,
            "fleet_feasible": fleet == 0,
            "reasons": [],
        },
        "objective": {
            "status": "present",
            "fleet_violation": fleet,
            "total_distance": distance,
            "routes": 1,
        },
        "telemetry": {},
    }


def test_f1_case_analysis_uses_case_units_and_positive_improvement() -> None:
    rows = []
    for stage in ("screening", "validation"):
        for case_path, _ in contract.F1_CASES[stage]:
            for seed in contract.F1_SEEDS[stage]:
                for arm, distance in (
                    ("champion", 110.0),
                    ("h1_only", 120.0),
                    ("swap_only", 90.0),
                    ("cumulative", 100.0),
                ):
                    rows.append(
                        _row(
                            stage=stage,
                            case_path=case_path,
                            seed=seed,
                            arm=arm,
                            distance=distance,
                        )
                    )
    result = f1_analysis._contrast("primary", "swap_only", "cumulative", rows)
    for stage in ("screening", "validation"):
        summary = result["stages"][stage]
        assert summary["total_cases"] == 8
        assert summary["valid_cases"] == 8
        assert summary["bootstrap_input_count"] == 8
        assert summary["median_improvement"] == 10.0
        assert summary["case_sign_counts"] == {
            "treatment_wins": 8,
            "reference_wins": 0,
            "ties": 0,
            "incomplete": 0,
        }
        assert summary["direction"] == "treatment_better"


def test_f1_fleet_difference_keeps_lexicographic_vote_but_not_distance() -> None:
    treatment = _row(
        stage="screening",
        case_path="case.vrp",
        seed=11,
        arm="swap_only",
        distance=90.0,
        fleet=1,
    )
    reference = _row(
        stage="screening",
        case_path="case.vrp",
        seed=11,
        arm="cumulative",
        distance=100.0,
        fleet=0,
    )
    result = f1_analysis._paired_seed(treatment, reference)
    assert result["comparison"] == "reference_win"
    assert result["distance_improvement"] is None
    assert result["missing_reason"] is None
    assert result["distance_missing_reason"] == "fleet_difference"


def test_f1_parser_fleet_violation_remains_lexicographically_usable() -> None:
    parsed = f1_runner._parse_solver_evidence(
        {"runtime": {}},
        {
            # This is the real sealed-validator state for a structurally and
            # capacity-valid solution that uses one route above the limit.
            "solution_valid": True,
            "fleet_feasible": False,
            "reasons": [],
            "objective": {
                "fleet_violation": 1,
                "total_distance": 90.0,
                "routes": 2,
            },
            "bks": 80.0,
            "bks_routes": 1,
            "bks_gap_pct": 12.5,
        },
    )
    treatment = {
        "job_id": "parsed-fleet-violation",
        "stage": "screening",
        "case_path": "case.vrp",
        "seed": 11,
        "arm": "swap_only",
        "status": "validated_solver",
        "failure": None,
        **parsed,
    }
    reference = _row(
        stage="screening",
        case_path="case.vrp",
        seed=11,
        arm="cumulative",
        distance=100.0,
        fleet=0,
    )
    assert treatment["validity"]["fleet_feasible"] is False
    f1_analysis._validate_usable_shape(treatment)
    assert f1_analysis._usable(treatment)
    paired = f1_analysis._paired_seed(treatment, reference)
    assert paired["comparison"] == "reference_win"
    assert paired["distance_improvement"] is None
    assert paired["distance_missing_reason"] == "fleet_difference"


def test_f1_fleet_difference_only_matrix_uses_lexicographic_direction() -> None:
    rows = []
    for stage in ("screening", "validation"):
        for case_path, _ in contract.F1_CASES[stage]:
            for seed in contract.F1_SEEDS[stage]:
                for arm, fleet in (
                    ("champion", 3),
                    ("h1_only", 4),
                    ("swap_only", 1),
                    ("cumulative", 2),
                ):
                    rows.append(
                        _row(
                            stage=stage,
                            case_path=case_path,
                            seed=seed,
                            arm=arm,
                            distance=100.0,
                            fleet=fleet,
                        )
                    )
    contrasts = _all_contrasts(rows)
    assert f1_analysis._scientific_evidence_sufficient(contrasts)
    for contrast in contrasts:
        for stage in ("screening", "validation"):
            summary = contrast["stages"][stage]
            assert summary["valid_cases"] == 8
            assert summary["bootstrap_input_count"] == 0
            assert summary["median_improvement"] is None
            assert summary["bootstrap_ci"] is None
            assert summary["direction"] in {
                "treatment_better",
                "reference_better",
            }


def test_f1_stage_direction_uses_case_votes_before_eligible_median() -> None:
    cases = [
        {
            "case_path": "a.vrp",
            "case_outcome": "treatment_win",
            "median_improvement": -100.0,
            "missing_reasons": [],
        },
        {
            "case_path": "b.vrp",
            "case_outcome": "treatment_win",
            "median_improvement": -100.0,
            "missing_reasons": [],
        },
        {
            "case_path": "c.vrp",
            "case_outcome": "reference_win",
            "median_improvement": -100.0,
            "missing_reasons": [],
        },
    ]
    assert f1_analysis._summary_values(cases)["direction"] == "treatment_better"
    no_distance_tie = [
        {
            "case_path": "d.vrp",
            "case_outcome": "tie",
            "median_improvement": None,
            "missing_reasons": [],
        }
    ]
    tied = f1_analysis._summary_values(no_distance_tie)
    assert tied["direction"] == "unknown"
    assert tied["median_improvement"] is None
    assert tied["bootstrap_ci"] is None


def _failure_row(
    *, stage: str, case_path: str, seed: int, arm: str
) -> dict[str, object]:
    return {
        "job_id": f"{stage}-{Path(case_path).stem}-{seed}-{arm}",
        "stage": stage,
        "case_path": case_path,
        "seed": seed,
        "arm": arm,
        "status": "solver_failure",
        "failure": {"type": "nonzero_exit_or_signal", "reason": "typed failure"},
        "validity": {"status": "missing", "reason": "solver_failure"},
        "objective": {"status": "missing", "reason": "solver_failure"},
        "telemetry": {"status": "missing", "reason": "solver_failure"},
    }


def _matrix_rows(
    *, fail_validation_cumulative: bool = False
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for stage in ("screening", "validation"):
        for case_path, _ in contract.F1_CASES[stage]:
            for seed in contract.F1_SEEDS[stage]:
                for arm, distance in (
                    ("champion", 110.0),
                    ("h1_only", 120.0),
                    ("swap_only", 90.0),
                    ("cumulative", 100.0),
                ):
                    if (
                        fail_validation_cumulative
                        and stage == "validation"
                        and arm == "cumulative"
                    ):
                        rows.append(
                            _failure_row(
                                stage=stage,
                                case_path=case_path,
                                seed=seed,
                                arm=arm,
                            )
                        )
                    else:
                        rows.append(
                            _row(
                                stage=stage,
                                case_path=case_path,
                                seed=seed,
                                arm=arm,
                                distance=distance,
                            )
                        )
    return rows


def _all_contrasts(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    return [
        f1_analysis._contrast(role, treatment, reference, rows)
        for role, treatment, reference in f1_analysis._CONTRASTS
    ]


def test_f1_zero_eligible_complete_typed_population_is_invalid_unknown() -> None:
    rows = [
        _failure_row(stage=stage, case_path=case_path, seed=seed, arm=arm)
        for stage in ("screening", "validation")
        for case_path, _ in contract.F1_CASES[stage]
        for seed in contract.F1_SEEDS[stage]
        for arm in contract.F1_ARM_ORDER
    ]
    assert len(rows) == 256
    contrasts = _all_contrasts(rows)
    assert all(
        contrast["stages"][stage]["direction"] == "unknown"
        and contrast["stages"][stage]["bootstrap_input_count"] == 0
        and contrast["stages"][stage]["median_improvement"] is None
        and contrast["stages"][stage]["bootstrap_ci"] is None
        for contrast in contrasts
        for stage in ("screening", "validation")
    )
    assert not f1_analysis._scientific_evidence_sufficient(contrasts)
    assert (
        f1_analysis._report_disposition(
            evidence_sufficient=False,
            failures=rows,
        )
        == "invalid_or_incomplete"
    )


def test_f1_r11c_consistency_is_typed_missing_when_direction_unknown() -> None:
    assert f1_analysis._directional_consistency("unknown") == {
        "status": "missing",
        "reason": "f1_cumulative_direction_unknown",
    }
    assert f1_analysis._directional_consistency("treatment_better") == {
        "status": "present",
        "value": True,
    }
    assert f1_analysis._directional_consistency("reference_better") == {
        "status": "present",
        "value": False,
    }
    assert f1_analysis._directional_consistency("tie") == {
        "status": "present",
        "value": False,
    }


def test_f1_structurally_insufficient_partial_population_is_invalid() -> None:
    rows = _matrix_rows(fail_validation_cumulative=True)
    assert len(rows) == 256
    contrasts = _all_contrasts(rows)
    assert not f1_analysis._scientific_evidence_sufficient(contrasts)
    assert any(
        contrast["stages"]["validation"]["direction"] == "unknown"
        for contrast in contrasts
    )
    failures = [row for row in rows if row["status"] == "solver_failure"]
    assert (
        f1_analysis._report_disposition(
            evidence_sufficient=False,
            failures=failures,
        )
        == "invalid_or_incomplete"
    )


def test_f1_runner_types_missing_telemetry_instead_of_zero() -> None:
    parsed = f1_runner._parse_solver_evidence(
        {
            "runtime": {
                # This historical-looking field is not the frozen SWAP*
                # elapsed-time authority and must not be used as a fallback.
                "solver_algorithm_phase_runtime_ms": {"swap_star": 999},
            }
        },
        {
            "solution_valid": True,
            "fleet_feasible": True,
            "reasons": [],
            "objective": {
                "fleet_violation": 0,
                "total_distance": 10.0,
                "routes": 1,
            },
            "bks": 9.0,
            "bks_routes": 1,
            "bks_gap_pct": 100.0 / 9.0,
        },
    )
    assert parsed["telemetry"]["initial_solution"]["identity"] == {
        "status": "missing",
        "reason": "solver_did_not_emit_initial_solution_identity",
    }
    assert parsed["telemetry"]["swap_star"]["attempts"] == {
        "status": "missing",
        "reason": "solver_did_not_emit",
    }
    assert parsed["telemetry"]["swap_star"]["elapsed_ms"] == {
        "status": "missing",
        "reason": "solver_did_not_emit",
    }
    assert parsed["telemetry"]["route_elimination"]["selections"] == {
        "status": "missing",
        "reason": "solver_did_not_emit",
    }
    assert parsed["telemetry"]["alns"]["best_update_trace"] == {
        "status": "missing",
        "reason": "solver_did_not_emit_best_update_trace",
    }
    assert parsed["telemetry"]["alns"]["best_update_summary"] == {
        "status": "missing",
        "reason": "solver_did_not_emit_best_update_summary",
    }
    assert parsed["telemetry"]["alns"]["acceptance_trajectory"] == {
        "status": "missing",
        "reason": "solver_did_not_emit",
    }
    assert parsed["telemetry"]["alns"]["sa_temperature_trajectory"] == {
        "status": "missing",
        "reason": "solver_did_not_emit_sa_temperature_trajectory",
    }


def test_f1_parser_matches_protected_r11c_telemetry_schema() -> None:
    relative = "campaign/metrics/83fe3b49-df68-4b14-8c74-7e6f0d2f62a8.json"
    path = contract.F1_SOURCE_ROOT / relative
    if not path.is_file():
        pytest.skip("protected R11c telemetry authority is absent")
    assert f1_io._sha256_file(path) == contract._PROTECTED_AUTHORITIES[relative]
    pair = json.loads(path.read_text(encoding="utf-8"))["pairs"][0]
    assert pair["case"] == "cvrplib/A/A-n64-k9.vrp"
    assert pair["seed"] == 11
    runtime = pair["candidate_runtime"]
    assert "solver_algorithm_trajectory" not in runtime
    assert "solver_algorithm_search_throughput" not in runtime
    assert "solver_algorithm_sa_temperature_trajectory" not in runtime
    assert "swap_star" not in runtime["solver_algorithm_phase_runtime_ms"]
    parsed = f1_runner._parse_solver_evidence(
        {"runtime": runtime},
        {
            "solution_valid": True,
            "fleet_feasible": True,
            "reasons": [],
            "objective": runtime["solver_algorithm_objective"],
            "bks": 1401.0,
            "bks_routes": 9,
            "bks_gap_pct": 0.0,
        },
    )
    assert parsed["telemetry"]["initial_solution"]["objective"] == {
        "status": "present",
        "value": runtime["solver_algorithm_solution_progress"][
            "initial_total_distance"
        ],
    }
    assert parsed["telemetry"]["alns"]["throughput"] == {
        "status": "missing",
        "reason": "solver_did_not_emit",
    }
    assert parsed["telemetry"]["swap_star"]["elapsed_ms"] == {
        "status": "present",
        "value": runtime["solver_algorithm_actionability_summary"]["phases"][
            "swap_star"
        ]["runtime_ms"],
    }
    assert (
        parsed["telemetry"]["alns"]["best_update_trace"]
        == runtime["solver_algorithm_best_update_trace"]
    )
    assert (
        parsed["telemetry"]["alns"]["best_update_summary"]
        == runtime["solver_algorithm_best_update_summary"]
    )
    assert (
        parsed["telemetry"]["alns"]["acceptance_trajectory"]
        == runtime["solver_algorithm_alns_iteration_trace"]
    )
    assert parsed["telemetry"]["alns"]["sa_temperature_trajectory"] == {
        "status": "missing",
        "reason": "solver_did_not_emit_sa_temperature_trajectory",
    }


def test_f1_route_elimination_counts_only_route_operator_rows() -> None:
    raw = {
        "runtime": {
            "solver_algorithm_alns_iteration_trace": [
                {
                    "destroy_operator": "route",
                    "acceptance_reason": "destroy_empty",
                    "accepted": False,
                    "best_improved": False,
                },
                {
                    "destroy_operator": "route",
                    "acceptance_reason": "improved",
                    "accepted": True,
                    "best_improved": True,
                },
                {
                    "destroy_operator": "random",
                    "repair_operator": "regret3",
                    "acceptance_reason": "improved",
                    "accepted": True,
                    "best_improved": True,
                },
            ]
        }
    }
    parsed = f1_runner._parse_solver_evidence(
        raw,
        {
            "solution_valid": True,
            "fleet_feasible": True,
            "reasons": [],
            "objective": {
                "fleet_violation": 0,
                "total_distance": 10.0,
                "routes": 1,
            },
            "bks": 9.0,
            "bks_routes": 1,
            "bks_gap_pct": 100.0 / 9.0,
        },
    )
    route = parsed["telemetry"]["route_elimination"]
    assert route["selections"] == {"status": "present", "value": 2}
    assert route["destroy_empty"] == {"status": "present", "value": 1}
    assert route["repair_invocations"] == {"status": "present", "value": 1}
    assert route["acceptances"] == {"status": "present", "value": 1}
    assert route["best_updates"] == {"status": "present", "value": 1}


def test_f1_mechanism_summary_counts_activation_occupancy_and_missing() -> None:
    rows = [
        _row(
            stage="screening",
            case_path="case.vrp",
            seed=seed,
            arm="cumulative",
            distance=distance,
        )
        for seed, distance in ((11, 10.0), (29, 11.0))
    ]
    rows[0]["telemetry"] = {
        "swap_star": {
            "attempts": {"status": "present", "value": 3},
            "accepted": {"status": "present", "value": 1},
        },
        "alns": {
            "iterations": {"status": "present", "value": 0},
            "throughput": {"status": "missing", "reason": "solver_did_not_emit"},
            "best_update_trace": [{"iteration": 1, "total_distance": 10.0}],
            "best_update_summary": {"best_update_count": 1},
            "iteration_trace": [
                {
                    "iteration": 1,
                    "destroy_operator": "route",
                    "repair_operator": "regret3_existing",
                    "q": 10,
                }
            ],
            "acceptance_trajectory": [
                {
                    "iteration": 1,
                    "accepted": False,
                    "acceptance_reason": "destroy_empty",
                }
            ],
            "sa_temperature_trajectory": {
                "status": "missing",
                "reason": "solver_did_not_emit_sa_temperature_trajectory",
            },
        },
        "phase_runtime_ms": {
            "vns_initial": {"status": "present", "value": 10},
            "vns_embedded": {"status": "missing", "reason": "solver_did_not_emit"},
            "alns_core": {"status": "present", "value": 30},
        },
        "route_elimination": {
            "selections": {"status": "present", "value": 1},
            "destroy_empty": {"status": "present", "value": 1},
            "repair_invocations": {"status": "present", "value": 0},
            "acceptances": {"status": "present", "value": 0},
            "best_updates": {"status": "present", "value": 0},
            "elapsed_ms": {
                "status": "missing",
                "reason": "solver_did_not_emit_route_elimination_elapsed",
            },
        },
    }
    rows[1]["telemetry"] = {
        "swap_star": {
            "attempts": {"status": "present", "value": 0},
            "accepted": {"status": "present", "value": 0},
        },
        "alns": {
            "iterations": {"status": "present", "value": 5},
            "throughput": {"status": "missing", "reason": "solver_did_not_emit"},
            "best_update_trace": {
                "status": "missing",
                "reason": "solver_did_not_emit_best_update_trace",
            },
            "best_update_summary": {
                "status": "missing",
                "reason": "solver_did_not_emit_best_update_summary",
            },
            "iteration_trace": {"status": "missing", "reason": "solver_did_not_emit"},
            "acceptance_trajectory": {
                "status": "missing",
                "reason": "solver_did_not_emit",
            },
            "sa_temperature_trajectory": {
                "status": "missing",
                "reason": "solver_did_not_emit_sa_temperature_trajectory",
            },
        },
        "phase_runtime_ms": {
            "vns_initial": {"status": "present", "value": 0},
            "vns_embedded": {"status": "present", "value": 20},
            "alns_core": {"status": "present", "value": 40},
        },
        "route_elimination": {
            name: {"status": "missing", "reason": "solver_did_not_emit"}
            for name in (
                "selections",
                "destroy_empty",
                "repair_invocations",
                "acceptances",
                "best_updates",
                "elapsed_ms",
            )
        },
    }
    summary = f1_analysis._mechanism_summary(rows)
    group = next(
        row
        for row in summary["groups"]
        if row["stage"] == "screening" and row["arm"] == "cumulative"
    )
    assert group["swap_star_activation"]["activated_count"] == 1
    assert group["swap_star_activation"]["inactive_count"] == 1
    assert group["zero_alns_incidence"]["zero_count"] == 1
    assert group["zero_alns_incidence"]["nonzero_count"] == 1
    assert group["vns_occupancy_runtime_ms"]["initial"]["present_count"] == 2
    assert group["vns_occupancy_runtime_ms"]["embedded"]["typed_missing_count"] == 1
    assert group["alns_throughput"]["present_count"] == 0
    assert group["alns_throughput"]["typed_missing_count"] == 2
    route = group["route_elimination_deadness"]
    assert route["ancestry_treatment"] is True
    assert route["dead_count"] == 1
    assert route["typed_missing_count"] == 1
    scheduler = group["scheduler_rng_path"]
    assert scheduler["present_path_count"] == 1
    assert scheduler["typed_missing_count"] == 1
    assert scheduler["destroy_operator_counts"] == {
        "status": "present",
        "value": {"route": 1},
    }
    assert scheduler["raw_rng_state"] == {
        "status": "missing",
        "reason": "solver_did_not_emit_rng_state",
    }
    mechanism_row = f1_analysis._mechanism_row(rows[0])
    assert mechanism_row["best_update_trace"] == [
        {"iteration": 1, "total_distance": 10.0}
    ]
    assert mechanism_row["best_update_summary"] == {"best_update_count": 1}
    assert mechanism_row["acceptance_trajectory"][0]["acceptance_reason"] == (
        "destroy_empty"
    )
    assert mechanism_row["sa_temperature_trajectory"] == {
        "status": "missing",
        "reason": "solver_did_not_emit_sa_temperature_trajectory",
    }
    assert summary["throughput_derivation"] is None


def _artifact_telemetry() -> dict[str, Any]:
    missing = {"status": "missing", "reason": "solver_did_not_emit"}
    return {
        "initial_solution": {
            "identity": dict(missing),
            "objective": {"status": "present", "value": 120.0},
        },
        "phase_runtime_ms": {
            "vns_initial": {"status": "present", "value": 1},
            "vns_embedded": {"status": "present", "value": 2},
            "alns_core": {"status": "present", "value": 3},
            "repair": dict(missing),
            "polish": dict(missing),
            "residual": dict(missing),
        },
        "alns": {
            "iterations": {"status": "present", "value": 1},
            "throughput": dict(missing),
            "best_updates": {"status": "present", "value": 0},
            "best_update_trace": [],
            "best_update_summary": {"best_update_count": 0},
            "iteration_trace": [
                {
                    "iteration": 1,
                    "destroy_operator": "random",
                    "repair_operator": "regret2",
                    "q": 5,
                }
            ],
            "acceptance_trajectory": [
                {
                    "iteration": 1,
                    "destroy_operator": "random",
                    "repair_operator": "regret2",
                    "q": 5,
                }
            ],
            "sa_temperature_trajectory": {
                "status": "missing",
                "reason": "solver_did_not_emit_sa_temperature_trajectory",
            },
            "objective_probes": dict(missing),
            "stop_reason": {"status": "present", "value": "time_limit"},
            "runtime_budget_hit": {"status": "present", "value": True},
        },
        "swap_star": {
            "attempts": {"status": "present", "value": 1},
            "accepted": {"status": "present", "value": 0},
            "delta": {"status": "present", "value": 0.0},
            "elapsed_ms": {"status": "present", "value": 0},
        },
        "route_elimination": {
            "selections": {"status": "present", "value": 0},
            "destroy_empty": {"status": "present", "value": 0},
            "repair_invocations": {"status": "present", "value": 0},
            "acceptances": {"status": "present", "value": 0},
            "best_updates": {"status": "present", "value": 0},
            "elapsed_ms": {
                "status": "missing",
                "reason": "solver_did_not_emit_route_elimination_elapsed",
            },
        },
    }


def _write_complete_artifact_set(
    root: Path,
    *,
    failure_ordinals: frozenset[int] = frozenset(),
    terminal_failures: int | None = None,
) -> F1Plan:
    for dirname in ("raw", "interchange", "streams"):
        (root / dirname).mkdir(parents=True, exist_ok=True)
    arms = [
        {
            "arm": arm,
            "runtime_identity_sha256": f"runtime-{arm}",
        }
        for arm in contract.F1_ARM_ORDER
    ]
    by_symbol = {symbol: arm for arm, symbol in contract.F1_ARM_SYMBOL.items()}
    jobs: list[dict[str, Any]] = []
    ordinal = 0
    for stage in ("screening", "validation"):
        stage_cell = 0
        for case_path, time_limit in contract.F1_CASES[stage]:
            for seed in contract.F1_SEEDS[stage]:
                sequence = contract.F1_WILLIAMS[stage_cell % 4]
                for position, symbol in enumerate(sequence):
                    arm = by_symbol[symbol]
                    job_id = f"artifact-{ordinal:03d}"
                    jobs.append(
                        {
                            "root_id": "artifact-root",
                            "job_identity_sha256": f"job-{ordinal}",
                            "job_id": job_id,
                            "job_ordinal": ordinal,
                            "cell_ordinal": (
                                (0 if stage == "screening" else 32) + stage_cell
                            ),
                            "stage": stage,
                            "arm": arm,
                            "arm_symbol": symbol,
                            "schedule_position": position,
                            "williams_sequence": sequence,
                            "case_path": case_path,
                            "case_identity_sha256": f"case-{stage_cell}",
                            "solution_identity_sha256": f"solution-{stage_cell}",
                            "seed": seed,
                            "time_limit_sec": time_limit,
                            "command": ["frozen-solver", job_id],
                            "environment": {"F1": "sealed"},
                            "working_directory": f"/sealed/{arm}",
                            "row_path": f"raw/{job_id}.json",
                            "interchange_path": f"interchange/{job_id}.json",
                            "stdout_path": f"streams/{job_id}.stdout",
                            "stderr_path": f"streams/{job_id}.stderr",
                        }
                    )
                    ordinal += 1
                stage_cell += 1
    assert ordinal == 256
    manifest = {
        "dry_run": False,
        "root_id": "artifact-root",
        "arms": arms,
        "jobs": jobs,
    }
    manifest_path = root / "manifest.json"
    manifest_path.write_bytes(f1_io._canonical_pretty_bytes(manifest))
    plan = F1Plan(root=root, manifest_path=manifest_path, manifest=manifest)
    distances = {
        "champion": 110.0,
        "h1_only": 120.0,
        "swap_only": 90.0,
        "cumulative": 100.0,
    }
    for job in jobs:
        interchange = root / job["interchange_path"]
        stdout = root / job["stdout_path"]
        stderr = root / job["stderr_path"]
        interchange.write_text("{}\n", encoding="utf-8")
        stdout.write_bytes(b"")
        stderr.write_bytes(b"")
        row: dict[str, Any] = {
            "schema_version": contract.F1_ROW_SCHEMA,
            "manifest_sha256": plan.manifest_sha256,
            **{
                key: job[key]
                for key in (
                    "root_id",
                    "job_identity_sha256",
                    "job_id",
                    "job_ordinal",
                    "cell_ordinal",
                    "stage",
                    "arm",
                    "arm_symbol",
                    "schedule_position",
                    "williams_sequence",
                    "case_path",
                    "case_identity_sha256",
                    "solution_identity_sha256",
                    "seed",
                    "time_limit_sec",
                    "command",
                    "environment",
                    "working_directory",
                )
            },
            "workspace_identity_sha256": f"runtime-{job['arm']}",
            "interchange": f1_io._file_evidence(interchange),
            "stdout": f1_io._file_evidence(stdout),
            "stderr": f1_io._file_evidence(stderr),
        }
        if job["job_ordinal"] in failure_ordinals:
            row.update(
                {
                    "status": "solver_failure",
                    "failure": {
                        "type": "nonzero_exit_or_signal",
                        "reason": "fixture failure",
                    },
                    "parsed_payload": {
                        "status": "missing",
                        "reason": "nonzero_exit_or_signal",
                    },
                    "validity": {
                        "status": "missing",
                        "reason": "nonzero_exit_or_signal",
                    },
                    "objective": {
                        "status": "missing",
                        "reason": "nonzero_exit_or_signal",
                    },
                    "telemetry": {
                        "status": "missing",
                        "reason": "nonzero_exit_or_signal",
                    },
                }
            )
        else:
            row.update(
                {
                    "status": "validated_solver",
                    "failure": None,
                    "parsed_payload": {"status": "present", "sha256": "fixture"},
                    "validity": {
                        "status": "present",
                        "solution_valid": True,
                        "fleet_feasible": True,
                        "reasons": [],
                    },
                    "objective": {
                        "status": "present",
                        "fleet_violation": 0,
                        "total_distance": distances[job["arm"]],
                        "routes": 1,
                        "bks": 80.0,
                        "bks_routes": 1,
                        "bks_gap_pct": 0.0,
                    },
                    "telemetry": _artifact_telemetry(),
                }
            )
        (root / job["row_path"]).write_bytes(f1_io._canonical_pretty_bytes(row))
    failures = len(failure_ordinals) if terminal_failures is None else terminal_failures
    terminal = {
        "schema_version": contract.F1_TERMINAL_SCHEMA,
        "manifest_sha256": plan.manifest_sha256,
        "declared_jobs": 256,
        "published_rows": 256,
        "typed_solver_failures": failures,
        "runner_complete": True,
        "retry": False,
        "resume": False,
        "automatic_rerun": False,
    }
    (root / "terminal.json").write_bytes(f1_io._canonical_pretty_bytes(terminal))
    return plan


def test_f1_complete_artifact_set_closes_through_real_inventory_and_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = _write_complete_artifact_set(tmp_path / "artifact-set")
    monkeypatch.setattr(
        f1_analysis.preparation,
        "verify_f1_root",
        lambda _root: plan,
    )
    receipt = f1_analysis.close_f1_root(plan.root)
    report = json.loads((plan.root / f1_analysis.REPORT_NAME).read_text("utf-8"))
    assert receipt["closure_state"] == "complete"
    assert receipt["observed_rows"] == 256
    assert receipt["typed_solver_failures"] == 0
    assert len(receipt["row_identities"]) == 256
    assert len(report["analysis_inputs"]) == 256
    assert report["r11c_directional_consistency"] == {
        "screening": {"status": "present", "value": True},
        "validation": {"status": "present", "value": True},
    }
    first_mechanism = report["mechanism_trajectory"][0]
    assert first_mechanism["best_update_trace"] == []
    assert first_mechanism["best_update_summary"] == {"best_update_count": 0}
    assert first_mechanism["acceptance_trajectory"][0]["q"] == 5
    assert first_mechanism["sa_temperature_trajectory"] == {
        "status": "missing",
        "reason": "solver_did_not_emit_sa_temperature_trajectory",
    }


def test_f1_terminal_failure_count_must_match_complete_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = _write_complete_artifact_set(
        tmp_path / "terminal-mismatch",
        failure_ordinals=frozenset({0}),
        terminal_failures=0,
    )
    monkeypatch.setattr(
        f1_analysis.preparation,
        "verify_f1_root",
        lambda _root: plan,
    )
    with pytest.raises(CvrpF1Error, match="disagrees with immutable rows"):
        f1_analysis.close_f1_root(plan.root)
    assert not (plan.root / f1_analysis.REPORT_NAME).exists()
    assert not (plan.root / f1_analysis.RECEIPT_NAME).exists()


def test_f1_unknown_cumulative_direction_is_typed_missing_in_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = _write_complete_artifact_set(
        tmp_path / "unknown-direction",
        failure_ordinals=frozenset(range(256)),
    )
    monkeypatch.setattr(
        f1_analysis.preparation,
        "verify_f1_root",
        lambda _root: plan,
    )
    receipt = f1_analysis.close_f1_root(plan.root)
    report = json.loads((plan.root / f1_analysis.REPORT_NAME).read_text("utf-8"))
    assert receipt["disposition"] == "invalid_or_incomplete"
    assert report["r11c_directional_consistency"] == {
        "screening": {
            "status": "missing",
            "reason": "f1_cumulative_direction_unknown",
        },
        "validation": {
            "status": "missing",
            "reason": "f1_cumulative_direction_unknown",
        },
    }


def test_f1_atomic_publication_is_no_replace(tmp_path: Path) -> None:
    path = tmp_path / "artifact.json"
    f1_io._publish_json_no_replace(path, {"value": 1})
    original = path.read_bytes()
    with pytest.raises(FileExistsError):
        f1_io._publish_json_no_replace(path, {"value": 2})
    assert path.read_bytes() == original


def test_f1_closure_replay_is_byte_exact(tmp_path: Path) -> None:
    path = tmp_path / "closure.json"
    expected = b'{"sealed":true}\n'
    f1_analysis._publish_or_replay_bytes(path, expected)
    f1_analysis._publish_or_replay_bytes(path, expected)
    with pytest.raises(CvrpF1Error, match="differs from byte replay"):
        f1_analysis._publish_or_replay_bytes(path, b'{"sealed":false}\n')
    assert path.read_bytes() == expected


def test_f1_closer_recovers_report_published_receipt_missing_window(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "complete-root"
    raw_root = root / "raw"
    raw_root.mkdir(parents=True)
    manifest_path = root / "manifest.json"
    manifest_path.write_text("{}\n", encoding="utf-8")
    terminal_path = root / "terminal.json"
    terminal_path.write_text("{}\n", encoding="utf-8")
    raw_path = raw_root / "job-0.json"
    raw_path.write_text("{}\n", encoding="utf-8")
    plan = F1Plan(
        root=root,
        manifest_path=manifest_path,
        manifest={"dry_run": False, "root_id": "root-id"},
    )
    row = {"job_id": "job-0", "status": "validated_solver"}
    report = {
        "schema_version": f1_analysis.REPORT_SCHEMA,
        "disposition": "accepted_diagnostic",
        "fixed": True,
    }
    calls = {"rows": 0, "report": 0}

    def load_rows(_plan: F1Plan) -> list[dict[str, object]]:
        calls["rows"] += 1
        return [row]

    def build_report(
        _plan: F1Plan, _rows: list[dict[str, object]]
    ) -> dict[str, object]:
        calls["report"] += 1
        return report

    complete_inventory = {
        "missing_rows": [],
        "extra_rows": [],
        "missing_interchange": [],
        "extra_interchange": [],
        "missing_streams": [],
        "extra_streams": [],
        "partial_paths": [],
        "observed_rows": ["raw/job-0.json"],
        "observed_interchange": [],
        "observed_streams": [],
    }
    monkeypatch.setattr(f1_analysis.preparation, "verify_f1_root", lambda _root: plan)
    monkeypatch.setattr(
        f1_analysis, "_execution_inventory", lambda _plan: complete_inventory
    )
    monkeypatch.setattr(
        f1_analysis,
        "_terminal",
        lambda _plan: {"runner_complete": True, "typed_solver_failures": 0},
    )
    monkeypatch.setattr(f1_analysis, "_load_and_verify_rows", load_rows)
    monkeypatch.setattr(f1_analysis, "_build_report", build_report)

    first = f1_analysis.close_f1_root(root)
    report_path = root / f1_analysis.REPORT_NAME
    receipt_path = root / f1_analysis.RECEIPT_NAME
    expected_report = report_path.read_bytes()
    assert first["closure_state"] == "complete"
    assert report_path.is_file() and receipt_path.is_file()

    replayed = f1_analysis.close_f1_root(root)
    assert replayed == first
    assert report_path.read_bytes() == expected_report
    assert calls == {"rows": 2, "report": 2}

    receipt_path.unlink()
    recovered = f1_analysis.close_f1_root(root)
    assert recovered["closure_state"] == "complete"
    assert report_path.read_bytes() == expected_report
    assert receipt_path.is_file()
    assert calls == {"rows": 3, "report": 3}

    receipt_path.unlink()
    report_path.write_bytes(b'{"divergent":true}\n')
    with pytest.raises(CvrpF1Error, match="differs from byte replay"):
        f1_analysis.close_f1_root(root)
    assert not receipt_path.exists()
    assert report_path.read_bytes() == b'{"divergent":true}\n'
    assert calls == {"rows": 4, "report": 4}

    report_path.write_bytes(expected_report)
    f1_analysis.close_f1_root(root)
    report_path.unlink()
    receipt_bytes = receipt_path.read_bytes()
    with pytest.raises(CvrpF1Error, match="artifact set is incomplete"):
        f1_analysis.close_f1_root(root)
    assert receipt_path.read_bytes() == receipt_bytes
