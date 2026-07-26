from __future__ import annotations

import ast
from dataclasses import replace
import hashlib
import json
import zipfile
from pathlib import Path
import sys
import types

import pytest

# Importing the problem composition initializes the execution package.  Keep
# this source-only gate test fail-on-use and portable when the accepted native
# extension is not built in the checkout.
_native_extension = types.ModuleType("scion.runtime.native._spawn_into_cgroup")


class _NativeBlockedChild:
    pass


def _native_not_configured(*_args: object, **_kwargs: object) -> object:
    raise AssertionError("native spawn was not configured by this test")


for _native_name, _native_value in {
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
}.items():
    setattr(_native_extension, _native_name, _native_value)
sys.modules.setdefault(
    "scion.runtime.native._spawn_into_cgroup",
    _native_extension,
)

from scion.problems.warehouse_delivery import w3_candidate_gate as gate_module
from scion.problems.warehouse_delivery.w3_candidate_gate import (
    CandidateAbsenceFacts,
    CandidateAbsenceObservation,
    CandidateCompositionInspection,
    CandidateGateClosureBundle,
    CandidateGateReceipt,
    CandidateNamespaceFinalProbeRef,
    FilesystemCandidateCompositionInspector,
    WarehouseW3CandidateGateError,
    close_candidate_gate,
    close_candidate_gate_closure,
    derive_namespace_probe_evidence_sha256,
)
from scion.problems.warehouse_delivery.w3_composition import (
    EXPECTED_MANIFEST_SHA256,
    EXPECTED_SOURCE_TREE_IDENTITY_SHA256,
    WarehouseW3LaunchReadyFact,
)
from scion.problems.warehouse_delivery.w3_environment_receipts import (
    DbusProvenance,
    EnvironmentProbeFact,
    ImportIdentity,
    InstalledWheelMember,
    NamespaceProbeExecutionFact,
    NativeElfIdentity,
    WarehouseEnvironmentContentReceipt,
    WarehouseEnvironmentEvidence,
    WheelInstallationProvenance,
    derive_final_environment_path,
)
from scion.problems.warehouse_delivery.w3_installation import (
    ACCEPTED_ROOT_INSTALLATION_PLAN_SHA256,
    CandidateRootIdentity,
    CandidateVerificationReceipt,
    PreparedCandidate,
    derive_launch_id,
)
from scion.problems.warehouse_delivery.w3_wheel import (
    ACCEPTED_NATIVE_ELF_SHA256,
    BUILDER_ARGV_TEMPLATE,
    FIXED_REQUIRED_WHEEL_MEMBERS,
    OfflineDoubleWheelArtifact,
    OfflineDoubleWheelReceipt,
    WheelFileIdentity,
    WheelMember,
)
from scion.runtime.execution.environment_integrity import EnvironmentContentReceipt

SITE = "lib/python3.12/site-packages"
DBUS_PACKAGE = f"{SITE}/dbus/__init__.py"
DBUS_BINDINGS = f"{SITE}/_dbus_bindings.cpython-312-x86_64-linux-gnu.so"
DBUS_GLIB = f"{SITE}/_dbus_glib_bindings.cpython-312-x86_64-linux-gnu.so"
DBUS_METADATA = f"{SITE}/dbus_python-1.3.2.egg-info/PKG-INFO"
DBUS_METADATA_CONTENTS = "Metadata-Version: 2.1\nName: dbus-python\nVersion: 1.3.2\n\n"
WHEEL_INSTALLATION_MANIFEST = ".scion/w3-wheel-installation.json"


def test_offline_double_wheel_v4_schema_matches_persisted_paths() -> None:
    receipt = _double_wheel()

    assert json.loads(receipt.raw)["schema"] == "scion.w3-offline-double-wheel.v4"
    assert gate_module.W3_WHEEL_RECEIPT_LOGICAL_PATH == (
        "receipts/offline-double-wheel.v4.json"
    )
    assert gate_module.W3_WHEEL_RECEIPT_SEALED_PATH == (
        "sealed/receipts/offline-double-wheel.v4.json"
    )


_PREPARED_BY_ROOT: dict[str, PreparedCandidate] = {}
_ORIGINAL_INSPECT = FilesystemCandidateCompositionInspector.inspect


@pytest.fixture(autouse=True)
def _fixed_gate_dependencies(monkeypatch: pytest.MonkeyPatch):
    _PREPARED_BY_ROOT.clear()

    def verify_artifact(
        artifact: OfflineDoubleWheelArtifact,
    ) -> OfflineDoubleWheelReceipt:
        assert type(artifact) is OfflineDoubleWheelArtifact
        return artifact.receipt

    def verify_prepared(
        candidate_root: Path,
        *,
        external_runtime_paths: tuple[Path, ...],
    ) -> PreparedCandidate:
        assert external_runtime_paths == (Path("/usr/lib/libdbus-1.so.3"),)
        return _PREPARED_BY_ROOT[str(candidate_root)]

    def inspect(
        _self: FilesystemCandidateCompositionInspector,
        **values: object,
    ) -> tuple[CandidateCompositionInspection, CandidateAbsenceFacts]:
        candidate = values["candidate_verification"]
        wheel = values["double_wheel"]
        semantic = values["semantic_environment"]
        candidate_probe = values["candidate_probe"]
        final_probe = values["namespace_final_probe"]
        relocation = values["namespace_probe_ref"]
        accepted_root = values["accepted_root"]
        nonce = values["nonce"]
        assert type(candidate) is CandidateVerificationReceipt
        assert type(wheel) is OfflineDoubleWheelReceipt
        assert type(semantic) is WarehouseEnvironmentContentReceipt
        assert type(candidate_probe) is EnvironmentProbeFact
        assert type(final_probe) is EnvironmentProbeFact
        assert type(relocation) is CandidateNamespaceFinalProbeRef
        assert isinstance(accepted_root, Path)
        assert type(nonce) is str
        root_identity, inventory_sha, inventory_count = (
            gate_module._readonly_tree_inventory(accepted_root)
        )
        bindings = {
            "candidate_verification_sha256": candidate.raw_sha256,
            "double_wheel_receipt_sha256": wheel.raw_sha256,
            "semantic_environment_receipt_sha256": semantic.raw_sha256,
            "candidate_probe_sha256": candidate_probe.raw_sha256,
            "namespace_final_probe_sha256": final_probe.raw_sha256,
            "namespace_probe_ref_sha256": relocation.raw_sha256,
            "namespace_probe_evidence_sha256": (relocation.evidence_receipt_sha256),
        }
        subjects = gate_module._derived_absence_subjects(
            accepted_root=str(accepted_root),
            launch_id=relocation.launch_id,
            nonce=nonce,
            authority_sha256=candidate.authority_sha256,
            installation_sha256=candidate.installation_sha256,
            environment_receipt_sha256=candidate.environment_receipt_sha256,
        )
        observations = tuple(
            CandidateAbsenceObservation(
                role=role,
                subject=subjects[role],
                observation_sha256=gate_module._absence_observation_sha256(
                    role=role,
                    subject=subjects[role],
                    candidate_verification_sha256=candidate.raw_sha256,
                    double_wheel_receipt_sha256=wheel.raw_sha256,
                    semantic_environment_receipt_sha256=semantic.raw_sha256,
                    namespace_probe_ref_sha256=relocation.raw_sha256,
                ),
                state="ABSENT",
            )
            for role in gate_module._ABSENCE_ROLES
        )
        absence = CandidateAbsenceFacts.create(
            selection_key=candidate.selection_key,
            launch_id=relocation.launch_id,
            nonce=nonce,
            authority_sha256=candidate.authority_sha256,
            installation_sha256=candidate.installation_sha256,
            environment_receipt_sha256=candidate.environment_receipt_sha256,
            accepted_root=accepted_root,
            **bindings,
            observations=observations,
        )
        inspection = CandidateCompositionInspection.create(
            selection_key=candidate.selection_key,
            launch_id=relocation.launch_id,
            nonce=nonce,
            authority_sha256=candidate.authority_sha256,
            installation_sha256=candidate.installation_sha256,
            accepted_root=accepted_root,
            accepted_root_identity=root_identity,
            accepted_root_inventory_sha256=inventory_sha,
            accepted_root_inventory_count=inventory_count,
            **bindings,
            manifest_sha256=EXPECTED_MANIFEST_SHA256,
            source_tree_identity_sha256=EXPECTED_SOURCE_TREE_IDENTITY_SHA256,
            state="COMPOSITION_READY_EXTERNAL_INSTALLATION_REQUIRED",
            external_installation_required=True,
            cell_count=43,
            job_count=172,
            formal_jobs_started=0,
            formal_execution_authorized=False,
            filesystem_mutated=False,
            absence_facts=absence,
        )
        return inspection, absence

    monkeypatch.setattr(
        gate_module,
        "verify_offline_double_wheel_artifact",
        verify_artifact,
    )
    monkeypatch.setattr(gate_module, "verify_candidate", verify_prepared)
    monkeypatch.setattr(
        gate_module,
        "_verify_candidate_wheel_bindings",
        lambda _prepared, _artifact: None,
    )
    monkeypatch.setattr(
        FilesystemCandidateCompositionInspector,
        "inspect",
        inspect,
    )
    yield
    _PREPARED_BY_ROOT.clear()


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode("ascii")).hexdigest()


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


def _candidate(
    *,
    selection_key: str | None = None,
    authority_sha256: str | None = None,
    installation_sha256: str | None = None,
    environment_receipt_sha256: str,
    candidate_root_identity: CandidateRootIdentity,
    candidate_receipt_sha256: str | None = None,
    source_receipt_sha256: str | None = None,
    source_acceptance_sha256: str | None = None,
) -> CandidateVerificationReceipt:
    value = {
        "schema": "scion.w3-candidate-verification.v2",
        "fixed_plan_sha256": ACCEPTED_ROOT_INSTALLATION_PLAN_SHA256,
        "selection_key": selection_key or _sha("selection"),
        "source_acceptance_sha256": (
            source_acceptance_sha256 or _sha("source-acceptance")
        ),
        "candidate_root_identity": candidate_root_identity.to_mapping(),
        "candidate_receipt_sha256": (candidate_receipt_sha256 or _sha("candidate")),
        "content_aggregate_sha256": _sha("content"),
        "source_receipt_sha256": source_receipt_sha256 or _sha("source"),
        "sealed_store_receipt_sha256": _sha("sealed"),
        "environment_receipt_sha256": environment_receipt_sha256,
        "authority_sha256": authority_sha256 or _sha("authority"),
        "installation_sha256": installation_sha256 or _sha("installation"),
        "selection_intent_sha256": _sha("intent"),
        "selection_commit_sha256": _sha("commit"),
        "retry": False,
        "resume": False,
        "reuse": False,
    }
    return CandidateVerificationReceipt.from_bytes(_canonical(value))


def _environment_content(
    wheel: OfflineDoubleWheelReceipt,
) -> EnvironmentContentReceipt:
    wheel_installation = WheelInstallationProvenance(
        manifest_path=WHEEL_INSTALLATION_MANIFEST,
        wheel_receipt_sha256=wheel.raw_sha256,
        wheel_sha256=wheel.wheel_sha256,
        installed_members=tuple(
            InstalledWheelMember(
                wheel_member_path=member.path,
                environment_path=f"{SITE}/{member.path}",
                sha256=member.sha256,
                size_bytes=member.size_bytes,
            )
            for member in wheel.member_inventory
        ),
    )
    files = {
        "bin/python": _sha("python"),
        DBUS_BINDINGS: _sha("bindings"),
        DBUS_PACKAGE: _sha("dbus"),
        DBUS_GLIB: _sha("glib"),
        DBUS_METADATA: hashlib.sha256(DBUS_METADATA_CONTENTS.encode()).hexdigest(),
        WHEEL_INSTALLATION_MANIFEST: hashlib.sha256(
            wheel_installation.manifest_bytes()
        ).hexdigest(),
        **{
            item.environment_path: item.sha256
            for item in wheel_installation.installed_members
        },
    }
    sizes = {
        **{path: 1 for path in files},
        DBUS_METADATA: len(DBUS_METADATA_CONTENTS.encode()),
        WHEEL_INSTALLATION_MANIFEST: len(wheel_installation.manifest_bytes()),
        **{
            item.environment_path: item.size_bytes
            for item in wheel_installation.installed_members
        },
    }
    directories = {"."}
    for path in files:
        parent = Path(path).parent
        while str(parent) != ".":
            directories.add(parent.as_posix())
            parent = parent.parent
    inventory = [
        {
            "path": path,
            "kind": "directory",
            "mode": 0o555,
            "size_bytes": 0,
            "sha256": None,
        }
        for path in directories
    ] + [
        {
            "path": path,
            "kind": "regular",
            "mode": 0o444,
            "size_bytes": sizes[path],
            "sha256": digest,
        }
        for path, digest in files.items()
    ]
    inventory.sort(key=lambda item: item["path"].encode())
    return EnvironmentContentReceipt.from_bytes(
        _canonical(
            {
                "schema": "scion.environment-content.v1",
                "environment_inventory": inventory,
                "external_runtime": [
                    {
                        "path": "/usr/lib/libdbus-1.so.3",
                        "device": 3,
                        "inode": 4,
                        "size_bytes": 1,
                        "sha256": _sha("libdbus"),
                    }
                ],
            }
        )
    )


def _double_wheel() -> OfflineDoubleWheelReceipt:
    native_path = (
        "scion/runtime/native/" "_spawn_into_cgroup.cpython-312-x86_64-linux-gnu.so"
    )
    paths = tuple(
        sorted(
            {
                *FIXED_REQUIRED_WHEEL_MEMBERS,
                native_path,
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
            size_bytes=1,
            compressed_size_bytes=1,
            crc32=1,
            compression=zipfile.ZIP_STORED,
            sha256=(
                ACCEPTED_NATIVE_ELF_SHA256
                if path == native_path
                else _sha(f"member:{path}")
            ),
        )
        for path in paths
    )
    required = tuple(
        sorted(path for path in FIXED_REQUIRED_WHEEL_MEMBERS if path.endswith(".py"))
    )
    return OfflineDoubleWheelReceipt._for_test(
        source_commit="0123456789abcdef0123456789abcdef01234567",
        source_tree="89abcdef0123456789abcdef0123456789abcdef",
        source_date_epoch=1_700_000_000,
        archive_sha256=(_sha("archive-a"), _sha("archive-b")),
        archive_inventory_sha256=_sha("archive-inventory"),
        required_module_members=required,
        wheel_filename="scion-0.4.0-cp312-cp312-linux_x86_64.whl",
        wheel_size_bytes=123,
        wheel_sha256=_sha("wheel"),
        member_inventory=members,
        native_member_path=native_path,
        source_receipt_sha256=_sha("source"),
    )


def _semantic(
    generic: EnvironmentContentReceipt,
    double_wheel: OfflineDoubleWheelReceipt,
) -> WarehouseEnvironmentContentReceipt:
    native_member = next(
        item
        for item in double_wheel.member_inventory
        if item.path == double_wheel.native_member_path
    )
    wheel_installation = WheelInstallationProvenance(
        manifest_path=WHEEL_INSTALLATION_MANIFEST,
        wheel_receipt_sha256=double_wheel.raw_sha256,
        wheel_sha256=double_wheel.wheel_sha256,
        installed_members=tuple(
            InstalledWheelMember(
                wheel_member_path=member.path,
                environment_path=f"{SITE}/{member.path}",
                sha256=member.sha256,
                size_bytes=member.size_bytes,
            )
            for member in double_wheel.member_inventory
        ),
    )
    imports = (
        ImportIdentity(
            "sys.executable",
            "executable",
            "environment",
            "bin/python",
            _sha("python"),
            1,
        ),
        ImportIdentity(
            "_dbus_bindings",
            "native_extension",
            "environment",
            DBUS_BINDINGS,
            _sha("bindings"),
            1,
        ),
        ImportIdentity(
            "_dbus_glib_bindings",
            "native_extension",
            "environment",
            DBUS_GLIB,
            _sha("glib"),
            1,
        ),
        ImportIdentity(
            "dbus",
            "python",
            "environment",
            DBUS_PACKAGE,
            _sha("dbus"),
            1,
        ),
        ImportIdentity(
            "native",
            "native_extension",
            "environment",
            f"{SITE}/{double_wheel.native_member_path}",
            ACCEPTED_NATIVE_ELF_SHA256,
            native_member.size_bytes,
        ),
        ImportIdentity(
            "shared",
            "shared_library",
            "external_runtime",
            "/usr/lib/libdbus-1.so.3",
            _sha("libdbus"),
            1,
        ),
        *(
            ImportIdentity(
                (
                    ".".join(Path(member.path).parent.parts)
                    if member.path.endswith("/__init__.py")
                    else ".".join(Path(member.path[:-3]).parts)
                ),
                "python",
                "environment",
                f"{SITE}/{member.path}",
                member.sha256,
                member.size_bytes,
            )
            for member in double_wheel.member_inventory
            if member.path in double_wheel.required_module_members
        ),
    )
    evidence = WarehouseEnvironmentEvidence(
        native_elf=NativeElfIdentity(
            environment_path=f"{SITE}/{double_wheel.native_member_path}",
            sha256=ACCEPTED_NATIVE_ELF_SHA256,
            size_bytes=native_member.size_bytes,
        ),
        wheel_installation=wheel_installation,
        import_table=tuple(
            sorted(
                imports,
                key=lambda item: (
                    item.subject.encode("utf-8"),
                    item.path.encode("utf-8"),
                ),
            )
        ),
        dbus_provenance=DbusProvenance(
            package_version="1.3.2",
            package_metadata_path=DBUS_METADATA,
            package_metadata_contents=DBUS_METADATA_CONTENTS,
            package_subject="dbus",
            bindings_subject="_dbus_bindings",
            glib_bindings_subject="_dbus_glib_bindings",
            shared_library_paths=("/usr/lib/libdbus-1.so.3",),
        ),
    )
    return WarehouseEnvironmentContentReceipt.create(
        generic,
        double_wheel,
        evidence,
    )


def _probe(
    semantic: WarehouseEnvironmentContentReceipt,
    *,
    phase: str,
    root: Path,
) -> EnvironmentProbeFact:
    native_paths = tuple(
        sorted(
            str(root / item.path)
            for item in semantic.evidence.import_table
            if item.kind == "native_extension"
        )
    )
    return EnvironmentProbeFact.create(
        phase=phase,
        content_receipt_sha256=semantic.raw_sha256,
        environment_root=root,
        sys_executable=root / "bin/python",
        sys_prefix=root,
        sys_path=(root / "lib/python3.12/site-packages",),
        import_table_sha256=semantic.import_table_sha256,
        loaded_import_table=semantic.evidence.import_table,
        native_loaded_paths=tuple(Path(path) for path in native_paths),
        shared_library_paths=(Path("/usr/lib/libdbus-1.so.3"),),
        dbus_acquired=True,
        dbus_unique_name=":1.42",
        dispatcher_argv=(
            str(root / "bin/python"),
            "-m",
            "scion.tools.scion_w3_tool",
            "run",
        ),
    )


def _bundle(tmp_path: Path) -> dict[str, object]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    candidate_root = tmp_path / "candidate"
    accepted_root = tmp_path / "accepted"
    candidate_root.mkdir()
    accepted_root.mkdir()
    marker = accepted_root / "composition.manifest"
    marker.write_bytes(b"read-only accepted composition\n")
    marker.chmod(0o444)
    candidate_root.chmod(0o555)
    accepted_root.chmod(0o555)
    double_wheel = _double_wheel()
    wheel_work = tmp_path / "wheel-work"
    wheel_path = wheel_work / "build-1" / "wheel" / double_wheel.wheel_filename
    double_wheel_artifact = OfflineDoubleWheelArtifact._for_test(
        wheel_path=wheel_path,
        wheel_identity=double_wheel.wheel_identity,
        receipt=double_wheel,
        build_argv=(
            BUILDER_ARGV_TEMPLATE[:8] + (str(wheel_work / "build-1" / "wheel"), "."),
            BUILDER_ARGV_TEMPLATE[:8] + (str(wheel_work / "build-2" / "wheel"), "."),
        ),
    )
    generic = _environment_content(double_wheel)
    candidate = _candidate(
        environment_receipt_sha256=generic.raw_sha256,
        candidate_root_identity=CandidateRootIdentity.capture(candidate_root),
    )
    semantic = _semantic(generic, double_wheel)
    candidate_probe = _probe(
        semantic,
        phase="candidate",
        root=candidate_root / "environment",
    )
    simulated_root = Path(
        f"{tmp_path}/simulated/var/lib/scion/environments/w3/"
        f"{semantic.generic_receipt_sha256}"
    )
    simulated_probe = _probe(
        semantic,
        phase="namespace_final",
        root=derive_final_environment_path(semantic),
    )
    namespace_execution = NamespaceProbeExecutionFact.create(
        physical_environment_root=simulated_root,
        visible_environment_root=derive_final_environment_path(semantic),
        environment_probe=simulated_probe,
        producer_euid=1000,
        producer_egid=1000,
        no_new_privs=True,
        parent_network_namespace="net:[1]",
        child_network_namespace="net:[2]",
        parent_mount_namespace="mnt:[3]",
        child_mount_namespace="mnt:[4]",
        bwrap_sha256=_sha("bwrap"),
        bwrap_device=1,
        bwrap_inode=2,
        bwrap_size_bytes=3,
        bwrap_mode=0o755,
    )
    nonce = _sha("nonce")
    launch_id = derive_launch_id(candidate.authority_sha256, nonce)
    relocation = CandidateNamespaceFinalProbeRef.create(
        evidence_receipt_sha256=derive_namespace_probe_evidence_sha256(
            semantic.raw,
            candidate_probe.raw,
            simulated_probe.raw,
            namespace_execution.raw,
        ),
        selection_key=candidate.selection_key,
        launch_id=launch_id,
        authority_sha256=candidate.authority_sha256,
        installation_sha256=candidate.installation_sha256,
        semantic_environment=semantic,
        candidate_probe=candidate_probe,
        namespace_final_probe=simulated_probe,
        namespace_probe_execution=namespace_execution,
    )
    _PREPARED_BY_ROOT[str(candidate_root)] = PreparedCandidate(
        candidate_root=candidate_root,
        intent=None,  # type: ignore[arg-type]
        selection_commit=None,  # type: ignore[arg-type]
        source_receipt=types.SimpleNamespace(  # type: ignore[arg-type]
            raw_sha256=candidate.source_receipt_sha256
        ),
        sealed_store_receipt=types.SimpleNamespace(  # type: ignore[arg-type]
            inventory=()
        ),
        environment_receipt=generic,
        authority=types.SimpleNamespace(  # type: ignore[arg-type]
            authority_sha256=candidate.authority_sha256,
            nonce=nonce,
            inputs=(),
        ),
        installation=types.SimpleNamespace(  # type: ignore[arg-type]
            installation_sha256=candidate.installation_sha256,
            run_root=str(accepted_root),
        ),
        candidate_receipt=None,  # type: ignore[arg-type]
        verification_receipt=candidate,
    )
    return {
        "candidate_verification": candidate,
        "double_wheel_artifact": double_wheel_artifact,
        "semantic_environment": semantic,
        "environment_content": generic,
        "candidate_probe": candidate_probe,
        "namespace_final_probe": simulated_probe,
        "namespace_probe_execution": namespace_execution,
        "namespace_probe_ref": relocation,
        "candidate_root": candidate_root,
        "accepted_root": accepted_root,
        "nonce": nonce,
        "accepted_manifest_sha256": EXPECTED_MANIFEST_SHA256,
        "inspector": FilesystemCandidateCompositionInspector(),
    }


def _inspect_bundle(
    bundle: dict[str, object],
) -> tuple[CandidateCompositionInspection, CandidateAbsenceFacts]:
    inspector = bundle["inspector"]
    assert type(inspector) is FilesystemCandidateCompositionInspector
    prepared = _PREPARED_BY_ROOT[str(bundle["candidate_root"])]
    artifact = bundle["double_wheel_artifact"]
    assert type(artifact) is OfflineDoubleWheelArtifact
    return inspector.inspect(
        accepted_root=bundle["accepted_root"],
        candidate_root=bundle["candidate_root"],
        nonce=bundle["nonce"],
        manifest_sha256=bundle["accepted_manifest_sha256"],
        prepared_candidate=prepared,
        candidate_verification=bundle["candidate_verification"],
        double_wheel=artifact.receipt,
        semantic_environment=bundle["semantic_environment"],
        candidate_probe=bundle["candidate_probe"],
        namespace_final_probe=bundle["namespace_final_probe"],
        namespace_probe_ref=bundle["namespace_probe_ref"],
    )


def _production_inspector_inputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[dict[str, object], WarehouseW3LaunchReadyFact]:
    accepted_root = tmp_path / "accepted-0700"
    candidate_root = tmp_path / "candidate-sidecars"
    accepted_root.mkdir(mode=0o700)
    candidate_root.mkdir(mode=0o700)
    (candidate_root / "units").mkdir(mode=0o700)
    manifest_raw = _canonical(
        {
            "cells": list(range(43)),
            "jobs": list(range(172)),
            "formal_jobs_started": 0,
            "formal_execution_authorized": False,
        }
    )
    manifest_path = accepted_root / gate_module.EXPECTED_MANIFEST_NAME
    manifest_path.write_bytes(manifest_raw)
    marker = accepted_root / "payload.bin"
    marker.write_bytes(b"stable accepted payload\n")
    manifest_sha = hashlib.sha256(manifest_raw).hexdigest()
    source_tree_sha = _sha("synthetic-source-tree")
    monkeypatch.setattr(gate_module, "EXPECTED_MANIFEST_SHA256", manifest_sha)
    monkeypatch.setattr(
        gate_module,
        "EXPECTED_SOURCE_TREE_IDENTITY_SHA256",
        source_tree_sha,
    )

    authority_raw = b'{"authority":"exact"}\n'
    installation_raw = b'{"installation":"exact"}\n'
    run_raw = b"[Unit]\nDescription=exact run\n"
    close_raw = b"[Unit]\nDescription=exact close\n"
    sidecars = (
        (candidate_root / "authority.json", authority_raw),
        (candidate_root / "installation.json", installation_raw),
        (candidate_root / "units/scion-w3@.service", run_raw),
        (candidate_root / "units/scion-w3-close@.service", close_raw),
    )
    for path, raw in sidecars:
        path.write_bytes(raw)
        path.chmod(0o444)
    candidate_root.chmod(0o555)
    candidate = _candidate(
        environment_receipt_sha256=_sha("environment"),
        candidate_root_identity=CandidateRootIdentity.capture(candidate_root),
    )
    nonce = _sha("production-inspector-nonce")
    launch_id = derive_launch_id(candidate.authority_sha256, nonce)
    authority = types.SimpleNamespace(
        raw=authority_raw,
        authority_sha256=candidate.authority_sha256,
        nonce=nonce,
        inputs=(),
    )
    installation = types.SimpleNamespace(
        raw=installation_raw,
        installation_sha256=candidate.installation_sha256,
        launch_id=launch_id,
        run_root=str(accepted_root),
        authority_path=(
            f"/var/lib/scion/authorities/w3/{candidate.authority_sha256}.json"
        ),
        projection_root=f"/var/lib/scion/projections/w3/{launch_id}",
        sealed_root=(f"/var/lib/scion/sealed/w3/{manifest_sha}"),
        environment_root=(
            "/var/lib/scion/environments/w3/" f"{candidate.environment_receipt_sha256}"
        ),
        terminal_root=f"{accepted_root}/control/invocation",
    )
    prepared = PreparedCandidate(
        candidate_root=candidate_root,
        intent=None,  # type: ignore[arg-type]
        selection_commit=None,  # type: ignore[arg-type]
        source_receipt=types.SimpleNamespace(  # type: ignore[arg-type]
            raw_sha256=candidate.source_receipt_sha256
        ),
        sealed_store_receipt=types.SimpleNamespace(  # type: ignore[arg-type]
            inventory=()
        ),
        environment_receipt=None,  # type: ignore[arg-type]
        authority=authority,  # type: ignore[arg-type]
        installation=installation,  # type: ignore[arg-type]
        candidate_receipt=None,  # type: ignore[arg-type]
        verification_receipt=candidate,
    )
    readiness = WarehouseW3LaunchReadyFact(
        state="COMPOSITION_READY_EXTERNAL_INSTALLATION_REQUIRED",
        authority=authority,  # type: ignore[arg-type]
        installation=installation,  # type: ignore[arg-type]
        run_template=types.SimpleNamespace(),  # type: ignore[arg-type]
        close_template=types.SimpleNamespace(),  # type: ignore[arg-type]
        terminal_policy=types.SimpleNamespace(expected_rows=172),  # type: ignore[arg-type]
        source_tree_identity_sha256=source_tree_sha,
        external_installation_required=True,
        formal_execution_authorized=False,
        filesystem_mutated=False,
        _authority_raw=authority_raw,
        _installation_raw=installation_raw,
        _run_template_raw=run_raw,
        _close_template_raw=close_raw,
        _live_configured_pair=None,
    )
    wheel = _double_wheel()
    values: dict[str, object] = {
        "accepted_root": accepted_root,
        "candidate_root": candidate_root,
        "nonce": nonce,
        "manifest_sha256": manifest_sha,
        "prepared_candidate": prepared,
        "candidate_verification": candidate,
        "double_wheel": wheel,
        "semantic_environment": types.SimpleNamespace(raw_sha256=_sha("semantic")),
        "candidate_probe": types.SimpleNamespace(raw_sha256=_sha("candidate-probe")),
        "namespace_final_probe": types.SimpleNamespace(
            raw_sha256=_sha("simulated-probe")
        ),
        "namespace_probe_ref": types.SimpleNamespace(
            launch_id=launch_id,
            raw_sha256=_sha("relocation"),
            evidence_receipt_sha256=_sha("relocation-evidence"),
        ),
    }
    return values, readiness


def test_production_inspector_calls_fixed_readiness_and_accepts_stable_0700_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    values, readiness = _production_inspector_inputs(tmp_path, monkeypatch)
    calls: list[tuple[object, ...]] = []

    def fixed_readiness(*args: object) -> WarehouseW3LaunchReadyFact:
        calls.append(args)
        return readiness

    monkeypatch.setattr(
        gate_module,
        "inspect_w3_launch_readiness",
        fixed_readiness,
    )
    inspection, absence = _ORIGINAL_INSPECT(
        FilesystemCandidateCompositionInspector(),
        **values,
    )

    candidate_root = values["candidate_root"]
    accepted_root = values["accepted_root"]
    assert isinstance(candidate_root, Path)
    assert isinstance(accepted_root, Path)
    assert calls == [
        (
            accepted_root,
            (candidate_root / "authority.json").read_bytes(),
            (candidate_root / "installation.json").read_bytes(),
            (candidate_root / "units/scion-w3@.service").read_bytes(),
            (candidate_root / "units/scion-w3-close@.service").read_bytes(),
        )
    ]
    assert inspection.accepted_root_identity.mode == 0o700
    assert inspection.cell_count == 43
    assert inspection.job_count == 172
    assert inspection.manifest_sha256 == values["manifest_sha256"]
    assert inspection.absence_facts_sha256 == absence.raw_sha256


@pytest.mark.parametrize("target", ("accepted_payload", "authority_sidecar"))
def test_production_inspector_rejects_content_or_sidecar_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    target: str,
) -> None:
    values, readiness = _production_inspector_inputs(tmp_path, monkeypatch)

    def drifting_readiness(*_args: object) -> WarehouseW3LaunchReadyFact:
        accepted_root = values["accepted_root"]
        candidate_root = values["candidate_root"]
        assert isinstance(accepted_root, Path)
        assert isinstance(candidate_root, Path)
        path = (
            accepted_root / "payload.bin"
            if target == "accepted_payload"
            else candidate_root / "authority.json"
        )
        path.chmod(0o644)
        path.write_bytes(b"drifted after readiness acquisition\n")
        path.chmod(0o444)
        return readiness

    monkeypatch.setattr(
        gate_module,
        "inspect_w3_launch_readiness",
        drifting_readiness,
    )
    with pytest.raises(
        WarehouseW3CandidateGateError,
        match="changed during readiness inspection",
    ):
        _ORIGINAL_INSPECT(
            FilesystemCandidateCompositionInspector(),
            **values,
        )


def test_production_inspector_rejects_arbitrary_read_only_tree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    values, _readiness = _production_inspector_inputs(tmp_path, monkeypatch)
    accepted_root = values["accepted_root"]
    assert isinstance(accepted_root, Path)
    manifest = accepted_root / gate_module.EXPECTED_MANIFEST_NAME
    manifest.chmod(0o644)
    manifest.write_bytes(b'{"arbitrary":true}\n')
    manifest.chmod(0o444)

    with pytest.raises(
        WarehouseW3CandidateGateError,
        match="manifest dry facts differ",
    ):
        _ORIGINAL_INSPECT(
            FilesystemCandidateCompositionInspector(),
            **values,
        )


def test_candidate_gate_closes_exact_artifacts_dry_root_and_absence(
    tmp_path: Path,
) -> None:
    bundle = _bundle(tmp_path)
    closure = close_candidate_gate_closure(**bundle)
    receipt = closure.gate

    assert CandidateGateClosureBundle.from_bytes(closure.raw) == closure
    assert close_candidate_gate(**bundle) == receipt
    assert CandidateGateReceipt.from_bytes(receipt.raw) == receipt
    assert receipt.state == "CANDIDATE_ACCEPTED_INSTALLATION_ABSENT"
    assert receipt.external_installation_required is True
    assert receipt.cell_count == 43
    assert receipt.job_count == 172
    assert receipt.formal_jobs_started == 0
    assert receipt.formal_execution_authorized is False
    assert receipt.filesystem_mutated is False
    assert receipt.source_receipt_sha256 == _sha("source")
    assert receipt.candidate_root == str(bundle["candidate_root"])
    assert receipt.accepted_root_read_only is True
    semantic = bundle["semantic_environment"]
    generic = bundle["environment_content"]
    relocation = bundle["namespace_probe_ref"]
    assert type(semantic) is WarehouseEnvironmentContentReceipt
    assert type(generic) is EnvironmentContentReceipt
    assert type(relocation) is CandidateNamespaceFinalProbeRef
    assert semantic.raw_sha256 != generic.raw_sha256
    assert semantic.generic_receipt_sha256 == generic.raw_sha256
    assert relocation.environment_content_receipt_sha256 == generic.raw_sha256
    assert Path(relocation.physical_environment_root).name == generic.raw_sha256


def test_candidate_gate_reverifies_complete_candidate_after_inspection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = _bundle(tmp_path)
    candidate_root = bundle["candidate_root"]
    assert isinstance(candidate_root, Path)
    prepared = _PREPARED_BY_ROOT[str(candidate_root)]
    calls: list[Path] = []

    def verify_twice(
        current_root: Path,
        *,
        external_runtime_paths: tuple[Path, ...],
    ) -> PreparedCandidate:
        assert external_runtime_paths == (Path("/usr/lib/libdbus-1.so.3"),)
        calls.append(current_root)
        if len(calls) == 1:
            return prepared
        return replace(
            prepared,
            candidate_root=tmp_path / "same-inode-content-drift",
        )

    monkeypatch.setattr(gate_module, "verify_candidate", verify_twice)
    with pytest.raises(
        WarehouseW3CandidateGateError,
        match="changed during candidate gate closure",
    ):
        close_candidate_gate(**bundle)

    assert calls == [candidate_root, candidate_root]


def test_minimal_old_candidate_and_launch_ready_claim_are_rejected(
    tmp_path: Path,
) -> None:
    bundle = _bundle(tmp_path)
    candidate = bundle["candidate_verification"]
    with pytest.raises(TypeError):
        close_candidate_gate(candidate_verification=candidate)  # type: ignore[call-arg]

    old_minimal = _canonical(
        {
            "schema": "scion.w3-candidate-gate.v1",
            "candidate_verification_sha256": candidate.raw_sha256,
        }
    )
    with pytest.raises(WarehouseW3CandidateGateError, match="fields differ"):
        CandidateGateReceipt.from_bytes(old_minimal)

    inspector = bundle["inspector"]
    assert type(inspector) is FilesystemCandidateCompositionInspector
    artifact = bundle["double_wheel_artifact"]
    assert type(artifact) is OfflineDoubleWheelArtifact
    inspection, _absence_fact = inspector.inspect(
        accepted_root=bundle["accepted_root"],
        candidate_root=bundle["candidate_root"],
        nonce=bundle["nonce"],
        manifest_sha256=bundle["accepted_manifest_sha256"],
        prepared_candidate=_PREPARED_BY_ROOT[str(bundle["candidate_root"])],
        candidate_verification=bundle["candidate_verification"],
        double_wheel=artifact.receipt,
        semantic_environment=bundle["semantic_environment"],
        candidate_probe=bundle["candidate_probe"],
        namespace_final_probe=bundle["namespace_final_probe"],
        namespace_probe_ref=bundle["namespace_probe_ref"],
    )
    assert type(inspection) is CandidateCompositionInspection
    value = json.loads(inspection.raw)
    value["state"] = "LAUNCH_READY"
    value["external_installation_required"] = False
    with pytest.raises(
        WarehouseW3CandidateGateError,
        match="inspection state differs",
    ):
        CandidateCompositionInspection.from_bytes(_canonical(value))


def test_gate_rejects_mixed_selection_authority_and_receipt_replay(
    tmp_path: Path,
) -> None:
    bundle = _bundle(tmp_path / "selection")
    relocation = bundle["namespace_probe_ref"]
    assert type(relocation) is CandidateNamespaceFinalProbeRef
    value = json.loads(relocation.raw)

    value["selection_key"] = _sha("replayed-selection")
    bundle["namespace_probe_ref"] = CandidateNamespaceFinalProbeRef.from_bytes(
        _canonical(value),
        semantic_environment=bundle["semantic_environment"],
    )
    with pytest.raises(WarehouseW3CandidateGateError, match="binding differs"):
        close_candidate_gate(**bundle)

    bundle = _bundle(tmp_path / "authority")
    relocation = bundle["namespace_probe_ref"]
    assert type(relocation) is CandidateNamespaceFinalProbeRef
    value = json.loads(relocation.raw)
    value["authority_sha256"] = _sha("replayed-authority")
    bundle["namespace_probe_ref"] = CandidateNamespaceFinalProbeRef.from_bytes(
        _canonical(value),
        semantic_environment=bundle["semantic_environment"],
    )
    with pytest.raises(WarehouseW3CandidateGateError, match="binding differs"):
        close_candidate_gate(**bundle)

    bundle = _bundle(tmp_path / "probe")
    relocation = bundle["namespace_probe_ref"]
    assert type(relocation) is CandidateNamespaceFinalProbeRef
    value = json.loads(relocation.raw)
    value["candidate_probe_sha256"] = _sha("replayed-probe")
    bundle["namespace_probe_ref"] = CandidateNamespaceFinalProbeRef.from_bytes(
        _canonical(value),
        semantic_environment=bundle["semantic_environment"],
    )
    with pytest.raises(WarehouseW3CandidateGateError, match="binding differs"):
        close_candidate_gate(**bundle)


def test_gate_rejects_mixed_absence_and_root_final_relocation_semantics(
    tmp_path: Path,
) -> None:
    bundle = _bundle(tmp_path / "fake")
    bundle["inspector"] = object()
    with pytest.raises(TypeError, match="FilesystemCandidateCompositionInspector"):
        close_candidate_gate(**bundle)

    bundle = _bundle(tmp_path / "root-final")
    relocation = bundle["namespace_probe_ref"]
    assert type(relocation) is CandidateNamespaceFinalProbeRef
    value = json.loads(relocation.raw)
    value["physical_environment_root"] = (
        f"/var/lib/scion/environments/w3/"
        f"{relocation.environment_content_receipt_sha256}"
    )
    with pytest.raises(
        WarehouseW3CandidateGateError,
        match="physical or visible path",
    ):
        CandidateNamespaceFinalProbeRef.from_bytes(
            _canonical(value),
            semantic_environment=bundle["semantic_environment"],
        )


def test_namespace_probe_ref_rejects_old_schema_visible_suffix_and_generic_drift(
    tmp_path: Path,
) -> None:
    bundle = _bundle(tmp_path)
    relocation = bundle["namespace_probe_ref"]
    semantic = bundle["semantic_environment"]
    assert type(relocation) is CandidateNamespaceFinalProbeRef
    assert type(semantic) is WarehouseEnvironmentContentReceipt
    assert semantic.raw_sha256 != semantic.generic_receipt_sha256
    value = json.loads(relocation.raw)
    assert value["schema"] == "scion.w3-candidate-namespace-final-probe-ref.v1"

    old_v1 = dict(value)
    old_v1["schema"] = "scion.w3-candidate-simulated-relocation-ref.v2"
    with pytest.raises(WarehouseW3CandidateGateError, match="authority differs"):
        CandidateNamespaceFinalProbeRef.from_bytes(
            _canonical(old_v1),
            semantic_environment=semantic,
        )

    semantic_suffix = dict(value)
    semantic_suffix["visible_environment_root"] = (
        f"{tmp_path}/semantic-suffix/var/lib/scion/environments/w3/"
        f"{semantic.raw_sha256}"
    )
    with pytest.raises(
        WarehouseW3CandidateGateError,
        match="physical or visible path",
    ):
        CandidateNamespaceFinalProbeRef.from_bytes(
            _canonical(semantic_suffix),
            semantic_environment=semantic,
        )

    generic_drift = dict(value)
    generic_drift["environment_content_receipt_sha256"] = _sha("generic-drift")
    with pytest.raises(
        WarehouseW3CandidateGateError,
        match="environment binding differs",
    ):
        CandidateNamespaceFinalProbeRef.from_bytes(
            _canonical(generic_drift),
            semantic_environment=semantic,
        )


def test_gate_rejects_double_wheel_and_semantic_environment_mix(
    tmp_path: Path,
) -> None:
    bundle = _bundle(tmp_path)
    artifact = bundle["double_wheel_artifact"]
    assert type(artifact) is OfflineDoubleWheelArtifact
    double_wheel = artifact.receipt
    other = json.loads(double_wheel.raw)
    other["wheel_sha256"] = _sha("other-wheel")
    changed = OfflineDoubleWheelReceipt.from_bytes(_canonical(other))
    bundle["double_wheel_artifact"] = OfflineDoubleWheelArtifact._for_test(
        wheel_path=artifact.wheel_path,
        wheel_identity=artifact.wheel_identity,
        receipt=changed,
        build_argv=artifact.build_argv,
    )
    with pytest.raises(
        WarehouseW3CandidateGateError,
        match="cannot be reopened|object differs|binding differs",
    ):
        close_candidate_gate(**bundle)


def test_gate_requires_exact_candidate_environment_root_and_identity(
    tmp_path: Path,
) -> None:
    bundle = _bundle(tmp_path / "probe")
    semantic = bundle["semantic_environment"]
    assert type(semantic) is WarehouseEnvironmentContentReceipt
    final_root = Path(
        f"/var/lib/scion/environments/w3/{semantic.generic_receipt_sha256}"
    )
    bad_probe = _probe(
        semantic,
        phase="candidate",
        root=final_root,
    )
    relocation = bundle["namespace_probe_ref"]
    assert type(relocation) is CandidateNamespaceFinalProbeRef
    bundle["candidate_probe"] = bad_probe
    bundle["namespace_probe_ref"] = CandidateNamespaceFinalProbeRef.create(
        evidence_receipt_sha256=relocation.evidence_receipt_sha256,
        selection_key=relocation.selection_key,
        launch_id=relocation.launch_id,
        authority_sha256=relocation.authority_sha256,
        installation_sha256=relocation.installation_sha256,
        semantic_environment=semantic,
        candidate_probe=bad_probe,
        namespace_final_probe=bundle["namespace_final_probe"],
        namespace_probe_execution=bundle["namespace_probe_execution"],
    )
    with pytest.raises(
        WarehouseW3CandidateGateError,
        match="candidate environment probe is not cross-bound",
    ):
        close_candidate_gate(**bundle)

    bundle = _bundle(tmp_path / "identity")
    other_root = tmp_path / "identity" / "other-candidate"
    other_root.mkdir()
    other_root.chmod(0o555)
    bundle["candidate_root"] = other_root
    with pytest.raises(
        WarehouseW3CandidateGateError,
        match="candidate cannot be reopened and reverified",
    ):
        close_candidate_gate(**bundle)


@pytest.mark.parametrize("mutation", ("foreign-sys-path", "partial-import-table"))
def test_gate_rejects_incomplete_environment_probe_semantics(
    tmp_path: Path,
    mutation: str,
) -> None:
    bundle = _bundle(tmp_path / mutation)
    probe = bundle["candidate_probe"]
    assert type(probe) is EnvironmentProbeFact
    value = json.loads(probe.raw)
    if mutation == "foreign-sys-path":
        value["sys_path"].append("/tmp/foreign-python")
    else:
        assert len(value["loaded_import_table"]) > 1
        value["loaded_import_table"] = value["loaded_import_table"][:1]
    bundle["candidate_probe"] = EnvironmentProbeFact.from_bytes(_canonical(value))

    with pytest.raises(
        WarehouseW3CandidateGateError,
        match="candidate environment probe is not cross-bound",
    ):
        close_candidate_gate(**bundle)


def test_source_receipt_and_candidate_raw_replay_are_cross_bound(
    tmp_path: Path,
) -> None:
    bundle = _bundle(tmp_path / "source")
    candidate = bundle["candidate_verification"]
    assert type(candidate) is CandidateVerificationReceipt
    bundle["candidate_verification"] = _candidate(
        selection_key=candidate.selection_key,
        authority_sha256=candidate.authority_sha256,
        installation_sha256=candidate.installation_sha256,
        environment_receipt_sha256=candidate.environment_receipt_sha256,
        candidate_root_identity=candidate.candidate_root_identity,
        source_receipt_sha256=_sha("other-source"),
    )
    with pytest.raises(
        WarehouseW3CandidateGateError,
        match="wheel or semantic environment binding differs",
    ):
        close_candidate_gate(**bundle)

    bundle = _bundle(tmp_path / "replay")
    _inspection, _old_absence = _inspect_bundle(bundle)
    old_candidate = bundle["candidate_verification"]
    assert type(old_candidate) is CandidateVerificationReceipt
    bundle["candidate_verification"] = _candidate(
        selection_key=old_candidate.selection_key,
        authority_sha256=old_candidate.authority_sha256,
        installation_sha256=old_candidate.installation_sha256,
        environment_receipt_sha256=old_candidate.environment_receipt_sha256,
        candidate_root_identity=old_candidate.candidate_root_identity,
        candidate_receipt_sha256=_sha("new-candidate-receipt"),
    )
    with pytest.raises(
        WarehouseW3CandidateGateError,
        match="candidate wheel or semantic environment binding differs",
    ):
        close_candidate_gate(**bundle)


def test_absence_subjects_and_integer_domain_are_not_caller_declared(
    tmp_path: Path,
) -> None:
    bundle = _bundle(tmp_path)
    inspection, absence = _inspect_bundle(bundle)
    value = json.loads(absence.raw)
    first = value["observations"][0]
    first["subject"] = "/unrelated/caller-declared"
    first["observation_sha256"] = gate_module._absence_observation_sha256(
        role=first["role"],
        subject=first["subject"],
        candidate_verification_sha256=value["candidate_verification_sha256"],
        double_wheel_receipt_sha256=value["double_wheel_receipt_sha256"],
        semantic_environment_receipt_sha256=value[
            "semantic_environment_receipt_sha256"
        ],
        namespace_probe_ref_sha256=value["namespace_probe_ref_sha256"],
    )
    with pytest.raises(
        WarehouseW3CandidateGateError,
        match="mechanically derived",
    ):
        CandidateAbsenceFacts.from_bytes(_canonical(value))

    inspection_value = json.loads(inspection.raw)
    inspection_value["accepted_root_inventory_count"] = 1 << 65
    with pytest.raises(
        WarehouseW3CandidateGateError,
        match="bounded unsigned integer",
    ):
        CandidateCompositionInspection.from_bytes(_canonical(inspection_value))


def test_candidate_gate_has_no_root_manager_or_mutation_surface() -> None:
    source_path = (
        Path(__file__).parents[4]
        / "problems"
        / "warehouse_delivery"
        / "w3_candidate_gate.py"
    )
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module.split(".", 1)[0])
    called = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }

    assert imported.isdisjoint({"ctypes", "dbus", "psutil", "subprocess"})
    assert called.isdisjoint(
        {
            "StartUnit",
            "kill",
            "mount",
            "open_tree",
            "fchmod",
            "fsync",
            "mkdir",
            "remove",
            "rename",
            "replace",
            "rmdir",
            "setns",
            "system",
            "umount",
            "unlink",
            "write",
            "write_bytes",
            "write_text",
        }
    )
