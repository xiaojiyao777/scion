from __future__ import annotations

from scion.core.models import ExperimentStage
from scion.core.runtime_budget_diagnostics import (
    TINY_RUNTIME_BUDGET_SATURATION,
    format_runtime_budget_diagnostic,
    runtime_budget_diagnostic,
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
    assert diagnostic["candidate"]["max_budget_ratio"] == 0.8167
    rendered = format_runtime_budget_diagnostic(diagnostic)
    assert "runtime_budget_diagnostic=TINY_RUNTIME_BUDGET_SATURATION" in rendered
    assert "candidate_budget_ratio=0.8167" in rendered


def test_comfortably_bounded_screening_runtime_has_no_diagnostic() -> None:
    diagnostic = runtime_budget_diagnostic(
        stage=ExperimentStage.SCREENING,
        time_limit_sec=30,
        candidate_elapsed_ms=(5000, 6000, 7000, 8000),
        champion_elapsed_ms=(4000, 4100, 4200, 4300),
        total_pairs=4,
    )

    assert diagnostic is None
