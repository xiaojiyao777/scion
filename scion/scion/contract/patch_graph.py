"""Patch-set import graph helpers for ContractGate."""
from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Callable

from scion.core.models import PatchProposal, patch_file_changes
from scion.core.paths import normalize_relative_patch_path


@dataclass(frozen=True)
class PatchSetGraph:
    """Normalized candidate file graph for a primary patch plus additions."""

    actions_by_path: dict[str, str]

    @classmethod
    def from_patch(cls, patch: PatchProposal) -> "PatchSetGraph":
        actions: dict[str, str] = {}
        for change in patch_file_changes(patch):
            try:
                file_rel = normalize_relative_patch_path(change.file_path)
            except ValueError:
                continue
            actions[file_rel] = str(change.action)
        return cls(actions_by_path=actions)

    def is_created(self, file_rel: str) -> bool:
        return self.actions_by_path.get(file_rel) == "create"

    def allows_same_patch_relative_import(
        self,
        *,
        importer_path: str,
        node: ast.ImportFrom,
        is_editable_solver_file: Callable[[str], bool],
    ) -> bool:
        """Return whether a relative import targets same-patch created modules."""
        if node.level <= 0:
            return False
        try:
            importer_rel = normalize_relative_patch_path(importer_path)
        except ValueError:
            return False
        if not is_editable_solver_file(importer_rel):
            return False
        targets = _relative_import_module_targets(importer_rel, node)
        if not targets:
            return False
        return all(
            target != importer_rel
            and self.is_created(target)
            and is_editable_solver_file(target)
            for target in targets
        )


def _relative_import_module_targets(
    importer_rel: str,
    node: ast.ImportFrom,
) -> tuple[str, ...]:
    package_parts = importer_rel.removesuffix(".py").split("/")[:-1]
    up_levels = max(0, int(node.level) - 1)
    if up_levels:
        if up_levels > len(package_parts):
            return ()
        package_parts = package_parts[:-up_levels]

    module = str(node.module or "").strip(".")
    if module:
        parts = package_parts + [part for part in module.split(".") if part]
        if not parts:
            return ()
        return ("/".join(parts) + ".py",)

    targets: list[str] = []
    for alias in node.names:
        name = str(alias.name or "")
        if not name or name == "*":
            continue
        parts = package_parts + [part for part in name.split(".") if part]
        if parts:
            targets.append("/".join(parts) + ".py")
    return tuple(targets)
