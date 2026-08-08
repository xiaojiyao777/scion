from __future__ import annotations

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
from scion.problem.bridge import legacy_problem_spec_from_v1, load_problem_spec_v1_from_yaml
from scion.problems.cvrp.adapter import CvrpAdapter
from scion.problems.cvrp.solver_design.manifest import SOLVER_DESIGN_API_MANIFEST_FILES
from scion.proposal.context_manager import ContextManager
from scion.proposal.context_manager.code_context import _step_can_own_branch_source
from scion.proposal.edit_protocol.source_discovery import source_digest_for_content
from scion.proposal.engine import _split_code_context, _split_hypothesis_context
from scion.tests.unit.research_surface_helpers import _CVRP_ROOT


def _active_solver_source_paths() -> tuple[str, ...]:
    module_dir = _CVRP_ROOT / "policies" / "baseline_modules"
    paths = [
        _CVRP_ROOT / "policies" / "baseline_algorithm.py",
        *(
            path
            for path in module_dir.glob("*.py")
            if path.name != "__init__.py"
        ),
    ]
    return tuple(
        path.relative_to(_CVRP_ROOT).as_posix()
        for path in sorted(paths)
    )


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


def test_branch_source_ownership_fails_closed_without_exact_disposition() -> None:
    _spec, _legacy, _champion, branch = _runtime()
    rejected = _verified_source_step(
        branch,
        features=_decision_features(branch),
    )

    assert _step_can_own_branch_source(rejected) is False
    assert _step_can_own_branch_source(replace(rejected, decision=None)) is False
    assert (
        _step_can_own_branch_source(
            replace(rejected, decision_features_snapshot=None)
        )
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


def test_cvrp_source_ledger_does_not_expose_ambiguous_rejected_history() -> None:
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
    ledger = context["proposal_source_ledger"]
    scheduler_path = "policies/baseline_modules/scheduler.py"
    scheduler = next(
        entry for entry in ledger["entries"] if entry["path"] == scheduler_path
    )
    clean_source = (_CVRP_ROOT / scheduler_path).read_text()

    assert scheduler["content"] == clean_source
    assert scheduler["digest"] == source_digest_for_content(clean_source)
    assert scheduler["provenance"] != "branch_history_current"
    assert rejected_sentinel.strip() not in scheduler["content"]
    assert scheduler_path not in ledger["views"]["branch_current"]


def test_direct_cvrp_declared_sources_have_one_full_source_owner() -> None:
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
    ledger = context["proposal_source_ledger"]
    entries = ledger["entries"]
    owned_paths = [entry["path"] for entry in entries]
    active_paths = _active_solver_source_paths()

    assert ledger["schema_version"] == "proposal-source-ledger.v2"
    assert ledger["approved_target"] == target
    assert set(owned_paths) == set(active_paths)
    assert Counter(owned_paths) == Counter(
        {path: 1 for path in active_paths}
    )
    assert set(SOLVER_DESIGN_API_MANIFEST_FILES).issubset(owned_paths)
    assert set(active_paths).issubset(ledger["views"]["api_reference"])
    assert [entry["owner"] for entry in entries].count("approved_target") == 1
    assert all(entry["content"] for entry in entries)
    assert all(entry["digest"] for entry in entries)
    system_blocks, user_prompt = _split_code_context(context)
    rendered = "\n".join(block["text"] for block in system_blocks) + user_prompt
    for path in active_paths:
        assert rendered.count(f'"path": "{path}"') == 1


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
    assert context["research_question"]["schema_version"] == (
        "scion.typed_research_question.v1"
    )
    assert "policies/baseline_algorithm.py" in context["existing_target_files"]
    assert "policies/baseline_modules/*.py" in context["create_path_patterns"]
    assert context["available_actions"] == ["create_new", "modify"]
    assert all("*" not in path for path in context["existing_target_files"])
    for path in _active_solver_source_paths():
        assert path in context["existing_target_files"]
        assert context["champion_operators_code"].count(
            f"### {path} (research surface)"
        ) == 1
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

    assert "solver_design_prompt_guidance" in context["proposal_renderer_inputs"]
    assert '"active_subject_code_constraints"' in rendered
    assert "source ledger" in rendered
    assert "_Solution.routes" in rendered
    assert "_Route" in rendered
    instrumentation_guidance = "\n".join(
        (
            str(context["operator_interface_spec"]),
            str(context["active_subject_code_constraints"]),
            str(context["proposal_renderer_inputs"]),
            str(context["research_surface"]),
        )
    )
    assert "record_move" not in instrumentation_guidance
    assert "record_phase" not in instrumentation_guidance
    assert "record_iteration" not in instrumentation_guidance
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
