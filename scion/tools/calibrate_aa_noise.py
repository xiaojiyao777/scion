#!/usr/bin/env python3
"""Run champion-vs-champion A/A measurement calibration."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from scion.cli.commands.data_roots import (
    activate_declared_problem_data_root,
    validate_declared_problem_data_cases,
    with_declared_problem_data_roots,
)
from scion.config.problem import ProtocolConfig, SeedLedgerConfig, SplitManifest
from scion.core.models import ExperimentStage
from scion.measurement.aa_calibration import (
    AAPairRecord,
    build_aa_noise_floor_payload,
    resolve_calibration_time_limit_sec,
    runtime_policy_summary,
)
from scion.problem.loader import load_problem_adapter, load_problem_spec_v1_from_yaml
from scion.problem.objectives import compare_lexicographic, compare_weighted_sum
from scion.protocol.experiment.selection import (
    SeedLedger,
    SplitManager,
    resolve_case_path_details,
    select_cases,
    select_seeds,
)
from scion.runtime.runner import ResourceLimits, run_solver_with_surface
from scion.runtime.subprocess_runner import LocalSubprocessRunner
from scion.verification.feasibility import _registry_path


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    problem_v1_path = Path(args.problem_v1).expanduser().resolve(strict=False)
    protocol_path = Path(args.protocol).expanduser().resolve(strict=False)
    adapter = load_problem_adapter(load_problem_spec_v1_from_yaml(problem_v1_path))
    problem_spec = adapter.spec
    protocol = ProtocolConfig.from_yaml(protocol_path).with_problem_measurement(
        problem_spec
    )
    split = SplitManifest.from_yaml(args.split)
    activation = activate_declared_problem_data_root(
        problem_yaml=problem_v1_path,
        protocol_path=protocol_path,
    )
    validate_declared_problem_data_cases(
        activation=activation,
        problem_yaml=problem_v1_path,
        split_manifest=split,
    )
    split = with_declared_problem_data_roots(
        activation=activation,
        split_manifest=split,
    )
    seed_ledger = SeedLedgerConfig.from_yaml(args.seeds)
    stage = _stage(args.stage)
    cases, seeds = _select_calibration_population(
        protocol=protocol,
        split=split,
        seed_ledger=seed_ledger,
        stage=stage,
        hypothesis_action=args.hypothesis_action,
        expand_round=args.expand_round,
        max_seeds=args.max_seeds,
    )
    if not cases or not seeds:
        raise SystemExit("calibration requires at least one case and one seed")

    runtime_policy = runtime_policy_summary(
        protocol=protocol,
        stage=stage,
        cases=cases,
        fallback_time_limit_sec=args.time_limit_sec,
        selected_policy=args.runtime_policy,
    )
    runner = LocalSubprocessRunner(
        ResourceLimits(
            timeout_sec=runtime_policy["runner_timeout_sec"],
            memory_mb=args.memory_mb,
        )
    )
    records = _collect_records(
        protocol=protocol,
        stage=stage,
        problem_spec=problem_spec,
        metric_specs=tuple(problem_spec.objectives),
        objective_policy=problem_spec.objective_policy,
        runner=runner,
        workspace=Path(args.champion_workspace).resolve(),
        cases=cases,
        seeds=seeds,
        safe_data_roots=split.safe_data_roots,
        fallback_time_limit_sec=args.time_limit_sec,
        runtime_policy=args.runtime_policy,
        replicates=args.replicates,
        seed_offset=args.seed_offset,
        measurement_metric=problem_spec.measurement.effect_scale.metric,
        measurement_unit=problem_spec.measurement.effect_scale.unit,
        selected_surface=args.selected_surface,
    )
    payload = build_aa_noise_floor_payload(
        records=records,
        problem_id=problem_spec.id,
        stage=stage.value,
        metric=problem_spec.measurement.effect_scale.metric,
        unit=problem_spec.measurement.effect_scale.unit,
        win_rate_min=protocol.gates.screening.win_rate_min,
        practical_delta=protocol.screening_min_practical_delta,
        calibrated_at=datetime.now(timezone.utc).isoformat(),
        champion_version=args.champion_version,
        protocol_version=protocol.version,
        n_boot=args.bootstrap_samples,
        selected_cases=cases,
        selected_seeds=seeds,
        replicates=args.replicates,
        seed_offset=args.seed_offset,
        selected_surface=args.selected_surface,
        runtime_policy=runtime_policy,
        safe_data_roots=split.safe_data_roots,
        combined_case_rule=_combined_case_rule(protocol, stage),
    )
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(f"wrote A/A calibration: {output}")
    print(
        "mde_at_power_80="
        f"{payload['protocol_power'].get('mde_at_power_80')} "
        "false_pass_rate="
        f"{payload['protocol_power'].get('false_pass_rate_at_current_gate')}"
    )
    combined_null = payload.get("combined_case_rule_null")
    if isinstance(combined_null, Mapping):
        print(
            "combined_null_pass_rate="
            f"{combined_null.get('null_pass_rate')} "
            "wilson_upper_95="
            f"{combined_null.get('null_pass_rate_wilson_upper_95')}"
        )
    return 0


def _collect_records(
    *,
    protocol: ProtocolConfig,
    stage: ExperimentStage,
    problem_spec: Any,
    metric_specs: Any,
    objective_policy: Any,
    runner: Any,
    workspace: Path,
    cases: list[str],
    seeds: list[int],
    safe_data_roots: list[str],
    fallback_time_limit_sec: int,
    runtime_policy: str,
    replicates: int,
    seed_offset: int,
    measurement_metric: str,
    measurement_unit: str,
    selected_surface: str | None,
) -> list[AAPairRecord]:
    records: list[AAPairRecord] = []
    for case in cases:
        resolution = resolve_case_path_details(
            case,
            workspace=str(workspace),
            safe_data_roots=safe_data_roots,
        )
        if not resolution.safe or not Path(resolution.resolved).exists():
            raise SystemExit(f"case path could not be resolved safely: {case}")
        case_time_limit_sec = resolve_calibration_time_limit_sec(
            protocol=protocol,
            stage=stage,
            case_path=resolution.resolved,
            fallback_time_limit_sec=fallback_time_limit_sec,
            runtime_policy=runtime_policy,
        )
        for seed in seeds:
            for replicate in range(replicates):
                champion_seed = int(seed)
                candidate_seed = int(seed) + seed_offset * (replicate + 1)
                champion = _run_once(
                    runner,
                    workspace=workspace,
                    case_path=resolution.resolved,
                    seed=champion_seed,
                    time_limit_sec=case_time_limit_sec,
                    selected_surface=selected_surface,
                )
                candidate = _run_once(
                    runner,
                    workspace=workspace,
                    case_path=resolution.resolved,
                    seed=candidate_seed,
                    time_limit_sec=case_time_limit_sec,
                    selected_surface=selected_surface,
                )
                comparison = _compare(
                    metric_specs,
                    objective_policy,
                    candidate["objective"],
                    champion["objective"],
                )
                raw_delta, candidate_value, champion_value = _metric_delta(
                    comparison.metrics,
                    measurement_metric,
                )
                delta = _scale_delta(
                    raw_delta,
                    champion_value=champion_value,
                    unit=measurement_unit,
                )
                records.append(
                    AAPairRecord(
                        case_id=case,
                        seed=seed,
                        replicate=replicate,
                        outcome=comparison.outcome,
                        delta=delta,
                        raw_delta=raw_delta,
                        candidate_value=candidate_value,
                        champion_value=champion_value,
                        candidate_seed=candidate_seed,
                        resolved_case_path=resolution.resolved,
                        case_resolution=resolution.as_metrics(),
                        champion_elapsed_ms=champion["elapsed_ms"],
                        candidate_elapsed_ms=candidate["elapsed_ms"],
                        time_limit_sec=case_time_limit_sec,
                    )
                )
    return records


def _select_calibration_population(
    *,
    protocol: ProtocolConfig, split: SplitManifest,
    seed_ledger: SeedLedgerConfig, stage: ExperimentStage,
    hypothesis_action: str, expand_round: int, max_seeds: int | None,
) -> tuple[list[str], list[int]]:
    cases = select_cases(
        config=protocol, split_manager=SplitManager(split), stage=stage,
        hypothesis_action=hypothesis_action, expand_round=expand_round,
    )
    seeds = select_seeds(
        config=protocol, seed_ledger=SeedLedger(seed_ledger), stage=stage,
        expanded=expand_round > 0,
    )
    if max_seeds is not None:
        if max_seeds <= 0:
            raise ValueError("max_seeds must be positive")
        seeds = seeds[:max_seeds]
    return cases, seeds


def _combined_case_rule(
    protocol: ProtocolConfig,
    stage: ExperimentStage,
) -> dict[str, float] | None:
    gate = getattr(protocol.gates, stage.value)
    values = (
        gate.min_net_case_score, gate.max_case_loss_rate,
        gate.bootstrap_ci_low_min,
    )
    if None in values:
        return None
    practical_delta = (
        protocol.screening_min_practical_delta
        if stage == ExperimentStage.SCREENING
        else protocol.validation_min_practical_delta
    )
    return {
        "case_equivalence_band": float(protocol.case_equivalence_band),
        "min_net_case_score": float(gate.min_net_case_score),
        "max_case_loss_rate": float(gate.max_case_loss_rate),
        "median_delta_min": float(practical_delta),
        "bootstrap_ci_low_min": float(gate.bootstrap_ci_low_min),
    }


def _run_once(
    runner: Any,
    *,
    workspace: Path,
    case_path: str,
    seed: int,
    time_limit_sec: int,
    selected_surface: str | None,
) -> dict[str, Any]:
    result = run_solver_with_surface(
        runner,
        workdir=str(workspace),
        instance_path=case_path,
        seed=seed,
        time_limit_sec=time_limit_sec,
        registry_path=_registry_path(str(workspace)),
        selected_surface=selected_surface,
    )
    if not result.success or result.output is None:
        raise SystemExit(
            "solver failed during A/A calibration: "
            f"case={case_path} seed={seed} category={result.error_category}"
        )
    return {"objective": result.output.objective, "elapsed_ms": result.elapsed_ms}


def _compare(metric_specs: Any, objective_policy: Any, candidate: Mapping[str, Any], champion: Mapping[str, Any]) -> Any:
    if getattr(objective_policy, "mode", "") == "weighted_sum":
        return compare_weighted_sum(metric_specs, candidate, champion)
    return compare_lexicographic(metric_specs, candidate, champion)


def _metric_delta(metrics: Any, metric_name: str) -> tuple[float, float | None, float | None]:
    for row in metrics:
        if row.name == metric_name:
            return float(row.signed_delta), float(row.candidate_value), float(row.champion_value)
    raise SystemExit(f"measurement metric not found in comparison: {metric_name}")


def _scale_delta(raw_delta: float, *, champion_value: float | None, unit: str) -> float:
    if unit == "relative_pct":
        denominator = abs(float(champion_value or 0.0))
        if denominator <= 0.0:
            return 0.0
        return 100.0 * raw_delta / denominator
    return raw_delta


def _stage(value: str) -> ExperimentStage:
    normalized = value.strip().lower()
    if normalized == "screening":
        return ExperimentStage.SCREENING
    if normalized == "validation":
        return ExperimentStage.VALIDATION
    if normalized == "frozen":
        return ExperimentStage.FROZEN
    raise SystemExit("--stage must be screening, validation, or frozen")


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--problem-v1", required=True, help="Path to problem-v1.yaml")
    parser.add_argument("--protocol", required=True, help="Path to protocol.yaml")
    parser.add_argument("--split", required=True, help="Path to split_manifest.yaml")
    parser.add_argument("--seeds", required=True, help="Path to seed_ledger.yaml")
    parser.add_argument("--champion-workspace", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--stage", default="screening")
    parser.add_argument("--hypothesis-action", default="modify")
    parser.add_argument("--expand-round", type=int, default=0)
    parser.add_argument("--max-seeds", type=int, default=None)
    parser.add_argument("--replicates", type=int, default=3)
    parser.add_argument("--seed-offset", type=int, default=1_000_003)
    parser.add_argument("--time-limit-sec", type=int, default=30)
    parser.add_argument(
        "--runtime-policy",
        choices=("uniform_time_limit", "protocol_time_limits"),
        default="uniform_time_limit",
        help=(
            "Use the CLI time limit uniformly, or resolve protocol runtime "
            "time-limit rules per selected case."
        ),
    )
    parser.add_argument("--memory-mb", type=int, default=4096)
    parser.add_argument("--bootstrap-samples", type=int, default=400)
    parser.add_argument("--selected-surface", default=None)
    parser.add_argument("--champion-version", default="")
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
