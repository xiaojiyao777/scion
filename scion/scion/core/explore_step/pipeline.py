"""Explore-step pipeline facade class."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Mapping, MutableMapping, Optional, Sequence, Tuple

from scion.core.execution_outcome import (
    ExecutionOutcome,
    ExecutionOutcomeRecord,
    execution_outcome_projection_kwargs,
    install_branch_execution_hold,
    record_execution_outcome_event,
)
from scion.core.models import (
    Branch,
    BranchState,
    CanaryResult,
    ChampionState,
    Decision,
    FailureEvent,
    HypothesisProposal,
    HypothesisRecord,
    PatchProposal,
    ProtocolResult,
    StepRecord,
    VerificationResult,
)
from scion.core.evaluation_orchestrator import (
    EvaluationExecutionResult,
)
from scion.core.step_result import StepResult
from scion.core.telemetry_validation import screened_experiment_effective
from scion.core.verification_call import run_verification_gate
from scion.contract.result_payload import diagnostic_checks
from scion.proposal.context_manager.code_context import branch_current_file_sources

from .common import (
    _proposal_failure_hypothesis,
)
from .events import ExploreStepEventMixin
from .verification import VerificationMixin

logger = logging.getLogger(__name__)


def _advisory_contract_diagnostic(
    kind: str,
    detail: str,
    *,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    diagnostic_metadata = {
        "gate_action": "diagnostic",
        "diagnostic_kind": kind,
        "authority": "outer_contract_audit_only",
    }
    diagnostic_metadata.update(dict(metadata or {}))
    return {
        "name": f"K5_{kind}",
        "passed": True,
        "severity": "light",
        "detail": detail,
        "metadata": diagnostic_metadata,
    }

__all__ = [
    "ExploreStepPipeline",
]


@dataclass
class ExploreStepPipeline(VerificationMixin, ExploreStepEventMixin):
    """Own the proposal -> contract -> verification -> screening path."""

    branch_controller: Any
    contract_gate: Any
    verification_gate: Any
    hypothesis_store: Any
    registry: Any
    campaign_id: str
    get_champion: Callable[[], Optional[ChampionState]]
    branch_hypotheses: MutableMapping[str, HypothesisProposal]
    branch_patches: MutableMapping[str, PatchProposal]
    branch_current_hypothesis: MutableMapping[str, HypothesisRecord]
    branch_workspaces: MutableMapping[str, str]
    failure_streak: MutableMapping[str, int]
    increment_round: Callable[[], int]
    generate_hypothesis: Callable[
        [Branch],
        Tuple[Optional[HypothesisProposal], Optional[HypothesisRecord]],
    ]
    generate_code: Callable[..., Optional[PatchProposal]]
    handle_failure: Callable[..., None]
    record_step: Callable[[StepRecord], None]
    setup_workspace: Callable[[Branch], Optional[str]]
    apply_patch: Callable[..., Any]
    record_verification_pass: Callable[[Branch, str], None]
    archive_failed_workspace: Callable[[str, str, int], Optional[str]]
    evaluate: Callable[
        [Branch, str, HypothesisProposal],
        EvaluationExecutionResult,
    ]
    apply_decision_and_finalize: Callable[..., StepResult]
    decision_reason_codes_for: Callable[[str, Optional[ProtocolResult]], Optional[Tuple[str, ...]]]
    proposal_failure_detail_for: Callable[[str], Optional[str]] = lambda _branch_id: None
    proposal_execution_outcome_for: Callable[
        [str], Optional[ExecutionOutcomeRecord]
    ] = lambda _branch_id: None
    proposal_session_ref_for: Callable[[str], Optional[dict[str, Any]]] = lambda _branch_id: None
    proposal_governance_envelope_for: Callable[[str], Any | None] = (
        lambda _branch_id: None
    )
    persist_branch_state: Callable[[str], None] = lambda _branch_id: None
    update_status_progress: Callable[[dict[str, Any] | None], None] = (
        lambda _payload: None
    )
    step_history: Sequence[StepRecord] = ()
    decision_provenance_for: Callable[[str], dict[str, Any]] = lambda _branch_id: {}

    def run(self, branch: Branch) -> StepResult:
        """Run the full EXPLORE/EXPLORE_EXPAND branch step."""
        bid = branch.branch_id
        self._proposal_session_ref_cache = {}
        rnum = self.increment_round()
        h_contract_diagnostics: tuple[dict[str, Any], ...] = ()
        branch.screening_expand_count = 0
        branch.validation_expand_count = 0

        self._emit_status_progress(
            branch,
            phase="proposal_hypothesis",
            round_num=rnum,
        )
        hypothesis, h_record = self.generate_hypothesis(branch)
        if hypothesis is None:
            failure_detail = (
                self.proposal_failure_detail_for(bid)
                or "hypothesis generation failed"
            )
            session_ref = self._proposal_session_ref(bid)
            proposal_outcome = self.proposal_execution_outcome_for(bid)
            if proposal_outcome is None:
                proposal_outcome = ExecutionOutcomeRecord(
                    outcome=ExecutionOutcome.BLOCKED_INFRA,
                    reason_code="PROPOSAL_OUTCOME_MISSING",
                    detail=failure_detail,
                    provenance={
                        "owner": "explore_step_pipeline",
                        "stage": "proposal_hypothesis",
                    },
                )
            record_execution_outcome_event(
                registry=self.registry,
                campaign_id=self.campaign_id,
                branch_id=bid,
                record=proposal_outcome,
                hypothesis_id=None,
                event_kind="proposal_execution_outcome",
            )
            outcome_kwargs = execution_outcome_projection_kwargs(
                proposal_outcome
            )
            if install_branch_execution_hold(branch, proposal_outcome):
                self.persist_branch_state(bid)
            self.record_step(
                StepRecord(
                    round_num=rnum,
                    branch_id=bid,
                    hypothesis=_proposal_failure_hypothesis(failure_detail),
                    patch=None,
                    contract_passed=False,
                    verification_passed=False,
                    protocol_result=None,
                    decision=None,
                    failure_stage="proposal_hypothesis",
                    failure_detail=failure_detail,
                    proposal_session_ref=session_ref,
                    **outcome_kwargs,
                )
            )
            return self._finish_status_progress(
                StepResult(
                    action="explore",
                    branch_id=bid,
                    reason=failure_detail,
                    failure_stage="proposal_hypothesis",
                    failure_detail=failure_detail,
                    failure_category=proposal_outcome.outcome.value,
                    proposal_session_ref=session_ref,
                    **outcome_kwargs,
                )
            )
        if h_record is None:
            raise RuntimeError(
                f"Branch {bid}: hypothesis generated without canonical record"
            )
        logger.info(
            "Branch %s R1 hypothesis: locus=%s action=%s target=%s text='%s'",
            bid,
            hypothesis.change_locus,
            hypothesis.action,
            hypothesis.target_file,
            hypothesis.hypothesis_text or "",
        )

        self._emit_status_progress(
            branch,
            phase="hypothesis_contract",
            round_num=rnum,
            hypothesis=hypothesis,
        )
        governance_envelope = self.proposal_governance_envelope_for(bid)
        session_ref = self._proposal_session_ref(bid)
        envelope_digest = str(
            getattr(governance_envelope, "digest", "") or ""
        )
        governance_diagnostics = (
            _advisory_contract_diagnostic(
                "governance_envelope",
                "host governance envelope consumed by the outer Contract",
                metadata={"governance_envelope_digest": envelope_digest},
            ),
        )
        c_result = self._validate_hypothesis(
            hypothesis,
            governance_envelope=governance_envelope,
        )
        h_contract_diagnostics = (
            *diagnostic_checks(c_result),
            *governance_diagnostics,
        )
        if not c_result.passed:
            logger.info(
                "Branch %s: hypothesis contract failed: %s",
                bid,
                c_result.failure_reason,
            )
            failure_stage = "hypothesis_contract"
            failure_detail = c_result.failure_reason
            contract_outcome = self._record_contract_failure(
                bid,
                hypothesis,
                c_result,
                stage=failure_stage,
                hypothesis_id=h_record.hypothesis_id,
            )
            self.hypothesis_store.mark_status(
                h_record.hypothesis_id,
                "research_rejected",
            )
            outcome_kwargs = execution_outcome_projection_kwargs(
                contract_outcome
            )
            self.record_step(
                StepRecord(
                    round_num=rnum,
                    branch_id=bid,
                    hypothesis=hypothesis,
                    patch=None,
                    contract_passed=False,
                    verification_passed=False,
                    protocol_result=None,
                    decision=None,
                    failure_stage=failure_stage,
                    failure_detail=failure_detail,
                    contract_diagnostics=h_contract_diagnostics,
                    hypothesis_id=h_record.hypothesis_id,
                    proposal_session_ref=session_ref,
                    **outcome_kwargs,
                )
            )
            return self._finish_status_progress(
                StepResult(
                    action="explore",
                    branch_id=bid,
                    reason="hypothesis contract rejected",
                    failure_stage=failure_stage,
                    failure_detail=failure_detail,
                    failure_category=ExecutionOutcome.RESEARCH_REJECTED.value,
                    proposal_session_ref=session_ref,
                    **outcome_kwargs,
                )
            )

        durable_record = self.hypothesis_store.get_one(h_record.hypothesis_id)
        if durable_record is None:
            raise RuntimeError(
                f"Branch {bid}: direct hypothesis record is not durable"
            )
        h_record = durable_record
        self.branch_hypotheses[bid] = hypothesis

        self._emit_status_progress(
            branch,
            phase="proposal_code",
            round_num=rnum,
            hypothesis=hypothesis,
        )
        patch = self.generate_code(branch, hypothesis)
        if patch is not None:
            logger.info(
                "Branch %s R2 code: file=%s action=%s code_len=%d",
                bid,
                patch.file_path,
                patch.action,
                len(patch.code_content or ""),
            )

        if patch is None:
            detailed_failure = self.proposal_failure_detail_for(bid)
            cache = getattr(self, "_proposal_session_ref_cache", None)
            if isinstance(cache, dict):
                cache.pop(bid, None)
            proposal_outcome = self.proposal_execution_outcome_for(bid)
            if proposal_outcome is None:
                proposal_outcome = ExecutionOutcomeRecord(
                    outcome=ExecutionOutcome.BLOCKED_INFRA,
                    reason_code="PROPOSAL_OUTCOME_MISSING",
                    detail=detailed_failure or "code generation failed",
                    provenance={
                        "owner": "explore_step_pipeline",
                        "stage": "proposal_code",
                    },
                )
            status = {
                ExecutionOutcome.NOT_EVALUATED: "not_evaluated",
                ExecutionOutcome.BLOCKED_INFRA: "blocked_infra",
                ExecutionOutcome.RESOURCE_EXHAUSTED: "resource_exhausted",
            }.get(proposal_outcome.outcome, "not_evaluated")
            self.hypothesis_store.mark_status(h_record.hypothesis_id, status)
            session_ref = self._proposal_session_ref(bid)
            record_execution_outcome_event(
                registry=self.registry,
                campaign_id=self.campaign_id,
                branch_id=bid,
                record=proposal_outcome,
                hypothesis_id=h_record.hypothesis_id,
                event_kind="proposal_execution_outcome",
            )
            outcome_kwargs = execution_outcome_projection_kwargs(
                proposal_outcome
            )
            if install_branch_execution_hold(branch, proposal_outcome):
                self.persist_branch_state(bid)
            self.record_step(
                StepRecord(
                    round_num=rnum,
                    branch_id=bid,
                    hypothesis=hypothesis,
                    patch=None,
                    contract_passed=True,
                    verification_passed=False,
                    protocol_result=None,
                    decision=None,
                    failure_stage="proposal_code",
                    failure_detail=detailed_failure,
                    hypothesis_id=h_record.hypothesis_id,
                    proposal_session_ref=session_ref,
                    **outcome_kwargs,
                )
            )
            return self._finish_status_progress(
                StepResult(
                    action="explore",
                    branch_id=bid,
                    reason=detailed_failure or proposal_outcome.reason_code,
                    failure_stage="proposal_code",
                    failure_detail=detailed_failure,
                    failure_category=proposal_outcome.outcome.value,
                    proposal_session_ref=session_ref,
                    **outcome_kwargs,
                )
            )

        self._emit_status_progress(
            branch,
            phase="patch_contract",
            round_num=rnum,
            hypothesis=hypothesis,
            patch=patch,
        )
        p_result = self.contract_gate.validate_patch(
            patch,
            approved_hypothesis=hypothesis,
            base_snapshot_path=self.branch_workspaces.get(bid),
            base_file_overrides=branch_current_file_sources(
                branch,
                self.step_history,
            ),
        )
        if not p_result.passed:
            logger.info(
                "Branch %s: patch contract failed: %s",
                bid,
                p_result.failure_reason,
            )
            session_ref = self._proposal_session_ref(bid)
            contract_outcome = self._record_contract_failure(
                bid,
                hypothesis,
                p_result,
                stage="patch_contract",
                hypothesis_id=h_record.hypothesis_id,
                patch=patch,
            )
            outcome_kwargs = execution_outcome_projection_kwargs(
                contract_outcome
            )
            self.hypothesis_store.mark_status(
                h_record.hypothesis_id,
                "research_rejected",
            )
            self.record_step(
                StepRecord(
                    round_num=rnum,
                    branch_id=bid,
                    hypothesis=hypothesis,
                    patch=patch,
                    contract_passed=False,
                    verification_passed=False,
                    protocol_result=None,
                    decision=None,
                    failure_stage="patch_contract",
                    failure_detail=p_result.failure_reason,
                    contract_diagnostics=(
                        *h_contract_diagnostics,
                        *diagnostic_checks(p_result),
                    ),
                    hypothesis_id=h_record.hypothesis_id,
                    proposal_session_ref=session_ref,
                    **outcome_kwargs,
                )
            )
            return self._finish_status_progress(
                StepResult(
                    action="explore",
                    branch_id=bid,
                    reason="patch contract rejected",
                    failure_stage="patch_contract",
                    failure_detail=p_result.failure_reason,
                    failure_category=ExecutionOutcome.RESEARCH_REJECTED.value,
                    proposal_session_ref=session_ref,
                    **outcome_kwargs,
                )
            )

        self._emit_status_progress(
            branch,
            phase="workspace_setup",
            round_num=rnum,
            hypothesis=hypothesis,
            patch=patch,
        )
        workspace = self.setup_workspace(branch)
        if workspace is None:
            workspace_outcome = ExecutionOutcomeRecord(
                outcome=ExecutionOutcome.BLOCKED_INFRA,
                reason_code="WORKSPACE_SETUP_FAILED",
                detail="workspace setup failed",
                provenance={
                    "owner": "explore_step_pipeline",
                    "stage": "workspace_setup",
                },
            )
            record_execution_outcome_event(
                registry=self.registry,
                campaign_id=self.campaign_id,
                branch_id=bid,
                record=workspace_outcome,
                hypothesis_id=h_record.hypothesis_id,
                event_kind="workspace_execution_outcome",
            )
            self.handle_failure(
                branch,
                FailureEvent(category="infra", detail="workspace setup failed"),
                hypothesis_already_recorded=True,
            )
            self.hypothesis_store.mark_status(
                h_record.hypothesis_id,
                "blocked_infra",
            )
            session_ref = self._proposal_session_ref(bid)
            outcome_kwargs = execution_outcome_projection_kwargs(
                workspace_outcome
            )
            self.record_step(
                StepRecord(
                    round_num=rnum,
                    branch_id=bid,
                    hypothesis=hypothesis,
                    patch=patch,
                    contract_passed=True,
                    verification_passed=False,
                    protocol_result=None,
                    decision=None,
                    failure_stage="workspace",
                    failure_detail="workspace setup failed",
                    hypothesis_id=h_record.hypothesis_id,
                    proposal_session_ref=session_ref,
                    **outcome_kwargs,
                )
            )
            return self._finish_status_progress(
                StepResult(
                    action="explore",
                    branch_id=bid,
                    reason="workspace setup failed",
                    failure_stage="workspace",
                    failure_detail="workspace setup failed",
                    failure_category=ExecutionOutcome.BLOCKED_INFRA.value,
                    proposal_session_ref=session_ref,
                    **outcome_kwargs,
                )
            )

        try:
            self._emit_status_progress(
                branch,
                phase="apply_patch",
                round_num=rnum,
                hypothesis=hypothesis,
                patch=patch,
            )
            applied = self.apply_patch(
                branch,
                workspace,
                patch,
                hypothesis=hypothesis,
                remember_patch=True,
                sync_registry=True,
            )
            code_hash = applied.code_hash
        except Exception as exc:
            logger.warning("Branch %s: apply_patch failed: %s", bid, exc)
            failure_detail = f"apply_patch: {exc}"
            workspace_outcome = ExecutionOutcomeRecord(
                outcome=ExecutionOutcome.BLOCKED_INFRA,
                reason_code="PATCH_MATERIALIZATION_FAILED",
                detail=failure_detail,
                provenance={
                    "owner": "explore_step_pipeline",
                    "stage": "patch_materialization",
                    "error_type": type(exc).__name__,
                },
            )
            record_execution_outcome_event(
                registry=self.registry,
                campaign_id=self.campaign_id,
                branch_id=bid,
                record=workspace_outcome,
                hypothesis_id=h_record.hypothesis_id,
                event_kind="workspace_execution_outcome",
            )
            self.handle_failure(
                branch,
                FailureEvent(category="infra", detail=failure_detail),
                hypothesis_already_recorded=True,
            )
            self.hypothesis_store.mark_status(
                h_record.hypothesis_id,
                "blocked_infra",
            )
            session_ref = self._proposal_session_ref(bid)
            outcome_kwargs = execution_outcome_projection_kwargs(
                workspace_outcome
            )
            self.record_step(
                StepRecord(
                    round_num=rnum,
                    branch_id=bid,
                    hypothesis=hypothesis,
                    patch=patch,
                    contract_passed=True,
                    verification_passed=False,
                    protocol_result=None,
                    decision=None,
                    failure_stage="workspace",
                    failure_detail=failure_detail,
                    hypothesis_id=h_record.hypothesis_id,
                    proposal_session_ref=session_ref,
                    **outcome_kwargs,
                )
            )
            return self._finish_status_progress(
                StepResult(
                    action="explore",
                    branch_id=bid,
                    reason="apply_patch failed",
                    failure_stage="workspace",
                    failure_detail=failure_detail,
                    failure_category=ExecutionOutcome.BLOCKED_INFRA.value,
                    proposal_session_ref=session_ref,
                    **outcome_kwargs,
                )
            )

        champion = self.get_champion()
        champ_ws = champion.code_snapshot_path if champion else ""
        self._emit_status_progress(
            branch,
            phase="verification",
            round_num=rnum,
            hypothesis=hypothesis,
            patch=patch,
        )
        vresult = run_verification_gate(
            self.verification_gate,
            workspace,
            champ_ws,
            patch,
            hypothesis=hypothesis,
        )
        if not vresult.passed:
            verification_outcome = self._handle_verification_failure(
                branch=branch,
                rnum=rnum,
                workspace=workspace,
                patch=patch,
                hypothesis=hypothesis,
                h_record=h_record,
                vresult=vresult,
                code_hash=code_hash,
                champion_workspace=champ_ws,
            )
            if verification_outcome.step_result is not None:
                return self._finish_status_progress(
                    verification_outcome.step_result
                )
            code_hash = verification_outcome.code_hash
            vresult = verification_outcome.verification_result

        self.record_verification_pass(branch, code_hash)
        self.failure_streak.clear()
        self.branch_current_hypothesis[bid] = h_record

        fresh = self.branch_controller.get_branch(bid)
        if fresh and fresh.state in (BranchState.STALE, BranchState.STALE_WEIGHT_UPDATE):
            logger.info(
                "Branch %s: marked stale by async weight-opt during explore - deferring",
                bid,
            )
            return self._finish_status_progress(
                StepResult(
                    action="skip",
                    branch_id=bid,
                    reason="stale_during_explore",
                    attempt_kind="other",
                    execution_outcome=ExecutionOutcome.NOT_EVALUATED,
                    execution_outcome_reason_code="BRANCH_STALE_DURING_EXPLORE",
                )
            )

        self.branch_controller.next_stage(bid)
        self._emit_status_progress(
            branch,
            phase="evaluation_dispatch",
            round_num=rnum,
            hypothesis=hypothesis,
            patch=patch,
        )
        evaluation = self.evaluate(
            branch,
            workspace,
            hypothesis,
        )
        if not isinstance(evaluation, EvaluationExecutionResult):
            raise TypeError("evaluate callback must return EvaluationExecutionResult")
        decision = evaluation.decision
        protocol_result = evaluation.protocol_result
        canary_result = evaluation.canary_result
        execution_outcome = evaluation.execution_outcome
        session_ref = self._proposal_session_ref(bid)
        record_execution_outcome_event(
            registry=self.registry,
            campaign_id=self.campaign_id,
            branch_id=bid,
            hypothesis_id=h_record.hypothesis_id,
            record=execution_outcome,
            event_kind="explore_evaluation_outcome",
        )
        if execution_outcome.outcome is not ExecutionOutcome.EVALUATED:
            result = StepResult(
                action="explore",
                branch_id=bid,
                reason=execution_outcome.detail or execution_outcome.reason_code,
                attempt_kind="other",
                failure_stage="evaluation",
                failure_detail=(
                    execution_outcome.detail or execution_outcome.reason_code
                ),
                proposal_session_ref=session_ref,
                canary_result=canary_result,
                **execution_outcome_projection_kwargs(execution_outcome),
            )
            provenance = self.decision_provenance_for(bid)
            for key, value in provenance.items():
                setattr(result, key, value)
            self.record_step(
                StepRecord(
                    round_num=rnum,
                    branch_id=bid,
                    hypothesis=hypothesis,
                    patch=self.branch_patches.get(bid, patch),
                    contract_passed=True,
                    verification_passed=True,
                    protocol_result=None,
                    decision=None,
                    failure_stage="evaluation",
                    failure_detail=(
                        execution_outcome.detail or execution_outcome.reason_code
                    ),
                    contract_diagnostics=(
                        *h_contract_diagnostics,
                        *diagnostic_checks(p_result),
                    ),
                    hypothesis_id=h_record.hypothesis_id,
                    decision_reason_codes=None,
                    **provenance,
                    proposal_session_ref=session_ref,
                    canary_result=canary_result,
                    attempt_kind="other",
                    **execution_outcome_projection_kwargs(execution_outcome),
                )
            )
            return self._finish_status_progress(result)
        if decision is None:
            raise ValueError("evaluated result missing Decision")
        result = self.apply_decision_and_finalize(
            branch=branch,
            decision=decision,
            hypothesis=hypothesis,
            h_record=h_record,
            protocol_result=protocol_result,
            canary_result=canary_result,
            contract_result=p_result,
            verification_result=vresult,
            action_label="explore",
            proposal_attempt_ref=session_ref,
        )
        _annotate_protocol_accounting(result, protocol_result)
        result.canary_result = canary_result
        for key, value in execution_outcome_projection_kwargs(
            execution_outcome
        ).items():
            setattr(result, key, value)
        failure_stage, failure_detail = _evaluation_failure_detail(
            protocol_result,
            canary_result=canary_result,
        )
        provenance = self.decision_provenance_for(bid)
        for key, value in provenance.items():
            setattr(result, key, value)
        result.proposal_session_ref = session_ref
        logger.debug(
            "_run_explore_step done bid=%s decision=%s workspaces=%s",
            bid,
            decision.value,
            list(self.branch_workspaces.keys()),
        )
        self.record_step(
            StepRecord(
                round_num=rnum,
                branch_id=bid,
                hypothesis=hypothesis,
                patch=self.branch_patches.get(bid, patch),
                contract_passed=True,
                verification_passed=True,
                protocol_result=protocol_result,
                decision=result.decision if decision is not None else None,
                failure_stage=failure_stage,
                failure_detail=failure_detail,
                contract_diagnostics=(
                    *h_contract_diagnostics,
                    *diagnostic_checks(p_result),
                ),
                hypothesis_id=h_record.hypothesis_id,
                decision_reason_codes=self.decision_reason_codes_for(
                    bid,
                    protocol_result,
                ),
                **provenance,
                proposal_session_ref=session_ref,
                canary_result=canary_result,
                attempt_kind=result.attempt_kind,
                repair_policy_reason=result.repair_policy_reason or None,
                repair_mechanism_ids=result.repair_mechanism_ids,
                **execution_outcome_projection_kwargs(execution_outcome),
            )
        )
        return self._finish_status_progress(result)

    def _emit_status_progress(
        self,
        branch: Branch,
        *,
        phase: str,
        round_num: int,
        hypothesis: HypothesisProposal | None = None,
        patch: PatchProposal | None = None,
    ) -> None:
        """Best-effort heartbeat for long pre-protocol steps."""
        payload: dict[str, Any] = {
            "branch_id": branch.branch_id,
            "stage": "proposal",
            "phase": phase,
            "round_num": round_num,
            "base_champion_id": branch.base_champion_id,
            "branch_weight_revision": getattr(branch, "weight_revision", 0),
            "step_started_at": datetime.now().isoformat(),
            "complete": False,
        }
        if hypothesis is not None:
            payload.update(
                {
                    "target_file": hypothesis.target_file,
                    "hypothesis_action": hypothesis.action,
                    "hypothesis_text": hypothesis.hypothesis_text,
                }
            )
        if patch is not None:
            payload.update(
                {
                    "patch_action": patch.action,
                    "patch_file": patch.file_path,
                }
            )
        try:
            self.update_status_progress(payload)
        except Exception:  # pragma: no cover - heartbeat must never break research
            logger.debug("Failed to emit explore status progress", exc_info=True)

    def _finish_status_progress(self, result: StepResult) -> StepResult:
        try:
            self.update_status_progress(None)
        except Exception:  # pragma: no cover - status cleanup must not affect result
            logger.debug("Failed to clear explore status progress", exc_info=True)
        return result


def _evaluation_failure_detail(
    protocol_result: ProtocolResult | None,
    *,
    canary_result: CanaryResult | None = None,
) -> tuple[str | None, str | None]:
    if protocol_result is None:
        return None, None
    reason_codes = {
        str(code).lower()
        for code in getattr(protocol_result, "reason_codes", ()) or ()
    }
    if "evaluation_failed" not in reason_codes:
        return None, None
    detail = str(getattr(canary_result, "reason", "") or "evaluation failed")
    return "evaluation", detail


def _annotate_protocol_accounting(
    result: StepResult,
    protocol_result: ProtocolResult | None,
) -> None:
    if protocol_result is None:
        return
    stage_obj = getattr(protocol_result, "stage", "")
    stage = str(getattr(stage_obj, "value", stage_obj) or "")
    if stage not in {"screening", "validation", "frozen"}:
        return
    formal_evaluated = (
        getattr(protocol_result, "stats", None) is not None
        and screened_experiment_effective(protocol_result)
    )
    result.protocol_stage = stage  # type: ignore[assignment]
    result.formal_protocol_evaluated = formal_evaluated
    result.screened_experiment_effective = stage == "screening" and formal_evaluated
