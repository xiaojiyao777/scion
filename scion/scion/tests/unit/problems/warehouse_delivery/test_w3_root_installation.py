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
from scion.problems.warehouse_delivery.w3_environment_receipts import (
    LiveEnvironmentRehashFact,
)
from scion.problems.warehouse_delivery.w3_prestart_facts import (
    PreStartAbsenceObservation,
    WarehouseW3DryRootReadinessReceipt,
    WarehouseW3PreStartAbsenceReceipt,
    WarehouseW3RuntimeAccountReceipt,
)
from scion.problems.warehouse_delivery.w3_root_installation import (
    WAREHOUSE_W3_PRESTART_EVIDENCE_SCHEMA,
    WarehouseW3AuthorityPublishedReceipt,
    WarehouseW3PreStartEvidence,
    WarehouseW3ProjectionReceipt,
    WarehouseW3RootInstallationError,
    WarehouseW3StagedCandidateReceipt,
    WarehouseW3StoresPublishedReceipt,
)
from scion.runtime.execution.external_installation import (
    INSTALL_PHASES,
    DirectoryIdentity,
    DirectorySnapshot,
    LoadedManagerReceipt,
    ManagerIdentity,
    ManagerReloadReceipt,
    MountBindingReceipt,
    PublishedDirectoryReceipt,
    PublishedRegularFileReceipt,
    PublishedTreeReceipt,
    RootPhaseIntentReceipt,
    RootPhaseReceipt,
    SelectionReceipt,
    UnitPublicationReceipt,
    parse_selected_mountinfo,
)
from scion.runtime.execution.external_linux import (
    FileIdentity,
    ImmutableTreeImportReceipt,
    MountNamespacePair,
    NamespaceIdentity,
)
from scion.runtime.execution.launch_authority import AcceptedLaunchAuthority
from scion.runtime.execution.systemd_acquisition import ConfiguredPairReadback

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


def _template_raws() -> tuple[bytes, bytes]:
    systemd_root = (
        Path(__file__).parents[4] / "problems" / "warehouse_delivery" / "systemd"
    )
    return (
        (systemd_root / "scion-w3@.service").read_bytes(),
        (systemd_root / "scion-w3-close@.service").read_bytes(),
    )


def _structured_exec(command: str) -> tuple[object, ...]:
    argv = command.split(" ")
    return (
        argv[0],
        argv,
        False,
        1,
        2,
        3,
        4,
        4242,
        0,
        0,
    )


def _manager_bundle(
    authority,
    installation,
    *,
    boot_id: str,
):
    projection = installation.projection_root
    python = f"{projection}/environment/bin/python"
    tool = f"{projection}/sealed/bin/scion-w3-tool"
    run_start = f"{python} -B -s {tool} run {installation.launch_id}"
    run_stop = f"{python} -B -s {tool} seal-unit-drained {installation.launch_id}"
    close_start = f"{python} -B -s {tool} close {installation.launch_id}"
    read_only = (
        f"{projection}/installation.json",
        f"{projection}/authority.json",
        f"{projection}/sealed",
        f"{projection}/environment",
    )
    read_write = (f"{projection}/run", f"{projection}/nonce-claims")
    run_wiring = {
        "Type": "exec",
        "User": "clawd",
        "Group": "clawd",
        "UMask": "0077",
        "ExecStart": run_start,
        "ExecStopPost": run_stop,
        "ExitType": "main",
        "SendSIGKILL": "yes",
        "OOMPolicy": "stop",
        "NoNewPrivileges": "yes",
        "PrivateTmp": "yes",
        "PrivateMounts": "yes",
        "ProtectSystem": "strict",
        "ProtectHome": "read-only",
        "ProtectControlGroups": "no",
        "ProtectProc": "invisible",
        "ProcSubset": "all",
        "ReadOnlyPaths": " ".join(read_only),
        "ReadWritePaths": " ".join(read_write),
    }
    close_wiring = {
        "Type": "oneshot",
        "User": "clawd",
        "Group": "clawd",
        "UMask": "0077",
        "ExecStart": close_start,
        "NoNewPrivileges": "yes",
        "PrivateTmp": "yes",
        "ProtectSystem": "strict",
        "ProtectHome": "read-only",
        "ReadOnlyPaths": " ".join(read_only),
        "ReadWritePaths": " ".join(read_write),
    }
    run_properties = {
        "Id": installation.run_unit,
        "Type": "exec",
        "User": "clawd",
        "Group": "clawd",
        "UMask": 0o077,
        "ExecStart": [_structured_exec(run_start)],
        "ExecStopPost": [_structured_exec(run_stop)],
        "ExitType": "main",
        "SendSIGKILL": True,
        "OOMPolicy": "stop",
        "NoNewPrivileges": True,
        "PrivateTmp": True,
        "PrivateMounts": True,
        "ProtectSystem": "strict",
        "ProtectHome": "read-only",
        "ProtectControlGroups": False,
        "ProtectProc": "invisible",
        "ProcSubset": "all",
        "ReadOnlyPaths": list(read_only),
        "ReadWritePaths": list(read_write),
        "Delegate": True,
        "DelegateControllers": ["pids"],
        "DelegateSubgroup": "supervisor",
        "CollectMode": "inactive",
        "Restart": "no",
        "KillMode": "control-group",
        "TimeoutStopUSec": (1 << 64) - 1,
        "OnSuccess": [installation.close_unit],
        "OnFailure": [installation.close_unit],
    }
    close_properties = {
        "Id": installation.close_unit,
        "Type": "oneshot",
        "User": "clawd",
        "Group": "clawd",
        "UMask": 0o077,
        "ExecStart": [_structured_exec(close_start)],
        "NoNewPrivileges": True,
        "PrivateTmp": True,
        "ProtectSystem": "strict",
        "ProtectHome": "read-only",
        "ReadOnlyPaths": list(read_only),
        "ReadWritePaths": list(read_write),
        "CollectMode": "inactive",
        "Restart": "no",
        "TimeoutStartUSec": (1 << 64) - 1,
        "After": [installation.run_unit],
    }
    configured_readback = ConfiguredPairReadback.create(
        run_unit=installation.run_unit,
        close_unit=installation.close_unit,
        run_properties=run_properties,
        close_properties=close_properties,
        configured_pair=installation.configured_pair,
        run_wiring=run_wiring,
        close_wiring=close_wiring,
    )
    run_template, close_template = _template_raws()
    run_publication = _published_file(
        role="run-fragment",
        path="/etc/systemd/system/scion-w3@.service",
        raw=run_template,
        inode=501,
    )
    close_publication = _published_file(
        role="close-fragment",
        path="/etc/systemd/system/scion-w3-close@.service",
        raw=close_template,
        inode=502,
    )
    unit_publication = UnitPublicationReceipt.create(
        authority=authority,
        installation=installation,
        run_template_raw=run_template,
        close_template_raw=close_template,
        run_publication=run_publication,
        close_publication=close_publication,
    )
    identity = ManagerIdentity(
        unique_owner=":1.42",
        boot_id=boot_id,
        version="255.4-1ubuntu8",
    )
    manager_reload = ManagerReloadReceipt.create(
        manager_identity=identity,
        configured_readback=configured_readback,
        unit_publication=unit_publication,
    )
    loaded_fields = {
        "DropInPaths": [],
        "LoadState": "loaded",
        "ActiveState": "inactive",
        "SubState": "dead",
        "Job": [0, "/"],
        "InvocationID": [0] * 16,
        "Transient": False,
    }
    loaded_manager = LoadedManagerReceipt.create(
        manager_identity=identity,
        run_object_path="/org/freedesktop/systemd1/unit/scion_2dw3_2drun",
        close_object_path="/org/freedesktop/systemd1/unit/scion_2dw3_2dclose",
        run_properties={
            **run_properties,
            **loaded_fields,
            "FragmentPath": unit_publication.run_fragment_path,
        },
        close_properties={
            **close_properties,
            **loaded_fields,
            "FragmentPath": unit_publication.close_fragment_path,
        },
        configured_readback=configured_readback,
        unit_publication=unit_publication,
        manager_reload=manager_reload,
    )
    return unit_publication, manager_reload, loaded_manager


def _selection_receipt(
    candidate,
    staged,
    *,
    candidate_sha256: str | None = None,
) -> SelectionReceipt:
    candidate_identity = candidate.candidate_root_identity
    # Root selection is a distinct user-owned directory, not the root-owned
    # immutable staging destination.
    selection_identity = DirectorySnapshot(
        device=29,
        inode=30,
        mode=0o555,
        uid=1000,
        gid=1000,
        nlink=2,
    )
    return SelectionReceipt.create(
        selection_key=candidate.selection_key,
        launch_id=candidate.launch_id,
        nonce=candidate.nonce,
        authority_sha256=candidate.authority_sha256,
        candidate_sha256=(
            candidate.raw_sha256 if candidate_sha256 is None else candidate_sha256
        ),
        preparation_intent_sha256="8" * 64,
        preparation_commit_sha256="9" * 64,
        import_receipt_sha256=staged.tree_import_sha256,
        imported_staging_aggregate_sha256=(staged.imported_tree_aggregate_sha256),
        source_candidate_identity=DirectorySnapshot(
            device=candidate_identity.device,
            inode=candidate_identity.inode,
            mode=candidate_identity.mode,
            uid=candidate_identity.uid,
            gid=candidate_identity.gid,
            nlink=candidate_identity.nlink,
        ),
        source_selection_identity=selection_identity,
    )


def _absence_receipt(authority, installation):
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
    return WarehouseW3PreStartAbsenceReceipt.create(
        authority=authority,
        installation=installation,
        observations=tuple(
            PreStartAbsenceObservation(role=role, subject=subjects[role])
            for role in sorted(subjects)
        ),
    )


def _prestart_phase_prefix(
    launch_id: str,
    effect_producers: tuple[object, ...],
    manager_reload: ManagerReloadReceipt,
    *,
    drift_index: int | None = None,
):
    intents: list[RootPhaseIntentReceipt] = []
    receipts: list[RootPhaseReceipt] = []
    for index, (phase, producer) in enumerate(
        zip(INSTALL_PHASES[:7], effect_producers, strict=True)
    ):
        intent = RootPhaseIntentReceipt.create(
            launch_id=launch_id,
            phase=phase,
            predecessor_sha256=(() if index == 0 else (receipts[-1].raw_sha256,)),
            effect_authority_sha256=hashlib.sha256(
                f"prestart-authority:{phase.value}".encode()
            ).hexdigest(),
        )
        receipt = RootPhaseReceipt.create(
            intent=intent,
            effect_sha256=("f" * 64 if drift_index == index else producer.raw_sha256),
        )
        intents.append(intent)
        receipts.append(receipt)
    intents.append(
        RootPhaseIntentReceipt.create(
            launch_id=launch_id,
            phase=INSTALL_PHASES[7],
            predecessor_sha256=(receipts[-1].raw_sha256,),
            effect_authority_sha256=manager_reload.raw_sha256,
        )
    )
    return tuple(intents), tuple(receipts)


def _prestart_inputs(semantic_inputs: dict[str, object]) -> dict[str, object]:
    semantic = _semantic(semantic_inputs)
    candidate_path, simulated_path = _relocation_inputs(semantic_inputs, semantic)
    relocation = _relocation_receipt(semantic, candidate_path, simulated_path)
    sealed = _sealed_store()
    authority, installation = _launch_pair(
        sealed,
        semantic.generic_receipt_sha256,
    )
    imported = _tree_import()
    source_device = os.makedev(8, 1)
    candidate = _candidate_gate(
        authority=authority,
        installation=installation,
        semantic_sha256=semantic.raw_sha256,
        generic_sha256=semantic.generic_receipt_sha256,
        source_identity=imported.source_root,
        accepted_root_device=source_device,
        accepted_root_inode=61,
    )
    staged = WarehouseW3StagedCandidateReceipt.create(
        candidate_gate=candidate,
        tree_import=imported,
    )
    selection = _selection_receipt(candidate, staged)
    sealed_publication = PublishedTreeReceipt.create(
        role="sealed",
        path=installation.sealed_root,
        source_receipt_sha256=sealed.raw_sha256,
        expected_tree_sha256=sealed.aggregate_sha256,
        reopened_tree_sha256=sealed.aggregate_sha256,
        identity=_root_tree_identity(62, device=source_device),
    )
    environment_publication = PublishedTreeReceipt.create(
        role="environment",
        path=installation.environment_root,
        source_receipt_sha256=semantic.generic_receipt_sha256,
        expected_tree_sha256=semantic.environment_inventory_sha256,
        reopened_tree_sha256=semantic.environment_inventory_sha256,
        identity=_root_tree_identity(63, device=source_device),
    )
    stores = WarehouseW3StoresPublishedReceipt.create(
        candidate_gate=candidate,
        authority=authority,
        installation=installation,
        sealed_store=sealed,
        environment_content=semantic,
        sealed_publication=sealed_publication,
        environment_publication=environment_publication,
        environment_relocation=relocation,
    )
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
    nonce_directory = _published_directory(
        role="nonce-claims",
        path=installation.nonce_ledger_parent,
        inode=64,
        mode=0o700,
        uid=1000,
        gid=1000,
        device=source_device,
    )
    authority_published = WarehouseW3AuthorityPublishedReceipt.create(
        authority=authority,
        installation=installation,
        authority_publication=authority_file,
        installation_publication=installation_file,
        nonce_directory=nonce_directory,
    )
    projection_root = installation.projection_root
    projection = WarehouseW3ProjectionReceipt.create(
        authority=authority,
        installation=installation,
        candidate_gate=candidate,
        sealed_publication=sealed_publication,
        environment_publication=environment_publication,
        nonce_directory=nonce_directory,
        namespace_pair=MountNamespacePair(
            self_namespace=NamespaceIdentity(device=1, inode=2),
            pid1_namespace=NamespaceIdentity(device=1, inode=2),
        ),
        destination_parent_chain=_projection_chain(projection_root),
        boot_id="12345678-1234-1234-1234-123456789abc",
        run_mount=_mount(
            installation.projected_run_root,
            read_only=False,
            inode=61,
            mount_id=101,
        ),
        sealed_mount=_mount(
            installation.projected_sealed_root,
            read_only=True,
            inode=62,
            mount_id=102,
        ),
        environment_mount=_mount(
            installation.projected_environment_root,
            read_only=True,
            inode=63,
            mount_id=103,
        ),
        nonce_claims_mount=_mount(
            installation.projected_nonce_ledger_parent,
            read_only=False,
            inode=64,
            mount_id=104,
        ),
        authority_publication=_published_file(
            role="authority",
            path=f"{projection_root}/authority.json",
            raw=authority.raw,
            inode=51,
        ),
        installation_publication=_published_file(
            role="installation",
            path=f"{projection_root}/installation.json",
            raw=installation.raw,
            inode=52,
        ),
    )
    unit_publication, manager_reload, loaded_manager = _manager_bundle(
        authority,
        installation,
        boot_id=projection.boot_id,
    )
    environment_rehash = LiveEnvironmentRehashFact._from_observed(
        phase="preclaim",
        environment_root=Path(stores.environment_path),
        content_receipt=semantic,
        observed_generic_receipt=semantic.generic_receipt,
    )
    dry_root = WarehouseW3DryRootReadinessReceipt.create(
        candidate_gate=candidate,
        installation=installation,
        observed_identity=candidate.accepted_root_identity,
        observed_inventory_sha256=candidate.accepted_root_inventory_sha256,
        observed_inventory_count=57,
        observed_read_only=True,
        composition_state="LAUNCH_READY",
    )
    prestart_absence = _absence_receipt(authority, installation)
    runtime_account = WarehouseW3RuntimeAccountReceipt.create(
        observed_name="clawd",
        observed_uid=1000,
        observed_gid=1000,
    )
    effect_producers = (
        staged,
        selection,
        stores,
        authority_published,
        projection,
        unit_publication,
        manager_reload,
    )
    phase_intents, phase_receipts = _prestart_phase_prefix(
        installation.launch_id,
        effect_producers,
        manager_reload,
    )
    return {
        "authority": authority,
        "installation": installation,
        "candidate_gate": candidate,
        "staged_candidate": staged,
        "selection": selection,
        "stores_published": stores,
        "authority_published": authority_published,
        "projection": projection,
        "unit_publication": unit_publication,
        "manager_reload": manager_reload,
        "loaded_manager": loaded_manager,
        "environment_rehash": environment_rehash,
        "dry_root": dry_root,
        "prestart_absence": prestart_absence,
        "runtime_account": runtime_account,
        "phase_intents": phase_intents,
        "phase_receipts": phase_receipts,
    }


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


def _prestart_effect_producers(inputs: dict[str, object]) -> tuple[object, ...]:
    return (
        inputs["staged_candidate"],
        inputs["selection"],
        inputs["stores_published"],
        inputs["authority_published"],
        inputs["projection"],
        inputs["unit_publication"],
        inputs["manager_reload"],
    )


def test_prestart_evidence_round_trip_closes_exact_pending_gate(
    semantic_inputs: dict[str, object],
) -> None:
    inputs = _prestart_inputs(semantic_inputs)

    evidence = WarehouseW3PreStartEvidence.create(**inputs)
    value = json.loads(evidence.raw)

    assert value["schema"] == WAREHOUSE_W3_PRESTART_EVIDENCE_SCHEMA
    assert value["state"] == "PRESTART_GATES_REACQUIRED_NOT_STARTED"
    assert value["formal_jobs_started"] == 0
    assert value["pending_intent_sha256"] == inputs["phase_intents"][-1].raw_sha256
    assert (
        value["predecessor_phase_receipt_sha256"]
        == inputs["phase_receipts"][-1].raw_sha256
    )
    assert value["phase_effect_sha256"] == {
        receipt.phase.value: receipt.effect_sha256
        for receipt in inputs["phase_receipts"]
    }
    assert frozenset(value["producer_receipt_sha256"]) == frozenset(
        {
            "candidate_gate",
            "loaded_manager",
            "environment_rehash",
            "dry_root",
            "prestart_absence",
            "runtime_account",
        }
    )
    unit_value = json.loads(inputs["unit_publication"].raw)
    assert unit_value["schema"] == "scion.unit-publication-acceptance.v3"
    assert unit_value["run_publication_sha256"] == (
        inputs["unit_publication"].run_publication_sha256
    )
    assert unit_value["close_publication_sha256"] == (
        inputs["unit_publication"].close_publication_sha256
    )
    forbidden = {
        "acceptance_sha256",
        "installed_acceptance_sha256",
        "phase_intent_sha256",
        "phase_receipt_sha256",
        "authorization_sha256",
        "start_issue_sha256",
        "issued_at_utc",
        "recorded_at_utc",
        "timestamp",
    }
    assert forbidden.isdisjoint(value)
    assert inputs["selection"].candidate_sha256 == inputs["candidate_gate"].raw_sha256
    assert (
        inputs["selection"].source_selection_identity.device,
        inputs["selection"].source_selection_identity.inode,
    ) != (
        inputs["staged_candidate"].destination_identity.device,
        inputs["staged_candidate"].destination_identity.inode,
    )
    assert WarehouseW3PreStartEvidence.from_bytes(evidence.raw, **inputs) == evidence
    with pytest.raises(TypeError, match="parsed from exact bytes"):
        WarehouseW3PreStartEvidence()


def test_prestart_evidence_requires_pending_i7_not_committed_k7(
    semantic_inputs: dict[str, object],
) -> None:
    inputs = _prestart_inputs(semantic_inputs)

    missing_pending = dict(inputs)
    missing_pending["phase_intents"] = inputs["phase_intents"][:-1]
    with pytest.raises(
        WarehouseW3RootInstallationError,
        match="pending I7 transaction",
    ):
        WarehouseW3PreStartEvidence.create(**missing_pending)

    committed = RootPhaseReceipt.create(
        intent=inputs["phase_intents"][-1],
        effect_sha256="e" * 64,
    )
    committed_k7 = dict(inputs)
    committed_k7["phase_receipts"] = (*inputs["phase_receipts"], committed)
    with pytest.raises(
        WarehouseW3RootInstallationError,
        match="pending I7 transaction",
    ):
        WarehouseW3PreStartEvidence.create(**committed_k7)

    wrong_pending = RootPhaseIntentReceipt.create(
        launch_id=inputs["installation"].launch_id,
        phase=INSTALL_PHASES[7],
        predecessor_sha256=(inputs["phase_receipts"][-1].raw_sha256,),
        effect_authority_sha256="d" * 64,
    )
    wrong_authority = dict(inputs)
    wrong_authority["phase_intents"] = (
        *inputs["phase_intents"][:-1],
        wrong_pending,
    )
    with pytest.raises(
        WarehouseW3RootInstallationError,
        match="effect authority differs",
    ):
        WarehouseW3PreStartEvidence.create(**wrong_authority)


@pytest.mark.parametrize("phase_index", tuple(range(7)))
def test_prestart_evidence_rejects_every_committed_phase_effect_drift(
    semantic_inputs: dict[str, object],
    phase_index: int,
) -> None:
    inputs = _prestart_inputs(semantic_inputs)
    phase_intents, phase_receipts = _prestart_phase_prefix(
        inputs["installation"].launch_id,
        _prestart_effect_producers(inputs),
        inputs["manager_reload"],
        drift_index=phase_index,
    )
    drifted = {
        **inputs,
        "phase_intents": phase_intents,
        "phase_receipts": phase_receipts,
    }

    with pytest.raises(
        WarehouseW3RootInstallationError,
        match="phase effect differs",
    ):
        WarehouseW3PreStartEvidence.create(**drifted)


def test_prestart_evidence_defines_selection_candidate_as_closed_gate(
    semantic_inputs: dict[str, object],
) -> None:
    inputs = _prestart_inputs(semantic_inputs)
    alternate = _selection_receipt(
        inputs["candidate_gate"],
        inputs["staged_candidate"],
        candidate_sha256=inputs["candidate_gate"].source_receipt_sha256,
    )
    effect_producers = list(_prestart_effect_producers(inputs))
    effect_producers[1] = alternate
    phase_intents, phase_receipts = _prestart_phase_prefix(
        inputs["installation"].launch_id,
        tuple(effect_producers),
        inputs["manager_reload"],
    )
    drifted = {
        **inputs,
        "selection": alternate,
        "phase_intents": phase_intents,
        "phase_receipts": phase_receipts,
    }

    with pytest.raises(
        WarehouseW3RootInstallationError,
        match="selection binding differs",
    ):
        WarehouseW3PreStartEvidence.create(**drifted)


def test_prestart_evidence_rejects_projection_source_fact_drift(
    semantic_inputs: dict[str, object],
) -> None:
    inputs = _prestart_inputs(semantic_inputs)
    installation = inputs["installation"]
    authority = inputs["authority"]
    candidate = inputs["candidate_gate"]
    stores = inputs["stores_published"]
    source_device = os.makedev(8, 1)
    sealed_source = PublishedTreeReceipt.create(
        role="sealed",
        path=stores.sealed_path,
        source_receipt_sha256=stores.sealed_store_sha256,
        expected_tree_sha256=stores.sealed_tree_aggregate_sha256,
        reopened_tree_sha256=stores.sealed_tree_aggregate_sha256,
        identity=_root_tree_identity(162, device=source_device),
    )
    environment_source = PublishedTreeReceipt.create(
        role="environment",
        path=stores.environment_path,
        source_receipt_sha256=candidate.environment_content_receipt_sha256,
        expected_tree_sha256=stores.environment_tree_aggregate_sha256,
        reopened_tree_sha256=stores.environment_tree_aggregate_sha256,
        identity=_root_tree_identity(163, device=source_device),
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
    alternate_projection = WarehouseW3ProjectionReceipt.create(
        authority=authority,
        installation=installation,
        candidate_gate=candidate,
        sealed_publication=sealed_source,
        environment_publication=environment_source,
        nonce_directory=nonce_source,
        namespace_pair=MountNamespacePair(
            self_namespace=NamespaceIdentity(device=1, inode=2),
            pid1_namespace=NamespaceIdentity(device=1, inode=2),
        ),
        destination_parent_chain=_projection_chain(installation.projection_root),
        boot_id=inputs["projection"].boot_id,
        run_mount=_mount(
            installation.projected_run_root,
            read_only=False,
            inode=61,
            mount_id=301,
        ),
        sealed_mount=_mount(
            installation.projected_sealed_root,
            read_only=True,
            inode=162,
            mount_id=302,
        ),
        environment_mount=_mount(
            installation.projected_environment_root,
            read_only=True,
            inode=163,
            mount_id=303,
        ),
        nonce_claims_mount=_mount(
            installation.projected_nonce_ledger_parent,
            read_only=False,
            inode=64,
            mount_id=304,
        ),
        authority_publication=_published_file(
            role="authority",
            path=f"{installation.projection_root}/authority.json",
            raw=authority.raw,
            inode=51,
        ),
        installation_publication=_published_file(
            role="installation",
            path=f"{installation.projection_root}/installation.json",
            raw=installation.raw,
            inode=52,
        ),
    )
    effect_producers = list(_prestart_effect_producers(inputs))
    effect_producers[4] = alternate_projection
    phase_intents, phase_receipts = _prestart_phase_prefix(
        installation.launch_id,
        tuple(effect_producers),
        inputs["manager_reload"],
    )
    drifted = {
        **inputs,
        "projection": alternate_projection,
        "phase_intents": phase_intents,
        "phase_receipts": phase_receipts,
    }

    with pytest.raises(
        WarehouseW3RootInstallationError,
        match="projection source fact binding differs",
    ):
        WarehouseW3PreStartEvidence.create(**drifted)


def test_prestart_evidence_rejects_manager_boot_live_phase_and_account_drift(
    semantic_inputs: dict[str, object],
) -> None:
    inputs = _prestart_inputs(semantic_inputs)

    unit, reload_receipt, loaded = _manager_bundle(
        inputs["authority"],
        inputs["installation"],
        boot_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    )
    effect_producers = list(_prestart_effect_producers(inputs))
    effect_producers[5] = unit
    effect_producers[6] = reload_receipt
    phase_intents, phase_receipts = _prestart_phase_prefix(
        inputs["installation"].launch_id,
        tuple(effect_producers),
        reload_receipt,
    )
    manager_drift = {
        **inputs,
        "unit_publication": unit,
        "manager_reload": reload_receipt,
        "loaded_manager": loaded,
        "phase_intents": phase_intents,
        "phase_receipts": phase_receipts,
    }
    with pytest.raises(
        WarehouseW3RootInstallationError,
        match="identity, or boot binding differs",
    ):
        WarehouseW3PreStartEvidence.create(**manager_drift)

    changed_rehash = json.loads(inputs["environment_rehash"].raw)
    changed_rehash["phase"] = "completion"
    live_drift = {
        **inputs,
        "environment_rehash": LiveEnvironmentRehashFact.from_bytes(
            _canonical(changed_rehash)
        ),
    }
    with pytest.raises(
        WarehouseW3RootInstallationError,
        match="live preclaim environment binding differs",
    ):
        WarehouseW3PreStartEvidence.create(**live_drift)

    account_drift = {
        **inputs,
        "runtime_account": WarehouseW3RuntimeAccountReceipt.create(
            observed_name="clawd",
            observed_uid=1001,
            observed_gid=1001,
        ),
    }
    with pytest.raises(
        WarehouseW3RootInstallationError,
        match="nonce directory ownership differ",
    ):
        WarehouseW3PreStartEvidence.create(**account_drift)

    root_account = {
        **inputs,
        "runtime_account": WarehouseW3RuntimeAccountReceipt.create(
            observed_name="clawd",
            observed_uid=0,
            observed_gid=0,
        ),
    }
    with pytest.raises(
        WarehouseW3RootInstallationError,
        match="nonce directory ownership differ",
    ):
        WarehouseW3PreStartEvidence.create(**root_account)


def test_prestart_evidence_rejects_forged_exact_class_raw_attribute_split(
    semantic_inputs: dict[str, object],
) -> None:
    inputs = _prestart_inputs(semantic_inputs)
    original = inputs["stores_published"]
    forged = object.__new__(WarehouseW3StoresPublishedReceipt)
    for field in WarehouseW3StoresPublishedReceipt.__dataclass_fields__:
        object.__setattr__(forged, field, getattr(original, field))
    changed = json.loads(original.raw)
    changed["selection_key"] = "f" * 64
    forged_raw = _canonical(changed)
    object.__setattr__(forged, "raw", forged_raw)
    object.__setattr__(
        forged,
        "raw_sha256",
        hashlib.sha256(forged_raw).hexdigest(),
    )
    forged_inputs = {**inputs, "stores_published": forged}

    with pytest.raises(
        WarehouseW3RootInstallationError,
        match="object differs from canonical raw",
    ):
        WarehouseW3PreStartEvidence.create(**forged_inputs)


def test_prestart_evidence_rejects_forged_unit_publication_raw_binding(
    semantic_inputs: dict[str, object],
) -> None:
    inputs = _prestart_inputs(semantic_inputs)
    original = inputs["unit_publication"]
    mutations = (
        ("launch_id", "f" * 64),
        ("authority_sha256", "f" * 64),
        ("installation_sha256", "f" * 64),
        ("configured_pair_sha256", "f" * 64),
        ("template_derivation_sha256", "f" * 64),
        ("run_unit", "forged-run.service"),
        ("close_unit", "forged-close.service"),
        ("run_fragment_path", "/etc/systemd/system/forged-run.service"),
        ("close_fragment_path", "/etc/systemd/system/forged-close.service"),
        ("run_template_sha256", "f" * 64),
        ("close_template_sha256", "f" * 64),
        ("run_template_size_bytes", original.run_template_size_bytes + 1),
        ("close_template_size_bytes", original.close_template_size_bytes + 1),
        ("run_publication_sha256", "f" * 64),
        ("close_publication_sha256", "f" * 64),
    )
    for wire_field, wire_value in mutations:
        forged = object.__new__(UnitPublicationReceipt)
        for field in UnitPublicationReceipt.__dataclass_fields__:
            object.__setattr__(forged, field, getattr(original, field))
        changed = json.loads(original.raw)
        changed[wire_field] = wire_value
        forged_raw = _canonical(changed)
        object.__setattr__(forged, "raw", forged_raw)
        object.__setattr__(
            forged,
            "raw_sha256",
            hashlib.sha256(forged_raw).hexdigest(),
        )
        forged_inputs = {**inputs, "unit_publication": forged}

        with pytest.raises(
            WarehouseW3RootInstallationError,
            match="dependency object differs",
        ):
            WarehouseW3PreStartEvidence.create(**forged_inputs)


def test_prestart_evidence_parser_rejects_extra_or_forbidden_fields(
    semantic_inputs: dict[str, object],
) -> None:
    inputs = _prestart_inputs(semantic_inputs)
    evidence = WarehouseW3PreStartEvidence.create(**inputs)

    for field in ("unknown", "authorization_sha256", "start_issue_sha256"):
        changed = json.loads(evidence.raw)
        changed[field] = "f" * 64
        with pytest.raises(
            WarehouseW3RootInstallationError,
            match="fields differ",
        ):
            WarehouseW3PreStartEvidence.from_bytes(
                _canonical(changed),
                **inputs,
            )
