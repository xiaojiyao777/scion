"""Campaign summary builder for evidence recording."""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Iterable, Mapping

from scion.core.models import ChampionState, StepRecord
from scion.core.public_refs import public_artifact_ref, public_case_ref, redact_public_refs
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
    telemetry_failure_categories,
    telemetry_validation_feedback,
)
from scion.evidence.formal_readiness import validate_formal_readiness

from .artifact_refs import _screening_rate_fields
from .common import _stage_value
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
        screened_experiments = sum(
            1 for step in steps if formal_screening_attempted(step.protocol_result)
        )
        effective_rounds_completed = sum(
            1 for step in steps if screened_experiment_effective(step.protocol_result)
        )
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
        loop_telemetry_repair_attempts = None
        loop_telemetry_repair_counts = None
        if isinstance(loop_status, Mapping):
            loop_proposal_attempts = loop_status.get("proposal_attempts_consumed")
            loop_total_rounds = loop_status.get("total_rounds")
            loop_effective_rounds = loop_status.get("effective_rounds_completed")
            loop_telemetry_repair_attempts = loop_status.get(
                "telemetry_repair_attempts"
            )
            loop_telemetry_repair_counts = loop_status.get(
                "telemetry_repair_attempts_by_branch_mechanism"
            )
            if loop_effective_rounds is not None:
                effective_rounds_completed = int(loop_effective_rounds)

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
            "effective_rounds_completed": effective_rounds_completed,
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
                "telemetry_diagnostic_attempts",
                "quality_blocks",
                "blocked_attempts",
            ):
                value = self.campaign_loop_status.get(key)
                if value is not None:
                    summary[key] = value
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
                summary["n_active_branches"] = state.get("n_active_branches")
                summary["branches"] = list(state.get("branches") or [])
            except Exception as exc:  # pragma: no cover - summary is best-effort
                logger.debug("state snapshot for campaign_summary failed: %s", exc)

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
            }
            step_data["proposal_session_ref"] = {
                key: value
                for key, value in dict(step.proposal_session_ref).items()
                if key in allowed_ref_fields
            }
            step_data["proposal_session_ref"] = redact_public_refs(
                step_data["proposal_session_ref"],
                base_dir=self.campaign_dir,
            )
        if step.protocol_result and step.protocol_result.stats:
            stats = step.protocol_result.stats
            pr = step.protocol_result
            protocol_reason_codes = list(pr.reason_codes)
            effective_reason_codes = decision_reason_codes or protocol_reason_codes
            telemetry_details = list(telemetry_decision_details(pr))
            raw_metrics_public_ref = public_artifact_ref(
                pr.raw_metrics_ref,
                base_dir=self.campaign_dir,
                kind="metrics",
            )
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
                "candidate_surface_runtime_summary": dict(
                    pr.candidate_surface_runtime_summary or {}
                ),
                "telemetry_guard_failed": formal_telemetry_guard_failed(pr),
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
