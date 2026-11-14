"""Factory for campaign verification-gate construction."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from scion.verification.gate import VerificationGate


def protocol_runner(experiment_protocol: Any | None) -> Any | None:
    if experiment_protocol is None:
        return None
    return getattr(
        experiment_protocol,
        "runner",
        getattr(experiment_protocol, "_runner", None),
    )


@dataclass(frozen=True)
class CampaignVerificationFactory:
    """Build the default VerificationGate for programmatic campaigns."""

    @staticmethod
    def build(
        *,
        verification_gate: Any | None,
        experiment_protocol: Any | None,
        campaign_dir: str,
        adapter: Any,
    ) -> Any:
        problem_spec = getattr(adapter, "spec", None)
        if problem_spec is None:
            raise TypeError("campaign verification requires adapter.spec")
        runtime_cfg = getattr(getattr(experiment_protocol, "config", None), "runtime", None)
        max_runtime_ratio = getattr(runtime_cfg, "max_runtime_ratio", None)
        runtime_time_limit_sec = _verification_runtime_time_limit_sec(
            problem_spec=problem_spec,
            experiment_protocol=experiment_protocol,
            runtime_cfg=runtime_cfg,
        )
        if verification_gate is not None:
            if not isinstance(verification_gate, VerificationGate):
                raise ValueError(
                    "custom verification_gate is outside the direct-V3 boundary"
                )
            verification_gate.bind_problem_adapter(adapter)
            verification_gate.bind_runtime_policy(
                max_runtime_ratio=max_runtime_ratio,
                runtime_time_limit_sec=runtime_time_limit_sec,
            )
            return verification_gate

        runner = protocol_runner(experiment_protocol)

        return VerificationGate(
            runner=runner,
            metrics_dir=f"{campaign_dir}/metrics",
            adapter=adapter,
            strict_runtime_checks=True,
            max_runtime_ratio=max_runtime_ratio,
            runtime_time_limit_sec=runtime_time_limit_sec,
        )


def _verification_runtime_time_limit_sec(
    *,
    problem_spec: Any,
    experiment_protocol: Any | None,
    runtime_cfg: Any | None,
) -> int | None:
    """Return the explicit runtime budget used by verification canary checks."""

    candidates = (
        getattr(runtime_cfg, "verification_runtime_budget_sec", None),
        getattr(experiment_protocol, "verification_runtime_budget_sec", None),
        getattr(experiment_protocol, "time_limit_sec", None),
        getattr(getattr(problem_spec, "solver", None), "time_limit_sec", None),
    )
    for value in candidates:
        if isinstance(value, bool) or value is None:
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        if numeric > 0:
            return max(1, int(numeric))
    return None
