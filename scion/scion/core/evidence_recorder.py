"""Evidence recording boundary for campaign artifacts.

This module is intentionally a service shell for v0.4 Phase 1.  It mirrors
CampaignManager's current status, lineage, and summary payloads so integration
can move call sites behind this boundary without changing artifact schemas.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Mapping, MutableSequence

from scion.core.models import (
    Branch,
    CanaryResult,
    ChampionState,
    ContractResult,
    Decision,
    HypothesisProposal,
    PatchProposal,
    ProtocolResult,
    StepRecord,
    VerificationResult,
)
from scion.core.status_reporter import StatusReporter
from scion.evidence.formal_readiness import validate_formal_readiness

logger = logging.getLogger(__name__)


StateProvider = Callable[[], Mapping[str, Any]]


def _serialize_verification_checks(
    verification_result: VerificationResult,
) -> list[Dict[str, Any]]:
    return [
        {
            "name": check.name,
            "passed": check.passed,
            "severity": check.severity,
            "elapsed_ms": check.elapsed_ms,
            "metadata": dict(check.metadata or {}),
        }
        for check in verification_result.checks
    ]


def _extract_runtime_guard_evidence(
    verification_result: VerificationResult,
) -> Dict[str, Any]:
    for check in verification_result.checks:
        if check.name == "V9_perf_guard":
            return {
                "passed": check.passed,
                "detail": check.detail,
                "elapsed_ms": check.elapsed_ms,
                "metadata": dict(check.metadata or {}),
            }
    return {}


def _extract_protocol_runtime_stats(
    protocol_result: ProtocolResult | None,
) -> Dict[str, Any]:
    if protocol_result is None:
        return {
            "runtime_ratio_median": None,
            "runtime_delta_median_ms": None,
            "runtime_regression_rate": None,
            "runtime_pairs": 0,
        }
    stats = protocol_result.stats
    return {
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
    }


class EvidenceRecorder:
    """Record campaign evidence while preserving existing artifact contracts."""

    def __init__(
        self,
        *,
        campaign_id: str,
        campaign_dir: str | Path,
        status_reporter: StatusReporter | None = None,
        registry: Any | None = None,
        state_provider: StateProvider | None = None,
        model_id: str | None = None,
        protocol_version: str | None = None,
        family_taxonomy: Any | None = None,
    ) -> None:
        self.campaign_id = campaign_id
        self.campaign_dir = Path(campaign_dir)
        self.status_reporter = status_reporter or StatusReporter(str(self.campaign_dir))
        self.registry = registry
        self.state_provider = state_provider
        self.model_id = model_id
        self.protocol_version = protocol_version
        self.family_taxonomy = family_taxonomy
        self.current_status_progress: Dict[str, Any] | None = None
        self.last_status_result: Dict[str, Any] | None = None
        self.final_evidence_refs: Dict[str, Any] = {}

    def record_step(
        self,
        step: StepRecord,
        step_history: MutableSequence[StepRecord],
        *,
        search_memory: Any | None = None,
    ) -> None:
        """Append a completed step and update optional search memory."""
        step_history.append(step)
        if search_memory is not None:
            search_memory.update(step)

    def write_status(
        self,
        *,
        last_result: Any | None = None,
        stopped_reason: str | None = None,
    ) -> Dict[str, Any]:
        """Write ``status.json`` using the existing CampaignManager payload shape."""
        payload: Dict[str, Any] = (
            dict(self.state_provider()) if self.state_provider is not None else {}
        )
        if last_result is not None:
            self.last_status_result = {
                "action": last_result.action,
                "branch_id": last_result.branch_id,
                "decision": (
                    last_result.decision.value
                    if getattr(last_result, "decision", None) is not None
                    else None
                ),
                "stopped": last_result.stopped,
                "reason": last_result.reason,
            }
        if self.last_status_result is not None:
            payload["last_result"] = self.last_status_result
        if stopped_reason is not None:
            payload["stopped_reason"] = stopped_reason
        if self.current_status_progress is not None:
            payload["current_progress"] = self.current_status_progress
        try:
            self.status_reporter.write(payload)
        except Exception as exc:  # pragma: no cover - mirrors campaign best-effort behavior
            logger.debug("Failed to write status.json: %s", exc)
        return payload

    def record_protocol_progress(self, **payload: Any) -> Dict[str, Any]:
        """Merge a protocol progress update and refresh ``status.json``."""
        progress = dict(self.current_status_progress or {})
        progress.update(payload)
        progress["last_progress_at"] = datetime.now().isoformat()
        self.current_status_progress = progress
        self.write_status()
        return progress

    def attach_final_evidence_refs(self, refs: Mapping[str, Any]) -> None:
        """Store future final quality harness refs without touching step schema."""
        self.final_evidence_refs.update(dict(refs))

    def build_step_lineage_event(
        self,
        *,
        branch: Branch,
        hypothesis: HypothesisProposal,
        patch: PatchProposal | None,
        contract_result: ContractResult,
        verification_result: VerificationResult,
        canary_result: CanaryResult,
        protocol_result: ProtocolResult | None,
        decision: Decision,
        champion: ChampionState,
        hypothesis_id: str = "",
        decision_reason_codes: Iterable[str] | None = None,
        event_id: str | None = None,
    ) -> Dict[str, Any]:
        """Build the experiment event payload currently written to lineage."""
        stats = protocol_result.stats if protocol_result else None
        runtime_stats = _extract_protocol_runtime_stats(protocol_result)
        evidence_metadata = {
            "branch_state": branch.state.value,
            "branch_base_champion_id": branch.base_champion_id,
            "branch_weight_revision": getattr(branch, "weight_revision", 0),
            "current_champion_version": champion.version,
            "current_champion_weight_revision": getattr(champion, "weight_revision", 0),
            "protocol_raw_metrics_ref": (
                protocol_result.raw_metrics_ref if protocol_result else ""
            ),
            "metrics_refs": {
                "protocol_raw_metrics_ref": (
                    protocol_result.raw_metrics_ref if protocol_result else ""
                ),
            },
            "verification_checks": _serialize_verification_checks(verification_result),
            "runtime_guard": _extract_runtime_guard_evidence(verification_result),
            "runtime_stats": runtime_stats,
            "decision_reason_codes": list(decision_reason_codes or ()),
        }
        event = {
            "campaign_id": self.campaign_id,
            "branch_id": branch.branch_id,
            "timestamp": datetime.now().isoformat(),
            "hypothesis_id": hypothesis_id,
            "code_hash": branch.current_code_hash or "",
            "patch_action": patch.action if patch else "",
            "patch_file": patch.file_path if patch else "",
            "hypothesis_text": (hypothesis.hypothesis_text or "")[:500],
            "contract_passed": str(contract_result.passed),
            "verification_passed": str(verification_result.passed),
            "contract_result": "passed" if contract_result.passed else "failed",
            "verification_result": "passed" if verification_result.passed else "failed",
            "canary_result": "passed" if canary_result.passed else "failed",
            "stage": protocol_result.stage.value if protocol_result else "",
            "case_ids": json.dumps(list(protocol_result.case_ids)) if protocol_result else "[]",
            "seed_set": json.dumps(list(protocol_result.seed_set)) if protocol_result else "[]",
            "raw_metrics_ref": protocol_result.raw_metrics_ref if protocol_result else "",
            "screening_n_cases": stats.n_cases if stats else 0,
            "screening_win_rate": stats.win_rate if stats else None,
            "screening_median_delta": stats.median_delta if stats else None,
            "screening_ci_low": stats.ci_low if stats else None,
            "screening_ci_high": stats.ci_high if stats else None,
            "decision_features_json": json.dumps(evidence_metadata),
            "decision": decision.value,
            "model_id": self.model_id,
            "protocol_version": self.protocol_version,
        }
        if event_id:
            event["event_id"] = event_id
        return event

    def build_decision_lineage_payload(
        self,
        *,
        branch: Branch,
        protocol_result: ProtocolResult | None,
        contract_result: ContractResult,
        verification_result: VerificationResult,
        canary_result: CanaryResult,
        decision: Decision,
        decision_reason_codes: Iterable[str] | None = None,
    ) -> Dict[str, str]:
        """Build the append-only decision payload for LineageRegistry.record_decision."""
        stats = protocol_result.stats if protocol_result else None
        runtime_stats = _extract_protocol_runtime_stats(protocol_result)
        features_json = json.dumps(
            {
                "branch_id": branch.branch_id,
                "stage": protocol_result.stage.value if protocol_result else "",
                "contract_passed": contract_result.passed,
                "verification_passed": verification_result.passed,
                "canary_passed": canary_result.passed,
                "win_rate": stats.win_rate if stats else None,
                "median_delta": stats.median_delta if stats else None,
                "retry_count": branch.retry_count,
                "failure_codes": branch.failure_codes,
                "runtime_guard": _extract_runtime_guard_evidence(verification_result),
                "runtime_stats": runtime_stats,
            }
        )
        return {
            "branch_id": branch.branch_id,
            "features_json": features_json,
            "decision": decision.value,
            "reason": json.dumps(list(decision_reason_codes or ())),
        }

    def record_step_lineage(
        self,
        *,
        branch: Branch,
        hypothesis: HypothesisProposal,
        patch: PatchProposal | None,
        contract_result: ContractResult,
        verification_result: VerificationResult,
        canary_result: CanaryResult,
        protocol_result: ProtocolResult | None,
        decision: Decision,
        champion: ChampionState,
        hypothesis_id: str = "",
        decision_reason_codes: Iterable[str] | None = None,
        event_id: str | None = None,
    ) -> Dict[str, Any]:
        """Write experiment + decision lineage rows where a registry is configured."""
        event = self.build_step_lineage_event(
            branch=branch,
            hypothesis=hypothesis,
            patch=patch,
            contract_result=contract_result,
            verification_result=verification_result,
            canary_result=canary_result,
            protocol_result=protocol_result,
            decision=decision,
            champion=champion,
            hypothesis_id=hypothesis_id,
            decision_reason_codes=decision_reason_codes,
            event_id=event_id,
        )
        if self.registry is not None:
            try:
                self.registry.record_event(event)
            except Exception as exc:  # pragma: no cover - mirrors campaign best-effort behavior
                logger.debug("registry.record_event failed: %s", exc)
            decision_payload = self.build_decision_lineage_payload(
                branch=branch,
                protocol_result=protocol_result,
                contract_result=contract_result,
                verification_result=verification_result,
                canary_result=canary_result,
                decision=decision,
                decision_reason_codes=decision_reason_codes,
            )
            try:
                self.registry.record_decision(**decision_payload)
            except Exception as exc:  # pragma: no cover
                logger.debug("registry.record_decision failed: %s", exc)
        return event

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
        total_tokens = 0
        cache_read_tokens = 0
        cache_create_tokens = 0
        for step in steps:
            cs = step.cache_stats or {}
            total_tokens += cs.get("total", 0)
            cache_read_tokens += cs.get("cache_read", 0)
            cache_create_tokens += cs.get("cache_create", 0)
        cache_hit_rate = (
            round(cache_read_tokens / total_tokens, 4) if total_tokens > 0 else 0.0
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
        effective_stopped_reason = (
            "api_balance_exhausted"
            if balance_exhausted
            else ("circuit_breaker" if circuit_breaker_tripped else stopped_reason)
        )
        summary: Dict[str, Any] = {
            "campaign_id": self.campaign_id,
            "total_rounds": round_num,
            "champion_version": champion.version,
            "champion_weight_revision": getattr(champion, "weight_revision", 0),
            "stopped_reason": effective_stopped_reason,
            "cache_stats": {
                "total_tokens": total_tokens,
                "cache_read_tokens": cache_read_tokens,
                "cache_create_tokens": cache_create_tokens,
                "cache_hit_rate": cache_hit_rate,
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
        if frozen_budget is not None:
            summary["frozen_budget"] = dict(frozen_budget)
        refs = dict(self.final_evidence_refs)
        if final_evidence_refs:
            refs.update(dict(final_evidence_refs))
        readiness = validate_formal_readiness(refs)
        summary["formal_readiness"] = {
            "formal_ready": readiness.formal_ready,
            "missing": list(readiness.missing),
        }
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

    @staticmethod
    def _build_summary_step(step: StepRecord) -> Dict[str, Any]:
        decision_reason_codes = list(step.decision_reason_codes or ())
        step_data: Dict[str, Any] = {
            "round": step.round_num,
            "branch_id": step.branch_id,
            "decision": step.decision.value if step.decision is not None else None,
            "decision_reason_codes": decision_reason_codes,
            "contract_passed": step.contract_passed,
            "verification_passed": step.verification_passed,
            "failure_stage": step.failure_stage,
            "failure_detail": step.failure_detail,
            "verification_detail": step.verification_detail,
            "code_archive_ref": step.code_archive_ref,
            "cache_stats": step.cache_stats,
            "hypothesis": {
                "text": (step.hypothesis.hypothesis_text or "")[:200],
                "action": step.hypothesis.action,
                "change_locus": step.hypothesis.change_locus,
                "target_file": step.hypothesis.target_file,
            },
        }
        if step.protocol_result and step.protocol_result.stats:
            stats = step.protocol_result.stats
            pr = step.protocol_result
            protocol_reason_codes = list(pr.reason_codes)
            effective_reason_codes = decision_reason_codes or protocol_reason_codes
            step_data["protocol_result"] = {
                "stage": pr.stage.value if hasattr(pr.stage, "value") else str(pr.stage),
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
                "effective_reason_codes": effective_reason_codes,
                "effective_reason_source": (
                    "decision_engine" if decision_reason_codes else "protocol_gate"
                ),
                "raw_metrics_ref": pr.raw_metrics_ref,
                "case_ids": list(pr.case_ids),
                "seed_set": list(pr.seed_set),
            }
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
