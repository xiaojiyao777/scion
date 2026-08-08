"""Lineage payload builders for campaign evidence recording."""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, Iterable

from scion.core.decision_features_serialization import decision_features_to_json
from scion.core.models import (
    Branch,
    CanaryResult,
    ChampionState,
    ContractResult,
    Decision,
    DecisionFeatures,
    HypothesisProposal,
    PatchProposal,
    ProtocolResult,
    VerificationResult,
)
from scion.core.public_refs import public_artifact_ref, public_case_ref
from scion.core.reason_code_groups import classify_reason_codes
from scion.core.telemetry_validation import (
    screened_experiment_effective,
)
from scion.contract.result_payload import diagnostic_checks

from .artifact_refs import (
    _extract_protocol_runtime_stats,
    _extract_runtime_guard_evidence,
    _screening_rate_fields,
    _serialize_verification_checks,
)
logger = logging.getLogger(__name__)

_LINEAGE_DEGRADED_WARNING = "lineage_registry_write_degraded"


def _lineage_error(exc: Exception) -> Dict[str, Any]:
    message = " ".join(str(exc).split())
    return {
        "type": type(exc).__name__,
        "message": message,
    }


def _new_lineage_outcome(
    *,
    branch_id: str,
    hypothesis_id: str,
    decision: Decision,
    event_id: str | None,
    strict: bool,
    registry_configured: bool,
) -> Dict[str, Any]:
    return {
        "schema_version": "scion.lineage_write_outcome.v1",
        "branch_id": branch_id,
        "hypothesis_id": hypothesis_id,
        "decision": decision.value,
        "event_id": event_id,
        "strict": strict,
        "registry_configured": registry_configured,
        "event_recorded": None,
        "decision_recorded": None,
        "errors": [],
        "status": "not_configured" if not registry_configured else "pending",
    }


def _finalize_lineage_outcome(outcome: Dict[str, Any]) -> Dict[str, Any]:
    if not outcome.get("registry_configured"):
        outcome["status"] = "not_configured"
    elif outcome.get("errors"):
        outcome["status"] = "degraded"
    elif (
        outcome.get("event_recorded") is True
        and outcome.get("decision_recorded") is True
    ):
        outcome["status"] = "complete"
    else:
        outcome["status"] = "incomplete"
    return outcome


def lineage_integrity_snapshot(
    *,
    outcomes: Iterable[Dict[str, Any]],
    registry_configured: bool,
    expected_step_count: int | None = None,
    source: str = "recorder_accumulator",
) -> Dict[str, Any]:
    outcome_list = [dict(outcome) for outcome in outcomes]
    degraded = [
        outcome for outcome in outcome_list if outcome.get("status") == "degraded"
    ]
    event_failures = sum(
        1
        for outcome in degraded
        for error in outcome.get("errors", ())
        if isinstance(error, dict) and error.get("operation") == "record_event"
    )
    decision_failures = sum(
        1
        for outcome in degraded
        for error in outcome.get("errors", ())
        if isinstance(error, dict) and error.get("operation") == "record_decision"
    )
    status = "not_configured"
    if registry_configured:
        status = "degraded" if degraded else "complete"
    snapshot: Dict[str, Any] = {
        "schema_version": "scion.lineage_integrity.v1",
        "status": status,
        "degraded": bool(degraded),
        "registry_configured": registry_configured,
        "source": source,
        "recorded_outcome_count": len(outcome_list),
        "degraded_outcome_count": len(degraded),
        "event_recording_failures": event_failures,
        "decision_recording_failures": decision_failures,
        "warning": _LINEAGE_DEGRADED_WARNING if degraded else None,
        "degraded_outcomes": degraded,
    }
    if expected_step_count is not None:
        snapshot["expected_step_count"] = expected_step_count
    return snapshot


def apply_lineage_integrity_to_run_validity(
    payload: Dict[str, Any],
    integrity: Dict[str, Any],
) -> None:
    if integrity.get("status") != "degraded":
        return
    run_validity = payload.get("run_validity")
    if not isinstance(run_validity, dict):
        return
    run_validity["integrity_status"] = "degraded"
    warnings = run_validity.setdefault("warnings", [])
    if isinstance(warnings, list) and _LINEAGE_DEGRADED_WARNING not in warnings:
        warnings.append(_LINEAGE_DEGRADED_WARNING)


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
    def lineage_integrity_snapshot(
        self,
        *,
        expected_step_count: int | None = None,
        source: str = "recorder_accumulator",
    ) -> Dict[str, Any]:
        return lineage_integrity_snapshot(
            outcomes=getattr(self, "lineage_recording_outcomes", ()),
            registry_configured=self.registry is not None,
            expected_step_count=expected_step_count,
            source=source,
        )

    def _record_lineage_outcome(self, outcome: Dict[str, Any]) -> None:
        accumulator = getattr(self, "lineage_recording_outcomes", None)
        if isinstance(accumulator, list):
            accumulator.append(dict(outcome))

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
        decision_features: DecisionFeatures | None = None,
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
        protocol_reason_codes = (
            list(protocol_result.reason_codes) if protocol_result else []
        )
        reason_code_groups = classify_reason_codes(
            tuple(decision_reason_codes or ()) + tuple(protocol_reason_codes),
            protocol_reason_codes=protocol_reason_codes,
        )
        verification_checks = _serialize_verification_checks(
            verification_result,
            base_dir=self.campaign_dir,
        )
        runtime_guard = _extract_runtime_guard_evidence(verification_result)
        selected_surface = (
            (protocol_result.selected_surface if protocol_result else None)
            or hypothesis.change_locus
            or ""
        )
        internal_audit_payload = {
            "schema": "scion.internal_audit_refs.v2",
            "internal_only": True,
            "selected_surface": selected_surface,
            "verification_checks": verification_checks,
            "runtime_guard": runtime_guard,
        }
        evidence_metadata = {
            "branch_state": branch.state.value,
            "branch_base_champion_id": branch.base_champion_id,
            "branch_weight_revision": getattr(branch, "weight_revision", 0),
            "branch_code_status": getattr(branch, "branch_code_status", "clean"),
            "current_champion_version": champion.version,
            "current_champion_weight_revision": getattr(champion, "weight_revision", 0),
            "selected_surface": selected_surface,
            "runtime_stats": runtime_stats,
            "decision_reason_codes": list(decision_reason_codes or ()),
            "gate_observation_reason_codes": list(
                reason_code_groups.gate_observation_reason_codes
            ),
            "auxiliary_protocol_reason_codes": protocol_reason_codes,
            "screened_experiment_effective": screened_experiment_effective(
                protocol_result
            ),
        }
        evidence_metadata.update(_runtime_guard_decision_features(runtime_guard))
        internal_audit_payload["lineage_metadata"] = evidence_metadata
        decision_features_json = (
            decision_features_to_json(decision_features)
            if decision_features is not None
            else json.dumps(evidence_metadata, sort_keys=True)
        )
        event = {
            "campaign_id": self.campaign_id,
            "branch_id": branch.branch_id,
            "timestamp": datetime.now().isoformat(),
            "hypothesis_id": hypothesis_id,
            "code_hash": branch.current_code_hash or "",
            "patch_action": patch.action if patch else "",
            "patch_file": patch.file_path if patch else "",
            "hypothesis_text": hypothesis.hypothesis_text or "",
            "contract_passed": str(contract_result.passed),
            "contract_diagnostics_json": json.dumps(
                list(diagnostic_checks(contract_result)),
                sort_keys=True,
            ),
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
            "decision_features_json": decision_features_json,
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
        hypothesis_id: str = "",
        decision_reason_codes: Iterable[str] | None = None,
        decision_features: DecisionFeatures | None = None,
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
            "contract_diagnostics": list(diagnostic_checks(contract_result)),
            "verification_passed": verification_result.passed,
            "canary_passed": canary_result.passed,
            "win_rate": stats.win_rate if stats else None,
            "median_delta": stats.median_delta if stats else None,
            "failure_codes": branch.failure_codes,
            "branch_code_status": getattr(branch, "branch_code_status", "clean"),
            "runtime_stats": runtime_stats,
            "auxiliary_protocol_reason_codes": protocol_reason_codes,
            "gate_observation_reason_codes": list(
                reason_code_groups.gate_observation_reason_codes
            ),
            "screened_experiment_effective": screened_experiment_effective(
                protocol_result
            ),
        }
        features.update(
            _runtime_guard_decision_features(
                _extract_runtime_guard_evidence(verification_result)
            )
        )
        features_json = (
            decision_features_to_json(decision_features)
            if decision_features is not None
            else json.dumps(features, sort_keys=True)
        )
        return {
            "campaign_id": self.campaign_id,
            "branch_id": branch.branch_id,
            "hypothesis_id": hypothesis_id,
            "stage": protocol_result.stage.value if protocol_result else "",
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
        decision_features: DecisionFeatures | None = None,
        event_id: str | None = None,
        strict: bool = False,
    ) -> Dict[str, Any]:
        """Write experiment + decision lineage rows where a registry is configured."""
        outcome = _new_lineage_outcome(
            branch_id=branch.branch_id,
            hypothesis_id=hypothesis_id,
            decision=decision,
            event_id=event_id,
            strict=strict,
            registry_configured=self.registry is not None,
        )
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
            decision_features=decision_features,
            event_id=event_id,
        )
        if self.registry is None:
            outcome = _finalize_lineage_outcome(outcome)
            self._record_lineage_outcome(outcome)
            return outcome

        try:
            self.registry.record_event(event)
            outcome["event_recorded"] = True
        except Exception as exc:  # pragma: no cover - mirrors campaign best-effort behavior
            outcome["event_recorded"] = False
            outcome["errors"].append(
                {
                    "operation": "record_event",
                    **_lineage_error(exc),
                }
            )
            if strict:
                outcome = _finalize_lineage_outcome(outcome)
                self._record_lineage_outcome(outcome)
                raise
            logger.debug("registry.record_event failed: %s", exc)

        decision_payload = self.build_decision_lineage_payload(
            branch=branch,
            protocol_result=protocol_result,
            contract_result=contract_result,
            verification_result=verification_result,
            canary_result=canary_result,
            decision=decision,
            hypothesis_id=hypothesis_id,
            decision_reason_codes=decision_reason_codes,
            decision_features=decision_features,
        )
        try:
            self.registry.record_decision(**decision_payload)
            outcome["decision_recorded"] = True
        except Exception as exc:  # pragma: no cover
            outcome["decision_recorded"] = False
            outcome["errors"].append(
                {
                    "operation": "record_decision",
                    **_lineage_error(exc),
                }
            )
            outcome = _finalize_lineage_outcome(outcome)
            self._record_lineage_outcome(outcome)
            if strict:
                raise
            logger.debug("registry.record_decision failed: %s", exc)
            return outcome

        outcome = _finalize_lineage_outcome(outcome)
        self._record_lineage_outcome(outcome)
        return outcome

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
