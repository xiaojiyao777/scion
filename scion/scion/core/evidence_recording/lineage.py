"""Lineage payload builders for campaign evidence recording."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any

from scion.contract.result_payload import diagnostic_checks
from scion.core.execution_outcome import ExecutionOutcome, ExecutionOutcomeRecord
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
    patch_file_changes,
)
from scion.core.public_refs import public_artifact_ref, public_case_ref
from scion.core.selected_hypothesis_basis import (
    canonical_selected_hypothesis_research_basis_json,
)

from .artifact_refs import _screening_rate_fields

logger = logging.getLogger(__name__)


class LineageRecorderMixin:
    def build_step_lineage_event(
        self,
        *,
        branch: Branch,
        code_hash: str,
        hypothesis: HypothesisProposal,
        patch: PatchProposal | None,
        contract_result: ContractResult | None,
        verification_result: VerificationResult | None,
        canary_result: CanaryResult,
        protocol_result: ProtocolResult | None,
        decision: Decision,
        champion: ChampionState,
        decision_reason_codes: Iterable[str] | None = None,
        base_champion_version: int,
        base_source_ref: str,
        changed_files: Iterable[str],
        event_id: str | None = None,
    ) -> dict[str, Any]:
        """Build the experiment event payload currently written to lineage."""
        stats = protocol_result.stats if protocol_result else None
        raw_metrics_internal_ref = (
            protocol_result.raw_metrics_ref if protocol_result else ""
        )
        raw_metrics_ref = (
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
        protocol_reason_codes = tuple(
            protocol_result.reason_codes if protocol_result else ()
        )
        reason_codes = tuple(
            dict.fromkeys((*tuple(decision_reason_codes or ()), *protocol_reason_codes))
        )
        changed_file_values = tuple(dict.fromkeys(changed_files))
        if type(base_champion_version) is not int or base_champion_version < 0:
            raise ValueError("lineage base_champion_version is invalid")
        if not isinstance(base_source_ref, str) or not base_source_ref.strip():
            raise ValueError("lineage base_source_ref is required")
        patch_files = (
            tuple(change.file_path for change in patch_file_changes(patch))
            if patch is not None
            else ()
        )
        if not set(patch_files).issubset(changed_file_values):
            raise ValueError("lineage changed_files omit a patch file")
        event_stage = (
            protocol_result.stage.value if protocol_result is not None else "canary"
        )
        event = {
            "campaign_id": self.campaign_id,
            "branch_id": branch.branch_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "code_hash": code_hash,
            "base_champion_version": base_champion_version,
            "base_source_ref": base_source_ref,
            "changed_files_json": json.dumps(list(changed_file_values)),
            "selected_hypothesis_research_basis_json": (
                canonical_selected_hypothesis_research_basis_json(
                    branch.selected_hypothesis_research_basis
                )
            ),
            "patch_action": patch.action if patch else "",
            "patch_file": patch.file_path if patch else "",
            "hypothesis_text": hypothesis.hypothesis_text or "",
            "contract_diagnostics_json": json.dumps(
                list(diagnostic_checks(contract_result)) if contract_result else [],
                sort_keys=True,
            ),
            "contract_result": (
                "passed"
                if contract_result is not None and contract_result.passed
                else "failed"
                if contract_result is not None
                else "not_run"
            ),
            "verification_result": (
                "passed"
                if verification_result is not None and verification_result.passed
                else "failed"
                if verification_result is not None
                else "not_run"
            ),
            "canary_result": "passed" if canary_result.passed else "failed",
            "stage": event_stage,
            "case_ids": json.dumps(public_case_ids) if protocol_result else "[]",
            "seed_set": json.dumps(list(protocol_result.seed_set))
            if protocol_result
            else "[]",
            "raw_metrics_ref": raw_metrics_ref,
            "screening_n_cases": stats.n_cases if stats else 0,
            "screening_median_delta": stats.median_delta if stats else None,
            "screening_ci_low": stats.ci_low if stats else None,
            "screening_ci_high": stats.ci_high if stats else None,
            "decision": decision.value,
            "decision_reason": json.dumps(list(reason_codes)),
            "model_id": self.model_id,
            "protocol_version": self.protocol_version,
            "execution_outcome": ExecutionOutcome.EVALUATED.value,
            "execution_outcome_reason_code": "EVALUATION_COMPLETED",
            "execution_outcome_detail": "",
            "execution_outcome_provenance_json": json.dumps(
                {"stage": event_stage},
                sort_keys=True,
            ),
        }
        event.update(_screening_rate_fields(protocol_result))
        if event_id:
            event["event_id"] = event_id
        return event

    def record_step_lineage(
        self,
        *,
        branch: Branch,
        code_hash: str,
        hypothesis: HypothesisProposal,
        patch: PatchProposal | None,
        contract_result: ContractResult | None,
        verification_result: VerificationResult | None,
        canary_result: CanaryResult,
        protocol_result: ProtocolResult | None,
        decision: Decision,
        champion: ChampionState,
        decision_reason_codes: Iterable[str] | None = None,
        base_champion_version: int,
        base_source_ref: str,
        changed_files: Iterable[str],
        event_id: str | None = None,
        strict: bool = False,
    ) -> str | None:
        """Append the single ordinary event for this completed experiment."""
        event = self.build_step_lineage_event(
            branch=branch,
            code_hash=code_hash,
            hypothesis=hypothesis,
            patch=patch,
            contract_result=contract_result,
            verification_result=verification_result,
            canary_result=canary_result,
            protocol_result=protocol_result,
            decision=decision,
            champion=champion,
            decision_reason_codes=decision_reason_codes,
            base_champion_version=base_champion_version,
            base_source_ref=base_source_ref,
            changed_files=changed_files,
            event_id=event_id,
        )
        if self.registry is None:
            return None

        try:
            typed_writer = getattr(self.registry, "record_execution_outcome", None)
            if callable(typed_writer):
                protected = {
                    "event_id",
                    "timestamp",
                    "event_kind",
                    "campaign_id",
                    "branch_id",
                    "stage",
                    "execution_outcome",
                    "execution_outcome_reason_code",
                    "execution_outcome_detail",
                    "execution_outcome_provenance_json",
                    "decision",
                    "decision_reason",
                }
                extra_fields = {
                    key: value for key, value in event.items() if key not in protected
                }
                outcome = ExecutionOutcomeRecord.from_primitive(
                    {
                        "outcome": event["execution_outcome"],
                        "reason_code": event["execution_outcome_reason_code"],
                        "detail": event["execution_outcome_detail"],
                        "provenance": json.loads(
                            event["execution_outcome_provenance_json"]
                        ),
                    }
                )
                return typed_writer(
                    campaign_id=event["campaign_id"],
                    branch_id=event["branch_id"],
                    record=outcome,
                    event_kind=event.get("event_kind", "experiment"),
                    stage=event["stage"],
                    decision=event["decision"],
                    decision_reason=event["decision_reason"],
                    extra_fields=extra_fields,
                    event_id=event.get("event_id"),
                    timestamp=event["timestamp"],
                )
            return self.registry.record_event(event)
        except (
            Exception
        ) as exc:  # pragma: no cover - mirrors campaign best-effort behavior
            if strict:
                raise
            logger.debug("registry.record_event failed: %s", exc)
            return None
