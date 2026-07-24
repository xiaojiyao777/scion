from __future__ import annotations

import json

import pytest

import scion.problems.warehouse_delivery.w3_root_preflight as preflight
from scion.problems.warehouse_delivery.w3_root_preflight import (
    WarehouseW3RootFinalAbsenceReceipt,
    WarehouseW3RootPreflightError,
    WarehouseW3RootTransactionTraceReceipt,
    acquire_root_final_absence,
)
from scion.tests.unit.problems.warehouse_delivery.test_w3_environment_receipts import (
    semantic_inputs,
)
from scion.tests.unit.problems.warehouse_delivery.test_w3_root_selection import (
    _bundle,
)


def _canonical(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("ascii")


def test_root_preflight_round_trip_binds_trace_to_expected_and_acquired_absence(
    semantic_inputs,
) -> None:
    selected, *_rest = _bundle(semantic_inputs)
    trace = selected.root_transaction_trace
    absence = selected.root_final_absence
    candidate_absence = (
        selected.staged_candidate.root_staging_verification.candidate_gate_closure.absence_facts
    )

    assert WarehouseW3RootTransactionTraceReceipt.from_bytes(trace.raw) == trace
    assert (
        WarehouseW3RootFinalAbsenceReceipt.from_bytes(
            absence.raw,
            candidate_absence=candidate_absence,
        )
        == absence
    )
    assert trace.expected_root_final_absence_sha256 == absence.raw_sha256
    subjects = {item.role: item.subject for item in absence.observations}
    assert subjects["nonce_ledger_parent"] == ("/var/lib/scion/runs/w3/.nonce-ledger")
    assert subjects["nonce_claims"] == ("/var/lib/scion/runs/w3/.nonce-ledger/claims")


def test_root_transaction_trace_refuses_derived_path_substitution(
    semantic_inputs,
) -> None:
    selected, *_rest = _bundle(semantic_inputs)
    value = json.loads(selected.root_transaction_trace.raw)
    value["selection_path"] = "/var/lib/scion/selections/w3/" + "0" * 64 + ".json"

    with pytest.raises(
        WarehouseW3RootPreflightError,
        match="selection_path differs",
    ):
        WarehouseW3RootTransactionTraceReceipt.from_bytes(_canonical(value))


def test_root_final_absence_requires_every_subject_absent(
    semantic_inputs,
    monkeypatch,
) -> None:
    selected, *_rest = _bundle(semantic_inputs)
    absence = selected.root_final_absence
    candidate_absence = (
        selected.staged_candidate.root_staging_verification.candidate_gate_closure.absence_facts
    )
    seen: list[str] = []
    monkeypatch.setattr(
        preflight,
        "_path_is_absent",
        lambda subject: (seen.append(subject), True)[1],
    )
    monkeypatch.setattr(
        preflight,
        "_process_is_absent",
        lambda subject: (seen.append(subject), True)[1],
    )

    assert (
        acquire_root_final_absence(
            absence,
            candidate_absence=candidate_absence,
        )
        == absence
    )
    assert len(seen) == len(absence.observations)

    monkeypatch.setattr(preflight, "_path_is_absent", lambda subject: False)
    with pytest.raises(
        WarehouseW3RootPreflightError,
        match="subject is present",
    ):
        acquire_root_final_absence(
            absence,
            candidate_absence=candidate_absence,
        )


def test_descriptor_walk_distinguishes_absent_present_and_linked_ancestor(
    tmp_path,
) -> None:
    parent = tmp_path / "parent"
    parent.mkdir()
    assert preflight._path_is_absent(str(parent / "absent"))

    present = parent / "present"
    present.write_bytes(b"present\n")
    assert not preflight._path_is_absent(str(present))

    linked = tmp_path / "linked"
    linked.symlink_to(parent, target_is_directory=True)
    with pytest.raises(
        WarehouseW3RootPreflightError,
        match="ancestor is not a directory",
    ):
        preflight._path_is_absent(str(linked / "absent"))
