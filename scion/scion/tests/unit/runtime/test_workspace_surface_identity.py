from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from scion.core.research_surface_index import editable_patterns
from scion.core.models import PatchProposal
from scion.runtime.workspace import (
    FrozenFileError,
    WorkspaceMaterializer,
)


def test_editable_patterns_prefer_research_surfaces() -> None:
    spec = SimpleNamespace(
        research_surfaces=[
            SimpleNamespace(
                targets=SimpleNamespace(files=["surfaces/", "surfaces/*.py"])
            ),
            SimpleNamespace(target_files=["legacy_surface.py", "surfaces/*.py"]),
        ],
        search_space=SimpleNamespace(editable=["operators/*.py"]),
    )

    assert editable_patterns(spec) == (
        "surfaces",
        "surfaces/*.py",
        "legacy_surface.py",
    )


def test_editable_patterns_fall_back_to_search_space() -> None:
    spec = SimpleNamespace(
        research_surfaces=[],
        search_space=SimpleNamespace(editable=["operators/*.py", "policies/*.py"]),
    )

    assert editable_patterns(spec) == ("operators/*.py", "policies/*.py")


def test_editable_patterns_reject_unsafe_paths() -> None:
    spec = SimpleNamespace(
        research_surfaces=[
            SimpleNamespace(targets=SimpleNamespace(files=["../outside.py"]))
        ],
        search_space=SimpleNamespace(editable=["operators/*.py"]),
    )

    with pytest.raises(ValueError, match="glob pattern"):
        editable_patterns(spec)


def test_explicit_surface_hash_tracks_non_legacy_surface_only(tmp_path: Path) -> None:
    ws = _workspace(tmp_path)
    materializer = WorkspaceMaterializer(
        str(tmp_path / "campaign"),
        editable_patterns=("surfaces/*.py",),
    )

    code_hash = materializer.compute_code_hash(str(ws))

    _write(ws / "surfaces" / "heuristic.py", "VALUE = 2\n")
    assert materializer.compute_code_hash(str(ws)) != code_hash

    code_hash = materializer.compute_code_hash(str(ws))
    _write(ws / "data" / "case.json", '{"changed": true}\n')
    _write(ws / "tests" / "test_surface.py", "def test_changed(): pass\n")

    assert materializer.compute_code_hash(str(ws)) == code_hash

def test_explicit_archive_copies_only_editable_non_frozen_files(tmp_path: Path) -> None:
    ws = _workspace(tmp_path)
    materializer = WorkspaceMaterializer(
        str(tmp_path / "campaign"),
        frozen_patterns=frozenset({"surfaces/frozen.py"}),
        editable_patterns=("surfaces",),
    )

    archive = materializer.archive_workspace(str(ws), branch_id="branch-abcdef")

    assert archive is not None
    archived_files = _relative_files(Path(archive))
    assert archived_files == [
        "surfaces/heuristic.py",
        "surfaces/pkg/helper.py",
    ]


def test_default_materializer_does_not_freeze_legacy_vrp_files(
    tmp_path: Path,
) -> None:
    ws = _workspace(tmp_path)
    materializer = WorkspaceMaterializer(str(tmp_path / "campaign"))

    for file_path in ("solver.py", "vns.py", "pool.py", "operators/base.py"):
        materializer.apply_patch(
            str(ws),
            PatchProposal(
                file_path=file_path,
                action="modify",
                code_content=f"# editable {file_path}\n",
            ),
        )

    assert (ws / "solver.py").read_text(encoding="utf-8") == "# editable solver.py\n"
    assert (ws / "vns.py").read_text(encoding="utf-8") == "# editable vns.py\n"
    assert (ws / "pool.py").read_text(encoding="utf-8") == "# editable pool.py\n"
    assert (ws / "operators" / "base.py").read_text(
        encoding="utf-8"
    ) == "# editable operators/base.py\n"


def test_explicit_problem_frozen_patterns_still_reject_files(
    tmp_path: Path,
) -> None:
    ws = _workspace(tmp_path)
    materializer = WorkspaceMaterializer(
        str(tmp_path / "campaign"),
        frozen_patterns=frozenset({"solver.py", "vns.py"}),
    )

    with pytest.raises(FrozenFileError):
        materializer.apply_patch(
            str(ws),
            PatchProposal(
                file_path="solver.py",
                action="modify",
                code_content="# rejected\n",
            ),
        )

    with pytest.raises(FrozenFileError):
        materializer.apply_patch(
            str(ws),
            PatchProposal(
                file_path="vns.py",
                action="modify",
                code_content="# rejected\n",
            ),
        )


def test_explicit_empty_frozen_patterns_do_not_reinstate_legacy_defaults(
    tmp_path: Path,
) -> None:
    ws = _workspace(tmp_path)
    materializer = WorkspaceMaterializer(
        str(tmp_path / "campaign"),
        frozen_patterns=frozenset(),
        editable_patterns=("solver.py", "vns.py"),
    )

    code_hash = materializer.compute_code_hash(str(ws))
    _write(ws / "operators" / "legacy.py", "VALUE = 2\n")
    assert materializer.compute_code_hash(str(ws)) == code_hash

    _write(ws / "solver.py", "VALUE = 2\n")
    assert materializer.compute_code_hash(str(ws)) != code_hash

    archive = materializer.archive_workspace(str(ws), branch_id="surface-branch")
    assert archive is not None
    assert _relative_files(Path(archive)) == ["solver.py", "vns.py"]


def test_default_materializer_has_no_selected_editable_files(tmp_path: Path) -> None:
    ws = _workspace(tmp_path)
    materializer = WorkspaceMaterializer(str(tmp_path / "campaign"))

    code_hash = materializer.compute_code_hash(str(ws))
    _write(ws / "surfaces" / "heuristic.py", "VALUE = 99\n")
    _write(ws / "data" / "case.json", '{"changed": true}\n')
    _write(ws / "operators" / "legacy.py", "VALUE = 2\n")
    _write(ws / "policies" / "legacy_policy.py", "VALUE = 2\n")
    assert materializer.compute_code_hash(str(ws)) == code_hash

    assert materializer.archive_workspace(str(ws), branch_id="default-branch") is None


def test_explicit_operators_policies_patterns_keep_legacy_behavior(
    tmp_path: Path,
) -> None:
    ws = _workspace(tmp_path)
    materializer = WorkspaceMaterializer(
        str(tmp_path / "campaign"),
        editable_patterns=("operators/*.py", "policies/*.py"),
    )

    code_hash = materializer.compute_code_hash(str(ws))
    _write(ws / "surfaces" / "heuristic.py", "VALUE = 99\n")
    _write(ws / "data" / "case.json", '{"changed": true}\n')
    assert materializer.compute_code_hash(str(ws)) == code_hash

    _write(ws / "operators" / "legacy.py", "VALUE = 2\n")
    assert materializer.compute_code_hash(str(ws)) != code_hash

    archive = materializer.archive_workspace(str(ws), branch_id="legacy-branch")
    assert archive is not None
    archived_files = _relative_files(Path(archive))
    assert archived_files == [
        "operators/legacy.py",
        "policies/legacy_policy.py",
    ]


def test_registry_changes_code_digest_only_when_declared_editable(tmp_path: Path) -> None:
    ws = _workspace(tmp_path)
    materializer = WorkspaceMaterializer(
        str(tmp_path / "campaign"),
        editable_patterns=("surfaces/*.py",),
    )

    code_hash = materializer.compute_code_hash(str(ws))
    _write(ws / "registry.yaml", "operators:\n- name: changed\n")

    assert materializer.compute_code_hash(str(ws)) == code_hash

    registry_materializer = WorkspaceMaterializer(
        str(tmp_path / "campaign-registry"),
        editable_patterns=("surfaces/*.py", "registry.yaml"),
    )
    code_hash = registry_materializer.compute_code_hash(str(ws))
    _write(ws / "registry.yaml", "operators:\n- name: changed_again\n")

    assert registry_materializer.compute_code_hash(str(ws)) != code_hash


def _workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "workspace"
    _write(ws / "operators" / "legacy.py", "VALUE = 1\n")
    _write(ws / "operators" / "notes.txt", "not code\n")
    _write(ws / "policies" / "legacy_policy.py", "VALUE = 1\n")
    _write(ws / "surfaces" / "heuristic.py", "VALUE = 1\n")
    _write(ws / "surfaces" / "frozen.py", "VALUE = 1\n")
    _write(ws / "surfaces" / "pkg" / "helper.py", "VALUE = 1\n")
    _write(ws / "data" / "case.json", "{}\n")
    _write(ws / "tests" / "test_surface.py", "def test_demo(): pass\n")
    _write(ws / "registry.yaml", "operators: []\n")
    _write(ws / "solver.py", "VALUE = 1\n")
    _write(ws / "vns.py", "VALUE = 1\n")
    _write(ws / "pool.py", "VALUE = 1\n")
    return ws


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _relative_files(root: Path) -> list[str]:
    return sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
    )
