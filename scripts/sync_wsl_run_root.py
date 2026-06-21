#!/usr/bin/env python3
"""Sync a WSL Scion run root to the local mirror and check postrun readiness."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any


REPO_DIR = Path(__file__).resolve().parents[1]
SCION_TOOLS_DIR = REPO_DIR / "scion" / "tools"
DEFAULT_WSL_USER = "xjy-ubuntu"
DEFAULT_WSL_HOST = "127.0.0.1"
DEFAULT_WSL_PORT = 2222
DEFAULT_SSH_KEY = Path("/home/clawd/.ssh/id_ed25519_codex_wsl")
SSH_CONNECT_TIMEOUT_SEC = 10
SSH_SERVER_ALIVE_INTERVAL_SEC = 5
SSH_SERVER_ALIVE_COUNT_MAX = 3
DEFAULT_LOCAL_EXPERIMENTS_ROOT = Path(
    os.environ.get(
        "SCION_LOCAL_EXPERIMENTS_ROOT",
        "/home/clawd/research/scion-experiments",
    )
)
POSTRUN_UNREADY_EXIT = 64
SOURCE_CHECK_FAILED_EXIT = 65
LOCAL_STATUS_FAILED_EXIT = 66


def _ssh_options() -> list[str]:
    return [
        "-o",
        "BatchMode=yes",
        "-o",
        f"ConnectTimeout={SSH_CONNECT_TIMEOUT_SEC}",
        "-o",
        f"ServerAliveInterval={SSH_SERVER_ALIVE_INTERVAL_SEC}",
        "-o",
        f"ServerAliveCountMax={SSH_SERVER_ALIVE_COUNT_MAX}",
        "-o",
        "StrictHostKeyChecking=no",
    ]


def build_source_check_command(
    *,
    wsl_run_root: str,
    wsl_user: str = DEFAULT_WSL_USER,
    wsl_host: str = DEFAULT_WSL_HOST,
    wsl_port: int = DEFAULT_WSL_PORT,
    ssh_key: Path = DEFAULT_SSH_KEY,
) -> list[str]:
    root = _remote_path(wsl_run_root)
    remote_script = (
        f"root={shlex.quote(root)}; "
        f"fail() {{ printf '%s\\n' \"$1\" >&2; exit {SOURCE_CHECK_FAILED_EXIT}; }}; "
        "test -d \"$root\" || fail \"missing WSL run root directory: $root\"; "
        "test -f \"$root/run_status.json\" || fail \"missing root run_status.json: $root\"; "
        "( test -f \"$root/prepared_run_manifest.v1.json\" || "
        "test -f \"$root/campaign/run_status.json\" || "
        "test -f \"$root/campaign/status.json\" ) || "
        "fail \"missing Scion run markers under: $root\"; "
        "printf 'source_root_ok\\n'"
    )
    return [
        "ssh",
        "-i",
        str(ssh_key),
        "-p",
        str(int(wsl_port)),
        *_ssh_options(),
        f"{wsl_user}@{wsl_host}",
        remote_script,
    ]


def build_rsync_command(
    *,
    wsl_run_root: str,
    local_run_root: Path,
    wsl_user: str = DEFAULT_WSL_USER,
    wsl_host: str = DEFAULT_WSL_HOST,
    wsl_port: int = DEFAULT_WSL_PORT,
    ssh_key: Path = DEFAULT_SSH_KEY,
    delete: bool = True,
) -> list[str]:
    command = ["rsync", "-a"]
    if delete:
        command.append("--delete")
    command.extend(
        [
            "-e",
            (
                f"ssh -i {ssh_key} -p {int(wsl_port)} "
                + " ".join(shlex.quote(option) for option in _ssh_options())
            ),
            f"{wsl_user}@{wsl_host}:{_remote_dir(wsl_run_root)}",
            f"{local_run_root}/",
        ]
    )
    return command


def build_postrun_check_command(local_run_root: Path) -> list[str]:
    return [
        sys.executable,
        str(SCION_TOOLS_DIR / "check_postrun_acceptance.py"),
        str(local_run_root),
        "--require-current-run-ready",
        "--format",
        "json",
    ]


def sync_and_check(
    *,
    wsl_run_root: str,
    local_run_root: Path | None = None,
    local_experiments_root: Path = DEFAULT_LOCAL_EXPERIMENTS_ROOT,
    wsl_user: str = DEFAULT_WSL_USER,
    wsl_host: str = DEFAULT_WSL_HOST,
    wsl_port: int = DEFAULT_WSL_PORT,
    ssh_key: Path = DEFAULT_SSH_KEY,
    delete: bool = True,
    execute: bool = False,
    check_source: bool = True,
    check_postrun: bool = True,
) -> dict[str, Any]:
    resolved_local = (
        Path(local_run_root)
        if local_run_root is not None
        else local_experiments_root / run_root_name(wsl_run_root)
    ).expanduser()
    resolved_experiments_root = Path(local_experiments_root).expanduser()
    if execute and delete:
        _ensure_safe_delete_destination(
            local_run_root=resolved_local,
            local_experiments_root=resolved_experiments_root,
        )
    expanded_ssh_key = ssh_key.expanduser()
    source_check_command = build_source_check_command(
        wsl_run_root=wsl_run_root,
        wsl_user=wsl_user,
        wsl_host=wsl_host,
        wsl_port=wsl_port,
        ssh_key=expanded_ssh_key,
    )
    rsync_command = build_rsync_command(
        wsl_run_root=wsl_run_root,
        local_run_root=resolved_local,
        wsl_user=wsl_user,
        wsl_host=wsl_host,
        wsl_port=wsl_port,
        ssh_key=expanded_ssh_key,
        delete=delete,
    )
    postrun_command = build_postrun_check_command(resolved_local)
    report: dict[str, Any] = {
        "schema_version": "scion.wsl_run_root_sync.v1",
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "campaign_state_mutated": False,
        "scheduler_state_mutated": False,
        "promotion_state_mutated": False,
        "wsl_run_root": wsl_run_root,
        "local_run_root": str(resolved_local),
        "execute": bool(execute),
        "source_check_command": source_check_command if check_source else [],
        "rsync_command": rsync_command,
        "postrun_check_command": postrun_command if check_postrun else [],
        "source_check_exit_status": None,
        "rsync_exit_status": None,
        "postrun_check_exit_status": None,
        "postrun_check_skipped": False,
        "postrun_check_skip_reason": None,
        "local_status_check_exit_status": None,
        "local_run_status_summary": None,
    }
    if not execute:
        return report

    if check_source:
        source_result = _run(source_check_command)
        report["source_check_exit_status"] = source_result.returncode
        report["source_check_stdout"] = source_result.stdout
        report["source_check_stderr"] = source_result.stderr
        if source_result.returncode != 0:
            return report

    resolved_local.parent.mkdir(parents=True, exist_ok=True)
    rsync_result = _run(rsync_command)
    report["rsync_exit_status"] = rsync_result.returncode
    report["rsync_stdout"] = rsync_result.stdout
    report["rsync_stderr"] = rsync_result.stderr
    if rsync_result.returncode != 0:
        return report

    report["local_run_status_summary"] = _run_status_summary(
        resolved_local / "run_status.json"
    )
    if not report["local_run_status_summary"].get("available"):
        report["local_status_check_exit_status"] = LOCAL_STATUS_FAILED_EXIT
        report["local_status_check_error"] = "local root run_status.json missing or unreadable"
        return report
    report["local_status_check_exit_status"] = 0
    if not check_postrun:
        report["postrun_check_skipped"] = True
        report["postrun_check_skip_reason"] = "operator_skip_postrun_check"
        return report
    if _is_prepared_only_summary(report["local_run_status_summary"]):
        report["postrun_check_skipped"] = True
        report["postrun_check_skip_reason"] = "prepared_only_not_launched"
        report["postrun_current_run_ready"] = False
        return report

    postrun_result = _run(postrun_command)
    report["postrun_check_exit_status"] = postrun_result.returncode
    report["postrun_check_stdout"] = postrun_result.stdout
    report["postrun_check_stderr"] = postrun_result.stderr
    report["postrun_check_summary"] = _postrun_summary_from_stdout(
        postrun_result.stdout
    )
    report["postrun_current_run_ready"] = report["postrun_check_summary"].get(
        "current_run_analysis_ready"
    )
    return report


def run_root_name(wsl_run_root: str) -> str:
    parts = [
        part
        for part in PurePosixPath(wsl_run_root.replace("\\", "/")).parts
        if part not in {"", "/"}
    ]
    if not parts:
        raise ValueError("wsl_run_root must include a directory name")
    return parts[-1]


def render_text(report: dict[str, Any]) -> str:
    lines = [
        f"WSL_RUN_ROOT={report['wsl_run_root']}",
        f"LOCAL_RUN_ROOT={report['local_run_root']}",
        f"EXECUTE={int(bool(report['execute']))}",
    ]
    if report.get("source_check_command"):
        lines.append(
            "SOURCE_CHECK_COMMAND="
            + _shell_join(report["source_check_command"])
        )
    lines.append("RSYNC_COMMAND=" + _shell_join(report["rsync_command"]))
    if report.get("postrun_check_command"):
        lines.append(
            "POSTRUN_CHECK_COMMAND="
            + _shell_join(report["postrun_check_command"])
        )
    if report.get("source_check_exit_status") is not None:
        lines.append(
            f"SOURCE_CHECK_EXIT_STATUS={report['source_check_exit_status']}"
        )
    if report.get("rsync_exit_status") is not None:
        lines.append(f"RSYNC_EXIT_STATUS={report['rsync_exit_status']}")
    if report.get("local_status_check_exit_status") is not None:
        lines.append(
            "LOCAL_STATUS_CHECK_EXIT_STATUS="
            f"{report['local_status_check_exit_status']}"
        )
    if report.get("local_status_check_error"):
        lines.append(f"LOCAL_STATUS_CHECK_ERROR={report['local_status_check_error']}")
    if report.get("postrun_check_exit_status") is not None:
        lines.append(
            f"POSTRUN_CHECK_EXIT_STATUS={report['postrun_check_exit_status']}"
        )
    if report.get("postrun_check_skipped"):
        lines.append("POSTRUN_CHECK_SKIPPED=1")
        if report.get("postrun_check_skip_reason"):
            lines.append(
                f"POSTRUN_CHECK_SKIP_REASON={report['postrun_check_skip_reason']}"
            )
    if "postrun_current_run_ready" in report:
        lines.append(
            f"POSTRUN_CURRENT_RUN_READY={int(bool(report['postrun_current_run_ready']))}"
        )
    run_status_summary = report.get("local_run_status_summary")
    if isinstance(run_status_summary, dict):
        for key in (
            "status",
            "prepared_only",
            "wrapper_exit_status",
            "campaign_wrapper_exit_status",
            "pre_campaign_completion_preflight",
            "pre_campaign_infra_failure",
            "git_runtime_dirty",
            "git_runtime_commit_mismatch",
            "postrun_acceptance_status",
            "postrun_acceptance_failed",
            "postrun_reports_exit_status",
            "postrun_readiness_exit_status",
            "postrun_status_write_exit_status_markers",
            "wrapper_exit_status_effective_markers",
            "postrun_acceptance_failed_markers",
            "postrun_reports_effective_exit_status_markers",
            "postrun_readiness_effective_exit_status_markers",
        ):
            if key in run_status_summary:
                lines.append(
                    f"LOCAL_RUN_STATUS_{key.upper()}={run_status_summary[key]}"
                )
    postrun_summary = report.get("postrun_check_summary")
    if isinstance(postrun_summary, dict):
        failed_required = postrun_summary.get("failed_required_checks")
        if isinstance(failed_required, list):
            lines.append(
                "POSTRUN_FAILED_REQUIRED_CHECKS="
                + ",".join(str(item) for item in failed_required)
            )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wsl_run_root")
    parser.add_argument("--local-run-root", type=Path)
    parser.add_argument(
        "--local-experiments-root",
        type=Path,
        default=DEFAULT_LOCAL_EXPERIMENTS_ROOT,
    )
    parser.add_argument("--wsl-user", default=DEFAULT_WSL_USER)
    parser.add_argument("--wsl-host", default=DEFAULT_WSL_HOST)
    parser.add_argument("--wsl-port", type=int, default=DEFAULT_WSL_PORT)
    parser.add_argument("--ssh-key", type=Path, default=DEFAULT_SSH_KEY)
    parser.add_argument("--no-delete", action="store_true")
    parser.add_argument("--skip-source-check", action="store_true")
    parser.add_argument("--skip-postrun-check", action="store_true")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually run rsync and the local postrun readiness check.",
    )
    parser.add_argument(
        "--format",
        choices=("json", "text"),
        default="text",
    )
    args = parser.parse_args(argv)

    try:
        report = sync_and_check(
            wsl_run_root=args.wsl_run_root,
            local_run_root=args.local_run_root,
            local_experiments_root=args.local_experiments_root,
            wsl_user=args.wsl_user,
            wsl_host=args.wsl_host,
            wsl_port=args.wsl_port,
            ssh_key=args.ssh_key,
            delete=not args.no_delete,
            execute=args.execute,
            check_source=not args.skip_source_check,
            check_postrun=not args.skip_postrun_check,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(render_text(report), end="")

    if not args.execute:
        return 0
    source_exit = report.get("source_check_exit_status")
    if source_exit not in (None, 0):
        return int(source_exit)
    rsync_exit = report.get("rsync_exit_status")
    if rsync_exit not in (None, 0):
        return int(rsync_exit)
    local_status_exit = report.get("local_status_check_exit_status")
    if local_status_exit not in (None, 0):
        return int(local_status_exit)
    if not args.skip_postrun_check:
        postrun_exit = report.get("postrun_check_exit_status")
        if postrun_exit not in (None, 0):
            return int(postrun_exit)
    return 0


def _remote_dir(path: str) -> str:
    value = _remote_path(path)
    return value + "/"


def _remote_path(path: str) -> str:
    value = path.rstrip("/")
    if not value:
        raise ValueError("wsl_run_root must not be empty")
    return value


def _ensure_safe_delete_destination(
    *,
    local_run_root: Path,
    local_experiments_root: Path,
) -> None:
    if not _path_is_relative_to(
        local_run_root.absolute(),
        local_experiments_root.absolute(),
    ):
        raise ValueError(
            "local_run_root must be inside local_experiments_root "
            "when --execute and --delete are enabled"
        )


def _path_is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
    )


def _postrun_ready_from_stdout(stdout: str) -> bool | None:
    value = _postrun_summary_from_stdout(stdout).get("current_run_analysis_ready")
    return value if isinstance(value, bool) else None


def _is_prepared_only_summary(summary: Any) -> bool:
    return isinstance(summary, dict) and summary.get("prepared_only") is True


def _run_status_summary(path: Path) -> dict[str, Any]:
    status = _read_json_object(path)
    if not status:
        return {
            "available": False,
            "path": str(path),
        }
    keys = (
        "status",
        "prepared_only",
        "wrapper_exit_status",
        "campaign_wrapper_exit_status",
        "pre_campaign_completion_preflight",
        "pre_campaign_infra_failure",
        "git_runtime_dirty",
        "git_runtime_commit_mismatch",
        "postrun_acceptance_status",
        "postrun_acceptance_failed",
        "postrun_reports_exit_status",
        "postrun_readiness_exit_status",
        "postrun_acceptance_report_dir",
        "postrun_acceptance_readiness_path",
    )
    summary = {
        "available": True,
        "path": str(path),
    }
    for key in keys:
        if key in status:
            summary[key] = status.get(key)
    run_root = path.parent
    summary["postrun_status_write_exit_status_markers"] = _line_marker_count(
        run_root / "run.log",
        "POSTRUN_STATUS_WRITE_EXIT_STATUS:",
    )
    summary["wrapper_exit_status_effective_markers"] = _line_marker_count(
        run_root / "exit.txt",
        "WRAPPER_EXIT_STATUS_EFFECTIVE:",
    )
    summary["postrun_acceptance_failed_markers"] = _line_marker_count(
        run_root / "exit.txt",
        "POSTRUN_ACCEPTANCE_FAILED:",
    )
    summary["postrun_reports_effective_exit_status_markers"] = _line_marker_count(
        run_root / "exit.txt",
        "POSTRUN_REPORTS_EFFECTIVE_EXIT_STATUS:",
    )
    summary["postrun_readiness_effective_exit_status_markers"] = _line_marker_count(
        run_root / "exit.txt",
        "POSTRUN_READINESS_EFFECTIVE_EXIT_STATUS:",
    )
    return summary


def _line_marker_count(path: Path, marker: str) -> int:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return 0
    return sum(1 for line in text.splitlines() if line.startswith(marker))


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _postrun_summary_from_stdout(stdout: str) -> dict[str, Any]:
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    ready = payload.get("current_run_analysis_ready")
    summary: dict[str, Any] = {
        "current_run_analysis_ready": bool(ready)
        if ready is not None
        else None,
    }
    for key in (
        "failed_required_checks",
        "failed_checks",
        "failed_optional_checks",
    ):
        value = payload.get(key)
        if isinstance(value, list):
            summary[key] = [str(item) for item in value]
    return summary


def _shell_join(command: list[str]) -> str:
    return " ".join(_shell_quote(part) for part in command)


def _shell_quote(value: str) -> str:
    if not value:
        return "''"
    safe = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-=./:@")
    if all(char in safe for char in value):
        return value
    return "'" + value.replace("'", "'\"'\"'") + "'"


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
