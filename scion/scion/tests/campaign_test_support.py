"""Tests for T20: CampaignManager — full pipeline with MockLLMClient."""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
import pytest

from scion.config.problem import ProblemSpec, ProtocolConfig, SplitManifest, SeedLedgerConfig, SearchSpace
from scion.core.campaign import CampaignManager, VerificationGate, StepResult
from scion.core.models import (
    Branch, BranchState, CanaryResult, ChampionState, Decision,
    EvalStats, ExperimentStage, ProtocolResult, VerificationResult, CheckResult,
)
from scion.core.termination import TerminationConfig
from scion.evidence.final_evidence_refs import (
    FINAL_EVIDENCE_REASON_NORMAL_COMPLETION,
    FINAL_EVIDENCE_STATUS_NON_FORMAL_CLOSED,
)
from scion.proposal.mock_client import MockLLMClient


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_VALID_CODE = (
    "class LocalSearch:\n"
    "    def execute(self, solution, rng):\n"
    "        return solution\n"
)

_VALID_HYPOTHESIS = {
    "hypothesis_text": "Improve local search by trying 2-opt.",
    "change_locus": "local_search",
    "action": "modify",
    "target_file": "operators/local_search.py",
    "predicted_direction": "improve",
    "target_weakness": "slow convergence",
    "expected_effect": "better solutions",
    "suggested_weight": 0.3,
}

_VALID_PATCH = {
    "file_path": "operators/local_search.py",
    "action": "modify",
    "code_content": _VALID_CODE,
    "test_hint": None,
}


def _make_problem_spec(root_dir: str) -> ProblemSpec:
    return ProblemSpec(
        name="test_vrp",
        root_dir=root_dir,
        operator_categories=["local_search"],
        search_space=SearchSpace(
            editable=["operators/*.py"],
            frozen=["solver.py", "oracle.py"],
            import_whitelist=["numpy", "random", "math"],
        ),
    )


def _make_champion(code_dir: str) -> ChampionState:
    return ChampionState(
        version=1,
        operator_pool={},
        solver_config_hash="abc123",
        code_snapshot_path=code_dir,
        code_snapshot_hash="deadbeef",
    )


def _make_protocol_config() -> ProtocolConfig:
    return ProtocolConfig(
        screening_n=6,
        screening_win_rate_threshold=0.66,
        validation_n=12,
        validation_win_rate_threshold=0.66,
        frozen_n=24,
        min_practical_delta=0.001,
    )


def _make_split_manifest() -> SplitManifest:
    return SplitManifest(
        screening=["case1", "case2"],
        validation=["case3", "case4"],
        frozen=["case5", "case6"],
    )


def _make_seed_ledger() -> SeedLedgerConfig:
    return SeedLedgerConfig(
        screening=[1, 2],
        validation=[3, 4],
        frozen=[5, 6],
    )


def _make_protocol_result(
    stage: ExperimentStage,
    gate_outcome: str = "pass",
    win_rate: float = 0.7,
    median_delta: float = 0.01,
    ci_low: float = 0.005,
    ci_high: float = 0.02,
) -> ProtocolResult:
    stats = EvalStats(
        n_cases=10, wins=7, losses=2, ties=1,
        win_rate=win_rate, median_delta=median_delta,
        ci_low=ci_low, ci_high=ci_high,
    )
    return ProtocolResult(
        stage=stage,
        stats=stats,
        gate_outcome=gate_outcome,
        reason_codes=("TEST",),
        exposed_summary=f"stage={stage.value} outcome={gate_outcome}",
        raw_metrics_ref="/tmp/test.json",
    )


class MockExperimentProtocol:
    """Configurable mock ExperimentProtocol for campaign tests."""

    def __init__(self, results: List[ProtocolResult], canary_pass: bool = True) -> None:
        self._results = list(results)
        self._canary_pass = canary_pass
        self.canary_call_count = 0
        self.experiment_call_count = 0

    def run_canary(self, candidate_ws: str, champion_ws: str) -> CanaryResult:
        self.canary_call_count += 1
        return CanaryResult(passed=self._canary_pass, reason=None)

    def run_experiment(
        self,
        stage: ExperimentStage,
        candidate_ws: str,
        champion_ws: str,
        hypothesis_action: str,
        expand: bool = False,
        expand_round: int = 1,
    ) -> ProtocolResult:
        self.experiment_call_count += 1
        if self._results:
            return self._results.pop(0)
        # Default: return a screening pass
        return _make_protocol_result(stage)


class AlwaysPassVerificationGate:
    """Verification gate stub that always passes."""

    def run(self, workspace: str, champion_workspace: str, patch: Any) -> VerificationResult:
        check = CheckResult(
            name="SYNTAX", passed=True, severity="light", detail="stub pass", elapsed_ms=0
        )
        return VerificationResult(passed=True, checks=(check,))


class AlwaysFailVerificationGate:
    """Verification gate stub that always fails (light)."""

    def run(self, workspace: str, champion_workspace: str, patch: Any) -> VerificationResult:
        check = CheckResult(
            name="SYNTAX", passed=False, severity="light",
            detail="stub fail", elapsed_ms=0,
        )
        return VerificationResult(
            passed=False, checks=(check,),
            failure_severity="light", first_failure="SYNTAX",
        )


def _campaign(
    tmp_path: Path,
    llm_client: Any = None,
    experiment_protocol: Any = None,
    verification_gate: Any = None,
    termination_config: Optional[TerminationConfig] = None,
) -> CampaignManager:
    # Create minimal champion code directory
    code_dir = tmp_path / "champion_code"
    (code_dir / "operators").mkdir(parents=True)
    (code_dir / "operators" / "local_search.py").write_text(_VALID_CODE)

    campaign_dir = str(tmp_path / "campaign")
    spec = _make_problem_spec(str(code_dir))
    champion = _make_champion(str(code_dir))

    return CampaignManager(
        problem_spec=spec,
        protocol_config=_make_protocol_config(),
        split_manifest=_make_split_manifest(),
        seed_ledger=_make_seed_ledger(),
        llm_client=llm_client or MockLLMClient(
            hypothesis_response=_VALID_HYPOTHESIS,
            patch_response=_VALID_PATCH,
        ),
        champion=champion,
        campaign_dir=campaign_dir,
        verification_gate=verification_gate or AlwaysPassVerificationGate(),
        experiment_protocol=experiment_protocol,
        termination_config=termination_config or TerminationConfig(
            max_experiments=100,
            stagnation_limit=50,
        ),
    )


# ---------------------------------------------------------------------------
# Basic campaign structure tests
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# CONTINUE_EXPLORE path (no protocol — auto-continue)
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# Full successful path: EXPLORE → QUEUE_VALIDATE → VALIDATING → QUEUE_FROZEN → PROMOTE
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# Contract failure routing
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# Screening fail → ABANDON (win_rate very low)
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# Canary failure
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# Stale branch reconciliation
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# Verification gate failure
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# run() loop integration
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# T03+T04: archive_workspace returns path + campaign_summary.json
# ---------------------------------------------------------------------------





# ---------------------------------------------------------------------------
# T16 — _on_promote weight optimization hook
# ---------------------------------------------------------------------------

def _promote_protocol():
    """Return a protocol that produces screening→validation→frozen pass."""
    return MockExperimentProtocol(results=[
        _make_protocol_result(ExperimentStage.SCREENING, gate_outcome="pass"),
        _make_protocol_result(ExperimentStage.VALIDATION, gate_outcome="pass",
                              win_rate=0.7, ci_low=0.005, ci_high=0.02),
        _make_protocol_result(ExperimentStage.FROZEN, gate_outcome="pass",
                              win_rate=0.7, ci_low=0.005, ci_high=0.02),
    ])


def _run_to_promote(cm):
    """Drive campaign manager through three steps to reach PROMOTE."""
    cm.run_one_step()
    cm.run_one_step()
    result = cm.run_one_step()
    assert result.decision == Decision.PROMOTE
    return result


def _setup_for_on_promote(tmp_path, with_registry=False):
    """Create a campaign + workspace ready to call _on_promote directly.

    Returns (cm, branch, ws_path).
    """
    import yaml as _yaml

    ws = tmp_path / "branch_ws"
    ws.mkdir(parents=True)
    (ws / "operators").mkdir(exist_ok=True)
    (ws / "operators" / "local_search.py").write_text(_VALID_CODE)

    if with_registry:
        ops = [
            {"name": "swap", "file_path": "operators/swap.py",
             "category": "order_level", "weight": 0.6, "class_name": "Swap"},
            {"name": "move", "file_path": "operators/move.py",
             "category": "order_level", "weight": 0.4, "class_name": "Move"},
        ]
        (ws / "registry.yaml").write_text(_yaml.dump({"operators": ops}))

    cm = _campaign(tmp_path)
    branch = cm._branch_ctrl.create_branch(cm._champion)
    branch.state = BranchState.FROZEN_TESTING
    cm._branch_workspaces[branch.branch_id] = str(ws)
    return cm, branch, str(ws)




# ---------------------------------------------------------------------------
# T20: Code-failure degraded recovery (pending hypothesis retry)
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# T1: No fake HypothesisRecord fallback in eval step (Sprint G-patch)
# ---------------------------------------------------------------------------


__all__ = [
    name
    for name in globals()
    if not (name.startswith("__") and name.endswith("__"))
]
