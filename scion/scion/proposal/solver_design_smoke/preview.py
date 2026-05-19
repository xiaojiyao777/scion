"""Runtime smoke preview orchestration for solver-design patches."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping

from scion.core.models import HypothesisProposal, PatchProposal, patch_file_changes
from scion.runtime.telemetry_guard import (
    build_telemetry_guard_summary,
    format_telemetry_guard_issue,
)

from .audit import (
    _compact_runtime_audit_failure,
    _compact_runtime_smoke_payload,
    _problem_spec_for_runtime_audit,
    _runtime_smoke_audit_failure,
)
from .benchmark import (
    _compact_solver_design_micro_benchmark,
    _solver_design_micro_benchmark_issue,
    _solver_design_micro_benchmark_result,
)
from .cases import (
    _runtime_smoke_case_public_payload,
    _runtime_smoke_cases,
    _runtime_smoke_payload_provenance,
    _runtime_smoke_safe_data_roots,
)
from .constants import (
    _ALGORITHM_SMOKE_DEFAULT_SEED,
    _ALGORITHM_SMOKE_TIME_LIMIT_SEC,
)
from .effort import (
    _solver_design_low_effort_issue,
    _solver_design_patch_claims_search_effort,
    _solver_design_zero_effort_issue,
)
from .guidance import _solver_design_smoke_repair_guidance
from .provider import _solver_design_smoke_provider
from .runner import _run_solver_design_smoke
from .utils import _attr, _normalize_rel_path, _normalize_solver_design_surface
from .workspace import (
    _apply_patch_to_runtime_smoke_workspace,
    _is_solver_design_runtime_patch_path,
    _runtime_smoke_base_workspace,
)

if TYPE_CHECKING:
    from scion.proposal.tools import ProposalToolContext
else:
    ProposalToolContext = Any


def _runtime_algorithm_smoke_preview(
    context: ProposalToolContext,
    patch: PatchProposal,
    selected_surface: str | None,
    hypothesis: HypothesisProposal | None = None,
) -> dict[str, Any] | None:
    surface_name = _normalize_solver_design_surface(selected_surface)
    if surface_name != "solver_design":
        return None
    provider = _solver_design_smoke_provider(context)
    if provider is None:
        return None
    patch_paths = [
        _normalize_rel_path(change.file_path) for change in patch_file_changes(patch)
    ]
    if not any(
        _is_solver_design_runtime_patch_path(path, provider=provider)
        for path in patch_paths
    ):
        return None

    base_workspace = _runtime_smoke_base_workspace(context)
    canary_rel = str(_attr(context.problem_spec, "canary_case_path", "") or "").strip()
    if base_workspace is None:
        return {
            "passed": False,
            "skipped": False,
            "workspace_materialized": False,
            "runtime_smoke_run": False,
            "issues": ["No runnable base workspace found for solver_design smoke."],
        }
    if not canary_rel:
        return {
            "passed": False,
            "skipped": False,
            "workspace_materialized": False,
            "runtime_smoke_run": False,
            "issues": ["No canary_case_path configured for solver_design smoke."],
        }

    with tempfile.TemporaryDirectory(prefix="scion_algorithm_smoke_") as tmp:
        workspace = Path(tmp) / "workspace"
        champion_workspace = Path(tmp) / "champion"
        try:
            shutil.copytree(
                base_workspace,
                workspace,
                ignore=shutil.ignore_patterns(
                    "__pycache__",
                    "*.pyc",
                    ".pytest_cache",
                    ".mypy_cache",
                    ".ruff_cache",
                ),
            )
            shutil.copytree(
                base_workspace,
                champion_workspace,
                ignore=shutil.ignore_patterns(
                    "__pycache__",
                    "*.pyc",
                    ".pytest_cache",
                    ".mypy_cache",
                    ".ruff_cache",
                ),
            )
            _apply_patch_to_runtime_smoke_workspace(workspace, patch)
            smoke_cases, missing_cases = _runtime_smoke_cases(
                workspace=workspace,
                base_workspace=base_workspace,
                canary_rel=canary_rel,
                split_manifest=context.split_manifest,
                seed_ledger=context.seed_ledger,
                safe_data_roots=_runtime_smoke_safe_data_roots(context),
            )
            if not smoke_cases:
                return {
                    "passed": False,
                    "skipped": False,
                    "workspace_materialized": True,
                    "runtime_smoke_run": False,
                    "issues": missing_cases
                    or [f"No runnable smoke case found: {canary_rel}"],
                }
            registry_path = workspace / "registry.yaml"
            if not registry_path.exists():
                registry_path = workspace / "registry.json"
            champion_registry_path = champion_workspace / "registry.yaml"
            if not champion_registry_path.exists():
                champion_registry_path = champion_workspace / "registry.json"
            runs: list[dict[str, Any]] = []
            micro_results: list[dict[str, Any]] = []
            candidate_guard_runtimes: list[Mapping[str, Any]] = []
            champion_guard_runtimes: list[Mapping[str, Any]] = []
            telemetry_guard_summary: dict[str, Any] = {}
            representative: dict[str, Any] | None = None
            issue: str | None = None
            audit_failure: Mapping[str, Any] | None = None
            for smoke_case in smoke_cases:
                raw, run_payload = _run_solver_design_smoke(
                    workspace=workspace,
                    smoke_case=smoke_case,
                    registry_path=registry_path,
                    selected_surface=surface_name,
                )
                if raw is None:
                    issue = str(run_payload.get("detail") or "solver run failed")
                    representative = {
                        **_runtime_smoke_case_public_payload(smoke_case),
                        "seed": smoke_case.seed,
                        "label": smoke_case.label,
                        "passed": False,
                        "objective": None,
                        "feasible": None,
                        "runtime": {},
                        "run": run_payload,
                    }
                    runs.append(representative)
                    break

                audit_failure = _runtime_smoke_audit_failure(
                    raw,
                    context=context,
                    selected_surface=surface_name,
                )
                runtime = raw.get("runtime") if isinstance(raw, Mapping) else None
                if isinstance(runtime, Mapping):
                    candidate_guard_runtimes.append(runtime)
                run_result = {
                    **_runtime_smoke_case_public_payload(smoke_case),
                    "seed": smoke_case.seed,
                    "label": smoke_case.label,
                    "passed": audit_failure is None,
                    "objective": raw.get("objective")
                    if isinstance(raw, Mapping)
                    else None,
                    "feasible": raw.get("feasible") if isinstance(raw, Mapping) else None,
                    "runtime": _compact_runtime_smoke_payload(runtime),
                    "run": run_payload,
                }
                if audit_failure is not None:
                    issue = str(audit_failure.get("detail") or "runtime audit failed")
                    repair_guidance = _solver_design_smoke_repair_guidance(
                        audit_failure,
                        runtime=runtime,
                        run_payload=run_payload,
                        provider=provider,
                    )
                    run_result["runtime_audit_failure"] = (
                        _compact_runtime_audit_failure(audit_failure)
                    )
                    if repair_guidance:
                        run_result["repair_guidance"] = repair_guidance
                runs.append(run_result)
                if representative is None or audit_failure is not None:
                    representative = run_result
                if audit_failure is not None:
                    break
                champion_raw, champion_run = _run_solver_design_smoke(
                    workspace=champion_workspace,
                    smoke_case=smoke_case,
                    registry_path=champion_registry_path,
                    selected_surface=surface_name,
                )
                micro_result = _solver_design_micro_benchmark_result(
                    candidate_raw=raw,
                    candidate_run=run_payload,
                    champion_raw=champion_raw,
                    champion_run=champion_run,
                    smoke_case=smoke_case,
                )
                champion_runtime = (
                    champion_raw.get("runtime")
                    if isinstance(champion_raw, Mapping)
                    else None
                )
                if isinstance(champion_runtime, Mapping):
                    champion_guard_runtimes.append(champion_runtime)
                run_result["micro_benchmark"] = micro_result
                micro_results.append(micro_result)
            if issue is None:
                telemetry_guard_summary = build_telemetry_guard_summary(
                    candidate_runtimes=candidate_guard_runtimes,
                    champion_runtimes=champion_guard_runtimes,
                    problem_spec=_problem_spec_for_runtime_audit(context.problem_spec),
                    selected_surface=surface_name,
                    expected_telemetry=getattr(hypothesis, "expected_telemetry", None),
                    declared_mechanisms=getattr(hypothesis, "mechanism_changes", ()),
                    protected_objectives=getattr(
                        hypothesis,
                        "protected_objectives",
                        (),
                    ),
                    implicit_activity_claim=_solver_design_patch_claims_search_effort(
                        patch,
                        hypothesis,
                        provider=provider,
                    ),
                )
                issue = format_telemetry_guard_issue(telemetry_guard_summary)
            if issue is None:
                issue = _solver_design_zero_effort_issue(
                    patch=patch,
                    hypothesis=hypothesis,
                    runs=runs,
                    provider=provider,
                )
            if issue is None:
                issue = _solver_design_low_effort_issue(
                    patch=patch,
                    hypothesis=hypothesis,
                    runs=runs,
                    micro_results=micro_results,
                    provider=provider,
                )
            if issue is None:
                issue = _solver_design_micro_benchmark_issue(micro_results)
        except Exception as exc:
            return {
                "passed": False,
                "skipped": False,
                "workspace_materialized": True,
                "runtime_smoke_run": False,
                "issues": [f"runtime smoke setup failed: {type(exc).__name__}: {exc}"],
            }

    representative = representative or {}
    passed = issue is None
    issues = [] if passed else [str(issue)]
    payload = {
        "passed": passed,
        "skipped": False,
        "workspace_materialized": True,
        "runtime_smoke_run": True,
        "selected_surface": surface_name,
        "case": representative.get("case") or canary_rel,
        "resolved_case_path": representative.get("resolved_case_path"),
        "case_path_ref": representative.get("case_path_ref"),
        "data_root": representative.get("data_root"),
        "data_root_source": representative.get("data_root_source"),
        "data_root_status": representative.get("data_root_status"),
        "provenance": _runtime_smoke_payload_provenance(representative),
        "seed": representative.get("seed") or _ALGORITHM_SMOKE_DEFAULT_SEED,
        "case_count": len(runs),
        "cases": [
            {
                "label": run.get("label"),
                "case": run.get("case"),
                "resolved_case_path": run.get("resolved_case_path"),
                "case_path_ref": run.get("case_path_ref"),
                "data_root": run.get("data_root"),
                "data_root_source": run.get("data_root_source"),
                "data_root_status": run.get("data_root_status"),
                "provenance": run.get("provenance"),
                "seed": run.get("seed"),
                "passed": run.get("passed"),
            }
            for run in runs
        ],
        "time_limit_sec": _ALGORITHM_SMOKE_TIME_LIMIT_SEC,
        "objective": representative.get("objective"),
        "feasible": representative.get("feasible"),
        "runtime": representative.get("runtime") or {},
        "issues": issues,
        "run": representative.get("run") or {},
        "runs": runs,
        "micro_benchmark": _compact_solver_design_micro_benchmark(micro_results),
    }
    if telemetry_guard_summary:
        payload["telemetry_guard"] = telemetry_guard_summary
    if audit_failure is not None:
        payload["runtime_audit_failure"] = _compact_runtime_audit_failure(
            audit_failure
        )
        repair_guidance = _solver_design_smoke_repair_guidance(
            audit_failure,
            runtime=representative.get("runtime"),
            run_payload=representative.get("run"),
            provider=provider,
        )
        if repair_guidance:
            payload["repair_guidance"] = repair_guidance
    return payload
