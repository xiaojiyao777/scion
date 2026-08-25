"""Campaign summary projection for fresh V3 runs."""

from __future__ import annotations

import json
import logging
import math
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping

from scion.core.execution_outcome import ExecutionOutcome
from scion.core.models import (
    EvalStats,
    ExperimentStage,
    PairwiseCaseFeedback,
    ProtocolResult,
    StepRecord,
)
from scion.core.public_refs import (
    public_artifact_ref,
    public_case_ref,
    redact_public_refs,
)

from .artifact_refs import _screening_rate_fields
from .common import _stage_value

logger = logging.getLogger(__name__)

_REDACTED_PROPOSAL_STAGES = frozenset(
    {"proposal_hypothesis", "proposal_code"}
)
_PAIRED_EFFECT_CELLS_SCHEMA = "scion.paired_effect_cells.v1"
_PAIR_COMPARISONS = frozenset({"win", "loss", "tie"})
_METRIC_RELATIONS = frozenset({"candidate", "champion", "tie"})
_METRIC_NAME_RE = re.compile(r"[A-Za-z][A-Za-z0-9_.:-]{0,127}\Z")


def _finite_numeric(value: Any) -> bool:
    if type(value) not in {int, float}:
        return False
    try:
        return math.isfinite(float(value))
    except (OverflowError, TypeError, ValueError):
        return False


def _ordered_complete_pair_feedback(
    protocol_result: ProtocolResult,
) -> tuple[PairwiseCaseFeedback, ...] | None:
    if (
        type(protocol_result) is not ProtocolResult
        or protocol_result.stage is not ExperimentStage.SCREENING
        or type(protocol_result.stats) is not EvalStats
        or type(protocol_result.case_ids) is not tuple
        or type(protocol_result.seed_set) is not tuple
        or type(protocol_result.pair_feedback) is not tuple
        or not protocol_result.case_ids
        or not protocol_result.seed_set
        or not protocol_result.pair_feedback
    ):
        return None
    if any(
        type(case_id) is not str or not case_id.strip()
        for case_id in protocol_result.case_ids
    ):
        return None
    case_basenames = tuple(
        os.path.basename(case_id) for case_id in protocol_result.case_ids
    )
    if any(not basename for basename in case_basenames) or len(
        set(case_basenames)
    ) != len(case_basenames):
        return None
    seeds = protocol_result.seed_set
    if any(type(seed) is not int for seed in seeds) or len(set(seeds)) != len(seeds):
        return None
    expected_pairs = tuple(
        (case_id, seed) for case_id in case_basenames for seed in seeds
    )
    feedback = protocol_result.pair_feedback
    if len(feedback) != len(expected_pairs):
        return None
    for item, expected in zip(feedback, expected_pairs, strict=True):
        if (
            type(item) is not PairwiseCaseFeedback
            or type(item.case_id) is not str
            or type(item.seed) is not int
            or (item.case_id, item.seed) != expected
        ):
            return None
    return feedback


def _complete_pair_counts(
    stats: EvalStats,
    feedback: tuple[PairwiseCaseFeedback, ...],
    *,
    case_count: int,
) -> bool:
    count_fields = (
        stats.n_cases,
        stats.wins,
        stats.losses,
        stats.ties,
        stats.total_pairs,
        stats.attempted_pairs,
        stats.valid_pairs,
        stats.failed_pairs,
        stats.candidate_failed_pairs,
        stats.champion_failed_pairs,
        stats.shared_failed_pairs,
        stats.bilateral_failed_pairs,
        stats.pair_wins,
        stats.pair_losses,
        stats.pair_ties,
    )
    if any(type(value) is not int for value in count_fields):
        return False
    if min(stats.n_cases, stats.wins, stats.losses, stats.ties) < 0 or (
        stats.wins + stats.losses + stats.ties != stats.n_cases
    ):
        return False
    expected = len(feedback)
    if not (
        expected > 0
        and stats.n_cases == case_count
        and stats.total_pairs == stats.attempted_pairs == stats.valid_pairs == expected
        and stats.failed_pairs
        == stats.candidate_failed_pairs
        == stats.champion_failed_pairs
        == stats.shared_failed_pairs
        == stats.bilateral_failed_pairs
        == 0
    ):
        return False
    observed = (
        sum(item.comparison == "win" for item in feedback),
        sum(item.comparison == "loss" for item in feedback),
        sum(item.comparison == "tie" for item in feedback),
    )
    return observed == (stats.pair_wins, stats.pair_losses, stats.pair_ties)


def _metric_values_are_consistent(
    metric: Any,
) -> bool:
    if type(metric.name) is not str or _METRIC_NAME_RE.fullmatch(metric.name) is None:
        return False
    if not _finite_numeric(metric.candidate_value) or not _finite_numeric(
        metric.champion_value
    ):
        return False
    if (
        not _finite_numeric(metric.signed_delta)
        or type(metric.relation) is not str
        or metric.relation not in _METRIC_RELATIONS
        or type(metric.decisive) is not bool
    ):
        return False
    candidate_value = float(metric.candidate_value)
    reference_value = float(metric.champion_value)
    signed_delta = float(metric.signed_delta)
    if not math.isclose(
        abs(signed_delta),
        abs(candidate_value - reference_value),
    ):
        return False
    return not (
        (metric.relation == "candidate" and signed_delta <= 0.0)
        or (metric.relation == "champion" and signed_delta >= 0.0)
    )


def _objective_decisive_shape_is_consistent(
    comparison: Any,
    metrics: tuple[Any, ...],
) -> bool:
    if not _finite_numeric(comparison.scalar_delta):
        return False
    metric_names = tuple(metric.name for metric in metrics)
    if len(set(metric_names)) != len(metric_names):
        return False
    decisive = tuple(metric for metric in metrics if metric.decisive)
    if comparison.outcome == "tie":
        return comparison.decisive_metric is None and not decisive
    if (
        type(comparison.decisive_metric) is not str
        or _METRIC_NAME_RE.fullmatch(comparison.decisive_metric) is None
        or len(decisive) != 1
        or decisive[0].name != comparison.decisive_metric
    ):
        return False
    expected_relation = "candidate" if comparison.outcome == "win" else "champion"
    return decisive[0].relation == expected_relation


def _feedback_matches_objective(feedback: Any, comparison: Any) -> bool:
    if type(feedback.comparison) is not str:
        return False
    if feedback.comparison not in _PAIR_COMPARISONS:
        return False
    if type(comparison.outcome) is not str:
        return False
    if comparison.outcome != feedback.comparison:
        return False
    if not _finite_numeric(feedback.delta) or not _finite_numeric(
        comparison.scalar_delta
    ):
        return False
    return math.isclose(float(feedback.delta), float(comparison.scalar_delta))


def _paired_effect_cell(
    feedback: PairwiseCaseFeedback,
    *,
    metric_name: str,
) -> dict[str, int | float] | None:
    from scion.problem.objectives import MetricComparison, ObjectiveComparison

    comparison = feedback.objective_comparison
    if type(comparison) is not ObjectiveComparison:
        return None
    if not _feedback_matches_objective(feedback, comparison):
        return None
    metrics = comparison.metrics
    if type(metrics) is not tuple or any(
        type(metric) is not MetricComparison for metric in metrics
    ):
        return None
    if any(not _metric_values_are_consistent(metric) for metric in metrics):
        return None
    if not _objective_decisive_shape_is_consistent(comparison, metrics):
        return None
    matches = tuple(
        metric
        for metric in metrics
        if type(metric.name) is str and metric.name == metric_name
    )
    if len(matches) != 1:
        return None
    metric = matches[0]
    return {
        "candidate_value": metric.candidate_value,
        "reference_value": metric.champion_value,
    }


def _paired_effect_cells_payload(protocol_result: Any) -> dict[str, Any]:
    try:
        feedback = _ordered_complete_pair_feedback(protocol_result)
        if feedback is None or not _complete_pair_counts(
            protocol_result.stats,
            feedback,
            case_count=len(protocol_result.case_ids),
        ):
            return {}
        if (
            type(protocol_result.case_aggregation_method) is not str
            or protocol_result.case_aggregation_method != "paired_effect_median"
        ):
            return {}
        metric_name = protocol_result.case_effect_metric
        if (
            type(metric_name) is not str
            or metric_name != metric_name.strip()
            or _METRIC_NAME_RE.fullmatch(metric_name) is None
        ):
            return {}
        cells: list[dict[str, int | float]] = []
        for item in feedback:
            cell = _paired_effect_cell(item, metric_name=metric_name)
            if cell is None:
                return {}
            cells.append(cell)
        return {
            "schema_version": _PAIRED_EFFECT_CELLS_SCHEMA,
            "metric_name": metric_name,
            "cells": cells,
        }
    except Exception:  # noqa: BLE001 - summary projection must remain no-throw
        return {}


def _redacted_proposal_stage(step: StepRecord) -> str | None:
    record = getattr(step, "execution_outcome", None)
    if record is None or record.outcome is ExecutionOutcome.EVALUATED:
        return None
    failure_stage = step.failure_stage
    provenance_stage = record.provenance.get("stage")
    if (
        isinstance(failure_stage, str)
        and failure_stage in _REDACTED_PROPOSAL_STAGES
    ):
        return failure_stage
    if (
        isinstance(provenance_stage, str)
        and provenance_stage in _REDACTED_PROPOSAL_STAGES
    ):
        return provenance_stage
    return None


def _execution_outcome_projection(step: StepRecord) -> dict[str, Any] | None:
    record = getattr(step, "execution_outcome", None)
    if record is None:
        return None
    proposal_stage = _redacted_proposal_stage(step)
    if proposal_stage is not None:
        return {
            "outcome": record.outcome.value,
            "reason_code": record.reason_code,
            "detail": "",
            "provenance": {"stage": proposal_stage},
        }
    return record.to_primitive()


def _render_campaign_summary_json(summary: Mapping[str, Any]) -> str:
    if not isinstance(summary, Mapping):
        raise TypeError("campaign_summary.json payload must be a JSON object")
    rendered = json.dumps(summary, indent=2, default=str)
    decoder = json.JSONDecoder()
    decoded, end = decoder.raw_decode(rendered)
    if rendered[end:].strip():
        raise ValueError("campaign_summary.json rendered multiple JSON values")
    if not isinstance(decoded, dict):
        raise TypeError("campaign_summary.json top-level payload must be an object")
    return rendered + "\n"


def _write_text_atomically(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as tmp:
            tmp_path = tmp.name
            tmp.write(content)
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(tmp_path, path)
        tmp_path = None
    finally:
        if tmp_path is not None:
            try:
                os.unlink(tmp_path)
            except FileNotFoundError:
                pass


class CampaignSummaryMixin:
    def write_campaign_summary(
        self,
        *,
        state: Mapping[str, Any],
        run_result: Mapping[str, Any],
        step_history: Iterable[StepRecord],
        diagnostics: Any | None = None,
        final_evidence_refs: Mapping[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Write a research summary from one explicit operator-state snapshot."""

        steps = list(step_history)

        verification_failures: Dict[str, int] = {}
        action_locus_coverage: Dict[str, int] = {}
        family_coverage: Dict[str, int] = {}
        for step in steps:
            if step.failure_stage == "verification" and step.failure_detail:
                detail = step.failure_detail or ""
                code = (
                    detail.split(":", 1)[0].strip()
                    if ":" in detail
                    else detail.split()[0]
                    if detail
                    else "unknown"
                )
                verification_failures[code] = verification_failures.get(code, 0) + 1
            hypothesis = step.hypothesis
            if hypothesis is not None:
                locus = f"{hypothesis.action}/{hypothesis.change_locus}"
                action_locus_coverage[locus] = (
                    action_locus_coverage.get(locus, 0) + 1
                )

        try:
            from scion.proposal.mechanism_labels import extract_mechanism_label

            for step in steps:
                hypothesis = step.hypothesis
                if hypothesis is None:
                    continue
                label = extract_mechanism_label(
                    hypothesis.hypothesis_text or "",
                    taxonomy=self.family_taxonomy,
                    preferred_label=hypothesis.change_locus,
                )
                family_coverage[label] = family_coverage.get(label, 0) + 1
        except Exception as exc:  # pragma: no cover - observational best effort
            logger.debug("family coverage extraction failed: %s", exc)

        summary: Dict[str, Any] = dict(state)
        summary["run_result"] = dict(run_result)
        summary.update(
            {
                "verification_failure_breakdown": verification_failures,
                "action_locus_coverage": action_locus_coverage,
                "family_coverage": family_coverage,
                "diagnostics": diagnostics if diagnostics is not None else [],
                "steps": [],
            }
        )

        refs = dict(self.final_evidence_refs)
        if final_evidence_refs:
            refs.update(dict(final_evidence_refs))
        refs = redact_public_refs(refs, base_dir=self.campaign_dir)
        if refs:
            summary["final_evidence_refs"] = refs

        for step in steps:
            summary["steps"].append(self._build_summary_step(step))

        summary = redact_public_refs(summary, base_dir=self.campaign_dir)
        out_path = self.campaign_dir / "campaign_summary.json"
        try:
            _write_text_atomically(out_path, _render_campaign_summary_json(summary))
        except Exception as exc:  # pragma: no cover - observational best effort
            logger.warning("Failed to write campaign_summary.json: %s", exc)
        return summary

    def _build_summary_step(self, step: StepRecord) -> Dict[str, Any]:
        decision_reason_codes = list(step.decision_reason_codes or ())
        diagnostic_reason_codes = list(
            getattr(step, "diagnostic_reason_codes", ()) or ()
        )
        bypass_reason_codes = list(getattr(step, "bypass_reason_codes", ()) or ())
        execution_outcome = _execution_outcome_projection(step)
        proposal_stage = _redacted_proposal_stage(step)
        public_failure_detail = step.failure_detail
        if execution_outcome is not None and proposal_stage is not None:
            public_failure_detail = execution_outcome["reason_code"]
        public_failure_stage = proposal_stage or step.failure_stage
        hypothesis = step.hypothesis
        step_data: Dict[str, Any] = {
            "round": step.round_num,
            "branch_id": step.branch_id,
            "decision": step.decision.value if step.decision is not None else None,
            "decision_reason_codes": decision_reason_codes,
            "diagnostic_reason_codes": diagnostic_reason_codes,
            "bypass_reason_codes": bypass_reason_codes,
            "contract_passed": step.contract_passed,
            "contract_diagnostics": list(
                getattr(step, "contract_diagnostics", ()) or ()
            ),
            "verification_passed": step.verification_passed,
            "failure_stage": public_failure_stage,
            "failure_detail": public_failure_detail,
            "hypothesis": (
                {
                    "text": hypothesis.hypothesis_text or "",
                    "action": hypothesis.action,
                    "change_locus": hypothesis.change_locus,
                    "target_file": hypothesis.target_file,
                }
                if hypothesis is not None
                else None
            ),
        }
        if execution_outcome is not None:
            step_data["execution_outcome"] = execution_outcome
        canary_payload = _canary_result_payload(
            getattr(step, "canary_result", None),
            base_dir=self.campaign_dir,
        )
        if canary_payload:
            step_data["canary_result"] = canary_payload
        if step.protocol_result and step.protocol_result.stats:
            stats = step.protocol_result.stats
            pr = step.protocol_result
            protocol_reason_codes = list(pr.reason_codes)
            raw_metrics_ref = public_artifact_ref(
                pr.raw_metrics_ref,
                base_dir=self.campaign_dir,
                kind="metrics",
            )
            step_data["protocol_result"] = {
                "stage": pr.stage.value
                if hasattr(pr.stage, "value")
                else str(pr.stage),
                "win_rate": stats.win_rate,
                "median_delta": stats.median_delta,
                "ci_low": stats.ci_low,
                "ci_high": stats.ci_high,
                "statistical_status": stats.statistical_status,
                "statistical_metric": stats.statistical_metric,
                "metric_stats": [
                    {
                        "metric_name": m.metric_name,
                        "median_delta": m.median_delta,
                        "ci_low": m.ci_low,
                        "ci_high": m.ci_high,
                        "n_cases": m.n_cases,
                    }
                    for m in stats.metric_stats
                ],
                "runtime_ratio_median": stats.runtime_ratio_median,
                "runtime_delta_median_ms": stats.runtime_delta_median_ms,
                "runtime_regression_rate": stats.runtime_regression_rate,
                "runtime_pairs": stats.runtime_pairs,
                "runtime_confidence": pr.runtime_confidence,
                "runtime_model": pr.runtime_model,
                "runtime_evidence_status": stats.runtime_evidence_status,
                "total_pairs": stats.total_pairs,
                "attempted_pairs": stats.attempted_pairs,
                "valid_pairs": stats.valid_pairs,
                "failed_pairs": stats.failed_pairs,
                "candidate_failed_pairs": stats.candidate_failed_pairs,
                "champion_failed_pairs": stats.champion_failed_pairs,
                "shared_failed_pairs": stats.shared_failed_pairs,
                "bilateral_failed_pairs": stats.bilateral_failed_pairs,
                "gate_outcome": pr.gate_outcome,
                "reason_codes": protocol_reason_codes,
                "decision_reason_codes": decision_reason_codes,
                "diagnostic_reason_codes": diagnostic_reason_codes,
                "bypass_reason_codes": bypass_reason_codes,
                "raw_metrics_ref": raw_metrics_ref,
                "case_ids": [
                    ref
                    for ref in (
                        public_case_ref(case, base_dir=self.campaign_dir)
                        for case in pr.case_ids
                    )
                    if ref is not None
                ],
                "seed_set": list(pr.seed_set),
                "case_aggregation": {
                    "method": str(
                        getattr(pr, "case_aggregation_method", "")
                        or "seed_vote_majority"
                    ),
                    "effect_metric": str(getattr(pr, "case_effect_metric", "") or ""),
                    "equivalence_band": float(
                        getattr(pr, "case_equivalence_band", 0.0) or 0.0
                    ),
                },
                "selected_surface": pr.selected_surface,
                "opportunity_status": pr.opportunity_status,
                "opportunity_diagnostics": list(pr.opportunity_diagnostics or ()),
                "mechanism_evidence": dict(pr.mechanism_evidence or {}),
                "candidate_surface_runtime_summary": dict(
                    pr.candidate_surface_runtime_summary or {}
                ),
                "candidate_phase_telemetry_summary": dict(
                    getattr(pr, "candidate_phase_telemetry_summary", {}) or {}
                ),
                "runtime_budget_diagnostic": _runtime_budget_diagnostic(pr),
                "candidate_runtime_failure_categories": dict(
                    pr.candidate_runtime_failure_categories or {}
                ),
                "candidate_first_runtime_failure": (
                    dict(pr.candidate_first_runtime_failure)
                    if pr.candidate_first_runtime_failure
                    else None
                ),
                "candidate_operator_attempts": pr.candidate_operator_attempts,
                "candidate_operator_accepted": pr.candidate_operator_accepted,
                "candidate_operator_errors": pr.candidate_operator_errors,
                "candidate_operator_invalid_outputs": (
                    pr.candidate_operator_invalid_outputs
                ),
                "candidate_policy_errors": pr.candidate_policy_errors,
                "candidate_construction_errors": pr.candidate_construction_errors,
                "candidate_portfolio_errors": pr.candidate_portfolio_errors,
                "candidate_runtime_stop_reasons": dict(
                    pr.candidate_runtime_stop_reasons or {}
                ),
            }
            candidate_infeasible_pairs = getattr(
                pr,
                "candidate_attributable_infeasible_pairs",
                None,
            )
            if (
                type(candidate_infeasible_pairs) is int
                and type(stats.attempted_pairs) is int
                and type(stats.total_pairs) is int
                and 0
                <= candidate_infeasible_pairs
                <= stats.attempted_pairs
                <= stats.total_pairs
            ):
                step_data["protocol_result"][
                    "candidate_attributable_infeasible_pairs"
                ] = candidate_infeasible_pairs
            paired_effect_cells = _paired_effect_cells_payload(pr)
            if paired_effect_cells:
                step_data["protocol_result"]["paired_effect_cells"] = (
                    paired_effect_cells
                )
            if _stage_value(pr.stage) == "screening":
                step_data["protocol_result"].pop("win_rate")
            step_data["protocol_result"].update(_screening_rate_fields(pr))
            if pr.case_feedback:
                step_data["case_feedback_summary"] = [
                    {
                        "case_id": cf.case_id,
                        "dominant_result": cf.dominant_result,
                        "seed_pattern": getattr(cf, "seed_pattern", "uniform"),
                        "decisive": cf.decisive_metric,
                        "median_deltas": dict(cf.median_deltas),
                    }
                    for cf in pr.case_feedback
                ]
        return step_data


def _canary_result_payload(
    canary_result: Any,
    *,
    base_dir: str | Path | None,
) -> dict[str, Any]:
    if canary_result is None:
        return {}
    details = getattr(canary_result, "details", None)
    payload: dict[str, Any] = {
        "passed": bool(getattr(canary_result, "passed", False)),
        "reason": getattr(canary_result, "reason", None),
    }
    failure_category = str(getattr(canary_result, "failure_category", "") or "")
    if failure_category:
        payload["failure_category"] = failure_category
    reason_codes = tuple(getattr(canary_result, "reason_codes", ()) or ())
    if reason_codes:
        payload["reason_codes"] = list(reason_codes)
    candidate_infeasible_pairs = getattr(
        canary_result,
        "candidate_attributable_infeasible_pairs",
        None,
    )
    passed = getattr(canary_result, "passed", None)
    if (
        type(candidate_infeasible_pairs) is int
        and candidate_infeasible_pairs in {0, 1}
        and (passed is False or (passed is True and candidate_infeasible_pairs == 0))
    ):
        payload["candidate_attributable_infeasible_pairs"] = candidate_infeasible_pairs
    if isinstance(details, Mapping) and details.get("raw_metrics_ref"):
        raw_metrics_ref = public_artifact_ref(
            details["raw_metrics_ref"],
            base_dir=base_dir,
            kind="metrics",
        )
        if raw_metrics_ref is not None:
            payload["raw_metrics_ref"] = raw_metrics_ref
    return redact_public_refs(payload, base_dir=base_dir)


def _runtime_budget_diagnostic(protocol_result: Any) -> dict[str, Any] | None:
    surface_summary = getattr(
        protocol_result, "candidate_surface_runtime_summary", None
    )
    if not isinstance(surface_summary, Mapping):
        return None
    diagnostic = surface_summary.get("runtime_budget_diagnostic")
    return dict(diagnostic) if isinstance(diagnostic, Mapping) else None
