"""StagnationDetector — multi-dimensional campaign stagnation detection (T25/T23)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from scion.core.models import Decision, StepRecord

# Threshold for infra_loop detection (same failure_code streak)
_INFRA_LOOP_THRESHOLD = 5


@dataclass
class StagnationSignal:
    kind: str   # "oscillation" | "plateau" | "collapse" | "timeout_cascade"
    severity: str  # "warning" | "critical"
    detail: str
    suggested_action: str


@dataclass
class CampaignDiagnosis:
    """Structured diagnosis produced when stagnation is detected (T23)."""
    round_num: int
    signals: List[StagnationSignal]
    family_distribution: Dict[str, int]
    failure_pattern: Dict[str, int]  # failure_stage → count
    recommendation: str  # "diversify_locus" | "switch_action" | "check_environment" | "increase_screening_n"


class StagnationDetector:
    """Detect multi-dimensional stagnation patterns in the campaign history."""

    def __init__(self, window_size: int = 5) -> None:
        self._window = window_size

    def check(
        self,
        step_history: List[StepRecord],
        failure_streak: Optional[Dict[str, int]] = None,
    ) -> List[StagnationSignal]:
        """Check for stagnation signals in the step history.

        Args:
            step_history: Full campaign step history.
            failure_streak: Optional dict of failure_code → current consecutive streak,
                            provided by CampaignManager for infra_loop detection.

        Returns a (possibly empty) list of signals. Never raises.
        """
        if not step_history:
            return []
        signals: List[StagnationSignal] = []
        recent = step_history[-self._window :]

        # 1. Collapse: 3+ consecutive hard failures (contract/verification/code)
        collapse = self._check_collapse(step_history)
        if collapse:
            signals.append(collapse)

        # 2. Timeout cascade: 2+ consecutive timeout failures
        timeout = self._check_timeout_cascade(step_history)
        if timeout:
            signals.append(timeout)

        # 3. Oscillation: alternating win/loss among recent steps with no net gain
        oscillation = self._check_oscillation(recent)
        if oscillation:
            signals.append(oscillation)

        # 4. Plateau: all recent hypotheses same mechanism family, similar win_rate
        plateau = self._check_plateau(recent)
        if plateau:
            signals.append(plateau)

        # 5. Infra loop: same failure_code streak >= threshold
        if failure_streak:
            infra_loop = self._check_infra_loop(failure_streak)
            if infra_loop:
                signals.append(infra_loop)

        return signals

    # ------------------------------------------------------------------
    # Individual detectors
    # ------------------------------------------------------------------

    def _check_collapse(self, steps: List[StepRecord]) -> Optional[StagnationSignal]:
        """3+ consecutive hard failures → collapse."""
        streak = 0
        for step in reversed(steps):
            if step.failure_stage in (
                "verification", "contract", "patch_contract",
                "hypothesis_contract", "workspace",
            ):
                streak += 1
            else:
                break
        if streak >= 3:
            return StagnationSignal(
                kind="collapse",
                severity="critical" if streak >= 5 else "warning",
                detail=f"{streak} consecutive hard failures (contract/verification)",
                suggested_action="check_environment",
            )
        return None

    def _check_timeout_cascade(self, steps: List[StepRecord]) -> Optional[StagnationSignal]:
        """2+ consecutive timeout failures → timeout_cascade."""
        streak = 0
        for step in reversed(steps):
            detail = (step.failure_detail or "").lower()
            if step.failure_stage and "timeout" in detail:
                streak += 1
            else:
                break
        if streak >= 2:
            return StagnationSignal(
                kind="timeout_cascade",
                severity="critical",
                detail=f"{streak} consecutive timeout failures",
                suggested_action="check_environment",
            )
        return None

    def _check_oscillation(self, recent: List[StepRecord]) -> Optional[StagnationSignal]:
        """Alternating win/loss outcomes with no net improvement."""
        if len(recent) < 4:
            return None
        # Classify each step as "win" or "loss" based on protocol_result or failure
        outcomes = []
        for step in recent:
            if step.failure_stage:
                outcomes.append("fail")
            elif step.protocol_result:
                if step.protocol_result.gate_outcome in ("pass", "expand"):
                    outcomes.append("win")
                else:
                    outcomes.append("loss")
            elif step.decision == Decision.PROMOTE:
                outcomes.append("win")
            else:
                outcomes.append("neutral")

        # Check for alternating pattern (win-loss-win-loss or loss-win-loss-win)
        alternating = 0
        for i in range(1, len(outcomes)):
            a, b = outcomes[i - 1], outcomes[i]
            if (a == "win" and b == "loss") or (a == "loss" and b == "win"):
                alternating += 1

        # If ≥ 60% of consecutive pairs alternate, it's oscillation
        if alternating >= max(2, int(0.6 * (len(outcomes) - 1))):
            wins = sum(1 for o in outcomes if o == "win")
            losses = sum(1 for o in outcomes if o == "loss")
            return StagnationSignal(
                kind="oscillation",
                severity="warning",
                detail=f"Alternating win/loss pattern: {wins}W/{losses}L in last {len(recent)} steps",
                suggested_action="diversify_locus",
            )
        return None

    def _check_plateau(self, recent: List[StepRecord]) -> Optional[StagnationSignal]:
        """All recent hypotheses from same mechanism family with similar win rates."""
        if len(recent) < 3:
            return None

        # Collect mechanism labels from hypothesis texts
        from scion.proposal.context_manager import _extract_mechanism_label
        labels = [
            _extract_mechanism_label(s.hypothesis.hypothesis_text or "")
            for s in recent
        ]
        if len(set(labels)) == 1:
            # Same mechanism for all recent steps — check if progress is flat
            win_rates = []
            for step in recent:
                if step.protocol_result:
                    win_rates.append(step.protocol_result.stats.win_rate)
            if len(win_rates) >= 2:
                spread = max(win_rates) - min(win_rates)
                if spread < 0.15:  # All within 15% of each other
                    return StagnationSignal(
                        kind="plateau",
                        severity="warning",
                        detail=(
                            f"All {len(recent)} recent steps use '{labels[0]}' mechanism "
                            f"with flat win_rate (spread={spread:.2f})"
                        ),
                        suggested_action="switch_action",
                    )
        return None

    def _check_infra_loop(self, failure_streak: Dict[str, int]) -> Optional[StagnationSignal]:
        """Same failure_code streak >= threshold → infra_loop (should_stop=True)."""
        for code, streak in failure_streak.items():
            if streak >= _INFRA_LOOP_THRESHOLD:
                return StagnationSignal(
                    kind="infra_loop",
                    severity="critical",
                    detail=f"failure_code='{code}' repeated {streak} consecutive times",
                    suggested_action="check_environment",
                )
        return None

    # ------------------------------------------------------------------
    # Diagnosis (T23)
    # ------------------------------------------------------------------

    def diagnose(
        self, round_num: int, step_history: List[StepRecord],
        failure_streak: Optional[Dict[str, int]] = None,
    ) -> Optional[CampaignDiagnosis]:
        """Produce a structured diagnosis when critical signals are detected.

        Returns None if no critical signals exist.
        """
        signals = self.check(step_history, failure_streak=failure_streak)
        critical = [s for s in signals if s.severity == "critical"]
        if not critical:
            return None

        from scion.proposal.context_manager import _extract_mechanism_label

        # Family distribution
        family_distribution: Dict[str, int] = {}
        for step in step_history:
            label = _extract_mechanism_label(step.hypothesis.hypothesis_text or "")
            family_distribution[label] = family_distribution.get(label, 0) + 1

        # Failure pattern (last 10 steps)
        failure_pattern: Dict[str, int] = {}
        for step in step_history[-10:]:
            if step.failure_stage:
                failure_pattern[step.failure_stage] = failure_pattern.get(step.failure_stage, 0) + 1

        # Determine recommendation from signal kinds
        kinds = {s.kind for s in signals}
        if "infra_loop" in kinds or "timeout_cascade" in kinds or "collapse" in kinds:
            recommendation = "check_environment"
        elif "oscillation" in kinds:
            recommendation = "diversify_locus"
        elif "plateau" in kinds:
            recommendation = "switch_action"
        else:
            recommendation = "increase_screening_n"

        return CampaignDiagnosis(
            round_num=round_num,
            signals=signals,
            family_distribution=family_distribution,
            failure_pattern=failure_pattern,
            recommendation=recommendation,
        )
