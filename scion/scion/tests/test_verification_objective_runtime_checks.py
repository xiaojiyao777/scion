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

    def test_adapter_required_spec_without_adapter_fails_before_legacy_fallback(
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
        assert "legacy objective fallback disabled" in r.detail

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

        r = check_objective(
            spec,
            runner,
            str(tmp_path),
            selected_surface="search_policy",
        )

        assert r.passed is False
        assert "solver runtime audit failed" in r.detail
        assert "missing=policy_loaded" in r.detail
        assert "problem adapter is required" not in r.detail


class TestStateleakCheck:
    def test_skipped_when_no_canary(self):
        spec = _make_spec(canary="")
        runner = _mock_runner()
        r = check_nondeterminism(spec, runner, "/tmp")
        assert r.passed is True
        assert "skipped" in r.detail

    def test_deterministic_runs_pass(self, tmp_path):
        canary = str(tmp_path / "small.json")
        Path(canary).write_text("{}")
        spec = _make_spec(canary=canary)
        # Both runs return same objective.
        runner = _mock_runner(output_dict=_solver_output_dict(splits=2, cost=6600))
        r = check_nondeterminism(spec, runner, str(tmp_path))
        # Check passes (even if oracle isn't available — we compare raw JSON objects).
        assert r.name == "V8_nondeterminism"
        assert r.passed is True
        assert r.metadata["comparison_mode"] == "legacy_objective"
        assert r.metadata["adapter_backed"] is False
        assert r.metadata["comparison_equal"] is True

    def test_non_deterministic_runs_fail(self, tmp_path):
        canary = str(tmp_path / "small.json")
        Path(canary).write_text("{}")
        spec = _make_spec(canary=canary)

        call_count = [0]

        def run_solver(workdir, instance_path, seed, time_limit_sec, registry_path):
            call_count[0] += 1
            fd, path = tempfile.mkstemp(suffix=".json")
            os.close(fd)
            # Return different objective on second call.
            splits = 2 if call_count[0] == 1 else 5
            data = _solver_output_dict(splits=splits)
            with open(path, "w") as f:
                json.dump(data, f)
            sol = SolverOutput(
                vehicles=data["vehicles"],
                assignment=data["assignment"],
                objective=data["objective"],
                feasible=True,
            )
            return RunResult(
                success=True, exit_code=0, stdout="", stderr="",
                elapsed_ms=100, output=sol, output_path=path, error_category=None,
            )

        runner = MagicMock()
        runner.run_solver.side_effect = run_solver

        r = check_nondeterminism(spec, runner, str(tmp_path))
        assert r.passed is False
        assert r.name == "V8_nondeterminism"
        # detail is now a JSON string with diff_keys
        detail = json.loads(r.detail)
        assert "diff_keys" in detail
        assert len(detail["diff_keys"]) > 0

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
        assert "legacy nondeterminism fallback disabled" in detail["error"]

    def test_adapter_backed_fails_when_normalized_artifacts_differ(
        self,
        tmp_path,
    ):
        canary = str(tmp_path / "small.json")
        Path(canary).write_text("{}")
        spec = _make_spec(canary=canary)
        runner = _sequential_runner(
            [
                {"routes": [[0, 1, 0]], "objective": {"cost": 10}, "feasible": True},
                {"routes": [[0, 2, 0]], "objective": {"cost": 10}, "feasible": True},
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
        )

        assert r.passed is False
        detail = json.loads(r.detail)
        assert detail["comparison_mode"] == "adapter_canonical_signature"
        assert detail["diff_keys"] == ["normalized_solution"]
        assert detail["run1_signature"]["objective"] == {"cost": 10}
        assert detail["run2_signature"]["objective"] == {"cost": 10}

    def test_adapter_backed_passes_when_raw_output_differs_but_signature_equal(
        self,
        tmp_path,
    ):
        canary = str(tmp_path / "small.json")
        Path(canary).write_text("{}")
        spec = _make_spec(canary=canary)
        runner = _sequential_runner(
            [
                {
                    "routes": [[0, 1, 0]],
                    "objective": {"cost": 10},
                    "feasible": True,
                    "diagnostics": {"nonce": "a"},
                },
                {
                    "routes": [[0, 1, 0]],
                    "objective": {"cost": 10},
                    "feasible": True,
                    "diagnostics": {"nonce": "b"},
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
        )

        assert r.passed is True
        assert "adapter_canonical_signature identical" in r.detail
        assert r.metadata["comparison_mode"] == "adapter_canonical_signature"
        assert r.metadata["adapter_backed"] is True
        assert r.metadata["comparison_equal"] is True

    @pytest.mark.parametrize(
        ("bad_run", "expected_run"),
        [
            (0, "first"),
            (1, "second"),
        ],
    )
    def test_selected_surface_runtime_audit_fails_on_either_run(
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
        assert detail["comparison_mode"] == "runtime_audit"
        assert detail["selected_surface"] == "search_policy"
        assert detail["run"] == expected_run
        assert f"{expected_run} run runtime audit failed" in detail["error"]
        assert "missing=policy_loaded" in detail["error"]
        assert "problem adapter is required" not in detail["error"]


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
            fd, path = tempfile.mkstemp(suffix=".json")
            os.close(fd)
            data = _solver_output_dict()
            with open(path, "w") as f:
                json.dump(data, f)
            return RunResult(
                success=True, exit_code=0, stdout="", stderr="",
                elapsed_ms=ms, output=None, output_path=path, error_category=None,
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

    def test_slow_candidate_fails(self, tmp_path):
        canary = str(tmp_path / "small.json")
        Path(canary).write_text("{}")
        champ_ws = str(tmp_path / "champ")
        Path(champ_ws).mkdir()
        spec = _make_spec(canary=canary)

        # Candidate: 6000ms, Champion: 1000ms → ratio=6 > 5 → fails
        def run_solver(workdir, instance_path, seed, time_limit_sec, registry_path):
            ms = 6000 if workdir != champ_ws else 1000
            fd, path = tempfile.mkstemp(suffix=".json")
            os.close(fd)
            data = _solver_output_dict()
            with open(path, "w") as f:
                json.dump(data, f)
            return RunResult(
                success=True, exit_code=0, stdout="", stderr="",
                elapsed_ms=ms, output=None, output_path=path, error_category=None,
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
            fd, path = tempfile.mkstemp(suffix=".json")
            os.close(fd)
            with open(path, "w") as f:
                json.dump(_solver_output_dict(), f)
            return RunResult(
                success=True, exit_code=0, stdout="", stderr="",
                elapsed_ms=ms, output=None, output_path=path, error_category=None,
            )

        runner = MagicMock()
        runner.run_solver.side_effect = run_solver
        r = check_perf(spec, runner, str(tmp_path), champ_ws, max_slowdown=2.0)
        assert r.passed is False
        assert r.metadata["ratio"] == pytest.approx(3.0)
        assert r.metadata["limit_ratio"] == 2.0
        assert "limit=2x" in r.detail
