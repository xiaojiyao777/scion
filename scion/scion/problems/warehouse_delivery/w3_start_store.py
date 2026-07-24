"""Fixed root-owned receipt-store acquisition for the installed W3 run gate."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import stat

from scion.runtime.execution.external_linux import (
    FileIdentity,
    PinnedDirectory,
    pin_absolute_directory,
)

from .w3_root_selection import (
    RootSelectedCandidateAuthority,
    WarehouseW3SelectionReplayInputs,
)
from .w3_installed_replay import (
    RootInstalledAcceptanceAuthority,
    WarehouseW3InstalledReplayInputs,
)
from .w3_environment_receipts import (
    FilesystemLiveEnvironmentReader,
    LiveEnvironmentRehashFact,
    WarehouseEnvironmentContentReceipt,
    verify_live_environment,
)
from .w3_start_gate import (
    WarehouseW3EnvironmentIntegrityRefused,
    WarehouseW3InstalledIdentityRefused,
    WarehouseW3IssuedStartGate,
    WarehouseW3PreStartProducerReplayInputs,
    WarehouseW3StartPermitRefused,
    WarehouseW3SystemdLineageRefused,
    verify_w3_issued_start_gate,
)

_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_ACCEPTANCE_ROOT = "/var/lib/scion/acceptances/w3"
_SELECTION_ROOT = "/var/lib/scion/selections/w3"
_BUNDLE_LEAF = "START_GATE_INPUTS.v1.json"
_AUTHORIZATION_LEAF = "START_AUTHORIZED"
_ISSUE_LEAF = "START_ISSUED"
_MAX_BUNDLE_BYTES = 256 * 1024 * 1024
_MAX_RECEIPT_BYTES = 4 * 1024 * 1024
_SELECTION_FIELDS = tuple(WarehouseW3SelectionReplayInputs.__dataclass_fields__)
_PRESTART_FIELDS = tuple(WarehouseW3PreStartProducerReplayInputs.__dataclass_fields__)
_INSTALLED_FIELDS = tuple(WarehouseW3InstalledReplayInputs.__dataclass_fields__)
_INSTALLED_TUPLE_FIELDS = frozenset(
    {
        "phase_intent_raws",
        "phase_receipt_raws",
        "projection_parent_raws",
    }
)


class WarehouseW3StartStoreError(RuntimeError):
    """The fixed root-owned installed start evidence is absent or drifted."""


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
        raise WarehouseW3StartStoreError(
            "installed start bundle is not canonical JSON data"
        ) from exc


def _decode(raw: bytes, *, label: str, maximum: int) -> dict[str, object]:
    if type(raw) is not bytes:
        raise TypeError(f"{label} must be exact bytes")
    if not raw or len(raw) > maximum:
        raise WarehouseW3StartStoreError(f"{label} exceeds its byte limit")

    def mapping(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"{label} contains a duplicate field")
            result[key] = value
        return result

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
    except (UnicodeError, ValueError, TypeError) as exc:
        raise WarehouseW3StartStoreError(f"{label} is not canonical JSON") from exc
    if type(value) is not dict or _canonical_json(value) != raw:
        raise WarehouseW3StartStoreError(f"{label} bytes are not canonical")
    return value


def _nested_raw(value: object, *, field: str) -> bytes:
    if type(value) is not str:
        raise WarehouseW3StartStoreError(
            f"installed start bundle {field} is not exact text"
        )
    try:
        raw = value.encode("utf-8", "strict")
    except UnicodeError as exc:
        raise WarehouseW3StartStoreError(
            f"installed start bundle {field} is not UTF-8"
        ) from exc
    if not raw or len(raw) > 64 * 1024 * 1024:
        raise WarehouseW3StartStoreError(
            f"installed start bundle {field} exceeds its byte limit"
        )
    return raw


def _raw_text(raw: object, *, field: str) -> str:
    if type(raw) is not bytes:
        raise TypeError(f"{field} must be exact bytes")
    if not raw or len(raw) > 64 * 1024 * 1024:
        raise WarehouseW3StartStoreError(
            f"installed start bundle {field} exceeds its byte limit"
        )
    try:
        return raw.decode("utf-8", "strict")
    except UnicodeError as exc:
        raise WarehouseW3StartStoreError(
            f"installed start bundle {field} is not UTF-8"
        ) from exc


@dataclass(frozen=True, slots=True, init=False)
class WarehouseW3InstalledStartGateBundle:
    prospective_intent_raw: bytes
    installed_acceptance_raw: bytes
    prestart_evidence_raw: bytes
    selection_replay_inputs: WarehouseW3SelectionReplayInputs
    prestart_producer_replay_inputs: WarehouseW3PreStartProducerReplayInputs
    installed_replay_inputs: WarehouseW3InstalledReplayInputs
    raw: bytes
    raw_sha256: str

    def __new__(cls) -> "WarehouseW3InstalledStartGateBundle":
        del cls
        raise TypeError(
            "WarehouseW3InstalledStartGateBundle must be parsed from exact bytes"
        )

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("WarehouseW3InstalledStartGateBundle is final")

    @classmethod
    def create(
        cls,
        *,
        prospective_intent_raw: bytes,
        installed_acceptance_raw: bytes,
        prestart_evidence_raw: bytes,
        selection_replay_inputs: WarehouseW3SelectionReplayInputs,
        prestart_producer_replay_inputs: WarehouseW3PreStartProducerReplayInputs,
        installed_replay_inputs: WarehouseW3InstalledReplayInputs,
    ) -> "WarehouseW3InstalledStartGateBundle":
        if os.geteuid() != 0:
            raise PermissionError(
                "installed start bundle construction requires " "effective UID zero"
            )
        return cls._create_for_test(
            prospective_intent_raw=prospective_intent_raw,
            installed_acceptance_raw=installed_acceptance_raw,
            prestart_evidence_raw=prestart_evidence_raw,
            selection_replay_inputs=selection_replay_inputs,
            prestart_producer_replay_inputs=prestart_producer_replay_inputs,
            installed_replay_inputs=installed_replay_inputs,
        )

    @classmethod
    def _create_for_test(
        cls,
        *,
        prospective_intent_raw: bytes,
        installed_acceptance_raw: bytes,
        prestart_evidence_raw: bytes,
        selection_replay_inputs: WarehouseW3SelectionReplayInputs,
        prestart_producer_replay_inputs: WarehouseW3PreStartProducerReplayInputs,
        installed_replay_inputs: WarehouseW3InstalledReplayInputs,
    ) -> "WarehouseW3InstalledStartGateBundle":
        if type(selection_replay_inputs) is not WarehouseW3SelectionReplayInputs:
            raise TypeError(
                "selection_replay_inputs must be exact "
                "WarehouseW3SelectionReplayInputs"
            )
        if (
            type(prestart_producer_replay_inputs)
            is not WarehouseW3PreStartProducerReplayInputs
        ):
            raise TypeError(
                "prestart_producer_replay_inputs must be exact "
                "WarehouseW3PreStartProducerReplayInputs"
            )
        if type(installed_replay_inputs) is not WarehouseW3InstalledReplayInputs:
            raise TypeError(
                "installed_replay_inputs must be exact "
                "WarehouseW3InstalledReplayInputs"
            )
        value = {
            "schema": "scion.w3-installed-start-gate-bundle.v1",
            "prospective_intent": _raw_text(
                prospective_intent_raw,
                field="prospective_intent",
            ),
            "installed_acceptance": _raw_text(
                installed_acceptance_raw,
                field="installed_acceptance",
            ),
            "prestart_evidence": _raw_text(
                prestart_evidence_raw,
                field="prestart_evidence",
            ),
            "selection_replay": {
                name: _raw_text(
                    getattr(selection_replay_inputs, name),
                    field=f"selection_replay.{name}",
                )
                for name in _SELECTION_FIELDS
            },
            "prestart_producer_replay": {
                name: _raw_text(
                    getattr(prestart_producer_replay_inputs, name),
                    field=f"prestart_producer_replay.{name}",
                )
                for name in _PRESTART_FIELDS
            },
            "installed_replay": {
                name: (
                    [
                        _raw_text(
                            raw,
                            field=f"installed_replay.{name}",
                        )
                        for raw in getattr(installed_replay_inputs, name)
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
        return cls.from_bytes(_canonical_json(value))

    @classmethod
    def from_bytes(
        cls,
        raw: bytes,
    ) -> "WarehouseW3InstalledStartGateBundle":
        value = _decode(
            raw,
            label="installed start gate bundle",
            maximum=_MAX_BUNDLE_BYTES,
        )
        if (
            frozenset(value)
            != frozenset(
                {
                    "schema",
                    "prospective_intent",
                    "installed_acceptance",
                    "prestart_evidence",
                    "selection_replay",
                    "prestart_producer_replay",
                    "installed_replay",
                }
            )
            or value["schema"] != "scion.w3-installed-start-gate-bundle.v1"
        ):
            raise WarehouseW3StartStoreError(
                "installed start gate bundle fields differ"
            )
        selection_value = value["selection_replay"]
        prestart_value = value["prestart_producer_replay"]
        installed_value = value["installed_replay"]
        if (
            type(selection_value) is not dict
            or frozenset(selection_value) != frozenset(_SELECTION_FIELDS)
            or type(prestart_value) is not dict
            or frozenset(prestart_value) != frozenset(_PRESTART_FIELDS)
            or type(installed_value) is not dict
            or frozenset(installed_value) != frozenset(_INSTALLED_FIELDS)
        ):
            raise WarehouseW3StartStoreError(
                "installed start gate replay inventory differs"
            )
        prospective = _nested_raw(
            value["prospective_intent"],
            field="prospective_intent",
        )
        acceptance = _nested_raw(
            value["installed_acceptance"],
            field="installed_acceptance",
        )
        evidence = _nested_raw(
            value["prestart_evidence"],
            field="prestart_evidence",
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
        prestart = WarehouseW3PreStartProducerReplayInputs(
            **{
                name: _nested_raw(
                    prestart_value[name],
                    field=f"prestart_producer_replay.{name}",
                )
                for name in _PRESTART_FIELDS
            }
        )
        installed_values: dict[str, object] = {}
        for name in _INSTALLED_FIELDS:
            item = installed_value[name]
            if name in _INSTALLED_TUPLE_FIELDS:
                if type(item) is not list or not item:
                    raise WarehouseW3StartStoreError(
                        "installed start gate replay tuple inventory differs"
                    )
                installed_values[name] = tuple(
                    _nested_raw(
                        raw,
                        field=f"installed_replay.{name}",
                    )
                    for raw in item
                )
            else:
                installed_values[name] = _nested_raw(
                    item,
                    field=f"installed_replay.{name}",
                )
        installed = WarehouseW3InstalledReplayInputs(**installed_values)
        instance = object.__new__(cls)
        object.__setattr__(instance, "prospective_intent_raw", prospective)
        object.__setattr__(instance, "installed_acceptance_raw", acceptance)
        object.__setattr__(instance, "prestart_evidence_raw", evidence)
        object.__setattr__(instance, "selection_replay_inputs", selection)
        object.__setattr__(
            instance,
            "prestart_producer_replay_inputs",
            prestart,
        )
        object.__setattr__(
            instance,
            "installed_replay_inputs",
            installed,
        )
        object.__setattr__(instance, "raw", raw)
        object.__setattr__(
            instance,
            "raw_sha256",
            hashlib.sha256(raw).hexdigest(),
        )
        return instance


@dataclass(frozen=True, slots=True)
class WarehouseW3InstalledStartContext:
    """Verified issued gate plus the exact live-environment rehash authority."""

    gate: WarehouseW3IssuedStartGate
    semantic_environment: WarehouseEnvironmentContentReceipt
    external_runtime_paths: tuple[Path, ...]
    candidate_root: Path
    selection_root: Path
    expected_preclaim_rehash: LiveEnvironmentRehashFact
    _authority: _FixedStartReceiptGuard

    def __post_init__(self) -> None:
        if type(self.gate) is not WarehouseW3IssuedStartGate:
            raise TypeError("gate must be exact WarehouseW3IssuedStartGate")
        if type(self.semantic_environment) is not WarehouseEnvironmentContentReceipt:
            raise TypeError(
                "semantic_environment must be exact "
                "WarehouseEnvironmentContentReceipt"
            )
        if (
            type(self.expected_preclaim_rehash) is not LiveEnvironmentRehashFact
            or self.expected_preclaim_rehash.phase != "preclaim"
        ):
            raise TypeError("expected_preclaim_rehash must be one exact preclaim fact")
        if type(self._authority) is not _FixedStartReceiptGuard:
            raise TypeError("_authority must be exact fixed start receipt guard")

    def revalidate(self) -> None:
        """Revalidate every retained named receipt and predecessor authority."""

        self._authority.revalidate()

    def close(self) -> None:
        """Release every retained descriptor in the installed start gate."""

        self._authority.close()

    def __enter__(self) -> WarehouseW3InstalledStartContext:
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

    def verify_environment(self, phase: str) -> LiveEnvironmentRehashFact:
        """Rehash the installed environment at preclaim or completion."""

        self.revalidate()
        try:
            fact = verify_live_environment(
                self.semantic_environment,
                phase=phase,
                live_reader=FilesystemLiveEnvironmentReader(
                    external_runtime_paths=self.external_runtime_paths,
                    candidate_root=self.candidate_root,
                    selection_root=self.selection_root,
                ),
            )
        except WarehouseW3EnvironmentIntegrityRefused:
            raise
        except Exception as exc:
            raise WarehouseW3EnvironmentIntegrityRefused(
                f"{phase} environment integrity differs"
            ) from exc
        if phase == "preclaim" and fact != self.expected_preclaim_rehash:
            raise WarehouseW3EnvironmentIntegrityRefused(
                "live preclaim environment differs from root acceptance"
            )
        self.revalidate()
        return fact


def _receipt_signature(value: os.stat_result) -> tuple[int, ...]:
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


class _RetainedReceiptAuthority:
    __slots__ = (
        "_closed",
        "_descriptor",
        "_identity",
        "_leaf",
        "_parent",
        "_raw",
    )

    @classmethod
    def acquire(
        cls,
        directory: PinnedDirectory,
        leaf: str,
        *,
        maximum: int,
        require_root_owner: bool,
    ) -> _RetainedReceiptAuthority:
        _require_owned_directory(
            directory,
            require_root_owner=require_root_owner,
        )
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
                raise WarehouseW3StartStoreError(
                    f"installed start receipt identity differs: {leaf}"
                )
            chunks: list[bytes] = []
            total = 0
            while True:
                remaining = maximum + 1 - total
                if remaining <= 0:
                    raise WarehouseW3StartStoreError(
                        "installed start receipt exceeds its byte limit: " f"{leaf}"
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
            identity = _receipt_signature(after)
            if (
                _receipt_signature(before) != identity
                or _receipt_signature(named_after) != identity
                or total != after.st_size
            ):
                raise WarehouseW3StartStoreError(
                    f"installed start receipt drifted: {leaf}"
                )
            instance = cls()
            instance._closed = False
            instance._descriptor = descriptor
            instance._identity = identity
            instance._leaf = leaf
            instance._parent = directory.duplicate()
            instance._raw = b"".join(chunks)
            descriptor = -1
            instance.revalidate()
            return instance
        finally:
            if descriptor >= 0:
                os.close(descriptor)

    @property
    def raw(self) -> bytes:
        self.revalidate()
        return self._raw

    def revalidate(self) -> None:
        if self._closed:
            raise WarehouseW3StartStoreError(
                "installed start receipt authority is closed"
            )
        self._parent.revalidate_mutable_leaf()
        current = os.fstat(self._descriptor)
        named = os.stat(
            self._leaf,
            dir_fd=self._parent.fd,
            follow_symlinks=False,
        )
        if (
            _receipt_signature(current) != self._identity
            or _receipt_signature(named) != self._identity
        ):
            raise WarehouseW3StartStoreError(
                f"installed start receipt authority drifted: {self._leaf}"
            )

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        os.close(self._descriptor)
        self._parent.close()


class _FixedStartReceiptGuard:
    __slots__ = (
        "_authorization",
        "_bundle",
        "_closed",
        "_installed",
        "_issue",
        "_selection",
    )

    def __init__(
        self,
        *,
        bundle: _RetainedReceiptAuthority,
        authorization: _RetainedReceiptAuthority,
        issue: _RetainedReceiptAuthority,
        installed: RootInstalledAcceptanceAuthority,
        selection: RootSelectedCandidateAuthority,
    ) -> None:
        if (
            type(bundle) is not _RetainedReceiptAuthority
            or type(authorization) is not _RetainedReceiptAuthority
            or type(issue) is not _RetainedReceiptAuthority
            or type(installed) is not RootInstalledAcceptanceAuthority
            or type(selection) is not RootSelectedCandidateAuthority
        ):
            raise TypeError("fixed start receipt guard authority differs")
        self._authorization = authorization
        self._bundle = bundle
        self._closed = False
        self._installed = installed
        self._issue = issue
        self._selection = selection
        self.revalidate()

    def revalidate(self) -> None:
        if self._closed:
            raise WarehouseW3StartStoreError("fixed start receipt guard is closed")
        self._bundle.revalidate()
        self._authorization.revalidate()
        self._issue.revalidate()
        self._installed.revalidate()
        self._selection.revalidate()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._selection.close()
        self._installed.close()
        self._issue.close()
        self._authorization.close()
        self._bundle.close()


def _require_owned_directory(
    directory: PinnedDirectory,
    *,
    require_root_owner: bool,
) -> None:
    directory.revalidate_mutable_leaf()
    identity = FileIdentity.from_stat(os.fstat(directory.fd))
    if require_root_owner and (
        any(
            component.identity.uid != 0
            or component.identity.gid != 0
            or stat.S_IMODE(component.identity.mode) & 0o022
            for component in directory.components
        )
        or identity.uid != 0
        or identity.gid != 0
        or stat.S_IMODE(identity.mode) & 0o022
    ):
        raise WarehouseW3StartStoreError("installed start directory ownership differs")


def _acquire_from_roots(
    acceptance_parent: PinnedDirectory,
    selection_parent: PinnedDirectory,
    *,
    expected_launch_id: str,
    expected_authority_sha256: str,
    expected_installation_sha256: str,
    expected_unit: str,
    require_root_owner: bool,
    require_live_environment: bool,
) -> WarehouseW3InstalledStartContext:
    if _SHA256_RE.fullmatch(expected_launch_id) is None:
        raise WarehouseW3StartStoreError("installed launch id differs")
    launch = acceptance_parent.open_child_directory(expected_launch_id)
    try:
        install = launch.open_child_directory("install")
        try:
            try:
                start = launch.open_child_directory("start")
            except Exception as exc:
                raise WarehouseW3StartPermitRefused(
                    "fixed START_ISSUED store is absent"
                ) from exc
            try:
                bundle_receipt: _RetainedReceiptAuthority | None = None
                authorization_receipt: _RetainedReceiptAuthority | None = None
                issue_receipt: _RetainedReceiptAuthority | None = None
                installed_authority: RootInstalledAcceptanceAuthority | None = None
                selection_authority: RootSelectedCandidateAuthority | None = None
                guard: _FixedStartReceiptGuard | None = None
                try:
                    for directory in (
                        acceptance_parent,
                        launch,
                        install,
                        start,
                    ):
                        _require_owned_directory(
                            directory,
                            require_root_owner=require_root_owner,
                        )
                    try:
                        bundle_receipt = _RetainedReceiptAuthority.acquire(
                            start,
                            _BUNDLE_LEAF,
                            maximum=_MAX_BUNDLE_BYTES,
                            require_root_owner=require_root_owner,
                        )
                        bundle = WarehouseW3InstalledStartGateBundle.from_bytes(
                            bundle_receipt.raw
                        )
                    except Exception as exc:
                        raise WarehouseW3InstalledIdentityRefused(
                            "fixed installed start replay bundle differs"
                        ) from exc
                    try:
                        installed_authority = (
                            RootInstalledAcceptanceAuthority._acquire_from_install(
                                install,
                                expected_launch_id=expected_launch_id,
                                require_root_owner=require_root_owner,
                            )
                        )
                    except Exception as exc:
                        raise WarehouseW3InstalledIdentityRefused(
                            "fixed installed acceptance authority differs"
                        ) from exc
                    try:
                        authorization_receipt = _RetainedReceiptAuthority.acquire(
                            start,
                            _AUTHORIZATION_LEAF,
                            maximum=_MAX_RECEIPT_BYTES,
                            require_root_owner=require_root_owner,
                        )
                        issue_receipt = _RetainedReceiptAuthority.acquire(
                            start,
                            _ISSUE_LEAF,
                            maximum=_MAX_RECEIPT_BYTES,
                            require_root_owner=require_root_owner,
                        )
                    except Exception as exc:
                        raise WarehouseW3StartPermitRefused(
                            "fixed START_AUTHORIZED or START_ISSUED differs"
                        ) from exc
                    try:
                        selection_authority = (
                            RootSelectedCandidateAuthority._acquire_from_parent(
                                selection_parent,
                                bundle.selection_replay_inputs,
                                require_root_owner=require_root_owner,
                            )
                        )
                    except Exception as exc:
                        raise WarehouseW3InstalledIdentityRefused(
                            "fixed root selection authority differs"
                        ) from exc
                    if (
                        installed_authority.bundle.selection_replay_inputs
                        != bundle.selection_replay_inputs
                        or installed_authority.bundle.installed_replay_inputs
                        != bundle.installed_replay_inputs
                    ):
                        raise WarehouseW3StartStoreError(
                            "installed start and acceptance replay bundles differ"
                        )
                    gate = verify_w3_issued_start_gate(
                        issue_raw=issue_receipt.raw,
                        authorization_raw=authorization_receipt.raw,
                        prospective_intent_raw=bundle.prospective_intent_raw,
                        installed_acceptance_raw=bundle.installed_acceptance_raw,
                        prestart_evidence_raw=bundle.prestart_evidence_raw,
                        prestart_producer_replay_inputs=(
                            bundle.prestart_producer_replay_inputs
                        ),
                        installed_replay_inputs=(bundle.installed_replay_inputs),
                        selection_replay_inputs=bundle.selection_replay_inputs,
                        expected_launch_id=expected_launch_id,
                        expected_authority_sha256=expected_authority_sha256,
                        expected_installation_sha256=(expected_installation_sha256),
                        expected_unit=expected_unit,
                    )
                    if (
                        gate.root_selection_sha256
                        != selection_authority.chain.root_selection.raw_sha256
                    ):
                        raise WarehouseW3StartStoreError(
                            "installed start root selection differs"
                        )
                    chain = selection_authority.chain
                    selection_intent = chain.root_staging_verification.selection_intent
                    expected_rehash = LiveEnvironmentRehashFact.from_bytes(
                        bundle.prestart_producer_replay_inputs.environment_rehash_raw
                    )
                    guard = _FixedStartReceiptGuard(
                        bundle=bundle_receipt,
                        authorization=authorization_receipt,
                        issue=issue_receipt,
                        installed=installed_authority,
                        selection=selection_authority,
                    )
                    bundle_receipt = None
                    authorization_receipt = None
                    issue_receipt = None
                    installed_authority = None
                    selection_authority = None
                    context = WarehouseW3InstalledStartContext(
                        gate=gate,
                        semantic_environment=chain.closure.semantic_environment,
                        external_runtime_paths=tuple(
                            Path(item.path)
                            for item in chain.closure.environment_content.external_runtime
                        ),
                        candidate_root=Path(selection_intent.candidate_root),
                        selection_root=Path(selection_intent.selection_directory),
                        expected_preclaim_rehash=expected_rehash,
                        _authority=guard,
                    )
                    if require_live_environment:
                        context.verify_environment("preclaim")
                    guard = None
                    return context
                finally:
                    if guard is not None:
                        guard.close()
                    if selection_authority is not None:
                        selection_authority.close()
                    if installed_authority is not None:
                        installed_authority.close()
                    if issue_receipt is not None:
                        issue_receipt.close()
                    if authorization_receipt is not None:
                        authorization_receipt.close()
                    if bundle_receipt is not None:
                        bundle_receipt.close()
            finally:
                start.close()
        finally:
            install.close()
    finally:
        launch.close()


def acquire_w3_issued_start_gate(
    *,
    expected_launch_id: str,
    expected_authority_sha256: str,
    expected_installation_sha256: str,
    expected_unit: str,
) -> WarehouseW3InstalledStartContext:
    """Acquire the exact fixed root-owned gate used by the installed run."""

    try:
        with (
            pin_absolute_directory(_ACCEPTANCE_ROOT) as acceptance_parent,
            pin_absolute_directory(_SELECTION_ROOT) as selection_parent,
        ):
            return _acquire_from_roots(
                acceptance_parent,
                selection_parent,
                expected_launch_id=expected_launch_id,
                expected_authority_sha256=expected_authority_sha256,
                expected_installation_sha256=expected_installation_sha256,
                expected_unit=expected_unit,
                require_root_owner=True,
                require_live_environment=True,
            )
    except (
        WarehouseW3EnvironmentIntegrityRefused,
        WarehouseW3InstalledIdentityRefused,
        WarehouseW3StartPermitRefused,
        WarehouseW3SystemdLineageRefused,
    ):
        raise
    except Exception as exc:
        raise WarehouseW3InstalledIdentityRefused(
            "fixed root-owned installed start identity is unavailable"
        ) from exc


def _acquire_w3_issued_start_gate_for_test(
    acceptance_root: str,
    selection_root: str,
    *,
    expected_launch_id: str,
    expected_authority_sha256: str,
    expected_installation_sha256: str,
    expected_unit: str,
    require_live_environment: bool = False,
) -> WarehouseW3InstalledStartContext:
    with (
        pin_absolute_directory(acceptance_root) as acceptance_parent,
        pin_absolute_directory(selection_root) as selection_parent,
    ):
        return _acquire_from_roots(
            acceptance_parent,
            selection_parent,
            expected_launch_id=expected_launch_id,
            expected_authority_sha256=expected_authority_sha256,
            expected_installation_sha256=expected_installation_sha256,
            expected_unit=expected_unit,
            require_root_owner=False,
            require_live_environment=require_live_environment,
        )


__all__ = [
    "WarehouseW3InstalledStartGateBundle",
    "WarehouseW3InstalledStartContext",
    "acquire_w3_issued_start_gate",
]
