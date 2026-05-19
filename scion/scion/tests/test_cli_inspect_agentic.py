"""Focused tests split from test_cli.py."""

from .cli_test_support import *  # noqa: F401,F403

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
