from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

import scion.problems.warehouse_delivery.w3_candidate_gate as gate_module
import scion.problems.warehouse_delivery.w3_root_staging as root_staging_module
import scion.runtime.execution.external_linux as external_linux
from scion.problems.warehouse_delivery.w3_candidate_gate import (
    CandidateGateClosureBundle,
)
from scion.problems.warehouse_delivery.w3_candidate_ingress import (
    pin_candidate_gate_ingress,
    publish_candidate_gate_ingress,
)
from scion.problems.warehouse_delivery.w3_installation import prepare_candidate
from scion.problems.warehouse_delivery.w3_root_staging import (
    WarehouseW3RootStagingError,
    WarehouseW3RootStagingVerification,
    verify_imported_w3_candidate,
)
from scion.runtime.execution.external_linux import pin_absolute_directory
from scion.runtime.execution.external_linux import ImmutableTreeImportReceipt
from scion.tests.unit.problems.warehouse_delivery.test_w3_installation import (
    NONCE,
    _prepared_inputs,
)
from scion.tests.unit.problems.warehouse_delivery.test_w3_environment_receipts import (
    _semantic,
    semantic_inputs,
)
from scion.tests.unit.problems.warehouse_delivery.w3_candidate_gate_support import (
    make_candidate_gate_closure,
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


@pytest.fixture(autouse=True)
def _verified_external_root_facts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        root_staging_module,
        "verify_namespace_probe_execution_binary",
        lambda fact: fact,
    )
    monkeypatch.setattr(
        root_staging_module,
        "verify_wheel_bytes_against_receipt",
        lambda raw, receipt, *, trusted_source_snapshot: receipt,
    )


def _closure(
    prepared,
    *,
    accepted_root: Path,
    semantic,
    candidate_verification_sha256: str | None = None,
) -> CandidateGateClosureBundle:
    candidate = prepared.verification_receipt
    if candidate_verification_sha256 is not None:
        value = json.loads(candidate.raw)
        value["candidate_receipt_sha256"] = candidate_verification_sha256
        candidate = type(candidate).from_bytes(_canonical(value))
    return make_candidate_gate_closure(
        candidate=candidate,
        candidate_root=prepared.candidate_root,
        accepted_root=accepted_root,
        nonce=prepared.authority.nonce,
        manifest_sha256=prepared.intent.dry_root_manifest_sha256,
        wheel=semantic.wheel_receipt,
        semantic=semantic,
        environment=prepared.environment_receipt,
    )


def _prepared_with_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    semantic_inputs: dict[str, object],
    *,
    verification_sha256: str | None = None,
):
    (
        intent,
        source,
        objects,
        _environment_root,
        _environment_receipt,
        _runtime_paths,
        accepted_root,
    ) = _prepared_inputs(tmp_path, monkeypatch)
    semantic = _semantic(semantic_inputs)
    prepared = prepare_candidate(
        intent,
        source=source,
        sealed_objects=objects,
        environment_root=semantic_inputs["environment"],
        environment_receipt=semantic.generic_receipt,
        external_runtime_paths=(semantic_inputs["external"],),
        run_root=accepted_root,
        nonce=NONCE,
    )
    accepted_root.mkdir()
    accepted_root.chmod(0o555)
    monkeypatch.setattr(
        gate_module,
        "EXPECTED_MANIFEST_SHA256",
        prepared.intent.dry_root_manifest_sha256,
    )
    closure = _closure(
        prepared,
        accepted_root=accepted_root,
        semantic=semantic,
        candidate_verification_sha256=verification_sha256,
    )
    publish_candidate_gate_ingress(closure)
    return prepared, closure


def _import_and_verify(
    tmp_path: Path,
    prepared,
):
    staging_parent = tmp_path / "root-staging"
    staging_parent.mkdir()
    with (
        pin_candidate_gate_ingress(prepared.candidate_root) as ingress,
        pin_absolute_directory(str(staging_parent)) as pinned_staging,
    ):
        imported = external_linux._import_immutable_tree(
            ingress.candidate.fd,
            pinned_staging.fd,
            "candidate",
            target_uid=os.geteuid(),
            target_gid=os.getegid(),
        )
        verification = root_staging_module._verify_imported_w3_candidate(
            ingress,
            pinned_staging,
            imported,
        )
        return verification, imported, ingress.fact, ingress.gate, ingress.closure


def test_root_staging_replays_candidate_local_chain_through_retained_ingress(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    semantic_inputs: dict[str, object],
) -> None:
    prepared, closure = _prepared_with_gate(
        tmp_path,
        monkeypatch,
        semantic_inputs,
    )
    gate = closure.gate

    verification, imported, ingress_fact, reopened_gate, reopened_closure = (
        _import_and_verify(
            tmp_path,
            prepared,
        )
    )

    assert reopened_gate == gate
    assert reopened_closure == closure
    assert verification.candidate_gate_sha256 == gate.raw_sha256
    assert verification.candidate_gate_ingress_fact_sha256 == ingress_fact.raw_sha256
    assert verification.tree_import_sha256 == imported.raw_sha256
    assert verification.imported_tree_aggregate_sha256 == imported.tree_sha256
    assert verification.candidate_receipt_sha256 == (
        prepared.candidate_receipt.raw_sha256
    )
    assert verification.candidate_content_aggregate_sha256 == (
        prepared.candidate_receipt.content_aggregate_sha256
    )
    assert (
        WarehouseW3RootStagingVerification.from_bytes(
            verification.raw,
            candidate_gate=gate,
            candidate_gate_closure=closure,
            candidate_gate_ingress=ingress_fact,
            tree_import=imported,
            candidate_receipt=prepared.candidate_receipt,
            candidate_verification=prepared.verification_receipt,
            source_receipt=prepared.source_receipt,
            sealed_store_receipt=prepared.sealed_store_receipt,
            environment_receipt=prepared.environment_receipt,
            authority=prepared.authority,
            installation=prepared.installation,
            selection_intent=prepared.intent,
            selection_commit=prepared.selection_commit,
        )
        == verification
    )


def test_root_staging_rejects_gate_subordinate_hash_not_in_imported_candidate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    semantic_inputs: dict[str, object],
) -> None:
    prepared, _closure_bundle = _prepared_with_gate(
        tmp_path,
        monkeypatch,
        semantic_inputs,
        verification_sha256=hashlib.sha256(b"wrong verification").hexdigest(),
    )
    staging_parent = tmp_path / "root-staging"
    staging_parent.mkdir()
    with (
        pin_candidate_gate_ingress(prepared.candidate_root) as ingress,
        pin_absolute_directory(str(staging_parent)) as pinned_staging,
    ):
        imported = external_linux._import_immutable_tree(
            ingress.candidate.fd,
            pinned_staging.fd,
            "candidate",
            target_uid=os.geteuid(),
            target_gid=os.getegid(),
        )
        with pytest.raises(
            WarehouseW3RootStagingError,
            match="semantic replay differs",
        ):
            root_staging_module._verify_imported_w3_candidate(
                ingress,
                pinned_staging,
                imported,
            )


def test_root_staging_rejects_candidate_fixed_inventory_extension(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    semantic_inputs: dict[str, object],
) -> None:
    (
        intent,
        source,
        objects,
        _environment_root,
        _environment_receipt,
        _runtime_paths,
        accepted_root,
    ) = _prepared_inputs(tmp_path, monkeypatch)
    semantic = _semantic(semantic_inputs)
    prepared = prepare_candidate(
        intent,
        source=source,
        sealed_objects=objects,
        environment_root=semantic_inputs["environment"],
        environment_receipt=semantic.generic_receipt,
        external_runtime_paths=(semantic_inputs["external"],),
        run_root=accepted_root,
        nonce=NONCE,
    )
    prepared.candidate_root.chmod(0o755)
    extra = prepared.candidate_root / "unexpected"
    extra.write_bytes(b"unexpected\n")
    extra.chmod(0o444)
    prepared.candidate_root.chmod(0o555)
    accepted_root.mkdir()
    accepted_root.chmod(0o555)
    monkeypatch.setattr(
        gate_module,
        "EXPECTED_MANIFEST_SHA256",
        prepared.intent.dry_root_manifest_sha256,
    )
    publish_candidate_gate_ingress(
        _closure(
            prepared,
            accepted_root=accepted_root,
            semantic=semantic,
        )
    )

    staging_parent = tmp_path / "root-staging"
    staging_parent.mkdir()
    with (
        pin_candidate_gate_ingress(prepared.candidate_root) as ingress,
        pin_absolute_directory(str(staging_parent)) as pinned_staging,
    ):
        imported = external_linux._import_immutable_tree(
            ingress.candidate.fd,
            pinned_staging.fd,
            "candidate",
            target_uid=os.geteuid(),
            target_gid=os.getegid(),
        )
        with pytest.raises(
            WarehouseW3RootStagingError,
            match="fixed inventory differs",
        ):
            root_staging_module._verify_imported_w3_candidate(
                ingress,
                pinned_staging,
                imported,
            )


def test_offline_root_staging_replay_rejects_empty_import_inventory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    semantic_inputs: dict[str, object],
) -> None:
    prepared, _closure_bundle = _prepared_with_gate(
        tmp_path,
        monkeypatch,
        semantic_inputs,
    )
    verification, imported, ingress_fact, gate, closure = _import_and_verify(
        tmp_path,
        prepared,
    )
    empty = ImmutableTreeImportReceipt.create(
        staging_leaf=imported.staging_leaf,
        target_uid=imported.target_uid,
        target_gid=imported.target_gid,
        source_root=imported.source_root,
        staging_root=imported.staging_root,
        entries=(),
    )
    value = json.loads(verification.raw)
    value["tree_import_sha256"] = empty.raw_sha256
    value["imported_tree_aggregate_sha256"] = empty.tree_sha256

    with pytest.raises(
        WarehouseW3RootStagingError,
        match="fixed inventory differs",
    ):
        WarehouseW3RootStagingVerification.from_bytes(
            _canonical(value),
            candidate_gate=gate,
            candidate_gate_closure=closure,
            candidate_gate_ingress=ingress_fact,
            tree_import=empty,
            candidate_receipt=prepared.candidate_receipt,
            candidate_verification=prepared.verification_receipt,
            source_receipt=prepared.source_receipt,
            sealed_store_receipt=prepared.sealed_store_receipt,
            environment_receipt=prepared.environment_receipt,
            authority=prepared.authority,
            installation=prepared.installation,
            selection_intent=prepared.intent,
            selection_commit=prepared.selection_commit,
        )


def test_public_root_staging_verifier_rejects_nonroot_before_semantic_replay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    semantic_inputs: dict[str, object],
) -> None:
    prepared, _closure_bundle = _prepared_with_gate(
        tmp_path,
        monkeypatch,
        semantic_inputs,
    )
    staging_parent = tmp_path / "root-staging"
    staging_parent.mkdir()
    with (
        pin_candidate_gate_ingress(prepared.candidate_root) as ingress,
        pin_absolute_directory(str(staging_parent)) as pinned_staging,
    ):
        imported = external_linux._import_immutable_tree(
            ingress.candidate.fd,
            pinned_staging.fd,
            "candidate",
            target_uid=os.geteuid(),
            target_gid=os.getegid(),
        )
        with pytest.raises(PermissionError, match="effective UID zero"):
            verify_imported_w3_candidate(
                ingress,
                pinned_staging,
                imported,
            )
