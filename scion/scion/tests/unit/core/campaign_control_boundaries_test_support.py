"""Sprint G1: Control boundary hardening + hypothesis lifecycle tests.

Verifies:
- fix patch re-passes Contract Gate before apply
- pending hypothesis re-passes hypothesis Contract Gate
- last_clean_code_hash only updated after verification pass
- eval-only steps reuse original hypothesis_id
- eval-only steps write StepRecord to step_history
- stale reconcile runs Contract → Verification → re-screening
- StepRecord.decision is None for early failures
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import MagicMock, patch as mock_patch

import pytest

from scion.config.problem import ProblemSpec, ProtocolConfig, SplitManifest, SeedLedgerConfig, SearchSpace
from scion.core.campaign import CampaignManager
from scion.core.models import (
    Branch, BranchState, CanaryResult, ChampionState, CheckResult,
    ContractResult, Decision, EvalStats, ExperimentStage, HypothesisProposal,
    HypothesisRecord, PatchProposal, ProtocolResult, StepRecord, VerificationResult,
)
from scion.problem.preflight import RuntimeDependencyPreflightError
from scion.problem.spec import RuntimeDependencySpec
from scion.proposal.mock_client import MockLLMClient


# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------

_VALID_CODE = (
    "class LocalSearch:\n"
    "    def execute(self, solution, rng):\n"
    "        return solution\n\n"
)

_VALID_HYPOTHESIS = {
    "hypothesis_text": "Improve by trying 2-opt.",
    "change_locus": "local_search",
    "action": "modify",
    "target_file": "operators/local_search.py",
    "predicted_direction": "improve",
    "target_weakness": "slow",
    "expected_effect": "better",
    "suggested_weight": 0.3,
}

_VALID_PATCH = {
    "file_path": "operators/local_search.py",
    "action": "modify",
    "code_content": _VALID_CODE,
    "test_hint": None,
}


def _make_spec(root_dir: str) -> ProblemSpec:
    return ProblemSpec(
        name="test_vrp",
        root_dir=root_dir,
        operator_categories=["local_search"],
        search_space=SearchSpace(
            editable=["operators/*.py"],
            frozen=["solver.py"],
            import_whitelist=["numpy", "random", "math"],
        ),
    )


def _make_champion(code_dir: str) -> ChampionState:
    return ChampionState(
        version=1,
        operator_pool={},
        solver_config_hash="abc123",
        code_snapshot_path=str(code_dir),
        code_snapshot_hash="deadbeef",
    )


def _make_protocol_result(
    gate_outcome: str = "pass",
    stage: ExperimentStage = ExperimentStage.SCREENING,
    win_rate: float = 0.7,
) -> ProtocolResult:
    stats = EvalStats(
        n_cases=6, wins=4, losses=2, ties=0,
        win_rate=win_rate, median_delta=0.01,
        ci_low=0.005, ci_high=0.02,
    )
    return ProtocolResult(
        stage=stage,
        stats=stats,
        gate_outcome=gate_outcome,
        reason_codes=(
            {
                ExperimentStage.SCREENING: "SCREENING_PASS",
                ExperimentStage.VALIDATION: "VALIDATION_PASS",
                ExperimentStage.FROZEN: "FROZEN_PASS",
            }[stage],
        ),
        exposed_summary=f"stage={stage.value}",
        raw_metrics_ref="/tmp/test.json",
    )


class _AlwaysPassVerification:
    def run(self, *args, **kwargs) -> VerificationResult:
        return VerificationResult(
            passed=True,
            checks=(CheckResult(name="SYNTAX", passed=True, severity="light", detail="ok", elapsed_ms=0),),
        )


class _AlwaysFailVerificationLight:
    def run(self, *args, **kwargs) -> VerificationResult:
        return VerificationResult(
            passed=False,
            checks=(CheckResult(name="SYNTAX", passed=False, severity="light", detail="fail", elapsed_ms=0),),
            failure_severity="light",
            first_failure="SYNTAX",
        )


class _MockProtocol:
    """Configurable mock ExperimentProtocol."""

    def __init__(
        self,
        results: Optional[List[ProtocolResult]] = None,
        canary_pass: bool = True,
    ) -> None:
        self._results = list(results or [])
        self._canary_pass = canary_pass
        self.canary_calls: List[Tuple] = []
        self.experiment_calls: List[Tuple] = []

    def run_canary(self, candidate_ws: str, champion_ws: str) -> CanaryResult:
        self.canary_calls.append((candidate_ws, champion_ws))
        return CanaryResult(passed=self._canary_pass)

    def run_experiment(
        self,
        stage: ExperimentStage,
        candidate_ws: str,
        champion_ws: str,
        hypothesis_action: str,
        expand: bool = False,
        expand_round: int = 1,
    ) -> ProtocolResult:
        self.experiment_calls.append((stage, candidate_ws, champion_ws, hypothesis_action))
        if self._results:
            return self._results.pop(0)
        return _make_protocol_result()


def _campaign(
    tmp_path: Path,
    llm_client: Any = None,
    experiment_protocol: Any = None,
    verification_gate: Any = None,
    protocol_config: ProtocolConfig | None = None,
) -> CampaignManager:
    code_dir = tmp_path / "champion_code"
    (code_dir / "operators").mkdir(parents=True)
    (code_dir / "operators" / "local_search.py").write_text(_VALID_CODE)

    campaign_dir = str(tmp_path / "campaign")
    spec = _make_spec(str(code_dir))
    champion = _make_champion(code_dir)

    return CampaignManager(
        problem_spec=spec,
        protocol_config=protocol_config or ProtocolConfig(
            screening_n=6,
            screening_win_rate_threshold=0.66,
            validation_n=12,
            validation_win_rate_threshold=0.66,
            frozen_n=24,
            min_practical_delta=0.001,
        ),
        split_manifest=SplitManifest(
            screening=["c1", "c2"],
            validation=["c3", "c4"],
            frozen=["c5", "c6"],
        ),
        seed_ledger=SeedLedgerConfig(
            screening=[1, 2],
            validation=[3, 4],
            frozen=[5, 6],
        ),
        llm_client=llm_client or MockLLMClient(
            hypothesis_response=_VALID_HYPOTHESIS,
            patch_response=_VALID_PATCH,
        ),
        champion=champion,
        campaign_dir=campaign_dir,
        verification_gate=verification_gate or _AlwaysPassVerification(),
        experiment_protocol=experiment_protocol,
    )


# ---------------------------------------------------------------------------
# Gate bypass — fix patch (T1)
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# Gate bypass — pending hypothesis (T2)
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# Clean-base (T3)
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# Hypothesis lifecycle (T4)
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# Eval-only step writes StepRecord (T5)
# ---------------------------------------------------------------------------







# ---------------------------------------------------------------------------
# Stale reconcile (T6)
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# Decision=None for early failures (T7)
# ---------------------------------------------------------------------------


__all__ = [
    name
    for name in globals()
    if not (name.startswith("__") and name.endswith("__"))
]
