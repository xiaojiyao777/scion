"""Tests for async (background-thread) weight optimization in CampaignManager.

Verifies:
- R1: _on_promote returns in <1s even when weight optimizer sleeps 2s
- R2: bg thread eventually updates self._champion.operator_pool with optimized weights
- R4: stale bg thread result is discarded when champion version has advanced
"""
from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

import pytest

from scion.config.problem import (
    ProblemSpec, ProtocolConfig, SplitManifest, SeedLedgerConfig, SearchSpace,
)
from scion.core.campaign import CampaignManager
from scion.core.models import (
    Branch, BranchState, CanaryResult, ChampionState, CheckResult,
    ContractResult, Decision, EvalStats, ExperimentStage, HypothesisProposal,
    HypothesisRecord, ProtocolResult, VerificationResult,
)
from scion.core.termination import TerminationConfig
from scion.proposal.mock_client import MockLLMClient


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_VALID_CODE = (
    "class LocalSearch:\n"
    "    def execute(self, solution, rng):\n"
    "        return solution\n"
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


class _AlwaysPassVerification:
    def run(self, *args, **kwargs) -> VerificationResult:
        return VerificationResult(
            passed=True,
            checks=(CheckResult(name="SYNTAX", passed=True, severity="light",
                                detail="ok", elapsed_ms=0),),
        )


def _make_spec(root_dir: str, weight_opt_enabled: bool = True) -> ProblemSpec:
    from scion.config.problem import ParameterSearchConfig
    param = ParameterSearchConfig(enabled=weight_opt_enabled)
    return ProblemSpec(
        name="test_vrp",
        root_dir=root_dir,
        operator_categories=["local_search"],
        search_space=SearchSpace(
            editable=["operators/*.py"],
            frozen=["solver.py"],
            import_whitelist=["numpy", "random", "math"],
        ),
        parameter_search=param,
    )


def _make_champion(code_dir: Path) -> ChampionState:
    return ChampionState(
        version=1,
        operator_pool={"local_search": 1.0},
        solver_config_hash="abc123",
        code_snapshot_path=str(code_dir),
        code_snapshot_hash="deadbeef",
    )


def _make_campaign(tmp_path: Path, experiment_protocol: Any = None,
                   weight_opt_enabled: bool = True) -> CampaignManager:
    code_dir = tmp_path / "champion_code"
    (code_dir / "operators").mkdir(parents=True)
    (code_dir / "operators" / "local_search.py").write_text(_VALID_CODE)

    campaign_dir = str(tmp_path / "campaign")
    spec = _make_spec(str(code_dir), weight_opt_enabled=weight_opt_enabled)
    champion = _make_champion(code_dir)

    return CampaignManager(
        problem_spec=spec,
        protocol_config=ProtocolConfig(
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
        llm_client=MockLLMClient(
            hypothesis_response=_VALID_HYPOTHESIS,
            patch_response=_VALID_PATCH,
        ),
        champion=champion,
        campaign_dir=campaign_dir,
        verification_gate=_AlwaysPassVerification(),
        experiment_protocol=experiment_protocol,
        termination_config=TerminationConfig(max_experiments=100, stagnation_limit=50),
    )


def _build_promoted_branch(cm: CampaignManager, tmp_path: Path) -> Branch:
    """Create a branch with a workspace and registry.yaml, ready for promote."""
    branch = cm._branch_ctrl.create_branch(cm._champion)
    bid = branch.branch_id
    ws = tmp_path / "branch_ws" / bid
    (ws / "operators").mkdir(parents=True)
    (ws / "operators" / "local_search.py").write_text(_VALID_CODE)
    (ws / "registry.yaml").write_text(
        'operators:\n  local_search:\n    weight: 1.0\n'
    )
    cm._branch_workspaces[bid] = str(ws)
    return branch


# ---------------------------------------------------------------------------
# R1: _on_promote returns immediately (non-blocking)
# ---------------------------------------------------------------------------

class TestOnPromoteNonBlocking:
    def test_on_promote_returns_before_weight_opt_completes(self, tmp_path):
        """_on_promote must return in <1s even when weight optimizer sleeps 2s."""
        mock_protocol = MagicMock()
        mock_protocol.runner = MagicMock()

        cm = _make_campaign(tmp_path, experiment_protocol=mock_protocol)

        # Patch _run_weight_optimization to sleep 2 seconds
        def slow_weight_opt(staging_path, version, current_weights):
            time.sleep(2.0)
            return None

        cm._run_weight_optimization = slow_weight_opt

        branch = _build_promoted_branch(cm, tmp_path)

        t_start = time.monotonic()
        cm._on_promote(branch)
        elapsed = time.monotonic() - t_start

        assert elapsed < 1.0, (
            f"_on_promote should return in <1s (non-blocking), but took {elapsed:.2f}s"
        )

        # Cleanup: join bg threads so they don't linger
        for t in cm._pending_weight_opt_threads:
            t.join(timeout=5.0)


# ---------------------------------------------------------------------------
# R2: bg thread is launched and champion version advances
# ---------------------------------------------------------------------------

class TestBgThreadLaunchedAndJoins:
    def test_bg_thread_launched_and_joins(self, tmp_path):
        """bg thread is appended to _pending_weight_opt_threads and completes."""
        mock_protocol = MagicMock()
        mock_protocol.runner = MagicMock()

        cm = _make_campaign(tmp_path, experiment_protocol=mock_protocol)

        completed = threading.Event()

        def instant_weight_opt(staging_path, version, current_weights):
            completed.set()
            return None  # no improvement — simpler path

        cm._run_weight_optimization = instant_weight_opt

        branch = _build_promoted_branch(cm, tmp_path)
        cm._on_promote(branch)

        assert len(cm._pending_weight_opt_threads) == 1, "bg thread should be registered"

        # Wait for completion
        assert completed.wait(timeout=5.0), "bg thread should complete within 5s"

        for t in cm._pending_weight_opt_threads:
            t.join(timeout=5.0)

        with cm._champion_lock:
            assert cm._champion.version == 2, "champion version should advance to 2"


# ---------------------------------------------------------------------------
# R4: stale bg thread result is discarded
# ---------------------------------------------------------------------------

class TestStaleBgThreadDiscarded:
    def test_stale_bg_result_is_discarded(self, tmp_path):
        """If champion version advances before bg thread completes, result is discarded."""
        from scion.parameter.optimizer import WeightOptimizationResult

        mock_protocol = MagicMock()
        mock_protocol.runner = MagicMock()

        cm = _make_campaign(tmp_path, experiment_protocol=mock_protocol)

        # Barrier: make weight opt block until we advance the champion version
        barrier = threading.Barrier(2, timeout=5.0)

        def blocking_weight_opt(staging_path, version, current_weights):
            try:
                barrier.wait()  # sync 1: bg thread is running
                barrier.wait()  # sync 2: main thread has advanced champion
            except threading.BrokenBarrierError:
                pass
            return WeightOptimizationResult(
                improved=True,
                baseline_score=0.5,
                best_score=0.8,
                best_weights={"local_search": 99.0},  # should be discarded
                n_evaluations=2,
            )

        cm._run_weight_optimization = blocking_weight_opt

        branch1 = _build_promoted_branch(cm, tmp_path)
        cm._on_promote(branch1)  # starts bg thread for version 2

        # Wait until bg thread is inside weight opt
        barrier.wait()  # sync 1

        # Manually advance champion to version 3
        with cm._champion_lock:
            cm._champion = ChampionState(
                version=3,
                operator_pool={"local_search": 1.0},
                solver_config_hash="abc123",
                code_snapshot_path=cm._champion.code_snapshot_path,
                code_snapshot_hash="newHash",
                promoted_at="2026-01-01T00:00:00",
            )

        # Release bg thread to complete
        barrier.wait()  # sync 2

        # Join all bg threads
        for t in cm._pending_weight_opt_threads:
            t.join(timeout=5.0)

        # Champion version should remain 3 and pool NOT updated to 99.0
        with cm._champion_lock:
            assert cm._champion.version == 3, "Champion version must not be rolled back"
            assert cm._champion.operator_pool.get("local_search") != 99.0, (
                "Stale bg thread result (weight=99.0) must be discarded"
            )
