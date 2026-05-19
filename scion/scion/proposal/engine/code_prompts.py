"""Code-generation prompt rendering for the proposal engine."""

from __future__ import annotations

from typing import Any, Dict

from .prompt_common import (
    _CACHE_5M,
    _DefaultDict,
    _agentic_research_context_block,
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
        "Your task is to write the complete file contents that implement the approved hypothesis below.\n\n"
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
            "The approved solver-design target file is provided in full in the "
            "`Target File` section below. Legacy component policies may be "
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

    system_blocks = [
        {
            "type": "text",
            "text": static_text,
            "cache_control": _CACHE_5M,
        },
        {
            "type": "text",
            "text": champion_text,
            "cache_control": _CACHE_5M,
        },
    ]

    prior_failure_section = ""
    if D["prior_code_failure"]:
        prior_failure_section = _prior_failure_prompt_section(
            str(D["prior_code_failure"])
        )
    agentic_context = _agentic_research_context_block(D, code_phase=True)
    if agentic_context:
        prior_failure_section += f"{agentic_context}\n\n"

    user_prompt = (
        f"{prior_failure_section}"
        f"## Hypothesis to Implement\n{_code_hypothesis_detail(D, is_solver_design_surface)}\n\n"
        f"{solver_design_api_manifest_section}"
        f"## Approved Target File Full Current Content\n{D['target_file_code']}\n\n"
        f"{solver_design_integration_files_section}"
        f"## Reference Surface Files\n{D['reference_operators']}\n\n"
        f"## Constraints\n"
        f"- Editable files: {D['editable_patterns']}\n"
        f"- Frozen (DO NOT MODIFY): {D['frozen_patterns']}\n"
        f"- Top-level `file_path` must be exactly the approved target_file: "
        f"{D['target_file']}\n"
        f"- First set `premise_check` to one of: supported, contradicted, duplicate, wrong_owner.\n"
        f"- If the target content already has the proposed mechanism, contradicts the hypothesis, or shows a different owner file should change, return that premise_check with `premise_check_reason` and leave patch fields empty.\n"
        f"- Conform to the active research-surface interface specification exactly\n"
        f"- Preserve all feasibility, consistency, and determinism invariants described there\n"
        f"- For operator surfaces, use the provided `rng` argument for all randomness and return the new solution/artifact, or the original if no valid move is found\n"
        f"- For policy surfaces, implement the required module-level functions and keep return values inside the documented bounds\n\n"
        f"{solver_design_user_constraints}\n"
        f"Respond with a single JSON object (no markdown fences, no extra text):\n"
        f"{{\n"
        f'  "premise_check": "supported" | "contradicted" | "duplicate" | "wrong_owner",\n'
        f'  "premise_check_reason": "<brief reason when not supported, otherwise empty>",\n'
        f'  "file_path": "<relative path, e.g. operators/my_operator.py>",\n'
        f'  "action": "modify" | "create" | "delete",\n'
        f'  "code_content": "<complete file contents>",\n'
        f'  "additional_changes": [{{"file_path": "<relative path>", '
        f'"action": "modify" | "create" | "delete", '
        f'"code_content": "<complete file contents>"}}],\n'
        f'  "test_hint": "<optional note, or null>"\n'
        f"}}\n"
    )

    return system_blocks, user_prompt


def _is_timeout_failure(text: str) -> bool:
    lowered = text.lower()
    return "timed out" in lowered or "timeout" in lowered


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
            "a small set of helpers, prefer one construction path plus "
            "one bounded improvement loop, and avoid large helper forests "
            "unless absolutely necessary.\n\n"
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
                "objectives/constraints to silence the guard.\n\n"
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
