from __future__ import annotations

import json
import logging
import os
import uuid as _uuid_mod
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import replace
from typing import TYPE_CHECKING, Any, Dict, List, Sequence

from scion.core.models import (
    EvalStats,
    ExperimentStage,
    PairwiseCaseFeedback,
    ProtocolResult,
)
from scion.core.runtime_budget_diagnostics import (
    format_runtime_budget_diagnostic,
    runtime_budget_diagnostic,
)
from scion.core.screening_visibility import (
    mechanism_evidence_for_protocol,
    opportunity_diagnostics_for_protocol,
    opportunity_status_for_diagnostics,
    runtime_gate_visibility_summary,
    runtime_evidence_policy_summary,
)
from scion.protocol.gates import GateResult, frozen_gate, screening_gate, validation_gate
from scion.protocol.stats import compute_eval_stats
from scion.runtime.audit import (
    declared_surface_required_runtime_fields,
    format_runtime_audit_failure,
    normalize_surface_name,
    runtime_audit_failure_from_result,
)
from scion.runtime.telemetry_guard import build_telemetry_guard_summary
from .cache import compute_workspace_digest
from .failures import (
    _bounded_runtime_failure,
    _bounded_runtime_failure_from_audit,
    _candidate_audit_failure_category,
    _candidate_process_failure_category,
    _format_runtime_failure_categories,
)
from .feedback import (
    _aggregate_case_feedback,
    _aggregate_pairs_to_case_level,
    _build_pattern_summary,
    _extract_case_features,
    _pair_feedback_counts,
)
from .phase_telemetry import (
    _finalize_phase_telemetry_summary,
    _format_phase_telemetry_summary,
    _phase_telemetry_summary_template,
    _record_phase_telemetry_sample,
)
from .runtime_observation import (
    _append_guard_runtime,
    _build_runtime_stats,
    _candidate_runtime_counter_template,
    _candidate_runtime_observation,
    _format_runtime_counter_summary,
    _format_runtime_summary,
    _format_telemetry_guard_summary,
    _merge_runtime_observation,
    _record_runtime_sample,
    _runtime_fields,
)
from .surface_runtime import (
    _record_surface_runtime_sample,
    _surface_runtime_summary_template,
    _surface_runtime_summary_with_guard,
)
from .values import _increment_category

if TYPE_CHECKING:
    from .facade import ExperimentProtocol

logger = logging.getLogger(__name__)


def run_experiment(
    protocol: "ExperimentProtocol",
    stage: ExperimentStage,
    candidate_ws: str,
    champion_ws: str,
    hypothesis_action: str,
    expand: bool = False,
    expand_round: int = 1,
    selected_surface: str | None = None,
    expected_telemetry: Mapping[str, Any] | None = None,
    mechanism_changes: Sequence[Any] | None = None,
    protected_objectives: Sequence[str] = (),
) -> ProtocolResult:
    """Execute paired A/B evaluation for the given stage.

    T2: Statistical unit is case (not pair). Each case is evaluated across
    all seeds, then majority-voted to a case-level win/loss/tie and median delta.
    T4: expand increases case count; seed set is unchanged.
    T5: case count depends on stage + hypothesis_action + expand flag.
    """
    cases = protocol._select_cases(
        stage, hypothesis_action, expand_round if expand else 0
    )
    seeds = protocol._select_seeds(stage)
    total_pairs = len(cases) * len(seeds)
    attempted_pairs = 0
    valid_pairs = 0

    # Persist a partial metrics file from the start of the stage, then update
    # it after every attempted pair. Long validation/frozen stages remain
    # inspectable even if the campaign is interrupted.
    raw_ref = os.path.join(protocol.metrics_dir, f"{_uuid_mod.uuid4()}.json")

    # Collect pair feedback grouped by case
    pairs_by_case: Dict[str, List[PairwiseCaseFeedback]] = defaultdict(list)
    raw_pairs: List[dict] = []
    raw_failures: List[dict] = []
    failed_pairs = 0
    candidate_failed_pairs = 0
    champion_failed_pairs = 0
    runtime_ratios: list[float] = []
    runtime_deltas_ms: list[float] = []
    candidate_runtime_categories: dict[str, int] = {}
    candidate_first_runtime_failure: dict[str, Any] | None = None
    candidate_runtime_stop_reasons: dict[str, int] = {}
    candidate_guard_runtimes: list[Mapping[str, Any]] = []
    champion_guard_runtimes: list[Mapping[str, Any]] = []
    candidate_telemetry_guard_summary: dict[str, Any] = {}
    runtime_budget_diagnostic_summary: dict[str, Any] | None = None
    candidate_elapsed_samples_ms: list[float] = []
    champion_elapsed_samples_ms: list[float] = []
    champion_cache_hits = 0
    champion_cache_misses = 0
    champion_cache_writes = 0
    champion_cached_runtime_pairs = 0
    runtime_evidence_status = "sufficient"
    runtime_gate_visibility: dict[str, Any] = {}
    normalized_selected_surface = normalize_surface_name(selected_surface) or None
    champion_cache = getattr(protocol, "_champion_result_cache", None)
    champion_runtime_policy = protocol.config.runtime.champion_runtime_policy
    champion_cache_enabled = bool(
        getattr(protocol, "_champion_result_cache_enabled", False)
        and champion_cache is not None
        and champion_runtime_policy != "fresh_always"
    )
    champion_workspace_digest = (
        compute_workspace_digest(champion_ws) if champion_cache_enabled else None
    )
    candidate_runtime_counters: dict[str, int] = _candidate_runtime_counter_template(
        problem_spec=protocol._problem_spec,
        selected_surface=normalized_selected_surface,
    )
    surface_required_runtime_fields = declared_surface_required_runtime_fields(
        protocol._problem_spec,
        normalized_selected_surface,
    )
    candidate_surface_runtime_summary = _surface_runtime_summary_template(
        selected_surface=normalized_selected_surface,
        required_fields=surface_required_runtime_fields,
    )
    candidate_phase_telemetry_summary = _phase_telemetry_summary_template(
        problem_spec=protocol._problem_spec,
        selected_surface=normalized_selected_surface,
    )

    def _write_metrics_snapshot(*, complete: bool) -> None:
        runtime_stats_snapshot = _build_runtime_stats(
            runtime_ratios,
            runtime_deltas_ms,
        )
        runtime_confidence_snapshot = (
            "low_cached_champion"
            if champion_cached_runtime_pairs
            else "high"
        )
        runtime_evidence_policy = runtime_evidence_policy_summary(
            runtime_confidence=runtime_confidence_snapshot,
            runtime_evidence_status=runtime_evidence_status,
            runtime_pairs=runtime_stats_snapshot["runtime_pairs"],
            champion_cached_runtime_pairs=champion_cached_runtime_pairs,
            runtime_aggregate_excluded=(
                champion_cached_runtime_pairs > 0
                and runtime_stats_snapshot["runtime_pairs"] <= 0
            ),
        )
        with open(raw_ref, "w") as f:
            json.dump(
                {
                    "stage": stage.value,
                    "selected_surface": normalized_selected_surface,
                    "case_ids": cases,
                    "seed_set": seeds,
                    "total_pairs": total_pairs,
                    "attempted_pairs": attempted_pairs,
                    "valid_pairs": valid_pairs,
                    "failed_pairs": failed_pairs,
                    "candidate_failed_pairs": candidate_failed_pairs,
                    "champion_failed_pairs": champion_failed_pairs,
                    "runtime_stats": runtime_stats_snapshot,
                    "runtime_confidence": runtime_confidence_snapshot,
                    "runtime_evidence_status": runtime_evidence_status,
                    "runtime_evidence_policy": runtime_evidence_policy,
                    "runtime_gate_visibility": runtime_gate_visibility,
                    "champion_cache_hits": champion_cache_hits,
                    "champion_cache_misses": champion_cache_misses,
                    "champion_cache_writes": champion_cache_writes,
                    "champion_cached_runtime_pairs": champion_cached_runtime_pairs,
                    "champion_result_cache": {
                        "enabled": champion_cache_enabled,
                        "hits": champion_cache_hits,
                        "misses": champion_cache_misses,
                        "writes": champion_cache_writes,
                        "cached_runtime_pairs": champion_cached_runtime_pairs,
                    },
                    "candidate_surface_runtime_summary": (
                        _surface_runtime_summary_with_guard(
                            candidate_surface_runtime_summary,
                            candidate_telemetry_guard_summary,
                            runtime_budget_diagnostic_summary,
                        )
                    ),
                    "candidate_phase_telemetry_summary": (
                        _finalize_phase_telemetry_summary(
                            candidate_phase_telemetry_summary
                        )
                    ),
                    "candidate_telemetry_guard_summary": (
                        candidate_telemetry_guard_summary
                    ),
                    "complete": complete,
                    "pairs": raw_pairs,
                    "failures": raw_failures,
                },
                f,
            )

    _write_metrics_snapshot(complete=False)
    protocol._emit_progress(
        stage=stage.value,
        case=None,
        seed=None,
        attempted_pairs=attempted_pairs,
        completed_pairs=valid_pairs,
        total_pairs=total_pairs,
        raw_metrics_ref=raw_ref,
    )

    for case in cases:
        case_features = _extract_case_features(case)
        for seed in seeds:
            attempted_pairs += 1
            champion_case_path = protocol._resolve_case_path(
                case,
                workspace=champion_ws,
            )
            candidate_case_path = protocol._resolve_case_path(
                case,
                workspace=candidate_ws,
            )
            protocol._emit_progress(
                stage=stage.value,
                case=case,
                seed=seed,
                attempted_pairs=attempted_pairs,
                completed_pairs=valid_pairs,
                total_pairs=total_pairs,
                raw_metrics_ref=raw_ref,
            )
            champion_cache_key: dict[str, Any] | None = None
            champion_result_source = "fresh"
            if champion_cache_enabled:
                champion_cache_key = champion_cache.build_key(
                    champion_workspace=champion_ws,
                    case_path=champion_case_path,
                    seed=seed,
                    time_limit_sec=protocol.time_limit_sec,
                    selected_surface=normalized_selected_surface,
                    runner=protocol.runner,
                    metric_specs=protocol._metric_specs,
                    objective_policy=protocol._objective_policy,
                    problem_spec=protocol._problem_spec,
                    workspace_digest=champion_workspace_digest,
                )
                cached_champion = champion_cache.get(champion_cache_key)
            else:
                cached_champion = None
            if cached_champion is not None:
                champ_r = cached_champion
                champion_result_source = "cached"
                champion_cache_hits += 1
            else:
                if champion_cache_enabled:
                    champion_cache_misses += 1
                champ_r = protocol.runner.run_solver(
                    workdir=champion_ws,
                    instance_path=champion_case_path,
                    seed=seed,
                    time_limit_sec=protocol.time_limit_sec,
                    registry_path=os.path.join(champion_ws, "registry.yaml"),
                    selected_surface=normalized_selected_surface,
                )
            cand_r = protocol.runner.run_solver(
                workdir=candidate_ws,
                instance_path=candidate_case_path,
                seed=seed,
                time_limit_sec=protocol.time_limit_sec,
                registry_path=os.path.join(candidate_ws, "registry.yaml"),
                selected_surface=normalized_selected_surface,
            )
            champion_cache_digest = (
                str(champion_cache_key.get("digest"))
                if champion_cache_key is not None
                else None
            )
            pair_cache_fields = {
                "champion_result_source": champion_result_source,
                "champion_cache_key": champion_cache_digest,
                "runtime_confidence": (
                    "low_cached_champion"
                    if champion_result_source == "cached"
                    else "high"
                ),
                "runtime_ratio_high_confidence": champion_result_source != "cached",
            }
            if champion_result_source == "cached":
                champion_cached_runtime_pairs += 1
            else:
                _append_elapsed_sample(champion_elapsed_samples_ms, champ_r.elapsed_ms)
            _append_elapsed_sample(candidate_elapsed_samples_ms, cand_r.elapsed_ms)
            _record_surface_runtime_sample(
                cand_r,
                candidate_surface_runtime_summary,
            )
            _record_phase_telemetry_sample(
                cand_r,
                candidate_phase_telemetry_summary,
            )
            runtime_fields = _runtime_fields(
                cand_r,
                champ_r,
                problem_spec=protocol._problem_spec,
                selected_surface=normalized_selected_surface,
                candidate_required_runtime_fields=surface_required_runtime_fields,
            )
            _append_guard_runtime(candidate_guard_runtimes, cand_r)
            _append_guard_runtime(champion_guard_runtimes, champ_r)
            if champion_result_source != "cached":
                _record_runtime_sample(
                    runtime_fields,
                    runtime_ratios,
                    runtime_deltas_ms,
                )
            runtime_observation = _candidate_runtime_observation(
                cand_r,
                problem_spec=protocol._problem_spec,
                selected_surface=normalized_selected_surface,
            )
            _merge_runtime_observation(
                runtime_observation,
                categories=candidate_runtime_categories,
                counters=candidate_runtime_counters,
                stop_reasons=candidate_runtime_stop_reasons,
            )
            if (
                candidate_first_runtime_failure is None
                and runtime_observation.get("first_failure") is not None
            ):
                candidate_first_runtime_failure = runtime_observation["first_failure"]

            champ_audit_failure = None
            if champ_r.success and champ_r.output is not None:
                champ_audit_failure = runtime_audit_failure_from_result(champ_r)
                if (
                    champ_audit_failure is None
                    and champion_result_source == "fresh"
                    and champion_cache_enabled
                    and champion_cache_key is not None
                    and champion_cache.put(champion_cache_key, champ_r)
                ):
                    champion_cache_writes += 1

            if not champ_r.success:
                failed_pairs += 1
                champion_failed_pairs += 1
                side = "both" if not cand_r.success else "champion"
                failure_record = {
                    "case": case,
                    "seed": seed,
                    "side": side,
                    "comparison": "invalid",
                    "error_category": (
                        "shared_process_failure"
                        if side == "both"
                        else champ_r.error_category or "unknown"
                    ),
                    "champion_error_category": champ_r.error_category or "unknown",
                    "candidate_error_category": (
                        cand_r.error_category or "unknown" if side == "both" else None
                    ),
                    "exit_code": champ_r.exit_code,
                    "champion_exit_code": champ_r.exit_code,
                    "candidate_exit_code": cand_r.exit_code if side == "both" else None,
                    "elapsed_ms": champ_r.elapsed_ms,
                    **runtime_fields,
                    **pair_cache_fields,
                    "stderr_tail": (champ_r.stderr or "")[-1000:],
                    "candidate_stderr_tail": (
                        (cand_r.stderr or "")[-1000:] if side == "both" else ""
                    ),
                }
                raw_failures.append(failure_record)
                raw_pairs.append({
                    "case": case,
                    "seed": seed,
                    "comparison": "invalid",
                    "delta": None,
                    "decisive_metric": (
                        "shared_process_failure"
                        if side == "both"
                        else "champion_runtime_failure"
                    ),
                    "metric_deltas": {},
                    **runtime_fields,
                    **pair_cache_fields,
                    "failure": failure_record,
                })
                logger.info(
                    "Pair %s seed=%d: %s solver failed category=%s elapsed_ms=%d → invalid",
                    os.path.basename(case), seed,
                    side,
                    champ_r.error_category or "unknown",
                    champ_r.elapsed_ms,
                )
                _write_metrics_snapshot(complete=False)
                protocol._emit_progress(
                    stage=stage.value,
                    case=case,
                    seed=seed,
                    attempted_pairs=attempted_pairs,
                    completed_pairs=valid_pairs,
                    total_pairs=total_pairs,
                    raw_metrics_ref=raw_ref,
                )
                continue

            if not cand_r.success:
                category = _candidate_process_failure_category(cand_r)
                _increment_category(candidate_runtime_categories, category)
                if candidate_first_runtime_failure is None:
                    candidate_first_runtime_failure = _bounded_runtime_failure(
                        category=category,
                        code=str(cand_r.error_category or cand_r.exit_code or "process_failure"),
                        surface=None,
                        component="solver_process",
                        detail_summary=cand_r.stderr or cand_r.stdout or "candidate solver process failed",
                    )
                failed_pairs += 1
                candidate_failed_pairs += 1
                failure_record = {
                    "case": case,
                    "seed": seed,
                    "side": "candidate",
                    "comparison": "loss",
                    "delta": -1.0,
                    "error_category": cand_r.error_category or "unknown",
                    "exit_code": cand_r.exit_code,
                    "elapsed_ms": cand_r.elapsed_ms,
                    **runtime_fields,
                    **pair_cache_fields,
                    "stderr_tail": (cand_r.stderr or "")[-1000:],
                }
                raw_failures.append(failure_record)
                raw_pairs.append({
                    "case": case,
                    "seed": seed,
                    "comparison": "loss",
                    "delta": -1.0,
                    "decisive_metric": "runtime_failure",
                    "metric_deltas": {},
                    **runtime_fields,
                    **pair_cache_fields,
                    "failure": failure_record,
                })
                pairs_by_case[os.path.basename(case)].append(
                    PairwiseCaseFeedback(
                        case_id=os.path.basename(case),
                        seed=seed,
                        comparison="loss",
                        delta=-1.0,
                        objective_comparison=None,
                        case_features=case_features,
                    )
                )
                logger.info(
                    "Pair %s seed=%d: candidate solver failed category=%s elapsed_ms=%d → loss",
                    os.path.basename(case), seed,
                    cand_r.error_category or "unknown",
                    cand_r.elapsed_ms,
                )
                _write_metrics_snapshot(complete=False)
                protocol._emit_progress(
                    stage=stage.value,
                    case=case,
                    seed=seed,
                    attempted_pairs=attempted_pairs,
                    completed_pairs=valid_pairs,
                    total_pairs=total_pairs,
                    raw_metrics_ref=raw_ref,
                )
                continue

            if cand_r.output is None or champ_r.output is None:
                failed_pairs += 1
                if cand_r.output is None:
                    _increment_category(candidate_runtime_categories, "invalid_output")
                    if candidate_first_runtime_failure is None:
                        candidate_first_runtime_failure = _bounded_runtime_failure(
                            category="invalid_output",
                            code="missing_output",
                            surface=None,
                            component="solver_output",
                            detail_summary="candidate solver succeeded without parsed output",
                        )
                failure_record = {
                    "case": case,
                    "seed": seed,
                    "side": "unknown",
                    "comparison": "invalid",
                    "error_category": "missing_output",
                    **runtime_fields,
                    **pair_cache_fields,
                }
                raw_failures.append(failure_record)
                raw_pairs.append({
                    "case": case,
                    "seed": seed,
                    "comparison": "invalid",
                    "delta": None,
                    "decisive_metric": "missing_output",
                    "metric_deltas": {},
                    **runtime_fields,
                    **pair_cache_fields,
                    "failure": failure_record,
                })
                _write_metrics_snapshot(complete=False)
                protocol._emit_progress(
                    stage=stage.value,
                    case=case,
                    seed=seed,
                    attempted_pairs=attempted_pairs,
                    completed_pairs=valid_pairs,
                    total_pairs=total_pairs,
                    raw_metrics_ref=raw_ref,
                )
                continue

            cand_audit_failure = runtime_audit_failure_from_result(
                cand_r,
                problem_spec=protocol._problem_spec,
                selected_surface=normalized_selected_surface,
            )
            if cand_audit_failure is not None:
                audit_category = _candidate_audit_failure_category(cand_audit_failure)
                if audit_category not in (runtime_observation.get("categories") or {}):
                    _increment_category(candidate_runtime_categories, audit_category)
                if candidate_first_runtime_failure is None:
                    candidate_first_runtime_failure = _bounded_runtime_failure_from_audit(
                        cand_audit_failure,
                        category=audit_category,
                    )
                failed_pairs += 1
                candidate_failed_pairs += 1
                failure_record = {
                    "case": case,
                    "seed": seed,
                    "side": "candidate",
                    "comparison": "loss",
                    "delta": -1.0,
                    "error_category": cand_audit_failure["error_category"],
                    "exit_code": cand_r.exit_code,
                    "elapsed_ms": cand_r.elapsed_ms,
                    **runtime_fields,
                    **pair_cache_fields,
                    "runtime_audit": cand_audit_failure,
                }
                raw_failures.append(failure_record)
                raw_pairs.append({
                    "case": case,
                    "seed": seed,
                    "comparison": "loss",
                    "delta": -1.0,
                    "decisive_metric": cand_audit_failure["error_category"],
                    "metric_deltas": {},
                    **runtime_fields,
                    **pair_cache_fields,
                    "failure": failure_record,
                })
                pairs_by_case[os.path.basename(case)].append(
                    PairwiseCaseFeedback(
                        case_id=os.path.basename(case),
                        seed=seed,
                        comparison="loss",
                        delta=-1.0,
                        objective_comparison=None,
                        case_features=case_features,
                    )
                )
                logger.info(
                    "Pair %s seed=%d: candidate runtime audit failed: %s",
                    os.path.basename(case), seed,
                    format_runtime_audit_failure(cand_audit_failure),
                )
                _write_metrics_snapshot(complete=False)
                protocol._emit_progress(
                    stage=stage.value,
                    case=case,
                    seed=seed,
                    attempted_pairs=attempted_pairs,
                    completed_pairs=valid_pairs,
                    total_pairs=total_pairs,
                    raw_metrics_ref=raw_ref,
                )
                continue

            if champ_audit_failure is not None:
                failed_pairs += 1
                champion_failed_pairs += 1
                failure_record = {
                    "case": case,
                    "seed": seed,
                    "side": "champion",
                    "comparison": "invalid",
                    "delta": None,
                    "error_category": champ_audit_failure["error_category"],
                    "exit_code": champ_r.exit_code,
                    "elapsed_ms": champ_r.elapsed_ms,
                    **runtime_fields,
                    **pair_cache_fields,
                    "runtime_audit": champ_audit_failure,
                }
                raw_failures.append(failure_record)
                raw_pairs.append({
                    "case": case,
                    "seed": seed,
                    "comparison": "invalid",
                    "delta": None,
                    "decisive_metric": f"champion_{champ_audit_failure['error_category']}",
                    "metric_deltas": {},
                    **runtime_fields,
                    **pair_cache_fields,
                    "failure": failure_record,
                })
                logger.info(
                    "Pair %s seed=%d: champion runtime audit failed: %s",
                    os.path.basename(case), seed,
                    format_runtime_audit_failure(champ_audit_failure),
                )
                _write_metrics_snapshot(complete=False)
                protocol._emit_progress(
                    stage=stage.value,
                    case=case,
                    seed=seed,
                    attempted_pairs=attempted_pairs,
                    completed_pairs=valid_pairs,
                    total_pairs=total_pairs,
                    raw_metrics_ref=raw_ref,
                )
                continue

            cmp, breakdown = protocol._compare_objectives(
                cand_r.output.objective,
                champ_r.output.objective,
            )
            delta = protocol._compute_delta(cand_r.output.objective, champ_r.output.objective)

            raw_pairs.append(
                {
                    "case": case,
                    "seed": seed,
                    "comparison": cmp,
                    "delta": delta,
                    "decisive_metric": breakdown.decisive_metric,
                    "metric_deltas": {
                        m.name: m.signed_delta for m in breakdown.metrics
                    } if breakdown.metrics else {},
                    **runtime_fields,
                    **pair_cache_fields,
                }
            )
            valid_pairs += 1
            pair_fb = PairwiseCaseFeedback(
                case_id=os.path.basename(case),
                seed=seed,
                comparison=cmp,
                delta=delta,
                objective_comparison=breakdown,
                case_features=case_features,
            )
            pairs_by_case[os.path.basename(case)].append(pair_fb)
            # Log per-pair result with generic metric values
            _mc = {m.name: m for m in breakdown.metrics} if breakdown.metrics else {}
            _cand_vals = " ".join(f"{m.name}={m.candidate_value}" for m in breakdown.metrics) if breakdown.metrics else ""
            _chmp_vals = " ".join(f"{m.name}={m.champion_value}" for m in breakdown.metrics) if breakdown.metrics else ""
            logger.info(
                "Pair %s seed=%d: cmp=%s delta=%.4f decisive=%s cand(%s) champ(%s)",
                os.path.basename(case), seed, cmp, delta,
                breakdown.decisive_metric,
                _cand_vals, _chmp_vals,
            )
            _write_metrics_snapshot(complete=False)
            protocol._emit_progress(
                stage=stage.value,
                case=case,
                seed=seed,
                attempted_pairs=attempted_pairs,
                completed_pairs=valid_pairs,
                total_pairs=total_pairs,
                raw_metrics_ref=raw_ref,
            )

    # T2: Aggregate pairs → case-level results
    all_pair_feedback = [fb for fbs in pairs_by_case.values() for fb in fbs]
    case_level_results = _aggregate_pairs_to_case_level(all_pair_feedback)

    case_comparisons = [r.comparison for r in case_level_results]
    case_deltas = [r.delta for r in case_level_results]

    if not case_comparisons:
        stats = EvalStats(
            n_cases=0, wins=0, losses=0, ties=0,
            win_rate=0.0, median_delta=0.0, ci_low=-1.0, ci_high=-1.0,
        )
        gate = GateResult(outcome="fail", reason_codes=("NO_VALID_RUNS",))
    else:
        # T2: stats computed on case-level comparisons/deltas.
        # F3: when metric_specs are present, gate CI is computed
        # hierarchically by objective priority instead of one raw scalar.
        if (
            protocol._metric_specs is not None
            and getattr(protocol._objective_policy, "mode", None) == "weighted_sum"
        ):
            metric_order = ["weighted_sum"]
        else:
            metric_order = (
                [m.name for m in sorted(protocol._metric_specs, key=lambda s: s.priority)]
                if protocol._metric_specs is not None else None
            )
        stats = compute_eval_stats(
            case_comparisons,
            case_deltas,
            metric_deltas=[r.metric_deltas or {} for r in case_level_results],
            metric_order=metric_order,
        )

    runtime_stats = _build_runtime_stats(runtime_ratios, runtime_deltas_ms)
    runtime_evidence_status = _runtime_evidence_status(
        champion_cached_runtime_pairs=champion_cached_runtime_pairs,
        runtime_pairs=runtime_stats["runtime_pairs"],
        min_runtime_pairs=protocol.config.runtime.tie_min_runtime_pairs,
    )
    stats = replace(
        stats,
        runtime_ratio_median=runtime_stats["runtime_ratio_median"],
        runtime_delta_median_ms=runtime_stats["runtime_delta_median_ms"],
        runtime_regression_rate=runtime_stats["runtime_regression_rate"],
        runtime_pairs=runtime_stats["runtime_pairs"],
        champion_cached_runtime_pairs=champion_cached_runtime_pairs,
        runtime_evidence_status=runtime_evidence_status,
        total_pairs=total_pairs,
        attempted_pairs=attempted_pairs,
        valid_pairs=valid_pairs,
        failed_pairs=failed_pairs,
        candidate_failed_pairs=candidate_failed_pairs,
        champion_failed_pairs=champion_failed_pairs,
    )
    if case_comparisons:
        if stage == ExperimentStage.SCREENING:
            gate = screening_gate(stats, protocol.config)
        elif stage == ExperimentStage.VALIDATION:
            gate = validation_gate(stats, protocol.config)
        else:
            gate = frozen_gate(stats, protocol.config)

        if "RUNTIME_TIE_FRESH_CHAMPION_REQUIRED" in gate.reason_codes:
            runtime_evidence_status = "fresh_champion_required"
            stats = replace(
                stats,
                runtime_evidence_status=runtime_evidence_status,
            )

        if failed_pairs > 0 and stage in (ExperimentStage.VALIDATION, ExperimentStage.FROZEN):
            reason_codes = ["INCOMPLETE_EVIDENCE"]
            if candidate_failed_pairs:
                reason_codes.append("CANDIDATE_RUNTIME_FAILURE")
            if champion_failed_pairs:
                reason_codes.append("CHAMPION_RUNTIME_FAILURE")
            gate = GateResult(outcome="fail", reason_codes=tuple(reason_codes))

    candidate_telemetry_guard_summary = build_telemetry_guard_summary(
        candidate_runtimes=candidate_guard_runtimes,
        champion_runtimes=champion_guard_runtimes,
        problem_spec=protocol._problem_spec,
        selected_surface=normalized_selected_surface,
        expected_telemetry=expected_telemetry,
        declared_mechanisms=mechanism_changes,
        protected_objectives=protected_objectives,
        effect_observation_required=stage != ExperimentStage.SCREENING,
    )
    telemetry_guard_failures = candidate_telemetry_guard_summary.get("failures")
    if isinstance(telemetry_guard_failures, list) and telemetry_guard_failures:
        guard_codes = tuple(
            str(item.get("code") or "TELEMETRY_GUARD_FAILED")
            for item in telemetry_guard_failures
            if isinstance(item, Mapping)
        )
        gate = GateResult(
            outcome="fail",
            reason_codes=(
                *tuple(gate.reason_codes),
                "TELEMETRY_GUARD_FAILED",
                *guard_codes[:3],
            ),
        )
    runtime_budget_diagnostic_summary = runtime_budget_diagnostic(
        stage=stage,
        time_limit_sec=protocol.time_limit_sec,
        candidate_elapsed_ms=candidate_elapsed_samples_ms,
        champion_elapsed_ms=champion_elapsed_samples_ms,
        total_pairs=total_pairs,
    )
    if runtime_budget_diagnostic_summary:
        runtime_budget_code = str(
            runtime_budget_diagnostic_summary.get("code") or ""
        ).strip()
        if runtime_budget_code:
            gate = GateResult(
                outcome=gate.outcome,
                reason_codes=tuple(
                    dict.fromkeys((*tuple(gate.reason_codes), runtime_budget_code))
                ),
            )
    runtime_confidence = (
        "low_cached_champion" if champion_cached_runtime_pairs else "high"
    )
    runtime_gate_visibility = runtime_gate_visibility_summary(
        stage=stage.value,
        gate_outcome=gate.outcome,
        reason_codes=gate.reason_codes,
        runtime_confidence=runtime_confidence,
        runtime_evidence_status=runtime_evidence_status,
        runtime_pairs=stats.runtime_pairs,
        champion_cached_runtime_pairs=champion_cached_runtime_pairs,
        failed_pairs=failed_pairs,
        candidate_failed_pairs=candidate_failed_pairs,
        champion_failed_pairs=champion_failed_pairs,
        runtime_budget_diagnostic=runtime_budget_diagnostic_summary,
    )

    # Persist final raw metrics snapshot.
    _write_metrics_snapshot(complete=True)
    protocol._emit_progress(
        stage=stage.value,
        complete=True,
        attempted_pairs=attempted_pairs,
        completed_pairs=valid_pairs,
        valid_pairs=valid_pairs,
        failed_pairs=failed_pairs,
        candidate_failed_pairs=candidate_failed_pairs,
        champion_failed_pairs=champion_failed_pairs,
        total_pairs=total_pairs,
        selected_surface=normalized_selected_surface,
        raw_metrics_ref=raw_ref,
        runtime_budget_diagnostic=runtime_budget_diagnostic_summary,
        runtime_budget_diagnostic_code=(
            runtime_budget_diagnostic_summary.get("code")
            if runtime_budget_diagnostic_summary
            else None
        ),
        runtime_confidence=runtime_confidence,
        runtime_evidence_status=runtime_evidence_status,
        runtime_gate_visibility=runtime_gate_visibility,
    )
    pair_counts = _pair_feedback_counts(all_pair_feedback)
    runtime_summary = _format_runtime_summary(stats)
    failure_category_summary = _format_runtime_failure_categories(
        candidate_runtime_categories
    )
    runtime_failure_summary = (
        f" candidate_runtime_categories={failure_category_summary}"
        if failure_category_summary
        else ""
    )
    runtime_attempt_summary = _format_runtime_counter_summary(candidate_runtime_counters)
    telemetry_guard_summary = _format_telemetry_guard_summary(
        candidate_telemetry_guard_summary
    )
    phase_telemetry_summary = _format_phase_telemetry_summary(
        _finalize_phase_telemetry_summary(candidate_phase_telemetry_summary)
    )
    runtime_budget_summary = format_runtime_budget_diagnostic(
        runtime_budget_diagnostic_summary
    )
    champion_cache_summary = (
        f" champion_cache_hits={champion_cache_hits}"
        f" champion_cache_misses={champion_cache_misses}"
        f" champion_cached_runtime_pairs={champion_cached_runtime_pairs}"
        f" runtime_confidence={runtime_confidence}"
        f" runtime_evidence_status={runtime_evidence_status}"
    )
    runtime_evidence_policy = runtime_evidence_policy_summary(
        runtime_confidence=runtime_confidence,
        runtime_evidence_status=runtime_evidence_status,
        runtime_pairs=stats.runtime_pairs,
        champion_cached_runtime_pairs=champion_cached_runtime_pairs,
        runtime_aggregate_excluded=(
            champion_cached_runtime_pairs > 0 and stats.runtime_pairs <= 0
        ),
    )
    champion_cache_summary += (
        " runtime_signal_role="
        f"{runtime_evidence_policy.get('runtime_signal_role', 'unknown')}"
        " runtime_standalone_optimization_signal="
        f"{str(runtime_evidence_policy.get('standalone_optimization_signal')).lower()}"
    )
    if runtime_evidence_policy.get("fresh_champion_required"):
        champion_cache_summary += " fresh_champion_required=true"
    if runtime_gate_visibility:
        champion_cache_summary += (
            " runtime_gate_reason_semantics="
            f"{','.join(runtime_gate_visibility.get('reason_semantics') or ())}"
            " runtime_rerun_recommendation="
            f"{runtime_gate_visibility.get('rerun_recommendation', 'none')}"
        )

    # Exposure control
    if stage == ExperimentStage.SCREENING:
        exposed = (
            f"stage={stage.value} case_win_rate={stats.win_rate:.2f} "
            f"gate_win_rate={stats.win_rate:.2f} "
            f"pair_win_rate={pair_counts['win_rate']:.2f} "
            f"pair_wins={pair_counts['wins']} "
            f"pair_losses={pair_counts['losses']} "
            f"pair_ties={pair_counts['ties']} "
            f"median_delta={stats.median_delta:.4f} outcome={gate.outcome} "
            f"failed_pairs={failed_pairs} candidate_failures={candidate_failed_pairs} "
            f"{runtime_summary}{runtime_failure_summary}{runtime_attempt_summary}"
            f"{telemetry_guard_summary}{phase_telemetry_summary}"
            f"{runtime_budget_summary}"
            f"{champion_cache_summary}"
        )
    else:
        # Validation / Frozen: aggregate summary only, no per-case data
        exposed = (
            f"stage={stage.value} outcome={gate.outcome} "
            f"stat={stats.statistical_status or 'legacy'} "
            f"metric={stats.statistical_metric or 'scalar'} "
            f"valid_pairs={valid_pairs}/{total_pairs} failed_pairs={failed_pairs} "
            f"candidate_failures={candidate_failed_pairs} champion_failures={champion_failed_pairs} "
            f"{runtime_summary}{runtime_failure_summary}{runtime_attempt_summary}"
            f"{telemetry_guard_summary}{phase_telemetry_summary}"
            f"{runtime_budget_summary}"
            f"{champion_cache_summary}"
        )

    # Build case-level feedback for screening only
    case_fb: tuple = ()
    pattern: "ScreeningPatternSummary | None" = None
    if stage == ExperimentStage.SCREENING and all_pair_feedback:
        case_fb = tuple(_aggregate_case_feedback(all_pair_feedback))
        pattern = _build_pattern_summary(case_fb)

    result = ProtocolResult(
        stage=stage,
        stats=stats,
        gate_outcome=gate.outcome,
        reason_codes=gate.reason_codes,
        exposed_summary=exposed,
        raw_metrics_ref=raw_ref,
        case_ids=tuple(cases),
        seed_set=tuple(seeds),
        pair_feedback=tuple(all_pair_feedback) if stage == ExperimentStage.SCREENING else (),
        case_feedback=case_fb,
        pattern_summary=pattern,
        selected_surface=normalized_selected_surface or selected_surface,
        candidate_surface_runtime_summary=_surface_runtime_summary_with_guard(
            candidate_surface_runtime_summary,
            candidate_telemetry_guard_summary,
            runtime_budget_diagnostic_summary,
        ),
        candidate_phase_telemetry_summary=_finalize_phase_telemetry_summary(
            candidate_phase_telemetry_summary
        ),
        candidate_runtime_failure_categories=dict(candidate_runtime_categories),
        candidate_first_runtime_failure=candidate_first_runtime_failure,
        candidate_operator_attempts=candidate_runtime_counters["operator_attempts"],
        candidate_operator_accepted=candidate_runtime_counters["operator_accepted"],
        candidate_operator_errors=candidate_runtime_counters["operator_errors"],
        candidate_operator_invalid_outputs=(
            candidate_runtime_counters["operator_invalid_outputs"]
        ),
        candidate_policy_errors=candidate_runtime_counters["policy_errors"],
        candidate_construction_errors=(
            candidate_runtime_counters["construction_errors"]
        ),
        candidate_portfolio_errors=candidate_runtime_counters["portfolio_errors"],
        candidate_runtime_stop_reasons=dict(candidate_runtime_stop_reasons),
        champion_cache_hits=champion_cache_hits,
        champion_cache_misses=champion_cache_misses,
        champion_cached_runtime_pairs=champion_cached_runtime_pairs,
        runtime_confidence=runtime_confidence,
        runtime_evidence_status=runtime_evidence_status,
    )
    no_objective_effect = (
        stats.wins == 0
        and stats.losses == 0
        and pair_counts["wins"] == 0
        and pair_counts["losses"] == 0
        and abs(float(stats.median_delta or 0.0)) <= 1e-12
    )
    mechanism_evidence = mechanism_evidence_for_protocol(result)
    opportunity_diagnostics = opportunity_diagnostics_for_protocol(
        result,
        mechanism_evidence=mechanism_evidence,
        no_objective_effect=no_objective_effect,
    )
    return replace(
        result,
        mechanism_evidence=mechanism_evidence,
        opportunity_diagnostics=opportunity_diagnostics,
        opportunity_status=opportunity_status_for_diagnostics(
            opportunity_diagnostics
        ),
    )


def _append_elapsed_sample(samples: list[float], value: Any) -> None:
    try:
        elapsed = float(value)
    except (TypeError, ValueError):
        return
    if elapsed >= 0:
        samples.append(elapsed)


def _runtime_evidence_status(
    *,
    champion_cached_runtime_pairs: int,
    runtime_pairs: int,
    min_runtime_pairs: int,
) -> str:
    if champion_cached_runtime_pairs > 0 and runtime_pairs < min_runtime_pairs:
        return "insufficient"
    return "sufficient"


__all__ = ["run_experiment"]
