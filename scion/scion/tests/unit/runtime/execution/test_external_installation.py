from __future__ import annotations

import ast
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
from typing import Mapping

import pytest

import scion.runtime.execution.external_installation as external_installation
from scion.runtime.execution.external_installation import (
    INSTALL_PHASES,
    CanonicalReceiptError,
    DefiniteStartError,
    DirectoryIdentity,
    DirectorySnapshot,
    DurableReceiptDirectory,
    ExternalInstallationError,
    InstalledAcceptance,
    LoadedManagerReceipt,
    ManagerAcceptanceError,
    ManagerIdentity,
    ManagerReloadReceipt,
    MountBindingReceipt,
    MountInfoError,
    NoReplaceReceiptSet,
    PublishedDirectoryReceipt,
    PublishedRegularFileReceipt,
    PublishedTreeReceipt,
    ReceiptDagError,
    RootInstallationState,
    RootPhaseIntentReceipt,
    RootPhaseReceipt,
    SelectionReceipt,
    StartAuthorizationReceipt,
    StartDispatchReceipt,
    StartDispatchState,
    StartIssueReceipt,
    StartPermitError,
    StartPermitOwner,
    SystemdExternalManager,
    UnitPublicationReceipt,
    acquire_loaded_manager_receipt,
    apply_manager_reload,
    apply_root_phase,
    classify_root_installation,
    classify_start_dispatch,
    parse_selected_mountinfo,
    validate_forward_receipt_dag,
    validate_root_transaction,
)
from scion.runtime.execution.launch_authority import (
    AcceptedLaunchAuthority,
    InstallationRecord,
)
from scion.runtime.execution.systemd255 import ConfiguredUnitProperties, UnitRole
from scion.runtime.execution.systemd_acquisition import (
    ConfiguredPairFact,
    ConfiguredPairReadback,
)

LAUNCH = "a" * 64
SELECTION = "b" * 64
CANDIDATE = "c" * 64
INTENT = "d" * 64
AUTHORIZATION = "1" * 64
INSTALLED = "2" * 64
PRESTART_RAW = b'{"schema":"fixture.prestart.v1"}\n'
PRESTART = hashlib.sha256(PRESTART_RAW).hexdigest()
INSTALLATION = "4" * 64
RUN = f"scion-run@{LAUNCH}.service"
CLOSE = f"scion-close@{LAUNCH}.service"
BOOT = "12345678-1234-1234-1234-123456789abc"
VERSION = "255.4-1ubuntu8"
RUN_OBJECT = "/org/freedesktop/systemd1/unit/scion_2drun_40fixture_2eservice"
CLOSE_OBJECT = "/org/freedesktop/systemd1/unit/scion_2dclose_40fixture_2eservice"
RUN_FRAGMENT = "/etc/systemd/system/scion-run@.service"
CLOSE_FRAGMENT = "/etc/systemd/system/scion-close@.service"
RUN_TEMPLATE_RAW = (
    b"[Unit]\n"
    b"CollectMode=inactive\n"
    + f"OnFailure={CLOSE}\n".encode()
    + f"OnSuccess={CLOSE}\n".encode()
    + b"\n[Service]\n"
    + b"Delegate=pids\n"
    + b"DelegateSubgroup=supervisor\n"
    + b"KillMode=control-group\n"
    + b"Restart=no\n"
    + b"TimeoutStopSec=infinity\n"
)
CLOSE_TEMPLATE_RAW = (
    b"[Unit]\n"
    + f"After={RUN}\n".encode()
    + b"CollectMode=inactive\n"
    + b"\n[Service]\n"
    + b"Restart=no\n"
    + b"TimeoutStartSec=infinity\n"
)
PYTHON = "/opt/scion/python"
TOOL = "/opt/scion/tool"
READ_ONLY = ("/opt/scion", "/var/lib/scion/sealed")
READ_WRITE = ("/var/lib/scion/run", "/var/lib/scion/nonce-claims")
RUN_START = f"{PYTHON} {TOOL} run"
RUN_STOP = f"{PYTHON} {TOOL} seal-unit-drained"
CLOSE_START = f"{PYTHON} {TOOL} close"
RUN_DIRECTIVES = {
    "Delegate": "pids",
    "DelegateSubgroup": "supervisor",
    "CollectMode": "inactive",
    "Restart": "no",
    "KillMode": "control-group",
    "TimeoutStopSec": "infinity",
    "OnSuccess": CLOSE,
    "OnFailure": CLOSE,
}
CLOSE_DIRECTIVES = {
    "CollectMode": "inactive",
    "Restart": "no",
    "TimeoutStartSec": "infinity",
    "After": RUN,
}
RUN_WIRING = {
    "Type": "exec",
    "User": "clawd",
    "Group": "clawd",
    "UMask": "0077",
    "ExecStart": RUN_START,
    "ExecStopPost": RUN_STOP,
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
    "ReadOnlyPaths": " ".join(READ_ONLY),
    "ReadWritePaths": " ".join(READ_WRITE),
}
CLOSE_WIRING = {
    "Type": "oneshot",
    "User": "clawd",
    "Group": "clawd",
    "UMask": "0077",
    "ExecStart": CLOSE_START,
    "NoNewPrivileges": "yes",
    "PrivateTmp": "yes",
    "ProtectSystem": "strict",
    "ProtectHome": "read-only",
    "ReadOnlyPaths": " ".join(READ_ONLY),
    "ReadWritePaths": " ".join(READ_WRITE),
}
RUN_CONFIGURED_NAMES = (
    "Id",
    "Type",
    "User",
    "Group",
    "UMask",
    "ExecStart",
    "ExecStopPost",
    "ExitType",
    "SendSIGKILL",
    "OOMPolicy",
    "NoNewPrivileges",
    "PrivateTmp",
    "PrivateMounts",
    "ProtectSystem",
    "ProtectHome",
    "ProtectControlGroups",
    "ProtectProc",
    "ProcSubset",
    "ReadOnlyPaths",
    "ReadWritePaths",
    "Delegate",
    "DelegateControllers",
    "DelegateSubgroup",
    "CollectMode",
    "Restart",
    "KillMode",
    "TimeoutStopUSec",
    "OnSuccess",
    "OnFailure",
)
CLOSE_CONFIGURED_NAMES = (
    "Id",
    "Type",
    "User",
    "Group",
    "UMask",
    "ExecStart",
    "NoNewPrivileges",
    "PrivateTmp",
    "ProtectSystem",
    "ProtectHome",
    "ReadOnlyPaths",
    "ReadWritePaths",
    "CollectMode",
    "Restart",
    "TimeoutStartUSec",
    "After",
)


@pytest.fixture(autouse=True)
def _effective_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(external_installation.os, "geteuid", lambda: 0)


def _canonical(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode()


def _phase_prefix(
    length: int,
    *,
    launch_id: str = LAUNCH,
) -> tuple[tuple[RootPhaseIntentReceipt, ...], tuple[RootPhaseReceipt, ...]]:
    intents: list[RootPhaseIntentReceipt] = []
    receipts: list[RootPhaseReceipt] = []
    for index, phase in enumerate(INSTALL_PHASES[:length]):
        intent = RootPhaseIntentReceipt.create(
            launch_id=launch_id,
            phase=phase,
            predecessor_sha256=(
                () if index == 0 else (receipts[index - 1].raw_sha256,)
            ),
            effect_authority_sha256=hashlib.sha256(
                f"authority:{phase.value}".encode()
            ).hexdigest(),
        )
        receipt = RootPhaseReceipt.create(
            intent=intent,
            effect_sha256=hashlib.sha256(phase.value.encode()).hexdigest(),
        )
        intents.append(intent)
        receipts.append(receipt)
    return tuple(intents), tuple(receipts)


def _structured(command: str) -> tuple[object, ...]:
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


def _run_properties() -> dict[str, object]:
    return {
        "Id": RUN,
        "FragmentPath": RUN_FRAGMENT,
        "DropInPaths": [],
        "LoadState": "loaded",
        "ActiveState": "inactive",
        "SubState": "dead",
        "Job": [0, "/"],
        "InvocationID": [0] * 16,
        "Transient": False,
        "Type": "exec",
        "User": "clawd",
        "Group": "clawd",
        "UMask": 0o077,
        "ExecStart": [_structured(RUN_START)],
        "ExecStopPost": [_structured(RUN_STOP)],
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
        "ReadOnlyPaths": list(READ_ONLY),
        "ReadWritePaths": list(READ_WRITE),
        "Delegate": True,
        "DelegateControllers": ["pids"],
        "DelegateSubgroup": "supervisor",
        "CollectMode": "inactive",
        "Restart": "no",
        "KillMode": "control-group",
        "TimeoutStopUSec": (1 << 64) - 1,
        "OnSuccess": [CLOSE],
        "OnFailure": [CLOSE],
    }


def _close_properties() -> dict[str, object]:
    return {
        "Id": CLOSE,
        "FragmentPath": CLOSE_FRAGMENT,
        "DropInPaths": [],
        "LoadState": "loaded",
        "ActiveState": "inactive",
        "SubState": "dead",
        "Job": [0, "/"],
        "InvocationID": [0] * 16,
        "Transient": False,
        "Type": "oneshot",
        "User": "clawd",
        "Group": "clawd",
        "UMask": 0o077,
        "ExecStart": [_structured(CLOSE_START)],
        "NoNewPrivileges": True,
        "PrivateTmp": True,
        "ProtectSystem": "strict",
        "ProtectHome": "read-only",
        "ReadOnlyPaths": list(READ_ONLY),
        "ReadWritePaths": list(READ_WRITE),
        "CollectMode": "inactive",
        "Restart": "no",
        "TimeoutStartUSec": (1 << 64) - 1,
        "After": [RUN],
    }


def _configured_readback() -> ConfiguredPairReadback:
    run_properties = _run_properties()
    close_properties = _close_properties()
    configured_pair = ConfiguredPairFact.create(
        ConfiguredUnitProperties.from_receipts(
            UnitRole.RUN,
            RUN_DIRECTIVES,
            {
                "Id": RUN,
                "Delegate": "yes",
                "DelegateControllers": "pids",
                "DelegateSubgroup": "supervisor",
                "CollectMode": "inactive",
                "Restart": "no",
                "KillMode": "control-group",
                "TimeoutStopUSec": "infinity",
                "OnSuccess": CLOSE,
                "OnFailure": CLOSE,
            },
            expected_unit=RUN,
            expected_peer=CLOSE,
        ),
        ConfiguredUnitProperties.from_receipts(
            UnitRole.CLOSER,
            CLOSE_DIRECTIVES,
            {
                "Id": CLOSE,
                "CollectMode": "inactive",
                "Restart": "no",
                "TimeoutStartUSec": "infinity",
                "After": RUN,
            },
            expected_unit=CLOSE,
            expected_peer=RUN,
        ),
    )
    return ConfiguredPairReadback.create(
        run_unit=RUN,
        close_unit=CLOSE,
        run_properties={name: run_properties[name] for name in RUN_CONFIGURED_NAMES},
        close_properties={
            name: close_properties[name] for name in CLOSE_CONFIGURED_NAMES
        },
        configured_pair=configured_pair,
        run_wiring=RUN_WIRING,
        close_wiring=CLOSE_WIRING,
    )


def _launch_pair() -> tuple[AcceptedLaunchAuthority, InstallationRecord]:
    manifest = b"manifest\n"
    manifest_sha = hashlib.sha256(manifest).hexdigest()
    source_commit = "0123456789abcdef0123456789abcdef01234567"
    authority = AcceptedLaunchAuthority.from_bytes(
        _canonical(
            {
                "schema": "scion.generic-launch-authority.v1",
                "problem_kind": "warehouse-w3",
                "source_commit": source_commit,
                "source_tree": "89abcdef0123456789abcdef0123456789abcdef",
                "manifest": {
                    "path": "control/manifest.json",
                    "sha256": manifest_sha,
                    "size_bytes": len(manifest),
                },
                "root_basename": "accepted-w3-root",
                "nonce": "3" * 64,
                "nonce_ledger_parent": ("/var/lib/scion/runs/w3/.nonce-ledger/claims"),
                "expected_rows": 172,
                "artifact_names": ["result.json"],
                "scientific_design_sha256": "1" * 64,
                "correction_design_sha256": "2" * 64,
                "native_acceptance_contract_sha256": "3" * 64,
                "native_acceptance_record_sha256": "4" * 64,
                "sealed_store_aggregate_sha256": "5" * 64,
                "environment_receipt_sha256": "6" * 64,
                "run_template_sha256": hashlib.sha256(RUN_TEMPLATE_RAW).hexdigest(),
                "close_template_sha256": hashlib.sha256(CLOSE_TEMPLATE_RAW).hexdigest(),
                "guardian_source_sha256": "7" * 64,
                "thin_tool_source_sha256": "8" * 64,
                "closer_source_sha256": "9" * 64,
                "inputs": [
                    {
                        "logical_path": "control/manifest.json",
                        "sealed_path": "sealed/control/manifest.json",
                        "sha256": manifest_sha,
                        "size_bytes": len(manifest),
                        "provenance": {
                            "kind": "git_blob",
                            "commit": source_commit,
                            "path": "control/manifest.json",
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
    configured_pair = _configured_readback().configured_pair
    installation = InstallationRecord.from_bytes(
        _canonical(
            {
                "schema": "scion.generic-launch-installation.v1",
                "launch_id": LAUNCH,
                "authority_sha256": authority.authority_sha256,
                "authority_path": (
                    f"/var/lib/scion/authorities/w3/"
                    f"{authority.authority_sha256}.json"
                ),
                "problem_kind": authority.problem_kind,
                "manifest_sha256": authority.manifest_sha256,
                "run_root": "/srv/accepted-w3-root",
                "terminal_root": "/srv/accepted-w3-root/control/invocation",
                "nonce": authority.nonce,
                "nonce_ledger_parent": authority.nonce_ledger_parent,
                "sealed_root": "/var/lib/scion/sealed/w3/fixture",
                "sealed_store_aggregate_sha256": (
                    authority.sealed_store_aggregate_sha256
                ),
                "environment_root": "/var/lib/scion/environments/w3/fixture",
                "environment_receipt_sha256": (authority.environment_receipt_sha256),
                "projection_root": f"/var/lib/scion/projections/w3/{LAUNCH}",
                "run_template_sha256": authority.run_template_sha256,
                "close_template_sha256": authority.close_template_sha256,
                "run_unit": RUN,
                "close_unit": CLOSE,
                "configured_pair": configured_pair.to_mapping(),
                "configured_pair_sha256": (configured_pair.configured_pair_sha256),
                "retry": False,
                "resume": False,
                "reuse": False,
            }
        ),
        authority,
    )
    return authority, installation


def _unit_publication() -> UnitPublicationReceipt:
    authority, installation = _launch_pair()
    run_publication, close_publication = _unit_fragment_publications()
    return UnitPublicationReceipt.create(
        authority=authority,
        installation=installation,
        run_template_raw=RUN_TEMPLATE_RAW,
        close_template_raw=CLOSE_TEMPLATE_RAW,
        run_publication=run_publication,
        close_publication=close_publication,
    )


def _unit_fragment_publication(
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
        device=31,
        inode=inode,
        mode=0o444,
        uid=0,
        gid=0,
        nlink=1,
    )


def _unit_fragment_publications() -> tuple[
    PublishedRegularFileReceipt,
    PublishedRegularFileReceipt,
]:
    return (
        _unit_fragment_publication(
            role="run-fragment",
            path=RUN_FRAGMENT,
            raw=RUN_TEMPLATE_RAW,
            inode=43,
        ),
        _unit_fragment_publication(
            role="close-fragment",
            path=CLOSE_FRAGMENT,
            raw=CLOSE_TEMPLATE_RAW,
            inode=44,
        ),
    )


def test_root_phase_receipts_form_one_forward_no_replace_prefix() -> None:
    partial_intents, partial = _phase_prefix(4)
    complete_intents, complete = _phase_prefix(len(INSTALL_PHASES))

    assert classify_root_installation((), ()) is RootInstallationState.ABSENT
    assert (
        classify_root_installation(partial_intents, partial)
        is RootInstallationState.PARTIAL_HOLD
    )
    assert (
        classify_root_installation(complete_intents, complete)
        is RootInstallationState.ACCEPTED
    )
    assert (
        validate_forward_receipt_dag(
            tuple(reversed(complete_intents)),
            tuple(reversed(complete)),
        )
        == complete
    )
    assert (
        RootPhaseIntentReceipt.from_bytes(complete_intents[-1].raw)
        == complete_intents[-1]
    )
    assert RootPhaseReceipt.from_bytes(complete[-1].raw) == complete[-1]

    writer = NoReplaceReceiptSet()
    writer.write_no_replace("INSTALLATION_ACCEPTED", complete[-1].raw)
    with pytest.raises(FileExistsError):
        writer.write_no_replace("INSTALLATION_ACCEPTED", complete[-1].raw)


def test_durable_receipt_directory_is_no_replace_fsynced_and_reopened(
    tmp_path: Path,
) -> None:
    with DurableReceiptDirectory(tmp_path, require_root=False) as writer:
        writer.write_no_replace("FACT.v1.json", b'{"fact":1}\n')
        assert writer.read("FACT.v1.json") == b'{"fact":1}\n'
        with pytest.raises(FileExistsError):
            writer.write_no_replace("FACT.v1.json", b'{"fact":1}\n')

    assert (tmp_path / "FACT.v1.json").stat().st_mode & 0o777 == 0o444
    with pytest.raises(ExternalInstallationError, match="closed"):
        writer.read("FACT.v1.json")


def test_root_phase_owner_persists_intent_before_effect_and_commit_after_reopen() -> (
    None
):
    writer = NoReplaceReceiptSet()
    calls: list[tuple[object, ...]] = []

    def effect() -> None:
        calls.append(("effect", writer.write_order))

    def reopen() -> bytes:
        calls.append(("reopen", writer.write_order))
        return b'{"observed":"stable"}\n'

    intent, receipt = apply_root_phase(
        launch_id=LAUNCH,
        phase=INSTALL_PHASES[0],
        effect_authority_sha256="7" * 64,
        prior_intents=(),
        prior_receipts=(),
        writer=writer,
        apply_effect=effect,
        reopen_effect=reopen,
    )

    assert calls[0][0] == "effect"
    assert calls[0][1] == ("00-root-staging-imported.intent.v1.json",)
    assert calls[1][0] == "reopen"
    assert writer.write_order == (
        "00-root-staging-imported.intent.v1.json",
        "00-root-staging-imported.commit.v2.json",
    )
    assert validate_root_transaction((intent,), (receipt,)) == (
        (intent,),
        (receipt,),
    )


def test_crash_after_root_intent_is_partial_hold_and_forbids_next_effect() -> None:
    writer = NoReplaceReceiptSet()
    with pytest.raises(RuntimeError, match="readback failed"):
        apply_root_phase(
            launch_id=LAUNCH,
            phase=INSTALL_PHASES[0],
            effect_authority_sha256="7" * 64,
            prior_intents=(),
            prior_receipts=(),
            writer=writer,
            apply_effect=lambda: None,
            reopen_effect=lambda: (_ for _ in ()).throw(
                RuntimeError("readback failed")
            ),
        )
    intent = RootPhaseIntentReceipt.from_bytes(
        writer.read("00-root-staging-imported.intent.v1.json")
    )
    assert (
        classify_root_installation((intent,), ()) is RootInstallationState.PARTIAL_HOLD
    )
    with pytest.raises(ReceiptDagError, match="pending root intent"):
        apply_root_phase(
            launch_id=LAUNCH,
            phase=INSTALL_PHASES[1],
            effect_authority_sha256="8" * 64,
            prior_intents=(intent,),
            prior_receipts=(),
            writer=writer,
            apply_effect=lambda: None,
            reopen_effect=lambda: b"unreachable\n",
        )


def test_root_phase_owner_rejects_mixed_launch_before_intent_or_effect() -> None:
    intents, receipts = _phase_prefix(1)
    writer = NoReplaceReceiptSet()
    effects: list[str] = []

    with pytest.raises(ReceiptDagError, match="before external effect"):
        apply_root_phase(
            launch_id="f" * 64,
            phase=INSTALL_PHASES[1],
            effect_authority_sha256="8" * 64,
            prior_intents=intents,
            prior_receipts=receipts,
            writer=writer,
            apply_effect=lambda: effects.append("effect"),
            reopen_effect=lambda: b"unreachable\n",
        )

    assert effects == []
    assert writer.names == ()


def test_root_receipt_gap_or_wrong_predecessor_is_partial_hold() -> None:
    first_intents, first_receipts = _phase_prefix(1)
    wrong_intent = RootPhaseIntentReceipt.create(
        launch_id=LAUNCH,
        phase=INSTALL_PHASES[1],
        predecessor_sha256=("f" * 64,),
        effect_authority_sha256="9" * 64,
    )
    wrong_second = RootPhaseReceipt.create(
        intent=wrong_intent,
        effect_sha256="9" * 64,
    )
    gapped_intent = RootPhaseIntentReceipt.create(
        launch_id=LAUNCH,
        phase=INSTALL_PHASES[2],
        predecessor_sha256=(first_receipts[0].raw_sha256,),
        effect_authority_sha256="8" * 64,
    )
    gapped = RootPhaseReceipt.create(intent=gapped_intent, effect_sha256="8" * 64)

    with pytest.raises(ReceiptDagError):
        validate_forward_receipt_dag(
            (*first_intents, wrong_intent),
            (*first_receipts, wrong_second),
        )
    assert (
        classify_root_installation(
            (*first_intents, wrong_intent),
            (*first_receipts, wrong_second),
        )
        is RootInstallationState.PARTIAL_HOLD
    )
    assert (
        classify_root_installation(
            (*first_intents, gapped_intent),
            (*first_receipts, gapped),
        )
        is RootInstallationState.PARTIAL_HOLD
    )


def test_root_phase_parser_rejects_noncanonical_and_duplicate_fields() -> None:
    _intents, receipts = _phase_prefix(1)
    receipt = receipts[0]
    with pytest.raises(CanonicalReceiptError, match="not canonical"):
        RootPhaseReceipt.from_bytes(receipt.raw.rstrip(b"\n"))

    decoded = json.loads(receipt.raw)
    duplicate = (
        b'{"effect_sha256":"'
        + decoded["effect_sha256"].encode()
        + b'","effect_sha256":"'
        + decoded["effect_sha256"].encode()
        + b'","launch_id":"'
        + LAUNCH.encode()
        + b'","effect_authority_sha256":"'
        + decoded["effect_authority_sha256"].encode()
        + b'","intent_sha256":"'
        + decoded["intent_sha256"].encode()
        + b'","phase":"ROOT_STAGING_IMPORTED",'
        + b'"predecessor_sha256":[],'
        + b'"schema":"scion.external-root-phase-commit.v2"}\n'
    )
    with pytest.raises(CanonicalReceiptError, match="not canonical JSON"):
        RootPhaseReceipt.from_bytes(duplicate)


def _published_tree(
    *,
    identity: DirectorySnapshot | None = None,
    expected_tree_sha256: str = "1" * 64,
    reopened_tree_sha256: str = "1" * 64,
) -> PublishedTreeReceipt:
    return PublishedTreeReceipt.create(
        role="generic-tree",
        path="/var/lib/scion/published/tree",
        source_receipt_sha256="2" * 64,
        expected_tree_sha256=expected_tree_sha256,
        reopened_tree_sha256=reopened_tree_sha256,
        identity=identity
        or DirectorySnapshot(
            device=31,
            inode=41,
            mode=0o555,
            uid=0,
            gid=0,
            nlink=2,
        ),
    )


def _published_file() -> PublishedRegularFileReceipt:
    return PublishedRegularFileReceipt.create(
        role="generic-file",
        path="/var/lib/scion/published/authority.json",
        content_sha256="3" * 64,
        size_bytes=127,
        device=31,
        inode=42,
        mode=0o444,
        uid=0,
        gid=0,
        nlink=1,
    )


def _published_directory() -> PublishedDirectoryReceipt:
    return PublishedDirectoryReceipt.create(
        role="generic-directory",
        path="/var/lib/scion/published/nonce-claims",
        device=31,
        inode=43,
        mode=0o700,
        uid=1001,
        gid=1002,
        nlink=2,
        expected_mode=0o700,
        expected_uid=1001,
        expected_gid=1002,
    )


def test_published_leaf_receipts_are_closed_canonical_records() -> None:
    tree = _published_tree()
    regular = _published_file()
    directory = _published_directory()

    assert PublishedTreeReceipt.from_bytes(tree.raw) == tree
    assert PublishedRegularFileReceipt.from_bytes(regular.raw) == regular
    assert PublishedDirectoryReceipt.from_bytes(directory.raw) == directory
    assert tree.expected_tree_sha256 == tree.reopened_tree_sha256
    assert tree.identity.mode == 0o555
    assert regular.content_sha256 == "3" * 64
    assert regular.size_bytes == 127
    assert directory.uid == directory.expected_uid == 1001
    assert directory.gid == directory.expected_gid == 1002
    assert directory.mode == directory.expected_mode == 0o700
    for receipt in (tree, regular, directory):
        assert receipt.raw_sha256 == hashlib.sha256(receipt.raw).hexdigest()
    with pytest.raises(TypeError, match="parsed from exact bytes"):
        PublishedTreeReceipt()
    with pytest.raises(TypeError, match="parsed from exact bytes"):
        PublishedRegularFileReceipt()
    with pytest.raises(TypeError, match="parsed from exact bytes"):
        PublishedDirectoryReceipt()


@pytest.mark.parametrize(
    ("receipt", "parser"),
    (
        (_published_tree(), PublishedTreeReceipt.from_bytes),
        (_published_file(), PublishedRegularFileReceipt.from_bytes),
        (_published_directory(), PublishedDirectoryReceipt.from_bytes),
    ),
)
def test_published_leaf_receipts_reject_extra_fields(
    receipt: object,
    parser: object,
) -> None:
    changed = json.loads(receipt.raw)  # type: ignore[attr-defined]
    changed["extra"] = False

    with pytest.raises(CanonicalReceiptError, match="fields differ"):
        parser(_canonical(changed))  # type: ignore[operator]


@pytest.mark.parametrize("path", ("relative/path", "/a/../b", "//a/b", "/"))
def test_published_leaf_receipts_reject_noncanonical_paths(path: str) -> None:
    for receipt, parser in (
        (_published_tree(), PublishedTreeReceipt.from_bytes),
        (_published_file(), PublishedRegularFileReceipt.from_bytes),
        (_published_directory(), PublishedDirectoryReceipt.from_bytes),
    ):
        changed = json.loads(receipt.raw)
        changed["path"] = path
        with pytest.raises(ExternalInstallationError, match="canonical absolute path"):
            parser(_canonical(changed))


@pytest.mark.parametrize(
    ("receipt", "field_path"),
    (
        (_published_tree(), ("identity", "inode")),
        (_published_file(), ("size_bytes",)),
        (_published_directory(), ("expected_uid",)),
    ),
)
def test_published_leaf_receipts_reject_boolean_integer_aliases(
    receipt: object,
    field_path: tuple[str, ...],
) -> None:
    changed = json.loads(receipt.raw)  # type: ignore[attr-defined]
    target = changed
    for field in field_path[:-1]:
        target = target[field]
    target[field_path[-1]] = True
    parser = {
        PublishedTreeReceipt: PublishedTreeReceipt.from_bytes,
        PublishedRegularFileReceipt: PublishedRegularFileReceipt.from_bytes,
        PublishedDirectoryReceipt: PublishedDirectoryReceipt.from_bytes,
    }[type(receipt)]

    with pytest.raises(ExternalInstallationError, match="not an integer"):
        parser(_canonical(changed))


def test_published_tree_rejects_reopen_drift_and_nonroot_identity() -> None:
    with pytest.raises(ExternalInstallationError, match="digest drifted"):
        _published_tree(reopened_tree_sha256="4" * 64)

    for identity in (
        DirectorySnapshot(
            device=31,
            inode=41,
            mode=0o755,
            uid=0,
            gid=0,
            nlink=2,
        ),
        DirectorySnapshot(
            device=31,
            inode=41,
            mode=0o555,
            uid=1001,
            gid=0,
            nlink=2,
        ),
        DirectorySnapshot(
            device=31,
            inode=41,
            mode=0o555,
            uid=0,
            gid=1002,
            nlink=2,
        ),
    ):
        with pytest.raises(
            ExternalInstallationError,
            match="root-owned mode 0555",
        ):
            _published_tree(identity=identity)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("mode", 0o644),
        ("uid", 1001),
        ("gid", 1002),
        ("nlink", 2),
    ),
)
def test_published_regular_file_rejects_identity_drift(
    field: str,
    value: int,
) -> None:
    changed = json.loads(_published_file().raw)
    changed[field] = value

    with pytest.raises(ExternalInstallationError, match="root-owned mode 0444"):
        PublishedRegularFileReceipt.from_bytes(_canonical(changed))


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("mode", 0o750),
        ("uid", 1003),
        ("gid", 1004),
    ),
)
def test_published_directory_rejects_expected_identity_drift(
    field: str,
    value: int,
) -> None:
    changed = json.loads(_published_directory().raw)
    changed[field] = value

    with pytest.raises(ExternalInstallationError, match="expected ownership"):
        PublishedDirectoryReceipt.from_bytes(_canonical(changed))


def test_selection_and_installed_acceptance_are_closed_canonical_records() -> None:
    intents, phases = _phase_prefix(len(INSTALL_PHASES) - 1)
    source_candidate = DirectorySnapshot(
        device=1,
        inode=2,
        mode=0o555,
        uid=1000,
        gid=1000,
        nlink=2,
    )
    source_selection = DirectorySnapshot(
        device=1,
        inode=3,
        mode=0o555,
        uid=1000,
        gid=1000,
        nlink=2,
    )
    selection = SelectionReceipt.create(
        selection_key=SELECTION,
        launch_id=LAUNCH,
        nonce="8" * 64,
        authority_sha256="9" * 64,
        candidate_sha256=CANDIDATE,
        preparation_intent_sha256=INTENT,
        preparation_commit_sha256="a" * 64,
        import_receipt_sha256="b" * 64,
        imported_staging_aggregate_sha256="c" * 64,
        source_candidate_identity=source_candidate,
        source_selection_identity=source_selection,
    )
    accepted = InstalledAcceptance.create(
        launch_id=LAUNCH,
        authority_sha256="4" * 64,
        installation_sha256="5" * 64,
        phase_intents=intents,
        phase_receipts=phases,
        problem_state_schema="scion.test-problem-state.v1",
        problem_state_sha256=phases[-1].effect_sha256,
    )

    assert SelectionReceipt.from_bytes(selection.raw) == selection
    assert selection.source_candidate_identity == source_candidate
    assert InstalledAcceptance.from_bytes(accepted.raw) == accepted
    accepted_value = json.loads(accepted.raw)
    assert accepted_value["schema"] == "scion.external-installed-acceptance.v4"
    assert accepted_value["formal_jobs_started"] == 0
    assert accepted.phase_effect_sha256 == tuple(
        (receipt.phase.value, receipt.effect_sha256) for receipt in phases
    )
    assert accepted_value["phase_effect_sha256"] == dict(accepted.phase_effect_sha256)
    assert accepted.problem_state_schema == "scion.test-problem-state.v1"
    assert accepted.problem_state_sha256 == phases[-1].effect_sha256
    with pytest.raises(TypeError, match="parsed from exact bytes"):
        SelectionReceipt()
    with pytest.raises(TypeError, match="parsed from exact bytes"):
        InstalledAcceptance()

    drift = json.loads(accepted.raw)
    drift["formal_jobs_started"] = 1
    with pytest.raises(CanonicalReceiptError, match="state differs"):
        InstalledAcceptance.from_bytes(_canonical(drift))


def test_installed_acceptance_v4_rejects_v3_and_field_inventory_drift() -> None:
    intents, receipts = _phase_prefix(len(INSTALL_PHASES) - 1)
    accepted = InstalledAcceptance.create(
        launch_id=LAUNCH,
        authority_sha256="4" * 64,
        installation_sha256="5" * 64,
        phase_intents=intents,
        phase_receipts=receipts,
        problem_state_schema="scion.test-problem-state.v1",
        problem_state_sha256=receipts[-1].effect_sha256,
    )
    value = json.loads(accepted.raw)

    legacy_schema = dict(value)
    legacy_schema["schema"] = "scion.external-installed-acceptance.v3"
    with pytest.raises(CanonicalReceiptError, match="state differs"):
        InstalledAcceptance.from_bytes(_canonical(legacy_schema))

    old_subordinate = dict(value)
    old_subordinate.pop("phase_effect_sha256")
    old_subordinate.pop("problem_state_schema")
    old_subordinate.pop("problem_state_sha256")
    old_subordinate["subordinate_receipt_sha256"] = {
        "root_selection": "1" * 64,
    }
    with pytest.raises(CanonicalReceiptError, match="fields differ"):
        InstalledAcceptance.from_bytes(_canonical(old_subordinate))

    extra = dict(value)
    extra["unexpected"] = "6" * 64
    with pytest.raises(CanonicalReceiptError, match="fields differ"):
        InstalledAcceptance.from_bytes(_canonical(extra))

    missing = dict(value)
    missing.pop("problem_state_schema")
    with pytest.raises(CanonicalReceiptError, match="fields differ"):
        InstalledAcceptance.from_bytes(_canonical(missing))

    for mutate in ("missing", "extra"):
        effect_key_drift = json.loads(accepted.raw)
        effects = effect_key_drift["phase_effect_sha256"]
        if mutate == "missing":
            effects.pop(INSTALL_PHASES[0].value)
        else:
            effects[INSTALL_PHASES[-1].value] = "7" * 64
        with pytest.raises(
            CanonicalReceiptError,
            match="phase effects fields differ",
        ):
            InstalledAcceptance.from_bytes(_canonical(effect_key_drift))


def test_installed_acceptance_v4_rejects_prefix_and_problem_state_drift() -> None:
    intents, receipts = _phase_prefix(len(INSTALL_PHASES) - 1)
    with pytest.raises(
        ExternalInstallationError,
        match="exact pre-acceptance phase DAG",
    ):
        InstalledAcceptance.create(
            launch_id=LAUNCH,
            authority_sha256="4" * 64,
            installation_sha256="5" * 64,
            phase_intents=intents[:-1],
            phase_receipts=receipts[:-1],
            problem_state_schema="scion.test-problem-state.v1",
            problem_state_sha256=receipts[-2].effect_sha256,
        )

    other_intents, other_receipts = _phase_prefix(
        len(INSTALL_PHASES) - 1,
        launch_id="f" * 64,
    )
    with pytest.raises(
        ExternalInstallationError,
        match="exact pre-acceptance phase DAG",
    ):
        InstalledAcceptance.create(
            launch_id=LAUNCH,
            authority_sha256="4" * 64,
            installation_sha256="5" * 64,
            phase_intents=other_intents,
            phase_receipts=other_receipts,
            problem_state_schema="scion.test-problem-state.v1",
            problem_state_sha256=other_receipts[-1].effect_sha256,
        )

    with pytest.raises(ExternalInstallationError, match="problem state differs"):
        InstalledAcceptance.create(
            launch_id=LAUNCH,
            authority_sha256="4" * 64,
            installation_sha256="5" * 64,
            phase_intents=intents,
            phase_receipts=receipts,
            problem_state_schema="scion.test-problem-state.v1",
            problem_state_sha256="0" * 64,
        )
    with pytest.raises(ExternalInstallationError, match="exceeds 256 bytes"):
        InstalledAcceptance.create(
            launch_id=LAUNCH,
            authority_sha256="4" * 64,
            installation_sha256="5" * 64,
            phase_intents=intents,
            phase_receipts=receipts,
            problem_state_schema="s" * 257,
            problem_state_sha256=receipts[-1].effect_sha256,
        )


def test_installed_acceptance_v4_rejects_stored_effect_swap_or_mismatch() -> None:
    prefix_intents, prefix_receipts = _phase_prefix(len(INSTALL_PHASES) - 1)
    accepted = InstalledAcceptance.create(
        launch_id=LAUNCH,
        authority_sha256="4" * 64,
        installation_sha256="5" * 64,
        phase_intents=prefix_intents,
        phase_receipts=prefix_receipts,
        problem_state_schema="scion.test-problem-state.v1",
        problem_state_sha256=prefix_receipts[-1].effect_sha256,
    )
    final_intent = RootPhaseIntentReceipt.create(
        launch_id=LAUNCH,
        phase=INSTALL_PHASES[-1],
        predecessor_sha256=(prefix_receipts[-1].raw_sha256,),
        effect_authority_sha256=accepted.raw_sha256,
    )
    final_receipt = RootPhaseReceipt.create(
        intent=final_intent,
        effect_sha256=accepted.raw_sha256,
    )
    full_intents = (*prefix_intents, final_intent)
    full_receipts = (*prefix_receipts, final_receipt)

    swapped = json.loads(accepted.raw)
    effects = swapped["phase_effect_sha256"]
    first = INSTALL_PHASES[0].value
    second = INSTALL_PHASES[1].value
    effects[first], effects[second] = effects[second], effects[first]
    swapped_acceptance = InstalledAcceptance.from_bytes(_canonical(swapped))
    with pytest.raises(ReceiptDagError, match="acceptance phase DAG differs"):
        swapped_acceptance.verify_phase_receipts(full_intents, full_receipts)

    mismatched = json.loads(accepted.raw)
    mismatched["phase_effect_sha256"][first] = "f" * 64
    mismatched_acceptance = InstalledAcceptance.from_bytes(_canonical(mismatched))
    with pytest.raises(ReceiptDagError, match="acceptance phase DAG differs"):
        mismatched_acceptance.verify_phase_receipts(full_intents, full_receipts)

    wrong_problem_state = json.loads(accepted.raw)
    wrong_problem_state["problem_state_sha256"] = "e" * 64
    with pytest.raises(CanonicalReceiptError, match="problem state differs"):
        InstalledAcceptance.from_bytes(_canonical(wrong_problem_state))


def test_installation_acceptance_closes_without_a_final_phase_hash_cycle() -> None:
    prefix_intents, prefix_receipts = _phase_prefix(len(INSTALL_PHASES) - 1)
    accepted = InstalledAcceptance.create(
        launch_id=LAUNCH,
        authority_sha256="4" * 64,
        installation_sha256="5" * 64,
        phase_intents=prefix_intents,
        phase_receipts=prefix_receipts,
        problem_state_schema="scion.test-problem-state.v1",
        problem_state_sha256=prefix_receipts[-1].effect_sha256,
    )
    writer = NoReplaceReceiptSet()

    def publish_acceptance() -> None:
        writer.write_no_replace("INSTALLATION_ACCEPTED.v4.json", accepted.raw)

    final_intent, final_receipt = apply_root_phase(
        launch_id=LAUNCH,
        phase=INSTALL_PHASES[-1],
        effect_authority_sha256=accepted.raw_sha256,
        prior_intents=prefix_intents,
        prior_receipts=prefix_receipts,
        writer=writer,
        apply_effect=publish_acceptance,
        reopen_effect=lambda: writer.read("INSTALLATION_ACCEPTED.v4.json"),
    )
    full_intents = (*prefix_intents, final_intent)
    full_receipts = (*prefix_receipts, final_receipt)

    assert writer.write_order == (
        "08-installation-accepted.intent.v1.json",
        "INSTALLATION_ACCEPTED.v4.json",
        "08-installation-accepted.commit.v2.json",
    )
    assert final_intent.effect_authority_sha256 == accepted.raw_sha256
    assert final_receipt.effect_sha256 == accepted.raw_sha256
    assert accepted.verify_phase_receipts(full_intents, full_receipts) == (
        full_receipts
    )
    with pytest.raises(ReceiptDagError, match="acceptance phase DAG differs"):
        accepted.verify_phase_receipts(prefix_intents, prefix_receipts)

    wrong_authority_intent = RootPhaseIntentReceipt.create(
        launch_id=LAUNCH,
        phase=INSTALL_PHASES[-1],
        predecessor_sha256=(prefix_receipts[-1].raw_sha256,),
        effect_authority_sha256="a" * 64,
    )
    wrong_authority_receipt = RootPhaseReceipt.create(
        intent=wrong_authority_intent,
        effect_sha256=accepted.raw_sha256,
    )
    with pytest.raises(ReceiptDagError, match="acceptance phase DAG differs"):
        accepted.verify_phase_receipts(
            (*prefix_intents, wrong_authority_intent),
            (*prefix_receipts, wrong_authority_receipt),
        )

    wrong_effect_receipt = RootPhaseReceipt.create(
        intent=final_intent,
        effect_sha256="b" * 64,
    )
    with pytest.raises(ReceiptDagError, match="acceptance phase DAG differs"):
        accepted.verify_phase_receipts(
            full_intents,
            (*prefix_receipts, wrong_effect_receipt),
        )

    wrong_commit_value = json.loads(final_receipt.raw)
    wrong_commit_value["effect_authority_sha256"] = "c" * 64
    wrong_authority_commit = RootPhaseReceipt.from_bytes(_canonical(wrong_commit_value))
    with pytest.raises(ReceiptDagError, match="does not bind its intent"):
        accepted.verify_phase_receipts(
            full_intents,
            (*prefix_receipts, wrong_authority_commit),
        )


def test_mountinfo_selected_row_has_canonical_digest_and_decodes_paths() -> None:
    raw = (
        b"20 1 8:1 / / rw,relatime shared:1 - ext4 /dev/sda1 rw,errors=remount-ro\n"
        b"37 20 8:1 /store /projection/my\\040sealed ro,nosuid "
        b"- ext4 /dev/sda1 rw,errors=remount-ro\n"
    )
    row = parse_selected_mountinfo(raw, mount_point="/projection/my sealed")

    assert row.mount_id == 37
    assert row.mount_point == "/projection/my sealed"
    assert row.root == "/store"
    assert row.optional_fields == ()
    assert row.canonical_sha256 == hashlib.sha256(row.canonical).hexdigest()
    assert json.loads(row.canonical)["super_options"] == ["rw", "errors=remount-ro"]


def test_mount_binding_requires_private_distinct_identity_and_exact_ro_rw() -> None:
    device = os.makedev(8, 1)
    identity = DirectoryIdentity(device=device, inode=4242)
    ro_row = parse_selected_mountinfo(
        b"37 20 8:1 /store /projection/sealed ro,nosuid "
        b"- ext4 /dev/sda1 rw,errors=remount-ro\n",
        mount_point="/projection/sealed",
    )
    receipt = MountBindingReceipt.create(
        row=ro_row,
        source_identity=identity,
        destination_identity=identity,
        source_mount_id=12,
        read_only=True,
        expected_filesystem_type="ext4",
        expected_mount_root="/store",
    )
    assert receipt.read_only
    assert receipt.destination_mount_id == ro_row.mount_id
    assert receipt.selected_row == ro_row
    assert receipt.selected_row_sha256 == ro_row.canonical_sha256
    assert MountBindingReceipt.from_bytes(receipt.raw) == receipt

    tampered = json.loads(receipt.raw)
    tampered["selected_row"]["mount_id"] = 38
    with pytest.raises(MountInfoError, match="selected row differs"):
        MountBindingReceipt.from_bytes(_canonical(tampered))

    rw_row = parse_selected_mountinfo(
        b"38 20 8:1 /run /projection/run rw,nosuid "
        b"- ext4 /dev/sda1 rw,errors=remount-ro\n",
        mount_point="/projection/run",
    )
    assert not MountBindingReceipt.create(
        row=rw_row,
        source_identity=identity,
        destination_identity=identity,
        source_mount_id=12,
        read_only=False,
        expected_filesystem_type="ext4",
        expected_mount_root="/run",
    ).read_only

    shared = parse_selected_mountinfo(
        b"39 20 8:1 /store /projection/shared ro,nosuid shared:55 "
        b"- ext4 /dev/sda1 rw\n",
        mount_point="/projection/shared",
    )
    with pytest.raises(MountInfoError, match="not private"):
        MountBindingReceipt.create(
            row=shared,
            source_identity=identity,
            destination_identity=identity,
            source_mount_id=12,
            read_only=True,
            expected_filesystem_type="ext4",
            expected_mount_root="/store",
        )
    with pytest.raises(MountInfoError, match="retain source identity"):
        MountBindingReceipt.create(
            row=ro_row,
            source_identity=identity,
            destination_identity=DirectoryIdentity(device=device, inode=99),
            source_mount_id=12,
            read_only=True,
            expected_filesystem_type="ext4",
            expected_mount_root="/store",
        )
    with pytest.raises(MountInfoError, match="not read-write"):
        MountBindingReceipt.create(
            row=ro_row,
            source_identity=identity,
            destination_identity=identity,
            source_mount_id=12,
            read_only=False,
            expected_filesystem_type="ext4",
            expected_mount_root="/store",
        )
    with pytest.raises(MountInfoError, match="filesystem or root differs"):
        MountBindingReceipt.create(
            row=ro_row,
            source_identity=identity,
            destination_identity=identity,
            source_mount_id=12,
            read_only=True,
            expected_filesystem_type="xfs",
            expected_mount_root="/store",
        )


def test_mountinfo_rejects_duplicate_selection_and_bad_escape() -> None:
    row = b"37 20 8:1 / /projection/run rw - ext4 /dev/sda1 rw\n"
    with pytest.raises(MountInfoError, match="exactly one"):
        parse_selected_mountinfo(row + row, mount_point="/projection/run")
    with pytest.raises(MountInfoError, match="unsupported escape"):
        parse_selected_mountinfo(
            b"37 20 8:1 / /projection/bad\\141 rw - ext4 /dev/sda1 rw\n",
            mount_point="/projection/bada",
        )


class _Manager:
    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []
        self.owner = ":1.42"
        self.boot = BOOT
        self.version = VERSION
        self.values = {
            RUN: _run_properties(),
            CLOSE: _close_properties(),
        }
        self.object_paths = {
            RUN: RUN_OBJECT,
            CLOSE: CLOSE_OBJECT,
        }
        self.drift_after_run = False

    def reload(self) -> None:
        self.calls.append(("reload",))

    def get_unique_owner(self) -> str:
        self.calls.append(("owner", self.owner))
        return self.owner

    def get_boot_id(self) -> str:
        self.calls.append(("boot", self.boot))
        return self.boot

    def get_version(self) -> str:
        self.calls.append(("version", self.version))
        return self.version

    def ref_unit(self, unit: str) -> None:
        self.calls.append(("ref", unit))

    def unref_unit(self, unit: str) -> None:
        self.calls.append(("unref", unit))

    def load_unit(self, unit: str) -> str:
        self.calls.append(("load", unit))
        return self.object_paths[unit]

    def get_unit(self, unit: str) -> str:
        self.calls.append(("get", unit))
        return self.object_paths[unit]

    def read_properties(
        self,
        unit: str,
        names: tuple[str, ...],
    ) -> Mapping[str, object]:
        self.calls.append(("read", unit, names))
        result = {
            name: self.values[unit][name] for name in names if name in self.values[unit]
        }
        if unit == RUN and self.drift_after_run:
            self.owner = ":1.99"
        return result


def _manager_reload_receipt(
    *,
    owner: str = ":1.42",
    boot: str = BOOT,
    version: str = VERSION,
) -> ManagerReloadReceipt:
    return ManagerReloadReceipt.create(
        manager_identity=ManagerIdentity(
            unique_owner=owner,
            boot_id=boot,
            version=version,
        ),
        configured_readback=_configured_readback(),
        unit_publication=_unit_publication(),
    )


def test_manager_reload_is_separate_and_reacquires_only_manager_facts() -> None:
    manager = _Manager()
    persisted: list[bytes] = []

    receipt = apply_manager_reload(
        manager,
        configured_readback=_configured_readback(),
        unit_publication=_unit_publication(),
        persist_and_reopen=lambda raw: persisted.append(raw) or bytes(raw),
    )

    assert persisted == [receipt.raw]
    assert receipt.manager_identity == ManagerIdentity(
        unique_owner=":1.42",
        boot_id=BOOT,
        version=VERSION,
    )
    assert receipt.unit_publication_sha256 == _unit_publication().raw_sha256
    assert receipt.configured_pair_readback_sha256 == _configured_readback().raw_sha256
    assert (
        receipt.configured_pair_sha256
        == _configured_readback().configured_pair.configured_pair_sha256
    )
    assert [call[0] for call in manager.calls] == [
        "owner",
        "boot",
        "version",
        "reload",
        "owner",
        "boot",
        "version",
        "owner",
        "boot",
        "version",
    ]
    assert (
        ManagerReloadReceipt.from_bytes(
            receipt.raw,
            configured_readback=_configured_readback(),
            unit_publication=_unit_publication(),
        )
        == receipt
    )


def test_manager_reload_rejects_identity_drift_without_loaded_acquisition() -> None:
    manager = _Manager()

    def drift_after_reload() -> None:
        manager.calls.append(("reload",))
        manager.owner = ":1.99"

    manager.reload = drift_after_reload  # type: ignore[method-assign]
    with pytest.raises(ManagerAcceptanceError, match="identity changed across reload"):
        apply_manager_reload(
            manager,
            configured_readback=_configured_readback(),
            unit_publication=_unit_publication(),
            persist_and_reopen=lambda raw: raw,
        )

    assert [call[0] for call in manager.calls] == [
        "owner",
        "boot",
        "version",
        "reload",
        "owner",
        "boot",
        "version",
    ]


def test_narrow_manager_acquisition_pins_reopens_and_unrefs_without_reload() -> None:
    manager = _Manager()
    persisted: list[bytes] = []

    def persist(raw: bytes) -> bytes:
        persisted.append(raw)
        return bytes(raw)

    receipt = acquire_loaded_manager_receipt(
        manager,
        configured_readback=_configured_readback(),
        unit_publication=_unit_publication(),
        manager_reload=_manager_reload_receipt(),
        persist_and_reopen=persist,
    )

    assert persisted == [receipt.raw]
    assert receipt.manager_identity.unique_owner == ":1.42"
    assert receipt.manager_identity.boot_id == BOOT
    assert receipt.manager_identity.version == VERSION
    assert receipt.run_object_path == RUN_OBJECT
    assert receipt.close_object_path == CLOSE_OBJECT
    assert dict(receipt.run_properties)["InvocationID"] == "0" * 32
    assert receipt.unit_publication_sha256 == _unit_publication().raw_sha256
    assert receipt.configured_pair_readback_sha256 == _configured_readback().raw_sha256
    assert (
        receipt.configured_pair_sha256
        == _configured_readback().configured_pair.configured_pair_sha256
    )
    assert receipt.manager_reload_sha256 == _manager_reload_receipt().raw_sha256
    assert [call[0] for call in manager.calls] == [
        "owner",
        "boot",
        "version",
        "ref",
        "ref",
        "load",
        "get",
        "load",
        "get",
        "owner",
        "boot",
        "version",
        "read",
        "owner",
        "boot",
        "version",
        "read",
        "owner",
        "boot",
        "version",
        "owner",
        "boot",
        "version",
        "unref",
        "unref",
    ]
    assert manager.calls[3:9] == [
        ("ref", RUN),
        ("ref", CLOSE),
        ("load", RUN),
        ("get", RUN),
        ("load", CLOSE),
        ("get", CLOSE),
    ]
    assert ("ref", RUN) in manager.calls
    assert ("ref", CLOSE) in manager.calls
    assert manager.calls[-2:] == [("unref", CLOSE), ("unref", RUN)]
    assert (
        LoadedManagerReceipt.from_bytes(
            receipt.raw,
            configured_readback=_configured_readback(),
            unit_publication=_unit_publication(),
            manager_reload=_manager_reload_receipt(),
        )
        == receipt
    )


def test_loaded_acquisition_rejects_another_reload_identity_before_ref() -> None:
    manager = _Manager()

    with pytest.raises(ManagerAcceptanceError, match="identity changed after reload"):
        acquire_loaded_manager_receipt(
            manager,
            configured_readback=_configured_readback(),
            unit_publication=_unit_publication(),
            manager_reload=_manager_reload_receipt(owner=":1.99"),
            persist_and_reopen=lambda raw: raw,
        )

    assert [call[0] for call in manager.calls] == ["owner", "boot", "version"]


def test_unit_publication_binds_installation_paths_and_reopened_template_bytes() -> (
    None
):
    authority, installation = _launch_pair()
    run_publication, close_publication = _unit_fragment_publications()
    receipt = _unit_publication()

    assert receipt.run_fragment_path == RUN_FRAGMENT
    assert receipt.close_fragment_path == CLOSE_FRAGMENT
    assert receipt.configured_pair_sha256 == installation.configured_pair_sha256
    assert receipt.run_publication_sha256 == run_publication.raw_sha256
    assert receipt.close_publication_sha256 == close_publication.raw_sha256
    assert json.loads(receipt.raw)["schema"] == "scion.unit-publication-acceptance.v3"
    assert (
        UnitPublicationReceipt.from_bytes(
            receipt.raw,
            authority=authority,
            installation=installation,
            run_template_raw=RUN_TEMPLATE_RAW,
            close_template_raw=CLOSE_TEMPLATE_RAW,
            run_publication=run_publication,
            close_publication=close_publication,
        )
        == receipt
    )

    with pytest.raises(
        ManagerAcceptanceError,
        match="run-fragment unit fragment publication authority",
    ):
        UnitPublicationReceipt.create(
            authority=authority,
            installation=installation,
            run_template_raw=RUN_TEMPLATE_RAW,
            close_template_raw=CLOSE_TEMPLATE_RAW,
            run_publication=_unit_fragment_publication(
                role="run-fragment",
                path=RUN_FRAGMENT,
                raw=RUN_TEMPLATE_RAW + b"# drift\n",
                inode=45,
            ),
            close_publication=close_publication,
        )

    changed = json.loads(receipt.raw)
    changed["run_fragment_path"] = "/tmp/caller-selected.service"
    with pytest.raises(ManagerAcceptanceError, match="authority differs"):
        UnitPublicationReceipt.from_bytes(
            _canonical(changed),
            authority=authority,
            installation=installation,
            run_template_raw=RUN_TEMPLATE_RAW,
            close_template_raw=CLOSE_TEMPLATE_RAW,
            run_publication=run_publication,
            close_publication=close_publication,
        )


@pytest.mark.parametrize(
    ("role", "path", "raw"),
    (
        ("alternate-run-fragment", RUN_FRAGMENT, RUN_TEMPLATE_RAW),
        ("run-fragment", "/etc/systemd/system/alternate@.service", RUN_TEMPLATE_RAW),
        ("run-fragment", RUN_FRAGMENT, RUN_TEMPLATE_RAW + b"# drift\n"),
    ),
)
def test_unit_publication_rejects_unbound_regular_publication(
    role: str,
    path: str,
    raw: bytes,
) -> None:
    authority, installation = _launch_pair()
    _, close_publication = _unit_fragment_publications()
    run_publication = _unit_fragment_publication(
        role=role,
        path=path,
        raw=raw,
        inode=45,
    )

    with pytest.raises(
        ManagerAcceptanceError,
        match="run-fragment unit fragment publication authority",
    ):
        UnitPublicationReceipt.create(
            authority=authority,
            installation=installation,
            run_template_raw=RUN_TEMPLATE_RAW,
            close_template_raw=CLOSE_TEMPLATE_RAW,
            run_publication=run_publication,
            close_publication=close_publication,
        )


def test_unit_publication_rejects_same_inode_for_distinct_fragments() -> None:
    authority, installation = _launch_pair()
    run_publication, _ = _unit_fragment_publications()
    close_publication = _unit_fragment_publication(
        role="close-fragment",
        path=CLOSE_FRAGMENT,
        raw=CLOSE_TEMPLATE_RAW,
        inode=run_publication.inode,
    )

    with pytest.raises(
        ManagerAcceptanceError,
        match="fragment publications are not distinct",
    ):
        UnitPublicationReceipt.create(
            authority=authority,
            installation=installation,
            run_template_raw=RUN_TEMPLATE_RAW,
            close_template_raw=CLOSE_TEMPLATE_RAW,
            run_publication=run_publication,
            close_publication=close_publication,
        )


def test_unit_publication_rejects_publication_object_raw_split_and_digest_drift() -> (
    None
):
    authority, installation = _launch_pair()
    run_publication, close_publication = _unit_fragment_publications()
    forged = object.__new__(PublishedRegularFileReceipt)
    for field in PublishedRegularFileReceipt.__dataclass_fields__:
        object.__setattr__(forged, field, getattr(run_publication, field))
    object.__setattr__(forged, "path", "/etc/systemd/system/forged@.service")

    with pytest.raises(
        ManagerAcceptanceError,
        match="run-fragment unit fragment publication authority",
    ):
        UnitPublicationReceipt.create(
            authority=authority,
            installation=installation,
            run_template_raw=RUN_TEMPLATE_RAW,
            close_template_raw=CLOSE_TEMPLATE_RAW,
            run_publication=forged,
            close_publication=close_publication,
        )

    receipt = _unit_publication()
    changed = json.loads(receipt.raw)
    changed["run_publication_sha256"] = "0" * 64
    with pytest.raises(ManagerAcceptanceError, match="authority differs"):
        UnitPublicationReceipt.from_bytes(
            _canonical(changed),
            authority=authority,
            installation=installation,
            run_template_raw=RUN_TEMPLATE_RAW,
            close_template_raw=CLOSE_TEMPLATE_RAW,
            run_publication=run_publication,
            close_publication=close_publication,
        )


def test_installation_rejects_units_from_another_launch_instance() -> None:
    authority, installation = _launch_pair()
    changed = json.loads(installation.raw)
    changed["run_unit"] = f"scion-run@{'b' * 64}.service"
    changed["close_unit"] = f"scion-close@{'b' * 64}.service"

    with pytest.raises(
        Exception,
        match="configured launch instances",
    ):
        InstallationRecord.from_bytes(_canonical(changed), authority)


def test_unit_publication_rederives_pair_from_exact_templates() -> None:
    authority, installation = _launch_pair()
    run_publication, close_publication = _unit_fragment_publications()
    alternate_run = f"alternate-run@{LAUNCH}.service"
    alternate_close = f"alternate-close@{LAUNCH}.service"
    original_pair = installation.configured_pair
    alternate_pair = ConfiguredPairFact.create(
        replace(
            original_pair.run,
            unit=alternate_run,
            peer_unit=alternate_close,
            configured_directives=tuple(
                sorted(
                    {
                        **dict(original_pair.run.configured_directives),
                        "OnSuccess": alternate_close,
                        "OnFailure": alternate_close,
                    }.items()
                )
            ),
            on_success=(alternate_close,),
            on_failure=(alternate_close,),
        ),
        replace(
            original_pair.closer,
            unit=alternate_close,
            peer_unit=alternate_run,
            configured_directives=tuple(
                sorted(
                    {
                        **dict(original_pair.closer.configured_directives),
                        "After": alternate_run,
                    }.items()
                )
            ),
            after=(alternate_run,),
        ),
    )
    changed = json.loads(installation.raw)
    changed["run_unit"] = alternate_run
    changed["close_unit"] = alternate_close
    changed["configured_pair"] = alternate_pair.to_mapping()
    changed["configured_pair_sha256"] = alternate_pair.configured_pair_sha256
    alternate_installation = InstallationRecord.from_bytes(
        _canonical(changed),
        authority,
    )

    with pytest.raises(
        ManagerAcceptanceError,
        match="exact template",
    ):
        UnitPublicationReceipt.create(
            authority=authority,
            installation=alternate_installation,
            run_template_raw=RUN_TEMPLATE_RAW,
            close_template_raw=CLOSE_TEMPLATE_RAW,
            run_publication=run_publication,
            close_publication=close_publication,
        )


@pytest.mark.parametrize(
    "field",
    (
        "unit_publication_sha256",
        "configured_pair_readback_sha256",
        "configured_pair_sha256",
    ),
)
def test_manager_reload_receipt_rejects_split_configured_authority(
    field: str,
) -> None:
    receipt = _manager_reload_receipt()
    changed = json.loads(receipt.raw)
    changed[field] = "0" * 64

    with pytest.raises(ManagerAcceptanceError, match="digest differs"):
        ManagerReloadReceipt.from_bytes(
            _canonical(changed),
            configured_readback=_configured_readback(),
            unit_publication=_unit_publication(),
        )


@pytest.mark.parametrize(
    "field",
    (
        "unit_publication_sha256",
        "configured_pair_readback_sha256",
        "configured_pair_sha256",
        "manager_reload_sha256",
    ),
)
def test_loaded_manager_receipt_rejects_split_configured_authority(
    field: str,
) -> None:
    receipt = acquire_loaded_manager_receipt(
        _Manager(),
        configured_readback=_configured_readback(),
        unit_publication=_unit_publication(),
        manager_reload=_manager_reload_receipt(),
        persist_and_reopen=lambda raw: raw,
    )
    changed = json.loads(receipt.raw)
    changed[field] = "0" * 64

    with pytest.raises(ManagerAcceptanceError, match="digest differs"):
        LoadedManagerReceipt.from_bytes(
            _canonical(changed),
            configured_readback=_configured_readback(),
            unit_publication=_unit_publication(),
            manager_reload=_manager_reload_receipt(),
        )


@pytest.mark.parametrize(
    ("unit", "field", "value"),
    (
        (RUN, "NoNewPrivileges", 1),
        (RUN, "ProtectControlGroups", 0),
        (CLOSE, "PrivateTmp", 1),
    ),
)
def test_loaded_manager_rejects_boolean_integer_type_aliases(
    unit: str,
    field: str,
    value: int,
) -> None:
    manager = _Manager()
    manager.values[unit][field] = value

    with pytest.raises(ManagerAcceptanceError, match="property mapping differs"):
        acquire_loaded_manager_receipt(
            manager,
            configured_readback=_configured_readback(),
            unit_publication=_unit_publication(),
            manager_reload=_manager_reload_receipt(),
            persist_and_reopen=lambda raw: raw,
        )


def test_loaded_manager_rejects_nested_type_alias_and_parser_tamper() -> None:
    manager = _Manager()
    command = list(manager.values[RUN]["ExecStart"][0])
    command[2] = 0
    manager.values[RUN]["ExecStart"] = [tuple(command)]
    with pytest.raises(ManagerAcceptanceError, match="property mapping differs"):
        acquire_loaded_manager_receipt(
            manager,
            configured_readback=_configured_readback(),
            unit_publication=_unit_publication(),
            manager_reload=_manager_reload_receipt(),
            persist_and_reopen=lambda raw: raw,
        )

    receipt = acquire_loaded_manager_receipt(
        _Manager(),
        configured_readback=_configured_readback(),
        unit_publication=_unit_publication(),
        manager_reload=_manager_reload_receipt(),
        persist_and_reopen=lambda raw: raw,
    )
    changed = json.loads(receipt.raw)
    changed["run_properties"]["NoNewPrivileges"] = 1
    with pytest.raises(ManagerAcceptanceError, match="properties differ"):
        LoadedManagerReceipt.from_bytes(
            _canonical(changed),
            configured_readback=_configured_readback(),
            unit_publication=_unit_publication(),
            manager_reload=_manager_reload_receipt(),
        )


def test_manager_acquisition_rejects_owner_property_and_object_path_drift() -> None:
    owner_drift = _Manager()
    owner_drift.drift_after_run = True
    with pytest.raises(ManagerAcceptanceError, match="identity changed"):
        acquire_loaded_manager_receipt(
            owner_drift,
            configured_readback=_configured_readback(),
            unit_publication=_unit_publication(),
            manager_reload=_manager_reload_receipt(),
            persist_and_reopen=lambda raw: raw,
        )

    property_drift = _Manager()
    property_drift.values[RUN]["Type"] = "notify"
    with pytest.raises(ManagerAcceptanceError, match="property mapping differs"):
        acquire_loaded_manager_receipt(
            property_drift,
            configured_readback=_configured_readback(),
            unit_publication=_unit_publication(),
            manager_reload=_manager_reload_receipt(),
            persist_and_reopen=lambda raw: raw,
        )

    path_drift = _Manager()
    original_get = path_drift.get_unit

    def get_different(unit: str) -> str:
        if unit == RUN:
            return "/org/freedesktop/systemd1/unit/different_2eservice"
        return original_get(unit)

    path_drift.get_unit = get_different  # type: ignore[method-assign]
    with pytest.raises(ManagerAcceptanceError, match="object paths differ"):
        acquire_loaded_manager_receipt(
            path_drift,
            configured_readback=_configured_readback(),
            unit_publication=_unit_publication(),
            manager_reload=_manager_reload_receipt(),
            persist_and_reopen=lambda raw: raw,
        )

    same_paths = _Manager()
    same_paths.object_paths[CLOSE] = RUN_OBJECT
    with pytest.raises(ManagerAcceptanceError, match="object paths must differ"):
        acquire_loaded_manager_receipt(
            same_paths,
            configured_readback=_configured_readback(),
            unit_publication=_unit_publication(),
            manager_reload=_manager_reload_receipt(),
            persist_and_reopen=lambda raw: raw,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("Transient", True),
        ("Transient", None),
        ("FragmentPath", "/tmp/caller-selected.service"),
        ("FragmentPath", None),
        ("DropInPaths", ["/etc/systemd/system/scion-run@.service.d/override.conf"]),
        ("DropInPaths", None),
    ),
)
def test_loaded_manager_rejects_transient_fragment_or_dropin_drift(
    field: str,
    value: object,
) -> None:
    manager = _Manager()
    if value is None:
        manager.values[RUN].pop(field)
    else:
        manager.values[RUN][field] = value
    with pytest.raises(ManagerAcceptanceError):
        acquire_loaded_manager_receipt(
            manager,
            configured_readback=_configured_readback(),
            unit_publication=_unit_publication(),
            manager_reload=_manager_reload_receipt(),
            persist_and_reopen=lambda raw: raw,
        )


@pytest.mark.parametrize(
    "invocation",
    (
        "0" * 32,
        [0] * 15,
        [0] * 15 + [256],
        [0] * 15 + [True],
        [1] + [0] * 15,
    ),
)
def test_loaded_manager_requires_strict_empty_invocation_ay(
    invocation: object,
) -> None:
    manager = _Manager()
    manager.values[RUN]["InvocationID"] = invocation
    with pytest.raises(ManagerAcceptanceError):
        acquire_loaded_manager_receipt(
            manager,
            configured_readback=_configured_readback(),
            unit_publication=_unit_publication(),
            manager_reload=_manager_reload_receipt(),
            persist_and_reopen=lambda raw: raw,
        )


def test_reload_and_loaded_acquisition_require_root_before_manager_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = _Manager()
    monkeypatch.setattr(external_installation.os, "geteuid", lambda: 1001)
    with pytest.raises(PermissionError, match="effective UID 0"):
        apply_manager_reload(
            manager,
            configured_readback=_configured_readback(),
            unit_publication=_unit_publication(),
            persist_and_reopen=lambda raw: raw,
        )
    with pytest.raises(PermissionError, match="effective UID 0"):
        acquire_loaded_manager_receipt(
            manager,
            configured_readback=_configured_readback(),
            unit_publication=_unit_publication(),
            manager_reload=_manager_reload_receipt(),
            persist_and_reopen=lambda raw: raw,
        )
    assert manager.calls == []


def test_real_adapter_surface_is_narrow_and_decodes_systemd_wire(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Integer(int):
        pass

    class _String(str):
        pass

    class _Boolean:
        def __init__(self, value: bool) -> None:
            self.value = value

        def __bool__(self) -> bool:
            return self.value

    class _Struct(tuple):
        pass

    class _Array(list):
        pass

    class _DbusException(Exception):
        def __init__(self, name: str, message: str) -> None:
            super().__init__(message)
            self._name = name
            self._message = message

        def get_dbus_name(self) -> str:
            return self._name

        def get_dbus_message(self) -> str:
            return self._message

    class _Daemon:
        def GetNameOwner(self, name: str) -> _String:
            assert name == "org.freedesktop.systemd1"
            return _String(":1.42")

    class _ManagerObject:
        def __init__(self) -> None:
            self.calls: list[tuple[object, ...]] = []
            self.start_error: str | None = None

        def Get(self, interface: str, name: str) -> _String:
            assert interface == "org.freedesktop.systemd1.Manager"
            assert name == "Version"
            return _String(VERSION)

        def Reload(self) -> None:
            self.calls.append(("reload",))

        def RefUnit(self, unit: str) -> None:
            self.calls.append(("ref", unit))

        def UnrefUnit(self, unit: str) -> None:
            self.calls.append(("unref", unit))

        def LoadUnit(self, unit: str) -> _String:
            self.calls.append(("load", unit))
            return _String(RUN_OBJECT)

        def GetUnit(self, unit: str) -> _String:
            self.calls.append(("get", unit))
            return _String(RUN_OBJECT)

        def StartUnit(self, unit: str, mode: str) -> _String:
            self.calls.append(("start", unit, mode))
            if self.start_error is not None:
                raise _DbusException(self.start_error, "wire failure")
            return _String("/org/freedesktop/systemd1/job/731")

    class _UnitObject:
        def Get(self, interface: str, name: str) -> object:
            assert interface == "org.freedesktop.systemd1.Unit"
            values = {
                "Id": _String(RUN),
                "Transient": _Boolean(False),
                "InvocationID": _Array([_Integer(0) for _ in range(16)]),
            }
            return values[name]

    manager_object = _ManagerObject()

    class _Bus:
        def get_object(self, destination: str, path: str) -> object:
            if destination == "org.freedesktop.DBus":
                return _Daemon()
            if path == "/org/freedesktop/systemd1":
                return manager_object
            assert destination == ":1.42"
            assert path == RUN_OBJECT
            return _UnitObject()

    class _Dbus:
        Boolean = _Boolean
        Byte = _Integer
        Int16 = _Integer
        UInt16 = _Integer
        Int32 = _Integer
        UInt32 = _Integer
        Int64 = _Integer
        UInt64 = _Integer
        String = _String
        ObjectPath = _String
        Signature = _String
        Struct = _Struct
        Array = _Array

        class exceptions:
            DBusException = _DbusException

        @staticmethod
        def SystemBus() -> _Bus:
            return _Bus()

        @staticmethod
        def Interface(value: object, *, dbus_interface: str) -> object:
            assert dbus_interface
            return value

    monkeypatch.setattr(
        external_installation.importlib,
        "import_module",
        lambda name: _Dbus if name == "dbus" else None,
    )
    monkeypatch.setattr(
        external_installation.Path,
        "read_bytes",
        lambda _path: (BOOT + "\n").encode(),
    )

    adapter = SystemdExternalManager()
    assert adapter.get_unique_owner() == ":1.42"
    assert adapter.get_boot_id() == BOOT
    assert adapter.get_version() == VERSION
    adapter.reload()
    adapter.ref_unit(RUN)
    assert adapter.load_unit(RUN) == RUN_OBJECT
    assert adapter.get_unit(RUN) == RUN_OBJECT
    assert adapter.read_properties(
        RUN,
        ("Id", "InvocationID", "Transient"),
    ) == {
        "Id": RUN,
        "InvocationID": [0] * 16,
        "Transient": False,
    }
    assert adapter.start_unit(RUN, "fail") == "/org/freedesktop/systemd1/job/731"
    adapter.unref_unit(RUN)

    manager_object.start_error = "org.freedesktop.systemd1.UnitExists"
    with pytest.raises(DefiniteStartError):
        adapter.start_unit(RUN, "fail")
    manager_object.start_error = "org.freedesktop.DBus.Error.NoReply"
    with pytest.raises(_DbusException):
        adapter.start_unit(RUN, "fail")


class _StartManager:
    def __init__(self, outcome: str) -> None:
        self.outcome = outcome
        self.calls: list[tuple[str, ...]] = []
        self.owner = ":1.42"
        self.boot = BOOT
        self.version = VERSION

    def get_unique_owner(self) -> str:
        self.calls.append(("owner", self.owner))
        return self.owner

    def get_boot_id(self) -> str:
        self.calls.append(("boot", self.boot))
        return self.boot

    def get_version(self) -> str:
        self.calls.append(("version", self.version))
        return self.version

    def ref_unit(self, unit: str) -> None:
        self.calls.append(("ref", unit))
        if self.outcome == "ref-rejected":
            raise DefiniteStartError(
                "org.freedesktop.systemd1.NoSuchUnit",
                "unit reference failed",
            )
        if self.outcome == "drift-before-start":
            self.owner = ":1.99"

    def unref_unit(self, unit: str) -> None:
        self.calls.append(("unref", unit))

    def start_unit(self, unit: str, mode: str) -> str:
        self.calls.append(("start", unit, mode))
        if self.outcome == "rejected":
            raise DefiniteStartError(
                "org.freedesktop.systemd1.UnitExists",
                "unit already has a conflicting job",
            )
        if self.outcome == "unknown":
            raise TimeoutError("response lost")
        if self.outcome == "drift-after-start":
            self.owner = ":1.99"
        return "/org/freedesktop/systemd1/job/731"


def _start_bundle() -> tuple[
    StartAuthorizationReceipt,
    InstalledAcceptance,
    StartIssueReceipt,
    tuple[RootPhaseIntentReceipt, ...],
    tuple[RootPhaseReceipt, ...],
]:
    prefix_intents, prefix_phases = _phase_prefix(len(INSTALL_PHASES) - 1)
    installed = InstalledAcceptance.create(
        launch_id=LAUNCH,
        authority_sha256="9" * 64,
        installation_sha256=INSTALLATION,
        phase_intents=prefix_intents,
        phase_receipts=prefix_phases,
        problem_state_schema="scion.test-problem-state.v1",
        problem_state_sha256=prefix_phases[-1].effect_sha256,
    )
    final_intent = RootPhaseIntentReceipt.create(
        launch_id=LAUNCH,
        phase=INSTALL_PHASES[-1],
        predecessor_sha256=(prefix_phases[-1].raw_sha256,),
        effect_authority_sha256=installed.raw_sha256,
    )
    final_receipt = RootPhaseReceipt.create(
        intent=final_intent,
        effect_sha256=installed.raw_sha256,
    )
    intents = (*prefix_intents, final_intent)
    phases = (*prefix_phases, final_receipt)
    authorization = StartAuthorizationReceipt.create(
        launch_id=LAUNCH,
        authority_sha256=installed.authority_sha256,
        installation_sha256=installed.installation_sha256,
        installed_acceptance_sha256=installed.raw_sha256,
        prospective_intent_sha256="8" * 64,
        plan_sha256="7" * 64,
        selection_key=SELECTION,
        preparation_commit_sha256="6" * 64,
        root_selection_sha256="5" * 64,
        user_statement="authorized exact first dispatch",
        task_event_identity="thread:019f86f1",
        recorded_at_utc="2026-07-23T17:00:00Z",
        unit=RUN,
    )
    issue = StartIssueReceipt.create_authorized(
        authorization,
        prestart_receipt_sha256=PRESTART,
        manager_identity=external_installation.ManagerIdentity(
            unique_owner=":1.42",
            boot_id=BOOT,
            version=VERSION,
        ),
    )
    return authorization, installed, issue, intents, phases


def _reacquire_prestart(
    authorization: StartAuthorizationReceipt,
    installed_acceptance: InstalledAcceptance,
) -> bytes:
    assert type(authorization) is StartAuthorizationReceipt
    assert type(installed_acceptance) is InstalledAcceptance
    return PRESTART_RAW


def test_installed_acceptance_and_start_permit_reject_alternate_complete_dag() -> None:
    authorization, installed, issue, _intents, _phases = _start_bundle()
    alternate_intents: list[RootPhaseIntentReceipt] = []
    alternate_phases: list[RootPhaseReceipt] = []
    for index, phase in enumerate(INSTALL_PHASES):
        intent = RootPhaseIntentReceipt.create(
            launch_id=LAUNCH,
            phase=phase,
            predecessor_sha256=(
                () if index == 0 else (alternate_phases[-1].raw_sha256,)
            ),
            effect_authority_sha256=hashlib.sha256(
                f"alternate-authority:{phase.value}".encode()
            ).hexdigest(),
        )
        receipt = RootPhaseReceipt.create(
            intent=intent,
            effect_sha256=hashlib.sha256(
                f"alternate-effect:{phase.value}".encode()
            ).hexdigest(),
        )
        alternate_intents.append(intent)
        alternate_phases.append(receipt)
    alternate_dag = (
        tuple(alternate_intents),
        tuple(alternate_phases),
    )

    assert validate_root_transaction(*alternate_dag) == alternate_dag
    assert (
        tuple(intent.raw_sha256 for intent in alternate_dag[0][:-1])
        != installed.phase_intent_sha256
    )
    assert (
        tuple(receipt.raw_sha256 for receipt in alternate_dag[1][:-1])
        != installed.phase_receipt_sha256
    )
    with pytest.raises(ReceiptDagError, match="acceptance phase DAG differs"):
        installed.verify_phase_receipts(*alternate_dag)

    manager = _StartManager("returned")
    writer = NoReplaceReceiptSet()
    reacquire_calls: list[str] = []

    def reacquire(
        current_authorization: StartAuthorizationReceipt,
        current_installed: InstalledAcceptance,
    ) -> bytes:
        del current_authorization, current_installed
        reacquire_calls.append("read")
        return PRESTART_RAW

    with pytest.raises(ReceiptDagError, match="acceptance phase DAG differs"):
        StartPermitOwner(
            authorization=authorization,
            installed_acceptance=installed,
            phase_intents=alternate_dag[0],
            phase_receipts=alternate_dag[1],
            issue=issue,
            manager=manager,
            reacquire_prestart=reacquire,
            writer=writer,
        )

    assert reacquire_calls == []
    assert manager.calls == []
    assert writer.names == ()


def test_start_authorization_closes_prospective_and_installed_identity() -> None:
    receipt = StartAuthorizationReceipt.create(
        launch_id=LAUNCH,
        authority_sha256="9" * 64,
        installation_sha256=INSTALLATION,
        installed_acceptance_sha256=INSTALLED,
        prospective_intent_sha256="8" * 64,
        plan_sha256="7" * 64,
        selection_key=SELECTION,
        preparation_commit_sha256="6" * 64,
        root_selection_sha256="5" * 64,
        user_statement="authorized exact first dispatch",
        task_event_identity="thread:019f86f1",
        recorded_at_utc="2026-07-23T17:00:00Z",
        unit=RUN,
    )

    assert StartAuthorizationReceipt.from_bytes(receipt.raw) == receipt
    assert receipt.unit == RUN
    drift = json.loads(receipt.raw)
    drift["retry"] = True
    with pytest.raises(CanonicalReceiptError, match="action differs"):
        StartAuthorizationReceipt.from_bytes(_canonical(drift))


@pytest.mark.parametrize(
    ("outcome", "state", "terminal_name"),
    (
        ("returned", StartDispatchState.RETURNED, "START_RETURNED"),
        ("rejected", StartDispatchState.REJECTED, "START_REJECTED"),
        ("unknown", StartDispatchState.UNKNOWN, "START_DISPATCH_UNKNOWN"),
    ),
)
def test_start_permit_is_one_shot_and_persists_issue_before_exact_dispatch(
    outcome: str,
    state: StartDispatchState,
    terminal_name: str,
) -> None:
    authorization, installed, issue, intents, phases = _start_bundle()
    manager = _StartManager(outcome)
    writer = NoReplaceReceiptSet()
    owner = StartPermitOwner(
        authorization=authorization,
        installed_acceptance=installed,
        phase_intents=intents,
        phase_receipts=phases,
        issue=issue,
        manager=manager,
        reacquire_prestart=_reacquire_prestart,
        writer=writer,
    )

    result = owner.dispatch()

    assert result.state is state
    assert writer.write_order == ("START_ISSUED", terminal_name)
    assert writer.read("START_ISSUED") == issue.raw
    assert StartDispatchReceipt.from_bytes(writer.read(terminal_name)) == result
    assert manager.calls[0:3] == [
        ("owner", ":1.42"),
        ("boot", BOOT),
        ("version", VERSION),
    ]
    assert ("ref", RUN) in manager.calls
    assert ("start", RUN, "fail") in manager.calls
    assert manager.calls[-1] == ("unref", RUN)
    if state is StartDispatchState.RETURNED:
        assert result.job_object_path == "/org/freedesktop/systemd1/job/731"
    elif state is StartDispatchState.REJECTED:
        assert result.error_name == "org.freedesktop.systemd1.UnitExists"
    else:
        assert result.job_object_path is None
        assert result.error_name is None
    with pytest.raises(StartPermitError, match="already spent"):
        owner.dispatch()
    assert [call for call in manager.calls if call[0] == "start"] == [
        ("start", RUN, "fail")
    ]
    assert classify_start_dispatch(issue, (result,)) is state


def test_issue_only_crash_classifies_unknown_and_never_absent() -> None:
    _authorization, _installed, issue, _intents, _phases = _start_bundle()

    assert classify_start_dispatch(None, ()) is None
    assert classify_start_dispatch(issue, ()) is StartDispatchState.UNKNOWN
    with pytest.raises(StartPermitError, match="without START_ISSUED"):
        classify_start_dispatch(
            None,
            (
                StartDispatchReceipt.create(
                    issue_sha256=issue.raw_sha256,
                    state=StartDispatchState.UNKNOWN,
                ),
            ),
        )


def test_definite_error_before_start_is_unknown_not_start_rejected() -> None:
    authorization, installed, issue, intents, phases = _start_bundle()
    manager = _StartManager("ref-rejected")
    writer = NoReplaceReceiptSet()
    result = StartPermitOwner(
        authorization=authorization,
        installed_acceptance=installed,
        phase_intents=intents,
        phase_receipts=phases,
        issue=issue,
        manager=manager,
        reacquire_prestart=_reacquire_prestart,
        writer=writer,
    ).dispatch()

    assert result.state is StartDispatchState.UNKNOWN
    assert writer.write_order == ("START_ISSUED", "START_DISPATCH_UNKNOWN")
    assert not any(call[0] == "start" for call in manager.calls)


@pytest.mark.parametrize("outcome", ("drift-before-start", "drift-after-start"))
def test_start_manager_identity_drift_is_unknown(outcome: str) -> None:
    authorization, installed, issue, intents, phases = _start_bundle()
    manager = _StartManager(outcome)
    writer = NoReplaceReceiptSet()

    result = StartPermitOwner(
        authorization=authorization,
        installed_acceptance=installed,
        phase_intents=intents,
        phase_receipts=phases,
        issue=issue,
        manager=manager,
        reacquire_prestart=_reacquire_prestart,
        writer=writer,
    ).dispatch()

    assert result.state is StartDispatchState.UNKNOWN
    assert writer.write_order == ("START_ISSUED", "START_DISPATCH_UNKNOWN")


def test_start_manager_identity_mismatch_refuses_before_issue() -> None:
    authorization, installed, issue, intents, phases = _start_bundle()
    manager = _StartManager("returned")
    manager.owner = ":1.99"
    writer = NoReplaceReceiptSet()

    with pytest.raises(StartPermitError, match="differs before issue"):
        StartPermitOwner(
            authorization=authorization,
            installed_acceptance=installed,
            phase_intents=intents,
            phase_receipts=phases,
            issue=issue,
            manager=manager,
            reacquire_prestart=_reacquire_prestart,
            writer=writer,
        ).dispatch()

    assert writer.names == ()
    assert not any(call[0] == "start" for call in manager.calls)


@pytest.mark.parametrize("mode", ("drift", "error"))
def test_start_permit_reacquires_prestart_before_manager_or_issue(mode: str) -> None:
    authorization, installed, issue, intents, phases = _start_bundle()
    manager = _StartManager("returned")
    writer = NoReplaceReceiptSet()

    def reacquire(
        current_authorization: StartAuthorizationReceipt,
        current_installed: InstalledAcceptance,
    ) -> bytes:
        assert current_authorization is authorization
        assert current_installed is installed
        if mode == "error":
            raise RuntimeError("live gate failed")
        return b'{"schema":"fixture.prestart.drift"}\n'

    with pytest.raises(StartPermitError, match="pre-start"):
        StartPermitOwner(
            authorization=authorization,
            installed_acceptance=installed,
            phase_intents=intents,
            phase_receipts=phases,
            issue=issue,
            manager=manager,
            reacquire_prestart=reacquire,
            writer=writer,
        ).dispatch()

    assert manager.calls == []
    assert writer.names == ()


def test_start_permit_requires_root_and_existing_issue_name_prevents_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authorization, installed, issue, intents, phases = _start_bundle()
    manager = _StartManager("returned")
    writer = NoReplaceReceiptSet()
    unprivileged = StartPermitOwner(
        authorization=authorization,
        installed_acceptance=installed,
        phase_intents=intents,
        phase_receipts=phases,
        issue=issue,
        manager=manager,
        reacquire_prestart=_reacquire_prestart,
        writer=writer,
    )
    monkeypatch.setattr(external_installation.os, "geteuid", lambda: 1001)
    with pytest.raises(PermissionError, match="effective UID 0"):
        unprivileged.dispatch()
    assert manager.calls == []

    monkeypatch.setattr(external_installation.os, "geteuid", lambda: 0)
    writer.write_no_replace("START_ISSUED", issue.raw)
    collision_manager = _StartManager("returned")
    collision = StartPermitOwner(
        authorization=authorization,
        installed_acceptance=installed,
        phase_intents=intents,
        phase_receipts=phases,
        issue=issue,
        manager=collision_manager,
        reacquire_prestart=_reacquire_prestart,
        writer=writer,
    )
    with pytest.raises(FileExistsError):
        collision.dispatch()
    assert not any(call[0] == "start" for call in collision_manager.calls)


def test_external_installation_exposes_only_narrow_manager_actions() -> None:
    source_path = (
        Path(__file__).parents[4] / "runtime" / "execution" / "external_installation.py"
    )
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }

    assert "subprocess" not in imported
    assert "dbus" not in imported
    assert "ctypes" not in imported
    assert "fcntl" not in imported
    assert "StartUnit" in source
    assert "StopUnit" not in source
    assert "RestartUnit" not in source
