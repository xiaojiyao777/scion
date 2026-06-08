"""Contract result construction helpers."""
from __future__ import annotations

import time
from typing import Any

from scion.core.models import CheckResult, ContractResult


def check_result(
    name: str,
    passed: bool,
    severity: str,
    detail: str,
    start_ns: int,
    *,
    metadata: dict[str, Any] | None = None,
) -> CheckResult:
    elapsed_ms = int((time.monotonic_ns() - start_ns) / 1_000_000)
    return CheckResult(
        name=name,
        passed=passed,
        severity=severity,  # type: ignore[arg-type]
        detail=detail,
        elapsed_ms=elapsed_ms,
        metadata=dict(metadata or {}),
    )


def prefix_checks(checks: list[CheckResult], prefix: str) -> list[CheckResult]:
    return [
        CheckResult(
            name=f"{prefix}.{check.name}",
            passed=check.passed,
            severity=check.severity,
            detail=check.detail,
            elapsed_ms=check.elapsed_ms,
            metadata=check.metadata,
        )
        for check in checks
    ]


def build_result(checks: list[CheckResult]) -> ContractResult:
    """Aggregate checks into ContractResult."""
    first_failure: str | None = None
    for check in checks:
        if not check.passed:
            first_failure = f"{check.name}: {check.detail}"
            break
    return ContractResult(
        passed=first_failure is None,
        checks=tuple(checks),
        failure_reason=first_failure,
    )


def diagnostic_checks(result: ContractResult | None) -> tuple[dict[str, Any], ...]:
    """Return compact passed-diagnostic contract checks for durable evidence."""
    if result is None:
        return ()
    diagnostics: list[dict[str, Any]] = []
    for check in getattr(result, "checks", ()) or ():
        metadata = dict(getattr(check, "metadata", {}) or {})
        if str(metadata.get("gate_action") or "") != "diagnostic":
            continue
        diagnostics.append(
            {
                "name": str(getattr(check, "name", "") or ""),
                "passed": bool(getattr(check, "passed", False)),
                "severity": str(getattr(check, "severity", "") or ""),
                "detail": str(getattr(check, "detail", "") or ""),
                "metadata": metadata,
            }
        )
    return tuple(diagnostics)
