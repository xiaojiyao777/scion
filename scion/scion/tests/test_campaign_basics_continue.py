"""Focused tests split from test_campaign.py."""

from .campaign_test_support import *  # noqa: F401,F403

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

    def test_max_rounds_exhausted_terminalizes_active_branches(self, tmp_path):
        cm = _campaign(
            tmp_path,
            experiment_protocol=MockExperimentProtocol([
                _make_protocol_result(ExperimentStage.SCREENING, gate_outcome="pass")
            ]),
            termination_config=TerminationConfig(max_experiments=1000),
        )

        cm.run(max_rounds=1)

        state = cm.get_state()
        assert state["n_active_branches"] == 0
        assert cm._last_stop_reason == "max_rounds_exhausted"
        branch = next(iter(cm._branch_ctrl._branches.values()))
        assert branch.state == BranchState.ABANDONED
        assert "MAX_ROUNDS_EXHAUSTED" in branch.failure_codes

        status = json.loads((tmp_path / "campaign" / "status.json").read_text())
        summary = json.loads((tmp_path / "campaign" / "campaign_summary.json").read_text())
        assert status["stopped_reason"] == "max_rounds_exhausted"
        assert status["n_active_branches"] == 0
        assert summary["stopped_reason"] == "max_rounds_exhausted"
        assert summary["n_active_branches"] == 0
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
        hyp2["target_file"] = "operators/other_op.py"
        patch1 = dict(_VALID_PATCH)
        patch1["file_path"] = "operators/local_search.py"
        patch2 = dict(_VALID_PATCH)
        patch2["file_path"] = "operators/other_op.py"

        class SequencedLLM:
            def __init__(self):
                self.hyp_calls = 0
                self.patch_calls = 0
            def call(self, prompt, schema, model=None, system_blocks=None):
                if "code_content" in schema.get("required", []):
                    self.patch_calls += 1
                    return patch1 if self.patch_calls == 1 else patch2
                self.hyp_calls += 1
                return hyp1 if self.hyp_calls == 1 else hyp2
            def call_with_tool(self, prompt, tool, model=None, system_blocks=None):
                return self.call(prompt, tool.get("input_schema", {}), model, system_blocks)

        cm = _campaign(tmp_path, llm_client=SequencedLLM(), experiment_protocol=None)
        # _campaign seeds champion_code/operators/local_search.py; seed other_op.py for step 2
        (tmp_path / "champion_code" / "operators" / "other_op.py").write_text(_VALID_CODE)
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
        hyp2["target_file"] = "operators/other_op.py"
        patch1 = dict(_VALID_PATCH)
        patch1["file_path"] = "operators/local_search.py"
        patch2 = dict(_VALID_PATCH)
        patch2["file_path"] = "operators/other_op.py"

        class SequencedLLM:
            def __init__(self):
                self.hyp_calls = 0
                self.patch_calls = 0
            def call(self, prompt, schema, model=None, system_blocks=None):
                if "code_content" in schema.get("required", []):
                    self.patch_calls += 1
                    return patch1 if self.patch_calls == 1 else patch2
                self.hyp_calls += 1
                return hyp1 if self.hyp_calls == 1 else hyp2
            def call_with_tool(self, prompt, tool, model=None, system_blocks=None):
                return self.call(prompt, tool.get("input_schema", {}), model, system_blocks)

        cm = _campaign(tmp_path, llm_client=SequencedLLM(), experiment_protocol=None)
        (tmp_path / "champion_code" / "operators" / "other_op.py").write_text(_VALID_CODE)

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
