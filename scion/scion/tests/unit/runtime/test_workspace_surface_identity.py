"""Regression tests for workspace identity across v0.4 research surfaces."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from scion.runtime.workspace import (
    WorkspaceMaterializer,
    editable_identity_patterns_from_problem_spec,
)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _problem_spec(
    *,
    editable=("operators/*.py",),
    surface_files=("solver_design/**/*.py",),
):
    surfaces = []
    if surface_files is not None:
        surfaces.append(
            SimpleNamespace(
                target_files=[],
                targets=SimpleNamespace(files=list(surface_files)),
            )
        )
    return SimpleNamespace(
        search_space=SimpleNamespace(editable=list(editable)),
        research_surfaces=surfaces,
    )


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


def test_identity_patterns_prefer_research_surface_targets_over_search_space() -> None:
    spec = _problem_spec(
        editable=("operators/*.py",),
        surface_files=("solver_design/**/*.py",),
    )

    assert editable_identity_patterns_from_problem_spec(spec) == (
        "solver_design/**/*.py",
    )


def test_identity_patterns_fall_back_to_search_space_editable() -> None:
    spec = _problem_spec(
        editable=("operators/*.py",),
        surface_files=None,
    )

    assert editable_identity_patterns_from_problem_spec(spec) == ("operators/*.py",)


def test_constructor_infers_problem_spec_identity_at_existing_call_sites(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    _write(workspace / "operators" / "op.py", "VALUE = 1\n")
    _write(workspace / "solver_design" / "moves.py", "VALUE = 1\n")
    _write(workspace / "data" / "case.json", '{"not": "identity"}\n')

    def build_materializer_like_campaign_composition(problem_spec):
        return WorkspaceMaterializer(
            str(tmp_path / "campaign"),
            frozen_patterns=frozenset({"solver.py"}),
        )

    materializer = build_materializer_like_campaign_composition(
        _problem_spec(
            editable=("operators/*.py",),
            surface_files=("solver_design/**/*.py",),
        )
    )

    before = materializer.compute_code_hash(str(workspace))
    _write(workspace / "operators" / "op.py", "VALUE = 2\n")
    after_operator_change = materializer.compute_code_hash(str(workspace))
    _write(workspace / "data" / "case.json", '{"not": "identity changed"}\n')
    after_data_change = materializer.compute_code_hash(str(workspace))
    _write(workspace / "solver_design" / "moves.py", "VALUE = 2\n")
    after_surface_change = materializer.compute_code_hash(str(workspace))

    assert before == after_operator_change
    assert after_operator_change == after_data_change
    assert after_data_change != after_surface_change


def test_compute_code_hash_excludes_registry_when_not_editable(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    _write(workspace / "solver_design" / "moves.py", "VALUE = 1\n")
    _write(workspace / "registry.yaml", "operators: []\n")

    materializer = WorkspaceMaterializer(
        str(tmp_path / "campaign"),
        frozen_patterns=frozenset({"solver.py"}),
        editable_patterns=("solver_design/**/*.py",),
    )

    before = materializer.compute_code_hash(str(workspace))
    _write(workspace / "registry.yaml", "operators:\n  - name: new_op\n")
    after = materializer.compute_code_hash(str(workspace))

    assert before == after


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
