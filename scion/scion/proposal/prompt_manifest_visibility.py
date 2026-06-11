"""Prompt manifest visibility ledger helpers.

This module owns the compact, schema-visible visibility ledgers derived from
already-normalized prompt section records, proposal-tool observation records,
and source visibility records.
"""

from __future__ import annotations

from typing import Any, Mapping

from scion.proposal.agentic_models import AGENTIC_CODE_PHASE_CONTEXT_PROFILE


VISIBILITY_LEDGER_SCHEMA_VERSION = "prompt-visibility-ledger.v1"
VISIBILITY_STATUS_VALUES = (
    "full",
    "dedicated_projection",
    "summary",
    "truncated",
    "omitted",
)


def _tool_result_visibility_ledger(
    included_observations: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    ledger: list[dict[str, Any]] = []
    for item in included_observations:
        bounded_projection = _is_bounded_tool_projection(item)
        ledger.append(
            {
                "observation_id": item.get("observation_id"),
                "stable_observation_id": item.get("stable_observation_id")
                or item.get("observation_id"),
                "tool_name": item.get("tool_name"),
                "stable_name": item.get("stable_name") or item.get("tool_name"),
                "status": item.get("status"),
                "payload_hash": item.get("payload_hash")
                or item.get("payload_digest"),
                "visible_text_chars": item.get("visible_text_chars", 0),
                "visible_text_hash": item.get("visible_text_hash", ""),
                "rendered_visibility_flag": bool(
                    item.get("rendered_visibility_flag")
                ),
                "result_in_final_prompt": bool(
                    item.get("rendered_visibility_flag")
                ),
                "result_in_final_prompt_status": (
                    "included" if item.get("rendered_visibility_flag") else "omitted"
                ),
                "rendered_visibility_source": item.get(
                    "rendered_visibility_source", ""
                ),
                "truncated": item.get("truncated")
                if item.get("truncated") is not None
                else item.get("payload_truncated"),
                "projection_kind": (
                    "bounded_tool_projection"
                    if bounded_projection
                    else "full_or_summary_tool_projection"
                ),
                "truncation_scope": (
                    "tool_result_payload_projection"
                    if bounded_projection
                    else ""
                ),
                "prompt_section_truncation": False,
                "projection_reason": (
                    "Tool payload/content was bounded before rendering; this "
                    "is not prompt section truncation. See truncated_sections "
                    "for provider-visible prompt section truncation."
                    if bounded_projection
                    else ""
                ),
                "omitted": bool(item.get("omitted_from_rendered_prompt")),
                "omitted_reason": item.get("omitted_reason", ""),
                "content_projection_count": item.get("content_projection_count", 0),
                "visible_content_projection_count": item.get(
                    "visible_content_projection_count", 0
                ),
            }
        )
    return ledger


def _visibility_ledger(
    *,
    section_records: list[Mapping[str, Any]],
    included_observations: list[Mapping[str, Any]],
    code_file_visibility_ledger: Mapping[str, Any],
    material_difference_requirement_visibility_ledger: Mapping[str, Any],
) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for section in section_records:
        entries.append(_section_visibility_ledger_entry(section))
    for item in included_observations:
        entries.append(_tool_visibility_ledger_entry(item))
    for record in _iter_code_visibility_records(code_file_visibility_ledger):
        entries.append(_code_file_visibility_ledger_entry(record))
    if material_difference_requirement_visibility_ledger:
        entries.append(
            _material_difference_requirement_visibility_ledger_entry(
                material_difference_requirement_visibility_ledger
            )
        )

    status_counts = {status: 0 for status in VISIBILITY_STATUS_VALUES}
    for entry in entries:
        status = str(entry.get("visibility_status") or "omitted")
        if status not in status_counts:
            status = "omitted"
            entry["visibility_status"] = status
        status_counts[status] += 1
    return {
        "schema_version": VISIBILITY_LEDGER_SCHEMA_VERSION,
        "status_values": list(VISIBILITY_STATUS_VALUES),
        "entry_count": len(entries),
        "status_counts": status_counts,
        "entries": entries,
    }


def _section_visibility_ledger_entry(section: Mapping[str, Any]) -> dict[str, Any]:
    char_count = _coerce_int(section.get("char_count")) or 0
    status = (
        "omitted"
        if section.get("omitted")
        else "truncated"
        if section.get("truncated")
        else "full"
    )
    name = str(section.get("name") or "")
    return _drop_empty(
        {
            "entry_kind": "section",
            "section_name": name,
            "block_family": section.get("block_family", ""),
            "prompt_block_profile": section.get("prompt_block_profile", ""),
            "inclusion_reason": section.get("inclusion_reason", ""),
            "source": "provider_prompt_section",
            "source_ref": f"section:{name}" if name else "",
            "visibility_status": status,
            "char_count": char_count,
            "token_estimate": _token_estimate(char_count),
            "digest": section.get("content_hash") or "",
            "ref": f"section:{name}" if name else "",
            "projected_to_section": name,
            "projection_ref": f"section:{name}" if name else "",
        }
    )


def _section_block_family(name: str) -> str:
    if name.startswith("tool_selection") or name in {
        "stable_tool_selection_context_adapter_provider_rendered_anchors",
        "dynamic_tool_selection_context",
        "tool_selection_phase",
    }:
        return "tool_selection"
    if "proposal_tool_observation" in name or "tool_result" in name:
        return "tool_observation"
    if "active_algorithm_fact" in name or "active_solver" in name:
        return "active_facts"
    if "solver_design" in name or "algorithm_file" in name or "source" in name:
        return "source_context"
    if name in {
        "compact_research_signals",
        "experiment_history_this_branch",
        "globally_failed_blacklisted_approaches",
        "currently_occupied_c10_reports_duplicate_risk_diagnostics",
        "sibling_branches",
        "cross_branch_research_map",
        "branch_lesson_usage_context",
        "branch_follow_up_policy",
        "branch_dossier",
        "branch_direction",
        "objective_opportunity_profile",
        "problem_measurement_diagnostics",
        "exploration_coverage",
        "strategy_guidance",
        "champion_baseline_hints",
    }:
        return "research_signal"
    if "lesson" in name or "cross_branch" in name or name.startswith("branch_"):
        return "research_signal"
    if "contract" in name or "schema" in name or "permission" in name:
        return "governance"
    if name in {
        "analysis_steps_follow_in_order",
        "compact_safety_and_output_invariants",
        "task",
    }:
        return "governance"
    if "feedback" in name or "runtime" in name or "screening" in name:
        return "feedback"
    if "repair" in name or "failure" in name:
        return "repair_guidance"
    return "general"


def _section_prompt_block_profile(name: str) -> str:
    if name.startswith("tool_selection") or name in {
        "stable_tool_selection_context_adapter_provider_rendered_anchors",
        "dynamic_tool_selection_context",
    }:
        return "tool_selection"
    if name in {
        "approved_target_file_current_content",
        "branch_current_integration_files",
        "required_full_integration_edit_sources",
    }:
        return AGENTIC_CODE_PHASE_CONTEXT_PROFILE
    if "repair" in name or "failure" in name:
        return "repair"
    return "algorithm"


def _section_inclusion_reason(name: str, *, prompt_part: str) -> str:
    if prompt_part == "user":
        return "dynamic_phase_context"
    family = _section_block_family(name)
    if family in {"governance", "active_facts"}:
        return "always_v3"
    if family == "source_context":
        return "phase_required"
    if family == "tool_selection":
        return "planner_selected"
    if family == "repair_guidance":
        return "failure_mode"
    if family == "tool_observation":
        return "planner_selected"
    if family == "feedback":
        return "phase_required"
    return "always"


def _tool_visibility_ledger_entry(item: Mapping[str, Any]) -> dict[str, Any]:
    status = _tool_compact_visibility_status(item)
    source_chars = _first_int(
        item.get("size_chars"),
        item.get("content_preview_chars"),
        item.get("visible_text_chars"),
        default=0,
    )
    section_name = str(item.get("rendered_visibility_source") or "")
    projected_section = (
        "solver_design_full_algorithm_file_reads"
        if status == "dedicated_projection"
        and item.get("full_content_visible_in_dedicated_source_section")
        else section_name
    )
    observation_id = str(item.get("observation_id") or "")
    bounded_projection = _is_bounded_tool_projection(item)
    return _drop_empty(
        {
            "entry_kind": "tool_result",
            "section_name": section_name,
            "source": "proposal_tool",
            "source_tool": item.get("tool_name"),
            "source_ref": observation_id,
            "visibility_status": status,
            "char_count": source_chars,
            "token_estimate": _token_estimate(source_chars),
            "digest": (
                item.get("payload_hash")
                or item.get("payload_digest")
                or item.get("content_preview_hash")
                or item.get("visible_text_hash")
                or ""
            ),
            "ref": observation_id,
            "file_path": item.get("file_path"),
            "target_file": item.get("target_file"),
            "symbol": item.get("symbol"),
            "slice_id": item.get("slice_id"),
            "projected_to_section": projected_section,
            "projection_ref": (
                f"section:{projected_section}" if projected_section else ""
            ),
            "content_projection_count": item.get("content_projection_count", 0),
            "visible_content_projection_count": item.get(
                "visible_content_projection_count", 0
            ),
            "projection_kind": (
                "bounded_tool_projection"
                if bounded_projection
                else "full_or_summary_tool_projection"
            ),
            "truncation_scope": (
                "tool_result_payload_projection"
                if bounded_projection
                else ""
            ),
            "prompt_section_truncation": False,
        }
    )


def _code_file_visibility_ledger_entry(record: Mapping[str, Any]) -> dict[str, Any]:
    status = _code_file_compact_visibility_status(record)
    char_count = _coerce_int(record.get("content_chars")) or 0
    section_name = str(record.get("section") or "")
    return _drop_empty(
        {
            "entry_kind": "file_source",
            "section_name": section_name,
            "source": record.get("role") or "code_file",
            "source_tool": (
                "context.read_algorithm_file"
                if str(record.get("role") or "").startswith(
                    "solver_design_full_algorithm_file_read"
                )
                else ""
            ),
            "source_ref": record.get("file_path"),
            "visibility_status": status,
            "char_count": char_count,
            "token_estimate": _token_estimate(char_count),
            "digest": record.get("content_hash") or "",
            "ref": record.get("file_path"),
            "file_path": record.get("file_path"),
            "projected_to_section": (
                section_name
                if status in {"full", "dedicated_projection", "summary", "truncated"}
                else ""
            ),
            "projection_ref": (
                f"section:{section_name}"
                if section_name
                and status
                in {"full", "dedicated_projection", "summary", "truncated"}
                else ""
            ),
            "source_provenance": record.get("source_provenance"),
        }
    )


def _material_difference_requirement_visibility_ledger_entry(
    ledger: Mapping[str, Any],
) -> dict[str, Any]:
    section_name = str(ledger.get("section_name") or "material_difference_requirement")
    visible = bool(ledger.get("visible"))
    return _drop_empty(
        {
            "entry_kind": "material_difference_requirement",
            "section_name": section_name,
            "source": ledger.get("source") or "scheduler_audit_metadata",
            "source_ref": ledger.get("record_id"),
            "visibility_status": "full" if visible else "omitted",
            "char_count": ledger.get("section_char_count", 0),
            "token_estimate": _token_estimate(
                _coerce_int(ledger.get("section_char_count")) or 0
            ),
            "digest": ledger.get("record_digest") or "",
            "ref": ledger.get("record_id"),
            "projected_to_section": section_name if visible else "",
            "projection_ref": f"section:{section_name}" if visible else "",
            "requirement_source": ledger.get("requirement_source"),
            "required_for": ledger.get("required_for"),
            "candidate_release_reason_count": ledger.get(
                "candidate_release_reason_count"
            ),
            "decision_features_excluded": True,
        }
    )


def _tool_compact_visibility_status(item: Mapping[str, Any]) -> str:
    visible = bool(
        item.get("rendered_visibility_flag")
        or item.get("visible_text_chars")
        or item.get("content_preview_visible_in_rendered_prompt")
        or item.get("full_content_visible_in_rendered_prompt")
    )
    if not visible:
        return "omitted"
    if item.get("truncated") is True or item.get("payload_truncated") is True:
        return "truncated"
    if item.get("full_content_visible_in_dedicated_source_section"):
        return "dedicated_projection"
    if item.get("content_preview_visible_in_dedicated_source_section"):
        return "dedicated_projection"
    if item.get("full_content_visible_in_rendered_prompt"):
        return "full"
    if item.get("content_preview_visible_in_rendered_prompt"):
        return "summary"
    return "summary"


def _projection_diagnostics(
    *,
    section_records: list[Mapping[str, Any]],
    included_observations: list[Mapping[str, Any]],
) -> dict[str, Any]:
    truncated_sections = [
        str(record.get("name") or "")
        for record in section_records
        if record.get("truncated")
    ]
    bounded_tool_projections = [
        _drop_empty(
            {
                "observation_id": item.get("observation_id"),
                "tool_name": item.get("tool_name"),
                "file_path": item.get("file_path"),
                "target_file": item.get("target_file"),
                "slice_id": item.get("slice_id"),
                "projection_kind": "bounded_tool_projection",
                "truncation_scope": "tool_result_payload_projection",
                "prompt_section_truncation": False,
                "reason": (
                    "Tool result payload/content was bounded before rendering; "
                    "this does not mean the API-visible prompt section was "
                    "truncated."
                ),
            }
        )
        for item in included_observations
        if _is_bounded_tool_projection(item)
    ]
    return {
        "schema_version": "prompt-projection-diagnostics.v1",
        "prompt_section_truncation_count": len(truncated_sections),
        "truncated_sections": truncated_sections,
        "bounded_tool_projection_count": len(bounded_tool_projections),
        "bounded_tool_projections": bounded_tool_projections,
        "interpretation": (
            "truncated_sections reports provider-visible prompt section "
            "truncation. bounded_tool_projections reports tool payloads that "
            "were intentionally projected under a content budget before being "
            "rendered; those are not prompt section truncations."
        ),
    }


def _is_bounded_tool_projection(item: Mapping[str, Any]) -> bool:
    if item.get("truncated") is True or item.get("payload_truncated") is True:
        return True
    for projection in item.get("content_projections") or ():
        if (
            isinstance(projection, Mapping)
            and projection.get("full_content_included") is False
        ):
            return True
    return False


def _code_file_compact_visibility_status(record: Mapping[str, Any]) -> str:
    source_status = str(record.get("source_status") or "")
    if source_status == "missing_current_source":
        return "omitted"
    section_status = str(record.get("section_status") or "")
    if section_status == "omitted":
        return "omitted"
    if section_status == "truncated":
        return "truncated"
    if record.get("target_file_create_mode"):
        return "omitted"
    role = str(record.get("role") or "")
    if (
        role.startswith("solver_design_full_algorithm_file_read")
        and record.get("full_content_visible_in_rendered_prompt")
    ):
        return "dedicated_projection"
    if record.get("full_content_visible_in_rendered_prompt"):
        return "full"
    if record.get("placeholder_visible_in_rendered_prompt"):
        return "summary"
    return "omitted"


def _iter_code_visibility_records(
    code_file_visibility_ledger: Mapping[str, Any],
) -> list[Mapping[str, Any]]:
    if not isinstance(code_file_visibility_ledger, Mapping):
        return []
    records: list[Mapping[str, Any]] = []
    target_file = code_file_visibility_ledger.get("target_file")
    if isinstance(target_file, Mapping):
        records.append(target_file)
    for key in ("integration_files", "algorithm_file_reads"):
        values = code_file_visibility_ledger.get(key)
        if not isinstance(values, list):
            continue
        records.extend(item for item in values if isinstance(item, Mapping))
    return records


def _token_estimate(chars: int) -> int:
    return max(0, (int(chars or 0) + 3) // 4)


def _first_int(*values: Any, default: int) -> int:
    for value in values:
        parsed = _coerce_int(value)
        if parsed is not None:
            return parsed
    return default


def _coerce_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except Exception:
        return None
    return parsed if parsed >= 0 else None


def _drop_empty(value: dict[str, Any]) -> dict[str, Any]:
    return {
        key: item
        for key, item in value.items()
        if item not in (None, "", (), [], {})
    }


__all__ = [
    "VISIBILITY_LEDGER_SCHEMA_VERSION",
    "VISIBILITY_STATUS_VALUES",
    "_projection_diagnostics",
    "_section_block_family",
    "_section_inclusion_reason",
    "_section_prompt_block_profile",
    "_tool_result_visibility_ledger",
    "_visibility_ledger",
]
