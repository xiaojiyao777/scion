"""Dynamic policy module loading for the CVRP solver runtime."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import time
from typing import Any


def _load_policy_module(path: Path) -> Any:
    module_name = _policy_module_name(path)
    workspace_root = _policy_workspace_root(path)
    if module_name is None:
        module_name = f"_scion_cvrp_search_policy_{abs(hash(str(path)))}_{time.time_ns()}"
    else:
        _evict_module_tree(module_name.split(".", 1)[0])
    if workspace_root is not None:
        sys.path.insert(0, str(workspace_root))
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"could not load module spec for {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        if workspace_root is not None:
            try:
                sys.path.remove(str(workspace_root))
            except ValueError:
                pass
    return module


def _policy_module_name(path: Path) -> str | None:
    parts = path.resolve().parts
    if "policies" not in parts:
        return None
    index = len(parts) - 1 - list(reversed(parts)).index("policies")
    module_parts = list(parts[index:])
    if not module_parts[-1].endswith(".py"):
        return None
    module_parts[-1] = module_parts[-1][:-3]
    if any(not part.isidentifier() for part in module_parts):
        return None
    return ".".join(module_parts)


def _policy_workspace_root(path: Path) -> Path | None:
    parts = path.resolve().parts
    if "policies" not in parts:
        return None
    index = len(parts) - 1 - list(reversed(parts)).index("policies")
    if index == 0:
        return None
    return Path(*parts[:index])


def _evict_module_tree(root_name: str) -> None:
    for name in list(sys.modules):
        if name == root_name or name.startswith(f"{root_name}."):
            sys.modules.pop(name, None)


def _call_policy_function(
    module: Any,
    function_name: str,
    instance: Any,
    time_limit_sec: float,
) -> Any:
    func = getattr(module, function_name, None)
    if not callable(func):
        raise ValueError(f"missing callable {function_name}")
    return func(instance, time_limit_sec)
