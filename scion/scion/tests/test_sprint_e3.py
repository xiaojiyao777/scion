"""Sprint E3 tests — T06, T09, T10, T25, T23, T24."""
from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest

from scion.core.models import (
    Decision, EvalStats, ExperimentStage, HypothesisProposal,
    PairwiseCaseFeedback, CaseAggregateFeedback,
    ProtocolResult, StepRecord, VerificationResult, CheckResult,
)
from scion.core.stagnation import StagnationDetector, StagnationSignal, CampaignDiagnosis


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_hypothesis(text: str = "test hypothesis", locus: str = "vehicle_level") -> HypothesisProposal:
    return HypothesisProposal(
        hypothesis_text=text,
        change_locus=locus,
        action="modify",
        target_file="operators/test.py",
        predicted_direction="improve",
        target_weakness="slow",
        expected_effect="faster",
    )


def _make_step(
    round_num: int = 1,
    branch_id: str = "branch1",
    decision: Decision = Decision.ABANDON,
    failure_stage: Optional[str] = None,
    failure_detail: Optional[str] = None,
    protocol_result: Optional[ProtocolResult] = None,
    hypothesis_text: str = "test hypothesis",
    verification_detail: Optional[str] = None,
    code_archive_ref: Optional[str] = None,
    cache_stats: Optional[Dict] = None,
) -> StepRecord:
    return StepRecord(
        round_num=round_num,
        branch_id=branch_id,
        hypothesis=_make_hypothesis(text=hypothesis_text),
        patch=None,
        contract_passed=failure_stage not in ("hypothesis_contract", "patch_contract"),
        verification_passed=failure_stage != "verification",
        protocol_result=protocol_result,
        decision=decision,
        failure_stage=failure_stage,
        failure_detail=failure_detail,
        verification_detail=verification_detail,
        code_archive_ref=code_archive_ref,
        cache_stats=cache_stats,
    )


def _make_protocol_result(gate_outcome: str = "pass", win_rate: float = 0.7) -> ProtocolResult:
    stats = EvalStats(
        n_cases=6, wins=4, losses=2, ties=0,
        win_rate=win_rate, median_delta=0.01,
        ci_low=0.005, ci_high=0.02,
    )
    return ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=stats,
        gate_outcome=gate_outcome,
        reason_codes=("TEST",),
        exposed_summary="test",
        raw_metrics_ref="/tmp/test.json",
    )


# ---------------------------------------------------------------------------
# T06: Observability fields in campaign summary
# ---------------------------------------------------------------------------

class TestT06ObservabilityFields:
    """T06: campaign_summary.json must contain new observability fields."""

    def _build_mock_campaign(self, tmp_path: Path):
        """Build a minimal CampaignManager with mock steps to test summary writing."""
        from scion.config.problem import ProblemSpec, ProtocolConfig, SplitManifest, SeedLedgerConfig, SearchSpace
        from scion.core.campaign import CampaignManager
        from scion.core.models import ChampionState
        from scion.proposal.mock_client import MockLLMClient

        op_dir = tmp_path / "operators"
        op_dir.mkdir()
        (op_dir / "local_search.py").write_text("class LocalSearch: pass\n")

        spec = ProblemSpec(
            name="test",
            root_dir=str(tmp_path),
            operator_categories=["local_search"],
            search_space=SearchSpace(
                editable=["operators/*.py"],
                frozen=["solver.py"],
                import_whitelist=["random"],
            ),
        )
        champion = ChampionState(
            version=1, operator_pool={}, solver_config_hash="abc",
            code_snapshot_path=str(tmp_path), code_snapshot_hash="xyz",
        )
        mgr = CampaignManager(
            problem_spec=spec,
            protocol_config=ProtocolConfig(),
            split_manifest=SplitManifest(screening=[], validation=[], frozen=[]),
            seed_ledger=SeedLedgerConfig(screening=[1], validation=[2], frozen=[3]),
            llm_client=MockLLMClient(mode="success"),
            champion=champion,
            campaign_dir=str(tmp_path),
        )
        return mgr

    def test_summary_contains_observability_fields(self, tmp_path):
        mgr = self._build_mock_campaign(tmp_path)

        # Inject some synthetic step history
        mgr._step_history = [
            _make_step(
                round_num=1,
                failure_stage="verification",
                failure_detail="V8_nondeterminism: uuid used",
                cache_stats={"total": 1000, "cache_read": 300, "cache_create": 700},
                hypothesis_text="subcategory consolidation via merging vehicles",
            ),
            _make_step(
                round_num=2,
                decision=Decision.QUEUE_VALIDATE,
                protocol_result=_make_protocol_result("pass", 0.75),
                cache_stats={"total": 1200, "cache_read": 600, "cache_create": 600},
                hypothesis_text="destroy rebuild approach",
            ),
        ]
        mgr._budget.used = 5
        mgr._budget.total = 20

        mgr._write_campaign_summary()

        summary_path = tmp_path / "campaign_summary.json"
        assert summary_path.exists(), "campaign_summary.json not written"
        summary = json.loads(summary_path.read_text())

        # Top-level observability fields
        assert "cache_stats" in summary, "Missing cache_stats"
        assert "verification_failure_breakdown" in summary, "Missing verification_failure_breakdown"
        assert "action_locus_coverage" in summary, "Missing action_locus_coverage"
        assert "family_coverage" in summary, "Missing family_coverage"
        assert "budget_utilization" in summary, "Missing budget_utilization"
        assert "stagnation_signals" in summary, "Missing stagnation_signals"
        assert "diagnostics" in summary, "Missing diagnostics"

        # Cache stats correctness
        cs = summary["cache_stats"]
        assert cs["total_tokens"] == 2200
        assert cs["cache_read_tokens"] == 900
        assert cs["cache_hit_rate"] == pytest.approx(900 / 2200, abs=1e-4)

        # Budget utilization
        assert summary["budget_utilization"] == pytest.approx(5 / 20, abs=1e-4)

        # Verification failure breakdown has entry
        assert "V8_nondeterminism" in summary["verification_failure_breakdown"]

        # Family coverage (mechanism label from hypothesis text)
        assert len(summary["family_coverage"]) > 0

    def test_failed_code_archived_in_steps(self, tmp_path):
        """Steps with code_archive_ref show public archive refs in summary."""
        mgr = self._build_mock_campaign(tmp_path)
        mgr._step_history = [
            _make_step(
                round_num=1,
                failure_stage="verification",
                failure_detail="V1_syntax: bad syntax",
                code_archive_ref="/tmp/archive/round_1_abc12345",
            ),
        ]
        mgr._write_campaign_summary()
        summary = json.loads((tmp_path / "campaign_summary.json").read_text())
        step = summary["steps"][0]
        assert not step["code_archive_ref"].startswith("/")
        assert "round_1_abc12345" in step["code_archive_ref"]
        assert step["verification_detail"] is None  # no verification_detail was set


# ---------------------------------------------------------------------------
# T09: Richer case feedback wording
# ---------------------------------------------------------------------------

class TestT09RicherCaseFeedback:
    """T09: _render_case_feedback must produce richer, directional output."""

    def _make_case_feedback(
        self,
        case_id: str = "scr_l01",
        dominant_result: str = "win",
        dominant_decisive_objective: str = "business_aggregation",
        median_delta_subcategory_splits: Optional[float] = -5.0,
        median_delta_total_cost: Optional[float] = 1000.0,
        case_features: Optional[Dict] = None,
    ) -> CaseAggregateFeedback:
        median_deltas = {}
        if median_delta_subcategory_splits is not None:
            median_deltas["subcategory_splits"] = median_delta_subcategory_splits
        if median_delta_total_cost is not None:
            median_deltas["total_cost"] = median_delta_total_cost
        return CaseAggregateFeedback(
            case_id=case_id,
            n_pairs=6,
            wins=4,
            losses=2,
            ties=0,
            win_rate=0.67,
            dominant_result=dominant_result,
            decisive_metric=dominant_decisive_objective,
            median_deltas=median_deltas,
            seed_consistency=0.67,
            case_features=case_features or {"size_bucket": "large", "n_orders": 150},
            # Deprecated aliases
            dominant_decisive_objective=dominant_decisive_objective,
            median_delta_total_cost=median_delta_total_cost,
            median_delta_subcategory_splits=median_delta_subcategory_splits,
        )

    def test_feedback_includes_decisive_objective(self):
        from scion.proposal.context_manager import _render_case_feedback
        cf = self._make_case_feedback()
        result = _render_case_feedback(cf)
        assert "Decisive:" in result

    def test_feedback_shows_directional_change_win(self):
        from scion.proposal.context_manager import _render_case_feedback
        cf = self._make_case_feedback(
            dominant_result="win",
            dominant_decisive_objective="subcategory_splits",
            median_delta_subcategory_splits=22.0,
        )
        result = _render_case_feedback(cf)
        assert "↓" in result or "22" in result

    def test_feedback_shows_directional_change_loss(self):
        from scion.proposal.context_manager import _render_case_feedback
        # splits_delta negative → candidate worse (more splits) → up arrow
        cf = self._make_case_feedback(
            dominant_result="loss",
            dominant_decisive_objective="business_aggregation",
            median_delta_subcategory_splits=-2.0,  # negative = candidate worse
        )
        result = _render_case_feedback(cf)
        # Should show ↑ (candidate increased splits)
        assert "↑" in result or "2.0" in result

    def test_feedback_shows_champion_baseline(self):
        from scion.proposal.context_manager import _render_case_feedback
        cf = self._make_case_feedback(
            case_features={"size_bucket": "large", "n_orders": 150, "champion_splits": 40}
        )
        result = _render_case_feedback(cf)
        assert "Champion baseline" in result or "40" in result

    def test_feedback_shows_result_label(self):
        from scion.proposal.context_manager import _render_case_feedback
        for result_str in ["win", "loss", "mixed"]:
            cf = self._make_case_feedback(dominant_result=result_str)
            rendered = _render_case_feedback(cf)
            assert result_str.upper() in rendered


# ---------------------------------------------------------------------------
# T10: Champion baseline hints
# ---------------------------------------------------------------------------

class TestT10ChampionBaselines:
    """T10: hypothesis context includes champion baseline hints."""

    def _make_pair_feedback(self, case_id: str, seed: int, champ_splits: float) -> PairwiseCaseFeedback:
        from scion.problem.objectives import ObjectiveComparison, MetricComparison
        oc = ObjectiveComparison(
            outcome="win", decisive_metric="subcategory_splits", scalar_delta=15000.0,
            metrics=(
                MetricComparison(name="subcategory_splits", candidate_value=champ_splits - 5,
                                 champion_value=champ_splits, signed_delta=5.0,
                                 relation="candidate", decisive=True),
                MetricComparison(name="total_cost", candidate_value=50000,
                                 champion_value=60000, signed_delta=10000.0,
                                 relation="candidate"),
            ),
        )
        return PairwiseCaseFeedback(
            case_id=case_id,
            seed=seed,
            comparison="win",
            delta=100.0,
            objective_comparison=oc,
            case_features={"size_bucket": "large"},
        )

    def _make_case_feedback(self, case_id: str) -> CaseAggregateFeedback:
        return CaseAggregateFeedback(
            case_id=case_id,
            n_pairs=1,
            wins=1,
            losses=0,
            ties=0,
            win_rate=1.0,
            dominant_result="win",
            decisive_metric="total_cost",
            median_deltas={"total_cost": 10.0},
            seed_consistency=1.0,
            case_features={"size_bucket": "secret", "champion_metrics": {"total_cost": 50}},
        )

    def _make_screening_step_with_pairs(self) -> StepRecord:
        pairs = (
            self._make_pair_feedback("scr_s01", 42, 8.0),
            self._make_pair_feedback("scr_s01", 43, 9.0),
            self._make_pair_feedback("scr_l01", 42, 17.0),
            self._make_pair_feedback("scr_x01", 42, 95.0),
        )
        stats = EvalStats(
            n_cases=3, wins=3, losses=0, ties=0,
            win_rate=1.0, median_delta=5.0, ci_low=3.0, ci_high=7.0,
        )
        pr = ProtocolResult(
            stage=ExperimentStage.SCREENING,
            stats=stats,
            gate_outcome="pass",
            reason_codes=("T",),
            exposed_summary="ok",
            raw_metrics_ref="/tmp/x.json",
            pair_feedback=pairs,
        )
        return _make_step(protocol_result=pr)

    def test_baseline_hints_present_when_data_exists(self):
        from scion.proposal.context_manager import _build_champion_baselines
        steps = [self._make_screening_step_with_pairs()]
        result = _build_champion_baselines(steps)
        assert "Champion Performance" in result
        assert "scr_s01" in result
        assert "scr_l01" in result

    def test_baseline_hints_absent_when_no_data(self):
        from scion.proposal.context_manager import _build_champion_baselines
        # No steps at all
        result = _build_champion_baselines([])
        assert result == ""

    def test_baseline_hints_absent_no_pair_feedback(self):
        from scion.proposal.context_manager import _build_champion_baselines
        # Step with no pair_feedback
        step = _make_step(protocol_result=_make_protocol_result())
        result = _build_champion_baselines([step])
        assert result == ""

    def test_baseline_hints_ignore_validation_and_frozen_feedback(self):
        from scion.proposal.context_manager import _build_champion_baselines

        stats = EvalStats(
            n_cases=1, wins=1, losses=0, ties=0,
            win_rate=1.0, median_delta=1.0, ci_low=1.0, ci_high=1.0,
        )
        screening = ProtocolResult(
            stage=ExperimentStage.SCREENING,
            stats=stats,
            gate_outcome="pass",
            reason_codes=("screening",),
            exposed_summary="screening summary",
            raw_metrics_ref="/tmp/screening.json",
            pair_feedback=(self._make_pair_feedback("screening-visible-case", 1, 7.0),),
            case_feedback=(self._make_case_feedback("screening-visible-aggregate"),),
        )
        validation = ProtocolResult(
            stage=ExperimentStage.VALIDATION,
            stats=stats,
            gate_outcome="pass",
            reason_codes=("validation",),
            exposed_summary="validation private summary",
            raw_metrics_ref="/tmp/private-validation.json",
            case_ids=("validation-secret-case-id",),
            seed_set=(11,),
            pair_feedback=(self._make_pair_feedback("validation-secret-pair", 2, 77.0),),
            case_feedback=(self._make_case_feedback("validation-secret-case"),),
        )
        frozen = ProtocolResult(
            stage=ExperimentStage.FROZEN,
            stats=stats,
            gate_outcome="fail",
            reason_codes=("frozen",),
            exposed_summary="frozen private summary",
            raw_metrics_ref="/tmp/private-frozen.json",
            case_ids=("frozen-secret-case-id",),
            seed_set=(13,),
            pair_feedback=(self._make_pair_feedback("frozen-secret-pair", 3, 88.0),),
            case_feedback=(self._make_case_feedback("frozen-secret-case"),),
        )

        result = _build_champion_baselines([
            _make_step(round_num=1, protocol_result=screening),
            _make_step(round_num=2, protocol_result=validation),
            _make_step(round_num=3, protocol_result=frozen),
        ])

        assert "screening-visible-case" in result
        assert "validation-secret" not in result
        assert "frozen-secret" not in result
        assert "77.0" not in result
        assert "88.0" not in result

    def test_hypothesis_context_champion_baselines_ignore_holdout_feedback(self):
        from scion.config.problem import ProblemSpec, SearchSpace
        from scion.core.models import Branch, BranchState, ChampionState
        from scion.proposal.context_manager import ContextManager
        from scion.proposal.engine import _split_hypothesis_context

        stats = EvalStats(
            n_cases=1, wins=1, losses=0, ties=0,
            win_rate=1.0, median_delta=1.0, ci_low=1.0, ci_high=1.0,
        )
        screening = ProtocolResult(
            stage=ExperimentStage.SCREENING,
            stats=stats,
            gate_outcome="pass",
            reason_codes=("screening",),
            exposed_summary="screening summary",
            raw_metrics_ref="/tmp/screening.json",
            pair_feedback=(self._make_pair_feedback("screening-visible-case", 1, 7.0),),
        )
        validation = ProtocolResult(
            stage=ExperimentStage.VALIDATION,
            stats=stats,
            gate_outcome="pass",
            reason_codes=("validation",),
            exposed_summary="validation private summary",
            raw_metrics_ref="/tmp/private-validation.json",
            case_ids=("validation-secret-case-id",),
            seed_set=(11,),
            pair_feedback=(self._make_pair_feedback("validation-secret-pair", 2, 77.0),),
            case_feedback=(self._make_case_feedback("validation-secret-case"),),
        )
        frozen = ProtocolResult(
            stage=ExperimentStage.FROZEN,
            stats=stats,
            gate_outcome="fail",
            reason_codes=("frozen",),
            exposed_summary="frozen private summary",
            raw_metrics_ref="/tmp/private-frozen.json",
            case_ids=("frozen-secret-case-id",),
            seed_set=(13,),
            pair_feedback=(self._make_pair_feedback("frozen-secret-pair", 3, 88.0),),
            case_feedback=(self._make_case_feedback("frozen-secret-case"),),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            op_dir = os.path.join(tmpdir, "operators")
            os.makedirs(op_dir)
            with open(os.path.join(op_dir, "dummy.py"), "w", encoding="utf-8") as fh:
                fh.write("class Dummy: pass\n")

            spec = ProblemSpec(
                name="test",
                root_dir=tmpdir,
                operator_categories=["ls"],
                search_space=SearchSpace(
                    editable=["operators/*.py"],
                    frozen=[],
                    import_whitelist=[],
                ),
            )
            champion = ChampionState(
                version=1,
                operator_pool={},
                solver_config_hash="x",
                code_snapshot_path=tmpdir,
                code_snapshot_hash="y",
            )
            branch = Branch(
                branch_id="b1",
                state=BranchState.EXPLORE,
                base_champion_id=1,
                base_champion_hash="x",
            )
            ctx = ContextManager().build_hypothesis_context(
                branch=branch,
                champion=champion,
                problem_spec=spec,
                active_hypotheses=[],
                blacklist=[],
                step_history=[
                    _make_step(round_num=1, protocol_result=screening),
                    _make_step(round_num=2, protocol_result=validation),
                    _make_step(round_num=3, protocol_result=frozen),
                ],
            )
            system_blocks, user_prompt = _split_hypothesis_context(ctx)
            prompt_text = "\n".join(block["text"] for block in system_blocks) + user_prompt

        assert "screening-visible-case" in prompt_text
        assert "validation-secret" not in prompt_text
        assert "frozen-secret" not in prompt_text
        assert "private-validation" not in prompt_text
        assert "private-frozen" not in prompt_text

    def test_hypothesis_context_memory_and_log_ignore_holdout_aggregates(self):
        from scion.config.problem import ProblemSpec, SearchSpace
        from scion.core.models import Branch, BranchState, ChampionState
        from scion.proposal.context_manager import ContextManager
        from scion.proposal.engine import _split_hypothesis_context
        from scion.proposal.research_log import CampaignResearchLog
        from scion.proposal.search_memory import CampaignSearchMemory

        def protocol(stage: ExperimentStage, win_rate: float, gate: str) -> ProtocolResult:
            return ProtocolResult(
                stage=stage,
                stats=EvalStats(
                    n_cases=5, wins=int(win_rate * 5), losses=5 - int(win_rate * 5),
                    ties=0, win_rate=win_rate, median_delta=123.0,
                    ci_low=0.0, ci_high=1.0,
                ),
                gate_outcome=gate,
                reason_codes=(stage.value,),
                exposed_summary=f"{stage.value} private summary",
                raw_metrics_ref=f"/tmp/{stage.value}-private.json",
            )

        screening = protocol(ExperimentStage.SCREENING, 0.25, "continue")
        validation = protocol(ExperimentStage.VALIDATION, 0.95, "pass")
        frozen = protocol(ExperimentStage.FROZEN, 0.88, "pass")
        promoted_hyp = "PROMOTED_SECRET_HYPOTHESIS_TEXT"
        screening_visible_hyp = "SCREENING_MEMORY_VISIBLE_TEXT"
        screening_visible = protocol(ExperimentStage.SCREENING, 0.35, "continue")
        steps = [
            _make_step(
                round_num=1,
                branch_id="promoted-branch",
                protocol_result=screening,
                hypothesis_text=promoted_hyp,
            ),
            _make_step(
                round_num=2,
                branch_id="promoted-branch",
                protocol_result=validation,
                hypothesis_text=promoted_hyp,
            ),
            _make_step(
                round_num=3,
                branch_id="promoted-branch",
                decision=Decision.PROMOTE,
                protocol_result=frozen,
                hypothesis_text=promoted_hyp,
            ),
            _make_step(
                round_num=4,
                branch_id="screening-branch",
                protocol_result=screening_visible,
                hypothesis_text=screening_visible_hyp,
            ),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            op_dir = os.path.join(tmpdir, "operators")
            os.makedirs(op_dir)
            with open(os.path.join(op_dir, "dummy.py"), "w", encoding="utf-8") as fh:
                fh.write("class Dummy: pass\n")

            conn = sqlite3.connect(os.path.join(tmpdir, "scion.db"))
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
                CREATE TABLE hypotheses (
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
            for idx, row in enumerate([
                ("promoted-branch", "screening", 0.25, "continue", promoted_hyp),
                ("promoted-branch", "validation", 0.95, "pass", promoted_hyp),
                ("promoted-branch", "frozen", 0.88, "promote", promoted_hyp),
                ("screening-branch", "screening", 0.35, "continue", screening_visible_hyp),
            ]):
                conn.execute("""
                    INSERT INTO experiment_events
                    (event_id, branch_id, stage, screening_win_rate,
                     screening_median_delta, decision, patch_file, hypothesis_text, created_at)
                    VALUES (?, ?, ?, ?, 123.0, ?, 'operators/dummy.py',
                            ?, datetime('now', ?))
                """, (f"evt-{idx}", row[0], row[1], row[2], row[3], row[4], f"+{idx} seconds"))
            conn.commit()
            conn.close()

            search_memory = CampaignSearchMemory()
            for step in steps:
                search_memory.update(step)
            search_memory.record_champion_promotion(
                "champion_evolution promotion PROMOTED_SECRET_OPERATOR",
                2,
            )

            spec = ProblemSpec(
                name="test",
                root_dir=tmpdir,
                operator_categories=["vehicle_level"],
                search_space=SearchSpace(
                    editable=["operators/*.py"],
                    frozen=[],
                    import_whitelist=[],
                ),
            )
            champion = ChampionState(
                version=1,
                operator_pool={},
                solver_config_hash="x",
                code_snapshot_path=tmpdir,
                code_snapshot_hash="y",
                promoted_at="PROMOTED_AT_SECRET",
            )
            branch = Branch(
                branch_id="screening-branch",
                state=BranchState.EXPLORE,
                base_champion_id=1,
                base_champion_hash="x",
            )
            ctx = ContextManager().build_hypothesis_context(
                branch=branch,
                champion=champion,
                problem_spec=spec,
                active_hypotheses=[],
                blacklist=[],
                step_history=steps,
                search_memory=search_memory,
                research_log=CampaignResearchLog(tmpdir),
            )
            system_blocks, user_prompt = _split_hypothesis_context(ctx)
            prompt_text = "\n".join(block["text"] for block in system_blocks) + user_prompt

        assert "SCREENING_MEMORY_VISIBLE_TEXT" in prompt_text
        assert "scr=0.35" in prompt_text or "wr=0.35" in prompt_text
        assert "PROMOTED_SECRET_HYPOTHESIS_TEXT" not in prompt_text
        assert "PROMOTED_SECRET_OPERATOR" not in prompt_text
        assert "PROMOTED_AT_SECRET" not in prompt_text
        assert "champion_evolution" not in prompt_text
        assert "promotion" not in prompt_text.lower()
        assert "promoted" not in prompt_text.lower()
        assert "scr=0.25" not in prompt_text
        assert "wr=0.25" not in prompt_text
        assert "0.95" not in prompt_text
        assert "0.88" not in prompt_text
        assert "val=" not in prompt_text
        assert "validation:" not in prompt_text
        assert "frozen: PASS" not in prompt_text
        assert "failed_validation" not in prompt_text
        assert "failed_frozen" not in prompt_text

    def test_baseline_context_key_present(self):
        """build_hypothesis_context includes 'champion_baselines' key."""
        from scion.proposal.context_manager import ContextManager
        from scion.core.models import Branch, BranchState, ChampionState
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmpdir:
            op_dir = os.path.join(tmpdir, "operators")
            os.makedirs(op_dir)
            open(os.path.join(op_dir, "dummy.py"), "w").write("class Dummy: pass\n")

            from scion.config.problem import ProblemSpec, SearchSpace
            spec = ProblemSpec(
                name="test", root_dir=tmpdir,
                operator_categories=["ls"],
                search_space=SearchSpace(editable=["operators/*.py"], frozen=[], import_whitelist=[]),
            )
            champion = ChampionState(
                version=1, operator_pool={}, solver_config_hash="x",
                code_snapshot_path=tmpdir, code_snapshot_hash="y",
            )
            branch = Branch(
                branch_id="b1", state=BranchState.EXPLORE,
                base_champion_id=1, base_champion_hash="x",
            )
            ctx_mgr = ContextManager()
            ctx = ctx_mgr.build_hypothesis_context(
                branch=branch, champion=champion,
                problem_spec=spec, active_hypotheses=[],
                blacklist=[], step_history=[],
            )
            assert "champion_baselines" in ctx


# ---------------------------------------------------------------------------
# T25: StagnationDetector
# ---------------------------------------------------------------------------

class TestT25StagnationDetector:
    """T25: StagnationDetector detects collapse, oscillation, plateau, timeout."""

    def test_no_signal_when_healthy(self):
        detector = StagnationDetector(window_size=5)
        # Use different mechanisms and varying win rates to avoid plateau/oscillation
        texts = [
            "subcategory consolidation via merging vehicles",
            "destroy rebuild approach completely",
            "order swap between vehicles",
            "cost reduction by downsizing vehicle type",
            "rebalance loads across vehicles",
        ]
        steps = [
            _make_step(round_num=i, decision=Decision.QUEUE_VALIDATE,
                       protocol_result=_make_protocol_result("pass", 0.5 + i * 0.1),
                       hypothesis_text=texts[i])
            for i in range(5)
        ]
        signals = detector.check(steps)
        assert signals == []

    def test_detects_collapse(self):
        detector = StagnationDetector()
        steps = [
            _make_step(round_num=i, failure_stage="verification", failure_detail="V1_syntax: err")
            for i in range(4)
        ]
        signals = detector.check(steps)
        kinds = {s.kind for s in signals}
        assert "collapse" in kinds

    def test_collapse_severity_critical_at_5(self):
        detector = StagnationDetector()
        steps = [
            _make_step(round_num=i, failure_stage="verification", failure_detail="V1_syntax: err")
            for i in range(6)
        ]
        signals = detector.check(steps)
        collapse_signals = [s for s in signals if s.kind == "collapse"]
        assert any(s.severity == "critical" for s in collapse_signals)

    def test_detects_oscillation(self):
        detector = StagnationDetector(window_size=6)
        # Alternating pass/fail pattern
        steps = []
        for i in range(6):
            if i % 2 == 0:
                steps.append(_make_step(round_num=i, decision=Decision.QUEUE_VALIDATE,
                                        protocol_result=_make_protocol_result("pass", 0.7)))
            else:
                steps.append(_make_step(round_num=i, decision=Decision.ABANDON,
                                        protocol_result=_make_protocol_result("fail", 0.3)))
        signals = detector.check(steps)
        kinds = {s.kind for s in signals}
        assert "oscillation" in kinds

    def test_no_oscillation_with_few_steps(self):
        detector = StagnationDetector()
        steps = [_make_step(round_num=1)]
        signals = detector.check(steps)
        assert not any(s.kind == "oscillation" for s in signals)

    def test_detects_timeout_cascade(self):
        detector = StagnationDetector()
        steps = [
            _make_step(round_num=i, failure_stage="screening", failure_detail="timeout: process killed")
            for i in range(3)
        ]
        signals = detector.check(steps)
        kinds = {s.kind for s in signals}
        assert "timeout_cascade" in kinds

    def test_empty_history(self):
        detector = StagnationDetector()
        assert detector.check([]) == []

    def test_signals_have_required_fields(self):
        detector = StagnationDetector()
        steps = [
            _make_step(round_num=i, failure_stage="verification", failure_detail="V1_syntax: x")
            for i in range(4)
        ]
        signals = detector.check(steps)
        for sig in signals:
            assert sig.kind in ("oscillation", "plateau", "collapse", "timeout_cascade")
            assert sig.severity in ("warning", "critical")
            assert isinstance(sig.detail, str)
            assert isinstance(sig.suggested_action, str)


# ---------------------------------------------------------------------------
# T23: Campaign Mid-Stage Diagnosis
# ---------------------------------------------------------------------------

class TestT23CampaignDiagnosis:
    """T23: diagnose() returns CampaignDiagnosis on critical stagnation."""

    def test_diagnosis_generated_on_stagnation(self):
        detector = StagnationDetector()
        steps = [
            _make_step(
                round_num=i,
                failure_stage="verification",
                failure_detail="V8_nondeterminism: uuid",
                hypothesis_text="subcategory consolidation merging",
            )
            for i in range(6)
        ]
        diag = detector.diagnose(round_num=6, step_history=steps)
        assert diag is not None
        assert isinstance(diag, CampaignDiagnosis)

    def test_diagnosis_format(self):
        detector = StagnationDetector()
        steps = [
            _make_step(
                round_num=i,
                failure_stage="verification",
                failure_detail="V6_feasibility: assignment mismatch",
                hypothesis_text="destroy rebuild approach",
            )
            for i in range(5)
        ]
        diag = detector.diagnose(round_num=5, step_history=steps)
        assert diag is not None
        assert diag.round_num == 5
        assert isinstance(diag.signals, list)
        assert isinstance(diag.family_distribution, dict)
        assert isinstance(diag.failure_pattern, dict)
        assert diag.recommendation in (
            "diversify_locus", "switch_action", "check_environment", "increase_screening_n"
        )

    def test_no_diagnosis_when_healthy(self):
        detector = StagnationDetector()
        steps = [
            _make_step(round_num=i, decision=Decision.QUEUE_VALIDATE,
                       protocol_result=_make_protocol_result("pass", 0.75))
            for i in range(3)
        ]
        diag = detector.diagnose(round_num=3, step_history=steps)
        assert diag is None

    def test_signals_in_summary(self, tmp_path):
        """Stagnation signals appear in campaign_summary.json."""
        from scion.config.problem import ProblemSpec, ProtocolConfig, SplitManifest, SeedLedgerConfig, SearchSpace
        from scion.core.campaign import CampaignManager
        from scion.core.models import ChampionState
        from scion.proposal.mock_client import MockLLMClient

        op_dir = tmp_path / "operators"
        op_dir.mkdir()
        (op_dir / "local_search.py").write_text("class LocalSearch: pass\n")

        spec = ProblemSpec(
            name="test", root_dir=str(tmp_path),
            operator_categories=["ls"],
            search_space=SearchSpace(editable=["operators/*.py"], frozen=[], import_whitelist=[]),
        )
        champion = ChampionState(
            version=1, operator_pool={}, solver_config_hash="abc",
            code_snapshot_path=str(tmp_path), code_snapshot_hash="xyz",
        )
        mgr = CampaignManager(
            problem_spec=spec, protocol_config=ProtocolConfig(),
            split_manifest=SplitManifest(screening=[], validation=[], frozen=[]),
            seed_ledger=SeedLedgerConfig(screening=[1], validation=[2], frozen=[3]),
            llm_client=MockLLMClient(mode="success"),
            champion=champion,
            campaign_dir=str(tmp_path),
        )
        # Inject collapse-inducing steps and manually trigger stagnation check
        mgr._step_history = [
            _make_step(round_num=i, failure_stage="verification", failure_detail="V1_syntax: err")
            for i in range(5)
        ]
        mgr._run_stagnation_check()
        mgr._write_campaign_summary()

        summary = json.loads((tmp_path / "campaign_summary.json").read_text())
        assert "stagnation_signals" in summary
        assert len(summary["stagnation_signals"]) > 0
        assert any(s["kind"] == "collapse" for s in summary["stagnation_signals"])


# ---------------------------------------------------------------------------
# T24: scion postmortem CLI
# ---------------------------------------------------------------------------

class TestT24PostmortemCLI:
    """T24: scion postmortem command generates markdown report."""

    def _make_summary(self, tmp_path: Path) -> Path:
        summary = {
            "campaign_id": "test-campaign-123",
            "total_rounds": 10,
            "champion_version": 2,
            "cache_stats": {
                "total_tokens": 5000,
                "cache_read_tokens": 2000,
                "cache_create_tokens": 3000,
                "cache_hit_rate": 0.4,
            },
            "verification_failure_breakdown": {"V8_nondeterminism": 3, "V6_feasibility": 1},
            "action_locus_coverage": {"modify/vehicle_level": 5, "create_new/order_level": 3},
            "family_coverage": {"subcategory_consolidation": 6, "destroy_rebuild": 2},
            "budget_utilization": 0.25,
            "stagnation_signals": [
                {
                    "kind": "collapse",
                    "severity": "critical",
                    "detail": "5 consecutive hard failures",
                    "suggested_action": "check_environment",
                }
            ],
            "diagnostics": [
                {
                    "round_num": 8,
                    "recommendation": "check_environment",
                    "family_distribution": {"subcategory_consolidation": 4},
                    "failure_pattern": {"verification": 3},
                    "signals": [],
                }
            ],
            "steps": [
                {
                    "round": 1,
                    "branch_id": "abc",
                    "decision": "promote",
                    "contract_passed": True,
                    "verification_passed": True,
                    "failure_stage": None,
                    "failure_detail": None,
                    "hypothesis": {
                        "text": "Merge subcategory vehicles",
                        "action": "modify",
                        "change_locus": "vehicle_level",
                        "target_file": "operators/merge.py",
                    },
                    "protocol_result": {"stage": "screening", "win_rate": 0.83, "gate_outcome": "pass"},
                },
                {
                    "round": 2,
                    "branch_id": "abc",
                    "decision": "abandon",
                    "contract_passed": True,
                    "verification_passed": False,
                    "failure_stage": "verification",
                    "failure_detail": "V8_nondeterminism: uuid",
                    "hypothesis": {
                        "text": "Try destroy-rebuild",
                        "action": "create_new",
                        "change_locus": "order_level",
                        "target_file": None,
                    },
                    "protocol_result": None,
                },
            ],
        }
        summary_file = tmp_path / "campaign_summary.json"
        summary_file.write_text(json.dumps(summary, indent=2))
        return summary_file

    def test_postmortem_cli_runs(self, tmp_path):
        from typer.testing import CliRunner
        from scion.cli.main import app

        self._make_summary(tmp_path)
        runner = CliRunner()
        result = runner.invoke(app, ["postmortem", str(tmp_path)])
        assert result.exit_code == 0, f"CLI failed: {result.output}"
        assert "Postmortem" in result.output or "Campaign Summary" in result.output

    def test_postmortem_output_format(self, tmp_path):
        from typer.testing import CliRunner
        from scion.cli.main import app

        self._make_summary(tmp_path)
        runner = CliRunner()
        result = runner.invoke(app, ["postmortem", str(tmp_path)])
        output = result.output

        # Check required sections
        assert "Campaign Summary" in output
        assert "Family Distribution" in output or "family" in output.lower()
        assert "Failure" in output
        assert "Stagnation" in output or "stagnation" in output.lower()
        assert "Recommendations" in output or "recommendation" in output.lower()

    def test_postmortem_output_file(self, tmp_path):
        from typer.testing import CliRunner
        from scion.cli.main import app

        self._make_summary(tmp_path)
        out_file = tmp_path / "report.md"
        runner = CliRunner()
        result = runner.invoke(app, ["postmortem", str(tmp_path), "--output", str(out_file)])
        assert result.exit_code == 0
        assert out_file.exists()
        content = out_file.read_text()
        assert "Campaign Summary" in content

    def test_postmortem_missing_summary(self, tmp_path):
        from typer.testing import CliRunner
        from scion.cli.main import app

        runner = CliRunner()
        result = runner.invoke(app, ["postmortem", str(tmp_path)])
        assert result.exit_code != 0
        assert "ERROR" in result.output or "not found" in result.output
