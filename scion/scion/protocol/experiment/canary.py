from __future__ import annotations

import os
from typing import TYPE_CHECKING

from scion.core.models import CanaryResult
from scion.runtime.audit import (
    format_runtime_audit_failure,
    runtime_audit_failure_from_result,
    runtime_audit_issue_blocks_execution,
)

if TYPE_CHECKING:
    from .facade import ExperimentProtocol


def run_canary(
    protocol: "ExperimentProtocol",
    candidate_ws: str,
    champion_ws: str,
    *,
    selected_surface: str | None = None,
) -> CanaryResult:
    """
    Canary regression check using the dedicated canary split and seeds.
    Veto-only — blocks if candidate produces infeasible solutions or crashes.

    Raises ValueError if canary split/seeds are not configured.
    """
    canary_cases = protocol.split_manager.get_canary_cases()
    canary_seeds = protocol.seed_ledger.get_canary_seeds()

    if not canary_cases:
        raise ValueError(
            "Canary split not configured: split_manifest.canary is empty. "
            "Add canary cases to split_manifest.yaml."
        )
    if not canary_seeds:
        raise ValueError(
            "Canary seeds not configured: seed_ledger.canary is empty. "
            "Add canary seeds to seed_ledger.yaml."
        )

    total_pairs = len(canary_cases) * len(canary_seeds)
    attempted_pairs = 0
    base_details = {
        "schema_version": "scion.canary_result.v1",
        "stage": "canary",
        "case_ids": list(canary_cases),
        "seed_set": list(canary_seeds),
        "total_pairs": total_pairs,
        "raw_metrics_ref": None,
        "raw_metrics_unavailable_reason": "canary_veto_before_formal_protocol",
    }
    protocol._emit_progress(
        stage="canary",
        phase="canary",
        case=None,
        seed=None,
        attempted_pairs=attempted_pairs,
        completed_pairs=0,
        total_pairs=total_pairs,
        complete=False,
    )
    for case in canary_cases:
        for seed in canary_seeds:
            attempted_pairs += 1
            pair_time_limit_sec = protocol.resolve_time_limit_sec(
                stage="canary",
                case_path=case,
            )
            candidate_case_path = protocol._resolve_case_path(
                case,
                workspace=candidate_ws,
            )
            champion_case_path = protocol._resolve_case_path(
                case,
                workspace=champion_ws,
            )
            protocol._emit_progress(
                stage="canary",
                phase="canary",
                case=case,
                seed=seed,
                time_limit_sec=pair_time_limit_sec,
                attempted_pairs=attempted_pairs,
                completed_pairs=attempted_pairs - 1,
                total_pairs=total_pairs,
                complete=False,
            )
            cand_result = protocol.runner.run_solver(
                workdir=candidate_ws,
                instance_path=candidate_case_path,
                seed=seed,
                time_limit_sec=pair_time_limit_sec,
                registry_path=os.path.join(candidate_ws, "registry.yaml"),
                selected_surface=selected_surface,
            )
            if not cand_result.success:
                protocol._emit_progress(
                    stage="canary",
                    phase="canary",
                    case=case,
                    seed=seed,
                    attempted_pairs=attempted_pairs,
                    completed_pairs=attempted_pairs - 1,
                    total_pairs=total_pairs,
                    candidate_failed_pairs=1,
                    failed_pairs=1,
                    complete=True,
                )
                return CanaryResult(
                    passed=False,
                    reason=f"Candidate solver failed on {case}: {cand_result.error_category}",
                    details=_failure_details(
                        base_details,
                        case=case,
                        seed=seed,
                        attempted_pairs=attempted_pairs,
                        candidate_result=cand_result,
                        champion_result=None,
                        failure_kind="candidate_solver_failed",
                        failure_reason=(
                            f"Candidate solver failed on {case}: "
                            f"{cand_result.error_category}"
                        ),
                    ),
                )
            cand_audit_issue = runtime_audit_failure_from_result(
                cand_result,
                problem_spec=protocol._problem_spec,
                selected_surface=selected_surface,
            )
            cand_audit_failure = (
                cand_audit_issue
                if runtime_audit_issue_blocks_execution(cand_audit_issue)
                else None
            )
            if cand_audit_failure is not None:
                protocol._emit_progress(
                    stage="canary",
                    phase="canary",
                    case=case,
                    seed=seed,
                    attempted_pairs=attempted_pairs,
                    completed_pairs=attempted_pairs - 1,
                    total_pairs=total_pairs,
                    candidate_failed_pairs=1,
                    failed_pairs=1,
                    complete=True,
                )
                return CanaryResult(
                    passed=False,
                    reason=(
                        f"Candidate runtime audit failed on {case}: "
                        f"{format_runtime_audit_failure(cand_audit_failure)}"
                    ),
                    details=_failure_details(
                        base_details,
                        case=case,
                        seed=seed,
                        attempted_pairs=attempted_pairs,
                        candidate_result=cand_result,
                        champion_result=None,
                        failure_kind="candidate_runtime_audit_failed",
                        failure_reason=(
                            "Candidate runtime audit failed on "
                            f"{case}: {format_runtime_audit_failure(cand_audit_failure)}"
                        ),
                    ),
                )

            champ_result = protocol.runner.run_solver(
                workdir=champion_ws,
                instance_path=champion_case_path,
                seed=seed,
                time_limit_sec=pair_time_limit_sec,
                registry_path=os.path.join(champion_ws, "registry.yaml"),
                selected_surface=selected_surface,
            )
            if not champ_result.success:
                # Infra issue on champion side — skip veto
                continue
            champion_audit_issue = runtime_audit_failure_from_result(champ_result)
            if runtime_audit_issue_blocks_execution(champion_audit_issue):
                # Existing champion-side runtime audit issues are not a
                # candidate veto in the canary gate; validation/frozen
                # evidence treats them as incomplete champion evidence.
                continue

            if (
                cand_result.output is not None
                and champ_result.output is not None
                and champ_result.output.feasible
                and not cand_result.output.feasible
            ):
                protocol._emit_progress(
                    stage="canary",
                    phase="canary",
                    case=case,
                    seed=seed,
                    attempted_pairs=attempted_pairs,
                    completed_pairs=attempted_pairs,
                    total_pairs=total_pairs,
                    candidate_failed_pairs=1,
                    failed_pairs=1,
                    complete=True,
                )
                return CanaryResult(
                    passed=False,
                    reason=f"Candidate infeasible on {case} (champion was feasible)",
                    details=_failure_details(
                        base_details,
                        case=case,
                        seed=seed,
                        attempted_pairs=attempted_pairs,
                        candidate_result=cand_result,
                        champion_result=champ_result,
                        failure_kind="candidate_infeasible_champion_feasible",
                        failure_reason=(
                            f"Candidate infeasible on {case} "
                            "(champion was feasible)"
                        ),
                    ),
                )

            protocol._emit_progress(
                stage="canary",
                phase="canary",
                case=case,
                seed=seed,
                attempted_pairs=attempted_pairs,
                completed_pairs=attempted_pairs,
                total_pairs=total_pairs,
                complete=attempted_pairs >= total_pairs,
            )

    return CanaryResult(
        passed=True,
        reason=None,
        details={
            **base_details,
            "passed": True,
            "attempted_pairs": attempted_pairs,
            "failure_kind": None,
            "failure_reason": None,
            "candidate_status": "passed",
            "champion_status": "not_applicable",
        },
    )


def _failure_details(
    base: dict,
    *,
    case: str,
    seed: int,
    attempted_pairs: int,
    candidate_result,
    champion_result,
    failure_kind: str,
    failure_reason: str,
) -> dict:
    return {
        **base,
        "passed": False,
        "failed_case_id": case,
        "failed_seed": seed,
        "attempted_pairs": attempted_pairs,
        "failure_kind": failure_kind,
        "failure_reason": failure_reason,
        "candidate_status": _run_status(candidate_result),
        "champion_status": (
            _run_status(champion_result)
            if champion_result is not None
            else "not_run"
        ),
        "candidate_outcome": _run_outcome(candidate_result),
        "champion_outcome": (
            _run_outcome(champion_result)
            if champion_result is not None
            else {"status": "not_run"}
        ),
    }


def _run_status(result) -> str:
    if result is None:
        return "not_run"
    if not getattr(result, "success", False):
        return str(getattr(result, "error_category", None) or "failed")
    output = getattr(result, "output", None)
    if output is not None and getattr(output, "feasible", None) is False:
        return "infeasible"
    return "success"


def _run_outcome(result) -> dict:
    if result is None:
        return {"status": "not_run"}
    output = getattr(result, "output", None)
    return {
        "status": _run_status(result),
        "success": bool(getattr(result, "success", False)),
        "exit_code": getattr(result, "exit_code", None),
        "error_category": getattr(result, "error_category", None),
        "elapsed_ms": getattr(result, "elapsed_ms", None),
        "feasible": getattr(output, "feasible", None) if output is not None else None,
        "output_path": getattr(result, "output_path", None),
    }


__all__ = ["run_canary"]
