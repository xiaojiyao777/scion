"""Focused tests split from test_sprint_e3.py."""

from .sprint_e3_test_support import *  # noqa: F401,F403

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
