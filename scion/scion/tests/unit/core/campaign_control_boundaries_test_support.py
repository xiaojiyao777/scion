"""Sprint G1: Control boundary hardening + hypothesis lifecycle tests.

Verifies:
- fix patch re-passes Contract Gate before apply
- pending hypothesis re-passes hypothesis Contract Gate
- current_code_hash is written only after candidate acceptance
- eval-only steps reuse the branch's ordinary hypothesis value
- eval-only steps write StepRecord to step_history
- stale reconcile runs Contract → Verification → re-screening
- StepRecord.decision is None for early failures
"""
# ruff: noqa: F401
from __future__ import annotations

import os
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import MagicMock, patch as mock_patch

import pytest

from scion.config.problem import ProblemSpec, ProtocolConfig, SplitManifest, SeedLedgerConfig, SearchSpace
from scion.core.campaign import CampaignManager
from scion.core.models import (
    Branch, BranchState, CanaryResult, ChampionState, CheckResult,
    ContractResult, Decision, EvalStats, ExperimentStage, HypothesisProposal,
    PatchProposal, ProtocolResult, StepRecord, VerificationResult,
)
from scion.problem.preflight import RuntimeDependencyPreflightError
from scion.problem.spec import RuntimeDependencySpec
from scion.problem.spec import ObjectiveMetricSpec
from scion.proposal.mock_client import MockLLMClient
from scion.verification.gate import VerificationGate


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
    "edit_intent": "exact_replace",
    "old_string": "        return solution\n",
    "new_string": "        candidate = solution\n        return candidate\n",
    "replace_all": False,
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
        code_snapshot_path=str(code_dir),
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


class _AlwaysPassVerification(VerificationGate):
    def __init__(self) -> None:
        super().__init__()

    def run(self, *args, **kwargs) -> VerificationResult:
        return VerificationResult(
            passed=True,
            checks=(CheckResult(name="SYNTAX", passed=True, severity="light", detail="ok", elapsed_ms=0),),
        )


class _AlwaysFailVerificationLight(VerificationGate):
    def __init__(self) -> None:
        super().__init__()

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
        self.runner = object()
        self.config = ProtocolConfig()
        self._metric_specs = (
            ObjectiveMetricSpec(name="cost", direction="minimize", priority=1),
        )
        self._problem_spec = None

    def set_problem_adapter(self, adapter: Any) -> None:
        self._problem_spec = adapter.spec
        objectives = getattr(adapter.spec, "objectives", None)
        if objectives:
            self._metric_specs = tuple(objectives)

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
        proposal_subject: dict[str, Any] | None = None,
    ) -> ProtocolResult:
        del proposal_subject
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
    protocol = experiment_protocol or _MockProtocol()
    protocol._problem_spec = spec

    return CampaignManager(
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
            canary=["c7"],
        ),
        seed_ledger=SeedLedgerConfig(
            screening=[1, 2],
            validation=[3, 4],
            frozen=[5, 6],
            canary=[7],
        ),
        llm_client=llm_client or MockLLMClient(
            hypothesis_response=_VALID_HYPOTHESIS,
            patch_response=_VALID_PATCH,
        ),
        champion=champion,
        campaign_dir=campaign_dir,
        verification_gate=verification_gate or _AlwaysPassVerification(),
        experiment_protocol=protocol,
        adapter=SimpleNamespace(spec=spec),
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
