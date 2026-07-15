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
        )
        cm.run(requested_rounds=3)

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
        )
        cm.run(requested_rounds=2)

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
    def test_promotion_writes_compact_dossier_with_stage_and_code_refs(self, tmp_path):
        import json
        from pathlib import Path

        cm = _campaign(tmp_path, experiment_protocol=_promote_protocol())

        result = _run_to_promote(cm)

        assert result.decision == Decision.PROMOTE
        promoted_branch = cm._branch_ctrl.get_branch(result.branch_id)
        evidence = promoted_branch.branch_evidence_summary
        assert evidence["stage"] == evidence["protocol_stage"] == "frozen"
        assert evidence["latest_protocol_evidence"]["stage"] == "frozen"
        assert "why_not_promoted_reason_codes" not in evidence
        assert set(evidence["protocol_evidence_by_stage"]) == {
            "screening",
            "validation",
            "frozen",
        }
        dossier_ref = cm._champion.promotion_dossier_ref
        assert dossier_ref == "artifacts/promotions/champion_v2_promotion_dossier.json"
        dossier_path = Path(cm._campaign_dir) / dossier_ref
        assert dossier_path.exists()

        dossier = json.loads(dossier_path.read_text(encoding="utf-8"))
        assert dossier["schema_version"] == "scion.promotion_dossier.v1"
        assert dossier["campaign_id"] == cm._campaign_id
        assert dossier["champion_version"] == 2
        assert (
            dossier["promotion_experiment_id"] == cm._champion.promotion_experiment_id
        )
        assert dossier["branch_id"] == result.branch_id
        assert dossier["hypothesis_id"]
        assert dossier["base_champion_version"] == 1

        stage_refs = dossier["stage_chain_refs"]
        assert set(stage_refs) == {"screening", "validation", "frozen"}
        assert all(stage_refs[stage]["raw_metrics_ref"] for stage in stage_refs)
        assert stage_refs["screening"]["gate_outcome"] == "pass"
        assert stage_refs["validation"]["gate_outcome"] == "pass"
        assert stage_refs["frozen"]["gate_outcome"] == "pass"

        assert dossier["metric_artifact_refs"]["screening"]
        assert dossier["metric_artifact_refs"]["validation"]
        assert dossier["metric_artifact_refs"]["frozen"]
        assert dossier["code_snapshot_hash"] == cm._champion.code_snapshot_hash
        assert dossier["code_hash"]
        assert dossier["patch_hash"]
        assert dossier["champion_snapshot"]["ref"]
        assert dossier["champion_snapshot"]["hash"] == cm._champion.code_snapshot_hash
        assert dossier["decision_reason_codes"]
        assert dossier["runtime_evidence_summary"]["status"] == "sufficient"

        persisted = cm._champion_store.get_by_version(2)
        assert persisted is not None
        assert persisted.promotion_dossier_ref == dossier_ref

        cm._write_campaign_summary()
        summary_path = Path(cm._campaign_dir) / "campaign_summary.json"
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        assert summary["promotion_dossier_ref"] == dossier_ref

    def test_on_promote_runs_weight_optimization(self, tmp_path):
        """promote → weight optimization coordinator is called when enabled + runner present."""

        call_log = []

        cm, branch, _ = _setup_for_on_promote(tmp_path)
        # Attach a protocol with a runner attribute so the enabled-and-runner check passes
        protocol = MockExperimentProtocol(results=[])
        protocol.runner = object()
        cm._experiment_protocol = protocol
        cm._spec.parameter_search.enabled = True

        class FakeWeightOptCoordinator:
            def spawn_for_promoted_champion(
                self, snapshot, version, current_weights, base_weight_revision=0
            ):
                call_log.append(
                    (snapshot, version, dict(current_weights), base_weight_revision)
                )

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

    def test_on_promote_transitions_promoted_branch_before_stale_marking(
        self, tmp_path
    ):
        """Direct compatibility helper must not leave the promoted branch stale."""
        cm, branch, _ = _setup_for_on_promote(tmp_path)
        cm._spec.parameter_search.enabled = False
        cm._experiment_protocol = None
        sibling = cm._branch_ctrl.create_branch(cm._champion)

        cm._on_promote(branch)

        assert (
            cm._branch_ctrl.get_branch(branch.branch_id).state == BranchState.PROMOTED
        )
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
        assert (
            cm._branch_ctrl.get_branch(sibling.branch_id).state == BranchState.EXPLORE
        )
        assert call_log == []

        rows = cm._registry.query_by_branch(bid)
        assert not any(row.get("decision") == "promote" for row in rows)

    def test_promotion_later_hook_failure_reports_recoverable_advancement(
        self, tmp_path
    ):
        """After durable champion persistence, hook failures stay promotion-aware."""

        cm = _campaign(tmp_path, experiment_protocol=_promote_protocol())

        def fail_commit_champion(champion):
            raise RuntimeError("memory install unavailable")

        cm._promotion_service._commit_champion = fail_commit_champion

        r1 = cm.run_one_step()
        bid = r1.branch_id
        assert bid is not None
        sibling = cm._branch_ctrl.create_branch(cm._champion)

        cm.run_one_step()
        result = cm.run_one_step()

        assert result.branch_id == bid
        assert result.decision == Decision.PROMOTE
        assert result.reason.startswith("promotion_commit_recovery_pending")
        assert result.failure_category == "promotion_recovery"
        assert cm._champion.version == 1
        assert cm._champion_store.get_by_version(2) is not None
        promoted = cm._champion_store.get_by_version(2)
        assert promoted is not None
        assert promoted.promotion_experiment_id
        assert cm._branch_ctrl.get_branch(bid).state == BranchState.FROZEN_TESTING
        assert (
            cm._branch_ctrl.get_branch(sibling.branch_id).state == BranchState.EXPLORE
        )

        marker = cm._branch_ctrl.get_branch(bid).branch_evidence_summary[
            "promotion_integrity"
        ]
        assert marker["status"] == "recovery_pending"
        assert marker["failed_phase"] == "commit_champion"
        assert marker["lineage_status"] == "recorded"
        assert marker["promotion_event_id"] == promoted.promotion_experiment_id

        rows = cm._registry.query_by_branch(bid)
        assert any(
            row.get("event_id") == promoted.promotion_experiment_id
            and row.get("decision") == "promote"
            for row in rows
        )

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

        assert (
            call_log == []
        ), "_run_weight_optimization must not be called when disabled"

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

        assert (
            call_log == []
        ), "_run_weight_optimization must not be called without experiment_protocol"
