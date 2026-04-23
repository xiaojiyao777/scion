"""CampaignManager — main loop integrating all Scion modules (Phase 5)."""
from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Tuple

from scion.config.problem import ProtocolConfig, ProblemSpec, SplitManifest, SeedLedgerConfig
from scion.verification.gate import VerificationGate
from scion.contract.gate import ContractGate
from scion.core.branch import BranchController, StateTransitionError
from scion.core.decision import DecisionEngine
from scion.core.features import SafeFeatureExtractor, BudgetState
from scion.core.models import (
    Branch, BranchState, CanaryResult, ChampionState, ContractResult,
    Decision, ExperimentStage, FailureEvent, HypothesisProposal, HypothesisRecord,
    PatchProposal, ProtocolResult, StepRecord, VerificationResult, CheckResult,
)
from scion.core.scheduler import Scheduler
from scion.core.termination import CampaignState, TerminationChecker, TerminationConfig
from scion.core.stagnation import StagnationDetector, StagnationSignal, CampaignDiagnosis
from scion.failure.router import FailureRouter, RetryConfig
from scion.proposal.context_manager import ContextManager
from scion.proposal.engine import CreativeLayer
from scion.proposal.llm_client import LLMRetryExhaustedError, LLMFormatError, LLMTimeoutError, LLMBalanceError
from scion.proposal.engine import ProposalValidationError
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
# Step result
# ---------------------------------------------------------------------------

@dataclass
class StepResult:
    action: Literal[
        "explore", "validate", "frozen", "create_branch",
        "reconcile", "skip", "stopped"
    ]
    branch_id: Optional[str] = None
    decision: Optional[Decision] = None
    stopped: bool = False
    reason: str = ""


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
        verification_gate  — custom VerificationGate; defaults to lightweight stub
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
        objective_lower_bounds: Optional[Dict[str, float]] = None,
    ) -> None:
        self._spec = problem_spec
        self._protocol_config = protocol_config
        self._split_manifest = split_manifest
        self._seed_ledger = seed_ledger
        self._llm_client = llm_client
        self._champion = champion
        self._campaign_dir = campaign_dir
        self._campaign_id = str(uuid.uuid4())
        self._adapter = adapter
        self._objective_lower_bounds = objective_lower_bounds

        # Sub-modules
        self._branch_ctrl = BranchController()
        self._scheduler = Scheduler()
        self._contract_gate = ContractGate(problem_spec)
        self._decision_engine = DecisionEngine(protocol_config)
        self._feature_extractor = SafeFeatureExtractor()
        self._failure_router = FailureRouter(retry_config or RetryConfig())
        self._creative = CreativeLayer(llm_client)
        self._ctx_manager = ContextManager(adapter=self._adapter)

        # O1: Hypothesis family classifier (keyword-only if no LLM client)
        from scion.proposal.classifier import HypothesisFamilyClassifier
        self._classifier = HypothesisFamilyClassifier(llm_client=llm_client)
        self._materializer = WorkspaceMaterializer(
            campaign_dir,
            frozen_patterns=frozenset(
                problem_spec.search_space.frozen
            ) if problem_spec.search_space.frozen else None,
        )
        import os as _os2
        _os2.makedirs(str(campaign_dir) + "/metrics", exist_ok=True)
        self._vgate = verification_gate or VerificationGate(problem_spec, metrics_dir=str(campaign_dir) + "/metrics", adapter=adapter)
        self._experiment_protocol = experiment_protocol  # may be None (no runner)

        # Lineage registry (SQLite, WAL mode)
        import os as _os
        _os.makedirs(campaign_dir, exist_ok=True)
        self._registry = LineageRegistry(
            _os.path.join(campaign_dir, "scion.db")
        )
        self._hyp_store = HypothesisStore(self._registry)
        self._branch_store = BranchStore(self._registry)

        # J6: Champion store for persistence
        self._champion_store = ChampionStore(
            _os.path.join(campaign_dir, "scion.db"),
            _os.path.join(campaign_dir, "champions"),
        )

        # Per-branch transient state
        self._branch_workspaces: Dict[str, str] = {}       # branch_id → workspace path
        self._branch_hypotheses: Dict[str, HypothesisProposal] = {}
        self._branch_patches: Dict[str, PatchProposal] = {}
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
        self._search_memory = CampaignSearchMemory()

        # J-patch: Campaign research log (cross-branch trajectory from SQLite)
        from scion.proposal.research_log import CampaignResearchLog
        self._research_log = CampaignResearchLog(str(campaign_dir))

        # J2: Saturation analyzer (initialized lazily after first screening with data)
        self._saturation_analyzer: Optional[ChampionSaturationAnalyzer] = None
        self._baseline_metrics: Optional[Dict[str, float]] = None

        # J6: Latest weight optimization result (for LLM feedback)
        self._latest_weight_opt_result: Optional[Any] = None

        # W3 / v0.3 B1: PlateauController — idle counter + early-stop + forced locus
        from scion.core.plateau_controller import PlateauController
        self._plateau = PlateauController()
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

        # Async weight optimization (R3/R5)
        self._champion_lock = threading.Lock()
        self._pending_weight_opt_threads: List[threading.Thread] = []

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
    # Public API
    # ------------------------------------------------------------------

    def _record_step(self, step: StepRecord) -> None:
        """Record a completed step and update search memory (J1)."""
        self._step_history.append(step)
        self._search_memory.update(step)
        # J2: Lazily initialize baseline metrics from first champion-side data
        if self._baseline_metrics is None and step.protocol_result is not None:
            from scion.proposal.saturation import extract_champion_metrics_from_step
            _pf_len = len(step.protocol_result.pair_feedback) if step.protocol_result.pair_feedback else 0
            logger.info("[SATURATION DEBUG] R%d stage=%s pair_feedback_len=%d", step.round_num, step.protocol_result.stage, _pf_len)
            metrics = extract_champion_metrics_from_step(step)
            if metrics:
                logger.info("[SATURATION] Baseline initialized: splits=%.1f cost=%.0f", metrics.get('subcategory_splits',0), metrics.get('total_cost',0))
                self._baseline_metrics = metrics
                self._saturation_analyzer = ChampionSaturationAnalyzer(
                    metrics, lower_bounds=self._objective_lower_bounds,
                )
            else:
                logger.info("[SATURATION DEBUG] extract returned None for stage=%s", step.protocol_result.stage)

    def run(self, max_rounds: int = 1000) -> None:
        """Run the campaign until a termination condition is met."""
        for _ in range(max_rounds):
            if self.should_stop():
                logger.info("Campaign terminated.")
                break
            if self._circuit_breaker.is_tripped:
                logger.critical(
                    "Circuit breaker tripped after %d consecutive LLM failures; "
                    "stopping campaign. Last error: %s",
                    MAX_CONSECUTIVE_LLM_FAILURES,
                    self._circuit_breaker.last_failure_detail,
                )
                break
            result = self.run_one_step()
            if result.stopped:
                break
            # T25/T23: stagnation check after each round
            self._run_stagnation_check()
            # I3: soft-stagnation check (T4 abandon consecutive accumulation)
            self._check_soft_stagnation()
        self._write_campaign_summary()
        # R5: join all pending weight opt threads (up to 10 min each)
        pending = [t for t in self._pending_weight_opt_threads if t.is_alive()]
        if pending:
            logger.info(
                "Waiting for %d background weight opt thread(s) to complete...",
                len(pending),
            )
        for t in self._pending_weight_opt_threads:
            t.join(timeout=600)

    def run_one_step(self) -> StepResult:
        """Execute one campaign step and return a StepResult."""
        if self.should_stop():
            return StepResult(action="stopped", stopped=True, reason="termination condition met")

        # Tick blocked branches before scheduling (auto-unblock after 3 rounds)
        self._tick_blocked_branches()

        active = self._branch_ctrl.get_active_branches()
        sched = self._scheduler.select_next(active)

        # --- At capacity: max_active_branches limit reached ---
        if sched.action == "at_capacity":
            return StepResult(action="skip", reason="max_active_branches reached")

        # --- Create a new branch ---
        if sched.action == "create_new":
            with self._champion_lock:
                champ_snapshot = self._champion
            branch = self._branch_ctrl.create_branch(champ_snapshot)
            logger.info("Created new branch %s", branch.branch_id)
            try:
                self._branch_store.save(branch)
            except Exception as _exc:
                logger.debug("BranchStore.save (create) failed: %s", _exc)
            result = self._run_explore_step(branch)
            result.action = "create_branch"
            return result

        branch = sched.branch
        assert branch is not None

        # --- Advance READY_* states to their running state ---
        # NOTE: EXPLORE_EXPAND is intentionally excluded here — it must go directly to
        # _run_eval_step (reusing the existing workspace+patch from the prior explore step).
        # schedule_branch would convert EXPLORE_EXPAND → EXPLORE, which would trigger a
        # brand-new _run_explore_step that destroys the preserved workspace.
        if branch.state in (
            BranchState.READY_VALIDATE,
            BranchState.READY_FROZEN,
        ):
            try:
                self._branch_ctrl.schedule_branch(branch.branch_id)
            except StateTransitionError as exc:
                logger.error("schedule_branch failed: %s", exc)
                return StepResult(
                    action="skip", branch_id=branch.branch_id, reason=str(exc)
                )

        branch = self._branch_ctrl.get_branch(branch.branch_id)

        # --- STALE: attempt reconciliation ---
        if branch.state in (BranchState.STALE, BranchState.STALE_WEIGHT_UPDATE):
            return self._run_reconcile_step(branch)

        # --- EXPLORE: full proposal + eval ---
        if branch.state == BranchState.EXPLORE:
            return self._run_explore_step(branch)

        # --- EXPLORE_EXPAND / VALIDATING / VALIDATING_EXPAND / FROZEN_TESTING: re-eval only ---
        if branch.state in (
            BranchState.EXPLORE_EXPAND,
            BranchState.VALIDATING,
            BranchState.VALIDATING_EXPAND,
            BranchState.FROZEN_TESTING,
        ):
            try:
                return self._run_eval_step(branch)
            except RuntimeError as exc:
                logger.error("Branch %s: eval step aborted — %s", branch.branch_id, exc)
                bid = branch.branch_id
                h_record = self._branch_current_hypothesis.get(bid)
                if h_record is not None:
                    try:
                        self._hyp_store.mark_status(h_record.hypothesis_id, "rejected")
                    except Exception:
                        pass
                    self._branch_current_hypothesis.pop(bid, None)
                self._branch_ctrl.apply_decision(branch.branch_id, Decision.ABANDON)
                return StepResult(
                    action="validate", branch_id=branch.branch_id, reason=str(exc)
                )

        logger.warning(
            "Branch %s in unexpected state %s — skipping",
            branch.branch_id, branch.state.value,
        )
        return StepResult(
            action="skip", branch_id=branch.branch_id, reason=f"unhandled state {branch.state.value}"
        )

    def should_stop(self) -> bool:
        active = self._branch_ctrl.get_active_branches()

        # W3: Check early-stop from saturation + stagnation signals
        early_stop_detected = False
        early_stop_reason = ""
        sat_signals = []
        if self._saturation_analyzer is not None and self._baseline_metrics:
            from scion.proposal.saturation import extract_candidate_metrics_from_step
            current_metrics = self._baseline_metrics
            for s in reversed(self._step_history):
                if s.decision is not None and s.decision.value == "promote":
                    m = extract_candidate_metrics_from_step(s)
                    if m:
                        current_metrics = m
                        break
            if current_metrics:
                sat_signals = self._saturation_analyzer.analyze(current_metrics)
        es_decision = self._early_stop.should_early_stop(
            sat_signals, self._stagnation_signals,
            total_rounds=self._round_num,
            rounds_since_last_promote=self._rounds_since_last_promote,
        )
        if es_decision.stop:
            early_stop_detected = True
            early_stop_reason = es_decision.reason
            logger.info("Early-stop triggered: %s (rule=%s)", es_decision.reason, es_decision.rule)

        cs = CampaignState(
            n_experiments=self._n_experiments,
            start_time=self._start_time,
            recent_abandoned_count=self._recent_abandoned_count,
            active_branches=active,
            can_create_new=True,
            early_stop_detected=early_stop_detected,
            early_stop_reason=early_stop_reason,
        )
        if not self._term_checker.should_stop(cs):
            return False

        # I4: stagnation detected — attempt one diversification escape before terminating
        stagnation_triggered = self._term_checker._stagnation_detected(cs)
        if stagnation_triggered and not self._hard_stagnation_escape_used:
            logger.warning(
                "Hard stagnation detected (%d consecutive hard-abandons) — "
                "attempting locus diversification escape (one-time)",
                self._recent_abandoned_count,
            )
            self._hard_stagnation_escape_used = True
            self._recent_abandoned_count = 0  # reset counter to allow continuation
            self._forced_next_locus = self._get_diversification_locus()
            return False  # don't stop yet — give one more chance

        return True  # escape already used, or non-stagnation termination → truly stop

    def get_state(self) -> Dict[str, Any]:
        branches = self._branch_ctrl.get_active_branches()
        return {
            "n_experiments": self._n_experiments,
            "n_active_branches": len(branches),
            "champion_version": self._champion.version,
            "budget_remaining": self._budget.remaining_ratio,
            "branches": [
                {"id": b.branch_id, "state": b.state.value}
                for b in branches
            ],
        }

    # ------------------------------------------------------------------
    # EXPLORE step (Round 1 + Round 2 + eval)
    # ------------------------------------------------------------------

    def _run_explore_step(self, branch: Branch) -> StepResult:
        """Full 14-step flow for an EXPLORE/EXPLORE_EXPAND branch."""
        bid = branch.branch_id
        self._round_num += 1
        self._rounds_since_last_promote += 1
        rnum = self._round_num

        # ---------- Check for pending hypothesis (code-retry path) ----------
        pending = self._pending_hypotheses.pop(bid, None)
        prior_failure: Optional[str] = None

        if pending is not None:
            # Retry code generation for a previously code-failed hypothesis (skip Round 1)
            hypothesis, h_record, prior_failure = pending
            logger.info(
                "Branch %s: retrying code gen for pending hypothesis (prior failure: %s)",
                bid, prior_failure[:80],
            )
            # T02: pending hypothesis must re-pass hypothesis Contract Gate before Round 2
            c_result_pending = self._contract_gate.validate_hypothesis(
                hypothesis,
                self._hyp_store.get_by_status("active"),
                self._hyp_store.get_by_status("blacklisted"),
                rejected_hypotheses=self._hyp_store.get_by_status("rejected"),
                current_champion_version=self._champion.version if self._champion else 0,
            )
            if not c_result_pending.passed:
                logger.info(
                    "Branch %s: pending hypothesis re-failed contract gate: %s",
                    bid, c_result_pending.failure_reason,
                )
                _reason_p = c_result_pending.failure_reason or ""
                _cat_p = "search_guidance" if "C10_novelty" in _reason_p else "contract"
                failure = FailureEvent(category=_cat_p, detail=_reason_p)
                self._handle_failure(branch, failure)
                self._hyp_store.mark_status(h_record.hypothesis_id, "rejected")
                self._record_step(StepRecord(
                    round_num=rnum, branch_id=bid,
                    hypothesis=hypothesis, patch=None,
                    contract_passed=False, verification_passed=False,
                    protocol_result=None, decision=None,
                    failure_stage="hypothesis_contract",
                    failure_detail=c_result_pending.failure_reason,
                    hypothesis_id=h_record.hypothesis_id,
                ))
                return StepResult(action="explore", branch_id=bid, reason="pending hypothesis re-failed contract gate")
            self._branch_hypotheses[bid] = hypothesis
        else:
            # ---------- Round 1: generate hypothesis ----------
            hypothesis, h_record = self._round1_generate_hypothesis(branch)
            if hypothesis is None:
                return StepResult(action="explore", branch_id=bid, reason="hypothesis generation failed")
            logger.info(
                "Branch %s R1 hypothesis: locus=%s action=%s target=%s text='%s'",
                bid, hypothesis.change_locus, hypothesis.action, hypothesis.target_file,
                (hypothesis.hypothesis_text or "")[:200],
            )

            # ---------- Contract gate: validate_hypothesis ----------
            c_result = self._contract_gate.validate_hypothesis(
                hypothesis,
                self._hyp_store.get_by_status("active"),
                self._hyp_store.get_by_status("blacklisted"),
                rejected_hypotheses=self._hyp_store.get_by_status("rejected"),
                current_champion_version=self._champion.version if self._champion else 0,
            )
            if not c_result.passed:
                logger.info("Branch %s: hypothesis contract failed: %s", bid, c_result.failure_reason)
                _reason = c_result.failure_reason or ""
                _cat = "search_guidance" if "C10_novelty" in _reason else "contract"
                failure = FailureEvent(category=_cat, detail=_reason)
                self._handle_failure(branch, failure)
                try:
                    self._registry.record_contract_failure(
                        campaign_id=self._campaign_id,
                        branch_id=bid,
                        hypothesis_text=hypothesis.hypothesis_text or "",
                        change_locus=hypothesis.change_locus,
                        action=hypothesis.action,
                        target_file=hypothesis.target_file,
                        failure_reason=c_result.failure_reason or "",
                    )
                except Exception:
                    pass
                self._record_step(StepRecord(
                    round_num=rnum, branch_id=bid,
                    hypothesis=hypothesis, patch=None,
                    contract_passed=False, verification_passed=False,
                    protocol_result=None, decision=None,
                    failure_stage="hypothesis_contract",
                    failure_detail=c_result.failure_reason,
                    hypothesis_id=h_record.hypothesis_id,
                ))
                return StepResult(action="explore", branch_id=bid, reason="hypothesis contract failed")

            # Register hypothesis in SQLite store
            h_record.base_champion_version = self._champion.version if self._champion else 0
            self._hyp_store.save(h_record)
            self._branch_hypotheses[bid] = hypothesis

        # ---------- Round 2: generate code ----------
        patch = self._round2_generate_code(branch, hypothesis, prior_failure=prior_failure)
        if patch is not None:
            logger.info(
                "Branch %s R2 code: file=%s action=%s code_len=%d",
                bid, patch.file_path, patch.action, len(patch.code_content or ""),
            )
        if patch is None:
            if prior_failure is not None:
                # Second code gen failure on retry — mark rejected, no further retries
                self._hyp_store.mark_status(h_record.hypothesis_id, "rejected")
                failure_stage_detail = "LLM code generation failed (retry — hypothesis rejected)"
            else:
                # First code gen failure — queue hypothesis for one retry next round
                self._pending_hypotheses[bid] = (hypothesis, h_record, "LLM code generation failed")
                self._hyp_store.mark_status(h_record.hypothesis_id, "code_failed")
                failure_stage_detail = "LLM code generation failed"
            self._record_step(StepRecord(
                round_num=rnum, branch_id=bid,
                hypothesis=hypothesis, patch=None,
                contract_passed=True, verification_passed=False,
                protocol_result=None, decision=None,
                failure_stage="code_generation",
                failure_detail=failure_stage_detail,
                hypothesis_id=h_record.hypothesis_id,
            ))
            return StepResult(action="explore", branch_id=bid, reason="code generation failed")

        # ---------- Contract gate: validate_patch ----------
        p_result = self._contract_gate.validate_patch(patch)
        if not p_result.passed:
            logger.info("Branch %s: patch contract failed: %s", bid, p_result.failure_reason)
            failure = FailureEvent(category="contract", detail=p_result.failure_reason or "")
            self._handle_failure(branch, failure)
            self._hyp_store.mark_status(h_record.hypothesis_id, "rejected")
            self._record_step(StepRecord(
                round_num=rnum, branch_id=bid,
                hypothesis=hypothesis, patch=patch,
                contract_passed=False, verification_passed=False,
                protocol_result=None, decision=None,
                failure_stage="patch_contract",
                failure_detail=p_result.failure_reason,
                hypothesis_id=h_record.hypothesis_id,
            ))
            return StepResult(action="explore", branch_id=bid, reason="patch contract failed")

        # ---------- Apply patch ----------
        workspace = self._setup_workspace(branch)
        if workspace is None:
            self._hyp_store.mark_status(h_record.hypothesis_id, "rejected")
            self._record_step(StepRecord(
                round_num=rnum, branch_id=bid,
                hypothesis=hypothesis, patch=patch,
                contract_passed=True, verification_passed=False,
                protocol_result=None, decision=None,
                failure_stage="workspace",
                failure_detail="workspace setup failed",
                hypothesis_id=h_record.hypothesis_id,
            ))
            return StepResult(action="explore", branch_id=bid, reason="workspace setup failed")

        try:
            code_hash = self._materializer.apply_patch(workspace, patch)
        except Exception as exc:
            logger.warning("Branch %s: apply_patch failed: %s", bid, exc)
            failure = FailureEvent(category="contract", detail=f"apply_patch: {exc}")
            self._handle_failure(branch, failure)
            self._hyp_store.mark_status(h_record.hypothesis_id, "rejected")
            self._record_step(StepRecord(
                round_num=rnum, branch_id=bid,
                hypothesis=hypothesis, patch=patch,
                contract_passed=True, verification_passed=False,
                protocol_result=None, decision=None,
                failure_stage="workspace",
                failure_detail=f"apply_patch: {exc}",
                hypothesis_id=h_record.hypothesis_id,
            ))
            return StepResult(action="explore", branch_id=bid, reason="apply_patch failed")

        self._branch_patches[bid] = patch
        # T4: sync registry via PoolManager after patch apply
        # (handles remove/modify correctly, not just create)
        self._sync_pool_registry(workspace, hypothesis, patch)
        # T03: only update current_code_hash here; last_clean_code_hash updated after verification passes
        self._branch_ctrl.record_candidate_code(bid, code_hash)

        # ---------- Verification gate ----------
        _champ_ws = self._champion.code_snapshot_path
        vresult = self._vgate.run(workspace, _champ_ws, patch)
        if not vresult.passed:
            severity = vresult.failure_severity or "light"
            logger.info("Branch %s: verification failed (%s): %s", bid, severity, vresult.first_failure)
            cat = "verification_light" if severity == "light" else "verification_heavy"
            failure = FailureEvent(category=cat, detail=vresult.first_failure or "")
            if severity == "light":
                # Attempt fix
                fixed = self._attempt_fix(branch, patch, vresult)
                if fixed is not None:
                    # T01: fix patch must pass Contract Gate before apply
                    fixed_contract = self._contract_gate.validate_patch(fixed)
                    if not fixed_contract.passed:
                        logger.info(
                            "Branch %s: fix patch failed contract gate: %s",
                            bid, fixed_contract.failure_reason,
                        )
                        fixed = None  # treat as if fix failed — do not apply
                    else:
                        try:
                            code_hash = self._materializer.apply_patch(workspace, fixed)
                            self._branch_patches[bid] = fixed
                            self._branch_ctrl.record_candidate_code(bid, code_hash)
                            vresult = self._vgate.run(workspace, _champ_ws, fixed)
                        except Exception:
                            pass
                if not vresult.passed:
                    self._handle_failure(branch, failure)
                    self._hyp_store.mark_status(h_record.hypothesis_id, "rejected")
                    archive_ref = self._archive_failed_workspace(workspace, bid, rnum)
                    try:
                        self._registry.record_event({
                            "campaign_id": self._campaign_id,
                            "branch_id": bid,
                            "hypothesis_id": h_record.hypothesis_id,
                            "timestamp": datetime.now().isoformat(),
                            "event_kind": "verification_fail",
                            "contract_passed": True,
                            "verification_passed": False,
                            "verification_result": vresult.first_failure,
                            "patch_file": patch.file_path if patch else None,
                            "hypothesis_text": (hypothesis.hypothesis_text or "")[:200],
                            "stage": "verification",
                            "decision_reason": "light",
                        })
                    except Exception:
                        pass
                    self._record_step(StepRecord(
                        round_num=rnum, branch_id=bid,
                        hypothesis=hypothesis, patch=patch,
                        contract_passed=True, verification_passed=False,
                        protocol_result=None, decision=None,
                        failure_stage="verification",
                        failure_detail=vresult.first_failure,
                        verification_detail=_build_verification_detail(vresult),
                        code_archive_ref=archive_ref,
                        hypothesis_id=h_record.hypothesis_id,
                    ))
                    return StepResult(action="explore", branch_id=bid, reason="verification failed (light)")
            else:
                self._hyp_store.mark_status(h_record.hypothesis_id, "blacklisted")
                self._handle_failure(branch, failure, hypothesis_already_recorded=True)
                archive_ref = self._archive_failed_workspace(workspace, bid, rnum)
                try:
                    self._registry.record_event({
                        "campaign_id": self._campaign_id,
                        "branch_id": bid,
                        "hypothesis_id": h_record.hypothesis_id,
                        "timestamp": datetime.now().isoformat(),
                        "event_kind": "verification_fail",
                        "contract_passed": True,
                        "verification_passed": False,
                        "verification_result": vresult.first_failure,
                        "patch_file": patch.file_path if patch else None,
                        "hypothesis_text": (hypothesis.hypothesis_text or "")[:200],
                        "stage": "verification",
                        "decision_reason": "heavy",
                    })
                except Exception:
                    pass
                self._record_step(StepRecord(
                    round_num=rnum, branch_id=bid,
                    hypothesis=hypothesis, patch=patch,
                    contract_passed=True, verification_passed=False,
                    protocol_result=None, decision=None,
                    failure_stage="verification",
                    failure_detail=vresult.first_failure,
                    verification_detail=_build_verification_detail(vresult),
                    code_archive_ref=archive_ref,
                    hypothesis_id=h_record.hypothesis_id,
                ))
                return StepResult(action="explore", branch_id=bid, reason="verification failed (heavy)")

        # T03: verification passed — now safe to update last_clean_code_hash
        self._branch_ctrl.record_verification_pass(bid, code_hash)
        # Sprint H2 T1: reset failure streaks on verification pass (entering screening)
        self._failure_streak.clear()
        # (used by _run_eval_step for validation/frozen stages)
        self._branch_current_hypothesis[bid] = h_record

        # ---------- Evaluate ----------
        # J4 concurrency guard: async weight-opt thread may have marked this branch STALE
        # while the LLM call was in flight. Re-fetch state before next_stage.
        _fresh = self._branch_ctrl.get_branch(bid)
        if _fresh and _fresh.state in (BranchState.STALE, BranchState.STALE_WEIGHT_UPDATE):
            logger.info("Branch %s: marked stale by async weight-opt during explore — deferring", bid)
            return StepResult(action="skip", branch_id=bid, reason="stale_during_explore")
        stage = self._branch_ctrl.next_stage(bid)
        decision, protocol_result, canary_result = self._evaluate(branch, workspace, hypothesis)

        # ---------- Apply decision ----------
        result = self._apply_decision_and_finalize(
            branch=branch,
            decision=decision,
            hypothesis=hypothesis,
            h_record=h_record,
            protocol_result=protocol_result,
            canary_result=canary_result,
            contract_result=p_result,
            verification_result=vresult,
            action_label="explore",
        )
        logger.debug(
            "_run_explore_step done bid=%s decision=%s workspaces=%s",
            bid, decision.value, list(self._branch_workspaces.keys()),
        )
        # Record the completed step
        self._record_step(StepRecord(
            round_num=rnum, branch_id=bid,
            hypothesis=hypothesis,
            patch=self._branch_patches.get(bid, patch),
            contract_passed=True, verification_passed=True,
            protocol_result=protocol_result,
            decision=result.decision or Decision.ABANDON,
            failure_stage=None,
            failure_detail=None,
            hypothesis_id=h_record.hypothesis_id,
        ))
        return result

    # ------------------------------------------------------------------
    # EVAL-ONLY step (re-use workspace from EXPLORE)
    # ------------------------------------------------------------------

    def _run_eval_step(self, branch: Branch) -> StepResult:
        """Evaluation-only step for VALIDATING / FROZEN_TESTING branches."""
        bid = branch.branch_id
        logger.debug(
            "_run_eval_step start bid=%s state=%s workspaces=%s",
            bid, branch.state.value, list(self._branch_workspaces.keys()),
        )
        workspace = self._branch_workspaces.get(bid)
        if workspace is None:
            # Workspace lost — abandon
            logger.warning("Branch %s: no workspace for eval step — abandoning", bid)
            h_record = self._branch_current_hypothesis.get(bid)
            if h_record is not None:
                try:
                    self._hyp_store.mark_status(h_record.hypothesis_id, "rejected")
                except Exception:
                    pass
                self._branch_current_hypothesis.pop(bid, None)
            self._branch_ctrl.apply_decision(bid, Decision.ABANDON)
            return StepResult(action="validate", branch_id=bid, reason="workspace not found")

        hypothesis = self._branch_hypotheses.get(bid)
        if hypothesis is None:
            logger.warning("Branch %s: no hypothesis for eval step — abandoning", bid)
            h_record = self._branch_current_hypothesis.get(bid)
            if h_record is not None:
                try:
                    self._hyp_store.mark_status(h_record.hypothesis_id, "rejected")
                except Exception:
                    pass
                self._branch_current_hypothesis.pop(bid, None)
            self._branch_ctrl.apply_decision(bid, Decision.ABANDON)
            return StepResult(action="validate", branch_id=bid, reason="hypothesis not found")

        patch = self._branch_patches.get(bid)
        vresult = VerificationResult(passed=True, checks=())
        if patch is not None:
            vresult = VerificationResult(passed=True, checks=())  # already passed

        action_label: Literal["explore", "validate", "frozen", "create_branch", "reconcile", "skip", "stopped"]
        if branch.state == BranchState.EXPLORE_EXPAND:
            action_label = "explore"
        elif branch.state in (BranchState.VALIDATING, BranchState.VALIDATING_EXPAND):
            action_label = "validate"
        else:
            action_label = "frozen"

        p_result = ContractResult(passed=True, checks=())
        decision, protocol_result, canary_result = self._evaluate(branch, workspace, hypothesis)

        # T04: reuse the canonical HypothesisRecord from screening — do NOT create a fake one
        h_record = self._branch_current_hypothesis.get(bid)
        if h_record is None:
            raise RuntimeError(
                f"Branch {bid}: no canonical hypothesis record — cannot proceed with eval"
            )

        self._round_num += 1
        # A2 (v0.3 post-opt regression fix): only count screening-expand self-loops as idle.
        # Branches that reach VALIDATING / FROZEN_TESTING are productive activity even if they
        # eventually fail — don't penalize them with idle accounting that would trigger
        # budget_efficiency early-stop.
        if action_label == "explore":
            self._rounds_since_last_promote += 1
        rnum = self._round_num
        result = self._apply_decision_and_finalize(
            branch=branch,
            decision=decision,
            hypothesis=hypothesis,
            h_record=h_record,
            protocol_result=protocol_result,
            canary_result=canary_result,
            contract_result=p_result,
            verification_result=vresult,
            action_label=action_label,
        )

        # T05: write StepRecord for eval-only steps (validation/frozen)
        stage_val = action_label  # "validate", "frozen", or "explore" for expand
        self._record_step(StepRecord(
            round_num=rnum, branch_id=bid,
            hypothesis=hypothesis,
            patch=patch,
            contract_passed=True, verification_passed=True,
            protocol_result=protocol_result,
            decision=result.decision,
            failure_stage=None,
            failure_detail=None,
            hypothesis_id=h_record.hypothesis_id,
            decision_reason_codes=protocol_result.reason_codes if protocol_result else None,
        ))
        return result

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
        bid = branch.branch_id
        patch = self._branch_patches.get(bid)
        h_record = self._branch_current_hypothesis.get(bid)

        def _cleanup() -> None:
            """Clean up zombie hypothesis to free C10 slot."""
            if h_record is not None:
                try:
                    self._hyp_store.mark_status(h_record.hypothesis_id, "rejected")
                except Exception:
                    pass
                self._branch_current_hypothesis.pop(bid, None)

        if patch is None:
            logger.info("Branch %s: no patch to reconcile — abandoning stale branch", bid)
            _cleanup()
            self._branch_ctrl.reconcile_stale(bid, success=False, new_champion=self._champion)
            return StepResult(action="reconcile", branch_id=bid, reason="no patch to reconcile")

        hypothesis = self._branch_hypotheses.get(bid)

        # --- Step 1: fresh workspace from new champion ---
        workspace = self._setup_workspace(branch, force_champion=True)
        if workspace is None:
            _cleanup()
            self._branch_ctrl.reconcile_stale(bid, success=False, new_champion=self._champion)
            return StepResult(action="reconcile", branch_id=bid, reason="workspace setup failed")

        # --- Step 2: reapply patch ---
        try:
            code_hash = self._materializer.apply_patch(workspace, patch)
        except Exception as exc:
            logger.info("Branch %s: reconcile apply_patch failed: %s", bid, exc)
            _cleanup()
            self._branch_ctrl.reconcile_stale(bid, success=False, new_champion=self._champion)
            return StepResult(action="reconcile", branch_id=bid, reason=f"apply_patch failed: {exc}")

        # T03: record candidate code hash (not yet verified)
        self._branch_ctrl.record_candidate_code(bid, code_hash)

        # --- Step 3: Contract Gate ---
        contract_result = self._contract_gate.validate_patch(patch)
        if not contract_result.passed:
            logger.info(
                "Branch %s: reconcile patch failed contract gate: %s",
                bid, contract_result.failure_reason,
            )
            _cleanup()
            self._branch_ctrl.reconcile_stale(bid, success=False, new_champion=self._champion)
            return StepResult(
                action="reconcile", branch_id=bid,
                reason=f"reconcile contract failed: {contract_result.failure_reason}",
            )

        # --- Step 4: Verification Gate ---
        # If verification gate has no runner, abandon rather than silently pass
        _champ_ws = self._champion.code_snapshot_path
        vresult = self._vgate.run(workspace, _champ_ws, patch)
        if not vresult.passed:
            logger.info(
                "Branch %s: reconcile verification failed: %s", bid, vresult.first_failure
            )
            _cleanup()
            self._branch_ctrl.reconcile_stale(bid, success=False, new_champion=self._champion)
            return StepResult(
                action="reconcile", branch_id=bid,
                reason=f"reconcile verification failed: {vresult.first_failure}",
            )

        # T03: verification passed — update last_clean_code_hash
        self._branch_ctrl.record_verification_pass(bid, code_hash)

        # --- Step 5: re-screening ---
        # If there is no experiment protocol, we cannot meaningfully re-screen —
        # abandon rather than silently accept (T06 requirement).
        if self._experiment_protocol is None:
            logger.info(
                "Branch %s: no experiment protocol for reconcile re-screening — abandoning stale branch", bid
            )
            _cleanup()
            self._branch_ctrl.reconcile_stale(bid, success=False, new_champion=self._champion)
            return StepResult(
                action="reconcile", branch_id=bid,
                reason="no experiment protocol for re-screening",
            )

        hypothesis_action = hypothesis.action if hypothesis else "modify"
        champ_ws = self._champion.code_snapshot_path
        try:
            canary_result = self._experiment_protocol.run_canary(workspace, champ_ws)
        except (ValueError, NotImplementedError) as exc:
            logger.debug("reconcile run_canary skipped: %s", exc)
            canary_result = CanaryResult(passed=True, reason=f"canary skipped: {exc}")
        if not canary_result.passed:
            logger.info("Branch %s: reconcile canary failed — abandoning stale branch", bid)
            _cleanup()
            self._branch_ctrl.reconcile_stale(bid, success=False, new_champion=self._champion)
            return StepResult(action="reconcile", branch_id=bid, reason="reconcile canary failed")

        try:
            screening_result = self._experiment_protocol.run_experiment(
                stage=ExperimentStage.SCREENING,
                candidate_ws=workspace,
                champion_ws=champ_ws,
                hypothesis_action=hypothesis_action,
                expand=False,
                expand_round=1,
            )
            self._n_experiments += 1
            self._budget.used += 1
        except Exception as exc:
            logger.error("Branch %s: reconcile re-screening failed: %s", bid, exc)
            _cleanup()
            self._branch_ctrl.reconcile_stale(bid, success=False, new_champion=self._champion)
            return StepResult(action="reconcile", branch_id=bid, reason=f"re-screening failed: {exc}")

        # --- Step 6: routing based on screening result ---
        if screening_result.gate_outcome in ("pass", "expand"):
            # Positive signal — allow branch to continue (as READY_VALIDATE to re-enter eval)
            self._branch_ctrl.reconcile_stale(bid, success=True, new_champion=self._champion)
            # Put branch in READY_VALIDATE so it gets a full validation cycle against new champion
            try:
                b = self._branch_ctrl.get_branch(bid)
                if b.state == BranchState.EXPLORE:
                    self._branch_ctrl.apply_decision(bid, Decision.QUEUE_VALIDATE)
            except Exception:
                pass
            logger.info(
                "Branch %s: reconcile succeeded (screening gate_outcome=%s) → READY_VALIDATE",
                bid, screening_result.gate_outcome,
            )
            try:
                _b = self._branch_ctrl.get_branch(bid)
                if _b:
                    self._branch_store.save(_b)
            except Exception as _exc:
                logger.debug("BranchStore.save (reconcile ok) failed: %s", _exc)
            return StepResult(action="reconcile", branch_id=bid, reason="reconcile succeeded — READY_VALIDATE")
        else:
            logger.info(
                "Branch %s: reconcile re-screening failed (gate_outcome=%s) — abandoning",
                bid, screening_result.gate_outcome,
            )
            _cleanup()
            self._branch_ctrl.reconcile_stale(bid, success=False, new_champion=self._champion)
            try:
                _b = self._branch_ctrl.get_branch(bid)
                if _b:
                    self._branch_store.save(_b)
            except Exception as _exc:
                logger.debug("BranchStore.save (reconcile fail) failed: %s", _exc)
            return StepResult(
                action="reconcile", branch_id=bid,
                reason=f"reconcile re-screening failed: gate_outcome={screening_result.gate_outcome}",
            )

    # ------------------------------------------------------------------
    # Round 1: generate hypothesis
    # ------------------------------------------------------------------

    def _round1_generate_hypothesis(
        self, branch: Branch
    ) -> Tuple[Optional[HypothesisProposal], Optional[HypothesisRecord]]:
        bid = branch.branch_id
        siblings = [
            b for b in self._branch_ctrl.get_active_branches()
            if b.branch_id != bid
        ]
        # Pass the current branch workspace so the LLM sees branch-specific code (§4.9)
        branch_workspace = self._branch_workspaces.get(bid)
        with self._champion_lock:
            champ_snapshot = self._champion
        # J2: Compute saturation signals if analyzer is available
        saturation_signals = None
        if self._saturation_analyzer is not None:
            from scion.proposal.saturation import extract_candidate_metrics_from_step
            # Use latest promoted champion metrics
            current_metrics = self._baseline_metrics  # fallback
            for s in reversed(self._step_history):
                if s.decision is not None and s.decision.value == "promote":
                    m = extract_candidate_metrics_from_step(s)
                    if m:
                        current_metrics = m
                        break
            if current_metrics:
                saturation_signals = self._saturation_analyzer.analyze(current_metrics)

        context = self._ctx_manager.build_hypothesis_context(
            branch=branch,
            champion=champ_snapshot,
            problem_spec=self._spec,
            active_hypotheses=self._hyp_store.get_by_status("active"),
            blacklist=self._hyp_store.get_by_status("blacklisted"),
            sibling_branches=siblings,
            step_history=self._step_history,
            branch_workspace=branch_workspace,
            failure_streak=dict(self._failure_streak),
            forced_locus=self._consume_forced_locus(),
            search_memory=self._search_memory,
            saturation_signals=saturation_signals,
            weight_opt_result=self._latest_weight_opt_result,
            research_log=self._research_log,
        )
        try:
            hypothesis = self._creative.generate_hypothesis(context)
        except LLMBalanceError as exc:
            logger.critical("Branch %s: API balance exhausted — stopping campaign: %s", bid, exc)
            self._balance_exhausted = True
            self._circuit_breaker.record_failure(str(exc))
            return None, None
        except (LLMRetryExhaustedError, LLMFormatError, LLMTimeoutError, ProposalValidationError) as exc:
            logger.warning("Branch %s: hypothesis LLM error: %s", bid, exc)
            failure = FailureEvent(category="proposal", detail=str(exc))
            self._handle_failure(branch, failure)
            self._circuit_breaker.record_failure(str(exc))
            return None, None

        self._circuit_breaker.record_success()
        # O1: classify hypothesis family
        cls_result = self._classifier.classify(hypothesis.hypothesis_text or "")
        h_record = HypothesisRecord(
            hypothesis_id=str(uuid.uuid4()),
            branch_id=bid,
            change_locus=hypothesis.change_locus,
            action=hypothesis.action,
            status="active",
            target_file=hypothesis.target_file,
            suggested_weight=hypothesis.suggested_weight,
            hypothesis_text=hypothesis.hypothesis_text,
            family_id=cls_result.family_id,
            family_source=cls_result.source,
            taxonomy_version=cls_result.taxonomy_version,
        )
        return hypothesis, h_record

    # ------------------------------------------------------------------
    # Round 2: generate code
    # ------------------------------------------------------------------

    def _round2_generate_code(
        self, branch: Branch, hypothesis: HypothesisProposal,
        prior_failure: Optional[str] = None,
    ) -> Optional[PatchProposal]:
        bid = branch.branch_id
        with self._champion_lock:
            champ_snapshot = self._champion
        context = self._ctx_manager.build_code_context(
            branch=branch,
            hypothesis=hypothesis,
            champion=champ_snapshot,
            problem_spec=self._spec,
            prior_failure=prior_failure,
        )
        try:
            result = self._creative.generate_code(context)
            self._circuit_breaker.record_success()
            return result
        except LLMBalanceError as exc:
            logger.critical("Branch %s: API balance exhausted — stopping campaign: %s", bid, exc)
            self._balance_exhausted = True
            self._circuit_breaker.record_failure(str(exc))
            return None
        except (LLMRetryExhaustedError, LLMFormatError, LLMTimeoutError, ProposalValidationError) as exc:
            logger.warning("Branch %s: code LLM error: %s", bid, exc)
            failure = FailureEvent(category="proposal", detail=str(exc))
            self._handle_failure(branch, failure)
            self._circuit_breaker.record_failure(str(exc))
            return None

    # ------------------------------------------------------------------
    # Fix code (verification_light retry)
    # ------------------------------------------------------------------

    def _attempt_fix(
        self, branch: Branch, patch: PatchProposal, vresult: VerificationResult
    ) -> Optional[PatchProposal]:
        context = self._ctx_manager.build_fix_context(
            branch=branch,
            patch=patch,
            verification_result=vresult,
            problem_spec=self._spec,
            failure_streak=dict(self._failure_streak),
        )
        try:
            return self._creative.fix_code(context)
        except (LLMRetryExhaustedError, LLMFormatError, LLMTimeoutError) as exc:
            logger.warning("Branch %s: fix LLM error: %s", branch.branch_id, exc)
            return None

    # ------------------------------------------------------------------
    # Workspace setup
    # ------------------------------------------------------------------

    def _setup_workspace(self, branch: Branch, force_champion: bool = False) -> Optional[str]:
        bid = branch.branch_id

        # If the branch has a verified clean code base, reuse the existing workspace
        # to enable iterative evolution within a branch (§11.2 / §4.5).
        if not force_champion:
            code_base = self._branch_ctrl.get_code_base(bid)
            if code_base == "branch_workspace":
                existing = self._branch_workspaces.get(bid)
                if existing:
                    import os as _os
                    if _os.path.isdir(existing):
                        return existing
                # Workspace was lost — fall through to create from champion

        # Clean up existing workspace if any
        existing = self._branch_workspaces.get(bid)
        if existing:
            try:
                self._materializer.cleanup(existing)
            except Exception:
                pass

        with self._champion_lock:
            src = self._champion.code_snapshot_path
        try:
            ws = self._materializer.create_branch_workspace(bid, src)
            self._branch_workspaces[bid] = ws
            return ws
        except Exception as exc:
            logger.error("Branch %s: workspace creation failed: %s", bid, exc)
            return None

    # ------------------------------------------------------------------
    # Evaluate (canary + experiment)
    # ------------------------------------------------------------------

    def _evaluate(
        self,
        branch: Branch,
        workspace: str,
        hypothesis: HypothesisProposal,
    ) -> Tuple[Decision, Optional[ProtocolResult], CanaryResult]:
        bid = branch.branch_id
        stage = self._branch_ctrl.next_stage(bid)

        # Champion workspace path
        champ_ws = self._champion.code_snapshot_path

        # ---- Canary ----
        canary_result: CanaryResult
        if self._experiment_protocol is not None:
            try:
                canary_result = self._experiment_protocol.run_canary(workspace, champ_ws)
            except (ValueError, NotImplementedError) as exc:
                # Canary not configured (e.g. empty split) — treat as skip/pass
                logger.debug("run_canary skipped: %s", exc)
                canary_result = CanaryResult(passed=True, reason=f"canary skipped: {exc}")
        else:
            canary_result = CanaryResult(passed=True, reason="no protocol — auto-pass")

        # ---- Experiment ----
        protocol_result: Optional[ProtocolResult] = None
        if self._experiment_protocol is not None:
            expand = branch.state in (
                BranchState.EXPLORE_EXPAND,
                BranchState.VALIDATING_EXPAND,
            )
            if expand:
                branch.expand_count += 1
            try:
                protocol_result = self._experiment_protocol.run_experiment(
                    stage=stage,
                    candidate_ws=workspace,
                    champion_ws=champ_ws,
                    hypothesis_action=hypothesis.action,
                    expand=expand,
                    expand_round=branch.expand_count if expand else 1,
                )
                self._n_experiments += 1
                self._budget.used += 1
            except Exception as exc:
                logger.error("Branch %s: experiment failed: %s", bid, exc)
                failure = FailureEvent(category="evaluation", detail=str(exc))
                self._handle_failure(branch, failure)
                return Decision.ABANDON, None, canary_result
        else:
            # No experiment protocol — auto-advance for skeleton testing
            self._n_experiments += 1
            self._budget.used += 1

        # ---- Features + Decision ----
        branch_obj = self._branch_ctrl.get_branch(bid)
        contract_result = ContractResult(passed=True, checks=())
        verification_result = VerificationResult(passed=True, checks=())

        features = self._feature_extractor.extract(
            branch=branch_obj,
            hypothesis_action=hypothesis.action,
            contract=contract_result,
            verification=verification_result,
            canary=canary_result,
            protocol=protocol_result,
            budget=self._budget,
        )
        outcome = self._decision_engine.decide(features)
        logger.info(
            "Branch %s: features wr=%s md=%s stage=%s → decision=%s reasons=%s",
            bid, features.win_rate, features.median_delta,
            features.stage, outcome.decision.value, outcome.reason_codes,
        )

        # Sprint H2 T4: Tiered evaluation routing (I1: soft-abandon path)
        decision = outcome.decision
        if (
            decision == Decision.CONTINUE_EXPLORE
            and features.win_rate is not None
        ):
            if features.win_rate < 0.3:
                # I1: T4 soft-abandon — independent of hard stagnation counter
                logger.info(
                    "Branch %s: win_rate=%.2f < 0.3 → soft_abandon (T4)",
                    bid, features.win_rate,
                )
                try:
                    self._registry.record_event({
                        "campaign_id": self._campaign_id,
                        "branch_id": bid,
                        "timestamp": datetime.now().isoformat(),
                        "event_kind": "abandon_fast",
                        "reason": "win_rate_below_threshold",
                        "win_rate": features.win_rate,
                        "abandon_type": "soft_t4",
                    })
                except Exception:
                    pass
                # T4 soft-abandon: track independently, don't go through ABANDON dispatch
                self._soft_abandon_streak += 1
                self._apply_soft_abandon(bid, branch, self._branch_current_hypothesis.get(bid))
                return Decision.ABANDON, protocol_result, canary_result
            elif features.win_rate > 0.6:
                # High potential — log for priority tracking
                logger.info(
                    "Branch %s: win_rate=%.2f > 0.6 → high_potential (continue_explore)",
                    bid, features.win_rate,
                )

        return decision, protocol_result, canary_result

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
        ws = self._branch_workspaces.pop(bid, None)
        if ws:
            try:
                self._materializer.archive_workspace(ws, bid)
            except Exception as exc:
                logger.debug("Branch %s: soft_abandon archive failed: %s", bid, exc)
            try:
                self._materializer.cleanup(ws)
            except Exception:
                pass
        self._branch_hypotheses.pop(bid, None)
        # Note: do NOT pop _branch_patches here — _record_step_lineage needs it
        # for patch_file recording. Cleanup happens in _apply_decision_and_finalize.
        if h_record is not None:
            self._hyp_store.mark_status(h_record.hypothesis_id, "rejected")
            self._branch_current_hypothesis.pop(bid, None)
        try:
            self._branch_ctrl.apply_decision(bid, Decision.ABANDON)
        except StateTransitionError as exc:
            logger.debug("Branch %s: soft_abandon apply_decision failed: %s", bid, exc)

    # ------------------------------------------------------------------
    # Pool/registry sync
    # ------------------------------------------------------------------

    def _sync_pool_registry(
        self,
        workspace: str,
        hypothesis: HypothesisProposal,
        patch: PatchProposal,
    ) -> None:
        """Rebuild and export registry.yaml in workspace via PoolManager.

        Ensures remove/modify/create_new all produce a consistent registry,
        rather than relying on WorkspaceMaterializer side effects (create-only).
        """
        if not self._champion.operator_pool:
            logger.debug("_sync_pool_registry skipped: champion pool is empty")
            return
        try:
            from scion.runtime.pool_manager import PoolManager
            pool_mgr = PoolManager(self._champion.operator_pool)
            candidate_pool = pool_mgr.build_candidate_pool(
                self._champion.operator_pool, hypothesis, patch,
                workspace=workspace,
            )
            pool_mgr.export_registry(candidate_pool, workspace)
        except Exception as exc:
            logger.debug("_sync_pool_registry failed (non-fatal): %s", exc)

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
        import json as _json

        bid = branch.branch_id
        stats = protocol_result.stats if protocol_result else None
        event: Dict[str, Any] = {
            "campaign_id": self._campaign_id,
            "branch_id": bid,
            "timestamp": datetime.now().isoformat(),
            "hypothesis_id": hypothesis_id,
            "code_hash": branch.current_code_hash or "",
            "patch_action": patch.action if patch else "",
            "patch_file": patch.file_path if patch else "",
            "hypothesis_text": (hypothesis.hypothesis_text or "")[:500],
            "contract_passed": str(contract_result.passed),
            "verification_passed": str(verification_result.passed),
            "contract_result": "passed" if contract_result.passed else "failed",
            "verification_result": "passed" if verification_result.passed else "failed",
            "canary_result": "passed" if canary_result.passed else "failed",
            "stage": protocol_result.stage.value if protocol_result else "",
            "screening_n_cases": stats.n_cases if stats else 0,
            "screening_win_rate": stats.win_rate if stats else None,
            "screening_median_delta": stats.median_delta if stats else None,
            "screening_ci_low": stats.ci_low if stats else None,
            "screening_ci_high": stats.ci_high if stats else None,
            "decision": decision.value,
            "model_id": getattr(self._llm_client, "model", None),
            "protocol_version": getattr(self._protocol_config, "version", None),
        }
        try:
            self._registry.record_event(event)
        except Exception as exc:
            logger.debug("registry.record_event failed: %s", exc)

        features_json = _json.dumps({
            "branch_id": bid,
            "stage": event["stage"],
            "contract_passed": contract_result.passed,
            "verification_passed": verification_result.passed,
            "canary_passed": canary_result.passed,
            "win_rate": stats.win_rate if stats else None,
            "median_delta": stats.median_delta if stats else None,
            "retry_count": branch.retry_count,
            "failure_codes": branch.failure_codes,
        })
        try:
            self._registry.record_decision(
                bid,
                features_json,
                decision.value,
                _json.dumps(list(decision_reason_codes)) if decision_reason_codes else "[]",
            )
        except Exception as exc:
            logger.debug("registry.record_decision failed: %s", exc)

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
    ) -> StepResult:
        bid = branch.branch_id
        logger.info("Branch %s: decision=%s", bid, decision.value)

        # Record event + decision in lineage registry
        self._record_step_lineage(
            branch=branch,
            hypothesis=hypothesis,
            patch=self._branch_patches.get(bid),
            contract_result=contract_result,
            verification_result=verification_result,
            canary_result=canary_result,
            protocol_result=protocol_result,
            decision=decision,
            hypothesis_id=h_record.hypothesis_id,
            decision_reason_codes=protocol_result.reason_codes if protocol_result else None,
        )

        # CONTINUE_EXPLORE — preserve workspace when screening shows positive signal (§11.2)
        if decision == Decision.CONTINUE_EXPLORE:
            # Preserve workspace + patch if verification passed and screening has positive signal.
            # This enables iterative evolution: the next hypothesis builds on the current code.
            verification_passed = verification_result.passed
            has_positive_signal = (
                protocol_result is not None
                and protocol_result.stats is not None
                and protocol_result.stats.win_rate > 0
            )
            preserve_workspace = verification_passed and has_positive_signal

            if not preserve_workspace:
                # Revert: discard workspace and patch for this round
                ws = self._branch_workspaces.get(bid)
                if ws:
                    try:
                        self._materializer.cleanup(ws)
                    except Exception:
                        pass
                    del self._branch_workspaces[bid]
                self._branch_patches.pop(bid, None)

            # Branch direction tracking (Sprint 4)
            if has_positive_signal:
                self._branch_zero_win_streaks[bid] = 0
                if branch.direction is None:
                    # First positive signal on this branch — lock in direction
                    branch.direction = (
                        f"{hypothesis.change_locus}: "
                        f"{(hypothesis.hypothesis_text or '')[:100]}"
                    )
                    logger.debug("Branch %s: direction set to %r", bid, branch.direction)
            else:
                streak = self._branch_zero_win_streaks.get(bid, 0) + 1
                self._branch_zero_win_streaks[bid] = streak
                if streak >= 3 and branch.direction is not None:
                    logger.debug(
                        "Branch %s: %d consecutive 0-win-rate rounds — clearing direction", bid, streak
                    )
                    branch.direction = None

            # Always discard current hypothesis — a new one is generated next round
            self._branch_hypotheses.pop(bid, None)
            self._hyp_store.mark_status(h_record.hypothesis_id, "rejected")
            # For EXPLORE_EXPAND the branch is not already in EXPLORE — call apply_decision
            # so the transition map (EXPLORE_EXPAND → EXPLORE) fires correctly.
            # Skip STALE_WEIGHT_UPDATE: let it flow to reconcile unchanged.
            if branch.state not in (BranchState.EXPLORE, BranchState.STALE_WEIGHT_UPDATE):
                try:
                    self._branch_ctrl.apply_decision(bid, decision)
                except StateTransitionError as exc:
                    logger.error(
                        "Branch %s: apply_decision(CONTINUE_EXPLORE) from %s failed: %s",
                        bid, branch.state.value, exc,
                    )
            # Otherwise branch stays as-is — EXPLORE needs no transition,
            # STALE_WEIGHT_UPDATE flows to reconcile on next step.
            self._recent_abandoned_count = 0
            return StepResult(
                action=action_label,  # type: ignore[arg-type]
                branch_id=bid,
                decision=decision,
                reason="CONTINUE_EXPLORE: re-propose next step",
            )

        # PROMOTE — transition branch to PROMOTED first so mark_all_stale skips it,
        # then update champion and mark remaining active branches stale.
        if decision == Decision.PROMOTE:
            try:
                self._branch_ctrl.apply_decision(bid, decision)
            except StateTransitionError as exc:
                logger.error("Branch %s: apply_decision(%s) failed: %s", bid, decision.value, exc)
            # T04: mark the original hypothesis as promoted
            self._hyp_store.mark_status(h_record.hypothesis_id, "promoted")
            self._branch_current_hypothesis.pop(bid, None)
            self._on_promote(branch)
            return StepResult(
                action=action_label,  # type: ignore[arg-type]
                branch_id=bid,
                decision=decision,
                reason=f"decision={decision.value}",
            )

        # ABANDON
        if decision == Decision.ABANDON:
            # I1: check if T4 soft-abandon already handled this branch
            updated_branch = self._branch_ctrl.get_branch(bid)
            if updated_branch and updated_branch.state == BranchState.ABANDONED:
                # T4 path already processed — clean up deferred patch and skip ABANDON dispatch
                self._branch_patches.pop(bid, None)
                return StepResult(
                    action="soft_abandon",
                    branch_id=bid,
                    decision=decision,
                    reason="T4: win_rate < 0.3",
                )
            self._recent_abandoned_count += 1
            ws = self._branch_workspaces.pop(bid, None)
            if ws:
                try:
                    self._materializer.archive_workspace(ws, bid)
                except Exception as exc:
                    logger.debug("Branch %s: archive failed: %s", bid, exc)
                try:
                    self._materializer.cleanup(ws)
                except Exception:
                    pass
            self._branch_hypotheses.pop(bid, None)
            self._branch_patches.pop(bid, None)
            # T04: mark original hypothesis as rejected and clear mapping
            self._hyp_store.mark_status(h_record.hypothesis_id, "rejected")
            self._branch_current_hypothesis.pop(bid, None)
        else:
            self._recent_abandoned_count = 0

        try:
            self._branch_ctrl.apply_decision(bid, decision)
        except StateTransitionError as exc:
            logger.error("Branch %s: apply_decision(%s) failed: %s", bid, decision.value, exc)

        try:
            _b = self._branch_ctrl.get_branch(bid)
            if _b:
                self._branch_store.save(_b)
        except Exception as _exc:
            logger.debug("BranchStore.save (decision) failed: %s", _exc)

        return StepResult(
            action=action_label,  # type: ignore[arg-type]
            branch_id=bid,
            decision=decision,
            reason=f"decision={decision.value}",
        )

    # ------------------------------------------------------------------
    # Promote
    # ------------------------------------------------------------------

    def _on_promote(self, branch: Branch) -> None:
        """Update champion immediately (pre-optimized weights) and launch bg weight opt.

        R1: returns in seconds — weight optimization runs in a daemon thread.
        """
        import os as _os
        import shutil as _shutil
        from scion.runtime.workspace import _make_tree_writable
        bid = branch.branch_id

        # I2: Promotion resets stagnation counters — new champion establishes new baseline
        self._recent_abandoned_count = 0
        self._soft_abandon_streak = 0
        # I4: Reset escape opportunity for the new champion cycle
        self._hard_stagnation_escape_used = False
        logger.debug("Branch %s promoted → stagnation counters reset", bid)

        ws = self._branch_workspaces.get(bid)
        if ws is None:
            logger.warning("Branch %s promoted but no workspace found", bid)
            return

        with self._champion_lock:
            new_version = self._champion.version + 1
            prev_solver_config_hash = self._champion.solver_config_hash
            prev_pool = self._champion.operator_pool

        # T3: Create mutable staging at champions/champion_v{N} from promoted workspace.
        staging_path = str(self._materializer._champions_dir / f"champion_v{new_version}")
        try:
            if _os.path.exists(staging_path):
                from pathlib import Path as _Path
                _make_tree_writable(_Path(staging_path))
                _shutil.rmtree(staging_path)
            _shutil.copytree(ws, staging_path)
            from pathlib import Path as _Path
            _make_tree_writable(_Path(staging_path))
        except Exception as exc:
            logger.error("Branch %s: mutable staging failed: %s", bid, exc)
            staging_path = ws  # fallback

        # Read current weights before freezing (bg thread will use these)
        param_cfg = self._spec.parameter_search
        current_weights: dict = {}
        if param_cfg.enabled and self._experiment_protocol is not None:
            try:
                from scion.runtime.pool_manager import read_weights
                registry_path = _os.path.join(staging_path, "registry.yaml")
                current_weights = read_weights(registry_path) if _os.path.exists(registry_path) else {}
            except Exception as exc:
                logger.warning("Branch %s: failed to read weights before freeze: %s", bid, exc)

        # T3: Freeze staging → final champion snapshot (read-only)
        try:
            self._materializer.freeze_snapshot(staging_path)
        except Exception as exc:
            logger.error("Failed to freeze staging %s: %s", staging_path, exc)

        snapshot_path = staging_path

        # Rebuild operator_pool from final registry.yaml (pre-optimized weights)
        from scion.runtime.pool_manager import read_registry
        registry_path = _os.path.join(snapshot_path, "registry.yaml")
        try:
            final_pool = read_registry(registry_path)
        except Exception:
            final_pool = prev_pool  # fallback

        # T4: Use compute_snapshot_hash (includes registry.yaml) for champion hash
        code_hash = self._materializer.compute_snapshot_hash(snapshot_path)
        new_champion = ChampionState(
            version=new_version,
            operator_pool=final_pool,
            solver_config_hash=prev_solver_config_hash,
            code_snapshot_path=snapshot_path,
            code_snapshot_hash=code_hash,
            promoted_at=datetime.now().isoformat(),
        )

        # Update champion immediately with pre-optimized weights (R1)
        with self._champion_lock:
            self._champion = new_champion
        self._rounds_since_last_promote = 0
        stale_ids = self._branch_ctrl.mark_all_stale(new_version)
        logger.info("Promoted branch %s to champion v%d; marked %d branches stale",
                    bid, new_version, len(stale_ids))

        # J1: Record champion promotion in search memory (J-patch: include operator name + screening wr)
        patch = self._branch_patches.get(bid)
        op_name = patch.file_path.split('/')[-1].replace('.py', '') if patch and patch.file_path else 'unknown'
        # Find most recent screening wr for this branch
        scr_wr = None
        for s in reversed(self._step_history):
            if s.branch_id == bid and s.protocol_result and s.protocol_result.stage == ExperimentStage.SCREENING:
                scr_wr = s.protocol_result.stats.win_rate
                break
        desc = f"→v{new_version} {op_name} (R{self._round_num}"
        if scr_wr is not None:
            desc += f", scr_wr={scr_wr:.2f}"
        desc += ")"
        self._search_memory.record_champion_promotion(desc, new_version)

        # J6: Persist champion to SQLite
        try:
            self._champion_store.promote(new_champion)
        except Exception as exc:
            logger.warning("Failed to persist champion v%d to store: %s", new_version, exc)

        # Launch background weight optimization (R2)
        if param_cfg.enabled and self._experiment_protocol is not None:
            t = threading.Thread(
                target=self._bg_weight_opt_task,
                args=(staging_path, new_version, current_weights),
                daemon=True,
                name=f"weight-opt-v{new_version}",
            )
            self._pending_weight_opt_threads.append(t)
            t.start()

    def _bg_weight_opt_task(
        self, staging_path: str, version: int, current_weights: dict
    ) -> None:
        """Background thread: run weight opt and update champion on success.

        Creates a NEW immutable snapshot rather than modifying the original.
        Atomic pointer switch under champion_lock.
        """
        import os as _os
        import shutil as _shutil
        import time as _time
        from scion.runtime.workspace import _make_tree_writable
        from pathlib import Path as _Path

        t0 = _time.monotonic()
        try:
            opt_result = self._run_weight_optimization(staging_path, version, current_weights)
        except Exception as exc:
            logger.error("Background weight opt failed for champion v%d: %s", version, exc)
            return

        elapsed_min = (_time.monotonic() - t0) / 60.0

        if opt_result is None:
            return

        self._latest_weight_opt_result = opt_result
        try:
            self._registry.record_weight_optimization(
                campaign_id=self._campaign_id,
                champion_version=version,
                result=opt_result,
            )
        except Exception as exc:
            logger.warning("Background weight opt: failed to record result: %s", exc)

        if not opt_result.improved:
            logger.info(
                "Background weight opt complete for champion v%d (%.1f min) — no improvement",
                version, elapsed_min,
            )
            return

        # Determine new revision number
        with self._champion_lock:
            if self._champion.version != version:
                logger.warning(
                    "Background weight opt for champion v%d discarded — "
                    "champion has advanced to v%d",
                    version, self._champion.version,
                )
                return
            new_revision = self._champion.weight_revision + 1

        # Create NEW immutable snapshot with optimized weights (never modify original)
        new_snapshot_path = str(self._materializer._champions_dir / f"champion_v{version}_r{new_revision}")
        try:
            if _os.path.exists(new_snapshot_path):
                _make_tree_writable(_Path(new_snapshot_path))
                _shutil.rmtree(new_snapshot_path)
            _shutil.copytree(staging_path, new_snapshot_path)
            _make_tree_writable(_Path(new_snapshot_path))

            from scion.runtime.pool_manager import update_weights, read_registry
            registry_path = _os.path.join(new_snapshot_path, "registry.yaml")
            if _os.path.exists(registry_path):
                update_weights(registry_path, opt_result.best_weights)
            self._materializer.freeze_snapshot(new_snapshot_path)
        except Exception as exc:
            logger.error(
                "Background weight opt: failed to create snapshot for champion v%d_r%d: %s",
                version, new_revision, exc,
            )
            return

        # Recompute hash and read updated pool
        try:
            registry_path = _os.path.join(new_snapshot_path, "registry.yaml")
            new_pool = read_registry(registry_path)
            new_hash = self._materializer.compute_snapshot_hash(new_snapshot_path)
        except Exception as exc:
            logger.error(
                "Background weight opt: failed to recompute hash for champion v%d_r%d: %s",
                version, new_revision, exc,
            )
            return

        # Atomic pointer switch
        with self._champion_lock:
            if self._champion.version != version:
                logger.warning(
                    "Background weight opt for champion v%d discarded — "
                    "champion has advanced to v%d",
                    version, self._champion.version,
                )
                return
            self._champion = ChampionState(
                version=self._champion.version,
                operator_pool=new_pool,
                solver_config_hash=self._champion.solver_config_hash,
                code_snapshot_path=new_snapshot_path,
                code_snapshot_hash=new_hash,
                promoted_at=self._champion.promoted_at,
                weight_revision=new_revision,
            )

        logger.info(
            "Background weight opt complete for champion v%d_r%d (%.1f min)",
            version, new_revision, elapsed_min,
        )

        # Stage-aware stale: only mark screening/explore branches
        try:
            stale_weight_ids = self._branch_ctrl.mark_stale_for_weight_update(version)
            if stale_weight_ids:
                logger.info(
                    "Background weight opt: marked %d screening branches stale for re-screening",
                    len(stale_weight_ids),
                )
        except Exception as exc:
            logger.warning("Background weight opt: failed to mark branches stale: %s", exc)

    def _run_weight_optimization(
        self, champion_snapshot: str, version: int, current_weights: dict
    ):
        """Run weight optimization on a copy of the champion snapshot.

        Args:
            champion_snapshot: Path to the mutable staging snapshot directory.
            version: Champion version number (used for eval_ws naming and seed).
            current_weights: Current champion weights — passed to optimizer as
                true baseline (T1).

        Returns WeightOptimizationResult or None if prerequisites are missing.
        """
        import os as _os
        import shutil
        from scion.parameter.optimizer import RandomLocalWeightOptimizer, BayesianWeightOptimizer
        from scion.parameter.evaluator import collect_baseline, evaluate_weights
        from scion.parameter.search_space import ParameterSearchSpace

        param_cfg = self._spec.parameter_search

        # Locate runner
        runner = getattr(self._experiment_protocol, 'runner',
                         getattr(self._experiment_protocol, '_runner', None))
        if runner is None:
            logger.warning("No runner available for weight optimization")
            return None

        # Require a registry.yaml in the snapshot
        registry_path = _os.path.join(champion_snapshot, "registry.yaml")
        if not _os.path.exists(registry_path):
            logger.warning("No registry.yaml in snapshot %s; skipping weight opt", champion_snapshot)
            return None

        # Create evaluation workspace (isolated copy of champion snapshot)
        eval_ws = _os.path.join(self._campaign_dir, f"weight_opt_v{version}")
        if _os.path.exists(eval_ws):
            shutil.rmtree(eval_ws)
        shutil.copytree(champion_snapshot, eval_ws)
        # Ensure eval workspace is writable
        for _root, _dirs, _files in _os.walk(eval_ws):
            for _d in _dirs:
                _os.chmod(_os.path.join(_root, _d), 0o755)
            for _f in _files:
                _os.chmod(_os.path.join(_root, _f), 0o644)

        # Determine eval cases (fall back to screening split)
        eval_cases = list(param_cfg.eval_cases)
        if not eval_cases:
            eval_cases = list(self._split_manifest.screening)
        resolved_cases = [
            _os.path.join(self._spec.root_dir, c) if not _os.path.isabs(c) else c
            for c in eval_cases
        ]

        seeds = list(self._seed_ledger.screening)[:param_cfg.n_eval_seeds]
        time_limit = getattr(getattr(self._spec, 'solver', None), 'time_limit_sec', 300)

        operator_names = tuple(current_weights.keys())

        # Collect baseline objectives for evaluate_weights comparisons
        baseline = collect_baseline(eval_ws, resolved_cases, seeds, runner, time_limit)

        # Build search space
        search_space = ParameterSearchSpace(
            operator_names=operator_names,
            weight_bounds=param_cfg.weight_bounds,
            n_initial_random=param_cfg.n_initial_random,
            n_iterations=param_cfg.n_iterations,
            n_eval_seeds=param_cfg.n_eval_seeds,
            eval_cases=tuple(resolved_cases),
        )

        def eval_fn(weights):
            return evaluate_weights(
                weights=weights,
                workspace=eval_ws,
                cases=resolved_cases,
                seeds=seeds,
                runner=runner,
                time_limit_sec=time_limit,
                baseline_objectives=baseline,
            )

        optimizer = RandomLocalWeightOptimizer(search_space, eval_fn, seed=version)
        if getattr(param_cfg, 'strategy', 'random_local') == 'bayesian':
            optimizer = BayesianWeightOptimizer(search_space, eval_fn, seed=version)

        # T2: artifacts dir for saving observations JSON
        artifacts_dir = _os.path.join(self._campaign_dir, "artifacts")
        _os.makedirs(artifacts_dir, exist_ok=True)

        # T1: pass current_weights so optimizer evaluates true baseline first
        result = optimizer.optimize(current_weights, artifacts_dir=artifacts_dir)

        try:
            shutil.rmtree(eval_ws)
        except Exception:
            pass

        return result

    # ------------------------------------------------------------------
    # Stagnation detection (T25/T23)
    # ------------------------------------------------------------------

    def _run_stagnation_check(self) -> None:
        """Check for stagnation signals after each round and log critical ones."""
        signals = self._stagnation_detector.check(
            self._step_history, failure_streak=self._failure_streak
        )
        if signals:
            self._stagnation_signals = signals  # keep latest signals
            for sig in signals:
                if sig.severity == "critical":
                    logger.warning(
                        "STAGNATION [%s] %s — suggested: %s",
                        sig.kind, sig.detail, sig.suggested_action,
                    )
                else:
                    logger.info(
                        "Stagnation signal [%s] %s — suggested: %s",
                        sig.kind, sig.detail, sig.suggested_action,
                    )
            # T23: generate structured diagnosis on critical signals
            diagnosis = self._stagnation_detector.diagnose(
                self._round_num, self._step_history,
                failure_streak=self._failure_streak,
            )
            if diagnosis is not None:
                diag_dict = {
                    "round_num": diagnosis.round_num,
                    "recommendation": diagnosis.recommendation,
                    "family_distribution": diagnosis.family_distribution,
                    "failure_pattern": diagnosis.failure_pattern,
                    "signals": [
                        {
                            "kind": s.kind,
                            "severity": s.severity,
                            "detail": s.detail,
                            "suggested_action": s.suggested_action,
                        }
                        for s in diagnosis.signals
                    ],
                }
                self._diagnostics.append(diag_dict)
                logger.warning(
                    "Campaign diagnosis at round %d: %s",
                    diagnosis.round_num, diagnosis.recommendation,
                )

    def _check_soft_stagnation(self) -> None:
        """If soft_abandon_streak hits limit, force the next branch to diversify locus.

        soft-stagnation means: champion is too strong in current locus, not that the
        framework is broken. Response = diversify search direction, NOT terminate.
        """
        limit = self._term_checker.config.soft_stagnation_limit
        if self._soft_abandon_streak < limit:
            return

        logger.info(
            "Soft stagnation detected: %d consecutive T4 soft-abandons → forcing locus diversification",
            self._soft_abandon_streak,
        )

        # Determine current dominant locus from recent step history
        recent = self._step_history[-limit:] if len(self._step_history) >= limit else self._step_history
        locus_counts: Dict[str, int] = {}
        for step in recent:
            locus = getattr(step.hypothesis, "change_locus", None) or ""
            if locus:
                locus_counts[locus] = locus_counts.get(locus, 0) + 1

        # Force a non-dominant locus on next branch creation
        dominant_locus = max(locus_counts, key=locus_counts.get) if locus_counts else ""
        all_loci = set(getattr(self._spec, 'operator_categories', [])) or {"vehicle_level", "order_level"}
        unexplored = all_loci - {dominant_locus}
        self._forced_next_locus = next(iter(sorted(unexplored)), None)

        self._soft_abandon_streak = 0  # reset after acting

        logger.info(
            "Soft stagnation: dominant_locus=%s → forcing next branch locus=%s",
            dominant_locus, self._forced_next_locus,
        )

    def _consume_forced_locus(self) -> Optional[str]:
        """Consume and return forced locus (set by soft/hard stagnation), or None."""
        forced = self._forced_next_locus
        if forced is not None:
            self._forced_next_locus = None
            logger.info("Applying forced locus diversification: %s", forced)
        return forced

    def _get_diversification_locus(self) -> Optional[str]:
        """Determine the best locus to diversify into, using StagnationDetector diagnosis."""
        diagnosis = self._stagnation_detector.diagnose(
            self._round_num, self._step_history,
            failure_streak=self._failure_streak,
        )
        # Flip from dominant locus in recent history
        recent = self._step_history[-5:] if len(self._step_history) >= 5 else self._step_history
        locus_counts: Dict[str, int] = {}
        for step in recent:
            locus = getattr(step.hypothesis, "change_locus", None) or ""
            if locus:
                locus_counts[locus] = locus_counts.get(locus, 0) + 1
        dominant = max(locus_counts, key=locus_counts.get) if locus_counts else ""
        all_loci = set(getattr(self._spec, 'operator_categories', [])) or {"vehicle_level", "order_level"}
        unexplored = all_loci - {dominant}
        return next(iter(sorted(unexplored)), None)

    # ------------------------------------------------------------------
    # Failure handling
    # ------------------------------------------------------------------

    def _handle_failure(
        self,
        branch: Branch,
        failure: FailureEvent,
        hypothesis_already_recorded: bool = False,
    ) -> None:
        """Route failure and execute the appropriate recovery strategy.

        Args:
            hypothesis_already_recorded: When True, skip the hypothesis memory
                write in this method (the caller has already called mark_status
                on the original record).  Used for verification_heavy failures
                to prevent a duplicate blacklisted record.
        """
        # Sprint H2 T1: Update campaign-level failure counters before routing
        fcode = failure.category
        self._failure_streak[fcode] = self._failure_streak.get(fcode, 0) + 1
        self._total_failures[fcode] = self._total_failures.get(fcode, 0) + 1

        action = self._failure_router.route(
            failure, branch,
            streak=self._failure_streak[fcode],
            total=self._total_failures[fcode],
        )
        branch.retry_count += 1
        branch.failure_codes.append(failure.category.upper())
        logger.debug(
            "Branch %s: failure=%s streak=%d → action=%s (budget=%s)",
            branch.branch_id, failure.category,
            self._failure_streak[fcode], action.action, action.consumes_budget,
        )
        if action.consumes_budget:
            self._budget.used += 1
        if action.writes_hypothesis_memory and not hypothesis_already_recorded:
            # Record in blacklist via HypothesisStore
            hyp = self._branch_hypotheses.get(branch.branch_id)
            if hyp:
                record = HypothesisRecord(
                    hypothesis_id=str(uuid.uuid4()),
                    branch_id=branch.branch_id,
                    change_locus=hyp.change_locus,
                    action=hyp.action,
                    status="blacklisted",
                    target_file=hyp.target_file,
                    hypothesis_text=hyp.hypothesis_text,
                    base_champion_version=self._champion.version if self._champion else 0,
                )
                self._hyp_store.save(record)

        bid = branch.branch_id

        if action.action == "retry_llm":
            branch.consecutive_llm_retries += 1
            if branch.consecutive_llm_retries >= 3:
                # Downgrade to discard after too many consecutive LLM retries
                logger.info(
                    "Branch %s: retry_llm exhausted (%d consecutive) — downgrading to discard",
                    bid, branch.consecutive_llm_retries,
                )
                branch.consecutive_llm_retries = 0
                branch.pending_retry = False
                self._branch_patches.pop(bid, None)
                branch.current_code_hash = branch.last_clean_code_hash
                if branch.state not in (BranchState.ABANDONED, BranchState.PROMOTED):
                    branch.state = BranchState.EXPLORE
                    branch.updated_at = datetime.now()
            else:
                branch.pending_retry = True

        elif action.action == "retry_infra":
            branch.consecutive_llm_retries = 0
            branch.pending_retry = False
            branch.infra_block_count += 1
            if branch.infra_block_count >= 2:
                logger.warning(
                    "Branch %s: permanent infra failure (block #%d) — abandoning",
                    bid, branch.infra_block_count,
                )
                try:
                    self._branch_ctrl.apply_decision(bid, Decision.ABANDON)
                except StateTransitionError:
                    pass  # already in terminal state
            else:
                logger.info("Branch %s: infra failure — blocking for 3 rounds", bid)
                try:
                    self._branch_ctrl.block_infra(bid)
                    branch.blocked_rounds = 0
                except StateTransitionError as exc:
                    logger.debug("Branch %s: block_infra skipped: %s", bid, exc)

        elif action.action == "discard":
            branch.pending_retry = False
            branch.consecutive_llm_retries = 0
            self._branch_patches.pop(bid, None)
            branch.current_code_hash = branch.last_clean_code_hash
            if branch.state not in (BranchState.ABANDONED, BranchState.PROMOTED, BranchState.STALE, BranchState.STALE_WEIGHT_UPDATE):
                branch.state = BranchState.EXPLORE
                branch.updated_at = datetime.now()

        elif action.action == "abandon":
            branch.pending_retry = False
            branch.consecutive_llm_retries = 0
            try:
                self._branch_ctrl.apply_decision(bid, Decision.ABANDON)
            except StateTransitionError:
                pass  # already in terminal state

        elif action.action == "infra_suspected":
            # Sprint H2: Consecutive light failures → suspected infra issue
            logger.warning(
                "Branch %s: infra_suspected after %d consecutive '%s' failures — blocking",
                bid, self._failure_streak[fcode], fcode,
            )
            branch.pending_retry = False
            branch.consecutive_llm_retries = 0
            try:
                self._registry.record_event({
                    "campaign_id": self._campaign_id,
                    "branch_id": bid,
                    "timestamp": datetime.now().isoformat(),
                    "event_kind": "infra_suspected",
                    "failure_code": fcode,
                    "streak": self._failure_streak[fcode],
                    "suggested_action": "check_environment",
                })
            except Exception:
                pass
            try:
                self._branch_ctrl.block_infra(bid)
                branch.blocked_rounds = 0
            except StateTransitionError as exc:
                logger.debug("Branch %s: block_infra (infra_suspected) skipped: %s", bid, exc)

        elif action.action == "abandon_fast":
            # Sprint H2: Consecutive heavy failures → fast abandon (skip budget deduction)
            logger.warning(
                "Branch %s: abandon_fast after %d consecutive '%s' failures",
                bid, self._failure_streak[fcode], fcode,
            )
            branch.pending_retry = False
            branch.consecutive_llm_retries = 0
            try:
                self._registry.record_event({
                    "campaign_id": self._campaign_id,
                    "branch_id": bid,
                    "timestamp": datetime.now().isoformat(),
                    "event_kind": "abandon_fast",
                    "failure_code": fcode,
                    "streak": self._failure_streak[fcode],
                })
            except Exception:
                pass
            try:
                self._branch_ctrl.apply_decision(bid, Decision.ABANDON)
            except StateTransitionError:
                pass  # already in terminal state

        # Persist branch state after any failure action
        try:
            _b = self._branch_ctrl.get_branch(bid)
            if _b:
                self._branch_store.save(_b)
        except Exception as _exc:
            logger.debug("BranchStore.save (failure) failed: %s", _exc)

    def _tick_blocked_branches(self) -> None:
        """Increment blocked_rounds for every BLOCKED_INFRA branch; auto-unblock at 3 rounds."""
        for branch in self._branch_ctrl.get_active_branches():
            if branch.state != BranchState.BLOCKED_INFRA:
                continue
            branch.blocked_rounds += 1
            if branch.blocked_rounds >= 3:
                logger.info(
                    "Branch %s: auto-unblocking after %d blocked rounds",
                    branch.branch_id, branch.blocked_rounds,
                )
                try:
                    self._branch_ctrl.unblock_infra(branch.branch_id)
                except StateTransitionError as exc:
                    logger.debug("Branch %s: unblock_infra skipped: %s", branch.branch_id, exc)
                branch.blocked_rounds = 0
                branch.consecutive_llm_retries = 0

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
        import json as _json
        from pathlib import Path as _Path
        from collections import Counter as _Counter

        # --- Aggregate cache stats across all steps ---
        total_tokens = 0
        cache_read_tokens = 0
        cache_create_tokens = 0
        for step in self._step_history:
            cs = step.cache_stats or {}
            total_tokens += cs.get("total", 0)
            cache_read_tokens += cs.get("cache_read", 0)
            cache_create_tokens += cs.get("cache_create", 0)
        cache_hit_rate = round(cache_read_tokens / total_tokens, 4) if total_tokens > 0 else 0.0

        # --- Verification failure breakdown by V-code ---
        vfail_counter: Dict[str, int] = {}
        for step in self._step_history:
            if step.failure_stage == "verification" and step.failure_detail:
                fd = step.failure_detail or ""
                vcode = fd.split(":")[0].strip() if ":" in fd else fd.split()[0] if fd else "unknown"
                vfail_counter[vcode] = vfail_counter.get(vcode, 0) + 1

        # --- Action/locus coverage ---
        action_locus_counter: Dict[str, int] = {}
        for step in self._step_history:
            key = f"{step.hypothesis.action}/{step.hypothesis.change_locus}"
            action_locus_counter[key] = action_locus_counter.get(key, 0) + 1

        # --- Family coverage (mechanism labels) ---
        family_counter: Dict[str, int] = {}
        from scion.proposal.context_manager import _extract_mechanism_label
        _taxonomy = getattr(getattr(self._spec, 'family_taxonomy', None), 'families', None)
        for step in self._step_history:
            label = _extract_mechanism_label(step.hypothesis.hypothesis_text or "", taxonomy=_taxonomy)
            family_counter[label] = family_counter.get(label, 0) + 1

        # --- Budget utilization ---
        budget_utilization = round(self._budget.used / self._budget.total, 4) if self._budget.total > 0 else 0.0

        summary: Dict[str, Any] = {
            "campaign_id": self._campaign_id,
            "total_rounds": self._round_num,
            "champion_version": self._champion.version,
            "stopped_reason": (
                "api_balance_exhausted" if self._balance_exhausted
                else ("circuit_breaker" if self._circuit_breaker.is_tripped else None)
            ),
            "cache_stats": {
                "total_tokens": total_tokens,
                "cache_read_tokens": cache_read_tokens,
                "cache_create_tokens": cache_create_tokens,
                "cache_hit_rate": cache_hit_rate,
            },
            "verification_failure_breakdown": vfail_counter,
            "action_locus_coverage": action_locus_counter,
            "family_coverage": family_counter,
            "budget_utilization": budget_utilization,
            "stagnation_signals": [
                {
                    "kind": s.kind,
                    "severity": s.severity,
                    "detail": s.detail,
                    "suggested_action": s.suggested_action,
                }
                for s in self._stagnation_signals
            ],
            "diagnostics": self._diagnostics,
            "steps": [],
        }
        for step in self._step_history:
            step_data: Dict[str, Any] = {
                "round": step.round_num,
                "branch_id": step.branch_id,
                "decision": step.decision.value if step.decision is not None else None,
                "contract_passed": step.contract_passed,
                "verification_passed": step.verification_passed,
                "failure_stage": step.failure_stage,
                "failure_detail": step.failure_detail,
                "verification_detail": step.verification_detail,
                "code_archive_ref": step.code_archive_ref,
                "cache_stats": step.cache_stats,
                "hypothesis": {
                    "text": (step.hypothesis.hypothesis_text or "")[:200],
                    "action": step.hypothesis.action,
                    "change_locus": step.hypothesis.change_locus,
                    "target_file": step.hypothesis.target_file,
                },
            }
            if step.protocol_result and step.protocol_result.stats:
                stats = step.protocol_result.stats
                pr = step.protocol_result
                step_data["protocol_result"] = {
                    "stage": pr.stage.value if hasattr(pr.stage, "value") else str(pr.stage),
                    "win_rate": stats.win_rate,
                    "median_delta": stats.median_delta,
                    "ci_low": stats.ci_low,
                    "ci_high": stats.ci_high,
                    "gate_outcome": pr.gate_outcome,
                }
                if pr.case_feedback:
                    step_data["case_feedback_summary"] = [
                        {
                            "case_id": cf.case_id,
                            "dominant_result": cf.dominant_result,
                            "decisive": cf.decisive_metric if hasattr(cf, 'decisive_metric') else getattr(cf, 'dominant_decisive_objective', ''),
                        }
                        for cf in pr.case_feedback[:20]
                    ]
            summary["steps"].append(step_data)

        out_path = _Path(self._campaign_dir) / "campaign_summary.json"
        try:
            out_path.write_text(_json.dumps(summary, indent=2, default=str))
        except Exception as exc:
            logger.warning("Failed to write campaign_summary.json: %s", exc)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _build_verification_detail(vresult: VerificationResult) -> Optional[str]:
    """Build a full verification failure detail string for LLM diagnosis."""
    if not vresult or vresult.passed:
        return None
    failed = [c for c in vresult.checks if not c.passed]
    if not failed:
        return vresult.first_failure
    lines = [f"severity={vresult.failure_severity or 'unknown'}  first_failure={vresult.first_failure or 'N/A'}"]
    for c in failed:
        lines.append(f"  [{c.name}] ({c.severity}) {c.detail}")
    return "\n".join(lines)
