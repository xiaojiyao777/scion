from __future__ import annotations

import json
from pathlib import Path

import pytest
from scion.core.execution_outcome import ExecutionOutcome, ExecutionOutcomeRecord
from scion.core.models import (
    Branch,
    BranchState,
    CaseAggregateFeedback,
    ChampionState,
    Decision,
    EvalStats,
    ExperimentStage,
    HypothesisProposal,
    PairwiseCaseFeedback,
    PatchFileChange,
    PatchProposal,
    ProtocolResult,
    StepRecord,
)
from scion.problem.bridge import (
    legacy_problem_spec_from_v1,
    load_problem_spec_v1_from_yaml,
)
from scion.problem.loader import load_problem_adapter
from scion.proposal.context_manager import ContextManager
from scion.proposal.context_manager.history_projection import (
    proposal_screening_history,
)
from scion.proposal.context_manager.manager import (
    _screening_projection,
    screening_record,
)
from scion.proposal.context_snapshot import freeze_proposal_context
from scion.proposal.engine import (
    _parse_hypothesis,
    _split_code_context,
    _split_hypothesis_context,
)
from scion.protocol.experiment.proposal_evidence import (
    problem_proposal_mechanism_evidence,
)

_PROBLEM_ROOT = Path(__file__).resolve().parents[2] / "problems"


def _runtime(problem_id: str):
    spec = load_problem_spec_v1_from_yaml(
        _PROBLEM_ROOT / problem_id / "problem-v1.yaml"
    )
    legacy = legacy_problem_spec_from_v1(spec)
    adapter = load_problem_adapter(spec)
    champion = ChampionState(
        version=1,
        operator_pool={},
        code_snapshot_path=legacy.root_dir,
    )
    branch = Branch(
        branch_id=f"direct-{problem_id}",
        state=BranchState.EXPLORE,
        base_champion_id=1,
    )
    return spec, legacy, adapter, champion, branch


def test_warehouse_hypothesis_context_exposes_all_declared_safe_surfaces_and_source() -> (
    None
):
    spec, legacy, adapter, champion, branch = _runtime("warehouse_delivery")

    context = ContextManager(adapter=adapter).build_hypothesis_context(
        branch=branch,
        champion=champion,
        problem_spec=legacy,
    )

    assert {surface["name"] for surface in context["research_surfaces"]} == {
        surface.name for surface in spec.research_surfaces or []
    }
    editable_operator_files = {
        path.relative_to(Path(champion.code_snapshot_path)).as_posix()
        for path in Path(champion.code_snapshot_path, "operators").glob("*.py")
        if path.name not in {"__init__.py", "base.py"}
    }
    assert editable_operator_files
    for file_rel in editable_operator_files:
        assert f"### {file_rel}" in context["champion_operators_code"]
        assert file_rel in context["existing_target_files"]
    assert context["create_path_patterns"] == ["operators/*.py"]
    assert "remove" not in context["available_actions"]
    mechanics = context["solver_mechanics"]
    assert "top-40 elitist solution pool" in mechanics
    assert "at most 200 iterations" in mechanics
    assert "30 consecutive iterations" in mechanics
    assert "move_order=0.2" in mechanics
    assert "create_new" in mechanics
    diagnostics = context["problem_measurement_diagnostics"][
        "problem_owned_diagnostics"
    ]
    assert diagnostics["aggregate_objective_headroom"]["theoretical_lower_bounds"] == {
        "subcategory_splits": 0
    }
    assert diagnostics["aggregate_noise_context"]["mde_at_power_80"] == 577.5
    assert diagnostics["aggregate_noise_context"]["n_pairs"] > 0


def test_warehouse_real_provider_prompts_are_phase_specific() -> None:
    spec, legacy, adapter, champion, branch = _runtime("warehouse_delivery")
    surface_specs = {surface.name: surface for surface in spec.research_surfaces or []}

    h_context = ContextManager(adapter=adapter).build_hypothesis_context(
        branch=branch,
        champion=champion,
        problem_spec=legacy,
    )
    h_blocks, h_user = _split_hypothesis_context(
        freeze_proposal_context("hypothesis", h_context).provider_context(
            include_renderer_inputs=True
        )
    )
    h_rendered = "\n".join(block["text"] for block in h_blocks) + h_user
    assert all("hypothesis_guidance" in item for item in h_context["research_surfaces"])
    assert all(
        "implementation_guidance" not in item for item in h_context["research_surfaces"]
    )
    assert all("anti_patterns" not in item for item in h_context["research_surfaces"])
    for surface in surface_specs.values():
        assert h_rendered.count(surface.prompt.hypothesis_guidance) == 1
        assert surface.prompt.implementation_guidance not in h_rendered
        assert surface.prompt.anti_patterns not in h_rendered
    assert "research_question" not in h_context
    assert "prior_research_observations" not in h_context

    hypothesis = HypothesisProposal(
        hypothesis_text="Test a vehicle-level structural improvement.",
        change_locus="vehicle_level",
        action="modify",
        target_file="operators/change_vehicle_type.py",
    )
    c_context = ContextManager(adapter=adapter).build_code_context(
        branch,
        hypothesis,
        champion,
        legacy,
    )
    c_blocks, c_user = _split_code_context(
        freeze_proposal_context("code", c_context).provider_context(
            include_renderer_inputs=True
        )
    )
    c_rendered = "\n".join(block["text"] for block in c_blocks) + c_user
    selected = surface_specs["vehicle_level"].prompt
    assert c_context["research_surface"]["implementation_guidance"] == (
        selected.implementation_guidance
    )
    assert c_context["research_surface"]["anti_patterns"] == selected.anti_patterns
    assert "hypothesis_guidance" not in c_context["research_surface"]
    assert "Active Surface Prompt Guidance" not in c_context["operator_interface_spec"]
    assert c_rendered.count(selected.implementation_guidance) == 1
    assert selected.anti_patterns not in c_rendered
    assert c_rendered.count("solution.assignment") >= 1
    assert c_rendered.count("locked_vehicle_id") >= 1
    assert "import whitelist" not in c_rendered.casefold()
    provider_context = json.loads(c_blocks[1]["text"].split("\n", 1)[1])
    assert set(provider_context) == {
        "approved_hypothesis",
        "editable_source_context",
    }
    assert surface_specs["order_level"].prompt.hypothesis_guidance not in c_rendered
    assert surface_specs["order_level"].prompt.implementation_guidance not in c_rendered
    assert "research_question" not in c_context
    assert "prior_research_observations" not in c_context


@pytest.mark.parametrize("problem_id", ("warehouse_delivery", "cvrp"))
def test_direct_v3_real_problem_response_uses_minimal_parser_path(
    problem_id: str,
) -> None:
    _spec, legacy, _adapter, _champion, _branch = _runtime(problem_id)
    surface = legacy.research_surfaces[0]
    target_file = (
        "policies/baseline_modules/local_search.py"
        if problem_id == "cvrp"
        else "operators/direct_lossless_fixture.py"
    )

    proposal = _parse_hypothesis(
        {
            "hypothesis_text": f"Exercise {problem_id} direct response parsing.",
            "change_locus": surface.name,
            "action": "modify" if problem_id == "cvrp" else "create_new",
            "target_file": target_file,
            "predicted_direction": "improve",
            "target_weakness": "slow convergence",
            "expected_effect": "faster convergence",
        }
    )

    assert proposal.change_locus == surface.name
    assert proposal.target_file == target_file


@pytest.mark.parametrize("problem_id", ("warehouse_delivery", "cvrp"))
def test_direct_v3_hypothesis_context_is_complete_without_control_pile(
    problem_id: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _spec, legacy, adapter, champion, branch = _runtime(problem_id)
    branch.direction = f"SENTINEL_{problem_id}_HOST_DIRECTION"
    objective_tail = f"SENTINEL_{problem_id}_OBJECTIVE"
    runtime_error_tail = f"SENTINEL_{problem_id}_RUNTIME_ERROR"
    safe_diagnostic = f"SENTINEL_{problem_id}_SAFE_DIAGNOSTIC"
    hidden_phase_telemetry = f"SENTINEL_{problem_id}_HIDDEN_PHASE_TELEMETRY"
    pre_protocol_noise = f"SENTINEL_{problem_id}_PRE_PROTOCOL_NOISE"
    forbidden_raw = f"FORBIDDEN_{problem_id}_RAW_PAIR"
    hypothesis = HypothesisProposal(
        hypothesis_text=objective_tail,
        change_locus=legacy.research_surfaces[0].name,
        action="modify",
        target_file=(
            "policies/baseline_modules/local_search.py"
            if problem_id == "cvrp"
            else "operators/change_vehicle_type.py"
        ),
    )
    screening = StepRecord(
        round_num=1,
        branch_id=branch.branch_id,
        hypothesis=hypothesis,
        patch=None,
        contract_passed=True,
        verification_passed=True,
        protocol_result=ProtocolResult(
            stage=ExperimentStage.SCREENING,
            stats=EvalStats(
                n_cases=1,
                wins=1,
                losses=0,
                ties=0,
                win_rate=1.0,
                median_delta=2.5,
                ci_low=1.0,
                ci_high=4.0,
                total_pairs=1,
                valid_pairs=1,
                pair_wins=1,
                pair_losses=0,
                pair_ties=0,
            ),
            gate_outcome="pass",
            reason_codes=("SCREENING_PASS",),
            exposed_summary="duplicate summary noise",
            raw_metrics_ref="private/raw.json",
            objective_semantics="minimize total objective",
            case_ids=("case-visible",),
            seed_set=(11,),
            pair_feedback=(
                PairwiseCaseFeedback(
                    case_id="case-visible",
                    seed=11,
                    comparison="win",
                    delta=2.5,
                ),
            ),
            case_feedback=(
                CaseAggregateFeedback(
                    case_id="case-visible",
                    n_pairs=1,
                    wins=1,
                    losses=0,
                    ties=0,
                    win_rate=1.0,
                    dominant_result="win",
                    median_deltas={"objective": 2.5},
                ),
            ),
            candidate_phase_telemetry_summary={"phase": hidden_phase_telemetry},
            candidate_operator_attempts=99,
            mechanism_evidence={"mechanism": hidden_phase_telemetry},
            candidate_runtime_failure_categories={"crash": 1},
            candidate_first_runtime_failure={"detail": runtime_error_tail},
        ),
        decision=Decision.CONTINUE_EXPLORE,
        failure_stage=None,
        failure_detail=None,
    )
    pre_protocol = StepRecord(
        round_num=2,
        branch_id=branch.branch_id,
        hypothesis=HypothesisProposal(
            hypothesis_text=pre_protocol_noise,
            change_locus=legacy.research_surfaces[0].name,
            action="modify",
            target_file=hypothesis.target_file,
        ),
        patch=None,
        contract_passed=False,
        verification_passed=False,
        protocol_result=None,
        decision=None,
        failure_stage="verification",
        failure_detail=pre_protocol_noise,
    )
    adapter_payload = dict(adapter.render_problem_measurement_diagnostics())
    visible_diagnostic_field = (
        "typed_attribution" if problem_id == "cvrp" else "opportunity_diagnostics"
    )
    adapter_payload[visible_diagnostic_field] = [{"summary": safe_diagnostic}]
    adapter_payload["phase_telemetry"] = [hidden_phase_telemetry]
    adapter_payload["raw_pair_rows"] = [forbidden_raw]
    monkeypatch.setattr(
        adapter,
        "render_problem_measurement_diagnostics",
        lambda: adapter_payload,
    )

    context = ContextManager(adapter=adapter).build_hypothesis_context(
        branch=branch,
        champion=champion,
        problem_spec=legacy,
        step_history=[screening, pre_protocol],
    )
    snapshot = freeze_proposal_context("hypothesis", context)
    blocks, user_prompt = _split_hypothesis_context(
        snapshot.provider_context(include_renderer_inputs=True)
    )
    rendered = "\n".join(block["text"] for block in blocks) + user_prompt

    assert len(context["experiment_history"]) == 1
    evidence = context["experiment_history"][0]
    assert evidence["summary_level"] == "full"
    assert evidence["latest_round"] == 1
    assert "attempt_id" not in evidence
    assert "screening_attempt_id" not in evidence
    assert set(evidence["experiment_evidence"]) == {
        "stage",
        "protocol_outcome",
        "decision_outcome",
        "objective_outcome",
        "case_outcomes",
        "runtime_errors",
    }
    composition = evidence["candidate_composition"]
    assert not composition.get("current_step")
    assert {
        key: value for key, value in composition.items() if key != "current_step"
    } == {
        "attribution_scope": "cumulative_branch_candidate",
        "protocol_comparison_scope": "candidate_vs_champion",
        "evaluation_candidate": "reused_verified_branch_state",
        "current_step_change_scope": "eval_only_reuse",
        "incremental_effect_isolated": False,
    }
    protocol_outcome = evidence["experiment_evidence"]["protocol_outcome"]
    assert protocol_outcome == {
        "gate_outcome": "pass",
        "reason_codes": ["SCREENING_PASS"],
    }
    assert evidence["experiment_evidence"]["decision_outcome"] == {
        "decision": "continue_explore",
    }
    assert evidence["experiment_evidence"]["runtime_errors"] == {
        "categories": {"crash": 1}
    }
    aggregation = evidence["experiment_evidence"]["objective_outcome"]["aggregation"]
    assert aggregation["statistical_unit"] == "case"
    assert aggregation["win_rate_scope"] == "case_level_gate"
    assert aggregation["median_delta_scope"] == "case_medians"
    assert aggregation["ci_scope"] == "case_medians"
    assert aggregation["pair_win_rate_scope"] == "pair_level_protocol_stats"
    assert aggregation["pair_win_rate"] == 1.0
    assert "pair_level" not in aggregation
    assert "pair_median_delta" not in aggregation
    assert objective_tail in rendered
    assert "case-visible" not in rendered
    assert runtime_error_tail not in rendered
    assert safe_diagnostic in rendered
    assert hidden_phase_telemetry not in rendered
    assert pre_protocol_noise not in rendered
    assert forbidden_raw not in rendered
    assert "problem_opportunity_summary" not in context
    assert "raw_pair_rows" not in rendered
    assert "champion-code" not in rendered
    assert "champion-config" not in rendered
    assert "research_question" not in context
    assert "prior_research_observations" not in context
    assert "report_only" not in rendered
    assert "branch_direction" not in context
    assert branch.direction not in rendered
    assert set(context).isdisjoint(
        {
            "failed_hypotheses",
            "active_hypotheses",
            "sibling_branches",
            "branch_dossier",
            "cross_branch_research",
            "material_difference_requirement",
            "branch_lesson_usage_requirement",
            "search_memory",
            "research_log",
            "runtime_feedback",
            "agent_quality_feedback",
            "search_control_guidance",
        }
    )
    lowered = rendered.lower()
    for forbidden in (
        "omitted_item_count",
        "text_digest",
        "compact_to_fit",
        "target_intent",
    ):
        assert forbidden not in lowered


def test_rejection_steps_do_not_become_h_repair_steering() -> None:
    _spec, legacy, adapter, champion, branch = _runtime("warehouse_delivery")
    sibling = Branch(
        branch_id="prior-rejected-sibling",
        state=BranchState.EXPLORE,
        base_champion_id=champion.version,
    )
    hypothesis = HypothesisProposal(
        hypothesis_text="FORBIDDEN_PROVIDER_HYPOTHESIS_PROSE",
        change_locus="order_level",
        action="modify",
        target_file="operators/change_vehicle_type.py",
    )
    patch = PatchProposal(
        file_path="operators/change_vehicle_type.py",
        action="modify",
        code_content="FORBIDDEN_REJECTED_PATCH_SOURCE",
    )

    def rejected_step(
        *,
        round_num: int,
        phase: str,
        reason_code: str,
        check_code: str,
        rejected_patch: PatchProposal | None,
        source_branch_id: str = branch.branch_id,
        check_detail: str = "FORBIDDEN_CHECK_DETAIL",
    ) -> StepRecord:
        checks_key = (
            "contract_checks" if phase.endswith("contract") else "verification_checks"
        )
        return StepRecord(
            round_num=round_num,
            branch_id=source_branch_id,
            hypothesis=hypothesis,
            patch=rejected_patch,
            contract_passed=phase == "verification",
            verification_passed=False,
            protocol_result=None,
            decision=None,
            failure_stage=phase,
            failure_detail="FORBIDDEN_PROVIDER_OR_CHECK_PROSE",
            execution_outcome=ExecutionOutcomeRecord(
                outcome=ExecutionOutcome.RESEARCH_REJECTED,
                reason_code=reason_code,
                detail="FORBIDDEN_EXECUTION_DETAIL",
                provenance={
                    "stage": phase,
                    checks_key: [
                        {
                            "name": check_code,
                            "passed": False,
                            "severity": "heavy",
                            "detail": check_detail,
                            "metadata": {
                                "validation_case_details": "FORBIDDEN_VALIDATION_RAW"
                            },
                        },
                        {
                            "name": "PASSED_CHECK_MUST_NOT_APPEAR",
                            "passed": True,
                        },
                    ],
                },
            ),
        )

    steps = [
        rejected_step(
            round_num=1,
            phase="hypothesis_contract",
            reason_code="HYPOTHESIS_CONTRACT_REJECTED",
            check_code="H3_target_matches_locus",
            rejected_patch=None,
        ),
        rejected_step(
            round_num=2,
            phase="patch_contract",
            reason_code="PATCH_CONTRACT_REJECTED",
            check_code="C5_frozen_boundary",
            rejected_patch=patch,
        ),
        rejected_step(
            round_num=3,
            phase="verification",
            reason_code="VERIFICATION_HEAVY_REJECTED",
            check_code="V6_feasibility",
            rejected_patch=patch,
            source_branch_id=sibling.branch_id,
        ),
        rejected_step(
            round_num=4,
            phase="verification",
            reason_code="VERIFICATION_REJECTED",
            check_code="V1_syntax",
            rejected_patch=patch,
            check_detail="syntax_error: expected an indented block",
        ),
        StepRecord(
            round_num=5,
            branch_id=branch.branch_id,
            hypothesis=hypothesis,
            patch=None,
            contract_passed=False,
            verification_passed=False,
            protocol_result=None,
            decision=None,
            failure_stage="proposal_hypothesis",
            failure_detail="FORBIDDEN_PROVIDER_FAILURE",
        ),
        *[
            StepRecord(
                round_num=round_num,
                branch_id=branch.branch_id,
                hypothesis=hypothesis,
                patch=patch,
                contract_passed=True,
                verification_passed=False,
                protocol_result=ProtocolResult(
                    stage=stage,
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
                    reason_codes=(f"FORBIDDEN_{stage.value.upper()}_CODE",),
                    exposed_summary=f"FORBIDDEN_{stage.value.upper()}_SUMMARY",
                    raw_metrics_ref=f"private/FORBIDDEN_{stage.value.upper()}.json",
                    case_ids=(f"FORBIDDEN_{stage.value.upper()}_CASE",),
                ),
                decision=None,
                failure_stage="verification",
                failure_detail=f"FORBIDDEN_{stage.value.upper()}_DETAIL",
            )
            for round_num, stage in (
                (6, ExperimentStage.VALIDATION),
                (7, ExperimentStage.FROZEN),
            )
        ],
    ]

    context = ContextManager(adapter=adapter).build_hypothesis_context(
        branch=branch,
        champion=champion,
        problem_spec=legacy,
        step_history=steps,
    )

    assert "last_research_rejection" not in context
    snapshot = freeze_proposal_context("hypothesis", context)
    blocks, user_prompt = _split_hypothesis_context(
        snapshot.provider_context(include_renderer_inputs=True)
    )
    rendered = "\n".join(block["text"] for block in blocks) + user_prompt
    for forbidden in (
        "FORBIDDEN_PROVIDER_HYPOTHESIS_PROSE",
        "FORBIDDEN_REJECTED_PATCH_SOURCE",
        "FORBIDDEN_PROVIDER_OR_CHECK_PROSE",
        "FORBIDDEN_EXECUTION_DETAIL",
        "FORBIDDEN_CHECK_DETAIL",
        "FORBIDDEN_VALIDATION_RAW",
        "FORBIDDEN_PROVIDER_FAILURE",
        "PASSED_CHECK_MUST_NOT_APPEAR",
        "FORBIDDEN_VALIDATION_CODE",
        "FORBIDDEN_VALIDATION_SUMMARY",
        "FORBIDDEN_VALIDATION_CASE",
        "FORBIDDEN_FROZEN_CODE",
        "FORBIDDEN_FROZEN_SUMMARY",
        "FORBIDDEN_FROZEN_CASE",
        "syntax_error: expected an indented block",
    ):
        assert forbidden not in rendered


def test_live_screening_step_is_the_single_in_process_scientific_record() -> None:
    _spec, legacy, adapter, champion, branch = _runtime("cvrp")
    hypothesis = HypothesisProposal(
        hypothesis_text="Test one durable screening observation.",
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/local_search.py",
    )
    screening = StepRecord(
        round_num=1,
        branch_id=branch.branch_id,
        hypothesis=hypothesis,
        patch=None,
        contract_passed=True,
        verification_passed=True,
        protocol_result=ProtocolResult(
            stage=ExperimentStage.SCREENING,
            stats=EvalStats(
                n_cases=2,
                wins=1,
                losses=1,
                ties=0,
                win_rate=0.5,
                median_delta=-1.0,
                ci_low=-2.0,
                ci_high=0.0,
            ),
            gate_outcome="fail",
            reason_codes=("SCREENING_FAIL",),
            exposed_summary="screening failed",
            raw_metrics_ref="private/round-1.json",
        ),
        decision=Decision.CONTINUE_EXPLORE,
        failure_stage=None,
        failure_detail=None,
    )

    context = ContextManager(adapter=adapter).build_hypothesis_context(
        branch=branch,
        champion=champion,
        problem_spec=legacy,
        step_history=[screening],
    )

    assert len(context["experiment_history"]) == 1
    projected = context["experiment_history"][0]
    assert projected["summary_level"] == "full"
    assert "attempt_id" not in projected
    assert "screening_attempt_id" not in projected


def test_raw_runtime_facts_reach_canonical_h_history_without_advice() -> None:
    _spec, legacy, adapter, champion, branch = _runtime("cvrp")
    screening = StepRecord(
        round_num=1,
        branch_id=branch.branch_id,
        hypothesis=HypothesisProposal(
            hypothesis_text="Diagnose a budget-exhausting CVRP candidate.",
            change_locus="solver_design",
            action="modify",
            target_file="policies/baseline_modules/local_search.py",
        ),
        patch=None,
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
                runtime_pairs=4,
            ),
            gate_outcome="fail",
            reason_codes=("SCREENING_FAIL_WIN_RATE",),
            exposed_summary="screening failed",
            raw_metrics_ref="private/budget-exhausting.json",
            runtime_model="budget_exhausting",
        ),
        decision=Decision.CONTINUE_EXPLORE,
        failure_stage=None,
        failure_detail=None,
    )

    context = ContextManager(adapter=adapter).build_hypothesis_context(
        branch=branch,
        champion=champion,
        problem_spec=legacy,
        step_history=[screening],
    )

    evidence = context["experiment_history"][0]["experiment_evidence"]
    assert evidence["runtime_model"] == "budget_exhausting"
    assert evidence["protocol_outcome"] == {
        "gate_outcome": "fail",
        "reason_codes": ["SCREENING_FAIL_WIN_RATE"],
    }
    aggregate = evidence["objective_outcome"]["aggregate"]
    assert aggregate["runtime_pairs"] == 4
    assert "runtime_evidence_status" not in aggregate
    assert "runtime_confidence" not in evidence


def test_step_history_is_the_scientific_context_owner() -> None:
    _spec, legacy, adapter, champion, branch = _runtime("cvrp")
    hypothesis = HypothesisProposal(
        hypothesis_text="Test one durable screening observation.",
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/local_search.py",
    )
    screening = StepRecord(
        round_num=1,
        branch_id=branch.branch_id,
        hypothesis=hypothesis,
        patch=None,
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
                median_delta=-4.0,
                ci_low=-10.0,
                ci_high=-0.5,
            ),
            gate_outcome="fail",
            reason_codes=("SCREENING_FAIL_WIN_RATE",),
            exposed_summary="screening failed",
            raw_metrics_ref="private/round.json",
        ),
        decision=Decision.CONTINUE_EXPLORE,
        failure_stage=None,
        failure_detail=None,
    )
    context = ContextManager(adapter=adapter).build_hypothesis_context(
        branch=branch,
        champion=champion,
        problem_spec=legacy,
        step_history=[screening],
    )

    assert len(context["experiment_history"]) == 1
    projected = context["experiment_history"][0]
    assert projected["experiment_evidence"]["decision_outcome"] == {
        "decision": "continue_explore",
    }
    assert (
        projected["experiment_evidence"]["objective_outcome"]["aggregate"][
            "median_delta"
        ]
        == -4.0
    )


@pytest.mark.parametrize(
    (
        "candidate_parent_scope",
        "expected_attribution_scope",
        "expected_incremental_effect_isolated",
    ),
    (
        ("declared_champion", "current_step_candidate", True),
        ("retained_branch_head", "cumulative_branch_candidate", False),
        (None, "cumulative_branch_candidate", False),
    ),
)
def test_screening_record_uses_host_owned_candidate_parent_scope(
    candidate_parent_scope: str | None,
    expected_attribution_scope: str,
    expected_incremental_effect_isolated: bool,
) -> None:
    hypothesis = HypothesisProposal(
        hypothesis_text="Add one integrated mechanism.",
        change_locus="solver_design",
        action="modify",
        target_file="policies/solver.py",
    )
    patch = PatchProposal(
        file_path="policies/solver.py",
        action="modify",
        code_content="def solve():\n    return 2\n",
        additional_changes=(
            PatchFileChange(
                file_path="policies/scheduler.py",
                action="modify",
                code_content="ENABLED = True\n",
            ),
        ),
    )
    step = StepRecord(
        round_num=2,
        branch_id="branch-1",
        hypothesis=hypothesis,
        patch=patch,
        contract_passed=True,
        verification_passed=True,
        protocol_result=ProtocolResult(
            stage=ExperimentStage.SCREENING,
            stats=EvalStats(
                n_cases=1,
                wins=1,
                losses=0,
                ties=0,
                win_rate=1.0,
                median_delta=3.0,
                ci_low=1.0,
                ci_high=4.0,
            ),
            gate_outcome="pass",
            reason_codes=("SCREENING_PASS",),
            exposed_summary="passed",
            raw_metrics_ref="metrics/round-2.json",
        ),
        decision=Decision.QUEUE_VALIDATE,
        failure_stage=None,
        failure_detail=None,
        candidate_parent_scope=candidate_parent_scope,
    )

    record = screening_record(step)

    composition = record["candidate_composition"]
    assert composition["attribution_scope"] == expected_attribution_scope
    assert composition["protocol_comparison_scope"] == "candidate_vs_champion"
    assert composition["evaluation_candidate"] == (
        "branch_state_after_current_step_patch"
    )
    assert composition["current_step_change_scope"] == "incremental_patch"
    assert (
        composition["incremental_effect_isolated"]
        is expected_incremental_effect_isolated
    )
    assert composition["current_step"]["target_files"] == [
        "policies/scheduler.py",
        "policies/solver.py",
    ]
    aggregation = record["experiment_evidence"]["objective_outcome"]["aggregation"]
    assert "pair_win_rate_scope" not in aggregation
    assert "pair_win_rate" not in aggregation


@pytest.mark.parametrize(
    ("pair_stats", "expected_error"),
    (
        ({}, "pair feedback conflicts with Protocol stats"),
        (
            {"total_pairs": 1, "pair_wins": 1},
            (
                "pair feedback cardinality conflicts with "
                "valid/candidate-failure pair counts"
            ),
        ),
    ),
)
def test_screening_record_rejects_pair_stats_row_conflict(
    pair_stats: dict[str, int],
    expected_error: str,
) -> None:
    stats = EvalStats(
        n_cases=1,
        wins=1,
        losses=0,
        ties=0,
        win_rate=1.0,
        median_delta=1.0,
        ci_low=0.0,
        ci_high=2.0,
        **pair_stats,
    )
    step = StepRecord(
        round_num=1,
        branch_id="branch-1",
        hypothesis=HypothesisProposal(
            hypothesis_text="Test conflicting evidence.",
            change_locus="solver_design",
            action="modify",
            target_file="policies/solver.py",
        ),
        patch=None,
        contract_passed=True,
        verification_passed=True,
        protocol_result=ProtocolResult(
            stage=ExperimentStage.SCREENING,
            stats=stats,
            gate_outcome="pass",
            reason_codes=("SCREENING_PASS",),
            exposed_summary="conflicting pair evidence",
            raw_metrics_ref="metrics/conflict.json",
            pair_feedback=(
                PairwiseCaseFeedback(
                    case_id="case-1",
                    seed=11,
                    comparison="win",
                    delta=1.0,
                ),
            ),
        ),
        decision=Decision.QUEUE_VALIDATE,
        failure_stage=None,
        failure_detail=None,
    )

    with pytest.raises(
        ValueError,
        match=expected_error,
    ):
        screening_record(step)


def test_marked_problem_mechanism_evidence_reaches_next_h_without_raw_trace() -> None:
    _spec, legacy, adapter, champion, branch = _runtime("cvrp")
    packet = problem_proposal_mechanism_evidence(
        stage="screening",
        selected_surface="solver_design",
        runtime_pairs=[
            {
                "candidate_runtime": {
                    "solver_algorithm_alns_iteration_trace": [
                        {
                            "iteration": 1,
                            "repair_operator": "pair",
                            "accepted": True,
                            "best_improved": True,
                            "acceptance_reason": "repair_error",
                            "elapsed_ms_before": 10,
                            "elapsed_ms_after": 30,
                        }
                    ]
                },
                "champion_runtime": {
                    "solver_algorithm_alns_iteration_trace": [
                        {
                            "iteration": 1,
                            "repair_operator": "greedy",
                            "accepted": False,
                            "best_improved": False,
                            "acceptance_reason": "route_limit",
                            "elapsed_ms_before": 5,
                            "elapsed_ms_after": 15,
                        }
                    ]
                },
                "champion_result_source": "cached",
            }
        ],
        problem_spec=legacy,
        adapter=adapter,
    )
    hypothesis = HypothesisProposal(
        hypothesis_text="Test measured repair behavior.",
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/destroy_repair.py",
    )
    screening = StepRecord(
        round_num=1,
        branch_id=branch.branch_id,
        hypothesis=hypothesis,
        patch=None,
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
                median_delta=-4.0,
                ci_low=-10.0,
                ci_high=-0.5,
            ),
            gate_outcome="fail",
            reason_codes=("SCREENING_FAIL_WIN_RATE",),
            exposed_summary="screening failed",
            raw_metrics_ref="private/round.json",
            mechanism_evidence=packet,
        ),
        decision=Decision.CONTINUE_EXPLORE,
        failure_stage=None,
        failure_detail=None,
    )

    context = ContextManager(adapter=adapter).build_hypothesis_context(
        branch=branch,
        champion=champion,
        problem_spec=legacy,
        step_history=[screening],
    )
    evidence = context["experiment_history"][0]["experiment_evidence"]
    assert evidence["mechanism_evidence"] == packet
    proposal_evidence = packet["evidence"]
    assert proposal_evidence["comparison_columns"] == [
        "candidate",
        "champion",
        "candidate_minus_champion",
    ]
    assert proposal_evidence["paired_comparison"]["alns"]["iterations"] == [
        1,
        1,
        0,
    ]
    assert proposal_evidence["paired_comparison"]["alns"]["repair_error"] == [
        1,
        0,
        1,
    ]
    blocks, user_prompt = _split_hypothesis_context(context)
    rendered = "\n".join(block["text"] for block in blocks) + user_prompt
    rendered_mechanism = json.loads(blocks[2]["text"].split("\n", 1)[1])[
        "experiment_history"
    ][0]["experiment_evidence"]["mechanism_evidence"]
    assert '"paired_comparison"' in rendered
    assert '"comparison_columns"' in rendered
    host_control_keys = {"schema_version"}

    def research_projection(value):
        if isinstance(value, dict):
            return {
                key: research_projection(child)
                for key, child in value.items()
                if key not in host_control_keys
            }
        if isinstance(value, list):
            return [research_projection(child) for child in value]
        return value

    assert packet["schema_version"]
    assert packet["evidence"]["schema_version"]
    assert rendered_mechanism == research_projection(packet)
    assert rendered_mechanism["evidence"] == research_projection(packet["evidence"])
    assert host_control_keys.isdisjoint(rendered_mechanism)
    assert host_control_keys.isdisjoint(rendered_mechanism["evidence"])
    assert rendered_mechanism["evidence"]["evidence_scope"] == (
        "screening_search_allocation"
    )
    assert rendered_mechanism["evidence"]["hypothesis_attribution"] == "unbound"
    assert rendered_mechanism["evidence"]["interpretation_constraint"] == (
        "association_only"
    )
    assert "activation_evidence_status" not in rendered
    assert "objective_effect_status" not in rendered
    assert "solver_algorithm_alns_iteration_trace" not in json.dumps(
        rendered_mechanism,
        sort_keys=True,
    )


def test_unmarked_mechanism_mapping_keeps_existing_screening_projection_behavior() -> (
    None
):
    protocol = ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=EvalStats(
            n_cases=0,
            wins=0,
            losses=0,
            ties=0,
            win_rate=0.0,
            median_delta=0.0,
            ci_low=0.0,
            ci_high=0.0,
        ),
        gate_outcome="fail",
        reason_codes=("SCREENING_FAIL_WIN_RATE",),
        exposed_summary="screening failed",
        raw_metrics_ref="private/round.json",
        mechanism_evidence={"legacy_unmarked_diagnostic": {"empty": None}},
    )

    assert "mechanism_evidence" not in _screening_projection(protocol)


def test_marked_legacy_mechanism_envelope_round_trips_losslessly() -> None:
    legacy_envelope = {
        "schema_version": "scion.problem_proposal_mechanism_evidence.v1",
        "problem_family": "cvrp",
        "producer": "problem_provider",
        "evidence": {
            "schema_version": "scion.cvrp.alns_proposal_mechanism_evidence.v1",
            "trace_coverage": {"candidate_trace_pairs": 0},
            "candidate": {"repairs": {}, "unavailable": None},
        },
    }
    protocol = ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=EvalStats(
            n_cases=0,
            wins=0,
            losses=0,
            ties=0,
            win_rate=0.0,
            median_delta=0.0,
            ci_low=0.0,
            ci_high=0.0,
        ),
        gate_outcome="fail",
        reason_codes=("SCREENING_FAIL_WIN_RATE",),
        exposed_summary="screening failed",
        raw_metrics_ref="private/round.json",
        mechanism_evidence=legacy_envelope,
    )

    assert _screening_projection(protocol)["mechanism_evidence"] == legacy_envelope


def test_step_history_keeps_multiple_screenings_of_one_hypothesis() -> None:
    _spec, legacy, adapter, champion, branch = _runtime("cvrp")
    hypothesis = HypothesisProposal(
        hypothesis_text="Expand screening for the same hypothesis.",
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/local_search.py",
    )

    def screening(round_num: int, raw_ref: str, median_delta: float) -> StepRecord:
        return StepRecord(
            round_num=round_num,
            branch_id=branch.branch_id,
            hypothesis=hypothesis,
            patch=None,
            contract_passed=True,
            verification_passed=True,
            protocol_result=ProtocolResult(
                stage=ExperimentStage.SCREENING,
                stats=EvalStats(
                    n_cases=2,
                    wins=1,
                    losses=1,
                    ties=0,
                    win_rate=0.5,
                    median_delta=median_delta,
                    ci_low=-2.0,
                    ci_high=2.0,
                ),
                gate_outcome="expand",
                reason_codes=("SCREENING_EXPAND",),
                exposed_summary="screening expanded",
                raw_metrics_ref=raw_ref,
            ),
            decision=Decision.CONTINUE_EXPLORE,
            failure_stage=None,
            failure_detail=None,
        )

    first = screening(1, "private/round-1.json", -1.0)
    second = screening(2, "private/round-2.json", 0.5)

    context = ContextManager(adapter=adapter).build_hypothesis_context(
        branch=branch,
        champion=champion,
        problem_spec=legacy,
        step_history=[first, second],
    )
    history = context["experiment_history"]
    assert len(history) == 2
    assert [item["latest_round"] for item in history] == [1, 2]
    assert {item["summary_level"] for item in history} == {"full"}
    assert all("screening_trajectory" not in item for item in history)
    assert (
        history[-1]["experiment_evidence"]["objective_outcome"]["aggregate"][
            "median_delta"
        ]
        == 0.5
    )
    assert "attempt_id" not in history[0]
    assert "screening_attempt_id" not in history[0]


def test_provider_history_keeps_every_current_screening_full() -> None:
    records = [
        {
            "attempt_id": f"attempt-{round_num}",
            "screening_attempt_id": f"screening-{round_num}",
            "round_num": round_num,
            "source_branch_id": "current-branch",
            "relation": "current",
            "hypothesis": {
                "hypothesis_text": f"Mechanism {round_num}",
                "change_locus": "solver_design",
                "action": "modify",
                "target_file": "policies/baseline_modules/local_search.py",
            },
            "candidate_composition": {
                "attribution_scope": "current_step_candidate",
                "incremental_effect_isolated": True,
            },
            "experiment_evidence": {
                "stage": "screening",
                "protocol_outcome": {"gate_outcome": "fail"},
                "objective_outcome": {
                    "aggregate": {
                        "median_delta": float(round_num),
                        "runtime_pairs": round_num,
                        "runtime_evidence_status": "insufficient",
                        "runtime_confidence": "FORBIDDEN_DERIVED_CONFIDENCE",
                    },
                },
                "case_outcomes": {"case_feedback": []},
                "runtime_errors": {},
                "mechanism_evidence": {"signal": f"detail-{round_num}"},
                "decision_outcome": {"decision": "continue_explore"},
            },
        }
        for round_num in range(1, 5)
    ]

    projected = proposal_screening_history(records)

    assert [item["summary_level"] for item in projected] == ["full"] * 4
    assert [item["latest_round"] for item in projected] == [1, 2, 3, 4]
    assert projected[0]["experiment_evidence"]["objective_outcome"]["aggregate"] == {
        "median_delta": 1.0,
        "runtime_pairs": 1,
    }
    assert projected[0]["experiment_evidence"]["mechanism_evidence"] == {
        "signal": "detail-1"
    }
    assert projected[-1]["experiment_evidence"]["mechanism_evidence"] == {
        "signal": "detail-4"
    }
    rendered = json.dumps(projected, sort_keys=True)
    assert "attempt_id" not in rendered
    assert "screening_attempt_id" not in rendered
    assert "source_branch_id" not in rendered


@pytest.mark.parametrize("stage", ("validation", "frozen"))
def test_provider_history_rejects_non_screening_durable_evidence(stage: str) -> None:
    record = {
        "attempt_id": "attempt-1",
        "round_num": 1,
        "source_branch_id": "current-branch",
        "relation": "current",
        "experiment_evidence": {"stage": stage},
    }

    with pytest.raises(ValueError, match="screening evidence only"):
        proposal_screening_history([record])


def test_provider_history_does_not_use_attempt_identity_as_a_gate() -> None:
    records = [
        {
            "attempt_id": "attempt-1",
            "round_num": round_num,
            "source_branch_id": "branch-1",
            "relation": relation,
            "experiment_evidence": {"stage": "screening"},
        }
        for round_num, relation in ((1, "current"), (2, "sibling"))
    ]

    projected = proposal_screening_history(records)

    assert [item["relation"] for item in projected] == ["current", "sibling"]
    assert [item["latest_round"] for item in projected] == [1, 2]


def test_live_screening_relation_does_not_require_owner_registration() -> None:
    _spec, legacy, adapter, champion, current = _runtime("cvrp")
    unknown_step = StepRecord(
        round_num=1,
        branch_id="unknown-sibling",
        hypothesis=HypothesisProposal(
            hypothesis_text="FORBIDDEN_UNKNOWN_OWNER_HYPOTHESIS",
            change_locus="solver_design",
            action="modify",
            target_file="policies/baseline_modules/local_search.py",
        ),
        patch=None,
        contract_passed=True,
        verification_passed=True,
        protocol_result=ProtocolResult(
            stage=ExperimentStage.SCREENING,
            stats=EvalStats(
                n_cases=1,
                wins=1,
                losses=0,
                ties=0,
                win_rate=1.0,
                median_delta=1.0,
                ci_low=0.0,
                ci_high=2.0,
            ),
            gate_outcome="pass",
            reason_codes=("SCREENING_PASS",),
            exposed_summary="screening passed",
            raw_metrics_ref="private/unknown-owner.json",
        ),
        decision=Decision.QUEUE_VALIDATE,
        failure_stage=None,
        failure_detail=None,
    )

    context = ContextManager(adapter=adapter).build_hypothesis_context(
        branch=current,
        champion=champion,
        problem_spec=legacy,
        step_history=[unknown_step],
    )
    assert len(context["experiment_history"]) == 1
    assert context["experiment_history"][0]["relation"] == "sibling"


@pytest.mark.parametrize(
    ("problem_id", "surface", "target_file"),
    (
        (
            "warehouse_delivery",
            "vehicle_level",
            "operators/change_vehicle_type.py",
        ),
        (
            "cvrp",
            "solver_design",
            "policies/baseline_modules/local_search.py",
        ),
    ),
)
def test_direct_v3_code_context_contains_source_not_research_history(
    problem_id: str,
    surface: str,
    target_file: str,
) -> None:
    _spec, legacy, adapter, champion, branch = _runtime(problem_id)
    hypothesis = HypothesisProposal(
        hypothesis_text="Implement one source-grounded algorithmic change.",
        change_locus=surface,
        action="modify",
        target_file=target_file,
        predicted_direction="improve",
        target_weakness="current mechanism leaves measurable quality headroom",
        expected_effect="improve the declared objective",
    )

    context = ContextManager(adapter=adapter).build_code_context(
        branch,
        hypothesis,
        champion,
        legacy,
        step_history=[
            StepRecord(
                round_num=1,
                branch_id=branch.branch_id,
                hypothesis=hypothesis,
                patch=None,
                contract_passed=False,
                verification_passed=False,
                protocol_result=None,
                decision=Decision.CONTINUE_EXPLORE,
                failure_stage="hypothesis_contract",
                failure_detail="must-not-enter-code-context",
            )
        ],
    )
    snapshot = freeze_proposal_context("code", context)
    blocks, user_prompt = _split_code_context(
        snapshot.provider_context(include_renderer_inputs=True)
    )
    rendered = "\n".join(block["text"] for block in blocks) + user_prompt
    source_context = context["editable_source_context"]
    sources = source_context["sources"]
    source_paths = [source["path"] for source in sources]
    target = next(source for source in sources if source["path"] == target_file)

    assert source_context["approved_target"] == target_file
    assert len(source_paths) == len(set(source_paths))
    assert all(set(source) == {"path", "content"} for source in sources)
    assert all(isinstance(source["content"], str) for source in sources)
    assert isinstance(target["content"], str)
    assert target["content"]
    assert context["approved_hypothesis"]["target_file"] == target_file
    assert "follow the tool schema's edit protocol" in user_prompt
    assert "source owner, provenance, and digest" not in user_prompt
    assert "setattr, delattr, dynamic-name getattr" not in user_prompt
    assert "globals, locals, or vars" not in user_prompt
    assert (
        "process, network, environment, dynamic-import, or file APIs" not in user_prompt
    )
    assert "must-not-enter-code-context" not in rendered
    assert set(context).isdisjoint(
        {
            "experiment_history",
            "failed_hypotheses",
            "active_hypotheses",
            "sibling_branches",
            "branch_direction",
            "research_question",
        }
    )
    assert "target_intent" not in rendered
    canonical = json.loads(blocks[1]["text"].split("\n", 1)[1])
    assert set(canonical) == {"approved_hypothesis", "editable_source_context"}
    assert canonical["approved_hypothesis"]["target_file"] == target_file
    assert "proposal_source_ledger" not in canonical
    provider_sources = canonical["editable_source_context"]
    assert provider_sources["approved_target"] == target_file
    assert set(provider_sources) == {
        "approved_target",
        "sources",
        "target_api_guidance",
    }
    assert provider_sources["sources"]
    assert all(set(item) == {"path", "content"} for item in provider_sources["sources"])
    for hidden in ("digest", "owner", "provenance", "visibility", "views"):
        assert f'"{hidden}"' not in blocks[1]["text"]


def test_direct_v3_cvrp_create_context_has_empty_target_and_support_sources() -> None:
    _spec, legacy, adapter, champion, branch = _runtime("cvrp")
    target_file = "policies/baseline_modules/new_mechanism.py"
    hypothesis = HypothesisProposal(
        hypothesis_text="Create one source-grounded CVRP mechanism.",
        change_locus="solver_design",
        action="create_new",
        target_file=target_file,
        predicted_direction="improve",
        target_weakness="current mechanism leaves measurable quality headroom",
        expected_effect="improve the declared objective",
    )

    context = ContextManager(adapter=adapter).build_code_context(
        branch,
        hypothesis,
        champion,
        legacy,
        step_history=[],
    )
    source_context = context["editable_source_context"]
    sources = source_context["sources"]
    source_paths = [source["path"] for source in sources]
    target = next(source for source in sources if source["path"] == target_file)
    support_sources = [source for source in sources if source["path"] != target_file]

    assert source_context["approved_target"] == target_file
    assert len(source_paths) == len(set(source_paths))
    assert target["content"] is None
    assert support_sources
    assert all(set(source) == {"path", "content"} for source in sources)
    assert all(isinstance(source["content"], str) for source in support_sources)
