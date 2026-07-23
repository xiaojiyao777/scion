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
    ACCEPTED_ROOT_INSTALLATION_PLAN_SHA256,
    CandidateRootIdentity,
    CandidateSelectionCommit,
    CandidateSelectionIntent,
    derive_launch_id,
)
from scion.problems.warehouse_delivery.w3_root_installation import (
    WAREHOUSE_W3_PRESTART_EVIDENCE_SCHEMA,
    WarehouseW3PreStartEvidence,
)
from scion.runtime.execution.external_installation import (
    INSTALL_PHASES,
    DirectorySnapshot,
    InstalledAcceptance,
    ReceiptDagError,
    RootPhaseIntentReceipt,
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


def _prestart_evidence(
    *,
    pending_intent: RootPhaseIntentReceipt,
    phase_receipts: tuple[RootPhaseReceipt, ...],
    candidate_selected_sha256: str | None = None,
) -> WarehouseW3PreStartEvidence:
    phase_effects = {
        receipt.phase.value: receipt.effect_sha256 for receipt in phase_receipts
    }
    if candidate_selected_sha256 is not None:
        phase_effects["CANDIDATE_SELECTED"] = candidate_selected_sha256
    producer_receipts = {
        "candidate_gate": "7" * 64,
        "dry_root": "8" * 64,
        "environment_rehash": "9" * 64,
        "loaded_manager": "a" * 64,
        "prestart_absence": "d" * 64,
        "runtime_account": "e" * 64,
    }
    raw = _canonical(
        {
            "schema": WAREHOUSE_W3_PRESTART_EVIDENCE_SCHEMA,
            "state": "PRESTART_GATES_REACQUIRED_NOT_STARTED",
            "plan_sha256": ACCEPTED_ROOT_INSTALLATION_PLAN_SHA256,
            "launch_id": LAUNCH,
            "authority_sha256": AUTHORITY,
            "installation_sha256": INSTALLATION,
            "pending_intent_sha256": pending_intent.raw_sha256,
            "predecessor_phase_receipt_sha256": (phase_receipts[-1].raw_sha256),
            "phase_effect_sha256": phase_effects,
            "producer_receipt_sha256": producer_receipts,
            "formal_jobs_started": 0,
            "retry": False,
            "resume": False,
            "reuse": False,
        }
    )
    instance = object.__new__(WarehouseW3PreStartEvidence)
    for field, value in (
        ("launch_id", LAUNCH),
        ("authority_sha256", AUTHORITY),
        ("installation_sha256", INSTALLATION),
        ("pending_intent_sha256", pending_intent.raw_sha256),
        (
            "predecessor_phase_receipt_sha256",
            phase_receipts[-1].raw_sha256,
        ),
        (
            "phase_effect_sha256",
            tuple(
                (phase.value, phase_effects[phase.value])
                for phase in INSTALL_PHASES[:7]
            ),
        ),
        (
            "producer_receipt_sha256",
            tuple(sorted(producer_receipts.items())),
        ),
        ("raw", raw),
        ("raw_sha256", hashlib.sha256(raw).hexdigest()),
    ):
        object.__setattr__(instance, field, value)
    return instance


def _installed(
    selection: SelectionReceipt,
    *,
    problem_state_schema: str = WAREHOUSE_W3_PRESTART_EVIDENCE_SCHEMA,
    candidate_selected_sha256: str | None = None,
) -> tuple[
    WarehouseW3PreStartEvidence,
    InstalledAcceptance,
    tuple[RootPhaseIntentReceipt, ...],
    tuple[RootPhaseReceipt, ...],
]:
    intents = []
    receipts = []
    for phase in INSTALL_PHASES[:7]:
        intent = RootPhaseIntentReceipt.create(
            launch_id=LAUNCH,
            phase=phase,
            predecessor_sha256=(() if not receipts else (receipts[-1].raw_sha256,)),
            effect_authority_sha256=hashlib.sha256(
                f"{phase.value}:authority".encode()
            ).hexdigest(),
        )
        receipt = RootPhaseReceipt.create(
            intent=intent,
            effect_sha256=(
                selection.raw_sha256
                if phase.value == "CANDIDATE_SELECTED"
                else hashlib.sha256(phase.value.encode()).hexdigest()
            ),
        )
        intents.append(intent)
        receipts.append(receipt)
    pending_intent = RootPhaseIntentReceipt.create(
        launch_id=LAUNCH,
        phase=INSTALL_PHASES[7],
        predecessor_sha256=(receipts[-1].raw_sha256,),
        effect_authority_sha256="f" * 64,
    )
    evidence = _prestart_evidence(
        pending_intent=pending_intent,
        phase_receipts=tuple(receipts),
        candidate_selected_sha256=candidate_selected_sha256,
    )
    intents.append(pending_intent)
    receipts.append(
        RootPhaseReceipt.create(
            intent=pending_intent,
            effect_sha256=evidence.raw_sha256,
        )
    )
    installed = InstalledAcceptance.create(
        launch_id=LAUNCH,
        authority_sha256=AUTHORITY,
        installation_sha256=INSTALLATION,
        phase_intents=tuple(intents),
        phase_receipts=tuple(receipts),
        problem_state_schema=problem_state_schema,
        problem_state_sha256=evidence.raw_sha256,
    )
    final_intent = RootPhaseIntentReceipt.create(
        launch_id=LAUNCH,
        phase=INSTALL_PHASES[-1],
        predecessor_sha256=(receipts[-1].raw_sha256,),
        effect_authority_sha256=installed.raw_sha256,
    )
    final_receipt = RootPhaseReceipt.create(
        intent=final_intent,
        effect_sha256=installed.raw_sha256,
    )
    return (
        evidence,
        installed,
        (*intents, final_intent),
        (*receipts, final_receipt),
    )


def test_prospective_intent_binds_only_after_exact_root_selection(
    tmp_path: Path,
) -> None:
    prospective = ProspectiveStartAuthorizationIntent.from_bytes(_prospective_raw())
    intent, commit = _preparation(tmp_path)
    selection = _root_selection(intent, commit)
    evidence, installed, phase_intents, phase_receipts = _installed(selection)

    authorization = bind_start_authorization(
        prospective,
        preparation_intent=intent,
        preparation_commit=commit,
        root_selection=selection,
        prestart_evidence=evidence,
        installed_acceptance=installed,
        phase_intents=phase_intents,
        phase_receipts=phase_receipts,
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
    evidence, installed, phase_intents, phase_receipts = _installed(selection)
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
            prestart_evidence=evidence,
            installed_acceptance=installed,
            phase_intents=phase_intents,
            phase_receipts=phase_receipts,
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
            prestart_evidence=evidence,
            installed_acceptance=installed,
            phase_intents=phase_intents,
            phase_receipts=phase_receipts,
            recorded_at_utc="2026-07-23T17:00:00Z",
            unit=RUN_UNIT,
        )


def test_binding_requires_exact_w3_problem_state_and_evidence(
    tmp_path: Path,
) -> None:
    prospective = ProspectiveStartAuthorizationIntent.from_bytes(_prospective_raw())
    intent, commit = _preparation(tmp_path)
    selection = _root_selection(intent, commit)
    (
        evidence,
        wrong_schema_acceptance,
        phase_intents,
        phase_receipts,
    ) = _installed(
        selection,
        problem_state_schema="scion.test-problem-state.v1",
    )

    with pytest.raises(
        WarehouseW3StartAuthorizationError,
        match="differ",
    ):
        bind_start_authorization(
            prospective,
            preparation_intent=intent,
            preparation_commit=commit,
            root_selection=selection,
            prestart_evidence=evidence,
            installed_acceptance=wrong_schema_acceptance,
            phase_intents=phase_intents,
            phase_receipts=phase_receipts,
            recorded_at_utc="2026-07-23T17:00:00Z",
            unit=RUN_UNIT,
        )

    evidence, installed, phase_intents, phase_receipts = _installed(selection)
    alternate_evidence = _prestart_evidence(
        pending_intent=phase_intents[7],
        phase_receipts=phase_receipts[:7],
        candidate_selected_sha256="f" * 64,
    )
    with pytest.raises(
        WarehouseW3StartAuthorizationError,
        match="differ",
    ):
        bind_start_authorization(
            prospective,
            preparation_intent=intent,
            preparation_commit=commit,
            root_selection=selection,
            prestart_evidence=alternate_evidence,
            installed_acceptance=installed,
            phase_intents=phase_intents,
            phase_receipts=phase_receipts,
            recorded_at_utc="2026-07-23T17:00:00Z",
            unit=RUN_UNIT,
        )


def test_binding_rejects_alternate_complete_dag_before_authorization_creation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prospective = ProspectiveStartAuthorizationIntent.from_bytes(_prospective_raw())
    preparation_intent, preparation_commit = _preparation(tmp_path)
    selection = _root_selection(preparation_intent, preparation_commit)
    evidence, installed, _phase_intents, _phase_receipts = _installed(selection)
    alternate_intents: list[RootPhaseIntentReceipt] = []
    alternate_receipts: list[RootPhaseReceipt] = []
    for phase in INSTALL_PHASES:
        intent = RootPhaseIntentReceipt.create(
            launch_id=LAUNCH,
            phase=phase,
            predecessor_sha256=(
                () if not alternate_receipts else (alternate_receipts[-1].raw_sha256,)
            ),
            effect_authority_sha256=hashlib.sha256(
                f"alternate:{phase.value}:authority".encode()
            ).hexdigest(),
        )
        alternate_intents.append(intent)
        alternate_receipts.append(
            RootPhaseReceipt.create(
                intent=intent,
                effect_sha256=hashlib.sha256(
                    f"alternate:{phase.value}:effect".encode()
                ).hexdigest(),
            )
        )

    called = False

    def unexpected_create(
        cls: type[StartAuthorizationReceipt],
        **_kwargs: object,
    ) -> StartAuthorizationReceipt:
        nonlocal called
        del cls
        called = True
        raise AssertionError("authorization creation must not be reached")

    monkeypatch.setattr(
        StartAuthorizationReceipt,
        "create",
        classmethod(unexpected_create),
    )
    with pytest.raises(ReceiptDagError, match="phase DAG differs"):
        bind_start_authorization(
            prospective,
            preparation_intent=preparation_intent,
            preparation_commit=preparation_commit,
            root_selection=selection,
            prestart_evidence=evidence,
            installed_acceptance=installed,
            phase_intents=tuple(alternate_intents),
            phase_receipts=tuple(alternate_receipts),
            recorded_at_utc="2026-07-23T17:00:00Z",
            unit=RUN_UNIT,
        )
    assert called is False
