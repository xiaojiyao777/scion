"""Shared prompt rendering helpers for proposal-engine requests."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict

from scion.proposal.engine.telemetry_retry_projection import (
    schema_retry_feedback_json as _schema_retry_feedback_json,
    schema_retry_feedback_projection as _schema_retry_feedback_projection,
)


class _DefaultDict(dict):
    """dict subclass that returns '' for missing keys (safe format_map)."""

    def __missing__(self, key: str) -> str:
        return ""


_CACHE_5M = {"type": "ephemeral"}
_AGENTIC_RESEARCH_DIAGNOSIS_CHARS = 12000
_AGENTIC_ACTIVE_ALGORITHM_FACTS_CHARS = 16000
_AGENTIC_ACTIVE_SOLVER_MECHANISMS_CHARS = 4000
_AGENTIC_ACTIVE_SOLVER_MAP_RECEIPTS_CHARS = 48000
_AGENTIC_RESUME_CONTEXT_CHARS = 16000
_AGENTIC_TOOL_OBSERVATIONS_CHARS = 96000
_AGENTIC_FULL_ALGORITHM_FILE_READS_CHARS = 1_000_000
_AGENTIC_CODE_FULL_ALGORITHM_FILE_READS_CHARS = 400_000
_AGENTIC_CODE_RESEARCH_DIAGNOSIS_CHARS = 16000
_AGENTIC_CODE_TOOL_OBSERVATIONS_CHARS = 48000
_AGENTIC_CODE_PREVIEW_FEEDBACK_CHARS = 16000
_AGENTIC_CODE_SELF_CHECK_FEEDBACK_CHARS = 12000
_AGENTIC_SCHEMA_RETRY_FEEDBACK_CHARS = 12000
_PREVIEW_TOOL_NAMES = frozenset(
    {
        "proposal.schema_preview",
        "proposal.target_permission_preview",
        "proposal.contract_preview",
        "proposal.algorithm_smoke",
    }
)


def _agentic_research_context_block(
    context: Dict[str, Any],
    *,
    code_phase: bool = False,
) -> str:
    parts: list[str] = []
    semantic_rejections = context.get("agentic_hypothesis_semantic_rejections")
    if semantic_rejections:
        retry_payload = {
            "retry_attempt": context.get("agentic_hypothesis_retry_attempt"),
            "retry_rule": context.get("agentic_hypothesis_retry_rule"),
            "semantic_rejections": semantic_rejections,
        }
        parts.append(
            "## Hypothesis Semantic Retry Feedback\n"
            "The previous hypothesis was rejected by an audited semantic gate. "
            "Use this feedback as a boundary/objective constraint when marked "
            "hard. If the candidate remains near an "
            "existing mechanism, acknowledge the existing mechanism and state "
            "the material trigger, scoring, schedule, or behavior difference. "
            "If prior wording acknowledged the existing mechanism but was "
            "ambiguous, clarify that acknowledgement and the variant boundary "
            "rather than drifting the research goal.\n\n"
            f"{_bounded_json(retry_payload, 6000)}"
        )
    preview_rejections = context.get("agentic_hypothesis_preview_rejections")
    if preview_rejections:
        retry_payload = _schema_retry_feedback_projection(
            retry_attempt=context.get("agentic_hypothesis_retry_attempt"),
            retry_rule=context.get("agentic_hypothesis_preview_retry_rule"),
            preview_rejections=preview_rejections,
        )
        parts.append(
            "## Hypothesis Schema/Telemetry Retry Feedback\n"
            "The previous hypothesis was rejected by an audited schema/target "
            "preview. Use this feedback as a hard structured-output constraint: "
            "the final task is to repair the same hypothesis' schema/telemetry "
            "fields. Preserve the protected identity exactly and ignore ordinary "
            "exploration guidance that would choose a different mechanism. "
            "This is a schema/accounting repair, not a new algorithmic "
            "hypothesis; the exact allowed telemetry template in this section "
            "is authoritative.\n\n"
            f"{_schema_retry_feedback_json(retry_payload)}"
        )
    grounding_rejections = context.get("agentic_hypothesis_grounding_rejections")
    if grounding_rejections:
        retry_payload = {
            "retry_attempt": context.get("agentic_hypothesis_retry_attempt"),
            "retry_rule": context.get("agentic_hypothesis_grounding_retry_rule"),
            "grounding_rejections": grounding_rejections,
        }
        parts.append(
            "## Hypothesis Target-File Grounding Retry Feedback\n"
            "The previous solver-design hypothesis selected an existing target "
            "file before that file's full source was visible in the provider "
            "prompt. Use the newly visible target-file observation as a hard "
            "grounding requirement before redrafting.\n\n"
            f"{_bounded_json(retry_payload, 6000)}"
        )
    resume_context = _resume_context_projection(context.get("agentic_resume_context"))
    if resume_context:
        parts.append(
            "## Agentic Resume Context\n"
            "This compact handoff summarizes the previous APS attempt. Read "
            "receipts are digests, not source contents; reread files when exact "
            "code is needed. Do not infer hidden raw ledger contents from this "
            "section.\n\n"
            f"{_bounded_json(resume_context, _AGENTIC_RESUME_CONTEXT_CHARS)}"
        )
    diagnosis = _agentic_research_diagnosis_projection(
        context.get("agentic_research_diagnosis"),
        code_phase=code_phase,
    )
    if diagnosis:
        heading = (
            "## Evidence Diagnosis Behind This Hypothesis"
            if code_phase
            else "## Agentic Research Diagnosis"
        )
        parts.append(
            f"{heading}\n"
            "Screening/runtime observations below are tainted proposal context, "
            "not Decision input. Use them to explain which declared surface "
            "evidence should change and why the next mechanism differs from "
            "prior failed attempts.\n\n"
            f"{_bounded_json(diagnosis, _agentic_research_diagnosis_chars(code_phase))}"
        )
    active_algorithm_facts = context.get("agentic_active_algorithm_facts")
    if active_algorithm_facts:
        parts.append(
            "## Active Algorithm Facts\n"
            "These compact problem-adapter facts are the primary active-solver "
            "mechanism context. They are shared with deterministic semantic "
            "gates; use raw tool observations only as audit/support material.\n\n"
            f"{_bounded_json(active_algorithm_facts, _AGENTIC_ACTIVE_ALGORITHM_FACTS_CHARS)}"
        )
    active_solver_mechanisms = context.get("agentic_active_solver_mechanisms")
    if active_solver_mechanisms and not _same_fact_packet(
        active_algorithm_facts,
        active_solver_mechanisms,
    ):
        parts.append(
            "## Active Solver Mechanism Digest\n"
            "Compact mechanism evidence from the active-solver snapshot. Use it "
            "only when it adds information not already present in Active "
            "Algorithm Facts.\n\n"
            f"{_bounded_json(active_solver_mechanisms, _AGENTIC_ACTIVE_SOLVER_MECHANISMS_CHARS)}"
        )
    observations = context.get("agentic_tool_observations")
    active_solver_map_receipts = _active_solver_map_receipts_projection(observations)
    if active_solver_map_receipts:
        parts.append(
            "## Active Solver Map Receipts\n"
            "Provider-declared active-map, operator-registry, and algorithm-slice "
            "receipts. Use these ids as the preferred bridge from compact map "
            "metadata to bounded source slices. This is a bounded projection, "
            "not raw repository context.\n\n"
            f"{_bounded_json(active_solver_map_receipts, _AGENTIC_ACTIVE_SOLVER_MAP_RECEIPTS_CHARS)}"
        )
    telemetry_guidance = context.get("agentic_expected_telemetry_guidance")
    if telemetry_guidance:
        parts.append(
            "## Expected Telemetry Schema Examples\n"
            "Adapter-declared legal expected_telemetry patterns for the active "
            "research boundary. Use these examples when filling the final "
            "hypothesis; they are guidance for schema correctness, not a "
            "relaxed contract.\n\n"
            f"{_bounded_json(telemetry_guidance, 6000)}"
        )
    preview_feedback = context.get("agentic_preview_feedback")
    if preview_feedback:
        preview_payload = _preview_feedback_model_projection(
            preview_feedback,
            code_phase=code_phase,
        )
        heading = (
            "## Latest Preview Repair Feedback"
            if code_phase
            else "## Latest Preview Feedback"
        )
        parts.append(
            f"{heading}\n"
            "This is the structured failing preview that triggered the retry. "
            "Treat actionable_telemetry_feedback as executable repair input: "
            "preserve the declared mechanism id, use the expected call pattern "
            "when repairing code, and report a telemetry declaration mismatch "
            "instead of fabricating effect evidence; do not fabricate effect "
            "evidence.\n\n"
            f"{_bounded_json(preview_payload, _preview_feedback_chars(code_phase))}"
        )
    code_shape_feedback = context.get("agentic_code_schema_shape_retry_feedback")
    if code_phase and code_shape_feedback:
        parts.append(
            "## Code Output Shape Retry Feedback\n"
            "The previous code response failed structured output shape checks. "
            "This is a schema-only repair: preserve the approved target, "
            "mechanism ids, and patch intent exactly; only fix the JSON shape "
            "called out below.\n\n"
            f"{_bounded_json(code_shape_feedback, 3000)}"
        )
    code_edit_feedback = context.get("agentic_code_edit_retry_feedback")
    if code_phase and code_edit_feedback:
        parts.append(
            "## Typed Edit Retry Feedback\n"
            "The previous typed edit failed host-side validation. Preserve the "
            "approved hypothesis and patch intent, then repair only the edit "
            "selector details below. Use candidate snippets to construct a "
            "unique old_string; set replace_all only for a deliberate global "
            "replacement.\n\n"
            f"{_bounded_json(code_edit_feedback, 6000)}"
        )
    code_self_check_feedback = context.get("agentic_code_self_check_feedback")
    if code_phase and code_self_check_feedback:
        parts.append(
            "## Code Self-Check Retry Feedback\n"
            "The previous patch failed deterministic code-stage validation. "
            "Repair only the current_blocker described below. When "
            "offending_telemetry_usages is present, treat each listed "
            "file_path/json_pointer/line_text as the concrete generated call "
            "to edit: use an approved protected mechanism id for new mechanism "
            "evidence, or remove that newly added telemetry call. Baseline or "
            "structural telemetry ids may remain only when unchanged.\n\n"
            f"{_bounded_json(code_self_check_feedback, _AGENTIC_CODE_SELF_CHECK_FEEDBACK_CHARS)}"
        )
    if observations:
        full_algorithm_reads = _solver_design_full_algorithm_file_reads(observations)
        full_algorithm_read_ids = {
            str(item.get("observation_id") or "")
            for item in full_algorithm_reads
            if str(item.get("observation_id") or "")
        }
        if full_algorithm_reads:
            full_read_projection = {
                "projection_kind": "solver_design_full_algorithm_file_reads.v1",
                "source_section": "agentic_tool_observations",
                "prompt_contract": (
                    "Successful full context.read_algorithm_file observations "
                    "for active solver_design files are projected here before "
                    "the generic tool-observation section so section-level "
                    "compaction cannot hide source that a hypothesis must use."
                ),
                "reads": full_algorithm_reads,
            }
            parts.append(
                "## Solver-Design Full Algorithm File Reads\n"
                "These successful full `context.read_algorithm_file` observations "
                "are API-visible source content for active solver-design files. "
                "A read receipt or digest elsewhere is not a substitute for this "
                "section when grounding a solver_design hypothesis.\n\n"
                f"{_bounded_json(full_read_projection, _full_algorithm_read_chars(code_phase))}"
            )
        observations = _dedupe_tool_observations(
            observations,
            active_algorithm_facts=active_algorithm_facts,
            resume_context=resume_context,
            full_read_observation_ids=full_algorithm_read_ids,
        )
        observations = _tool_observations_model_projection(
            observations,
            code_phase=code_phase,
        )
        parts.append(
            "## Agentic Proposal Tool Observations\n"
            "These are exposure-controlled tool observations gathered before "
            "generation. This section is a bounded semantic projection, not a "
            "raw append-only transcript; full algorithm file reads, active "
            "facts, and preview repair details are projected into dedicated "
            "sections above. Use the receipts and digests to decide what to "
            "reread through tools when exact detail is needed.\n\n"
            f"{_bounded_json(observations, _agentic_observation_chars(code_phase))}"
        )
    return "\n\n".join(parts)


def _format_bulleted_section(title: str, lines: list[str]) -> str:
    return f"## {title}\n{_format_bullets(lines)}"


def _format_bullets(lines: list[str]) -> str:
    return "".join(f"- {line}\n" for line in lines)


def _limit_code_phase_text(text: str, max_chars: int, *, label: str) -> str:
    if not text or len(text) <= max_chars:
        return text
    suffix = f"\n... <truncated {label} for compact code generation>"
    return text[: max(0, max_chars - len(suffix))] + suffix


def _agentic_research_diagnosis_chars(code_phase: bool) -> int:
    return (
        _AGENTIC_CODE_RESEARCH_DIAGNOSIS_CHARS
        if code_phase
        else _AGENTIC_RESEARCH_DIAGNOSIS_CHARS
    )


def _agentic_observation_chars(code_phase: bool) -> int:
    return (
        _AGENTIC_CODE_TOOL_OBSERVATIONS_CHARS
        if code_phase
        else _AGENTIC_TOOL_OBSERVATIONS_CHARS
    )


def _full_algorithm_read_chars(code_phase: bool) -> int:
    return (
        _AGENTIC_CODE_FULL_ALGORITHM_FILE_READS_CHARS
        if code_phase
        else _AGENTIC_FULL_ALGORITHM_FILE_READS_CHARS
    )


def _preview_feedback_chars(code_phase: bool) -> int:
    return (
        _AGENTIC_CODE_PREVIEW_FEEDBACK_CHARS
        if code_phase
        else _AGENTIC_TOOL_OBSERVATIONS_CHARS
    )


def _bounded_json(value: Any, max_chars: int) -> str:
    try:
        rendered = json.dumps(value, indent=2, sort_keys=True, default=str)
    except TypeError:
        rendered = str(value)
    if len(rendered) <= max_chars:
        return rendered
    return rendered[: max(0, max_chars - 80)] + "\n... <truncated agentic context>"


def _preview_feedback_model_projection(value: Any, *, code_phase: bool) -> Any:
    if not code_phase or not isinstance(value, dict):
        return value
    structured = value.get("structured_payload")
    payload = structured if isinstance(structured, dict) else value
    return _drop_empty(
        {
            "projection_kind": "latest_preview_repair_feedback.v1",
            "observation_id": value.get("observation_id"),
            "tool_name": value.get("tool_name"),
            "summary": _limit_text(str(value.get("summary") or ""), 900),
            "failure_code": value.get("failure_code")
            or (payload.get("failure_code") if isinstance(payload, dict) else None),
            "repair_hint": _limit_text(str(value.get("repair_hint") or ""), 900),
            "preserved_retry_diagnostics": _preview_retry_diagnostics(payload),
            "structured_payload": _compact_preview_feedback_payload(payload),
            "projection_note": (
                "Large raw preview artifacts are compacted, but root cause, "
                "gate/check ids, failing paths, and previous patch summaries "
                "are preserved for retry repair."
            ),
        }
    )


def _preview_retry_diagnostics(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    found: dict[str, Any] = {}

    def remember(key: str, item: Any) -> None:
        if item in (None, "", [], (), {}):
            return
        found.setdefault(key, _compact_preview_critical_value(item))

    def visit(item: Any, path: tuple[str, ...] = ()) -> None:
        if isinstance(item, dict):
            lowered_path = ".".join(part.lower() for part in path)
            failed = item.get("passed") is False or bool(
                item.get("failed") or item.get("failure_code")
            )
            if failed:
                failed_checks = found.setdefault("failed_checks", [])
                if isinstance(failed_checks, list) and len(failed_checks) < 12:
                    failed_checks.append(_preview_failed_item_summary(item, path))
            for key, child in item.items():
                normalized = str(key).lower()
                child_path = path + (normalized,)
                if normalized in {
                    "root_cause",
                    "root_cause_summary",
                    "primary_issue",
                    "issue_summary",
                    "current_blocker",
                }:
                    remember("root_cause", child)
                elif normalized in {
                    "gate_id",
                    "gate",
                    "check_id",
                    "check_name",
                    "name",
                } and (
                    failed
                    or "failure" in lowered_path
                    or "preview" in lowered_path
                    or "check" in lowered_path
                ):
                    remember("gate_or_check_id", child)
                elif normalized == "failure_code" and (
                    failed
                    or "failure" in lowered_path
                    or "preview" in lowered_path
                    or "check" in lowered_path
                ):
                    remember("failure_code", child)
                elif normalized in {
                    "failing_paths",
                    "failed_paths",
                    "paths",
                    "file_path",
                    "target_file",
                    "path",
                } and (
                    failed
                    or "failure" in lowered_path
                    or "missing" in lowered_path
                    or "path" in normalized
                ):
                    remember("failing_paths", child)
                elif normalized in {
                    "previous_patch_summary",
                    "patch_summary",
                    "previous_patch",
                    "patch",
                }:
                    remember(
                        "previous_patch_summary",
                        _compact_preview_previous_patch_summary(child),
                    )
                visit(child, child_path)
        elif isinstance(item, list):
            for child in item[:24]:
                visit(child, path)

    visit(value)
    if "failed_checks" in found:
        found["failed_checks"] = [
            item for item in found["failed_checks"] if item not in ({}, None)
        ][:12]
    return _drop_empty(found)


def _preview_failed_item_summary(
    item: dict[str, Any],
    path: tuple[str, ...],
) -> dict[str, Any]:
    return _drop_empty(
        {
            "path": ".".join(path),
            "name": item.get("name") or item.get("check_id") or item.get("gate_id"),
            "failure_code": item.get("failure_code") or item.get("code"),
            "root_cause": _limit_text(
                str(
                    item.get("root_cause")
                    or item.get("issue_summary")
                    or item.get("detail")
                    or item.get("reason")
                    or ""
                ),
                700,
            ),
            "failing_paths": _compact_preview_critical_value(
                item.get("failing_paths")
                or item.get("failed_paths")
                or item.get("paths")
                or item.get("file_path")
            ),
        }
    )


def _compact_preview_feedback_payload(value: Any) -> Any:
    if not isinstance(value, dict):
        return _compact_preview_critical_value(value)
    keep = {
        "passed",
        "failure_code",
        "failure_class",
        "primary_issue",
        "issue_summary",
        "root_cause",
        "root_cause_summary",
        "current_blocker",
        "error_category",
        "gate_id",
        "gate",
        "check_id",
        "check_name",
        "failed_checks",
        "checks",
        "failing_paths",
        "failed_paths",
        "paths",
        "file_path",
        "target_file",
        "actionable_telemetry_feedback",
        "activation_diagnostic",
        "telemetry_diagnostics",
        "runtime_failure",
        "previous_patch_summary",
        "patch_summary",
        "previous_patch",
        "allowed_top_level_categories",
        "exact_allowed_top_level_categories",
        "declared_mechanism_ids",
        "protected_mechanism_ids",
        "template_mechanism_ids",
        "legal_mechanism_id_policy",
        "allowed_expected_telemetry_template",
    }
    compact: dict[str, Any] = {}
    for key, item in value.items():
        key_text = str(key)
        if key_text not in keep:
            continue
        if key_text == "allowed_expected_telemetry_template":
            compact[key_text] = item
            continue
        if key_text == "checks" and isinstance(item, list):
            compact[key_text] = [
                _compact_preview_critical_value(check)
                for check in item
                if isinstance(check, dict) and check.get("passed") is False
            ][:16]
            continue
        if key_text in {
            "previous_patch",
            "patch",
            "previous_patch_summary",
            "patch_summary",
        }:
            compact[key_text] = _compact_preview_previous_patch_summary(item)
            continue
        compact[key_text] = _compact_preview_critical_value(item)
    return _drop_empty(compact)


def _compact_preview_critical_value(value: Any) -> Any:
    if isinstance(value, dict):
        compact: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= 24:
                compact["_truncated_items"] = len(value) - 24
                break
            key_text = str(key)
            if key_text in {
                "code_content",
                "content_after",
                "raw_stdout",
                "raw_stderr",
            }:
                compact[f"{key_text}_chars"] = len(str(item))
                compact[f"{key_text}_digest"] = _stable_short_digest(item)
                continue
            compact[key_text] = _compact_preview_critical_value(item)
        return _drop_empty(compact)
    if isinstance(value, tuple):
        value = list(value)
    if isinstance(value, list):
        items = [_compact_preview_critical_value(item) for item in value[:24]]
        if len(value) > 24:
            items.append({"_truncated_items": len(value) - 24})
        return items
    if isinstance(value, str):
        return _limit_text(value, 1600)
    return value


def _compact_preview_previous_patch_summary(value: Any) -> Any:
    if not isinstance(value, dict):
        return _compact_preview_critical_value(value)
    compact: dict[str, Any] = {}
    for key, item in value.items():
        key_text = str(key)
        if key_text in {"code_content", "content_after", "old_string", "new_string"}:
            compact[f"{key_text}_chars"] = len(str(item))
            compact[f"{key_text}_digest"] = _stable_short_digest(item)
            compact[f"{key_text}_snippet"] = _limit_text(str(item), 260)
            continue
        if key_text == "additional_changes" and isinstance(item, list):
            compact[key_text] = [
                _compact_preview_previous_patch_summary(change)
                for change in item[:6]
                if isinstance(change, dict)
            ]
            continue
        compact[key_text] = _compact_preview_critical_value(item)
    return _drop_empty(compact)


def _agentic_research_diagnosis_projection(
    value: Any,
    *,
    code_phase: bool,
) -> Any:
    if not isinstance(value, dict):
        return value
    projection = value.get("model_facing_projection")
    if isinstance(projection, dict):
        return projection
    latest = value.get("latest_runtime_diagnosis")
    aggregate = value.get("aggregate_runtime_diagnosis")
    compact_latest = (
        _compact_runtime_diagnosis(latest, row_limit=8)
        if isinstance(latest, dict)
        else latest
    )
    compact_aggregate = (
        _compact_runtime_diagnosis(aggregate, row_limit=12)
        if isinstance(aggregate, dict)
        else aggregate
    )
    compact = _drop_empty(
        {
            "projection_kind": "agentic_research_diagnosis_projection.v1",
            "source_schema_version": value.get("schema_version"),
            "code_phase": code_phase,
            "runtime_diagnosis_count": value.get("runtime_diagnosis_count"),
            "runtime_diagnoses_with_signal": value.get(
                "runtime_diagnoses_with_signal"
            ),
            "latest_runtime_diagnosis": compact_latest,
            "aggregate_runtime_diagnosis": compact_aggregate,
            "notes": _bounded_list(value.get("notes"), 12),
            "repair_guidance": _bounded_list(value.get("repair_guidance"), 12),
            "audit_digest": _stable_short_digest(value),
            "projection_note": (
                "Raw diagnosis rows are audit material. This projection keeps "
                "latest/aggregate signals and bounded examples so long-running "
                "campaigns do not accumulate unbounded prompt history."
            ),
        }
    )
    return compact


def _compact_runtime_diagnosis(value: dict[str, Any], *, row_limit: int) -> dict[str, Any]:
    return _drop_empty(
        {
            "schema_version": value.get("schema_version"),
            "screening_step_count": value.get("screening_step_count"),
            "reason_code_counts": value.get("reason_code_counts"),
            "surface_counts": value.get("surface_counts"),
            "gate_outcome_counts": value.get("gate_outcome_counts"),
            "failure_mode_tags": _bounded_list(value.get("failure_mode_tags"), 16),
            "runtime_signal_rows": _bounded_list(
                value.get("runtime_signal_rows"),
                row_limit,
            ),
            "telemetry_failure_tags": _bounded_list(
                value.get("telemetry_failure_tags"),
                16,
            ),
            "branch_states": value.get("branch_states"),
            "audit_digest": _stable_short_digest(value),
        }
    )


def _limit_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - 3)] + "..."


def _resume_context_projection(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    resume = value.get("resume") if isinstance(value.get("resume"), dict) else value
    projection = resume.get("model_facing_projection")
    if isinstance(projection, dict):
        return projection
    compact = {
        "schema_version": "agentic-resume-model-projection.v1",
        "source": value.get("source") or "agentic_resume_context",
        "previous_session": _drop_empty(
            {
                "session_id": resume.get("session_id"),
                "termination_reason": resume.get("termination_reason"),
                "failure_category": resume.get("failure_category"),
                "transcript_digest": resume.get("transcript_digest"),
            }
        ),
        "active_fact_anchor": resume.get("active_fact_anchor"),
        "read_receipts": _bounded_list(resume.get("read_receipts"), 6),
        "tool_budget_used": resume.get("tool_budget_used"),
        "structured_rejection": resume.get("structured_rejection"),
    }
    return _drop_empty(compact)


def _tool_observations_model_projection(
    observations: Any,
    *,
    code_phase: bool,
) -> Any:
    if not isinstance(observations, list):
        return observations
    max_items = 40 if code_phase else 80
    compact_items = [_compact_tool_observation_for_model(item) for item in observations]
    compact_items = [item for item in compact_items if item]
    shown = compact_items[-max_items:]
    return _drop_empty(
        {
            "projection_kind": "agentic_tool_observations_projection.v1",
            "observation_count": len(compact_items),
            "shown_latest_count": len(shown),
            "omitted_older_count": max(0, len(compact_items) - len(shown)),
            "tool_counts": _tool_counts(compact_items),
            "file_read_receipts": _file_read_receipts(compact_items, limit=24),
            "preview_receipts": _preview_receipts(compact_items, limit=12),
            "observations": shown,
            "projection_note": (
                "This is a bounded model-facing projection. Exact source content "
                "for full reads appears in dedicated source sections; older raw "
                "observations remain in the audit ledger and should be queried "
                "through tools or read receipts when needed."
            ),
        }
    )


def _active_solver_map_receipts_projection(observations: Any) -> dict[str, Any]:
    if not isinstance(observations, list):
        return {}
    map_reads: list[dict[str, Any]] = []
    registry_reads: list[dict[str, Any]] = []
    slice_reads: list[dict[str, Any]] = []
    already_visible_source: list[dict[str, Any]] = []
    for item in observations:
        if not isinstance(item, dict):
            continue
        tool_name = str(item.get("tool_name") or "")
        payload = item.get("structured_payload")
        if not isinstance(payload, dict):
            continue
        if tool_name == "context.read_active_solver_map":
            registry_refs = _bounded_list(payload.get("operator_registries"), 16)
            slice_refs = _bounded_list(payload.get("algorithm_slices"), 24)
            map_reads.append(
                _drop_empty(
                    {
                        "observation_id": item.get("observation_id"),
                        "available": payload.get("available"),
                        "surface": payload.get("surface"),
                        "subject_id": payload.get("subject_id"),
                        "snapshot_digest": payload.get("snapshot_digest"),
                        "read_receipt": _compact_receipt(payload.get("read_receipt")),
                        "available_registry_ids": [
                            str(ref.get("registry_id"))
                            for ref in registry_refs
                            if isinstance(ref, dict) and ref.get("registry_id")
                        ],
                        "available_slice_ids": [
                            str(ref.get("slice_id"))
                            for ref in slice_refs
                            if isinstance(ref, dict) and ref.get("slice_id")
                        ],
                        "operator_registries": [
                            _compact_registry_ref(ref)
                            for ref in registry_refs
                            if isinstance(ref, dict)
                        ],
                        "algorithm_slices": [
                            _compact_slice_ref(ref)
                            for ref in slice_refs
                            if isinstance(ref, dict)
                        ],
                        "source_policy": _compact_source_policy(
                            payload.get("source_policy")
                        ),
                    }
                )
            )
        elif tool_name == "context.read_operator_registry":
            registry_reads.append(
                _drop_empty(
                    {
                        "observation_id": item.get("observation_id"),
                        "available": payload.get("available"),
                        "registry_id": payload.get("registry_id"),
                        "surface": payload.get("surface"),
                        "subject_id": payload.get("subject_id"),
                        "snapshot_digest": payload.get("snapshot_digest"),
                        "owner_file": payload.get("owner_file"),
                        "owner_symbol": payload.get("owner_symbol"),
                        "registry_kind": payload.get("registry_kind"),
                        "operator_count": _len_if_list(payload.get("operators")),
                        "operators": [
                            _compact_operator_ref(ref)
                            for ref in _bounded_list(payload.get("operators"), 16)
                            if isinstance(ref, dict)
                        ],
                        "integration_points": [
                            _compact_integration_point(ref)
                            for ref in _bounded_list(
                                payload.get("integration_points"),
                                8,
                            )
                            if isinstance(ref, dict)
                        ],
                        "read_receipt": _compact_receipt(payload.get("read_receipt")),
                    }
                )
            )
        elif tool_name == "context.read_algorithm_slice":
            content = str(payload.get("content") or "")
            slice_reads.append(
                _drop_empty(
                    {
                        "observation_id": item.get("observation_id"),
                        "available": payload.get("available"),
                        "slice_id": payload.get("slice_id"),
                        "surface": payload.get("surface"),
                        "subject_id": payload.get("subject_id"),
                        "snapshot_digest": payload.get("snapshot_digest"),
                        "file_path": payload.get("file_path"),
                        "symbols": payload.get("symbols"),
                        "slice_kind": payload.get("slice_kind"),
                        "line_start": payload.get("line_start"),
                        "line_end": payload.get("line_end"),
                        "token_estimate": payload.get("token_estimate"),
                        "content_digest": payload.get("content_digest"),
                        "content_preview": _limit_text(content, 2200),
                        "content_chars": len(content) if content else None,
                        "truncated": payload.get("truncated"),
                        "max_chars": payload.get("max_chars"),
                        "why_visible": _limit_text(
                            str(payload.get("why_visible") or ""),
                            500,
                        ),
                        "source_policy_receipt": _compact_receipt(
                            payload.get("source_policy_receipt")
                        ),
                        "read_receipt": _compact_receipt(payload.get("read_receipt")),
                    }
                )
            )
            already_visible_source.append(
                _drop_empty(
                    {
                        "tool_name": tool_name,
                        "slice_id": payload.get("slice_id"),
                        "file_path": payload.get("file_path"),
                        "symbols": payload.get("symbols"),
                        "line_start": payload.get("line_start"),
                        "line_end": payload.get("line_end"),
                        "content_digest": payload.get("content_digest"),
                        "visibility": "bounded_algorithm_slice",
                    }
                )
            )
        elif tool_name == "context.read_algorithm_file":
            file_path = payload.get("file_path")
            if file_path:
                already_visible_source.append(
                    _drop_empty(
                        {
                            "tool_name": tool_name,
                            "file_path": file_path,
                            "coverage": (
                                "full"
                                if payload.get("truncated") is False
                                else "truncated"
                            ),
                            "digest": payload.get("digest")
                            or payload.get("sha256"),
                            "max_chars": payload.get("max_chars"),
                        }
                    )
                )
    if not (map_reads or registry_reads or slice_reads):
        return {}
    return _drop_empty(
        {
            "projection_kind": "active_solver_map_receipts.v1",
            "map_reads": map_reads[-4:],
            "registry_reads": registry_reads[-8:],
            "slice_reads": slice_reads[-8:],
            "available_registry_ids": _unique_strings(
                registry_id
                for read in map_reads
                for registry_id in read.get("available_registry_ids", ())
            ),
            "available_slice_ids": _unique_strings(
                slice_id
                for read in map_reads
                for slice_id in read.get("available_slice_ids", ())
            ),
            "already_visible_source": already_visible_source[-16:],
            "receipt_rule": (
                "Map/registry/slice receipts identify provider-approved source "
                "handles. Exact full-file source remains separate and should be "
                "requested only when a bounded slice is insufficient."
            ),
        }
    )


def _compact_receipt(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return _drop_empty(
        {
            "tool_name": value.get("tool_name"),
            "surface": value.get("surface"),
            "subject_id": value.get("subject_id"),
            "target_id": value.get("target_id"),
            "snapshot_digest": value.get("snapshot_digest"),
            "digest": value.get("digest"),
            "content_digest": value.get("content_digest"),
            "available": value.get("available"),
            "allowed": value.get("allowed"),
            "reason": _limit_text(str(value.get("reason") or ""), 300),
            "remaining_budget": value.get("remaining_budget"),
        }
    )


def _compact_registry_ref(value: dict[str, Any]) -> dict[str, Any]:
    return _drop_empty(
        {
            "registry_id": value.get("registry_id"),
            "owner_file": value.get("owner_file"),
            "owner_symbol": value.get("owner_symbol"),
            "registry_kind": value.get("registry_kind"),
            "operator_count": _len_if_list(value.get("operators")),
        }
    )


def _compact_operator_ref(value: dict[str, Any]) -> dict[str, Any]:
    return _drop_empty(
        {
            "id": value.get("id"),
            "symbol": value.get("symbol"),
            "file_path": value.get("file_path"),
            "order": value.get("order"),
            "role": value.get("role"),
            "summary": _limit_text(str(value.get("summary") or ""), 300),
            "mechanism_tags": _bounded_list(value.get("mechanism_tags"), 6),
            "telemetry_ids": _bounded_list(value.get("telemetry_ids"), 6),
        }
    )


def _compact_integration_point(value: dict[str, Any]) -> dict[str, Any]:
    return _drop_empty(
        {
            "file_path": value.get("file_path"),
            "symbol": value.get("symbol"),
            "insert_policy": _limit_text(str(value.get("insert_policy") or ""), 300),
            "required_telemetry_pattern": _limit_text(
                str(value.get("required_telemetry_pattern") or ""),
                300,
            ),
        }
    )


def _compact_slice_ref(value: dict[str, Any]) -> dict[str, Any]:
    return _drop_empty(
        {
            "slice_id": value.get("slice_id"),
            "file_path": value.get("file_path"),
            "symbols": value.get("symbols"),
            "purpose": _limit_text(str(value.get("purpose") or ""), 360),
            "exposure_level": value.get("exposure_level"),
            "source_digest": value.get("source_digest"),
            "token_estimate": value.get("token_estimate"),
            "redaction_reason": _limit_text(
                str(value.get("redaction_reason") or ""),
                240,
            ),
        }
    )


def _compact_source_policy(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return _drop_empty(
        {
            "max_total_tokens": value.get("max_total_tokens"),
            "max_body_tokens_per_tool_call": value.get(
                "max_body_tokens_per_tool_call"
            ),
            "allowed_files_digest": value.get("allowed_files_digest"),
            "redaction_policy": value.get("redaction_policy"),
        }
    )


def _len_if_list(value: Any) -> int | None:
    if isinstance(value, (list, tuple)):
        return len(value)
    return None


def _unique_strings(values: Any) -> list[str]:
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in result:
            result.append(text)
    return result


def _compact_tool_observation_for_model(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {"value": _limit_text(str(value), 500)}
    payload = value.get("structured_payload")
    compact_payload = (
        _compact_payload_for_model(payload)
        if isinstance(payload, dict)
        else payload
    )
    return _drop_empty(
        {
            "observation_id": value.get("observation_id"),
            "tool_name": value.get("tool_name"),
            "phase": value.get("phase"),
            "proposal_phase": value.get("proposal_phase"),
            "status": value.get("status"),
            "failure_code": value.get("failure_code"),
            "summary": _limit_text(str(value.get("summary") or ""), 700),
            "repair_hint": _limit_text(str(value.get("repair_hint") or ""), 700),
            "file_path": value.get("file_path"),
            "coverage": value.get("coverage"),
            "digest": value.get("digest"),
            "truncated": value.get("truncated"),
            "structured_payload": compact_payload,
        }
    )


def _compact_payload_for_model(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("projection_kind"):
        return payload
    keys_to_keep = (
        "schema_version",
        "projection_kind",
        "tool_name",
        "surface",
        "surface_id",
        "selected_surface",
        "problem_id",
        "problem_spec_hash",
        "file_path",
        "module",
        "coverage_status",
        "max_chars",
        "size_chars",
        "truncated",
        "digest",
        "sha256",
        "passed",
        "failure_code",
        "reason",
        "summary",
        "research_diagnosis",
        "runtime_feedback",
        "screening_feedback",
        "read_receipts",
        "read_receipt",
        "available",
        "subject_id",
        "snapshot_digest",
        "registry_id",
        "slice_id",
        "owner_file",
        "owner_symbol",
        "registry_kind",
        "symbols",
        "slice_kind",
        "line_start",
        "line_end",
        "content_digest",
        "source_policy_receipt",
        "active_algorithm_facts_ref",
        "content_preview_ref",
        "content_preview_omitted_from_generic_observations",
        "dedicated_context_sections",
    )
    compact = {key: payload.get(key) for key in keys_to_keep if key in payload}
    if "research_diagnosis" in compact and isinstance(
        compact["research_diagnosis"],
        dict,
    ):
        compact["research_diagnosis"] = _agentic_research_diagnosis_projection(
            compact["research_diagnosis"],
            code_phase=False,
        )
    for key in ("runtime_feedback", "screening_feedback", "read_receipts"):
        if isinstance(compact.get(key), list):
            compact[key] = _bounded_list(compact[key], 16)
    if not compact:
        compact = {
            "payload_digest": _stable_short_digest(payload),
            "payload_keys": list(payload)[:24],
        }
    else:
        compact["payload_digest"] = _stable_short_digest(payload)
    return _drop_empty(compact)


def _tool_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        tool_name = str(item.get("tool_name") or "unknown")
        counts[tool_name] = counts.get(tool_name, 0) + 1
    return counts


def _file_read_receipts(items: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    receipts: list[dict[str, Any]] = []
    for item in items:
        tool_name = str(item.get("tool_name") or "")
        if tool_name not in {
            "context.read_algorithm_file",
            "context.list_algorithm_files",
            "context.read_surface",
            "context.read_active_solver_map",
            "context.read_operator_registry",
            "context.read_algorithm_slice",
            "context.read_active_solver_design",
            "context.read_solver_call_graph",
        }:
            continue
        receipts.append(
            _drop_empty(
                {
                    "tool_name": tool_name,
                    "file_path": item.get("file_path"),
                    "registry_id": _payload_value(item, "registry_id"),
                    "slice_id": _payload_value(item, "slice_id"),
                    "target_id": _payload_receipt_value(item, "target_id"),
                    "coverage": item.get("coverage"),
                    "digest": item.get("digest"),
                    "summary": item.get("summary"),
                }
            )
        )
    return receipts[-limit:]


def _payload_value(item: dict[str, Any], key: str) -> Any:
    payload = item.get("structured_payload")
    if isinstance(payload, dict):
        return payload.get(key)
    return None


def _payload_receipt_value(item: dict[str, Any], key: str) -> Any:
    payload = item.get("structured_payload")
    if not isinstance(payload, dict):
        return None
    receipt = payload.get("read_receipt")
    if isinstance(receipt, dict):
        return receipt.get(key)
    return None


def _preview_receipts(items: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    receipts: list[dict[str, Any]] = []
    for item in items:
        if str(item.get("tool_name") or "") not in _PREVIEW_TOOL_NAMES:
            continue
        payload = item.get("structured_payload")
        payload_dict = payload if isinstance(payload, dict) else {}
        receipts.append(
            _drop_empty(
                {
                    "tool_name": item.get("tool_name"),
                    "status": item.get("status"),
                    "failure_code": item.get("failure_code")
                    or payload_dict.get("failure_code"),
                    "passed": payload_dict.get("passed"),
                    "summary": item.get("summary"),
                    "repair_hint": item.get("repair_hint"),
                }
            )
        )
    return receipts[-limit:]


def _dedupe_tool_observations(
    observations: Any,
    *,
    active_algorithm_facts: Any,
    resume_context: Any,
    full_read_observation_ids: set[str] | None = None,
) -> Any:
    if not isinstance(observations, list):
        return observations
    active_digest = _fact_packet_digest(active_algorithm_facts)
    resume_active_digest = _fact_packet_digest(resume_context)
    full_read_observation_ids = full_read_observation_ids or set()
    compact: list[Any] = []
    for observation in observations:
        if not isinstance(observation, dict):
            compact.append(observation)
            continue
        item = dict(observation)
        payload = item.get("structured_payload")
        if isinstance(payload, dict):
            payload = _dedupe_observation_payload(
                payload,
                tool_name=str(item.get("tool_name") or ""),
                observation_summary=str(item.get("summary") or ""),
                observation_failure_code=str(item.get("failure_code") or ""),
                observation_repair_hint=str(item.get("repair_hint") or ""),
                active_digest=active_digest,
                resume_active_digest=resume_active_digest,
                has_full_algorithm_reads=bool(full_read_observation_ids),
                omit_full_algorithm_content=(
                    str(item.get("observation_id") or "")
                    in full_read_observation_ids
                ),
            )
            item["structured_payload"] = payload
        compact.append(item)
    return compact


def _dedupe_observation_payload(
    payload: dict[str, Any],
    *,
    tool_name: str,
    observation_summary: str = "",
    observation_failure_code: str = "",
    observation_repair_hint: str = "",
    active_digest: str,
    resume_active_digest: str,
    has_full_algorithm_reads: bool = False,
    omit_full_algorithm_content: bool = False,
) -> dict[str, Any]:
    compact = dict(payload)
    if omit_full_algorithm_content and "content_preview" in compact:
        content_preview_ref = _drop_empty(
            {
                "section": "solver_design_full_algorithm_file_reads",
                "file_path": compact.get("file_path"),
                "content_preview_chars": len(str(compact.get("content_preview") or "")),
                "full_content_included_in_prompt_section": True,
            }
        )
        return _drop_empty(
            {
                "active": compact.get("active"),
                "coverage_status": "full",
                "content_preview_chars": len(
                    str(compact.get("content_preview") or "")
                ),
                "content_preview_ref": content_preview_ref,
                "content_preview_omitted_from_generic_observations": True,
                "digest": compact.get("digest"),
                "file_path": compact.get("file_path"),
                "max_chars": compact.get("max_chars"),
                "module": compact.get("module"),
                "readable": compact.get("readable"),
                "role": compact.get("role"),
                "sha256": compact.get("sha256"),
                "size_chars": compact.get("size_chars"),
                "source": compact.get("source"),
                "source_digest": _canonical_full_source_digest(compact),
                "source_digest_hash": _noncanonical_source_digest_hash(compact)
                or compact.get("digest"),
                "truncated": compact.get("truncated"),
            }
        )
    if active_digest and tool_name in {
        "context.read_active_solver_design",
        "context.read_solver_call_graph",
        "context.list_algorithm_files",
    }:
        return _compact_static_solver_context_payload(
            tool_name,
            compact,
            active_digest=active_digest,
            resume_active_digest=resume_active_digest,
        )
    if tool_name == "context.list_surfaces":
        return _compact_list_surfaces_payload(compact)
    if tool_name == "context.read_problem":
        return _compact_read_problem_payload(compact)
    if (
        active_digest
        and has_full_algorithm_reads
        and tool_name == "context.read_surface"
        and _is_solver_design_surface_payload(compact)
    ):
        return _compact_surface_payload(compact, active_digest=active_digest)
    if tool_name in _PREVIEW_TOOL_NAMES:
        return _compact_preview_tool_payload(
            tool_name=tool_name,
            payload=compact,
            observation_summary=observation_summary,
            observation_failure_code=observation_failure_code,
            observation_repair_hint=observation_repair_hint,
        )
    facts = compact.get("active_algorithm_facts")
    facts_digest = _fact_packet_digest(facts)
    if facts_digest and facts_digest in {active_digest, resume_active_digest}:
        compact["active_algorithm_facts_ref"] = _drop_empty(
            {
                "fact_packet_digest": facts_digest,
                "snapshot_digest": _snapshot_digest(facts),
                "fact_ids": _fact_ids(facts),
                "omitted_from_raw_observation": (
                    "deduplicated; see Active Algorithm Facts / Resume Context"
                ),
            }
        )
        compact.pop("active_algorithm_facts", None)
    return compact


def _compact_preview_tool_payload(
    *,
    tool_name: str,
    payload: dict[str, Any],
    observation_summary: str,
    observation_failure_code: str,
    observation_repair_hint: str,
) -> dict[str, Any]:
    passed = _preview_passed(payload)
    failed_checks = _preview_failed_checks(payload)
    failure_reason = _preview_failure_reason(payload)
    compact = {
        "projection_kind": "preview_tool_receipt.v1",
        "tool_payload_omitted_from_generic_observations": True,
        "tool_name": tool_name,
        "passed": passed,
        "failure_code": observation_failure_code or payload.get("failure_code"),
        "summary": _limit_text(observation_summary, 360),
        "failure_reason": _limit_text(failure_reason, 700),
        "failed_checks": failed_checks[:10],
        "repair_templates": _preview_repair_templates(payload),
        "repair_hint": _limit_text(
            observation_repair_hint or str(payload.get("repair_hint") or ""),
            700,
        ),
        "payload_digest": _stable_short_digest(payload),
        "payload_sections_present": [
            str(key)
            for key in payload
            if key not in {"hypothesis_object", "patch_object"}
        ][:16],
        "requested": _compact_preview_requested(payload),
        "permission": _compact_preview_permission(payload),
        "workspace_materialized": payload.get("workspace_materialized"),
        "static_only": payload.get("static_only"),
        "dedicated_feedback_section": _preview_feedback_section(tool_name),
        "audit_ref": (
            "Full preview payload is omitted from the agent-facing observation; "
            "use the raw observation ledger/session artifact for audit detail."
        ),
    }
    return _drop_empty(compact)


def _compact_list_surfaces_payload(payload: dict[str, Any]) -> dict[str, Any]:
    surfaces = payload.get("surfaces")
    compact_surfaces: list[dict[str, Any]] = []
    if isinstance(surfaces, list):
        for surface in surfaces[:16]:
            if not isinstance(surface, dict):
                continue
            targets = surface.get("targets") if isinstance(surface.get("targets"), dict) else {}
            compact_surfaces.append(
                _drop_empty(
                    {
                        "name": surface.get("name"),
                        "kind": surface.get("kind"),
                        "target_files": surface.get("target_files")
                        or targets.get("files"),
                        "allowed_actions": targets.get("allowed_actions"),
                    }
                )
            )
    return _drop_empty(
        {
            "projection_kind": "surface_list_receipt.v1",
            "tool_payload_omitted_from_generic_observations": True,
            "surface_count": payload.get("surface_count")
            or len(compact_surfaces),
            "total_declared_surface_count": payload.get(
                "total_declared_surface_count"
            ),
            "surfaces": compact_surfaces,
            "forced_surface_constraint": payload.get("forced_surface_constraint"),
            "active_problem_boundary_constraint": payload.get(
                "active_problem_boundary_constraint"
            ),
            "payload_digest": _stable_short_digest(payload),
        }
    )


def _compact_read_problem_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return _drop_empty(
        {
            "projection_kind": "problem_context_receipt.v1",
            "tool_payload_omitted_from_generic_observations": True,
            "problem_id": payload.get("problem_id"),
            "problem_spec_hash": payload.get("problem_spec_hash"),
            "summary": _limit_text(str(payload.get("summary") or ""), 700),
            "problem_object_chars": len(str(payload.get("problem_object") or "")),
            "solver_mechanics_chars": len(str(payload.get("solver_mechanics") or "")),
            "problem_object_omitted_from_generic_observations": bool(
                payload.get("problem_object")
            ),
            "solver_mechanics_omitted_from_generic_observations": bool(
                payload.get("solver_mechanics")
            ),
            "dedicated_context_sections": [
                "problem_summary",
                "problem_object",
                "research_surfaces",
            ],
            "payload_digest": _stable_short_digest(payload),
        }
    )


def _compact_surface_payload(
    payload: dict[str, Any],
    *,
    active_digest: str,
) -> dict[str, Any]:
    surface = payload.get("surface")
    surface_payload = surface if isinstance(surface, dict) else {}
    current_artifact = _artifact_receipt(payload.get("current_artifact"))
    support_artifacts = [
        artifact
        for artifact in (
            _artifact_receipt(item)
            for item in _bounded_list(payload.get("support_artifacts"), 64)
        )
        if artifact
    ]
    readable_support_count = sum(
        1 for artifact in support_artifacts if artifact.get("readable") is True
    )
    unreadable_support_count = sum(
        1 for artifact in support_artifacts if artifact.get("readable") is False
    )
    compact: dict[str, Any] = {
        "projection_kind": "surface_interface_receipt.v1",
        "tool_payload_omitted_from_generic_observations": True,
        "dedicated_context_sections": [
            "active_algorithm_facts",
            "solver_design_full_algorithm_file_reads",
        ],
        "surface": _drop_empty(
            {
                "id": surface_payload.get("id") or payload.get("surface_id"),
                "name": surface_payload.get("name") or payload.get("name"),
                "kind": surface_payload.get("kind") or payload.get("kind"),
                "section": surface_payload.get("section") or payload.get("section"),
                "selected": surface_payload.get("selected") or payload.get("selected"),
                "active": surface_payload.get("active") or payload.get("active"),
            }
        ),
        "target_file": payload.get("target_file")
        or current_artifact.get("file_path"),
        "declared_targets": payload.get("declared_targets"),
        "surface_digest": _stable_short_digest(
            _drop_empty(
                {
                    "surface": _surface_identity(payload),
                    "surface_contract": payload.get("surface_contract"),
                    "declared_targets": payload.get("declared_targets"),
                    "target_file": payload.get("target_file"),
                }
            )
        ),
        "provenance": payload.get("provenance"),
        "active_algorithm_facts_ref": {
            "fact_packet_digest": active_digest,
            "omitted_from_raw_observation": (
                "deduplicated; see Active Algorithm Facts and full algorithm "
                "file read sections"
            ),
        },
        "current_artifact": _drop_empty(
            {
                "file_path": current_artifact.get("file_path"),
                "readable": current_artifact.get("readable"),
                "source": current_artifact.get("source"),
            }
        ),
        "support_artifact_count": len(support_artifacts),
        "support_artifact_paths": [
            artifact["file_path"]
            for artifact in support_artifacts
            if artifact.get("file_path")
        ],
        "support_artifact_readable_count": readable_support_count,
        "support_artifact_unreadable_count": unreadable_support_count,
        "source_pointer": (
            "Full solver-design source and active facts are projected in "
            "dedicated cacheable prompt sections; artifact previews and API "
            "summaries are omitted from generic tool observations."
        ),
    }
    contract = payload.get("surface_contract")
    if isinstance(contract, dict):
        compact["surface_contract"] = _drop_empty(
            {
                "schema_version": contract.get("schema_version"),
                "detail": contract.get("detail"),
                "section": contract.get("section"),
                "available_sections": contract.get("available_sections"),
                "target_preview": _target_preview_receipt(
                    contract.get("target_preview")
                ),
            }
        )
    return _drop_empty(compact)


def _artifact_receipt(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {
        key: item
        for key, item in {
            "file_path": value.get("file_path") or value.get("path"),
            "readable": value.get("readable"),
            "source": value.get("source"),
            "read_receipt": "content/API summary omitted; see dedicated source sections",
        }.items()
        if item not in (None, "", (), [], {})
    }


def _target_preview_receipt(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {
        key: item
        for key, item in {
            "file_path": value.get("file_path"),
            "readable": value.get("readable"),
            "read_receipt": "target preview omitted; see dedicated source sections",
        }.items()
        if item not in (None, "", (), [], {})
    }


def _preview_feedback_section(tool_name: str) -> str:
    if tool_name == "proposal.schema_preview":
        return "hypothesis_schema_telemetry_retry_feedback"
    if tool_name in {"proposal.contract_preview", "proposal.algorithm_smoke"}:
        return "latest_preview_repair_feedback"
    if tool_name == "proposal.target_permission_preview":
        return "hypothesis_schema_telemetry_retry_feedback"
    return ""


def _preview_passed(payload: Any) -> bool | None:
    if isinstance(payload, dict) and "passed" in payload:
        return bool(payload.get("passed"))
    return None


def _preview_failed_checks(value: Any) -> list[str]:
    failed: list[str] = []

    def visit(item: Any) -> None:
        if len(failed) >= 20:
            return
        if isinstance(item, dict):
            name = item.get("name")
            if name and item.get("passed") is False:
                failed.append(str(name))
            contract = item.get("contract")
            if isinstance(contract, dict):
                raw_failed = contract.get("failed_checks")
                if isinstance(raw_failed, list):
                    failed.extend(str(check) for check in raw_failed[:20])
            for child in item.values():
                visit(child)
        elif isinstance(item, list):
            for child in item[:40]:
                visit(child)

    visit(value)
    return list(dict.fromkeys(item for item in failed if item))[:20]


def _preview_repair_templates(value: Any) -> list[dict[str, Any]]:
    templates: list[dict[str, Any]] = []

    def visit(item: Any) -> None:
        if len(templates) >= 4:
            return
        if isinstance(item, dict):
            raw_templates = item.get("repair_templates")
            if isinstance(raw_templates, list):
                for template in raw_templates:
                    if isinstance(template, dict):
                        templates.append(_compact_preview_repair_template(template))
                        if len(templates) >= 4:
                            return
            raw_template = item.get("repair_template")
            if isinstance(raw_template, dict):
                templates.append(_compact_preview_repair_template(raw_template))
                if len(templates) >= 4:
                    return
            for child in item.values():
                visit(child)
        elif isinstance(item, list):
            for child in item[:40]:
                visit(child)

    visit(value)
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for template in templates:
        key = json.dumps(template, sort_keys=True, default=str)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(template)
    return deduped[:4]


def _compact_preview_repair_template(template: dict[str, Any]) -> dict[str, Any]:
    return _drop_empty(
        {
            "repair_type": template.get("repair_type"),
            "check": template.get("check"),
            "severity": template.get("severity"),
            "missing_fields": template.get("missing_fields"),
            "observed": template.get("observed"),
            "required_template": template.get("required_template"),
            "recommended_shape": template.get("recommended_shape"),
            "agent_instruction": template.get("agent_instruction"),
        }
    )


def _preview_failure_reason(value: Any) -> str:
    reasons: list[str] = []

    def add(text: Any) -> None:
        reason = str(text or "").strip()
        if reason and reason not in reasons:
            reasons.append(reason)

    def visit(item: Any) -> None:
        if len(reasons) >= 8:
            return
        if isinstance(item, dict):
            for key in ("failure_reason", "issue_summary", "repair_hint"):
                value_for_key = item.get(key)
                add(value_for_key)
            errors = item.get("errors")
            if isinstance(errors, list):
                for error in errors[:4]:
                    if isinstance(error, dict):
                        add(error.get("msg") or error.get("message") or error)
                    else:
                        add(error)
            issues = item.get("issues")
            if isinstance(issues, list):
                for issue in issues[:4]:
                    add(issue)
            for child in item.values():
                visit(child)
        elif isinstance(item, list):
            for child in item[:20]:
                visit(child)

    visit(value)
    return "; ".join(reasons[:6])


def _compact_preview_requested(payload: dict[str, Any]) -> dict[str, Any]:
    requested = payload.get("requested")
    if isinstance(requested, dict):
        return _drop_empty(
            {
                "change_locus": requested.get("change_locus"),
                "action": requested.get("action"),
                "target_file": requested.get("target_file"),
            }
        )
    hypothesis = payload.get("hypothesis")
    if isinstance(hypothesis, dict):
        summary = hypothesis.get("hypothesis")
        if isinstance(summary, dict):
            return _drop_empty(
                {
                    "change_locus": summary.get("change_locus"),
                    "action": summary.get("action"),
                    "target_file": summary.get("target_file"),
                    "mechanism_changes": summary.get("mechanism_changes"),
                }
            )
    patch = payload.get("patch")
    if isinstance(patch, dict):
        summary = patch.get("patch")
        if isinstance(summary, dict):
            return _drop_empty(
                {
                    "file_path": summary.get("file_path"),
                    "action": summary.get("action"),
                }
            )
    return {}


def _compact_preview_permission(payload: dict[str, Any]) -> dict[str, Any]:
    permission = payload.get("permission")
    if not isinstance(permission, dict):
        return {}
    return _drop_empty(
        {
            "surface_known": permission.get("surface_known"),
            "action_allowed": permission.get("action_allowed"),
            "target_required": permission.get("target_required"),
            "target_path_safe": permission.get("target_path_safe"),
            "target_declared": permission.get("target_declared"),
        }
    )


def _compact_static_solver_context_payload(
    tool_name: str,
    payload: dict[str, Any],
    *,
    active_digest: str,
    resume_active_digest: str,
) -> dict[str, Any]:
    facts = payload.get("active_algorithm_facts")
    facts_digest = _fact_packet_digest(facts)
    source_digest = _compact_source_digest(payload.get("source_digest"))
    compact: dict[str, Any] = {
        "projection_kind": "static_solver_context_receipt.v1",
        "tool_payload_omitted_from_generic_observations": True,
        "dedicated_context_sections": [
            section
            for section in (
                "active_algorithm_facts" if active_digest else "",
                "solver_design_full_algorithm_file_reads",
            )
            if section
        ],
        "surface": payload.get("surface"),
        "source": payload.get("source"),
        "snapshot_digest": _snapshot_digest(payload),
        "source_digest": source_digest,
    }
    if facts_digest:
        compact["active_algorithm_facts_ref"] = _drop_empty(
            {
                "fact_packet_digest": facts_digest,
                "snapshot_digest": _snapshot_digest(facts),
                "fact_ids": _fact_ids(facts),
                "omitted_from_raw_observation": (
                    "deduplicated; see Active Algorithm Facts / Resume Context"
                    if facts_digest in {active_digest, resume_active_digest}
                    else "deduplicated; see static solver context sections"
                ),
            }
        )
    if tool_name == "context.list_algorithm_files":
        paths = _algorithm_file_paths(payload.get("files"))
        compact.update(
            {
                "file_count": len(paths),
                "file_paths": paths,
            }
        )
    elif tool_name == "context.read_solver_call_graph":
        edges = payload.get("edges")
        nodes = payload.get("nodes")
        compact.update(
            {
                "edge_count": len(edges) if isinstance(edges, list) else None,
                "node_count": len(nodes) if isinstance(nodes, list) else None,
                "call_graph_ref": "deduplicated; see Active Algorithm Facts / solver execution model",
            }
        )
    elif tool_name == "context.read_active_solver_design":
        paths = _algorithm_file_paths(payload.get("files"))
        if not paths and isinstance(payload.get("source_digest"), dict):
            files = payload["source_digest"].get("files")
            if isinstance(files, dict):
                paths = [str(path) for path in files if str(path).strip()]
        compact.update(
            {
                "entrypoint": payload.get("entrypoint"),
                "file_count": len(paths),
                "file_paths": paths[:16],
                "active_solver_snapshot_ref": "deduplicated; see Active Algorithm Facts and full algorithm file reads",
            }
        )
    return _drop_empty(compact)


def _is_solver_design_surface_payload(payload: dict[str, Any]) -> bool:
    identity = _surface_identity(payload)
    return any(value == "solver_design" for value in identity.values())


def _surface_identity(payload: dict[str, Any]) -> dict[str, str]:
    raw_surface = payload.get("surface")
    surface = raw_surface if isinstance(raw_surface, dict) else {}
    candidates = {
        "id": surface.get("id") or payload.get("surface_id"),
        "name": surface.get("name") or payload.get("name"),
        "kind": surface.get("kind") or payload.get("kind"),
    }
    if isinstance(raw_surface, str):
        candidates["surface"] = raw_surface
    summary = payload.get("interface_summary")
    if isinstance(summary, str) and "Declared Research Surface: solver_design" in summary:
        candidates["interface_summary_surface"] = "solver_design"
    return {
        key: str(value).strip()
        for key, value in candidates.items()
        if str(value or "").strip()
    }


def _algorithm_file_paths(value: Any) -> list[str]:
    if isinstance(value, dict):
        return [str(path) for path in value if str(path).strip()]
    if not isinstance(value, list):
        return []
    paths: list[str] = []
    for item in value:
        if isinstance(item, dict):
            path = str(item.get("file_path") or item.get("path") or "").strip()
        else:
            path = str(item or "").strip()
        if path:
            paths.append(path)
    return list(dict.fromkeys(paths))


def _compact_source_digest(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    files = value.get("files")
    file_count = len(files) if isinstance(files, dict) else None
    return _drop_empty(
        {
            "algorithm": value.get("algorithm"),
            "snapshot_digest": value.get("snapshot_digest"),
            "file_count": file_count,
            "digest": _stable_short_digest(value),
        }
    )


def _stable_short_digest(value: Any) -> str:
    try:
        rendered = json.dumps(value, sort_keys=True, default=str)
    except TypeError:
        rendered = str(value)
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()[:16]


def _solver_design_full_algorithm_file_reads(observations: Any) -> list[dict[str, Any]]:
    if not isinstance(observations, list):
        return []
    reads: list[dict[str, Any]] = []
    for observation in observations:
        if not isinstance(observation, dict):
            continue
        if observation.get("tool_name") != "context.read_algorithm_file":
            continue
        if bool(observation.get("is_error")):
            continue
        payload = observation.get("structured_payload")
        if not isinstance(payload, dict):
            continue
        if not _is_full_algorithm_file_payload(payload):
            continue
        reads.append(
            _drop_empty(
                {
                    "observation_id": observation.get("observation_id"),
                    "tool_name": observation.get("tool_name"),
                    "observation_digest": observation.get("digest"),
                    "file_path": payload.get("file_path"),
                    "active": payload.get("active"),
                    "role": payload.get("role"),
                    "module": payload.get("module"),
                    "readable": payload.get("readable"),
                    "source": payload.get("source"),
                    "source_digest": _canonical_full_source_digest(payload),
                    "source_digest_hash": _noncanonical_source_digest_hash(payload)
                    or payload.get("digest"),
                    "sha256": payload.get("sha256"),
                    "truncated": payload.get("truncated"),
                    "size_chars": payload.get("size_chars"),
                    "max_chars": payload.get("max_chars"),
                    "content_preview": payload.get("content_preview"),
                }
            )
        )
    return reads


def _canonical_full_source_digest(payload: dict[str, Any]) -> str:
    for key in ("source_digest", "sha256"):
        value = payload.get(key)
        if _looks_like_sha256(value):
            return str(value)
    content = payload.get("content_preview")
    if isinstance(content, str) and content and _is_full_algorithm_file_payload(payload):
        return hashlib.sha256(content.encode("utf-8")).hexdigest()
    return ""


def _noncanonical_source_digest_hash(payload: dict[str, Any]) -> Any:
    value = payload.get("source_digest_hash") or payload.get("source_digest")
    if _looks_like_sha256(value):
        return ""
    return value


def _looks_like_sha256(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    return all(ch in "0123456789abcdefABCDEF" for ch in value)


def _is_full_algorithm_file_payload(payload: dict[str, Any]) -> bool:
    if payload.get("readable") is not True:
        return False
    if payload.get("already_observed"):
        return False
    if payload.get("active") is False:
        return False
    content_preview = payload.get("content_preview")
    if content_preview is None:
        return False
    if bool(payload.get("truncated")):
        return False
    preview_chars = len(str(content_preview))
    size_chars = _coerce_nonnegative_int(payload.get("size_chars"))
    max_chars = _coerce_nonnegative_int(payload.get("max_chars"))
    if size_chars is not None and max_chars is not None and max_chars >= size_chars:
        return True
    if size_chars is not None:
        return preview_chars >= size_chars
    if max_chars is not None:
        return preview_chars >= max_chars
    return True


def _coerce_nonnegative_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except Exception:
        return None
    return parsed if parsed >= 0 else None


def _same_fact_packet(left: Any, right: Any) -> bool:
    left_digest = _fact_packet_digest(left)
    return bool(left_digest and left_digest == _fact_packet_digest(right))


def _fact_packet_digest(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    direct = value.get("fact_packet_digest")
    if direct:
        return str(direct)
    for key in (
        "active_algorithm_facts",
        "active_fact_anchor",
        "active_fact_digest",
    ):
        child = value.get(key)
        if isinstance(child, dict):
            digest = _fact_packet_digest(child)
            if digest:
                return digest
    return ""


def _snapshot_digest(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    direct = value.get("snapshot_digest")
    if direct:
        return str(direct)
    child = value.get("active_algorithm_facts")
    if isinstance(child, dict):
        return _snapshot_digest(child)
    return ""


def _fact_ids(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return []
    raw = value.get("fact_ids")
    if isinstance(raw, (list, tuple)):
        return [str(item) for item in raw[:20] if str(item)]
    child = value.get("active_algorithm_facts")
    if isinstance(child, dict):
        return _fact_ids(child)
    return []


def _bounded_list(value: Any, limit: int) -> list[Any]:
    if not isinstance(value, (list, tuple)):
        return []
    return list(value[: max(0, limit)])


def _drop_empty(value: dict[str, Any]) -> dict[str, Any]:
    return {
        key: item
        for key, item in value.items()
        if item not in (None, "", (), [], {})
    }
