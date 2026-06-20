from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


REPO_DIR = Path(__file__).parents[3]
SCION_DIR = REPO_DIR / "scion"
TOOL_PATH = REPO_DIR / "scripts" / "sync_wsl_run_root.py"
SPEC = importlib.util.spec_from_file_location("sync_wsl_run_root", TOOL_PATH)
assert SPEC is not None
sync_tool = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(sync_tool)


def test_sync_wsl_run_root_dry_run_builds_safe_commands(tmp_path: Path) -> None:
    report = sync_tool.sync_and_check(
        wsl_run_root="/home/xjy-ubuntu/research/scion-experiments/run-a",
        local_experiments_root=tmp_path,
        execute=False,
    )

    assert report["schema_version"] == "scion.wsl_run_root_sync.v1"
    assert report["report_only"] is True
    assert report["decision_features_excluded"] is True
    assert report["campaign_state_mutated"] is False
    assert report["execute"] is False
    assert report["local_run_root"] == str(tmp_path / "run-a")
    assert report["source_check_command"][0] == "ssh"
    assert "run-a" in report["source_check_command"][-1]
    source_command = report["source_check_command"]
    assert "ConnectTimeout=10" in source_command
    assert "ServerAliveInterval=5" in source_command
    assert "ServerAliveCountMax=3" in source_command
    assert report["source_check_exit_status"] is None
    assert report["rsync_command"][:2] == ["rsync", "-a"]
    assert "--delete" in report["rsync_command"]
    ssh_transport = report["rsync_command"][report["rsync_command"].index("-e") + 1]
    assert "ConnectTimeout=10" in ssh_transport
    assert "ServerAliveInterval=5" in ssh_transport
    assert "ServerAliveCountMax=3" in ssh_transport
    assert report["rsync_command"][-2] == (
        "xjy-ubuntu@127.0.0.1:"
        "/home/xjy-ubuntu/research/scion-experiments/run-a/"
    )
    assert report["rsync_command"][-1] == f"{tmp_path / 'run-a'}/"
    assert report["postrun_check_command"] == [
        sys.executable,
        str(SCION_DIR / "tools" / "check_postrun_acceptance.py"),
        str(tmp_path / "run-a"),
        "--require-current-run-ready",
        "--format",
        "json",
    ]


def test_sync_wsl_run_root_execute_runs_rsync_then_postrun_check(
    tmp_path: Path,
    monkeypatch,
) -> None:
    calls: list[list[str]] = []

    def fake_run(command: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        if command[0] == "ssh":
            return subprocess.CompletedProcess(
                command, 0, "source_root_ok\n", ""
            )
        if command[0] == "rsync":
            local_dir = Path(command[-1])
            local_dir.mkdir(parents=True, exist_ok=True)
            (local_dir / "run_status.json").write_text(
                json.dumps(
                    {
                        "status": "finished",
                        "prepared_only": False,
                        "wrapper_exit_status": 0,
                        "campaign_wrapper_exit_status": 0,
                        "postrun_acceptance_status": "ready",
                        "postrun_acceptance_failed": False,
                    }
                ),
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, "synced", "")
        return subprocess.CompletedProcess(
            command,
            0,
            json.dumps({"current_run_analysis_ready": True}),
            "",
        )

    monkeypatch.setattr(sync_tool, "_run", fake_run)

    report = sync_tool.sync_and_check(
        wsl_run_root="/wsl/experiments/run-b",
        local_experiments_root=tmp_path,
        execute=True,
    )

    assert len(calls) == 3
    assert calls[0][0] == "ssh"
    assert calls[1][0] == "rsync"
    assert calls[2][0] == sys.executable
    assert report["source_check_exit_status"] == 0
    assert report["rsync_exit_status"] == 0
    assert report["local_run_status_summary"] == {
        "available": True,
        "path": str(tmp_path / "run-b" / "run_status.json"),
        "status": "finished",
        "prepared_only": False,
        "wrapper_exit_status": 0,
        "campaign_wrapper_exit_status": 0,
        "postrun_acceptance_status": "ready",
        "postrun_acceptance_failed": False,
    }
    assert report["postrun_check_exit_status"] == 0
    assert report["postrun_current_run_ready"] is True
    rendered = sync_tool.render_text(report)
    assert "LOCAL_RUN_STATUS_WRAPPER_EXIT_STATUS=0" in rendered
    assert "LOCAL_RUN_STATUS_POSTRUN_ACCEPTANCE_STATUS=ready" in rendered


def test_sync_wsl_run_root_skips_postrun_check_when_requested(
    tmp_path: Path,
    monkeypatch,
) -> None:
    calls: list[list[str]] = []

    def fake_run(command: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        if command[0] == "rsync":
            local_dir = Path(command[-1])
            local_dir.mkdir(parents=True, exist_ok=True)
            (local_dir / "run_status.json").write_text(
                json.dumps(
                    {
                        "status": "finished",
                        "prepared_only": False,
                        "wrapper_exit_status": 64,
                        "pre_campaign_completion_preflight": "failed",
                    }
                ),
                encoding="utf-8",
            )
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(sync_tool, "_run", fake_run)

    report = sync_tool.sync_and_check(
        wsl_run_root="/wsl/experiments/run-c",
        local_experiments_root=tmp_path,
        execute=True,
        check_postrun=False,
    )

    assert len(calls) == 2
    assert calls[0][0] == "ssh"
    assert calls[1][0] == "rsync"
    assert report["postrun_check_command"] == []
    assert report["postrun_check_exit_status"] is None
    assert report["local_run_status_summary"]["wrapper_exit_status"] == 64
    assert report["local_run_status_summary"][
        "pre_campaign_completion_preflight"
    ] == "failed"


def test_sync_wsl_run_root_preserves_postrun_unready_status(
    tmp_path: Path,
    monkeypatch,
) -> None:
    def fake_run(command: list[str]) -> subprocess.CompletedProcess[str]:
        if command[0] == "ssh":
            return subprocess.CompletedProcess(
                command, 0, "source_root_ok\n", ""
            )
        if command[0] == "rsync":
            return subprocess.CompletedProcess(command, 0, "synced", "")
        return subprocess.CompletedProcess(
            command,
            sync_tool.POSTRUN_UNREADY_EXIT,
            json.dumps(
                {
                    "current_run_analysis_ready": False,
                    "failed_required_checks": ["problem_summary_input_consistency"],
                    "failed_checks": [
                        "problem_summary_input_consistency",
                        "research_context_actionability",
                    ],
                }
            ),
            "",
        )

    monkeypatch.setattr(sync_tool, "_run", fake_run)

    report = sync_tool.sync_and_check(
        wsl_run_root="/wsl/experiments/run-unready",
        local_experiments_root=tmp_path,
        execute=True,
    )

    assert report["rsync_exit_status"] == 0
    assert report["postrun_check_exit_status"] == sync_tool.POSTRUN_UNREADY_EXIT
    assert report["postrun_current_run_ready"] is False
    assert report["postrun_check_summary"] == {
        "current_run_analysis_ready": False,
        "failed_required_checks": ["problem_summary_input_consistency"],
        "failed_checks": [
            "problem_summary_input_consistency",
            "research_context_actionability",
        ],
    }
    assert "current_run_analysis_ready" in report["postrun_check_stdout"]
    rendered = sync_tool.render_text(report)
    assert "POSTRUN_CURRENT_RUN_READY=0" in rendered
    assert (
        "POSTRUN_FAILED_REQUIRED_CHECKS=problem_summary_input_consistency"
        in rendered
    )


def test_sync_wsl_run_root_source_check_failure_stops_before_rsync(
    tmp_path: Path,
    monkeypatch,
) -> None:
    calls: list[list[str]] = []

    def fake_run(command: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(
            command,
            sync_tool.SOURCE_CHECK_FAILED_EXIT,
            "",
            "missing root run_status.json",
        )

    monkeypatch.setattr(sync_tool, "_run", fake_run)

    report = sync_tool.sync_and_check(
        wsl_run_root="/wsl/experiments/not-a-run",
        local_experiments_root=tmp_path,
        execute=True,
    )

    assert len(calls) == 1
    assert calls[0][0] == "ssh"
    assert report["source_check_exit_status"] == sync_tool.SOURCE_CHECK_FAILED_EXIT
    assert "missing root run_status" in report["source_check_stderr"]
    assert report["rsync_exit_status"] is None
    assert report["postrun_check_exit_status"] is None


def test_sync_wsl_run_root_rejects_delete_outside_experiments(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="local_run_root must be inside"):
        sync_tool.sync_and_check(
            wsl_run_root="/wsl/experiments/run-outside",
            local_run_root=tmp_path.parent / "outside-run",
            local_experiments_root=tmp_path,
            execute=True,
        )


def test_sync_wsl_run_root_cli_returns_postrun_unready_exit(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    def fake_sync_and_check(**_: object) -> dict[str, object]:
        return {
            "execute": True,
            "rsync_exit_status": 0,
            "postrun_check_exit_status": sync_tool.POSTRUN_UNREADY_EXIT,
        }

    monkeypatch.setattr(sync_tool, "sync_and_check", fake_sync_and_check)

    exit_code = sync_tool.main(
        [
            "/wsl/experiments/run-unready",
            "--local-experiments-root",
            str(tmp_path),
            "--execute",
            "--format",
            "json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == sync_tool.POSTRUN_UNREADY_EXIT
    assert payload["postrun_check_exit_status"] == sync_tool.POSTRUN_UNREADY_EXIT


def test_sync_wsl_run_root_cli_dry_run_json(tmp_path: Path, capsys) -> None:
    exit_code = sync_tool.main(
        [
            "/wsl/experiments/run-d",
            "--local-experiments-root",
            str(tmp_path),
            "--format",
            "json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["execute"] is False
    assert payload["local_run_root"] == str(tmp_path / "run-d")
