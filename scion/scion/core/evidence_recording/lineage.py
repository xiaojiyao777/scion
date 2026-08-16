"""Lineage payload builders for campaign evidence recording."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, Iterable

from scion.contract.result_payload import diagnostic_checks
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
        event_id: str | None = None,
    ) -> Dict[str, Any]:
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
        del champion
        event = {
            "campaign_id": self.campaign_id,
            "branch_id": branch.branch_id,
            "timestamp": datetime.now().isoformat(),
            "code_hash": code_hash,
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
            "stage": protocol_result.stage.value if protocol_result else "",
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
            event_id=event_id,
        )
        if self.registry is None:
            return None

        try:
            return self.registry.record_event(event)
        except (
            Exception
        ) as exc:  # pragma: no cover - mirrors campaign best-effort behavior
            if strict:
                raise
            logger.debug("registry.record_event failed: %s", exc)
            return None
