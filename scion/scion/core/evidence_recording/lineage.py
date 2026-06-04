"""Lineage payload builders for campaign evidence recording."""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, Iterable

from scion.core.models import (
    Branch,
    CanaryResult,
    ChampionState,
    ContractResult,
    Decision,
    HypothesisProposal,
    PatchProposal,
    ProtocolResult,
    VerificationResult,
)
from scion.core.public_refs import public_artifact_ref, public_case_ref
from scion.core.reason_code_groups import classify_reason_codes
from scion.core.telemetry_validation import (
    formal_telemetry_guard_failed,
    screened_experiment_effective,
    telemetry_decision_details,
    telemetry_failure_categories,
    telemetry_validation_feedback,
)

from .artifact_refs import (
    _extract_protocol_runtime_stats,
    _extract_runtime_guard_evidence,
    _screening_rate_fields,
    _serialize_verification_checks,
)

logger = logging.getLogger(__name__)


def _runtime_guard_decision_features(
    runtime_guard: Dict[str, Any],
) -> Dict[str, Any]:
    """Return the non-text runtime guard subset allowed in decision features."""
    if not runtime_guard:
        return {}
    features: Dict[str, Any] = {}
    if "passed" in runtime_guard:
        features["runtime_guard_passed"] = bool(runtime_guard["passed"])
    if "elapsed_ms" in runtime_guard:
        features["runtime_guard_elapsed_ms"] = runtime_guard["elapsed_ms"]
    return features


class LineageRecorderMixin:
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
        telemetry_details = list(telemetry_decision_details(protocol_result))
        protocol_reason_codes = (
            list(protocol_result.reason_codes) if protocol_result else []
        )
        reason_code_groups = classify_reason_codes(
            tuple(decision_reason_codes or ()) + tuple(protocol_reason_codes),
            protocol_reason_codes=protocol_reason_codes,
        )
        verification_checks = _serialize_verification_checks(verification_result)
        runtime_guard = _extract_runtime_guard_evidence(verification_result)
        telemetry_feedback = telemetry_validation_feedback(protocol_result)
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
            "verification_checks": verification_checks,
            "runtime_guard": runtime_guard,
            "telemetry_failure_details": telemetry_details,
            "telemetry_validation_feedback": telemetry_feedback,
        }
        evidence_metadata = {
            "branch_state": branch.state.value,
            "branch_base_champion_id": branch.base_champion_id,
            "branch_weight_revision": getattr(branch, "weight_revision", 0),
            "branch_code_status": getattr(branch, "branch_code_status", "clean"),
            "last_screening_feedback_tier": getattr(
                branch,
                "last_screening_feedback_tier",
                None,
            ),
            "last_telemetry_outcome": getattr(branch, "last_telemetry_outcome", None),
            "branch_mechanism_ids": list(
                getattr(branch, "branch_mechanism_ids", ()) or ()
            ),
            "telemetry_repair_mechanism_ids": list(
                getattr(branch, "telemetry_repair_mechanism_ids", ()) or ()
            ),
            "telemetry_repair_attempts": dict(
                getattr(branch, "telemetry_repair_attempts", {}) or {}
            ),
            "current_champion_version": champion.version,
            "current_champion_weight_revision": getattr(champion, "weight_revision", 0),
            "selected_surface": (
                protocol_result.selected_surface if protocol_result else None
            ),
            "runtime_stats": runtime_stats,
            "decision_reason_codes": list(decision_reason_codes or ()),
            "gate_observation_reason_codes": list(
                reason_code_groups.gate_observation_reason_codes
            ),
            "lifecycle_action_reason_codes": list(
                reason_code_groups.lifecycle_action_reason_codes
            ),
            "auxiliary_protocol_reason_codes": protocol_reason_codes,
            "screened_experiment_effective": screened_experiment_effective(
                protocol_result
            ),
            "telemetry_guard_failed": formal_telemetry_guard_failed(protocol_result),
            "telemetry_failure_categories": list(
                telemetry_failure_categories(protocol_result)
            ),
        }
        evidence_metadata.update(_runtime_guard_decision_features(runtime_guard))
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
            "telemetry_guard_failed": int(
                formal_telemetry_guard_failed(protocol_result)
            ),
            "telemetry_failure_categories_json": json.dumps(
                list(telemetry_failure_categories(protocol_result))
            ),
            "telemetry_failure_details_json": json.dumps(telemetry_details),
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
        protocol_reason_codes = (
            list(protocol_result.reason_codes) if protocol_result else []
        )
        reason_code_groups = classify_reason_codes(
            tuple(decision_reason_codes or ()) + tuple(protocol_reason_codes),
            protocol_reason_codes=protocol_reason_codes,
        )
        features = {
            "branch_id": branch.branch_id,
            "stage": protocol_result.stage.value if protocol_result else "",
            "contract_passed": contract_result.passed,
            "verification_passed": verification_result.passed,
            "canary_passed": canary_result.passed,
            "win_rate": stats.win_rate if stats else None,
            "median_delta": stats.median_delta if stats else None,
            "retry_count": branch.retry_count,
            "failure_codes": branch.failure_codes,
            "branch_code_status": getattr(branch, "branch_code_status", "clean"),
            "last_screening_feedback_tier": getattr(
                branch,
                "last_screening_feedback_tier",
                None,
            ),
            "last_telemetry_outcome": getattr(
                branch,
                "last_telemetry_outcome",
                None,
            ),
            "branch_mechanism_ids": list(
                getattr(branch, "branch_mechanism_ids", ()) or ()
            ),
            "telemetry_repair_mechanism_ids": list(
                getattr(branch, "telemetry_repair_mechanism_ids", ()) or ()
            ),
            "telemetry_repair_attempts": dict(
                getattr(branch, "telemetry_repair_attempts", {}) or {}
            ),
            "runtime_stats": runtime_stats,
            "auxiliary_protocol_reason_codes": protocol_reason_codes,
            "gate_observation_reason_codes": list(
                reason_code_groups.gate_observation_reason_codes
            ),
            "lifecycle_action_reason_codes": list(
                reason_code_groups.lifecycle_action_reason_codes
            ),
            "screened_experiment_effective": screened_experiment_effective(
                protocol_result
            ),
            "telemetry_guard_failed": formal_telemetry_guard_failed(protocol_result),
            "telemetry_failure_categories": list(
                telemetry_failure_categories(protocol_result)
            ),
        }
        features.update(
            _runtime_guard_decision_features(
                _extract_runtime_guard_evidence(verification_result)
            )
        )
        features_json = json.dumps(features)
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

    def record_scheduler_result_lineage(
        self,
        *,
        result: Any,
        step: Any | None = None,
    ) -> None:
        """Append a replayable scheduler/result event when scheduler metadata exists."""
        slot = str(getattr(result, "scheduler_slot", "") or "")
        reason = str(getattr(result, "scheduler_reason", "") or "")
        if not (slot or reason) or self.registry is None:
            return
        branch_id = str(getattr(result, "branch_id", "") or "")
        decision = getattr(result, "decision", None)
        decision_value = (
            decision.value if getattr(decision, "value", None) is not None else decision
        )
        payload = {
            "schema": "scion.scheduler_result.v1",
            "scheduler_slot": slot,
            "scheduler_reason": reason,
            "scheduler_audit_metadata": dict(
                getattr(result, "scheduler_audit_metadata", None) or {}
            ),
            "result_action": str(getattr(result, "action", "") or ""),
            "result_reason": str(getattr(result, "reason", "") or ""),
            "branch_id": branch_id,
            "decision": decision_value,
            "counts_toward_max_rounds": bool(
                getattr(result, "counts_toward_max_rounds", True)
            ),
            "attempt_kind": str(getattr(result, "attempt_kind", "screening") or ""),
            "step_round": getattr(step, "round_num", None),
            "step_branch_id": getattr(step, "branch_id", None),
            "step_decision": (
                step.decision.value
                if getattr(getattr(step, "decision", None), "value", None) is not None
                else getattr(step, "decision", None)
            ),
        }
        for key in (
            "pre_finalizer_scheduler_action",
            "pre_finalizer_scheduler_slot",
            "pre_finalizer_scheduler_reason",
            "pre_finalizer_selected_branch_id",
            "post_finalizer_lifecycle_action",
            "post_finalizer_actual_branch_action",
            "post_finalizer_active_slot_release_reason",
            "post_finalizer_next_proposal_policy",
            "post_finalizer_counts_toward_active_slots",
        ):
            if key in payload["scheduler_audit_metadata"]:
                payload[key] = payload["scheduler_audit_metadata"][key]
        event = {
            "campaign_id": self.campaign_id,
            "branch_id": branch_id,
            "timestamp": datetime.now().isoformat(),
            "event_kind": "scheduler_result",
            "patch_action": payload["result_action"],
            "decision": decision_value,
            "scheduler_slot": slot,
            "scheduler_reason": reason,
            "decision_features_json": "",
            "audit_payload_json": json.dumps(payload, sort_keys=True),
        }
        hypothesis_id = getattr(step, "hypothesis_id", None)
        if hypothesis_id:
            event["hypothesis_id"] = hypothesis_id
        try:
            self.registry.record_event(event)
        except Exception as exc:  # pragma: no cover
            logger.debug("registry.record_event scheduler_result failed: %s", exc)
