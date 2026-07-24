"""Root-owned W3 transaction trace and final-absence acquisition.

The trace is published before the first launch-specific root mutation.  The
final-absence receipt is derived before that publication, then reacquired after
the candidate import and before K0 commits.  Only explicit ``ENOENT`` and an
exhaustive procfs scan can establish absence.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
from pathlib import PurePosixPath
import re
import stat
from typing import Mapping

from .w3_candidate_gate import CandidateAbsenceFacts
from .w3_composition import EXPECTED_NONCE_LEDGER_PARENT

_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_MAX_RECEIPT_BYTES = 4 * 1024 * 1024
_MAX_PROC_BYTES = 1024 * 1024
_TRACE_SCHEMA = "scion.w3-root-transaction-trace.v1"
_ABSENCE_SCHEMA = "scion.w3-root-final-absence.v1"
ROOT_FINAL_ABSENCE_LEAF = "ROOT_FINAL_ABSENCE.v1.json"

_EXTRA_PATH_ROLES = (
    "acceptance_launch",
    "nonce_ledger",
    "root_selection",
    "template_close_dropin",
    "template_run_dropin",
)


class WarehouseW3RootPreflightError(RuntimeError):
    """The root transaction trace or final-absence evidence differs."""


def _canonical_json(value: Mapping[str, object]) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
        + b"\n"
    )


def _decode(raw: bytes, *, label: str) -> dict[str, object]:
    if type(raw) is not bytes or not raw or len(raw) > _MAX_RECEIPT_BYTES:
        raise WarehouseW3RootPreflightError(f"{label} is not bounded exact bytes")

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
    except (UnicodeError, ValueError, TypeError) as exc:
        raise WarehouseW3RootPreflightError(f"{label} is not canonical JSON") from exc
    if type(value) is not dict or _canonical_json(value) != raw:
        raise WarehouseW3RootPreflightError(f"{label} bytes are not canonical")
    return value


def _fields(
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
        raise WarehouseW3RootPreflightError(f"{label} fields differ")
    return value


def _sha256(value: object, *, field: str) -> str:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        raise WarehouseW3RootPreflightError(f"{field} is not one SHA-256 value")
    return value


def _absolute_path(value: object, *, field: str) -> str:
    if type(value) is not str or not value or len(value.encode("utf-8")) > 4096:
        raise WarehouseW3RootPreflightError(f"{field} is not bounded text")
    path = PurePosixPath(value)
    if (
        not path.is_absolute()
        or value == "/"
        or value.startswith("//")
        or str(path) != value
        or any(part in {"", ".", ".."} for part in path.parts[1:])
    ):
        raise WarehouseW3RootPreflightError(
            f"{field} is not one canonical absolute path"
        )
    return value


def _leaf(value: object, *, field: str) -> str:
    if (
        type(value) is not str
        or not value
        or value in {".", ".."}
        or "/" in value
        or "\x00" in value
        or len(value.encode("utf-8")) > 255
    ):
        raise WarehouseW3RootPreflightError(f"{field} is not one safe leaf")
    return value


def _observation_sha256(
    *,
    role: str,
    subject: str,
    candidate_absence_sha256: str,
    source_acceptance_sha256: str,
) -> str:
    return hashlib.sha256(
        _canonical_json(
            {
                "schema": "scion.w3-root-final-absence-observation.v1",
                "role": role,
                "subject": subject,
                "candidate_absence_sha256": candidate_absence_sha256,
                "source_acceptance_sha256": source_acceptance_sha256,
                "state": "ABSENT",
            }
        )
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class RootFinalAbsenceObservation:
    role: str
    subject: str
    observation_sha256: str
    state: str

    @classmethod
    def from_mapping(
        cls,
        value: object,
        *,
        candidate_absence_sha256: str,
        source_acceptance_sha256: str,
    ) -> "RootFinalAbsenceObservation":
        item = _fields(
            value,
            frozenset({"role", "subject", "observation_sha256", "state"}),
            label="root final-absence observation",
        )
        role = _leaf(item["role"], field="root absence role")
        subject = (
            item["subject"]
            if role == "process"
            else _absolute_path(item["subject"], field=f"root absence {role}")
        )
        if type(subject) is not str or not subject or item["state"] != "ABSENT":
            raise WarehouseW3RootPreflightError(
                "root final-absence observation state differs"
            )
        expected_sha = _observation_sha256(
            role=role,
            subject=subject,
            candidate_absence_sha256=candidate_absence_sha256,
            source_acceptance_sha256=source_acceptance_sha256,
        )
        if item["observation_sha256"] != expected_sha:
            raise WarehouseW3RootPreflightError(
                "root final-absence observation digest differs"
            )
        return cls(
            role=role,
            subject=subject,
            observation_sha256=expected_sha,
            state="ABSENT",
        )

    def to_mapping(self) -> dict[str, object]:
        return {
            "role": self.role,
            "subject": self.subject,
            "observation_sha256": self.observation_sha256,
            "state": self.state,
        }


@dataclass(frozen=True, slots=True, init=False)
class WarehouseW3RootFinalAbsenceReceipt:
    selection_key: str
    launch_id: str
    source_acceptance_sha256: str
    candidate_absence_sha256: str
    observations: tuple[RootFinalAbsenceObservation, ...]
    raw: bytes
    raw_sha256: str

    def __new__(cls) -> "WarehouseW3RootFinalAbsenceReceipt":
        del cls
        raise TypeError(
            "WarehouseW3RootFinalAbsenceReceipt must be parsed from exact bytes"
        )

    @classmethod
    def derive(
        cls,
        candidate_absence: CandidateAbsenceFacts,
        *,
        source_acceptance_sha256: str,
    ) -> "WarehouseW3RootFinalAbsenceReceipt":
        if type(candidate_absence) is not CandidateAbsenceFacts:
            raise TypeError("candidate_absence must be exact CandidateAbsenceFacts")
        acceptance = _sha256(
            source_acceptance_sha256,
            field="source acceptance sha256",
        )
        launch_id = _sha256(candidate_absence.launch_id, field="launch id")
        selection_key = _sha256(
            candidate_absence.selection_key,
            field="selection key",
        )
        subjects = {item.role: item.subject for item in candidate_absence.observations}
        subjects.update(
            {
                "acceptance_launch": (f"/var/lib/scion/acceptances/w3/{launch_id}"),
                "nonce_ledger": EXPECTED_NONCE_LEDGER_PARENT,
                "root_selection": (
                    f"/var/lib/scion/selections/w3/{selection_key}.json"
                ),
                "template_close_dropin": (
                    "/etc/systemd/system/scion-w3-close@.service.d"
                ),
                "template_run_dropin": ("/etc/systemd/system/scion-w3@.service.d"),
            }
        )
        roles = tuple(item.role for item in candidate_absence.observations) + (
            _EXTRA_PATH_ROLES
        )
        observations = tuple(
            RootFinalAbsenceObservation(
                role=role,
                subject=subjects[role],
                observation_sha256=_observation_sha256(
                    role=role,
                    subject=subjects[role],
                    candidate_absence_sha256=candidate_absence.raw_sha256,
                    source_acceptance_sha256=acceptance,
                ),
                state="ABSENT",
            )
            for role in roles
        )
        return cls.from_bytes(
            _canonical_json(
                {
                    "schema": _ABSENCE_SCHEMA,
                    "state": "ROOT_FINAL_ABSENT",
                    "selection_key": selection_key,
                    "launch_id": launch_id,
                    "source_acceptance_sha256": acceptance,
                    "candidate_absence_sha256": candidate_absence.raw_sha256,
                    "observations": [item.to_mapping() for item in observations],
                    "retry": False,
                    "resume": False,
                    "reuse": False,
                }
            ),
            candidate_absence=candidate_absence,
        )

    @classmethod
    def from_bytes(
        cls,
        raw: bytes,
        *,
        candidate_absence: CandidateAbsenceFacts,
    ) -> "WarehouseW3RootFinalAbsenceReceipt":
        if type(candidate_absence) is not CandidateAbsenceFacts:
            raise TypeError("candidate_absence must be exact CandidateAbsenceFacts")
        value = _fields(
            _decode(raw, label="root final-absence receipt"),
            frozenset(
                {
                    "schema",
                    "state",
                    "selection_key",
                    "launch_id",
                    "source_acceptance_sha256",
                    "candidate_absence_sha256",
                    "observations",
                    "retry",
                    "resume",
                    "reuse",
                }
            ),
            label="root final-absence receipt",
        )
        if (
            value["schema"] != _ABSENCE_SCHEMA
            or value["state"] != "ROOT_FINAL_ABSENT"
            or value["retry"] is not False
            or value["resume"] is not False
            or value["reuse"] is not False
            or value["candidate_absence_sha256"] != candidate_absence.raw_sha256
        ):
            raise WarehouseW3RootPreflightError(
                "root final-absence control binding differs"
            )
        launch_id = _sha256(value["launch_id"], field="root absence launch id")
        selection_key = _sha256(
            value["selection_key"],
            field="root absence selection key",
        )
        acceptance = _sha256(
            value["source_acceptance_sha256"],
            field="root absence source acceptance sha256",
        )
        raw_observations = value["observations"]
        if type(raw_observations) is not list:
            raise WarehouseW3RootPreflightError(
                "root final-absence observations are not an array"
            )
        observations = tuple(
            RootFinalAbsenceObservation.from_mapping(
                item,
                candidate_absence_sha256=candidate_absence.raw_sha256,
                source_acceptance_sha256=acceptance,
            )
            for item in raw_observations
        )
        expected_roles = (
            tuple(item.role for item in candidate_absence.observations)
            + _EXTRA_PATH_ROLES
        )
        candidate_subjects = {
            item.role: item.subject for item in candidate_absence.observations
        }
        if (
            launch_id != candidate_absence.launch_id
            or selection_key != candidate_absence.selection_key
            or tuple(item.role for item in observations) != expected_roles
            or any(
                item.subject != candidate_subjects[item.role]
                for item in observations[: len(candidate_absence.observations)]
            )
        ):
            raise WarehouseW3RootPreflightError(
                "root final-absence dependency binding differs"
            )
        instance = object.__new__(cls)
        for field, item in (
            ("selection_key", selection_key),
            ("launch_id", launch_id),
            ("source_acceptance_sha256", acceptance),
            ("candidate_absence_sha256", candidate_absence.raw_sha256),
            ("observations", observations),
            ("raw", raw),
            ("raw_sha256", hashlib.sha256(raw).hexdigest()),
        ):
            object.__setattr__(instance, field, item)
        return instance


@dataclass(frozen=True, slots=True, init=False)
class WarehouseW3RootTransactionTraceReceipt:
    selection_key: str
    launch_id: str
    candidate_gate_sha256: str
    candidate_gate_closure_sha256: str
    candidate_gate_ingress_sha256: str
    source_acceptance_sha256: str
    quarantine_leaf: str
    quarantine_path: str
    selection_path: str
    acceptance_path: str
    expected_root_final_absence_sha256: str
    raw: bytes
    raw_sha256: str

    def __new__(cls) -> "WarehouseW3RootTransactionTraceReceipt":
        del cls
        raise TypeError(
            "WarehouseW3RootTransactionTraceReceipt must be parsed from exact bytes"
        )

    @classmethod
    def create(
        cls,
        *,
        selection_key: str,
        launch_id: str,
        candidate_gate_sha256: str,
        candidate_gate_closure_sha256: str,
        candidate_gate_ingress_sha256: str,
        source_acceptance_sha256: str,
        quarantine_leaf: str,
        expected_root_final_absence_sha256: str,
    ) -> "WarehouseW3RootTransactionTraceReceipt":
        selection = _sha256(selection_key, field="trace selection key")
        launch = _sha256(launch_id, field="trace launch id")
        quarantine = _sha256(quarantine_leaf, field="trace quarantine leaf")
        return cls.from_bytes(
            _canonical_json(
                {
                    "schema": _TRACE_SCHEMA,
                    "state": "ROOT_TRANSACTION_OPENED",
                    "selection_key": selection,
                    "launch_id": launch,
                    "candidate_gate_sha256": candidate_gate_sha256,
                    "candidate_gate_closure_sha256": (candidate_gate_closure_sha256),
                    "candidate_gate_ingress_sha256": (candidate_gate_ingress_sha256),
                    "source_acceptance_sha256": source_acceptance_sha256,
                    "quarantine_leaf": quarantine,
                    "quarantine_path": (f"/var/lib/scion/imports/w3/{quarantine}"),
                    "selection_path": (
                        f"/var/lib/scion/selections/w3/{selection}.json"
                    ),
                    "acceptance_path": (f"/var/lib/scion/acceptances/w3/{launch}"),
                    "expected_root_final_absence_sha256": (
                        expected_root_final_absence_sha256
                    ),
                    "retry": False,
                    "resume": False,
                    "reuse": False,
                }
            )
        )

    @classmethod
    def from_bytes(
        cls,
        raw: bytes,
    ) -> "WarehouseW3RootTransactionTraceReceipt":
        value = _fields(
            _decode(raw, label="root transaction trace"),
            frozenset(
                {
                    "schema",
                    "state",
                    "selection_key",
                    "launch_id",
                    "candidate_gate_sha256",
                    "candidate_gate_closure_sha256",
                    "candidate_gate_ingress_sha256",
                    "source_acceptance_sha256",
                    "quarantine_leaf",
                    "quarantine_path",
                    "selection_path",
                    "acceptance_path",
                    "expected_root_final_absence_sha256",
                    "retry",
                    "resume",
                    "reuse",
                }
            ),
            label="root transaction trace",
        )
        if (
            value["schema"] != _TRACE_SCHEMA
            or value["state"] != "ROOT_TRANSACTION_OPENED"
            or value["retry"] is not False
            or value["resume"] is not False
            or value["reuse"] is not False
        ):
            raise WarehouseW3RootPreflightError(
                "root transaction trace controls differ"
            )
        selection = _sha256(value["selection_key"], field="trace selection key")
        launch = _sha256(value["launch_id"], field="trace launch id")
        quarantine = _sha256(
            value["quarantine_leaf"],
            field="trace quarantine leaf",
        )
        expected_paths = {
            "quarantine_path": f"/var/lib/scion/imports/w3/{quarantine}",
            "selection_path": (f"/var/lib/scion/selections/w3/{selection}.json"),
            "acceptance_path": f"/var/lib/scion/acceptances/w3/{launch}",
        }
        for name, expected in expected_paths.items():
            if _absolute_path(value[name], field=f"trace {name}") != expected:
                raise WarehouseW3RootPreflightError(
                    f"root transaction trace {name} differs"
                )
        instance = object.__new__(cls)
        for field, item in (
            ("selection_key", selection),
            ("launch_id", launch),
            (
                "candidate_gate_sha256",
                _sha256(value["candidate_gate_sha256"], field="trace gate sha256"),
            ),
            (
                "candidate_gate_closure_sha256",
                _sha256(
                    value["candidate_gate_closure_sha256"],
                    field="trace closure sha256",
                ),
            ),
            (
                "candidate_gate_ingress_sha256",
                _sha256(
                    value["candidate_gate_ingress_sha256"],
                    field="trace ingress sha256",
                ),
            ),
            (
                "source_acceptance_sha256",
                _sha256(
                    value["source_acceptance_sha256"],
                    field="trace source acceptance sha256",
                ),
            ),
            ("quarantine_leaf", quarantine),
            ("quarantine_path", expected_paths["quarantine_path"]),
            ("selection_path", expected_paths["selection_path"]),
            ("acceptance_path", expected_paths["acceptance_path"]),
            (
                "expected_root_final_absence_sha256",
                _sha256(
                    value["expected_root_final_absence_sha256"],
                    field="trace expected root absence sha256",
                ),
            ),
            ("raw", raw),
            ("raw_sha256", hashlib.sha256(raw).hexdigest()),
        ):
            object.__setattr__(instance, field, item)
        return instance


def root_transaction_trace_leaf(launch_id: str) -> str:
    return f"trace.{_sha256(launch_id, field='trace launch id')}.v1.json"


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


def _path_is_absent(subject: str) -> bool:
    path = PurePosixPath(_absolute_path(subject, field="root absence subject"))
    root_descriptor = os.open(
        "/",
        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
    )
    descriptors = [root_descriptor]
    edges: list[tuple[int, str, int, tuple[int, ...]]] = []

    def revalidate_chain() -> None:
        for parent, name, child, expected in edges:
            try:
                named = os.stat(
                    name,
                    dir_fd=parent,
                    follow_symlinks=False,
                )
            except OSError as exc:
                raise WarehouseW3RootPreflightError(
                    "root absence path ancestor drifted"
                ) from exc
            if _signature(named) != expected or _signature(os.fstat(child)) != expected:
                raise WarehouseW3RootPreflightError(
                    "root absence path ancestor drifted"
                )

    try:
        descriptor = root_descriptor
        for index, component in enumerate(path.parts[1:]):
            last = index == len(path.parts[1:]) - 1
            try:
                named = os.stat(
                    component,
                    dir_fd=descriptor,
                    follow_symlinks=False,
                )
            except FileNotFoundError:
                revalidate_chain()
                try:
                    os.stat(
                        component,
                        dir_fd=descriptor,
                        follow_symlinks=False,
                    )
                except FileNotFoundError:
                    revalidate_chain()
                    return True
                except OSError as exc:
                    raise WarehouseW3RootPreflightError(
                        "root absence path lookup is ambiguous"
                    ) from exc
                return False
            except OSError as exc:
                raise WarehouseW3RootPreflightError(
                    "root absence path lookup is ambiguous"
                ) from exc
            if last:
                return False
            if not stat.S_ISDIR(named.st_mode):
                raise WarehouseW3RootPreflightError(
                    "root absence path ancestor is not a directory"
                )
            try:
                child = os.open(
                    component,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                    dir_fd=descriptor,
                )
            except OSError as exc:
                raise WarehouseW3RootPreflightError(
                    "root absence path ancestor cannot be pinned"
                ) from exc
            opened = os.fstat(child)
            if _signature(opened) != _signature(named):
                os.close(child)
                raise WarehouseW3RootPreflightError(
                    "root absence path ancestor drifted"
                )
            expected = _signature(opened)
            edges.append((descriptor, component, child, expected))
            descriptors.append(child)
            descriptor = child
        raise WarehouseW3RootPreflightError("root absence path has no leaf")
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def _process_is_absent(token: str) -> bool:
    if type(token) is not str or not token or len(token.encode("utf-8")) > 4096:
        raise WarehouseW3RootPreflightError("root absence process token differs")
    needle = token.encode("utf-8", "strict")
    try:
        proc = os.open(
            "/proc",
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
        )
    except OSError as exc:
        raise WarehouseW3RootPreflightError("procfs cannot be pinned") from exc
    try:
        try:
            entries = tuple(
                name for name in os.listdir(proc) if name.isascii() and name.isdecimal()
            )
        except OSError as exc:
            raise WarehouseW3RootPreflightError("procfs cannot be listed") from exc
        for pid in entries:
            try:
                process = os.open(
                    pid,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                    dir_fd=proc,
                )
            except (FileNotFoundError, ProcessLookupError):
                continue
            except OSError as exc:
                raise WarehouseW3RootPreflightError(
                    "procfs process directory is ambiguous"
                ) from exc
            try:
                for leaf in ("cmdline", "cgroup"):
                    try:
                        descriptor = os.open(
                            leaf,
                            os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
                            dir_fd=process,
                        )
                    except (FileNotFoundError, ProcessLookupError):
                        continue
                    except OSError as exc:
                        raise WarehouseW3RootPreflightError(
                            "procfs process fact is ambiguous"
                        ) from exc
                    try:
                        chunks: list[bytes] = []
                        total = 0
                        while True:
                            remaining = _MAX_PROC_BYTES + 1 - total
                            if remaining <= 0:
                                raise WarehouseW3RootPreflightError(
                                    "procfs process fact exceeds its bound"
                                )
                            chunk = os.read(descriptor, min(64 * 1024, remaining))
                            if not chunk:
                                break
                            chunks.append(chunk)
                            total += len(chunk)
                        if needle in b"".join(chunks):
                            return False
                    finally:
                        os.close(descriptor)
            finally:
                os.close(process)
        return True
    finally:
        os.close(proc)


def acquire_root_final_absence(
    expected: WarehouseW3RootFinalAbsenceReceipt,
    *,
    candidate_absence: CandidateAbsenceFacts,
) -> WarehouseW3RootFinalAbsenceReceipt:
    """Typed acquisition entry point retaining the candidate absence object."""

    if type(expected) is not WarehouseW3RootFinalAbsenceReceipt:
        raise TypeError("expected must be exact WarehouseW3RootFinalAbsenceReceipt")
    if type(candidate_absence) is not CandidateAbsenceFacts:
        raise TypeError("candidate_absence must be exact CandidateAbsenceFacts")
    parsed = WarehouseW3RootFinalAbsenceReceipt.from_bytes(
        expected.raw,
        candidate_absence=candidate_absence,
    )
    for observation in parsed.observations:
        absent = (
            _process_is_absent(observation.subject)
            if observation.role == "process"
            else _path_is_absent(observation.subject)
        )
        if not absent:
            raise WarehouseW3RootPreflightError(
                f"root final-absence subject is present: {observation.role}"
            )
    return parsed


__all__ = [
    "ROOT_FINAL_ABSENCE_LEAF",
    "RootFinalAbsenceObservation",
    "WarehouseW3RootFinalAbsenceReceipt",
    "WarehouseW3RootPreflightError",
    "WarehouseW3RootTransactionTraceReceipt",
    "acquire_root_final_absence",
    "root_transaction_trace_leaf",
]
