from __future__ import annotations

import copy
import hashlib
import json
import pickle
from pathlib import Path

import pytest

from scion.runtime.execution.launch_authority import (
    AcceptedLaunchAuthority,
    InstallationRecord,
    LaunchAuthorityError,
    NonceClaimOwner,
    inspect_nonce_claim,
)
from scion.runtime.execution.systemd255 import (
    ConfiguredUnitProperties,
    UnitRole,
)
from scion.runtime.execution.systemd_acquisition import ConfiguredPairFact

SOURCE_COMMIT = "1" * 40
SOURCE_TREE = "2" * 40
MANIFEST_BYTES = b"manifest\n"
MANIFEST_SHA256 = hashlib.sha256(MANIFEST_BYTES).hexdigest()
NONCE = "3" * 64
LAUNCH_ID = "4" * 64
ARTIFACTS = (
    "warehouse_w3_fixed_arm_results.v1.json",
    "warehouse_w3_fixed_arm_report.v1.md",
    "warehouse_w3_fixed_arm_receipt.v1.json",
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


def _authority_value(
    tmp_path: Path,
    *,
    provenance: dict[str, object] | None = None,
) -> dict[str, object]:
    if provenance is None:
        provenance = {
            "kind": "git_blob",
            "commit": SOURCE_COMMIT,
            "path": "control/warehouse_w3_fixed_arm_manifest.v1.json",
            "blob_oid": "5" * 40,
        }
    return {
        "schema": "scion.generic-launch-authority.v1",
        "problem_kind": "warehouse-w3",
        "source_commit": SOURCE_COMMIT,
        "source_tree": SOURCE_TREE,
        "manifest": {
            "path": "control/warehouse_w3_fixed_arm_manifest.v1.json",
            "sha256": MANIFEST_SHA256,
            "size_bytes": len(MANIFEST_BYTES),
        },
        "root_basename": "accepted-w3-root",
        "nonce": NONCE,
        "nonce_ledger_parent": str(tmp_path / "ledger"),
        "expected_rows": 172,
        "artifact_names": list(ARTIFACTS),
        "scientific_design_sha256": "1" * 64,
        "correction_design_sha256": "2" * 64,
        "native_acceptance_contract_sha256": "3" * 64,
        "native_acceptance_record_sha256": "4" * 64,
        "sealed_store_aggregate_sha256": "6" * 64,
        "environment_receipt_sha256": "7" * 64,
        "run_template_sha256": "8" * 64,
        "close_template_sha256": "9" * 64,
        "guardian_source_sha256": "a" * 64,
        "thin_tool_source_sha256": "b" * 64,
        "closer_source_sha256": "c" * 64,
        "inputs": [
            {
                "logical_path": ("control/warehouse_w3_fixed_arm_manifest.v1.json"),
                "sealed_path": (
                    "sealed/control/" "warehouse_w3_fixed_arm_manifest.v1.json"
                ),
                "sha256": MANIFEST_SHA256,
                "size_bytes": len(MANIFEST_BYTES),
                "provenance": provenance,
            }
        ],
        "retry": False,
        "resume": False,
        "reuse": False,
    }


def _authority(tmp_path: Path) -> AcceptedLaunchAuthority:
    return AcceptedLaunchAuthority.from_bytes(_canonical(_authority_value(tmp_path)))


def _installation_value(
    tmp_path: Path,
    authority: AcceptedLaunchAuthority,
) -> dict[str, object]:
    projection_root = tmp_path / "projections" / LAUNCH_ID
    run_root = tmp_path / authority.root_basename
    run_unit = f"scion-w3@{LAUNCH_ID}.service"
    close_unit = f"scion-w3-close@{LAUNCH_ID}.service"
    run = ConfiguredUnitProperties.from_receipts(
        UnitRole.RUN,
        {
            "Delegate": "pids",
            "DelegateSubgroup": "supervisor",
            "CollectMode": "inactive",
            "Restart": "no",
            "KillMode": "control-group",
            "TimeoutStopSec": "infinity",
            "OnSuccess": close_unit,
            "OnFailure": close_unit,
        },
        {
            "Id": run_unit,
            "Delegate": "yes",
            "DelegateControllers": "pids",
            "DelegateSubgroup": "supervisor",
            "CollectMode": "inactive",
            "Restart": "no",
            "KillMode": "control-group",
            "TimeoutStopUSec": "infinity",
            "OnSuccess": close_unit,
            "OnFailure": close_unit,
        },
        expected_unit=run_unit,
        expected_peer=close_unit,
    )
    closer = ConfiguredUnitProperties.from_receipts(
        UnitRole.CLOSER,
        {
            "CollectMode": "inactive",
            "Restart": "no",
            "TimeoutStartSec": "infinity",
            "After": run_unit,
        },
        {
            "Id": close_unit,
            "CollectMode": "inactive",
            "Restart": "no",
            "TimeoutStartUSec": "infinity",
            "After": run_unit,
        },
        expected_unit=close_unit,
        expected_peer=run_unit,
    )
    pair = ConfiguredPairFact.create(run, closer)
    return {
        "schema": "scion.generic-launch-installation.v1",
        "launch_id": LAUNCH_ID,
        "authority_sha256": authority.authority_sha256,
        "authority_path": str(
            tmp_path / "authorities" / f"{authority.authority_sha256}.json"
        ),
        "problem_kind": authority.problem_kind,
        "manifest_sha256": authority.manifest_sha256,
        "run_root": str(run_root),
        "terminal_root": str(run_root / "control" / "invocation"),
        "nonce": authority.nonce,
        "nonce_ledger_parent": authority.nonce_ledger_parent,
        "sealed_root": str(tmp_path / "sealed-store"),
        "sealed_store_aggregate_sha256": (authority.sealed_store_aggregate_sha256),
        "environment_root": str(tmp_path / "environment"),
        "environment_receipt_sha256": (authority.environment_receipt_sha256),
        "projection_root": str(projection_root),
        "run_template_sha256": authority.run_template_sha256,
        "close_template_sha256": authority.close_template_sha256,
        "run_unit": run_unit,
        "close_unit": close_unit,
        "configured_pair": pair.to_mapping(),
        "configured_pair_sha256": pair.configured_pair_sha256,
        "retry": False,
        "resume": False,
        "reuse": False,
    }


def _installation(
    tmp_path: Path,
    authority: AcceptedLaunchAuthority,
) -> InstallationRecord:
    return InstallationRecord.from_bytes(
        _canonical(_installation_value(tmp_path, authority)),
        authority,
    )


def _prepare_claim_directories(
    authority: AcceptedLaunchAuthority,
    installation: InstallationRecord,
) -> None:
    Path(authority.nonce_ledger_parent).mkdir(parents=True)
    terminal = Path(installation.projected_terminal_root)
    Path(installation.projected_nonce_ledger_parent).mkdir(parents=True)
    terminal.mkdir(parents=True)
    for child in ("control", "evidence", "raw", "artifacts"):
        (terminal / child).mkdir()


def test_canonical_authority_and_installation_are_exact_and_acyclic(
    tmp_path: Path,
) -> None:
    authority = _authority(tmp_path)
    installation = _installation(tmp_path, authority)

    assert authority.authority_sha256 == hashlib.sha256(authority.raw).hexdigest()
    assert (
        installation.installation_sha256 == hashlib.sha256(installation.raw).hexdigest()
    )
    assert authority.expected_rows == 172
    assert authority.artifact_names == ARTIFACTS
    assert authority.inputs[0].to_mapping()["provenance"]["kind"] == "git_blob"
    assert "authority_sha256" not in json.loads(authority.raw)
    assert "launch_id" not in json.loads(authority.raw)
    assert installation.terminal_root == (f"{installation.run_root}/control/invocation")


def test_authority_rejects_duplicate_noncanonical_unknown_and_bad_order(
    tmp_path: Path,
) -> None:
    raw = _canonical(_authority_value(tmp_path))
    duplicate = b'{"schema":"scion.generic-launch-authority.v1",' + raw[1:]
    with pytest.raises(LaunchAuthorityError, match="duplicate JSON key"):
        AcceptedLaunchAuthority.from_bytes(duplicate)
    with pytest.raises(LaunchAuthorityError, match="not one canonical"):
        AcceptedLaunchAuthority.from_bytes(b" " + raw)

    unknown = _authority_value(tmp_path)
    unknown["authority_sha256"] = "f" * 64
    with pytest.raises(LaunchAuthorityError, match="fields differ"):
        AcceptedLaunchAuthority.from_bytes(_canonical(unknown))

    two_inputs = _authority_value(tmp_path)
    two_inputs["inputs"].insert(
        0,
        {
            "logical_path": "z-source",
            "sealed_path": "sealed/z-source",
            "sha256": "e" * 64,
            "size_bytes": 0,
            "provenance": {
                "kind": "git_blob",
                "commit": SOURCE_COMMIT,
                "path": "z-source",
                "blob_oid": "f" * 40,
            },
        },
    )
    with pytest.raises(LaunchAuthorityError, match="not sorted"):
        AcceptedLaunchAuthority.from_bytes(_canonical(two_inputs))


def test_generated_provenance_is_deeply_immutable(tmp_path: Path) -> None:
    inputs = ["d" * 64, "e" * 64]
    value = _authority_value(
        tmp_path,
        provenance={
            "kind": "generated",
            "generator_sha256": "a" * 64,
            "input_sha256": inputs,
            "rule_sha256": "b" * 64,
        },
    )
    authority = AcceptedLaunchAuthority.from_bytes(_canonical(value))
    inputs.append("f" * 64)

    stored = authority.inputs[0].to_mapping()["provenance"]["input_sha256"]
    assert stored == ["d" * 64, "e" * 64]
    assert type(dict(authority.inputs[0].provenance)["input_sha256"]) is tuple


@pytest.mark.parametrize(
    ("field", "replacement", "message"),
    (
        ("manifest_sha256", "0" * 64, "manifest_sha256 differs"),
        ("nonce", "0" * 64, "nonce differs"),
        (
            "run_template_sha256",
            "0" * 64,
            "run_template_sha256 differs",
        ),
    ),
)
def test_installation_rejects_cross_binding_drift(
    tmp_path: Path,
    field: str,
    replacement: str,
    message: str,
) -> None:
    authority = _authority(tmp_path)
    value = _installation_value(tmp_path, authority)
    value[field] = replacement
    with pytest.raises(LaunchAuthorityError, match=message):
        InstallationRecord.from_bytes(_canonical(value), authority)


def test_installation_rejects_copied_or_colliding_roots(
    tmp_path: Path,
) -> None:
    authority = _authority(tmp_path)
    value = _installation_value(tmp_path, authority)
    value["run_root"] = str(tmp_path / "copied-root")
    value["terminal_root"] = str(tmp_path / "copied-root" / "control" / "invocation")
    with pytest.raises(LaunchAuthorityError, match="basename differs"):
        InstallationRecord.from_bytes(_canonical(value), authority)

    value = _installation_value(tmp_path, authority)
    value["environment_root"] = value["sealed_root"]
    with pytest.raises(LaunchAuthorityError, match="identities are not distinct"):
        InstallationRecord.from_bytes(_canonical(value), authority)


def test_nonce_claim_is_external_first_exact_and_one_use(
    tmp_path: Path,
) -> None:
    authority = _authority(tmp_path)
    installation = _installation(tmp_path, authority)
    _prepare_claim_directories(authority, installation)

    owner = NonceClaimOwner(authority, installation)
    expected = owner.expected_claim
    with pytest.raises(TypeError, match="not copyable"):
        copy.copy(owner)
    with pytest.raises(TypeError, match="not serializable"):
        pickle.dumps(owner)
    claim = owner.claim()
    assert claim == expected
    assert inspect_nonce_claim(authority, installation) == expected
    assert (
        Path(installation.projected_nonce_ledger_parent)
        / f"{authority.nonce}.claim.json"
    ).read_bytes() == expected.raw
    assert (
        Path(installation.projected_terminal_root)
        / "control"
        / "invocation_claimed.v1.json"
    ).read_bytes() == expected.raw
    with pytest.raises(LaunchAuthorityError, match="not open"):
        owner.claim()
    with pytest.raises(LaunchAuthorityError, match="external nonce publication failed"):
        NonceClaimOwner(authority, installation).claim()


def test_external_claim_consumes_nonce_when_root_publication_fails(
    tmp_path: Path,
) -> None:
    authority = _authority(tmp_path)
    installation = _installation(tmp_path, authority)
    Path(installation.projected_nonce_ledger_parent).mkdir(parents=True)

    owner = NonceClaimOwner(authority, installation)
    expected = owner.expected_claim
    with pytest.raises(LaunchAuthorityError, match="claim directory"):
        owner.claim()
    assert (
        Path(installation.projected_nonce_ledger_parent)
        / f"{authority.nonce}.claim.json"
    ).read_bytes() == expected.raw
    with pytest.raises(LaunchAuthorityError, match="not open"):
        owner.claim()


def test_claim_inspection_rejects_byte_drift(tmp_path: Path) -> None:
    authority = _authority(tmp_path)
    installation = _installation(tmp_path, authority)
    _prepare_claim_directories(authority, installation)
    NonceClaimOwner(authority, installation).claim()
    invocation_claim = (
        Path(installation.projected_terminal_root)
        / "control"
        / "invocation_claimed.v1.json"
    )
    invocation_claim.write_bytes(b"drift\n")

    with pytest.raises(LaunchAuthorityError, match="bytes differ"):
        inspect_nonce_claim(authority, installation)
