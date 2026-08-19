from __future__ import annotations

import json
from collections import Counter

from scion.core.models import (
    Branch,
    BranchState,
    ChampionState,
    Decision,
    EvalStats,
    ExperimentStage,
    HypothesisProposal,
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
from scion.proposal.engine import _split_code_context, _split_hypothesis_context
from scion.tests.unit.research_surface_helpers import _CVRP_ROOT


def _active_solver_source_paths() -> tuple[str, ...]:
    module_dir = _CVRP_ROOT / "policies" / "baseline_modules"
    paths = [
        _CVRP_ROOT / "policies" / "baseline_algorithm.py",
        *(path for path in module_dir.glob("*.py") if path.name != "__init__.py"),
    ]
    return tuple(path.relative_to(_CVRP_ROOT).as_posix() for path in sorted(paths))


def _runtime():
    spec = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    legacy = legacy_problem_spec_from_v1(spec)
    champion = ChampionState(
        version=1,
        operator_pool={},
        code_snapshot_path=str(_CVRP_ROOT),
    )
    branch = Branch(
        branch_id="direct-cvrp-guidance",
        state=BranchState.EXPLORE,
        base_champion_id=1,
    )
    return spec, legacy, champion, branch


def _verified_source_step(
    branch: Branch,
    *,
    content: str = "# REJECTED_ANCESTRY_SENTINEL\n",
) -> StepRecord:
    target = "policies/baseline_modules/scheduler.py"
    hypothesis = HypothesisProposal(
        hypothesis_text="Exercise branch source ownership.",
        change_locus="solver_design",
        action="modify",
        target_file=target,
    )
    return StepRecord(
        round_num=1,
        branch_id=branch.branch_id,
        hypothesis=hypothesis,
        patch=PatchProposal(target, "modify", content),
        contract_passed=True,
        verification_passed=True,
        protocol_result=ProtocolResult(
            stage=ExperimentStage.SCREENING,
            stats=EvalStats(
                n_cases=1,
                wins=0,
                losses=1,
                ties=0,
                win_rate=0.0,
                median_delta=-1.0,
                ci_low=-2.0,
                ci_high=0.0,
            ),
            gate_outcome="fail",
            reason_codes=("SCREENING_FAIL",),
            exposed_summary="failed",
            raw_metrics_ref="metrics/round-1.json",
        ),
        decision=Decision.CONTINUE_EXPLORE,
        failure_stage=None,
        failure_detail=None,
        decision_reason_codes=("SCREENING_FAIL",),
    )


def test_cvrp_editable_sources_do_not_expose_ambiguous_rejected_history() -> None:
    spec, legacy, champion, branch = _runtime()
    rejected_sentinel = "# REJECTED_ANCESTRY_SENTINEL\n"
    rejected = _verified_source_step(
        branch,
        content=rejected_sentinel,
    )
    fresh = HypothesisProposal(
        hypothesis_text="Try a fresh local-search mechanism.",
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/local_search.py",
    )

    context = ContextManager(adapter=CvrpAdapter(spec)).build_code_context(
        branch,
        fresh,
        champion,
        legacy,
        branch_workspace=str(_CVRP_ROOT),
        step_history=[rejected],
    )
    source_context = context["editable_source_context"]
    scheduler_path = "policies/baseline_modules/scheduler.py"
    scheduler = next(
        source
        for source in source_context["sources"]
        if source["path"] == scheduler_path
    )
    clean_source = (_CVRP_ROOT / scheduler_path).read_text()

    assert scheduler["content"] == clean_source
    assert rejected_sentinel.strip() not in scheduler["content"]
    assert all(
        rejected_sentinel.strip() not in str(source["content"])
        for source in source_context["sources"]
    )


def test_direct_cvrp_declared_sources_are_unique_complete_source_pairs() -> None:
    spec, legacy, champion, branch = _runtime()
    target = "policies/baseline_modules/local_search.py"
    hypothesis = HypothesisProposal(
        hypothesis_text="Improve the local-search mechanism.",
        change_locus="solver_design",
        action="modify",
        target_file=target,
    )

    context = ContextManager(adapter=CvrpAdapter(spec)).build_code_context(
        branch,
        hypothesis,
        champion,
        legacy,
    )
    source_context = context["editable_source_context"]
    sources = source_context["sources"]
    source_paths = [source["path"] for source in sources]
    active_paths = _active_solver_source_paths()

    assert set(source_context) == {
        "approved_target",
        "sources",
        "public_tests",
        "target_api_guidance",
    }
    assert source_context["approved_target"] == target
    assert set(source_paths) == set(active_paths)
    assert Counter(source_paths) == Counter({path: 1 for path in active_paths})
    assert source_context["public_tests"] == []
    assert all(
        set(source) == {"path", "content", "roles", "visible"}
        for source in sources
    )
    assert all(isinstance(source["content"], str) for source in sources)
    source_by_path = {source["path"]: source for source in sources}
    assert source_by_path[target]["roles"] == ["target"]
    assert source_by_path["policies/baseline_modules/config.py"]["roles"] == [
        "dependency"
    ]
    assert source_by_path["policies/baseline_modules/scheduler.py"]["roles"] == [
        "caller"
    ]
    assert source_by_path["policies/baseline_modules/acceptance.py"]["visible"] is False
    system_blocks, user_prompt = _split_code_context(context)
    del user_prompt
    provider_context = json.loads(system_blocks[1]["text"].split("\n", 1)[1])
    rendered_paths = [
        source["path"]
        for source in provider_context["editable_source_context"]["sources"]
    ]
    assert Counter(rendered_paths) == Counter({path: 1 for path in active_paths})


def test_direct_cvrp_hypothesis_context_is_open_algorithm_guidance() -> None:
    spec, legacy, champion, branch = _runtime()

    context = ContextManager(adapter=CvrpAdapter(spec)).build_hypothesis_context(
        branch=branch,
        champion=champion,
        problem_spec=legacy,
    )
    system_blocks, user_prompt = _split_hypothesis_context(context)
    rendered = "\n".join(block["text"] for block in system_blocks) + user_prompt

    assert [surface["name"] for surface in context["research_surfaces"]] == [
        "solver_design"
    ]
    assert "No prepared file or mechanism is mandatory" in rendered
    assert "Runtime errors may explain failed outcomes" in rendered
    assert "Use MDE only when a matched calibration exists" in rendered
    assert "R3 has no matched MDE or power estimate" in rendered
    assert "same-seed A/A result checks only obvious false-pass" in rendered
    assert "research_question" not in context
    assert "prior_research_observations" not in context
    assert "smallest complete causal implementation" in rendered
    assert "policies/baseline_algorithm.py" in context["existing_target_files"]
    assert "policies/baseline_modules/*.py" in context["create_path_patterns"]
    assert context["available_actions"] == ["create_new", "modify"]
    assert all("*" not in path for path in context["existing_target_files"])
    for path in _active_solver_source_paths():
        assert path in context["existing_target_files"]
        assert (
            context["champion_operators_code"].count(f"### {path} (research surface)")
            == 1
        )
    assert "target_intent" not in rendered
    assert "read_active_solver_map" not in rendered


def test_direct_cvrp_code_context_renders_source_and_object_model() -> None:
    spec, legacy, champion, branch = _runtime()
    hypothesis = HypothesisProposal(
        hypothesis_text="Test a new route-state local-search path.",
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/local_search.py",
        predicted_direction="improve",
    )

    context = ContextManager(adapter=CvrpAdapter(spec)).build_code_context(
        branch,
        hypothesis,
        champion,
        legacy,
    )
    system_blocks, user_prompt = _split_code_context(context)
    rendered = "\n".join(block["text"] for block in system_blocks) + user_prompt
    provider_context = json.loads(system_blocks[1]["text"].split("\n", 1)[1])

    assert "proposal_renderer_inputs" not in context
    assert set(provider_context) == {
        "approved_hypothesis",
        "editable_source_context",
    }
    assert '"active_subject_code_constraints"' not in rendered
    assert '"solver_design_prompt_guidance"' not in rendered
    assert '"code_rules"' not in rendered
    assert '"user_constraints"' not in rendered
    assert "_Solution.routes" in rendered
    assert "_Route" in rendered
    assert "shared by initial and embedded VNS" in rendered
    assert "target phase only" in rendered
    assert rendered.count("smallest complete scheduler wiring") == 1
    instrumentation_guidance = "\n".join(
        (
            str(context["operator_interface_spec"]),
            str(context["active_subject_code_constraints"]),
            str(context["research_surface"]),
        )
    )
    assert set(context["active_subject_code_constraints"]) == {
        "object_model_hints",
        "api_contracts",
        "forbidden_patterns",
    }
    assert "source ledger" not in instrumentation_guidance
    assert "stable entrypoint" not in instrumentation_guidance
    assert "Excess route count is reported as fleet_violation" in rendered
    assert "route-count-violating outputs" not in rendered
    target_guidance = context["editable_source_context"]["target_api_guidance"]
    assert "record_move" in target_guidance
    assert "record_phase" in target_guidance
    assert "record_iteration" in target_guidance
    assert '"object_model_hints"' not in target_guidance
    assert '"api_contracts"' not in target_guidance
    assert "ObjectiveValue arithmetic" not in target_guidance
    assert "case ids, reference objectives" not in target_guidance
    assert "telemetry_identity_allowlist" not in instrumentation_guidance
    assert "target_intent" not in rendered
    assert "agentic_code_scope_control" not in rendered


def test_direct_cvrp_context_keeps_only_active_solver_surface() -> None:
    spec, legacy, champion, branch = _runtime()
    hypothesis = HypothesisProposal(
        hypothesis_text="Change the destroy and repair state transition.",
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/destroy_repair.py",
    )

    context = ContextManager(adapter=CvrpAdapter(spec)).build_code_context(
        branch,
        hypothesis,
        champion,
        legacy,
    )
    rendered = "\n".join(str(value) for value in context.values())

    assert context["research_surface"]["name"] == "solver_design"
    assert context["research_surface"]["kind"] == "solver_design"
    assert "policies/baseline_modules/destroy_repair.py" in rendered
    assert "policies/search_policy.py" not in context["editable_patterns"]
    assert "policies/solver_algorithm.py" not in context["editable_patterns"]
