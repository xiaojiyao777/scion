"""Root-staging replay for one retained Warehouse W3 candidate ingress.

The non-privileged candidate gate is an acceptance fact, not a capability to
trust arbitrary bytes after privilege changes.  This module keeps the retained
candidate/gate ingress open while it reopens the root-owned imported tree,
parses every candidate-local producer receipt, and independently rederives the
candidate, authority, and installation chain.

Facts outside the immutable candidate (double-wheel, namespace-final execution,
dry-root inspection, and absence observations) cross privilege only in the
fixed ingress closure bundle.  Root reparses that complete producer graph and
binds its candidate verification to the independently replayed imported tree.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat

from scion.problems.warehouse_delivery.w3_candidate_gate import (
    CandidateGateClosureBundle,
    CandidateGateReceipt,
    W3_WHEEL_SEALED_PATH,
)
from scion.problems.warehouse_delivery.w3_candidate_ingress import (
    CandidateGateIngressFact,
    PinnedCandidateGateIngress,
)
from scion.problems.warehouse_delivery.w3_composition import EXPECTED_MANIFEST_NAME
from scion.problems.warehouse_delivery.w3_installation import (
    AuthorityInputAdapter,
    CandidateContentEntry,
    CandidateReceipt,
    CandidateRootIdentity,
    CandidateSelectionCommit,
    CandidateSelectionIntent,
    CandidateVerificationReceipt,
    GitBlobFact,
    GitSourceReceipt,
    GitSourceSnapshot,
    SealedStoreReceipt,
    W3_NATIVE_RECORD_LOGICAL_PATH,
    build_warehouse_installation,
    build_warehouse_launch_authority,
)
from scion.problems.warehouse_delivery.w3_wheel import (
    verify_wheel_bytes_against_receipt,
)
from scion.problems.warehouse_delivery.w3_source_acceptance import (
    RootFixedSourceAcceptanceReceipt,
    W3_SOURCE_ACCEPTANCE_SEALED_PATH,
)
from scion.problems.warehouse_delivery.w3_environment_receipts import (
    verify_namespace_probe_execution_binary,
)
from scion.runtime.execution.environment_integrity import EnvironmentContentReceipt
from scion.runtime.execution.external_linux import (
    FileIdentity,
    ImmutableTreeImportReceipt,
    ImportEntry,
    PinnedDirectory,
    reopen_imported_tree,
)
from scion.runtime.execution.launch_authority import (
    AcceptedLaunchAuthority,
    InstallationRecord,
)

_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_SCHEMA = "scion.w3-root-staging-verification.v2"
_STATE = "ROOT_STAGING_REVERIFIED"
_MAX_FIXED_RECEIPT_BYTES = 32 * 1024 * 1024
_ROOT_INVENTORY = (
    "authority.json",
    "candidate.v1.json",
    "environment",
    "installation.json",
    "receipts",
    "sealed-store",
    "units",
)
_UNIT_INVENTORY = (
    "scion-w3-close@.service",
    "scion-w3@.service",
)
_RECEIPT_INVENTORY = (
    "candidate-verification.v1.json",
    "environment.v1.json",
    "sealed-store.v1.json",
    "selection-committed.v1.json",
    "selection-intent.v1.json",
    "source.v1.json",
)


class WarehouseW3RootStagingError(RuntimeError):
    """The imported candidate or its retained ingress no longer closes."""


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
        raise WarehouseW3RootStagingError(
            "root-staging verification is not canonical JSON data"
        ) from exc


def _decode_canonical(raw: bytes) -> dict[str, object]:
    if type(raw) is not bytes:
        raise TypeError("root-staging verification must be exact bytes")

    def mapping(pairs: list[tuple[str, object]]) -> dict[str, object]:
        value: dict[str, object] = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("root-staging verification has a duplicate field")
            value[key] = item
        return value

    try:
        value = json.loads(
            raw.decode("utf-8", "strict"),
            object_pairs_hook=mapping,
            parse_float=lambda _value: (_ for _ in ()).throw(
                ValueError("root-staging verification contains a float")
            ),
            parse_constant=lambda token: (_ for _ in ()).throw(
                ValueError(f"root-staging verification contains {token}")
            ),
        )
    except (UnicodeError, ValueError, TypeError) as exc:
        raise WarehouseW3RootStagingError(
            "root-staging verification is not canonical JSON"
        ) from exc
    if type(value) is not dict or _canonical_json(value) != raw:
        raise WarehouseW3RootStagingError(
            "root-staging verification bytes are not canonical"
        )
    return value


def _sha256(value: object, *, field: str) -> str:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        raise WarehouseW3RootStagingError(f"{field} is not canonical SHA-256")
    return value


def _exact_type(value: object, expected: type[object], *, field: str) -> None:
    if type(value) is not expected:
        raise TypeError(f"{field} must be exact {expected.__name__}")


def _same_source_identity(
    source: FileIdentity,
    candidate: CandidateRootIdentity,
) -> bool:
    return (
        source.device,
        source.inode,
        stat.S_IMODE(source.mode),
        source.uid,
        source.gid,
        source.link_count,
    ) == (
        candidate.device,
        candidate.inode,
        candidate.mode,
        candidate.uid,
        candidate.gid,
        candidate.nlink,
    )


def _same_file_identity(left: FileIdentity, right: FileIdentity) -> bool:
    return left == right


def _direct_inventory(
    entries: dict[str, ImportEntry],
    prefix: str,
) -> tuple[str, ...]:
    depth = len(PurePosixPath(prefix).parts) if prefix else 0
    names = {
        PurePosixPath(path).parts[depth]
        for path in entries
        if (
            (not prefix or path.startswith(f"{prefix}/"))
            and len(PurePosixPath(path).parts) > depth
        )
    }
    return tuple(sorted(names, key=lambda item: item.encode("utf-8")))


def _require_fixed_inventory(entries: dict[str, ImportEntry]) -> None:
    if (
        _direct_inventory(entries, "") != _ROOT_INVENTORY
        or _direct_inventory(entries, "units") != _UNIT_INVENTORY
        or _direct_inventory(entries, "receipts") != _RECEIPT_INVENTORY
    ):
        raise WarehouseW3RootStagingError("imported candidate fixed inventory differs")


def _open_relative_parent(root_fd: int, path: str) -> tuple[int, str]:
    parsed = PurePosixPath(path)
    if (
        parsed.is_absolute()
        or str(parsed) != path
        or not parsed.parts
        or any(part in {"", ".", ".."} for part in parsed.parts)
    ):
        raise WarehouseW3RootStagingError("imported candidate path differs")
    descriptor = os.dup(root_fd)
    try:
        for part in parsed.parts[:-1]:
            child = os.open(
                part,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=descriptor,
            )
            os.close(descriptor)
            descriptor = child
        return descriptor, parsed.parts[-1]
    except BaseException:
        os.close(descriptor)
        raise


def _read_imported_regular(
    root_fd: int,
    entries: dict[str, ImportEntry],
    path: str,
) -> bytes:
    entry = entries.get(path)
    if entry is None or entry.kind != "file" or entry.sha256 is None:
        raise WarehouseW3RootStagingError(
            f"imported candidate regular is absent: {path}"
        )
    if entry.size > _MAX_FIXED_RECEIPT_BYTES:
        raise WarehouseW3RootStagingError(
            f"imported candidate regular exceeds bound: {path}"
        )
    parent_fd, leaf = _open_relative_parent(root_fd, path)
    descriptor = -1
    try:
        descriptor = os.open(
            leaf,
            os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
            dir_fd=parent_fd,
        )
        before = FileIdentity.from_stat(os.fstat(descriptor))
        named_before = FileIdentity.from_stat(
            os.stat(leaf, dir_fd=parent_fd, follow_symlinks=False)
        )
        if not _same_file_identity(
            before, entry.destination_identity
        ) or not _same_file_identity(named_before, entry.destination_identity):
            raise WarehouseW3RootStagingError(
                f"imported candidate regular identity differs: {path}"
            )
        chunks: list[bytes] = []
        total = 0
        digest = hashlib.sha256()
        while True:
            remaining = _MAX_FIXED_RECEIPT_BYTES + 1 - total
            if remaining <= 0:
                raise WarehouseW3RootStagingError(
                    f"imported candidate regular exceeds bound: {path}"
                )
            chunk = os.read(descriptor, min(64 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            digest.update(chunk)
        after = FileIdentity.from_stat(os.fstat(descriptor))
        named_after = FileIdentity.from_stat(
            os.stat(leaf, dir_fd=parent_fd, follow_symlinks=False)
        )
        if (
            after != entry.destination_identity
            or named_after != entry.destination_identity
            or total != entry.size
            or digest.hexdigest() != entry.sha256
        ):
            raise WarehouseW3RootStagingError(
                f"imported candidate regular content differs: {path}"
            )
        return b"".join(chunks)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        os.close(parent_fd)


def _require_inventory_receipt(
    entries: dict[str, ImportEntry],
    *,
    prefix: str,
    inventory: tuple[object, ...],
) -> None:
    expected_paths: set[str] = set()
    for item in inventory:
        try:
            relative = item.path  # type: ignore[attr-defined]
            kind = item.kind  # type: ignore[attr-defined]
            mode = item.mode  # type: ignore[attr-defined]
            size = item.size_bytes  # type: ignore[attr-defined]
            digest = item.sha256  # type: ignore[attr-defined]
        except AttributeError as exc:
            raise WarehouseW3RootStagingError(
                f"{prefix} inventory object differs"
            ) from exc
        path = prefix if relative == "." else f"{prefix}/{relative}"
        expected_paths.add(path)
        entry = entries.get(path)
        expected_kind = "directory" if kind == "directory" else "file"
        if (
            entry is None
            or entry.kind != expected_kind
            or entry.mode != mode
            or entry.size != size
            or entry.sha256 != digest
        ):
            raise WarehouseW3RootStagingError(
                f"imported {prefix} inventory differs: {relative}"
            )
    actual_paths = {
        path for path in entries if path == prefix or path.startswith(f"{prefix}/")
    }
    if actual_paths != expected_paths:
        raise WarehouseW3RootStagingError(
            f"imported {prefix} inventory closure differs"
        )


def _candidate_content(
    entries: dict[str, ImportEntry],
    candidate: CandidateReceipt,
) -> tuple[CandidateContentEntry, ...]:
    content: list[CandidateContentEntry] = []
    for expected in candidate.content_inventory:
        entry = entries.get(expected.path)
        if entry is None:
            raise WarehouseW3RootStagingError(
                f"candidate content path is absent: {expected.path}"
            )
        current = CandidateContentEntry(
            path=entry.path,
            kind="directory" if entry.kind == "directory" else "regular",
            mode=entry.mode,
            size_bytes=entry.size,
            sha256=entry.sha256,
        )
        if current != expected:
            raise WarehouseW3RootStagingError(
                f"candidate content differs: {expected.path}"
            )
        content.append(current)
    return tuple(content)


def _require_imported_regular_raw(
    entries: dict[str, ImportEntry],
    *,
    path: str,
    raw: bytes,
) -> None:
    entry = entries.get(path)
    if (
        entry is None
        or entry.kind != "file"
        or entry.mode != 0o444
        or entry.size != len(raw)
        or entry.sha256 != hashlib.sha256(raw).hexdigest()
    ):
        raise WarehouseW3RootStagingError(
            f"imported candidate producer bytes differ: {path}"
        )


def _require_import_receipt_semantics(
    imported: ImmutableTreeImportReceipt,
    *,
    candidate: CandidateReceipt,
    candidate_verification: CandidateVerificationReceipt,
    source: GitSourceReceipt,
    sealed: SealedStoreReceipt,
    environment: EnvironmentContentReceipt,
    authority: AcceptedLaunchAuthority,
    installation: InstallationRecord,
    intent: CandidateSelectionIntent,
    commit: CandidateSelectionCommit,
) -> tuple[CandidateContentEntry, ...]:
    """Bind an offline import receipt to every candidate-local producer."""

    entries = {entry.path: entry for entry in imported.entries}
    if len(entries) != len(imported.entries):
        raise WarehouseW3RootStagingError("imported candidate entries are not unique")
    _require_fixed_inventory(entries)
    _require_inventory_receipt(
        entries,
        prefix="sealed-store",
        inventory=sealed.inventory,
    )
    _require_inventory_receipt(
        entries,
        prefix="environment",
        inventory=environment.environment_inventory,
    )
    content = _candidate_content(entries, candidate)
    if content != candidate.content_inventory:
        raise WarehouseW3RootStagingError(
            "imported candidate content inventory differs"
        )
    for path, producer_raw in (
        ("authority.json", authority.raw),
        ("candidate.v1.json", candidate.raw),
        ("installation.json", installation.raw),
        ("receipts/candidate-verification.v1.json", candidate_verification.raw),
        ("receipts/environment.v1.json", environment.raw),
        ("receipts/sealed-store.v1.json", sealed.raw),
        ("receipts/selection-committed.v1.json", commit.raw),
        ("receipts/selection-intent.v1.json", intent.raw),
        ("receipts/source.v1.json", source.raw),
    ):
        _require_imported_regular_raw(
            entries,
            path=path,
            raw=producer_raw,
        )
    for path, digest in (
        ("units/scion-w3@.service", authority.run_template_sha256),
        ("units/scion-w3-close@.service", authority.close_template_sha256),
    ):
        entry = entries.get(path)
        if (
            entry is None
            or entry.kind != "file"
            or entry.mode != 0o444
            or entry.sha256 != digest
        ):
            raise WarehouseW3RootStagingError(
                f"imported candidate unit template differs: {path}"
            )
    sealed_by_path = {item.path: item for item in sealed.inventory}
    for identity in source.blobs:
        entry = sealed_by_path.get(f"sealed/{identity.logical_path}")
        if (
            entry is None
            or entry.kind != "regular"
            or entry.sha256 != identity.sha256
            or entry.size_bytes != identity.size_bytes
        ):
            raise WarehouseW3RootStagingError(
                "imported candidate Git source differs from sealed store"
            )
    return content


def _adapter_from_sealed_entry(
    entry: object,
    *,
    logical_path: str,
) -> AuthorityInputAdapter:
    try:
        if (
            entry.kind != "regular"  # type: ignore[attr-defined]
            or entry.provenance is None  # type: ignore[attr-defined]
            or entry.sha256 is None  # type: ignore[attr-defined]
        ):
            raise WarehouseW3RootStagingError(
                "authority input is not one sealed regular"
            )
        return AuthorityInputAdapter(
            logical_path=logical_path,
            sealed_path=entry.path,  # type: ignore[attr-defined]
            sha256=entry.sha256,  # type: ignore[attr-defined]
            size_bytes=entry.size_bytes,  # type: ignore[attr-defined]
            provenance=entry.provenance,  # type: ignore[attr-defined]
        )
    except AttributeError as exc:
        raise WarehouseW3RootStagingError("authority sealed entry differs") from exc


@dataclass(frozen=True, slots=True, init=False)
class WarehouseW3RootStagingVerification:
    """Canonical replay of all facts locally available in imported staging."""

    selection_key: str
    launch_id: str
    candidate_gate_sha256: str
    candidate_gate_closure_sha256: str
    candidate_gate_ingress_fact_sha256: str
    tree_import_sha256: str
    imported_tree_aggregate_sha256: str
    candidate_receipt_sha256: str
    candidate_content_aggregate_sha256: str
    candidate_verification_sha256: str
    source_acceptance_sha256: str
    source_receipt_sha256: str
    sealed_store_receipt_sha256: str
    sealed_store_aggregate_sha256: str
    environment_receipt_sha256: str
    authority_sha256: str
    installation_sha256: str
    selection_intent_sha256: str
    selection_commit_sha256: str
    candidate_receipt: CandidateReceipt
    candidate_verification: CandidateVerificationReceipt
    source_receipt: GitSourceReceipt
    sealed_store_receipt: SealedStoreReceipt
    environment_receipt: EnvironmentContentReceipt
    authority: AcceptedLaunchAuthority
    installation: InstallationRecord
    selection_intent: CandidateSelectionIntent
    selection_commit: CandidateSelectionCommit
    candidate_gate_closure: CandidateGateClosureBundle
    raw: bytes
    raw_sha256: str

    def __new__(cls) -> "WarehouseW3RootStagingVerification":
        del cls
        raise TypeError(
            "WarehouseW3RootStagingVerification must be parsed from exact bytes"
        )

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("WarehouseW3RootStagingVerification is final")

    @classmethod
    def _create(
        cls,
        *,
        candidate_gate: CandidateGateReceipt,
        candidate_gate_closure: CandidateGateClosureBundle,
        candidate_gate_ingress: CandidateGateIngressFact,
        tree_import: ImmutableTreeImportReceipt,
        candidate_receipt: CandidateReceipt,
        candidate_verification: CandidateVerificationReceipt,
        source_receipt: GitSourceReceipt,
        sealed_store_receipt: SealedStoreReceipt,
        environment_receipt: EnvironmentContentReceipt,
        authority: AcceptedLaunchAuthority,
        installation: InstallationRecord,
        selection_intent: CandidateSelectionIntent,
        selection_commit: CandidateSelectionCommit,
    ) -> "WarehouseW3RootStagingVerification":
        value = {
            "schema": _SCHEMA,
            "state": _STATE,
            "selection_key": candidate_gate.selection_key,
            "launch_id": candidate_gate.launch_id,
            "candidate_gate_sha256": candidate_gate.raw_sha256,
            "candidate_gate_closure_sha256": candidate_gate_closure.raw_sha256,
            "candidate_gate_ingress_fact_sha256": candidate_gate_ingress.raw_sha256,
            "tree_import_sha256": tree_import.raw_sha256,
            "imported_tree_aggregate_sha256": tree_import.tree_sha256,
            "candidate_receipt_sha256": candidate_receipt.raw_sha256,
            "candidate_content_aggregate_sha256": (
                candidate_receipt.content_aggregate_sha256
            ),
            "candidate_verification_sha256": candidate_verification.raw_sha256,
            "source_acceptance_sha256": (
                candidate_verification.source_acceptance_sha256
            ),
            "source_receipt_sha256": source_receipt.raw_sha256,
            "sealed_store_receipt_sha256": sealed_store_receipt.raw_sha256,
            "sealed_store_aggregate_sha256": sealed_store_receipt.aggregate_sha256,
            "environment_receipt_sha256": environment_receipt.raw_sha256,
            "authority_sha256": authority.authority_sha256,
            "installation_sha256": installation.installation_sha256,
            "selection_intent_sha256": selection_intent.raw_sha256,
            "selection_commit_sha256": selection_commit.raw_sha256,
            "retry": False,
            "resume": False,
            "reuse": False,
        }
        return cls.from_bytes(
            _canonical_json(value),
            candidate_gate=candidate_gate,
            candidate_gate_closure=candidate_gate_closure,
            candidate_gate_ingress=candidate_gate_ingress,
            tree_import=tree_import,
            candidate_receipt=candidate_receipt,
            candidate_verification=candidate_verification,
            source_receipt=source_receipt,
            sealed_store_receipt=sealed_store_receipt,
            environment_receipt=environment_receipt,
            authority=authority,
            installation=installation,
            selection_intent=selection_intent,
            selection_commit=selection_commit,
        )

    @classmethod
    def from_bytes(
        cls,
        raw: bytes,
        *,
        candidate_gate: CandidateGateReceipt,
        candidate_gate_closure: CandidateGateClosureBundle,
        candidate_gate_ingress: CandidateGateIngressFact,
        tree_import: ImmutableTreeImportReceipt,
        candidate_receipt: CandidateReceipt,
        candidate_verification: CandidateVerificationReceipt,
        source_receipt: GitSourceReceipt,
        sealed_store_receipt: SealedStoreReceipt,
        environment_receipt: EnvironmentContentReceipt,
        authority: AcceptedLaunchAuthority,
        installation: InstallationRecord,
        selection_intent: CandidateSelectionIntent,
        selection_commit: CandidateSelectionCommit,
    ) -> "WarehouseW3RootStagingVerification":
        _exact_type(candidate_gate, CandidateGateReceipt, field="candidate_gate")
        _exact_type(
            candidate_gate_closure,
            CandidateGateClosureBundle,
            field="candidate_gate_closure",
        )
        _exact_type(
            candidate_gate_ingress,
            CandidateGateIngressFact,
            field="candidate_gate_ingress",
        )
        _exact_type(
            tree_import,
            ImmutableTreeImportReceipt,
            field="tree_import",
        )
        gate = CandidateGateReceipt.from_bytes(candidate_gate.raw)
        closure = CandidateGateClosureBundle.from_bytes(candidate_gate_closure.raw)
        ingress = CandidateGateIngressFact.from_bytes(candidate_gate_ingress.raw)
        imported = ImmutableTreeImportReceipt.from_bytes(tree_import.raw)
        candidate_local = CandidateReceipt.from_bytes(candidate_receipt.raw)
        candidate_verification_local = CandidateVerificationReceipt.from_bytes(
            candidate_verification.raw
        )
        source = GitSourceReceipt.from_bytes(source_receipt.raw)
        sealed = SealedStoreReceipt.from_bytes(sealed_store_receipt.raw)
        environment = EnvironmentContentReceipt.from_bytes(environment_receipt.raw)
        authority_value = AcceptedLaunchAuthority.from_bytes(authority.raw)
        installation_value = InstallationRecord.from_bytes(
            installation.raw,
            authority_value,
        )
        intent = CandidateSelectionIntent.from_bytes(selection_intent.raw)
        commit = CandidateSelectionCommit.from_bytes(selection_commit.raw, intent)
        if (
            gate != candidate_gate
            or closure != candidate_gate_closure
            or ingress != candidate_gate_ingress
            or imported != tree_import
            or candidate_local != candidate_receipt
            or candidate_verification_local != candidate_verification
            or source != source_receipt
            or sealed != sealed_store_receipt
            or environment != environment_receipt
            or authority_value != authority
            or installation_value != installation
            or intent != selection_intent
            or commit != selection_commit
        ):
            raise WarehouseW3RootStagingError("root-staging dependency object differs")
        value = _decode_canonical(raw)
        expected_fields = frozenset(
            {
                "schema",
                "state",
                "selection_key",
                "launch_id",
                "candidate_gate_sha256",
                "candidate_gate_closure_sha256",
                "candidate_gate_ingress_fact_sha256",
                "tree_import_sha256",
                "imported_tree_aggregate_sha256",
                "candidate_receipt_sha256",
                "candidate_content_aggregate_sha256",
                "candidate_verification_sha256",
                "source_acceptance_sha256",
                "source_receipt_sha256",
                "sealed_store_receipt_sha256",
                "sealed_store_aggregate_sha256",
                "environment_receipt_sha256",
                "authority_sha256",
                "installation_sha256",
                "selection_intent_sha256",
                "selection_commit_sha256",
                "retry",
                "resume",
                "reuse",
            }
        )
        if frozenset(value) != expected_fields or any(
            type(key) is not str for key in value
        ):
            raise WarehouseW3RootStagingError("root-staging verification fields differ")
        if (
            value["schema"] != _SCHEMA
            or value["state"] != _STATE
            or any(value[name] is not False for name in ("retry", "resume", "reuse"))
            or value["selection_key"] != gate.selection_key
            or value["launch_id"] != gate.launch_id
            or value["candidate_gate_sha256"] != gate.raw_sha256
            or value["candidate_gate_closure_sha256"] != closure.raw_sha256
            or value["candidate_gate_ingress_fact_sha256"] != ingress.raw_sha256
            or value["tree_import_sha256"] != imported.raw_sha256
            or value["imported_tree_aggregate_sha256"] != imported.tree_sha256
            or value["candidate_verification_sha256"]
            != gate.candidate_verification_sha256
            or value["source_acceptance_sha256"] != gate.source_acceptance_sha256
            or value["source_receipt_sha256"] != gate.source_receipt_sha256
            or value["environment_receipt_sha256"]
            != gate.environment_content_receipt_sha256
            or value["authority_sha256"] != gate.authority_sha256
            or value["installation_sha256"] != gate.installation_sha256
            or ingress.selection_key != gate.selection_key
            or ingress.candidate_root != gate.candidate_root
            or ingress.gate_receipt_sha256 != gate.raw_sha256
            or ingress.gate_sha256 != gate.raw_sha256
            or ingress.closure_sha256 != closure.raw_sha256
            or closure.gate != gate
            or closure.candidate_verification != candidate_verification_local
            or imported.source_root != ingress.candidate_identity
            or not _same_source_identity(
                imported.source_root,
                gate.candidate_root_identity,
            )
        ):
            raise WarehouseW3RootStagingError(
                "root-staging verification dependency binding differs"
            )
        hash_fields = (
            "candidate_gate_sha256",
            "candidate_gate_closure_sha256",
            "candidate_gate_ingress_fact_sha256",
            "tree_import_sha256",
            "imported_tree_aggregate_sha256",
            "candidate_receipt_sha256",
            "candidate_content_aggregate_sha256",
            "candidate_verification_sha256",
            "source_acceptance_sha256",
            "source_receipt_sha256",
            "sealed_store_receipt_sha256",
            "sealed_store_aggregate_sha256",
            "environment_receipt_sha256",
            "authority_sha256",
            "installation_sha256",
            "selection_intent_sha256",
            "selection_commit_sha256",
        )
        parsed = {name: _sha256(value[name], field=name) for name in hash_fields}
        imported_content = _require_import_receipt_semantics(
            imported,
            candidate=candidate_local,
            candidate_verification=candidate_verification_local,
            source=source,
            sealed=sealed,
            environment=environment,
            authority=authority_value,
            installation=installation_value,
            intent=intent,
            commit=commit,
        )
        rebuilt_candidate = CandidateReceipt.create(
            intent=intent,
            content_inventory=imported_content,
            sealed_store_receipt=sealed,
            environment_receipt=environment,
            authority=authority_value,
            installation=installation_value,
            selection_commit=commit,
        )
        rebuilt_verification = CandidateVerificationReceipt.create(
            intent=intent,
            selection_commit=commit,
            source_receipt=source,
            sealed_store_receipt=sealed,
            environment_receipt=environment,
            authority=authority_value,
            installation=installation_value,
            candidate_receipt=candidate_local,
        )
        if (
            parsed["candidate_receipt_sha256"] != candidate_local.raw_sha256
            or parsed["candidate_content_aggregate_sha256"]
            != candidate_local.content_aggregate_sha256
            or parsed["candidate_verification_sha256"]
            != candidate_verification_local.raw_sha256
            or parsed["source_acceptance_sha256"]
            != candidate_verification_local.source_acceptance_sha256
            or parsed["source_acceptance_sha256"] != intent.source_acceptance_sha256
            or parsed["source_receipt_sha256"] != source.raw_sha256
            or parsed["sealed_store_receipt_sha256"] != sealed.raw_sha256
            or parsed["sealed_store_aggregate_sha256"] != sealed.aggregate_sha256
            or parsed["environment_receipt_sha256"] != environment.raw_sha256
            or parsed["authority_sha256"] != authority_value.authority_sha256
            or parsed["installation_sha256"] != installation_value.installation_sha256
            or parsed["selection_intent_sha256"] != intent.raw_sha256
            or parsed["selection_commit_sha256"] != commit.raw_sha256
            or rebuilt_candidate != candidate_local
            or rebuilt_verification != candidate_verification_local
            or candidate_local.selection_key != gate.selection_key
            or candidate_local.candidate_root != gate.candidate_root
            or candidate_verification_local.selection_key != gate.selection_key
            or candidate_verification_local.candidate_root_identity
            != gate.candidate_root_identity
            or commit.candidate_root_identity != gate.candidate_root_identity
            or commit.launch_id != gate.launch_id
            or commit.nonce != gate.nonce
            or commit.authority_sha256 != gate.authority_sha256
            or authority_value.authority_sha256 != gate.authority_sha256
            or authority_value.nonce != gate.nonce
            or installation_value.installation_sha256 != gate.installation_sha256
            or installation_value.launch_id != gate.launch_id
            or installation_value.run_root != gate.accepted_root
        ):
            raise WarehouseW3RootStagingError(
                "root-staging typed producer binding differs"
            )
        instance = object.__new__(cls)
        for field, item in (
            ("selection_key", gate.selection_key),
            ("launch_id", gate.launch_id),
            *((name, parsed[name]) for name in hash_fields),
            ("candidate_receipt", candidate_local),
            ("candidate_verification", candidate_verification_local),
            ("source_receipt", source),
            ("sealed_store_receipt", sealed),
            ("environment_receipt", environment),
            ("authority", authority_value),
            ("installation", installation_value),
            ("selection_intent", intent),
            ("selection_commit", commit),
            ("candidate_gate_closure", closure),
            ("raw", raw),
            ("raw_sha256", hashlib.sha256(raw).hexdigest()),
        ):
            object.__setattr__(instance, field, item)
        return instance


def _verify_imported_w3_candidate(
    ingress: PinnedCandidateGateIngress,
    staging_parent: PinnedDirectory,
    tree_import: ImmutableTreeImportReceipt,
) -> WarehouseW3RootStagingVerification:
    """Capability-free semantic core; production enters through the root gate."""

    _exact_type(
        ingress,
        PinnedCandidateGateIngress,
        field="ingress",
    )
    _exact_type(staging_parent, PinnedDirectory, field="staging_parent")
    _exact_type(
        tree_import,
        ImmutableTreeImportReceipt,
        field="tree_import",
    )
    try:
        imported = ImmutableTreeImportReceipt.from_bytes(tree_import.raw)
        if imported != tree_import:
            raise WarehouseW3RootStagingError("tree import object differs")
        ingress.revalidate()
        gate = ingress.gate
        closure = ingress.closure
        verify_namespace_probe_execution_binary(closure.namespace_probe_execution)
        ingress_fact = ingress.fact
        if (
            imported.source_root != ingress_fact.candidate_identity
            or not _same_source_identity(
                imported.source_root,
                gate.candidate_root_identity,
            )
        ):
            raise WarehouseW3RootStagingError(
                "retained candidate differs from imported source"
            )
        reopen_imported_tree(staging_parent, imported)
        entries = {entry.path: entry for entry in imported.entries}
        _require_fixed_inventory(entries)

        named = FileIdentity.from_stat(
            os.stat(
                imported.staging_leaf,
                dir_fd=staging_parent.fd,
                follow_symlinks=False,
            )
        )
        if named != imported.staging_root:
            raise WarehouseW3RootStagingError("imported staging root identity differs")
        root_fd = os.open(
            imported.staging_leaf,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
            dir_fd=staging_parent.fd,
        )
        try:
            if FileIdentity.from_stat(os.fstat(root_fd)) != imported.staging_root:
                raise WarehouseW3RootStagingError(
                    "imported staging descriptor identity differs"
                )
            intent = CandidateSelectionIntent.from_bytes(
                _read_imported_regular(
                    root_fd,
                    entries,
                    "receipts/selection-intent.v1.json",
                )
            )
            commit = CandidateSelectionCommit.from_bytes(
                _read_imported_regular(
                    root_fd,
                    entries,
                    "receipts/selection-committed.v1.json",
                ),
                intent,
            )
            source = GitSourceReceipt.from_bytes(
                _read_imported_regular(
                    root_fd,
                    entries,
                    "receipts/source.v1.json",
                )
            )
            sealed = SealedStoreReceipt.from_bytes(
                _read_imported_regular(
                    root_fd,
                    entries,
                    "receipts/sealed-store.v1.json",
                )
            )
            environment = EnvironmentContentReceipt.from_bytes(
                _read_imported_regular(
                    root_fd,
                    entries,
                    "receipts/environment.v1.json",
                )
            )
            authority = AcceptedLaunchAuthority.from_bytes(
                _read_imported_regular(root_fd, entries, "authority.json")
            )
            installation = InstallationRecord.from_bytes(
                _read_imported_regular(root_fd, entries, "installation.json"),
                authority,
            )
            candidate = CandidateReceipt.from_bytes(
                _read_imported_regular(root_fd, entries, "candidate.v1.json")
            )
            verification = CandidateVerificationReceipt.from_bytes(
                _read_imported_regular(
                    root_fd,
                    entries,
                    "receipts/candidate-verification.v1.json",
                )
            )
            run_template = _read_imported_regular(
                root_fd,
                entries,
                "units/scion-w3@.service",
            )
            close_template = _read_imported_regular(
                root_fd,
                entries,
                "units/scion-w3-close@.service",
            )

            _require_inventory_receipt(
                entries,
                prefix="sealed-store",
                inventory=sealed.inventory,
            )
            _require_inventory_receipt(
                entries,
                prefix="environment",
                inventory=environment.environment_inventory,
            )
            content = _candidate_content(entries, candidate)
            sealed_by_path = {item.path: item for item in sealed.inventory}
            source_acceptance = RootFixedSourceAcceptanceReceipt.from_bytes(
                _read_imported_regular(
                    root_fd,
                    entries,
                    f"sealed-store/{W3_SOURCE_ACCEPTANCE_SEALED_PATH}",
                )
            )
            if (
                source_acceptance.raw_sha256 != intent.source_acceptance_sha256
                or source_acceptance.raw_sha256 != verification.source_acceptance_sha256
                or source_acceptance.raw_sha256 != closure.gate.source_acceptance_sha256
                or source_acceptance.source_receipt != source
            ):
                raise WarehouseW3RootStagingError(
                    "root fixed-source acceptance differs from imported candidate"
                )
            blobs: list[GitBlobFact] = []
            for identity in source.blobs:
                path = f"sealed/{identity.logical_path}"
                entry = sealed_by_path.get(path)
                if (
                    entry is None
                    or entry.sha256 != identity.sha256
                    or entry.size_bytes != identity.size_bytes
                ):
                    raise WarehouseW3RootStagingError(
                        "sealed Git source identity differs"
                    )
                blobs.append(
                    GitBlobFact(
                        source_commit=source.source_commit,
                        source_tree=source.source_tree,
                        identity=identity,
                        raw=_read_imported_regular(
                            root_fd,
                            entries,
                            f"sealed-store/{path}",
                        ),
                    )
                )
            snapshot = GitSourceSnapshot(receipt=source, blobs=tuple(blobs))
            wheel_raw = _read_imported_regular(
                root_fd,
                entries,
                f"sealed-store/{W3_WHEEL_SEALED_PATH}",
            )
            verify_wheel_bytes_against_receipt(
                wheel_raw,
                closure.double_wheel,
                trusted_source_snapshot=snapshot,
            )
            adapters = tuple(
                AuthorityInputAdapter(
                    logical_path=item.logical_path,
                    sealed_path=item.sealed_path,
                    sha256=item.sha256,
                    size_bytes=item.size_bytes,
                    provenance=item.provenance,
                )
                for item in authority.inputs
            )
            for adapter in adapters:
                entry = sealed_by_path.get(adapter.sealed_path)
                if (
                    entry is None
                    or _adapter_from_sealed_entry(
                        entry,
                        logical_path=adapter.logical_path,
                    )
                    != adapter
                ):
                    raise WarehouseW3RootStagingError(
                        "authority input differs from sealed-store receipt"
                    )
            source_logical = {item.logical_path for item in snapshot.blobs}
            manifest = [
                item for item in adapters if item.logical_path == EXPECTED_MANIFEST_NAME
            ]
            native = [
                item
                for item in adapters
                if item.logical_path == W3_NATIVE_RECORD_LOGICAL_PATH
            ]
            if len(manifest) != 1 or len(native) != 1:
                raise WarehouseW3RootStagingError(
                    "authority manifest or native record differs"
                )
            extras = tuple(
                item
                for item in adapters
                if item.logical_path
                not in {
                    *source_logical,
                    EXPECTED_MANIFEST_NAME,
                    W3_NATIVE_RECORD_LOGICAL_PATH,
                }
            )
            rebuilt_authority = build_warehouse_launch_authority(
                snapshot,
                manifest_input=manifest[0],
                native_record_input=native[0],
                root_basename=authority.root_basename,
                nonce=authority.nonce,
                sealed_store_aggregate_sha256=sealed.aggregate_sha256,
                environment_receipt_sha256=environment.raw_sha256,
                extra_inputs=extras,
            )
            rebuilt_installation = build_warehouse_installation(
                authority,
                run_root=Path(installation.run_root),
                run_template_raw=run_template,
                close_template_raw=close_template,
            )
            rebuilt_candidate = CandidateReceipt.create(
                intent=intent,
                content_inventory=content,
                sealed_store_receipt=sealed,
                environment_receipt=environment,
                authority=authority,
                installation=installation,
                selection_commit=commit,
            )
            rebuilt_verification = CandidateVerificationReceipt.create(
                intent=intent,
                selection_commit=commit,
                source_receipt=source,
                sealed_store_receipt=sealed,
                environment_receipt=environment,
                authority=authority,
                installation=installation,
                candidate_receipt=candidate,
            )
            if (
                rebuilt_authority != authority
                or rebuilt_installation != installation
                or rebuilt_candidate != candidate
                or rebuilt_verification != verification
                or intent.selection_key != gate.selection_key
                or candidate.selection_key != gate.selection_key
                or verification.selection_key != gate.selection_key
                or commit.selection_key != gate.selection_key
                or commit.launch_id != gate.launch_id
                or commit.nonce != gate.nonce
                or commit.authority_sha256 != gate.authority_sha256
                or commit.candidate_root_identity != gate.candidate_root_identity
                or candidate.candidate_root != gate.candidate_root
                or candidate.authority_sha256 != gate.authority_sha256
                or candidate.installation_sha256 != gate.installation_sha256
                or verification.raw_sha256 != gate.candidate_verification_sha256
                or verification != closure.candidate_verification
                or source.raw_sha256 != gate.source_receipt_sha256
                or environment.raw_sha256 != gate.environment_content_receipt_sha256
                or authority.authority_sha256 != gate.authority_sha256
                or authority.nonce != gate.nonce
                or installation.installation_sha256 != gate.installation_sha256
                or installation.launch_id != gate.launch_id
                or installation.run_root != gate.accepted_root
            ):
                raise WarehouseW3RootStagingError(
                    "imported candidate semantic replay differs"
                )
            result = WarehouseW3RootStagingVerification._create(
                candidate_gate=gate,
                candidate_gate_closure=closure,
                candidate_gate_ingress=ingress_fact,
                tree_import=imported,
                candidate_receipt=candidate,
                candidate_verification=verification,
                source_receipt=source,
                sealed_store_receipt=sealed,
                environment_receipt=environment,
                authority=authority,
                installation=installation,
                selection_intent=intent,
                selection_commit=commit,
            )
        finally:
            os.close(root_fd)
        reopen_imported_tree(staging_parent, imported)
        ingress.revalidate()
        return result
    except WarehouseW3RootStagingError:
        raise
    except Exception as exc:
        raise WarehouseW3RootStagingError(
            "root-staging candidate replay failed"
        ) from exc


def verify_imported_w3_candidate(
    ingress: PinnedCandidateGateIngress,
    staging_parent: PinnedDirectory,
    tree_import: ImmutableTreeImportReceipt,
) -> WarehouseW3RootStagingVerification:
    """Reverify one root-owned import while retaining its fixed ingress."""

    _exact_type(
        ingress,
        PinnedCandidateGateIngress,
        field="ingress",
    )
    _exact_type(staging_parent, PinnedDirectory, field="staging_parent")
    _exact_type(
        tree_import,
        ImmutableTreeImportReceipt,
        field="tree_import",
    )
    if os.geteuid() != 0:
        raise PermissionError("root-staging verification requires effective UID zero")
    staging_parent.revalidate_mutable_leaf()
    parent_identity = FileIdentity.from_stat(os.fstat(staging_parent.fd))
    imported = ImmutableTreeImportReceipt.from_bytes(tree_import.raw)
    if (
        not stat.S_ISDIR(parent_identity.mode)
        or parent_identity.uid != 0
        or parent_identity.gid != 0
        or stat.S_IMODE(parent_identity.mode) & 0o022
        or imported.target_uid != 0
        or imported.target_gid != 0
        or imported.staging_root.uid != 0
        or imported.staging_root.gid != 0
        or ingress.fact.candidate_identity.uid == 0
    ):
        raise WarehouseW3RootStagingError("root-staging authority or ownership differs")
    return _verify_imported_w3_candidate(
        ingress,
        staging_parent,
        imported,
    )


__all__ = [
    "WarehouseW3RootStagingError",
    "WarehouseW3RootStagingVerification",
    "verify_imported_w3_candidate",
]
