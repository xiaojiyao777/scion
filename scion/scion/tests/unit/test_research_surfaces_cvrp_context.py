from __future__ import annotations

from scion.core.models import Branch, BranchState, ChampionState, HypothesisProposal
from scion.problem.bridge import legacy_problem_spec_from_v1, load_problem_spec_v1_from_yaml
from scion.problems.cvrp.adapter import CvrpAdapter
from scion.proposal.context_manager import ContextManager
from scion.proposal.engine import _split_code_context, _split_hypothesis_context
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
    assert "Do not edit `policies/baseline_modules/state.py`" in rendered
