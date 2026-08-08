"""Decision finalization boundary for campaign branch steps."""

from __future__ import annotations

import copy
import logging
import uuid
from dataclasses import dataclass, replace
from typing import Any, Callable, Iterable, Mapping, MutableMapping, Optional, Protocol

from scion.core.branch import BranchController, StateTransitionError
from scion.core.candidate_disposition import (
    CandidateDisposition,
    CandidateDispositionMapper,
    CandidateDispositionPlan,
)
from scion.core.candidate_evaluation import (
    candidate_evaluation_kind,
    candidate_evaluation_pending,
    mark_candidate_evaluation_completed,
    mark_candidate_evaluation_pending,
)
from scion.core.decision_lifecycle_actions import (
    update_branch_protocol_evidence_summary as _update_branch_protocol_evidence_summary,
)
from scion.core.models import (
    Branch,
    BranchState,
    CanaryResult,
    ContractResult,
    Decision,
    DecisionFeatures,
    DecisionOutcome,
    FailureEvent,
    HypothesisProposal,
    HypothesisRecord,
    PatchProposal,
    ProtocolResult,
    VerificationResult,
)
from scion.core.promotion_service import PromotionCommitError, PromotionPlan
from scion.core.step_result import StepResult
from scion.core.telemetry_validation import screened_experiment_effective

logger = logging.getLogger(__name__)


class HypothesisStoreLike(Protocol):
    def mark_status(self, hypothesis_id: str, status: str) -> None: ...


class BranchStoreLike(Protocol):
    def save(self, branch: Branch) -> None: ...


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
    ) -> None: ...


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
    persist_branch_state: Callable[[str], None]
    decision_provenance_for: Callable[[str], dict[str, Any]] = lambda _branch_id: {}
    decision_features_for: Callable[[str], DecisionFeatures | None] = lambda _bid: None
    pending_candidate_patch: Callable[[Branch], PatchProposal | None] | None = None
    accept_candidate: Callable[[Branch, str, str], str] | None = None
    reject_candidate: Callable[[Branch, str], Any] | None = None

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
        effective_reason_codes = (
            decision_reason_codes
            or self.decision_reason_codes_for(
                bid,
                protocol_result,
            )
        )
        if (
            protocol_result is not None
            and decision is not Decision.PROMOTE
            and candidate_evaluation_pending(branch)
        ):
            return self._apply_nonpromotion(
                branch=branch,
                decision=decision,
                hypothesis=hypothesis,
                h_record=h_record,
                protocol_result=protocol_result,
                canary_result=canary_result,
                contract_result=contract_result,
                verification_result=verification_result,
                action_label=action_label,
                decision_reason_codes=effective_reason_codes,
            )
        mark_candidate_evaluation_completed(branch)
        _consume_completed_protocol_expansion(branch, protocol_result)
        patch = self.branch_patches.get(bid)
        if (
            decision == Decision.PROMOTE
            and protocol_result is not None
            and getattr(protocol_result, "stats", None) is not None
        ):
            # Promotion planning snapshots branch evidence. Project frozen
            # facts before preparing the dossier so validation cannot remain
            # mislabeled as the latest stage on a promoted branch.
            _update_branch_protocol_evidence_summary(
                branch,
                protocol_result=protocol_result,
                decision_reason_codes=effective_reason_codes,
            )
        if decision == Decision.ABANDON:
            _sync_terminal_branch_evidence(
                branch,
                hypothesis=hypothesis,
                patch=patch,
                protocol_result=protocol_result,
                decision_reason_codes=effective_reason_codes,
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

    def _apply_nonpromotion(
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
        decision_reason_codes: Optional[tuple[str, ...]],
    ) -> StepResult:
        """Apply one completed Protocol decision directly and synchronously.

        The Protocol result, branch snapshot, hypothesis status, and ordinary
        lineage are the scientific record.  There is deliberately no separate
        intent, digest, CAS fence, or recovery lifecycle to attest the same
        fact a second time.
        """
        bid = branch.branch_id
        candidate_kind = candidate_evaluation_kind(branch)
        if candidate_kind is None:
            raise RuntimeError("pending candidate evaluation kind is unavailable")
        patch = self.branch_patches.get(bid)
        if patch is None and self.pending_candidate_patch is not None:
            patch = self.pending_candidate_patch(branch)
        disposition = self._candidate_disposition(
            branch_id=bid,
            decision=decision,
            decision_reason_codes=decision_reason_codes,
        )
        target = copy.deepcopy(branch)
        _consume_completed_protocol_expansion(target, protocol_result)

        if decision == Decision.ABANDON:
            _sync_terminal_branch_evidence(
                target,
                hypothesis=hypothesis,
                patch=patch,
                protocol_result=protocol_result,
                decision_reason_codes=decision_reason_codes,
            )
        elif decision in (
            Decision.CONTINUE_EXPLORE,
            Decision.VALIDATION_REPAIR_REQUIRED,
        ):
            if (
                protocol_result is not None
                and getattr(protocol_result, "stats", None) is not None
            ):
                _update_branch_protocol_evidence_summary(
                    target,
                    protocol_result=protocol_result,
                    decision_reason_codes=decision_reason_codes,
                )
        else:
            _sync_retained_protocol_branch_evidence(
                target,
                hypothesis=hypothesis,
                patch=patch,
                protocol_result=protocol_result,
                decision_reason_codes=decision_reason_codes,
            )

        if not (
            decision in (Decision.CONTINUE_EXPLORE, Decision.VALIDATION_REPAIR_REQUIRED)
            and target.state in (BranchState.EXPLORE, BranchState.STALE_WEIGHT_UPDATE)
        ):
            _apply_decision_to_detached_branch(target, decision)

        # Append-only Decision lineage records the evaluated staging candidate.
        # Write it while the detached target still describes that candidate:
        # rejection restores the live branch to its clean parent and drops the
        # pending patch binding. If lineage fails, leave that live candidate
        # untouched and pending so no consumed-candidate/pending-marker split
        # can be retried as a second Decision.
        lineage_branch = copy.deepcopy(target)
        self._record_lineage(
            branch=lineage_branch,
            hypothesis=hypothesis,
            h_record=h_record,
            protocol_result=protocol_result,
            canary_result=canary_result,
            contract_result=contract_result,
            verification_result=verification_result,
            decision=decision,
            decision_reason_codes=decision_reason_codes,
            patch=patch,
        )
        terminal_h_status, discard_restored_workspace = (
            self._apply_candidate_disposition(
                branch=branch,
                target=target,
                plan=disposition,
            )
        )
        if (
            disposition.disposition
            in {
                CandidateDisposition.PROVISIONAL_HEAD,
                CandidateDisposition.EXACT_REUSE,
            }
            and target.direction is None
        ):
            target.direction = (
                f"{hypothesis.change_locus}: {hypothesis.hypothesis_text or ''}"
            )
        mark_candidate_evaluation_pending(
            target,
            hypothesis_id=h_record.hypothesis_id,
            kind=candidate_kind,
        )
        mark_candidate_evaluation_completed(target)
        _install_branch_snapshot(self.branch_controller, branch, target)
        if terminal_h_status is not None:
            self.hypothesis_store.mark_status(h_record.hypothesis_id, terminal_h_status)
            h_record.status = terminal_h_status
        self.persist_branch_state(bid)

        if discard_restored_workspace:
            self.discard_branch_workspace(bid)

        if decision in (
            Decision.CONTINUE_EXPLORE,
            Decision.VALIDATION_REPAIR_REQUIRED,
        ):
            self.branch_patches.pop(bid, None)
            self.branch_hypotheses.pop(bid, None)
            self.branch_current_hypothesis.pop(bid, None)
        elif decision == Decision.ABANDON:
            self.branch_hypotheses.pop(bid, None)
            self.branch_patches.pop(bid, None)
            self.branch_current_hypothesis.pop(bid, None)
        reason_codes = tuple(decision_reason_codes or ())
        reason = f"decision={decision.value}"
        if reason_codes:
            reason = f"{reason}; reasons={','.join(reason_codes)}"
        return _with_protocol_accounting(
            StepResult(
                action=action_label,  # type: ignore[arg-type]
                branch_id=bid,
                decision=decision,
                reason=reason,
                attempt_kind="screening",
            ),
            protocol_result,
        )

    def _candidate_disposition(
        self,
        *,
        branch_id: str,
        decision: Decision,
        decision_reason_codes: Iterable[str] | None,
    ) -> CandidateDispositionPlan:
        features = self.decision_features_for(branch_id)
        if features is None:
            raise RuntimeError("candidate disposition DecisionFeatures are unavailable")
        return CandidateDispositionMapper.map(
            DecisionOutcome(
                decision=decision,
                reason_codes=tuple(decision_reason_codes or ()),
                features_snapshot=features,
            )
        )

    def _apply_candidate_disposition(
        self,
        *,
        branch: Branch,
        target: Branch,
        plan: CandidateDispositionPlan,
    ) -> tuple[str, bool]:
        disposition = plan.disposition
        workspace = self.branch_workspaces.get(branch.branch_id)
        if not workspace:
            raise RuntimeError("pending candidate workspace is unavailable")

        if disposition in {
            CandidateDisposition.EXACT_REUSE,
            CandidateDisposition.PROVISIONAL_HEAD,
        }:
            if self.accept_candidate is None:
                raise RuntimeError("candidate acceptance callback is unavailable")
            self.accept_candidate(branch, branch.current_code_hash or "", workspace)
            target.current_code_hash = branch.current_code_hash
            target.last_clean_code_hash = branch.last_clean_code_hash
        elif disposition is CandidateDisposition.REJECT_TERMINAL:
            if self.reject_candidate is None:
                raise RuntimeError("candidate rejection callback is unavailable")
            self.reject_candidate(branch, workspace)
            target.current_code_hash = branch.current_code_hash
            target.last_clean_code_hash = branch.last_clean_code_hash

        if disposition is CandidateDisposition.PROVISIONAL_HEAD:
            target.branch_code_status = "provisional"
        elif disposition is CandidateDisposition.EXACT_REUSE:
            target.branch_code_status = "clean"
        elif disposition is not CandidateDisposition.REJECT_TERMINAL:
            raise RuntimeError(
                f"unsupported nonpromotion candidate disposition: {disposition.value}"
            )

        summary = dict(target.branch_evidence_summary or {})
        summary["candidate_disposition"] = {
            "schema_version": "candidate-disposition.v1",
            "disposition": disposition.value,
            "hypothesis_status": plan.hypothesis_status.value,
            "rule": plan.rule.value,
        }
        target.branch_evidence_summary = summary
        return (
            plan.hypothesis_status.value,
            disposition is CandidateDisposition.REJECT_TERMINAL,
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
        patch: PatchProposal | None = None,
    ) -> None:
        args = (
            branch,
            hypothesis,
            patch if patch is not None else self.branch_patches.get(branch.branch_id),
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
    ) -> StepResult:
        bid = branch.branch_id
        if (
            protocol_result is not None
            and getattr(protocol_result, "stats", None) is not None
        ):
            _update_branch_protocol_evidence_summary(
                branch,
                protocol_result=protocol_result,
                decision_reason_codes=decision_reason_codes,
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
    ) -> StepResult:
        bid = branch.branch_id
        promotion_event_id = str(uuid.uuid4())
        promoted_champion = replace(
            promote_plan.champion,
            promotion_experiment_id=promotion_event_id,
        )
        promote_plan = replace(
            promote_plan,
            champion=promoted_champion,
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
        self.discard_branch_workspace(bid)
        self.branch_hypotheses.pop(bid, None)
        self.branch_patches.pop(bid, None)
        self.hypothesis_store.mark_status(h_record.hypothesis_id, "rejected")
        self.branch_current_hypothesis.pop(bid, None)

    def _persist_current_branch(self, branch_id: str) -> None:
        branch = self.branch_controller.get_branch(branch_id)
        if branch and self.branch_store is not None:
            self.branch_store.save(branch)


def _apply_decision_to_detached_branch(branch: Branch, decision: Decision) -> None:
    controller = BranchController()
    controller.restore_branch(branch)
    controller.apply_decision(branch.branch_id, decision)


def _consume_completed_protocol_expansion(
    branch: Branch,
    protocol_result: ProtocolResult | None,
) -> None:
    """Consume an expansion round only in the completed decision target."""

    if protocol_result is None:
        return
    if branch.state is BranchState.EXPLORE_EXPAND:
        branch.screening_expand_count += 1
    elif branch.state is BranchState.VALIDATING_EXPAND:
        branch.validation_expand_count += 1


def _install_branch_snapshot(
    controller: BranchController,
    branch: Branch,
    target: Branch,
) -> None:
    values = copy.deepcopy(target.__dict__)
    branch.__dict__.clear()
    branch.__dict__.update(values)
    current = controller.get_branch(target.branch_id)
    if current is not branch:
        current.__dict__.clear()
        current.__dict__.update(copy.deepcopy(values))


def _with_protocol_accounting(
    result: StepResult,
    protocol_result: Optional[ProtocolResult],
) -> StepResult:
    if protocol_result is None:
        return result
    stage = _stage_value(protocol_result)
    if stage not in {"screening", "validation", "frozen"}:
        return result
    formal_evaluated = getattr(
        protocol_result, "stats", None
    ) is not None and screened_experiment_effective(protocol_result)
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
    if (
        protocol_result is not None
        and getattr(protocol_result, "stats", None) is not None
    ):
        _update_branch_protocol_evidence_summary(
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
            f"{hypothesis.change_locus}: {hypothesis.hypothesis_text or ''}"
        )
    _update_branch_protocol_evidence_summary(
        branch,
        protocol_result=protocol_result,
        decision_reason_codes=reason_codes,
    )
    if _stage_value(protocol_result) != "screening" and reason_codes:
        summary = dict(getattr(branch, "branch_evidence_summary", {}) or {})
        summary["why_not_promoted_reason_codes"] = list(reason_codes)
        branch.branch_evidence_summary = summary


def _stage_value(protocol_result: ProtocolResult) -> str:
    stage = getattr(protocol_result, "stage", "")
    return str(getattr(stage, "value", stage) or "")
