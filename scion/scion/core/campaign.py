"""CampaignManager — main loop integrating all Scion modules (Phase 5)."""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Tuple

from scion.config.problem import ProtocolConfig, ProblemSpec, SplitManifest, SeedLedgerConfig
from scion.contract.gate import ContractGate
from scion.core.branch import BranchController, StateTransitionError
from scion.core.decision import DecisionEngine
from scion.core.features import SafeFeatureExtractor, BudgetState
from scion.core.models import (
    Branch, BranchState, CanaryResult, ChampionState, ContractResult,
    Decision, FailureEvent, HypothesisProposal, HypothesisRecord,
    PatchProposal, ProtocolResult, StepRecord, VerificationResult, CheckResult,
)
from scion.core.scheduler import Scheduler
from scion.core.termination import CampaignState, TerminationChecker, TerminationConfig
from scion.failure.router import FailureRouter, RetryConfig
from scion.proposal.context_manager import ContextManager
from scion.proposal.engine import CreativeLayer
from scion.proposal.llm_client import LLMRetryExhaustedError, LLMFormatError, LLMTimeoutError
from scion.runtime.workspace import WorkspaceMaterializer

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Verification Gate (minimal stub — Phase 5 MVP)
# ---------------------------------------------------------------------------

class VerificationGate:
    """Runs static checks on a workspace after a patch is applied.

    Phase 5 MVP: performs only a lightweight syntax re-check (the patch has
    already passed ContractGate C6/C7/C8/C9).  A real implementation would
    also run unit tests, regression tests, feasibility oracle, etc.

    Inject a custom instance via CampaignManager(..., verification_gate=...)
    to override in tests.
    """

    def run(self, workspace: str, patch: PatchProposal) -> VerificationResult:
        """Return a VerificationResult for the patched workspace."""
        import ast, time
        t0 = time.monotonic_ns()

        if patch.action == "delete":
            check = CheckResult(
                name="SYNTAX", passed=True, severity="light",
                detail="delete — no syntax check", elapsed_ms=0,
            )
            return VerificationResult(passed=True, checks=(check,))

        try:
            ast.parse(patch.code_content)
            elapsed = int((time.monotonic_ns() - t0) / 1_000_000)
            check = CheckResult(
                name="SYNTAX", passed=True, severity="light",
                detail="syntax ok", elapsed_ms=elapsed,
            )
            return VerificationResult(passed=True, checks=(check,))
        except SyntaxError as exc:
            elapsed = int((time.monotonic_ns() - t0) / 1_000_000)
            check = CheckResult(
                name="SYNTAX", passed=False, severity="light",
                detail=f"SyntaxError: {exc}", elapsed_ms=elapsed,
            )
            return VerificationResult(
                passed=False, checks=(check,),
                failure_severity="light", first_failure="SYNTAX",
            )


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
    ) -> None:
        self._spec = problem_spec
        self._protocol_config = protocol_config
        self._split_manifest = split_manifest
        self._seed_ledger = seed_ledger
        self._llm_client = llm_client
        self._champion = champion
        self._campaign_dir = campaign_dir

        # Sub-modules
        self._branch_ctrl = BranchController()
        self._scheduler = Scheduler()
        self._contract_gate = ContractGate(problem_spec)
        self._decision_engine = DecisionEngine(protocol_config)
        self._feature_extractor = SafeFeatureExtractor()
        self._failure_router = FailureRouter(retry_config or RetryConfig())
        self._creative = CreativeLayer(llm_client)
        self._ctx_manager = ContextManager()
        self._materializer = WorkspaceMaterializer(
            campaign_dir,
            frozen_patterns=frozenset(
                problem_spec.search_space.frozen
            ) if problem_spec.search_space.frozen else None,
        )
        self._vgate = verification_gate or VerificationGate()
        self._experiment_protocol = experiment_protocol  # may be None (no runner)

        # Per-branch transient state
        self._branch_workspaces: Dict[str, str] = {}       # branch_id → workspace path
        self._branch_hypotheses: Dict[str, HypothesisProposal] = {}
        self._branch_patches: Dict[str, PatchProposal] = {}

        # Hypothesis memory (in-memory list for novelty / context; no SQLite in MVP)
        self._active_hypotheses: List[HypothesisRecord] = []
        self._blacklist: List[HypothesisRecord] = []

        # Experiment history — full record of every completed explore step
        self._step_history: List[StepRecord] = []
        self._round_num: int = 0

        # Budget / termination
        self._term_checker = TerminationChecker(termination_config or TerminationConfig())
        self._budget = budget or BudgetState(total=1000, used=0)
        self._n_experiments = 0
        self._recent_abandoned_count = 0
        self._start_time = datetime.now()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, max_rounds: int = 1000) -> None:
        """Run the campaign until a termination condition is met."""
        for _ in range(max_rounds):
            if self.should_stop():
                logger.info("Campaign terminated.")
                break
            result = self.run_one_step()
            if result.stopped:
                break

    def run_one_step(self) -> StepResult:
        """Execute one campaign step and return a StepResult."""
        if self.should_stop():
            return StepResult(action="stopped", stopped=True, reason="termination condition met")

        active = self._branch_ctrl.get_active_branches()
        sched = self._scheduler.select_next(active)

        # --- Create a new branch ---
        if sched.action == "create_new":
            branch = self._branch_ctrl.create_branch(self._champion)
            logger.info("Created new branch %s", branch.branch_id)
            result = self._run_explore_step(branch)
            result.action = "create_branch"
            return result

        branch = sched.branch
        assert branch is not None

        # --- Advance READY_* / expand states to their running state ---
        if branch.state in (
            BranchState.READY_VALIDATE,
            BranchState.READY_FROZEN,
            BranchState.EXPLORE_EXPAND,
            BranchState.VALIDATING_EXPAND,
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
        if branch.state == BranchState.STALE:
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
            return self._run_eval_step(branch)

        logger.warning(
            "Branch %s in unexpected state %s — skipping",
            branch.branch_id, branch.state.value,
        )
        return StepResult(
            action="skip", branch_id=branch.branch_id, reason=f"unhandled state {branch.state.value}"
        )

    def should_stop(self) -> bool:
        active = self._branch_ctrl.get_active_branches()
        cs = CampaignState(
            n_experiments=self._n_experiments,
            start_time=self._start_time,
            recent_abandoned_count=self._recent_abandoned_count,
            active_branches=active,
            can_create_new=True,  # always can create new in MVP
        )
        return self._term_checker.should_stop(cs)

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
        rnum = self._round_num

        # ---------- Round 1: generate hypothesis ----------
        hypothesis, h_record = self._round1_generate_hypothesis(branch)
        if hypothesis is None:
            return StepResult(action="explore", branch_id=bid, reason="hypothesis generation failed")

        # ---------- Contract gate: validate_hypothesis ----------
        c_result = self._contract_gate.validate_hypothesis(
            hypothesis, self._active_hypotheses, self._blacklist
        )
        if not c_result.passed:
            logger.info("Branch %s: hypothesis contract failed: %s", bid, c_result.failure_reason)
            failure = FailureEvent(category="contract", detail=c_result.failure_reason or "")
            self._handle_failure(branch, failure)
            self._step_history.append(StepRecord(
                round_num=rnum, branch_id=bid,
                hypothesis=hypothesis, patch=None,
                contract_passed=False, verification_passed=False,
                protocol_result=None, decision=Decision.ABANDON,
                failure_stage="hypothesis_contract",
                failure_detail=c_result.failure_reason,
            ))
            return StepResult(action="explore", branch_id=bid, reason="hypothesis contract failed")

        # Register hypothesis
        self._active_hypotheses.append(h_record)
        self._branch_hypotheses[bid] = hypothesis

        # ---------- Round 2: generate code ----------
        patch = self._round2_generate_code(branch, hypothesis)
        if patch is None:
            self._active_hypotheses.remove(h_record)
            self._step_history.append(StepRecord(
                round_num=rnum, branch_id=bid,
                hypothesis=hypothesis, patch=None,
                contract_passed=True, verification_passed=False,
                protocol_result=None, decision=Decision.ABANDON,
                failure_stage="code_generation",
                failure_detail="LLM code generation failed",
            ))
            return StepResult(action="explore", branch_id=bid, reason="code generation failed")

        # ---------- Contract gate: validate_patch ----------
        p_result = self._contract_gate.validate_patch(patch)
        if not p_result.passed:
            logger.info("Branch %s: patch contract failed: %s", bid, p_result.failure_reason)
            failure = FailureEvent(category="contract", detail=p_result.failure_reason or "")
            self._handle_failure(branch, failure)
            self._active_hypotheses.remove(h_record)
            self._step_history.append(StepRecord(
                round_num=rnum, branch_id=bid,
                hypothesis=hypothesis, patch=patch,
                contract_passed=False, verification_passed=False,
                protocol_result=None, decision=Decision.ABANDON,
                failure_stage="patch_contract",
                failure_detail=p_result.failure_reason,
            ))
            return StepResult(action="explore", branch_id=bid, reason="patch contract failed")

        # ---------- Apply patch ----------
        workspace = self._setup_workspace(branch)
        if workspace is None:
            self._active_hypotheses.remove(h_record)
            self._step_history.append(StepRecord(
                round_num=rnum, branch_id=bid,
                hypothesis=hypothesis, patch=patch,
                contract_passed=True, verification_passed=False,
                protocol_result=None, decision=Decision.ABANDON,
                failure_stage="workspace",
                failure_detail="workspace setup failed",
            ))
            return StepResult(action="explore", branch_id=bid, reason="workspace setup failed")

        try:
            code_hash = self._materializer.apply_patch(workspace, patch)
        except Exception as exc:
            logger.warning("Branch %s: apply_patch failed: %s", bid, exc)
            failure = FailureEvent(category="contract", detail=f"apply_patch: {exc}")
            self._handle_failure(branch, failure)
            self._active_hypotheses.remove(h_record)
            self._step_history.append(StepRecord(
                round_num=rnum, branch_id=bid,
                hypothesis=hypothesis, patch=patch,
                contract_passed=True, verification_passed=False,
                protocol_result=None, decision=Decision.ABANDON,
                failure_stage="workspace",
                failure_detail=f"apply_patch: {exc}",
            ))
            return StepResult(action="explore", branch_id=bid, reason="apply_patch failed")

        self._branch_patches[bid] = patch
        self._branch_ctrl.record_verification_result(bid, True, code_hash)

        # ---------- Verification gate ----------
        vresult = self._vgate.run(workspace, patch)
        if not vresult.passed:
            severity = vresult.failure_severity or "light"
            logger.info("Branch %s: verification failed (%s): %s", bid, severity, vresult.first_failure)
            cat = "verification_light" if severity == "light" else "verification_heavy"
            failure = FailureEvent(category=cat, detail=vresult.first_failure or "")
            if severity == "light":
                # Attempt fix
                fixed = self._attempt_fix(branch, patch, vresult)
                if fixed is not None:
                    try:
                        code_hash = self._materializer.apply_patch(workspace, fixed)
                        self._branch_patches[bid] = fixed
                        vresult = self._vgate.run(workspace, fixed)
                    except Exception:
                        pass
                if not vresult.passed:
                    self._handle_failure(branch, failure)
                    self._active_hypotheses.remove(h_record)
                    self._step_history.append(StepRecord(
                        round_num=rnum, branch_id=bid,
                        hypothesis=hypothesis, patch=patch,
                        contract_passed=True, verification_passed=False,
                        protocol_result=None, decision=Decision.ABANDON,
                        failure_stage="verification",
                        failure_detail=vresult.first_failure,
                    ))
                    return StepResult(action="explore", branch_id=bid, reason="verification failed (light)")
            else:
                self._handle_failure(branch, failure)
                self._blacklist.append(h_record)
                self._active_hypotheses.remove(h_record)
                self._step_history.append(StepRecord(
                    round_num=rnum, branch_id=bid,
                    hypothesis=hypothesis, patch=patch,
                    contract_passed=True, verification_passed=False,
                    protocol_result=None, decision=Decision.ABANDON,
                    failure_stage="verification",
                    failure_detail=vresult.first_failure,
                ))
                return StepResult(action="explore", branch_id=bid, reason="verification failed (heavy)")

        # ---------- Evaluate ----------
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
        # Record the completed step
        self._step_history.append(StepRecord(
            round_num=rnum, branch_id=bid,
            hypothesis=hypothesis,
            patch=self._branch_patches.get(bid, patch),
            contract_passed=True, verification_passed=True,
            protocol_result=protocol_result,
            decision=result.decision or Decision.ABANDON,
            failure_stage=None,
            failure_detail=None,
        ))
        return result

    # ------------------------------------------------------------------
    # EVAL-ONLY step (re-use workspace from EXPLORE)
    # ------------------------------------------------------------------

    def _run_eval_step(self, branch: Branch) -> StepResult:
        """Evaluation-only step for VALIDATING / FROZEN_TESTING branches."""
        bid = branch.branch_id
        workspace = self._branch_workspaces.get(bid)
        if workspace is None:
            # Workspace lost — abandon
            logger.warning("Branch %s: no workspace for eval step — abandoning", bid)
            self._branch_ctrl.apply_decision(bid, Decision.ABANDON)
            return StepResult(action="validate", branch_id=bid, reason="workspace not found")

        hypothesis = self._branch_hypotheses.get(bid)
        if hypothesis is None:
            logger.warning("Branch %s: no hypothesis for eval step — abandoning", bid)
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

        h_record = HypothesisRecord(
            hypothesis_id=str(uuid.uuid4()),
            branch_id=bid,
            change_locus=hypothesis.change_locus,
            action=hypothesis.action,
            status="active",
            target_file=hypothesis.target_file,
            suggested_weight=hypothesis.suggested_weight,
            hypothesis_text=hypothesis.hypothesis_text,
        )

        return self._apply_decision_and_finalize(
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

    # ------------------------------------------------------------------
    # STALE reconciliation
    # ------------------------------------------------------------------

    def _run_reconcile_step(self, branch: Branch) -> StepResult:
        """Attempt to rebase a STALE branch on the new champion."""
        bid = branch.branch_id
        patch = self._branch_patches.get(bid)
        if patch is None:
            self._branch_ctrl.reconcile_stale(bid, success=False, new_champion=self._champion)
            return StepResult(action="reconcile", branch_id=bid, reason="no patch to reconcile")

        # Create a fresh workspace from new champion
        workspace = self._setup_workspace(branch, force_champion=True)
        if workspace is None:
            self._branch_ctrl.reconcile_stale(bid, success=False, new_champion=self._champion)
            return StepResult(action="reconcile", branch_id=bid, reason="workspace setup failed")

        try:
            self._materializer.apply_patch(workspace, patch)
            self._branch_ctrl.reconcile_stale(bid, success=True, new_champion=self._champion)
            return StepResult(action="reconcile", branch_id=bid, reason="reconcile succeeded")
        except Exception as exc:
            logger.info("Branch %s: reconcile failed: %s", bid, exc)
            self._branch_ctrl.reconcile_stale(bid, success=False, new_champion=self._champion)
            return StepResult(action="reconcile", branch_id=bid, reason=f"reconcile failed: {exc}")

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
        context = self._ctx_manager.build_hypothesis_context(
            branch=branch,
            champion=self._champion,
            problem_spec=self._spec,
            active_hypotheses=self._active_hypotheses,
            blacklist=self._blacklist,
            sibling_branches=siblings,
            step_history=self._step_history,
        )
        try:
            hypothesis = self._creative.generate_hypothesis(context)
        except (LLMRetryExhaustedError, LLMFormatError, LLMTimeoutError) as exc:
            logger.warning("Branch %s: hypothesis LLM error: %s", bid, exc)
            failure = FailureEvent(category="proposal", detail=str(exc))
            self._handle_failure(branch, failure)
            return None, None

        h_record = HypothesisRecord(
            hypothesis_id=str(uuid.uuid4()),
            branch_id=bid,
            change_locus=hypothesis.change_locus,
            action=hypothesis.action,
            status="active",
            target_file=hypothesis.target_file,
            suggested_weight=hypothesis.suggested_weight,
            hypothesis_text=hypothesis.hypothesis_text,
        )
        return hypothesis, h_record

    # ------------------------------------------------------------------
    # Round 2: generate code
    # ------------------------------------------------------------------

    def _round2_generate_code(
        self, branch: Branch, hypothesis: HypothesisProposal
    ) -> Optional[PatchProposal]:
        bid = branch.branch_id
        context = self._ctx_manager.build_code_context(
            branch=branch,
            hypothesis=hypothesis,
            champion=self._champion,
            problem_spec=self._spec,
        )
        try:
            return self._creative.generate_code(context)
        except (LLMRetryExhaustedError, LLMFormatError, LLMTimeoutError) as exc:
            logger.warning("Branch %s: code LLM error: %s", bid, exc)
            failure = FailureEvent(category="proposal", detail=str(exc))
            self._handle_failure(branch, failure)
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
        # Clean up existing workspace if any
        existing = self._branch_workspaces.get(bid)
        if existing:
            try:
                self._materializer.cleanup(existing)
            except Exception:
                pass

        code_base = self._branch_ctrl.get_code_base(bid)
        if code_base == "champion" or force_champion:
            src = self._champion.code_snapshot_path
        else:
            import os as _os
            # get_code_base() may return a SHA-256 hash (not a path); fall back to champion
            src = code_base if _os.path.isdir(code_base) else self._champion.code_snapshot_path

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
            canary_result = self._experiment_protocol.run_canary(workspace, champ_ws)
        else:
            canary_result = CanaryResult(passed=True, reason="no protocol — auto-pass")

        # ---- Experiment ----
        protocol_result: Optional[ProtocolResult] = None
        if self._experiment_protocol is not None:
            expand = branch.state in (
                BranchState.EXPLORE_EXPAND,
                BranchState.VALIDATING_EXPAND,
            )
            try:
                protocol_result = self._experiment_protocol.run_experiment(
                    stage=stage,
                    candidate_ws=workspace,
                    champion_ws=champ_ws,
                    hypothesis_action=hypothesis.action,
                    expand=expand,
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
        return outcome.decision, protocol_result, canary_result

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

        # CONTINUE_EXPLORE (P0 — discard current patch, re-propose next iteration)
        if decision == Decision.CONTINUE_EXPLORE:
            # State remains EXPLORE — next iteration will do full Round 1 → Round 2
            ws = self._branch_workspaces.get(bid)
            if ws:
                try:
                    self._materializer.cleanup(ws)
                except Exception:
                    pass
                del self._branch_workspaces[bid]
            self._branch_hypotheses.pop(bid, None)
            self._branch_patches.pop(bid, None)
            # Remove hypothesis from active (it's being discarded)
            if h_record in self._active_hypotheses:
                self._active_hypotheses.remove(h_record)
            # Do NOT call apply_decision — branch stays EXPLORE
            self._recent_abandoned_count = 0
            return StepResult(
                action=action_label,  # type: ignore[arg-type]
                branch_id=bid,
                decision=decision,
                reason="CONTINUE_EXPLORE: re-propose next step",
            )

        # PROMOTE — update champion, mark all stale
        if decision == Decision.PROMOTE:
            self._on_promote(branch)

        # ABANDON
        if decision == Decision.ABANDON:
            self._recent_abandoned_count += 1
            ws = self._branch_workspaces.pop(bid, None)
            if ws:
                try:
                    self._materializer.cleanup(ws)
                except Exception:
                    pass
            self._branch_hypotheses.pop(bid, None)
            self._branch_patches.pop(bid, None)
            if h_record in self._active_hypotheses:
                self._active_hypotheses.remove(h_record)
        else:
            self._recent_abandoned_count = 0

        try:
            self._branch_ctrl.apply_decision(bid, decision)
        except StateTransitionError as exc:
            logger.error("Branch %s: apply_decision(%s) failed: %s", bid, decision.value, exc)

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
        """Update champion and mark all other active branches stale."""
        bid = branch.branch_id
        ws = self._branch_workspaces.get(bid)
        if ws is None:
            logger.warning("Branch %s promoted but no workspace found", bid)
            return

        new_version = self._champion.version + 1
        # Create a champion snapshot from the promoted workspace
        try:
            snapshot_path = self._materializer.create_champion_snapshot(
                champion=ChampionState(
                    version=new_version,
                    operator_pool=self._champion.operator_pool,
                    solver_config_hash=self._champion.solver_config_hash,
                    code_snapshot_path=ws,
                    code_snapshot_hash=self._materializer.compute_code_hash(ws),
                ),
                target_dir=str(self._materializer._champions_dir),
            )
        except Exception as exc:
            logger.error("Branch %s: champion snapshot failed: %s", bid, exc)
            snapshot_path = ws  # fallback

        code_hash = self._materializer.compute_code_hash(ws)
        new_champion = ChampionState(
            version=new_version,
            operator_pool=self._champion.operator_pool,
            solver_config_hash=self._champion.solver_config_hash,
            code_snapshot_path=snapshot_path,
            code_snapshot_hash=code_hash,
            promoted_at=datetime.now().isoformat(),
        )
        self._champion = new_champion
        stale_ids = self._branch_ctrl.mark_all_stale(new_version)
        logger.info("Promoted branch %s to champion v%d; marked %d branches stale",
                    bid, new_version, len(stale_ids))

    # ------------------------------------------------------------------
    # Failure handling
    # ------------------------------------------------------------------

    def _handle_failure(self, branch: Branch, failure: FailureEvent) -> None:
        """Route failure and update branch retry count."""
        action = self._failure_router.route(failure, branch)
        branch.retry_count += 1
        branch.failure_codes.append(failure.category.upper())
        logger.debug(
            "Branch %s: failure=%s → action=%s (budget=%s)",
            branch.branch_id, failure.category, action.action, action.consumes_budget,
        )
        if action.consumes_budget:
            self._budget.used += 1
        if action.writes_hypothesis_memory:
            # Record in blacklist (basic in-memory tracking)
            hyp = self._branch_hypotheses.get(branch.branch_id)
            if hyp:
                record = HypothesisRecord(
                    hypothesis_id=str(uuid.uuid4()),
                    branch_id=branch.branch_id,
                    change_locus=hyp.change_locus,
                    action=hyp.action,
                    status="rejected",
                    target_file=hyp.target_file,
                    hypothesis_text=hyp.hypothesis_text,
                )
                self._blacklist.append(record)
