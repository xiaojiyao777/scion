"""Capability-free Warehouse W3 facts reacquired before first start.

The codecs in this module accept already observed values.  They do not inspect
the filesystem, query the password database, contact systemd, or mutate any
external state.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Mapping

from scion.problems.warehouse_delivery.w3_candidate_gate import CandidateGateReceipt
from scion.problems.warehouse_delivery.w3_installation import (
    ACCEPTED_ROOT_INSTALLATION_PLAN_SHA256,
    CandidateRootIdentity,
)
from scion.runtime.execution.launch_authority import (
    AcceptedLaunchAuthority,
    InstallationRecord,
)

_SHA256_LENGTH = 64
_DRY_ROOT_SCHEMA = "scion.w3-dry-root-readiness.v1"
_ABSENCE_SCHEMA = "scion.w3-prestart-absence.v1"
_ACCOUNT_SCHEMA = "scion.w3-runtime-account.v1"
WAREHOUSE_W3_PRESTART_EVIDENCE_SCHEMA = "scion.w3-prestart-evidence.v2"
_ABSENCE_ROLES = tuple(
    sorted(
        {
            "external_nonce_claim",
            "invocation_nonce_claim",
            "terminal_root",
            "raw",
            "artifacts",
            "dynamic_control",
            "service_cgroup",
            "supervisor_cgroup",
            "start_issued",
            "process",
        }
    )
)


class WarehouseW3PreStartFactError(RuntimeError):
    """A W3 pre-start fact differs from its exact authority or observation."""


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
        raise WarehouseW3PreStartFactError(
            "pre-start fact is not canonical JSON data"
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
        raise WarehouseW3PreStartFactError(f"{label} is not canonical JSON") from exc
    if type(value) is not dict or _canonical_json(value) != raw:
        raise WarehouseW3PreStartFactError(f"{label} bytes are not canonical")
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
        raise WarehouseW3PreStartFactError(f"{label} fields differ")
    return value


def _text(value: object, *, field: str) -> str:
    if type(value) is not str or not value:
        raise WarehouseW3PreStartFactError(f"{field} must be nonempty exact text")
    try:
        encoded = value.encode("utf-8", "strict")
    except UnicodeError as exc:
        raise WarehouseW3PreStartFactError(f"{field} is not UTF-8") from exc
    if any(byte < 0x20 or byte == 0x7F for byte in encoded):
        raise WarehouseW3PreStartFactError(f"{field} contains a control character")
    return value


def _sha256(value: object, *, field: str) -> str:
    text = _text(value, field=field)
    if len(text) != _SHA256_LENGTH or any(
        character not in "0123456789abcdef" for character in text
    ):
        raise WarehouseW3PreStartFactError(f"{field} is not canonical SHA-256")
    return text


def _uint(value: object, *, field: str, positive: bool = False) -> int:
    minimum = 1 if positive else 0
    if type(value) is not int or value < minimum:
        raise WarehouseW3PreStartFactError(f"{field} is not an integer >= {minimum}")
    return value


def _false_controls(value: Mapping[str, object], *, label: str) -> None:
    if any(value.get(name) is not False for name in ("retry", "resume", "reuse")):
        raise WarehouseW3PreStartFactError(f"{label} enables retry, resume, or reuse")


def _identity_mapping(identity: CandidateRootIdentity) -> dict[str, int]:
    return identity.to_mapping()


def _reopen_candidate(candidate_gate: CandidateGateReceipt) -> CandidateGateReceipt:
    if type(candidate_gate) is not CandidateGateReceipt:
        raise TypeError("candidate_gate must be exact CandidateGateReceipt")
    reopened = CandidateGateReceipt.from_bytes(candidate_gate.raw)
    if reopened != candidate_gate:
        raise WarehouseW3PreStartFactError("candidate gate object differs")
    return reopened


def _bind_candidate_installation(
    candidate_gate: CandidateGateReceipt,
    installation: InstallationRecord,
) -> tuple[CandidateGateReceipt, InstallationRecord]:
    candidate = _reopen_candidate(candidate_gate)
    if type(installation) is not InstallationRecord:
        raise TypeError("installation must be exact InstallationRecord")
    installation_sha = hashlib.sha256(installation.raw).hexdigest()
    installation_value = _decode_canonical(
        installation.raw,
        label="installation dependency",
    )
    raw_authority_sha256 = installation_value.get("authority_sha256")
    if (
        installation_sha != installation.installation_sha256
        or installation_value.get("launch_id") != installation.launch_id
        or raw_authority_sha256 != installation.authority_sha256
        or installation_value.get("run_root") != installation.run_root
        or candidate.launch_id != installation.launch_id
        or candidate.authority_sha256 != installation.authority_sha256
        or candidate.installation_sha256 != installation.installation_sha256
        or candidate.accepted_root != installation.run_root
    ):
        raise WarehouseW3PreStartFactError(
            "candidate gate and installation binding differs"
        )
    return candidate, installation


def _reopen_authority_installation(
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
        raise WarehouseW3PreStartFactError("authority or installation object differs")
    return reopened_authority, reopened_installation


@dataclass(frozen=True, slots=True, init=False)
class WarehouseW3DryRootReadinessReceipt:
    candidate_gate_sha256: str
    launch_id: str
    authority_sha256: str
    installation_sha256: str
    run_root: str
    identity: CandidateRootIdentity
    inventory_sha256: str
    inventory_count: int
    read_only: bool
    composition_state: str
    cell_count: int
    job_count: int
    formal_jobs_started: int
    formal_execution_authorized: bool
    filesystem_mutated: bool
    raw: bytes
    raw_sha256: str

    def __new__(cls) -> "WarehouseW3DryRootReadinessReceipt":
        del cls
        raise TypeError(
            "WarehouseW3DryRootReadinessReceipt must be parsed from exact bytes"
        )

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("WarehouseW3DryRootReadinessReceipt is final")

    @classmethod
    def create(
        cls,
        *,
        candidate_gate: CandidateGateReceipt,
        installation: InstallationRecord,
        observed_identity: CandidateRootIdentity,
        observed_inventory_sha256: str,
        observed_inventory_count: int,
        observed_read_only: bool,
        composition_state: str,
    ) -> "WarehouseW3DryRootReadinessReceipt":
        candidate, installation_value = _bind_candidate_installation(
            candidate_gate,
            installation,
        )
        value = cls._expected(
            candidate,
            installation_value,
            observed_identity=observed_identity,
            observed_inventory_sha256=observed_inventory_sha256,
            observed_inventory_count=observed_inventory_count,
            observed_read_only=observed_read_only,
            composition_state=composition_state,
        )
        return cls.from_bytes(
            _canonical_json(value),
            candidate_gate=candidate,
            installation=installation_value,
            observed_identity=observed_identity,
            observed_inventory_sha256=observed_inventory_sha256,
            observed_inventory_count=observed_inventory_count,
            observed_read_only=observed_read_only,
            composition_state=composition_state,
        )

    @staticmethod
    def _expected(
        candidate: CandidateGateReceipt,
        installation: InstallationRecord,
        *,
        observed_identity: CandidateRootIdentity,
        observed_inventory_sha256: str,
        observed_inventory_count: int,
        observed_read_only: bool,
        composition_state: str,
    ) -> dict[str, object]:
        if type(observed_identity) is not CandidateRootIdentity:
            raise TypeError("observed_identity must be exact CandidateRootIdentity")
        inventory_sha = _sha256(
            observed_inventory_sha256,
            field="observed_inventory_sha256",
        )
        inventory_count = _uint(
            observed_inventory_count,
            field="observed_inventory_count",
            positive=True,
        )
        if type(observed_read_only) is not bool:
            raise TypeError("observed_read_only must be exact bool")
        state = _text(composition_state, field="composition_state")
        if (
            candidate.accepted_root != installation.run_root
            or candidate.accepted_root_identity != observed_identity
            or candidate.accepted_root_inventory_sha256 != inventory_sha
            or candidate.accepted_root_read_only is not True
            or observed_read_only is not True
            or state != "LAUNCH_READY"
            or candidate.cell_count != 43
            or candidate.job_count != 172
            or candidate.formal_jobs_started != 0
            or candidate.formal_execution_authorized is not False
            or candidate.filesystem_mutated is not False
        ):
            raise WarehouseW3PreStartFactError(
                "dry-root readiness observation differs from candidate gate"
            )
        return {
            "schema": _DRY_ROOT_SCHEMA,
            "candidate_gate_sha256": candidate.raw_sha256,
            "launch_id": candidate.launch_id,
            "authority_sha256": candidate.authority_sha256,
            "installation_sha256": installation.installation_sha256,
            "run_root": installation.run_root,
            "identity": _identity_mapping(observed_identity),
            "inventory_sha256": inventory_sha,
            "inventory_count": inventory_count,
            "read_only": True,
            "composition_state": "LAUNCH_READY",
            "cell_count": 43,
            "job_count": 172,
            "formal_jobs_started": 0,
            "formal_execution_authorized": False,
            "filesystem_mutated": False,
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
        installation: InstallationRecord,
        observed_identity: CandidateRootIdentity,
        observed_inventory_sha256: str,
        observed_inventory_count: int,
        observed_read_only: bool,
        composition_state: str,
    ) -> "WarehouseW3DryRootReadinessReceipt":
        candidate, installation_value = _bind_candidate_installation(
            candidate_gate,
            installation,
        )
        expected = cls._expected(
            candidate,
            installation_value,
            observed_identity=observed_identity,
            observed_inventory_sha256=observed_inventory_sha256,
            observed_inventory_count=observed_inventory_count,
            observed_read_only=observed_read_only,
            composition_state=composition_state,
        )
        value = _exact_fields(
            _decode_canonical(raw, label="W3 dry-root readiness receipt"),
            frozenset(expected),
            label="W3 dry-root readiness receipt",
        )
        _false_controls(value, label="W3 dry-root readiness receipt")
        if value != expected:
            raise WarehouseW3PreStartFactError(
                "dry-root readiness producer binding differs"
            )
        instance = object.__new__(cls)
        for field, item in (
            ("candidate_gate_sha256", candidate.raw_sha256),
            ("launch_id", candidate.launch_id),
            ("authority_sha256", candidate.authority_sha256),
            ("installation_sha256", installation_value.installation_sha256),
            ("run_root", installation_value.run_root),
            ("identity", observed_identity),
            ("inventory_sha256", observed_inventory_sha256),
            ("inventory_count", observed_inventory_count),
            ("read_only", True),
            ("composition_state", "LAUNCH_READY"),
            ("cell_count", 43),
            ("job_count", 172),
            ("formal_jobs_started", 0),
            ("formal_execution_authorized", False),
            ("filesystem_mutated", False),
            ("raw", raw),
            ("raw_sha256", hashlib.sha256(raw).hexdigest()),
        ):
            object.__setattr__(instance, field, item)
        return instance


@dataclass(frozen=True, slots=True)
class PreStartAbsenceObservation:
    role: str
    subject: str
    state: str = "ABSENT"

    def __post_init__(self) -> None:
        role = _text(self.role, field="pre-start absence role")
        if role not in _ABSENCE_ROLES:
            raise WarehouseW3PreStartFactError(
                "pre-start absence observation role differs"
            )
        _text(self.subject, field=f"pre-start absence {role} subject")
        if self.state != "ABSENT":
            raise WarehouseW3PreStartFactError(
                "pre-start absence observation is not ABSENT"
            )

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("PreStartAbsenceObservation is final")

    @classmethod
    def from_mapping(cls, value: object) -> "PreStartAbsenceObservation":
        item = _exact_fields(
            value,
            frozenset({"role", "subject", "state"}),
            label="pre-start absence observation",
        )
        return cls(
            role=item["role"],  # type: ignore[arg-type]
            subject=item["subject"],  # type: ignore[arg-type]
            state=item["state"],  # type: ignore[arg-type]
        )

    def to_mapping(self) -> dict[str, str]:
        return {
            "role": self.role,
            "subject": self.subject,
            "state": self.state,
        }


def _absence_subjects(
    authority: AcceptedLaunchAuthority,
    installation: InstallationRecord,
) -> dict[str, str]:
    terminal = installation.terminal_root
    service_cgroup = f"/sys/fs/cgroup/system.slice/{installation.run_unit}"
    return {
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


@dataclass(frozen=True, slots=True, init=False)
class WarehouseW3PreStartAbsenceReceipt:
    authority_sha256: str
    installation_sha256: str
    observations: tuple[PreStartAbsenceObservation, ...]
    raw: bytes
    raw_sha256: str

    def __new__(cls) -> "WarehouseW3PreStartAbsenceReceipt":
        del cls
        raise TypeError(
            "WarehouseW3PreStartAbsenceReceipt must be parsed from exact bytes"
        )

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("WarehouseW3PreStartAbsenceReceipt is final")

    @classmethod
    def create(
        cls,
        *,
        authority: AcceptedLaunchAuthority,
        installation: InstallationRecord,
        observations: tuple[PreStartAbsenceObservation, ...],
    ) -> "WarehouseW3PreStartAbsenceReceipt":
        authority_value, installation_value = _reopen_authority_installation(
            authority,
            installation,
        )
        expected_observations = cls._validate_observations(
            observations,
            authority=authority_value,
            installation=installation_value,
        )
        value = {
            "schema": _ABSENCE_SCHEMA,
            "authority_sha256": authority_value.authority_sha256,
            "installation_sha256": installation_value.installation_sha256,
            "observations": [
                observation.to_mapping() for observation in expected_observations
            ],
            "retry": False,
            "resume": False,
            "reuse": False,
        }
        return cls.from_bytes(
            _canonical_json(value),
            authority=authority_value,
            installation=installation_value,
            observations=expected_observations,
        )

    @staticmethod
    def _validate_observations(
        observations: tuple[PreStartAbsenceObservation, ...],
        *,
        authority: AcceptedLaunchAuthority,
        installation: InstallationRecord,
    ) -> tuple[PreStartAbsenceObservation, ...]:
        if type(observations) is not tuple or any(
            type(item) is not PreStartAbsenceObservation for item in observations
        ):
            raise TypeError(
                "observations must be exact tuple of PreStartAbsenceObservation"
            )
        subjects = _absence_subjects(authority, installation)
        expected = tuple(
            PreStartAbsenceObservation(role=role, subject=subjects[role])
            for role in _ABSENCE_ROLES
        )
        if observations != expected:
            raise WarehouseW3PreStartFactError(
                "pre-start absence observation inventory differs"
            )
        return observations

    @classmethod
    def from_bytes(
        cls,
        raw: bytes,
        *,
        authority: AcceptedLaunchAuthority,
        installation: InstallationRecord,
        observations: tuple[PreStartAbsenceObservation, ...],
    ) -> "WarehouseW3PreStartAbsenceReceipt":
        authority_value, installation_value = _reopen_authority_installation(
            authority,
            installation,
        )
        expected_observations = cls._validate_observations(
            observations,
            authority=authority_value,
            installation=installation_value,
        )
        expected = {
            "schema": _ABSENCE_SCHEMA,
            "authority_sha256": authority_value.authority_sha256,
            "installation_sha256": installation_value.installation_sha256,
            "observations": [
                observation.to_mapping() for observation in expected_observations
            ],
            "retry": False,
            "resume": False,
            "reuse": False,
        }
        value = _exact_fields(
            _decode_canonical(raw, label="W3 pre-start absence receipt"),
            frozenset(expected),
            label="W3 pre-start absence receipt",
        )
        _false_controls(value, label="W3 pre-start absence receipt")
        raw_observations = value["observations"]
        if type(raw_observations) is not list:
            raise WarehouseW3PreStartFactError(
                "pre-start absence observations are not an array"
            )
        parsed_observations = tuple(
            PreStartAbsenceObservation.from_mapping(item) for item in raw_observations
        )
        if parsed_observations != expected_observations or value != expected:
            raise WarehouseW3PreStartFactError(
                "pre-start absence producer binding differs"
            )
        instance = object.__new__(cls)
        for field, item in (
            ("authority_sha256", authority_value.authority_sha256),
            ("installation_sha256", installation_value.installation_sha256),
            ("observations", expected_observations),
            ("raw", raw),
            ("raw_sha256", hashlib.sha256(raw).hexdigest()),
        ):
            object.__setattr__(instance, field, item)
        return instance


@dataclass(frozen=True, slots=True, init=False)
class WarehouseW3RuntimeAccountReceipt:
    name: str
    uid: int
    gid: int
    source: str
    raw: bytes
    raw_sha256: str

    def __new__(cls) -> "WarehouseW3RuntimeAccountReceipt":
        del cls
        raise TypeError(
            "WarehouseW3RuntimeAccountReceipt must be parsed from exact bytes"
        )

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("WarehouseW3RuntimeAccountReceipt is final")

    @classmethod
    def create(
        cls,
        *,
        observed_name: str,
        observed_uid: int,
        observed_gid: int,
    ) -> "WarehouseW3RuntimeAccountReceipt":
        value = cls._expected(
            observed_name=observed_name,
            observed_uid=observed_uid,
            observed_gid=observed_gid,
        )
        return cls.from_bytes(
            _canonical_json(value),
            observed_name=observed_name,
            observed_uid=observed_uid,
            observed_gid=observed_gid,
        )

    @staticmethod
    def _expected(
        *,
        observed_name: str,
        observed_uid: int,
        observed_gid: int,
    ) -> dict[str, object]:
        name = _text(observed_name, field="observed runtime account name")
        uid = _uint(observed_uid, field="observed runtime account uid")
        gid = _uint(observed_gid, field="observed runtime account gid")
        if name != "clawd":
            raise WarehouseW3PreStartFactError("runtime account name differs")
        return {
            "schema": _ACCOUNT_SCHEMA,
            "name": "clawd",
            "uid": uid,
            "gid": gid,
            "source": "pwd.getpwnam",
            "retry": False,
            "resume": False,
            "reuse": False,
        }

    @classmethod
    def from_bytes(
        cls,
        raw: bytes,
        *,
        observed_name: str,
        observed_uid: int,
        observed_gid: int,
    ) -> "WarehouseW3RuntimeAccountReceipt":
        expected = cls._expected(
            observed_name=observed_name,
            observed_uid=observed_uid,
            observed_gid=observed_gid,
        )
        value = _exact_fields(
            _decode_canonical(raw, label="W3 runtime account receipt"),
            frozenset(expected),
            label="W3 runtime account receipt",
        )
        _false_controls(value, label="W3 runtime account receipt")
        if value != expected:
            raise WarehouseW3PreStartFactError(
                "runtime account producer binding differs"
            )
        instance = object.__new__(cls)
        for field, item in (
            ("name", "clawd"),
            ("uid", observed_uid),
            ("gid", observed_gid),
            ("source", "pwd.getpwnam"),
            ("raw", raw),
            ("raw_sha256", hashlib.sha256(raw).hexdigest()),
        ):
            object.__setattr__(instance, field, item)
        return instance


__all__ = [
    "ACCEPTED_ROOT_INSTALLATION_PLAN_SHA256",
    "WAREHOUSE_W3_PRESTART_EVIDENCE_SCHEMA",
    "PreStartAbsenceObservation",
    "WarehouseW3DryRootReadinessReceipt",
    "WarehouseW3PreStartAbsenceReceipt",
    "WarehouseW3PreStartFactError",
    "WarehouseW3RuntimeAccountReceipt",
]
