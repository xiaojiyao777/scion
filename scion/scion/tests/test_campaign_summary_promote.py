"""Focused tests split from test_campaign.py."""

from scion.core.execution_outcome import ExecutionOutcome

from .campaign_test_support import *  # noqa: F401,F403


def _assert_single_promotion_terminal(cm, result, *, reason_code: str) -> None:
    assert result.branch_id is not None
    record = result.execution_outcome
    assert record is not None
    assert record.outcome is ExecutionOutcome.BLOCKED_INFRA
    assert record.reason_code == reason_code
    assert record.provenance["stage"] == "promotion"
    assert result.reason.startswith("promotion_failed")
    assert result.failure_stage == "promotion"
    assert result.failure_category == ExecutionOutcome.BLOCKED_INFRA.value
    assert result.decision is None
    assert result.protocol_result is None
    assert cm._branch_ctrl.get_branch(result.branch_id).state is BranchState.BLOCKED_INFRA

    step = cm._step_history[-1]
    assert step.execution_outcome is record
    assert step.failure_stage == "promotion"
    assert step.decision is None
    assert step.protocol_result is None

    outcomes = cm._registry.query_execution_outcomes(branch_id=result.branch_id)
    assert len(outcomes) == 1
    assert outcomes[0]["event_kind"] == "promotion_execution_outcome"
    assert outcomes[0]["stage"] == "promotion"
    assert outcomes[0]["outcome"] == ExecutionOutcome.BLOCKED_INFRA.value
    assert outcomes[0]["reason_code"] == reason_code


class TestCampaignSummaryJson:
    def test_campaign_summary_json_structure(self, tmp_path):
        """run() must produce campaign_summary.json with a 'steps' array."""
        import json
        from pathlib import Path

        cm = _campaign(tmp_path)
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

class TestPromoteWeightOptimizationHook:
    def test_promotion_keeps_protocol_lineage_without_dossier(self, tmp_path):
        import json

        cm = _campaign(tmp_path, experiment_protocol=_promote_protocol())

        result = _run_to_promote(cm)

        assert result.decision == Decision.PROMOTE
        assert cm._champion.version == 2
        promoted_branch = cm._branch_ctrl.get_branch(result.branch_id)
        assert promoted_branch.state == BranchState.PROMOTED
        assert not hasattr(promoted_branch, "branch_evidence_summary")

        assert not (tmp_path / "campaign" / "artifacts" / "promotions").exists()

        rows = cm._registry.query_by_branch(result.branch_id)
        promotion_rows = [
            row
            for row in rows
            if row.get("decision") == "promote"
            and row.get("event_kind") == "experiment"
        ]
        assert len(promotion_rows) == 1
        assert promotion_rows[0]["stage"] == "frozen"

        cm._write_campaign_summary()
        summary = json.loads(
            (tmp_path / "campaign" / "campaign_summary.json").read_text(
                encoding="utf-8"
            )
        )
        assert "promotion_dossier_ref" not in summary

    def test_promotion_runs_weight_optimization(self, tmp_path):
        """promote → weight optimization coordinator is called when enabled + runner present."""

        call_log = []

        cm, branch, _ = _setup_for_promotion(tmp_path)
        # Attach a protocol with a runner attribute so the enabled-and-runner check passes
        protocol = MockExperimentProtocol(results=[])
        protocol.runner = object()
        cm._experiment_protocol = protocol
        cm._problem_runtime.spec.parameter_search.enabled = True

        class FakeWeightOptCoordinator:
            def spawn_for_promoted_champion(
                self, snapshot, version, current_weights, base_weight_revision=0
            ):
                call_log.append(
                    (snapshot, version, dict(current_weights), base_weight_revision)
                )

        cm._weight_opt_coord = FakeWeightOptCoordinator()
        _promote_frozen_branch(cm, branch)

        assert len(call_log) == 1, "Expected weight opt coordinator to be called once"
        assert call_log[0][1] == 2  # champion version bumps from 1 → 2

    def test_promotion_rebuilds_operator_pool_from_registry(self, tmp_path):
        """After promote, champion.operator_pool comes from snapshot registry.yaml."""
        cm, branch, _ = _setup_for_promotion(tmp_path, with_registry=True)
        cm._problem_runtime.spec.parameter_search.enabled = False
        cm._experiment_protocol = None

        _promote_frozen_branch(cm, branch)

        pool = cm._champion.operator_pool
        assert cm._champion.version == 2
        # Registry had swap + move — pool should include them
        assert "swap" in pool and "move" in pool

    def test_promotion_transitions_promoted_branch_before_stale_marking(
        self, tmp_path
    ):
        """Promotion must not leave the promoted branch stale."""
        cm, branch, _ = _setup_for_promotion(tmp_path)
        cm._problem_runtime.spec.parameter_search.enabled = False
        cm._experiment_protocol = None
        sibling = cm._branch_ctrl.create_branch(cm._champion)

        _promote_frozen_branch(cm, branch)

        assert (
            cm._branch_ctrl.get_branch(branch.branch_id).state == BranchState.PROMOTED
        )
        assert cm._branch_ctrl.get_branch(sibling.branch_id).state == BranchState.STALE

    def test_promotion_later_hook_failure_is_one_typed_terminal(
        self, tmp_path
    ):

        cm = _campaign(tmp_path, experiment_protocol=_promote_protocol())

        def fail_commit_champion(champion):
            raise RuntimeError("memory install unavailable")

        cm._promotion_service._set_champion = fail_commit_champion

        r1 = cm.run_one_step()
        bid = r1.branch_id
        assert bid is not None
        sibling = cm._branch_ctrl.create_branch(cm._champion)

        cm.run_one_step()
        result = cm.run_one_step()

        assert result.branch_id == bid
        _assert_single_promotion_terminal(
            cm,
            result,
            reason_code="PROMOTION_FAILED",
        )
        assert cm._champion.version == 1
        assert (
            cm._branch_ctrl.get_branch(sibling.branch_id).state == BranchState.EXPLORE
        )

        rows = cm._registry.query_by_branch(bid)
        assert not any(row.get("decision") == "promote" for row in rows)
