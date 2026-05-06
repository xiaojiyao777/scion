"""Runtime dependency preflight checks for problem packages."""
from __future__ import annotations

import importlib.util
import shutil
import sys
from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class RuntimePreflightReport:
    passed: bool
    reasons: tuple[str, ...] = ()


class RuntimeDependencyPreflightError(RuntimeError):
    """Raised when declared runtime dependencies are not available."""

    def __init__(self, reasons: Iterable[str]) -> None:
        self.reasons = tuple(str(reason) for reason in reasons if str(reason))
        detail = "; ".join(self.reasons) if self.reasons else "unknown failure"
        super().__init__(f"runtime dependency preflight failed: {detail}")


def run_runtime_preflight(spec: Any, adapter: Any | None = None) -> RuntimePreflightReport:
    """Fail closed when a problem's declared runtime dependencies are missing.

    ``spec`` may be a ProblemSpecV1 or a legacy ProblemSpec carrying the
    bridged ``runtime_dependencies`` attribute. Problems that declare no
    dependencies and no adapter-owned hook keep the historical no-op behavior.
    """
    reasons: list[str] = []
    dependencies = getattr(spec, "runtime_dependencies", None)

    for module_name in _as_tuple(
        getattr(dependencies, "required_python_modules", ())
    ):
        if not _python_module_available(module_name):
            reasons.append(
                "missing required Python module "
                f"'{module_name}' for interpreter '{sys.executable}'"
            )

    for executable in _as_tuple(getattr(dependencies, "required_executables", ())):
        if shutil.which(executable) is None:
            reasons.append(
                "missing required executable "
                f"'{executable}' on PATH for interpreter '{sys.executable}'"
            )

    hook = _adapter_preflight_hook(adapter)
    if hook is not None:
        reasons.extend(_normalize_hook_result(hook()))

    if reasons:
        raise RuntimeDependencyPreflightError(reasons)
    return RuntimePreflightReport(passed=True)


def _python_module_available(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


def _adapter_preflight_hook(adapter: Any | None) -> Any | None:
    if adapter is None:
        return None
    for name in ("run_preflight_checks", "preflight_checks"):
        hook = getattr(adapter, name, None)
        if callable(hook):
            return hook
    return None


def _normalize_hook_result(result: Any) -> tuple[str, ...]:
    if result is None:
        return ()

    passed = getattr(result, "passed", None)
    reasons = getattr(result, "reasons", None)
    if passed is not None:
        if bool(passed):
            return ()
        return tuple(str(reason) for reason in _as_tuple(reasons)) or (
            "adapter preflight hook failed",
        )

    if isinstance(result, bool):
        return () if result else ("adapter preflight hook failed",)

    if isinstance(result, str):
        return (result,) if result else ()

    return tuple(str(reason) for reason in _as_tuple(result) if str(reason))


def _as_tuple(value: Any) -> tuple[Any, ...]:
    if value is None:
        return ()
    if isinstance(value, (str, bytes)):
        return (value,)
    try:
        return tuple(value)
    except TypeError:
        return (value,)


__all__ = (
    "RuntimeDependencyPreflightError",
    "RuntimePreflightReport",
    "run_runtime_preflight",
)
