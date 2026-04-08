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
