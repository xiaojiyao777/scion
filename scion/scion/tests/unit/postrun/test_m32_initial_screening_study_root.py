from __future__ import annotations

import json
import signal
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

import scion.postrun.research_effectiveness as public_api
import scion.postrun.research_effectiveness.study_root as study_root_module
from scion.cli.commands.init_run import (
    _campaign_signal_handlers,
    _CampaignOuterHardwall,
    _CampaignSignalStop,
)
from scion.core.execution_outcome import ExecutionOutcome, ExecutionOutcomeRecord
from scion.core.proposal_pipeline import ProposalAttempt
from scion.core.research_history import normalize_research_history_record
from scion.core.scheduler import Scheduler
from scion.postrun.research_effectiveness import LoadedHistoryAvailable
from scion.postrun.research_effectiveness.models import ResearchEffectivenessInputError
from scion.postrun.research_effectiveness.study_root import (
    _calculate_initial_screening_study_root_effectiveness,
    _compare_five_block_initial_screening_study_roots,
    _InitialScreeningStudyExpectation,
    _InitialScreeningStudyRootArtifacts,
    _MatchedInitialScreeningStudyBlock,
)
from scion.tests.campaign_test_support import MockExperimentProtocol
from scion.tests.unit.core.test_m32_initial_screening_only_boundary import (
    _campaign,
    _envelope,
    _initial_only_config,
    _install_synthetic_bounded_proposals,
    _limits,
)
from scion.tests.unit.core.test_m32_paired_effect_cells_summary import (
    _complete_protocol,
)
from scion.tests.unit.postrun.test_m32_research_effectiveness import (
    _artifacts,
    _attempt,
    _canary_record,
    _expectation,
    _hypothesis,
    _hypothesis_free_record,
    _patch,
    _protocol_failure,
    _screening_record,
    _set_canary_category,
)

_CASE_REFS = ("cases/alpha.vrp", "cases/beta.vrp")
_SEEDS = (17,)
_EQUIVALENCE_BAND = 0.0
_PRODUCER_CASE_REFS = ("private/a/alpha.vrp", "private/b/beta.vrp")
_PRODUCER_SEEDS = (11, 29)


def _formal_record(
    *,
    hypothesis_text: str = "study hypothesis",
    source: str = "def improve():\n    return 1\n",
) -> dict[str, Any]:
    record = _screening_record(
        hypothesis=_hypothesis(hypothesis_text),
        patch=_patch(source),
    )
    target_files = sorted(
        {change["file_path"] for change in record["patch"]["changes"]}
    )
    record["protocol"]["candidate_composition"] = {
        "attribution_scope": "current_step_candidate",
        "protocol_comparison_scope": "candidate_vs_champion",
        "evaluation_candidate": "branch_state_after_current_step_patch",
        "current_step_change_scope": "incremental_patch",
        "incremental_effect_isolated": True,
        "current_step": {"target_files": target_files},
    }
    return normalize_research_history_record(record, expected_problem_id="demo")


def _cells_payload(
    *,
    candidate_values: tuple[int | float, int | float] = (90.0, 80.0),
    reference_values: tuple[int | float, int | float] = (100.0, 100.0),
) -> dict[str, Any]:
    return {
        "schema_version": "scion.paired_effect_cells.v1",
        "metric_name": "total_distance",
        "cells": [
            {"candidate_value": candidate, "reference_value": reference}
            for candidate, reference in zip(
                candidate_values, reference_values, strict=True
            )
        ],
    }


def _study_root(
    *,
    records: tuple[dict[str, Any], ...] | None = None,
    k: int = 1,
    a_cap: int = 1,
    campaign_id: str = "study-arm",
    paired_cells: dict[int, Any] | None = None,
    branch_ids: tuple[str, ...] | None = None,
    attempts_override: list[dict[str, Any]] | None = None,
) -> _InitialScreeningStudyRootArtifacts:
    records = records or (_formal_record(),)
    if branch_ids is None:
        branch_ids = tuple(f"branch-{index}" for index in range(1, len(records) + 1))
    if len(branch_ids) != len(records):
        raise ValueError("test branch ids must match records")
    expectation = _expectation(a_cap=a_cap, p_cap=40, k=k)
    study_expectation = _InitialScreeningStudyExpectation(
        effectiveness=expectation,
        case_refs=_CASE_REFS,
        seeds=_SEEDS,
        equivalence_band=_EQUIVALENCE_BAND,
    )
    calls = (
        {"hypothesis_research_turn": 1, "code_research_finalize": 1}
        if k == 1
        else {"hypothesis_research_turn": 3, "code_research_finalize": 1}
    )
    attempts = (
        attempts_override
        if attempts_override is not None
        else [
            (
                _attempt(index, {"hypothesis_research_turn": 1})
                if record["hypothesis"] is None
                else _attempt(
                    index,
                    calls,
                    completed=k,
                    selected=1,
                    exported=1,
                    patches=1,
                    ready=1,
                )
            )
            for index, record in enumerate(records, 1)
        ]
    )
    incomplete = any(
        record["outcome"]["outcome"] not in {"evaluated", "research_rejected"}
        for record in records
    )
    status, summary = _artifacts(
        expectation=expectation,
        records=list(records),
        attempts=attempts,
        stop_reason=("execution_resource_exhausted" if incomplete else _QUAL_STOP),
        disposition=("incomplete" if incomplete else _QUAL_STOP),
    )
    run = status["run_result"]
    run["requested_rounds"] = a_cap
    qualification = run["qualification"]
    qualification["development_boundary_mode"] = "initial_screening_only_v1"
    qualification["limits"] = {
        "max_proposal_attempts": a_cap,
        "max_verified_candidate_chains": a_cap,
        "max_formal_screening_stages": a_cap,
    }
    for index, (step, branch_id) in enumerate(
        zip(summary["steps"], branch_ids, strict=True), 1
    ):
        step["branch_id"] = branch_id
        step["contract_diagnostics"] = []
        if step.get("canary_result") is not None:
            step["canary_result"].setdefault("reason", None)
        if step.get("protocol_result") is None:
            step.pop("protocol_result", None)
        if step.get("protocol_result") is not None:
            protocol = step["protocol_result"]
            protocol.pop("n_cases", None)
            protocol["case_ids"] = list(_CASE_REFS)
            protocol["seed_set"] = list(_SEEDS)
            protocol["case_aggregation"] = {
                "method": "paired_effect_median",
                "effect_metric": "total_distance",
                "equivalence_band": _EQUIVALENCE_BAND,
            }
            protocol.update(
                {
                    "median_delta": 0.0,
                    "ci_low": 0.0,
                    "ci_high": 0.0,
                    "statistical_status": "ok",
                    "statistical_metric": "total_distance",
                    "metric_stats": [],
                    "runtime_ratio_median": None,
                    "runtime_delta_median_ms": None,
                    "runtime_regression_rate": None,
                    "runtime_pairs": 0,
                    "runtime_confidence": "unavailable",
                    "runtime_model": None,
                    "runtime_evidence_status": "unavailable",
                    "decision_reason_codes": list(step["decision_reason_codes"]),
                    "diagnostic_reason_codes": list(step["diagnostic_reason_codes"]),
                    "bypass_reason_codes": list(step["bypass_reason_codes"]),
                    "raw_metrics_ref": None,
                    "selected_surface": None,
                    "opportunity_status": None,
                    "opportunity_diagnostics": [],
                    "mechanism_evidence": {},
                    "candidate_surface_runtime_summary": {},
                    "candidate_phase_telemetry_summary": {},
                    "runtime_budget_diagnostic": None,
                    "candidate_runtime_failure_categories": {},
                    "candidate_first_runtime_failure": None,
                    "candidate_operator_attempts": 0,
                    "candidate_operator_accepted": 0,
                    "candidate_operator_errors": 0,
                    "candidate_operator_invalid_outputs": 0,
                    "candidate_policy_errors": 0,
                    "candidate_construction_errors": 0,
                    "candidate_portfolio_errors": 0,
                    "candidate_runtime_stop_reasons": {},
                    "screening_case_win_rate": 0.5,
                    "screening_pair_win_rate": 0.5,
                }
            )
            if paired_cells is None or index in paired_cells:
                protocol["paired_effect_cells"] = (
                    _cells_payload()
                    if paired_cells is None
                    else deepcopy(paired_cells[index])
                )
    qualification["verified_candidate_chains"] = len(
        {
            step["branch_id"]
            for step in summary["steps"]
            if step.get("verification_passed") is True
        }
    )

    ordered_unique_branches = list(dict.fromkeys(branch_ids))
    branches = []
    for branch_id in ordered_unique_branches:
        branch_steps = [
            step for step in summary["steps"] if step["branch_id"] == branch_id
        ]
        retired = any(
            step.get("protocol_result") is not None
            or (
                isinstance(step.get("canary_result"), dict)
                and step["canary_result"].get("failure_category") == "candidate_failure"
            )
            for step in branch_steps
        )
        last_outcome = branch_steps[-1]["execution_outcome"]
        held = last_outcome["outcome"] in {
            "not_evaluated",
            "blocked_infra",
            "resource_exhausted",
            "interrupted",
        }
        state = "parked_lineage" if retired else "blocked_infra" if held else "explore"
        branches.append(
            {
                "id": branch_id,
                "state": state,
                "base_champion_id": 0,
                "current_code_hash": None,
                "weight_revision": 0,
                "direction": None,
                "failure_codes": ([last_outcome["reason_code"]] if held else []),
                "created_at": "2026-08-25T00:00:00+00:00",
                "updated_at": "2026-08-25T00:00:01+00:00",
            }
        )
    active_ids = [branch["id"] for branch in branches if branch["state"] == "explore"]
    last_step = summary["steps"][-1]
    last_execution = last_step["execution_outcome"]
    last_branch_id = last_step["branch_id"]
    last_result = {
        "action": ("explore" if last_branch_id in branch_ids[:-1] else "create_branch"),
        "branch_id": last_branch_id,
        "decision": last_step["decision"],
        "stopped": False,
        "reason": "synthetic durable result",
        "execution_outcome": {
            "outcome": last_execution["outcome"],
            "reason_code": last_execution["reason_code"],
            "stage": last_execution["provenance"]["stage"],
        },
    }
    status.update(
        {
            "updated_at": "2026-08-25T00:00:02+00:00",
            "campaign_id": campaign_id,
            "champion_version": 0,
            "champion_weight_revision": 0,
            "balance_exhausted": False,
            "measurement_readiness": {
                "status": "not_ready",
                "reason_code": "missing_measurement",
                "calibration_age_days": None,
                "calibration_max_age_days": 0,
                "n_pairs": 0,
                "mde_at_power_80": None,
                "noise_band_p90_abs": None,
                "effect_to_mde_ratio": None,
                "signal_to_noise_tier": "unknown",
                "calibration_evidence_level": "none",
            },
            "branches": branches,
            "n_active_branches": len(active_ids),
            "active_slots": {
                "used": len(active_ids),
                "max": 8,
                "available": 8 - len(active_ids),
                "branch_ids": active_ids,
            },
            "last_result": last_result,
        }
    )
    summary.update(
        {
            "verification_failure_breakdown": {},
            "action_locus_coverage": {},
            "family_coverage": {},
            "diagnostics": [],
        }
    )
    for key, value in status.items():
        if key != "updated_at":
            summary[key] = deepcopy(value)
    return _InitialScreeningStudyRootArtifacts(
        status=status,
        summary=summary,
        current_history=records,
        expectation=study_expectation,
    )


_QUAL_STOP = "qualification_not_reached"


def _replace_root(
    root: _InitialScreeningStudyRootArtifacts,
    *,
    status: dict[str, Any] | None = None,
    summary: dict[str, Any] | None = None,
    current_history: tuple[dict[str, Any], ...] | None = None,
    expectation: _InitialScreeningStudyExpectation | None = None,
) -> _InitialScreeningStudyRootArtifacts:
    return _InitialScreeningStudyRootArtifacts(
        status=status if status is not None else root.status,
        summary=summary if summary is not None else root.summary,
        current_history=(
            current_history if current_history is not None else root.current_history
        ),
        expectation=expectation if expectation is not None else root.expectation,
    )


def _sync_terminal_twins(
    root: _InitialScreeningStudyRootArtifacts,
    mutate: Any,
) -> _InitialScreeningStudyRootArtifacts:
    status = deepcopy(root.status)
    summary = deepcopy(root.summary)
    mutate(status)
    mutate(summary)
    return _replace_root(root, status=status, summary=summary)


def _stopped_prefix(
    root: _InitialScreeningStudyRootArtifacts,
    *,
    reason: str = "OUTER_HARDWALL_EXCEEDED",
) -> _InitialScreeningStudyRootArtifacts:
    def mutate(value: dict[str, Any]) -> None:
        run = value["run_result"]
        run["status"] = "stopped"
        run["stop_reason"] = reason
        run["run_validity"] = {
            "valid": True,
            "status": "valid",
            "reason": "valid_incomplete",
        }
        run["qualification"]["disposition"] = "incomplete"

    return _sync_terminal_twins(root, mutate)


def _pre_reservation_interrupt_root() -> _InitialScreeningStudyRootArtifacts:
    root = _study_root(a_cap=2)
    status = deepcopy(root.status)
    summary = deepcopy(root.summary)
    for artifact in (status, summary):
        artifact["proposal_runtime"]["attempts"] = []
        provider = artifact["proposal_runtime"]["provider_calls"]
        provider["budget_admitted"] = 0
        provider["remaining"] = provider["cap"]
        provider["by_request_kind"] = {name: 0 for name in provider["by_request_kind"]}
        run = artifact["run_result"]
        run.update(
            {
                "status": "stopped",
                "evaluated_rounds": 0,
                "scheduled_calls": 1,
                "formal_screened_candidates": 0,
                "protocol_stage_counts": {
                    "screening": 0,
                    "validation": 0,
                    "frozen": 0,
                },
                "failure_categories": {},
                "execution_outcome_counts": {
                    "evaluated": 0,
                    "research_rejected": 0,
                    "not_evaluated": 0,
                    "blocked_infra": 0,
                    "resource_exhausted": 0,
                    "interrupted": 1,
                },
                "unknown_outcome_count": 0,
                "last_execution_outcome": {
                    "outcome": "interrupted",
                    "reason_code": "OUTER_HARDWALL_EXCEEDED",
                    "stage": "campaign",
                },
                "run_validity": {
                    "valid": False,
                    "status": "invalid",
                    "reason": "invalid_no_evaluated_outcome",
                },
                "stop_reason": "OUTER_HARDWALL_EXCEEDED",
            }
        )
        run["qualification"].update(
            {
                "proposal_attempts": 0,
                "verified_candidate_chains": 0,
                "formal_screening_stages": 0,
                "initial_screening_stages": 0,
                "expanded_screening_stages": 0,
                "disposition": "incomplete",
            }
        )
        artifact.pop("last_result", None)
        artifact.pop("current_progress", None)
        artifact.update(
            {
                "n_steps": 0,
                "total_rounds": 1,
                "n_experiments": 0,
                "screened_experiments": 0,
                "branches": [
                    {
                        "id": "pre-reservation-branch",
                        "state": "explore",
                        "base_champion_id": 0,
                        "current_code_hash": None,
                        "weight_revision": 0,
                        "direction": None,
                        "failure_codes": [],
                        "created_at": "2026-08-25T00:00:00+00:00",
                        "updated_at": "2026-08-25T00:00:01+00:00",
                    }
                ],
                "n_active_branches": 1,
                "active_slots": {
                    "used": 1,
                    "max": 8,
                    "available": 7,
                    "branch_ids": ["pre-reservation-branch"],
                },
            }
        )
        if "steps" in artifact:
            artifact["steps"] = []
    return _replace_root(
        root,
        status=status,
        summary=summary,
        current_history=(),
    )


def _pre_attempt_interrupt_root(
    kind: str,
    *,
    with_prefix: bool,
) -> _InitialScreeningStudyRootArtifacts:
    if kind not in {"zero", "admitted", "pre_reservation", "reserved"}:
        raise ValueError("unknown test interrupt kind")
    if kind == "zero" and with_prefix:
        raise ValueError("zero-evidence interrupt cannot have a durable prefix")
    root = _study_root(a_cap=2) if with_prefix else _pre_reservation_interrupt_root()
    prefix_count = int(with_prefix)
    round_delta = int(kind in {"pre_reservation", "reserved"})
    proposal_delta = int(kind == "reserved")

    def mutate(artifact: dict[str, Any]) -> None:
        run = artifact["run_result"]
        run.update(
            {
                "status": "stopped",
                "scheduled_calls": prefix_count + 1,
                "execution_outcome_counts": {
                    "evaluated": prefix_count,
                    "research_rejected": 0,
                    "not_evaluated": 0,
                    "blocked_infra": 0,
                    "resource_exhausted": 0,
                    "interrupted": 1,
                },
                "unknown_outcome_count": 0,
                "last_execution_outcome": {
                    "outcome": "interrupted",
                    "reason_code": "OUTER_HARDWALL_EXCEEDED",
                    "stage": "campaign",
                },
                "run_validity": (
                    {
                        "valid": True,
                        "status": "valid",
                        "reason": "valid_incomplete",
                    }
                    if with_prefix
                    else {
                        "valid": False,
                        "status": "invalid",
                        "reason": "invalid_no_evaluated_outcome",
                    }
                ),
                "stop_reason": "OUTER_HARDWALL_EXCEEDED",
            }
        )
        run.pop("terminal_exception", None)
        run["qualification"].update(
            {
                "proposal_attempts": prefix_count + proposal_delta,
                "disposition": "incomplete",
            }
        )
        artifact["total_rounds"] = prefix_count + round_delta
        artifact.pop("current_progress", None)
        if kind == "zero":
            artifact["branches"] = []
        elif with_prefix and kind in {"pre_reservation", "reserved"}:
            extra = deepcopy(artifact["branches"][0])
            extra.update(
                {
                    "id": "terminal-gap-branch",
                    "state": "explore",
                    "failure_codes": [],
                }
            )
            artifact["branches"].append(extra)
        active_ids = [
            branch["id"]
            for branch in artifact["branches"]
            if branch["state"] == "explore"
        ]
        artifact["n_active_branches"] = len(active_ids)
        artifact["active_slots"].update(
            {
                "used": len(active_ids),
                "available": artifact["active_slots"]["max"] - len(active_ids),
                "branch_ids": active_ids,
            }
        )

    return _sync_terminal_twins(root, mutate)


def _event_write_failure_root(
    *,
    failure_detail: str = "lineage unavailable",
) -> _InitialScreeningStudyRootArtifacts:
    record = deepcopy(_formal_record())
    record.update(
        {
            "protocol": None,
            "decision": None,
            "outcome": {
                "outcome": "blocked_infra",
                "stage": "decision_event",
                "reason_code": "EXPERIMENT_EVENT_WRITE_FAILED",
            },
        }
    )
    record = normalize_research_history_record(record, expected_problem_id="demo")
    root = _study_root(records=(record,), a_cap=2, paired_cells={})

    def mutate(artifact: dict[str, Any]) -> None:
        artifact["n_experiments"] = 1
        run = artifact["run_result"]
        run["stop_reason"] = "execution_blocked_infra"
        run["qualification"]["verified_candidate_chains"] = 1
        if "steps" in artifact:
            artifact["steps"][0]["verification_passed"] = True
            artifact["steps"][0]["failure_detail"] = failure_detail

    return _sync_terminal_twins(root, mutate)


def _preflight_exception_root() -> _InitialScreeningStudyRootArtifacts:
    root = _pre_reservation_interrupt_root()

    def mutate(artifact: dict[str, Any]) -> None:
        run = artifact["run_result"]
        run.update(
            {
                "scheduled_calls": 0,
                "execution_outcome_counts": {
                    "evaluated": 0,
                    "research_rejected": 0,
                    "not_evaluated": 0,
                    "blocked_infra": 0,
                    "resource_exhausted": 0,
                    "interrupted": 0,
                },
                "last_execution_outcome": None,
                "stop_reason": "preflight_exception",
                "terminal_exception": {
                    "reason": "preflight_exception",
                    "type": "RuntimeError",
                    "message": "synthetic preflight failure",
                },
            }
        )
        artifact.update(
            {
                "total_rounds": 0,
                "branches": [],
                "n_active_branches": 0,
                "active_slots": {
                    "used": 0,
                    "max": 8,
                    "available": 8,
                    "branch_ids": [],
                },
            }
        )

    return _sync_terminal_twins(root, mutate)


def _closed_cleanup_exception_root(
    *, retain_current_last_result: bool
) -> _InitialScreeningStudyRootArtifacts:
    root = _study_root(a_cap=2)

    def mutate(artifact: dict[str, Any]) -> None:
        run = artifact["run_result"]
        run.update(
            {
                "status": "stopped",
                "stop_reason": "unhandled_exception",
                "run_validity": {
                    "valid": True,
                    "status": "valid",
                    "reason": "valid_incomplete",
                },
                "terminal_exception": {
                    "reason": "unhandled_exception",
                    "type": "RuntimeError",
                    "message": "synthetic cleanup failure",
                },
            }
        )
        run["qualification"]["disposition"] = "incomplete"
        if not retain_current_last_result:
            artifact.pop("last_result", None)

    return _sync_terminal_twins(root, mutate)


def _durable_nonclosed_root(
    state: str,
) -> _InitialScreeningStudyRootArtifacts:
    rejected = _hypothesis_free_record(
        outcome="research_rejected",
        reason_code="HYPOTHESIS_RESEARCH_ABANDONED",
    )
    attempt = _attempt(1, {"hypothesis_research_turn": 1})
    attempt["accounting_state"] = state
    root = _study_root(
        records=(rejected,),
        a_cap=2,
        attempts_override=[attempt],
        paired_cells={},
    )

    def mutate(artifact: dict[str, Any]) -> None:
        run = artifact["run_result"]
        run.update(
            {
                "status": "stopped",
                "failure_categories": {},
                "execution_outcome_counts": {
                    "evaluated": 0,
                    "research_rejected": 0,
                    "not_evaluated": 0,
                    "blocked_infra": 0,
                    "resource_exhausted": 0,
                    "interrupted": int(state == "interrupted"),
                },
                "unknown_outcome_count": int(state == "unresolved"),
                "last_execution_outcome": (
                    {
                        "outcome": "interrupted",
                        "reason_code": "OUTER_HARDWALL_EXCEEDED",
                        "stage": "campaign",
                    }
                    if state == "interrupted"
                    else None
                ),
                "run_validity": {
                    "valid": False,
                    "status": "invalid",
                    "reason": "invalid_no_evaluated_outcome",
                },
                "stop_reason": (
                    "OUTER_HARDWALL_EXCEEDED"
                    if state == "interrupted"
                    else "unhandled_exception"
                ),
            }
        )
        if state == "unresolved":
            run["terminal_exception"] = {
                "reason": "unhandled_exception",
                "type": "RuntimeError",
                "message": "synthetic post-record failure",
            }
        else:
            run.pop("terminal_exception", None)
        run["qualification"].update(
            {
                "verified_candidate_chains": 0,
                "formal_screening_stages": 0,
                "initial_screening_stages": 0,
                "expanded_screening_stages": 0,
                "disposition": "incomplete",
            }
        )
        artifact.pop("last_result", None)
        artifact.pop("current_progress", None)

    return _sync_terminal_twins(root, mutate)


def _unmatched_nonclosed_root(
    state: str = "unresolved",
    *,
    ready: bool = False,
) -> _InitialScreeningStudyRootArtifacts:
    rejected = _hypothesis_free_record(
        outcome="research_rejected",
        reason_code="HYPOTHESIS_RESEARCH_ABANDONED",
    )
    first = _attempt(1, {"hypothesis_research_turn": 1})
    terminal = _attempt(
        2,
        (
            {"hypothesis_research_turn": 1, "code_research_finalize": 1}
            if ready
            else {"hypothesis_research_turn": 1}
        ),
        completed=int(ready),
        selected=int(ready),
        exported=int(ready),
        patches=int(ready),
        ready=int(ready),
    )
    terminal["accounting_state"] = state
    root = _study_root(
        records=(rejected,),
        a_cap=2,
        attempts_override=[first, terminal],
        paired_cells={},
    )

    def mutate(artifact: dict[str, Any]) -> None:
        run = artifact["run_result"]
        run.update(
            {
                "status": "stopped",
                "scheduled_calls": 2,
                "execution_outcome_counts": {
                    "evaluated": 0,
                    "research_rejected": 1,
                    "not_evaluated": 0,
                    "blocked_infra": 0,
                    "resource_exhausted": 0,
                    "interrupted": int(state == "interrupted"),
                },
                "unknown_outcome_count": int(state == "unresolved"),
                "last_execution_outcome": (
                    {
                        "outcome": "interrupted",
                        "reason_code": "OUTER_HARDWALL_EXCEEDED",
                        "stage": "campaign",
                    }
                    if state == "interrupted"
                    else {
                        "outcome": "research_rejected",
                        "reason_code": "HYPOTHESIS_RESEARCH_ABANDONED",
                        "stage": "proposal_hypothesis",
                    }
                ),
                "run_validity": {
                    "valid": False,
                    "status": "invalid",
                    "reason": "invalid_no_evaluated_outcome",
                },
                "stop_reason": (
                    "OUTER_HARDWALL_EXCEEDED"
                    if state == "interrupted"
                    else "unhandled_exception"
                ),
            }
        )
        if state == "unresolved":
            run["terminal_exception"] = {
                "reason": "unhandled_exception",
                "type": "RuntimeError",
                "message": "synthetic in-attempt failure",
            }
        else:
            run.pop("terminal_exception", None)
        run["qualification"]["disposition"] = "incomplete"

    return _sync_terminal_twins(root, mutate)


def _proposal_progress(branch_id: str, round_num: int) -> dict[str, Any]:
    return {
        "branch_id": branch_id,
        "stage": "proposal",
        "phase": "proposal_hypothesis",
        "round_num": round_num,
        "base_champion_id": 0,
        "branch_weight_revision": 0,
        "step_started_at": "2026-08-25T00:00:02+00:00",
        "complete": False,
        "last_progress_at": "2026-08-25T00:00:03+00:00",
        "branch_state": "explore",
    }


def _score(
    root: _InitialScreeningStudyRootArtifacts,
) -> dict[str, Any]:
    return _calculate_initial_screening_study_root_effectiveness(
        artifacts=root,
        loaded_history=LoadedHistoryAvailable(records=()),
    )


def _real_producer_protocol() -> Any:
    return replace(
        _complete_protocol(),
        reason_codes=("SCREENING_PASS",),
        case_feedback=(),
        candidate_attributable_infeasible_pairs=0,
    )


def _real_producer_campaign(tmp_path: Path) -> Any:
    manager = _campaign(
        tmp_path,
        experiment_protocol=MockExperimentProtocol(results=[_real_producer_protocol()]),
        qualification_only=_initial_only_config(attempt_cap=2),
        resource_envelope=_envelope(),
        code_research_limits=_limits(),
    )
    _install_synthetic_bounded_proposals(manager, candidates=1)
    generate_hypothesis = manager._explore_step_pipeline.generate_hypothesis
    generate_code = manager._explore_step_pipeline.generate_code

    def counted_hypothesis(branch: Any) -> Any:
        manager._provider_call_budget.consume(request_kind="hypothesis_research_turn")
        return generate_hypothesis(branch)

    def counted_code(branch: Any, hypothesis: Any) -> Any:
        manager._provider_call_budget.consume(request_kind="code_research_finalize")
        return generate_code(branch, hypothesis)

    manager._explore_step_pipeline.generate_hypothesis = counted_hypothesis
    manager._explore_step_pipeline.generate_code = counted_code
    return manager


def _real_producer_artifacts(
    tmp_path: Path,
) -> _InitialScreeningStudyRootArtifacts:
    campaign_root = tmp_path / "campaign"
    status = json.loads((campaign_root / "status.json").read_text(encoding="utf-8"))
    summary = json.loads(
        (campaign_root / "campaign_summary.json").read_text(encoding="utf-8")
    )
    history = tuple(
        json.loads(line)
        for line in (campaign_root / "research_history.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    effectiveness = replace(
        _expectation(a_cap=2, p_cap=200, k=1),
        problem_id="test_vrp",
        expected_initial_case_count=2,
        expected_initial_pair_count=4,
    )
    return _InitialScreeningStudyRootArtifacts(
        status=status,
        summary=summary,
        current_history=history,
        expectation=_InitialScreeningStudyExpectation(
            effectiveness=effectiveness,
            case_refs=_PRODUCER_CASE_REFS,
            seeds=_PRODUCER_SEEDS,
            equivalence_band=0.0,
        ),
    )


def _assert_real_producer_roundtrip(
    root: _InitialScreeningStudyRootArtifacts,
) -> dict[str, Any]:
    status_before = deepcopy(root.status)
    summary_before = deepcopy(root.summary)
    history_before = deepcopy(root.current_history)
    result = _score(root)
    result_before = deepcopy(result)

    assert root.status == status_before
    assert root.summary == summary_before
    assert root.current_history == history_before

    forbidden_values = {
        str(root.status["campaign_id"]),
        *_PRODUCER_CASE_REFS,
        *(str(branch["id"]) for branch in root.status["branches"]),
    }
    for record in root.current_history:
        hypothesis = record.get("hypothesis")
        if isinstance(hypothesis, dict):
            forbidden_values.add(str(hypothesis.get("text", "")))
        patch = record.get("patch")
        if isinstance(patch, dict):
            for change in patch.get("changes", []):
                if isinstance(change, dict):
                    forbidden_values.add(str(change.get("file_path", "")))
                    forbidden_values.add(str(change.get("source", "")))
    rendered = json.dumps(result, sort_keys=True)
    assert all(not value or value not in rendered for value in forbidden_values)

    forbidden_keys = {
        "advance",
        "branch_id",
        "campaign_id",
        "case_id",
        "digest",
        "go",
        "hash",
        "patch",
        "path",
        "seed",
        "source",
    }

    def assert_safe_keys(value: Any) -> None:
        if isinstance(value, dict):
            assert not (set(value) & forbidden_keys)
            for nested in value.values():
                assert_safe_keys(nested)
        elif isinstance(value, list):
            for nested in value:
                assert_safe_keys(nested)

    assert_safe_keys(result)
    assert isinstance(root.status, dict)
    campaign_id = root.status["campaign_id"]
    root.status["campaign_id"] = "POST_SCORE_INPUT_MUTATION"
    assert result == result_before
    root.status["campaign_id"] = campaign_id
    result["physical"]["a_used"] = -1
    assert root.status == status_before
    assert root.summary == summary_before
    assert root.current_history == history_before
    return result_before


def _assert_input_error(
    root: _InitialScreeningStudyRootArtifacts,
    code: str,
) -> None:
    with pytest.raises(ResearchEffectivenessInputError, match=f"^{code}$"):
        _score(root)


def _block(ordinal: int) -> _MatchedInitialScreeningStudyBlock:
    k1_record = _formal_record(
        hypothesis_text=f"loaded k1 hypothesis {ordinal}",
        source=f"def improve():\n    return {ordinal}\n",
    )
    k2_record = _formal_record(
        hypothesis_text=f"novel k2 hypothesis {ordinal}",
        source=f"def improve():\n    return {100 + ordinal}\n",
    )
    return _MatchedInitialScreeningStudyBlock(
        k1=_study_root(
            records=(k1_record,),
            k=1,
            campaign_id=f"block-{ordinal}-k1",
        ),
        k2=_study_root(
            records=(k2_record,),
            k=2,
            campaign_id=f"block-{ordinal}-k2",
        ),
        loaded_history=LoadedHistoryAvailable(records=(deepcopy(k1_record),)),
    )


def test_single_root_decodes_cells_and_delegates_to_d2() -> None:
    result = _calculate_initial_screening_study_root_effectiveness(
        artifacts=_study_root(),
        loaded_history=LoadedHistoryAvailable(records=()),
    )

    assert result["scientific_status"] == {"value": "complete", "reasons": []}
    assert result["endpoint_status"] == {"value": "complete", "limitations": []}
    assert result["physical"]["a_used"] == result["physical"]["a_cap"] == 1
    assert result["adjusted"]["f"] == result["adjusted"]["g"] == 1
    assert result["adjusted"]["e"]["status"] == "FINITE"
    assert result["adjusted"]["e"]["value"] == pytest.approx(-0.15)


def test_absent_cells_remain_an_ordinal_placeholder_for_d2() -> None:
    result = _calculate_initial_screening_study_root_effectiveness(
        artifacts=_study_root(paired_cells={}),
        loaded_history=LoadedHistoryAvailable(records=()),
    )

    assert result["adjusted"]["f"] == 1
    assert result["adjusted"]["e"] == {"status": "UNAVAILABLE", "value": None}
    assert result["endpoint_status"] == {
        "value": "partial",
        "limitations": ["INITIAL_CELL_DATA_UNAVAILABLE"],
    }


def test_present_null_cells_are_not_treated_as_absence() -> None:
    with pytest.raises(
        ResearchEffectivenessInputError,
        match="STUDY_PAIRED_EFFECT_CELLS_INVALID",
    ):
        _calculate_initial_screening_study_root_effectiveness(
            artifacts=_study_root(paired_cells={1: None}),
            loaded_history=LoadedHistoryAvailable(records=()),
        )


def test_exact_five_study_blocks_delegate_to_existing_d3() -> None:
    result = _compare_five_block_initial_screening_study_roots(
        blocks=tuple(_block(ordinal) for ordinal in range(1, 6))
    )

    assert result["status"] == "endpoint_conditions_satisfied"
    assert result["counts"]["endpoint_conditions_satisfied"] == 5
    assert result["cross_block"]["k1"]["u_f"] == 0
    assert result["cross_block"]["k2"]["u_f"] == 5


def test_study_artifacts_are_private_and_repr_redacted() -> None:
    root = _study_root(campaign_id="PRIVATE_SENTINEL")
    block = _MatchedInitialScreeningStudyBlock(
        k1=root,
        k2=_study_root(k=2, campaign_id="other"),
        loaded_history=LoadedHistoryAvailable(records=()),
    )

    assert "PRIVATE_SENTINEL" not in repr(root)
    assert "PRIVATE_SENTINEL" not in repr(root.expectation)
    assert "PRIVATE_SENTINEL" not in repr(block)
    assert not hasattr(public_api, "InitialScreeningStudyRootArtifacts")
    assert not hasattr(
        public_api, "calculate_initial_screening_study_root_effectiveness"
    )


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"case_refs": [*_CASE_REFS]}, "STUDY_CASE_REFS_INVALID"),
        (
            {"case_refs": ("cases/alpha.vrp", "other/alpha.vrp")},
            "STUDY_CASE_BASENAMES_INVALID",
        ),
        ({"seeds": [17]}, "STUDY_SEEDS_INVALID"),
        ({"seeds": (True,)}, "STUDY_SEEDS_INVALID"),
        ({"equivalence_band": 0}, "STUDY_EQUIVALENCE_BAND_INVALID"),
        ({"equivalence_band": -0.1}, "STUDY_EQUIVALENCE_BAND_INVALID"),
        ({"equivalence_band": float("nan")}, "STUDY_EQUIVALENCE_BAND_INVALID"),
    ],
)
def test_study_expectation_rejects_noncanonical_controls(
    overrides: dict[str, Any], code: str
) -> None:
    values: dict[str, Any] = {
        "effectiveness": _expectation(a_cap=1, p_cap=40),
        "case_refs": _CASE_REFS,
        "seeds": _SEEDS,
        "equivalence_band": _EQUIVALENCE_BAND,
    }
    values.update(overrides)

    with pytest.raises((ValueError, ResearchEffectivenessInputError), match=code):
        _InitialScreeningStudyExpectation(**values)


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("mode", "qualification_v1", "STUDY_DEVELOPMENT_BOUNDARY_MODE_INVALID"),
        ("attempt_cap", 2, "QUALIFICATION_ATTEMPT_CAP_MISMATCH"),
        ("verified_cap", 2, "STUDY_QUALIFICATION_CAP_MISMATCH"),
        ("formal_cap", 2, "STUDY_QUALIFICATION_CAP_MISMATCH"),
        ("requested", 2, "STUDY_REQUESTED_ROUNDS_MISMATCH"),
        ("expanded", 1, "QUALIFICATION_SCREENING_COUNT_MISMATCH"),
        ("validation", 1, "FORBIDDEN_PROTOCOL_STAGE_COUNT"),
        ("frozen", 1, "FORBIDDEN_PROTOCOL_STAGE_COUNT"),
    ],
)
def test_initial_only_projection_controls_fail_closed(
    field: str, value: Any, code: str
) -> None:
    root = _study_root()

    def mutate(artifact: dict[str, Any]) -> None:
        run = artifact["run_result"]
        qualification = run["qualification"]
        if field == "mode":
            qualification["development_boundary_mode"] = value
        elif field == "attempt_cap":
            qualification["limits"]["max_proposal_attempts"] = value
        elif field == "verified_cap":
            qualification["limits"]["max_verified_candidate_chains"] = value
        elif field == "formal_cap":
            qualification["limits"]["max_formal_screening_stages"] = value
        elif field == "requested":
            run["requested_rounds"] = value
        elif field == "expanded":
            qualification["expanded_screening_stages"] = value
        else:
            run["protocol_stage_counts"][field] = value

    _assert_input_error(_sync_terminal_twins(root, mutate), code)


@pytest.mark.parametrize("case", ["timestamp", "mismatch", "summary_extra"])
def test_status_summary_snapshot_fails_closed(case: str) -> None:
    root = _study_root()
    status = deepcopy(root.status)
    summary = deepcopy(root.summary)
    if case == "timestamp":
        status["updated_at"] = ""
    elif case == "mismatch":
        summary["campaign_id"] = "different"
    else:
        summary["forged_terminal_field"] = 1

    with pytest.raises(ResearchEffectivenessInputError):
        _score(_replace_root(root, status=status, summary=summary))


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("case_ids", ["cases/beta.vrp", "cases/alpha.vrp"], "STUDY_CASE_REFS_MISMATCH"),
        ("seed_set", [18], "STUDY_SEEDS_MISMATCH"),
        ("method", "seed_vote_majority", "STUDY_CASE_AGGREGATION_INVALID"),
        ("effect_metric", "fleet_size", "STUDY_CASE_AGGREGATION_INVALID"),
        ("equivalence_band", 1.0, "STUDY_CASE_AGGREGATION_INVALID"),
    ],
)
def test_formal_row_ordinal_controls_are_exact(
    field: str, value: Any, code: str
) -> None:
    root = _study_root()
    summary = deepcopy(root.summary)
    protocol = summary["steps"][0]["protocol_result"]
    if field in {"case_ids", "seed_set"}:
        protocol[field] = value
    else:
        protocol["case_aggregation"][field] = value

    _assert_input_error(_replace_root(root, summary=summary), code)


@pytest.mark.parametrize(
    "field",
    [
        "attribution_scope",
        "protocol_comparison_scope",
        "evaluation_candidate",
        "current_step_change_scope",
        "incremental_effect_isolated",
        "target_files",
    ],
)
def test_candidate_composition_is_exact(field: str) -> None:
    root = _study_root()
    history = deepcopy(root.current_history)
    composition = history[0]["protocol"]["candidate_composition"]
    if field == "target_files":
        composition["current_step"]["target_files"] = ["operators/other.py"]
    elif field == "incremental_effect_isolated":
        composition[field] = False
    else:
        composition[field] = "forged"

    _assert_input_error(
        _replace_root(root, current_history=history),
        "STUDY_CANDIDATE_COMPOSITION_INVALID",
    )


@pytest.mark.parametrize("declared", ["n_cases", "total_pairs"])
def test_declared_matrix_shape_must_match_frozen_roster(declared: str) -> None:
    root = _study_root(paired_cells={})
    summary = deepcopy(root.summary)
    history = deepcopy(root.current_history)
    aggregate = history[0]["protocol"]["evidence"]["objective_outcome"]["aggregate"]
    protocol = summary["steps"][0]["protocol_result"]
    if declared == "total_pairs":
        aggregate["total_pairs"] = protocol["total_pairs"] = 3
    else:
        aggregate.update({"n_cases": 1, "wins": 1, "ties": 0})
        protocol.update(
            {
                "screening_case_total": 1,
                "screening_case_wins": 1,
                "screening_case_ties": 0,
            }
        )

    _assert_input_error(
        _replace_root(root, summary=summary, current_history=history),
        "STUDY_DECLARED_MATRIX_SHAPE_MISMATCH",
    )


def test_observed_failure_matrix_is_a_d2_quality_negative() -> None:
    failed = _protocol_failure(_formal_record(), candidate=1, champion=0)
    result = _score(_study_root(records=(failed,), paired_cells={}))

    assert result["adjusted"]["f"] == 1
    assert result["adjusted"]["g"] == 0
    assert result["adjusted"]["e"] == {
        "status": "POSITIVE_INFINITY",
        "value": None,
    }


@pytest.mark.parametrize(
    ("case", "code"),
    [
        ("schema", "STUDY_PAIRED_EFFECT_CELLS_INVALID"),
        ("metric", "STUDY_PAIRED_EFFECT_CELLS_INVALID"),
        ("outer_type", "STUDY_PAIRED_EFFECT_CELLS_INVALID"),
        ("cardinality", "STUDY_PAIRED_EFFECT_CELLS_INVALID"),
        ("cell_keys", "STUDY_PAIRED_EFFECT_CELL_INVALID"),
        ("candidate_bool", "STUDY_PAIRED_EFFECT_CELL_INVALID"),
        ("candidate_nan", "STUDY_PAIRED_EFFECT_CELL_INVALID"),
        ("candidate_negative", "STUDY_PAIRED_EFFECT_CELL_INVALID"),
        ("reference_inf", "STUDY_PAIRED_EFFECT_CELL_INVALID"),
    ],
)
def test_present_cell_payload_is_strict(case: str, code: str) -> None:
    payload = _cells_payload()
    if case == "schema":
        payload["schema_version"] = "future"
    elif case == "metric":
        payload["metric_name"] = "fleet_size"
    elif case == "outer_type":
        payload["cells"] = tuple(payload["cells"])
    elif case == "cardinality":
        payload["cells"] = payload["cells"][:1]
    elif case == "cell_keys":
        payload["cells"][0]["delta"] = 1
    elif case == "candidate_bool":
        payload["cells"][0]["candidate_value"] = True
    elif case == "candidate_nan":
        payload["cells"][0]["candidate_value"] = float("nan")
    elif case == "candidate_negative":
        payload["cells"][0]["candidate_value"] = -1
    else:
        payload["cells"][0]["reference_value"] = float("inf")

    _assert_input_error(_study_root(paired_cells={1: payload}), code)


def test_zero_candidate_is_valid_but_nonpositive_reference_is_d2_unscorable() -> None:
    result = _score(
        _study_root(
            paired_cells={
                1: _cells_payload(
                    candidate_values=(0, 0),
                    reference_values=(0, 100),
                )
            }
        )
    )

    assert result["adjusted"]["f"] == 1
    assert result["adjusted"]["e"] == {"status": "UNAVAILABLE", "value": None}
    assert result["endpoint_status"] == {
        "value": "partial",
        "limitations": ["BLOCK_UNSCORABLE"],
    }


def test_evaluated_stopped_prefix_delegates_as_inconclusive() -> None:
    result = _score(_stopped_prefix(_study_root(a_cap=2)))

    assert result["scientific_status"]["value"] == "incomplete"
    assert result["endpoint_status"]["value"] == "unavailable"
    assert "RUN_INCOMPLETE" in result["endpoint_status"]["limitations"]


def test_zero_evaluated_resource_prefix_is_canonical_incomplete() -> None:
    record = _hypothesis_free_record(
        outcome="resource_exhausted",
        reason_code="HYPOTHESIS_RESEARCH_TURN_CAP_EXHAUSTED",
    )
    result = _score(_study_root(records=(record,), a_cap=2, paired_cells={}))

    assert result["physical"]["a_used"] == 1
    assert result["scientific_status"]["value"] == "incomplete"


@pytest.mark.parametrize("failure_detail", ["lineage unavailable", ""])
def test_event_write_failure_is_exact_unprojected_formal_incomplete(
    failure_detail: str,
) -> None:
    result = _score(_event_write_failure_root(failure_detail=failure_detail))

    assert result["physical"]["a_used"] == 1
    assert result["physical"]["initial_protocol_dispatches"] == 0
    assert result["scientific_status"]["value"] == "incomplete"
    assert result["endpoint_status"]["limitations"] == ["RUN_INCOMPLETE"]


@pytest.mark.parametrize(
    "case",
    ["experiment_count", "reason", "stage", "verification", "ready"],
)
def test_event_write_failure_projection_mutations_fail_closed(case: str) -> None:
    root = _event_write_failure_root()

    def mutate(artifact: dict[str, Any]) -> None:
        if case == "experiment_count":
            artifact["n_experiments"] = 0
        elif case == "reason":
            if "steps" in artifact:
                artifact["steps"][0]["execution_outcome"]["reason_code"] = "OTHER"
            artifact["run_result"]["last_execution_outcome"]["reason_code"] = "OTHER"
        elif case == "stage":
            if "steps" in artifact:
                artifact["steps"][0]["failure_stage"] = "screening"
                artifact["steps"][0]["execution_outcome"]["provenance"]["stage"] = (
                    "screening"
                )
            artifact["run_result"]["last_execution_outcome"]["stage"] = "screening"
        elif case == "verification":
            if "steps" in artifact:
                artifact["steps"][0]["verification_passed"] = False
            artifact["run_result"]["qualification"]["verified_candidate_chains"] = 0
        else:
            artifact["proposal_runtime"]["attempts"][0]["code_candidates_ready"] = 0

    with pytest.raises(ResearchEffectivenessInputError):
        _score(_sync_terminal_twins(root, mutate))


def test_stopped_prefix_accepts_one_unmatched_terminal_attempt() -> None:
    result = _score(_unmatched_nonclosed_root())
    assert result["physical"]["a_used"] == 2
    assert result["scientific_status"]["value"] == "incomplete"


@pytest.mark.parametrize("state", ["explore", "blocked_infra"])
def test_unmatched_rowless_branch_must_be_clean_explore(state: str) -> None:
    root = _unmatched_nonclosed_root()

    def mutate(artifact: dict[str, Any]) -> None:
        extra = deepcopy(artifact["branches"][0])
        extra.update(
            {
                "id": "unmatched-rowless-branch",
                "state": state,
                "failure_codes": (
                    [] if state == "explore" else ["OUTER_HARDWALL_EXCEEDED"]
                ),
            }
        )
        artifact["branches"].append(extra)
        if state == "explore":
            artifact["active_slots"]["used"] += 1
            artifact["active_slots"]["available"] -= 1
            artifact["active_slots"]["branch_ids"].append(extra["id"])
            artifact["n_active_branches"] += 1

    candidate = _sync_terminal_twins(root, mutate)
    if state == "explore":
        assert _score(candidate)["scientific_status"]["value"] == "incomplete"
    else:
        with pytest.raises(ResearchEffectivenessInputError):
            _score(candidate)


@pytest.mark.parametrize("state", ["unresolved", "interrupted"])
def test_stopped_prefix_accepts_a_durable_nonclosed_preformal_row(
    state: str,
) -> None:
    result = _score(_durable_nonclosed_root(state))

    assert result["physical"]["a_used"] == 1
    assert result["scientific_status"]["value"] == "incomplete"


@pytest.mark.parametrize(
    "case",
    ["scheduled", "active", "round", "validity"],
)
def test_stopped_prefix_inventory_mutations_fail_closed(case: str) -> None:
    root = _stopped_prefix(_study_root(a_cap=2))

    def mutate(artifact: dict[str, Any]) -> None:
        run = artifact["run_result"]
        if case == "scheduled":
            run["scheduled_calls"] = 0
        elif case == "active":
            artifact["proposal_runtime"]["attempts"][0]["accounting_state"] = "active"
        elif case == "round":
            artifact["proposal_runtime"]["attempts"][0]["round_num"] = 2
        else:
            run["run_validity"] = {
                "valid": True,
                "status": "valid",
                "reason": "valid",
            }

    with pytest.raises(ResearchEffectivenessInputError):
        _score(_sync_terminal_twins(root, mutate))


def test_stopped_prefix_rejects_rows_after_a_terminal_outcome() -> None:
    terminal = _hypothesis_free_record(
        outcome="resource_exhausted",
        reason_code="HYPOTHESIS_RESEARCH_TURN_CAP_EXHAUSTED",
    )
    later = _hypothesis_free_record(
        outcome="research_rejected",
        reason_code="HYPOTHESIS_RESEARCH_ABANDONED",
    )
    root = _study_root(
        records=(terminal, later),
        a_cap=2,
        paired_cells={},
    )

    _assert_input_error(root, "STUDY_STOPPED_TERMINAL_PROJECTION_INVALID")


def test_repeated_preformal_rejections_can_reuse_clean_explore_branch() -> None:
    records = tuple(
        _hypothesis_free_record(
            outcome="research_rejected",
            reason_code="HYPOTHESIS_RESEARCH_ABANDONED",
        )
        for _ in range(2)
    )
    result = _score(
        _study_root(
            records=records,
            a_cap=2,
            branch_ids=("shared-branch", "shared-branch"),
            paired_cells={},
        )
    )

    assert result["scientific_status"]["value"] == "complete"
    assert result["physical"]["a_used"] == 2


@pytest.mark.parametrize("shape", ["twice", "after_retirement"])
def test_retired_branch_cannot_be_reused(shape: str) -> None:
    first = _formal_record(hypothesis_text="first")
    second = (
        _formal_record(hypothesis_text="second")
        if shape == "twice"
        else _hypothesis_free_record(
            outcome="research_rejected",
            reason_code="HYPOTHESIS_RESEARCH_ABANDONED",
        )
    )
    root = _study_root(
        records=(first, second),
        a_cap=2,
        branch_ids=("shared-branch", "shared-branch"),
        paired_cells={},
    )

    _assert_input_error(root, "STUDY_BRANCH_RETIREMENT_SEQUENCE_INVALID")


def test_stopped_formal_abandon_remains_visible_and_parked() -> None:
    failed = _protocol_failure(_formal_record(), candidate=1, champion=0)
    root = _stopped_prefix(_study_root(records=(failed,), a_cap=2, paired_cells={}))

    assert root.status["branches"][0]["state"] == "parked_lineage"
    assert _score(root)["scientific_status"]["value"] == "incomplete"


def test_reference_canary_abandonment_is_omitted_from_reportable_branches() -> None:
    root = _stopped_prefix(
        _study_root(
            records=(_canary_record(canary_code="CANARY_CHAMPION_FAILURE"),),
            a_cap=2,
            paired_cells={},
        ),
        reason="evaluated_without_formal_protocol_result",
    )
    status = deepcopy(root.status)
    summary = deepcopy(root.summary)
    _set_canary_category(
        status,
        summary,
        step_index=0,
        category="incomplete_evidence",
    )
    for artifact in (status, summary):
        artifact["branches"] = []
        artifact["n_active_branches"] = 0
        artifact["active_slots"].update({"used": 0, "available": 8, "branch_ids": []})
    result = _score(_replace_root(root, status=status, summary=summary))

    assert result["physical"]["champion_failure_candidates"] == 1
    assert result["scientific_status"]["value"] == "incomplete"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("state", "ready_validate"),
        ("current_code_hash", "forged"),
        ("direction", "forged"),
        ("base_champion_id", 1),
        ("weight_revision", 1),
    ],
)
def test_branch_authority_mutations_fail_closed(field: str, value: Any) -> None:
    root = _study_root()

    def mutate(artifact: dict[str, Any]) -> None:
        artifact["branches"][0][field] = value

    with pytest.raises(ResearchEffectivenessInputError):
        _score(_sync_terminal_twins(root, mutate))


@pytest.mark.parametrize("field", ["used", "max", "available", "n_active"])
def test_active_inventory_rejects_bool_counts(field: str) -> None:
    rejected = _hypothesis_free_record(
        outcome="research_rejected",
        reason_code="HYPOTHESIS_RESEARCH_ABANDONED",
    )
    root = _study_root(records=(rejected,), paired_cells={})

    def mutate(artifact: dict[str, Any]) -> None:
        if field == "n_active":
            artifact["n_active_branches"] = True
        else:
            artifact["active_slots"][field] = True

    with pytest.raises(ResearchEffectivenessInputError):
        _score(_sync_terminal_twins(root, mutate))


def test_blocked_branch_must_be_the_typed_terminal_row() -> None:
    rejected = _hypothesis_free_record(
        outcome="research_rejected",
        reason_code="HYPOTHESIS_RESEARCH_ABANDONED",
    )
    root = _stopped_prefix(_study_root(records=(rejected,), a_cap=2, paired_cells={}))

    def mutate(artifact: dict[str, Any]) -> None:
        branch = artifact["branches"][0]
        branch["state"] = "blocked_infra"
        branch["failure_codes"] = ["HYPOTHESIS_RESEARCH_ABANDONED"]
        artifact["n_active_branches"] = 0
        artifact["active_slots"].update({"used": 0, "available": 8, "branch_ids": []})
        artifact["run_result"]["run_validity"] = {
            "valid": False,
            "status": "invalid",
            "reason": "invalid_no_evaluated_outcome",
        }

    with pytest.raises(ResearchEffectivenessInputError):
        _score(_sync_terminal_twins(root, mutate))


def test_real_json_sort_keys_roundtrip_keeps_runtime_authority() -> None:
    rejected = _hypothesis_free_record(
        outcome="research_rejected",
        reason_code="HYPOTHESIS_RESEARCH_ABANDONED",
    )
    root = _study_root(records=(rejected,), paired_cells={})
    status = json.loads(json.dumps(root.status, sort_keys=True))
    summary = json.loads(json.dumps(root.summary, sort_keys=True))

    result = _score(_replace_root(root, status=status, summary=summary))

    assert result["physical"]["a_used"] == 1
    assert (
        result["physical"]["provider_calls_by_request_kind"]["hypothesis_research_turn"]
        == 1
    )
    assert status["run_result"]["failure_categories"] == {"research_rejected": 1}


def test_pre_reservation_interrupt_is_typed_incomplete() -> None:
    result = _score(_pre_reservation_interrupt_root())

    assert result["physical"]["a_used"] == 0
    assert result["scientific_status"]["value"] == "incomplete"
    assert result["endpoint_status"]["limitations"] == ["RUN_INCOMPLETE"]


@pytest.mark.parametrize(
    ("kind", "with_prefix", "total_rounds", "proposal_attempts", "a_used"),
    [
        ("zero", False, 0, 0, 0),
        ("admitted", False, 0, 0, 0),
        ("admitted", True, 1, 1, 1),
        ("pre_reservation", False, 1, 0, 0),
        ("pre_reservation", True, 2, 1, 1),
        ("reserved", False, 1, 1, 0),
        ("reserved", True, 2, 2, 1),
    ],
)
def test_pre_attempt_interrupt_taxonomy_is_typed_incomplete(
    kind: str,
    with_prefix: bool,
    total_rounds: int,
    proposal_attempts: int,
    a_used: int,
) -> None:
    root = _pre_attempt_interrupt_root(kind, with_prefix=with_prefix)

    result = _score(root)

    assert root.status["total_rounds"] == total_rounds
    assert (
        root.status["run_result"]["qualification"]["proposal_attempts"]
        == proposal_attempts
    )
    assert result["physical"]["a_used"] == a_used
    assert result["scientific_status"]["value"] == "incomplete"
    assert result["endpoint_status"]["limitations"] == ["RUN_INCOMPLETE"]


@pytest.mark.parametrize(
    ("kind", "with_prefix"),
    [
        ("zero", False),
        ("admitted", False),
        ("admitted", True),
        ("pre_reservation", False),
        ("pre_reservation", True),
        ("reserved", False),
        ("reserved", True),
    ],
)
def test_pre_attempt_interrupt_rejects_balance_exhaustion(
    kind: str, with_prefix: bool
) -> None:
    root = _pre_attempt_interrupt_root(kind, with_prefix=with_prefix)

    def mutate(artifact: dict[str, Any]) -> None:
        artifact["balance_exhausted"] = True

    with pytest.raises(ResearchEffectivenessInputError):
        _score(_sync_terminal_twins(root, mutate))


@pytest.mark.parametrize(
    ("kind", "with_prefix"),
    [
        ("zero", False),
        ("admitted", False),
        ("pre_reservation", False),
        ("reserved", False),
        ("admitted", True),
        ("pre_reservation", True),
        ("reserved", True),
    ],
)
def test_pre_attempt_interrupt_rejects_terminal_progress(
    kind: str, with_prefix: bool
) -> None:
    root = _pre_attempt_interrupt_root(kind, with_prefix=with_prefix)
    branch_id = (
        root.status["branches"][-1]["id"]
        if root.status["branches"]
        else "forged-zero-branch"
    )

    def mutate(artifact: dict[str, Any]) -> None:
        artifact["current_progress"] = _proposal_progress(
            branch_id,
            artifact["total_rounds"] or 1,
        )

    with pytest.raises(ResearchEffectivenessInputError):
        _score(_sync_terminal_twins(root, mutate))


def test_pre_reservation_progress_is_rejected_after_terminal_cleanup() -> None:
    root = _pre_reservation_interrupt_root()

    def mutate(artifact: dict[str, Any]) -> None:
        artifact["current_progress"] = _proposal_progress("pre-reservation-branch", 1)

    with pytest.raises(ResearchEffectivenessInputError):
        _score(_sync_terminal_twins(root, mutate))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("stage", "validation"),
        ("phase", "proposal_code"),
        ("round_num", 2),
        ("branch_id", "wrong-branch"),
        ("base_champion_id", 1),
        ("branch_weight_revision", 1),
        ("branch_state", "ready_validate"),
        ("complete", True),
        ("step_started_at", ""),
    ],
)
def test_pre_reservation_progress_mutations_fail_closed(field: str, value: Any) -> None:
    root = _pre_reservation_interrupt_root()

    def mutate(artifact: dict[str, Any]) -> None:
        progress = _proposal_progress("pre-reservation-branch", 1)
        progress[field] = value
        artifact["current_progress"] = progress

    with pytest.raises(ResearchEffectivenessInputError):
        _score(_sync_terminal_twins(root, mutate))


@pytest.mark.parametrize(
    "root",
    [
        pytest.param(_unmatched_nonclosed_root(), id="unmatched"),
        pytest.param(_durable_nonclosed_root("unresolved"), id="durable"),
    ],
)
def test_nonclosed_proposal_progress_is_rejected_after_terminal_cleanup(
    root: _InitialScreeningStudyRootArtifacts,
) -> None:
    branch_id = str(root.summary["steps"][-1]["branch_id"])
    round_num = len(root.status["proposal_runtime"]["attempts"])

    def mutate(artifact: dict[str, Any]) -> None:
        artifact["current_progress"] = _proposal_progress(branch_id, round_num)

    with pytest.raises(ResearchEffectivenessInputError):
        _score(_sync_terminal_twins(root, mutate))


@pytest.mark.parametrize("stage", ["canary", "screening", "validation", "frozen"])
def test_nonclosed_nonproposal_progress_is_rejected(stage: str) -> None:
    root = _unmatched_nonclosed_root()

    def mutate(artifact: dict[str, Any]) -> None:
        progress = _proposal_progress("branch-1", 2)
        progress["stage"] = stage
        artifact["current_progress"] = progress

    with pytest.raises(ResearchEffectivenessInputError):
        _score(_sync_terminal_twins(root, mutate))


def test_closed_stopped_root_rejects_current_progress() -> None:
    root = _stopped_prefix(_study_root(a_cap=2))

    def mutate(artifact: dict[str, Any]) -> None:
        artifact["current_progress"] = _proposal_progress("branch-1", 1)

    with pytest.raises(ResearchEffectivenessInputError):
        _score(_sync_terminal_twins(root, mutate))


@pytest.mark.parametrize(
    "case",
    ["unknown", "counted_row", "closed_attempt", "formal_row", "verified_row"],
)
def test_durable_nonclosed_projection_mutations_fail_closed(case: str) -> None:
    root = _durable_nonclosed_root("unresolved")
    if case == "formal_row":
        attempt = _attempt(
            1,
            {"code_research_finalize": 1},
            completed=1,
            selected=1,
            exported=1,
            patches=1,
            ready=1,
        )
        attempt["accounting_state"] = "unresolved"
        root = _stopped_prefix(_study_root(a_cap=2, attempts_override=[attempt]))

    def mutate(artifact: dict[str, Any]) -> None:
        run = artifact["run_result"]
        if case == "unknown":
            run["unknown_outcome_count"] = 0
        elif case == "counted_row":
            run["execution_outcome_counts"]["research_rejected"] = 1
            run["failure_categories"] = {"research_rejected": 1}
        elif case == "closed_attempt":
            artifact["proposal_runtime"]["attempts"][-1]["accounting_state"] = "closed"
        elif case == "verified_row":
            if "steps" in artifact:
                artifact["steps"][-1]["verification_passed"] = True
            run["qualification"]["verified_candidate_chains"] = 1

    with pytest.raises(ResearchEffectivenessInputError):
        _score(_sync_terminal_twins(root, mutate))


@pytest.mark.parametrize(
    "case",
    ["unknown", "last_stage", "terminal_exception", "cap_full", "disposition"],
)
def test_pre_reservation_terminal_mutations_fail_closed(case: str) -> None:
    root = _pre_reservation_interrupt_root()

    def mutate(artifact: dict[str, Any]) -> None:
        run = artifact["run_result"]
        if case == "unknown":
            run["unknown_outcome_count"] = 1
        elif case == "last_stage":
            run["last_execution_outcome"]["stage"] = "screening"
        elif case == "terminal_exception":
            run["terminal_exception"] = {
                "reason": "OUTER_HARDWALL_EXCEEDED",
                "type": "RuntimeError",
                "message": "forged",
            }
        elif case == "cap_full":
            run["qualification"]["limits"]["max_proposal_attempts"] = 0
        else:
            run["qualification"]["disposition"] = "pending"

    with pytest.raises(ResearchEffectivenessInputError):
        _score(_sync_terminal_twins(root, mutate))


@pytest.mark.parametrize(
    ("location", "field"),
    [
        ("step", "validation_result"),
        ("protocol", "heldout_evidence"),
    ],
)
def test_summary_step_and_protocol_unknown_fields_fail_closed(
    location: str, field: str
) -> None:
    root = _study_root()
    summary = deepcopy(root.summary)
    target = (
        summary["steps"][0]
        if location == "step"
        else summary["steps"][0]["protocol_result"]
    )
    target[field] = {"private": "sentinel"}

    with pytest.raises(ResearchEffectivenessInputError):
        _score(_replace_root(root, summary=summary))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("diagnostics", [{"heldout": "sentinel"}]),
        ("verification_failure_breakdown", {"x": True}),
        ("action_locus_coverage", {"x": -1}),
        ("family_coverage", {"x": 2}),
    ],
)
def test_summary_only_diagnostics_and_counts_fail_closed(
    field: str, value: Any
) -> None:
    root = _study_root()
    summary = deepcopy(root.summary)
    summary[field] = value

    with pytest.raises(ResearchEffectivenessInputError):
        _score(_replace_root(root, summary=summary))


def test_campaign_mode_must_be_exact_qualification_only() -> None:
    root = _study_root()

    def mutate(artifact: dict[str, Any]) -> None:
        artifact["campaign_mode"] = "qualification"

    _assert_input_error(
        _sync_terminal_twins(root, mutate), "CAMPAIGN_MODE_NOT_QUALIFICATION_ONLY"
    )


def test_case_feedback_uses_ordered_public_case_basenames() -> None:
    root = _study_root()
    summary = deepcopy(root.summary)
    summary["steps"][0]["case_feedback_summary"] = [
        {
            "case_id": "alpha.vrp",
            "dominant_result": "win",
            "seed_pattern": "uniform",
            "decisive": "total_distance",
            "median_deltas": {"total_distance": 10.0},
        },
        {
            "case_id": "beta.vrp",
            "dominant_result": "tie",
            "seed_pattern": "heterogeneous",
            "decisive": "tie",
            "median_deltas": {"total_distance": 0.0},
        },
    ]

    assert _score(_replace_root(root, summary=summary))["adjusted"]["f"] == 1


def test_case_feedback_cannot_attach_to_a_preformal_row() -> None:
    rejected = _hypothesis_free_record(
        outcome="research_rejected",
        reason_code="HYPOTHESIS_RESEARCH_ABANDONED",
    )
    root = _study_root(records=(rejected,), paired_cells={})
    summary = deepcopy(root.summary)
    summary["steps"][0]["case_feedback_summary"] = [{}]

    with pytest.raises(ResearchEffectivenessInputError):
        _score(_replace_root(root, summary=summary))


def test_seed_bool_cannot_equal_the_frozen_integer_seed() -> None:
    root = _study_root()
    summary = deepcopy(root.summary)
    summary["steps"][0]["protocol_result"]["seed_set"] = [True]
    expectation = replace(root.expectation, seeds=(1,))

    _assert_input_error(
        _replace_root(root, summary=summary, expectation=expectation),
        "STUDY_SEEDS_MISMATCH",
    )


def test_preflight_exception_is_typed_incomplete() -> None:
    result = _score(_preflight_exception_root())

    assert result["physical"]["a_used"] == 0
    assert result["scientific_status"]["value"] == "incomplete"


@pytest.mark.parametrize("retain_current", [False, True])
def test_closed_cleanup_exception_accepts_both_last_result_windows(
    retain_current: bool,
) -> None:
    result = _score(
        _closed_cleanup_exception_root(retain_current_last_result=retain_current)
    )

    assert result["physical"]["a_used"] == 1
    assert result["scientific_status"]["value"] == "incomplete"


def test_closed_unhandled_accepts_a_balance_marked_noncontinuable_row() -> None:
    terminal = _hypothesis_free_record(
        outcome="resource_exhausted",
        reason_code="PROVIDER_BALANCE_EXHAUSTED",
    )
    root = _study_root(records=(terminal,), a_cap=2, paired_cells={})

    def mutate(artifact: dict[str, Any]) -> None:
        artifact["balance_exhausted"] = True
        run = artifact["run_result"]
        run["stop_reason"] = "unhandled_exception"
        run["terminal_exception"] = {
            "reason": "unhandled_exception",
            "type": "RuntimeError",
            "message": "post-accounting failure",
        }

    result = _score(_sync_terminal_twins(root, mutate))
    assert result["scientific_status"]["value"] == "incomplete"


@pytest.mark.parametrize(
    "stop_reason",
    [
        "OUTER_HARDWALL_EXCEEDED",
        "external_stop_requested",
        "signal:SIGINT",
        "signal:SIGTERM",
    ],
)
def test_closed_fully_accounted_terminal_row_accepts_deferred_external_override(
    stop_reason: str,
) -> None:
    terminal = _hypothesis_free_record(
        outcome="resource_exhausted",
        reason_code="HYPOTHESIS_RESEARCH_TURN_CAP_EXHAUSTED",
    )
    root = _study_root(records=(terminal,), a_cap=2, paired_cells={})

    def mutate(artifact: dict[str, Any]) -> None:
        artifact["run_result"]["stop_reason"] = stop_reason

    candidate = _sync_terminal_twins(root, mutate)
    result = _score(candidate)

    assert result["scientific_status"]["value"] == "incomplete"
    assert (
        candidate.status["run_result"]["execution_outcome_counts"]["resource_exhausted"]
        == 1
    )
    assert (
        candidate.status["run_result"]["execution_outcome_counts"]["interrupted"] == 0
    )
    assert candidate.status["run_result"]["last_execution_outcome"] == {
        "outcome": "resource_exhausted",
        "reason_code": "HYPOTHESIS_RESEARCH_TURN_CAP_EXHAUSTED",
        "stage": "proposal_hypothesis",
    }


def test_closed_balance_row_accepts_deferred_hardwall_override() -> None:
    terminal = _hypothesis_free_record(
        outcome="resource_exhausted",
        reason_code="PROVIDER_BALANCE_EXHAUSTED",
    )
    root = _study_root(records=(terminal,), a_cap=2, paired_cells={})

    def mutate(artifact: dict[str, Any]) -> None:
        artifact["balance_exhausted"] = True
        artifact["run_result"]["stop_reason"] = "OUTER_HARDWALL_EXCEEDED"

    result = _score(_sync_terminal_twins(root, mutate))

    assert result["scientific_status"]["value"] == "incomplete"


@pytest.mark.parametrize(
    ("stop_reason", "exception_reason"),
    [
        ("OUTER_HARDWALL_EXCEEDED", "unhandled_exception"),
        ("unhandled_exception", None),
        ("qualification_heldout_stage_observed", None),
    ],
)
def test_closed_stop_and_exception_taxonomy_fail_closed(
    stop_reason: str, exception_reason: str | None
) -> None:
    root = _stopped_prefix(_study_root(a_cap=2), reason=stop_reason)

    def mutate(artifact: dict[str, Any]) -> None:
        run = artifact["run_result"]
        if exception_reason is None:
            run.pop("terminal_exception", None)
        else:
            run["terminal_exception"] = {
                "reason": exception_reason,
                "type": "RuntimeError",
                "message": "forged",
            }

    with pytest.raises(ResearchEffectivenessInputError):
        _score(_sync_terminal_twins(root, mutate))


def test_api_balance_stop_requires_flag_and_a_continuable_last_row() -> None:
    root = _stopped_prefix(_study_root(a_cap=2), reason="api_balance_exhausted")

    def flag(artifact: dict[str, Any]) -> None:
        artifact["balance_exhausted"] = True

    result = _score(_sync_terminal_twins(root, flag))
    assert result["scientific_status"]["value"] == "incomplete"

    with pytest.raises(ResearchEffectivenessInputError):
        _score(root)


@pytest.mark.parametrize("state", ["unresolved", "interrupted"])
@pytest.mark.parametrize("case", ["histogram", "unknown", "exception", "last"])
def test_unmatched_terminal_projection_mutations_fail_closed(
    state: str, case: str
) -> None:
    root = _unmatched_nonclosed_root(state)

    def mutate(artifact: dict[str, Any]) -> None:
        run = artifact["run_result"]
        if case == "histogram":
            run["execution_outcome_counts"]["research_rejected"] = 0
        elif case == "unknown":
            run["unknown_outcome_count"] = 1 - int(state == "unresolved")
        elif case == "exception":
            if state == "unresolved":
                run.pop("terminal_exception", None)
            else:
                run["terminal_exception"] = {
                    "reason": run["stop_reason"],
                    "type": "RuntimeError",
                    "message": "forged",
                }
        else:
            run["last_execution_outcome"] = None

    with pytest.raises(ResearchEffectivenessInputError):
        _score(_sync_terminal_twins(root, mutate))


@pytest.mark.parametrize("ready", [False, True])
def test_unprojected_experiment_requires_ready_carrier(ready: bool) -> None:
    root = _unmatched_nonclosed_root(ready=ready)

    def mutate(artifact: dict[str, Any]) -> None:
        artifact["n_experiments"] = 1

    candidate = _sync_terminal_twins(root, mutate)
    if ready:
        assert _score(candidate)["scientific_status"]["value"] == "incomplete"
    else:
        with pytest.raises(ResearchEffectivenessInputError):
            _score(candidate)


def test_unprojected_experiment_cannot_retain_proposal_progress() -> None:
    root = _unmatched_nonclosed_root(ready=True)

    def mutate(artifact: dict[str, Any]) -> None:
        artifact["n_experiments"] = 1
        artifact["current_progress"] = _proposal_progress("branch-1", 2)

    with pytest.raises(ResearchEffectivenessInputError):
        _score(_sync_terminal_twins(root, mutate))


def test_all_ten_arms_decode_before_an_inconclusive_study(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    blocks = [_block(ordinal) for ordinal in range(1, 6)]
    blocks[0] = replace(
        blocks[0],
        k1=_study_root(
            k=1,
            campaign_id="block-1-k1",
            paired_cells={},
        ),
    )
    original = study_root_module._decode_study_root
    calls = 0

    def counted(artifacts: _InitialScreeningStudyRootArtifacts) -> Any:
        nonlocal calls
        calls += 1
        return original(artifacts)

    monkeypatch.setattr(study_root_module, "_decode_study_root", counted)

    result = _compare_five_block_initial_screening_study_roots(blocks=tuple(blocks))

    assert calls == 10
    assert result["status"] == "inconclusive"


def test_real_producer_completed_rejection_reuse_and_formal_roundtrip(
    tmp_path: Path,
) -> None:
    manager = _real_producer_campaign(tmp_path)
    manager._scheduler = Scheduler(max_active_branches=1)
    manager._branch_step_runner.scheduler = manager._scheduler
    successful_hypothesis = manager._explore_step_pipeline.generate_hypothesis
    calls = 0

    def reject_once(branch: Any) -> Any:
        nonlocal calls
        calls += 1
        if calls == 1:
            manager._provider_call_budget.consume(
                request_kind="hypothesis_research_turn"
            )
            return ProposalAttempt.failure(
                ExecutionOutcomeRecord(
                    outcome=ExecutionOutcome.RESEARCH_REJECTED,
                    reason_code="HYPOTHESIS_RESEARCH_ABSTAINED",
                    provenance={"stage": "proposal_hypothesis"},
                )
            )
        return successful_hypothesis(branch)

    manager._explore_step_pipeline.generate_hypothesis = reject_once
    terminal = manager.run(requested_rounds=2)
    root = _real_producer_artifacts(tmp_path)

    assert terminal.completed is True
    assert root.status["run_result"]["status"] == "completed"
    assert [step["execution_outcome"]["outcome"] for step in root.summary["steps"]] == [
        "research_rejected",
        "evaluated",
    ]
    assert len({step["branch_id"] for step in root.summary["steps"]}) == 1
    assert [branch["state"] for branch in root.status["branches"]] == ["parked_lineage"]

    result = _assert_real_producer_roundtrip(root)

    assert result["scientific_status"] == {"value": "complete", "reasons": []}
    assert result["physical"]["a_used"] == 2
    assert result["physical"]["h"] == 1
    assert result["physical"]["initial_protocol_dispatches"] == 1


def test_real_producer_r1_reserved_pre_attempt_roundtrip_is_incomplete(
    tmp_path: Path,
) -> None:
    manager = _real_producer_campaign(tmp_path)
    hardwall = _CampaignOuterHardwall(None)
    hardwall.expired.set()
    attempt_scope = manager._explore_step_pipeline.proposal_attempt_scope
    reservations = 0

    with _campaign_signal_handlers(manager, hardwall=hardwall):
        handler = signal.getsignal(signal.SIGTERM)
        assert callable(handler)

        def interrupt_second_reservation(round_num: int) -> Any:
            nonlocal reservations
            reservations += 1
            if reservations == 2:
                handler(signal.SIGTERM, None)
            return attempt_scope(round_num)

        manager._explore_step_pipeline.proposal_attempt_scope = (
            interrupt_second_reservation
        )
        with pytest.raises(_CampaignSignalStop) as raised:
            manager.run(requested_rounds=2)

    manager.finalize_requested_stop(
        raised.value.reason,
        interrupted_override=raised.value.interrupted_override,
    )
    root = _real_producer_artifacts(tmp_path)
    run = root.status["run_result"]

    assert run["status"] == "stopped"
    assert run["scheduled_calls"] == 2
    assert run["qualification"]["proposal_attempts"] == 2
    assert root.status["total_rounds"] == 2
    assert len(root.status["proposal_runtime"]["attempts"]) == 1
    assert "current_progress" not in root.status

    result = _assert_real_producer_roundtrip(root)

    assert result["endpoint_status"]["value"] == "unavailable"
    assert "RUN_INCOMPLETE" in result["endpoint_status"]["limitations"]
    assert result["scientific_status"]["value"] == "incomplete"
    assert result["physical"]["a_used"] == 1


def test_real_producer_event_write_failure_roundtrip_is_incomplete(
    tmp_path: Path,
) -> None:
    manager = _real_producer_campaign(tmp_path)

    def fail_lineage(*_args: Any, **_kwargs: Any) -> None:
        raise OSError()

    manager._decision_finalizer.record_step_lineage = fail_lineage
    terminal = manager.run(requested_rounds=2)
    root = _real_producer_artifacts(tmp_path)
    run = root.status["run_result"]
    step = root.summary["steps"][0]

    assert terminal.completed is False
    assert run["stop_reason"] == "execution_blocked_infra"
    assert root.status["n_experiments"] == 1
    assert root.status["screened_experiments"] == 0
    assert step["execution_outcome"]["reason_code"] == ("EXPERIMENT_EVENT_WRITE_FAILED")
    assert step["failure_detail"] == ""
    assert root.status["branches"][0]["state"] == "blocked_infra"
    assert root.status["branches"][0]["current_code_hash"] is None

    result = _assert_real_producer_roundtrip(root)

    assert result["endpoint_status"] == {
        "value": "unavailable",
        "limitations": ["RUN_INCOMPLETE"],
    }
    assert result["scientific_status"]["value"] == "incomplete"
    assert result["physical"]["a_used"] == 1
    assert result["physical"]["c_ready"] == 1
    assert result["physical"]["initial_protocol_dispatches"] == 0


def _sentinelized_root(
    root: _InitialScreeningStudyRootArtifacts,
    *,
    ordinal: int,
) -> _InitialScreeningStudyRootArtifacts:
    status = deepcopy(root.status)
    summary = deepcopy(root.summary)
    history = deepcopy(root.current_history)
    case_refs = (
        f"cases/CASE_PATH_PRIVATE_SENTINEL_{ordinal}.vrp",
        f"cases/control_{ordinal}.vrp",
    )
    seed = 867_530_900 + ordinal
    status["campaign_id"] = f"CAMPAIGN_PRIVATE_SENTINEL_{ordinal}"
    summary["campaign_id"] = status["campaign_id"]
    step = summary["steps"][0]
    step["hypothesis"]["text"] = f"H_PRIVATE_SENTINEL_{ordinal}"
    protocol = step["protocol_result"]
    protocol["case_ids"] = list(case_refs)
    protocol["seed_set"] = [seed]
    protocol["paired_effect_cells"]["cells"][0].update(
        {"candidate_value": 987_654_300 + ordinal, "reference_value": 987_654_400}
    )
    record = history[0]
    record["hypothesis"]["text"] = step["hypothesis"]["text"]
    patch_path = f"operators/PATCH_PATH_PRIVATE_SENTINEL_{ordinal}.py"
    record["patch"]["changes"][0].update(
        {
            "file_path": patch_path,
            "source": f"PATCH_SOURCE_PRIVATE_SENTINEL_{ordinal}",
        }
    )
    record["protocol"]["candidate_composition"]["current_step"] = {
        "target_files": [patch_path]
    }
    expectation = replace(root.expectation, case_refs=case_refs, seeds=(seed,))
    return _replace_root(
        root,
        status=status,
        summary=summary,
        current_history=history,
        expectation=expectation,
    )


def test_s2_outputs_recursively_hide_all_ten_arm_identity_sentinels() -> None:
    private_blocks: list[_MatchedInitialScreeningStudyBlock] = []
    forbidden: list[str] = []
    for block_ordinal in range(1, 6):
        block = _block(block_ordinal)
        k1_ordinal = block_ordinal * 10 + 1
        k2_ordinal = block_ordinal * 10 + 2
        k1 = _sentinelized_root(block.k1, ordinal=k1_ordinal)
        k2 = _sentinelized_root(block.k2, ordinal=k2_ordinal)
        shared_cases = k1.expectation.case_refs
        shared_seed = k1.expectation.seeds
        k2_summary = deepcopy(k2.summary)
        k2_summary["steps"][0]["protocol_result"]["case_ids"] = list(shared_cases)
        k2_summary["steps"][0]["protocol_result"]["seed_set"] = list(shared_seed)
        k2 = _replace_root(
            k2,
            summary=k2_summary,
            expectation=replace(
                k2.expectation,
                case_refs=shared_cases,
                seeds=shared_seed,
            ),
        )
        private_blocks.append(replace(block, k1=k1, k2=k2))
        forbidden.extend(
            [
                "CAMPAIGN_PRIVATE_SENTINEL",
                "CASE_PATH_PRIVATE_SENTINEL",
                "H_PRIVATE_SENTINEL",
                "PATCH_PATH_PRIVATE_SENTINEL",
                "PATCH_SOURCE_PRIVATE_SENTINEL",
                str(shared_seed[0]),
                str(987_654_300 + k1_ordinal),
            ]
        )

    result = _compare_five_block_initial_screening_study_roots(
        blocks=tuple(private_blocks)
    )
    rendered = json.dumps(result, sort_keys=True)
    for sentinel in forbidden:
        assert sentinel not in rendered
    forbidden_keys = {
        "campaign_id",
        "case_id",
        "seed",
        "patch",
        "path",
        "source",
        "hash",
        "digest",
        "go",
        "advance",
    }

    def assert_safe_keys(value: Any) -> None:
        if isinstance(value, dict):
            assert not (set(value) & forbidden_keys)
            for nested in value.values():
                assert_safe_keys(nested)
        elif isinstance(value, list):
            for nested in value:
                assert_safe_keys(nested)

    assert_safe_keys(result)


def test_s2_input_and_output_are_detached_in_both_directions() -> None:
    root = _study_root()
    status_before = deepcopy(root.status)
    summary_before = deepcopy(root.summary)
    result = _score(root)

    result["physical"]["a_used"] = 999
    result["adjusted"]["e"] = {"status": "MUTATED", "value": 999}
    assert root.status == status_before
    assert root.summary == summary_before

    detached = _score(root)
    detached_before = deepcopy(detached)
    assert isinstance(root.status, dict)
    assert isinstance(root.summary, dict)
    root.status["campaign_id"] = "MUTATED_INPUT"
    root.summary["steps"][0]["protocol_result"]["paired_effect_cells"]["cells"][0][
        "candidate_value"
    ] = 0
    assert detached == detached_before
