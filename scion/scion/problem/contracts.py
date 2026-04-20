"""Problem adapter protocol and data types.

Defines the contract between Scion core and problem-specific implementations.
Core depends ONLY on these types — never on concrete problem modules.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping, Protocol, Sequence, runtime_checkable


@dataclass(frozen=True)
class CheckReport:
    passed: bool
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class LowerBoundEstimate:
    metric_name: str
    value: int | float
    kind: Literal["exact", "instance", "heuristic"]
    note: str = ""


@dataclass(frozen=True)
class SolverArtifact:
    raw_output: Mapping[str, Any]
    objective: Mapping[str, int | float]
    feasible: bool
    normalized_solution: Any | None = None


@runtime_checkable
class ProblemAdapter(Protocol):
    """Problem-specific runtime hooks for Scion core."""

    # --- Prompt / context ---

    def render_problem_summary(self) -> str:
        """Rich problem summary for Round-1/2 prompt construction."""
        ...

    def render_operator_interface(self) -> str:
        """Operator base class / interface / key invariants as prompt text."""
        ...

    # --- Instance / output ---

    def load_instance(self, instance_path: str) -> Any:
        """Load one benchmark instance into a problem-specific object."""
        ...

    def deserialize_solver_output(
        self,
        raw_output: Mapping[str, Any],
        instance: Any,
    ) -> SolverArtifact:
        """Convert raw solver JSON output into a normalized artifact."""
        ...

    # --- Verification ---

    def check_solution_consistency(
        self,
        artifact: SolverArtifact,
        instance: Any,
    ) -> CheckReport:
        """Problem-specific internal consistency check."""
        ...

    def check_feasibility(
        self,
        artifact: SolverArtifact,
        instance: Any,
    ) -> CheckReport:
        """Hard feasibility check against frozen oracle / constraints."""
        ...

    def recompute_objective(
        self,
        artifact: SolverArtifact,
        instance: Any,
    ) -> Mapping[str, int | float]:
        """Recompute objective from artifact + instance for verification."""
        ...

    # --- Optional: lower bound ---

    def estimate_lower_bound(
        self,
        metric_name: str,
        instance_paths: Sequence[str],
    ) -> LowerBoundEstimate | None:
        """Optional lower-bound estimate for saturation analysis.

        Return None if not implemented; core falls back to no bound.
        """
        ...
