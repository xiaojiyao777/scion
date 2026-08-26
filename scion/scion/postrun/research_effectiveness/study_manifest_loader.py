"""Private validation-only M32 manifest and ten-root config join."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, NoReturn

from .models import (
    LoadedHistoryAvailable,
    LoadedHistoryUnavailable,
    ResearchEffectivenessExpectation,
    ResearchEffectivenessInputError,
)
from .study_manifest_io import (
    _close_manifest_bundle,
    _HistoryBasis,
    _load_history_bases,
    _load_root_snapshots,
    _open_manifest_bundle,
    _RootSnapshot,
    _validate_bundle_paths,
    _validate_identity_set,
    _verify_study_bundle,
)
from .study_manifest_schema import (
    _canonical_json_bytes,
    _config_subset_join_result,
    _derive_expectation,
    _freeze_json,
    _normalize_root_controls,
    _normalize_study_manifest,
    _NormalizedStudyArm,
    _NormalizedStudyControls,
    _NormalizedStudyManifest,
    _StudyExpectationFacts,
    _validate_root_control_join,
)
from .study_root import (
    _decode_study_root,
    _InitialScreeningStudyExpectation,
    _InitialScreeningStudyRootArtifacts,
)

_ERROR = "STUDY_CONFIG_SUBSET_JOIN_INVALID"
_MANIFEST_MAX_BYTES = 16 << 20


@dataclass(frozen=True, repr=False)
class _JoinedValidationArm:
    """One decoded-input carrier sharing its block's replay declaration."""

    artifacts: _InitialScreeningStudyRootArtifacts
    loaded_history: LoadedHistoryAvailable | LoadedHistoryUnavailable

    def __repr__(self) -> str:
        return "_JoinedValidationArm(<redacted>)"

    __str__ = __repr__


@dataclass(frozen=True, repr=False)
class _JoinedValidationBlock:
    """One ordered pair used only to prove config-subset association."""

    arms: tuple[_JoinedValidationArm, _JoinedValidationArm]

    def __repr__(self) -> str:
        return "_JoinedValidationBlock(<redacted>)"

    __str__ = __repr__


def _validate_initial_screening_study_manifest_config_subset(
    *,
    manifest_path: str,
) -> dict[str, Any]:
    """Validate the private config subset without evaluating endpoints."""

    failed = False
    result: dict[str, Any] | None = None
    try:
        result = _validate_config_subset_unsafe(manifest_path)
    except Exception:  # noqa: BLE001 - collapse every path/schema/artifact detail
        failed = True
    if failed or result is None:
        _fail()
    return result


def _validate_config_subset_unsafe(manifest_path: object) -> dict[str, Any]:
    bundle = _open_manifest_bundle(manifest_path)
    try:
        if (
            _canonical_json_bytes(
                bundle.value,
                max_bytes=_MANIFEST_MAX_BYTES,
            )
            != bundle.manifest.raw
        ):
            raise ValueError
        manifest = _normalize_study_manifest(bundle.value)
        arms = _ordered_arms(manifest)
        declarations = tuple(
            (block.loaded_history.available, block.loaded_history.files)
            for block in manifest.blocks
        )
        root_tokens = tuple(arm.root_path for arm in arms)
        history_tokens = tuple(
            token for _available, files in declarations for token in files
        )
        _validate_bundle_paths(roots=root_tokens, history_files=history_tokens)
        histories = _load_history_bases(
            bundle,
            expected_problem_id=manifest.problem_id,
            declarations=declarations,
        )
        loaded_histories = tuple(
            _loaded_history_carrier(basis) for basis in histories.bases
        )
        if len(loaded_histories) != 5:
            raise ValueError
        roots = _load_root_snapshots(
            bundle,
            roots=tuple((arm.root_path, arm.declared_controls.a_cap) for arm in arms),
        )
        _validate_identity_set(bundle, histories, roots)
        blocks = _build_validation_blocks(
            manifest,
            arms,
            roots,
            loaded_histories,
        )
        _verify_study_bundle(bundle, histories, roots)
        _decode_validation_blocks(blocks)
        return _config_subset_join_result()
    finally:
        _close_manifest_bundle(bundle)


def _ordered_arms(
    manifest: _NormalizedStudyManifest,
) -> tuple[_NormalizedStudyArm, ...]:
    if type(manifest) is not _NormalizedStudyManifest:
        raise TypeError
    arms = tuple(arm for block in manifest.blocks for arm in block.arms)
    if len(arms) != 10:
        raise ValueError
    return arms


def _loaded_history_carrier(
    basis: _HistoryBasis,
) -> LoadedHistoryAvailable | LoadedHistoryUnavailable:
    if type(basis) is not _HistoryBasis:
        raise TypeError
    if basis.available:
        return LoadedHistoryAvailable(records=basis.records)
    if basis.records or basis.files:
        raise ValueError
    return LoadedHistoryUnavailable()


def _build_validation_blocks(
    manifest: _NormalizedStudyManifest,
    arms: tuple[_NormalizedStudyArm, ...],
    roots: tuple[_RootSnapshot, ...],
    loaded_histories: tuple[
        LoadedHistoryAvailable | LoadedHistoryUnavailable,
        ...,
    ],
) -> tuple[_JoinedValidationBlock, ...]:
    if len(arms) != 10 or len(roots) != 10 or len(loaded_histories) != 5:
        raise ValueError
    artifacts: list[_InitialScreeningStudyRootArtifacts] = []
    visible_keys: list[tuple[Any, ...]] = []
    for arm, root in zip(arms, roots, strict=True):
        controls = _normalize_root_controls(root.controls)
        if controls.canonical_bytes != root.controls_leaf.raw:
            raise ValueError
        joined = _validate_root_control_join(
            arm,
            controls,
            root.code_limits,
            root.resource_envelope,
        )
        if (
            _producer_json_bytes(root.code_limits) != root.code_limits_leaf.raw
            or _producer_json_bytes(root.resource_envelope)
            != root.resource_envelope_leaf.raw
        ):
            raise ValueError
        campaign_id = root.status.get("campaign_id")
        if type(campaign_id) is not str or campaign_id != arm.campaign_id:
            raise ValueError
        visible_keys.append(_visible_root_key(root, joined))
        facts = _derive_expectation(manifest.problem_id, joined)
        artifacts.append(_root_artifacts(root, facts))
    if len(artifacts) != 10:
        raise ValueError
    blocks: list[_JoinedValidationBlock] = []
    for ordinal, history in enumerate(loaded_histories):
        if visible_keys[ordinal * 2] != visible_keys[ordinal * 2 + 1]:
            raise ValueError
        left = _JoinedValidationArm(artifacts[ordinal * 2], history)
        right = _JoinedValidationArm(artifacts[ordinal * 2 + 1], history)
        if left.loaded_history is not right.loaded_history:
            raise ValueError
        blocks.append(_JoinedValidationBlock((left, right)))
    return tuple(blocks)


def _visible_root_key(
    root: _RootSnapshot,
    controls: _NormalizedStudyControls,
) -> tuple[Any, ...]:
    active = root.status.get("active_slots")
    readiness = root.status.get("measurement_readiness")
    champion_version = root.status.get("champion_version")
    weight_revision = root.status.get("champion_weight_revision")
    if (
        type(active) is not dict
        or type(active.get("max")) is not int
        or active["max"] != controls.scheduler_max
        or _freeze_json(readiness) != controls.measurement_readiness
        or type(champion_version) is not int
        or type(weight_revision) is not int
    ):
        raise ValueError
    return (
        champion_version,
        weight_revision,
        active["max"],
        controls.measurement_readiness,
    )


def _decode_validation_blocks(
    blocks: tuple[_JoinedValidationBlock, ...],
) -> None:
    if len(blocks) != 5:
        raise ValueError
    for block in blocks:
        if (
            type(block) is not _JoinedValidationBlock
            or block.arms[0].loaded_history is not block.arms[1].loaded_history
        ):
            raise ValueError
        for arm in block.arms:
            _decode_study_root(arm.artifacts)


def _producer_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, allow_nan=False, indent=2, sort_keys=True).encode("utf-8")
        + b"\n"
    )


def _root_artifacts(
    root: _RootSnapshot,
    facts: _StudyExpectationFacts,
) -> _InitialScreeningStudyRootArtifacts:
    effectiveness = ResearchEffectivenessExpectation(
        problem_id=facts.problem_id,
        expected_initial_case_count=facts.expected_initial_case_count,
        expected_initial_pair_count=facts.expected_initial_pair_count,
        a_cap=facts.a_cap,
        p_cap=facts.p_cap,
        max_hypothesis_candidates=facts.max_hypothesis_candidates,
    )
    expectation = _InitialScreeningStudyExpectation(
        effectiveness=effectiveness,
        case_refs=facts.case_refs,
        seeds=facts.seeds,
        equivalence_band=facts.equivalence_band,
    )
    return _InitialScreeningStudyRootArtifacts(
        status=root.status,
        summary=root.summary,
        current_history=root.current_history,
        expectation=expectation,
    )


def _fail() -> NoReturn:
    raise ResearchEffectivenessInputError(_ERROR)


__all__: tuple[str, ...] = ()
