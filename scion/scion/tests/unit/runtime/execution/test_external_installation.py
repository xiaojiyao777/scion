from __future__ import annotations

import ast
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
    MountBindingReceipt,
    MountInfoError,
    NoReplaceReceiptSet,
    ReceiptDagError,
    RootInstallationState,
    RootPhaseReceipt,
    SelectionReceipt,
    StartAuthorizationReceipt,
    StartDispatchReceipt,
    StartDispatchState,
    StartIssueReceipt,
    StartPermitError,
    StartPermitOwner,
    SystemdExternalManager,
    acquire_loaded_manager_receipt,
    classify_root_installation,
    classify_start_dispatch,
    parse_selected_mountinfo,
    validate_forward_receipt_dag,
)

LAUNCH = "a" * 64
SELECTION = "b" * 64
CANDIDATE = "c" * 64
INTENT = "d" * 64
PAIR = "e" * 64
AUTHORIZATION = "1" * 64
INSTALLED = "2" * 64
PRESTART_RAW = b'{"schema":"fixture.prestart.v1"}\n'
PRESTART = hashlib.sha256(PRESTART_RAW).hexdigest()
INSTALLATION = "4" * 64
RUN = "scion-run@fixture.service"
CLOSE = "scion-close@fixture.service"
BOOT = "12345678-1234-1234-1234-123456789abc"
VERSION = "255.4-1ubuntu8"
RUN_OBJECT = "/org/freedesktop/systemd1/unit/scion_2drun_40fixture_2eservice"
CLOSE_OBJECT = "/org/freedesktop/systemd1/unit/scion_2dclose_40fixture_2eservice"


@pytest.fixture(autouse=True)
def _effective_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(external_installation.os, "geteuid", lambda: 0)


def _canonical(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode()


def _phase_prefix(length: int) -> tuple[RootPhaseReceipt, ...]:
    receipts: list[RootPhaseReceipt] = []
    for index, phase in enumerate(INSTALL_PHASES[:length]):
        receipt = RootPhaseReceipt.create(
            launch_id=LAUNCH,
            phase=phase,
            predecessor_sha256=(
                () if index == 0 else (receipts[index - 1].raw_sha256,)
            ),
            effect_sha256=hashlib.sha256(phase.value.encode()).hexdigest(),
        )
        receipts.append(receipt)
    return tuple(receipts)


def _run_properties() -> dict[str, object]:
    return {
        "Id": RUN,
        "FragmentPath": "/etc/systemd/system/scion-run@.service",
        "DropInPaths": [],
        "LoadState": "loaded",
        "ActiveState": "inactive",
        "SubState": "dead",
        "Job": [0, "/"],
        "InvocationID": [0] * 16,
        "Transient": False,
        "Type": "exec",
        "User": "clawd",
        "ExecStart": [
            (
                "/opt/scion/python",
                ["/opt/scion/python", "/opt/scion/tool", "run"],
                False,
            )
        ],
    }


def _close_properties() -> dict[str, object]:
    return {
        "Id": CLOSE,
        "FragmentPath": "/etc/systemd/system/scion-close@.service",
        "DropInPaths": [],
        "LoadState": "loaded",
        "ActiveState": "inactive",
        "SubState": "dead",
        "Job": [0, "/"],
        "InvocationID": [0] * 16,
        "Transient": False,
        "Type": "oneshot",
        "User": "clawd",
        "ExecStart": [
            (
                "/opt/scion/python",
                ["/opt/scion/python", "/opt/scion/tool", "close"],
                False,
            )
        ],
    }


def test_root_phase_receipts_form_one_forward_no_replace_prefix() -> None:
    partial = _phase_prefix(4)
    complete = _phase_prefix(len(INSTALL_PHASES))

    assert classify_root_installation(()) is RootInstallationState.ABSENT
    assert classify_root_installation(partial) is RootInstallationState.PARTIAL_HOLD
    assert classify_root_installation(complete) is RootInstallationState.ACCEPTED
    assert validate_forward_receipt_dag(tuple(reversed(complete))) == complete
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


def test_root_receipt_gap_or_wrong_predecessor_is_partial_hold() -> None:
    first = _phase_prefix(1)[0]
    wrong_second = RootPhaseReceipt.create(
        launch_id=LAUNCH,
        phase=INSTALL_PHASES[1],
        predecessor_sha256=("f" * 64,),
        effect_sha256="9" * 64,
    )
    gapped = RootPhaseReceipt.create(
        launch_id=LAUNCH,
        phase=INSTALL_PHASES[2],
        predecessor_sha256=(first.raw_sha256,),
        effect_sha256="8" * 64,
    )

    with pytest.raises(ReceiptDagError):
        validate_forward_receipt_dag((first, wrong_second))
    assert (
        classify_root_installation((first, wrong_second))
        is RootInstallationState.PARTIAL_HOLD
    )
    assert (
        classify_root_installation((first, gapped))
        is RootInstallationState.PARTIAL_HOLD
    )


def test_root_phase_parser_rejects_noncanonical_and_duplicate_fields() -> None:
    receipt = _phase_prefix(1)[0]
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
        + b'","phase":"ROOT_STAGING_IMPORTED",'
        + b'"predecessor_sha256":[],"schema":"scion.external-root-phase.v1"}\n'
    )
    with pytest.raises(CanonicalReceiptError, match="not canonical JSON"):
        RootPhaseReceipt.from_bytes(duplicate)


def test_selection_and_installed_acceptance_are_closed_canonical_records() -> None:
    phases = _phase_prefix(len(INSTALL_PHASES))
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
        phase_receipts=phases,
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
    )

    assert SelectionReceipt.from_bytes(selection.raw) == selection
    assert selection.source_candidate_identity == source_candidate
    assert InstalledAcceptance.from_bytes(accepted.raw) == accepted
    assert json.loads(accepted.raw)["formal_jobs_started"] == 0
    with pytest.raises(TypeError, match="parsed from exact bytes"):
        SelectionReceipt()
    with pytest.raises(TypeError, match="parsed from exact bytes"):
        InstalledAcceptance()

    drift = json.loads(accepted.raw)
    drift["formal_jobs_started"] = 1
    with pytest.raises(CanonicalReceiptError, match="state differs"):
        InstalledAcceptance.from_bytes(_canonical(drift))


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


def test_narrow_manager_acquisition_pins_reopens_and_unrefs_in_order() -> None:
    manager = _Manager()
    persisted: list[bytes] = []

    def persist(raw: bytes) -> bytes:
        persisted.append(raw)
        return bytes(raw)

    receipt = acquire_loaded_manager_receipt(
        manager,
        run_unit=RUN,
        close_unit=CLOSE,
        expected_run_properties=_run_properties(),
        expected_close_properties=_close_properties(),
        configured_pair_sha256=PAIR,
        persist_and_reopen=persist,
    )

    assert persisted == [receipt.raw]
    assert receipt.manager_identity.unique_owner == ":1.42"
    assert receipt.manager_identity.boot_id == BOOT
    assert receipt.manager_identity.version == VERSION
    assert receipt.run_object_path == RUN_OBJECT
    assert receipt.close_object_path == CLOSE_OBJECT
    assert dict(receipt.run_properties)["InvocationID"] == "0" * 32
    assert manager.calls[0] == ("reload",)
    assert ("ref", RUN) in manager.calls
    assert ("ref", CLOSE) in manager.calls
    assert manager.calls[-2:] == [("unref", CLOSE), ("unref", RUN)]
    assert (
        LoadedManagerReceipt.from_bytes(
            receipt.raw,
            expected_run_properties=_run_properties(),
            expected_close_properties=_close_properties(),
            expected_configured_pair_sha256=PAIR,
        )
        == receipt
    )


def test_manager_acquisition_rejects_owner_property_and_object_path_drift() -> None:
    owner_drift = _Manager()
    owner_drift.drift_after_run = True
    with pytest.raises(ManagerAcceptanceError, match="identity changed"):
        acquire_loaded_manager_receipt(
            owner_drift,
            run_unit=RUN,
            close_unit=CLOSE,
            expected_run_properties=_run_properties(),
            expected_close_properties=_close_properties(),
            configured_pair_sha256=PAIR,
            persist_and_reopen=lambda raw: raw,
        )

    property_drift = _Manager()
    property_drift.values[RUN]["Type"] = "notify"
    with pytest.raises(ManagerAcceptanceError, match="property mapping differs"):
        acquire_loaded_manager_receipt(
            property_drift,
            run_unit=RUN,
            close_unit=CLOSE,
            expected_run_properties=_run_properties(),
            expected_close_properties=_close_properties(),
            configured_pair_sha256=PAIR,
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
            run_unit=RUN,
            close_unit=CLOSE,
            expected_run_properties=_run_properties(),
            expected_close_properties=_close_properties(),
            configured_pair_sha256=PAIR,
            persist_and_reopen=lambda raw: raw,
        )

    same_paths = _Manager()
    same_paths.object_paths[CLOSE] = RUN_OBJECT
    with pytest.raises(ManagerAcceptanceError, match="object paths must differ"):
        acquire_loaded_manager_receipt(
            same_paths,
            run_unit=RUN,
            close_unit=CLOSE,
            expected_run_properties=_run_properties(),
            expected_close_properties=_close_properties(),
            configured_pair_sha256=PAIR,
            persist_and_reopen=lambda raw: raw,
        )


@pytest.mark.parametrize("transient", (True, None))
def test_loaded_manager_rejects_transient_or_missing_fragment(
    transient: object,
) -> None:
    manager = _Manager()
    if transient is None:
        manager.values[RUN].pop("Transient")
    else:
        manager.values[RUN]["Transient"] = transient
    with pytest.raises(ManagerAcceptanceError):
        acquire_loaded_manager_receipt(
            manager,
            run_unit=RUN,
            close_unit=CLOSE,
            expected_run_properties=_run_properties(),
            expected_close_properties=_close_properties(),
            configured_pair_sha256=PAIR,
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
            run_unit=RUN,
            close_unit=CLOSE,
            expected_run_properties=_run_properties(),
            expected_close_properties=_close_properties(),
            configured_pair_sha256=PAIR,
            persist_and_reopen=lambda raw: raw,
        )


def test_loaded_manager_mutation_requires_root_before_reload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = _Manager()
    monkeypatch.setattr(external_installation.os, "geteuid", lambda: 1001)
    with pytest.raises(PermissionError, match="effective UID 0"):
        acquire_loaded_manager_receipt(
            manager,
            run_unit=RUN,
            close_unit=CLOSE,
            expected_run_properties=_run_properties(),
            expected_close_properties=_close_properties(),
            configured_pair_sha256=PAIR,
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
    tuple[RootPhaseReceipt, ...],
]:
    phases = _phase_prefix(len(INSTALL_PHASES))
    installed = InstalledAcceptance.create(
        launch_id=LAUNCH,
        authority_sha256="9" * 64,
        installation_sha256=INSTALLATION,
        phase_receipts=phases,
        subordinate_receipt_sha256={
            "root_selection": "1" * 64,
            "sealed_store": "2" * 64,
            "environment_content": "3" * 64,
            "environment_relocation": "4" * 64,
            "projection": "5" * 64,
            "units": "6" * 64,
            "loaded_manager": "7" * 64,
            "dry_root": "8" * 64,
            "prestart_absence": "a" * 64,
        },
    )
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
    return authorization, installed, issue, phases


def _reacquire_prestart(
    authorization: StartAuthorizationReceipt,
    installed_acceptance: InstalledAcceptance,
) -> bytes:
    assert type(authorization) is StartAuthorizationReceipt
    assert type(installed_acceptance) is InstalledAcceptance
    return PRESTART_RAW


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
    authorization, installed, issue, phases = _start_bundle()
    manager = _StartManager(outcome)
    writer = NoReplaceReceiptSet()
    owner = StartPermitOwner(
        authorization=authorization,
        installed_acceptance=installed,
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
    _authorization, _installed, issue, _phases = _start_bundle()

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
    authorization, installed, issue, phases = _start_bundle()
    manager = _StartManager("ref-rejected")
    writer = NoReplaceReceiptSet()
    result = StartPermitOwner(
        authorization=authorization,
        installed_acceptance=installed,
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
    authorization, installed, issue, phases = _start_bundle()
    manager = _StartManager(outcome)
    writer = NoReplaceReceiptSet()

    result = StartPermitOwner(
        authorization=authorization,
        installed_acceptance=installed,
        phase_receipts=phases,
        issue=issue,
        manager=manager,
        reacquire_prestart=_reacquire_prestart,
        writer=writer,
    ).dispatch()

    assert result.state is StartDispatchState.UNKNOWN
    assert writer.write_order == ("START_ISSUED", "START_DISPATCH_UNKNOWN")


def test_start_manager_identity_mismatch_refuses_before_issue() -> None:
    authorization, installed, issue, phases = _start_bundle()
    manager = _StartManager("returned")
    manager.owner = ":1.99"
    writer = NoReplaceReceiptSet()

    with pytest.raises(StartPermitError, match="differs before issue"):
        StartPermitOwner(
            authorization=authorization,
            installed_acceptance=installed,
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
    authorization, installed, issue, phases = _start_bundle()
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
    authorization, installed, issue, phases = _start_bundle()
    manager = _StartManager("returned")
    writer = NoReplaceReceiptSet()
    unprivileged = StartPermitOwner(
        authorization=authorization,
        installed_acceptance=installed,
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
