"""Fix-context prompt rendering for proposal-engine repair requests."""

from __future__ import annotations

from typing import Any, Dict

from scion.proposal.edit_protocol import build_patch_edit_source_manifest

from .prompt_common import _CACHE_5M, _DefaultDict


def _split_fix_context(
    context: Dict[str, Any],
) -> "tuple[list[dict], str]":
    """Split fix context into system blocks (cacheable) and user prompt.

    System (1h cache): role + problem + operator interface + import whitelist
    User (dynamic): original code + failure details + task
    """
    D = _DefaultDict(context)
    solver_mechanics = str(D["solver_mechanics"]).strip()
    problem_object = str(D["problem_object"]).strip()
    problem_object_section = (
        f"## Problem Object\n{problem_object}\n\n" if problem_object else ""
    )
    solver_mechanics_section = (
        f"## Solver Execution Model\n{solver_mechanics}\n\n" if solver_mechanics else ""
    )

    system_text = (
        "You are a software engineer fixing an optimisation research-surface file that failed verification.\n"
        "Correct the code so it passes, while preserving the intended logic.\n\n"
        f"## Problem Summary\n{D['problem_summary']}\n\n"
        f"{problem_object_section}"
        f"{solver_mechanics_section}"
        f"## Research Surface Interface Specification\n"
        f"Follow this interface exactly:\n\n"
        f"{D['operator_interface_spec']}\n\n"
        f"## Allowed Imports\n"
        f"Only use modules from this whitelist — any other import will be rejected:\n"
        f"{D['import_whitelist']}"
    )

    system_blocks = [
        {
            "type": "text",
            "text": system_text,
            "cache_control": _CACHE_5M,
        }
    ]

    user_prompt = (
        f"## Original Code That Failed\n{D['original_code']}\n\n"
        f"## Patch Edit Source Digests\n"
        f"{build_patch_edit_source_manifest(context)}\n\n"
        f"## Verification Failure Details\n{D['failure_detail']}\n\n"
        f"## Constraints\n"
        f"- Editable files: {D['editable_patterns']}\n"
        f"- Frozen (DO NOT MODIFY): {D['frozen_patterns']}\n"
        f"- Preserve the research-surface interface described above exactly\n"
        f"- Make only the minimal changes needed to fix the reported failure\n"
        f"- For existing `action: modify` files, default to "
        f"`edit_intent: exact_replace`. Use the source_digest shown above "
        f"and exact old/new strings.\n"
        f"- Use `edit_intent: full_file` with `content_after` only for "
        f"creates or deletes. Host-visible existing-file modifies that emit "
        f"`full_file`/`content_after` are rejected by default; "
        f"`full_file_reason` is not an authorization. Do not emit unified diffs.\n"
        f"- If the failure is a telemetry guard or algorithm smoke failure, keep "
        f"the declared mechanism id stable and add the missing activation/effect "
        f"runtime record on the active path. Do not edit objectives, constraints, "
        f"or expected telemetry just to pass the guard. For delta-valued effect "
        f"failures, use "
        f"`context.record_move('<mechanism>', attempted=1, accepted=1, "
        f"delta=<positive_improvement_delta>, best_improved=True)` only when "
        f"the mechanism truly produces positive improvement. If the mechanism "
        f"is activity/activation-only, report the telemetry declaration mismatch "
        f"instead of fabricating effect evidence.\n"
    )

    return system_blocks, user_prompt
