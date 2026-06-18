"""Focused tests split from test_campaign.py."""

import shutil

from .campaign_test_support import *  # noqa: F401,F403
from scion.core.models import HypothesisRecord, MechanismChange
from scion.proposal.llm_client import LLMTransientProviderError

class TestCampaignBasics:
    def test_initial_state(self, tmp_path):
        cm = _campaign(tmp_path)
        state = cm.get_state()
        assert state["n_experiments"] == 0
        assert state["n_active_branches"] == 0
        assert state["champion_version"] == 1
        assert "campaign_id" in state

    def test_run_writes_status_json(self, tmp_path):
        cm = _campaign(
            tmp_path,
            experiment_protocol=MockExperimentProtocol([
                _make_protocol_result(ExperimentStage.SCREENING, gate_outcome="fail")
            ]),
        )

        cm.run(max_rounds=1)

        status_path = tmp_path / "campaign" / "status.json"
        assert status_path.exists()
        status = json.loads(status_path.read_text())
        assert status["campaign_id"] == cm.get_state()["campaign_id"]
        assert status["total_rounds"] >= 1
        assert "last_result" in status

    def test_max_rounds_exhausted_preserves_active_branches_for_resume(self, tmp_path):
        cm = _campaign(
            tmp_path,
            experiment_protocol=MockExperimentProtocol([
                _make_protocol_result(ExperimentStage.SCREENING, gate_outcome="pass")
            ]),
            termination_config=TerminationConfig(max_experiments=1000),
        )

        cm.run(max_rounds=1)

        state = cm.get_state()
        assert state["n_active_branches"] == 1
        assert cm._last_stop_reason == "max_rounds_exhausted"
        branch = next(iter(cm._branch_ctrl._branches.values()))
        assert branch.state != BranchState.ABANDONED
        assert "MAX_ROUNDS_EXHAUSTED" not in branch.failure_codes

        status = json.loads((tmp_path / "campaign" / "status.json").read_text())
        summary = json.loads((tmp_path / "campaign" / "campaign_summary.json").read_text())
        assert status["stopped_reason"] == "max_rounds_exhausted"
        assert status["n_active_branches"] == 1
        assert status["branches"][0]["state"] == branch.state.value
        assert summary["stopped_reason"] == "max_rounds_exhausted"
        assert summary["n_active_branches"] == 1
        assert summary["branches"][0]["state"] == branch.state.value
        with sqlite3.connect(tmp_path / "campaign" / "scion.db") as conn:
            row = conn.execute(
                "SELECT state, failure_codes FROM branches WHERE branch_id = ?",
                (branch.branch_id,),
            ).fetchone()
        assert row is not None
        assert row[0] == branch.state.value
        assert row[0] != BranchState.ABANDONED.value
        assert "MAX_ROUNDS_EXHAUSTED" not in (row[1] or "")
        assert summary["final_evidence_refs"]["status"] == (
            FINAL_EVIDENCE_STATUS_NON_FORMAL_CLOSED
        )
        assert summary["final_evidence_refs"]["reason_code"] == (
            FINAL_EVIDENCE_REASON_NORMAL_COMPLETION
        )
        assert summary["final_evidence_refs"]["required_for_formal_readiness"] is False
        assert summary["formal_readiness"] == {
            "formal_ready": False,
            "missing": [],
            "status": FINAL_EVIDENCE_STATUS_NON_FORMAL_CLOSED,
            "reason_code": FINAL_EVIDENCE_REASON_NORMAL_COMPLETION,
        }

    def test_reopened_campaign_restores_champion_active_branch_and_workspace(
        self, tmp_path
    ):
        cm = _campaign(tmp_path)
        branch = cm._branch_ctrl.create_branch(cm._champion)
        branch.state = BranchState.EXPLORE_EXPAND
        branch.current_code_hash = "candidate-hash"
        branch.last_clean_code_hash = "candidate-hash"
        branch.branch_mechanism_ids = ("demand_slack_regret_insertion",)
        branch.branch_evidence_summary = {
            "stage": "screening",
            "tier": "marginal",
            "case_level_negative_cases": [{"case_id": "CMT4.vrp"}],
        }
        cm._branch_store.save(branch)
        active_hypothesis = HypothesisRecord(
            hypothesis_id="active-demand-slack",
            branch_id=branch.branch_id,
            change_locus="solver_design",
            action="modify",
            status="active",
            target_file="policies/baseline_modules/destroy_repair.py",
            hypothesis_text="Follow demand slack regret insertion.",
            predicted_direction="improve",
            target_objectives=("quality",),
            protected_objectives=("runtime",),
            novelty_signature={"mechanism_id": "demand_slack_regret_insertion"},
            mechanism_changes=(
                MechanismChange(
                    id="demand_slack_regret_insertion",
                    change_type="modify",
                ),
            ),
        )
        cm._hyp_store.save(active_hypothesis)

        workspace = tmp_path / "campaign" / "workspaces" / branch.branch_id
        workspace.mkdir(parents=True)
        (workspace / "solver.py").write_text("# retained branch workspace\n")
        cm._champion_store.promote(
            ChampionState(
                version=2,
                operator_pool={},
                solver_config_hash="promoted",
                code_snapshot_path=cm._champion.code_snapshot_path,
                code_snapshot_hash="promoted-hash",
            )
        )
        shutil.rmtree(tmp_path / "champion_code")

        reopened = _campaign(tmp_path)

        assert reopened._champion.version == 2
        restored = reopened._branch_ctrl.get_branch(branch.branch_id)
        assert restored.state == BranchState.EXPLORE_EXPAND
        assert restored.branch_mechanism_ids == (
            "demand_slack_regret_insertion",
        )
        assert restored.branch_evidence_summary["tier"] == "marginal"
        assert reopened._branch_workspaces[branch.branch_id] == str(workspace)
        assert (
            reopened._branch_current_hypothesis[branch.branch_id].hypothesis_id
            == "active-demand-slack"
        )
        restored_hypothesis = reopened._branch_hypotheses[branch.branch_id]
        assert restored_hypothesis.target_file == (
            "policies/baseline_modules/destroy_repair.py"
        )
        assert restored_hypothesis.mechanism_changes == (
            MechanismChange(
                id="demand_slack_regret_insertion",
                change_type="modify",
            ),
        )
        assert reopened.get_state()["n_active_branches"] == 1

    def test_reopened_copied_campaign_reanchors_current_champion_snapshot(
        self, tmp_path
    ):
        cm = _campaign(tmp_path)
        current = cm._champion_store.get_current()
        assert current is not None

        source_root = tmp_path / "source_root"
        stale_snapshot = source_root / "champions" / "champion_v1"
        stale_snapshot.mkdir(parents=True)
        cm._champion_store._conn.execute(
            "UPDATE champions SET code_snapshot_path = ? WHERE version = 1",
            (str(stale_snapshot),),
        )
        cm._champion_store._conn.commit()
        shutil.rmtree(tmp_path / "champion_code")

        reopened = _campaign(tmp_path)

        assert reopened._champion.code_snapshot_path == str(
            tmp_path / "campaign" / "champions" / "champion_v1"
        )

    def test_final_round_queue_validate_drains_validation_without_new_proposal(self, tmp_path):
        cm = _campaign(
            tmp_path,
            experiment_protocol=MockExperimentProtocol([
                _make_protocol_result(ExperimentStage.SCREENING, gate_outcome="pass"),
                _make_protocol_result(
                    ExperimentStage.VALIDATION,
                    gate_outcome="pass",
                    win_rate=0.7,
                    ci_low=0.005,
                    ci_high=0.02,
                ),
            ]),
            termination_config=TerminationConfig(max_experiments=1000),
        )

        cm.run(max_rounds=1)

        branch = next(iter(cm._branch_ctrl._branches.values()))
        assert branch.state == BranchState.READY_FROZEN
        status = json.loads((tmp_path / "campaign" / "status.json").read_text())
        assert status["stopped_reason"] == "max_rounds_exhausted"
        assert status["effective_rounds_completed"] == 1
        assert status["proposal_attempts_consumed"] == 1
        assert status["protocol_stage_counts"] == {
            "screening": 1,
            "validation": 1,
            "frozen": 0,
        }
        assert status["stage_transition_drain_executed"] == 1
        assert status["stage_transition_drain"]["counts_toward_max_rounds"] is False
        assert status["stage_transition_drain"]["generates_new_hypothesis"] is False

    def test_infra_only_attempt_exhaustion_is_marked_invalid(self, tmp_path):
        class NoAvailableAccountsLLM:
            def call(self, prompt, response_schema, model=None, system_blocks=None):
                raise LLMTransientProviderError(
                    "Transient provider error: HTTP 503 no_available_accounts"
                )

            def call_with_tool(self, prompt, tool, model=None, system_blocks=None):
                return self.call(
                    prompt,
                    tool.get("input_schema", {}),
                    model=model,
                    system_blocks=system_blocks,
                )

        cm = _campaign(
            tmp_path,
            llm_client=NoAvailableAccountsLLM(),
            experiment_protocol=MockExperimentProtocol(
                [_make_protocol_result(ExperimentStage.SCREENING)]
            ),
        )

        cm.run(max_rounds=4)

        status = json.loads((tmp_path / "campaign" / "status.json").read_text())
        summary = json.loads((tmp_path / "campaign" / "campaign_summary.json").read_text())
        assert cm._last_stop_reason == "proposal_attempt_limit_exhausted"
        assert status["stopped_reason"] == "proposal_attempt_limit_exhausted"
        assert status["effective_rounds_completed"] == 0
        assert status["n_experiments"] == 0
        assert status["run_validity"]["status"] == "invalid"
        assert status["run_validity"]["reason"] == "invalid_infra_only"
        assert status["campaign_loop"]["failure_categories"] == {"infra": 12}
        assert summary["run_validity"]["reason"] == "invalid_infra_only"
        assert summary["failure_categories"] == {"infra": 12}

    def test_should_stop_false_initially(self, tmp_path):
        cm = _campaign(tmp_path)
        assert not cm.should_stop()

    def test_should_stop_when_max_experiments_reached(self, tmp_path):
        cm = _campaign(
            tmp_path,
            termination_config=TerminationConfig(max_experiments=0)
        )
        assert cm.should_stop()

    def test_pending_evaluation_queue_delays_early_stop(self, tmp_path):
        cm = _campaign(tmp_path)
        active = [
            Branch(
                branch_id=str(uuid.uuid4()),
                state=BranchState.READY_VALIDATE,
                base_champion_id=1,
                base_champion_hash="h",
            )
        ]
        assert cm._has_pending_evaluation(active) is True

    def test_stale_queue_delays_early_stop(self, tmp_path):
        cm = _campaign(tmp_path)
        active = [
            Branch(
                branch_id=str(uuid.uuid4()),
                state=BranchState.STALE,
                base_champion_id=1,
                base_champion_hash="h",
            )
        ]
        assert cm._has_pending_evaluation(active) is True

    def test_explore_only_queue_does_not_delay_early_stop(self, tmp_path):
        cm = _campaign(tmp_path)
        active = [
            Branch(
                branch_id=str(uuid.uuid4()),
                state=BranchState.EXPLORE,
                base_champion_id=1,
                base_champion_hash="h",
            )
        ]
        assert cm._has_pending_evaluation(active) is False

    def test_run_one_step_creates_branch(self, tmp_path):
        cm = _campaign(tmp_path, experiment_protocol=MockExperimentProtocol(
            results=[_make_protocol_result(ExperimentStage.SCREENING)]
        ))
        result = cm.run_one_step()
        assert result.branch_id is not None

    def test_get_state_after_step(self, tmp_path):
        cm = _campaign(tmp_path, experiment_protocol=MockExperimentProtocol(
            results=[_make_protocol_result(ExperimentStage.SCREENING)]
        ))
        cm.run_one_step()
        state = cm.get_state()
        assert state["n_experiments"] == 1


class TestContinueExplore:
    def test_no_protocol_produces_continue_explore(self, tmp_path):
        """Without experiment protocol, decision is CONTINUE_EXPLORE (no stats)."""
        cm = _campaign(tmp_path, experiment_protocol=None)
        result = cm.run_one_step()
        # Decision should be CONTINUE_EXPLORE because there are no stats
        assert result.decision == Decision.CONTINUE_EXPLORE

    def test_continue_explore_clears_workspace(self, tmp_path):
        """After CONTINUE_EXPLORE, the branch workspace is cleaned up."""
        cm = _campaign(tmp_path, experiment_protocol=None)
        result = cm.run_one_step()
        assert result.branch_id is not None
        bid = result.branch_id
        # Workspace should have been cleared
        assert bid not in cm._branch_workspaces

    def test_continue_explore_clears_hypothesis(self, tmp_path):
        """After CONTINUE_EXPLORE, the branch hypothesis is cleared."""
        cm = _campaign(tmp_path, experiment_protocol=None)
        result = cm.run_one_step()
        bid = result.branch_id
        assert bid not in cm._branch_hypotheses

    def test_continue_explore_branch_stays_in_explore(self, tmp_path):
        """Branch should remain in EXPLORE state after CONTINUE_EXPLORE."""
        cm = _campaign(tmp_path, experiment_protocol=None)
        result = cm.run_one_step()
        bid = result.branch_id
        branch = cm._branch_ctrl.get_branch(bid)
        assert branch.state == BranchState.EXPLORE

    def test_second_step_proposes_new_hypothesis(self, tmp_path):
        """After CONTINUE_EXPLORE, the next step generates a fresh hypothesis.

        Uses a sequenced LLM so the two steps produce different hypotheses.
        C10_novelty key for action='modify' is (locus, action, target_file), so the
        two hypotheses must differ in one of those — we vary target_file.
        """
        hyp1 = dict(_VALID_HYPOTHESIS)
        hyp1["target_file"] = "operators/local_search.py"
        hyp2 = dict(_VALID_HYPOTHESIS)
        hyp2["action"] = "create_new"
        hyp2["target_file"] = "operators/other_op.py"
        patch1 = dict(_VALID_PATCH)
        patch1["file_path"] = "operators/local_search.py"
        patch2 = {
            "file_path": "operators/other_op.py",
            "action": "create",
            "edit_intent": "full_file",
            "content_after": _VALID_CODE,
            "test_hint": None,
        }

        class SequencedLLM:
            def __init__(self):
                self.hyp_calls = 0
                self.patch_calls = 0
            def call(self, prompt, schema, model=None, system_blocks=None):
                if _schema_requests_patch(schema):
                    self.patch_calls += 1
                    return patch1 if self.patch_calls == 1 else patch2
                self.hyp_calls += 1
                return hyp1 if self.hyp_calls == 1 else hyp2
            def call_with_tool(self, prompt, tool, model=None, system_blocks=None):
                return self.call(prompt, tool.get("input_schema", {}), model, system_blocks)

        cm = _campaign(tmp_path, llm_client=SequencedLLM(), experiment_protocol=None)
        r1 = cm.run_one_step()
        r2 = cm.run_one_step()
        # Both steps should be on the same branch
        assert r1.branch_id == r2.branch_id
        # Both should be CONTINUE_EXPLORE
        assert r2.decision == Decision.CONTINUE_EXPLORE

    def test_new_hypothesis_resets_expand_counters(self, tmp_path):
        """T3: When a new hypothesis is generated on a branch (pending=None),
        screening_expand_count and validation_expand_count must reset to 0.
        Per v3 §11.5 'expand 1 次' is per-candidate, not per-branch."""
        hyp1 = dict(_VALID_HYPOTHESIS)
        hyp1["target_file"] = "operators/local_search.py"
        hyp2 = dict(_VALID_HYPOTHESIS)
        hyp2["action"] = "create_new"
        hyp2["target_file"] = "operators/other_op.py"
        patch1 = dict(_VALID_PATCH)
        patch1["file_path"] = "operators/local_search.py"
        patch2 = {
            "file_path": "operators/other_op.py",
            "action": "create",
            "edit_intent": "full_file",
            "content_after": _VALID_CODE,
            "test_hint": None,
        }

        class SequencedLLM:
            def __init__(self):
                self.hyp_calls = 0
                self.patch_calls = 0
            def call(self, prompt, schema, model=None, system_blocks=None):
                if _schema_requests_patch(schema):
                    self.patch_calls += 1
                    return patch1 if self.patch_calls == 1 else patch2
                self.hyp_calls += 1
                return hyp1 if self.hyp_calls == 1 else hyp2
            def call_with_tool(self, prompt, tool, model=None, system_blocks=None):
                return self.call(prompt, tool.get("input_schema", {}), model, system_blocks)

        cm = _campaign(tmp_path, llm_client=SequencedLLM(), experiment_protocol=None)

        # First step: first hypothesis — counters start at 0
        r1 = cm.run_one_step()
        branch = cm._branch_ctrl.get_branch(r1.branch_id)
        # Simulate that the first candidate had expands happen (e.g., a prior screening expand
        # leaked from hypothesis 1's cycle, or validation expand from a prior trip)
        branch.screening_expand_count = 2
        branch.validation_expand_count = 1

        # Second step: new hypothesis (pending is None) — counters must reset
        r2 = cm.run_one_step()
        assert r2.branch_id == r1.branch_id
        branch_after = cm._branch_ctrl.get_branch(r2.branch_id)
        assert branch_after.screening_expand_count == 0, \
            "screening_expand_count must reset on new hypothesis (v3 §11.5 per-candidate)"
        assert branch_after.validation_expand_count == 0, \
            "validation_expand_count must reset on new hypothesis (v3 §11.5 per-candidate)"
