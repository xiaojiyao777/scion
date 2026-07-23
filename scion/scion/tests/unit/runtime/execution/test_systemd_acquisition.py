from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import scion.runtime.execution.systemd_acquisition as systemd_acquisition
from scion.runtime.execution.systemd_acquisition import (
    ConfiguredPairReadback,
    Systemd255Acquirer,
    SystemdAcquisitionError,
    SystemdDbusPropertyReader,
    SystemdManagerIdentityFact,
    parse_unit_template,
)

RUN = "scion-w3@fixture.service"
CLOSE = "scion-w3-close@fixture.service"
INVOCATION = "1" * 32
BOOT = "00000000-0000-0000-0000-000000000001"
VERSION = "255.4-1ubuntu8.16"
CONTROL_GROUP = f"/system.slice/{RUN}"
PYTHON = "/var/lib/scion/projections/w3/fixture/environment/bin/python"
TOOL = "/var/lib/scion/projections/w3/fixture/" "sealed/bin/scion-w3-tool"
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
READ_ONLY = (
    "/var/lib/scion/projections/w3/fixture/installation.json "
    "/var/lib/scion/projections/w3/fixture/authority.json "
    "/var/lib/scion/projections/w3/fixture/sealed "
    "/var/lib/scion/projections/w3/fixture/environment"
)
READ_WRITE = (
    "/var/lib/scion/projections/w3/fixture/run "
    "/var/lib/scion/projections/w3/fixture/nonce-claims"
)
RUN_START = f"{PYTHON} -B -s {TOOL} run fixture"
RUN_STOP = f"{PYTHON} -B -s {TOOL} seal-unit-drained fixture"
CLOSE_START = f"{PYTHON} -B -s {TOOL} close fixture"
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
    "ReadOnlyPaths": READ_ONLY,
    "ReadWritePaths": READ_WRITE,
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
    "ReadOnlyPaths": READ_ONLY,
    "ReadWritePaths": READ_WRITE,
}


def _structured(command: str, *, code: int = 0) -> tuple[object, ...]:
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
        code,
        0,
    )


class _Reader:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[str, ...]]] = []
        self.values: dict[str, dict[str, object]] = {
            RUN: {
                "Id": RUN,
                "Type": "exec",
                "User": "clawd",
                "Group": "clawd",
                "UMask": 0o077,
                "ExecStart": [_structured(RUN_START)],
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
                "ReadOnlyPaths": READ_ONLY.split(" "),
                "ReadWritePaths": READ_WRITE.split(" "),
                "Delegate": True,
                "DelegateControllers": ["pids"],
                "DelegateSubgroup": "supervisor",
                "CollectMode": "inactive",
                "Restart": "no",
                "KillMode": "control-group",
                "TimeoutStopUSec": (1 << 64) - 1,
                "OnSuccess": [CLOSE],
                "OnFailure": [CLOSE],
                "InvocationID": list(bytes.fromhex(INVOCATION)),
                "ControlGroup": CONTROL_GROUP,
                "MainPID": 4242,
                "LoadState": "loaded",
                "ActiveState": "inactive",
                "SubState": "dead",
                "Result": "success",
                "ExecMainCode": 1,
                "ExecMainStatus": 0,
                "ExecStopPost": [_structured(RUN_STOP, code=1)],
            },
            CLOSE: {
                "Id": CLOSE,
                "Type": "oneshot",
                "User": "clawd",
                "Group": "clawd",
                "UMask": 0o077,
                "ExecStart": [_structured(CLOSE_START)],
                "NoNewPrivileges": True,
                "PrivateTmp": True,
                "ProtectSystem": "strict",
                "ProtectHome": "read-only",
                "ReadOnlyPaths": READ_ONLY.split(" "),
                "ReadWritePaths": READ_WRITE.split(" "),
                "CollectMode": "inactive",
                "Restart": "no",
                "TimeoutStartUSec": (1 << 64) - 1,
                "After": [RUN],
            },
        }

    def read_properties(
        self,
        unit: str,
        names: tuple[str, ...],
    ) -> dict[str, object]:
        self.calls.append((unit, names))
        return {name: self.values[unit][name] for name in names}


class _IdentityReader(_Reader):
    def __init__(
        self,
        events: list[tuple[str, ...]],
        *,
        owners: tuple[str, ...] = (":1.42", ":1.42"),
        version: str = VERSION,
    ) -> None:
        super().__init__()
        self.events = events
        self.owners = list(owners)
        self.version = version

    def get_unique_owner(self) -> str:
        self.events.append(("owner",))
        if not self.owners:
            raise AssertionError("unexpected owner read")
        return self.owners.pop(0)

    def get_manager_version(self, expected_owner: str) -> str:
        self.events.append(("version", expected_owner))
        return self.version


def _proc_stat(pid: int, starttime: int) -> bytes:
    after_name = ["S"] + ["1"] * 18 + [str(starttime)]
    return f"{pid} (scion fixture) {' '.join(after_name)}\n".encode("ascii")


def _filesystem(tmp_path: Path) -> tuple[Path, Path, Path]:
    proc = tmp_path / "proc"
    cgroup = tmp_path / "cgroup"
    boot = proc / "sys" / "kernel" / "random" / "boot_id"
    process = proc / "4242"
    service = cgroup / "system.slice" / RUN
    supervisor = service / "supervisor"
    process.mkdir(parents=True)
    supervisor.mkdir(parents=True)
    boot.parent.mkdir(parents=True)
    boot.write_text(
        f"{BOOT}\n",
        encoding="ascii",
    )
    (process / "stat").write_bytes(_proc_stat(4242, 700))
    (process / "cgroup").write_text(
        f"0::{CONTROL_GROUP}/supervisor\n",
        encoding="ascii",
    )
    return proc, cgroup, boot


def _acquirer(
    tmp_path: Path,
) -> tuple[Systemd255Acquirer, _Reader, Path, Path]:
    proc, cgroup, boot = _filesystem(tmp_path)
    reader = _Reader()
    return (
        Systemd255Acquirer(
            reader,
            proc_root=proc,
            cgroup_root=cgroup,
            boot_id_path=boot,
        ),
        reader,
        proc,
        cgroup,
    )


def test_manager_identity_fact_preserves_full_systemd_version() -> None:
    fact = SystemdManagerIdentityFact(
        unique_owner=":1.42",
        boot_id=BOOT,
        version=VERSION,
    )

    assert fact.unique_owner == ":1.42"
    assert fact.boot_id == BOOT
    assert fact.version == "255.4-1ubuntu8.16"


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (
        ("unique_owner", "org.freedesktop.systemd1", "unique owner"),
        ("unique_owner", ":1", "unique owner"),
        ("unique_owner", "", "unique owner"),
        (
            "boot_id",
            "ABCDEFAB-CDEF-ABCD-EFAB-CDEFABCDEFAB",
            "boot id",
        ),
        ("boot_id", "0" * 32, "boot id"),
        ("version", "", "version"),
        ("version", "254.9", "major version"),
        ("version", "256.1", "major version"),
        ("version", "255\nforged", "control"),
        ("version", "255." + "x" * 253, "exceeds"),
    ),
)
def test_manager_identity_fact_rejects_noncanonical_fields(
    field: str,
    value: str,
    message: str,
) -> None:
    values = {
        "unique_owner": ":1.42",
        "boot_id": BOOT,
        "version": VERSION,
    }
    values[field] = value

    with pytest.raises(SystemdAcquisitionError, match=message):
        SystemdManagerIdentityFact(**values)


def test_manager_identity_acquisition_has_one_stable_owner_batch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proc, cgroup, boot = _filesystem(tmp_path)
    events: list[tuple[str, ...]] = []
    reader = _IdentityReader(events)
    acquirer = Systemd255Acquirer(
        reader,
        proc_root=proc,
        cgroup_root=cgroup,
        boot_id_path=boot,
    )
    real_read = systemd_acquisition._read_regular

    def tracked_read(
        parent_fd: int,
        name: str,
        *,
        maximum: int = 4 * 1024 * 1024,
    ) -> bytes:
        if name == "boot_id":
            events.append(("boot", name))
        return real_read(parent_fd, name, maximum=maximum)

    monkeypatch.setattr(systemd_acquisition, "_read_regular", tracked_read)
    fact = acquirer.acquire_manager_identity()

    assert fact == SystemdManagerIdentityFact(":1.42", BOOT, VERSION)
    assert events == [
        ("owner",),
        ("version", ":1.42"),
        ("boot", "boot_id"),
        ("owner",),
    ]


def test_manager_identity_acquisition_rejects_owner_drift(
    tmp_path: Path,
) -> None:
    proc, cgroup, boot = _filesystem(tmp_path)
    events: list[tuple[str, ...]] = []
    reader = _IdentityReader(
        events,
        owners=(":1.42", ":1.99"),
    )
    acquirer = Systemd255Acquirer(
        reader,
        proc_root=proc,
        cgroup_root=cgroup,
        boot_id_path=boot,
    )

    with pytest.raises(SystemdAcquisitionError, match="unique owner changed"):
        acquirer.acquire_manager_identity()
    assert events == [
        ("owner",),
        ("version", ":1.42"),
        ("owner",),
    ]


def test_manager_identity_rejects_noncanonical_boot_bytes(
    tmp_path: Path,
) -> None:
    proc, cgroup, boot = _filesystem(tmp_path)
    boot.write_text(f" {BOOT}\n", encoding="ascii")
    reader = _IdentityReader([])
    acquirer = Systemd255Acquirer(
        reader,
        proc_root=proc,
        cgroup_root=cgroup,
        boot_id_path=boot,
    )

    with pytest.raises(SystemdAcquisitionError, match="boot id"):
        acquirer.acquire_manager_identity()


def test_manager_identity_reads_linux_zero_size_boot_pseudofile() -> None:
    boot = Path("/proc/sys/kernel/random/boot_id")
    if not boot.exists() or boot.stat().st_size != 0:
        pytest.skip("Linux zero-size boot-id pseudo-file is unavailable")
    events: list[tuple[str, ...]] = []
    reader = _IdentityReader(events)
    fact = Systemd255Acquirer(reader).acquire_manager_identity()

    assert fact.unique_owner == ":1.42"
    assert fact.version == VERSION
    assert len(fact.boot_id) == 36


def test_property_only_reader_cannot_acquire_manager_identity(
    tmp_path: Path,
) -> None:
    acquirer, reader, _proc, _cgroup = _acquirer(tmp_path)

    with pytest.raises(TypeError, match="lacks manager identity"):
        acquirer.acquire_manager_identity()
    assert reader.calls == []


def test_dbus_reader_uses_unique_owner_for_version_and_property_batch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[tuple[object, ...]] = []

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

    class _Daemon:
        def GetNameOwner(self, name: str) -> _String:
            events.append(("owner", name))
            return _String(":1.42")

    class _ManagerObject:
        def __init__(self) -> None:
            self.version: object = _String(VERSION)

        def GetUnit(self, unit: str) -> _String:
            events.append(("get-unit", unit))
            return _String("/org/freedesktop/systemd1/unit/fixture")

        def Get(self, interface: str, name: str) -> object:
            events.append(("get-version", interface, name))
            return self.version

    class _UnitObject:
        def Get(self, interface: str, name: str) -> object:
            events.append(("get-property", interface, name))
            return {
                "Id": _String(RUN),
                "MainPID": _Integer(4242),
            }[name]

    daemon = _Daemon()
    manager = _ManagerObject()
    unit = _UnitObject()

    class _Bus:
        def get_object(self, destination: str, path: str) -> object:
            events.append(("get-object", destination, path))
            if destination == "org.freedesktop.DBus":
                return daemon
            if path == "/org/freedesktop/systemd1":
                return manager
            assert path == "/org/freedesktop/systemd1/unit/fixture"
            return unit

    bus = _Bus()

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

        @staticmethod
        def SystemBus() -> _Bus:
            events.append(("system-bus",))
            return bus

        @staticmethod
        def Interface(value: object, *, dbus_interface: str) -> object:
            events.append(("interface", dbus_interface))
            return value

    monkeypatch.setattr(
        systemd_acquisition.importlib,
        "import_module",
        lambda name: _Dbus if name == "dbus" else None,
    )

    reader = SystemdDbusPropertyReader()
    constructor_events = tuple(events)
    assert not any(
        event[:1] == ("owner",)
        or (event[:1] == ("get-object",) and event[2] == "/org/freedesktop/systemd1")
        for event in constructor_events
    )
    assert reader.get_unique_owner() == ":1.42"
    assert reader.get_manager_version(":1.42") == VERSION
    manager.version = _Integer(255)
    with pytest.raises(SystemdAcquisitionError, match="exact string property"):
        reader.get_manager_version(":1.42")
    manager.version = _String(VERSION)
    assert reader.read_properties(RUN, ("Id", "MainPID")) == {
        "Id": RUN,
        "MainPID": 4242,
    }
    systemd_objects = [
        event
        for event in events
        if event[:1] == ("get-object",) and event[2] != "/org/freedesktop/DBus"
    ]
    assert systemd_objects
    assert all(event[1] == ":1.42" for event in systemd_objects)
    assert not any(event[1] == "org.freedesktop.systemd1" for event in systemd_objects)


def test_dbus_property_batch_rejects_unique_owner_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owners = iter((":1.42", ":1.99"))

    class _String(str):
        pass

    class _Integer(int):
        pass

    class _Daemon:
        def GetNameOwner(self, name: str) -> _String:
            assert name == "org.freedesktop.systemd1"
            return _String(next(owners))

    class _Manager:
        def GetUnit(self, unit: str) -> _String:
            assert unit == RUN
            return _String("/org/freedesktop/systemd1/unit/fixture")

    class _Unit:
        def Get(self, interface: str, name: str) -> _String:
            assert interface == "org.freedesktop.systemd1.Unit"
            assert name == "Id"
            return _String(RUN)

    class _Bus:
        def get_object(self, destination: str, path: str) -> object:
            if destination == "org.freedesktop.DBus":
                return _Daemon()
            assert destination == ":1.42"
            return _Manager() if path == "/org/freedesktop/systemd1" else _Unit()

    class _Dbus:
        Boolean = bool
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
        Struct = tuple
        Array = list

        @staticmethod
        def SystemBus() -> _Bus:
            return _Bus()

        @staticmethod
        def Interface(value: object, *, dbus_interface: str) -> object:
            assert dbus_interface
            return value

    monkeypatch.setattr(
        systemd_acquisition.importlib,
        "import_module",
        lambda name: _Dbus if name == "dbus" else None,
    )

    reader = SystemdDbusPropertyReader()
    with pytest.raises(SystemdAcquisitionError, match="unique owner changed"):
        reader.read_properties(RUN, ("Id",))


def test_systemd_acquisition_source_has_no_manager_mutation_surface() -> None:
    source = Path(systemd_acquisition.__file__).read_text(encoding="utf-8")

    for forbidden in (
        "StartUnit",
        "StopUnit",
        "RestartUnit",
        "Reload",
        "LoadUnit",
        "RefUnit",
        "UnrefUnit",
        "subprocess",
        "sudo",
    ):
        assert forbidden not in source


def test_configured_pair_uses_fixed_read_only_property_sets(
    tmp_path: Path,
) -> None:
    acquirer, reader, _proc, _cgroup = _acquirer(tmp_path)
    fact = acquirer.acquire_configured_pair(
        run_unit=RUN,
        close_unit=CLOSE,
        run_directives=RUN_DIRECTIVES,
        close_directives=CLOSE_DIRECTIVES,
        run_wiring=RUN_WIRING,
        close_wiring=CLOSE_WIRING,
    )

    assert fact.run.unit == RUN
    assert fact.closer.unit == CLOSE
    assert len(fact.configured_pair_sha256) == 64
    assert reader.calls == [
        (
            RUN,
            (
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
            ),
        ),
        (
            CLOSE,
            (
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
            ),
        ),
    ]
    assert not hasattr(acquirer, "start_unit")
    assert not hasattr(acquirer, "stop_unit")


def test_configured_pair_readback_is_canonical_and_reopenable(
    tmp_path: Path,
) -> None:
    acquirer, reader, _proc, _cgroup = _acquirer(tmp_path)
    acquisition = acquirer.acquire_configured_pair_readback(
        run_unit=RUN,
        close_unit=CLOSE,
        run_directives=RUN_DIRECTIVES,
        close_directives=CLOSE_DIRECTIVES,
        run_wiring=RUN_WIRING,
        close_wiring=CLOSE_WIRING,
    )

    decoded = json.loads(acquisition.raw)
    assert decoded["schema"] == "scion.systemd255-configured-pair-readback.v1"
    assert decoded["run_unit"] == RUN
    assert decoded["close_unit"] == CLOSE
    expected_run = {
        name: reader.values[RUN][name] for name in decoded["run_properties"]
    }
    expected_close = {
        name: reader.values[CLOSE][name] for name in decoded["close_properties"]
    }
    assert decoded["run_properties"] == json.loads(json.dumps(expected_run))
    assert decoded["close_properties"] == json.loads(json.dumps(expected_close))
    assert (
        decoded["configured_pair_sha256"]
        == acquisition.configured_pair.configured_pair_sha256
    )
    assert acquisition.raw_sha256 == hashlib.sha256(acquisition.raw).hexdigest()
    assert tuple(dict(acquisition.run_properties)) != ()
    assert (
        ConfiguredPairReadback.from_bytes(
            acquisition.raw,
            expected_run_wiring=RUN_WIRING,
            expected_close_wiring=CLOSE_WIRING,
        )
        == acquisition
    )
    with pytest.raises(TypeError, match="parsed from exact bytes"):
        ConfiguredPairReadback()
    with pytest.raises(TypeError, match="final"):
        type("Derived", (type(acquisition),), {})


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("run_unit", CLOSE),
        ("close_unit", RUN),
        ("configured_pair_sha256", "0" * 64),
    ),
)
def test_configured_pair_readback_rejects_identity_drift(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    acquirer, _reader, _proc, _cgroup = _acquirer(tmp_path)
    acquisition = acquirer.acquire_configured_pair_readback(
        run_unit=RUN,
        close_unit=CLOSE,
        run_directives=RUN_DIRECTIVES,
        close_directives=CLOSE_DIRECTIVES,
        run_wiring=RUN_WIRING,
        close_wiring=CLOSE_WIRING,
    )
    decoded = json.loads(acquisition.raw)
    decoded[field] = value

    with pytest.raises(SystemdAcquisitionError):
        ConfiguredPairReadback.from_bytes(
            (
                json.dumps(decoded, sort_keys=True, separators=(",", ":")) + "\n"
            ).encode(),
            expected_run_wiring=RUN_WIRING,
            expected_close_wiring=CLOSE_WIRING,
        )


def test_configured_pair_readback_rejects_noncanonical_bytes(
    tmp_path: Path,
) -> None:
    acquirer, _reader, _proc, _cgroup = _acquirer(tmp_path)
    acquisition = acquirer.acquire_configured_pair_readback(
        run_unit=RUN,
        close_unit=CLOSE,
        run_directives=RUN_DIRECTIVES,
        close_directives=CLOSE_DIRECTIVES,
        run_wiring=RUN_WIRING,
        close_wiring=CLOSE_WIRING,
    )

    with pytest.raises(SystemdAcquisitionError, match="not canonical"):
        ConfiguredPairReadback.from_bytes(
            acquisition.raw.rstrip(b"\n"),
            expected_run_wiring=RUN_WIRING,
            expected_close_wiring=CLOSE_WIRING,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("Type", "notify"),
        ("ExecStart", "not-a-dbus-command"),
        ("UMask", -1),
    ),
)
def test_configured_pair_readback_rejects_raw_wiring_drift(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    acquirer, _reader, _proc, _cgroup = _acquirer(tmp_path)
    acquisition = acquirer.acquire_configured_pair_readback(
        run_unit=RUN,
        close_unit=CLOSE,
        run_directives=RUN_DIRECTIVES,
        close_directives=CLOSE_DIRECTIVES,
        run_wiring=RUN_WIRING,
        close_wiring=CLOSE_WIRING,
    )
    decoded = json.loads(acquisition.raw)
    decoded["run_properties"][field] = value
    raw = (json.dumps(decoded, sort_keys=True, separators=(",", ":")) + "\n").encode()

    with pytest.raises(SystemdAcquisitionError):
        ConfiguredPairReadback.from_bytes(
            raw,
            expected_run_wiring=RUN_WIRING,
            expected_close_wiring=CLOSE_WIRING,
        )


def test_configured_pair_rejects_manager_or_directive_drift(
    tmp_path: Path,
) -> None:
    acquirer, reader, _proc, _cgroup = _acquirer(tmp_path)
    reader.values[RUN]["Delegate"] = False
    with pytest.raises(SystemdAcquisitionError, match="pair differs"):
        acquirer.acquire_configured_pair(
            run_unit=RUN,
            close_unit=CLOSE,
            run_directives=RUN_DIRECTIVES,
            close_directives=CLOSE_DIRECTIVES,
            run_wiring=RUN_WIRING,
            close_wiring=CLOSE_WIRING,
        )

    altered = dict(RUN_DIRECTIVES)
    altered["Unknown"] = "yes"
    with pytest.raises(SystemdAcquisitionError, match="inventory differs"):
        acquirer.acquire_configured_pair(
            run_unit=RUN,
            close_unit=CLOSE,
            run_directives=altered,
            close_directives=CLOSE_DIRECTIVES,
            run_wiring=RUN_WIRING,
            close_wiring=CLOSE_WIRING,
        )


def test_configured_pair_rejects_loaded_exec_and_path_wiring_drift(
    tmp_path: Path,
) -> None:
    acquirer, reader, _proc, _cgroup = _acquirer(tmp_path)
    reader.values[RUN]["ExecStopPost"] = [_structured(CLOSE_START, code=1)]
    with pytest.raises(
        SystemdAcquisitionError,
        match="loaded run/closer wiring",
    ):
        acquirer.acquire_configured_pair(
            run_unit=RUN,
            close_unit=CLOSE,
            run_directives=RUN_DIRECTIVES,
            close_directives=CLOSE_DIRECTIVES,
            run_wiring=RUN_WIRING,
            close_wiring=CLOSE_WIRING,
        )

    reader.values[RUN]["ExecStopPost"] = [_structured(RUN_STOP, code=1)]
    reader.values[CLOSE]["ReadWritePaths"] = ["/var/lib/scion"]
    with pytest.raises(
        SystemdAcquisitionError,
        match="loaded run/closer wiring",
    ):
        acquirer.acquire_configured_pair(
            run_unit=RUN,
            close_unit=CLOSE,
            run_directives=RUN_DIRECTIVES,
            close_directives=CLOSE_DIRECTIVES,
            run_wiring=RUN_WIRING,
            close_wiring=CLOSE_WIRING,
        )


def test_lineage_and_stop_post_topology_are_descriptor_bound(
    tmp_path: Path,
) -> None:
    acquirer, _reader, proc, cgroup = _acquirer(tmp_path)
    lineage = acquirer.acquire_self_lineage(
        expected_unit=RUN,
        expected_invocation_id=INVOCATION,
        expected_main_pid=4242,
    )
    assert lineage.main_starttime == 700
    assert lineage.control_group == CONTROL_GROUP

    environment = acquirer.acquire_stop_post_environment(
        {
            "INVOCATION_ID": INVOCATION,
            "SERVICE_RESULT": "success",
            "EXIT_CODE": "exited",
            "EXIT_STATUS": "0",
        }
    )
    service = cgroup / "system.slice" / RUN
    control = service / ".control"
    control.mkdir()
    for directory, content in (
        (service, b""),
        (service / "supervisor", b""),
        (control, b"4242\n"),
    ):
        (directory / "cgroup.procs").write_bytes(content)
    (proc / "4242" / "cgroup").write_text(
        f"0::{CONTROL_GROUP}/.control\n",
        encoding="ascii",
    )

    topology = acquirer.acquire_stop_post_topology(
        lineage=lineage,
        environment=environment,
        sealer_pid=4242,
    )
    assert topology.control_pids == (4242,)
    assert topology.supervisor_pids == ()
    assert topology.job_cgroups == ()


def test_manager_invocation_id_byte_array_is_normalized(
    tmp_path: Path,
) -> None:
    acquirer, reader, _proc, _cgroup = _acquirer(tmp_path)
    reader.values[RUN]["InvocationID"] = list(bytes.fromhex(INVOCATION))

    lineage = acquirer.acquire_self_lineage(
        expected_unit=RUN,
        expected_invocation_id=INVOCATION,
        expected_main_pid=4242,
    )

    assert lineage.invocation_id == INVOCATION


def test_empty_manager_invocation_id_is_not_active_lineage(
    tmp_path: Path,
) -> None:
    acquirer, reader, _proc, _cgroup = _acquirer(tmp_path)
    reader.values[RUN]["InvocationID"] = [0] * 16

    with pytest.raises(SystemdAcquisitionError, match="empty manager invocation"):
        acquirer.acquire_self_lineage(
            expected_unit=RUN,
            expected_invocation_id="0" * 32,
            expected_main_pid=4242,
        )


@pytest.mark.parametrize(
    "value",
    (
        INVOCATION,
        [1] * 15,
        [1] * 15 + [256],
        [1] * 15 + [True],
    ),
)
def test_manager_invocation_id_rejects_malformed_byte_array(
    tmp_path: Path,
    value: object,
) -> None:
    acquirer, reader, _proc, _cgroup = _acquirer(tmp_path)
    reader.values[RUN]["InvocationID"] = value

    with pytest.raises(SystemdAcquisitionError, match="manager invocation id"):
        acquirer.acquire_self_lineage(
            expected_unit=RUN,
            expected_invocation_id=INVOCATION,
            expected_main_pid=4242,
        )


def test_stop_post_topology_rejects_residual_job_cgroup(
    tmp_path: Path,
) -> None:
    acquirer, _reader, proc, cgroup = _acquirer(tmp_path)
    lineage = acquirer.acquire_self_lineage(
        expected_unit=RUN,
        expected_invocation_id=INVOCATION,
        expected_main_pid=4242,
    )
    environment = acquirer.acquire_stop_post_environment(
        {
            "INVOCATION_ID": INVOCATION,
            "SERVICE_RESULT": "success",
            "EXIT_CODE": "exited",
            "EXIT_STATUS": "0",
        }
    )
    service = cgroup / "system.slice" / RUN
    control = service / ".control"
    control.mkdir()
    (service / "job-0-aaaaaaaaaaaaaaaa").mkdir()
    for directory, content in (
        (service, b""),
        (service / "supervisor", b""),
        (control, b"4242\n"),
    ):
        (directory / "cgroup.procs").write_bytes(content)
    (proc / "4242" / "cgroup").write_text(
        f"0::{CONTROL_GROUP}/.control\n",
        encoding="ascii",
    )

    with pytest.raises(SystemdAcquisitionError, match="topology differs"):
        acquirer.acquire_stop_post_topology(
            lineage=lineage,
            environment=environment,
            sealer_pid=4242,
        )


def test_final_acquisition_retains_structured_exec_stop_post(
    tmp_path: Path,
) -> None:
    acquirer, reader, _proc, _cgroup = _acquirer(tmp_path)
    reader.values[RUN]["InvocationID"] = tuple(bytes.fromhex(INVOCATION))
    expected_argv = (
        PYTHON,
        "-B",
        "-s",
        TOOL,
        "seal-unit-drained",
        "fixture",
    )
    final = acquirer.acquire_unit_final(
        expected_unit=RUN,
        expected_invocation_id=INVOCATION,
        expected_exec_path=PYTHON,
        expected_argv=expected_argv,
    )

    assert final.command.argv == expected_argv
    assert final.command.code == 1
    assert final.command.status == 0
    assert final.handoff.exec_stop_post_code == 1
    assert final.handoff.exec_stop_post_status == 0
    assert reader.calls[-1][1][-1] == "ExecStopPost"


@pytest.mark.parametrize("mutation", ("path", "status", "shape"))
def test_final_acquisition_rejects_structured_command_drift(
    tmp_path: Path,
    mutation: str,
) -> None:
    acquirer, reader, _proc, _cgroup = _acquirer(tmp_path)
    command = list(reader.values[RUN]["ExecStopPost"][0])
    if mutation == "path":
        command[0] = "/bin/true"
    elif mutation == "status":
        command[9] = 300
    else:
        command.pop()
    reader.values[RUN]["ExecStopPost"] = [tuple(command)]

    with pytest.raises(SystemdAcquisitionError):
        acquirer.acquire_unit_final(
            expected_unit=RUN,
            expected_invocation_id=INVOCATION,
            expected_exec_path=PYTHON,
            expected_argv=(
                PYTHON,
                "-B",
                "-s",
                TOOL,
                "seal-unit-drained",
                "fixture",
            ),
        )


def test_unit_template_parser_preserves_exact_wiring_and_rejects_duplicates() -> None:
    raw = (
        b"[Unit]\n"
        b"Description=Scion W3 run\n"
        b"\n"
        b"[Service]\n"
        b"Type=oneshot\n"
        b"ExecStart=/projection/%i/python -B -s /projection/%i/tool run %i\n"
        b"ExecStopPost=/projection/%i/python -B -s /projection/%i/tool "
        b"seal-unit-drained %i\n"
        b"Restart=no\n"
    )
    template = parse_unit_template(raw)
    assert template.section("Service")["ExecStart"].endswith("run %i")
    assert template.section("Service")["ExecStopPost"].endswith("seal-unit-drained %i")
    assert len(template.raw_sha256) == 64

    duplicate = raw + b"Restart=no\n"
    with pytest.raises(SystemdAcquisitionError, match="duplicate"):
        parse_unit_template(duplicate)
    with pytest.raises(SystemdAcquisitionError, match="final newline"):
        parse_unit_template(raw[:-1])
