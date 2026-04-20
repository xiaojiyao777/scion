"""Tests for Sprint P: campaign journal, weight-opt feedback, solution consistency, canary."""
from __future__ import annotations

import sqlite3
import pytest

from scion.core.canary import CanarySetVersion
from scion.core.models import WeightOptimizationResult
from scion.lineage.registry import LineageRegistry
from scion.proposal.journal import CampaignJournal, JournalSnapshot
from scion.proposal.weight_feedback import extract_weight_signals, render_weight_feedback
from scion.verification.state_mutation import _classify_consistency_failure, _check_solution_consistency


# ---------------------------------------------------------------------------
# W9: Campaign journal
# ---------------------------------------------------------------------------

class TestCampaignJournal:
    def test_empty_db(self, tmp_path) -> None:
        registry = LineageRegistry(str(tmp_path / "test.db"))
        journal = CampaignJournal(registry)
        snap = journal.build_snapshot()
        assert snap.total_experiments == 0
        assert snap.champion_epochs == ()

    def test_render_empty(self, tmp_path) -> None:
        registry = LineageRegistry(str(tmp_path / "test.db"))
        journal = CampaignJournal(registry)
        text = journal.render_for_llm()
        assert "Campaign Journal" in text

    def test_snapshot_with_data(self, tmp_path) -> None:
        registry = LineageRegistry(str(tmp_path / "test.db"))
        with sqlite3.connect(registry.db_path) as conn:
            conn.execute("""
                INSERT INTO champions (version, operator_pool_json, solver_config_hash,
                    code_snapshot_path, code_snapshot_hash, promoted_at)
                VALUES (1, '{}', 'h', '/p', 'hash1', datetime('now'))
            """)
            conn.execute("""
                INSERT INTO hypotheses (hypothesis_id, branch_id, change_locus, action,
                    status, created_at, base_champion_version, family_id)
                VALUES ('h1', 'b1', 'x', 'modify', 'active', datetime('now'), 1, 'fam_a')
            """)
        journal = CampaignJournal(registry)
        snap = journal.build_snapshot()
        assert len(snap.champion_epochs) == 1
        assert snap.champion_epochs[0].n_hypotheses == 1
        assert snap.family_distribution.get("fam_a") == 1


# ---------------------------------------------------------------------------
# W10: Weight-opt feedback
# ---------------------------------------------------------------------------

class TestWeightFeedback:
    def test_no_result(self) -> None:
        assert extract_weight_signals(None) == []
        assert render_weight_feedback(None) == ""

    def test_not_improved(self) -> None:
        r = WeightOptimizationResult(
            baseline_weights={"a": 1.0}, best_weights={"a": 1.0},
            baseline_score=0.5, best_score=0.4, improved=False,
            n_evaluations=10, elapsed_seconds=5.0, observations_ref="",
        )
        assert extract_weight_signals(r) == []

    def test_improved_signals(self) -> None:
        r = WeightOptimizationResult(
            baseline_weights={"op_a": 1.0, "op_b": 1.0, "op_c": 1.0},
            best_weights={"op_a": 2.0, "op_b": 0.5, "op_c": 1.1},
            baseline_score=0.3, best_score=0.6, improved=True,
            n_evaluations=20, elapsed_seconds=10.0, observations_ref="",
        )
        signals = extract_weight_signals(r)
        assert len(signals) == 3
        dirs = {s.operator_name: s.direction for s in signals}
        assert dirs["op_a"] == "increased"
        assert dirs["op_b"] == "decreased"
        assert dirs["op_c"] == "stable"

    def test_render(self) -> None:
        r = WeightOptimizationResult(
            baseline_weights={"op_a": 1.0},
            best_weights={"op_a": 2.0},
            baseline_score=0.3, best_score=0.6, improved=True,
            n_evaluations=10, elapsed_seconds=5.0, observations_ref="",
        )
        text = render_weight_feedback(r)
        assert "Parameter Search Feedback" in text
        assert "op_a" in text


# ---------------------------------------------------------------------------
# W11: Solution consistency diagnosis
# ---------------------------------------------------------------------------

class TestSolutionConsistencyDiagnosis:
    def test_candidate_classification(self) -> None:
        issues = ["order o1 in multiple vehicles: v1 and v2"]
        assert _classify_consistency_failure(issues) == "CANDIDATE"

    def test_env_classification(self) -> None:
        issues = ["empty vehicle v3 in output"]
        assert _classify_consistency_failure(issues) == "ENV"

    def test_unknown_classification(self) -> None:
        issues = ["some weird issue"]
        assert _classify_consistency_failure(issues) == "UNKNOWN"

    def test_consistency_check_clean(self) -> None:
        raw = {
            "solution": {
                "assignment": {"o1": "v1", "o2": "v1"},
                "vehicles": {"v1": {"order_ids": ["o1", "o2"]}},
            }
        }
        assert _check_solution_consistency(raw) == []

    def test_consistency_check_duplicate(self) -> None:
        raw = {
            "solution": {
                "assignment": {"o1": "v1"},
                "vehicles": {
                    "v1": {"order_ids": ["o1"]},
                    "v2": {"order_ids": ["o1"]},
                },
            }
        }
        issues = _check_solution_consistency(raw)
        assert len(issues) > 0
        assert "multiple vehicles" in issues[0]


# ---------------------------------------------------------------------------
# W12: Canary versioning
# ---------------------------------------------------------------------------

class TestCanaryVersioning:
    def test_initial_version(self) -> None:
        v = CanarySetVersion(version="v1", cases=["/data/c1.json", "/data/c2.json"])
        assert len(v.cases) == 2
        assert v.accumulated_candidates == []

    def test_accumulate_candidate(self) -> None:
        v = CanarySetVersion(version="v1", cases=["/data/c1.json"])
        v.add_candidate("/data/c3.json", "known_failure")
        assert len(v.accumulated_candidates) == 1
        assert v.cases == ["/data/c1.json"]

    def test_no_duplicate_candidates(self) -> None:
        v = CanarySetVersion(version="v1", cases=[])
        v.add_candidate("/data/c3.json", "reason1")
        v.add_candidate("/data/c3.json", "reason1")
        assert len(v.accumulated_candidates) == 1

    def test_export_next_version(self) -> None:
        v = CanarySetVersion(version="v1", cases=["/data/c1.json"])
        v.add_candidate("/data/c3.json", "known_failure")
        v2 = v.export_next_version("v2")
        assert v2.version == "v2"
        assert "/data/c1.json" in v2.cases
        assert "/data/c3.json" in v2.cases
        assert v2.accumulated_candidates == []

    def test_export_no_duplicate_existing(self) -> None:
        v = CanarySetVersion(version="v1", cases=["/data/c1.json"])
        v.add_candidate("/data/c1.json", "already_exists")
        v2 = v.export_next_version("v2")
        assert v2.cases.count("/data/c1.json") == 1
