from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scion.problems.warehouse_delivery.w3_prestart_facts import (
    ACCEPTED_ROOT_INSTALLATION_PLAN_SHA256,
    WAREHOUSE_W3_PRESTART_EVIDENCE_SCHEMA,
)
from scion.problems.warehouse_delivery.w3_start_gate import (
    WarehouseW3InstalledIdentityRefused,
    WarehouseW3StartPermitRefused,
    verify_w3_issued_start_gate,
)
from scion.runtime.execution.external_installation import (
    INSTALL_PHASES,
    DirectorySnapshot,
    InstalledAcceptance,
    ManagerIdentity,
    RootPhaseIntentReceipt,
    RootPhaseReceipt,
    SelectionReceipt,
    StartAuthorizationReceipt,
    StartIssueReceipt,
)

LAUNCH = "a" * 64
AUTHORITY = "b" * 64
INSTALLATION = "c" * 64
SELECTION_KEY = "d" * 64
UNIT = f"scion-w3@{LAUNCH}.service"


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


def _selection() -> SelectionReceipt:
    return SelectionReceipt.create(
        selection_key=SELECTION_KEY,
        launch_id=LAUNCH,
        nonce="e" * 64,
        authority_sha256=AUTHORITY,
        candidate_sha256="f" * 64,
        preparation_intent_sha256="1" * 64,
        preparation_commit_sha256="2" * 64,
        import_receipt_sha256="3" * 64,
        imported_staging_aggregate_sha256="4" * 64,
        source_candidate_identity=DirectorySnapshot(
            device=1,
            inode=2,
            mode=0o555,
            uid=1001,
            gid=1001,
            nlink=2,
        ),
        source_selection_identity=DirectorySnapshot(
            device=1,
            inode=3,
            mode=0o555,
            uid=1001,
            gid=1001,
            nlink=2,
        ),
    )


def _prestart_raw(
    *,
    pending: RootPhaseIntentReceipt,
    receipts: tuple[RootPhaseReceipt, ...],
    candidate_selected_effect: str | None,
    pending_sha256: str | None,
) -> bytes:
    effects = {receipt.phase.value: receipt.effect_sha256 for receipt in receipts}
    if candidate_selected_effect is not None:
        effects["CANDIDATE_SELECTED"] = candidate_selected_effect
    return _canonical(
        {
            "schema": WAREHOUSE_W3_PRESTART_EVIDENCE_SCHEMA,
            "state": "PRESTART_GATES_REACQUIRED_NOT_STARTED",
            "plan_sha256": ACCEPTED_ROOT_INSTALLATION_PLAN_SHA256,
            "launch_id": LAUNCH,
            "authority_sha256": AUTHORITY,
            "installation_sha256": INSTALLATION,
            "pending_intent_sha256": (
                pending.raw_sha256 if pending_sha256 is None else pending_sha256
            ),
            "predecessor_phase_receipt_sha256": receipts[-1].raw_sha256,
            "phase_effect_sha256": effects,
            "producer_receipt_sha256": {
                "candidate_gate": "5" * 64,
                "dry_root": "6" * 64,
                "environment_rehash": "7" * 64,
                "loaded_manager": "8" * 64,
                "prestart_absence": "9" * 64,
                "runtime_account": "0" * 64,
            },
            "formal_jobs_started": 0,
            "retry": False,
            "resume": False,
            "reuse": False,
        }
    )


def _chain(
    *,
    problem_state_schema: str = WAREHOUSE_W3_PRESTART_EVIDENCE_SCHEMA,
    committed_selection_effect: str | None = None,
    evidence_selection_effect: str | None = None,
    evidence_pending_sha256: str | None = None,
) -> dict[str, bytes | str]:
    selection = _selection()
    selected_effect = (
        selection.raw_sha256
        if committed_selection_effect is None
        else committed_selection_effect
    )
    intents: list[RootPhaseIntentReceipt] = []
    receipts: list[RootPhaseReceipt] = []
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
                selected_effect
                if phase.value == "CANDIDATE_SELECTED"
                else hashlib.sha256(phase.value.encode()).hexdigest()
            ),
        )
        intents.append(intent)
        receipts.append(receipt)
    pending = RootPhaseIntentReceipt.create(
        launch_id=LAUNCH,
        phase=INSTALL_PHASES[7],
        predecessor_sha256=(receipts[-1].raw_sha256,),
        effect_authority_sha256="f" * 64,
    )
    prestart_raw = _prestart_raw(
        pending=pending,
        receipts=tuple(receipts),
        candidate_selected_effect=evidence_selection_effect,
        pending_sha256=evidence_pending_sha256,
    )
    intents.append(pending)
    receipts.append(
        RootPhaseReceipt.create(
            intent=pending,
            effect_sha256=hashlib.sha256(prestart_raw).hexdigest(),
        )
    )
    acceptance = InstalledAcceptance.create(
        launch_id=LAUNCH,
        authority_sha256=AUTHORITY,
        installation_sha256=INSTALLATION,
        phase_intents=tuple(intents),
        phase_receipts=tuple(receipts),
        problem_state_schema=problem_state_schema,
        problem_state_sha256=hashlib.sha256(prestart_raw).hexdigest(),
    )
    authorization = StartAuthorizationReceipt.create(
        launch_id=LAUNCH,
        authority_sha256=AUTHORITY,
        installation_sha256=INSTALLATION,
        installed_acceptance_sha256=acceptance.raw_sha256,
        prospective_intent_sha256="a" * 64,
        plan_sha256=ACCEPTED_ROOT_INSTALLATION_PLAN_SHA256,
        selection_key=SELECTION_KEY,
        preparation_commit_sha256=selection.preparation_commit_sha256,
        root_selection_sha256=selection.raw_sha256,
        user_statement="authorize exact accepted W3 first start",
        task_event_identity="thread:test-w3-start-gate",
        recorded_at_utc="2026-07-23T19:00:00Z",
        unit=UNIT,
    )
    issue = StartIssueReceipt.create_authorized(
        authorization,
        prestart_receipt_sha256=hashlib.sha256(prestart_raw).hexdigest(),
        manager_identity=ManagerIdentity(
            unique_owner=":1.42",
            boot_id="12345678-1234-1234-1234-123456789abc",
            version="255.4-1ubuntu8",
        ),
    )
    return {
        "issue_raw": issue.raw,
        "authorization_raw": authorization.raw,
        "installed_acceptance_raw": acceptance.raw,
        "prestart_evidence_raw": prestart_raw,
        "candidate_selected_receipt_raw": receipts[1].raw,
        "root_selection_raw": selection.raw,
        "expected_launch_id": LAUNCH,
        "expected_authority_sha256": AUTHORITY,
        "expected_installation_sha256": INSTALLATION,
        "expected_unit": UNIT,
    }


def test_issued_start_gate_closes_exact_receipt_chain() -> None:
    inputs = _chain()

    gate = verify_w3_issued_start_gate(**inputs)

    assert gate.launch_id == LAUNCH
    assert gate.authority_sha256 == AUTHORITY
    assert gate.installation_sha256 == INSTALLATION
    assert gate.unit == UNIT
    assert gate.issue_sha256 == hashlib.sha256(inputs["issue_raw"]).hexdigest()
    assert gate.manager_unique_owner == ":1.42"
    assert gate.boot_id == "12345678-1234-1234-1234-123456789abc"
    assert gate.manager_version == "255.4-1ubuntu8"


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("unit", "scion-other.service"),
        ("method", "RestartUnit"),
        ("mode", "replace"),
        ("authorization_sha256", "0" * 64),
        ("prestart_receipt_sha256", "0" * 64),
    ),
)
def test_issued_start_gate_rejects_permit_drift(
    field: str,
    value: object,
) -> None:
    inputs = _chain()
    issue = json.loads(inputs["issue_raw"])
    issue[field] = value
    inputs["issue_raw"] = _canonical(issue)

    with pytest.raises(WarehouseW3StartPermitRefused):
        verify_w3_issued_start_gate(**inputs)


@pytest.mark.parametrize(
    "inputs",
    (
        {
            "problem_state_schema": "scion.test-problem-state.v1",
        },
        {
            "evidence_selection_effect": "0" * 64,
        },
        {
            "committed_selection_effect": "0" * 64,
        },
        {
            "evidence_pending_sha256": "0" * 64,
        },
    ),
)
def test_issued_start_gate_rejects_installed_chain_drift(
    inputs: dict[str, str],
) -> None:
    with pytest.raises(WarehouseW3InstalledIdentityRefused):
        verify_w3_issued_start_gate(**_chain(**inputs))


def test_issued_start_gate_rejects_duplicate_or_noncanonical_receipts() -> None:
    inputs = _chain()
    issue = inputs["issue_raw"]
    assert type(issue) is bytes
    duplicate = issue.replace(
        b'{"authorization_sha256":',
        b'{"authorization_sha256":"' + b"0" * 64 + b'","authorization_sha256":',
    )
    inputs["issue_raw"] = duplicate
    with pytest.raises(
        WarehouseW3StartPermitRefused,
        match="canonical JSON",
    ):
        verify_w3_issued_start_gate(**inputs)

    inputs = _chain()
    acceptance = json.loads(inputs["installed_acceptance_raw"])
    acceptance["unknown"] = False
    inputs["installed_acceptance_raw"] = _canonical(acceptance)
    with pytest.raises(
        WarehouseW3InstalledIdentityRefused,
        match="fields differ",
    ):
        verify_w3_issued_start_gate(**inputs)


def test_start_gate_source_has_no_capability_owner_or_callback() -> None:
    source = (
        Path(__file__).parents[4]
        / "problems"
        / "warehouse_delivery"
        / "w3_start_gate.py"
    ).read_text()

    assert "external_installation" not in source
    assert "w3_root_composition" not in source
    assert "callback" not in source
    assert "StartUnit(" not in source
    assert "os." not in source
    assert "Path(" not in source
