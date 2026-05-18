"""Public reference helpers for status, summaries, and reports.

Internal execution objects often need absolute filesystem paths so tests and
audit tools can reopen artifacts.  Public status/report payloads should expose
only stable relative refs or opaque artifact ids.
"""
from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path, PurePosixPath
from typing import Any, Mapping
from urllib.parse import unquote, urlsplit


_PATH_REF_KEYS = {
    "artifact_path",
    "artifact_ref",
    "code_archive_ref",
    "observations_ref",
    "protocol_raw_metrics_ref",
    "raw_metrics_path",
    "raw_metrics_ref",
}

_CASE_REF_KEYS = {
    "case",
    "case_id",
    "case_ids",
}

_EMBEDDED_PATH_PREFIX = r"(?P<prefix>^|[\s'\"(<[{=,;:])"
_LOCAL_FILE_URI_WINDOWS_PATH_RE = re.compile(
    _EMBEDDED_PATH_PREFIX
    + r"(?P<path>file:(?://(?:localhost)?)?/[A-Za-z]:[\\/][^\s'\"`<>{}\[\](),;:!?]+)",
    re.IGNORECASE,
)
_LOCAL_FILE_URI_POSIX_PATH_RE = re.compile(
    _EMBEDDED_PATH_PREFIX
    + r"(?P<path>file:(?://(?:localhost)?)?/(?!/)[^\s'\"`<>{}\[\](),;:!?]+)",
    re.IGNORECASE,
)
_UNIX_ABSOLUTE_PATH_RE = re.compile(
    _EMBEDDED_PATH_PREFIX
    + r"(?P<path>/(?!/)[^\s'\"`<>{}\[\](),;:!?]+)"
)
_WINDOWS_ABSOLUTE_PATH_RE = re.compile(
    _EMBEDDED_PATH_PREFIX
    + r"(?P<path>[A-Za-z]:[\\/][^\s'\"`<>{}\[\](),;:!?]+)"
)
_TRAILING_PATH_PUNCTUATION = ".,"


def public_artifact_ref(
    value: Any,
    *,
    base_dir: str | Path | None = None,
    kind: str = "artifact",
) -> str | None:
    """Return a public, non-absolute reference for an internal path-like value."""

    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return text

    path_text = _local_file_uri_path(text) or text
    normalized = path_text.replace("\\", "/")
    if not _looks_absolute(path_text):
        safe = _normalize_relative_ref(normalized)
        return safe if safe is not None else _opaque_ref(path_text, kind=kind)

    if base_dir is not None:
        try:
            base = Path(base_dir).resolve()
            path = Path(path_text).resolve()
            rel = path.relative_to(base).as_posix()
            safe = _normalize_relative_ref(rel)
            if safe is not None:
                return safe
        except Exception:
            pass

    return _opaque_ref(path_text, kind=kind)


def public_case_ref(
    value: Any,
    *,
    base_dir: str | Path | None = None,
) -> str | None:
    return public_artifact_ref(value, base_dir=base_dir, kind="case")


def redact_public_refs(
    value: Any,
    *,
    base_dir: str | Path | None = None,
) -> Any:
    """Recursively convert internal path refs in public payloads to public refs."""

    if isinstance(value, Mapping):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            key_lower = key_text.lower()
            if key_lower in {"artifacts", "artifact_refs"} and isinstance(item, Mapping):
                cleaned[key_text] = _redact_path_value(item, base_dir=base_dir)
            elif key_lower in _CASE_REF_KEYS:
                cleaned[key_text] = _redact_case_value(item, base_dir=base_dir)
            elif _is_path_ref_key(key_lower):
                cleaned[key_text] = _redact_path_value(item, base_dir=base_dir)
            else:
                cleaned[key_text] = redact_public_refs(item, base_dir=base_dir)
        return cleaned
    if isinstance(value, tuple):
        return [redact_public_refs(item, base_dir=base_dir) for item in value]
    if isinstance(value, list):
        return [redact_public_refs(item, base_dir=base_dir) for item in value]
    if isinstance(value, os.PathLike):
        return public_artifact_ref(value, base_dir=base_dir, kind="artifact")
    if isinstance(value, str):
        if _looks_absolute(value):
            return public_artifact_ref(value, base_dir=base_dir, kind="artifact")
        return _redact_embedded_absolute_paths(
            value,
            base_dir=base_dir,
            kind="artifact",
        )
    return value


def contains_absolute_path(value: Any) -> bool:
    """Best-effort check used by tests for public payloads."""

    if isinstance(value, Mapping):
        return any(contains_absolute_path(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(contains_absolute_path(item) for item in value)
    if isinstance(value, os.PathLike):
        return _looks_absolute(str(value))
    if isinstance(value, str):
        return _contains_absolute_path_text(value)
    return False


def _redact_path_value(
    value: Any,
    *,
    base_dir: str | Path | None,
) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _redact_path_value(item, base_dir=base_dir)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_redact_path_value(item, base_dir=base_dir) for item in value]
    if (
        isinstance(value, str)
        and not _looks_absolute(value)
        and _has_embedded_absolute_path(value)
    ):
        return _redact_embedded_absolute_paths(
            value,
            base_dir=base_dir,
            kind="artifact",
        )
    return public_artifact_ref(value, base_dir=base_dir, kind="artifact")


def _redact_case_value(
    value: Any,
    *,
    base_dir: str | Path | None,
) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _redact_case_value(item, base_dir=base_dir)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [public_case_ref(item, base_dir=base_dir) for item in value]
    if (
        isinstance(value, str)
        and not _looks_absolute(value)
        and _has_embedded_absolute_path(value)
    ):
        return _redact_embedded_absolute_paths(value, base_dir=base_dir, kind="case")
    return public_case_ref(value, base_dir=base_dir)


def _is_path_ref_key(key: str) -> bool:
    if key in _PATH_REF_KEYS:
        return True
    return (
        key.endswith("_artifact_ref")
        or key.endswith("_artifact_path")
        or key.endswith("_metrics_ref")
        or key.endswith("_metrics_path")
    )


def _contains_absolute_path_text(value: str) -> bool:
    if _looks_absolute(value):
        return True
    return _has_embedded_absolute_path(value)


def _has_embedded_absolute_path(value: str) -> bool:
    return (
        _LOCAL_FILE_URI_WINDOWS_PATH_RE.search(value) is not None
        or _LOCAL_FILE_URI_POSIX_PATH_RE.search(value) is not None
        or _WINDOWS_ABSOLUTE_PATH_RE.search(value) is not None
        or _UNIX_ABSOLUTE_PATH_RE.search(value) is not None
    )


def _redact_embedded_absolute_paths(
    value: str,
    *,
    base_dir: str | Path | None,
    kind: str,
) -> str:
    if not _has_embedded_absolute_path(value):
        return value
    value = _replace_embedded_absolute_paths(
        value,
        pattern=_LOCAL_FILE_URI_WINDOWS_PATH_RE,
        base_dir=base_dir,
        kind=kind,
    )
    value = _replace_embedded_absolute_paths(
        value,
        pattern=_LOCAL_FILE_URI_POSIX_PATH_RE,
        base_dir=base_dir,
        kind=kind,
    )
    value = _replace_embedded_absolute_paths(
        value,
        pattern=_WINDOWS_ABSOLUTE_PATH_RE,
        base_dir=base_dir,
        kind=kind,
    )
    return _replace_embedded_absolute_paths(
        value,
        pattern=_UNIX_ABSOLUTE_PATH_RE,
        base_dir=base_dir,
        kind=kind,
    )


def _replace_embedded_absolute_paths(
    value: str,
    *,
    pattern: re.Pattern[str],
    base_dir: str | Path | None,
    kind: str,
) -> str:
    pieces: list[str] = []
    last_end = 0
    changed = False
    for match in pattern.finditer(value):
        path_start, path_end = match.span("path")
        path_text = match.group("path")
        path_ref, trailing = _split_trailing_path_punctuation(path_text)
        if not path_ref:
            continue
        pieces.append(value[last_end:path_start])
        pieces.append(public_artifact_ref(path_ref, base_dir=base_dir, kind=kind) or "")
        pieces.append(trailing)
        last_end = path_end
        changed = True
    if not changed:
        return value
    pieces.append(value[last_end:])
    return "".join(pieces)


def _split_trailing_path_punctuation(value: str) -> tuple[str, str]:
    end = len(value)
    while end > 0 and value[end - 1] in _TRAILING_PATH_PUNCTUATION:
        end -= 1
    return value[:end], value[end:]


def _looks_absolute(value: str) -> bool:
    if not value:
        return False
    local_uri_path = _local_file_uri_path(value)
    if local_uri_path is not None:
        return _looks_absolute(local_uri_path)
    return value.startswith("/") or (
        len(value) >= 3
        and value[1] == ":"
        and value[2] in {"/", "\\"}
        and value[0].isalpha()
    )


def _local_file_uri_path(value: str) -> str | None:
    if not value.lower().startswith("file:"):
        return None
    parsed = urlsplit(value)
    if parsed.scheme.lower() != "file":
        return None
    if parsed.netloc and parsed.netloc.lower() != "localhost":
        return None
    path = unquote(parsed.path)
    if not path.startswith("/"):
        return None
    if len(path) >= 4 and path[0] == "/" and path[1].isalpha() and path[2] == ":":
        return path[1:]
    return path


def _normalize_relative_ref(value: str) -> str | None:
    raw = value.replace(os.sep, "/")
    if not raw or raw in {".", ".."} or raw.startswith("/"):
        return None
    parts = PurePosixPath(raw).parts
    if any(part in {"", ".", ".."} for part in parts):
        return None
    return "/".join(parts)


def _opaque_ref(value: str, *, kind: str) -> str:
    basename = Path(value).name or kind
    basename = "".join(
        ch if ch.isalnum() or ch in {"-", "_", "."} else "_"
        for ch in basename
    ).strip("._")
    if not basename:
        basename = kind
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
    return f"{kind}:{basename}#{digest}"


__all__ = [
    "contains_absolute_path",
    "public_artifact_ref",
    "public_case_ref",
    "redact_public_refs",
]
