"""Helpers for problem-defined operator interface signatures."""
from __future__ import annotations

import ast
from dataclasses import dataclass


DEFAULT_EXECUTE_SIGNATURE = "execute(self, solution, rng) -> Solution"


@dataclass(frozen=True)
class OperatorExecuteSignature:
    name: str
    args: tuple[str, ...]
    display: str

    @property
    def expected_args_detail(self) -> str:
        return "[" + ", ".join(repr(arg) for arg in self.args) + "]"


def parse_execute_signature(signature: str | None) -> OperatorExecuteSignature:
    """Parse a problem-defined execute signature into comparable argument names."""
    raw = (signature or DEFAULT_EXECUTE_SIGNATURE).strip()
    if raw.startswith("def "):
        raw = raw[4:].strip()
    if raw.endswith(":"):
        raw = raw[:-1].strip()

    try:
        tree = ast.parse(f"def {raw}:\n    pass\n")
    except SyntaxError as exc:
        raise ValueError(f"invalid operator execute_signature: {signature!r}") from exc

    if not tree.body or not isinstance(tree.body[0], ast.FunctionDef):
        raise ValueError(f"invalid operator execute_signature: {signature!r}")

    fn = tree.body[0]
    if fn.name != "execute":
        raise ValueError("operator execute_signature must define execute(...)")

    if fn.args.vararg is not None or fn.args.kwarg is not None or fn.args.kwonlyargs:
        raise ValueError("operator execute_signature must use explicit positional args")

    if fn.args.defaults:
        raise ValueError("operator execute_signature must not define default args")

    args = tuple(arg.arg for arg in fn.args.args)
    if not args or args[0] != "self":
        raise ValueError("operator execute_signature must start with self")

    return OperatorExecuteSignature(name=fn.name, args=args, display=raw)
