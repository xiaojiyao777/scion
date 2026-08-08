"""Focused tests split from test_campaign_control_boundaries.py."""

from .campaign_control_boundaries_test_support import *  # noqa: F401,F403

from types import SimpleNamespace

import pytest

from scion.core.execution_outcome import ExecutionOutcome
from scion.core.production_boundary import production_boundary_errors
from scion.problem.spec import ObjectiveMetricSpec


class _StrictAlwaysPassVerification(_AlwaysPassVerification):
    _strict_runtime_checks = True
    _require_adapter_for_runtime = True


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

    def test_eval_protocol_exception_records_evaluation_failure_not_decision_abandon(
        self,
        tmp_path,
    ):
        class _RaisesOnValidationProtocol(_MockProtocol):
            def run_experiment(self, **kwargs):
                if self.experiment_calls:
                    self.experiment_calls.append(
                        (
                            kwargs.get("stage"),
                            kwargs.get("candidate_ws"),
                            kwargs.get("champion_ws"),
                            kwargs.get("hypothesis_action"),
                        )
                    )
                    raise RuntimeError("protocol boom")
                return super().run_experiment(**kwargs)

        cm = _campaign(
            tmp_path,
            experiment_protocol=_RaisesOnValidationProtocol(
                results=[
                    _make_protocol_result(
                        "pass",
                        stage=ExperimentStage.SCREENING,
                        win_rate=0.85,
                    )
                ],
            ),
        )

        screening = cm.run_one_step()
        assert screening.decision == Decision.QUEUE_VALIDATE

        result = cm.run_one_step()

        assert result.failure_stage == "evaluation"
        assert result.decision is None
        assert result.failure_detail == "protocol boom"

        failure_steps = [
            step
            for step in cm._step_history
            if step.failure_stage == "evaluation"
        ]
        assert failure_steps, "evaluation exception must write a failure StepRecord"
        failure = failure_steps[-1]
        assert failure.decision is None
        assert failure.protocol_result is None
        assert failure.execution_outcome is ExecutionOutcome.NOT_EVALUATED
        assert failure.execution_outcome_reason_code == "EVALUATION_EXCEPTION"

    def test_screening_protocol_exception_records_evaluation_failure(
        self,
        tmp_path,
    ):
        class _RaisesImmediatelyProtocol(_MockProtocol):
            def run_experiment(self, **kwargs):
                self.experiment_calls.append(
                    (
                        kwargs.get("stage"),
                        kwargs.get("candidate_ws"),
                        kwargs.get("champion_ws"),
                        kwargs.get("hypothesis_action"),
                    )
                )
                raise RuntimeError("protocol boom")

        cm = _campaign(
            tmp_path,
            experiment_protocol=_RaisesImmediatelyProtocol(),
        )

        result = cm.run_one_step()

        assert result.failure_stage == "evaluation"
        assert result.decision is None

        failure = cm._step_history[-1]
        assert failure.failure_stage == "evaluation"
        assert failure.decision is None
        assert failure.protocol_result is None
        assert failure.execution_outcome is ExecutionOutcome.NOT_EVALUATED


class TestProgrammaticRuntimeVerificationDefault:
    def _production_spec(self, base: ProblemSpec, canary_case_path: str = "") -> ProblemSpec:
        return base.model_copy(
            update={
                "spec_version": "problem-v1",
                "adapter_import_path": "scion.problems.demo.adapter:DemoAdapter",
                "requires_adapter_for_runtime": True,
                "canary_case_path": canary_case_path,
            }
        )

    def _production_split(self) -> SplitManifest:
        return SplitManifest(
            screening=["screening-case"],
            validation=["validation-case"],
            frozen=["frozen-case"],
            canary=["canary-case"],
        )

    def _production_seeds(self) -> SeedLedgerConfig:
        return SeedLedgerConfig(
            screening=[1],
            validation=[2],
            frozen=[3],
            canary=[4],
        )

    def _metric_specs(self, *names: str) -> tuple[ObjectiveMetricSpec, ...]:
        metric_names = names or ("cost",)
        return tuple(
            ObjectiveMetricSpec(
                name=name,
                direction="minimize",
                priority=index,
            )
            for index, name in enumerate(metric_names, start=1)
        )

    def _production_protocol(
        self,
        *,
        metric_specs: (
            tuple[ObjectiveMetricSpec, ...] | tuple[object, ...] | None
        ) = None,
        problem_spec: object | None = None,
        time_limit_sec: int | None = None,
    ) -> _MockProtocol:
        proto = _MockProtocol()
        proto.runner = object()
        proto.config = ProtocolConfig()
        if time_limit_sec is not None:
            proto.time_limit_sec = time_limit_sec
        proto._metric_specs = metric_specs or self._metric_specs()
        proto._require_metric_specs = True
        proto._problem_spec = problem_spec
        return proto

    def _adapter_for(self, problem_spec: object) -> SimpleNamespace:
        return SimpleNamespace(spec=problem_spec)

    def _legacy_spec(self, base: ProblemSpec) -> ProblemSpec:
        return base.model_copy(
            update={
                "spec_version": "legacy",
                "adapter_import_path": "",
                "requires_adapter_for_runtime": False,
            }
        )

    def test_adapter_protocol_runner_builds_strict_verification_gate(self, tmp_path):
        base = _campaign(tmp_path, verification_gate=None)
        problem_spec = self._production_spec(base._spec)
        proto = _MockProtocol()
        proto.runner = object()
        proto.config = ProtocolConfig()
        proto._metric_specs = self._metric_specs()
        proto._require_metric_specs = True
        proto._problem_spec = problem_spec
        cm_adapter = self._adapter_for(problem_spec)
        cm = CampaignManager(
            problem_spec=problem_spec,
            protocol_config=ProtocolConfig(),
            split_manifest=self._production_split(),
            seed_ledger=self._production_seeds(),
            llm_client=MockLLMClient(
                hypothesis_response=_VALID_HYPOTHESIS,
                patch_response=_VALID_PATCH,
            ),
            champion=base._champion,
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
        problem_spec = self._production_spec(base._spec)
        proto = self._production_protocol(problem_spec=problem_spec)
        proto.runner = None
        cm = CampaignManager(
            problem_spec=problem_spec,
            protocol_config=ProtocolConfig(),
            split_manifest=self._production_split(),
            seed_ledger=self._production_seeds(),
            llm_client=MockLLMClient(
                hypothesis_response=_VALID_HYPOTHESIS,
                patch_response=_VALID_PATCH,
            ),
            champion=base._champion,
            campaign_dir=str(tmp_path / "missing-runner-campaign"),
            experiment_protocol=proto,
            adapter=self._adapter_for(problem_spec),
        )
        result = cm._vgate.run(
            str(tmp_path / "champion_code"),
            str(tmp_path / "champion_code"),
            PatchProposal(**_VALID_PATCH),
        )

        assert result.passed is False
        assert result.first_failure == "V_runtime_config"

    def test_adapter_allow_non_strict_runtime_verification_is_rejected(self, tmp_path):
        base = _campaign(tmp_path, verification_gate=_AlwaysPassVerification())

        with pytest.raises(
            ValueError,
            match="allow_non_strict_runtime_verification is not allowed",
        ):
            CampaignManager(
                problem_spec=base._spec,
                protocol_config=ProtocolConfig(),
                split_manifest=self._production_split(),
                seed_ledger=self._production_seeds(),
                llm_client=MockLLMClient(
                    hypothesis_response=_VALID_HYPOTHESIS,
                    patch_response=_VALID_PATCH,
                ),
                champion=base._champion,
                campaign_dir=str(tmp_path / "compat-campaign"),
                experiment_protocol=self._production_protocol(),
                adapter=object(),
                allow_non_strict_runtime_verification=True,
            )

    def test_adapter_skeleton_mode_preserves_non_strict_runtime_fallback(
        self,
        tmp_path,
    ):
        base = _campaign(tmp_path, verification_gate=_AlwaysPassVerification())
        cm = CampaignManager(
            problem_spec=base._spec,
            protocol_config=ProtocolConfig(),
            split_manifest=SplitManifest(),
            seed_ledger=SeedLedgerConfig(),
            llm_client=MockLLMClient(
                hypothesis_response=_VALID_HYPOTHESIS,
                patch_response=_VALID_PATCH,
            ),
            champion=base._champion,
            campaign_dir=str(tmp_path / "compat-skeleton-campaign"),
            experiment_protocol=_MockProtocol(),
            adapter=object(),
            allow_non_strict_runtime_verification=True,
            allow_skeleton_mode=True,
        )

        assert cm._vgate._strict_runtime_checks is False
        assert cm._vgate._require_adapter_for_runtime is False

    def test_production_campaign_requires_experiment_protocol(self, tmp_path):
        base = _campaign(tmp_path, verification_gate=_AlwaysPassVerification())

        with pytest.raises(ValueError, match="experiment_protocol is required"):
            CampaignManager(
                problem_spec=self._production_spec(base._spec),
                protocol_config=ProtocolConfig(),
                split_manifest=self._production_split(),
                seed_ledger=self._production_seeds(),
                llm_client=MockLLMClient(
                    hypothesis_response=_VALID_HYPOTHESIS,
                    patch_response=_VALID_PATCH,
                ),
                champion=base._champion,
                campaign_dir=str(tmp_path / "production-no-protocol"),
                experiment_protocol=None,
                adapter=object(),
            )

    def test_production_campaign_rejects_parameter_search(self, tmp_path):
        base = _campaign(tmp_path, verification_gate=_AlwaysPassVerification())
        problem_spec = self._production_spec(base._spec)
        problem_spec.parameter_search.enabled = True

        with pytest.raises(
            ValueError,
            match=r"parameter_search\.enabled must be false",
        ):
            CampaignManager(
                problem_spec=problem_spec,
                protocol_config=ProtocolConfig(),
                split_manifest=self._production_split(),
                seed_ledger=self._production_seeds(),
                llm_client=MockLLMClient(
                    hypothesis_response=_VALID_HYPOTHESIS,
                    patch_response=_VALID_PATCH,
                ),
                champion=base._champion,
                campaign_dir=str(tmp_path / "production-parameter-search"),
                experiment_protocol=self._production_protocol(
                    problem_spec=problem_spec,
                ),
                adapter=self._adapter_for(problem_spec),
            )

    def test_legacy_adapter_campaign_requires_metric_specs(self, tmp_path):
        base = _campaign(tmp_path, verification_gate=_AlwaysPassVerification())
        proto = _MockProtocol()
        proto.runner = object()
        proto.config = ProtocolConfig()

        with pytest.raises(ValueError, match="metric_specs are required"):
            CampaignManager(
                problem_spec=self._legacy_spec(base._spec),
                protocol_config=ProtocolConfig(),
                split_manifest=self._production_split(),
                seed_ledger=self._production_seeds(),
                llm_client=MockLLMClient(
                    hypothesis_response=_VALID_HYPOTHESIS,
                    patch_response=_VALID_PATCH,
                ),
                champion=base._champion,
                campaign_dir=str(tmp_path / "legacy-adapter-no-metrics"),
                experiment_protocol=proto,
                adapter=object(),
            )

    def test_legacy_adapter_campaign_requires_canary_split_and_seed(
        self,
        tmp_path,
    ):
        base = _campaign(tmp_path, verification_gate=_AlwaysPassVerification())

        with pytest.raises(ValueError, match="split_manifest.canary is required"):
            CampaignManager(
                problem_spec=self._legacy_spec(base._spec),
                protocol_config=ProtocolConfig(),
                split_manifest=SplitManifest(
                    screening=["screening-case"],
                    validation=["validation-case"],
                    frozen=["frozen-case"],
                    canary=[],
                ),
                seed_ledger=self._production_seeds(),
                llm_client=MockLLMClient(
                    hypothesis_response=_VALID_HYPOTHESIS,
                    patch_response=_VALID_PATCH,
                ),
                champion=base._champion,
                campaign_dir=str(tmp_path / "legacy-adapter-no-canary-split"),
                experiment_protocol=self._production_protocol(),
                adapter=object(),
            )

        with pytest.raises(ValueError, match="seed_ledger.canary is required"):
            CampaignManager(
                problem_spec=self._legacy_spec(base._spec),
                protocol_config=ProtocolConfig(),
                split_manifest=self._production_split(),
                seed_ledger=SeedLedgerConfig(
                    screening=[1],
                    validation=[2],
                    frozen=[3],
                    canary=[],
                ),
                llm_client=MockLLMClient(
                    hypothesis_response=_VALID_HYPOTHESIS,
                    patch_response=_VALID_PATCH,
                ),
                champion=base._champion,
                campaign_dir=str(tmp_path / "legacy-adapter-no-canary-seed"),
                experiment_protocol=self._production_protocol(),
                adapter=object(),
            )

    def test_production_campaign_requires_split_seed_canary_evidence(self, tmp_path):
        base = _campaign(tmp_path, verification_gate=_AlwaysPassVerification())
        proto = _MockProtocol()
        proto.runner = object()
        proto.config = ProtocolConfig()
        proto._metric_specs = self._metric_specs()
        proto._require_metric_specs = True

        with pytest.raises(ValueError, match="split_manifest.canary is required"):
            CampaignManager(
                problem_spec=self._production_spec(base._spec),
                protocol_config=ProtocolConfig(),
                split_manifest=SplitManifest(
                    screening=["screening-case"],
                    validation=["validation-case"],
                    frozen=["frozen-case"],
                    canary=[],
                ),
                seed_ledger=self._production_seeds(),
                llm_client=MockLLMClient(
                    hypothesis_response=_VALID_HYPOTHESIS,
                    patch_response=_VALID_PATCH,
                ),
                champion=base._champion,
                campaign_dir=str(tmp_path / "production-no-canary"),
                experiment_protocol=proto,
                adapter=object(),
            )

    def test_production_campaign_rejects_dummy_metric_specs(self, tmp_path):
        base = _campaign(tmp_path, verification_gate=_AlwaysPassVerification())

        with pytest.raises(ValueError, match=r"metric_specs\[0\]\.name is required"):
            CampaignManager(
                problem_spec=self._production_spec(base._spec),
                protocol_config=ProtocolConfig(),
                split_manifest=self._production_split(),
                seed_ledger=self._production_seeds(),
                llm_client=MockLLMClient(
                    hypothesis_response=_VALID_HYPOTHESIS,
                    patch_response=_VALID_PATCH,
                ),
                champion=base._champion,
                campaign_dir=str(tmp_path / "production-dummy-metrics"),
                experiment_protocol=self._production_protocol(
                    metric_specs=(object(),),
                ),
                adapter=object(),
            )

    def test_production_campaign_rejects_protocol_problem_spec_mismatch(
        self,
        tmp_path,
    ):
        base = _campaign(tmp_path, verification_gate=_AlwaysPassVerification())

        with pytest.raises(
            ValueError,
            match="experiment_protocol.problem_spec must match",
        ):
            CampaignManager(
                problem_spec=self._production_spec(base._spec),
                protocol_config=ProtocolConfig(),
                split_manifest=self._production_split(),
                seed_ledger=self._production_seeds(),
                llm_client=MockLLMClient(
                    hypothesis_response=_VALID_HYPOTHESIS,
                    patch_response=_VALID_PATCH,
                ),
                champion=base._champion,
                campaign_dir=str(tmp_path / "production-protocol-spec-mismatch"),
                experiment_protocol=self._production_protocol(
                    problem_spec=SimpleNamespace(id="other_problem"),
                ),
                adapter=object(),
            )

    def test_production_campaign_rejects_adapter_spec_mismatch(self, tmp_path):
        base = _campaign(tmp_path, verification_gate=_AlwaysPassVerification())

        with pytest.raises(ValueError, match="adapter.spec must match"):
            CampaignManager(
                problem_spec=self._production_spec(base._spec),
                protocol_config=ProtocolConfig(),
                split_manifest=self._production_split(),
                seed_ledger=self._production_seeds(),
                llm_client=MockLLMClient(
                    hypothesis_response=_VALID_HYPOTHESIS,
                    patch_response=_VALID_PATCH,
                ),
                champion=base._champion,
                campaign_dir=str(tmp_path / "production-adapter-spec-mismatch"),
                experiment_protocol=self._production_protocol(),
                adapter=SimpleNamespace(spec=SimpleNamespace(id="other_problem")),
            )

    def test_production_boundary_accepts_same_id_without_spec_hash_parity(
        self,
        tmp_path,
    ):
        base = _campaign(tmp_path, verification_gate=_AlwaysPassVerification())
        campaign_spec = self._production_spec(base._spec)
        protocol_spec = campaign_spec.model_copy(
            update={"description": "different generic declaration"}
        )

        errors = production_boundary_errors(
            problem_spec=campaign_spec,
            experiment_protocol=self._production_protocol(
                problem_spec=protocol_spec,
            ),
            adapter=self._adapter_for(campaign_spec),
            split_manifest=self._production_split(),
            seed_ledger=self._production_seeds(),
        )

        assert errors == ()

    def test_production_boundary_rejects_different_adapter_problem_id(
        self,
        tmp_path,
    ):
        base = _campaign(tmp_path, verification_gate=_AlwaysPassVerification())
        campaign_spec = self._production_spec(base._spec)
        adapter_spec = SimpleNamespace(id="other_problem")

        errors = production_boundary_errors(
            problem_spec=campaign_spec,
            experiment_protocol=self._production_protocol(
                problem_spec=campaign_spec,
            ),
            adapter=self._adapter_for(adapter_spec),
            split_manifest=self._production_split(),
            seed_ledger=self._production_seeds(),
        )

        assert any(
            "adapter.spec must match campaign problem_spec identity" in error
            for error in errors
        )

    def test_production_boundary_accepts_legacy_adapter_spec_with_matching_id(
        self,
        tmp_path,
    ):
        base = _campaign(tmp_path, verification_gate=_AlwaysPassVerification())
        campaign_spec = self._production_spec(base._spec)
        adapter_spec = SimpleNamespace(
            name=campaign_spec.name,
            description="legacy adapter-visible compatibility view",
        )

        errors = production_boundary_errors(
            problem_spec=campaign_spec,
            experiment_protocol=self._production_protocol(
                problem_spec=campaign_spec,
            ),
            adapter=self._adapter_for(adapter_spec),
            split_manifest=self._production_split(),
            seed_ledger=self._production_seeds(),
        )

        assert errors == ()

    def test_production_boundary_ignores_adapter_self_declared_problem_hash(
        self,
        tmp_path,
    ):
        base = _campaign(tmp_path, verification_gate=_AlwaysPassVerification())
        campaign_spec = self._production_spec(base._spec)
        adapter_spec = SimpleNamespace(
            name=campaign_spec.name,
            problem_spec_hash="wrong-v1-hash",
        )

        errors = production_boundary_errors(
            problem_spec=campaign_spec,
            experiment_protocol=self._production_protocol(
                problem_spec=campaign_spec,
            ),
            adapter=self._adapter_for(adapter_spec),
            split_manifest=self._production_split(),
            seed_ledger=self._production_seeds(),
        )

        assert errors == ()

    def test_production_boundary_rejects_adapter_without_visible_generic_spec(
        self,
        tmp_path,
    ):
        base = _campaign(tmp_path, verification_gate=_AlwaysPassVerification())
        campaign_spec = self._production_spec(base._spec)

        errors = production_boundary_errors(
            problem_spec=campaign_spec,
            experiment_protocol=self._production_protocol(
                problem_spec=campaign_spec,
            ),
            adapter=object(),
            split_manifest=self._production_split(),
            seed_ledger=self._production_seeds(),
        )

        assert "adapter.spec is required" in errors

    def test_production_boundary_accepts_matching_runtime_capabilities(
        self,
        tmp_path,
    ):
        base = _campaign(tmp_path, verification_gate=_AlwaysPassVerification())
        campaign_spec = self._production_spec(base._spec)
        protocol = self._production_protocol(problem_spec=campaign_spec)
        adapter = self._adapter_for(campaign_spec)
        split_manifest = self._production_split()
        seed_ledger = self._production_seeds()

        errors = production_boundary_errors(
            problem_spec=campaign_spec,
            experiment_protocol=protocol,
            adapter=adapter,
            split_manifest=split_manifest,
            seed_ledger=seed_ledger,
            verification_gate=_AlwaysPassVerification(),
        )

        assert errors == ()

    def test_production_boundary_requires_verification_run_capability(self, tmp_path):
        base = _campaign(tmp_path, verification_gate=_AlwaysPassVerification())
        campaign_spec = self._production_spec(base._spec)

        errors = production_boundary_errors(
            problem_spec=campaign_spec,
            experiment_protocol=self._production_protocol(
                problem_spec=campaign_spec,
            ),
            adapter=self._adapter_for(campaign_spec),
            split_manifest=self._production_split(),
            seed_ledger=self._production_seeds(),
            verification_gate=object(),
        )

        assert "verification_gate.run is required" in errors

    def test_production_boundary_rejects_parameter_search(self, tmp_path):
        base = _campaign(tmp_path, verification_gate=_AlwaysPassVerification())
        campaign_spec = self._production_spec(base._spec)
        campaign_spec.parameter_search.enabled = True

        errors = production_boundary_errors(
            problem_spec=campaign_spec,
            experiment_protocol=self._production_protocol(
                problem_spec=campaign_spec,
            ),
            adapter=self._adapter_for(campaign_spec),
            split_manifest=self._production_split(),
            seed_ledger=self._production_seeds(),
        )

        assert (
            "parameter_search.enabled must be false for direct-v3 production "
            "campaigns"
        ) in errors

    def test_production_campaign_rejects_metric_names_mismatch(self, tmp_path):
        base = _campaign(tmp_path, verification_gate=_AlwaysPassVerification())
        problem_spec = self._production_spec(base._spec).model_copy(
            update={"objectives": self._metric_specs("cost")}
        )

        with pytest.raises(
            ValueError,
            match="metric_specs must match problem_spec.objectives names",
        ):
            CampaignManager(
                problem_spec=problem_spec,
                protocol_config=ProtocolConfig(),
                split_manifest=self._production_split(),
                seed_ledger=self._production_seeds(),
                llm_client=MockLLMClient(
                    hypothesis_response=_VALID_HYPOTHESIS,
                    patch_response=_VALID_PATCH,
                ),
                champion=base._champion,
                campaign_dir=str(tmp_path / "production-metric-mismatch"),
                experiment_protocol=self._production_protocol(
                    metric_specs=self._metric_specs("quality"),
                ),
                adapter=object(),
            )

    def test_allow_skeleton_mode_preserves_explicit_legacy_fallback(self, tmp_path):
        base = _campaign(tmp_path, verification_gate=_AlwaysPassVerification())

        cm = CampaignManager(
            problem_spec=self._production_spec(base._spec),
            protocol_config=ProtocolConfig(),
            split_manifest=SplitManifest(),
            seed_ledger=SeedLedgerConfig(),
            llm_client=MockLLMClient(
                hypothesis_response=_VALID_HYPOTHESIS,
                patch_response=_VALID_PATCH,
            ),
            champion=base._champion,
            campaign_dir=str(tmp_path / "explicit-skeleton"),
            experiment_protocol=None,
            adapter=None,
            allow_skeleton_mode=True,
        )

        assert cm._experiment_protocol is None
        assert cm._vgate._strict_runtime_checks is False
        assert cm._vgate._require_adapter_for_runtime is False

    def test_production_campaign_rejects_custom_non_strict_gate(self, tmp_path):
        base = _campaign(tmp_path, verification_gate=_AlwaysPassVerification())

        with pytest.raises(
            ValueError,
            match="custom verification_gate is not allowed",
        ):
            CampaignManager(
                problem_spec=self._production_spec(base._spec),
                protocol_config=ProtocolConfig(),
                split_manifest=self._production_split(),
                seed_ledger=self._production_seeds(),
                llm_client=MockLLMClient(
                    hypothesis_response=_VALID_HYPOTHESIS,
                    patch_response=_VALID_PATCH,
                ),
                champion=base._champion,
                campaign_dir=str(tmp_path / "production-custom-non-strict"),
                experiment_protocol=self._production_protocol(),
                adapter=object(),
                verification_gate=_AlwaysPassVerification(),
            )

    def test_production_campaign_rejects_custom_strict_always_pass_gate(
        self,
        tmp_path,
    ):
        base = _campaign(tmp_path, verification_gate=_AlwaysPassVerification())
        gate = _StrictAlwaysPassVerification()

        with pytest.raises(
            ValueError,
            match="custom verification_gate is not allowed",
        ):
            CampaignManager(
                problem_spec=self._production_spec(base._spec),
                protocol_config=ProtocolConfig(),
                split_manifest=self._production_split(),
                seed_ledger=self._production_seeds(),
                llm_client=MockLLMClient(
                    hypothesis_response=_VALID_HYPOTHESIS,
                    patch_response=_VALID_PATCH,
                ),
                champion=base._champion,
                campaign_dir=str(tmp_path / "production-custom-strict"),
                experiment_protocol=self._production_protocol(),
                adapter=object(),
                verification_gate=gate,
            )

    def test_skeleton_mode_allows_custom_test_gate(self, tmp_path):
        base = _campaign(tmp_path, verification_gate=_AlwaysPassVerification())
        gate = _StrictAlwaysPassVerification()

        cm = CampaignManager(
            problem_spec=self._production_spec(base._spec),
            protocol_config=ProtocolConfig(),
            split_manifest=SplitManifest(),
            seed_ledger=SeedLedgerConfig(),
            llm_client=MockLLMClient(
                hypothesis_response=_VALID_HYPOTHESIS,
                patch_response=_VALID_PATCH,
            ),
            champion=base._champion,
            campaign_dir=str(tmp_path / "skeleton-custom-gate"),
            experiment_protocol=_MockProtocol(),
            adapter=object(),
            verification_gate=gate,
            allow_skeleton_mode=True,
        )

        assert cm._vgate is gate

    def test_protocol_time_limit_configures_verification_runtime_budget(
        self,
        tmp_path,
    ):
        base = _campaign(tmp_path, verification_gate=_AlwaysPassVerification())
        problem_spec = self._production_spec(base._spec)

        cm = CampaignManager(
            problem_spec=problem_spec,
            protocol_config=ProtocolConfig(),
            split_manifest=self._production_split(),
            seed_ledger=self._production_seeds(),
            llm_client=MockLLMClient(
                hypothesis_response=_VALID_HYPOTHESIS,
                patch_response=_VALID_PATCH,
            ),
            champion=base._champion,
            campaign_dir=str(tmp_path / "production-runtime-budget"),
            experiment_protocol=self._production_protocol(
                problem_spec=problem_spec,
                time_limit_sec=17,
            ),
            adapter=self._adapter_for(problem_spec),
            verification_gate=None,
        )

        assert cm._vgate._runtime_time_limit_sec == 17

    def test_production_campaign_without_custom_gate_builds_strict_gate(self, tmp_path):
        base = _campaign(tmp_path, verification_gate=_AlwaysPassVerification())
        problem_spec = self._production_spec(base._spec)

        cm = CampaignManager(
            problem_spec=problem_spec,
            protocol_config=ProtocolConfig(),
            split_manifest=self._production_split(),
            seed_ledger=self._production_seeds(),
            llm_client=MockLLMClient(
                hypothesis_response=_VALID_HYPOTHESIS,
                patch_response=_VALID_PATCH,
            ),
            champion=base._champion,
            campaign_dir=str(tmp_path / "production-default-strict"),
            experiment_protocol=self._production_protocol(
                problem_spec=problem_spec,
            ),
            adapter=self._adapter_for(problem_spec),
            verification_gate=None,
        )

        assert cm._vgate._strict_runtime_checks is True
        assert cm._vgate._require_adapter_for_runtime is True
