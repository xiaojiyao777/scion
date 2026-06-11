from __future__ import annotations

from scion.core.models import ExperimentStage
from scion.core.runtime_budget_diagnostics import (
    BOTH_RUNTIME_BUDGET_SATURATION,
    CANDIDATE_RUNTIME_BUDGET_SATURATION,
    CHAMPION_RUNTIME_BUDGET_SATURATION,
    TINY_RUNTIME_BUDGET_SATURATION,
    format_runtime_budget_diagnostic,
    runtime_budget_candidate_saturation_detected,
    runtime_budget_diagnostic,
    runtime_budget_diagnostic_code,
    runtime_budget_summary_reason_codes,
)


def test_tiny_runtime_saturation_returns_repairable_budget_diagnostic() -> None:
    diagnostic = runtime_budget_diagnostic(
        stage=ExperimentStage.SCREENING,
        time_limit_sec=30,
        candidate_elapsed_ms=(24100, 23800, 24500),
        champion_elapsed_ms=(900, 920, 910),
        total_pairs=3,
    )

    assert diagnostic is not None
    assert diagnostic["code"] == TINY_RUNTIME_BUDGET_SATURATION
    assert diagnostic["repairable"] is True
    assert diagnostic["saturated_side"] == "candidate"
    assert diagnostic["reason_codes"] == [CANDIDATE_RUNTIME_BUDGET_SATURATION]
    assert diagnostic["candidate"]["max_budget_ratio"] == 0.8167
    assert "candidate side" in diagnostic["guidance"]
    rendered = format_runtime_budget_diagnostic(diagnostic)
    assert "runtime_budget_diagnostic=TINY_RUNTIME_BUDGET_SATURATION" in rendered
    assert "candidate_budget_ratio=0.8167" in rendered
    assert "saturated_side=candidate" in rendered
    assert runtime_budget_summary_reason_codes(diagnostic) == (
        TINY_RUNTIME_BUDGET_SATURATION,
        CANDIDATE_RUNTIME_BUDGET_SATURATION,
    )


def test_comfortably_bounded_screening_runtime_has_no_diagnostic() -> None:
    diagnostic = runtime_budget_diagnostic(
        stage=ExperimentStage.SCREENING,
        time_limit_sec=30,
        candidate_elapsed_ms=(5000, 6000, 7000, 8000),
        champion_elapsed_ms=(4000, 4100, 4200, 4300),
        total_pairs=4,
    )

    assert diagnostic is None


def test_champion_only_runtime_saturation_is_not_candidate_repair() -> None:
    diagnostic = runtime_budget_diagnostic(
        stage=ExperimentStage.SCREENING,
        time_limit_sec=30,
        candidate_elapsed_ms=(900, 920, 910),
        champion_elapsed_ms=(24100, 23800, 24500),
        total_pairs=3,
    )

    assert diagnostic is not None
    assert diagnostic["code"] == TINY_RUNTIME_BUDGET_SATURATION
    assert diagnostic["repairable"] is False
    assert diagnostic["saturated_side"] == "champion"
    assert diagnostic["reason_codes"] == [CHAMPION_RUNTIME_BUDGET_SATURATION]
    assert "do not direct candidate repair" in diagnostic["guidance"]
    assert runtime_budget_summary_reason_codes(diagnostic) == (
        CHAMPION_RUNTIME_BUDGET_SATURATION,
    )
    protocol_result = type(
        "ProtocolResult",
        (),
        {
            "candidate_surface_runtime_summary": {
                "runtime_budget_diagnostic": diagnostic
            }
        },
    )()
    assert runtime_budget_diagnostic_code(protocol_result) == ""


def test_both_sides_runtime_saturation_is_distinct() -> None:
    diagnostic = runtime_budget_diagnostic(
        stage=ExperimentStage.SCREENING,
        time_limit_sec=30,
        candidate_elapsed_ms=(24100, 23800, 24500),
        champion_elapsed_ms=(24200, 23900, 24600),
        total_pairs=3,
    )

    assert diagnostic is not None
    assert diagnostic["repairable"] is True
    assert diagnostic["saturated_side"] == "both"
    assert diagnostic["reason_codes"] == [BOTH_RUNTIME_BUDGET_SATURATION]
    assert runtime_budget_summary_reason_codes(diagnostic) == (
        TINY_RUNTIME_BUDGET_SATURATION,
        BOTH_RUNTIME_BUDGET_SATURATION,
    )


def test_budget_exhausting_runtime_saturation_is_observational() -> None:
    diagnostic = runtime_budget_diagnostic(
        stage=ExperimentStage.SCREENING,
        runtime_model="budget_exhausting",
        time_limit_sec=30,
        candidate_elapsed_ms=(29100, 29800, 29500),
        champion_elapsed_ms=(900, 920, 910),
        total_pairs=3,
    )

    assert diagnostic is not None
    assert diagnostic["code"] == TINY_RUNTIME_BUDGET_SATURATION
    assert diagnostic["runtime_model"] == "budget_exhausting"
    assert diagnostic["severity"] == "info"
    assert diagnostic["repairable"] is False
    assert diagnostic["reason_codes"] == []
    assert format_runtime_budget_diagnostic(diagnostic) == ""
    assert runtime_budget_summary_reason_codes(diagnostic) == ()
    protocol_result = type(
        "ProtocolResult",
        (),
        {
            "candidate_surface_runtime_summary": {
                "runtime_budget_diagnostic": diagnostic
            }
        },
    )()
    assert runtime_budget_diagnostic_code(protocol_result) == ""
    assert runtime_budget_candidate_saturation_detected(protocol_result) is False
