from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Literal, cast

import pytest

from scion.core.evidence_recording import EvidenceRecorder
from scion.core.models import (
    CanaryResult,
    Decision,
    ExperimentStage,
    PairwiseCaseFeedback,
    ProtocolResult,
)
from scion.problem.objectives import MetricComparison, ObjectiveComparison
from scion.proposal.context_manager.manager import screening_record

from .evidence_recorder_test_support import (
    _branch,
    _champion,
    _hypothesis,
    _operator_state,
    _patch,
    _run_projection,
    _step,
)


def _objective(
    comparison: Literal["win", "loss", "tie"],
    *,
    candidate_value: float,
    reference_value: float,
) -> ObjectiveComparison:
    return ObjectiveComparison(
        outcome=comparison,
        decisive_metric="total_distance",
        scalar_delta=float(reference_value) - float(candidate_value),
        metrics=(
            MetricComparison(
                name="total_distance",
                candidate_value=candidate_value,
                champion_value=reference_value,
                signed_delta=float(reference_value) - float(candidate_value),
                relation="candidate",
                decisive=True,
            ),
        ),
    )


def _complete_protocol() -> ProtocolResult:
    step = _step()
    feedback = tuple(
        PairwiseCaseFeedback(
            case_id=case_id,
            seed=seed,
            comparison="win",
            delta=float(reference) - float(candidate),
            objective_comparison=_objective(
                "win",
                candidate_value=candidate,
                reference_value=reference,
            ),
        )
        for case_id, seed, candidate, reference in (
            ("alpha.vrp", 11, 90, 100),
            ("alpha.vrp", 29, 91.5, 101.5),
            ("beta.vrp", 11, 190, 200),
            ("beta.vrp", 29, 191.5, 201.5),
        )
    )
    return replace(
        step.protocol_result,
        case_ids=("private/a/alpha.vrp", "private/b/beta.vrp"),
        seed_set=(11, 29),
        pair_feedback=feedback,
        case_aggregation_method="paired_effect_median",
        case_effect_metric="total_distance",
        stats=replace(
            step.protocol_result.stats,
            n_cases=2,
            wins=2,
            losses=0,
            ties=0,
            total_pairs=4,
            attempted_pairs=4,
            valid_pairs=4,
            failed_pairs=0,
            candidate_failed_pairs=0,
            champion_failed_pairs=0,
            shared_failed_pairs=0,
            bilateral_failed_pairs=0,
            pair_wins=4,
            pair_losses=0,
            pair_ties=0,
        ),
    )


def _summary(tmp_path: Path, protocol_result: ProtocolResult) -> dict[str, Any]:
    recorder = EvidenceRecorder(campaign_id="camp-1", campaign_dir=tmp_path)
    step = _step()
    step.protocol_result = protocol_result
    return recorder.write_campaign_summary(
        state=_operator_state(n_steps=1),
        run_result=_run_projection(),
        step_history=[step],
    )


def _protocol_payload(
    tmp_path: Path, protocol_result: ProtocolResult
) -> dict[str, Any]:
    return _summary(tmp_path, protocol_result)["steps"][0]["protocol_result"]


def _assert_omitted(tmp_path: Path, protocol_result: ProtocolResult) -> None:
    protocol = _protocol_payload(tmp_path, protocol_result)
    assert "paired_effect_cells" not in protocol
    written = json.loads(
        (tmp_path / "campaign_summary.json").read_text(encoding="utf-8")
    )
    assert "paired_effect_cells" not in written["steps"][0]["protocol_result"]


def _replace_feedback(
    protocol: ProtocolResult,
    index: int,
    feedback: PairwiseCaseFeedback,
) -> ProtocolResult:
    items = list(protocol.pair_feedback)
    items[index] = feedback
    return replace(protocol, pair_feedback=tuple(items))


def _replace_first_objective(
    protocol: ProtocolResult,
    objective: Any,
) -> ProtocolResult:
    feedback = replace(protocol.pair_feedback[0], objective_comparison=objective)
    return _replace_feedback(protocol, 0, feedback)


def _replace_first_metric(
    protocol: ProtocolResult,
    metric: Any,
    *,
    decisive_metric: Any = "total_distance",
    outcome: Any = "win",
) -> ProtocolResult:
    comparison = cast(
        ObjectiveComparison, protocol.pair_feedback[0].objective_comparison
    )
    objective = replace(
        comparison,
        outcome=outcome,
        decisive_metric=decisive_metric,
        metrics=(metric,),
    )
    return _replace_first_objective(protocol, objective)


@dataclass(frozen=True)
class _LookalikeObjectiveComparison:
    outcome: str
    decisive_metric: str | None
    scalar_delta: float
    metrics: tuple[Any, ...]


@dataclass(frozen=True)
class _LookalikeMetricComparison:
    name: str
    candidate_value: int | float
    champion_value: int | float
    signed_delta: float
    relation: str
    decisive: bool


def test_complete_screening_projects_identity_free_paired_effect_cells(
    tmp_path: Path,
) -> None:
    summary = _summary(tmp_path, _complete_protocol())

    payload = summary["steps"][0]["protocol_result"]["paired_effect_cells"]  # type: ignore[index]
    assert payload == {
        "schema_version": "scion.paired_effect_cells.v1",
        "metric_name": "total_distance",
        "cells": [
            {"candidate_value": 90, "reference_value": 100},
            {"candidate_value": 91.5, "reference_value": 101.5},
            {"candidate_value": 190, "reference_value": 200},
            {"candidate_value": 191.5, "reference_value": 201.5},
        ],
    }
    assert set(payload) == {"schema_version", "metric_name", "cells"}
    assert all(
        set(cell) == {"candidate_value", "reference_value"} for cell in payload["cells"]
    )
    rendered = json.dumps(payload, sort_keys=True)
    for forbidden in (
        "alpha",
        "beta",
        "private",
        "case_id",
        "seed",
        "path",
        "hypothesis",
        "patch",
        "delta",
        "champion",
        "initial",
        "b0",
    ):
        assert forbidden not in rendered.lower()


@pytest.mark.parametrize("gate_outcome", ("pass", "expand", "fail"))
def test_every_complete_screening_shape_projects_the_generic_cells_field(
    tmp_path: Path,
    gate_outcome: str,
) -> None:
    protocol = replace(
        _complete_protocol(),
        gate_outcome=cast(Any, gate_outcome),
    )

    assert "paired_effect_cells" in _protocol_payload(tmp_path, protocol)


@pytest.mark.parametrize(
    "mutation",
    (
        "non_screening",
        "wrong_aggregation",
        "empty_cases",
        "empty_seeds",
        "empty_feedback",
        "non_tuple_cases",
        "non_tuple_seeds",
        "non_tuple_feedback",
        "duplicate_basename",
        "duplicate_seed",
        "bool_seed",
        "missing_pair",
        "extra_pair",
        "reversed_pairs",
        "duplicate_pair",
        "feedback_bool_seed",
        "feedback_case_mismatch",
    ),
)
def test_noncanonical_screening_matrix_omits_entire_field(
    tmp_path: Path,
    mutation: str,
) -> None:
    protocol = _complete_protocol()
    feedback = protocol.pair_feedback
    if mutation == "non_screening":
        protocol = replace(protocol, stage=ExperimentStage.VALIDATION)
    elif mutation == "wrong_aggregation":
        protocol = replace(protocol, case_aggregation_method="seed_vote_majority")
    elif mutation == "empty_cases":
        protocol = replace(protocol, case_ids=())
    elif mutation == "empty_seeds":
        protocol = replace(protocol, seed_set=())
    elif mutation == "empty_feedback":
        protocol = replace(protocol, pair_feedback=())
    elif mutation == "non_tuple_cases":
        protocol = replace(protocol, case_ids=cast(Any, list(protocol.case_ids)))
    elif mutation == "non_tuple_seeds":
        protocol = replace(protocol, seed_set=cast(Any, list(protocol.seed_set)))
    elif mutation == "non_tuple_feedback":
        protocol = replace(protocol, pair_feedback=cast(Any, list(feedback)))
    elif mutation == "duplicate_basename":
        protocol = replace(
            protocol,
            case_ids=("private/a/alpha.vrp", "other/alpha.vrp"),
        )
    elif mutation == "duplicate_seed":
        protocol = replace(protocol, seed_set=(11, 11))
    elif mutation == "bool_seed":
        protocol = replace(protocol, seed_set=cast(Any, (True, 29)))
    elif mutation == "missing_pair":
        protocol = replace(protocol, pair_feedback=feedback[:-1])
    elif mutation == "extra_pair":
        protocol = replace(protocol, pair_feedback=(*feedback, feedback[-1]))
    elif mutation == "reversed_pairs":
        protocol = replace(protocol, pair_feedback=tuple(reversed(feedback)))
    elif mutation == "duplicate_pair":
        protocol = replace(
            protocol,
            pair_feedback=(feedback[0], feedback[0], *feedback[2:]),
        )
    elif mutation == "feedback_bool_seed":
        protocol = _replace_feedback(
            protocol,
            0,
            replace(feedback[0], seed=cast(Any, True)),
        )
    elif mutation == "feedback_case_mismatch":
        protocol = _replace_feedback(
            protocol,
            0,
            replace(feedback[0], case_id="gamma.vrp"),
        )
    else:  # pragma: no cover - parametrization is closed above
        raise AssertionError(mutation)

    _assert_omitted(tmp_path, protocol)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("n_cases", 3),
        ("n_cases", True),
        ("wins", -1),
        ("losses", 1),
        ("ties", True),
        ("total_pairs", 3),
        ("attempted_pairs", 3),
        ("valid_pairs", 3),
        ("failed_pairs", 1),
        ("candidate_failed_pairs", 1),
        ("champion_failed_pairs", 1),
        ("shared_failed_pairs", 1),
        ("bilateral_failed_pairs", 1),
        ("pair_wins", 3),
        ("pair_losses", 1),
        ("pair_ties", 1),
        ("pair_wins", True),
    ),
)
def test_noncanonical_complete_stats_omit_entire_field(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    protocol = _complete_protocol()
    stats = replace(protocol.stats, **{field: value})

    _assert_omitted(tmp_path, replace(protocol, stats=stats))


@pytest.mark.parametrize(
    "metric_name",
    (
        "",
        " total_distance",
        "total distance",
        "1total_distance",
        "total/distance",
        "a" * 129,
    ),
)
def test_noncanonical_metric_name_omits_entire_field(
    tmp_path: Path,
    metric_name: str,
) -> None:
    _assert_omitted(
        tmp_path,
        replace(_complete_protocol(), case_effect_metric=metric_name),
    )


@pytest.mark.parametrize(
    "mutation",
    (
        "feedback_comparison_unknown",
        "feedback_delta_bool",
        "feedback_delta_nan",
        "feedback_delta_mismatch",
        "objective_outcome_mismatch",
        "objective_decisive_metric_type",
        "objective_scalar_bool",
        "objective_scalar_nan",
        "objective_lookalike",
        "metrics_not_tuple",
        "metric_missing",
        "metric_duplicate",
        "metric_lookalike",
        "nonselected_metric_invalid_name",
        "nonselected_metric_nonfinite",
        "candidate_bool",
        "candidate_nan",
        "candidate_inf",
        "candidate_overflow",
        "reference_bool",
        "reference_nan",
        "reference_inf",
        "reference_overflow",
        "signed_delta_bool",
        "signed_delta_nan",
        "signed_delta_mismatch",
        "relation_unknown",
        "candidate_relation_negative",
        "champion_relation_positive",
        "decisive_not_bool",
        "decisive_flag_mismatch",
        "decisive_wrong_name",
        "multiple_decisive",
        "decisive_tie",
        "decisive_candidate_loss",
        "decisive_champion_win",
    ),
)
def test_noncanonical_objective_evidence_omits_entire_field(
    tmp_path: Path,
    mutation: str,
) -> None:
    protocol = _complete_protocol()
    comparison = cast(
        ObjectiveComparison,
        protocol.pair_feedback[0].objective_comparison,
    )
    metric = comparison.metrics[0]
    if mutation == "feedback_comparison_unknown":
        protocol = _replace_feedback(
            protocol,
            0,
            replace(protocol.pair_feedback[0], comparison=cast(Any, "future")),
        )
    elif mutation == "feedback_delta_bool":
        protocol = _replace_feedback(
            protocol,
            0,
            replace(protocol.pair_feedback[0], delta=cast(Any, True)),
        )
    elif mutation == "feedback_delta_nan":
        protocol = _replace_feedback(
            protocol,
            0,
            replace(protocol.pair_feedback[0], delta=float("nan")),
        )
    elif mutation == "feedback_delta_mismatch":
        protocol = _replace_feedback(
            protocol,
            0,
            replace(protocol.pair_feedback[0], delta=11.0),
        )
    elif mutation == "objective_outcome_mismatch":
        protocol = _replace_first_objective(
            protocol,
            replace(comparison, outcome="loss"),
        )
    elif mutation == "objective_decisive_metric_type":
        protocol = _replace_first_objective(
            protocol,
            replace(comparison, decisive_metric=cast(Any, 1)),
        )
    elif mutation == "objective_scalar_bool":
        protocol = _replace_first_objective(
            protocol,
            replace(comparison, scalar_delta=cast(Any, True)),
        )
    elif mutation == "objective_scalar_nan":
        protocol = _replace_first_objective(
            protocol,
            replace(comparison, scalar_delta=float("nan")),
        )
    elif mutation == "objective_lookalike":
        protocol = _replace_first_objective(
            protocol,
            _LookalikeObjectiveComparison(
                outcome="win",
                decisive_metric="total_distance",
                scalar_delta=10.0,
                metrics=(metric,),
            ),
        )
    elif mutation == "metrics_not_tuple":
        protocol = _replace_first_objective(
            protocol,
            replace(comparison, metrics=cast(Any, [metric])),
        )
    elif mutation == "metric_missing":
        protocol = _replace_first_metric(
            protocol,
            replace(metric, name="fleet_violation"),
        )
    elif mutation == "metric_duplicate":
        protocol = _replace_first_objective(
            protocol,
            replace(comparison, metrics=(metric, metric)),
        )
    elif mutation == "metric_lookalike":
        protocol = _replace_first_metric(
            protocol,
            _LookalikeMetricComparison(
                name="total_distance",
                candidate_value=90,
                champion_value=100,
                signed_delta=10.0,
                relation="candidate",
                decisive=True,
            ),
        )
    elif mutation == "nonselected_metric_invalid_name":
        protocol = _replace_first_objective(
            protocol,
            replace(
                comparison,
                metrics=(
                    metric,
                    replace(metric, name="fleet violation", decisive=False),
                ),
            ),
        )
    elif mutation == "nonselected_metric_nonfinite":
        protocol = _replace_first_objective(
            protocol,
            replace(
                comparison,
                metrics=(
                    metric,
                    replace(
                        metric,
                        name="fleet_violation",
                        candidate_value=float("inf"),
                        decisive=False,
                    ),
                ),
            ),
        )
    elif mutation == "candidate_bool":
        protocol = _replace_first_metric(
            protocol,
            replace(metric, candidate_value=cast(Any, True)),
        )
    elif mutation == "candidate_nan":
        protocol = _replace_first_metric(
            protocol,
            replace(metric, candidate_value=float("nan")),
        )
    elif mutation == "candidate_inf":
        protocol = _replace_first_metric(
            protocol,
            replace(metric, candidate_value=float("inf")),
        )
    elif mutation == "candidate_overflow":
        protocol = _replace_first_metric(
            protocol,
            replace(metric, candidate_value=10**1000),
        )
    elif mutation == "reference_bool":
        protocol = _replace_first_metric(
            protocol,
            replace(metric, champion_value=cast(Any, False)),
        )
    elif mutation == "reference_nan":
        protocol = _replace_first_metric(
            protocol,
            replace(metric, champion_value=float("nan")),
        )
    elif mutation == "reference_inf":
        protocol = _replace_first_metric(
            protocol,
            replace(metric, champion_value=float("-inf")),
        )
    elif mutation == "reference_overflow":
        protocol = _replace_first_metric(
            protocol,
            replace(metric, champion_value=10**1000),
        )
    elif mutation == "signed_delta_bool":
        protocol = _replace_first_metric(
            protocol,
            replace(metric, signed_delta=cast(Any, True)),
        )
    elif mutation == "signed_delta_nan":
        protocol = _replace_first_metric(
            protocol,
            replace(metric, signed_delta=float("nan")),
        )
    elif mutation == "signed_delta_mismatch":
        protocol = _replace_first_metric(
            protocol,
            replace(metric, signed_delta=11.0),
        )
    elif mutation == "relation_unknown":
        protocol = _replace_first_metric(
            protocol,
            replace(metric, relation=cast(Any, "future")),
        )
    elif mutation == "candidate_relation_negative":
        protocol = _replace_first_metric(
            protocol,
            replace(metric, signed_delta=-10.0),
        )
    elif mutation == "champion_relation_positive":
        protocol = _replace_first_metric(
            protocol,
            replace(metric, relation="champion"),
        )
    elif mutation == "decisive_not_bool":
        protocol = _replace_first_metric(
            protocol,
            replace(metric, decisive=cast(Any, 1)),
        )
    elif mutation == "decisive_flag_mismatch":
        protocol = _replace_first_metric(
            protocol,
            replace(metric, decisive=False),
        )
    elif mutation == "decisive_wrong_name":
        protocol = _replace_first_metric(
            protocol,
            metric,
            decisive_metric="fleet_violation",
        )
    elif mutation == "multiple_decisive":
        protocol = _replace_first_objective(
            protocol,
            replace(
                comparison,
                metrics=(
                    metric,
                    replace(
                        metric,
                        name="fleet_violation",
                        candidate_value=0,
                        champion_value=1,
                        signed_delta=1.0,
                    ),
                ),
            ),
        )
    elif mutation == "decisive_tie":
        protocol = _replace_first_metric(
            protocol,
            replace(metric, relation="tie"),
            outcome="tie",
        )
        protocol = _replace_feedback(
            protocol,
            0,
            replace(protocol.pair_feedback[0], comparison="tie"),
        )
        protocol = replace(
            protocol,
            stats=replace(protocol.stats, pair_wins=3, pair_ties=1),
        )
    elif mutation == "decisive_candidate_loss":
        protocol = _replace_first_metric(protocol, metric, outcome="loss")
        protocol = _replace_feedback(
            protocol,
            0,
            replace(protocol.pair_feedback[0], comparison="loss"),
        )
        protocol = replace(
            protocol,
            stats=replace(protocol.stats, pair_wins=3, pair_losses=1),
        )
    elif mutation == "decisive_champion_win":
        protocol = _replace_first_metric(
            protocol,
            replace(metric, relation="champion", signed_delta=-10.0),
        )
    else:  # pragma: no cover - parametrization is closed above
        raise AssertionError(mutation)

    _assert_omitted(tmp_path, protocol)


def test_nondiagnostic_selected_metric_and_nonpositive_reference_remain_observed(
    tmp_path: Path,
) -> None:
    protocol = _complete_protocol()
    metric = cast(
        ObjectiveComparison,
        protocol.pair_feedback[0].objective_comparison,
    ).metrics[0]
    selected_metric = replace(
        metric,
        champion_value=0,
        signed_delta=-90.0,
        relation="tie",
        decisive=False,
    )
    decisive_metric = MetricComparison(
        name="fleet_violation",
        candidate_value=0,
        champion_value=1,
        signed_delta=1.0,
        relation="candidate",
        decisive=True,
    )
    comparison = cast(
        ObjectiveComparison,
        protocol.pair_feedback[0].objective_comparison,
    )
    protocol = _replace_first_objective(
        protocol,
        replace(
            comparison,
            scalar_delta=-89.0,
            decisive_metric="fleet_violation",
            metrics=(decisive_metric, selected_metric),
        ),
    )
    protocol = _replace_feedback(
        protocol,
        0,
        replace(protocol.pair_feedback[0], delta=-89.0),
    )

    cells = _protocol_payload(tmp_path, protocol)["paired_effect_cells"]["cells"]
    assert cells[0] == {"candidate_value": 90, "reference_value": 0}


def test_canonical_tie_with_nonzero_within_tolerance_delta_remains_observed(
    tmp_path: Path,
) -> None:
    protocol = _complete_protocol()
    comparison = cast(
        ObjectiveComparison,
        protocol.pair_feedback[0].objective_comparison,
    )
    metric = replace(comparison.metrics[0], relation="tie", decisive=False)
    protocol = _replace_first_objective(
        protocol,
        replace(
            comparison,
            outcome="tie",
            decisive_metric=None,
            metrics=(metric,),
        ),
    )
    protocol = _replace_feedback(
        protocol,
        0,
        replace(protocol.pair_feedback[0], comparison="tie", delta=10.0),
    )
    protocol = replace(
        protocol,
        stats=replace(protocol.stats, pair_wins=3, pair_ties=1),
    )

    assert "paired_effect_cells" in _protocol_payload(tmp_path, protocol)


def test_cells_field_is_not_added_to_other_existing_authority_surfaces(
    tmp_path: Path,
) -> None:
    recorder = EvidenceRecorder(
        campaign_id="camp-1",
        campaign_dir=tmp_path,
        problem_id="cvrp",
    )
    step = _step()
    step.protocol_result = _complete_protocol()
    history: list[Any] = []
    recorder.record_step(step, history)
    recorder.write_status(
        state=_operator_state(n_steps=1),
        run_result=_run_projection(),
    )
    summary = recorder.write_campaign_summary(
        state=_operator_state(n_steps=1),
        run_result=_run_projection(),
        step_history=history,
    )

    assert "paired_effect_cells" in summary["steps"][0]["protocol_result"]
    context_record = screening_record(step)
    lineage_event = recorder.build_step_lineage_event(
        branch=_branch(),
        code_hash="candidate-hash",
        hypothesis=_hypothesis(),
        patch=_patch(),
        contract_result=None,
        verification_result=None,
        canary_result=CanaryResult(passed=True),
        protocol_result=step.protocol_result,
        decision=Decision.QUEUE_VALIDATE,
        champion=_champion(),
        base_champion_version=1,
        base_source_ref="champion:v1",
        changed_files=("operators/local_search.py",),
    )
    history_text = (tmp_path / "research_history.jsonl").read_text(encoding="utf-8")
    status_text = (tmp_path / "status.json").read_text(encoding="utf-8")
    assert "paired_effect_cells" not in history_text
    assert "scion.paired_effect_cells.v1" not in history_text
    assert "paired_effect_cells" not in status_text
    assert "paired_effect_cells" not in json.dumps(context_record, sort_keys=True)
    assert "paired_effect_cells" not in json.dumps(lineage_event, sort_keys=True)
    assert step.decision is Decision.QUEUE_VALIDATE
    assert not list(tmp_path.glob("*.db"))
