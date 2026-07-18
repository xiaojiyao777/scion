"""Deterministic analysis and closure for the sealed CVRP F1 matrix."""

from __future__ import annotations

import math
from pathlib import Path
from statistics import median
from typing import Any, Mapping, Sequence

from scion.problems.cvrp.evidence import f1_contract as contract
from scion.problems.cvrp.evidence import f1_io as io
from scion.problems.cvrp.evidence import f1_preparation as preparation
from scion.protocol.stats import bootstrap_ci

REPORT_SCHEMA = "scion.cvrp_f1_ancestry_report.v1"
RECEIPT_SCHEMA = "scion.cvrp_f1_ancestry_receipt.v1"
REPORT_NAME = "cvrp_f1_ancestry_report.v1.json"
RECEIPT_NAME = "cvrp_f1_ancestry_receipt.v1.json"
_CONTRASTS = (
    ("primary", "swap_only", "cumulative"),
    ("secondary", "swap_only", "champion"),
    ("secondary", "h1_only", "champion"),
    ("secondary", "cumulative", "champion"),
    ("secondary", "cumulative", "h1_only"),
)


def close_f1_root(root: str | Path) -> dict[str, Any]:
    """Publish or byte-replay the complete or incomplete F1 closure."""

    plan = preparation.verify_f1_root(root)
    if plan.manifest.get("dry_run") is not False:
        raise contract.CvrpF1Error("F1 dry root cannot be scientifically closed")
    inventory = _execution_inventory(plan)
    complete = not any(
        inventory[key]
        for key in (
            "missing_rows",
            "extra_rows",
            "missing_interchange",
            "extra_interchange",
            "missing_streams",
            "extra_streams",
            "partial_paths",
        )
    )
    terminal = _terminal(plan)
    receipt_path = plan.root / RECEIPT_NAME
    report_path = plan.root / REPORT_NAME
    receipt_exists = receipt_path.exists()
    report_exists = report_path.exists()
    if report_exists and (not complete or terminal is None):
        raise contract.CvrpF1Error("incomplete F1 root owns a scientific report")
    if receipt_exists:
        existing = io._load_object(receipt_path, label="F1 closure receipt")
        state = existing.get("closure_state")
        if state == "incomplete" and complete and terminal is not None:
            raise contract.CvrpF1Error(
                "F1 incomplete closure is terminal and cannot become complete"
            )
        if state == "complete" and (
            not complete or terminal is None or not report_exists
        ):
            raise contract.CvrpF1Error("F1 complete closure artifact set is incomplete")
        if state not in {"complete", "incomplete"}:
            raise contract.CvrpF1Error("F1 closure receipt state is invalid")
    if not complete or terminal is None:
        receipt = _incomplete_receipt(plan, inventory, terminal)
        _publish_or_replay(receipt_path, receipt)
        if report_path.exists():
            raise contract.CvrpF1Error("incomplete F1 root owns a scientific report")
        return receipt

    rows = _load_and_verify_rows(plan)
    _verify_terminal_failure_count(terminal, rows)
    report = _build_report(plan, rows)
    report_bytes = io._canonical_pretty_bytes(report)
    receipt = {
        "schema_version": RECEIPT_SCHEMA,
        "disposition": report["disposition"],
        "closure_state": "complete",
        "manifest_sha256": plan.manifest_sha256,
        "terminal_sha256": io._sha256_file(plan.root / "terminal.json"),
        "report_name": REPORT_NAME,
        "report_sha256": io._sha256_bytes(report_bytes),
        "declared_jobs": 256,
        "observed_rows": 256,
        "typed_solver_failures": sum(row["status"] == "solver_failure" for row in rows),
        "row_identities": [
            {
                "job_id": row["job_id"],
                "sha256": io._sha256_file(plan.root / f"raw/{row['job_id']}.json"),
            }
            for row in rows
        ],
        "retry": False,
        "resume": False,
        "automatic_rerun": False,
    }
    _publish_or_replay_bytes(report_path, report_bytes)
    _publish_or_replay(receipt_path, receipt)
    return receipt


def _execution_inventory(plan: preparation.F1Plan) -> dict[str, list[str]]:
    jobs = plan.manifest["jobs"]
    expected_rows = {str(row["row_path"]) for row in jobs}
    expected_interchange = {str(row["interchange_path"]) for row in jobs}
    expected_streams = {
        str(row[key]) for row in jobs for key in ("stdout_path", "stderr_path")
    }
    observed_rows = _regular_relative_files(plan.root, "raw")
    observed_interchange = _regular_relative_files(plan.root, "interchange")
    observed_streams = _regular_relative_files(plan.root, "streams")
    all_files = _regular_relative_files(plan.root, "")
    partial = sorted(
        path
        for path in all_files
        if Path(path).name.startswith(".") or Path(path).suffix in {".partial", ".tmp"}
    )
    return {
        "missing_rows": sorted(expected_rows - observed_rows),
        "extra_rows": sorted(observed_rows - expected_rows),
        "missing_interchange": sorted(expected_interchange - observed_interchange),
        "extra_interchange": sorted(observed_interchange - expected_interchange),
        "missing_streams": sorted(expected_streams - observed_streams),
        "extra_streams": sorted(observed_streams - expected_streams),
        "partial_paths": partial,
        "observed_rows": sorted(observed_rows),
        "observed_interchange": sorted(observed_interchange),
        "observed_streams": sorted(observed_streams),
    }


def _regular_relative_files(root: Path, subdirectory: str) -> set[str]:
    base = root / subdirectory if subdirectory else root
    if not base.exists():
        return set()
    if base.is_symlink() or not base.is_dir():
        raise contract.CvrpF1Error(f"F1 execution path is not a directory: {base}")
    rows: set[str] = set()
    for path in base.rglob("*"):
        if path.is_symlink() or (not path.is_file() and not path.is_dir()):
            raise contract.CvrpF1Error(
                f"F1 execution inventory contains unsafe entry: {path}"
            )
        if path.is_file():
            rows.add(path.relative_to(root).as_posix())
    return rows


def _terminal(plan: preparation.F1Plan) -> dict[str, Any] | None:
    path = plan.root / "terminal.json"
    if not path.exists():
        return None
    marker = io._load_object(path, label="F1 terminal marker")
    expected = {
        "schema_version": contract.F1_TERMINAL_SCHEMA,
        "manifest_sha256": plan.manifest_sha256,
        "declared_jobs": 256,
        "published_rows": 256,
        "runner_complete": True,
        "retry": False,
        "resume": False,
        "automatic_rerun": False,
    }
    for key, value in expected.items():
        if marker.get(key) != value:
            raise contract.CvrpF1Error(f"F1 terminal marker drift: {key}")
    failures = marker.get("typed_solver_failures")
    if (
        not isinstance(failures, int)
        or isinstance(failures, bool)
        or not 0 <= failures <= 256
    ):
        raise contract.CvrpF1Error("F1 terminal failure count is invalid")
    return marker


def _verify_terminal_failure_count(
    terminal: Mapping[str, Any], rows: Sequence[Mapping[str, Any]]
) -> None:
    observed = sum(row.get("status") == "solver_failure" for row in rows)
    if terminal.get("typed_solver_failures") != observed:
        raise contract.CvrpF1Error(
            "F1 terminal failure count disagrees with immutable rows"
        )


def _incomplete_receipt(
    plan: preparation.F1Plan,
    inventory: Mapping[str, Sequence[str]],
    terminal: Mapping[str, Any] | None,
) -> dict[str, Any]:
    observed = list(inventory["observed_rows"])
    row_identities = [
        {
            "path": path,
            "sha256": io._sha256_file(plan.root / path),
        }
        for path in observed
    ]
    return {
        "schema_version": RECEIPT_SCHEMA,
        "disposition": "invalid_or_incomplete",
        "closure_state": "incomplete",
        "manifest_sha256": plan.manifest_sha256,
        "terminal_present": terminal is not None,
        "declared_jobs": 256,
        "observed_rows": len(observed),
        "missing_rows": list(inventory["missing_rows"]),
        "extra_rows": list(inventory["extra_rows"]),
        "missing_interchange": list(inventory["missing_interchange"]),
        "extra_interchange": list(inventory["extra_interchange"]),
        "missing_streams": list(inventory["missing_streams"]),
        "extra_streams": list(inventory["extra_streams"]),
        "partial_paths": list(inventory["partial_paths"]),
        "observed_row_identities": row_identities,
        "scientific_report_published": False,
        "retry": False,
        "resume": False,
        "automatic_rerun": False,
    }


def _load_and_verify_rows(plan: preparation.F1Plan) -> list[dict[str, Any]]:
    manifest_sha = plan.manifest_sha256
    arms = {str(row["arm"]): row for row in plan.manifest["arms"]}
    rows: list[dict[str, Any]] = []
    for job in plan.manifest["jobs"]:
        row_path = plan.root / str(job["row_path"])
        row = io._load_object(row_path, label=f"F1 row {job['job_id']}")
        expected = {
            "schema_version": contract.F1_ROW_SCHEMA,
            "manifest_sha256": manifest_sha,
            "root_id": job["root_id"],
            "job_identity_sha256": job["job_identity_sha256"],
            "job_id": job["job_id"],
            "job_ordinal": job["job_ordinal"],
            "cell_ordinal": job["cell_ordinal"],
            "stage": job["stage"],
            "arm": job["arm"],
            "arm_symbol": job["arm_symbol"],
            "schedule_position": job["schedule_position"],
            "williams_sequence": job["williams_sequence"],
            "case_path": job["case_path"],
            "case_identity_sha256": job["case_identity_sha256"],
            "solution_identity_sha256": job["solution_identity_sha256"],
            "seed": job["seed"],
            "time_limit_sec": job["time_limit_sec"],
            "command": job["command"],
            "environment": job["environment"],
            "working_directory": job["working_directory"],
            "workspace_identity_sha256": arms[str(job["arm"])][
                "runtime_identity_sha256"
            ],
        }
        for key, value in expected.items():
            if row.get(key) != value:
                raise contract.CvrpF1Error(
                    f"F1 row identity drift {job['job_id']}: {key}"
                )
        if row.get("status") not in {"validated_solver", "solver_failure"}:
            raise contract.CvrpF1Error(f"F1 row has unknown status: {job['job_id']}")
        for field, path_key in (
            ("interchange", "interchange_path"),
            ("stdout", "stdout_path"),
            ("stderr", "stderr_path"),
        ):
            evidence = row.get(field)
            if not isinstance(evidence, dict) or evidence.get("status") != "present":
                raise contract.CvrpF1Error(
                    f"F1 row omitted full {field} evidence: {job['job_id']}"
                )
            path = plan.root / str(job[path_key])
            if evidence.get("sha256") != io._sha256_file(path):
                raise contract.CvrpF1Error(
                    f"F1 row {field} identity drift: {job['job_id']}"
                )
        if row["status"] == "validated_solver":
            _validate_usable_shape(row)
        rows.append(row)
    if [row["job_ordinal"] for row in rows] != list(range(256)):
        raise contract.CvrpF1Error("F1 row order drift")
    return rows


def _validate_usable_shape(row: Mapping[str, Any]) -> None:
    validity = row.get("validity")
    objective = row.get("objective")
    if not isinstance(validity, dict) or validity.get("status") != "present":
        raise contract.CvrpF1Error("F1 validated row omitted validity")
    if not isinstance(validity.get("solution_valid"), bool) or not isinstance(
        validity.get("fleet_feasible"), bool
    ):
        raise contract.CvrpF1Error("F1 validated row validity flags are invalid")
    if not isinstance(objective, dict) or objective.get("status") != "present":
        raise contract.CvrpF1Error("F1 validated row omitted objective")
    for key in ("fleet_violation", "total_distance", "routes"):
        value = objective.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise contract.CvrpF1Error(f"F1 objective field is nonnumeric: {key}")
        if not math.isfinite(float(value)):
            raise contract.CvrpF1Error(f"F1 objective field is nonfinite: {key}")
    if (
        float(objective["fleet_violation"]) > 0
        and validity["fleet_feasible"] is not False
    ):
        raise contract.CvrpF1Error(
            "F1 fleet-violating objective cannot be marked fleet feasible"
        )


def _build_report(
    plan: preparation.F1Plan, rows: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    usable = [row for row in rows if _usable(row)]
    failures = [row for row in rows if not _usable(row)]
    contrasts = [
        _contrast(role, treatment, reference, rows)
        for role, treatment, reference in _CONTRASTS
    ]
    cumulative = next(
        item
        for item in contrasts
        if item["treatment"] == "cumulative" and item["reference"] == "champion"
    )
    consistency = {
        stage: _directional_consistency(str(cumulative["stages"][stage]["direction"]))
        for stage in ("screening", "validation")
    }
    evidence_sufficient = _scientific_evidence_sufficient(contrasts)
    disposition = _report_disposition(
        evidence_sufficient=evidence_sufficient,
        failures=failures,
    )
    return {
        "schema_version": REPORT_SCHEMA,
        "disposition": disposition,
        "scientific_role": "fixed_candidate_ancestry_diagnostic_only",
        "manifest_sha256": plan.manifest_sha256,
        "root_id": plan.manifest["root_id"],
        "population": {
            "declared_rows": 256,
            "terminal_rows": len(rows),
            "usable_rows": len(usable),
            "unusable_rows": len(failures),
            "unusable": [
                {
                    "job_id": row["job_id"],
                    "status": row["status"],
                    "reason": _unusable_reason(row),
                }
                for row in failures
            ],
        },
        "scientific_evidence": {
            "sufficient": evidence_sufficient,
            "minimum_structure": (
                "at_least_one_complete_case_and_determinate_direction_"
                "per_stage_per_contrast"
            ),
            "effect_threshold": None,
            "promotion_gate": None,
        },
        "analysis_contract": {
            "case_is_primary_unit": True,
            "improvement": "reference_distance_minus_treatment_distance",
            "equal_fleet_distance_only": True,
            "bootstrap": {
                "function": "scion.protocol.stats.bootstrap_ci",
                "n_boot": 1000,
                "alpha": 0.05,
                "seed": 42,
            },
            "combined_view_diagnostic_only": True,
            "promotion_gate": None,
        },
        "contrasts": contrasts,
        "r11c_directional_consistency": consistency,
        "heterogeneity": _heterogeneity(rows),
        "mechanism_trajectory": _mechanism_rows(rows),
        "mechanism_summary": _mechanism_summary(rows),
        "analysis_inputs": [
            {
                "job_id": row["job_id"],
                "row_sha256": io._sha256_file(plan.root / f"raw/{row['job_id']}.json"),
            }
            for row in rows
        ],
        "claims": {
            "arm_promoted": False,
            "canonical_profile_selected": False,
            "generative_claim": False,
            "b2_b3_authorized": False,
        },
    }


def _scientific_evidence_sufficient(
    contrasts: Sequence[Mapping[str, Any]],
) -> bool:
    """Require analyzable structure without inventing an effect threshold."""

    if len(contrasts) != len(_CONTRASTS):
        return False
    if any(
        set(_stages(contrast)) != {"screening", "validation"} for contrast in contrasts
    ):
        return False
    return all(
        stage.get("valid_cases", 0) > 0 and stage.get("direction") != "unknown"
        for contrast in contrasts
        for stage in _stages(contrast).values()
    )


def _directional_consistency(direction: str) -> dict[str, Any]:
    if direction == "unknown":
        return {
            "status": "missing",
            "reason": "f1_cumulative_direction_unknown",
        }
    return {"status": "present", "value": direction == "treatment_better"}


def _report_disposition(
    *, evidence_sufficient: bool, failures: Sequence[Mapping[str, Any]]
) -> str:
    if not evidence_sufficient:
        return "invalid_or_incomplete"
    return "accepted_with_declared_caveats" if failures else "accepted_diagnostic"


def _stages(contrast: Mapping[str, Any]) -> dict[str, Any]:
    value = contrast.get("stages")
    return dict(value) if isinstance(value, Mapping) else {}


def _contrast(
    role: str,
    treatment: str,
    reference: str,
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    by_key = {
        (row["stage"], row["case_path"], row["seed"], row["arm"]): row for row in rows
    }
    stages = {}
    for stage in ("screening", "validation"):
        case_results = []
        for case_path, _ in contract.F1_CASES[stage]:
            seed_results = []
            seed_wins = seed_losses = 0
            equal_fleet_deltas = []
            missing = []
            for seed in contract.F1_SEEDS[stage]:
                treatment_row = by_key[(stage, case_path, seed, treatment)]
                reference_row = by_key[(stage, case_path, seed, reference)]
                result = _paired_seed(treatment_row, reference_row)
                seed_results.append({"seed": seed, **result})
                if result["comparison"] == "treatment_win":
                    seed_wins += 1
                elif result["comparison"] == "reference_win":
                    seed_losses += 1
                if result["distance_improvement"] is not None:
                    equal_fleet_deltas.append(result["distance_improvement"])
                if result["missing_reason"] is not None:
                    missing.append({"seed": seed, "reason": result["missing_reason"]})
            if missing:
                outcome = "incomplete"
            else:
                outcome = (
                    "treatment_win"
                    if seed_wins > seed_losses
                    else "reference_win" if seed_wins < seed_losses else "tie"
                )
            case_result = {
                "case_path": case_path,
                "seed_results": seed_results,
                "case_outcome": outcome,
                "treatment_seed_wins": seed_wins,
                "reference_seed_wins": seed_losses,
                "seed_ties": sum(row["comparison"] == "tie" for row in seed_results),
                "missing_seeds": sum(
                    row["comparison"] == "missing" for row in seed_results
                ),
                "equal_fleet_distance_denominator": len(equal_fleet_deltas),
                "median_improvement": (
                    float(median(equal_fleet_deltas))
                    if equal_fleet_deltas and not missing
                    else None
                ),
                "missing_reasons": missing,
                "distance_missing_reasons": [
                    {
                        "seed": row["seed"],
                        "reason": row["distance_missing_reason"],
                    }
                    for row in seed_results
                    if row["distance_missing_reason"] is not None
                ],
            }
            case_results.append(case_result)
        stages[stage] = _stage_summary(case_results)
    combined_cases = [row for stage in stages.values() for row in stage["cases"]]
    return {
        "role": role,
        "treatment": treatment,
        "reference": reference,
        "stages": stages,
        "combined_diagnostic": _summary_values(combined_cases),
    }


def _paired_seed(
    treatment: Mapping[str, Any], reference: Mapping[str, Any]
) -> dict[str, Any]:
    if not _usable(treatment):
        return {
            "comparison": "missing",
            "distance_improvement": None,
            "equal_fleet": None,
            "missing_reason": "treatment:" + _unusable_reason(treatment),
            "distance_missing_reason": "treatment_unusable",
        }
    if not _usable(reference):
        return {
            "comparison": "missing",
            "distance_improvement": None,
            "equal_fleet": None,
            "missing_reason": "reference:" + _unusable_reason(reference),
            "distance_missing_reason": "reference_unusable",
        }
    t_obj = treatment["objective"]
    r_obj = reference["objective"]
    t_tuple = (float(t_obj["fleet_violation"]), float(t_obj["total_distance"]))
    r_tuple = (float(r_obj["fleet_violation"]), float(r_obj["total_distance"]))
    comparison = (
        "treatment_win"
        if t_tuple < r_tuple
        else "reference_win" if t_tuple > r_tuple else "tie"
    )
    equal_fleet = t_tuple[0] == r_tuple[0]
    improvement = r_tuple[1] - t_tuple[1] if equal_fleet else None
    return {
        "comparison": comparison,
        "distance_improvement": improvement,
        "equal_fleet": equal_fleet,
        "missing_reason": None,
        "distance_missing_reason": None if equal_fleet else "fleet_difference",
    }


def _stage_summary(cases: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    summary = _summary_values(cases)
    return {**summary, "cases": list(cases)}


def _summary_values(cases: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    valid = [row for row in cases if row["case_outcome"] != "incomplete"]
    eligible = [
        float(row["median_improvement"])
        for row in cases
        if row["median_improvement"] is not None
    ]
    wins = sum(row["case_outcome"] == "treatment_win" for row in cases)
    losses = sum(row["case_outcome"] == "reference_win" for row in cases)
    ties = sum(row["case_outcome"] == "tie" for row in cases)
    incomplete = sum(row["case_outcome"] == "incomplete" for row in cases)
    median_value = float(median(eligible)) if eligible else None
    bootstrap_interval = None
    if eligible:
        low, high = bootstrap_ci(eligible, n_boot=1000, alpha=0.05, seed=42)
        bootstrap_interval = [low, high]
    if not valid:
        direction = "unknown"
    elif wins > losses:
        direction = "treatment_better"
    elif wins < losses:
        direction = "reference_better"
    elif median_value is None:
        direction = "unknown"
    elif median_value > 0:
        direction = "treatment_better"
    elif median_value < 0:
        direction = "reference_better"
    else:
        direction = "tie"
    return {
        "total_cases": len(cases),
        "valid_cases": len(valid),
        "equal_fleet_cases": len(eligible),
        "bootstrap_input_count": len(eligible),
        "case_sign_counts": {
            "treatment_wins": wins,
            "reference_wins": losses,
            "ties": ties,
            "incomplete": incomplete,
        },
        "median_improvement": median_value,
        "bootstrap_ci": bootstrap_interval,
        "direction": direction,
        "missing_reasons": [
            {"case_path": row["case_path"], "reasons": row["missing_reasons"]}
            for row in cases
            if row["missing_reasons"]
        ],
    }


def _heterogeneity(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    views = (
        ("tai150a_starvation_probe", "validation", {"cvrplib/tai/tai150a.vrp"}),
        (
            "validation_60_second_large",
            "validation",
            {
                "cvrplib/tai/tai150a.vrp",
                "cvrplib/tai/tai150b.vrp",
                "cvrplib/X/X-n190-k8.vrp",
            },
        ),
        (
            "validation_45_second",
            "validation",
            {"cvrplib/X/X-n120-k6.vrp", "cvrplib/X/X-n129-k18.vrp"},
        ),
        (
            "screening_45_second",
            "screening",
            {"cvrplib/CMT/CMT4.vrp", "cvrplib/M/M-n200-k17.vrp"},
        ),
        (
            "screening_remaining_30_second",
            "screening",
            {path for path, limit in contract.F1_CASES["screening"] if limit == 30},
        ),
        (
            "validation_remaining_30_second",
            "validation",
            {path for path, limit in contract.F1_CASES["validation"] if limit == 30},
        ),
    )
    return [
        {
            "view": name,
            "stage": stage,
            "case_paths": sorted(cases),
            "inferential_claim": False,
            "rows": [
                _mechanism_row(row)
                for row in rows
                if row["stage"] == stage and row["case_path"] in cases
            ],
        }
        for name, stage, cases in views
    ]


def _mechanism_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    groups = []
    for stage in ("screening", "validation"):
        for arm in contract.F1_ARM_ORDER:
            selected = [
                row for row in rows if row["stage"] == stage and row["arm"] == arm
            ]
            swap_attempts = _typed_numeric_summary(
                selected, ("telemetry", "swap_star", "attempts")
            )
            alns_iterations = _typed_numeric_summary(
                selected, ("telemetry", "alns", "iterations")
            )
            groups.append(
                {
                    "stage": stage,
                    "arm": arm,
                    "row_count": len(selected),
                    "usable_objective_count": sum(_usable(row) for row in selected),
                    "objective_total_distance": _typed_numeric_summary(
                        selected, ("objective", "total_distance"), typed_leaf=False
                    ),
                    "swap_star_activation": {
                        "attempts": swap_attempts,
                        "accepted": _typed_numeric_summary(
                            selected, ("telemetry", "swap_star", "accepted")
                        ),
                        "activated_count": swap_attempts["positive_count"],
                        "inactive_count": swap_attempts["zero_count"],
                        "typed_missing_count": swap_attempts["typed_missing_count"],
                    },
                    "zero_alns_incidence": {
                        "iterations": alns_iterations,
                        "zero_count": alns_iterations["zero_count"],
                        "nonzero_count": alns_iterations["positive_count"],
                        "typed_missing_count": alns_iterations["typed_missing_count"],
                    },
                    "vns_occupancy_runtime_ms": {
                        "initial": _typed_numeric_summary(
                            selected,
                            ("telemetry", "phase_runtime_ms", "vns_initial"),
                        ),
                        "embedded": _typed_numeric_summary(
                            selected,
                            ("telemetry", "phase_runtime_ms", "vns_embedded"),
                        ),
                    },
                    "route_elimination_deadness": _route_elimination_deadness(
                        selected,
                        ancestry_treatment=arm in {"h1_only", "cumulative"},
                    ),
                    "scheduler_rng_path": _scheduler_rng_path_summary(selected),
                    # The frozen runtime does not emit a native throughput
                    # field.  This remains typed missing rather than deriving
                    # a new formula from iterations and wall time.
                    "alns_throughput": _typed_numeric_summary(
                        selected, ("telemetry", "alns", "throughput")
                    ),
                }
            )
    return {
        "schema_version": "scion.cvrp_f1_mechanism_summary.v1",
        "throughput_derivation": None,
        "groups": groups,
    }


def _route_elimination_deadness(
    rows: Sequence[Mapping[str, Any]], *, ancestry_treatment: bool
) -> dict[str, Any]:
    fields = {
        name: _typed_numeric_summary(rows, ("telemetry", "route_elimination", name))
        for name in (
            "selections",
            "destroy_empty",
            "repair_invocations",
            "acceptances",
            "best_updates",
            "elapsed_ms",
        )
    }
    classifications: list[str] = []
    missing_reasons: dict[str, int] = {}
    for row in rows:
        values: dict[str, float] = {}
        row_reasons: set[str] = set()
        for name in (
            "selections",
            "destroy_empty",
            "repair_invocations",
            "acceptances",
            "best_updates",
        ):
            evidence = _row_evidence(
                row,
                ("telemetry", "route_elimination", name),
                typed_leaf=True,
            )
            value = evidence.get("value")
            if (
                evidence.get("status") != "present"
                or isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
            ):
                row_reasons.add(str(evidence.get("reason") or "non_numeric_evidence"))
            else:
                values[name] = float(value)
        if row_reasons:
            reason = "+".join(sorted(row_reasons))
            missing_reasons[reason] = missing_reasons.get(reason, 0) + 1
            continue
        if values["selections"] == 0:
            classifications.append("unselected")
        elif (
            values["destroy_empty"] == values["selections"]
            and values["repair_invocations"] == 0
            and values["acceptances"] == 0
            and values["best_updates"] == 0
        ):
            classifications.append("dead")
        else:
            classifications.append("non_dead")
    return {
        "ancestry_treatment": ancestry_treatment,
        **fields,
        "dead_count": classifications.count("dead"),
        "unselected_count": classifications.count("unselected"),
        "non_dead_count": classifications.count("non_dead"),
        "typed_missing_count": len(rows) - len(classifications),
        "typed_missing_reasons": dict(sorted(missing_reasons.items())),
    }


def _scheduler_rng_path_summary(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    paths: list[str] = []
    iteration_counts: list[float] = []
    q_values: list[float] = []
    destroy_counts: dict[str, int] = {}
    repair_counts: dict[str, int] = {}
    pair_counts: dict[str, int] = {}
    missing_reasons: dict[str, int] = {}
    for row in rows:
        evidence = _row_evidence(
            row,
            ("telemetry", "alns", "iteration_trace"),
            typed_leaf=False,
        )
        trace = evidence.get("value")
        if evidence.get("status") != "present":
            reason = str(evidence.get("reason") or "typed_missing")
            missing_reasons[reason] = missing_reasons.get(reason, 0) + 1
            continue
        if not isinstance(trace, list):
            missing_reasons["malformed_iteration_trace"] = (
                missing_reasons.get("malformed_iteration_trace", 0) + 1
            )
            continue
        tokens: list[dict[str, Any]] = []
        malformed = False
        for item in trace:
            if not isinstance(item, Mapping):
                malformed = True
                break
            iteration = item.get("iteration")
            destroy = item.get("destroy_operator")
            repair = item.get("repair_operator")
            q = item.get("q")
            if (
                isinstance(iteration, bool)
                or not isinstance(iteration, int)
                or not isinstance(destroy, str)
                or not isinstance(repair, str)
                or isinstance(q, bool)
                or not isinstance(q, (int, float))
                or not math.isfinite(float(q))
            ):
                malformed = True
                break
            tokens.append(
                {
                    "iteration": iteration,
                    "destroy_operator": destroy,
                    "repair_operator": repair,
                    "q": q,
                }
            )
        if malformed:
            missing_reasons["trace_missing_scheduler_rng_fields"] = (
                missing_reasons.get("trace_missing_scheduler_rng_fields", 0) + 1
            )
            continue
        paths.append(io._canonical_sha256(tokens))
        iteration_counts.append(float(len(tokens)))
        for token in tokens:
            destroy = str(token["destroy_operator"])
            repair = str(token["repair_operator"])
            pair = destroy + "+" + repair
            destroy_counts[destroy] = destroy_counts.get(destroy, 0) + 1
            repair_counts[repair] = repair_counts.get(repair, 0) + 1
            pair_counts[pair] = pair_counts.get(pair, 0) + 1
            q_values.append(float(token["q"]))
    path_counts = {value: paths.count(value) for value in sorted(set(paths))}
    aggregate_status = "present" if paths else "missing"
    aggregate_reason = None if paths else "no_scheduler_rng_path_evidence"

    def typed_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
        if aggregate_status == "present":
            return {"status": "present", "value": dict(sorted(value.items()))}
        return {"status": "missing", "reason": aggregate_reason}

    return {
        "observable": "ordered_iteration_destroy_repair_q_path",
        "claim_boundary": "observable_scheduler_consequence_not_raw_rng_state",
        "raw_rng_state": {
            "status": "missing",
            "reason": "solver_did_not_emit_rng_state",
        },
        "present_path_count": len(paths),
        "typed_missing_count": len(rows) - len(paths),
        "typed_missing_reasons": dict(sorted(missing_reasons.items())),
        "distinct_path_count": len(path_counts) if paths else None,
        "path_sha256_counts": typed_mapping(path_counts),
        "iteration_count": _numeric_values_summary(
            iteration_counts,
            total_count=len(rows),
            missing_reasons=missing_reasons,
        ),
        "destroy_operator_counts": typed_mapping(destroy_counts),
        "repair_operator_counts": typed_mapping(repair_counts),
        "operator_pair_counts": typed_mapping(pair_counts),
        "q": _numeric_values_summary(
            q_values,
            total_count=len(q_values),
            missing_reasons={},
        ),
    }


def _numeric_values_summary(
    values: Sequence[float],
    *,
    total_count: int,
    missing_reasons: Mapping[str, int],
) -> dict[str, Any]:
    return {
        "present_count": len(values),
        "typed_missing_count": total_count - len(values),
        "typed_missing_reasons": dict(sorted(missing_reasons.items())),
        "zero_count": sum(value == 0 for value in values),
        "positive_count": sum(value > 0 for value in values),
        "negative_count": sum(value < 0 for value in values),
        "median": float(median(values)) if values else None,
        "sum": float(sum(values)) if values else None,
    }


def _typed_numeric_summary(
    rows: Sequence[Mapping[str, Any]],
    path: Sequence[str],
    *,
    typed_leaf: bool = True,
) -> dict[str, Any]:
    values: list[float] = []
    missing_reasons: dict[str, int] = {}
    for row in rows:
        evidence = _row_evidence(row, path, typed_leaf=typed_leaf)
        if evidence.get("status") != "present":
            reason = str(evidence.get("reason") or "typed_missing")
            missing_reasons[reason] = missing_reasons.get(reason, 0) + 1
            continue
        value = evidence.get("value")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            missing_reasons["non_numeric_evidence"] = (
                missing_reasons.get("non_numeric_evidence", 0) + 1
            )
            continue
        numeric = float(value)
        if not math.isfinite(numeric):
            missing_reasons["non_finite_evidence"] = (
                missing_reasons.get("non_finite_evidence", 0) + 1
            )
            continue
        values.append(numeric)
    return {
        "present_count": len(values),
        "typed_missing_count": len(rows) - len(values),
        "typed_missing_reasons": dict(sorted(missing_reasons.items())),
        "zero_count": sum(value == 0 for value in values),
        "positive_count": sum(value > 0 for value in values),
        "negative_count": sum(value < 0 for value in values),
        "median": float(median(values)) if values else None,
        "sum": float(sum(values)) if values else None,
    }


def _row_evidence(
    row: Mapping[str, Any], path: Sequence[str], *, typed_leaf: bool
) -> dict[str, Any]:
    if not _usable(row):
        return {"status": "missing", "reason": "row_unusable:" + _unusable_reason(row)}
    current: Any = row
    for key in path:
        if isinstance(current, Mapping) and current.get("status") == "missing":
            return dict(current)
        if not isinstance(current, Mapping) or key not in current:
            return {"status": "missing", "reason": "solver_did_not_emit"}
        current = current[key]
    if typed_leaf:
        if not isinstance(current, Mapping):
            return {"status": "missing", "reason": "malformed_typed_evidence"}
        return dict(current)
    return {"status": "present", "value": current}


def _mechanism_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [_mechanism_row(row) for row in rows]


def _mechanism_row(row: Mapping[str, Any]) -> dict[str, Any]:
    if not _usable(row):
        return {
            "job_id": row["job_id"],
            "stage": row["stage"],
            "case_path": row["case_path"],
            "seed": row["seed"],
            "arm": row["arm"],
            "usable": False,
            "missing_reason": _unusable_reason(row),
        }
    telemetry = row["telemetry"]
    return {
        "job_id": row["job_id"],
        "stage": row["stage"],
        "case_path": row["case_path"],
        "seed": row["seed"],
        "arm": row["arm"],
        "usable": True,
        "objective": row["objective"],
        "initial_vns_ms": telemetry["phase_runtime_ms"]["vns_initial"],
        "embedded_vns_ms": telemetry["phase_runtime_ms"]["vns_embedded"],
        "alns_core_ms": telemetry["phase_runtime_ms"]["alns_core"],
        "alns_iterations": telemetry["alns"]["iterations"],
        "alns_throughput": telemetry["alns"]["throughput"],
        "best_update_trace": telemetry["alns"]["best_update_trace"],
        "best_update_summary": telemetry["alns"]["best_update_summary"],
        "scheduler_rng_path": telemetry["alns"]["iteration_trace"],
        "acceptance_trajectory": telemetry["alns"]["acceptance_trajectory"],
        "sa_temperature_trajectory": telemetry["alns"]["sa_temperature_trajectory"],
        "swap_star": telemetry["swap_star"],
        "route_elimination": telemetry["route_elimination"],
    }


def _usable(row: Mapping[str, Any]) -> bool:
    if row.get("status") != "validated_solver":
        return False
    validity = row.get("validity")
    return bool(
        isinstance(validity, dict)
        and validity.get("solution_valid") is True
        and _objective_usable(row.get("objective"))
    )


def _objective_usable(value: Any) -> bool:
    if not isinstance(value, Mapping) or value.get("status") != "present":
        return False
    for key in ("fleet_violation", "total_distance", "routes"):
        item = value.get(key)
        if (
            isinstance(item, bool)
            or not isinstance(item, (int, float))
            or not math.isfinite(float(item))
        ):
            return False
    return True


def _unusable_reason(row: Mapping[str, Any]) -> str:
    if row.get("status") != "validated_solver":
        failure = row.get("failure")
        if isinstance(failure, dict):
            return str(failure.get("type") or "solver_failure")
        return "solver_failure"
    validity = row.get("validity")
    if isinstance(validity, dict):
        reasons = validity.get("reasons")
        if isinstance(reasons, list) and reasons:
            return "solution_invalid:" + ";".join(str(value) for value in reasons)
    if not _objective_usable(row.get("objective")):
        return "objective_missing_or_nonfinite"
    return "solution_invalid"


def _publish_or_replay(path: Path, payload: Mapping[str, Any]) -> None:
    _publish_or_replay_bytes(path, io._canonical_pretty_bytes(payload))


def _publish_or_replay_bytes(path: Path, expected: bytes) -> None:
    if path.exists():
        if path.is_symlink() or not path.is_file() or path.read_bytes() != expected:
            raise contract.CvrpF1Error(
                f"existing F1 closure artifact differs from byte replay: {path.name}"
            )
        return
    io._publish_bytes_no_replace(path, expected)


__all__ = [
    "RECEIPT_NAME",
    "RECEIPT_SCHEMA",
    "REPORT_NAME",
    "REPORT_SCHEMA",
    "close_f1_root",
]
