from __future__ import annotations

from scion.proposal.engine import _split_code_context, _split_hypothesis_context
from scion.proposal.prompt_manifest import build_api_visible_prompt_manifest
from scion.tests.unit.agentic_session_test_support import *


def _solver_design_hypothesis() -> HypothesisProposal:
    return HypothesisProposal(
        **_valid_hypothesis_payload(
            change_locus="solver_design",
            target_file="policies/baseline_modules/local_search.py",
            hypothesis_text=(
                "Improve existing cross-route Or-opt candidate ordering and "
                "delta scoring without adding a duplicate neighborhood."
            ),
            target_weakness=(
                "Existing local search can spend effort on low-value candidate "
                "pairs before reaching better distance improvements."
            ),
            expected_effect=(
                "Reduce total_distance while preserving active feasibility and "
                "route-limit guards."
            ),
        )
    )


def test_hypothesis_and_code_context_include_active_algorithm_facts(
    tmp_path: Path,
) -> None:
    context = replace(
        _cvrp_context_with_champion(tmp_path),
        forced_surface="solver_design",
        active_problem_boundary_surfaces=("solver_design",),
    )
    patch = PatchProposal(
        file_path="policies/baseline_modules/local_search.py",
        action="modify",
        code_content="def placeholder():\n    return None\n",
    )
    creative = PlanningCreative(
        [{"stop": True}],
        hypothesis=_solver_design_hypothesis(),
        patch=patch,
    )
    session = AgenticProposalSession(
        creative,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    session.run(
        AgenticProposalRequest(
            campaign_id="camp-cvrp-facts",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={"seed": "facts-context"},
            build_code_context=lambda hypothesis: {
                "research_surface_name": "solver_design",
                "research_surface_kind": "solver_design",
                "target_file": hypothesis.target_file,
                "target_file_code": "# target file omitted in test\n",
            },
            approve_hypothesis=lambda _hypothesis: SimpleNamespace(
                passed=True,
                failure_reason=None,
            ),
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    hypothesis_context = creative.hypothesis_contexts[0]
    code_context = creative.code_contexts[0]
    hypothesis_facts = hypothesis_context["agentic_active_algorithm_facts"]
    code_facts = code_context["agentic_active_algorithm_facts"]
    hypothesis_packet = hypothesis_facts["active_algorithm_facts"]
    code_packet = code_facts["active_algorithm_facts"]

    assert hypothesis_facts["fact_packet_digest"] == code_facts["fact_packet_digest"]
    assert hypothesis_packet["fact_packet_digest"] == code_packet["fact_packet_digest"]
    assert "cvrp.destroy_repair.shaw_related_removal" in hypothesis_packet["fact_ids"]
    assert "cvrp.search_state.starts_feasible_rejects_infeasible" in hypothesis_packet[
        "fact_ids"
    ]
    assert list(hypothesis_context).index("agentic_active_algorithm_facts") < list(
        hypothesis_context
    ).index("agentic_tool_observations")
    assert list(code_context).index("agentic_active_algorithm_facts") < list(
        code_context
    ).index("agentic_tool_observations")

    hypothesis_blocks, _ = _split_hypothesis_context(hypothesis_context)
    _, code_prompt = _split_code_context(code_context)
    rendered_hypothesis = "\n".join(block["text"] for block in hypothesis_blocks)
    assert rendered_hypothesis.index("## Active Algorithm Facts") < rendered_hypothesis.index(
        "## Agentic Proposal Tool Observations"
    )
    assert code_prompt.index("## Active Algorithm Facts") < code_prompt.index(
        "## Agentic Proposal Tool Observations"
    )


def test_prompt_manifest_marks_large_observations_truncated_but_facts_included() -> None:
    active_facts = {
        "source": "context.read_active_solver_design",
        "fact_packet_digest": "packet-digest-123",
        "active_algorithm_facts": {
            "packet_id": "cvrp_active_algorithm_facts_v1",
            "snapshot_digest": "snapshot-digest-123",
            "fact_packet_digest": "packet-digest-123",
            "fact_ids": ["cvrp.destroy_repair.shaw_related_removal"],
            "facts": [
                {
                    "fact_id": "cvrp.destroy_repair.shaw_related_removal",
                    "claim": "_shaw_removal already exists.",
                    "evidence": ["_shaw_removal"],
                    "source_paths_or_symbols": [
                        "policies/baseline_modules/destroy_repair.py::_shaw_removal"
                    ],
                    "importance": "high",
                    "used_by_prompt": True,
                    "used_by_gate": True,
                }
            ],
        },
    }
    prompt_context = {
        "seed": "manifest-facts",
        "agentic_active_algorithm_facts": active_facts,
        "agentic_tool_observations": [
            {
                "tool_name": "context.read_active_solver_design",
                "structured_payload": {
                    "content_preview": "x" * 50000,
                    "truncated": True,
                },
            }
        ],
    }

    manifest = build_api_visible_prompt_manifest(
        session_id="session-facts",
        phase="draft_hypothesis",
        call_kind="hypothesis",
        prompt_context=prompt_context,
        observations=[],
        call_index=1,
    )

    facts_status = manifest["section_statuses"]["agentic_active_algorithm_facts"]
    observations_status = manifest["section_statuses"]["agentic_tool_observations"]
    assert facts_status["status"] == "included"
    assert facts_status["content_hash"]
    assert facts_status["fact_packet_digest"] == "packet-digest-123"
    assert observations_status["status"] == "truncated"
    assert "agentic_tool_observations" in manifest["truncated_sections"]
    assert "agentic_active_algorithm_facts" not in manifest["truncated_sections"]
