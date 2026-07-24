"""Exact thin administrative CLI for one Warehouse W3 installation lifecycle."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Sequence


def _canonical_json(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _require_euid(*, root: bool) -> None:
    effective = os.geteuid()
    if root and effective != 0:
        raise PermissionError("command requires effective UID zero")
    if not root and effective == 0:
        raise PermissionError("command rejects effective UID zero")


def _path(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise argparse.ArgumentTypeError("path must be canonical and absolute")
    return path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="scion-w3-install")
    commands = parser.add_subparsers(dest="command", required=True)

    prepare = commands.add_parser("prepare-candidate")
    prepare.add_argument("--accepted-root", required=True, type=_path)
    prepare.add_argument("--repo-root", required=True, type=_path)
    prepare.add_argument("--launch-commit", required=True)
    prepare.add_argument("--remote-name", required=True)
    prepare.add_argument("--remote-ref", required=True)
    prepare.add_argument("--native-record", required=True, type=_path)
    prepare.add_argument("--python", required=True, type=_path)

    verify_candidate = commands.add_parser("verify-candidate")
    verify_candidate.add_argument("--candidate-root", required=True, type=_path)
    verify_candidate.add_argument("--repo-root", required=True, type=_path)

    apply_root = commands.add_parser("apply-root")
    apply_root.add_argument("--candidate-root", required=True, type=_path)

    verify_installed = commands.add_parser("verify-installed")
    verify_installed.add_argument("--launch-id", required=True)

    authorize = commands.add_parser("record-start-authorization")
    authorize.add_argument("--launch-id", required=True)
    authorize.add_argument("--prospective-intent", required=True, type=_path)
    authorize.add_argument("--recorded-at-utc", required=True)

    start = commands.add_parser("start")
    start.add_argument("--launch-id", required=True)

    inspect = commands.add_parser("inspect-terminal")
    inspect.add_argument("--launch-id", required=True)

    accept = commands.add_parser("accept-terminal")
    accept.add_argument("--launch-id", required=True)
    return parser


def _dispatch(arguments: argparse.Namespace) -> bytes:
    command = arguments.command
    if command == "prepare-candidate":
        _require_euid(root=False)
        from scion.problems.warehouse_delivery.w3_candidate_coordinator import (
            prepare_w3_candidate,
        )

        result = prepare_w3_candidate(
            arguments.accepted_root,
            repo_root=arguments.repo_root,
            launch_commit=arguments.launch_commit,
            remote_name=arguments.remote_name,
            remote_ref=arguments.remote_ref,
            native_record_path=arguments.native_record,
            runtime_python=arguments.python,
        )
        return _canonical_json(
            {
                "candidate_root": str(result.candidate.candidate_root),
                "closure_sha256": result.closure.raw_sha256,
                "gate_path": str(result.gate_path),
                "launch_id": result.candidate.installation.launch_id,
                "selection_key": result.candidate.intent.selection_key,
                "state": "CANDIDATE_CLOSED",
            }
        )
    if command == "verify-candidate":
        _require_euid(root=False)
        from scion.problems.warehouse_delivery.w3_candidate_coordinator import (
            verify_w3_candidate,
        )

        result = verify_w3_candidate(
            arguments.candidate_root,
            repo_root=arguments.repo_root,
        )
        return _canonical_json(
            {
                "candidate_root": str(result.candidate.candidate_root),
                "closure_sha256": result.closure.raw_sha256,
                "launch_id": result.candidate.installation.launch_id,
                "selection_key": result.candidate.intent.selection_key,
                "state": "CANDIDATE_VERIFIED",
            }
        )
    if command == "apply-root":
        _require_euid(root=True)
        from scion.problems.warehouse_delivery.w3_root_coordinator import (
            apply_w3_root_installation,
        )

        result = apply_w3_root_installation(arguments.candidate_root)
        return _canonical_json(
            {
                "launch_id": result.launch_id,
                "state": result.state.value,
            }
        )
    if command == "verify-installed":
        _require_euid(root=True)
        from scion.problems.warehouse_delivery.w3_root_coordinator import (
            verify_installed_w3,
        )

        with verify_installed_w3(arguments.launch_id) as authority:
            return _canonical_json(
                {
                    "installed_acceptance_sha256": (
                        authority.chain.installed_acceptance.raw_sha256
                    ),
                    "installed_replay_sha256": authority.bundle.raw_sha256,
                    "launch_id": authority.chain.installed_acceptance.launch_id,
                    "state": "INSTALLATION_ACCEPTED_NOT_STARTED",
                }
            )
    if command == "record-start-authorization":
        _require_euid(root=True)
        from scion.problems.warehouse_delivery.w3_root_coordinator import (
            record_w3_start_authorization,
        )

        raw = arguments.prospective_intent.read_bytes()
        result = record_w3_start_authorization(
            arguments.launch_id,
            prospective_intent_raw=raw,
            recorded_at_utc=arguments.recorded_at_utc,
        )
        return result.raw
    if command == "start":
        _require_euid(root=True)
        from scion.problems.warehouse_delivery.w3_root_coordinator import start_w3

        return start_w3(arguments.launch_id).raw
    if command == "inspect-terminal":
        from scion.problems.warehouse_delivery.w3_terminal_acceptance import (
            inspect_w3_terminal,
        )

        return inspect_w3_terminal(arguments.launch_id).raw
    if command == "accept-terminal":
        _require_euid(root=True)
        from scion.problems.warehouse_delivery.w3_terminal_acceptance import (
            accept_w3_terminal,
        )

        return accept_w3_terminal(arguments.launch_id).raw
    raise AssertionError("unreachable W3 install command")


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        raw = _dispatch(arguments)
    except Exception as exc:
        print(f"scion-w3-install: {exc}", file=sys.stderr)
        return 1
    sys.stdout.buffer.write(raw)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
