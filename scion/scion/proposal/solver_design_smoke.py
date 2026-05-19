"""Solver-design runtime smoke helpers for proposal tools."""

from __future__ import annotations

import json
import os
import shutil
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any, Mapping

import yaml

from scion.core.models import (
    ExperimentStage,
    HypothesisProposal,
    PatchFileChange,
    PatchProposal,
    patch_file_changes,
)
from scion.core.paths import normalize_relative_patch_path
from scion.problem.bridge import legacy_problem_spec_from_v1
from scion.problem.providers import resolve_solver_design_smoke_provider
from scion.runtime.telemetry_guard import (
    build_telemetry_guard_summary,
    format_telemetry_guard_issue,
)

if TYPE_CHECKING:
    from scion.proposal.tools import ProposalToolContext
else:
    ProposalToolContext = Any

_ALGORITHM_SMOKE_TIME_LIMIT_SEC = 3
_ALGORITHM_SMOKE_TIMEOUT_SEC = 15
_ALGORITHM_SMOKE_DEFAULT_SEED = 77
_ALGORITHM_SMOKE_MAX_SCREENING_CASES = 4
_ALGORITHM_SMOKE_LOW_EFFORT_MIN_CASES = 2
_ALGORITHM_SMOKE_LOW_EFFORT_MAX_ITERATIONS = 5
_ALGORITHM_SMOKE_LOW_EFFORT_MAX_ATTEMPTS = 30
_ALGORITHM_SMOKE_LOW_EFFORT_MAX_RUNTIME_RATIO = 0.35
_ALGORITHM_SMOKE_LOW_EFFORT_STOP_REASONS = frozenset(
    {
        "no_improvement",
        "early_exit",
        "construction_only",
        "no_search",
    }
)


@dataclass(frozen=True)
class _RuntimeSmokeCase:
    label: str
    rel_path: str
    seed: int
    path: Path
    data_root: str | None = None
    data_root_source: str = "unknown"
    data_root_status: str = "unresolved"
    case_source: str = "runtime_smoke_manifest"


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


def _runtime_smoke_base_workspace(context: ProposalToolContext) -> Path | None:
    champion_path = _attr(context.champion, "code_snapshot_path")
    if champion_path:
        path = Path(str(champion_path)).expanduser().resolve(strict=False)
        if path.is_dir() and (path / "solver.py").is_file():
            return path
    root_dir = _attr(context.problem_spec, "root_dir")
    if root_dir:
        path = Path(str(root_dir)).expanduser().resolve(strict=False)
        if path.is_dir() and (path / "solver.py").is_file():
            return path
    return None


def _solver_design_smoke_provider(context: ProposalToolContext) -> Any | None:
    return resolve_solver_design_smoke_provider(
        problem_spec=getattr(context, "problem_spec", None),
        adapter=getattr(context, "adapter", None),
    )


def _is_solver_design_runtime_patch_path(
    path: str | None,
    *,
    provider: Any | None = None,
) -> bool:
    checker = getattr(provider, "is_runtime_patch_path", None)
    if callable(checker):
        return bool(checker(path))
    return False


def _apply_patch_to_runtime_smoke_workspace(
    workspace: Path,
    patch: PatchProposal,
) -> None:
    for change in patch_file_changes(patch):
        _apply_file_change_to_runtime_smoke_workspace(workspace, change)


def _apply_file_change_to_runtime_smoke_workspace(
    workspace: Path,
    change: PatchFileChange,
) -> None:
    rel = normalize_relative_patch_path(change.file_path)
    target = (workspace / rel).resolve(strict=False)
    target.relative_to(workspace.resolve(strict=False))
    action = str(change.action or "modify")
    if action in {"modify", "add", "create", "create_new"}:
        _ensure_runtime_smoke_path_writable(target.parent)
        target.parent.mkdir(parents=True, exist_ok=True)
        _ensure_runtime_smoke_path_writable(target)
        target.write_text(str(change.code_content or ""), encoding="utf-8")
    elif action in {"remove", "delete"}:
        if target.exists():
            _ensure_runtime_smoke_path_writable(target.parent)
            _ensure_runtime_smoke_path_writable(target)
            target.unlink()
    else:
        raise ValueError(f"unsupported patch action for smoke: {action}")


def _ensure_runtime_smoke_path_writable(path: Path) -> None:
    try:
        mode = path.stat().st_mode
    except FileNotFoundError:
        return
    writable_mode = mode | stat.S_IWUSR
    if path.is_dir():
        writable_mode |= stat.S_IXUSR
    if writable_mode != mode:
        path.chmod(writable_mode)


def _runtime_smoke_cases(
    *,
    workspace: Path,
    base_workspace: Path,
    canary_rel: str,
    split_manifest: Any = None,
    seed_ledger: Any = None,
    safe_data_roots: Any = None,
) -> tuple[list[_RuntimeSmokeCase], list[str]]:
    cases: list[_RuntimeSmokeCase] = []
    missing: list[str] = []
    seen: set[tuple[str, int]] = set()

    def add_case(label: str, rel_path: Any, seed: Any, case_source: str) -> None:
        rel = str(rel_path or "").strip()
        if not rel:
            return
        try:
            seed_value = int(seed)
        except (TypeError, ValueError):
            seed_value = _ALGORITHM_SMOKE_DEFAULT_SEED
        key = (rel, seed_value)
        if key in seen:
            return
        seen.add(key)
        resolution = _resolve_smoke_instance(
            workspace=workspace,
            base_workspace=base_workspace,
            case_rel=rel,
            safe_data_roots=safe_data_roots,
            case_source=case_source,
        )
        if resolution["path"] is None:
            missing.append(f"{label} smoke case not found: {rel}")
            return
        cases.append(
            _RuntimeSmokeCase(
                label=label,
                rel_path=rel,
                seed=seed_value,
                path=resolution["path"],
                data_root=resolution["data_root"],
                data_root_source=resolution["data_root_source"],
                data_root_status=resolution["data_root_status"],
                case_source=case_source,
            )
        )

    if split_manifest is None:
        split_manifest = _load_runtime_smoke_yaml(
            workspace=workspace,
            base_workspace=base_workspace,
            filename="split_manifest.yaml",
        )
    if seed_ledger is None:
        seed_ledger = _load_runtime_smoke_yaml(
            workspace=workspace,
            base_workspace=base_workspace,
            filename="seed_ledger.yaml",
        )
    if safe_data_roots is None:
        safe_data_roots = _runtime_smoke_safe_data_roots_from_manifest(split_manifest)

    canary_seed = _first_int(
        _runtime_smoke_stage_value(seed_ledger, "canary"),
        _ALGORITHM_SMOKE_DEFAULT_SEED,
    )
    canary_cases = _string_list(_runtime_smoke_stage_value(split_manifest, "canary"))
    case_source = _runtime_smoke_case_source(split_manifest)
    if canary_rel and canary_rel not in canary_cases:
        canary_cases.append(canary_rel)
    for rel in canary_cases[:1]:
        add_case("canary", rel, canary_seed, case_source)

    screening_seed = _first_int(
        _runtime_smoke_stage_value(seed_ledger, "screening"),
        _ALGORITHM_SMOKE_DEFAULT_SEED,
    )
    screening_cases = _select_runtime_smoke_screening_cases(
        _string_list(_runtime_smoke_stage_value(split_manifest, "screening")),
        _ALGORITHM_SMOKE_MAX_SCREENING_CASES,
    )
    for rel in screening_cases:
        add_case("screening", rel, screening_seed, case_source)
    return cases, missing


def _runtime_smoke_stage_value(source: Any, stage: str) -> Any:
    if source is None:
        return None
    if isinstance(source, Mapping):
        return source.get(stage)
    if stage == "canary":
        getter = getattr(source, "get_canary_cases", None)
        if callable(getter):
            try:
                return getter()
            except Exception:
                return None
        seed_getter = getattr(source, "get_canary_seeds", None)
        if callable(seed_getter):
            try:
                return seed_getter()
            except Exception:
                return None
    getter = getattr(source, "get_cases", None)
    if callable(getter):
        arguments = _runtime_smoke_stage_arguments(stage)
        for argument in arguments:
            try:
                return getter(argument)
            except Exception:
                continue
    seed_getter = getattr(source, "get_seeds", None)
    if callable(seed_getter):
        arguments = _runtime_smoke_stage_arguments(stage)
        for argument in arguments:
            try:
                return seed_getter(argument)
            except Exception:
                continue
    try:
        return getattr(source, stage)
    except Exception:
        return None


def _runtime_smoke_stage_arguments(stage: str) -> tuple[Any, ...]:
    enum_stage = getattr(ExperimentStage, stage.upper(), None)
    if enum_stage is None:
        return (stage,)
    return (enum_stage, stage)


def _select_runtime_smoke_screening_cases(paths: list[str], max_cases: int) -> list[str]:
    cases = [path for path in paths if str(path or "").strip()]
    total = len(cases)
    if max_cases <= 0 or total <= 0:
        return []
    if max_cases >= total:
        return cases
    if max_cases == 1:
        return [cases[total // 2]]

    indices = [round(i * (total - 1) / (max_cases - 1)) for i in range(max_cases)]
    selected: list[int] = []
    seen: set[int] = set()
    for idx in indices:
        if idx in seen:
            continue
        selected.append(idx)
        seen.add(idx)
    for idx in range(total):
        if len(selected) >= max_cases:
            break
        if idx in seen:
            continue
        selected.append(idx)
        seen.add(idx)
    return [cases[idx] for idx in sorted(selected[:max_cases])]


def _load_runtime_smoke_yaml(
    *,
    workspace: Path,
    base_workspace: Path,
    filename: str,
) -> Mapping[str, Any]:
    for root in (workspace, base_workspace):
        path = root / filename
        if not path.is_file():
            continue
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            return {}
        if isinstance(payload, Mapping):
            return payload
        return {}
    return {}


def _first_int(value: Any, default: int) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, (str, bytes)):
        candidates = [value]
    elif isinstance(value, (list, tuple)):
        candidates = list(value)
    else:
        candidates = []
    for item in candidates:
        try:
            return int(item)
        except (TypeError, ValueError):
            continue
    return default


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if not isinstance(value, (list, tuple)):
        return []
    result: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if text:
            result.append(text)
    return result


def _runtime_smoke_safe_data_roots(context: ProposalToolContext) -> tuple[Path, ...]:
    roots: list[Any] = []
    for source in (
        getattr(context, "split_manifest", None),
        getattr(context, "problem_spec", None),
        _attr(getattr(context, "adapter", None), "spec"),
    ):
        roots.extend(_runtime_smoke_safe_data_roots_from_manifest(source))
    return _normalize_runtime_smoke_safe_roots(roots)


def _runtime_smoke_safe_data_roots_from_manifest(source: Any) -> list[Any]:
    if source is None:
        return []
    values: list[Any] = []
    keys = (
        "safe_data_roots",
        "safe_data_root",
        "data_roots",
        "data_root",
        "problem_data_roots",
        "problem_data_root",
    )
    for key in keys:
        value = _attr(source, key)
        if value in (None, "", [], ()):
            continue
        if isinstance(value, Mapping):
            values.extend(value.values())
        elif isinstance(value, (list, tuple, set)):
            values.extend(value)
        else:
            values.append(value)
    return values


def _normalize_runtime_smoke_safe_roots(value: Any) -> tuple[Path, ...]:
    if value in (None, "", [], ()):
        return ()
    raw_values = value if isinstance(value, (list, tuple, set)) else (value,)
    roots: list[Path] = []
    seen: set[str] = set()
    for item in raw_values:
        text = str(item or "").strip()
        if not text:
            continue
        root = Path(text).expanduser().resolve(strict=False)
        key = str(root)
        if key in seen:
            continue
        seen.add(key)
        roots.append(root)
    return tuple(roots)


def _runtime_smoke_case_source(split_manifest: Any) -> str:
    if split_manifest is None:
        return "workspace_split_manifest"
    source = str(_attr(split_manifest, "source") or "").strip()
    if source:
        return source
    if isinstance(split_manifest, Mapping):
        return "campaign_config_manifest"
    return "campaign_split_manifest"


def _runtime_smoke_relative_path(case_rel: str) -> Path | None:
    text = str(case_rel or "").replace("\\", "/").strip()
    if not text:
        return None
    pure = PurePosixPath(text)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        return None
    return Path(*pure.parts)


def _runtime_smoke_candidate_within_root(
    path: Path,
    *,
    workspace: Path,
    base_workspace: Path,
    safe_data_roots: Any,
) -> bool:
    candidate = path.expanduser().resolve(strict=False)
    roots = (
        workspace.expanduser().resolve(strict=False),
        base_workspace.expanduser().resolve(strict=False),
        *_normalize_runtime_smoke_safe_roots(safe_data_roots),
    )
    for root in roots:
        try:
            candidate.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def _runtime_smoke_audited_manifest_ref(
    *,
    workspace: Path,
    base_workspace: Path,
    rel_path: str,
) -> str | None:
    for root in (workspace, base_workspace):
        root = root.expanduser().resolve(strict=False)
        for manifest_path in sorted(root.glob("**/manifests/*.json")):
            try:
                payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(payload, Mapping):
                continue
            if payload.get("schema") != "scion.cvrp_case_manifest.v1":
                continue
            cases = payload.get("cases")
            if not isinstance(cases, list):
                continue
            for case in cases:
                if not isinstance(case, Mapping):
                    continue
                if str(case.get("source_path") or "").strip() != rel_path:
                    continue
                try:
                    return manifest_path.relative_to(root).as_posix()
                except ValueError:
                    return "problem_case_manifest"
    return None


def _runtime_smoke_case_public_payload(
    smoke_case: _RuntimeSmokeCase,
) -> dict[str, Any]:
    case_ref = f"{smoke_case.data_root_source}:{smoke_case.rel_path}"
    provenance = {
        "source": smoke_case.case_source,
        "case_path_ref": case_ref,
        "data_root_source": smoke_case.data_root_source,
        "data_root_status": smoke_case.data_root_status,
        "absolute_paths_exposed": False,
    }
    return {
        "case": smoke_case.rel_path,
        "resolved_case_path": smoke_case.rel_path,
        "case_path_ref": case_ref,
        "data_root": smoke_case.data_root,
        "data_root_source": smoke_case.data_root_source,
        "data_root_status": smoke_case.data_root_status,
        "provenance": provenance,
    }


def _runtime_smoke_payload_provenance(
    representative: Mapping[str, Any],
) -> dict[str, Any]:
    provenance = representative.get("provenance")
    if isinstance(provenance, Mapping):
        result = dict(provenance)
    else:
        result = {
            "source": "runtime_smoke_manifest",
            "absolute_paths_exposed": False,
        }
    result.setdefault("absolute_paths_exposed", False)
    return result


def _resolve_smoke_instance_path(
    *,
    workspace: Path,
    base_workspace: Path,
    case_rel: str,
    safe_data_roots: Any = None,
) -> Path | None:
    return _resolve_smoke_instance(
        workspace=workspace,
        base_workspace=base_workspace,
        case_rel=case_rel,
        safe_data_roots=safe_data_roots,
    )["path"]


def _resolve_smoke_instance(
    *,
    workspace: Path,
    base_workspace: Path,
    case_rel: str,
    safe_data_roots: Any = None,
    case_source: str = "runtime_smoke_manifest",
) -> dict[str, Any]:
    rel = _runtime_smoke_relative_path(case_rel)
    if rel is None:
        path = Path(str(case_rel or ""))
        source = "rejected_absolute_path" if path.is_absolute() else "rejected_case_path"
        status = "absolute_path_rejected" if path.is_absolute() else "unsafe_relative_rejected"
        return {
            "path": None,
            "data_root": None,
            "data_root_source": source,
            "data_root_status": status,
        }
    candidates: list[tuple[Path, str | None, str, str]] = []
    candidates.append(
        (workspace / rel, "workspace", "workspace", "safe_root_relative")
    )
    candidates.append(
        (
            base_workspace / rel,
            "base_workspace",
            "base_workspace",
            "safe_root_relative",
        )
    )
    for index, safe_root in enumerate(
        _normalize_runtime_smoke_safe_roots(safe_data_roots)
    ):
        candidates.append(
            (
                safe_root / rel,
                f"safe_data_root:{index}",
                "safe_data_root",
                "safe_root_relative",
            )
        )
    for path, data_root, source, status in candidates:
        if not _runtime_smoke_candidate_within_root(
            path,
            workspace=workspace,
            base_workspace=base_workspace,
            safe_data_roots=safe_data_roots,
        ):
            continue
        if path.is_file():
            manifest_ref = _runtime_smoke_audited_manifest_ref(
                workspace=workspace,
                base_workspace=base_workspace,
                rel_path=rel.as_posix(),
            )
            if manifest_ref:
                source = "audited_problem_data_manifest"
                status = "audited_manifest_relative"
                data_root = manifest_ref
            return {
                "path": path,
                "data_root": data_root,
                "data_root_source": source,
                "data_root_status": status,
            }
    return {
        "path": None,
        "data_root": None,
        "data_root_source": case_source,
        "data_root_status": "missing",
    }


def _run_solver_design_smoke(
    *,
    workspace: Path,
    smoke_case: _RuntimeSmokeCase,
    registry_path: Path,
    selected_surface: str,
) -> tuple[Mapping[str, Any] | None, dict[str, Any]]:
    from scion.runtime.runner import ResourceLimits
    from scion.runtime.subprocess_runner import LocalSubprocessRunner

    runner = LocalSubprocessRunner(
        ResourceLimits(timeout_sec=_ALGORITHM_SMOKE_TIMEOUT_SEC, memory_mb=2048)
    )
    result = runner.run_solver(
        workdir=str(workspace),
        instance_path=str(smoke_case.path),
        seed=smoke_case.seed,
        time_limit_sec=_ALGORITHM_SMOKE_TIME_LIMIT_SEC,
        registry_path=str(registry_path),
        selected_surface=selected_surface,
    )
    run_payload = {
        **_runtime_smoke_case_public_payload(smoke_case),
        "seed": smoke_case.seed,
        "label": smoke_case.label,
        "success": result.success,
        "exit_code": result.exit_code,
        "elapsed_ms": result.elapsed_ms,
        "error_category": result.error_category,
        "stdout": _redact_runtime_smoke_paths(
            _limit_text(result.stdout or "", 800),
            workspace,
            smoke_case.path,
        ),
        "stderr": _redact_runtime_smoke_paths(
            _limit_text(result.stderr or "", 800),
            workspace,
            smoke_case.path,
        ),
    }
    if not result.success or result.output_path is None:
        detail = _redact_runtime_smoke_paths(
            _solver_run_failure_detail(result),
            workspace,
            smoke_case.path,
        )
        run_payload["detail"] = detail
        return None, run_payload
    try:
        with open(result.output_path, encoding="utf-8") as f:
            raw = json.load(f)
    except Exception as exc:
        run_payload["detail"] = f"could not read solver output: {exc}"
        return None, run_payload
    run_payload["detail"] = "solver smoke completed"
    return raw, run_payload


def _solver_run_failure_detail(result: Any) -> str:
    parts = [
        "solver run failed",
        f"exit_code={getattr(result, 'exit_code', None)}",
    ]
    error_category = getattr(result, "error_category", None)
    if error_category:
        parts.append(f"error_category={error_category}")
    elapsed_ms = getattr(result, "elapsed_ms", None)
    if elapsed_ms is not None:
        parts.append(f"elapsed_ms={elapsed_ms}")
    stderr = str(getattr(result, "stderr", "") or "").strip()
    stdout = str(getattr(result, "stdout", "") or "").strip()
    if stderr:
        parts.append("stderr=" + _limit_text(stderr, 1200))
    if stdout:
        parts.append("stdout=" + _limit_text(stdout, 1200))
    return "; ".join(parts)


def _redact_runtime_smoke_paths(text: str, *paths: Path) -> str:
    redacted = str(text or "")
    replacements = {
        str(path.expanduser().resolve(strict=False)): "<runtime_smoke_path>"
        for path in paths
        if path is not None
    }
    for raw, marker in sorted(replacements.items(), key=lambda item: -len(item[0])):
        if raw:
            redacted = redacted.replace(raw, marker)
    return redacted


def _runtime_smoke_audit_failure(
    raw: Mapping[str, Any],
    *,
    context: ProposalToolContext,
    selected_surface: str,
) -> Mapping[str, Any] | None:
    from scion.runtime.audit import runtime_audit_failure_from_raw

    problem_spec = _problem_spec_for_runtime_audit(context.problem_spec)
    return runtime_audit_failure_from_raw(
        raw,
        problem_spec=problem_spec,
        selected_surface=selected_surface,
    )


def _problem_spec_for_runtime_audit(problem_spec: Any) -> Any:
    if (
        str(_attr(problem_spec, "spec_version", "") or "") == "problem-v1"
        and _attr(problem_spec, "id") is not None
    ):
        return legacy_problem_spec_from_v1(problem_spec)
    return problem_spec


def _compact_runtime_smoke_payload(runtime: Any) -> dict[str, Any]:
    if not isinstance(runtime, Mapping):
        return {}
    keys = (
        "solver_algorithm_path",
        "solver_algorithm_loaded",
        "solver_algorithm_active",
        "solver_algorithm_errors",
        "solver_algorithm_events",
        "solver_algorithm_elapsed_ms",
        "solver_algorithm_solution_valid",
        "solver_algorithm_total_distance",
        "solver_algorithm_fleet_violation",
        "solver_algorithm_baseline_calls",
        "solver_algorithm_baseline_errors",
        "solver_algorithm_search_iterations",
        "solver_algorithm_move_attempts",
        "solver_algorithm_accepted_moves",
        "solver_algorithm_improving_moves",
        "solver_algorithm_neutral_accepted_moves",
        "solver_algorithm_best_improving_moves",
        "solver_algorithm_best_delta",
        "solver_algorithm_phase_delta_sum",
        "solver_algorithm_phase_best_delta",
        "solver_algorithm_phase_improvement_counts",
        "solver_algorithm_stop_reason",
    )
    return {key: runtime.get(key) for key in keys if key in runtime}


def _compact_runtime_audit_failure(value: Mapping[str, Any]) -> dict[str, Any]:
    keys = (
        "error_category",
        "detail",
        "failed_runtime_fields",
        "solver_algorithm_errors",
        "solver_algorithm_events",
    )
    return {key: value.get(key) for key in keys if key in value}


def _solver_design_micro_benchmark_result(
    *,
    candidate_raw: Mapping[str, Any],
    candidate_run: Mapping[str, Any],
    champion_raw: Mapping[str, Any] | None,
    champion_run: Mapping[str, Any],
    smoke_case: _RuntimeSmokeCase,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "case": smoke_case.rel_path,
        "seed": smoke_case.seed,
        "label": smoke_case.label,
        "candidate_elapsed_ms": candidate_run.get("elapsed_ms"),
        "champion_elapsed_ms": champion_run.get("elapsed_ms"),
    }
    if champion_raw is None:
        result.update(
            {
                "comparison": "incomparable",
                "champion_failed": True,
                "champion_error_category": champion_run.get("error_category"),
                "champion_detail": _limit_text(
                    str(champion_run.get("detail") or ""),
                    320,
                ),
            }
        )
        return result

    comparison = _compare_solver_design_raw_outputs(candidate_raw, champion_raw)
    result.update(comparison)
    try:
        result["runtime_delta_ms"] = int(candidate_run.get("elapsed_ms") or 0) - int(
            champion_run.get("elapsed_ms") or 0
        )
    except (TypeError, ValueError):
        pass
    return result


def _compare_solver_design_raw_outputs(
    candidate_raw: Mapping[str, Any],
    champion_raw: Mapping[str, Any],
) -> dict[str, Any]:
    candidate_obj = candidate_raw.get("objective")
    champion_obj = champion_raw.get("objective")
    if not isinstance(candidate_obj, Mapping) or not isinstance(champion_obj, Mapping):
        return {"comparison": "incomparable"}
    candidate_fleet = _float_or_none(candidate_obj.get("fleet_violation"))
    champion_fleet = _float_or_none(champion_obj.get("fleet_violation"))
    candidate_distance = _float_or_none(candidate_obj.get("total_distance"))
    champion_distance = _float_or_none(champion_obj.get("total_distance"))
    comparison = "tie"
    delta = 0.0
    decisive_metric = "total_distance"
    if candidate_fleet is not None and champion_fleet is not None:
        fleet_delta = champion_fleet - candidate_fleet
        if abs(fleet_delta) > 1e-9:
            comparison = "win" if fleet_delta > 0 else "loss"
            delta = fleet_delta
            decisive_metric = "fleet_violation"
    if comparison == "tie" and candidate_distance is not None and champion_distance is not None:
        distance_delta = champion_distance - candidate_distance
        if abs(distance_delta) > 1e-9:
            comparison = "win" if distance_delta > 0 else "loss"
            delta = distance_delta
        else:
            delta = 0.0
    return {
        "comparison": comparison,
        "delta": delta,
        "decisive_metric": decisive_metric,
        "candidate_objective": {
            key: candidate_obj.get(key)
            for key in ("fleet_violation", "total_distance")
            if key in candidate_obj
        },
        "champion_objective": {
            key: champion_obj.get(key)
            for key in ("fleet_violation", "total_distance")
            if key in champion_obj
        },
    }


def _solver_design_micro_benchmark_issue(
    micro_results: list[dict[str, Any]],
) -> str | None:
    comparable = [
        result
        for result in micro_results
        if result.get("comparison") in {"win", "loss", "tie"}
    ]
    if not comparable:
        return None
    losses = sum(1 for result in comparable if result.get("comparison") == "loss")
    wins = sum(1 for result in comparable if result.get("comparison") == "win")
    ties = sum(1 for result in comparable if result.get("comparison") == "tie")
    if losses == len(comparable) and wins == 0 and ties == 0:
        return (
            "tainted micro-benchmark objective regression: candidate lost all "
            f"{len(comparable)} comparable smoke case(s) against the current champion"
        )
    return None


def _solver_design_zero_effort_issue(
    *,
    patch: PatchProposal,
    hypothesis: HypothesisProposal | None,
    runs: list[dict[str, Any]],
    provider: Any | None = None,
) -> str | None:
    checker = getattr(provider, "zero_effort_issue", None)
    if callable(checker):
        return checker(patch=patch, hypothesis=hypothesis, runs=runs)
    return None


def _solver_design_low_effort_issue(
    *,
    patch: PatchProposal,
    hypothesis: HypothesisProposal | None,
    runs: list[dict[str, Any]],
    micro_results: list[dict[str, Any]],
    provider: Any | None = None,
) -> str | None:
    checker = getattr(provider, "low_effort_issue", None)
    if callable(checker):
        return checker(
            patch=patch,
            hypothesis=hypothesis,
            runs=runs,
            micro_results=micro_results,
        )
    return None


def _solver_design_patch_claims_search_effort(
    patch: PatchProposal,
    hypothesis: HypothesisProposal | None,
    *,
    provider: Any | None = None,
) -> bool:
    checker = getattr(provider, "patch_claims_search_effort", None)
    if callable(checker):
        return bool(checker(patch, hypothesis))
    return False


def _solver_design_patch_paths(patch: PatchProposal) -> list[str]:
    paths: list[str] = []
    for change in patch_file_changes(patch):
        try:
            path = normalize_relative_patch_path(change.file_path)
        except ValueError:
            path = str(change.file_path or "")
        if path:
            paths.append(path)
    return paths


def _solver_design_smoke_runtime_underspent(
    run: Mapping[str, Any],
    *,
    micro_by_case_seed: Mapping[tuple[str, int], Mapping[str, Any]],
) -> bool:
    elapsed = _nonnegative_int((run.get("run") or {}).get("elapsed_ms"))
    if elapsed <= 0:
        return False

    key = (str(run.get("case") or ""), _nonnegative_int(run.get("seed")))
    micro = micro_by_case_seed.get(key)
    if isinstance(micro, Mapping):
        champion_elapsed = _nonnegative_int(micro.get("champion_elapsed_ms"))
        if champion_elapsed > 0:
            return (
                elapsed / champion_elapsed
                <= _ALGORITHM_SMOKE_LOW_EFFORT_MAX_RUNTIME_RATIO
            )
    return (
        elapsed
        <= int(
            _ALGORITHM_SMOKE_TIME_LIMIT_SEC
            * 1000
            * _ALGORITHM_SMOKE_LOW_EFFORT_MAX_RUNTIME_RATIO
        )
    )


def _runtime_stop_reason(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text or "unknown"


def _nonnegative_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _compact_solver_design_micro_benchmark(
    micro_results: list[dict[str, Any]],
) -> dict[str, Any]:
    comparable = [
        result
        for result in micro_results
        if result.get("comparison") in {"win", "loss", "tie"}
    ]
    wins = sum(1 for result in comparable if result.get("comparison") == "win")
    losses = sum(1 for result in comparable if result.get("comparison") == "loss")
    ties = sum(1 for result in comparable if result.get("comparison") == "tie")
    return {
        "non_promotional": True,
        "tainted_debug": True,
        "comparable_cases": len(comparable),
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "results": [
            {
                key: result.get(key)
                for key in (
                    "label",
                    "case",
                    "seed",
                    "comparison",
                    "delta",
                    "decisive_metric",
                    "runtime_delta_ms",
                )
                if key in result
            }
            for result in micro_results[:_ALGORITHM_SMOKE_MAX_SCREENING_CASES + 1]
        ],
    }


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _solver_design_smoke_repair_guidance(
    audit_failure: Mapping[str, Any],
    *,
    runtime: Any,
    run_payload: Any,
    provider: Any | None = None,
) -> list[str]:
    renderer = getattr(provider, "runtime_smoke_repair_guidance", None)
    if callable(renderer):
        return list(
            renderer(audit_failure, runtime=runtime, run_payload=run_payload)
        )
    if audit_failure.get("error_category") == "solver_algorithm_runtime_error":
        return [
            "Failure occurred inside the candidate solver_design solve path during tainted algorithm smoke; repair the candidate algorithm code, not protocol or adapter files."
        ]
    return []


def _attr(value: Any, name: str, default: Any = None) -> Any:
    if value is None:
        return default
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _normalize_solver_design_surface(value: Any) -> str:
    surface = str(value or "").strip()
    if surface == "solver_algorithm":
        return "solver_design"
    return surface


def _normalize_rel_path(path: str) -> str | None:
    raw_path = str(path).replace(os.sep, "/")
    if raw_path.startswith("/"):
        return None
    raw = raw_path
    if not raw or raw in {".", ".."}:
        return None
    parts = PurePosixPath(raw).parts
    if any(part in {"..", ""} for part in parts):
        return None
    return "/".join(parts)


def _limit_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    suffix = "\n[truncated by proposal tool result budget]"
    return text[: max(0, max_chars - len(suffix))] + suffix
