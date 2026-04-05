"""Runner Protocol and ResourceLimits for Scion runtime isolation."""
from __future__ import annotations

from dataclasses import dataclass
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
    ) -> RunResult:
        """Execute solver in isolation, return RunResult.

        Args:
            workdir: Path to the branch workspace (solver.py lives here).
            instance_path: Path to the problem instance file.
            seed: Random seed for the solver run.
            time_limit_sec: Soft time budget passed to solver via CLI.
            registry_path: Path to operator registry JSON file.

        Returns:
            RunResult with success flag, exit code, stdout/stderr, elapsed_ms,
            output_path and error_category.
        """
        ...
