"""Problem-neutral local-import graph for focused code research context."""

from __future__ import annotations

import ast
from collections.abc import Mapping
from pathlib import PurePosixPath

_ROLE_ORDER = ("target", "dependency", "caller", "peer")


def source_graph_roles(
    sources: Mapping[str, str | None],
    *,
    target: str,
    qualified_prefixes: tuple[str, ...] = (),
) -> dict[str, tuple[str, ...]]:
    """Classify current editable source around one approved target.

    Dependencies are the target's transitive local-import closure.  Callers are
    its transitive reverse-import closure.  The two traversals are intentionally
    independent: dependencies of a caller do not become target dependencies.
    Any invalid current Python source fails context construction closed rather
    than silently weakening the dependency graph.
    """

    dependencies_by_path = _dependency_edges(
        sources,
        qualified_prefixes=qualified_prefixes,
    )

    dependencies = _reachable(target, dependencies_by_path)
    reverse: dict[str, set[str]] = {path: set() for path in sources}
    for caller, imported_paths in dependencies_by_path.items():
        for imported in imported_paths:
            reverse.setdefault(imported, set()).add(caller)
    callers = _reachable(target, reverse)

    roles: dict[str, tuple[str, ...]] = {}
    for path in sources:
        selected: list[str] = []
        if path == target:
            selected.append("target")
        if path in dependencies:
            selected.append("dependency")
        if path in callers:
            selected.append("caller")
        if not selected:
            selected.append("peer")
        roles[path] = tuple(role for role in _ROLE_ORDER if role in selected)
    return roles


def source_graph_links(
    sources: Mapping[str, str | None],
    *,
    qualified_prefixes: tuple[str, ...] = (),
) -> dict[str, dict[str, tuple[str, ...]]]:
    """Return direct local-import adjacency without inventing a focus target."""

    dependencies = _dependency_edges(
        sources,
        qualified_prefixes=qualified_prefixes,
    )
    callers: dict[str, set[str]] = {path: set() for path in sources}
    for caller, imported_paths in dependencies.items():
        for imported in imported_paths:
            callers[imported].add(caller)
    return {
        path: {
            "dependencies": tuple(sorted(dependencies[path])),
            "callers": tuple(sorted(callers[path])),
        }
        for path in sorted(sources)
    }


def ordered_source_paths(
    roles: Mapping[str, tuple[str, ...]],
) -> tuple[str, ...]:
    """Return deterministic target/dependency/caller/peer presentation order."""

    def rank(item: tuple[str, tuple[str, ...]]) -> tuple[int, str]:
        path, path_roles = item
        return (
            min(_ROLE_ORDER.index(role) for role in path_roles),
            path,
        )

    return tuple(path for path, _path_roles in sorted(roles.items(), key=rank))


def _module_path_index(
    sources: Mapping[str, str | None],
) -> dict[str, str]:
    modules: dict[str, str] = {}
    for path in sources:
        module = _module_name(path)
        if module:
            if module in modules:
                raise ValueError(f"duplicate local source module: {module}")
            modules[module] = path
    return modules


def _dependency_edges(
    sources: Mapping[str, str | None],
    *,
    qualified_prefixes: tuple[str, ...],
) -> dict[str, set[str]]:
    module_paths = _module_path_index(sources)
    dependencies: dict[str, set[str]] = {path: set() for path in sources}
    for path, content in sources.items():
        if not isinstance(content, str) or not path.endswith(".py"):
            continue
        dependencies[path].update(
            _local_import_paths(
                path=path,
                content=content,
                module_paths=module_paths,
                qualified_prefixes=qualified_prefixes,
            )
        )
        dependencies[path].discard(path)
    return dependencies


def _module_name(path: str) -> str:
    pure = PurePosixPath(path)
    if pure.suffix != ".py":
        return ""
    parts = list(pure.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _local_import_paths(
    *,
    path: str,
    content: str,
    module_paths: Mapping[str, str],
    qualified_prefixes: tuple[str, ...],
) -> set[str]:
    try:
        tree = ast.parse(content, filename=path)
    except (SyntaxError, ValueError) as exc:
        raise ValueError(f"cannot parse current editable source: {path}") from exc
    current_module = _module_name(path)
    current_package = (
        current_module
        if path.endswith("/__init__.py")
        else current_module.rpartition(".")[0]
    )
    imported: set[str] = set()
    for node in ast.walk(tree):
        candidates: list[str] = []
        if isinstance(node, ast.Import):
            candidates.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = _resolved_from_module(
                current_package=current_package,
                module=node.module,
                level=node.level,
            )
            if base:
                candidates.append(base)
                candidates.extend(
                    f"{base}.{alias.name}" for alias in node.names if alias.name != "*"
                )
        for candidate in candidates:
            if resolved := _nearest_local_module(
                candidate,
                module_paths,
                qualified_prefixes=qualified_prefixes,
            ):
                imported.add(module_paths[resolved])
    return imported


def _resolved_from_module(
    *,
    current_package: str,
    module: str | None,
    level: int,
) -> str:
    if level <= 0:
        return str(module or "")
    package_parts = [part for part in current_package.split(".") if part]
    remove = level - 1
    if not package_parts or remove > len(package_parts):
        raise ValueError("relative import escapes the current source package")
    prefix = package_parts[: len(package_parts) - remove]
    if module:
        prefix.extend(str(module).split("."))
    return ".".join(prefix)


def _nearest_local_module(
    candidate: str,
    module_paths: Mapping[str, str],
    *,
    qualified_prefixes: tuple[str, ...],
) -> str | None:
    candidates = [candidate]
    for prefix in qualified_prefixes:
        if candidate.startswith(prefix):
            candidates.append(candidate[len(prefix) :])
    matches = {
        resolved
        for value in candidates
        if (resolved := _exact_or_parent_module(value, module_paths)) is not None
    }
    if len(matches) == 1:
        return next(iter(matches))
    if len(matches) > 1:
        raise ValueError(f"ambiguous local import: {candidate}")
    return None


def _exact_or_parent_module(
    candidate: str,
    module_paths: Mapping[str, str],
) -> str | None:
    parts = [part for part in candidate.split(".") if part]
    while parts:
        module = ".".join(parts)
        if module in module_paths:
            return module
        parts.pop()
    return None


def _reachable(
    start: str,
    edges: Mapping[str, set[str]],
) -> set[str]:
    reached: set[str] = set()
    pending = list(sorted(edges.get(start, ()), reverse=True))
    while pending:
        path = pending.pop()
        if path == start or path in reached:
            continue
        reached.add(path)
        pending.extend(
            dependency
            for dependency in sorted(edges.get(path, ()), reverse=True)
            if dependency not in reached
        )
    return reached


__all__ = ["ordered_source_paths", "source_graph_links", "source_graph_roles"]
