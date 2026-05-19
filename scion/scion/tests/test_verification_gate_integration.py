"""Focused tests split from test_verification.py."""

from .verification_test_support import *  # noqa: F401,F403

class TestVerificationGateIntegration:
    def test_no_runner_runs_static_checks_only(self):
        gate = VerificationGate()
        patch = _make_patch(_VALID_CODE)
        result = gate.run("/tmp", "", patch)
        assert result.passed is True
        # Only V1+V2 checks (no runner, no spec)
        check_names = [c.name for c in result.checks]
        assert "V1_syntax" in check_names
        assert "V2_interface" in check_names
        # No runtime checks
        assert "V6_feasibility" not in check_names

    def test_syntax_fail_stops_early(self):
        gate = VerificationGate()
        patch = _make_patch(_BAD_SYNTAX)
        result = gate.run("/tmp", "", patch)
        assert result.passed is False
        assert result.failure_severity == "light"
        assert result.first_failure == "V1_syntax"

    def test_interface_fail_stops_early(self, tmp_path):
        gate = VerificationGate()
        patch = _make_patch(_NO_EXECUTE)
        result = gate.run(str(tmp_path), "", patch)
        assert result.passed is False
        assert result.failure_severity == "light"
        assert result.first_failure == "V2_interface"

    def test_with_spec_no_canary_skips_runtime(self):
        spec = _make_spec(canary="")
        runner = _mock_runner()
        gate = VerificationGate(problem_spec=spec, runner=runner)
        patch = _make_patch(_VALID_CODE)
        result = gate.run("/tmp", "", patch)
        assert result.passed is True
        # All runtime checks should be present (but skipped/passed)
        check_names = [c.name for c in result.checks]
        assert "V6_feasibility" in check_names
        assert "V7_objective" in check_names
        assert "V8_nondeterminism" in check_names
        assert "V9_perf_guard" in check_names

    def test_strict_runtime_checks_fail_without_runner_or_spec(self):
        gate = VerificationGate(strict_runtime_checks=True)
        patch = _make_patch(_VALID_CODE)
        result = gate.run("/tmp", "/tmp", patch)
        assert result.passed is False
        assert result.failure_severity == "heavy"
        assert result.first_failure == "V_runtime_config"

    def test_strict_runtime_checks_fail_without_canary(self, tmp_path):
        spec = _make_spec(canary="")
        runner = _mock_runner()
        gate = VerificationGate(
            problem_spec=spec,
            runner=runner,
            strict_runtime_checks=True,
        )
        patch = _make_patch(_VALID_CODE)
        result = gate.run(str(tmp_path), str(tmp_path), patch)
        assert result.passed is False
        assert result.first_failure == "V_runtime_config"
        assert "canary_case_path" in result.checks[-1].detail

    def test_strict_runtime_checks_fail_without_champion_workspace(self, tmp_path):
        canary = tmp_path / "small.json"
        canary.write_text("{}")
        spec = _make_spec(canary=str(canary))
        runner = _mock_runner()
        gate = VerificationGate(
            problem_spec=spec,
            runner=runner,
            strict_runtime_checks=True,
        )
        patch = _make_patch(_VALID_CODE)
        result = gate.run(str(tmp_path), str(tmp_path / "missing_champion"), patch)
        assert result.passed is False
        assert result.first_failure == "V_runtime_config"
        assert "champion workspace" in result.checks[-1].detail

    def test_strict_runtime_config_resolves_problem_relative_canary(self, tmp_path):
        from scion.verification.gate import _validate_runtime_config

        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "small.json").write_text("{}")
        spec = _make_spec(canary="data/small.json").model_copy(
            update={"root_dir": str(tmp_path)}
        )

        result = _validate_runtime_config(spec, str(tmp_path))

        assert result is None

    def test_strict_runtime_checks_can_require_adapter(self, tmp_path):
        canary = tmp_path / "small.json"
        canary.write_text("{}")
        spec = _make_spec(canary=str(canary))
        runner = _mock_runner()
        gate = VerificationGate(
            problem_spec=spec,
            runner=runner,
            strict_runtime_checks=True,
            require_adapter_for_runtime=True,
        )
        patch = _make_patch(_VALID_CODE)

        result = gate.run(str(tmp_path), str(tmp_path), patch)

        assert result.passed is False
        assert result.first_failure == "V5_solution_consistency"
        assert "problem adapter" in result.checks[-1].detail

    def test_adapter_backed_problem_v1_without_adapter_fails_v5(self, tmp_path):
        canary = tmp_path / "small.json"
        canary.write_text("{}")
        spec = _make_adapter_required_spec(str(canary))
        runner = _mock_runner(output_dict=_solver_output_dict())
        gate = VerificationGate(problem_spec=spec, runner=runner)

        result = gate.run(str(tmp_path), str(tmp_path), _make_patch(_VALID_CODE))

        assert result.passed is False
        assert result.first_failure == "V5_solution_consistency"
        assert "problem adapter is required" in result.checks[-1].detail
        assert "legacy solution consistency fallback disabled" in result.checks[-1].detail

    def test_selected_surface_runtime_fields_do_not_enable_legacy_v5_fallback(
        self,
        tmp_path,
    ):
        canary = tmp_path / "small.json"
        canary.write_text("{}")
        spec = _make_adapter_required_spec(str(canary)).model_copy(
            update={
                "operator_categories": ["search_policy"],
                "research_surfaces": [
                    {
                        "name": "search_policy",
                        "kind": "operator",
                        "target_files": ["operators/*.py"],
                        "evidence": {
                            "required_runtime_fields": [
                                "policy_loaded",
                                "policy_errors",
                            ],
                        },
                    }
                ],
            }
        )
        output = _solver_output_dict()
        output["runtime"] = {
            "policy_loaded": True,
            "policy_errors": 0,
        }
        runner = _mock_runner(output_dict=output)
        gate = VerificationGate(problem_spec=spec, runner=runner)

        result = gate.run(
            str(tmp_path),
            str(tmp_path),
            _make_patch(_VALID_CODE),
            selected_surface="search_policy",
        )

        assert result.passed is False
        assert result.first_failure == "V5_solution_consistency"
        assert "problem adapter is required" in result.checks[-1].detail
        assert "legacy solution consistency fallback disabled" in result.checks[-1].detail

    def test_strict_adapter_backed_runtime_passes_toy_tsp(self, tmp_path):
        spec_v1, adapter = _load_toy_tsp_adapter()
        canary = os.path.join(spec_v1.root_dir, "data", "tsp_10.json")
        spec = _make_spec(canary=canary).model_copy(update={"root_dir": spec_v1.root_dir})
        runner = _mock_runner(output_dict={"tour": list(range(10))}, elapsed_ms=100)
        gate = VerificationGate(
            problem_spec=spec,
            runner=runner,
            adapter=adapter,
            strict_runtime_checks=True,
            require_adapter_for_runtime=True,
            operator_execute_signature=spec_v1.operator_interface.execute_signature,
        )

        result = gate.run(str(tmp_path), str(tmp_path), _make_toy_tsp_patch())

        assert result.passed is True
        check_names = [c.name for c in result.checks]
        assert "V6_feasibility" in check_names
        assert "V7_objective" in check_names

    def test_gate_uses_problem_defined_interface_signature(self, tmp_path):
        gate = VerificationGate(
            operator_execute_signature="execute(self, solution, instance, rng) -> TspSolution"
        )
        patch = _make_patch(_VALID_CODE)
        result = gate.run(str(tmp_path), "", patch)
        assert result.passed is False
        assert result.first_failure == "V2_interface"

    def test_gate_forwards_hypothesis_surface_to_v2_interface(self, tmp_path):
        gate = VerificationGate(problem_spec=_make_policy_interface_spec())
        patch = _make_patch(_VALID_CODE)

        result = gate.run(
            str(tmp_path),
            "",
            patch,
            hypothesis=_make_hypothesis("search_policy"),
        )

        assert result.passed is False
        assert result.first_failure == "V2_interface"
        assert "is not in target files" in result.checks[-1].detail

    def test_delete_patch_passes_all(self):
        gate = VerificationGate()
        patch = _make_patch(action="delete")
        result = gate.run("/tmp", "", patch)
        assert result.passed is True

    def test_selected_surface_missing_runtime_field_fails_closed(self, tmp_path):
        canary = tmp_path / "small.json"
        canary.write_text("{}")
        spec = _make_surface_spec(
            str(canary),
            [
                {
                    "name": "search_policy",
                    "evidence": {
                        "required_runtime_fields": [
                            "policy_loaded",
                            "policy_errors",
                        ],
                    },
                },
            ],
        )
        runner = _mock_runner(
            output_dict={
                **_solver_output_dict(),
                "runtime": {"policy_loaded": True},
            }
        )
        gate = VerificationGate(problem_spec=spec, runner=runner)

        result = gate.run(
            str(tmp_path),
            str(tmp_path),
            _make_patch(_VALID_CODE),
            selected_surface="search_policy",
        )

        assert result.passed is False
        assert result.first_failure == "V5_solution_consistency"
        assert "failed runtime evidence contract" in result.checks[-1].detail
        assert "missing=policy_errors" in result.checks[-1].detail

    def test_unknown_selected_surface_fails_at_v2_interface(self, tmp_path):
        canary = tmp_path / "small.json"
        canary.write_text("{}")
        spec = _make_surface_spec(
            str(canary),
            [
                {
                    "name": "search_policy",
                    "evidence": {
                        "required_runtime_fields": ["policy_loaded"],
                    },
                },
            ],
        )
        runner = _mock_runner(
            output_dict={
                **_solver_output_dict(),
                "runtime": {"policy_loaded": True},
            }
        )
        gate = VerificationGate(problem_spec=spec, runner=runner)

        result = gate.run(
            str(tmp_path),
            str(tmp_path),
            _make_patch(_VALID_CODE),
            selected_surface="not_declared",
        )

        assert result.passed is False
        assert result.first_failure == "V2_interface"
        assert "is not declared" in result.checks[-1].detail

    def test_hypothesis_change_locus_selects_surface_for_runtime_contract(
        self,
        tmp_path,
    ):
        canary = tmp_path / "small.json"
        canary.write_text("{}")
        spec = _make_surface_spec(
            str(canary),
            [
                {
                    "name": "search_policy",
                    "evidence": {
                        "required_runtime_fields": [
                            "policy_loaded",
                            "policy_errors",
                        ],
                    },
                },
            ],
        )
        runner = _mock_runner(
            output_dict={
                **_solver_output_dict(),
                "runtime": {"policy_loaded": True},
            }
        )
        gate = VerificationGate(problem_spec=spec, runner=runner)

        result = gate.run(
            str(tmp_path),
            str(tmp_path),
            _make_patch(_VALID_CODE),
            hypothesis=_make_hypothesis("search_policy"),
        )

        assert result.passed is False
        assert result.first_failure == "V5_solution_consistency"
        assert "failed runtime evidence contract" in result.checks[-1].detail
        assert "missing=policy_errors" in result.checks[-1].detail

    def test_run_verification_gate_helper_forwards_hypothesis_surface(
        self,
        tmp_path,
    ):
        canary = tmp_path / "small.json"
        canary.write_text("{}")
        spec = _make_surface_spec(
            str(canary),
            [
                {
                    "name": "dispatch_policy",
                    "evidence": {
                        "required_runtime_fields": [
                            "dispatch_executed",
                            "dispatch_errors",
                        ],
                    },
                },
            ],
        )
        runner = _mock_runner(
            output_dict={
                **_solver_output_dict(),
                "runtime": {
                    "dispatch_executed": False,
                    "dispatch_errors": 0,
                },
            }
        )
        gate = VerificationGate(problem_spec=spec, runner=runner)

        result = run_verification_gate(
            gate,
            str(tmp_path),
            str(tmp_path),
            _make_patch(_VALID_CODE),
            hypothesis=_make_hypothesis("dispatch_policy"),
        )

        assert result.passed is False
        assert result.first_failure == "V5_solution_consistency"
        assert "failed=dispatch_executed" in result.checks[-1].detail
