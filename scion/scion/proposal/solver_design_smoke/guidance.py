"""Repair guidance rendering for solver-design smoke failures."""

from __future__ import annotations

from typing import Any, Mapping


def _solver_design_smoke_repair_guidance(
    audit_failure: Mapping[str, Any],
    *,
    runtime: Any,
    run_payload: Any,
    provider: Any | None = None,
) -> list[str]:
    renderer = getattr(provider, "runtime_smoke_repair_guidance", None)
    if callable(renderer):
        return list(
            renderer(audit_failure, runtime=runtime, run_payload=run_payload)
        )
    if audit_failure.get("error_category") == "solver_algorithm_runtime_error":
        return [
            "Failure occurred inside the candidate solver_design solve path during tainted algorithm smoke; repair the candidate algorithm code, not protocol or adapter files."
        ]
    return []
