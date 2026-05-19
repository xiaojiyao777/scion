"""Contract result construction helpers."""
from __future__ import annotations

import time

from scion.core.models import CheckResult, ContractResult


def check_result(
    name: str,
    passed: bool,
    severity: str,
    detail: str,
    start_ns: int,
) -> CheckResult:
    elapsed_ms = int((time.monotonic_ns() - start_ns) / 1_000_000)
    return CheckResult(
        name=name,
        passed=passed,
        severity=severity,  # type: ignore[arg-type]
        detail=detail,
        elapsed_ms=elapsed_ms,
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
