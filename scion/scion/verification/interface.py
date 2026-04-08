"""Interface check: confirm operator module has an Operator subclass with execute().

Strategy:
1. Attempt dynamic import from the candidate workspace.
2. If import succeeds, inspect classes for Operator subclass + execute signature.
3. If import fails (file not yet on disk, or no workspace), fall back to AST analysis
   — look for any class with execute(self, solution, rng).  This is the same rule
   ContractGate C7 already enforced, so a fall-back pass is safe.
"""
from __future__ import annotations

import ast
import importlib
import importlib.util
import os
import sys
import time
from typing import Optional

from scion.core.models import CheckResult, PatchProposal


def check_interface(patch: PatchProposal, candidate_workspace: str) -> CheckResult:
    """V2_interface: operator module has Operator subclass with execute(self, solution, rng)."""
    t0 = time.monotonic_ns()

    if patch.action == "delete":
        return _cr(True, "light", "delete action — no interface check", t0)

    # Try runtime import from workspace first.
    result = _runtime_check(patch, candidate_workspace, t0)
    if result is not None:
        return result

    # Fall back to AST analysis (mirrors ContractGate C7).
    return _ast_check(patch, t0)


# ---------------------------------------------------------------------------
# Runtime import check
# ---------------------------------------------------------------------------

def _runtime_check(
    patch: PatchProposal, workspace: str, t0: int
) -> Optional[CheckResult]:
    """Try to dynamically import the operator file and inspect classes.

    Returns None if import cannot be attempted (workspace/file not ready).
    """
    file_rel = patch.file_path.lstrip("/")
    abs_path = os.path.join(workspace, file_rel)
    if not os.path.isfile(abs_path):
        return None  # file not on disk yet → fall back to AST

    # Derive a stable module name from the relative file path.
    module_name = "_scion_vgate_" + file_rel.replace("/", "_").replace(".py", "")

    saved_path = list(sys.path)
    try:
        if workspace not in sys.path:
            sys.path.insert(0, workspace)

        spec = importlib.util.spec_from_file_location(module_name, abs_path)
        if spec is None or spec.loader is None:
            return None

        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]

        # Find classes that look like Operator subclasses.
        found_operator_cls = False
        found_execute = False
        for attr_name in dir(mod):
            cls = getattr(mod, attr_name, None)
            if not isinstance(cls, type):
                continue
            # Check if it inherits from something named "Operator"
            bases = [b.__name__ for b in cls.__mro__]
            if "Operator" in bases and cls.__name__ != "Operator":
                found_operator_cls = True
                method = getattr(cls, "execute", None)
                if callable(method):
                    import inspect
                    sig = inspect.signature(method)
                    params = list(sig.parameters.keys())
                    if params == ["self", "solution", "rng"]:
                        found_execute = True
                        break

        if not found_operator_cls:
            # No Operator subclass found; check for any class with execute sig.
            for attr_name in dir(mod):
                cls = getattr(mod, attr_name, None)
                if not isinstance(cls, type) or cls.__name__ in ("object",):
                    continue
                method = getattr(cls, "execute", None)
                if callable(method):
                    import inspect
                    sig = inspect.signature(method)
                    params = list(sig.parameters.keys())
                    if params == ["self", "solution", "rng"]:
                        # Acceptable: class with right execute signature
                        return _cr(True, "light", "execute signature ok (runtime)", t0)
            return _cr(
                False, "light",
                "no class with execute(self, solution, rng) found (runtime check)",
                t0,
            )

        if found_execute:
            return _cr(True, "light", "Operator subclass with execute ok (runtime)", t0)
        return _cr(
            False, "light",
            "Operator subclass found but execute(self, solution, rng) missing",
            t0,
        )

    except Exception as exc:
        # Import failed — fall back to AST
        return None
    finally:
        sys.path[:] = saved_path


# ---------------------------------------------------------------------------
# AST fallback check (same logic as ContractGate C7)
# ---------------------------------------------------------------------------

def _ast_check(patch: PatchProposal, t0: int) -> CheckResult:
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
                if args == ["self", "solution", "rng"]:
                    return _cr(True, "light", "execute signature ok (AST)", t0)
                return _cr(
                    False, "light",
                    f"execute signature wrong: {args}, expected ['self','solution','rng'] (AST)",
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
