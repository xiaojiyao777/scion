from __future__ import annotations

import json
import logging
import os
import uuid as _uuid_mod
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import replace
from typing import TYPE_CHECKING, Any

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
    normalize_surface_name,
    runtime_audit_failure_from_result,
    runtime_audit_issue_blocks_execution,
)

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
from .types import CaseLevelResult, PairedExecutionSpec
from .values import _increment_category

if TYPE_CHECKING:
    from .facade import ExperimentProtocol

logger = logging.getLogger(__name__)

SCREENING_PARTIAL_CHAMPION_EVIDENCE = "SCREENING_PARTIAL_CHAMPION_EVIDENCE"


def run_experiment(
    protocol: ExperimentProtocol,
    stage: ExperimentStage,
    candidate_ws: str,
    champion_ws: str,
    hypothesis_action: str,
    expand: bool = False,
    expand_round: int = 1,
    selected_surface: str | None = None,
    *,
    paired_execution: PairedExecutionSpec | None = None,
    proposal_subject: Mapping[str, Any] | None = None,
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
    if paired_execution is not None:
        _validate_paired_execution(paired_execution, cases, seeds)
    total_pairs = len(cases) * len(seeds)
    attempted_pairs = 0
    valid_pairs = 0

    # Protocol construction is side-effect free so a campaign can enforce its
    # fresh-output boundary before installing services. Direct protocol users
    # still receive a metrics directory when an experiment actually starts.
    os.makedirs(protocol.metrics_dir, exist_ok=True)
    raw_ref = os.path.join(protocol.metrics_dir, f"{_uuid_mod.uuid4()}.json")

    # Collect pair feedback grouped by case
    pairs_by_case: dict[str, list[PairwiseCaseFeedback]] = defaultdict(list)
    raw_pairs: list[dict] = []
    raw_failures: list[dict] = []
    failed_pairs = 0
    candidate_failed_pairs = 0
    champion_failed_pairs = 0
    shared_failed_pairs = 0
    bilateral_failed_pairs = 0
    candidate_attributable_infeasible_pairs = 0
    candidate_only_timeout_pairs = 0
    candidate_only_invalid_output_pairs = 0
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
    problem_runtime_pairs: list[dict[str, Any]] = []
    runtime_evidence_status = "sufficient"
    protected_objective_regressions: tuple[str, ...] = ()
    runtime_model = getattr(
        protocol.config.runtime,
        "runtime_model",
        "comparative",
    )
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

    def _write_terminal_metrics(
        *,
        gate_outcome: str,
        reason_codes: tuple[str, ...],
    ) -> None:
        runtime_stats_snapshot = _build_runtime_stats(
            runtime_ratios,
            runtime_deltas_ms,
        )
        temporary_ref = f"{raw_ref}.tmp"
        try:
            with open(temporary_ref, "x", encoding="utf-8") as f:
                json.dump(
                    {
                    "stage": stage.value,
                    "gate_outcome": gate_outcome,
                    "reason_codes": list(reason_codes),
                    "selected_surface": normalized_selected_surface,
                    "objective_semantics": objective_semantics,
                    "runtime_model": runtime_model,
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
                    "shared_failed_pairs": shared_failed_pairs,
                    "bilateral_failed_pairs": bilateral_failed_pairs,
                    "candidate_attributable_infeasible_pairs": (
                        candidate_attributable_infeasible_pairs
                    ),
                    "candidate_only_timeout_pairs": candidate_only_timeout_pairs,
                    "candidate_only_invalid_output_pairs": (
                        candidate_only_invalid_output_pairs
                    ),
                    "screening_evidence_status": _screening_evidence_status(
                        stage=stage,
                        complete=True,
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
                    "runtime_confidence": "high",
                    "runtime_evidence_status": runtime_evidence_status,
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
                    "complete": True,
                    "pairs": raw_pairs,
                    "failures": raw_failures,
                    },
                    f,
                )
                f.flush()
                os.fsync(f.fileno())
            os.replace(temporary_ref, raw_ref)
        except BaseException:
            if os.path.lexists(temporary_ref):
                os.unlink(temporary_ref)
            raise

    def _progress(case=None, seed=None, **payload) -> None:
        payload.setdefault("phase", f"{stage.value}_protocol")
        payload.setdefault("complete", False)
        protocol._emit_progress(
            stage=stage.value, case=case, seed=seed,
            attempted_pairs=attempted_pairs, completed_pairs=valid_pairs,
            valid_pairs=valid_pairs, failed_pairs=failed_pairs,
            candidate_failed_pairs=candidate_failed_pairs,
            champion_failed_pairs=champion_failed_pairs,
            shared_failed_pairs=shared_failed_pairs,
            bilateral_failed_pairs=bilateral_failed_pairs,
            total_pairs=total_pairs,
            **payload,
        )

    def _record_candidate_observation(observation: dict[str, Any]) -> None:
        nonlocal candidate_first_runtime_failure
        _merge_runtime_observation(
            observation,
            categories=candidate_runtime_categories,
            counters=candidate_runtime_counters,
            stop_reasons=candidate_runtime_stop_reasons,
        )
        if (
            candidate_first_runtime_failure is None
            and observation.get("first_failure") is not None
        ):
            candidate_first_runtime_failure = observation["first_failure"]

    def _record_attributable_candidate_failure(
        *,
        attribution: Mapping[str, str],
        result: RunResult,
        audit: Mapping[str, Any] | None,
        observation: dict[str, Any],
    ) -> None:
        nonlocal candidate_first_runtime_failure
        _record_candidate_observation(observation)
        kind = attribution.get("candidate_failure_kind")
        if kind == "process":
            category = _candidate_process_failure_category(result)
            _increment_category(candidate_runtime_categories, category)
            if candidate_first_runtime_failure is None:
                candidate_first_runtime_failure = _runtime_failure_summary(
                    category=category,
                    code=str(
                        result.error_category or result.exit_code or "process_failure"
                    ),
                    surface=None,
                    component="solver_process",
                    detail_summary=(
                        result.stderr
                        or result.stdout
                        or "candidate solver process failed"
                    ),
                )
        elif kind == "missing_output":
            _increment_category(candidate_runtime_categories, "invalid_output")
            if candidate_first_runtime_failure is None:
                candidate_first_runtime_failure = _runtime_failure_summary(
                    category="invalid_output",
                    code="missing_output",
                    surface=None,
                    component="solver_output",
                    detail_summary="candidate solver succeeded without parsed output",
                )
        elif kind == "runtime_audit" and audit is not None:
            category = _candidate_audit_failure_category(audit)
            if category not in (observation.get("categories") or {}):
                _increment_category(candidate_runtime_categories, category)
            if candidate_first_runtime_failure is None:
                candidate_first_runtime_failure = _runtime_failure_summary_from_audit(
                    audit,
                    category=category,
                )

    _progress(
        None,
        None,
        child_pid=None,
        child_phase=None,
        child_exit_code=None,
        child_elapsed_ms=None,
    )

    for case in cases:
        case_features = _extract_case_features(
            case,
            adapter=getattr(protocol, "_problem_adapter", None),
        )
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
            _progress(case, seed, time_limit_sec=pair_time_limit_sec)
            cand_r: RunResult | None = None
            paired_raw: dict[str, Any] | None = None
            if paired_execution is not None:
                case_ordinal = paired_execution.case_ordinals[case]
                seed_ordinal = paired_execution.seed_ordinals[seed]
                parity = (paired_execution.candidate_ordinal
                          + paired_execution.block_ordinal
                          + case_ordinal + seed_ordinal) % 2
                order = ("A", "B") if parity == 0 else ("B", "A")
                results: dict[str, RunResult] = {}
                actual: list[str] = []

                def run_side(side: str, workspace: str, case_path: str,
                             _actual=actual, _results=results, _seed=seed, _limit=pair_time_limit_sec,
                             _case=case, _case_ordinal=case_ordinal, _seed_ordinal=seed_ordinal,
                             _order=order) -> RunResult:
                    _actual.append(side)
                    result = protocol.runner.run_solver(
                        workdir=workspace, instance_path=case_path, seed=_seed,
                        time_limit_sec=_limit,
                        registry_path=os.path.join(workspace, "registry.yaml"),
                        selected_surface=normalized_selected_surface,
                    )
                    _results[side] = result
                    return result

                if order[0] == "B":
                    cand_r = run_side("B", candidate_ws, candidate_case_path)
            champ_r = (
                run_side("A", champion_ws, champion_case_path)
                if paired_execution is not None
                else protocol.runner.run_solver(
                    workdir=champion_ws,
                    instance_path=champion_case_path,
                    seed=seed,
                    time_limit_sec=pair_time_limit_sec,
                    registry_path=os.path.join(champion_ws, "registry.yaml"),
                    selected_surface=normalized_selected_surface,
                )
            )
            if cand_r is None:
                if paired_execution is not None:
                    cand_r = run_side("B", candidate_ws, candidate_case_path)
                else:
                    cand_r = protocol.runner.run_solver(
                        workdir=candidate_ws,
                        instance_path=candidate_case_path,
                        seed=seed,
                        time_limit_sec=pair_time_limit_sec,
                        registry_path=os.path.join(candidate_ws, "registry.yaml"),
                        selected_surface=normalized_selected_surface,
                    )
            if paired_execution is not None:
                audits = {}
                for label, result in results.items():
                    issue = (runtime_audit_failure_from_result(
                        result, problem_spec=protocol._problem_spec,
                        selected_surface=normalized_selected_surface,
                    ) if result.success and result.output is not None else None)
                    audits[label] = issue if runtime_audit_issue_blocks_execution(issue) else None
                a_failure = _paired_failure(champ_r, audits["A"])
                b_failure = _paired_failure(cand_r, audits["B"])
                paired_raw = _paired_raw(
                    paired_execution, case_ordinal, seed_ordinal, order, actual, results,
                    pair_time_limit_sec, {"A": a_failure, "B": b_failure},
                )
                if a_failure or b_failure:
                    failed_pairs += 1
                    attribution = _paired_failure_attribution(
                        champion_result=champ_r,
                        candidate_result=cand_r,
                        champion_audit=audits["A"],
                        candidate_audit=audits["B"],
                    )
                    candidate_attributable_infeasible_pairs += int(
                        _is_candidate_attributable_infeasibility(attribution)
                    )
                    candidate_only_timeout_pairs += int(
                        _is_candidate_only_timeout(attribution, cand_r)
                    )
                    candidate_only_invalid_output_pairs += int(
                        _is_candidate_only_invalid_output(
                            attribution,
                            cand_r,
                            audits["B"],
                        )
                    )
                    side = attribution["side"]
                    if side == "candidate":
                        candidate_failed_pairs += 1
                    elif side == "champion":
                        champion_failed_pairs += 1
                    elif attribution["attribution"] == "shared":
                        # Shared evidence invalidates the comparison/reference
                        # without becoming a candidate-attributable failure.
                        champion_failed_pairs += 1
                        shared_failed_pairs += 1
                    else:
                        candidate_failed_pairs += 1
                        champion_failed_pairs += 1
                        bilateral_failed_pairs += 1
                    failure_record = {
                        "case": case, "seed": seed, "side": side,
                        "comparison": "invalid",
                        "failure_attribution": attribution["attribution"],
                        "error_category": attribution["error_category"],
                        "champion_error_category": a_failure,
                        "candidate_error_category": b_failure,
                        **(
                            {"champion_runtime_audit": audits["A"]}
                            if audits["A"] is not None
                            else {}
                        ),
                        **(
                            {"candidate_runtime_audit": audits["B"]}
                            if audits["B"] is not None
                            else {}
                        ),
                    }
                    raw_failures.append(failure_record)
                    raw_pairs.append({
                        "case": case, "seed": seed, "comparison": "invalid",
                        "delta": None, "decisive_metric": "paired_execution_failure",
                        "metric_deltas": {}, "paired_execution": paired_raw,
                        "failure": failure_record,
                    })
                    _progress(case, seed)
                    continue
            if _append_elapsed_sample(champion_elapsed_samples_ms, champ_r.elapsed_ms):
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

            champ_audit_failure = None
            if (
                paired_execution is None
                and champ_r.success
                and champ_r.output is not None
            ):
                # Candidate surface contracts are not imposed on the current
                # champion.  Generic runtime errors remain audited on both
                # sides and are compared by their common failure signature.
                champ_audit_issue = runtime_audit_failure_from_result(champ_r)
                champ_audit_failure = (
                    champ_audit_issue
                    if runtime_audit_issue_blocks_execution(champ_audit_issue)
                    else None
                )
            cand_audit_failure = None
            if (
                paired_execution is None
                and cand_r.success
                and cand_r.output is not None
            ):
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

            infeasibility_attribution = _paired_failure_attribution(
                champion_result=champ_r,
                candidate_result=cand_r,
                champion_audit=champ_audit_failure,
                candidate_audit=cand_audit_failure,
            )
            candidate_attributable_infeasible_pairs += int(
                _is_candidate_attributable_infeasibility(
                    infeasibility_attribution
                )
            )
            failure_attribution = _paired_failure_attribution(
                champion_result=champ_r,
                candidate_result=cand_r,
                champion_audit=champ_audit_failure,
                candidate_audit=cand_audit_failure,
                include_infeasible=False,
            )
            candidate_only_timeout_pairs += int(
                _is_candidate_only_timeout(failure_attribution, cand_r)
            )
            candidate_only_invalid_output_pairs += int(
                _is_candidate_only_invalid_output(
                    failure_attribution,
                    cand_r,
                    cand_audit_failure,
                )
            )
            if failure_attribution is not None:
                failed_pairs += 1
                attribution = failure_attribution["attribution"]
                side = failure_attribution["side"]
                if side == "candidate":
                    candidate_failed_pairs += 1
                elif side == "champion":
                    champion_failed_pairs += 1
                elif attribution == "shared":
                    champion_failed_pairs += 1
                    shared_failed_pairs += 1
                else:
                    candidate_failed_pairs += 1
                    champion_failed_pairs += 1
                    bilateral_failed_pairs += 1

                if attribution in ("candidate", "bilateral"):
                    _record_attributable_candidate_failure(
                        attribution=failure_attribution,
                        result=cand_r,
                        audit=cand_audit_failure,
                        observation=runtime_observation,
                    )
                elif attribution == "champion":
                    _record_candidate_observation(runtime_observation)

                candidate_loss = (
                    side == "candidate"
                    and failure_attribution.get("candidate_failure_kind")
                    in ("process", "runtime_audit")
                )
                comparison = "loss" if candidate_loss else "invalid"
                delta = -1.0 if candidate_loss else None
                failure_record = {
                    "case": case,
                    "seed": seed,
                    "side": side,
                    "failure_attribution": attribution,
                    "comparison": comparison,
                    "delta": delta,
                    "error_category": failure_attribution["error_category"],
                    "champion_error_category": failure_attribution.get(
                        "champion_error_category"
                    ),
                    "candidate_error_category": failure_attribution.get(
                        "candidate_error_category"
                    ),
                    "exit_code": (
                        cand_r.exit_code if side == "candidate" else champ_r.exit_code
                    ),
                    "elapsed_ms": (
                        cand_r.elapsed_ms if side == "candidate" else champ_r.elapsed_ms
                    ),
                    "champion_exit_code": champ_r.exit_code,
                    "candidate_exit_code": cand_r.exit_code,
                    **pair_budget_fields,
                    **runtime_fields,
                    "champion_stderr": champ_r.stderr or "",
                    "candidate_stderr": cand_r.stderr or "",
                    "stderr": (
                        cand_r.stderr or ""
                        if side == "candidate"
                        else champ_r.stderr or ""
                    ),
                    **(
                        {"runtime_audit": cand_audit_failure}
                        if side == "candidate" and cand_audit_failure is not None
                        else {}
                    ),
                    **(
                        {"runtime_audit": champ_audit_failure}
                        if side == "champion" and champ_audit_failure is not None
                        else {}
                    ),
                    **(
                        {"champion_runtime_audit": champ_audit_failure}
                        if champ_audit_failure is not None and side == "both"
                        else {}
                    ),
                    **(
                        {"candidate_runtime_audit": cand_audit_failure}
                        if cand_audit_failure is not None and side == "both"
                        else {}
                    ),
                }
                raw_failures.append(failure_record)
                decisive_metric = failure_attribution["error_category"]
                if candidate_loss and (
                    failure_attribution.get("candidate_failure_kind") == "process"
                ):
                    decisive_metric = "runtime_failure"
                elif side == "champion":
                    decisive_metric = f"champion_{decisive_metric}"
                raw_pairs.append(
                    {
                        "case": case,
                        "seed": seed,
                        "comparison": comparison,
                        "delta": delta,
                        "decisive_metric": decisive_metric,
                        "metric_deltas": {},
                        **pair_budget_fields,
                        **runtime_fields,
                        "failure": failure_record,
                    }
                )
                if candidate_loss:
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
                    "Pair %s seed=%d: execution failure side=%s "
                    "attribution=%s category=%s",
                    os.path.basename(case),
                    seed,
                    side,
                    attribution,
                    failure_attribution["error_category"],
                )
                _progress(case, seed)
                continue

            _record_candidate_observation(runtime_observation)
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
                    **({"paired_execution": paired_raw} if paired_raw else {}),
                }
            )
            problem_runtime_pairs.append(
                {
                    "candidate_runtime": dict(cand_r.output.runtime),
                    "champion_runtime": dict(champ_r.output.runtime),
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
            _progress(case, seed)

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
            allow_empty_metric_evidence=(
                valid_pairs == 0
                and bool(case_level_results)
                and all(not row.metric_deltas for row in case_level_results)
            ),
        )

    protected_objective_regressions = _protected_objective_regressions(
        all_pair_feedback,
        protocol.config.protected_objectives,
    )

    runtime_stats = _build_runtime_stats(runtime_ratios, runtime_deltas_ms)
    stats = replace(
        stats,
        runtime_ratio_median=runtime_stats["runtime_ratio_median"],
        runtime_delta_median_ms=runtime_stats["runtime_delta_median_ms"],
        runtime_regression_rate=runtime_stats["runtime_regression_rate"],
        runtime_pairs=runtime_stats["runtime_pairs"],
        runtime_evidence_status=runtime_evidence_status,
        total_pairs=total_pairs,
        attempted_pairs=attempted_pairs,
        valid_pairs=valid_pairs,
        failed_pairs=failed_pairs,
        candidate_failed_pairs=candidate_failed_pairs,
        champion_failed_pairs=champion_failed_pairs,
        shared_failed_pairs=shared_failed_pairs,
        bilateral_failed_pairs=bilateral_failed_pairs,
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

        if failed_pairs > 0 and stage in (
            ExperimentStage.VALIDATION,
            ExperimentStage.FROZEN,
        ):
            reason_codes = ["INCOMPLETE_EVIDENCE"]
            if candidate_failed_pairs > bilateral_failed_pairs:
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
    runtime_confidence = "high"
    _write_terminal_metrics(
        gate_outcome=gate.outcome,
        reason_codes=gate.reason_codes,
    )
    protocol._emit_progress(
        stage=stage.value,
        complete=True,
        gate_outcome=gate.outcome,
        reason_codes=list(gate.reason_codes),
        attempted_pairs=attempted_pairs,
        completed_pairs=valid_pairs,
        valid_pairs=valid_pairs,
        failed_pairs=failed_pairs,
        candidate_failed_pairs=candidate_failed_pairs,
        champion_failed_pairs=champion_failed_pairs,
        shared_failed_pairs=shared_failed_pairs,
        bilateral_failed_pairs=bilateral_failed_pairs,
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
        runtime_model=runtime_model,
        runtime_ratio_median=stats.runtime_ratio_median,
        runtime_delta_median_ms=stats.runtime_delta_median_ms,
        runtime_regression_rate=stats.runtime_regression_rate,
        runtime_pairs=stats.runtime_pairs,
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
    runtime_evidence_summary = (
        f" runtime_confidence={runtime_confidence}"
        f" runtime_evidence_status={runtime_evidence_status}"
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
            f"shared_failures={shared_failed_pairs} "
            f"bilateral_failures={bilateral_failed_pairs} "
            f"screening_evidence_status={_screening_evidence_status(stage=stage, complete=True, champion_failed_pairs=champion_failed_pairs)} "
            f"reason_codes={','.join(gate.reason_codes) or 'none'} "
            f"{runtime_summary}{runtime_failure_summary}{runtime_attempt_summary}"
            f"{phase_telemetry_summary}"
            f"{runtime_budget_summary}"
            f"{runtime_evidence_summary}"
        )
    else:
        # Validation / Frozen: aggregate summary only, no per-case data
        exposed = (
            f"stage={stage.value} outcome={gate.outcome} "
            f"stat={stats.statistical_status or 'legacy'} "
            f"metric={stats.statistical_metric or 'scalar'} "
            f"objective_semantics={objective_semantics} "
            f"valid_pairs={valid_pairs}/{total_pairs} failed_pairs={failed_pairs} "
            f"candidate_failures={candidate_failed_pairs} "
            f"champion_failures={champion_failed_pairs} "
            f"shared_failures={shared_failed_pairs} "
            f"bilateral_failures={bilateral_failed_pairs} "
            f"{runtime_summary}{runtime_failure_summary}{runtime_attempt_summary}"
            f"{phase_telemetry_summary}"
            f"{runtime_budget_summary}"
            f"{runtime_evidence_summary}"
        )

    # Build case-level feedback for screening only
    case_fb: tuple = ()
    pattern: ScreeningPatternSummary | None = None
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
        proposal_subject=proposal_subject,
        runtime_pairs_complete=(failed_pairs == 0),
        problem_spec=(
            protocol._problem_spec
            if getattr(protocol, "_problem_adapter", None) is None
            else None
        ),
        adapter=getattr(protocol, "_problem_adapter", None),
    )
    pair_level_safety_counts = {
        "candidate_attributable_infeasible_pairs": (
            candidate_attributable_infeasible_pairs
        ),
        "candidate_only_timeout_pairs": candidate_only_timeout_pairs,
        "candidate_only_invalid_output_pairs": (
            candidate_only_invalid_output_pairs
        ),
    }
    for field_name, count in pair_level_safety_counts.items():
        if type(count) is not int or not 0 <= count <= attempted_pairs:
            raise ValueError(
                f"{field_name} must be between zero and attempted_pairs"
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
        runtime_confidence=runtime_confidence,
        runtime_model=runtime_model,
        mechanism_evidence=problem_mechanism_evidence,
        candidate_attributable_infeasible_pairs=(
            candidate_attributable_infeasible_pairs
        ),
        candidate_only_timeout_pairs=candidate_only_timeout_pairs,
        candidate_only_invalid_output_pairs=(
            candidate_only_invalid_output_pairs
        ),
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


def _validate_paired_execution(spec: PairedExecutionSpec,
                               cases: list[str], seeds: list[int]) -> None:
    fixed = [("candidate_ordinal", spec.candidate_ordinal), ("block_ordinal", spec.block_ordinal)]
    case_values = ((f"case_ordinals[{key!r}]", spec.case_ordinals.get(key)) for key in cases)
    seed_values = ((f"seed_ordinals[{key!r}]", spec.seed_ordinals.get(key)) for key in seeds)
    for name, value in (*fixed, *case_values, *seed_values):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{name} must be a non-negative integer")
    for name, values in (("case", [spec.case_ordinals[key] for key in cases]),
                         ("seed", [spec.seed_ordinals[key] for key in seeds])):
        if len(values) != len(set(values)):
            raise ValueError(f"selected {name} ordinals must be unique")


def _paired_failure(
    result: RunResult,
    audit: Mapping[str, Any] | None,
    *,
    include_infeasible: bool = True,
) -> str | None:
    if not result.success:
        return result.error_category or "process_failure"
    if result.output is None:
        return "missing_output"
    if audit:
        return str(audit.get("error_category") or "runtime_audit_failure")
    if include_infeasible and not result.output.feasible:
        return "infeasible"
    return None


def _failure_kind(
    result: RunResult,
    audit: Mapping[str, Any] | None,
    *,
    include_infeasible: bool,
) -> str | None:
    if not result.success:
        return "process"
    if result.output is None:
        return "missing_output"
    if audit:
        return "runtime_audit"
    if include_infeasible and not result.output.feasible:
        return "infeasible"
    return None


def _paired_failure_attribution(
    *,
    champion_result: RunResult,
    candidate_result: RunResult,
    champion_audit: Mapping[str, Any] | None,
    candidate_audit: Mapping[str, Any] | None,
    include_infeasible: bool = True,
) -> dict[str, str] | None:
    """Classify pair-local execution failures without losing either side."""

    champion_failure = _paired_failure(
        champion_result,
        champion_audit,
        include_infeasible=include_infeasible,
    )
    candidate_failure = _paired_failure(
        candidate_result,
        candidate_audit,
        include_infeasible=include_infeasible,
    )
    champion_kind = _failure_kind(
        champion_result,
        champion_audit,
        include_infeasible=include_infeasible,
    )
    candidate_kind = _failure_kind(
        candidate_result,
        candidate_audit,
        include_infeasible=include_infeasible,
    )
    if champion_failure is None and candidate_failure is None:
        return None
    if champion_failure is None:
        return {
            "side": "candidate",
            "attribution": "candidate",
            "error_category": str(candidate_failure or "execution_failure"),
            "candidate_error_category": str(candidate_failure or "execution_failure"),
            "candidate_failure_kind": str(candidate_kind or "execution"),
        }
    if candidate_failure is None:
        return {
            "side": "champion",
            "attribution": "champion",
            "error_category": str(champion_failure),
            "champion_error_category": str(champion_failure),
            "champion_failure_kind": str(champion_kind or "execution"),
        }

    shared = _paired_failures_equivalent(
        champion_result=champion_result,
        candidate_result=candidate_result,
        champion_audit=champion_audit,
        candidate_audit=candidate_audit,
    )
    if champion_kind == candidate_kind == "runtime_audit":
        category = (
            "shared_runtime_audit_failure"
            if shared
            else "bilateral_runtime_audit_failure"
        )
    elif champion_kind == candidate_kind == "process":
        category = _paired_process_failure_category(
            champion_result,
            candidate_result,
        )
    elif champion_kind == candidate_kind:
        category = f"shared_{champion_kind}" if shared else f"bilateral_{champion_kind}"
    else:
        category = (
            "shared_execution_failure" if shared else "bilateral_execution_failure"
        )
    return {
        "side": "both",
        "attribution": "shared" if shared else "bilateral",
        "error_category": category,
        "champion_error_category": str(champion_failure),
        "candidate_error_category": str(candidate_failure),
        "champion_failure_kind": str(champion_kind or "execution"),
        "candidate_failure_kind": str(candidate_kind or "execution"),
    }


def _is_candidate_attributable_infeasibility(
    attribution: Mapping[str, str] | None,
) -> bool:
    return bool(
        attribution is not None
        and attribution.get("attribution") == "candidate"
        and attribution.get("candidate_failure_kind") == "infeasible"
    )


def _is_candidate_only_timeout(
    attribution: Mapping[str, str] | None,
    candidate_result: RunResult,
) -> bool:
    return bool(
        attribution is not None
        and attribution.get("attribution") == "candidate"
        and attribution.get("candidate_failure_kind") == "process"
        and _normalized_failure_category(candidate_result.error_category) == "timeout"
    )


def _is_candidate_only_invalid_output(
    attribution: Mapping[str, str] | None,
    candidate_result: RunResult,
    candidate_audit: Mapping[str, Any] | None,
) -> bool:
    if attribution is None or attribution.get("attribution") != "candidate":
        return False
    kind = attribution.get("candidate_failure_kind")
    if kind == "missing_output":
        return True
    if kind == "runtime_audit" and candidate_audit is not None:
        return (
            _candidate_audit_failure_category(dict(candidate_audit))
            == "invalid_output"
        )
    return bool(
        kind == "process"
        and _normalized_failure_category(candidate_result.error_category)
        == "invalid_output"
    )


def _normalized_failure_category(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_")


def _paired_failures_equivalent(
    *,
    champion_result: RunResult,
    candidate_result: RunResult,
    champion_audit: Mapping[str, Any] | None,
    candidate_audit: Mapping[str, Any] | None,
) -> bool:
    if champion_audit is not None or candidate_audit is not None:
        return _runtime_audit_failures_equivalent(
            champion_audit,
            candidate_audit,
        )
    if not champion_result.success or not candidate_result.success:
        return _process_failures_equivalent(champion_result, candidate_result)
    if champion_result.output is None or candidate_result.output is None:
        return champion_result.output is None and candidate_result.output is None
    return (
        bool(champion_result.output.feasible)
        == bool(candidate_result.output.feasible)
    )


def _runtime_audit_failures_equivalent(
    champion_failure: Mapping[str, Any] | None,
    candidate_failure: Mapping[str, Any] | None,
) -> bool:
    if champion_failure is None or candidate_failure is None:
        return False
    # Candidate surface-aware audit and generic champion audit describe the
    # same runtime incident with two structural extras.  Remove only those
    # view-specific fields; every substantive diagnostic must still match.
    view_specific_fields = frozenset(
        {"selected_surface", "runtime_error_counts"}
    )
    champion_signature = {
        field: value
        for field, value in champion_failure.items()
        if field not in view_specific_fields
    }
    candidate_signature = {
        field: value
        for field, value in candidate_failure.items()
        if field not in view_specific_fields
    }
    return bool(champion_signature) and champion_signature == candidate_signature


def _process_failures_equivalent(
    champion_result: RunResult,
    candidate_result: RunResult,
) -> bool:
    if champion_result.success or candidate_result.success:
        return False
    return (
        champion_result.error_category == candidate_result.error_category
        and champion_result.exit_code == candidate_result.exit_code
        and (champion_result.stderr or "") == (candidate_result.stderr or "")
        and (champion_result.stdout or "") == (candidate_result.stdout or "")
    )


def _paired_raw(spec, case_ordinal, seed_ordinal, order, actual, results,
                time_limit_sec, failures=None) -> dict[str, Any]:
    failures = failures or {}
    def side(label):
        result = results.get(label)
        if result is None:
            return None
        output = result.output
        failure = failures.get(label) or result.error_category
        return {"objective": dict(result.output.objective) if result.output else None,
                "success": bool(result.success),
                "feasible": bool(output.feasible) if output else None,
                "elapsed_ms": result.elapsed_ms, "time_limit_sec": time_limit_sec,
                "exit_code": result.exit_code,
                "failure": str(failure)[:128] if failure else None}
    return {"block_ordinal": spec.block_ordinal, "case_ordinal": case_ordinal,
            "seed_ordinal": seed_ordinal,
            "scheduled_order": "".join(order), "actual_order": "".join(actual),
            "A": side("A"), "B": side("B")}


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

    if not _process_failures_equivalent(champion_result, candidate_result):
        return "bilateral_process_failure"
    if (
        champion_result.error_category == "timeout"
        and candidate_result.error_category == "timeout"
    ):
        return "dual_runtime_failure"
    return "shared_process_failure"


__all__ = ["run_experiment"]
