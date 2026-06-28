from __future__ import annotations

from pathlib import Path

import pytest

from scion.proposal.engine.hypothesis_prompts import (
    _split_hypothesis_target_intent_context,
)
from scion.research_guidance import launch_research_guidance_payload

from .proposal_pipeline_test_support import _champion, _pipeline


@pytest.mark.parametrize(
    "context_focus",
    [
        {},
        {"schema_version": "empty_launch_focus_shell.v1"},
        {"research_focus": {"required_mechanism_ids": []}},
    ],
)
def test_agentic_tool_context_uses_provider_for_empty_context_focus_shells(
    context_focus: dict,
) -> None:
    provider_focus = {
        "schema_version": "provider_focus.v1",
        "reviewed_mechanism_ids": ["reviewed_probe"],
        "successor_opportunity_families": ["successor_probe"],
    }
    pipeline, branch, _, _, _, _ = _pipeline(
        launch_research_focus_provider=lambda: provider_focus,
    )

    request = pipeline._build_agentic_request(
        branch=branch,
        champion=_champion(),
        hypothesis_context={"launch_research_focus": context_focus},
    )

    assert request.tool_context is not None
    assert request.tool_context.launch_research_focus == provider_focus


def test_agentic_tool_context_loads_launch_research_focus_from_provider(
    tmp_path: Path,
) -> None:
    reviewed_id = "reviewed_mechanism_probe"
    successor_family = "successor_family_probe"
    manifest_path = tmp_path / "prepared_run_manifest.v1.json"
    launch_focus_payload = launch_research_guidance_payload(
        manifest_path=manifest_path,
        manifest={
            "problem_family": "toy",
            "analysis_intent": (
                "Prepared successor focus for a generic test problem."
            ),
            "acceptance_focus": ["Keep prepared guidance proposal-only."],
            "research_focus": {
                "schema_version": "scion.prepared_research_focus.v1",
                "required_mechanism_ids": [],
                "reviewed_mechanism_ids": [reviewed_id],
                "successor_opportunity_families": [successor_family],
                "next_required_direction": (
                    "Select a materially different successor mechanism."
                ),
            },
        },
    )
    pipeline, branch, _, _, _, _ = _pipeline(
        launch_research_focus_provider=lambda: launch_focus_payload,
    )
    branch.branch_code_status = "active_no_effect"
    branch.branch_mechanism_ids = (reviewed_id,)

    request = pipeline._build_agentic_request(
        branch=branch,
        champion=_champion(),
        hypothesis_context={},
    )

    assert request.tool_context is not None
    launch_focus = request.tool_context.launch_research_focus
    assert launch_focus["schema_version"] == (
        "scion.launch_research_guidance_prompt.v1"
    )
    assert launch_focus["source"] == "PREPARED_RUN_MANIFEST"
    assert launch_focus["required_mechanism_ids"] == []
    assert launch_focus["reviewed_mechanism_ids"] == [reviewed_id]
    assert launch_focus["successor_opportunity_families"] == [successor_family]

    prompt_context = {
        "problem_summary": "Toy combinatorial optimization problem.",
        "research_surfaces": "local_search",
        "objective_policy_guidance": "Improve the declared objective safely.",
        "solver_mechanics": "Use the declared adapter mechanics.",
        "champion_operators_code": "def solve(instance):\n    return instance\n",
        "champion_stats": "champion=v1",
        "targetable_files": "operators/bounded.py",
        "active_problem_boundary_surfaces": "local_search",
        "branch_hygiene": request.tool_context.branch_hygiene,
        "branch_hygiene_guidance": request.tool_context.branch_hygiene_guidance,
        "branch_followup_policy": request.tool_context.branch_hygiene.get(
            "branch_followup_policy",
            "",
        ),
        "launch_research_focus": launch_focus,
    }
    target_blocks, target_user = _split_hypothesis_target_intent_context(
        prompt_context
    )
    target_text = "\n\n".join(
        str(block.get("text") or "") for block in target_blocks
    ) + target_user

    assert "## Prepared Successor Focus" in target_text
    assert reviewed_id in target_text
    assert successor_family in target_text
    assert "do not select or repeat a reviewed mechanism id" in target_text
    assert "## Same-Mechanism Follow-up Constraints" not in target_text


def test_agentic_tool_context_does_not_swallow_launch_focus_provider_failure() -> None:
    def failing_provider():
        raise RuntimeError("launch focus provider failed")

    pipeline, branch, _, _, _, _ = _pipeline(
        launch_research_focus_provider=failing_provider,
    )

    with pytest.raises(RuntimeError, match="launch focus provider failed"):
        pipeline._build_agentic_request(
            branch=branch,
            champion=_champion(),
            hypothesis_context={},
        )
