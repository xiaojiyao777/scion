"""Static randomness-source checks."""
from __future__ import annotations

import ast
import time

from scion.contract.result_payload import check_result
from scion.core.models import CheckResult, PatchProposal

_NON_RNG_RANDOM_PATTERNS = frozenset(
    {
        ("uuid", "uuid4"),
        ("uuid", "uuid1"),
        ("random", "random"),
        ("random", "randint"),
        ("random", "choice"),
        ("random", "sample"),
        ("random", "shuffle"),
        ("random", "uniform"),
        ("random", "randrange"),
        ("os", "urandom"),
        ("secrets", "token_bytes"),
        ("secrets", "token_hex"),
        ("secrets", "token_urlsafe"),
    }
)


def check_non_rng_random(patch: PatchProposal) -> CheckResult:
    t0 = time.monotonic_ns()
    if patch.action == "delete":
        return check_result(
            "C9b_non_rng_random",
            True,
            "heavy",
            "delete action — no randomness check",
            t0,
        )

    try:
        tree = ast.parse(patch.code_content)
    except SyntaxError:
        return check_result(
            "C9b_non_rng_random",
            False,
            "heavy",
            "unparseable code",
            t0,
        )

    dangerous_names: set[str] = set()
    module_aliases: dict[str, str] = {}

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                local_name = alias.asname if alias.asname else alias.name
                if (module, alias.name) in _NON_RNG_RANDOM_PATTERNS:
                    dangerous_names.add(local_name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    module_aliases[alias.asname] = alias.name

    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name):
            if func.id in dangerous_names:
                violations.append(f"{func.id}(...)")
        elif isinstance(func, ast.Attribute):
            obj_name: str | None = None
            if isinstance(func.value, ast.Name):
                obj_name = func.value.id
            if obj_name is None:
                continue
            if obj_name == "rng":
                continue
            resolved = module_aliases.get(obj_name, obj_name)
            if (resolved, func.attr) in _NON_RNG_RANDOM_PATTERNS:
                violations.append(f"{obj_name}.{func.attr}")

    passed = len(violations) == 0
    detail = (
        "no non-rng random sources"
        if passed
        else f"non-rng random sources detected: {violations}"
    )
    return check_result("C9b_non_rng_random", passed, "heavy", detail, t0)
