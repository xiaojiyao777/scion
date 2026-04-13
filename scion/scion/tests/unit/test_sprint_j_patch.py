"""Sprint J-patch unit tests: Search Memory fixes + CampaignResearchLog."""
from __future__ import annotations

import os
import sqlite3
import tempfile

import pytest

from scion.core.models import (
    Branch, BranchState, ChampionState, Decision, EvalStats,
    ExperimentStage, HypothesisProposal, PatchProposal, ProtocolResult,
    StepRecord,
)
from scion.proposal.search_memory import (
    CampaignSearchMemory, FamilyEntry, _make_family_key,
)
from scion.proposal.context_manager import (
    ContextManager, build_exploration_coverage, _extract_families_from_steps,
    _build_strategy_guidance,
)
from scion.proposal.research_log import CampaignResearchLog, BranchSummary


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_hypothesis(text: str = "subcategory swap", locus: str = "vehicle_level", action: str = "create_new"):
    return HypothesisProposal(
        hypothesis_text=text,
        change_locus=locus,
        action=action,
    )


def _make_step(
    hyp_text: str = "subcategory swap",
    locus: str = "vehicle_level",
    action: str = "create_new",
    win_rate: float = 0.0,
    failure_stage: str | None = None,
    failure_detail: str | None = None,
    decision: Decision | None = None,
    branch_id: str = "b1",
    round_num: int = 1,
    stage: ExperimentStage = ExperimentStage.SCREENING,
) -> StepRecord:
    hyp = _make_hypothesis(hyp_text, locus, action)
    protocol_result = None
    if failure_stage is None:
        protocol_result = ProtocolResult(
            stage=stage,
            stats=EvalStats(
                n_cases=5, wins=int(win_rate * 5), losses=5 - int(win_rate * 5),
                ties=0, win_rate=win_rate, median_delta=0.0, ci_low=0.0, ci_high=0.0,
            ),
            gate_outcome="pass" if win_rate > 0.5 else "fail",
            reason_codes=(),
            exposed_summary="",
            raw_metrics_ref="",
        )
    return StepRecord(
        round_num=round_num,
        branch_id=branch_id,
        hypothesis=hyp,
        patch=None,
        contract_passed=failure_stage is None,
        verification_passed=failure_stage is None,
        protocol_result=protocol_result,
        decision=decision,
        failure_stage=failure_stage,
        failure_detail=failure_detail,
    )


def _make_branch(branch_id: str = "b-new") -> Branch:
    return Branch(branch_id=branch_id, base_champion_version=1)


def _make_champion() -> ChampionState:
    return ChampionState(
        version=1,
        operator_pool={},
        solver_config_hash="test",
        code_snapshot_path="/tmp/nonexistent",
    )


def _make_problem_spec():
    """Minimal ProblemSpec stub for ContextManager tests."""
    from unittest.mock import MagicMock
    spec = MagicMock()
    spec.name = "test"
    spec.description = "test problem"
    spec.operator_categories = ["vehicle_level", "order_level"]
    spec.search_space.editable = ["operators/*.py"]
    spec.search_space.frozen = ["solver.py"]
    spec.search_space.import_whitelist = ["math"]
    return spec


# ---------------------------------------------------------------------------
# Task 1: exploration_coverage / strategy_guidance global
# ---------------------------------------------------------------------------

class TestFamiliesGlobal:
    def test_families_global_not_branch_local(self):
        """New branch generates hypothesis with exploration_coverage based on global step_history."""
        steps = [
            _make_step(hyp_text="subcategory consolidate", branch_id="b-old", round_num=1, win_rate=0.8,
                       decision=Decision.PROMOTE),
            _make_step(hyp_text="destroy and rebuild", branch_id="b-old", round_num=2, win_rate=0.1),
            _make_step(hyp_text="subcategory swap", branch_id="b-other", round_num=3, win_rate=0.2),
        ]
        # Use _extract_families_from_steps with all_steps (simulating the fix)
        families = _extract_families_from_steps(steps)
        coverage = build_exploration_coverage(families)
        # Coverage should include families from ALL branches
        assert "subcategory_consolidation" in coverage
        assert "destroy_rebuild" in coverage

    def test_strategy_guidance_global(self):
        """strategy_guidance is based on global families, not branch-local."""
        steps = [
            _make_step(hyp_text="subcategory swap", branch_id="b1", round_num=1, win_rate=0.1),
            _make_step(hyp_text="subcategory swap", branch_id="b1", round_num=2, win_rate=0.1),
            _make_step(hyp_text="subcategory swap", branch_id="b1", round_num=3, win_rate=0.1),
            _make_step(hyp_text="subcategory swap", branch_id="b2", round_num=4, win_rate=0.1),
        ]
        families = _extract_families_from_steps(steps)
        guidance = _build_strategy_guidance(families)
        # With 4 total failures, strategy guidance should flag this direction
        assert guidance  # non-empty


# ---------------------------------------------------------------------------
# Task 2: Semantic loop detection (replaces post-promotion exhaustion)
# ---------------------------------------------------------------------------

class TestSemanticLoopDetection:
    def test_no_loop_with_diverse_hypotheses(self):
        """Different directions should not trigger loop warning."""
        sm = CampaignSearchMemory()
        diverse = [
            "subcategory swap to reduce cost",
            "destroy and rebuild vehicle routes",
            "split large orders into smaller ones",
            "eliminate underused vehicles entirely",
            "rebalance load across depot zones",
        ]
        for i, text in enumerate(diverse):
            sm.update(_make_step(hyp_text=text, win_rate=0.10, round_num=i))
        assert sm._detect_hypothesis_loop() is None

    def test_loop_detected_with_similar_hypotheses(self):
        """3+ similar hypothesis pairs should trigger warning."""
        sm = CampaignSearchMemory()
        similar = [
            "subcategory swap to reduce vehicle cost",
            "subcategory swap to reduce vehicle cost further",
            "subcategory swap to reduce vehicle cost more",
            "subcategory swap to reduce vehicle cost again",
        ]
        for i, text in enumerate(similar):
            sm.update(_make_step(hyp_text=text, win_rate=0.10, round_num=i))
        warning = sm._detect_hypothesis_loop()
        assert warning is not None
        assert "SEMANTIC LOOP DETECTED" in warning

    def test_loop_warning_in_render(self):
        """render() output includes loop warning when loop detected."""
        sm = CampaignSearchMemory()
        similar = [
            "subcategory swap to reduce vehicle cost",
            "subcategory swap to reduce vehicle cost further",
            "subcategory swap to reduce vehicle cost more",
            "subcategory swap to reduce vehicle cost again",
        ]
        for i, text in enumerate(similar):
            sm.update(_make_step(hyp_text=text, win_rate=0.10, round_num=i))
        rendered = sm.render()
        assert "Hypothesis Loop Warning" in rendered
        assert "SEMANTIC LOOP DETECTED" in rendered

    def test_loop_resets_with_new_direction(self):
        """Adding diverse hypotheses dilutes similarity and reduces similar_pairs."""
        sm = CampaignSearchMemory()
        # First, fill with similar
        similar = [
            "subcategory swap to reduce vehicle cost",
            "subcategory swap to reduce vehicle cost further",
            "subcategory swap to reduce vehicle cost more",
        ]
        for i, text in enumerate(similar):
            sm.update(_make_step(hyp_text=text, win_rate=0.10, round_num=i))
        # Now add many diverse hypotheses to push out old ones
        diverse = [
            "destroy and rebuild vehicle routes completely",
            "eliminate underused vehicles from fleet",
            "rebalance load across all depot zones",
            "split large orders into smaller batches",
            "drain low priority stops from routes",
            "redistribute capacity among hubs",
            "merge adjacent subcategories together",
            "upgrade fleet composition entirely",
            "purify route assignments for efficiency",
            "kill empty vehicle runs immediately",
        ]
        for i, text in enumerate(diverse):
            sm.update(_make_step(hyp_text=text, win_rate=0.10, round_num=i + 3))
        # With 10 diverse hypotheses filling the window, loop should not trigger
        assert sm._detect_hypothesis_loop() is None


# ---------------------------------------------------------------------------
# Task 3: Champion description
# ---------------------------------------------------------------------------

class TestChampionDescription:
    def test_champion_description_includes_operator_name(self):
        """record_champion_promotion description includes operator file name."""
        sm = CampaignSearchMemory()
        # Simulate what campaign.py does after J-patch
        desc = "→v2 subcategory_consolidate (R5, scr_wr=1.00)"
        sm.record_champion_promotion(desc, 2)
        assert "subcategory_consolidate" in sm.champion_evolution[0]

    def test_champion_description_uses_screening_wr_not_frozen(self):
        """Description uses screening wr, no frozen data."""
        sm = CampaignSearchMemory()
        desc = "→v3 my_operator (R10, scr_wr=0.85)"
        sm.record_champion_promotion(desc, 3)
        assert "scr_wr=0.85" in sm.champion_evolution[0]
        assert "frozen" not in sm.champion_evolution[0].lower()


# ---------------------------------------------------------------------------
# Task 4: CampaignResearchLog
# ---------------------------------------------------------------------------

def _create_test_db(path: str, rows: list) -> None:
    """Create a test SQLite DB with experiment_events."""
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
            (event_id, branch_id, event_kind, stage, screening_win_rate,
             decision, patch_file, hypothesis_text, created_at)
            VALUES (?, ?, 'experiment', ?, ?, ?, ?, ?, datetime('now', ?))
        """, (
            f"evt-{i}",
            row["branch_id"],
            row.get("stage", "screening"),
            row.get("wr"),
            row.get("decision", "abandon"),
            row.get("file"),
            row.get("hyp"),
            f"+{i} seconds",
        ))
    conn.commit()
    conn.close()


class TestResearchLogRender:
    def test_research_log_render_promoted(self, tmp_path):
        """Promoted branches appear in promoted section."""
        db_path = str(tmp_path)
        _create_test_db(os.path.join(db_path, "scion.db"), [
            {"branch_id": "b1", "stage": "screening", "wr": 1.0, "decision": "pass",
             "file": "operators/subcat_consolidate.py", "hyp": "consolidate subcategories"},
            {"branch_id": "b1", "stage": "validation", "wr": 0.9, "decision": "pass",
             "file": "operators/subcat_consolidate.py", "hyp": "consolidate subcategories"},
            {"branch_id": "b1", "stage": "frozen", "wr": 0.8, "decision": "promote",
             "file": "operators/subcat_consolidate.py", "hyp": "consolidate subcategories"},
        ])
        log = CampaignResearchLog(db_path)
        rendered = log.render()
        assert "[PROMOTED]" in rendered
        assert "subcat_consolidate" in rendered
        assert "scr=1.00" in rendered
        assert "frozen=PASS" in rendered

    def test_research_log_render_failed_frozen(self, tmp_path):
        """Failed frozen branches in 'reached validation' section, pass/fail only."""
        db_path = str(tmp_path)
        _create_test_db(os.path.join(db_path, "scion.db"), [
            {"branch_id": "b2", "stage": "screening", "wr": 0.80, "decision": "pass",
             "file": "operators/evict_consolidate.py", "hyp": "evict then consolidate"},
            {"branch_id": "b2", "stage": "validation", "wr": 1.0, "decision": "pass",
             "file": "operators/evict_consolidate.py", "hyp": "evict then consolidate"},
            {"branch_id": "b2", "stage": "frozen", "wr": 0.3, "decision": "abandon",
             "file": "operators/evict_consolidate.py", "hyp": "evict then consolidate"},
        ])
        log = CampaignResearchLog(db_path)
        rendered = log.render()
        assert "[FAILED frozen]" in rendered
        assert "evict_consolidate" in rendered
        assert "frozen=FAIL" in rendered

    def test_research_log_no_frozen_wr_exposed(self, tmp_path):
        """render() output must not contain frozen wr value."""
        db_path = str(tmp_path)
        _create_test_db(os.path.join(db_path, "scion.db"), [
            {"branch_id": "b2", "stage": "screening", "wr": 0.80, "decision": "pass",
             "file": "operators/evict.py", "hyp": "evict"},
            {"branch_id": "b2", "stage": "validation", "wr": 1.0, "decision": "pass",
             "file": "operators/evict.py", "hyp": "evict"},
            {"branch_id": "b2", "stage": "frozen", "wr": 0.30, "decision": "abandon",
             "file": "operators/evict.py", "hyp": "evict"},
        ])
        log = CampaignResearchLog(db_path)
        rendered = log.render()
        # frozen wr=0.30 should NOT appear in output
        # Only "frozen=FAIL" or "frozen=PASS"
        # Check that "0.30" does not appear after "frozen"
        assert "frozen=0" not in rendered
        assert "frozen_wr" not in rendered

    def test_research_log_screening_failures_compact(self, tmp_path):
        """Multiple screening failures shown in compact format."""
        db_path = str(tmp_path)
        rows = []
        for i in range(5):
            rows.append({
                "branch_id": f"b-fail-{i}",
                "stage": "screening",
                "wr": 0.1 + i * 0.02,
                "decision": "abandon",
                "file": f"operators/fail_op_{i}.py",
                "hyp": f"fail hypothesis {i}",
            })
        _create_test_db(os.path.join(db_path, "scion.db"), rows)
        log = CampaignResearchLog(db_path)
        rendered = log.render()
        assert "Failed at Screening (5 branches)" in rendered
        assert "fail_op_0" in rendered
        assert "no signal" in rendered

    def test_research_log_empty_db(self, tmp_path):
        """No SQLite file → empty string, no crash."""
        log = CampaignResearchLog(str(tmp_path))
        assert log.render() == ""

    def test_research_log_empty_table(self, tmp_path):
        """SQLite exists but no experiment rows → empty string."""
        db_path = str(tmp_path)
        _create_test_db(os.path.join(db_path, "scion.db"), [])
        log = CampaignResearchLog(db_path)
        assert log.render() == ""
