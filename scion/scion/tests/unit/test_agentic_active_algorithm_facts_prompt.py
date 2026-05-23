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
    assert "cvrp.destroy_repair.random_removal_destroy" in hypothesis_packet["fact_ids"]
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

    system_blocks, user_prompt = _split_hypothesis_context(prompt_context)
    manifest = build_api_visible_prompt_manifest(
        session_id="session-facts",
        phase="draft_hypothesis",
        call_kind="hypothesis",
        prompt_context=prompt_context,
        observations=[],
        call_index=1,
        system_blocks=system_blocks,
        user_prompt=user_prompt,
    )

    facts_status = manifest["section_statuses"]["active_algorithm_facts"]
    observations_status = manifest["section_statuses"][
        "agentic_proposal_tool_observations"
    ]
    assert facts_status["status"] == "included"
    assert facts_status["content_hash"]
    assert facts_status["fact_packet_digest"] == "packet-digest-123"
    assert observations_status["status"] == "truncated"
    assert "agentic_proposal_tool_observations" in manifest["truncated_sections"]
    assert "active_algorithm_facts" not in manifest["truncated_sections"]


def test_raw_tool_observations_reference_duplicate_active_facts_by_digest() -> None:
    active_facts = {
        "source": "context.read_active_solver_design",
        "snapshot_digest": "snapshot-digest-1",
        "fact_packet_digest": "packet-digest-1",
        "active_algorithm_facts": {
            "packet_id": "packet-1",
            "snapshot_digest": "snapshot-digest-1",
            "fact_packet_digest": "packet-digest-1",
            "fact_ids": ["fact.unique"],
            "facts": [
                {
                    "fact_id": "fact.unique",
                    "claim": "UNIQUE_ACTIVE_FACT_CLAIM",
                    "evidence": ["source evidence"],
                }
            ],
        },
    }
    system_blocks, user_prompt = _split_hypothesis_context(
        {
            "problem_summary": "problem",
            "research_surfaces": "surface",
            "champion_operators_code": "code",
            "champion_stats": "stats",
            "agentic_active_algorithm_facts": active_facts,
            "agentic_tool_observations": [
                {
                    "observation_id": "obs-active",
                    "tool_name": "context.read_active_solver_design",
                    "structured_payload": {
                        "active_algorithm_facts": active_facts[
                            "active_algorithm_facts"
                        ],
                    },
                }
            ],
        }
    )
    rendered = json.dumps(system_blocks, sort_keys=True) + user_prompt

    assert rendered.count("UNIQUE_ACTIVE_FACT_CLAIM") == 1
    assert "active_algorithm_facts_ref" in rendered
    assert "deduplicated; see Active Algorithm Facts" in rendered


def test_negative_fact_block_renders_before_hypothesis_task_without_domain_terms() -> None:
    block = (
        "## Do Not Claim Missing / Known Existing Mechanisms\n"
        "- fact_id=planner.swap_window.exists; mechanism=swap_window; "
        "do_not_claim_missing=true; allowed_variant_guidance=Change trigger "
        "or observable behavior."
    )
    _blocks, user_prompt = _split_hypothesis_context(
        {
            "problem_summary": "Synthetic planner problem.",
            "research_surfaces": "planner_policy",
            "champion_operators_code": "def solve():\n    pass\n",
            "champion_stats": "{}",
            "operator_categories": "planner_policy",
            "agentic_negative_fact_block": block,
        }
    )

    assert block in user_prompt
    assert user_prompt.index("## Do Not Claim Missing") < user_prompt.index("## Task")
    lowered = user_prompt.lower()
    assert "cvrp" not in lowered
    assert "alns" not in lowered
    assert "vns" not in lowered
