from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scion.problems.warehouse_delivery.w3_start_authorization import (
    ProspectiveStartAuthorizationIntent,
    WarehouseW3StartAuthorizationError,
    bind_start_authorization,
)
from scion.problems.warehouse_delivery.w3_installation import (
    CandidateRootIdentity,
    CandidateSelectionCommit,
    CandidateSelectionIntent,
    derive_launch_id,
)
from scion.runtime.execution.external_installation import (
    INSTALL_PHASES,
    DirectorySnapshot,
    InstalledAcceptance,
    RootPhaseReceipt,
    SelectionReceipt,
    StartAuthorizationReceipt,
)

AUTHORITY = "b" * 64
INSTALLATION = "c" * 64
NONCE = "1" * 64
LAUNCH = derive_launch_id(AUTHORITY, NONCE)
RUN_UNIT = f"scion-w3@{LAUNCH}.service"
TASK_EVENT = "thread:019f86f1-a40c-7ab1-b584-3bd64f9aa97a"
LAUNCH_COMMIT = "0123456789abcdef0123456789abcdef01234567"
LAUNCH_TREE = "89abcdef0123456789abcdef0123456789abcdef"


def _prospective_raw() -> bytes:
    path = (
        Path(__file__).parents[5]
        / "docs"
        / "experiments"
        / "v0.4"
        / "v04-w3-prospective-start-authorization-intent-20260723.json"
    )
    return path.read_bytes()


def _preparation(
    tmp_path: Path,
    *,
    task_event: str = TASK_EVENT,
) -> tuple[CandidateSelectionIntent, CandidateSelectionCommit]:
    intent = CandidateSelectionIntent.create(
        experiment_parent=tmp_path,
        task_event_identity=task_event,
        launch_commit=LAUNCH_COMMIT,
        launch_tree=LAUNCH_TREE,
    )
    commit = CandidateSelectionCommit.create(
        intent=intent,
        candidate_root_identity=CandidateRootIdentity(
            device=1,
            inode=2,
            mode=0o555,
            uid=1001,
            gid=1001,
            nlink=2,
        ),
        nonce=NONCE,
        authority_sha256=AUTHORITY,
    )
    return intent, commit


def _root_selection(
    intent: CandidateSelectionIntent,
    commit: CandidateSelectionCommit,
) -> SelectionReceipt:
    snapshot = DirectorySnapshot(
        device=1,
        inode=2,
        mode=0o555,
        uid=1001,
        gid=1001,
        nlink=2,
    )
    return SelectionReceipt.create(
        selection_key=intent.selection_key,
        launch_id=LAUNCH,
        nonce=NONCE,
        authority_sha256=AUTHORITY,
        candidate_sha256="2" * 64,
        preparation_intent_sha256=intent.raw_sha256,
        preparation_commit_sha256=commit.raw_sha256,
        import_receipt_sha256="5" * 64,
        imported_staging_aggregate_sha256="6" * 64,
        source_candidate_identity=snapshot,
        source_selection_identity=DirectorySnapshot(
            device=1,
            inode=3,
            mode=0o555,
            uid=1001,
            gid=1001,
            nlink=2,
        ),
    )


def _installed(
    selection: SelectionReceipt,
) -> tuple[InstalledAcceptance, tuple[RootPhaseReceipt, ...]]:
    phases = []
    for index, phase in enumerate(INSTALL_PHASES):
        receipt = RootPhaseReceipt.create(
            launch_id=LAUNCH,
            phase=phase,
            predecessor_sha256=(() if index == 0 else (phases[-1].raw_sha256,)),
            effect_sha256=hashlib.sha256(phase.value.encode()).hexdigest(),
        )
        phases.append(receipt)
    phase_tuple = tuple(phases)
    return (
        InstalledAcceptance.create(
            launch_id=LAUNCH,
            authority_sha256=AUTHORITY,
            installation_sha256=INSTALLATION,
            phase_receipts=phase_tuple,
            subordinate_receipt_sha256={
                "root_selection": selection.raw_sha256,
                "sealed_store": "1" * 64,
                "environment_content": "2" * 64,
                "environment_relocation": "3" * 64,
                "projection": "4" * 64,
                "units": "5" * 64,
                "loaded_manager": "6" * 64,
                "dry_root": "7" * 64,
                "prestart_absence": "8" * 64,
            },
        ),
        phase_tuple,
    )


def test_prospective_intent_binds_only_after_exact_root_selection(
    tmp_path: Path,
) -> None:
    prospective = ProspectiveStartAuthorizationIntent.from_bytes(_prospective_raw())
    intent, commit = _preparation(tmp_path)
    selection = _root_selection(intent, commit)
    installed, phases = _installed(selection)

    authorization = bind_start_authorization(
        prospective,
        preparation_intent=intent,
        preparation_commit=commit,
        root_selection=selection,
        installed_acceptance=installed,
        phase_receipts=phases,
        recorded_at_utc="2026-07-23T17:00:00Z",
        unit=RUN_UNIT,
    )

    assert StartAuthorizationReceipt.from_bytes(authorization.raw) == authorization
    assert authorization.user_statement == prospective.statement
    assert authorization.root_selection_sha256 == selection.raw_sha256
    assert authorization.installed_acceptance_sha256 == installed.raw_sha256


def test_prospective_parser_and_binding_reject_drift(tmp_path: Path) -> None:
    raw = _prospective_raw()
    value = json.loads(raw)
    value["retry"] = True
    drift = (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode()
    with pytest.raises(
        WarehouseW3StartAuthorizationError,
        match="authority differs",
    ):
        ProspectiveStartAuthorizationIntent.from_bytes(drift)

    prospective = ProspectiveStartAuthorizationIntent.from_bytes(raw)
    intent, commit = _preparation(tmp_path)
    selection = _root_selection(intent, commit)
    installed, phases = _installed(selection)
    other = SelectionReceipt.from_bytes(
        selection.raw.replace(
            f'"authority_sha256":"{AUTHORITY}"'.encode(),
            f'"authority_sha256":"{"e" * 64}"'.encode(),
        )
    )
    with pytest.raises(
        WarehouseW3StartAuthorizationError,
        match="differ",
    ):
        bind_start_authorization(
            prospective,
            preparation_intent=intent,
            preparation_commit=commit,
            root_selection=other,
            installed_acceptance=installed,
            phase_receipts=phases,
            recorded_at_utc="2026-07-23T17:00:00Z",
            unit=RUN_UNIT,
        )

    other_intent, other_commit = _preparation(
        tmp_path / "other",
        task_event="thread:another-authority-event",
    )
    with pytest.raises(
        WarehouseW3StartAuthorizationError,
        match="differ",
    ):
        bind_start_authorization(
            prospective,
            preparation_intent=other_intent,
            preparation_commit=other_commit,
            root_selection=selection,
            installed_acceptance=installed,
            phase_receipts=phases,
            recorded_at_utc="2026-07-23T17:00:00Z",
            unit=RUN_UNIT,
        )
