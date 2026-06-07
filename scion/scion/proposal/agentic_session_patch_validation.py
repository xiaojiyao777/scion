"""Deterministic code-stage patch validation helpers."""
from __future__ import annotations

from collections import Counter
import json
import re
from typing import Any, Mapping

from scion.core.models import (
    HypothesisProposal,
    PatchProposal,
    mechanism_changes,
    patch_file_changes,
)
from scion.core.paths import normalize_relative_patch_path
from scion.proposal.agentic_utils import _drop_empty_dict

_SOURCE_FILE_RE = re.compile(
    r"^(?:###\s+|File:\s*)(?P<path>[^\n]+?)"
    r"(?:\s+\([^\n]*\))?\n"
    r"(?:[^\n]*\n)*?"
    r"```(?:python|py)?\n"
    r"(?P<content>.*?)"
    r"(?P<terminal_newline>\n)```",
    re.DOTALL | re.MULTILINE,
)

_TELEMETRY_CALL_RE = re.compile(
    r"(?P<receiver>context|self\.context)\."
    r"(?P<helper>record_(?:phase|iteration|move))\(\s*"
    r"(?P<quote>['\"])(?P<mechanism_id>[A-Za-z][A-Za-z0-9_]{1,63})(?P=quote)"
)


def _code_stage_identity_issue(
    hypothesis: HypothesisProposal,
    patch: PatchProposal,
    *,
    code_context: Mapping[str, Any] | None = None,
) -> str | None:
    expected_ids = _mechanism_id_set(hypothesis)
    patch_ids = _mechanism_id_set(patch)
    if expected_ids or patch_ids:
        if expected_ids != patch_ids:
            return (
                "code_stage_identity_mismatch: patch mechanism_changes ids must "
                "exactly match the approved hypothesis. "
                f"expected={sorted(expected_ids)!r}; observed={sorted(patch_ids)!r}. "
                "Retry the same patch mechanism identity; do not add, drop, or "
                "rename mechanism ids."
            )
    telemetry_usages = _new_telemetry_mechanism_usages_from_patch(
        patch,
        code_context=code_context,
    )
    telemetry_ids = {
        str(usage.get("mechanism_id") or "").strip()
        for usage in telemetry_usages
        if str(usage.get("mechanism_id") or "").strip()
    }
    telemetry_identity_allowlist = _telemetry_identity_allowlist(code_context)
    unexpected_telemetry_ids = sorted(
        telemetry_ids - expected_ids - telemetry_identity_allowlist
    )
    if expected_ids and unexpected_telemetry_ids:
        unexpected_set = set(unexpected_telemetry_ids)
        offending_usages = [
            usage
            for usage in telemetry_usages
            if str(usage.get("mechanism_id") or "").strip() in unexpected_set
        ][:8]
        usage_detail = ""
        if offending_usages:
            usage_detail = (
                " Offending generated telemetry usages: "
                + json.dumps(offending_usages, sort_keys=True)
                + "."
            )
        return (
            "code_stage_telemetry_identity_mismatch: patch introduces or "
            "increases generated telemetry for mechanism id(s) not declared "
            "by the approved hypothesis: "
            f"{unexpected_telemetry_ids!r}. Use only protected mechanism "
            f"id(s) {sorted(expected_ids)!r} for new mechanism evidence, or "
            "remove unrelated telemetry. Baseline or structural telemetry ids "
            "visible in source context may remain only when unchanged; do not "
            "introduce or increase them as mechanism evidence."
            f"{usage_detail}"
        )
    return None


def _code_integration_visibility_issue(
    patch: PatchProposal,
    manifest: Any,
) -> dict[str, Any] | None:
    changed_paths = [
        _normalize_patch_path(change.file_path)
        for change in patch.additional_changes or ()
        if getattr(change, "action", None) != "create"
    ]
    changed_paths = [path for path in changed_paths if path]
    if not changed_paths:
        return None
    visible_paths = _full_visible_code_prompt_paths(manifest)
    missing = sorted(path for path in dict.fromkeys(changed_paths) if path not in visible_paths)
    if not missing:
        return None
    return {
        "paths": tuple(missing),
        "detail": (
            "code_integration_file_visibility_missing: additional_changes "
            "modify integration file(s) whose full current source was not "
            f"API-visible in the code prompt: {missing!r}. Retry with the same "
            "hypothesis and patch intent after projecting those files in full."
        ),
    }


def _code_context_with_required_full_integration_files(
    code_context: Mapping[str, Any],
    paths: Any,
) -> dict[str, Any]:
    retry_context = dict(code_context)
    source_files = _code_context_source_by_path(retry_context)
    required_sections: list[str] = []
    for path in paths or ():
        normalized = _normalize_patch_path(path)
        content = source_files.get(normalized)
        if not normalized or content is None:
            continue
        required_sections.append(
            f"### {normalized}\n"
            "Provenance: branch-current integration source required after "
            "code visibility invariant failure\n"
            f"```python\n{content}```"
        )
    if required_sections:
        retry_context["agentic_required_full_integration_files"] = "\n\n".join(
            required_sections
        )
    return retry_context


def _new_telemetry_mechanism_ids_from_patch(
    patch: PatchProposal,
    *,
    code_context: Mapping[str, Any] | None = None,
) -> set[str]:
    return {
        str(usage.get("mechanism_id") or "").strip()
        for usage in _new_telemetry_mechanism_usages_from_patch(
            patch,
            code_context=code_context,
        )
        if str(usage.get("mechanism_id") or "").strip()
    }


def _telemetry_identity_allowlist(
    code_context: Mapping[str, Any] | None,
) -> set[str]:
    if not isinstance(code_context, Mapping):
        return set()
    taxonomy = code_context.get("active_subject_taxonomy")
    if not isinstance(taxonomy, Mapping):
        return set()
    return {
        str(item or "").strip()
        for item in taxonomy.get("telemetry_identity_allowlist", ()) or ()
        if str(item or "").strip()
    }


def _mechanism_id_set(proposal: HypothesisProposal | PatchProposal) -> set[str]:
    return {
        str(change.id).strip()
        for change in mechanism_changes(proposal)
        if str(change.id).strip()
    }


def _new_telemetry_mechanism_usages_from_patch(
    patch: PatchProposal,
    *,
    code_context: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], ...]:
    before_sources = _code_context_source_by_path(code_context)
    usages: list[dict[str, Any]] = []
    for change_index, change in enumerate(patch_file_changes(patch)):
        path = _normalize_patch_path(change.file_path)
        after_usages = _telemetry_mechanism_usages(
            change.code_content,
            file_path=path,
            action=str(change.action or ""),
            change_index=change_index,
        )
        if not before_sources or change.action == "create":
            usages.extend(after_usages)
            continue
        before_counts = _telemetry_mechanism_counts(before_sources.get(path, ""))
        seen_after: Counter[str] = Counter()
        for usage in after_usages:
            mechanism_id = str(usage.get("mechanism_id") or "").strip()
            if not mechanism_id:
                continue
            seen_after[mechanism_id] += 1
            if seen_after[mechanism_id] > before_counts.get(mechanism_id, 0):
                usages.append(usage)
    return tuple(usages)


def _telemetry_mechanism_counts(source: Any) -> Counter[str]:
    return Counter(
        match.group("mechanism_id")
        for match in _TELEMETRY_CALL_RE.finditer(str(source or ""))
    )


def _telemetry_mechanism_usages(
    source: Any,
    *,
    file_path: str,
    action: str,
    change_index: int,
) -> list[dict[str, Any]]:
    text = str(source or "")
    usages: list[dict[str, Any]] = []
    for match in _TELEMETRY_CALL_RE.finditer(text):
        line_start = text.rfind("\n", 0, match.start()) + 1
        line_end = text.find("\n", match.start())
        if line_end < 0:
            line_end = len(text)
        line_text = text[line_start:line_end].strip()
        json_pointer = (
            "/code_content"
            if change_index == 0
            else f"/additional_changes/{change_index - 1}/code_content"
        )
        usages.append(
            _drop_empty_dict(
                {
                    "mechanism_id": match.group("mechanism_id"),
                    "file_path": file_path,
                    "json_pointer": json_pointer,
                    "action": action,
                    "line": text.count("\n", 0, match.start()) + 1,
                    "column": match.start() - line_start + 1,
                    "helper": match.group("helper"),
                    "receiver": match.group("receiver"),
                    "line_text": _telemetry_usage_snippet(line_text),
                    "usage_kind": "new_or_increased_generated_telemetry",
                    "repair_guidance": (
                        "Replace this telemetry mechanism id with an approved "
                        "protected mechanism id, or remove this newly added "
                        "mechanism-evidence call."
                    ),
                }
            )
        )
    return usages


def _telemetry_usage_snippet(text: str, max_chars: int = 240) -> str:
    text = str(text or "").strip()
    if len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - 3)] + "..."


def _code_context_source_by_path(
    code_context: Mapping[str, Any] | None,
) -> dict[str, str]:
    if not isinstance(code_context, Mapping):
        return {}
    result: dict[str, str] = {}
    target_path = _normalize_patch_path(code_context.get("target_file"))
    target_source = code_context.get("target_file_code")
    if target_path and isinstance(target_source, str) and target_source.strip():
        parsed = _parse_markdown_source_files(target_source)
        result[target_path] = parsed.get(target_path, target_source)
    for key in (
        "agentic_required_full_integration_files",
        "solver_design_branch_current_integration_files",
    ):
        result.update(_parse_markdown_source_files(code_context.get(key)))
    result.update(
        _full_algorithm_read_sources(
            code_context.get("solver_design_full_algorithm_file_reads")
        )
    )
    result.update(
        _agentic_tool_observation_full_read_sources(
            code_context.get("agentic_tool_observations")
        )
    )
    return result


def _full_visible_code_prompt_paths(manifest: Any) -> set[str]:
    if not isinstance(manifest, Mapping):
        return set()
    ledger = manifest.get("code_file_visibility_ledger")
    if not isinstance(ledger, Mapping):
        return set()
    paths: set[str] = set()
    target = ledger.get("target_file")
    if isinstance(target, Mapping) and target.get("full_content_visible_in_rendered_prompt"):
        path = _normalize_patch_path(target.get("file_path"))
        if path:
            paths.add(path)
    for record in ledger.get("integration_files") or ():
        if not isinstance(record, Mapping):
            continue
        if not record.get("full_content_visible_in_rendered_prompt"):
            continue
        path = _normalize_patch_path(record.get("file_path"))
        if path:
            paths.add(path)
    for record in ledger.get("algorithm_file_reads") or ():
        if not isinstance(record, Mapping):
            continue
        if not record.get("full_content_visible_in_rendered_prompt"):
            continue
        path = _normalize_patch_path(record.get("file_path"))
        if path:
            paths.add(path)
    return paths


def _full_algorithm_read_sources(value: Any) -> dict[str, str]:
    if isinstance(value, Mapping):
        value = value.get("reads")
    if not isinstance(value, (list, tuple)):
        return {}
    sources: dict[str, str] = {}
    for item in value:
        if not isinstance(item, Mapping):
            continue
        path = _normalize_patch_path(item.get("file_path"))
        content = _full_algorithm_read_content(item)
        if path and content is not None:
            sources[path] = content
    return sources


def _agentic_tool_observation_full_read_sources(value: Any) -> dict[str, str]:
    if not isinstance(value, (list, tuple)):
        return {}
    sources: dict[str, str] = {}
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
        path = _normalize_patch_path(payload.get("file_path"))
        content = _full_algorithm_read_content(payload)
        if path and content is not None:
            sources[path] = content
    return sources


def _full_algorithm_read_content(payload: Mapping[str, Any]) -> str | None:
    if payload.get("readable") is not True:
        return None
    if payload.get("active") is False:
        return None
    if bool(payload.get("truncated")):
        return None
    content = payload.get("content_preview")
    return content if isinstance(content, str) else None


def _parse_markdown_source_files(value: Any) -> dict[str, str]:
    if not isinstance(value, str):
        return {}
    files: dict[str, str] = {}
    for match in _SOURCE_FILE_RE.finditer(value):
        path = _normalize_patch_path(match.group("path"))
        content = match.group("content") + match.group("terminal_newline")
        if path:
            files[path] = content
    return files


def _normalize_patch_path(value: Any) -> str:
    try:
        return normalize_relative_patch_path(str(value or ""))
    except ValueError:
        text = str(value or "").replace("\\", "/").strip()
        while text.startswith("./"):
            text = text[2:]
        return text.lstrip("/")
