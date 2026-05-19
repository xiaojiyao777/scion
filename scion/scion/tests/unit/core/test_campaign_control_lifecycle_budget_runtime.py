"""Focused tests split from test_campaign_control_boundaries.py."""

from .campaign_control_boundaries_test_support import *  # noqa: F401,F403

class TestEvalStepHypothesisLifecycle:
    def test_eval_step_reuses_original_hypothesis_id(self, tmp_path):
        """Validation/frozen steps must reuse the same hypothesis_id from screening."""
        # NOTE: run_one_step() for READY_VALIDATE schedules AND runs the eval in one call.
        cm = _campaign(
            tmp_path,
            experiment_protocol=_MockProtocol(results=[
                _make_protocol_result("pass", stage=ExperimentStage.SCREENING, win_rate=0.85),
                _make_protocol_result("pass", stage=ExperimentStage.VALIDATION, win_rate=0.85),
            ]),
        )
        # Step 1: explore + screening → QUEUE_VALIDATE
        r1 = cm.run_one_step()
        assert r1.decision == Decision.QUEUE_VALIDATE

        # Get the hypothesis_id from the screening step record
        screening_steps = [s for s in cm._step_history if s.failure_stage is None and s.hypothesis_id]
        assert screening_steps, "should have at least one success step"
        screening_hyp_id = screening_steps[-1].hypothesis_id

        # Step 2: schedule READY_VALIDATE → VALIDATING + run eval (in same call)
        r2 = cm.run_one_step()
        assert r2.action == "validate", f"expected validate action, got {r2.action!r}"

        # Find the validation step record (must exist in step_history after screening)
        val_steps = [
            s for s in cm._step_history
            if s.verification_passed and s.failure_stage is None
            and s.hypothesis_id is not None
            and s.round_num > screening_steps[-1].round_num
        ]
        assert val_steps, "validation step must be in step_history"
        val_hyp_id = val_steps[-1].hypothesis_id
        assert val_hyp_id == screening_hyp_id, (
            f"validation step hypothesis_id {val_hyp_id!r} must match "
            f"screening step hypothesis_id {screening_hyp_id!r}"
        )

    def test_promote_marks_original_hypothesis_as_promoted(self, tmp_path):
        """After PROMOTE, the original screening HypothesisRecord status must be 'promoted'."""
        # Full happy path: screening → validation → frozen → promote
        cm = _campaign(
            tmp_path,
            experiment_protocol=_MockProtocol(results=[
                _make_protocol_result("pass", stage=ExperimentStage.SCREENING, win_rate=0.85),
                _make_protocol_result("pass", stage=ExperimentStage.VALIDATION, win_rate=0.85),
                _make_protocol_result("pass", stage=ExperimentStage.FROZEN, win_rate=0.90),
            ]),
        )
        # Run enough steps to get to PROMOTE
        for _ in range(10):
            result = cm.run_one_step()
            if result.decision == Decision.PROMOTE:
                break

        # Find the original hypothesis_id
        success_steps = [s for s in cm._step_history if s.failure_stage is None and s.hypothesis_id]
        assert success_steps, "must have at least one success step"
        original_hyp_id = success_steps[0].hypothesis_id

        # Check that the hypothesis_store has it as "promoted"
        promoted_records = cm._hyp_store.get_by_status("promoted")
        promoted_ids = [r.hypothesis_id for r in promoted_records]
        assert original_hyp_id in promoted_ids, (
            f"Original hypothesis {original_hyp_id!r} should be marked 'promoted', "
            f"but promoted ids are {promoted_ids}"
        )

    def test_abandon_marks_original_hypothesis_as_rejected(self, tmp_path):
        """After ABANDON via Decision Engine (canary fail), the original hypothesis must be 'rejected'."""
        # Canary failure causes CANARY_FAILED → ABANDON from the decision engine.
        # The hypothesis goes through screening (h_record stored in _branch_current_hypothesis),
        # then gets abandoned.
        cm = _campaign(
            tmp_path,
            experiment_protocol=_MockProtocol(
                results=[_make_protocol_result("pass", win_rate=0.85)],
                canary_pass=False,  # canary fail → ABANDON
            ),
        )
        r = cm.run_one_step()
        assert r.decision == Decision.ABANDON, (
            f"expected ABANDON from canary failure, got {r.decision!r}"
        )

        # The hypothesis that was stored in _branch_current_hypothesis during screening
        # should be marked rejected after ABANDON
        rejected = cm._hyp_store.get_by_status("rejected")
        assert rejected, "abandoned branch's hypothesis should be marked rejected"


class TestEvalStepWritesStepRecord:
    def test_eval_step_writes_step_record(self, tmp_path):
        """Validation step must appear in step_history with verification_passed=True."""
        cm = _campaign(
            tmp_path,
            experiment_protocol=_MockProtocol(results=[
                _make_protocol_result("pass", stage=ExperimentStage.SCREENING, win_rate=0.85),
                _make_protocol_result("pass", stage=ExperimentStage.VALIDATION, win_rate=0.85),
            ]),
        )
        # screening → QUEUE_VALIDATE
        r1 = cm.run_one_step()
        assert r1.decision == Decision.QUEUE_VALIDATE
        steps_after_screen = len(cm._step_history)

        # schedule + validation eval
        cm.run_one_step()  # schedule READY_VALIDATE → VALIDATING
        cm.run_one_step()  # eval step

        new_steps = cm._step_history[steps_after_screen:]
        assert new_steps, "eval step must append to step_history"
        val_steps = [s for s in new_steps if s.verification_passed and s.failure_stage is None]
        assert val_steps, (
            "validation step must have verification_passed=True and failure_stage=None in step_history"
        )


class TestFrozenBudgetLedger:
    def test_frozen_budget_consumes_before_attempt_and_blocks_second_branch(
        self,
        tmp_path,
    ):
        proto = _MockProtocol(
            results=[
                _make_protocol_result(
                    "fail",
                    stage=ExperimentStage.FROZEN,
                    win_rate=0.0,
                )
            ]
        )
        cm = _campaign(
            tmp_path,
            experiment_protocol=proto,
            protocol_config=ProtocolConfig(
                frozen=FrozenConfig(max_uses_per_campaign=1),
            ),
        )
        workspace = str(tmp_path / "champion_code")
        first_bid = _install_frozen_ready_branch(cm, workspace)
        second_bid = _install_frozen_ready_branch(cm, workspace)

        first = cm.run_one_step()
        second = cm.run_one_step()

        assert first.branch_id == first_bid
        assert second.branch_id == second_bid
        assert len(proto.experiment_calls) == 1
        assert proto.experiment_calls[0][0] == ExperimentStage.FROZEN
        assert len(proto.canary_calls) == 1
        assert cm._frozen_budget_ledger.snapshot() == {
            "used": 1,
            "limit": 1,
            "remaining": 0,
        }

        blocked_steps = [
            step for step in cm._step_history
            if step.branch_id == second_bid
        ]
        assert blocked_steps
        blocked = blocked_steps[-1]
        assert blocked.failure_stage == "frozen_budget"
        assert blocked.failure_detail == FROZEN_BUDGET_EXHAUSTED
        assert blocked.protocol_result is not None
        assert blocked.protocol_result.reason_codes == (FROZEN_BUDGET_EXHAUSTED,)
        assert blocked.decision == Decision.ABANDON

        rebuilt = FrozenBudgetLedger(
            max_uses=1,
            registry=cm._registry,
            campaign_id="fresh-process-campaign-id",
        )
        assert rebuilt.used == 1


class TestProgrammaticRuntimeVerificationDefault:
    def test_adapter_protocol_runner_builds_strict_verification_gate(self, tmp_path):
        proto = _MockProtocol()
        proto.runner = object()
        proto.config = ProtocolConfig()
        cm = _campaign(
            tmp_path,
            experiment_protocol=proto,
            verification_gate=None,
        )
        cm_adapter = object()
        cm = CampaignManager(
            problem_spec=cm._spec,
            protocol_config=ProtocolConfig(),
            split_manifest=SplitManifest(screening=["c1"], validation=["c2"], frozen=["c3"]),
            seed_ledger=SeedLedgerConfig(screening=[1], validation=[2], frozen=[3]),
            llm_client=MockLLMClient(
                hypothesis_response=_VALID_HYPOTHESIS,
                patch_response=_VALID_PATCH,
            ),
            champion=cm._champion,
            campaign_dir=str(tmp_path / "strict-campaign"),
            experiment_protocol=proto,
            adapter=cm_adapter,
        )

        assert cm._vgate._runner is proto.runner
        assert cm._vgate._adapter is cm_adapter
        assert cm._vgate._strict_runtime_checks is True
        assert cm._vgate._require_adapter_for_runtime is True

    def test_adapter_without_runner_fails_closed_by_default(self, tmp_path):
        base = _campaign(tmp_path, verification_gate=_AlwaysPassVerification())
        cm = CampaignManager(
            problem_spec=base._spec,
            protocol_config=ProtocolConfig(),
            split_manifest=SplitManifest(screening=["c1"], validation=["c2"], frozen=["c3"]),
            seed_ledger=SeedLedgerConfig(screening=[1], validation=[2], frozen=[3]),
            llm_client=MockLLMClient(
                hypothesis_response=_VALID_HYPOTHESIS,
                patch_response=_VALID_PATCH,
            ),
            champion=base._champion,
            campaign_dir=str(tmp_path / "missing-runner-campaign"),
            experiment_protocol=_MockProtocol(),
            adapter=object(),
        )
        result = cm._vgate.run(
            str(tmp_path / "champion_code"),
            str(tmp_path / "champion_code"),
            PatchProposal(**_VALID_PATCH),
        )

        assert result.passed is False
        assert result.first_failure == "V_runtime_config"

    def test_adapter_without_runner_compatibility_opt_in_is_non_strict(self, tmp_path):
        base = _campaign(tmp_path, verification_gate=_AlwaysPassVerification())
        cm = CampaignManager(
            problem_spec=base._spec,
            protocol_config=ProtocolConfig(),
            split_manifest=SplitManifest(screening=["c1"], validation=["c2"], frozen=["c3"]),
            seed_ledger=SeedLedgerConfig(screening=[1], validation=[2], frozen=[3]),
            llm_client=MockLLMClient(
                hypothesis_response=_VALID_HYPOTHESIS,
                patch_response=_VALID_PATCH,
            ),
            champion=base._champion,
            campaign_dir=str(tmp_path / "compat-campaign"),
            experiment_protocol=_MockProtocol(),
            adapter=object(),
            allow_non_strict_runtime_verification=True,
        )
        result = cm._vgate.run(
            str(tmp_path / "champion_code"),
            str(tmp_path / "champion_code"),
            PatchProposal(**_VALID_PATCH),
        )

        assert result.passed is True
        assert cm._vgate._strict_runtime_checks is False
