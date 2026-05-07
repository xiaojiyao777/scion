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
        problem_spec: Any,
        verification_gate: Any | None,
        experiment_protocol: Any | None,
        campaign_dir: str,
        adapter: Any | None = None,
        operator_execute_signature: str | None = None,
        allow_non_strict_runtime_verification: bool = False,
    ) -> Any:
        if verification_gate is not None:
            return verification_gate

        runner = protocol_runner(experiment_protocol)
        runtime_cfg = getattr(getattr(experiment_protocol, "config", None), "runtime", None)
        max_runtime_ratio = getattr(runtime_cfg, "max_runtime_ratio", None)

        spec_requires_adapter = _problem_spec_requires_adapter(problem_spec)
        adapter_backed = adapter is not None or spec_requires_adapter
        strict_runtime_checks = spec_requires_adapter or (
            adapter_backed
            and (runner is not None or not allow_non_strict_runtime_verification)
        )
        require_adapter_for_runtime = spec_requires_adapter or strict_runtime_checks

        return VerificationGate(
            problem_spec,
            runner=runner,
            metrics_dir=f"{campaign_dir}/metrics",
            adapter=adapter,
            strict_runtime_checks=strict_runtime_checks,
            require_adapter_for_runtime=require_adapter_for_runtime,
            operator_execute_signature=operator_execute_signature,
            max_runtime_ratio=max_runtime_ratio,
        )


def _problem_spec_requires_adapter(problem_spec: Any | None) -> bool:
    if problem_spec is None:
        return False
    if bool(getattr(problem_spec, "requires_adapter_for_runtime", False)):
        return True
    return (
        getattr(problem_spec, "spec_version", None) == "problem-v1"
        and bool(getattr(problem_spec, "adapter_import_path", ""))
    )
