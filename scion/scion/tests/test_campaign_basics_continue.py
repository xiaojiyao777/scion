"""Focused tests split from test_campaign.py."""

import json
from pathlib import Path

from scion.core.code_research_limits import CodeResearchLimits
from scion.core.resource_envelope import ResourceEnvelope
from scion.core.scheduler import Scheduler
from scion.proposal.llm_client import LLMProviderError

from .campaign_test_support import *  # noqa: F401,F403


class TestCampaignBasics:
    def test_initial_state(self, tmp_path):
        cm = _campaign(tmp_path)
        state = cm.get_state()
        assert state["n_experiments"] == 0
        assert state["n_active_branches"] == 0
        assert state["champion_version"] == 1
        assert state["proposal_runtime_mode"] == "direct_v3"
        assert "proposal_runtime" not in state
        assert "campaign_id" in state

    def test_run_writes_status_json(self, tmp_path):
        cm = _campaign(
            tmp_path,
            experiment_protocol=MockExperimentProtocol(
                [_make_protocol_result(ExperimentStage.SCREENING, gate_outcome="fail")]
            ),
        )

        cm.run(requested_rounds=1)

        status_path = tmp_path / "campaign" / "status.json"
        assert status_path.exists()
        status = json.loads(status_path.read_text())
        assert status["campaign_id"] == cm.get_state()["campaign_id"]
        assert status["proposal_runtime_mode"] == "direct_v3"
        assert "proposal_runtime" not in status
        assert status["total_rounds"] >= 1
        assert "last_result" in status

    def test_requested_rounds_completed_preserves_active_branches(self, tmp_path):
        cm = _campaign(
            tmp_path,
            experiment_protocol=MockExperimentProtocol(
                [_make_protocol_result(ExperimentStage.SCREENING, gate_outcome="pass")]
            ),
        )

        cm.run(requested_rounds=1)

        state = cm.get_state()
        assert state["n_active_branches"] == 1
        assert cm._last_stop_reason == "requested_rounds_completed"
        branch = next(iter(cm._branch_ctrl._branches.values()))
        assert branch.state != BranchState.ABANDONED
        assert "MAX_ROUNDS_EXHAUSTED" not in branch.failure_codes

        status = json.loads((tmp_path / "campaign" / "status.json").read_text())
        summary = json.loads(
            (tmp_path / "campaign" / "campaign_summary.json").read_text()
        )
        assert status["run_result"]["stop_reason"] == "requested_rounds_completed"
        assert status["n_active_branches"] == 1
        assert status["branches"][0]["state"] == branch.state.value
        assert summary["run_result"] == status["run_result"]
        assert summary["n_active_branches"] == 1
        assert summary["branches"][0]["state"] == branch.state.value
        assert status["proposal_runtime_mode"] == "direct_v3"
        assert summary["proposal_runtime_mode"] == "direct_v3"
        assert "proposal_runtime" not in status
        assert "proposal_runtime" not in summary
        assert "formal_candidate_artifact_count" not in summary
        assert not (tmp_path / "campaign" / "artifacts" / "formal_candidates").exists()
        assert "final_evidence_refs" not in summary
        assert "formal_readiness" not in summary

    def test_final_round_leaves_validation_for_next_invocation(self, tmp_path):
        cm = _campaign(
            tmp_path,
            experiment_protocol=MockExperimentProtocol(
                [
                    _make_protocol_result(
                        ExperimentStage.SCREENING, gate_outcome="pass"
                    ),
                    _make_protocol_result(
                        ExperimentStage.VALIDATION,
                        gate_outcome="pass",
                        win_rate=0.7,
                        ci_low=0.005,
                        ci_high=0.02,
                    ),
                ]
            ),
        )

        cm.run(requested_rounds=1)

        branch = next(iter(cm._branch_ctrl._branches.values()))
        assert branch.state == BranchState.READY_VALIDATE
        status = json.loads((tmp_path / "campaign" / "status.json").read_text())
        run_result = status["run_result"]
        assert run_result["stop_reason"] == "requested_rounds_completed"
        assert run_result["evaluated_rounds"] == 1
        assert run_result["protocol_stage_counts"] == {
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
        summary = json.loads(
            (tmp_path / "campaign" / "campaign_summary.json").read_text()
        )
        assert cm._last_stop_reason == "execution_blocked_infra"
        run_result = status["run_result"]
        assert run_result["stop_reason"] == "execution_blocked_infra"
        assert run_result["evaluated_rounds"] == 0
        assert status["n_experiments"] == 0
        assert run_result["run_validity"] == {
            "status": "invalid",
            "reason": "invalid_no_evaluated_outcome",
            "valid": False,
        }
        assert run_result["failure_categories"] == {"blocked_infra": 1}
        assert run_result["scheduled_calls"] == 1
        assert summary["run_result"] == run_result

    def test_bounded_provider_failure_projects_one_terminal_runtime_snapshot(
        self,
        tmp_path,
    ):
        class FailingBoundedLLM:
            model = "fake-bounded-model"

            def call_with_tool(
                self,
                prompt,
                tool,
                model=None,
                system_blocks=None,
                request_kind=None,
            ):
                del prompt, tool, model, system_blocks, request_kind
                raise LLMProviderError("bounded provider failure")

        cm = _campaign(
            tmp_path,
            llm_client=FailingBoundedLLM(),
            code_research_limits=CodeResearchLimits(max_turns=1),
            resource_envelope=ResourceEnvelope(provider_call_cap=2),
        )

        result = cm.run(requested_rounds=1)

        state = cm.get_state(run_result=result)
        status = json.loads((tmp_path / "campaign" / "status.json").read_text())
        summary = json.loads(
            (tmp_path / "campaign" / "campaign_summary.json").read_text()
        )
        expected_runtime = {
            "provider_calls": {
                "budget_admitted": 1,
                "cap": 2,
                "remaining": 1,
                "by_request_kind": {
                    "hypothesis": 0,
                    "hypothesis_research_turn": 1,
                    "code": 0,
                    "code_research_turn": 0,
                    "code_research_finalize": 0,
                    "other": 0,
                },
            }
        }
        assert result.stop_reason == "execution_blocked_infra"
        assert state["proposal_runtime_mode"] == "bounded_research_v1"
        assert status["proposal_runtime_mode"] == "bounded_research_v1"
        assert summary["proposal_runtime_mode"] == "bounded_research_v1"
        assert state["proposal_runtime"] == expected_runtime
        assert status["proposal_runtime"] == expected_runtime
        assert summary["proposal_runtime"] == expected_runtime

    def test_should_stop_false_initially(self, tmp_path):
        cm = _campaign(tmp_path)
        assert not cm.should_stop()

    def test_external_stop_is_explicit_and_preserves_reason(self, tmp_path):
        cm = _campaign(tmp_path)

        cm.request_stop("operator_requested_stop")

        assert cm.should_stop()
        assert cm._last_stop_reason == "operator_requested_stop"
        status_path = tmp_path / "campaign" / "status.json"
        assert not status_path.exists()

        terminal = cm.run(requested_rounds=1)

        assert terminal.stop_reason == "operator_requested_stop"
        status = json.loads(status_path.read_text())
        assert status["run_result"]["stop_reason"] == "operator_requested_stop"

    def test_run_one_step_creates_branch(self, tmp_path):
        cm = _campaign(
            tmp_path,
            experiment_protocol=MockExperimentProtocol(
                results=[_make_protocol_result(ExperimentStage.SCREENING)]
            ),
        )
        result = cm.run_one_step()
        assert result.branch_id is not None

    def test_get_state_after_step(self, tmp_path):
        cm = _campaign(
            tmp_path,
            experiment_protocol=MockExperimentProtocol(
                results=[_make_protocol_result(ExperimentStage.SCREENING)]
            ),
        )
        cm.run_one_step()
        state = cm.get_state()
        assert state["n_experiments"] == 1


class TestContinueExplore:
    def test_protocol_continue_produces_provisional_head(self, tmp_path):
        """An explicit inconclusive Protocol verdict retains provisional code."""
        cm = _campaign(
            tmp_path,
            experiment_protocol=MockExperimentProtocol(
                [
                    _make_protocol_result(
                        ExperimentStage.SCREENING, gate_outcome="continue"
                    )
                ]
            ),
        )
        result = cm.run_one_step()
        assert result.decision == Decision.CONTINUE_EXPLORE
        branch = cm._branch_ctrl.get_branch(result.branch_id)
        assert branch.current_code_hash is not None

    def test_continue_explore_retains_verified_workspace(self, tmp_path):
        """CONTINUE_EXPLORE keeps the branch's executable verified codebase."""
        cm = _campaign(
            tmp_path,
            experiment_protocol=MockExperimentProtocol(
                [
                    _make_protocol_result(
                        ExperimentStage.SCREENING, gate_outcome="continue"
                    )
                ]
            ),
        )
        result = cm.run_one_step()
        assert result.branch_id is not None
        bid = result.branch_id
        workspace = Path(cm._branch_workspaces[bid])
        assert workspace.is_dir()
        assert (
            "candidate = solution"
            in (workspace / "operators" / "local_search.py").read_text()
        )

    def test_continue_explore_clears_hypothesis(self, tmp_path):
        """After CONTINUE_EXPLORE, the branch hypothesis is cleared."""
        cm = _campaign(
            tmp_path,
            experiment_protocol=MockExperimentProtocol(
                [
                    _make_protocol_result(
                        ExperimentStage.SCREENING, gate_outcome="continue"
                    )
                ]
            ),
        )
        result = cm.run_one_step()
        bid = result.branch_id
        assert cm._branch_ctrl.get_branch(bid).hypothesis is None

    def test_continue_explore_branch_stays_in_explore(self, tmp_path):
        """Branch should remain in EXPLORE state after CONTINUE_EXPLORE."""
        cm = _campaign(
            tmp_path,
            experiment_protocol=MockExperimentProtocol(
                [
                    _make_protocol_result(
                        ExperimentStage.SCREENING, gate_outcome="continue"
                    )
                ]
            ),
        )
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
        cm._scheduler = Scheduler(max_active_branches=1)
        cm._branch_step_runner.scheduler = cm._scheduler
        r1 = cm.run_one_step()
        r2 = cm.run_one_step()
        assert r1.decision == Decision.CONTINUE_EXPLORE
        assert r2.decision == Decision.QUEUE_VALIDATE
        assert r1.branch_id == r2.branch_id
        assert len(cm._branch_ctrl._branches) == 1
        assert llm.hyp_calls == 2
        assert llm.patch_calls == 2

        hypothesis_calls = [
            call for call in llm.provider_calls if call["request_kind"] == "hypothesis"
        ]
        second_h_evidence = json.loads(
            hypothesis_calls[1]["system_blocks"][2]["text"].split("\n", 1)[1]
        )
        second_h_static = json.loads(
            hypothesis_calls[1]["system_blocks"][1]["text"].split("\n", 1)[1]
        )
        assert len(second_h_evidence["experiment_history"]) == 1
        prior = second_h_evidence["experiment_history"][0]
        assert prior["experiment_evidence"]["stage"] == "screening"
        prior_aggregate = prior["experiment_evidence"]["objective_outcome"]["aggregate"]
        assert prior_aggregate["win_rate"] == 0.1
        assert prior_aggregate["median_delta"] == -12.0
        assert "candidate = solution" in second_h_evidence.get(
            "branch_current_code", ""
        )
        assert (
            "### operators/local_search.py"
            not in (second_h_static["champion_operators_code"])
        )
        assert "### operators/local_search.py" in second_h_evidence.get(
            "branch_current_code", ""
        )

        code_calls = [
            call for call in llm.provider_calls if call["request_kind"] == "code"
        ]
        second_c_context = json.loads(
            code_calls[1]["system_blocks"][1]["text"].split("\n", 1)[1]
        )
        source_context = second_c_context["editable_source_context"]
        prior_source = next(
            entry
            for entry in source_context["sources"]
            if entry["path"] == "operators/local_search.py"
        )
        # The prior edit remains durable branch state and visible to the next H,
        # but it is only a peer of this C target.  Stage-5 source selection keeps
        # peer content out of the initial code prompt while retaining inventory.
        assert prior_source["roles"] == ["peer"]
        assert prior_source["visible"] is False
        assert prior_source["content"] is None

        workspace = Path(cm._branch_workspaces[r2.branch_id])
        assert (
            "candidate = solution"
            in (workspace / "operators" / "local_search.py").read_text()
        )
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
                return self.call(
                    prompt, tool.get("input_schema", {}), model, system_blocks
                )

        cm = _campaign(
            tmp_path,
            llm_client=SequencedLLM(),
            experiment_protocol=MockExperimentProtocol(
                [
                    _make_protocol_result(
                        ExperimentStage.SCREENING,
                        gate_outcome="continue",
                    ),
                    _make_protocol_result(
                        ExperimentStage.SCREENING,
                        gate_outcome="continue",
                    ),
                ]
            ),
        )
        cm._scheduler = Scheduler(max_active_branches=1)
        cm._branch_step_runner.scheduler = cm._scheduler

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
