"""Tests for scion/protocol/ — evaluation, stats, gates, experiment."""
from __future__ import annotations
import inspect
import json
import os
import uuid
import pytest
from unittest.mock import MagicMock
from datetime import datetime
from types import SimpleNamespace

from scion.core.models import (
    ExperimentStage, EvalStats, ProtocolResult, RunResult, SolverOutput, CanaryResult,
    MechanismChange,
)
from scion.config.problem import ProtocolConfig, SplitManifest, SeedLedgerConfig
from scion.protocol.evaluation import lexicographic_compare, compute_delta
from scion.protocol.stats import compute_eval_stats, bootstrap_ci
from scion.protocol.gates import GateResult, screening_gate, validation_gate, frozen_gate
from scion.protocol.experiment import SplitManager, SeedLedger, ExperimentProtocol


# ─────────────────────────────────────────────────────────────────────────────
# evaluation.py
# ─────────────────────────────────────────────────────────────────────────────



















# ─────────────────────────────────────────────────────────────────────────────
# stats.py
# ─────────────────────────────────────────────────────────────────────────────













# ─────────────────────────────────────────────────────────────────────────────
# gates.py
# ─────────────────────────────────────────────────────────────────────────────

def _make_stats(**kwargs) -> EvalStats:
    defaults = dict(
        n_cases=10, wins=7, losses=2, ties=1,
        win_rate=0.7, median_delta=0.01,
        ci_low=0.005, ci_high=0.02,
    )
    defaults.update(kwargs)
    return EvalStats(**defaults)


_cfg = ProtocolConfig()
































# ─────────────────────────────────────────────────────────────────────────────
# experiment.py — SplitManager, SeedLedger
# ─────────────────────────────────────────────────────────────────────────────

def _make_manifest():
    # canary cases must be disjoint from screening/validation/frozen
    return SplitManifest(
        version="test",
        screening=["case_a", "case_b"],
        validation=["case_c", "case_d"],
        frozen=["case_e", "case_f"],
        canary=["canary_x", "canary_y"],
    )


def _make_ledger():
    return SeedLedgerConfig(
        version="test",
        screening=[1, 2],
        validation=[3, 4],
        frozen=[5, 6],
        canary=[99],
    )






def _make_run_result(
    splits: int,
    cost: float,
    feasible: bool = True,
    elapsed_ms: int = 100,
    runtime: dict | None = None,
) -> RunResult:
    return RunResult(
        success=True,
        exit_code=0,
        stdout="",
        stderr="",
        elapsed_ms=elapsed_ms,
        output=SolverOutput(
            vehicles={},
            assignment={},
            objective={"subcategory_splits": splits, "total_cost": cost},
            feasible=feasible,
            runtime=runtime or {},
        ),
    )


def _make_missing_output(elapsed_ms: int = 100) -> RunResult:
    return RunResult(
        success=True,
        exit_code=0,
        stdout="",
        stderr="",
        elapsed_ms=elapsed_ms,
        output=None,
        output_path=None,
    )


def _make_run_failure(category: str = "timeout", elapsed_ms: int = 1000) -> RunResult:
    return RunResult(
        success=False,
        exit_code=-9,
        stdout="",
        stderr=category,
        elapsed_ms=elapsed_ms,
        output=None,
        output_path=None,
        error_category=category,
    )


def _make_protocol(runner, tmp_path, problem_spec=None) -> ExperimentProtocol:
    return ExperimentProtocol(
        protocol_config=ProtocolConfig(),
        split_manager=SplitManager(_make_manifest()),
        seed_ledger=SeedLedger(_make_ledger()),
        runner=runner,
        time_limit_sec=10,
        metrics_dir=str(tmp_path / "metrics"),
        problem_spec=problem_spec,
    )


def _surface_problem_spec(
    name: str = "dispatch_policy",
    required_runtime_fields: tuple[str, ...] = ("dispatch_loaded", "dispatch_errors"),
):
    return SimpleNamespace(
        research_surfaces=[
            SimpleNamespace(
                name=name,
                evidence=SimpleNamespace(
                    required_runtime_fields=list(required_runtime_fields)
                ),
            )
        ]
    )


__all__ = [
    name
    for name in globals()
    if not (name.startswith("__") and name.endswith("__"))
]
