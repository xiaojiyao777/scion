from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

import scion.problems.warehouse_delivery.w3_candidate_coordinator as coordinator
from scion.problems.warehouse_delivery.w3_candidate_coordinator import (
    WarehouseW3CandidateCoordinatorError,
    prepare_w3_candidate,
)
from scion.problems.warehouse_delivery.w3_candidate_gate import (
    derive_namespace_probe_evidence_sha256,
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


def test_namespace_evidence_digest_binds_all_four_inputs() -> None:
    digest = derive_namespace_probe_evidence_sha256(b"a", b"b", b"c", b"d")
    assert (
        digest
        == hashlib.sha256(
            b"scion.w3-candidate-namespace-final-probe-evidence.v1\0abcd"
        ).hexdigest()
    )
    assert digest != derive_namespace_probe_evidence_sha256(b"a", b"b", b"c", b"e")


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


def test_runtime_package_sources_close_on_the_fixed_host_paths() -> None:
    sources = coordinator._runtime_sources()
    sources.validate()
    assert sources.dbus_package == Path("/usr/lib/python3/dist-packages/dbus")
    assert sources.yaml_package == Path("/usr/lib/python3/dist-packages/yaml")


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
