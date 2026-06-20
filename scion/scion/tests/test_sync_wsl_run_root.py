from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


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
    assert report["rsync_command"][:2] == ["rsync", "-a"]
    assert "--delete" in report["rsync_command"]
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
        if command[0] == "rsync":
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

    assert len(calls) == 2
    assert calls[0][0] == "rsync"
    assert calls[1][0] == sys.executable
    assert report["rsync_exit_status"] == 0
    assert report["postrun_check_exit_status"] == 0
    assert report["postrun_current_run_ready"] is True


def test_sync_wsl_run_root_skips_postrun_check_when_requested(
    tmp_path: Path,
    monkeypatch,
) -> None:
    calls: list[list[str]] = []

    def fake_run(command: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(sync_tool, "_run", fake_run)

    report = sync_tool.sync_and_check(
        wsl_run_root="/wsl/experiments/run-c",
        local_experiments_root=tmp_path,
        execute=True,
        check_postrun=False,
    )

    assert len(calls) == 1
    assert calls[0][0] == "rsync"
    assert report["postrun_check_command"] == []
    assert report["postrun_check_exit_status"] is None


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
