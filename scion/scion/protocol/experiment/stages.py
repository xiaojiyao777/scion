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
from scion.protocol.gates import GateResult, frozen_gate, screening_gate, validation_gate
from scion.protocol.stats import compute_eval_stats
from scion.runtime.audit import (
    declared_surface_required_runtime_fields,
    format_runtime_audit_failure,
    normalize_surface_name,
    runtime_audit_failure_from_result,
)
from scion.runtime.telemetry_guard import build_telemetry_guard_summary
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
from .runtime_observation import (
    _append_guard_runtime,
    _build_runtime_stats,
    _candidate_runtime_observation,
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
    candidate_runtime_counters: dict[str, int] = {
        "operator_attempts": 0,
        "operator_accepted": 0,
        "operator_errors": 0,
        "operator_invalid_outputs": 0,
        "policy_errors": 0,
        "construction_errors": 0,
        "portfolio_errors": 0,
        "solver_algorithm_errors": 0,
        "solver_algorithm_search_iterations": 0,
        "solver_algorithm_move_attempts": 0,
        "solver_algorithm_accepted_moves": 0,
        "solver_algorithm_improving_moves": 0,
        "solver_algorithm_neutral_accepted_moves": 0,
        "solver_algorithm_baseline_calls": 0,
        "solver_algorithm_baseline_errors": 0,
    }
    candidate_runtime_stop_reasons: dict[str, int] = {}
    candidate_guard_runtimes: list[Mapping[str, Any]] = []
    champion_guard_runtimes: list[Mapping[str, Any]] = []
    candidate_telemetry_guard_summary: dict[str, Any] = {}
    normalized_selected_surface = normalize_surface_name(selected_surface) or None
    surface_required_runtime_fields = declared_surface_required_runtime_fields(
        protocol._problem_spec,
        normalized_selected_surface,
    )
    candidate_surface_runtime_summary = _surface_runtime_summary_template(
        selected_surface=normalized_selected_surface,
        required_fields=surface_required_runtime_fields,
    )

    def _write_metrics_snapshot(*, complete: bool) -> None:
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
                    "runtime_stats": _build_runtime_stats(
                        runtime_ratios,
                        runtime_deltas_ms,
                    ),
                    "candidate_surface_runtime_summary": (
                        _surface_runtime_summary_with_guard(
                            candidate_surface_runtime_summary,
                            candidate_telemetry_guard_summary,
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
            protocol._emit_progress(
                stage=stage.value,
                case=case,
                seed=seed,
                attempted_pairs=attempted_pairs,
                completed_pairs=valid_pairs,
                total_pairs=total_pairs,
                raw_metrics_ref=raw_ref,
            )
            champ_r = protocol.runner.run_solver(
                workdir=champion_ws,
                instance_path=case,
                seed=seed,
                time_limit_sec=protocol.time_limit_sec,
                registry_path=os.path.join(champion_ws, "registry.yaml"),
                selected_surface=normalized_selected_surface,
            )
            cand_r = protocol.runner.run_solver(
                workdir=candidate_ws,
                instance_path=case,
                seed=seed,
                time_limit_sec=protocol.time_limit_sec,
                registry_path=os.path.join(candidate_ws, "registry.yaml"),
                selected_surface=normalized_selected_surface,
            )
            _record_surface_runtime_sample(
                cand_r,
                candidate_surface_runtime_summary,
            )
            runtime_fields = _runtime_fields(
                cand_r,
                champ_r,
                candidate_required_runtime_fields=surface_required_runtime_fields,
            )
            _append_guard_runtime(candidate_guard_runtimes, cand_r)
            _append_guard_runtime(champion_guard_runtimes, champ_r)
            _record_runtime_sample(
                runtime_fields,
                runtime_ratios,
                runtime_deltas_ms,
            )
            runtime_observation = _candidate_runtime_observation(cand_r)
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

            champ_audit_failure = runtime_audit_failure_from_result(champ_r)
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
    stats = replace(
        stats,
        runtime_ratio_median=runtime_stats["runtime_ratio_median"],
        runtime_delta_median_ms=runtime_stats["runtime_delta_median_ms"],
        runtime_regression_rate=runtime_stats["runtime_regression_rate"],
        runtime_pairs=runtime_stats["runtime_pairs"],
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

    # Persist final raw metrics snapshot.
    _write_metrics_snapshot(complete=True)
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
    runtime_attempt_summary = (
        " candidate_operator_attempts="
        f"{candidate_runtime_counters['operator_attempts']}"
        " candidate_operator_accepted="
        f"{candidate_runtime_counters['operator_accepted']}"
        " candidate_operator_errors="
        f"{candidate_runtime_counters['operator_errors']}"
        " candidate_invalid_outputs="
        f"{candidate_runtime_counters['operator_invalid_outputs']}"
        " candidate_solver_algorithm_iterations="
        f"{candidate_runtime_counters['solver_algorithm_search_iterations']}"
        " candidate_solver_algorithm_move_attempts="
        f"{candidate_runtime_counters['solver_algorithm_move_attempts']}"
        " candidate_solver_algorithm_accepted_moves="
        f"{candidate_runtime_counters['solver_algorithm_accepted_moves']}"
        " candidate_solver_algorithm_improving_moves="
        f"{candidate_runtime_counters['solver_algorithm_improving_moves']}"
        " candidate_solver_algorithm_neutral_moves="
        f"{candidate_runtime_counters['solver_algorithm_neutral_accepted_moves']}"
        " candidate_solver_algorithm_baseline_calls="
        f"{candidate_runtime_counters['solver_algorithm_baseline_calls']}"
        " candidate_solver_algorithm_errors="
        f"{candidate_runtime_counters['solver_algorithm_errors']}"
    )
    telemetry_guard_summary = _format_telemetry_guard_summary(
        candidate_telemetry_guard_summary
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
            f"{telemetry_guard_summary}"
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
            f"{telemetry_guard_summary}"
        )

    # Build case-level feedback for screening only
    case_fb: tuple = ()
    pattern: "ScreeningPatternSummary | None" = None
    if stage == ExperimentStage.SCREENING and all_pair_feedback:
        case_fb = tuple(_aggregate_case_feedback(all_pair_feedback))
        pattern = _build_pattern_summary(case_fb)

    return ProtocolResult(
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
    )


__all__ = ["run_experiment"]
