"""Runner Protocol and ResourceLimits for Scion runtime isolation."""
from __future__ import annotations

from dataclasses import dataclass
import inspect
from typing import Optional, Protocol, runtime_checkable

from scion.core.models import RunResult


@dataclass
class ResourceLimits:
    """Resource constraints applied to each solver subprocess."""

    timeout_sec: int = 300
    memory_mb: int = 4096
    max_file_descriptors: int = 256


@runtime_checkable
class Runner(Protocol):
    """Protocol for executing solver in an isolated subprocess environment."""

    def run_solver(
        self,
        workdir: str,
        instance_path: str,
        seed: int,
        time_limit_sec: int,
        registry_path: str,
        selected_surface: str | None = None,
    ) -> RunResult:
        """Execute solver in isolation, return RunResult.

        Args:
            workdir: Path to the branch workspace (solver.py lives here).
            instance_path: Path to the problem instance file.
            seed: Random seed for the solver run.
            time_limit_sec: Soft time budget passed to solver via CLI.
            registry_path: Path to operator registry JSON file.
            selected_surface: Optional research surface name to expose to the
                solver runtime.

        Returns:
            RunResult with success flag, exit code, stdout/stderr, elapsed_ms,
            output_path and error_category.
        """
        ...


def run_solver_with_surface(
    runner: Runner,
    *,
    workdir: str,
    instance_path: str,
    seed: int,
    time_limit_sec: int,
    registry_path: str,
    selected_surface: str | None = None,
) -> RunResult:
    """Call ``runner.run_solver`` while preserving compatibility with old test fakes."""
    kwargs = {
        "workdir": workdir,
        "instance_path": instance_path,
        "seed": seed,
        "time_limit_sec": time_limit_sec,
        "registry_path": registry_path,
    }
    if _accepts_selected_surface(runner):
        kwargs["selected_surface"] = selected_surface
    return runner.run_solver(**kwargs)


def _accepts_selected_surface(runner: Runner) -> bool:
    run_solver = runner.run_solver
    side_effect = getattr(run_solver, "side_effect", None)
    signature_target = side_effect if callable(side_effect) else run_solver
    try:
        signature = inspect.signature(signature_target)
    except (TypeError, ValueError):
        return True
    parameters = signature.parameters
    return "selected_surface" in parameters or any(
        parameter.kind is inspect.Parameter.VAR_KEYWORD
        for parameter in parameters.values()
    )
