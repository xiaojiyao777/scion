"""Code-generation prompt rendering for the proposal engine."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict

from scion.proposal.edit_protocol import build_patch_edit_source_manifest

from .prompt_common import (
    _CACHE_5M,
    _DefaultDict,
    _agentic_research_context_block,
    _bounded_json,
    _limit_code_phase_text,
)
from .solver_design_prompts import (
    _SOLVER_DESIGN_CODE_API_MANIFEST_CHARS,
    _SOLVER_DESIGN_CODE_INTEGRATION_FILES_CHARS,
    _SOLVER_DESIGN_CODE_INTERFACE_CHARS,
    _SOLVER_DESIGN_CODE_PROBLEM_OBJECT_CHARS,
    _SOLVER_DESIGN_CODE_SOLVER_MECHANICS_CHARS,
    _SOLVER_DESIGN_COMPACT_RETRY_API_MANIFEST_CHARS,
    _SOLVER_DESIGN_COMPACT_RETRY_INTEGRATION_FILES_CHARS,
    _SOLVER_DESIGN_COMPACT_RETRY_INTERFACE_CHARS,
    _SOLVER_DESIGN_COMPACT_RETRY_PROBLEM_OBJECT_CHARS,
    _SOLVER_DESIGN_COMPACT_RETRY_SOLVER_MECHANICS_CHARS,
    _code_hypothesis_detail,
    _solver_design_code_rules_section,
    _solver_design_scope_control_section,
    _solver_design_user_constraints,
)


def _split_code_context(
    context: Dict[str, Any],
) -> "tuple[list[dict], str]":
    """Split code context into system blocks (cacheable) and user prompt.

    System: Block 1 (static role + rules + interface) + Block 2 (champion code)
    User (dynamic): hypothesis + target file + constraints
    """
    D = _DefaultDict(context)
    solver_mechanics = str(D["solver_mechanics"]).strip()
    problem_object = str(D["problem_object"]).strip()
    surface_name = str(D["research_surface_name"] or D["change_locus"]).strip()
    surface_kind = str(D["research_surface_kind"] or "operator").strip()
    is_solver_design_surface = surface_kind in {
        "solver_design",
        "solver_algorithm",
    } or surface_name in {"solver_design", "solver_algorithm"}
    compact_timeout_retry = (
        str(D["code_generation_mode"]).strip() == "compact_timeout_retry"
    )
    if is_solver_design_surface:
        problem_object = _limit_code_phase_text(
            problem_object,
            (
                _SOLVER_DESIGN_COMPACT_RETRY_PROBLEM_OBJECT_CHARS
                if compact_timeout_retry
                else _SOLVER_DESIGN_CODE_PROBLEM_OBJECT_CHARS
            ),
            label="problem object",
        )
        solver_mechanics = _limit_code_phase_text(
            solver_mechanics,
            (
                _SOLVER_DESIGN_COMPACT_RETRY_SOLVER_MECHANICS_CHARS
                if compact_timeout_retry
                else _SOLVER_DESIGN_CODE_SOLVER_MECHANICS_CHARS
            ),
            label="solver execution model",
        )
        interface_spec = _limit_code_phase_text(
            str(D["operator_interface_spec"]),
            (
                _SOLVER_DESIGN_COMPACT_RETRY_INTERFACE_CHARS
                if compact_timeout_retry
                else _SOLVER_DESIGN_CODE_INTERFACE_CHARS
            ),
            label="surface interface",
        )
        solver_design_api_manifest = _limit_code_phase_text(
            str(D["solver_design_api_manifest"]).strip(),
            (
                _SOLVER_DESIGN_COMPACT_RETRY_API_MANIFEST_CHARS
                if compact_timeout_retry
                else _SOLVER_DESIGN_CODE_API_MANIFEST_CHARS
            ),
            label="solver-design API manifest",
        )
        solver_design_integration_files = _limit_code_phase_text(
            str(D["solver_design_branch_current_integration_files"]).strip(),
            (
                _SOLVER_DESIGN_COMPACT_RETRY_INTEGRATION_FILES_CHARS
                if compact_timeout_retry
                else _SOLVER_DESIGN_CODE_INTEGRATION_FILES_CHARS
            ),
            label="solver-design branch-current integration files",
        )
    else:
        interface_spec = str(D["operator_interface_spec"])
        solver_design_api_manifest = ""
        solver_design_integration_files = ""
    problem_object_section = (
        f"## Problem Object\n{problem_object}\n\n" if problem_object else ""
    )
    solver_mechanics_section = (
        f"## Solver Execution Model\n{solver_mechanics}\n\n" if solver_mechanics else ""
    )
    active_subject_code_constraints_section = (
        _active_subject_code_constraints_section(
            D["active_subject_code_constraints"]
        )
    )
    solver_design_api_manifest_section = (
        f"## Solver-Design Module API Manifest\n{solver_design_api_manifest}\n\n"
        if solver_design_api_manifest
        else ""
    )
    solver_design_integration_files_section = (
        "## Branch-Current Integration Files\n"
        "These files are not the approved target unless their path matches "
        "`target_file`. Use them as current-content provenance for "
        "`additional_changes`; preserve their existing contracts and make only "
        "the smallest necessary wiring edits.\n"
        f"{solver_design_integration_files}\n\n"
        if solver_design_integration_files
        else ""
    )

    surface_label = (
        f"{surface_name} [{surface_kind}]" if surface_name else f"[{surface_kind}]"
    )
    solver_design_code_rules = _solver_design_code_rules_section(
        D,
        is_solver_design_surface=is_solver_design_surface,
    )
    solver_design_scope_control = _solver_design_scope_control_section(
        D,
        is_solver_design_surface=is_solver_design_surface,
    )
    solver_design_user_constraints = _solver_design_user_constraints(
        D,
        is_solver_design_surface=is_solver_design_surface,
    )

    static_text = (
        "You are a software engineer implementing a declared research surface for a combinatorial optimisation solver framework.\n"
        "Your task is to submit typed edits that implement the approved hypothesis below.\n\n"
        "## Code Quality Rules\n"
        "- Write ONLY what the hypothesis requires. For non-solver surfaces, do not add extra helper functions or abstractions.\n"
        "- Do not add error handling for impossible cases. Trust the data model.\n"
        "- Do not add comments explaining WHAT the code does — only WHY for non-obvious choices.\n"
        "- Prefer simple, direct code over clever abstractions.\n"
        "- Match the coding style of the existing champion research-surface files.\n"
        "- Do NOT add logging, print statements, or debug output.\n"
        f"{solver_design_code_rules}"
        f"{solver_design_scope_control}\n"
        "## Feasibility is Non-Negotiable\n"
        "An operator surface that produces infeasible solutions is worse than no change. "
        "Follow the problem-specific feasibility and consistency rules in the interface specification exactly.\n\n"
        f"## Problem Summary\n{D['problem_summary']}\n\n"
        f"{problem_object_section}"
        f"{solver_mechanics_section}"
        f"{active_subject_code_constraints_section}"
        f"## Research Surface Interface Specification\n"
        f"Active surface: {surface_label}\n"
        f"Follow this interface exactly:\n\n"
        f"{interface_spec}\n\n"
        f"## Allowed Imports\n"
        f"Only use modules from this whitelist — any other import will be rejected:\n"
        f"{D['import_whitelist']}"
    )

    if is_solver_design_surface:
        champion_text = (
            "## Current Champion Research Code\n"
            "The approved solver-design target file is provided as current "
            "source in the `Target File` section below so typed edits can cite "
            "exact source text and digests. Legacy component policies may be "
            "implementation context, but they are not the research object for "
            "this patch; follow the problem object, interface specification, "
            "and target file instead of copying lifecycle/config tables."
        )
    else:
        champion_text = (
            f"## Current Champion Research Code\n"
            f"Study these files for coding style, data model usage, and patterns:\n\n"
            f"{D['champion_operators_code']}"
        )

    stable_system_parts = [static_text, champion_text]

    prior_failure_section = ""
    if D["prior_code_failure"]:
        prior_failure_section = _prior_failure_prompt_section(
            str(D["prior_code_failure"])
        )
    if D["branch_hygiene_guidance"]:
        prior_failure_section += (
            f"## Branch Code Status\n{D['branch_hygiene_guidance']}\n\n"
        )
    prior_quality_section = _code_prior_quality_feedback_section(D)
    if prior_quality_section:
        prior_failure_section += prior_quality_section
    previous_patch_section = _previous_patch_prompt_section(
        D["previous_patch"],
        current_feedback=D["agentic_code_self_check_feedback"],
    )
    telemetry_identity_retry_section = _telemetry_identity_retry_blocker_section(
        D["agentic_code_self_check_feedback"]
    )
    telemetry_identity_section = _telemetry_identity_guidance_section(D)
    agentic_context = _agentic_research_context_block(D, code_phase=True)
    cacheable_agentic_context = ""
    dynamic_agentic_context = ""
    if agentic_context:
        cacheable_agentic_context, dynamic_agentic_context = (
            _split_agentic_context_for_code_cache(agentic_context)
        )
        if dynamic_agentic_context:
            prior_failure_section += f"{dynamic_agentic_context}\n\n"
    edit_source_manifest = build_patch_edit_source_manifest(context)
    required_full_integration_files = str(
        D["agentic_required_full_integration_files"]
    ).strip()
    required_full_integration_section = (
        "## Required Full Integration Edit Sources\n"
        "The previous patch attempted to edit these integration files before "
        "their full current source was visible in the API prompt. Treat this "
        "section as the current source of truth for any `additional_changes` "
        "against these paths.\n"
        f"{required_full_integration_files}\n\n"
        if required_full_integration_files
        else ""
    )

    source_context_section = ""
    if is_solver_design_surface:
        source_context_parts = []
        if cacheable_agentic_context:
            source_context_parts.append(cacheable_agentic_context)
        source_context_parts.append(
            "## Code Source Visibility Ledger\n"
            "The stable source sections in this cacheable block are the "
            "provider-visible source of truth for typed edits. Dynamic retry "
            "feedback and previous patches are intentionally outside this "
            "cacheable block."
        )
        if solver_design_api_manifest_section:
            source_context_parts.append(solver_design_api_manifest_section.strip())
        if str(D["target_file_code"]).strip():
            source_context_parts.append(
                f"## Approved Target File Current Content\n{D['target_file_code']}"
            )
        if edit_source_manifest:
            source_context_parts.append(
                f"## Patch Edit Source Digests\n{edit_source_manifest}"
            )
        if solver_design_integration_files_section:
            source_context_parts.append(solver_design_integration_files_section.strip())
        source_context_section = "\n\n".join(
            part for part in source_context_parts if str(part).strip()
        )
    if source_context_section:
        stable_system_parts.append(source_context_section)
    system_blocks = [
        {
            "type": "text",
            "text": "\n\n".join(
                part for part in stable_system_parts if str(part).strip()
            ),
            "cache_control": _CACHE_5M,
        }
    ]
    dynamic_solver_design_api_manifest_section = (
        "" if is_solver_design_surface else solver_design_api_manifest_section
    )
    dynamic_target_file_section = (
        ""
        if is_solver_design_surface
        else f"## Approved Target File Current Content\n{D['target_file_code']}\n\n"
    )
    dynamic_edit_source_section = (
        ""
        if is_solver_design_surface
        else f"## Patch Edit Source Digests\n{edit_source_manifest}\n\n"
    )
    dynamic_integration_files_section = (
        "" if is_solver_design_surface else solver_design_integration_files_section
    )

    user_prompt = (
        f"{prior_failure_section}"
        f"{previous_patch_section}"
        f"{telemetry_identity_retry_section}"
        f"## Hypothesis to Implement\n{_code_implementation_brief(D)}\n\n"
        f"## Hypothesis Detail Audit\n{_code_hypothesis_detail(D, is_solver_design_surface)}\n\n"
        f"{required_full_integration_section}"
        f"{dynamic_solver_design_api_manifest_section}"
        f"{dynamic_target_file_section}"
        f"{dynamic_edit_source_section}"
        f"{dynamic_integration_files_section}"
        f"## Reference Surface Files\n{D['reference_operators']}\n\n"
        f"{telemetry_identity_section}"
        f"## Constraints\n"
        f"- Editable files: {D['editable_patterns']}\n"
        f"- Frozen (DO NOT MODIFY): {D['frozen_patterns']}\n"
        f"- Top-level `file_path` must be exactly the approved target_file: "
        f"{D['target_file']}\n"
        f"- First set `premise_check` to one of: supported, contradicted, duplicate, wrong_owner.\n"
        f"- Use `supported` for implementable algorithm changes, including risky or uncertain research changes.\n"
        f"- `duplicate` and mechanism/premise `contradicted` observations are diagnostic only: continue with the patch when the approved hypothesis is a material variant and explain the overlap or concern in `premise_check_reason`.\n"
        f"- Do not use `contradicted` as a no-patch exit for novelty, duplicate-risk, near-existing mechanism, baseline-already-has-similar-capability observations, uncertain algorithm benefit, or telemetry expectation mismatch.\n"
        f"- Only `wrong_owner` and explicit hard boundary/objective-policy/protected-constraint contradictions may leave patch fields empty.\n"
        f"- Conform to the active research-surface interface specification exactly\n"
        f"- Preserve all feasibility, consistency, and determinism invariants described there\n"
        f"- For operator surfaces, use the provided `rng` argument for all randomness and return the new solution/artifact, or the original if no valid move is found\n"
        f"- For policy surfaces, implement the required module-level functions and keep return values inside the documented bounds\n\n"
        f"- For existing `action: modify` files, default to "
        f"`edit_intent: exact_replace`. Use the exact `source_digest` shown "
        f"above plus exact `old_string`, `new_string`, and `replace_all`. "
        f"Prefer function-level or small block replacements; avoid using one "
        f"huge `exact_replace` as a near-full-file modify. Host preflight "
        f"rejects exact_replace selectors that cover nearly the whole file "
        f"(hard limit 85% of files over 2000 chars); aim to keep each "
        f"`old_string` under 35% of the file and scoped to a function, import "
        f"block, registry entry, or local code block.\n"
        f"- For `exact_replace`, `old_string` must be a non-empty string and "
        f"`new_string` must be present as a string. To delete text, set "
        f"`new_string` to `\"\"`; do not omit it or set it to null.\n"
        f"- Existing files must never be changed through `action: create`, "
        f"`create_new`, or `full_file`. Existing file requires "
        f"`action: modify` with `edit_intent: exact_replace` and "
        f"`source_digest`; create is only for new files.\n"
        f"- Use `edit_intent: full_file` with `content_after` only for "
        f"creates or deletes. Host-visible existing-file modifies that emit "
        f"`full_file`/`content_after` are rejected by default; "
        f"`full_file_reason` is not an authorization or replace policy. "
        f"Legacy `code_content` full-file output is rejected for model-facing "
        f"existing-file modifies.\n"
        f"- If you add a new module and must wire an existing integration file, "
        f"the new module may use `action: create` with full content, but each "
        f"existing integration file in `additional_changes` must use "
        f"`action: modify` with typed `exact_replace`.\n"
        f"- Do not use `full_file` just because the current target source is "
        f"shown in the prompt.\n"
        f"- When one file needs multiple small edits, prefer one file change or "
        f"serializable `exact_replace` edits for that same `file_path`; each "
        f"later `old_string` must match the content after earlier same-file "
        f"edits. Do not emit no-op `exact_replace` entries such as "
        f"`old_string == new_string` or EOF/trailing newline edits. Do not "
        f"emit conflicting `full_file` entries for one file.\n"
        f"- Do not emit unified diffs. Scion derives the audit diff from host "
        f"before/after content after validating the typed edit.\n"
        f"{solver_design_user_constraints}\n"
        f"Respond with a single JSON object (no markdown fences, no extra text):\n"
        f"{{\n"
        f'  "premise_check": "supported" | "contradicted" | "duplicate" | "wrong_owner",\n'
        f'  "premise_check_reason": "<brief reason when not supported, otherwise empty>",\n'
        f'  "file_path": "<relative path, e.g. operators/my_operator.py>",\n'
        f'  "action": "modify" | "create" | "delete",\n'
        f'  "edit_intent": "exact_replace" | "full_file",\n'
        f'  "source_digest": "<sha256 digest for existing files, or null for create>",\n'
        f'  "old_string": "<exact current text for exact_replace>",\n'
        f'  "new_string": "<replacement text for exact_replace>",\n'
        f'  "replace_all": false,\n'
        f'  "content_after": "<complete file contents only for full_file>",\n'
        f'  "full_file_reason": "<required when edit_intent is full_file, otherwise empty>",\n'
        f'  "evidence_refs": ["<observation/source ref>"],\n'
        f'  "additional_changes": [{{"file_path": "<relative path>", '
        f'"action": "modify" | "create" | "delete", '
        f'"edit_intent": "exact_replace" | "full_file", '
        f'"source_digest": "<sha256 digest or null>", '
        f'"old_string": "<exact current text>", '
        f'"new_string": "<replacement text>", '
        f'"replace_all": false, '
        f'"content_after": "<complete file contents only for full_file>", '
        f'"full_file_reason": "<required when edit_intent is full_file>", '
        f'"evidence_refs": ["<observation/source ref>"]}}],\n'
        f'  "test_hint": "<optional note, or null>"\n'
        f"}}\n"
    )

    return system_blocks, user_prompt


def _code_prior_quality_feedback_section(context: Dict[str, Any]) -> str:
    prior_quality_blocks = context.get("agentic_prior_quality_blocks")
    if not prior_quality_blocks:
        return ""
    payload: dict[str, Any] = {
        "rule": str(context.get("agentic_prior_quality_block_rule") or "").strip(),
        "prior_quality_blocks": prior_quality_blocks,
    }
    negative_fact_block = str(context.get("agentic_negative_fact_block") or "").strip()
    if negative_fact_block:
        payload["negative_fact_block"] = negative_fact_block
    rendered = json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        default=str,
        indent=2,
    )
    return (
        "## Prior Agent Quality Blocks For This Code Patch\n"
        "These are branch-local proposal quality blocks from attempts that "
        "failed before protocol. They are tainted proposal context and are not "
        "Decision input, but they are hard repair constraints for this code "
        "generation call. Do not emit a near-same patch until the cited "
        "failure_code, gate, retry_constraint, repair_template, or missing "
        "code element is repaired in code.\n"
        f"{rendered}\n\n"
    )


def _telemetry_identity_guidance_section(context: Dict[str, Any]) -> str:
    mechanism_ids = _approved_mechanism_ids(context)
    if not mechanism_ids:
        return ""
    taxonomy = context.get("active_subject_taxonomy")
    allowlist: list[str] = []
    if isinstance(taxonomy, dict):
        allowlist = sorted(_string_set(taxonomy.get("telemetry_identity_allowlist")))
    allowlist_text = ", ".join(f"`{item}`" for item in allowlist) or "none declared"
    mechanism_text = ", ".join(f"`{item}`" for item in mechanism_ids)
    return (
        "## Telemetry Identity Rules\n"
        f"- Approved/protected mechanism id(s) for this code patch: {mechanism_text}.\n"
        "- Any new or increased mechanism telemetry must use only those exact "
        "approved/protected mechanism id(s). This applies to runtime telemetry "
        "helpers such as `record_phase`, `record_iteration`, `record_move`, and "
        "equivalent selected-surface telemetry helpers.\n"
        "- Do not create, rename, copy, or increase telemetry under undeclared "
        "mechanism ids. Do not use a broad phase, baseline, structural, or "
        "aggregate id as mechanism evidence for this hypothesis.\n"
        "- Baseline, structural, or aggregate phase telemetry may remain only "
        "when it is unchanged from the visible source, or when the adapter "
        "telemetry identity allowlist explicitly permits that id. Adapter "
        f"allowlist for such non-mechanism phase ids: {allowlist_text}.\n"
        "- Allowed baseline/structural/aggregate phase telemetry is diagnostic "
        "or accounting context only; it is not activation/effect evidence for "
        "the approved mechanism id(s).\n\n"
    )


def _telemetry_identity_retry_blocker_section(feedback: Any) -> str:
    policy = _telemetry_identity_preservation_policy(feedback)
    if not policy["protected_id_only"] or not isinstance(feedback, dict):
        return ""
    approved = sorted(policy["protected_ids"])
    offending = sorted(policy["offending_ids"])
    approved_text = ", ".join(f"`{item}`" for item in approved) or "none"
    offending_text = ", ".join(f"`{item}`" for item in offending) or "none"
    usage_lines = _compact_offending_telemetry_usage_lines(feedback)
    usage_section = (
        "Offending generated telemetry usages to edit:\n"
        + "\n".join(f"- {line}" for line in usage_lines)
        + "\n"
        if usage_lines
        else ""
    )
    return (
        "## Telemetry Identity Repair Blocker\n"
        f"Approved/protected mechanism id(s): {approved_text}.\n"
        f"Offending unapproved telemetry id(s): {offending_text}.\n"
        "Hard repair rules:\n"
        "- Do not add or increase telemetry for baseline, structural, "
        "aggregate, or unapproved mechanism ids.\n"
        "- Do not copy existing baseline telemetry as new evidence for this "
        "patch.\n"
        "- Use an approved/protected mechanism id only when the edited code "
        "path genuinely implements that mechanism.\n"
        "- Otherwise remove the newly added or increased telemetry call.\n"
        f"{usage_section}\n"
    )


def _compact_offending_telemetry_usage_lines(feedback: Dict[str, Any]) -> list[str]:
    usages = feedback.get("compact_offending_telemetry_usages")
    if not isinstance(usages, list) or not usages:
        usages = feedback.get("offending_telemetry_usages")
    if not isinstance(usages, list):
        return []
    lines: list[str] = []
    for usage in usages[:8]:
        if not isinstance(usage, dict):
            continue
        file_path = str(usage.get("file") or usage.get("file_path") or "").strip()
        line_no = str(usage.get("line") or "?").strip()
        helper = str(usage.get("helper") or "").strip()
        mechanism_id = str(usage.get("mechanism_id") or "").strip()
        line_text = _snippet_text(
            str(usage.get("line_text") or ""),
            max_chars=180,
        )
        parts = [
            f"file={file_path}" if file_path else "",
            f"line={line_no}" if line_no else "",
            f"helper={helper}" if helper else "",
            f"mechanism_id={mechanism_id}" if mechanism_id else "",
            f"line_text={line_text}" if line_text else "",
        ]
        rendered = "; ".join(part for part in parts if part)
        if rendered:
            lines.append(rendered)
    return lines


def _approved_mechanism_ids(context: Dict[str, Any]) -> list[str]:
    ids: list[str] = []
    for source in (
        context.get("mechanism_changes"),
        (
            context.get("hypothesis_implementation_brief", {})
            if isinstance(context.get("hypothesis_implementation_brief"), dict)
            else {}
        ).get("mechanism_changes"),
    ):
        if not isinstance(source, (list, tuple)):
            continue
        for change in source:
            if not isinstance(change, dict):
                continue
            mechanism_id = str(change.get("id") or "").strip()
            if mechanism_id and mechanism_id not in ids:
                ids.append(mechanism_id)
    for mechanism_id in sorted(_string_set(context.get("protected_mechanism_ids"))):
        if mechanism_id not in ids:
            ids.append(mechanism_id)
    return ids


def _code_implementation_brief(context: Dict[str, Any]) -> str:
    brief = context.get("hypothesis_implementation_brief")
    if isinstance(brief, dict):
        payload = _compact_implementation_brief(brief)
    else:
        payload = _compact_implementation_brief(
            {
                "action": context.get("action"),
                "target_file": context.get("target_file"),
                "hypothesis_text": context.get("hypothesis_text"),
                "expected_telemetry": context.get("expected_telemetry"),
                "mechanism_changes": context.get("mechanism_changes"),
                "target_runtime_effect": context.get("target_runtime_effect"),
                "no_op_condition": context.get("no_op_condition"),
                "risk_to_higher_priority": context.get("risk_to_higher_priority"),
            }
        )
    return (
        "Use this short structured implementation brief as the complete "
        "source of truth for target_file, mechanism ids, telemetry, risk, and "
        "no-op behavior. The detail-audit section below is explanatory only.\n"
        f"{_bounded_json(payload, 12000)}"
    )


_AGENTIC_CONTEXT_HEADING_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_CACHEABLE_CODE_AGENTIC_CONTEXT_HEADINGS = frozenset(
    {
        "active algorithm facts",
        "active solver mechanism digest",
        "solver-design full algorithm file reads",
    }
)


def _split_agentic_context_for_code_cache(text: str) -> tuple[str, str]:
    """Split stable active-source context from dynamic code retry context."""
    text = str(text or "")
    if not text.strip():
        return "", ""
    matches = list(_AGENTIC_CONTEXT_HEADING_RE.finditer(text))
    if not matches:
        return "", text
    cacheable: list[str] = []
    dynamic: list[str] = []
    if matches[0].start() > 0 and text[: matches[0].start()].strip():
        dynamic.append(text[: matches[0].start()].strip())
    for offset, match in enumerate(matches):
        start = match.start()
        end = matches[offset + 1].start() if offset + 1 < len(matches) else len(text)
        section = text[start:end].strip()
        heading = re.sub(r"\s+", " ", match.group(1).strip().lower())
        if heading in _CACHEABLE_CODE_AGENTIC_CONTEXT_HEADINGS:
            cacheable.append(section)
        else:
            dynamic.append(section)
    return "\n\n".join(cacheable), "\n\n".join(dynamic)


def _compact_implementation_brief(value: Dict[str, Any]) -> Dict[str, Any]:
    mechanism_changes = value.get("mechanism_changes")
    if not isinstance(mechanism_changes, (list, tuple)):
        mechanism_changes = []
    mechanisms = []
    for change in mechanism_changes:
        if isinstance(change, dict):
            mechanisms.append(
                {
                    key: change.get(key)
                    for key in ("id", "change_type", "name", "action", "target", "module")
                    if change.get(key) not in (None, "", [], {}, ())
                }
            )
    return {
        key: item
        for key, item in {
            "hypothesis_text": value.get("hypothesis_text"),
            "change_locus": value.get("change_locus"),
            "action": value.get("action"),
            "target_file": value.get("target_file"),
            "mechanism_changes": mechanisms,
            "expected_telemetry": value.get("expected_telemetry"),
            "target_objectives": value.get("target_objectives"),
            "protected_objectives": value.get("protected_objectives"),
            "target_runtime_effect": value.get("target_runtime_effect"),
            "no_op_condition": value.get("no_op_condition"),
            "risk_to_higher_priority": value.get("risk_to_higher_priority"),
            "typed_edit_requirement": (
                "Modify existing files with exact_replace typed edits; do not "
                "emit full-file content for existing-file modifications."
            ),
        }.items()
        if item not in (None, "", [], {}, ())
    }


def _active_subject_code_constraints_section(value: Any) -> str:
    if value in (None, "", {}, [], ()):
        return ""
    payload = _compact_active_subject_code_constraints(value)
    if not payload:
        return ""
    return (
        "## Active Subject Code Constraints\n"
        "These provider-owned facts are the active subject object/API contract "
        "for code generation. Treat them as hard constraints when editing the "
        "approved target and integration files.\n\n"
        f"{_bounded_json(payload, 12000)}\n\n"
    )


def _compact_active_subject_code_constraints(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {"constraints": _compact_constraint_list(value)}
    payload: Dict[str, Any] = {}
    for key in (
        "surface",
        "subject_id",
        "version",
        "constraints",
        "object_model_hints",
        "api_contracts",
        "forbidden_patterns",
    ):
        item = value.get(key)
        if item in (None, "", [], (), {}):
            continue
        if key in {
            "constraints",
            "object_model_hints",
            "api_contracts",
            "forbidden_patterns",
        }:
            payload[key] = _compact_constraint_list(item)
        else:
            payload[key] = item
    return {key: item for key, item in payload.items() if item not in (None, "", [])}


def _compact_constraint_list(value: Any) -> list[Any]:
    if value in (None, "", [], (), {}):
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [_compact_constraint_item(value)]
    try:
        items = list(value)
    except TypeError:
        return [str(value)]
    return [_compact_constraint_item(item) for item in items[:24]]


def _compact_constraint_item(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _snippet_text(str(item)) if isinstance(item, str) else item
            for key, item in value.items()
            if item not in (None, "", [], (), {})
        }
    if isinstance(value, str):
        return _snippet_text(value)
    return value


def _is_timeout_failure(text: str) -> bool:
    lowered = text.lower()
    return "timed out" in lowered or "timeout" in lowered


def _previous_patch_prompt_section(
    value: Any,
    *,
    current_feedback: Any = None,
) -> str:
    if value in (None, "", {}, []):
        return ""
    telemetry_policy = _telemetry_identity_preservation_policy(current_feedback)
    telemetry_summary = _previous_patch_telemetry_summary(
        value,
        exclude_ids=telemetry_policy["offending_ids"],
        include_ids=(
            telemetry_policy["protected_ids"]
            if telemetry_policy["protected_id_only"]
            else None
        ),
    )
    telemetry_blocker_section = ""
    if telemetry_policy["protected_id_only"]:
        forbidden_ids = sorted(telemetry_policy["offending_ids"])
        telemetry_blocker_section = (
            "Current blocker is telemetry identity. Do not preserve telemetry "
            "records for any id outside protected_mechanism_ids "
            f"{sorted(telemetry_policy['protected_ids'])!r}. "
            "Do not introduce or increase telemetry calls for baseline, "
            "structural, or broad phase ids outside that protected set; such "
            "ids are diagnostic context only and must not be used as mechanism "
            "evidence. "
            f"Current offending id(s): {forbidden_ids!r}; delete them or "
            "rename newly added/changed calls to the protected mechanism id(s) "
            f"{sorted(telemetry_policy['protected_ids'])!r}.\n\n"
        )
    telemetry_section = (
        "Telemetry records detected in the previous patch. Preserve these "
        "mechanism-specific calls only when they are not the current blocker:\n"
        f"{telemetry_summary}\n\n"
        if telemetry_summary
        else ""
    )
    compact_previous = _compact_previous_patch_attempt(value, digest_string=True)
    return (
        "## Previous Patch Attempt\n"
        "This is the immediately previous generated patch attempt. Repair it "
        "instead of starting from scratch. Current failure feedback overrides "
        "generic preservation. Preserve helper calls, imports, mechanism ids, "
        "and telemetry records only when the current blocker does not identify "
        "them as wrong.\n\n"
        f"{telemetry_blocker_section}"
        f"{telemetry_section}"
        f"{_bounded_json(compact_previous, 6000)}\n\n"
    )


def _compact_previous_patch_attempt(value: Any, *, digest_string: bool = False) -> Any:
    if isinstance(value, dict):
        compact: dict[str, Any] = {}
        for key, item in value.items():
            if key in {"code_content", "content_after"}:
                digest_prefix = (
                    "legacy_full_file" if key == "code_content" else "result_content"
                )
                compact.update(_content_digest_fields(digest_prefix, item))
                continue
            if key in {"old_string", "new_string"}:
                compact[f"{key}_snippet"] = _snippet_text(item)
                compact.update(_content_digest_fields(key, item))
                continue
            if key == "additional_changes" and isinstance(item, list):
                compact[key] = [
                    _compact_previous_patch_attempt(change)
                    for change in item[:6]
                    if isinstance(change, dict)
                ]
                if len(item) > 6:
                    compact["additional_changes_omitted"] = len(item) - 6
                continue
            if key == "mechanism_changes" and isinstance(item, list):
                compact[key] = item[:8]
                if len(item) > 8:
                    compact["mechanism_changes_omitted"] = len(item) - 8
                continue
            if key == "repair_attribution" and isinstance(item, list):
                compact[key] = [
                    _compact_previous_patch_attempt(entry)
                    for entry in item[:8]
                    if isinstance(entry, dict)
                ]
                if len(item) > 8:
                    compact["repair_attribution_omitted"] = len(item) - 8
                continue
            compact[key] = _compact_previous_patch_attempt(item)
        return compact
    if isinstance(value, list):
        compact_items = [
            _compact_previous_patch_attempt(item, digest_string=digest_string)
            for item in value[:8]
        ]
        if len(value) > 8:
            compact_items.append({"items_omitted": len(value) - 8})
        return compact_items
    if isinstance(value, str):
        if not digest_string:
            return _snippet_text(value)
        return {
            "text_snippet": _snippet_text(value),
            **_content_digest_fields("text", value),
        }
    return value


def _content_digest_fields(prefix: str, value: Any) -> dict[str, Any]:
    if not isinstance(value, str):
        return {}
    return {
        f"{prefix}_char_count": len(value),
        f"{prefix}_sha256": hashlib.sha256(value.encode("utf-8")).hexdigest(),
        f"{prefix}_raw_omitted": True,
    }


def _snippet_text(value: Any, max_chars: int = 600) -> str:
    text = str(value or "")
    if len(text) <= max_chars:
        return text
    suffix = "\n... <truncated previous patch snippet>"
    return text[: max(0, max_chars - len(suffix))] + suffix


def _previous_patch_telemetry_summary(
    value: Any,
    *,
    exclude_ids: set[str] | None = None,
    include_ids: set[str] | None = None,
) -> str:
    calls = _extract_previous_patch_telemetry_calls(
        value,
        exclude_ids=exclude_ids or set(),
        include_ids=include_ids,
    )
    if not calls:
        return ""
    return "\n".join(f"- `{call}`" for call in calls[:18])


def _extract_previous_patch_telemetry_calls(
    value: Any,
    *,
    exclude_ids: set[str] | None = None,
    include_ids: set[str] | None = None,
) -> list[str]:
    text = _previous_patch_text(value)
    if not text:
        return []
    excluded = exclude_ids or set()
    included = include_ids
    pattern = re.compile(
        r"context\.(record_phase|record_iteration|record_move)\("
        r"\s*(['\"])([a-z][a-z0-9_]{0,63})\2",
    )
    calls: list[str] = []
    for match in pattern.finditer(text):
        mechanism_id = match.group(3)
        if mechanism_id in excluded:
            continue
        if included is not None and mechanism_id not in included:
            continue
        call = f"context.{match.group(1)}('{mechanism_id}', ...)"
        if call not in calls:
            calls.append(call)
    return calls


def _telemetry_identity_preservation_policy(feedback: Any) -> dict[str, Any]:
    if not isinstance(feedback, dict):
        return {
            "offending_ids": set(),
            "protected_ids": set(),
            "protected_id_only": False,
        }
    failure_code = str(feedback.get("failure_code") or "")
    issue = str(feedback.get("issue") or "")
    if (
        failure_code != "code_stage_telemetry_identity_mismatch"
        and "code_stage_telemetry_identity_mismatch" not in issue
    ):
        return {
            "offending_ids": set(),
            "protected_ids": set(),
            "protected_id_only": False,
        }
    return {
        "offending_ids": _string_set(feedback.get("offending_telemetry_ids")),
        "protected_ids": _string_set(feedback.get("protected_mechanism_ids")),
        "protected_id_only": True,
    }


def _string_set(value: Any) -> set[str]:
    if isinstance(value, str):
        values = [value]
    else:
        try:
            values = list(value or [])
        except TypeError:
            values = [value]
    return {str(item).strip() for item in values if str(item).strip()}


def _previous_patch_text(value: Any) -> str:
    if value in (None, "", {}, []):
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        chunks: list[str] = []
        for key in (
            "code_content",
            "content_after",
            "old_string",
            "new_string",
            "file_path",
            "action",
        ):
            item = value.get(key)
            if item:
                chunks.append(str(item))
        for item in value.get("additional_changes") or []:
            if isinstance(item, dict):
                for key in ("code_content", "content_after", "old_string", "new_string"):
                    code = item.get(key)
                    if code:
                        chunks.append(str(code))
        return "\n".join(chunks)
    if isinstance(value, list):
        return "\n".join(_previous_patch_text(item) for item in value)
    return str(value)


def _prior_failure_prompt_section(prior_failure: str) -> str:
    prior_failure = str(prior_failure or "").strip()
    if not prior_failure:
        return ""
    lowered = prior_failure.lower()
    if "hypothesis_generation_failed" in lowered:
        return (
            "## Previous Attempt Failed\n"
            "The previous hypothesis generation or hypothesis self-check "
            "failed before code generation with:\n"
            f"{prior_failure}\n"
            "Use the approved hypothesis supplied below; do not treat this "
            "as a previous code implementation failure.\n\n"
        )
    if "self_check_failed" in lowered or "agentic_self_check_failed" in lowered:
        return (
            "## Previous Attempt Failed\n"
            "The previous deterministic self-check failed with:\n"
            f"{prior_failure}\n"
            "Address the preview or contract issue directly.\n\n"
        )
    if _is_timeout_failure(prior_failure):
        return (
            "## Previous Attempt Failed\n"
            "The previous code generation attempt timed out before "
            "returning a patch. Keep the implementation compact and "
            "bounded. Implement one coherent solver body with at most "
            "a small set of helpers, prefer one initialization path plus "
            "one bounded improvement loop, and avoid large helper forests "
            "unless absolutely necessary.\n\n"
        )
    if _is_algorithm_smoke_or_telemetry_failure(lowered):
        if "code_stage_telemetry_identity_mismatch" in lowered:
            return (
                "## Previous Attempt Failed\n"
                "The previous code generation introduced or increased "
                "telemetry for an id outside the approved protected mechanism "
                "ids:\n"
                f"{prior_failure}\n"
                "Repair only the telemetry identity issue: delete those "
                "newly added calls or rename them to the protected mechanism "
                "ids named in the failure. Baseline or structural phase ids "
                "visible in source context are diagnostic/budget context only; "
                "do not introduce, increase, or use them as mechanism evidence "
                "for this hypothesis.\n\n"
            )
        return (
            "## Previous Attempt Failed\n"
            "The previous code generation failed algorithm smoke or runtime "
            "telemetry verification with:\n"
            f"{prior_failure}\n"
            "Repair the exact runtime/API issue while preserving any telemetry "
            "records from the previous patch that already satisfied earlier "
            "activation/effect/budget feedback. Use the selected surface runtime "
            "telemetry helpers on the active code path; do not rename the "
            "mechanism, remove expected_telemetry, or change problem "
            "objectives/constraints to silence the guard. "
            "Treat telemetry/accounting-only feedback as schema or precise "
            "instrumentation repair, not permission to change the research "
            "target, constraints, or algorithm boundary. Preserve previously "
            "successful integration edits from `additional_changes` such as "
            "imports, operator registration, and call-site dispatch unless the "
            "failure specifically says that integration edge is wrong. Do not "
            "drop wiring while repairing API/schema/telemetry shape. If the feedback "
            "contains telemetry_static_preview.required_calls, the corrected "
            "code must include those mechanism-specific helper calls on the "
            "path where the mechanism actually runs. Preserve previously "
            "passing record_phase, record_iteration, or record_move calls "
            "only for the protected mechanism ids while adding the missing "
            "category. For delta-valued effect "
            "failures, follow actionable_telemetry_feedback."
            "expected_call_pattern exactly: "
            "context.record_move('<mechanism>', attempted=1, accepted=1, "
            "delta=<positive_improvement_delta>, best_improved=True). If the "
            "mechanism only intended activity/activation, do not fabricate a "
            "positive delta and do not self-reject with a contradicted premise; "
            "instrument the natural activity/decision/skipped path and let "
            "validation classify missing effect as diagnostic evidence. For conditional "
            "or rare-trigger mechanisms, instrument the natural condition, "
            "decision/budget counters, diagnostic skipped status, or a "
            "canary-targeted threshold; do not force unconditional activation "
            "or guarantee positive telemetry only to pass smoke.\n\n"
        )
    if "code_generation_failed" in lowered:
        if "telemetry" in lowered or "algorithm_smoke" in lowered:
            return (
                "## Previous Attempt Failed\n"
                "The previous code generation failed algorithm smoke or runtime "
                "telemetry verification with:\n"
                f"{prior_failure}\n"
                "Repair the exact missing activation/effect evidence for the "
                "declared mechanism id. Use the selected surface runtime "
                "telemetry helpers on the active code path; do not rename the "
                "mechanism, remove expected_telemetry, or change problem "
                "objectives/constraints to silence the guard. "
                "Treat telemetry/accounting-only feedback as schema or precise "
                "instrumentation repair, not permission to change the research "
                "target, constraints, or algorithm boundary. Preserve previously "
                "successful integration edits from `additional_changes` such as "
                "imports, operator registration, and call-site dispatch unless the "
                "failure specifically says that integration edge is wrong. Do not "
                "drop wiring while repairing API/schema/telemetry shape. If the feedback "
                "contains telemetry_static_preview.required_calls, the corrected "
                "code must include those mechanism-specific helper calls on the "
                "path where the mechanism actually runs. Preserve previously "
                "passing record_phase, record_iteration, or record_move calls "
                "only for the protected mechanism ids while adding the missing "
                "category. For delta-valued effect "
                "failures, follow actionable_telemetry_feedback."
                "expected_call_pattern exactly: "
                "context.record_move('<mechanism>', attempted=1, accepted=1, "
                "delta=<positive_improvement_delta>, best_improved=True). If "
                "the mechanism only intended activity/activation, do not "
                "fabricate a positive delta and do not self-reject with a "
                "contradicted premise; instrument the natural activity/decision/"
                "skipped path and let validation classify missing effect as "
                "diagnostic evidence. For conditional or rare-trigger "
                "mechanisms, instrument the natural condition, decision/budget "
                "counters, diagnostic skipped status, or a canary-targeted "
                "threshold; do not force unconditional activation or guarantee "
                "positive telemetry only to pass smoke.\n\n"
            )
        return (
            "## Previous Attempt Failed\n"
            "The previous code generation failed with:\n"
            f"{prior_failure}\n"
            "Avoid the same mistake.\n\n"
        )
    return (
        "## Previous Attempt Failed\n"
        "The previous code generation failed with:\n"
        f"{prior_failure}\n"
        "Avoid the same mistake.\n\n"
    )


def _is_algorithm_smoke_or_telemetry_failure(lowered: str) -> bool:
    return (
        "algorithm_smoke" in lowered
        or "algorithm smoke" in lowered
        or "telemetry" in lowered
        or "runtime audit" in lowered
    )
