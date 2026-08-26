"""Private safe-path adapter for the initial-screening study audit.

This layer proves only that ten distinct canonical roots yielded bounded,
detached byte snapshots which passed sequential path revalidation.  It does
not claim an atomic simultaneous snapshot or live freshness.  Expectations
and loaded-history controls remain caller declarations; pre-outcome manifest
and full configuration authority are intentionally outside this boundary.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from scion.core.research_history import MAX_RESEARCH_HISTORY_TOTAL_BYTES

from .models import (
    LoadedHistoryAvailable,
    LoadedHistoryUnavailable,
    ResearchEffectivenessInputError,
)
from .safe_artifact_loader import (
    _ALL_ARTIFACTS_MAX_BYTES,
    _canonical_root,
    _fail_load,
    _load_root_snapshot_from_canonical,
    _LoadedRootSnapshot,
    _validate_snapshot_set,
    _verify_root_snapshot,
)
from .study_root import (
    _compare_five_block_initial_screening_study_roots,
    _InitialScreeningStudyExpectation,
    _InitialScreeningStudyRootArtifacts,
    _MatchedInitialScreeningStudyBlock,
)


@dataclass(frozen=True, repr=False)
class _InitialScreeningStudyRootPath:
    """One private root path paired with its caller-declared controls."""

    root: str | os.PathLike[str]
    expectation: _InitialScreeningStudyExpectation

    def __post_init__(self) -> None:
        if type(self.expectation) is not _InitialScreeningStudyExpectation:
            raise ValueError("STUDY_ROOT_PATH_EXPECTATION_INVALID")

    def __repr__(self) -> str:
        return "_InitialScreeningStudyRootPath(<redacted>)"


@dataclass(frozen=True, repr=False)
class _MatchedInitialScreeningStudyRootPathBlock:
    """One private K=1/K=2 root pair sharing a declared replay basis."""

    k1: _InitialScreeningStudyRootPath
    k2: _InitialScreeningStudyRootPath
    loaded_history: LoadedHistoryAvailable | LoadedHistoryUnavailable

    def __post_init__(self) -> None:
        if (
            type(self.k1) is not _InitialScreeningStudyRootPath
            or type(self.k2) is not _InitialScreeningStudyRootPath
        ):
            raise ValueError("STUDY_ROOT_PATH_BLOCK_ARM_INVALID")
        if type(self.loaded_history) not in {
            LoadedHistoryAvailable,
            LoadedHistoryUnavailable,
        }:
            raise ValueError("STUDY_ROOT_PATH_BLOCK_HISTORY_INVALID")

    def __repr__(self) -> str:
        return "_MatchedInitialScreeningStudyRootPathBlock(<redacted>)"


def _compare_five_block_initial_screening_study_root_paths(
    *,
    blocks: tuple[_MatchedInitialScreeningStudyRootPathBlock, ...],
) -> dict[str, Any]:
    """Load ten roots safely, then run the decoded-artifact study audit."""

    if (
        type(blocks) is not tuple
        or len(blocks) != 5
        or any(
            type(block) is not _MatchedInitialScreeningStudyRootPathBlock
            for block in blocks
        )
    ):
        _fail_load()
    decoded_blocks = _load_path_blocks(blocks)
    return _compare_decoded_blocks(decoded_blocks)


def _compare_decoded_blocks(
    blocks: tuple[_MatchedInitialScreeningStudyBlock, ...],
) -> dict[str, Any]:
    failure_code: str | None = None
    unexpected_failure = False
    result: dict[str, Any] | None = None
    try:
        result = _compare_five_block_initial_screening_study_roots(blocks=blocks)
    except ResearchEffectivenessInputError as error:
        failure_code = error.code
    except Exception:  # noqa: BLE001 - sanitize decoded artifact details too
        unexpected_failure = True
    if failure_code is not None:
        raise ResearchEffectivenessInputError(failure_code)
    if unexpected_failure or result is None:
        _fail_load()
    return result


def _load_path_blocks(
    blocks: tuple[_MatchedInitialScreeningStudyRootPathBlock, ...],
) -> tuple[_MatchedInitialScreeningStudyBlock, ...]:
    failed = False
    decoded: tuple[_MatchedInitialScreeningStudyBlock, ...] | None = None
    try:
        decoded = _load_path_blocks_unsafe(blocks)
    except Exception:  # noqa: BLE001 - collapse all private loader details
        failed = True
    if failed or decoded is None:
        _fail_load()
    return decoded


def _load_path_blocks_unsafe(
    blocks: tuple[_MatchedInitialScreeningStudyRootPathBlock, ...],
) -> tuple[_MatchedInitialScreeningStudyBlock, ...]:
    paths = tuple(path for block in blocks for path in (block.k1, block.k2))
    canonical = tuple(_canonical_root(path.root) for path in paths)
    if len(set(canonical)) != 10:
        _fail_load()
    snapshots: list[_LoadedRootSnapshot] = []
    decoded: list[_MatchedInitialScreeningStudyBlock] = []
    total_bytes = 0
    history_bytes = 0
    for ordinal, block in enumerate(blocks):
        k1_snapshot = _load_one(
            block.k1,
            canonical[ordinal * 2],
            total_remaining=_ALL_ARTIFACTS_MAX_BYTES - total_bytes,
            history_remaining=MAX_RESEARCH_HISTORY_TOTAL_BYTES - history_bytes,
        )
        total_bytes += k1_snapshot.total_bytes
        history_bytes += k1_snapshot.history_bytes
        k2_snapshot = _load_one(
            block.k2,
            canonical[ordinal * 2 + 1],
            total_remaining=_ALL_ARTIFACTS_MAX_BYTES - total_bytes,
            history_remaining=MAX_RESEARCH_HISTORY_TOTAL_BYTES - history_bytes,
        )
        total_bytes += k2_snapshot.total_bytes
        history_bytes += k2_snapshot.history_bytes
        snapshots.extend((k1_snapshot, k2_snapshot))
        decoded.append(
            _MatchedInitialScreeningStudyBlock(
                k1=_artifacts(block.k1, k1_snapshot),
                k2=_artifacts(block.k2, k2_snapshot),
                loaded_history=block.loaded_history,
            )
        )
    frozen_snapshots = tuple(snapshots)
    for token, snapshot in zip(canonical, frozen_snapshots, strict=True):
        _verify_root_snapshot(token, snapshot)
    _validate_snapshot_set(frozen_snapshots)
    return tuple(decoded)


def _load_one(
    path: _InitialScreeningStudyRootPath,
    canonical: str,
    *,
    total_remaining: int,
    history_remaining: int,
) -> _LoadedRootSnapshot:
    return _load_root_snapshot_from_canonical(
        canonical,
        history_record_cap=path.expectation.effectiveness.a_cap,
        total_byte_limit=total_remaining,
        history_byte_limit=history_remaining,
    )


def _artifacts(
    path: _InitialScreeningStudyRootPath,
    snapshot: _LoadedRootSnapshot,
) -> _InitialScreeningStudyRootArtifacts:
    return _InitialScreeningStudyRootArtifacts(
        status=snapshot.status,
        summary=snapshot.summary,
        current_history=snapshot.current_history,
        expectation=path.expectation,
    )


__all__: tuple[str, ...] = ()
