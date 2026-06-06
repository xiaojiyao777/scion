"""Regression tests for workspace identity across v0.4 research surfaces."""
from __future__ import annotations

from pathlib import Path

from scion.runtime.workspace import WorkspaceMaterializer


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_configured_surface_hash_includes_non_operator_file(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    _write(workspace / "solver_design" / "moves.py", "VALUE = 1\n")

    materializer = WorkspaceMaterializer(
        str(tmp_path / "campaign"),
        frozen_patterns=frozenset({"solver.py"}),
        editable_patterns=("solver_design/**/*.py",),
    )

    before = materializer.compute_code_hash(str(workspace))
    _write(workspace / "solver_design" / "moves.py", "VALUE = 2\n")
    after = materializer.compute_code_hash(str(workspace))

    assert before != after


def test_spec_boundary_fallback_hashes_non_frozen_source_surfaces(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    _write(workspace / "solver.py", "FROZEN = 1\n")
    _write(workspace / "solver_design" / "moves.py", "VALUE = 1\n")
    _write(workspace / "artifacts" / "run.json", '{"noise": 1}\n')

    # Campaign composition already passes explicit frozen patterns from the problem
    # spec. Even before a full editable-surface index is threaded through every
    # caller, this mode must not collapse identity back to operators/policies only.
    materializer = WorkspaceMaterializer(
        str(tmp_path / "campaign"),
        frozen_patterns=frozenset({"solver.py"}),
    )

    before = materializer.compute_code_hash(str(workspace))
    _write(workspace / "solver_design" / "moves.py", "VALUE = 2\n")
    after_surface_change = materializer.compute_code_hash(str(workspace))
    _write(workspace / "artifacts" / "run.json", '{"noise": 2}\n')
    after_artifact_change = materializer.compute_code_hash(str(workspace))

    assert before != after_surface_change
    assert after_surface_change == after_artifact_change


def test_snapshot_hash_includes_configured_surface_and_registry(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    _write(workspace / "solver_design" / "moves.py", "VALUE = 1\n")
    _write(workspace / "registry.yaml", "operators: []\n")

    materializer = WorkspaceMaterializer(
        str(tmp_path / "campaign"),
        frozen_patterns=frozenset({"solver.py"}),
        editable_patterns=("solver_design/**/*.py",),
    )

    before = materializer.compute_snapshot_hash(str(workspace))
    _write(workspace / "solver_design" / "moves.py", "VALUE = 2\n")
    after_surface_change = materializer.compute_snapshot_hash(str(workspace))
    _write(workspace / "registry.yaml", "operators:\n  - name: new_op\n")
    after_registry_change = materializer.compute_snapshot_hash(str(workspace))

    assert before != after_surface_change
    assert after_surface_change != after_registry_change


def test_archive_preserves_configured_surface_files(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    _write(workspace / "solver_design" / "moves.py", "VALUE = 1\n")
    _write(workspace / "notes.md", "not research evidence\n")

    materializer = WorkspaceMaterializer(
        str(tmp_path / "campaign"),
        frozen_patterns=frozenset({"solver.py"}),
        editable_patterns=("solver_design/**/*.py",),
    )

    archive = materializer.archive_workspace(str(workspace), "12345678-branch")

    assert archive is not None
    archive_root = Path(archive)
    assert (archive_root / "solver_design" / "moves.py").read_text(encoding="utf-8") == "VALUE = 1\n"
    assert not (archive_root / "notes.md").exists()


def test_legacy_hash_mode_remains_operator_policy_only(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    _write(workspace / "operators" / "op.py", "VALUE = 1\n")
    _write(workspace / "solver_design" / "moves.py", "VALUE = 1\n")

    materializer = WorkspaceMaterializer(str(tmp_path / "campaign"))

    before = materializer.compute_code_hash(str(workspace))
    _write(workspace / "solver_design" / "moves.py", "VALUE = 2\n")
    after_non_legacy_change = materializer.compute_code_hash(str(workspace))
    _write(workspace / "operators" / "op.py", "VALUE = 2\n")
    after_operator_change = materializer.compute_code_hash(str(workspace))

    assert before == after_non_legacy_change
    assert after_non_legacy_change != after_operator_change
