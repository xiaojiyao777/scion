"""Provider-delegated solver search effort checks."""

from __future__ import annotations

from typing import Any, Mapping

from scion.core.models import HypothesisProposal, PatchProposal, patch_file_changes
from scion.core.paths import normalize_relative_patch_path

from .constants import (
    _ALGORITHM_SMOKE_LOW_EFFORT_MAX_RUNTIME_RATIO,
    _ALGORITHM_SMOKE_TIME_LIMIT_SEC,
)


def _solver_design_zero_effort_issue(
    *,
    patch: PatchProposal,
    hypothesis: HypothesisProposal | None,
    runs: list[dict[str, Any]],
    provider: Any | None = None,
) -> str | None:
    checker = getattr(provider, "zero_effort_issue", None)
    if callable(checker):
        return checker(patch=patch, hypothesis=hypothesis, runs=runs)
    return None


def _solver_design_low_effort_issue(
    *,
    patch: PatchProposal,
    hypothesis: HypothesisProposal | None,
    runs: list[dict[str, Any]],
    micro_results: list[dict[str, Any]],
    provider: Any | None = None,
) -> str | None:
    checker = getattr(provider, "low_effort_issue", None)
    if callable(checker):
        return checker(
            patch=patch,
            hypothesis=hypothesis,
            runs=runs,
            micro_results=micro_results,
        )
    return None


def _solver_design_patch_claims_search_effort(
    patch: PatchProposal,
    hypothesis: HypothesisProposal | None,
    *,
    provider: Any | None = None,
) -> bool:
    checker = getattr(provider, "patch_claims_search_effort", None)
    if callable(checker):
        return bool(checker(patch, hypothesis))
    return False


def _solver_design_patch_paths(patch: PatchProposal) -> list[str]:
    paths: list[str] = []
    for change in patch_file_changes(patch):
        try:
            path = normalize_relative_patch_path(change.file_path)
        except ValueError:
            path = str(change.file_path or "")
        if path:
            paths.append(path)
    return paths


def _solver_design_smoke_runtime_underspent(
    run: Mapping[str, Any],
    *,
    micro_by_case_seed: Mapping[tuple[str, int], Mapping[str, Any]],
) -> bool:
    elapsed = _nonnegative_int((run.get("run") or {}).get("elapsed_ms"))
    if elapsed <= 0:
        return False

    key = (str(run.get("case") or ""), _nonnegative_int(run.get("seed")))
    micro = micro_by_case_seed.get(key)
    if isinstance(micro, Mapping):
        champion_elapsed = _nonnegative_int(micro.get("champion_elapsed_ms"))
        if champion_elapsed > 0:
            return (
                elapsed / champion_elapsed
                <= _ALGORITHM_SMOKE_LOW_EFFORT_MAX_RUNTIME_RATIO
            )
    return (
        elapsed
        <= int(
            _ALGORITHM_SMOKE_TIME_LIMIT_SEC
            * 1000
            * _ALGORITHM_SMOKE_LOW_EFFORT_MAX_RUNTIME_RATIO
        )
    )


def _runtime_stop_reason(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text or "unknown"


def _nonnegative_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0
