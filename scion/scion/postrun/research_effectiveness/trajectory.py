"""Problem-neutral, provider- and solver-free research trajectory metrics.

Only ordinary in-memory campaign projections are consumed.  The output is a
collection of separate endpoints, never a Decision input, aggregate score, or
GO conclusion.
"""

from __future__ import annotations

import json
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, NoReturn

_REPORT_SCHEMA = "scion.research_trajectory.v1"
_COMPARISON_SCHEMA = "scion.research_trajectory.history_comparison.v1"
_STAGES = ("screening", "validation", "frozen")
_HELD_OUT = frozenset({"validation", "frozen"})
_DECISIONS = (
    "continue_explore",
    "expand_screening",
    "queue_validate",
    "expand_validation",
    "queue_frozen",
    "promote",
    "abandon",
)
_GATE_OUTCOMES = ("pass", "fail", "expand", "unclear")
_STATISTICAL_STATUSES = ("positive", "negative", "tie", "uncertain")
_PAIR_FIELDS = (
    "total_pairs",
    "attempted_pairs",
    "valid_pairs",
    "failed_pairs",
    "candidate_failed_pairs",
    "champion_failed_pairs",
    "shared_failed_pairs",
    "bilateral_failed_pairs",
)
_SCREENING_CASE_FIELDS = (
    "screening_case_wins",
    "screening_case_losses",
    "screening_case_ties",
    "screening_case_total",
)
_SCREENING_PAIR_FIELDS = (
    "screening_pair_wins",
    "screening_pair_losses",
    "screening_pair_ties",
    "screening_pair_total",
)
_CANDIDATE_FAILURE_CATEGORIES = (
    "timeout",
    "oom",
    "crash",
    "process_error",
    "invalid_output",
    "operator_error",
    "policy_error",
    "construction_error",
    "portfolio_error",
    "surface_contract_error",
    "other",
)
_EXECUTION_OUTCOMES = (
    "evaluated",
    "research_rejected",
    "not_evaluated",
    "blocked_infra",
    "resource_exhausted",
    "interrupted",
)
_PROTECTED_REGRESSION_CODES = {
    "screening": "SCREENING_FAIL_PROTECTED_OBJECTIVE_REGRESSION",
    "validation": "VALIDATION_FAIL_PROTECTED_OBJECTIVE_REGRESSION",
    "frozen": "FROZEN_FAIL_PROTECTED_OBJECTIVE_REGRESSION",
}
_FIXED_SCREENING_SLOTS = 2


class ResearchTrajectoryInputError(ValueError):
    """A consumed field in an ordinary postrun projection is malformed."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class _Step:
    round_num: int
    branch_id: str | None
    hypothesis: Mapping[str, Any] | None
    h_key: str | None
    selected_hypothesis_research_basis: Mapping[str, Any] | None
    contract: bool | None
    verification: bool | None
    stage: str | None
    protocol: Mapping[str, Any] | None
    decision: str | None
    held_out: bool


@dataclass(frozen=True)
class _HistoryRow:
    hypothesis: Mapping[str, Any] | None
    h_key: str | None
    patch_key: str | None


def calculate_research_trajectory(
    *,
    status: Mapping[str, Any],
    campaign_summary: Mapping[str, Any],
    research_history: Sequence[Mapping[str, Any]],
    hypothesis_research_traces: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Describe one campaign without external reads or runtime effects.

    Proposal-runtime attempt rounds are the preferred episode boundary.  A
    direct V3 run without that optional telemetry falls back to consecutive H
    episodes on each branch.  This prevents screening expansion and later
    scientific stages for one candidate from being counted as proposal replay.
    """

    status_map = _mapping(status, "STATUS_NOT_A_MAPPING")
    summary = _mapping(campaign_summary, "SUMMARY_NOT_A_MAPPING")
    steps = _steps(summary)
    history = _history_rows(
        _mapping_sequence(research_history, "RESEARCH_HISTORY_INVALID")
    )
    traces = _mapping_sequence(
        hypothesis_research_traces, "HYPOTHESIS_RESEARCH_TRACES_INVALID"
    )

    summary_runtime = _runtime(summary)
    status_runtime = _runtime(status_map)
    charged = (
        summary_runtime[0] if summary_runtime[0] is not None else status_runtime[0]
    )
    formal_h = (
        summary_runtime[1] if summary_runtime[1] is not None else status_runtime[1]
    )
    formal_rounds = (
        summary_runtime[2] if summary_runtime[1] is not None else status_runtime[2]
    )
    episodes, episode_source = _proposal_episodes(steps, formal_rounds)
    formal_source = "proposal_runtime"
    if formal_h is None:
        formal_h = len(episodes)
        formal_source = "summary_hypothesis_episodes"

    hypotheses, pair_observability = _hypothesis_metrics(history, steps, episodes)
    contract, verification = _gate_metrics(episodes)
    stage_reach, stage_reach_complete = _stage_reach(steps)
    decisions = {name: 0 for name in _DECISIONS}
    for step in steps:
        if step.decision is not None:
            decisions[step.decision] += 1
    maximum_depth, depth_complete = _maximum_depth(episodes)
    screening_quality = _screening_quality(steps)
    candidate_safety = _candidate_safety(steps)
    history_use, selected_basis_observability = _history_use(
        traces=traces,
        episodes=episodes,
    )
    campaign_outcome, campaign_outcome_source = _campaign_outcome(
        summary=summary,
        status=status_map,
    )

    return {
        "schema_version": _REPORT_SCHEMA,
        "metrics": {
            "provider_calls": {"charged": charged},
            "throughput": {
                "distinct_formal_h_per_charged_call": (
                    hypotheses["distinct"] / charged
                    if charged is not None and charged > 0
                    else None
                )
            },
            "hypotheses": {"formal": formal_h, **hypotheses},
            "contract": contract,
            "verification": verification,
            "stage_reach": stage_reach,
            "decision_counts": decisions,
            "promotions": decisions["promote"],
            "max_branch_depth": maximum_depth,
            "first_round": _first_rounds(steps),
            "history_use": history_use,
            "screening_quality": screening_quality,
            "candidate_safety": candidate_safety,
            "campaign_outcome": campaign_outcome,
        },
        "observability": {
            "charged_provider_calls": (
                "proposal_runtime" if charged is not None else "unavailable"
            ),
            "formal_h": formal_source,
            "hypothesis_endpoints": episode_source,
            "h_patch_endpoints": pair_observability,
            "branch_depth": "complete" if depth_complete else "partial",
            "stage_branch_reach": ("complete" if stage_reach_complete else "partial"),
            "screening_quality": "ordinary_campaign_summary",
            "candidate_safety": "ordinary_campaign_summary",
            "campaign_outcome": campaign_outcome_source,
            "selected_h_basis": selected_basis_observability,
        },
    }


def compare_history_trajectories(
    *, history_on: Mapping[str, Any], history_off: Mapping[str, Any]
) -> dict[str, Any]:
    """Compare history ON/OFF reports one numeric endpoint at a time."""

    on_metrics, on_observability = _report(history_on, "HISTORY_ON")
    off_metrics, off_observability = _report(history_off, "HISTORY_OFF")
    on = _flatten(on_metrics)
    off = _flatten(off_metrics)
    if set(on) != set(off):
        _fail("HISTORY_REPORT_ENDPOINT_MISMATCH")
    endpoints: dict[str, dict[str, int | float | None]] = {}
    for path in sorted(on):
        difference = None
        if on[path] is not None and off[path] is not None:
            difference = on[path] - off[path]
        endpoints[path] = {
            "history_on": on[path],
            "history_off": off[path],
            "difference_on_minus_off": difference,
        }
    return {
        "schema_version": _COMPARISON_SCHEMA,
        "endpoints": endpoints,
        "observability": {
            "history_on": on_observability,
            "history_off": off_observability,
        },
    }


def _steps(summary: Mapping[str, Any]) -> tuple[_Step, ...]:
    raw_steps = summary.get("steps")
    if not isinstance(raw_steps, list):
        _fail("SUMMARY_STEPS_INVALID")
    parsed: list[_Step] = []
    for raw in raw_steps:
        item = _mapping(raw, "SUMMARY_STEP_INVALID")
        round_num = _positive_int(item.get("round"), "SUMMARY_STEP_ROUND_INVALID")
        branch = item.get("branch_id")
        if branch is not None and (not isinstance(branch, str) or not branch.strip()):
            _fail("SUMMARY_STEP_BRANCH_INVALID")
        hypothesis = item.get("hypothesis")
        if hypothesis is not None:
            hypothesis = _mapping(hypothesis, "SUMMARY_HYPOTHESIS_INVALID")
            h_key = _json_key(hypothesis, "SUMMARY_HYPOTHESIS_INVALID")
        else:
            h_key = None
        raw_basis = item.get("selected_hypothesis_research_basis")
        selected_basis = None
        if raw_basis is not None:
            if hypothesis is None:
                _fail("SUMMARY_SELECTED_H_BASIS_WITHOUT_HYPOTHESIS")
            selected_basis = _mapping(
                raw_basis,
                "SUMMARY_SELECTED_H_BASIS_INVALID",
            )
        contract = _optional_bool(
            item.get("contract_passed"), "SUMMARY_CONTRACT_RESULT_INVALID"
        )
        verification = _optional_bool(
            item.get("verification_passed"),
            "SUMMARY_VERIFICATION_RESULT_INVALID",
        )
        raw_protocol = item.get("protocol_result")
        protocol = None
        stage = None
        if raw_protocol is not None:
            protocol = _mapping(raw_protocol, "SUMMARY_PROTOCOL_RESULT_INVALID")
            stage = protocol.get("stage")
            if stage not in _STAGES:
                _fail("SUMMARY_PROTOCOL_STAGE_INVALID")
        decision = item.get("decision")
        if decision is not None and decision not in _DECISIONS:
            _fail("SUMMARY_DECISION_INVALID")
        failure_stage = item.get("failure_stage")
        if failure_stage is not None and not isinstance(failure_stage, str):
            _fail("SUMMARY_FAILURE_STAGE_INVALID")
        execution_outcome = item.get("execution_outcome")
        outcome_stage = None
        if execution_outcome is not None:
            outcome = _mapping(execution_outcome, "SUMMARY_EXECUTION_OUTCOME_INVALID")
            provenance = _mapping(
                outcome.get("provenance"),
                "SUMMARY_EXECUTION_OUTCOME_PROVENANCE_INVALID",
            )
            outcome_stage = provenance.get("stage")
            if outcome_stage is not None and not isinstance(outcome_stage, str):
                _fail("SUMMARY_EXECUTION_OUTCOME_STAGE_INVALID")
        parsed.append(
            _Step(
                round_num=round_num,
                branch_id=branch.strip() if isinstance(branch, str) else None,
                hypothesis=hypothesis,
                h_key=h_key,
                selected_hypothesis_research_basis=selected_basis,
                contract=contract,
                verification=verification,
                stage=stage,
                protocol=protocol,
                decision=decision,
                held_out=(
                    stage in _HELD_OUT
                    or failure_stage in _HELD_OUT
                    or outcome_stage in _HELD_OUT
                ),
            )
        )
    return tuple(sorted(parsed, key=lambda step: step.round_num))


def _runtime(
    artifact: Mapping[str, Any],
) -> tuple[int | None, int | None, tuple[int, ...] | None]:
    raw_runtime = artifact.get("proposal_runtime")
    if raw_runtime is None:
        return None, None, None
    runtime = _mapping(raw_runtime, "PROPOSAL_RUNTIME_INVALID")
    provider = _mapping(
        runtime.get("provider_calls"), "PROPOSAL_PROVIDER_CALLS_INVALID"
    )
    charged = _nonnegative_int(
        provider.get("budget_admitted"), "PROPOSAL_PROVIDER_CHARGED_INVALID"
    )
    for field in ("cap", "remaining"):
        if field in provider:
            _nonnegative_int(provider[field], "PROPOSAL_PROVIDER_BUDGET_INVALID")
    if "by_request_kind" in provider:
        _count_mapping(provider["by_request_kind"], "PROPOSAL_PROVIDER_KINDS_INVALID")

    attempts = runtime.get("attempts")
    if attempts is None:
        return charged, None, None
    if not isinstance(attempts, list):
        _fail("PROPOSAL_ATTEMPTS_INVALID")
    formal = 0
    rounds: list[int] = []
    rounds_complete = True
    for raw_attempt in attempts:
        attempt = _mapping(raw_attempt, "PROPOSAL_ATTEMPT_INVALID")
        round_num = None
        if "round_num" in attempt:
            round_num = _positive_int(
                attempt["round_num"], "PROPOSAL_ATTEMPT_ROUND_INVALID"
            )
        else:
            rounds_complete = False
        if "provider_calls" in attempt:
            calls = _mapping(
                attempt["provider_calls"], "PROPOSAL_ATTEMPT_PROVIDER_CALLS_INVALID"
            )
            _nonnegative_int(
                calls.get("budget_admitted"),
                "PROPOSAL_ATTEMPT_PROVIDER_CHARGED_INVALID",
            )
            _count_mapping(
                calls.get("by_request_kind"),
                "PROPOSAL_ATTEMPT_PROVIDER_KINDS_INVALID",
            )
        exported = _nonnegative_int(
            attempt.get("hypotheses_exported"),
            "PROPOSAL_ATTEMPT_HYPOTHESES_INVALID",
        )
        formal += exported
        if exported and round_num is not None:
            rounds.append(round_num)
    return charged, formal, tuple(rounds) if rounds_complete else None


def _proposal_episodes(
    steps: tuple[_Step, ...], formal_rounds: tuple[int, ...] | None
) -> tuple[tuple[_Step, ...], str]:
    proposal_steps = tuple(
        step for step in steps if step.h_key is not None and not step.held_out
    )
    if formal_rounds is not None:
        rounds = set(formal_rounds)
        return (
            tuple(step for step in proposal_steps if step.round_num in rounds),
            "proposal_runtime_attempt_rounds",
        )

    episodes: list[_Step] = []
    previous_by_branch: dict[str, _Step] = {}
    unattributed_seen: set[str] = set()
    for step in proposal_steps:
        assert step.h_key is not None
        if step.branch_id is None:
            if step.h_key in unattributed_seen:
                continue
            unattributed_seen.add(step.h_key)
        else:
            previous = previous_by_branch.get(step.branch_id)
            previous_by_branch[step.branch_id] = step
            if (
                previous is not None
                and previous.h_key == step.h_key
                and previous.stage == step.stage == "screening"
                and previous.decision == "expand_screening"
            ):
                continue
        episodes.append(step)
    return tuple(episodes), "summary_hypothesis_episodes"


def _history_rows(
    history: tuple[Mapping[str, Any], ...],
) -> tuple[_HistoryRow, ...]:
    rows: list[_HistoryRow] = []
    for record in history:
        if "hypothesis" not in record or "patch" not in record:
            _fail("RESEARCH_HISTORY_RECORD_INVALID")
        hypothesis, patch = record["hypothesis"], record["patch"]
        if hypothesis is None:
            if patch is not None:
                _fail("RESEARCH_HISTORY_PATCH_WITHOUT_HYPOTHESIS")
            rows.append(_HistoryRow(None, None, None))
            continue
        hypothesis = _mapping(hypothesis, "RESEARCH_HISTORY_HYPOTHESIS_INVALID")
        h_key = _json_key(hypothesis, "RESEARCH_HISTORY_HYPOTHESIS_INVALID")
        patch_key = None
        if patch is not None:
            patch_key = _json_key(
                _mapping(patch, "RESEARCH_HISTORY_PATCH_INVALID"),
                "RESEARCH_HISTORY_PATCH_INVALID",
            )
        rows.append(_HistoryRow(hypothesis, h_key, patch_key))
    return tuple(rows)


def _aligned_history(
    history: tuple[_HistoryRow, ...], steps: tuple[_Step, ...]
) -> dict[int, _HistoryRow] | None:
    visible = tuple(step for step in steps if not step.held_out)
    if len(history) != len(visible):
        return None
    aligned: dict[int, _HistoryRow] = {}
    for step, row in zip(visible, history, strict=True):
        if (step.hypothesis is None) != (row.hypothesis is None):
            return None
        if (
            step.hypothesis is not None
            and row.hypothesis is not None
            and any(
                key not in row.hypothesis or row.hypothesis[key] != value
                for key, value in step.hypothesis.items()
            )
        ):
            return None
        aligned[step.round_num] = row
    return aligned


def _hypothesis_metrics(
    history: tuple[_HistoryRow, ...],
    steps: tuple[_Step, ...],
    episodes: tuple[_Step, ...],
) -> tuple[dict[str, int | None], str]:
    aligned = _aligned_history(history, steps)
    hypotheses: list[str] = []
    pairs: list[tuple[str, str]] = []
    for step in episodes:
        row = aligned.get(step.round_num) if aligned is not None else None
        h_key = row.h_key if row is not None and row.h_key is not None else step.h_key
        assert h_key is not None
        hypotheses.append(h_key)
        if row is not None and row.patch_key is not None:
            pairs.append((h_key, row.patch_key))
    distinct_h, distinct_pairs = len(set(hypotheses)), len(set(pairs))
    pair_available = aligned is not None
    return {
        "observed": len(hypotheses),
        "distinct": distinct_h,
        "replays": len(hypotheses) - distinct_h,
        "h_patch_observed": len(pairs) if pair_available else None,
        "distinct_h_patch": distinct_pairs if pair_available else None,
        "h_patch_replays": len(pairs) - distinct_pairs if pair_available else None,
    }, "summary_history_order_alignment" if pair_available else "unavailable"


def _gate_metrics(
    steps: tuple[_Step, ...],
) -> tuple[dict[str, int], dict[str, int]]:
    contract = [step.contract for step in steps if step.contract is not None]
    verification = [
        step.verification
        for step in steps
        if step.contract is True and step.verification is not None
    ]
    return _bool_counts(contract), _bool_counts(verification)


def _bool_counts(values: Sequence[bool]) -> dict[str, int]:
    return {
        "attempted": len(values),
        "passed": sum(value is True for value in values),
        "failed": sum(value is False for value in values),
    }


def _screening_quality(steps: tuple[_Step, ...]) -> dict[str, Any]:
    rows = tuple(
        step
        for step in steps
        if step.stage == "screening" and step.protocol is not None
    )
    gate_counts = {name: 0 for name in (*_GATE_OUTCOMES, "missing")}
    statistical_counts = {name: 0 for name in (*_STATISTICAL_STATUSES, "missing")}
    for step in rows:
        assert step.protocol is not None
        gate = step.protocol.get("gate_outcome")
        if gate is None:
            gate_counts["missing"] += 1
        elif gate in _GATE_OUTCOMES:
            gate_counts[str(gate)] += 1
        else:
            _fail("SUMMARY_SCREENING_GATE_OUTCOME_INVALID")
        statistical = step.protocol.get("statistical_status")
        if statistical is None:
            statistical_counts["missing"] += 1
        elif statistical in _STATISTICAL_STATUSES:
            statistical_counts[str(statistical)] += 1
        else:
            _fail("SUMMARY_SCREENING_STATISTICAL_STATUS_INVALID")

    sequence: dict[str, Any] = {
        "observed": len(rows),
        "beyond_fixed_slots": max(0, len(rows) - _FIXED_SCREENING_SLOTS),
    }
    for index in range(_FIXED_SCREENING_SLOTS):
        sequence[f"slot_{index + 1}"] = _screening_slot(
            rows[index] if index < len(rows) else None
        )

    return {
        "gate_counts": gate_counts,
        "statistical_counts": statistical_counts,
        "pair_counts": _screening_pair_counts(rows),
        "protected_regressions": _protected_regressions(steps),
        "opportunity_sequence": sequence,
    }


def _screening_slot(step: _Step | None) -> dict[str, Any]:
    if step is None:
        return {
            "round": None,
            "gate_outcome": {name: None for name in _GATE_OUTCOMES},
            "statistical_status": {name: None for name in _STATISTICAL_STATUSES},
            "median_delta": None,
            "ci_low": None,
            "ci_high": None,
            "case_wins": None,
            "case_losses": None,
            "case_ties": None,
            "case_total": None,
            "pair_wins": None,
            "pair_losses": None,
            "pair_ties": None,
            "pair_total": None,
            "protected_regression": None,
        }
    assert step.protocol is not None
    protocol = step.protocol
    reason_codes = _reason_codes(protocol)
    return {
        "round": step.round_num,
        "gate_outcome": _categorical_indicators(
            protocol.get("gate_outcome"),
            categories=_GATE_OUTCOMES,
            code="SUMMARY_SCREENING_GATE_OUTCOME_INVALID",
        ),
        "statistical_status": _categorical_indicators(
            protocol.get("statistical_status"),
            categories=_STATISTICAL_STATUSES,
            code="SUMMARY_SCREENING_STATISTICAL_STATUS_INVALID",
        ),
        "median_delta": _optional_finite_number(
            protocol.get("median_delta"), "SUMMARY_SCREENING_MEDIAN_INVALID"
        ),
        "ci_low": _optional_finite_number(
            protocol.get("ci_low"), "SUMMARY_SCREENING_CI_INVALID"
        ),
        "ci_high": _optional_finite_number(
            protocol.get("ci_high"), "SUMMARY_SCREENING_CI_INVALID"
        ),
        "case_wins": _optional_nonnegative_field(
            protocol, "screening_case_wins", "SUMMARY_SCREENING_WLT_INVALID"
        ),
        "case_losses": _optional_nonnegative_field(
            protocol, "screening_case_losses", "SUMMARY_SCREENING_WLT_INVALID"
        ),
        "case_ties": _optional_nonnegative_field(
            protocol, "screening_case_ties", "SUMMARY_SCREENING_WLT_INVALID"
        ),
        "case_total": _optional_nonnegative_field(
            protocol, "screening_case_total", "SUMMARY_SCREENING_WLT_INVALID"
        ),
        "pair_wins": _optional_nonnegative_field(
            protocol, "screening_pair_wins", "SUMMARY_SCREENING_WLT_INVALID"
        ),
        "pair_losses": _optional_nonnegative_field(
            protocol, "screening_pair_losses", "SUMMARY_SCREENING_WLT_INVALID"
        ),
        "pair_ties": _optional_nonnegative_field(
            protocol, "screening_pair_ties", "SUMMARY_SCREENING_WLT_INVALID"
        ),
        "pair_total": _optional_nonnegative_field(
            protocol, "screening_pair_total", "SUMMARY_SCREENING_WLT_INVALID"
        ),
        "protected_regression": (
            None
            if reason_codes is None
            else int(_PROTECTED_REGRESSION_CODES["screening"] in reason_codes)
        ),
    }


def _screening_pair_counts(rows: tuple[_Step, ...]) -> dict[str, int | None]:
    field_values: dict[str, list[int | None]] = {field: [] for field in _PAIR_FIELDS}
    accounting_complete = attribution_complete = 0
    accounting_observed = attribution_observed = 0
    case_wlt_complete = pair_wlt_complete = 0
    case_wlt_observed = pair_wlt_observed = 0
    for step in rows:
        assert step.protocol is not None
        protocol = step.protocol
        values = {
            field: _optional_nonnegative_field(
                protocol, field, "SUMMARY_SCREENING_PAIR_COUNT_INVALID"
            )
            for field in _PAIR_FIELDS
        }
        for field, value in values.items():
            field_values[field].append(value)
        core = tuple(
            values[field]
            for field in (
                "total_pairs",
                "attempted_pairs",
                "valid_pairs",
                "failed_pairs",
            )
        )
        if all(value is not None for value in core):
            total, attempted, valid, failed = core
            assert total is not None
            assert attempted is not None
            assert valid is not None
            assert failed is not None
            accounting_observed += 1
            accounting_complete += int(
                attempted <= total and attempted == valid + failed
            )
        attribution = tuple(values[field] for field in _PAIR_FIELDS[3:])
        if all(value is not None for value in attribution):
            failed, candidate, champion, shared, bilateral = attribution
            assert failed is not None
            assert candidate is not None
            assert champion is not None
            assert shared is not None
            assert bilateral is not None
            attribution_observed += 1
            attribution_complete += int(
                failed == candidate + champion - bilateral
                and shared <= champion
                and bilateral <= min(candidate, champion)
                and shared + bilateral <= champion
            )
        case_values = tuple(
            _optional_nonnegative_field(
                protocol, field, "SUMMARY_SCREENING_WLT_INVALID"
            )
            for field in _SCREENING_CASE_FIELDS
        )
        pair_values = tuple(
            _optional_nonnegative_field(
                protocol, field, "SUMMARY_SCREENING_WLT_INVALID"
            )
            for field in _SCREENING_PAIR_FIELDS
        )
        if all(value is not None for value in case_values):
            wins, losses, ties, total = case_values
            assert None not in case_values
            case_wlt_observed += 1
            case_wlt_complete += int(wins + losses + ties == total)
        if all(value is not None for value in pair_values):
            wins, losses, ties, total = pair_values
            assert None not in pair_values
            pair_wlt_observed += 1
            pair_wlt_complete += int(wins + losses + ties == total)
    return {
        "opportunities": len(rows),
        **{field: _sum_if_complete(values) for field, values in field_values.items()},
        "accounting_observed_opportunities": accounting_observed,
        "accounting_complete_opportunities": accounting_complete,
        "accounting_incomplete_opportunities": len(rows) - accounting_complete,
        "attribution_observed_opportunities": attribution_observed,
        "attribution_complete_opportunities": attribution_complete,
        "attribution_incomplete_opportunities": len(rows) - attribution_complete,
        "case_wlt_observed_opportunities": case_wlt_observed,
        "case_wlt_complete_opportunities": case_wlt_complete,
        "case_wlt_incomplete_opportunities": len(rows) - case_wlt_complete,
        "pair_wlt_observed_opportunities": pair_wlt_observed,
        "pair_wlt_complete_opportunities": pair_wlt_complete,
        "pair_wlt_incomplete_opportunities": len(rows) - pair_wlt_complete,
    }


def _protected_regressions(steps: tuple[_Step, ...]) -> dict[str, int]:
    counts = {stage: 0 for stage in _STAGES}
    observed = missing = 0
    for step in steps:
        if step.protocol is None or step.stage is None:
            continue
        reason_codes = _reason_codes(step.protocol)
        if reason_codes is None:
            missing += 1
            continue
        observed += 1
        counts[step.stage] += reason_codes.count(
            _PROTECTED_REGRESSION_CODES[step.stage]
        )
    return {
        **counts,
        "total": sum(counts.values()),
        "reason_codes_observed_opportunities": observed,
        "reason_codes_missing_opportunities": missing,
    }


def _candidate_safety(steps: tuple[_Step, ...]) -> dict[str, Any]:
    rows = tuple(step for step in steps if step.protocol is not None)
    category_totals = {name: 0 for name in _CANDIDATE_FAILURE_CATEGORIES}
    category_observed = 0
    attempted_values: list[int | None] = []
    timeout_values: list[int | None] = []
    invalid_output_values: list[int | None] = []
    infeasible_values: list[int | None] = []
    time_limit_values: list[int | None] = []
    for step in rows:
        assert step.protocol is not None
        protocol = step.protocol
        raw_categories = protocol.get("candidate_runtime_failure_categories")
        if raw_categories is not None:
            categories = _mapping(
                raw_categories, "SUMMARY_CANDIDATE_FAILURE_CATEGORIES_INVALID"
            )
            category_observed += 1
            for raw_name, raw_count in categories.items():
                if not isinstance(raw_name, str) or not raw_name.strip():
                    _fail("SUMMARY_CANDIDATE_FAILURE_CATEGORIES_INVALID")
                count = _nonnegative_int(
                    raw_count, "SUMMARY_CANDIDATE_FAILURE_CATEGORIES_INVALID"
                )
                normalized = raw_name.strip().lower().replace("-", "_")
                category = (
                    normalized
                    if normalized in category_totals and normalized != "other"
                    else "other"
                )
                category_totals[category] += count
        attempted = _optional_nonnegative_field(
            protocol,
            "attempted_pairs",
            "SUMMARY_CANDIDATE_SAFETY_ATTEMPTED_INVALID",
        )
        attempted_values.append(attempted)
        pair_fields = (
            (
                timeout_values,
                "candidate_only_timeout_pairs",
                "SUMMARY_CANDIDATE_TIMEOUT_PAIRS_INVALID",
            ),
            (
                invalid_output_values,
                "candidate_only_invalid_output_pairs",
                "SUMMARY_CANDIDATE_INVALID_OUTPUT_PAIRS_INVALID",
            ),
            (
                infeasible_values,
                "candidate_attributable_infeasible_pairs",
                "SUMMARY_CANDIDATE_INFEASIBLE_INVALID",
            ),
        )
        for values, field, code in pair_fields:
            count = _optional_nonnegative_field(protocol, field, code)
            if count is not None and attempted is not None and count > attempted:
                _fail(code)
            values.append(count)
        raw_stops = protocol.get("candidate_runtime_stop_reasons")
        if raw_stops is None:
            time_limit_values.append(None)
        else:
            stops = _mapping(raw_stops, "SUMMARY_CANDIDATE_STOP_REASONS_INVALID")
            time_limit = 0
            for raw_name, raw_count in stops.items():
                if not isinstance(raw_name, str) or not raw_name.strip():
                    _fail("SUMMARY_CANDIDATE_STOP_REASONS_INVALID")
                count = _nonnegative_int(
                    raw_count, "SUMMARY_CANDIDATE_STOP_REASONS_INVALID"
                )
                if raw_name.strip().lower().replace("-", "_") == "time_limit":
                    time_limit += count
            time_limit_values.append(time_limit)
    categories: dict[str, int | None] = {
        name: (count if category_observed == len(rows) and rows else None)
        for name, count in category_totals.items()
    }
    attempted_pairs = _sum_if_complete(attempted_values)
    timeout_pairs = _sum_if_complete(timeout_values)
    invalid_output_pairs = _sum_if_complete(invalid_output_values)
    infeasible_pairs = _sum_if_complete(infeasible_values)

    def pair_rate(numerator: int | None) -> float | None:
        if numerator is None or attempted_pairs is None or attempted_pairs <= 0:
            return None
        return numerator / attempted_pairs

    return {
        "protocol_opportunities": len(rows),
        "failure_category_observed_opportunities": category_observed,
        "failure_category_missing_opportunities": len(rows) - category_observed,
        "failure_categories": categories,
        "pair_rate_denominator_attempted_pairs": attempted_pairs,
        "candidate_only_timeout_pairs": timeout_pairs,
        "candidate_only_invalid_output_pairs": invalid_output_pairs,
        "candidate_only_infeasible_pairs": infeasible_pairs,
        "candidate_only_timeout_rate_per_attempted_pair": pair_rate(timeout_pairs),
        "candidate_only_invalid_output_rate_per_attempted_pair": pair_rate(
            invalid_output_pairs
        ),
        "candidate_only_infeasible_rate_per_attempted_pair": pair_rate(
            infeasible_pairs
        ),
        "pair_rate_completeness": {
            "opportunities": len(rows),
            "attempted_pairs_observed_opportunities": sum(
                value is not None for value in attempted_values
            ),
            "attempted_pairs_missing_opportunities": sum(
                value is None for value in attempted_values
            ),
            "timeout_observed_opportunities": sum(
                value is not None for value in timeout_values
            ),
            "timeout_missing_opportunities": sum(
                value is None for value in timeout_values
            ),
            "invalid_output_observed_opportunities": sum(
                value is not None for value in invalid_output_values
            ),
            "invalid_output_missing_opportunities": sum(
                value is None for value in invalid_output_values
            ),
            "infeasible_observed_opportunities": sum(
                value is not None for value in infeasible_values
            ),
            "infeasible_missing_opportunities": sum(
                value is None for value in infeasible_values
            ),
        },
        # A solver's normal deadline stop is not a failed process timeout.
        "normal_time_limit_stops": _sum_if_complete(time_limit_values),
        "stop_reason_observed_opportunities": sum(
            value is not None for value in time_limit_values
        ),
        "stop_reason_missing_opportunities": sum(
            value is None for value in time_limit_values
        ),
    }


def _campaign_outcome(
    *, summary: Mapping[str, Any], status: Mapping[str, Any]
) -> tuple[dict[str, Any], str]:
    source = "unavailable"
    raw_result = summary.get("run_result")
    if raw_result is not None:
        source = "campaign_summary.run_result"
    else:
        raw_result = status.get("run_result")
        if raw_result is not None:
            source = "status.run_result"
    if raw_result is None:
        missing = {name: None for name in _EXECUTION_OUTCOMES}
        return {
            "available": 0,
            "terminal_status": {
                "completed": None,
                "stopped": None,
                "running": None,
            },
            "requested_rounds": None,
            "evaluated_rounds": None,
            "scheduled_calls": None,
            "formal_screened_candidates": None,
            "protocol_stage_counts": {stage: None for stage in _STAGES},
            "execution_outcomes": missing,
            "typed_execution_outcomes": None,
            "unknown_execution_outcomes": None,
            "requested_rounds_complete": None,
            "outcome_accounting_complete": None,
            "run_valid": None,
        }, source

    result = _mapping(raw_result, "CAMPAIGN_RUN_RESULT_INVALID")
    status_value = result.get("status")
    if status_value not in {"completed", "stopped", "running"}:
        _fail("CAMPAIGN_RUN_STATUS_INVALID")
    requested = _positive_int(
        result.get("requested_rounds"), "CAMPAIGN_REQUESTED_ROUNDS_INVALID"
    )
    evaluated = _nonnegative_int(
        result.get("evaluated_rounds"), "CAMPAIGN_EVALUATED_ROUNDS_INVALID"
    )
    scheduled = _nonnegative_int(
        result.get("scheduled_calls"), "CAMPAIGN_SCHEDULED_CALLS_INVALID"
    )
    formal = _nonnegative_int(
        result.get("formal_screened_candidates"),
        "CAMPAIGN_FORMAL_SCREENED_INVALID",
    )
    raw_stage_counts = _mapping(
        result.get("protocol_stage_counts"), "CAMPAIGN_STAGE_COUNTS_INVALID"
    )
    stage_counts = {
        stage: _nonnegative_int(
            raw_stage_counts.get(stage), "CAMPAIGN_STAGE_COUNTS_INVALID"
        )
        for stage in _STAGES
    }
    raw_outcomes = _mapping(
        result.get("execution_outcome_counts"),
        "CAMPAIGN_EXECUTION_OUTCOMES_INVALID",
    )
    if set(raw_outcomes) != set(_EXECUTION_OUTCOMES):
        _fail("CAMPAIGN_EXECUTION_OUTCOMES_INVALID")
    outcomes = {
        name: _nonnegative_int(
            raw_outcomes[name], "CAMPAIGN_EXECUTION_OUTCOMES_INVALID"
        )
        for name in _EXECUTION_OUTCOMES
    }
    unknown = _nonnegative_int(
        result.get("unknown_outcome_count"),
        "CAMPAIGN_UNKNOWN_OUTCOMES_INVALID",
    )
    raw_validity = result.get("run_validity")
    run_valid = None
    if raw_validity is not None:
        validity = _mapping(raw_validity, "CAMPAIGN_RUN_VALIDITY_INVALID")
        value = validity.get("valid")
        if value is not None and type(value) is not bool:
            _fail("CAMPAIGN_RUN_VALIDITY_INVALID")
        run_valid = None if value is None else int(value)
    typed = sum(outcomes.values())
    return {
        "available": 1,
        "terminal_status": {
            name: int(status_value == name)
            for name in ("completed", "stopped", "running")
        },
        "requested_rounds": requested,
        "evaluated_rounds": evaluated,
        "scheduled_calls": scheduled,
        "formal_screened_candidates": formal,
        "protocol_stage_counts": stage_counts,
        "execution_outcomes": outcomes,
        "typed_execution_outcomes": typed,
        "unknown_execution_outcomes": unknown,
        "requested_rounds_complete": int(evaluated >= requested),
        "outcome_accounting_complete": int(scheduled == typed + unknown),
        "run_valid": run_valid,
    }, source


def _reason_codes(protocol: Mapping[str, Any]) -> tuple[str, ...] | None:
    raw = protocol.get("reason_codes")
    if raw is None:
        return None
    return _text_list(raw, "SUMMARY_PROTOCOL_REASON_CODES_INVALID")


def _optional_nonnegative_field(
    value: Mapping[str, Any], field: str, code: str
) -> int | None:
    raw = value.get(field)
    return None if raw is None else _nonnegative_int(raw, code)


def _optional_finite_number(value: Any, code: str) -> int | float | None:
    if value is None:
        return None
    if type(value) not in {int, float} or not math.isfinite(value):
        _fail(code)
    return value


def _categorical_indicators(
    value: Any,
    *,
    categories: Sequence[str],
    code: str,
) -> dict[str, int | None]:
    if value is None:
        return {name: None for name in categories}
    if value not in categories:
        _fail(code)
    return {name: int(value == name) for name in categories}


def _sum_if_complete(values: Sequence[int | None]) -> int | None:
    if not values or any(value is None for value in values):
        return None
    return sum(value for value in values if value is not None)


def _stage_reach(
    steps: tuple[_Step, ...],
) -> tuple[dict[str, dict[str, int | None]], bool]:
    result: dict[str, dict[str, int | None]] = {}
    complete = True
    for stage in _STAGES:
        rows = [step for step in steps if step.stage == stage]
        missing = any(step.branch_id is None for step in rows)
        complete = complete and not missing
        result[stage] = {
            "steps": len(rows),
            "branches": None if missing else len({step.branch_id for step in rows}),
        }
    return result, complete


def _maximum_depth(episodes: tuple[_Step, ...]) -> tuple[int | None, bool]:
    if any(step.branch_id is None for step in episodes):
        return None, False
    depths: dict[str, int] = {}
    for step in episodes:
        assert step.branch_id is not None
        depths[step.branch_id] = depths.get(step.branch_id, 0) + 1
    return max(depths.values(), default=0), True


def _first_rounds(steps: tuple[_Step, ...]) -> dict[str, int | None]:
    return {
        "hypothesis": _first(step for step in steps if step.hypothesis is not None),
        "contract": _first(step for step in steps if step.contract is not None),
        "verification": _first(
            step
            for step in steps
            if step.contract is True and step.verification is not None
        ),
        **{
            stage: _first(step for step in steps if step.stage == stage)
            for stage in _STAGES
        },
        "promotion": _first(step for step in steps if step.decision == "promote"),
    }


def _first(steps: Iterable[_Step]) -> int | None:
    return min((step.round_num for step in steps), default=None)


def _history_use(
    *,
    traces: tuple[Mapping[str, Any], ...],
    episodes: tuple[_Step, ...],
) -> tuple[dict[str, Any], str]:
    read_actions = search_actions = 0
    action_refs: list[str] = []
    for trace in traces:
        payload = _trace_payload(trace)
        if payload is None:
            continue
        action = payload.get("action")
        if action is not None and not isinstance(action, str):
            _fail("HYPOTHESIS_RESEARCH_ACTION_INVALID")
        if action == "read_history":
            read_actions += 1
            action_refs.append(
                _text(payload.get("ref"), "HYPOTHESIS_HISTORY_READ_REF_INVALID")
            )
        elif action == "search_history":
            search_actions += 1
            if "ref" in payload:
                action_refs.append(
                    _text(payload["ref"], "HYPOTHESIS_HISTORY_SEARCH_REF_INVALID")
                )
    basis_history_refs: list[str] = []
    citations: list[str] = []
    basis_observed = 0
    for step in episodes:
        basis = step.selected_hypothesis_research_basis
        if basis is None:
            continue
        basis_observed += 1
        read_refs = _text_list(
            basis.get("read_refs"), "SUMMARY_SELECTED_H_BASIS_READ_REFS_INVALID"
        )
        basis_citations = _text_list(
            basis.get("nearest_prior_refs"),
            "SUMMARY_SELECTED_H_BASIS_CITATIONS_INVALID",
        )
        if not set(basis_citations) <= set(read_refs) or any(
            not ref.startswith("history-") for ref in basis_citations
        ):
            _fail("SUMMARY_SELECTED_H_BASIS_CITATIONS_INVALID")
        citations.extend(basis_citations)
        basis_history_refs.extend(
            ref for ref in read_refs if ref.startswith("history-")
        )
    basis_complete = basis_observed == len(episodes)
    selected_basis_metrics: dict[str, int | None] = {
        "episodes": len(episodes),
        "basis_observed_episodes": basis_observed,
        "basis_missing_episodes": len(episodes) - basis_observed,
        "basis_history_read_references": (
            len(basis_history_refs) if basis_complete else None
        ),
        "distinct_basis_history_read_references": (
            len(set(basis_history_refs)) if basis_complete else None
        ),
        "citations": len(citations) if basis_complete else None,
        "distinct_citations": len(set(citations)) if basis_complete else None,
    }
    if not episodes:
        observability = "no_formal_h"
    else:
        observability = "complete" if basis_complete else "partial"
    return {
        "all_deliberation": {
            "read_actions": read_actions,
            "search_actions": search_actions,
            "action_reference_mentions": len(action_refs),
            "distinct_action_references": len(set(action_refs)),
        },
        "selected_h_basis": selected_basis_metrics,
    }, observability


def _trace_payload(trace: Mapping[str, Any]) -> Mapping[str, Any] | None:
    request_kind = trace.get("request_kind")
    if request_kind is None:
        return trace
    if not isinstance(request_kind, str):
        _fail("HYPOTHESIS_RESEARCH_TRACE_KIND_INVALID")
    if request_kind != "hypothesis_research_turn":
        return None
    ok = trace.get("ok")
    if ok is not None and type(ok) is not bool:
        _fail("HYPOTHESIS_RESEARCH_TRACE_OK_INVALID")
    if ok is False or trace.get("response") is None:
        return None
    return _mapping(trace["response"], "HYPOTHESIS_RESEARCH_TRACE_RESPONSE_INVALID")


def _report(
    value: Mapping[str, Any], label: str
) -> tuple[Mapping[str, Any], dict[str, Any]]:
    report = _mapping(value, f"{label}_REPORT_INVALID")
    if report.get("schema_version") != _REPORT_SCHEMA:
        _fail(f"{label}_REPORT_SCHEMA_INVALID")
    metrics = _mapping(report.get("metrics"), f"{label}_METRICS_INVALID")
    observability = _mapping(
        report.get("observability"), f"{label}_OBSERVABILITY_INVALID"
    )
    return metrics, dict(observability)


def _flatten(
    metrics: Mapping[str, Any], prefix: str = ""
) -> dict[str, int | float | None]:
    leaves: dict[str, int | float | None] = {}
    for key in sorted(metrics):
        if not isinstance(key, str) or not key:
            _fail("REPORT_METRIC_KEY_INVALID")
        path, value = (f"{prefix}.{key}" if prefix else key), metrics[key]
        if isinstance(value, Mapping):
            leaves.update(_flatten(value, path))
        elif value is None:
            leaves[path] = None
        elif type(value) in {int, float} and (
            type(value) is int or math.isfinite(value)
        ):
            leaves[path] = value
        else:
            _fail("REPORT_METRIC_VALUE_INVALID")
    return leaves


def _json_key(value: Mapping[str, Any], code: str) -> str:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError, OverflowError, RecursionError):
        _fail(code)


def _mapping_sequence(
    value: Sequence[Mapping[str, Any]], code: str
) -> tuple[Mapping[str, Any], ...]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        _fail(code)
    if any(not isinstance(item, Mapping) for item in value):
        _fail(code)
    return tuple(value)


def _count_mapping(value: Any, code: str) -> None:
    counts = _mapping(value, code)
    for count in counts.values():
        _nonnegative_int(count, code)


def _text_list(value: Any, code: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        _fail(code)
    return tuple(_text(item, code) for item in value)


def _mapping(value: Any, code: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _fail(code)
    return value


def _optional_bool(value: Any, code: str) -> bool | None:
    if value is not None and type(value) is not bool:
        _fail(code)
    return value


def _text(value: Any, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(code)
    return value


def _positive_int(value: Any, code: str) -> int:
    if type(value) is not int or value <= 0:
        _fail(code)
    return value


def _nonnegative_int(value: Any, code: str) -> int:
    if type(value) is not int or value < 0:
        _fail(code)
    return value


def _fail(code: str) -> NoReturn:
    raise ResearchTrajectoryInputError(code)


__all__ = [
    "ResearchTrajectoryInputError",
    "calculate_research_trajectory",
    "compare_history_trajectories",
]
