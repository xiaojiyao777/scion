"""Discover host-visible source records for typed edit normalization."""

from __future__ import annotations

import fnmatch
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


_SOURCE_FILE_RECORD_RE = re.compile(
    r"^(?:###\s+|File:\s*)(?P<path>[^\n]+?)"
    r"(?:\s+\([^\n]*\))?\n"
    r"(?P<metadata>(?:[^\n]*\n)*?)"
    r"```(?:python|py)?\n"
    r"(?P<content>.*?)"
    r"(?P<terminal_newline>\n)```",
    re.DOTALL | re.MULTILINE,
)

_FENCED_SOURCE_RE = re.compile(
    r"^\s*```(?:python|py)?\n(?P<content>.*?)(?P<terminal_newline>\n)```\s*$",
    re.DOTALL,
)

_LOOSE_FILE_SOURCE_RE = re.compile(
    r"^\s*File:\s*(?P<path>[^\n]+?)\n```(?:python|py)?\n(?P<content>.*)\Z",
    re.DOTALL,
)


@dataclass(frozen=True)
class SourceRecord:
    content: str
    provenance: str

    @property
    def digest(self) -> str:
        return source_digest_for_content(self.content)


def source_digest_for_content(content: str) -> str:
    """Return the canonical per-file source digest for typed edit checks."""

    return hashlib.sha256(str(content).encode("utf-8")).hexdigest()


def source_files_from_context(context: Mapping[str, Any] | None) -> dict[str, str]:
    return {
        path: record.content
        for path, record in source_records_from_context(context).items()
    }


def source_records_from_context(
    context: Mapping[str, Any] | None,
    *,
    requested_paths: tuple[str, ...] = (),
) -> dict[str, SourceRecord]:
    if not context:
        return {}
    source_files: dict[str, SourceRecord] = {}
    for key in ("patch_source_files", "source_files", "editable_source_files"):
        value = context.get(key)
        if isinstance(value, Mapping):
            for path, content in value.items():
                normalized_path = _normalize_path(path)
                source = _source_text_from_context_value(
                    content,
                    expected_path=normalized_path,
                )
                if normalized_path and source is not None:
                    _put_source_record(
                        source_files,
                        normalized_path,
                        source,
                        key,
                    )
    target_file = _normalize_path(context.get("target_file"))
    target_content = context.get("target_file_code")
    target_source = _source_text_from_context_value(
        target_content,
        expected_path=target_file,
    )
    if target_file and target_source is not None:
        _put_source_record(source_files, target_file, target_source, "target_file_code")
    original_code = context.get("original_code")
    if isinstance(original_code, str):
        _put_source_records(
            source_files,
            _parse_original_code_source(original_code),
            "original_code",
        )
    for key in ("solver_design_branch_current_integration_files",):
        integration_files = context.get(key)
        if isinstance(integration_files, str):
            _put_source_records(
                source_files,
                _parse_markdown_source_files(integration_files),
                key,
            )
    _put_source_records(
        source_files,
        _solver_design_full_read_sources(
            context.get("solver_design_full_algorithm_file_reads")
        ),
        "solver_design_full_algorithm_file_reads",
    )
    _put_source_records(
        source_files,
        _agentic_tool_observation_full_read_sources(
            context.get("agentic_tool_observations")
        ),
        "agentic_tool_observations.context.read_algorithm_file",
    )
    integration_files = context.get("agentic_required_full_integration_files")
    if isinstance(integration_files, str):
        _put_source_records(
            source_files,
            _parse_markdown_source_files(integration_files),
            "agentic_required_full_integration_files",
        )
    for requested_path in requested_paths:
        if requested_path in source_files:
            continue
        fallback = _branch_workspace_source(context, requested_path)
        if fallback is not None:
            _put_source_record(
                source_files,
                requested_path,
                fallback,
                "branch_workspace_fallback",
            )
    return source_files


def _put_source_records(
    records: dict[str, SourceRecord],
    sources: Mapping[str, str],
    provenance: str,
) -> None:
    for path, content in sources.items():
        _put_source_record(records, path, content, provenance)


def _put_source_record(
    records: dict[str, SourceRecord],
    path: str,
    content: str,
    provenance: str,
) -> None:
    normalized_path = _normalize_path(path)
    if not normalized_path or content is None:
        return
    records[normalized_path] = SourceRecord(
        content=str(content),
        provenance=provenance,
    )


def _solver_design_full_read_sources(value: Any) -> dict[str, str]:
    records: dict[str, str] = {}
    if isinstance(value, Mapping):
        value = value.get("reads")
    if not isinstance(value, (list, tuple)):
        return records
    for item in value:
        if not isinstance(item, Mapping):
            continue
        source = _full_read_source_from_payload(item)
        path = _normalize_path(item.get("file_path"))
        if path and source is not None:
            records[path] = source
    return records


def _agentic_tool_observation_full_read_sources(value: Any) -> dict[str, str]:
    records: dict[str, str] = {}
    if not isinstance(value, (list, tuple)):
        return records
    for item in value:
        if not isinstance(item, Mapping):
            continue
        if item.get("tool_name") != "context.read_algorithm_file":
            continue
        if bool(item.get("is_error")):
            continue
        payload = item.get("structured_payload")
        if not isinstance(payload, Mapping):
            continue
        source = _full_read_source_from_payload(payload)
        path = _normalize_path(payload.get("file_path"))
        if path and source is not None:
            records[path] = source
    return records


def _full_read_source_from_payload(payload: Mapping[str, Any]) -> str | None:
    if payload.get("readable") is not True:
        return None
    if payload.get("active") is False:
        return None
    if bool(payload.get("truncated")):
        return None
    content = payload.get("content_preview")
    if not isinstance(content, str):
        return None
    return content


def _branch_workspace_source(
    context: Mapping[str, Any],
    requested_path: str,
) -> str | None:
    normalized_path = _normalize_path(requested_path)
    if not normalized_path or not _path_editable_for_branch_fallback(
        context,
        normalized_path,
    ):
        return None
    root_value = (
        context.get("branch_workspace")
        or context.get("solver_design_source_root")
        or context.get("source_root")
    )
    if not isinstance(root_value, str) or not root_value.strip():
        return None
    try:
        root = Path(root_value).resolve()
        candidate = (root / normalized_path).resolve()
        candidate.relative_to(root)
    except Exception:
        return None
    if not candidate.is_file():
        return None
    try:
        return candidate.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None


def _path_editable_for_branch_fallback(
    context: Mapping[str, Any],
    path: str,
) -> bool:
    editable_patterns = _pattern_list(context.get("editable_patterns"))
    if not editable_patterns:
        return False
    frozen_patterns = _pattern_list(context.get("frozen_patterns"))
    if any(fnmatch.fnmatchcase(path, pattern) for pattern in frozen_patterns):
        return False
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in editable_patterns)


def _pattern_list(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        items = re.split(r"[\n,]+", value)
    elif isinstance(value, (list, tuple, set, frozenset)):
        items = [str(item) for item in value]
    else:
        return ()
    return tuple(item.strip() for item in items if item and item.strip())


def _parse_markdown_source_files(rendered: str) -> dict[str, str]:
    files: dict[str, str] = {}
    for match in _SOURCE_FILE_RECORD_RE.finditer(rendered):
        path = _normalize_path(match.group("path"))
        content = match.group("content") + match.group("terminal_newline")
        metadata = match.group("metadata") or ""
        if path and _is_current_source_record(metadata, content):
            files[path] = content
    return files


def _parse_original_code_source(rendered: str) -> dict[str, str]:
    return _parse_markdown_source_files(rendered)


def _source_text_from_context_value(
    value: Any,
    *,
    expected_path: str = "",
) -> str | None:
    if not _is_existing_source_text(value):
        return None
    text = str(value)
    markdown_sources = _parse_markdown_source_files(text)
    normalized_expected = _normalize_path(expected_path)
    if normalized_expected and normalized_expected in markdown_sources:
        return markdown_sources[normalized_expected]
    if not normalized_expected and len(markdown_sources) == 1:
        return next(iter(markdown_sources.values()))

    fenced = _FENCED_SOURCE_RE.match(text)
    if fenced:
        return fenced.group("content") + fenced.group("terminal_newline")

    loose = _LOOSE_FILE_SOURCE_RE.match(text)
    if loose:
        path = _normalize_path(loose.group("path"))
        if not normalized_expected or path == normalized_expected:
            return _strip_trailing_fence(loose.group("content"))

    return text


def _strip_trailing_fence(value: str) -> str:
    text = str(value)
    stripped = text.rstrip()
    if stripped.endswith("```"):
        stripped = stripped[:-3].rstrip()
        return stripped + ("\n" if text.endswith("\n") else "")
    return text


def _is_existing_source_text(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    stripped = value.strip()
    if not stripped:
        return False
    lowered = stripped.lower()
    return not (
        "will be created" in lowered
        or "source_status=new_file" in lowered
        or "new_file_placeholder" in lowered
        or "could not read" in lowered
        or "missing_current_source" in lowered
        or "readable=false" in lowered
        or "visibility=not_visible" in lowered
    )


def _is_current_source_record(metadata: str, content: str) -> bool:
    text = f"{metadata}\n{content}".lower()
    return not (
        "readable=false" in text
        or "missing_current_source" in text
        or "visibility=not_visible" in text
        or "could not read" in text
    )


def _normalize_path(value: Any) -> str:
    return str(value or "").replace("\\", "/").lstrip("/").strip()
