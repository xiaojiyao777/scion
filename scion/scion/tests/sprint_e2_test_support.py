"""Tests for Sprint E2: T05/T07/T08/T11/T26.

T05: Frozen holdout expansion (split_manifest.yaml).
T07: Hypothesis family tracking — family assignment, coverage report.
T08: Strategy-shift guidance — repeated family failure detection.
T11: Screening set rebalance (split_manifest.yaml — already verified).
T26: Context manager memory classification — What Worked / What Failed sections.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import List, Optional

import pytest

from scion.config.problem import ProblemSpec, SearchSpace
from scion.core.models import (
    Branch,
    BranchState,
    ChampionState,
    Decision,
    EvalStats,
    ExperimentStage,
    HypothesisFamily,
    HypothesisProposal,
    HypothesisRecord,
    ProtocolResult,
    StepRecord,
)
from scion.proposal.context_manager import (
    ContextManager,
    _build_runtime_feedback,
    _build_runtime_failure_guidance,
    _build_strategy_guidance,
    _build_what_worked_section,
    _extract_families_from_steps,
    assign_family_id,
    build_exploration_coverage,
)
from scion.proposal.engine import _split_hypothesis_context
from scion.tests.taxonomy_helpers import cvrp_family_taxonomy, warehouse_family_taxonomy

WAREHOUSE_MECHANISM_TAXONOMY = warehouse_family_taxonomy()
CVRP_FAMILY_TAXONOMY = cvrp_family_taxonomy()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_hypothesis(
    text: str = "some hypothesis",
    action: str = "create_new",
    locus: str = "vehicle_level",
) -> HypothesisProposal:
    return HypothesisProposal(
        hypothesis_text=text,
        change_locus=locus,
        action=action,
        target_file=None,
        predicted_direction="improve",
        target_weakness="slow",
        expected_effect="faster",
    )


def _make_step(
    branch_id: str = "b1",
    round_num: int = 1,
    hypothesis_text: str = "test hypothesis",
    action: str = "create_new",
    locus: str = "vehicle_level",
    decision: Decision = Decision.CONTINUE_EXPLORE,
    failure_stage: Optional[str] = None,
    win_rate: float = 0.0,
    runtime_ratio_median=None,
    runtime_delta_median_ms=None,
    runtime_regression_rate=None,
    runtime_pairs: int = 0,
    protocol_stage: ExperimentStage = ExperimentStage.SCREENING,
) -> StepRecord:
    protocol_result = None
    if failure_stage is None:
        stats = EvalStats(
            n_cases=6,
            wins=int(win_rate * 6),
            losses=6 - int(win_rate * 6),
            ties=0,
            win_rate=win_rate,
            median_delta=0.01 if win_rate > 0 else 0.0,
            ci_low=0.0,
            ci_high=0.02,
            runtime_ratio_median=runtime_ratio_median,
            runtime_delta_median_ms=runtime_delta_median_ms,
            runtime_regression_rate=runtime_regression_rate,
            runtime_pairs=runtime_pairs,
        )
        protocol_result = ProtocolResult(
            stage=protocol_stage,
            stats=stats,
            gate_outcome="pass" if win_rate > 0.6 else "continue",
            reason_codes=("TEST",),
            exposed_summary="test",
            raw_metrics_ref="/tmp/test.json",
        )
    return StepRecord(
        round_num=round_num,
        branch_id=branch_id,
        hypothesis=_make_hypothesis(hypothesis_text, action, locus),
        patch=None,
        contract_passed=True,
        verification_passed=(failure_stage is None),
        protocol_result=protocol_result,
        decision=decision,
        failure_stage=failure_stage,
        failure_detail=f"failed at {failure_stage}" if failure_stage else None,
    )


def _make_family(
    mechanism_label: str,
    action_pattern: str = "create_new",
    locus_pattern: str = "vehicle_level",
    statuses: Optional[List[str]] = None,
) -> HypothesisFamily:
    statuses = statuses or []
    return HypothesisFamily(
        family_id=f"{mechanism_label}/{action_pattern}/{locus_pattern}",
        mechanism_label=mechanism_label,
        action_pattern=action_pattern,
        locus_pattern=locus_pattern,
        evidence_count=len(statuses),
        statuses=statuses,
    )


# ---------------------------------------------------------------------------
# T05: Frozen holdout expansion
# ---------------------------------------------------------------------------

MANIFEST_PATH = Path(__file__).parent.parent.parent / "problems/warehouse_delivery/split_manifest.yaml"








# ---------------------------------------------------------------------------
# T11: Screening set rebalance
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# T07: Family assignment by keywords
# ---------------------------------------------------------------------------



















# ---------------------------------------------------------------------------
# T07: Coverage report format
# ---------------------------------------------------------------------------









# ---------------------------------------------------------------------------
# T07: Family tracking across rounds
# ---------------------------------------------------------------------------





# ---------------------------------------------------------------------------
# T08: Strategy-shift guidance
# ---------------------------------------------------------------------------











# ---------------------------------------------------------------------------
# T26: History includes successes and failures
# ---------------------------------------------------------------------------


__all__ = [
    name
    for name in globals()
    if not (name.startswith("__") and name.endswith("__"))
]
