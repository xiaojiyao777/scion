from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import scion.problems.warehouse_delivery.w3_candidate_coordinator as candidate_module
import scion.problems.warehouse_delivery.w3_root_coordinator as root_module
import scion.problems.warehouse_delivery.w3_terminal_acceptance as terminal_module
import scion.tools.scion_w3_install as cli

LAUNCH_ID = "1" * 64


def _args(command: str):
    parser = cli._parser()
    values = {
        "prepare-candidate": (
            "--accepted-root /tmp/accepted --repo-root /tmp/repo "
            f"--launch-commit {'2' * 40} --remote-name origin "
            "--remote-ref refs/heads/test --native-record /tmp/native "
            "--python /usr/bin/python3.12"
        ),
        "verify-candidate": ("--candidate-root /tmp/candidate --repo-root /tmp/repo"),
        "apply-root": "--candidate-root /tmp/candidate",
        "verify-installed": f"--launch-id {LAUNCH_ID}",
        "record-start-authorization": (
            f"--launch-id {LAUNCH_ID} --prospective-intent /tmp/intent "
            "--recorded-at-utc 2026-07-23T00:00:00Z"
        ),
        "start": f"--launch-id {LAUNCH_ID}",
        "inspect-terminal": f"--launch-id {LAUNCH_ID}",
        "accept-terminal": f"--launch-id {LAUNCH_ID}",
    }
    return parser.parse_args([command, *values[command].split()])


def test_parser_exposes_exact_eight_commands() -> None:
    parser = cli._parser()
    action = next(item for item in parser._actions if item.dest == "command")
    assert frozenset(action.choices) == {
        "prepare-candidate",
        "verify-candidate",
        "apply-root",
        "verify-installed",
        "record-start-authorization",
        "start",
        "inspect-terminal",
        "accept-terminal",
    }


@pytest.mark.parametrize(
    ("command", "effective_uid"),
    (
        ("prepare-candidate", 0),
        ("verify-candidate", 0),
        ("apply-root", 1001),
        ("verify-installed", 1001),
        ("record-start-authorization", 1001),
        ("start", 1001),
        ("accept-terminal", 1001),
    ),
)
def test_euid_matrix_rejects_before_action(
    command: str,
    effective_uid: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cli.os, "geteuid", lambda: effective_uid)
    with pytest.raises(PermissionError):
        cli._dispatch(_args(command))


def test_candidate_commands_emit_canonical_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = SimpleNamespace(
        candidate_root=Path("/tmp/candidate"),
        installation=SimpleNamespace(launch_id=LAUNCH_ID),
        intent=SimpleNamespace(selection_key="3" * 64),
    )
    result = SimpleNamespace(
        candidate=candidate,
        closure=SimpleNamespace(raw_sha256="4" * 64),
        gate_path=Path("/tmp/gate"),
    )
    monkeypatch.setattr(cli.os, "geteuid", lambda: 1001)
    monkeypatch.setattr(
        candidate_module,
        "prepare_w3_candidate",
        lambda *args, **kwargs: result,
    )
    monkeypatch.setattr(
        candidate_module,
        "verify_w3_candidate",
        lambda *args, **kwargs: result,
    )

    prepared = json.loads(cli._dispatch(_args("prepare-candidate")))
    verified = json.loads(cli._dispatch(_args("verify-candidate")))

    assert prepared["state"] == "CANDIDATE_CLOSED"
    assert verified["state"] == "CANDIDATE_VERIFIED"
    assert prepared["launch_id"] == verified["launch_id"] == LAUNCH_ID


def test_root_and_terminal_commands_return_exact_receipt_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prospective = tmp_path / "prospective.json"
    prospective.write_bytes(b"prospective\n")
    arguments = _args("record-start-authorization")
    arguments.prospective_intent = prospective
    monkeypatch.setattr(cli.os, "geteuid", lambda: 0)
    monkeypatch.setattr(
        root_module,
        "record_w3_start_authorization",
        lambda *args, **kwargs: SimpleNamespace(raw=b"authorized\n"),
    )
    monkeypatch.setattr(
        root_module,
        "start_w3",
        lambda *args, **kwargs: SimpleNamespace(raw=b"started\n"),
    )
    monkeypatch.setattr(
        terminal_module,
        "accept_w3_terminal",
        lambda *args, **kwargs: SimpleNamespace(raw=b"accepted\n"),
    )
    monkeypatch.setattr(
        terminal_module,
        "inspect_w3_terminal",
        lambda *args, **kwargs: SimpleNamespace(raw=b"inspected\n"),
    )

    assert cli._dispatch(arguments) == b"authorized\n"
    assert cli._dispatch(_args("start")) == b"started\n"
    assert cli._dispatch(_args("accept-terminal")) == b"accepted\n"
    assert cli._dispatch(_args("inspect-terminal")) == b"inspected\n"


def test_inspect_terminal_is_read_only_for_nonroot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cli.os, "geteuid", lambda: 1001)
    monkeypatch.setattr(
        terminal_module,
        "inspect_w3_terminal",
        lambda *args, **kwargs: SimpleNamespace(raw=b"report\n"),
    )
    assert cli._dispatch(_args("inspect-terminal")) == b"report\n"
