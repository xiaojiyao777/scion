"""Sprint J-RL2 tests: champion evolution, weight feedback, full trajectory."""
from __future__ import annotations

import json
import os
import sqlite3

import pytest

from scion.proposal.research_log import CampaignResearchLog, BranchSummary


# ---------------------------------------------------------------------------
# Helper: create test DB with all tables
# ---------------------------------------------------------------------------

def _create_full_db(
    path: str,
    rows: list,
    *,
    champions: list | None = None,
    weight_opts: list | None = None,
    hypotheses: list | None = None,
) -> None:
    """Create a test SQLite DB with experiment_events, champions, weight_optimizations."""
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE experiment_events (
            event_id TEXT PRIMARY KEY,
            branch_id TEXT NOT NULL,
            event_kind TEXT DEFAULT 'experiment',
            hypothesis_id TEXT,
            stage TEXT,
            screening_win_rate REAL,
            screening_median_delta REAL,
            decision TEXT,
            patch_file TEXT,
            hypothesis_text TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS hypotheses (
            hypothesis_id TEXT PRIMARY KEY,
            branch_id TEXT,
            change_locus TEXT,
            action TEXT,
            status TEXT,
            target_file TEXT,
            hypothesis_text TEXT,
            created_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS champions (
            version INTEGER PRIMARY KEY,
            operator_pool_json TEXT NOT NULL,
            solver_config_hash TEXT NOT NULL,
            code_snapshot_path TEXT NOT NULL,
            code_snapshot_hash TEXT NOT NULL,
            promotion_experiment_id TEXT,
            promoted_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS weight_optimizations (
            optimization_id TEXT PRIMARY KEY,
            campaign_id TEXT,
            champion_version INTEGER NOT NULL,
            n_operators INTEGER NOT NULL,
            n_evaluations INTEGER NOT NULL,
            baseline_score REAL,
            best_score REAL,
            improved INTEGER,
            baseline_weights_json TEXT,
            best_weights_json TEXT,
            elapsed_seconds REAL,
            observations_ref TEXT,
            timestamp TEXT NOT NULL
        )
    """)
    for i, row in enumerate(rows):
        conn.execute("""
            INSERT INTO experiment_events
            (event_id, branch_id, event_kind, hypothesis_id, stage, screening_win_rate,
             decision, patch_file, hypothesis_text, created_at)
            VALUES (?, ?, 'experiment', ?, ?, ?, ?, ?, ?, datetime('now', ?))
        """, (
            f"evt-{i}",
            row["branch_id"],
            row.get("hypothesis_id"),
            row.get("stage", "screening"),
            row.get("wr"),
            row.get("decision", "abandon"),
            row.get("file"),
            row.get("hyp"),
            f"+{i} seconds",
        ))
    for c in (champions or []):
        conn.execute("""
            INSERT INTO champions
            (version, operator_pool_json, solver_config_hash, code_snapshot_path,
             code_snapshot_hash, promotion_experiment_id, promoted_at)
            VALUES (?, '{}', 'hash', ?, 'hash', ?, datetime('now'))
        """, (c["version"], c["code_snapshot_path"], c.get("promotion_experiment_id")))
    for w in (weight_opts or []):
        conn.execute("""
            INSERT INTO weight_optimizations
            (optimization_id, campaign_id, champion_version, n_operators, n_evaluations,
             baseline_score, best_score, improved, baseline_weights_json, best_weights_json,
             elapsed_seconds, observations_ref, timestamp)
            VALUES (?, 'camp1', ?, ?, 10, 0.5, 0.6, 1, '{}', ?, 60.0, '', datetime('now', ?))
        """, (
            w["id"],
            w["champion_version"],
            w["n_operators"],
            w["best_weights_json"],
            f"+{w.get('offset', 0)} seconds",
        ))
    for h in (hypotheses or []):
        conn.execute("""
            INSERT INTO hypotheses
            (hypothesis_id, branch_id, target_file, hypothesis_text)
            VALUES (?, ?, ?, ?)
        """, (h["hypothesis_id"], h.get("branch_id"), h.get("target_file"), h.get("hyp")))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Test 1: Champion evolution shows diff
# ---------------------------------------------------------------------------

class TestChampionEvolution:
    def test_champion_evolution_shows_diff(self, tmp_path):
        """v1 has N operators, v2 added a new one — shown in evolution section."""
        db_path = str(tmp_path)
        # Create operator dirs for v1 and v2
        v1_ops = tmp_path / "champions" / "v1" / "operators"
        v2_ops = tmp_path / "champions" / "v2" / "operators"
        v1_ops.mkdir(parents=True)
        v2_ops.mkdir(parents=True)
        # v1 base operators
        for name in ["move_order.py", "swap_orders.py", "__init__.py", "base.py"]:
            (v1_ops / name).write_text("# op")
        # v2 = v1 + new operator
        for name in ["move_order.py", "swap_orders.py", "subcat_consolidate.py", "__init__.py", "base.py"]:
            (v2_ops / name).write_text("# op")

        _create_full_db(
            os.path.join(db_path, "scion.db"),
            rows=[
                {"branch_id": "b1", "stage": "screening", "wr": 1.0, "decision": "promote",
                 "file": "operators/subcat_consolidate.py", "hyp": "consolidate"},
            ],
            champions=[
                {"version": 1, "code_snapshot_path": str(tmp_path / "champions" / "v1")},
                {"version": 2, "code_snapshot_path": str(tmp_path / "champions" / "v2"),
                 "promotion_experiment_id": "evt-0"},
            ],
        )
        log = CampaignResearchLog(db_path)
        rendered = log.render()
        assert "v1 → base pool:" in rendered
        assert "move_order" in rendered
        assert "v2 → added subcat_consolidate" in rendered


# ---------------------------------------------------------------------------
# Test 2-3: Weight feedback
# ---------------------------------------------------------------------------

class TestWeightFeedback:
    def test_weight_feedback_sorted_by_weight(self, tmp_path):
        """Weights sorted descending, high/low annotations correct."""
        db_path = str(tmp_path)
        weights = {
            "destroy_rebuild": 3.51,
            "move_order": 1.30,
            "split_vehicle": 0.08,
            "merge_vehicles": 0.60,
        }
        _create_full_db(
            os.path.join(db_path, "scion.db"),
            rows=[
                {"branch_id": "b1", "stage": "screening", "wr": 0.5, "decision": "abandon",
                 "file": "operators/op.py", "hyp": "test"},
            ],
            weight_opts=[
                {"id": "w1", "champion_version": 1, "n_operators": 4,
                 "best_weights_json": json.dumps(weights)},
            ],
        )
        log = CampaignResearchLog(db_path)
        rendered = log.render()
        # Check order: destroy_rebuild (3.51) before move_order (1.30) before merge (0.60) before split (0.08)
        pos_destroy = rendered.index("destroy_rebuild")
        pos_move = rendered.index("move_order")
        pos_merge = rendered.index("merge_vehicles")
        pos_split = rendered.index("split_vehicle")
        assert pos_destroy < pos_move < pos_merge < pos_split
        # Check annotations
        assert "高贡献" in rendered  # destroy_rebuild > 1.0
        assert "低贡献" in rendered  # split_vehicle < 0.3

    def test_weight_feedback_empty_when_no_data(self, tmp_path):
        """No weight_optimizations records — no crash, no weight section."""
        db_path = str(tmp_path)
        _create_full_db(
            os.path.join(db_path, "scion.db"),
            rows=[
                {"branch_id": "b1", "stage": "screening", "wr": 0.5, "decision": "abandon",
                 "file": "operators/op.py", "hyp": "test"},
            ],
        )
        log = CampaignResearchLog(db_path)
        rendered = log.render()
        assert "算子权重" not in rendered


# ---------------------------------------------------------------------------
# Test 4: Hypothesis text 200 chars
# ---------------------------------------------------------------------------

class TestFullTrajectory:
    def test_full_hypothesis_text_200_chars(self, tmp_path):
        """Hypothesis text truncated at 200 chars, not 40."""
        db_path = str(tmp_path)
        long_hyp = "A" * 300  # 300 chars
        _create_full_db(
            os.path.join(db_path, "scion.db"),
            rows=[
                {"branch_id": "b1", "stage": "screening", "wr": 0.5, "decision": "abandon",
                 "file": "operators/op.py", "hyp": long_hyp},
            ],
        )
        log = CampaignResearchLog(db_path)
        rendered = log.render()
        # Should contain 200 A's but not 201
        assert "A" * 200 in rendered
        assert "A" * 201 not in rendered

    def test_multi_round_trajectory_shown(self, tmp_path):
        """Same branch with multiple screening rounds shows all rounds."""
        db_path = str(tmp_path)
        _create_full_db(
            os.path.join(db_path, "scion.db"),
            rows=[
                {"branch_id": "b1", "stage": "screening", "wr": 0.30, "decision": "continue",
                 "file": "operators/repack.py", "hyp": "repack subcategories"},
                {"branch_id": "b1", "stage": "screening", "wr": 0.00, "decision": "abandon",
                 "file": "operators/repack.py", "hyp": "repack subcategories"},
            ],
        )
        log = CampaignResearchLog(db_path)
        rendered = log.render()
        assert "[ABANDONED] repack (2 rounds)" in rendered
        # Both screening wr values should appear
        assert "scr=0.30" in rendered
        assert "scr=0.00" in rendered

    def test_frozen_only_pass_fail_no_wr(self, tmp_path):
        """Frozen stage shows only PASS/FAIL, no numeric wr."""
        db_path = str(tmp_path)
        _create_full_db(
            os.path.join(db_path, "scion.db"),
            rows=[
                {"branch_id": "b1", "stage": "screening", "wr": 0.80, "decision": "pass",
                 "file": "operators/op.py", "hyp": "test"},
                {"branch_id": "b1", "stage": "validation", "wr": 0.90, "decision": "pass",
                 "file": "operators/op.py", "hyp": "test"},
                {"branch_id": "b1", "stage": "frozen", "wr": 0.70, "decision": "promote",
                 "file": "operators/op.py", "hyp": "test"},
            ],
        )
        log = CampaignResearchLog(db_path)
        rendered = log.render()
        assert "frozen=PASS" in rendered
        # The frozen wr (0.70) must NOT appear near frozen
        assert "frozen=0" not in rendered
        assert "frozen_wr" not in rendered


# ---------------------------------------------------------------------------
# Test 7: Abandoned batch display over 20
# ---------------------------------------------------------------------------

class TestAbandonedBatchDisplay:
    def test_abandoned_batch_display_over_20(self, tmp_path):
        """More than 20 abandoned branches — bottom ones use compact batch format."""
        db_path = str(tmp_path)
        rows = []
        for i in range(25):
            rows.append({
                "branch_id": f"b-abn-{i:02d}",
                "stage": "screening",
                "wr": 0.01 * i,  # 0.00 to 0.24
                "decision": "abandon",
                "file": f"operators/abn_op_{i:02d}.py",
                "hyp": f"abandon hypothesis {i}",
            })
        _create_full_db(os.path.join(db_path, "scion.db"), rows)
        log = CampaignResearchLog(db_path)
        rendered = log.render()
        # Top 20 should be rendered individually (highest wr first)
        assert "[ABANDONED] abn_op_24" in rendered  # highest wr=0.24
        # Bottom 5 should be in batch format
        assert "ABANDONED x5 more" in rendered


# ---------------------------------------------------------------------------
# Test 8-9: render() includes new sections
# ---------------------------------------------------------------------------

class TestRenderSections:
    def test_render_includes_champion_evolution_section(self, tmp_path):
        """render() output includes 'Champion 演化' section when champions exist."""
        db_path = str(tmp_path)
        v1_ops = tmp_path / "champ" / "v1" / "operators"
        v1_ops.mkdir(parents=True)
        (v1_ops / "move_order.py").write_text("# op")

        _create_full_db(
            os.path.join(db_path, "scion.db"),
            rows=[
                {"branch_id": "b1", "stage": "screening", "wr": 0.5, "decision": "abandon",
                 "file": "operators/op.py", "hyp": "test"},
            ],
            champions=[
                {"version": 1, "code_snapshot_path": str(tmp_path / "champ" / "v1")},
            ],
        )
        log = CampaignResearchLog(db_path)
        rendered = log.render()
        assert "Champion 演化" in rendered
        assert "v1 → base pool:" in rendered

    def test_render_includes_weight_section(self, tmp_path):
        """render() output includes 'Champion Pool 算子权重' section when weights exist."""
        db_path = str(tmp_path)
        weights = {"op_a": 2.0, "op_b": 0.5}
        _create_full_db(
            os.path.join(db_path, "scion.db"),
            rows=[
                {"branch_id": "b1", "stage": "screening", "wr": 0.5, "decision": "abandon",
                 "file": "operators/op.py", "hyp": "test"},
            ],
            weight_opts=[
                {"id": "w1", "champion_version": 1, "n_operators": 2,
                 "best_weights_json": json.dumps(weights)},
            ],
        )
        log = CampaignResearchLog(db_path)
        rendered = log.render()
        assert "Champion Pool 算子权重" in rendered
        assert "op_a" in rendered
        assert "op_b" in rendered
