from __future__ import annotations

import json
from pathlib import Path

import pytest

import scion.problems.warehouse_delivery.w3_terminal_acceptance as terminal
from scion.runtime.execution.external_installation import (
    StartDispatchReceipt,
    StartDispatchState,
)
from scion.problems.warehouse_delivery.w3_terminal_acceptance import (
    WarehouseW3TerminalAcceptance,
    WarehouseW3TerminalAcceptanceError,
    WarehouseW3TerminalReport,
    accept_w3_terminal,
)

LAUNCH_ID = "1" * 64


def _canonical(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode()


def _report_raw(*, classification: str = "PENDING") -> bytes:
    def properties(unit: str) -> dict[str, object]:
        return {
            "Id": unit,
            "InvocationID": "0" * 32,
            "LoadState": "loaded",
            "ActiveState": "inactive",
            "SubState": "dead",
            "Result": "success",
            "ExecMainCode": 0,
            "ExecMainStatus": 0,
        }

    return _canonical(
        {
            "schema": "scion.w3-terminal-report.v1",
            "launch_id": LAUNCH_ID,
            "authority_sha256": "2" * 64,
            "installation_sha256": "3" * 64,
            "installed_acceptance_sha256": "4" * 64,
            "start_issue_sha256": "5" * 64,
            "start_outcome": "START_DISPATCH_UNKNOWN",
            "start_outcome_sha256": None,
            "manager": {
                "unique_owner": ":1.42",
                "boot_id": "12345678-1234-1234-1234-123456789abc",
                "version": "255.4",
            },
            "run_properties": properties(f"scion-w3@{LAUNCH_ID}.service"),
            "close_properties": properties(f"scion-w3-close@{LAUNCH_ID}.service"),
            "nonce_claim_state": "ABSENT",
            "nonce_claim_sha256": "6" * 64,
            "terminal_state": "ABSENT",
            "evidence_count": 0,
            "row_count": 0,
            "classification": classification,
            "artifacts": [],
            "replay_receipt_sha256": None,
            "retry": False,
            "resume": False,
            "reuse": False,
        }
    )


def _acceptance_raw(
    *,
    classification: str = "PRECLAIM_TERMINATION_UNKNOWN",
) -> bytes:
    return _canonical(
        {
            "schema": "scion.w3-terminal-acceptance.v1",
            "launch_id": LAUNCH_ID,
            "report_sha256": "7" * 64,
            "classification": classification,
            "installed_acceptance_sha256": "4" * 64,
            "start_issue_sha256": "5" * 64,
            "retry": False,
            "resume": False,
            "reuse": False,
        }
    )


def test_terminal_report_round_trips_exact_canonical_bytes() -> None:
    raw = _report_raw()
    report = WarehouseW3TerminalReport.from_bytes(raw)

    assert report.raw == raw
    assert report.launch_id == LAUNCH_ID
    assert report.classification == "PENDING"
    assert report.run_properties["InvocationID"] == "0" * 32


def test_terminal_report_rejects_duplicate_and_noncanonical_fields() -> None:
    raw = _report_raw()
    with pytest.raises(WarehouseW3TerminalAcceptanceError):
        WarehouseW3TerminalReport.from_bytes(raw.replace(b"{", b'{ "x":1,', 1))

    value = json.loads(raw)
    value["retry"] = True
    with pytest.raises(WarehouseW3TerminalAcceptanceError):
        WarehouseW3TerminalReport.from_bytes(_canonical(value))

    value = json.loads(raw)
    value["run_properties"]["InvocationID"] = "not-an-invocation"
    with pytest.raises(WarehouseW3TerminalAcceptanceError):
        WarehouseW3TerminalReport.from_bytes(_canonical(value))


def test_terminal_acceptance_allows_only_fixed_terminal_classes() -> None:
    accepted = WarehouseW3TerminalAcceptance.from_bytes(_acceptance_raw())
    assert accepted.classification == "PRECLAIM_TERMINATION_UNKNOWN"

    with pytest.raises(WarehouseW3TerminalAcceptanceError):
        WarehouseW3TerminalAcceptance.from_bytes(
            _acceptance_raw(classification="PENDING")
        )


def test_accept_terminal_rejects_nonroot_before_live_inspection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(terminal.os, "geteuid", lambda: 1001)
    monkeypatch.setattr(
        terminal,
        "inspect_w3_terminal",
        lambda _launch_id: pytest.fail("live inspection must not run"),
    )

    with pytest.raises(PermissionError):
        accept_w3_terminal(LAUNCH_ID)


def test_issue_only_start_store_is_durably_unknown(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    start = tmp_path / LAUNCH_ID / "start"
    start.mkdir(parents=True)
    for name in terminal._START_BASE:
        (start / name).write_bytes(b"x")
    monkeypatch.setattr(terminal, "_LAUNCH_ROOT", tmp_path)

    assert terminal._start_outcome(
        LAUNCH_ID,
        expected_issue_sha256="8" * 64,
    ) == ("START_DISPATCH_UNKNOWN", None)


def test_start_outcome_reopens_and_binds_dispatch_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    issue_sha256 = "8" * 64
    start = tmp_path / LAUNCH_ID / "start"
    start.mkdir(parents=True)
    for name in terminal._START_BASE:
        (start / name).write_bytes(b"x")
    receipt = StartDispatchReceipt.create(
        issue_sha256=issue_sha256,
        state=StartDispatchState.REJECTED,
        error_name="org.example.Rejected",
        error_message="rejected",
    )
    (start / "START_REJECTED").write_bytes(receipt.raw)
    monkeypatch.setattr(terminal, "_LAUNCH_ROOT", tmp_path)
    monkeypatch.setattr(
        terminal,
        "_root_receipt",
        lambda path: path.read_bytes(),
    )

    outcome, digest = terminal._start_outcome(
        LAUNCH_ID,
        expected_issue_sha256=issue_sha256,
    )

    assert outcome == "START_REJECTED"
    assert digest == receipt.raw_sha256

    with pytest.raises(
        WarehouseW3TerminalAcceptanceError,
        match="binding",
    ):
        terminal._start_outcome(
            LAUNCH_ID,
            expected_issue_sha256="9" * 64,
        )


def test_terminal_reader_pins_both_units_and_releases_in_reverse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[tuple[str, str]] = []

    class Reader:
        def ref_unit(self, unit: str) -> None:
            events.append(("ref", unit))

        def unref_unit(self, unit: str) -> None:
            events.append(("unref", unit))

    reader = Reader()
    monkeypatch.setattr(
        terminal,
        "WarehouseW3TerminalManager",
        lambda: reader,
    )

    run = f"scion-w3@{LAUNCH_ID}.service"
    close = f"scion-w3-close@{LAUNCH_ID}.service"
    with terminal._pinned_unit_reader(run, close) as acquired:
        assert acquired is reader
        events.append(("inside", "inspection"))

    assert events == [
        ("ref", run),
        ("ref", close),
        ("inside", "inspection"),
        ("unref", close),
        ("unref", run),
    ]
