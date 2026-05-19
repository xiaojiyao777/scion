"""Focused tests split from test_sprint_k.py."""

from .sprint_k_test_support import *  # noqa: F401,F403

class TestK3MarkAllStale:
    def _make_ctrl_with_branches(self, state_map: dict) -> BranchController:
        ctrl = BranchController()
        champion = _make_champion()
        for bid, state in state_map.items():
            b = Branch(
                branch_id=bid,
                state=state,
                base_champion_id=1,
                base_champion_hash="abc",
            )
            ctrl._branches[bid] = b
        return ctrl

    def test_frozen_testing_not_marked_stale(self):
        ctrl = self._make_ctrl_with_branches({
            "b-frozen": BranchState.FROZEN_TESTING,
        })
        affected = ctrl.mark_all_stale(new_champion_id=2)
        assert "b-frozen" not in affected
        assert ctrl._branches["b-frozen"].state == BranchState.FROZEN_TESTING

    def test_explore_is_marked_stale(self):
        ctrl = self._make_ctrl_with_branches({
            "b-explore": BranchState.EXPLORE,
        })
        affected = ctrl.mark_all_stale(new_champion_id=2)
        assert "b-explore" in affected
        assert ctrl._branches["b-explore"].state == BranchState.STALE

    def test_validating_is_marked_stale(self):
        ctrl = self._make_ctrl_with_branches({
            "b-val": BranchState.VALIDATING,
        })
        affected = ctrl.mark_all_stale(new_champion_id=2)
        assert "b-val" in affected
        assert ctrl._branches["b-val"].state == BranchState.STALE

    def test_ready_frozen_is_marked_stale(self):
        ctrl = self._make_ctrl_with_branches({
            "b-rf": BranchState.READY_FROZEN,
        })
        affected = ctrl.mark_all_stale(new_champion_id=2)
        assert "b-rf" in affected
        assert ctrl._branches["b-rf"].state == BranchState.STALE

    def test_mixed_states(self):
        ctrl = self._make_ctrl_with_branches({
            "b-frozen": BranchState.FROZEN_TESTING,
            "b-explore": BranchState.EXPLORE,
            "b-val": BranchState.VALIDATING,
        })
        affected = ctrl.mark_all_stale(new_champion_id=2)
        assert "b-frozen" not in affected
        assert "b-explore" in affected
        assert "b-val" in affected
        assert ctrl._branches["b-frozen"].state == BranchState.FROZEN_TESTING
        assert ctrl._branches["b-explore"].state == BranchState.STALE
        assert ctrl._branches["b-val"].state == BranchState.STALE

    def test_promoted_and_abandoned_not_affected(self):
        ctrl = self._make_ctrl_with_branches({
            "b-prom": BranchState.PROMOTED,
            "b-aband": BranchState.ABANDONED,
        })
        affected = ctrl.mark_all_stale(new_champion_id=2)
        assert affected == []


class TestK4ActiveHypSummary:
    def test_summarise_empty(self):
        result = _summarise_active_hypotheses([])
        assert result == "(none)"

    def test_summarise_single_with_file(self):
        h = HypothesisRecord(
            hypothesis_id="h1",
            branch_id="b1",
            change_locus="vehicle_level",
            action="modify",
            status="active",
            target_file="operators/foo.py",
        )
        result = _summarise_active_hypotheses([h])
        assert "vehicle_level/modify" in result
        assert "operators/foo.py" in result
        assert "OCCUPIED" in result

    def test_summarise_without_target_file(self):
        h = HypothesisRecord(
            hypothesis_id="h1",
            branch_id="b1",
            change_locus="order_level",
            action="create_new",
            status="active",
        )
        result = _summarise_active_hypotheses([h])
        assert "order_level/create_new" in result
        assert "OCCUPIED" in result

    def test_summarise_multiple(self):
        hs = [
            HypothesisRecord("h1", "b1", "vehicle_level", "modify", "active", "ops/a.py"),
            HypothesisRecord("h2", "b2", "order_level", "create_new", "active"),
        ]
        result = _summarise_active_hypotheses(hs)
        assert "vehicle_level" in result
        assert "order_level" in result
        lines = [l for l in result.splitlines() if l.strip()]
        assert len(lines) == 2

    def test_build_hypothesis_context_contains_occupied_key(self):
        """build_hypothesis_context returns dict with 'active_hyp_summary' key containing OCCUPIED."""
        from scion.config.problem import ProblemSpec, SearchSpace
        ctx_mgr = ContextManager()
        champion = _make_champion()
        branch = _make_branch(state=BranchState.EXPLORE)

        spec = MagicMock()
        spec.operator_categories = ["vehicle_level"]
        spec.search_space = MagicMock()
        spec.search_space.editable = ["operators/*.py"]
        spec.search_space.frozen = []
        spec.description = "test"

        active_hyps = [
            HypothesisRecord("h1", "b1", "vehicle_level", "modify", "active", "ops/a.py"),
        ]

        ctx = ctx_mgr.build_hypothesis_context(
            branch=branch,
            champion=champion,
            problem_spec=spec,
            active_hypotheses=active_hyps,
            blacklist=[],
        )

        assert "active_hyp_summary" in ctx
        assert "OCCUPIED" in ctx["active_hyp_summary"]
        assert "ops/a.py" in ctx["active_hyp_summary"]

    def test_build_hypothesis_context_empty_active(self):
        """With no active hypotheses, summary is '(none)'."""
        ctx_mgr = ContextManager()
        champion = _make_champion()
        branch = _make_branch(state=BranchState.EXPLORE)
        spec = MagicMock()
        spec.operator_categories = ["vehicle_level"]
        spec.search_space = MagicMock()
        spec.search_space.editable = ["operators/*.py"]
        spec.search_space.frozen = []
        spec.description = "test"

        ctx = ctx_mgr.build_hypothesis_context(
            branch=branch,
            champion=champion,
            problem_spec=spec,
            active_hypotheses=[],
            blacklist=[],
        )

        assert ctx["active_hyp_summary"] == "(none)"


class TestK5ContractFailure:
    def test_record_contract_failure_stored(self, tmp_path):
        from scion.lineage.registry import LineageRegistry
        db = str(tmp_path / "scion.db")
        reg = LineageRegistry(db)
        reg.record_contract_failure(
            campaign_id="c1",
            branch_id="b1",
            hypothesis_text="some text",
            change_locus="vehicle_level",
            action="modify",
            target_file="ops/foo.py",
            failure_reason="C10_novelty: duplicate",
        )
        import sqlite3
        conn = sqlite3.connect(db)
        rows = conn.execute(
            "SELECT * FROM experiment_events WHERE event_kind='contract_fail'"
        ).fetchall()
        conn.close()
        assert len(rows) == 1

    def test_record_contract_failure_fields(self, tmp_path):
        from scion.lineage.registry import LineageRegistry
        db = str(tmp_path / "scion.db")
        reg = LineageRegistry(db)
        reg.record_contract_failure(
            campaign_id="c1",
            branch_id="b42",
            hypothesis_text="X" * 600,  # should be truncated to 500
            change_locus="order_level",
            action="create_new",
            target_file=None,
            failure_reason="C2_change_locus: invalid",
        )
        import sqlite3
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM experiment_events WHERE event_kind='contract_fail' LIMIT 1"
        ).fetchone()
        conn.close()
        assert row["branch_id"] == "b42"
        assert row["campaign_id"] == "c1"
        assert len(row["hypothesis_text"]) <= 500
        assert row["contract_result"] == "failed"
        assert row["stage"] == "hypothesis_contract"
        assert row["decision"] == "abandon"

    def test_campaign_calls_record_contract_failure_on_c10_fail(self):
        """campaign.py calls registry.record_contract_failure when hypothesis contract fails."""
        bid = "b1"
        h_record = _make_h_record(bid=bid)
        harness = _make_campaign_harness(bid=bid, h_record=h_record)
        harness._branch_hypotheses = {}
        harness._pending_hypotheses = {}
        harness._round_num = 0
        harness._branch_workspaces[bid] = "/tmp/ws"
        harness._failure_streak = {}
        harness._step_history = []
        harness._hyp_store.get_by_status.return_value = []

        hyp = _make_hypothesis(text="Duplicate idea")
        h_record2 = _make_h_record(bid=bid, hid="hyp-2")

        # Contract gate returns failure
        harness._contract_gate.validate_hypothesis.return_value = ContractResult(
            passed=False, checks=(), failure_reason="C10_novelty: duplicate"
        )

        # Inject mocked round1 to return the hypothesis
        harness._round1_generate_hypothesis = MagicMock(return_value=(hyp, h_record2))
        harness._handle_failure = MagicMock()
        harness._record_step = MagicMock()
        harness._record_step_lineage = MagicMock()

        from scion.core.campaign import CampaignManager
        branch = _make_branch(state=BranchState.EXPLORE, bid=bid)
        CampaignManager._run_explore_step(harness, branch)

        harness._registry.record_contract_failure.assert_called_once()
        call_kwargs = harness._registry.record_contract_failure.call_args
        assert call_kwargs.kwargs["failure_reason"] == "C10_novelty: duplicate"
        assert call_kwargs.kwargs["branch_id"] == bid
