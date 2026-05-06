"""Tests for scion.cli.main — inspect and report subcommands."""
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

import pytest
from typer.testing import CliRunner

from scion.cli.main import app
from scion.core.models import Branch, BranchState, HypothesisRecord
from scion.lineage.registry import LineageRegistry
from scion.lineage.branch_store import BranchStore, HypothesisStore
from scion.proposal.agentic_session import (
    AgenticProposalOutput,
    AgenticProposalStatus,
    AgenticTerminationReason,
    FileAgenticSessionArtifactStore,
)

runner = CliRunner()


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


def _write_minimal_problem(tmp_path: Path) -> Path:
    root_dir = tmp_path / "workspace"
    root_dir.mkdir()
    problem_yaml = tmp_path / "problem.yaml"
    problem_yaml.write_text(
        "\n".join(
            [
                "name: cli-agentic-test",
                f"root_dir: {root_dir}",
                "description: CLI APS wiring test",
                "operator_categories: []",
                "search_space:",
                "  editable: []",
                "  frozen: []",
                "  import_whitelist: []",
            ]
        ),
        encoding="utf-8",
    )
    return problem_yaml


def _write_minimal_problem_v1_package(
    tmp_path: Path,
    *,
    required_python_modules: list[str] | None = None,
) -> Path:
    root_dir = tmp_path / "workspace"
    root_dir.mkdir()
    problem_yaml = tmp_path / "problem.yaml"
    problem_yaml.write_text(
        "\n".join(
            [
                "name: fakecli",
                f"root_dir: {root_dir}",
                "description: CLI problem-v1 preflight test",
                "operator_categories: []",
                "search_space:",
                "  editable: []",
                "  frozen: []",
                "  import_whitelist: []",
            ]
        ),
        encoding="utf-8",
    )

    modules = required_python_modules or []
    module_lines = "\n".join(f"    - {module}" for module in modules)
    runtime_block = (
        "\n".join(
            [
                "runtime_dependencies:",
                "  required_python_modules:",
                module_lines,
            ]
        )
        if modules
        else ""
    )
    problem_v1_yaml = tmp_path / "problem-v1.yaml"
    problem_v1_yaml.write_text(
        "\n".join(
            line
            for line in [
                'spec_version: "problem-v1"',
                "id: fakecli",
                'display_name: "Fake CLI"',
                "root_dir: PLACEHOLDER",
                "description: CLI problem-v1 preflight test",
                "search_space:",
                "  editable: []",
                "  frozen: []",
                "  import_whitelist: []",
                "solver:",
                "  time_limit_sec: 1",
                "  max_iter: 1",
                "parameter_search:",
                "  enabled: false",
                runtime_block,
                "operator_interface:",
                '  base_class_import: "scion.problems.fakecli.operators.base:FakeOperator"',
                '  execute_signature: "execute(self, solution, rng) -> Solution"',
                "  categories: []",
                "objective_policy:",
                "  mode: single",
                "objectives:",
                "  - name: cost",
                "    direction: minimize",
                "    priority: 1",
                "adapter:",
                '  import_path: "scion.problems.fakecli.adapter:FakeAdapter"',
                '  api_version: "v1"',
            ]
            if line
        ),
        encoding="utf-8",
    )
    return problem_yaml


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


def test_inspect_agentic_session_validates_good_artifact(tmp_path: Path) -> None:
    artifact = {
        "schema_version": "agentic-proposal-session.v1",
        "session_id": "session-1",
        "request_id": "request-1",
        "idempotency_key": "aps:stable",
        "status": "completed",
        "termination_reason": "completed",
        "tool_loop_config": {
            "max_steps": 4,
            "max_tool_calls": 4,
            "max_observation_chars": 1000,
            "max_wall_time_sec": 120.0,
            "max_repeated_tool_calls": 2,
        },
        "tool_budget_used": {
            "tool_steps": 0,
            "tool_calls": 0,
            "observation_chars": 0,
        },
        "transcript_digest": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
        "compact_transcript": [],
    }
    artifact_path = tmp_path / "agentic-output.json"
    artifact_path.write_text(json.dumps(artifact), encoding="utf-8")

    result = runner.invoke(
        app,
        ["inspect", "agentic-session", "--artifact", str(artifact_path)],
    )

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["schema_version"] == "agentic-proposal-session.v1"
    assert data["session_id"] == "session-1"
    assert data["request_id"] == "request-1"
    assert data["termination_reason"] == "completed"
    assert data["validation"]["ok"] is True
    assert "compact_transcript" not in data
    assert "idempotency_key" not in data


def test_inspect_agentic_session_rejects_raw_ref_artifact(tmp_path: Path) -> None:
    artifact = {
        "schema_version": "agentic-proposal-session.v1",
        "session_id": "session-1",
        "request_id": "request-1",
        "idempotency_key": "aps:stable",
        "status": "failed",
        "termination_reason": "tool_loop_limit",
        "tool_loop_config": {
            "max_steps": 4,
            "max_tool_calls": 4,
            "max_observation_chars": 1000,
        },
        "tool_budget_used": {
            "tool_steps": 1,
            "tool_calls": 1,
            "observation_chars": 10,
        },
        "transcript_digest": "wrong",
        "compact_transcript": [
            {
                "phase": "diagnose",
                "metadata": {
                    "step_id": "tool-0001",
                    "tool_name": "context.read_problem",
                    "status": "ok",
                    "result_summary": "raw_metrics_ref=/secret/raw.json",
                },
            }
        ],
    }
    artifact_path = tmp_path / "bad-agentic-output.json"
    artifact_path.write_text(json.dumps(artifact), encoding="utf-8")

    result = runner.invoke(
        app,
        ["inspect", "agentic-session", "--artifact", str(artifact_path)],
    )

    assert result.exit_code == 1
    data = json.loads(result.output)
    assert data["validation"]["ok"] is False
    assert any("raw ref marker" in error for error in data["validation"]["errors"])


def test_inspect_agentic_sessions_lists_index_without_transcript(
    tmp_path: Path,
) -> None:
    artifact_dir = tmp_path / "artifacts" / "agentic_proposal_sessions"
    empty_digest = "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945"
    output = AgenticProposalOutput(
        status=AgenticProposalStatus.FAILED,
        session_id="session-list-1",
        campaign_id="camp-1",
        branch_id="branch-1",
        request_id="request-list-1",
        idempotency_key="aps:list",
        termination_reason=AgenticTerminationReason.SESSION_TIMEOUT,
        tool_loop_config={
            "max_steps": 4,
            "max_tool_calls": 4,
            "max_observation_chars": 1000,
            "max_wall_time_sec": 120.0,
            "max_repeated_tool_calls": 2,
        },
        tool_budget_used={
            "tool_steps": 1,
            "tool_calls": 1,
            "observation_chars": 10,
        },
        transcript_digest=empty_digest,
    )
    FileAgenticSessionArtifactStore(artifact_dir).write_output(output)
    output_path = artifact_dir / "session-list-1" / "output.json"
    artifact = json.loads(output_path.read_text(encoding="utf-8"))
    artifact["compact_transcript"] = [
        {
            "phase": "diagnose",
            "metadata": {
                "step_id": "tool-0001",
                "tool_name": "context.read_problem",
                "result_summary": "raw_metrics_ref=/secret/raw.json",
            },
        }
    ]
    output_path.write_text(json.dumps(artifact), encoding="utf-8")

    result = runner.invoke(
        app,
        ["inspect", "agentic-sessions", "--artifact-dir", str(artifact_dir)],
    )

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["sessions"][0]["session_id"] == "session-list-1"
    assert data["sessions"][0]["validation"]["ok"] is False
    rendered = json.dumps(data, sort_keys=True)
    assert "compact_transcript" not in rendered
    assert "context.read_problem" not in rendered
    assert "raw_metrics_ref" not in rendered


def _make_campaign(tmp_path: Path) -> Path:
    """Set up a minimal campaign dir with scion.db and .scion_state.json."""
    campaign_dir = tmp_path / "campaign"
    campaign_dir.mkdir()

    # Write state file
    state = {"problem_name": "test_problem", "campaign_dir": str(campaign_dir), "problem_yaml": "/fake/problem.yaml"}
    (campaign_dir / ".scion_state.json").write_text(json.dumps(state))

    # Create scion.db with some records
    registry = LineageRegistry(str(campaign_dir / "scion.db"))

    branch_store = BranchStore(registry)
    hyp_store = HypothesisStore(registry)

    branch_id = str(uuid.uuid4())
    branch = Branch(
        branch_id=branch_id,
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="abc123",
    )
    branch_store.save(branch)

    hyp_id = str(uuid.uuid4())
    hyp = HypothesisRecord(
        hypothesis_id=hyp_id,
        branch_id=branch_id,
        change_locus="order_level",
        action="modify",
        status="active",
        target_file="operators/move.py",
        hypothesis_text="Test hypothesis text",
    )
    hyp_store.save(hyp)

    # Record an event
    registry.record_event({
        "branch_id": branch_id,
        "hypothesis_id": hyp_id,
        "contract_result": "passed",
        "verification_result": "passed",
        "decision": "continue_explore",
        "decision_reason": "low win rate",
    })

    return campaign_dir, branch_id, hyp_id


class TestInspectCampaign:
    def test_inspect_campaign_outputs_json(self, tmp_path):
        campaign_dir, _, _ = _make_campaign(tmp_path)
        result = runner.invoke(app, ["inspect", "campaign", "--campaign-dir", str(campaign_dir)])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert "total_events" in data
        assert data["total_events"] >= 1

    def test_inspect_campaign_no_db(self, tmp_path):
        result = runner.invoke(app, ["inspect", "campaign", "--campaign-dir", str(tmp_path)])
        assert result.exit_code == 1


class TestInspectBranch:
    def test_inspect_branch_outputs_details(self, tmp_path):
        campaign_dir, branch_id, hyp_id = _make_campaign(tmp_path)
        result = runner.invoke(app, ["inspect", "branch", branch_id, "--campaign-dir", str(campaign_dir)])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["branch_id"] == branch_id
        assert "hypotheses" in data
        assert len(data["hypotheses"]) >= 1
        assert "experiment_events" in data

    def test_inspect_branch_no_db(self, tmp_path):
        result = runner.invoke(app, ["inspect", "branch", "fake-id", "--campaign-dir", str(tmp_path)])
        assert result.exit_code == 1


class TestInspectHypothesis:
    def test_inspect_hypothesis_outputs_record(self, tmp_path):
        campaign_dir, branch_id, hyp_id = _make_campaign(tmp_path)
        result = runner.invoke(app, ["inspect", "hypothesis", hyp_id, "--campaign-dir", str(campaign_dir)])
        assert result.exit_code == 0, result.output
        # Output starts with the hypothesis JSON (may be followed by related events block)
        first_block = result.output.split("\nRelated experiment events:")[0].strip()
        data = json.loads(first_block)
        assert data["hypothesis_id"] == hyp_id
        assert data["status"] == "active"
        assert data["action"] == "modify"

    def test_inspect_hypothesis_not_found(self, tmp_path):
        campaign_dir, _, _ = _make_campaign(tmp_path)
        result = runner.invoke(app, ["inspect", "hypothesis", "nonexistent-id", "--campaign-dir", str(campaign_dir)])
        assert result.exit_code == 1


class TestReportSummary:
    def test_report_summary_outputs_json(self, tmp_path):
        campaign_dir, _, _ = _make_campaign(tmp_path)
        result = runner.invoke(app, ["report", "summary", "--campaign-dir", str(campaign_dir)])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert "total_experiments" in data
        assert "verification_intercept_rate" in data
        assert "screening_pass_rate" in data
        assert "by_decision" in data

    def test_report_summary_write_to_file(self, tmp_path):
        campaign_dir, _, _ = _make_campaign(tmp_path)
        out_file = tmp_path / "summary.json"
        result = runner.invoke(app, [
            "report", "summary", "--campaign-dir", str(campaign_dir), "--output", str(out_file)
        ])
        assert result.exit_code == 0
        assert out_file.exists()
        data = json.loads(out_file.read_text())
        assert "total_experiments" in data


class TestReportFailures:
    def test_report_failures_outputs_json(self, tmp_path):
        campaign_dir, branch_id, _ = _make_campaign(tmp_path)
        # Add a failure event
        registry = LineageRegistry(str(campaign_dir / "scion.db"))
        registry.record_event({
            "branch_id": branch_id,
            "contract_result": "failed",
            "verification_result": "failed",
            "decision": "abandon",
        })
        result = runner.invoke(app, ["report", "failures", "--campaign-dir", str(campaign_dir)])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert "total_failures" in data
        assert "by_type" in data
        assert data["total_failures"] >= 1

    def test_report_failures_empty_db(self, tmp_path):
        campaign_dir, _, _ = _make_campaign(tmp_path)
        result = runner.invoke(app, ["report", "failures", "--campaign-dir", str(campaign_dir)])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["total_failures"] == 0


# ---------------------------------------------------------------------------
# T17b: CLI / Report Polish tests
# ---------------------------------------------------------------------------

class TestReportFamilyDistribution:
    def test_report_includes_family_distribution(self, tmp_path):
        """report summary JSON output includes family_distribution key."""
        campaign_dir, _, _ = _make_campaign(tmp_path)
        result = runner.invoke(app, ["report", "summary", "--campaign-dir", str(campaign_dir)])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert "family_distribution" in data
        # order_level change_locus was set in _make_campaign
        assert "order_level" in data["family_distribution"]
        assert data["family_distribution"]["order_level"] >= 1

    def test_report_includes_verification_failure_breakdown(self, tmp_path):
        """report summary JSON output includes verification_failure_breakdown key."""
        campaign_dir, _, _ = _make_campaign(tmp_path)
        result = runner.invoke(app, ["report", "summary", "--campaign-dir", str(campaign_dir)])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert "verification_failure_breakdown" in data

    def test_report_includes_weight_optimization(self, tmp_path):
        """report summary JSON output includes weight_optimization key (None if no runs)."""
        campaign_dir, _, _ = _make_campaign(tmp_path)
        result = runner.invoke(app, ["report", "summary", "--campaign-dir", str(campaign_dir)])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert "weight_optimization" in data

    def test_report_markdown_flag(self, tmp_path):
        """--markdown flag produces markdown output with section headers."""
        campaign_dir, _, _ = _make_campaign(tmp_path)
        result = runner.invoke(app, ["report", "summary", "--markdown", "--campaign-dir", str(campaign_dir)])
        assert result.exit_code == 0, result.output
        assert "# Campaign Report" in result.output
        assert "## Overview" in result.output


class TestInspectShowsWeights:
    def test_inspect_shows_weights(self, tmp_path):
        """inspect campaign output includes weight_optimization key."""
        campaign_dir, _, _ = _make_campaign(tmp_path)
        result = runner.invoke(app, ["inspect", "campaign", "--campaign-dir", str(campaign_dir)])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert "weight_optimization" in data


class TestPostmortemJsonFlag:
    def _make_summary(self, campaign_dir: Path) -> None:
        summary = {
            "campaign_id": "test-campaign",
            "total_rounds": 5,
            "champion_version": 2,
            "budget_utilization": 0.6,
            "family_coverage": {"order_level": 3, "route_level": 1},
            "verification_failure_breakdown": {"infra": 1},
            "action_locus_coverage": {"modify:order_level": 2},
            "stagnation_signals": [],
            "diagnostics": [],
            "cache_stats": {},
            "steps": [
                {"decision": "promote", "failure_stage": None,
                 "hypothesis": {"action": "modify", "target_file": "op.py", "text": "test"},
                 "protocol_result": {"win_rate": 0.7}},
            ],
        }
        (campaign_dir / "campaign_summary.json").write_text(json.dumps(summary))

    def test_postmortem_json_flag(self, tmp_path):
        """--json flag produces machine-readable JSON output."""
        campaign_dir = tmp_path / "campaign"
        campaign_dir.mkdir()
        self._make_summary(campaign_dir)

        result = runner.invoke(app, ["postmortem", "--json", str(campaign_dir)])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["campaign_id"] == "test-campaign"
        assert data["total_rounds"] == 5
        assert "family_coverage" in data
        assert "stagnation_signals" in data

    def test_postmortem_default_markdown(self, tmp_path):
        """Default postmortem output is markdown."""
        campaign_dir = tmp_path / "campaign"
        campaign_dir.mkdir()
        self._make_summary(campaign_dir)

        result = runner.invoke(app, ["postmortem", str(campaign_dir)])
        assert result.exit_code == 0, result.output
        assert "# Scion Campaign Postmortem" in result.output

    def test_postmortem_comparison_section(self, tmp_path):
        """Postmortem includes comparison section when sibling campaigns exist."""
        campaign_a = tmp_path / "campaign_a"
        campaign_b = tmp_path / "campaign_b"
        campaign_a.mkdir()
        campaign_b.mkdir()
        self._make_summary(campaign_a)
        self._make_summary(campaign_b)

        result = runner.invoke(app, ["postmortem", str(campaign_a)])
        assert result.exit_code == 0, result.output
        assert "Comparison with Other Campaigns" in result.output
        assert "campaign_b" in result.output


class TestCliHelpText:
    def test_cli_help_text(self):
        """scion --help renders without error."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "scion" in result.output.lower()

    def test_inspect_help_text(self):
        """scion inspect --help renders without error."""
        result = runner.invoke(app, ["inspect", "--help"])
        assert result.exit_code == 0

    def test_report_help_text(self):
        """scion report --help renders without error."""
        result = runner.invoke(app, ["report", "--help"])
        assert result.exit_code == 0

    def test_postmortem_help_text(self):
        """scion postmortem --help renders without error."""
        result = runner.invoke(app, ["postmortem", "--help"])
        assert result.exit_code == 0
        assert "--json" in result.output
