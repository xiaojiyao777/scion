"""Focused tests split from test_campaign.py."""

from .campaign_test_support import *  # noqa: F401,F403

class TestCampaignSummaryJson:
    def test_campaign_summary_json_structure(self, tmp_path):
        """run() must produce campaign_summary.json with a 'steps' array."""
        import json
        from pathlib import Path

        cm = _campaign(
            tmp_path,
            experiment_protocol=None,
            termination_config=TerminationConfig(max_experiments=1000),
        )
        cm.run(max_rounds=3)

        summary_path = Path(cm._campaign_dir) / "campaign_summary.json"
        assert summary_path.exists()
        data = json.loads(summary_path.read_text())
        assert "steps" in data
        assert isinstance(data["steps"], list)
        assert len(data["steps"]) >= 1
        step = data["steps"][0]
        assert "round" in step
        assert "branch_id" in step
        assert "decision" in step

    def test_campaign_summary_failed_step_has_archive(self, tmp_path):
        """Verification-failed steps must have code_archive_ref in summary."""
        import json
        from pathlib import Path

        cm = _campaign(
            tmp_path,
            verification_gate=AlwaysFailVerificationGate(),
            experiment_protocol=None,
            termination_config=TerminationConfig(max_experiments=1000),
        )
        cm.run(max_rounds=2)

        summary_path = Path(cm._campaign_dir) / "campaign_summary.json"
        assert summary_path.exists()
        data = json.loads(summary_path.read_text())
        assert "steps" in data
        # Steps that failed verification should have failure_stage='verification'
        failed = [s for s in data["steps"] if s.get("failure_stage") == "verification"]
        assert len(failed) >= 1
        # code_archive_ref field must exist (may be None if operators/ absent)
        for s in failed:
            assert "code_archive_ref" in s

    def test_step_record_has_archive_ref_field(self, tmp_path):
        """StepRecord must have code_archive_ref attribute."""
        from scion.core.models import StepRecord, Decision, HypothesisProposal

        hyp = HypothesisProposal(
            hypothesis_text="test",
            change_locus="local_search",
            action="modify",
        )
        sr = StepRecord(
            round_num=1,
            branch_id="br1",
            hypothesis=hyp,
            patch=None,
            contract_passed=False,
            verification_passed=False,
            protocol_result=None,
            decision=Decision.ABANDON,
            failure_stage="verification",
            failure_detail="test fail",
            code_archive_ref="/some/path",
        )
        assert sr.code_archive_ref == "/some/path"
        assert sr.cache_stats is None


class TestPromoteWeightOptimizationHook:
    def test_on_promote_runs_weight_optimization(self, tmp_path):
        """promote → weight optimization coordinator is called when enabled + runner present."""

        call_log = []

        cm, branch, _ = _setup_for_on_promote(tmp_path)
        # Attach a protocol with a runner attribute so the enabled-and-runner check passes
        protocol = MockExperimentProtocol(results=[])
        protocol.runner = object()
        cm._experiment_protocol = protocol
        # spec.parameter_search.enabled is True by default

        class FakeWeightOptCoordinator:
            def spawn_for_promoted_champion(
                self, snapshot, version, current_weights, base_weight_revision=0
            ):
                call_log.append((snapshot, version, dict(current_weights), base_weight_revision))

        cm._weight_opt_coord = FakeWeightOptCoordinator()
        cm._on_promote(branch)

        assert len(call_log) == 1, "Expected weight opt coordinator to be called once"
        assert call_log[0][1] == 2  # champion version bumps from 1 → 2

    def test_on_promote_rebuilds_operator_pool_from_registry(self, tmp_path):
        """After promote, champion.operator_pool comes from snapshot registry.yaml."""
        cm, branch, _ = _setup_for_on_promote(tmp_path, with_registry=True)
        cm._spec.parameter_search.enabled = False  # isolate: no optimizer
        cm._experiment_protocol = None

        cm._on_promote(branch)

        pool = cm._champion.operator_pool
        assert cm._champion.version == 2
        # Registry had swap + move — pool should include them
        assert "swap" in pool and "move" in pool

    def test_on_promote_transitions_promoted_branch_before_stale_marking(self, tmp_path):
        """Direct compatibility helper must not leave the promoted branch stale."""
        cm, branch, _ = _setup_for_on_promote(tmp_path)
        cm._spec.parameter_search.enabled = False
        cm._experiment_protocol = None
        sibling = cm._branch_ctrl.create_branch(cm._champion)

        cm._on_promote(branch)

        assert cm._branch_ctrl.get_branch(branch.branch_id).state == BranchState.PROMOTED
        assert cm._branch_ctrl.get_branch(sibling.branch_id).state == BranchState.STALE

    def test_promotion_store_failure_does_not_commit_side_effects(self, tmp_path):
        """Champion store failure must not install champion, stale branches, or write PROMOTE."""

        class FailingChampionStore:
            def promote(self, champion):
                raise OSError("store unavailable")

        call_log = []

        class FakeWeightOptCoordinator:
            latest_result = None

            def spawn_for_promoted_champion(
                self, snapshot, version, current_weights, base_weight_revision=0
            ):
                call_log.append(("spawn", version))

            def run_for_promoted_champion_sync(
                self, snapshot, version, current_weights, base_weight_revision=0
            ):
                call_log.append(("sync", version))

            def drain_completed_events(self):
                return []

            def status_snapshot(self):
                return {"pending_threads": 0, "active": [], "runs": []}

        cm = _campaign(tmp_path, experiment_protocol=_promote_protocol())
        cm._champion_store = FailingChampionStore()
        cm._weight_opt_coord = FakeWeightOptCoordinator()

        r1 = cm.run_one_step()
        bid = r1.branch_id
        assert bid is not None
        sibling = cm._branch_ctrl.create_branch(cm._champion)

        cm.run_one_step()
        result = cm.run_one_step()

        assert result.branch_id == bid
        assert result.decision is None
        assert "promote_commit_failed" in result.reason
        assert cm._champion.version == 1
        assert cm._branch_ctrl.get_branch(bid).state != BranchState.PROMOTED
        assert cm._branch_ctrl.get_branch(sibling.branch_id).state == BranchState.EXPLORE
        assert call_log == []

        rows = cm._registry.query_by_branch(bid)
        assert not any(row.get("decision") == "promote" for row in rows)

    def test_on_promote_without_parameter_search(self, tmp_path):
        """parameter_search.enabled=False → _run_weight_optimization is NOT called."""
        import types

        call_log = []

        def fake_run_opt(self_cm, snapshot, version):
            call_log.append(version)
            return None

        cm, branch, _ = _setup_for_on_promote(tmp_path)
        cm._spec.parameter_search.enabled = False  # type: ignore[attr-defined]
        cm._run_weight_optimization = types.MethodType(fake_run_opt, cm)

        cm._on_promote(branch)

        assert call_log == [], "_run_weight_optimization must not be called when disabled"

    def test_on_promote_without_runner(self, tmp_path):
        """experiment_protocol=None → no optimization triggered, no crash."""
        import types

        call_log = []

        def fake_run_opt(self_cm, snapshot, version):
            call_log.append(version)
            return None

        cm, branch, _ = _setup_for_on_promote(tmp_path)
        cm._experiment_protocol = None  # no runner
        cm._run_weight_optimization = types.MethodType(fake_run_opt, cm)

        cm._on_promote(branch)  # must not crash

        assert call_log == [], "_run_weight_optimization must not be called without experiment_protocol"
