"""Tests for scion.cli.main — inspect and report subcommands."""
from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
from typer.testing import CliRunner

from scion.cli.main import app
from scion.core.models import Branch, BranchState, HypothesisRecord
from scion.lineage.registry import LineageRegistry
from scion.lineage.branch_store import BranchStore, HypothesisStore

runner = CliRunner()


def test_run_help_exposes_disable_early_stop_option() -> None:
    result = runner.invoke(app, ["run", "--help"])

    assert result.exit_code == 0, result.output
    assert "--disable-early-stop" in result.output


def test_run_threads_problem_v1_objective_policy_into_protocol() -> None:
    source = Path(__file__).resolve().parents[1] / "cli" / "main.py"
    text = source.read_text(encoding="utf-8")

    assert "objective_policy = bridge.objective_policy" in text
    assert "objective_policy=objective_policy" in text


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
