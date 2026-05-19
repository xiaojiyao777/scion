"""Focused tests split from test_verification.py."""

from .verification_test_support import *  # noqa: F401,F403

class TestFeasibilityCheck:
    def test_skipped_when_no_canary(self):
        spec = _make_spec(canary="")
        runner = _mock_runner()
        r = check_feasibility(spec, runner, "/tmp")
        assert r.passed is True
        assert "skipped" in r.detail

    def test_skipped_when_canary_not_found(self):
        spec = _make_spec(canary="/nonexistent/path/instance.json")
        runner = _mock_runner()
        r = check_feasibility(spec, runner, "/tmp")
        assert r.passed is True
        assert "skipped" in r.detail

    def test_solver_failure_fails(self, tmp_path):
        # Create a dummy canary file.
        canary = str(tmp_path / "small.json")
        Path(canary).write_text("{}")
        spec = _make_spec(canary=canary)
        runner = _mock_runner(success=False)
        r = check_feasibility(spec, runner, str(tmp_path))
        assert r.passed is False
        assert r.name == "V6_feasibility"

    def test_adapter_required_spec_without_adapter_fails_before_legacy_fallback(
        self,
        tmp_path,
    ):
        canary = str(tmp_path / "small.json")
        Path(canary).write_text("{}")
        (tmp_path / "oracle.py").write_text(
            "def check_solver_output_feasibility(raw, canary):\n"
            "    raise AssertionError('legacy oracle should not be called')\n"
        )
        spec = _make_adapter_required_spec(canary).model_copy(
            update={"root_dir": str(tmp_path), "oracle_path": "oracle.py"}
        )
        runner = _mock_runner(output_dict=_solver_output_dict())

        r = check_feasibility(spec, runner, str(tmp_path))

        assert r.passed is False
        assert r.name == "V6_feasibility"
        assert "problem adapter is required" in r.detail
        assert "legacy feasibility fallback disabled" in r.detail

    def test_legacy_oracle_fallback_remains_compatible(self, tmp_path):
        canary = str(tmp_path / "small.json")
        Path(canary).write_text("{}")
        (tmp_path / "oracle.py").write_text(
            "def check_solver_output_feasibility(raw, canary):\n"
            "    return True\n"
        )
        spec = _make_spec(canary=canary).model_copy(
            update={"root_dir": str(tmp_path), "oracle_path": "oracle.py"}
        )
        runner = _mock_runner(output_dict=_solver_output_dict())

        r = check_feasibility(spec, runner, str(tmp_path))

        assert r.passed is True
        assert r.name == "V6_feasibility"
        assert "feasibility ok" in r.detail

    def test_selected_surface_missing_runtime_field_preempts_adapter_required(
        self,
        tmp_path,
    ):
        canary = str(tmp_path / "small.json")
        Path(canary).write_text("{}")
        spec = _make_adapter_required_spec(canary).model_copy(
            update={
                "research_surfaces": [
                    {
                        "name": "search_policy",
                        "kind": "policy",
                        "target_files": ["policies/search_policy.py"],
                        "evidence": {
                            "required_runtime_fields": ["policy_loaded"],
                        },
                    }
                ],
            }
        )
        output = _solver_output_dict()
        output["runtime"] = {}
        runner = _mock_runner(output_dict=output)

        r = check_feasibility(
            spec,
            runner,
            str(tmp_path),
            selected_surface="search_policy",
        )

        assert r.passed is False
        assert "solver runtime audit failed" in r.detail
        assert "missing=policy_loaded" in r.detail
        assert "problem adapter is required" not in r.detail


class TestSolutionConsistencyCheck:
    def test_top_level_assignment_vehicle_mismatch_fails(self, tmp_path):
        canary = str(tmp_path / "small.json")
        Path(canary).write_text("{}")
        spec = _make_spec(canary=canary)
        output = _solver_output_dict()
        output["assignment"] = {"O1": "V_MISMATCH"}
        runner = _mock_runner(output_dict=output)

        r = check_state_mutation(spec, runner, str(tmp_path))

        assert r.passed is False
        assert r.severity == "heavy"
        assert "assignment says" in r.detail

    def test_adapter_consistency_failure_fails_closed(self, tmp_path):
        canary = str(tmp_path / "small.json")
        Path(canary).write_text("{}")
        spec = _make_spec(canary=canary)
        runner = _mock_runner(output_dict={"routes": [[1, 1]], "objective": {"cost": 1.0}})

        class RejectingAdapter:
            def load_instance(self, instance_path):
                return {"path": instance_path}

            def deserialize_solver_output(self, raw_output, instance):
                return SolverArtifact(
                    raw_output=raw_output,
                    objective={"cost": 1.0},
                    feasible=True,
                    normalized_solution=raw_output,
                )

            def check_solution_consistency(self, artifact, instance):
                return CheckReport(False, ("customer 1 appears twice",))

        r = check_state_mutation(spec, runner, str(tmp_path), adapter=RejectingAdapter())

        assert r.passed is False
        assert r.name == "V5_solution_consistency"
        assert "adapter consistency failed" in r.detail
        assert "customer 1 appears twice" in r.detail

    def test_adapter_required_spec_without_adapter_fails_before_legacy_fallback(
        self,
        tmp_path,
    ):
        canary = str(tmp_path / "small.json")
        Path(canary).write_text("{}")
        spec = _make_adapter_required_spec(canary)
        runner = _mock_runner(output_dict=_solver_output_dict())

        r = check_state_mutation(spec, runner, str(tmp_path))

        assert r.passed is False
        assert r.name == "V5_solution_consistency"
        assert "problem adapter is required" in r.detail
        assert "legacy solution consistency fallback disabled" in r.detail
        assert runner.run_solver.called

    def test_solver_runtime_audit_failure_fails_closed(self, tmp_path):
        canary = str(tmp_path / "small.json")
        Path(canary).write_text("{}")
        spec = _make_spec(canary=canary)
        output = _solver_output_dict()
        output["runtime"] = {
            "operator_errors": 1,
            "operator_events": [
                {
                    "operator": "bad_op",
                    "status": "error",
                    "detail": "'CvrpInstance' object has no attribute 'vehicle_capacity'",
                }
            ],
        }
        runner = _mock_runner(output_dict=output)

        r = check_state_mutation(spec, runner, str(tmp_path))

        assert r.passed is False
        assert r.name == "V5_solution_consistency"
        assert "solver runtime audit failed" in r.detail
        assert "operator_errors=1" in r.detail

    def test_surface_runtime_contract_all_required_fields_present_passes(self, tmp_path):
        canary = str(tmp_path / "small.json")
        Path(canary).write_text("{}")
        spec = _make_surface_spec(
            canary,
            [
                {
                    "name": "search_policy",
                    "evidence": {
                        "required_runtime_fields": [
                            "policy_loaded",
                            "policy_errors",
                            "baseline_time_fraction",
                        ],
                    },
                },
            ],
        )
        output = _solver_output_dict()
        output["runtime"] = {
            "policy_loaded": True,
            "policy_errors": 0,
            "baseline_time_fraction": 0.6,
        }
        runner = _mock_runner(output_dict=output)

        r = check_state_mutation(
            spec,
            runner,
            str(tmp_path),
            selected_surface="search_policy",
        )

        assert r.passed is True

    def test_surface_without_declared_evidence_keeps_legacy_behavior(self, tmp_path):
        canary = str(tmp_path / "small.json")
        Path(canary).write_text("{}")
        spec = _make_surface_spec(
            canary,
            [{"name": "local_search", "evidence": {"required_runtime_fields": []}}],
        )
        runner = _mock_runner(output_dict=_solver_output_dict())

        r = check_state_mutation(
            spec,
            runner,
            str(tmp_path),
            selected_surface="local_search",
        )

        assert r.passed is True

    def test_surface_runtime_contract_skips_when_no_surface_selected(self, tmp_path):
        canary = str(tmp_path / "small.json")
        Path(canary).write_text("{}")
        spec = _make_surface_spec(
            canary,
            [
                {
                    "name": "search_policy",
                    "evidence": {
                        "required_runtime_fields": ["policy_loaded"],
                    },
                },
            ],
        )
        runner = _mock_runner(output_dict=_solver_output_dict())

        r = check_state_mutation(spec, runner, str(tmp_path))

        assert r.passed is True

    @pytest.mark.parametrize(
        ("required_field", "runtime_value", "expected_detail"),
        [
            ("dispatch_loaded", False, "failed=dispatch_loaded"),
            ("dispatch_executed", False, "failed=dispatch_executed"),
            ("dispatch_active", False, "failed=dispatch_active"),
            ("dispatch_errors", 1, "failed=dispatch_errors"),
            ("dispatch_errors", "not-an-int", "failed=dispatch_errors"),
        ],
    )
    def test_generic_surface_runtime_evidence_fields_fail_closed(
        self,
        required_field,
        runtime_value,
        expected_detail,
    ):
        spec = _make_surface_spec(
            "",
            [
                {
                    "name": "dispatch_policy",
                    "evidence": {"required_runtime_fields": [required_field]},
                },
            ],
        )

        issue = runtime_audit_failure_from_runtime(
            {required_field: runtime_value},
            problem_spec=spec,
            selected_surface="dispatch_policy",
        )

        assert issue is not None
        assert issue["error_category"] == "surface_runtime_contract_error"
        assert issue["failed_runtime_fields"] == (required_field,)
        assert expected_detail in issue["detail"]
