from __future__ import annotations

import json
import logging
import os
import uuid as _uuid_mod
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import replace
from typing import TYPE_CHECKING, Any, Dict, List

from scion.core.models import (
    EvalStats,
    ExperimentStage,
    PairwiseCaseFeedback,
    ProtocolResult,
    RunResult,
    ScreeningPatternSummary,
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
from scion.protocol.gates import (
    GateResult,
    frozen_gate,
    screening_gate,
    validation_gate,
)
from scion.protocol.stats import compute_eval_stats
from scion.runtime.audit import (
    declared_surface_required_runtime_fields,
    format_runtime_audit_failure,
    normalize_surface_name,
    runtime_audit_failure_from_result,
    runtime_audit_issue_blocks_execution,
)

from .cache import compute_workspace_digest
from .failures import (
    _candidate_audit_failure_category,
    _candidate_process_failure_category,
    _format_runtime_failure_categories,
    _runtime_failure_summary,
    _runtime_failure_summary_from_audit,
)
from .feedback import (
    _aggregate_case_feedback,
    _aggregate_pairs_to_case_level,
    _build_pattern_summary,
    _extract_case_features,
    _pair_feedback_counts,
    _protected_objective_regressions,
)
from .phase_telemetry import (
    _finalize_phase_telemetry_summary,
    _format_phase_telemetry_summary,
    _phase_telemetry_summary_template,
    _record_phase_telemetry_sample,
)
from .proposal_evidence import problem_proposal_mechanism_evidence
from .runtime_observation import (
    _build_runtime_stats,
    _candidate_runtime_counter_template,
    _candidate_runtime_observation,
    _format_runtime_counter_summary,
    _format_runtime_summary,
    _merge_runtime_observation,
    _record_runtime_sample,
    _runtime_fields,
)
from .selection import (
    configured_priority_case_ids,
    resolved_configured_priority_case_ids,
)
from .surface_runtime import (
    _record_surface_runtime_sample,
    _surface_runtime_summary_template,
    _surface_runtime_summary_with_diagnostics,
)
from .types import CaseLevelResult
from .values import _increment_category

if TYPE_CHECKING:
    from .facade import ExperimentProtocol

logger = logging.getLogger(__name__)

SCREENING_PARTIAL_CHAMPION_EVIDENCE = "SCREENING_PARTIAL_CHAMPION_EVIDENCE"


def run_experiment(
    protocol: "ExperimentProtocol",
    stage: ExperimentStage,
    candidate_ws: str,
    champion_ws: str,
    hypothesis_action: str,
    expand: bool = False,
    expand_round: int = 1,
    selected_surface: str | None = None,
) -> ProtocolResult:
    """Execute paired A/B evaluation for the given stage.

    T2: Statistical unit is case (not pair). Each case is evaluated across
    its preregistered seed prefix, then reduced by the configured case rule.
    T4: expansion uses deterministic case and seed prefixes.
    T5: case count depends on stage + hypothesis_action + expand flag.
    """
    cases = protocol._select_cases(
        stage,
        hypothesis_action,
        expand_round if expand else 0,
    )
    configured_priority_cases = configured_priority_case_ids(
        config=protocol.config,
        stage=stage,
    )
    effective_priority_case_ids = resolved_configured_priority_case_ids(
        config=protocol.config,
        stage=stage,
        all_cases=protocol.split_manager.get_cases(stage),
        selected_cases=cases,
    )
    seeds = protocol._select_seeds(stage, expanded=expand)
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
    runtime_budget_diagnostic_summary: dict[str, Any] | None = None
    candidate_elapsed_samples_ms: list[float] = []
    champion_elapsed_samples_ms: list[float] = []
    candidate_time_limit_samples_sec: list[float] = []
    champion_time_limit_samples_sec: list[float] = []
    champion_cache_hits = 0
    champion_cache_misses = 0
    champion_cache_writes = 0
    champion_cached_runtime_pairs = 0
    problem_runtime_pairs: list[dict[str, Any]] = []
    runtime_evidence_status = "sufficient"
    protected_objective_regressions: tuple[str, ...] = ()
    runtime_model = getattr(
        protocol.config.runtime,
        "runtime_model",
        "comparative",
    )
    runtime_gate_visibility: dict[str, Any] = {}
    normalized_selected_surface = normalize_surface_name(selected_surface) or None
    objective_semantics = protocol.objective_semantics
    case_aggregation_method = protocol.config.case_aggregation
    case_effect_metric = (
        "weighted_sum"
        if (
            protocol._metric_specs is not None
            and getattr(protocol._objective_policy, "mode", None) == "weighted_sum"
        )
        else (protocol.config.effect_metric or "")
    )
    case_level_results: list[CaseLevelResult] = []
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
    case_path_resolutions: dict[str, dict[str, Any]] = {}
    resolved_case_paths: dict[str, dict[str, str]] = {}
    for case in cases:
        champion_resolution = protocol._resolve_case_path_status(
            case,
            workspace=champion_ws,
        )
        candidate_resolution = protocol._resolve_case_path_status(
            case,
            workspace=candidate_ws,
        )
        case_path_resolutions[case] = {
            "champion": champion_resolution.as_metrics(),
            "candidate": candidate_resolution.as_metrics(),
        }
        resolved_case_paths[case] = {
            "champion": champion_resolution.resolved,
            "candidate": candidate_resolution.resolved,
        }
    # Problem providers receive every distinct screening case even when no
    # solver pair completes.  These path-only inputs are ephemeral and never
    # enter raw Protocol metrics or the generic proposal envelope.
    if stage == ExperimentStage.SCREENING:
        problem_runtime_pairs.extend(
            {"case_path": resolved_case_paths[case]["candidate"]}
            for case in cases
        )

    def _case_path_resolution_status_counts() -> dict[str, int]:
        counts: dict[str, int] = {}
        for side_records in case_path_resolutions.values():
            for side, payload in side_records.items():
                if not isinstance(payload, Mapping):
                    continue
                status = str(payload.get("status") or "unknown")
                key = f"{side}:{status}"
                counts[key] = counts.get(key, 0) + 1
        return counts

    def _write_metrics_snapshot(*, complete: bool) -> None:
        runtime_stats_snapshot = _build_runtime_stats(
            runtime_ratios,
            runtime_deltas_ms,
        )
        runtime_confidence_snapshot = (
            "low_cached_champion" if champion_cached_runtime_pairs else "high"
        )
        runtime_aggregate_excluded_snapshot = (
            champion_cached_runtime_pairs > 0
            and runtime_stats_snapshot["runtime_pairs"] <= 0
        )
        runtime_evidence_policy = runtime_evidence_policy_summary(
            runtime_confidence=runtime_confidence_snapshot,
            runtime_evidence_status=runtime_evidence_status,
            runtime_model=runtime_model,
            runtime_pairs=runtime_stats_snapshot["runtime_pairs"],
            champion_cached_runtime_pairs=champion_cached_runtime_pairs,
            runtime_aggregate_excluded=runtime_aggregate_excluded_snapshot,
            candidate_runtime_pair_evidence_count=(
                candidate_surface_runtime_summary.get("candidate_pairs", 0)
                if runtime_aggregate_excluded_snapshot
                else 0
            ),
        )
        with open(raw_ref, "w") as f:
            json.dump(
                {
                    "stage": stage.value,
                    "selected_surface": normalized_selected_surface,
                    "objective_semantics": objective_semantics,
                    "effect_metric": protocol.config.effect_metric or None,
                    "case_aggregation": {
                        "method": case_aggregation_method,
                        "effect_metric": case_effect_metric or None,
                        "equivalence_band": protocol.config.case_equivalence_band,
                    },
                    "protected_objectives": list(protocol.config.protected_objectives),
                    "protected_objective_regressions": list(
                        protected_objective_regressions
                    ),
                    "configured_priority_case_ids": list(configured_priority_cases),
                    "effective_priority_case_ids": list(effective_priority_case_ids),
                    "case_ids": cases,
                    "time_limit_policy": protocol.time_limit_policy_summary(
                        stage=stage,
                        cases=tuple(cases),
                    ),
                    "case_path_resolution": {
                        "strict": bool(getattr(protocol, "_strict_case_paths", False)),
                        "status_counts": _case_path_resolution_status_counts(),
                        "cases": case_path_resolutions,
                    },
                    "seed_set": seeds,
                    "case_level_results": [
                        {
                            "case_id": row.case_id,
                            "comparison": row.comparison,
                            "delta": row.delta,
                            "metric_deltas": dict(row.metric_deltas or {}),
                        }
                        for row in case_level_results
                    ],
                    "total_pairs": total_pairs,
                    "attempted_pairs": attempted_pairs,
                    "valid_pairs": valid_pairs,
                    "failed_pairs": failed_pairs,
                    "candidate_failed_pairs": candidate_failed_pairs,
                    "champion_failed_pairs": champion_failed_pairs,
                    "screening_evidence_status": _screening_evidence_status(
                        stage=stage,
                        complete=complete,
                        champion_failed_pairs=champion_failed_pairs,
                    ),
                    "screening_partial_champion_evidence": (
                        _screening_partial_champion_evidence(
                            stage=stage,
                            total_pairs=total_pairs,
                            valid_pairs=valid_pairs,
                            failed_pairs=failed_pairs,
                            champion_failed_pairs=champion_failed_pairs,
                        )
                    ),
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
                        _surface_runtime_summary_with_diagnostics(
                            candidate_surface_runtime_summary,
                            runtime_budget_diagnostic_summary,
                        )
                    ),
                    "candidate_phase_telemetry_summary": (
                        _finalize_phase_telemetry_summary(
                            candidate_phase_telemetry_summary
                        )
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
            resolved_for_case = resolved_case_paths[case]
            champion_case_path = resolved_for_case["champion"]
            candidate_case_path = resolved_for_case["candidate"]
            pair_time_limit_sec = protocol.resolve_time_limit_sec(
                stage=stage,
                case_path=case,
            )
            pair_budget_fields = {"time_limit_sec": pair_time_limit_sec}
            protocol._emit_progress(
                stage=stage.value,
                case=case,
                seed=seed,
                time_limit_sec=pair_time_limit_sec,
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
                    time_limit_sec=pair_time_limit_sec,
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
                    time_limit_sec=pair_time_limit_sec,
                    registry_path=os.path.join(champion_ws, "registry.yaml"),
                    selected_surface=normalized_selected_surface,
                )
            cand_r = protocol.runner.run_solver(
                workdir=candidate_ws,
                instance_path=candidate_case_path,
                seed=seed,
                time_limit_sec=pair_time_limit_sec,
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
                if _append_elapsed_sample(
                    champion_elapsed_samples_ms, champ_r.elapsed_ms
                ):
                    champion_time_limit_samples_sec.append(float(pair_time_limit_sec))
            if _append_elapsed_sample(candidate_elapsed_samples_ms, cand_r.elapsed_ms):
                candidate_time_limit_samples_sec.append(float(pair_time_limit_sec))
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
                champ_audit_issue = runtime_audit_failure_from_result(champ_r)
                champ_audit_failure = (
                    champ_audit_issue
                    if runtime_audit_issue_blocks_execution(champ_audit_issue)
                    else None
                )
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
                paired_failure_category = (
                    _paired_process_failure_category(champ_r, cand_r)
                    if side == "both"
                    else None
                )
                failure_record = {
                    "case": case,
                    "seed": seed,
                    "side": side,
                    "comparison": "invalid",
                    "error_category": (
                        paired_failure_category
                        if paired_failure_category is not None
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
                    **pair_budget_fields,
                    **runtime_fields,
                    **pair_cache_fields,
                    "stderr": champ_r.stderr or "",
                    "candidate_stderr": (cand_r.stderr or "" if side == "both" else ""),
                }
                raw_failures.append(failure_record)
                raw_pairs.append(
                    {
                        "case": case,
                        "seed": seed,
                        "comparison": "invalid",
                        "delta": None,
                        "decisive_metric": (
                            paired_failure_category
                            if paired_failure_category is not None
                            else "champion_runtime_failure"
                        ),
                        "metric_deltas": {},
                        **pair_budget_fields,
                        **runtime_fields,
                        **pair_cache_fields,
                        "failure": failure_record,
                    }
                )
                logger.info(
                    "Pair %s seed=%d: %s solver failed category=%s elapsed_ms=%d → invalid",
                    os.path.basename(case),
                    seed,
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
                    candidate_first_runtime_failure = _runtime_failure_summary(
                        category=category,
                        code=str(
                            cand_r.error_category
                            or cand_r.exit_code
                            or "process_failure"
                        ),
                        surface=None,
                        component="solver_process",
                        detail_summary=cand_r.stderr
                        or cand_r.stdout
                        or "candidate solver process failed",
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
                    **pair_budget_fields,
                    **runtime_fields,
                    **pair_cache_fields,
                    "stderr": cand_r.stderr or "",
                }
                raw_failures.append(failure_record)
                raw_pairs.append(
                    {
                        "case": case,
                        "seed": seed,
                        "comparison": "loss",
                        "delta": -1.0,
                        "decisive_metric": "runtime_failure",
                        "metric_deltas": {},
                        **pair_budget_fields,
                        **runtime_fields,
                        **pair_cache_fields,
                        "failure": failure_record,
                    }
                )
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
                    os.path.basename(case),
                    seed,
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
                candidate_output_missing = cand_r.output is None
                champion_output_missing = champ_r.output is None
                failed_pairs += 1
                if candidate_output_missing:
                    candidate_failed_pairs += 1
                    _increment_category(candidate_runtime_categories, "invalid_output")
                    if candidate_first_runtime_failure is None:
                        candidate_first_runtime_failure = _runtime_failure_summary(
                            category="invalid_output",
                            code="missing_output",
                            surface=None,
                            component="solver_output",
                            detail_summary="candidate solver succeeded without parsed output",
                        )
                if champion_output_missing:
                    champion_failed_pairs += 1
                if candidate_output_missing and champion_output_missing:
                    failure_side = "both"
                elif candidate_output_missing:
                    failure_side = "candidate"
                else:
                    failure_side = "champion"
                failure_record = {
                    "case": case,
                    "seed": seed,
                    "side": failure_side,
                    "comparison": "invalid",
                    "error_category": "missing_output",
                    **pair_budget_fields,
                    **runtime_fields,
                    **pair_cache_fields,
                }
                raw_failures.append(failure_record)
                raw_pairs.append(
                    {
                        "case": case,
                        "seed": seed,
                        "comparison": "invalid",
                        "delta": None,
                        "decisive_metric": "missing_output",
                        "metric_deltas": {},
                        **pair_budget_fields,
                        **runtime_fields,
                        **pair_cache_fields,
                        "failure": failure_record,
                    }
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

            cand_audit_issue = runtime_audit_failure_from_result(
                cand_r,
                problem_spec=protocol._problem_spec,
                selected_surface=normalized_selected_surface,
            )
            cand_audit_failure = (
                cand_audit_issue
                if runtime_audit_issue_blocks_execution(cand_audit_issue)
                else None
            )
            if cand_audit_failure is not None:
                audit_category = _candidate_audit_failure_category(cand_audit_failure)
                if audit_category not in (runtime_observation.get("categories") or {}):
                    _increment_category(candidate_runtime_categories, audit_category)
                if candidate_first_runtime_failure is None:
                    candidate_first_runtime_failure = (
                        _runtime_failure_summary_from_audit(
                            cand_audit_failure,
                            category=audit_category,
                        )
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
                    **pair_budget_fields,
                    **runtime_fields,
                    **pair_cache_fields,
                    "runtime_audit": cand_audit_failure,
                }
                raw_failures.append(failure_record)
                raw_pairs.append(
                    {
                        "case": case,
                        "seed": seed,
                        "comparison": "loss",
                        "delta": -1.0,
                        "decisive_metric": cand_audit_failure["error_category"],
                        "metric_deltas": {},
                        **pair_budget_fields,
                        **runtime_fields,
                        **pair_cache_fields,
                        "failure": failure_record,
                    }
                )
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
                    os.path.basename(case),
                    seed,
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
                    **pair_budget_fields,
                    **runtime_fields,
                    **pair_cache_fields,
                    "runtime_audit": champ_audit_failure,
                }
                raw_failures.append(failure_record)
                raw_pairs.append(
                    {
                        "case": case,
                        "seed": seed,
                        "comparison": "invalid",
                        "delta": None,
                        "decisive_metric": f"champion_{champ_audit_failure['error_category']}",
                        "metric_deltas": {},
                        **pair_budget_fields,
                        **runtime_fields,
                        **pair_cache_fields,
                        "failure": failure_record,
                    }
                )
                logger.info(
                    "Pair %s seed=%d: champion runtime audit failed: %s",
                    os.path.basename(case),
                    seed,
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
            delta = protocol._compute_delta(
                cand_r.output.objective, champ_r.output.objective
            )

            raw_pairs.append(
                {
                    "case": case,
                    "seed": seed,
                    "comparison": cmp,
                    "objective_semantics": objective_semantics,
                    "delta": delta,
                    "decisive_metric": breakdown.decisive_metric,
                    "metric_deltas": (
                        {m.name: m.signed_delta for m in breakdown.metrics}
                        if breakdown.metrics
                        else {}
                    ),
                    **pair_budget_fields,
                    **runtime_fields,
                    **pair_cache_fields,
                }
            )
            problem_runtime_pairs.append(
                {
                    "candidate_runtime": dict(cand_r.output.runtime),
                    "champion_runtime": dict(champ_r.output.runtime),
                    "champion_result_source": champion_result_source,
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
            _cand_vals = (
                " ".join(f"{m.name}={m.candidate_value}" for m in breakdown.metrics)
                if breakdown.metrics
                else ""
            )
            _chmp_vals = (
                " ".join(f"{m.name}={m.champion_value}" for m in breakdown.metrics)
                if breakdown.metrics
                else ""
            )
            logger.info(
                "Pair %s seed=%d: cmp=%s delta=%.4f decisive=%s cand(%s) champ(%s)",
                os.path.basename(case),
                seed,
                cmp,
                delta,
                breakdown.decisive_metric,
                _cand_vals,
                _chmp_vals,
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
    pair_wins = sum(1 for fb in all_pair_feedback if fb.comparison == "win")
    pair_losses = sum(1 for fb in all_pair_feedback if fb.comparison == "loss")
    pair_ties = len(all_pair_feedback) - pair_wins - pair_losses
    case_level_results = _aggregate_pairs_to_case_level(
        all_pair_feedback,
        aggregation=case_aggregation_method,
        effect_metric=case_effect_metric,
        equivalence_band=protocol.config.case_equivalence_band,
    )

    case_comparisons = [r.comparison for r in case_level_results]
    case_deltas = [r.delta for r in case_level_results]

    if not case_comparisons:
        stats = EvalStats(
            n_cases=0,
            wins=0,
            losses=0,
            ties=0,
            win_rate=0.0,
            median_delta=0.0,
            ci_low=-1.0,
            ci_high=-1.0,
        )
        gate = GateResult(outcome="fail", reason_codes=("NO_VALID_RUNS",))
    else:
        # T2: stats are computed on case-level comparisons/deltas. When typed
        # metrics are present, the problem-owned effect metric supplies the
        # practical-effect estimate while all objective rows stay observable.
        if (
            protocol._metric_specs is not None
            and getattr(protocol._objective_policy, "mode", None) == "weighted_sum"
        ):
            metric_order = ["weighted_sum"]
            effect_metric = "weighted_sum"
        else:
            metric_order = (
                [
                    m.name
                    for m in sorted(protocol._metric_specs, key=lambda s: s.priority)
                ]
                if protocol._metric_specs is not None
                else None
            )
            effect_metric = protocol.config.effect_metric or None
        bootstrap_n = (
            protocol.config.gates.validation.bootstrap_n
            if stage in (ExperimentStage.VALIDATION, ExperimentStage.FROZEN)
            else 1000
        )
        stats = compute_eval_stats(
            case_comparisons,
            case_deltas,
            n_boot=bootstrap_n,
            metric_deltas=[r.metric_deltas or {} for r in case_level_results],
            metric_order=metric_order,
            effect_metric=effect_metric,
        )

    protected_objective_regressions = _protected_objective_regressions(
        all_pair_feedback,
        protocol.config.protected_objectives,
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
        pair_wins=pair_wins,
        pair_losses=pair_losses,
        pair_ties=pair_ties,
        protected_objective_regressions=protected_objective_regressions,
    )
    if case_comparisons:
        if stage == ExperimentStage.SCREENING:
            gate = screening_gate(stats, protocol.config, expanded=expand)
        elif stage == ExperimentStage.VALIDATION:
            gate = validation_gate(stats, protocol.config, expanded=expand)
        else:
            gate = frozen_gate(stats, protocol.config)

        if "RUNTIME_TIE_FRESH_CHAMPION_REQUIRED" in gate.reason_codes:
            runtime_evidence_status = "fresh_champion_required"
            stats = replace(
                stats,
                runtime_evidence_status=runtime_evidence_status,
            )

        if failed_pairs > 0 and stage in (
            ExperimentStage.VALIDATION,
            ExperimentStage.FROZEN,
        ):
            reason_codes = ["INCOMPLETE_EVIDENCE"]
            if candidate_failed_pairs:
                reason_codes.append("CANDIDATE_RUNTIME_FAILURE")
            if champion_failed_pairs:
                reason_codes.append("CHAMPION_RUNTIME_FAILURE")
            gate = GateResult(outcome="fail", reason_codes=tuple(reason_codes))

        if stage == ExperimentStage.SCREENING and champion_failed_pairs > 0:
            gate = GateResult(
                outcome="unclear" if gate.outcome == "pass" else gate.outcome,
                reason_codes=tuple(
                    dict.fromkeys(
                        (
                            *tuple(gate.reason_codes),
                            SCREENING_PARTIAL_CHAMPION_EVIDENCE,
                        )
                    )
                ),
            )

    runtime_budget_diagnostic_summary = runtime_budget_diagnostic(
        stage=stage,
        time_limit_sec=(
            candidate_time_limit_samples_sec
            or champion_time_limit_samples_sec
            or [protocol.time_limit_sec]
        ),
        runtime_model=runtime_model,
        candidate_elapsed_ms=candidate_elapsed_samples_ms,
        champion_elapsed_ms=champion_elapsed_samples_ms,
        candidate_time_limit_sec=candidate_time_limit_samples_sec,
        champion_time_limit_sec=champion_time_limit_samples_sec,
        total_pairs=total_pairs,
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
    runtime_attempt_summary = _format_runtime_counter_summary(
        candidate_runtime_counters
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
    runtime_aggregate_excluded = (
        champion_cached_runtime_pairs > 0 and stats.runtime_pairs <= 0
    )
    runtime_evidence_policy = runtime_evidence_policy_summary(
        runtime_confidence=runtime_confidence,
        runtime_evidence_status=runtime_evidence_status,
        runtime_model=runtime_model,
        runtime_pairs=stats.runtime_pairs,
        champion_cached_runtime_pairs=champion_cached_runtime_pairs,
        runtime_aggregate_excluded=runtime_aggregate_excluded,
        candidate_runtime_pair_evidence_count=(
            candidate_surface_runtime_summary.get("candidate_pairs", 0)
            if runtime_aggregate_excluded
            else 0
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
            f"objective_semantics={objective_semantics} "
            f"failed_pairs={failed_pairs} candidate_failures={candidate_failed_pairs} "
            f"champion_failures={champion_failed_pairs} "
            f"screening_evidence_status={_screening_evidence_status(stage=stage, complete=True, champion_failed_pairs=champion_failed_pairs)} "
            f"reason_codes={','.join(gate.reason_codes) or 'none'} "
            f"{runtime_summary}{runtime_failure_summary}{runtime_attempt_summary}"
            f"{phase_telemetry_summary}"
            f"{runtime_budget_summary}"
            f"{champion_cache_summary}"
        )
    else:
        # Validation / Frozen: aggregate summary only, no per-case data
        exposed = (
            f"stage={stage.value} outcome={gate.outcome} "
            f"stat={stats.statistical_status or 'legacy'} "
            f"metric={stats.statistical_metric or 'scalar'} "
            f"objective_semantics={objective_semantics} "
            f"valid_pairs={valid_pairs}/{total_pairs} failed_pairs={failed_pairs} "
            f"candidate_failures={candidate_failed_pairs} champion_failures={champion_failed_pairs} "
            f"{runtime_summary}{runtime_failure_summary}{runtime_attempt_summary}"
            f"{phase_telemetry_summary}"
            f"{runtime_budget_summary}"
            f"{champion_cache_summary}"
        )

    # Build case-level feedback for screening only
    case_fb: tuple = ()
    pattern: "ScreeningPatternSummary | None" = None
    if stage == ExperimentStage.SCREENING and all_pair_feedback:
        case_fb = tuple(
            _aggregate_case_feedback(
                all_pair_feedback,
                aggregation=case_aggregation_method,
                effect_metric=case_effect_metric,
                equivalence_band=protocol.config.case_equivalence_band,
            )
        )
        pattern = _build_pattern_summary(case_fb)

    problem_mechanism_evidence = problem_proposal_mechanism_evidence(
        stage=stage.value,
        selected_surface=normalized_selected_surface or selected_surface,
        runtime_pairs=problem_runtime_pairs,
        problem_spec=protocol._problem_spec,
        adapter=getattr(protocol, "_problem_adapter", None),
    )
    result = ProtocolResult(
        stage=stage,
        stats=stats,
        gate_outcome=gate.outcome,
        reason_codes=gate.reason_codes,
        exposed_summary=exposed,
        raw_metrics_ref=raw_ref,
        objective_semantics=objective_semantics,
        case_aggregation_method=case_aggregation_method,
        case_effect_metric=case_effect_metric,
        case_equivalence_band=protocol.config.case_equivalence_band,
        case_ids=tuple(cases),
        seed_set=tuple(seeds),
        pair_feedback=(
            tuple(all_pair_feedback) if stage == ExperimentStage.SCREENING else ()
        ),
        case_feedback=case_fb,
        pattern_summary=pattern,
        selected_surface=normalized_selected_surface or selected_surface,
        candidate_surface_runtime_summary=_surface_runtime_summary_with_diagnostics(
            candidate_surface_runtime_summary,
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
        runtime_model=runtime_model,
        mechanism_evidence=problem_mechanism_evidence,
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
        opportunity_status=opportunity_status_for_diagnostics(opportunity_diagnostics),
    )


def _append_elapsed_sample(samples: list[float], value: Any) -> bool:
    try:
        elapsed = float(value)
    except (TypeError, ValueError):
        return False
    if elapsed >= 0:
        samples.append(elapsed)
        return True
    return False


def _runtime_evidence_status(
    *,
    champion_cached_runtime_pairs: int,
    runtime_pairs: int,
    min_runtime_pairs: int,
) -> str:
    if champion_cached_runtime_pairs > 0 and runtime_pairs < min_runtime_pairs:
        return "insufficient"
    return "sufficient"


def _screening_evidence_status(
    *,
    stage: ExperimentStage,
    complete: bool,
    champion_failed_pairs: int,
) -> str:
    if not complete:
        return "in_progress"
    if stage == ExperimentStage.SCREENING and champion_failed_pairs > 0:
        return "partial_champion_evidence"
    return "complete"


def _screening_partial_champion_evidence(
    *,
    stage: ExperimentStage,
    total_pairs: int,
    valid_pairs: int,
    failed_pairs: int,
    champion_failed_pairs: int,
) -> dict[str, Any] | None:
    if stage != ExperimentStage.SCREENING or champion_failed_pairs <= 0:
        return None
    ratio = (
        float(champion_failed_pairs) / float(total_pairs) if total_pairs > 0 else 0.0
    )
    return {
        "reason_code": SCREENING_PARTIAL_CHAMPION_EVIDENCE,
        "total_pairs": total_pairs,
        "valid_pairs": valid_pairs,
        "failed_pairs": failed_pairs,
        "champion_failed_pairs": champion_failed_pairs,
        "champion_failed_pair_ratio": ratio,
        "decision_complete_evidence": False,
    }


def _paired_process_failure_category(
    champion_result: RunResult,
    candidate_result: RunResult,
) -> str:
    """Describe two failed, independently executed solver processes."""

    if (
        champion_result.error_category == "timeout"
        and candidate_result.error_category == "timeout"
    ):
        return "dual_runtime_failure"
    return "shared_process_failure"


__all__ = ["run_experiment"]
