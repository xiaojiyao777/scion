"""Discover host-visible source records for typed edit normalization."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from scion.core.paths import normalize_relative_patch_path

_SOURCE_ROLES = ("target", "dependency", "caller", "peer")
_DEVELOPMENT_CHECKS = ("D3_unit_tests", "D4_regression_tests")


def source_files_from_context(context: Mapping[str, Any] | None) -> dict[str, str]:
    """Return provider-visible editable source keyed by canonical path."""

    sources, _public_tests, visible_sources, _dependencies = _source_context_files(
        context
    )
    return {
        path: content for path, content in sources.items() if path in visible_sources
    }


def all_source_files_from_context(
    context: Mapping[str, Any] | None,
) -> dict[str, str]:
    """Return the host-held complete editable source corpus."""

    return _source_context_files(context)[0]


def public_test_files_from_context(
    context: Mapping[str, Any] | None,
) -> dict[str, str]:
    """Return read-only public development test text keyed by canonical path."""

    return _source_context_files(context)[1]


def research_files_from_context(
    context: Mapping[str, Any] | None,
) -> dict[str, str]:
    """Return the combined editable and read-only code-research corpus."""

    sources, public_tests, _visible_sources, dependencies = _source_context_files(
        context
    )
    dependencies = {
        path: content
        for path, content in dependencies.items()
        if isinstance(content, str)
    }
    return {**sources, **dependencies, **public_tests}


def read_only_files_from_context(
    context: Mapping[str, Any] | None,
) -> dict[str, str | None]:
    """Return public dependencies and tests, without granting patch access."""

    _sources, public_tests, _visible, dependencies = _source_context_files(context)
    return {**dependencies, **public_tests}


def _source_context_files(
    context: Mapping[str, Any] | None,
) -> tuple[dict[str, str], dict[str, str], frozenset[str], dict[str, str | None]]:
    if not context:
        return {}, {}, frozenset(), {}
    source_context = context.get("editable_source_context")
    if not isinstance(source_context, Mapping):
        return {}, {}, frozenset(), {}
    required = {
        "approved_target",
        "sources",
        "public_tests",
        "target_api_guidance",
    }
    if not required <= set(source_context) or set(source_context) - required - {
        "read_only_sources"
    }:
        raise ValueError("editable source context has unknown or missing keys")
    target = _canonical_path(source_context.get("approved_target"))
    if not isinstance(source_context.get("target_api_guidance"), str):
        raise ValueError("editable source target_api_guidance must be a string")
    sources = source_context.get("sources")
    if not isinstance(sources, list):
        raise ValueError("editable source context sources must be a list")
    records: dict[str, str] = {}
    visible_sources: set[str] = set()
    seen: set[str] = set()
    for entry in sources:
        if not isinstance(entry, Mapping) or set(entry) != {
            "path",
            "content",
            "roles",
            "visible",
        }:
            raise ValueError("editable source entry has unknown or missing keys")
        path = _canonical_path(entry.get("path"))
        if path in seen:
            raise ValueError(f"duplicate editable source path: {path}")
        seen.add(path)
        content = entry.get("content")
        if content is not None and not isinstance(content, str):
            raise ValueError(f"editable source content must be text or null: {path}")
        roles = entry.get("roles")
        if (
            not isinstance(roles, list)
            or not roles
            or any(role not in _SOURCE_ROLES for role in roles)
            or roles != [role for role in _SOURCE_ROLES if role in roles]
            or len(roles) != len(set(roles))
        ):
            raise ValueError(f"editable source roles are invalid: {path}")
        visible = entry.get("visible")
        if not isinstance(visible, bool):
            raise ValueError(f"editable source visibility must be boolean: {path}")
        if visible:
            visible_sources.add(path)
        if isinstance(content, str):
            records[path] = content
    if target not in seen:
        raise ValueError("editable source approved target is missing")
    public_records: dict[str, str] = {}
    public_tests = source_context.get("public_tests")
    if not isinstance(public_tests, list):
        raise ValueError("editable source context public_tests must be a list")
    for entry in public_tests:
        if not isinstance(entry, Mapping) or set(entry) != {
            "path",
            "content",
            "check_name",
            "visible",
        }:
            raise ValueError("public test entry has unknown or missing keys")
        path = _canonical_path(entry.get("path"))
        if path in seen:
            raise ValueError(f"duplicate research source path: {path}")
        seen.add(path)
        content = entry.get("content")
        if content is not None and not isinstance(content, str):
            raise ValueError(f"public test content must be text or null: {path}")
        if entry.get("check_name") not in _DEVELOPMENT_CHECKS:
            raise ValueError(f"public test check_name is invalid: {path}")
        if not isinstance(entry.get("visible"), bool):
            raise ValueError(f"public test visibility must be boolean: {path}")
        if isinstance(content, str):
            public_records[path] = content
    dependencies: dict[str, str | None] = {}
    read_only = source_context.get("read_only_sources", [])
    if not isinstance(read_only, list):
        raise ValueError("read-only source context must be a list")
    for entry in read_only:
        if not isinstance(entry, Mapping) or set(entry) != {
            "path",
            "content",
            "visible",
        }:
            raise ValueError("read-only source entry has unknown or missing keys")
        path = _canonical_path(entry.get("path"))
        if path in seen:
            raise ValueError(f"duplicate research source path: {path}")
        seen.add(path)
        content = entry.get("content")
        if content is not None and not isinstance(content, str):
            raise ValueError(f"read-only source content must be text or null: {path}")
        if not isinstance(entry.get("visible"), bool):
            raise ValueError(f"read-only source visibility must be boolean: {path}")
        # A redacted read-only source is still forbidden as a patch target.
        dependencies[path] = content
    return records, public_records, frozenset(visible_sources), dependencies


def _canonical_path(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError(f"editable source path must be a string: {value!r}")
    try:
        path = normalize_relative_patch_path(value)
    except ValueError as exc:
        raise ValueError(f"invalid editable source path: {value!r}") from exc
    if path != value:
        raise ValueError(f"editable source path is not canonical: {value}")
    return path
