"""Runner-backed CVRP final evaluation service.

This module executes two workspaces on the same CVRP case/seed set and converts
the checked outputs into final-quality records. It does not mutate campaign
state and does not make promotion decisions.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping, Sequence

from scion.evidence.cvrp_package import CvrpEvidencePackageResult
from scion.evidence.final_quality import (
    FinalQualityConfig,
    FinalQualityPackage,
    QualityCaseRecord,
    build_final_quality_package,
    write_final_quality_package,
)
from scion.runtime.audit import format_runtime_audit_failure, runtime_audit_failure_from_raw

if TYPE_CHECKING:
    from scion.core.models import RunResult
    from scion.problem.contracts import CheckReport, ProblemAdapter
    from scion.runtime.runner import Runner


__all__ = [
    "CvrpFinalEvaluationConfig",
    "CvrpSideResult",
    "build_cvrp_final_evidence_package",
    "evaluate_cvrp_final_quality_records",
    "write_cvrp_final_evidence_package",
]


@dataclass(frozen=True)
class CvrpFinalEvaluationConfig:
    """Configuration for paired runner-backed CVRP final evaluation."""

    campaign_id: str
    baseline_workspace: str | Path
    candidate_workspace: str | Path
    case_paths: Sequence[str | Path]
    seeds: Sequence[int]
    time_limit_sec: int
    problem_id: str = "cvrp"
    baseline_label: str = "baseline"
    candidate_label: str = "candidate"
    runtime_regression_threshold: float = 2.0
    objective_tolerance: float = 1e-9
    baseline_registry_path: str | Path | None = None
    candidate_registry_path: str | Path | None = None
    output_dir: str | Path | None = None


@dataclass(frozen=True)
class CvrpSideResult:
    """Checked result for one workspace on one CVRP case/seed pair."""

    status: str
    elapsed_ms: float | None = None
    cost: float | None = None
    routes: int | None = None
    bks: float | None = None
    bks_routes: int | None = None
    route_gap: int | None = None
    gap_pct: float | None = None
    feasible: bool | None = None
    benchmark_feasible: bool | None = None
    error_category: str | None = None
    detail: str | None = None


def evaluate_cvrp_final_quality_records(
    *,
    config: CvrpFinalEvaluationConfig,
    runner: "Runner",
    adapter: "ProblemAdapter",
) -> tuple[QualityCaseRecord, ...]:
    """Run baseline/candidate workspaces and return final-quality records."""

    _validate_config(config)
    records: list[QualityCaseRecord] = []

    for case_path in config.case_paths:
        case_path_str = str(case_path)
        for seed in config.seeds:
            seed_int = _coerce_seed(seed)
            try:
                instance = adapter.load_instance(case_path_str)
            except Exception as exc:
                side = _side_error("error", "load_instance", str(exc))
                records.append(
                    _quality_record(
                        case_id=Path(case_path_str).stem,
                        seed=seed_int,
                        baseline=side,
                        candidate=side,
                    )
                )
                continue

            baseline = _evaluate_side(
                workspace=config.baseline_workspace,
                registry_path=config.baseline_registry_path,
                case_path=case_path_str,
                seed=seed_int,
                time_limit_sec=config.time_limit_sec,
                runner=runner,
                adapter=adapter,
                instance=instance,
            )
            candidate = _evaluate_side(
                workspace=config.candidate_workspace,
                registry_path=config.candidate_registry_path,
                case_path=case_path_str,
                seed=seed_int,
                time_limit_sec=config.time_limit_sec,
                runner=runner,
                adapter=adapter,
                instance=instance,
            )
            records.append(
                _quality_record(
                    case_id=_case_id(instance, case_path_str),
                    seed=seed_int,
                    baseline=baseline,
                    candidate=candidate,
                )
            )

    return tuple(records)


def build_cvrp_final_evidence_package(
    *,
    config: CvrpFinalEvaluationConfig,
    runner: "Runner",
    adapter: "ProblemAdapter",
) -> FinalQualityPackage:
    """Run paired final evaluation and build an in-memory evidence package."""

    records = evaluate_cvrp_final_quality_records(
        config=config,
        runner=runner,
        adapter=adapter,
    )
    return build_final_quality_package(records, _final_quality_config(config))


def write_cvrp_final_evidence_package(
    *,
    config: CvrpFinalEvaluationConfig,
    runner: "Runner",
    adapter: "ProblemAdapter",
    output_dir: str | Path | None = None,
) -> CvrpEvidencePackageResult:
    """Run paired final evaluation, write evidence artifacts, and return refs."""

    resolved_output_dir = output_dir if output_dir is not None else config.output_dir
    if resolved_output_dir is None:
        raise ValueError("output_dir is required to write a CVRP final evidence package")

    package = build_cvrp_final_evidence_package(
        config=config,
        runner=runner,
        adapter=adapter,
    )
    artifacts = write_final_quality_package(package, resolved_output_dir)
    return CvrpEvidencePackageResult(package=package, artifacts=artifacts)


def _evaluate_side(
    *,
    workspace: str | Path,
    registry_path: str | Path | None,
    case_path: str,
    seed: int,
    time_limit_sec: int,
    runner: "Runner",
    adapter: "ProblemAdapter",
    instance: Any,
) -> CvrpSideResult:
    try:
        result = runner.run_solver(
            workdir=str(workspace),
            instance_path=case_path,
            seed=seed,
            time_limit_sec=time_limit_sec,
            registry_path=_registry_path(registry_path),
        )
    except Exception as exc:
        return _side_error("crash", "runner_exception", str(exc))

    if not result.success:
        return _failed_run_side(result)

    raw_output, output_error = _load_raw_solver_output(result)
    if output_error is not None:
        return CvrpSideResult(
            status="error",
            elapsed_ms=result.elapsed_ms,
            error_category=output_error[0],
            detail=output_error[1],
        )

    audit_failure = runtime_audit_failure_from_raw(raw_output)
    if audit_failure is not None:
        return CvrpSideResult(
            status="error",
            elapsed_ms=result.elapsed_ms,
            error_category=str(audit_failure["error_category"]),
            detail=format_runtime_audit_failure(audit_failure),
        )

    try:
        artifact = adapter.deserialize_solver_output(raw_output, instance)
    except Exception as exc:
        return CvrpSideResult(
            status="error",
            elapsed_ms=result.elapsed_ms,
            error_category="deserialize",
            detail=str(exc),
        )

    try:
        consistency = adapter.check_solution_consistency(artifact, instance)
    except Exception as exc:
        return CvrpSideResult(
            status="error",
            elapsed_ms=result.elapsed_ms,
            error_category="consistency_check",
            detail=str(exc),
        )

    if not consistency.passed:
        return CvrpSideResult(
            status=_status_for_consistency_failure(consistency),
            elapsed_ms=result.elapsed_ms,
            error_category="consistency",
            detail="; ".join(consistency.reasons),
        )

    try:
        objective = adapter.recompute_objective(artifact, instance)
    except Exception as exc:
        return CvrpSideResult(
            status="error",
            elapsed_ms=result.elapsed_ms,
            error_category="objective",
            detail=str(exc),
        )

    try:
        feasibility = adapter.check_feasibility(artifact, instance)
    except Exception as exc:
        return CvrpSideResult(
            status="error",
            elapsed_ms=result.elapsed_ms,
            error_category="feasibility_check",
            detail=str(exc),
        )

    cost = _float_value(objective.get("total_distance", objective.get("cost")))
    routes = _int_value(objective.get("routes"))
    if routes is None:
        routes = _routes_from_artifact(artifact)
    bks = _float_value(getattr(instance, "bks", None))
    bks_routes = _int_value(getattr(instance, "bks_routes", None))
    feasible = bool(feasibility.passed)

    side = _side_from_objective(
        status="ok" if feasible else "infeasible",
        elapsed_ms=result.elapsed_ms,
        cost=cost,
        routes=routes,
        bks=bks,
        bks_routes=bks_routes,
        feasible=feasible,
        error_category=None if feasible else "infeasible",
        detail=None if feasible else "; ".join(feasibility.reasons),
    )
    return side


def _side_from_objective(
    *,
    status: str,
    elapsed_ms: float | None,
    cost: float | None,
    routes: int | None,
    bks: float | None,
    bks_routes: int | None,
    feasible: bool | None,
    error_category: str | None,
    detail: str | None,
) -> CvrpSideResult:
    route_gap = None if routes is None or bks_routes is None else routes - bks_routes
    gap_pct = None if cost is None or bks in (None, 0) else (cost - bks) / bks * 100.0
    benchmark_feasible = None
    if bks_routes is not None and feasible is not None and routes is not None:
        benchmark_feasible = bool(feasible and routes <= bks_routes)
    return CvrpSideResult(
        status=status,
        elapsed_ms=elapsed_ms,
        cost=cost,
        routes=routes,
        bks=bks,
        bks_routes=bks_routes,
        route_gap=route_gap,
        gap_pct=gap_pct,
        feasible=feasible,
        benchmark_feasible=benchmark_feasible,
        error_category=error_category,
        detail=detail,
    )


def _quality_record(
    *,
    case_id: str,
    seed: int,
    baseline: CvrpSideResult,
    candidate: CvrpSideResult,
) -> QualityCaseRecord:
    return QualityCaseRecord(
        case_id=case_id,
        seed=seed,
        baseline_status=baseline.status,
        candidate_status=candidate.status,
        comparison=None,
        decisive_metric="cost",
        baseline_objective=baseline.cost,
        candidate_objective=candidate.cost,
        baseline_elapsed_ms=baseline.elapsed_ms,
        candidate_elapsed_ms=candidate.elapsed_ms,
        error_category=_merged_error(baseline.error_category, candidate.error_category),
        baseline_cost=baseline.cost,
        candidate_cost=candidate.cost,
        bks=baseline.bks if baseline.bks is not None else candidate.bks,
        baseline_gap_pct=baseline.gap_pct,
        candidate_gap_pct=candidate.gap_pct,
        baseline_routes=baseline.routes,
        candidate_routes=candidate.routes,
        bks_routes=(
            baseline.bks_routes
            if baseline.bks_routes is not None
            else candidate.bks_routes
        ),
        baseline_route_gap=baseline.route_gap,
        candidate_route_gap=candidate.route_gap,
        baseline_feasible=baseline.feasible,
        candidate_feasible=candidate.feasible,
        baseline_benchmark_feasible=baseline.benchmark_feasible,
        candidate_benchmark_feasible=candidate.benchmark_feasible,
    )


def _failed_run_side(result: "RunResult") -> CvrpSideResult:
    status = _run_failure_status(result)
    return CvrpSideResult(
        status=status,
        elapsed_ms=result.elapsed_ms,
        error_category=result.error_category or status,
        detail=(result.stderr or result.stdout or "")[:1000] or None,
    )


def _load_raw_solver_output(
    result: "RunResult",
) -> tuple[Mapping[str, Any], tuple[str, str] | None]:
    if result.output_path:
        try:
            with Path(result.output_path).open(encoding="utf-8") as handle:
                raw = json.load(handle)
        except FileNotFoundError:
            return {}, ("missing_output", f"output file not found: {result.output_path}")
        except json.JSONDecodeError as exc:
            return {}, ("invalid_output", str(exc))
        except OSError as exc:
            return {}, ("invalid_output", str(exc))
        if not isinstance(raw, Mapping):
            return {}, ("invalid_output", "solver output JSON must be a mapping")
        return raw, None

    raw_from_output = _raw_mapping_from_output_object(result.output)
    if raw_from_output is None:
        return {}, ("missing_output", "solver produced no output mapping")
    return raw_from_output, None


def _raw_mapping_from_output_object(output: Any) -> Mapping[str, Any] | None:
    if output is None:
        return None
    if isinstance(output, Mapping):
        return output
    raw_output = getattr(output, "raw_output", None)
    if isinstance(raw_output, Mapping):
        return raw_output

    payload: dict[str, Any] = {}
    for attr in ("routes", "solution", "objective", "feasible", "runtime"):
        if hasattr(output, attr):
            payload[attr] = getattr(output, attr)
    return payload or None


def _run_failure_status(result: "RunResult") -> str:
    category = (result.error_category or "").strip().lower()
    if category in {"timeout", "crash", "oom", "error"}:
        return category
    if category:
        return "error"
    if result.exit_code != 0:
        return "crash"
    return "error"


def _status_for_consistency_failure(report: "CheckReport") -> str:
    for reason in report.reasons:
        if reason.startswith("objective field"):
            return "error"
    return "infeasible"


def _side_error(status: str, category: str, detail: str) -> CvrpSideResult:
    return CvrpSideResult(
        status=status,
        error_category=category,
        detail=detail,
    )


def _final_quality_config(config: CvrpFinalEvaluationConfig) -> FinalQualityConfig:
    return FinalQualityConfig(
        problem_id=config.problem_id,
        campaign_id=config.campaign_id,
        baseline_label=config.baseline_label,
        candidate_label=config.candidate_label,
        runtime_regression_threshold=config.runtime_regression_threshold,
        objective_sense="minimize",
        primary_metric="cost",
        objective_tolerance=config.objective_tolerance,
    )


def _validate_config(config: CvrpFinalEvaluationConfig) -> None:
    if not config.campaign_id:
        raise ValueError("campaign_id is required")
    if not config.case_paths:
        raise ValueError("case_paths must not be empty")
    if not config.seeds:
        raise ValueError("seeds must not be empty")
    if config.time_limit_sec <= 0:
        raise ValueError("time_limit_sec must be positive")


def _registry_path(explicit: str | Path | None) -> str:
    return "" if explicit is None else str(explicit)


def _case_id(instance: Any, case_path: str) -> str:
    name = getattr(instance, "name", None)
    if isinstance(name, str) and name.strip():
        return name.strip()
    return Path(case_path).stem


def _coerce_seed(seed: int) -> int:
    return int(seed)


def _float_value(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _int_value(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _routes_from_artifact(artifact: Any) -> int | None:
    solution = getattr(artifact, "normalized_solution", None)
    routes = getattr(solution, "routes", None)
    if routes is None:
        return None
    try:
        return len(routes)
    except TypeError:
        return None


def _merged_error(
    baseline_error: str | None,
    candidate_error: str | None,
) -> str | None:
    if baseline_error and candidate_error and baseline_error != candidate_error:
        return f"baseline:{baseline_error};candidate:{candidate_error}"
    return candidate_error or baseline_error
