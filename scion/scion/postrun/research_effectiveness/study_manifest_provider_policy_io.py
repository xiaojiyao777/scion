"""Seven-leaf no-follow IO for the private M32 provider-policy join."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .study_manifest_io import (
    _FileSnapshot,
    _HistoryLoad,
    _ManifestBundle,
    _open_absolute_directory,
    _open_relative_directory,
    _parse_json_lines,
    _parse_json_object,
    _read_optional_leaf,
    _read_required_leaf,
    _RootSnapshot,
    _validate_private_root,
    _verify_final_manifest_rewalk,
    _verify_leaf_absent,
    _verify_open_leaf,
    _verify_relative_file,
)
from .study_manifest_io_primitives import (
    _directory_fingerprint,
    _Identity,
    _StudyManifestIoError,
)

_STATUS_MAX_BYTES = 8 << 20
_SUMMARY_MAX_BYTES = 32 << 20
_CURRENT_HISTORY_MAX_BYTES = 32 << 20
_CONTROLS_MAX_BYTES = 1 << 20
_CODE_LIMITS_MAX_BYTES = 4096
_RESOURCE_ENVELOPE_MAX_BYTES = 4096
_PROVIDER_POLICY_MAX_BYTES = 65_536
_ROOT_TOTAL_MAX_BYTES = 256 << 20
_CURRENT_HISTORY_TOTAL_MAX_BYTES = 64 << 20
_CURRENT_HISTORY_RECORDS_MAX = 256

_STATUS_NAME = "status.json"
_SUMMARY_NAME = "campaign_summary.json"
_CURRENT_HISTORY_NAME = "research_history.jsonl"
_CONTROLS_NAME = "initial_screening_study_controls.json"
_CODE_LIMITS_NAME = "code_research_limits.json"
_RESOURCE_ENVELOPE_NAME = "resource_envelope.json"
_PROVIDER_POLICY_NAME = "initial_screening_provider_policy.json"


@dataclass(frozen=True, repr=False)
class _ProviderPolicyRootSnapshot:
    """One seven-leaf root with its unchanged v1 six-leaf projection."""

    base: _RootSnapshot
    provider_policy: Mapping[str, Any]
    provider_policy_leaf: _FileSnapshot
    total_bytes: int

    def __repr__(self) -> str:
        return "_ProviderPolicyRootSnapshot(<redacted>)"

    __str__ = __repr__

    @property
    def leaf_identities(self) -> tuple[_Identity, ...]:
        return self.base.leaf_identities + (
            self.provider_policy_leaf.fingerprint.identity,
        )


def _load_provider_policy_root_snapshots(
    bundle: _ManifestBundle,
    *,
    roots: tuple[tuple[str, int], ...],
) -> tuple[_ProviderPolicyRootSnapshot, ...]:
    """Load all ten seven-leaf roots before semantic root validation."""

    if (
        type(bundle) is not _ManifestBundle
        or type(roots) is not tuple
        or len(roots) != 10
    ):
        raise _StudyManifestIoError
    snapshots: list[_ProviderPolicyRootSnapshot] = []
    total = 0
    history_total = 0
    for item in roots:
        if (
            type(item) is not tuple
            or len(item) != 2
            or type(item[0]) is not str
            or type(item[1]) is not int
        ):
            raise _StudyManifestIoError
        snapshot = _load_one_provider_policy_root(
            bundle,
            token=item[0],
            record_cap=item[1],
            total_limit=_ROOT_TOTAL_MAX_BYTES - total,
            history_limit=_CURRENT_HISTORY_TOTAL_MAX_BYTES - history_total,
        )
        snapshots.append(snapshot)
        total += snapshot.total_bytes
        history_total += snapshot.base.history_bytes
    result = tuple(snapshots)
    _validate_provider_policy_root_set(result)
    return result


def _load_one_provider_policy_root(
    bundle: _ManifestBundle,
    *,
    token: str,
    record_cap: int,
    total_limit: int,
    history_limit: int,
) -> _ProviderPolicyRootSnapshot:
    if (
        type(token) is not str
        or type(record_cap) is not int
        or record_cap <= 0
        or type(total_limit) is not int
        or total_limit < 0
        or type(history_limit) is not int
        or history_limit < 0
    ):
        raise _StudyManifestIoError
    root_fd, chain = _open_relative_directory(bundle, token)
    try:
        root_before = _directory_fingerprint(os.fstat(root_fd))
        _validate_private_root(root_before)
        remaining = total_limit
        status_leaf = _read_required_leaf(
            root_fd,
            _STATUS_NAME,
            limit=min(_STATUS_MAX_BYTES, remaining),
        )
        remaining -= len(status_leaf.raw)
        summary_leaf = _read_required_leaf(
            root_fd,
            _SUMMARY_NAME,
            limit=min(_SUMMARY_MAX_BYTES, remaining),
        )
        remaining -= len(summary_leaf.raw)
        history_leaf = _read_optional_leaf(
            root_fd,
            _CURRENT_HISTORY_NAME,
            limit=min(_CURRENT_HISTORY_MAX_BYTES, remaining, history_limit),
        )
        history_bytes = 0 if history_leaf is None else len(history_leaf.raw)
        remaining -= history_bytes
        controls_leaf = _read_required_leaf(
            root_fd,
            _CONTROLS_NAME,
            limit=min(_CONTROLS_MAX_BYTES, remaining),
            private=True,
        )
        remaining -= len(controls_leaf.raw)
        code_limits_leaf = _read_required_leaf(
            root_fd,
            _CODE_LIMITS_NAME,
            limit=min(_CODE_LIMITS_MAX_BYTES, remaining),
        )
        remaining -= len(code_limits_leaf.raw)
        resource_leaf = _read_required_leaf(
            root_fd,
            _RESOURCE_ENVELOPE_NAME,
            limit=min(_RESOURCE_ENVELOPE_MAX_BYTES, remaining),
        )
        remaining -= len(resource_leaf.raw)
        provider_leaf = _read_required_leaf(
            root_fd,
            _PROVIDER_POLICY_NAME,
            limit=min(_PROVIDER_POLICY_MAX_BYTES, remaining),
            private=True,
        )
        status = _parse_json_object(status_leaf.raw)
        summary = _parse_json_object(summary_leaf.raw)
        controls = _parse_json_object(controls_leaf.raw)
        code_limits = _parse_json_object(code_limits_leaf.raw)
        resource = _parse_json_object(resource_leaf.raw)
        provider_policy = _parse_json_object(provider_leaf.raw)
        current_history = _current_history(
            summary,
            history_leaf,
            record_cap=record_cap,
        )
        leaves = (
            status_leaf,
            summary_leaf,
            history_leaf,
            controls_leaf,
            code_limits_leaf,
            resource_leaf,
            provider_leaf,
        )
        _verify_loaded_leaves(root_fd, leaves)
        if _directory_fingerprint(os.fstat(root_fd)) != root_before:
            raise _StudyManifestIoError
    finally:
        os.close(root_fd)
    base_total = sum(len(leaf.raw) for leaf in leaves[:-1] if leaf is not None)
    base = _RootSnapshot(
        token=token,
        directory_chain=chain,
        root_fingerprint=root_before,
        status=status,
        summary=summary,
        current_history=current_history,
        controls=controls,
        code_limits=code_limits,
        resource_envelope=resource,
        status_leaf=status_leaf,
        summary_leaf=summary_leaf,
        history_leaf=history_leaf,
        controls_leaf=controls_leaf,
        code_limits_leaf=code_limits_leaf,
        resource_envelope_leaf=resource_leaf,
        total_bytes=base_total,
        history_bytes=history_bytes,
    )
    return _ProviderPolicyRootSnapshot(
        base=base,
        provider_policy=provider_policy,
        provider_policy_leaf=provider_leaf,
        total_bytes=base_total + len(provider_leaf.raw),
    )


def _current_history(
    summary: Mapping[str, Any],
    leaf: _FileSnapshot | None,
    *,
    record_cap: int,
) -> tuple[Mapping[str, Any], ...]:
    if leaf is None:
        if summary.get("steps") != []:
            raise _StudyManifestIoError
        return ()
    if not leaf.raw:
        raise _StudyManifestIoError
    return _parse_json_lines(
        leaf.raw,
        record_cap=min(record_cap, _CURRENT_HISTORY_RECORDS_MAX),
    )


def _verify_loaded_leaves(
    root_fd: int,
    leaves: tuple[_FileSnapshot | None, ...],
) -> None:
    for leaf in leaves:
        if leaf is None:
            _verify_leaf_absent(root_fd, _CURRENT_HISTORY_NAME)
        else:
            _verify_open_leaf(root_fd, leaf)


def _validate_provider_policy_root_set(
    snapshots: tuple[_ProviderPolicyRootSnapshot, ...],
) -> None:
    if type(snapshots) is not tuple or len(snapshots) != 10:
        raise _StudyManifestIoError
    if any(type(snapshot) is not _ProviderPolicyRootSnapshot for snapshot in snapshots):
        raise _StudyManifestIoError
    root_identities = [
        snapshot.base.root_fingerprint.identity for snapshot in snapshots
    ]
    leaf_identities = [
        identity for snapshot in snapshots for identity in snapshot.leaf_identities
    ]
    if (
        len(root_identities) != len(set(root_identities))
        or len(leaf_identities) != len(set(leaf_identities))
        or set(root_identities).intersection(leaf_identities)
        or sum(snapshot.total_bytes for snapshot in snapshots) > _ROOT_TOTAL_MAX_BYTES
        or sum(snapshot.base.history_bytes for snapshot in snapshots)
        > _CURRENT_HISTORY_TOTAL_MAX_BYTES
    ):
        raise _StudyManifestIoError


def _validate_provider_policy_identity_set(
    bundle: _ManifestBundle,
    histories: _HistoryLoad,
    roots: tuple[_ProviderPolicyRootSnapshot, ...],
) -> None:
    if (
        type(bundle) is not _ManifestBundle
        or type(histories) is not _HistoryLoad
        or type(roots) is not tuple
        or len(roots) != 10
    ):
        raise _StudyManifestIoError
    file_identities = [bundle.manifest.fingerprint.identity]
    file_identities.extend(
        snapshot.leaf.fingerprint.identity for snapshot in histories.unique_files
    )
    file_identities.extend(
        identity for root in roots for identity in root.leaf_identities
    )
    root_identities = [root.base.root_fingerprint.identity for root in roots]
    if (
        len(file_identities) != len(set(file_identities))
        or len(root_identities) != len(set(root_identities))
        or set(file_identities).intersection(root_identities)
    ):
        raise _StudyManifestIoError


def _verify_provider_policy_study_bundle(
    bundle: _ManifestBundle,
    histories: _HistoryLoad,
    roots: tuple[_ProviderPolicyRootSnapshot, ...],
) -> None:
    """Freshly rewalk every authority, then rewalk the manifest alone."""

    final_fd, final_chain = _open_absolute_directory(bundle.parent_parts)
    try:
        if final_chain != bundle.parent_chain:
            raise _StudyManifestIoError
        final_bundle = _ManifestBundle(
            manifest_path=bundle.manifest_path,
            parent_parts=bundle.parent_parts,
            parent_chain=final_chain,
            parent_fd=final_fd,
            manifest=bundle.manifest,
            value=bundle.value,
        )
        _verify_open_leaf(final_fd, bundle.manifest, compare_bytes=True)
        for history in histories.unique_files:
            _verify_relative_file(final_bundle, history)
        for root in roots:
            _verify_provider_policy_root_snapshot(final_bundle, root)
        _verify_open_leaf(final_fd, bundle.manifest, compare_bytes=True)
        if _directory_fingerprint(os.fstat(final_fd)) != final_chain[-1]:
            raise _StudyManifestIoError
    finally:
        os.close(final_fd)
    if _directory_fingerprint(os.fstat(bundle.parent_fd)) != bundle.parent_chain[-1]:
        raise _StudyManifestIoError
    _verify_final_manifest_rewalk(bundle)
    _validate_provider_policy_identity_set(bundle, histories, roots)


def _verify_provider_policy_root_snapshot(
    bundle: _ManifestBundle,
    snapshot: _ProviderPolicyRootSnapshot,
) -> None:
    root_fd, chain = _open_relative_directory(bundle, snapshot.base.token)
    try:
        if chain != snapshot.base.directory_chain:
            raise _StudyManifestIoError
        current = _directory_fingerprint(os.fstat(root_fd))
        _validate_private_root(current)
        if current != snapshot.base.root_fingerprint:
            raise _StudyManifestIoError
        for leaf in (
            snapshot.base.status_leaf,
            snapshot.base.summary_leaf,
            snapshot.base.controls_leaf,
            snapshot.base.code_limits_leaf,
            snapshot.base.resource_envelope_leaf,
            snapshot.provider_policy_leaf,
        ):
            _verify_open_leaf(root_fd, leaf, compare_bytes=True)
        if snapshot.base.history_leaf is None:
            _verify_leaf_absent(root_fd, _CURRENT_HISTORY_NAME)
        else:
            _verify_open_leaf(root_fd, snapshot.base.history_leaf, compare_bytes=True)
        if _directory_fingerprint(os.fstat(root_fd)) != snapshot.base.root_fingerprint:
            raise _StudyManifestIoError
    finally:
        os.close(root_fd)


__all__: tuple[str, ...] = ()
