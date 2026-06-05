"""Campaign summary builder for evidence recording."""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Iterable, Mapping

from scion.core.branch_cards import (
    active_slot_inventory_from_branch_cards,
    branch_prompt_card_from_context,
)
from scion.core.models import ChampionState, StepRecord
from scion.core.public_refs import public_artifact_ref, public_case_ref, redact_public_refs
from scion.core.research_process_guidance_audit import (
    extract_research_process_guidance_audit,
)
from scion.core.reason_code_groups import classify_reason_codes
from scion.core.run_validity import build_run_validity, step_failure_categories
from scion.core.screening_visibility import (
    mechanism_evidence_for_protocol,
    runtime_aggregate_exclusion_for_protocol,
    runtime_evidence_policy_for_protocol,
)
from scion.core.status_reporter import (
    API_BALANCE_EXHAUSTED_STOP_REASON,
    PROVIDER_ERROR_CATEGORY_BALANCE_EXHAUSTED,
    is_provider_balance_exhausted_detail,
    normalize_stopped_reason,
)
from scion.core.telemetry_validation import (
    formal_telemetry_guard_failed,
    formal_screening_attempted,
    screened_experiment_effective,
    telemetry_decision_details,
    telemetry_effect_zero_diagnostics,
    telemetry_failure_categories,
    telemetry_validation_feedback,
)
from scion.evidence.formal_readiness import validate_formal_readiness

from .artifact_refs import _screening_rate_fields
from .accounting import (
    accounting_reconciliation_fields,
    proposal_accounting_fields,
)
from .common import _stage_value
from .cross_branch_observability import build_cross_branch_research_observability
from .failure_summary import (
    _contract_not_run_reason,
    _default_final_evidence_closure_refs,
    _primary_failure_attribution,
    _secondary_failure_observations,
)
from .telemetry_summary import (
    _telemetry_failed_experiment_category_counts,
    _telemetry_failed_experiment_details,
)

logger = logging.getLogger(__name__)


class CampaignSummaryMixin:
    def write_campaign_summary(
        self,
        *,
        step_history: Iterable[StepRecord],
        round_num: int,
        champion: ChampionState,
        budget_used: float = 0.0,
        budget_total: float = 0.0,
        stopped_reason: str | None = None,
        balance_exhausted: bool = False,
        circuit_breaker_tripped: bool = False,
        stagnation_signals: Iterable[Any] = (),
        diagnostics: Any | None = None,
        final_evidence_refs: Mapping[str, Any] | None = None,
        frozen_budget: Mapping[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Write ``campaign_summary.json`` with the current backward-compatible schema."""
        steps = list(step_history)
        cache_stats = _campaign_cache_stats(
            steps,
            campaign_dir=self.campaign_dir,
        )

        vfail_counter: Dict[str, int] = {}
        for step in steps:
            if step.failure_stage == "verification" and step.failure_detail:
                fd = step.failure_detail or ""
                vcode = (
                    fd.split(":")[0].strip()
                    if ":" in fd
                    else fd.split()[0] if fd else "unknown"
                )
                vfail_counter[vcode] = vfail_counter.get(vcode, 0) + 1

        action_locus_counter: Dict[str, int] = {}
        for step in steps:
            key = f"{step.hypothesis.action}/{step.hypothesis.change_locus}"
            action_locus_counter[key] = action_locus_counter.get(key, 0) + 1

        family_counter: Dict[str, int] = {}
        try:
            from scion.proposal.context_manager import _extract_mechanism_label

            for step in steps:
                label = _extract_mechanism_label(
                    step.hypothesis.hypothesis_text or "",
                    taxonomy=self.family_taxonomy,
                    preferred_label=step.hypothesis.change_locus,
                )
                family_counter[label] = family_counter.get(label, 0) + 1
        except Exception as exc:  # pragma: no cover - defensive parity with artifact writing
            logger.debug("family coverage extraction failed: %s", exc)

        budget_utilization = (
            round(budget_used / budget_total, 4) if budget_total > 0 else 0.0
        )
        inferred_balance_exhausted = balance_exhausted or any(
            is_provider_balance_exhausted_detail(step.failure_detail)
            or is_provider_balance_exhausted_detail(step.verification_detail)
            for step in steps
        )
        effective_stopped_reason = normalize_stopped_reason(
            stopped_reason,
            balance_exhausted=inferred_balance_exhausted,
            circuit_breaker_tripped=circuit_breaker_tripped,
        )
        telemetry_failed_experiments = sum(
            1
            for step in steps
            if formal_telemetry_guard_failed(step.protocol_result)
        )
        telemetry_failed_experiments_by_category = (
            _telemetry_failed_experiment_category_counts(
                step.protocol_result for step in steps
            )
        )
        telemetry_failure_details = _telemetry_failed_experiment_details(steps)
        telemetry_effect_zero_details = _telemetry_effect_zero_details(steps)
        runtime_budget_diagnostics = _runtime_budget_diagnostic_details(steps)
        screened_experiments = sum(
            1 for step in steps if formal_screening_attempted(step.protocol_result)
        )
        counted_experiment_steps = sum(
            1 for step in steps if screened_experiment_effective(step.protocol_result)
        )
        effective_rounds_completed = counted_experiment_steps
        state_screened_experiments: Any | None = None
        if self.state_provider is not None:
            try:
                state_for_counts = dict(self.state_provider())
                state_screened_experiments = state_for_counts.get(
                    "screened_experiments"
                )
                state_telemetry_failed = state_for_counts.get(
                    "telemetry_failed_experiments"
                )
                if state_telemetry_failed is not None:
                    telemetry_failed_experiments = max(
                        telemetry_failed_experiments,
                        int(state_telemetry_failed),
                    )
                state_category_counts = state_for_counts.get(
                    "telemetry_failed_experiments_by_category"
                )
                if isinstance(state_category_counts, Mapping):
                    for key, value in state_category_counts.items():
                        try:
                            telemetry_failed_experiments_by_category[str(key)] = max(
                                telemetry_failed_experiments_by_category.get(
                                    str(key),
                                    0,
                                ),
                                int(value),
                            )
                        except (TypeError, ValueError):
                            continue
                state_telemetry_details = state_for_counts.get(
                    "telemetry_failure_details"
                )
                if (
                    not telemetry_failure_details
                    and isinstance(state_telemetry_details, list)
                ):
                    telemetry_failure_details = [
                        dict(item)
                        for item in state_telemetry_details
                        if isinstance(item, Mapping)
                    ]
            except Exception as exc:  # pragma: no cover - summary is best-effort
                logger.debug("state snapshot for campaign_summary counts failed: %s", exc)
        if state_screened_experiments is not None:
            screened_experiments = int(state_screened_experiments)
        loop_status = getattr(self, "campaign_loop_status", None)
        loop_proposal_attempts = None
        loop_total_rounds = None
        loop_campaign_steps = None
        loop_telemetry_repair_attempts = None
        loop_telemetry_repair_counts = None
        if isinstance(loop_status, Mapping):
            loop_proposal_attempts = loop_status.get("proposal_attempts_consumed")
            loop_total_rounds = loop_status.get("total_rounds")
            loop_campaign_steps = loop_status.get("campaign_steps")
            if loop_campaign_steps is None:
                loop_campaign_steps = loop_status.get("loop_steps")
            loop_effective_rounds = loop_status.get("effective_rounds_completed")
            loop_telemetry_repair_attempts = loop_status.get(
                "telemetry_repair_attempts"
            )
            loop_telemetry_repair_counts = loop_status.get(
                "telemetry_repair_attempts_by_branch_mechanism"
            )
            if loop_effective_rounds is not None:
                effective_rounds_completed = int(loop_effective_rounds)
        failure_categories = step_failure_categories(steps)
        if isinstance(loop_status, Mapping):
            loop_failure_categories = loop_status.get("failure_categories")
            if isinstance(loop_failure_categories, Mapping):
                for key, value in loop_failure_categories.items():
                    try:
                        failure_categories[str(key)] = max(
                            failure_categories.get(str(key), 0),
                            int(value),
                        )
                    except (TypeError, ValueError):
                        continue

        summary: Dict[str, Any] = {
            "campaign_id": self.campaign_id,
            "total_rounds": (
                int(loop_total_rounds)
                if loop_total_rounds is not None
                else round_num
            ),
            "proposal_attempts": (
                int(loop_proposal_attempts)
                if loop_proposal_attempts is not None
                else round_num
            ),
            "proposal_attempts_consumed": (
                int(loop_proposal_attempts)
                if loop_proposal_attempts is not None
                else round_num
            ),
            "campaign_steps": (
                int(loop_campaign_steps)
                if loop_campaign_steps is not None
                else len(steps)
            ),
            "screened_rounds": screened_experiments,
            "effective_rounds_completed": effective_rounds_completed,
            "counted_experiment_steps": counted_experiment_steps,
            "telemetry_repair_attempts": (
                int(loop_telemetry_repair_attempts)
                if loop_telemetry_repair_attempts is not None
                else sum(
                    1
                    for step in steps
                    if str(getattr(step, "attempt_kind", ""))
                    in {
                        "telemetry_repair",
                        "telemetry_repairable",
                        "validation_repair_required",
                    }
                )
            ),
            "telemetry_repair_attempts_by_branch_mechanism": (
                dict(loop_telemetry_repair_counts)
                if isinstance(loop_telemetry_repair_counts, Mapping)
                else {}
            ),
            "screened_experiments": screened_experiments,
            "telemetry_failed_experiments": telemetry_failed_experiments,
            "telemetry_failed_experiments_by_category": (
                telemetry_failed_experiments_by_category
            ),
            "telemetry_failure_details": telemetry_failure_details,
            "telemetry_effect_zero_diagnostics": telemetry_effect_zero_details,
            "runtime_budget_diagnostics": runtime_budget_diagnostics,
            "runtime_budget_diagnostic_count": len(runtime_budget_diagnostics),
            "champion_version": champion.version,
            "champion_weight_revision": getattr(champion, "weight_revision", 0),
            "stopped_reason": effective_stopped_reason,
            "stopped": effective_stopped_reason not in (None, "run_complete"),
            "balance_exhausted": inferred_balance_exhausted,
            "circuit_breaker_tripped": circuit_breaker_tripped,
            "cache_stats": {
                "total_tokens": cache_stats["total_tokens"],
                "cache_read_tokens": cache_stats["cache_read_tokens"],
                "cache_create_tokens": cache_stats["cache_create_tokens"],
                "cache_hit_rate": cache_stats["cache_hit_rate"],
                **(
                    {"output_tokens": cache_stats["output_tokens"]}
                    if cache_stats.get("output_tokens")
                    else {}
                ),
                **(
                    {"calls": cache_stats["calls"]}
                    if cache_stats.get("calls")
                    else {}
                ),
                "source": cache_stats["source"],
                **(
                    {
                        "repeated_cache_create_groups": cache_stats[
                            "repeated_cache_create_groups"
                        ]
                    }
                    if cache_stats.get("repeated_cache_create_groups")
                    else {}
                ),
            },
            "verification_failure_breakdown": vfail_counter,
            "action_locus_coverage": action_locus_counter,
            "family_coverage": family_counter,
            "budget_utilization": budget_utilization,
            "stagnation_signals": [
                {
                    "kind": s.kind,
                    "severity": s.severity,
                    "detail": s.detail,
                    "suggested_action": s.suggested_action,
                }
                for s in stagnation_signals
            ],
            "diagnostics": diagnostics if diagnostics is not None else [],
            "steps": [],
        }
        state_n_experiments: Any | None = None
        if self.state_provider is not None:
            try:
                state_for_validity = dict(self.state_provider())
                state_n_experiments = state_for_validity.get("n_experiments")
            except Exception as exc:  # pragma: no cover - summary is best-effort
                logger.debug("state snapshot for run validity failed: %s", exc)
        summary["failure_categories"] = failure_categories
        summary["run_validity"] = build_run_validity(
            requested_rounds=(
                self.campaign_loop_status.get("requested_rounds")
                if isinstance(self.campaign_loop_status, Mapping)
                else None
            ),
            effective_rounds_completed=effective_rounds_completed,
            n_experiments=(
                state_n_experiments
                if state_n_experiments is not None
                else screened_experiments
            ),
            proposal_attempts=summary["proposal_attempts_consumed"],
            stopped_reason=effective_stopped_reason,
            failure_categories=failure_categories,
            stopped=True,
        )
        summary["run_validity_status"] = summary["run_validity"]["reason"]
        if effective_stopped_reason == API_BALANCE_EXHAUSTED_STOP_REASON:
            summary["stop_category"] = "provider_error"
            summary["provider_error"] = {
                "category": PROVIDER_ERROR_CATEGORY_BALANCE_EXHAUSTED,
            }
        if frozen_budget is not None:
            summary["frozen_budget"] = dict(frozen_budget)
        if self.campaign_loop_status is not None:
            summary["campaign_loop"] = dict(self.campaign_loop_status)
            for key in (
                "requested_rounds",
                "effective_rounds_completed",
                "campaign_steps",
                "loop_steps",
                "telemetry_diagnostic_attempts",
                "branch_lifecycle_policy_blocks",
                "reconcile_lifecycle_steps",
                "non_counted_lifecycle_steps",
                "quality_blocks",
                "blocked_attempts",
            ):
                value = self.campaign_loop_status.get(key)
                if value is not None:
                    summary[key] = value
        accounting = proposal_accounting_fields(
            campaign_dir=self.campaign_dir,
            steps=steps,
            loop_status=self.campaign_loop_status,
            state=summary,
            round_num=round_num,
            screened_rounds=screened_experiments,
        )
        accounting_reconciliation = accounting_reconciliation_fields(
            steps=steps,
            loop_status=self.campaign_loop_status,
            state=summary,
            round_num=round_num,
            screened_rounds=screened_experiments,
            effective_rounds_completed=effective_rounds_completed,
            counted_experiment_steps=counted_experiment_steps,
            telemetry_failed_experiments=telemetry_failed_experiments,
        )
        summary.update(accounting)
        summary["accounting_reconciliation"] = accounting_reconciliation
        summary["proposal_accounting"] = {
            "proposal_attempts": summary.get("proposal_attempts"),
            "proposal_attempts_consumed": summary.get("proposal_attempts_consumed"),
            **accounting,
            "accounting_reconciliation": accounting_reconciliation,
        }
        refs = dict(self.final_evidence_refs)
        if final_evidence_refs:
            refs.update(dict(final_evidence_refs))
        if not refs:
            refs = _default_final_evidence_closure_refs(effective_stopped_reason)
        refs = redact_public_refs(refs, base_dir=self.campaign_dir)
        readiness = validate_formal_readiness(refs)
        summary["formal_readiness"] = {
            "formal_ready": readiness.formal_ready,
            "missing": list(readiness.missing),
            "status": readiness.status,
        }
        if readiness.reason_code:
            summary["formal_readiness"]["reason_code"] = readiness.reason_code
        if refs:
            summary["final_evidence_refs"] = refs
        if self.state_provider is not None:
            try:
                state = dict(self.state_provider())
                branch_rows = [dict(row) for row in (state.get("branches") or []) if isinstance(row, Mapping)]
                branch_cards = _branch_cards_from_rows(branch_rows)
                existing_active_slots = (
                    dict(state["active_slots"])
                    if isinstance(state.get("active_slots"), Mapping)
                    else {}
                )
                reconciled_active_slots = active_slot_inventory_from_branch_cards(
                    branch_cards,
                    max_active_branches=existing_active_slots.get("max"),
                )
                if reconciled_active_slots is not None:
                    summary["n_active_branches"] = reconciled_active_slots["used"]
                    summary["active_slots"] = reconciled_active_slots
                else:
                    summary["n_active_branches"] = state.get("n_active_branches")
                    if existing_active_slots:
                        summary["active_slots"] = existing_active_slots
                summary["branches"] = branch_rows
                summary["branch_cards"] = branch_cards
                summary["branch_history_cards"] = _branch_history_cards(steps, branch_cards)
                if isinstance(state.get("current_progress"), Mapping):
                    summary["current_progress"] = dict(state["current_progress"])
                if isinstance(state.get("checkpoint_inventory"), Mapping):
                    summary["checkpoint_inventory"] = dict(state["checkpoint_inventory"])
                summary["rollback_events"] = _rollback_events(steps, branch_cards)
            except Exception as exc:  # pragma: no cover - summary is best-effort
                logger.debug("state snapshot for campaign_summary failed: %s", exc)

        try:
            summary["cross_branch_research_observability"] = (
                build_cross_branch_research_observability(
                    steps=steps,
                    branch_rows=summary.get("branches") or (),
                )
            )
        except Exception as exc:  # pragma: no cover - observability is best-effort
            logger.debug("cross-branch observability summary failed: %s", exc)

        for step in steps:
            summary["steps"].append(self._build_summary_step(step))

        summary = redact_public_refs(summary, base_dir=self.campaign_dir)
        out_path = self.campaign_dir / "campaign_summary.json"
        try:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(
                json.dumps(summary, indent=2, default=str),
                encoding="utf-8",
            )
        except Exception as exc:  # pragma: no cover
            logger.warning("Failed to write campaign_summary.json: %s", exc)
        return summary

    def _build_summary_step(self, step: StepRecord) -> Dict[str, Any]:
        decision_reason_codes = list(step.decision_reason_codes or ())
        code_archive_ref = public_artifact_ref(
            step.code_archive_ref,
            base_dir=self.campaign_dir,
            kind="artifact",
        )
        contract_not_run_reason = _contract_not_run_reason(step)
        primary_failure = _primary_failure_attribution(step)
        secondary_observations = _secondary_failure_observations(
            step,
            primary_failure,
        )
        step_data: Dict[str, Any] = {
            "round": step.round_num,
            "branch_id": step.branch_id,
            "decision": step.decision.value if step.decision is not None else None,
            "decision_reason_codes": decision_reason_codes,
            "contract_passed": False if contract_not_run_reason else step.contract_passed,
            "verification_passed": step.verification_passed,
            "failure_stage": step.failure_stage,
            "failure_detail": step.failure_detail,
            "counts_toward_max_rounds": getattr(
                step,
                "counts_toward_max_rounds",
                True,
            ),
            "attempt_kind": getattr(step, "attempt_kind", "screening"),
            "scheduler_slot": getattr(step, "scheduler_slot", ""),
            "scheduler_reason": getattr(step, "scheduler_reason", ""),
            "scheduler_audit_metadata": dict(
                getattr(step, "scheduler_audit_metadata", {}) or {}
            ),
            "repair_policy_reason": getattr(step, "repair_policy_reason", None),
            "repair_mechanism_ids": list(
                getattr(step, "repair_mechanism_ids", ()) or ()
            ),
            "verification_detail": step.verification_detail,
            "code_archive_ref": code_archive_ref,
            "cache_stats": step.cache_stats,
            "hypothesis": {
                "text": (step.hypothesis.hypothesis_text or "")[:200],
                "action": step.hypothesis.action,
                "change_locus": step.hypothesis.change_locus,
                "target_file": step.hypothesis.target_file,
            },
            "screened_experiment": step.protocol_result is not None,
            "screened_experiment_effective": screened_experiment_effective(
                step.protocol_result
            ),
            "telemetry_guard_failed": formal_telemetry_guard_failed(
                step.protocol_result
            ),
            "telemetry_failure_categories": list(
                telemetry_failure_categories(step.protocol_result)
            ),
            "telemetry_failure_details": list(
                telemetry_decision_details(step.protocol_result)
            ),
        }
        if contract_not_run_reason:
            step_data["contract_not_run_reason"] = contract_not_run_reason
        if primary_failure:
            step_data["primary_failure"] = primary_failure
        if secondary_observations:
            step_data["secondary_observations"] = secondary_observations
        guidance_audit = (
            extract_research_process_guidance_audit(step.proposal_session_ref)
            or extract_research_process_guidance_audit(
                getattr(step, "scheduler_audit_metadata", {}) or {}
            )
        )
        if guidance_audit:
            step_data["research_process_guidance_audit"] = guidance_audit
        if step.proposal_session_ref:
            allowed_ref_fields = {
                "schema_version",
                "session_id",
                "request_id",
                "idempotency_key",
                "artifact_ref",
                "transcript_digest",
                "termination_reason",
                "status",
                "failure_category",
                "failure_code",
                "agent_block_reason",
                "primary_failure",
                "secondary_observations",
                "rejection_constraint",
                "novelty_warnings",
                "planner_loop_diagnostic",
                "diagnostic_only",
                "formal_round_succeeded",
                "research_process_guidance_audit",
            }
            step_data["proposal_session_ref"] = {
                key: value
                for key, value in dict(step.proposal_session_ref).items()
                if key in allowed_ref_fields
            }
            _annotate_proposal_session_ref_diagnostic(
                step_data["proposal_session_ref"],
                formal_round_succeeded=bool(step.protocol_result is not None),
            )
            step_data["proposal_session_ref"] = redact_public_refs(
                step_data["proposal_session_ref"],
                base_dir=self.campaign_dir,
            )
        if step.protocol_result and step.protocol_result.stats:
            stats = step.protocol_result.stats
            pr = step.protocol_result
            protocol_reason_codes = list(pr.reason_codes)
            effective_reason_codes = decision_reason_codes or protocol_reason_codes
            reason_code_groups = classify_reason_codes(
                tuple(decision_reason_codes) + tuple(protocol_reason_codes),
                protocol_reason_codes=protocol_reason_codes,
            )
            telemetry_details = list(telemetry_decision_details(pr))
            screening_feedback_payload: dict[str, Any] | None = None
            if _stage_value(pr.stage) == "screening":
                try:
                    from scion.proposal.screening_feedback import (
                        screening_feedback_summary,
                    )

                    screening_feedback_payload = screening_feedback_summary(
                        pr,
                        decision_reason_codes=tuple(decision_reason_codes),
                    ).to_payload()
                except Exception as exc:  # pragma: no cover - summary is best-effort
                    logger.debug("screening feedback summary failed: %s", exc)
            raw_metrics_public_ref = public_artifact_ref(
                pr.raw_metrics_ref,
                base_dir=self.campaign_dir,
                kind="metrics",
            )
            runtime_evidence_policy = runtime_evidence_policy_for_protocol(pr)
            step_data["protocol_result"] = {
                "stage": pr.stage.value if hasattr(pr.stage, "value") else str(pr.stage),
                "win_rate": stats.win_rate,
                "win_rate_scope": (
                    "case_level_gate"
                    if _stage_value(pr.stage) == "screening"
                    else "case_level"
                ),
                "case_win_rate": stats.win_rate,
                "gate_win_rate": stats.win_rate,
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
                "runtime_evidence_confidence": pr.runtime_confidence,
                "runtime_evidence_status": getattr(
                    pr,
                    "runtime_evidence_status",
                    getattr(stats, "runtime_evidence_status", "sufficient"),
                ),
                "total_pairs": stats.total_pairs,
                "attempted_pairs": stats.attempted_pairs,
                "valid_pairs": stats.valid_pairs,
                "failed_pairs": stats.failed_pairs,
                "candidate_failed_pairs": stats.candidate_failed_pairs,
                "champion_failed_pairs": stats.champion_failed_pairs,
                "gate_outcome": pr.gate_outcome,
                "reason_codes": list(pr.reason_codes),
                "protocol_reason_codes": protocol_reason_codes,
                "decision_reason_codes": decision_reason_codes,
                "auxiliary_protocol_reason_codes": protocol_reason_codes,
                "effective_reason_codes": effective_reason_codes,
                "gate_observation_reason_codes": list(
                    reason_code_groups.gate_observation_reason_codes
                ),
                "lifecycle_action_reason_codes": list(
                    reason_code_groups.lifecycle_action_reason_codes
                ),
                "effective_reason_source": (
                    "decision_engine" if decision_reason_codes else "protocol_gate"
                ),
                "raw_metrics_ref": raw_metrics_public_ref,
                "raw_metrics_public_ref": raw_metrics_public_ref,
                "raw_metrics_ref_scope": "public_artifact_ref",
                "raw_metrics_internal_only": True,
                "case_ids": [
                    ref
                    for ref in (
                        public_case_ref(case, base_dir=self.campaign_dir)
                        for case in pr.case_ids
                    )
                    if ref is not None
                ],
                "seed_set": list(pr.seed_set),
                "selected_surface": pr.selected_surface,
                "champion_cache_hits": pr.champion_cache_hits,
                "champion_cache_misses": pr.champion_cache_misses,
                "champion_cached_runtime_pairs": pr.champion_cached_runtime_pairs,
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
                "runtime_aggregate_exclusion": (
                    runtime_aggregate_exclusion_for_protocol(pr)
                ),
                "runtime_evidence_policy": runtime_evidence_policy,
                "telemetry_guard_failed": formal_telemetry_guard_failed(pr),
                "telemetry_effect_zero_diagnostics": list(
                    telemetry_effect_zero_diagnostics(pr)
                ),
                "telemetry_failure_categories": list(
                    telemetry_failure_categories(pr)
                ),
                "telemetry_failure_details": telemetry_details,
                "candidate_runtime_failure_categories": dict(
                    pr.candidate_runtime_failure_categories
                    or step.candidate_runtime_failure_categories
                    or {}
                ),
                "candidate_first_runtime_failure": (
                    dict(
                        pr.candidate_first_runtime_failure
                        or step.candidate_first_runtime_failure
                    )
                    if (
                        pr.candidate_first_runtime_failure
                        or step.candidate_first_runtime_failure
                    )
                    else None
                ),
                "candidate_operator_attempts": (
                    pr.candidate_operator_attempts
                    or step.candidate_operator_attempts
                ),
                "candidate_operator_accepted": (
                    pr.candidate_operator_accepted
                    or step.candidate_operator_accepted
                ),
                "candidate_operator_errors": (
                    pr.candidate_operator_errors
                    or step.candidate_operator_errors
                ),
                "candidate_operator_invalid_outputs": (
                    pr.candidate_operator_invalid_outputs
                    or step.candidate_operator_invalid_outputs
                ),
                "candidate_policy_errors": (
                    pr.candidate_policy_errors
                    or step.candidate_policy_errors
                ),
                "candidate_construction_errors": (
                    pr.candidate_construction_errors
                    or step.candidate_construction_errors
                ),
                "candidate_portfolio_errors": (
                    pr.candidate_portfolio_errors
                    or step.candidate_portfolio_errors
                ),
                "candidate_runtime_stop_reasons": dict(
                    pr.candidate_runtime_stop_reasons
                    or step.candidate_runtime_stop_reasons
                    or {}
                ),
                "screened_experiment_effective": screened_experiment_effective(pr),
            }
            if screening_feedback_payload is not None:
                step_data["protocol_result"][
                    "screening_feedback"
                ] = screening_feedback_payload
                step_data["protocol_result"]["screening_feedback_digest"] = (
                    screening_feedback_payload.get("feedback_digest")
                )
                step_data["protocol_result"]["opportunity_status"] = (
                    screening_feedback_payload.get("opportunity_status")
                    or step_data["protocol_result"]["opportunity_status"]
                )
                step_data["protocol_result"]["opportunity_diagnostics"] = (
                    screening_feedback_payload.get("opportunity_diagnostics")
                    or step_data["protocol_result"]["opportunity_diagnostics"]
                )
                step_data["protocol_result"]["mechanism_evidence"] = (
                    screening_feedback_payload.get("mechanism_evidence")
                    or step_data["protocol_result"]["mechanism_evidence"]
                )
            telemetry_feedback = telemetry_validation_feedback(pr)
            if telemetry_feedback:
                step_data["protocol_result"][
                    "telemetry_validation_feedback"
                ] = telemetry_feedback
            step_data["protocol_result"].update(_screening_rate_fields(pr))
            if pr.case_feedback:
                step_data["case_feedback_summary"] = [
                    {
                        "case_id": cf.case_id,
                        "dominant_result": cf.dominant_result,
                        "decisive": (
                            cf.decisive_metric
                            if hasattr(cf, "decisive_metric")
                            else getattr(cf, "dominant_decisive_objective", "")
                        ),
                    }
                    for cf in pr.case_feedback[:20]
                ]
        return step_data


def _annotate_proposal_session_ref_diagnostic(
    session_ref: dict[str, Any],
    *,
    formal_round_succeeded: bool,
) -> None:
    diagnostic = session_ref.get("planner_loop_diagnostic")
    if isinstance(diagnostic, Mapping):
        payload = dict(diagnostic)
    else:
        payload = _planner_loop_diagnostic_from_ref(session_ref)
    if not payload:
        return
    payload["formal_round_succeeded"] = bool(formal_round_succeeded)
    if formal_round_succeeded:
        payload["diagnostic_only"] = True
        session_ref["diagnostic_only"] = True
        session_ref["formal_round_succeeded"] = True
    session_ref["planner_loop_diagnostic"] = payload


def _planner_loop_diagnostic_from_ref(
    session_ref: Mapping[str, Any],
) -> dict[str, Any]:
    failure_category = str(session_ref.get("failure_category") or "").strip()
    termination_reason = str(session_ref.get("termination_reason") or "").strip()
    diagnostic_codes = {
        "tool_budget_exhausted",
        "tool_loop_limit",
        "repeated_tool_call",
    }
    if failure_category not in diagnostic_codes and termination_reason not in diagnostic_codes:
        return {}
    code = failure_category if failure_category in diagnostic_codes else termination_reason
    return {
        "schema_version": "planner_loop_diagnostic.v1",
        "category": "planner_loop_diagnostic",
        "code": code,
        "failure_category": failure_category,
        "termination_reason": termination_reason,
        "diagnostic_only": False,
        "formal_round_succeeded": False,
    }


def _branch_cards_from_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [dict(row["branch_card"]) for row in rows if isinstance(row.get("branch_card"), Mapping)]

def _branch_history_cards(steps: Iterable[StepRecord], active_cards: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    cards_by_branch = {str(card.get("branch_id") or ""): dict(card) for card in active_cards if card.get("branch_id")}
    grouped: dict[str, list[StepRecord]] = {}
    for step in steps:
        grouped.setdefault(step.branch_id, []).append(step)
    for branch_id, branch_steps in grouped.items():
        latest, card = branch_steps[-1], dict(cards_by_branch.get(branch_id, {}))
        reason_codes, evidence = _step_reason_codes(latest), _step_generic_evidence(latest)
        status = _history_card_status(card, _step_status(latest))
        gate_observation_reason_codes = _step_gate_observation_reason_codes(latest)
        lifecycle_action_reason_codes = _step_lifecycle_action_reason_codes(latest)
        retained = bool(card.get("best_quality_checkpoint_id") or card.get("last_valid_checkpoint_id"))
        card.update({
            "branch_id": branch_id,
            "direction": card.get("direction") or f"{latest.hypothesis.action}/{latest.hypothesis.change_locus}",
            "status": status,
            "mechanism_ids": card.get("mechanism_ids") or _step_mechanism_ids(branch_steps),
            "current_head_status": card.get("current_head_status") or evidence["tier"],
            "best_checkpoint_status": card.get("best_checkpoint_status", "none"),
            "best_quality_checkpoint_id": card.get("best_quality_checkpoint_id"),
            "last_valid_checkpoint_id": card.get("last_valid_checkpoint_id"),
            "rollback_count": int(card.get("rollback_count") or 0),
            "latest_head_failed": card.get("latest_head_failed", status == "abandoned" or evidence["tier"] in {"regression", "invalid"}),
            "lineage_retained_checkpoint": retained,
            "allowed_next_actions": card.get("allowed_next_actions") or ["clean_fork"],
            "forbidden_next_actions": card.get("forbidden_next_actions") or ["resume_abandoned_lineage_without_new_evidence"],
            "generic_evidence_summary": card.get("generic_evidence_summary") or evidence,
            "case_level_winners": card.get("case_level_winners")
            or _step_case_outcomes(latest, "win"),
            "case_level_losses": card.get("case_level_losses")
            or _step_case_outcomes(latest, "loss"),
            "phase_activation_summary": card.get("phase_activation_summary")
            or _step_phase_activation_summary(latest),
            "runtime_evidence_confidence": card.get("runtime_evidence_confidence")
            or _step_runtime_evidence_confidence(latest),
            "gate_observation_reason_codes": card.get("gate_observation_reason_codes")
            or gate_observation_reason_codes,
            "lifecycle_action_reason_codes": card.get("lifecycle_action_reason_codes")
            or lifecycle_action_reason_codes,
            "why_not_promoted_reason_codes": card.get("why_not_promoted_reason_codes") or reason_codes,
            "why_abandoned_reason_codes": card.get("why_abandoned_reason_codes") or (reason_codes if status == "abandoned" else []),
        })
        card["branch_card_text"] = branch_prompt_card_from_context(card)
        cards_by_branch[branch_id] = card
    return list(cards_by_branch.values())

def _rollback_events(steps: Iterable[StepRecord], branch_cards: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for step in steps:
        codes = _step_reason_codes(step)
        if any("rollback" in code.lower() for code in codes):
            events.append({"branch_id": step.branch_id, "round": step.round_num, "reason_codes": codes})
    for card in branch_cards:
        rollback_count = int(card.get("rollback_count") or 0)
        if rollback_count:
            events.append({"branch_id": card.get("branch_id"), "rollback_count": rollback_count, "best_quality_checkpoint_id": card.get("best_quality_checkpoint_id"), "last_valid_checkpoint_id": card.get("last_valid_checkpoint_id")})
    return events

def _step_mechanism_ids(steps: Iterable[StepRecord]) -> list[str]:
    ids: list[str] = []
    for step in steps:
        for source in (step.hypothesis, step.patch):
            for change in getattr(source, "mechanism_changes", ()) or ():
                value = str(getattr(change, "id", "") or "").strip()
                if value:
                    ids.append(value)
        ids.extend(str(item) for item in (step.repair_mechanism_ids or ()) if item)
    return list(dict.fromkeys(ids))

def _step_reason_codes(step: StepRecord) -> list[str]:
    codes = list(step.decision_reason_codes or ())
    if step.protocol_result is not None:
        codes.extend(step.protocol_result.reason_codes)
    detail = str(step.failure_detail or step.verification_detail or "").strip()
    if detail:
        codes.append(detail.split(":", 1)[0].split()[0])
    return list(dict.fromkeys(str(code) for code in codes if str(code)))

def _step_gate_observation_reason_codes(step: StepRecord) -> list[str]:
    groups = _step_reason_code_groups(step)
    return list(groups.gate_observation_reason_codes)

def _step_lifecycle_action_reason_codes(step: StepRecord) -> list[str]:
    groups = _step_reason_code_groups(step)
    return list(groups.lifecycle_action_reason_codes)

def _step_reason_code_groups(step: StepRecord):
    protocol_reason_codes: Iterable[str] = ()
    if step.protocol_result is not None:
        protocol_reason_codes = step.protocol_result.reason_codes
    return classify_reason_codes(
        _step_reason_codes(step),
        protocol_reason_codes=protocol_reason_codes,
    )

def _step_generic_evidence(step: StepRecord) -> dict[str, Any]:
    pr = step.protocol_result
    if pr is None:
        return {"tier": "invalid" if step.failure_stage else "unknown"}
    stats = pr.stats
    if stats.losses > stats.wins or stats.median_delta < 0:
        tier = "regression"
    elif stats.wins > stats.losses:
        tier = "weak_positive" if pr.gate_outcome == "pass" else "marginal"
    else:
        tier = "no_effect" if stats.wins == 0 and stats.losses == 0 else "marginal"
    evidence: dict[str, Any] = {"tier": tier, "wins": stats.wins, "losses": stats.losses, "ties": stats.ties, "effect": {"median_delta": stats.median_delta, "ci_low": stats.ci_low, "ci_high": stats.ci_high}}
    if stats.runtime_ratio_median is not None or stats.runtime_regression_rate is not None:
        evidence["runtime"] = {"runtime_ratio_median": stats.runtime_ratio_median, "runtime_regression_rate": stats.runtime_regression_rate}
    runtime_confidence = str(getattr(pr, "runtime_confidence", "") or "").strip()
    if runtime_confidence:
        evidence["runtime_evidence_confidence"] = runtime_confidence
    runtime_status = str(getattr(pr, "runtime_evidence_status", "") or "").strip()
    if runtime_status:
        evidence["runtime_evidence_status"] = runtime_status
    runtime_aggregate_exclusion = runtime_aggregate_exclusion_for_protocol(pr)
    if runtime_aggregate_exclusion:
        evidence["runtime_aggregate_exclusion"] = runtime_aggregate_exclusion
    runtime_evidence_policy = runtime_evidence_policy_for_protocol(pr)
    if runtime_evidence_policy:
        evidence["runtime_evidence_policy"] = runtime_evidence_policy
    return evidence

def _step_case_outcomes(step: StepRecord, dominant_result: str) -> list[dict[str, Any]]:
    pr = step.protocol_result
    if pr is None:
        return []
    outcomes: list[dict[str, Any]] = []
    for feedback in getattr(pr, "case_feedback", ()) or ():
        if str(getattr(feedback, "dominant_result", "") or "") != dominant_result:
            continue
        deltas = getattr(feedback, "median_deltas", {}) or {}
        outcomes.append(
            {
                "case_id": str(getattr(feedback, "case_id", "") or ""),
                "result": dominant_result,
                "delta": _case_delta_for_protocol(deltas, pr),
                "effect_counters": {
                    "wins": max(0, int(getattr(feedback, "wins", 0) or 0)),
                    "losses": max(0, int(getattr(feedback, "losses", 0) or 0)),
                    "ties": max(0, int(getattr(feedback, "ties", 0) or 0)),
                    "pairs": max(0, int(getattr(feedback, "n_pairs", 0) or 0)),
                },
            }
        )
        if len(outcomes) >= 5:
            return outcomes
    if outcomes:
        return outcomes
    return _step_pair_outcomes(pr, dominant_result)

def _step_pair_outcomes(protocol_result: Any, dominant_result: str) -> list[dict[str, Any]]:
    grouped: dict[str, list[Any]] = {}
    for row in getattr(protocol_result, "pair_feedback", ()) or ():
        case_id = str(getattr(row, "case_id", "") or "")
        if case_id:
            grouped.setdefault(case_id, []).append(row)
    outcomes: list[dict[str, Any]] = []
    for case_id, rows in sorted(grouped.items()):
        wins = sum(1 for row in rows if getattr(row, "comparison", None) == "win")
        losses = sum(1 for row in rows if getattr(row, "comparison", None) == "loss")
        ties = len(rows) - wins - losses
        result = "win" if wins > losses else "loss" if losses > wins else "tie"
        if result != dominant_result:
            continue
        deltas = [
            float(getattr(row, "delta"))
            for row in rows
            if isinstance(getattr(row, "delta", None), (int, float))
        ]
        outcomes.append(
            {
                "case_id": case_id,
                "result": result,
                "delta": _median(deltas) if deltas else None,
                "effect_counters": {
                    "wins": wins,
                    "losses": losses,
                    "ties": ties,
                    "pairs": len(rows),
                },
            }
        )
        if len(outcomes) >= 5:
            return outcomes
    return outcomes

def _step_phase_activation_summary(step: StepRecord) -> dict[str, Any]:
    pr = step.protocol_result
    if pr is None:
        return {
            "stage": str(step.failure_stage or "unknown"),
            "activation_status": "unknown",
            "effect_status": "unknown",
            "activation_evidence_status": "unknown",
            "objective_effect_status": "unknown",
            "opportunity_status": "unknown",
            "telemetry_outcome": None,
        }
    stats = pr.stats
    mechanism_evidence = mechanism_evidence_for_protocol(pr)
    return {
        "stage": _stage_value(pr.stage),
        "activation_status": str(
            mechanism_evidence.get("primary_activation_status") or "unknown"
        ),
        "effect_status": str(
            mechanism_evidence.get("primary_effect_status")
            or (
                "observed"
                if max(0, int(getattr(stats, "wins", 0) or 0))
                or max(0, int(getattr(stats, "losses", 0) or 0))
                else "not_observed"
            )
        ),
        "activation_evidence_status": str(
            mechanism_evidence.get("activation_evidence_status") or "unknown"
        ),
        "objective_effect_status": str(
            mechanism_evidence.get("objective_effect_status") or "unknown"
        ),
        "opportunity_status": str(getattr(pr, "opportunity_status", "") or "unknown"),
        "telemetry_outcome": "failed" if formal_telemetry_guard_failed(pr) else pr.gate_outcome,
    }

def _step_runtime_evidence_confidence(step: StepRecord) -> str:
    pr = step.protocol_result
    if pr is None:
        return "unknown"
    return str(getattr(pr, "runtime_confidence", "") or "unknown")

def _case_delta_for_protocol(deltas: Mapping[str, Any], protocol_result: Any) -> float | None:
    if not isinstance(deltas, Mapping):
        return None
    metric = str(getattr(protocol_result.stats, "statistical_metric", "") or "")
    keys = [metric] if metric else []
    keys.extend(sorted(str(key) for key in deltas if str(key) not in keys))
    for key in keys:
        try:
            return float(deltas[key])
        except (KeyError, TypeError, ValueError):
            continue
    return None

def _median(values: list[float]) -> float:
    ordered = sorted(values)
    size = len(ordered)
    midpoint = size // 2
    if size % 2:
        return ordered[midpoint]
    return (ordered[midpoint - 1] + ordered[midpoint]) / 2.0

def _step_status(step: StepRecord) -> str:
    decision = step.decision.value if getattr(step.decision, "value", None) else None
    return "abandoned" if decision == "abandon" else str(step.failure_stage or decision or "screened")

def _history_card_status(card: Mapping[str, Any], step_status: str) -> str:
    card_status = str(card.get("status") or "").strip()
    current_head_status = str(card.get("current_head_status") or "").strip()
    branch_code_status = str(card.get("branch_code_status") or "").strip()
    active_slot_status = str(card.get("active_slot_status") or "").strip()
    terminal_statuses = {"abandoned", "archived", "parked_lineage", "promoted"}
    for status in (card_status, current_head_status, branch_code_status, active_slot_status):
        if status in terminal_statuses:
            return status
    if step_status == "abandoned":
        return step_status
    return card_status or step_status

def _runtime_budget_diagnostic(protocol_result: Any) -> dict[str, Any] | None:
    surface_summary = getattr(protocol_result, "candidate_surface_runtime_summary", None)
    if not isinstance(surface_summary, Mapping):
        return None
    diagnostic = surface_summary.get("runtime_budget_diagnostic")
    return dict(diagnostic) if isinstance(diagnostic, Mapping) else None


def _runtime_budget_diagnostic_details(
    steps: Iterable[StepRecord],
) -> list[dict[str, Any]]:
    details: list[dict[str, Any]] = []
    for step in steps:
        pr = step.protocol_result
        if pr is None:
            continue
        diagnostic = _runtime_budget_diagnostic(pr)
        if not diagnostic:
            continue
        details.append(
            {
                "branch_id": step.branch_id,
                "action": step.hypothesis.action,
                "target_file": step.hypothesis.target_file,
                "stage": _stage_value(pr.stage),
                "code": diagnostic.get("code"),
                "severity": diagnostic.get("severity"),
                "saturation_ratio": diagnostic.get("saturation_ratio"),
                "threshold_ratio": diagnostic.get("threshold_ratio"),
                "total_pairs": diagnostic.get("total_pairs"),
            }
        )
    return details


def _telemetry_effect_zero_details(
    steps: Iterable[StepRecord],
) -> list[dict[str, Any]]:
    details: list[dict[str, Any]] = []
    for step in steps:
        pr = step.protocol_result
        if pr is None:
            continue
        for diagnostic in telemetry_effect_zero_diagnostics(pr):
            details.append(
                {
                    "branch_id": step.branch_id,
                    "action": step.hypothesis.action,
                    "target_file": step.hypothesis.target_file,
                    **dict(diagnostic),
                }
            )
    return details


def _campaign_cache_stats(
    steps: Iterable[StepRecord],
    *,
    campaign_dir: Any,
) -> dict[str, Any]:
    """Return campaign-level prompt-cache statistics.

    Legacy step records may contain coarse cache stats, but agentic LLM calls
    write the authoritative per-call usage to ``llm_traces/*.json``. Prefer the
    trace aggregate when present so campaign summaries reflect actual provider
    cache reads/writes and can surface repeated cache creates for an unchanged
    prompt-cache key.
    """
    step_stats = _step_cache_stats(steps)
    trace_stats = _llm_trace_cache_stats(campaign_dir)
    if trace_stats["calls"] > 0:
        return trace_stats
    return step_stats


def _step_cache_stats(steps: Iterable[StepRecord]) -> dict[str, Any]:
    total_tokens = 0
    cache_read_tokens = 0
    cache_create_tokens = 0
    for step in steps:
        cs = step.cache_stats or {}
        total_tokens += _safe_int(cs.get("total", 0))
        cache_read_tokens += _safe_int(cs.get("cache_read", 0))
        cache_create_tokens += _safe_int(cs.get("cache_create", 0))
    cache_hit_rate = (
        round(cache_read_tokens / total_tokens, 4) if total_tokens > 0 else 0.0
    )
    return {
        "total_tokens": total_tokens,
        "cache_read_tokens": cache_read_tokens,
        "cache_create_tokens": cache_create_tokens,
        "cache_hit_rate": cache_hit_rate,
        "output_tokens": 0,
        "calls": 0,
        "source": "step_records",
        "repeated_cache_create_groups": [],
    }


def _llm_trace_cache_stats(campaign_dir: Any) -> dict[str, Any]:
    trace_dir = getattr(campaign_dir, "joinpath", None)
    if callable(trace_dir):
        llm_dir = campaign_dir.joinpath("llm_traces")
    else:
        from pathlib import Path

        llm_dir = Path(campaign_dir) / "llm_traces"
    total_tokens = 0
    output_tokens = 0
    cache_read_tokens = 0
    cache_create_tokens = 0
    calls = 0
    groups: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    if not llm_dir.exists():
        return {
            "total_tokens": 0,
            "cache_read_tokens": 0,
            "cache_create_tokens": 0,
            "cache_hit_rate": 0.0,
            "output_tokens": 0,
            "calls": 0,
            "source": "llm_traces",
            "repeated_cache_create_groups": [],
        }
    for trace_path in sorted(llm_dir.glob("*.json")):
        try:
            payload = json.loads(trace_path.read_text())
        except Exception as exc:  # pragma: no cover - best-effort summary
            logger.debug("failed to read llm trace cache stats %s: %s", trace_path, exc)
            continue
        usage = payload.get("llm_usage")
        if not isinstance(usage, Mapping):
            continue
        prompt_tokens = _safe_int(usage.get("input_tokens"))
        cache_create = _safe_int(usage.get("cache_creation_input_tokens"))
        cache_read = _safe_int(usage.get("cache_read_input_tokens"))
        completion_tokens = _safe_int(usage.get("output_tokens"))
        calls += 1
        total_tokens += prompt_tokens + cache_create + cache_read
        output_tokens += completion_tokens
        cache_create_tokens += cache_create
        cache_read_tokens += cache_read
        audit = payload.get("prompt_cache_audit")
        if isinstance(audit, Mapping):
            cache_hash = str(audit.get("cacheable_system_blocks_hash") or "")
            tool_schema_hash = str(audit.get("tool_schema_hash") or "")
            cacheable_chars = _safe_int(audit.get("cacheable_system_chars"))
        else:
            cache_hash = ""
            tool_schema_hash = ""
            cacheable_chars = 0
        if cache_hash:
            key = (
                str(payload.get("request_kind") or usage.get("request_kind") or ""),
                str(usage.get("model") or payload.get("model") or ""),
                cache_hash,
                tool_schema_hash,
            )
            group = groups.setdefault(
                key,
                {
                    "request_kind": key[0],
                    "model": key[1],
                    "cacheable_system_blocks_hash": cache_hash,
                    "tool_schema_hash": tool_schema_hash,
                    "cacheable_system_chars": cacheable_chars,
                    "calls": 0,
                    "cache_create_calls": 0,
                    "cache_read_calls": 0,
                    "cache_create_tokens": 0,
                    "cache_read_tokens": 0,
                    "first_trace": trace_path.name,
                    "last_trace": trace_path.name,
                },
            )
            group["calls"] += 1
            group["last_trace"] = trace_path.name
            if cache_create > 0:
                group["cache_create_calls"] += 1
                group["cache_create_tokens"] += cache_create
            if cache_read > 0:
                group["cache_read_calls"] += 1
                group["cache_read_tokens"] += cache_read
    cache_hit_rate = (
        round(cache_read_tokens / total_tokens, 4) if total_tokens > 0 else 0.0
    )
    repeated = [
        {
            **group,
            "diagnosis": (
                "same cache key produced multiple cache writes without a read; "
                "the provider likely has cache warmup/visibility delay, unless "
                "the upstream service treats additional hidden request fields as "
                "part of the cache key"
            )
            if group["cache_read_calls"] == 0
            else (
                "same cache key warmed before later reads; this is expected with "
                "provider-side eventual cache visibility"
            ),
        }
        for group in groups.values()
        if group["cache_create_calls"] > 1
    ]
    return {
        "total_tokens": total_tokens,
        "cache_read_tokens": cache_read_tokens,
        "cache_create_tokens": cache_create_tokens,
        "cache_hit_rate": cache_hit_rate,
        "output_tokens": output_tokens,
        "calls": calls,
        "source": "llm_traces",
        "repeated_cache_create_groups": repeated,
    }


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
