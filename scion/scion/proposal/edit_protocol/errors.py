"""Shared edit-protocol error types and payload helpers."""

from __future__ import annotations

import json


class PatchEditProtocolError(ValueError):
    """Raised when a typed edit cannot be safely normalized."""


def raise_duplicate_file_error(
    *,
    reason: str,
    file_path: str,
    change_pointer: str,
    prior_change_pointers: tuple[str, ...],
    detail: str,
) -> None:
    raise PatchEditProtocolError(
        json.dumps(
            {
                "error": "patch_edit_protocol",
                "reason": reason,
                "file_path": file_path,
                "json_pointer": change_pointer,
                "prior_json_pointers": list(prior_change_pointers),
                "detail": detail,
                "guidance": (
                    "Use one file change for this file or serializable "
                    "exact_replace edits whose old_string values match the "
                    "content after earlier same-file edits. Do not emit no-op "
                    "exact_replace entries such as old_string == new_string or "
                    "EOF/trailing newline edits."
                ),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )
