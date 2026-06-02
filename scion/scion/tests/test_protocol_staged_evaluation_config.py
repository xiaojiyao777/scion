from __future__ import annotations

import pytest

from scion.config.protocol_config import (
    EvaluationPipelineConfig,
    EvaluationStageConfig,
    ProtocolConfig,
)


def test_quick_broad_protocol_stage_summary_is_generic() -> None:
    config = ProtocolConfig(
        evaluation_pipeline=EvaluationPipelineConfig(
            enabled=True,
            stages=(
                EvaluationStageConfig(
                    name="quick_signal",
                    role="quick_prescreen",
                    split="screening",
                    n_cases=4,
                    n_seeds=1,
                    expose="full",
                    gate="diagnostic",
                    hard_failure=False,
                    smoke_runtime_policy="diagnostic_only",
                ),
                EvaluationStageConfig(
                    name="broad_safety",
                    role="broad_screening",
                    split="validation",
                    n_cases=24,
                    n_seeds=2,
                    expose="aggregate_only",
                    gate="screening",
                    hard_failure=True,
                ),
            ),
        )
    )

    summary = config.evaluation_stage_summary()

    assert summary == [
        {
            "name": "quick_signal",
            "role": "quick_prescreen",
            "split": "screening",
            "n_cases": 4,
            "n_seeds": 1,
            "expose": "full",
            "gate": "diagnostic",
            "hard_failure": False,
            "smoke_runtime_policy": "diagnostic_only",
        },
        {
            "name": "broad_safety",
            "role": "broad_screening",
            "split": "validation",
            "n_cases": 24,
            "n_seeds": 2,
            "expose": "aggregate_only",
            "gate": "screening",
            "hard_failure": True,
            "smoke_runtime_policy": "diagnostic_only",
        },
    ]


def test_evaluation_pipeline_stage_names_are_unique() -> None:
    with pytest.raises(ValueError, match="stage names must be unique"):
        EvaluationPipelineConfig(
            enabled=True,
            stages=(
                EvaluationStageConfig(
                    name="quick_signal",
                    role="quick_prescreen",
                ),
                EvaluationStageConfig(
                    name="quick_signal",
                    role="broad_screening",
                ),
            ),
        )
