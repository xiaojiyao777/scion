"""Factory for campaign verification-gate construction."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from scion.core.production_boundary import is_adapter_backed_production_campaign
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
        problem_spec: Any,
        verification_gate: Any | None,
        experiment_protocol: Any | None,
        campaign_dir: str,
        adapter: Any | None = None,
        operator_execute_signature: str | None = None,
        allow_non_strict_runtime_verification: bool = False,
        allow_skeleton_mode: bool = False,
    ) -> Any:
        production_campaign = is_adapter_backed_production_campaign(
            problem_spec=problem_spec,
            adapter=adapter,
            allow_skeleton=allow_skeleton_mode,
        )
        runtime_cfg = getattr(getattr(experiment_protocol, "config", None), "runtime", None)
        max_runtime_ratio = getattr(runtime_cfg, "max_runtime_ratio", None)
        runtime_time_limit_sec = _verification_runtime_time_limit_sec(
            problem_spec=problem_spec,
            experiment_protocol=experiment_protocol,
            runtime_cfg=runtime_cfg,
        )
        if verification_gate is not None:
            if production_campaign and not isinstance(verification_gate, VerificationGate):
                raise ValueError(
                    "custom verification_gate is not allowed for adapter-backed "
                    "production campaigns; use the default VerificationGate or "
                    "explicit skeleton mode for tests"
                )
            if production_campaign and isinstance(verification_gate, VerificationGate):
                verification_gate.bind_runtime_policy(
                    max_runtime_ratio=max_runtime_ratio,
                    runtime_time_limit_sec=runtime_time_limit_sec,
                )
            return verification_gate

        runner = protocol_runner(experiment_protocol)

        if production_campaign and allow_non_strict_runtime_verification:
            raise ValueError(
                "allow_non_strict_runtime_verification is not allowed for "
                "adapter-backed production campaigns"
            )
        strict_runtime_checks = production_campaign
        require_adapter_for_runtime = production_campaign

        return VerificationGate(
            problem_spec,
            runner=runner,
            metrics_dir=f"{campaign_dir}/metrics",
            adapter=adapter,
            strict_runtime_checks=strict_runtime_checks,
            require_adapter_for_runtime=require_adapter_for_runtime,
            allow_adapter_runtime_fallback=allow_skeleton_mode,
            operator_execute_signature=operator_execute_signature,
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
