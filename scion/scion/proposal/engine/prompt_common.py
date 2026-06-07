"""Shared prompt rendering helpers for proposal-engine requests."""

from __future__ import annotations

import json
from typing import Any, Dict, Mapping

from scion.proposal.engine.prompt.formatting import (
    _DefaultDict,
    _bounded_json,
    _bounded_list,
    _drop_empty,
    _format_bulleted_section,
    _format_bullets,
    _limit_code_phase_text,
    _limit_text,
    _stable_short_digest,
)
from scion.proposal.engine.prompt.observations import (
    _active_solver_map_receipts_projection,
    _dedupe_tool_observations,
    _same_fact_packet,
    _solver_design_full_algorithm_file_reads,
    _tool_observations_model_projection as _tool_observations_model_projection_base,
)
from scion.proposal.engine.telemetry_retry_projection import (
    schema_retry_feedback_json as _schema_retry_feedback_json,
    schema_retry_feedback_projection as _schema_retry_feedback_projection,
)


_CACHE_5M = {"type": "ephemeral"}
_AGENTIC_RESEARCH_DIAGNOSIS_CHARS = 12000
_AGENTIC_ACTIVE_ALGORITHM_FACTS_CHARS = 16000
_AGENTIC_ACTIVE_SOLVER_MECHANISMS_CHARS = 4000
_AGENTIC_ACTIVE_SOLVER_MAP_RECEIPTS_CHARS = 48000
_AGENTIC_RESUME_CONTEXT_CHARS = 16000
_AGENTIC_MATERIAL_DIFFERENCE_REQUIREMENT_CHARS = 6000
_AGENTIC_TOOL_OBSERVATIONS_CHARS = 96000
_AGENTIC_FULL_ALGORITHM_FILE_READS_CHARS = 1_000_000
_AGENTIC_CODE_FULL_ALGORITHM_FILE_READS_CHARS = 400_000
_AGENTIC_CODE_RESEARCH_DIAGNOSIS_CHARS = 16000
_AGENTIC_CODE_TOOL_OBSERVATIONS_CHARS = 48000
_AGENTIC_CODE_PREVIEW_FEEDBACK_CHARS = 16000
_AGENTIC_CODE_SELF_CHECK_FEEDBACK_CHARS = 12000
_AGENTIC_SCHEMA_RETRY_FEEDBACK_CHARS = 12000

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
    target_intent = context.get("agentic_hypothesis_target_intent")
    if target_intent:
        parts.append(
            "## Hypothesis Target-Intent Preflight\n"
            "This tainted preflight summary is not a formal hypothesis and not "
            "a Decision input. It is binding for this formal hypothesis call: "
            "target_file, action, change_locus, and mechanism family or "
            "mechanism continuation must stay consistent with the selected "
            "intent because the host exposed owner source or a create-new "
            "placeholder for that intent. Do not switch owners or mechanisms "
            "inside the formal hypothesis. A different target requires a "
            "host-controlled target-intent reselect flow before formal "
            "hypothesis generation. Treat later schema, semantic, or grounding "
            "retry feedback as authoritative only when it keeps or explicitly "
            "repairs that same selected intent. Use `intent.mechanism_id` as "
            "the formal schema-safe id when present. Any "
            "`raw_mechanism_id` or provenance field is audit-only and must not "
            "be copied into formal `mechanism_changes` or telemetry refs.\n\n"
            f"{_bounded_json(target_intent, 4000)}"
        )
    target_placeholder = context.get("agentic_hypothesis_target_placeholder")
    if target_placeholder:
        parts.append(
            "## Hypothesis Target Placeholder\n"
            "The selected target is a create-new intent, so no existing owner "
            "source is required. Use this visible placeholder plus active "
            "solver facts, map receipts, and declared surface context as "
            "integration context for the final hypothesis.\n\n"
            f"{_bounded_json(target_placeholder, 3000)}"
        )
    material_requirement = _material_difference_requirement_projection(context)
    if material_requirement:
        rendered_material_requirement = _bounded_json(
            material_requirement,
            _AGENTIC_MATERIAL_DIFFERENCE_REQUIREMENT_CHARS,
        )
        parts.append(
            "## Material Difference Requirement\n"
            "Scheduler audit metadata requires the next hypothesis to make a "
            "first-class material_difference claim before code generation. "
            "This is proposal-visible governance context only, not a Decision "
            "input. Use it to select or draft a hypothesis that is materially "
            "different from the listed nearby branch candidates. The final "
            "hypothesis must fill `material_difference` with compact generic "
            "structural anchors such as `changed_dimensions`, "
            "`signature_digest`, or `evidence_status_delta`; "
            "generic phrases such as 'different approach', 'new mechanism', "
            "or repeated hypothesis prose do not satisfy this requirement. "
            "Descriptive-only fields such as `differs_from` or `effect_path` "
            "are not enough unless accompanied by one of the structural "
            "anchor fields.\n\n"
            f"{rendered_material_requirement}"
        )
    contract_preview_signature = context.get("contract_preview_failure_signature")
    if isinstance(contract_preview_signature, Mapping) and contract_preview_signature:
        parts.append(
            "## Contract Preview Failure Signature\n"
            "This branch-local contract-preview signature is hard negative "
            "proposal feedback only. It is excluded from DecisionFeatures. "
            "Do not repeat the same target/check/mechanism write pattern. "
            "For target-intent or hypothesis generation, reselect the target, "
            "mechanism, or implementation path unless the next attempt is an "
            "explicit repair of this signature. For code generation, repair "
            "the implementation so the forbidden pattern is absent; if the "
            "approved target cannot avoid the same boundary failure, report "
            "`wrong_owner` instead of emitting the same pattern.\n\n"
            f"{_bounded_json(contract_preview_signature, 6000)}"
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


def _tool_observations_model_projection(
    observations: Any,
    *,
    code_phase: bool,
) -> Any:
    return _tool_observations_model_projection_base(
        observations,
        code_phase=code_phase,
        research_diagnosis_projection=_agentic_research_diagnosis_projection,
    )


def _material_difference_requirement_projection(
    context: Mapping[str, Any],
) -> dict[str, Any]:
    value = context.get("material_difference_requirement")
    if not isinstance(value, Mapping):
        return {}
    if value.get("required") is False:
        return {}
    if not (
        value.get("required") is True
        or str(value.get("record_id") or "").strip()
        or str(value.get("required_for") or "").strip()
    ):
        return {}
    return _drop_empty(
        {
            "schema_version": "proposal_material_difference_requirement.v1",
            "required": True,
            "record_id": value.get("record_id"),
            "record_digest": value.get("record_digest"),
            "record_type": value.get("record_type"),
            "requirement_source": value.get("requirement_source"),
            "reason": value.get("reason"),
            "reason_codes": _bounded_string_list(value.get("reason_codes"), 12),
            "required_for": value.get("required_for"),
            "required_metadata_key": value.get("required_metadata_key"),
            "candidate_count": value.get("candidate_count"),
            "candidate_branch_ids": _bounded_string_list(
                value.get("candidate_branch_ids"),
                16,
            ),
            "candidate_release_reasons": _bounded_string_list(
                value.get("candidate_release_reasons"),
                16,
            ),
            "candidate_summaries": _bounded_candidate_summaries(
                value.get("candidate_summaries")
            ),
            "required_output_field": "material_difference",
            "required_output_contract": value.get("required_output_contract"),
            "proposal_visibility_only": True,
            "proposal_guidance_only": True,
            "audit_only": True,
            "decision_features_excluded": True,
        }
    )


def _bounded_candidate_summaries(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, (list, tuple)):
        return []
    summaries: list[dict[str, Any]] = []
    for item in list(value)[:8]:
        if not isinstance(item, Mapping):
            continue
        summaries.append(
            _drop_empty(
                {
                    "branch_id": item.get("branch_id"),
                    "release_reason": item.get("release_reason"),
                    "scheduler_preference": item.get("scheduler_preference"),
                    "lineage_status": item.get("lineage_status"),
                    "branch_state": item.get("branch_state"),
                    "branch_code_status": item.get("branch_code_status"),
                    "screening_tier": item.get("screening_tier"),
                    "candidate_source": item.get("candidate_source"),
                }
            )
        )
    return [item for item in summaries if item]


def _bounded_string_list(value: Any, limit: int) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    return [str(item).strip() for item in list(value)[:limit] if str(item).strip()]


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
