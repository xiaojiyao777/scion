"""Module loading helpers for CVRP adapter previews."""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
import shutil
import stat
import sys
import tempfile
import types

from scion.core.models import PatchProposal, patch_file_changes
from scion.core.paths import normalize_relative_patch_path
from scion.problems.cvrp.preview.paths import (
    _is_baseline_algorithm_path,
    _is_solver_design_module_path,
)
from scion.problems.cvrp.solver_runtime.policy_modules import _load_policy_module


@contextmanager
def _policy_preview_module(
    *,
    file_path: str,
    code: str,
    patch: PatchProposal | None = None,
    base_workspace: str | None = None,
) -> Iterator[types.ModuleType]:
    """Load a CVRP policy module against a branch-current preview workspace."""

    with tempfile.TemporaryDirectory(prefix="scion_cvrp_policy_preview_") as tmp:
        workspace = Path(tmp) / "workspace"
        _materialize_policy_preview_workspace(
            workspace,
            patch=patch,
            file_path=file_path,
            code=code,
            base_workspace=base_workspace,
        )
        target = workspace / normalize_relative_patch_path(file_path)
        with _temporary_policy_import_context(workspace):
            yield _load_policy_module(target)


def _module_from_policy_code(file_path: str, code: str) -> types.ModuleType:
    with _policy_preview_module(file_path=file_path, code=code) as module:
        return module


def _materialize_policy_preview_workspace(
    workspace: Path,
    *,
    patch: PatchProposal | None,
    file_path: str,
    code: str,
    base_workspace: str | None,
) -> None:
    workspace.mkdir(parents=True, exist_ok=True)
    base = _preview_base_workspace(base_workspace)
    if base is not None and (base / "policies").is_dir():
        shutil.copytree(
            base / "policies",
            workspace / "policies",
            ignore=shutil.ignore_patterns(
                "__pycache__",
                "*.pyc",
                ".pytest_cache",
                ".mypy_cache",
                ".ruff_cache",
            ),
        )
    _ensure_policy_packages(workspace)
    if patch is not None:
        for change in patch_file_changes(patch):
            rel = normalize_relative_patch_path(change.file_path)
            if not _is_policy_preview_path(rel):
                continue
            target = workspace / rel
            action = str(change.action or "modify")
            if action in {"modify", "create", "add", "create_new"}:
                _ensure_preview_path_writable(target.parent)
                target.parent.mkdir(parents=True, exist_ok=True)
                _ensure_preview_path_writable(target)
                target.write_text(str(change.code_content or ""), encoding="utf-8")
            elif action == "delete":
                if target.exists():
                    _ensure_preview_path_writable(target.parent)
                    _ensure_preview_path_writable(target)
                    target.unlink()
            else:
                raise ValueError(f"unsupported preview patch action: {action}")
        return
    rel = normalize_relative_patch_path(file_path)
    target = workspace / rel
    _ensure_preview_path_writable(target.parent)
    target.parent.mkdir(parents=True, exist_ok=True)
    _ensure_preview_path_writable(target)
    target.write_text(code, encoding="utf-8")


def _preview_base_workspace(base_workspace: str | None) -> Path | None:
    candidates = [base_workspace, str(Path(__file__).resolve().parents[1])]
    for raw in candidates:
        value = str(raw or "").strip()
        if not value:
            continue
        path = Path(value).expanduser().resolve(strict=False)
        if path.is_dir():
            return path
    return None


def _ensure_policy_packages(workspace: Path) -> None:
    policies = workspace / "policies"
    baseline_modules = policies / "baseline_modules"
    baseline_modules.mkdir(parents=True, exist_ok=True)
    for package in (policies, baseline_modules):
        init_path = package / "__init__.py"
        if not init_path.exists():
            _ensure_preview_path_writable(package)
            init_path.write_text("", encoding="utf-8")


def _is_policy_preview_path(path: str) -> bool:
    return _is_baseline_algorithm_path(path) or _is_solver_design_module_path(path)


def _ensure_preview_path_writable(path: Path) -> None:
    try:
        mode = path.stat().st_mode
    except FileNotFoundError:
        return
    writable_mode = mode | stat.S_IWUSR
    if path.is_dir():
        writable_mode |= stat.S_IXUSR
    if writable_mode != mode:
        path.chmod(writable_mode)


@contextmanager
def _temporary_policy_import_context(workspace: Path) -> Iterator[None]:
    saved_path = list(sys.path)
    saved_modules = {
        name: module
        for name, module in sys.modules.items()
        if name == "policies" or name.startswith("policies.")
    }
    for name in list(sys.modules):
        if name == "policies" or name.startswith("policies."):
            sys.modules.pop(name, None)
    sys.path.insert(0, str(workspace))
    try:
        yield
    finally:
        sys.path[:] = saved_path
        for name in list(sys.modules):
            if name == "policies" or name.startswith("policies."):
                sys.modules.pop(name, None)
        sys.modules.update(saved_modules)
