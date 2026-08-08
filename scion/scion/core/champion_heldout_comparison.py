"""Independent held-out comparison of ordinary champion snapshot copies.

This eval-only path deliberately bypasses the research campaign.  It loads a
ProblemSpecV1 and the problem-owned Protocol, records a symmetric canary safety
diagnostic, and runs only the frozen paired evaluation.  It does not create
hypotheses, request code, schedule branches, make decisions, or promote.
"""
from __future__ import annotations

import json
import math
import re
import shutil
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, replace
from datetime import datetime, timezone
from numbers import Real
from pathlib import Path
from typing import Any

from scion.core.models import ExperimentStage, RunResult
from scion.runtime.runner import Runner

MANIFEST_SCHEMA_VERSION = "scion.champion_heldout_comparison_manifest.v1"
GROUP_SCHEMA_VERSION = "scion.champion_heldout_comparison_group.v1"
SUMMARY_SCHEMA_VERSION = "scion.champion_heldout_comparison_summary.v1"
DEFAULT_SUMMARY_FILENAME = "champion_heldout_comparison_summary.v1.json"

_COMPARISON_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")


class InfeasibleAsFailureRunner:
    """Make an invalid solver output an explicit failure of that arm."""

    def __init__(
        self,
        delegate: Runner,
        *,
        metric_names: Sequence[str] = (),
    ) -> None:
        self.delegate = delegate
        self.metric_names = tuple(str(name) for name in metric_names)

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
        error_category = self._output_error_category(result)
        if error_category is not None:
            return replace(
                result,
                success=False,
                error_category=error_category,  # type: ignore[arg-type]
            )
        return result

    def _output_error_category(self, result: RunResult) -> str | None:
        if not result.success:
            return None
        if result.output is None:
            return "missing_solver_output"
        if not result.output.feasible:
            return "infeasible_solution"
        objective = result.output.objective
        for name in self.metric_names:
            if name not in objective:
                return "missing_objective_metric"
            value = objective[name]
            if isinstance(value, bool) or not isinstance(value, Real):
                return "invalid_objective_metric"
            if not math.isfinite(float(value)):
                return "nonfinite_objective_metric"
        return None

    def set_progress_callback(self, callback: Callable[..., None] | None) -> None:
        setter = getattr(self.delegate, "set_progress_callback", None)
        if callable(setter):
            setter(callback)

    def terminate_active_processes(self, *, reason: str = "shutdown") -> int:
        terminate = getattr(self.delegate, "terminate_active_processes", None)
        if not callable(terminate):
            return 0
        return int(terminate(reason=reason))


def execute_champion_heldout_comparison(
    manifest_path: str | Path,
    *,
    output_dir: str | Path,
    protocol_factory: Callable[..., Any] | None = None,
) -> Path:
    """Execute all comparison groups and return the total summary path."""

    manifest_file = Path(manifest_path).expanduser().resolve()
    manifest = _load_manifest(manifest_file)
    base_dir = manifest_file.parent
    common = _common_config(manifest, base_dir=base_dir)
    groups = _comparison_groups(manifest, base_dir=base_dir)

    destination = Path(output_dir).expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True)
    workspace_root = destination / "workspaces"
    result_root = destination / "groups"
    workspace_root.mkdir(exist_ok=True)
    result_root.mkdir(exist_ok=True)

    results: list[dict[str, Any]] = []
    for group in groups:
        group_result = _execute_group(
            group,
            common=common,
            workspace_root=workspace_root,
            result_root=result_root,
            protocol_factory=protocol_factory,
        )
        results.append(group_result)

    summary_path = destination / DEFAULT_SUMMARY_FILENAME
    summary = _summary_payload(
        manifest_path=manifest_file,
        output_dir=destination,
        groups=results,
    )
    _write_json(summary_path, summary)
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
    """Build the isolated production Protocol used by held-out comparison."""

    from scion.config.problem import ProtocolConfig, SeedLedgerConfig, SplitManifest
    from scion.problem.bridge import (
        bridge_problem_spec_v1,
        load_problem_spec_v1_from_yaml,
    )
    from scion.protocol.experiment import ExperimentProtocol, SeedLedger, SplitManager
    from scion.runtime.runner import ResourceLimits
    from scion.runtime.subprocess_runner import LocalSubprocessRunner

    problem_path = Path(problem_yaml_path).expanduser().resolve()
    problem_v1 = load_problem_spec_v1_from_yaml(problem_path)
    bridge = bridge_problem_spec_v1(problem_v1)
    config = ProtocolConfig.from_yaml(protocol_path).with_problem_measurement(
        bridge.problem_spec,
        governance_mode="on",
    )
    split = SplitManifest.from_yaml(split_path)
    seeds = SeedLedgerConfig.from_yaml(seeds_path)
    _validate_complete_frozen_matrix(
        protocol_config=config,
        split_manifest=split,
        seed_ledger=seeds,
    )
    limit = _positive_int(time_limit_sec, label="time_limit_sec")
    local_runner = LocalSubprocessRunner(ResourceLimits(timeout_sec=limit + 15))
    runner = InfeasibleAsFailureRunner(
        local_runner,
        metric_names=tuple(metric.name for metric in bridge.metric_specs),
    )
    protocol = ExperimentProtocol(
        protocol_config=config,
        split_manager=SplitManager(split),
        seed_ledger=SeedLedger(seeds),
        runner=runner,
        time_limit_sec=limit,
        metrics_dir=str(Path(metrics_dir).expanduser().resolve()),
        metric_specs=bridge.metric_specs,
        objective_policy=bridge.objective_policy,
        require_metric_specs=True,
        problem_spec=bridge.problem_spec,
        champion_result_cache_enabled=False,
    )
    selected_cases = protocol._select_cases(ExperimentStage.FROZEN, "modify", 0)
    selected_seeds = protocol._select_seeds(ExperimentStage.FROZEN)
    if selected_cases != list(split.frozen) or selected_seeds != list(seeds.frozen):
        raise ValueError(
            "held-out comparison requires the complete frozen matrix; "
            "Protocol selection differs from the declared frozen split or seeds"
        )
    return protocol


def _execute_group(
    group: Mapping[str, Any],
    *,
    common: Mapping[str, Any],
    workspace_root: Path,
    result_root: Path,
    protocol_factory: Callable[..., Any] | None,
) -> dict[str, Any]:
    comparison_id = str(group["comparison_id"])
    group_workspace = workspace_root / comparison_id
    group_result_dir = result_root / comparison_id
    group_result_dir.mkdir(parents=True, exist_ok=False)
    result_path = group_result_dir / "comparison.json"
    base = {
        "schema_version": GROUP_SCHEMA_VERSION,
        "comparison_id": comparison_id,
        "evaluation_only": True,
        "stage": "frozen",
        "candidate_label": group["candidate_label"],
        "champion_label": group["champion_label"],
        "selected_surface": group.get("selected_surface"),
        "workspace_mode": "ordinary_copy",
        "result_path": str(result_path),
    }
    try:
        candidate_copy = group_workspace / "candidate"
        champion_copy = group_workspace / "champion"
        shutil.copytree(group["candidate_workspace"], candidate_copy)
        shutil.copytree(group["champion_workspace"], champion_copy)

        factory = protocol_factory or build_champion_heldout_protocol
        protocol = factory(
            problem_yaml_path=common["problem_yaml_path"],
            protocol_path=common["protocol_path"],
            split_path=common["split_path"],
            seeds_path=common["seeds_path"],
            metrics_dir=group_result_dir / "metrics",
            time_limit_sec=common["time_limit_sec"],
        )
        selected_surface = group.get("selected_surface")
        canary = {
            "candidate": _canary_diagnostic(
                protocol,
                subject_workspace=candidate_copy,
                comparison_workspace=champion_copy,
                selected_surface=selected_surface,
            ),
            "champion": _canary_diagnostic(
                protocol,
                subject_workspace=champion_copy,
                comparison_workspace=candidate_copy,
                selected_surface=selected_surface,
            ),
        }
        canary["passed"] = all(
            item.get("status") == "completed" and item.get("passed") is True
            for item in (canary["candidate"], canary["champion"])
        )

        if not canary["passed"]:
            payload = {
                **base,
                "status": "execution-invalid",
                "completed_at": _utc_now_iso(),
                "candidate_workspace": str(candidate_copy),
                "champion_workspace": str(champion_copy),
                "canary_safety_diagnostic": canary,
                "formal": {
                    "status": "not-run",
                    "reason_code": "CANARY_SAFETY_VETO",
                },
                "supports_candidate": False,
            }
            _write_json(result_path, payload)
            return payload

        formal = protocol.run_experiment(
            ExperimentStage.FROZEN,
            str(candidate_copy),
            str(champion_copy),
            "modify",
            selected_surface=selected_surface,
        )
        formal_payload = _formal_payload(formal)
        supports_candidate = _formal_supports_candidate(
            canary_passed=bool(canary["passed"]),
            formal=formal_payload,
        )
        payload = {
            **base,
            "status": "completed",
            "completed_at": _utc_now_iso(),
            "candidate_workspace": str(candidate_copy),
            "champion_workspace": str(champion_copy),
            "canary_safety_diagnostic": canary,
            "formal": formal_payload,
            "supports_candidate": supports_candidate,
        }
    except Exception as exc:  # noqa: BLE001 - preserve a result for each group
        payload = {
            **base,
            "status": "error",
            "completed_at": _utc_now_iso(),
            "error": {"type": type(exc).__name__, "message": str(exc)},
            "supports_candidate": False,
        }
    _write_json(result_path, payload)
    return payload


def _canary_diagnostic(
    protocol: Any,
    *,
    subject_workspace: Path,
    comparison_workspace: Path,
    selected_surface: str | None,
) -> dict[str, Any]:
    try:
        result = protocol.run_canary(
            str(subject_workspace),
            str(comparison_workspace),
            selected_surface=selected_surface,
        )
        return {
            "status": "completed",
            "passed": bool(getattr(result, "passed", False)),
            "reason": getattr(result, "reason", None),
            "details": dict(getattr(result, "details", {}) or {}),
        }
    except Exception as exc:  # noqa: BLE001 - preserve the canary veto evidence
        return {
            "status": "error",
            "passed": False,
            "error": {"type": type(exc).__name__, "message": str(exc)},
        }


def _formal_payload(result: Any) -> dict[str, Any]:
    stats = getattr(result, "stats", None)
    if stats is None:
        raise ValueError("frozen Protocol result is missing stats")
    stats_payload = asdict(stats) if hasattr(stats, "__dataclass_fields__") else vars(stats)
    return {
        "stage": str(getattr(getattr(result, "stage", None), "value", "frozen")),
        "gate_outcome": str(getattr(result, "gate_outcome", "")),
        "reason_codes": list(getattr(result, "reason_codes", ()) or ()),
        "objective_semantics": str(getattr(result, "objective_semantics", "")),
        "case_ids": list(getattr(result, "case_ids", ()) or ()),
        "seed_set": list(getattr(result, "seed_set", ()) or ()),
        "raw_metrics_ref": str(getattr(result, "raw_metrics_ref", "")),
        "stats": stats_payload,
    }


def _formal_supports_candidate(
    *,
    canary_passed: bool,
    formal: Mapping[str, Any],
) -> bool:
    stats = formal.get("stats")
    if not isinstance(stats, Mapping):
        return False
    case_ids = formal.get("case_ids") or ()
    seed_set = formal.get("seed_set") or ()
    expected_cases = len(case_ids)
    expected_pairs = len(case_ids) * len(seed_set)
    return bool(
        canary_passed
        and formal.get("gate_outcome") == "pass"
        and "FROZEN_PASS_HIERARCHICAL" in (formal.get("reason_codes") or ())
        and expected_pairs > 0
        and stats.get("n_cases") == expected_cases
        and _count_total(stats, ("wins", "losses", "ties")) == expected_cases
        and _count_total(stats, ("pair_wins", "pair_losses", "pair_ties"))
        == expected_pairs
        and stats.get("total_pairs") == expected_pairs
        and stats.get("attempted_pairs") == expected_pairs
        and stats.get("valid_pairs") == expected_pairs
        and stats.get("failed_pairs") == 0
        and stats.get("candidate_failed_pairs") == 0
        and stats.get("champion_failed_pairs") == 0
    )


def _count_total(stats: Mapping[str, Any], names: Sequence[str]) -> int | None:
    values = [stats.get(name) for name in names]
    if any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0
        for value in values
    ):
        return None
    return sum(values)


def _common_config(manifest: Mapping[str, Any], *, base_dir: Path) -> dict[str, Any]:
    return {
        "problem_yaml_path": _required_file(manifest, "problem_yaml", base_dir),
        "protocol_path": _required_file(manifest, "protocol", base_dir),
        "split_path": _required_file(manifest, "split_manifest", base_dir),
        "seeds_path": _required_file(manifest, "seed_ledger", base_dir),
        "time_limit_sec": _positive_int(
            manifest.get("time_limit_sec"),
            label="time_limit_sec",
        ),
    }


def _validate_complete_frozen_matrix(
    *,
    protocol_config: Any,
    split_manifest: Any,
    seed_ledger: Any,
) -> None:
    frozen_cases = list(split_manifest.frozen)
    frozen_seeds = list(seed_ledger.frozen)
    configured_cases = int(protocol_config.frozen.n_cases)
    configured_seeds = int(protocol_config.frozen.n_seeds)
    if configured_cases != len(frozen_cases) or configured_seeds != len(frozen_seeds):
        raise ValueError(
            "held-out comparison requires the complete frozen matrix: "
            f"protocol n_cases/n_seeds={configured_cases}/{configured_seeds}, "
            f"declared split/ledger={len(frozen_cases)}/{len(frozen_seeds)}"
        )


def _comparison_groups(
    manifest: Mapping[str, Any],
    *,
    base_dir: Path,
) -> list[dict[str, Any]]:
    raw_groups = manifest.get("groups")
    if not isinstance(raw_groups, Sequence) or isinstance(raw_groups, (str, bytes)):
        raise ValueError("groups must be a non-empty array")  # noqa: TRY004
    if not raw_groups:
        raise ValueError("groups must be a non-empty array")
    groups: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_groups):
        if not isinstance(raw, Mapping):
            raise ValueError(f"groups[{index}] must be an object")  # noqa: TRY004
        comparison_id = _required_text(raw, "comparison_id")
        if not _COMPARISON_ID_RE.fullmatch(comparison_id):
            raise ValueError(f"invalid comparison_id: {comparison_id!r}")
        if comparison_id in seen:
            raise ValueError(f"duplicate comparison_id: {comparison_id}")
        seen.add(comparison_id)
        candidate = _required_directory(raw, "candidate_workspace", base_dir)
        champion = _required_directory(raw, "champion_workspace", base_dir)
        groups.append(
            {
                "comparison_id": comparison_id,
                "candidate_workspace": candidate,
                "champion_workspace": champion,
                "candidate_label": _optional_text(raw, "candidate_label")
                or candidate.name,
                "champion_label": _optional_text(raw, "champion_label")
                or champion.name,
                "selected_surface": _optional_text(raw, "selected_surface") or None,
            }
        )
    return groups


def _load_manifest(path: Path) -> Mapping[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("comparison manifest must be a JSON object")  # noqa: TRY004
    if payload.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise ValueError(
            f"schema_version must be {MANIFEST_SCHEMA_VERSION!r}"
        )
    return payload


def _required_file(
    payload: Mapping[str, Any],
    key: str,
    base_dir: Path,
) -> Path:
    path = _resolve_path(_required_text(payload, key), base_dir)
    if not path.is_file():
        raise FileNotFoundError(f"{key} not found: {path}")
    return path


def _required_directory(
    payload: Mapping[str, Any],
    key: str,
    base_dir: Path,
) -> Path:
    path = _resolve_path(_required_text(payload, key), base_dir)
    if not path.is_dir():
        raise FileNotFoundError(f"{key} not found: {path}")
    return path


def _resolve_path(value: str, base_dir: Path) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = base_dir / path
    return path.resolve()


def _required_text(payload: Mapping[str, Any], key: str) -> str:
    value = _optional_text(payload, key)
    if not value:
        raise ValueError(f"{key} must be non-empty")
    return value


def _optional_text(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    return str(value).strip() if value is not None else ""


def _positive_int(value: Any, *, label: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a positive integer")  # noqa: TRY004
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a positive integer") from exc
    if parsed <= 0 or parsed != value:
        raise ValueError(f"{label} must be a positive integer")
    return parsed


def _summary_payload(
    *,
    manifest_path: Path,
    output_dir: Path,
    groups: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    completed = [group for group in groups if group.get("status") == "completed"]
    execution_invalid = [
        group for group in groups if group.get("status") == "execution-invalid"
    ]
    errors = [group for group in groups if group.get("status") == "error"]
    supported = [group for group in completed if group.get("supports_candidate")]
    canary_passed = [
        group
        for group in completed
        if (group.get("canary_safety_diagnostic") or {}).get("passed") is True
    ]
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "evaluation_only": True,
        "stage": "frozen",
        "manifest_path": str(manifest_path),
        "output_dir": str(output_dir),
        "completed_at": _utc_now_iso(),
        "group_count": len(groups),
        "completed_group_count": len(completed),
        "execution_invalid_group_count": len(execution_invalid),
        "error_group_count": len(errors),
        "canary_safety_passed_group_count": len(canary_passed),
        "candidate_supported_group_count": len(supported),
        "all_groups_supported": bool(groups) and len(supported) == len(groups),
        "groups": [
            {
                "comparison_id": group["comparison_id"],
                "status": group["status"],
                "supports_candidate": bool(group.get("supports_candidate", False)),
                "result_path": group["result_path"],
            }
            for group in groups
        ],
    }


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "DEFAULT_SUMMARY_FILENAME",
    "GROUP_SCHEMA_VERSION",
    "MANIFEST_SCHEMA_VERSION",
    "SUMMARY_SCHEMA_VERSION",
    "InfeasibleAsFailureRunner",
    "build_champion_heldout_protocol",
    "execute_champion_heldout_comparison",
]
