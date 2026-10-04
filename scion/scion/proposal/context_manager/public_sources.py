"""Read explicitly public development dependencies without widening edit access."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from scion.core.path_match import segment_glob_match
from scion.verification.development import (
    declared_development_problem_package_paths,
    declared_development_workspace_paths,
    validate_development_closure_boundary,
)

from .io import _read_solver_design_context_artifact


def public_support_sources(
    problem_spec: Any,
    *,
    source_root: str,
    split_manifest: Any | None = None,
) -> list[dict[str, Any]]:
    """Expose only declared source closures, never test-support data discovery.

    Workspace support uses the selected complete algorithm tree. Package support
    uses the frozen problem root, exactly as in development execution. Neither
    falls back to a champion or searches for undeclared imports.
    """

    spec = getattr(problem_spec, "spec_v1", problem_spec)
    workspace_paths = declared_development_workspace_paths(spec)
    package_paths = declared_development_problem_package_paths(spec)
    if not workspace_paths and not package_paths:
        return []
    if set(workspace_paths) & set(package_paths):
        raise ValueError("public dependency paths alias workspace and problem package")
    validate_development_closure_boundary(
        problem_spec=spec,
        suites=(),
        workspace_paths=workspace_paths,
        problem_package_paths=package_paths,
        split_manifest=split_manifest,
        champion_root=source_root,
    )
    # Also validate the actual selected workspace locations, not just the
    # problem-root declarations: a split may name a branch file absolutely.
    selected_spec = SimpleNamespace(
        root_dir=source_root,
        canary_case_path=getattr(spec, "canary_case_path", ""),
    )
    validate_development_closure_boundary(
        problem_spec=selected_spec,
        suites=(),
        workspace_paths=workspace_paths,
        problem_package_paths=(),
        split_manifest=split_manifest,
        champion_root=getattr(spec, "root_dir", None),
    )
    editable = tuple(spec.search_space.editable)
    frozen = tuple(spec.search_space.frozen)
    records: list[dict[str, Any]] = []
    for paths, root in (
        (workspace_paths, source_root),
        (package_paths, str(spec.root_dir)),
    ):
        for path in paths:
            if any(
                segment_glob_match(path, pattern) for pattern in editable
            ) and not any(segment_glob_match(path, pattern) for pattern in frozen):
                raise ValueError(f"public dependency overlaps editable source: {path}")
            artifact = _read_solver_design_context_artifact(
                path,
                source_root=root,
                champion_root="",
                allow_champion_fallback=False,
            )
            content = artifact.get("content")
            if not artifact.get("readable") or not isinstance(content, str):
                raise ValueError(f"public dependency is unreadable: {path}")
            records.append({"path": path, "content": content, "visible": True})
    return records
