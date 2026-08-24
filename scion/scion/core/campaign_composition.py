"""Campaign service composition helpers.

This module owns the constructor-time wiring for CampaignManager.  The manager
remains the public facade and callback owner; service construction lives here so
new runtime boundaries do not keep growing campaign.py.
"""

from __future__ import annotations

import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from scion.contract.gate import ContractGate
from scion.core.async_weight_opt import (
    AsyncWeightOptCoordinator,
    bounded_terminal_wait_timeout,
)
from scion.core.branch import BranchController
from scion.core.branch_step_runner import BranchStepRunner
from scion.core.campaign_loop import CampaignLoop
from scion.core.code_development import CodeDevelopmentEvaluator
from scion.core.code_research_limits import (
    normalize_code_research_limits,
    write_code_research_limits,
)
from scion.core.decision_coordinator import DecisionCoordinator
from scion.core.decision_finalizer import DecisionFinalizer
from scion.core.evaluation_orchestrator import EvaluationOrchestrator
from scion.core.evidence_recording import EvidenceRecorder
from scion.core.explore_step.pipeline import ExploreStepPipeline
from scion.core.problem_runtime import ProblemRuntime
from scion.core.production_boundary import (
    validate_fresh_campaign_output,
    validate_production_campaign_boundary,
)
from scion.core.promotion_service import PromotionService
from scion.core.proposal_pipeline import (
    ProposalPipeline,
)
from scion.core.qualification import (
    QualificationRuntime,
    normalize_qualification_only_config,
)
from scion.core.research_history import problem_id_from_spec
from scion.core.research_input import write_research_input
from scion.core.research_rejection_finalizer import ResearchRejectionFinalizer
from scion.core.research_surface_index import editable_patterns
from scion.core.resource_envelope import (
    ProviderCallBudget,
    normalize_resource_envelope,
    write_resource_envelope,
)
from scion.core.scheduler import Scheduler
from scion.core.status_reporter import StatusReporter
from scion.core.verification_factory import CampaignVerificationFactory
from scion.core.weight_opt_committer import WeightOptCommitter
from scion.core.workspace_service import WorkspaceService
from scion.lineage.registry import LineageRegistry
from scion.proposal.engine import CreativeLayer
from scion.runtime.workspace import WorkspaceMaterializer
from scion.verification.development import (
    declared_development_problem_package_paths,
    declared_development_suites,
    declared_development_workspace_paths,
    validate_development_closure_boundary,
)


def _mark_balance_exhausted(owner: Any) -> None:
    owner._balance_exhausted = True
    if not getattr(owner, "_external_stop_requested", False):
        owner.request_stop("api_balance_exhausted")


def _pattern_set(patterns: Any) -> frozenset[str] | None:
    normalized = frozenset(
        pattern
        for pattern in (str(value).strip() for value in (patterns or ()))
        if pattern
    )
    return normalized or None


def _materializer_kwargs_from_problem_spec(
    problem_spec: Any,
) -> dict[str, Any]:
    search_space = getattr(problem_spec, "search_space", None)
    return {
        "frozen_patterns": _pattern_set(getattr(search_space, "frozen", ())),
        "editable_patterns": editable_patterns(problem_spec),
    }


def compose_campaign_services(
    owner: Any,
    *,
    problem_spec: Any,
    protocol_config: Any,
    split_manifest: Any,
    seed_ledger: Any,
    llm_client: Any,
    champion: Any,
    campaign_dir: str,
    experiment_protocol: Any,
    adapter: Any,
    verification_gate: Any | None = None,
    operator_execute_signature: str | None = None,
    research_input: Any | None = None,
    research_history: Any = (),
    resource_envelope: Any | None = None,
    code_research_limits: Any | None = None,
    qualification_only: Any | None = None,
) -> None:
    """Install CampaignManager services and state on *owner*."""
    validate_fresh_campaign_output(campaign_dir)
    normalized_code_research_limits = (
        None
        if code_research_limits is None
        else normalize_code_research_limits(code_research_limits)
    )
    development_suites = (
        ()
        if normalized_code_research_limits is None
        else declared_development_suites(problem_spec)
    )
    development_workspace_paths = (
        ()
        if normalized_code_research_limits is None
        else declared_development_workspace_paths(problem_spec)
    )
    development_problem_package_paths = (
        ()
        if normalized_code_research_limits is None
        else declared_development_problem_package_paths(problem_spec)
    )
    if normalized_code_research_limits is not None:
        validate_development_closure_boundary(
            problem_spec=problem_spec,
            suites=development_suites,
            workspace_paths=development_workspace_paths,
            problem_package_paths=development_problem_package_paths,
            split_manifest=split_manifest,
            champion_root=getattr(champion, "code_snapshot_path", None),
        )
    owner._problem_runtime = ProblemRuntime(
        problem_spec=problem_spec,
        adapter=adapter,
        split_manifest=split_manifest,
        seed_ledger=seed_ledger,
        research_input=research_input,
        research_history=research_history,
        development_suites=development_suites,
    )
    owner._protocol_config = protocol_config
    owner._resource_envelope = normalize_resource_envelope(resource_envelope)
    owner._provider_call_budget = ProviderCallBudget(
        owner._resource_envelope.provider_call_cap
    )
    owner._code_research_limits = normalized_code_research_limits
    owner._qualification_only_config = normalize_qualification_only_config(
        qualification_only
    )
    owner._qualification_runtime = (
        QualificationRuntime(owner._qualification_only_config)
        if owner._qualification_only_config is not None
        else None
    )
    owner._split_manifest = split_manifest
    owner._seed_ledger = seed_ledger
    owner._llm_client = llm_client
    owner._champion = champion
    owner._campaign_dir = campaign_dir
    # Campaign IDs are ordinary labels used to group records.
    owner._campaign_id = Path(campaign_dir).name or "campaign"
    owner._status_reporter = StatusReporter(campaign_dir)
    owner._last_status_result = None
    owner._current_status_progress = None
    owner._last_stop_reason = None
    owner._external_stop_requested = False
    owner._branch_ctrl = BranchController()
    owner._scheduler = Scheduler()
    owner._contract_gate = ContractGate(
        problem_spec,
        operator_execute_signature=operator_execute_signature,
        adapter=adapter,
        champion_snapshot_provider=lambda: getattr(
            owner._champion,
            "code_snapshot_path",
            None,
        ),
    )
    owner._decision_coordinator = DecisionCoordinator(config=protocol_config)
    from scion.core.features import SafeFeatureExtractor

    owner._feature_extractor = SafeFeatureExtractor()
    owner._creative = CreativeLayer(
        llm_client,
        trace_dir=f"{campaign_dir}/llm_traces",
        provider_call_budget=owner._provider_call_budget,
    )

    family_taxonomy = getattr(owner._problem_runtime.spec, "family_taxonomy", None)
    owner._materializer = WorkspaceMaterializer(
        campaign_dir,
        **_materializer_kwargs_from_problem_spec(problem_spec),
    )
    owner._code_development_evaluator = (
        None
        if owner._code_research_limits is None
        else CodeDevelopmentEvaluator(
            materializer=owner._materializer,
            problem_spec=problem_spec,
            suites=owner._problem_runtime.development_suites,
            workspace_paths=development_workspace_paths,
            problem_package_paths=development_problem_package_paths,
            limits=owner._code_research_limits,
            operator_execute_signature=operator_execute_signature,
        )
    )
    owner._experiment_protocol = experiment_protocol
    if hasattr(owner._experiment_protocol, "set_problem_adapter"):
        owner._experiment_protocol.set_problem_adapter(adapter)
    os.makedirs(str(campaign_dir) + "/metrics", exist_ok=True)
    owner._vgate = CampaignVerificationFactory.build(
        problem_spec=problem_spec,
        verification_gate=verification_gate,
        experiment_protocol=experiment_protocol,
        campaign_dir=str(campaign_dir),
        adapter=adapter,
        operator_execute_signature=operator_execute_signature,
    )
    validate_production_campaign_boundary(
        problem_spec=problem_spec,
        experiment_protocol=experiment_protocol,
        adapter=adapter,
        split_manifest=split_manifest,
        seed_ledger=seed_ledger,
        verification_gate=owner._vgate,
    )
    if hasattr(owner._experiment_protocol, "set_progress_callback"):
        owner._experiment_protocol.set_progress_callback(owner._on_protocol_progress)

    def _read_promotion_weights(registry_path: str) -> dict[str, float]:
        if (
            owner._problem_runtime.spec.parameter_search.enabled
            and owner._experiment_protocol is not None
        ):
            from scion.runtime.pool_manager import read_weights

            return read_weights(registry_path)
        return {}

    owner._promotion_service = PromotionService(
        snapshot_root=owner._materializer._champions_dir,
        materializer=owner._materializer,
        set_champion=owner._set_promoted_champion,
        promote_branch=owner._transition_promoted_branch,
        mark_stale=owner._branch_ctrl.mark_all_stale,
        read_weights_fn=_read_promotion_weights,
    )

    os.makedirs(campaign_dir, exist_ok=True)
    if owner._code_research_limits is not None:
        write_code_research_limits(campaign_dir, owner._code_research_limits)
    owner._registry = LineageRegistry(os.path.join(campaign_dir, "scion.db"))
    owner._evidence_recorder = EvidenceRecorder(
        campaign_id=owner._campaign_id,
        campaign_dir=campaign_dir,
        status_reporter=owner._status_reporter,
        registry=owner._registry,
        model_id=getattr(llm_client, "model", None),
        protocol_version=getattr(protocol_config, "version", None),
        family_taxonomy=family_taxonomy,
        problem_id=problem_id_from_spec(problem_spec),
    )
    if owner._problem_runtime.research_input is not None:
        write_research_input(
            campaign_dir,
            owner._problem_runtime.research_input,
        )
    write_resource_envelope(campaign_dir, owner._resource_envelope)
    owner._branch_workspaces = {}
    owner._branch_patches = {}
    owner._step_history = []
    owner._round_num = 0

    owner._n_experiments = 0
    owner._start_time = datetime.now()

    owner._balance_exhausted = False
    owner._research_preflight_checked = False

    owner._champion_lock = threading.Lock()
    owner._workspace_service = WorkspaceService(
        materializer=owner._materializer,
        branch_controller=owner._branch_ctrl,
        branch_workspaces=owner._branch_workspaces,
        champion_lock=owner._champion_lock,
        get_champion=lambda: owner._champion,
    )
    owner._proposal_pipeline = ProposalPipeline(
        creative=owner._creative,
        problem_runtime=owner._problem_runtime,
        branch_workspaces=owner._branch_workspaces,
        champion_lock=owner._champion_lock,
        get_champion=lambda: owner._champion,
        step_history=owner._step_history,
        mark_balance_exhausted=lambda: _mark_balance_exhausted(owner),
        code_research_limits=owner._code_research_limits,
        code_development_evaluator=owner._code_development_evaluator,
    )
    owner._research_rejection_finalizer = ResearchRejectionFinalizer(
        campaign_id=owner._campaign_id,
        registry=owner._registry,
        workspace_service=owner._workspace_service,
        branch_patches=owner._branch_patches,
    )
    owner._weight_opt_coord = AsyncWeightOptCoordinator(owner)
    owner._weight_opt_committer = WeightOptCommitter(
        event_source=owner._weight_opt_coord,
        champion_lock=owner._champion_lock,
        get_champion=lambda: owner._champion,
        set_champion=lambda champion: setattr(owner, "_champion", champion),
        branch_controller=owner._branch_ctrl,
        registry=owner._registry,
        campaign_id=owner._campaign_id,
    )
    owner._decision_finalizer = DecisionFinalizer(
        branch_controller=owner._branch_ctrl,
        branch_patches=owner._branch_patches,
        require_promotable_branch=owner._require_promotable_branch,
        promote_branch=owner._promote_branch,
        record_step_lineage=owner._record_step_lineage,
        discard_branch_workspace=owner._workspace_service.discard_branch_workspace,
        accept_candidate=owner._workspace_service.accept_candidate,
        reject_candidate=owner._workspace_service.reject_candidate,
        registry=owner._registry,
        campaign_id=owner._campaign_id,
    )
    owner._evaluation_orchestrator = EvaluationOrchestrator(
        branch_controller=owner._branch_ctrl,
        champion_lock=owner._champion_lock,
        get_champion=lambda: owner._champion,
        branch_patches=owner._branch_patches,
        branch_workspaces=owner._branch_workspaces,
        experiment_protocol_provider=lambda: owner._experiment_protocol,
        feature_extractor=owner._feature_extractor,
        decision_coordinator=owner._decision_coordinator,
        campaign_id=owner._campaign_id,
        registry=owner._registry,
        materializer=owner._materializer,
        begin_status_progress=owner._begin_status_progress,
        end_status_progress=owner._end_status_progress,
        increment_experiment_count=lambda: setattr(
            owner,
            "_n_experiments",
            owner._n_experiments + 1,
        ),
    )
    owner._explore_step_pipeline = ExploreStepPipeline(
        branch_controller=owner._branch_ctrl,
        contract_gate=owner._contract_gate,
        verification_gate=owner._vgate,
        registry=owner._registry,
        campaign_id=owner._campaign_id,
        get_champion=lambda: owner._champion,
        branch_patches=owner._branch_patches,
        branch_workspaces=owner._branch_workspaces,
        increment_round=owner._increment_round,
        generate_hypothesis=owner._round1_generate_hypothesis,
        generate_code=owner._round2_generate_code,
        record_step=owner._record_step,
        setup_workspace=owner._setup_workspace,
        apply_patch=owner._workspace_service.apply_candidate_patch,
        verify_candidate=owner._workspace_service.verify_candidate,
        reject_candidate=owner._workspace_service.reject_candidate,
        finalize_research_rejection=owner._research_rejection_finalizer.finalize,
        evaluate=owner._evaluate,
        apply_decision_and_finalize=owner._apply_decision_and_finalize,
        reserve_proposal_attempt=(
            owner._qualification_runtime.reserve_proposal_attempt
            if owner._qualification_runtime is not None
            else (lambda: None)
        ),
        update_status_progress=owner._update_status_progress,
        step_history=owner._step_history,
    )
    owner._branch_step_runner = BranchStepRunner(
        branch_controller=owner._branch_ctrl,
        scheduler=owner._scheduler,
        champion_lock=owner._champion_lock,
        get_champion=lambda: owner._champion,
        branch_workspaces=owner._branch_workspaces,
        branch_patches=owner._branch_patches,
        experiment_protocol_provider=lambda: owner._experiment_protocol,
        contract_gate=owner._contract_gate,
        verification_gate=owner._vgate,
        drain_weight_opt_events=owner._drain_weight_opt_events,
        should_stop=owner.should_stop,
        get_last_stop_reason=lambda: owner._last_stop_reason,
        setup_workspace=owner._setup_workspace,
        evaluate=owner._evaluate,
        apply_decision_and_finalize=owner._apply_decision_and_finalize,
        record_step=owner._record_step,
        run_explore_step=owner._explore_step_pipeline.run,
        run_eval_step_callback=owner._run_eval_step,
        run_reconcile_step_callback=owner._run_reconcile_step,
        increment_round=owner._increment_round,
        registry=owner._registry,
        campaign_id=owner._campaign_id,
        apply_reconcile_candidate=(owner._workspace_service.apply_candidate_patch),
        verify_reconcile_candidate=(owner._workspace_service.verify_candidate),
        reject_reconcile_candidate=(owner._workspace_service.reject_candidate),
        qualification_only=owner._qualification_only_config is not None,
        qualification_runtime=owner._qualification_runtime,
        discard_branch_workspace=owner._workspace_service.discard_branch_workspace,
    )
    owner._campaign_loop = CampaignLoop(
        write_status=lambda **kwargs: owner._write_status(**kwargs),
        drain_weight_opt_events=lambda: owner._drain_weight_opt_events(),
        should_stop=lambda: owner.should_stop(),
        get_last_stop_reason=lambda: owner._last_stop_reason,
        set_last_stop_reason=lambda reason: setattr(owner, "_last_stop_reason", reason),
        run_one_step=(
            (lambda: owner._run_scheduled_step())
            if owner._qualification_only_config is not None
            else (lambda: owner.run_one_step())
        ),
        write_terminal_artifacts=lambda result: owner._write_terminal_artifacts(result),
        get_final_wait_timeout=lambda: bounded_terminal_wait_timeout(
            getattr(
                owner._problem_runtime.spec.parameter_search,
                "final_wait_timeout_sec",
                600.0,
            )
        ),
        wait_weight_opt_all=lambda timeout: owner._weight_opt_coord.wait_all(
            timeout=timeout
        ),
        qualification_runtime=owner._qualification_runtime,
        park_qualification_chain=owner._park_qualification_chain,
    )


def required_service_names() -> tuple[str, ...]:
    """Key services expected after composition."""
    return (
        "_vgate",
        "_evidence_recorder",
        "_branch_step_runner",
        "_proposal_pipeline",
        "_campaign_loop",
    )
