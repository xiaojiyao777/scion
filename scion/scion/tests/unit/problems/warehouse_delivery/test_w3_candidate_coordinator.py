from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

import scion.problems.warehouse_delivery.w3_candidate_coordinator as coordinator
from scion.problems.warehouse_delivery.w3_candidate_coordinator import (
    WarehouseW3CandidateCoordinatorError,
    prepare_w3_candidate,
)

COMMIT = "1" * 40


class _GitInventory:
    def __init__(self, raw: bytes) -> None:
        self.raw = raw

    def run(self, argv, *, cwd):
        del argv, cwd
        return self.raw


def _entry(mode: str, path: str) -> bytes:
    return f"{mode} blob {'2' * 40}\t{path}\0".encode()


def test_launch_inventory_is_sorted_regular_and_excludes_tests(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = b"".join(
        (
            _entry("100644", "scion/tools/scion_w3_tool.py"),
            _entry("100644", "scion/tests/test_hidden.py"),
            _entry("100644", "pyproject.toml"),
            _entry("100644", "scion/tools/scion_w3_install.py"),
            _entry("100644", "scion/problems/warehouse_delivery/module.py"),
        )
    )
    monkeypatch.setattr(
        coordinator,
        "SubprocessGitRunner",
        lambda: _GitInventory(raw),
    )

    paths = coordinator._tracked_launch_paths(tmp_path, COMMIT)

    assert paths == tuple(sorted(paths))
    assert "scion/tests/test_hidden.py" not in paths
    assert "scion/tools/scion_w3_install.py" in paths


def test_launch_inventory_rejects_symlink_blob(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = b"".join(
        (
            _entry("100644", "pyproject.toml"),
            _entry("100644", "scion/tools/scion_w3_tool.py"),
            _entry("100644", "scion/tools/scion_w3_install.py"),
            _entry("120000", "scion/link"),
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


def test_simulated_evidence_digest_binds_all_three_inputs() -> None:
    digest = coordinator._simulated_evidence_sha256(b"a", b"b", b"c")
    assert (
        digest
        == hashlib.sha256(
            b"scion.w3-candidate-simulated-relocation-evidence.v1\0abc"
        ).hexdigest()
    )
    assert digest != coordinator._simulated_evidence_sha256(b"a", b"b", b"d")


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
    simulated_probe = SimpleNamespace(raw=b"simulated")
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
        simulated_final_probe=simulated_probe,
        simulated_relocation=SimpleNamespace(
            simulated_final_environment_root=str(simulated_root),
            evidence_receipt_sha256=coordinator._simulated_evidence_sha256(
                semantic.raw,
                candidate_probe.raw,
                simulated_probe.raw,
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
            return candidate_probe if phase == "candidate" else simulated_probe

    monkeypatch.setattr(coordinator, "verify_environment_content", verify)
    monkeypatch.setattr(
        coordinator,
        "SubprocessEnvironmentProbeReader",
        Probe,
    )

    coordinator._reverify_environment_evidence(prepared, closure)

    assert rehashed == [candidate_root / "environment", simulated_root]
    assert probed == [
        (candidate_root / "environment", "candidate"),
        (simulated_root, "simulated_final"),
    ]


def test_candidate_reopen_rejects_changed_relocation_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate_probe = SimpleNamespace(raw=b"candidate")
    simulated_probe = SimpleNamespace(raw=b"simulated")
    prepared = SimpleNamespace(
        candidate_root=tmp_path / "candidate",
        intent=SimpleNamespace(selection_directory=str(tmp_path)),
    )
    closure = SimpleNamespace(
        environment_content=SimpleNamespace(external_runtime=()),
        semantic_environment=SimpleNamespace(raw=b"semantic"),
        candidate_probe=candidate_probe,
        simulated_final_probe=simulated_probe,
        simulated_relocation=SimpleNamespace(
            simulated_final_environment_root=str(tmp_path / "simulated"),
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
        lambda: SimpleNamespace(
            probe=lambda *args, **kwargs: (
                candidate_probe if kwargs["phase"] == "candidate" else simulated_probe
            )
        ),
    )

    with pytest.raises(
        WarehouseW3CandidateCoordinatorError,
        match="relocation evidence",
    ):
        coordinator._reverify_environment_evidence(prepared, closure)
