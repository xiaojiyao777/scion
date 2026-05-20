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
from scion.core.public_refs import (
    public_artifact_ref,
    public_case_ref,
    redact_public_refs,
)
from scion.core.status_reporter import (
    API_BALANCE_EXHAUSTED_STOP_REASON,
    PROVIDER_ERROR_CATEGORY_BALANCE_EXHAUSTED,
    StatusReporter,
    is_provider_balance_exhausted_detail,
    normalize_status_payload,
    normalize_stopped_reason,
)
from scion.evidence.final_evidence_refs import (
    FINAL_EVIDENCE_REASON_NORMAL_COMPLETION,
    FINAL_EVIDENCE_REASON_PENDING_EXTERNAL,
    FINAL_EVIDENCE_STATUS_PENDING_EXTERNAL,
    build_final_evidence_closure_refs,
)
from scion.evidence.formal_readiness import validate_formal_readiness

logger = logging.getLogger(__name__)


StateProvider = Callable[[], Mapping[str, Any]]

_NON_FORMAL_FINAL_EVIDENCE_STOP_REASONS = {"max_rounds_exhausted"}
_DEFAULT_NON_FORMAL_FINAL_EVIDENCE_REASON = (
    "campaign ended normally without an attached formal final evidence package; "
    "recording a non-formal final evidence closure"
)
_DEFAULT_PENDING_FINAL_EVIDENCE_REASON = (
    "final evidence package was not attached; post-campaign final evaluation "
    "is still required for formal readiness"
)


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


def _stage_value(stage: Any) -> str:
    return str(getattr(stage, "value", stage) or "")


def _screening_pair_counts(protocol_result: ProtocolResult | None) -> Dict[str, Any]:
    if protocol_result is None or _stage_value(protocol_result.stage) != "screening":
        return {}
    wins = losses = ties = 0
    for feedback in protocol_result.pair_feedback or ():
        comparison = str(getattr(feedback, "comparison", "") or "")
        if comparison == "win":
            wins += 1
        elif comparison == "loss":
            losses += 1
        else:
            ties += 1
    total = wins + losses + ties
    return {
        "screening_pair_wins": wins,
        "screening_pair_losses": losses,
        "screening_pair_ties": ties,
        "screening_pair_total": total,
        "screening_pair_win_rate": wins / total if total else 0.0,
    }


def _screening_rate_fields(
    protocol_result: ProtocolResult | None,
) -> Dict[str, Any]:
    if protocol_result is None or _stage_value(protocol_result.stage) != "screening":
        return {}
    stats = protocol_result.stats
    return {
        "screening_case_wins": stats.wins,
        "screening_case_losses": stats.losses,
        "screening_case_ties": stats.ties,
        "screening_case_win_rate": stats.win_rate,
        "screening_gate_win_rate": stats.win_rate,
        "screening_win_rate": stats.win_rate,
        "screening_win_rate_scope": "case_level_gate",
        **_screening_pair_counts(protocol_result),
    }


def _contract_not_run_reason(step: StepRecord) -> str | None:
    if step.patch is not None:
        return None
    if step.failure_stage == "agent_quality_blocked":
        return "proposal_only_agent_quality_blocked"
    if step.failure_stage == "proposal":
        return "proposal_generation_failed"
    if step.failure_stage == "code_generation":
        return "patch_not_generated"
    return None


def _primary_failure_attribution(step: StepRecord) -> dict[str, Any] | None:
    ref = step.proposal_session_ref
    if isinstance(ref, Mapping):
        session_observation = _proposal_session_failure_observation(ref)
        if (
            session_observation
            and (
                str(session_observation.get("stage") or "")
                == "agent_quality_blocked"
                or str(session_observation.get("category") or "")
                == "llm_transient_api_error"
            )
        ):
            return _drop_empty_summary_items(
                {
                    key: value
                    for key, value in session_observation.items()
                    if key != "source"
                }
            )
    if not step.failure_stage and not step.failure_detail:
        return None
    stage = step.failure_stage or "unknown"
    reason = step.failure_detail or stage
    return _drop_empty_summary_items(
        {
            "stage": stage,
            "reason": reason,
            "category": _failure_category_for_stage(stage, reason),
        }
    )


def _secondary_failure_observations(
    step: StepRecord,
    primary: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    ref = step.proposal_session_ref
    if isinstance(ref, Mapping):
        session_observation = _proposal_session_failure_observation(ref)
        if session_observation and not _same_failure_observation(
            session_observation,
            primary,
        ):
            observations.append(session_observation)
    return observations


def _proposal_session_failure_observation(
    ref: Mapping[str, Any],
) -> dict[str, Any] | None:
    primary = ref.get("primary_failure")
    if isinstance(primary, Mapping):
        observation = dict(primary)
        observation.setdefault("source", "proposal_session")
        return _drop_empty_summary_items(observation)

    failure_code = str(ref.get("failure_code") or "").strip()
    failure_category = str(ref.get("failure_category") or "").strip()
    block_reason = str(ref.get("agent_block_reason") or "").strip()
    if not (failure_code or failure_category or block_reason):
        return None
    return _drop_empty_summary_items(
        {
            "source": "proposal_session",
            "stage": block_reason or str(ref.get("termination_reason") or ""),
            "reason": failure_code or failure_category,
            "category": failure_category,
            "code": failure_code,
        }
    )


def _same_failure_observation(
    observation: Mapping[str, Any],
    primary: Mapping[str, Any] | None,
) -> bool:
    if not primary:
        return False
    primary_stage = str(primary.get("stage") or "")
    primary_reason = str(primary.get("reason") or "")
    primary_category = str(primary.get("category") or "")
    observation_stage = str(observation.get("stage") or "")
    observation_reason = str(observation.get("reason") or "")
    observation_category = str(observation.get("category") or "")
    return bool(
        primary_stage
        and primary_stage == observation_stage
        and (
            (primary_reason and primary_reason == observation_reason)
            or (primary_category and primary_category == observation_category)
        )
    )


def _failure_category_for_stage(stage: str, reason: str) -> str:
    if stage in {"hypothesis_contract", "patch_contract"}:
        return "contract"
    if stage == "agent_quality_blocked":
        return "agent_grounding_failure"
    if stage in {"proposal", "code_generation"}:
        return "proposal"
    if stage == "verification":
        return "verification"
    if stage == "workspace":
        return "workspace"
    if "contract" in reason:
        return "contract"
    return stage or "unknown"


def _drop_empty_summary_items(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        str(key): value
        for key, value in payload.items()
        if value not in (None, "", [], {})
    }


def _default_final_evidence_closure_refs(
    stopped_reason: str | None,
) -> dict[str, Any]:
    if stopped_reason in _NON_FORMAL_FINAL_EVIDENCE_STOP_REASONS:
        return build_final_evidence_closure_refs(
            reason=_DEFAULT_NON_FORMAL_FINAL_EVIDENCE_REASON,
            reason_code=FINAL_EVIDENCE_REASON_NORMAL_COMPLETION,
            required_for_formal_readiness=False,
        )
    return build_final_evidence_closure_refs(
        reason=_DEFAULT_PENDING_FINAL_EVIDENCE_REASON,
        reason_code=FINAL_EVIDENCE_REASON_PENDING_EXTERNAL,
        status=FINAL_EVIDENCE_STATUS_PENDING_EXTERNAL,
        required_for_formal_readiness=True,
    )


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
                "counts_toward_max_rounds": getattr(
                    last_result,
                    "counts_toward_max_rounds",
                    True,
                ),
            }
        if self.last_status_result is not None:
            payload["last_result"] = self.last_status_result
        if stopped_reason is not None:
            payload["stopped_reason"] = normalize_stopped_reason(
                stopped_reason,
                balance_exhausted=bool(payload.get("balance_exhausted")),
                circuit_breaker_tripped=bool(payload.get("circuit_breaker_tripped")),
            )
        if self.current_status_progress is not None:
            payload["current_progress"] = self.current_status_progress
        payload = normalize_status_payload(payload)
        public_payload = redact_public_refs(payload, base_dir=self.campaign_dir)
        try:
            self.status_reporter.write(public_payload)
        except Exception as exc:  # pragma: no cover - mirrors campaign best-effort behavior
            logger.debug("Failed to write status.json: %s", exc)
        return public_payload

    def record_protocol_progress(self, **payload: Any) -> Dict[str, Any]:
        """Merge a protocol progress update and refresh ``status.json``."""
        progress = dict(self.current_status_progress or {})
        progress.update(payload)
        if progress.get("raw_metrics_ref"):
            progress["raw_metrics_ref_scope"] = "public_artifact_ref"
            progress["raw_metrics_internal_only"] = True
        progress["last_progress_at"] = datetime.now().isoformat()
        progress = redact_public_refs(progress, base_dir=self.campaign_dir)
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
        raw_metrics_internal_ref = (
            protocol_result.raw_metrics_ref if protocol_result else ""
        )
        raw_metrics_public_ref = (
            public_artifact_ref(
                raw_metrics_internal_ref,
                base_dir=self.campaign_dir,
                kind="metrics",
            )
            or ""
        )
        public_case_ids = [
            public_case_ref(case, base_dir=self.campaign_dir)
            for case in (protocol_result.case_ids if protocol_result else ())
        ]
        public_case_ids = [case for case in public_case_ids if case is not None]
        internal_audit_payload = {
            "schema": "scion.internal_audit_refs.v1",
            "internal_only": True,
            "raw_metrics_ref": raw_metrics_public_ref,
            "raw_metrics_public_ref": raw_metrics_public_ref,
            "raw_metrics_ref_scope": "public_artifact_ref",
            "protocol_raw_metrics_ref": raw_metrics_public_ref,
            "protocol_raw_metrics_ref_scope": "public_artifact_ref",
            "raw_metrics_internal_only": True,
            "case_ids": public_case_ids,
            "metrics_refs": {
                "raw_metrics_ref": raw_metrics_public_ref,
                "raw_metrics_ref_scope": "public_artifact_ref",
                "protocol_raw_metrics_ref": raw_metrics_public_ref,
                "protocol_raw_metrics_ref_scope": "public_artifact_ref",
                "raw_metrics_internal_only": True,
            },
        }
        evidence_metadata = {
            "branch_state": branch.state.value,
            "branch_base_champion_id": branch.base_champion_id,
            "branch_weight_revision": getattr(branch, "weight_revision", 0),
            "current_champion_version": champion.version,
            "current_champion_weight_revision": getattr(champion, "weight_revision", 0),
            "protocol_raw_metrics_ref": raw_metrics_public_ref,
            "protocol_raw_metrics_ref_scope": "public_artifact_ref",
            "raw_metrics_public_ref": raw_metrics_public_ref,
            "raw_metrics_ref_scope": "public_artifact_ref",
            "raw_metrics_internal_only": True,
            "internal_audit_payload": "experiment_events.audit_payload_json",
            "metrics_refs": {
                "raw_metrics_ref": raw_metrics_public_ref,
                "raw_metrics_ref_scope": "public_artifact_ref",
                "protocol_raw_metrics_ref": raw_metrics_public_ref,
                "protocol_raw_metrics_ref_scope": "public_artifact_ref",
                "raw_metrics_internal_only": True,
                "audit_payload_stored_in": "experiment_events.audit_payload_json",
            },
            "selected_surface": (
                protocol_result.selected_surface if protocol_result else None
            ),
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
            "case_ids": json.dumps(public_case_ids) if protocol_result else "[]",
            "seed_set": json.dumps(list(protocol_result.seed_set)) if protocol_result else "[]",
            "raw_metrics_ref": raw_metrics_public_ref,
            "screening_n_cases": stats.n_cases if stats else 0,
            "screening_win_rate": stats.win_rate if stats else None,
            "screening_median_delta": stats.median_delta if stats else None,
            "screening_ci_low": stats.ci_low if stats else None,
            "screening_ci_high": stats.ci_high if stats else None,
            "decision_features_json": json.dumps(evidence_metadata),
            "decision": decision.value,
            "model_id": self.model_id,
            "protocol_version": self.protocol_version,
            "audit_payload_json": json.dumps(internal_audit_payload, sort_keys=True),
        }
        event.update(_screening_rate_fields(protocol_result))
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
        screened_experiments = sum(
            1 for step in steps if step.protocol_result is not None
        )
        state_screened_experiments: Any | None = None
        if self.state_provider is not None:
            try:
                state_for_counts = dict(self.state_provider())
                state_screened_experiments = state_for_counts.get(
                    "screened_experiments",
                    state_for_counts.get("n_experiments"),
                )
            except Exception as exc:  # pragma: no cover - summary is best-effort
                logger.debug("state snapshot for campaign_summary counts failed: %s", exc)
        if state_screened_experiments is not None:
            screened_experiments = int(state_screened_experiments)

        summary: Dict[str, Any] = {
            "campaign_id": self.campaign_id,
            "total_rounds": round_num,
            "proposal_attempts": round_num,
            "screened_experiments": screened_experiments,
            "champion_version": champion.version,
            "champion_weight_revision": getattr(champion, "weight_revision", 0),
            "stopped_reason": effective_stopped_reason,
            "balance_exhausted": inferred_balance_exhausted,
            "circuit_breaker_tripped": circuit_breaker_tripped,
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
        if effective_stopped_reason == API_BALANCE_EXHAUSTED_STOP_REASON:
            summary["stop_category"] = "provider_error"
            summary["provider_error"] = {
                "category": PROVIDER_ERROR_CATEGORY_BALANCE_EXHAUSTED,
            }
        if frozen_budget is not None:
            summary["frozen_budget"] = dict(frozen_budget)
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
            }
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
