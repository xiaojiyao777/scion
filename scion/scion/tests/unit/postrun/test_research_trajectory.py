from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest

from scion.postrun.research_effectiveness import (
    ResearchTrajectoryInputError,
    calculate_research_trajectory,
    compare_history_trajectories,
)


def _hypothesis(name: str) -> dict[str, Any]:
    return {
        "text": f"hypothesis {name}",
        "action": "modify",
        "change_locus": "local_search",
        "target_file": "solver.py",
    }


def _patch(name: str) -> dict[str, Any]:
    return {
        "changes": [
            {
                "file_path": "solver.py",
                "action": "modify",
                "source": f"def improve(): return {name!r}\n",
            }
        ]
    }


def _step(
    round_num: int,
    branch: str,
    hypothesis: dict[str, Any],
    *,
    contract: bool,
    verification: bool,
    decision: str,
    stage: str | None = None,
    protocol_fields: dict[str, Any] | None = None,
    selected_basis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    protocol_result = None
    if stage is not None:
        protocol_result = {"stage": stage, **(protocol_fields or {})}
    return {
        "round": round_num,
        "branch_id": branch,
        "hypothesis": deepcopy(hypothesis),
        "selected_hypothesis_research_basis": deepcopy(selected_basis),
        "contract_passed": contract,
        "verification_passed": verification,
        "decision": decision,
        "protocol_result": protocol_result,
    }


def _runtime(charged: int, exported: int) -> dict[str, Any]:
    request_kinds = {
        "hypothesis": 0,
        "hypothesis_research_turn": 1,
        "code": 0,
        "code_research_turn": 0,
        "code_research_finalize": 0,
        "other": 0,
    }
    return {
        "provider_calls": {
            "budget_admitted": charged,
            "cap": 20,
            "remaining": 20 - charged,
            "by_request_kind": {"hypothesis_research_turn": charged},
        },
        "attempts": [
            {
                "round_num": index + 1,
                "accounting_state": "closed",
                "provider_calls": {
                    "budget_admitted": 1,
                    "by_request_kind": deepcopy(request_kinds),
                },
                "hypothesis_candidates_completed": 1,
                "hypothesis_candidates_selected": 1,
                "hypotheses_exported": 1,
                "patches_completed": 1,
                "code_candidates_ready": 1,
            }
            for index in range(exported)
        ],
    }


def _basis(*history_refs: str) -> dict[str, Any]:
    return {
        "read_refs": ["source-0001", *history_refs],
        "nearest_prior_refs": list(history_refs),
        "material_delta": "A material mechanism change.",
        "alternatives_considered": ["Keep the current mechanism."],
        "observable_prediction": "The declared metric improves.",
        "falsification_condition": "The declared metric does not improve.",
    }


def _complete_inputs() -> tuple[
    dict[str, Any],
    dict[str, Any],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    h1, h2, h3 = (_hypothesis(name) for name in ("one", "two", "three"))
    status = {"proposal_runtime": _runtime(11, 3)}
    summary = {
        "steps": [
            _step(
                1,
                "branch-a",
                h1,
                contract=True,
                verification=True,
                decision="continue_explore",
                stage="screening",
                selected_basis=_basis("history-selected-0001"),
            ),
            _step(
                2,
                "branch-b",
                h2,
                contract=False,
                verification=False,
                decision="abandon",
                selected_basis=_basis(),
            ),
            _step(
                3,
                "branch-a",
                h3,
                contract=True,
                verification=True,
                decision="expand_screening",
                stage="screening",
                selected_basis=_basis("history-selected-0002"),
            ),
            _step(
                4,
                "branch-a",
                h3,
                contract=True,
                verification=True,
                decision="queue_validate",
                stage="screening",
            ),
            _step(
                5,
                "branch-a",
                h3,
                contract=True,
                verification=True,
                decision="queue_frozen",
                stage="validation",
            ),
            _step(
                6,
                "branch-a",
                h3,
                contract=True,
                verification=True,
                decision="promote",
                stage="frozen",
            ),
        ]
    }
    history = [
        {"hypothesis": deepcopy(h1), "patch": _patch("one")},
        {"hypothesis": deepcopy(h2), "patch": _patch("two")},
        {"hypothesis": deepcopy(h3), "patch": _patch("three")},
        {"hypothesis": deepcopy(h3), "patch": _patch("three")},
    ]
    traces = [
        {
            "request_kind": "hypothesis_research_turn",
            "ok": True,
            "response": {"action": "read_history", "ref": "history-0001"},
        },
        {"action": "search_history", "query": "local", "ref": "history-0002"},
        {
            "request_kind": "hypothesis_research_turn",
            "ok": True,
            "response": {
                "action": "stage_hypothesis_candidate",
                "research_basis": {
                    "read_refs": [
                        "source-0001",
                        "history-unselected-0001",
                        "history-unselected-0002",
                        "history-unselected-0003",
                    ],
                    "nearest_prior_refs": [
                        "history-unselected-0001",
                        "history-unselected-0002",
                        "history-unselected-0003",
                    ],
                },
            },
        },
        {
            "request_kind": "code_research_turn",
            "ok": True,
            "response": {"action": "search_history", "query": "ignored"},
        },
    ]
    return status, summary, history, traces


def test_calculates_continuous_research_endpoints_without_io(monkeypatch) -> None:
    status, summary, history, traces = _complete_inputs()
    originals = deepcopy((status, summary, history, traces))

    def forbidden_open(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("trajectory evaluation must not read artifacts")

    monkeypatch.setattr("builtins.open", forbidden_open)
    report = calculate_research_trajectory(
        status=status,
        campaign_summary=summary,
        research_history=history,
        hypothesis_research_traces=traces,
    )

    assert (status, summary, history, traces) == originals
    metrics = report["metrics"]
    assert metrics["provider_calls"] == {"charged": 11}
    assert metrics["throughput"]["distinct_formal_h_per_charged_call"] == pytest.approx(
        3 / 11
    )
    assert metrics["hypotheses"] == {
        "formal": 3,
        "observed": 3,
        "distinct": 3,
        "replays": 0,
        "h_patch_observed": 3,
        "distinct_h_patch": 3,
        "h_patch_replays": 0,
    }
    assert metrics["contract"] == {"attempted": 3, "passed": 2, "failed": 1}
    assert metrics["verification"] == {
        "attempted": 2,
        "passed": 2,
        "failed": 0,
    }
    assert metrics["stage_reach"] == {
        "screening": {"steps": 3, "branches": 1},
        "validation": {"steps": 1, "branches": 1},
        "frozen": {"steps": 1, "branches": 1},
    }
    assert metrics["decision_counts"] == {
        "continue_explore": 1,
        "expand_screening": 1,
        "queue_validate": 1,
        "expand_validation": 0,
        "queue_frozen": 1,
        "promote": 1,
        "abandon": 1,
    }
    assert metrics["promotions"] == 1
    assert metrics["max_branch_depth"] == 2
    assert metrics["first_round"] == {
        "hypothesis": 1,
        "contract": 1,
        "verification": 1,
        "screening": 1,
        "validation": 5,
        "frozen": 6,
        "promotion": 6,
    }
    assert metrics["history_use"] == {
        "all_deliberation": {
            "read_actions": 1,
            "search_actions": 1,
            "action_reference_mentions": 2,
            "distinct_action_references": 2,
        },
        "selected_h_basis": {
            "episodes": 3,
            "basis_observed_episodes": 3,
            "basis_missing_episodes": 0,
            "basis_history_read_references": 2,
            "distinct_basis_history_read_references": 2,
            "citations": 2,
            "distinct_citations": 2,
        },
    }
    assert report["observability"]["selected_h_basis"] == "complete"


def test_direct_runtime_falls_back_to_hypothesis_episodes() -> None:
    h1, h2 = _hypothesis("one"), _hypothesis("two")
    summary = {
        "steps": [
            _step(
                1,
                "branch-a",
                h1,
                contract=True,
                verification=True,
                decision="expand_screening",
                stage="screening",
            ),
            _step(
                2,
                "branch-a",
                h1,
                contract=True,
                verification=True,
                decision="queue_validate",
                stage="screening",
            ),
            _step(
                3,
                "branch-a",
                h1,
                contract=True,
                verification=True,
                decision="queue_frozen",
                stage="validation",
            ),
            _step(
                4,
                "branch-a",
                h2,
                contract=True,
                verification=True,
                decision="continue_explore",
                stage="screening",
            ),
            _step(
                5,
                "branch-a",
                h2,
                contract=True,
                verification=True,
                decision="abandon",
                stage="screening",
            ),
        ]
    }

    report = calculate_research_trajectory(
        status={},
        campaign_summary=summary,
        research_history=[
            {"hypothesis": h1, "patch": _patch("one")},
            {"hypothesis": h1, "patch": _patch("one")},
            {"hypothesis": h2, "patch": _patch("two")},
            {"hypothesis": h2, "patch": _patch("two")},
        ],
    )

    assert report["metrics"]["provider_calls"]["charged"] is None
    assert report["metrics"]["hypotheses"] == {
        "formal": 3,
        "observed": 3,
        "distinct": 2,
        "replays": 1,
        "h_patch_observed": 3,
        "distinct_h_patch": 2,
        "h_patch_replays": 1,
    }
    assert report["metrics"]["max_branch_depth"] == 3
    assert report["observability"]["formal_h"] == "summary_hypothesis_episodes"
    assert report["observability"]["h_patch_endpoints"] == (
        "summary_history_order_alignment"
    )


def test_patch_endpoints_are_unavailable_when_history_cannot_align() -> None:
    h = _hypothesis("one")
    report = calculate_research_trajectory(
        status={},
        campaign_summary={
            "steps": [
                _step(
                    1,
                    "branch-a",
                    h,
                    contract=True,
                    verification=True,
                    decision="continue_explore",
                    stage="screening",
                )
            ]
        },
        research_history=[],
    )

    hypotheses = report["metrics"]["hypotheses"]
    assert hypotheses["h_patch_observed"] is None
    assert hypotheses["distinct_h_patch"] is None
    assert hypotheses["h_patch_replays"] is None
    assert report["observability"]["h_patch_endpoints"] == "unavailable"
    selected = report["metrics"]["history_use"]["selected_h_basis"]
    assert selected["episodes"] == 1
    assert selected["basis_observed_episodes"] == 0
    assert selected["basis_missing_episodes"] == 1
    assert selected["basis_history_read_references"] is None
    assert selected["citations"] is None
    assert report["observability"]["selected_h_basis"] == "partial"


def test_execution_outcome_stage_excludes_heldout_step_from_episode_alignment() -> None:
    h = _hypothesis("heldout-provenance")
    visible = _step(
        1,
        "branch-a",
        h,
        contract=True,
        verification=True,
        decision="queue_validate",
        stage="screening",
    )
    heldout = _step(
        2,
        "branch-a",
        h,
        contract=True,
        verification=True,
        decision="continue_explore",
    )
    heldout["execution_outcome"] = {
        "outcome": "not_evaluated",
        "reason_code": "VALIDATION_INTERRUPTED",
        "provenance": {"stage": "validation"},
    }

    report = calculate_research_trajectory(
        status={},
        campaign_summary={"steps": [visible, heldout]},
        research_history=[{"hypothesis": h, "patch": _patch("heldout")}],
    )

    assert report["metrics"]["hypotheses"]["observed"] == 1
    assert report["metrics"]["hypotheses"]["h_patch_observed"] == 1
    assert report["metrics"]["contract"] == {
        "attempted": 1,
        "passed": 1,
        "failed": 0,
    }
    assert report["observability"]["h_patch_endpoints"] == (
        "summary_history_order_alignment"
    )


def test_execution_outcome_provenance_shape_is_validated() -> None:
    step = _step(
        1,
        "branch-a",
        _hypothesis("bad-provenance"),
        contract=True,
        verification=True,
        decision="continue_explore",
        stage="screening",
    )
    step["execution_outcome"] = {"provenance": "validation"}

    with pytest.raises(ResearchTrajectoryInputError) as exc_info:
        calculate_research_trajectory(
            status={}, campaign_summary={"steps": [step]}, research_history=[]
        )

    assert exc_info.value.code == "SUMMARY_EXECUTION_OUTCOME_PROVENANCE_INVALID"


def test_reads_real_proposal_runtime_attempt_shape() -> None:
    h = _hypothesis("runtime-shape")
    report = calculate_research_trajectory(
        status={"proposal_runtime": _runtime(3, 1)},
        campaign_summary={
            "steps": [
                _step(
                    1,
                    "branch-a",
                    h,
                    contract=True,
                    verification=True,
                    decision="continue_explore",
                    stage="screening",
                )
            ]
        },
        research_history=[{"hypothesis": h, "patch": _patch("runtime-shape")}],
    )

    assert report["metrics"]["provider_calls"] == {"charged": 3}
    assert report["metrics"]["hypotheses"]["formal"] == 1
    assert report["observability"]["hypothesis_endpoints"] == (
        "proposal_runtime_attempt_rounds"
    )


def test_history_comparison_reports_every_endpoint_without_a_go_score() -> None:
    status, summary, history, traces = _complete_inputs()
    history_on = calculate_research_trajectory(
        status=status,
        campaign_summary=summary,
        research_history=history,
        hypothesis_research_traces=traces,
    )
    history_off = calculate_research_trajectory(
        status={"proposal_runtime": _runtime(8, 1)},
        campaign_summary={"steps": [summary["steps"][0]]},
        research_history=[history[0]],
    )

    comparison = compare_history_trajectories(
        history_on=history_on,
        history_off=history_off,
    )

    endpoints = comparison["endpoints"]
    assert endpoints["provider_calls.charged"] == {
        "history_on": 11,
        "history_off": 8,
        "difference_on_minus_off": 3,
    }
    throughput = endpoints["throughput.distinct_formal_h_per_charged_call"]
    assert throughput["history_on"] == pytest.approx(3 / 11)
    assert throughput["history_off"] == pytest.approx(1 / 8)
    assert throughput["difference_on_minus_off"] == pytest.approx(3 / 11 - 1 / 8)
    assert endpoints["hypotheses.distinct"]["difference_on_minus_off"] == 2
    assert endpoints["decision_counts.promote"]["difference_on_minus_off"] == 1
    assert "screening_quality.gate_counts.missing" in endpoints
    assert "history_use.all_deliberation.read_actions" in endpoints
    assert "history_use.selected_h_basis.citations" in endpoints
    assert "candidate_safety.failure_categories.timeout" in endpoints
    assert (
        "candidate_safety.candidate_only_timeout_rate_per_attempted_pair" in endpoints
    )
    assert (
        "candidate_safety.candidate_only_infeasible_rate_per_attempted_pair"
        in endpoints
    )
    assert "campaign_outcome.execution_outcomes.interrupted" in endpoints
    assert endpoints["first_round.validation"] == {
        "history_on": 5,
        "history_off": None,
        "difference_on_minus_off": None,
    }
    rendered_keys = " ".join(comparison).lower()
    assert "go" not in rendered_keys
    assert "score" not in rendered_keys


def test_reports_fixed_screening_quality_safety_and_terminal_endpoints() -> None:
    first = {
        "median_delta": 3.0,
        "ci_low": 0.5,
        "ci_high": 5.5,
        "statistical_status": "positive",
        "gate_outcome": "expand",
        "reason_codes": ["SCREENING_FAIL_PROTECTED_OBJECTIVE_REGRESSION"],
        "total_pairs": 6,
        "attempted_pairs": 6,
        "valid_pairs": 4,
        "failed_pairs": 2,
        "candidate_failed_pairs": 1,
        "champion_failed_pairs": 1,
        "shared_failed_pairs": 1,
        "bilateral_failed_pairs": 0,
        "screening_case_wins": 2,
        "screening_case_losses": 0,
        "screening_case_ties": 1,
        "screening_case_total": 3,
        "screening_pair_wins": 3,
        "screening_pair_losses": 1,
        "screening_pair_ties": 0,
        "screening_pair_total": 4,
        "candidate_attributable_infeasible_pairs": 1,
        "candidate_only_timeout_pairs": 1,
        "candidate_only_invalid_output_pairs": 1,
        "candidate_runtime_failure_categories": {
            "timeout": 2,
            "invalid_output": 1,
            "surface_contract_error": 1,
        },
        "candidate_runtime_stop_reasons": {"time_limit": 4, "completed": 2},
    }
    second = {
        "median_delta": -1.0,
        "ci_low": -4.0,
        "ci_high": 2.0,
        "statistical_status": "uncertain",
        "gate_outcome": "fail",
        "reason_codes": [],
        "total_pairs": 12,
        "attempted_pairs": 10,
        "valid_pairs": 9,
        "failed_pairs": 1,
        "candidate_failed_pairs": 1,
        "champion_failed_pairs": 1,
        "shared_failed_pairs": 0,
        "bilateral_failed_pairs": 1,
        "screening_case_wins": 1,
        "screening_case_losses": 2,
        "screening_case_ties": 3,
        "screening_case_total": 6,
        "screening_pair_wins": 2,
        "screening_pair_losses": 3,
        "screening_pair_ties": 4,
        "screening_pair_total": 9,
        "candidate_attributable_infeasible_pairs": 0,
        "candidate_only_timeout_pairs": 0,
        "candidate_only_invalid_output_pairs": 0,
        "candidate_runtime_failure_categories": {
            "oom": 1,
            "crash": 2,
            "process_error": 3,
            "operator_error": 4,
            "policy_error": 5,
            "construction_error": 6,
            "portfolio_error": 7,
            "unclassified_runtime_error": 8,
        },
        "candidate_runtime_stop_reasons": {"time_limit": 2},
    }
    h1, h2 = _hypothesis("quality-one"), _hypothesis("quality-two")
    run_result = {
        "status": "stopped",
        "requested_rounds": 2,
        "evaluated_rounds": 1,
        "scheduled_calls": 3,
        "formal_screened_candidates": 2,
        "protocol_stage_counts": {"screening": 2, "validation": 0, "frozen": 0},
        "failure_categories": {},
        "execution_outcome_counts": {
            "evaluated": 1,
            "research_rejected": 1,
            "not_evaluated": 0,
            "blocked_infra": 0,
            "resource_exhausted": 0,
            "interrupted": 1,
        },
        "unknown_outcome_count": 0,
        "last_execution_outcome": {
            "outcome": "interrupted",
            "reason_code": "OUTER_HARDWALL",
            "stage": "screening",
        },
        "run_validity": {
            "status": "valid",
            "reason": "valid_incomplete",
            "valid": True,
        },
        "stop_reason": "signal_SIGTERM",
    }
    report = calculate_research_trajectory(
        status={"run_result": deepcopy(run_result)},
        campaign_summary={
            "run_result": deepcopy(run_result),
            "steps": [
                _step(
                    1,
                    "branch-a",
                    h1,
                    contract=True,
                    verification=True,
                    decision="expand_screening",
                    stage="screening",
                    protocol_fields=first,
                ),
                _step(
                    2,
                    "branch-a",
                    h2,
                    contract=True,
                    verification=True,
                    decision="continue_explore",
                    stage="screening",
                    protocol_fields=second,
                ),
            ],
        },
        research_history=[
            {"hypothesis": h1, "patch": _patch("quality-one")},
            {"hypothesis": h2, "patch": _patch("quality-two")},
        ],
    )

    quality = report["metrics"]["screening_quality"]
    assert quality["gate_counts"] == {
        "pass": 0,
        "fail": 1,
        "expand": 1,
        "unclear": 0,
        "missing": 0,
    }
    assert quality["statistical_counts"] == {
        "positive": 1,
        "negative": 0,
        "tie": 0,
        "uncertain": 1,
        "missing": 0,
    }
    assert quality["pair_counts"] == {
        "opportunities": 2,
        "total_pairs": 18,
        "attempted_pairs": 16,
        "valid_pairs": 13,
        "failed_pairs": 3,
        "candidate_failed_pairs": 2,
        "champion_failed_pairs": 2,
        "shared_failed_pairs": 1,
        "bilateral_failed_pairs": 1,
        "accounting_observed_opportunities": 2,
        "accounting_complete_opportunities": 2,
        "accounting_incomplete_opportunities": 0,
        "attribution_observed_opportunities": 2,
        "attribution_complete_opportunities": 2,
        "attribution_incomplete_opportunities": 0,
        "case_wlt_observed_opportunities": 2,
        "case_wlt_complete_opportunities": 2,
        "case_wlt_incomplete_opportunities": 0,
        "pair_wlt_observed_opportunities": 2,
        "pair_wlt_complete_opportunities": 2,
        "pair_wlt_incomplete_opportunities": 0,
    }
    assert quality["protected_regressions"] == {
        "screening": 1,
        "validation": 0,
        "frozen": 0,
        "total": 1,
        "reason_codes_observed_opportunities": 2,
        "reason_codes_missing_opportunities": 0,
    }
    assert quality["opportunity_sequence"] == {
        "observed": 2,
        "beyond_fixed_slots": 0,
        "slot_1": {
            "round": 1,
            "gate_outcome": {
                "pass": 0,
                "fail": 0,
                "expand": 1,
                "unclear": 0,
            },
            "statistical_status": {
                "positive": 1,
                "negative": 0,
                "tie": 0,
                "uncertain": 0,
            },
            "median_delta": 3.0,
            "ci_low": 0.5,
            "ci_high": 5.5,
            "case_wins": 2,
            "case_losses": 0,
            "case_ties": 1,
            "case_total": 3,
            "pair_wins": 3,
            "pair_losses": 1,
            "pair_ties": 0,
            "pair_total": 4,
            "protected_regression": 1,
        },
        "slot_2": {
            "round": 2,
            "gate_outcome": {
                "pass": 0,
                "fail": 1,
                "expand": 0,
                "unclear": 0,
            },
            "statistical_status": {
                "positive": 0,
                "negative": 0,
                "tie": 0,
                "uncertain": 1,
            },
            "median_delta": -1.0,
            "ci_low": -4.0,
            "ci_high": 2.0,
            "case_wins": 1,
            "case_losses": 2,
            "case_ties": 3,
            "case_total": 6,
            "pair_wins": 2,
            "pair_losses": 3,
            "pair_ties": 4,
            "pair_total": 9,
            "protected_regression": 0,
        },
    }

    safety = report["metrics"]["candidate_safety"]
    assert safety["pair_rate_denominator_attempted_pairs"] == 16
    assert safety["candidate_only_timeout_pairs"] == 1
    assert safety["candidate_only_invalid_output_pairs"] == 1
    assert safety["candidate_only_infeasible_pairs"] == 1
    assert safety["candidate_only_timeout_rate_per_attempted_pair"] == pytest.approx(
        1 / 16
    )
    assert safety[
        "candidate_only_invalid_output_rate_per_attempted_pair"
    ] == pytest.approx(1 / 16)
    assert safety["candidate_only_infeasible_rate_per_attempted_pair"] == pytest.approx(
        1 / 16
    )
    assert safety["pair_rate_completeness"] == {
        "opportunities": 2,
        "attempted_pairs_observed_opportunities": 2,
        "attempted_pairs_missing_opportunities": 0,
        "timeout_observed_opportunities": 2,
        "timeout_missing_opportunities": 0,
        "invalid_output_observed_opportunities": 2,
        "invalid_output_missing_opportunities": 0,
        "infeasible_observed_opportunities": 2,
        "infeasible_missing_opportunities": 0,
    }
    assert safety["normal_time_limit_stops"] == 6
    assert safety["failure_categories"] == {
        "timeout": 2,
        "oom": 1,
        "crash": 2,
        "process_error": 3,
        "invalid_output": 1,
        "operator_error": 4,
        "policy_error": 5,
        "construction_error": 6,
        "portfolio_error": 7,
        "surface_contract_error": 1,
        "other": 8,
    }
    assert safety["failure_categories"]["timeout"] != safety["normal_time_limit_stops"]

    campaign = report["metrics"]["campaign_outcome"]
    assert campaign["available"] == 1
    assert campaign["terminal_status"] == {
        "completed": 0,
        "stopped": 1,
        "running": 0,
    }
    assert campaign["execution_outcomes"]["interrupted"] == 1
    assert campaign["typed_execution_outcomes"] == 3
    assert campaign["unknown_execution_outcomes"] == 0
    assert campaign["requested_rounds_complete"] == 0
    assert campaign["outcome_accounting_complete"] == 1
    assert campaign["run_valid"] == 1
    assert report["observability"]["campaign_outcome"] == (
        "campaign_summary.run_result"
    )


def test_missing_screening_and_campaign_fields_keep_fixed_none_slots() -> None:
    report = calculate_research_trajectory(
        status={},
        campaign_summary={"steps": []},
        research_history=[],
    )

    sequence = report["metrics"]["screening_quality"]["opportunity_sequence"]
    assert sequence["slot_1"]["median_delta"] is None
    assert sequence["slot_1"]["gate_outcome"]["expand"] is None
    assert sequence["slot_1"]["statistical_status"]["positive"] is None
    assert sequence["slot_2"]["pair_total"] is None
    campaign = report["metrics"]["campaign_outcome"]
    assert campaign["available"] == 0
    assert campaign["execution_outcomes"]["evaluated"] is None
    assert campaign["outcome_accounting_complete"] is None


def test_candidate_safety_rates_fail_closed_for_zero_and_missing_denominators() -> None:
    hypothesis = _hypothesis("pair-rate-completeness")

    def safety(protocol_fields: dict[str, Any]) -> dict[str, Any]:
        report = calculate_research_trajectory(
            status={},
            campaign_summary={
                "steps": [
                    _step(
                        1,
                        "branch-a",
                        hypothesis,
                        contract=True,
                        verification=True,
                        decision="continue_explore",
                        stage="screening",
                        protocol_fields=protocol_fields,
                    )
                ]
            },
            research_history=[],
        )
        return report["metrics"]["candidate_safety"]

    zero = safety(
        {
            "attempted_pairs": 0,
            "candidate_only_timeout_pairs": 0,
            "candidate_only_invalid_output_pairs": 0,
            "candidate_attributable_infeasible_pairs": 0,
        }
    )
    assert zero["pair_rate_denominator_attempted_pairs"] == 0
    assert zero["candidate_only_timeout_rate_per_attempted_pair"] is None
    assert zero["candidate_only_invalid_output_rate_per_attempted_pair"] is None
    assert zero["candidate_only_infeasible_rate_per_attempted_pair"] is None

    legacy = safety(
        {
            "attempted_pairs": 4,
            "candidate_attributable_infeasible_pairs": 0,
        }
    )
    assert legacy["pair_rate_denominator_attempted_pairs"] == 4
    assert legacy["candidate_only_timeout_pairs"] is None
    assert legacy["candidate_only_invalid_output_pairs"] is None
    assert legacy["candidate_only_infeasible_pairs"] == 0
    assert legacy["candidate_only_timeout_rate_per_attempted_pair"] is None
    assert legacy["candidate_only_invalid_output_rate_per_attempted_pair"] is None
    assert legacy["candidate_only_infeasible_rate_per_attempted_pair"] == 0.0
    assert legacy["pair_rate_completeness"]["timeout_missing_opportunities"] == 1
    assert legacy["pair_rate_completeness"]["invalid_output_missing_opportunities"] == 1

    missing_denominator = safety(
        {
            "candidate_only_timeout_pairs": 0,
            "candidate_only_invalid_output_pairs": 0,
            "candidate_attributable_infeasible_pairs": 0,
        }
    )
    assert missing_denominator["pair_rate_denominator_attempted_pairs"] is None
    assert missing_denominator["candidate_only_timeout_rate_per_attempted_pair"] is None
    assert (
        missing_denominator["candidate_only_invalid_output_rate_per_attempted_pair"]
        is None
    )
    assert (
        missing_denominator["candidate_only_infeasible_rate_per_attempted_pair"] is None
    )
    assert (
        missing_denominator["pair_rate_completeness"][
            "attempted_pairs_missing_opportunities"
        ]
        == 1
    )


@pytest.mark.parametrize(
    ("status", "summary", "history", "traces", "code"),
    (
        ({}, {"steps": "not-a-list"}, [], [], "SUMMARY_STEPS_INVALID"),
        (
            {},
            {"steps": []},
            [{"hypothesis": None, "patch": {}}],
            [],
            "RESEARCH_HISTORY_PATCH_WITHOUT_HYPOTHESIS",
        ),
        (
            {},
            {"steps": []},
            [],
            [{"action": "read_history"}],
            "HYPOTHESIS_HISTORY_READ_REF_INVALID",
        ),
    ),
)
def test_rejects_malformed_consumed_fields(
    status: dict[str, Any],
    summary: dict[str, Any],
    history: list[dict[str, Any]],
    traces: list[dict[str, Any]],
    code: str,
) -> None:
    with pytest.raises(ResearchTrajectoryInputError) as exc_info:
        calculate_research_trajectory(
            status=status,
            campaign_summary=summary,
            research_history=history,
            hypothesis_research_traces=traces,
        )

    assert exc_info.value.code == code
