"""Problem-owned replay of Warehouse W3 root staging and selection.

The generic selection receipt deliberately does not know Warehouse semantics.
This module wraps it with the complete staged-candidate binding and provides
one capability-free verifier for the K0/K1 transaction prefix.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
import re
import stat

from scion.problems.warehouse_delivery.w3_candidate_gate import (
    CandidateGateClosureBundle,
)
from scion.problems.warehouse_delivery.w3_candidate_ingress import (
    CandidateGateIngressFact,
)
from scion.problems.warehouse_delivery.w3_installation import (
    ACCEPTED_ROOT_INSTALLATION_PLAN_SHA256,
    CandidateReceipt,
    CandidateSelectionCommit,
    CandidateSelectionIntent,
    GitSourceReceipt,
    SealedStoreReceipt,
)
from scion.problems.warehouse_delivery.w3_root_installation import (
    WarehouseW3StagedCandidateReceipt,
)
from scion.problems.warehouse_delivery.w3_root_staging import (
    WarehouseW3RootStagingVerification,
)
from scion.problems.warehouse_delivery.w3_root_preflight import (
    WarehouseW3RootFinalAbsenceReceipt,
    WarehouseW3RootTransactionTraceReceipt,
)
from scion.runtime.execution.environment_integrity import EnvironmentContentReceipt
from scion.runtime.execution.external_installation import (
    RootPhase,
    RootPhaseIntentReceipt,
    RootPhaseReceipt,
    SelectionReceipt,
)
from scion.runtime.execution.external_linux import ImmutableTreeImportReceipt
from scion.runtime.execution.external_linux import (
    FileIdentity,
    PinnedDirectory,
    pin_absolute_directory,
)
from scion.runtime.execution.launch_authority import (
    AcceptedLaunchAuthority,
    InstallationRecord,
)

_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_SCHEMA = "scion.w3-root-selection.v3"
_MAX_REPLAY_OBJECT_BYTES = 64 * 1024 * 1024


class WarehouseW3RootSelectionError(RuntimeError):
    """The W3 K0/staged/K1 selection chain is incomplete or inconsistent."""


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
        raise WarehouseW3RootSelectionError(
            "W3 root selection is not canonical JSON data"
        ) from exc


def _decode(raw: bytes, *, label: str) -> dict[str, object]:
    if type(raw) is not bytes:
        raise TypeError(f"{label} must be exact bytes")
    if not raw or len(raw) > _MAX_REPLAY_OBJECT_BYTES:
        raise WarehouseW3RootSelectionError(f"{label} exceeds its byte limit")

    def mapping(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, item in pairs:
            if key in result:
                raise ValueError(f"{label} contains a duplicate field")
            result[key] = item
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
        raise WarehouseW3RootSelectionError(f"{label} is not canonical JSON") from exc
    if type(value) is not dict or _canonical_json(value) != raw:
        raise WarehouseW3RootSelectionError(f"{label} bytes are not canonical")
    return value


def _sha256(value: object, *, field: str) -> str:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        raise WarehouseW3RootSelectionError(f"{field} is not canonical SHA-256")
    return value


def _source_identity_tuple(value: object) -> tuple[int, ...]:
    try:
        return (
            value.device,  # type: ignore[attr-defined]
            value.inode,  # type: ignore[attr-defined]
            stat.S_IMODE(value.mode),  # type: ignore[attr-defined]
            value.uid,  # type: ignore[attr-defined]
            value.gid,  # type: ignore[attr-defined]
            (
                value.nlink  # type: ignore[attr-defined]
                if hasattr(value, "nlink")
                else value.link_count  # type: ignore[attr-defined]
            ),
        )
    except (AttributeError, TypeError) as exc:
        raise WarehouseW3RootSelectionError(
            "W3 root selection source identity differs"
        ) from exc


def derive_root_staging_effect_authority_sha256(
    closure: CandidateGateClosureBundle,
    ingress: CandidateGateIngressFact,
    tree_import: ImmutableTreeImportReceipt,
    trace: WarehouseW3RootTransactionTraceReceipt,
    root_final_absence: WarehouseW3RootFinalAbsenceReceipt,
) -> str:
    """Re-derive K0 authority from the completed import's pre-effect fields."""

    if type(tree_import) is not ImmutableTreeImportReceipt:
        raise TypeError("tree_import must be exact ImmutableTreeImportReceipt")
    if tree_import.source_root != ingress.candidate_identity:
        raise WarehouseW3RootSelectionError(
            "K0 root-staging authority producer differs"
        )
    return derive_root_staging_import_authority_sha256(
        closure,
        ingress,
        staging_leaf=tree_import.staging_leaf,
        target_uid=tree_import.target_uid,
        target_gid=tree_import.target_gid,
        trace=trace,
        root_final_absence=root_final_absence,
    )


def derive_root_staging_import_authority_sha256(
    closure: CandidateGateClosureBundle,
    ingress: CandidateGateIngressFact,
    *,
    staging_leaf: str,
    target_uid: int,
    target_gid: int,
    trace: WarehouseW3RootTransactionTraceReceipt,
    root_final_absence: WarehouseW3RootFinalAbsenceReceipt,
) -> str:
    """Derive K0 authority entirely from facts fixed before import."""

    if type(closure) is not CandidateGateClosureBundle:
        raise TypeError("closure must be exact CandidateGateClosureBundle")
    if type(ingress) is not CandidateGateIngressFact:
        raise TypeError("ingress must be exact CandidateGateIngressFact")
    if type(trace) is not WarehouseW3RootTransactionTraceReceipt:
        raise TypeError("trace must be exact WarehouseW3RootTransactionTraceReceipt")
    if type(root_final_absence) is not WarehouseW3RootFinalAbsenceReceipt:
        raise TypeError(
            "root_final_absence must be exact WarehouseW3RootFinalAbsenceReceipt"
        )
    if (
        type(staging_leaf) is not str
        or not staging_leaf
        or staging_leaf in {".", ".."}
        or "/" in staging_leaf
        or "\x00" in staging_leaf
    ):
        raise WarehouseW3RootSelectionError("K0 root-staging leaf differs")
    if (
        type(target_uid) is not int
        or type(target_gid) is not int
        or target_uid != 0
        or target_gid != 0
        or ingress.closure_sha256 != closure.raw_sha256
        or ingress.gate_sha256 != closure.gate.raw_sha256
        or trace.selection_key != closure.gate.selection_key
        or trace.launch_id != closure.gate.launch_id
        or trace.candidate_gate_sha256 != closure.gate.raw_sha256
        or trace.candidate_gate_closure_sha256 != closure.raw_sha256
        or trace.candidate_gate_ingress_sha256 != ingress.raw_sha256
        or trace.source_acceptance_sha256 != closure.gate.source_acceptance_sha256
        or trace.expected_root_final_absence_sha256 != root_final_absence.raw_sha256
        or root_final_absence.selection_key != closure.gate.selection_key
        or root_final_absence.launch_id != closure.gate.launch_id
        or root_final_absence.source_acceptance_sha256
        != closure.gate.source_acceptance_sha256
    ):
        raise WarehouseW3RootSelectionError(
            "K0 root-staging authority producer differs"
        )
    value = {
        "schema": "scion.w3-root-staging-effect-authority.v2",
        "selection_key": closure.gate.selection_key,
        "launch_id": closure.gate.launch_id,
        "candidate_gate_ingress_fact_sha256": ingress.raw_sha256,
        "candidate_gate_closure_sha256": closure.raw_sha256,
        "source_candidate_identity": ingress.candidate_identity.to_mapping(),
        "staging_leaf": staging_leaf,
        "target_uid": target_uid,
        "target_gid": target_gid,
        "root_transaction_trace_sha256": trace.raw_sha256,
        "expected_root_final_absence_sha256": (
            trace.expected_root_final_absence_sha256
        ),
        "root_final_absence_sha256": root_final_absence.raw_sha256,
    }
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def derive_root_selection_effect_authority_sha256(
    selection: "WarehouseW3RootSelectionReceipt",
) -> str:
    """Derive the K1 authority for one fixed root-owned selection slot."""

    if type(selection) is not WarehouseW3RootSelectionReceipt:
        raise TypeError("selection must be exact WarehouseW3RootSelectionReceipt")
    value = {
        "schema": "scion.w3-root-selection-effect-authority.v1",
        "selection_key": selection.selection_key,
        "launch_id": selection.launch_id,
        "selection_path": (
            f"/var/lib/scion/selections/w3/{selection.selection_key}.json"
        ),
        "root_selection_sha256": selection.raw_sha256,
    }
    return hashlib.sha256(_canonical_json(value)).hexdigest()


@dataclass(frozen=True, slots=True, init=False)
class WarehouseW3RootSelectionReceipt:
    selection_key: str
    launch_id: str
    nonce: str
    authority_sha256: str
    installation_sha256: str
    source_acceptance_sha256: str
    root_transaction_trace_sha256: str
    root_final_absence_sha256: str
    generic_selection_sha256: str
    staged_candidate_sha256: str
    root_staging_verification_sha256: str
    candidate_gate_ingress_fact_sha256: str
    candidate_gate_closure_sha256: str
    candidate_gate_sha256: str
    tree_import_sha256: str
    imported_tree_aggregate_sha256: str
    candidate_verification_sha256: str
    candidate_content_aggregate_sha256: str
    preparation_intent_sha256: str
    preparation_commit_sha256: str
    selection: SelectionReceipt
    staged_candidate: WarehouseW3StagedCandidateReceipt
    root_transaction_trace: WarehouseW3RootTransactionTraceReceipt
    root_final_absence: WarehouseW3RootFinalAbsenceReceipt
    raw: bytes
    raw_sha256: str

    def __new__(cls) -> "WarehouseW3RootSelectionReceipt":
        del cls
        raise TypeError(
            "WarehouseW3RootSelectionReceipt must be parsed from exact bytes"
        )

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("WarehouseW3RootSelectionReceipt is final")

    @classmethod
    def create(
        cls,
        *,
        selection: SelectionReceipt,
        staged_candidate: WarehouseW3StagedCandidateReceipt,
        trace: WarehouseW3RootTransactionTraceReceipt,
        root_final_absence: WarehouseW3RootFinalAbsenceReceipt,
    ) -> "WarehouseW3RootSelectionReceipt":
        if os.geteuid() != 0:
            raise PermissionError(
                "root selection construction requires effective UID zero"
            )
        return cls._create_for_test(
            selection=selection,
            staged_candidate=staged_candidate,
            trace=trace,
            root_final_absence=root_final_absence,
        )

    @classmethod
    def _create_for_test(
        cls,
        *,
        selection: SelectionReceipt,
        staged_candidate: WarehouseW3StagedCandidateReceipt,
        trace: WarehouseW3RootTransactionTraceReceipt,
        root_final_absence: WarehouseW3RootFinalAbsenceReceipt,
    ) -> "WarehouseW3RootSelectionReceipt":
        expected, selected, staged = cls._expected(
            selection,
            staged_candidate,
            trace,
            root_final_absence,
        )
        return cls.from_bytes(
            _canonical_json(expected),
            selection=selected,
            staged_candidate=staged,
            trace=trace,
            root_final_absence=root_final_absence,
        )

    @staticmethod
    def _expected(
        selection: SelectionReceipt,
        staged_candidate: WarehouseW3StagedCandidateReceipt,
        trace: WarehouseW3RootTransactionTraceReceipt,
        root_final_absence: WarehouseW3RootFinalAbsenceReceipt,
    ) -> tuple[
        dict[str, object],
        SelectionReceipt,
        WarehouseW3StagedCandidateReceipt,
    ]:
        if type(selection) is not SelectionReceipt:
            raise TypeError("selection must be exact SelectionReceipt")
        if type(staged_candidate) is not WarehouseW3StagedCandidateReceipt:
            raise TypeError(
                "staged_candidate must be exact " "WarehouseW3StagedCandidateReceipt"
            )
        if type(trace) is not WarehouseW3RootTransactionTraceReceipt:
            raise TypeError(
                "trace must be exact WarehouseW3RootTransactionTraceReceipt"
            )
        if type(root_final_absence) is not WarehouseW3RootFinalAbsenceReceipt:
            raise TypeError(
                "root_final_absence must be exact " "WarehouseW3RootFinalAbsenceReceipt"
            )
        selected = SelectionReceipt.from_bytes(selection.raw)
        verification = staged_candidate.root_staging_verification
        gate = verification.candidate_gate_closure.gate
        staged = WarehouseW3StagedCandidateReceipt.from_bytes(
            staged_candidate.raw,
            candidate_gate=gate,
            candidate_gate_ingress=staged_candidate.candidate_gate_ingress,
            tree_import=staged_candidate.tree_import,
            root_staging_verification=verification,
        )
        intent = verification.selection_intent
        commit = verification.selection_commit
        if (
            selected != selection
            or staged != staged_candidate
            or selected.selection_key != staged.selection_key
            or selected.selection_key != intent.selection_key
            or selected.launch_id != staged.launch_id
            or selected.launch_id != commit.launch_id
            or selected.nonce != gate.nonce
            or selected.authority_sha256 != staged.authority_sha256
            or selected.candidate_sha256 != gate.raw_sha256
            or selected.preparation_intent_sha256 != intent.raw_sha256
            or selected.preparation_commit_sha256 != commit.raw_sha256
            or selected.import_receipt_sha256 != staged.tree_import_sha256
            or selected.imported_staging_aggregate_sha256
            != staged.imported_tree_aggregate_sha256
            or _source_identity_tuple(selected.source_candidate_identity)
            != _source_identity_tuple(staged.source_identity)
            or trace.selection_key != staged.selection_key
            or trace.launch_id != staged.launch_id
            or trace.candidate_gate_sha256 != gate.raw_sha256
            or trace.candidate_gate_closure_sha256
            != staged.candidate_gate_closure_sha256
            or trace.candidate_gate_ingress_sha256
            != staged.candidate_gate_ingress_fact_sha256
            or trace.source_acceptance_sha256 != intent.source_acceptance_sha256
            or trace.expected_root_final_absence_sha256 != root_final_absence.raw_sha256
            or root_final_absence.selection_key != staged.selection_key
            or root_final_absence.launch_id != staged.launch_id
            or root_final_absence.source_acceptance_sha256
            != intent.source_acceptance_sha256
        ):
            raise WarehouseW3RootSelectionError(
                "generic selection differs from W3 staged candidate"
            )
        return (
            {
                "schema": _SCHEMA,
                "state": "ROOT_CANDIDATE_SELECTED",
                "plan_sha256": ACCEPTED_ROOT_INSTALLATION_PLAN_SHA256,
                "selection_key": staged.selection_key,
                "launch_id": staged.launch_id,
                "nonce": gate.nonce,
                "authority_sha256": staged.authority_sha256,
                "installation_sha256": staged.installation_sha256,
                "source_acceptance_sha256": intent.source_acceptance_sha256,
                "root_transaction_trace_sha256": trace.raw_sha256,
                "root_final_absence_sha256": root_final_absence.raw_sha256,
                "generic_selection_sha256": selected.raw_sha256,
                "staged_candidate_sha256": staged.raw_sha256,
                "root_staging_verification_sha256": (
                    staged.root_staging_verification_sha256
                ),
                "candidate_gate_ingress_fact_sha256": (
                    staged.candidate_gate_ingress_fact_sha256
                ),
                "candidate_gate_closure_sha256": (staged.candidate_gate_closure_sha256),
                "candidate_gate_sha256": staged.candidate_gate_sha256,
                "tree_import_sha256": staged.tree_import_sha256,
                "imported_tree_aggregate_sha256": (
                    staged.imported_tree_aggregate_sha256
                ),
                "candidate_verification_sha256": (staged.candidate_verification_sha256),
                "candidate_content_aggregate_sha256": (
                    staged.candidate_content_aggregate_sha256
                ),
                "preparation_intent_sha256": intent.raw_sha256,
                "preparation_commit_sha256": commit.raw_sha256,
                "retry": False,
                "resume": False,
                "reuse": False,
            },
            selected,
            staged,
        )

    @classmethod
    def from_bytes(
        cls,
        raw: bytes,
        *,
        selection: SelectionReceipt,
        staged_candidate: WarehouseW3StagedCandidateReceipt,
        trace: WarehouseW3RootTransactionTraceReceipt,
        root_final_absence: WarehouseW3RootFinalAbsenceReceipt,
    ) -> "WarehouseW3RootSelectionReceipt":
        expected, selected, staged = cls._expected(
            selection,
            staged_candidate,
            trace,
            root_final_absence,
        )
        value = _decode(raw, label="W3 root selection")
        if (
            frozenset(value) != frozenset(expected)
            or any(type(key) is not str for key in value)
            or _canonical_json(value) != _canonical_json(expected)
        ):
            raise WarehouseW3RootSelectionError(
                "W3 root selection producer binding differs"
            )
        instance = object.__new__(cls)
        for field, item in (
            *(
                (name, _sha256(expected[name], field=name))
                for name in (
                    "selection_key",
                    "launch_id",
                    "nonce",
                    "authority_sha256",
                    "installation_sha256",
                    "source_acceptance_sha256",
                    "root_transaction_trace_sha256",
                    "root_final_absence_sha256",
                    "generic_selection_sha256",
                    "staged_candidate_sha256",
                    "root_staging_verification_sha256",
                    "candidate_gate_ingress_fact_sha256",
                    "candidate_gate_closure_sha256",
                    "candidate_gate_sha256",
                    "tree_import_sha256",
                    "imported_tree_aggregate_sha256",
                    "candidate_verification_sha256",
                    "candidate_content_aggregate_sha256",
                    "preparation_intent_sha256",
                    "preparation_commit_sha256",
                )
            ),
            ("selection", selected),
            ("staged_candidate", staged),
            ("root_transaction_trace", trace),
            ("root_final_absence", root_final_absence),
            ("raw", raw),
            ("raw_sha256", hashlib.sha256(raw).hexdigest()),
        ):
            object.__setattr__(instance, field, item)
        return instance


@dataclass(frozen=True, slots=True)
class WarehouseW3SelectionReplayInputs:
    candidate_gate_closure_raw: bytes
    candidate_gate_ingress_fact_raw: bytes
    root_transaction_trace_raw: bytes
    root_final_absence_raw: bytes
    tree_import_raw: bytes
    candidate_receipt_raw: bytes
    source_receipt_raw: bytes
    sealed_store_receipt_raw: bytes
    environment_receipt_raw: bytes
    authority_raw: bytes
    installation_raw: bytes
    selection_intent_raw: bytes
    selection_commit_raw: bytes
    root_staging_verification_raw: bytes
    staged_candidate_raw: bytes
    generic_selection_raw: bytes
    root_selection_raw: bytes
    root_staging_intent_raw: bytes
    root_staging_receipt_raw: bytes
    candidate_selected_intent_raw: bytes
    candidate_selected_receipt_raw: bytes

    def __post_init__(self) -> None:
        for name in self.__dataclass_fields__:
            raw = getattr(self, name)
            if type(raw) is not bytes or not raw or len(raw) > _MAX_REPLAY_OBJECT_BYTES:
                raise TypeError(f"{name} must be bounded exact bytes")


@dataclass(frozen=True, slots=True)
class WarehouseW3SelectedCandidateChain:
    closure: CandidateGateClosureBundle
    ingress: CandidateGateIngressFact
    root_transaction_trace: WarehouseW3RootTransactionTraceReceipt
    root_final_absence: WarehouseW3RootFinalAbsenceReceipt
    tree_import: ImmutableTreeImportReceipt
    root_staging_verification: WarehouseW3RootStagingVerification
    staged_candidate: WarehouseW3StagedCandidateReceipt
    generic_selection: SelectionReceipt
    root_selection: WarehouseW3RootSelectionReceipt
    root_staging_intent: RootPhaseIntentReceipt
    root_staging_receipt: RootPhaseReceipt
    candidate_selected_intent: RootPhaseIntentReceipt
    candidate_selected_receipt: RootPhaseReceipt

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("WarehouseW3SelectedCandidateChain is final")


def selection_replay_inputs_from_chain(
    chain: WarehouseW3SelectedCandidateChain,
) -> WarehouseW3SelectionReplayInputs:
    """Freeze the exact replay payload for one already verified K0/K1 chain."""

    if type(chain) is not WarehouseW3SelectedCandidateChain:
        raise TypeError("chain must be exact WarehouseW3SelectedCandidateChain")
    verification = chain.root_staging_verification
    inputs = WarehouseW3SelectionReplayInputs(
        candidate_gate_closure_raw=chain.closure.raw,
        candidate_gate_ingress_fact_raw=chain.ingress.raw,
        root_transaction_trace_raw=chain.root_transaction_trace.raw,
        root_final_absence_raw=chain.root_final_absence.raw,
        tree_import_raw=chain.tree_import.raw,
        candidate_receipt_raw=verification.candidate_receipt.raw,
        source_receipt_raw=verification.source_receipt.raw,
        sealed_store_receipt_raw=verification.sealed_store_receipt.raw,
        environment_receipt_raw=verification.environment_receipt.raw,
        authority_raw=verification.authority.raw,
        installation_raw=verification.installation.raw,
        selection_intent_raw=verification.selection_intent.raw,
        selection_commit_raw=verification.selection_commit.raw,
        root_staging_verification_raw=verification.raw,
        staged_candidate_raw=chain.staged_candidate.raw,
        generic_selection_raw=chain.generic_selection.raw,
        root_selection_raw=chain.root_selection.raw,
        root_staging_intent_raw=chain.root_staging_intent.raw,
        root_staging_receipt_raw=chain.root_staging_receipt.raw,
        candidate_selected_intent_raw=chain.candidate_selected_intent.raw,
        candidate_selected_receipt_raw=chain.candidate_selected_receipt.raw,
    )
    if verify_w3_selected_candidate_chain(inputs) != chain:
        raise WarehouseW3RootSelectionError("selected candidate replay payload differs")
    return inputs


class RootSelectedCandidateAuthority:
    """Retained root-owned no-replace selection needed for authorization."""

    __slots__ = (
        "_chain",
        "_closed",
        "_descriptor",
        "_identity",
        "_parent",
    )

    def __new__(cls) -> "RootSelectedCandidateAuthority":
        del cls
        raise TypeError(
            "RootSelectedCandidateAuthority must be acquired from the fixed store"
        )

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("RootSelectedCandidateAuthority is final")

    @classmethod
    def acquire(
        cls,
        inputs: WarehouseW3SelectionReplayInputs,
    ) -> "RootSelectedCandidateAuthority":
        parent = pin_absolute_directory("/var/lib/scion/selections/w3")
        try:
            return cls._acquire_from_parent(
                parent,
                inputs,
                require_root_owner=True,
            )
        finally:
            parent.close()

    @classmethod
    def _acquire_for_test(
        cls,
        parent: PinnedDirectory,
        inputs: WarehouseW3SelectionReplayInputs,
    ) -> "RootSelectedCandidateAuthority":
        return cls._acquire_from_parent(
            parent,
            inputs,
            require_root_owner=False,
        )

    @classmethod
    def _acquire_from_parent(
        cls,
        parent: PinnedDirectory,
        inputs: WarehouseW3SelectionReplayInputs,
        *,
        require_root_owner: bool,
    ) -> "RootSelectedCandidateAuthority":
        if type(parent) is not PinnedDirectory:
            raise TypeError("selection parent must be exact PinnedDirectory")
        if type(require_root_owner) is not bool:
            raise TypeError("require_root_owner must be exact bool")
        chain = verify_w3_selected_candidate_chain(inputs)
        leaf = f"{chain.root_selection.selection_key}.json"
        parent.revalidate_mutable_leaf()
        parent_identity = FileIdentity.from_stat(os.fstat(parent.fd))
        if require_root_owner and (
            any(
                component.identity.uid != 0
                or component.identity.gid != 0
                or stat.S_IMODE(component.identity.mode) & 0o022
                for component in parent.components
            )
            or parent_identity.uid != 0
            or parent_identity.gid != 0
            or stat.S_IMODE(parent_identity.mode) & 0o022
        ):
            raise WarehouseW3RootSelectionError(
                "root selection parent ownership differs"
            )
        descriptor = os.open(
            leaf,
            os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
            dir_fd=parent.fd,
        )
        try:
            before = os.fstat(descriptor)
            named = os.stat(leaf, dir_fd=parent.fd, follow_symlinks=False)
            if (
                not stat.S_ISREG(before.st_mode)
                or stat.S_IMODE(before.st_mode) != 0o444
                or before.st_nlink != 1
                or (require_root_owner and (before.st_uid != 0 or before.st_gid != 0))
                or FileIdentity.from_stat(before) != FileIdentity.from_stat(named)
            ):
                raise WarehouseW3RootSelectionError(
                    "root selection file identity differs"
                )
            chunks: list[bytes] = []
            total = 0
            while True:
                remaining = _MAX_REPLAY_OBJECT_BYTES + 1 - total
                if remaining <= 0:
                    raise WarehouseW3RootSelectionError(
                        "root selection file exceeds its byte limit"
                    )
                chunk = os.read(descriptor, min(64 * 1024, remaining))
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
            after = os.fstat(descriptor)
            named_after = os.stat(
                leaf,
                dir_fd=parent.fd,
                follow_symlinks=False,
            )
            signature = lambda value: (
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
                or b"".join(chunks) != chain.root_selection.raw
            ):
                raise WarehouseW3RootSelectionError("root selection file bytes differ")
            instance = object.__new__(cls)
            instance._chain = chain
            instance._closed = False
            instance._descriptor = descriptor
            instance._identity = signature(after)
            instance._parent = parent.duplicate()
            descriptor = -1
            instance.revalidate()
            return instance
        finally:
            if descriptor >= 0:
                os.close(descriptor)

    @property
    def chain(self) -> WarehouseW3SelectedCandidateChain:
        self.revalidate()
        return self._chain

    def revalidate(self) -> None:
        if self._closed:
            raise WarehouseW3RootSelectionError("root selection authority is closed")
        self._parent.revalidate_mutable_leaf()
        current = os.fstat(self._descriptor)
        named = os.stat(
            f"{self._chain.root_selection.selection_key}.json",
            dir_fd=self._parent.fd,
            follow_symlinks=False,
        )
        signature = lambda value: (
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
            raise WarehouseW3RootSelectionError("root selection authority drifted")

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        os.close(self._descriptor)
        self._parent.close()

    def __enter__(self) -> "RootSelectedCandidateAuthority":
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


def verify_w3_selected_candidate_chain(
    inputs: WarehouseW3SelectionReplayInputs,
) -> WarehouseW3SelectedCandidateChain:
    """Deep-replay the exact closure, imported candidate, staged v3, K0 and K1."""

    if type(inputs) is not WarehouseW3SelectionReplayInputs:
        raise TypeError("inputs must be exact WarehouseW3SelectionReplayInputs")
    try:
        closure = CandidateGateClosureBundle.from_bytes(
            inputs.candidate_gate_closure_raw
        )
        ingress = CandidateGateIngressFact.from_bytes(
            inputs.candidate_gate_ingress_fact_raw
        )
        trace = WarehouseW3RootTransactionTraceReceipt.from_bytes(
            inputs.root_transaction_trace_raw
        )
        root_final_absence = WarehouseW3RootFinalAbsenceReceipt.from_bytes(
            inputs.root_final_absence_raw,
            candidate_absence=closure.absence_facts,
        )
        imported = ImmutableTreeImportReceipt.from_bytes(inputs.tree_import_raw)
        candidate = CandidateReceipt.from_bytes(inputs.candidate_receipt_raw)
        source = GitSourceReceipt.from_bytes(inputs.source_receipt_raw)
        sealed = SealedStoreReceipt.from_bytes(inputs.sealed_store_receipt_raw)
        environment = EnvironmentContentReceipt.from_bytes(
            inputs.environment_receipt_raw
        )
        authority = AcceptedLaunchAuthority.from_bytes(inputs.authority_raw)
        installation = InstallationRecord.from_bytes(
            inputs.installation_raw,
            authority,
        )
        intent = CandidateSelectionIntent.from_bytes(inputs.selection_intent_raw)
        commit = CandidateSelectionCommit.from_bytes(
            inputs.selection_commit_raw,
            intent,
        )
        verification = WarehouseW3RootStagingVerification.from_bytes(
            inputs.root_staging_verification_raw,
            candidate_gate=closure.gate,
            candidate_gate_closure=closure,
            candidate_gate_ingress=ingress,
            tree_import=imported,
            candidate_receipt=candidate,
            candidate_verification=closure.candidate_verification,
            source_receipt=source,
            sealed_store_receipt=sealed,
            environment_receipt=environment,
            authority=authority,
            installation=installation,
            selection_intent=intent,
            selection_commit=commit,
        )
        staged = WarehouseW3StagedCandidateReceipt.from_bytes(
            inputs.staged_candidate_raw,
            candidate_gate=closure.gate,
            candidate_gate_ingress=ingress,
            tree_import=imported,
            root_staging_verification=verification,
        )
        generic = SelectionReceipt.from_bytes(inputs.generic_selection_raw)
        root_selection = WarehouseW3RootSelectionReceipt.from_bytes(
            inputs.root_selection_raw,
            selection=generic,
            staged_candidate=staged,
            trace=trace,
            root_final_absence=root_final_absence,
        )
        k0_intent = RootPhaseIntentReceipt.from_bytes(inputs.root_staging_intent_raw)
        k0 = RootPhaseReceipt.from_bytes(inputs.root_staging_receipt_raw)
        k1_intent = RootPhaseIntentReceipt.from_bytes(
            inputs.candidate_selected_intent_raw
        )
        k1 = RootPhaseReceipt.from_bytes(inputs.candidate_selected_receipt_raw)
    except WarehouseW3RootSelectionError:
        raise
    except Exception as exc:
        raise WarehouseW3RootSelectionError(
            "W3 selected candidate producer replay failed"
        ) from exc

    def receipt_matches(
        phase_intent: RootPhaseIntentReceipt,
        receipt: RootPhaseReceipt,
    ) -> bool:
        return (
            receipt.launch_id == phase_intent.launch_id
            and receipt.phase is phase_intent.phase
            and receipt.intent_sha256 == phase_intent.raw_sha256
            and receipt.predecessor_sha256 == phase_intent.predecessor_sha256
            and receipt.effect_authority_sha256 == phase_intent.effect_authority_sha256
        )

    if (
        ingress.gate_sha256 != closure.gate.raw_sha256
        or ingress.gate_receipt_sha256 != closure.gate.raw_sha256
        or ingress.closure_sha256 != closure.raw_sha256
        or k0_intent.phase is not RootPhase.ROOT_STAGING_IMPORTED
        or k0_intent.launch_id != root_selection.launch_id
        or k0_intent.predecessor_sha256 != ()
        or k0_intent.effect_authority_sha256
        != derive_root_staging_effect_authority_sha256(
            closure,
            ingress,
            imported,
            trace,
            root_final_absence,
        )
        or not receipt_matches(k0_intent, k0)
        or k0.effect_sha256 != staged.raw_sha256
        or root_selection.root_transaction_trace_sha256 != trace.raw_sha256
        or root_selection.root_final_absence_sha256 != root_final_absence.raw_sha256
        or k1_intent.phase is not RootPhase.CANDIDATE_SELECTED
        or k1_intent.launch_id != root_selection.launch_id
        or k1_intent.predecessor_sha256 != (k0.raw_sha256,)
        or k1_intent.effect_authority_sha256
        != derive_root_selection_effect_authority_sha256(root_selection)
        or not receipt_matches(k1_intent, k1)
        or k1.effect_sha256 != root_selection.raw_sha256
    ):
        raise WarehouseW3RootSelectionError(
            "W3 K0/K1 selected candidate transaction differs"
        )
    return WarehouseW3SelectedCandidateChain(
        closure=closure,
        ingress=ingress,
        root_transaction_trace=trace,
        root_final_absence=root_final_absence,
        tree_import=imported,
        root_staging_verification=verification,
        staged_candidate=staged,
        generic_selection=generic,
        root_selection=root_selection,
        root_staging_intent=k0_intent,
        root_staging_receipt=k0,
        candidate_selected_intent=k1_intent,
        candidate_selected_receipt=k1,
    )


__all__ = [
    "RootSelectedCandidateAuthority",
    "WarehouseW3RootSelectionError",
    "WarehouseW3RootSelectionReceipt",
    "WarehouseW3SelectedCandidateChain",
    "WarehouseW3SelectionReplayInputs",
    "derive_root_staging_import_authority_sha256",
    "derive_root_selection_effect_authority_sha256",
    "derive_root_staging_effect_authority_sha256",
    "verify_w3_selected_candidate_chain",
    "selection_replay_inputs_from_chain",
]
