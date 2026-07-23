"""Canonical Warehouse W3 aggregates for reopened root-installation facts.

This module is deliberately capability-free.  It accepts only exact producer
receipt objects, reopens those objects from their canonical bytes, and closes
the Warehouse-specific role and path inventory.  It performs no filesystem,
mount, manager, or receipt-store mutation.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import PurePosixPath
import re
import stat
from typing import Mapping

from scion.problems.warehouse_delivery.w3_candidate_gate import CandidateGateReceipt
from scion.problems.warehouse_delivery.w3_environment_receipts import (
    EnvironmentRelocationReceipt,
    LiveEnvironmentRehashFact,
    WarehouseEnvironmentContentReceipt,
    derive_final_environment_path,
)
from scion.problems.warehouse_delivery.w3_installation import (
    ACCEPTED_ROOT_INSTALLATION_PLAN_SHA256,
    SealedStoreReceipt,
)
from scion.problems.warehouse_delivery.w3_prestart_facts import (
    WAREHOUSE_W3_PRESTART_EVIDENCE_SCHEMA,
    WarehouseW3DryRootReadinessReceipt,
    WarehouseW3PreStartAbsenceReceipt,
    WarehouseW3RuntimeAccountReceipt,
)
from scion.runtime.execution.external_installation import (
    INSTALL_PHASES,
    LoadedManagerReceipt,
    ManagerReloadReceipt,
    MountBindingReceipt,
    PublishedDirectoryReceipt,
    PublishedRegularFileReceipt,
    PublishedTreeReceipt,
    RootPhaseIntentReceipt,
    RootPhaseReceipt,
    SelectionReceipt,
    UnitPublicationReceipt,
    validate_root_transaction,
)
from scion.runtime.execution.external_linux import (
    FileIdentity,
    ImmutableTreeImportReceipt,
    MountNamespacePair,
)
from scion.runtime.execution.launch_authority import (
    AcceptedLaunchAuthority,
    InstallationRecord,
)

_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_BOOT_ID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-" r"[0-9a-f]{4}-[0-9a-f]{12}\Z"
)

_STAGED_SCHEMA = "scion.w3-root-staged-candidate.v1"
_STORES_SCHEMA = "scion.w3-root-stores-published.v1"
_AUTHORITY_SCHEMA = "scion.w3-root-authority-published.v1"
_PROJECTION_SCHEMA = "scion.w3-root-projection.v1"

_SEALED_ROLE = "sealed"
_ENVIRONMENT_ROLE = "environment"
_AUTHORITY_ROLE = "authority"
_INSTALLATION_ROLE = "installation"
_NONCE_CLAIMS_ROLE = "nonce-claims"
_RUN_ROLE = "run"
_PROJECTION_PARENT_ROLE = "projection-parent"
_PROJECTION_ROOT_ROLE = "projection-root"


class WarehouseW3RootInstallationError(RuntimeError):
    """One root-installation aggregate differs from its exact producer facts."""


def _canonical_json(value: object) -> bytes:
    try:
        return (
            json.dumps(
                value,
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise WarehouseW3RootInstallationError(
            "root-installation aggregate is not canonical JSON data"
        ) from exc


def _decode_canonical(raw: bytes, *, label: str) -> dict[str, object]:
    if type(raw) is not bytes:
        raise TypeError(f"{label} must be exact bytes")

    def mapping(pairs: list[tuple[str, object]]) -> dict[str, object]:
        value: dict[str, object] = {}
        for key, item in pairs:
            if key in value:
                raise ValueError(f"{label} contains a duplicate field")
            value[key] = item
        return value

    try:
        value = json.loads(
            raw.decode("utf-8", "strict"),
            object_pairs_hook=mapping,
            parse_float=lambda _value: (_ for _ in ()).throw(
                ValueError(f"{label} contains a floating-point value")
            ),
            parse_constant=lambda token: (_ for _ in ()).throw(
                ValueError(f"{label} contains {token}")
            ),
        )
    except (UnicodeError, ValueError, TypeError) as exc:
        raise WarehouseW3RootInstallationError(
            f"{label} is not canonical JSON"
        ) from exc
    if type(value) is not dict or _canonical_json(value) != raw:
        raise WarehouseW3RootInstallationError(f"{label} bytes are not canonical")
    return value


def _exact_fields(
    value: object,
    expected: frozenset[str],
    *,
    label: str,
) -> dict[str, object]:
    if (
        type(value) is not dict
        or frozenset(value) != expected
        or any(type(key) is not str for key in value)
    ):
        raise WarehouseW3RootInstallationError(f"{label} fields differ")
    return value


def _sha256(value: object, *, field: str) -> str:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        raise WarehouseW3RootInstallationError(f"{field} is not canonical SHA-256")
    return value


def _boot_id(value: object) -> str:
    if type(value) is not str or _BOOT_ID_RE.fullmatch(value) is None:
        raise WarehouseW3RootInstallationError("boot_id is not canonical")
    return value


def _absolute_path(value: object, *, field: str) -> str:
    if type(value) is not str or not value:
        raise WarehouseW3RootInstallationError(f"{field} is not exact text")
    path = PurePosixPath(value)
    if (
        not path.is_absolute()
        or value == "/"
        or value.startswith("//")
        or str(path) != value
        or ".." in path.parts
    ):
        raise WarehouseW3RootInstallationError(
            f"{field} is not a canonical absolute path"
        )
    return value


def _false_controls(value: Mapping[str, object], *, label: str) -> None:
    if any(value.get(name) is not False for name in ("retry", "resume", "reuse")):
        raise WarehouseW3RootInstallationError(
            f"{label} enables retry, resume, or reuse"
        )


def _identity_mapping(identity: FileIdentity) -> dict[str, int]:
    return identity.to_mapping()


def _reopen_candidate(receipt: CandidateGateReceipt) -> CandidateGateReceipt:
    if type(receipt) is not CandidateGateReceipt:
        raise TypeError("candidate_gate must be exact CandidateGateReceipt")
    reopened = CandidateGateReceipt.from_bytes(receipt.raw)
    if reopened != receipt:
        raise WarehouseW3RootInstallationError("candidate gate object differs")
    return reopened


def _reopen_import(
    receipt: ImmutableTreeImportReceipt,
) -> ImmutableTreeImportReceipt:
    if type(receipt) is not ImmutableTreeImportReceipt:
        raise TypeError("tree_import must be exact ImmutableTreeImportReceipt")
    reopened = ImmutableTreeImportReceipt.from_bytes(receipt.raw)
    if reopened != receipt:
        raise WarehouseW3RootInstallationError("tree import object differs")
    return reopened


def _reopen_authority_pair(
    authority: AcceptedLaunchAuthority,
    installation: InstallationRecord,
) -> tuple[AcceptedLaunchAuthority, InstallationRecord]:
    if type(authority) is not AcceptedLaunchAuthority:
        raise TypeError("authority must be exact AcceptedLaunchAuthority")
    if type(installation) is not InstallationRecord:
        raise TypeError("installation must be exact InstallationRecord")
    reopened_authority = AcceptedLaunchAuthority.from_bytes(authority.raw)
    reopened_installation = InstallationRecord.from_bytes(
        installation.raw,
        reopened_authority,
    )
    if reopened_authority != authority or reopened_installation != installation:
        raise WarehouseW3RootInstallationError(
            "authority or installation object differs"
        )
    return reopened_authority, reopened_installation


def _reopen_sealed(receipt: SealedStoreReceipt) -> SealedStoreReceipt:
    if type(receipt) is not SealedStoreReceipt:
        raise TypeError("sealed_store must be exact SealedStoreReceipt")
    reopened = SealedStoreReceipt.from_bytes(receipt.raw)
    if reopened != receipt:
        raise WarehouseW3RootInstallationError("sealed-store object differs")
    return reopened


def _reopen_semantic(
    receipt: WarehouseEnvironmentContentReceipt,
) -> WarehouseEnvironmentContentReceipt:
    if type(receipt) is not WarehouseEnvironmentContentReceipt:
        raise TypeError(
            "environment_content must be exact WarehouseEnvironmentContentReceipt"
        )
    reopened = WarehouseEnvironmentContentReceipt.from_bytes(
        receipt.raw,
        generic_receipt=receipt.generic_receipt,
        wheel_receipt=receipt.wheel_receipt,
    )
    if reopened != receipt:
        raise WarehouseW3RootInstallationError(
            "Warehouse environment content object differs"
        )
    return reopened


def _reopen_relocation(
    receipt: EnvironmentRelocationReceipt,
    *,
    content: WarehouseEnvironmentContentReceipt,
) -> EnvironmentRelocationReceipt:
    if type(receipt) is not EnvironmentRelocationReceipt:
        raise TypeError(
            "environment_relocation must be exact EnvironmentRelocationReceipt"
        )
    reopened = EnvironmentRelocationReceipt.from_bytes(
        receipt.raw,
        content_receipt=content,
    )
    if reopened != receipt:
        raise WarehouseW3RootInstallationError("environment relocation object differs")
    return reopened


def _reopen_tree(receipt: PublishedTreeReceipt) -> PublishedTreeReceipt:
    if type(receipt) is not PublishedTreeReceipt:
        raise TypeError("published tree must be exact PublishedTreeReceipt")
    reopened = PublishedTreeReceipt.from_bytes(receipt.raw)
    if reopened != receipt:
        raise WarehouseW3RootInstallationError("published tree object differs")
    return reopened


def _reopen_file(
    receipt: PublishedRegularFileReceipt,
) -> PublishedRegularFileReceipt:
    if type(receipt) is not PublishedRegularFileReceipt:
        raise TypeError("published file must be exact PublishedRegularFileReceipt")
    reopened = PublishedRegularFileReceipt.from_bytes(receipt.raw)
    if reopened != receipt:
        raise WarehouseW3RootInstallationError("published file object differs")
    return reopened


def _reopen_directory(
    receipt: PublishedDirectoryReceipt,
) -> PublishedDirectoryReceipt:
    if type(receipt) is not PublishedDirectoryReceipt:
        raise TypeError("published directory must be exact PublishedDirectoryReceipt")
    reopened = PublishedDirectoryReceipt.from_bytes(receipt.raw)
    if reopened != receipt:
        raise WarehouseW3RootInstallationError("published directory object differs")
    return reopened


def _reopen_mount(receipt: MountBindingReceipt) -> MountBindingReceipt:
    if type(receipt) is not MountBindingReceipt:
        raise TypeError("mount binding must be exact MountBindingReceipt")
    reopened = MountBindingReceipt.from_bytes(receipt.raw)
    if reopened != receipt:
        raise WarehouseW3RootInstallationError("mount binding object differs")
    return reopened


def _require_exact_receipt_object(
    receipt: object,
    *,
    expected_type: type[object],
    label: str,
    expected_fields: frozenset[str],
    schema: str,
) -> dict[str, object]:
    """Check one final producer object when its parser needs unavailable inputs."""

    if type(receipt) is not expected_type:
        raise TypeError(f"{label} must be exact {expected_type.__name__}")
    raw = getattr(receipt, "raw", None)
    raw_sha256 = getattr(receipt, "raw_sha256", None)
    if (
        type(raw) is not bytes
        or type(raw_sha256) is not str
        or hashlib.sha256(raw).hexdigest() != raw_sha256
    ):
        raise WarehouseW3RootInstallationError(f"{label} raw identity differs")
    value = _exact_fields(
        _decode_canonical(raw, label=label),
        expected_fields,
        label=label,
    )
    if value.get("schema") != schema:
        raise WarehouseW3RootInstallationError(f"{label} schema differs")
    return value


def _directory_identity_tuple(identity: object) -> tuple[int, int, int, int, int, int]:
    try:
        return (
            identity.device,  # type: ignore[attr-defined]
            identity.inode,  # type: ignore[attr-defined]
            stat.S_IMODE(identity.mode),  # type: ignore[attr-defined]
            identity.uid,  # type: ignore[attr-defined]
            identity.gid,  # type: ignore[attr-defined]
            (
                identity.nlink  # type: ignore[attr-defined]
                if hasattr(identity, "nlink")
                else identity.link_count  # type: ignore[attr-defined]
            ),
        )
    except (AttributeError, TypeError) as exc:
        raise WarehouseW3RootInstallationError(
            "selection directory identity differs"
        ) from exc


def _require_candidate_installation_binding(
    candidate: CandidateGateReceipt,
    authority: AcceptedLaunchAuthority,
    installation: InstallationRecord,
) -> None:
    if (
        candidate.launch_id != installation.launch_id
        or candidate.authority_sha256 != authority.authority_sha256
        or candidate.installation_sha256 != installation.installation_sha256
        or installation.authority_sha256 != authority.authority_sha256
        or candidate.nonce != authority.nonce
    ):
        raise WarehouseW3RootInstallationError(
            "candidate, authority, and installation binding differs"
        )


def _expected_installation_path(installation: InstallationRecord) -> str:
    return f"/var/lib/scion/installations/w3/{installation.launch_id}.json"


def _require_exact_value(
    raw: bytes,
    *,
    expected: dict[str, object],
    fields: frozenset[str],
    label: str,
) -> dict[str, object]:
    value = _exact_fields(_decode_canonical(raw, label=label), fields, label=label)
    _false_controls(value, label=label)
    if _canonical_json(value) != _canonical_json(expected):
        raise WarehouseW3RootInstallationError(f"{label} producer binding differs")
    return value


@dataclass(frozen=True, slots=True, init=False)
class WarehouseW3StagedCandidateReceipt:
    selection_key: str
    launch_id: str
    authority_sha256: str
    installation_sha256: str
    candidate_gate_sha256: str
    tree_import_sha256: str
    candidate_root: str
    source_identity: FileIdentity
    staging_leaf: str
    destination_identity: FileIdentity
    imported_tree_aggregate_sha256: str
    raw: bytes
    raw_sha256: str

    def __new__(cls) -> "WarehouseW3StagedCandidateReceipt":
        del cls
        raise TypeError(
            "WarehouseW3StagedCandidateReceipt must be parsed from exact bytes"
        )

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("WarehouseW3StagedCandidateReceipt is final")

    @classmethod
    def create(
        cls,
        *,
        candidate_gate: CandidateGateReceipt,
        tree_import: ImmutableTreeImportReceipt,
    ) -> "WarehouseW3StagedCandidateReceipt":
        candidate = _reopen_candidate(candidate_gate)
        imported = _reopen_import(tree_import)
        expected = cls._expected(candidate, imported)
        return cls.from_bytes(
            _canonical_json(expected),
            candidate_gate=candidate,
            tree_import=imported,
        )

    @staticmethod
    def _expected(
        candidate: CandidateGateReceipt,
        imported: ImmutableTreeImportReceipt,
    ) -> dict[str, object]:
        source = imported.source_root
        candidate_identity = candidate.candidate_root_identity
        if (
            (
                source.device,
                source.inode,
                stat.S_IMODE(source.mode),
                source.uid,
                source.gid,
                source.link_count,
            )
            != (
                candidate_identity.device,
                candidate_identity.inode,
                candidate_identity.mode,
                candidate_identity.uid,
                candidate_identity.gid,
                candidate_identity.nlink,
            )
            or imported.target_uid != 0
            or imported.target_gid != 0
            or stat.S_IMODE(imported.staging_root.mode) != 0o555
            or imported.staging_root.uid != 0
            or imported.staging_root.gid != 0
        ):
            raise WarehouseW3RootInstallationError(
                "staged candidate source or destination identity differs"
            )
        return {
            "schema": _STAGED_SCHEMA,
            "state": "ROOT_STAGING_IMPORTED",
            "plan_sha256": ACCEPTED_ROOT_INSTALLATION_PLAN_SHA256,
            "selection_key": candidate.selection_key,
            "launch_id": candidate.launch_id,
            "authority_sha256": candidate.authority_sha256,
            "installation_sha256": candidate.installation_sha256,
            "candidate_gate_sha256": candidate.raw_sha256,
            "tree_import_sha256": imported.raw_sha256,
            "candidate_root": candidate.candidate_root,
            "source_identity": _identity_mapping(source),
            "staging_leaf": imported.staging_leaf,
            "destination_identity": _identity_mapping(imported.staging_root),
            "imported_tree_aggregate_sha256": imported.tree_sha256,
            "retry": False,
            "resume": False,
            "reuse": False,
        }

    @classmethod
    def from_bytes(
        cls,
        raw: bytes,
        *,
        candidate_gate: CandidateGateReceipt,
        tree_import: ImmutableTreeImportReceipt,
    ) -> "WarehouseW3StagedCandidateReceipt":
        candidate = _reopen_candidate(candidate_gate)
        imported = _reopen_import(tree_import)
        expected = cls._expected(candidate, imported)
        _require_exact_value(
            raw,
            expected=expected,
            fields=frozenset(expected),
            label="W3 staged candidate receipt",
        )
        instance = object.__new__(cls)
        for field, item in (
            ("selection_key", candidate.selection_key),
            ("launch_id", candidate.launch_id),
            ("authority_sha256", candidate.authority_sha256),
            ("installation_sha256", candidate.installation_sha256),
            ("candidate_gate_sha256", candidate.raw_sha256),
            ("tree_import_sha256", imported.raw_sha256),
            ("candidate_root", candidate.candidate_root),
            ("source_identity", imported.source_root),
            ("staging_leaf", imported.staging_leaf),
            ("destination_identity", imported.staging_root),
            ("imported_tree_aggregate_sha256", imported.tree_sha256),
            ("raw", raw),
            ("raw_sha256", hashlib.sha256(raw).hexdigest()),
        ):
            object.__setattr__(instance, field, item)
        return instance


@dataclass(frozen=True, slots=True, init=False)
class WarehouseW3StoresPublishedReceipt:
    selection_key: str
    launch_id: str
    authority_sha256: str
    installation_sha256: str
    candidate_gate_sha256: str
    sealed_store_sha256: str
    environment_content_sha256: str
    sealed_publication_sha256: str
    environment_publication_sha256: str
    environment_relocation_sha256: str
    sealed_path: str
    environment_path: str
    sealed_tree_aggregate_sha256: str
    environment_tree_aggregate_sha256: str
    raw: bytes
    raw_sha256: str

    def __new__(cls) -> "WarehouseW3StoresPublishedReceipt":
        del cls
        raise TypeError(
            "WarehouseW3StoresPublishedReceipt must be parsed from exact bytes"
        )

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("WarehouseW3StoresPublishedReceipt is final")

    @classmethod
    def create(
        cls,
        *,
        candidate_gate: CandidateGateReceipt,
        authority: AcceptedLaunchAuthority,
        installation: InstallationRecord,
        sealed_store: SealedStoreReceipt,
        environment_content: WarehouseEnvironmentContentReceipt,
        sealed_publication: PublishedTreeReceipt,
        environment_publication: PublishedTreeReceipt,
        environment_relocation: EnvironmentRelocationReceipt,
    ) -> "WarehouseW3StoresPublishedReceipt":
        dependencies = cls._dependencies(
            candidate_gate=candidate_gate,
            authority=authority,
            installation=installation,
            sealed_store=sealed_store,
            environment_content=environment_content,
            sealed_publication=sealed_publication,
            environment_publication=environment_publication,
            environment_relocation=environment_relocation,
        )
        expected = cls._expected(*dependencies)
        return cls.from_bytes(
            _canonical_json(expected),
            candidate_gate=dependencies[0],
            authority=dependencies[1],
            installation=dependencies[2],
            sealed_store=dependencies[3],
            environment_content=dependencies[4],
            sealed_publication=dependencies[5],
            environment_publication=dependencies[6],
            environment_relocation=dependencies[7],
        )

    @staticmethod
    def _dependencies(
        *,
        candidate_gate: CandidateGateReceipt,
        authority: AcceptedLaunchAuthority,
        installation: InstallationRecord,
        sealed_store: SealedStoreReceipt,
        environment_content: WarehouseEnvironmentContentReceipt,
        sealed_publication: PublishedTreeReceipt,
        environment_publication: PublishedTreeReceipt,
        environment_relocation: EnvironmentRelocationReceipt,
    ) -> tuple[
        CandidateGateReceipt,
        AcceptedLaunchAuthority,
        InstallationRecord,
        SealedStoreReceipt,
        WarehouseEnvironmentContentReceipt,
        PublishedTreeReceipt,
        PublishedTreeReceipt,
        EnvironmentRelocationReceipt,
    ]:
        candidate = _reopen_candidate(candidate_gate)
        authority_value, installation_value = _reopen_authority_pair(
            authority,
            installation,
        )
        sealed = _reopen_sealed(sealed_store)
        content = _reopen_semantic(environment_content)
        sealed_tree = _reopen_tree(sealed_publication)
        environment_tree = _reopen_tree(environment_publication)
        relocation = _reopen_relocation(
            environment_relocation,
            content=content,
        )
        _require_candidate_installation_binding(
            candidate,
            authority_value,
            installation_value,
        )
        return (
            candidate,
            authority_value,
            installation_value,
            sealed,
            content,
            sealed_tree,
            environment_tree,
            relocation,
        )

    @staticmethod
    def _expected(
        candidate: CandidateGateReceipt,
        authority: AcceptedLaunchAuthority,
        installation: InstallationRecord,
        sealed: SealedStoreReceipt,
        content: WarehouseEnvironmentContentReceipt,
        sealed_tree: PublishedTreeReceipt,
        environment_tree: PublishedTreeReceipt,
        relocation: EnvironmentRelocationReceipt,
    ) -> dict[str, object]:
        sealed_path = f"/var/lib/scion/sealed/w3/{installation.manifest_sha256}"
        environment_path = str(derive_final_environment_path(content))
        if (
            installation.sealed_root != sealed_path
            or installation.environment_root != environment_path
            or authority.sealed_store_aggregate_sha256 != sealed.aggregate_sha256
            or installation.sealed_store_aggregate_sha256 != sealed.aggregate_sha256
            or authority.environment_receipt_sha256 != content.generic_receipt_sha256
            or installation.environment_receipt_sha256 != content.generic_receipt_sha256
            or candidate.semantic_environment_receipt_sha256 != content.raw_sha256
            or candidate.environment_content_receipt_sha256
            != content.generic_receipt_sha256
            or sealed_tree.role != _SEALED_ROLE
            or sealed_tree.path != sealed_path
            or sealed_tree.source_receipt_sha256 != sealed.raw_sha256
            or sealed_tree.expected_tree_sha256 != sealed.aggregate_sha256
            or sealed_tree.reopened_tree_sha256 != sealed.aggregate_sha256
            or environment_tree.role != _ENVIRONMENT_ROLE
            or environment_tree.path != environment_path
            or environment_tree.source_receipt_sha256 != content.generic_receipt_sha256
            or environment_tree.expected_tree_sha256
            != content.environment_inventory_sha256
            or environment_tree.reopened_tree_sha256
            != content.environment_inventory_sha256
            or relocation.content_receipt_sha256 != content.raw_sha256
            or relocation.final_environment_path != environment_path
        ):
            raise WarehouseW3RootInstallationError(
                "published store role, path, or content binding differs"
            )
        return {
            "schema": _STORES_SCHEMA,
            "state": "STORES_PUBLISHED",
            "plan_sha256": ACCEPTED_ROOT_INSTALLATION_PLAN_SHA256,
            "selection_key": candidate.selection_key,
            "launch_id": installation.launch_id,
            "authority_sha256": authority.authority_sha256,
            "installation_sha256": installation.installation_sha256,
            "candidate_gate_sha256": candidate.raw_sha256,
            "sealed_store_sha256": sealed.raw_sha256,
            "environment_content_sha256": content.raw_sha256,
            "sealed_publication_sha256": sealed_tree.raw_sha256,
            "environment_publication_sha256": environment_tree.raw_sha256,
            "environment_relocation_sha256": relocation.raw_sha256,
            "stores": [
                {
                    "role": _ENVIRONMENT_ROLE,
                    "path": environment_path,
                    "source_receipt_sha256": content.generic_receipt_sha256,
                    "tree_aggregate_sha256": content.environment_inventory_sha256,
                    "publication_sha256": environment_tree.raw_sha256,
                },
                {
                    "role": _SEALED_ROLE,
                    "path": sealed_path,
                    "source_receipt_sha256": sealed.raw_sha256,
                    "tree_aggregate_sha256": sealed.aggregate_sha256,
                    "publication_sha256": sealed_tree.raw_sha256,
                },
            ],
            "retry": False,
            "resume": False,
            "reuse": False,
        }

    @classmethod
    def from_bytes(
        cls,
        raw: bytes,
        *,
        candidate_gate: CandidateGateReceipt,
        authority: AcceptedLaunchAuthority,
        installation: InstallationRecord,
        sealed_store: SealedStoreReceipt,
        environment_content: WarehouseEnvironmentContentReceipt,
        sealed_publication: PublishedTreeReceipt,
        environment_publication: PublishedTreeReceipt,
        environment_relocation: EnvironmentRelocationReceipt,
    ) -> "WarehouseW3StoresPublishedReceipt":
        dependencies = cls._dependencies(
            candidate_gate=candidate_gate,
            authority=authority,
            installation=installation,
            sealed_store=sealed_store,
            environment_content=environment_content,
            sealed_publication=sealed_publication,
            environment_publication=environment_publication,
            environment_relocation=environment_relocation,
        )
        expected = cls._expected(*dependencies)
        _require_exact_value(
            raw,
            expected=expected,
            fields=frozenset(expected),
            label="W3 stores-published receipt",
        )
        (
            candidate,
            authority_value,
            installation_value,
            sealed,
            content,
            sealed_tree,
            environment_tree,
            relocation,
        ) = dependencies
        instance = object.__new__(cls)
        for field, item in (
            ("selection_key", candidate.selection_key),
            ("launch_id", installation_value.launch_id),
            ("authority_sha256", authority_value.authority_sha256),
            ("installation_sha256", installation_value.installation_sha256),
            ("candidate_gate_sha256", candidate.raw_sha256),
            ("sealed_store_sha256", sealed.raw_sha256),
            ("environment_content_sha256", content.raw_sha256),
            ("sealed_publication_sha256", sealed_tree.raw_sha256),
            ("environment_publication_sha256", environment_tree.raw_sha256),
            ("environment_relocation_sha256", relocation.raw_sha256),
            ("sealed_path", sealed_tree.path),
            ("environment_path", environment_tree.path),
            ("sealed_tree_aggregate_sha256", sealed.aggregate_sha256),
            (
                "environment_tree_aggregate_sha256",
                content.environment_inventory_sha256,
            ),
            ("raw", raw),
            ("raw_sha256", hashlib.sha256(raw).hexdigest()),
        ):
            object.__setattr__(instance, field, item)
        return instance


@dataclass(frozen=True, slots=True, init=False)
class WarehouseW3AuthorityPublishedReceipt:
    launch_id: str
    authority_sha256: str
    installation_sha256: str
    authority_publication_sha256: str
    installation_publication_sha256: str
    nonce_directory_sha256: str
    authority_path: str
    installation_path: str
    nonce_ledger_parent: str
    nonce_uid: int
    nonce_gid: int
    raw: bytes
    raw_sha256: str

    def __new__(cls) -> "WarehouseW3AuthorityPublishedReceipt":
        del cls
        raise TypeError(
            "WarehouseW3AuthorityPublishedReceipt must be parsed from exact bytes"
        )

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("WarehouseW3AuthorityPublishedReceipt is final")

    @classmethod
    def create(
        cls,
        *,
        authority: AcceptedLaunchAuthority,
        installation: InstallationRecord,
        authority_publication: PublishedRegularFileReceipt,
        installation_publication: PublishedRegularFileReceipt,
        nonce_directory: PublishedDirectoryReceipt,
    ) -> "WarehouseW3AuthorityPublishedReceipt":
        dependencies = cls._dependencies(
            authority=authority,
            installation=installation,
            authority_publication=authority_publication,
            installation_publication=installation_publication,
            nonce_directory=nonce_directory,
        )
        expected = cls._expected(*dependencies)
        return cls.from_bytes(
            _canonical_json(expected),
            authority=dependencies[0],
            installation=dependencies[1],
            authority_publication=dependencies[2],
            installation_publication=dependencies[3],
            nonce_directory=dependencies[4],
        )

    @staticmethod
    def _dependencies(
        *,
        authority: AcceptedLaunchAuthority,
        installation: InstallationRecord,
        authority_publication: PublishedRegularFileReceipt,
        installation_publication: PublishedRegularFileReceipt,
        nonce_directory: PublishedDirectoryReceipt,
    ) -> tuple[
        AcceptedLaunchAuthority,
        InstallationRecord,
        PublishedRegularFileReceipt,
        PublishedRegularFileReceipt,
        PublishedDirectoryReceipt,
    ]:
        authority_value, installation_value = _reopen_authority_pair(
            authority,
            installation,
        )
        return (
            authority_value,
            installation_value,
            _reopen_file(authority_publication),
            _reopen_file(installation_publication),
            _reopen_directory(nonce_directory),
        )

    @staticmethod
    def _expected(
        authority: AcceptedLaunchAuthority,
        installation: InstallationRecord,
        authority_file: PublishedRegularFileReceipt,
        installation_file: PublishedRegularFileReceipt,
        nonce_directory: PublishedDirectoryReceipt,
    ) -> dict[str, object]:
        installation_path = _expected_installation_path(installation)
        if (
            authority_file.role != _AUTHORITY_ROLE
            or authority_file.path != installation.authority_path
            or authority_file.content_sha256 != authority.authority_sha256
            or authority_file.size_bytes != len(authority.raw)
            or installation_file.role != _INSTALLATION_ROLE
            or installation_file.path != installation_path
            or installation_file.content_sha256 != installation.installation_sha256
            or installation_file.size_bytes != len(installation.raw)
            or nonce_directory.role != _NONCE_CLAIMS_ROLE
            or nonce_directory.path != installation.nonce_ledger_parent
            or nonce_directory.expected_mode != 0o700
            or nonce_directory.mode != 0o700
            or nonce_directory.uid != nonce_directory.expected_uid
            or nonce_directory.gid != nonce_directory.expected_gid
        ):
            raise WarehouseW3RootInstallationError(
                "authority publication role, path, bytes, or ownership differs"
            )
        # This aggregate seals the root producer's exact numeric ownership
        # fact.  Matching it to the caller-configured runtime owner belongs to
        # the later prestart aggregate, which consumes that configuration.
        return {
            "schema": _AUTHORITY_SCHEMA,
            "state": "AUTHORITY_PUBLISHED",
            "plan_sha256": ACCEPTED_ROOT_INSTALLATION_PLAN_SHA256,
            "launch_id": installation.launch_id,
            "authority_sha256": authority.authority_sha256,
            "installation_sha256": installation.installation_sha256,
            "authority_publication_sha256": authority_file.raw_sha256,
            "installation_publication_sha256": installation_file.raw_sha256,
            "nonce_directory_sha256": nonce_directory.raw_sha256,
            "files": [
                {
                    "role": _AUTHORITY_ROLE,
                    "path": installation.authority_path,
                    "content_sha256": authority.authority_sha256,
                    "size_bytes": len(authority.raw),
                    "publication_sha256": authority_file.raw_sha256,
                },
                {
                    "role": _INSTALLATION_ROLE,
                    "path": installation_path,
                    "content_sha256": installation.installation_sha256,
                    "size_bytes": len(installation.raw),
                    "publication_sha256": installation_file.raw_sha256,
                },
            ],
            "nonce_ledger": {
                "role": _NONCE_CLAIMS_ROLE,
                "path": installation.nonce_ledger_parent,
                "mode": 0o700,
                "uid": nonce_directory.uid,
                "gid": nonce_directory.gid,
                "publication_sha256": nonce_directory.raw_sha256,
            },
            "retry": False,
            "resume": False,
            "reuse": False,
        }

    @classmethod
    def from_bytes(
        cls,
        raw: bytes,
        *,
        authority: AcceptedLaunchAuthority,
        installation: InstallationRecord,
        authority_publication: PublishedRegularFileReceipt,
        installation_publication: PublishedRegularFileReceipt,
        nonce_directory: PublishedDirectoryReceipt,
    ) -> "WarehouseW3AuthorityPublishedReceipt":
        dependencies = cls._dependencies(
            authority=authority,
            installation=installation,
            authority_publication=authority_publication,
            installation_publication=installation_publication,
            nonce_directory=nonce_directory,
        )
        expected = cls._expected(*dependencies)
        _require_exact_value(
            raw,
            expected=expected,
            fields=frozenset(expected),
            label="W3 authority-published receipt",
        )
        authority_value, installation_value, authority_file, install_file, nonce = (
            dependencies
        )
        instance = object.__new__(cls)
        for field, item in (
            ("launch_id", installation_value.launch_id),
            ("authority_sha256", authority_value.authority_sha256),
            ("installation_sha256", installation_value.installation_sha256),
            ("authority_publication_sha256", authority_file.raw_sha256),
            ("installation_publication_sha256", install_file.raw_sha256),
            ("nonce_directory_sha256", nonce.raw_sha256),
            ("authority_path", authority_file.path),
            ("installation_path", install_file.path),
            ("nonce_ledger_parent", nonce.path),
            ("nonce_uid", nonce.uid),
            ("nonce_gid", nonce.gid),
            ("raw", raw),
            ("raw_sha256", hashlib.sha256(raw).hexdigest()),
        ):
            object.__setattr__(instance, field, item)
        return instance


@dataclass(frozen=True, slots=True, init=False)
class WarehouseW3ProjectionReceipt:
    launch_id: str
    authority_sha256: str
    installation_sha256: str
    boot_id: str
    namespace_pair: MountNamespacePair
    parent_chain_sha256: tuple[str, ...]
    authority_publication_sha256: str
    installation_publication_sha256: str
    run_mount_sha256: str
    sealed_mount_sha256: str
    environment_mount_sha256: str
    nonce_claims_mount_sha256: str
    run_source_fact_sha256: str
    sealed_source_fact_sha256: str
    environment_source_fact_sha256: str
    nonce_claims_source_fact_sha256: str
    raw: bytes
    raw_sha256: str

    def __new__(cls) -> "WarehouseW3ProjectionReceipt":
        del cls
        raise TypeError("WarehouseW3ProjectionReceipt must be parsed from exact bytes")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("WarehouseW3ProjectionReceipt is final")

    @classmethod
    def create(
        cls,
        *,
        authority: AcceptedLaunchAuthority,
        installation: InstallationRecord,
        candidate_gate: CandidateGateReceipt,
        sealed_publication: PublishedTreeReceipt,
        environment_publication: PublishedTreeReceipt,
        nonce_directory: PublishedDirectoryReceipt,
        namespace_pair: MountNamespacePair,
        destination_parent_chain: tuple[PublishedDirectoryReceipt, ...],
        boot_id: str,
        run_mount: MountBindingReceipt,
        sealed_mount: MountBindingReceipt,
        environment_mount: MountBindingReceipt,
        nonce_claims_mount: MountBindingReceipt,
        authority_publication: PublishedRegularFileReceipt,
        installation_publication: PublishedRegularFileReceipt,
    ) -> "WarehouseW3ProjectionReceipt":
        dependencies = cls._dependencies(
            authority=authority,
            installation=installation,
            candidate_gate=candidate_gate,
            sealed_publication=sealed_publication,
            environment_publication=environment_publication,
            nonce_directory=nonce_directory,
            namespace_pair=namespace_pair,
            destination_parent_chain=destination_parent_chain,
            boot_id=boot_id,
            run_mount=run_mount,
            sealed_mount=sealed_mount,
            environment_mount=environment_mount,
            nonce_claims_mount=nonce_claims_mount,
            authority_publication=authority_publication,
            installation_publication=installation_publication,
        )
        expected = cls._expected(*dependencies)
        return cls.from_bytes(
            _canonical_json(expected),
            authority=dependencies[0],
            installation=dependencies[1],
            candidate_gate=dependencies[2],
            sealed_publication=dependencies[3],
            environment_publication=dependencies[4],
            nonce_directory=dependencies[5],
            namespace_pair=dependencies[6],
            destination_parent_chain=dependencies[7],
            boot_id=dependencies[8],
            run_mount=dependencies[9],
            sealed_mount=dependencies[10],
            environment_mount=dependencies[11],
            nonce_claims_mount=dependencies[12],
            authority_publication=dependencies[13],
            installation_publication=dependencies[14],
        )

    @staticmethod
    def _dependencies(
        *,
        authority: AcceptedLaunchAuthority,
        installation: InstallationRecord,
        candidate_gate: CandidateGateReceipt,
        sealed_publication: PublishedTreeReceipt,
        environment_publication: PublishedTreeReceipt,
        nonce_directory: PublishedDirectoryReceipt,
        namespace_pair: MountNamespacePair,
        destination_parent_chain: tuple[PublishedDirectoryReceipt, ...],
        boot_id: str,
        run_mount: MountBindingReceipt,
        sealed_mount: MountBindingReceipt,
        environment_mount: MountBindingReceipt,
        nonce_claims_mount: MountBindingReceipt,
        authority_publication: PublishedRegularFileReceipt,
        installation_publication: PublishedRegularFileReceipt,
    ) -> tuple[
        AcceptedLaunchAuthority,
        InstallationRecord,
        CandidateGateReceipt,
        PublishedTreeReceipt,
        PublishedTreeReceipt,
        PublishedDirectoryReceipt,
        MountNamespacePair,
        tuple[PublishedDirectoryReceipt, ...],
        str,
        MountBindingReceipt,
        MountBindingReceipt,
        MountBindingReceipt,
        MountBindingReceipt,
        PublishedRegularFileReceipt,
        PublishedRegularFileReceipt,
    ]:
        authority_value, installation_value = _reopen_authority_pair(
            authority,
            installation,
        )
        candidate = _reopen_candidate(candidate_gate)
        _require_candidate_installation_binding(
            candidate,
            authority_value,
            installation_value,
        )
        if type(namespace_pair) is not MountNamespacePair:
            raise TypeError("namespace_pair must be exact MountNamespacePair")
        if not namespace_pair.matches:
            raise WarehouseW3RootInstallationError(
                "self and PID 1 mount namespaces differ"
            )
        if type(destination_parent_chain) is not tuple or any(
            type(item) is not PublishedDirectoryReceipt
            for item in destination_parent_chain
        ):
            raise TypeError(
                "destination_parent_chain must be an exact "
                "PublishedDirectoryReceipt tuple"
            )
        reopened_chain = tuple(
            _reopen_directory(item) for item in destination_parent_chain
        )
        return (
            authority_value,
            installation_value,
            candidate,
            _reopen_tree(sealed_publication),
            _reopen_tree(environment_publication),
            _reopen_directory(nonce_directory),
            namespace_pair,
            reopened_chain,
            _boot_id(boot_id),
            _reopen_mount(run_mount),
            _reopen_mount(sealed_mount),
            _reopen_mount(environment_mount),
            _reopen_mount(nonce_claims_mount),
            _reopen_file(authority_publication),
            _reopen_file(installation_publication),
        )

    @staticmethod
    def _expected(
        authority: AcceptedLaunchAuthority,
        installation: InstallationRecord,
        candidate: CandidateGateReceipt,
        sealed_source: PublishedTreeReceipt,
        environment_source: PublishedTreeReceipt,
        nonce_source: PublishedDirectoryReceipt,
        namespace_pair: MountNamespacePair,
        parent_chain: tuple[PublishedDirectoryReceipt, ...],
        boot_id: str,
        run_mount: MountBindingReceipt,
        sealed_mount: MountBindingReceipt,
        environment_mount: MountBindingReceipt,
        nonce_mount: MountBindingReceipt,
        authority_file: PublishedRegularFileReceipt,
        installation_file: PublishedRegularFileReceipt,
    ) -> dict[str, object]:
        projection_parts = PurePosixPath(installation.projection_root).parts
        expected_parent_paths = tuple(
            str(PurePosixPath(*projection_parts[:index]))
            for index in range(2, len(projection_parts) + 1)
        )
        if (
            tuple(item.path for item in parent_chain) != expected_parent_paths
            or any(
                item.role
                != (
                    _PROJECTION_ROOT_ROLE
                    if index == len(parent_chain) - 1
                    else _PROJECTION_PARENT_ROLE
                )
                for index, item in enumerate(parent_chain)
            )
            or any(
                item.uid != 0
                or item.gid != 0
                or item.expected_uid != 0
                or item.expected_gid != 0
                or item.mode != 0o755
                or item.expected_mode != 0o755
                for item in parent_chain
            )
        ):
            raise WarehouseW3RootInstallationError(
                "projection destination parent chain differs"
            )
        if (
            environment_source.role != _ENVIRONMENT_ROLE
            or environment_source.path != installation.environment_root
            or nonce_source.role != _NONCE_CLAIMS_ROLE
            or nonce_source.path != installation.nonce_ledger_parent
            or candidate.accepted_root != installation.run_root
            or candidate.accepted_root_read_only is not True
            or sealed_source.role != _SEALED_ROLE
            or sealed_source.path != installation.sealed_root
        ):
            raise WarehouseW3RootInstallationError(
                "projection mount source role or path differs"
            )
        mount_expectations = (
            (
                _ENVIRONMENT_ROLE,
                environment_mount,
                installation.projected_environment_root,
                True,
                environment_source,
                environment_source.identity.device,
                environment_source.identity.inode,
            ),
            (
                _NONCE_CLAIMS_ROLE,
                nonce_mount,
                installation.projected_nonce_ledger_parent,
                False,
                nonce_source,
                nonce_source.device,
                nonce_source.inode,
            ),
            (
                _RUN_ROLE,
                run_mount,
                installation.projected_run_root,
                False,
                candidate,
                candidate.accepted_root_identity.device,
                candidate.accepted_root_identity.inode,
            ),
            (
                _SEALED_ROLE,
                sealed_mount,
                installation.projected_sealed_root,
                True,
                sealed_source,
                sealed_source.identity.device,
                sealed_source.identity.inode,
            ),
        )
        if any(
            receipt.mount_point != path or receipt.read_only is not read_only
            for (
                _role,
                receipt,
                path,
                read_only,
                _source,
                _source_device,
                _source_inode,
            ) in mount_expectations
        ):
            raise WarehouseW3RootInstallationError(
                "projection mount path or read-only policy differs"
            )
        if any(
            receipt.source_identity.device != source_device
            or receipt.source_identity.inode != source_inode
            for (
                _role,
                receipt,
                _path,
                _read_only,
                _source,
                source_device,
                source_inode,
            ) in mount_expectations
        ):
            raise WarehouseW3RootInstallationError(
                "projection mount source identity differs"
            )
        authority_path = f"{installation.projection_root}/authority.json"
        installation_path = f"{installation.projection_root}/installation.json"
        if (
            authority_file.role != _AUTHORITY_ROLE
            or authority_file.path != authority_path
            or authority_file.content_sha256 != authority.authority_sha256
            or authority_file.size_bytes != len(authority.raw)
            or installation_file.role != _INSTALLATION_ROLE
            or installation_file.path != installation_path
            or installation_file.content_sha256 != installation.installation_sha256
            or installation_file.size_bytes != len(installation.raw)
        ):
            raise WarehouseW3RootInstallationError(
                "projection regular-file role, path, or bytes differ"
            )
        inventory = [
            {
                "role": _AUTHORITY_ROLE,
                "kind": "regular",
                "path": authority_path,
                "read_only": True,
                "receipt_sha256": authority_file.raw_sha256,
            },
            *(
                {
                    "role": role,
                    "kind": "mount",
                    "path": path,
                    "read_only": read_only,
                    "receipt_sha256": receipt.raw_sha256,
                    "source_fact_sha256": source.raw_sha256,
                    "source_identity": {
                        "device": source_device,
                        "inode": source_inode,
                    },
                }
                for (
                    role,
                    receipt,
                    path,
                    read_only,
                    source,
                    source_device,
                    source_inode,
                ) in mount_expectations[:1]
            ),
            {
                "role": _INSTALLATION_ROLE,
                "kind": "regular",
                "path": installation_path,
                "read_only": True,
                "receipt_sha256": installation_file.raw_sha256,
            },
            *(
                {
                    "role": role,
                    "kind": "mount",
                    "path": path,
                    "read_only": read_only,
                    "receipt_sha256": receipt.raw_sha256,
                    "source_fact_sha256": source.raw_sha256,
                    "source_identity": {
                        "device": source_device,
                        "inode": source_inode,
                    },
                }
                for (
                    role,
                    receipt,
                    path,
                    read_only,
                    source,
                    source_device,
                    source_inode,
                ) in mount_expectations[1:]
            ),
        ]
        roles = tuple(item["role"] for item in inventory)
        if roles != (
            _AUTHORITY_ROLE,
            _ENVIRONMENT_ROLE,
            _INSTALLATION_ROLE,
            _NONCE_CLAIMS_ROLE,
            _RUN_ROLE,
            _SEALED_ROLE,
        ):
            raise AssertionError("projection inventory order is not closed")
        return {
            "schema": _PROJECTION_SCHEMA,
            "state": "PROJECTION_MOUNTED",
            "plan_sha256": ACCEPTED_ROOT_INSTALLATION_PLAN_SHA256,
            "launch_id": installation.launch_id,
            "authority_sha256": authority.authority_sha256,
            "installation_sha256": installation.installation_sha256,
            "boot_id": boot_id,
            "mount_namespaces": {
                "self": {
                    "device": namespace_pair.self_namespace.device,
                    "inode": namespace_pair.self_namespace.inode,
                },
                "pid1": {
                    "device": namespace_pair.pid1_namespace.device,
                    "inode": namespace_pair.pid1_namespace.inode,
                },
            },
            "destination_parent_chain": [
                {
                    "role": item.role,
                    "path": item.path,
                    "device": item.device,
                    "inode": item.inode,
                    "mode": item.mode,
                    "uid": item.uid,
                    "gid": item.gid,
                    "nlink": item.nlink,
                    "receipt_sha256": item.raw_sha256,
                }
                for item in parent_chain
            ],
            "inventory": inventory,
            "retry": False,
            "resume": False,
            "reuse": False,
        }

    @classmethod
    def from_bytes(
        cls,
        raw: bytes,
        *,
        authority: AcceptedLaunchAuthority,
        installation: InstallationRecord,
        candidate_gate: CandidateGateReceipt,
        sealed_publication: PublishedTreeReceipt,
        environment_publication: PublishedTreeReceipt,
        nonce_directory: PublishedDirectoryReceipt,
        namespace_pair: MountNamespacePair,
        destination_parent_chain: tuple[PublishedDirectoryReceipt, ...],
        boot_id: str,
        run_mount: MountBindingReceipt,
        sealed_mount: MountBindingReceipt,
        environment_mount: MountBindingReceipt,
        nonce_claims_mount: MountBindingReceipt,
        authority_publication: PublishedRegularFileReceipt,
        installation_publication: PublishedRegularFileReceipt,
    ) -> "WarehouseW3ProjectionReceipt":
        dependencies = cls._dependencies(
            authority=authority,
            installation=installation,
            candidate_gate=candidate_gate,
            sealed_publication=sealed_publication,
            environment_publication=environment_publication,
            nonce_directory=nonce_directory,
            namespace_pair=namespace_pair,
            destination_parent_chain=destination_parent_chain,
            boot_id=boot_id,
            run_mount=run_mount,
            sealed_mount=sealed_mount,
            environment_mount=environment_mount,
            nonce_claims_mount=nonce_claims_mount,
            authority_publication=authority_publication,
            installation_publication=installation_publication,
        )
        expected = cls._expected(*dependencies)
        _require_exact_value(
            raw,
            expected=expected,
            fields=frozenset(expected),
            label="W3 projection receipt",
        )
        (
            authority_value,
            installation_value,
            candidate,
            sealed_source,
            environment_source,
            nonce_source,
            namespaces,
            parent_chain,
            boot,
            run,
            sealed,
            environment,
            nonce,
            authority_file,
            installation_file,
        ) = dependencies
        instance = object.__new__(cls)
        for field, item in (
            ("launch_id", installation_value.launch_id),
            ("authority_sha256", authority_value.authority_sha256),
            ("installation_sha256", installation_value.installation_sha256),
            ("boot_id", boot),
            ("namespace_pair", namespaces),
            (
                "parent_chain_sha256",
                tuple(item.raw_sha256 for item in parent_chain),
            ),
            ("authority_publication_sha256", authority_file.raw_sha256),
            ("installation_publication_sha256", installation_file.raw_sha256),
            ("run_mount_sha256", run.raw_sha256),
            ("sealed_mount_sha256", sealed.raw_sha256),
            ("environment_mount_sha256", environment.raw_sha256),
            ("nonce_claims_mount_sha256", nonce.raw_sha256),
            ("run_source_fact_sha256", candidate.raw_sha256),
            ("sealed_source_fact_sha256", sealed_source.raw_sha256),
            (
                "environment_source_fact_sha256",
                environment_source.raw_sha256,
            ),
            ("nonce_claims_source_fact_sha256", nonce_source.raw_sha256),
            ("raw", raw),
            ("raw_sha256", hashlib.sha256(raw).hexdigest()),
        ):
            object.__setattr__(instance, field, item)
        return instance


@dataclass(frozen=True, slots=True, init=False)
class WarehouseW3PreStartEvidence:
    launch_id: str
    authority_sha256: str
    installation_sha256: str
    pending_intent_sha256: str
    predecessor_phase_receipt_sha256: str
    phase_effect_sha256: tuple[tuple[str, str], ...]
    producer_receipt_sha256: tuple[tuple[str, str], ...]
    raw: bytes
    raw_sha256: str

    def __new__(cls) -> "WarehouseW3PreStartEvidence":
        del cls
        raise TypeError("WarehouseW3PreStartEvidence must be parsed from exact bytes")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("WarehouseW3PreStartEvidence is final")

    @classmethod
    def create(
        cls,
        *,
        authority: AcceptedLaunchAuthority,
        installation: InstallationRecord,
        candidate_gate: CandidateGateReceipt,
        staged_candidate: WarehouseW3StagedCandidateReceipt,
        selection: SelectionReceipt,
        stores_published: WarehouseW3StoresPublishedReceipt,
        authority_published: WarehouseW3AuthorityPublishedReceipt,
        projection: WarehouseW3ProjectionReceipt,
        unit_publication: UnitPublicationReceipt,
        manager_reload: ManagerReloadReceipt,
        loaded_manager: LoadedManagerReceipt,
        environment_rehash: LiveEnvironmentRehashFact,
        dry_root: WarehouseW3DryRootReadinessReceipt,
        prestart_absence: WarehouseW3PreStartAbsenceReceipt,
        runtime_account: WarehouseW3RuntimeAccountReceipt,
        phase_intents: tuple[RootPhaseIntentReceipt, ...],
        phase_receipts: tuple[RootPhaseReceipt, ...],
    ) -> "WarehouseW3PreStartEvidence":
        expected = cls._expected(
            authority=authority,
            installation=installation,
            candidate_gate=candidate_gate,
            staged_candidate=staged_candidate,
            selection=selection,
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
            phase_intents=phase_intents,
            phase_receipts=phase_receipts,
        )
        return cls.from_bytes(
            _canonical_json(expected),
            authority=authority,
            installation=installation,
            candidate_gate=candidate_gate,
            staged_candidate=staged_candidate,
            selection=selection,
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
            phase_intents=phase_intents,
            phase_receipts=phase_receipts,
        )

    @staticmethod
    def _expected(
        *,
        authority: AcceptedLaunchAuthority,
        installation: InstallationRecord,
        candidate_gate: CandidateGateReceipt,
        staged_candidate: WarehouseW3StagedCandidateReceipt,
        selection: SelectionReceipt,
        stores_published: WarehouseW3StoresPublishedReceipt,
        authority_published: WarehouseW3AuthorityPublishedReceipt,
        projection: WarehouseW3ProjectionReceipt,
        unit_publication: UnitPublicationReceipt,
        manager_reload: ManagerReloadReceipt,
        loaded_manager: LoadedManagerReceipt,
        environment_rehash: LiveEnvironmentRehashFact,
        dry_root: WarehouseW3DryRootReadinessReceipt,
        prestart_absence: WarehouseW3PreStartAbsenceReceipt,
        runtime_account: WarehouseW3RuntimeAccountReceipt,
        phase_intents: tuple[RootPhaseIntentReceipt, ...],
        phase_receipts: tuple[RootPhaseReceipt, ...],
    ) -> dict[str, object]:
        authority_value, installation_value = _reopen_authority_pair(
            authority,
            installation,
        )
        candidate = _reopen_candidate(candidate_gate)
        if type(selection) is not SelectionReceipt:
            raise TypeError("selection must be exact SelectionReceipt")
        selection_value = SelectionReceipt.from_bytes(selection.raw)
        if selection_value != selection:
            raise WarehouseW3RootInstallationError("selection object differs")
        staged_raw = _require_exact_receipt_object(
            staged_candidate,
            expected_type=WarehouseW3StagedCandidateReceipt,
            label="staged_candidate",
            expected_fields=frozenset(
                {
                    "schema",
                    "state",
                    "plan_sha256",
                    "selection_key",
                    "launch_id",
                    "authority_sha256",
                    "installation_sha256",
                    "candidate_gate_sha256",
                    "tree_import_sha256",
                    "candidate_root",
                    "source_identity",
                    "staging_leaf",
                    "destination_identity",
                    "imported_tree_aggregate_sha256",
                    "retry",
                    "resume",
                    "reuse",
                }
            ),
            schema=_STAGED_SCHEMA,
        )
        stores_raw = _require_exact_receipt_object(
            stores_published,
            expected_type=WarehouseW3StoresPublishedReceipt,
            label="stores_published",
            expected_fields=frozenset(
                {
                    "schema",
                    "state",
                    "plan_sha256",
                    "selection_key",
                    "launch_id",
                    "authority_sha256",
                    "installation_sha256",
                    "candidate_gate_sha256",
                    "sealed_store_sha256",
                    "environment_content_sha256",
                    "sealed_publication_sha256",
                    "environment_publication_sha256",
                    "environment_relocation_sha256",
                    "stores",
                    "retry",
                    "resume",
                    "reuse",
                }
            ),
            schema=_STORES_SCHEMA,
        )
        authority_raw = _require_exact_receipt_object(
            authority_published,
            expected_type=WarehouseW3AuthorityPublishedReceipt,
            label="authority_published",
            expected_fields=frozenset(
                {
                    "schema",
                    "state",
                    "plan_sha256",
                    "launch_id",
                    "authority_sha256",
                    "installation_sha256",
                    "authority_publication_sha256",
                    "installation_publication_sha256",
                    "nonce_directory_sha256",
                    "files",
                    "nonce_ledger",
                    "retry",
                    "resume",
                    "reuse",
                }
            ),
            schema=_AUTHORITY_SCHEMA,
        )
        projection_raw = _require_exact_receipt_object(
            projection,
            expected_type=WarehouseW3ProjectionReceipt,
            label="projection",
            expected_fields=frozenset(
                {
                    "schema",
                    "state",
                    "plan_sha256",
                    "launch_id",
                    "authority_sha256",
                    "installation_sha256",
                    "boot_id",
                    "mount_namespaces",
                    "destination_parent_chain",
                    "inventory",
                    "retry",
                    "resume",
                    "reuse",
                }
            ),
            schema=_PROJECTION_SCHEMA,
        )
        unit_raw = _require_exact_receipt_object(
            unit_publication,
            expected_type=UnitPublicationReceipt,
            label="unit_publication",
            expected_fields=frozenset(
                {
                    "schema",
                    "state",
                    "launch_id",
                    "authority_sha256",
                    "installation_sha256",
                    "configured_pair_sha256",
                    "template_derivation_sha256",
                    "run_unit",
                    "close_unit",
                    "run_fragment_path",
                    "close_fragment_path",
                    "run_template_sha256",
                    "close_template_sha256",
                    "run_template_size_bytes",
                    "close_template_size_bytes",
                    "run_publication_sha256",
                    "close_publication_sha256",
                }
            ),
            schema="scion.unit-publication-acceptance.v3",
        )
        reload_raw = _require_exact_receipt_object(
            manager_reload,
            expected_type=ManagerReloadReceipt,
            label="manager_reload",
            expected_fields=frozenset(
                {
                    "schema",
                    "manager",
                    "unit_publication_sha256",
                    "configured_pair_readback_sha256",
                    "configured_pair_sha256",
                }
            ),
            schema="scion.manager-reload.v1",
        )
        loaded_raw = _require_exact_receipt_object(
            loaded_manager,
            expected_type=LoadedManagerReceipt,
            label="loaded_manager",
            expected_fields=frozenset(
                {
                    "schema",
                    "run_unit",
                    "close_unit",
                    "manager",
                    "run_object_path",
                    "close_object_path",
                    "run_properties",
                    "close_properties",
                    "unit_publication_sha256",
                    "configured_pair_readback_sha256",
                    "configured_pair_sha256",
                    "manager_reload_sha256",
                }
            ),
            schema="scion.loaded-manager-acceptance.v4",
        )
        if type(dry_root) is not WarehouseW3DryRootReadinessReceipt:
            raise TypeError("dry_root must be exact WarehouseW3DryRootReadinessReceipt")
        reopened_dry = WarehouseW3DryRootReadinessReceipt.from_bytes(
            dry_root.raw,
            candidate_gate=candidate,
            installation=installation_value,
            observed_identity=dry_root.identity,
            observed_inventory_sha256=dry_root.inventory_sha256,
            observed_inventory_count=dry_root.inventory_count,
            observed_read_only=dry_root.read_only,
            composition_state=dry_root.composition_state,
        )
        if reopened_dry != dry_root:
            raise WarehouseW3RootInstallationError("dry-root object differs")
        if type(prestart_absence) is not WarehouseW3PreStartAbsenceReceipt:
            raise TypeError(
                "prestart_absence must be exact WarehouseW3PreStartAbsenceReceipt"
            )
        reopened_absence = WarehouseW3PreStartAbsenceReceipt.from_bytes(
            prestart_absence.raw,
            authority=authority_value,
            installation=installation_value,
            observations=prestart_absence.observations,
        )
        if reopened_absence != prestart_absence:
            raise WarehouseW3RootInstallationError("pre-start absence object differs")
        if type(runtime_account) is not WarehouseW3RuntimeAccountReceipt:
            raise TypeError(
                "runtime_account must be exact WarehouseW3RuntimeAccountReceipt"
            )
        reopened_account = WarehouseW3RuntimeAccountReceipt.from_bytes(
            runtime_account.raw,
            observed_name=runtime_account.name,
            observed_uid=runtime_account.uid,
            observed_gid=runtime_account.gid,
        )
        if reopened_account != runtime_account:
            raise WarehouseW3RootInstallationError("runtime account object differs")
        if type(environment_rehash) is not LiveEnvironmentRehashFact:
            raise TypeError(
                "environment_rehash must be exact LiveEnvironmentRehashFact"
            )
        rehash = LiveEnvironmentRehashFact.from_bytes(environment_rehash.raw)
        if rehash != environment_rehash:
            raise WarehouseW3RootInstallationError(
                "live environment rehash object differs"
            )
        ordered_intents, ordered_receipts = validate_root_transaction(
            phase_intents,
            phase_receipts,
        )
        pending_phases = INSTALL_PHASES[:8]
        committed_phases = INSTALL_PHASES[:7]
        if (
            len(ordered_intents) != 8
            or len(ordered_receipts) != 7
            or tuple(intent.phase for intent in ordered_intents) != pending_phases
            or tuple(receipt.phase for receipt in ordered_receipts) != committed_phases
        ):
            raise WarehouseW3RootInstallationError(
                "pre-start evidence requires exact pending I7 transaction"
            )
        pending = ordered_intents[-1]
        if (
            pending.predecessor_sha256 != (ordered_receipts[-1].raw_sha256,)
            or pending.effect_authority_sha256 != manager_reload.raw_sha256
        ):
            raise WarehouseW3RootInstallationError(
                "pending I7 predecessor or effect authority differs"
            )
        _require_candidate_installation_binding(
            candidate,
            authority_value,
            installation_value,
        )
        # W3 gives the generic SelectionReceipt candidate slot one exact
        # problem-owned meaning: root selected the fully closed CandidateGate,
        # not the earlier candidate source/header receipt.
        launch_id = installation_value.launch_id
        authority_sha = authority_value.authority_sha256
        installation_sha = installation_value.installation_sha256
        raw_stores = stores_raw["stores"]
        if type(raw_stores) is not list or len(raw_stores) != 2:
            raise WarehouseW3RootInstallationError(
                "stores_published raw inventory differs"
            )
        store_by_role = {
            item.get("role"): item
            for item in raw_stores
            if type(item) is dict and type(item.get("role")) is str
        }
        raw_environment_store = store_by_role.get(_ENVIRONMENT_ROLE)
        raw_sealed_store = store_by_role.get(_SEALED_ROLE)
        raw_nonce_ledger = authority_raw["nonce_ledger"]
        raw_inventory = projection_raw["inventory"]
        if (
            type(raw_environment_store) is not dict
            or type(raw_sealed_store) is not dict
            or frozenset(store_by_role) != frozenset({_ENVIRONMENT_ROLE, _SEALED_ROLE})
            or type(raw_nonce_ledger) is not dict
            or type(raw_inventory) is not list
            or len(raw_inventory) != 6
        ):
            raise WarehouseW3RootInstallationError(
                "pre-start dependency raw inventory differs"
            )
        projection_by_role = {
            item.get("role"): item
            for item in raw_inventory
            if type(item) is dict and type(item.get("role")) is str
        }
        raw_reload_manager = reload_raw["manager"]
        raw_loaded_manager = loaded_raw["manager"]
        if (
            frozenset(projection_by_role)
            != frozenset(
                {
                    _AUTHORITY_ROLE,
                    _ENVIRONMENT_ROLE,
                    _INSTALLATION_ROLE,
                    _NONCE_CLAIMS_ROLE,
                    _RUN_ROLE,
                    _SEALED_ROLE,
                }
            )
            or type(raw_reload_manager) is not dict
            or type(raw_loaded_manager) is not dict
            or type(loaded_raw["run_properties"]) is not dict
            or type(loaded_raw["close_properties"]) is not dict
        ):
            raise WarehouseW3RootInstallationError(
                "pre-start manager or projection raw inventory differs"
            )
        staged_raw_binding = {
            "selection_key": staged_candidate.selection_key,
            "launch_id": staged_candidate.launch_id,
            "authority_sha256": staged_candidate.authority_sha256,
            "installation_sha256": staged_candidate.installation_sha256,
            "candidate_gate_sha256": staged_candidate.candidate_gate_sha256,
            "tree_import_sha256": staged_candidate.tree_import_sha256,
            "candidate_root": staged_candidate.candidate_root,
            "source_identity": _identity_mapping(staged_candidate.source_identity),
            "staging_leaf": staged_candidate.staging_leaf,
            "destination_identity": _identity_mapping(
                staged_candidate.destination_identity
            ),
            "imported_tree_aggregate_sha256": (
                staged_candidate.imported_tree_aggregate_sha256
            ),
        }
        stores_raw_binding = {
            "selection_key": stores_published.selection_key,
            "launch_id": stores_published.launch_id,
            "authority_sha256": stores_published.authority_sha256,
            "installation_sha256": stores_published.installation_sha256,
            "candidate_gate_sha256": stores_published.candidate_gate_sha256,
            "sealed_store_sha256": stores_published.sealed_store_sha256,
            "environment_content_sha256": (stores_published.environment_content_sha256),
            "sealed_publication_sha256": (stores_published.sealed_publication_sha256),
            "environment_publication_sha256": (
                stores_published.environment_publication_sha256
            ),
            "environment_relocation_sha256": (
                stores_published.environment_relocation_sha256
            ),
        }
        authority_raw_binding = {
            "launch_id": authority_published.launch_id,
            "authority_sha256": authority_published.authority_sha256,
            "installation_sha256": authority_published.installation_sha256,
            "authority_publication_sha256": (
                authority_published.authority_publication_sha256
            ),
            "installation_publication_sha256": (
                authority_published.installation_publication_sha256
            ),
            "nonce_directory_sha256": (authority_published.nonce_directory_sha256),
        }
        projection_raw_binding = {
            "launch_id": projection.launch_id,
            "authority_sha256": projection.authority_sha256,
            "installation_sha256": projection.installation_sha256,
            "boot_id": projection.boot_id,
        }
        unit_raw_binding = {
            "launch_id": unit_publication.launch_id,
            "authority_sha256": unit_publication.authority_sha256,
            "installation_sha256": unit_publication.installation_sha256,
            "configured_pair_sha256": (unit_publication.configured_pair_sha256),
            "template_derivation_sha256": (unit_publication.template_derivation_sha256),
            "run_unit": unit_publication.run_unit,
            "close_unit": unit_publication.close_unit,
            "run_fragment_path": unit_publication.run_fragment_path,
            "close_fragment_path": unit_publication.close_fragment_path,
            "run_template_sha256": unit_publication.run_template_sha256,
            "close_template_sha256": unit_publication.close_template_sha256,
            "run_template_size_bytes": unit_publication.run_template_size_bytes,
            "close_template_size_bytes": unit_publication.close_template_size_bytes,
            "run_publication_sha256": (unit_publication.run_publication_sha256),
            "close_publication_sha256": (unit_publication.close_publication_sha256),
        }
        reload_raw_binding = {
            "unit_publication_sha256": manager_reload.unit_publication_sha256,
            "configured_pair_readback_sha256": (
                manager_reload.configured_pair_readback_sha256
            ),
            "configured_pair_sha256": manager_reload.configured_pair_sha256,
        }
        loaded_raw_binding = {
            "run_unit": loaded_manager.run_unit,
            "close_unit": loaded_manager.close_unit,
            "unit_publication_sha256": (loaded_manager.unit_publication_sha256),
            "configured_pair_readback_sha256": (
                loaded_manager.configured_pair_readback_sha256
            ),
            "configured_pair_sha256": loaded_manager.configured_pair_sha256,
            "manager_reload_sha256": loaded_manager.manager_reload_sha256,
        }
        if (
            any(
                value.get("plan_sha256") != ACCEPTED_ROOT_INSTALLATION_PLAN_SHA256
                or value.get("retry") is not False
                or value.get("resume") is not False
                or value.get("reuse") is not False
                or value.get("state") != expected_state
                for value, expected_state in (
                    (staged_raw, "ROOT_STAGING_IMPORTED"),
                    (stores_raw, "STORES_PUBLISHED"),
                    (authority_raw, "AUTHORITY_PUBLISHED"),
                    (projection_raw, "PROJECTION_MOUNTED"),
                )
            )
            or unit_raw.get("state") != "PUBLISHED_REOPENED"
            or any(
                staged_raw.get(name) != item
                for name, item in staged_raw_binding.items()
            )
            or any(
                stores_raw.get(name) != item
                for name, item in stores_raw_binding.items()
            )
            or raw_sealed_store.get("path") != stores_published.sealed_path
            or raw_sealed_store.get("tree_aggregate_sha256")
            != stores_published.sealed_tree_aggregate_sha256
            or raw_sealed_store.get("publication_sha256")
            != stores_published.sealed_publication_sha256
            or raw_environment_store.get("path") != stores_published.environment_path
            or raw_environment_store.get("tree_aggregate_sha256")
            != stores_published.environment_tree_aggregate_sha256
            or raw_environment_store.get("publication_sha256")
            != stores_published.environment_publication_sha256
            or any(
                authority_raw.get(name) != item
                for name, item in authority_raw_binding.items()
            )
            or raw_nonce_ledger.get("uid") != authority_published.nonce_uid
            or raw_nonce_ledger.get("gid") != authority_published.nonce_gid
            or any(
                projection_raw.get(name) != item
                for name, item in projection_raw_binding.items()
            )
            or projection_by_role[_RUN_ROLE].get("source_fact_sha256")
            != projection.run_source_fact_sha256
            or projection_by_role[_SEALED_ROLE].get("source_fact_sha256")
            != projection.sealed_source_fact_sha256
            or projection_by_role[_ENVIRONMENT_ROLE].get("source_fact_sha256")
            != projection.environment_source_fact_sha256
            or projection_by_role[_NONCE_CLAIMS_ROLE].get("source_fact_sha256")
            != projection.nonce_claims_source_fact_sha256
            or any(
                unit_raw.get(name) != item for name, item in unit_raw_binding.items()
            )
            or any(
                reload_raw.get(name) != item
                for name, item in reload_raw_binding.items()
            )
            or raw_reload_manager
            != {
                "unique_owner": manager_reload.manager_identity.unique_owner,
                "boot_id": manager_reload.manager_identity.boot_id,
                "version": manager_reload.manager_identity.version,
            }
            or any(
                loaded_raw.get(name) != item
                for name, item in loaded_raw_binding.items()
            )
            or raw_loaded_manager
            != {
                "unique_owner": loaded_manager.manager_identity.unique_owner,
                "boot_id": loaded_manager.manager_identity.boot_id,
                "version": loaded_manager.manager_identity.version,
            }
            or _canonical_json(loaded_raw["run_properties"])
            != _canonical_json(dict(loaded_manager.run_properties))
            or _canonical_json(loaded_raw["close_properties"])
            != _canonical_json(dict(loaded_manager.close_properties))
        ):
            raise WarehouseW3RootInstallationError(
                "pre-start dependency object differs from canonical raw"
            )
        if (
            staged_candidate.selection_key != candidate.selection_key
            or staged_candidate.launch_id != launch_id
            or staged_candidate.authority_sha256 != authority_sha
            or staged_candidate.installation_sha256 != installation_sha
            or staged_candidate.candidate_gate_sha256 != candidate.raw_sha256
            or staged_candidate.candidate_root != candidate.candidate_root
            or selection_value.selection_key != candidate.selection_key
            or selection_value.launch_id != launch_id
            or selection_value.nonce != authority_value.nonce
            or selection_value.authority_sha256 != authority_sha
            or selection_value.candidate_sha256 != candidate.raw_sha256
            or selection_value.import_receipt_sha256
            != staged_candidate.tree_import_sha256
            or selection_value.imported_staging_aggregate_sha256
            != staged_candidate.imported_tree_aggregate_sha256
            or _directory_identity_tuple(selection_value.source_candidate_identity)
            != _directory_identity_tuple(staged_candidate.source_identity)
            or stores_published.selection_key != candidate.selection_key
            or stores_published.launch_id != launch_id
            or stores_published.authority_sha256 != authority_sha
            or stores_published.installation_sha256 != installation_sha
            or stores_published.candidate_gate_sha256 != candidate.raw_sha256
            or authority_published.launch_id != launch_id
            or authority_published.authority_sha256 != authority_sha
            or authority_published.installation_sha256 != installation_sha
            or projection.launch_id != launch_id
            or projection.authority_sha256 != authority_sha
            or projection.installation_sha256 != installation_sha
            or unit_publication.launch_id != launch_id
            or unit_publication.authority_sha256 != authority_sha
            or unit_publication.installation_sha256 != installation_sha
            or dry_root.candidate_gate_sha256 != candidate.raw_sha256
            or dry_root.launch_id != launch_id
            or dry_root.authority_sha256 != authority_sha
            or dry_root.installation_sha256 != installation_sha
            or prestart_absence.authority_sha256 != authority_sha
            or prestart_absence.installation_sha256 != installation_sha
        ):
            raise WarehouseW3RootInstallationError(
                "pre-start launch, authority, installation, or selection binding differs"
            )
        if (
            projection.run_source_fact_sha256 != candidate.raw_sha256
            or projection.sealed_source_fact_sha256
            != stores_published.sealed_publication_sha256
            or projection.environment_source_fact_sha256
            != stores_published.environment_publication_sha256
            or projection.nonce_claims_source_fact_sha256
            != authority_published.nonce_directory_sha256
        ):
            raise WarehouseW3RootInstallationError(
                "projection source fact binding differs"
            )
        configured_pair_sha = installation_value.configured_pair_sha256
        if (
            unit_publication.run_unit != installation_value.run_unit
            or unit_publication.close_unit != installation_value.close_unit
            or unit_publication.configured_pair_sha256 != configured_pair_sha
            or manager_reload.unit_publication_sha256 != unit_publication.raw_sha256
            or manager_reload.configured_pair_sha256 != configured_pair_sha
            or loaded_manager.run_unit != installation_value.run_unit
            or loaded_manager.close_unit != installation_value.close_unit
            or loaded_manager.unit_publication_sha256 != unit_publication.raw_sha256
            or loaded_manager.configured_pair_readback_sha256
            != manager_reload.configured_pair_readback_sha256
            or loaded_manager.configured_pair_sha256 != configured_pair_sha
            or loaded_manager.manager_reload_sha256 != manager_reload.raw_sha256
            or loaded_manager.manager_identity != manager_reload.manager_identity
            or projection.boot_id != manager_reload.manager_identity.boot_id
            or projection.boot_id != loaded_manager.manager_identity.boot_id
        ):
            raise WarehouseW3RootInstallationError(
                "manager unit, reload, configured pair, identity, or boot binding differs"
            )
        for label, properties in (
            ("run", dict(loaded_manager.run_properties)),
            ("closer", dict(loaded_manager.close_properties)),
        ):
            if (
                properties.get("User") != runtime_account.name
                or properties.get("Group") != runtime_account.name
                or type(properties.get("UMask")) is not int
                or properties["UMask"] != 0o077
            ):
                raise WarehouseW3RootInstallationError(
                    f"loaded {label} runtime account or UMask differs"
                )
        if (
            runtime_account.uid == 0
            or runtime_account.gid == 0
            or runtime_account.uid != authority_published.nonce_uid
            or runtime_account.gid != authority_published.nonce_gid
        ):
            raise WarehouseW3RootInstallationError(
                "runtime account and nonce directory ownership differ"
            )
        if (
            rehash.phase != "preclaim"
            or rehash.content_receipt_sha256
            != candidate.semantic_environment_receipt_sha256
            or rehash.content_receipt_sha256
            != stores_published.environment_content_sha256
            or rehash.generic_receipt_sha256
            != candidate.environment_content_receipt_sha256
            or rehash.environment_root != stores_published.environment_path
            or rehash.environment_inventory_sha256
            != stores_published.environment_tree_aggregate_sha256
        ):
            raise WarehouseW3RootInstallationError(
                "live preclaim environment binding differs"
            )
        effect_producers = (
            staged_candidate,
            selection_value,
            stores_published,
            authority_published,
            projection,
            unit_publication,
            manager_reload,
        )
        if any(
            receipt.effect_sha256 != producer.raw_sha256
            for receipt, producer in zip(
                ordered_receipts,
                effect_producers,
                strict=True,
            )
        ):
            raise WarehouseW3RootInstallationError(
                "pre-start committed phase effect differs"
            )
        phase_effects = {
            receipt.phase.value: receipt.effect_sha256 for receipt in ordered_receipts
        }
        producer_receipts = {
            "candidate_gate": candidate.raw_sha256,
            "dry_root": dry_root.raw_sha256,
            "environment_rehash": rehash.raw_sha256,
            "loaded_manager": loaded_manager.raw_sha256,
            "prestart_absence": prestart_absence.raw_sha256,
            "runtime_account": runtime_account.raw_sha256,
        }
        return {
            "schema": WAREHOUSE_W3_PRESTART_EVIDENCE_SCHEMA,
            "state": "PRESTART_GATES_REACQUIRED_NOT_STARTED",
            "plan_sha256": ACCEPTED_ROOT_INSTALLATION_PLAN_SHA256,
            "launch_id": launch_id,
            "authority_sha256": authority_sha,
            "installation_sha256": installation_sha,
            "pending_intent_sha256": pending.raw_sha256,
            "predecessor_phase_receipt_sha256": ordered_receipts[-1].raw_sha256,
            "phase_effect_sha256": phase_effects,
            "producer_receipt_sha256": producer_receipts,
            "formal_jobs_started": 0,
            "retry": False,
            "resume": False,
            "reuse": False,
        }

    @classmethod
    def from_bytes(
        cls,
        raw: bytes,
        *,
        authority: AcceptedLaunchAuthority,
        installation: InstallationRecord,
        candidate_gate: CandidateGateReceipt,
        staged_candidate: WarehouseW3StagedCandidateReceipt,
        selection: SelectionReceipt,
        stores_published: WarehouseW3StoresPublishedReceipt,
        authority_published: WarehouseW3AuthorityPublishedReceipt,
        projection: WarehouseW3ProjectionReceipt,
        unit_publication: UnitPublicationReceipt,
        manager_reload: ManagerReloadReceipt,
        loaded_manager: LoadedManagerReceipt,
        environment_rehash: LiveEnvironmentRehashFact,
        dry_root: WarehouseW3DryRootReadinessReceipt,
        prestart_absence: WarehouseW3PreStartAbsenceReceipt,
        runtime_account: WarehouseW3RuntimeAccountReceipt,
        phase_intents: tuple[RootPhaseIntentReceipt, ...],
        phase_receipts: tuple[RootPhaseReceipt, ...],
    ) -> "WarehouseW3PreStartEvidence":
        expected = cls._expected(
            authority=authority,
            installation=installation,
            candidate_gate=candidate_gate,
            staged_candidate=staged_candidate,
            selection=selection,
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
            phase_intents=phase_intents,
            phase_receipts=phase_receipts,
        )
        _require_exact_value(
            raw,
            expected=expected,
            fields=frozenset(expected),
            label="W3 pre-start evidence",
        )
        ordered_intents, ordered_receipts = validate_root_transaction(
            phase_intents,
            phase_receipts,
        )
        instance = object.__new__(cls)
        for field, item in (
            ("launch_id", installation.launch_id),
            ("authority_sha256", authority.authority_sha256),
            ("installation_sha256", installation.installation_sha256),
            ("pending_intent_sha256", ordered_intents[-1].raw_sha256),
            (
                "predecessor_phase_receipt_sha256",
                ordered_receipts[-1].raw_sha256,
            ),
            (
                "phase_effect_sha256",
                tuple(
                    (receipt.phase.value, receipt.effect_sha256)
                    for receipt in ordered_receipts
                ),
            ),
            (
                "producer_receipt_sha256",
                tuple(
                    (name, sha256)
                    for name, sha256 in sorted(
                        expected["producer_receipt_sha256"].items()  # type: ignore[union-attr]
                    )
                ),
            ),
            ("raw", raw),
            ("raw_sha256", hashlib.sha256(raw).hexdigest()),
        ):
            object.__setattr__(instance, field, item)
        return instance


__all__ = [
    "WAREHOUSE_W3_PRESTART_EVIDENCE_SCHEMA",
    "WarehouseW3AuthorityPublishedReceipt",
    "WarehouseW3PreStartEvidence",
    "WarehouseW3ProjectionReceipt",
    "WarehouseW3RootInstallationError",
    "WarehouseW3StagedCandidateReceipt",
    "WarehouseW3StoresPublishedReceipt",
]
