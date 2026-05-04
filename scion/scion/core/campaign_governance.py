"""Campaign-level termination and stagnation governance."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, MutableSet, Optional

from scion.core.branch import Branch
from scion.core.models import BranchState, StepRecord
from scion.core.plateau_controller import PlateauController
from scion.core.stagnation import StagnationDetector, StagnationSignal
from scion.core.termination import CampaignState, TerminationChecker

logger = logging.getLogger(__name__)


@dataclass
class CampaignGovernanceService:
    """Own early-stop, hard/soft stagnation, and diagnostics policy."""

    branch_controller: Any
    termination_checker: TerminationChecker
    plateau: PlateauController
    stagnation_detector: StagnationDetector
    get_step_history: Callable[[], List[StepRecord]]
    get_failure_streak: Callable[[], Dict[str, int]]
    diagnostics: List[Dict[str, Any]]
    hard_abandon_counted_branches: Callable[[], MutableSet[str]]
    get_saturation_analyzer: Callable[[], Any]
    get_baseline_metrics: Callable[[], Optional[Dict[str, float]]]
    get_stagnation_signals: Callable[[], List[StagnationSignal]]
    set_stagnation_signals: Callable[[List[StagnationSignal]], None]
    get_round_num: Callable[[], int]
    get_rounds_since_last_promote: Callable[[], int]
    get_n_experiments: Callable[[], int]
    get_start_time: Callable[[], Any]
    get_recent_abandoned_count: Callable[[], int]
    set_recent_abandoned_count: Callable[[int], None]
    get_hard_stagnation_escape_used: Callable[[], bool]
    set_hard_stagnation_escape_used: Callable[[bool], None]
    get_soft_abandon_streak: Callable[[], int]
    set_soft_abandon_streak: Callable[[int], None]
    get_operator_categories: Callable[[], List[str]]
    set_last_stop_reason: Callable[[Optional[str]], None]

    def should_stop(self) -> bool:
        active = self.branch_controller.get_active_branches()
        self.set_last_stop_reason(None)

        early_stop_detected = False
        early_stop_reason = ""
        sat_signals = self._saturation_signals()
        es_decision = self.plateau.early_stop.should_early_stop(
            sat_signals,
            self.get_stagnation_signals(),
            total_rounds=self.get_round_num(),
            rounds_since_last_promote=self.get_rounds_since_last_promote(),
        )
        if es_decision.stop:
            if self.has_pending_evaluation(active):
                logger.info(
                    "Early-stop delayed: %s (rule=%s) but validation/frozen queue is non-empty",
                    es_decision.reason,
                    es_decision.rule,
                )
            else:
                early_stop_detected = True
                early_stop_reason = es_decision.reason
                logger.info(
                    "Early-stop triggered: %s (rule=%s)",
                    es_decision.reason,
                    es_decision.rule,
                )

        campaign_state = CampaignState(
            n_experiments=self.get_n_experiments(),
            start_time=self.get_start_time(),
            recent_abandoned_count=self.get_recent_abandoned_count(),
            active_branches=active,
            can_create_new=True,
            early_stop_detected=early_stop_detected,
            early_stop_reason=early_stop_reason,
        )
        if not self.termination_checker.should_stop(campaign_state):
            return False

        stagnation_triggered = self.termination_checker._stagnation_detected(
            campaign_state
        )
        if stagnation_triggered and not self.get_hard_stagnation_escape_used():
            logger.warning(
                "Hard stagnation detected (%d consecutive hard-abandons) - "
                "attempting locus diversification escape (one-time)",
                self.get_recent_abandoned_count(),
            )
            self.set_hard_stagnation_escape_used(True)
            self.set_recent_abandoned_count(0)
            self.hard_abandon_counted_branches().clear()
            self.plateau.set_forced_locus(self.get_diversification_locus())
            return False

        if early_stop_detected:
            self.set_last_stop_reason(early_stop_reason or "early_stop")
        elif self.termination_checker._max_experiments_reached(campaign_state):
            self.set_last_stop_reason("max_experiments_reached")
        elif self.termination_checker._wall_clock_exceeded(campaign_state):
            self.set_last_stop_reason("max_wall_clock_exceeded")
        elif stagnation_triggered:
            self.set_last_stop_reason("hard_stagnation")
        elif self.termination_checker._no_progress_possible(campaign_state):
            self.set_last_stop_reason("no_progress_possible")
        else:
            self.set_last_stop_reason("termination condition met")
        return True

    def run_stagnation_check(self) -> None:
        """Check for stagnation signals after each round and log critical ones."""
        signals = self.stagnation_detector.check(
            self.get_step_history(),
            failure_streak=self.get_failure_streak(),
        )
        if not signals:
            return

        self.set_stagnation_signals(signals)
        for signal in signals:
            if signal.severity == "critical":
                logger.warning(
                    "STAGNATION [%s] %s - suggested: %s",
                    signal.kind,
                    signal.detail,
                    signal.suggested_action,
                )
            else:
                logger.info(
                    "Stagnation signal [%s] %s - suggested: %s",
                    signal.kind,
                    signal.detail,
                    signal.suggested_action,
                )

        diagnosis = self.stagnation_detector.diagnose(
            self.get_round_num(),
            self.get_step_history(),
            failure_streak=self.get_failure_streak(),
        )
        if diagnosis is None:
            return

        diag_dict = {
            "round_num": diagnosis.round_num,
            "recommendation": diagnosis.recommendation,
            "family_distribution": diagnosis.family_distribution,
            "failure_pattern": diagnosis.failure_pattern,
            "signals": [
                {
                    "kind": signal.kind,
                    "severity": signal.severity,
                    "detail": signal.detail,
                    "suggested_action": signal.suggested_action,
                }
                for signal in diagnosis.signals
            ],
        }
        self.diagnostics.append(diag_dict)
        logger.warning(
            "Campaign diagnosis at round %d: %s",
            diagnosis.round_num,
            diagnosis.recommendation,
        )

    def check_soft_stagnation(self) -> None:
        """Force locus diversification after repeated no-signal abandons."""
        limit = self.termination_checker.config.soft_stagnation_limit
        if self.get_soft_abandon_streak() < limit:
            return

        logger.info(
            "Soft stagnation detected: %d consecutive T4 soft-abandons; forcing locus diversification",
            self.get_soft_abandon_streak(),
        )

        step_history = self.get_step_history()
        recent = step_history[-limit:] if len(step_history) >= limit else step_history
        dominant_locus = self._dominant_locus(recent)
        all_loci = set(self.get_operator_categories())
        if not all_loci:
            logger.info("Soft stagnation: no operator categories available for forced locus")
            self.set_soft_abandon_streak(0)
            return

        unexplored = all_loci - {dominant_locus}
        forced_locus = next(iter(sorted(unexplored)), None)
        self.plateau.set_forced_locus(forced_locus)
        self.set_soft_abandon_streak(0)

        logger.info(
            "Soft stagnation: dominant_locus=%s -> forcing next branch locus=%s",
            dominant_locus,
            forced_locus,
        )

    def consume_forced_locus(self) -> Optional[str]:
        """Consume and return forced locus, if any."""
        forced = self.plateau.consume_forced_locus()
        if forced is not None:
            logger.info("Applying forced locus diversification: %s", forced)
        return forced

    def get_diversification_locus(self) -> Optional[str]:
        """Return a non-dominant operator locus when possible."""
        self.stagnation_detector.diagnose(
            self.get_round_num(),
            self.get_step_history(),
            failure_streak=self.get_failure_streak(),
        )
        step_history = self.get_step_history()
        recent = step_history[-5:] if len(step_history) >= 5 else step_history
        dominant = self._dominant_locus(recent)
        all_loci = set(self.get_operator_categories())
        if not all_loci:
            return None
        unexplored = all_loci - {dominant}
        return next(iter(sorted(unexplored)), None)

    @staticmethod
    def has_pending_evaluation(branches: List[Branch]) -> bool:
        """Return True when a candidate has earned validation/frozen budget."""
        pending_states = {
            BranchState.READY_VALIDATE,
            BranchState.VALIDATING,
            BranchState.VALIDATING_EXPAND,
            BranchState.READY_FROZEN,
            BranchState.FROZEN_TESTING,
            BranchState.STALE,
            BranchState.STALE_WEIGHT_UPDATE,
        }
        return any(branch.state in pending_states for branch in branches)

    def _saturation_signals(self) -> list[Any]:
        analyzer = self.get_saturation_analyzer()
        baseline_metrics = self.get_baseline_metrics()
        if analyzer is None or not baseline_metrics:
            return []

        from scion.proposal.saturation import extract_candidate_metrics_from_step

        current_metrics = baseline_metrics
        for step in reversed(self.get_step_history()):
            if step.decision is not None and step.decision.value == "promote":
                metrics = extract_candidate_metrics_from_step(step)
                if metrics:
                    current_metrics = metrics
                    break
        if not current_metrics:
            return []
        return analyzer.analyze(current_metrics)

    @staticmethod
    def _dominant_locus(steps: List[StepRecord]) -> str:
        locus_counts: Dict[str, int] = {}
        for step in steps:
            locus = getattr(step.hypothesis, "change_locus", None) or ""
            if locus:
                locus_counts[locus] = locus_counts.get(locus, 0) + 1
        return max(locus_counts, key=locus_counts.get) if locus_counts else ""
