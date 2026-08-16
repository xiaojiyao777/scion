"""Focused tests split from test_cli.py."""

import json
from pathlib import Path

from typer.testing import CliRunner

from scion.cli.main import app
from scion.core.execution_outcome import ExecutionOutcome, ExecutionOutcomeRecord
from scion.lineage.registry import LineageRegistry

from .cli_test_support import _make_campaign


runner = CliRunner()


class TestReportSummary:
    def test_report_summary_outputs_json(self, tmp_path):
        campaign_dir, _ = _make_campaign(tmp_path)
        result = runner.invoke(
            app, ["report", "summary", "--campaign-dir", str(campaign_dir)]
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert "total_experiments" in data
        assert "verification_intercept_rate" in data
        assert "screening_pass_rate" in data
        assert "by_decision" in data

    def test_report_summary_write_to_file(self, tmp_path):
        campaign_dir, _ = _make_campaign(tmp_path)
        out_file = tmp_path / "summary.json"
        result = runner.invoke(
            app,
            [
                "report",
                "summary",
                "--campaign-dir",
                str(campaign_dir),
                "--output",
                str(out_file),
            ],
        )
        assert result.exit_code == 0
        assert out_file.exists()
        data = json.loads(out_file.read_text())
        assert "total_experiments" in data


class TestReportFailures:
    def test_report_failures_outputs_json(self, tmp_path):
        campaign_dir, branch_id = _make_campaign(tmp_path)
        # Add one typed Contract rejection.
        registry = LineageRegistry(str(campaign_dir / "scion.db"))
        registry.record_execution_outcome(
            campaign_id="campaign-typed-failure",
            branch_id=branch_id,
            record=ExecutionOutcomeRecord(
                outcome=ExecutionOutcome.RESEARCH_REJECTED,
                reason_code="HYPOTHESIS_CONTRACT_REJECTED",
                detail="contract rejected",
                provenance={"stage": "hypothesis_contract"},
            ),
            event_kind="contract_fail",
            stage="hypothesis_contract",
        )
        result = runner.invoke(
            app, ["report", "failures", "--campaign-dir", str(campaign_dir)]
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert "total_failures" in data
        assert "by_type" in data
        assert data["total_failures"] >= 1

    def test_report_failures_empty_db(self, tmp_path):
        campaign_dir, _ = _make_campaign(tmp_path)
        result = runner.invoke(
            app, ["report", "failures", "--campaign-dir", str(campaign_dir)]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["total_failures"] == 0

    def test_typed_verification_rejection_is_reported(self, tmp_path):
        campaign_dir, branch_id = _make_campaign(tmp_path)
        registry = LineageRegistry(str(campaign_dir / "scion.db"))
        registry.record_execution_outcome(
            campaign_id="campaign-typed-failure",
            branch_id=branch_id,
            record=ExecutionOutcomeRecord(
                outcome=ExecutionOutcome.RESEARCH_REJECTED,
                reason_code="VERIFICATION_LIGHT_REJECTED",
                detail="V1b_undefined_names",
                provenance={
                    "owner": "verification_gate",
                    "stage": "verification",
                    "verification_checks": [
                        {"name": "V1_syntax", "passed": True},
                        {"name": "V1b_undefined_names", "passed": False},
                    ],
                },
            ),
            event_kind="verification_fail",
            stage="verification",
        )

        failures = runner.invoke(
            app,
            ["report", "failures", "--campaign-dir", str(campaign_dir)],
        )
        assert failures.exit_code == 0, failures.output
        failure_data = json.loads(failures.output)
        assert failure_data["total_failures"] == 1
        assert failure_data["by_type"] == {
            "verification:VERIFICATION_LIGHT_REJECTED": 1
        }
        assert failure_data["recent_failures"][0]["event_kind"] == ("verification_fail")

        summary = runner.invoke(
            app,
            ["report", "summary", "--campaign-dir", str(campaign_dir)],
        )
        assert summary.exit_code == 0, summary.output
        summary_data = json.loads(summary.output)
        # _make_campaign contributes one formally evaluated experiment; the
        # typed rejection is the second distinct gate outcome.
        assert summary_data["gate_outcome_events"] == 2
        assert summary_data["contract_gate_outcome_events"] == 2
        assert summary_data["verification_gate_outcome_events"] == 2
        assert summary_data["verification_intercept_rate"] == 0.5
        assert summary_data["verification_failure_breakdown"] == {
            "VERIFICATION_LIGHT_REJECTED": 1
        }

    def test_contract_failure_is_not_a_verification_opportunity(self, tmp_path):
        campaign_dir, branch_id = _make_campaign(tmp_path)
        registry = LineageRegistry(str(campaign_dir / "scion.db"))
        registry.record_execution_outcome(
            campaign_id="campaign-mixed-failures",
            branch_id=branch_id,
            record=ExecutionOutcomeRecord(
                outcome=ExecutionOutcome.RESEARCH_REJECTED,
                reason_code="HYPOTHESIS_CONTRACT_REJECTED",
                detail="hypothesis contract rejected",
            ),
            event_kind="contract_fail",
            stage="contract",
        )
        registry.record_execution_outcome(
            campaign_id="campaign-mixed-failures",
            branch_id=branch_id,
            record=ExecutionOutcomeRecord(
                outcome=ExecutionOutcome.RESEARCH_REJECTED,
                reason_code="VERIFICATION_LIGHT_REJECTED",
                detail="V1b_undefined_names",
                provenance={
                    "verification_checks": [
                        {"name": "V1b_undefined_names", "passed": False}
                    ]
                },
            ),
            event_kind="verification_fail",
            stage="verification",
        )

        result = runner.invoke(
            app,
            ["report", "summary", "--campaign-dir", str(campaign_dir)],
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["gate_outcome_events"] == 3
        assert data["contract_gate_outcome_events"] == 3
        assert data["verification_gate_outcome_events"] == 2
        assert data["contract_intercept_rate"] == 0.3333
        assert data["verification_intercept_rate"] == 0.5


class TestReportDetails:
    def test_report_includes_verification_failure_breakdown(self, tmp_path):
        """report summary JSON output includes verification_failure_breakdown key."""
        campaign_dir, _ = _make_campaign(tmp_path)
        result = runner.invoke(
            app, ["report", "summary", "--campaign-dir", str(campaign_dir)]
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert "verification_failure_breakdown" in data

    def test_report_includes_weight_optimization(self, tmp_path):
        """report summary JSON output includes weight_optimization key (None if no runs)."""
        campaign_dir, _ = _make_campaign(tmp_path)
        result = runner.invoke(
            app, ["report", "summary", "--campaign-dir", str(campaign_dir)]
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert "weight_optimization" in data

    def test_report_markdown_flag(self, tmp_path):
        """--markdown flag produces markdown output with section headers."""
        campaign_dir, _ = _make_campaign(tmp_path)
        result = runner.invoke(
            app,
            ["report", "summary", "--markdown", "--campaign-dir", str(campaign_dir)],
        )
        assert result.exit_code == 0, result.output
        assert "# Campaign Report" in result.output
        assert "## Overview" in result.output
        assert "Contract intercept rate" in result.output
        assert "Verification intercept rate" in result.output
        assert "opportunities" in result.output


class TestInspect:
    def test_inspect_shows_weights(self, tmp_path):
        """inspect campaign output includes weight_optimization key."""
        campaign_dir, _ = _make_campaign(tmp_path)
        result = runner.invoke(
            app, ["inspect", "campaign", "--campaign-dir", str(campaign_dir)]
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert "weight_optimization" in data

    def test_inspect_branch_shows_only_branch_and_ordinary_experiments(
        self, tmp_path
    ):
        campaign_dir, branch_id = _make_campaign(tmp_path)
        registry = LineageRegistry(str(campaign_dir / "scion.db"))
        registry.record_event(
            {
                "branch_id": branch_id,
                "event_kind": "proposal_call",
                "stage": "proposal_hypothesis",
            }
        )

        result = runner.invoke(
            app,
            [
                "inspect",
                "branch",
                branch_id,
                "--campaign-dir",
                str(campaign_dir),
            ],
        )

        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert set(data) == {"branch_id", "experiment_events"}
        assert data["branch_id"] == branch_id
        assert len(data["experiment_events"]) == 1
        assert data["experiment_events"][0]["event_kind"] == "experiment"

    def test_inspect_has_no_hypothesis_identity_command(self):
        help_result = runner.invoke(app, ["inspect", "--help"])
        assert help_result.exit_code == 0, help_result.output
        assert "hypothesis" not in help_result.output.lower()

        removed = runner.invoke(app, ["inspect", "hypothesis", "retired-id"])
        assert removed.exit_code != 0


class TestPostmortemJsonFlag:
    def _make_summary(self, campaign_dir: Path) -> None:
        summary = {
            "campaign_id": "test-campaign",
            "total_rounds": 5,
            "champion_version": 2,
            "family_coverage": {"order_level": 3, "route_level": 1},
            "verification_failure_breakdown": {"infra": 1},
            "action_locus_coverage": {"modify:order_level": 2},
            "diagnostics": [],
            "steps": [
                {
                    "decision": "promote",
                    "failure_stage": None,
                    "hypothesis": {
                        "action": "modify",
                        "target_file": "op.py",
                        "text": "test",
                    },
                    "protocol_result": {"win_rate": 0.7},
                },
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
        assert "cache_stats" not in data

    def test_postmortem_default_markdown(self, tmp_path):
        """Default postmortem output is markdown."""
        campaign_dir = tmp_path / "campaign"
        campaign_dir.mkdir()
        self._make_summary(campaign_dir)

        result = runner.invoke(app, ["postmortem", str(campaign_dir)])
        assert result.exit_code == 0, result.output
        assert "# Scion Campaign Postmortem" in result.output
        assert "LLM Cache Statistics" not in result.output

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
