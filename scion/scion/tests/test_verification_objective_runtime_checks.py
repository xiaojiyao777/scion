"""Focused tests split from test_verification.py."""

from .verification_test_support import *  # noqa: F401,F403

class TestObjectiveCheck:
    def test_skipped_when_no_canary(self):
        spec = _make_spec(canary="")
        runner = _mock_runner()
        r = check_objective(spec, runner, "/tmp")
        assert r.passed is True
        assert "skipped" in r.detail

    def test_skipped_when_canary_not_found(self):
        spec = _make_spec(canary="/no/such/file.json")
        runner = _mock_runner()
        r = check_objective(spec, runner, "/tmp")
        assert r.passed is True
        assert "skipped" in r.detail

    def test_solver_failure_fails(self, tmp_path):
        canary = str(tmp_path / "small.json")
        Path(canary).write_text("{}")
        spec = _make_spec(canary=canary)
        runner = _mock_runner(success=False)
        r = check_objective(spec, runner, str(tmp_path))
        assert r.passed is False
        assert r.name == "V7_objective"

    def test_solver_runtime_audit_failure_fails(self, tmp_path):
        canary = str(tmp_path / "small.json")
        Path(canary).write_text("{}")
        spec = _make_spec(canary=canary)
        output = _solver_output_dict()
        output["runtime"] = {"operator_errors": 1}
        runner = _mock_runner(output_dict=output)

        r = check_objective(spec, runner, str(tmp_path))

        assert r.passed is False
        assert "solver runtime audit failed" in r.detail

    def test_adapter_required_spec_without_adapter_fails_closed(
        self,
        tmp_path,
    ):
        canary = str(tmp_path / "small.json")
        Path(canary).write_text("{}")
        (tmp_path / "oracle.py").write_text(
            "def recompute_solver_output_objective(raw, canary):\n"
            "    raise AssertionError('legacy oracle should not be called')\n"
        )
        spec = _make_adapter_required_spec(canary).model_copy(
            update={"root_dir": str(tmp_path), "oracle_path": "oracle.py"}
        )
        runner = _mock_runner(output_dict=_solver_output_dict())

        r = check_objective(spec, runner, str(tmp_path))

        assert r.passed is False
        assert r.name == "V7_objective"
        assert "problem adapter is required" in r.detail

    def test_adapter_declared_objective_missing_from_solver_output_fails(
        self,
        tmp_path,
    ):
        canary = str(tmp_path / "small.json")
        Path(canary).write_text("{}")
        spec = _with_objectives(_make_spec(canary=canary), "cost", "penalty")
        runner = _mock_runner(
            output_dict={
                "objective": {"penalty": 0},
                "feasible": True,
            }
        )

        class ObjectiveAdapter:
            def load_instance(self, instance_path):
                return {"path": instance_path}

            def deserialize_solver_output(self, raw_output, instance):
                return SolverArtifact(
                    raw_output=raw_output,
                    objective=dict(raw_output.get("objective", {})),
                    feasible=True,
                    normalized_solution={},
                )

            def recompute_objective(self, artifact, instance):
                return {"cost": 10, "penalty": 0}

        r = check_objective(
            spec,
            runner,
            str(tmp_path),
            adapter=ObjectiveAdapter(),
        )

        assert r.passed is False
        assert "solver objective missing declared metrics: cost" in r.detail

    def test_adapter_declared_objective_missing_from_recomputation_fails(
        self,
        tmp_path,
    ):
        canary = str(tmp_path / "small.json")
        Path(canary).write_text("{}")
        spec = _with_objectives(_make_spec(canary=canary), "cost", "penalty")
        runner = _mock_runner(
            output_dict={
                "objective": {"cost": 10, "penalty": 0},
                "feasible": True,
            }
        )

        class ObjectiveAdapter:
            def load_instance(self, instance_path):
                return {"path": instance_path}

            def deserialize_solver_output(self, raw_output, instance):
                return SolverArtifact(
                    raw_output=raw_output,
                    objective=dict(raw_output.get("objective", {})),
                    feasible=True,
                    normalized_solution={},
                )

            def recompute_objective(self, artifact, instance):
                return {"cost": 10}

        r = check_objective(
            spec,
            runner,
            str(tmp_path),
            adapter=ObjectiveAdapter(),
        )

        assert r.passed is False
        assert "adapter recomputation missing declared metrics: penalty" in r.detail

    def test_selected_surface_missing_runtime_field_does_not_preempt_adapter_required(
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

        r = check_objective(
            spec,
            runner,
            str(tmp_path),
            selected_surface="search_policy",
        )

        assert r.passed is False
        assert "solver runtime audit failed" not in r.detail
        assert "problem adapter is required" in r.detail


class TestStateleakCheck:
    def test_skipped_when_no_canary(self):
        spec = _make_spec(canary="")
        runner = _mock_runner()
        r = check_nondeterminism(spec, runner, "/tmp")
        assert r.passed is True
        assert "skipped" in r.detail

    def test_adapter_required_spec_without_adapter_fails_closed(self, tmp_path):
        canary = str(tmp_path / "small.json")
        Path(canary).write_text("{}")
        spec = _make_adapter_required_spec(canary)
        runner = _mock_runner(output_dict=_solver_output_dict())

        r = check_nondeterminism(spec, runner, str(tmp_path))

        assert r.passed is False
        assert r.name == "V8_nondeterminism"
        detail = json.loads(r.detail)
        assert detail["comparison_mode"] == "adapter_required_missing"
        assert detail["selected_surface"] is None
        assert "problem adapter is required" in detail["error"]

    def test_adapter_backed_fails_when_normalized_artifacts_differ(
        self,
        tmp_path,
    ):
        canary = str(tmp_path / "small.json")
        Path(canary).write_text("{}")
        spec = _make_spec(canary=canary)
        metrics_dir = tmp_path / "metrics"
        metrics_dir.mkdir()
        runtime_summary = {
            "solver_algorithm_actionability_summary": {
                "schema": "scion.cvrp.solver_actionability.v1",
                "attempted": True,
                "accepted_moves": 1,
            }
        }
        runner = _sequential_runner(
            [
                {
                    "routes": [[0, 1, "run1-solution-secret", 0]],
                    "objective": {"cost": 10},
                    "feasible": True,
                    "runtime": runtime_summary,
                },
                {
                    "routes": [[0, 2, "run2-solution-secret", 0]],
                    "objective": {"cost": 10},
                    "feasible": True,
                    "runtime": runtime_summary,
                },
            ]
        )

        class RouteAdapter:
            def load_instance(self, instance_path):
                return {"path": instance_path}

            def deserialize_solver_output(self, raw_output, instance):
                return SolverArtifact(
                    raw_output=raw_output,
                    objective=dict(raw_output.get("objective", {})),
                    feasible=bool(raw_output.get("feasible")),
                    normalized_solution=raw_output.get("routes"),
                )

        r = check_nondeterminism(
            spec,
            runner,
            str(tmp_path),
            adapter=RouteAdapter(),
            metrics_dir=str(metrics_dir),
        )

        assert r.passed is False
        detail = json.loads(r.detail)
        assert detail["comparison_mode"] == "adapter_canonical_signature"
        assert detail["diff_keys"] == ["normalized_solution"]
        assert len(detail["run1_signature_digest"]) == 16
        assert len(detail["run2_signature_digest"]) == 16
        assert detail["run1_signature_digest"] != detail["run2_signature_digest"]
        assert "run1_signature" not in detail
        assert "run2_signature" not in detail
        assert "run1-solution-secret" not in r.detail
        assert "run2-solution-secret" not in r.detail
        assert len(r.detail.encode("utf-8")) <= 8 * 1024
        diagnostics = list(metrics_dir.glob("v8_failure_*.json"))
        assert len(diagnostics) == 1
        assert diagnostics[0].stat().st_size <= 8 * 1024
        assert json.loads(diagnostics[0].read_text(encoding="utf-8")) == detail
        assert r.metadata == {"diagnostic_ref": str(diagnostics[0])}

    def test_adapter_backed_passes_when_raw_output_differs_but_signature_equal(
        self,
        tmp_path,
    ):
        canary = str(tmp_path / "small.json")
        Path(canary).write_text("{}")
        spec = _make_spec(canary=canary)
        metrics_dir = tmp_path / "metrics"
        metrics_dir.mkdir()
        runner = _sequential_runner(
            [
                {
                    "routes": [[0, 1, 0]],
                    "objective": {"cost": 10},
                    "feasible": True,
                    "diagnostics": {"nonce": "a"},
                    "runtime": {"large_sequence": ["run1"]},
                },
                {
                    "routes": [[0, 1, 0]],
                    "objective": {"cost": 10},
                    "feasible": True,
                    "diagnostics": {"nonce": "b"},
                    "runtime": {"large_sequence": ["run2"] * 100_000},
                },
            ]
        )

        class RouteAdapter:
            def load_instance(self, instance_path):
                return {"path": instance_path}

            def deserialize_solver_output(self, raw_output, instance):
                return SolverArtifact(
                    raw_output=raw_output,
                    objective=dict(raw_output.get("objective", {})),
                    feasible=bool(raw_output.get("feasible")),
                    normalized_solution=raw_output.get("routes"),
                )

        r = check_nondeterminism(
            spec,
            runner,
            str(tmp_path),
            adapter=RouteAdapter(),
            metrics_dir=str(metrics_dir),
        )

        assert r.passed is True
        assert "adapter_canonical_signature identical" in r.detail
        assert r.metadata["comparison_mode"] == "adapter_canonical_signature"
        assert r.metadata["adapter_backed"] is True
        assert r.metadata["comparison_equal"] is True
        assert not list(metrics_dir.iterdir())

    def test_adapter_exception_failure_detail_is_hard_bounded(self, tmp_path):
        canary = str(tmp_path / "small.json")
        Path(canary).write_text("{}")
        spec = _make_spec(canary=canary)
        runner = _mock_runner(output_dict=_solver_output_dict())
        metrics_dir = tmp_path / "metrics"
        metrics_dir.mkdir()

        class FailingAdapter:
            def load_instance(self, instance_path):
                return {"path": instance_path}

            def deserialize_solver_output(self, raw_output, instance):
                raise ValueError("adapter-secret-" * 10_000)

        result = check_nondeterminism(
            spec,
            runner,
            str(tmp_path),
            adapter=FailingAdapter(),
            metrics_dir=str(metrics_dir),
        )

        assert result.passed is False
        detail = json.loads(result.detail)
        assert detail["comparison_mode"] == "adapter_deserialize"
        assert detail["error"].startswith("adapter deserialize error:")
        assert len(detail["error"]) <= 1024
        assert len(result.detail.encode("utf-8")) <= 8 * 1024
        diagnostic = Path(result.metadata["diagnostic_ref"])
        assert diagnostic.is_file()
        assert diagnostic.stat().st_size <= 8 * 1024
        assert json.loads(diagnostic.read_text(encoding="utf-8")) == detail
        assert "diagnostic_persistence_error" not in result.metadata

    @pytest.mark.parametrize(
        ("bad_run", "expected_run"),
        [
            (0, "first"),
            (1, "second"),
        ],
    )
    def test_selected_surface_runtime_diagnostic_does_not_preempt_adapter_boundary(
        self,
        tmp_path,
        bad_run,
        expected_run,
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
        ok_output = _solver_output_dict()
        ok_output["runtime"] = {"policy_loaded": True}
        bad_output = _solver_output_dict()
        bad_output["runtime"] = {}
        outputs = [ok_output, ok_output]
        outputs[bad_run] = bad_output
        runner = _sequential_runner(outputs)

        r = check_nondeterminism(
            spec,
            runner,
            str(tmp_path),
            selected_surface="search_policy",
        )

        assert r.passed is False
        detail = json.loads(r.detail)
        assert detail["comparison_mode"] == "adapter_required_missing"
        assert detail["selected_surface"] == "search_policy"
        assert "problem adapter is required" in detail["error"]
        assert "runtime audit failed" not in detail["error"]


class TestPerfGuardCheck:
    def test_skipped_when_no_canary(self):
        spec = _make_spec(canary="")
        runner = _mock_runner()
        r = check_perf(spec, runner, "/tmp", "/tmp/champ")
        assert r.passed is True
        assert "skipped" in r.detail

    def test_skipped_when_no_champion_workspace(self, tmp_path):
        canary = str(tmp_path / "small.json")
        Path(canary).write_text("{}")
        spec = _make_spec(canary=canary)
        runner = _mock_runner()
        r = check_perf(spec, runner, str(tmp_path), "")
        assert r.passed is True
        assert "skipped" in r.detail

    def test_fast_candidate_passes(self, tmp_path):
        canary = str(tmp_path / "small.json")
        Path(canary).write_text("{}")
        champ_ws = str(tmp_path / "champ")
        Path(champ_ws).mkdir()
        spec = _make_spec(canary=canary)

        # Candidate: 500ms, Champion: 1000ms → ratio=0.5 → passes
        call_count = [0]
        def run_solver(workdir, instance_path, seed, time_limit_sec, registry_path):
            call_count[0] += 1
            ms = 500 if workdir != champ_ws else 1000
            data = _solver_output_dict()
            return RunResult(
                success=True, exit_code=0, stdout="", stderr="",
                elapsed_ms=ms,
                output=_solver_output_from_dict(data),
                error_category=None,
            )

        runner = MagicMock()
        runner.run_solver.side_effect = run_solver
        r = check_perf(spec, runner, str(tmp_path), champ_ws)
        assert r.passed is True
        assert r.name == "V9_perf_guard"
        assert r.metadata["candidate_ms"] == 500
        assert r.metadata["champion_ms"] == 1000
        assert r.metadata["ratio"] == pytest.approx(0.5)
        assert r.metadata["candidate_timeout"] is False

    def test_runtime_telemetry_diagnostic_is_nonblocking_and_preserved(
        self,
        tmp_path,
    ):
        canary = str(tmp_path / "small.json")
        Path(canary).write_text("{}")
        champ_ws = str(tmp_path / "champ")
        Path(champ_ws).mkdir()
        spec = _make_spec(canary=canary).model_copy(
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

        r = check_perf(
            spec,
            runner,
            str(tmp_path),
            champ_ws,
            selected_surface="search_policy",
        )

        assert r.passed is True
        assert r.metadata["comparison_valid"] is True
        assert (
            r.metadata["candidate_runtime_audit_diagnostic"]["error_category"]
            == "surface_runtime_contract_error"
        )
        assert (
            r.metadata["champion_runtime_audit_diagnostic"]["error_category"]
            == "surface_runtime_contract_error"
        )

    def test_slow_candidate_fails(self, tmp_path):
        canary = str(tmp_path / "small.json")
        Path(canary).write_text("{}")
        champ_ws = str(tmp_path / "champ")
        Path(champ_ws).mkdir()
        spec = _make_spec(canary=canary)

        # Candidate: 6000ms, Champion: 1000ms → ratio=6 > 5 → fails
        def run_solver(workdir, instance_path, seed, time_limit_sec, registry_path):
            ms = 6000 if workdir != champ_ws else 1000
            data = _solver_output_dict()
            return RunResult(
                success=True, exit_code=0, stdout="", stderr="",
                elapsed_ms=ms,
                output=_solver_output_from_dict(data),
                error_category=None,
            )

        runner = MagicMock()
        runner.run_solver.side_effect = run_solver
        r = check_perf(spec, runner, str(tmp_path), champ_ws)
        assert r.passed is False
        assert "too slow" in r.detail
        assert r.metadata["ratio"] == pytest.approx(6.0)
        assert r.metadata["limit_ratio"] == 5.0

    def test_configured_slowdown_limit_is_used(self, tmp_path):
        canary = str(tmp_path / "small.json")
        Path(canary).write_text("{}")
        champ_ws = str(tmp_path / "champ")
        Path(champ_ws).mkdir()
        spec = _make_spec(canary=canary)

        def run_solver(workdir, instance_path, seed, time_limit_sec, registry_path):
            ms = 3000 if workdir != champ_ws else 1000
            data = _solver_output_dict()
            return RunResult(
                success=True, exit_code=0, stdout="", stderr="",
                elapsed_ms=ms,
                output=_solver_output_from_dict(data),
                error_category=None,
            )

        runner = MagicMock()
        runner.run_solver.side_effect = run_solver
        r = check_perf(spec, runner, str(tmp_path), champ_ws, max_slowdown=2.0)
        assert r.passed is False
        assert r.metadata["ratio"] == pytest.approx(3.0)
        assert r.metadata["limit_ratio"] == 2.0
        assert "limit=2x" in r.detail

    def test_configured_timeout_budget_is_used_and_exposed(self, tmp_path):
        canary = str(tmp_path / "small.json")
        Path(canary).write_text("{}")
        champ_ws = str(tmp_path / "champ")
        Path(champ_ws).mkdir()
        spec = _make_spec(canary=canary)
        seen_limits = []

        def run_solver(workdir, instance_path, seed, time_limit_sec, registry_path):
            seen_limits.append(time_limit_sec)
            data = _solver_output_dict()
            return RunResult(
                success=True, exit_code=0, stdout="", stderr="",
                elapsed_ms=100,
                output=_solver_output_from_dict(data),
                error_category=None,
            )

        runner = MagicMock()
        runner.run_solver.side_effect = run_solver
        r = check_perf(spec, runner, str(tmp_path), champ_ws, timeout_sec=17)

        assert r.passed is True
        assert seen_limits == [17, 17]
        assert r.metadata["timeout_sec"] == 17

    def test_strict_champion_failure_is_non_passing(self, tmp_path):
        canary = str(tmp_path / "small.json")
        Path(canary).write_text("{}")
        champ_ws = str(tmp_path / "champ")
        Path(champ_ws).mkdir()
        spec = _make_spec(canary=canary)

        def run_solver(workdir, instance_path, seed, time_limit_sec, registry_path):
            if workdir == champ_ws:
                return RunResult(
                    success=False, exit_code=1, stdout="", stderr="boom",
                    elapsed_ms=50, output=None,
                    error_category="crash",
                )
            data = _solver_output_dict()
            return RunResult(
                success=True, exit_code=0, stdout="", stderr="",
                elapsed_ms=100,
                output=_solver_output_from_dict(data),
                error_category=None,
            )

        runner = MagicMock()
        runner.run_solver.side_effect = run_solver
        r = check_perf(
            spec,
            runner,
            str(tmp_path),
            champ_ws,
            timeout_sec=17,
            strict_runtime_checks=True,
        )

        assert r.passed is False
        assert r.metadata["comparison_valid"] is False
        assert r.metadata["champion_error_category"] == "crash"
        assert "comparison invalid" in r.detail
