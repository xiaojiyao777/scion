"""Campaign service composition helpers.

This module owns the constructor-time wiring for CampaignManager.  The manager
remains the public facade and callback owner; service construction lives here so
new runtime boundaries do not keep growing campaign.py.
"""
from __future__ import annotations

import os
import threading
import uuid
from datetime import datetime
from typing import Any

from scion.contract.gate import ContractGate
from scion.core.async_weight_opt import AsyncWeightOptCoordinator
from scion.core.branch import BranchController
from scion.core.branch_step_runner import BranchStepRunner
from scion.core.campaign_adapters import _workspace_service_for
from scion.core.campaign_governance import CampaignGovernanceService
from scion.core.campaign_loop import CampaignLoop
from scion.core.circuit_breaker import CircuitBreaker, MAX_CONSECUTIVE_LLM_FAILURES
from scion.core.decision_coordinator import DecisionCoordinator
from scion.core.decision_finalizer import DecisionFinalizer
from scion.core.evaluation_orchestrator import EvaluationOrchestrator
from scion.core.evidence_recorder import EvidenceRecorder
from scion.core.explore_step_pipeline import ExploreStepPipeline
from scion.core.failure_lifecycle import FailureLifecycleService
from scion.core.features import BudgetState
from scion.core.frozen_budget import FrozenBudgetLedger
from scion.core.models import ChampionState, OperatorConfig
from scion.core.plateau_controller import PlateauController
from scion.core.problem_runtime import ProblemRuntime
from scion.core.promotion_lifecycle import PromotionLifecycleService
from scion.core.promotion_service import PromotionService
from scion.core.proposal_pipeline import ProposalPipeline
from scion.core.scheduler import Scheduler
from scion.core.status_reporter import StatusReporter
from scion.core.stagnation import StagnationDetector
from scion.core.termination import TerminationChecker, TerminationConfig
from scion.core.verification_factory import CampaignVerificationFactory
from scion.core.weight_opt_committer import WeightOptCommitter
from scion.core.workspace_lifecycle import WorkspaceLifecycleService
from scion.failure.router import FailureRouter, RetryConfig
from scion.lineage.branch_store import BranchStore, HypothesisStore
from scion.lineage.champion_store import ChampionStore
from scion.lineage.registry import LineageRegistry
from scion.proposal.classifier import HypothesisFamilyClassifier
from scion.proposal.engine import CreativeLayer
from scion.proposal.journal import CampaignJournal
from scion.proposal.research_log import CampaignResearchLog
from scion.proposal.search_memory import CampaignSearchMemory
from scion.runtime.workspace import WorkspaceMaterializer


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
    verification_gate: Any | None = None,
    experiment_protocol: Any | None = None,
    budget: Any | None = None,
    termination_config: Any | None = None,
    retry_config: Any | None = None,
    adapter: Any | None = None,
    operator_execute_signature: str | None = None,
    objective_lower_bounds: dict[str, float] | None = None,
    use_objective_lower_bounds_for_early_stop: bool = False,
    force_continue_early_stop: bool = False,
    allow_non_strict_runtime_verification: bool = False,
    use_agentic_proposal: bool = False,
    agentic_artifact_dir: str | None = None,
    agentic_session_timeout_sec: float | None = None,
) -> None:
    """Install CampaignManager services and state on *owner*."""
    owner._problem_runtime = ProblemRuntime(
        problem_spec=problem_spec,
        adapter=adapter,
        runtime_slow_threshold=protocol_config.runtime.max_runtime_ratio,
    )
    owner._protocol_config = protocol_config
    owner._split_manifest = split_manifest
    owner._seed_ledger = seed_ledger
    owner._llm_client = llm_client
    owner._champion = champion
    owner._campaign_dir = campaign_dir
    owner._campaign_id = str(uuid.uuid4())
    owner._status_reporter = StatusReporter(campaign_dir)
    owner._last_status_result = None
    owner._current_status_progress = None
    owner._last_stop_reason = None
    owner._objective_lower_bounds = objective_lower_bounds
    owner._use_objective_lower_bounds_for_early_stop = (
        use_objective_lower_bounds_for_early_stop
    )

    owner._branch_ctrl = BranchController()
    owner._scheduler = Scheduler()
    owner._contract_gate = ContractGate(
        problem_spec,
        operator_execute_signature=operator_execute_signature,
    )
    owner._decision_coordinator = DecisionCoordinator(config=protocol_config)
    from scion.core.features import SafeFeatureExtractor

    owner._feature_extractor = SafeFeatureExtractor()
    owner._failure_router = FailureRouter(retry_config or RetryConfig())
    owner._creative = CreativeLayer(
        llm_client,
        trace_dir=f"{campaign_dir}/llm_traces",
    )

    family_taxonomy = getattr(owner._spec, "family_taxonomy", None)
    owner._classifier = HypothesisFamilyClassifier(
        llm_client=llm_client,
        taxonomy=family_taxonomy,
        taxonomy_version=getattr(family_taxonomy, "version", "v1"),
    )
    owner._materializer = WorkspaceMaterializer(
        campaign_dir,
        frozen_patterns=frozenset(problem_spec.search_space.frozen)
        if problem_spec.search_space.frozen
        else None,
    )
    owner._experiment_protocol = experiment_protocol
    os.makedirs(str(campaign_dir) + "/metrics", exist_ok=True)
    owner._vgate = CampaignVerificationFactory.build(
        problem_spec=problem_spec,
        verification_gate=verification_gate,
        experiment_protocol=experiment_protocol,
        campaign_dir=str(campaign_dir),
        adapter=adapter,
        operator_execute_signature=operator_execute_signature,
        allow_non_strict_runtime_verification=allow_non_strict_runtime_verification,
    )
    if hasattr(owner._experiment_protocol, "set_progress_callback"):
        owner._experiment_protocol.set_progress_callback(owner._on_protocol_progress)

    def _read_promotion_weights(registry_path: str) -> dict[str, float]:
        if owner._spec.parameter_search.enabled and owner._experiment_protocol is not None:
            from scion.runtime.pool_manager import read_weights

            return read_weights(registry_path)
        return {}

    owner._promotion_service = PromotionService(
        snapshot_root=owner._materializer._champions_dir,
        materializer=owner._materializer,
        before_commit=owner._begin_promotion_commit,
        commit_champion=owner._commit_promoted_champion_state,
        persist_champion=owner._persist_promoted_champion,
        promote_branch=owner._transition_promoted_branch,
        mark_stale=owner._branch_ctrl.mark_all_stale,
        persist_branch_states=owner._persist_all_branch_states,
        on_promoted_branch=owner._record_promoted_branch,
        read_weights_fn=_read_promotion_weights,
    )

    os.makedirs(campaign_dir, exist_ok=True)
    owner._registry = LineageRegistry(os.path.join(campaign_dir, "scion.db"))
    owner._hyp_store = HypothesisStore(owner._registry)
    owner._branch_store = BranchStore(owner._registry)
    owner._evidence_recorder = EvidenceRecorder(
        campaign_id=owner._campaign_id,
        campaign_dir=campaign_dir,
        status_reporter=owner._status_reporter,
        registry=owner._registry,
        state_provider=owner.get_state,
        model_id=getattr(llm_client, "model", None),
        protocol_version=getattr(protocol_config, "version", None),
        family_taxonomy=family_taxonomy,
    )
    owner._frozen_budget_ledger = FrozenBudgetLedger(
        max_uses=protocol_config.frozen.max_uses_per_campaign,
        registry=owner._registry,
        campaign_id=owner._campaign_id,
    )
    owner._champion_store = ChampionStore(
        os.path.join(campaign_dir, "scion.db"),
        os.path.join(campaign_dir, "champions"),
    )
    _persist_initial_champion(owner)

    owner._branch_workspaces = {}
    owner._branch_hypotheses = {}
    owner._branch_patches = {}
    owner._decision_reason_codes = {}
    owner._branch_current_hypothesis = {}
    owner._pending_hypotheses = {}
    owner._step_history = []
    owner._round_num = 0

    owner._term_checker = TerminationChecker(termination_config or TerminationConfig())
    owner._budget = budget or BudgetState(total=1000, used=0)
    owner._n_experiments = 0
    owner._recent_abandoned_count = 0
    owner._hard_abandon_counted_branches = set()
    owner._soft_abandon_streak = 0
    owner._branch_zero_win_streaks = {}
    owner._start_time = datetime.now()
    owner._hard_stagnation_escape_used = False

    owner._stagnation_detector = StagnationDetector(
        window_size=5,
        taxonomy=family_taxonomy,
    )
    owner._stagnation_signals = []
    owner._diagnostics = []

    owner._circuit_breaker = CircuitBreaker()
    owner._balance_exhausted = False
    owner._search_memory = CampaignSearchMemory(family_taxonomy=family_taxonomy)
    owner._research_log = CampaignResearchLog(str(campaign_dir))
    owner._saturation_analyzer = None
    owner._baseline_metrics = None
    owner._runtime_preflight_checked = False

    early_stop_controller = None
    if force_continue_early_stop:
        from scion.core.early_stop import EarlyStopController

        early_stop_controller = EarlyStopController(force_continue=True)
    owner._plateau = PlateauController(early_stop=early_stop_controller)
    owner._early_stop = owner._plateau.early_stop

    owner._journal = CampaignJournal(owner._registry)
    from scion.core.token_usage import TokenUsageTracker

    owner._token_tracker = TokenUsageTracker()
    if hasattr(llm_client, "set_token_tracker"):
        llm_client.set_token_tracker(owner._token_tracker)

    owner._failure_streak = {}
    owner._total_failures = {}
    owner._failure_lifecycle = FailureLifecycleService(
        failure_router=owner._failure_router,
        budget=owner._budget,
        failure_streak=owner._failure_streak,
        total_failures=owner._total_failures,
        branch_controller=owner._branch_ctrl,
        branch_hypotheses=owner._branch_hypotheses,
        branch_patches=owner._branch_patches,
        hypothesis_store=owner._hyp_store,
        branch_store=owner._branch_store,
        registry=owner._registry,
        campaign_id=owner._campaign_id,
        get_champion=lambda: owner._champion,
        record_hard_abandon=owner._record_hard_abandon,
    )

    owner._champion_lock = threading.Lock()
    owner._workspace_lifecycle = WorkspaceLifecycleService(
        materializer=owner._materializer,
        branch_controller=owner._branch_ctrl,
        branch_workspaces=owner._branch_workspaces,
        branch_patches=owner._branch_patches,
        champion_lock=owner._champion_lock,
        get_champion=lambda: owner._champion,
    )
    owner._weight_opt_coord = AsyncWeightOptCoordinator(owner)
    owner._weight_opt_committer = WeightOptCommitter(
        event_source=owner._weight_opt_coord,
        champion_lock=owner._champion_lock,
        get_champion=lambda: owner._champion,
        set_champion=lambda champion: setattr(owner, "_champion", champion),
        champion_store=owner._champion_store,
        branch_controller=owner._branch_ctrl,
        persist_branch_states=owner._persist_all_branch_states,
        registry=owner._registry,
        campaign_id=owner._campaign_id,
    )
    owner._promotion_lifecycle = PromotionLifecycleService(
        promotion_service=owner._promotion_service,
        branch_controller=owner._branch_ctrl,
        branch_workspaces=owner._branch_workspaces,
        branch_patches=owner._branch_patches,
        branch_current_hypothesis=owner._branch_current_hypothesis,
        step_history=owner._step_history,
        champion_lock=owner._champion_lock,
        get_champion=lambda: owner._champion,
        set_champion=lambda champion: setattr(owner, "_champion", champion),
        get_champion_store=lambda: owner._champion_store,
        hypothesis_store=owner._hyp_store,
        search_memory=owner._search_memory,
        get_weight_opt_coord=lambda: owner._weight_opt_coord,
        get_weight_opt_committer=lambda: owner._weight_opt_committer,
        get_parameter_search_execution=lambda: getattr(
            owner._spec.parameter_search,
            "execution",
            "async",
        ),
        get_round_num=lambda: owner._round_num,
        reset_promotion_counters=owner._reset_promotion_counters,
        set_rounds_since_last_promote=lambda value: setattr(
            owner,
            "_rounds_since_last_promote",
            value,
        ),
    )
    owner._decision_finalizer = DecisionFinalizer(
        branch_controller=owner._branch_ctrl,
        branch_store=owner._branch_store,
        hypothesis_store=owner._hyp_store,
        branch_workspaces=owner._branch_workspaces,
        branch_hypotheses=owner._branch_hypotheses,
        branch_patches=owner._branch_patches,
        branch_current_hypothesis=owner._branch_current_hypothesis,
        branch_zero_win_streaks=owner._branch_zero_win_streaks,
        prepare_promoted_champion=owner._prepare_promoted_champion,
        require_promotable_branch=owner._require_promotable_branch,
        commit_promote_plan=owner._commit_promote_plan,
        handle_failure=owner._handle_failure,
        record_hard_abandon=owner._record_hard_abandon,
        record_step_lineage=owner._record_step_lineage,
        decision_reason_codes_for=owner._decision_reason_codes_for,
        discard_branch_workspace=lambda branch_id: _workspace_service_for(
            owner
        ).discard_branch_workspace(branch_id),
        archive_workspace=owner._materializer.archive_workspace,
        cleanup_workspace=owner._materializer.cleanup,
        persist_branch_state=owner._persist_branch_state,
        reset_recent_abandoned_count=lambda: setattr(
            owner,
            "_recent_abandoned_count",
            0,
        ),
    )
    owner._evaluation_orchestrator = EvaluationOrchestrator(
        branch_controller=owner._branch_ctrl,
        champion_lock=owner._champion_lock,
        get_champion=lambda: owner._champion,
        branch_patches=owner._branch_patches,
        branch_workspaces=owner._branch_workspaces,
        branch_hypotheses=owner._branch_hypotheses,
        branch_current_hypothesis=owner._branch_current_hypothesis,
        experiment_protocol_provider=lambda: owner._experiment_protocol,
        feature_extractor=owner._feature_extractor,
        get_budget=lambda: owner._budget,
        decision_coordinator=owner._decision_coordinator,
        decision_reason_codes=owner._decision_reason_codes,
        campaign_id=owner._campaign_id,
        registry=owner._registry,
        materializer=owner._materializer,
        hypothesis_store=owner._hyp_store,
        persist_branch_state=owner._persist_branch_state,
        begin_status_progress=owner._begin_status_progress,
        end_status_progress=owner._end_status_progress,
        handle_failure=owner._handle_failure,
        increment_experiment_count=lambda: setattr(
            owner,
            "_n_experiments",
            owner._n_experiments + 1,
        ),
        increment_budget_used=lambda: setattr(
            owner._budget,
            "used",
            owner._budget.used + 1,
        ),
        increment_soft_abandon_streak=lambda: setattr(
            owner,
            "_soft_abandon_streak",
            owner._soft_abandon_streak + 1,
        ),
        frozen_budget_ledger=owner._frozen_budget_ledger,
    )
    owner._explore_step_pipeline = ExploreStepPipeline(
        branch_controller=owner._branch_ctrl,
        contract_gate=owner._contract_gate,
        verification_gate=owner._vgate,
        hypothesis_store=owner._hyp_store,
        registry=owner._registry,
        campaign_id=owner._campaign_id,
        get_champion=lambda: owner._champion,
        pending_hypotheses=owner._pending_hypotheses,
        branch_hypotheses=owner._branch_hypotheses,
        branch_patches=owner._branch_patches,
        branch_current_hypothesis=owner._branch_current_hypothesis,
        branch_workspaces=owner._branch_workspaces,
        failure_streak=owner._failure_streak,
        increment_round=owner._increment_round,
        increment_rounds_since_last_promote=owner._increment_rounds_since_last_promote,
        generate_hypothesis=owner._round1_generate_hypothesis,
        generate_code=owner._round2_generate_code,
        attempt_fix=owner._attempt_fix,
        handle_failure=owner._handle_failure,
        record_step=owner._record_step,
        setup_workspace=owner._setup_workspace,
        apply_patch=lambda branch, workspace, patch, **kwargs: _workspace_service_for(
            owner
        ).apply_patch(branch, workspace, patch, **kwargs),
        record_verification_pass=lambda branch, code_hash: _workspace_service_for(
            owner
        ).record_verification_pass(branch, code_hash),
        archive_failed_workspace=owner._archive_failed_workspace,
        evaluate=owner._evaluate,
        apply_decision_and_finalize=owner._apply_decision_and_finalize,
        decision_reason_codes_for=owner._decision_reason_codes_for,
        proposal_failure_detail_for=owner._proposal_failure_detail_for,
        proposal_session_ref_for=owner._proposal_session_ref_for,
    )
    owner._branch_step_runner = BranchStepRunner(
        branch_controller=owner._branch_ctrl,
        scheduler=owner._scheduler,
        champion_lock=owner._champion_lock,
        get_champion=lambda: owner._champion,
        branch_store=owner._branch_store,
        branch_workspaces=owner._branch_workspaces,
        branch_hypotheses=owner._branch_hypotheses,
        branch_patches=owner._branch_patches,
        branch_current_hypothesis=owner._branch_current_hypothesis,
        experiment_protocol_provider=lambda: owner._experiment_protocol,
        contract_gate=owner._contract_gate,
        verification_gate=owner._vgate,
        drain_weight_opt_events=owner._drain_weight_opt_events,
        should_stop=owner.should_stop,
        get_last_stop_reason=lambda: owner._last_stop_reason,
        tick_blocked_branches=owner._tick_blocked_branches,
        persist_branch_state=owner._persist_branch_state,
        record_hard_abandon=owner._record_hard_abandon,
        setup_workspace=owner._setup_workspace,
        apply_patch=lambda branch, workspace, patch, **kwargs: _workspace_service_for(
            owner
        ).apply_patch(branch, workspace, patch, **kwargs),
        record_verification_pass=lambda branch, code_hash: _workspace_service_for(
            owner
        ).record_verification_pass(branch, code_hash),
        evaluate=owner._evaluate,
        apply_decision_and_finalize=owner._apply_decision_and_finalize,
        record_step=owner._record_step,
        decision_reason_codes_for=owner._decision_reason_codes_for,
        run_explore_step=owner._explore_step_pipeline.run,
        run_eval_step_callback=owner._run_eval_step,
        run_reconcile_step_callback=owner._run_reconcile_step,
        increment_round=owner._increment_round,
        increment_rounds_since_last_promote=owner._increment_rounds_since_last_promote,
        hypothesis_store=owner._hyp_store,
    )
    owner._proposal_pipeline = ProposalPipeline(
        creative=owner._creative,
        problem_runtime=owner._problem_runtime,
        classifier=owner._classifier,
        branch_controller=owner._branch_ctrl,
        hypothesis_store=owner._hyp_store,
        branch_workspaces=owner._branch_workspaces,
        champion_lock=owner._champion_lock,
        get_champion=lambda: owner._champion,
        step_history=owner._step_history,
        failure_streak=owner._failure_streak,
        consume_forced_locus=owner._consume_forced_locus,
        search_memory=owner._search_memory,
        get_saturation_analyzer=lambda: owner._saturation_analyzer,
        get_baseline_metrics=lambda: owner._baseline_metrics,
        get_latest_weight_opt_result=lambda: owner._latest_weight_opt_result,
        research_log=owner._research_log,
        handle_failure=owner._handle_failure,
        circuit_breaker=owner._circuit_breaker,
        mark_balance_exhausted=lambda: setattr(owner, "_balance_exhausted", True),
        lineage_registry=owner._registry,
        use_agentic_proposal=use_agentic_proposal,
        agentic_artifact_dir=agentic_artifact_dir,
        agentic_session_timeout_sec=agentic_session_timeout_sec,
    )
    owner._governance = CampaignGovernanceService(
        branch_controller=owner._branch_ctrl,
        termination_checker=owner._term_checker,
        plateau=owner._plateau,
        stagnation_detector=owner._stagnation_detector,
        get_step_history=lambda: owner._step_history,
        get_failure_streak=lambda: owner._failure_streak,
        diagnostics=owner._diagnostics,
        hard_abandon_counted_branches=lambda: owner._hard_abandon_counted_branches,
        get_saturation_analyzer=lambda: owner._saturation_analyzer,
        get_baseline_metrics=lambda: owner._baseline_metrics,
        get_stagnation_signals=lambda: owner._stagnation_signals,
        set_stagnation_signals=lambda signals: setattr(
            owner,
            "_stagnation_signals",
            signals,
        ),
        get_round_num=lambda: owner._round_num,
        get_rounds_since_last_promote=lambda: owner._rounds_since_last_promote,
        get_n_experiments=lambda: owner._n_experiments,
        get_start_time=lambda: owner._start_time,
        get_recent_abandoned_count=lambda: owner._recent_abandoned_count,
        set_recent_abandoned_count=lambda value: setattr(
            owner,
            "_recent_abandoned_count",
            value,
        ),
        get_hard_stagnation_escape_used=lambda: owner._hard_stagnation_escape_used,
        set_hard_stagnation_escape_used=lambda value: setattr(
            owner,
            "_hard_stagnation_escape_used",
            value,
        ),
        get_soft_abandon_streak=lambda: owner._soft_abandon_streak,
        set_soft_abandon_streak=lambda value: setattr(
            owner,
            "_soft_abandon_streak",
            value,
        ),
        get_operator_categories=lambda: list(
            getattr(owner._spec, "operator_categories", [])
        ),
        set_last_stop_reason=lambda reason: setattr(
            owner,
            "_last_stop_reason",
            reason,
        ),
    )
    owner._campaign_loop = CampaignLoop(
        write_status=lambda **kwargs: owner._write_status(**kwargs),
        drain_weight_opt_events=lambda: owner._drain_weight_opt_events(),
        should_stop=lambda: owner.should_stop(),
        get_last_stop_reason=lambda: owner._last_stop_reason,
        set_last_stop_reason=lambda reason: setattr(owner, "_last_stop_reason", reason),
        get_circuit_breaker=lambda: owner._circuit_breaker,
        circuit_breaker_threshold=MAX_CONSECUTIVE_LLM_FAILURES,
        run_one_step=lambda: owner.run_one_step(),
        run_stagnation_check=lambda: owner._run_stagnation_check(),
        check_soft_stagnation=lambda: owner._check_soft_stagnation(),
        write_campaign_summary=lambda: owner._write_campaign_summary(),
        terminalize_active_branches=lambda reason: owner._terminalize_active_branches(
            reason
        ),
        get_final_wait_timeout=lambda: getattr(
            owner._spec.parameter_search,
            "final_wait_timeout_sec",
            600.0,
        ),
        wait_weight_opt_all=lambda timeout: owner._weight_opt_coord.wait_all(
            timeout=timeout
        ),
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


def _persist_initial_champion(owner: Any) -> None:
    """Persist the base champion so campaign evidence has a real v1 anchor."""
    if owner._champion_store.get_current() is not None:
        return

    champion = owner._champion
    source_path = os.path.abspath(champion.code_snapshot_path)
    champions_root = os.path.abspath(str(owner._materializer._champions_dir))
    snapshot_path = source_path

    # Avoid recursively copying a problem root into a campaign directory that
    # lives inside that same root. The DB anchor is still useful in that layout.
    if os.path.commonpath([source_path, champions_root]) != source_path:
        snapshot_path = owner._materializer.create_champion_snapshot(
            champion,
            str(owner._materializer._champions_dir),
        )

    persisted = ChampionState(
        version=champion.version,
        operator_pool=_normalize_operator_pool(champion.operator_pool),
        solver_config_hash=champion.solver_config_hash,
        code_snapshot_path=snapshot_path,
        code_snapshot_hash=owner._materializer.compute_snapshot_hash(snapshot_path),
        promotion_experiment_id=champion.promotion_experiment_id,
        promoted_at=champion.promoted_at,
        weight_revision=champion.weight_revision,
    )
    owner._champion_store.promote(persisted)
    owner._champion = persisted


def _normalize_operator_pool(operator_pool: dict[str, Any]) -> dict[str, OperatorConfig]:
    """Normalize legacy name->weight pools before persistence."""
    normalized: dict[str, OperatorConfig] = {}
    for name, cfg in (operator_pool or {}).items():
        if isinstance(cfg, OperatorConfig):
            normalized[name] = cfg
            continue
        required_attrs = ("name", "file_path", "category", "weight", "class_name")
        if all(hasattr(cfg, attr) for attr in required_attrs):
            normalized[name] = OperatorConfig(
                name=cfg.name,
                file_path=cfg.file_path,
                category=cfg.category,
                weight=float(cfg.weight),
                class_name=cfg.class_name,
            )
            continue
        if isinstance(cfg, dict):
            normalized[name] = OperatorConfig(
                name=str(cfg.get("name", name)),
                file_path=str(cfg.get("file_path", f"operators/{name}.py")),
                category=str(cfg.get("category", name)),
                weight=float(cfg.get("weight", 1.0)),
                class_name=str(cfg.get("class_name", name)),
            )
            continue
        normalized[name] = OperatorConfig(
            name=name,
            file_path=f"operators/{name}.py",
            category=name,
            weight=float(cfg),
            class_name=name,
        )
    return normalized
