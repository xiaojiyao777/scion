"""Root-owned W3 installed verification and authorization coordination.

This module is intentionally separate from the installed service dispatcher.
It owns fixed root receipt-store capabilities and never exposes arbitrary
filesystem roots through its production API.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
from pathlib import PurePosixPath
import pwd
import re
import stat
import subprocess
from typing import Callable, TypeVar

from scion.runtime.execution.external_installation import (
    DurableReceiptDirectory,
    DirectoryIdentity,
    INSTALL_PHASES,
    InstalledAcceptance,
    LoadedManagerReceipt,
    ManagerReloadReceipt,
    MountBindingReceipt,
    MountInfoRow,
    NarrowInstallationManager,
    NarrowReloadManager,
    DirectorySnapshot,
    PublishedDirectoryReceipt,
    PublishedRegularFileReceipt,
    PublishedTreeReceipt,
    RootInstallationState,
    RootPhase,
    RootPhaseIntentReceipt,
    RootPhaseReceipt,
    SelectionReceipt,
    StartDispatchReceipt,
    StartAuthorizationReceipt,
    StartIssueReceipt,
    StartPermitOwner,
    SystemdExternalManager,
    UnitPublicationReceipt,
    acquire_loaded_manager_pair,
    apply_manager_reload as apply_systemd_manager_reload,
    apply_root_phase,
    classify_root_installation,
    parse_mountinfo_mount_id,
    parse_selected_mountinfo,
    validate_root_transaction,
)
from scion.runtime.execution.external_linux import (
    FileIdentity,
    FreshDirectorySpec,
    LinuxRootAdapter,
    MountNamespacePair,
    PinnedDirectory,
    RootDirectoryHierarchy,
    RegularPublicationSpec,
    acquire_mount_namespace_pair,
    attach_cloned_mount,
    import_root_owned_tree,
    pin_absolute_directory,
    publish_noreplace,
    reopen_imported_tree,
)
from scion.runtime.execution.launch_authority import (
    AcceptedLaunchAuthority,
    InstallationRecord,
)
from scion.runtime.execution.environment_integrity import verify_environment_content
from scion.runtime.execution.systemd_acquisition import (
    ConfiguredPairReadback,
    Systemd255Acquirer,
    parse_unit_template,
)

from .w3_candidate_gate import CandidateGateReceipt
from .w3_candidate_gate import CandidateGateClosureBundle
from .w3_candidate_gate import reverify_w3_accepted_root
from .w3_candidate_ingress import (
    CandidateGateIngressFact,
    pin_candidate_gate_ingress,
)
from .w3_environment_receipts import (
    EnvironmentRelocationReceipt,
    FilesystemLiveEnvironmentReader,
    LiveEnvironmentRehashFact,
    SubprocessEnvironmentProbeReader,
    WarehouseEnvironmentContentReceipt,
    derive_final_environment_path,
    verify_live_environment,
)
from .w3_installation import (
    SealedStoreReceipt,
    derive_candidate_paths,
    reverify_sealed_store,
)
from .w3_installed_replay import (
    RootInstalledAcceptanceAuthority,
    WarehouseW3InstalledAcceptanceBundle,
    WarehouseW3InstalledReplayInputs,
    reacquire_live_w3_prestart,
    verify_w3_installed_replay,
)
from .w3_root_selection import RootSelectedCandidateAuthority
from .w3_root_selection import (
    WarehouseW3RootSelectionReceipt,
    WarehouseW3SelectedCandidateChain,
    WarehouseW3SelectionReplayInputs,
    derive_root_selection_effect_authority_sha256,
    derive_root_staging_import_authority_sha256,
    selection_replay_inputs_from_chain,
)
from .w3_root_staging import verify_imported_w3_candidate
from .w3_root_installation import (
    WarehouseW3AuthorityPublishedReceipt,
    WarehouseW3PreStartEvidence,
    WarehouseW3ProjectionReceipt,
    WarehouseW3StagedCandidateReceipt,
    WarehouseW3StoresPublishedReceipt,
    derive_w3_authority_effect_authority_sha256,
    derive_w3_projection_effect_authority_sha256,
    derive_w3_reload_effect_authority_sha256,
    derive_w3_stores_effect_authority_sha256,
    derive_w3_units_effect_authority_sha256,
)
from .w3_start_authorization import (
    ProspectiveStartAuthorizationIntent,
    bind_start_authorization,
)
from .w3_start_gate import WarehouseW3PreStartProducerReplayInputs
from .w3_start_store import WarehouseW3InstalledStartGateBundle
from .w3_prestart_facts import (
    WAREHOUSE_W3_PRESTART_EVIDENCE_SCHEMA,
    PreStartAbsenceObservation,
    WarehouseW3DryRootReadinessReceipt,
    WarehouseW3PreStartAbsenceReceipt,
    WarehouseW3RuntimeAccountReceipt,
)

_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_BOOT_ID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-" r"[0-9a-f]{4}-[0-9a-f]{12}\Z"
)
_ACCEPTANCE_ROOT = Path("/var/lib/scion/acceptances/w3")
_AUTHORITY_ROOT = Path("/var/lib/scion/authorities/w3")
_ENVIRONMENT_ROOT = Path("/var/lib/scion/environments/w3")
_IMPORT_ROOT = Path("/var/lib/scion/imports/w3")
_INSTALLATION_ROOT = Path("/var/lib/scion/installations/w3")
_PROJECTION_ROOT = Path("/var/lib/scion/projections/w3")
_RUN_ROOT = Path("/var/lib/scion/runs/w3")
_SEALED_ROOT = Path("/var/lib/scion/sealed/w3")
_SELECTION_ROOT = Path("/var/lib/scion/selections/w3")
_SCION_ROOT_PARENT = Path("/var/lib")
_SYSTEMD_UNIT_ROOT = Path("/etc/systemd/system")
_START_AUTHORIZATION_LEAF = "START_AUTHORIZED"
_START_GATE_BUNDLE_LEAF = "START_GATE_INPUTS.v1.json"
_START_SPEND_LEAVES = (
    "START_DISPATCH_UNKNOWN",
    "START_ISSUED",
    "START_REJECTED",
    "START_RETURNED",
)
_MAX_RECEIPT_BYTES = 4 * 1024 * 1024
_INSTALLED_REPLAY_LEAF = "INSTALLED_REPLAY.v1.json"
_INSTALLED_ACCEPTANCE_LEAF = "INSTALLATION_ACCEPTED"
_CONFIGURED_PAIR_READBACK_LEAF = "CONFIGURED_PAIR_READBACK"
_ENVIRONMENT_RELOCATION_LEAF = "ENVIRONMENT_RELOCATION"
_LOADED_MANAGER_LEAF = "LOADED_MANAGER"
_EffectReceipt = TypeVar("_EffectReceipt")


def _phase_prefix(index: int, phase: RootPhase) -> str:
    return f"{index:02d}-{phase.value.lower().replace('_', '-')}"


_PHASE_INTENT_LEAVES = tuple(
    f"{_phase_prefix(index, phase)}.intent.v1.json"
    for index, phase in enumerate(INSTALL_PHASES)
)
_PHASE_COMMIT_LEAVES = tuple(
    f"{_phase_prefix(index, phase)}.commit.v2.json"
    for index, phase in enumerate(INSTALL_PHASES)
)
_PHASE_EFFECT_LEAVES = tuple(phase.value for phase in INSTALL_PHASES)
_INSTALL_LEDGER_LEAVES = frozenset(
    {
        *_PHASE_INTENT_LEAVES,
        *_PHASE_COMMIT_LEAVES,
        *_PHASE_EFFECT_LEAVES,
        _CONFIGURED_PAIR_READBACK_LEAF,
        _ENVIRONMENT_RELOCATION_LEAF,
        _INSTALLED_ACCEPTANCE_LEAF,
        _INSTALLED_REPLAY_LEAF,
        _LOADED_MANAGER_LEAF,
    }
)


class WarehouseW3RootCoordinatorError(RuntimeError):
    """The fixed installed W3 ledger cannot authorize the requested action."""


@dataclass(frozen=True, slots=True)
class WarehouseW3RootInstallationInspection:
    """Fail-closed read-only classification of one fixed root phase ledger."""

    launch_id: str
    state: RootInstallationState
    committed_phase_count: int
    pending_phase: RootPhase | None
    installed_replay_sha256: str | None

    def __post_init__(self) -> None:
        _launch_id(self.launch_id)
        if type(self.state) is not RootInstallationState:
            raise TypeError("state must be exact RootInstallationState")
        if (
            type(self.committed_phase_count) is not int
            or self.committed_phase_count < 0
            or self.committed_phase_count > len(INSTALL_PHASES)
        ):
            raise TypeError("committed phase count differs")
        if self.pending_phase is not None and type(self.pending_phase) is not RootPhase:
            raise TypeError("pending phase must be exact RootPhase or None")
        if self.installed_replay_sha256 is not None and (
            type(self.installed_replay_sha256) is not str
            or _SHA256_RE.fullmatch(self.installed_replay_sha256) is None
        ):
            raise TypeError("installed replay SHA-256 differs")


def _launch_id(value: object) -> str:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        raise WarehouseW3RootCoordinatorError("W3 root coordinator launch id differs")
    return value


def _require_root() -> None:
    if os.geteuid() != 0:
        raise PermissionError("W3 root coordinator requires effective UID zero")


def _signature(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_uid,
        value.st_gid,
        value.st_nlink,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _directory_snapshot(identity: FileIdentity) -> DirectorySnapshot:
    if type(identity) is not FileIdentity or not stat.S_ISDIR(identity.mode):
        raise WarehouseW3RootCoordinatorError(
            "root selection directory identity differs"
        )
    return DirectorySnapshot(
        device=identity.device,
        inode=identity.inode,
        mode=stat.S_IMODE(identity.mode),
        uid=identity.uid,
        gid=identity.gid,
        nlink=identity.link_count,
    )


def _w3_root_layout_specs(
    *,
    uid: int,
    gid: int,
) -> tuple[FreshDirectorySpec, ...]:
    roots = (
        "acceptances",
        "authorities",
        "environments",
        "imports",
        "installations",
        "projections",
        "runs",
        "sealed",
        "selections",
    )
    return (
        FreshDirectorySpec(
            role="scion",
            parent_role=None,
            leaf="scion",
            mode=0o755,
            uid=uid,
            gid=gid,
        ),
        *(
            FreshDirectorySpec(
                role=root,
                parent_role="scion",
                leaf=root,
                mode=0o755,
                uid=uid,
                gid=gid,
            )
            for root in roots
        ),
        *(
            FreshDirectorySpec(
                role=f"{root}-w3",
                parent_role=root,
                leaf="w3",
                mode=0o755,
                uid=uid,
                gid=gid,
            )
            for root in roots
        ),
    )


def _initialize_w3_root_layout_at(
    parent_path: Path,
    *,
    uid: int,
    gid: int,
    require_root_owner: bool,
) -> None:
    """Create the fixed root hierarchy once; every collision is a hold."""

    if not isinstance(parent_path, Path) or not parent_path.is_absolute():
        raise TypeError("root layout parent must be one absolute Path")
    if type(require_root_owner) is not bool:
        raise TypeError("require_root_owner must be exact bool")
    parent = pin_absolute_directory(str(parent_path))
    try:
        if require_root_owner:
            _require_root_owned_chain(parent)
            if uid != 0 or gid != 0:
                raise WarehouseW3RootCoordinatorError(
                    "production root layout owner differs"
                )
        with RootDirectoryHierarchy.create_fresh(
            parent,
            _w3_root_layout_specs(uid=uid, gid=gid),
        ):
            pass
    except Exception as exc:
        raise WarehouseW3RootCoordinatorError(
            "fresh W3 root layout is a permanent hold"
        ) from exc
    finally:
        parent.close()


def _initialize_w3_root_layout() -> None:
    _require_root()
    _initialize_w3_root_layout_at(
        _SCION_ROOT_PARENT,
        uid=0,
        gid=0,
        require_root_owner=True,
    )


def _verify_w3_root_layout_at(
    parent_path: Path,
    *,
    uid: int,
    gid: int,
    require_root_owner: bool,
) -> None:
    """Read-only reopen of every fixed W3 root parent after bootstrap."""

    if not isinstance(parent_path, Path) or not parent_path.is_absolute():
        raise TypeError("root layout parent must be one absolute Path")
    if type(require_root_owner) is not bool:
        raise TypeError("require_root_owner must be exact bool")
    for relative in (
        "scion",
        *(
            f"scion/{root}"
            for root in (
                "acceptances",
                "authorities",
                "environments",
                "imports",
                "installations",
                "projections",
                "runs",
                "sealed",
                "selections",
            )
        ),
        *(
            f"scion/{root}/w3"
            for root in (
                "acceptances",
                "authorities",
                "environments",
                "imports",
                "installations",
                "projections",
                "runs",
                "sealed",
                "selections",
            )
        ),
    ):
        directory = pin_absolute_directory(str(parent_path / relative))
        try:
            identity = FileIdentity.from_stat(os.fstat(directory.fd))
            if require_root_owner:
                _require_root_owned_chain(directory)
            else:
                directory.revalidate_mutable_leaf()
            if (
                identity.uid != uid
                or identity.gid != gid
                or stat.S_IMODE(identity.mode) != 0o755
            ):
                raise WarehouseW3RootCoordinatorError(
                    "fixed W3 root layout identity differs"
                )
        finally:
            directory.close()


def _ensure_w3_root_layout() -> None:
    """Create only from total absence, otherwise require the complete layout."""

    _require_root()
    try:
        metadata = os.stat(
            _SCION_ROOT_PARENT / "scion",
            follow_symlinks=False,
        )
    except FileNotFoundError:
        _initialize_w3_root_layout()
        return
    if not stat.S_ISDIR(metadata.st_mode):
        raise WarehouseW3RootCoordinatorError(
            "fixed W3 root layout is a permanent hold"
        )
    try:
        _verify_w3_root_layout_at(
            _SCION_ROOT_PARENT,
            uid=0,
            gid=0,
            require_root_owner=True,
        )
    except Exception as exc:
        raise WarehouseW3RootCoordinatorError(
            "fixed W3 root layout is a permanent hold"
        ) from exc


def _require_root_owned_chain(directory: PinnedDirectory) -> None:
    directory.revalidate_mutable_leaf()
    current = FileIdentity.from_stat(os.fstat(directory.fd))
    if (
        any(
            component.identity.uid != 0
            or component.identity.gid != 0
            or stat.S_IMODE(component.identity.mode) & 0o022
            for component in directory.components
        )
        or current.uid != 0
        or current.gid != 0
        or stat.S_IMODE(current.mode) & 0o022
    ):
        raise WarehouseW3RootCoordinatorError("fixed start authority ownership differs")


def _acquire_fixed_receipt(
    directory: PinnedDirectory,
    leaf: str,
    *,
    maximum: int,
    require_root_owner: bool,
) -> tuple[int, tuple[int, ...], bytes]:
    descriptor = os.open(
        leaf,
        os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
        dir_fd=directory.fd,
    )
    try:
        before = os.fstat(descriptor)
        named = os.stat(
            leaf,
            dir_fd=directory.fd,
            follow_symlinks=False,
        )
        if (
            not stat.S_ISREG(before.st_mode)
            or stat.S_IMODE(before.st_mode) != 0o444
            or before.st_nlink != 1
            or (require_root_owner and (before.st_uid != 0 or before.st_gid != 0))
            or FileIdentity.from_stat(before) != FileIdentity.from_stat(named)
        ):
            raise WarehouseW3RootCoordinatorError(f"fixed {leaf} identity differs")
        chunks: list[bytes] = []
        total = 0
        while True:
            remaining = maximum + 1 - total
            if remaining <= 0:
                raise WarehouseW3RootCoordinatorError(
                    f"fixed {leaf} exceeds its byte limit"
                )
            chunk = os.read(descriptor, min(64 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
        after = os.fstat(descriptor)
        named_after = os.stat(
            leaf,
            dir_fd=directory.fd,
            follow_symlinks=False,
        )
        identity = _signature(after)
        if (
            _signature(before) != identity
            or _signature(named_after) != identity
            or total != after.st_size
        ):
            raise WarehouseW3RootCoordinatorError(f"fixed {leaf} drifted")
        return descriptor, identity, b"".join(chunks)
    except Exception:
        os.close(descriptor)
        raise


def _partial_inspection(
    launch_id: str,
    *,
    committed_phase_count: int = 0,
    pending_phase: RootPhase | None = None,
) -> WarehouseW3RootInstallationInspection:
    return WarehouseW3RootInstallationInspection(
        launch_id=launch_id,
        state=RootInstallationState.PARTIAL_HOLD,
        committed_phase_count=committed_phase_count,
        pending_phase=pending_phase,
        installed_replay_sha256=None,
    )


def _read_install_ledger(
    install: PinnedDirectory,
    *,
    launch_id: str,
    require_root_owner: bool,
) -> WarehouseW3RootInstallationInspection:
    """Inspect one already pinned install directory without any mutation."""

    if type(install) is not PinnedDirectory:
        raise TypeError("install must be exact PinnedDirectory")
    if type(require_root_owner) is not bool:
        raise TypeError("require_root_owner must be exact bool")
    normalized_launch_id = _launch_id(launch_id)
    try:
        install.revalidate_mutable_leaf()
        install_identity = FileIdentity.from_stat(os.fstat(install.fd))
        if (
            not stat.S_ISDIR(install_identity.mode)
            or stat.S_IMODE(install_identity.mode) not in {0o555, 0o755}
            or (
                require_root_owner
                and (
                    any(
                        component.identity.uid != 0
                        or component.identity.gid != 0
                        or stat.S_IMODE(component.identity.mode) & 0o022
                        for component in install.components
                    )
                    or install_identity.uid != 0
                    or install_identity.gid != 0
                    or stat.S_IMODE(install_identity.mode) & 0o022
                )
            )
        ):
            return _partial_inspection(normalized_launch_id)
        names = tuple(sorted(os.listdir(install.fd), key=os.fsencode))
        if any(type(name) is not str for name in names) or not set(names).issubset(
            _INSTALL_LEDGER_LEAVES
        ):
            return _partial_inspection(normalized_launch_id)

        intents: list[RootPhaseIntentReceipt] = []
        receipts: list[RootPhaseReceipt] = []
        for leaf in _PHASE_INTENT_LEAVES:
            if leaf not in names:
                continue
            descriptor, _identity, raw = _acquire_fixed_receipt(
                install,
                leaf,
                maximum=_MAX_RECEIPT_BYTES,
                require_root_owner=require_root_owner,
            )
            os.close(descriptor)
            intents.append(RootPhaseIntentReceipt.from_bytes(raw))
        for leaf in _PHASE_COMMIT_LEAVES:
            if leaf not in names:
                continue
            descriptor, _identity, raw = _acquire_fixed_receipt(
                install,
                leaf,
                maximum=_MAX_RECEIPT_BYTES,
                require_root_owner=require_root_owner,
            )
            os.close(descriptor)
            receipts.append(RootPhaseReceipt.from_bytes(raw))
        state = classify_root_installation(tuple(intents), tuple(receipts))
        committed_count = len(receipts)
        pending = intents[-1].phase if len(intents) == len(receipts) + 1 else None
        if state is not RootInstallationState.ACCEPTED:
            return _partial_inspection(
                normalized_launch_id,
                committed_phase_count=committed_count,
                pending_phase=pending,
            )
        expected_names = _INSTALL_LEDGER_LEAVES
        if (
            frozenset(names) != expected_names
            or stat.S_IMODE(install_identity.mode) != 0o555
        ):
            return _partial_inspection(
                normalized_launch_id,
                committed_phase_count=committed_count,
            )
        descriptor, _identity, raw = _acquire_fixed_receipt(
            install,
            _INSTALLED_REPLAY_LEAF,
            maximum=512 * 1024 * 1024,
            require_root_owner=require_root_owner,
        )
        os.close(descriptor)
        bundle = WarehouseW3InstalledAcceptanceBundle.from_bytes(raw)
        chain = verify_w3_installed_replay(
            bundle.installed_replay_inputs,
            bundle.selection_replay_inputs,
        )
        effect_producers = (
            chain.selected_candidate.staged_candidate,
            chain.selected_candidate.root_selection,
            chain.stores_published,
            chain.authority_published,
            chain.projection,
            chain.unit_publication,
            chain.manager_reload,
            chain.prestart_evidence,
            chain.installed_acceptance,
        )
        for leaf, producer in zip(
            _PHASE_EFFECT_LEAVES,
            effect_producers,
            strict=True,
        ):
            descriptor, _identity, effect_raw = _acquire_fixed_receipt(
                install,
                leaf,
                maximum=512 * 1024 * 1024,
                require_root_owner=require_root_owner,
            )
            os.close(descriptor)
            if effect_raw != producer.raw:
                return _partial_inspection(
                    normalized_launch_id,
                    committed_phase_count=committed_count,
                )
        for leaf, producer in (
            (_CONFIGURED_PAIR_READBACK_LEAF, chain.configured_pair_readback),
            (_ENVIRONMENT_RELOCATION_LEAF, chain.environment_relocation),
            (_LOADED_MANAGER_LEAF, chain.loaded_manager),
        ):
            descriptor, _identity, subordinate_raw = _acquire_fixed_receipt(
                install,
                leaf,
                maximum=512 * 1024 * 1024,
                require_root_owner=require_root_owner,
            )
            os.close(descriptor)
            if subordinate_raw != producer.raw:
                return _partial_inspection(
                    normalized_launch_id,
                    committed_phase_count=committed_count,
                )
        descriptor, _identity, installed_raw = _acquire_fixed_receipt(
            install,
            _INSTALLED_ACCEPTANCE_LEAF,
            maximum=_MAX_RECEIPT_BYTES,
            require_root_owner=require_root_owner,
        )
        os.close(descriptor)
        top_level_installed = InstalledAcceptance.from_bytes(installed_raw)
        if (
            chain.installed_acceptance.launch_id != normalized_launch_id
            or top_level_installed != chain.installed_acceptance
            or chain.phase_intents != tuple(intents)
            or chain.phase_receipts != tuple(receipts)
        ):
            return _partial_inspection(
                normalized_launch_id,
                committed_phase_count=committed_count,
            )
        install.revalidate_mutable_leaf()
        if tuple(sorted(os.listdir(install.fd), key=os.fsencode)) != names:
            return _partial_inspection(
                normalized_launch_id,
                committed_phase_count=committed_count,
            )
        return WarehouseW3RootInstallationInspection(
            launch_id=normalized_launch_id,
            state=RootInstallationState.ACCEPTED,
            committed_phase_count=len(INSTALL_PHASES),
            pending_phase=None,
            installed_replay_sha256=bundle.raw_sha256,
        )
    except Exception:
        return _partial_inspection(normalized_launch_id)


def _inspect_w3_root_installation_at(
    acceptance_root: Path,
    launch_id: str,
    *,
    require_root_owner: bool,
) -> WarehouseW3RootInstallationInspection:
    """Test seam and fixed-root implementation for fail-closed classification."""

    if not isinstance(acceptance_root, Path) or not acceptance_root.is_absolute():
        raise TypeError("acceptance_root must be one absolute Path")
    normalized_launch_id = _launch_id(launch_id)
    launch_root = acceptance_root / normalized_launch_id
    try:
        metadata = os.stat(launch_root, follow_symlinks=False)
    except FileNotFoundError:
        return WarehouseW3RootInstallationInspection(
            launch_id=normalized_launch_id,
            state=RootInstallationState.ABSENT,
            committed_phase_count=0,
            pending_phase=None,
            installed_replay_sha256=None,
        )
    except OSError:
        return _partial_inspection(normalized_launch_id)
    if not stat.S_ISDIR(metadata.st_mode):
        return _partial_inspection(normalized_launch_id)
    try:
        launch = pin_absolute_directory(str(launch_root))
    except Exception:
        return _partial_inspection(normalized_launch_id)
    try:
        launch.revalidate_mutable_leaf()
        launch_identity = FileIdentity.from_stat(os.fstat(launch.fd))
        names = tuple(sorted(os.listdir(launch.fd), key=os.fsencode))
        if (
            stat.S_IMODE(launch_identity.mode) != 0o755
            or (
                require_root_owner
                and (
                    launch_identity.uid != 0
                    or launch_identity.gid != 0
                    or stat.S_IMODE(launch_identity.mode) & 0o022
                )
            )
            or any(name not in {"install", "start", "terminal"} for name in names)
            or "install" not in names
        ):
            return _partial_inspection(normalized_launch_id)
        install = launch.open_child_directory("install")
        try:
            inspection = _read_install_ledger(
                install,
                launch_id=normalized_launch_id,
                require_root_owner=require_root_owner,
            )
        finally:
            install.close()
        if inspection.state is RootInstallationState.ACCEPTED:
            if frozenset(names) != frozenset({"install", "start", "terminal"}):
                return _partial_inspection(
                    normalized_launch_id,
                    committed_phase_count=inspection.committed_phase_count,
                )
            for role in ("start", "terminal"):
                child = launch.open_child_directory(role)
                try:
                    identity = FileIdentity.from_stat(os.fstat(child.fd))
                    if (
                        not stat.S_ISDIR(identity.mode)
                        or stat.S_IMODE(identity.mode) not in {0o555, 0o755}
                        or (
                            require_root_owner
                            and (
                                identity.uid != 0
                                or identity.gid != 0
                                or stat.S_IMODE(identity.mode) & 0o022
                            )
                        )
                    ):
                        return _partial_inspection(
                            normalized_launch_id,
                            committed_phase_count=inspection.committed_phase_count,
                        )
                finally:
                    child.close()
        return inspection
    except Exception:
        return _partial_inspection(normalized_launch_id)
    finally:
        launch.close()


def inspect_w3_root_installation(
    launch_id: str,
) -> WarehouseW3RootInstallationInspection:
    """Classify the fixed root ledger as ABSENT, PARTIAL_HOLD, or ACCEPTED."""

    _require_root()
    return _inspect_w3_root_installation_at(
        _ACCEPTANCE_ROOT,
        _launch_id(launch_id),
        require_root_owner=True,
    )


def _close_w3_root_selection_prefix(
    *,
    closure: CandidateGateClosureBundle,
    ingress: CandidateGateIngressFact,
    staging_leaf: str,
    writer: DurableReceiptDirectory,
    import_and_verify: Callable[[], WarehouseW3StagedCandidateReceipt],
    build_selection: Callable[
        [WarehouseW3StagedCandidateReceipt],
        WarehouseW3RootSelectionReceipt,
    ],
    publish_selection: Callable[[WarehouseW3RootSelectionReceipt], bytes],
) -> tuple[
    WarehouseW3SelectedCandidateChain,
    WarehouseW3SelectionReplayInputs,
]:
    """Close K0/K1 with both external effects strictly after durable intents."""

    _require_root()
    if type(closure) is not CandidateGateClosureBundle:
        raise TypeError("closure must be exact CandidateGateClosureBundle")
    if type(ingress) is not CandidateGateIngressFact:
        raise TypeError("ingress must be exact CandidateGateIngressFact")
    if type(writer) is not DurableReceiptDirectory:
        raise TypeError("writer must be exact DurableReceiptDirectory")
    if not all(
        callable(callback)
        for callback in (import_and_verify, build_selection, publish_selection)
    ):
        raise TypeError("root selection phase callbacks must be callable")
    launch_id = _launch_id(closure.gate.launch_id)
    k0_authority = derive_root_staging_import_authority_sha256(
        closure,
        ingress,
        staging_leaf=staging_leaf,
        target_uid=0,
        target_gid=0,
    )
    observed: dict[str, object] = {}

    def import_effect() -> None:
        staged = import_and_verify()
        if (
            type(staged) is not WarehouseW3StagedCandidateReceipt
            or staged.launch_id != launch_id
            or staged.candidate_gate_ingress != ingress
            or staged.root_staging_verification.candidate_gate_closure != closure
            or staged.tree_import.staging_leaf != staging_leaf
            or staged.tree_import.target_uid != 0
            or staged.tree_import.target_gid != 0
        ):
            raise WarehouseW3RootCoordinatorError(
                "root staging producer differs from K0 intent"
            )
        writer.write_no_replace(
            RootPhase.ROOT_STAGING_IMPORTED.value,
            staged.raw,
        )
        if writer.read(RootPhase.ROOT_STAGING_IMPORTED.value) != staged.raw:
            raise WarehouseW3RootCoordinatorError(
                "root staging effect differs after reopen"
            )
        observed["staged"] = staged

    k0_intent, k0_receipt = apply_root_phase(
        launch_id=launch_id,
        phase=RootPhase.ROOT_STAGING_IMPORTED,
        effect_authority_sha256=k0_authority,
        prior_intents=(),
        prior_receipts=(),
        writer=writer,
        apply_effect=import_effect,
        reopen_effect=lambda: writer.read(RootPhase.ROOT_STAGING_IMPORTED.value),
    )
    staged = observed.get("staged")
    if (
        type(staged) is not WarehouseW3StagedCandidateReceipt
        or k0_receipt.effect_sha256 != staged.raw_sha256
    ):
        raise WarehouseW3RootCoordinatorError("K0 root staging receipt differs")

    root_selection = build_selection(staged)
    if (
        type(root_selection) is not WarehouseW3RootSelectionReceipt
        or root_selection.staged_candidate != staged
        or root_selection.launch_id != launch_id
    ):
        raise WarehouseW3RootCoordinatorError(
            "root selection producer differs before K1 intent"
        )
    k1_authority = derive_root_selection_effect_authority_sha256(root_selection)

    def select_effect() -> None:
        reopened = publish_selection(root_selection)
        if type(reopened) is not bytes or reopened != root_selection.raw:
            raise WarehouseW3RootCoordinatorError("root selection publication differs")
        writer.write_no_replace(
            RootPhase.CANDIDATE_SELECTED.value,
            reopened,
        )
        if writer.read(RootPhase.CANDIDATE_SELECTED.value) != reopened:
            raise WarehouseW3RootCoordinatorError(
                "root selection effect differs after reopen"
            )

    k1_intent, k1_receipt = apply_root_phase(
        launch_id=launch_id,
        phase=RootPhase.CANDIDATE_SELECTED,
        effect_authority_sha256=k1_authority,
        prior_intents=(k0_intent,),
        prior_receipts=(k0_receipt,),
        writer=writer,
        apply_effect=select_effect,
        reopen_effect=lambda: writer.read(RootPhase.CANDIDATE_SELECTED.value),
    )
    if k1_receipt.effect_sha256 != root_selection.raw_sha256:
        raise WarehouseW3RootCoordinatorError("K1 root selection receipt differs")
    chain = WarehouseW3SelectedCandidateChain(
        closure=closure,
        ingress=ingress,
        tree_import=staged.tree_import,
        root_staging_verification=staged.root_staging_verification,
        staged_candidate=staged,
        generic_selection=root_selection.selection,
        root_selection=root_selection,
        root_staging_intent=k0_intent,
        root_staging_receipt=k0_receipt,
        candidate_selected_intent=k1_intent,
        candidate_selected_receipt=k1_receipt,
    )
    replay_inputs = selection_replay_inputs_from_chain(chain)
    return chain, replay_inputs


def begin_w3_root_installation(
    candidate_root: Path,
) -> tuple[
    "WarehouseW3InstallPhaseLedger",
    WarehouseW3SelectionReplayInputs,
]:
    """Import, root-select, and open the unique K0/K1 installation ledger."""

    _require_root()
    if not isinstance(candidate_root, Path) or not candidate_root.is_absolute():
        raise TypeError("candidate_root must be one absolute Path")
    with pin_candidate_gate_ingress(candidate_root) as ingress:
        ingress.revalidate()
        gate = ingress.gate
        launch_id = _launch_id(gate.launch_id)
        if (
            _inspect_w3_root_installation_at(
                _ACCEPTANCE_ROOT,
                launch_id,
                require_root_owner=True,
            ).state
            is not RootInstallationState.ABSENT
        ):
            raise WarehouseW3RootCoordinatorError(
                "root installation launch slot is not absent"
            )
        _ensure_w3_root_layout()
        candidate_paths = derive_candidate_paths(
            candidate_root.parent,
            gate.selection_key,
        )
        if candidate_paths.candidate_root != candidate_root:
            raise WarehouseW3RootCoordinatorError(
                "candidate path differs from its selection key"
            )
        source_selection = pin_absolute_directory(
            str(candidate_paths.selection_directory)
        )
        import_parent = pin_absolute_directory(str(_IMPORT_ROOT))
        selection_parent = pin_absolute_directory(str(_SELECTION_ROOT))
        quarantine: PinnedDirectory | None = None
        writer: DurableReceiptDirectory | None = None
        selection_writer: DurableReceiptDirectory | None = None
        authority: RootSelectedCandidateAuthority | None = None
        quarantine_started = False
        try:
            _require_root_owned_chain(import_parent)
            _require_root_owned_chain(selection_parent)
            for parent in (import_parent, selection_parent):
                identity = FileIdentity.from_stat(os.fstat(parent.fd))
                if stat.S_IMODE(identity.mode) != 0o755:
                    raise WarehouseW3RootCoordinatorError(
                        "fixed W3 root parent mode differs"
                    )
            source_selection.revalidate()
            source_selection_identity = FileIdentity.from_stat(
                os.fstat(source_selection.fd)
            )
            if (
                not stat.S_ISDIR(source_selection_identity.mode)
                or stat.S_IMODE(source_selection_identity.mode) != 0o555
                or source_selection_identity.uid == 0
                or source_selection_identity.gid == 0
                or tuple(sorted(os.listdir(source_selection.fd), key=os.fsencode))
                != ("committed.v1.json", "intent.v1.json")
            ):
                raise WarehouseW3RootCoordinatorError(
                    "source candidate selection authority differs"
                )
            intent_descriptor, intent_identity, source_intent_raw = (
                _acquire_fixed_receipt(
                    source_selection,
                    "intent.v1.json",
                    maximum=_MAX_RECEIPT_BYTES,
                    require_root_owner=False,
                )
            )
            os.close(intent_descriptor)
            commit_descriptor, commit_identity, source_commit_raw = (
                _acquire_fixed_receipt(
                    source_selection,
                    "committed.v1.json",
                    maximum=_MAX_RECEIPT_BYTES,
                    require_root_owner=False,
                )
            )
            os.close(commit_descriptor)
            if any(
                identity.uid != source_selection_identity.uid
                or identity.gid != source_selection_identity.gid
                for identity in (intent_identity, commit_identity)
            ):
                raise WarehouseW3RootCoordinatorError(
                    "source selection receipt ownership differs"
                )
            source_selection.revalidate()
            quarantine_leaf = (
                ingress.closure.candidate_verification.candidate_receipt_sha256
            )
            _launch_id(quarantine_leaf)
            for parent, leaf, label in (
                (import_parent, quarantine_leaf, "root quarantine"),
                (
                    selection_parent,
                    f"{gate.selection_key}.json",
                    "root selection",
                ),
            ):
                try:
                    os.stat(
                        leaf,
                        dir_fd=parent.fd,
                        follow_symlinks=False,
                    )
                except FileNotFoundError:
                    pass
                else:
                    raise WarehouseW3RootCoordinatorError(f"{label} slot is not absent")
            quarantine_started = True
            os.mkdir(quarantine_leaf, 0o700, dir_fd=import_parent.fd)
            quarantine_fd = os.open(
                quarantine_leaf,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=import_parent.fd,
            )
            try:
                os.fchown(quarantine_fd, 0, 0)
                os.fchmod(quarantine_fd, 0o755)
                os.fsync(quarantine_fd)
                os.fsync(import_parent.fd)
            finally:
                os.close(quarantine_fd)
            quarantine = import_parent.open_child_directory(quarantine_leaf)
            _require_root_owned_chain(quarantine)
            writer = DurableReceiptDirectory(
                Path(quarantine.path),
                require_root=True,
            )
            selection_writer = DurableReceiptDirectory(
                _SELECTION_ROOT,
                require_root=True,
            )

            def import_and_verify() -> WarehouseW3StagedCandidateReceipt:
                ingress.revalidate()
                source_selection.revalidate()
                imported = import_root_owned_tree(
                    ingress.candidate,
                    quarantine,
                    "candidate",
                )
                verification = verify_imported_w3_candidate(
                    ingress,
                    quarantine,
                    imported,
                )
                staged = WarehouseW3StagedCandidateReceipt.create(
                    candidate_gate=gate,
                    candidate_gate_ingress=ingress.fact,
                    tree_import=imported,
                    root_staging_verification=verification,
                )
                ingress.revalidate()
                source_selection.revalidate()
                return staged

            def build_selection(
                staged: WarehouseW3StagedCandidateReceipt,
            ) -> WarehouseW3RootSelectionReceipt:
                verification = staged.root_staging_verification
                if (
                    verification.selection_intent.raw != source_intent_raw
                    or verification.selection_commit.raw != source_commit_raw
                ):
                    raise WarehouseW3RootCoordinatorError(
                        "source selection bytes differ from imported candidate"
                    )
                generic = SelectionReceipt.create(
                    selection_key=gate.selection_key,
                    launch_id=launch_id,
                    nonce=gate.nonce,
                    authority_sha256=gate.authority_sha256,
                    candidate_sha256=gate.raw_sha256,
                    preparation_intent_sha256=(
                        verification.selection_intent.raw_sha256
                    ),
                    preparation_commit_sha256=(
                        verification.selection_commit.raw_sha256
                    ),
                    import_receipt_sha256=staged.tree_import.raw_sha256,
                    imported_staging_aggregate_sha256=(staged.tree_import.tree_sha256),
                    source_candidate_identity=_directory_snapshot(
                        ingress.fact.candidate_identity
                    ),
                    source_selection_identity=_directory_snapshot(
                        source_selection_identity
                    ),
                )
                return WarehouseW3RootSelectionReceipt.create(
                    selection=generic,
                    staged_candidate=staged,
                )

            def publish_selection(
                root_selection: WarehouseW3RootSelectionReceipt,
            ) -> bytes:
                leaf = f"{root_selection.selection_key}.json"
                selection_writer.write_no_replace(leaf, root_selection.raw)
                return selection_writer.read(leaf)

            chain, replay_inputs = _close_w3_root_selection_prefix(
                closure=ingress.closure,
                ingress=ingress.fact,
                staging_leaf="candidate",
                writer=writer,
                import_and_verify=import_and_verify,
                build_selection=build_selection,
                publish_selection=publish_selection,
            )
            writer.close()
            writer = None
            selection_writer.close()
            selection_writer = None
            expected_quarantine_names = tuple(
                sorted(
                    (
                        "candidate",
                        _PHASE_INTENT_LEAVES[0],
                        _PHASE_COMMIT_LEAVES[0],
                        _PHASE_EFFECT_LEAVES[0],
                        _PHASE_INTENT_LEAVES[1],
                        _PHASE_COMMIT_LEAVES[1],
                        _PHASE_EFFECT_LEAVES[1],
                    ),
                    key=os.fsencode,
                )
            )
            if (
                tuple(sorted(os.listdir(quarantine.fd), key=os.fsencode))
                != expected_quarantine_names
            ):
                raise WarehouseW3RootCoordinatorError(
                    "root quarantine inventory differs"
                )
            os.fchmod(quarantine.fd, 0o555)
            os.fsync(quarantine.fd)
            os.fsync(import_parent.fd)
            ingress.revalidate()
            source_selection.revalidate()
            authority = RootSelectedCandidateAuthority._acquire_from_parent(
                selection_parent,
                replay_inputs,
                require_root_owner=True,
            )
            ledger = WarehouseW3InstallPhaseLedger.create(authority)
            authority = None
            return ledger, replay_inputs
        except Exception as exc:
            if quarantine_started:
                raise WarehouseW3RootCoordinatorError(
                    "root candidate import or selection is a permanent hold"
                ) from exc
            raise
        finally:
            if authority is not None:
                authority.close()
            if selection_writer is not None:
                selection_writer.close()
            if writer is not None:
                writer.close()
            if quarantine is not None:
                quarantine.close()
            selection_parent.close()
            import_parent.close()
            source_selection.close()


def _publish_w3_selected_stores(
    selected: WarehouseW3SelectedCandidateChain,
    *,
    persist_relocation: Callable[[bytes], bytes],
) -> WarehouseW3StoresPublishedReceipt:
    """Publish and independently reopen the two immutable candidate stores."""

    _require_root()
    if type(selected) is not WarehouseW3SelectedCandidateChain:
        raise TypeError("selected must be exact WarehouseW3SelectedCandidateChain")
    if not callable(persist_relocation):
        raise TypeError("persist_relocation must be callable")
    closure = selected.closure
    verification = selected.root_staging_verification
    gate = closure.gate
    authority = verification.authority
    installation = verification.installation
    sealed_store = verification.sealed_store_receipt
    environment_content = closure.semantic_environment
    sealed_path = _SEALED_ROOT / installation.manifest_sha256
    environment_path = derive_final_environment_path(environment_content)
    if (
        Path(installation.sealed_root) != sealed_path
        or Path(installation.environment_root) != environment_path
        or sealed_path.parent != _SEALED_ROOT
        or environment_path.parent != _ENVIRONMENT_ROOT
    ):
        raise WarehouseW3RootCoordinatorError(
            "selected store destination differs from the fixed W3 layout"
        )
    quarantine_leaf = closure.candidate_verification.candidate_receipt_sha256
    _launch_id(quarantine_leaf)
    quarantine = pin_absolute_directory(str(_IMPORT_ROOT / quarantine_leaf))
    candidate = quarantine.open_child_directory(selected.tree_import.staging_leaf)
    sealed_parent = pin_absolute_directory(str(_SEALED_ROOT))
    environment_parent = pin_absolute_directory(str(_ENVIRONMENT_ROOT))
    candidate_environment: PinnedDirectory | None = None
    final_sealed: PinnedDirectory | None = None
    final_environment: PinnedDirectory | None = None
    try:
        for directory in (
            quarantine,
            candidate,
            sealed_parent,
            environment_parent,
        ):
            _require_root_owned_chain(directory)
        if (
            reopen_imported_tree(quarantine, selected.tree_import)
            != selected.tree_import
        ):
            raise WarehouseW3RootCoordinatorError(
                "selected imported candidate differs before store publication"
            )
        candidate_environment = candidate.open_child_directory("environment")
        candidate_environment_path = Path(candidate_environment.path)
        probe_reader = SubprocessEnvironmentProbeReader()
        candidate_probe = probe_reader.probe(
            candidate_environment_path,
            phase="candidate",
            content_receipt=environment_content,
        )
        candidate_environment.revalidate()
        candidate_environment.close()
        candidate_environment = None

        adapter = LinuxRootAdapter()
        publish_noreplace(
            adapter,
            source_parent_fd=candidate.fd,
            source_leaf="sealed-store",
            destination_parent_fd=sealed_parent.fd,
            destination_leaf=sealed_path.name,
        )
        publish_noreplace(
            adapter,
            source_parent_fd=candidate.fd,
            source_leaf="environment",
            destination_parent_fd=environment_parent.fd,
            destination_leaf=environment_path.name,
        )
        candidate.revalidate_mutable_leaf()
        sealed_parent.revalidate_mutable_leaf()
        environment_parent.revalidate_mutable_leaf()

        final_sealed = sealed_parent.open_child_directory(sealed_path.name)
        final_environment = environment_parent.open_child_directory(
            environment_path.name
        )
        for directory in (final_sealed, final_environment):
            _require_root_owned_chain(directory)
            identity = FileIdentity.from_stat(os.fstat(directory.fd))
            if stat.S_IMODE(identity.mode) != 0o555:
                raise WarehouseW3RootCoordinatorError("published store mode differs")
        reverify_sealed_store(sealed_path, sealed_store)
        external_runtime_paths = tuple(
            Path(item.path)
            for item in environment_content.generic_receipt.external_runtime
        )
        source_candidate_root = Path(selected.ingress.candidate_root)
        source_selection_root = derive_candidate_paths(
            source_candidate_root.parent,
            gate.selection_key,
        ).selection_directory
        live_reader = FilesystemLiveEnvironmentReader(
            external_runtime_paths=external_runtime_paths,
            candidate_root=source_candidate_root,
            selection_root=source_selection_root,
        )
        relocation_pre = live_reader.rehash(
            environment_path,
            phase="relocation_pre",
            content_receipt=environment_content,
            generic_receipt=environment_content.generic_receipt,
        )
        final_probe = probe_reader.probe(
            environment_path,
            phase="final",
            content_receipt=environment_content,
        )
        relocation_post = live_reader.rehash(
            environment_path,
            phase="relocation_post",
            content_receipt=environment_content,
            generic_receipt=environment_content.generic_receipt,
        )
        relocation = EnvironmentRelocationReceipt.create(
            environment_content,
            candidate_probe=candidate_probe,
            simulated_final_probe=closure.simulated_final_probe,
            final_probe=final_probe,
            relocation_pre_rehash=relocation_pre,
            relocation_post_rehash=relocation_post,
        )
        if persist_relocation(relocation.raw) != relocation.raw:
            raise WarehouseW3RootCoordinatorError(
                "environment relocation differs after durable reopen"
            )
        sealed_publication = PublishedTreeReceipt.create(
            role="sealed",
            path=str(sealed_path),
            source_receipt_sha256=sealed_store.raw_sha256,
            expected_tree_sha256=sealed_store.aggregate_sha256,
            reopened_tree_sha256=sealed_store.aggregate_sha256,
            identity=_directory_snapshot(
                FileIdentity.from_stat(os.fstat(final_sealed.fd))
            ),
        )
        environment_publication = PublishedTreeReceipt.create(
            role="environment",
            path=str(environment_path),
            source_receipt_sha256=environment_content.generic_receipt_sha256,
            expected_tree_sha256=(environment_content.environment_inventory_sha256),
            reopened_tree_sha256=(environment_content.environment_inventory_sha256),
            identity=_directory_snapshot(
                FileIdentity.from_stat(os.fstat(final_environment.fd))
            ),
        )
        final_sealed.revalidate()
        final_environment.revalidate()
        return WarehouseW3StoresPublishedReceipt.create(
            candidate_gate=gate,
            authority=authority,
            installation=installation,
            sealed_store=sealed_store,
            environment_content=environment_content,
            sealed_publication=sealed_publication,
            environment_publication=environment_publication,
            environment_relocation=relocation,
        )
    except Exception as exc:
        raise WarehouseW3RootCoordinatorError(
            "W3 store publication is a permanent K2 hold"
        ) from exc
    finally:
        if final_environment is not None:
            final_environment.close()
        if final_sealed is not None:
            final_sealed.close()
        if candidate_environment is not None:
            candidate_environment.close()
        environment_parent.close()
        sealed_parent.close()
        candidate.close()
        quarantine.close()


def _acquire_w3_runtime_account() -> WarehouseW3RuntimeAccountReceipt:
    """Bind the sole configured runtime account before K3 intent creation."""

    _require_root()
    try:
        account = pwd.getpwnam("clawd")
        receipt = WarehouseW3RuntimeAccountReceipt.create(
            observed_name=account.pw_name,
            observed_uid=account.pw_uid,
            observed_gid=account.pw_gid,
        )
    except Exception as exc:
        raise WarehouseW3RootCoordinatorError(
            "fixed W3 runtime account cannot be acquired"
        ) from exc
    if receipt.uid == 0 or receipt.gid == 0:
        raise WarehouseW3RootCoordinatorError("fixed W3 runtime account is root")
    return receipt


def _published_regular_receipt(
    parent: PinnedDirectory,
    *,
    role: str,
    leaf: str,
    path: Path,
    expected_raw: bytes,
) -> PublishedRegularFileReceipt:
    descriptor, identity, raw = _acquire_fixed_receipt(
        parent,
        leaf,
        maximum=_MAX_RECEIPT_BYTES,
        require_root_owner=True,
    )
    try:
        if raw != expected_raw:
            raise WarehouseW3RootCoordinatorError(f"published {role} bytes differ")
        return PublishedRegularFileReceipt.create(
            role=role,
            path=str(path),
            content_sha256=hashlib.sha256(raw).hexdigest(),
            size_bytes=identity.size,
            device=identity.device,
            inode=identity.inode,
            mode=stat.S_IMODE(identity.mode),
            uid=identity.uid,
            gid=identity.gid,
            nlink=identity.link_count,
        )
    finally:
        os.close(descriptor)


def _publish_w3_authority_records(
    selected: WarehouseW3SelectedCandidateChain,
    runtime_account: WarehouseW3RuntimeAccountReceipt,
) -> WarehouseW3AuthorityPublishedReceipt:
    """Publish the exact authority pair and fresh external nonce-claim root."""

    _require_root()
    if type(selected) is not WarehouseW3SelectedCandidateChain:
        raise TypeError("selected must be exact WarehouseW3SelectedCandidateChain")
    if type(runtime_account) is not WarehouseW3RuntimeAccountReceipt:
        raise TypeError("runtime_account must be exact")
    verification = selected.root_staging_verification
    authority = verification.authority
    installation = verification.installation
    authority_path = _AUTHORITY_ROOT / f"{authority.authority_sha256}.json"
    installation_path = _INSTALLATION_ROOT / f"{installation.launch_id}.json"
    nonce_ledger_parent = _RUN_ROOT / ".nonce-ledger" / "claims"
    if (
        Path(installation.authority_path) != authority_path
        or Path(installation.nonce_ledger_parent) != nonce_ledger_parent
        or runtime_account.name != "clawd"
        or runtime_account.uid == 0
        or runtime_account.gid == 0
    ):
        raise WarehouseW3RootCoordinatorError(
            "selected authority destination or runtime owner differs"
        )
    authority_parent = pin_absolute_directory(str(_AUTHORITY_ROOT))
    installation_parent = pin_absolute_directory(str(_INSTALLATION_ROOT))
    run_parent = pin_absolute_directory(str(_RUN_ROOT))
    authority_writer: DurableReceiptDirectory | None = None
    installation_writer: DurableReceiptDirectory | None = None
    nonce_hierarchy: RootDirectoryHierarchy | None = None
    claims: PinnedDirectory | None = None
    try:
        for parent in (authority_parent, installation_parent, run_parent):
            _require_root_owned_chain(parent)
            identity = FileIdentity.from_stat(os.fstat(parent.fd))
            if stat.S_IMODE(identity.mode) != 0o755:
                raise WarehouseW3RootCoordinatorError(
                    "fixed W3 publication parent mode differs"
                )
        authority_writer = DurableReceiptDirectory(_AUTHORITY_ROOT)
        authority_writer.write_no_replace(authority_path.name, authority.raw)
        installation_writer = DurableReceiptDirectory(_INSTALLATION_ROOT)
        installation_writer.write_no_replace(
            installation_path.name,
            installation.raw,
        )
        authority_publication = _published_regular_receipt(
            authority_parent,
            role="authority",
            leaf=authority_path.name,
            path=authority_path,
            expected_raw=authority.raw,
        )
        installation_publication = _published_regular_receipt(
            installation_parent,
            role="installation",
            leaf=installation_path.name,
            path=installation_path,
            expected_raw=installation.raw,
        )

        nonce_hierarchy = RootDirectoryHierarchy.create_fresh(
            run_parent,
            (
                FreshDirectorySpec(
                    role="nonce-ledger",
                    parent_role=None,
                    leaf=".nonce-ledger",
                    mode=0o755,
                    uid=0,
                    gid=0,
                ),
                FreshDirectorySpec(
                    role="nonce-claims",
                    parent_role="nonce-ledger",
                    leaf="claims",
                    mode=0o700,
                    uid=runtime_account.uid,
                    gid=runtime_account.gid,
                ),
            ),
        )
        claims_observation = nonce_hierarchy.directory_observation("nonce-claims")
        nonce_hierarchy.close()
        nonce_hierarchy = None
        claims = pin_absolute_directory(str(nonce_ledger_parent))
        claims.revalidate()
        claims_identity = FileIdentity.from_stat(os.fstat(claims.fd))
        if (
            claims_identity != claims_observation.identity
            or claims_identity.uid != runtime_account.uid
            or claims_identity.gid != runtime_account.gid
            or stat.S_IMODE(claims_identity.mode) != 0o700
            or os.listdir(claims.fd)
        ):
            raise WarehouseW3RootCoordinatorError(
                "external nonce-claim root differs after reopen"
            )
        for component in claims.components[:-1]:
            if (
                component.identity.uid != 0
                or component.identity.gid != 0
                or stat.S_IMODE(component.identity.mode) & 0o022
            ):
                raise WarehouseW3RootCoordinatorError(
                    "external nonce-claim parent chain differs"
                )
        nonce_directory = PublishedDirectoryReceipt.create(
            role="nonce-claims",
            path=str(nonce_ledger_parent),
            device=claims_identity.device,
            inode=claims_identity.inode,
            mode=stat.S_IMODE(claims_identity.mode),
            uid=claims_identity.uid,
            gid=claims_identity.gid,
            nlink=claims_identity.link_count,
            expected_mode=0o700,
            expected_uid=runtime_account.uid,
            expected_gid=runtime_account.gid,
        )
        authority_parent.revalidate_mutable_leaf()
        installation_parent.revalidate_mutable_leaf()
        run_parent.revalidate_mutable_leaf()
        return WarehouseW3AuthorityPublishedReceipt.create(
            authority=authority,
            installation=installation,
            authority_publication=authority_publication,
            installation_publication=installation_publication,
            nonce_directory=nonce_directory,
        )
    except Exception as exc:
        raise WarehouseW3RootCoordinatorError(
            "W3 authority publication is a permanent K3 hold"
        ) from exc
    finally:
        if claims is not None:
            claims.close()
        if nonce_hierarchy is not None:
            nonce_hierarchy.close()
        if installation_writer is not None:
            installation_writer.close()
        if authority_writer is not None:
            authority_writer.close()
        run_parent.close()
        installation_parent.close()
        authority_parent.close()


def _read_stable_kernel_fact(path: Path, *, maximum: int, label: str) -> bytes:
    if not isinstance(path, Path) or not path.is_absolute():
        raise TypeError("kernel fact path must be one absolute Path")
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:

        def read_once() -> bytes:
            os.lseek(descriptor, 0, os.SEEK_SET)
            chunks: list[bytes] = []
            total = 0
            while True:
                chunk = os.read(descriptor, min(64 * 1024, maximum + 1 - total))
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
                if total > maximum:
                    raise WarehouseW3RootCoordinatorError(
                        f"{label} exceeds its byte limit"
                    )
            return b"".join(chunks)

        before = os.fstat(descriptor)
        first = read_once()
        middle = os.fstat(descriptor)
        second = read_once()
        after = os.fstat(descriptor)
        if (
            not first
            or first != second
            or _signature(before) != _signature(middle)
            or _signature(middle) != _signature(after)
        ):
            raise WarehouseW3RootCoordinatorError(f"{label} is not stable")
        return first
    finally:
        os.close(descriptor)


def _acquire_boot_and_mount_namespace(
    adapter: LinuxRootAdapter,
) -> tuple[str, MountNamespacePair]:
    if type(adapter) is not LinuxRootAdapter:
        raise TypeError("adapter must be exact LinuxRootAdapter")
    raw = _read_stable_kernel_fact(
        Path("/proc/sys/kernel/random/boot_id"),
        maximum=128,
        label="kernel boot id",
    )
    try:
        boot_id = raw.decode("ascii", "strict").removesuffix("\n")
    except UnicodeError as exc:
        raise WarehouseW3RootCoordinatorError("kernel boot id differs") from exc
    if raw != f"{boot_id}\n".encode("ascii") or _BOOT_ID_RE.fullmatch(boot_id) is None:
        raise WarehouseW3RootCoordinatorError("kernel boot id differs")
    return boot_id, acquire_mount_namespace_pair(adapter, require_same=True)


def _reopen_w3_store_publications(
    selected: WarehouseW3SelectedCandidateChain,
    stores_published: WarehouseW3StoresPublishedReceipt,
) -> tuple[PublishedTreeReceipt, PublishedTreeReceipt]:
    verification = selected.root_staging_verification
    installation = verification.installation
    sealed_store = verification.sealed_store_receipt
    environment_content = selected.closure.semantic_environment
    sealed_path = Path(installation.sealed_root)
    environment_path = Path(installation.environment_root)
    sealed = pin_absolute_directory(str(sealed_path))
    environment = pin_absolute_directory(str(environment_path))
    try:
        for directory in (sealed, environment):
            _require_root_owned_chain(directory)
            identity = FileIdentity.from_stat(os.fstat(directory.fd))
            if stat.S_IMODE(identity.mode) != 0o555:
                raise WarehouseW3RootCoordinatorError(
                    "published store mode differs during K4 reopen"
                )
        reverify_sealed_store(sealed_path, sealed_store)
        generic = environment_content.generic_receipt
        verify_environment_content(
            environment_path,
            generic,
            external_runtime_paths=tuple(
                Path(item.path) for item in generic.external_runtime
            ),
            candidate_root=Path(selected.ingress.candidate_root),
            selection_root=derive_candidate_paths(
                Path(selected.ingress.candidate_root).parent,
                selected.closure.gate.selection_key,
            ).selection_directory,
        )
        sealed_receipt = PublishedTreeReceipt.create(
            role="sealed",
            path=str(sealed_path),
            source_receipt_sha256=sealed_store.raw_sha256,
            expected_tree_sha256=sealed_store.aggregate_sha256,
            reopened_tree_sha256=sealed_store.aggregate_sha256,
            identity=_directory_snapshot(FileIdentity.from_stat(os.fstat(sealed.fd))),
        )
        environment_receipt = PublishedTreeReceipt.create(
            role="environment",
            path=str(environment_path),
            source_receipt_sha256=environment_content.generic_receipt_sha256,
            expected_tree_sha256=environment_content.environment_inventory_sha256,
            reopened_tree_sha256=environment_content.environment_inventory_sha256,
            identity=_directory_snapshot(
                FileIdentity.from_stat(os.fstat(environment.fd))
            ),
        )
        if (
            sealed_receipt.raw_sha256 != stores_published.sealed_publication_sha256
            or environment_receipt.raw_sha256
            != stores_published.environment_publication_sha256
            or stores_published.sealed_path != str(sealed_path)
            or stores_published.environment_path != str(environment_path)
        ):
            raise WarehouseW3RootCoordinatorError(
                "K2 store publication differs during K4 reopen"
            )
        sealed.revalidate()
        environment.revalidate()
        return sealed_receipt, environment_receipt
    finally:
        environment.close()
        sealed.close()


def _reopen_w3_authority_publications(
    selected: WarehouseW3SelectedCandidateChain,
    authority_published: WarehouseW3AuthorityPublishedReceipt,
    runtime_account: WarehouseW3RuntimeAccountReceipt,
) -> tuple[
    PublishedRegularFileReceipt,
    PublishedRegularFileReceipt,
    PublishedDirectoryReceipt,
]:
    verification = selected.root_staging_verification
    authority = verification.authority
    installation = verification.installation
    authority_path = Path(installation.authority_path)
    installation_path = _INSTALLATION_ROOT / f"{installation.launch_id}.json"
    authority_parent = pin_absolute_directory(str(_AUTHORITY_ROOT))
    installation_parent = pin_absolute_directory(str(_INSTALLATION_ROOT))
    claims = pin_absolute_directory(installation.nonce_ledger_parent)
    try:
        authority_file = _published_regular_receipt(
            authority_parent,
            role="authority",
            leaf=authority_path.name,
            path=authority_path,
            expected_raw=authority.raw,
        )
        installation_file = _published_regular_receipt(
            installation_parent,
            role="installation",
            leaf=installation_path.name,
            path=installation_path,
            expected_raw=installation.raw,
        )
        claims_identity = FileIdentity.from_stat(os.fstat(claims.fd))
        if (
            claims_identity.uid != runtime_account.uid
            or claims_identity.gid != runtime_account.gid
            or stat.S_IMODE(claims_identity.mode) != 0o700
            or os.listdir(claims.fd)
        ):
            raise WarehouseW3RootCoordinatorError(
                "K3 nonce root differs during K4 reopen"
            )
        nonce_directory = PublishedDirectoryReceipt.create(
            role="nonce-claims",
            path=installation.nonce_ledger_parent,
            device=claims_identity.device,
            inode=claims_identity.inode,
            mode=stat.S_IMODE(claims_identity.mode),
            uid=claims_identity.uid,
            gid=claims_identity.gid,
            nlink=claims_identity.link_count,
            expected_mode=0o700,
            expected_uid=runtime_account.uid,
            expected_gid=runtime_account.gid,
        )
        if (
            authority_file.raw_sha256
            != authority_published.authority_publication_sha256
            or installation_file.raw_sha256
            != authority_published.installation_publication_sha256
            or nonce_directory.raw_sha256 != authority_published.nonce_directory_sha256
            or authority_published.nonce_uid != runtime_account.uid
            or authority_published.nonce_gid != runtime_account.gid
        ):
            raise WarehouseW3RootCoordinatorError(
                "K3 authority publication differs during K4 reopen"
            )
        claims.revalidate()
        return authority_file, installation_file, nonce_directory
    finally:
        claims.close()
        installation_parent.close()
        authority_parent.close()


def _projection_parent_receipts(
    projection_root: Path,
) -> tuple[PublishedDirectoryReceipt, ...]:
    parts = PurePosixPath(str(projection_root)).parts
    paths = tuple(
        Path(str(PurePosixPath(*parts[:index]))) for index in range(2, len(parts) + 1)
    )
    receipts: list[PublishedDirectoryReceipt] = []
    for index, path in enumerate(paths):
        directory = pin_absolute_directory(str(path))
        try:
            _require_root_owned_chain(directory)
            identity = FileIdentity.from_stat(os.fstat(directory.fd))
            if stat.S_IMODE(identity.mode) != 0o755:
                raise WarehouseW3RootCoordinatorError(
                    "projection parent chain mode differs"
                )
            receipts.append(
                PublishedDirectoryReceipt.create(
                    role=(
                        "projection-root"
                        if index == len(paths) - 1
                        else "projection-parent"
                    ),
                    path=str(path),
                    device=identity.device,
                    inode=identity.inode,
                    mode=stat.S_IMODE(identity.mode),
                    uid=identity.uid,
                    gid=identity.gid,
                    nlink=identity.link_count,
                    expected_mode=0o755,
                    expected_uid=0,
                    expected_gid=0,
                )
            )
        finally:
            directory.close()
    return tuple(receipts)


def _mount_root_for_source(source_path: Path, source_row: MountInfoRow) -> str:
    if type(source_row) is not MountInfoRow:
        raise TypeError("source_row must be exact MountInfoRow")
    mount_point = PurePosixPath(source_row.mount_point)
    root = PurePosixPath(source_row.root)
    try:
        relative = PurePosixPath(str(source_path)).relative_to(mount_point)
    except ValueError as exc:
        raise WarehouseW3RootCoordinatorError(
            "source path is outside its retained mount"
        ) from exc
    return str(root / relative)


def _mount_w3_projection(
    selected: WarehouseW3SelectedCandidateChain,
    stores_published: WarehouseW3StoresPublishedReceipt,
    authority_published: WarehouseW3AuthorityPublishedReceipt,
    runtime_account: WarehouseW3RuntimeAccountReceipt,
    *,
    boot_id: str,
    namespace_pair: MountNamespacePair,
) -> WarehouseW3ProjectionReceipt:
    """Create the six-entry projection and attach four descriptor-owned mounts."""

    _require_root()
    if (
        type(selected) is not WarehouseW3SelectedCandidateChain
        or type(stores_published) is not WarehouseW3StoresPublishedReceipt
        or type(authority_published) is not WarehouseW3AuthorityPublishedReceipt
        or type(runtime_account) is not WarehouseW3RuntimeAccountReceipt
        or type(namespace_pair) is not MountNamespacePair
    ):
        raise TypeError("K4 projection inputs differ")
    verification = selected.root_staging_verification
    gate = selected.closure.gate
    authority = verification.authority
    installation = verification.installation
    projection_root = _PROJECTION_ROOT / installation.launch_id
    if (
        Path(installation.projection_root) != projection_root
        or _BOOT_ID_RE.fullmatch(boot_id) is None
        or not namespace_pair.matches
    ):
        raise WarehouseW3RootCoordinatorError(
            "K4 projection root, boot, or namespace differs"
        )
    sealed_publication, environment_publication = _reopen_w3_store_publications(
        selected, stores_published
    )
    (
        _authority_publication,
        _installation_publication,
        nonce_directory,
    ) = _reopen_w3_authority_publications(
        selected,
        authority_published,
        runtime_account,
    )
    projection_parent = pin_absolute_directory(str(_PROJECTION_ROOT))
    hierarchy: RootDirectoryHierarchy | None = None
    projection: PinnedDirectory | None = None
    sources: list[PinnedDirectory] = []
    try:
        _require_root_owned_chain(projection_parent)
        hierarchy = RootDirectoryHierarchy.create_fresh(
            projection_parent,
            (
                FreshDirectorySpec(
                    role="projection-root",
                    parent_role=None,
                    leaf=installation.launch_id,
                    mode=0o755,
                    uid=0,
                    gid=0,
                ),
                *(
                    FreshDirectorySpec(
                        role=f"projection-{leaf}",
                        parent_role="projection-root",
                        leaf=leaf,
                        mode=0o755,
                        uid=0,
                        gid=0,
                    )
                    for leaf in ("environment", "nonce-claims", "run", "sealed")
                ),
            ),
        )
        hierarchy.publish_regular_noreplace(
            RegularPublicationSpec(
                role="projection-authority",
                parent_role="projection-root",
                leaf="authority.json",
                raw=authority.raw,
                maximum=_MAX_RECEIPT_BYTES,
            )
        )
        hierarchy.publish_regular_noreplace(
            RegularPublicationSpec(
                role="projection-installation",
                parent_role="projection-root",
                leaf="installation.json",
                raw=installation.raw,
                maximum=_MAX_RECEIPT_BYTES,
            )
        )
        hierarchy.close()
        hierarchy = None
        projection = projection_parent.open_child_directory(installation.launch_id)
        _require_root_owned_chain(projection)
        if tuple(sorted(os.listdir(projection.fd), key=os.fsencode)) != (
            "authority.json",
            "environment",
            "installation.json",
            "nonce-claims",
            "run",
            "sealed",
        ):
            raise WarehouseW3RootCoordinatorError("fresh projection inventory differs")

        source_specs = (
            (
                "environment",
                Path(installation.environment_root),
                environment_publication.identity.device,
                environment_publication.identity.inode,
                True,
            ),
            (
                "nonce-claims",
                Path(installation.nonce_ledger_parent),
                nonce_directory.device,
                nonce_directory.inode,
                False,
            ),
            (
                "run",
                Path(installation.run_root),
                gate.accepted_root_identity.device,
                gate.accepted_root_identity.inode,
                False,
            ),
            (
                "sealed",
                Path(installation.sealed_root),
                sealed_publication.identity.device,
                sealed_publication.identity.inode,
                True,
            ),
        )
        for _role, path, expected_device, expected_inode, _read_only in source_specs:
            source = pin_absolute_directory(str(path))
            identity = FileIdentity.from_stat(os.fstat(source.fd))
            if identity.device != expected_device or identity.inode != expected_inode:
                source.close()
                raise WarehouseW3RootCoordinatorError(
                    "projection source identity differs before attach"
                )
            sources.append(source)
        run_identity = FileIdentity.from_stat(os.fstat(sources[2].fd))
        accepted = gate.accepted_root_identity
        if (
            run_identity.device,
            run_identity.inode,
            stat.S_IMODE(run_identity.mode),
            run_identity.uid,
            run_identity.gid,
            run_identity.link_count,
        ) != (
            accepted.device,
            accepted.inode,
            accepted.mode,
            accepted.uid,
            accepted.gid,
            accepted.nlink,
        ):
            raise WarehouseW3RootCoordinatorError(
                "accepted dry-root identity differs before projection"
            )

        adapter = LinuxRootAdapter()
        attached = {}
        for (
            role,
            _path,
            _expected_device,
            _expected_inode,
            read_only,
        ), source in zip(source_specs, sources, strict=True):
            attached[role] = attach_cloned_mount(
                adapter,
                source_fd=source.fd,
                destination_parent_fd=projection.fd,
                destination_leaf=role,
                read_only=read_only,
            )
        mountinfo = _read_stable_kernel_fact(
            Path("/proc/self/mountinfo"),
            maximum=16 * 1024 * 1024,
            label="self mountinfo",
        )
        mount_receipts: dict[str, MountBindingReceipt] = {}
        for (
            role,
            source_path,
            _expected_device,
            _expected_inode,
            read_only,
        ), source in zip(source_specs, sources, strict=True):
            attachment = attached[role]
            source_identity = FileIdentity.from_stat(os.fstat(source.fd))
            destination_path = projection_root / role
            destination = pin_absolute_directory(str(destination_path))
            try:
                destination_identity = FileIdentity.from_stat(os.fstat(destination.fd))
                row = parse_selected_mountinfo(
                    mountinfo,
                    mount_point=str(destination_path),
                )
                source_row = parse_mountinfo_mount_id(
                    mountinfo,
                    mount_id=attachment.source_mount_id,
                )
                if (
                    row.mount_id != attachment.destination_mount_id
                    or destination_identity.device != source_identity.device
                    or destination_identity.inode != source_identity.inode
                ):
                    raise WarehouseW3RootCoordinatorError(
                        "attached projection mount identity differs"
                    )
                mount_receipts[role] = MountBindingReceipt.create(
                    row=row,
                    source_identity=DirectoryIdentity(
                        device=source_identity.device,
                        inode=source_identity.inode,
                    ),
                    destination_identity=DirectoryIdentity(
                        device=destination_identity.device,
                        inode=destination_identity.inode,
                    ),
                    source_mount_id=attachment.source_mount_id,
                    read_only=read_only,
                    expected_filesystem_type=source_row.filesystem_type,
                    expected_mount_root=_mount_root_for_source(
                        source_path,
                        source_row,
                    ),
                )
                destination.revalidate()
            finally:
                destination.close()
        current_boot_id, current_namespace_pair = _acquire_boot_and_mount_namespace(
            adapter
        )
        if current_boot_id != boot_id or current_namespace_pair != namespace_pair:
            raise WarehouseW3RootCoordinatorError(
                "boot or mount namespace changed during K4"
            )
        projected_authority = _published_regular_receipt(
            projection,
            role="authority",
            leaf="authority.json",
            path=projection_root / "authority.json",
            expected_raw=authority.raw,
        )
        projected_installation = _published_regular_receipt(
            projection,
            role="installation",
            leaf="installation.json",
            path=projection_root / "installation.json",
            expected_raw=installation.raw,
        )
        parent_chain = _projection_parent_receipts(projection_root)
        projection.revalidate()
        for source in sources:
            source.revalidate()
        return WarehouseW3ProjectionReceipt.create(
            authority=authority,
            installation=installation,
            candidate_gate=gate,
            sealed_publication=sealed_publication,
            environment_publication=environment_publication,
            nonce_directory=nonce_directory,
            namespace_pair=namespace_pair,
            destination_parent_chain=parent_chain,
            boot_id=boot_id,
            run_mount=mount_receipts["run"],
            sealed_mount=mount_receipts["sealed"],
            environment_mount=mount_receipts["environment"],
            nonce_claims_mount=mount_receipts["nonce-claims"],
            authority_publication=projected_authority,
            installation_publication=projected_installation,
        )
    except Exception as exc:
        raise WarehouseW3RootCoordinatorError(
            "W3 projection mutation is a permanent K4 hold"
        ) from exc
    finally:
        for source in reversed(sources):
            source.close()
        if projection is not None:
            projection.close()
        if hierarchy is not None:
            hierarchy.close()
        projection_parent.close()


def _verify_w3_units_with_systemd_analyze(
    installation: InstallationRecord,
) -> None:
    """Run the sole read-only unit verifier after projection and publication."""

    if type(installation) is not InstallationRecord:
        raise TypeError("installation must be exact InstallationRecord")
    argv = (
        "/usr/bin/systemd-analyze",
        "verify",
        installation.run_unit,
        installation.close_unit,
    )
    environment = {
        "HOME": "/nonexistent",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PATH": "/usr/bin:/bin",
        "SYSTEMD_LOG_LEVEL": "warning",
    }
    try:
        completed = subprocess.run(
            argv,
            cwd="/",
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise WarehouseW3RootCoordinatorError(
            "systemd-analyze verify could not execute"
        ) from exc
    if (
        type(completed.returncode) is not int
        or completed.returncode != 0
        or type(completed.stdout) is not bytes
        or type(completed.stderr) is not bytes
        or completed.stdout
        or completed.stderr
    ):
        raise WarehouseW3RootCoordinatorError(
            "systemd-analyze verify did not return one clean success"
        )


def _publish_w3_units(
    selected: WarehouseW3SelectedCandidateChain,
    projection: WarehouseW3ProjectionReceipt,
) -> UnitPublicationReceipt:
    """Publish both exact templates no-replace and rederive their pair."""

    _require_root()
    if (
        type(selected) is not WarehouseW3SelectedCandidateChain
        or type(projection) is not WarehouseW3ProjectionReceipt
    ):
        raise TypeError("K5 unit publication inputs differ")
    verification = selected.root_staging_verification
    authority = verification.authority
    installation = verification.installation
    if (
        projection.launch_id != installation.launch_id
        or projection.authority_sha256 != authority.authority_sha256
        or projection.installation_sha256 != installation.installation_sha256
    ):
        raise WarehouseW3RootCoordinatorError("K5 projection predecessor differs")
    quarantine_leaf = selected.closure.candidate_verification.candidate_receipt_sha256
    candidate = pin_absolute_directory(
        str(_IMPORT_ROOT / quarantine_leaf / selected.tree_import.staging_leaf)
    )
    units = candidate.open_child_directory("units")
    unit_parent = pin_absolute_directory(str(_SYSTEMD_UNIT_ROOT))
    writer: DurableReceiptDirectory | None = None
    try:
        _require_root_owned_chain(candidate)
        _require_root_owned_chain(units)
        _require_root_owned_chain(unit_parent)
        unit_parent_identity = FileIdentity.from_stat(os.fstat(unit_parent.fd))
        if stat.S_IMODE(unit_parent_identity.mode) & 0o022:
            raise WarehouseW3RootCoordinatorError(
                "systemd unit publication parent is writable by non-root"
            )
        run_leaf = "scion-w3@.service"
        close_leaf = "scion-w3-close@.service"
        run_descriptor, _run_identity, run_raw = _acquire_fixed_receipt(
            units,
            run_leaf,
            maximum=_MAX_RECEIPT_BYTES,
            require_root_owner=True,
        )
        os.close(run_descriptor)
        close_descriptor, _close_identity, close_raw = _acquire_fixed_receipt(
            units,
            close_leaf,
            maximum=_MAX_RECEIPT_BYTES,
            require_root_owner=True,
        )
        os.close(close_descriptor)
        if (
            hashlib.sha256(run_raw).hexdigest() != authority.run_template_sha256
            or hashlib.sha256(close_raw).hexdigest() != authority.close_template_sha256
        ):
            raise WarehouseW3RootCoordinatorError(
                "imported unit template authority differs"
            )
        for leaf in (
            run_leaf,
            close_leaf,
            f"{installation.run_unit}.d",
            f"{installation.close_unit}.d",
        ):
            try:
                os.stat(leaf, dir_fd=unit_parent.fd, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise WarehouseW3RootCoordinatorError(
                    "unit fragment or instance drop-in slot is not absent"
                )
        writer = DurableReceiptDirectory(_SYSTEMD_UNIT_ROOT)
        writer.write_no_replace(run_leaf, run_raw)
        writer.write_no_replace(close_leaf, close_raw)
        run_publication = _published_regular_receipt(
            unit_parent,
            role="run-fragment",
            leaf=run_leaf,
            path=_SYSTEMD_UNIT_ROOT / run_leaf,
            expected_raw=run_raw,
        )
        close_publication = _published_regular_receipt(
            unit_parent,
            role="close-fragment",
            leaf=close_leaf,
            path=_SYSTEMD_UNIT_ROOT / close_leaf,
            expected_raw=close_raw,
        )
        _verify_w3_units_with_systemd_analyze(installation)
        units.revalidate()
        candidate.revalidate_mutable_leaf()
        unit_parent.revalidate_mutable_leaf()
        return UnitPublicationReceipt.create(
            authority=authority,
            installation=installation,
            run_template_raw=run_raw,
            close_template_raw=close_raw,
            run_publication=run_publication,
            close_publication=close_publication,
        )
    except Exception as exc:
        raise WarehouseW3RootCoordinatorError(
            "W3 unit publication is a permanent K5 hold"
        ) from exc
    finally:
        if writer is not None:
            writer.close()
        unit_parent.close()
        units.close()
        candidate.close()


def _reopen_w3_unit_publications(
    selected: WarehouseW3SelectedCandidateChain,
    unit_publication: UnitPublicationReceipt,
) -> tuple[
    bytes,
    bytes,
    PublishedRegularFileReceipt,
    PublishedRegularFileReceipt,
]:
    verification = selected.root_staging_verification
    installation = verification.installation
    unit_parent = pin_absolute_directory(str(_SYSTEMD_UNIT_ROOT))
    try:
        run_path = _SYSTEMD_UNIT_ROOT / "scion-w3@.service"
        close_path = _SYSTEMD_UNIT_ROOT / "scion-w3-close@.service"
        run_descriptor, _run_identity, run_raw = _acquire_fixed_receipt(
            unit_parent,
            run_path.name,
            maximum=_MAX_RECEIPT_BYTES,
            require_root_owner=True,
        )
        os.close(run_descriptor)
        close_descriptor, _close_identity, close_raw = _acquire_fixed_receipt(
            unit_parent,
            close_path.name,
            maximum=_MAX_RECEIPT_BYTES,
            require_root_owner=True,
        )
        os.close(close_descriptor)
        run_publication = _published_regular_receipt(
            unit_parent,
            role="run-fragment",
            leaf=run_path.name,
            path=run_path,
            expected_raw=run_raw,
        )
        close_publication = _published_regular_receipt(
            unit_parent,
            role="close-fragment",
            leaf=close_path.name,
            path=close_path,
            expected_raw=close_raw,
        )
        reopened = UnitPublicationReceipt.create(
            authority=verification.authority,
            installation=installation,
            run_template_raw=run_raw,
            close_template_raw=close_raw,
            run_publication=run_publication,
            close_publication=close_publication,
        )
        if reopened != unit_publication:
            raise WarehouseW3RootCoordinatorError(
                "K5 unit publication differs during manager acquisition"
            )
        return run_raw, close_raw, run_publication, close_publication
    finally:
        unit_parent.close()


def _expanded_template_value(value: str, launch_id: str) -> str:
    if type(value) is not str:
        raise TypeError("unit template value must be exact text")
    return value.replace("%i", launch_id)


def _acquire_w3_configured_readback(
    manager: NarrowInstallationManager,
    installation: InstallationRecord,
    *,
    run_template_raw: bytes,
    close_template_raw: bytes,
) -> ConfiguredPairReadback:
    """Acquire the exact problem-owned property/wiring surface after Load/Get."""

    run_template = parse_unit_template(run_template_raw)
    close_template = parse_unit_template(close_template_raw)
    launch_id = installation.launch_id
    run_unit = dict(run_template.section("Unit"))
    run_service = dict(run_template.section("Service"))
    close_unit = dict(close_template.section("Unit"))
    close_service = dict(close_template.section("Service"))

    def selected(
        unit_values: dict[str, str],
        service_values: dict[str, str],
        names: tuple[str, ...],
    ) -> dict[str, str]:
        try:
            return {
                name: _expanded_template_value(
                    (
                        unit_values[name]
                        if name in unit_values
                        else service_values[name]
                    ),
                    launch_id,
                )
                for name in names
            }
        except KeyError as exc:
            raise WarehouseW3RootCoordinatorError(
                "unit template configured surface differs"
            ) from exc

    run_directives = selected(
        run_unit,
        run_service,
        (
            "Delegate",
            "DelegateSubgroup",
            "CollectMode",
            "Restart",
            "KillMode",
            "TimeoutStopSec",
            "OnSuccess",
            "OnFailure",
        ),
    )
    close_directives = selected(
        close_unit,
        close_service,
        ("CollectMode", "Restart", "TimeoutStartSec", "After"),
    )
    run_wiring = selected(
        {},
        run_service,
        (
            "Type",
            "User",
            "Group",
            "UMask",
            "ExecStart",
            "ExecStopPost",
            "ExitType",
            "SendSIGKILL",
            "OOMPolicy",
            "NoNewPrivileges",
            "PrivateTmp",
            "PrivateMounts",
            "ProtectSystem",
            "ProtectHome",
            "ProtectControlGroups",
            "ProtectProc",
            "ProcSubset",
            "ReadOnlyPaths",
            "ReadWritePaths",
        ),
    )
    close_wiring = selected(
        {},
        close_service,
        (
            "Type",
            "User",
            "Group",
            "UMask",
            "ExecStart",
            "NoNewPrivileges",
            "PrivateTmp",
            "ProtectSystem",
            "ProtectHome",
            "ReadOnlyPaths",
            "ReadWritePaths",
        ),
    )
    readback = Systemd255Acquirer(manager).acquire_configured_pair_readback(
        run_unit=installation.run_unit,
        close_unit=installation.close_unit,
        run_directives=run_directives,
        close_directives=close_directives,
        run_wiring=run_wiring,
        close_wiring=close_wiring,
    )
    if (
        readback.run_unit != installation.run_unit
        or readback.close_unit != installation.close_unit
        or readback.configured_pair != installation.configured_pair
    ):
        raise WarehouseW3RootCoordinatorError(
            "configured pair readback differs from installation"
        )
    return readback


def _verify_no_w3_process(unit: str) -> None:
    token = unit.encode("ascii", "strict")
    try:
        processes = tuple(
            item
            for item in Path("/proc").iterdir()
            if item.name.isascii() and item.name.isdecimal()
        )
    except OSError as exc:
        raise WarehouseW3RootCoordinatorError(
            "prestart process inventory is unavailable"
        ) from exc
    for process in processes:
        for leaf in ("cmdline", "cgroup"):
            try:
                raw = (process / leaf).read_bytes()
            except (FileNotFoundError, ProcessLookupError, PermissionError):
                continue
            except OSError as exc:
                raise WarehouseW3RootCoordinatorError(
                    "prestart process fact is ambiguous"
                ) from exc
            if len(raw) > 1024 * 1024:
                raise WarehouseW3RootCoordinatorError(
                    "prestart process fact exceeds its bound"
                )
            if token in raw:
                raise WarehouseW3RootCoordinatorError(
                    "W3 service process is already present"
                )


def _acquire_w3_prestart_absence(
    authority: AcceptedLaunchAuthority,
    installation: InstallationRecord,
) -> WarehouseW3PreStartAbsenceReceipt:
    terminal = installation.terminal_root
    service_cgroup = f"/sys/fs/cgroup/system.slice/{installation.run_unit}"
    subjects = {
        "artifacts": f"{terminal}/artifacts",
        "dynamic_control": f"{terminal}/control",
        "external_nonce_claim": (
            f"{installation.nonce_ledger_parent}/{authority.nonce}.claim.json"
        ),
        "invocation_nonce_claim": (f"{terminal}/control/invocation_claimed.v1.json"),
        "process": installation.run_unit,
        "raw": f"{terminal}/raw",
        "service_cgroup": service_cgroup,
        "start_issued": (
            f"/var/lib/scion/acceptances/w3/{installation.launch_id}"
            "/start/START_ISSUED"
        ),
        "supervisor_cgroup": f"{service_cgroup}/supervisor",
        "terminal_root": terminal,
    }
    observations = tuple(
        PreStartAbsenceObservation(role=role, subject=subjects[role])
        for role in sorted(subjects)
    )
    for observation in observations:
        if observation.role == "process":
            _verify_no_w3_process(observation.subject)
        elif os.path.lexists(observation.subject):
            raise WarehouseW3RootCoordinatorError(
                f"prestart subject is already present: {observation.role}"
            )
    return WarehouseW3PreStartAbsenceReceipt.create(
        authority=authority,
        installation=installation,
        observations=observations,
    )


def _reacquire_w3_prestart_producers(
    selected: WarehouseW3SelectedCandidateChain,
    *,
    configured_readback: ConfiguredPairReadback,
    runtime_account: WarehouseW3RuntimeAccountReceipt,
    run_template_raw: bytes,
    close_template_raw: bytes,
) -> tuple[
    LiveEnvironmentRehashFact,
    WarehouseW3DryRootReadinessReceipt,
    WarehouseW3PreStartAbsenceReceipt,
    WarehouseW3RuntimeAccountReceipt,
]:
    verification = selected.root_staging_verification
    gate = selected.closure.gate
    authority = verification.authority
    installation = verification.installation
    semantic = selected.closure.semantic_environment
    selection_intent = verification.selection_intent
    environment_rehash = verify_live_environment(
        semantic,
        phase="preclaim",
        live_reader=FilesystemLiveEnvironmentReader(
            external_runtime_paths=tuple(
                Path(item.path)
                for item in selected.closure.environment_content.external_runtime
            ),
            candidate_root=Path(selection_intent.candidate_root),
            selection_root=Path(selection_intent.selection_directory),
        ),
    )
    identity, inventory_sha256, inventory_count = reverify_w3_accepted_root(
        Path(installation.run_root)
    )
    dry_root = WarehouseW3DryRootReadinessReceipt.create(
        candidate_gate=gate,
        installation=installation,
        observed_identity=identity,
        observed_inventory_sha256=inventory_sha256,
        observed_inventory_count=inventory_count,
        observed_read_only=True,
        composition_state="LAUNCH_READY",
    )
    from .w3_composition import inspect_w3_launch_readiness

    readiness = inspect_w3_launch_readiness(
        Path(installation.run_root),
        authority.raw,
        installation.raw,
        run_template_raw,
        close_template_raw,
        live_configured_pair=configured_readback.configured_pair,
    )
    if readiness.state != "LAUNCH_READY" or readiness.filesystem_mutated is not False:
        raise WarehouseW3RootCoordinatorError(
            "problem-owned installed launch readiness differs"
        )
    prestart_absence = _acquire_w3_prestart_absence(authority, installation)
    current_runtime_account = _acquire_w3_runtime_account()
    if current_runtime_account != runtime_account:
        raise WarehouseW3RootCoordinatorError(
            "runtime account changed during installation"
        )
    return (
        environment_rehash,
        dry_root,
        prestart_absence,
        current_runtime_account,
    )


def _build_w3_prestart_evidence(
    selected: WarehouseW3SelectedCandidateChain,
    *,
    stores_published: WarehouseW3StoresPublishedReceipt,
    authority_published: WarehouseW3AuthorityPublishedReceipt,
    projection: WarehouseW3ProjectionReceipt,
    unit_publication: UnitPublicationReceipt,
    manager_reload: ManagerReloadReceipt,
    loaded_manager: LoadedManagerReceipt,
    configured_readback: ConfiguredPairReadback,
    runtime_account: WarehouseW3RuntimeAccountReceipt,
    pending_intent: RootPhaseIntentReceipt,
    prior_intents: tuple[RootPhaseIntentReceipt, ...],
    prior_receipts: tuple[RootPhaseReceipt, ...],
    run_template_raw: bytes,
    close_template_raw: bytes,
) -> WarehouseW3PreStartEvidence:
    """Reacquire every problem fact while K7 remains a pending transaction."""

    verification = selected.root_staging_verification
    gate = selected.closure.gate
    authority = verification.authority
    installation = verification.installation
    (
        environment_rehash,
        dry_root,
        prestart_absence,
        current_runtime_account,
    ) = _reacquire_w3_prestart_producers(
        selected,
        configured_readback=configured_readback,
        runtime_account=runtime_account,
        run_template_raw=run_template_raw,
        close_template_raw=close_template_raw,
    )
    if current_runtime_account != runtime_account:
        raise WarehouseW3RootCoordinatorError(
            "runtime account changed during prestart evidence"
        )
    return WarehouseW3PreStartEvidence.create(
        authority=authority,
        installation=installation,
        candidate_gate=gate,
        staged_candidate=selected.staged_candidate,
        selection=selected.root_selection,
        stores_published=stores_published,
        authority_published=authority_published,
        projection=projection,
        unit_publication=unit_publication,
        manager_reload=manager_reload,
        loaded_manager=loaded_manager,
        environment_rehash=environment_rehash,
        dry_root=dry_root,
        prestart_absence=prestart_absence,
        runtime_account=runtime_account,
        phase_intents=(*prior_intents, pending_intent),
        phase_receipts=prior_receipts,
    )


def _reopen_w3_projection_artifacts(
    selected: WarehouseW3SelectedCandidateChain,
    *,
    stores_published: WarehouseW3StoresPublishedReceipt,
    authority_published: WarehouseW3AuthorityPublishedReceipt,
    projection: WarehouseW3ProjectionReceipt,
    runtime_account: WarehouseW3RuntimeAccountReceipt,
) -> tuple[
    tuple[PublishedDirectoryReceipt, ...],
    MountBindingReceipt,
    MountBindingReceipt,
    MountBindingReceipt,
    MountBindingReceipt,
    PublishedRegularFileReceipt,
    PublishedRegularFileReceipt,
]:
    verification = selected.root_staging_verification
    installation = verification.installation
    sealed_publication, environment_publication = _reopen_w3_store_publications(
        selected, stores_published
    )
    _authority_file, _installation_file, nonce_directory = (
        _reopen_w3_authority_publications(
            selected,
            authority_published,
            runtime_account,
        )
    )
    adapter = LinuxRootAdapter()
    boot_id, namespace_pair = _acquire_boot_and_mount_namespace(adapter)
    if boot_id != projection.boot_id or namespace_pair != projection.namespace_pair:
        raise WarehouseW3RootCoordinatorError(
            "K4 boot or namespace differs during replay construction"
        )
    mountinfo = _read_stable_kernel_fact(
        Path("/proc/self/mountinfo"),
        maximum=16 * 1024 * 1024,
        label="self mountinfo",
    )
    source_specs = (
        (
            "environment",
            Path(installation.environment_root),
            environment_publication.identity.device,
            environment_publication.identity.inode,
            True,
        ),
        (
            "nonce-claims",
            Path(installation.nonce_ledger_parent),
            nonce_directory.device,
            nonce_directory.inode,
            False,
        ),
        (
            "run",
            Path(installation.run_root),
            selected.closure.gate.accepted_root_identity.device,
            selected.closure.gate.accepted_root_identity.inode,
            False,
        ),
        (
            "sealed",
            Path(installation.sealed_root),
            sealed_publication.identity.device,
            sealed_publication.identity.inode,
            True,
        ),
    )
    mounts: dict[str, MountBindingReceipt] = {}
    for role, source_path, expected_device, expected_inode, read_only in source_specs:
        source = pin_absolute_directory(str(source_path))
        destination = pin_absolute_directory(
            str(Path(installation.projection_root) / role)
        )
        try:
            source_identity = FileIdentity.from_stat(os.fstat(source.fd))
            destination_identity = FileIdentity.from_stat(os.fstat(destination.fd))
            if (
                source_identity.device != expected_device
                or source_identity.inode != expected_inode
                or destination_identity.device != expected_device
                or destination_identity.inode != expected_inode
            ):
                raise WarehouseW3RootCoordinatorError(
                    "K4 source or destination identity differs during replay"
                )
            source_mount_id = adapter.mount_id_for_fd(source.fd)
            source_row = parse_mountinfo_mount_id(
                mountinfo,
                mount_id=source_mount_id,
            )
            mounts[role] = MountBindingReceipt.create(
                row=parse_selected_mountinfo(
                    mountinfo,
                    mount_point=str(Path(installation.projection_root) / role),
                ),
                source_identity=DirectoryIdentity(
                    device=source_identity.device,
                    inode=source_identity.inode,
                ),
                destination_identity=DirectoryIdentity(
                    device=destination_identity.device,
                    inode=destination_identity.inode,
                ),
                source_mount_id=source_mount_id,
                read_only=read_only,
                expected_filesystem_type=source_row.filesystem_type,
                expected_mount_root=_mount_root_for_source(
                    source_path,
                    source_row,
                ),
            )
            source.revalidate()
            destination.revalidate()
        finally:
            destination.close()
            source.close()
    projection_root = Path(installation.projection_root)
    projection_parent = pin_absolute_directory(str(projection_root))
    try:
        projected_authority = _published_regular_receipt(
            projection_parent,
            role="authority",
            leaf="authority.json",
            path=projection_root / "authority.json",
            expected_raw=verification.authority.raw,
        )
        projected_installation = _published_regular_receipt(
            projection_parent,
            role="installation",
            leaf="installation.json",
            path=projection_root / "installation.json",
            expected_raw=installation.raw,
        )
    finally:
        projection_parent.close()
    parent_chain = _projection_parent_receipts(projection_root)
    reopened = WarehouseW3ProjectionReceipt.create(
        authority=verification.authority,
        installation=installation,
        candidate_gate=selected.closure.gate,
        sealed_publication=sealed_publication,
        environment_publication=environment_publication,
        nonce_directory=nonce_directory,
        namespace_pair=namespace_pair,
        destination_parent_chain=parent_chain,
        boot_id=boot_id,
        run_mount=mounts["run"],
        sealed_mount=mounts["sealed"],
        environment_mount=mounts["environment"],
        nonce_claims_mount=mounts["nonce-claims"],
        authority_publication=projected_authority,
        installation_publication=projected_installation,
    )
    if reopened != projection:
        raise WarehouseW3RootCoordinatorError(
            "K4 projection differs during replay construction"
        )
    return (
        parent_chain,
        mounts["run"],
        mounts["sealed"],
        mounts["environment"],
        mounts["nonce-claims"],
        projected_authority,
        projected_installation,
    )


def _construct_w3_installed_replay_inputs(
    selected: WarehouseW3SelectedCandidateChain,
    selection_replay_inputs: WarehouseW3SelectionReplayInputs,
    *,
    phase_intents: tuple[RootPhaseIntentReceipt, ...],
    phase_receipts: tuple[RootPhaseReceipt, ...],
    stores_published: WarehouseW3StoresPublishedReceipt,
    authority_published: WarehouseW3AuthorityPublishedReceipt,
    projection: WarehouseW3ProjectionReceipt,
    unit_publication: UnitPublicationReceipt,
    configured_readback: ConfiguredPairReadback,
    manager_reload: ManagerReloadReceipt,
    loaded_manager: LoadedManagerReceipt,
    runtime_account: WarehouseW3RuntimeAccountReceipt,
    prestart_evidence: WarehouseW3PreStartEvidence,
    installed_acceptance: InstalledAcceptance,
    environment_relocation_raw: bytes,
) -> WarehouseW3InstalledReplayInputs:
    """Independently reopen every K2-K7 producer for the final deep replay."""

    if (
        type(phase_intents) is not tuple
        or len(phase_intents) != len(INSTALL_PHASES)
        or type(phase_receipts) is not tuple
        or len(phase_receipts) != len(INSTALL_PHASES)
    ):
        raise WarehouseW3RootCoordinatorError(
            "K0-K8 replay transaction inventory differs"
        )
    verification = selected.root_staging_verification
    sealed_publication, environment_publication = _reopen_w3_store_publications(
        selected, stores_published
    )
    relocation = EnvironmentRelocationReceipt.from_bytes(
        environment_relocation_raw,
        content_receipt=selected.closure.semantic_environment,
    )
    rebuilt_stores = WarehouseW3StoresPublishedReceipt.create(
        candidate_gate=selected.closure.gate,
        authority=verification.authority,
        installation=verification.installation,
        sealed_store=verification.sealed_store_receipt,
        environment_content=selected.closure.semantic_environment,
        sealed_publication=sealed_publication,
        environment_publication=environment_publication,
        environment_relocation=relocation,
    )
    if rebuilt_stores != stores_published:
        raise WarehouseW3RootCoordinatorError(
            "K2 aggregate differs during replay construction"
        )
    (
        authority_publication,
        installation_publication,
        nonce_directory,
    ) = _reopen_w3_authority_publications(
        selected,
        authority_published,
        runtime_account,
    )
    (
        projection_parent_chain,
        run_mount,
        sealed_mount,
        environment_mount,
        nonce_claims_mount,
        projection_authority_publication,
        projection_installation_publication,
    ) = _reopen_w3_projection_artifacts(
        selected,
        stores_published=stores_published,
        authority_published=authority_published,
        projection=projection,
        runtime_account=runtime_account,
    )
    (
        run_template_raw,
        close_template_raw,
        run_publication,
        close_publication,
    ) = _reopen_w3_unit_publications(selected, unit_publication)
    (
        environment_rehash,
        dry_root,
        prestart_absence,
        current_runtime_account,
    ) = _reacquire_w3_prestart_producers(
        selected,
        configured_readback=configured_readback,
        runtime_account=runtime_account,
        run_template_raw=run_template_raw,
        close_template_raw=close_template_raw,
    )
    if current_runtime_account != runtime_account:
        raise WarehouseW3RootCoordinatorError(
            "runtime account differs during replay construction"
        )
    rebuilt_evidence = WarehouseW3PreStartEvidence.create(
        authority=verification.authority,
        installation=verification.installation,
        candidate_gate=selected.closure.gate,
        staged_candidate=selected.staged_candidate,
        selection=selected.root_selection,
        stores_published=stores_published,
        authority_published=authority_published,
        projection=projection,
        unit_publication=unit_publication,
        manager_reload=manager_reload,
        loaded_manager=loaded_manager,
        environment_rehash=environment_rehash,
        dry_root=dry_root,
        prestart_absence=prestart_absence,
        runtime_account=runtime_account,
        phase_intents=phase_intents[:8],
        phase_receipts=phase_receipts[:7],
    )
    if rebuilt_evidence != prestart_evidence:
        raise WarehouseW3RootCoordinatorError(
            "K7 prestart evidence differs during replay construction"
        )
    inputs = WarehouseW3InstalledReplayInputs(
        phase_intent_raws=tuple(item.raw for item in phase_intents),
        phase_receipt_raws=tuple(item.raw for item in phase_receipts),
        stores_published_raw=stores_published.raw,
        sealed_publication_raw=sealed_publication.raw,
        environment_publication_raw=environment_publication.raw,
        environment_relocation_raw=relocation.raw,
        authority_published_raw=authority_published.raw,
        authority_publication_raw=authority_publication.raw,
        installation_publication_raw=installation_publication.raw,
        nonce_directory_raw=nonce_directory.raw,
        projection_raw=projection.raw,
        projection_parent_raws=tuple(item.raw for item in projection_parent_chain),
        run_mount_raw=run_mount.raw,
        sealed_mount_raw=sealed_mount.raw,
        environment_mount_raw=environment_mount.raw,
        nonce_claims_mount_raw=nonce_claims_mount.raw,
        projection_authority_publication_raw=(projection_authority_publication.raw),
        projection_installation_publication_raw=(
            projection_installation_publication.raw
        ),
        run_template_raw=run_template_raw,
        close_template_raw=close_template_raw,
        run_unit_publication_raw=run_publication.raw,
        close_unit_publication_raw=close_publication.raw,
        unit_publication_raw=unit_publication.raw,
        configured_pair_readback_raw=configured_readback.raw,
        manager_reload_raw=manager_reload.raw,
        loaded_manager_raw=loaded_manager.raw,
        environment_rehash_raw=environment_rehash.raw,
        dry_root_raw=dry_root.raw,
        prestart_absence_raw=prestart_absence.raw,
        runtime_account_raw=runtime_account.raw,
        prestart_evidence_raw=prestart_evidence.raw,
        installed_acceptance_raw=installed_acceptance.raw,
    )
    verify_w3_installed_replay(inputs, selection_replay_inputs)
    return inputs


class WarehouseW3InstallPhaseLedger:
    """Forward-only owner for one fresh authoritative K0-K8 install ledger."""

    __slots__ = (
        "_acceptance_root",
        "_closed",
        "_intents",
        "_launch_id",
        "_receipts",
        "_require_root_owner",
        "_selected_candidate",
        "_selection_authority",
        "_writer",
    )

    def __new__(cls) -> "WarehouseW3InstallPhaseLedger":
        del cls
        raise TypeError("W3 install phase ledger must be created fresh")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("WarehouseW3InstallPhaseLedger is final")

    @classmethod
    def create(
        cls,
        selection_authority: RootSelectedCandidateAuthority,
    ) -> "WarehouseW3InstallPhaseLedger":
        """Create the fixed launch hierarchy from one retained root selection."""

        _require_root()
        if type(selection_authority) is not RootSelectedCandidateAuthority:
            raise TypeError(
                "selection_authority must be exact RootSelectedCandidateAuthority"
            )
        selection_authority.revalidate()
        instance = cls._create_at(
            _ACCEPTANCE_ROOT,
            selection_authority.chain,
            require_root_owner=True,
        )
        instance._selection_authority = selection_authority
        selection_authority.revalidate()
        return instance

    @classmethod
    def _create_at(
        cls,
        acceptance_root: Path,
        selected: WarehouseW3SelectedCandidateChain,
        *,
        require_root_owner: bool,
    ) -> "WarehouseW3InstallPhaseLedger":
        if not isinstance(acceptance_root, Path) or not acceptance_root.is_absolute():
            raise TypeError("acceptance_root must be one absolute Path")
        if type(selected) is not WarehouseW3SelectedCandidateChain:
            raise TypeError("selected must be exact WarehouseW3SelectedCandidateChain")
        if type(require_root_owner) is not bool:
            raise TypeError("require_root_owner must be exact bool")
        launch_id = _launch_id(selected.root_selection.launch_id)
        intents = (
            selected.root_staging_intent,
            selected.candidate_selected_intent,
        )
        receipts = (
            selected.root_staging_receipt,
            selected.candidate_selected_receipt,
        )
        validate_root_transaction(intents, receipts)
        if (
            tuple(intent.phase for intent in intents) != INSTALL_PHASES[:2]
            or tuple(receipt.phase for receipt in receipts) != INSTALL_PHASES[:2]
        ):
            raise WarehouseW3RootCoordinatorError(
                "root selection is not the exact K0/K1 prefix"
            )
        initial = _inspect_w3_root_installation_at(
            acceptance_root,
            launch_id,
            require_root_owner=require_root_owner,
        )
        if initial.state is not RootInstallationState.ABSENT:
            raise WarehouseW3RootCoordinatorError(
                "root installation launch slot is not absent"
            )
        parent = pin_absolute_directory(str(acceptance_root))
        launch_fd = -1
        child_fds: list[int] = []
        started = False
        try:
            if require_root_owner:
                _require_root_owned_chain(parent)
                parent_identity = FileIdentity.from_stat(os.fstat(parent.fd))
                if stat.S_IMODE(parent_identity.mode) != 0o755:
                    raise WarehouseW3RootCoordinatorError(
                        "fixed acceptance root mode differs"
                    )
            try:
                os.stat(launch_id, dir_fd=parent.fd, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise WarehouseW3RootCoordinatorError(
                    "root installation launch slot is not absent"
                )
            started = True
            os.mkdir(launch_id, 0o700, dir_fd=parent.fd)
            launch_fd = os.open(
                launch_id,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=parent.fd,
            )
            if require_root_owner:
                os.fchown(launch_fd, 0, 0)
            for leaf in ("install", "start", "terminal"):
                os.mkdir(leaf, 0o700, dir_fd=launch_fd)
                descriptor = os.open(
                    leaf,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                    dir_fd=launch_fd,
                )
                child_fds.append(descriptor)
                if require_root_owner:
                    os.fchown(descriptor, 0, 0)
                os.fchmod(descriptor, 0o755)
                os.fsync(descriptor)
            os.fchmod(launch_fd, 0o755)
            os.fsync(launch_fd)
            os.fsync(parent.fd)
        except Exception as exc:
            if started:
                raise WarehouseW3RootCoordinatorError(
                    "fresh root receipt hierarchy is a permanent partial hold"
                ) from exc
            raise
        finally:
            for descriptor in reversed(child_fds):
                os.close(descriptor)
            if launch_fd >= 0:
                os.close(launch_fd)
            parent.close()

        install_path = acceptance_root / launch_id / "install"
        writer = DurableReceiptDirectory(
            install_path,
            require_root=require_root_owner,
        )
        try:
            initial_producers = (
                selected.staged_candidate,
                selected.root_selection,
            )
            for index, (intent, receipt, producer) in enumerate(
                zip(intents, receipts, initial_producers, strict=True)
            ):
                writer.write_no_replace(_PHASE_INTENT_LEAVES[index], intent.raw)
                writer.write_no_replace(_PHASE_EFFECT_LEAVES[index], producer.raw)
                writer.write_no_replace(_PHASE_COMMIT_LEAVES[index], receipt.raw)
            reopened_intents = tuple(
                RootPhaseIntentReceipt.from_bytes(
                    writer.read(_PHASE_INTENT_LEAVES[index])
                )
                for index in range(2)
            )
            reopened_receipts = tuple(
                RootPhaseReceipt.from_bytes(writer.read(_PHASE_COMMIT_LEAVES[index]))
                for index in range(2)
            )
            validate_root_transaction(reopened_intents, reopened_receipts)
            if reopened_intents != intents or reopened_receipts != receipts:
                raise WarehouseW3RootCoordinatorError(
                    "fresh K0/K1 root ledger differs after reopen"
                )
            instance = object.__new__(cls)
            instance._acceptance_root = acceptance_root
            instance._closed = False
            instance._intents = list(reopened_intents)
            instance._launch_id = launch_id
            instance._receipts = list(reopened_receipts)
            instance._require_root_owner = require_root_owner
            instance._selected_candidate = selected
            instance._selection_authority = None
            instance._writer = writer
            writer = None
            return instance
        except Exception as exc:
            raise WarehouseW3RootCoordinatorError(
                "fresh K0/K1 ledger is a permanent partial hold"
            ) from exc
        finally:
            if writer is not None:
                writer.close()

    @property
    def launch_id(self) -> str:
        self._require_open()
        return self._launch_id

    @property
    def phase_intents(self) -> tuple[RootPhaseIntentReceipt, ...]:
        self._require_open()
        return tuple(self._intents)

    @property
    def phase_receipts(self) -> tuple[RootPhaseReceipt, ...]:
        self._require_open()
        return tuple(self._receipts)

    @property
    def selected_candidate(self) -> WarehouseW3SelectedCandidateChain:
        self._require_open()
        self._revalidate_selection()
        if (
            self._selection_authority is not None
            and self._selection_authority.chain != self._selected_candidate
        ):
            raise WarehouseW3RootCoordinatorError(
                "retained selected candidate authority differs"
            )
        return self._selected_candidate

    def _require_open(self) -> None:
        if self._closed:
            raise WarehouseW3RootCoordinatorError("W3 install phase ledger is closed")

    def _revalidate_selection(self) -> None:
        if self._selection_authority is not None:
            self._selection_authority.revalidate()

    def _persist_named_raw(
        self,
        leaf: str,
        raw: bytes,
        *,
        maximum: int = 512 * 1024 * 1024,
    ) -> bytes:
        """Publish one known no-replace fact or verify its exact durable bytes."""

        self._require_open()
        if type(leaf) is not str or leaf not in _INSTALL_LEDGER_LEAVES:
            raise WarehouseW3RootCoordinatorError(
                "root installation receipt leaf differs"
            )
        if (
            type(raw) is not bytes
            or not raw
            or type(maximum) is not int
            or maximum <= 0
            or len(raw) > maximum
        ):
            raise WarehouseW3RootCoordinatorError(
                "root installation receipt bytes differ"
            )
        try:
            reopened = self._writer.read(leaf, maximum=maximum)
        except FileNotFoundError:
            self._writer.write_no_replace(leaf, raw)
            reopened = self._writer.read(leaf, maximum=maximum)
        if reopened != raw:
            raise WarehouseW3RootCoordinatorError(
                "root installation durable receipt differs"
            )
        return reopened

    def apply_phase(
        self,
        phase: RootPhase,
        *,
        effect_authority_sha256: str,
        apply_effect: Callable[[], None],
        reopen_effect: Callable[[], bytes],
    ) -> tuple[RootPhaseIntentReceipt, RootPhaseReceipt]:
        """Append one intent/effect/readback/commit edge with no resume path."""

        self._require_open()
        self._revalidate_selection()
        try:
            phase_index = INSTALL_PHASES.index(phase)
        except ValueError as exc:
            raise WarehouseW3RootCoordinatorError(
                "root phase is outside the fixed W3 transaction"
            ) from exc
        effect_leaf = _PHASE_EFFECT_LEAVES[phase_index]

        def reopen_and_persist_effect() -> bytes:
            raw = reopen_effect()
            if type(raw) is not bytes or not raw:
                raise WarehouseW3RootCoordinatorError(
                    "root phase effect readback is not exact bytes"
                )
            return self._persist_named_raw(effect_leaf, raw)

        intent, receipt = apply_root_phase(
            launch_id=self._launch_id,
            phase=phase,
            effect_authority_sha256=effect_authority_sha256,
            prior_intents=tuple(self._intents),
            prior_receipts=tuple(self._receipts),
            writer=self._writer,
            apply_effect=apply_effect,
            reopen_effect=reopen_and_persist_effect,
        )
        self._intents.append(intent)
        self._receipts.append(receipt)
        self._revalidate_selection()
        return intent, receipt

    def _apply_typed_effect_phase(
        self,
        phase: RootPhase,
        *,
        effect_authority_sha256: str,
        produce_effect: Callable[[], _EffectReceipt],
        expected_type: type[_EffectReceipt],
    ) -> _EffectReceipt:
        """Run one typed producer only after its durable phase intent exists."""

        if not callable(produce_effect) or type(expected_type) is not type:
            raise TypeError("typed phase producer contract differs")
        observed: dict[str, object] = {}

        def apply_effect() -> None:
            producer = produce_effect()
            if type(producer) is not expected_type:
                raise WarehouseW3RootCoordinatorError(
                    f"{phase.value} producer type differs"
                )
            raw = getattr(producer, "raw", None)
            if type(raw) is not bytes or not raw:
                raise WarehouseW3RootCoordinatorError(
                    f"{phase.value} producer bytes differ"
                )
            self._persist_named_raw(phase.value, raw)
            observed["producer"] = producer

        intent, receipt = self.apply_phase(
            phase,
            effect_authority_sha256=effect_authority_sha256,
            apply_effect=apply_effect,
            reopen_effect=lambda: self._writer.read(
                phase.value,
                maximum=512 * 1024 * 1024,
            ),
        )
        producer = observed.get("producer")
        if (
            type(producer) is not expected_type
            or receipt.effect_sha256 != getattr(producer, "raw_sha256", None)
            or intent.effect_authority_sha256 != effect_authority_sha256
        ):
            raise WarehouseW3RootCoordinatorError(
                f"{phase.value} typed phase receipt differs"
            )
        return producer

    def apply_stores_published_phase(
        self,
        *,
        candidate_gate: CandidateGateReceipt,
        authority: AcceptedLaunchAuthority,
        installation: InstallationRecord,
        sealed_store: SealedStoreReceipt,
        environment_content: WarehouseEnvironmentContentReceipt,
        produce_effect: Callable[[], WarehouseW3StoresPublishedReceipt],
    ) -> WarehouseW3StoresPublishedReceipt:
        """Own K2 with authority fixed before either store publication."""

        if not self._receipts:
            raise WarehouseW3RootCoordinatorError(
                "store publication has no predecessor phase"
            )
        effect_authority_sha256 = derive_w3_stores_effect_authority_sha256(
            predecessor=self._receipts[-1],
            candidate_gate=candidate_gate,
            authority=authority,
            installation=installation,
            sealed_store=sealed_store,
            environment_content=environment_content,
        )
        return self._apply_typed_effect_phase(
            RootPhase.STORES_PUBLISHED,
            effect_authority_sha256=effect_authority_sha256,
            produce_effect=produce_effect,
            expected_type=WarehouseW3StoresPublishedReceipt,
        )

    def publish_selected_stores(self) -> WarehouseW3StoresPublishedReceipt:
        """Own the complete production K2 mutation from the retained selection."""

        _require_root()
        selected = self.selected_candidate
        verification = selected.root_staging_verification
        return self.apply_stores_published_phase(
            candidate_gate=selected.closure.gate,
            authority=verification.authority,
            installation=verification.installation,
            sealed_store=verification.sealed_store_receipt,
            environment_content=selected.closure.semantic_environment,
            produce_effect=lambda: _publish_w3_selected_stores(
                selected,
                persist_relocation=lambda raw: self._persist_named_raw(
                    _ENVIRONMENT_RELOCATION_LEAF,
                    raw,
                ),
            ),
        )

    def apply_authority_published_phase(
        self,
        *,
        stores_published: WarehouseW3StoresPublishedReceipt,
        authority: AcceptedLaunchAuthority,
        installation: InstallationRecord,
        runtime_account: WarehouseW3RuntimeAccountReceipt,
        produce_effect: Callable[[], WarehouseW3AuthorityPublishedReceipt],
    ) -> WarehouseW3AuthorityPublishedReceipt:
        """Own K3 with fixed record paths and the exact runtime account."""

        if not self._receipts:
            raise WarehouseW3RootCoordinatorError(
                "authority publication has no predecessor phase"
            )
        effect_authority_sha256 = derive_w3_authority_effect_authority_sha256(
            predecessor=self._receipts[-1],
            stores_published=stores_published,
            authority=authority,
            installation=installation,
            runtime_account=runtime_account,
        )
        return self._apply_typed_effect_phase(
            RootPhase.AUTHORITY_PUBLISHED,
            effect_authority_sha256=effect_authority_sha256,
            produce_effect=produce_effect,
            expected_type=WarehouseW3AuthorityPublishedReceipt,
        )

    def publish_selected_authority(
        self,
        stores_published: WarehouseW3StoresPublishedReceipt,
    ) -> tuple[
        WarehouseW3AuthorityPublishedReceipt,
        WarehouseW3RuntimeAccountReceipt,
    ]:
        """Own production K3 from a freshly reacquired fixed runtime account."""

        _require_root()
        selected = self.selected_candidate
        verification = selected.root_staging_verification
        runtime_account = _acquire_w3_runtime_account()
        published = self.apply_authority_published_phase(
            stores_published=stores_published,
            authority=verification.authority,
            installation=verification.installation,
            runtime_account=runtime_account,
            produce_effect=lambda: _publish_w3_authority_records(
                selected,
                runtime_account,
            ),
        )
        return published, runtime_account

    def apply_projection_mounted_phase(
        self,
        *,
        candidate_gate: CandidateGateReceipt,
        stores_published: WarehouseW3StoresPublishedReceipt,
        authority_published: WarehouseW3AuthorityPublishedReceipt,
        installation: InstallationRecord,
        namespace_pair: MountNamespacePair,
        boot_id: str,
        produce_effect: Callable[[], WarehouseW3ProjectionReceipt],
    ) -> WarehouseW3ProjectionReceipt:
        """Own K4 with namespace and destination authority fixed pre-mount."""

        if not self._receipts:
            raise WarehouseW3RootCoordinatorError(
                "projection mount has no predecessor phase"
            )
        effect_authority_sha256 = derive_w3_projection_effect_authority_sha256(
            predecessor=self._receipts[-1],
            candidate_gate=candidate_gate,
            stores_published=stores_published,
            authority_published=authority_published,
            installation=installation,
            namespace_pair=namespace_pair,
            boot_id=boot_id,
        )
        return self._apply_typed_effect_phase(
            RootPhase.PROJECTION_MOUNTED,
            effect_authority_sha256=effect_authority_sha256,
            produce_effect=produce_effect,
            expected_type=WarehouseW3ProjectionReceipt,
        )

    def mount_selected_projection(
        self,
        *,
        stores_published: WarehouseW3StoresPublishedReceipt,
        authority_published: WarehouseW3AuthorityPublishedReceipt,
        runtime_account: WarehouseW3RuntimeAccountReceipt,
    ) -> WarehouseW3ProjectionReceipt:
        """Own production K4 after fixing boot and namespace before its intent."""

        _require_root()
        selected = self.selected_candidate
        verification = selected.root_staging_verification
        boot_id, namespace_pair = _acquire_boot_and_mount_namespace(LinuxRootAdapter())
        return self.apply_projection_mounted_phase(
            candidate_gate=selected.closure.gate,
            stores_published=stores_published,
            authority_published=authority_published,
            installation=verification.installation,
            namespace_pair=namespace_pair,
            boot_id=boot_id,
            produce_effect=lambda: _mount_w3_projection(
                selected,
                stores_published,
                authority_published,
                runtime_account,
                boot_id=boot_id,
                namespace_pair=namespace_pair,
            ),
        )

    def apply_units_published_phase(
        self,
        *,
        projection: WarehouseW3ProjectionReceipt,
        authority: AcceptedLaunchAuthority,
        installation: InstallationRecord,
        produce_effect: Callable[[], UnitPublicationReceipt],
    ) -> UnitPublicationReceipt:
        """Own K5 with both exact fragment targets fixed before publication."""

        if not self._receipts:
            raise WarehouseW3RootCoordinatorError(
                "unit publication has no predecessor phase"
            )
        effect_authority_sha256 = derive_w3_units_effect_authority_sha256(
            predecessor=self._receipts[-1],
            projection=projection,
            authority=authority,
            installation=installation,
        )
        return self._apply_typed_effect_phase(
            RootPhase.UNITS_PUBLISHED,
            effect_authority_sha256=effect_authority_sha256,
            produce_effect=produce_effect,
            expected_type=UnitPublicationReceipt,
        )

    def publish_selected_units(
        self,
        projection: WarehouseW3ProjectionReceipt,
    ) -> UnitPublicationReceipt:
        """Own production K5 after the final projection exists."""

        _require_root()
        selected = self.selected_candidate
        verification = selected.root_staging_verification
        return self.apply_units_published_phase(
            projection=projection,
            authority=verification.authority,
            installation=verification.installation,
            produce_effect=lambda: _publish_w3_units(selected, projection),
        )

    def apply_manager_reload_phase(
        self,
        manager: NarrowReloadManager,
        *,
        unit_publication: UnitPublicationReceipt,
    ) -> ManagerReloadReceipt:
        """Own K6 as one Reload bound to the durable UNITS_PUBLISHED prefix."""

        self._require_open()
        if type(unit_publication) is not UnitPublicationReceipt:
            raise TypeError("unit_publication must be exact UnitPublicationReceipt")
        if not self._receipts:
            raise WarehouseW3RootCoordinatorError(
                "manager reload has no predecessor phase"
            )
        authority_sha256 = derive_w3_reload_effect_authority_sha256(
            predecessor=self._receipts[-1],
            unit_publication=unit_publication,
        )
        observed: dict[str, ManagerReloadReceipt] = {}

        def reload_manager() -> None:
            observed["receipt"] = apply_systemd_manager_reload(
                manager,
                unit_publication=unit_publication,
                persist_and_reopen=lambda raw: self._persist_named_raw(
                    RootPhase.MANAGER_RELOADED.value,
                    raw,
                ),
            )

        intent, receipt = self.apply_phase(
            RootPhase.MANAGER_RELOADED,
            effect_authority_sha256=authority_sha256,
            apply_effect=reload_manager,
            reopen_effect=lambda: self._writer.read(
                RootPhase.MANAGER_RELOADED.value,
                maximum=512 * 1024 * 1024,
            ),
        )
        manager_reload = observed.get("receipt")
        if (
            type(manager_reload) is not ManagerReloadReceipt
            or receipt.effect_sha256 != manager_reload.raw_sha256
            or intent.effect_authority_sha256 != authority_sha256
        ):
            raise WarehouseW3RootCoordinatorError(
                "manager reload phase receipt differs"
            )
        return manager_reload

    def apply_loaded_manager_phase(
        self,
        manager: NarrowInstallationManager,
        *,
        unit_publication: UnitPublicationReceipt,
        manager_reload: ManagerReloadReceipt,
        acquire_configured_readback: Callable[[], ConfiguredPairReadback],
        build_prestart_evidence: Callable[
            [
                RootPhaseIntentReceipt,
                ConfiguredPairReadback,
                LoadedManagerReceipt,
            ],
            WarehouseW3PreStartEvidence,
        ],
    ) -> tuple[
        ConfiguredPairReadback,
        LoadedManagerReceipt,
        WarehouseW3PreStartEvidence,
    ]:
        """Own K7 load/readback/evidence ordering under one pending intent."""

        self._require_open()
        if type(unit_publication) is not UnitPublicationReceipt:
            raise TypeError("unit_publication must be exact UnitPublicationReceipt")
        if type(manager_reload) is not ManagerReloadReceipt:
            raise TypeError("manager_reload must be exact ManagerReloadReceipt")
        if not callable(acquire_configured_readback) or not callable(
            build_prestart_evidence
        ):
            raise TypeError(
                "configured readback and prestart evidence builders must be callable"
            )
        reopened_reload = ManagerReloadReceipt.from_bytes(
            manager_reload.raw,
            unit_publication=unit_publication,
        )
        if (
            reopened_reload != manager_reload
            or not self._receipts
            or self._receipts[-1].phase is not RootPhase.MANAGER_RELOADED
            or self._receipts[-1].effect_sha256 != manager_reload.raw_sha256
            or self._writer.read(RootPhase.MANAGER_RELOADED.value) != manager_reload.raw
        ):
            raise WarehouseW3RootCoordinatorError(
                "loaded manager phase reload authority differs"
            )
        expected_pending = RootPhaseIntentReceipt.create(
            launch_id=self._launch_id,
            phase=RootPhase.INSTANCES_LOADED,
            predecessor_sha256=(self._receipts[-1].raw_sha256,),
            effect_authority_sha256=manager_reload.raw_sha256,
        )
        observed: dict[str, object] = {}

        def acquire_readback() -> ConfiguredPairReadback:
            readback = acquire_configured_readback()
            if type(readback) is not ConfiguredPairReadback:
                raise WarehouseW3RootCoordinatorError(
                    "configured pair readback type differs"
                )
            self._persist_named_raw(
                _CONFIGURED_PAIR_READBACK_LEAF,
                readback.raw,
            )
            return readback

        def load_pair_and_build_evidence() -> None:
            readback, loaded = acquire_loaded_manager_pair(
                manager,
                acquire_configured_readback=acquire_readback,
                unit_publication=unit_publication,
                manager_reload=manager_reload,
                persist_and_reopen=lambda raw: self._persist_named_raw(
                    _LOADED_MANAGER_LEAF,
                    raw,
                ),
            )
            evidence = build_prestart_evidence(
                expected_pending,
                readback,
                loaded,
            )
            if type(evidence) is not WarehouseW3PreStartEvidence:
                raise WarehouseW3RootCoordinatorError("prestart evidence type differs")
            self._persist_named_raw(
                RootPhase.INSTANCES_LOADED.value,
                evidence.raw,
            )
            observed["readback"] = readback
            observed["loaded"] = loaded
            observed["evidence"] = evidence

        intent, receipt = self.apply_phase(
            RootPhase.INSTANCES_LOADED,
            effect_authority_sha256=manager_reload.raw_sha256,
            apply_effect=load_pair_and_build_evidence,
            reopen_effect=lambda: self._writer.read(
                RootPhase.INSTANCES_LOADED.value,
                maximum=512 * 1024 * 1024,
            ),
        )
        readback = observed.get("readback")
        loaded = observed.get("loaded")
        evidence = observed.get("evidence")
        if (
            intent != expected_pending
            or type(readback) is not ConfiguredPairReadback
            or type(loaded) is not LoadedManagerReceipt
            or type(evidence) is not WarehouseW3PreStartEvidence
            or loaded.configured_pair_readback_sha256 != readback.raw_sha256
            or receipt.effect_sha256 != evidence.raw_sha256
        ):
            raise WarehouseW3RootCoordinatorError(
                "loaded manager phase receipt differs"
            )
        return readback, loaded, evidence

    def load_selected_instances(
        self,
        manager: NarrowInstallationManager,
        *,
        stores_published: WarehouseW3StoresPublishedReceipt,
        authority_published: WarehouseW3AuthorityPublishedReceipt,
        projection: WarehouseW3ProjectionReceipt,
        unit_publication: UnitPublicationReceipt,
        manager_reload: ManagerReloadReceipt,
        runtime_account: WarehouseW3RuntimeAccountReceipt,
    ) -> tuple[
        ConfiguredPairReadback,
        LoadedManagerReceipt,
        WarehouseW3PreStartEvidence,
    ]:
        """Own production K7 configured readback and problem prestart closure."""

        _require_root()
        selected = self.selected_candidate
        installation = selected.root_staging_verification.installation
        run_raw, close_raw, _run_publication, _close_publication = (
            _reopen_w3_unit_publications(selected, unit_publication)
        )
        prior_intents = self.phase_intents
        prior_receipts = self.phase_receipts
        return self.apply_loaded_manager_phase(
            manager,
            unit_publication=unit_publication,
            manager_reload=manager_reload,
            acquire_configured_readback=lambda: _acquire_w3_configured_readback(
                manager,
                installation,
                run_template_raw=run_raw,
                close_template_raw=close_raw,
            ),
            build_prestart_evidence=lambda pending, readback, loaded: (
                _build_w3_prestart_evidence(
                    selected,
                    stores_published=stores_published,
                    authority_published=authority_published,
                    projection=projection,
                    unit_publication=unit_publication,
                    manager_reload=manager_reload,
                    loaded_manager=loaded,
                    configured_readback=readback,
                    runtime_account=runtime_account,
                    pending_intent=pending,
                    prior_intents=prior_intents,
                    prior_receipts=prior_receipts,
                    run_template_raw=run_raw,
                    close_template_raw=close_raw,
                )
            ),
        )

    def accept_installed(
        self,
        installed: InstalledAcceptance,
    ) -> tuple[RootPhaseIntentReceipt, RootPhaseReceipt]:
        """Publish top-level installed acceptance as the exact K8 effect."""

        self._require_open()
        if type(installed) is not InstalledAcceptance:
            raise TypeError("installed must be exact InstalledAcceptance")
        reopened = InstalledAcceptance.from_bytes(installed.raw)
        if reopened != installed or installed.launch_id != self._launch_id:
            raise WarehouseW3RootCoordinatorError("installed acceptance object differs")

        def publish() -> None:
            self._writer.write_no_replace(
                _INSTALLED_ACCEPTANCE_LEAF,
                installed.raw,
            )

        return self.apply_phase(
            RootPhase.INSTALLATION_ACCEPTED,
            effect_authority_sha256=installed.raw_sha256,
            apply_effect=publish,
            reopen_effect=lambda: self._writer.read(_INSTALLED_ACCEPTANCE_LEAF),
        )

    def accept_and_seal_selected(
        self,
        selection_replay_inputs: WarehouseW3SelectionReplayInputs,
        *,
        stores_published: WarehouseW3StoresPublishedReceipt,
        authority_published: WarehouseW3AuthorityPublishedReceipt,
        projection: WarehouseW3ProjectionReceipt,
        unit_publication: UnitPublicationReceipt,
        configured_readback: ConfiguredPairReadback,
        manager_reload: ManagerReloadReceipt,
        loaded_manager: LoadedManagerReceipt,
        runtime_account: WarehouseW3RuntimeAccountReceipt,
        prestart_evidence: WarehouseW3PreStartEvidence,
    ) -> tuple[
        WarehouseW3RootInstallationInspection,
        WarehouseW3InstalledAcceptanceBundle,
    ]:
        """Own K8, construct the deep bundle, seal, and reopen ACCEPTED."""

        _require_root()
        selected = self.selected_candidate
        verification = selected.root_staging_verification
        if (
            len(self._intents) != len(INSTALL_PHASES) - 1
            or len(self._receipts) != len(INSTALL_PHASES) - 1
            or self._receipts[-1].effect_sha256 != prestart_evidence.raw_sha256
        ):
            raise WarehouseW3RootCoordinatorError("K8 predecessor transaction differs")
        installed = InstalledAcceptance.create(
            launch_id=self._launch_id,
            authority_sha256=verification.authority.authority_sha256,
            installation_sha256=verification.installation.installation_sha256,
            phase_intents=self.phase_intents,
            phase_receipts=self.phase_receipts,
            problem_state_schema=WAREHOUSE_W3_PRESTART_EVIDENCE_SCHEMA,
            problem_state_sha256=prestart_evidence.raw_sha256,
        )
        self.accept_installed(installed)
        environment_relocation_raw = self._writer.read(
            _ENVIRONMENT_RELOCATION_LEAF,
            maximum=512 * 1024 * 1024,
        )
        inputs = _construct_w3_installed_replay_inputs(
            selected,
            selection_replay_inputs,
            phase_intents=self.phase_intents,
            phase_receipts=self.phase_receipts,
            stores_published=stores_published,
            authority_published=authority_published,
            projection=projection,
            unit_publication=unit_publication,
            configured_readback=configured_readback,
            manager_reload=manager_reload,
            loaded_manager=loaded_manager,
            runtime_account=runtime_account,
            prestart_evidence=prestart_evidence,
            installed_acceptance=installed,
            environment_relocation_raw=environment_relocation_raw,
        )
        bundle = WarehouseW3InstalledAcceptanceBundle.create(
            selection_replay_inputs=selection_replay_inputs,
            installed_replay_inputs=inputs,
        )
        return self.publish_replay_and_seal(bundle), bundle

    def publish_replay_and_seal(
        self,
        bundle: WarehouseW3InstalledAcceptanceBundle,
    ) -> WarehouseW3RootInstallationInspection:
        """Publish the derived replay bundle, seal install/, and reopen ACCEPTED."""

        self._require_open()
        if type(bundle) is not WarehouseW3InstalledAcceptanceBundle:
            raise TypeError("bundle must be exact WarehouseW3InstalledAcceptanceBundle")
        chain = verify_w3_installed_replay(
            bundle.installed_replay_inputs,
            bundle.selection_replay_inputs,
        )
        if (
            chain.phase_intents != tuple(self._intents)
            or chain.phase_receipts != tuple(self._receipts)
            or chain.installed_acceptance.raw
            != self._writer.read(_INSTALLED_ACCEPTANCE_LEAF)
            or chain.configured_pair_readback.raw
            != self._writer.read(
                _CONFIGURED_PAIR_READBACK_LEAF,
                maximum=512 * 1024 * 1024,
            )
            or chain.environment_relocation.raw
            != self._writer.read(
                _ENVIRONMENT_RELOCATION_LEAF,
                maximum=512 * 1024 * 1024,
            )
            or chain.loaded_manager.raw
            != self._writer.read(
                _LOADED_MANAGER_LEAF,
                maximum=512 * 1024 * 1024,
            )
        ):
            raise WarehouseW3RootCoordinatorError(
                "installed replay bundle differs from live K0-K8 ledger"
            )
        self._revalidate_selection()
        self._writer.write_no_replace(_INSTALLED_REPLAY_LEAF, bundle.raw)
        if (
            self._writer.read(
                _INSTALLED_REPLAY_LEAF,
                maximum=512 * 1024 * 1024,
            )
            != bundle.raw
        ):
            raise WarehouseW3RootCoordinatorError(
                "installed replay bundle differs after durable reopen"
            )
        self._writer.close()
        install_path = self._acceptance_root / self._launch_id / "install"
        install = pin_absolute_directory(str(install_path))
        try:
            os.fchmod(install.fd, 0o555)
            os.fsync(install.fd)
        finally:
            install.close()
        self._closed = True
        inspection = _inspect_w3_root_installation_at(
            self._acceptance_root,
            self._launch_id,
            require_root_owner=self._require_root_owner,
        )
        if inspection.state is not RootInstallationState.ACCEPTED:
            raise WarehouseW3RootCoordinatorError(
                "sealed W3 root installation did not reopen as ACCEPTED"
            )
        self._revalidate_selection()
        return inspection

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._writer.close()

    def __enter__(self) -> "WarehouseW3InstallPhaseLedger":
        self._require_open()
        return self

    def __exit__(
        self,
        exc_type: object,
        exc: object,
        traceback: object,
    ) -> None:
        del exc_type, exc, traceback
        self.close()


class _FixedStartAuthorizationAuthority:
    __slots__ = (
        "_authorization",
        "_bundle",
        "_bundle_descriptor",
        "_bundle_identity",
        "_closed",
        "_descriptor",
        "_identity",
        "_parent",
    )

    @classmethod
    def acquire(
        cls,
        launch_id: str,
    ) -> _FixedStartAuthorizationAuthority:
        start = pin_absolute_directory(str(_ACCEPTANCE_ROOT / launch_id / "start"))
        try:
            return cls._acquire_from_start(
                start,
                require_root_owner=True,
            )
        finally:
            start.close()

    @classmethod
    def _acquire_from_start(
        cls,
        start: PinnedDirectory,
        *,
        require_root_owner: bool,
    ) -> _FixedStartAuthorizationAuthority:
        if type(start) is not PinnedDirectory:
            raise TypeError("start must be exact PinnedDirectory")
        if type(require_root_owner) is not bool:
            raise TypeError("require_root_owner must be exact bool")
        if require_root_owner:
            _require_root_owned_chain(start)
        else:
            start.revalidate_mutable_leaf()
        descriptor = -1
        bundle_descriptor = -1
        try:
            descriptor, identity, authorization_raw = _acquire_fixed_receipt(
                start,
                _START_AUTHORIZATION_LEAF,
                maximum=_MAX_RECEIPT_BYTES,
                require_root_owner=require_root_owner,
            )
            bundle_descriptor, bundle_identity, bundle_raw = _acquire_fixed_receipt(
                start,
                _START_GATE_BUNDLE_LEAF,
                maximum=512 * 1024 * 1024,
                require_root_owner=require_root_owner,
            )
            authorization = StartAuthorizationReceipt.from_bytes(authorization_raw)
            bundle = WarehouseW3InstalledStartGateBundle.from_bytes(bundle_raw)
            prospective = ProspectiveStartAuthorizationIntent.from_bytes(
                bundle.prospective_intent_raw
            )
            if (
                bundle.prospective_intent_raw != prospective.raw
                or authorization.prospective_intent_sha256 != prospective.raw_sha256
                or authorization.installed_acceptance_sha256
                != hashlib.sha256(bundle.installed_acceptance_raw).hexdigest()
                or authorization.root_selection_sha256
                != hashlib.sha256(
                    bundle.selection_replay_inputs.root_selection_raw
                ).hexdigest()
            ):
                raise WarehouseW3RootCoordinatorError(
                    "fixed start bundle differs from authorization"
                )
            instance = cls()
            instance._authorization = authorization
            instance._bundle = bundle
            instance._bundle_descriptor = bundle_descriptor
            instance._bundle_identity = bundle_identity
            instance._closed = False
            instance._descriptor = descriptor
            instance._identity = identity
            instance._parent = start.duplicate()
            descriptor = -1
            bundle_descriptor = -1
            instance.revalidate()
            instance.require_unspent()
            return instance
        finally:
            if bundle_descriptor >= 0:
                os.close(bundle_descriptor)
            if descriptor >= 0:
                os.close(descriptor)

    @property
    def authorization(self) -> StartAuthorizationReceipt:
        self.revalidate()
        return self._authorization

    @property
    def bundle(self) -> WarehouseW3InstalledStartGateBundle:
        self.revalidate()
        return self._bundle

    def revalidate(self) -> None:
        if self._closed:
            raise WarehouseW3RootCoordinatorError(
                "fixed START_AUTHORIZED authority is closed"
            )
        self._parent.revalidate_mutable_leaf()
        current = os.fstat(self._descriptor)
        named = os.stat(
            _START_AUTHORIZATION_LEAF,
            dir_fd=self._parent.fd,
            follow_symlinks=False,
        )
        bundle_current = os.fstat(self._bundle_descriptor)
        bundle_named = os.stat(
            _START_GATE_BUNDLE_LEAF,
            dir_fd=self._parent.fd,
            follow_symlinks=False,
        )
        if (
            _signature(current) != self._identity
            or _signature(named) != self._identity
            or _signature(bundle_current) != self._bundle_identity
            or _signature(bundle_named) != self._bundle_identity
        ):
            raise WarehouseW3RootCoordinatorError(
                "fixed START_AUTHORIZED authority drifted"
            )

    def require_unspent(self) -> None:
        self.revalidate()
        for leaf in _START_SPEND_LEAVES:
            try:
                os.stat(
                    leaf,
                    dir_fd=self._parent.fd,
                    follow_symlinks=False,
                )
            except FileNotFoundError:
                continue
            except OSError as exc:
                raise WarehouseW3RootCoordinatorError(
                    "fixed start spend state is ambiguous"
                ) from exc
            raise WarehouseW3RootCoordinatorError(
                "fixed start authorization is already spent"
            )

    def seal_start_directory(self) -> None:
        self.revalidate()
        os.fchmod(self._parent.fd, 0o555)
        os.fsync(self._parent.fd)
        current = os.fstat(self._parent.fd)
        if (
            not stat.S_ISDIR(current.st_mode)
            or stat.S_IMODE(current.st_mode) != 0o555
            or current.st_uid != 0
            or current.st_gid != 0
        ):
            raise WarehouseW3RootCoordinatorError("fixed start directory did not seal")

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        os.close(self._bundle_descriptor)
        os.close(self._descriptor)
        self._parent.close()

    def __enter__(self) -> _FixedStartAuthorizationAuthority:
        self.revalidate()
        return self

    def __exit__(
        self,
        exc_type: object,
        exc: object,
        traceback: object,
    ) -> None:
        del exc_type, exc, traceback
        self.close()


def _verify_installed_authority(
    authority: RootInstalledAcceptanceAuthority,
    manager: NarrowInstallationManager,
) -> LoadedManagerReceipt:
    authority.revalidate()
    reacquire_live_w3_prestart(authority, manager)
    authority.revalidate()
    return authority.chain.loaded_manager


def verify_installed_w3(
    launch_id: str,
) -> RootInstalledAcceptanceAuthority:
    """Acquire the retained fixed-store installation authority."""

    _require_root()
    normalized_launch_id = _launch_id(launch_id)
    inspection = inspect_w3_root_installation(normalized_launch_id)
    if inspection.state is not RootInstallationState.ACCEPTED:
        raise WarehouseW3RootCoordinatorError(
            "fixed W3 root installation is not accepted"
        )
    authority = RootInstalledAcceptanceAuthority.acquire(normalized_launch_id)
    try:
        _verify_installed_authority(
            authority,
            SystemdExternalManager(),
        )
        return authority
    except Exception:
        authority.close()
        raise


def apply_w3_root_installation(
    candidate_root: Path,
) -> WarehouseW3RootInstallationInspection:
    """Run the sole K0-K8 composition and independent loaded-manager reopen."""

    _require_root()
    ledger, selection_replay_inputs = begin_w3_root_installation(candidate_root)
    accepted_bundle: WarehouseW3InstalledAcceptanceBundle | None = None
    try:
        stores_published = ledger.publish_selected_stores()
        authority_published, runtime_account = ledger.publish_selected_authority(
            stores_published
        )
        projection = ledger.mount_selected_projection(
            stores_published=stores_published,
            authority_published=authority_published,
            runtime_account=runtime_account,
        )
        unit_publication = ledger.publish_selected_units(projection)
        manager = SystemdExternalManager()
        manager_reload = ledger.apply_manager_reload_phase(
            manager,
            unit_publication=unit_publication,
        )
        configured_readback, loaded_manager, prestart_evidence = (
            ledger.load_selected_instances(
                manager,
                stores_published=stores_published,
                authority_published=authority_published,
                projection=projection,
                unit_publication=unit_publication,
                manager_reload=manager_reload,
                runtime_account=runtime_account,
            )
        )
        inspection, accepted_bundle = ledger.accept_and_seal_selected(
            selection_replay_inputs,
            stores_published=stores_published,
            authority_published=authority_published,
            projection=projection,
            unit_publication=unit_publication,
            configured_readback=configured_readback,
            manager_reload=manager_reload,
            loaded_manager=loaded_manager,
            runtime_account=runtime_account,
            prestart_evidence=prestart_evidence,
        )
    finally:
        ledger.close()
    if (
        accepted_bundle is None
        or inspection.state is not RootInstallationState.ACCEPTED
    ):
        raise WarehouseW3RootCoordinatorError(
            "root W3 installation did not reach accepted state"
        )
    with verify_installed_w3(inspection.launch_id) as installed_authority:
        if installed_authority.bundle != accepted_bundle:
            raise WarehouseW3RootCoordinatorError(
                "independent installed authority differs after acceptance"
            )
    return inspection


def record_w3_start_authorization(
    launch_id: str,
    *,
    prospective_intent_raw: bytes,
    recorded_at_utc: str,
) -> StartAuthorizationReceipt:
    """Bind and publish START_AUTHORIZED from fixed retained authorities."""

    _require_root()
    normalized_launch_id = _launch_id(launch_id)
    try:
        prospective = ProspectiveStartAuthorizationIntent.from_bytes(
            prospective_intent_raw
        )
        with verify_installed_w3(normalized_launch_id) as installed_authority:
            installed_chain = installed_authority.chain
            installed = installed_chain.installed_acceptance
            selection_inputs = installed_authority.bundle.selection_replay_inputs
            with RootSelectedCandidateAuthority.acquire(
                selection_inputs
            ) as selection_authority:
                authorization = bind_start_authorization(
                    prospective,
                    root_selection_authority=selection_authority,
                    installed_acceptance_authority=installed_authority,
                    recorded_at_utc=recorded_at_utc,
                    unit=(
                        installed_chain.selected_candidate.root_staging_verification.installation.run_unit
                    ),
                )
                if (
                    authorization.launch_id != normalized_launch_id
                    or authorization.installed_acceptance_sha256 != installed.raw_sha256
                ):
                    raise WarehouseW3RootCoordinatorError(
                        "bound start authorization differs from " "fixed installation"
                    )
                prestart_inputs = WarehouseW3PreStartProducerReplayInputs(
                    candidate_gate_raw=(
                        installed_chain.selected_candidate.closure.gate.raw
                    ),
                    dry_root_raw=installed_chain.dry_root.raw,
                    environment_rehash_raw=(installed_chain.environment_rehash.raw),
                    loaded_manager_raw=installed_chain.loaded_manager.raw,
                    prestart_absence_raw=(installed_chain.prestart_absence.raw),
                    runtime_account_raw=installed_chain.runtime_account.raw,
                )
                start_bundle = WarehouseW3InstalledStartGateBundle.create(
                    prospective_intent_raw=prospective.raw,
                    installed_acceptance_raw=installed.raw,
                    prestart_evidence_raw=(installed_chain.prestart_evidence.raw),
                    selection_replay_inputs=selection_inputs,
                    prestart_producer_replay_inputs=prestart_inputs,
                    installed_replay_inputs=(
                        installed_authority.bundle.installed_replay_inputs
                    ),
                )
                start_root = _ACCEPTANCE_ROOT / normalized_launch_id / "start"
                with DurableReceiptDirectory(start_root) as writer:
                    writer.write_no_replace(
                        _START_GATE_BUNDLE_LEAF,
                        start_bundle.raw,
                    )
                    writer.write_no_replace(
                        _START_AUTHORIZATION_LEAF,
                        authorization.raw,
                    )
                    reopened = StartAuthorizationReceipt.from_bytes(
                        writer.read(_START_AUTHORIZATION_LEAF)
                    )
                    reopened_bundle = WarehouseW3InstalledStartGateBundle.from_bytes(
                        writer.read(
                            _START_GATE_BUNDLE_LEAF,
                            maximum=512 * 1024 * 1024,
                        )
                    )
                    selection_authority.revalidate()
                    installed_authority.revalidate()
                if reopened != authorization or reopened_bundle != start_bundle:
                    raise WarehouseW3RootCoordinatorError(
                        "durable START_AUTHORIZED differs after reopen"
                    )
                selection_authority.revalidate()
                installed_authority.revalidate()
                return reopened
    except (
        PermissionError,
        WarehouseW3RootCoordinatorError,
    ):
        raise
    except Exception as exc:
        raise WarehouseW3RootCoordinatorError(
            "fixed installed W3 cannot record start authorization"
        ) from exc


def start_w3(launch_id: str) -> StartDispatchReceipt:
    """Spend one fixed authorization and issue exactly one StartUnit call."""

    _require_root()
    normalized_launch_id = _launch_id(launch_id)
    inspection = inspect_w3_root_installation(normalized_launch_id)
    if inspection.state is not RootInstallationState.ACCEPTED:
        raise WarehouseW3RootCoordinatorError(
            "fixed W3 root installation is not accepted"
        )
    with _FixedStartAuthorizationAuthority.acquire(
        normalized_launch_id
    ) as authorization_authority:
        manager = SystemdExternalManager()
        installed_authority = RootInstalledAcceptanceAuthority.acquire(
            normalized_launch_id
        )
        try:
            loaded_manager = _verify_installed_authority(
                installed_authority,
                manager,
            )
            authorization = authorization_authority.authorization
            start_bundle = authorization_authority.bundle
            chain = installed_authority.chain
            installed = chain.installed_acceptance
            producers = start_bundle.prestart_producer_replay_inputs
            if (
                authorization.launch_id != normalized_launch_id
                or authorization.authority_sha256 != installed.authority_sha256
                or authorization.installation_sha256 != installed.installation_sha256
                or authorization.installed_acceptance_sha256 != installed.raw_sha256
                or start_bundle.installed_acceptance_raw != installed.raw
                or start_bundle.prestart_evidence_raw != chain.prestart_evidence.raw
                or start_bundle.selection_replay_inputs
                != installed_authority.bundle.selection_replay_inputs
                or start_bundle.installed_replay_inputs
                != installed_authority.bundle.installed_replay_inputs
                or producers.candidate_gate_raw
                != chain.selected_candidate.closure.gate.raw
                or producers.dry_root_raw != chain.dry_root.raw
                or producers.environment_rehash_raw != chain.environment_rehash.raw
                or producers.loaded_manager_raw != chain.loaded_manager.raw
                or producers.prestart_absence_raw != chain.prestart_absence.raw
                or producers.runtime_account_raw != chain.runtime_account.raw
            ):
                raise WarehouseW3RootCoordinatorError(
                    "fixed start authorization differs from installation"
                )
            issue = StartIssueReceipt.create_authorized(
                authorization,
                prestart_receipt_sha256=chain.prestart_evidence.raw_sha256,
                manager_identity=loaded_manager.manager_identity,
            )

            def reacquire_prestart(
                current_authorization: StartAuthorizationReceipt,
                current_installed: object,
            ) -> bytes:
                if (
                    current_authorization != authorization
                    or current_installed is not installed
                ):
                    raise WarehouseW3RootCoordinatorError(
                        "start owner dependencies differ"
                    )
                authorization_authority.revalidate()
                installed_authority.revalidate()
                raw = reacquire_live_w3_prestart(
                    installed_authority,
                    manager,
                )
                authorization_authority.revalidate()
                installed_authority.revalidate()
                return raw

            start_root = _ACCEPTANCE_ROOT / normalized_launch_id / "start"
            with DurableReceiptDirectory(start_root) as writer:
                authorization_authority.revalidate()
                authorization_authority.require_unspent()
                installed_authority.revalidate()
                owner = StartPermitOwner(
                    authorization=authorization,
                    installed_acceptance=installed,
                    phase_intents=chain.phase_intents,
                    phase_receipts=chain.phase_receipts,
                    issue=issue,
                    manager=manager,
                    reacquire_prestart=reacquire_prestart,
                    writer=writer,
                )
                receipt = owner.dispatch()
                authorization_authority.revalidate()
                installed_authority.revalidate()
            authorization_authority.seal_start_directory()
            return receipt
        except (
            PermissionError,
            WarehouseW3RootCoordinatorError,
        ):
            raise
        except Exception as exc:
            raise WarehouseW3RootCoordinatorError(
                "fixed installed W3 start could not be dispatched"
            ) from exc
        finally:
            installed_authority.close()


__all__ = [
    "WarehouseW3InstallPhaseLedger",
    "WarehouseW3RootInstallationInspection",
    "WarehouseW3RootCoordinatorError",
    "apply_w3_root_installation",
    "begin_w3_root_installation",
    "inspect_w3_root_installation",
    "record_w3_start_authorization",
    "start_w3",
    "verify_installed_w3",
]
