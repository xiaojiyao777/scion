"""Minimal problem-neutral adapters for Protocol unit tests."""

from __future__ import annotations

from collections.abc import Sequence
from types import SimpleNamespace
from typing import Any

from scion.problem.spec import ObjectivePolicySpec


class _ProtocolTestSpec:
    """Overlay objective declarations while preserving an optional test spec."""

    def __init__(
        self,
        base: Any | None,
        *,
        objectives: Sequence[Any],
        objective_policy: Any,
    ) -> None:
        self._base = base
        self.objectives = tuple(objectives)
        self.objective_policy = objective_policy
        if base is None:
            self.id = "protocol_test"
            self.name = "protocol_test"
            self.measurement = None

    def __getattr__(self, name: str) -> Any:
        if self._base is None:
            raise AttributeError(name)
        return getattr(self._base, name)


def protocol_test_adapter(
    metric_specs: Sequence[Any] | None,
    *,
    problem_spec: Any | None = None,
    objective_policy: Any | None = None,
) -> Any:
    """Return a local adapter whose sole spec owns Protocol test semantics."""

    objectives = (
        tuple(metric_specs)
        if metric_specs is not None
        else tuple(getattr(problem_spec, "objectives", ()) or ())
    )
    policy = (
        objective_policy
        or getattr(problem_spec, "objective_policy", None)
        or ObjectivePolicySpec()
    )
    return SimpleNamespace(
        spec=_ProtocolTestSpec(
            problem_spec,
            objectives=objectives,
            objective_policy=policy,
        )
    )


__all__ = ["protocol_test_adapter"]
