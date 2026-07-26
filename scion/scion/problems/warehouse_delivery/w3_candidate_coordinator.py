"""Production coordinator for one non-root Warehouse W3 candidate closure.

This module owns only preparation-time composition.  It has no root, mount,
systemd-manager, nonce-claim, terminal-write, retry, or launch capability.
"""

from __future__ import annotations

import hashlib
import os
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from scion.runtime.execution.environment_integrity import verify_environment_content

from .w3_candidate_gate import (
    W3_WHEEL_LOGICAL_PATH,
    W3_WHEEL_RECEIPT_LOGICAL_PATH,
    W3_WHEEL_RECEIPT_SEALED_PATH,
    W3_WHEEL_SEALED_PATH,
    CandidateGateClosureBundle,
    CandidateNamespaceFinalProbeRef,
    FilesystemCandidateCompositionInspector,
    close_candidate_gate_closure,
    derive_namespace_probe_evidence_sha256,
)
from .w3_candidate_ingress import (
    PinnedCandidateGateIngress,
    derive_candidate_gate_ingress_paths,
    pin_candidate_gate_ingress,
    publish_candidate_gate_ingress,
)
from .w3_composition import (
    EXPECTED_MANIFEST_NAME,
    EXPECTED_MANIFEST_SHA256,
    EXPECTED_NATIVE_ACCEPTANCE_RECORD_SHA256,
)
from .w3_environment import (
    WarehouseRuntimeSources,
    materialize_simulated_warehouse_environment as materialize_namespace_environment,
    prepare_production_warehouse_environment,
    validate_runtime_python,
)
from .w3_environment_receipts import (
    FilesystemEnvironmentSemanticReader,
    NonRootNamespaceEnvironmentProbeReader,
    SubprocessEnvironmentProbeReader,
    acquire_warehouse_environment_content,
)
from .w3_installation import (
    ACCEPTED_ROOT_INSTALLATION_PLAN_SHA256,
    W3_NATIVE_RECORD_LOGICAL_PATH,
    W3_PROJECT_GIT_TREE_PREFIX,
    CandidateSelectionIntent,
    GitSourceAcquirer,
    GitSourceSnapshot,
    PreparedCandidate,
    SealedStoreObject,
    SubprocessGitRunner,
    derive_candidate_paths,
    prepare_candidate,
    verify_candidate,
    w3_project_git_pathspec,
)
from .w3_source_acceptance import (
    RootFixedSourceAcceptanceAuthority,
    W3_SOURCE_ACCEPTANCE_LOGICAL_PATH,
    W3_SOURCE_ACCEPTANCE_SEALED_PATH,
    source_acceptance_path as canonical_source_acceptance_path,
)
from .w3_wheel import (
    ImmutableGitArchive,
    OfflineDoubleWheelArtifact,
    build_offline_double_wheel,
    reopen_offline_double_wheel_artifact,
)

W3_TASK_EVENT_IDENTITY = (
    "task-event:20260723-w3-root-installation-loaded-manager-launch"
)
_WORK_PARENT = ".scion-w3-candidate-work"
_ARCHIVE_NAMES = ("source-1.tar", "source-2.tar")
_RUNTIME_PACKAGE_ROOT = Path("/usr/lib/python3/dist-packages")
_MAX_GIT_INVENTORY_BYTES = 8 * 1024 * 1024
_MAX_EXTERNAL_EVIDENCE_BYTES = 64 * 1024 * 1024


class WarehouseW3CandidateCoordinatorError(RuntimeError):
    """The one-candidate production preparation transaction differs."""


@dataclass(frozen=True, slots=True)
class WarehouseW3PreparedCandidateClosure:
    candidate: PreparedCandidate
    closure: CandidateGateClosureBundle
    gate_path: Path
    work_root: Path

    def __post_init__(self) -> None:
        if (
            type(self.candidate) is not PreparedCandidate
            or type(self.closure) is not CandidateGateClosureBundle
            or not isinstance(self.gate_path, Path)
            or not isinstance(self.work_root, Path)
            or self.closure.candidate_verification
            != self.candidate.verification_receipt
            or self.closure.gate.selection_key != self.candidate.intent.selection_key
        ):
            raise WarehouseW3CandidateCoordinatorError(
                "prepared candidate closure fields differ"
            )

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("WarehouseW3PreparedCandidateClosure is final")


def _require_nonroot() -> None:
    if os.geteuid() == 0:
        raise PermissionError("W3 candidate coordinator rejects effective UID 0")


def _absolute_directory(path: Path, *, label: str) -> Path:
    if not isinstance(path, Path):
        raise TypeError(f"{label} must be Path")
    text = str(path)
    pure = PurePosixPath(text)
    if (
        not pure.is_absolute()
        or text == "/"
        or text.startswith("//")
        or str(pure) != text
        or any(part in {"", ".", ".."} for part in pure.parts[1:])
    ):
        raise WarehouseW3CandidateCoordinatorError(
            f"{label} is not one canonical absolute path"
        )
    try:
        named = os.lstat(path)
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise WarehouseW3CandidateCoordinatorError(
            f"{label} cannot be reopened"
        ) from exc
    if (
        stat.S_ISLNK(named.st_mode)
        or not stat.S_ISDIR(named.st_mode)
        or resolved != path
    ):
        raise WarehouseW3CandidateCoordinatorError(
            f"{label} is not one direct directory"
        )
    return path


def _bound_regular_bytes(path: Path, *, label: str, maximum: int) -> bytes:
    if not isinstance(path, Path) or type(maximum) is not int or maximum <= 0:
        raise TypeError("bound regular read arguments differ")
    flags = os.O_RDONLY | os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = -1
    try:
        named_before = os.lstat(path)
        descriptor = os.open(path, flags)
        opened_before = os.fstat(descriptor)
        if (
            stat.S_ISLNK(named_before.st_mode)
            or not stat.S_ISREG(opened_before.st_mode)
            or opened_before.st_nlink != 1
            or opened_before.st_size > maximum
            or (
                named_before.st_dev,
                named_before.st_ino,
                named_before.st_mode,
                named_before.st_uid,
                named_before.st_gid,
                named_before.st_nlink,
                named_before.st_size,
                named_before.st_mtime_ns,
                named_before.st_ctime_ns,
            )
            != (
                opened_before.st_dev,
                opened_before.st_ino,
                opened_before.st_mode,
                opened_before.st_uid,
                opened_before.st_gid,
                opened_before.st_nlink,
                opened_before.st_size,
                opened_before.st_mtime_ns,
                opened_before.st_ctime_ns,
            )
        ):
            raise WarehouseW3CandidateCoordinatorError(f"{label} identity differs")
        chunks: list[bytes] = []
        size = 0
        while True:
            chunk = os.read(descriptor, min(1024 * 1024, maximum - size + 1))
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
            if size > maximum:
                raise WarehouseW3CandidateCoordinatorError(f"{label} exceeds its bound")
        opened_after = os.fstat(descriptor)
        named_after = os.lstat(path)
    except WarehouseW3CandidateCoordinatorError:
        raise
    except OSError as exc:
        raise WarehouseW3CandidateCoordinatorError(f"{label} cannot be read") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    before = (
        opened_before.st_dev,
        opened_before.st_ino,
        opened_before.st_mode,
        opened_before.st_uid,
        opened_before.st_gid,
        opened_before.st_nlink,
        opened_before.st_size,
        opened_before.st_mtime_ns,
        opened_before.st_ctime_ns,
    )
    if before != (
        opened_after.st_dev,
        opened_after.st_ino,
        opened_after.st_mode,
        opened_after.st_uid,
        opened_after.st_gid,
        opened_after.st_nlink,
        opened_after.st_size,
        opened_after.st_mtime_ns,
        opened_after.st_ctime_ns,
    ) or before != (
        named_after.st_dev,
        named_after.st_ino,
        named_after.st_mode,
        named_after.st_uid,
        named_after.st_gid,
        named_after.st_nlink,
        named_after.st_size,
        named_after.st_mtime_ns,
        named_after.st_ctime_ns,
    ):
        raise WarehouseW3CandidateCoordinatorError(f"{label} changed while read")
    return b"".join(chunks)


def _tracked_launch_paths(repo_root: Path, launch_commit: str) -> tuple[str, ...]:
    raw = SubprocessGitRunner().run(
        (
            "git",
            "ls-tree",
            "-rz",
            "--full-tree",
            launch_commit,
            "--",
            w3_project_git_pathspec("pyproject.toml"),
            w3_project_git_pathspec("scion"),
        ),
        cwd=repo_root,
    )
    if not raw or len(raw) > _MAX_GIT_INVENTORY_BYTES or not raw.endswith(b"\0"):
        raise WarehouseW3CandidateCoordinatorError(
            "launch Git inventory is absent or exceeds its bound"
        )
    paths: list[str] = []
    for encoded in raw[:-1].split(b"\0"):
        try:
            header, path_raw = encoded.split(b"\t", 1)
            mode_raw, kind_raw, _oid_raw = header.split(b" ", 2)
            mode = mode_raw.decode("ascii", "strict")
            kind = kind_raw.decode("ascii", "strict")
            git_tree_path = path_raw.decode("utf-8", "strict")
        except (ValueError, UnicodeError) as exc:
            raise WarehouseW3CandidateCoordinatorError(
                "launch Git inventory entry is malformed"
            ) from exc
        if not git_tree_path.startswith(W3_PROJECT_GIT_TREE_PREFIX):
            raise WarehouseW3CandidateCoordinatorError(
                "launch Git inventory escapes the fixed project subtree"
            )
        path = git_tree_path.removeprefix(W3_PROJECT_GIT_TREE_PREFIX)
        pure = PurePosixPath(path)
        if (
            kind != "blob"
            or mode not in {"100644", "100755"}
            or pure.is_absolute()
            or str(pure) != path
            or any(part in {"", ".", ".."} for part in pure.parts)
        ):
            raise WarehouseW3CandidateCoordinatorError(
                "launch Git inventory contains a non-regular entry"
            )
        if path.startswith("scion/tests/"):
            continue
        paths.append(path)
    selected = tuple(sorted(paths, key=lambda item: item.encode("utf-8")))
    if (
        not selected
        or len(set(selected)) != len(selected)
        or "pyproject.toml" not in selected
        or "scion/tools/scion_w3_tool.py" not in selected
        or "scion/tools/scion_w3_install.py" not in selected
    ):
        raise WarehouseW3CandidateCoordinatorError("launch Git source closure differs")
    return selected


def _prepare_work_root(experiment_parent: Path, selection_key: str) -> Path:
    parent = experiment_parent / _WORK_PARENT
    try:
        os.mkdir(parent, 0o755)
        parent.chmod(0o755)
        parent_fd = os.open(
            experiment_parent,
            os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY,
        )
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
    except FileExistsError:
        pass
    except OSError as exc:
        raise WarehouseW3CandidateCoordinatorError(
            "candidate work parent cannot be created"
        ) from exc
    metadata = os.lstat(parent)
    if (
        stat.S_ISLNK(metadata.st_mode)
        or not stat.S_ISDIR(metadata.st_mode)
        or stat.S_IMODE(metadata.st_mode) != 0o755
        or metadata.st_uid != os.geteuid()
        or metadata.st_gid != os.getegid()
    ):
        raise WarehouseW3CandidateCoordinatorError(
            "candidate work parent identity differs"
        )
    work_root = parent / selection_key
    try:
        os.mkdir(work_root, 0o700)
        work_root.chmod(0o700)
        parent_fd = os.open(parent, os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
    except OSError as exc:
        raise WarehouseW3CandidateCoordinatorError(
            "candidate work root already exists or cannot be created"
        ) from exc
    return work_root


def _create_git_archive(
    repo_root: Path,
    *,
    launch_commit: str,
    logical_paths: tuple[str, ...],
    destination: Path,
    source: GitSourceSnapshot,
) -> ImmutableGitArchive:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = -1
    try:
        descriptor = os.open(destination, flags, 0o600)
        environment = dict(os.environ)
        for name in tuple(environment):
            if name.startswith("GIT_"):
                del environment[name]
        environment.update(
            {
                "GIT_NO_REPLACE_OBJECTS": "1",
                "GIT_OPTIONAL_LOCKS": "0",
                "GIT_TERMINAL_PROMPT": "0",
                "LANG": "C",
                "LC_ALL": "C",
            }
        )
        completed = subprocess.run(
            (
                "git",
                "-c",
                "tar.umask=0022",
                "archive",
                "--format=tar",
                launch_commit,
                "--",
                *logical_paths,
            ),
            cwd=repo_root,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=descriptor,
            stderr=subprocess.PIPE,
            shell=False,
            check=False,
            timeout=120,
        )
        if (
            completed.returncode != 0
            or type(completed.stderr) is not bytes
            or completed.stderr
        ):
            raise WarehouseW3CandidateCoordinatorError(
                "immutable Git archive command failed"
            )
        os.fsync(descriptor)
        os.fchmod(descriptor, 0o444)
        os.fsync(descriptor)
    except WarehouseW3CandidateCoordinatorError:
        raise
    except (OSError, subprocess.SubprocessError) as exc:
        raise WarehouseW3CandidateCoordinatorError(
            "immutable Git archive could not be created"
        ) from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    raw = _bound_regular_bytes(
        destination,
        label="immutable Git archive",
        maximum=1024 * 1024 * 1024,
    )
    return ImmutableGitArchive(
        path=destination,
        sha256=hashlib.sha256(raw).hexdigest(),
        source_receipt=source.receipt,
    )


def _one_runtime_match(pattern: str, *, directory: bool) -> Path:
    try:
        matches = tuple(
            sorted(
                _RUNTIME_PACKAGE_ROOT.glob(pattern),
                key=lambda item: str(item).encode("utf-8"),
            )
        )
    except OSError as exc:
        raise WarehouseW3CandidateCoordinatorError(
            "runtime package source cannot be enumerated"
        ) from exc
    if len(matches) != 1:
        raise WarehouseW3CandidateCoordinatorError(
            f"runtime package source is not unique: {pattern}"
        )
    metadata = os.lstat(matches[0])
    expected = (
        stat.S_ISDIR(metadata.st_mode) if directory else stat.S_ISREG(metadata.st_mode)
    )
    if stat.S_ISLNK(metadata.st_mode) or not expected:
        raise WarehouseW3CandidateCoordinatorError(
            f"runtime package source identity differs: {pattern}"
        )
    return matches[0]


def _runtime_sources() -> WarehouseRuntimeSources:
    sources = WarehouseRuntimeSources(
        dbus_package=_one_runtime_match("dbus", directory=True),
        dbus_bindings=_one_runtime_match(
            "_dbus_bindings.cpython-312-*.so",
            directory=False,
        ),
        dbus_glib_bindings=_one_runtime_match(
            "_dbus_glib_bindings.cpython-312-*.so",
            directory=False,
        ),
        dbus_metadata=_one_runtime_match(
            "dbus_python-*.egg-info",
            directory=True,
        ),
        yaml_package=_one_runtime_match("yaml", directory=True),
        yaml_metadata=_one_runtime_match(
            "PyYAML-*.dist-info",
            directory=True,
        ),
    )
    sources.validate()
    return sources


def _generated_store_objects(
    source: GitSourceSnapshot,
    artifact: OfflineDoubleWheelArtifact,
) -> tuple[SealedStoreObject, SealedStoreObject]:
    source_by_path = {item.logical_path: item for item in source.blobs}
    generator = source_by_path.get("scion/problems/warehouse_delivery/w3_wheel.py")
    if generator is None:
        raise WarehouseW3CandidateCoordinatorError(
            "launch source lacks the fixed wheel generator"
        )
    wheel_raw = _bound_regular_bytes(
        artifact.wheel_path,
        label="offline W3 wheel",
        maximum=max(artifact.receipt.wheel_size_bytes, 1),
    )
    if hashlib.sha256(wheel_raw).hexdigest() != artifact.receipt.wheel_sha256:
        raise WarehouseW3CandidateCoordinatorError("offline W3 wheel bytes differ")
    wheel = SealedStoreObject.generated(
        logical_path=W3_WHEEL_LOGICAL_PATH,
        sealed_path=W3_WHEEL_SEALED_PATH,
        raw=wheel_raw,
        generator_sha256=generator.sha256,
        input_sha256=(
            source.receipt.raw_sha256,
            *artifact.receipt.archive_sha256,
        ),
        rule_sha256=ACCEPTED_ROOT_INSTALLATION_PLAN_SHA256,
    )
    receipt = SealedStoreObject.generated(
        logical_path=W3_WHEEL_RECEIPT_LOGICAL_PATH,
        sealed_path=W3_WHEEL_RECEIPT_SEALED_PATH,
        raw=artifact.receipt.raw,
        generator_sha256=generator.sha256,
        input_sha256=(
            source.receipt.raw_sha256,
            artifact.receipt.wheel_sha256,
        ),
        rule_sha256=ACCEPTED_ROOT_INSTALLATION_PLAN_SHA256,
    )
    return wheel, receipt


def _reverify_environment_evidence(
    prepared: PreparedCandidate,
    closure: CandidateGateClosureBundle,
) -> None:
    """Rehash and rerun both non-root relocation probes during reopen."""

    candidate_root = prepared.candidate_root / "environment"
    physical_root = Path(closure.namespace_probe_ref.physical_environment_root)
    external_runtime_paths = tuple(
        Path(item.path) for item in closure.environment_content.external_runtime
    )
    selection_root = Path(prepared.intent.selection_directory)
    for label, environment_root in (
        ("candidate", candidate_root),
        ("namespace-physical", physical_root),
    ):
        try:
            verify_environment_content(
                environment_root,
                closure.environment_content,
                external_runtime_paths=external_runtime_paths,
                candidate_root=prepared.candidate_root,
                selection_root=selection_root,
            )
        except Exception as exc:
            raise WarehouseW3CandidateCoordinatorError(
                f"live {label} environment differs from candidate closure"
            ) from exc
    reader = SubprocessEnvironmentProbeReader()
    namespace_reader = NonRootNamespaceEnvironmentProbeReader()
    try:
        candidate_probe = reader.probe(
            candidate_root,
            phase="candidate",
            content_receipt=closure.semantic_environment,
        )
        namespace_probe, namespace_execution = namespace_reader.probe(
            physical_root,
            content_receipt=closure.semantic_environment,
        )
    except Exception as exc:
        raise WarehouseW3CandidateCoordinatorError(
            "live candidate relocation probe differs"
        ) from exc
    if (
        candidate_probe != closure.candidate_probe
        or namespace_probe != closure.namespace_final_probe
        or namespace_execution != closure.namespace_probe_execution
        or derive_namespace_probe_evidence_sha256(
            closure.semantic_environment.raw,
            candidate_probe.raw,
            namespace_probe.raw,
            namespace_execution.raw,
        )
        != closure.namespace_probe_ref.evidence_receipt_sha256
    ):
        raise WarehouseW3CandidateCoordinatorError(
            "live candidate relocation evidence differs"
        )


def prepare_w3_candidate(
    accepted_root: Path,
    *,
    repo_root: Path,
    launch_commit: str,
    remote_name: str,
    remote_ref: str,
    native_record_path: Path,
    runtime_python: Path,
    source_acceptance_path: Path,
) -> WarehouseW3PreparedCandidateClosure:
    """Prepare, close, publish, and independently reopen one exact candidate."""

    _require_nonroot()
    validate_runtime_python(runtime_python)
    runtime_sources = _runtime_sources()
    root = _absolute_directory(accepted_root, label="accepted_root")
    repo = _absolute_directory(repo_root, label="repo_root")
    if not isinstance(native_record_path, Path):
        raise TypeError("native_record_path must be Path")
    manifest_path = root / EXPECTED_MANIFEST_NAME
    manifest_raw = _bound_regular_bytes(
        manifest_path,
        label="accepted W3 manifest",
        maximum=_MAX_EXTERNAL_EVIDENCE_BYTES,
    )
    native_raw = _bound_regular_bytes(
        native_record_path,
        label="accepted native record",
        maximum=_MAX_EXTERNAL_EVIDENCE_BYTES,
    )
    if (
        hashlib.sha256(manifest_raw).hexdigest() != EXPECTED_MANIFEST_SHA256
        or hashlib.sha256(native_raw).hexdigest()
        != EXPECTED_NATIVE_ACCEPTANCE_RECORD_SHA256
    ):
        raise WarehouseW3CandidateCoordinatorError(
            "accepted manifest or native record identity differs"
        )
    with RootFixedSourceAcceptanceAuthority.open(
        source_acceptance_path
    ) as source_authority:
        source_acceptance = source_authority.receipt
        if (
            source_acceptance_path
            != canonical_source_acceptance_path(source_acceptance.source_commit)
            or launch_commit != source_acceptance.source_commit
        ):
            raise WarehouseW3CandidateCoordinatorError(
                "root fixed-source acceptance path or commit differs"
            )
        logical_paths = _tracked_launch_paths(repo, launch_commit)
        source = GitSourceAcquirer(repo).acquire(
            launch_commit=launch_commit,
            remote_name=remote_name,
            remote_ref=remote_ref,
            logical_paths=logical_paths,
        )
        if source.receipt != source_acceptance.source_receipt:
            raise WarehouseW3CandidateCoordinatorError(
                "live Git source differs from root fixed-source acceptance"
            )
        source_authority.revalidate()
    intent = CandidateSelectionIntent.create(
        experiment_parent=root.parent,
        task_event_identity=W3_TASK_EVENT_IDENTITY,
        launch_commit=source.receipt.source_commit,
        launch_tree=source.receipt.source_tree,
        dry_root_manifest_sha256=EXPECTED_MANIFEST_SHA256,
        native_record_sha256=EXPECTED_NATIVE_ACCEPTANCE_RECORD_SHA256,
        source_acceptance_sha256=source_acceptance.raw_sha256,
    )
    paths = derive_candidate_paths(root.parent, intent.selection_key)
    work_root = _prepare_work_root(root.parent, intent.selection_key)
    archives = tuple(
        _create_git_archive(
            repo,
            launch_commit=source.receipt.source_commit,
            logical_paths=logical_paths,
            destination=work_root / name,
            source=source,
        )
        for name in _ARCHIVE_NAMES
    )
    if len(archives) != 2:
        raise AssertionError("fixed archive count differs")
    artifact = build_offline_double_wheel(
        (archives[0], archives[1]),
        repo_root=repo,
        work_root=work_root / "double-wheel",
    )
    production_environment = prepare_production_warehouse_environment(
        work_root / "environment",
        wheel_path=artifact.wheel_path,
        wheel_sha256=artifact.receipt.wheel_sha256,
        runtime_sources=runtime_sources,
        candidate_root=paths.candidate_root,
        selection_root=paths.selection_directory,
        runtime_python=runtime_python,
    )
    probe_reader = SubprocessEnvironmentProbeReader()
    semantic = acquire_warehouse_environment_content(
        production_environment.build.environment_root,
        generic_receipt=production_environment.build.receipt,
        wheel_receipt=artifact.receipt,
        reader=FilesystemEnvironmentSemanticReader(probe_reader),
    )
    generated = _generated_store_objects(source, artifact)
    sealed_objects = (
        *(SealedStoreObject.from_git_blob(item) for item in source.blobs),
        SealedStoreObject.external_evidence(
            logical_path=EXPECTED_MANIFEST_NAME,
            sealed_path=f"sealed/{EXPECTED_MANIFEST_NAME}",
            source_path=manifest_path,
        ),
        SealedStoreObject.external_evidence(
            logical_path=W3_NATIVE_RECORD_LOGICAL_PATH,
            sealed_path=f"sealed/{W3_NATIVE_RECORD_LOGICAL_PATH}",
            source_path=native_record_path,
        ),
        SealedStoreObject.external_evidence(
            logical_path=W3_SOURCE_ACCEPTANCE_LOGICAL_PATH,
            sealed_path=W3_SOURCE_ACCEPTANCE_SEALED_PATH,
            source_path=source_acceptance_path,
        ),
        *generated,
    )
    prepared = prepare_candidate(
        intent,
        source=source,
        sealed_objects=tuple(sealed_objects),
        environment_root=production_environment.build.environment_root,
        environment_receipt=production_environment.build.receipt,
        external_runtime_paths=production_environment.external_runtime_paths,
        run_root=root,
    )
    candidate_environment = prepared.candidate_root / "environment"
    candidate_probe = probe_reader.probe(
        candidate_environment,
        phase="candidate",
        content_receipt=semantic,
    )
    namespace_environment = (
        work_root
        / "namespace-physical"
        / "var"
        / "lib"
        / "scion"
        / "environments"
        / "w3"
        / production_environment.build.receipt.raw_sha256
    )
    namespace_environment.parent.mkdir(mode=0o700, parents=True)
    materialize_namespace_environment(
        candidate_environment,
        namespace_environment,
        production_environment.build.receipt,
        external_runtime_paths=production_environment.external_runtime_paths,
        candidate_root=prepared.candidate_root,
        selection_root=paths.selection_directory,
    )
    (
        namespace_probe,
        namespace_execution,
    ) = NonRootNamespaceEnvironmentProbeReader().probe(
        namespace_environment,
        content_receipt=semantic,
    )
    launch_id = prepared.installation.launch_id
    relocation = CandidateNamespaceFinalProbeRef.create(
        evidence_receipt_sha256=derive_namespace_probe_evidence_sha256(
            semantic.raw,
            candidate_probe.raw,
            namespace_probe.raw,
            namespace_execution.raw,
        ),
        selection_key=intent.selection_key,
        launch_id=launch_id,
        authority_sha256=prepared.authority.authority_sha256,
        installation_sha256=prepared.installation.installation_sha256,
        semantic_environment=semantic,
        candidate_probe=candidate_probe,
        namespace_final_probe=namespace_probe,
        namespace_probe_execution=namespace_execution,
    )
    closure = close_candidate_gate_closure(
        candidate_verification=prepared.verification_receipt,
        double_wheel_artifact=artifact,
        semantic_environment=semantic,
        environment_content=production_environment.build.receipt,
        candidate_probe=candidate_probe,
        namespace_final_probe=namespace_probe,
        namespace_probe_execution=namespace_execution,
        namespace_probe_ref=relocation,
        candidate_root=prepared.candidate_root,
        accepted_root=root,
        nonce=prepared.authority.nonce,
        accepted_manifest_sha256=EXPECTED_MANIFEST_SHA256,
    )
    gate_path = publish_candidate_gate_ingress(closure)
    with pin_candidate_gate_ingress(prepared.candidate_root) as pinned:
        if pinned.closure != closure:
            raise WarehouseW3CandidateCoordinatorError(
                "published candidate closure differs"
            )
        pinned.revalidate()
    reopened = verify_w3_candidate(
        prepared.candidate_root,
        repo_root=repo,
        source_acceptance_path=source_acceptance_path,
    )
    if reopened.closure != closure or reopened.candidate != prepared:
        raise WarehouseW3CandidateCoordinatorError(
            "independent candidate reopen differs"
        )
    return WarehouseW3PreparedCandidateClosure(
        candidate=prepared,
        closure=closure,
        gate_path=gate_path,
        work_root=work_root,
    )


def _reopen_build_artifact(
    pinned: PinnedCandidateGateIngress,
    *,
    prepared: PreparedCandidate,
    repo_root: Path,
) -> OfflineDoubleWheelArtifact:
    closure = pinned.closure
    selection_key = closure.gate.selection_key
    work_root = Path(closure.gate.candidate_root).parent / _WORK_PARENT / selection_key
    archives = (
        ImmutableGitArchive(
            path=work_root / _ARCHIVE_NAMES[0],
            sha256=closure.double_wheel.archive_sha256[0],
            source_receipt=prepared.source_receipt,
        ),
        ImmutableGitArchive(
            path=work_root / _ARCHIVE_NAMES[1],
            sha256=closure.double_wheel.archive_sha256[1],
            source_receipt=prepared.source_receipt,
        ),
    )
    return reopen_offline_double_wheel_artifact(
        archives,
        repo_root=repo_root,
        work_root=work_root / "double-wheel",
        receipt=closure.double_wheel,
    )


def verify_w3_candidate(
    candidate_root: Path,
    *,
    repo_root: Path,
    source_acceptance_path: Path,
) -> WarehouseW3PreparedCandidateClosure:
    """Independently reopen static candidate, build, dry-root, and ingress facts."""

    _require_nonroot()
    root = _absolute_directory(repo_root, label="repo_root")
    with pin_candidate_gate_ingress(candidate_root) as pinned:
        closure = pinned.closure
        external_runtime_paths = tuple(
            Path(item.path) for item in closure.environment_content.external_runtime
        )
        prepared = verify_candidate(
            candidate_root,
            external_runtime_paths=external_runtime_paths,
        )
        if prepared.verification_receipt != closure.candidate_verification:
            raise WarehouseW3CandidateCoordinatorError(
                "candidate verification differs from ingress"
            )
        with RootFixedSourceAcceptanceAuthority.open(
            source_acceptance_path
        ) as source_authority:
            source_acceptance = source_authority.receipt
            source = GitSourceAcquirer(root).acquire(
                launch_commit=prepared.source_receipt.source_commit,
                remote_name=prepared.source_receipt.remote_name,
                remote_ref=prepared.source_receipt.remote_ref,
                logical_paths=tuple(
                    item.logical_path for item in prepared.source_receipt.blobs
                ),
            )
            if (
                source_acceptance_path
                != canonical_source_acceptance_path(source_acceptance.source_commit)
                or source.receipt != prepared.source_receipt
                or source.receipt != source_acceptance.source_receipt
                or prepared.intent.source_acceptance_sha256
                != source_acceptance.raw_sha256
                or closure.candidate_verification.source_acceptance_sha256
                != source_acceptance.raw_sha256
            ):
                raise WarehouseW3CandidateCoordinatorError(
                    "live Git/source acceptance differs from candidate"
                )
            source_authority.revalidate()
        _reverify_environment_evidence(prepared, closure)
        artifact = _reopen_build_artifact(
            pinned,
            prepared=prepared,
            repo_root=root,
        )
        if artifact.receipt != closure.double_wheel:
            raise WarehouseW3CandidateCoordinatorError(
                "live wheel artifact differs from candidate"
            )
        inspected = FilesystemCandidateCompositionInspector().inspect(
            accepted_root=Path(closure.gate.accepted_root),
            candidate_root=prepared.candidate_root,
            nonce=prepared.authority.nonce,
            manifest_sha256=prepared.intent.dry_root_manifest_sha256,
            prepared_candidate=prepared,
            candidate_verification=closure.candidate_verification,
            double_wheel=closure.double_wheel,
            semantic_environment=closure.semantic_environment,
            candidate_probe=closure.candidate_probe,
            namespace_final_probe=closure.namespace_final_probe,
            namespace_probe_ref=closure.namespace_probe_ref,
        )
        if inspected != (closure.inspection, closure.absence_facts):
            raise WarehouseW3CandidateCoordinatorError(
                "live candidate composition differs from closure"
            )
        pinned.revalidate()
        gate_path = derive_candidate_gate_ingress_paths(
            Path(closure.gate.candidate_root),
            closure.gate.selection_key,
        ).gate_path
        work_root = (
            Path(closure.gate.candidate_root).parent
            / _WORK_PARENT
            / closure.gate.selection_key
        )
    return WarehouseW3PreparedCandidateClosure(
        candidate=prepared,
        closure=closure,
        gate_path=gate_path,
        work_root=work_root,
    )


__all__ = [
    "W3_TASK_EVENT_IDENTITY",
    "WarehouseW3CandidateCoordinatorError",
    "WarehouseW3PreparedCandidateClosure",
    "prepare_w3_candidate",
    "verify_w3_candidate",
]
