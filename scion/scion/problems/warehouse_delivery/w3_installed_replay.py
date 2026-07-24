"""Deep replay of one complete Warehouse W3 installed-acceptance DAG.

The verifier is capability-free.  It consumes only canonical producer bytes,
reconstructs K0 through K8, and returns exact typed receipts.  Filesystem
authority is added separately by the fixed root-owned receipt-store adapter.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import stat

from scion.runtime.execution.external_installation import (
    DirectoryIdentity,
    INSTALL_PHASES,
    InstalledAcceptance,
    LoadedManagerReceipt,
    ManagerReloadReceipt,
    MountBindingReceipt,
    PublishedDirectoryReceipt,
    PublishedRegularFileReceipt,
    PublishedTreeReceipt,
    NarrowInstallationManager,
    RootPhaseIntentReceipt,
    RootPhaseReceipt,
    UnitPublicationReceipt,
    parse_selected_mountinfo,
    reacquire_loaded_manager_receipt,
)
from scion.runtime.execution.external_linux import (
    LinuxRootAdapter,
    FileIdentity,
    MountNamespacePair,
    NamespaceIdentity,
    PinnedDirectory,
    acquire_mount_namespace_pair,
    pin_absolute_directory,
)
from scion.runtime.execution.systemd_acquisition import (
    ConfiguredPairReadback,
    parse_unit_template,
)

from .w3_environment_receipts import (
    EnvironmentRelocationReceipt,
    FilesystemLiveEnvironmentReader,
    LiveEnvironmentRehashFact,
    verify_live_environment,
)
from .w3_candidate_gate import reverify_w3_accepted_root
from .w3_installation import reverify_sealed_store
from .w3_prestart_facts import (
    PreStartAbsenceObservation,
    WarehouseW3DryRootReadinessReceipt,
    WarehouseW3PreStartAbsenceReceipt,
    WarehouseW3RuntimeAccountReceipt,
)
from .w3_root_installation import (
    WarehouseW3AuthorityPublishedReceipt,
    WarehouseW3PreStartEvidence,
    WarehouseW3ProjectionReceipt,
    WarehouseW3StoresPublishedReceipt,
)
from .w3_root_selection import (
    WarehouseW3SelectedCandidateChain,
    WarehouseW3SelectionReplayInputs,
    verify_w3_selected_candidate_chain,
)

_MAX_OBJECT_BYTES = 64 * 1024 * 1024
_MAX_BUNDLE_BYTES = 512 * 1024 * 1024
_PHASE_COUNT = len(INSTALL_PHASES)
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_FIXED_ACCEPTANCE_ROOT = "/var/lib/scion/acceptances/w3"
_FIXED_REPLAY_LEAF = "INSTALLED_REPLAY.v1.json"
_RUN_WIRING = (
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
)
_CLOSE_WIRING = (
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
)


class WarehouseW3InstalledReplayError(RuntimeError):
    """The installed acceptance cannot be reconstructed from exact producers."""


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
        raise WarehouseW3InstalledReplayError(
            "installed replay value is not canonical JSON"
        ) from exc


def _decode(
    raw: bytes,
    *,
    label: str,
    maximum: int = _MAX_OBJECT_BYTES,
) -> dict[str, object]:
    if type(raw) is not bytes or not raw or len(raw) > maximum:
        raise WarehouseW3InstalledReplayError(f"{label} must be bounded exact bytes")

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
                ValueError(f"{label} contains a float")
            ),
            parse_constant=lambda token: (_ for _ in ()).throw(
                ValueError(f"{label} contains {token}")
            ),
        )
    except (UnicodeError, TypeError, ValueError) as exc:
        raise WarehouseW3InstalledReplayError(f"{label} is not canonical JSON") from exc
    if type(value) is not dict or _canonical_json(value) != raw:
        raise WarehouseW3InstalledReplayError(f"{label} bytes are not canonical")
    return value


def _raw_text(raw: bytes, *, field: str) -> str:
    if type(raw) is not bytes or not raw or len(raw) > _MAX_OBJECT_BYTES:
        raise WarehouseW3InstalledReplayError(f"{field} must be bounded exact bytes")
    try:
        return raw.decode("utf-8", "strict")
    except UnicodeError as exc:
        raise WarehouseW3InstalledReplayError(f"{field} is not UTF-8") from exc


def _nested_raw(value: object, *, field: str) -> bytes:
    if type(value) is not str:
        raise WarehouseW3InstalledReplayError(f"{field} is not exact text")
    try:
        raw = value.encode("utf-8", "strict")
    except UnicodeError as exc:
        raise WarehouseW3InstalledReplayError(f"{field} is not UTF-8") from exc
    if not raw or len(raw) > _MAX_OBJECT_BYTES:
        raise WarehouseW3InstalledReplayError(f"{field} exceeds its byte limit")
    return raw


def _expanded(value: str, launch_id: str) -> str:
    if type(value) is not str:
        raise WarehouseW3InstalledReplayError(
            "unit template directive is not exact text"
        )
    return value.replace("%i", launch_id)


def _wiring(
    run_template_raw: bytes,
    close_template_raw: bytes,
    launch_id: str,
) -> tuple[dict[str, str], dict[str, str]]:
    run = parse_unit_template(run_template_raw)
    close = parse_unit_template(close_template_raw)
    run_service = dict(run.section("Service"))
    close_service = dict(close.section("Service"))
    try:
        return (
            {key: _expanded(run_service[key], launch_id) for key in _RUN_WIRING},
            {key: _expanded(close_service[key], launch_id) for key in _CLOSE_WIRING},
        )
    except KeyError as exc:
        raise WarehouseW3InstalledReplayError(
            "unit template wiring inventory differs"
        ) from exc


def _namespace_pair(projection_raw: bytes) -> tuple[MountNamespacePair, str]:
    value = _decode(projection_raw, label="W3 projection")
    raw_namespaces = value.get("mount_namespaces")
    if type(raw_namespaces) is not dict or frozenset(raw_namespaces) != frozenset(
        {"self", "pid1"}
    ):
        raise WarehouseW3InstalledReplayError("projection namespace inventory differs")

    def identity(name: str) -> NamespaceIdentity:
        item = raw_namespaces[name]
        if type(item) is not dict or frozenset(item) != frozenset({"device", "inode"}):
            raise WarehouseW3InstalledReplayError(
                "projection namespace identity differs"
            )
        return NamespaceIdentity(device=item["device"], inode=item["inode"])

    boot_id = value.get("boot_id")
    if type(boot_id) is not str:
        raise WarehouseW3InstalledReplayError("projection boot identity differs")
    return (
        MountNamespacePair(
            self_namespace=identity("self"),
            pid1_namespace=identity("pid1"),
        ),
        boot_id,
    )


@dataclass(frozen=True, slots=True)
class WarehouseW3InstalledReplayInputs:
    """All raw producers needed to reconstruct one installed acceptance."""

    phase_intent_raws: tuple[bytes, ...]
    phase_receipt_raws: tuple[bytes, ...]
    stores_published_raw: bytes
    sealed_publication_raw: bytes
    environment_publication_raw: bytes
    environment_relocation_raw: bytes
    authority_published_raw: bytes
    authority_publication_raw: bytes
    installation_publication_raw: bytes
    nonce_directory_raw: bytes
    projection_raw: bytes
    projection_parent_raws: tuple[bytes, ...]
    run_mount_raw: bytes
    sealed_mount_raw: bytes
    environment_mount_raw: bytes
    nonce_claims_mount_raw: bytes
    projection_authority_publication_raw: bytes
    projection_installation_publication_raw: bytes
    run_template_raw: bytes
    close_template_raw: bytes
    run_unit_publication_raw: bytes
    close_unit_publication_raw: bytes
    unit_publication_raw: bytes
    configured_pair_readback_raw: bytes
    manager_reload_raw: bytes
    loaded_manager_raw: bytes
    environment_rehash_raw: bytes
    dry_root_raw: bytes
    prestart_absence_raw: bytes
    runtime_account_raw: bytes
    prestart_evidence_raw: bytes
    installed_acceptance_raw: bytes

    def __post_init__(self) -> None:
        if (
            type(self.phase_intent_raws) is not tuple
            or len(self.phase_intent_raws) != _PHASE_COUNT
            or type(self.phase_receipt_raws) is not tuple
            or len(self.phase_receipt_raws) != _PHASE_COUNT
            or type(self.projection_parent_raws) is not tuple
            or not self.projection_parent_raws
        ):
            raise TypeError("installed replay tuple inventory differs")
        for name in self.__dataclass_fields__:
            value = getattr(self, name)
            raws = value if type(value) is tuple else (value,)
            if any(
                type(raw) is not bytes or not raw or len(raw) > _MAX_OBJECT_BYTES
                for raw in raws
            ):
                raise TypeError(f"{name} must contain bounded exact bytes")


_SELECTION_FIELDS = tuple(WarehouseW3SelectionReplayInputs.__dataclass_fields__)
_INSTALLED_FIELDS = tuple(WarehouseW3InstalledReplayInputs.__dataclass_fields__)
_INSTALLED_TUPLE_FIELDS = frozenset(
    {
        "phase_intent_raws",
        "phase_receipt_raws",
        "projection_parent_raws",
    }
)


@dataclass(frozen=True, slots=True, init=False)
class WarehouseW3InstalledAcceptanceBundle:
    """Canonical fixed-store payload for one complete installed replay."""

    selection_replay_inputs: WarehouseW3SelectionReplayInputs
    installed_replay_inputs: WarehouseW3InstalledReplayInputs
    raw: bytes
    raw_sha256: str

    def __new__(cls) -> "WarehouseW3InstalledAcceptanceBundle":
        del cls
        raise TypeError(
            "WarehouseW3InstalledAcceptanceBundle must be parsed from exact bytes"
        )

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("WarehouseW3InstalledAcceptanceBundle is final")

    @classmethod
    def create(
        cls,
        *,
        selection_replay_inputs: WarehouseW3SelectionReplayInputs,
        installed_replay_inputs: WarehouseW3InstalledReplayInputs,
    ) -> "WarehouseW3InstalledAcceptanceBundle":
        if os.geteuid() != 0:
            raise PermissionError(
                "installed replay bundle construction requires effective UID zero"
            )
        return cls._create_for_test(
            selection_replay_inputs=selection_replay_inputs,
            installed_replay_inputs=installed_replay_inputs,
        )

    @classmethod
    def _create_for_test(
        cls,
        *,
        selection_replay_inputs: WarehouseW3SelectionReplayInputs,
        installed_replay_inputs: WarehouseW3InstalledReplayInputs,
    ) -> "WarehouseW3InstalledAcceptanceBundle":
        if type(selection_replay_inputs) is not WarehouseW3SelectionReplayInputs:
            raise TypeError(
                "selection_replay_inputs must be exact "
                "WarehouseW3SelectionReplayInputs"
            )
        if type(installed_replay_inputs) is not WarehouseW3InstalledReplayInputs:
            raise TypeError(
                "installed_replay_inputs must be exact "
                "WarehouseW3InstalledReplayInputs"
            )
        return cls.from_bytes(
            _canonical_json(
                {
                    "schema": "scion.w3-installed-replay-bundle.v1",
                    "selection_replay": {
                        name: _raw_text(
                            getattr(selection_replay_inputs, name),
                            field=f"selection_replay.{name}",
                        )
                        for name in _SELECTION_FIELDS
                    },
                    "installed_replay": {
                        name: (
                            [
                                _raw_text(
                                    raw,
                                    field=f"installed_replay.{name}",
                                )
                                for raw in getattr(
                                    installed_replay_inputs,
                                    name,
                                )
                            ]
                            if name in _INSTALLED_TUPLE_FIELDS
                            else _raw_text(
                                getattr(installed_replay_inputs, name),
                                field=f"installed_replay.{name}",
                            )
                        )
                        for name in _INSTALLED_FIELDS
                    },
                }
            )
        )

    @classmethod
    def from_bytes(
        cls,
        raw: bytes,
    ) -> "WarehouseW3InstalledAcceptanceBundle":
        value = _decode(
            raw,
            label="installed replay bundle",
            maximum=_MAX_BUNDLE_BYTES,
        )
        if (
            frozenset(value)
            != frozenset(
                {
                    "schema",
                    "selection_replay",
                    "installed_replay",
                }
            )
            or value["schema"] != "scion.w3-installed-replay-bundle.v1"
        ):
            raise WarehouseW3InstalledReplayError(
                "installed replay bundle fields differ"
            )
        selection_value = value["selection_replay"]
        installed_value = value["installed_replay"]
        if (
            type(selection_value) is not dict
            or frozenset(selection_value) != frozenset(_SELECTION_FIELDS)
            or type(installed_value) is not dict
            or frozenset(installed_value) != frozenset(_INSTALLED_FIELDS)
        ):
            raise WarehouseW3InstalledReplayError(
                "installed replay bundle inventory differs"
            )
        selection = WarehouseW3SelectionReplayInputs(
            **{
                name: _nested_raw(
                    selection_value[name],
                    field=f"selection_replay.{name}",
                )
                for name in _SELECTION_FIELDS
            }
        )
        installed_fields: dict[str, object] = {}
        for name in _INSTALLED_FIELDS:
            item = installed_value[name]
            if name in _INSTALLED_TUPLE_FIELDS:
                if type(item) is not list or not item:
                    raise WarehouseW3InstalledReplayError(
                        "installed replay bundle tuple inventory differs"
                    )
                installed_fields[name] = tuple(
                    _nested_raw(
                        raw_item,
                        field=f"installed_replay.{name}",
                    )
                    for raw_item in item
                )
            else:
                installed_fields[name] = _nested_raw(
                    item,
                    field=f"installed_replay.{name}",
                )
        installed = WarehouseW3InstalledReplayInputs(**installed_fields)
        instance = object.__new__(cls)
        for field, item in (
            ("selection_replay_inputs", selection),
            ("installed_replay_inputs", installed),
            ("raw", raw),
            ("raw_sha256", hashlib.sha256(raw).hexdigest()),
        ):
            object.__setattr__(instance, field, item)
        return instance


@dataclass(frozen=True, slots=True)
class WarehouseW3InstalledReplayChain:
    selected_candidate: WarehouseW3SelectedCandidateChain
    phase_intents: tuple[RootPhaseIntentReceipt, ...]
    phase_receipts: tuple[RootPhaseReceipt, ...]
    stores_published: WarehouseW3StoresPublishedReceipt
    sealed_publication: PublishedTreeReceipt
    environment_publication: PublishedTreeReceipt
    environment_relocation: EnvironmentRelocationReceipt
    authority_published: WarehouseW3AuthorityPublishedReceipt
    authority_publication: PublishedRegularFileReceipt
    installation_publication: PublishedRegularFileReceipt
    nonce_directory: PublishedDirectoryReceipt
    projection: WarehouseW3ProjectionReceipt
    projection_parent_chain: tuple[PublishedDirectoryReceipt, ...]
    run_mount: MountBindingReceipt
    sealed_mount: MountBindingReceipt
    environment_mount: MountBindingReceipt
    nonce_claims_mount: MountBindingReceipt
    projection_authority_publication: PublishedRegularFileReceipt
    projection_installation_publication: PublishedRegularFileReceipt
    unit_publication: UnitPublicationReceipt
    configured_pair_readback: ConfiguredPairReadback
    manager_reload: ManagerReloadReceipt
    loaded_manager: LoadedManagerReceipt
    environment_rehash: LiveEnvironmentRehashFact
    dry_root: WarehouseW3DryRootReadinessReceipt
    prestart_absence: WarehouseW3PreStartAbsenceReceipt
    runtime_account: WarehouseW3RuntimeAccountReceipt
    prestart_evidence: WarehouseW3PreStartEvidence
    installed_acceptance: InstalledAcceptance

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("WarehouseW3InstalledReplayChain is final")


def verify_w3_installed_replay(
    inputs: WarehouseW3InstalledReplayInputs,
    selection_inputs: WarehouseW3SelectionReplayInputs,
) -> WarehouseW3InstalledReplayChain:
    """Reopen K0-K8 and every K2-K7 producer from exact canonical bytes."""

    if type(inputs) is not WarehouseW3InstalledReplayInputs:
        raise TypeError("inputs must be exact WarehouseW3InstalledReplayInputs")
    if type(selection_inputs) is not WarehouseW3SelectionReplayInputs:
        raise TypeError(
            "selection_inputs must be exact WarehouseW3SelectionReplayInputs"
        )
    try:
        selected = verify_w3_selected_candidate_chain(selection_inputs)
        intents = tuple(
            RootPhaseIntentReceipt.from_bytes(raw) for raw in inputs.phase_intent_raws
        )
        receipts = tuple(
            RootPhaseReceipt.from_bytes(raw) for raw in inputs.phase_receipt_raws
        )
        if intents[:2] != (
            selected.root_staging_intent,
            selected.candidate_selected_intent,
        ) or receipts[:2] != (
            selected.root_staging_receipt,
            selected.candidate_selected_receipt,
        ):
            raise WarehouseW3InstalledReplayError(
                "K0/K1 transaction differs from root selection"
            )

        verification = selected.root_staging_verification
        authority = verification.authority
        installation = verification.installation
        candidate = selected.closure.gate
        sealed_publication = PublishedTreeReceipt.from_bytes(
            inputs.sealed_publication_raw
        )
        environment_publication = PublishedTreeReceipt.from_bytes(
            inputs.environment_publication_raw
        )
        relocation = EnvironmentRelocationReceipt.from_bytes(
            inputs.environment_relocation_raw,
            content_receipt=selected.closure.semantic_environment,
        )
        stores = WarehouseW3StoresPublishedReceipt.from_bytes(
            inputs.stores_published_raw,
            candidate_gate=candidate,
            authority=authority,
            installation=installation,
            sealed_store=verification.sealed_store_receipt,
            environment_content=selected.closure.semantic_environment,
            sealed_publication=sealed_publication,
            environment_publication=environment_publication,
            environment_relocation=relocation,
        )

        authority_publication = PublishedRegularFileReceipt.from_bytes(
            inputs.authority_publication_raw
        )
        installation_publication = PublishedRegularFileReceipt.from_bytes(
            inputs.installation_publication_raw
        )
        nonce_directory = PublishedDirectoryReceipt.from_bytes(
            inputs.nonce_directory_raw
        )
        authority_published = WarehouseW3AuthorityPublishedReceipt.from_bytes(
            inputs.authority_published_raw,
            authority=authority,
            installation=installation,
            authority_publication=authority_publication,
            installation_publication=installation_publication,
            nonce_directory=nonce_directory,
        )

        namespace_pair, boot_id = _namespace_pair(inputs.projection_raw)
        parent_chain = tuple(
            PublishedDirectoryReceipt.from_bytes(raw)
            for raw in inputs.projection_parent_raws
        )
        run_mount = MountBindingReceipt.from_bytes(inputs.run_mount_raw)
        sealed_mount = MountBindingReceipt.from_bytes(inputs.sealed_mount_raw)
        environment_mount = MountBindingReceipt.from_bytes(inputs.environment_mount_raw)
        nonce_claims_mount = MountBindingReceipt.from_bytes(
            inputs.nonce_claims_mount_raw
        )
        projection_authority_publication = PublishedRegularFileReceipt.from_bytes(
            inputs.projection_authority_publication_raw
        )
        projection_installation_publication = PublishedRegularFileReceipt.from_bytes(
            inputs.projection_installation_publication_raw
        )
        projection = WarehouseW3ProjectionReceipt.from_bytes(
            inputs.projection_raw,
            authority=authority,
            installation=installation,
            candidate_gate=candidate,
            sealed_publication=sealed_publication,
            environment_publication=environment_publication,
            nonce_directory=nonce_directory,
            namespace_pair=namespace_pair,
            destination_parent_chain=parent_chain,
            boot_id=boot_id,
            run_mount=run_mount,
            sealed_mount=sealed_mount,
            environment_mount=environment_mount,
            nonce_claims_mount=nonce_claims_mount,
            authority_publication=projection_authority_publication,
            installation_publication=(projection_installation_publication),
        )

        run_publication = PublishedRegularFileReceipt.from_bytes(
            inputs.run_unit_publication_raw
        )
        close_publication = PublishedRegularFileReceipt.from_bytes(
            inputs.close_unit_publication_raw
        )
        unit_publication = UnitPublicationReceipt.from_bytes(
            inputs.unit_publication_raw,
            authority=authority,
            installation=installation,
            run_template_raw=inputs.run_template_raw,
            close_template_raw=inputs.close_template_raw,
            run_publication=run_publication,
            close_publication=close_publication,
        )
        run_wiring, close_wiring = _wiring(
            inputs.run_template_raw,
            inputs.close_template_raw,
            installation.launch_id,
        )
        configured_readback = ConfiguredPairReadback.from_bytes(
            inputs.configured_pair_readback_raw,
            expected_run_wiring=run_wiring,
            expected_close_wiring=close_wiring,
        )
        if configured_readback.configured_pair != installation.configured_pair:
            raise WarehouseW3InstalledReplayError(
                "configured pair differs from installation"
            )
        manager_reload = ManagerReloadReceipt.from_bytes(
            inputs.manager_reload_raw,
            unit_publication=unit_publication,
        )
        loaded_manager = LoadedManagerReceipt.from_bytes(
            inputs.loaded_manager_raw,
            configured_readback=configured_readback,
            unit_publication=unit_publication,
            manager_reload=manager_reload,
        )

        rehash = LiveEnvironmentRehashFact.from_bytes(inputs.environment_rehash_raw)
        dry_value = _decode(inputs.dry_root_raw, label="W3 dry-root")
        dry_root = WarehouseW3DryRootReadinessReceipt.from_bytes(
            inputs.dry_root_raw,
            candidate_gate=candidate,
            installation=installation,
            observed_identity=candidate.accepted_root_identity.from_mapping(
                dry_value["identity"]
            ),
            observed_inventory_sha256=dry_value["inventory_sha256"],
            observed_inventory_count=dry_value["inventory_count"],
            observed_read_only=dry_value["read_only"],
            composition_state=dry_value["composition_state"],
        )
        absence_value = _decode(
            inputs.prestart_absence_raw,
            label="W3 pre-start absence",
        )
        raw_observations = absence_value.get("observations")
        if type(raw_observations) is not list:
            raise WarehouseW3InstalledReplayError(
                "pre-start absence observations differ"
            )
        prestart_absence = WarehouseW3PreStartAbsenceReceipt.from_bytes(
            inputs.prestart_absence_raw,
            authority=authority,
            installation=installation,
            observations=tuple(
                PreStartAbsenceObservation.from_mapping(item)
                for item in raw_observations
            ),
        )
        account_value = _decode(
            inputs.runtime_account_raw,
            label="W3 runtime account",
        )
        runtime_account = WarehouseW3RuntimeAccountReceipt.from_bytes(
            inputs.runtime_account_raw,
            observed_name=account_value["name"],
            observed_uid=account_value["uid"],
            observed_gid=account_value["gid"],
        )
        evidence = WarehouseW3PreStartEvidence.from_bytes(
            inputs.prestart_evidence_raw,
            authority=authority,
            installation=installation,
            candidate_gate=candidate,
            staged_candidate=selected.staged_candidate,
            selection=selected.root_selection,
            stores_published=stores,
            authority_published=authority_published,
            projection=projection,
            unit_publication=unit_publication,
            manager_reload=manager_reload,
            loaded_manager=loaded_manager,
            environment_rehash=rehash,
            dry_root=dry_root,
            prestart_absence=prestart_absence,
            runtime_account=runtime_account,
            phase_intents=intents[:8],
            phase_receipts=receipts[:7],
        )
        installed = InstalledAcceptance.from_bytes(inputs.installed_acceptance_raw)
        installed.verify_phase_receipts(intents, receipts)
        producers = (
            selected.staged_candidate,
            selected.root_selection,
            stores,
            authority_published,
            projection,
            unit_publication,
            manager_reload,
            evidence,
            installed,
        )
        if any(
            receipt.effect_sha256 != producer.raw_sha256
            for receipt, producer in zip(receipts, producers, strict=True)
        ):
            raise WarehouseW3InstalledReplayError("K0-K8 effect producer differs")
        if (
            loaded_manager.raw_sha256
            != dict(evidence.producer_receipt_sha256)["loaded_manager"]
            or installed.problem_state_sha256 != evidence.raw_sha256
        ):
            raise WarehouseW3InstalledReplayError(
                "installed evidence or loaded manager binding differs"
            )
    except WarehouseW3InstalledReplayError:
        raise
    except Exception as exc:
        raise WarehouseW3InstalledReplayError(
            "installed acceptance deep replay differs"
        ) from exc

    return WarehouseW3InstalledReplayChain(
        selected_candidate=selected,
        phase_intents=intents,
        phase_receipts=receipts,
        stores_published=stores,
        sealed_publication=sealed_publication,
        environment_publication=environment_publication,
        environment_relocation=relocation,
        authority_published=authority_published,
        authority_publication=authority_publication,
        installation_publication=installation_publication,
        nonce_directory=nonce_directory,
        projection=projection,
        projection_parent_chain=parent_chain,
        run_mount=run_mount,
        sealed_mount=sealed_mount,
        environment_mount=environment_mount,
        nonce_claims_mount=nonce_claims_mount,
        projection_authority_publication=(projection_authority_publication),
        projection_installation_publication=(projection_installation_publication),
        unit_publication=unit_publication,
        configured_pair_readback=configured_readback,
        manager_reload=manager_reload,
        loaded_manager=loaded_manager,
        environment_rehash=rehash,
        dry_root=dry_root,
        prestart_absence=prestart_absence,
        runtime_account=runtime_account,
        prestart_evidence=evidence,
        installed_acceptance=installed,
    )


class RootInstalledAcceptanceAuthority:
    """Retained fixed-store authority for one deeply replayed installation."""

    __slots__ = (
        "_bundle",
        "_chain",
        "_closed",
        "_descriptor",
        "_identity",
        "_parent",
    )

    def __new__(cls) -> "RootInstalledAcceptanceAuthority":
        del cls
        raise TypeError(
            "RootInstalledAcceptanceAuthority must be acquired from the fixed store"
        )

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("RootInstalledAcceptanceAuthority is final")

    @classmethod
    def acquire(
        cls,
        launch_id: str,
    ) -> "RootInstalledAcceptanceAuthority":
        if type(launch_id) is not str or _SHA256_RE.fullmatch(launch_id) is None:
            raise WarehouseW3InstalledReplayError(
                "installed acceptance launch id differs"
            )
        parent = pin_absolute_directory(f"{_FIXED_ACCEPTANCE_ROOT}/{launch_id}/install")
        try:
            return cls._acquire_from_install(
                parent,
                expected_launch_id=launch_id,
                require_root_owner=True,
            )
        finally:
            parent.close()

    @classmethod
    def _acquire_for_test(
        cls,
        install: PinnedDirectory,
        *,
        expected_launch_id: str,
    ) -> "RootInstalledAcceptanceAuthority":
        return cls._acquire_from_install(
            install,
            expected_launch_id=expected_launch_id,
            require_root_owner=False,
        )

    @classmethod
    def _acquire_from_install(
        cls,
        install: PinnedDirectory,
        *,
        expected_launch_id: str,
        require_root_owner: bool,
    ) -> "RootInstalledAcceptanceAuthority":
        if type(install) is not PinnedDirectory:
            raise TypeError("install directory must be exact PinnedDirectory")
        if (
            type(expected_launch_id) is not str
            or _SHA256_RE.fullmatch(expected_launch_id) is None
        ):
            raise WarehouseW3InstalledReplayError(
                "installed acceptance launch id differs"
            )
        if type(require_root_owner) is not bool:
            raise TypeError("require_root_owner must be exact bool")
        install.revalidate_mutable_leaf()
        parent_identity = FileIdentity.from_stat(os.fstat(install.fd))
        if require_root_owner and (
            any(
                component.identity.uid != 0
                or component.identity.gid != 0
                or stat.S_IMODE(component.identity.mode) & 0o022
                for component in install.components
            )
            or parent_identity.uid != 0
            or parent_identity.gid != 0
            or stat.S_IMODE(parent_identity.mode) & 0o022
        ):
            raise WarehouseW3InstalledReplayError(
                "installed acceptance directory ownership differs"
            )
        descriptor = os.open(
            _FIXED_REPLAY_LEAF,
            os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
            dir_fd=install.fd,
        )
        try:
            before = os.fstat(descriptor)
            named = os.stat(
                _FIXED_REPLAY_LEAF,
                dir_fd=install.fd,
                follow_symlinks=False,
            )
            if (
                not stat.S_ISREG(before.st_mode)
                or stat.S_IMODE(before.st_mode) != 0o444
                or before.st_nlink != 1
                or (require_root_owner and (before.st_uid != 0 or before.st_gid != 0))
                or FileIdentity.from_stat(before) != FileIdentity.from_stat(named)
            ):
                raise WarehouseW3InstalledReplayError(
                    "installed replay file identity differs"
                )
            chunks: list[bytes] = []
            total = 0
            while True:
                remaining = _MAX_BUNDLE_BYTES + 1 - total
                if remaining <= 0:
                    raise WarehouseW3InstalledReplayError(
                        "installed replay file exceeds its byte limit"
                    )
                chunk = os.read(descriptor, min(64 * 1024, remaining))
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
            after = os.fstat(descriptor)
            named_after = os.stat(
                _FIXED_REPLAY_LEAF,
                dir_fd=install.fd,
                follow_symlinks=False,
            )

            def signature(value: os.stat_result) -> tuple[int, ...]:
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

            if (
                signature(before) != signature(after)
                or signature(after) != signature(named_after)
                or total != after.st_size
            ):
                raise WarehouseW3InstalledReplayError("installed replay file drifted")
            bundle = WarehouseW3InstalledAcceptanceBundle.from_bytes(b"".join(chunks))
            chain = verify_w3_installed_replay(
                bundle.installed_replay_inputs,
                bundle.selection_replay_inputs,
            )
            if chain.installed_acceptance.launch_id != expected_launch_id:
                raise WarehouseW3InstalledReplayError(
                    "installed replay launch identity differs"
                )
            instance = object.__new__(cls)
            instance._bundle = bundle
            instance._chain = chain
            instance._closed = False
            instance._descriptor = descriptor
            instance._identity = signature(after)
            instance._parent = install.duplicate()
            descriptor = -1
            instance.revalidate()
            return instance
        finally:
            if descriptor >= 0:
                os.close(descriptor)

    @property
    def bundle(self) -> WarehouseW3InstalledAcceptanceBundle:
        self.revalidate()
        return self._bundle

    @property
    def chain(self) -> WarehouseW3InstalledReplayChain:
        self.revalidate()
        return self._chain

    def revalidate(self) -> None:
        if self._closed:
            raise WarehouseW3InstalledReplayError(
                "installed acceptance authority is closed"
            )
        self._parent.revalidate_mutable_leaf()
        current = os.fstat(self._descriptor)
        named = os.stat(
            _FIXED_REPLAY_LEAF,
            dir_fd=self._parent.fd,
            follow_symlinks=False,
        )

        def signature(value: os.stat_result) -> tuple[int, ...]:
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

        if signature(current) != self._identity or signature(named) != self._identity:
            raise WarehouseW3InstalledReplayError(
                "installed acceptance authority drifted"
            )

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        os.close(self._descriptor)
        self._parent.close()

    def __enter__(self) -> "RootInstalledAcceptanceAuthority":
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


def verify_live_w3_loaded_manager(
    authority: RootInstalledAcceptanceAuthority,
    manager: NarrowInstallationManager,
) -> LoadedManagerReceipt:
    """Reacquire and compare the complete loaded pair to the fixed receipt."""

    if type(authority) is not RootInstalledAcceptanceAuthority:
        raise TypeError("authority must be exact RootInstalledAcceptanceAuthority")
    authority.revalidate()
    chain = authority.chain
    try:
        current = reacquire_loaded_manager_receipt(
            manager,
            configured_readback=chain.configured_pair_readback,
            unit_publication=chain.unit_publication,
            manager_reload=chain.manager_reload,
        )
    except Exception as exc:
        raise WarehouseW3InstalledReplayError(
            "live loaded-manager reacquisition differs"
        ) from exc
    authority.revalidate()
    if current != chain.loaded_manager:
        raise WarehouseW3InstalledReplayError(
            "live loaded-manager receipt differs from fixed acceptance"
        )
    return current


def verify_live_w3_environment(
    authority: RootInstalledAcceptanceAuthority,
    *,
    phase: str,
) -> LiveEnvironmentRehashFact:
    """Rehash the complete fixed environment against current filesystem bytes."""

    if type(authority) is not RootInstalledAcceptanceAuthority:
        raise TypeError("authority must be exact RootInstalledAcceptanceAuthority")
    authority.revalidate()
    chain = authority.chain
    selected = chain.selected_candidate
    selection_intent = selected.root_staging_verification.selection_intent
    semantic = selected.closure.semantic_environment
    try:
        current = verify_live_environment(
            semantic,
            phase=phase,
            live_reader=FilesystemLiveEnvironmentReader(
                external_runtime_paths=tuple(
                    Path(item.path)
                    for item in selected.closure.environment_content.external_runtime
                ),
                candidate_root=Path(selection_intent.candidate_root),
                selection_root=Path(selection_intent.selection_directory),
            ),
        )
    except Exception as exc:
        raise WarehouseW3InstalledReplayError(
            f"live {phase} environment reacquisition differs"
        ) from exc
    authority.revalidate()
    if phase == "preclaim" and current != chain.environment_rehash:
        raise WarehouseW3InstalledReplayError(
            "live preclaim environment differs from fixed acceptance"
        )
    return current


def verify_live_w3_dry_root(
    authority: RootInstalledAcceptanceAuthority,
) -> WarehouseW3DryRootReadinessReceipt:
    """Reopen the installed run root and problem composition without mutation."""

    if type(authority) is not RootInstalledAcceptanceAuthority:
        raise TypeError("authority must be exact RootInstalledAcceptanceAuthority")
    authority.revalidate()
    chain = authority.chain
    selected = chain.selected_candidate
    candidate = selected.closure.gate
    installation = selected.root_staging_verification.installation
    try:
        identity, inventory_sha256, inventory_count = reverify_w3_accepted_root(
            Path(installation.run_root)
        )
        current = WarehouseW3DryRootReadinessReceipt.create(
            candidate_gate=candidate,
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
            selected.root_staging_verification.authority.raw,
            installation.raw,
            authority.bundle.installed_replay_inputs.run_template_raw,
            authority.bundle.installed_replay_inputs.close_template_raw,
            live_configured_pair=chain.configured_pair_readback.configured_pair,
        )
    except Exception as exc:
        raise WarehouseW3InstalledReplayError(
            "live W3 dry-root reacquisition differs"
        ) from exc
    authority.revalidate()
    if (
        current != chain.dry_root
        or readiness.state != "LAUNCH_READY"
        or readiness.filesystem_mutated is not False
    ):
        raise WarehouseW3InstalledReplayError(
            "live W3 dry root differs from fixed acceptance"
        )
    return current


def _stat_signature(value: os.stat_result) -> tuple[int, ...]:
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


def _read_bounded(path: Path, *, maximum: int) -> bytes:
    descriptor = os.open(
        path,
        os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
    )
    try:
        chunks: list[bytes] = []
        total = 0
        while True:
            remaining = maximum + 1 - total
            if remaining <= 0:
                raise WarehouseW3InstalledReplayError(
                    f"live read exceeds bound: {path}"
                )
            chunk = os.read(descriptor, min(64 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _verify_live_directory_receipt(
    receipt: PublishedDirectoryReceipt,
) -> None:
    with pin_absolute_directory(receipt.path) as directory:
        directory.revalidate()
        current = os.fstat(directory.fd)
        if (
            current.st_dev != receipt.device
            or current.st_ino != receipt.inode
            or stat.S_IMODE(current.st_mode) != receipt.mode
            or current.st_uid != receipt.uid
            or current.st_gid != receipt.gid
            or current.st_nlink != receipt.nlink
        ):
            raise WarehouseW3InstalledReplayError(
                f"live published directory differs: {receipt.path}"
            )


def _verify_live_tree_receipt(receipt: PublishedTreeReceipt) -> None:
    with pin_absolute_directory(receipt.path) as directory:
        directory.revalidate()
        current = os.fstat(directory.fd)
        identity = receipt.identity
        if (
            current.st_dev != identity.device
            or current.st_ino != identity.inode
            or stat.S_IMODE(current.st_mode) != identity.mode
            or current.st_uid != identity.uid
            or current.st_gid != identity.gid
            or current.st_nlink != identity.nlink
        ):
            raise WarehouseW3InstalledReplayError(
                f"live published tree identity differs: {receipt.path}"
            )


def _verify_live_regular_receipt(
    receipt: PublishedRegularFileReceipt,
) -> None:
    path = Path(receipt.path)
    descriptor = os.open(
        path,
        os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
    )
    try:
        opened = os.fstat(descriptor)
        named = os.lstat(path)
        if _stat_signature(opened) != _stat_signature(named):
            raise WarehouseW3InstalledReplayError(
                f"live published regular file identity differs: {receipt.path}"
            )
        chunks: list[bytes] = []
        total = 0
        while True:
            remaining = receipt.size_bytes + 1 - total
            if remaining <= 0:
                raise WarehouseW3InstalledReplayError(
                    f"live published regular file exceeds bound: {receipt.path}"
                )
            chunk = os.read(descriptor, min(64 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
        after = os.fstat(descriptor)
        named_after = os.lstat(path)
        raw = b"".join(chunks)
        if (
            _stat_signature(opened) != _stat_signature(after)
            or _stat_signature(after) != _stat_signature(named_after)
            or not stat.S_ISREG(after.st_mode)
            or after.st_dev != receipt.device
            or after.st_ino != receipt.inode
            or stat.S_IMODE(after.st_mode) != receipt.mode
            or after.st_uid != receipt.uid
            or after.st_gid != receipt.gid
            or after.st_nlink != receipt.nlink
            or len(raw) != receipt.size_bytes
            or hashlib.sha256(raw).hexdigest() != receipt.content_sha256
        ):
            raise WarehouseW3InstalledReplayError(
                f"live published regular file differs: {receipt.path}"
            )
    finally:
        os.close(descriptor)


def _reacquire_mount(
    stored: MountBindingReceipt,
    *,
    source_path: str,
    mountinfo_raw: bytes,
    adapter: LinuxRootAdapter,
) -> MountBindingReceipt:
    with (
        pin_absolute_directory(source_path) as source,
        pin_absolute_directory(stored.mount_point) as destination,
    ):
        source.revalidate()
        destination.revalidate()
        source_stat = os.fstat(source.fd)
        destination_stat = os.fstat(destination.fd)
        current = MountBindingReceipt.create(
            row=parse_selected_mountinfo(
                mountinfo_raw,
                mount_point=stored.mount_point,
            ),
            source_identity=DirectoryIdentity(
                device=source_stat.st_dev,
                inode=source_stat.st_ino,
            ),
            destination_identity=DirectoryIdentity(
                device=destination_stat.st_dev,
                inode=destination_stat.st_ino,
            ),
            source_mount_id=adapter.mount_id_for_fd(source.fd),
            read_only=stored.read_only,
            expected_filesystem_type=stored.filesystem_type,
            expected_mount_root=stored.mount_root,
        )
        source.revalidate()
        destination.revalidate()
    return current


def verify_live_w3_projection(
    authority: RootInstalledAcceptanceAuthority,
) -> WarehouseW3ProjectionReceipt:
    """Reacquire exact namespace, mount, parent, and publication identities."""

    if type(authority) is not RootInstalledAcceptanceAuthority:
        raise TypeError("authority must be exact RootInstalledAcceptanceAuthority")
    authority.revalidate()
    chain = authority.chain
    selected = chain.selected_candidate
    verification = selected.root_staging_verification
    installation = verification.installation
    adapter = LinuxRootAdapter()
    try:
        namespace_pair = acquire_mount_namespace_pair(adapter)
        boot_raw = _read_bounded(
            Path("/proc/sys/kernel/random/boot_id"),
            maximum=128,
        )
        boot_id = boot_raw.decode("ascii", "strict").strip()
        if (
            boot_raw != f"{boot_id}\n".encode("ascii")
            or boot_id != chain.projection.boot_id
        ):
            raise WarehouseW3InstalledReplayError(
                "live projection boot identity differs"
            )
        mountinfo_raw = _read_bounded(
            Path("/proc/self/mountinfo"),
            maximum=16 * 1024 * 1024,
        )
        for receipt in chain.projection_parent_chain:
            _verify_live_directory_receipt(receipt)
        _verify_live_tree_receipt(chain.sealed_publication)
        _verify_live_tree_receipt(chain.environment_publication)
        reverify_sealed_store(
            Path(installation.sealed_root),
            verification.sealed_store_receipt,
        )
        _verify_live_directory_receipt(chain.nonce_directory)
        _verify_live_regular_receipt(chain.projection_authority_publication)
        _verify_live_regular_receipt(chain.projection_installation_publication)
        run_mount = _reacquire_mount(
            chain.run_mount,
            source_path=installation.run_root,
            mountinfo_raw=mountinfo_raw,
            adapter=adapter,
        )
        sealed_mount = _reacquire_mount(
            chain.sealed_mount,
            source_path=installation.sealed_root,
            mountinfo_raw=mountinfo_raw,
            adapter=adapter,
        )
        environment_mount = _reacquire_mount(
            chain.environment_mount,
            source_path=installation.environment_root,
            mountinfo_raw=mountinfo_raw,
            adapter=adapter,
        )
        nonce_claims_mount = _reacquire_mount(
            chain.nonce_claims_mount,
            source_path=installation.nonce_ledger_parent,
            mountinfo_raw=mountinfo_raw,
            adapter=adapter,
        )
        current = WarehouseW3ProjectionReceipt.create(
            authority=verification.authority,
            installation=installation,
            candidate_gate=selected.closure.gate,
            sealed_publication=chain.sealed_publication,
            environment_publication=chain.environment_publication,
            nonce_directory=chain.nonce_directory,
            namespace_pair=namespace_pair,
            destination_parent_chain=chain.projection_parent_chain,
            boot_id=boot_id,
            run_mount=run_mount,
            sealed_mount=sealed_mount,
            environment_mount=environment_mount,
            nonce_claims_mount=nonce_claims_mount,
            authority_publication=(chain.projection_authority_publication),
            installation_publication=(chain.projection_installation_publication),
        )
    except WarehouseW3InstalledReplayError:
        raise
    except Exception as exc:
        raise WarehouseW3InstalledReplayError(
            "live W3 projection reacquisition differs"
        ) from exc
    authority.revalidate()
    if current != chain.projection:
        raise WarehouseW3InstalledReplayError(
            "live W3 projection differs from fixed acceptance"
        )
    return current


def _verify_no_w3_process(unit: str) -> None:
    token = unit.encode("ascii")
    try:
        processes = tuple(
            item
            for item in Path("/proc").iterdir()
            if item.name.isascii() and item.name.isdecimal()
        )
    except OSError as exc:
        raise WarehouseW3InstalledReplayError(
            "live procfs process inventory is unavailable"
        ) from exc
    for process in processes:
        for leaf in ("cmdline", "cgroup"):
            try:
                raw = (process / leaf).read_bytes()
            except (FileNotFoundError, ProcessLookupError, PermissionError):
                continue
            except OSError as exc:
                raise WarehouseW3InstalledReplayError(
                    "live procfs process fact is ambiguous"
                ) from exc
            if len(raw) > 1024 * 1024:
                raise WarehouseW3InstalledReplayError(
                    "live procfs process fact exceeds bound"
                )
            if token in raw:
                raise WarehouseW3InstalledReplayError("live W3 process is present")


def verify_live_w3_prestart_absence(
    authority: RootInstalledAcceptanceAuthority,
) -> WarehouseW3PreStartAbsenceReceipt:
    """Reacquire every path, process, cgroup, and issued-start absence."""

    if type(authority) is not RootInstalledAcceptanceAuthority:
        raise TypeError("authority must be exact RootInstalledAcceptanceAuthority")
    authority.revalidate()
    chain = authority.chain
    try:
        for observation in chain.prestart_absence.observations:
            if observation.role == "process":
                _verify_no_w3_process(observation.subject)
            elif os.path.lexists(observation.subject):
                raise WarehouseW3InstalledReplayError(
                    "live W3 pre-start subject is present: " f"{observation.role}"
                )
        current = WarehouseW3PreStartAbsenceReceipt.create(
            authority=(chain.selected_candidate.root_staging_verification.authority),
            installation=(
                chain.selected_candidate.root_staging_verification.installation
            ),
            observations=chain.prestart_absence.observations,
        )
    except WarehouseW3InstalledReplayError:
        raise
    except Exception as exc:
        raise WarehouseW3InstalledReplayError(
            "live W3 pre-start absence reacquisition differs"
        ) from exc
    authority.revalidate()
    if current != chain.prestart_absence:
        raise WarehouseW3InstalledReplayError(
            "live W3 pre-start absence differs from fixed acceptance"
        )
    return current


def verify_live_w3_runtime_account(
    authority: RootInstalledAcceptanceAuthority,
) -> WarehouseW3RuntimeAccountReceipt:
    """Reacquire the exact runtime account from the local password database."""

    if type(authority) is not RootInstalledAcceptanceAuthority:
        raise TypeError("authority must be exact RootInstalledAcceptanceAuthority")
    authority.revalidate()
    chain = authority.chain
    try:
        account = pwd.getpwnam(chain.runtime_account.name)
        current = WarehouseW3RuntimeAccountReceipt.create(
            observed_name=account.pw_name,
            observed_uid=account.pw_uid,
            observed_gid=account.pw_gid,
        )
    except Exception as exc:
        raise WarehouseW3InstalledReplayError(
            "live W3 runtime account reacquisition differs"
        ) from exc
    authority.revalidate()
    if current != chain.runtime_account:
        raise WarehouseW3InstalledReplayError(
            "live W3 runtime account differs from fixed acceptance"
        )
    return current


def reacquire_live_w3_prestart(
    authority: RootInstalledAcceptanceAuthority,
    manager: NarrowInstallationManager,
) -> bytes:
    """Reacquire the complete launch gate and return its exact evidence bytes."""

    if type(authority) is not RootInstalledAcceptanceAuthority:
        raise TypeError("authority must be exact RootInstalledAcceptanceAuthority")
    verify_live_w3_loaded_manager(authority, manager)
    verify_live_w3_projection(authority)
    verify_live_w3_environment(authority, phase="preclaim")
    verify_live_w3_dry_root(authority)
    verify_live_w3_prestart_absence(authority)
    verify_live_w3_runtime_account(authority)
    authority.revalidate()
    return authority.chain.prestart_evidence.raw


__all__ = [
    "RootInstalledAcceptanceAuthority",
    "WarehouseW3InstalledAcceptanceBundle",
    "WarehouseW3InstalledReplayChain",
    "WarehouseW3InstalledReplayError",
    "WarehouseW3InstalledReplayInputs",
    "verify_live_w3_loaded_manager",
    "verify_live_w3_environment",
    "verify_live_w3_dry_root",
    "verify_live_w3_prestart_absence",
    "verify_live_w3_projection",
    "verify_live_w3_runtime_account",
    "reacquire_live_w3_prestart",
    "verify_w3_installed_replay",
]
