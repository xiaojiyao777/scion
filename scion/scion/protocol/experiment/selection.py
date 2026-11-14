from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Sequence

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


@dataclass(frozen=True)
class CasePathResolution:
    """Structured case path resolution evidence for protocol raw metrics."""

    original: str
    resolved: str
    status: str
    source: str
    safe: bool
    reason: str = ""
    matched_root: str | None = None

    def as_metrics(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "original": self.original,
            "resolved": self.resolved,
            "status": self.status,
            "source": self.source,
            "safe": self.safe,
        }
        if self.reason:
            payload["reason"] = self.reason
        if self.matched_root:
            payload["matched_root"] = self.matched_root
        return payload


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


def validate_requested_screening_expansion(
    *,
    config: Any,
    split_manifest: SplitManifest,
    requested_rounds: int,
) -> None:
    """Reject an unusable multi-round screening plan before proposal work.

    A second evaluated round may be the expanded screening requested by the
    Decision engine.  That path must add cases and the declared split must be
    large enough for either supported proposal action.  Validating the shared
    configuration here prevents an otherwise deterministic failure only after
    H/C, Contract, Verification, canary, and the initial formal screen.
    """

    if max(1, int(requested_rounds)) <= 1:
        return

    available = len(split_manifest.screening)
    for action, initial, expanded in (
        (
            "modify",
            int(config.screening.n_cases_modify),
            int(config.screening.expand_to_modify),
        ),
        (
            "create_new",
            int(config.screening.n_cases_create),
            int(config.screening.expand_to_create),
        ),
    ):
        if expanded <= initial:
            raise ValueError(
                "multi-round screening requires expand_to_"
                f"{action.removesuffix('_new')} > n_cases_"
                f"{action.removesuffix('_new')}"
            )
        if expanded > available:
            raise ValueError(
                f"multi-round screening {action} expansion requests "
                f"{expanded} cases but the screening split declares {available}"
            )


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


def _select_cases_with_configured_priorities(
    all_cases: Sequence[str],
    n: int,
    configured_case_ids: Sequence[str] = (),
) -> List[str]:
    """Select cases while retaining configured priority cases when possible.

    Configured ids may be bare case names while the manifest stores
    split-relative paths, so matching uses exact id first and then a unique
    basename match. Ambiguous basenames are ignored rather than guessed.
    """
    cases = list(all_cases)
    total = len(cases)
    if n <= 0:
        return []
    if n >= total:
        return cases

    selected: set[str] = set()
    for case in _resolve_configured_priority_cases(cases, configured_case_ids):
        if len(selected) >= n:
            break
        selected.add(case)

    if len(selected) < n:
        for case in _select_evenly_spaced_cases(cases, n):
            if len(selected) >= n:
                break
            selected.add(case)

    if len(selected) < n:
        for case in cases:
            if len(selected) >= n:
                break
            selected.add(case)

    return [case for case in cases if case in selected]


def _select_nested_expansion_cases(
    all_cases: Sequence[str],
    *,
    initial_n: int,
    expanded_n: int,
    configured_case_ids: Sequence[str] = (),
) -> List[str]:
    """Expand a fixed initial population only by adding deterministic cases."""

    cases = list(all_cases)
    initial = _select_cases_with_configured_priorities(
        cases,
        initial_n,
        configured_case_ids,
    )
    if expanded_n <= len(initial):
        raise ValueError(
            "expanded case population must be larger than the initial population"
        )
    if expanded_n > len(cases):
        raise ValueError(
            "expanded case population exceeds the declared split population"
        )
    if expanded_n >= len(cases):
        return cases

    selected = set(initial)
    resolved_priorities = _resolve_configured_priority_cases(
        cases,
        configured_case_ids,
    )
    for case in resolved_priorities:
        if len(selected) >= expanded_n:
            break
        selected.add(case)

    remaining = [case for case in cases if case not in selected]
    needed = expanded_n - len(selected)
    selected.update(_select_evenly_spaced_cases(remaining, needed))
    expanded = [case for case in cases if case in selected]
    if not set(initial) < set(expanded):
        raise ValueError(
            "expanded case population must strictly contain the initial population"
        )
    return expanded


def _resolve_configured_priority_cases(
    all_cases: Sequence[str],
    configured_case_ids: Sequence[str],
) -> List[str]:
    cases = [str(case) for case in all_cases]
    exact = {case: case for case in cases}
    basename_matches: dict[str, list[str]] = {}
    for case in cases:
        basename_matches.setdefault(_case_basename(case), []).append(case)

    selected: list[str] = []
    seen: set[str] = set()
    for raw_case_id in configured_case_ids or ():
        case_id = str(raw_case_id or "").strip()
        if not case_id:
            continue
        match = exact.get(case_id)
        if match is None:
            matches = basename_matches.get(_case_basename(case_id), [])
            if len(matches) == 1:
                match = matches[0]
        if match is None or match in seen:
            continue
        selected.append(match)
        seen.add(match)
    return selected


def _case_basename(case_id: str) -> str:
    return str(case_id).replace("\\", "/").rstrip("/").split("/")[-1]


def configured_priority_case_ids(
    *,
    config: Any,
    stage: ExperimentStage,
) -> tuple[str, ...]:
    """Return stage-local configured case priorities, if the protocol declares any."""

    stage_config = getattr(config, stage.value, None)
    return tuple(
        str(case_id).strip()
        for case_id in getattr(stage_config, "priority_case_ids", ()) or ()
        if str(case_id).strip()
    )


def resolved_configured_priority_case_ids(
    *,
    config: Any,
    stage: ExperimentStage,
    all_cases: Sequence[str],
    selected_cases: Sequence[str],
) -> tuple[str, ...]:
    """Resolve only problem-configured priority ids included in a selection."""

    selected = set(selected_cases)
    return tuple(
        case
        for case in _resolve_configured_priority_cases(
            all_cases,
            configured_priority_case_ids(config=config, stage=stage),
        )
        if case in selected
    )


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
    configured_priorities = configured_priority_case_ids(
        config=config,
        stage=stage,
    )

    if stage == ExperimentStage.SCREENING:
        initial_n = (
            config.screening.n_cases_create
            if hypothesis_action == "create_new"
            else config.screening.n_cases_modify
        )
        if expand_round > 0:
            n = (
                config.screening.expand_to_create
                if hypothesis_action == "create_new"
                else config.screening.expand_to_modify
            )
        else:
            n = initial_n
    elif stage == ExperimentStage.VALIDATION:
        initial_n = config.validation.n_cases
        n = (
            config.validation.expand_to
            if expand_round > 0
            else config.validation.n_cases
        )
    elif stage == ExperimentStage.FROZEN:
        initial_n = config.frozen.n_cases
        n = config.frozen.n_cases
    else:
        return all_cases

    if expand_round > 0:
        return _select_nested_expansion_cases(
            all_cases,
            initial_n=initial_n,
            expanded_n=n,
            configured_case_ids=configured_priorities,
        )
    return _select_cases_with_configured_priorities(
        all_cases,
        n,
        configured_priorities,
    )


def select_seeds(
    *,
    config: Any,
    seed_ledger: SeedLedger,
    stage: ExperimentStage,
    expanded: bool = False,
) -> List[int]:
    """Select the preregistered seed prefix required by the protocol stage.

    Ledger order is authoritative.  Protocols that explicitly declare
    ``expand_n_seeds`` opt into staged, strict prefixes.  Legacy protocols keep
    their historical behavior and consume the complete stage ledger.
    """

    available = seed_ledger.get_seeds(stage)
    staged_prefixes = config.screening.expand_n_seeds is not None
    if not staged_prefixes:
        return available

    if stage == ExperimentStage.SCREENING:
        required = (
            config.screening.effective_expand_n_seeds
            if expanded
            else config.screening.n_seeds
        )
    elif stage == ExperimentStage.VALIDATION:
        required = config.validation.n_seeds
    elif stage == ExperimentStage.FROZEN:
        required = config.frozen.n_seeds
    else:  # pragma: no cover - ExperimentStage is currently exhaustive.
        raise ValueError(f"Unknown stage: {stage}")

    required = int(required)
    if len(available) < required:
        raise ValueError(
            f"seed ledger has insufficient {stage.value} seeds: "
            f"required={required}, available={len(available)}"
        )
    return available[:required]


def resolve_case_path(
    instance_path: str,
    *,
    workspace: str,
    safe_data_roots: Sequence[str] = (),
) -> str:
    """Resolve a case path against a workspace or declared read-only data roots."""

    return resolve_case_path_details(
        instance_path,
        workspace=workspace,
        safe_data_roots=safe_data_roots,
    ).resolved


def resolve_case_path_details(
    instance_path: str,
    *,
    workspace: str,
    safe_data_roots: Sequence[str] = (),
) -> CasePathResolution:
    """Resolve a case path and return boundary/safety status."""

    original = str(instance_path)
    path = Path(original).expanduser()
    workspace_root = Path(workspace).expanduser().resolve(strict=False)
    safe_roots = tuple(
        Path(root).expanduser().resolve(strict=False)
        for root in safe_data_roots
        if str(root)
    )

    if path.is_absolute():
        resolved = path.resolve(strict=False)
        if _is_relative_to(resolved, workspace_root):
            return CasePathResolution(
                original=original,
                resolved=str(resolved),
                status="resolved_workspace",
                source="absolute",
                safe=True,
                matched_root=str(workspace_root),
            )
        safe_root = _matching_root(resolved, safe_roots)
        if safe_root is not None:
            return CasePathResolution(
                original=original,
                resolved=str(resolved),
                status="resolved_safe_data_root",
                source="absolute",
                safe=True,
                matched_root=str(safe_root),
            )
        return CasePathResolution(
            original=original,
            resolved=str(path),
            status="absolute_outside_roots",
            source="absolute",
            safe=False,
            reason="absolute case path is outside workspace and safe_data_roots",
        )

    workspace_candidate = workspace_root / path
    if workspace_candidate.exists():
        resolved = workspace_candidate.resolve(strict=False)
        if _is_relative_to(resolved, workspace_root):
            return CasePathResolution(
                original=original,
                resolved=str(resolved),
                status="resolved_workspace",
                source="workspace",
                safe=True,
                matched_root=str(workspace_root),
            )
        return CasePathResolution(
            original=original,
            resolved=str(workspace_candidate),
            status="workspace_escape",
            source="workspace",
            safe=False,
            reason="relative case path escapes workspace",
            matched_root=str(workspace_root),
        )

    for root_path in safe_roots:
        candidate = root_path / path
        if candidate.exists():
            resolved = candidate.resolve(strict=False)
            if _is_relative_to(resolved, root_path):
                return CasePathResolution(
                    original=original,
                    resolved=str(resolved),
                    status="resolved_safe_data_root",
                    source="safe_data_root",
                    safe=True,
                    matched_root=str(root_path),
                )
            return CasePathResolution(
                original=original,
                resolved=str(candidate),
                status="safe_data_root_escape",
                source="safe_data_root",
                safe=False,
                reason="relative case path escapes safe_data_root",
                matched_root=str(root_path),
            )

    return CasePathResolution(
        original=original,
        resolved=original,
        status="unresolved_relative",
        source="unresolved",
        safe=False,
        reason="relative case path did not resolve under workspace or safe_data_roots",
    )


def validate_case_path_resolution(
    resolution: CasePathResolution,
    *,
    strict: bool,
) -> None:
    """Reject unsafe case paths when protocol strict path safety is enabled."""

    if strict and not resolution.safe:
        raise ValueError(
            "Unsafe case path in strict ExperimentProtocol: "
            f"{resolution.original!r} status={resolution.status} "
            f"reason={resolution.reason or 'not under an allowed root'}"
        )


def _matching_root(path: Path, roots: Sequence[Path]) -> Path | None:
    for root in roots:
        if _is_relative_to(path, root):
            return root
    return None


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


__all__ = [
    "CasePathResolution",
    "SeedLedger",
    "SplitManager",
    "_select_evenly_spaced_cases",
    "resolve_case_path",
    "resolve_case_path_details",
    "select_cases",
    "select_seeds",
    "validate_case_path_resolution",
    "validate_requested_screening_expansion",
]
