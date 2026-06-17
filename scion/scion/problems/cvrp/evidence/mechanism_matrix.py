"""Problem-owned CVRP mechanism diagnostic matrix payload helpers.

The payloads produced here are diagnostics/report artifacts only. They may
contain CVRP family labels, BKS gaps, route-count regressions, and mechanism
names, and they must not be wired into generic DecisionFeatures.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


__all__ = [
    "CvrpMatrixCase",
    "CvrpMatrixJob",
    "CvrpMechanismSpec",
    "available_cvrp_mechanisms",
    "build_jobs",
    "build_cvrp_mechanism_matrix_manifest",
    "case_slice_for_dimension",
    "default_cvrp_mechanisms",
    "load_case_entries",
    "planned_result_for_job",
    "summarize_solver_output_for_job",
]

MATRIX_SCHEMA = "scion.cvrp_mechanism_matrix.v1"
RESULTS_SCHEMA = "scion.cvrp_mechanism_matrix_results.v1"

_DECISION_BOUNDARY_NOTE = (
    "CVRP family, slice, BKS, gap, route-regression, and mechanism diagnostics "
    "are problem-owned report fields only and must not enter generic "
    "DecisionFeatures."
)


@dataclass(frozen=True)
class CvrpMechanismSpec:
    """One no-LLM CVRP mechanism replay surface."""

    mechanism_id: str
    label: str
    mechanism_family: str
    mechanism_slice: str
    description: str
    overlays: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, Any]:
        return {
            "mechanism_id": self.mechanism_id,
            "label": self.label,
            "mechanism_family": self.mechanism_family,
            "mechanism_slice": self.mechanism_slice,
            "description": self.description,
            "overlays": list(self.overlays),
            "decision_boundary": _DECISION_BOUNDARY_NOTE,
        }


@dataclass(frozen=True)
class CvrpMatrixCase:
    """One CVRP case selected for mechanism diagnostics."""

    case_id: str
    source_path: str
    case_family: str
    case_slice: str
    dimension: int | None = None
    bks: float | None = None
    bks_routes: int | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "path": self.source_path,
            "case_family": self.case_family,
            "case_slice": self.case_slice,
            "dimension": self.dimension,
            "bks": self.bks,
            "bks_routes": self.bks_routes,
        }


@dataclass(frozen=True)
class CvrpMatrixJob:
    """One case x seed x mechanism diagnostic job."""

    job_id: str
    case: CvrpMatrixCase
    seed: int
    time_budget_sec: int
    mechanism: CvrpMechanismSpec
    output_path: str

    def to_payload(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "case": self.case.to_payload(),
            "seed": self.seed,
            "time_budget_sec": self.time_budget_sec,
            "mechanism_id": self.mechanism.mechanism_id,
            "mechanism_family": self.mechanism.mechanism_family,
            "mechanism_slice": self.mechanism.mechanism_slice,
            "output_path": self.output_path,
            "reserved_result_fields": _reserved_result_fields(),
        }


def default_cvrp_mechanisms() -> tuple[CvrpMechanismSpec, ...]:
    """Return the default CVRP-owned no-LLM mechanism surfaces."""

    return (
        CvrpMechanismSpec(
            mechanism_id="canonical_alns_vns",
            label="canonical ALNS+VNS",
            mechanism_family="canonical",
            mechanism_slice="alns_vns",
            description=(
                "Current canonical solver-design baseline: construction, ALNS "
                "destroy/repair, and bounded VNS enabled."
            ),
        ),
        CvrpMechanismSpec(
            mechanism_id="alns_only",
            label="ALNS-only",
            mechanism_family="ablation",
            mechanism_slice="alns_only",
            description=(
                "Problem-owned diagnostic ablation with VNS disabled; this is "
                "not a canonical baseline replacement."
            ),
            overlays=("config_use_vns_false",),
        ),
        CvrpMechanismSpec(
            mechanism_id="size70_two_opt_candidate",
            label="size70/two_opt candidate",
            mechanism_family="candidate_probe",
            mechanism_slice="size_le_70_two_opt",
            description=(
                "Small-case candidate probe that gates VNS to dimension <= 70 "
                "and restricts the local-search list to intra-route two-opt."
            ),
            overlays=("config_vns_threshold_70", "local_search_two_opt_only"),
        ),
    )


def available_cvrp_mechanisms() -> tuple[CvrpMechanismSpec, ...]:
    """Return all selectable CVRP no-LLM mechanisms, including focused probes."""

    return default_cvrp_mechanisms() + (
        CvrpMechanismSpec(
            mechanism_id="initial_vns_disabled",
            label="initial VNS disabled",
            mechanism_family="diagnostic_probe",
            mechanism_slice="disable_initial_vns",
            description=(
                "Focused scheduler diagnostic that keeps embedded VNS enabled "
                "but disables the initial VNS phase."
            ),
            overlays=("config_disable_initial_vns",),
        ),
        CvrpMechanismSpec(
            mechanism_id="embedded_vns_disabled",
            label="embedded VNS disabled",
            mechanism_family="diagnostic_probe",
            mechanism_slice="disable_embedded_vns",
            description=(
                "Focused scheduler diagnostic that keeps initial VNS enabled "
                "but disables VNS inside ALNS candidate evaluation."
            ),
            overlays=("config_disable_embedded_vns",),
        ),
        CvrpMechanismSpec(
            mechanism_id="pure_alns_no_polish",
            label="pure ALNS without local-search polish",
            mechanism_family="diagnostic_probe",
            mechanism_slice="pure_alns_no_polish",
            description=(
                "Focused diagnostic with VNS disabled and the size70/two-opt "
                "fallback disabled, separating ALNS from cheap local polish."
            ),
            overlays=("config_use_vns_false", "config_disable_size70_two_opt"),
        ),
    )


def load_case_entries(
    manifest_path: str | Path,
    *,
    case_limit: int | None = None,
    case_id_filter: Sequence[str] = (),
    family_filter: Sequence[str] = (),
    slice_filter: Sequence[str] = (),
) -> tuple[CvrpMatrixCase, ...]:
    """Load matrix cases from an existing CVRP case manifest JSON."""

    path = Path(manifest_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("CVRP case manifest must be a JSON object")
    cases_payload = payload.get("cases")
    if not isinstance(cases_payload, list):
        raise ValueError("CVRP case manifest must contain a cases list")

    case_id_allow = {str(item) for item in case_id_filter if str(item).strip()}
    family_allow = {str(item) for item in family_filter if str(item).strip()}
    slice_allow = {str(item) for item in slice_filter if str(item).strip()}
    cases: list[CvrpMatrixCase] = []
    for item in cases_payload:
        if not isinstance(item, dict):
            raise ValueError("CVRP case entries must be JSON objects")
        case = _case_from_payload(item)
        if case_id_allow and case.case_id not in case_id_allow:
            continue
        if family_allow and case.case_family not in family_allow:
            continue
        if slice_allow and case.case_slice not in slice_allow:
            continue
        cases.append(case)
        if case_limit is not None and len(cases) >= case_limit:
            break
    if not cases:
        raise ValueError("CVRP mechanism matrix selected no cases")
    return tuple(cases)


def build_cvrp_mechanism_matrix_manifest(
    *,
    cases: Sequence[CvrpMatrixCase],
    mechanisms: Sequence[CvrpMechanismSpec],
    seeds: Sequence[int],
    time_budget_sec: int,
    output_dir: str | Path,
    repo_root: str | Path,
    workspace: str | Path,
    data_root: str | Path,
    python: str,
    selected_surface: str,
    dry_run: bool,
) -> dict[str, Any]:
    """Build a deterministic problem-owned matrix manifest payload."""

    jobs = build_jobs(
        cases=cases,
        mechanisms=mechanisms,
        seeds=seeds,
        time_budget_sec=time_budget_sec,
        output_dir=output_dir,
    )
    return {
        "schema_version": MATRIX_SCHEMA,
        "problem_id": "cvrp",
        "dry_run": bool(dry_run),
        "repo_root": str(repo_root),
        "workspace": str(workspace),
        "data_root": str(data_root),
        "python": str(python),
        "selected_surface": str(selected_surface),
        "time_budget_sec": int(time_budget_sec),
        "diagnostic_policy": {
            "decision_boundary": _DECISION_BOUNDARY_NOTE,
            "bks_gap_usage": "problem_owned_diagnostics_report_only",
            "generic_decision_inputs_changed": False,
        },
        "mechanisms": [mechanism.to_payload() for mechanism in mechanisms],
        "cases": [case.to_payload() for case in cases],
        "seeds": [int(seed) for seed in seeds],
        "jobs": [job.to_payload() for job in jobs],
    }


def build_jobs(
    *,
    cases: Sequence[CvrpMatrixCase],
    mechanisms: Sequence[CvrpMechanismSpec],
    seeds: Sequence[int],
    time_budget_sec: int,
    output_dir: str | Path,
) -> tuple[CvrpMatrixJob, ...]:
    output_root = Path(output_dir) / "raw"
    jobs: list[CvrpMatrixJob] = []
    for case in cases:
        for seed in seeds:
            for mechanism in mechanisms:
                job_id = _job_id(case, seed=seed, mechanism_id=mechanism.mechanism_id)
                jobs.append(
                    CvrpMatrixJob(
                        job_id=job_id,
                        case=case,
                        seed=int(seed),
                        time_budget_sec=int(time_budget_sec),
                        mechanism=mechanism,
                        output_path=str(output_root / f"{job_id}.json"),
                    )
                )
    return tuple(jobs)


def planned_result_for_job(job: CvrpMatrixJob) -> dict[str, Any]:
    """Return a dry-run result row with all reserved diagnostics present."""

    return {
        "schema_version": RESULTS_SCHEMA,
        "job_id": job.job_id,
        "status": "planned",
        "case": job.case.to_payload(),
        "seed": job.seed,
        "time_budget_sec": job.time_budget_sec,
        "mechanism_id": job.mechanism.mechanism_id,
        "mechanism_family": job.mechanism.mechanism_family,
        "mechanism_slice": job.mechanism.mechanism_slice,
        "output_path": job.output_path,
        "quality": _empty_quality(job),
        "route_fleet_regression_flags": _empty_regression_flags(),
        "accepted_moves": _empty_accepted_moves(),
        "best_update_telemetry": _empty_best_update(),
        "phase_telemetry": _empty_phase_telemetry(),
        "runtime_phase_split": _empty_runtime_phase_split(),
        "decision_boundary": _DECISION_BOUNDARY_NOTE,
    }


def summarize_solver_output_for_job(
    raw: Mapping[str, Any],
    *,
    job: CvrpMatrixJob,
    reference: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Summarize one solver JSON output into the matrix result schema."""

    objective = _dict_or_empty(raw.get("objective"))
    runtime = _dict_or_empty(raw.get("runtime"))
    total_distance = _float_or_none(
        runtime.get("solver_algorithm_total_distance")
        or objective.get("total_distance")
    )
    route_count = _int_or_none(
        runtime.get("solver_algorithm_solution_routes") or objective.get("routes")
    )
    fleet_violation = _float_or_none(
        runtime.get("solver_algorithm_fleet_violation")
        or objective.get("fleet_violation")
    )
    reference_quality = _dict_or_empty(
        reference.get("quality") if isinstance(reference, Mapping) else None
    )
    reference_distance = _float_or_none(reference_quality.get("total_distance"))
    reference_routes = _int_or_none(reference_quality.get("route_count"))
    reference_fleet = _float_or_none(reference_quality.get("fleet_violation"))
    quality_delta_vs_reference = (
        None
        if total_distance is None or reference_distance is None
        else total_distance - reference_distance
    )

    phase_runtime = _dict_ints(runtime.get("solver_algorithm_phase_runtime_ms"))
    phase_runtime_total = sum(phase_runtime.values())
    best_update_summary = _dict_or_none(
        runtime.get("solver_algorithm_best_update_summary")
    )
    objective_probes = _list_or_empty(
        runtime.get("solver_algorithm_objective_probes")
    )
    alns_iteration_trace = _list_or_empty(
        runtime.get("solver_algorithm_alns_iteration_trace")
    )
    actionability = _dict_or_none(
        runtime.get("solver_algorithm_actionability_summary")
    )

    return {
        "schema_version": RESULTS_SCHEMA,
        "job_id": job.job_id,
        "status": "completed",
        "case": job.case.to_payload(),
        "seed": job.seed,
        "time_budget_sec": job.time_budget_sec,
        "mechanism_id": job.mechanism.mechanism_id,
        "mechanism_family": job.mechanism.mechanism_family,
        "mechanism_slice": job.mechanism.mechanism_slice,
        "output_path": job.output_path,
        "quality": {
            "objective": objective,
            "total_distance": total_distance,
            "bks": job.case.bks,
            "bks_gap_pct": _gap_pct(total_distance, job.case.bks),
            "quality_delta_total_distance_vs_reference": quality_delta_vs_reference,
            "quality_improvement_total_distance_vs_reference": (
                None
                if quality_delta_vs_reference is None
                else -quality_delta_vs_reference
            ),
            "route_count": route_count,
            "bks_routes": job.case.bks_routes,
            "fleet_violation": fleet_violation,
        },
        "route_fleet_regression_flags": {
            "route_count_exceeds_bks_routes": (
                None
                if route_count is None or job.case.bks_routes is None
                else route_count > job.case.bks_routes
            ),
            "fleet_violation_positive": (
                None if fleet_violation is None else fleet_violation > 0.0
            ),
            "route_count_regressed_vs_reference": (
                None
                if route_count is None or reference_routes is None
                else route_count > reference_routes
            ),
            "fleet_regressed_vs_reference": (
                None
                if fleet_violation is None or reference_fleet is None
                else fleet_violation > reference_fleet
            ),
        },
        "accepted_moves": {
            "total": _int_or_zero(runtime.get("solver_algorithm_accepted_moves")),
            "move_attempts": _int_or_zero(runtime.get("solver_algorithm_move_attempts")),
            "improving_moves": _int_or_zero(
                runtime.get("solver_algorithm_improving_moves")
            ),
            "neutral_accepted_moves": _int_or_zero(
                runtime.get("solver_algorithm_neutral_accepted_moves")
            ),
            "by_phase": _dict_ints(
                runtime.get("solver_algorithm_phase_accepted_moves")
            ),
        },
        "best_update_telemetry": {
            "best_delta": _float_or_zero(runtime.get("solver_algorithm_best_delta")),
            "best_update_count": (
                _int_or_zero(best_update_summary.get("best_update_count"))
                if best_update_summary
                else _int_or_zero(runtime.get("solver_algorithm_best_update_count"))
            ),
            "best_update_summary": best_update_summary,
            "best_update_trace": _list_or_empty(
                runtime.get("solver_algorithm_best_update_trace")
            ),
        },
        "phase_telemetry": {
            "phase_move_attempts": _dict_ints(
                runtime.get("solver_algorithm_phase_move_attempts")
            ),
            "phase_accepted_moves": _dict_ints(
                runtime.get("solver_algorithm_phase_accepted_moves")
            ),
            "phase_delta_sum": _dict_floats(
                runtime.get("solver_algorithm_phase_delta_sum")
            ),
            "phase_best_delta": _dict_floats(
                runtime.get("solver_algorithm_phase_best_delta")
            ),
            "phase_improvement_counts": _dict_ints(
                runtime.get("solver_algorithm_phase_improvement_counts")
            ),
            "objective_probes": objective_probes,
            "alns_iteration_trace": alns_iteration_trace,
            "actionability_summary": actionability,
        },
        "runtime_phase_split": {
            "runtime_elapsed_sec": _float_or_none(runtime.get("elapsed_s")),
            "solver_algorithm_elapsed_ms": _int_or_none(
                runtime.get("solver_algorithm_elapsed_ms")
            ),
            "solver_algorithm_stop_reason": runtime.get(
                "solver_algorithm_stop_reason"
            ),
            "solver_algorithm_runtime_budget_hit": runtime.get(
                "solver_algorithm_runtime_budget_hit"
            ),
            "phase_runtime_ms": phase_runtime,
            "phase_runtime_fraction": _runtime_fractions(phase_runtime),
            "phase_runtime_total_ms": phase_runtime_total,
        },
        "decision_boundary": _DECISION_BOUNDARY_NOTE,
    }


def case_slice_for_dimension(dimension: int | None) -> str:
    """Return a stable size slice label for CVRP diagnostics."""

    if dimension is None:
        return "size_unknown"
    if dimension <= 70:
        return "size_le_70"
    if dimension <= 200:
        return "size_71_200"
    if dimension <= 600:
        return "size_201_600"
    return "size_gt_600"


def _case_from_payload(payload: Mapping[str, Any]) -> CvrpMatrixCase:
    case_id = str(payload.get("case_id") or "").strip()
    source_path = str(payload.get("source_path") or payload.get("path") or "").strip()
    if not case_id:
        case_id = Path(source_path).stem
    if not case_id or not source_path:
        raise ValueError("CVRP matrix cases require case_id and source_path")
    dimension = _int_or_none(payload.get("dimension"))
    case_family = str(payload.get("subset") or _family_from_path(source_path)).strip()
    if not case_family:
        case_family = "unknown"
    return CvrpMatrixCase(
        case_id=case_id,
        source_path=source_path,
        case_family=case_family,
        case_slice=case_slice_for_dimension(dimension),
        dimension=dimension,
        bks=_float_or_none(payload.get("bks")),
        bks_routes=_int_or_none(payload.get("bks_routes")),
    )


def _family_from_path(path: str) -> str:
    parts = Path(path).parts
    if len(parts) >= 3 and parts[-3] == "cvrplib":
        return parts[-2]
    if len(parts) >= 2:
        return parts[-2]
    return ""


def _job_id(case: CvrpMatrixCase, *, seed: int, mechanism_id: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", case.case_id).strip(".-_")
    family = re.sub(r"[^A-Za-z0-9._-]+", "-", case.case_family).strip(".-_")
    slice_id = re.sub(r"[^A-Za-z0-9._-]+", "-", case.case_slice).strip(".-_")
    return f"{family}_{slice_id}_{stem}_seed{int(seed)}_{mechanism_id}"


def _reserved_result_fields() -> dict[str, Any]:
    return {
        "quality": [
            "total_distance",
            "bks",
            "bks_gap_pct",
            "quality_delta_total_distance_vs_reference",
            "quality_improvement_total_distance_vs_reference",
        ],
        "route_fleet_regression_flags": [
            "route_count_exceeds_bks_routes",
            "fleet_violation_positive",
            "route_count_regressed_vs_reference",
            "fleet_regressed_vs_reference",
        ],
        "accepted_moves": [
            "total",
            "move_attempts",
            "improving_moves",
            "neutral_accepted_moves",
            "by_phase",
        ],
        "best_update_telemetry": [
            "best_delta",
            "best_update_count",
            "best_update_summary",
            "best_update_trace",
        ],
        "phase_telemetry": [
            "phase_move_attempts",
            "phase_accepted_moves",
            "phase_delta_sum",
            "phase_best_delta",
            "phase_improvement_counts",
            "objective_probes",
            "alns_iteration_trace",
            "actionability_summary",
        ],
        "runtime_phase_split": [
            "runtime_elapsed_sec",
            "solver_algorithm_elapsed_ms",
            "solver_algorithm_stop_reason",
            "solver_algorithm_runtime_budget_hit",
            "phase_runtime_ms",
            "phase_runtime_fraction",
        ],
    }


def _empty_quality(job: CvrpMatrixJob) -> dict[str, Any]:
    return {
        "objective": None,
        "total_distance": None,
        "bks": job.case.bks,
        "bks_gap_pct": None,
        "quality_delta_total_distance_vs_reference": None,
        "quality_improvement_total_distance_vs_reference": None,
        "route_count": None,
        "bks_routes": job.case.bks_routes,
        "fleet_violation": None,
    }


def _empty_regression_flags() -> dict[str, Any]:
    return {
        "route_count_exceeds_bks_routes": None,
        "fleet_violation_positive": None,
        "route_count_regressed_vs_reference": None,
        "fleet_regressed_vs_reference": None,
    }


def _empty_accepted_moves() -> dict[str, Any]:
    return {
        "total": None,
        "move_attempts": None,
        "improving_moves": None,
        "neutral_accepted_moves": None,
        "by_phase": {},
    }


def _empty_best_update() -> dict[str, Any]:
    return {
        "best_delta": None,
        "best_update_count": None,
        "best_update_summary": None,
        "best_update_trace": [],
    }


def _empty_phase_telemetry() -> dict[str, Any]:
    return {
        "phase_move_attempts": {},
        "phase_accepted_moves": {},
        "phase_delta_sum": {},
        "phase_best_delta": {},
        "phase_improvement_counts": {},
        "objective_probes": [],
        "alns_iteration_trace": [],
        "actionability_summary": None,
    }


def _empty_runtime_phase_split() -> dict[str, Any]:
    return {
        "runtime_elapsed_sec": None,
        "solver_algorithm_elapsed_ms": None,
        "solver_algorithm_stop_reason": None,
        "solver_algorithm_runtime_budget_hit": None,
        "phase_runtime_ms": {},
        "phase_runtime_fraction": {},
        "phase_runtime_total_ms": 0,
    }


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _dict_or_none(value: Any) -> dict[str, Any] | None:
    return dict(value) if isinstance(value, Mapping) else None


def _list_or_empty(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _dict_ints(value: Any) -> dict[str, int]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): _int_or_zero(item) for key, item in value.items()}


def _dict_floats(value: Any) -> dict[str, float]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): _float_or_zero(item) for key, item in value.items()}


def _runtime_fractions(values: Mapping[str, int]) -> dict[str, float]:
    total = sum(max(0, int(value)) for value in values.values())
    if total <= 0:
        return {}
    return {
        str(key): max(0, int(value)) / float(total)
        for key, value in values.items()
    }


def _gap_pct(distance: float | None, bks: float | None) -> float | None:
    if distance is None or bks is None or bks <= 0:
        return None
    return 100.0 * (float(distance) - float(bks)) / float(bks)


def _float_or_none(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _float_or_zero(value: Any) -> float:
    parsed = _float_or_none(value)
    return 0.0 if parsed is None else parsed


def _int_or_none(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _int_or_zero(value: Any) -> int:
    parsed = _int_or_none(value)
    return 0 if parsed is None else parsed
