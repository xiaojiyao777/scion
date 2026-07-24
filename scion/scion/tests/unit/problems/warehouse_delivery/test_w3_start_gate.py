from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest

import scion.problems.warehouse_delivery.w3_start_store as start_store
from scion.problems.warehouse_delivery.w3_environment_receipts import (
    LiveEnvironmentRehashFact,
)
from scion.problems.warehouse_delivery.w3_start_authorization import (
    ProspectiveStartAuthorizationIntent,
    _bind_start_authorization_for_test,
)
from scion.problems.warehouse_delivery.w3_installed_replay import (
    WarehouseW3InstalledAcceptanceBundle,
)
from scion.problems.warehouse_delivery.w3_start_gate import (
    WarehouseW3InstalledIdentityRefused,
    WarehouseW3PreStartProducerReplayInputs,
    WarehouseW3StartPermitRefused,
    verify_w3_issued_start_gate,
)
from scion.problems.warehouse_delivery.w3_start_store import (
    WarehouseW3InstalledStartGateBundle,
    _acquire_w3_issued_start_gate_for_test,
)
from scion.runtime.execution.external_installation import (
    ManagerIdentity,
    StartIssueReceipt,
)
from scion.tests.unit.problems.warehouse_delivery.test_w3_environment_receipts import (
    semantic_inputs,
)
from scion.tests.unit.problems.warehouse_delivery.test_w3_start_authorization import (
    _installed_bundle,
    _installed_replay_inputs,
    _prospective_raw,
)


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


def _chain(semantic_inputs: dict[str, object]) -> dict[str, object]:
    values, replay, evidence, installed, intents, receipts = _installed_bundle(
        semantic_inputs
    )
    authorization = _bind_start_authorization_for_test(
        ProspectiveStartAuthorizationIntent.from_bytes(_prospective_raw()),
        selection_replay_inputs=replay,
        prestart_evidence=evidence,
        installed_acceptance=installed,
        phase_intents=intents,
        phase_receipts=receipts,
        recorded_at_utc="2026-07-23T19:00:00Z",
        unit=values["installation"].run_unit,
    )
    issue = StartIssueReceipt.create_authorized(
        authorization,
        prestart_receipt_sha256=evidence.raw_sha256,
        manager_identity=ManagerIdentity(
            unique_owner=":1.42",
            boot_id="12345678-1234-1234-1234-123456789abc",
            version="255.4-1ubuntu8",
        ),
    )
    installed_replay = _installed_replay_inputs(
        values,
        evidence,
        installed,
        intents,
        receipts,
    )
    return {
        "issue_raw": issue.raw,
        "authorization_raw": authorization.raw,
        "prospective_intent_raw": _prospective_raw(),
        "installed_acceptance_raw": installed.raw,
        "prestart_evidence_raw": evidence.raw,
        "prestart_producer_replay_inputs": (
            WarehouseW3PreStartProducerReplayInputs(
                candidate_gate_raw=values["candidate_gate"].raw,
                dry_root_raw=values["dry_root"].raw,
                environment_rehash_raw=values["environment_rehash"].raw,
                loaded_manager_raw=values["loaded_manager"].raw,
                prestart_absence_raw=values["prestart_absence"].raw,
                runtime_account_raw=values["runtime_account"].raw,
            )
        ),
        "installed_replay_inputs": installed_replay,
        "selection_replay_inputs": replay,
        "expected_launch_id": installed.launch_id,
        "expected_authority_sha256": installed.authority_sha256,
        "expected_installation_sha256": installed.installation_sha256,
        "expected_unit": values["installation"].run_unit,
    }


def test_issued_start_gate_closes_exact_receipt_and_staged_chain(
    semantic_inputs: dict[str, object],
) -> None:
    inputs = _chain(semantic_inputs)

    gate = verify_w3_issued_start_gate(**inputs)

    assert gate.launch_id == inputs["expected_launch_id"]
    assert gate.authority_sha256 == inputs["expected_authority_sha256"]
    assert gate.installation_sha256 == inputs["expected_installation_sha256"]
    assert gate.unit == inputs["expected_unit"]
    assert gate.issue_sha256 == hashlib.sha256(inputs["issue_raw"]).hexdigest()
    assert gate.manager_unique_owner == ":1.42"
    assert gate.boot_id == "12345678-1234-1234-1234-123456789abc"
    assert gate.manager_version == "255.4-1ubuntu8"
    assert (
        gate.staged_candidate_sha256
        == hashlib.sha256(
            inputs["selection_replay_inputs"].staged_candidate_raw
        ).hexdigest()
    )
    assert len(gate.root_staging_verification_sha256) == 64
    assert len(gate.candidate_gate_ingress_fact_sha256) == 64
    assert len(gate.candidate_gate_closure_sha256) == 64


def test_fixed_receipt_store_reopens_gate_and_root_selection(
    tmp_path: Path,
    semantic_inputs: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = _chain(semantic_inputs)
    replay = inputs["selection_replay_inputs"]
    installed_bundle = WarehouseW3InstalledAcceptanceBundle._create_for_test(
        selection_replay_inputs=replay,
        installed_replay_inputs=inputs["installed_replay_inputs"],
    )
    bundle = WarehouseW3InstalledStartGateBundle._create_for_test(
        prospective_intent_raw=inputs["prospective_intent_raw"],
        installed_acceptance_raw=inputs["installed_acceptance_raw"],
        prestart_evidence_raw=inputs["prestart_evidence_raw"],
        selection_replay_inputs=replay,
        prestart_producer_replay_inputs=(inputs["prestart_producer_replay_inputs"]),
        installed_replay_inputs=inputs["installed_replay_inputs"],
    )
    acceptance_root = tmp_path / "acceptances"
    launch = acceptance_root / inputs["expected_launch_id"]
    install = launch / "install"
    start = launch / "start"
    selection_root = tmp_path / "selections"
    install.mkdir(parents=True)
    start.mkdir()
    selection_root.mkdir()
    files = (
        (start / "START_GATE_INPUTS.v1.json", bundle.raw),
        (install / "INSTALLED_REPLAY.v1.json", installed_bundle.raw),
        (start / "START_AUTHORIZED", inputs["authorization_raw"]),
        (start / "START_ISSUED", inputs["issue_raw"]),
        (
            selection_root
            / f"{json.loads(replay.root_selection_raw)['selection_key']}.json",
            replay.root_selection_raw,
        ),
    )
    for path, raw in files:
        path.write_bytes(raw)
        path.chmod(0o444)
    install.chmod(0o555)
    start.chmod(0o555)
    expected_rehash = LiveEnvironmentRehashFact.from_bytes(
        inputs["prestart_producer_replay_inputs"].environment_rehash_raw
    )
    phases: list[str] = []

    def verify_environment(
        _content: object,
        *,
        phase: str,
        live_reader: object,
    ) -> LiveEnvironmentRehashFact:
        del live_reader
        phases.append(phase)
        return expected_rehash

    monkeypatch.setattr(
        start_store,
        "verify_live_environment",
        verify_environment,
    )

    context = _acquire_w3_issued_start_gate_for_test(
        str(acceptance_root),
        str(selection_root),
        expected_launch_id=inputs["expected_launch_id"],
        expected_authority_sha256=inputs["expected_authority_sha256"],
        expected_installation_sha256=inputs["expected_installation_sha256"],
        expected_unit=inputs["expected_unit"],
        require_live_environment=True,
    )

    gate = context.gate
    assert phases == ["preclaim"]
    assert gate.issue_sha256 == hashlib.sha256(inputs["issue_raw"]).hexdigest()
    assert (
        gate.root_selection_sha256
        == hashlib.sha256(replay.root_selection_raw).hexdigest()
    )
    context.revalidate()

    authorization_path = start / "START_AUTHORIZED"
    start.chmod(0o755)
    authorization_path.unlink()
    authorization_path.write_bytes(inputs["authorization_raw"])
    authorization_path.chmod(0o444)
    start.chmod(0o555)
    with pytest.raises(
        start_store.WarehouseW3StartStoreError,
        match="authority drifted",
    ):
        context.revalidate()
    context.close()


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
    semantic_inputs: dict[str, object],
    field: str,
    value: object,
) -> None:
    inputs = _chain(semantic_inputs)
    issue = json.loads(inputs["issue_raw"])
    issue[field] = value
    inputs["issue_raw"] = _canonical(issue)

    with pytest.raises(WarehouseW3StartPermitRefused):
        verify_w3_issued_start_gate(**inputs)


def test_issued_start_gate_rejects_ingress_closure_substitution(
    semantic_inputs: dict[str, object],
) -> None:
    inputs = _chain(semantic_inputs)
    replay = inputs["selection_replay_inputs"]
    ingress = json.loads(replay.candidate_gate_ingress_fact_raw)
    ingress["closure_sha256"] = "0" * 64
    inputs["selection_replay_inputs"] = replace(
        replay,
        candidate_gate_ingress_fact_raw=_canonical(ingress),
    )

    with pytest.raises(
        WarehouseW3InstalledIdentityRefused,
        match="producer replay differs",
    ):
        verify_w3_issued_start_gate(**inputs)


def test_issued_start_gate_replays_prospective_authorization_intent(
    semantic_inputs: dict[str, object],
) -> None:
    inputs = _chain(semantic_inputs)
    authorization = json.loads(inputs["authorization_raw"])
    authorization["prospective_intent_sha256"] = "0" * 64
    authorization["user_statement"] = "self-consistent replacement"
    authorization_raw = _canonical(authorization)
    issue = json.loads(inputs["issue_raw"])
    issue["authorization_sha256"] = hashlib.sha256(authorization_raw).hexdigest()
    inputs["authorization_raw"] = authorization_raw
    inputs["issue_raw"] = _canonical(issue)

    with pytest.raises(
        WarehouseW3StartPermitRefused,
        match="START_AUTHORIZED authority differs",
    ):
        verify_w3_issued_start_gate(**inputs)


def test_issued_start_gate_replays_prestart_producer_receipts(
    semantic_inputs: dict[str, object],
) -> None:
    inputs = _chain(semantic_inputs)
    evidence = json.loads(inputs["prestart_evidence_raw"])
    evidence["producer_receipt_sha256"]["loaded_manager"] = "0" * 64
    evidence_raw = _canonical(evidence)
    evidence_sha256 = hashlib.sha256(evidence_raw).hexdigest()

    acceptance = json.loads(inputs["installed_acceptance_raw"])
    acceptance["problem_state_sha256"] = evidence_sha256
    acceptance["phase_effect_sha256"]["INSTANCES_LOADED"] = evidence_sha256
    acceptance_raw = _canonical(acceptance)
    acceptance_sha256 = hashlib.sha256(acceptance_raw).hexdigest()

    authorization = json.loads(inputs["authorization_raw"])
    authorization["installed_acceptance_sha256"] = acceptance_sha256
    authorization_raw = _canonical(authorization)
    authorization_sha256 = hashlib.sha256(authorization_raw).hexdigest()

    issue = json.loads(inputs["issue_raw"])
    issue["authorization_sha256"] = authorization_sha256
    issue["installed_acceptance_sha256"] = acceptance_sha256
    issue["prestart_receipt_sha256"] = evidence_sha256

    inputs["prestart_evidence_raw"] = evidence_raw
    inputs["installed_acceptance_raw"] = acceptance_raw
    inputs["authorization_raw"] = authorization_raw
    inputs["issue_raw"] = _canonical(issue)

    with pytest.raises(
        WarehouseW3InstalledIdentityRefused,
        match="installed replay bundle",
    ):
        verify_w3_issued_start_gate(**inputs)


def test_issued_start_gate_rejects_k0_or_k1_effect_substitution(
    semantic_inputs: dict[str, object],
) -> None:
    inputs = _chain(semantic_inputs)
    replay = inputs["selection_replay_inputs"]
    k0 = json.loads(replay.root_staging_receipt_raw)
    k0["effect_sha256"] = "0" * 64
    inputs["selection_replay_inputs"] = replace(
        replay,
        root_staging_receipt_raw=_canonical(k0),
    )

    with pytest.raises(
        WarehouseW3InstalledIdentityRefused,
        match="producer replay differs",
    ):
        verify_w3_issued_start_gate(**inputs)


def test_issued_start_gate_rejects_duplicate_or_unknown_receipts(
    semantic_inputs: dict[str, object],
) -> None:
    inputs = _chain(semantic_inputs)
    issue = inputs["issue_raw"]
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

    inputs = _chain(semantic_inputs)
    acceptance = json.loads(inputs["installed_acceptance_raw"])
    acceptance["unknown"] = False
    inputs["installed_acceptance_raw"] = _canonical(acceptance)
    with pytest.raises(
        WarehouseW3InstalledIdentityRefused,
        match="installed replay bundle",
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
