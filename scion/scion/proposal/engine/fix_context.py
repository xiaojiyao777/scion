"""Fix-context prompt rendering for proposal-engine repair requests."""

from __future__ import annotations

from typing import Any, Dict

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
        f"## Verification Failure Details\n{D['failure_detail']}\n\n"
        f"## Constraints\n"
        f"- Editable files: {D['editable_patterns']}\n"
        f"- Frozen (DO NOT MODIFY): {D['frozen_patterns']}\n"
        f"- Preserve the research-surface interface described above exactly\n"
        f"- Make only the minimal changes needed to fix the reported failure\n"
        f"- If the failure is a telemetry guard or algorithm smoke failure, keep "
        f"the declared mechanism id stable and add the missing activation/effect "
        f"runtime record on the active path. Do not edit objectives, constraints, "
        f"or expected telemetry just to pass the guard.\n"
    )

    return system_blocks, user_prompt
