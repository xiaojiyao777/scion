"""Private validation-only M32 provider-policy manifest join."""

from __future__ import annotations

from typing import Any, NoReturn

from .models import ResearchEffectivenessInputError
from .study_manifest_controls_schema import _canonical_json_bytes
from .study_manifest_io import (
    _close_manifest_bundle,
    _load_history_bases,
    _open_manifest_bundle,
    _validate_bundle_paths,
)
from .study_manifest_loader import (
    _build_validation_blocks,
    _JoinedValidationBlock,
    _loaded_history_carrier,
    _ordered_arms,
)
from .study_manifest_provider_policy_io import (
    _load_provider_policy_root_snapshots,
    _ProviderPolicyRootSnapshot,
    _validate_provider_policy_identity_set,
    _verify_provider_policy_study_bundle,
)
from .study_manifest_provider_policy_schema import (
    _MANIFEST_MAX_BYTES,
    _config_and_requested_provider_policy_join_result,
    _normalize_declared_provider_policy,
    _normalize_study_manifest_provider_policy,
    _NormalizedDeclaredProviderPolicy,
)
from .study_root import _decode_study_root

_ERROR = "STUDY_CONFIG_SUBSET_AND_REQUESTED_PROVIDER_POLICY_JOIN_INVALID"


def _validate_initial_screening_study_manifest_config_subset_and_requested_provider_policy(
    *,
    manifest_path: str,
) -> dict[str, Any]:
    """Validate v2 config and requested policy without evaluating endpoints."""

    failed = False
    result: dict[str, Any] | None = None
    try:
        result = _validate_config_and_requested_provider_policy_unsafe(manifest_path)
    except Exception:  # noqa: BLE001 - collapse every private input detail
        failed = True
    if failed or result is None:
        _fail()
    return result


def _validate_config_and_requested_provider_policy_unsafe(
    manifest_path: object,
) -> dict[str, Any]:
    bundle = _open_manifest_bundle(manifest_path)
    try:
        if (
            _canonical_json_bytes(bundle.value, max_bytes=_MANIFEST_MAX_BYTES)
            != bundle.manifest.raw
        ):
            raise ValueError
        manifest = _normalize_study_manifest_provider_policy(bundle.value)
        base_manifest = manifest.base_manifest
        arms = _ordered_arms(base_manifest)
        declarations = tuple(
            (block.loaded_history.available, block.loaded_history.files)
            for block in base_manifest.blocks
        )
        root_tokens = tuple(arm.root_path for arm in arms)
        history_tokens = tuple(
            token for _available, files in declarations for token in files
        )
        _validate_bundle_paths(roots=root_tokens, history_files=history_tokens)
        histories = _load_history_bases(
            bundle,
            expected_problem_id=base_manifest.problem_id,
            declarations=declarations,
        )
        loaded_histories = tuple(
            _loaded_history_carrier(basis) for basis in histories.bases
        )
        if len(loaded_histories) != 5:
            raise ValueError
        roots = _load_provider_policy_root_snapshots(
            bundle,
            roots=tuple((arm.root_path, arm.declared_controls.a_cap) for arm in arms),
        )
        _validate_provider_policy_identity_set(bundle, histories, roots)
        _validate_root_provider_policies(
            roots,
            manifest.declared_provider_policy,
        )
        blocks = _build_validation_blocks(
            base_manifest,
            arms,
            tuple(root.base for root in roots),
            loaded_histories,
        )
        _verify_provider_policy_study_bundle(bundle, histories, roots)
        _decode_provider_policy_validation_blocks(blocks)
        return _config_and_requested_provider_policy_join_result()
    finally:
        _close_manifest_bundle(bundle)


def _validate_root_provider_policies(
    roots: tuple[_ProviderPolicyRootSnapshot, ...],
    declared: _NormalizedDeclaredProviderPolicy,
) -> None:
    if (
        type(roots) is not tuple
        or len(roots) != 10
        or any(type(root) is not _ProviderPolicyRootSnapshot for root in roots)
        or type(declared) is not _NormalizedDeclaredProviderPolicy
    ):
        raise TypeError
    failed = False
    for root in roots:
        try:
            normalized = _normalize_declared_provider_policy(root.provider_policy)
            if (
                normalized.canonical_bytes != root.provider_policy_leaf.raw
                or normalized.canonical_bytes != declared.canonical_bytes
                or normalized.frozen != declared.frozen
            ):
                raise ValueError
        except Exception:  # noqa: BLE001 - audit every already-loaded arm
            failed = True
    if failed:
        raise ValueError


def _decode_provider_policy_validation_blocks(
    blocks: tuple[_JoinedValidationBlock, ...],
) -> None:
    if type(blocks) is not tuple or len(blocks) != 5:
        raise ValueError
    decoded = 0
    for block in blocks:
        if (
            type(block) is not _JoinedValidationBlock
            or block.arms[0].loaded_history is not block.arms[1].loaded_history
        ):
            raise ValueError
        for arm in block.arms:
            _decode_study_root(arm.artifacts)
            decoded += 1
    if decoded != 10:
        raise ValueError


def _fail() -> NoReturn:
    raise ResearchEffectivenessInputError(_ERROR)


__all__: tuple[str, ...] = ()
