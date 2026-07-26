from __future__ import annotations

import ast
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import types
from email.parser import Parser
from email.policy import strict as strict_email_policy

import pytest

import scion.problems.warehouse_delivery.w3_environment_receipts as receipts_module
import scion.problems.warehouse_delivery.w3_wheel as w3_wheel_module

# The semantic receipt module has no native dependency, but importing the
# execution package initializes its public spawn exports.  Keep this source-only
# test portable across supported Python versions by installing the same inert
# ABI surface used by the execution unit-test fixture.
_native_extension = types.ModuleType("scion.runtime.native._spawn_into_cgroup")


class _NativeBlockedChild:
    pass


def _native_not_configured(*_args: object, **_kwargs: object) -> object:
    raise AssertionError("native spawn was not configured by this test")


_native_constants: dict[str, object] = {
    "CHILD_EXEC_ERROR_FD": 198,
    "CHILD_RELEASE_FD": 199,
    "CHILD_STDERR_FD": 197,
    "CHILD_STDIN_FD": 195,
    "CHILD_STDOUT_FD": 196,
    "CLONE_ARGS_SIZE": 88,
    "CLONE_FLAGS": 0,
    "ERROR_RECORD_MAGIC": b"SCXE",
    "ERROR_RECORD_FORMAT": "<4sBBHI",
    "ERROR_RECORD_SIZE": 12,
    "ERROR_RECORD_VERSION": 1,
    "ERROR_STAGE_CHDIR": 12,
    "ERROR_STAGE_CLOSE_RANGE": 10,
    "ERROR_STAGE_DUP_EXEC_ERROR": 8,
    "ERROR_STAGE_DUP_RELEASE": 9,
    "ERROR_STAGE_DUP_STDERR": 7,
    "ERROR_STAGE_DUP_STDIN": 5,
    "ERROR_STAGE_DUP_STDOUT": 6,
    "ERROR_STAGE_EXECVE": 13,
    "ERROR_STAGE_RELEASE_BYTE": 4,
    "ERROR_STAGE_RELEASE_CLOSE": 3,
    "ERROR_STAGE_RELEASE_READ": 2,
    "ERROR_STAGE_SIGNAL_DISPOSITIONS": 11,
    "ERROR_STAGE_SIGNAL_MASK": 1,
    "EXIT_SIGNAL": 17,
    "RELEASE_BYTE": b"\x01",
    "WAIT_RESULT_FIELDS": (
        "pid",
        "uid",
        "si_code",
        "si_status",
        "wait_status",
        "return_code",
        "signal",
        "core_dumped",
    ),
    "BlockedChild": _NativeBlockedChild,
    "spawn_blocked": _native_not_configured,
}
for _native_name, _native_value in _native_constants.items():
    setattr(_native_extension, _native_name, _native_value)
sys.modules.setdefault(
    "scion.runtime.native._spawn_into_cgroup",
    _native_extension,
)

from scion.problems.warehouse_delivery.w3_environment_receipts import (
    ACCEPTED_ROOT_INSTALLATION_PLAN_SHA256,
    DbusProvenance,
    EnvironmentProbeFact,
    EnvironmentRelocationReceipt,
    FIXED_RUNTIME_PROBE_WHEEL_MEMBERS,
    FilesystemEnvironmentSemanticReader,
    FilesystemLiveEnvironmentReader,
    ImportIdentity,
    InstalledWheelMember,
    LiveEnvironmentRehashFact,
    NativeElfIdentity,
    NamespaceProbeExecutionFact,
    SubprocessEnvironmentProbeReader,
    WarehouseEnvironmentContentReceipt,
    WarehouseEnvironmentEvidence,
    WarehouseW3EnvironmentReceiptError,
    WheelInstallationProvenance,
    acquire_warehouse_environment_content,
    acquire_warehouse_environment_content_for_test,
    discover_environment_external_runtime_paths,
    derive_final_environment_path,
    verify_live_environment,
)
from scion.problems.warehouse_delivery.w3_environment import (
    WHEEL_GENERATED_INSTALLATION_FILES,
    WHEEL_RECORD_MEMBER_PATH,
    canonical_installed_record_bytes,
)
from scion.problems.warehouse_delivery.w3_wheel import (
    ACCEPTED_NATIVE_ELF_SHA256,
    FIXED_REQUIRED_WHEEL_MEMBERS,
    OfflineDoubleWheelReceipt,
    WarehouseW3WheelError,
    WheelMember,
)
from scion.runtime.execution.environment_integrity import EnvironmentContentReceipt

PLAN_SHA = "87c873a22da7e1581ae370bf0a13d86414e1d05ac441754339fcb2efcf027643"
SITE = "lib/python3.12/site-packages"
NATIVE = (
    f"{SITE}/scion/runtime/native/_spawn_into_cgroup.cpython-312-x86_64-linux-gnu.so"
)
NATIVE_MEMBER = (
    "scion/runtime/native/" "_spawn_into_cgroup.cpython-312-x86_64-linux-gnu.so"
)
DBUS_PACKAGE = f"{SITE}/dbus/__init__.py"
DBUS_BINDINGS = f"{SITE}/_dbus_bindings.cpython-312-x86_64-linux-gnu.so"
DBUS_GLIB = f"{SITE}/_dbus_glib_bindings.cpython-312-x86_64-linux-gnu.so"
DBUS_METADATA = f"{SITE}/dbus_python-1.3.2.egg-info/PKG-INFO"
DBUS_METADATA_CONTENTS = (
    "Metadata-Version: 2.1\n" "Name: dbus-python\n" "Version: 1.3.2\n" "\n"
)
WHEEL_INSTALLATION_MANIFEST = ".scion/w3-wheel-installation.json"


def _canonical(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode()


def _hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _wheel_receipt(
    *,
    native_size_bytes: int,
    wheel_sha256: str | None = None,
) -> OfflineDoubleWheelReceipt:
    paths = tuple(
        sorted(
            {
                *FIXED_REQUIRED_WHEEL_MEMBERS,
                *FIXED_RUNTIME_PROBE_WHEEL_MEMBERS,
                NATIVE_MEMBER,
                "scion-0.1.0.dist-info/METADATA",
                "scion-0.1.0.dist-info/WHEEL",
                "scion-0.1.0.dist-info/entry_points.txt",
                "scion-0.1.0.dist-info/top_level.txt",
                "scion-0.1.0.dist-info/RECORD",
            }
        )
    )
    members = tuple(
        WheelMember(
            path=path,
            mode=(0o664 if path == "scion-0.1.0.dist-info/RECORD" else 0o644),
            size_bytes=native_size_bytes if path == NATIVE_MEMBER else len(path),
            compressed_size_bytes=(
                native_size_bytes if path == NATIVE_MEMBER else len(path)
            ),
            crc32=0,
            compression=0,
            sha256=(
                w3_wheel_module.ACCEPTED_NATIVE_ELF_SHA256
                if path == NATIVE_MEMBER
                else _hash(path.encode())
            ),
        )
        for path in paths
    )
    return OfflineDoubleWheelReceipt._for_test(
        source_commit="a" * 40,
        source_tree="b" * 40,
        source_date_epoch=1_725_000_000,
        archive_sha256=("1" * 64, "2" * 64),
        archive_inventory_sha256="3" * 64,
        required_module_members=tuple(
            sorted(
                {
                    *(
                        path
                        for path in FIXED_REQUIRED_WHEEL_MEMBERS
                        if path.endswith(".py")
                    ),
                    *FIXED_RUNTIME_PROBE_WHEEL_MEMBERS,
                }
            )
        ),
        wheel_filename="scion-0.1.0-cp312-cp312-linux_x86_64.whl",
        wheel_size_bytes=100_000,
        wheel_sha256=wheel_sha256 or _hash(b"exact wheel bytes"),
        member_inventory=members,
        native_member_path=NATIVE_MEMBER,
    )


def _wheel_installation(
    wheel: OfflineDoubleWheelReceipt,
    installed_contents: dict[str, bytes],
) -> WheelInstallationProvenance:
    return WheelInstallationProvenance(
        manifest_path=WHEEL_INSTALLATION_MANIFEST,
        wheel_receipt_sha256=wheel.raw_sha256,
        wheel_sha256=wheel.wheel_sha256,
        installed_members=tuple(
            InstalledWheelMember(
                wheel_member_path=member.path,
                environment_path=f"{SITE}/{member.path}",
                sha256=_hash(installed_contents[member.path]),
                size_bytes=len(installed_contents[member.path]),
            )
            for member in wheel.member_inventory
        ),
    )


def _write(root: Path, relative: str, raw: bytes, *, mode: int = 0o444) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    path.chmod(mode)


def _freeze_directories(root: Path) -> None:
    directories = [root, *(path for path in root.rglob("*") if path.is_dir())]
    for path in sorted(directories, key=lambda item: len(item.parts), reverse=True):
        path.chmod(0o555)


@pytest.fixture
def semantic_inputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
) -> dict[str, object]:
    environment = tmp_path / "staging-environment"
    environment.mkdir()
    native_source = (
        Path(__file__).parents[5]
        / "build"
        / "lib.linux-x86_64-cpython-312"
        / "scion"
        / "runtime"
        / "native"
        / "_spawn_into_cgroup.cpython-312-x86_64-linux-gnu.so"
    )
    native_raw = native_source.read_bytes()
    monkeypatch.setattr(
        w3_wheel_module,
        "ACCEPTED_NATIVE_ELF_SHA256",
        _hash(native_raw),
    )
    wheel = _wheel_receipt(native_size_bytes=len(native_raw))
    installed_contents = {
        member.path: (
            native_raw if member.path == NATIVE_MEMBER else member.path.encode()
        )
        for member in wheel.member_inventory
    }
    installed_record_inputs = {
        path: (_hash(raw), len(raw)) for path, raw in installed_contents.items()
    }
    installed_record_inputs.update(
        {
            path: (_hash(raw), len(raw))
            for path, raw in WHEEL_GENERATED_INSTALLATION_FILES.items()
        }
    )
    installed_contents[WHEEL_RECORD_MEMBER_PATH] = canonical_installed_record_bytes(
        tuple(item.path for item in wheel.member_inventory),
        installed_record_inputs,
    )
    wheel_installation = _wheel_installation(wheel, installed_contents)
    content = {
        DBUS_PACKAGE: b"DBUS = 'copied'\n",
        DBUS_BINDINGS: native_raw,
        DBUS_GLIB: native_raw,
        DBUS_METADATA: DBUS_METADATA_CONTENTS.encode(),
        NATIVE: native_raw,
        **{f"{SITE}/{path}": raw for path, raw in installed_contents.items()},
        **{
            f"{SITE}/{path}": raw
            for path, raw in WHEEL_GENERATED_INSTALLATION_FILES.items()
        },
        WHEEL_INSTALLATION_MANIFEST: wheel_installation.manifest_bytes(),
    }
    python_target = environment / "bin" / "python"
    python_target.parent.mkdir(parents=True)
    shutil.copy2(sys.executable, python_target)
    python_target.chmod(0o555)
    for path, raw in content.items():
        _write(environment, path, raw)
    _freeze_directories(environment)

    external = tmp_path / "external" / "libdbus-1.so.3"
    external.parent.mkdir()
    external.write_bytes(native_raw)
    external.chmod(0o444)
    candidate = tmp_path / "candidate"
    selection = tmp_path / ".scion-w3-selections" / ("a" * 64)
    selection.mkdir(parents=True)
    generic = EnvironmentContentReceipt.create(
        environment,
        external_runtime_paths=(external,),
        candidate_root=candidate,
        selection_root=selection,
    )
    by_path = {
        item.path: item
        for item in generic.environment_inventory
        if item.kind == "regular"
    }
    external_entry = generic.external_runtime[0]
    native = NativeElfIdentity(
        environment_path=NATIVE,
        sha256=by_path[NATIVE].sha256 or "",
        size_bytes=by_path[NATIVE].size_bytes,
    )
    required_imports = tuple(
        ImportIdentity(
            subject=(
                ".".join(Path(member).parent.parts)
                if member.endswith("/__init__.py")
                else ".".join(Path(member[:-3]).parts)
            ),
            kind="python",
            scope="environment",
            path=f"{SITE}/{member}",
            sha256=by_path[f"{SITE}/{member}"].sha256 or "",
            size_bytes=by_path[f"{SITE}/{member}"].size_bytes,
        )
        for member in wheel.required_module_members
    )
    imports = tuple(
        sorted(
            (
                *required_imports,
                ImportIdentity(
                    subject="_dbus_bindings",
                    kind="native_extension",
                    scope="environment",
                    path=DBUS_BINDINGS,
                    sha256=by_path[DBUS_BINDINGS].sha256 or "",
                    size_bytes=by_path[DBUS_BINDINGS].size_bytes,
                ),
                ImportIdentity(
                    subject="_dbus_glib_bindings",
                    kind="native_extension",
                    scope="environment",
                    path=DBUS_GLIB,
                    sha256=by_path[DBUS_GLIB].sha256 or "",
                    size_bytes=by_path[DBUS_GLIB].size_bytes,
                ),
                ImportIdentity(
                    subject="dbus",
                    kind="python",
                    scope="environment",
                    path=DBUS_PACKAGE,
                    sha256=by_path[DBUS_PACKAGE].sha256 or "",
                    size_bytes=by_path[DBUS_PACKAGE].size_bytes,
                ),
                ImportIdentity(
                    subject="libdbus",
                    kind="shared_library",
                    scope="external_runtime",
                    path=external_entry.path,
                    sha256=external_entry.sha256,
                    size_bytes=external_entry.size_bytes,
                ),
                ImportIdentity(
                    subject="scion.runtime.native._spawn_into_cgroup",
                    kind="native_extension",
                    scope="environment",
                    path=NATIVE,
                    sha256=by_path[NATIVE].sha256 or "",
                    size_bytes=by_path[NATIVE].size_bytes,
                ),
                ImportIdentity(
                    subject="sys.executable",
                    kind="executable",
                    scope="environment",
                    path="bin/python",
                    sha256=by_path["bin/python"].sha256 or "",
                    size_bytes=by_path["bin/python"].size_bytes,
                ),
            ),
            key=lambda item: (item.subject.encode(), item.path.encode()),
        )
    )
    evidence = WarehouseEnvironmentEvidence(
        native_elf=native,
        wheel_installation=wheel_installation,
        import_table=imports,
        dbus_provenance=DbusProvenance(
            package_version="1.3.2",
            package_metadata_path=DBUS_METADATA,
            package_metadata_contents=DBUS_METADATA_CONTENTS,
            package_subject="dbus",
            bindings_subject="_dbus_bindings",
            glib_bindings_subject="_dbus_glib_bindings",
            shared_library_paths=(str(external),),
        ),
    )

    def restore() -> None:
        for path in sorted(
            (item for item in tmp_path.rglob("*") if item.is_dir()),
            key=lambda item: len(item.parts),
        ):
            path.chmod(0o755)
        for path in tmp_path.rglob("*"):
            if path.is_file():
                path.chmod(0o644)

    request.addfinalizer(restore)
    return {
        "tmp_path": tmp_path,
        "environment": environment,
        "external": external,
        "candidate": candidate,
        "selection": selection,
        "generic": generic,
        "wheel": wheel,
        "evidence": evidence,
    }


class _SemanticReader:
    def __init__(
        self,
        evidence: WarehouseEnvironmentEvidence,
        *,
        second: WarehouseEnvironmentEvidence | None = None,
    ) -> None:
        self.evidence = evidence
        self.second = second
        self.calls: list[Path] = []

    def read(
        self,
        environment_root: Path,
        *,
        generic_receipt: EnvironmentContentReceipt,
        wheel_receipt: OfflineDoubleWheelReceipt,
    ) -> WarehouseEnvironmentEvidence:
        assert type(generic_receipt) is EnvironmentContentReceipt
        assert type(wheel_receipt) is OfflineDoubleWheelReceipt
        self.calls.append(environment_root)
        return (
            self.evidence
            if len(self.calls) == 1 or self.second is None
            else self.second
        )


def _semantic(
    values: dict[str, object],
    *,
    wheel: OfflineDoubleWheelReceipt | None = None,
) -> WarehouseEnvironmentContentReceipt:
    selected_wheel = values["wheel"] if wheel is None else wheel
    return acquire_warehouse_environment_content_for_test(
        values["environment"],
        generic_receipt=values["generic"],
        wheel_receipt=selected_wheel,
        reader=_SemanticReader(values["evidence"]),
    )


def _rewrite_installed_wheel_member(
    values: dict[str, object],
    *,
    wheel_member_path: str,
    raw: bytes,
) -> tuple[
    EnvironmentContentReceipt,
    WarehouseEnvironmentEvidence,
    WheelInstallationProvenance,
]:
    environment = values["environment"]
    evidence = values["evidence"]
    target = environment / SITE / wheel_member_path
    target.chmod(0o644)
    target.write_bytes(raw)
    target.chmod(0o444)
    installed_members = tuple(
        (
            InstalledWheelMember(
                wheel_member_path=item.wheel_member_path,
                environment_path=item.environment_path,
                sha256=_hash(raw),
                size_bytes=len(raw),
            )
            if item.wheel_member_path == wheel_member_path
            else item
        )
        for item in evidence.wheel_installation.installed_members
    )
    provenance = WheelInstallationProvenance(
        manifest_path=WHEEL_INSTALLATION_MANIFEST,
        wheel_receipt_sha256=evidence.wheel_installation.wheel_receipt_sha256,
        wheel_sha256=evidence.wheel_installation.wheel_sha256,
        installed_members=installed_members,
    )
    manifest = environment / WHEEL_INSTALLATION_MANIFEST
    manifest.chmod(0o644)
    manifest.write_bytes(provenance.manifest_bytes())
    manifest.chmod(0o444)
    generic = EnvironmentContentReceipt.create(
        environment,
        external_runtime_paths=(values["external"],),
        candidate_root=values["candidate"],
        selection_root=values["selection"],
    )
    rewritten_evidence = WarehouseEnvironmentEvidence(
        native_elf=evidence.native_elf,
        wheel_installation=provenance,
        import_table=evidence.import_table,
        dbus_provenance=evidence.dbus_provenance,
    )
    return generic, rewritten_evidence, provenance


def test_semantic_receipt_canonically_binds_all_problem_owned_evidence(
    semantic_inputs: dict[str, object],
) -> None:
    reader = _SemanticReader(semantic_inputs["evidence"])
    receipt = acquire_warehouse_environment_content_for_test(
        semantic_inputs["environment"],
        generic_receipt=semantic_inputs["generic"],
        wheel_receipt=semantic_inputs["wheel"],
        reader=reader,
    )

    assert reader.calls == [
        semantic_inputs["environment"],
        semantic_inputs["environment"],
    ]
    assert receipt.generic_receipt_sha256 == semantic_inputs["generic"].raw_sha256
    assert receipt.wheel_receipt_sha256 == semantic_inputs["wheel"].raw_sha256
    assert receipt.wheel_sha256 == semantic_inputs["wheel"].wheel_sha256
    assert receipt.external_runtime_count == 1
    assert str("/var/lib/scion/environments/w3/").encode() not in receipt.raw
    assert (
        WarehouseEnvironmentContentReceipt.from_bytes(
            receipt.raw,
            generic_receipt=semantic_inputs["generic"],
            wheel_receipt=semantic_inputs["wheel"],
        )
        == receipt
    )
    assert OfflineDoubleWheelReceipt.from_bytes(semantic_inputs["wheel"].raw) == (
        semantic_inputs["wheel"]
    )
    assert ACCEPTED_ROOT_INSTALLATION_PLAN_SHA256 == PLAN_SHA


def test_semantic_receipt_binds_canonical_installed_record_rewrite(
    semantic_inputs: dict[str, object],
) -> None:
    record_member = "scion-0.1.0.dist-info/RECORD"
    receipt = WarehouseEnvironmentContentReceipt.create(
        semantic_inputs["generic"],
        semantic_inputs["wheel"],
        semantic_inputs["evidence"],
    )

    assert (
        receipts_module._read_wheel_installation_provenance(
            semantic_inputs["environment"],
            semantic_inputs["generic"],
        )
        == semantic_inputs["evidence"].wheel_installation
    )
    installed_record = next(
        item
        for item in receipt.evidence.wheel_installation.installed_members
        if item.wheel_member_path == record_member
    )
    wheel_record = next(
        item
        for item in semantic_inputs["wheel"].member_inventory
        if item.path == record_member
    )
    assert installed_record.sha256 != wheel_record.sha256


def test_semantic_receipt_rejects_arbitrary_installed_record_rewrite(
    semantic_inputs: dict[str, object],
) -> None:
    generic, evidence, _provenance = _rewrite_installed_wheel_member(
        semantic_inputs,
        wheel_member_path=WHEEL_RECORD_MEMBER_PATH,
        raw=b"arbitrary installed RECORD\n",
    )

    with pytest.raises(
        WarehouseW3EnvironmentReceiptError,
        match="installed RECORD is not the canonical wheel transformation",
    ):
        WarehouseEnvironmentContentReceipt.create(
            generic,
            semantic_inputs["wheel"],
            evidence,
        )


def test_semantic_receipt_rejects_other_installed_wheel_rewrite(
    semantic_inputs: dict[str, object],
) -> None:
    generic, evidence, _provenance = _rewrite_installed_wheel_member(
        semantic_inputs,
        wheel_member_path="scion-0.1.0.dist-info/METADATA",
        raw=b"rewritten immutable metadata\n",
    )

    with pytest.raises(
        WarehouseW3EnvironmentReceiptError,
        match="immutable wheel member is not installed byte-for-byte",
    ):
        WarehouseEnvironmentContentReceipt.create(
            generic,
            semantic_inputs["wheel"],
            evidence,
        )


def test_semantic_receipt_rejects_mixed_wheel_import_and_external_evidence(
    semantic_inputs: dict[str, object],
    tmp_path: Path,
) -> None:
    wheel = semantic_inputs["wheel"]
    mixed_wheel = _wheel_receipt(
        native_size_bytes=next(
            member.size_bytes
            for member in wheel.member_inventory
            if member.path == wheel.native_member_path
        ),
        wheel_sha256="f" * 64,
    )
    receipt = _semantic(semantic_inputs)
    with pytest.raises(
        WarehouseW3EnvironmentReceiptError,
        match="another double-wheel receipt",
    ):
        WarehouseEnvironmentContentReceipt.from_bytes(
            receipt.raw,
            generic_receipt=semantic_inputs["generic"],
            wheel_receipt=mixed_wheel,
        )
    with pytest.raises(
        WarehouseW3EnvironmentReceiptError,
        match="another double-wheel receipt",
    ):
        _semantic(semantic_inputs, wheel=mixed_wheel)

    imports = list(semantic_inputs["evidence"].import_table)
    target = next(item for item in imports if item.subject == "dbus")
    imports[imports.index(target)] = ImportIdentity(
        subject=target.subject,
        kind=target.kind,
        scope=target.scope,
        path=target.path,
        sha256="e" * 64,
        size_bytes=target.size_bytes,
    )
    imports.sort(key=lambda item: (item.subject.encode(), item.path.encode()))
    mixed_imports = WarehouseEnvironmentEvidence(
        native_elf=semantic_inputs["evidence"].native_elf,
        wheel_installation=semantic_inputs["evidence"].wheel_installation,
        import_table=tuple(imports),
        dbus_provenance=semantic_inputs["evidence"].dbus_provenance,
    )
    with pytest.raises(
        WarehouseW3EnvironmentReceiptError,
        match="not bound by generic content",
    ):
        WarehouseEnvironmentContentReceipt.create(
            semantic_inputs["generic"],
            semantic_inputs["wheel"],
            mixed_imports,
        )

    other_external = tmp_path / "other-runtime.so"
    other_external.write_bytes(b"other runtime\n")
    other_external.chmod(0o444)
    other_generic = EnvironmentContentReceipt.create(
        semantic_inputs["environment"],
        external_runtime_paths=(other_external,),
        candidate_root=semantic_inputs["candidate"],
        selection_root=semantic_inputs["selection"],
    )
    with pytest.raises(
        WarehouseW3EnvironmentReceiptError,
        match="not installed byte-for-byte|not bound by generic content|does not close",
    ):
        WarehouseEnvironmentContentReceipt.create(
            other_generic,
            semantic_inputs["wheel"],
            semantic_inputs["evidence"],
        )


@pytest.mark.parametrize(
    "omitted",
    (
        "scion/problems/warehouse_delivery/w3_analysis.py",
        "scion/problems/warehouse_delivery/w3_composition.py",
        "scion/problems/warehouse_delivery/w3_start_gate.py",
        "scion/tools/scion_w3_tool.py",
    ),
)
def test_semantic_receipt_requires_runtime_probe_closure_in_target_interpreter(
    semantic_inputs: dict[str, object],
    omitted: str,
) -> None:
    evidence = semantic_inputs["evidence"]
    omitted_path = f"{SITE}/{omitted}"
    incomplete = WarehouseEnvironmentEvidence(
        native_elf=evidence.native_elf,
        wheel_installation=evidence.wheel_installation,
        import_table=tuple(
            item for item in evidence.import_table if item.path != omitted_path
        ),
        dbus_provenance=evidence.dbus_provenance,
    )
    with pytest.raises(
        WarehouseW3EnvironmentReceiptError,
        match="target interpreter omitted one required wheel module",
    ):
        WarehouseEnvironmentContentReceipt.create(
            semantic_inputs["generic"],
            semantic_inputs["wheel"],
            incomplete,
        )


def test_semantic_receipt_does_not_force_preparation_module_import(
    semantic_inputs: dict[str, object],
) -> None:
    evidence = semantic_inputs["evidence"]
    preparation_member = "scion/problems/warehouse_delivery/w3_candidate_coordinator.py"
    preparation_path = f"{SITE}/{preparation_member}"
    reduced = WarehouseEnvironmentEvidence(
        native_elf=evidence.native_elf,
        wheel_installation=evidence.wheel_installation,
        import_table=tuple(
            item for item in evidence.import_table if item.path != preparation_path
        ),
        dbus_provenance=evidence.dbus_provenance,
    )

    receipt = WarehouseEnvironmentContentReceipt.create(
        semantic_inputs["generic"],
        semantic_inputs["wheel"],
        reduced,
    )

    assert preparation_path not in {item.path for item in receipt.evidence.import_table}
    assert preparation_member not in FIXED_RUNTIME_PROBE_WHEEL_MEMBERS
    assert {
        "scion/problems/warehouse_delivery/w3_analysis.py",
        "scion/problems/warehouse_delivery/w3_composition.py",
        "scion/problems/warehouse_delivery/w3_start_gate.py",
        "scion/problems/warehouse_delivery/w3_start_store.py",
        "scion/runtime/execution/invocation_terminal.py",
        "scion/tools/scion_w3_tool.py",
    }.issubset(FIXED_RUNTIME_PROBE_WHEEL_MEMBERS)


def test_semantic_reader_drift_is_fail_closed(
    semantic_inputs: dict[str, object],
) -> None:
    evidence = semantic_inputs["evidence"]
    imports = list(evidence.import_table)
    imports[0], imports[1] = imports[1], imports[0]
    with pytest.raises(
        WarehouseW3EnvironmentReceiptError,
        match="unique, and byte-sorted",
    ):
        WarehouseEnvironmentEvidence(
            native_elf=evidence.native_elf,
            wheel_installation=evidence.wheel_installation,
            import_table=tuple(imports),
            dbus_provenance=evidence.dbus_provenance,
        )

    other = WarehouseEnvironmentEvidence(
        native_elf=evidence.native_elf,
        wheel_installation=evidence.wheel_installation,
        import_table=evidence.import_table,
        dbus_provenance=DbusProvenance(
            package_version="1.3.3",
            package_metadata_path=DBUS_METADATA.replace("1.3.2", "1.3.3"),
            package_metadata_contents=DBUS_METADATA_CONTENTS.replace(
                "Version: 1.3.2",
                "Version: 1.3.3",
            ),
            package_subject="dbus",
            bindings_subject="_dbus_bindings",
            glib_bindings_subject="_dbus_glib_bindings",
            shared_library_paths=evidence.dbus_provenance.shared_library_paths,
        ),
    )
    with pytest.raises(
        WarehouseW3EnvironmentReceiptError,
        match="changed while acquired",
    ):
        acquire_warehouse_environment_content_for_test(
            semantic_inputs["environment"],
            generic_receipt=semantic_inputs["generic"],
            wheel_receipt=semantic_inputs["wheel"],
            reader=_SemanticReader(evidence, second=other),
        )

    with pytest.raises(TypeError, match="exact FilesystemEnvironmentSemanticReader"):
        acquire_warehouse_environment_content(
            semantic_inputs["environment"],
            generic_receipt=semantic_inputs["generic"],
            wheel_receipt=semantic_inputs["wheel"],
            reader=_SemanticReader(evidence),
        )


def test_semantic_receipt_v3_binds_copied_debian_dbus_metadata(
    semantic_inputs: dict[str, object],
) -> None:
    receipt = WarehouseEnvironmentContentReceipt.create(
        semantic_inputs["generic"],
        semantic_inputs["wheel"],
        semantic_inputs["evidence"],
    )

    assert json.loads(receipt.raw)["schema"] == (
        "scion.w3-environment-semantic-content.v3"
    )
    assert receipt.evidence.dbus_provenance.package_metadata_path == DBUS_METADATA


def test_dbus_provenance_rejects_synthetic_wheel_metadata_layout() -> None:
    with pytest.raises(
        WarehouseW3EnvironmentReceiptError,
        match="metadata path differs",
    ):
        DbusProvenance(
            package_version="1.3.2",
            package_metadata_path=(f"{SITE}/dbus_python-1.3.2.dist-info/METADATA"),
            package_metadata_contents=DBUS_METADATA_CONTENTS,
            package_subject="dbus",
            bindings_subject="_dbus_bindings",
            glib_bindings_subject="_dbus_glib_bindings",
            shared_library_paths=("/usr/lib/libdbus-1.so.3",),
        )


def test_strict_dbus_metadata_headers_project_to_exact_text() -> None:
    metadata = Parser(policy=strict_email_policy).parsestr(
        DBUS_METADATA_CONTENTS,
        headersonly=True,
    )
    raw_version = metadata.get_all("Version", failobj=[])[0]

    assert type(raw_version) is not str
    assert receipts_module._metadata_header_texts(
        metadata,
        "Version",
        field="test D-Bus version",
        maximum=128,
    ) == ("1.3.2",)


def test_production_readers_and_discovery_surface_are_fixed() -> None:
    with pytest.raises(TypeError, match="final"):

        class _SemanticSubclass(FilesystemEnvironmentSemanticReader):
            pass

    with pytest.raises(TypeError, match="final"):

        class _ProbeSubclass(SubprocessEnvironmentProbeReader):
            pass

    with pytest.raises(TypeError, match="exact SubprocessEnvironmentProbeReader"):
        FilesystemEnvironmentSemanticReader(object())  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="unexpected keyword argument"):
        discover_environment_external_runtime_paths(
            Path("/fixed/environment"),
            reader=object(),  # type: ignore[call-arg]
        )


def test_discovery_runs_only_the_fixed_local_read_only_probe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    environment = tmp_path / "environment"
    external_python = tmp_path / "runtime" / "json.py"
    external_library = tmp_path / "runtime" / "libdbus-1.so.3"
    external_python.parent.mkdir(parents=True)
    external_python.write_bytes(b"external Python bytes\n")
    external_library.write_bytes(b"\x7fELFexternal library bytes")
    observation = _canonical(
        {
            "schema": "scion.w3-environment-runtime-observation.v2",
            "sys_executable": str(environment / "bin" / "python"),
            "sys_prefix": str(environment),
            "sys_path": [str(environment / SITE)],
            "module_files": [
                {
                    "subject": "dbus",
                    "path": str(environment / DBUS_PACKAGE),
                },
                {"subject": "json", "path": str(external_python)},
            ],
            "mapped_shared_libraries": [str(external_library)],
            "dbus_acquired": True,
            "dbus_unique_name": ":1.91",
            "effective_uid": os.geteuid(),
            "effective_gid": os.getegid(),
            "no_new_privs": 0,
            "network_namespace": "net:[1]",
            "mount_namespace": "mnt:[2]",
        }
    )
    calls: list[tuple[tuple[str, ...], dict[str, str]]] = []

    def fixed_run(
        argv: tuple[str, ...],
        *,
        cwd: Path,
        env: dict[str, str],
        stdin: object,
        stdout: object,
        stderr: object,
        check: bool,
        timeout: int,
    ) -> subprocess.CompletedProcess[bytes]:
        del cwd, stdin, stdout, stderr, check, timeout
        calls.append((argv, env))
        return subprocess.CompletedProcess(argv, 0, observation, b"")

    monkeypatch.setattr(subprocess, "run", fixed_run)
    assert discover_environment_external_runtime_paths(environment) == (
        external_python,
        external_library,
    )
    assert len(calls) == 1
    argv, environment_variables = calls[0]
    assert argv[:4] == (
        str(environment / "bin" / "python"),
        "-I",
        "-B",
        "-c",
    )
    assert environment_variables["DBUS_SYSTEM_BUS_ADDRESS"] == (
        "unix:path=/run/dbus/system_bus_socket"
    )
    assert not {
        key
        for key in environment_variables
        if "PROXY" in key or key in {"SSH_AUTH_SOCK", "PYTHONPATH"}
    }


def test_stable_fake_dbus_version_is_rejected_by_installed_metadata(
    semantic_inputs: dict[str, object],
) -> None:
    evidence = semantic_inputs["evidence"]
    fake_metadata = DBUS_METADATA_CONTENTS.replace(
        "Version: 1.3.2",
        "Version: 9.9.9",
    )
    forged = WarehouseEnvironmentEvidence(
        native_elf=evidence.native_elf,
        wheel_installation=evidence.wheel_installation,
        import_table=evidence.import_table,
        dbus_provenance=DbusProvenance(
            package_version="9.9.9",
            package_metadata_path=DBUS_METADATA.replace("1.3.2", "9.9.9"),
            package_metadata_contents=fake_metadata,
            package_subject="dbus",
            bindings_subject="_dbus_bindings",
            glib_bindings_subject="_dbus_glib_bindings",
            shared_library_paths=evidence.dbus_provenance.shared_library_paths,
        ),
    )
    with pytest.raises(
        WarehouseW3EnvironmentReceiptError,
        match="D-Bus package and native bindings",
    ):
        WarehouseEnvironmentContentReceipt.create(
            semantic_inputs["generic"],
            semantic_inputs["wheel"],
            forged,
        )


def test_dbus_shared_library_provenance_must_equal_complete_shared_imports(
    semantic_inputs: dict[str, object],
) -> None:
    evidence = semantic_inputs["evidence"]
    generic_value = json.loads(semantic_inputs["generic"].raw)
    extra_path = "/usr/lib/libglib-2.0.so.0"
    extra_sha = _hash(b"exact external glib")
    generic_value["external_runtime"].append(
        {
            "path": extra_path,
            "device": 7,
            "inode": 8,
            "size_bytes": 19,
            "sha256": extra_sha,
        }
    )
    generic_value["external_runtime"].sort(key=lambda item: item["path"].encode())
    generic = EnvironmentContentReceipt.from_bytes(_canonical(generic_value))
    imports = tuple(
        sorted(
            (
                *evidence.import_table,
                ImportIdentity(
                    subject="libglib",
                    kind="shared_library",
                    scope="external_runtime",
                    path=extra_path,
                    sha256=extra_sha,
                    size_bytes=19,
                ),
            ),
            key=lambda item: (item.subject.encode(), item.path.encode()),
        )
    )
    incomplete = WarehouseEnvironmentEvidence(
        native_elf=evidence.native_elf,
        wheel_installation=evidence.wheel_installation,
        import_table=imports,
        dbus_provenance=evidence.dbus_provenance,
    )
    with pytest.raises(
        WarehouseW3EnvironmentReceiptError,
        match="does not close the import table",
    ):
        WarehouseEnvironmentContentReceipt.create(
            generic,
            semantic_inputs["wheel"],
            incomplete,
        )


def test_canonical_parsers_reject_unknown_duplicate_and_retry_fields(
    semantic_inputs: dict[str, object],
) -> None:
    wheel = semantic_inputs["wheel"]
    changed = json.loads(wheel.raw)
    changed["retry"] = True
    with pytest.raises(
        WarehouseW3WheelError,
        match="fixed authority",
    ):
        OfflineDoubleWheelReceipt.from_bytes(_canonical(changed))

    semantic = _semantic(semantic_inputs)
    unknown = json.loads(semantic.raw)
    unknown["unknown"] = 1
    with pytest.raises(
        WarehouseW3EnvironmentReceiptError,
        match="fields differ",
    ):
        WarehouseEnvironmentContentReceipt.from_bytes(
            _canonical(unknown),
            generic_receipt=semantic_inputs["generic"],
            wheel_receipt=wheel,
        )

    duplicate = semantic.raw.replace(
        b'{"dbus_provenance":',
        b'{"dbus_provenance":{},"dbus_provenance":',
        1,
    )
    with pytest.raises(
        WarehouseW3EnvironmentReceiptError,
        match="duplicate",
    ):
        WarehouseEnvironmentContentReceipt.from_bytes(
            duplicate,
            generic_receipt=semantic_inputs["generic"],
            wheel_receipt=wheel,
        )


def _loaded_paths(
    root: Path,
    content: WarehouseEnvironmentContentReceipt,
    kind: str,
) -> tuple[Path, ...]:
    return tuple(
        sorted(
            (
                root / item.path if item.scope == "environment" else Path(item.path)
                for item in content.evidence.import_table
                if item.kind == kind
            ),
            key=lambda item: str(item).encode(),
        )
    )


class _ProbeReader:
    def __init__(
        self,
        *,
        wrong_final_root: bool = False,
        outside_sys_path: bool = False,
        mismatched_final_sys_path: bool = False,
        broad_usr_sys_path: bool = False,
        wrong_common_argv: bool = False,
    ) -> None:
        self.wrong_final_root = wrong_final_root
        self.outside_sys_path = outside_sys_path
        self.mismatched_final_sys_path = mismatched_final_sys_path
        self.broad_usr_sys_path = broad_usr_sys_path
        self.wrong_common_argv = wrong_common_argv
        self.calls: list[tuple[Path, str]] = []

    def probe(
        self,
        environment_root: Path,
        *,
        phase: str,
        content_receipt: WarehouseEnvironmentContentReceipt,
    ) -> EnvironmentProbeFact:
        self.calls.append((environment_root, phase))
        root = (
            Path("/wrong/final/environment")
            if self.wrong_final_root and phase == "namespace_final"
            else environment_root
        )
        sys_path = (
            Path("/usr")
            if self.broad_usr_sys_path
            else (
                Path("/unbound/python-path")
                if self.outside_sys_path
                else (
                    root / "lib" / "python3.12"
                    if self.mismatched_final_sys_path and phase == "namespace_final"
                    else root / SITE
                )
            )
        )
        return EnvironmentProbeFact.create(
            phase=phase,
            content_receipt_sha256=content_receipt.raw_sha256,
            environment_root=root,
            sys_executable=root / "bin" / "python",
            sys_prefix=root,
            sys_path=(sys_path,),
            import_table_sha256=content_receipt.import_table_sha256,
            loaded_import_table=content_receipt.evidence.import_table,
            native_loaded_paths=_loaded_paths(
                root,
                content_receipt,
                "native_extension",
            ),
            shared_library_paths=_loaded_paths(
                root,
                content_receipt,
                "shared_library",
            ),
            dbus_acquired=True,
            dbus_unique_name=":1.42",
            dispatcher_argv=(
                str(root / "bin" / "python"),
                "-m",
                (
                    "scion.tools.wrong_but_phase_stable"
                    if self.wrong_common_argv
                    else "scion.tools.scion_w3_tool"
                ),
                "run",
            ),
        )


class _ExpectedOnlyLiveReader:
    def __init__(self) -> None:
        self.calls: list[tuple[Path, str]] = []

    def rehash(
        self,
        environment_root: Path,
        *,
        phase: str,
        content_receipt: WarehouseEnvironmentContentReceipt,
        generic_receipt: EnvironmentContentReceipt,
    ) -> LiveEnvironmentRehashFact:
        assert generic_receipt == content_receipt.generic_receipt
        self.calls.append((environment_root, phase))
        return LiveEnvironmentRehashFact._from_observed(
            phase=phase,
            environment_root=environment_root,
            content_receipt=content_receipt,
            observed_generic_receipt=content_receipt.generic_receipt,
        )


def _relocation_inputs(
    semantic_inputs: dict[str, object],
    content: WarehouseEnvironmentContentReceipt,
) -> tuple[Path, Path]:
    candidate = semantic_inputs["tmp_path"] / "candidate" / "environment"
    simulated = (
        semantic_inputs["tmp_path"]
        / "simulated-root"
        / "var"
        / "lib"
        / "scion"
        / "environments"
        / "w3"
        / content.generic_receipt_sha256
    )
    return candidate, simulated


def _relocation_receipt(
    content: WarehouseEnvironmentContentReceipt,
    candidate: Path,
    simulated: Path,
    *,
    probe_reader: _ProbeReader | None = None,
    observed_generic: EnvironmentContentReceipt | None = None,
) -> EnvironmentRelocationReceipt:
    reader = _ProbeReader() if probe_reader is None else probe_reader
    final = derive_final_environment_path(content)
    candidate_fact = reader.probe(
        candidate,
        phase="candidate",
        content_receipt=content,
    )
    namespace_fact = reader.probe(
        final,
        phase="namespace_final",
        content_receipt=content,
    )
    namespace_execution = NamespaceProbeExecutionFact.create(
        physical_environment_root=simulated,
        visible_environment_root=final,
        environment_probe=namespace_fact,
        producer_euid=1000,
        producer_egid=1000,
        no_new_privs=True,
        parent_network_namespace="net:[1]",
        child_network_namespace="net:[2]",
        parent_mount_namespace="mnt:[3]",
        child_mount_namespace="mnt:[4]",
        bwrap_sha256="a" * 64,
        bwrap_device=1,
        bwrap_inode=2,
        bwrap_size_bytes=3,
        bwrap_mode=0o755,
    )
    observed = content.generic_receipt if observed_generic is None else observed_generic
    imported_root = candidate.parent / "imported" / "environment"
    imported = LiveEnvironmentRehashFact._from_observed(
        phase="imported_candidate",
        environment_root=imported_root,
        content_receipt=content,
        observed_generic_receipt=observed,
    )
    pre = LiveEnvironmentRehashFact._from_observed(
        phase="relocation_pre",
        environment_root=final,
        content_receipt=content,
        observed_generic_receipt=observed,
    )
    post = LiveEnvironmentRehashFact._from_observed(
        phase="relocation_post",
        environment_root=final,
        content_receipt=content,
        observed_generic_receipt=observed,
    )
    return EnvironmentRelocationReceipt.create(
        content,
        candidate_probe=candidate_fact,
        namespace_final_probe=namespace_fact,
        namespace_probe_execution=namespace_execution,
        imported_candidate_rehash=imported,
        relocation_pre_rehash=pre,
        relocation_post_rehash=post,
    )


def test_relocation_owner_derives_final_path_and_binds_all_probe_rehash_facts(
    semantic_inputs: dict[str, object],
) -> None:
    content = _semantic(semantic_inputs)
    candidate, simulated = _relocation_inputs(semantic_inputs, content)
    probe = _ProbeReader()
    receipt = _relocation_receipt(content, candidate, simulated, probe_reader=probe)
    final = Path("/var/lib/scion/environments/w3") / content.generic_receipt_sha256

    assert content.raw_sha256 != content.generic_receipt_sha256
    assert derive_final_environment_path(content) == final
    assert receipt.final_environment_path == str(final)
    assert probe.calls == [
        (candidate, "candidate"),
        (final, "namespace_final"),
    ]
    assert receipt.relocation_pre_rehash.environment_root == str(final)
    assert receipt.relocation_post_rehash.environment_root == str(final)
    assert (
        EnvironmentRelocationReceipt.from_bytes(
            receipt.raw,
            content_receipt=content,
        )
        == receipt
    )


def test_relocation_rejects_wrong_final_and_simulated_paths(
    semantic_inputs: dict[str, object],
) -> None:
    content = _semantic(semantic_inputs)
    candidate, simulated = _relocation_inputs(semantic_inputs, content)
    with pytest.raises(
        WarehouseW3EnvironmentReceiptError,
        match="namespace probe execution boundary",
    ):
        _relocation_receipt(
            content,
            candidate,
            simulated,
            probe_reader=_ProbeReader(wrong_final_root=True),
        )

    with pytest.raises(
        WarehouseW3EnvironmentReceiptError,
        match="exact import-root closure",
    ):
        _relocation_receipt(
            content,
            candidate,
            simulated,
            probe_reader=_ProbeReader(outside_sys_path=True),
        )

    with pytest.raises(
        WarehouseW3EnvironmentReceiptError,
        match="exact import-root closure",
    ):
        _relocation_receipt(
            content,
            candidate,
            simulated,
            probe_reader=_ProbeReader(broad_usr_sys_path=True),
        )

    with pytest.raises(
        WarehouseW3EnvironmentReceiptError,
        match="dispatcher argv or interpreter identity differs",
    ):
        _relocation_receipt(
            content,
            candidate,
            simulated,
            probe_reader=_ProbeReader(wrong_common_argv=True),
        )

    with pytest.raises(
        WarehouseW3EnvironmentReceiptError,
        match="exact import-root closure",
    ):
        _relocation_receipt(
            content,
            candidate,
            simulated,
            probe_reader=_ProbeReader(mismatched_final_sys_path=True),
        )

    with pytest.raises(
        WarehouseW3EnvironmentReceiptError,
        match="namespace probe execution boundary",
    ):
        _relocation_receipt(
            content,
            candidate,
            derive_final_environment_path(content),
        )


def test_relocation_rejects_replay_against_another_semantic_content(
    semantic_inputs: dict[str, object],
) -> None:
    first = _semantic(semantic_inputs)
    candidate, simulated = _relocation_inputs(semantic_inputs, first)
    relocation = _relocation_receipt(first, candidate, simulated)
    evidence = semantic_inputs["evidence"]
    external = next(
        item for item in evidence.import_table if item.scope == "external_runtime"
    )
    second_imports = tuple(
        sorted(
            (
                *(
                    item
                    for item in evidence.import_table
                    if item.scope != "external_runtime"
                ),
                ImportIdentity(
                    subject="libdbus-replay",
                    kind=external.kind,
                    scope=external.scope,
                    path=external.path,
                    sha256=external.sha256,
                    size_bytes=external.size_bytes,
                ),
            ),
            key=lambda item: (item.subject.encode(), item.path.encode()),
        )
    )
    second = WarehouseEnvironmentContentReceipt.create(
        semantic_inputs["generic"],
        semantic_inputs["wheel"],
        WarehouseEnvironmentEvidence(
            native_elf=evidence.native_elf,
            wheel_installation=evidence.wheel_installation,
            import_table=second_imports,
            dbus_provenance=evidence.dbus_provenance,
        ),
    )

    with pytest.raises(
        WarehouseW3EnvironmentReceiptError,
        match="content or path binding differs",
    ):
        EnvironmentRelocationReceipt.from_bytes(
            relocation.raw,
            content_receipt=second,
        )


def test_relocation_rejects_mixed_live_rehash_evidence(
    semantic_inputs: dict[str, object],
) -> None:
    content = _semantic(semantic_inputs)
    candidate, simulated = _relocation_inputs(semantic_inputs, content)
    other_generic_value = json.loads(content.generic_receipt.raw)
    other_generic_value["external_runtime"][0]["sha256"] = "c" * 64
    other_generic = EnvironmentContentReceipt.from_bytes(
        _canonical(other_generic_value)
    )

    with pytest.raises(
        WarehouseW3EnvironmentReceiptError,
        match="live environment rehash is not cross-bound",
    ):
        _relocation_receipt(
            content,
            candidate,
            simulated,
            observed_generic=other_generic,
        )


def test_runtime_live_rehash_interface_is_exact_for_preclaim_and_completion(
    semantic_inputs: dict[str, object],
) -> None:
    content = _semantic(semantic_inputs)
    fake = _ExpectedOnlyLiveReader()
    assert not hasattr(LiveEnvironmentRehashFact, "create")
    with pytest.raises(TypeError, match="exact FilesystemLiveEnvironmentReader"):
        verify_live_environment(
            content,
            phase="preclaim",
            live_reader=fake,
        )
    assert fake.calls == []
    with pytest.raises(
        WarehouseW3EnvironmentReceiptError,
        match="phase differs",
    ):
        verify_live_environment(
            content,
            phase="relocation_pre",
            live_reader=fake,
        )

    real = FilesystemLiveEnvironmentReader(
        external_runtime_paths=(semantic_inputs["external"],),
        candidate_root=semantic_inputs["candidate"],
        selection_root=semantic_inputs["selection"],
    )
    fact = real.rehash(
        semantic_inputs["environment"],
        phase="preclaim",
        content_receipt=content,
        generic_receipt=content.generic_receipt,
    )
    assert fact.observed_generic_receipt == content.generic_receipt

    if os.geteuid() == 0:
        with pytest.raises(PermissionError, match="rejects effective UID zero"):
            SubprocessEnvironmentProbeReader()


def test_module_is_problem_owned_and_has_no_mutation_capability() -> None:
    source_path = (
        Path(__file__).parents[4]
        / "problems"
        / "warehouse_delivery"
        / "w3_environment_receipts.py"
    )
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    calls = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    named_calls = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }

    assert "dbus" not in imports
    assert "ctypes" not in imports
    forbidden_calls = {
        "write",
        "write_bytes",
        "write_text",
        "rename",
        "replace",
        "mount",
        "unlink",
        "rmdir",
        "mkdir",
        "chmod",
        "chown",
    }
    assert not forbidden_calls.intersection(calls)
    assert not forbidden_calls.intersection(named_calls)
    assert "open" not in named_calls
    assert "O_WRONLY" not in source
    assert "O_CREAT" not in source
    assert "run" in calls
    assert "FilesystemEnvironmentSemanticReader" in source
    assert "SubprocessEnvironmentProbeReader" in source
    assert "from scion.problems.warehouse_delivery.w3_installation import" not in source
    assert "import scion.problems.warehouse_delivery.w3_installation" not in source
