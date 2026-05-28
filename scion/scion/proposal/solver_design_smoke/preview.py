"""Runtime smoke preview orchestration for solver-design patches."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping

from scion.core.models import HypothesisProposal, PatchProposal, patch_file_changes
from scion.core.runtime_budget_diagnostics import runtime_budget_diagnostic
from scion.runtime.audit import format_runtime_audit_failure
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
    _solver_design_static_issue,
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
        return {
            "passed": True,
            "skipped": True,
            "workspace_materialized": False,
            "runtime_smoke_run": False,
            "selected_surface": surface_name,
            "provider_unavailable": True,
            "provider_hook_used": False,
            "provider_case_count": 0,
            "provider_case_attempted_count": 0,
            "case_count": 0,
            "selected_case_count": 0,
            "attempted_case_count": 0,
            "case_execution_ledger": [],
            "issues": [
                (
                    "No problem-owned solver-design smoke provider is registered; "
                    "provider representative smoke cases cannot be selected."
                )
            ],
            "evidence_diagnostics": [
                {
                    "code": "solver_design_smoke_provider_unavailable",
                    "severity": "warning",
                    "detail": (
                        "No problem-owned solver-design smoke provider is "
                        "registered, so algorithm smoke cannot run provider "
                        "representative cases."
                    ),
                    "provider_case_count": 0,
                    "provider_case_attempted_count": 0,
                    "case_count": 0,
                }
            ],
        }
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
            "selected_surface": surface_name,
            "issues": ["No runnable base workspace found for solver_design smoke."],
            **_unavailable_provider_smoke_evidence(
                selected_surface=surface_name,
                code="solver_design_smoke_workspace_unavailable",
                detail=(
                    "No runnable base workspace was available, so provider "
                    "representative smoke cases could not be selected or run."
                ),
            ),
        }
    if not canary_rel:
        return {
            "passed": False,
            "skipped": False,
            "workspace_materialized": False,
            "runtime_smoke_run": False,
            "selected_surface": surface_name,
            "issues": ["No canary_case_path configured for solver_design smoke."],
            **_unavailable_provider_smoke_evidence(
                selected_surface=surface_name,
                code="solver_design_smoke_canary_unavailable",
                detail=(
                    "No canary_case_path was configured, so provider "
                    "representative smoke cases could not be selected or run."
                ),
            ),
        }
    static_issue = _solver_design_static_issue(
        patch=patch,
        hypothesis=hypothesis,
        provider=provider,
    )
    if static_issue:
        provider_evidence = _unrun_provider_smoke_evidence(
            context=context,
            base_workspace=base_workspace,
            canary_rel=canary_rel,
            provider=provider,
            selected_surface=surface_name,
            skip_code="provider_representative_smoke_cases_skipped_by_static_diagnostic",
            skip_detail=(
                "Provider representative smoke cases were selected, but "
                "runtime smoke execution was skipped because a static smoke "
                "diagnostic fired before candidate execution."
            ),
        )
        return {
            "passed": False,
            "skipped": False,
            "workspace_materialized": False,
            "runtime_smoke_run": False,
            "selected_surface": surface_name,
            "issues": [static_issue],
            **provider_evidence,
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
                provider=provider,
                context=context,
            )
            if not smoke_cases:
                provider_evidence = _unrun_provider_smoke_evidence_from_cases(
                    smoke_cases=smoke_cases,
                    missing_cases=missing_cases,
                    provider=provider,
                    selected_surface=surface_name,
                    skip_code="provider_representative_smoke_cases_unavailable",
                    skip_detail=(
                        "No runnable provider representative smoke cases were "
                        "available for algorithm smoke."
                    ),
                )
                return {
                    "passed": False,
                    "skipped": False,
                    "workspace_materialized": True,
                    "runtime_smoke_run": False,
                    "selected_surface": surface_name,
                    "issues": missing_cases
                    or [f"No runnable smoke case found: {canary_rel}"],
                    **provider_evidence,
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
            candidate_elapsed_samples_ms: list[float] = []
            champion_elapsed_samples_ms: list[float] = []
            telemetry_guard_summary: dict[str, Any] = {}
            runtime_budget_diagnostic_summary: dict[str, Any] | None = None
            case_execution_ledger: list[dict[str, Any]] = []
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
                _append_smoke_elapsed(candidate_elapsed_samples_ms, run_payload)
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
                    "runtime": _compact_runtime_smoke_payload(
                        runtime,
                        context=context,
                        selected_surface=surface_name,
                    ),
                    "run": run_payload,
                }
                if audit_failure is not None:
                    issue = format_runtime_audit_failure(audit_failure)
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
                _append_smoke_elapsed(champion_elapsed_samples_ms, champion_run)
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
                    effect_observation_required=(
                        _smoke_effect_observation_required(provider, hypothesis)
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
            runtime_budget_diagnostic_summary = runtime_budget_diagnostic(
                stage="proposal_smoke",
                time_limit_sec=_ALGORITHM_SMOKE_TIME_LIMIT_SEC,
                candidate_elapsed_ms=candidate_elapsed_samples_ms,
                champion_elapsed_ms=champion_elapsed_samples_ms,
                total_pairs=len(runs),
            )
            case_execution_ledger = _runtime_smoke_case_execution_ledger(
                smoke_cases,
                runs,
                selected_surface=surface_name,
            )
            provider_case_count = sum(
                1 for item in case_execution_ledger if item.get("provider_hook_used")
            )
            provider_case_attempted_count = sum(
                1
                for item in case_execution_ledger
                if item.get("provider_hook_used") and item.get("attempted")
            )
            provider_missing_cases = _provider_case_missing_issues(missing_cases)
            if issue is None and provider_missing_cases:
                issue = "; ".join(provider_missing_cases[:3])
            if (
                issue is None
                and provider_case_count > 0
                and provider_case_attempted_count < provider_case_count
            ):
                issue = (
                    "provider representative smoke cases were selected but not all "
                    "executed before algorithm smoke completion; "
                    f"attempted={provider_case_attempted_count}/"
                    f"{provider_case_count}"
                )
        except Exception as exc:
            return {
                "passed": False,
                "skipped": False,
                "workspace_materialized": True,
                "runtime_smoke_run": False,
                "selected_surface": surface_name,
                "provider_hook_used": False,
                "provider_case_count": 0,
                "provider_case_attempted_count": 0,
                "case_count": 0,
                "selected_case_count": 0,
                "attempted_case_count": 0,
                "case_execution_ledger": [],
                "cases": [],
                "evidence_diagnostics": [
                    {
                        "code": "provider_representative_smoke_case_selection_failed",
                        "severity": "warning",
                        "detail": (
                            "Runtime smoke setup failed before provider "
                            "representative evidence could be completed."
                        ),
                        "provider_case_count": 0,
                        "provider_case_attempted_count": 0,
                    }
                ],
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
        "selected_case_count": len(case_execution_ledger),
        "attempted_case_count": sum(
            1 for item in case_execution_ledger if item.get("attempted")
        ),
        "provider_hook_used": any(
            bool(item.get("provider_hook_used")) for item in case_execution_ledger
        ),
        "provider_case_count": sum(
            1 for item in case_execution_ledger if item.get("provider_hook_used")
        ),
        "provider_case_attempted_count": sum(
            1
            for item in case_execution_ledger
            if item.get("provider_hook_used") and item.get("attempted")
        ),
        "cases": case_execution_ledger,
        "case_execution_ledger": case_execution_ledger,
        "time_limit_sec": _ALGORITHM_SMOKE_TIME_LIMIT_SEC,
        "objective": representative.get("objective"),
        "feasible": representative.get("feasible"),
        "runtime": _compact_runtime_smoke_payload(
            representative.get("runtime"),
            context=context,
            selected_surface=surface_name,
        ),
        "issues": issues,
        "run": representative.get("run") or {},
        "runs": runs,
        "micro_benchmark": _compact_solver_design_micro_benchmark(micro_results),
    }
    if telemetry_guard_summary:
        payload["telemetry_guard"] = telemetry_guard_summary
    if runtime_budget_diagnostic_summary:
        payload["runtime_budget_diagnostic"] = runtime_budget_diagnostic_summary
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


def _unavailable_provider_smoke_evidence(
    *,
    selected_surface: str,
    code: str,
    detail: str,
) -> dict[str, Any]:
    return {
        "provider_hook_used": False,
        "provider_case_count": 0,
        "provider_case_attempted_count": 0,
        "case_count": 0,
        "selected_case_count": 0,
        "attempted_case_count": 0,
        "case_execution_ledger": [],
        "cases": [],
        "provenance": {
            "source": "provider_smoke_not_selectable",
            "absolute_paths_exposed": False,
        },
        "evidence_diagnostics": [
            {
                "code": code,
                "severity": "warning",
                "detail": detail,
                "selected_surface": selected_surface,
                "provider_case_count": 0,
                "provider_case_attempted_count": 0,
            }
        ],
    }


def _unrun_provider_smoke_evidence(
    *,
    context: ProposalToolContext,
    base_workspace: Path,
    canary_rel: str,
    provider: Any,
    selected_surface: str,
    skip_code: str,
    skip_detail: str,
) -> dict[str, Any]:
    try:
        smoke_cases, missing_cases = _runtime_smoke_cases(
            workspace=base_workspace,
            base_workspace=base_workspace,
            canary_rel=canary_rel,
            split_manifest=context.split_manifest,
            seed_ledger=context.seed_ledger,
            safe_data_roots=_runtime_smoke_safe_data_roots(context),
            provider=provider,
            context=context,
        )
    except Exception as exc:
        return {
            "provider_hook_used": False,
            "provider_case_count": 0,
            "provider_case_attempted_count": 0,
            "case_count": 0,
            "selected_case_count": 0,
            "attempted_case_count": 0,
            "case_execution_ledger": [],
            "cases": [],
            "provenance": {
                "source": "provider_smoke_static_selection_failed",
                "absolute_paths_exposed": False,
            },
            "evidence_diagnostics": [
                {
                    "code": "provider_representative_smoke_case_selection_failed",
                    "severity": "warning",
                    "detail": (
                        "Provider representative smoke case selection failed "
                        f"before runtime execution: {type(exc).__name__}: {exc}"
                    ),
                    "provider_case_count": 0,
                    "provider_case_attempted_count": 0,
                }
            ],
        }
    return _unrun_provider_smoke_evidence_from_cases(
        smoke_cases=smoke_cases,
        missing_cases=missing_cases,
        provider=provider,
        selected_surface=selected_surface,
        skip_code=skip_code,
        skip_detail=skip_detail,
    )


def _unrun_provider_smoke_evidence_from_cases(
    *,
    smoke_cases: list[Any],
    missing_cases: list[str],
    provider: Any,
    selected_surface: str,
    skip_code: str,
    skip_detail: str,
) -> dict[str, Any]:
    ledger = _runtime_smoke_case_execution_ledger(
        smoke_cases,
        [],
        selected_surface=selected_surface,
    )
    provider_case_count = sum(
        1 for item in ledger if item.get("provider_hook_used")
    )
    provider_case_attempted_count = sum(
        1
        for item in ledger
        if item.get("provider_hook_used") and item.get("attempted")
    )
    diagnostics: list[dict[str, Any]] = []
    provider_missing_cases = _provider_case_missing_issues(missing_cases)
    if provider_case_count > 0:
        diagnostics.append(
            {
                "code": skip_code,
                "severity": "warning",
                "detail": skip_detail,
                "provider_case_count": provider_case_count,
                "provider_case_attempted_count": provider_case_attempted_count,
            }
        )
    elif provider_missing_cases:
        diagnostics.append(
            {
                "code": "provider_representative_smoke_cases_unavailable",
                "severity": "warning",
                "detail": (
                    "Provider representative smoke cases were requested but "
                    "could not be resolved from safe data roots."
                ),
                "provider_case_count": 0,
                "provider_case_attempted_count": 0,
                "missing_cases": provider_missing_cases[:4],
            }
        )
    elif provider is not None:
        diagnostics.append(
            {
                "code": "provider_representative_smoke_cases_not_selected",
                "severity": "warning",
                "detail": (
                    "A solver-design smoke provider is registered, but it did "
                    "not provide representative cases for this algorithm smoke."
                ),
                "provider_case_count": 0,
                "provider_case_attempted_count": 0,
            }
        )
    return {
        "provider_hook_used": provider_case_count > 0,
        "provider_case_count": provider_case_count,
        "provider_case_attempted_count": provider_case_attempted_count,
        "case_count": 0,
        "selected_case_count": len(ledger),
        "attempted_case_count": 0,
        "case_execution_ledger": ledger,
        "cases": ledger,
        "provenance": {
            "source": "provider_smoke_static_case_selection",
            "absolute_paths_exposed": False,
        },
        "evidence_diagnostics": diagnostics,
    }


def _provider_case_missing_issues(missing_cases: list[str]) -> list[str]:
    issues: list[str] = []
    for item in missing_cases:
        text = str(item or "").strip()
        if not text:
            continue
        if "provider" not in text.lower():
            continue
        issues.append(f"provider representative smoke case missing: {text}")
    return issues


def _runtime_smoke_case_execution_ledger(
    smoke_cases: list[Any],
    runs: list[dict[str, Any]],
    *,
    selected_surface: str,
) -> list[dict[str, Any]]:
    runs_by_digest: dict[str, Mapping[str, Any]] = {}
    for run in runs:
        digest = str(run.get("case_digest") or run.get("case_metadata_hash") or "")
        if digest:
            runs_by_digest.setdefault(digest, run)
    ledger: list[dict[str, Any]] = []
    seen_run_ids: set[int] = set()
    for smoke_case in smoke_cases:
        case_payload = _runtime_smoke_case_public_payload(smoke_case)
        digest = str(case_payload.get("case_digest") or "")
        run = runs_by_digest.get(digest)
        if run is not None:
            seen_run_ids.add(id(run))
            ledger.append(
                _runtime_smoke_case_execution_record(
                    run,
                    selected_surface=selected_surface,
                    attempted=True,
                )
            )
        else:
            ledger.append(
                _runtime_smoke_case_execution_record(
                    {
                        **case_payload,
                        "label": smoke_case.label,
                        "seed": smoke_case.seed,
                    },
                    selected_surface=selected_surface,
                    attempted=False,
                )
            )
    for run in runs:
        if id(run) in seen_run_ids:
            continue
        ledger.append(
            _runtime_smoke_case_execution_record(
                run,
                selected_surface=selected_surface,
                attempted=True,
            )
        )
    return ledger


def _runtime_smoke_case_execution_record(
    run: Mapping[str, Any],
    *,
    selected_surface: str,
    attempted: bool,
) -> dict[str, Any]:
    runtime = run.get("runtime") if isinstance(run.get("runtime"), Mapping) else {}
    run_payload = run.get("run") if isinstance(run.get("run"), Mapping) else {}
    audit = (
        run.get("runtime_audit_failure")
        if isinstance(run.get("runtime_audit_failure"), Mapping)
        else {}
    )
    failure = _runtime_smoke_case_failure(run, run_payload, audit, attempted=attempted)
    surface_summary = _selected_surface_runtime_summary(runtime, audit)
    elapsed_ms = run_payload.get("elapsed_ms")
    record = {
        "label": run.get("label"),
        "case": run.get("case"),
        "resolved_case_path": run.get("resolved_case_path"),
        "case_path_ref": run.get("case_path_ref"),
        "case_source": run.get("case_source"),
        "data_root": run.get("data_root"),
        "data_root_source": run.get("data_root_source"),
        "data_root_status": run.get("data_root_status"),
        "provider_hook_used": bool(run.get("provider_hook_used")),
        "provider_hook_name": run.get("provider_hook_name"),
        "seed": run.get("seed"),
        "attempted": attempted,
        "success": run_payload.get("success") if attempted else None,
        "passed": run.get("passed") if attempted else None,
        "failure": failure,
        "selected_surface": selected_surface,
        "selected_surface_runtime": surface_summary,
        "selected_surface_active": surface_summary.get("active"),
        "selected_surface_errors": surface_summary.get("errors"),
        "selected_surface_fallback": surface_summary.get("fallback_emitted"),
        "runtime_audit_summary": _runtime_audit_summary(audit),
        "runtime_audit_hash": (
            _runtime_smoke_ledger_digest(audit) if audit else ""
        ),
        "elapsed_ms": elapsed_ms,
        "duration_ms": elapsed_ms,
        "case_digest": run.get("case_digest") or run.get("case_metadata_hash"),
        "case_metadata_hash": run.get("case_metadata_hash") or run.get("case_digest"),
        "run_digest": run_payload.get("run_digest")
        or _runtime_smoke_ledger_digest(run_payload),
    }
    return {key: value for key, value in record.items() if value not in ("", {}, [])}


def _runtime_smoke_case_failure(
    run: Mapping[str, Any],
    run_payload: Mapping[str, Any],
    audit: Mapping[str, Any],
    *,
    attempted: bool,
) -> str:
    if not attempted:
        return "not_attempted"
    if audit:
        return str(audit.get("detail") or audit.get("error_category") or "runtime_audit_failure")
    if run_payload.get("success") is False:
        return str(run_payload.get("detail") or "solver run failed")
    if run.get("passed") is False:
        return "runtime smoke case failed"
    return ""


def _runtime_audit_summary(audit: Mapping[str, Any]) -> dict[str, Any]:
    if not audit:
        return {}
    return {
        key: audit.get(key)
        for key in (
            "error_category",
            "detail",
            "failed_runtime_fields",
            "runtime_error_field",
            "runtime_error_count",
            "runtime_events",
        )
        if audit.get(key) not in (None, "", [], {})
    }


def _selected_surface_runtime_summary(
    runtime: Mapping[str, Any],
    audit: Mapping[str, Any],
) -> dict[str, Any]:
    active_field, active = _first_runtime_suffix_value(runtime, ("active",))
    error_field, errors = _first_runtime_suffix_value(
        runtime,
        ("errors", "error_count", "invalid_outputs"),
    )
    fallback = _runtime_mentions_fallback(runtime) or _runtime_mentions_fallback(audit)
    return {
        key: value
        for key, value in {
            "active_field": active_field,
            "active": active,
            "errors_field": error_field,
            "errors": errors,
            "fallback_emitted": fallback,
        }.items()
        if value not in (None, "", {}, [])
    }


def _first_runtime_suffix_value(
    runtime: Mapping[str, Any],
    suffixes: tuple[str, ...],
) -> tuple[str, Any]:
    suffix_tokens = tuple(suffix.replace(".", "_").strip("_") for suffix in suffixes)
    for key, value in sorted(runtime.items()):
        normalized = str(key).replace(".", "_").strip("_")
        if normalized in suffix_tokens or any(
            normalized.endswith("_" + suffix) for suffix in suffix_tokens
        ):
            return str(key), value
    return "", None


def _runtime_mentions_fallback(value: Any) -> bool:
    if isinstance(value, Mapping):
        for key, item in value.items():
            text = str(key).lower()
            if "fallback" in text and item not in (None, "", False, 0, [], {}):
                return True
            if _runtime_mentions_fallback(item):
                return True
        return False
    if isinstance(value, (list, tuple)):
        return any(_runtime_mentions_fallback(item) for item in value)
    return "fallback" in str(value or "").lower()


def _runtime_smoke_ledger_digest(value: Any) -> str:
    rendered = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()[:16]


def _append_smoke_elapsed(samples: list[float], run_payload: Mapping[str, Any]) -> None:
    try:
        elapsed = float(run_payload.get("elapsed_ms"))
    except (TypeError, ValueError):
        return
    if elapsed >= 0:
        samples.append(elapsed)


def _smoke_effect_observation_required(
    provider: Any,
    hypothesis: HypothesisProposal | None,
) -> bool:
    """Return whether algorithm-smoke must see positive effect evidence."""
    for name in (
        "requires_smoke_effect_observation",
        "smoke_effect_observation_required",
        "algorithm_smoke_requires_positive_effect",
    ):
        hook = getattr(provider, name, None)
        if not callable(hook):
            continue
        try:
            return bool(hook(hypothesis=hypothesis))
        except TypeError:
            try:
                return bool(hook(hypothesis))
            except TypeError:
                return bool(hook())
    if hypothesis is None:
        return False
    for name in (
        "smoke_effect_required",
        "smoke_requires_positive_effect",
        "algorithm_smoke_requires_positive_effect",
    ):
        value = getattr(hypothesis, name, None)
        if value not in (None, "", (), [], {}):
            return bool(value)
    expected = getattr(hypothesis, "expected_telemetry", None)
    if isinstance(expected, Mapping):
        return bool(
            expected.get("smoke_effect_required")
            or expected.get("smoke_requires_positive_effect")
        )
    return False
