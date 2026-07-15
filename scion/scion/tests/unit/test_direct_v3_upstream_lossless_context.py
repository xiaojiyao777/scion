from __future__ import annotations

import json
from pathlib import Path

import pytest

from scion.core.models import (
    Branch,
    BranchState,
    ChampionState,
    CaseAggregateFeedback,
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
from scion.postrun.direct_v3_prompt_visibility import (
    direct_v3_code_source_visibility,
)
from scion.proposal.context_manager import ContextManager
from scion.proposal.context_manager.manager import (
    CANONICAL_SCREENING_HISTORY_KEY,
    canonical_screening_record,
    persist_canonical_screening_record,
)
from scion.proposal.context_owner_maps import proposal_context_snapshot
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
        solver_config_hash="champion-config",
        code_snapshot_path=legacy.root_dir,
        code_snapshot_hash="champion-code",
    )
    branch = Branch(
        branch_id=f"direct-{problem_id}",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion-code",
    )
    return spec, legacy, adapter, champion, branch


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
    telemetry_noise = f"SENTINEL_{problem_id}_TELEMETRY_NOISE"
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
            candidate_phase_telemetry_summary={"phase": telemetry_noise},
            candidate_operator_attempts=99,
            mechanism_evidence={"mechanism": telemetry_noise},
            candidate_runtime_failure_categories={"crash": 1},
            candidate_first_runtime_failure={"detail": runtime_error_tail},
        ),
        decision=Decision.CONTINUE_EXPLORE,
        failure_stage=None,
        failure_detail=None,
        hypothesis_id="attempt-screening-1",
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
    adapter_payload["opportunity_diagnostics"] = [telemetry_noise]
    adapter_payload["phase_telemetry"] = [telemetry_noise]
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
    snapshot = proposal_context_snapshot("hypothesis", context)
    blocks, user_prompt = _split_hypothesis_context(
        snapshot.inputs.provider_context(include_renderer_inputs=True)
    )
    rendered = "\n".join(block["text"] for block in blocks) + user_prompt

    assert len(context["experiment_history"]) == 1
    evidence = context["experiment_history"][0]
    assert evidence["attempt_id"] == "attempt-screening-1"
    assert set(evidence["experiment_evidence"]) == {
        "stage",
        "protocol_outcome",
        "objective_outcome",
        "case_outcomes",
        "runtime_errors",
    }
    assert evidence["candidate_composition"] == {
        "attribution_scope": "cumulative_branch_candidate",
        "protocol_comparison_scope": "candidate_vs_champion",
        "evaluation_candidate": "reused_verified_branch_state",
        "current_step_change_scope": "eval_only_reuse",
        "incremental_effect_isolated": False,
        "current_step": {"hypothesis_id": "attempt-screening-1"},
    }
    protocol_outcome = evidence["experiment_evidence"]["protocol_outcome"]
    assert protocol_outcome == {
        "gate_outcome": "pass",
        "reason_codes": ["SCREENING_PASS"],
    }
    aggregation = evidence["experiment_evidence"]["objective_outcome"][
        "aggregation"
    ]
    assert aggregation["statistical_unit"] == "case"
    assert aggregation["win_rate_scope"] == "case_level_gate"
    assert aggregation["median_delta_scope"] == "case_medians"
    assert aggregation["ci_scope"] == "case_medians"
    assert aggregation["pair_win_rate_scope"] == "pair_level_protocol_stats"
    assert aggregation["pair_win_rate"] == 1.0
    assert "pair_level" not in aggregation
    assert "pair_median_delta" not in aggregation
    assert objective_tail in rendered
    assert "case-visible" in rendered
    assert runtime_error_tail in rendered
    assert telemetry_noise not in rendered
    assert pre_protocol_noise not in rendered
    assert forbidden_raw not in rendered
    assert "problem_opportunity_summary" not in context
    assert "raw_pair_rows" not in rendered
    assert set(context["research_question"]) == {
        "schema_version",
        "problem_family",
        "current_question",
    }
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


def test_canonical_screening_history_deduplicates_durable_and_live_record() -> None:
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
        hypothesis_id="same-hypothesis",
    )

    assert persist_canonical_screening_record(branch, screening) is True
    context = ContextManager(adapter=adapter).build_hypothesis_context(
        branch=branch,
        champion=champion,
        problem_spec=legacy,
        step_history=[screening],
    )

    assert len(context["experiment_history"]) == 1
    assert context["experiment_history"][0]["attempt_id"] == "same-hypothesis"
    assert persist_canonical_screening_record(branch, screening) is False


def test_canonical_screening_history_upgrades_legacy_row_without_duplicate() -> None:
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
        hypothesis_id="legacy-attempt",
    )
    legacy_record = canonical_screening_record(screening)
    legacy_record.pop("candidate_composition")
    legacy_evidence = legacy_record["experiment_evidence"]
    legacy_evidence.pop("protocol_outcome")
    legacy_evidence["objective_outcome"].pop("aggregation")
    legacy_record["screening_attempt_id"] = "legacy-schema-dependent-id"
    branch.branch_evidence_summary = {
        CANONICAL_SCREENING_HISTORY_KEY: [legacy_record]
    }

    context = ContextManager(adapter=adapter).build_hypothesis_context(
        branch=branch,
        champion=champion,
        problem_spec=legacy,
        step_history=[screening],
    )

    assert len(context["experiment_history"]) == 1
    upgraded = context["experiment_history"][0]
    assert upgraded["attempt_id"] == "legacy-attempt"
    assert upgraded["screening_attempt_id"] != "legacy-schema-dependent-id"
    assert "candidate_composition" in upgraded
    assert "protocol_outcome" in upgraded["experiment_evidence"]
    assert persist_canonical_screening_record(branch, screening) is True
    assert len(
        branch.branch_evidence_summary[CANONICAL_SCREENING_HISTORY_KEY]
    ) == 1


def test_canonical_screening_history_rejects_conflicting_legacy_fact() -> None:
    _spec, legacy, adapter, champion, branch = _runtime("cvrp")
    hypothesis = HypothesisProposal(
        hypothesis_text="Test conflicting durable evidence.",
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
                wins=1,
                losses=0,
                ties=0,
                win_rate=1.0,
                median_delta=2.0,
                ci_low=1.0,
                ci_high=3.0,
            ),
            gate_outcome="pass",
            reason_codes=("SCREENING_PASS",),
            exposed_summary="screening passed",
            raw_metrics_ref="metrics/legacy-conflict.json",
        ),
        decision=Decision.QUEUE_VALIDATE,
        failure_stage=None,
        failure_detail=None,
        hypothesis_id="legacy-conflict",
    )
    legacy_record = canonical_screening_record(screening)
    legacy_record.pop("candidate_composition")
    evidence = legacy_record["experiment_evidence"]
    evidence.pop("protocol_outcome")
    evidence["objective_outcome"].pop("aggregation")
    evidence["objective_outcome"]["aggregate"]["median_delta"] = -999.0
    branch.branch_evidence_summary = {
        CANONICAL_SCREENING_HISTORY_KEY: [legacy_record]
    }

    with pytest.raises(
        ValueError,
        match="canonical screening history conflicts with current step",
    ):
        ContextManager(adapter=adapter).build_hypothesis_context(
            branch=branch,
            champion=champion,
            problem_spec=legacy,
            step_history=[screening],
        )


def test_canonical_screening_record_marks_incremental_patch_as_cumulative_state() -> None:
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
        hypothesis_id="hypothesis-2",
    )

    record = canonical_screening_record(step)

    composition = record["candidate_composition"]
    assert composition["attribution_scope"] == "cumulative_branch_candidate"
    assert composition["protocol_comparison_scope"] == "candidate_vs_champion"
    assert composition["evaluation_candidate"] == (
        "branch_state_after_current_step_patch"
    )
    assert composition["current_step_change_scope"] == "incremental_patch"
    assert composition["incremental_effect_isolated"] is False
    assert composition["current_step"]["hypothesis_id"] == "hypothesis-2"
    assert composition["current_step"]["target_files"] == [
        "policies/scheduler.py",
        "policies/solver.py",
    ]
    aggregation = record["experiment_evidence"]["objective_outcome"][
        "aggregation"
    ]
    assert "pair_win_rate_scope" not in aggregation
    assert "pair_win_rate" not in aggregation


@pytest.mark.parametrize(
    ("pair_stats", "expected_error"),
    (
        ({}, "pair feedback conflicts with Protocol stats"),
        (
            {"total_pairs": 1, "pair_wins": 1},
            "valid-pair count conflicts with pair feedback",
        ),
    ),
)
def test_canonical_screening_record_rejects_pair_stats_row_conflict(
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
        hypothesis_id="hypothesis-1",
    )

    with pytest.raises(
        ValueError,
        match=expected_error,
    ):
        canonical_screening_record(step)


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
                n_cases=1, wins=0, losses=1, ties=0, win_rate=0.0,
                median_delta=-4.0, ci_low=-10.0, ci_high=-0.5,
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
        hypothesis_id="mechanism-attempt",
    )

    context = ContextManager(adapter=adapter).build_hypothesis_context(
        branch=branch,
        champion=champion,
        problem_spec=legacy,
        step_history=[screening],
    )
    evidence = context["experiment_history"][0]["experiment_evidence"]
    assert evidence["mechanism_evidence"] == packet
    blocks, user_prompt = _split_hypothesis_context(context)
    rendered = "\n".join(block["text"] for block in blocks) + user_prompt
    assert '"attempts": 1' in rendered
    assert '"repair_error": 1' in rendered
    assert '"evidence_scope": "alns_repair_runtime_diagnostics"' in rendered
    assert '"hypothesis_attribution": "unbound"' in rendered
    assert "activation_evidence_status" not in rendered
    assert "objective_effect_status" not in rendered
    assert '"solver_algorithm_alns_iteration_trace": [' not in rendered


def test_canonical_screening_history_keeps_multiple_screenings_of_one_hypothesis() -> None:
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
            hypothesis_id="same-hypothesis",
        )

    first = screening(1, "private/round-1.json", -1.0)
    second = screening(2, "private/round-2.json", 0.5)
    assert persist_canonical_screening_record(branch, first) is True
    assert persist_canonical_screening_record(branch, second) is True

    context = ContextManager(adapter=adapter).build_hypothesis_context(
        branch=branch,
        champion=champion,
        problem_spec=legacy,
        step_history=[],
    )
    history = context["experiment_history"]
    assert len(history) == 2
    assert {record["attempt_id"] for record in history} == {"same-hypothesis"}
    assert len({record["screening_attempt_id"] for record in history}) == 2


def test_canonical_screening_history_fails_closed_on_malformed_durable_owner() -> None:
    _spec, legacy, adapter, champion, branch = _runtime("cvrp")
    branch.branch_evidence_summary = {
        CANONICAL_SCREENING_HISTORY_KEY: {"not": "a list"}
    }

    with pytest.raises(ValueError, match="canonical screening history is invalid"):
        ContextManager(adapter=adapter).build_hypothesis_context(
            branch=branch,
            champion=champion,
            problem_spec=legacy,
            step_history=[],
        )


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
    snapshot = proposal_context_snapshot("code", context)
    blocks, user_prompt = _split_code_context(
        snapshot.inputs.provider_context(include_renderer_inputs=True)
    )
    rendered = "\n".join(block["text"] for block in blocks) + user_prompt
    ledger = context["proposal_source_ledger"]
    visibility = direct_v3_code_source_visibility(context)
    guarantees = visibility["code_phase_guarantees"]
    target = next(
        item for item in ledger["entries"] if item["path"] == target_file
    )

    assert target["visibility"] == "full_current"
    assert target["content"]
    assert target["digest"]
    assert context["approved_hypothesis"]["target_file"] == target_file
    assert "Use direct attribute access" in user_prompt
    assert "setattr, delattr, dynamic-name getattr" in user_prompt
    assert "process, network, environment, dynamic-import, or file APIs" in user_prompt
    assert guarantees["target_source_visible"] is True
    assert guarantees["protected_source_visible"] is True
    assert guarantees["required_integration_source_visible"] is True
    assert guarantees["algorithm_file_read_source_visible"] is True
    assert guarantees["missing_required_source_paths"] == []
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
    assert canonical["approved_hypothesis"]["target_file"] == target_file
    assert canonical["proposal_source_ledger"]["approved_target"] == target_file


def test_direct_v3_cvrp_create_ledger_proves_target_and_support_sources() -> None:
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
    ledger = context["proposal_source_ledger"]
    target = next(
        item for item in ledger["entries"] if item["path"] == target_file
    )
    guarantees = direct_v3_code_source_visibility(context)[
        "code_phase_guarantees"
    ]

    assert target["visibility"] == "new_file_placeholder"
    assert target_file not in ledger["views"]["api_reference"]
    assert ledger["views"]["api_reference"]
    assert ledger["views"]["integration_full"]
    assert ledger["views"]["champion_research"]
    assert guarantees["target_source_visible"] is True
    assert guarantees["protected_source_visible"] is True
    assert guarantees["required_integration_source_visible"] is True
    assert guarantees["algorithm_file_read_source_visible"] is True
    assert guarantees["missing_required_source_paths"] == []
