"""Campaign summary builder for evidence recording."""
from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping

from scion.core.branch_cards import active_slot_inventory_from_branch_cards
from scion.core.models import ChampionState, StepRecord
from scion.core.public_refs import public_artifact_ref, public_case_ref, redact_public_refs
from scion.core.research_process_guidance_audit import (
    extract_research_process_guidance_audit,
)
from scion.core.reason_code_groups import classify_reason_codes
from scion.core.run_validity import (
    apply_run_completion_aliases,
    build_run_validity,
    step_failure_categories,
)
from scion.core.screening_visibility import (
    candidate_intent_counts_for_steps,
    candidate_intent_visibility_for_step,
    observability_value_counts_for_steps,
    observability_value_visibility_for_step,
    runtime_aggregate_exclusion_for_protocol,
    runtime_gate_visibility_for_protocol,
    runtime_evidence_policy_for_protocol,
    runtime_evidence_policy_counts_for_steps,
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
from .summary_branch_history import (
    _branch_cards_from_rows,
    _branch_history_cards,
    _rollback_events,
)
from .summary_cache import _campaign_cache_stats
from .telemetry_summary import (
    _telemetry_failed_experiment_category_counts,
    _telemetry_failed_experiment_details,
)

logger = logging.getLogger(__name__)


_VISIBILITY_AUDIT_RECORD_KEYS = {
    "schema_version",
    "record_type",
    "record_id",
    "record_digest",
    "requirement_digest",
    "requirement_id",
    "status",
    "requirement_status",
    "source",
    "source_ref",
    "artifact_ref",
    "digest",
    "reason_codes",
    "policy",
    "proposal_visibility_only",
    "decision_features_excluded",
    "decision_input_policy",
    "material_difference_required",
}

_VISIBILITY_AUDIT_CONTAINER_KEYS = {
    "cross_branch_research_audit_records",
    "material_difference_audit_records",
    "material_difference_requirement",
    "material_difference_requirement_ref",
    "material_difference_requirement_status",
    "cross_branch_research_payload",
    "cross_branch_research_status",
    "cross_branch_research_audit_ref",
    "novelty_pressure",
}


def _summary_scope_reconciliation(
    *,
    steps: list[StepRecord],
    branch_rows: Iterable[Mapping[str, Any]],
    cross_branch_observability: Mapping[str, Any] | None,
) -> dict[str, Any]:
    branch_row_list = [row for row in branch_rows if isinstance(row, Mapping)]
    protocol_steps = [step for step in steps if step.protocol_result is not None]
    failed_steps = [step for step in steps if step.failure_stage]
    non_counted_steps = [
        step for step in steps if not getattr(step, "counts_toward_max_rounds", True)
    ]
    source_counts = {
        "step_history_total": len(steps),
        "protocol_step_count": len(protocol_steps),
        "screening_protocol_step_count": sum(
            1 for step in steps if formal_screening_attempted(step.protocol_result)
        ),
        "effective_protocol_step_count": sum(
            1 for step in steps if screened_experiment_effective(step.protocol_result)
        ),
        "failed_step_count": len(failed_steps),
        "non_counted_step_count": len(non_counted_steps),
        "branch_row_count": len(branch_row_list),
    }
    if isinstance(cross_branch_observability, Mapping):
        source_counts["cross_branch_observable_step_count"] = (
            cross_branch_observability.get("observable_step_count")
        )
    return {
        "schema_version": "evidence_scope_reconciliation.v1",
        "payload": "campaign_summary",
        "step_history_scope": "full_step_history",
        "branch_state_scope": "branch_rows_snapshot" if branch_row_list else "none",
        "last_result_scope": "not_used",
        "protocol_progress_scope": "completed_step_protocol_results",
        "includes_failed_steps": bool(failed_steps),
        "includes_non_counted_steps": bool(non_counted_steps),
        "source_counts": source_counts,
    }


def _summary_current_progress(
    state: Mapping[str, Any],
    *,
    stopped: bool,
) -> dict[str, Any] | None:
    progress = state.get("current_progress")
    if not isinstance(progress, Mapping):
        return None
    if stopped and progress.get("complete") is not True:
        return None
    return dict(progress)


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
        candidate_intent_counts = candidate_intent_counts_for_steps(steps)
        observability_value_counts = observability_value_counts_for_steps(steps)
        runtime_evidence_policy_counts = runtime_evidence_policy_counts_for_steps(
            steps
        )
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
            "candidate_intent_counts": candidate_intent_counts,
            "observability_value_counts": observability_value_counts,
            "runtime_evidence_policy_counts": runtime_evidence_policy_counts,
            "fresh_champion_required_count": runtime_evidence_policy_counts[
                "fresh_champion_required_count"
            ],
            "runtime_aggregate_excluded_count": runtime_evidence_policy_counts[
                "runtime_aggregate_excluded_count"
            ],
            "champion_version": champion.version,
            "champion_weight_revision": getattr(champion, "weight_revision", 0),
            "stopped_reason": effective_stopped_reason,
            "stopped": effective_stopped_reason not in (None, "run_complete"),
            "balance_exhausted": inferred_balance_exhausted,
            "circuit_breaker_tripped": circuit_breaker_tripped,
            "cache_stats": {
                "total_tokens": cache_stats["total_tokens"],
                "prompt_tokens_total": cache_stats["prompt_tokens_total"],
                "input_tokens": cache_stats["input_tokens"],
                "cache_read_tokens": cache_stats["cache_read_tokens"],
                "cache_miss_tokens": cache_stats["cache_miss_tokens"],
                "cache_create_tokens": cache_stats["cache_create_tokens"],
                "cache_hit_rate": cache_stats["cache_hit_rate"],
                "cache_accounting_modes": cache_stats["cache_accounting_modes"],
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
                **(
                    {
                        "by_request_kind_provider": cache_stats[
                            "by_request_kind_provider"
                        ]
                    }
                    if cache_stats.get("by_request_kind_provider")
                    else {}
                ),
                **(
                    {
                        "repeated_cache_key_groups": cache_stats[
                            "repeated_cache_key_groups"
                        ]
                    }
                    if cache_stats.get("repeated_cache_key_groups")
                    else {}
                ),
                **(
                    {
                        "repeated_cache_key_no_read": cache_stats[
                            "repeated_cache_key_no_read"
                        ]
                    }
                    if cache_stats.get("repeated_cache_key_no_read")
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
                "scheduler_active_slot_blocked_attempts",
                "active_slot_blocked_attempts",
                "scheduler_active_slot_blocked_attempt_limit",
                "active_slot_blocked_attempt_limit",
                "quality_blocks",
                "quality_block_ledger",
                "quality_block_ledger_count",
                "non_effective_screenings",
                "non_effective_screening_count",
                "blocked_attempts",
            ):
                value = self.campaign_loop_status.get(key)
                if value is not None:
                    summary[key] = value
        summary = apply_run_completion_aliases(summary)
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
                current_progress = _summary_current_progress(
                    state,
                    stopped=bool(summary.get("stopped")),
                )
                if current_progress is not None:
                    summary["current_progress"] = current_progress
                if isinstance(state.get("weight_optimization"), Mapping):
                    summary["weight_optimization"] = dict(
                        state["weight_optimization"]
                    )
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
        summary["evidence_scope_reconciliation"] = _summary_scope_reconciliation(
            steps=steps,
            branch_rows=summary.get("branches") or (),
            cross_branch_observability=summary.get(
                "cross_branch_research_observability"
            )
            if isinstance(summary.get("cross_branch_research_observability"), Mapping)
            else None,
        )

        for step in steps:
            summary["steps"].append(self._build_summary_step(step))

        summary = redact_public_refs(summary, base_dir=self.campaign_dir)
        out_path = self.campaign_dir / "campaign_summary.json"
        try:
            _write_text_atomically(out_path, _render_campaign_summary_json(summary))
        except Exception as exc:  # pragma: no cover
            logger.warning("Failed to write campaign_summary.json: %s", exc)
        return summary

    def _build_summary_step(self, step: StepRecord) -> Dict[str, Any]:
        decision_reason_codes = list(step.decision_reason_codes or ())
        candidate_intent_visibility = candidate_intent_visibility_for_step(step)
        observability_value_visibility = observability_value_visibility_for_step(step)
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
        if candidate_intent_visibility:
            step_data["candidate_intent"] = candidate_intent_visibility[
                "candidate_intent"
            ]
            step_data["candidate_intent_visibility"] = candidate_intent_visibility
            if candidate_intent_visibility.get("quality_search_interpretation"):
                step_data["quality_search_interpretation"] = (
                    candidate_intent_visibility["quality_search_interpretation"]
                )
        if observability_value_visibility:
            step_data["observability_value_visibility"] = (
                observability_value_visibility
            )
        step_data["step_visibility_audit"] = _step_visibility_audit(
            step,
            candidate_intent_visibility=candidate_intent_visibility,
            observability_value_visibility=observability_value_visibility,
        )
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
                "cross_branch_research_audit_records",
                "cross_branch_research_audit_ref",
                "cross_branch_research_payload",
                "cross_branch_research_status",
                "material_difference_audit_records",
                "material_difference_requirement",
                "material_difference_requirement_ref",
                "material_difference_requirement_status",
                "novelty_pressure",
            }
            audit_ref_fields = _VISIBILITY_AUDIT_CONTAINER_KEYS
            session_ref: dict[str, Any] = {}
            for key, value in dict(step.proposal_session_ref).items():
                if key not in allowed_ref_fields:
                    continue
                if key in audit_ref_fields:
                    compact_value = _compact_visibility_audit_value(value)
                    if compact_value:
                        session_ref[key] = compact_value
                    continue
                session_ref[key] = value
            step_data["proposal_session_ref"] = session_ref
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
            runtime_gate_visibility = runtime_gate_visibility_for_protocol(pr)
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
                "runtime_gate_visibility": runtime_gate_visibility,
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
            step_data["protocol_result"]["candidate_intent"] = (
                candidate_intent_visibility["candidate_intent"]
            )
            step_data["protocol_result"]["candidate_intent_visibility"] = (
                candidate_intent_visibility
            )
            step_data["protocol_result"]["observability_value_visibility"] = (
                observability_value_visibility
            )
            if candidate_intent_visibility.get("quality_search_interpretation"):
                step_data["protocol_result"]["quality_search_interpretation"] = (
                    candidate_intent_visibility["quality_search_interpretation"]
                )
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


def _step_visibility_audit(
    step: StepRecord,
    *,
    candidate_intent_visibility: Mapping[str, Any],
    observability_value_visibility: Mapping[str, Any],
) -> dict[str, Any]:
    cross_branch_records, material_records = _step_cross_branch_material_records(step)
    return {
        "schema_version": "step_visibility_audit.v1",
        "proposal_visibility_only": True,
        "decision_features_excluded": True,
        "candidate_intent_visibility": {
            "status": "derived" if candidate_intent_visibility else "missing",
            "ref": "candidate_intent_visibility",
            "candidate_intent": candidate_intent_visibility.get(
                "candidate_intent",
                "unknown",
            ),
            "reason_codes": list(
                candidate_intent_visibility.get(
                    "candidate_intent_reason_codes",
                    (),
                )
                or ()
            ),
        },
        "observability_value_visibility": {
            "status": "derived" if observability_value_visibility else "missing",
            "ref": "observability_value_visibility",
            "observability_value_status": observability_value_visibility.get(
                "observability_value_status",
                "missing",
            ),
            "reason_codes": list(
                observability_value_visibility.get("reason_codes", ()) or ()
            ),
        },
        "cross_branch_research_visibility": {
            "status": "available" if cross_branch_records else "missing",
            "record_count": len(cross_branch_records),
            "records": cross_branch_records,
        },
        "material_difference_requirement_visibility": {
            "status": "available" if material_records else "missing",
            "record_count": len(material_records),
            "records": material_records,
        },
    }


def _step_cross_branch_material_records(
    step: StepRecord,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cross_branch_records: list[dict[str, Any]] = []
    material_records: list[dict[str, Any]] = []
    for source, value in (
        ("scheduler_audit_metadata", getattr(step, "scheduler_audit_metadata", {})),
        ("proposal_session_ref", getattr(step, "proposal_session_ref", {}) or {}),
    ):
        if not isinstance(value, Mapping):
            continue
        for kind, record in _visibility_records_from_mapping(value, source=source):
            if kind == "material":
                material_records.append(record)
            else:
                cross_branch_records.append(record)
    return (
        _dedupe_visibility_records(cross_branch_records),
        _dedupe_visibility_records(material_records),
    )


def _visibility_records_from_mapping(
    item: Mapping[str, Any],
    *,
    source: str,
) -> Iterable[tuple[str, dict[str, Any]]]:
    for key in (
        "cross_branch_research_audit_records",
        "material_difference_audit_records",
    ):
        values = item.get(key)
        if not isinstance(values, (list, tuple)):
            continue
        kind = "material" if key.startswith("material") else "cross_branch"
        for value in values:
            record = _compact_visibility_audit_record(value, source=source)
            if record:
                yield kind, record

    material_requirement = item.get("material_difference_requirement")
    if isinstance(material_requirement, Mapping):
        record = _compact_visibility_audit_record(
            material_requirement,
            source=source,
        )
        if record:
            yield "material", record

    for key in (
        "material_difference_requirement_ref",
        "material_difference_requirement_status",
        "cross_branch_research_audit_ref",
        "cross_branch_research_status",
    ):
        value = item.get(key)
        if value in (None, "", (), []):
            continue
        kind = "material" if key.startswith("material") else "cross_branch"
        yield kind, {
            "source": source,
            "record_type": key,
            "status": str(value) if "status" in key else "available",
            **({"source_ref": str(value)} if "ref" in key else {}),
        }

    for key in ("cross_branch_research_payload", "novelty_pressure"):
        payload = item.get(key)
        if not isinstance(payload, Mapping):
            continue
        for nested_kind, nested_record in _visibility_records_from_mapping(
            payload,
            source=f"{source}.{key}",
        ):
            yield nested_kind, nested_record


def _compact_visibility_audit_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        compact: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if key_text in _VISIBILITY_AUDIT_RECORD_KEYS:
                compact_item = _compact_visibility_scalar_or_list(item)
                if compact_item not in (None, [], {}):
                    compact[key_text] = compact_item
                continue
            if key_text in _VISIBILITY_AUDIT_CONTAINER_KEYS:
                compact_item = _compact_visibility_audit_value(item)
                if compact_item not in (None, [], {}):
                    compact[key_text] = compact_item
        return compact
    if isinstance(value, (list, tuple)):
        records = [
            _compact_visibility_audit_value(item)
            for item in value
            if isinstance(item, Mapping)
        ]
        return [record for record in records if record]
    return _compact_visibility_scalar_or_list(value)


def _compact_visibility_audit_record(
    value: Any,
    *,
    source: str,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    compact = _compact_visibility_audit_value(value)
    if not isinstance(compact, dict):
        return {}
    compact["source"] = str(compact.get("source") or source)
    if "status" not in compact:
        compact["status"] = "available"
    return compact


def _compact_visibility_scalar_or_list(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        compact: list[Any] = []
        for item in value:
            if isinstance(item, (str, int, float, bool)):
                compact.append(item)
        return compact
    if isinstance(value, Mapping):
        return _compact_visibility_audit_value(value)
    return None


def _dedupe_visibility_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str, str]] = set()
    deduped: list[dict[str, Any]] = []
    for record in records:
        key = (
            str(record.get("record_id") or ""),
            str(record.get("record_digest") or ""),
            str(record.get("source_ref") or ""),
            str(record.get("record_type") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(record)
    return deduped


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
