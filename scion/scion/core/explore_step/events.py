"""Lineage/event helpers for explore-step execution."""
from __future__ import annotations

from scion.core.execution_outcome import ExecutionOutcome, ExecutionOutcomeRecord
from scion.core.models import ContractResult, PatchProposal

class ExploreStepEventMixin:
    def _record_contract_failure(
        self,
        result: ContractResult,
        *,
        stage: str,
        patch: PatchProposal | None = None,
    ) -> ExecutionOutcomeRecord:
        reason_code = (
            "HYPOTHESIS_CONTRACT_REJECTED"
            if stage == "hypothesis_contract"
            else "PATCH_CONTRACT_REJECTED"
        )
        checks = [
            {
                "name": check.name,
                "passed": check.passed,
                "severity": check.severity,
                "detail": check.detail,
                "elapsed_ms": check.elapsed_ms,
                "metadata": dict(check.metadata or {}),
            }
            for check in result.checks
        ]
        detail = result.failure_reason or ""
        provenance = {
            "stage": stage,
            "contract_checks": checks,
        }
        if patch is not None:
            provenance["patch"] = {
                "action": patch.action,
                "files": [change.file_path for change in patch.iter_file_changes()],
            }
        record = ExecutionOutcomeRecord(
            outcome=ExecutionOutcome.RESEARCH_REJECTED,
            reason_code=reason_code,
            detail=detail,
            provenance=provenance,
        )
        return record
