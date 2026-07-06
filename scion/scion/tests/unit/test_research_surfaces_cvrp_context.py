from __future__ import annotations

import json

from scion.core.models import (
    Branch,
    BranchState,
    ChampionState,
    HypothesisProposal,
    MechanismChange,
)
from scion.problem.bridge import legacy_problem_spec_from_v1, load_problem_spec_v1_from_yaml
from scion.problems.cvrp.adapter import CvrpAdapter
from scion.proposal.context_manager import ContextManager
from scion.proposal.engine import _split_code_context, _split_hypothesis_context
from scion.proposal.prompt_manifest import build_api_visible_prompt_manifest
from scion.tests.unit.research_surface_helpers import _CVRP_ROOT


def test_cvrp_hypothesis_context_exposes_only_active_solver_design() -> None:
    spec_v1 = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    legacy = legacy_problem_spec_from_v1(spec_v1)
    champion = ChampionState(
        version=1,
        operator_pool={},
        solver_config_hash="h",
        code_snapshot_path=str(_CVRP_ROOT),
        code_snapshot_hash="h",
    )
    branch = Branch(
        branch_id="b1",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="h",
    )

    ctx = ContextManager(adapter=CvrpAdapter(spec_v1)).build_hypothesis_context(
        branch=branch,
        champion=champion,
        problem_spec=legacy,
        active_hypotheses=[],
        blacklist=[],
    )
    system_blocks, user_prompt = _split_hypothesis_context(ctx)
    prompt_text = "\n".join(block["text"] for block in system_blocks) + user_prompt

    assert ctx["operator_categories"] == "solver_design"
    assert ctx["active_problem_boundary_surfaces"] == "solver_design"
    assert "solver_design [solver_design]" in prompt_text
    assert "adaptive embedded-VNS share-70 line" in prompt_text
    assert "simple share70 cap/rescue variants are rejected" in prompt_text
    assert "CVRP_MDE_EXCEEDS_PRACTICAL_DELTA" in prompt_text
    assert "large_instance_intra_route_two_opt_seed" in prompt_text
    assert "deadline-aware bounded" in prompt_text
    assert "UNBOUNDED_TWO_OPT_DEFAULT_REJECT" in prompt_text
    assert "v04-vrp-large-instance-two-opt-seed-evidence-20260618.md" in prompt_text
    assert "launch_research_focus" not in prompt_text
    assert "proposal-only" in prompt_text
    assert "Do not hardcode case ids, BKS values, seeds, or split membership" in prompt_text
    assert "policies/baseline_algorithm.py" in ctx["targetable_files"]
    assert "policies/baseline_modules/*.py" in ctx["targetable_files"]
    assert "policies/search_policy.py" not in ctx["targetable_files"]
    assert "policies/solver_algorithm.py" not in ctx["targetable_files"]
    assert "policies/main_search_strategy.py" not in ctx["targetable_files"]
    assert "route_local [operator]" not in prompt_text
    assert "search_policy [policy]" not in prompt_text
    assert "algorithm_blueprint [config]" not in prompt_text
    assert "interface.required_functions: solve" in prompt_text
    assert "solver_algorithm_loaded" in prompt_text


def test_cvrp_hypothesis_context_uses_prepared_launch_research_focus(
    tmp_path,
    monkeypatch,
) -> None:
    manifest_path = tmp_path / "prepared_run_manifest.v1.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "scion.launcher_prepared_run_manifest.v1",
                "problem_family": "cvrp",
                "analysis_intent": "Prepared CVRP post-pivot continuation.",
                "acceptance_focus": [
                    "Check the research_focus default-avoid list before launch."
                ],
                "research_focus": {
                    "schema_version": "scion.cvrp_research_focus.v1",
                    "scope": "report_only_prepared_handoff",
                    "next_required_direction": (
                        "First attempt large_instance_intra_route_two_opt_seed."
                    ),
                    "required_mechanism_ids": [
                        "large_instance_intra_route_two_opt_seed",
                    ],
                    "target_intent_required_mechanism_ids": [],
                    "successor40_reviewed_evidence": {
                        "mechanism_id": "bounded_two_for_one_exchange",
                        "mechanism_family": "bounded_local_search_variant",
                        "target_file": "policies/baseline_modules/local_search.py",
                        "reviewed_rule": (
                            "Do not continue unchanged two-for-one exchange "
                            "or threshold/gating variants."
                        ),
                    },
                    "required_evidence": [
                        "material causal-path difference from reviewed bounded_two_for_one_exchange",
                        "direct mechanism objective-effect evidence",
                        (
                            "CMT2/CMT4 case-level total_distance deltas or "
                            "split caveat"
                        ),
                    ],
                    "current_question": (
                        "Select a materially different CVRP solver-design mechanism."
                    ),
                    "route_merge_exception_rule": (
                        "Only continue route_merge_repair with a new causal path."
                    ),
                    "construction_seed_rule": (
                        "Require same-run seed baseline for seed-pool claims."
                    ),
                    "default_avoid_directions": [
                        "route-merge absorption",
                        "route-limit seed diversification",
                    ],
                    "measurable_opportunity_classes": [
                        "bounded_local_search_variant",
                        "destroy_repair_selection",
                    ],
                    "large_instance_two_opt_constraints": {
                        "schema_version": (
                            "scion.cvrp_large_instance_two_opt_constraints.v1"
                        ),
                        "scope": "proposal_only_prepared_handoff",
                        "seed_report": "seed-report.md",
                        "proposal_visibility_only": True,
                        "decision_features_excluded": True,
                        "implementation_constraints": [
                            "derive a deadline from solver time_limit",
                            "do not call unbounded two_opt_intra",
                        ],
                        "required_pair_evidence": [
                            "total_distance delta by case and seed",
                            "wall-clock elapsed status",
                        ],
                        "default_reject_directions": [
                            "activation claims without wall-clock evidence",
                        ],
                    },
                    "case_protection_requirements": {
                        "schema_version": (
                            "scion.cvrp_case_protection_requirements.v1"
                        ),
                        "scope": "proposal_only_prepared_handoff",
                        "proposal_visibility_only": True,
                        "decision_features_excluded": True,
                        "protected_cases": ["CMT2", "CMT4"],
                        "rules": [
                            (
                                "Target intent or hypothesis must name the "
                                "CMT2/CMT4 protection plan."
                            ),
                            (
                                "Same-branch follow-up should keep CMT2 and "
                                "CMT4 in formal coverage when available."
                            ),
                        ],
                        "required_evidence": [
                            "live target-intent or hypothesis trace mentions CMT2/CMT4 protection",
                            "case-level total_distance deltas for CMT2 and CMT4",
                        ],
                    },
                    "measurement_opportunity_diagnostics": {
                        "schema_version": (
                            "cvrp_measurement_opportunity_handoff.v1"
                        ),
                        "metric": "total_distance",
                        "runtime_model": "budget_exhausting",
                        "pairing_validity": "trajectory_divergent",
                        "practical_screen_delta": 2.0,
                        "screening_mde_at_power_80": 9.9,
                        "recommended_min_seeds": 8,
                        "reason_codes": ["CVRP_MDE_EXCEEDS_PRACTICAL_DELTA"],
                        "summary": (
                            "Sub-MDE effects need direct objective-effect "
                            "attribution."
                        ),
                        "decision_features_excluded": True,
                        "proposal_visibility_only": True,
                    },
                    "decision_boundary": (
                        "This focus is proposal guidance only and must not enter "
                        "DecisionFeatures."
                    ),
                },
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("PREPARED_RUN_MANIFEST", str(manifest_path))
    spec_v1 = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    legacy = legacy_problem_spec_from_v1(spec_v1)
    champion = ChampionState(
        version=1,
        operator_pool={},
        solver_config_hash="h",
        code_snapshot_path=str(_CVRP_ROOT),
        code_snapshot_hash="h",
    )
    branch = Branch(
        branch_id="b-prepared-focus",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="h",
    )

    ctx = ContextManager(adapter=CvrpAdapter(spec_v1)).build_hypothesis_context(
        branch=branch,
        champion=champion,
        problem_spec=legacy,
        active_hypotheses=[],
        blacklist=[],
    )
    focus = ctx["launch_research_focus"]
    assert focus["decision_features_excluded"] is True
    assert focus["problem_family"] == "cvrp"
    assert focus["contract_source"] == "legacy_research_focus_adapter"
    assert focus["current_question"] == (
        "Select a materially different CVRP solver-design mechanism."
    )
    assert focus["required_mechanism_ids"] == [
        "large_instance_intra_route_two_opt_seed"
    ]
    assert "large_instance_two_opt_constraints" in focus["guidance_text"]
    assert "derive a deadline from solver time_limit" in focus["guidance_text"]
    assert "case_protection_requirements.protected_cases[0]" in focus["guidance_text"]

    system_blocks, user_prompt = _split_hypothesis_context(ctx)
    prompt_text = "\n".join(block["text"] for block in system_blocks) + user_prompt

    assert "launch_research_focus" in prompt_text
    assert "next_required_direction" in prompt_text
    assert "required_mechanism_ids" in prompt_text
    assert "route-merge absorption" in prompt_text
    assert "bounded_local_search_variant" in prompt_text
    assert "large_instance_two_opt_constraints" in prompt_text
    assert "case_protection_requirements" in prompt_text
    assert "CMT2/CMT4 protection plan" in prompt_text
    assert "two_opt_intra" in prompt_text
    assert "CVRP_MDE_EXCEEDS_PRACTICAL_DELTA" in prompt_text
    assert "DecisionFeatures" in prompt_text
    assert "## Prepared Research Obligations" in prompt_text
    assert "material causal-path difference from reviewed bounded_two_for_one_exchange" in (
        prompt_text
    )

    hypothesis = HypothesisProposal(
        hypothesis_text="Test a route load-slack rebalancing local-search path.",
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/local_search.py",
        predicted_direction="improve",
        target_objectives=["total_distance"],
        protected_objectives=["fleet_violation"],
        mechanism_changes=(
            MechanismChange(
                id="route_load_slack_rebalance_search",
                change_type="modify",
            ),
        ),
    )
    code_ctx = ContextManager(adapter=CvrpAdapter(spec_v1)).build_code_context(
        branch,
        hypothesis,
        champion,
        legacy,
    )
    assert code_ctx["launch_research_focus"]["target_intent_required_mechanism_ids"] == []

    code_blocks, code_user_prompt = _split_code_context(code_ctx)
    code_prompt_text = (
        "\n".join(block["text"] for block in code_blocks) + code_user_prompt
    )

    assert "## Prepared Research Obligations" in code_prompt_text
    assert "Code-generation must implement or preserve" in code_prompt_text
    assert "bounded_two_for_one_exchange" in code_prompt_text
    assert "route_load_slack_rebalance_search" in code_prompt_text
    assert "material causal-path difference from reviewed bounded_two_for_one_exchange" in (
        code_prompt_text
    )
    assert "direct mechanism objective-effect evidence" in code_prompt_text
    assert "CMT2/CMT4 case-level total_distance deltas or split caveat" in (
        code_prompt_text
    )
    assert "together with the Prepared Research Obligations section above" in (
        code_prompt_text
    )
    code_manifest = build_api_visible_prompt_manifest(
        session_id="session-cvrp-prepared-obligations-code",
        phase="draft_patch",
        call_kind="code",
        prompt_context=code_ctx,
        observations=[],
        call_index=2,
        system_blocks=code_blocks,
        user_prompt=code_user_prompt,
    )
    assert "prepared_research_obligations" in code_manifest["section_names"]
    assert code_manifest["section_statuses"]["prepared_research_obligations"][
        "status"
    ] == "included"
    assert code_manifest["section_statuses"]["prepared_research_obligations"][
        "block_family"
    ] == "research_signal"


def test_cvrp_solver_design_hypothesis_keeps_active_file_guidance() -> None:
    spec_v1 = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    legacy = legacy_problem_spec_from_v1(spec_v1)
    champion = ChampionState(
        version=1,
        operator_pool={},
        solver_config_hash="h",
        code_snapshot_path=str(_CVRP_ROOT),
        code_snapshot_hash="h",
    )
    branch = Branch(
        branch_id="b2",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="h",
    )
    hypothesis = HypothesisProposal(
        hypothesis_text="Adjust active ALNS/VNS scheduler telemetry.",
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/scheduler.py",
        predicted_direction="improve",
        target_objectives=["total_distance"],
        protected_objectives=["fleet_violation"],
    )

    ctx = ContextManager(adapter=CvrpAdapter(spec_v1)).build_code_context(
        branch,
        hypothesis,
        champion,
        legacy,
    )
    rendered = "\n".join(str(value) for value in ctx.values())

    assert ctx["research_surface_name"] == "solver_design"
    assert ctx["research_surface_kind"] == "solver_design"
    assert "policies/baseline_modules/scheduler.py" in rendered
    assert "policies/baseline_algorithm.py" in rendered
    assert "context.record_iteration" in rendered
    assert "policies/baseline_algorithm.py" in ctx["editable_patterns"]
    assert "policies/baseline_modules/*.py" in ctx["editable_patterns"]
    assert "policies/search_policy.py" not in ctx["editable_patterns"]
    assert "policies/solver_algorithm.py" not in ctx["editable_patterns"]


def test_cvrp_solver_design_code_prompt_gets_provider_from_context_manager() -> None:
    spec_v1 = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    legacy = legacy_problem_spec_from_v1(spec_v1)
    champion = ChampionState(
        version=1,
        operator_pool={},
        solver_config_hash="h",
        code_snapshot_path=str(_CVRP_ROOT),
        code_snapshot_hash="h",
    )
    branch = Branch(
        branch_id="b3",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="h",
    )
    hypothesis = HypothesisProposal(
        hypothesis_text="Adjust active ALNS/VNS scheduler telemetry.",
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/scheduler.py",
        predicted_direction="improve",
        target_objectives=["total_distance"],
        protected_objectives=["fleet_violation"],
    )

    ctx = ContextManager(adapter=CvrpAdapter(spec_v1)).build_code_context(
        branch,
        hypothesis,
        champion,
        legacy,
    )
    system_blocks, user_prompt = _split_code_context(ctx)
    rendered = "\n".join(block["text"] for block in system_blocks) + user_prompt

    assert "solver_design_prompt_provider" in ctx
    assert "CvrpSolverDesignProvider" in ctx["solver_design_prompt_provider_ref"]
    assert "_ALNSVNSSolver" in rendered
    assert "`_Solution` and `_Route` are slotted state objects" in rendered
    assert "Active Subject Code Constraints" in rendered
    assert "large_instance_two_opt_runtime_guard" in rendered
    assert "large_instance_intra_route_two_opt_seed" in rendered
    assert "UNBOUNDED_TWO_OPT_DEFAULT_REJECT" in rendered
    assert "Do not edit `policies/baseline_modules/state.py`" in rendered


def test_cvrp_code_context_relays_opportunity_commitment_from_mechanism_changes() -> None:
    spec_v1 = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    legacy = legacy_problem_spec_from_v1(spec_v1)
    champion = ChampionState(
        version=1,
        operator_pool={},
        solver_config_hash="h",
        code_snapshot_path=str(_CVRP_ROOT),
        code_snapshot_hash="h",
    )
    branch = Branch(
        branch_id="b4",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="h",
    )
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "Clean-fork to a materially distinct CVRP-owned causal path with "
            "deadline-aware evidence."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/local_search.py",
        predicted_direction="improve",
        target_objectives=("total_distance",),
        protected_objectives=("fleet_violation",),
        mechanism_changes=(
            MechanismChange(
                id="clean_cvrp_solver_fork",
                change_type="modify",
            ),
        ),
    )

    ctx = ContextManager(adapter=CvrpAdapter(spec_v1)).build_code_context(
        branch,
        hypothesis,
        champion,
        legacy,
    )
    system_blocks, user_prompt = _split_code_context(ctx)
    rendered = "\n".join(block["text"] for block in system_blocks) + user_prompt
    manifest = build_api_visible_prompt_manifest(
        session_id="session-cvrp-context-manager-opportunity-commitment",
        phase="draft_patch",
        call_kind="code",
        prompt_context=ctx,
        observations=[],
        call_index=2,
        system_blocks=system_blocks,
        user_prompt=user_prompt,
    )

    assert "opportunity_evidence_commitment" in ctx
    assert "## Opportunity Evidence Commitment" in rendered
    assert "large_instance_two_opt_objective_runtime_requirement" in rendered
    assert "cmt2_cmt4_case_protection" in rendered
    assert "opportunity_evidence_commitment" in manifest["section_names"]
    assert manifest["section_statuses"]["opportunity_evidence_commitment"][
        "status"
    ] == "included"
    commitment_summary = manifest["opportunity_evidence_commitment_summary"]
    assert commitment_summary["selected_mechanism_ids"] == [
        "clean_cvrp_solver_fork"
    ]
    assert commitment_summary["requirement_ids"] == [
        "large_instance_two_opt_objective_runtime_requirement",
        "cmt2_cmt4_case_protection",
    ]
