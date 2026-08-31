"""Sprint E3 tests — T06, T09, T10, T25, T23, T24."""
# ruff: noqa: F401
from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest

from scion.core.models import (
    CaseAggregateFeedback,
    CheckResult,
    Decision,
    EvalStats,
    ExperimentStage,
    HypothesisProposal,
    PairwiseCaseFeedback,
    ProtocolResult,
    StepRecord,
    VerificationResult,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_hypothesis(text: str = "test hypothesis", locus: str = "vehicle_level") -> HypothesisProposal:
    return HypothesisProposal(
        hypothesis_text=text,
        change_locus=locus,
        action="modify",
        target_file="operators/test.py",
        predicted_direction="improve",
        target_weakness="slow",
        expected_effect="faster",
    )


def _make_step(
    round_num: int = 1,
    branch_id: str = "branch1",
    decision: Decision = Decision.ABANDON,
    failure_stage: Optional[str] = None,
    failure_detail: Optional[str] = None,
    protocol_result: Optional[ProtocolResult] = None,
    hypothesis_text: str = "test hypothesis",
) -> StepRecord:
    return StepRecord(
        round_num=round_num,
        branch_id=branch_id,
        hypothesis=_make_hypothesis(text=hypothesis_text),
        patch=None,
        contract_passed=failure_stage not in ("hypothesis_contract", "patch_contract"),
        verification_passed=failure_stage != "verification",
        protocol_result=protocol_result,
        decision=decision,
        failure_stage=failure_stage,
        failure_detail=failure_detail,
        base_champion_version=1,
        base_source_ref="champion:v1",
        changed_files=(),
    )


def _make_protocol_result(gate_outcome: str = "pass", win_rate: float = 0.7) -> ProtocolResult:
    stats = EvalStats(
        n_cases=6, wins=4, losses=2, ties=0,
        win_rate=win_rate, median_delta=0.01,
        ci_low=0.005, ci_high=0.02,
    )
    return ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=stats,
        gate_outcome=gate_outcome,
        reason_codes=("SCREENING_PASS",),
        exposed_summary="test",
        raw_metrics_ref="/tmp/test.json",
    )


# ---------------------------------------------------------------------------
# T06: Observability fields in campaign summary
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# T09: Richer case feedback wording
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# T10: Champion baseline hints
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# T25: StagnationDetector
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# T23: Campaign Mid-Stage Diagnosis
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# T24: scion postmortem CLI
# ---------------------------------------------------------------------------


__all__ = [
    name
    for name in globals()
    if not (name.startswith("__") and name.endswith("__"))
]
