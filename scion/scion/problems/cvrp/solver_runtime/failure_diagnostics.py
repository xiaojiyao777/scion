"""Bounded diagnostics for candidate solver exceptions."""

import re
from pathlib import Path
from types import ModuleType

_ATTRIBUTE_RE = re.compile(
    r"(?:type object )?'(?P<owner>[A-Za-z_]\w*)'(?: object)? has no attribute "
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
        owner_object = getattr(exc, "obj", None)
        if name and owner_object is not None:
            owner = type(owner_object).__name__
            if isinstance(owner_object, (type, ModuleType)):
                owner = owner_object.__name__
            if owner.isidentifier() and name.isidentifier():
                return f"{owner}.{name}"
        if match := _ATTRIBUTE_RE.search(str(exc)):
            return f"{match.group('owner')}.{match.group('name')}"
    if isinstance(exc, NameError):
        name = str(getattr(exc, "name", "") or "").strip()
        if name.isidentifier():
            return name
    return ""


def _workspace_callsite(exc: Exception, *, workspace_root: str | Path) -> str:
    workspace = Path(workspace_root).resolve()
    selected = ""
    current = exc.__traceback__
    while current is not None:
        source = Path(current.tb_frame.f_code.co_filename).resolve()
        try:
            relative = source.relative_to(workspace)
        except ValueError:
            pass
        else:
            selected = f"{relative.as_posix()}:{current.tb_lineno}"
        current = current.tb_next
    return selected
