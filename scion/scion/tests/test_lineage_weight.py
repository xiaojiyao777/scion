"""Tests for T17a — weight_optimizations lineage table."""
from __future__ import annotations

import sqlite3

import pytest

from scion.core.models import WeightOptimizationResult
from scion.lineage.registry import LineageRegistry


def _make_result(baseline_score=0.5, best_score=0.8, improved=True) -> WeightOptimizationResult:
    return WeightOptimizationResult(
        baseline_weights={"op_a": 1.0, "op_b": 1.0},
        best_weights={"op_a": 1.5, "op_b": 0.8},
        baseline_score=baseline_score,
        best_score=best_score,
        improved=improved,
        n_evaluations=16,
        elapsed_seconds=2.3,
        observations_ref="",
    )


def test_weight_optimization_table_created(tmp_path):
    """LineageRegistry.__init__ creates the weight_optimizations table."""
    db_path = str(tmp_path / "scion.db")
    LineageRegistry(db_path)

    with sqlite3.connect(db_path) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert "weight_optimizations" in tables


def test_record_weight_optimization(tmp_path):
    """record_weight_optimization writes a row and returns an optimization_id."""
    db_path = str(tmp_path / "scion.db")
    reg = LineageRegistry(db_path)

    opt_id = reg.record_weight_optimization(
        campaign_id="camp_1",
        champion_version=2,
        result=_make_result(),
    )

    assert opt_id is not None
    assert len(opt_id) > 0

    rows = reg.query_weight_optimizations(campaign_id="camp_1")
    assert len(rows) == 1
    assert rows[0]["optimization_id"] == opt_id
    assert rows[0]["champion_version"] == 2
    assert rows[0]["improved"] == 1
    assert rows[0]["n_evaluations"] == 16


def test_query_weight_optimizations_by_version(tmp_path):
    """Records from different champion versions can be queried independently."""
    db_path = str(tmp_path / "scion.db")
    reg = LineageRegistry(db_path)

    reg.record_weight_optimization("camp", 2, _make_result(best_score=0.8))
    reg.record_weight_optimization("camp", 3, _make_result(best_score=0.9))

    v2_rows = reg.query_weight_optimizations(champion_version=2)
    v3_rows = reg.query_weight_optimizations(champion_version=3)

    assert len(v2_rows) == 1
    assert len(v3_rows) == 1
    assert abs(v2_rows[0]["best_score"] - 0.8) < 1e-9
    assert abs(v3_rows[0]["best_score"] - 0.9) < 1e-9


def test_query_weight_optimizations_empty(tmp_path):
    """Query on an empty table returns an empty list."""
    db_path = str(tmp_path / "scion.db")
    reg = LineageRegistry(db_path)

    rows = reg.query_weight_optimizations()
    assert rows == []
