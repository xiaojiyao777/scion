from __future__ import annotations

from pathlib import Path

from scion.core.models import (
    Branch,
    BranchState,
    ChampionState,
    Decision,
    EvalStats,
    ExperimentStage,
    HypothesisProposal,
    HypothesisRecord,
    PatchProposal,
    ProtocolResult,
    StepRecord,
)
from scion.problem.bridge import (
    legacy_problem_spec_from_v1,
    load_problem_spec_v1_from_yaml,
)
from scion.problems.cvrp.adapter import CvrpAdapter
from scion.proposal.context_manager import ContextManager
from scion.proposal.engine import (
    _split_code_context,
    _split_hypothesis_context,
)
from scion.tests.unit.research_surface_helpers import _CVRP_ROOT


def test_context_exposes_search_policy_surface_and_modify_when_no_operator_pool(
    tmp_path: Path,
) -> None:
    spec_v1 = load_problem_spec_v1_from_yaml(
        Path(__file__).resolve().parents[2] / "problems" / "cvrp" / "problem-v1.yaml"
    )
    legacy = legacy_problem_spec_from_v1(spec_v1)
    (tmp_path / "policies").mkdir()
    (tmp_path / "policies" / "search_policy.py").write_text(
        "def baseline_time_fraction(instance, time_limit_sec):\n"
        "    return 0.8\n\n"
        "def max_operator_rounds(instance, time_limit_sec):\n"
        "    return 20\n\n"
        "def enable_post_baseline_operators(instance, time_limit_sec):\n"
        "    return True\n",
        encoding="utf-8",
    )
    champion = ChampionState(
        version=1,
        operator_pool={},
        solver_config_hash="h",
        code_snapshot_path=str(tmp_path),
        code_snapshot_hash="h",
    )
    branch = Branch(
        branch_id="b1",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="h",
    )
    manager = ContextManager(adapter=CvrpAdapter(spec_v1))

    ctx = manager.build_hypothesis_context(
        branch=branch,
        champion=champion,
        problem_spec=legacy,
        active_hypotheses=[],
        blacklist=[],
    )
    system_blocks, user_prompt = _split_hypothesis_context(ctx)
    prompt_text = "\n".join(block["text"] for block in system_blocks) + user_prompt

    assert "## Research Surfaces" in prompt_text
    assert "## Problem Object" in prompt_text
    assert "Instance model:" in prompt_text
    assert "Solution model:" in prompt_text
    assert "Solver lifecycle:" in prompt_text
    assert "Move/design grammar:" in prompt_text
    assert "Runtime evidence for problem-level hypotheses:" in prompt_text
    assert "Component policies are implementation hooks" in prompt_text
    assert "search_policy [policy]" in prompt_text
    assert "construction_policy [construction]" in prompt_text
    assert "neighborhood_portfolio [portfolio]" in prompt_text
    assert "algorithm_blueprint [config]" in prompt_text
    assert "solver_design [solver_design]" in prompt_text
    assert "policies/search_policy.py" in prompt_text
    assert "policies/construction_policy.py" in prompt_text
    assert "policies/neighborhood_portfolio.py" in prompt_text
    assert "policies/algorithm_blueprint.py" in prompt_text
    assert "policies/solver_algorithm.py" in prompt_text
    assert "policies/baseline_modules/*.py" in prompt_text
    assert "algorithm.role: post_baseline_search_scheduling" in prompt_text
    assert (
        "algorithm.invocation_point: "
        "before_and_during_post_baseline_operator_search"
    ) in prompt_text
    assert "targets.files: policies/search_policy.py" in prompt_text
    assert (
        "action permissions: create_new=false, modify=true, remove=false"
        in prompt_text
    )
    assert "singleton: true" in prompt_text
    assert (
        "interface.required_functions: baseline_time_fraction, "
        "max_operator_rounds, enable_post_baseline_operators"
    ) in prompt_text
    assert "interface.return_contract:" in prompt_text
    assert "bounds.allowed_components:" in prompt_text
    assert "baseline_time_fraction" in prompt_text
    assert "operator_round_limit" in prompt_text
    assert "bounds.numeric_ranges:" in prompt_text
    assert (
        "bounds.complexity_scale_terms: time_limit_sec, route_count, "
        "customer_count"
    ) in prompt_text
    assert (
        "evidence.required_runtime_fields: policy_loaded, policy_errors"
        in prompt_text
    )
    assert "novelty.strategy: semantic_signature" in prompt_text
    assert "novelty.signature_fields: predicted_direction, target_objectives" in prompt_text
    assert "construction_mode" in prompt_text
    assert "construction_elapsed_ms" in prompt_text
    assert "enabled_components" in prompt_text
    assert "component_weights" in prompt_text
    assert "candidate_limits" in prompt_text
    assert "portfolio_stop_reason" in prompt_text
    assert "algorithm_plan" in prompt_text
    assert "algorithm_blueprint_errors" in prompt_text
    assert "solver_algorithm_errors" in prompt_text
    assert "algorithm_local_search_components" in prompt_text
    assert "prompt.hypothesis_guidance:" in prompt_text
    assert "prompt.implementation_guidance:" in prompt_text
    assert "prompt.anti_patterns:" in prompt_text
    assert "instance.customer_ids, instance.customer_count" in prompt_text
    assert "instance.demands[customer_id]" in prompt_text
    assert "Never use instance.customers" in prompt_text
    assert ctx["available_actions"] == "create_new, modify"
    assert "remove" not in ctx["available_actions"]
    assert "Move/design grammar:" in ctx["problem_object"]

    hypothesis = HypothesisProposal(
        hypothesis_text="Tune baseline/operator budget.",
        change_locus="search_policy",
        action="modify",
        target_file="policies/search_policy.py",
        target_weakness="baseline/operator scheduling",
        expected_effect="better budget allocation",
    )
    code_ctx = manager.build_code_context(
        branch=branch,
        hypothesis=hypothesis,
        champion=champion,
        problem_spec=legacy,
    )
    system_blocks, _ = _split_code_context(code_ctx)
    code_prompt_text = "\n".join(block["text"] for block in system_blocks)

    assert "Active surface: search_policy [policy]" in code_prompt_text
    assert "## Problem Object" in code_prompt_text
    assert "Solver lifecycle:" in code_prompt_text
    assert "module-level policy file; no class is required" in code_prompt_text
    assert "def baseline_time_fraction" in code_prompt_text
    assert "`instance.customer_count`" in code_prompt_text
    assert "Never use `instance.customers`" in code_prompt_text

    construction_hypothesis = HypothesisProposal(
        hypothesis_text="Tune initial construction mode.",
        change_locus="construction_policy",
        action="modify",
        target_file="policies/construction_policy.py",
        target_weakness="initial route construction",
        expected_effect="better construction audit distance",
    )
    construction_code_ctx = manager.build_code_context(
        branch=branch,
        hypothesis=construction_hypothesis,
        champion=champion,
        problem_spec=legacy,
    )
    system_blocks, _ = _split_code_context(construction_code_ctx)
    construction_prompt_text = "\n".join(block["text"] for block in system_blocks)

    assert "Active surface: construction_policy [construction]" in construction_prompt_text
    assert "module-level construction policy file; no class is required" in construction_prompt_text
    assert "def construction_mode" in construction_prompt_text

    portfolio_hypothesis = HypothesisProposal(
        hypothesis_text="Tune neighborhood portfolio.",
        change_locus="neighborhood_portfolio",
        action="modify",
        target_file="policies/neighborhood_portfolio.py",
        target_weakness="component scheduling",
        expected_effect="better post-baseline neighborhood selection",
    )
    portfolio_code_ctx = manager.build_code_context(
        branch=branch,
        hypothesis=portfolio_hypothesis,
        champion=champion,
        problem_spec=legacy,
    )
    system_blocks, _ = _split_code_context(portfolio_code_ctx)
    portfolio_prompt_text = "\n".join(block["text"] for block in system_blocks)

    assert "Active surface: neighborhood_portfolio [portfolio]" in portfolio_prompt_text
    assert "module-level portfolio policy file; no class is required" in portfolio_prompt_text
    assert "def enabled_components" in portfolio_prompt_text

    blueprint_hypothesis = HypothesisProposal(
        hypothesis_text="Coordinate the top-level algorithm lifecycle.",
        change_locus="algorithm_blueprint",
        action="modify",
        target_file="policies/algorithm_blueprint.py",
        target_weakness="no accepted post-baseline moves",
        expected_effect="run bounded package-owned local search",
    )
    blueprint_code_ctx = manager.build_code_context(
        branch=branch,
        hypothesis=blueprint_hypothesis,
        champion=champion,
        problem_spec=legacy,
    )
    system_blocks, _ = _split_code_context(blueprint_code_ctx)
    blueprint_prompt_text = "\n".join(block["text"] for block in system_blocks)

    assert "Active surface: algorithm_blueprint [config]" in blueprint_prompt_text
    assert "top-level algorithm lifecycle config surface" in blueprint_prompt_text
    assert "def algorithm_plan" in blueprint_prompt_text
    assert "intra_route_2opt" in blueprint_prompt_text
    assert "Never use `instance.customers`" in blueprint_prompt_text

    solver_design_hypothesis = HypothesisProposal(
        hypothesis_text="Coordinate the solver design from the problem object.",
        change_locus="solver_design",
        action="modify",
        target_file="policies/solver_algorithm.py",
        target_weakness="component hooks are not moving phase-best objective",
        expected_effect="better whole-solver phase movement",
    )
    solver_design_code_ctx = manager.build_code_context(
        branch=branch,
        hypothesis=solver_design_hypothesis,
        champion=champion,
        problem_spec=legacy,
    )
    system_blocks, _ = _split_code_context(solver_design_code_ctx)
    solver_design_prompt_text = "\n".join(block["text"] for block in system_blocks)

    assert (
        "Active surface: solver_design [solver_design]"
        in solver_design_prompt_text
    )
    assert "problem-object research surface" in solver_design_prompt_text
    assert "def solve" in solver_design_prompt_text
    assert "Solver lifecycle:" in solver_design_prompt_text
    assert "full algorithm hook" in solver_design_prompt_text
    assert "baseline_modules" in solver_design_prompt_text
    assert "context.nearest_neighbor" in solver_design_prompt_text
    assert "do not call context.baseline" in solver_design_prompt_text
    assert "context.objective_key" in solver_design_prompt_text
    assert "context.record_move" in solver_design_prompt_text
    assert "solver_algorithm_search_iterations=0" in solver_design_prompt_text
    assert "shallow wrapper" in solver_design_prompt_text
    assert "instance.depot" in solver_design_prompt_text
    assert "adapter/solver remains the authority" in solver_design_prompt_text


def test_solver_design_verification_failure_guides_retry_not_surface_fallback() -> None:
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
        branch_id="branch-solver-design",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="h",
    )
    hypothesis = HypothesisProposal(
        hypothesis_text="Try a coordinated full solver algorithm.",
        change_locus="solver_design",
        action="modify",
        target_file="policies/solver_algorithm.py",
        target_objectives=("total_distance",),
        protected_objectives=("fleet_violation",),
    )
    failed_step = StepRecord(
        round_num=1,
        branch_id=branch.branch_id,
        hypothesis=hypothesis,
        patch=PatchProposal(
            file_path="policies/solver_algorithm.py",
            action="modify",
            code_content=(
                "def solve(instance, rng, time_limit_sec, context):\n"
                "    return {'routes': [[1], [1]]}\n"
            ),
        ),
        contract_passed=True,
        verification_passed=False,
        protocol_result=None,
        decision=None,
        failure_stage="verification",
        failure_detail="V5_solution_consistency",
        verification_detail=(
            "V5_solution_consistency: candidate routes changed infeasibly"
        ),
    )
    rejected = HypothesisRecord(
        hypothesis_id="h-solver-design",
        branch_id=branch.branch_id,
        change_locus="solver_design",
        action="modify",
        status="rejected",
        target_file="policies/solver_algorithm.py",
        hypothesis_text=hypothesis.hypothesis_text,
        base_champion_version=1,
    )
    manager = ContextManager(adapter=CvrpAdapter(spec_v1))

    ctx = manager.build_hypothesis_context(
        branch=branch,
        champion=champion,
        problem_spec=legacy,
        active_hypotheses=[],
        blacklist=[],
        rejected_hypotheses=[rejected],
        step_history=[failed_step],
    )
    system_blocks, user_prompt = _split_hypothesis_context(ctx)
    prompt_text = "\n".join(block["text"] for block in system_blocks) + user_prompt

    assert "## Solver-Design Boundary Control" in prompt_text
    assert "retry the solver-design boundary" in prompt_text
    assert "Component policies" in prompt_text
    assert "algorithm_family" in prompt_text
    assert "runtime_budget_strategy" in prompt_text
    assert "## Globally Failed / Blacklisted Approaches\n(none)" in prompt_text
    assert ctx["active_problem_boundary_surfaces"] == "solver_design"
    assert ctx["operator_categories"] == "solver_design"
    assert "policies/baseline_algorithm.py" in ctx["targetable_files"]
    assert "policies/solver_algorithm.py" in ctx["targetable_files"]
    assert "policies/baseline_modules/*.py" in ctx["targetable_files"]
    assert "policies/baseline_modules/construction.py" in ctx["targetable_files"]
    assert "policies/baseline_modules/destroy_repair.py" in ctx["targetable_files"]
    assert "policies/baseline_modules/local_search.py" in ctx["targetable_files"]
    assert "policies/baseline_modules/scheduler.py" in ctx["targetable_files"]
    assert "policies/baseline_policy.py" not in ctx["targetable_files"]
    assert "Set `change_locus` to one of: solver_design." in user_prompt
    assert "Do not choose a component policy" in user_prompt
    assert "choose the target file by mechanism ownership" in user_prompt
    assert "target that concrete module" in user_prompt
    assert "Choose a research surface from" not in user_prompt


def test_solver_design_winless_scheduler_plateau_guides_target_diversity() -> None:
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
        branch_id="branch-solver-design",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="h",
    )
    steps = []
    for round_num in (1, 2):
        hypothesis = HypothesisProposal(
            hypothesis_text="Try another scheduler variant.",
            change_locus="solver_design",
            action="modify",
            target_file="policies/baseline_modules/scheduler.py",
        )
        steps.append(
            StepRecord(
                round_num=round_num,
                branch_id=branch.branch_id,
                hypothesis=hypothesis,
                patch=PatchProposal(
                    file_path="policies/baseline_modules/scheduler.py",
                    action="modify",
                    code_content="# scheduler\n",
                ),
                contract_passed=True,
                verification_passed=True,
                protocol_result=ProtocolResult(
                    stage=ExperimentStage.SCREENING,
                    stats=EvalStats(
                        n_cases=8,
                        wins=0,
                        losses=1,
                        ties=7,
                        win_rate=0.0,
                        median_delta=0.0,
                        ci_low=0.0,
                        ci_high=0.0,
                    ),
                    gate_outcome="fail",
                    reason_codes=("SCREENING_FAIL_WIN_RATE",),
                    exposed_summary="screening failed with zero wins",
                    raw_metrics_ref="/tmp/screening.json",
                    selected_surface="solver_design",
                ),
                decision=Decision.ABANDON,
                failure_stage="screening",
                failure_detail="T4: win_rate < 0.3",
            )
        )
    manager = ContextManager(adapter=CvrpAdapter(spec_v1))

    ctx = manager.build_hypothesis_context(
        branch=branch,
        champion=champion,
        problem_spec=legacy,
        active_hypotheses=[],
        blacklist=[],
        step_history=steps,
    )
    system_blocks, user_prompt = _split_hypothesis_context(ctx)
    prompt_text = "\n".join(block["text"] for block in system_blocks) + user_prompt

    assert "Solver-design plateau" in prompt_text
    assert "Solver-design target diversity" in prompt_text
    assert "policies/baseline_modules/scheduler.py x2" in prompt_text
    assert "construction.py" in prompt_text
    assert "destroy_repair.py" in prompt_text
    assert "local_search.py" in prompt_text
    assert "scheduler/entrypoint edits only as integration wiring" in prompt_text
