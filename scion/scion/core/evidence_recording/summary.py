"""Campaign summary projection for fresh V3 runs."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping

from scion.core.execution_outcome import ExecutionOutcome
from scion.core.models import StepRecord
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
