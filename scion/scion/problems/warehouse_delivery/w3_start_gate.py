"""Capability-free verification of one issued Warehouse W3 start.

This module consumes only bounded canonical receipt bytes and caller-owned
expected identities.  It performs no filesystem, manager, process, mount,
password-database, nonce, or terminal operation.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

from .w3_candidate_gate import CandidateGateReceipt
from .w3_environment_receipts import LiveEnvironmentRehashFact
from .w3_installation import CandidateRootIdentity
from .w3_installed_replay import (
    WarehouseW3InstalledReplayError,
    WarehouseW3InstalledReplayInputs,
    verify_w3_installed_replay,
)
from .w3_start_authorization import ProspectiveStartAuthorizationIntent
from .w3_prestart_facts import (
    ACCEPTED_ROOT_INSTALLATION_PLAN_SHA256,
    PreStartAbsenceObservation,
    WAREHOUSE_W3_PRESTART_EVIDENCE_SCHEMA,
    WarehouseW3DryRootReadinessReceipt,
    WarehouseW3PreStartAbsenceReceipt,
    WarehouseW3RuntimeAccountReceipt,
)
from .w3_root_selection import (
    WarehouseW3RootSelectionError,
    WarehouseW3SelectionReplayInputs,
    verify_w3_selected_candidate_chain,
)

_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_UNIT_RE = re.compile(r"[A-Za-z0-9:_.@-]+\.service\Z")
_UNIQUE_OWNER_RE = re.compile(r":[0-9]+\.[0-9]+\Z")
_BOOT_ID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-" r"[0-9a-f]{4}-[0-9a-f]{12}\Z"
)
_INSTALL_PHASES = (
    "ROOT_STAGING_IMPORTED",
    "CANDIDATE_SELECTED",
    "STORES_PUBLISHED",
    "AUTHORITY_PUBLISHED",
    "PROJECTION_MOUNTED",
    "UNITS_PUBLISHED",
    "MANAGER_RELOADED",
    "INSTANCES_LOADED",
    "INSTALLATION_ACCEPTED",
)
_PRESTART_PRODUCERS = frozenset(
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
_MAX_PRESTART_PRODUCER_BYTES = 64 * 1024 * 1024


class WarehouseW3StartPermitRefused(RuntimeError):
    """The issued permit or its authorization is missing or inconsistent."""


class WarehouseW3EnvironmentIntegrityRefused(RuntimeError):
    """The independently reacquired environment differs before nonce claim."""


class WarehouseW3InstalledIdentityRefused(RuntimeError):
    """The installed acceptance, W, K1, or selection chain differs."""


class WarehouseW3SystemdLineageRefused(RuntimeError):
    """Current systemd manager or invocation lineage differs."""


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
        raise ValueError("value is not canonical JSON data") from exc


def _decode(
    raw: bytes,
    *,
    label: str,
    error_type: type[RuntimeError],
) -> dict[str, object]:
    if type(raw) is not bytes:
        raise TypeError(f"{label} must be exact bytes")

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
                ValueError(f"{label} contains a floating-point value")
            ),
            parse_constant=lambda token: (_ for _ in ()).throw(
                ValueError(f"{label} contains {token}")
            ),
        )
        if type(value) is not dict or _canonical_json(value) != raw:
            raise ValueError(f"{label} bytes are not canonical")
    except (UnicodeError, ValueError, TypeError) as exc:
        raise error_type(f"{label} is not canonical JSON") from exc
    return value


def _exact(
    value: object,
    fields: frozenset[str],
    *,
    label: str,
    error_type: type[RuntimeError],
) -> dict[str, object]:
    if (
        type(value) is not dict
        or frozenset(value) != fields
        or any(type(key) is not str for key in value)
    ):
        raise error_type(f"{label} fields differ")
    return value


def _text(
    value: object,
    *,
    field: str,
    maximum: int,
    error_type: type[RuntimeError],
) -> str:
    if type(value) is not str or not value:
        raise error_type(f"{field} is not exact text")
    try:
        encoded = value.encode("utf-8", "strict")
    except UnicodeError as exc:
        raise error_type(f"{field} is not UTF-8") from exc
    if len(encoded) > maximum or any(byte < 0x20 or byte == 0x7F for byte in encoded):
        raise error_type(f"{field} is not bounded text")
    return value


def _sha(
    value: object,
    *,
    field: str,
    error_type: type[RuntimeError],
) -> str:
    text = _text(
        value,
        field=field,
        maximum=64,
        error_type=error_type,
    )
    if _SHA256_RE.fullmatch(text) is None:
        raise error_type(f"{field} is not canonical SHA-256")
    return text


def _sha_array(
    value: object,
    *,
    field: str,
    count: int,
    error_type: type[RuntimeError],
) -> tuple[str, ...]:
    if type(value) is not list or len(value) != count:
        raise error_type(f"{field} inventory differs")
    result = tuple(_sha(item, field=field, error_type=error_type) for item in value)
    if len(set(result)) != len(result):
        raise error_type(f"{field} contains a duplicate")
    return result


def _sha_mapping(
    value: object,
    *,
    field: str,
    keys: frozenset[str],
    error_type: type[RuntimeError],
) -> dict[str, str]:
    raw = _exact(
        value,
        keys,
        label=field,
        error_type=error_type,
    )
    return {
        key: _sha(
            raw[key],
            field=f"{field}.{key}",
            error_type=error_type,
        )
        for key in sorted(keys)
    }


def _uint(
    value: object,
    *,
    field: str,
    positive: bool,
    error_type: type[RuntimeError],
) -> int:
    minimum = 1 if positive else 0
    if type(value) is not int or value < minimum:
        raise error_type(f"{field} is not an integer >= {minimum}")
    return value


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True, slots=True)
class WarehouseW3IssuedStartGate:
    launch_id: str
    authority_sha256: str
    installation_sha256: str
    unit: str
    issue_sha256: str
    authorization_sha256: str
    installed_acceptance_sha256: str
    prestart_evidence_sha256: str
    loaded_manager_sha256: str
    candidate_selected_receipt_sha256: str
    root_selection_sha256: str
    source_acceptance_sha256: str
    staged_candidate_sha256: str
    root_staging_verification_sha256: str
    candidate_gate_ingress_fact_sha256: str
    candidate_gate_closure_sha256: str
    manager_unique_owner: str
    boot_id: str
    manager_version: str

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("WarehouseW3IssuedStartGate is final")


@dataclass(frozen=True, slots=True)
class WarehouseW3PreStartProducerReplayInputs:
    candidate_gate_raw: bytes
    dry_root_raw: bytes
    environment_rehash_raw: bytes
    loaded_manager_raw: bytes
    prestart_absence_raw: bytes
    runtime_account_raw: bytes

    def __post_init__(self) -> None:
        for name in self.__dataclass_fields__:
            raw = getattr(self, name)
            if (
                type(raw) is not bytes
                or not raw
                or len(raw) > _MAX_PRESTART_PRODUCER_BYTES
            ):
                raise TypeError(f"{name} must be bounded exact bytes")


def _verify_prestart_producers(
    inputs: WarehouseW3PreStartProducerReplayInputs,
    *,
    selected_chain: object,
    expected_sha256: dict[str, str],
    issue_manager_unique_owner: str,
    issue_boot_id: str,
    issue_manager_version: str,
    evidence_effects: dict[str, str],
) -> None:
    if type(inputs) is not WarehouseW3PreStartProducerReplayInputs:
        raise TypeError(
            "prestart_producer_replay_inputs must be exact "
            "WarehouseW3PreStartProducerReplayInputs"
        )
    chain = selected_chain
    try:
        candidate = CandidateGateReceipt.from_bytes(inputs.candidate_gate_raw)
        if candidate != chain.closure.gate:
            raise ValueError("candidate gate differs")
        dry_value = _decode(
            inputs.dry_root_raw,
            label="W3 dry-root readiness",
            error_type=WarehouseW3InstalledIdentityRefused,
        )
        dry_identity = CandidateRootIdentity.from_mapping(dry_value["identity"])
        dry_root = WarehouseW3DryRootReadinessReceipt.from_bytes(
            inputs.dry_root_raw,
            candidate_gate=candidate,
            installation=chain.root_staging_verification.installation,
            observed_identity=dry_identity,
            observed_inventory_sha256=dry_value["inventory_sha256"],
            observed_inventory_count=dry_value["inventory_count"],
            observed_read_only=dry_value["read_only"],
            composition_state=dry_value["composition_state"],
        )
        rehash = LiveEnvironmentRehashFact.from_bytes(inputs.environment_rehash_raw)
        absence_value = _decode(
            inputs.prestart_absence_raw,
            label="W3 pre-start absence",
            error_type=WarehouseW3InstalledIdentityRefused,
        )
        raw_observations = absence_value["observations"]
        if type(raw_observations) is not list:
            raise ValueError("absence observations differ")
        observations = tuple(
            PreStartAbsenceObservation.from_mapping(item) for item in raw_observations
        )
        absence = WarehouseW3PreStartAbsenceReceipt.from_bytes(
            inputs.prestart_absence_raw,
            authority=chain.root_staging_verification.authority,
            installation=chain.root_staging_verification.installation,
            observations=observations,
        )
        account_value = _decode(
            inputs.runtime_account_raw,
            label="W3 runtime account",
            error_type=WarehouseW3InstalledIdentityRefused,
        )
        account = WarehouseW3RuntimeAccountReceipt.from_bytes(
            inputs.runtime_account_raw,
            observed_name=account_value["name"],
            observed_uid=account_value["uid"],
            observed_gid=account_value["gid"],
        )
        loaded = _exact(
            _decode(
                inputs.loaded_manager_raw,
                label="loaded manager",
                error_type=WarehouseW3InstalledIdentityRefused,
            ),
            frozenset(
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
            label="loaded manager",
            error_type=WarehouseW3InstalledIdentityRefused,
        )
        loaded_manager = _exact(
            loaded["manager"],
            frozenset({"unique_owner", "boot_id", "version"}),
            label="loaded manager identity",
            error_type=WarehouseW3InstalledIdentityRefused,
        )
        installation = chain.root_staging_verification.installation
        semantic = chain.closure.semantic_environment
        if (
            rehash.phase != "preclaim"
            or rehash.content_receipt_sha256 != semantic.raw_sha256
            or rehash.generic_receipt_sha256 != semantic.generic_receipt_sha256
            or rehash.environment_root != installation.environment_root
            or rehash.observed_generic_receipt != chain.closure.environment_content
            or loaded["schema"] != "scion.loaded-manager-acceptance.v4"
            or loaded["run_unit"] != installation.run_unit
            or loaded["close_unit"] != installation.close_unit
            or loaded["configured_pair_sha256"] != installation.configured_pair_sha256
            or loaded["manager_reload_sha256"] != evidence_effects["MANAGER_RELOADED"]
            or loaded["unit_publication_sha256"] != evidence_effects["UNITS_PUBLISHED"]
            or loaded_manager
            != {
                "unique_owner": issue_manager_unique_owner,
                "boot_id": issue_boot_id,
                "version": issue_manager_version,
            }
            or account.uid == 0
            or account.gid == 0
            or dry_root.launch_id != installation.launch_id
            or absence.installation_sha256 != installation.installation_sha256
        ):
            raise ValueError("pre-start producer semantics differ")
        actual_sha256 = {
            "candidate_gate": _digest(inputs.candidate_gate_raw),
            "dry_root": _digest(inputs.dry_root_raw),
            "environment_rehash": _digest(inputs.environment_rehash_raw),
            "loaded_manager": _digest(inputs.loaded_manager_raw),
            "prestart_absence": _digest(inputs.prestart_absence_raw),
            "runtime_account": _digest(inputs.runtime_account_raw),
            "source_acceptance": (chain.root_selection.source_acceptance_sha256),
        }
        if actual_sha256 != expected_sha256:
            raise ValueError("pre-start producer hashes differ")
    except WarehouseW3InstalledIdentityRefused:
        raise
    except Exception as exc:
        raise WarehouseW3InstalledIdentityRefused(
            "W3 pre-start producer replay differs"
        ) from exc


def verify_w3_issued_start_gate(
    *,
    issue_raw: bytes,
    authorization_raw: bytes,
    prospective_intent_raw: bytes,
    installed_acceptance_raw: bytes,
    prestart_evidence_raw: bytes,
    prestart_producer_replay_inputs: WarehouseW3PreStartProducerReplayInputs,
    installed_replay_inputs: WarehouseW3InstalledReplayInputs,
    selection_replay_inputs: WarehouseW3SelectionReplayInputs,
    expected_launch_id: str,
    expected_authority_sha256: str,
    expected_installation_sha256: str,
    expected_unit: str,
) -> WarehouseW3IssuedStartGate:
    """Close ``START_ISSUED -> authorization -> A/W/K0/staged/K1``."""

    launch_id = _sha(
        expected_launch_id,
        field="expected_launch_id",
        error_type=WarehouseW3StartPermitRefused,
    )
    authority_sha256 = _sha(
        expected_authority_sha256,
        field="expected_authority_sha256",
        error_type=WarehouseW3InstalledIdentityRefused,
    )
    installation_sha256 = _sha(
        expected_installation_sha256,
        field="expected_installation_sha256",
        error_type=WarehouseW3InstalledIdentityRefused,
    )
    unit = _text(
        expected_unit,
        field="expected_unit",
        maximum=256,
        error_type=WarehouseW3StartPermitRefused,
    )
    if _UNIT_RE.fullmatch(unit) is None:
        raise WarehouseW3StartPermitRefused(
            "expected_unit is not a canonical service unit"
        )
    try:
        prospective = ProspectiveStartAuthorizationIntent.from_bytes(
            prospective_intent_raw
        )
    except Exception as exc:
        raise WarehouseW3StartPermitRefused(
            "prospective authorization intent differs"
        ) from exc
    try:
        selected_chain = verify_w3_selected_candidate_chain(selection_replay_inputs)
    except WarehouseW3RootSelectionError as exc:
        raise WarehouseW3InstalledIdentityRefused(
            "W3 selected candidate producer replay differs"
        ) from exc
    try:
        installed_chain = verify_w3_installed_replay(
            installed_replay_inputs,
            selection_replay_inputs,
        )
    except WarehouseW3InstalledReplayError as exc:
        raise WarehouseW3InstalledIdentityRefused(
            "W3 installed acceptance producer replay differs"
        ) from exc
    if (
        installed_chain.selected_candidate != selected_chain
        or installed_chain.installed_acceptance.raw != installed_acceptance_raw
        or installed_chain.prestart_evidence.raw != prestart_evidence_raw
        or installed_chain.loaded_manager.raw
        != prestart_producer_replay_inputs.loaded_manager_raw
        or installed_chain.environment_rehash.raw
        != prestart_producer_replay_inputs.environment_rehash_raw
        or installed_chain.dry_root.raw != prestart_producer_replay_inputs.dry_root_raw
        or installed_chain.prestart_absence.raw
        != prestart_producer_replay_inputs.prestart_absence_raw
        or installed_chain.runtime_account.raw
        != prestart_producer_replay_inputs.runtime_account_raw
        or selected_chain.closure.gate.raw
        != prestart_producer_replay_inputs.candidate_gate_raw
    ):
        raise WarehouseW3InstalledIdentityRefused(
            "installed replay bundle aliases different producer bytes"
        )
    candidate_selected_receipt_raw = selected_chain.candidate_selected_receipt.raw
    root_selection_raw = selected_chain.root_selection.raw

    issue = _exact(
        _decode(
            issue_raw,
            label="START_ISSUED",
            error_type=WarehouseW3StartPermitRefused,
        ),
        frozenset(
            {
                "schema",
                "launch_id",
                "authorization_sha256",
                "installation_sha256",
                "installed_acceptance_sha256",
                "prestart_receipt_sha256",
                "loaded_manager_sha256",
                "manager_unique_owner",
                "boot_id",
                "manager_version",
                "unit",
                "method",
                "mode",
                "retry",
                "resume",
                "reuse",
            }
        ),
        label="START_ISSUED",
        error_type=WarehouseW3StartPermitRefused,
    )
    authorization = _exact(
        _decode(
            authorization_raw,
            label="START_AUTHORIZED",
            error_type=WarehouseW3StartPermitRefused,
        ),
        frozenset(
            {
                "schema",
                "launch_id",
                "authority_sha256",
                "installation_sha256",
                "installed_acceptance_sha256",
                "prospective_intent_sha256",
                "plan_sha256",
                "selection_key",
                "preparation_commit_sha256",
                "root_selection_sha256",
                "external_source_acceptance_sha256",
                "user_statement",
                "task_event_identity",
                "recorded_at_utc",
                "unit",
                "method",
                "mode",
                "retry",
                "resume",
                "reuse",
            }
        ),
        label="START_AUTHORIZED",
        error_type=WarehouseW3StartPermitRefused,
    )
    acceptance = _exact(
        _decode(
            installed_acceptance_raw,
            label="installed acceptance",
            error_type=WarehouseW3InstalledIdentityRefused,
        ),
        frozenset(
            {
                "schema",
                "state",
                "formal_jobs_started",
                "launch_id",
                "authority_sha256",
                "installation_sha256",
                "phase_intent_sha256",
                "phase_receipt_sha256",
                "phase_effect_sha256",
                "problem_state_schema",
                "problem_state_sha256",
            }
        ),
        label="installed acceptance",
        error_type=WarehouseW3InstalledIdentityRefused,
    )
    evidence = _exact(
        _decode(
            prestart_evidence_raw,
            label="W3 pre-start evidence",
            error_type=WarehouseW3InstalledIdentityRefused,
        ),
        frozenset(
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
        ),
        label="W3 pre-start evidence",
        error_type=WarehouseW3InstalledIdentityRefused,
    )
    candidate_selected = _exact(
        _decode(
            candidate_selected_receipt_raw,
            label="K1 candidate-selected receipt",
            error_type=WarehouseW3InstalledIdentityRefused,
        ),
        frozenset(
            {
                "schema",
                "launch_id",
                "phase",
                "intent_sha256",
                "predecessor_sha256",
                "effect_authority_sha256",
                "effect_sha256",
            }
        ),
        label="K1 candidate-selected receipt",
        error_type=WarehouseW3InstalledIdentityRefused,
    )
    root_selection = selected_chain.root_selection
    generic_selection = selected_chain.generic_selection

    authorization_sha256 = _digest(authorization_raw)
    acceptance_sha256 = _digest(installed_acceptance_raw)
    evidence_sha256 = _digest(prestart_evidence_raw)
    candidate_selected_sha256 = _digest(candidate_selected_receipt_raw)
    selection_sha256 = _digest(root_selection_raw)

    for field in (
        "authorization_sha256",
        "installation_sha256",
        "installed_acceptance_sha256",
        "prestart_receipt_sha256",
        "loaded_manager_sha256",
    ):
        _sha(
            issue[field],
            field=f"START_ISSUED.{field}",
            error_type=WarehouseW3StartPermitRefused,
        )
    manager_unique_owner = _text(
        issue["manager_unique_owner"],
        field="START_ISSUED.manager_unique_owner",
        maximum=256,
        error_type=WarehouseW3StartPermitRefused,
    )
    boot_id = _text(
        issue["boot_id"],
        field="START_ISSUED.boot_id",
        maximum=36,
        error_type=WarehouseW3StartPermitRefused,
    )
    manager_version = _text(
        issue["manager_version"],
        field="START_ISSUED.manager_version",
        maximum=256,
        error_type=WarehouseW3StartPermitRefused,
    )
    if (
        issue["schema"] != "scion.start-issued.v2"
        or issue["launch_id"] != launch_id
        or issue["authorization_sha256"] != authorization_sha256
        or issue["installation_sha256"] != installation_sha256
        or issue["installed_acceptance_sha256"] != acceptance_sha256
        or issue["prestart_receipt_sha256"] != evidence_sha256
        or issue["loaded_manager_sha256"] != installed_chain.loaded_manager.raw_sha256
        or issue["unit"] != unit
        or issue["method"] != "StartUnit"
        or issue["mode"] != "fail"
        or issue["retry"] is not False
        or issue["resume"] is not False
        or issue["reuse"] is not False
        or _UNIQUE_OWNER_RE.fullmatch(manager_unique_owner) is None
        or _BOOT_ID_RE.fullmatch(boot_id) is None
        or re.match(r"255(?:\D|$)", manager_version) is None
    ):
        raise WarehouseW3StartPermitRefused("START_ISSUED authority differs")

    for field in (
        "authority_sha256",
        "installation_sha256",
        "installed_acceptance_sha256",
        "prospective_intent_sha256",
        "plan_sha256",
        "selection_key",
        "preparation_commit_sha256",
        "root_selection_sha256",
        "external_source_acceptance_sha256",
    ):
        _sha(
            authorization[field],
            field=f"START_AUTHORIZED.{field}",
            error_type=WarehouseW3StartPermitRefused,
        )
    _text(
        authorization["user_statement"],
        field="START_AUTHORIZED.user_statement",
        maximum=4096,
        error_type=WarehouseW3StartPermitRefused,
    )
    _text(
        authorization["task_event_identity"],
        field="START_AUTHORIZED.task_event_identity",
        maximum=256,
        error_type=WarehouseW3StartPermitRefused,
    )
    _text(
        authorization["recorded_at_utc"],
        field="START_AUTHORIZED.recorded_at_utc",
        maximum=64,
        error_type=WarehouseW3StartPermitRefused,
    )
    if (
        authorization["schema"] != "scion.start-authorization.v2"
        or authorization["launch_id"] != launch_id
        or authorization["authority_sha256"] != authority_sha256
        or authorization["installation_sha256"] != installation_sha256
        or authorization["installed_acceptance_sha256"] != acceptance_sha256
        or authorization["prospective_intent_sha256"] != prospective.raw_sha256
        or authorization["plan_sha256"] != ACCEPTED_ROOT_INSTALLATION_PLAN_SHA256
        or authorization["root_selection_sha256"] != selection_sha256
        or authorization["external_source_acceptance_sha256"]
        != root_selection.source_acceptance_sha256
        or authorization["user_statement"] != prospective.statement
        or authorization["unit"] != unit
        or authorization["method"] != "StartUnit"
        or authorization["mode"] != "fail"
        or authorization["retry"] is not False
        or authorization["resume"] is not False
        or authorization["reuse"] is not False
    ):
        raise WarehouseW3StartPermitRefused("START_AUTHORIZED authority differs")

    intent_sha256 = _sha_array(
        acceptance["phase_intent_sha256"],
        field="installed acceptance phase intents",
        count=8,
        error_type=WarehouseW3InstalledIdentityRefused,
    )
    receipt_sha256 = _sha_array(
        acceptance["phase_receipt_sha256"],
        field="installed acceptance phase receipts",
        count=8,
        error_type=WarehouseW3InstalledIdentityRefused,
    )
    acceptance_effects = _sha_mapping(
        acceptance["phase_effect_sha256"],
        field="installed acceptance phase effects",
        keys=frozenset(_INSTALL_PHASES[:8]),
        error_type=WarehouseW3InstalledIdentityRefused,
    )
    evidence_effects = _sha_mapping(
        evidence["phase_effect_sha256"],
        field="W3 pre-start phase effects",
        keys=frozenset(_INSTALL_PHASES[:7]),
        error_type=WarehouseW3InstalledIdentityRefused,
    )
    producer_sha256 = _sha_mapping(
        evidence["producer_receipt_sha256"],
        field="W3 pre-start producer receipts",
        keys=_PRESTART_PRODUCERS,
        error_type=WarehouseW3InstalledIdentityRefused,
    )
    _verify_prestart_producers(
        prestart_producer_replay_inputs,
        selected_chain=selected_chain,
        expected_sha256=producer_sha256,
        issue_manager_unique_owner=manager_unique_owner,
        issue_boot_id=boot_id,
        issue_manager_version=manager_version,
        evidence_effects=evidence_effects,
    )
    for value, field in (
        (acceptance["authority_sha256"], "acceptance.authority_sha256"),
        (acceptance["installation_sha256"], "acceptance.installation_sha256"),
        (acceptance["problem_state_sha256"], "acceptance.problem_state_sha256"),
        (evidence["authority_sha256"], "evidence.authority_sha256"),
        (evidence["installation_sha256"], "evidence.installation_sha256"),
        (evidence["pending_intent_sha256"], "evidence.pending_intent_sha256"),
        (
            evidence["predecessor_phase_receipt_sha256"],
            "evidence.predecessor_phase_receipt_sha256",
        ),
    ):
        _sha(
            value,
            field=field,
            error_type=WarehouseW3InstalledIdentityRefused,
        )
    if (
        acceptance["schema"] != "scion.external-installed-acceptance.v4"
        or acceptance["state"] != "INSTALLATION_ACCEPTED_NOT_STARTED"
        or type(acceptance["formal_jobs_started"]) is not int
        or acceptance["formal_jobs_started"] != 0
        or acceptance["launch_id"] != launch_id
        or acceptance["authority_sha256"] != authority_sha256
        or acceptance["installation_sha256"] != installation_sha256
        or acceptance["problem_state_schema"] != WAREHOUSE_W3_PRESTART_EVIDENCE_SCHEMA
        or acceptance["problem_state_sha256"] != evidence_sha256
        or acceptance_effects["INSTANCES_LOADED"] != evidence_sha256
        or evidence["schema"] != WAREHOUSE_W3_PRESTART_EVIDENCE_SCHEMA
        or evidence["state"] != "PRESTART_GATES_REACQUIRED_NOT_STARTED"
        or evidence["plan_sha256"] != ACCEPTED_ROOT_INSTALLATION_PLAN_SHA256
        or type(evidence["formal_jobs_started"]) is not int
        or evidence["formal_jobs_started"] != 0
        or evidence["launch_id"] != launch_id
        or evidence["authority_sha256"] != authority_sha256
        or evidence["installation_sha256"] != installation_sha256
        or evidence["retry"] is not False
        or evidence["resume"] is not False
        or evidence["reuse"] is not False
        or tuple((phase, acceptance_effects[phase]) for phase in _INSTALL_PHASES[:7])
        != tuple((phase, evidence_effects[phase]) for phase in _INSTALL_PHASES[:7])
        or evidence["pending_intent_sha256"] != intent_sha256[7]
        or evidence["predecessor_phase_receipt_sha256"] != receipt_sha256[6]
        or intent_sha256[0] != selected_chain.root_staging_intent.raw_sha256
        or receipt_sha256[0] != selected_chain.root_staging_receipt.raw_sha256
        or acceptance_effects["ROOT_STAGING_IMPORTED"]
        != selected_chain.staged_candidate.raw_sha256
        or evidence_effects["ROOT_STAGING_IMPORTED"]
        != selected_chain.staged_candidate.raw_sha256
    ):
        raise WarehouseW3InstalledIdentityRefused(
            "installed acceptance and W3 pre-start evidence differ"
        )

    candidate_predecessors = _sha_array(
        candidate_selected["predecessor_sha256"],
        field="K1 predecessor",
        count=1,
        error_type=WarehouseW3InstalledIdentityRefused,
    )
    for field in (
        "intent_sha256",
        "effect_authority_sha256",
        "effect_sha256",
    ):
        _sha(
            candidate_selected[field],
            field=f"K1.{field}",
            error_type=WarehouseW3InstalledIdentityRefused,
        )
    if (
        candidate_selected["schema"] != "scion.external-root-phase-commit.v2"
        or candidate_selected["launch_id"] != launch_id
        or candidate_selected["phase"] != "CANDIDATE_SELECTED"
        or candidate_selected["intent_sha256"] != intent_sha256[1]
        or candidate_predecessors != (receipt_sha256[0],)
        or candidate_selected["effect_sha256"] != selection_sha256
        or candidate_selected_sha256 != receipt_sha256[1]
        or candidate_selected_sha256
        != selected_chain.candidate_selected_receipt.raw_sha256
        or intent_sha256[1] != selected_chain.candidate_selected_intent.raw_sha256
        or acceptance_effects["CANDIDATE_SELECTED"] != selection_sha256
        or evidence_effects["CANDIDATE_SELECTED"] != selection_sha256
    ):
        raise WarehouseW3InstalledIdentityRefused(
            "K1 candidate selection binding differs"
        )

    if (
        root_selection.launch_id != launch_id
        or root_selection.authority_sha256 != authority_sha256
        or root_selection.installation_sha256 != installation_sha256
        or root_selection.selection_key != authorization["selection_key"]
        or root_selection.preparation_commit_sha256
        != authorization["preparation_commit_sha256"]
        or root_selection.source_acceptance_sha256
        != authorization["external_source_acceptance_sha256"]
        or selected_chain.root_staging_verification.selection_intent.task_event_identity
        != authorization["task_event_identity"]
        or generic_selection.preparation_commit_sha256
        != root_selection.preparation_commit_sha256
    ):
        raise WarehouseW3InstalledIdentityRefused("root selection authority differs")

    return WarehouseW3IssuedStartGate(
        launch_id=launch_id,
        authority_sha256=authority_sha256,
        installation_sha256=installation_sha256,
        unit=unit,
        issue_sha256=_digest(issue_raw),
        authorization_sha256=authorization_sha256,
        installed_acceptance_sha256=acceptance_sha256,
        prestart_evidence_sha256=evidence_sha256,
        loaded_manager_sha256=installed_chain.loaded_manager.raw_sha256,
        candidate_selected_receipt_sha256=candidate_selected_sha256,
        root_selection_sha256=selection_sha256,
        source_acceptance_sha256=root_selection.source_acceptance_sha256,
        staged_candidate_sha256=(selected_chain.staged_candidate.raw_sha256),
        root_staging_verification_sha256=(
            selected_chain.root_staging_verification.raw_sha256
        ),
        candidate_gate_ingress_fact_sha256=(selected_chain.ingress.raw_sha256),
        candidate_gate_closure_sha256=(selected_chain.closure.raw_sha256),
        manager_unique_owner=manager_unique_owner,
        boot_id=boot_id,
        manager_version=manager_version,
    )


__all__ = [
    "WarehouseW3EnvironmentIntegrityRefused",
    "WarehouseW3InstalledIdentityRefused",
    "WarehouseW3IssuedStartGate",
    "WarehouseW3PreStartProducerReplayInputs",
    "WarehouseW3StartPermitRefused",
    "WarehouseW3SystemdLineageRefused",
    "verify_w3_issued_start_gate",
]
