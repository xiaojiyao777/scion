"""Warehouse binding of prospective user intent to one installed W3 launch."""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass

from scion.runtime.execution.external_installation import (
    INSTALL_PHASES,
    InstalledAcceptance,
    RootPhaseIntentReceipt,
    RootPhaseReceipt,
    StartAuthorizationReceipt,
)

from .w3_prestart_facts import WAREHOUSE_W3_PRESTART_EVIDENCE_SCHEMA
from .w3_installed_replay import RootInstalledAcceptanceAuthority
from .w3_root_installation import (
    WarehouseW3PreStartEvidence,
)
from .w3_installation import ACCEPTED_ROOT_INSTALLATION_PLAN_SHA256
from .w3_root_selection import (
    RootSelectedCandidateAuthority,
    WarehouseW3RootSelectionError,
    WarehouseW3SelectedCandidateChain,
    WarehouseW3SelectionReplayInputs,
    verify_w3_selected_candidate_chain,
)

_DATE_RE = re.compile(
    r"(?:19|20)[0-9]{2}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])\Z"
)
_EXPECTED_SCOPE = (
    "unique_root_selected_candidate_after_fixed_source_candidate_and_"
    "installed_acceptance"
)


class WarehouseW3StartAuthorizationError(RuntimeError):
    """Prospective intent cannot authorize this exact installed launch."""


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
        raise WarehouseW3StartAuthorizationError(
            "prospective intent is not canonical JSON data"
        ) from exc


def _decode(raw: bytes, *, label: str) -> dict[str, object]:
    if type(raw) is not bytes:
        raise TypeError(f"{label} must be exact bytes")

    def mapping(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate {label} field")
            result[key] = value
        return result

    try:
        value = json.loads(
            raw.decode("utf-8", "strict"),
            object_pairs_hook=mapping,
            parse_constant=lambda token: (_ for _ in ()).throw(
                ValueError(f"nonfinite {label} value: {token}")
            ),
        )
    except (UnicodeError, ValueError, TypeError) as exc:
        raise WarehouseW3StartAuthorizationError(
            f"{label} is not canonical JSON"
        ) from exc
    if type(value) is not dict or _canonical_json(value) != raw:
        raise WarehouseW3StartAuthorizationError(f"{label} bytes are not canonical")
    return value


def _bounded_text(value: object, *, field: str, maximum: int) -> str:
    if type(value) is not str or not value:
        raise WarehouseW3StartAuthorizationError(f"{field} is not exact text")
    try:
        encoded = value.encode("utf-8", "strict")
    except UnicodeError as exc:
        raise WarehouseW3StartAuthorizationError(f"{field} is not UTF-8") from exc
    if len(encoded) > maximum or any(byte < 0x20 or byte == 0x7F for byte in encoded):
        raise WarehouseW3StartAuthorizationError(f"{field} is not bounded text")
    return value


@dataclass(frozen=True, slots=True, init=False)
class ProspectiveStartAuthorizationIntent:
    statement: str
    statement_date: str
    raw: bytes
    raw_sha256: str

    def __new__(cls) -> "ProspectiveStartAuthorizationIntent":
        del cls
        raise TypeError(
            "ProspectiveStartAuthorizationIntent must be parsed from exact bytes"
        )

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("ProspectiveStartAuthorizationIntent is final")

    @classmethod
    def from_bytes(cls, raw: bytes) -> "ProspectiveStartAuthorizationIntent":
        value = _decode(raw, label="prospective intent")
        if frozenset(value) != frozenset(
            {
                "schema",
                "authorization_scope",
                "not_yet_bound_to_installed_receipts",
                "plan_sha256",
                "source",
                "statement",
                "statement_date",
                "retry",
                "resume",
                "reuse",
            }
        ):
            raise WarehouseW3StartAuthorizationError("prospective intent fields differ")
        if (
            value["schema"] != "scion.w3-prospective-start-authorization-intent.v1"
            or value["authorization_scope"] != _EXPECTED_SCOPE
            or value["not_yet_bound_to_installed_receipts"] is not True
            or value["plan_sha256"] != ACCEPTED_ROOT_INSTALLATION_PLAN_SHA256
            or value["source"] != "active_codex_task_user_message"
            or value["retry"] is not False
            or value["resume"] is not False
            or value["reuse"] is not False
        ):
            raise WarehouseW3StartAuthorizationError(
                "prospective intent authority differs"
            )
        statement = _bounded_text(
            value["statement"],
            field="prospective statement",
            maximum=4096,
        )
        statement_date = value["statement_date"]
        if (
            type(statement_date) is not str
            or _DATE_RE.fullmatch(statement_date) is None
        ):
            raise WarehouseW3StartAuthorizationError(
                "prospective statement date differs"
            )
        instance = object.__new__(cls)
        object.__setattr__(instance, "statement", statement)
        object.__setattr__(instance, "statement_date", statement_date)
        object.__setattr__(instance, "raw", raw)
        object.__setattr__(
            instance,
            "raw_sha256",
            hashlib.sha256(raw).hexdigest(),
        )
        return instance


def _reopen_prestart_evidence(
    evidence: WarehouseW3PreStartEvidence,
) -> WarehouseW3PreStartEvidence:
    if type(evidence) is not WarehouseW3PreStartEvidence:
        raise TypeError("prestart_evidence must be exact WarehouseW3PreStartEvidence")
    if (
        type(evidence.raw) is not bytes
        or hashlib.sha256(evidence.raw).hexdigest() != evidence.raw_sha256
    ):
        raise WarehouseW3StartAuthorizationError(
            "pre-start evidence raw identity differs"
        )
    value = _decode(evidence.raw, label="pre-start evidence")
    if frozenset(value) != frozenset(
        {
            "schema",
            "state",
            "plan_sha256",
            "launch_id",
            "authority_sha256",
            "installation_sha256",
            "pending_intent_sha256",
            "predecessor_phase_receipt_sha256",
            "phase_effect_sha256",
            "producer_receipt_sha256",
            "formal_jobs_started",
            "retry",
            "resume",
            "reuse",
        }
    ):
        raise WarehouseW3StartAuthorizationError("pre-start evidence fields differ")
    expected_effect_keys = frozenset(phase.value for phase in INSTALL_PHASES[:7])
    raw_effects = value["phase_effect_sha256"]
    raw_producers = value["producer_receipt_sha256"]
    if (
        type(raw_effects) is not dict
        or frozenset(raw_effects) != expected_effect_keys
        or type(raw_producers) is not dict
        or frozenset(raw_producers)
        != frozenset(
            {
                "candidate_gate",
                "dry_root",
                "environment_rehash",
                "loaded_manager",
                "prestart_absence",
                "runtime_account",
                "source_acceptance",
            }
        )
        or value["schema"] != WAREHOUSE_W3_PRESTART_EVIDENCE_SCHEMA
        or value["state"] != "PRESTART_GATES_REACQUIRED_NOT_STARTED"
        or value["plan_sha256"] != ACCEPTED_ROOT_INSTALLATION_PLAN_SHA256
        or value["formal_jobs_started"] != 0
        or type(value["formal_jobs_started"]) is not int
        or value["retry"] is not False
        or value["resume"] is not False
        or value["reuse"] is not False
        or value["launch_id"] != evidence.launch_id
        or value["authority_sha256"] != evidence.authority_sha256
        or value["installation_sha256"] != evidence.installation_sha256
        or value["pending_intent_sha256"] != evidence.pending_intent_sha256
        or value["predecessor_phase_receipt_sha256"]
        != evidence.predecessor_phase_receipt_sha256
        or raw_effects != dict(evidence.phase_effect_sha256)
        or raw_producers != dict(evidence.producer_receipt_sha256)
    ):
        raise WarehouseW3StartAuthorizationError("pre-start evidence authority differs")
    return evidence


def bind_start_authorization(
    prospective: ProspectiveStartAuthorizationIntent,
    *,
    root_selection_authority: RootSelectedCandidateAuthority,
    installed_acceptance_authority: RootInstalledAcceptanceAuthority,
    recorded_at_utc: str,
    unit: str,
) -> StartAuthorizationReceipt:
    """Bind prior intent through retained root selection and installation."""

    if type(prospective) is not ProspectiveStartAuthorizationIntent:
        raise TypeError("prospective must be exact ProspectiveStartAuthorizationIntent")
    if type(root_selection_authority) is not RootSelectedCandidateAuthority:
        raise TypeError(
            "root_selection_authority must be exact " "RootSelectedCandidateAuthority"
        )
    if type(installed_acceptance_authority) is not RootInstalledAcceptanceAuthority:
        raise TypeError(
            "installed_acceptance_authority must be exact "
            "RootInstalledAcceptanceAuthority"
        )
    if os.geteuid() != 0:
        raise PermissionError("start authorization binding requires effective UID zero")
    root_selection_authority.revalidate()
    installed_acceptance_authority.revalidate()
    installed_chain = installed_acceptance_authority.chain
    if installed_chain.selected_candidate != root_selection_authority.chain:
        raise WarehouseW3StartAuthorizationError(
            "root selection and installed acceptance authorities differ"
        )
    receipt = _bind_start_authorization_from_chain(
        prospective,
        selected_chain=root_selection_authority.chain,
        prestart_evidence=installed_chain.prestart_evidence,
        installed_acceptance=installed_chain.installed_acceptance,
        phase_intents=installed_chain.phase_intents,
        phase_receipts=installed_chain.phase_receipts,
        recorded_at_utc=recorded_at_utc,
        unit=unit,
    )
    root_selection_authority.revalidate()
    installed_acceptance_authority.revalidate()
    return receipt


def _bind_start_authorization_for_test(
    prospective: ProspectiveStartAuthorizationIntent,
    *,
    selection_replay_inputs: WarehouseW3SelectionReplayInputs,
    prestart_evidence: WarehouseW3PreStartEvidence,
    installed_acceptance: InstalledAcceptance,
    phase_intents: tuple[RootPhaseIntentReceipt, ...],
    phase_receipts: tuple[RootPhaseReceipt, ...],
    recorded_at_utc: str,
    unit: str,
) -> StartAuthorizationReceipt:
    if type(prospective) is not ProspectiveStartAuthorizationIntent:
        raise TypeError("prospective must be exact ProspectiveStartAuthorizationIntent")
    try:
        selected_chain = verify_w3_selected_candidate_chain(selection_replay_inputs)
    except WarehouseW3RootSelectionError as exc:
        raise WarehouseW3StartAuthorizationError(
            "root selection producer replay differs"
        ) from exc
    return _bind_start_authorization_from_chain(
        prospective,
        selected_chain=selected_chain,
        prestart_evidence=prestart_evidence,
        installed_acceptance=installed_acceptance,
        phase_intents=phase_intents,
        phase_receipts=phase_receipts,
        recorded_at_utc=recorded_at_utc,
        unit=unit,
    )


def _bind_start_authorization_from_chain(
    prospective: ProspectiveStartAuthorizationIntent,
    *,
    selected_chain: WarehouseW3SelectedCandidateChain,
    prestart_evidence: WarehouseW3PreStartEvidence,
    installed_acceptance: InstalledAcceptance,
    phase_intents: tuple[RootPhaseIntentReceipt, ...],
    phase_receipts: tuple[RootPhaseReceipt, ...],
    recorded_at_utc: str,
    unit: str,
) -> StartAuthorizationReceipt:
    if type(selected_chain) is not WarehouseW3SelectedCandidateChain:
        raise TypeError(
            "selected_chain must be exact WarehouseW3SelectedCandidateChain"
        )
    root_selection = selected_chain.root_selection
    generic_selection = selected_chain.generic_selection
    verification = selected_chain.root_staging_verification
    preparation_intent = verification.selection_intent
    preparation_commit = verification.selection_commit
    evidence = _reopen_prestart_evidence(prestart_evidence)
    if type(installed_acceptance) is not InstalledAcceptance:
        raise TypeError("installed_acceptance must be exact InstalledAcceptance")
    installed_acceptance.verify_phase_receipts(
        phase_intents,
        phase_receipts,
    )
    phase_effects = dict(installed_acceptance.phase_effect_sha256)
    evidence_effects = dict(evidence.phase_effect_sha256)
    candidate_identity = preparation_commit.candidate_root_identity
    selected_identity = generic_selection.source_candidate_identity
    if (
        preparation_commit.intent_sha256 != preparation_intent.raw_sha256
        or preparation_commit.selection_key != preparation_intent.selection_key
        or root_selection.selection_key != preparation_intent.selection_key
        or root_selection.preparation_intent_sha256 != preparation_intent.raw_sha256
        or root_selection.preparation_commit_sha256 != preparation_commit.raw_sha256
        or root_selection.nonce != preparation_commit.nonce
        or root_selection.launch_id != preparation_commit.launch_id
        or root_selection.authority_sha256 != preparation_commit.authority_sha256
        or root_selection.source_acceptance_sha256
        != preparation_intent.source_acceptance_sha256
        or dict(evidence.producer_receipt_sha256)["source_acceptance"]
        != root_selection.source_acceptance_sha256
        or (
            selected_identity.device,
            selected_identity.inode,
            selected_identity.mode,
            selected_identity.uid,
            selected_identity.gid,
            selected_identity.nlink,
        )
        != (
            candidate_identity.device,
            candidate_identity.inode,
            candidate_identity.mode,
            candidate_identity.uid,
            candidate_identity.gid,
            candidate_identity.nlink,
        )
        or phase_effects["CANDIDATE_SELECTED"] != root_selection.raw_sha256
        or phase_effects["ROOT_STAGING_IMPORTED"]
        != selected_chain.staged_candidate.raw_sha256
        or evidence_effects["CANDIDATE_SELECTED"] != root_selection.raw_sha256
        or evidence_effects["ROOT_STAGING_IMPORTED"]
        != selected_chain.staged_candidate.raw_sha256
        or tuple(phase_receipts[:2])
        != (
            selected_chain.root_staging_receipt,
            selected_chain.candidate_selected_receipt,
        )
        or tuple(phase_intents[:2])
        != (
            selected_chain.root_staging_intent,
            selected_chain.candidate_selected_intent,
        )
        or tuple(installed_acceptance.phase_effect_sha256[:7])
        != evidence.phase_effect_sha256
        or phase_effects["INSTANCES_LOADED"] != evidence.raw_sha256
        or installed_acceptance.problem_state_schema
        != WAREHOUSE_W3_PRESTART_EVIDENCE_SCHEMA
        or installed_acceptance.problem_state_sha256 != evidence.raw_sha256
        or evidence.launch_id != root_selection.launch_id
        or evidence.authority_sha256 != root_selection.authority_sha256
        or evidence.installation_sha256 != installed_acceptance.installation_sha256
        or installed_acceptance.launch_id != root_selection.launch_id
        or installed_acceptance.authority_sha256 != root_selection.authority_sha256
        or unit != f"scion-w3@{installed_acceptance.launch_id}.service"
    ):
        raise WarehouseW3StartAuthorizationError(
            "root selection and installed acceptance differ"
        )
    return StartAuthorizationReceipt.create(
        launch_id=installed_acceptance.launch_id,
        authority_sha256=installed_acceptance.authority_sha256,
        installation_sha256=installed_acceptance.installation_sha256,
        installed_acceptance_sha256=installed_acceptance.raw_sha256,
        prospective_intent_sha256=prospective.raw_sha256,
        plan_sha256=ACCEPTED_ROOT_INSTALLATION_PLAN_SHA256,
        selection_key=root_selection.selection_key,
        preparation_commit_sha256=(root_selection.preparation_commit_sha256),
        root_selection_sha256=root_selection.raw_sha256,
        external_source_acceptance_sha256=(root_selection.source_acceptance_sha256),
        user_statement=prospective.statement,
        task_event_identity=preparation_intent.task_event_identity,
        recorded_at_utc=recorded_at_utc,
        unit=unit,
    )


__all__ = [
    "ProspectiveStartAuthorizationIntent",
    "WarehouseW3StartAuthorizationError",
    "bind_start_authorization",
]
