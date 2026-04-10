"""Tests for scion/runtime/pool_manager.py — PoolManager + registry IO."""
from __future__ import annotations
import os
import pytest
import yaml

from scion.core.models import OperatorConfig, HypothesisProposal, PatchProposal
from scion.runtime.pool_manager import (
    PoolManager, _normalize_weights,
    read_registry, read_weights, update_weights,
)


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


# ─────────────────────────────────────────────────────────────────────────────
# T13 — Registry IO (read_registry / read_weights / update_weights)
# ─────────────────────────────────────────────────────────────────────────────

def _write_registry(tmp_path, operators):
    data = {"operators": operators}
    path = tmp_path / "registry.yaml"
    with open(path, "w") as f:
        yaml.dump(data, f)
    return str(path)


def _two_op_registry(tmp_path):
    ops = [
        {"name": "swap", "file_path": "operators/swap.py", "category": "order_level",
         "weight": 0.5, "class_name": "Swap"},
        {"name": "move", "file_path": "operators/move.py", "category": "order_level",
         "weight": 0.5, "class_name": "Move"},
    ]
    return _write_registry(tmp_path, ops)


def test_read_registry_returns_operator_configs(tmp_path):
    reg_path = _two_op_registry(tmp_path)
    pool = read_registry(reg_path)
    assert "swap" in pool
    assert "move" in pool
    assert pool["swap"].file_path == "operators/swap.py"
    assert pool["swap"].category == "order_level"
    assert abs(pool["swap"].weight - 0.5) < 1e-9
    assert pool["swap"].class_name == "Swap"


def test_read_weights_returns_dict(tmp_path):
    reg_path = _write_registry(tmp_path, [
        {"name": "swap", "file_path": "operators/swap.py", "category": "order_level",
         "weight": 0.3, "class_name": "Swap"},
        {"name": "move", "file_path": "operators/move.py", "category": "order_level",
         "weight": 0.7, "class_name": "Move"},
    ])
    weights = read_weights(reg_path)
    assert isinstance(weights, dict)
    assert abs(weights["swap"] - 0.3) < 1e-9
    assert abs(weights["move"] - 0.7) < 1e-9


def test_update_weights_preserves_other_fields(tmp_path):
    reg_path = _two_op_registry(tmp_path)
    update_weights(reg_path, {"swap": 0.8, "move": 0.2})
    pool = read_registry(reg_path)
    assert pool["swap"].file_path == "operators/swap.py"
    assert pool["swap"].category == "order_level"
    assert pool["swap"].class_name == "Swap"
    assert pool["move"].file_path == "operators/move.py"


def test_update_weights_round_trip(tmp_path):
    reg_path = _two_op_registry(tmp_path)
    new_weights = {"swap": 0.3, "move": 0.7}
    update_weights(reg_path, new_weights)
    read_back = read_weights(reg_path)
    assert abs(read_back["swap"] - 0.3) < 1e-6
    assert abs(read_back["move"] - 0.7) < 1e-6


def test_update_weights_mismatch_raises(tmp_path):
    reg_path = _two_op_registry(tmp_path)
    with pytest.raises(KeyError):
        update_weights(reg_path, {"swap": 1.0})  # missing "move"


def test_update_weights_extra_key_raises(tmp_path):
    reg_path = _two_op_registry(tmp_path)
    with pytest.raises(KeyError):
        update_weights(reg_path, {"swap": 0.5, "move": 0.3, "extra": 0.2})
