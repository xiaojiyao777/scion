"""Shared candidate canary execution for runtime verification checks."""
from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Mapping

from scion.core.models import RunResult
from scion.runtime.runner import Runner, run_solver_with_surface


SHARED_CANARY_SEED = 77


@dataclass(frozen=True)
class CandidateCanaryExecution:
    """One solver execution shared by V5/V6/V7 and the first V8 sample."""

    case_path: str
    seed: int
    result: RunResult | None
    raw_output: Mapping[str, Any] | None
    error: str = ""


def run_candidate_canary(
    runner: Runner,
    *,
    candidate_workspace: str,
    case_path: str,
    registry_path: str,
    selected_surface: str | None,
    runtime_time_limit_sec: int | float,
) -> CandidateCanaryExecution:
    """Execute and parse the candidate canary exactly once."""

    try:
        result = run_solver_with_surface(
            runner,
            workdir=candidate_workspace,
            instance_path=case_path,
            seed=SHARED_CANARY_SEED,
            time_limit_sec=runtime_time_limit_sec,
            registry_path=registry_path,
            selected_surface=selected_surface,
        )
    except Exception as exc:
        return CandidateCanaryExecution(
            case_path=case_path,
            seed=SHARED_CANARY_SEED,
            result=None,
            raw_output=None,
            error=str(exc),
        )

    if not result.success:
        detail = result.stderr.strip() if result.stderr else ""
        return CandidateCanaryExecution(
            case_path=case_path,
            seed=SHARED_CANARY_SEED,
            result=result,
            raw_output=None,
            error=detail or str(result.error_category or "solver failed"),
        )

    try:
        raw = _raw_output_from_result(result)
    except Exception as exc:
        return CandidateCanaryExecution(
            case_path=case_path,
            seed=SHARED_CANARY_SEED,
            result=result,
            raw_output=None,
            error=str(exc),
        )
    if raw is None:
        return CandidateCanaryExecution(
            case_path=case_path,
            seed=SHARED_CANARY_SEED,
            result=result,
            raw_output=None,
            error="solver produced no output",
        )
    return CandidateCanaryExecution(
        case_path=case_path,
        seed=SHARED_CANARY_SEED,
        result=result,
        raw_output=raw,
    )


def _raw_output_from_result(result: RunResult) -> Mapping[str, Any] | None:
    if result.output_path:
        with open(result.output_path, encoding="utf-8") as handle:
            raw = json.load(handle)
        if not isinstance(raw, Mapping):
            raise TypeError("solver output JSON must be an object")
        return raw
    if result.output is None:
        return None
    raw = dict(result.output.solution_payload)
    raw["objective"] = dict(result.output.objective)
    raw["feasible"] = bool(result.output.feasible)
    raw["runtime"] = dict(result.output.runtime)
    return raw
