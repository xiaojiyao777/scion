from __future__ import annotations

from pathlib import Path
from typing import List, Sequence

from scion.config.problem import SeedLedgerConfig, SplitManifest
from scion.core.models import ExperimentStage


class SplitManager:
    def __init__(self, manifest: SplitManifest) -> None:
        self._manifest = manifest

    def get_cases(self, stage: ExperimentStage) -> List[str]:
        if stage == ExperimentStage.SCREENING:
            return list(self._manifest.screening)
        elif stage == ExperimentStage.VALIDATION:
            return list(self._manifest.validation)
        elif stage == ExperimentStage.FROZEN:
            return list(self._manifest.frozen)
        raise ValueError(f"Unknown stage: {stage}")

    def get_canary_cases(self) -> List[str]:
        """Return the dedicated canary case list."""
        return list(self._manifest.canary)

    def safe_data_roots(self) -> List[str]:
        """Return optional read-only data roots for external case assets."""
        return list(getattr(self._manifest, "safe_data_roots", ()))

    def validate_disjoint(self) -> bool:
        self._manifest.validate_disjoint()
        return True


class SeedLedger:
    def __init__(self, ledger: SeedLedgerConfig) -> None:
        self._ledger = ledger

    def get_seeds(self, stage: ExperimentStage) -> List[int]:
        if stage == ExperimentStage.SCREENING:
            return list(self._ledger.screening)
        elif stage == ExperimentStage.VALIDATION:
            return list(self._ledger.validation)
        elif stage == ExperimentStage.FROZEN:
            return list(self._ledger.frozen)
        raise ValueError(f"Unknown stage: {stage}")

    def get_canary_seeds(self) -> List[int]:
        """Return the dedicated canary seed list."""
        return list(self._ledger.canary)


def _select_evenly_spaced_cases(all_cases: Sequence[str], n: int) -> List[str]:
    """Select a deterministic spread across the manifest instead of a prefix.

    Split manifests are often ordered by generation family, size, or creation
    time. Prefix selection can accidentally make screening blind to later
    strata. Even spacing keeps runs reproducible while covering the full split.
    """
    cases = list(all_cases)
    total = len(cases)
    if n <= 0:
        return []
    if n >= total:
        return cases
    if n == 1:
        return [cases[total // 2]]

    indices = [round(i * (total - 1) / (n - 1)) for i in range(n)]
    # ``round`` should be unique for n <= total, but keep a deterministic
    # fill path for small edge cases and future Python behavior changes.
    selected = []
    seen: set[int] = set()
    for idx in indices:
        if idx not in seen:
            selected.append(idx)
            seen.add(idx)
    for idx in range(total):
        if len(selected) >= n:
            break
        if idx not in seen:
            selected.append(idx)
            seen.add(idx)

    return [cases[i] for i in sorted(selected[:n])]


def select_cases(
    *,
    config,
    split_manager: SplitManager,
    stage: ExperimentStage,
    hypothesis_action: str,
    expand_round: int,
) -> List[str]:
    """Select deterministic protocol cases for a stage/action pair."""
    all_cases = split_manager.get_cases(stage)

    if stage == ExperimentStage.SCREENING:
        if expand_round > 0:
            n = (
                config.screening.expand_to_create
                if hypothesis_action == "create_new"
                else config.screening.expand_to_modify
            )
        else:
            n = (
                config.screening.n_cases_create
                if hypothesis_action == "create_new"
                else config.screening.n_cases_modify
            )
    elif stage == ExperimentStage.VALIDATION:
        n = (
            config.validation.expand_to
            if expand_round > 0
            else config.validation.n_cases
        )
    elif stage == ExperimentStage.FROZEN:
        n = config.frozen.n_cases
    else:
        return all_cases

    return _select_evenly_spaced_cases(all_cases, n)


def select_seeds(*, seed_ledger: SeedLedger, stage: ExperimentStage) -> List[int]:
    """Return the fixed seed list for the stage; expands never add seeds."""
    return seed_ledger.get_seeds(stage)


def resolve_case_path(
    instance_path: str,
    *,
    workspace: str,
    safe_data_roots: Sequence[str] = (),
) -> str:
    """Resolve a case path against a workspace or declared read-only data roots."""

    path = Path(instance_path)
    if path.is_absolute():
        return str(path)

    workspace_candidate = Path(workspace) / path
    if workspace_candidate.exists():
        return str(workspace_candidate)

    for root in safe_data_roots:
        root_path = Path(root).expanduser()
        candidate = root_path / path
        if candidate.exists():
            return str(candidate.resolve(strict=False))

    return instance_path


__all__ = [
    "SeedLedger",
    "SplitManager",
    "_select_evenly_spaced_cases",
    "resolve_case_path",
    "select_cases",
    "select_seeds",
]
