"""Authority-bound code-source selection for checkpoint-A hypothesis prompts.

The owner accepts only the leaf request and a Registry-owned SQLite snapshot.
It derives the selected campaign path from construction-time authorities, then
captures immutable source bytes once.  It is deliberately not a general path,
manifest, mapping, or code-string ingestion surface.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from scion.core.models import Branch, BranchState
from scion.lineage import sqlite_connection as _sqlite
from scion.lineage.champion_store import (
    ConnectionScopedChampionStore,
    StoredChampionRecord,
)
from scion.lineage.durable_owner import (
    DurableOwnerIntegrityError,
    RevisionedBranchRecord,
)
from scion.proposal import hypothesis_generation_authority as _generation
from scion.runtime.workspace import (
    EditableIdentityBytesCapture,
    WorkspaceIdentityCaptureError,
    WorkspaceMaterializer,
)

HypothesisCodeSource = _generation.HypothesisCodeSource
HypothesisCodeSourceRequest = _generation.HypothesisCodeSourceRequest

__all__ = (
    "CampaignWorkspaceAuthority",
    "HypothesisCodeSource",
    "HypothesisCodeSourceOwner",
    "HypothesisCodeSourceOwnerError",
    "HypothesisCodeSourceRejectedError",
    "HypothesisCodeSourceRequest",
    "HypothesisCodeSourceUnknownError",
)

_SAFE_BRANCH_ID: Final[re.Pattern[str]] = re.compile(
    r"[A-Za-z0-9](?:[A-Za-z0-9_.-]*[A-Za-z0-9])?"
)


class HypothesisCodeSourceOwnerError(RuntimeError):
    """Base error for the checkpoint-A semantic code-source owner."""


class HypothesisCodeSourceRejectedError(HypothesisCodeSourceOwnerError):
    """Captured durable or filesystem facts deterministically reject a source."""


class HypothesisCodeSourceUnknownError(HypothesisCodeSourceOwnerError):
    """An unexpected failure left source selection execution-uncertain."""


def _sealed_subclass(name: str) -> None:
    raise TypeError(f"{name} is sealed")


def _canonical_owned_directory(path: Path, *, label: str) -> Path:
    if not path.is_absolute():
        raise HypothesisCodeSourceRejectedError(f"{label} is not absolute")
    if path.is_symlink():
        raise HypothesisCodeSourceRejectedError(f"{label} cannot be a symlink")
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise HypothesisCodeSourceRejectedError(f"{label} is unavailable") from exc
    if path != resolved or not resolved.is_dir():
        raise HypothesisCodeSourceRejectedError(
            f"{label} is not one canonical directory"
        )
    return resolved


class CampaignWorkspaceAuthority:
    """Sealed path derivation authority for one exact campaign materializer."""

    __slots__ = (
        "__campaign_root",
        "__champions_root",
        "__editable_patterns",
        "__frozen_patterns",
        "__materializer",
        "__workspaces_root",
    )

    def __init_subclass__(cls, **_kwargs: object) -> None:
        _sealed_subclass("CampaignWorkspaceAuthority")

    def __init__(self, materializer: WorkspaceMaterializer) -> None:
        if type(materializer) is not WorkspaceMaterializer:
            raise TypeError(
                "CampaignWorkspaceAuthority requires an exact WorkspaceMaterializer"
            )
        campaign_root = _canonical_owned_directory(
            materializer._campaign_dir,
            label="campaign workspace root",
        )
        workspaces_root = _canonical_owned_directory(
            materializer._workspaces_dir,
            label="campaign Branch-workspace root",
        )
        champions_root = _canonical_owned_directory(
            materializer._champions_dir,
            label="campaign champion root",
        )
        if (
            workspaces_root.parent != campaign_root
            or workspaces_root.name != "workspaces"
            or champions_root.parent != campaign_root
            or champions_root.name != "champions"
        ):
            raise HypothesisCodeSourceRejectedError(
                "campaign materializer roots do not have the frozen layout"
            )
        self.__materializer = materializer
        self.__campaign_root = campaign_root
        self.__workspaces_root = workspaces_root
        self.__champions_root = champions_root
        self.__editable_patterns = materializer._editable_patterns
        self.__frozen_patterns = materializer._frozen_patterns

    def __copy__(self) -> CampaignWorkspaceAuthority:
        raise TypeError("CampaignWorkspaceAuthority cannot be copied")

    def __deepcopy__(self, _memo: dict[int, object]) -> CampaignWorkspaceAuthority:
        raise TypeError("CampaignWorkspaceAuthority cannot be copied")

    def __reduce__(self) -> object:
        raise TypeError("CampaignWorkspaceAuthority cannot be pickled")

    def __reduce_ex__(self, _protocol: int) -> object:
        raise TypeError("CampaignWorkspaceAuthority cannot be pickled")

    def _require_intact(self) -> None:
        materializer = self.__materializer
        if (
            materializer._campaign_dir != self.__campaign_root
            or materializer._workspaces_dir != self.__workspaces_root
            or materializer._champions_dir != self.__champions_root
            or materializer._editable_patterns != self.__editable_patterns
            or materializer._frozen_patterns != self.__frozen_patterns
        ):
            raise HypothesisCodeSourceRejectedError(
                "campaign workspace authority configuration changed"
            )

    def _capture_branch_workspace(
        self,
        branch_id: str,
    ) -> EditableIdentityBytesCapture:
        self._require_intact()
        if (
            type(branch_id) is not str
            or _SAFE_BRANCH_ID.fullmatch(branch_id) is None
        ):
            raise HypothesisCodeSourceRejectedError(
                "captured Branch ID cannot derive an owned workspace"
            )
        workspace = self.__workspaces_root / branch_id
        return self._capture(workspace, label="verified Branch workspace")

    def _capture_champion_snapshot(
        self,
        champion_owner: StoredChampionRecord,
    ) -> EditableIdentityBytesCapture:
        self._require_intact()
        if type(champion_owner) is not StoredChampionRecord:
            raise HypothesisCodeSourceRejectedError(
                "base champion source requires an exact stored champion token"
            )
        try:
            champion = champion_owner.value()
        except DurableOwnerIntegrityError as exc:
            raise HypothesisCodeSourceRejectedError(
                "base champion token failed storage validation"
            ) from exc
        if (
            type(champion.code_snapshot_path) is not str
            or not champion.code_snapshot_path
        ):
            raise HypothesisCodeSourceRejectedError(
                "base champion snapshot path is invalid"
            )
        snapshot = Path(champion.code_snapshot_path)
        canonical = _canonical_owned_directory(
            snapshot,
            label="base champion snapshot",
        )
        try:
            relative = canonical.relative_to(self.__champions_root)
        except ValueError as exc:
            raise HypothesisCodeSourceRejectedError(
                "base champion snapshot is outside the campaign authority"
            ) from exc
        if not relative.parts:
            raise HypothesisCodeSourceRejectedError(
                "campaign champion root is not a champion snapshot"
            )
        return self._capture(canonical, label="base champion snapshot")

    def _capture(
        self,
        workspace: Path,
        *,
        label: str,
    ) -> EditableIdentityBytesCapture:
        try:
            return self.__materializer.capture_editable_identity_bytes(str(workspace))
        except WorkspaceIdentityCaptureError as exc:
            raise HypothesisCodeSourceRejectedError(
                f"{label} failed immutable identity capture"
            ) from exc


@dataclass(frozen=True, slots=True)
class _ResolvedCodeSource:
    source_kind: str
    branch_owner: RevisionedBranchRecord
    champion_owner: StoredChampionRecord | None
    capture: EditableIdentityBytesCapture
    captured_current_code_hash: str | None
    captured_last_clean_code_hash: str | None


class HypothesisCodeSourceOwner:
    """Select and bind one immutable source for one exact leaf request."""

    __slots__ = (
        "__champion_store",
        "__generation_authority",
        "__workspace_authority",
    )

    def __init_subclass__(cls, **_kwargs: object) -> None:
        _sealed_subclass("HypothesisCodeSourceOwner")

    def __init__(
        self,
        workspace_authority: CampaignWorkspaceAuthority,
        champion_store: ConnectionScopedChampionStore,
    ) -> None:
        if type(workspace_authority) is not CampaignWorkspaceAuthority:
            raise TypeError(
                "HypothesisCodeSourceOwner requires an exact "
                "CampaignWorkspaceAuthority"
            )
        if type(champion_store) is not ConnectionScopedChampionStore:
            raise TypeError(
                "HypothesisCodeSourceOwner requires an exact "
                "ConnectionScopedChampionStore"
            )
        self.__workspace_authority = workspace_authority
        self.__champion_store = champion_store
        self.__generation_authority: _generation._AuthorityHandle | None = None

    def _install_hypothesis_generation_authority(
        self,
        authority: _generation._AuthorityHandle,
    ) -> None:
        """Install this exact owner's leaf handle once during composition."""

        if self.__generation_authority is not None:
            raise _generation.HypothesisGenerationLifecycleError(
                "HypothesisCodeSourceOwner generation authority is already installed"
            )
        _generation._require_authority(
            authority,
            role=_generation._AuthorityRole.CODE_SOURCE_OWNER,
            owner=self,
        )
        self.__generation_authority = authority

    def _require_hypothesis_generation_authority(
        self,
    ) -> _generation._AuthorityHandle:
        authority = self.__generation_authority
        if authority is None:
            raise _generation.InvalidHypothesisGenerationCapabilityError(
                "HypothesisCodeSourceOwner generation authority is not installed"
            )
        _generation._require_authority(
            authority,
            role=_generation._AuthorityRole.CODE_SOURCE_OWNER,
            owner=self,
        )
        return authority

    def _bind_hypothesis_code_source_from_snapshot(
        self,
        snapshot: _sqlite._IndependentReadSnapshot,
        request: HypothesisCodeSourceRequest,
    ) -> HypothesisCodeSource:
        """Consume one request using only its captured owner and sealed roots."""

        authority = self._require_hypothesis_generation_authority()
        if type(snapshot) is not _sqlite._IndependentReadSnapshot:
            raise _generation.InvalidHypothesisGenerationCapabilityError(
                "code-source binding requires an exact Registry read snapshot"
            )
        projection = _generation._claim_code_source_request(authority, request)
        try:
            resolved = self._resolve_from_snapshot(
                snapshot,
                projection.branch_owner,
            )
            entries = tuple(
                (
                    entry.file_path,
                    entry.content,
                    entry.sha256,
                    entry.code_identity,
                    entry.snapshot_identity,
                )
                for entry in resolved.capture.entries
            )
            source = _generation._issue_code_source(
                authority,
                request,
                source_kind=resolved.source_kind,
                selected_manifest_digest=resolved.capture.manifest_digest,
                code_hash=resolved.capture.code_hash,
                snapshot_hash=resolved.capture.snapshot_hash,
                entries=entries,
            )
        except HypothesisCodeSourceRejectedError:
            _generation._finish_code_source_request_failure(
                authority,
                request,
                rejected=True,
            )
            raise
        except BaseException as exc:
            _generation._finish_code_source_request_failure(
                authority,
                request,
                rejected=False,
            )
            if not isinstance(exc, Exception):
                raise
            raise HypothesisCodeSourceUnknownError(
                "code-source selection failed unexpectedly"
            ) from exc
        return source

    def _resolve_from_snapshot(
        self,
        snapshot: _sqlite._IndependentReadSnapshot,
        branch_owner: object,
    ) -> _ResolvedCodeSource:
        if type(branch_owner) is not RevisionedBranchRecord:
            raise HypothesisCodeSourceRejectedError(
                "code-source request has no exact durable Branch owner"
            )
        try:
            branch = branch_owner.value()
        except DurableOwnerIntegrityError as exc:
            raise HypothesisCodeSourceRejectedError(
                "captured Branch owner failed storage validation"
            ) from exc
        source_kind = _select_source_kind(branch)
        if source_kind == "base_champion":
            return self._resolve_base_champion(snapshot, branch_owner, branch)
        capture = self.__workspace_authority._capture_branch_workspace(
            branch.branch_id
        )
        if (
            capture.code_hash != branch.current_code_hash
            or capture.code_hash != branch.last_clean_code_hash
        ):
            raise HypothesisCodeSourceRejectedError(
                "verified Branch workspace differs from both captured clean hashes"
            )
        return _ResolvedCodeSource(
            source_kind="verified_branch_workspace",
            branch_owner=branch_owner,
            champion_owner=None,
            capture=capture,
            captured_current_code_hash=branch.current_code_hash,
            captured_last_clean_code_hash=branch.last_clean_code_hash,
        )

    def _resolve_base_champion(
        self,
        snapshot: _sqlite._IndependentReadSnapshot,
        branch_owner: RevisionedBranchRecord,
        branch: Branch,
    ) -> _ResolvedCodeSource:
        try:
            champion_owner = self.__champion_store._load_exact_from_snapshot(
                snapshot,
                branch.base_champion_id,
                branch.weight_revision,
            )
        except DurableOwnerIntegrityError as exc:
            raise HypothesisCodeSourceRejectedError(
                "captured base champion failed exact storage validation"
            ) from exc
        if champion_owner is None:
            raise HypothesisCodeSourceRejectedError(
                "captured base champion revision does not exist"
            )
        try:
            champion = champion_owner.value()
        except DurableOwnerIntegrityError as exc:
            raise HypothesisCodeSourceRejectedError(
                "captured base champion token failed storage validation"
            ) from exc
        if (
            champion.version != branch.base_champion_id
            or champion.weight_revision != branch.weight_revision
            or champion.code_snapshot_hash != branch.base_champion_hash
        ):
            raise HypothesisCodeSourceRejectedError(
                "captured Branch and exact base champion anchors differ"
            )
        capture = self.__workspace_authority._capture_champion_snapshot(
            champion_owner
        )
        if (
            capture.snapshot_hash != branch.base_champion_hash
            or capture.snapshot_hash != champion.code_snapshot_hash
        ):
            raise HypothesisCodeSourceRejectedError(
                "base champion bytes differ from the captured complete manifest"
            )
        return _ResolvedCodeSource(
            source_kind="base_champion",
            branch_owner=branch_owner,
            champion_owner=champion_owner,
            capture=capture,
            captured_current_code_hash=branch.current_code_hash,
            captured_last_clean_code_hash=branch.last_clean_code_hash,
        )


def _select_source_kind(branch: Branch) -> str:
    if branch.state in {BranchState.STALE, BranchState.STALE_WEIGHT_UPDATE}:
        return "base_champion"
    if branch.current_code_hash is None or branch.last_clean_code_hash is None:
        return "base_champion"
    if (
        branch.branch_code_status == "clean"
        and branch.current_code_hash == branch.last_clean_code_hash
    ):
        return "verified_branch_workspace"
    raise HypothesisCodeSourceRejectedError(
        "captured Branch has no verified hypothesis code source"
    )
