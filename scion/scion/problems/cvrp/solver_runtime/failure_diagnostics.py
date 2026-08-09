"""Bounded diagnostics for candidate solver exceptions."""
from __future__ import annotations

import re
from pathlib import Path
from types import ModuleType
from typing import Any

_ATTRIBUTE_RE = re.compile(
    r"(?:type object |)'(?P<owner>[A-Za-z_]\w*)' object has no attribute "
    r"'(?P<name>[A-Za-z_]\w*)'"
)
_TYPE_ATTRIBUTE_RE = re.compile(
    r"type object '(?P<owner>[A-Za-z_]\w*)' has no attribute "
    r"'(?P<name>[A-Za-z_]\w*)'"
)


def exception_failure_diagnostic(
    exc: Exception,
    *,
    workspace_root: str | Path,
) -> dict[str, str]:
    """Extract only a dotted symbol and workspace-relative source location."""

    return {
        "failing_symbol": _failing_symbol(exc),
        "callsite": _workspace_callsite(exc, workspace_root=workspace_root),
    }


def _failing_symbol(exc: Exception) -> str:
    if isinstance(exc, AttributeError):
        name = str(getattr(exc, "name", "") or "").strip()
        owner_object: Any = getattr(exc, "obj", None)
        if name and owner_object is not None:
            owner = (
                owner_object.__name__
                if isinstance(owner_object, (type, ModuleType))
                else type(owner_object).__name__
            )
            if _identifier(owner) and _identifier(name):
                return f"{owner}.{name}"
        message = str(exc)
        match = _TYPE_ATTRIBUTE_RE.search(message) or _ATTRIBUTE_RE.search(message)
        if match is not None:
            return f"{match.group('owner')}.{match.group('name')}"
    if isinstance(exc, NameError):
        name = str(getattr(exc, "name", "") or "").strip()
        if _identifier(name):
            return name
    return ""


def _workspace_callsite(
    exc: Exception,
    *,
    workspace_root: str | Path,
) -> str:
    workspace = Path(workspace_root).resolve()
    selected: tuple[str, int] | None = None
    current = exc.__traceback__
    while current is not None:
        source = Path(current.tb_frame.f_code.co_filename).resolve()
        try:
            relative = source.relative_to(workspace)
        except ValueError:
            current = current.tb_next
            continue
        selected = (relative.as_posix(), int(current.tb_lineno))
        current = current.tb_next
    if selected is None:
        return ""
    return f"{selected[0]}:{selected[1]}"


def _identifier(value: str) -> bool:
    return bool(value) and value.isidentifier()


__all__ = ["exception_failure_diagnostic"]
