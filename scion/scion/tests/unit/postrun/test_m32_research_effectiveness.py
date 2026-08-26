from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

import pytest

from scion.core.research_history import normalize_research_history_record
from scion.postrun.research_effectiveness import (
    CANDIDATE_FEASIBILITY_EVIDENCE_UNAVAILABLE,
    HISTORY_REPLAY_BASIS_UNAVAILABLE,
    InitialCell,
    LoadedHistoryAvailable,
    LoadedHistoryUnavailable,
    ResearchEffectivenessExpectation,
    calculate_research_effectiveness,
)

_KINDS = (
    "hypothesis",
    "hypothesis_research_turn",
    "code",
    "code_research_turn",
    "code_research_finalize",
    "other",
)
_OUTCOMES = (
    "evaluated",
    "research_rejected",
    "not_evaluated",
    "blocked_infra",
    "resource_exhausted",
    "interrupted",
)


def _expectation(*, a_cap: int = 2, p_cap: int = 10, k: int = 1):
    return ResearchEffectivenessExpectation(
        problem_id="demo",
        expected_initial_case_count=2,
        expected_initial_pair_count=2,
        a_cap=a_cap,
        p_cap=p_cap,
        max_hypothesis_candidates=k,
    )


def _hypothesis(text: str = "bounded exact hypothesis") -> dict[str, Any]:
    return {
        "text": text,
        "change_locus": "local_search",
        "action": "modify",
        "target_file": "operators/local_search.py",
        "predicted_direction": "improve",
        "target_weakness": "weak neighborhood",
        "expected_effect": "lower distance",
        "suggested_weight": None,
    }


def _patch(source: str = "def improve():\n    return 1\n") -> dict[str, Any]:
    return {
        "changes": [
            {
                "file_path": "operators/local_search.py",
                "action": "modify",
                "source": source,
            }
        ]
    }


def _screening_record(
    *,
    hypothesis: dict[str, Any] | None = None,
    patch: dict[str, Any] | None = None,
    gate: str = "expand",
    decision: str = "expand_screening",
) -> dict[str, Any]:
    hypothesis = deepcopy(hypothesis or _hypothesis())
    patch = deepcopy(patch or _patch())
    aggregate = {
        "n_cases": 2,
        "wins": 1,
        "losses": 0,
        "ties": 1,
        "total_pairs": 2,
        "attempted_pairs": 2,
        "valid_pairs": 2,
        "failed_pairs": 0,
        "candidate_failed_pairs": 0,
        "champion_failed_pairs": 0,
        "shared_failed_pairs": 0,
        "bilateral_failed_pairs": 0,
        "pair_wins": 1,
        "pair_losses": 0,
        "pair_ties": 1,
    }
    return normalize_research_history_record(
        {
            "schema_version": "scion.research_history.step.v1",
            "problem_id": "demo",
            "hypothesis": hypothesis,
            "patch": patch,
            "outcome": {
                "outcome": "evaluated",
                "stage": "screening",
                "reason_code": "EVALUATION_COMPLETED",
            },
            "protocol": {
                "candidate_composition": {},
                "evidence": {
                    "stage": "screening",
                    "runtime_model": "comparative",
                    "protocol_outcome": {
                        "gate_outcome": gate,
                        "reason_codes": [],
                    },
                    "objective_outcome": {
                        "semantics": "declared_objectives_lexicographic",
                        "aggregate": aggregate,
                        "aggregation": {},
                    },
                    "case_outcomes": {"case_feedback": []},
                },
            },
            "decision": {
                "value": decision,
                "reason_codes": [],
                "engine_reason_codes": [],
                "diagnostic_reason_codes": [],
                "bypass_reason_codes": [],
            },
        },
        expected_problem_id="demo",
    )


def _hypothesis_free_record(*, outcome: str, reason_code: str) -> dict[str, Any]:
    return normalize_research_history_record(
        {
            "schema_version": "scion.research_history.step.v1",
            "problem_id": "demo",
            "hypothesis": None,
            "patch": None,
            "outcome": {
                "outcome": outcome,
                "stage": "proposal_hypothesis",
                "reason_code": reason_code,
            },
            "protocol": None,
            "decision": None,
        },
        expected_problem_id="demo",
    )


def _canary_record(
    *,
    hypothesis: dict[str, Any] | None = None,
    patch: dict[str, Any] | None = None,
    canary_code: str = "CANARY_FAILED",
) -> dict[str, Any]:
    decision_reason_codes = ["CANARY_FAILED"]
    if canary_code != "CANARY_FAILED":
        decision_reason_codes.append(canary_code)
    return normalize_research_history_record(
        {
            "schema_version": "scion.research_history.step.v1",
            "problem_id": "demo",
            "hypothesis": deepcopy(hypothesis or _hypothesis()),
            "patch": deepcopy(patch or _patch()),
            "outcome": {
                "outcome": "evaluated",
                "stage": "canary",
                "reason_code": "EVALUATION_COMPLETED",
            },
            "protocol": None,
            "decision": {
                "value": "abandon",
                "reason_codes": decision_reason_codes,
                "engine_reason_codes": [],
                "diagnostic_reason_codes": [],
                "bypass_reason_codes": [],
            },
        },
        expected_problem_id="demo",
    )


def _protocol_failure(
    record: dict[str, Any],
    *,
    candidate: int,
    champion: int,
    shared: int = 0,
    bilateral: int = 0,
    protected: bool = False,
) -> dict[str, Any]:
    value = deepcopy(record)
    aggregate = value["protocol"]["evidence"]["objective_outcome"]["aggregate"]
    failed = candidate + champion - bilateral
    valid = 2 - failed
    aggregate.update(
        {
            "attempted_pairs": 2,
            "valid_pairs": valid,
            "failed_pairs": failed,
            "candidate_failed_pairs": candidate,
            "champion_failed_pairs": champion,
            "shared_failed_pairs": shared,
            "bilateral_failed_pairs": bilateral,
            "pair_wins": min(1, valid),
            "pair_losses": 0,
            "pair_ties": max(0, valid - 1),
        }
    )
    if protected:
        aggregate["protected_objective_regressions"] = ["fleet_violation"]
    value["decision"]["value"] = (
        "abandon" if candidate - bilateral > 0 else "continue_explore"
    )
    value["protocol"]["evidence"]["protocol_outcome"]["gate_outcome"] = "fail"
    return normalize_research_history_record(value, expected_problem_id="demo")


def _summary_step(round_num: int, record: dict[str, Any]) -> dict[str, Any]:
    hypothesis = record["hypothesis"]
    outcome = record["outcome"]
    step: dict[str, Any] = {
        "round": round_num,
        "decision": record["decision"]["value"] if record["decision"] else None,
        "decision_reason_codes": (
            list(record["decision"]["reason_codes"]) if record["decision"] else []
        ),
        "diagnostic_reason_codes": (
            list(record["decision"]["diagnostic_reason_codes"])
            if record["decision"]
            else []
        ),
        "bypass_reason_codes": (
            list(record["decision"]["bypass_reason_codes"])
            if record["decision"]
            else []
        ),
        "contract_passed": True if hypothesis is not None else None,
        "verification_passed": (
            True
            if record["protocol"] is not None or outcome["stage"] == "canary"
            else None
        ),
        "failure_stage": outcome["stage"] if record["protocol"] is None else None,
        "failure_detail": (
            outcome["reason_code"] if record["protocol"] is None else None
        ),
        "hypothesis": (
            {
                "text": hypothesis["text"],
                "action": hypothesis["action"],
                "change_locus": hypothesis["change_locus"],
                "target_file": hypothesis["target_file"],
            }
            if hypothesis is not None
            else None
        ),
        "execution_outcome": {
            "outcome": outcome["outcome"],
            "reason_code": outcome["reason_code"],
            "provenance": {"stage": outcome["stage"]},
        },
    }
    if record["protocol"] is None:
        if outcome["stage"] == "canary":
            step["canary_result"] = {
                "passed": False,
                "failure_category": "candidate_failure",
                "reason_codes": [record["decision"]["reason_codes"][-1]],
                "candidate_attributable_infeasible_pairs": 0,
            }
        step["protocol_result"] = None
        return step
    aggregate = record["protocol"]["evidence"]["objective_outcome"]["aggregate"]
    step["canary_result"] = {
        "passed": True,
        "candidate_attributable_infeasible_pairs": 0,
    }
    step["protocol_result"] = {
        "stage": "screening",
        "candidate_attributable_infeasible_pairs": 0,
        **{
            key: aggregate[key]
            for key in (
                "n_cases",
                "total_pairs",
                "attempted_pairs",
                "valid_pairs",
                "failed_pairs",
                "candidate_failed_pairs",
                "champion_failed_pairs",
                "shared_failed_pairs",
                "bilateral_failed_pairs",
            )
        },
        "gate_outcome": record["protocol"]["evidence"]["protocol_outcome"][
            "gate_outcome"
        ],
        "reason_codes": list(
            record["protocol"]["evidence"]["protocol_outcome"]["reason_codes"]
        ),
        "screening_case_wins": aggregate["wins"],
        "screening_case_losses": aggregate["losses"],
        "screening_case_ties": aggregate["ties"],
        "screening_case_total": aggregate["n_cases"],
        "screening_pair_wins": aggregate["pair_wins"],
        "screening_pair_losses": aggregate["pair_losses"],
        "screening_pair_ties": aggregate["pair_ties"],
        "screening_pair_total": aggregate["valid_pairs"],
    }
    return step


def _attempt(
    round_num: int,
    calls: dict[str, int],
    *,
    completed: int = 0,
    selected: int = 0,
    exported: int = 0,
    patches: int = 0,
    ready: int = 0,
) -> dict[str, Any]:
    by_kind = {kind: calls.get(kind, 0) for kind in _KINDS}
    return {
        "round_num": round_num,
        "accounting_state": "closed",
        "provider_calls": {
            "budget_admitted": sum(by_kind.values()),
            "by_request_kind": by_kind,
        },
        "hypothesis_candidates_completed": completed,
        "hypothesis_candidates_selected": selected,
        "hypotheses_exported": exported,
        "patches_completed": patches,
        "code_candidates_ready": ready,
    }


def _artifacts(
    *,
    expectation: ResearchEffectivenessExpectation,
    records: list[dict[str, Any]],
    attempts: list[dict[str, Any]],
    stop_reason: str = "qualification_not_reached",
    disposition: str = "qualification_not_reached",
) -> tuple[dict[str, Any], dict[str, Any]]:
    steps = [_summary_step(index, record) for index, record in enumerate(records, 1)]
    attempt_rounds = {attempt["round_num"] for attempt in attempts}
    current_branch_id = ""
    for step in steps:
        if step["round"] in attempt_rounds:
            current_branch_id = f"branch-{step['round']}"
        step["branch_id"] = current_branch_id
    by_kind = {
        kind: sum(
            attempt["provider_calls"]["by_request_kind"][kind] for attempt in attempts
        )
        for kind in _KINDS
    }
    p_charged = sum(by_kind.values())
    runtime = {
        "provider_calls": {
            "budget_admitted": p_charged,
            "cap": expectation.p_cap,
            "remaining": expectation.p_cap - p_charged,
            "by_request_kind": by_kind,
        },
        "attempts": attempts,
    }
    protocol_count = sum(record["protocol"] is not None for record in records)
    initial_count = sum(
        record["protocol"] is not None and index in attempt_rounds
        for index, record in enumerate(records, 1)
    )
    verified_count = len(
        {
            step["branch_id"]
            for step in steps
            if step["verification_passed"] is True and step["round"] in attempt_rounds
        }
    )
    outcomes = {
        name: sum(record["outcome"]["outcome"] == name for record in records)
        for name in _OUTCOMES
    }
    failure_categories: dict[str, int] = {}
    for step, record in zip(steps, records):
        if not step["failure_stage"] and not step["failure_detail"]:
            continue
        canary = step.get("canary_result")
        if record["outcome"]["outcome"] == "research_rejected":
            category = "research_rejected"
        elif record["outcome"]["outcome"] != "evaluated":
            category = record["outcome"]["outcome"]
        elif isinstance(canary, dict) and canary.get("passed") is False:
            category = str(canary["failure_category"])
        else:
            category = str(step["failure_stage"])
        failure_categories[category] = failure_categories.get(category, 0) + 1
    incomplete = any(outcomes[name] for name in _OUTCOMES[2:])
    qualification = {
        "mode": "qualification_only",
        "limits": {
            "max_proposal_attempts": expectation.a_cap,
            "max_verified_candidate_chains": 2,
            "max_formal_screening_stages": 4,
        },
        "proposal_attempts": len(attempts),
        "verified_candidate_chains": verified_count,
        "formal_screening_stages": protocol_count,
        "initial_screening_stages": initial_count,
        "expanded_screening_stages": protocol_count - initial_count,
        "disposition": disposition,
    }
    run = {
        "status": "stopped" if incomplete else "completed",
        "requested_rounds": 1,
        "evaluated_rounds": protocol_count,
        "scheduled_calls": len(records),
        "formal_screened_candidates": protocol_count,
        "protocol_stage_counts": {
            "screening": protocol_count,
            "validation": 0,
            "frozen": 0,
        },
        "failure_categories": failure_categories,
        "execution_outcome_counts": outcomes,
        "unknown_outcome_count": 0,
        "last_execution_outcome": {
            "outcome": records[-1]["outcome"]["outcome"],
            "reason_code": records[-1]["outcome"]["reason_code"],
            "stage": records[-1]["outcome"]["stage"],
        },
        "run_validity": (
            {"valid": True, "status": "valid", "reason": "valid"}
            if not incomplete
            else {"valid": True, "status": "valid", "reason": "valid_incomplete"}
            if protocol_count
            else {
                "valid": False,
                "status": "invalid",
                "reason": "invalid_no_evaluated_outcome",
            }
        ),
        "qualification": qualification,
        "stop_reason": stop_reason,
    }
    shared = {
        "campaign_mode": "qualification_only",
        "proposal_runtime_mode": expectation.proposal_runtime_mode,
        "proposal_runtime": runtime,
        "run_result": run,
        "n_steps": len(steps),
        "total_rounds": max(
            [step["round"] for step in steps]
            + [attempt["round_num"] for attempt in attempts],
            default=0,
        ),
        "n_experiments": protocol_count,
        "screened_experiments": protocol_count,
    }
    status = deepcopy(shared)
    summary = {**deepcopy(shared), "steps": steps}
    return status, summary


def _set_canary_category(
    status: dict[str, Any],
    summary: dict[str, Any],
    *,
    step_index: int,
    category: str,
) -> None:
    previous = summary["steps"][step_index]["canary_result"]["failure_category"]
    summary["steps"][step_index]["canary_result"]["failure_category"] = category
    for artifact in (status, summary):
        counts = artifact["run_result"]["failure_categories"]
        counts[previous] -= 1
        if counts[previous] == 0:
            del counts[previous]
        counts[category] = counts.get(category, 0) + 1


def test_complete_arm_computes_frozen_positive_endpoints() -> None:
    expectation = _expectation()
    initial = _screening_record()
    expanded = _screening_record(gate="fail", decision="continue_explore")
    attempts = [
        _attempt(
            1,
            {"hypothesis_research_turn": 1, "code_research_finalize": 1},
            completed=1,
            selected=1,
            exported=1,
            patches=1,
            ready=1,
        )
    ]
    status, summary = _artifacts(
        expectation=expectation,
        records=[initial, expanded],
        attempts=attempts,
    )

    result = calculate_research_effectiveness(
        status=status,
        summary=summary,
        current_history=[initial, expanded],
        loaded_history=LoadedHistoryAvailable(records=()),
        expectation=expectation,
        initial_cells=((InitialCell(90.0, 100.0), InitialCell(80.0, 100.0)),),
    )

    assert result["scientific_status"] == {"value": "complete", "reasons": []}
    assert result["endpoint_status"] == {"value": "complete", "limitations": []}
    assert result["physical"]["initial_protocol_dispatches"] == 1
    assert result["physical"]["initial_expand_progressions"] == 1
    assert result["adjusted"]["d_h"] == 1
    assert result["adjusted"]["f"] == 1
    assert result["adjusted"]["g"] == 1
    assert result["adjusted"]["t"] == {
        "numerator": 1,
        "denominator": 2,
        "value": 0.5,
        "status": "FINITE",
    }
    assert result["adjusted"]["q"]["value"] == 1.0
    assert result["adjusted"]["e"] == pytest.approx(
        {"status": "FINITE", "value": -0.15}
    )


@pytest.mark.parametrize(
    ("shape", "counts", "expected_candidates"),
    (
        ("expanded", (1, 1), 1),
        ("expanded", (0, 1), 1),
        ("two_origins", (1, 1), 2),
    ),
)
def test_protocol_infeasibility_authority_is_sticky_per_origin_and_independent(
    shape: str,
    counts: tuple[int, int],
    expected_candidates: int,
) -> None:
    expectation = _expectation()
    if shape == "expanded":
        initial = _screening_record()
        records = [
            initial,
            _screening_record(
                hypothesis=initial["hypothesis"],
                patch=initial["patch"],
                gate="fail",
                decision="continue_explore",
            ),
        ]
        attempts = [
            _attempt(
                1,
                {"code_research_finalize": 1},
                completed=1,
                selected=1,
                exported=1,
                patches=1,
                ready=1,
            )
        ]
        cells = ((InitialCell(90.0, 100.0), InitialCell(90.0, 100.0)),)
    else:
        records = [
            _screening_record(gate="fail", decision="continue_explore"),
            _screening_record(
                hypothesis=_hypothesis("second exact hypothesis"),
                patch=_patch("def improve():\n    return 2\n"),
                gate="fail",
                decision="continue_explore",
            ),
        ]
        attempts = [
            _attempt(
                round_num,
                {"code_research_finalize": 1},
                completed=1,
                selected=1,
                exported=1,
                patches=1,
                ready=1,
            )
            for round_num in (1, 2)
        ]
        cells = (
            (InitialCell(90.0, 100.0), InitialCell(90.0, 100.0)),
            (InitialCell(95.0, 100.0), InitialCell(95.0, 100.0)),
        )
    status, summary = _artifacts(
        expectation=expectation,
        records=records,
        attempts=attempts,
    )
    baseline = calculate_research_effectiveness(
        status=status,
        summary=summary,
        current_history=records,
        loaded_history=LoadedHistoryAvailable(records=()),
        expectation=expectation,
        initial_cells=cells,
    )
    for step, count in zip(summary["steps"], counts):
        step["protocol_result"]["candidate_attributable_infeasible_pairs"] = count

    result = calculate_research_effectiveness(
        status=status,
        summary=summary,
        current_history=records,
        loaded_history=LoadedHistoryAvailable(records=()),
        expectation=expectation,
        initial_cells=cells,
    )

    assert (
        result["physical"]["candidate_attributable_infeasibility_candidates"]
        == expected_candidates
    )
    assert result["physical"]["candidate_attributable_infeasibility_rate"] == {
        "numerator": expected_candidates,
        "denominator": 2,
        "value": expected_candidates / 2,
        "status": "FINITE",
    }
    assert result["adjusted"] == baseline["adjusted"]


def test_candidate_canary_infeasibility_is_one_origin_and_candidate_only() -> None:
    expectation = _expectation()
    record = _canary_record()
    attempts = [
        _attempt(
            1,
            {"hypothesis_research_turn": 1},
            completed=1,
            selected=1,
            exported=1,
            patches=1,
            ready=1,
        )
    ]
    status, summary = _artifacts(
        expectation=expectation,
        records=[record],
        attempts=attempts,
    )
    summary["steps"][0]["canary_result"]["candidate_attributable_infeasible_pairs"] = 1

    result = calculate_research_effectiveness(
        status=status,
        summary=summary,
        current_history=[record],
        loaded_history=LoadedHistoryAvailable(records=()),
        expectation=expectation,
    )

    assert result["endpoint_status"] == {"value": "complete", "limitations": []}
    assert result["physical"]["candidate_only_failure_candidates"] == 1
    assert result["physical"]["candidate_attributable_infeasibility_candidates"] == 1


def test_m30_calibration_preserves_physical_counts_and_both_limitations() -> None:
    expectation = _expectation(a_cap=6, p_cap=60)
    formal = _screening_record(gate="fail", decision="continue_explore")
    rejected = _hypothesis_free_record(
        outcome="research_rejected", reason_code="HYPOTHESIS_RESEARCH_ABSTAINED"
    )
    exhausted = _hypothesis_free_record(
        outcome="resource_exhausted",
        reason_code="HYPOTHESIS_RESEARCH_TURN_CAP_EXHAUSTED",
    )
    attempts = [
        _attempt(
            1,
            {
                "hypothesis_research_turn": 7,
                "code_research_turn": 5,
                "code_research_finalize": 1,
            },
            completed=1,
            selected=1,
            exported=1,
            patches=1,
            ready=1,
        ),
        _attempt(2, {"hypothesis_research_turn": 6}),
        _attempt(3, {"hypothesis_research_turn": 6}),
    ]
    status, summary = _artifacts(
        expectation=expectation,
        records=[formal, rejected, exhausted],
        attempts=attempts,
        stop_reason="execution_resource_exhausted",
        disposition="incomplete",
    )
    del summary["steps"][0]["canary_result"]["candidate_attributable_infeasible_pairs"]
    del summary["steps"][0]["protocol_result"][
        "candidate_attributable_infeasible_pairs"
    ]

    result = calculate_research_effectiveness(
        status=status,
        summary=summary,
        current_history=[formal, rejected, exhausted],
        loaded_history=LoadedHistoryUnavailable(),
        expectation=expectation,
    )

    assert result["scientific_status"]["value"] == "incomplete"
    assert result["endpoint_status"] == {
        "value": "unavailable",
        "limitations": [
            "RUN_INCOMPLETE",
            HISTORY_REPLAY_BASIS_UNAVAILABLE,
            CANDIDATE_FEASIBILITY_EVIDENCE_UNAVAILABLE,
        ],
    }
    assert result["physical"] | {} == result["physical"]
    assert {
        key: result["physical"][key]
        for key in ("a_cap", "a_used", "p_cap", "p_charged", "h", "c_ready")
    } == {
        "a_cap": 6,
        "a_used": 3,
        "p_cap": 60,
        "p_charged": 25,
        "h": 1,
        "c_ready": 1,
    }
    assert result["physical"]["provider_calls_by_request_kind"] == {
        "hypothesis": 0,
        "hypothesis_research_turn": 19,
        "code": 0,
        "code_research_turn": 5,
        "code_research_finalize": 1,
        "other": 0,
    }
    assert result["physical"]["initial_protocol_dispatches"] == 1
    assert result["physical"]["initial_expand_progressions"] == 0
    assert result["physical"]["h_productivity"] == {
        "numerator": 1,
        "denominator": 25,
        "value": 0.04,
        "status": "FINITE",
    }
    assert result["physical"]["c_readiness"]["value"] == 1.0
    assert result["physical"]["within_block_h_replays"] == 0
    assert result["physical"]["within_block_pair_replays"] == 0
    assert result["physical"]["candidate_only_failure_candidates"] == 0
    assert result["physical"]["candidate_attributable_infeasibility_candidates"] is None
    assert result["physical"]["candidate_attributable_infeasibility_rate"] == {
        "numerator": None,
        "denominator": 6,
        "value": None,
        "status": "UNAVAILABLE",
    }
    assert all(value is None for value in result["adjusted"].values())


@pytest.mark.parametrize(
    "mutation",
    (
        "missing_canary",
        "canary_bool",
        "canary_pass_failure_fields",
        "missing_protocol",
        "protocol_negative",
        "protocol_large",
    ),
)
def test_missing_or_invalid_feasibility_authority_is_partial_not_zero(
    mutation: str,
) -> None:
    expectation = _expectation()
    record = _screening_record()
    attempts = [
        _attempt(
            1,
            {"code_research_finalize": 1},
            completed=1,
            selected=1,
            exported=1,
            patches=1,
            ready=1,
        )
    ]
    status, summary = _artifacts(
        expectation=expectation,
        records=[record],
        attempts=attempts,
    )
    baseline = calculate_research_effectiveness(
        status=status,
        summary=summary,
        current_history=[record],
        loaded_history=LoadedHistoryAvailable(records=()),
        expectation=expectation,
        initial_cells=((InitialCell(90.0, 100.0), InitialCell(90.0, 100.0)),),
    )
    canary = summary["steps"][0]["canary_result"]
    protocol = summary["steps"][0]["protocol_result"]
    if mutation == "missing_canary":
        del canary["candidate_attributable_infeasible_pairs"]
    elif mutation == "canary_bool":
        canary["candidate_attributable_infeasible_pairs"] = False
    elif mutation == "canary_pass_failure_fields":
        canary["failure_category"] = "candidate_failure"
        canary["reason_codes"] = ["CANARY_FAILED"]
    elif mutation == "missing_protocol":
        del protocol["candidate_attributable_infeasible_pairs"]
    elif mutation == "protocol_negative":
        protocol["candidate_attributable_infeasible_pairs"] = -1
    else:
        protocol["candidate_attributable_infeasible_pairs"] = 3

    result = calculate_research_effectiveness(
        status=status,
        summary=summary,
        current_history=[record],
        loaded_history=LoadedHistoryAvailable(records=()),
        expectation=expectation,
        initial_cells=((InitialCell(90.0, 100.0), InitialCell(90.0, 100.0)),),
    )

    assert result["endpoint_status"] == {
        "value": "partial",
        "limitations": [CANDIDATE_FEASIBILITY_EVIDENCE_UNAVAILABLE],
    }
    assert result["physical"]["candidate_attributable_infeasibility_candidates"] is None
    assert result["physical"]["candidate_attributable_infeasibility_rate"] == {
        "numerator": None,
        "denominator": 2,
        "value": None,
        "status": "UNAVAILABLE",
    }
    assert result["adjusted"] == baseline["adjusted"]


def test_k2_uses_one_attempt_and_shared_provider_budget() -> None:
    expectation = _expectation(k=2)
    record = _screening_record(gate="fail", decision="continue_explore")
    attempts = [
        _attempt(
            1,
            {"hypothesis_research_turn": 3, "code_research_finalize": 1},
            completed=2,
            selected=1,
            exported=1,
            patches=1,
            ready=1,
        )
    ]
    status, summary = _artifacts(
        expectation=expectation, records=[record], attempts=attempts
    )

    result = calculate_research_effectiveness(
        status=status,
        summary=summary,
        current_history=[record],
        loaded_history=LoadedHistoryAvailable(records=()),
        expectation=expectation,
        initial_cells=((InitialCell(90.0, 100.0), InitialCell(95.0, 100.0)),),
    )

    assert result["physical"]["a_used"] == 1
    assert result["physical"]["hypothesis_candidates_completed"] == 2
    assert result["physical"]["p_charged"] == 4
    assert result["adjusted"]["f"] == 1


def test_loaded_and_within_arm_replays_are_independent_fixed_denominator_guards() -> (
    None
):
    expectation = _expectation(a_cap=3, p_cap=12)
    first = _screening_record(gate="fail", decision="continue_explore")
    second = deepcopy(first)
    attempts = [
        _attempt(
            round_num,
            {"hypothesis_research_turn": 1, "code_research_finalize": 1},
            completed=1,
            selected=1,
            exported=1,
            patches=1,
            ready=1,
        )
        for round_num in (1, 2)
    ]
    status, summary = _artifacts(
        expectation=expectation, records=[first, second], attempts=attempts
    )

    result = calculate_research_effectiveness(
        status=status,
        summary=summary,
        current_history=[first, second],
        loaded_history=LoadedHistoryAvailable(records=(deepcopy(first),)),
        expectation=expectation,
        initial_cells=(
            (InitialCell(90.0, 100.0), InitialCell(90.0, 100.0)),
            (InitialCell(90.0, 100.0), InitialCell(90.0, 100.0)),
        ),
    )

    assert result["adjusted"]["d_h"] == 0
    assert result["adjusted"]["f"] == 0
    assert result["adjusted"]["loaded_history_h_replay_rate"]["numerator"] == 2
    assert result["adjusted"]["within_block_h_replay_rate"]["numerator"] == 1
    assert result["adjusted"]["loaded_history_pair_replay_rate"]["numerator"] == 2
    assert result["adjusted"]["within_block_pair_replay_rate"]["numerator"] == 1
    assert result["physical"]["within_block_h_replays"] == 1
    assert result["physical"]["within_block_pair_replays"] == 1
    assert result["adjusted"]["e"] == {"status": "POSITIVE_INFINITY", "value": None}


@pytest.mark.parametrize(
    ("candidate", "champion", "shared", "bilateral", "candidate_only"),
    (
        (1, 0, 0, 0, 1),
        (1, 1, 0, 1, 0),
        (0, 1, 1, 0, 0),
    ),
)
def test_protocol_failure_classes_make_e_infinite_without_flattening_candidate_only(
    candidate: int,
    champion: int,
    shared: int,
    bilateral: int,
    candidate_only: int,
) -> None:
    expectation = _expectation()
    record = _protocol_failure(
        _screening_record(),
        candidate=candidate,
        champion=champion,
        shared=shared,
        bilateral=bilateral,
    )
    attempts = [
        _attempt(
            1,
            {"hypothesis_research_turn": 1},
            completed=1,
            selected=1,
            exported=1,
            patches=1,
            ready=1,
        )
    ]
    status, summary = _artifacts(
        expectation=expectation, records=[record], attempts=attempts
    )

    result = calculate_research_effectiveness(
        status=status,
        summary=summary,
        current_history=[record],
        loaded_history=LoadedHistoryAvailable(records=()),
        expectation=expectation,
    )

    assert result["adjusted"]["f"] == 1
    assert result["adjusted"]["g"] == 0
    assert result["adjusted"]["e"] == {"status": "POSITIVE_INFINITY", "value": None}
    assert result["physical"]["candidate_only_failure_candidates"] == candidate_only


def test_protected_regression_is_history_authority_and_makes_candidate_infinite() -> (
    None
):
    expectation = _expectation()
    record = _protocol_failure(
        _screening_record(gate="fail", decision="continue_explore"),
        candidate=0,
        champion=0,
        protected=True,
    )
    attempts = [
        _attempt(
            1,
            {"code_research_finalize": 1},
            completed=1,
            selected=1,
            exported=1,
            patches=1,
            ready=1,
        )
    ]
    status, summary = _artifacts(
        expectation=expectation, records=[record], attempts=attempts
    )

    result = calculate_research_effectiveness(
        status=status,
        summary=summary,
        current_history=[record],
        loaded_history=LoadedHistoryAvailable(records=()),
        expectation=expectation,
    )

    assert result["physical"]["protected_regression_candidates"] == 1
    assert result["adjusted"]["g"] == 0
    assert result["adjusted"]["e"]["status"] == "POSITIVE_INFINITY"


@pytest.mark.parametrize(
    ("cells", "limitation", "feasibility_missing"),
    (
        (None, "INITIAL_CELL_DATA_UNAVAILABLE", False),
        (None, "INITIAL_CELL_DATA_UNAVAILABLE", True),
        (
            ((InitialCell(float("inf"), 100.0), InitialCell(90.0, 100.0)),),
            "BLOCK_UNSCORABLE",
            False,
        ),
        (
            ((InitialCell(90.0, 0.0), InitialCell(90.0, 100.0)),),
            "BLOCK_UNSCORABLE",
            False,
        ),
    ),
)
def test_e_unavailability_preserves_other_adjusted_endpoints(
    cells: Any,
    limitation: str,
    feasibility_missing: bool,
) -> None:
    expectation = _expectation()
    record = _screening_record()
    attempts = [
        _attempt(
            1,
            {"hypothesis_research_turn": 1},
            completed=1,
            selected=1,
            exported=1,
            patches=1,
            ready=1,
        )
    ]
    status, summary = _artifacts(
        expectation=expectation, records=[record], attempts=attempts
    )
    if feasibility_missing:
        del summary["steps"][0]["protocol_result"][
            "candidate_attributable_infeasible_pairs"
        ]

    result = calculate_research_effectiveness(
        status=status,
        summary=summary,
        current_history=[record],
        loaded_history=LoadedHistoryAvailable(records=()),
        expectation=expectation,
        initial_cells=cells,
    )

    assert result["endpoint_status"] == {
        "value": "partial",
        "limitations": (
            [CANDIDATE_FEASIBILITY_EVIDENCE_UNAVAILABLE, limitation]
            if feasibility_missing
            else [limitation]
        ),
    }
    assert result["adjusted"]["d_h"] == 1
    assert result["adjusted"]["f"] == 1
    assert result["adjusted"]["g"] == 1
    assert result["adjusted"]["e"] == {"status": "UNAVAILABLE", "value": None}


def test_f_zero_is_positive_infinity_without_initial_cell_payload() -> None:
    expectation = _expectation()
    record = _screening_record(gate="fail", decision="continue_explore")
    attempts = [
        _attempt(
            1,
            {"hypothesis_research_turn": 1},
            completed=1,
            selected=1,
            exported=1,
            patches=1,
            ready=1,
        )
    ]
    status, summary = _artifacts(
        expectation=expectation, records=[record], attempts=attempts
    )

    result = calculate_research_effectiveness(
        status=status,
        summary=summary,
        current_history=[record],
        loaded_history=LoadedHistoryAvailable(records=(deepcopy(record),)),
        expectation=expectation,
    )

    assert result["adjusted"]["f"] == 0
    assert result["endpoint_status"] == {"value": "complete", "limitations": []}
    assert result["adjusted"]["e"] == {"status": "POSITIVE_INFINITY", "value": None}


def test_initial_cell_bare_tuple_is_rejected() -> None:
    expectation = _expectation()
    record = _screening_record()
    attempts = [
        _attempt(
            1,
            {"hypothesis_research_turn": 1},
            completed=1,
            selected=1,
            exported=1,
            patches=1,
            ready=1,
        )
    ]
    status, summary = _artifacts(
        expectation=expectation, records=[record], attempts=attempts
    )
    malformed_cells: Any = (((90.0, 100.0), (90.0, 100.0)),)

    with pytest.raises(ValueError, match="INITIAL_CELL_MUST_BE_NAMED"):
        calculate_research_effectiveness(
            status=status,
            summary=summary,
            current_history=[record],
            loaded_history=LoadedHistoryAvailable(records=()),
            expectation=expectation,
            initial_cells=malformed_cells,
        )


@pytest.mark.parametrize(
    "reason_code",
    (
        "HYPOTHESIS_RESEARCH_TRANSCRIPT_EXHAUSTED",
        "HYPOTHESIS_RESEARCH_TURN_CAP_EXHAUSTED",
        "HYPOTHESIS_RESEARCH_RESULT_CAP_EXHAUSTED",
        "CODE_RESEARCH_TRANSCRIPT_EXHAUSTED",
        "CODE_RESEARCH_TURN_CAP_EXHAUSTED",
        "CODE_RESEARCH_RESULT_CAP_EXHAUSTED",
    ),
)
def test_typed_h_and_c_exhaustion_is_scientifically_incomplete_even_if_rejected(
    reason_code: str,
) -> None:
    expectation = _expectation()
    record = _hypothesis_free_record(
        outcome="research_rejected", reason_code=reason_code
    )
    attempts = [_attempt(1, {"hypothesis_research_turn": 1})]
    status, summary = _artifacts(
        expectation=expectation, records=[record], attempts=attempts
    )

    result = calculate_research_effectiveness(
        status=status,
        summary=summary,
        current_history=[record],
        loaded_history=LoadedHistoryAvailable(records=()),
        expectation=expectation,
    )

    assert result["scientific_status"]["value"] == "incomplete"
    assert result["endpoint_status"]["limitations"] == ["RUN_INCOMPLETE"]
    assert all(value is None for value in result["adjusted"].values())


@pytest.mark.parametrize("state", ("active", "interrupted", "unresolved"))
def test_nonclosed_attempt_is_typed_incomplete(state: str) -> None:
    expectation = _expectation()
    record = _hypothesis_free_record(
        outcome="research_rejected", reason_code="HYPOTHESIS_RESEARCH_ABSTAINED"
    )
    attempts = [_attempt(1, {"hypothesis_research_turn": 1})]
    attempts[0]["accounting_state"] = state
    status, summary = _artifacts(
        expectation=expectation, records=[record], attempts=attempts
    )

    result = calculate_research_effectiveness(
        status=status,
        summary=summary,
        current_history=[record],
        loaded_history=LoadedHistoryAvailable(records=()),
        expectation=expectation,
    )

    assert result["scientific_status"]["value"] == "incomplete"
    assert result["endpoint_status"]["limitations"] == ["RUN_INCOMPLETE"]


def test_missing_durable_attempt_row_is_typed_incomplete_not_schema_error() -> None:
    expectation = _expectation()
    record = _hypothesis_free_record(
        outcome="research_rejected", reason_code="HYPOTHESIS_RESEARCH_ABSTAINED"
    )
    attempts = [
        _attempt(1, {"hypothesis_research_turn": 1}),
        _attempt(2, {"hypothesis_research_turn": 1}),
    ]
    status, summary = _artifacts(
        expectation=expectation, records=[record], attempts=attempts
    )

    result = calculate_research_effectiveness(
        status=status,
        summary=summary,
        current_history=[record],
        loaded_history=LoadedHistoryAvailable(records=()),
        expectation=expectation,
    )

    assert result["scientific_status"]["value"] == "incomplete"
    assert result["physical"]["a_used"] == 2


@pytest.mark.parametrize(
    ("category", "scientific_value", "candidate_only"),
    (
        ("candidate_failure", "complete", 1),
        ("incomplete_evidence", "incomplete", 0),
        ("configuration_error", "incomplete", 0),
    ),
)
def test_initial_canary_categories_preserve_candidate_vs_incomplete_semantics(
    category: str,
    scientific_value: str,
    candidate_only: int,
) -> None:
    expectation = _expectation()
    record = _canary_record()
    attempts = [
        _attempt(
            1,
            {"hypothesis_research_turn": 1},
            completed=1,
            selected=1,
            exported=1,
            patches=1,
            ready=1,
        )
    ]
    status, summary = _artifacts(
        expectation=expectation, records=[record], attempts=attempts
    )
    _set_canary_category(status, summary, step_index=0, category=category)

    result = calculate_research_effectiveness(
        status=status,
        summary=summary,
        current_history=[record],
        loaded_history=LoadedHistoryAvailable(records=()),
        expectation=expectation,
    )

    assert result["scientific_status"]["value"] == scientific_value
    assert result["physical"]["candidate_only_failure_candidates"] == candidate_only
    assert result["physical"]["initial_protocol_dispatches"] == 0


@pytest.mark.parametrize(
    ("category", "scientific_value", "candidate_only"),
    (
        ("candidate_failure", "complete", 1),
        ("incomplete_evidence", "incomplete", 0),
    ),
)
def test_expanded_canary_continuation_is_joined_without_double_counting(
    category: str,
    scientific_value: str,
    candidate_only: int,
) -> None:
    expectation = _expectation()
    initial = _screening_record()
    canary = _canary_record(hypothesis=initial["hypothesis"], patch=initial["patch"])
    attempts = [
        _attempt(
            1,
            {"hypothesis_research_turn": 1},
            completed=1,
            selected=1,
            exported=1,
            patches=1,
            ready=1,
        )
    ]
    status, summary = _artifacts(
        expectation=expectation, records=[initial, canary], attempts=attempts
    )
    summary["steps"][1]["execution_outcome"]["provenance"]["stage"] = "screening"
    for artifact in (status, summary):
        artifact["run_result"]["last_execution_outcome"]["stage"] = "screening"
    _set_canary_category(status, summary, step_index=1, category=category)

    result = calculate_research_effectiveness(
        status=status,
        summary=summary,
        current_history=[initial, canary],
        loaded_history=LoadedHistoryAvailable(records=()),
        expectation=expectation,
        initial_cells=((InitialCell(90.0, 100.0), InitialCell(90.0, 100.0)),),
    )

    assert result["scientific_status"]["value"] == scientific_value
    assert result["physical"]["a_used"] == 1
    assert result["physical"]["initial_protocol_dispatches"] == 1
    assert result["physical"]["candidate_only_failure_candidates"] == candidate_only
    if scientific_value == "complete":
        assert result["adjusted"]["f"] == 1
        assert result["adjusted"]["g"] == 0
        assert result["physical"]["candidate_failure_candidates"] == 1
        assert result["adjusted"]["e"] == {
            "status": "POSITIVE_INFINITY",
            "value": None,
        }


@pytest.mark.parametrize(
    ("canary_code", "fields"),
    (
        ("CANARY_CHAMPION_FAILURE", ("champion_failure_candidates",)),
        (
            "CANARY_SHARED_FAILURE",
            ("champion_failure_candidates", "shared_failure_candidates"),
        ),
        (
            "CANARY_BILATERAL_FAILURE",
            (
                "candidate_failure_candidates",
                "champion_failure_candidates",
                "bilateral_failure_candidates",
            ),
        ),
    ),
)
@pytest.mark.parametrize("infeasible_pairs", (0, 1))
def test_complete_pair_canary_codes_map_quality_without_prose_or_identity(
    canary_code: str,
    fields: tuple[str, ...],
    infeasible_pairs: int,
) -> None:
    expectation = _expectation()
    initial = _screening_record()
    canary = _canary_record(
        hypothesis=initial["hypothesis"],
        patch=initial["patch"],
        canary_code=canary_code,
    )
    attempts = [
        _attempt(
            1,
            {"code_research_finalize": 1},
            completed=1,
            selected=1,
            exported=1,
            patches=1,
            ready=1,
        )
    ]
    status, summary = _artifacts(
        expectation=expectation,
        records=[initial, canary],
        attempts=attempts,
    )
    summary["steps"][1]["execution_outcome"]["provenance"]["stage"] = "screening"
    summary["steps"][1]["canary_result"]["details"] = {
        "failure_kind": "candidate_infeasible",
        "reason": "CANARY_SHARED_FAILURE",
    }
    summary["steps"][1]["canary_result"]["candidate_attributable_infeasible_pairs"] = (
        infeasible_pairs
    )
    for artifact in (status, summary):
        artifact["run_result"]["last_execution_outcome"]["stage"] = "screening"
    _set_canary_category(
        status,
        summary,
        step_index=1,
        category="incomplete_evidence",
    )

    result = calculate_research_effectiveness(
        status=status,
        summary=summary,
        current_history=[initial, canary],
        loaded_history=LoadedHistoryAvailable(records=()),
        expectation=expectation,
    )

    assert result["scientific_status"]["value"] == "incomplete"
    expected_limitations = ["RUN_INCOMPLETE"]
    if infeasible_pairs == 1:
        expected_limitations.append(CANDIDATE_FEASIBILITY_EVIDENCE_UNAVAILABLE)
    assert result["endpoint_status"] == {
        "value": "unavailable",
        "limitations": expected_limitations,
    }
    for field in (
        "candidate_failure_candidates",
        "champion_failure_candidates",
        "shared_failure_candidates",
        "bilateral_failure_candidates",
    ):
        assert result["physical"][field] == int(field in fields)
    assert result["physical"]["candidate_only_failure_candidates"] == 0
    assert result["physical"]["candidate_attributable_infeasibility_candidates"] == (
        None if infeasible_pairs else 0
    )


@pytest.mark.parametrize(
    ("canary_code", "category", "drop_joined_code"),
    (
        ("CANARY_CONFIG_ERROR", "configuration_error", False),
        ("CANARY_CHAMPION_FAILURE", "candidate_failure", False),
        ("CANARY_FUTURE_UNKNOWN", "candidate_failure", False),
        ("CANARY_SHARED_FAILURE", "incomplete_evidence", True),
    ),
)
def test_unknown_or_mismatched_canary_zero_is_not_feasibility_authority(
    canary_code: str,
    category: str,
    drop_joined_code: bool,
) -> None:
    expectation = _expectation()
    record = _canary_record(canary_code=canary_code)
    if drop_joined_code:
        record["decision"]["reason_codes"] = ["CANARY_FAILED"]
        record = normalize_research_history_record(record, expected_problem_id="demo")
    attempts = [
        _attempt(
            1,
            {"hypothesis_research_turn": 1},
            completed=1,
            selected=1,
            exported=1,
            patches=1,
            ready=1,
        )
    ]
    status, summary = _artifacts(
        expectation=expectation,
        records=[record],
        attempts=attempts,
    )
    if drop_joined_code:
        summary["steps"][0]["canary_result"]["reason_codes"] = [canary_code]
    _set_canary_category(status, summary, step_index=0, category=category)

    result = calculate_research_effectiveness(
        status=status,
        summary=summary,
        current_history=[record],
        loaded_history=LoadedHistoryAvailable(records=()),
        expectation=expectation,
    )

    assert result["scientific_status"]["value"] == "incomplete"
    assert result["endpoint_status"]["limitations"] == [
        "RUN_INCOMPLETE",
        CANDIDATE_FEASIBILITY_EVIDENCE_UNAVAILABLE,
    ]
    assert result["physical"]["candidate_attributable_infeasibility_candidates"] is None
    assert all(
        result["physical"][field] == 0
        for field in (
            "candidate_failure_candidates",
            "champion_failure_candidates",
            "shared_failure_candidates",
            "bilateral_failure_candidates",
        )
    )


@pytest.mark.parametrize(
    ("candidate", "champion", "shared", "bilateral", "protected", "fields"),
    (
        (1, 0, 0, 0, False, ("candidate_failure_candidates",)),
        (
            1,
            1,
            0,
            1,
            False,
            (
                "candidate_failure_candidates",
                "champion_failure_candidates",
                "bilateral_failure_candidates",
            ),
        ),
        (
            0,
            1,
            1,
            0,
            False,
            ("champion_failure_candidates", "shared_failure_candidates"),
        ),
        (0, 0, 0, 0, True, ("protected_regression_candidates",)),
    ),
)
def test_expanded_formal_quality_failures_are_merged_into_the_origin_candidate(
    candidate: int,
    champion: int,
    shared: int,
    bilateral: int,
    protected: bool,
    fields: tuple[str, ...],
) -> None:
    expectation = _expectation()
    initial = _screening_record()
    expanded = _protocol_failure(
        _screening_record(),
        candidate=candidate,
        champion=champion,
        shared=shared,
        bilateral=bilateral,
        protected=protected,
    )
    attempts = [
        _attempt(
            1,
            {"code_research_finalize": 1},
            completed=1,
            selected=1,
            exported=1,
            patches=1,
            ready=1,
        )
    ]
    status, summary = _artifacts(
        expectation=expectation,
        records=[initial, expanded],
        attempts=attempts,
    )

    result = calculate_research_effectiveness(
        status=status,
        summary=summary,
        current_history=[initial, expanded],
        loaded_history=LoadedHistoryAvailable(records=()),
        expectation=expectation,
    )

    assert result["physical"]["initial_protocol_dispatches"] == 1
    assert result["adjusted"]["f"] == 1
    assert result["adjusted"]["g"] == 0
    assert result["adjusted"]["e"] == {
        "status": "POSITIVE_INFINITY",
        "value": None,
    }
    assert result["physical"]["candidate_only_failure_candidates"] == int(
        candidate - bilateral > 0
    )
    for field in fields:
        assert result["physical"][field] == 1


def test_screening_pass_queue_validate_is_observed_but_not_g() -> None:
    expectation = _expectation()
    record = _screening_record(gate="pass", decision="queue_validate")
    attempts = [
        _attempt(
            1,
            {"code_research_finalize": 1},
            completed=1,
            selected=1,
            exported=1,
            patches=1,
            ready=1,
        )
    ]
    status, summary = _artifacts(
        expectation=expectation,
        records=[record],
        attempts=attempts,
        stop_reason="qualification_boundary_reached",
        disposition="ready_for_postrun_qualification_audit",
    )

    result = calculate_research_effectiveness(
        status=status,
        summary=summary,
        current_history=[record],
        loaded_history=LoadedHistoryAvailable(records=()),
        expectation=expectation,
        initial_cells=((InitialCell(90.0, 100.0), InitialCell(90.0, 100.0)),),
    )

    assert result["adjusted"]["f"] == 1
    assert result["adjusted"]["g"] == 0
    assert result["adjusted"]["q"]["value"] == 0.0


@pytest.mark.parametrize(
    ("mutation", "error_code"),
    (
        ("terminal_twin", "TERMINAL_PROJECTION_MISMATCH"),
        ("provider_kind", "PROVIDER_REQUEST_KINDS_INVALID"),
        ("provider_remaining", "PROVIDER_REMAINING_MISMATCH"),
        ("lifecycle", "PROPOSAL_ATTEMPT_LIFECYCLE_INVALID"),
        ("summary_h", "SUMMARY_HISTORY_HYPOTHESIS_MISMATCH"),
        ("verified_chains", "QUALIFICATION_VERIFIED_CHAIN_COUNT_MISMATCH"),
        ("run_validity", "RUN_VALIDITY_INCONSISTENT"),
        ("decision_reasons", "SUMMARY_HISTORY_REASON_CODES_MISMATCH"),
        ("protocol_reasons", "SUMMARY_HISTORY_PROTOCOL_REASON_CODES_MISMATCH"),
        ("last_outcome", "RUN_LAST_EXECUTION_OUTCOME_MISMATCH"),
        ("failure_categories", "RUN_FAILURE_CATEGORY_COUNT_MISMATCH"),
        ("zero_call_progress", "ZERO_CALL_ATTEMPT_PROGRESS_INVALID"),
    ),
)
def test_artifact_mutations_fail_closed_with_body_free_codes(
    mutation: str,
    error_code: str,
) -> None:
    expectation = _expectation()
    record = _screening_record(gate="fail", decision="continue_explore")
    attempts = [
        _attempt(
            1,
            {"hypothesis_research_turn": 1},
            completed=1,
            selected=1,
            exported=1,
            patches=1,
            ready=1,
        )
    ]
    status, summary = _artifacts(
        expectation=expectation, records=[record], attempts=attempts
    )
    if mutation == "terminal_twin":
        summary["n_steps"] = 2
    elif mutation == "provider_kind":
        for artifact in (status, summary):
            del artifact["proposal_runtime"]["provider_calls"]["by_request_kind"][
                "other"
            ]
    elif mutation == "provider_remaining":
        for artifact in (status, summary):
            artifact["proposal_runtime"]["provider_calls"]["remaining"] -= 1
    elif mutation == "lifecycle":
        for artifact in (status, summary):
            artifact["proposal_runtime"]["attempts"][0]["patches_completed"] = 0
    elif mutation == "summary_h":
        summary["steps"][0]["hypothesis"]["text"] = "PRIVATE MUTATION"
    elif mutation == "verified_chains":
        for artifact in (status, summary):
            artifact["run_result"]["qualification"]["verified_candidate_chains"] = 0
    elif mutation == "run_validity":
        for artifact in (status, summary):
            artifact["run_result"]["run_validity"]["reason"] = "bogus"
    elif mutation == "decision_reasons":
        summary["steps"][0]["decision_reason_codes"].append("MUTATED_REASON")
    elif mutation == "protocol_reasons":
        summary["steps"][0]["protocol_result"]["reason_codes"].append("MUTATED_REASON")
    elif mutation == "last_outcome":
        for artifact in (status, summary):
            artifact["run_result"]["last_execution_outcome"]["reason_code"] = (
                "MUTATED_REASON"
            )
    elif mutation == "failure_categories":
        for artifact in (status, summary):
            artifact["run_result"]["failure_categories"] = {"ghost": 1}
    elif mutation == "zero_call_progress":
        for artifact in (status, summary):
            runtime = artifact["proposal_runtime"]
            runtime["provider_calls"]["budget_admitted"] = 0
            runtime["provider_calls"]["remaining"] = expectation.p_cap
            runtime["provider_calls"]["by_request_kind"] = {kind: 0 for kind in _KINDS}
            runtime["attempts"][0]["provider_calls"] = {
                "budget_admitted": 0,
                "by_request_kind": {kind: 0 for kind in _KINDS},
            }

    with pytest.raises(ValueError, match=error_code) as caught:
        calculate_research_effectiveness(
            status=status,
            summary=summary,
            current_history=[record],
            loaded_history=LoadedHistoryAvailable(records=()),
            expectation=expectation,
            initial_cells=((InitialCell(90.0, 100.0), InitialCell(90.0, 100.0)),),
        )
    assert "PRIVATE MUTATION" not in str(caught.value)


def test_failed_canary_cannot_be_injected_into_a_noncanary_row() -> None:
    expectation = _expectation()
    record = _hypothesis_free_record(
        outcome="research_rejected", reason_code="HYPOTHESIS_RESEARCH_ABSTAINED"
    )
    attempts = [_attempt(1, {"hypothesis_research_turn": 1})]
    status, summary = _artifacts(
        expectation=expectation, records=[record], attempts=attempts
    )
    summary["steps"][0]["canary_result"] = {
        "passed": False,
        "failure_category": "candidate_failure",
    }

    with pytest.raises(ValueError, match="CANARY_ABANDONMENT_SHAPE_INVALID"):
        calculate_research_effectiveness(
            status=status,
            summary=summary,
            current_history=[record],
            loaded_history=LoadedHistoryAvailable(records=()),
            expectation=expectation,
        )


def test_zero_provider_denominators_preserve_t_only_defined_zero() -> None:
    expectation = _expectation()
    record = _hypothesis_free_record(
        outcome="research_rejected", reason_code="HYPOTHESIS_RESEARCH_ABSTAINED"
    )
    attempts = [_attempt(1, {})]
    status, summary = _artifacts(
        expectation=expectation, records=[record], attempts=attempts
    )

    result = calculate_research_effectiveness(
        status=status,
        summary=summary,
        current_history=[record],
        loaded_history=LoadedHistoryAvailable(records=()),
        expectation=expectation,
    )

    assert result["adjusted"]["t"] == {
        "numerator": 0,
        "denominator": 0,
        "value": 0.0,
        "status": "DEFINED_ZERO_PROVIDER_DENOMINATOR",
    }
    assert result["adjusted"]["h_productivity"] == {
        "numerator": 0,
        "denominator": 0,
        "value": None,
        "status": "ZERO_PROVIDER_DENOMINATOR",
    }


def test_loaded_h_replay_disqualifies_f_even_when_patch_is_distinct() -> None:
    expectation = _expectation()
    current = _screening_record(gate="fail", decision="continue_explore")
    loaded = deepcopy(current)
    loaded["patch"]["changes"][0]["source"] = "def improve():\n    return 2\n"
    loaded = normalize_research_history_record(loaded, expected_problem_id="demo")
    attempts = [
        _attempt(
            1,
            {"code_research_finalize": 1},
            completed=1,
            selected=1,
            exported=1,
            patches=1,
            ready=1,
        )
    ]
    status, summary = _artifacts(
        expectation=expectation, records=[current], attempts=attempts
    )

    result = calculate_research_effectiveness(
        status=status,
        summary=summary,
        current_history=[current],
        loaded_history=LoadedHistoryAvailable(records=(loaded,)),
        expectation=expectation,
        initial_cells=((InitialCell(90.0, 100.0), InitialCell(90.0, 100.0)),),
    )

    assert result["adjusted"]["d_h"] == 0
    assert result["adjusted"]["f"] == 0
    assert result["adjusted"]["g"] == 0
    assert result["adjusted"]["loaded_history_h_replay_rate"]["numerator"] == 1
    assert result["adjusted"]["loaded_history_pair_replay_rate"]["numerator"] == 0


def test_exact_h_uses_fields_not_present_in_summary_projection() -> None:
    expectation = _expectation()
    current = _screening_record(gate="fail", decision="continue_explore")
    loaded = deepcopy(current)
    loaded["hypothesis"]["expected_effect"] = "different exact effect"
    loaded = normalize_research_history_record(loaded, expected_problem_id="demo")
    attempts = [
        _attempt(
            1,
            {"code_research_finalize": 1},
            completed=1,
            selected=1,
            exported=1,
            patches=1,
            ready=1,
        )
    ]
    status, summary = _artifacts(
        expectation=expectation, records=[current], attempts=attempts
    )

    result = calculate_research_effectiveness(
        status=status,
        summary=summary,
        current_history=[current],
        loaded_history=LoadedHistoryAvailable(records=(loaded,)),
        expectation=expectation,
        initial_cells=((InitialCell(90.0, 100.0), InitialCell(90.0, 100.0)),),
    )

    assert result["adjusted"]["d_h"] == 1
    assert result["adjusted"]["f"] == 1


def test_ordered_patch_comparison_does_not_sort_or_hash_changes() -> None:
    expectation = _expectation()
    h = _hypothesis()
    forward = {
        "changes": [
            {
                "file_path": "operators/a.py",
                "action": "modify",
                "source": "A\n",
            },
            {
                "file_path": "operators/b.py",
                "action": "modify",
                "source": "B\n",
            },
        ]
    }
    reverse = {"changes": list(reversed(deepcopy(forward["changes"])))}
    current = _screening_record(
        hypothesis=h, patch=forward, gate="fail", decision="continue_explore"
    )
    loaded = _screening_record(
        hypothesis=h, patch=reverse, gate="fail", decision="continue_explore"
    )
    attempts = [
        _attempt(
            1,
            {"code_research_finalize": 1},
            completed=1,
            selected=1,
            exported=1,
            patches=1,
            ready=1,
        )
    ]
    status, summary = _artifacts(
        expectation=expectation, records=[current], attempts=attempts
    )

    result = calculate_research_effectiveness(
        status=status,
        summary=summary,
        current_history=[current],
        loaded_history=LoadedHistoryAvailable(records=(loaded,)),
        expectation=expectation,
        initial_cells=((InitialCell(90.0, 100.0), InitialCell(90.0, 100.0)),),
    )

    assert result["adjusted"]["loaded_history_h_replay_rate"]["numerator"] == 1
    assert result["adjusted"]["loaded_history_pair_replay_rate"]["numerator"] == 0


def test_loaded_preformal_patch_rejection_participates_in_pair_replay() -> None:
    expectation = _expectation()
    current = _screening_record(gate="fail", decision="continue_explore")
    loaded = normalize_research_history_record(
        {
            **deepcopy(current),
            "outcome": {
                "outcome": "research_rejected",
                "stage": "patch_contract",
                "reason_code": "PATCH_CONTRACT_REJECTED",
            },
            "protocol": None,
            "decision": None,
        },
        expected_problem_id="demo",
    )
    attempts = [
        _attempt(
            1,
            {"code_research_finalize": 1},
            completed=1,
            selected=1,
            exported=1,
            patches=1,
            ready=1,
        )
    ]
    status, summary = _artifacts(
        expectation=expectation, records=[current], attempts=attempts
    )

    result = calculate_research_effectiveness(
        status=status,
        summary=summary,
        current_history=[current],
        loaded_history=LoadedHistoryAvailable(records=(loaded,)),
        expectation=expectation,
        initial_cells=((InitialCell(90.0, 100.0), InitialCell(90.0, 100.0)),),
    )

    assert result["adjusted"]["loaded_history_pair_replay_rate"]["numerator"] == 1
    assert result["adjusted"]["f"] == 0


def test_e_is_median_of_candidate_medians_not_flattened_cells() -> None:
    expectation = _expectation(a_cap=2, p_cap=10)
    first = _screening_record(
        hypothesis=_hypothesis("first exact hypothesis"),
        patch=_patch("FIRST\n"),
        gate="fail",
        decision="continue_explore",
    )
    second = _screening_record(
        hypothesis=_hypothesis("second exact hypothesis"),
        patch=_patch("SECOND\n"),
        gate="fail",
        decision="continue_explore",
    )
    attempts = [
        _attempt(
            round_num,
            {"code_research_finalize": 1},
            completed=1,
            selected=1,
            exported=1,
            patches=1,
            ready=1,
        )
        for round_num in (1, 2)
    ]
    status, summary = _artifacts(
        expectation=expectation, records=[first, second], attempts=attempts
    )

    result = calculate_research_effectiveness(
        status=status,
        summary=summary,
        current_history=[first, second],
        loaded_history=LoadedHistoryAvailable(records=()),
        expectation=expectation,
        initial_cells=(
            (InitialCell(0.0, 100.0), InitialCell(0.0, 100.0)),
            (InitialCell(100.0, 100.0), InitialCell(10100.0, 100.0)),
        ),
    )

    assert result["adjusted"]["e"] == {"status": "FINITE", "value": 24.5}


def test_two_expanded_screening_continuations_join_in_global_order() -> None:
    expectation = _expectation()
    initial = _screening_record()
    expanded = _screening_record()
    final = _screening_record(gate="fail", decision="continue_explore")
    attempts = [
        _attempt(
            1,
            {"code_research_finalize": 1},
            completed=1,
            selected=1,
            exported=1,
            patches=1,
            ready=1,
        )
    ]
    status, summary = _artifacts(
        expectation=expectation,
        records=[initial, expanded, final],
        attempts=attempts,
    )

    result = calculate_research_effectiveness(
        status=status,
        summary=summary,
        current_history=[initial, expanded, final],
        loaded_history=LoadedHistoryAvailable(records=()),
        expectation=expectation,
        initial_cells=((InitialCell(90.0, 100.0), InitialCell(90.0, 100.0)),),
    )

    assert result["physical"]["initial_protocol_dispatches"] == 1
    assert result["adjusted"]["f"] == 1


def test_interleaved_row_breaks_expanded_continuation_join() -> None:
    expectation = _expectation()
    initial = _screening_record()
    interleaved = _hypothesis_free_record(
        outcome="research_rejected", reason_code="HYPOTHESIS_RESEARCH_ABSTAINED"
    )
    expanded = _screening_record(gate="fail", decision="continue_explore")
    attempts = [
        _attempt(
            1,
            {"code_research_finalize": 1},
            completed=1,
            selected=1,
            exported=1,
            patches=1,
            ready=1,
        ),
        _attempt(2, {"hypothesis_research_turn": 1}),
    ]
    status, summary = _artifacts(
        expectation=expectation,
        records=[initial, interleaved, expanded],
        attempts=attempts,
    )

    with pytest.raises(ValueError, match="EXPANDED_SCREENING_JOIN_INVALID"):
        calculate_research_effectiveness(
            status=status,
            summary=summary,
            current_history=[initial, interleaved, expanded],
            loaded_history=LoadedHistoryAvailable(records=()),
            expectation=expectation,
        )


def test_provider_cap_reason_requires_full_aggregate_cap() -> None:
    expectation = _expectation()
    record = _hypothesis_free_record(
        outcome="resource_exhausted", reason_code="PROVIDER_CALL_CAP_EXHAUSTED"
    )
    attempts = [_attempt(1, {"hypothesis_research_turn": 1})]
    status, summary = _artifacts(
        expectation=expectation,
        records=[record],
        attempts=attempts,
        stop_reason="execution_resource_exhausted",
        disposition="incomplete",
    )

    with pytest.raises(ValueError, match="PROVIDER_CAP_EXHAUSTION_ACCOUNTING_MISMATCH"):
        calculate_research_effectiveness(
            status=status,
            summary=summary,
            current_history=[record],
            loaded_history=LoadedHistoryAvailable(records=()),
            expectation=expectation,
        )


@pytest.mark.parametrize(
    ("field", "value", "error_code"),
    (
        ("text", " ", "HYPOTHESIS_REQUIRED_TEXT_INVALID"),
        ("target_file", None, "HYPOTHESIS_TARGET_INVALID"),
        ("suggested_weight", 1, "HYPOTHESIS_WEIGHT_INVALID"),
    ),
)
def test_exact_h_rejects_values_not_producible_by_the_provider_schema(
    field: str,
    value: Any,
    error_code: str,
) -> None:
    expectation = _expectation()
    record = _screening_record(gate="fail", decision="continue_explore")
    record["hypothesis"][field] = value
    record = normalize_research_history_record(record, expected_problem_id="demo")
    attempts = [
        _attempt(
            1,
            {"code_research_finalize": 1},
            completed=1,
            selected=1,
            exported=1,
            patches=1,
            ready=1,
        )
    ]
    status, summary = _artifacts(
        expectation=expectation, records=[record], attempts=attempts
    )

    with pytest.raises(ValueError, match=error_code):
        calculate_research_effectiveness(
            status=status,
            summary=summary,
            current_history=[record],
            loaded_history=LoadedHistoryAvailable(records=()),
            expectation=expectation,
        )


def test_result_is_body_free_and_detached_from_inputs() -> None:
    expectation = _expectation()
    record = _screening_record(
        hypothesis=_hypothesis("PRIVATE_HYPOTHESIS_SENTINEL"),
        patch=_patch("PRIVATE_SOURCE_SENTINEL\n"),
        gate="fail",
        decision="continue_explore",
    )
    attempts = [
        _attempt(
            1,
            {"code_research_finalize": 1},
            completed=1,
            selected=1,
            exported=1,
            patches=1,
            ready=1,
        )
    ]
    status, summary = _artifacts(
        expectation=expectation, records=[record], attempts=attempts
    )
    frozen_inputs = deepcopy((status, summary, record))

    result = calculate_research_effectiveness(
        status=status,
        summary=summary,
        current_history=[record],
        loaded_history=LoadedHistoryAvailable(records=()),
        expectation=expectation,
        initial_cells=((InitialCell(90.0, 100.0), InitialCell(90.0, 100.0)),),
    )
    rendered = json.dumps(result, allow_nan=False)

    assert "PRIVATE_HYPOTHESIS_SENTINEL" not in rendered
    assert "PRIVATE_SOURCE_SENTINEL" not in rendered
    assert "operators/local_search.py" not in rendered
    assert "round_num" not in rendered
    result["physical"]["p_charged"] = 999
    assert (status, summary, record) == frozen_inputs
