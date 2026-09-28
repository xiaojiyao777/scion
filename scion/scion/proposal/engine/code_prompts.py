"""Research-core code prompt rendering for the direct V3 proposal engine."""

from __future__ import annotations

from typing import Any, Dict

from .hypothesis_prompts import _direct_v3_canonical_json
from .prompt_common import _CACHE_5M


def _split_code_context(
    context: Dict[str, Any],
) -> tuple[list[dict], str]:
    """Render only the approved hypothesis and its frozen editable source."""

    source_context = context["editable_source_context"]
    visible_source_context = {
        **source_context,
        "sources": [
            {
                **source,
                "content": (
                    source.get("content") if source.get("visible") is True else None
                ),
            }
            for source in source_context["sources"]
        ],
        "public_tests": [
            {
                **public_test,
                "content": (
                    public_test.get("content")
                    if public_test.get("visible") is True
                    else None
                ),
            }
            for public_test in source_context["public_tests"]
        ],
    }
    provider_context = {
        "approved_hypothesis": context["approved_hypothesis"],
        "editable_source_context": visible_source_context,
    }

    system_blocks = [
        {
            "type": "text",
            "text": (
                "You are implementing an approved research hypothesis for a "
                "combinatorial optimisation solver. Produce a source-bound typed "
                "edit set that preserves the problem-owned interface, feasibility, "
                "determinism, and declared higher-priority objectives.\n\n"
                "The supplied current source is the complete edit base, which "
                "may already contain earlier branch changes; it is not necessarily "
                "the champion comparator. Untouched inherited code remains in "
                "the resulting candidate. Implement the approved hypothesis's "
                "delta against this source. If it calls for replacing a prior "
                "mechanism, include the necessary companion edits within the "
                "declared editable boundary; describing an alternative does not "
                "remove the inherited implementation. Do not infer an automatic "
                "rollback or an extra ablation requirement. Protocol evaluates "
                "the complete resulting candidate, not this edit in isolation.\n\n"
                "Testing guidance, not an extra gate: calling a helper directly "
                "does not show that the real entrypoint reaches it. Trace relevant "
                "callers and configuration guards when assessing activation. A "
                "mock collaborator can test wiring without showing that the real "
                "class implements the called methods; an integration probe with "
                "real collaborators can expose that gap. Mocks remain useful for "
                "isolated claims. Optional falsifier_diagnostic contains only an "
                "untrusted failure phase, exception category and, when available, "
                "a one-based line in your submitted probe. It is not "
                "an exception message or proof of a hypothesis failure; setup, "
                "probe and implementation defects can all cause exceptions. It "
                "does not change the failed exact-patch rule. Passing host checks "
                "after omitting a previously failed probe does not establish its "
                "claim, even for a different executable revision. Choose tests "
                "suited to the claim; no read, probe style or mechanism is required."
            ),
            "cache_control": _CACHE_5M,
        },
        {
            "type": "text",
            "text": (
                "## Direct V3 Canonical Code Context\n"
                f"{_direct_v3_canonical_json(provider_context)}"
            ),
        },
    ]
    user_prompt = (
        "## Implementation And Output Instructions\n"
        "Implement the approved hypothesis from the current source and target API "
        "guidance as one coherent patch. Source roles identify the target, its "
        "local dependencies, callers, and unread peer inventory; public_tests are "
        "read-only development references. Include necessary companion edits; "
        "follow the tool schema's edit protocol and return the patch through the "
        "required tool schema."
    )
    return system_blocks, user_prompt


__all__ = ["_split_code_context"]
