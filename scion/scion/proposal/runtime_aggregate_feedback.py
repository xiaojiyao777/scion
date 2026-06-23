"""Proposal-visible runtime aggregate semantics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

BUDGET_EXHAUSTING_RUNTIME_INTERPRETATION = "not_applicable_budget_exhausting"
_KNOWN_RUNTIME_MODELS = frozenset({"comparative", "budget_exhausting"})


@dataclass(frozen=True)
class RuntimeAggregateFeedback:
    runtime_model: str
    runtime_pairs: int | None
    runtime_ratio_median: float | None
    runtime_delta_median_ms: float | None
    runtime_regression_rate: float | None
    runtime_regression_rate_interpretation: str | None
    proposal_visibility_only: bool = True
    decision_features_excluded: bool = True

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "runtime_ratio_median": self.runtime_ratio_median,
            "runtime_delta_median_ms": self.runtime_delta_median_ms,
            "runtime_model": self.runtime_model,
            "runtime_regression_rate_interpretation": (
                self.runtime_regression_rate_interpretation
            ),
        }
        if self.runtime_pairs is not None:
            payload["runtime_pairs"] = self.runtime_pairs
        if self.runtime_model == "budget_exhausting":
            payload["runtime_regression_rate_interpretation"] = (
                self.runtime_regression_rate_interpretation
                or BUDGET_EXHAUSTING_RUNTIME_INTERPRETATION
            )
        else:
            payload["runtime_regression_rate"] = self.runtime_regression_rate
        return payload


def runtime_aggregate_feedback_payload(
    *,
    runtime_ratio_median: float | None,
    runtime_delta_median_ms: float | None,
    runtime_regression_rate: float | None,
    runtime_model: str,
    runtime_regression_rate_interpretation: str | None = None,
    runtime_pairs: int | None = None,
) -> dict[str, Any]:
    return RuntimeAggregateFeedback(
        runtime_model=normalize_runtime_model(runtime_model),
        runtime_pairs=runtime_pairs,
        runtime_ratio_median=runtime_ratio_median,
        runtime_delta_median_ms=runtime_delta_median_ms,
        runtime_regression_rate=runtime_regression_rate,
        runtime_regression_rate_interpretation=(
            runtime_regression_rate_interpretation
        ),
    ).to_payload()


def runtime_model_from_protocol(protocol: Any) -> str:
    summary = getattr(protocol, "candidate_surface_runtime_summary", None)
    if isinstance(summary, Mapping):
        diagnostic = summary.get("runtime_budget_diagnostic")
        if isinstance(diagnostic, Mapping):
            model = normalize_runtime_model(diagnostic.get("runtime_model"))
            if model:
                return model
        return normalize_runtime_model(summary.get("runtime_model"))
    return ""


def normalize_runtime_model(value: Any) -> str:
    text = str(value or "").strip()
    return text if text in _KNOWN_RUNTIME_MODELS else ""
