"""Independent frozen comparison of ordinary champion snapshot copies."""

from __future__ import annotations

import json
import math
import re
import shutil
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, replace
from numbers import Real
from pathlib import Path
from typing import Any

from scion.core.models import ExperimentStage, RunResult
from scion.runtime.runner import Runner

MANIFEST_SCHEMA_VERSION = "scion.champion_heldout_comparison_manifest.v1"
SUMMARY_SCHEMA_VERSION = "scion.champion_heldout_comparison_summary.v1"
DEFAULT_SUMMARY_FILENAME = "champion_heldout_comparison_summary.v1.json"
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")


class InfeasibleAsFailureRunner:
    def __init__(self, delegate: Runner, *, metric_names: Sequence[str]) -> None:
        self.delegate = delegate
        self.metric_names = tuple(metric_names)

    def run_solver(
        self,
        workdir: str,
        instance_path: str,
        seed: int,
        time_limit_sec: int,
        registry_path: str,
        selected_surface: str | None = None,
    ) -> RunResult:
        result = self.delegate.run_solver(
            workdir=workdir,
            instance_path=instance_path,
            seed=seed,
            time_limit_sec=time_limit_sec,
            registry_path=registry_path,
            selected_surface=selected_surface,
        )
        category = self._failure_category(result)
        return (
            replace(result, success=False, error_category=category)  # type: ignore[arg-type]
            if category
            else result
        )

    def _failure_category(self, result: RunResult) -> str | None:
        if not result.success:
            return None
        if result.output is None:
            return "missing_solver_output"
        if not result.output.feasible:
            return "infeasible_solution"
        for name in self.metric_names:
            if name not in result.output.objective:
                return "missing_objective_metric"
            value = result.output.objective[name]
            if isinstance(value, bool) or not isinstance(value, Real):
                return "invalid_objective_metric"
            if not math.isfinite(float(value)):
                return "nonfinite_objective_metric"
        return None


def execute_champion_heldout_comparison(
    manifest_path: str | Path,
    *,
    output_dir: str | Path,
    protocol_factory: Callable[..., Any] | None = None,
) -> Path:
    """Run manifest groups and atomically retain each completed result."""
    manifest_file = Path(manifest_path).expanduser().resolve()
    common, groups = _load_inputs(manifest_file)
    destination = Path(output_dir).expanduser().resolve()
    workspace_root = destination / "workspaces"
    metrics_root = destination / "metrics"
    workspace_root.mkdir(parents=True, exist_ok=True)
    metrics_root.mkdir(exist_ok=True)
    summary_path = destination / DEFAULT_SUMMARY_FILENAME
    summary: dict[str, Any] = {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "evaluation_only": True,
        "stage": "frozen",
        "status": "running",
        "manifest_path": str(manifest_file),
        "output_dir": str(destination),
        "group_count": len(groups),
        "groups": [],
    }
    _update_summary(summary, summary_path)
    for group in groups:
        summary["groups"].append(
            _run_group(
                group,
                common=common,
                workspace_root=workspace_root,
                metrics_root=metrics_root,
                protocol_factory=protocol_factory,
            )
        )
        if len(summary["groups"]) == len(groups):
            summary["status"] = "completed"
        _update_summary(summary, summary_path)
    return summary_path


def build_champion_heldout_protocol(
    *,
    problem_yaml_path: str | Path,
    protocol_path: str | Path,
    split_path: str | Path,
    seeds_path: str | Path,
    metrics_dir: str | Path,
    time_limit_sec: int,
) -> Any:
    """Build the ProblemSpecV1-backed, cache-free frozen Protocol."""
    from scion.config.problem import ProtocolConfig, SeedLedgerConfig, SplitManifest
    from scion.problem.bridge import (
        bridge_problem_spec_v1,
        load_problem_spec_v1_from_yaml,
    )
    from scion.protocol.experiment import ExperimentProtocol, SeedLedger, SplitManager
    from scion.runtime.runner import ResourceLimits
    from scion.runtime.subprocess_runner import LocalSubprocessRunner

    bridge = bridge_problem_spec_v1(load_problem_spec_v1_from_yaml(problem_yaml_path))
    config = ProtocolConfig.from_yaml(protocol_path).with_problem_measurement(
        bridge.problem_spec, governance_mode="on"
    )
    split = SplitManifest.from_yaml(split_path)
    seeds = SeedLedgerConfig.from_yaml(seeds_path)
    declared = (config.frozen.n_cases, config.frozen.n_seeds)
    actual = (len(split.frozen), len(seeds.frozen))
    if declared != actual:
        raise ValueError(
            "held-out comparison requires the complete frozen matrix: "
            f"protocol={declared[0]}/{declared[1]}, split/ledger={actual[0]}/{actual[1]}"
        )
    limit = time_limit_sec
    runner = InfeasibleAsFailureRunner(
        LocalSubprocessRunner(ResourceLimits(timeout_sec=limit + 15)),
        metric_names=tuple(metric.name for metric in bridge.metric_specs),
    )
    protocol = ExperimentProtocol(
        protocol_config=config,
        split_manager=SplitManager(split),
        seed_ledger=SeedLedger(seeds),
        runner=runner,
        time_limit_sec=limit,
        metrics_dir=str(Path(metrics_dir).resolve()),
        metric_specs=bridge.metric_specs,
        objective_policy=bridge.objective_policy,
        require_metric_specs=True,
        problem_spec=bridge.problem_spec,
        champion_result_cache_enabled=False,
    )
    selected = (
        protocol._select_cases(ExperimentStage.FROZEN, "modify", 0),
        protocol._select_seeds(ExperimentStage.FROZEN),
    )
    if selected != (list(split.frozen), list(seeds.frozen)):
        raise ValueError("Protocol selection differs from the complete frozen matrix")
    return protocol


def _run_group(
    group: Mapping[str, Any],
    *,
    common: Mapping[str, Any],
    workspace_root: Path,
    metrics_root: Path,
    protocol_factory: Callable[..., Any] | None,
) -> dict[str, Any]:
    comparison_id = str(group["comparison_id"])
    candidate = workspace_root / comparison_id / "candidate"
    champion = workspace_root / comparison_id / "champion"
    base = {
        "comparison_id": comparison_id,
        "workspace_mode": "ordinary_copy",
        "candidate_workspace": str(candidate),
        "champion_workspace": str(champion),
    }
    try:
        shutil.copytree(group["candidate_workspace"], candidate)
        shutil.copytree(group["champion_workspace"], champion)
        protocol = (protocol_factory or build_champion_heldout_protocol)(
            **common, metrics_dir=metrics_root / comparison_id
        )
        canary = {
            "candidate": _canary(protocol, candidate, champion),
            "champion": _canary(protocol, champion, candidate),
        }
        canary["passed"] = all(
            item.get("status") == "completed" and item.get("passed") is True
            for item in canary.values()
        )
        if not canary["passed"]:
            return {
                **base,
                "status": "execution-invalid",
                "canary_safety_diagnostic": canary,
                "formal": {"status": "not-run", "reason_code": "CANARY_SAFETY_VETO"},
                "supports_candidate": False,
            }
        formal = _formal(
            protocol.run_experiment(
                ExperimentStage.FROZEN, str(candidate), str(champion), "modify"
            )
        )
        return {
            **base,
            "status": "completed",
            "canary_safety_diagnostic": canary,
            "formal": formal,
            "supports_candidate": _supports(formal),
        }
    except Exception as exc:  # noqa: BLE001 - retain group-local failure
        return {
            **base,
            "status": "error",
            "error": {"type": type(exc).__name__, "message": str(exc)},
            "supports_candidate": False,
        }


def _canary(protocol: Any, subject: Path, comparison: Path) -> dict[str, Any]:
    try:
        result = protocol.run_canary(str(subject), str(comparison))
        return {
            "status": "completed",
            "passed": bool(result.passed),
            "reason": result.reason,
            "details": dict(result.details or {}),
        }
    except Exception as exc:  # noqa: BLE001 - canary exception is a veto fact
        return {
            "status": "error",
            "passed": False,
            "error": {"type": type(exc).__name__, "message": str(exc)},
        }


def _formal(result: Any) -> dict[str, Any]:
    if result.stats is None:
        raise ValueError("frozen Protocol result is missing stats")
    return {
        "stage": result.stage.value,
        "gate_outcome": result.gate_outcome,
        "reason_codes": list(result.reason_codes),
        "objective_semantics": result.objective_semantics,
        "case_ids": list(result.case_ids),
        "seed_set": list(result.seed_set),
        "raw_metrics_ref": result.raw_metrics_ref,
        "stats": asdict(result.stats),
    }


def _supports(formal: Mapping[str, Any]) -> bool:
    stats = formal["stats"]
    cases, seeds = formal["case_ids"], formal["seed_set"]
    n_cases, n_pairs = len(cases), len(cases) * len(seeds)
    return bool(
        formal["gate_outcome"] == "pass"
        and "FROZEN_PASS_HIERARCHICAL" in formal["reason_codes"]
        and n_pairs > 0
        and stats.get("n_cases") == n_cases
        and _total(stats, ("wins", "losses", "ties")) == n_cases
        and _total(stats, ("pair_wins", "pair_losses", "pair_ties")) == n_pairs
        and all(
            stats.get(name) == n_pairs
            for name in ("total_pairs", "attempted_pairs", "valid_pairs")
        )
        and all(
            stats.get(name) == 0
            for name in (
                "failed_pairs",
                "candidate_failed_pairs",
                "champion_failed_pairs",
            )
        )
    )


def _total(stats: Mapping[str, Any], names: Sequence[str]) -> int | None:
    values = [stats.get(name) for name in names]
    if any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0
        for value in values
    ):
        return None
    return sum(values)


def _load_inputs(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(manifest, Mapping)
        or manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION
    ):
        raise ValueError(f"manifest must use {MANIFEST_SCHEMA_VERSION}")
    base = path.parent

    def resolved(
        payload: Mapping[str, Any], key: str, *, directory: bool = False
    ) -> Path:
        value = str(payload.get(key) or "").strip()
        raw = Path(value)
        candidate = (base / raw if value and not raw.is_absolute() else raw).resolve()
        exists = candidate.is_dir() if directory else candidate.is_file()
        if not value or not exists:
            raise FileNotFoundError(f"{key} not found: {candidate}")
        return candidate

    time_limit = manifest.get("time_limit_sec")
    if (
        isinstance(time_limit, bool)
        or not isinstance(time_limit, int)
        or time_limit <= 0
    ):
        raise ValueError("time_limit_sec must be a positive integer")
    common = {
        "problem_yaml_path": resolved(manifest, "problem_yaml"),
        "protocol_path": resolved(manifest, "protocol"),
        "split_path": resolved(manifest, "split_manifest"),
        "seeds_path": resolved(manifest, "seed_ledger"),
        "time_limit_sec": time_limit,
    }
    raw_groups = manifest.get("groups")
    if not isinstance(raw_groups, list) or not raw_groups:
        raise ValueError("groups must be a non-empty array")
    groups, seen = [], set()
    for raw in raw_groups:
        if not isinstance(raw, Mapping):
            raise ValueError("each comparison group must be an object")  # noqa: TRY004
        comparison_id = str(raw.get("comparison_id") or "").strip()
        if not _ID_RE.fullmatch(comparison_id) or comparison_id in seen:
            raise ValueError(f"invalid or duplicate comparison_id: {comparison_id!r}")
        seen.add(comparison_id)
        groups.append(
            {
                "comparison_id": comparison_id,
                "candidate_workspace": resolved(
                    raw, "candidate_workspace", directory=True
                ),
                "champion_workspace": resolved(
                    raw, "champion_workspace", directory=True
                ),
            }
        )
    return common, groups


def _update_summary(summary: dict[str, Any], path: Path) -> None:
    groups = summary["groups"]
    summary.update(
        completed_group_count=sum(g["status"] == "completed" for g in groups),
        execution_invalid_group_count=sum(
            g["status"] == "execution-invalid" for g in groups
        ),
        error_group_count=sum(g["status"] == "error" for g in groups),
        candidate_supported_group_count=sum(
            bool(g.get("supports_candidate")) for g in groups
        ),
        all_groups_supported=(
            bool(groups)
            and len(groups) == summary["group_count"]
            and all(g.get("supports_candidate") for g in groups)
        ),
    )
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(path)
