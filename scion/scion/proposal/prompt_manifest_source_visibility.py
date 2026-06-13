"""Source visibility ledgers for API-visible prompt manifests.

This module owns source-file visibility audits derived from rendered prompt
sections and sanitized proposal context.  It does not decide proposal quality;
it records whether source that proposal prompts depend on was visible to the
provider for the current call.
"""

from __future__ import annotations

import json
import re
from typing import Any, Mapping

from scion.proposal.edit_protocol.source_discovery import source_digest_for_content
from scion.proposal.prompt_manifest_accounting import _text_digest


_SOURCE_FILE_RECORD_RE = re.compile(
    r"^(?:###\s+|File:\s*)(?P<path>[^\n]+?)"
    r"(?:\s+\([^\n]*\))?\n"
    r"(?P<metadata>(?:[^\n]*\n)*?)"
    r"```(?:python|py)?\n"
    r"(?P<content>.*?)"
    r"(?P<terminal_newline>\n)```",
    re.DOTALL | re.MULTILINE,
)


def _code_file_visibility_ledger(
    context: Mapping[str, Any],
    *,
    provider_prompt_text: str,
    section_statuses: Mapping[str, Mapping[str, Any]],
    call_kind: str,
) -> dict[str, Any]:
    if call_kind != "code":
        return {}
    target_file = _normalize_path(context.get("target_file"))
    target_source_record = _source_record_from_context_value(
        context.get("target_file_code"),
        expected_path=target_file,
    )
    target_file_create_mode = _target_file_create_mode(
        context,
        target_source_record=target_source_record,
    )
    target_record = _code_file_visibility_record(
        file_path=target_file,
        content=(
            target_source_record.get("content")
            if target_source_record is not None
            else None
        ),
        role="approved_target_file",
        section_name="approved_target_file_current_content",
        provider_prompt_text=provider_prompt_text,
        section_statuses=section_statuses,
        source_metadata=target_source_record,
        target_file_create_mode=target_file_create_mode,
    )
    integration_records: list[dict[str, Any]] = []
    seen_integration_paths: set[str] = set()
    for section_key, section_name, role in (
        (
            "agentic_required_full_integration_files",
            "required_full_integration_edit_sources",
            "required_full_integration_edit_source",
        ),
        (
            "solver_design_branch_current_integration_files",
            "branch_current_integration_files",
            "branch_current_integration_file",
        ),
    ):
        for file_path, source_record in _parse_markdown_source_file_records(
            context.get(section_key)
        ).items():
            if file_path in seen_integration_paths:
                continue
            seen_integration_paths.add(file_path)
            integration_records.append(
                _code_file_visibility_record(
                    file_path=file_path,
                    content=source_record.get("content"),
                    role=role,
                    section_name=section_name,
                    provider_prompt_text=provider_prompt_text,
                    section_statuses=section_statuses,
                    source_metadata=source_record,
                )
            )
    algorithm_read_records: list[dict[str, Any]] = []
    for file_path, content in _code_context_full_algorithm_read_sources(
        context
    ).items():
        algorithm_read_records.append(
            _code_file_visibility_record(
                file_path=file_path,
                content=content,
                role="solver_design_full_algorithm_file_read",
                section_name="solver_design_full_algorithm_file_reads",
                provider_prompt_text=provider_prompt_text,
                section_statuses=section_statuses,
            )
        )
    if not target_record and not integration_records and not algorithm_read_records:
        return {}
    source_guarantees = _code_phase_source_guarantees(
        target_record=target_record,
        integration_records=integration_records,
        algorithm_read_records=algorithm_read_records,
        target_file_create_mode=target_file_create_mode,
    )
    return _drop_empty(
        {
            "schema_version": "code-file-visibility-ledger.v1",
            "call_kind": call_kind,
            "prompt_contract": (
                "Code generation must use API-visible target and integration "
                "source sections for typed edits; read receipts alone do not "
                "prove the provider saw the file contents."
            ),
            "source_visibility_guarantees": source_guarantees,
            "target_file": target_record,
            "integration_files": integration_records,
            "algorithm_file_reads": algorithm_read_records,
        }
    )


def _target_file_create_mode(
    context: Mapping[str, Any],
    *,
    target_source_record: Mapping[str, Any] | None,
) -> bool:
    action = str(context.get("action") or "").strip()
    if action:
        return action in {"create", "create_new"}
    source_status = _source_status(
        target_source_record,
        (
            str(target_source_record.get("content"))
            if isinstance(target_source_record, Mapping)
            and target_source_record.get("content") is not None
            else None
        ),
    )
    if source_status == "new_file":
        return True
    return _explicit_false(context.get("target_file_exists"))


def _explicit_false(value: Any) -> bool:
    if isinstance(value, bool):
        return value is False
    return str(value).strip().lower() in {"false", "0", "no"}


def _hypothesis_target_source_visibility_ledger(
    context: Mapping[str, Any],
    *,
    provider_prompt_text: str,
    included_observations: list[Mapping[str, Any]],
    section_statuses: Mapping[str, Mapping[str, Any]],
    call_kind: str,
) -> dict[str, Any]:
    if not str(call_kind).startswith("hypothesis"):
        return {}
    raw_intent = context.get("agentic_hypothesis_target_intent")
    if not isinstance(raw_intent, Mapping):
        return {}
    intent_value = raw_intent.get("intent")
    intent = intent_value if isinstance(intent_value, Mapping) else raw_intent
    target_file = _normalize_path(intent.get("target_file"))
    action = _normalize_action(intent.get("action"))
    if not target_file:
        return {}
    target_source_required = action in {"modify", "remove"}
    source_items = [
        item
        for item in included_observations
        if item.get("tool_name") == "context.read_algorithm_file"
        and _normalize_path(item.get("file_path")) == target_file
    ]
    best_source = _best_hypothesis_source_item(source_items)
    placeholder = context.get("agentic_hypothesis_target_placeholder")
    placeholder_visible = bool(
        isinstance(placeholder, Mapping)
        and _rendered_contains_text(provider_prompt_text, target_file)
        and (
            not target_source_required
            or str(placeholder.get("owner_required") or "").lower() == "false"
        )
    )
    section_status = section_statuses.get(
        "hypothesis_target_intent_preflight",
        {},
    )
    placeholder_section_status = section_statuses.get(
        "hypothesis_target_placeholder",
        {},
    )
    return _drop_empty(
        {
            "schema_version": "hypothesis-target-source-visibility-ledger.v1",
            "call_kind": call_kind,
            "prompt_contract": (
                "For existing target intents, the first formal hypothesis "
                "prompt should contain full or bounded dedicated source for "
                "the selected target. For create-new intents, a visible "
                "placeholder is sufficient and no owner source is required."
            ),
            "target_intent": _drop_empty(
                {
                    "change_locus": intent.get("change_locus")
                    or intent.get("surface"),
                    "action": action,
                    "target_file": target_file,
                    "mechanism_id": intent.get("mechanism_id"),
                    "mechanism_family": intent.get("mechanism_family"),
                    "confidence": intent.get("confidence"),
                }
            ),
            "target_source_required": target_source_required,
            "preflight_section_status": section_status.get("status"),
            "owner_source": best_source,
            "placeholder": _drop_empty(
                {
                    "visible": placeholder_visible,
                    "section_status": placeholder_section_status.get("status"),
                    "target_file": target_file if placeholder_visible else "",
                    "owner_required": False if not target_source_required else None,
                }
            ),
            "visibility_status": (
                "full_dedicated_source_visible"
                if best_source.get("full_content_visible_in_dedicated_source_section")
                else "source_visible"
                if best_source.get("content_preview_visible_in_rendered_prompt")
                or best_source.get("full_content_visible_in_rendered_prompt")
                else "create_new_placeholder_visible"
                if placeholder_visible and not target_source_required
                else "not_visible"
            ),
        }
    )


def _material_difference_requirement_visibility_ledger(
    context: Mapping[str, Any],
    *,
    provider_prompt_text: str,
    section_statuses: Mapping[str, Mapping[str, Any]],
    call_kind: str,
) -> dict[str, Any]:
    if not str(call_kind).startswith("hypothesis"):
        return {}
    requirement = context.get("material_difference_requirement")
    if not isinstance(requirement, Mapping) or requirement.get("required") is False:
        return {}
    if not (
        requirement.get("required") is True
        or str(requirement.get("record_id") or "").strip()
        or str(requirement.get("required_for") or "").strip()
    ):
        return {}
    section_name = "material_difference_requirement"
    section_status = section_statuses.get(section_name, {})
    record_id = str(requirement.get("record_id") or "").strip()
    required_for = str(requirement.get("required_for") or "").strip()
    requirement_source = str(requirement.get("requirement_source") or "").strip()
    record_id_visible = bool(
        record_id and _rendered_contains_literal(provider_prompt_text, record_id)
    )
    required_for_visible = bool(
        required_for and _rendered_contains_literal(provider_prompt_text, required_for)
    )
    section_visible = section_status.get("status") == "included"
    visible = bool(section_visible and (record_id_visible or required_for_visible))
    candidate_release_reasons = _string_items(
        requirement.get("candidate_release_reasons")
    )
    return _drop_empty(
        {
            "schema_version": (
                "material-difference-requirement-visibility-ledger.v1"
            ),
            "call_kind": call_kind,
            "required": True,
            "source": "scheduler_audit_metadata",
            "requirement_source": requirement_source,
            "required_for": required_for,
            "record_id": record_id,
            "record_digest": requirement.get("record_digest"),
            "reason_code_count": len(_string_items(requirement.get("reason_codes"))),
            "candidate_count": requirement.get("candidate_count"),
            "candidate_branch_count": len(
                _string_items(requirement.get("candidate_branch_ids"))
            ),
            "candidate_release_reason_count": len(candidate_release_reasons),
            "candidate_release_reasons": candidate_release_reasons,
            "section_name": section_name,
            "section_status": section_status.get("status", "missing"),
            "section_char_count": section_status.get("char_count", 0),
            "record_id_visible": record_id_visible,
            "required_for_visible": required_for_visible,
            "visible": visible,
            "visibility_status": (
                "first_class_section_visible" if visible else "not_visible"
            ),
            "decision_features_excluded": True,
            "proposal_visibility_only": True,
        }
    )


def _best_hypothesis_source_item(
    items: list[Mapping[str, Any]],
) -> dict[str, Any]:
    if not items:
        return {}
    ranked = sorted(
        items,
        key=lambda item: (
            bool(item.get("full_content_visible_in_dedicated_source_section")),
            bool(item.get("full_content_visible_in_rendered_prompt")),
            bool(item.get("content_preview_visible_in_rendered_prompt")),
            int(item.get("visible_content_chars") or 0),
        ),
        reverse=True,
    )
    item = ranked[0]
    return _drop_empty(
        {
            "observation_id": item.get("observation_id"),
            "file_path": item.get("file_path"),
            "source": item.get("source"),
            "source_provenance": item.get("source_provenance"),
            "visibility_status": item.get("prompt_visibility_status"),
            "included_in_prompt_for_call": item.get("included_in_prompt_for_call"),
            "full_content_included_in_prompt": item.get(
                "full_content_included_in_prompt"
            ),
            "full_content_visible_in_rendered_prompt": item.get(
                "full_content_visible_in_rendered_prompt"
            ),
            "full_content_visible_in_dedicated_source_section": item.get(
                "full_content_visible_in_dedicated_source_section"
            ),
            "content_preview_visible_in_rendered_prompt": item.get(
                "content_preview_visible_in_rendered_prompt"
            ),
        }
    )


def _code_file_visibility_record(
    *,
    file_path: str,
    content: str | None,
    role: str,
    section_name: str,
    provider_prompt_text: str,
    section_statuses: Mapping[str, Mapping[str, Any]],
    source_metadata: Mapping[str, Any] | None = None,
    target_file_create_mode: bool = False,
) -> dict[str, Any]:
    if not file_path:
        return {}
    source_status = _source_status(source_metadata, content)
    if target_file_create_mode and source_status == "missing_current_source":
        source_status = "new_file"
    readable = source_status == "current_branch_source"
    content_visible = bool(
        readable
        and content is not None
        and _rendered_contains_text(provider_prompt_text, content)
    )
    placeholder_visible = bool(
        not readable
        and content is not None
        and _rendered_contains_text(provider_prompt_text, content)
    )
    section_status = section_statuses.get(section_name, {})
    section_included = section_status.get("status") == "included"
    source_digest = (
        source_digest_for_content(content)
        if readable and isinstance(content, str)
        else ""
    )
    source_digest_literal_visible = bool(
        source_digest and _rendered_contains_literal(provider_prompt_text, source_digest)
    )
    source_digest_derivable_from_source = bool(source_digest and content_visible)
    record = {
        "file_path": file_path,
        "role": role,
        "source_requirement_category": _source_requirement_category(role),
        "section": section_name,
        "section_status": section_status.get("status", "missing"),
        "section_char_count": section_status.get("char_count", 0),
        "source_status": source_status,
        "source_provenance": (
            "new_file_placeholder"
            if target_file_create_mode and source_status == "new_file"
            else _source_provenance(source_metadata)
        ),
        "readable": readable,
        "content_chars": len(content or ""),
        "content_hash": _text_digest(content, length=16) if content else "",
        "source_digest": source_digest,
        "source_digest_visible_in_rendered_prompt": source_digest_literal_visible,
        "source_digest_available_from_visible_source": (
            source_digest_derivable_from_source
        ),
        "source_digest_visibility_status": (
            "literal_visible"
            if source_digest_literal_visible
            else "derivable_from_visible_source"
            if source_digest_derivable_from_source
            else "not_visible"
        ),
        "content_visible_in_rendered_prompt": content_visible,
        "placeholder_visible_in_rendered_prompt": placeholder_visible,
        "prompt_visibility_status": (
            "create_new_target_no_current_source"
            if target_file_create_mode
            else "full_current_source_visible"
            if bool(section_included and content_visible)
            else "placeholder_visible"
            if placeholder_visible
            else "not_visible"
        ),
        "full_content_included_in_prompt": bool(section_included and content_visible),
        "full_content_visible_in_rendered_prompt": bool(
            section_included and content_visible
        ),
    }
    if target_file_create_mode:
        record["target_file_create_mode"] = True
        record["visibility_status"] = "create_new_target_no_current_source"
    return record


def _source_requirement_category(role: str) -> str:
    role_text = str(role or "")
    if role_text == "approved_target_file":
        return "target_source"
    if role_text == "required_full_integration_edit_source":
        return "required_integration_source"
    if role_text == "branch_current_integration_file":
        return "source_dependency_source"
    if role_text.startswith("solver_design_full_algorithm_file_read"):
        return "activation_source_dependency_source"
    return "source_dependency_source"


def _code_phase_source_guarantees(
    *,
    target_record: Mapping[str, Any],
    integration_records: list[Mapping[str, Any]],
    algorithm_read_records: list[Mapping[str, Any]],
    target_file_create_mode: bool,
) -> dict[str, Any]:
    required_integration_records = [
        record
        for record in integration_records
        if str(record.get("role") or "")
        == "required_full_integration_edit_source"
    ]
    target_source_visible = _source_record_satisfies_code_phase_requirement(
        target_record,
        target_file_create_mode=target_file_create_mode,
    )
    target_requirement = _source_requirement_diagnostic(
        target_record,
        requirement_category="target_source",
        target_file_create_mode=target_file_create_mode,
    )
    required_integration_requirements = [
        _source_requirement_diagnostic(
            record,
            requirement_category="required_integration_source",
            target_record=target_record,
            target_source_visible=target_source_visible,
        )
        for record in required_integration_records
        if isinstance(record, Mapping) and record
    ]
    activation_source_dependency_requirements = [
        _source_requirement_diagnostic(
            record,
            requirement_category="activation_source_dependency_source",
        )
        for record in algorithm_read_records
        if isinstance(record, Mapping) and record
    ]
    source_requirements = [
        requirement
        for requirement in (
            [target_requirement]
            + required_integration_requirements
            + activation_source_dependency_requirements
        )
        if requirement
    ]
    missing_required_sources = [
        requirement
        for requirement in source_requirements
        if requirement.get("required") is True
        and requirement.get("required_source_satisfied") is not True
    ]
    missing_required = _unique_paths(
        requirement.get("file_path") for requirement in missing_required_sources
    )
    required_integration_visible = all(
        requirement.get("required_source_satisfied") is True
        for requirement in required_integration_requirements
    )
    algorithm_reads_visible = all(
        requirement.get("required_source_satisfied") is True
        for requirement in activation_source_dependency_requirements
    )
    return _drop_empty(
        {
            "schema_version": "code-phase-source-visibility-guarantees.v1",
            "phase": "code",
            "policy": (
                "Compression may remove governance boilerplate, duplicated raw "
                "logs, and raw cross-branch payloads, but must keep source/code "
                "needed to modify or judge the approved target and required "
                "integration files."
            ),
            "target_file_create_mode": bool(target_file_create_mode),
            "target_source_visible": target_source_visible,
            "required_integration_source_visible": required_integration_visible,
            "algorithm_file_read_source_visible": algorithm_reads_visible,
            "protected_source_visible": not missing_required,
            "protected_source_count": len(source_requirements),
            "required_integration_source_count": len(required_integration_records),
            "algorithm_file_read_source_count": len(algorithm_read_records),
            "target_source_identity": target_requirement,
            "target_path": target_requirement.get("file_path"),
            "source_requirements": source_requirements,
            "required_integration_source_requirements": (
                required_integration_requirements
            ),
            "activation_source_dependency_requirements": (
                activation_source_dependency_requirements
            ),
            "missing_required_sources": missing_required_sources,
            "missing_required_source_paths": missing_required,
            "duplicate_target_paths_satisfied_by_target_source": _unique_paths(
                requirement.get("file_path")
                for requirement in required_integration_requirements
                if requirement.get("satisfied_by") == "target_source"
            ),
            "decision_features_excluded": True,
            "manifest_observability_only": True,
        }
    )


def _source_requirement_diagnostic(
    record: Mapping[str, Any],
    *,
    requirement_category: str,
    target_file_create_mode: bool = False,
    target_record: Mapping[str, Any] | None = None,
    target_source_visible: bool = False,
) -> dict[str, Any]:
    if not isinstance(record, Mapping) or not record:
        return {}
    path = _normalize_path(record.get("file_path"))
    target_path = _normalize_path(
        target_record.get("file_path") if isinstance(target_record, Mapping) else ""
    )
    duplicate_target_satisfied = bool(
        requirement_category == "required_integration_source"
        and path
        and target_path
        and path == target_path
        and target_source_visible
    )
    satisfied = (
        True
        if duplicate_target_satisfied
        else _source_record_satisfies_code_phase_requirement(
            record,
            target_file_create_mode=target_file_create_mode,
        )
    )
    required = not (
        requirement_category == "target_source" and target_file_create_mode
    )
    missing_reason = ""
    if required and not satisfied:
        missing_reason = _source_requirement_missing_reason(record)
    return _drop_empty(
        {
            "file_path": path,
            "requirement_category": requirement_category,
            "role": record.get("role"),
            "section": record.get("section"),
            "section_status": record.get("section_status"),
            "source_status": record.get("source_status"),
            "source_provenance": record.get("source_provenance"),
            "required": required,
            "required_source_satisfied": bool(satisfied),
            "target_file_create_mode": bool(target_file_create_mode),
            "satisfied_by": (
                "target_source" if duplicate_target_satisfied else ""
            ),
            "duplicate_target_requirement": duplicate_target_satisfied,
            "full_content_visible_in_rendered_prompt": record.get(
                "full_content_visible_in_rendered_prompt"
            ),
            "source_digest": record.get("source_digest"),
            "source_digest_visible_in_rendered_prompt": record.get(
                "source_digest_visible_in_rendered_prompt"
            ),
            "source_digest_available_from_visible_source": record.get(
                "source_digest_available_from_visible_source"
            ),
            "source_digest_visibility_status": record.get(
                "source_digest_visibility_status"
            ),
            "missing_reason": missing_reason,
        }
    )


def _source_requirement_missing_reason(record: Mapping[str, Any]) -> str:
    if not isinstance(record, Mapping) or not record:
        return "source_record_missing"
    if str(record.get("source_status") or "") == "missing_current_source":
        return "missing_current_source"
    if str(record.get("source_status") or "") == "new_file":
        return "new_file_has_no_current_source"
    section_status = str(record.get("section_status") or "")
    if section_status != "included":
        return "section_not_included"
    if not bool(record.get("full_content_visible_in_rendered_prompt")):
        return "full_current_source_not_visible"
    if str(record.get("source_status") or "") != "current_branch_source":
        return "not_current_branch_source"
    return "source_requirement_unsatisfied"


def _unique_paths(values: Any) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values or ():
        path = _normalize_path(value)
        if not path or path in seen:
            continue
        seen.add(path)
        result.append(path)
    return result


def _source_record_satisfies_code_phase_requirement(
    record: Mapping[str, Any],
    *,
    target_file_create_mode: bool = False,
) -> bool:
    if not isinstance(record, Mapping) or not record:
        return bool(target_file_create_mode)
    if target_file_create_mode:
        return (
            record.get("target_file_create_mode") is True
            and str(record.get("source_status") or "") == "new_file"
            and bool(record.get("placeholder_visible_in_rendered_prompt"))
        )
    return (
        str(record.get("section_status") or "") == "included"
        and str(record.get("source_status") or "") == "current_branch_source"
        and bool(record.get("full_content_visible_in_rendered_prompt"))
    )


def _parse_markdown_source_files(value: Any) -> dict[str, str]:
    if not isinstance(value, str):
        return {}
    files: dict[str, str] = {}
    for path, record in _parse_markdown_source_file_records(value).items():
        if _source_status(record, record.get("content")) == "current_branch_source":
            files[path] = str(record.get("content") or "")
    return files


def _parse_markdown_source_file_records(value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(value, str):
        return {}
    files: dict[str, dict[str, Any]] = {}
    for match in _SOURCE_FILE_RECORD_RE.finditer(value):
        path = _normalize_path(match.group("path"))
        content = match.group("content") + match.group("terminal_newline")
        metadata = match.group("metadata") or ""
        if path:
            files[path] = {
                "content": content,
                "metadata": metadata,
                "source_status": _source_status_from_text(metadata, content),
                "source_provenance": _source_provenance_from_text(metadata),
            }
    return files


def _code_context_full_algorithm_read_sources(
    context: Mapping[str, Any],
) -> dict[str, str]:
    sources: dict[str, str] = {}
    for item in _iter_full_algorithm_read_payloads(
        context.get("solver_design_full_algorithm_file_reads")
    ):
        path = _normalize_path(item.get("file_path"))
        content = item.get("content_preview")
        if path and isinstance(content, str):
            sources[path] = content
    observations = context.get("agentic_tool_observations")
    if isinstance(observations, (list, tuple)):
        for observation in observations:
            if not isinstance(observation, Mapping):
                continue
            if observation.get("tool_name") != "context.read_algorithm_file":
                continue
            if bool(observation.get("is_error")):
                continue
            payload = observation.get("structured_payload")
            for item in _iter_full_algorithm_read_payloads([payload]):
                path = _normalize_path(item.get("file_path"))
                content = item.get("content_preview")
                if path and isinstance(content, str):
                    sources[path] = content
    return sources


def _iter_full_algorithm_read_payloads(value: Any) -> list[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        value = value.get("reads")
    if not isinstance(value, (list, tuple)):
        return []
    payloads: list[Mapping[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping):
            continue
        if item.get("readable") is not True:
            continue
        if item.get("active") is False:
            continue
        if bool(item.get("truncated")):
            continue
        if not isinstance(item.get("content_preview"), str):
            continue
        payloads.append(item)
    return payloads


def _source_text_from_context_value(
    value: Any,
    *,
    expected_path: str = "",
) -> str | None:
    record = _source_record_from_context_value(value, expected_path=expected_path)
    if record is None:
        return None
    if _source_status(record, record.get("content")) != "current_branch_source":
        return None
    content = record.get("content")
    return str(content) if isinstance(content, str) else None


def _source_record_from_context_value(
    value: Any,
    *,
    expected_path: str = "",
) -> dict[str, Any] | None:
    if not isinstance(value, str):
        return None
    text = value
    markdown_sources = _parse_markdown_source_file_records(text)
    normalized_expected = _normalize_path(expected_path)
    if normalized_expected and normalized_expected in markdown_sources:
        return markdown_sources[normalized_expected]
    if not normalized_expected and len(markdown_sources) == 1:
        return next(iter(markdown_sources.values()))
    if _looks_like_missing_source(text):
        return {
            "content": None,
            "metadata": text,
            "source_status": "missing_current_source",
            "source_provenance": "missing_current_source",
        }
    return {
        "content": text,
        "metadata": "",
        "source_status": "current_branch_source",
        "source_provenance": "",
    } if text.strip() else None


def _source_status(
    source_metadata: Mapping[str, Any] | None,
    content: str | None,
) -> str:
    if source_metadata is not None:
        status = str(source_metadata.get("source_status") or "").strip()
        if status:
            return status
        metadata = str(source_metadata.get("metadata") or "")
        return _source_status_from_text(metadata, content)
    if content is None or _looks_like_missing_source(content):
        return "missing_current_source"
    return "current_branch_source"


def _source_status_from_text(metadata: str, content: str | None) -> str:
    text = f"{metadata}\n{content or ''}".lower()
    if "source_status=new_file" in text or "new_file_placeholder" in text:
        return "new_file"
    if (
        "readable=false" in text
        or "missing_current_source" in text
        or "visibility=not_visible" in text
        or "could not read" in text
    ):
        return "missing_current_source"
    return "current_branch_source"


def _source_provenance(source_metadata: Mapping[str, Any] | None) -> str:
    if source_metadata is None:
        return ""
    explicit = str(source_metadata.get("source_provenance") or "").strip()
    if explicit:
        return explicit
    return _source_provenance_from_text(str(source_metadata.get("metadata") or ""))


def _source_provenance_from_text(metadata: str) -> str:
    match = re.search(r"\bProvenance:\s*([^;\n]+)", str(metadata))
    return match.group(1).strip() if match else ""


def _looks_like_missing_source(value: Any) -> bool:
    text = str(value or "").strip().lower()
    return (
        not text
        or "will be created" in text
        or "source_status=new_file" in text
        or "new_file_placeholder" in text
        or text.startswith("(could not read ")
        or "could not read" in text
        or "missing_current_source" in text
        or "readable=false" in text
    )


def _normalize_path(value: Any) -> str:
    text = str(value or "").replace("\\", "/").strip()
    while text.startswith("./"):
        text = text[2:]
    return text.lstrip("/")


def _normalize_action(value: Any) -> str:
    text = str(value or "").strip()
    return "create_new" if text == "create" else text


def _string_items(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _drop_empty(value: dict[str, Any]) -> dict[str, Any]:
    return {
        key: item
        for key, item in value.items()
        if item not in (None, "", (), [], {})
    }


def _rendered_contains_literal(rendered_prompt: str, value: Any) -> bool:
    text = str(value or "")
    return bool(text and text in rendered_prompt)


def _rendered_contains_text(rendered_prompt: str, value: Any) -> bool:
    if value is None:
        return False
    text = str(value)
    if not text:
        return False
    if text in rendered_prompt:
        return True
    encoded = json.dumps(text)
    if encoded in rendered_prompt:
        return True
    if len(encoded) >= 2 and encoded[1:-1] in rendered_prompt:
        return True
    return False


__all__ = [
    "_code_file_visibility_ledger",
    "_hypothesis_target_source_visibility_ledger",
    "_material_difference_requirement_visibility_ledger",
]
