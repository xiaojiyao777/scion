"""Sprint J-Fix unit tests: NULL patch_file, exhausted threshold, saturation baseline, compact display."""
from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple
from unittest.mock import MagicMock

import pytest

from scion.proposal.research_log import CampaignResearchLog, BranchSummary
from scion.proposal.saturation import extract_champion_metrics_from_step


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_test_db(path: str, rows: list, *, hypotheses: list | None = None) -> None:
    """Create a test SQLite DB with experiment_events and optionally hypotheses."""
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
    for i, row in enumerate(rows):
        conn.execute("""
            INSERT INTO experiment_events
            (event_id, branch_id, event_kind, hypothesis_id, stage, screening_win_rate,
             decision, patch_file, hypothesis_text, created_at)
            VALUES (?, ?, 'experiment', ?, ?, ?, ?, ?, ?, datetime('now', ?))
        """, (
            f"evt-{i}",
            row["branch_id"],
            row.get("hypothesis_id", f"h-{i}"),
            row.get("stage", "screening"),
            row.get("wr"),
            row.get("decision", "abandon"),
            row.get("file"),
            row.get("hyp"),
            f"+{i} seconds",
        ))
    for h in (hypotheses or []):
        conn.execute("""
            INSERT INTO hypotheses
            (hypothesis_id, branch_id, target_file, hypothesis_text)
            VALUES (?, ?, ?, ?)
        """, (h["hypothesis_id"], h.get("branch_id"), h.get("target_file"), h.get("hyp")))
    conn.commit()
    conn.close()


def _make_step_with_case_features(case_features_list):
    """Build a minimal StepRecord with case_feedback containing case_features."""
    from scion.core.models import (
        EvalStats, ExperimentStage, HypothesisProposal, ProtocolResult,
        StepRecord, CaseAggregateFeedback,
    )
    case_fbs = []
    for i, feats in enumerate(case_features_list):
        case_fbs.append(CaseAggregateFeedback(
            case_id=f"case-{i}",
            n_pairs=3, wins=2, losses=1, ties=0,
            win_rate=0.67, dominant_result="win",
            decisive_metric="subcategory_splits",
            case_features=feats,
        ))
    pr = ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=EvalStats(n_cases=len(case_fbs), wins=2, losses=1, ties=0,
                        win_rate=0.67, median_delta=0.0, ci_low=0.0, ci_high=0.0),
        gate_outcome="pass",
        reason_codes=(),
        exposed_summary="",
        raw_metrics_ref="",
        case_feedback=tuple(case_fbs),
    )
    hyp = HypothesisProposal(hypothesis_text="test", change_locus="vehicle_level", action="modify")
    return StepRecord(
        round_num=1, branch_id="b1", hypothesis=hyp, patch=None,
        contract_passed=True, verification_passed=True,
        protocol_result=pr, decision=None,
        failure_stage=None, failure_detail=None,
    )


# ---------------------------------------------------------------------------
# Test 1: NULL patch_file resolved via hypotheses JOIN
# ---------------------------------------------------------------------------

class TestResearchLogNullPatchFile:
    def test_null_patch_file_resolved_via_join(self, tmp_path):
        """When patch_file is NULL, operator_name should come from hypotheses.target_file."""
        db_path = str(tmp_path)
        _create_test_db(
            os.path.join(db_path, "scion.db"),
            rows=[
                {"branch_id": "b1", "hypothesis_id": "h1", "stage": "screening",
                 "wr": 0.25, "decision": "abandon", "file": None,
                 "hyp": "consolidate subcategories"},
            ],
            hypotheses=[
                {"hypothesis_id": "h1", "branch_id": "b1",
                 "target_file": "operators/subcat_consolidate.py",
                 "hyp": "consolidate subcategories"},
            ],
        )
        log = CampaignResearchLog(db_path)
        summaries = log.build()
        assert len(summaries) == 1
        assert summaries[0].operator_name == "subcat_consolidate"


# ---------------------------------------------------------------------------
# Test 2-4: Exhausted threshold tiered warnings
# ---------------------------------------------------------------------------

class TestResearchLogExhaustedThreshold:
    def test_no_signal_warning_at_015(self, tmp_path):
        """max_wr=0.15 — all branches rendered with low scr values (v3: no pattern warnings)."""
        db_path = str(tmp_path)
        _create_test_db(os.path.join(db_path, "scion.db"), [
            {"branch_id": f"b{i}", "stage": "screening", "wr": 0.15,
             "decision": "abandon", "file": f"operators/op{i}.py", "hyp": "test"}
            for i in range(3)
        ])
        log = CampaignResearchLog(db_path)
        rendered = log.render()
        assert "scr=0.15" in rendered
        assert "abandoned" in rendered

    def test_no_warning_at_030(self, tmp_path):
        """max_wr=0.30 — branches rendered with scr values (v3: no pattern warnings)."""
        db_path = str(tmp_path)
        _create_test_db(os.path.join(db_path, "scion.db"), [
            {"branch_id": "b1", "stage": "screening", "wr": 0.30,
             "decision": "abandon", "file": "operators/op1.py", "hyp": "test"},
            {"branch_id": "b2", "stage": "screening", "wr": 0.10,
             "decision": "abandon", "file": "operators/op2.py", "hyp": "test"},
        ])
        log = CampaignResearchLog(db_path)
        rendered = log.render()
        assert "scr=0.30" in rendered
        assert "scr=0.10" in rendered

    def test_weak_signal_at_025(self, tmp_path):
        """max_wr=0.25 — branch rendered with scr value (v3: no pattern warnings)."""
        db_path = str(tmp_path)
        _create_test_db(os.path.join(db_path, "scion.db"), [
            {"branch_id": "b1", "stage": "screening", "wr": 0.25,
             "decision": "abandon", "file": "operators/op1.py", "hyp": "test"},
        ])
        log = CampaignResearchLog(db_path)
        rendered = log.render()
        assert "scr=0.25" in rendered
        assert "abandoned" in rendered

    def test_no_warning_at_040(self, tmp_path):
        """max_wr=0.40 (>= 0.35) should not trigger any warning."""
        db_path = str(tmp_path)
        _create_test_db(os.path.join(db_path, "scion.db"), [
            {"branch_id": "b1", "stage": "screening", "wr": 0.40,
             "decision": "abandon", "file": "operators/op1.py", "hyp": "test"},
        ])
        log = CampaignResearchLog(db_path)
        rendered = log.render()
        assert "no signal" not in rendered
        assert "weak signal" not in rendered
        assert "exhausted" not in rendered


# ---------------------------------------------------------------------------
# Test 5: Saturation extract from case_features
# ---------------------------------------------------------------------------

class TestSaturationExtractFromCaseFeatures:
    def test_case_features_champion_metrics(self):
        """Generic champion_metrics case_features can seed the baseline."""
        step = _make_step_with_case_features([
            {"champion_metrics": {"primary_metric": 10.0, "secondary_metric": 50000.0}},
            {"champion_metrics": {"primary_metric": 12.0, "secondary_metric": 48000.0}},
        ])
        result = extract_champion_metrics_from_step(step)
        assert result is not None
        assert abs(result["primary_metric"] - 11.0) < 0.01
        assert abs(result["secondary_metric"] - 49000.0) < 0.01

    def test_empty_case_features_falls_through(self):
        """Empty case_features should fall through to pair_feedback path."""
        step = _make_step_with_case_features([{}, {}])
        # No pair_feedback either → should return None
        result = extract_champion_metrics_from_step(step)
        assert result is None

    def test_no_protocol_result_returns_none(self):
        """Step with no protocol_result should return None."""
        from scion.core.models import HypothesisProposal, StepRecord
        hyp = HypothesisProposal(hypothesis_text="test", change_locus="vehicle_level", action="modify")
        step = StepRecord(
            round_num=1, branch_id="b1", hypothesis=hyp, patch=None,
            contract_passed=True, verification_passed=True,
            protocol_result=None, decision=None,
            failure_stage=None, failure_detail=None,
        )
        assert extract_champion_metrics_from_step(step) is None


# ---------------------------------------------------------------------------
# Test 6: Compact display for large-scale failed screening
# ---------------------------------------------------------------------------

class TestResearchLogCompactDisplay:
    def test_compact_at_large_scale(self, tmp_path):
        """More than 20 failed screening branches — all rendered individually in v3."""
        db_path = str(tmp_path)
        rows = []
        for i in range(25):
            prefix = "subcat" if i < 8 else "order"
            rows.append({
                "branch_id": f"b{i}", "stage": "screening", "wr": 0.1 + i * 0.01,
                "decision": "abandon", "file": f"operators/{prefix}_op{i}.py",
                "hyp": "test",
            })
        _create_test_db(os.path.join(db_path, "scion.db"), rows)
        log = CampaignResearchLog(db_path)
        rendered = log.render()
        # v3: all branches rendered individually, no batch
        assert "abandoned" in rendered
        assert "subcat_op0" in rendered

    def test_normal_display_under_10(self, tmp_path):
        """10 or fewer failed screening branches should use per-branch trajectory display."""
        db_path = str(tmp_path)
        rows = [
            {"branch_id": f"b{i}", "stage": "screening", "wr": 0.2,
             "decision": "abandon", "file": f"operators/op{i}.py", "hyp": "test"}
            for i in range(5)
        ]
        _create_test_db(os.path.join(db_path, "scion.db"), rows)
        log = CampaignResearchLog(db_path)
        rendered = log.render()
        # Individual branch format with scr= prefix
        assert "scr=0.20" in rendered
        assert "abandoned" in rendered
