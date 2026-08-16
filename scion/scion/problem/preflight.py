"""Runtime dependency preflight checks for problem packages."""
from __future__ import annotations

import importlib.util
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
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


@dataclass(frozen=True)
class ResearchEnvironmentPreflightReport:
    passed: bool
    checks: tuple[str, ...]


class ResearchEnvironmentPreflightError(RuntimeError):
    """Raised before H when the declared research environment is unusable."""

    def __init__(self, reasons: Iterable[str]) -> None:
        self.reasons = tuple(str(reason) for reason in reasons if str(reason))
        detail = "; ".join(self.reasons) if self.reasons else "unknown failure"
        super().__init__(f"research environment preflight failed: {detail}")


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


def run_research_environment_preflight(
    spec: Any,
    *,
    adapter: Any | None = None,
    verification_gate: Any | None = None,
) -> ResearchEnvironmentPreflightReport:
    """Validate concrete runtime and source prerequisites before the first H."""

    checks: list[str] = []
    reasons: list[str] = []
    try:
        run_runtime_preflight(spec, adapter=adapter)
        checks.append("runtime_dependencies")
    except RuntimeDependencyPreflightError as exc:
        reasons.extend(exc.reasons)

    reasons.extend(_research_surface_reasons(spec))
    if not any(reason.startswith("research surface") for reason in reasons):
        checks.append("research_surfaces")

    verification_preflight = getattr(verification_gate, "run_preflight", None)
    if callable(verification_preflight):
        try:
            verification_preflight()
            checks.append("verification_environment")
        except Exception as exc:
            reasons.append(f"verification environment unavailable: {exc}")

    if reasons:
        raise ResearchEnvironmentPreflightError(reasons)
    return ResearchEnvironmentPreflightReport(
        passed=True,
        checks=tuple(checks),
    )


def _research_surface_reasons(spec: Any) -> tuple[str, ...]:
    surfaces = list(getattr(spec, "research_surfaces", ()) or ())
    if not surfaces:
        return ()
    root_text = str(getattr(spec, "root_dir", "") or "").strip()
    root = Path(root_text).expanduser() if root_text else None
    reasons: list[str] = []
    for surface in surfaces:
        name = str(getattr(surface, "name", "") or "<unnamed>")
        targets = getattr(surface, "targets", None)
        files = list(
            getattr(targets, "files", None)
            or getattr(surface, "target_files", None)
            or ()
        )
        if not files:
            reasons.append(f"research surface '{name}' declares no target files")
            continue
        allowed = any(
            bool(
                getattr(
                    targets if targets is not None else surface,
                    f"{action}_allowed",
                    True,
                )
            )
            for action in ("create_new", "modify", "remove")
        )
        if not allowed:
            reasons.append(f"research surface '{name}' declares no allowed action")
            continue
        requires_existing = any(
            bool(
                getattr(
                    targets if targets is not None else surface,
                    f"{action}_allowed",
                    True,
                )
            )
            for action in ("modify", "remove")
        )
        if requires_existing and not _surface_has_existing_file(root, files):
            reasons.append(
                f"research surface '{name}' has no materialized target source"
            )
    return tuple(reasons)


def _surface_has_existing_file(root: Path | None, patterns: Iterable[Any]) -> bool:
    if root is None or not root.is_dir():
        return False
    for raw_pattern in patterns:
        pattern = str(raw_pattern or "").strip().lstrip("/")
        if not pattern:
            continue
        try:
            if any(path.is_file() for path in root.glob(pattern)):
                return True
        except OSError:
            continue
    return False


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
    "ResearchEnvironmentPreflightError",
    "ResearchEnvironmentPreflightReport",
    "RuntimeDependencyPreflightError",
    "RuntimePreflightReport",
    "run_research_environment_preflight",
    "run_runtime_preflight",
)
