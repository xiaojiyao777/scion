"""Focused tests split from test_campaign.py."""

import json
import shutil
from pathlib import Path

from .campaign_test_support import *  # noqa: F401,F403
from scion.core.models import HypothesisRecord, PatchFileChange
from scion.proposal.llm_client import LLMProviderError

class TestCampaignBasics:
    def test_initial_state(self, tmp_path):
        cm = _campaign(tmp_path)
        state = cm.get_state()
        assert state["n_experiments"] == 0
        assert state["n_active_branches"] == 0
        assert state["champion_version"] == 1
        assert state["proposal_runtime_mode"] == "direct_v3"
        assert "campaign_id" in state

    def test_run_writes_status_json(self, tmp_path):
        cm = _campaign(
            tmp_path,
            experiment_protocol=MockExperimentProtocol([
                _make_protocol_result(ExperimentStage.SCREENING, gate_outcome="fail")
            ]),
        )

        cm.run(requested_rounds=1)

        status_path = tmp_path / "campaign" / "status.json"
        assert status_path.exists()
        status = json.loads(status_path.read_text())
        assert status["campaign_id"] == cm.get_state()["campaign_id"]
        assert status["proposal_runtime_mode"] == "direct_v3"
        assert status["total_rounds"] >= 1
        assert "last_result" in status

    def test_requested_rounds_completed_preserves_active_branches(self, tmp_path):
        cm = _campaign(
            tmp_path,
            experiment_protocol=MockExperimentProtocol([
                _make_protocol_result(ExperimentStage.SCREENING, gate_outcome="pass")
            ]),
        )

        cm.run(requested_rounds=1)

        state = cm.get_state()
        assert state["n_active_branches"] == 1
        assert cm._last_stop_reason == "requested_rounds_completed"
        branch = next(iter(cm._branch_ctrl._branches.values()))
        assert branch.state != BranchState.ABANDONED
        assert "MAX_ROUNDS_EXHAUSTED" not in branch.failure_codes

        status = json.loads((tmp_path / "campaign" / "status.json").read_text())
        summary = json.loads((tmp_path / "campaign" / "campaign_summary.json").read_text())
        assert status["stopped_reason"] == "requested_rounds_completed"
        assert status["n_active_branches"] == 1
        assert status["branches"][0]["state"] == branch.state.value
        assert summary["stopped_reason"] == "requested_rounds_completed"
        assert summary["n_active_branches"] == 1
        assert summary["branches"][0]["state"] == branch.state.value
        assert summary["proposal_runtime_mode"] == "direct_v3"
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
        branch.branch_evidence_summary = {
            "stage": "screening",
            "tier": "marginal",
            "case_level_negative_cases": [{"case_id": "CMT4.vrp"}],
            "formal_candidate_patch_artifact_ref": (
                "artifacts/formal_candidates/8b1621af/"
                "screening-active-demand-slack-candidate/candidate.patch.json"
            ),
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
        )
        cm._hyp_store.save(active_hypothesis)
        artifact_dir = (
            tmp_path
            / "campaign"
            / "artifacts"
            / "formal_candidates"
            / "8b1621af"
            / "screening-active-demand-slack-candidate"
        )
        artifact_dir.mkdir(parents=True)
        artifact_ref = (
            "artifacts/formal_candidates/8b1621af/"
            "screening-active-demand-slack-candidate/candidate.patch.json"
        )
        (artifact_dir / "candidate.patch.json").write_text(
            json.dumps(
                {
                    "patch": {
                        "files": [
                            {
                                "file_path": (
                                    "policies/baseline_modules/destroy_repair.py"
                                ),
                                "action": "modify",
                                "code_content": "# restored destroy repair\n",
                            },
                            {
                                "file_path": "policies/baseline_algorithm.py",
                                "action": "modify",
                                "code_content": "# restored support file\n",
                            },
                        ]
                    }
                }
            ),
            encoding="utf-8",
        )
        index_dir = tmp_path / "campaign" / "artifacts" / "formal_candidates"
        (index_dir / "index.jsonl").write_text(
            json.dumps(
                {
                    "artifact_status": "recorded",
                    "artifact_ref": artifact_ref,
                    "branch_id": branch.branch_id,
                    "hypothesis_id": "active-demand-slack",
                    "stage": "screening",
                }
            )
            + "\n",
            encoding="utf-8",
        )

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
        assert restored_hypothesis.hypothesis_text == (
            "Follow demand slack regret insertion."
        )
        restored_patch = reopened._branch_patches[branch.branch_id]
        assert restored_patch.file_path == (
            "policies/baseline_modules/destroy_repair.py"
        )
        assert restored_patch.code_content == "# restored destroy repair\n"
        assert restored_patch.additional_changes == (
            PatchFileChange(
                file_path="policies/baseline_algorithm.py",
                action="modify",
                code_content="# restored support file\n",
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

    def test_final_round_leaves_validation_for_next_invocation(self, tmp_path):
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
        )

        cm.run(requested_rounds=1)

        branch = next(iter(cm._branch_ctrl._branches.values()))
        assert branch.state == BranchState.READY_VALIDATE
        status = json.loads((tmp_path / "campaign" / "status.json").read_text())
        assert status["stopped_reason"] == "requested_rounds_completed"
        assert status["effective_rounds_completed"] == 1
        assert status["protocol_stage_counts"] == {
            "screening": 1,
            "validation": 0,
            "frozen": 0,
        }
        assert "stage_transition_drain" not in status
        assert "stage_transition_drain_executed" not in status

    def test_infra_only_call_stops_immediately_and_is_marked_invalid(self, tmp_path):
        class NoAvailableAccountsLLM:
            def call(self, prompt, response_schema, model=None, system_blocks=None):
                raise LLMProviderError(
                    "Transient provider error: HTTP 503 no_available_accounts"
                )

            def call_with_tool(
                self, prompt, tool, model=None, system_blocks=None, request_kind=None
            ):
                del request_kind
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

        cm.run(requested_rounds=4)

        status = json.loads((tmp_path / "campaign" / "status.json").read_text())
        summary = json.loads((tmp_path / "campaign" / "campaign_summary.json").read_text())
        assert cm._last_stop_reason == "execution_blocked_infra"
        assert status["stopped_reason"] == "execution_blocked_infra"
        assert status["effective_rounds_completed"] == 0
        assert status["n_experiments"] == 0
        assert status["run_validity"]["status"] == "invalid"
        assert status["run_validity"]["reason"] == "invalid_infra_only"
        assert status["campaign_loop"]["failure_categories"] == {"infra": 1}
        assert status["campaign_loop"]["scheduled_calls"] == 1
        assert summary["run_validity"]["reason"] == "invalid_infra_only"
        assert summary["failure_categories"] == {"infra": 1}

    def test_should_stop_false_initially(self, tmp_path):
        cm = _campaign(tmp_path)
        assert not cm.should_stop()

    def test_external_stop_is_explicit_and_preserves_reason(self, tmp_path):
        cm = _campaign(tmp_path)

        cm.request_stop("operator_requested_stop")

        assert cm.should_stop()
        assert cm._last_stop_reason == "operator_requested_stop"
        status = json.loads((tmp_path / "campaign" / "status.json").read_text())
        assert status["stopped_reason"] == "operator_requested_stop"

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

    def test_continue_explore_retains_verified_workspace(self, tmp_path):
        """CONTINUE_EXPLORE keeps the branch's executable verified codebase."""
        cm = _campaign(tmp_path, experiment_protocol=None)
        result = cm.run_one_step()
        assert result.branch_id is not None
        bid = result.branch_id
        workspace = Path(cm._branch_workspaces[bid])
        assert workspace.is_dir()
        assert "candidate = solution" in (
            workspace / "operators" / "local_search.py"
        ).read_text()

    def test_continue_explore_clears_hypothesis(self, tmp_path):
        """After CONTINUE_EXPLORE, the branch hypothesis is cleared."""
        cm = _campaign(tmp_path, experiment_protocol=None)
        result = cm.run_one_step()
        bid = result.branch_id
        assert bid not in cm._branch_hypotheses
        assert bid not in cm._branch_current_hypothesis

    def test_continue_explore_branch_stays_in_explore(self, tmp_path):
        """Branch should remain in EXPLORE state after CONTINUE_EXPLORE."""
        cm = _campaign(tmp_path, experiment_protocol=None)
        result = cm.run_one_step()
        bid = result.branch_id
        branch = cm._branch_ctrl.get_branch(bid)
        assert branch.state == BranchState.EXPLORE

    def test_second_step_iterates_same_branch_with_screening_evidence(self, tmp_path):
        """After screening failure, the branch iterates from durable evidence.

        Uses a sequenced LLM so the two candidates have distinct targets while
        capturing the second H/C provider contexts.
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
                self.provider_calls = []
            def call(self, prompt, schema, model=None, system_blocks=None):
                if _schema_requests_patch(schema):
                    self.patch_calls += 1
                    return patch1 if self.patch_calls == 1 else patch2
                self.hyp_calls += 1
                return hyp1 if self.hyp_calls == 1 else hyp2
            def call_with_tool(
                self, prompt, tool, model=None, system_blocks=None, request_kind=None
            ):
                self.provider_calls.append(
                    {
                        "request_kind": request_kind,
                        "prompt": prompt,
                        "system_blocks": system_blocks,
                    }
                )
                return self.call(
                    prompt,
                    tool.get("input_schema", {}),
                    model,
                    system_blocks,
                )

        llm = SequencedLLM()
        cm = _campaign(
            tmp_path,
            llm_client=llm,
            experiment_protocol=MockExperimentProtocol(
                [
                    _make_protocol_result(
                        ExperimentStage.SCREENING,
                        gate_outcome="fail",
                        win_rate=0.1,
                        median_delta=-12.0,
                    ),
                    _make_protocol_result(
                        ExperimentStage.SCREENING,
                        gate_outcome="pass",
                    ),
                ]
            ),
        )
        r1 = cm.run_one_step()
        r2 = cm.run_one_step()
        assert r1.decision == Decision.CONTINUE_EXPLORE
        assert r2.decision == Decision.QUEUE_VALIDATE
        assert r1.branch_id == r2.branch_id
        assert len(cm._branch_ctrl._branches) == 1
        assert llm.hyp_calls == 2
        assert llm.patch_calls == 2

        hypothesis_calls = [
            call for call in llm.provider_calls
            if call["request_kind"] == "hypothesis"
        ]
        second_h_evidence = json.loads(
            hypothesis_calls[1]["system_blocks"][2]["text"].split("\n", 1)[1]
        )
        assert len(second_h_evidence["experiment_history"]) == 1
        prior = second_h_evidence["experiment_history"][0]
        assert prior["experiment_evidence"]["stage"] == "screening"
        prior_aggregate = prior["experiment_evidence"]["objective_outcome"][
            "aggregate"
        ]
        assert prior_aggregate["win_rate"] == 0.1
        assert prior_aggregate["median_delta"] == -12.0
        assert "candidate = solution" in second_h_evidence["branch_current_code"]

        code_calls = [
            call for call in llm.provider_calls if call["request_kind"] == "code"
        ]
        second_c_context = json.loads(
            code_calls[1]["system_blocks"][1]["text"].split("\n", 1)[1]
        )
        source_ledger = second_c_context["proposal_source_ledger"]
        prior_source = next(
            entry
            for entry in source_ledger["entries"]
            if entry["path"] == "operators/local_search.py"
        )
        assert prior_source["provenance"] == "branch_history_current"
        assert "candidate = solution" in prior_source["content"]

        workspace = Path(cm._branch_workspaces[r2.branch_id])
        assert "candidate = solution" in (
            workspace / "operators" / "local_search.py"
        ).read_text()
        assert (workspace / "operators" / "other_op.py").is_file()

    def test_reopen_iterates_same_branch_with_durable_history_and_source(self, tmp_path):
        """A process reopen preserves prior screening facts and verified code."""
        first = _campaign(
            tmp_path,
            experiment_protocol=MockExperimentProtocol(
                [
                    _make_protocol_result(
                        ExperimentStage.SCREENING,
                        gate_outcome="fail",
                        win_rate=0.1,
                        median_delta=-12.0,
                    )
                ]
            ),
        )
        r1 = first.run_one_step()
        assert r1.decision == Decision.CONTINUE_EXPLORE
        first_workspace = Path(first._branch_workspaces[r1.branch_id])
        assert "candidate = solution" in (
            first_workspace / "operators" / "local_search.py"
        ).read_text()

        hypothesis = dict(_VALID_HYPOTHESIS)
        hypothesis["action"] = "create_new"
        hypothesis["target_file"] = "operators/other_op.py"
        patch = {
            "file_path": "operators/other_op.py",
            "action": "create",
            "edit_intent": "full_file",
            "content_after": _VALID_CODE,
            "test_hint": None,
        }

        class ReopenLLM:
            def __init__(self):
                self.provider_calls = []
            def call(self, prompt, schema, model=None, system_blocks=None):
                return patch if _schema_requests_patch(schema) else hypothesis
            def call_with_tool(
                self, prompt, tool, model=None, system_blocks=None, request_kind=None
            ):
                self.provider_calls.append(
                    {
                        "request_kind": request_kind,
                        "prompt": prompt,
                        "system_blocks": system_blocks,
                    }
                )
                return self.call(
                    prompt,
                    tool.get("input_schema", {}),
                    model,
                    system_blocks,
                )

        llm = ReopenLLM()
        shutil.rmtree(tmp_path / "champion_code")
        reopened = _campaign(
            tmp_path,
            llm_client=llm,
            experiment_protocol=MockExperimentProtocol(
                [_make_protocol_result(ExperimentStage.SCREENING, gate_outcome="pass")]
            ),
        )
        assert reopened._branch_workspaces[r1.branch_id] == str(first_workspace)

        r2 = reopened.run_one_step()
        assert r2.decision == Decision.QUEUE_VALIDATE
        assert r2.branch_id == r1.branch_id
        assert len(reopened._branch_ctrl._branches) == 1

        hypothesis_call = next(
            call for call in llm.provider_calls
            if call["request_kind"] == "hypothesis"
        )
        h_evidence = json.loads(
            hypothesis_call["system_blocks"][2]["text"].split("\n", 1)[1]
        )
        assert len(h_evidence["experiment_history"]) == 1
        prior = h_evidence["experiment_history"][0]
        prior_aggregate = prior["experiment_evidence"]["objective_outcome"][
            "aggregate"
        ]
        assert prior_aggregate["median_delta"] == -12.0
        assert "candidate = solution" in h_evidence["branch_current_code"]

        code_call = next(
            call for call in llm.provider_calls if call["request_kind"] == "code"
        )
        c_context = json.loads(
            code_call["system_blocks"][1]["text"].split("\n", 1)[1]
        )
        prior_source = next(
            entry
            for entry in c_context["proposal_source_ledger"]["entries"]
            if entry["path"] == "operators/local_search.py"
        )
        assert prior_source["provenance"] == "branch_history_current"
        assert "candidate = solution" in prior_source["content"]

        workspace = Path(reopened._branch_workspaces[r2.branch_id])
        assert "candidate = solution" in (
            workspace / "operators" / "local_search.py"
        ).read_text()
        assert (workspace / "operators" / "other_op.py").is_file()

    def test_next_same_branch_candidate_starts_with_zero_expand_counters(
        self,
        tmp_path,
    ):
        """A new candidate iteration resets branch-local expand counters."""
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
            def call_with_tool(
                self, prompt, tool, model=None, system_blocks=None, request_kind=None
            ):
                del request_kind
                return self.call(prompt, tool.get("input_schema", {}), model, system_blocks)

        cm = _campaign(tmp_path, llm_client=SequencedLLM(), experiment_protocol=None)

        # First step: first hypothesis — counters start at 0
        r1 = cm.run_one_step()
        branch = cm._branch_ctrl.get_branch(r1.branch_id)
        # Simulate that the first candidate had expands happen (e.g., a prior screening expand
        # leaked from hypothesis 1's cycle, or validation expand from a prior trip)
        branch.screening_expand_count = 2
        branch.validation_expand_count = 1

        # Second step starts a fresh candidate on the same scientific branch.
        r2 = cm.run_one_step()
        assert r2.branch_id == r1.branch_id
        branch_after = cm._branch_ctrl.get_branch(r2.branch_id)
        assert branch_after.screening_expand_count == 0
        assert branch_after.validation_expand_count == 0
