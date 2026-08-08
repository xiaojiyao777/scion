"""Compatibility adapters used during CampaignManager decomposition."""

from __future__ import annotations

from contextlib import nullcontext
from types import SimpleNamespace
from typing import Any, List, Optional, Tuple

from scion.core.branch import Branch
from scion.core.branch_step_runner import BranchStepRunner
from scion.core.evaluation_orchestrator import (
    EvaluationExecutionResult,
    EvaluationOrchestrator,
)
from scion.core.explore_step_pipeline import ExploreStepPipeline
from scion.core.features import SafeFeatureExtractor
from scion.core.models import (
    HypothesisProposal,
    HypothesisRecord,
    PatchProposal,
    ProtocolResult,
)
from scion.core.production_boundary import is_adapter_backed_production_campaign
from scion.core.step_result import StepResult
from scion.core.workspace_lifecycle import WorkspaceLifecycleService


def _lookup_decision_reason_codes(
    owner: Any,
    branch_id: str,
    protocol_result: Optional[ProtocolResult],
) -> Optional[Tuple[str, ...]]:
    return getattr(owner, "_decision_reason_codes", {}).get(
        branch_id,
        protocol_result.reason_codes if protocol_result else None,
    )


def _lookup_decision_provenance(
    owner: Any,
    branch_id: str,
) -> dict[str, Any]:
    orchestrator = getattr(owner, "_evaluation_orchestrator", None)

    def mapping(name: str) -> Any:
        if orchestrator is not None:
            value = getattr(orchestrator, name, None)
            if value is not None:
                return value
        owner_name = f"_{name}"
        return getattr(owner, owner_name, {})

    return {
        "decision_engine_reason_codes": tuple(
            mapping("decision_engine_reason_codes").get(
                branch_id,
                (),
            )
        ),
        "diagnostic_reason_codes": tuple(
            mapping("diagnostic_reason_codes").get(
                branch_id,
                (),
            )
        ),
        "bypass_reason_codes": tuple(mapping("bypass_reason_codes").get(branch_id, ())),
        "decision_features_snapshot": mapping("decision_feature_snapshots").get(
            branch_id
        ),
    }


def _workspace_service_for(owner: Any) -> WorkspaceLifecycleService:
    lifecycle = getattr(owner, "_workspace_lifecycle", None)
    if lifecycle is None:
        lifecycle = WorkspaceLifecycleService.from_owner(owner)
    return lifecycle


class _NoopBranchStore:
    def save(self, branch: Branch) -> None:
        return None


class _NoopScheduler:
    def select_next(self, active: List[Branch]) -> Any:
        return SimpleNamespace(action="at_capacity", branch=None)


def _branch_step_runner_for(owner: Any) -> BranchStepRunner:
    runner = getattr(owner, "_branch_step_runner", None)
    if runner is not None:
        return runner

    def increment_round() -> int:
        value = getattr(owner, "_round_num", 0) + 1
        setattr(owner, "_round_num", value)
        return value

    def apply_patch(
        branch: Branch, workspace: str, patch: PatchProposal, **kwargs: Any
    ) -> Any:
        lifecycle = getattr(owner, "_workspace_lifecycle", None)
        if lifecycle is not None:
            return lifecycle.apply_patch(branch, workspace, patch, **kwargs)
        materializer = getattr(owner, "_materializer")
        code_hash = materializer.apply_patch(workspace, patch)
        try:
            owner._branch_ctrl.record_candidate_code(branch.branch_id, code_hash)
        except Exception:
            pass
        return SimpleNamespace(code_hash=code_hash)

    def missing_eval_step(branch: Branch) -> StepResult:
        raise RuntimeError("eval step callback is not available")

    def missing_reconcile_step(branch: Branch) -> StepResult:
        return StepResult(
            action="reconcile",
            branch_id=branch.branch_id,
            reason="reconcile step callback is not available",
        )

    lifecycle = getattr(owner, "_workspace_lifecycle", None)
    transactional_reconcile = lifecycle is not None

    return BranchStepRunner(
        branch_controller=owner._branch_ctrl,
        scheduler=getattr(owner, "_scheduler", _NoopScheduler()),
        champion_lock=getattr(owner, "_champion_lock", nullcontext()),
        get_champion=lambda: owner._champion,
        branch_store=getattr(owner, "_branch_store", _NoopBranchStore()),
        branch_workspaces=getattr(owner, "_branch_workspaces", {}),
        branch_hypotheses=getattr(owner, "_branch_hypotheses", {}),
        branch_patches=getattr(owner, "_branch_patches", {}),
        branch_current_hypothesis=getattr(owner, "_branch_current_hypothesis", {}),
        experiment_protocol_provider=lambda: getattr(
            owner, "_experiment_protocol", None
        ),
        contract_gate=getattr(owner, "_contract_gate", None),
        verification_gate=getattr(owner, "_vgate", None),
        drain_weight_opt_events=getattr(
            owner, "_drain_weight_opt_events", lambda: None
        ),
        should_stop=getattr(owner, "should_stop", lambda: False),
        get_last_stop_reason=lambda: getattr(owner, "_last_stop_reason", None),
        persist_branch_state=getattr(
            owner, "_persist_branch_state", lambda branch_id: None
        ),
        setup_workspace=getattr(
            owner, "_setup_workspace", lambda branch, force_champion=False: None
        ),
        apply_patch=apply_patch,
        evaluate=getattr(
            owner,
            "_evaluate",
            lambda branch, workspace, hypothesis: (_ for _ in ()).throw(
                RuntimeError("evaluate callback is not available")
            ),
        ),
        apply_decision_and_finalize=getattr(
            owner,
            "_apply_decision_and_finalize",
            lambda **kwargs: StepResult(
                action=kwargs.get("action_label", "eval"),
                branch_id=kwargs["branch"].branch_id,
                decision=kwargs["decision"],
            ),
        ),
        record_step=getattr(owner, "_record_step", lambda step: None),
        record_scheduler_result=getattr(
            owner,
            "_record_scheduler_result",
            lambda result: None,
        ),
        decision_reason_codes_for=getattr(
            owner,
            "_decision_reason_codes_for",
            lambda branch_id, protocol_result: _lookup_decision_reason_codes(
                owner,
                branch_id,
                protocol_result,
            ),
        ),
        decision_provenance_for=getattr(
            owner,
            "_decision_provenance_for",
            lambda branch_id: _lookup_decision_provenance(owner, branch_id),
        ),
        run_explore_step=getattr(
            owner,
            "_run_explore_step",
            lambda branch: StepResult(
                action="explore",
                branch_id=branch.branch_id,
                reason="explore step callback is not available",
            ),
        ),
        run_eval_step_callback=getattr(owner, "_run_eval_step", missing_eval_step),
        run_reconcile_step_callback=getattr(
            owner, "_run_reconcile_step", missing_reconcile_step
        ),
        increment_round=getattr(owner, "_increment_round", increment_round),
        hypothesis_store=getattr(owner, "_hyp_store", None),
        registry=getattr(owner, "_registry", None),
        campaign_id=getattr(owner, "_campaign_id", ""),
        apply_reconcile_candidate=(
            lifecycle.apply_candidate_patch if transactional_reconcile else None
        ),
        reject_reconcile_candidate=(
            lifecycle.reject_candidate if transactional_reconcile else None
        ),
    )


def _explore_step_pipeline_for(owner: Any) -> ExploreStepPipeline:
    pipeline = getattr(owner, "_explore_step_pipeline", None)
    if pipeline is not None:
        return pipeline

    def increment_round() -> int:
        value = getattr(owner, "_round_num", 0) + 1
        setattr(owner, "_round_num", value)
        return value

    def apply_patch(
        branch: Branch, workspace: str, patch: PatchProposal, **kwargs: Any
    ) -> Any:
        lifecycle = getattr(owner, "_workspace_lifecycle", None)
        if lifecycle is None:
            raise RuntimeError(
                "transactional workspace lifecycle is required for explore"
            )
        return lifecycle.apply_candidate_patch(branch, workspace, patch, **kwargs)

    def reject_candidate_workspace(branch: Branch, workspace: str) -> None:
        lifecycle = getattr(owner, "_workspace_lifecycle", None)
        if lifecycle is None:
            raise RuntimeError(
                "transactional workspace lifecycle is required for rejection"
            )
        lifecycle.reject_candidate(branch, workspace)

    def missing_generate_hypothesis(
        branch: Branch,
    ) -> Tuple[Optional[HypothesisProposal], Optional[HypothesisRecord]]:
        return None, None

    def missing_evaluate(
        branch: Branch,
        workspace: str,
        hypothesis: HypothesisProposal,
    ) -> EvaluationExecutionResult:
        raise RuntimeError("evaluate callback is not available")

    return ExploreStepPipeline(
        branch_controller=owner._branch_ctrl,
        contract_gate=getattr(owner, "_contract_gate", None),
        verification_gate=getattr(owner, "_vgate", None),
        hypothesis_store=getattr(owner, "_hyp_store", None),
        registry=getattr(owner, "_registry", None),
        campaign_id=getattr(owner, "_campaign_id", ""),
        get_champion=lambda: getattr(owner, "_champion", None),
        branch_hypotheses=getattr(owner, "_branch_hypotheses", {}),
        branch_patches=getattr(owner, "_branch_patches", {}),
        branch_current_hypothesis=getattr(owner, "_branch_current_hypothesis", {}),
        branch_workspaces=getattr(owner, "_branch_workspaces", {}),
        failure_streak=getattr(owner, "_failure_streak", {}),
        increment_round=getattr(owner, "_increment_round", increment_round),
        generate_hypothesis=getattr(
            owner,
            "_round1_generate_hypothesis",
            missing_generate_hypothesis,
        ),
        generate_code=getattr(
            owner,
            "_round2_generate_code",
            lambda branch, hypothesis: None,
        ),
        handle_failure=getattr(
            owner, "_handle_failure", lambda branch, failure, **kwargs: None
        ),
        record_step=getattr(owner, "_record_step", lambda step: None),
        setup_workspace=getattr(owner, "_setup_workspace", lambda branch: None),
        apply_patch=apply_patch,
        reject_candidate_workspace=reject_candidate_workspace,
        finalize_research_rejection=getattr(
            getattr(owner, "_research_rejection_finalizer", None),
            "finalize",
            lambda **kwargs: (_ for _ in ()).throw(
                RuntimeError("research rejection finalizer is unavailable")
            ),
        ),
        evaluate=getattr(owner, "_evaluate", missing_evaluate),
        apply_decision_and_finalize=getattr(
            owner,
            "_apply_decision_and_finalize",
            lambda **kwargs: StepResult(
                action=kwargs.get("action_label", "explore"),
                branch_id=kwargs["branch"].branch_id,
                decision=kwargs["decision"],
            ),
        ),
        decision_reason_codes_for=getattr(
            owner,
            "_decision_reason_codes_for",
            lambda branch_id, protocol_result: _lookup_decision_reason_codes(
                owner,
                branch_id,
                protocol_result,
            ),
        ),
        decision_provenance_for=getattr(
            owner,
            "_decision_provenance_for",
            lambda branch_id: _lookup_decision_provenance(owner, branch_id),
        ),
        proposal_session_ref_for=getattr(
            owner,
            "_proposal_session_ref_for",
            lambda branch_id: None,
        ),
        proposal_execution_outcome_for=getattr(
            owner,
            "_proposal_execution_outcome_for",
            lambda branch_id: None,
        ),
        discard_approved_hypothesis_binding=getattr(
            getattr(owner, "_proposal_pipeline", None),
            "discard_approved_hypothesis_binding",
            lambda branch_id: None,
        ),
        get_current_round=lambda: getattr(owner, "_round_num", 0),
        persist_branch_state=getattr(owner, "_persist_branch_state", lambda bid: None),
        step_history=getattr(owner, "_step_history", ()),
    )


def _evaluation_orchestrator_for(owner: Any) -> EvaluationOrchestrator:
    orchestrator = getattr(owner, "_evaluation_orchestrator", None)
    if orchestrator is not None:
        return orchestrator

    def increment_experiment_count() -> None:
        setattr(owner, "_n_experiments", getattr(owner, "_n_experiments", 0) + 1)

    problem_runtime = getattr(owner, "_problem_runtime", None)
    problem_spec = getattr(problem_runtime, "spec", getattr(owner, "_spec", None))
    adapter = getattr(problem_runtime, "adapter", getattr(owner, "_adapter", None))
    require_experiment_protocol = getattr(owner, "_require_experiment_protocol", None)
    if require_experiment_protocol is None:
        require_experiment_protocol = getattr(owner, "_production_campaign", None)
    if require_experiment_protocol is None:
        require_experiment_protocol = is_adapter_backed_production_campaign(
            problem_spec=problem_spec,
            adapter=adapter,
            allow_skeleton=getattr(owner, "_allow_skeleton_mode", False),
        )

    return EvaluationOrchestrator(
        branch_controller=owner._branch_ctrl,
        champion_lock=getattr(owner, "_champion_lock", nullcontext()),
        get_champion=lambda: owner._champion,
        branch_patches=getattr(owner, "_branch_patches", {}),
        branch_workspaces=getattr(owner, "_branch_workspaces", {}),
        branch_hypotheses=getattr(owner, "_branch_hypotheses", {}),
        branch_current_hypothesis=getattr(owner, "_branch_current_hypothesis", {}),
        experiment_protocol_provider=lambda: getattr(
            owner, "_experiment_protocol", None
        ),
        feature_extractor=getattr(owner, "_feature_extractor", SafeFeatureExtractor()),
        decision_coordinator=owner._decision_coordinator,
        decision_reason_codes=getattr(owner, "_decision_reason_codes", {}),
        decision_engine_reason_codes=getattr(
            owner,
            "_decision_engine_reason_codes",
            {},
        ),
        diagnostic_reason_codes=getattr(owner, "_diagnostic_reason_codes", {}),
        bypass_reason_codes=getattr(owner, "_bypass_reason_codes", {}),
        decision_feature_snapshots=getattr(owner, "_decision_feature_snapshots", {}),
        campaign_id=getattr(owner, "_campaign_id", ""),
        registry=getattr(owner, "_registry", None),
        materializer=getattr(owner, "_materializer", None),
        hypothesis_store=getattr(owner, "_hyp_store", None),
        persist_branch_state=getattr(owner, "_persist_branch_state", lambda bid: None),
        begin_status_progress=getattr(
            owner,
            "_begin_status_progress",
            lambda **kwargs: None,
        ),
        end_status_progress=getattr(owner, "_end_status_progress", lambda: None),
        increment_experiment_count=increment_experiment_count,
        require_experiment_protocol=bool(require_experiment_protocol),
    )
