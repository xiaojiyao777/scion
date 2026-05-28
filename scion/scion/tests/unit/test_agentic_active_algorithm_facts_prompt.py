from __future__ import annotations

from scion.proposal.engine import _split_code_context, _split_hypothesis_context
from scion.proposal.agentic_session_hypothesis import (
    _mechanism_novelty_gate_prompt_parity_feedback,
)
from scion.proposal.negative_facts import render_negative_fact_block
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

    hypothesis_blocks, hypothesis_prompt = _split_hypothesis_context(hypothesis_context)
    code_blocks, code_prompt = _split_code_context(code_context)
    rendered_hypothesis = (
        "\n".join(block["text"] for block in hypothesis_blocks)
        + "\n"
        + hypothesis_prompt
    )
    assert rendered_hypothesis.index("## Active Algorithm Facts") < rendered_hypothesis.index(
        "## Agentic Proposal Tool Observations"
    )
    active_fact_blocks = [
        block
        for block in hypothesis_blocks
        if "## Active Algorithm Facts" in str(block.get("text", ""))
    ]
    assert active_fact_blocks
    assert all(block.get("cache_control") for block in active_fact_blocks)
    assert "## Agentic Proposal Tool Observations" in hypothesis_prompt
    rendered_code = "\n".join(block["text"] for block in code_blocks) + "\n" + code_prompt
    assert rendered_code.index("## Active Algorithm Facts") < rendered_code.index(
        "## Agentic Proposal Tool Observations"
    )
    code_active_fact_blocks = [
        block
        for block in code_blocks
        if "## Active Algorithm Facts" in str(block.get("text", ""))
    ]
    assert code_active_fact_blocks
    assert all(block.get("cache_control") for block in code_active_fact_blocks)


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
    assert facts_status["prompt_part"] == "system"
    assert facts_status["cacheable"] is True
    assert facts_status["content_hash"]
    assert facts_status["fact_packet_digest"] == "packet-digest-123"
    assert observations_status["status"] == "included"
    assert observations_status["prompt_part"] == "user"
    assert observations_status["cacheable"] is False
    assert "agentic_proposal_tool_observations" not in manifest["truncated_sections"]
    assert "active_algorithm_facts" not in manifest["truncated_sections"]
    cacheability = manifest["provider_visible_prompt"]["cacheability"]
    assert cacheability["estimated_cacheable_chars"] > 0
    assert cacheability["estimated_non_cache_chars"] >= manifest[
        "char_budget"
    ]["user_prompt_chars"]


def test_mechanism_gate_rejection_requires_visible_fact_packet() -> None:
    result = SimpleNamespace(fact_packet_digest="packet-digest-123")

    missing_feedback = _mechanism_novelty_gate_prompt_parity_feedback(
        result,
        {
            "section_statuses": {
                "agentic_proposal_tool_observations": {"status": "included"}
            }
        },
        attempt=1,
    )
    assert missing_feedback is not None
    assert missing_feedback["failure_code"] == "gate_prompt_parity_retry_required"
    assert missing_feedback["fact_packet_digest"] == "packet-digest-123"
    assert missing_feedback["prompt_fact_status"] == "missing"

    truncated_feedback = _mechanism_novelty_gate_prompt_parity_feedback(
        result,
        {
            "section_statuses": {
                "active_algorithm_facts": {
                    "status": "truncated",
                    "fact_packet_digest": "packet-digest-123",
                }
            }
        },
        attempt=2,
    )
    assert truncated_feedback is not None
    assert truncated_feedback["prompt_fact_status"] == "truncated"

    assert (
        _mechanism_novelty_gate_prompt_parity_feedback(
            result,
            {
                "section_statuses": {
                    "active_algorithm_facts": {
                        "status": "included",
                        "fact_packet_digest": "packet-digest-123",
                    }
                }
            },
            attempt=3,
        )
        is None
    )


def test_prompt_manifest_marks_actual_section_truncation_only() -> None:
    prompt_context = {
        "seed": "manifest-section-truncation",
        "agentic_tool_observations": [
            {
                "tool_name": "context.read_active_solver_design",
                "structured_payload": {
                    "content_preview": "x" * 200000,
                    "truncated": False,
                },
            }
        ],
    }

    system_blocks, user_prompt = _split_hypothesis_context(prompt_context)
    manifest = build_api_visible_prompt_manifest(
        session_id="session-section-truncation",
        phase="draft_hypothesis",
        call_kind="hypothesis",
        prompt_context=prompt_context,
        observations=[],
        call_index=1,
        system_blocks=system_blocks,
        user_prompt=user_prompt,
    )

    observations_status = manifest["section_statuses"][
        "agentic_proposal_tool_observations"
    ]
    assert observations_status["status"] == "included"
    assert "agentic_proposal_tool_observations" not in manifest["truncated_sections"]
    assert "agentic_tool_observations_projection.v1" in user_prompt
    assert "x" * 200000 not in user_prompt


def test_prompt_manifest_keeps_truncated_receipt_section_auditable() -> None:
    receipt_payload = {
        "projection_kind": "active_solver_map_receipts.v1",
        "map_reads": [
            {
                "observation_id": "obs-map-1",
                "snapshot_digest": "snapshot-digest-1",
                "read_receipt": {
                    "tool_name": "context.read_active_solver_map",
                    "subject_id": "subject-1",
                    "digest": "receipt-digest-1",
                    "snapshot_digest": "snapshot-digest-1",
                },
                "source_policy": {"provider": "adapter-owned"},
            }
        ],
        "receipt_rule": "receipts identify provider-approved source handles",
        "truncated": True,
    }
    user_prompt = (
        "## Active Solver Map Receipts\n"
        f"{json.dumps(receipt_payload, sort_keys=True)}\n"
        "<truncated for compact prompt budget>\n"
    )

    manifest = build_api_visible_prompt_manifest(
        session_id="receipt-truncation",
        phase="draft_hypothesis",
        call_kind="hypothesis",
        prompt_context={},
        observations=[],
        call_index=1,
        system_blocks=[],
        user_prompt=user_prompt,
    )

    status = manifest["section_statuses"]["active_solver_map_receipts"]
    assert "active_solver_map_receipts" in manifest["truncated_sections"]
    assert status["status"] == "truncated"
    assert status["content_hash"]
    assert status["observation_id_count"] == 1
    assert status["observation_digest_count"] >= 1
    assert status["receipt_count"] >= 2
    assert status["digest_reference_count"] >= 2
    assert status["provenance_reference_count"] >= 2


def test_tool_observations_render_bounded_projection_not_raw_append_only() -> None:
    observations = [
        {
            "observation_id": f"obs-{idx}",
            "tool_name": "feedback.query_runtime",
            "summary": "runtime feedback with screening_win_rate_failure",
            "structured_payload": {
                "research_diagnosis": {
                    "schema_version": "research-diagnosis.v1",
                    "screening_step_count": idx,
                    "failure_mode_tags": ["screening_win_rate_failure"],
                    "runtime_signal_rows": [
                        {"round_num": row, "detail": "x" * 80}
                        for row in range(50)
                    ],
                },
                "raw_rows": [{"payload": "y" * 200} for _ in range(100)],
            },
        }
        for idx in range(120)
    ]

    _blocks, user_prompt = _split_hypothesis_context(
        {
            "problem_summary": "problem",
            "research_surfaces": "surface",
            "champion_operators_code": "code",
            "champion_stats": "stats",
            "agentic_tool_observations": observations,
        }
    )
    observation_section = user_prompt.split(
        "## Agentic Proposal Tool Observations",
        maxsplit=1,
    )[1]

    assert "agentic_tool_observations_projection.v1" in observation_section
    assert '"observation_count": 120' in observation_section
    assert '"omitted_older_count": 40' in observation_section
    assert "screening_win_rate_failure" in observation_section
    assert '"raw_rows"' not in observation_section


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


def test_static_solver_tool_observations_render_compact_receipts() -> None:
    active_facts = {
        "source": "context.read_active_solver_design",
        "snapshot_digest": "snapshot-digest-static",
        "fact_packet_digest": "packet-digest-static",
        "active_algorithm_facts": {
            "packet_id": "packet-static",
            "snapshot_digest": "snapshot-digest-static",
            "fact_packet_digest": "packet-digest-static",
            "fact_ids": ["fact.static"],
            "facts": [
                {
                    "fact_id": "fact.static",
                    "claim": "UNIQUE_STATIC_FACT_CLAIM",
                    "evidence": ["static evidence"],
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
                    "observation_id": "obs-files",
                    "tool_name": "context.list_algorithm_files",
                    "structured_payload": {
                        "files": [
                            {
                                "file_path": "policies/a.py",
                                "description": "HUGE_FILE_MANIFEST_DETAIL",
                            }
                        ],
                        "surface": "solver_design",
                    },
                },
                {
                    "observation_id": "obs-design",
                    "tool_name": "context.read_active_solver_design",
                    "structured_payload": {
                        "active_algorithm_facts": active_facts[
                            "active_algorithm_facts"
                        ],
                        "mechanisms": [{"description": "HUGE_MECHANISM_DETAIL"}],
                        "source_digest": {
                            "algorithm": "sha256",
                            "snapshot_digest": "snapshot-digest-static",
                            "files": {"policies/a.py": "abc"},
                        },
                        "surface": "solver_design",
                    },
                },
                {
                    "observation_id": "obs-graph",
                    "tool_name": "context.read_solver_call_graph",
                    "structured_payload": {
                        "edges": [
                            {
                                "from": "a",
                                "to": "b",
                                "evidence": ["HUGE_CALL_GRAPH_EDGE_DETAIL"],
                            }
                        ],
                        "source_digest": {
                            "algorithm": "sha256",
                            "snapshot_digest": "snapshot-digest-static",
                        },
                        "surface": "solver_design",
                    },
                },
            ],
        }
    )
    rendered_system = "\n".join(block["text"] for block in system_blocks)
    observation_section = user_prompt.split(
        "## Agentic Proposal Tool Observations",
        maxsplit=1,
    )[1]

    assert "UNIQUE_STATIC_FACT_CLAIM" in rendered_system
    assert "HUGE_FILE_MANIFEST_DETAIL" not in observation_section
    assert "HUGE_MECHANISM_DETAIL" not in observation_section
    assert "HUGE_CALL_GRAPH_EDGE_DETAIL" not in observation_section
    assert '"edges"' not in observation_section
    assert '"mechanisms"' not in observation_section
    assert '"files"' not in observation_section
    assert observation_section.count("static_solver_context_receipt.v1") == 3
    assert "active_algorithm_facts_ref" in observation_section
    assert "file_paths" in observation_section
    assert "edge_count" in observation_section


def test_surface_read_observation_renders_compact_receipt_with_dedicated_context() -> None:
    active_facts = {
        "source": "context.read_active_solver_design",
        "snapshot_digest": "snapshot-digest-surface",
        "fact_packet_digest": "packet-digest-surface",
        "active_algorithm_facts": {
            "packet_id": "packet-surface",
            "snapshot_digest": "snapshot-digest-surface",
            "fact_packet_digest": "packet-digest-surface",
            "fact_ids": ["fact.surface"],
            "facts": [
                {
                    "fact_id": "fact.surface",
                    "claim": "UNIQUE_SURFACE_FACT_CLAIM",
                    "evidence": ["surface evidence"],
                }
            ],
        },
    }
    prompt_context = {
        "problem_summary": "problem",
        "research_surfaces": "surface",
        "champion_operators_code": "code",
        "champion_stats": "stats",
        "agentic_active_algorithm_facts": active_facts,
        "agentic_tool_observations": [
            {
                "observation_id": "obs-full-target",
                "tool_name": "context.read_algorithm_file",
                "structured_payload": {
                    "active": True,
                    "content_preview": "def target_full_source():\n    return 1\n",
                    "digest": "target-digest",
                    "file_path": "policies/baseline_modules/local_search.py",
                    "max_chars": 64,
                    "readable": True,
                    "size_chars": 40,
                    "source": "champion_snapshot",
                    "truncated": False,
                },
            },
            {
                "observation_id": "obs-surface",
                "tool_name": "context.read_surface",
                "structured_payload": {
                    "surface": {
                        "name": "solver_design",
                        "kind": "solver_design",
                        "section": "all",
                    },
                    "target_file": "policies/baseline_modules/local_search.py",
                    "declared_targets": [
                        "policies/baseline_algorithm.py",
                        "policies/baseline_modules/*.py",
                    ],
                    "current_artifact": {
                        "file_path": "policies/baseline_modules/local_search.py",
                        "content_preview": "HUGE_SURFACE_CURRENT_PREVIEW",
                        "readable": True,
                        "size_chars": 10000,
                        "max_chars": 800,
                        "truncated": True,
                    },
                    "support_artifacts": [
                        {
                            "file_path": "policies/baseline_modules/scheduler.py",
                            "content_preview": "HUGE_SURFACE_SUPPORT_PREVIEW",
                            "python_api_summary": "HUGE_SURFACE_API_SUMMARY",
                            "readable": True,
                            "size_chars": 9000,
                            "max_chars": 800,
                            "truncated": True,
                        }
                    ],
                    "surface_contract": {
                        "schema_version": "surface-contract.v1",
                        "section": "all",
                        "target_preview": {
                            "file_path": "policies/baseline_modules/local_search.py",
                            "content_preview_chars": 800,
                            "readable": True,
                            "size_chars": 10000,
                            "max_chars": 800,
                            "truncated": True,
                        },
                    },
                },
            },
        ],
    }

    system_blocks, user_prompt = _split_hypothesis_context(prompt_context)
    rendered_system = "\n".join(block["text"] for block in system_blocks)
    observation_section = user_prompt.split(
        "## Agentic Proposal Tool Observations",
        maxsplit=1,
    )[1]
    manifest = build_api_visible_prompt_manifest(
        session_id="surface-compact",
        phase="draft_hypothesis",
        call_kind="hypothesis",
        prompt_context=prompt_context,
        observations=[],
        call_index=1,
        system_blocks=system_blocks,
        user_prompt=user_prompt,
    )

    assert "UNIQUE_SURFACE_FACT_CLAIM" in rendered_system
    assert "## Solver-Design Full Algorithm File Reads" in rendered_system
    assert all(
        block.get("cache_control")
        for block in system_blocks
        if "## Solver-Design Full Algorithm File Reads" in block["text"]
    )
    assert "surface_interface_receipt.v1" in observation_section
    assert "HUGE_SURFACE_CURRENT_PREVIEW" not in observation_section
    assert "HUGE_SURFACE_SUPPORT_PREVIEW" not in observation_section
    assert "HUGE_SURFACE_API_SUMMARY" not in observation_section
    assert '"content_preview"' not in observation_section
    assert '"python_api_summary"' not in observation_section
    assert "support_artifact_paths" in observation_section
    assert "policies/baseline_modules/scheduler.py" in observation_section
    assert manifest["section_statuses"]["agentic_proposal_tool_observations"][
        "char_count"
    ] == manifest["char_budget"]["sections"]["agentic_proposal_tool_observations"]
    assert manifest["char_budget"]["sections"][
        "agentic_proposal_tool_observations"
    ] < 6000


def test_preview_tool_observation_renders_compact_receipt() -> None:
    huge_declared_fields = [f"solver_algorithm_field_{idx}" for idx in range(300)]
    system_blocks, user_prompt = _split_hypothesis_context(
        {
            "problem_summary": "problem",
            "research_surfaces": "surface",
            "champion_operators_code": "code",
            "champion_stats": "stats",
            "agentic_tool_observations": [
                {
                    "observation_id": "obs-schema",
                    "tool_name": "proposal.schema_preview",
                    "summary": "Schema preview found issues: C11_expected_telemetry",
                    "structured_payload": {
                        "passed": False,
                        "hypothesis": {
                            "checks": [
                                {
                                    "name": "C11_expected_telemetry",
                                    "passed": False,
                                    "detail": "HUGE_SCHEMA_DETAIL" * 200,
                                }
                            ],
                            "expected_telemetry_contract": {
                                "declared_runtime_fields": huge_declared_fields,
                                "allowed_expected_telemetry_template": {
                                    "expected_telemetry": {
                                        "activation": [
                                            "solver_algorithm_context_records.foo"
                                        ]
                                    }
                                },
                            },
                        },
                        "workspace_materialized": False,
                    },
                }
            ],
        }
    )
    observation_section = user_prompt.split(
        "## Agentic Proposal Tool Observations",
        maxsplit=1,
    )[1]
    manifest = build_api_visible_prompt_manifest(
        session_id="preview-compact",
        phase="draft_hypothesis",
        call_kind="hypothesis",
        prompt_context={},
        observations=[],
        call_index=1,
        system_blocks=system_blocks,
        user_prompt=user_prompt,
    )

    assert "preview_tool_receipt.v1" in observation_section
    assert "C11_expected_telemetry" in observation_section
    assert "HUGE_SCHEMA_DETAIL" not in observation_section
    assert "declared_runtime_fields" not in observation_section
    assert "allowed_expected_telemetry_template" not in observation_section
    assert "hypothesis_schema_telemetry_retry_feedback" in observation_section
    assert manifest["char_budget"]["sections"][
        "agentic_proposal_tool_observations"
    ] < 2500


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


def test_negative_fact_block_includes_telemetry_and_weak_positive_memory() -> None:
    block = render_negative_fact_block(
        prior_quality_blocks=(
            {
                "mechanism": "same_route_or_opt",
                "target_file": "policies/baseline_modules/local_search.py",
                "failure_code": "telemetry_validation_repairable",
                "diagnostic_type": "effect_missing_observed_activation",
                "activation_status": "observed",
                "effect_status": "zero",
                "why_not_promoted": "active_no_case_level_gate",
                "screening_pair_case_split": (
                    "pair_wins=5,pair_losses=3,pair_ties=8,"
                    "case_win_rate=0.25"
                ),
                "allowed_variant_guidance": (
                    "adjust trigger, schedule, or combine with another bounded "
                    "mechanism; do not repeat unchanged mechanism"
                ),
            },
        )
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

    assert "same_route_or_opt" in user_prompt
    assert "effect_missing_observed_activation" in user_prompt
    assert "active_no_case_level_gate" in user_prompt
    assert "pair_wins=5" in user_prompt
    assert "repeat_unchanged_mechanism=false" in user_prompt
    assert user_prompt.index("same_route_or_opt") < user_prompt.index("## Task")


def test_hypothesis_prompt_renders_expected_telemetry_schema_examples() -> None:
    _blocks, user_prompt = _split_hypothesis_context(
        {
            "problem_summary": "Synthetic planner problem.",
            "research_surfaces": "planner_policy",
            "champion_operators_code": "def solve():\n    pass\n",
            "champion_stats": "{}",
            "operator_categories": "planner_policy",
            "agentic_expected_telemetry_guidance": {
                "schema_version": "agentic-expected-telemetry-guidance.v1",
                "templates_by_surface": {
                    "planner_policy": {
                        "expected_telemetry": {
                            "activation": [
                                "planner_stage_runtime_ms.<mechanism_id>"
                            ],
                            "effect": [
                                "planner_best_delta.<mechanism_id>"
                            ],
                        }
                    }
                },
            },
        }
    )

    assert "## Expected Telemetry Schema Examples" in user_prompt
    assert "planner_stage_runtime_ms.<mechanism_id>" in user_prompt
    assert user_prompt.index("Expected Telemetry Schema Examples") < user_prompt.index(
        "Telemetry contract:"
    )
