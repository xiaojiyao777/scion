"""Decision finalization boundary for campaign branch steps."""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, replace
from typing import Any, Callable, Iterable, Mapping, MutableMapping, Optional, Protocol

from scion.core.branch import BranchController, StateTransitionError
from scion.core.decision_lifecycle_actions import (
    update_branch_screening_evidence_summary as _update_branch_screening_evidence_summary,
)
from scion.core.models import (
    Branch,
    BranchState,
    CanaryResult,
    ContractResult,
    Decision,
    FailureEvent,
    HypothesisProposal,
    HypothesisRecord,
    PatchProposal,
    ProtocolResult,
    VerificationResult,
)
from scion.core.promotion_service import PromotionCommitError, PromotionPlan
from scion.core.step_result import StepResult
from scion.core.screening_visibility import runtime_aggregate_exclusion_for_protocol
from scion.core.telemetry_validation import screened_experiment_effective
logger = logging.getLogger(__name__)


class HypothesisStoreLike(Protocol):
    def mark_status(self, hypothesis_id: str, status: str) -> None:
        ...


class BranchStoreLike(Protocol):
    def save(self, branch: Branch) -> None:
        ...


class LineageRecorder(Protocol):
    def __call__(
        self,
        branch: Branch,
        hypothesis: HypothesisProposal,
        patch: Optional[PatchProposal],
        contract_result: ContractResult,
        verification_result: VerificationResult,
        canary_result: CanaryResult,
        protocol_result: Optional[ProtocolResult],
        decision: Decision,
        hypothesis_id: str = "",
        decision_reason_codes: Optional[tuple[str, ...]] = None,
        event_id: Optional[str] = None,
        strict: bool = False,
    ) -> None:
        ...

FormalCandidateArtifactRecorder = Callable[..., Optional[str]]


@dataclass
class DecisionFinalizer:
    """Apply deterministic decision side effects after feature extraction."""

    branch_controller: BranchController
    branch_store: BranchStoreLike | None
    hypothesis_store: HypothesisStoreLike
    branch_workspaces: MutableMapping[str, str]
    branch_hypotheses: MutableMapping[str, HypothesisProposal]
    branch_patches: MutableMapping[str, PatchProposal]
    branch_current_hypothesis: MutableMapping[str, HypothesisRecord]
    prepare_promoted_champion: Callable[[Branch], PromotionPlan]
    require_promotable_branch: Callable[[Branch], None]
    commit_promote_plan: Callable[[PromotionPlan], None]
    handle_failure: Callable[..., None]
    record_step_lineage: LineageRecorder
    decision_reason_codes_for: Callable[
        [str, Optional[ProtocolResult]],
        Optional[tuple[str, ...]],
    ]
    discard_branch_workspace: Callable[[str], None]
    archive_workspace: Callable[[str, str], None]
    cleanup_workspace: Callable[[str], None]
    persist_branch_state: Callable[[str], None]
    record_formal_candidate_artifact: FormalCandidateArtifactRecorder | None = None
    decision_provenance_for: Callable[[str], dict[str, Any]] = lambda _branch_id: {}

    def apply(
        self,
        *,
        branch: Branch,
        decision: Decision,
        hypothesis: HypothesisProposal,
        h_record: HypothesisRecord,
        protocol_result: Optional[ProtocolResult],
        canary_result: CanaryResult,
        contract_result: ContractResult,
        verification_result: VerificationResult,
        action_label: str,
        decision_reason_codes: Optional[tuple[str, ...]] = None,
        proposal_attempt_ref: Mapping[str, Any] | None = None,
    ) -> StepResult:
        bid = branch.branch_id
        logger.info("Branch %s: decision=%s", bid, decision.value)
        effective_reason_codes = decision_reason_codes or self.decision_reason_codes_for(
            bid,
            protocol_result,
        )
        patch = self.branch_patches.get(bid)
        if decision == Decision.ABANDON:
            _sync_terminal_branch_evidence(
                branch,
                hypothesis=hypothesis,
                patch=patch,
                protocol_result=protocol_result,
                decision_reason_codes=effective_reason_codes,
            )
            self._record_formal_candidate_artifact(
                branch=branch,
                hypothesis=hypothesis,
                h_record=h_record,
                patch=patch,
                protocol_result=protocol_result,
                canary_result=canary_result,
                contract_result=contract_result,
                verification_result=verification_result,
                decision=decision,
                decision_reason_codes=effective_reason_codes,
                proposal_attempt_ref=proposal_attempt_ref,
            )

        promote_plan: PromotionPlan | None = None
        if decision == Decision.PROMOTE:
            promote_plan = self._prepare_promotion(
                branch=branch,
                action_label=action_label,
            )
            if isinstance(promote_plan, StepResult):
                return _with_protocol_accounting(promote_plan, protocol_result)

        if decision != Decision.PROMOTE:
            self._record_lineage(
                branch=branch,
                hypothesis=hypothesis,
                h_record=h_record,
                protocol_result=protocol_result,
                canary_result=canary_result,
                contract_result=contract_result,
                verification_result=verification_result,
                decision=decision,
                decision_reason_codes=effective_reason_codes,
            )

        if decision not in (
            Decision.ABANDON,
            Decision.CONTINUE_EXPLORE,
            Decision.VALIDATION_REPAIR_REQUIRED,
            Decision.PROMOTE,
        ):
            _sync_retained_protocol_branch_evidence(
                branch,
                hypothesis=hypothesis,
                patch=patch,
                protocol_result=protocol_result,
                decision_reason_codes=effective_reason_codes,
            )

        if decision in (Decision.CONTINUE_EXPLORE, Decision.VALIDATION_REPAIR_REQUIRED):
            result = self._continue_explore(
                branch=branch,
                hypothesis=hypothesis,
                h_record=h_record,
                protocol_result=protocol_result,
                canary_result=canary_result,
                contract_result=contract_result,
                verification_result=verification_result,
                action_label=action_label,
                decision=decision,
                decision_reason_codes=effective_reason_codes,
                proposal_attempt_ref=proposal_attempt_ref,
            )
            return _with_protocol_accounting(result, protocol_result)

        if decision == Decision.PROMOTE:
            assert promote_plan is not None
            result = self._promote(
                branch=branch,
                promote_plan=promote_plan,
                hypothesis=hypothesis,
                h_record=h_record,
                protocol_result=protocol_result,
                canary_result=canary_result,
                contract_result=contract_result,
                verification_result=verification_result,
                action_label=action_label,
                decision_reason_codes=effective_reason_codes,
                proposal_attempt_ref=proposal_attempt_ref,
            )
            return _with_protocol_accounting(result, protocol_result)

        if decision == Decision.ABANDON:
            self._abandon(
                branch=branch,
                h_record=h_record,
                decision_reason_codes=effective_reason_codes,
            )

        try:
            self.branch_controller.apply_decision(bid, decision)
        except StateTransitionError as exc:
            logger.error(
                "Branch %s: apply_decision(%s) failed: %s",
                bid,
                decision.value,
                exc,
            )

        self._record_formal_candidate_artifact(
            branch=branch,
            hypothesis=hypothesis,
            h_record=h_record,
            patch=patch,
            protocol_result=protocol_result,
            canary_result=canary_result,
            contract_result=contract_result,
            verification_result=verification_result,
            decision=decision,
            decision_reason_codes=effective_reason_codes,
            proposal_attempt_ref=proposal_attempt_ref,
        )
        self._persist_current_branch(bid)
        reason_suffix = (
            f"; reasons={','.join(effective_reason_codes)}"
            if effective_reason_codes
            else ""
        )
        return _with_protocol_accounting(
            StepResult(
                action=action_label,  # type: ignore[arg-type]
                branch_id=bid,
                decision=decision,
                reason=f"decision={decision.value}{reason_suffix}",
            ),
            protocol_result,
        )

    def _prepare_promotion(
        self,
        *,
        branch: Branch,
        action_label: str,
    ) -> PromotionPlan | StepResult:
        bid = branch.branch_id
        try:
            self.require_promotable_branch(branch)
        except StateTransitionError as exc:
            logger.error("Branch %s: promote precondition failed: %s", bid, exc)
            self.handle_failure(
                branch,
                FailureEvent(category="infra", detail=f"promote_precondition: {exc}"),
                hypothesis_already_recorded=True,
            )
            return StepResult(
                action=action_label,  # type: ignore[arg-type]
                branch_id=bid,
                decision=None,
                reason=f"promote_precondition_failed: {exc}",
            )
        try:
            return self.prepare_promoted_champion(branch)
        except Exception as exc:
            logger.error("Branch %s: promote prepare failed: %s", bid, exc)
            self.handle_failure(
                branch,
                FailureEvent(category="infra", detail=f"promote_prepare: {exc}"),
                hypothesis_already_recorded=True,
            )
            return StepResult(
                action=action_label,  # type: ignore[arg-type]
                branch_id=bid,
                decision=None,
                reason=f"promote_prepare_failed: {exc}",
            )

    def _record_lineage(
        self,
        *,
        branch: Branch,
        hypothesis: HypothesisProposal,
        h_record: HypothesisRecord,
        protocol_result: Optional[ProtocolResult],
        canary_result: CanaryResult,
        contract_result: ContractResult,
        verification_result: VerificationResult,
        decision: Decision,
        decision_reason_codes: Optional[tuple[str, ...]],
        event_id: Optional[str] = None,
        strict: bool = False,
    ) -> None:
        args = (
            branch,
            hypothesis,
            self.branch_patches.get(branch.branch_id),
            contract_result,
            verification_result,
            canary_result,
            protocol_result,
            decision,
            h_record.hypothesis_id,
            decision_reason_codes,
            event_id,
        )
        if strict:
            self.record_step_lineage(*args, strict=True)
        else:
            self.record_step_lineage(*args)

    def _continue_explore(
        self,
        *,
        branch: Branch,
        hypothesis: HypothesisProposal,
        h_record: HypothesisRecord,
        protocol_result: Optional[ProtocolResult],
        canary_result: CanaryResult,
        contract_result: ContractResult,
        verification_result: VerificationResult,
        action_label: str,
        decision: Decision,
        decision_reason_codes: Optional[tuple[str, ...]],
        proposal_attempt_ref: Mapping[str, Any] | None,
    ) -> StepResult:
        bid = branch.branch_id
        if protocol_result is not None and _stage_value(protocol_result) == "screening":
            _update_branch_screening_evidence_summary(
                branch,
                protocol_result=protocol_result,
                decision_reason_codes=decision_reason_codes,
            )

        self._record_formal_candidate_artifact(
            branch=branch,
            hypothesis=hypothesis,
            h_record=h_record,
            patch=self.branch_patches.get(bid),
            protocol_result=protocol_result,
            canary_result=canary_result,
            contract_result=contract_result,
            verification_result=verification_result,
            decision=decision,
            decision_reason_codes=decision_reason_codes,
            proposal_attempt_ref=proposal_attempt_ref,
        )
        # Screening/validation continuation evolves the same V3 branch.  Keep
        # its verified workspace as the executable base for the next H/C turn;
        # discarding it here would make the prompt describe branch-current code
        # while the next candidate actually ran from the champion snapshot.
        self.branch_patches.pop(bid, None)
        self.branch_hypotheses.pop(bid, None)
        self.branch_current_hypothesis.pop(bid, None)
        self.hypothesis_store.mark_status(h_record.hypothesis_id, "rejected")
        branch.branch_code_status = "clean"
        branch.direction = None
        if branch.state not in (
            BranchState.EXPLORE,
            BranchState.STALE_WEIGHT_UPDATE,
        ):
            try:
                self.branch_controller.apply_decision(bid, decision)
            except StateTransitionError as exc:
                logger.error(
                    "Branch %s: apply_decision(%s) from %s failed: %s",
                    bid,
                    decision.value,
                    branch.state.value,
                    exc,
                )
        self.persist_branch_state(bid)
        reason_codes = tuple(decision_reason_codes or ())
        reason = "decision=continue_explore"
        if reason_codes:
            reason = f"{reason}; reasons={','.join(reason_codes)}"
        return StepResult(
            action=action_label,  # type: ignore[arg-type]
            branch_id=bid,
            decision=decision,
            reason=reason,
            attempt_kind="screening",
        )

    def _record_formal_candidate_artifact(
        self,
        *,
        branch: Branch,
        hypothesis: HypothesisProposal,
        h_record: HypothesisRecord,
        patch: PatchProposal | None,
        protocol_result: Optional[ProtocolResult],
        canary_result: CanaryResult,
        contract_result: ContractResult,
        verification_result: VerificationResult,
        decision: Decision,
        decision_reason_codes: Optional[tuple[str, ...]],
        proposal_attempt_ref: Mapping[str, Any] | None,
    ) -> None:
        if self.record_formal_candidate_artifact is None:
            return
        if not _should_reconcile_formal_candidate_artifact(
            protocol_result=protocol_result,
        ):
            return
        try:
            artifact_ref = self.record_formal_candidate_artifact(
                branch=branch,
                hypothesis=hypothesis,
                h_record=h_record,
                patch=patch,
                protocol_result=protocol_result,
                canary_result=canary_result,
                contract_result=contract_result,
                verification_result=verification_result,
                decision=decision,
                decision_reason_codes=tuple(decision_reason_codes or ()),
                workspace=self.branch_workspaces.get(branch.branch_id),
                proposal_attempt_ref=proposal_attempt_ref,
            )
        except Exception as exc:  # pragma: no cover - audit artifact is best effort
            logger.debug(
                "Branch %s: formal candidate patch artifact write failed: %s",
                branch.branch_id,
                exc,
            )
            return
        if artifact_ref:
            summary = dict(getattr(branch, "branch_evidence_summary", {}) or {})
            summary["formal_candidate_patch_artifact_ref"] = artifact_ref
            branch.branch_evidence_summary = summary

    def _promote(
        self,
        *,
        branch: Branch,
        promote_plan: PromotionPlan,
        hypothesis: HypothesisProposal,
        h_record: HypothesisRecord,
        protocol_result: Optional[ProtocolResult],
        canary_result: CanaryResult,
        contract_result: ContractResult,
        verification_result: VerificationResult,
        action_label: str,
        decision_reason_codes: Optional[tuple[str, ...]],
        proposal_attempt_ref: Mapping[str, Any] | None,
    ) -> StepResult:
        bid = branch.branch_id
        promotion_event_id = str(uuid.uuid4())
        promoted_champion = replace(
            promote_plan.champion,
            promotion_experiment_id=promotion_event_id,
        )
        promotion_metadata = dict(promote_plan.metadata or {})
        promotion_metadata.update(
            {
                "promotion_experiment_id": promotion_event_id,
                "branch_id": bid,
                "hypothesis_id": h_record.hypothesis_id,
                "base_champion_version": getattr(branch, "base_champion_id", None),
                "candidate_code_hash": (
                    getattr(branch, "current_code_hash", None)
                    or getattr(branch, "last_clean_code_hash", None)
                ),
                "patch": self.branch_patches.get(bid),
                "protocol_result": protocol_result,
                "decision_reason_codes": tuple(decision_reason_codes or ()),
                "branch_evidence_summary": dict(
                    getattr(branch, "branch_evidence_summary", {}) or {}
                ),
            }
        )
        promote_plan = replace(
            promote_plan,
            champion=promoted_champion,
            metadata=promotion_metadata,
        )
        try:
            self.commit_promote_plan(promote_plan)
        except PromotionCommitError as exc:
            if not exc.champion_persisted:
                logger.error("Branch %s: promote commit failed: %s", bid, exc)
                self.handle_failure(
                    branch,
                    FailureEvent(category="infra", detail=f"promote_commit: {exc}"),
                    hypothesis_already_recorded=True,
                )
                return StepResult(
                    action=action_label,  # type: ignore[arg-type]
                    branch_id=bid,
                    decision=None,
                    reason=f"promote_commit_failed: {exc}",
                    failure_stage="promotion_commit",
                    failure_category="infra",
                    failure_detail=str(exc),
                )
            logger.error(
                "Branch %s: promote commit failed after durable champion write at %s: %s",
                bid,
                exc.phase,
                exc.original,
            )
            lineage_status = "not_attempted"
            lineage_error = ""
            try:
                self._record_lineage(
                    branch=branch,
                    hypothesis=hypothesis,
                    h_record=h_record,
                    protocol_result=protocol_result,
                    canary_result=canary_result,
                    contract_result=contract_result,
                    verification_result=verification_result,
                    decision=Decision.PROMOTE,
                    decision_reason_codes=decision_reason_codes,
                    event_id=promotion_event_id,
                    strict=True,
                )
                lineage_status = "recorded"
            except Exception as lineage_exc:
                lineage_status = "degraded"
                lineage_error = str(lineage_exc)
                logger.error(
                    "Branch %s: promotion lineage write failed during recovery: %s",
                    bid,
                    lineage_exc,
                )
            _mark_promotion_integrity_status(
                branch,
                status="recovery_pending",
                promotion_event_id=promotion_event_id,
                champion_version=promote_plan.new_champion_version,
                failed_phase=exc.phase,
                completed_phases=exc.completed_phases,
                lineage_status=lineage_status,
                error=str(exc.original),
                lineage_error=lineage_error,
            )
            self.persist_branch_state(bid)
            return StepResult(
                action=action_label,  # type: ignore[arg-type]
                branch_id=bid,
                decision=Decision.PROMOTE,
                reason=(
                    "promotion_commit_recovery_pending: "
                    f"phase={exc.phase}; lineage_status={lineage_status}"
                ),
                failure_stage="promotion_commit",
                failure_category="promotion_recovery",
                failure_detail=str(exc.original),
                scheduler_audit_metadata={
                    "promotion_integrity_status": "recovery_pending",
                    "promotion_failed_phase": exc.phase,
                    "promotion_event_id": promotion_event_id,
                    "promotion_lineage_status": lineage_status,
                },
            )
        except Exception as exc:
            logger.error("Branch %s: promote commit failed: %s", bid, exc)
            self.handle_failure(
                branch,
                FailureEvent(category="infra", detail=f"promote_commit: {exc}"),
                hypothesis_already_recorded=True,
            )
            return StepResult(
                action=action_label,  # type: ignore[arg-type]
                branch_id=bid,
                decision=None,
                reason=f"promote_commit_failed: {exc}",
                failure_stage="promotion_commit",
                failure_category="infra",
                failure_detail=str(exc),
            )
        self._record_formal_candidate_artifact(
            branch=branch,
            hypothesis=hypothesis,
            h_record=h_record,
            patch=self.branch_patches.get(bid),
            protocol_result=protocol_result,
            canary_result=canary_result,
            contract_result=contract_result,
            verification_result=verification_result,
            decision=Decision.PROMOTE,
            decision_reason_codes=decision_reason_codes,
            proposal_attempt_ref=proposal_attempt_ref,
        )
        try:
            self._record_lineage(
                branch=branch,
                hypothesis=hypothesis,
                h_record=h_record,
                protocol_result=protocol_result,
                canary_result=canary_result,
                contract_result=contract_result,
                verification_result=verification_result,
                decision=Decision.PROMOTE,
                decision_reason_codes=decision_reason_codes,
                event_id=promotion_event_id,
                strict=True,
            )
        except Exception as exc:
            logger.error("Branch %s: promotion lineage write failed: %s", bid, exc)
            _mark_promotion_integrity_status(
                branch,
                status="lineage_degraded",
                promotion_event_id=promotion_event_id,
                champion_version=promote_plan.new_champion_version,
                failed_phase="record_lineage",
                completed_phases=(),
                lineage_status="degraded",
                error=str(exc),
            )
            self.persist_branch_state(bid)
            return StepResult(
                action=action_label,  # type: ignore[arg-type]
                branch_id=bid,
                decision=Decision.PROMOTE,
                reason=f"promotion_lineage_degraded: {exc}",
                failure_stage="promotion_lineage",
                failure_category="promotion_recovery",
                failure_detail=str(exc),
                scheduler_audit_metadata={
                    "promotion_integrity_status": "lineage_degraded",
                    "promotion_event_id": promotion_event_id,
                    "promotion_lineage_status": "degraded",
                },
            )
        self.persist_branch_state(bid)
        return StepResult(
            action=action_label,  # type: ignore[arg-type]
            branch_id=bid,
            decision=Decision.PROMOTE,
            reason="decision=promote",
        )

    def _abandon(
        self,
        *,
        branch: Branch,
        h_record: HypothesisRecord,
        decision_reason_codes: Optional[tuple[str, ...]],
    ) -> None:
        bid = branch.branch_id
        workspace = self.branch_workspaces.pop(bid, None)
        if workspace:
            try:
                self.archive_workspace(workspace, bid)
            except Exception as exc:
                logger.debug("Branch %s: archive failed: %s", bid, exc)
            try:
                self.cleanup_workspace(workspace)
            except Exception:
                pass
        self.branch_hypotheses.pop(bid, None)
        self.branch_patches.pop(bid, None)
        self.hypothesis_store.mark_status(h_record.hypothesis_id, "rejected")
        self.branch_current_hypothesis.pop(bid, None)

    def _persist_current_branch(self, branch_id: str) -> None:
        try:
            branch = self.branch_controller.get_branch(branch_id)
            if branch:
                if self.branch_store is not None:
                    self.branch_store.save(branch)
        except Exception as exc:
            logger.debug("BranchStore.save (decision) failed: %s", exc)


def _should_record_formal_candidate_artifact(
    *,
    patch: PatchProposal | None,
    protocol_result: Optional[ProtocolResult],
    canary_result: CanaryResult,
    contract_result: ContractResult,
    verification_result: VerificationResult,
) -> bool:
    if patch is None or protocol_result is None:
        return False
    if not (
        contract_result.passed
        and verification_result.passed
        and canary_result.passed
    ):
        return False
    if getattr(protocol_result, "stats", None) is None:
        return False
    return _stage_value(protocol_result) == "screening"


def _should_reconcile_formal_candidate_artifact(
    *,
    protocol_result: Optional[ProtocolResult],
) -> bool:
    if protocol_result is None:
        return False
    if getattr(protocol_result, "stats", None) is None:
        return False
    return _stage_value(protocol_result) == "screening"


def _with_protocol_accounting(
    result: StepResult,
    protocol_result: Optional[ProtocolResult],
) -> StepResult:
    if protocol_result is None:
        return result
    stage = _stage_value(protocol_result)
    if stage not in {"screening", "validation", "frozen"}:
        return result
    formal_evaluated = (
        getattr(protocol_result, "stats", None) is not None
        and screened_experiment_effective(protocol_result)
    )
    result.protocol_stage = stage  # type: ignore[assignment]
    result.formal_protocol_evaluated = formal_evaluated
    result.screened_experiment_effective = stage == "screening" and formal_evaluated
    return result


def _mark_promotion_integrity_status(
    branch: Branch,
    *,
    status: str,
    promotion_event_id: str,
    champion_version: int,
    failed_phase: str,
    completed_phases: Iterable[str],
    lineage_status: str,
    error: str,
    lineage_error: str = "",
) -> None:
    summary = dict(getattr(branch, "branch_evidence_summary", {}) or {})
    marker = {
        "status": status,
        "promotion_event_id": promotion_event_id,
        "champion_version": champion_version,
        "failed_phase": failed_phase,
        "completed_phases": list(completed_phases),
        "lineage_status": lineage_status,
        "recovery_required": True,
        "error": error,
    }
    if lineage_error:
        marker["lineage_error"] = lineage_error
    summary["promotion_integrity"] = marker
    branch.branch_evidence_summary = summary


def _sync_terminal_branch_evidence(
    branch: Branch,
    *,
    hypothesis: HypothesisProposal,
    patch: PatchProposal | None,
    protocol_result: Optional[ProtocolResult],
    decision_reason_codes: Iterable[str] | None,
) -> None:
    """Keep abandoned branch rows useful when read without campaign_summary."""

    reason_codes = tuple(
        dict.fromkeys(
            str(code).strip()
            for code in (decision_reason_codes or ())
            if str(code).strip()
        )
    )
    if protocol_result is not None and _stage_value(protocol_result) == "screening":
        _update_branch_screening_evidence_summary(
            branch,
            protocol_result=protocol_result,
            decision_reason_codes=reason_codes,
        )

    branch.branch_code_status = "abandoned"

    if reason_codes:
        branch.failure_codes = list(
            dict.fromkeys(
                [
                    *list(getattr(branch, "failure_codes", None) or ()),
                    *reason_codes,
                ]
            )
        )

    summary = dict(getattr(branch, "branch_evidence_summary", {}) or {})
    if (
        protocol_result is not None
        and getattr(protocol_result, "stats", None) is not None
    ):
        _merge_protocol_evidence_summary(summary, protocol_result)
    summary.update(
        {
            "terminal_status": BranchState.ABANDONED.value,
            "terminal_reason": reason_codes[0] if reason_codes else "decision_abandon",
            "terminal_reason_codes": list(reason_codes),
            "decision_reason_codes": list(reason_codes),
            "branch_code_status": branch.branch_code_status,
        }
    )
    branch.branch_evidence_summary = summary

def _sync_retained_protocol_branch_evidence(
    branch: Branch,
    *,
    hypothesis: HypothesisProposal,
    patch: PatchProposal | None,
    protocol_result: Optional[ProtocolResult],
    decision_reason_codes: Iterable[str] | None,
) -> None:
    """Persist compact evidence for non-terminal evaluated branch heads."""

    if protocol_result is None or getattr(protocol_result, "stats", None) is None:
        return
    reason_codes = tuple(
        dict.fromkeys(
            str(code).strip()
            for code in (decision_reason_codes or ())
            if str(code).strip()
        )
    )
    if branch.direction is None:
        branch.direction = (
            f"{hypothesis.change_locus}: "
            f"{hypothesis.hypothesis_text or ''}"
        )
    if _stage_value(protocol_result) == "screening":
        _update_branch_screening_evidence_summary(
            branch,
            protocol_result=protocol_result,
            decision_reason_codes=reason_codes,
        )
        return

    summary = dict(getattr(branch, "branch_evidence_summary", {}) or {})
    _merge_protocol_evidence_summary(summary, protocol_result)
    if reason_codes:
        summary["decision_reason_codes"] = list(reason_codes)
        summary["reason_codes"] = list(reason_codes)
        summary["why_not_promoted_reason_codes"] = list(reason_codes)
    summary["evidence_retention_status"] = "retained"
    branch.branch_evidence_summary = summary


def _stage_value(protocol_result: ProtocolResult) -> str:
    stage = getattr(protocol_result, "stage", "")
    return str(getattr(stage, "value", stage) or "")




def _merge_protocol_evidence_summary(
    summary: dict,
    protocol_result: ProtocolResult,
) -> None:
    stats = protocol_result.stats
    summary.setdefault("stage", _stage_value(protocol_result))
    summary.setdefault("gate_outcome", protocol_result.gate_outcome)
    for key, value in {
        "wins": int(getattr(stats, "wins", 0) or 0),
        "losses": int(getattr(stats, "losses", 0) or 0),
        "ties": int(getattr(stats, "ties", 0) or 0),
        "median_delta": getattr(stats, "median_delta", None),
        "ci_low": getattr(stats, "ci_low", None),
        "ci_high": getattr(stats, "ci_high", None),
        "statistical_status": getattr(stats, "statistical_status", None),
        "statistical_metric": getattr(stats, "statistical_metric", None),
        "runtime_ratio_median": getattr(stats, "runtime_ratio_median", None),
        "runtime_delta_median_ms": getattr(stats, "runtime_delta_median_ms", None),
        "runtime_regression_rate": getattr(stats, "runtime_regression_rate", None),
        "runtime_pairs": int(getattr(stats, "runtime_pairs", 0) or 0),
    }.items():
        if value is not None:
            summary.setdefault(key, value)
    runtime_aggregate_exclusion = runtime_aggregate_exclusion_for_protocol(
        protocol_result
    )
    if runtime_aggregate_exclusion:
        summary.setdefault(
            "runtime_aggregate_exclusion",
            runtime_aggregate_exclusion,
        )
