"""Path-to-surface helpers for CVRP adapter previews."""
from __future__ import annotations

def _surface_name_from_policy_path(path: str) -> str:
    normalized = path.replace("\\", "/").lstrip("/")
    return (
        "solver_design"
        if _is_baseline_algorithm_path(normalized)
        or _is_solver_design_module_path(normalized)
        else ""
    )

def _is_baseline_algorithm_path(path: str) -> bool:
    return path.replace("\\", "/").lstrip("/") == "policies/baseline_algorithm.py"

def _is_solver_design_module_path(path: str) -> bool:
    normalized = path.replace("\\", "/").lstrip("/")
    return (
        normalized.startswith("policies/baseline_modules/")
        and normalized.endswith(".py")
        and "/__pycache__/" not in normalized
    )
