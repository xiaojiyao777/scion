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
    assert "--agentic-session-timeout-sec" in result.output


def test_run_help_exposes_force_surface_options() -> None:
    result = runner.invoke(app, ["run", "--help"])

    assert result.exit_code == 0, result.output
    assert "--force-surface" in result.output
    assert "--force-action" in result.output
    assert "--force-target-file" in result.output


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
        ],
    )

    assert result.exit_code == 0, result.output
    kwargs = captured[0]
    assert kwargs["use_agentic_proposal"] is True
    assert kwargs["agentic_artifact_dir"] == str(artifact_dir.resolve())
    assert kwargs["agentic_session_timeout_sec"] == 7.5
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
    source = Path(__file__).resolve().parents[1] / "cli" / "main.py"
    text = source.read_text(encoding="utf-8")

    assert "objective_policy = bridge.objective_policy" in text
    assert "objective_policy=objective_policy" in text
