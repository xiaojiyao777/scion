"""Syntax check: AST parse of candidate patch code."""
from __future__ import annotations

import ast
import time

from scion.core.models import CheckResult, PatchProposal


def check_syntax(patch: PatchProposal) -> CheckResult:
    """V1_syntax: parse patch code with ast.parse; fail on SyntaxError."""
    t0 = time.monotonic_ns()

    if patch.action == "delete":
        return _cr(True, "light", "delete action — no syntax check", t0)

    try:
        ast.parse(patch.code_content)
        return _cr(True, "light", "syntax ok", t0)
    except SyntaxError as exc:
        return _cr(False, "light", f"SyntaxError: {exc}", t0)


def _cr(passed: bool, severity: str, detail: str, t0: int) -> CheckResult:
    elapsed = int((time.monotonic_ns() - t0) / 1_000_000)
    return CheckResult(
        name="V1_syntax",
        passed=passed,
        severity=severity,  # type: ignore[arg-type]
        detail=detail,
        elapsed_ms=elapsed,
    )
