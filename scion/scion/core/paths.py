"""Path hygiene helpers for tainted proposal file paths."""
from __future__ import annotations

from pathlib import PurePosixPath


def normalize_relative_patch_path(file_path: str) -> str:
    """Return a normalized POSIX relative path or raise ValueError.

    Patch file paths are tainted LLM output. Scion stores and matches them as
    POSIX-style paths relative to the candidate workspace root.
    """
    if not isinstance(file_path, str):
        raise ValueError("patch file_path must be a string")

    if file_path == "" or file_path != file_path.strip():
        raise ValueError("patch file_path must be a non-empty trimmed path")

    if "\x00" in file_path:
        raise ValueError("patch file_path contains NUL byte")

    if "\\" in file_path:
        raise ValueError("patch file_path must use POSIX '/' separators")

    path = PurePosixPath(file_path)
    if path.is_absolute():
        raise ValueError("patch file_path must be relative")

    parts = file_path.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError("patch file_path contains empty, '.', or '..' path segment")

    normalized = PurePosixPath(*parts).as_posix()
    if normalized in {"", "."}:
        raise ValueError("patch file_path must point to a file")

    return normalized
