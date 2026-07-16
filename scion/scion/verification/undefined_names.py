"""Lightweight static detection of unresolved names in candidate modules."""

from __future__ import annotations

import ast
import builtins
import symtable
import time
from collections.abc import Iterable

from scion.core.models import CheckResult, PatchProposal

_BUILTIN_NAMES = frozenset(dir(builtins))
_IMPLICIT_MODULE_GLOBALS = frozenset(
    {
        "__annotations__",
        "__builtins__",
        "__cached__",
        "__debug__",
        "__doc__",
        "__file__",
        "__loader__",
        "__name__",
        "__package__",
        "__path__",
        "__spec__",
    }
)


def check_undefined_names(patch: PatchProposal) -> CheckResult:
    """Reject referenced names that cannot resolve within a candidate module.

    ``symtable`` supplies Python's own scope classification, which avoids
    reimplementing closure, comprehension, ``global``, and ``nonlocal`` rules.
    A module containing a wildcard import is skipped because the imported
    names cannot be known statically; other files in the same proposal remain
    checked.
    """

    t0 = time.monotonic_ns()
    undefined_by_file: dict[str, list[str]] = {}
    wildcard_files: list[str] = []
    checked_files: list[str] = []

    for change in patch.iter_file_changes():
        if change.action == "delete":
            continue

        filename = change.file_path
        checked_files.append(filename)
        try:
            tree = ast.parse(change.code_content, filename=filename)
            if _has_wildcard_import(tree):
                wildcard_files.append(filename)
                continue
            table = symtable.symtable(change.code_content, filename, "exec")
        except SyntaxError as exc:
            return _cr(
                False,
                f"cannot check undefined names in {filename}: SyntaxError: {exc}",
                t0,
                metadata={"syntax_error_file": filename},
            )

        undefined = sorted(_undefined_names(table))
        if undefined:
            undefined_by_file[filename] = undefined

    metadata = {
        "checked_files": checked_files,
        "undefined_names": undefined_by_file,
        "wildcard_import_files": wildcard_files,
    }
    if undefined_by_file:
        detail = "; ".join(
            f"{filename}: {', '.join(names)}"
            for filename, names in undefined_by_file.items()
        )
        return _cr(False, f"undefined names: {detail}", t0, metadata=metadata)

    if not checked_files:
        detail = "delete actions only - no undefined-name check"
    elif wildcard_files:
        detail = "undefined-name check ok; wildcard import fallback: " + ", ".join(
            wildcard_files
        )
    else:
        detail = "undefined-name check ok"
    return _cr(True, detail, t0, metadata=metadata)


def _has_wildcard_import(tree: ast.AST) -> bool:
    return any(
        isinstance(node, ast.ImportFrom)
        and any(alias.name == "*" for alias in node.names)
        for node in ast.walk(tree)
    )


def _undefined_names(module_table: symtable.SymbolTable) -> set[str]:
    module_definitions = {
        symbol.get_name()
        for symbol in module_table.get_symbols()
        if _defines_name(symbol)
    }
    valid_globals = module_definitions | _BUILTIN_NAMES | _IMPLICIT_MODULE_GLOBALS
    undefined: set[str] = set()

    for table in _walk_tables(module_table):
        for symbol in table.get_symbols():
            if not symbol.is_referenced() or _defines_name(symbol):
                continue
            if symbol.is_free() or symbol.is_nonlocal():
                continue
            name = symbol.get_name()
            if symbol.is_global() and name not in valid_globals:
                undefined.add(name)
            elif not symbol.is_global() and not symbol.is_local():
                undefined.add(name)

    return undefined


def _defines_name(symbol: symtable.Symbol) -> bool:
    return symbol.is_assigned() or symbol.is_imported() or symbol.is_parameter()


def _walk_tables(
    table: symtable.SymbolTable,
) -> Iterable[symtable.SymbolTable]:
    yield table
    for child in table.get_children():
        yield from _walk_tables(child)


def _cr(
    passed: bool,
    detail: str,
    t0: int,
    *,
    metadata: dict[str, object],
) -> CheckResult:
    elapsed = int((time.monotonic_ns() - t0) / 1_000_000)
    return CheckResult(
        name="V1b_undefined_names",
        passed=passed,
        severity="light",
        detail=detail,
        elapsed_ms=elapsed,
        metadata=metadata,
    )
