from __future__ import annotations

import os
from typing import TYPE_CHECKING

from scion.core.models import CanaryResult
from scion.runtime.audit import (
    format_runtime_audit_failure,
    runtime_audit_failure_from_result,
)

if TYPE_CHECKING:
    from .facade import ExperimentProtocol


def run_canary(
    protocol: "ExperimentProtocol",
    candidate_ws: str,
    champion_ws: str,
    *,
    selected_surface: str | None = None,
) -> CanaryResult:
    """
    Canary regression check using the dedicated canary split and seeds.
    Veto-only — blocks if candidate produces infeasible solutions or crashes.

    Raises ValueError if canary split/seeds are not configured.
    """
    canary_cases = protocol.split_manager.get_canary_cases()
    canary_seeds = protocol.seed_ledger.get_canary_seeds()

    if not canary_cases:
        raise ValueError(
            "Canary split not configured: split_manifest.canary is empty. "
            "Add canary cases to split_manifest.yaml."
        )
    if not canary_seeds:
        raise ValueError(
            "Canary seeds not configured: seed_ledger.canary is empty. "
            "Add canary seeds to seed_ledger.yaml."
        )

    for case in canary_cases:
        for seed in canary_seeds:
            cand_result = protocol.runner.run_solver(
                workdir=candidate_ws,
                instance_path=case,
                seed=seed,
                time_limit_sec=protocol.time_limit_sec,
                registry_path=os.path.join(candidate_ws, "registry.yaml"),
                selected_surface=selected_surface,
            )
            if not cand_result.success:
                return CanaryResult(
                    passed=False,
                    reason=f"Candidate solver failed on {case}: {cand_result.error_category}",
                )
            cand_audit_failure = runtime_audit_failure_from_result(
                cand_result,
                problem_spec=protocol._problem_spec,
                selected_surface=selected_surface,
            )
            if cand_audit_failure is not None:
                return CanaryResult(
                    passed=False,
                    reason=(
                        f"Candidate runtime audit failed on {case}: "
                        f"{format_runtime_audit_failure(cand_audit_failure)}"
                    ),
                )

            champ_result = protocol.runner.run_solver(
                workdir=champion_ws,
                instance_path=case,
                seed=seed,
                time_limit_sec=protocol.time_limit_sec,
                registry_path=os.path.join(champion_ws, "registry.yaml"),
                selected_surface=selected_surface,
            )
            if not champ_result.success:
                # Infra issue on champion side — skip veto
                continue
            if runtime_audit_failure_from_result(champ_result) is not None:
                # Existing champion-side runtime audit issues are not a
                # candidate veto in the canary gate; validation/frozen
                # evidence treats them as incomplete champion evidence.
                continue

            if (
                cand_result.output is not None
                and champ_result.output is not None
                and champ_result.output.feasible
                and not cand_result.output.feasible
            ):
                return CanaryResult(
                    passed=False,
                    reason=f"Candidate infeasible on {case} (champion was feasible)",
                )

    return CanaryResult(passed=True, reason=None)


__all__ = ["run_canary"]
