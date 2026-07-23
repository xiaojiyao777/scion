from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest

from scion.problems.warehouse_delivery.w3_candidate_gate import CandidateGateReceipt
from scion.problems.warehouse_delivery.w3_composition import (
    EXPECTED_MANIFEST_NAME,
    EXPECTED_MANIFEST_SHA256,
    EXPECTED_SOURCE_TREE_IDENTITY_SHA256,
)
from scion.problems.warehouse_delivery.w3_installation import (
    CandidateRootIdentity,
    build_warehouse_installation,
)
from scion.problems.warehouse_delivery.w3_prestart_facts import (
    PreStartAbsenceObservation,
    WarehouseW3DryRootReadinessReceipt,
    WarehouseW3PreStartAbsenceReceipt,
    WarehouseW3PreStartFactError,
    WarehouseW3RuntimeAccountReceipt,
)
from scion.runtime.execution.launch_authority import AcceptedLaunchAuthority


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


def _launch_pair():
    run_template = (
        Path(__file__).parents[4]
        / "problems"
        / "warehouse_delivery"
        / "systemd"
        / "scion-w3@.service"
    ).read_bytes()
    close_template = (
        Path(__file__).parents[4]
        / "problems"
        / "warehouse_delivery"
        / "systemd"
        / "scion-w3-close@.service"
    ).read_bytes()
    source_commit = "0123456789abcdef0123456789abcdef01234567"
    authority = AcceptedLaunchAuthority.from_bytes(
        _canonical(
            {
                "schema": "scion.generic-launch-authority.v1",
                "problem_kind": "warehouse-w3",
                "source_commit": source_commit,
                "source_tree": "89abcdef0123456789abcdef0123456789abcdef",
                "manifest": {
                    "path": EXPECTED_MANIFEST_NAME,
                    "sha256": EXPECTED_MANIFEST_SHA256,
                    "size_bytes": 1,
                },
                "root_basename": "accepted-w3-root",
                "nonce": "3" * 64,
                "nonce_ledger_parent": ("/var/lib/scion/runs/w3/.nonce-ledger/claims"),
                "expected_rows": 172,
                "artifact_names": ["analysis.json", "routes.json", "summary.json"],
                "scientific_design_sha256": "1" * 64,
                "correction_design_sha256": "2" * 64,
                "native_acceptance_contract_sha256": "3" * 64,
                "native_acceptance_record_sha256": "4" * 64,
                "sealed_store_aggregate_sha256": "5" * 64,
                "environment_receipt_sha256": "6" * 64,
                "run_template_sha256": hashlib.sha256(run_template).hexdigest(),
                "close_template_sha256": hashlib.sha256(close_template).hexdigest(),
                "guardian_source_sha256": "7" * 64,
                "thin_tool_source_sha256": "8" * 64,
                "closer_source_sha256": "9" * 64,
                "inputs": [
                    {
                        "logical_path": EXPECTED_MANIFEST_NAME,
                        "sealed_path": f"sealed/{EXPECTED_MANIFEST_NAME}",
                        "sha256": EXPECTED_MANIFEST_SHA256,
                        "size_bytes": 1,
                        "provenance": {
                            "kind": "git_blob",
                            "commit": source_commit,
                            "path": EXPECTED_MANIFEST_NAME,
                            "blob_oid": "a" * 40,
                        },
                    }
                ],
                "retry": False,
                "resume": False,
                "reuse": False,
            }
        )
    )
    installation = build_warehouse_installation(
        authority,
        run_root=Path("/srv/accepted-w3-root"),
        run_template_raw=run_template,
        close_template_raw=close_template,
    )
    return authority, installation


def _candidate_gate(authority, installation) -> CandidateGateReceipt:
    return CandidateGateReceipt.from_bytes(
        _canonical(
            {
                "schema": "scion.w3-candidate-gate.v2",
                "state": "CANDIDATE_ACCEPTED_INSTALLATION_ABSENT",
                "selection_key": "a" * 64,
                "launch_id": installation.launch_id,
                "nonce": authority.nonce,
                "authority_sha256": authority.authority_sha256,
                "installation_sha256": installation.installation_sha256,
                "source_receipt_sha256": "b" * 64,
                "candidate_verification_sha256": "c" * 64,
                "double_wheel_receipt_sha256": "d" * 64,
                "semantic_environment_receipt_sha256": "e" * 64,
                "environment_content_receipt_sha256": "6" * 64,
                "candidate_probe_sha256": "f" * 64,
                "simulated_final_probe_sha256": "1" * 64,
                "simulated_relocation_ref_sha256": "2" * 64,
                "simulated_relocation_evidence_sha256": "3" * 64,
                "candidate_root": "/tmp/w3-candidate",
                "candidate_root_identity": {
                    "device": 7,
                    "inode": 8,
                    "mode": 0o555,
                    "uid": 1000,
                    "gid": 1000,
                    "nlink": 2,
                },
                "accepted_root": installation.run_root,
                "accepted_root_identity": {
                    "device": 8,
                    "inode": 9,
                    "mode": 0o555,
                    "uid": 1000,
                    "gid": 1000,
                    "nlink": 2,
                },
                "accepted_root_read_only": True,
                "accepted_root_inventory_sha256": "4" * 64,
                "manifest_sha256": EXPECTED_MANIFEST_SHA256,
                "source_tree_identity_sha256": (EXPECTED_SOURCE_TREE_IDENTITY_SHA256),
                "composition_inspection_sha256": "5" * 64,
                "absence_facts_sha256": "6" * 64,
                "external_installation_required": True,
                "cell_count": 43,
                "job_count": 172,
                "formal_jobs_started": 0,
                "formal_execution_authorized": False,
                "filesystem_mutated": False,
                "retry": False,
                "resume": False,
                "reuse": False,
            }
        )
    )


def _dry_inputs():
    authority, installation = _launch_pair()
    candidate = _candidate_gate(authority, installation)
    return {
        "candidate_gate": candidate,
        "installation": installation,
        "observed_identity": candidate.accepted_root_identity,
        "observed_inventory_sha256": candidate.accepted_root_inventory_sha256,
        "observed_inventory_count": 57,
        "observed_read_only": True,
        "composition_state": "LAUNCH_READY",
    }


def _absence_inputs():
    authority, installation = _launch_pair()
    terminal = installation.terminal_root
    service_cgroup = f"/sys/fs/cgroup/system.slice/{installation.run_unit}"
    subjects = {
        "artifacts": f"{terminal}/artifacts",
        "dynamic_control": f"{terminal}/control",
        "external_nonce_claim": (
            f"{installation.nonce_ledger_parent}/{authority.nonce}.claim.json"
        ),
        "invocation_nonce_claim": (f"{terminal}/control/invocation_claimed.v1.json"),
        "process": installation.run_unit,
        "raw": f"{terminal}/raw",
        "service_cgroup": service_cgroup,
        "start_issued": (
            f"/var/lib/scion/acceptances/w3/{installation.launch_id}"
            "/start/START_ISSUED"
        ),
        "supervisor_cgroup": f"{service_cgroup}/supervisor",
        "terminal_root": terminal,
    }
    observations = tuple(
        PreStartAbsenceObservation(role=role, subject=subjects[role])
        for role in sorted(subjects)
    )
    return {
        "authority": authority,
        "installation": installation,
        "observations": observations,
    }


def test_dry_root_readiness_round_trip_closes_exact_candidate_facts() -> None:
    inputs = _dry_inputs()

    receipt = WarehouseW3DryRootReadinessReceipt.create(**inputs)

    assert receipt.identity.uid == 1000
    assert receipt.inventory_count == 57
    assert receipt.composition_state == "LAUNCH_READY"
    assert receipt.cell_count == 43
    assert receipt.job_count == 172
    assert receipt.formal_jobs_started == 0
    assert receipt.formal_execution_authorized is False
    assert receipt.filesystem_mutated is False
    assert (
        WarehouseW3DryRootReadinessReceipt.from_bytes(
            receipt.raw,
            **inputs,
        )
        == receipt
    )
    with pytest.raises(TypeError, match="parsed from exact bytes"):
        WarehouseW3DryRootReadinessReceipt()


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (
        (
            "observed_identity",
            CandidateRootIdentity(
                device=8,
                inode=10,
                mode=0o555,
                uid=1000,
                gid=1000,
                nlink=2,
            ),
            "differs from candidate gate",
        ),
        ("observed_inventory_sha256", "7" * 64, "differs from candidate gate"),
        ("observed_inventory_count", 0, "integer >= 1"),
        ("observed_read_only", False, "differs from candidate gate"),
        ("composition_state", "NOT_READY", "differs from candidate gate"),
    ),
)
def test_dry_root_readiness_rejects_each_observation_drift(
    field: str,
    value: object,
    message: str,
) -> None:
    inputs = _dry_inputs()
    inputs[field] = value

    with pytest.raises(WarehouseW3PreStartFactError, match=message):
        WarehouseW3DryRootReadinessReceipt.create(**inputs)


def test_dry_root_readiness_rejects_installation_and_raw_drift() -> None:
    inputs = _dry_inputs()
    changed_installation = replace(
        inputs["installation"],
        run_root="/srv/other-root",
    )
    with pytest.raises(
        WarehouseW3PreStartFactError,
        match="binding differs",
    ):
        WarehouseW3DryRootReadinessReceipt.create(
            **{**inputs, "installation": changed_installation}
        )

    receipt = WarehouseW3DryRootReadinessReceipt.create(**inputs)
    changed = json.loads(receipt.raw)
    changed["inventory_count"] = 58
    with pytest.raises(WarehouseW3PreStartFactError, match="producer binding"):
        WarehouseW3DryRootReadinessReceipt.from_bytes(
            _canonical(changed),
            **inputs,
        )
    changed["unknown"] = False
    with pytest.raises(WarehouseW3PreStartFactError, match="fields differ"):
        WarehouseW3DryRootReadinessReceipt.from_bytes(
            _canonical(changed),
            **inputs,
        )
    with pytest.raises(WarehouseW3PreStartFactError, match="not canonical"):
        WarehouseW3DryRootReadinessReceipt.from_bytes(
            receipt.raw.rstrip(b"\n"),
            **inputs,
        )


def test_prestart_absence_round_trip_derives_exact_sorted_inventory() -> None:
    inputs = _absence_inputs()

    receipt = WarehouseW3PreStartAbsenceReceipt.create(**inputs)

    roles = tuple(observation.role for observation in receipt.observations)
    assert roles == tuple(sorted(roles))
    subjects = {item.role: item.subject for item in receipt.observations}
    assert subjects["process"] == inputs["installation"].run_unit
    assert subjects["dynamic_control"] == (
        f"{inputs['installation'].terminal_root}/control"
    )
    assert subjects["supervisor_cgroup"].endswith("/supervisor")
    assert subjects["start_issued"].endswith("/start/START_ISSUED")
    assert (
        WarehouseW3PreStartAbsenceReceipt.from_bytes(
            receipt.raw,
            **inputs,
        )
        == receipt
    )
    with pytest.raises(TypeError, match="parsed from exact bytes"):
        WarehouseW3PreStartAbsenceReceipt()


def test_prestart_absence_rejects_role_subject_state_or_tuple_drift() -> None:
    inputs = _absence_inputs()
    observations = inputs["observations"]

    with pytest.raises(WarehouseW3PreStartFactError, match="role differs"):
        PreStartAbsenceObservation(role="unknown", subject="/tmp/unknown")
    with pytest.raises(WarehouseW3PreStartFactError, match="not ABSENT"):
        PreStartAbsenceObservation(
            role="raw",
            subject="/tmp/raw",
            state="PRESENT",
        )
    changed_subject = (
        *observations[:-1],
        PreStartAbsenceObservation(
            role=observations[-1].role,
            subject="/tmp/wrong",
        ),
    )
    for drifted in (
        observations[:-1],
        tuple(reversed(observations)),
        changed_subject,
    ):
        with pytest.raises(
            WarehouseW3PreStartFactError,
            match="inventory differs",
        ):
            WarehouseW3PreStartAbsenceReceipt.create(
                **{**inputs, "observations": drifted}
            )


def test_prestart_absence_parser_rejects_unknown_duplicate_and_state_drift() -> None:
    inputs = _absence_inputs()
    receipt = WarehouseW3PreStartAbsenceReceipt.create(**inputs)
    changed = json.loads(receipt.raw)
    changed["observations"][0]["state"] = "PRESENT"
    with pytest.raises(WarehouseW3PreStartFactError, match="not ABSENT"):
        WarehouseW3PreStartAbsenceReceipt.from_bytes(
            _canonical(changed),
            **inputs,
        )

    changed = json.loads(receipt.raw)
    changed["unknown"] = False
    with pytest.raises(WarehouseW3PreStartFactError, match="fields differ"):
        WarehouseW3PreStartAbsenceReceipt.from_bytes(
            _canonical(changed),
            **inputs,
        )
    duplicate = receipt.raw.replace(
        b'"reuse":false,',
        b'"reuse":false,"reuse":false,',
        1,
    )
    with pytest.raises(WarehouseW3PreStartFactError, match="not canonical JSON"):
        WarehouseW3PreStartAbsenceReceipt.from_bytes(
            duplicate,
            **inputs,
        )


def test_runtime_account_round_trip_binds_observed_pwd_result() -> None:
    receipt = WarehouseW3RuntimeAccountReceipt.create(
        observed_name="clawd",
        observed_uid=1001,
        observed_gid=1002,
    )

    assert (receipt.name, receipt.uid, receipt.gid, receipt.source) == (
        "clawd",
        1001,
        1002,
        "pwd.getpwnam",
    )
    assert (
        WarehouseW3RuntimeAccountReceipt.from_bytes(
            receipt.raw,
            observed_name="clawd",
            observed_uid=1001,
            observed_gid=1002,
        )
        == receipt
    )
    with pytest.raises(TypeError, match="parsed from exact bytes"):
        WarehouseW3RuntimeAccountReceipt()


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (
        ("observed_name", "root", "name differs"),
        ("observed_uid", True, "integer >= 0"),
        ("observed_gid", False, "integer >= 0"),
        ("observed_uid", -1, "integer >= 0"),
        ("observed_gid", -1, "integer >= 0"),
    ),
)
def test_runtime_account_rejects_observed_identity_drift(
    field: str,
    value: object,
    message: str,
) -> None:
    inputs = {
        "observed_name": "clawd",
        "observed_uid": 1001,
        "observed_gid": 1002,
    }
    inputs[field] = value

    with pytest.raises(WarehouseW3PreStartFactError, match=message):
        WarehouseW3RuntimeAccountReceipt.create(**inputs)


def test_runtime_account_parser_rejects_raw_source_control_and_canonical_drift() -> (
    None
):
    inputs = {
        "observed_name": "clawd",
        "observed_uid": 1001,
        "observed_gid": 1002,
    }
    receipt = WarehouseW3RuntimeAccountReceipt.create(**inputs)
    for field, value in (
        ("name", "root"),
        ("uid", 1003),
        ("gid", 1004),
        ("source", "caller"),
        ("retry", True),
    ):
        changed = json.loads(receipt.raw)
        changed[field] = value
        with pytest.raises(WarehouseW3PreStartFactError):
            WarehouseW3RuntimeAccountReceipt.from_bytes(
                _canonical(changed),
                **inputs,
            )

    changed = json.loads(receipt.raw)
    changed["unknown"] = False
    with pytest.raises(WarehouseW3PreStartFactError, match="fields differ"):
        WarehouseW3RuntimeAccountReceipt.from_bytes(
            _canonical(changed),
            **inputs,
        )
    with pytest.raises(WarehouseW3PreStartFactError, match="not canonical"):
        WarehouseW3RuntimeAccountReceipt.from_bytes(
            receipt.raw.rstrip(b"\n"),
            **inputs,
        )
