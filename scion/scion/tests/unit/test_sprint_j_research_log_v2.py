"""Sprint J-RL3 tests: info layers, full hypothesis text, research snapshot, trajectories."""
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
             screening_median_delta, decision, patch_file, hypothesis_text, created_at)
            VALUES (?, ?, 'experiment', ?, ?, ?, ?, ?, ?, ?, datetime('now', ?))
        """, (
            f"evt-{i}",
            row["branch_id"],
            row.get("hypothesis_id"),
            row.get("stage", "screening"),
            row.get("wr"),
            row.get("md"),
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
            (hypothesis_id, branch_id, change_locus, action, target_file, hypothesis_text)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            h["hypothesis_id"],
            h.get("branch_id"),
            h.get("change_locus"),
            h.get("action"),
            h.get("target_file"),
            h.get("hyp"),
        ))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Test 1: render_has_three_layers
# ---------------------------------------------------------------------------

class TestThreeLayers:
    def test_render_has_three_layers(self, tmp_path):
        """render() contains all three sections: snapshot, evolution, trajectories."""
        db_path = str(tmp_path)
        v1_ops = tmp_path / "champions" / "v1" / "operators"
        v2_ops = tmp_path / "champions" / "v2" / "operators"
        v1_ops.mkdir(parents=True)
        v2_ops.mkdir(parents=True)
        for name in ["move_order.py", "__init__.py"]:
            (v1_ops / name).write_text("# op")
        for name in ["move_order.py", "consolidate.py", "__init__.py"]:
            (v2_ops / name).write_text("# op")

        _create_full_db(
            os.path.join(db_path, "scion.db"),
            rows=[
                {"branch_id": "b1", "stage": "screening", "wr": 1.0, "decision": "promote",
                 "file": "operators/consolidate.py", "hyp": "consolidate hypothesis"},
            ],
            champions=[
                {"version": 1, "code_snapshot_path": str(tmp_path / "champions" / "v1")},
                {"version": 2, "code_snapshot_path": str(tmp_path / "champions" / "v2"),
                 "promotion_experiment_id": "evt-0"},
            ],
            weight_opts=[
                {"id": "w1", "champion_version": 2, "n_operators": 2,
                 "best_weights_json": json.dumps({"move_order": 2.0, "consolidate": 0.5})},
            ],
        )
        log = CampaignResearchLog(db_path)
        rendered = log.render(view="audit")
        assert "### 研究进展快照" in rendered
        assert "### Champion 演化轨迹" in rendered
        assert "### 所有实验 Branch 轨迹" in rendered


class TestResearchSnapshotChampionVersion:
    def test_base_champion_is_not_counted_as_promotion(self, tmp_path):
        db_path = str(tmp_path)
        v1_ops = tmp_path / "champions" / "v1" / "operators"
        v1_ops.mkdir(parents=True)
        (v1_ops / "__init__.py").write_text("# op")

        _create_full_db(
            os.path.join(db_path, "scion.db"),
            rows=[
                {"branch_id": "b1", "stage": "screening", "wr": 0.0,
                 "decision": "abandon", "file": "operators/op.py",
                 "hyp": "safe no-op"},
            ],
            champions=[
                {"version": 1, "code_snapshot_path": str(tmp_path / "champions" / "v1")},
            ],
        )

        rendered = CampaignResearchLog(db_path).render(view="audit")

        assert "Champion 当前版本：v1，共 0 次晋升" in rendered

    def test_hypothesis_view_hides_champion_version_and_promotion_count(self, tmp_path):
        db_path = str(tmp_path)
        v1_ops = tmp_path / "champions" / "v1" / "operators"
        v1_ops.mkdir(parents=True)
        (v1_ops / "__init__.py").write_text("# op")

        _create_full_db(
            os.path.join(db_path, "scion.db"),
            rows=[
                {"branch_id": "b1", "stage": "screening", "wr": 0.0,
                 "decision": "abandon", "file": "operators/op.py",
                 "hyp": "safe no-op"},
            ],
            champions=[
                {"version": 1, "code_snapshot_path": str(tmp_path / "champions" / "v1")},
            ],
        )

        rendered = CampaignResearchLog(db_path).render()

        assert "Champion 当前版本" not in rendered
        assert "晋升" not in rendered
        assert "搜索进度" in rendered


# ---------------------------------------------------------------------------
# Test 2: snapshot_shows_coverage_gaps
# ---------------------------------------------------------------------------

class TestCoverageGaps:
    def test_snapshot_shows_coverage_gaps(self, tmp_path):
        """Under-explored locus/action combinations are flagged in snapshot."""
        db_path = str(tmp_path)
        # 2 attempts at vehicle_level/modify (< 5 → flagged)
        # 6 attempts at vehicle_level/create_new (>= 5 → not flagged)
        rows = []
        for i in range(6):
            rows.append({
                "branch_id": f"b-create-{i}", "stage": "screening", "wr": 0.1,
                "decision": "abandon", "file": f"operators/op_{i}.py",
                "hyp": f"create hypothesis {i}", "hypothesis_id": f"h-create-{i}",
            })
        for i in range(2):
            rows.append({
                "branch_id": f"b-modify-{i}", "stage": "screening", "wr": 0.1,
                "decision": "abandon", "file": f"operators/mod_{i}.py",
                "hyp": f"modify hypothesis {i}", "hypothesis_id": f"h-modify-{i}",
            })
        hypotheses = []
        for i in range(6):
            hypotheses.append({
                "hypothesis_id": f"h-create-{i}", "branch_id": f"b-create-{i}",
                "change_locus": "vehicle_level", "action": "create_new",
                "hyp": f"create hypothesis {i}",
            })
        for i in range(2):
            hypotheses.append({
                "hypothesis_id": f"h-modify-{i}", "branch_id": f"b-modify-{i}",
                "change_locus": "vehicle_level", "action": "modify",
                "hyp": f"modify hypothesis {i}",
            })

        _create_full_db(
            os.path.join(db_path, "scion.db"),
            rows=rows,
            hypotheses=hypotheses,
        )
        log = CampaignResearchLog(db_path)
        rendered = log.render()
        assert "vehicle_level/modify" in rendered
        assert "不足" in rendered
        # vehicle_level/create_new has 6 attempts, should NOT be in gaps
        assert "vehicle_level/create_new" not in rendered.split("尚未探索的方向")[1] if "尚未探索的方向" in rendered else True


# ---------------------------------------------------------------------------
# Test 3: snapshot_shows_weights
# ---------------------------------------------------------------------------

class TestSnapshotWeights:
    def test_snapshot_shows_weights(self, tmp_path):
        """Weight annotations (高贡献/中等/低贡献) appear in snapshot."""
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
        # Check order: destroy_rebuild (3.51) before move_order (1.30)
        pos_destroy = rendered.index("destroy_rebuild")
        pos_move = rendered.index("move_order")
        pos_merge = rendered.index("merge_vehicles")
        pos_split = rendered.index("split_vehicle")
        assert pos_destroy < pos_move < pos_merge < pos_split
        # Check annotations
        assert "高贡献" in rendered
        assert "低贡献" in rendered
        assert "中等" in rendered


# ---------------------------------------------------------------------------
# Test 4: hypothesis_text_not_truncated
# ---------------------------------------------------------------------------

class TestNoTruncation:
    def test_hypothesis_text_not_truncated(self, tmp_path):
        """Hypothesis text > 200 chars is preserved in full, not truncated."""
        db_path = str(tmp_path)
        long_hyp = "A" * 500  # 500 chars — well beyond old 200 limit
        _create_full_db(
            os.path.join(db_path, "scion.db"),
            rows=[
                {"branch_id": "b1", "stage": "screening", "wr": 0.5, "decision": "abandon",
                 "file": "operators/op.py", "hyp": long_hyp},
            ],
        )
        log = CampaignResearchLog(db_path)
        rendered = log.render()
        # Full 500-char string must appear
        assert "A" * 500 in rendered


# ---------------------------------------------------------------------------
# Test 5: branch_trajectories_promoted_first
# ---------------------------------------------------------------------------

class TestBranchOrdering:
    def test_branch_trajectories_promoted_first(self, tmp_path):
        """Promoted branches appear before abandoned ones in trajectory section."""
        db_path = str(tmp_path)
        _create_full_db(
            os.path.join(db_path, "scion.db"),
            rows=[
                # Abandoned branch (created first chronologically)
                {"branch_id": "b-abn", "stage": "screening", "wr": 0.1,
                 "decision": "abandon", "file": "operators/abn_op.py",
                 "hyp": "abandoned hypothesis"},
                # Promoted branch (created second)
                {"branch_id": "b-pro", "stage": "screening", "wr": 1.0,
                 "decision": "promote", "file": "operators/pro_op.py",
                 "hyp": "promoted hypothesis"},
            ],
        )
        log = CampaignResearchLog(db_path)
        rendered = log.render(view="audit")
        pos_promoted = rendered.index("promoted")
        pos_abandoned = rendered.index("abandoned")
        assert pos_promoted < pos_abandoned


# ---------------------------------------------------------------------------
# Test 6: frozen_pass_fail_no_wr_no_md
# ---------------------------------------------------------------------------

class TestFrozenExposure:
    def test_frozen_pass_fail_no_wr_no_md(self, tmp_path):
        """Frozen stage shows only PASS/FAIL — no numeric wr or md."""
        db_path = str(tmp_path)
        _create_full_db(
            os.path.join(db_path, "scion.db"),
            rows=[
                {"branch_id": "b1", "stage": "screening", "wr": 0.80, "md": 5000,
                 "decision": "pass", "file": "operators/op.py", "hyp": "test"},
                {"branch_id": "b1", "stage": "validation", "wr": 0.90,
                 "decision": "pass", "file": "operators/op.py", "hyp": "test"},
                {"branch_id": "b1", "stage": "frozen", "wr": 0.70, "md": 3000,
                 "decision": "promote", "file": "operators/op.py", "hyp": "test"},
            ],
        )
        log = CampaignResearchLog(db_path)
        rendered = log.render(view="audit")
        assert "validation: val=0.90" in rendered
        assert "frozen: PASS" in rendered
        # No numeric values near frozen
        assert "frozen=0" not in rendered
        assert "frozen_wr" not in rendered
        # Screening md should appear
        assert "[md=5000]" in rendered

    def test_hypothesis_view_hides_validation_and_frozen_outcomes(self, tmp_path):
        """Default render is hypothesis-safe: screening aggregate only."""
        db_path = str(tmp_path)
        _create_full_db(
            os.path.join(db_path, "scion.db"),
            rows=[
                {"branch_id": "b1", "stage": "screening", "wr": 0.80, "md": 5000,
                 "decision": "pass", "file": "operators/op.py", "hyp": "test"},
                {"branch_id": "b1", "stage": "validation", "wr": 0.90,
                 "decision": "pass", "file": "operators/op.py", "hyp": "test"},
                {"branch_id": "b1", "stage": "frozen", "wr": 0.70, "md": 3000,
                 "decision": "promote", "file": "operators/op.py", "hyp": "test"},
                {"branch_id": "b2", "stage": "screening", "wr": 0.40, "md": 1000,
                 "decision": "abandon", "file": "operators/screening_only.py",
                 "hyp": "screening visible"},
            ],
        )
        rendered = CampaignResearchLog(db_path).render()

        assert "scr=0.40" in rendered
        assert "[md=1000]" in rendered
        assert "scr=0.80" not in rendered
        assert "[md=5000]" not in rendered
        assert "→ pass" not in rendered
        assert "→ promote" not in rendered
        assert "val=" not in rendered
        assert "validation:" not in rendered
        assert "frozen:" not in rendered
        assert "frozen=PASS" not in rendered
        assert "promoted" not in rendered


# ---------------------------------------------------------------------------
# Test 7: champion_evolution_includes_hypothesis
# ---------------------------------------------------------------------------

class TestChampionEvolutionHypothesis:
    def test_champion_evolution_includes_hypothesis(self, tmp_path):
        """Promoted operator's full hypothesis appears in champion evolution section."""
        db_path = str(tmp_path)
        v1_ops = tmp_path / "champions" / "v1" / "operators"
        v2_ops = tmp_path / "champions" / "v2" / "operators"
        v1_ops.mkdir(parents=True)
        v2_ops.mkdir(parents=True)
        for name in ["move_order.py", "__init__.py"]:
            (v1_ops / name).write_text("# op")
        for name in ["move_order.py", "subcat_consolidate.py", "__init__.py"]:
            (v2_ops / name).write_text("# op")

        full_hyp = "This operator consolidates subcategory splits by merging vehicles carrying the same subcategory into fewer vehicles with upgraded capacity."
        _create_full_db(
            os.path.join(db_path, "scion.db"),
            rows=[
                {"branch_id": "b1", "stage": "screening", "wr": 1.0, "decision": "promote",
                 "file": "operators/subcat_consolidate.py", "hyp": full_hyp},
            ],
            champions=[
                {"version": 1, "code_snapshot_path": str(tmp_path / "champions" / "v1")},
                {"version": 2, "code_snapshot_path": str(tmp_path / "champions" / "v2"),
                 "promotion_experiment_id": "evt-0"},
            ],
        )
        log = CampaignResearchLog(db_path)
        rendered = log.render(view="audit")
        # Full hypothesis must appear in evolution section
        evo_section = rendered.split("### Champion 演化轨迹")[1].split("###")[0]
        assert full_hyp in evo_section
        assert "v2 新增: subcat_consolidate" in rendered

    def test_hypothesis_view_hides_promoted_hypothesis_and_audit_keeps_it(self, tmp_path):
        """Promotion path details stay out of hypothesis view but remain auditable."""
        db_path = str(tmp_path)
        v1_ops = tmp_path / "champions" / "v1" / "operators"
        v2_ops = tmp_path / "champions" / "v2" / "operators"
        v1_ops.mkdir(parents=True)
        v2_ops.mkdir(parents=True)
        for name in ["move_order.py", "__init__.py"]:
            (v1_ops / name).write_text("# op")
        for name in ["move_order.py", "promoted_secret.py", "__init__.py"]:
            (v2_ops / name).write_text("# op")

        promoted_hyp = "PROMOTED_SECRET_HYPOTHESIS_TEXT should only be in audit"
        _create_full_db(
            os.path.join(db_path, "scion.db"),
            rows=[
                {"branch_id": "b-promoted", "stage": "screening", "wr": 1.0,
                 "decision": "pass", "file": "operators/promoted_secret.py",
                 "hyp": promoted_hyp},
                {"branch_id": "b-promoted", "stage": "validation", "wr": 1.0,
                 "decision": "pass", "file": "operators/promoted_secret.py",
                 "hyp": promoted_hyp},
                {"branch_id": "b-promoted", "stage": "frozen", "wr": 1.0,
                 "decision": "promote", "file": "operators/promoted_secret.py",
                 "hyp": promoted_hyp},
                {"branch_id": "b-screening", "stage": "screening", "wr": 0.4,
                 "decision": "abandon", "file": "operators/screening_only.py",
                 "hyp": "SCREENING_ONLY_VISIBLE_TEXT"},
            ],
            champions=[
                {"version": 1, "code_snapshot_path": str(tmp_path / "champions" / "v1")},
                {"version": 2, "code_snapshot_path": str(tmp_path / "champions" / "v2"),
                 "promotion_experiment_id": "evt-2"},
            ],
        )

        hypothesis_rendered = CampaignResearchLog(db_path).render()
        audit_rendered = CampaignResearchLog(db_path).render(view="audit")

        assert "SCREENING_ONLY_VISIBLE_TEXT" in hypothesis_rendered
        assert "scr=0.40" in hypothesis_rendered
        assert "PROMOTED_SECRET_HYPOTHESIS_TEXT" not in hypothesis_rendered
        assert "Champion 演化轨迹" not in hypothesis_rendered
        assert "promotion" not in hypothesis_rendered.lower()
        assert "promoted" not in hypothesis_rendered.lower()
        assert "frozen: PASS" not in hypothesis_rendered
        assert "validation: val=" not in hypothesis_rendered

        assert "PROMOTED_SECRET_HYPOTHESIS_TEXT" in audit_rendered
        assert "Champion 演化轨迹" in audit_rendered
        assert "promoted" in audit_rendered


# ---------------------------------------------------------------------------
# Test 8: no_historical_operator_code
# ---------------------------------------------------------------------------

class TestNoOperatorCode:
    def test_no_historical_operator_code(self, tmp_path):
        """render() output must NOT contain Python def/class statements."""
        db_path = str(tmp_path)
        v1_ops = tmp_path / "champions" / "v1" / "operators"
        v1_ops.mkdir(parents=True)
        (v1_ops / "move_order.py").write_text("def apply(solution):\n    pass")

        _create_full_db(
            os.path.join(db_path, "scion.db"),
            rows=[
                {"branch_id": "b1", "stage": "screening", "wr": 0.5, "decision": "abandon",
                 "file": "operators/move_order.py", "hyp": "move orders around"},
            ],
            champions=[
                {"version": 1, "code_snapshot_path": str(tmp_path / "champions" / "v1")},
            ],
        )
        log = CampaignResearchLog(db_path)
        rendered = log.render()
        assert "def " not in rendered
        assert "class " not in rendered


# ---------------------------------------------------------------------------
# Test 9: render_no_token_limit_by_default
# ---------------------------------------------------------------------------

class TestNoTokenLimit:
    def test_render_no_token_limit_by_default(self, tmp_path):
        """available_tokens=None means no truncation — all branches rendered."""
        db_path = str(tmp_path)
        rows = []
        for i in range(50):
            rows.append({
                "branch_id": f"b-{i:03d}",
                "stage": "screening",
                "wr": 0.01 * i,
                "decision": "abandon",
                "file": f"operators/op_{i:03d}.py",
                "hyp": f"hypothesis for branch {i} with some detail",
            })
        _create_full_db(os.path.join(db_path, "scion.db"), rows)
        log = CampaignResearchLog(db_path)
        rendered = log.render(available_tokens=None)
        # All 50 branches should be individually rendered
        for i in range(50):
            assert f"op_{i:03d}" in rendered


# ---------------------------------------------------------------------------
# Backward compat: BranchSummary alias
# ---------------------------------------------------------------------------

class TestBackwardCompat:
    def test_branch_summary_alias(self):
        """BranchSummary is still importable as alias."""
        assert BranchSummary is not None

    def test_build_returns_trajectories(self, tmp_path):
        """build() still returns list of BranchTrajectory."""
        db_path = str(tmp_path)
        _create_full_db(
            os.path.join(db_path, "scion.db"),
            rows=[
                {"branch_id": "b1", "stage": "screening", "wr": 0.5, "decision": "abandon",
                 "file": "operators/op.py", "hyp": "test"},
            ],
        )
        log = CampaignResearchLog(db_path)
        result = log.build()
        assert len(result) == 1
        assert result[0].branch_id == "b1"


# ---------------------------------------------------------------------------
# Regression: weight feedback empty when no data
# ---------------------------------------------------------------------------

class TestWeightFeedbackEmpty:
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
        assert "算子池权重" not in rendered
