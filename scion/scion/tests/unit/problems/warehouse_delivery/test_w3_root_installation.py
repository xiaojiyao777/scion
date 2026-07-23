from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat

import pytest

from scion.problems.warehouse_delivery.w3_candidate_gate import (
    CandidateGateReceipt,
    WarehouseW3CandidateGateError,
)
from scion.problems.warehouse_delivery.w3_composition import (
    EXPECTED_MANIFEST_NAME,
    EXPECTED_MANIFEST_SHA256,
    EXPECTED_SOURCE_TREE_IDENTITY_SHA256,
)
from scion.problems.warehouse_delivery.w3_installation import (
    SealedStoreObject,
    SealedStoreReceipt,
    build_warehouse_installation,
)
from scion.problems.warehouse_delivery.w3_root_installation import (
    WarehouseW3AuthorityPublishedReceipt,
    WarehouseW3ProjectionReceipt,
    WarehouseW3RootInstallationError,
    WarehouseW3StagedCandidateReceipt,
    WarehouseW3StoresPublishedReceipt,
)
from scion.runtime.execution.external_installation import (
    DirectoryIdentity,
    PublishedDirectoryReceipt,
    PublishedRegularFileReceipt,
    PublishedTreeReceipt,
    parse_selected_mountinfo,
    MountBindingReceipt,
)
from scion.runtime.execution.external_linux import (
    FileIdentity,
    ImmutableTreeImportReceipt,
    MountNamespacePair,
    NamespaceIdentity,
)
from scion.runtime.execution.launch_authority import AcceptedLaunchAuthority

# Reuse the already accepted semantic/relocation producer fixture instead of
# synthesizing producer objects or weakening their exact parser.
from scion.tests.unit.problems.warehouse_delivery.test_w3_environment_receipts import (
    _relocation_inputs,
    _relocation_receipt,
    _semantic,
    semantic_inputs,
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


def _sealed_store() -> SealedStoreReceipt:
    raw = b"sealed fixture\n"
    item = SealedStoreObject.generated(
        logical_path="fixture.txt",
        sealed_path="sealed/fixture.txt",
        raw=raw,
        generator_sha256="1" * 64,
        input_sha256=("2" * 64,),
        rule_sha256="3" * 64,
    )
    return SealedStoreReceipt.create((item,))


def _launch_pair(
    sealed_store: SealedStoreReceipt,
    environment_content_sha256: str,
):
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
                "sealed_store_aggregate_sha256": sealed_store.aggregate_sha256,
                "environment_receipt_sha256": environment_content_sha256,
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


def _candidate_gate(
    *,
    authority: AcceptedLaunchAuthority,
    installation,
    semantic_sha256: str,
    generic_sha256: str,
    source_identity: FileIdentity,
    accepted_root_device: int = 8,
    accepted_root_inode: int = 9,
) -> CandidateGateReceipt:
    value = {
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
        "semantic_environment_receipt_sha256": semantic_sha256,
        "environment_content_receipt_sha256": generic_sha256,
        "candidate_probe_sha256": "e" * 64,
        "simulated_final_probe_sha256": "f" * 64,
        "simulated_relocation_ref_sha256": "1" * 64,
        "simulated_relocation_evidence_sha256": "2" * 64,
        "candidate_root": "/tmp/w3-candidate",
        "candidate_root_identity": {
            "device": source_identity.device,
            "inode": source_identity.inode,
            "mode": stat.S_IMODE(source_identity.mode),
            "uid": source_identity.uid,
            "gid": source_identity.gid,
            "nlink": source_identity.link_count,
        },
        "accepted_root": installation.run_root,
        "accepted_root_identity": {
            "device": accepted_root_device,
            "inode": accepted_root_inode,
            "mode": 0o555,
            "uid": 1000,
            "gid": 1000,
            "nlink": 2,
        },
        "accepted_root_read_only": True,
        "accepted_root_inventory_sha256": "3" * 64,
        "manifest_sha256": EXPECTED_MANIFEST_SHA256,
        "source_tree_identity_sha256": EXPECTED_SOURCE_TREE_IDENTITY_SHA256,
        "composition_inspection_sha256": "4" * 64,
        "absence_facts_sha256": "5" * 64,
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
    return CandidateGateReceipt.from_bytes(_canonical(value))


def _tree_import(
    *,
    source_inode: int = 11,
) -> ImmutableTreeImportReceipt:
    return ImmutableTreeImportReceipt.create(
        staging_leaf="staging",
        target_uid=0,
        target_gid=0,
        source_root=FileIdentity(
            device=7,
            inode=source_inode,
            mode=stat.S_IFDIR | 0o555,
            uid=1000,
            gid=1000,
            link_count=2,
            size=4096,
        ),
        staging_root=FileIdentity(
            device=17,
            inode=21,
            mode=stat.S_IFDIR | 0o555,
            uid=0,
            gid=0,
            link_count=2,
            size=4096,
        ),
        entries=(),
    )


def _published_file(
    *,
    role: str,
    path: str,
    raw: bytes,
    inode: int,
) -> PublishedRegularFileReceipt:
    return PublishedRegularFileReceipt.create(
        role=role,
        path=path,
        content_sha256=hashlib.sha256(raw).hexdigest(),
        size_bytes=len(raw),
        device=1,
        inode=inode,
        mode=0o444,
        uid=0,
        gid=0,
        nlink=1,
    )


def _published_directory(
    *,
    role: str,
    path: str,
    inode: int,
    mode: int = 0o755,
    uid: int = 0,
    gid: int = 0,
    device: int = 1,
) -> PublishedDirectoryReceipt:
    return PublishedDirectoryReceipt.create(
        role=role,
        path=path,
        device=device,
        inode=inode,
        mode=mode,
        uid=uid,
        gid=gid,
        nlink=2,
        expected_mode=mode,
        expected_uid=uid,
        expected_gid=gid,
    )


def _mount(
    path: str,
    *,
    read_only: bool,
    inode: int,
    mount_id: int,
) -> MountBindingReceipt:
    option = "ro" if read_only else "rw"
    row = parse_selected_mountinfo(
        (
            f"{mount_id} 1 8:1 / {path} {option},relatime "
            f"- ext4 /dev/sda1 {option},errors=remount-ro\n"
        ).encode(),
        mount_point=path,
    )
    identity = DirectoryIdentity(device=os.makedev(8, 1), inode=inode)
    return MountBindingReceipt.create(
        row=row,
        source_identity=identity,
        destination_identity=identity,
        source_mount_id=mount_id - 1,
        read_only=read_only,
        expected_filesystem_type="ext4",
        expected_mount_root="/",
    )


def _projection_chain(projection_root: str) -> tuple[PublishedDirectoryReceipt, ...]:
    parts = PurePosixPath(projection_root).parts
    paths = tuple(
        str(PurePosixPath(*parts[:index])) for index in range(2, len(parts) + 1)
    )
    return tuple(
        _published_directory(
            role="projection-root" if index == len(paths) - 1 else "projection-parent",
            path=path,
            inode=100 + index,
        )
        for index, path in enumerate(paths)
    )


def test_staged_candidate_round_trip_binds_exact_source_and_import() -> None:
    imported = _tree_import()
    sealed = _sealed_store()
    authority, installation = _launch_pair(sealed, "6" * 64)
    candidate = _candidate_gate(
        authority=authority,
        installation=installation,
        semantic_sha256="7" * 64,
        generic_sha256="6" * 64,
        source_identity=imported.source_root,
    )

    receipt = WarehouseW3StagedCandidateReceipt.create(
        candidate_gate=candidate,
        tree_import=imported,
    )

    assert receipt.imported_tree_aggregate_sha256 == imported.tree_sha256
    assert receipt.source_identity == imported.source_root
    assert (
        WarehouseW3StagedCandidateReceipt.from_bytes(
            receipt.raw,
            candidate_gate=candidate,
            tree_import=imported,
        )
        == receipt
    )
    with pytest.raises(TypeError, match="parsed from exact bytes"):
        WarehouseW3StagedCandidateReceipt()


def test_staged_candidate_rejects_source_identity_or_canonical_drift() -> None:
    imported = _tree_import()
    sealed = _sealed_store()
    authority, installation = _launch_pair(sealed, "6" * 64)
    candidate = _candidate_gate(
        authority=authority,
        installation=installation,
        semantic_sha256="7" * 64,
        generic_sha256="6" * 64,
        source_identity=imported.source_root,
    )
    receipt = WarehouseW3StagedCandidateReceipt.create(
        candidate_gate=candidate,
        tree_import=imported,
    )

    with pytest.raises(WarehouseW3RootInstallationError, match="identity differs"):
        WarehouseW3StagedCandidateReceipt.create(
            candidate_gate=candidate,
            tree_import=_tree_import(source_inode=12),
        )
    with pytest.raises(WarehouseW3RootInstallationError, match="not canonical"):
        WarehouseW3StagedCandidateReceipt.from_bytes(
            receipt.raw.rstrip(b"\n"),
            candidate_gate=candidate,
            tree_import=imported,
        )


def test_stores_round_trip_closes_exact_roles_paths_and_aggregates(
    semantic_inputs: dict[str, object],
) -> None:
    semantic = _semantic(semantic_inputs)
    candidate_path, simulated_path = _relocation_inputs(semantic_inputs, semantic)
    relocation = _relocation_receipt(semantic, candidate_path, simulated_path)
    sealed = _sealed_store()
    authority, installation = _launch_pair(
        sealed,
        semantic.generic_receipt_sha256,
    )
    imported = _tree_import()
    candidate = _candidate_gate(
        authority=authority,
        installation=installation,
        semantic_sha256=semantic.raw_sha256,
        generic_sha256=semantic.generic_receipt_sha256,
        source_identity=imported.source_root,
    )
    sealed_tree = PublishedTreeReceipt.create(
        role="sealed",
        path=installation.sealed_root,
        source_receipt_sha256=sealed.raw_sha256,
        expected_tree_sha256=sealed.aggregate_sha256,
        reopened_tree_sha256=sealed.aggregate_sha256,
        identity=_root_tree_identity(31),
    )
    environment_tree = PublishedTreeReceipt.create(
        role="environment",
        path=installation.environment_root,
        source_receipt_sha256=semantic.generic_receipt_sha256,
        expected_tree_sha256=semantic.environment_inventory_sha256,
        reopened_tree_sha256=semantic.environment_inventory_sha256,
        identity=_root_tree_identity(32),
    )

    receipt = WarehouseW3StoresPublishedReceipt.create(
        candidate_gate=candidate,
        authority=authority,
        installation=installation,
        sealed_store=sealed,
        environment_content=semantic,
        sealed_publication=sealed_tree,
        environment_publication=environment_tree,
        environment_relocation=relocation,
    )

    assert receipt.environment_path == installation.environment_root
    assert receipt.environment_path == relocation.final_environment_path
    assert (
        WarehouseW3StoresPublishedReceipt.from_bytes(
            receipt.raw,
            candidate_gate=candidate,
            authority=authority,
            installation=installation,
            sealed_store=sealed,
            environment_content=semantic,
            sealed_publication=sealed_tree,
            environment_publication=environment_tree,
            environment_relocation=relocation,
        )
        == receipt
    )


def _root_tree_identity(inode: int, *, device: int = 1):
    from scion.runtime.execution.external_installation import DirectorySnapshot

    return DirectorySnapshot(
        device=device,
        inode=inode,
        mode=0o555,
        uid=0,
        gid=0,
        nlink=2,
    )


def test_stores_reject_role_or_content_producer_drift(
    semantic_inputs: dict[str, object],
) -> None:
    semantic = _semantic(semantic_inputs)
    candidate_path, simulated_path = _relocation_inputs(semantic_inputs, semantic)
    relocation = _relocation_receipt(semantic, candidate_path, simulated_path)
    sealed = _sealed_store()
    authority, installation = _launch_pair(
        sealed,
        semantic.generic_receipt_sha256,
    )
    imported = _tree_import()
    candidate = _candidate_gate(
        authority=authority,
        installation=installation,
        semantic_sha256=semantic.raw_sha256,
        generic_sha256=semantic.generic_receipt_sha256,
        source_identity=imported.source_root,
    )
    wrong_sealed = PublishedTreeReceipt.create(
        role="environment",
        path=installation.sealed_root,
        source_receipt_sha256=sealed.raw_sha256,
        expected_tree_sha256=sealed.aggregate_sha256,
        reopened_tree_sha256=sealed.aggregate_sha256,
        identity=_root_tree_identity(33),
    )
    environment_tree = PublishedTreeReceipt.create(
        role="environment",
        path=installation.environment_root,
        source_receipt_sha256=semantic.generic_receipt_sha256,
        expected_tree_sha256=semantic.environment_inventory_sha256,
        reopened_tree_sha256=semantic.environment_inventory_sha256,
        identity=_root_tree_identity(34),
    )

    with pytest.raises(WarehouseW3RootInstallationError, match="role, path"):
        WarehouseW3StoresPublishedReceipt.create(
            candidate_gate=candidate,
            authority=authority,
            installation=installation,
            sealed_store=sealed,
            environment_content=semantic,
            sealed_publication=wrong_sealed,
            environment_publication=environment_tree,
            environment_relocation=relocation,
        )

    semantic_source_tree = PublishedTreeReceipt.create(
        role="environment",
        path=installation.environment_root,
        source_receipt_sha256=semantic.raw_sha256,
        expected_tree_sha256=semantic.environment_inventory_sha256,
        reopened_tree_sha256=semantic.environment_inventory_sha256,
        identity=_root_tree_identity(35),
    )
    with pytest.raises(
        WarehouseW3RootInstallationError,
        match="content binding differs",
    ):
        WarehouseW3StoresPublishedReceipt.create(
            candidate_gate=candidate,
            authority=authority,
            installation=installation,
            sealed_store=sealed,
            environment_content=semantic,
            sealed_publication=PublishedTreeReceipt.create(
                role="sealed",
                path=installation.sealed_root,
                source_receipt_sha256=sealed.raw_sha256,
                expected_tree_sha256=sealed.aggregate_sha256,
                reopened_tree_sha256=sealed.aggregate_sha256,
                identity=_root_tree_identity(36),
            ),
            environment_publication=semantic_source_tree,
            environment_relocation=relocation,
        )


def test_authority_publication_round_trip_and_rejects_role_or_nonce_mode() -> None:
    sealed = _sealed_store()
    authority, installation = _launch_pair(sealed, "6" * 64)
    authority_file = _published_file(
        role="authority",
        path=installation.authority_path,
        raw=authority.raw,
        inode=41,
    )
    installation_file = _published_file(
        role="installation",
        path=f"/var/lib/scion/installations/w3/{installation.launch_id}.json",
        raw=installation.raw,
        inode=42,
    )
    nonce = _published_directory(
        role="nonce-claims",
        path=installation.nonce_ledger_parent,
        inode=43,
        mode=0o700,
        uid=1000,
        gid=1000,
    )

    receipt = WarehouseW3AuthorityPublishedReceipt.create(
        authority=authority,
        installation=installation,
        authority_publication=authority_file,
        installation_publication=installation_file,
        nonce_directory=nonce,
    )
    assert receipt.nonce_uid == 1000
    assert (
        WarehouseW3AuthorityPublishedReceipt.from_bytes(
            receipt.raw,
            authority=authority,
            installation=installation,
            authority_publication=authority_file,
            installation_publication=installation_file,
            nonce_directory=nonce,
        )
        == receipt
    )

    wrong_role = _published_file(
        role="installation",
        path=installation.authority_path,
        raw=authority.raw,
        inode=44,
    )
    with pytest.raises(WarehouseW3RootInstallationError, match="role, path"):
        WarehouseW3AuthorityPublishedReceipt.create(
            authority=authority,
            installation=installation,
            authority_publication=wrong_role,
            installation_publication=installation_file,
            nonce_directory=nonce,
        )
    wrong_mode = _published_directory(
        role="nonce-claims",
        path=installation.nonce_ledger_parent,
        inode=45,
        mode=0o755,
        uid=1000,
        gid=1000,
    )
    with pytest.raises(WarehouseW3RootInstallationError, match="ownership differs"):
        WarehouseW3AuthorityPublishedReceipt.create(
            authority=authority,
            installation=installation,
            authority_publication=authority_file,
            installation_publication=installation_file,
            nonce_directory=wrong_mode,
        )

    changed_owner = _published_directory(
        role="nonce-claims",
        path=installation.nonce_ledger_parent,
        inode=46,
        mode=0o700,
        uid=1001,
        gid=1001,
    )
    with pytest.raises(
        WarehouseW3RootInstallationError,
        match="producer binding differs",
    ):
        WarehouseW3AuthorityPublishedReceipt.from_bytes(
            receipt.raw,
            authority=authority,
            installation=installation,
            authority_publication=authority_file,
            installation_publication=installation_file,
            nonce_directory=changed_owner,
        )


def _projection_inputs(authority, installation):
    projection = installation.projection_root
    source_device = os.makedev(8, 1)
    imported = _tree_import()
    candidate = _candidate_gate(
        authority=authority,
        installation=installation,
        semantic_sha256="7" * 64,
        generic_sha256="6" * 64,
        source_identity=imported.source_root,
        accepted_root_device=source_device,
        accepted_root_inode=61,
    )
    sealed_source = PublishedTreeReceipt.create(
        role="sealed",
        path=installation.sealed_root,
        source_receipt_sha256="1" * 64,
        expected_tree_sha256="2" * 64,
        reopened_tree_sha256="2" * 64,
        identity=_root_tree_identity(62, device=source_device),
    )
    environment_source = PublishedTreeReceipt.create(
        role="environment",
        path=installation.environment_root,
        source_receipt_sha256="3" * 64,
        expected_tree_sha256="4" * 64,
        reopened_tree_sha256="4" * 64,
        identity=_root_tree_identity(63, device=source_device),
    )
    nonce_source = _published_directory(
        role="nonce-claims",
        path=installation.nonce_ledger_parent,
        inode=64,
        mode=0o700,
        uid=1000,
        gid=1000,
        device=source_device,
    )
    authority_file = _published_file(
        role="authority",
        path=f"{projection}/authority.json",
        raw=authority.raw,
        inode=51,
    )
    installation_file = _published_file(
        role="installation",
        path=f"{projection}/installation.json",
        raw=installation.raw,
        inode=52,
    )
    return {
        "authority": authority,
        "installation": installation,
        "candidate_gate": candidate,
        "sealed_publication": sealed_source,
        "environment_publication": environment_source,
        "nonce_directory": nonce_source,
        "namespace_pair": MountNamespacePair(
            self_namespace=NamespaceIdentity(device=1, inode=2),
            pid1_namespace=NamespaceIdentity(device=1, inode=2),
        ),
        "destination_parent_chain": _projection_chain(projection),
        "boot_id": "12345678-1234-1234-1234-123456789abc",
        "run_mount": _mount(
            installation.projected_run_root,
            read_only=False,
            inode=61,
            mount_id=101,
        ),
        "sealed_mount": _mount(
            installation.projected_sealed_root,
            read_only=True,
            inode=62,
            mount_id=102,
        ),
        "environment_mount": _mount(
            installation.projected_environment_root,
            read_only=True,
            inode=63,
            mount_id=103,
        ),
        "nonce_claims_mount": _mount(
            installation.projected_nonce_ledger_parent,
            read_only=False,
            inode=64,
            mount_id=104,
        ),
        "authority_publication": authority_file,
        "installation_publication": installation_file,
    }


def test_projection_round_trip_closes_six_roles_namespace_and_parent_chain() -> None:
    sealed = _sealed_store()
    authority, installation = _launch_pair(sealed, "6" * 64)
    inputs = _projection_inputs(authority, installation)

    receipt = WarehouseW3ProjectionReceipt.create(**inputs)

    assert len(json.loads(receipt.raw)["inventory"]) == 6
    assert receipt.namespace_pair.matches
    assert receipt.run_source_fact_sha256 == inputs["candidate_gate"].raw_sha256
    assert receipt.sealed_source_fact_sha256 == inputs["sealed_publication"].raw_sha256
    assert len(receipt.parent_chain_sha256) == len(inputs["destination_parent_chain"])
    assert WarehouseW3ProjectionReceipt.from_bytes(receipt.raw, **inputs) == receipt


def test_projection_rejects_namespace_path_policy_or_incomplete_parent_chain() -> None:
    sealed = _sealed_store()
    authority, installation = _launch_pair(sealed, "6" * 64)
    inputs = _projection_inputs(authority, installation)

    wrong_namespace = dict(inputs)
    wrong_namespace["namespace_pair"] = MountNamespacePair(
        self_namespace=NamespaceIdentity(device=1, inode=2),
        pid1_namespace=NamespaceIdentity(device=1, inode=3),
    )
    with pytest.raises(WarehouseW3RootInstallationError, match="namespaces differ"):
        WarehouseW3ProjectionReceipt.create(**wrong_namespace)

    incomplete_chain = dict(inputs)
    incomplete_chain["destination_parent_chain"] = inputs["destination_parent_chain"][
        1:
    ]
    with pytest.raises(WarehouseW3RootInstallationError, match="parent chain"):
        WarehouseW3ProjectionReceipt.create(**incomplete_chain)

    unexpected_mode_chain = dict(inputs)
    chain = inputs["destination_parent_chain"]
    unexpected_mode_chain["destination_parent_chain"] = (
        _published_directory(
            role=chain[0].role,
            path=chain[0].path,
            inode=chain[0].inode,
            mode=0o711,
        ),
        *chain[1:],
    )
    with pytest.raises(WarehouseW3RootInstallationError, match="parent chain"):
        WarehouseW3ProjectionReceipt.create(**unexpected_mode_chain)

    wrong_policy = dict(inputs)
    wrong_policy["environment_mount"] = _mount(
        installation.projected_environment_root,
        read_only=False,
        inode=65,
        mount_id=105,
    )
    with pytest.raises(WarehouseW3RootInstallationError, match="read-only policy"):
        WarehouseW3ProjectionReceipt.create(**wrong_policy)

    wrong_path = dict(inputs)
    wrong_path["run_mount"] = _mount(
        f"{installation.projected_run_root}-wrong",
        read_only=False,
        inode=66,
        mount_id=106,
    )
    with pytest.raises(WarehouseW3RootInstallationError, match="mount path"):
        WarehouseW3ProjectionReceipt.create(**wrong_path)


@pytest.mark.parametrize(
    "mount_name,path_name,read_only,inode,mount_id",
    (
        ("run_mount", "projected_run_root", False, 161, 201),
        ("sealed_mount", "projected_sealed_root", True, 162, 202),
        ("environment_mount", "projected_environment_root", True, 163, 203),
        (
            "nonce_claims_mount",
            "projected_nonce_ledger_parent",
            False,
            164,
            204,
        ),
    ),
)
def test_projection_rejects_each_mount_source_identity_drift(
    mount_name: str,
    path_name: str,
    read_only: bool,
    inode: int,
    mount_id: int,
) -> None:
    sealed = _sealed_store()
    authority, installation = _launch_pair(sealed, "6" * 64)
    inputs = _projection_inputs(authority, installation)
    inputs[mount_name] = _mount(
        getattr(installation, path_name),
        read_only=read_only,
        inode=inode,
        mount_id=mount_id,
    )

    with pytest.raises(WarehouseW3RootInstallationError, match="source identity"):
        WarehouseW3ProjectionReceipt.create(**inputs)


def test_aggregate_parser_rejects_unknown_field_and_mixed_exact_producer() -> None:
    sealed = _sealed_store()
    authority, installation = _launch_pair(sealed, "6" * 64)
    inputs = _projection_inputs(authority, installation)
    receipt = WarehouseW3ProjectionReceipt.create(**inputs)
    changed = json.loads(receipt.raw)
    changed["unknown"] = True
    with pytest.raises(WarehouseW3RootInstallationError, match="fields differ"):
        WarehouseW3ProjectionReceipt.from_bytes(_canonical(changed), **inputs)

    alternate = dict(inputs)
    alternate["authority_publication"] = _published_file(
        role="authority",
        path=f"{installation.projection_root}/authority.json",
        raw=authority.raw,
        inode=99,
    )
    with pytest.raises(
        WarehouseW3RootInstallationError,
        match="producer binding differs",
    ):
        WarehouseW3ProjectionReceipt.from_bytes(receipt.raw, **alternate)

    alternate_mount = dict(inputs)
    alternate_mount["run_mount"] = _mount(
        installation.projected_run_root,
        read_only=False,
        inode=100,
        mount_id=107,
    )
    with pytest.raises(
        WarehouseW3RootInstallationError,
        match="source identity differs",
    ):
        WarehouseW3ProjectionReceipt.from_bytes(receipt.raw, **alternate_mount)

    alternate_source = dict(inputs)
    original_source = inputs["sealed_publication"]
    alternate_source["sealed_publication"] = PublishedTreeReceipt.create(
        role="sealed",
        path=installation.sealed_root,
        source_receipt_sha256="5" * 64,
        expected_tree_sha256=original_source.expected_tree_sha256,
        reopened_tree_sha256=original_source.reopened_tree_sha256,
        identity=original_source.identity,
    )
    with pytest.raises(
        WarehouseW3RootInstallationError,
        match="producer binding differs",
    ):
        WarehouseW3ProjectionReceipt.from_bytes(receipt.raw, **alternate_source)

    source_fact_drift = json.loads(receipt.raw)
    source_fact_drift["inventory"][1]["source_fact_sha256"] = "f" * 64
    with pytest.raises(
        WarehouseW3RootInstallationError,
        match="producer binding differs",
    ):
        WarehouseW3ProjectionReceipt.from_bytes(
            _canonical(source_fact_drift),
            **inputs,
        )


def test_candidate_gate_fixture_remains_exact() -> None:
    imported = _tree_import()
    sealed = _sealed_store()
    authority, installation = _launch_pair(sealed, "6" * 64)
    candidate = _candidate_gate(
        authority=authority,
        installation=installation,
        semantic_sha256="7" * 64,
        generic_sha256="6" * 64,
        source_identity=imported.source_root,
    )
    assert CandidateGateReceipt.from_bytes(candidate.raw) == candidate
    changed = json.loads(candidate.raw)
    changed["cell_count"] = 44
    with pytest.raises(WarehouseW3CandidateGateError, match="state differs"):
        CandidateGateReceipt.from_bytes(_canonical(changed))
