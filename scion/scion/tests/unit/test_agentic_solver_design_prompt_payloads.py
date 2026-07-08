from __future__ import annotations

from scion.problems.cvrp.solver_design_provider import CvrpSolverDesignProvider
from scion.proposal.engine import (
    _split_code_context,
    _split_hypothesis_context,
    _split_hypothesis_target_intent_context,
)
from scion.proposal.engine.code_prompts import (
    _active_subject_code_constraints_section,
)
from scion.proposal.prompt_manifest import build_api_visible_prompt_manifest
from scion.tests.unit.agentic_solver_design_test_support import *


class SyntheticSolverDesignPromptProvider:
    def solver_design_broad_scope_terms(self):
        return ("synthetic-wide",)

    def solver_design_code_rules(self, _context):
        return (
            "SYNTHETIC_CODE_RULE: keep beam-state updates inside the declared solver body.",
        )

    def solver_design_scope_guidance(self, _context, *, mode, broad_terms):
        return (
            f"SYNTHETIC_SCOPE: mode={mode or 'default'} terms={','.join(broad_terms)}",
        )

    def solver_design_user_constraints(self, _context):
        return (
            "SYNTHETIC_USER_CONSTRAINT: return a synthetic artifact with a stable score.",
        )


def test_active_subject_code_constraints_section_is_not_prompt_truncated() -> None:
    payload = {
        "surface": "solver_design",
        "subject_id": "synthetic",
        "version": "v1",
        "constraints": [
            {
                "name": f"constraint_{idx}",
                "requirement": "preserve the active subject contract " * 20,
            }
            for idx in range(80)
        ],
        "forbidden_patterns": [
            {"name": "avoid_full_file_rewrite", "pattern": "full file rewrite"}
        ],
    }

    rendered = _active_subject_code_constraints_section(payload)

    assert "## Active Subject Code Constraints" in rendered
    assert "... <truncated agentic context>" not in rendered
    assert "constraint_79" in rendered
    assert "avoid_full_file_rewrite" in rendered


def test_solver_design_hypothesis_prompt_resolves_provider_from_ref() -> None:
    _system_blocks, user_prompt = _split_hypothesis_context(
        {
            "problem_summary": "CVRP.",
            "research_surfaces": "solver_design [solver_design]",
            "objective_policy_guidance": "",
            "solver_mechanics": "",
            "champion_operators_code": "",
            "champion_stats": "{}",
            "experiment_history": "",
            "blacklist_summary": "",
            "active_hyp_summary": "",
            "sibling_summary": "",
            "operator_categories": "solver_design",
            "available_actions": "modify",
            "targetable_files": "policies/baseline_modules/scheduler.py",
            "active_problem_boundary_surfaces": "solver_design",
            # Agentic context sanitization removes provider objects; the ref is
            # the durable bridge back to the problem-owned prompt provider.
            "solver_design_prompt_provider": {"sanitized": True},
            "solver_design_prompt_provider_ref": (
                "scion.problems.cvrp.solver_design_provider."
                "CvrpSolverDesignProvider"
            ),
        }
    )

    assert "adaptive embedded-VNS share-70 line has already been tested" in user_prompt
    assert "floor, hard-cap, repair-rescue, and sparse-tail-rescue" in user_prompt
    assert "X-n110 30s checks reproduced the tail loss" in user_prompt
    assert "materially different from floor, hard-cap, repair-rescue" in user_prompt
    assert "record direct effect telemetry with `context.record_move`" in user_prompt
    assert "activation/runtime counters alone leave effect attribution missing" in user_prompt
    assert "`material_difference.changed_dimensions`" in user_prompt
    assert "`material_difference.contrast`" in user_prompt
    assert "`material_difference.evidence`" in user_prompt
    assert "branch_lesson_usage.clean_fork_diversity_claim" in user_prompt
    assert "priority_case_ids" in user_prompt
    assert "effective_priority_case_ids" in user_prompt
    assert "algorithmic-intervention sufficiency" in user_prompt
    assert "config-only activation" in user_prompt
    assert "final total_distance attribution" in user_prompt
    assert "Current CVRP route-merge lesson" in user_prompt
    assert "post-share70 target-selection run first selected `destroy_repair.py`" in user_prompt
    assert "pair W/L/T `10/3/19`" in user_prompt
    assert "`route_merge_repair` effect telemetry positive in `19/32`" in user_prompt
    assert "Do not default to another `route_merge_repair` absorption" in user_prompt
    assert "pivot to a materially different problem-owned solver-design lever" in user_prompt
    assert "explicitly contrast against the tested guarded-v2" in user_prompt
    assert "choose a different solver-design target" in user_prompt
    assert "Current CVRP demand-slack lesson" in user_prompt
    assert "`demand_slack_regret_insertion`" in user_prompt
    assert "`16/28/4` pair W/L/T" in user_prompt
    assert "prior-negative CMT2 must stay in follow-up coverage" in user_prompt
    assert "Do not continue unchanged `demand_slack_regret_insertion`" in user_prompt
    assert "Follow-up coverage is handled by Protocol case selection" in user_prompt
    assert "Current CVRP post-demand-slack pivot lesson" in user_prompt
    assert "`cross_route_2opt_reconnect`" in user_prompt
    assert "`cluster_biased_worst_removal`" in user_prompt
    assert "`5/10/17` pair W/L/T" in user_prompt
    assert "`8/16/8`" in user_prompt
    assert "Do not repeat unchanged `cross_route_2opt_reconnect`" in user_prompt
    assert "broad budget changes" in user_prompt
    assert "Current CVRP construction-pivot lesson" in user_prompt
    assert "`route_limit_seed_diversification`" in user_prompt
    assert "`1/3/28` pair W/L/T" in user_prompt
    assert "`4/32` candidate runs" in user_prompt
    assert "Do not repeat unchanged `route_limit_seed_diversification`" in user_prompt
    assert "same-run candidate-vs-baseline seed comparison" in user_prompt
    assert "merely choosing a seed is not effect evidence" in user_prompt


def test_solver_design_target_intent_prompt_resolves_provider_from_ref() -> None:
    _system_blocks, user_prompt = _split_hypothesis_target_intent_context(
        {
            "problem_summary": "CVRP.",
            "research_surfaces": "solver_design [solver_design]",
            "objective_policy_guidance": "",
            "solver_mechanics": "",
            "champion_operators_code": "",
            "champion_stats": "{}",
            "operator_categories": "solver_design",
            "available_actions": "modify",
            "targetable_files": "policies/baseline_modules/scheduler.py",
            "active_problem_boundary_surfaces": "solver_design",
            # Agentic target-intent runs before final hypothesis binding, so it
            # also needs the durable ref when sanitizer drops provider objects.
            "solver_design_prompt_provider": {"sanitized": True},
            "solver_design_prompt_provider_ref": (
                "scion.problems.cvrp.solver_design_provider."
                "CvrpSolverDesignProvider"
            ),
        }
    )

    assert "Solver-design target-selection guidance" in user_prompt
    assert "Current CVRP target-selection guidance" in user_prompt
    assert "policies/baseline_modules/seed_selector.py" in user_prompt
    assert "successor36b completed" in user_prompt
    assert "`seed_post_optimization_selector`" in user_prompt
    assert "Do not prefer another unchanged seed_selector.py" in user_prompt
    assert "materially different from successor36b" in user_prompt
    assert "Scheduler.py edits" in user_prompt
    assert "minimal integration changes" in user_prompt
    assert "Current route-merge branch lesson" in user_prompt
    assert "`policies/baseline_modules/destroy_repair.py`" in user_prompt
    assert "`expand_screening` evidence (`10/3/19`" in user_prompt
    assert "later guarded/absorption follow-ups were no-effect or regressive" in user_prompt
    assert "Do not choose another route-merge absorption target by default" in user_prompt
    assert "new causal path beyond tested guarded-v2" in user_prompt
    assert "different provider-declared solver-design lever" in user_prompt
    assert "Current demand-slack branch lesson" in user_prompt
    assert "`demand_slack_regret_insertion`" in user_prompt
    assert "rejected the unchanged branch as quality regression" in user_prompt
    assert "Do not select another unchanged demand-slack/regret-insertion target" in user_prompt
    assert "explicit CMT2/CMT4 coverage" in user_prompt
    assert "Current post-demand-slack pivot lesson" in user_prompt
    assert "`local_search.py` / `cross_route_2opt_reconnect`" in user_prompt
    assert "`destroy_repair.py` / `cluster_biased_worst_removal`" in user_prompt
    assert "`8/16/8`, median delta `-0.5`" in user_prompt
    assert "do not fix CMT2/CMT4" not in user_prompt
    assert "did not fix CMT2/CMT4" in user_prompt
    assert "Current construction-pivot lesson" in user_prompt
    assert "`construction.py` / `route_limit_seed_diversification`" in user_prompt
    assert "screened as no-effect/negative (`1/3/28`)" in user_prompt
    assert "broader formal-surface activation" in user_prompt
    assert "same-run seed baseline" in user_prompt
    assert "fallback activation as effect" in user_prompt


def test_solver_design_target_intent_prompt_uses_research_surface_context() -> None:
    _system_blocks, user_prompt = _split_hypothesis_target_intent_context(
        {
            "problem_summary": "CVRP.",
            "research_surfaces": "solver_design [solver_design]",
            "objective_policy_guidance": "",
            "solver_mechanics": "",
            "champion_operators_code": "",
            "champion_stats": "{}",
            "operator_categories": "",
            "available_actions": "modify",
            "targetable_files": "policies/baseline_modules/destroy_repair.py",
            "active_problem_boundary_surfaces": "",
            "solver_design_prompt_provider": {"sanitized": True},
            "solver_design_prompt_provider_ref": (
                "scion.problems.cvrp.solver_design_provider."
                "CvrpSolverDesignProvider"
            ),
        }
    )

    assert "Solver-design target-selection guidance" in user_prompt
    assert "Current route-merge branch lesson" in user_prompt
    assert "Do not choose another route-merge absorption target by default" in user_prompt
    assert "different provider-declared solver-design lever" in user_prompt


def test_solver_design_code_prompt_omits_duplicate_champion_policy_bundle() -> None:
    client = CapturingToolClient()
    creative = CreativeLayer(client)

    creative.generate_code(
        {
            "problem_summary": "CVRP.",
            "research_surface_name": "solver_design",
            "research_surface_kind": "solver_design",
            "change_locus": "solver_design",
            "problem_prompt_provider": CvrpSolverDesignProvider(),
            "hypothesis_detail": "Implement a direct solver body.",
            "operator_interface_spec": "def solve(instance, rng, time_limit_sec, context)",
            "import_whitelist": "math, random, time",
            "champion_operators_code": (
                "### policies/search_policy.py\n"
                "def baseline_time_fraction(instance, time_limit_sec):\n"
                "    return 0.75\n"
            ),
            "target_file_code": (
                "def solve(instance, rng, time_limit_sec, context):\n"
                "    return None\n"
            ),
            "reference_operators": "",
            "editable_patterns": "policies/*.py",
            "frozen_patterns": "solver.py, adapter.py",
        }
    )

    rendered_system = json.dumps(client.system_blocks, sort_keys=True)
    rendered_prompt = "\n".join(client.prompts)

    assert "baseline_time_fraction" not in rendered_system
    assert "Approved Target File Current Content" in rendered_system
    assert "def solve(instance, rng, time_limit_sec, context):" in rendered_system
    assert "def solve(instance, rng, time_limit_sec, context):" not in rendered_prompt


def test_solver_design_code_prompt_enforces_compact_single_mechanism_scope() -> None:
    client = CapturingToolClient()
    creative = CreativeLayer(client)

    creative.generate_code(
        {
            "problem_summary": "CVRP.",
            "research_surface_name": "solver_design",
            "research_surface_kind": "solver_design",
            "change_locus": "solver_design",
            "problem_prompt_provider": CvrpSolverDesignProvider(),
            "code_generation_mode": "compact_timeout_retry",
            "hypothesis_detail": (
                "Implement a hybrid ALNS/VNS route-pool destroy-repair "
                "population portfolio."
            ),
            "agentic_code_scope_control": {
                "mode": "compact_timeout_retry",
                "detected_broad_terms": [
                    "hybrid",
                    "alns",
                    "destroy",
                    "repair",
                    "portfolio",
                ],
                "failure_detail": "code_generation_timeout",
            },
            "solver_design_api_manifest": (
                "Approved target_file: policies/baseline_modules/destroy_repair.py\n"
                "- policies/baseline_modules/construction.py: exports "
                "def _clarke_wright_savings(instance, target_routes); "
                "def _nearest_neighbor(instance)\n"
                "Target-specific rule for destroy_repair.py: scheduler.py "
                "may only import exact new symbols from .destroy_repair."
            ),
            "solver_design_branch_current_integration_files": (
                "### policies/baseline_algorithm.py\n"
                "Provenance: branch_workspace; readable=True\n"
                "```python\n"
                "def solve(instance, rng, time_limit_sec, context):\n"
                "    solver = _ALNSVNSSolver(context=context)\n"
                "    return solver.solve(instance, rng)\n"
                "```\n"
                "### policies/baseline_modules/scheduler.py\n"
                "Provenance: branch_workspace; readable=True\n"
                "```python\n"
                "class _ALNSVNSSolver:\n"
                "    def solve(self, instance, rng):\n"
                "        return None\n"
                "```"
            ),
            "operator_interface_spec": "def solve(instance, rng, time_limit_sec, context)",
            "import_whitelist": "math, random, time",
            "champion_operators_code": "",
            "target_file_code": (
                "def solve(instance, rng, time_limit_sec, context):\n"
                "    return None\n"
            ),
            "reference_operators": "",
            "editable_patterns": "policies/*.py",
            "frozen_patterns": "solver.py, adapter.py",
        }
    )

    rendered_system = "\n".join(
        block["text"] for blocks in client.system_blocks for block in blocks
    )
    rendered_prompt = "\n".join(client.prompts)

    assert "Compact Solver-Design Implementation Scope" in rendered_system
    assert "one primary mechanism" in rendered_system
    assert "around 180 lines or less" in rendered_system
    assert (
        "Do not implement more than two move/neighborhood families" in rendered_system
    )
    assert "target file should own the mechanism" in rendered_system
    assert "stable runtime contract" in rendered_system
    assert "Approved Target File Current Content" in rendered_system
    assert "Branch-Current Integration Files" in rendered_system
    assert "branch_workspace" in rendered_system
    assert "smallest necessary wiring edits" in rendered_system
    assert "Do not add new calls to `context.record_best_update`" in rendered_system
    assert "keep the approved mechanism id `route_merge_repair`" in rendered_system
    assert "_ALNSVNSSolver(configured_keywords).solve(instance, rng)" in rendered_system
    assert "scheduler as orchestration" in rendered_system
    assert "_ALNSVNSSolver.__init__(self, *" in rendered_system
    assert "_ALNSVNSSolver.solve(self, instance, rng)" in rendered_system
    assert "initial-state hooks inside scheduler methods" in rendered_system
    assert "zero iterations and zero move attempts" in rendered_system
    assert "_default_vns_operators()" in rendered_system
    assert "detached `_run`/`run`" in rendered_system
    assert "do not implement a full portfolio" in rendered_system
    assert "Active solver-design work belongs in" in rendered_system
    assert "policies/baseline_algorithm.py" in rendered_system
    assert "policies/baseline_modules/*.py" in rendered_system
    assert "policies/solver_algorithm.py" not in rendered_system
    assert "legacy compatibility plumbing" not in rendered_system
    assert "Deleted hooks" in rendered_system
    assert "not optimization directions" in rendered_system
    assert "explicitly repairs that compatibility hook" not in rendered_system
    assert "_Solution.routes" in rendered_system
    assert "not `list[list[int]]`" in rendered_system
    assert "from_public" in rendered_system
    assert "from_cvrp_solution" in rendered_system
    assert "context.make_solution(solution.routes_as_tuples())" in rendered_system
    assert "Do not edit `policies/baseline_modules/state.py`" in rendered_prompt
    assert "return complete contents" not in rendered_prompt
    assert "complete contents of the target algorithm module" not in rendered_prompt
    assert "default existing-file changes to typed `exact_replace` edits" in rendered_prompt
    assert "Do not use `full_file` just because" in rendered_prompt
    assert "Solver-Design Module API Manifest" in rendered_system
    assert "_clarke_wright_savings" in rendered_system
    assert "may only import exact new symbols from .destroy_repair" in rendered_system


def test_solver_design_code_prompt_default_stays_problem_agnostic() -> None:
    client = CapturingToolClient()
    creative = CreativeLayer(client)

    creative.generate_code(
        {
            "problem_summary": "Generic routing-like problem.",
            "research_surface_name": "solver_design",
            "research_surface_kind": "solver_design",
            "change_locus": "solver_design",
            "hypothesis_detail": "Implement a direct solver body.",
            "operator_interface_spec": "def solve(instance, rng, time_limit_sec, context)",
            "import_whitelist": "math, random, time",
            "champion_operators_code": "",
            "target_file_code": "def solve(instance, rng, time_limit_sec, context):\n    return None\n",
            "reference_operators": "",
            "editable_patterns": "policies/*.py",
            "frozen_patterns": "solver.py, adapter.py",
        }
    )

    rendered_system = "\n".join(
        block["text"] for blocks in client.system_blocks for block in blocks
    )

    assert "_ALNSVNSSolver" not in rendered_system
    assert "_Solution" not in rendered_system
    assert "CVRP" not in rendered_system


def test_code_prompt_renders_generic_telemetry_identity_rules() -> None:
    context = {
        "problem_summary": "Synthetic scheduling problem.",
        "research_surface_name": "solver_design",
        "research_surface_kind": "solver_design",
        "change_locus": "solver_design",
        "target_file": "solver_body.py",
        "action": "modify",
        "hypothesis_implementation_brief": {
            "hypothesis_text": "Add a declared bounded intensifier.",
            "target_file": "solver_body.py",
            "mechanism_changes": [
                {"id": "bounded_intensifier", "change_type": "add"}
            ],
            "expected_telemetry": {
                "activation": ["runtime_records.{mechanism}_selected"]
            },
        },
        "target_file_code": (
            "def solve(instance, rng, time_limit_sec, context):\n"
            "    return None\n"
        ),
        "operator_interface_spec": "def solve(instance, rng, time_limit_sec, context)",
        "import_whitelist": "math, random, time",
        "reference_operators": "",
        "editable_patterns": "solver_body.py",
        "frozen_patterns": "adapter.py",
        "active_subject_taxonomy": {
            "telemetry_identity_allowlist": ("setup_phase",)
        },
    }

    system_blocks, user_prompt = _split_code_context(context)
    rendered_system = "\n".join(block["text"] for block in system_blocks)

    assert "Telemetry Identity Rules" in user_prompt
    assert "`bounded_intensifier`" in user_prompt
    assert "new or increased mechanism telemetry" in user_prompt
    assert "approved/protected mechanism id(s)" in user_prompt
    assert (
        "Do not use a broad phase, baseline, structural, or aggregate id"
        in user_prompt
    )
    assert "mechanism evidence for this hypothesis" in user_prompt
    assert (
        "Adapter allowlist for such non-mechanism phase ids: `setup_phase`"
        in user_prompt
    )
    assert "diagnostic or accounting context only" in user_prompt
    assert "Telemetry Identity Rules" not in rendered_system
    assert "CVRP" not in user_prompt
    assert "VRP" not in user_prompt
    assert "route" not in user_prompt.lower()
    assert "vehicle" not in user_prompt.lower()
    assert "capacity" not in user_prompt.lower()
    assert "demand" not in user_prompt.lower()


def test_code_prompt_telemetry_identity_repair_blocks_baseline_id_reuse() -> None:
    context = {
        "problem_summary": "Synthetic scheduling problem.",
        "research_surface_name": "solver_design",
        "research_surface_kind": "solver_design",
        "change_locus": "solver_design",
        "target_file": "solver_body.py",
        "action": "modify",
        "hypothesis_implementation_brief": {
            "hypothesis_text": "Add a declared bounded signal.",
            "target_file": "solver_body.py",
            "mechanism_changes": [
                {"id": "approved_signal", "change_type": "add"}
            ],
        },
        "target_file_code": (
            "def solve(instance, rng, time_limit_sec, context):\n"
            "    return None\n"
        ),
        "operator_interface_spec": "def solve(instance, rng, time_limit_sec, context)",
        "import_whitelist": "math, random, time",
        "reference_operators": "",
        "editable_patterns": "solver_body.py",
        "frozen_patterns": "adapter.py",
        "previous_patch": {
            "file_path": "solver_body.py",
            "action": "modify",
            "code_content": (
                "def solve(instance, rng, time_limit_sec, context):\n"
                "    context.record_move('alns', attempted=1, accepted=0)\n"
                "    return None\n"
            ),
        },
        "agentic_code_self_check_feedback": {
            "passed": False,
            "failure_code": "code_stage_telemetry_identity_mismatch",
            "current_blocker": "telemetry_identity",
            "offending_telemetry_ids": ["alns"],
            "protected_mechanism_ids": ["approved_signal"],
            "telemetry_preservation_policy": "protected_mechanism_ids_only",
            "compact_offending_telemetry_usages": [
                {
                    "file": "solver_body.py",
                    "line": 2,
                    "helper": "record_move",
                    "mechanism_id": "alns",
                    "line_text": (
                        "context.record_move('alns', attempted=1, accepted=0)"
                    ),
                }
            ],
            "hard_constraints": [
                (
                    "Do not add or increase telemetry for baseline, "
                    "structural, aggregate, or unapproved mechanism ids."
                ),
                "Do not copy existing baseline telemetry as new evidence.",
            ],
        },
    }

    _system_blocks, user_prompt = _split_code_context(context)

    assert "Telemetry Identity Repair Blocker" in user_prompt
    assert "Approved/protected mechanism id(s): `approved_signal`" in user_prompt
    assert "Offending unapproved telemetry id(s): `alns`" in user_prompt
    assert "Do not add or increase telemetry for baseline" in user_prompt
    assert "Do not copy existing baseline telemetry as new evidence" in user_prompt
    assert "genuinely implements that mechanism" in user_prompt
    assert "Otherwise remove the newly added or increased telemetry call" in user_prompt
    assert "file=solver_body.py" in user_prompt
    assert "line=2" in user_prompt
    assert "helper=record_move" in user_prompt
    assert "mechanism_id=alns" in user_prompt
    assert "line_text=context.record_move('alns', attempted=1, accepted=0)" in user_prompt
    assert "context.record_move('alns', ...)" not in user_prompt


def test_solver_design_code_prompt_uses_synthetic_provider_guidance() -> None:
    client = CapturingToolClient()
    creative = CreativeLayer(client)

    creative.generate_code(
        {
            "problem_summary": "Synthetic packing problem.",
            "research_surface_name": "solver_design",
            "research_surface_kind": "solver_design",
            "change_locus": "solver_design",
            "problem_prompt_provider": SyntheticSolverDesignPromptProvider(),
            "code_generation_mode": "compact_solver_design",
            "hypothesis_detail": "Implement a synthetic-wide beam update.",
            "operator_interface_spec": "def solve(instance, rng, time_limit_sec, context)",
            "import_whitelist": "math, random, time",
            "champion_operators_code": "",
            "target_file_code": (
                "def solve(instance, rng, time_limit_sec, context):\n"
                "    return None\n"
            ),
            "reference_operators": "",
            "editable_patterns": "solver_body.py",
            "frozen_patterns": "adapter.py",
        }
    )

    rendered_system = "\n".join(
        block["text"] for blocks in client.system_blocks for block in blocks
    )
    rendered_prompt = "\n".join(client.prompts)
    rendered = rendered_system + rendered_prompt

    assert "SYNTHETIC_CODE_RULE" in rendered_system
    assert "SYNTHETIC_SCOPE" in rendered_system
    assert "synthetic-wide" in rendered_system
    assert "SYNTHETIC_USER_CONSTRAINT" in rendered_prompt
    assert "_ALNSVNSSolver" not in rendered
    assert "CvrpSolution" not in rendered
    assert "ALNS" not in rendered
    assert "VNS" not in rendered


def test_prompt_manifest_omits_live_solver_design_provider_handle() -> None:
    prompt_context = {
        "solver_design_prompt_provider": SyntheticSolverDesignPromptProvider(),
        "solver_design_prompt_provider_ref": (
            "tests.SyntheticSolverDesignPromptProvider"
        ),
        "hypothesis_detail": "Synthetic provider handle should not persist.",
    }
    system_blocks, user_prompt = _split_code_context(prompt_context)
    manifest = build_api_visible_prompt_manifest(
        session_id="s1",
        phase="draft_patch",
        call_kind="code",
        prompt_context=prompt_context,
        observations=[],
        call_index=1,
        system_blocks=system_blocks,
        user_prompt=user_prompt,
    )

    assert "solver_design_prompt_provider" not in manifest["section_names"]
    assert "solver_design_prompt_provider_ref" in manifest["raw_context_audit"][
        "top_level_keys"
    ]


def test_code_phase_renders_compact_receipts_for_read_observations() -> None:
    read_observation = ProposalObservation(
        observation_id="map-read-1",
        session_id="session-1",
        tool_name="context.read_active_solver_map",
        tool_call_id="call-1",
        observation_type="tool_result",
        summary="Read active solver map.",
        structured_payload={
            "subject_id": "subject-1",
            "snapshot_digest": "snapshot-1",
            "read_receipt": {
                "tool_name": "context.read_active_solver_map",
                "target_id": "solver-map",
                "digest": "receipt-digest-1",
                "snapshot_digest": "snapshot-1",
            },
            "algorithm_slices": [{"slice_id": "slice-a"}],
        },
    )
    prompt_observations = [
        _code_observation_prompt_payload(observation)
        for observation in _code_prompt_observations([read_observation])
    ]
    context = {
        "problem_summary": "Synthetic problem.",
        "research_surface_name": "solver_design",
        "research_surface_kind": "solver_design",
        "change_locus": "solver_design",
        "target_file": "solver_body.py",
        "action": "modify",
        "hypothesis_text": "Modify solver body.",
        "target_file_code": "File: solver_body.py\n```python\ndef solve():\n    pass\n```\n",
        "operator_interface_spec": "def solve()",
        "import_whitelist": "math",
        "editable_patterns": "solver_body.py",
        "frozen_patterns": "adapter.py",
        "agentic_tool_observations": prompt_observations,
    }

    system_blocks, user_prompt = _split_code_context(context)
    manifest = build_api_visible_prompt_manifest(
        session_id="session-read-receipt",
        phase="draft_patch",
        call_kind="code",
        prompt_context=context,
        observations=[read_observation],
        call_index=1,
        system_blocks=system_blocks,
        user_prompt=user_prompt,
    )

    assert "file_read_receipts" in user_prompt
    assert "context.read_active_solver_map" in user_prompt
    assert "receipt-digest-1" in user_prompt
    ledger_item = manifest["tool_result_visibility_ledger"][0]
    assert ledger_item["rendered_visibility_flag"] is True
    assert ledger_item["omitted"] is False


def test_code_phase_projects_full_algorithm_file_source_to_96k_window() -> None:
    tail_marker = "TAIL_MARKER_VISIBLE_AFTER_24K"
    source = "def solve(instance, rng, time_limit_sec, context):\n" + (
        "# source filler\n" * 3800
    ) + tail_marker
    assert len(source) > 24000
    assert len(source) < 96000
    read_observation = ProposalObservation(
        observation_id="full-source-read",
        session_id="session-full-source",
        tool_name="context.read_algorithm_file",
        tool_call_id="call-full-source",
        observation_type="algorithm_file",
        summary="Returned full algorithm source.",
        structured_payload={
            "surface": "solver_design",
            "file_path": "policies/baseline_algorithm.py",
            "readable": True,
            "source": "champion_snapshot",
            "content_preview": source,
            "truncated": False,
            "size_chars": len(source),
            "max_chars": 96000,
        },
    )
    prompt_observations = [
        _code_observation_prompt_payload(observation)
        for observation in _code_prompt_observations([read_observation])
    ]
    compact_source = prompt_observations[0]["structured_payload"]["content_preview"]
    context = {
        "problem_summary": "Synthetic problem.",
        "research_surface_name": "solver_design",
        "research_surface_kind": "solver_design",
        "change_locus": "solver_design",
        "target_file": "policies/baseline_algorithm.py",
        "action": "modify",
        "hypothesis_text": "Modify solver body.",
        "target_file_code": "File: policies/baseline_algorithm.py\n```python\n"
        "def solve():\n    pass\n```\n",
        "operator_interface_spec": "def solve()",
        "import_whitelist": "math",
        "editable_patterns": "policies/baseline_algorithm.py",
        "frozen_patterns": "adapter.py",
        "agentic_tool_observations": prompt_observations,
    }

    system_blocks, user_prompt = _split_code_context(context)
    rendered = "\n".join(block["text"] for block in system_blocks) + "\n" + user_prompt

    assert len(compact_source) == len(source)
    assert tail_marker in compact_source
    assert "Solver-Design Full Algorithm File Reads" in rendered
    assert tail_marker in rendered


def test_code_phase_projects_algorithm_symbol_source_to_96k_window() -> None:
    tail_marker = "SYMBOL_TAIL_VISIBLE_AFTER_12K"
    source = "def improve(instance, rng, context):\n" + (
        "    score += 1\n" * 1500
    ) + tail_marker
    assert len(source) > 12000
    assert len(source) < 96000
    read_observation = ProposalObservation(
        observation_id="symbol-source-read",
        session_id="session-symbol-source",
        tool_name="context.read_algorithm_symbol",
        tool_call_id="call-symbol-source",
        observation_type="algorithm_symbol",
        summary="Returned algorithm symbol source.",
        structured_payload={
            "surface": "solver_design",
            "file_path": "policies/baseline_algorithm.py",
            "symbol": "improve",
            "readable": True,
            "source": "champion_snapshot",
            "content_preview": source,
            "truncated": False,
            "max_chars": 96000,
        },
    )
    prompt_observations = [
        _code_observation_prompt_payload(observation)
        for observation in _code_prompt_observations([read_observation])
    ]
    compact_source = prompt_observations[0]["structured_payload"]["content_preview"]
    context = {
        "problem_summary": "Synthetic problem.",
        "research_surface_name": "solver_design",
        "research_surface_kind": "solver_design",
        "change_locus": "solver_design",
        "target_file": "policies/baseline_algorithm.py",
        "action": "modify",
        "hypothesis_text": "Modify solver body.",
        "target_file_code": "File: policies/baseline_algorithm.py\n```python\n"
        "def solve():\n    pass\n```\n",
        "operator_interface_spec": "def solve()",
        "import_whitelist": "math",
        "editable_patterns": "policies/baseline_algorithm.py",
        "frozen_patterns": "adapter.py",
        "agentic_tool_observations": prompt_observations,
    }

    system_blocks, user_prompt = _split_code_context(context)
    rendered = "\n".join(block["text"] for block in system_blocks) + "\n" + user_prompt

    assert len(compact_source) == len(source)
    assert tail_marker in compact_source
    assert "Solver-Design Algorithm Symbol Reads" in rendered
    assert tail_marker in rendered
    assert "Solver-Design Algorithm Symbol Reads" in system_blocks[0]["text"]
    assert tail_marker in system_blocks[0]["text"]


def test_latest_preview_repair_feedback_preserves_retry_diagnostics() -> None:
    previous_patch = {
        "file_path": "solver_body.py",
        "action": "modify",
        "old_string": "old implementation",
        "new_string": "new implementation",
    }
    context = {
        "problem_summary": "Synthetic problem.",
        "research_surface_name": "solver_design",
        "research_surface_kind": "solver_design",
        "change_locus": "solver_design",
        "target_file": "solver_body.py",
        "action": "modify",
        "hypothesis_text": "Modify solver body.",
        "target_file_code": "File: solver_body.py\n```python\ndef solve():\n    pass\n```\n",
        "operator_interface_spec": "def solve()",
        "import_whitelist": "math",
        "editable_patterns": "solver_body.py",
        "frozen_patterns": "adapter.py",
        "previous_patch": previous_patch,
        "agentic_preview_feedback": {
            "observation_id": "contract-1",
            "tool_name": "proposal.contract_preview",
            "summary": "Contract preview failed.",
            "structured_payload": {
                "passed": False,
                "failure_code": "contract_preview_failed",
                "root_cause": "Wrong object API used for score update.",
                "gate_id": "C7_interface",
                "failing_paths": ["solver_body.py"],
                "previous_patch_summary": previous_patch,
                "raw_artifact": "x" * 80000,
            },
        },
    }

    _system_blocks, user_prompt = _split_code_context(context)

    assert "Wrong object API used for score update." in user_prompt
    assert "C7_interface" in user_prompt
    assert "solver_body.py" in user_prompt
    assert "old_string_digest" in user_prompt
    assert "raw_artifact" not in user_prompt
    assert "<truncated agentic context>" not in user_prompt


def test_create_new_target_visibility_ledger_marks_create_mode() -> None:
    context = {
        "problem_summary": "Synthetic problem.",
        "research_surface_name": "solver_design",
        "research_surface_kind": "solver_design",
        "change_locus": "solver_design",
        "target_file": "new_solver_body.py",
        "action": "create_new",
        "hypothesis_text": "Create a new solver body.",
        "target_file_code": "(new file - will be created)",
        "operator_interface_spec": "def solve()",
        "import_whitelist": "math",
        "editable_patterns": "*.py",
        "frozen_patterns": "adapter.py",
    }
    system_blocks, user_prompt = _split_code_context(context)

    manifest = build_api_visible_prompt_manifest(
        session_id="session-create-new",
        phase="draft_patch",
        call_kind="code",
        prompt_context=context,
        observations=[],
        call_index=1,
        system_blocks=system_blocks,
        user_prompt=user_prompt,
    )

    target = manifest["code_file_visibility_ledger"]["target_file"]
    assert target["file_path"] == "new_solver_body.py"
    assert target["target_file_create_mode"] is True
    assert target["visibility_status"] == "create_new_target_no_current_source"
    assert target["prompt_visibility_status"] == "create_new_target_no_current_source"
    assert target["source_status"] == "new_file"
    assert target["source_provenance"] == "new_file_placeholder"


def test_latest_preview_failure_detail_uses_latest_preview_not_stale_smoke() -> None:
    smoke = ProposalObservation(
        observation_id="smoke-1",
        session_id="session-1",
        tool_name="proposal.algorithm_smoke",
        tool_call_id="call-1",
        observation_type="tool_result",
        summary="Algorithm smoke failed.",
        structured_payload={
            "passed": False,
            "runtime_smoke": {
                "issues": ["old runtime failure"],
            },
        },
    )
    contract = ProposalObservation(
        observation_id="contract-1",
        session_id="session-1",
        tool_name="proposal.contract_preview",
        tool_call_id="call-2",
        observation_type="tool_result",
        summary="Contract preview failed.",
        structured_payload={
            "passed": False,
            "issue_summary": "new object model API misuse",
        },
    )

    detail = _latest_preview_failure_detail([smoke, contract])

    assert detail is not None
    assert "contract preview did not pass" in detail
    assert "new object model API misuse" in detail
    assert "old runtime failure" not in detail


def test_solver_run_failure_detail_includes_category_exit_and_stdout() -> None:
    detail = _solver_run_failure_detail(
        RunResult(
            success=False,
            exit_code=-9,
            stdout="last solver line",
            stderr="",
            elapsed_ms=12034,
            output_path=None,
            error_category="timeout",
        )
    )

    assert "solver run failed" in detail
    assert "exit_code=-9" in detail
    assert "error_category=timeout" in detail
    assert "elapsed_ms=12034" in detail
    assert "stdout=last solver line" in detail


def test_compact_algorithm_smoke_observation_preserves_pass_signal() -> None:
    observation = ProposalObservation(
        observation_id="smoke-1",
        session_id="session-1",
        tool_name="proposal.algorithm_smoke",
        tool_call_id="tool-10",
        observation_type="algorithm_smoke",
        summary="Algorithm smoke passed on tainted synthetic preview.",
        structured_payload={
            "passed": True,
            "non_promotional": True,
            "tainted_debug": True,
            "workspace_materialized": False,
            "verification_run": False,
            "protocol_run": False,
            "decision_run": False,
            "hypothesis": {
                "passed": True,
                "hypothesis_text": "x" * 8000,
                "contract": {"passed": True, "check_count": 6},
                "checks": [{"name": "C2_locus", "passed": True}],
            },
            "patch": {
                "passed": True,
                "code_content": "x" * 48000,
                "contract": {"passed": True, "check_count": 10},
                "checks": [{"name": "C7_interface", "passed": True}],
                "problem_preview": {
                    "passed": True,
                    "surface": "solver_design",
                    "checks": [{"name": "preview", "passed": True}],
                    "workspace_materialized": False,
                },
            },
            "problem_preview": {
                "passed": True,
                "surface": "solver_design",
                "checks": [{"name": "preview", "passed": True}],
                "workspace_materialized": False,
            },
            "runtime_smoke": {
                "passed": False,
                "runtime_smoke_run": True,
                "workspace_materialized": True,
                "case": "controlled/data/canary.vrp",
                "seed": 77,
                "case_count": 1,
                "issues": ["runtime audit failed"],
                "runtime_audit_failure": {
                    "error_category": "solver_algorithm_errors",
                    "detail": "'_Route' object is not subscriptable",
                    "solver_algorithm_errors": 1,
                    "solver_algorithm_events": [
                        {"type": "error", "message": "'_Route' object is not subscriptable"}
                    ],
                },
                "runtime": {
                    "solver_algorithm_loaded": True,
                    "solver_algorithm_active": True,
                    "solver_algorithm_errors": 1,
                    "solver_algorithm_events": [
                        {"type": "error", "message": "'_Route' object is not subscriptable"}
                    ],
                },
                "micro_benchmark": {
                    "non_promotional": True,
                    "tainted_debug": True,
                    "comparable_cases": 1,
                    "wins": 0,
                    "losses": 1,
                    "ties": 0,
                    "results": [
                        {
                            "label": "canary",
                            "case": "controlled/data/canary.vrp",
                            "comparison": "loss",
                            "delta": -3.0,
                            "decisive_metric": "total_distance",
                            "runtime_delta_ms": -100,
                        }
                    ],
                },
                "run": {"success": True, "detail": "solver smoke completed"},
            },
        },
    )

    compact = _compact_algorithm_smoke_observation(observation)

    assert compact is not None
    assert compact.is_error is False
    assert _json_size(_observation_prompt_payload(compact)) < 2200
    assert compact.structured_payload["passed"] is True
    assert compact.structured_payload["patch"]["contract"]["check_count"] == 10
    assert compact.structured_payload["problem_preview"]["passed"] is True
    assert compact.structured_payload["runtime_smoke"]["runtime"][
        "solver_algorithm_errors"
    ] == 1
    assert "_Route" in compact.structured_payload["runtime_smoke"][
        "runtime_audit_failure"
    ]["detail"]
    assert compact.structured_payload["runtime_smoke"]["micro_benchmark"][
        "losses"
    ] == 1
    assert compact.structured_payload["compact_due_to_budget"] is True


def test_code_prompt_observation_payload_preserves_algorithm_smoke_runtime_detail() -> None:
    observation = ProposalObservation(
        observation_id="smoke-runtime",
        session_id="session-1",
        tool_name="proposal.algorithm_smoke",
        tool_call_id="tool-12",
        observation_type="algorithm_smoke",
        summary="Algorithm smoke found issues.",
        structured_payload={
            "passed": False,
            "failure_code": "algorithm_smoke_runtime_failure",
            "runtime_smoke": {
                "passed": False,
                "runtime_smoke_run": True,
                "case": "controlled/data/canary.vrp",
                "issues": ["solver runtime audit reported solver_algorithm_errors=1"],
                "runtime_audit_failure": {
                    "detail": "solver runtime audit reported solver_algorithm_errors=1",
                    "solver_algorithm_errors": 1,
                    "solver_algorithm_events": [
                        {
                            "type": "error",
                            "message": "NameError: DESTROY_RATIO_LOW is not defined",
                        }
                    ],
                },
                "runtime": {
                    "solver_algorithm_errors": 1,
                    "solver_algorithm_events": [
                        {
                            "type": "error",
                            "message": "NameError: DESTROY_RATIO_LOW is not defined",
                        }
                    ],
                },
                "run": {
                    "success": True,
                    "detail": "solver smoke completed",
                    "stderr": "",
                },
            },
        },
    )

    selected = _code_prompt_observations([observation])
    compact = _code_observation_prompt_payload(selected[0])
    detail = _algorithm_smoke_failure_detail([observation])
    rendered = json.dumps(compact, sort_keys=True, default=str)

    assert selected == [observation]
    assert "DESTROY_RATIO_LOW" in rendered
    assert detail is not None
    assert "algorithm_smoke_runtime_failure" in detail
    assert "DESTROY_RATIO_LOW" in detail


def test_algorithm_smoke_failure_detail_includes_repair_guidance() -> None:
    observation = ProposalObservation(
        observation_id="smoke-runtime",
        session_id="session-1",
        tool_name="proposal.algorithm_smoke",
        tool_call_id="tool-12",
        observation_type="algorithm_smoke",
        summary="Algorithm smoke found issues.",
        structured_payload={
            "passed": False,
            "runtime_smoke": {
                "passed": False,
                "issues": ["solver runtime audit reported solver_algorithm_errors=1"],
                "runtime": {
                    "solver_algorithm_errors": 1,
                    "solver_algorithm_events": [
                        {
                            "policy": "policies/baseline_algorithm.py",
                            "status": "error",
                            "detail": "solve failed: '_Solution' object has no attribute '_instance'",
                        }
                    ],
                },
                "repair_guidance": [
                    "Specific fix: replace solution._instance with solution.instance.",
                    "_Solution.routes contains _Route objects.",
                ],
            },
        },
    )

    detail = _algorithm_smoke_failure_detail([observation])

    assert detail is not None
    assert "_Solution" in detail
    assert "solution.instance" in detail


def test_code_retry_prompt_keeps_actionable_delta_telemetry_feedback() -> None:
    expected_pattern = (
        "context.record_move('best_delta_probe', attempted=1, accepted=1, "
        "delta=<positive_improvement_delta>, best_improved=True)"
    )
    action = {
        "failure_code": "DECLARED_MECHANISM_DELTA_EVIDENCE_MISSING",
        "failure_mechanism_id": "best_delta_probe",
        "mechanism_id": "best_delta_probe",
        "category": "effect",
        "delta_valued_fields": [
            "solver_algorithm_phase_best_delta.best_delta_probe"
        ],
        "expected_call_pattern": expected_pattern,
        "invalid_call_summaries": [
            {
                "file_path": "policies/baseline_algorithm.py",
                "mechanism_id": "best_delta_probe",
                "helper": "context.record_move",
                "call": (
                    "context.record_move('best_delta_probe', attempted=1, "
                    "accepted=1, delta=None, best_improved=1)"
                ),
                "delta_status": "none",
                "reason": "delta=None does not populate delta-valued effect telemetry.",
            }
        ],
        "declaration_alternative": (
            "If this mechanism is intended to prove only activity or activation, "
            "repair the hypothesis expected_telemetry or mechanism declaration."
        ),
    }
    observation = ProposalObservation(
        observation_id="smoke-delta",
        session_id="session-1",
        tool_name="proposal.algorithm_smoke",
        tool_call_id="tool-13",
        observation_type="algorithm_smoke",
        summary="Algorithm smoke found issues.",
        structured_payload={
            "passed": False,
            "actionable_telemetry_feedback": [action],
            "telemetry_static_preview": {
                "passed": False,
                "issue_codes": ["DECLARED_MECHANISM_DELTA_EVIDENCE_MISSING"],
                "actionable_telemetry_feedback": [action],
            },
            "runtime_smoke": {
                "passed": False,
                "issues": ["x" * 20000],
            },
        },
    )

    compact = _compact_algorithm_smoke_observation(observation)
    assert compact is not None
    assert _json_size(_observation_prompt_payload(compact)) < _json_size(
        _observation_prompt_payload(observation)
    )
    compact_payload = compact.structured_payload
    assert compact_payload["actionable_telemetry_feedback"][0][
        "expected_call_pattern"
    ] == expected_pattern
    assert "delta=None" in compact_payload["actionable_telemetry_feedback"][0][
        "invalid_call_summaries"
    ][0]["call"]

    prior_failure = _algorithm_smoke_failure_detail([compact])
    prompt_context = {
        "problem_summary": "Synthetic problem.",
        "solver_mechanics": "Use bounded solver-design smoke.",
        "research_surface_name": "solver_design",
        "research_surface_kind": "solver_design",
        "change_locus": "solver_design",
        "operator_interface_spec": "def solve(instance, rng, time_limit_sec, context)",
        "import_whitelist": "math, time",
        "hypothesis_detail": "Add best_delta_probe.",
        "target_file": "policies/baseline_algorithm.py",
        "target_file_code": "def solve(instance, rng, time_limit_sec, context): pass",
        "reference_operators": "",
        "editable_patterns": "policies/*.py",
        "frozen_patterns": "vrp/",
        "prior_code_failure": prior_failure,
        "previous_patch": {
            "file_path": "policies/baseline_algorithm.py",
            "action": "modify",
            "code_content": (
                "def solve(instance, rng, time_limit_sec, context):\n"
                "    context.record_move('best_delta_probe', attempted=1, "
                "accepted=1, delta=None, best_improved=1)\n"
            ),
        },
        "agentic_preview_feedback": _observation_prompt_payload(compact),
        "agentic_tool_observations": [_code_observation_prompt_payload(compact)],
    }

    _system_blocks, user_prompt = _split_code_context(prompt_context)

    assert "Latest Preview Repair Feedback" in user_prompt
    assert expected_pattern in user_prompt
    assert "delta=None" in user_prompt
    assert "expected_telemetry" in user_prompt
    assert "not fabricate" in user_prompt


def test_hypothesis_schema_retry_prompt_preserves_allowed_telemetry_template() -> None:
    activation_fields = [
        f"solver_runtime_probe_{idx}.declared_probe" for idx in range(9)
    ]
    effect_fields = [
        f"solver_effect_probe_{idx}.declared_probe" for idx in range(7)
    ]
    feedback = {
        "attempt": 1,
        "attempt_kind": "schema_accounting_repair",
        "repair_classification": "telemetry_schema_accounting_repair",
        "failure_code": "C11_expected_telemetry",
        "reason": "expected_telemetry.activation used a broad aggregate label",
        "reason_full": (
            "expected_telemetry.activation used a broad aggregate label; "
            "exact corrective template requires declared_probe activation "
            "fields without changing target_file, action, or mechanism id."
        ),
        "allowed_top_level_categories": [
            "activation",
            "activity",
            "budget",
            "effect",
        ],
        "exact_allowed_top_level_categories": [
            "activation",
            "activity",
            "budget",
            "effect",
        ],
        "declared_mechanism_ids": ["declared_probe"],
        "protected_mechanism_ids": ["declared_probe"],
        "template_mechanism_ids": ["declared_probe"],
        "legal_mechanism_id_policy": (
            "Expected telemetry paths for mechanism-specific evidence must "
            "use the exact declared/protected mechanism id."
        ),
        "allowed_expected_telemetry_template": {
            "selected_surface": "solver_design",
            "mechanism_id": "declared_probe",
            "mechanism_ids": ["declared_probe"],
            "template_is_exact": True,
            "template_truncated": False,
            "expected_telemetry": {
                "activation": activation_fields,
                "effect": effect_fields,
            },
        },
        "allowed_expected_telemetry_template_full": {
            "selected_surface": "solver_design",
            "mechanism_id": "declared_probe",
            "mechanism_ids": ["declared_probe"],
            "template_is_exact": True,
            "template_truncated": False,
            "expected_telemetry": {
                "activation": activation_fields,
                "effect": effect_fields,
                "budget": ["solver_runtime_budget.declared_probe"],
            },
        },
        "preserve_hypothesis": {
            "target_file": "policies/synthetic.py",
            "mechanism_changes": [
                {"id": "declared_probe", "change_type": "modify"}
            ],
        },
        "retry_constraint": (
            "Repair only expected_telemetry/schema fields for the same "
            "hypothesis."
        ),
    }

    _system_blocks, user_prompt = _split_hypothesis_context(
        {
            "problem_summary": "Synthetic problem.",
            "champion_operators_code": "def solve(): pass",
            "champion_stats": "{}",
            "experiment_history": "",
            "blacklist_summary": "",
            "active_hyp_summary": "",
            "sibling_summary": "",
            "operator_categories": "solver_design",
            "agentic_hypothesis_retry_attempt": 2,
            "agentic_hypothesis_preview_rejections": [feedback],
        }
    )

    assert "Hypothesis Schema/Telemetry Retry Feedback" in user_prompt
    assert "schema/accounting repair" in user_prompt
    assert "... <truncated agentic context>" not in user_prompt
    assert "schema_accounting_repair" in user_prompt
    assert "template_truncated" in user_prompt
    assert "solver_runtime_budget.declared_probe" in user_prompt
    assert "exact corrective template requires declared_probe activation" in user_prompt
    for field in activation_fields + effect_fields:
        assert field in user_prompt


def test_hypothesis_launch_focus_required_mechanism_retry_prompt_keeps_required_id(
) -> None:
    required_id = "large_instance_intra_route_two_opt_seed"
    feedback = {
        "attempt": 2,
        "attempt_kind": "launch_focus_required_mechanism_repair",
        "repair_classification": "launch_focus_required_mechanism_repair",
        "failure_code": "launch_research_focus_required_mechanism",
        "reason": (
            "required_mechanism_ids=['large_instance_intra_route_two_opt_seed']; "
            "candidate_mechanism_ids=['bounded_two_opt_probe']"
        ),
        "required_mechanism_ids": [required_id],
        "candidate_mechanism_ids": ["bounded_two_opt_probe"],
        "candidate_target_file": "policies/baseline_modules/local_search.py",
        "allowed_repair_shape": {
            "mechanism_changes": [
                {"id": required_id, "change_type": "modify"}
            ],
        },
        "retry_constraint": (
            "Rewrite the hypothesis around the prepared required mechanism id "
            "'large_instance_intra_route_two_opt_seed'; put that exact id in "
            "mechanism_changes."
        ),
    }

    _system_blocks, user_prompt = _split_hypothesis_context(
        {
            "problem_summary": "CVRP.",
            "champion_operators_code": "def solve(): pass",
            "champion_stats": "{}",
            "experiment_history": "",
            "blacklist_summary": "",
            "active_hyp_summary": "",
            "sibling_summary": "",
            "operator_categories": "solver_design",
            "agentic_hypothesis_retry_attempt": 3,
            "agentic_hypothesis_preview_retry_rule": (
                "LAUNCH-FOCUS REQUIRED-MECHANISM RETRY."
            ),
            "agentic_hypothesis_preview_rejections": [feedback],
        }
    )

    assert "launch_focus_required_mechanism_repair" in user_prompt
    assert "required_mechanism_ids override the prior mechanism id" in user_prompt
    assert required_id in user_prompt
    assert "bounded_two_opt_probe" in user_prompt
    assert "allowed_repair_shape" in user_prompt


def test_algorithm_smoke_compacts_to_fit_remaining_observation_budget(
    tmp_path: Path,
) -> None:
    context = _context(tmp_path, policy=_tool_enabled_policy())
    config = AgenticToolLoopConfig(max_observation_chars=64000)
    state = AgenticProposalSessionState(
        session_id="session-smoke-budget",
        campaign_id="camp-1",
        branch_id="branch-1",
        observation_chars_used=62400,
    )
    session = AgenticProposalSession(
        FakeCreative(),
        tool_registry=ProposalToolRegistry.default_read_only(),
        tool_loop_config=config,
    )
    observation = ProposalObservation(
        observation_id="smoke-2",
        session_id=state.session_id,
        tool_name="proposal.algorithm_smoke",
        tool_call_id="tool-11",
        observation_type="algorithm_smoke",
        summary="Algorithm smoke passed on tainted synthetic preview.",
        structured_payload={
            "passed": True,
            "non_promotional": True,
            "tainted_debug": True,
            "workspace_materialized": False,
            "verification_run": False,
            "protocol_run": False,
            "decision_run": False,
            "patch": {
                "passed": True,
                "code_content": "x" * 48000,
                "contract": {"passed": True, "check_count": 10},
                "problem_preview": {"passed": True, "surface": "solver_design"},
            },
            "problem_preview": {"passed": True, "surface": "solver_design"},
        },
    )

    compact = session._enforce_observation_budget(context, state, observation)

    assert compact.is_error is False
    assert compact.failure_code is None
    assert compact.structured_payload["passed"] is True
    assert compact.structured_payload["compact_due_to_budget"] is True
    assert _json_size(_observation_prompt_payload(compact)) <= (
        config.max_observation_chars - state.observation_chars_used
    )
