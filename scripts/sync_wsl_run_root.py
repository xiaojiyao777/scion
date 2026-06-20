#!/usr/bin/env python3
"""Sync a WSL Scion run root to the local mirror and check postrun readiness."""

from __future__ import annotations

import argparse
import json
import os
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
DEFAULT_LOCAL_EXPERIMENTS_ROOT = Path(
    os.environ.get(
        "SCION_LOCAL_EXPERIMENTS_ROOT",
        "/home/clawd/research/scion-experiments",
    )
)
POSTRUN_UNREADY_EXIT = 64


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
                "-o BatchMode=yes -o StrictHostKeyChecking=no"
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
    check_postrun: bool = True,
) -> dict[str, Any]:
    resolved_local = (
        Path(local_run_root)
        if local_run_root is not None
        else local_experiments_root / run_root_name(wsl_run_root)
    ).expanduser()
    rsync_command = build_rsync_command(
        wsl_run_root=wsl_run_root,
        local_run_root=resolved_local,
        wsl_user=wsl_user,
        wsl_host=wsl_host,
        wsl_port=wsl_port,
        ssh_key=ssh_key.expanduser(),
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
        "rsync_command": rsync_command,
        "postrun_check_command": postrun_command if check_postrun else [],
        "rsync_exit_status": None,
        "postrun_check_exit_status": None,
    }
    if not execute:
        return report

    resolved_local.parent.mkdir(parents=True, exist_ok=True)
    rsync_result = _run(rsync_command)
    report["rsync_exit_status"] = rsync_result.returncode
    report["rsync_stdout"] = rsync_result.stdout
    report["rsync_stderr"] = rsync_result.stderr
    if rsync_result.returncode != 0 or not check_postrun:
        return report

    postrun_result = _run(postrun_command)
    report["postrun_check_exit_status"] = postrun_result.returncode
    report["postrun_check_stdout"] = postrun_result.stdout
    report["postrun_check_stderr"] = postrun_result.stderr
    report["postrun_current_run_ready"] = _postrun_ready_from_stdout(
        postrun_result.stdout
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
        "RSYNC_COMMAND=" + _shell_join(report["rsync_command"]),
    ]
    if report.get("postrun_check_command"):
        lines.append(
            "POSTRUN_CHECK_COMMAND="
            + _shell_join(report["postrun_check_command"])
        )
    if report.get("rsync_exit_status") is not None:
        lines.append(f"RSYNC_EXIT_STATUS={report['rsync_exit_status']}")
    if report.get("postrun_check_exit_status") is not None:
        lines.append(
            f"POSTRUN_CHECK_EXIT_STATUS={report['postrun_check_exit_status']}"
        )
    if "postrun_current_run_ready" in report:
        lines.append(
            f"POSTRUN_CURRENT_RUN_READY={int(bool(report['postrun_current_run_ready']))}"
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
    rsync_exit = report.get("rsync_exit_status")
    if rsync_exit not in (None, 0):
        return int(rsync_exit)
    if not args.skip_postrun_check:
        postrun_exit = report.get("postrun_check_exit_status")
        if postrun_exit not in (None, 0):
            return int(postrun_exit)
    return 0


def _remote_dir(path: str) -> str:
    value = path.rstrip("/")
    if not value:
        raise ValueError("wsl_run_root must not be empty")
    return value + "/"


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
    )


def _postrun_ready_from_stdout(stdout: str) -> bool | None:
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    ready = payload.get("current_run_analysis_ready")
    return bool(ready) if ready is not None else None


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
