"""Interface check: confirm operator code exposes the configured execute signature.

This check intentionally uses AST only. Candidate operator code is tainted LLM
output, so verification must not import it in the orchestrator process just to
inspect a method signature.
"""
from __future__ import annotations

import ast
import time

from scion.core.operator_interface import parse_execute_signature
from scion.core.paths import normalize_relative_patch_path
from scion.core.models import CheckResult, PatchProposal


def check_interface(
    patch: PatchProposal,
    candidate_workspace: str,
    *,
    operator_execute_signature: str | None = None,
) -> CheckResult:
    """V2_interface: operator module has the configured execute signature."""
    t0 = time.monotonic_ns()
    expected = parse_execute_signature(operator_execute_signature)

    if patch.action == "delete":
        return _cr(True, "light", "delete action — no interface check", t0)

    try:
        normalize_relative_patch_path(patch.file_path)
    except ValueError as exc:
        return _cr(False, "light", str(exc), t0)

    return _ast_check(patch, t0, expected.args, expected.expected_args_detail)


# ---------------------------------------------------------------------------
# AST check (same signature rule as ContractGate C7)
# ---------------------------------------------------------------------------

def _ast_check(
    patch: PatchProposal,
    t0: int,
    expected_args: tuple[str, ...],
    expected_detail: str,
) -> CheckResult:
    try:
        tree = ast.parse(patch.code_content)
    except SyntaxError:
        return _cr(False, "light", "unparseable code", t0)

    classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    if not classes:
        return _cr(True, "light", "no class found — skipped (AST)", t0)

    for cls in classes:
        for node in ast.walk(cls):
            if isinstance(node, ast.FunctionDef) and node.name == "execute":
                args = [a.arg for a in node.args.args]
                if tuple(args) == expected_args:
                    return _cr(True, "light", "execute signature ok (AST)", t0)
                return _cr(
                    False, "light",
                    f"execute signature wrong: {args}, expected {expected_detail} (AST)",
                    t0,
                )

    return _cr(False, "light", "class found but no execute method (AST)", t0)


def _cr(passed: bool, severity: str, detail: str, t0: int) -> CheckResult:
    elapsed = int((time.monotonic_ns() - t0) / 1_000_000)
    return CheckResult(
        name="V2_interface",
        passed=passed,
        severity=severity,  # type: ignore[arg-type]
        detail=detail,
        elapsed_ms=elapsed,
    )
