from __future__ import annotations

import json
from collections import Counter
from dataclasses import replace

from scion.core.models import (
    Branch,
    BranchState,
    ChampionState,
    Decision,
    DecisionFeatures,
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
from scion.problems.cvrp.research_guidance import CROSS_CAMPAIGN_RESEARCH_PRIOR
from scion.problems.cvrp.solver_design.manifest import SOLVER_DESIGN_API_MANIFEST_FILES
from scion.proposal.context_manager import ContextManager
from scion.proposal.context_manager.code_context import _step_can_own_branch_source
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
        solver_config_hash="h",
        code_snapshot_path=str(_CVRP_ROOT),
        code_snapshot_hash="h",
    )
    branch = Branch(
        branch_id="direct-cvrp-guidance",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="h",
    )
    return spec, legacy, champion, branch


def _decision_features(
    branch: Branch,
    *,
    gate: str = "fail",
    stage: str = "screening",
) -> DecisionFeatures:
    return DecisionFeatures(
        branch_id=branch.branch_id,
        hypothesis_action="modify",
        stage=stage,  # type: ignore[arg-type]
        contract_passed=True,
        verification_passed=True,
        canary_passed=True,
        n_cases=1,
        win_rate=0.0,
        median_delta=-1.0,
        ci_low=-2.0,
        ci_high=0.0,
        stale=False,
        recent_failure_codes=(),
        protocol_gate_outcome=gate,  # type: ignore[arg-type]
        protocol_reason_codes=(f"{stage.upper()}_{gate.upper()}",),
    )


def _verified_source_step(
    branch: Branch,
    *,
    decision: Decision | None = Decision.CONTINUE_EXPLORE,
    features: DecisionFeatures | None = None,
    reason_codes: tuple[str, ...] = ("SCREENING_FAIL",),
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
        decision=decision,
        failure_stage=None,
        failure_detail=None,
        decision_reason_codes=reason_codes,
        decision_features_snapshot=features,
    )


def test_branch_source_ownership_requires_typed_decision_and_features() -> None:
    _spec, _legacy, _champion, branch = _runtime()
    rejected = _verified_source_step(
        branch,
        features=_decision_features(branch),
    )

    assert _step_can_own_branch_source(rejected) is True
    assert _step_can_own_branch_source(replace(rejected, decision=None)) is False
    assert (
        _step_can_own_branch_source(replace(rejected, decision_features_snapshot=None))
        is False
    )
    assert (
        _step_can_own_branch_source(replace(rejected, decision_reason_codes=()))
        is False
    )


def test_branch_source_ownership_keeps_explicit_retaining_dispositions() -> None:
    _spec, _legacy, _champion, branch = _runtime()
    base = _verified_source_step(branch)
    provisional = replace(
        base,
        decision=Decision.CONTINUE_EXPLORE,
        decision_reason_codes=("SCREENING_UNCLEAR",),
        decision_features_snapshot=_decision_features(branch, gate="unclear"),
    )
    exact_reuse = replace(
        base,
        decision=Decision.EXPAND_SCREENING,
        decision_reason_codes=("SCREENING_EXPAND",),
        decision_features_snapshot=_decision_features(branch, gate="expand"),
    )
    promoted = replace(
        base,
        decision=Decision.PROMOTE,
        decision_reason_codes=("FROZEN_PASS",),
        decision_features_snapshot=_decision_features(
            branch,
            gate="pass",
            stage="frozen",
        ),
    )

    assert _step_can_own_branch_source(provisional) is True
    assert _step_can_own_branch_source(exact_reuse) is True
    assert _step_can_own_branch_source(promoted) is True


def test_cvrp_editable_sources_do_not_expose_ambiguous_rejected_history() -> None:
    spec, legacy, champion, branch = _runtime()
    rejected_sentinel = "# REJECTED_ANCESTRY_SENTINEL\n"
    rejected = _verified_source_step(
        branch,
        features=None,
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
        "target_api_guidance",
    }
    assert source_context["approved_target"] == target
    assert set(source_paths) == set(active_paths)
    assert Counter(source_paths) == Counter({path: 1 for path in active_paths})
    assert set(SOLVER_DESIGN_API_MANIFEST_FILES).issubset(source_paths)
    assert all(set(source) == {"path", "content"} for source in sources)
    assert all(isinstance(source["content"], str) for source in sources)
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
    assert context["research_question"]["schema_version"] == (
        "scion.typed_research_question.v2"
    )
    assert context["research_question"]["research_prior"] == list(
        CROSS_CAMPAIGN_RESEARCH_PRIOR
    )
    for line in CROSS_CAMPAIGN_RESEARCH_PRIOR:
        assert rendered.count(line) == 1
    prior_text = "\n".join(context["research_question"]["research_prior"])
    for hidden_detail in (
        "tai150a",
        "validation",
        "frozen",
        "8W/2L/2T",
        "5W/1L/2T",
        "-22, -210, -90, -21",
    ):
        assert hidden_detail.casefold() not in prior_text.casefold()
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
