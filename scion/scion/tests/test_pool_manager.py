"""Tests for scion/runtime/pool_manager.py — PoolManager."""
from __future__ import annotations
import os
import pytest
import yaml

from scion.core.models import OperatorConfig, HypothesisProposal, PatchProposal
from scion.runtime.pool_manager import PoolManager, _normalize_weights


def _op(name: str, file_path: str, weight: float) -> OperatorConfig:
    return OperatorConfig(
        name=name, file_path=file_path, category="order_level",
        weight=weight, class_name=name.capitalize(),
    )


def _champ_pool():
    return {
        "swap": _op("swap", "operators/swap.py", 0.5),
        "move": _op("move", "operators/move.py", 0.5),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Weight normalisation
# ─────────────────────────────────────────────────────────────────────────────

def test_normalize_weights_sums_to_one():
    pool = {
        "a": _op("a", "a.py", 0.3),
        "b": _op("b", "b.py", 0.3),
        "c": _op("c", "c.py", 0.3),
    }
    normalized = _normalize_weights(pool)
    total = sum(op.weight for op in normalized.values())
    assert abs(total - 1.0) < 1e-9


def test_normalize_weights_empty():
    assert _normalize_weights({}) == {}


# ─────────────────────────────────────────────────────────────────────────────
# build_candidate_pool
# ─────────────────────────────────────────────────────────────────────────────

def test_build_candidate_modify():
    pm = PoolManager(_champ_pool())
    hypothesis = HypothesisProposal(
        hypothesis_text="modify swap",
        change_locus="order_level",
        action="modify",
        target_file="operators/swap.py",
    )
    patch = PatchProposal(
        file_path="operators/swap.py",
        action="modify",
        code_content="class Swap: pass",
    )
    pool = pm.build_candidate_pool(_champ_pool(), hypothesis, patch)
    assert "swap" in pool
    assert pool["swap"].file_path == "operators/swap.py"
    # Weights unchanged
    total = sum(op.weight for op in pool.values())
    assert abs(total - 1.0) < 1e-9


def test_build_candidate_create_new():
    pm = PoolManager(_champ_pool())
    hypothesis = HypothesisProposal(
        hypothesis_text="add new op",
        change_locus="order_level",
        action="create_new",
        suggested_weight=0.2,
    )
    patch = PatchProposal(
        file_path="operators/new_op.py",
        action="create",
        code_content="class NewOp: pass",
    )
    pool = pm.build_candidate_pool(_champ_pool(), hypothesis, patch)
    assert "new_op" in pool
    total = sum(op.weight for op in pool.values())
    assert abs(total - 1.0) < 1e-9, f"weights sum to {total}"


def test_build_candidate_remove():
    pm = PoolManager(_champ_pool())
    hypothesis = HypothesisProposal(
        hypothesis_text="remove swap",
        change_locus="order_level",
        action="remove",
        target_file="operators/swap.py",
    )
    patch = PatchProposal(
        file_path="operators/swap.py",
        action="delete",
        code_content="",
    )
    pool = pm.build_candidate_pool(_champ_pool(), hypothesis, patch)
    assert "swap" not in pool
    assert len(pool) == 1
    total = sum(op.weight for op in pool.values())
    assert abs(total - 1.0) < 1e-9


# ─────────────────────────────────────────────────────────────────────────────
# export_registry
# ─────────────────────────────────────────────────────────────────────────────

def test_export_registry(tmp_path):
    pm = PoolManager(_champ_pool())
    pool = _champ_pool()
    reg_path = pm.export_registry(pool, str(tmp_path / "ws"))
    assert os.path.exists(reg_path)
    with open(reg_path) as f:
        data = yaml.safe_load(f)
    assert "operators" in data
    names = {op["name"] for op in data["operators"]}
    assert names == {"swap", "move"}
