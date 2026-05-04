"""CampaignManager — main loop integrating all Scion modules (Phase 5)."""
from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Tuple

from scion.config.problem import ProtocolConfig, ProblemSpec, SplitManifest, SeedLedgerConfig
from scion.verification.gate import VerificationGate
from scion.contract.gate import ContractGate
from scion.core.branch_step_runner import BranchStepRunner
from scion.core.branch import BranchController
from scion.core.campaign_adapters import (
    _branch_step_runner_for,
    _evaluation_orchestrator_for,
    _explore_step_pipeline_for,
    _lookup_decision_reason_codes,
    _workspace_service_for,
)
from scion.core.campaign_governance import CampaignGovernanceService
from scion.core.campaign_loop import CampaignLoop
from scion.core.decision_coordinator import DecisionCoordinator
from scion.core.decision_finalizer import DecisionFinalizer
from scion.core.evidence_recorder import EvidenceRecorder
from scion.core.evaluation_orchestrator import EvaluationOrchestrator
from scion.core.explore_step_pipeline import ExploreStepPipeline, build_verification_detail
from scion.core.features import SafeFeatureExtractor, BudgetState
from scion.core.frozen_budget import FrozenBudgetLedger
from scion.core.failure_lifecycle import FailureLifecycleService
from scion.core.models import (
    Branch, BranchState, CanaryResult, ChampionState, ContractResult,
    Decision, ExperimentStage, FailureEvent, HypothesisProposal, HypothesisRecord,
    PatchProposal, ProtocolResult, StepRecord, VerificationResult,
)
from scion.core.promotion_lifecycle import PromotionLifecycleService
from scion.core.promotion_service import PromotionPlan, PromotionService
from scion.core.proposal_pipeline import ProposalPipeline
from scion.core.scheduler import Scheduler
from scion.core.step_result import StepResult
from scion.core.status_reporter import StatusReporter
from scion.core.termination import TerminationChecker, TerminationConfig
from scion.core.stagnation import StagnationDetector, StagnationSignal
from scion.core.verification_factory import CampaignVerificationFactory
from scion.core.weight_opt_committer import WeightOptCommitter
from scion.core.workspace_lifecycle import WorkspaceLifecycleService
from scion.failure.router import FailureRouter, RetryConfig
from scion.proposal.engine import CreativeLayer
from scion.proposal.search_memory import CampaignSearchMemory
from scion.proposal.saturation import ChampionSaturationAnalyzer, render_saturation_signals
from scion.runtime.workspace import WorkspaceMaterializer
from scion.lineage.registry import LineageRegistry
from scion.lineage.branch_store import BranchStore, HypothesisStore
from scion.lineage.champion_store import ChampionStore

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Circuit breaker
# ---------------------------------------------------------------------------

MAX_CONSECUTIVE_LLM_FAILURES = 3


class CircuitBreaker:
    """Trips after N consecutive LLM failures to prevent budget burn."""

    def __init__(self, threshold: int = MAX_CONSECUTIVE_LLM_FAILURES) -> None:
        self._threshold = threshold
        self._consecutive_failures = 0
        self._last_failure_detail = ""

    def record_success(self) -> None:
        self._consecutive_failures = 0

    def record_failure(self, detail: str) -> bool:
        """Record a failure. Returns True if the circuit has just tripped."""
        self._consecutive_failures += 1
        self._last_failure_detail = detail
        return self._consecutive_failures >= self._threshold

    @property
    def is_tripped(self) -> bool:
        return self._consecutive_failures >= self._threshold

    @property
    def last_failure_detail(self) -> str:
        return self._last_failure_detail

# ---------------------------------------------------------------------------
# Campaign Manager
# ---------------------------------------------------------------------------

class CampaignManager:
    """Orchestrates the full 14-step Scion campaign loop.

    Dependencies:
        problem_spec       — static problem definition
        protocol_config    — gate thresholds (screening/validation/frozen)
        split_manifest     — case splits
        seed_ledger        — RNG seeds per stage
        llm_client         — LLMClient or MockLLMClient
        champion           — initial ChampionState
        campaign_dir       — root directory for workspaces/snapshots

    Optional overrides (useful for testing):
        verification_gate  — custom VerificationGate; otherwise built from
                             problem/runtime configuration
        experiment_protocol — custom ExperimentProtocol; defaults to None (no runner)
        budget             — BudgetState; defaults to max_rounds budget
        termination_config — TerminationConfig; defaults to library defaults
        retry_config       — RetryConfig; defaults to library defaults
    """

    def __init__(
        self,
        problem_spec: ProblemSpec,
        protocol_config: ProtocolConfig,
        split_manifest: SplitManifest,
        seed_ledger: SeedLedgerConfig,
        llm_client: Any,
        champion: ChampionState,
        campaign_dir: str,
        *,
        verification_gate: Optional[Any] = None,
        experiment_protocol: Optional[Any] = None,
        budget: Optional[BudgetState] = None,
        termination_config: Optional[TerminationConfig] = None,
        retry_config: Optional[RetryConfig] = None,
        adapter: Optional[Any] = None,
        operator_execute_signature: Optional[str] = None,
        objective_lower_bounds: Optional[Dict[str, float]] = None,
        use_objective_lower_bounds_for_early_stop: bool = False,
        force_continue_early_stop: bool = False,
        allow_non_strict_runtime_verification: bool = False,
    ) -> None:
        # v0.3 B3: ProblemRuntime owns problem_spec + adapter + ContextManager.
        # Instantiate FIRST so the backward-compat properties below (_spec,
        # _adapter, _ctx_manager) can proxy to it.
        from scion.core.problem_runtime import ProblemRuntime
        self._problem_runtime = ProblemRuntime(problem_spec=problem_spec, adapter=adapter)
        self._protocol_config = protocol_config
        self._split_manifest = split_manifest
        self._seed_ledger = seed_ledger
        self._llm_client = llm_client
        self._champion = champion
        self._campaign_dir = campaign_dir
        self._campaign_id = str(uuid.uuid4())
        self._status_reporter = StatusReporter(campaign_dir)
        self._last_status_result: Dict[str, Any] | None = None
        self._current_status_progress: Dict[str, Any] | None = None
        self._last_stop_reason: str | None = None
        self._objective_lower_bounds = objective_lower_bounds
        self._use_objective_lower_bounds_for_early_stop = use_objective_lower_bounds_for_early_stop

        # Sub-modules
        self._branch_ctrl = BranchController()
        self._scheduler = Scheduler()
        self._contract_gate = ContractGate(
            problem_spec,
            operator_execute_signature=operator_execute_signature,
        )
        self._decision_coordinator = DecisionCoordinator(config=protocol_config)
        self._feature_extractor = SafeFeatureExtractor()
        self._failure_router = FailureRouter(retry_config or RetryConfig())
        self._creative = CreativeLayer(
            llm_client,
            trace_dir=f"{campaign_dir}/llm_traces",
        )
        # _ctx_manager now backed by ProblemRuntime (see property below).

        # O1: Hypothesis family classifier (keyword-only if no LLM client)
        from scion.proposal.classifier import HypothesisFamilyClassifier
        _family_taxonomy = getattr(self._spec, "family_taxonomy", None)
        self._classifier = HypothesisFamilyClassifier(
            llm_client=llm_client,
            taxonomy=getattr(_family_taxonomy, "families", None),
            taxonomy_version=getattr(_family_taxonomy, "version", "v1"),
        )
        self._materializer = WorkspaceMaterializer(
            campaign_dir,
            frozen_patterns=frozenset(
                problem_spec.search_space.frozen
            ) if problem_spec.search_space.frozen else None,
        )
        import os as _os2
        self._experiment_protocol = experiment_protocol  # may be None (no runner)
        _os2.makedirs(str(campaign_dir) + "/metrics", exist_ok=True)
        self._vgate = CampaignVerificationFactory.build(
            problem_spec=problem_spec,
            verification_gate=verification_gate,
            experiment_protocol=experiment_protocol,
            campaign_dir=str(campaign_dir),
            adapter=adapter,
            operator_execute_signature=operator_execute_signature,
            allow_non_strict_runtime_verification=allow_non_strict_runtime_verification,
        )
        if hasattr(self._experiment_protocol, "set_progress_callback"):
            self._experiment_protocol.set_progress_callback(self._on_protocol_progress)

        def _read_promotion_weights(registry_path: str) -> Dict[str, float]:
            if self._spec.parameter_search.enabled and self._experiment_protocol is not None:
                from scion.runtime.pool_manager import read_weights
                return read_weights(registry_path)
            return {}

        self._promotion_service = PromotionService(
            snapshot_root=self._materializer._champions_dir,
            materializer=self._materializer,
            before_commit=self._begin_promotion_commit,
            commit_champion=self._commit_promoted_champion_state,
            persist_champion=self._persist_promoted_champion,
            promote_branch=self._transition_promoted_branch,
            mark_stale=self._branch_ctrl.mark_all_stale,
            persist_branch_states=self._persist_all_branch_states,
            on_promoted_branch=self._record_promoted_branch,
            read_weights_fn=_read_promotion_weights,
        )

        # Lineage registry (SQLite, WAL mode)
        import os as _os
        _os.makedirs(campaign_dir, exist_ok=True)
        self._registry = LineageRegistry(
            _os.path.join(campaign_dir, "scion.db")
        )
        self._hyp_store = HypothesisStore(self._registry)
        self._branch_store = BranchStore(self._registry)
        self._evidence_recorder = EvidenceRecorder(
            campaign_id=self._campaign_id,
            campaign_dir=campaign_dir,
            status_reporter=self._status_reporter,
            registry=self._registry,
            state_provider=self.get_state,
            model_id=getattr(llm_client, "model", None),
            protocol_version=getattr(protocol_config, "version", None),
            family_taxonomy=getattr(_family_taxonomy, "families", None),
        )
        self._frozen_budget_ledger = FrozenBudgetLedger(
            max_uses=protocol_config.frozen.max_uses_per_campaign,
            registry=self._registry,
            campaign_id=self._campaign_id,
        )

        # J6: Champion store for persistence
        self._champion_store = ChampionStore(
            _os.path.join(campaign_dir, "scion.db"),
            _os.path.join(campaign_dir, "champions"),
        )

        # Per-branch transient state
        self._branch_workspaces: Dict[str, str] = {}       # branch_id → workspace path
        self._branch_hypotheses: Dict[str, HypothesisProposal] = {}
        self._branch_patches: Dict[str, PatchProposal] = {}
        self._decision_reason_codes: Dict[str, Tuple[str, ...]] = {}
        # T04: branch_id → the canonical HypothesisRecord for the current screening cycle
        # (screening → validation → frozen all share the same record)
        self._branch_current_hypothesis: Dict[str, HypothesisRecord] = {}

        # Pending hypotheses: branch_id → (hypothesis, h_record, failure_detail)
        # A code-failed hypothesis gets ONE retry for code gen in the next round.
        self._pending_hypotheses: Dict[str, Tuple[HypothesisProposal, HypothesisRecord, str]] = {}

        # Hypothesis memory persisted to SQLite via HypothesisStore
        # (replaces in-memory _active_hypotheses and _blacklist lists)

        # Experiment history — full record of every completed explore step
        self._step_history: List[StepRecord] = []
        self._round_num: int = 0

        # Budget / termination
        self._term_checker = TerminationChecker(termination_config or TerminationConfig())
        self._budget = budget or BudgetState(total=1000, used=0)
        self._n_experiments = 0
        self._recent_abandoned_count = 0
        self._hard_abandon_counted_branches: set[str] = set()
        self._soft_abandon_streak: int = 0   # I1: T4 win_rate<0.3 consecutive count (independent of hard stagnation)
        self._branch_zero_win_streaks: Dict[str, int] = {}  # branch_id → consecutive 0-win-rate rounds
        self._start_time = datetime.now()
        # _forced_next_locus / _rounds_since_last_promote now live in PlateauController;
        # backward-compat properties defined below expose them as attributes.
        self._hard_stagnation_escape_used: bool = False  # I4: one-time escape before terminate

        # Stagnation / diagnosis (T25/T23)
        _taxonomy = getattr(getattr(self._spec, 'family_taxonomy', None), 'families', None)
        self._stagnation_detector = StagnationDetector(window_size=5, taxonomy=_taxonomy)
        self._stagnation_signals: List[StagnationSignal] = []
        self._diagnostics: List[Dict[str, Any]] = []

        # Circuit breaker (T29)
        self._circuit_breaker = CircuitBreaker()
        self._balance_exhausted: bool = False  # T6: set on 403 balance-exhausted errors

        # J1: Campaign search memory (cross-branch)
        self._search_memory = CampaignSearchMemory(family_taxonomy=_taxonomy)

        # J-patch: Campaign research log (cross-branch trajectory from SQLite)
        from scion.proposal.research_log import CampaignResearchLog
        self._research_log = CampaignResearchLog(str(campaign_dir))

        # J2: Saturation analyzer (initialized lazily after first screening with data)
        self._saturation_analyzer: Optional[ChampionSaturationAnalyzer] = None
        self._baseline_metrics: Optional[Dict[str, float]] = None

        # W3 / v0.3 B1: PlateauController — idle counter + early-stop + forced locus
        from scion.core.early_stop import EarlyStopController
        from scion.core.plateau_controller import PlateauController
        early_stop_controller = (
            EarlyStopController(force_continue=True)
            if force_continue_early_stop
            else None
        )
        self._plateau = PlateauController(early_stop=early_stop_controller)
        # Legacy attribute names kept as thin passthroughs for now (branch_store
        # and tests may still read them). Prefer self._plateau going forward.
        self._early_stop = self._plateau.early_stop

        # W9: Campaign journal (lineage-derived)
        from scion.proposal.journal import CampaignJournal
        self._journal = CampaignJournal(self._registry)

        # W13: Token usage tracker
        from scion.core.token_usage import TokenUsageTracker
        self._token_tracker = TokenUsageTracker()
        if hasattr(llm_client, 'set_token_tracker'):
            llm_client.set_token_tracker(self._token_tracker)

        # Sprint H2 T1: Campaign-level failure counters
        self._failure_streak: Dict[str, int] = {}   # failure_code → consecutive count
        self._total_failures: Dict[str, int] = {}   # failure_code → cumulative count
        self._failure_lifecycle = FailureLifecycleService(
            failure_router=self._failure_router,
            budget=self._budget,
            failure_streak=self._failure_streak,
            total_failures=self._total_failures,
            branch_controller=self._branch_ctrl,
            branch_hypotheses=self._branch_hypotheses,
            branch_patches=self._branch_patches,
            hypothesis_store=self._hyp_store,
            branch_store=self._branch_store,
            registry=self._registry,
            campaign_id=self._campaign_id,
            get_champion=lambda: self._champion,
            record_hard_abandon=self._record_hard_abandon,
        )

        # Async weight optimization (R3/R5) — v0.3 B2 coordinator owns
        # _pending_threads and _latest_result. Backward-compat properties
        # below expose them as _pending_weight_opt_threads /
        # _latest_weight_opt_result for tests and lineage paths.
        self._champion_lock = threading.Lock()
        self._workspace_lifecycle = WorkspaceLifecycleService(
            materializer=self._materializer,
            branch_controller=self._branch_ctrl,
            branch_workspaces=self._branch_workspaces,
            branch_patches=self._branch_patches,
            champion_lock=self._champion_lock,
            get_champion=lambda: self._champion,
        )
        from scion.core.async_weight_opt import AsyncWeightOptCoordinator
        self._weight_opt_coord = AsyncWeightOptCoordinator(self)
        self._weight_opt_committer = WeightOptCommitter(
            event_source=self._weight_opt_coord,
            champion_lock=self._champion_lock,
            get_champion=lambda: self._champion,
            set_champion=lambda champion: setattr(self, "_champion", champion),
            champion_store=self._champion_store,
            branch_controller=self._branch_ctrl,
            persist_branch_states=self._persist_all_branch_states,
            registry=self._registry,
            campaign_id=self._campaign_id,
        )
        self._promotion_lifecycle = PromotionLifecycleService(
            promotion_service=self._promotion_service,
            branch_controller=self._branch_ctrl,
            branch_workspaces=self._branch_workspaces,
            branch_patches=self._branch_patches,
            branch_current_hypothesis=self._branch_current_hypothesis,
            step_history=self._step_history,
            champion_lock=self._champion_lock,
            get_champion=lambda: self._champion,
            set_champion=lambda champion: setattr(self, "_champion", champion),
            get_champion_store=lambda: self._champion_store,
            hypothesis_store=self._hyp_store,
            search_memory=self._search_memory,
            get_weight_opt_coord=lambda: self._weight_opt_coord,
            get_weight_opt_committer=lambda: self._weight_opt_committer,
            get_parameter_search_execution=lambda: getattr(
                self._spec.parameter_search,
                "execution",
                "async",
            ),
            get_round_num=lambda: self._round_num,
            reset_promotion_counters=self._reset_promotion_counters,
            set_rounds_since_last_promote=lambda value: setattr(
                self,
                "_rounds_since_last_promote",
                value,
            ),
        )
        self._decision_finalizer = DecisionFinalizer(
            branch_controller=self._branch_ctrl,
            branch_store=self._branch_store,
            hypothesis_store=self._hyp_store,
            branch_workspaces=self._branch_workspaces,
            branch_hypotheses=self._branch_hypotheses,
            branch_patches=self._branch_patches,
            branch_current_hypothesis=self._branch_current_hypothesis,
            branch_zero_win_streaks=self._branch_zero_win_streaks,
            prepare_promoted_champion=self._prepare_promoted_champion,
            require_promotable_branch=self._require_promotable_branch,
            commit_promote_plan=self._commit_promote_plan,
            handle_failure=self._handle_failure,
            record_hard_abandon=self._record_hard_abandon,
            record_step_lineage=self._record_step_lineage,
            decision_reason_codes_for=self._decision_reason_codes_for,
            discard_branch_workspace=lambda branch_id: _workspace_service_for(
                self
            ).discard_branch_workspace(branch_id),
            archive_workspace=self._materializer.archive_workspace,
            cleanup_workspace=self._materializer.cleanup,
            persist_branch_state=self._persist_branch_state,
            reset_recent_abandoned_count=lambda: setattr(
                self,
                "_recent_abandoned_count",
                0,
            ),
        )
        self._evaluation_orchestrator = EvaluationOrchestrator(
            branch_controller=self._branch_ctrl,
            champion_lock=self._champion_lock,
            get_champion=lambda: self._champion,
            branch_patches=self._branch_patches,
            branch_workspaces=self._branch_workspaces,
            branch_hypotheses=self._branch_hypotheses,
            branch_current_hypothesis=self._branch_current_hypothesis,
            experiment_protocol_provider=lambda: self._experiment_protocol,
            feature_extractor=self._feature_extractor,
            get_budget=lambda: self._budget,
            decision_coordinator=self._decision_coordinator,
            decision_reason_codes=self._decision_reason_codes,
            campaign_id=self._campaign_id,
            registry=self._registry,
            materializer=self._materializer,
            hypothesis_store=self._hyp_store,
            persist_branch_state=self._persist_branch_state,
            begin_status_progress=self._begin_status_progress,
            end_status_progress=self._end_status_progress,
            handle_failure=self._handle_failure,
            increment_experiment_count=lambda: setattr(
                self,
                "_n_experiments",
                self._n_experiments + 1,
            ),
            increment_budget_used=lambda: setattr(
                self._budget,
                "used",
                self._budget.used + 1,
            ),
            increment_soft_abandon_streak=lambda: setattr(
                self,
                "_soft_abandon_streak",
                self._soft_abandon_streak + 1,
            ),
            frozen_budget_ledger=self._frozen_budget_ledger,
        )
        self._explore_step_pipeline = ExploreStepPipeline(
            branch_controller=self._branch_ctrl,
            contract_gate=self._contract_gate,
            verification_gate=self._vgate,
            hypothesis_store=self._hyp_store,
            registry=self._registry,
            campaign_id=self._campaign_id,
            get_champion=lambda: self._champion,
            pending_hypotheses=self._pending_hypotheses,
            branch_hypotheses=self._branch_hypotheses,
            branch_patches=self._branch_patches,
            branch_current_hypothesis=self._branch_current_hypothesis,
            branch_workspaces=self._branch_workspaces,
            failure_streak=self._failure_streak,
            increment_round=self._increment_round,
            increment_rounds_since_last_promote=self._increment_rounds_since_last_promote,
            generate_hypothesis=self._round1_generate_hypothesis,
            generate_code=self._round2_generate_code,
            attempt_fix=self._attempt_fix,
            handle_failure=self._handle_failure,
            record_step=self._record_step,
            setup_workspace=self._setup_workspace,
            apply_patch=lambda branch, workspace, patch, **kwargs: _workspace_service_for(
                self
            ).apply_patch(branch, workspace, patch, **kwargs),
            record_verification_pass=lambda branch, code_hash: _workspace_service_for(
                self
            ).record_verification_pass(branch, code_hash),
            archive_failed_workspace=self._archive_failed_workspace,
            evaluate=self._evaluate,
            apply_decision_and_finalize=self._apply_decision_and_finalize,
            decision_reason_codes_for=self._decision_reason_codes_for,
            proposal_failure_detail_for=self._proposal_failure_detail_for,
        )
        self._branch_step_runner = BranchStepRunner(
            branch_controller=self._branch_ctrl,
            scheduler=self._scheduler,
            champion_lock=self._champion_lock,
            get_champion=lambda: self._champion,
            branch_store=self._branch_store,
            branch_workspaces=self._branch_workspaces,
            branch_hypotheses=self._branch_hypotheses,
            branch_patches=self._branch_patches,
            branch_current_hypothesis=self._branch_current_hypothesis,
            experiment_protocol_provider=lambda: self._experiment_protocol,
            contract_gate=self._contract_gate,
            verification_gate=self._vgate,
            drain_weight_opt_events=self._drain_weight_opt_events,
            should_stop=self.should_stop,
            get_last_stop_reason=lambda: self._last_stop_reason,
            tick_blocked_branches=self._tick_blocked_branches,
            persist_branch_state=self._persist_branch_state,
            record_hard_abandon=self._record_hard_abandon,
            setup_workspace=self._setup_workspace,
            apply_patch=lambda branch, workspace, patch, **kwargs: _workspace_service_for(
                self
            ).apply_patch(branch, workspace, patch, **kwargs),
            record_verification_pass=lambda branch, code_hash: _workspace_service_for(
                self
            ).record_verification_pass(branch, code_hash),
            evaluate=self._evaluate,
            apply_decision_and_finalize=self._apply_decision_and_finalize,
            record_step=self._record_step,
            decision_reason_codes_for=self._decision_reason_codes_for,
            run_explore_step=self._explore_step_pipeline.run,
            run_eval_step_callback=self._run_eval_step,
            run_reconcile_step_callback=self._run_reconcile_step,
            increment_round=self._increment_round,
            increment_rounds_since_last_promote=self._increment_rounds_since_last_promote,
            hypothesis_store=self._hyp_store,
        )
        self._proposal_pipeline = ProposalPipeline(
            creative=self._creative,
            problem_runtime=self._problem_runtime,
            classifier=self._classifier,
            branch_controller=self._branch_ctrl,
            hypothesis_store=self._hyp_store,
            branch_workspaces=self._branch_workspaces,
            champion_lock=self._champion_lock,
            get_champion=lambda: self._champion,
            step_history=self._step_history,
            failure_streak=self._failure_streak,
            consume_forced_locus=self._consume_forced_locus,
            search_memory=self._search_memory,
            get_saturation_analyzer=lambda: self._saturation_analyzer,
            get_baseline_metrics=lambda: self._baseline_metrics,
            get_latest_weight_opt_result=lambda: self._latest_weight_opt_result,
            research_log=self._research_log,
            handle_failure=self._handle_failure,
            circuit_breaker=self._circuit_breaker,
            mark_balance_exhausted=lambda: setattr(self, "_balance_exhausted", True),
        )
        self._governance = CampaignGovernanceService(
            branch_controller=self._branch_ctrl,
            termination_checker=self._term_checker,
            plateau=self._plateau,
            stagnation_detector=self._stagnation_detector,
            get_step_history=lambda: self._step_history,
            get_failure_streak=lambda: self._failure_streak,
            diagnostics=self._diagnostics,
            hard_abandon_counted_branches=lambda: self._hard_abandon_counted_branches,
            get_saturation_analyzer=lambda: self._saturation_analyzer,
            get_baseline_metrics=lambda: self._baseline_metrics,
            get_stagnation_signals=lambda: self._stagnation_signals,
            set_stagnation_signals=lambda signals: setattr(
                self,
                "_stagnation_signals",
                signals,
            ),
            get_round_num=lambda: self._round_num,
            get_rounds_since_last_promote=lambda: self._rounds_since_last_promote,
            get_n_experiments=lambda: self._n_experiments,
            get_start_time=lambda: self._start_time,
            get_recent_abandoned_count=lambda: self._recent_abandoned_count,
            set_recent_abandoned_count=lambda value: setattr(
                self,
                "_recent_abandoned_count",
                value,
            ),
            get_hard_stagnation_escape_used=lambda: self._hard_stagnation_escape_used,
            set_hard_stagnation_escape_used=lambda value: setattr(
                self,
                "_hard_stagnation_escape_used",
                value,
            ),
            get_soft_abandon_streak=lambda: self._soft_abandon_streak,
            set_soft_abandon_streak=lambda value: setattr(
                self,
                "_soft_abandon_streak",
                value,
            ),
            get_operator_categories=lambda: list(
                getattr(self._spec, "operator_categories", [])
            ),
            set_last_stop_reason=lambda reason: setattr(
                self,
                "_last_stop_reason",
                reason,
            ),
        )
        self._campaign_loop = CampaignLoop(
            write_status=lambda **kwargs: self._write_status(**kwargs),
            drain_weight_opt_events=lambda: self._drain_weight_opt_events(),
            should_stop=lambda: self.should_stop(),
            get_last_stop_reason=lambda: self._last_stop_reason,
            set_last_stop_reason=lambda reason: setattr(self, "_last_stop_reason", reason),
            get_circuit_breaker=lambda: self._circuit_breaker,
            circuit_breaker_threshold=MAX_CONSECUTIVE_LLM_FAILURES,
            run_one_step=lambda: self.run_one_step(),
            run_stagnation_check=lambda: self._run_stagnation_check(),
            check_soft_stagnation=lambda: self._check_soft_stagnation(),
            write_campaign_summary=lambda: self._write_campaign_summary(),
            get_final_wait_timeout=lambda: getattr(
                self._spec.parameter_search,
                "final_wait_timeout_sec",
                600.0,
            ),
            wait_weight_opt_all=lambda timeout: self._weight_opt_coord.wait_all(
                timeout=timeout
            ),
        )

    # ------------------------------------------------------------------
    # Backward-compat properties for attributes now owned by PlateauController.
    # External callers (tests, branch_store) still read these by name.
    # ------------------------------------------------------------------

    @property
    def _rounds_since_last_promote(self) -> int:
        return self._plateau.rounds_since_last_promote

    @_rounds_since_last_promote.setter
    def _rounds_since_last_promote(self, value: int) -> None:
        self._plateau._rounds_since_last_promote = value

    @property
    def _forced_next_locus(self) -> Optional[str]:
        return self._plateau.forced_next_locus

    @_forced_next_locus.setter
    def _forced_next_locus(self, value: Optional[str]) -> None:
        self._plateau._forced_next_locus = value

    # ------------------------------------------------------------------
    # Backward-compat properties for attributes now owned by
    # AsyncWeightOptCoordinator (v0.3 B2). Tests and lineage paths read
    # these by name.
    # ------------------------------------------------------------------

    @property
    def _pending_weight_opt_threads(self) -> List[threading.Thread]:
        return self._weight_opt_coord.pending_threads

    @property
    def _latest_weight_opt_result(self) -> Optional[Any]:
        return self._weight_opt_coord.latest_result

    @_latest_weight_opt_result.setter
    def _latest_weight_opt_result(self, value: Optional[Any]) -> None:
        self._weight_opt_coord.latest_result = value

    # ------------------------------------------------------------------
    # Backward-compat properties for attributes now owned by
    # ProblemRuntime (v0.3 B3). Tests and internal code read these by
    # name (e.g. ``cm._spec``, ``cm._ctx_manager``).
    # ------------------------------------------------------------------

    @property
    def _spec(self):
        return self._problem_runtime.spec

    @_spec.setter
    def _spec(self, value):
        self._problem_runtime._spec = value

    @property
    def _adapter(self):
        return self._problem_runtime.adapter

    @_adapter.setter
    def _adapter(self, value):
        self._problem_runtime._adapter = value

    @property
    def _ctx_manager(self):
        return self._problem_runtime.ctx_manager

    @_ctx_manager.setter
    def _ctx_manager(self, value):
        self._problem_runtime._ctx_manager = value

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def _record_step(self, step: StepRecord) -> None:
        """Record a completed step and update search memory (J1)."""
        self._evidence_recorder.record_step(
            step,
            self._step_history,
            search_memory=self._search_memory,
        )
        # J2: Lazily initialize baseline metrics from first champion-side data
        if self._baseline_metrics is None and step.protocol_result is not None:
            from scion.proposal.saturation import extract_champion_metrics_from_step
            _pf_len = len(step.protocol_result.pair_feedback) if step.protocol_result.pair_feedback else 0
            logger.info("[SATURATION DEBUG] R%d stage=%s pair_feedback_len=%d", step.round_num, step.protocol_result.stage, _pf_len)
            metrics = extract_champion_metrics_from_step(step)
            if metrics:
                logger.info("[SATURATION] Baseline initialized: metrics=%s", metrics)
                self._baseline_metrics = metrics
                self._saturation_analyzer = ChampionSaturationAnalyzer(
                    metrics,
                    lower_bounds=(
                        self._objective_lower_bounds
                        if self._use_objective_lower_bounds_for_early_stop
                        else None
                    ),
                )
            else:
                logger.info("[SATURATION DEBUG] extract returned None for stage=%s", step.protocol_result.stage)

    def run(self, max_rounds: int = 1000) -> None:
        """Run the campaign until a termination condition is met."""
        self._campaign_loop.run(max_rounds=max_rounds)

    def run_one_step(self) -> StepResult:
        """Execute one campaign step and return a StepResult."""
        return _branch_step_runner_for(self).run_one_step()

    def should_stop(self) -> bool:
        return self._governance.should_stop()

    @staticmethod
    def _has_pending_evaluation(branches: List[Branch]) -> bool:
        """Compatibility wrapper for budget-efficiency early-stop guard."""
        return CampaignGovernanceService.has_pending_evaluation(branches)

    def get_state(self) -> Dict[str, Any]:
        branches = self._branch_ctrl.get_active_branches()
        state = {
            "campaign_id": self._campaign_id,
            "n_experiments": self._n_experiments,
            "total_rounds": self._round_num,
            "n_steps": len(self._step_history),
            "n_active_branches": len(branches),
            "champion_version": self._champion.version,
            "champion_weight_revision": getattr(self._champion, "weight_revision", 0),
            "budget_remaining": self._budget.remaining_ratio,
            "balance_exhausted": self._balance_exhausted,
            "circuit_breaker_tripped": self._circuit_breaker.is_tripped,
            "frozen_budget": self._frozen_budget_ledger.snapshot(),
            "branches": [
                {
                    "id": b.branch_id,
                    "state": b.state.value,
                    "base_champion_id": b.base_champion_id,
                    "weight_revision": getattr(b, "weight_revision", 0),
                }
                for b in branches
            ],
        }
        weight_opt_status = self._weight_opt_coord.status_snapshot()
        if (
            weight_opt_status["pending_threads"]
            or weight_opt_status["active"]
            or weight_opt_status["runs"]
        ):
            state["weight_optimization"] = weight_opt_status
        if self._current_status_progress is not None:
            state["current_progress"] = self._current_status_progress
        return state

    def _write_status(
        self,
        *,
        last_result: StepResult | None = None,
        stopped_reason: str | None = None,
    ) -> None:
        self._evidence_recorder.current_status_progress = self._current_status_progress
        self._evidence_recorder.last_status_result = self._last_status_result
        self._evidence_recorder.write_status(
            last_result=last_result,
            stopped_reason=stopped_reason,
        )
        self._last_status_result = self._evidence_recorder.last_status_result

    def _on_protocol_progress(self, **payload: Any) -> None:
        """Progress hook called by ExperimentProtocol during long stages."""
        self._evidence_recorder.current_status_progress = self._current_status_progress
        progress = self._evidence_recorder.record_protocol_progress(**payload)
        self._current_status_progress = progress
        self._last_status_result = self._evidence_recorder.last_status_result

    def _begin_status_progress(
        self,
        *,
        branch: Branch,
        stage: ExperimentStage,
        hypothesis: HypothesisProposal,
        expand: bool,
        expand_round: int,
    ) -> None:
        self._current_status_progress = {
            "branch_id": branch.branch_id,
            "stage": stage.value,
            "target_file": hypothesis.target_file,
            "hypothesis_action": hypothesis.action,
            "base_champion_id": branch.base_champion_id,
            "branch_weight_revision": getattr(branch, "weight_revision", 0),
            "champion_version": self._champion.version,
            "champion_weight_revision": getattr(self._champion, "weight_revision", 0),
            "expand": expand,
            "expand_round": expand_round,
            "step_started_at": datetime.now().isoformat(),
            "last_progress_at": datetime.now().isoformat(),
        }
        self._evidence_recorder.current_status_progress = self._current_status_progress
        self._write_status()

    def _end_status_progress(self) -> None:
        self._current_status_progress = None
        self._evidence_recorder.current_status_progress = None
        self._write_status()

    def _persist_branch_state(self, branch_id: str) -> None:
        try:
            self._branch_store.save(self._branch_ctrl.get_branch(branch_id))
        except Exception as exc:
            logger.debug("BranchStore.save(%s) failed: %s", branch_id, exc)

    def _persist_all_branch_states(self) -> None:
        for branch in list(self._branch_ctrl._branches.values()):
            try:
                self._branch_store.save(branch)
            except Exception as exc:
                logger.debug("BranchStore.save(%s) failed: %s", branch.branch_id, exc)

    # ------------------------------------------------------------------
    # EXPLORE step (Round 1 + Round 2 + eval)
    # ------------------------------------------------------------------

    def _run_explore_step(self, branch: Branch) -> StepResult:
        """Full 14-step flow for an EXPLORE/EXPLORE_EXPAND branch."""
        return _explore_step_pipeline_for(self).run(branch)

    # ------------------------------------------------------------------
    # EVAL-ONLY step (re-use workspace from EXPLORE)
    # ------------------------------------------------------------------

    def _run_eval_step(self, branch: Branch) -> StepResult:
        """Evaluation-only step for VALIDATING / FROZEN_TESTING branches."""
        return _branch_step_runner_for(self).run_eval_step(branch)

    # ------------------------------------------------------------------
    # STALE reconciliation
    # ------------------------------------------------------------------

    def _run_reconcile_step(self, branch: Branch) -> StepResult:
        """Attempt to rebase a STALE branch on the new champion.

        T06: Full reconcile pipeline — Contract → Verification → re-screening.
        A stale branch may only resume EXPLORE (→ READY_VALIDATE) if the patch
        passes all three gates against the new champion.
        If the VerificationGate or ExperimentProtocol is missing (skeleton mode),
        the stale branch is abandoned rather than silently passing.
        """
        return _branch_step_runner_for(self).run_reconcile_step(branch)

    # ------------------------------------------------------------------
    # Round 1: generate hypothesis
    # ------------------------------------------------------------------

    def _round1_generate_hypothesis(
        self, branch: Branch
    ) -> Tuple[Optional[HypothesisProposal], Optional[HypothesisRecord]]:
        return self._proposal_pipeline.generate_hypothesis(branch)

    def _proposal_failure_detail_for(self, branch_id: str) -> Optional[str]:
        return self._proposal_pipeline.pop_hypothesis_failure_detail(branch_id)

    # ------------------------------------------------------------------
    # Round 2: generate code
    # ------------------------------------------------------------------

    def _round2_generate_code(
        self, branch: Branch, hypothesis: HypothesisProposal,
        prior_failure: Optional[str] = None,
    ) -> Optional[PatchProposal]:
        return self._proposal_pipeline.generate_code(
            branch,
            hypothesis,
            prior_failure=prior_failure,
        )

    # ------------------------------------------------------------------
    # Fix code (verification_light retry)
    # ------------------------------------------------------------------

    def _attempt_fix(
        self, branch: Branch, patch: PatchProposal, vresult: VerificationResult
    ) -> Optional[PatchProposal]:
        return self._proposal_pipeline.attempt_fix(branch, patch, vresult)

    # ------------------------------------------------------------------
    # Workspace setup
    # ------------------------------------------------------------------

    def _setup_workspace(self, branch: Branch, force_champion: bool = False) -> Optional[str]:
        return _workspace_service_for(self).setup_workspace(
            branch,
            force_champion=force_champion,
        )

    def _workspace_service(self) -> WorkspaceLifecycleService:
        return _workspace_service_for(self)

    # ------------------------------------------------------------------
    # Evaluate (canary + experiment)
    # ------------------------------------------------------------------

    def _evaluate(
        self,
        branch: Branch,
        workspace: str,
        hypothesis: HypothesisProposal,
    ) -> Tuple[Decision, Optional[ProtocolResult], CanaryResult]:
        return _evaluation_orchestrator_for(self).evaluate(
            branch,
            workspace,
            hypothesis,
        )

    def _apply_soft_abandon(
        self,
        bid: str,
        branch: Branch,
        h_record: Optional[HypothesisRecord],
    ) -> None:
        """T4 soft-abandon: discard branch without affecting hard-stagnation counter.

        This path is for wr<0.3 'no signal' results — the branch couldn't beat the
        champion but there was no framework failure. Does NOT increment
        _recent_abandoned_count (which tracks framework-level stagnation only).
        """
        _evaluation_orchestrator_for(self).apply_soft_abandon(bid, branch, h_record)

    def _record_hard_abandon(self, branch_id: str, reason: str) -> None:
        """Count a non-T4 branch abandonment once for hard-stagnation logic."""
        counted = getattr(self, "_hard_abandon_counted_branches", None)
        if counted is None:
            counted = set()
            self._hard_abandon_counted_branches = counted
        if branch_id in counted:
            return
        counted.add(branch_id)
        self._recent_abandoned_count += 1
        logger.debug(
            "Branch %s: hard abandon counted (%s); recent_abandoned_count=%d",
            branch_id, reason, self._recent_abandoned_count,
        )

    # ------------------------------------------------------------------
    # Pool/registry sync
    # ------------------------------------------------------------------

    def _sync_pool_registry(
        self,
        workspace: str,
        hypothesis: HypothesisProposal,
        patch: PatchProposal,
    ) -> None:
        """Rebuild and export registry.yaml in workspace via PoolManager."""
        _workspace_service_for(self).sync_pool_registry(workspace, hypothesis, patch)

    # ------------------------------------------------------------------
    # Lineage recording
    # ------------------------------------------------------------------

    def _record_step_lineage(
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
        decision_reason_codes: Optional[tuple] = None,
    ) -> None:
        """Write one experiment_event + one decision row to the registry."""
        self._evidence_recorder.record_step_lineage(
            branch=branch,
            hypothesis=hypothesis,
            patch=patch,
            contract_result=contract_result,
            verification_result=verification_result,
            canary_result=canary_result,
            protocol_result=protocol_result,
            decision=decision,
            champion=self._champion,
            hypothesis_id=hypothesis_id,
            decision_reason_codes=decision_reason_codes,
        )

    def _decision_reason_codes_for(
        self,
        branch_id: str,
        protocol_result: Optional[ProtocolResult],
    ) -> Optional[Tuple[str, ...]]:
        return _lookup_decision_reason_codes(self, branch_id, protocol_result)

    def _increment_round(self) -> int:
        self._round_num += 1
        return self._round_num

    def _increment_rounds_since_last_promote(self) -> None:
        self._rounds_since_last_promote += 1

    # ------------------------------------------------------------------
    # Apply decision and finalise
    # ------------------------------------------------------------------

    def _apply_decision_and_finalize(
        self,
        branch: Branch,
        decision: Decision,
        hypothesis: HypothesisProposal,
        h_record: HypothesisRecord,
        protocol_result: Optional[ProtocolResult],
        canary_result: CanaryResult,
        contract_result: ContractResult,
        verification_result: VerificationResult,
        action_label: str,
        decision_reason_codes: Optional[Tuple[str, ...]] = None,
    ) -> StepResult:
        return self._decision_finalizer.apply(
            branch=branch,
            decision=decision,
            hypothesis=hypothesis,
            h_record=h_record,
            protocol_result=protocol_result,
            canary_result=canary_result,
            contract_result=contract_result,
            verification_result=verification_result,
            action_label=action_label,
            decision_reason_codes=decision_reason_codes,
        )

    # ------------------------------------------------------------------
    # Promote
    # ------------------------------------------------------------------

    def _on_promote(self, branch: Branch) -> None:
        """Update champion immediately (pre-optimized weights) and launch bg weight opt.

        Compatibility helper for tests and old callers. The branch must already
        be in the normal frozen promotion state; this method does not provide a
        second semantic promotion path.
        """
        self._promotion_lifecycle.on_promote(branch)

    def _prepare_promoted_champion(self, branch: Branch) -> PromotionPlan:
        """Build and freeze the champion snapshot before any promote state commit."""
        return self._promotion_lifecycle.prepare_promoted_champion(branch)

    def _require_promotable_branch(self, branch: Branch) -> None:
        self._promotion_lifecycle.require_promotable_branch(branch)

    def _commit_promote_plan(self, plan: PromotionPlan) -> None:
        """Commit an already prepared champion snapshot and launch follow-up work."""
        self._promotion_lifecycle.commit_promote_plan(plan)

    def _transition_promoted_branch(self, branch_id: str, new_champion: ChampionState) -> None:
        """Transition the promoted branch after champion persistence succeeds."""
        self._promotion_lifecycle.transition_promoted_branch(branch_id, new_champion)

    def _begin_promotion_commit(self, plan: PromotionPlan) -> None:
        """Reset campaign-level stagnation counters for a new champion cycle."""
        self._promotion_lifecycle.begin_promotion_commit(plan)

    def _reset_promotion_counters(self, branch_id: str) -> None:
        """Reset campaign-level stagnation counters for a committed champion."""
        self._recent_abandoned_count = 0
        self._hard_abandon_counted_branches.clear()
        self._soft_abandon_streak = 0
        self._hard_stagnation_escape_used = False

    def _commit_promoted_champion_state(self, new_champion: ChampionState) -> None:
        """Install the promoted champion in campaign memory."""
        self._promotion_lifecycle.commit_promoted_champion_state(new_champion)

    def _record_promoted_branch(self, branch_id: str, new_champion: ChampionState) -> None:
        """Record promotion context in search memory."""
        self._promotion_lifecycle.record_promoted_branch(branch_id, new_champion)

    def _persist_promoted_champion(self, new_champion: ChampionState) -> None:
        """Persist the promoted champion before mutable promotion side effects."""
        self._promotion_lifecycle.persist_promoted_champion(new_champion)

    def _start_weight_optimization(self, plan: PromotionPlan) -> None:
        """Launch or run weight optimization for an already committed champion."""
        self._promotion_lifecycle.start_weight_optimization(plan)

    def _drain_weight_opt_events(self) -> None:
        """Apply completed weight-optimization events on the campaign thread."""
        self._promotion_lifecycle.drain_weight_opt_events()

    def _run_weight_optimization(
        self, champion_snapshot: str, version: int, current_weights: dict
    ):
        """Delegate to AsyncWeightOptCoordinator (v0.3 B2).

        Kept as a method on CampaignManager so existing tests that monkey-patch
        ``cm._run_weight_optimization`` continue to work — the coordinator's bg
        thread calls back through ``self._mgr._run_weight_optimization(...)``.
        """
        return self._weight_opt_coord.run_optimization(
            champion_snapshot, version, current_weights
        )

    # ------------------------------------------------------------------
    # Stagnation detection (T25/T23)
    # ------------------------------------------------------------------

    def _run_stagnation_check(self) -> None:
        """Check for stagnation signals after each round and log critical ones."""
        self._governance.run_stagnation_check()

    def _check_soft_stagnation(self) -> None:
        """If soft_abandon_streak hits limit, force the next branch to diversify locus.

        soft-stagnation means: champion is too strong in current locus, not that the
        framework is broken. Response = diversify search direction, NOT terminate.
        """
        self._governance.check_soft_stagnation()

    def _consume_forced_locus(self) -> Optional[str]:
        """Consume and return forced locus (set by soft/hard stagnation), or None."""
        return self._governance.consume_forced_locus()

    def _get_diversification_locus(self) -> Optional[str]:
        """Determine the best locus to diversify into, using StagnationDetector diagnosis."""
        return self._governance.get_diversification_locus()

    # ------------------------------------------------------------------
    # Failure handling
    # ------------------------------------------------------------------

    def _handle_failure(
        self,
        branch: Branch,
        failure: FailureEvent,
        hypothesis_already_recorded: bool = False,
    ) -> None:
        """Route failure and execute the appropriate recovery strategy."""
        lifecycle = getattr(self, "_failure_lifecycle", None)
        if lifecycle is None:
            lifecycle = FailureLifecycleService.from_owner(self)
        lifecycle.handle_failure(
            branch,
            failure,
            hypothesis_already_recorded=hypothesis_already_recorded,
        )

    def _tick_blocked_branches(self) -> None:
        """Increment blocked_rounds for every BLOCKED_INFRA branch; auto-unblock at 3 rounds."""
        lifecycle = getattr(self, "_failure_lifecycle", None)
        if lifecycle is None:
            lifecycle = FailureLifecycleService.from_owner(self)
        lifecycle.tick_blocked_branches()

    # ------------------------------------------------------------------
    # Workspace archiving
    # ------------------------------------------------------------------

    def _archive_failed_workspace(
        self, workspace: str, branch_id: str, round_num: int
    ) -> Optional[str]:
        """Archive operators/ from a failed workspace. Returns archive path or None."""
        tag = f"round_{round_num}_{branch_id[:8]}"
        try:
            return self._materializer.archive_workspace(workspace=workspace, branch_id=tag)
        except Exception as exc:
            logger.debug("Branch %s: archive_failed_workspace failed: %s", branch_id, exc)
            return None

    # ------------------------------------------------------------------
    # Campaign summary
    # ------------------------------------------------------------------

    def _write_campaign_summary(self) -> None:
        """Write campaign_summary.json with per-step detail."""
        self._evidence_recorder.write_campaign_summary(
            step_history=self._step_history,
            round_num=self._round_num,
            champion=self._champion,
            budget_used=self._budget.used,
            budget_total=self._budget.total,
            stopped_reason=self._last_stop_reason,
            balance_exhausted=self._balance_exhausted,
            circuit_breaker_tripped=self._circuit_breaker.is_tripped,
            stagnation_signals=self._stagnation_signals,
            diagnostics=self._diagnostics,
            frozen_budget=self._frozen_budget_ledger.snapshot(),
        )


def _build_verification_detail(vresult: VerificationResult) -> Optional[str]:
    """Compatibility wrapper for the extracted explore-step helper."""
    return build_verification_detail(vresult)
