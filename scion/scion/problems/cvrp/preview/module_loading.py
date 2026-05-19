"""Module loading helpers for CVRP adapter previews."""
from __future__ import annotations

import types

def _module_from_policy_code(file_path: str, code: str) -> types.ModuleType:
    module = types.ModuleType(f"_scion_cvrp_policy_preview_{abs(hash(file_path))}")
    module.__dict__["__file__"] = f"<preview:{file_path}>"
    module.__dict__["__name__"] = module.__name__
    package = _preview_package_for_policy_path(file_path)
    if package:
        module.__dict__["__package__"] = package
    exec(compile(code, file_path, "exec"), module.__dict__)
    return module

def _preview_package_for_policy_path(file_path: str) -> str:
    normalized = file_path.replace("\\", "/").lstrip("/")
    if normalized == "policies/baseline_algorithm.py":
        return "scion.problems.cvrp.policies"
    if normalized.startswith("policies/baseline_modules/"):
        return "scion.problems.cvrp.policies.baseline_modules"
    return ""
