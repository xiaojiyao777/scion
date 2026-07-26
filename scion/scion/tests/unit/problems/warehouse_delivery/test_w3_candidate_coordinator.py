from __future__ import annotations

import hashlib
import subprocess
import tarfile
from pathlib import Path
from types import SimpleNamespace

import pytest

import scion.problems.warehouse_delivery.w3_candidate_coordinator as coordinator
import scion.problems.warehouse_delivery.w3_wheel as w3_wheel
from scion.problems.warehouse_delivery.w3_candidate_coordinator import (
    WarehouseW3CandidateCoordinatorError,
    prepare_w3_candidate,
)
from scion.problems.warehouse_delivery.w3_candidate_gate import (
    derive_namespace_probe_evidence_sha256,
)
from scion.problems.warehouse_delivery.w3_environment import (
    WarehouseW3EnvironmentError,
    dbus_metadata_installation_path,
    is_dbus_metadata_installation_path,
)
from scion.problems.warehouse_delivery.w3_installation import (
    GitSourceAcquirer,
    WarehouseW3InstallationError,
)

COMMIT = "1" * 40


class _GitInventory:
    def __init__(self, raw: bytes) -> None:
        self.raw = raw
        self.calls: list[tuple[str, ...]] = []

    def run(self, argv, *, cwd):
        del cwd
        self.calls.append(argv)
        return self.raw


def _entry(mode: str, path: str) -> bytes:
    return f"{mode} blob {'2' * 40}\t{path}\0".encode()


def test_launch_inventory_is_sorted_regular_and_excludes_tests(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = b"".join(
        (
            _entry("100644", "scion/scion/tools/scion_w3_tool.py"),
            _entry("100644", "scion/scion/tests/test_hidden.py"),
            _entry("100644", "scion/pyproject.toml"),
            _entry("100644", "scion/scion/tools/scion_w3_install.py"),
            _entry(
                "100644",
                "scion/scion/problems/warehouse_delivery/module.py",
            ),
        )
    )
    inventory = _GitInventory(raw)
    monkeypatch.setattr(
        coordinator,
        "SubprocessGitRunner",
        lambda: inventory,
    )

    paths = coordinator._tracked_launch_paths(tmp_path, COMMIT)

    assert paths == tuple(sorted(paths))
    assert "scion/tests/test_hidden.py" not in paths
    assert "scion/tools/scion_w3_install.py" in paths
    assert inventory.calls == [
        (
            "git",
            "ls-tree",
            "-rz",
            "--full-tree",
            COMMIT,
            "--",
            ":(top,literal)scion/pyproject.toml",
            ":(top,literal)scion/scion",
        )
    ]


def test_launch_inventory_rejects_symlink_blob(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = b"".join(
        (
            _entry("100644", "scion/pyproject.toml"),
            _entry("100644", "scion/scion/tools/scion_w3_tool.py"),
            _entry("100644", "scion/scion/tools/scion_w3_install.py"),
            _entry("120000", "scion/scion/link"),
        )
    )
    monkeypatch.setattr(
        coordinator,
        "SubprocessGitRunner",
        lambda: _GitInventory(raw),
    )

    with pytest.raises(
        WarehouseW3CandidateCoordinatorError,
        match="non-regular",
    ):
        coordinator._tracked_launch_paths(tmp_path, COMMIT)


def test_launch_inventory_rejects_path_outside_fixed_project_subtree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        coordinator,
        "SubprocessGitRunner",
        lambda: _GitInventory(_entry("100644", "pyproject.toml")),
    )

    with pytest.raises(
        WarehouseW3CandidateCoordinatorError,
        match="escapes the fixed project subtree",
    ):
        coordinator._tracked_launch_paths(tmp_path, COMMIT)


def test_launch_inventory_maps_one_real_nested_git_project(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    project = repository / "scion"
    package = project / "scion" / "tools"
    tests = project / "scion" / "tests"
    package.mkdir(parents=True)
    tests.mkdir()
    (project / "pyproject.toml").write_text("[project]\nname='fixture'\n")
    (package / "scion_w3_tool.py").write_text('"""tool"""\n')
    (package / "scion_w3_install.py").write_text('"""installer"""\n')
    (tests / "test_hidden.py").write_text('"""excluded"""\n')
    subprocess.run(
        ("git", "init", "-q"),
        cwd=repository,
        check=True,
        stdin=subprocess.DEVNULL,
    )
    subprocess.run(
        ("git", "add", "--", "scion"),
        cwd=repository,
        check=True,
        stdin=subprocess.DEVNULL,
    )
    subprocess.run(
        (
            "git",
            "-c",
            "user.name=Scion Test",
            "-c",
            "user.email=scion.test@example.invalid",
            "commit",
            "-qm",
            "fixture",
        ),
        cwd=repository,
        check=True,
        stdin=subprocess.DEVNULL,
    )
    launch_commit = (
        subprocess.check_output(
            ("git", "rev-parse", "HEAD"),
            cwd=repository,
        )
        .decode("ascii")
        .strip()
    )

    paths = coordinator._tracked_launch_paths(project, launch_commit)

    assert paths == (
        "pyproject.toml",
        "scion/tools/scion_w3_install.py",
        "scion/tools/scion_w3_tool.py",
    )
    branch = (
        subprocess.check_output(
            ("git", "symbolic-ref", "--short", "HEAD"),
            cwd=repository,
        )
        .decode("ascii")
        .strip()
    )
    subprocess.run(
        ("git", "remote", "add", "origin", str(repository)),
        cwd=repository,
        check=True,
        stdin=subprocess.DEVNULL,
    )
    subprocess.run(
        (
            "git",
            "fetch",
            "-q",
            "origin",
            f"refs/heads/{branch}:refs/remotes/origin/{branch}",
        ),
        cwd=repository,
        check=True,
        stdin=subprocess.DEVNULL,
    )
    source = GitSourceAcquirer(project).acquire(
        launch_commit=launch_commit,
        remote_name="origin",
        remote_ref=f"refs/heads/{branch}",
        logical_paths=paths,
    )
    archive = coordinator._create_git_archive(
        project,
        launch_commit=launch_commit,
        logical_paths=paths,
        destination=tmp_path / "source.tar",
        source=source,
    )

    with tarfile.open(archive.path, mode="r:") as stream:
        members = {item.name: item for item in stream.getmembers()}
    assert tuple(members) == (
        "pyproject.toml",
        "scion",
        "scion/tools",
        "scion/tools/scion_w3_install.py",
        "scion/tools/scion_w3_tool.py",
    )
    assert all(
        item.mode == (0o755 if item.isdir() else 0o644) for item in members.values()
    )
    source_date_epoch = int(
        subprocess.check_output(
            ("git", "show", "-s", "--format=%ct", launch_commit),
            cwd=repository,
        ).decode("ascii")
    )
    inventory, _aggregate, _identity = w3_wheel._archive_inventory(
        archive,
        source_date_epoch=source_date_epoch,
    )
    assert tuple(item.path for item in inventory) == (
        ".",
        "pyproject.toml",
        "scion",
        "scion/tools",
        "scion/tools/scion_w3_install.py",
        "scion/tools/scion_w3_tool.py",
    )


def test_namespace_evidence_digest_binds_all_four_inputs() -> None:
    digest = derive_namespace_probe_evidence_sha256(b"a", b"b", b"c", b"d")
    assert (
        digest
        == hashlib.sha256(
            b"scion.w3-candidate-namespace-final-probe-evidence.v1\0abcd"
        ).hexdigest()
    )
    assert digest != derive_namespace_probe_evidence_sha256(b"a", b"b", b"c", b"e")


def test_generated_wheel_provenance_deduplicates_equal_archive_content(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wheel_raw = b"deterministic wheel bytes"
    wheel_path = tmp_path / "scion.whl"
    wheel_path.write_bytes(wheel_raw)
    source_sha256 = hashlib.sha256(b"source receipt").hexdigest()
    archive_sha256 = hashlib.sha256(b"equal archive bytes").hexdigest()
    wheel_sha256 = hashlib.sha256(wheel_raw).hexdigest()
    captured: list[dict[str, object]] = []

    def generated(**kwargs: object) -> object:
        captured.append(kwargs)
        return kwargs["logical_path"]

    monkeypatch.setattr(
        coordinator,
        "SealedStoreObject",
        SimpleNamespace(generated=generated),
    )
    source = SimpleNamespace(
        blobs=(
            SimpleNamespace(
                logical_path="scion/problems/warehouse_delivery/w3_wheel.py",
                sha256=hashlib.sha256(b"generator").hexdigest(),
            ),
        ),
        receipt=SimpleNamespace(raw_sha256=source_sha256),
    )
    artifact = SimpleNamespace(
        wheel_path=wheel_path,
        receipt=SimpleNamespace(
            wheel_size_bytes=len(wheel_raw),
            wheel_sha256=wheel_sha256,
            archive_sha256=(archive_sha256, archive_sha256),
            raw=b'{"wheel":"receipt"}\n',
            raw_sha256=hashlib.sha256(b'{"wheel":"receipt"}\n').hexdigest(),
        ),
    )

    coordinator._generated_store_objects(source, artifact)

    assert captured[0]["input_sha256"] == tuple(sorted((source_sha256, archive_sha256)))
    assert captured[1]["input_sha256"] == (source_sha256, wheel_sha256)


def test_prepare_candidate_rejects_root_before_any_path_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(coordinator.os, "geteuid", lambda: 0)
    with pytest.raises(PermissionError):
        prepare_w3_candidate(
            Path("/absent"),
            repo_root=Path("/absent"),
            launch_commit=COMMIT,
            remote_name="origin",
            remote_ref="refs/heads/test",
            native_record_path=Path("/absent"),
            runtime_python=Path("/usr/bin/python3.12"),
            source_acceptance_path=Path("/absent"),
        )


def test_prepare_candidate_rejects_runtime_drift_before_any_path_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(coordinator.os, "geteuid", lambda: 1001)
    monkeypatch.setattr(
        coordinator,
        "_runtime_sources",
        lambda: (_ for _ in ()).throw(AssertionError("runtime sources were read")),
    )
    with pytest.raises(
        WarehouseW3EnvironmentError,
        match="runtime_python differs from fixed runtime",
    ):
        prepare_w3_candidate(
            Path("/absent"),
            repo_root=Path("/absent"),
            launch_commit=COMMIT,
            remote_name="origin",
            remote_ref="refs/heads/test",
            native_record_path=Path("/absent"),
            runtime_python=Path("/wrong/python3.12"),
            source_acceptance_path=Path("/absent"),
        )


@pytest.mark.parametrize("native_mode", (0o444, 0o555, 0o644))
def test_prepare_candidate_rejects_native_mode_before_work_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    native_mode: int,
) -> None:
    accepted_root = tmp_path / "accepted-root"
    repo_root = tmp_path / "repo"
    accepted_root.mkdir()
    repo_root.mkdir()
    manifest_raw = b'{"accepted":"manifest"}\n'
    manifest_path = accepted_root / coordinator.EXPECTED_MANIFEST_NAME
    manifest_path.write_bytes(manifest_raw)
    manifest_path.chmod(0o600)
    native_path = tmp_path / "native-record.json"
    native_path.write_bytes(b'{"accepted":"native"}\n')
    native_path.chmod(native_mode)

    monkeypatch.setattr(coordinator.os, "geteuid", lambda: 1001)
    monkeypatch.setattr(coordinator, "validate_runtime_python", lambda _path: None)
    monkeypatch.setattr(coordinator, "_runtime_sources", lambda: object())
    monkeypatch.setattr(
        coordinator,
        "EXPECTED_MANIFEST_SHA256",
        hashlib.sha256(manifest_raw).hexdigest(),
    )
    monkeypatch.setattr(
        coordinator,
        "_prepare_work_root",
        lambda *_args: (_ for _ in ()).throw(
            AssertionError("work root was created before external acquisition")
        ),
    )

    with pytest.raises(
        WarehouseW3InstallationError,
        match="not one accepted single-link regular file",
    ):
        prepare_w3_candidate(
            accepted_root,
            repo_root=repo_root,
            launch_commit=COMMIT,
            remote_name="origin",
            remote_ref="refs/heads/test",
            native_record_path=native_path,
            runtime_python=Path("/usr/bin/python3.12"),
            source_acceptance_path=tmp_path / "absent-source-acceptance.json",
        )


def test_prepare_candidate_acquires_all_external_roles_before_work_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    accepted_root = tmp_path / "accepted-root"
    repo_root = tmp_path / "repo"
    accepted_root.mkdir()
    repo_root.mkdir()
    manifest_raw = b'{"accepted":"manifest"}\n'
    native_raw = b'{"accepted":"native"}\n'
    source_acceptance_raw = b'{"accepted":"root-source"}\n'
    launch_commit = "12" * 20
    launch_tree = "23" * 20
    manifest_path = accepted_root / coordinator.EXPECTED_MANIFEST_NAME
    native_path = tmp_path / "native-record.json"
    source_acceptance_path = tmp_path / "source-acceptance.json"
    for path, raw, mode in (
        (manifest_path, manifest_raw, 0o600),
        (native_path, native_raw, 0o600),
        (source_acceptance_path, source_acceptance_raw, 0o444),
    ):
        path.write_bytes(raw)
        path.chmod(mode)

    source_receipt = SimpleNamespace(
        source_commit=launch_commit,
        source_tree=launch_tree,
    )
    source = SimpleNamespace(receipt=source_receipt, blobs=())
    source_acceptance = SimpleNamespace(
        source_commit=launch_commit,
        source_receipt=source_receipt,
        raw=source_acceptance_raw,
        raw_sha256=hashlib.sha256(source_acceptance_raw).hexdigest(),
    )

    class SourceAuthority:
        receipt = source_acceptance

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def revalidate(self):
            return None

    class SourceAcquirer:
        def __init__(self, _repo_root):
            pass

        def acquire(self, **_kwargs):
            return source

    original_external = coordinator.SealedStoreObject.external_evidence
    acquired: list[tuple[str, int]] = []

    def capture_external(_cls, **kwargs):
        acquired.append((str(kwargs["logical_path"]), int(kwargs["source_mode"])))
        return original_external(**kwargs)

    class WorkRootReached(RuntimeError):
        pass

    def stop_at_work_root(*_args):
        assert acquired == [
            (coordinator.EXPECTED_MANIFEST_NAME, 0o600),
            (coordinator.W3_NATIVE_RECORD_LOGICAL_PATH, 0o600),
            (coordinator.W3_SOURCE_ACCEPTANCE_LOGICAL_PATH, 0o444),
        ]
        raise WorkRootReached

    monkeypatch.setattr(coordinator.os, "geteuid", lambda: 1001)
    monkeypatch.setattr(coordinator, "validate_runtime_python", lambda _path: None)
    monkeypatch.setattr(coordinator, "_runtime_sources", lambda: object())
    monkeypatch.setattr(
        coordinator,
        "EXPECTED_MANIFEST_SHA256",
        hashlib.sha256(manifest_raw).hexdigest(),
    )
    monkeypatch.setattr(
        coordinator,
        "EXPECTED_NATIVE_ACCEPTANCE_RECORD_SHA256",
        hashlib.sha256(native_raw).hexdigest(),
    )
    monkeypatch.setattr(
        coordinator.RootFixedSourceAcceptanceAuthority,
        "open",
        lambda _path: SourceAuthority(),
    )
    monkeypatch.setattr(
        coordinator,
        "canonical_source_acceptance_path",
        lambda _commit: source_acceptance_path,
    )
    monkeypatch.setattr(coordinator, "_tracked_launch_paths", lambda *_args: ("x",))
    monkeypatch.setattr(coordinator, "GitSourceAcquirer", SourceAcquirer)
    monkeypatch.setattr(
        coordinator,
        "CandidateSelectionIntent",
        SimpleNamespace(
            create=lambda **_kwargs: SimpleNamespace(selection_key="34" * 32)
        ),
    )
    monkeypatch.setattr(
        coordinator.SealedStoreObject,
        "external_evidence",
        classmethod(capture_external),
    )
    monkeypatch.setattr(coordinator, "_prepare_work_root", stop_at_work_root)

    with pytest.raises(WorkRootReached):
        prepare_w3_candidate(
            accepted_root,
            repo_root=repo_root,
            launch_commit=launch_commit,
            remote_name="origin",
            remote_ref="refs/heads/test",
            native_record_path=native_path,
            runtime_python=Path("/usr/bin/python3.12"),
            source_acceptance_path=source_acceptance_path,
        )


def test_runtime_package_sources_close_on_the_fixed_host_paths() -> None:
    sources = coordinator._runtime_sources()
    sources.validate()
    assert sources.dbus_package == Path("/usr/lib/python3/dist-packages/dbus")
    assert sources.yaml_package == Path("/usr/lib/python3/dist-packages/yaml")
    metadata_path = dbus_metadata_installation_path(sources.dbus_metadata)
    assert metadata_path == (
        "lib/python3.12/site-packages/" f"{sources.dbus_metadata.name}/PKG-INFO"
    )
    assert is_dbus_metadata_installation_path(metadata_path)


def test_candidate_reopen_rehashes_and_reprobes_both_relocation_roots(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate_probe = SimpleNamespace(raw=b"candidate")
    namespace_probe = SimpleNamespace(raw=b"namespace")
    namespace_execution = SimpleNamespace(raw=b"execution")
    semantic = SimpleNamespace(raw=b"semantic")
    candidate_root = tmp_path / "selection" / "candidate"
    simulated_root = tmp_path / "simulated-final"
    prepared = SimpleNamespace(
        candidate_root=candidate_root,
        intent=SimpleNamespace(selection_directory=str(candidate_root.parent)),
    )
    closure = SimpleNamespace(
        environment_content=SimpleNamespace(
            external_runtime=(SimpleNamespace(path="/runtime"),),
        ),
        semantic_environment=semantic,
        candidate_probe=candidate_probe,
        namespace_final_probe=namespace_probe,
        namespace_probe_execution=namespace_execution,
        namespace_probe_ref=SimpleNamespace(
            physical_environment_root=str(simulated_root),
            evidence_receipt_sha256=derive_namespace_probe_evidence_sha256(
                semantic.raw,
                candidate_probe.raw,
                namespace_probe.raw,
                namespace_execution.raw,
            ),
        ),
    )
    rehashed: list[Path] = []
    probed: list[tuple[Path, str]] = []

    def verify(root, receipt, **kwargs):
        del receipt, kwargs
        rehashed.append(root)

    class Probe:
        def probe(self, root, *, phase, content_receipt):
            assert content_receipt is semantic
            probed.append((root, phase))
            return candidate_probe

    class NamespaceProbe:
        def probe(self, root, *, content_receipt):
            assert content_receipt is semantic
            probed.append((root, "namespace_final"))
            return namespace_probe, namespace_execution

    monkeypatch.setattr(coordinator, "verify_environment_content", verify)
    monkeypatch.setattr(
        coordinator,
        "SubprocessEnvironmentProbeReader",
        Probe,
    )
    monkeypatch.setattr(
        coordinator,
        "NonRootNamespaceEnvironmentProbeReader",
        NamespaceProbe,
    )

    coordinator._reverify_environment_evidence(prepared, closure)

    assert rehashed == [candidate_root / "environment", simulated_root]
    assert probed == [
        (candidate_root / "environment", "candidate"),
        (simulated_root, "namespace_final"),
    ]


def test_candidate_reopen_rejects_changed_relocation_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate_probe = SimpleNamespace(raw=b"candidate")
    namespace_probe = SimpleNamespace(raw=b"namespace")
    namespace_execution = SimpleNamespace(raw=b"execution")
    prepared = SimpleNamespace(
        candidate_root=tmp_path / "candidate",
        intent=SimpleNamespace(selection_directory=str(tmp_path)),
    )
    closure = SimpleNamespace(
        environment_content=SimpleNamespace(external_runtime=()),
        semantic_environment=SimpleNamespace(raw=b"semantic"),
        candidate_probe=candidate_probe,
        namespace_final_probe=namespace_probe,
        namespace_probe_execution=namespace_execution,
        namespace_probe_ref=SimpleNamespace(
            physical_environment_root=str(tmp_path / "simulated"),
            evidence_receipt_sha256="0" * 64,
        ),
    )

    monkeypatch.setattr(
        coordinator,
        "verify_environment_content",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        coordinator,
        "SubprocessEnvironmentProbeReader",
        lambda: SimpleNamespace(probe=lambda *args, **kwargs: candidate_probe),
    )
    monkeypatch.setattr(
        coordinator,
        "NonRootNamespaceEnvironmentProbeReader",
        lambda: SimpleNamespace(
            probe=lambda *args, **kwargs: (
                namespace_probe,
                namespace_execution,
            )
        ),
    )

    with pytest.raises(
        WarehouseW3CandidateCoordinatorError,
        match="relocation evidence",
    ):
        coordinator._reverify_environment_evidence(prepared, closure)
