"""Focused tests split from test_cli.py."""

from .cli_test_support import *  # noqa: F401,F403

def test_run_help_exposes_disable_early_stop_option() -> None:
    result = runner.invoke(app, ["run", "--help"])

    assert result.exit_code == 0, result.output
    assert "--disable-early-stop" in result.output


def test_run_help_exposes_agentic_proposal_options() -> None:
    result = runner.invoke(app, ["run", "--help"])

    assert result.exit_code == 0, result.output
    assert "--agentic-proposal" in result.output
    assert "--agentic-artifact-dir" in result.output
    assert (
        "--agentic-session-timeout-sec" in result.output
        or "--agentic-session-timeou" in result.output
        or "--agentic-session-tim" in result.output
    )
    assert (
        "--proposal-attempt-limit" in result.output
        or "--proposal-attempt-li" in result.output
    )
    assert "defaults to rounds +" in result.output
    assert "max(6, rounds * 2)" in result.output


def test_run_help_exposes_force_surface_options() -> None:
    result = runner.invoke(app, ["run", "--help"])

    assert result.exit_code == 0, result.output
    assert "--force-surface" in result.output
    assert "--force-action" in result.output
    assert "--force-target-file" in result.output


def test_run_help_exposes_measurement_governance_option() -> None:
    result = runner.invoke(app, ["run", "--help"])

    assert result.exit_code == 0, result.output
    assert (
        "--measurement-governance" in result.output
        or "--measurement-governa" in result.output
    )


def test_run_threads_measurement_governance_into_protocol_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    problem_yaml = _write_minimal_problem(tmp_path)
    captured: list[dict[str, object]] = []

    class FakeCampaignManager:
        def __init__(self, **kwargs: object) -> None:
            captured.append(kwargs)

        def run(self, max_rounds: int = 1000) -> None:
            captured[-1]["max_rounds"] = max_rounds

        def get_state(self) -> dict[str, object]:
            return {
                "n_experiments": 0,
                "champion_version": 1,
                "n_active_branches": 0,
            }

    import scion.core.campaign as campaign_module

    monkeypatch.setattr(campaign_module, "CampaignManager", FakeCampaignManager)

    result = runner.invoke(
        app,
        [
            "run",
            "--mock-llm",
            "--rounds",
            "1",
            "--campaign-dir",
            str(tmp_path / "campaign"),
            "--problem",
            str(problem_yaml),
            "--measurement-governance",
            "record-only",
        ],
    )

    assert result.exit_code == 0, result.output
    protocol_config = captured[0]["protocol_config"]
    assert protocol_config.measurement_governance == "record_only"
    assert captured[0]["max_rounds"] == 1


@pytest.mark.parametrize(
    ("cli_value", "expected_value"),
    [("record-only", "record_only"), ("on", "on")],
)
def test_run_measurement_governance_visible_in_summary_and_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    cli_value: str,
    expected_value: str,
) -> None:
    problem_yaml = _write_minimal_problem(tmp_path)
    campaign_dir = tmp_path / "campaign"

    class FakeCampaignManager:
        def __init__(self, **kwargs: object) -> None:
            self.campaign_dir = Path(str(kwargs["campaign_dir"]))
            self.protocol_config = kwargs["protocol_config"]

        def run(self, max_rounds: int = 1000) -> None:
            self.campaign_dir.mkdir(parents=True, exist_ok=True)
            payload = {
                "campaign_id": "fake-campaign",
                "measurement_governance": self.protocol_config.measurement_governance,
                "measurement_readiness": (
                    self.protocol_config.measurement_readiness.model_dump()
                ),
            }
            (self.campaign_dir / "campaign_summary.json").write_text(
                json.dumps(payload),
                encoding="utf-8",
            )
            (self.campaign_dir / "status.json").write_text(
                json.dumps(payload),
                encoding="utf-8",
            )

        def get_state(self) -> dict[str, object]:
            return {
                "n_experiments": 0,
                "champion_version": 1,
                "n_active_branches": 0,
            }

    import scion.core.campaign as campaign_module

    monkeypatch.setattr(campaign_module, "CampaignManager", FakeCampaignManager)

    result = runner.invoke(
        app,
        [
            "run",
            "--mock-llm",
            "--rounds",
            "1",
            "--campaign-dir",
            str(campaign_dir),
            "--problem",
            str(problem_yaml),
            "--measurement-governance",
            cli_value,
        ],
    )

    assert result.exit_code == 0, result.output
    summary = json.loads(
        (campaign_dir / "campaign_summary.json").read_text(encoding="utf-8")
    )
    status = json.loads((campaign_dir / "status.json").read_text(encoding="utf-8"))
    assert summary["measurement_governance"] == expected_value
    assert status["measurement_governance"] == expected_value
    assert summary["measurement_readiness"]["status"] == "not_ready"
    assert status["measurement_readiness"]["reason_code"] == "missing_measurement"
    assert "calibration_ref" not in summary["measurement_readiness"]
    assert "calibration_ref" not in status["measurement_readiness"]


def test_run_agentic_proposal_threads_config_to_campaign_manager(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    problem_yaml = _write_minimal_problem(tmp_path)
    campaign_dir = tmp_path / "campaign"
    artifact_dir = tmp_path / "aps-artifacts"
    captured: list[dict[str, object]] = []

    class FakeCampaignManager:
        def __init__(self, **kwargs: object) -> None:
            captured.append(kwargs)

        def run(self, max_rounds: int = 1000) -> None:
            captured[-1]["max_rounds"] = max_rounds

        def get_state(self) -> dict[str, object]:
            return {
                "n_experiments": 0,
                "champion_version": 1,
                "n_active_branches": 0,
            }

    import scion.core.campaign as campaign_module

    monkeypatch.setattr(campaign_module, "CampaignManager", FakeCampaignManager)

    result = runner.invoke(
        app,
        [
            "run",
            "--mock-llm",
            "--rounds",
            "1",
            "--campaign-dir",
            str(campaign_dir),
            "--problem",
            str(problem_yaml),
            "--agentic-proposal",
            "--agentic-artifact-dir",
            str(artifact_dir),
            "--agentic-session-timeout-sec",
            "7.5",
            "--proposal-attempt-limit",
            "4",
        ],
    )

    assert result.exit_code == 0, result.output
    kwargs = captured[0]
    assert kwargs["use_agentic_proposal"] is True
    assert kwargs["agentic_artifact_dir"] == str(artifact_dir.resolve())
    assert kwargs["agentic_session_timeout_sec"] == 7.5
    assert kwargs["proposal_attempt_limit"] == 4
    assert kwargs["max_rounds"] == 1


def test_run_agentic_proposal_defaults_to_campaign_subdir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    problem_yaml = _write_minimal_problem(tmp_path)
    campaign_dir = tmp_path / "campaign"
    captured: list[dict[str, object]] = []

    class FakeCampaignManager:
        def __init__(self, **kwargs: object) -> None:
            captured.append(kwargs)

        def run(self, max_rounds: int = 1000) -> None:
            pass

        def get_state(self) -> dict[str, object]:
            return {
                "n_experiments": 0,
                "champion_version": 1,
                "n_active_branches": 0,
            }

    import scion.core.campaign as campaign_module

    monkeypatch.setattr(campaign_module, "CampaignManager", FakeCampaignManager)

    result = runner.invoke(
        app,
        [
            "run",
            "--mock-llm",
            "--rounds",
            "1",
            "--campaign-dir",
            str(campaign_dir),
            "--problem",
            str(problem_yaml),
            "--agentic-proposal",
        ],
    )

    assert result.exit_code == 0, result.output
    kwargs = captured[0]
    assert kwargs["use_agentic_proposal"] is True
    assert kwargs["agentic_artifact_dir"] == str(campaign_dir.resolve() / "agentic_sessions")
    assert kwargs["agentic_session_timeout_sec"] is None


def test_run_leaves_agentic_proposal_disabled_by_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    problem_yaml = _write_minimal_problem(tmp_path)
    captured: list[dict[str, object]] = []

    class FakeCampaignManager:
        def __init__(self, **kwargs: object) -> None:
            captured.append(kwargs)

        def run(self, max_rounds: int = 1000) -> None:
            pass

        def get_state(self) -> dict[str, object]:
            return {
                "n_experiments": 0,
                "champion_version": 1,
                "n_active_branches": 0,
            }

    import scion.core.campaign as campaign_module

    monkeypatch.setattr(campaign_module, "CampaignManager", FakeCampaignManager)

    result = runner.invoke(
        app,
        [
            "run",
            "--mock-llm",
            "--rounds",
            "1",
            "--campaign-dir",
            str(tmp_path / "campaign"),
            "--problem",
            str(problem_yaml),
        ],
    )

    assert result.exit_code == 0, result.output
    kwargs = captured[0]
    assert kwargs["use_agentic_proposal"] is False
    assert kwargs["agentic_artifact_dir"] is None
    assert kwargs["agentic_session_timeout_sec"] is None


def test_run_writes_wrapper_audit_status_and_exit_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    problem_yaml = _write_minimal_problem(tmp_path)
    campaign_dir = tmp_path / "campaign"

    class FakeCampaignManager:
        def __init__(self, **kwargs: object) -> None:
            pass

        def run(self, max_rounds: int = 1000) -> None:
            pass

        def get_state(self) -> dict[str, object]:
            return {
                "n_experiments": 0,
                "champion_version": 1,
                "n_active_branches": 0,
            }

    import scion.core.campaign as campaign_module

    monkeypatch.setattr(campaign_module, "CampaignManager", FakeCampaignManager)

    result = runner.invoke(
        app,
        [
            "run",
            "--mock-llm",
            "--rounds",
            "1",
            "--campaign-dir",
            str(campaign_dir),
            "--problem",
            str(problem_yaml),
        ],
    )

    assert result.exit_code == 0, result.output
    audit = json.loads((campaign_dir / "run_status.json").read_text(encoding="utf-8"))
    exit_text = (campaign_dir / "exit.txt").read_text(encoding="utf-8")
    assert audit["schema"] == "scion.run_wrapper_audit.v1"
    assert audit["status"] == "finished"
    assert audit["wrapper_exit_status"] == 0
    assert audit["wrapper_signal"] is None
    assert audit["run_pid"]
    assert audit["started_at"]
    assert audit["ended_at"]
    assert "stdout" in audit
    assert "stderr" in audit
    assert "WRAPPER_EXIT_STATUS:0" in exit_text
    assert "RUN_PID:" in exit_text


def test_run_closes_llm_client_after_campaign_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    problem_yaml = _write_minimal_problem(tmp_path)
    closed: list[str] = []

    class ClosingMockLLMClient:
        def __init__(self, mode: str = "success") -> None:
            self.mode = mode

        def close(self) -> None:
            closed.append(self.mode)

    class FakeCampaignManager:
        def __init__(self, **kwargs: object) -> None:
            pass

        def run(self, max_rounds: int = 1000) -> None:
            pass

        def get_state(self) -> dict[str, object]:
            return {
                "n_experiments": 0,
                "champion_version": 1,
                "n_active_branches": 0,
            }

    import scion.core.campaign as campaign_module
    import scion.proposal.mock_client as mock_client_module

    monkeypatch.setattr(campaign_module, "CampaignManager", FakeCampaignManager)
    monkeypatch.setattr(mock_client_module, "MockLLMClient", ClosingMockLLMClient)

    result = runner.invoke(
        app,
        [
            "run",
            "--mock-llm",
            "--rounds",
            "1",
            "--campaign-dir",
            str(tmp_path / "campaign"),
            "--problem",
            str(problem_yaml),
        ],
    )

    assert result.exit_code == 0, result.output
    assert closed == ["success"]


def test_run_closes_llm_client_when_campaign_raises(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    problem_yaml = _write_minimal_problem(tmp_path)
    closed: list[str] = []

    class ClosingMockLLMClient:
        def __init__(self, mode: str = "success") -> None:
            self.mode = mode

        def close(self) -> None:
            closed.append(self.mode)

    class FakeCampaignManager:
        def __init__(self, **kwargs: object) -> None:
            pass

        def run(self, max_rounds: int = 1000) -> None:
            raise RuntimeError("boom")

    import scion.core.campaign as campaign_module
    import scion.proposal.mock_client as mock_client_module

    monkeypatch.setattr(campaign_module, "CampaignManager", FakeCampaignManager)
    monkeypatch.setattr(mock_client_module, "MockLLMClient", ClosingMockLLMClient)

    result = runner.invoke(
        app,
        [
            "run",
            "--mock-llm",
            "--rounds",
            "1",
            "--campaign-dir",
            str(tmp_path / "campaign"),
            "--problem",
            str(problem_yaml),
        ],
    )

    assert result.exit_code == 1
    assert closed == ["success"]


def test_run_returns_nonzero_for_incomplete_infra_stop(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    problem_yaml = _write_minimal_problem(tmp_path)
    campaign_dir = tmp_path / "campaign"

    class FakeCampaignManager:
        def __init__(self, **kwargs: object) -> None:
            self.campaign_dir = Path(str(kwargs["campaign_dir"]))

        def run(self, max_rounds: int = 1000) -> None:
            self.campaign_dir.mkdir(parents=True, exist_ok=True)
            (self.campaign_dir / "campaign_summary.json").write_text(
                json.dumps(
                    {
                        "stopped_reason": "api_balance_exhausted",
                        "last_stop_reason": "api_balance_exhausted",
                        "requested_rounds": 12,
                        "effective_rounds_completed": 6,
                        "completed_requested_rounds": False,
                        "run_complete": False,
                        "stop_category": "provider_error",
                        "run_validity_status": "valid_partial_interrupted",
                        "run_validity": {
                            "status": "valid",
                            "reason": "valid_partial_interrupted",
                            "valid": True,
                            "requested_rounds": 12,
                            "effective_rounds_completed": 6,
                            "completed_requested_rounds": False,
                            "complete": False,
                            "interrupted": True,
                            "completeness_status": "interrupted_incomplete",
                            "stopped_reason": "api_balance_exhausted",
                            "infra_failure_attempts": 1,
                        },
                    }
                ),
                encoding="utf-8",
            )

        def get_state(self) -> dict[str, object]:
            raise AssertionError("incomplete infra exit should not read final state")

    import scion.core.campaign as campaign_module

    monkeypatch.setattr(campaign_module, "CampaignManager", FakeCampaignManager)

    result = runner.invoke(
        app,
        [
            "run",
            "--mock-llm",
            "--rounds",
            "12",
            "--campaign-dir",
            str(campaign_dir),
            "--problem",
            str(problem_yaml),
        ],
    )

    assert result.exit_code == 20, result.output
    audit = json.loads((campaign_dir / "run_status.json").read_text(encoding="utf-8"))
    exit_text = (campaign_dir / "exit.txt").read_text(encoding="utf-8")
    assert audit["status"] == "incomplete"
    assert audit["wrapper_exit_status"] == 20
    assert audit["campaign_exit_status"] == "incomplete_infra_stop"
    assert audit["run_validity_status"] == "valid_partial_interrupted"
    assert audit["run_complete"] is False
    assert audit["completed_requested_rounds"] is False
    assert audit["last_stop_reason"] == "api_balance_exhausted"
    assert "WRAPPER_EXIT_STATUS:20" in exit_text
    assert "CAMPAIGN_EXIT_STATUS:incomplete_infra_stop" in exit_text
    assert "LAST_STOP_REASON:api_balance_exhausted" in exit_text


def test_run_force_surface_threads_validated_request_to_campaign_manager(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    problem_yaml = _write_minimal_problem_v1_package(
        tmp_path,
        research_surfaces_block=_FORCE_SURFACE_BLOCK,
    )
    captured: list[dict[str, object]] = []
    fake_adapter = object()

    class FakeCampaignManager:
        def __init__(self, **kwargs: object) -> None:
            captured.append(kwargs)

        def run(self, max_rounds: int = 1000) -> None:
            captured[-1]["max_rounds"] = max_rounds

        def get_state(self) -> dict[str, object]:
            return {
                "n_experiments": 0,
                "champion_version": 1,
                "n_active_branches": 0,
            }

    import scion.core.campaign as campaign_module
    import scion.problem.loader as loader_module
    import scion.problem.preflight as preflight_module

    monkeypatch.setattr(loader_module, "load_problem_adapter", lambda spec: fake_adapter)
    monkeypatch.setattr(preflight_module, "run_runtime_preflight", lambda *args, **kwargs: None)
    monkeypatch.setattr(campaign_module, "CampaignManager", FakeCampaignManager)

    result = runner.invoke(
        app,
        [
            "run",
            "--mock-llm",
            "--rounds",
            "1",
            "--campaign-dir",
            str(tmp_path / "campaign"),
            "--problem",
            str(problem_yaml),
            "--allow-skeleton",
            "--force-surface",
            "algorithm_blueprint",
        ],
    )

    assert result.exit_code == 0, result.output
    kwargs = captured[0]
    assert kwargs["force_surface"] == "algorithm_blueprint"
    assert kwargs["force_action"] == "modify"
    assert kwargs["force_target_file"] == "policies/algorithm_blueprint.py"
    assert kwargs["max_rounds"] == 1
    assert "force_surface=algorithm_blueprint" in result.output


def test_run_force_surface_rejects_unknown_before_campaign_launch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    problem_yaml = _write_minimal_problem_v1_package(
        tmp_path,
        research_surfaces_block=_FORCE_SURFACE_BLOCK,
    )

    class FakeCampaignManager:
        def __init__(self, **kwargs: object) -> None:
            raise AssertionError("CampaignManager should not be constructed")

    import scion.core.campaign as campaign_module
    import scion.problem.loader as loader_module
    import scion.problem.preflight as preflight_module

    monkeypatch.setattr(
        loader_module,
        "load_problem_adapter",
        lambda spec: pytest.fail("adapter should not be loaded"),
    )
    monkeypatch.setattr(preflight_module, "run_runtime_preflight", lambda *args, **kwargs: None)
    monkeypatch.setattr(campaign_module, "CampaignManager", FakeCampaignManager)

    result = runner.invoke(
        app,
        [
            "run",
            "--mock-llm",
            "--rounds",
            "1",
            "--campaign-dir",
            str(tmp_path / "campaign"),
            "--problem",
            str(problem_yaml),
            "--force-surface",
            "missing_surface",
        ],
    )

    assert result.exit_code == 1
    assert "invalid --force-surface" in result.output
    assert "missing_surface" in result.output
    assert "algorithm_blueprint" in result.output


def test_run_problem_v1_calls_runtime_preflight(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    problem_yaml = _write_minimal_problem_v1_package(
        tmp_path,
        required_python_modules=["sys"],
    )
    captured_preflight: list[tuple[str, bool]] = []
    captured_campaign: list[dict[str, object]] = []
    fake_adapter = object()

    def fake_preflight(spec: object, adapter: object | None = None) -> object:
        captured_preflight.append((getattr(spec, "id", ""), adapter is fake_adapter))
        return object()

    class FakeCampaignManager:
        def __init__(self, **kwargs: object) -> None:
            captured_campaign.append(kwargs)

        def run(self, max_rounds: int = 1000) -> None:
            pass

        def get_state(self) -> dict[str, object]:
            return {
                "n_experiments": 0,
                "champion_version": 1,
                "n_active_branches": 0,
            }

    import scion.core.campaign as campaign_module
    import scion.problem.loader as loader_module
    import scion.problem.preflight as preflight_module

    monkeypatch.setattr(loader_module, "load_problem_adapter", lambda spec: fake_adapter)
    monkeypatch.setattr(preflight_module, "run_runtime_preflight", fake_preflight)
    monkeypatch.setattr(campaign_module, "CampaignManager", FakeCampaignManager)

    result = runner.invoke(
        app,
        [
            "run",
            "--mock-llm",
            "--rounds",
            "1",
            "--campaign-dir",
            str(tmp_path / "campaign"),
            "--problem",
            str(problem_yaml),
            "--allow-skeleton",
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured_preflight == [("fakecli", False), ("fakecli", True)]
    assert captured_campaign[0]["adapter"] is fake_adapter


def test_run_problem_v1_missing_dependency_stops_before_campaign(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    missing = "scion_missing_cli_preflight_dependency_987654321"
    problem_yaml = _write_minimal_problem_v1_package(
        tmp_path,
        required_python_modules=[missing],
    )

    class FakeCampaignManager:
        def __init__(self, **kwargs: object) -> None:
            raise AssertionError("CampaignManager should not be constructed")

    import scion.core.campaign as campaign_module
    import scion.problem.loader as loader_module

    monkeypatch.setattr(
        loader_module,
        "load_problem_adapter",
        lambda spec: pytest.fail("adapter should not be loaded"),
    )
    monkeypatch.setattr(campaign_module, "CampaignManager", FakeCampaignManager)

    result = runner.invoke(
        app,
        [
            "run",
            "--mock-llm",
            "--rounds",
            "1",
            "--campaign-dir",
            str(tmp_path / "campaign"),
            "--problem",
            str(problem_yaml),
        ],
    )

    assert result.exit_code == 1
    assert missing in result.output
    assert sys.executable in result.output
    assert "runtime dependency preflight failed" in result.output


def test_run_threads_problem_v1_objective_policy_into_protocol() -> None:
    source = Path(__file__).resolve().parents[1] / "cli" / "commands" / "init_run.py"
    text = source.read_text(encoding="utf-8")

    assert "objective_policy = bridge.objective_policy" in text
    assert "objective_policy=objective_policy" in text


def test_weight_optimization_resolves_problem_v1_measurement_into_protocol() -> None:
    source = Path(__file__).resolve().parents[1] / "cli" / "commands" / "weights.py"
    text = source.read_text(encoding="utf-8")

    assert "problem_v1 = None" in text
    assert "with_problem_measurement(problem_v1 or spec)" in text
