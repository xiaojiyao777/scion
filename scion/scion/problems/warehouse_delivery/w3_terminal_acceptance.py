"""Read-only Warehouse W3 terminal inspection and root-owned final acceptance."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Iterator, Mapping

from scion.runtime.execution.external_installation import (
    DurableReceiptDirectory,
    StartDispatchReceipt,
    StartDispatchState,
)
from scion.runtime.execution.invocation_terminal import (
    TerminalInspection,
    TerminalPolicy,
    inspect_terminal,
    load_invocation_lineage,
)
from scion.runtime.execution.launch_authority import (
    NonceClaimFact,
    inspect_nonce_claim,
)
from scion.runtime.execution.systemd_acquisition import (
    Systemd255Acquirer,
)

from .w3_analysis import replay_artifacts
from .w3_fixed_arm import read_regular
from .w3_installed_replay import (
    RootInstalledAcceptanceAuthority,
    _verify_no_w3_process,
    verify_live_w3_environment,
    verify_live_w3_projection,
)
from .w3_root_coordinator import _acquire_w3_configured_readback
from .w3_start_store import acquire_w3_issued_start_gate
from .w3_terminal_manager import WarehouseW3TerminalManager

_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_LAUNCH_ROOT = Path("/var/lib/scion/acceptances/w3")
_REPORT_LEAF = "TERMINAL_REPORT.v1.json"
_ACCEPTANCE_LEAF = "TERMINAL_ACCEPTED"
_START_BASE = frozenset(
    {
        "START_AUTHORIZED",
        "START_GATE_INPUTS.v1.json",
        "START_ISSUED",
    }
)
_START_OUTCOMES = frozenset(
    {"START_DISPATCH_UNKNOWN", "START_REJECTED", "START_RETURNED"}
)
_TERMINAL_CLASSIFICATIONS = frozenset(
    {
        "CLOSED_ACCEPTED",
        "INCOMPLETE_PRESERVED",
        "START_DISPATCH_REJECTED",
        "PRECLAIM_REFUSED_ENVIRONMENT_INTEGRITY",
        "PRECLAIM_REFUSED_INSTALLED_IDENTITY",
        "PRECLAIM_REFUSED_START_PERMIT",
        "PRECLAIM_REFUSED_SYSTEMD_LINEAGE",
        "PRECLAIM_TERMINATION_UNKNOWN",
    }
)
_PRECLAIM_STATUSES = {
    70: "PRECLAIM_REFUSED_START_PERMIT",
    71: "PRECLAIM_REFUSED_ENVIRONMENT_INTEGRITY",
    72: "PRECLAIM_REFUSED_INSTALLED_IDENTITY",
    73: "PRECLAIM_REFUSED_SYSTEMD_LINEAGE",
}
_UNIQUE_OWNER_RE = re.compile(r":[0-9]+\.[0-9]+\Z")
_BOOT_ID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-" r"[0-9a-f]{4}-[0-9a-f]{12}\Z"
)
_INVOCATION_ID_RE = re.compile(r"[0-9a-f]{32}\Z")
_EMPTY_INVOCATION_ID = "0" * 32
_PROPERTY_NAMES = (
    "Id",
    "InvocationID",
    "LoadState",
    "ActiveState",
    "SubState",
    "Result",
    "ExecMainCode",
    "ExecMainStatus",
)
_MAX_REPORT_BYTES = 4 * 1024 * 1024


class WarehouseW3TerminalAcceptanceError(RuntimeError):
    """Live terminal or final root-owned acceptance evidence differs."""


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
        raise WarehouseW3TerminalAcceptanceError(
            "terminal value is not canonical JSON"
        ) from exc


def _decode(raw: bytes, *, label: str) -> dict[str, object]:
    if type(raw) is not bytes or not raw or len(raw) > _MAX_REPORT_BYTES:
        raise WarehouseW3TerminalAcceptanceError(f"{label} bytes differ")

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
    except (UnicodeError, ValueError, TypeError) as exc:
        raise WarehouseW3TerminalAcceptanceError(
            f"{label} is not canonical JSON"
        ) from exc
    if type(value) is not dict or _canonical_json(value) != raw:
        raise WarehouseW3TerminalAcceptanceError(f"{label} bytes differ")
    return value


def _sha(value: object, *, field: str) -> str:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        raise WarehouseW3TerminalAcceptanceError(f"{field} is not SHA-256")
    return value


def _launch_id(value: object) -> str:
    return _sha(value, field="launch_id")


def _normalize_properties(
    value: Mapping[str, object],
    *,
    expected_unit: str,
) -> dict[str, object]:
    if frozenset(value) != frozenset(_PROPERTY_NAMES):
        raise WarehouseW3TerminalAcceptanceError(
            "terminal manager property inventory differs"
        )
    result: dict[str, object] = {}
    for name in _PROPERTY_NAMES:
        item = value[name]
        if name == "InvocationID":
            if (
                type(item) not in {tuple, list}
                or len(item) != 16
                or any(
                    type(octet) is not int or not 0 <= octet <= 255 for octet in item
                )
            ):
                raise WarehouseW3TerminalAcceptanceError(
                    "terminal manager InvocationID differs"
                )
            result[name] = bytes(item).hex()
        elif name in {"ExecMainCode", "ExecMainStatus"}:
            if type(item) is not int or not 0 <= item <= 255:
                raise WarehouseW3TerminalAcceptanceError(
                    f"terminal manager {name} differs"
                )
            result[name] = item
        elif type(item) is str and item and len(item.encode("utf-8")) <= 4096:
            result[name] = item
        else:
            raise WarehouseW3TerminalAcceptanceError(f"terminal manager {name} differs")
    if result["Id"] != expected_unit:
        raise WarehouseW3TerminalAcceptanceError(
            "terminal manager unit identity differs"
        )
    return result


def _unit_properties(
    reader: WarehouseW3TerminalManager,
    unit: str,
) -> dict[str, object]:
    return _normalize_properties(
        reader.read_properties(unit, _PROPERTY_NAMES),
        expected_unit=unit,
    )


@contextmanager
def _pinned_unit_reader(
    run_unit: str,
    close_unit: str,
) -> Iterator[WarehouseW3TerminalManager]:
    """Hold both accepted instances across the complete property acquisition."""

    reader = WarehouseW3TerminalManager()
    referenced: list[str] = []
    try:
        for unit in (run_unit, close_unit):
            reader.ref_unit(unit)
            referenced.append(unit)
        yield reader
    finally:
        release_error: Exception | None = None
        for unit in reversed(referenced):
            try:
                reader.unref_unit(unit)
            except Exception as exc:
                if release_error is None:
                    release_error = exc
        if release_error is not None:
            raise WarehouseW3TerminalAcceptanceError(
                "terminal unit references could not be released"
            ) from release_error


@contextmanager
def _stable_installed_snapshot(
    installed: RootInstalledAcceptanceAuthority,
    expected_verification: object,
) -> Iterator[None]:
    installed.revalidate()
    if (
        installed.chain.selected_candidate.root_staging_verification
        != expected_verification
    ):
        raise WarehouseW3TerminalAcceptanceError(
            "installed verification changed before terminal inspection"
        )
    yield
    installed.revalidate()


def _root_receipt(path: Path, *, maximum: int = 4 * 1024 * 1024) -> bytes:
    snapshot = read_regular(path)
    metadata = os.lstat(path)
    if (
        stat.S_ISLNK(metadata.st_mode)
        or not stat.S_ISREG(metadata.st_mode)
        or stat.S_IMODE(metadata.st_mode) != 0o444
        or metadata.st_uid != 0
        or metadata.st_gid != 0
        or metadata.st_nlink != 1
        or snapshot.size_bytes > maximum
    ):
        raise WarehouseW3TerminalAcceptanceError(
            f"root receipt identity differs: {path.name}"
        )
    return snapshot.data


def _start_outcome(
    launch_id: str,
    *,
    expected_issue_sha256: str,
) -> tuple[str, str | None]:
    start_root = _LAUNCH_ROOT / launch_id / "start"
    try:
        names = frozenset(os.listdir(start_root))
    except OSError as exc:
        raise WarehouseW3TerminalAcceptanceError(
            "root start receipt store cannot be inspected"
        ) from exc
    outcomes = names & _START_OUTCOMES
    if names == _START_BASE:
        return "START_DISPATCH_UNKNOWN", None
    if len(outcomes) != 1 or names != _START_BASE | outcomes:
        raise WarehouseW3TerminalAcceptanceError("root start receipt inventory differs")
    outcome = next(iter(outcomes))
    raw = _root_receipt(start_root / outcome)
    try:
        receipt = StartDispatchReceipt.from_bytes(raw)
    except Exception as exc:
        raise WarehouseW3TerminalAcceptanceError(
            "root start outcome receipt differs"
        ) from exc
    expected_state = {
        "START_DISPATCH_UNKNOWN": StartDispatchState.UNKNOWN,
        "START_REJECTED": StartDispatchState.REJECTED,
        "START_RETURNED": StartDispatchState.RETURNED,
    }[outcome]
    if (
        receipt.state is not expected_state
        or receipt.issue_sha256 != expected_issue_sha256
    ):
        raise WarehouseW3TerminalAcceptanceError("root start outcome binding differs")
    return outcome, hashlib.sha256(raw).hexdigest()


def _claim_state(authority: object, installation: object) -> tuple[str, str]:
    expected = NonceClaimFact.create(authority, installation)  # type: ignore[arg-type]
    external = Path(installation.projected_nonce_ledger_parent) / (
        f"{authority.nonce}.claim.json"
    )
    invocation = (
        Path(installation.projected_terminal_root)
        / "control"
        / "invocation_claimed.v1.json"
    )
    external_present = os.path.lexists(external)
    invocation_present = os.path.lexists(invocation)
    if not external_present and not invocation_present:
        return "ABSENT", expected.claim_sha256
    if not external_present or not invocation_present:
        raise WarehouseW3TerminalAcceptanceError(
            "nonce claim locations form a partial hold"
        )
    actual = inspect_nonce_claim(authority, installation)  # type: ignore[arg-type]
    if actual != expected:
        raise WarehouseW3TerminalAcceptanceError("nonce claim differs")
    return "CLAIMED", expected.claim_sha256


def _terminal_inspection(
    terminal_root: Path,
    policy: TerminalPolicy,
) -> TerminalInspection:
    if not os.path.lexists(terminal_root):
        return TerminalInspection("ABSENT", 0, 0)
    return inspect_terminal(terminal_root, policy)


def _terminal_cgroup_absent(chain: object, run_unit: str) -> None:
    _verify_no_w3_process(run_unit)
    observations = {
        item.role: item.subject
        for item in chain.selected_candidate.closure.absence_facts.observations
    }
    cgroup = observations.get("cgroup")
    if type(cgroup) is not str or os.path.lexists(cgroup):
        raise WarehouseW3TerminalAcceptanceError(
            "terminal W3 cgroup is present or ambiguous"
        )


def _successful_artifacts(
    chain: object,
    terminal_root: Path,
) -> tuple[tuple[dict[str, object], ...], str]:
    installation = chain.selected_candidate.root_staging_verification.installation
    authority = chain.selected_candidate.root_staging_verification.authority
    rows: list[bytes] = []
    identities: list[dict[str, object]] = []
    for ordinal in range(authority.expected_rows):
        snapshot = read_regular(terminal_root / "raw" / f"{ordinal:06d}.opaque")
        rows.append(snapshot.data)
        identities.append(
            {
                "job_ordinal": ordinal,
                "opaque_publication_key": f"warehouse-w3-row-{ordinal:03d}",
                "sha256": snapshot.sha256,
                "size_bytes": snapshot.size_bytes,
            }
        )
    manifest = json.loads(
        read_regular(
            Path(installation.run_root) / authority.manifest_path,
            expected_sha256=authority.manifest_sha256,
        ).data
    )
    if type(manifest) is not dict:
        raise WarehouseW3TerminalAcceptanceError("W3 manifest differs")
    expected_results, expected_report, expected_receipt, _value = replay_artifacts(
        manifest,
        authority.manifest_sha256,
        tuple(rows),
        tuple(identities),
    )
    expected = (expected_results, expected_report, expected_receipt)
    summaries: list[dict[str, object]] = []
    for name, raw in zip(authority.artifact_names, expected, strict=True):
        actual = read_regular(terminal_root / "artifacts" / "final" / name)
        if actual.data != raw:
            raise WarehouseW3TerminalAcceptanceError(
                f"terminal W3 artifact differs: {name}"
            )
        summaries.append(
            {
                "name": name,
                "sha256": actual.sha256,
                "size_bytes": actual.size_bytes,
            }
        )
    return tuple(summaries), hashlib.sha256(expected_receipt).hexdigest()


def _unit_is_terminal(properties: Mapping[str, object]) -> bool:
    return (
        properties.get("LoadState") == "loaded"
        and properties.get("ActiveState") in {"inactive", "failed"}
        and properties.get("SubState") in {"dead", "failed"}
        and properties.get("ExecMainCode") in {1, 2, 3}
        and type(properties.get("ExecMainStatus")) is int
    )


def _closer_succeeded(properties: Mapping[str, object]) -> bool:
    return (
        _unit_is_terminal(properties)
        and properties.get("ActiveState") == "inactive"
        and properties.get("SubState") == "dead"
        and properties.get("Result") == "success"
        and properties.get("ExecMainCode") == 1
        and properties.get("ExecMainStatus") == 0
    )


def _prestart_unit_is_absent(properties: Mapping[str, object]) -> bool:
    return (
        properties.get("LoadState") == "loaded"
        and properties.get("ActiveState") == "inactive"
        and properties.get("SubState") == "dead"
        and properties.get("InvocationID") == _EMPTY_INVOCATION_ID
        and properties.get("ExecMainCode") == 0
        and properties.get("ExecMainStatus") == 0
    )


def _validate_report_properties(
    value: object,
    *,
    field: str,
) -> Mapping[str, object]:
    if type(value) is not dict or frozenset(value) != frozenset(_PROPERTY_NAMES):
        raise WarehouseW3TerminalAcceptanceError(
            f"Warehouse W3 terminal report {field} fields differ"
        )
    copied: dict[str, object] = {}
    for name in _PROPERTY_NAMES:
        item = value[name]
        if name == "InvocationID":
            if type(item) is not str or _INVOCATION_ID_RE.fullmatch(item) is None:
                raise WarehouseW3TerminalAcceptanceError(
                    f"Warehouse W3 terminal report {field} InvocationID differs"
                )
        elif name in {"ExecMainCode", "ExecMainStatus"}:
            if type(item) is not int or not 0 <= item <= 255:
                raise WarehouseW3TerminalAcceptanceError(
                    f"Warehouse W3 terminal report {field} status differs"
                )
        elif (
            type(item) is not str
            or not item
            or len(item.encode("utf-8", "strict")) > 4096
        ):
            raise WarehouseW3TerminalAcceptanceError(
                f"Warehouse W3 terminal report {field} property differs"
            )
        copied[name] = item
    return MappingProxyType(copied)


def _validate_report_artifacts(
    value: object,
) -> tuple[Mapping[str, object], ...]:
    if type(value) is not list or len(value) > 3:
        raise WarehouseW3TerminalAcceptanceError(
            "Warehouse W3 terminal report artifacts differ"
        )
    artifacts: list[Mapping[str, object]] = []
    names: set[str] = set()
    for item in value:
        if (
            type(item) is not dict
            or frozenset(item) != {"name", "sha256", "size_bytes"}
            or type(item["name"]) is not str
            or not item["name"]
            or len(item["name"].encode("utf-8", "strict")) > 128
            or item["name"] in names
            or type(item["size_bytes"]) is not int
            or item["size_bytes"] <= 0
        ):
            raise WarehouseW3TerminalAcceptanceError(
                "Warehouse W3 terminal report artifact fields differ"
            )
        names.add(item["name"])
        artifacts.append(
            MappingProxyType(
                {
                    "name": item["name"],
                    "sha256": _sha(
                        item["sha256"],
                        field="terminal artifact sha256",
                    ),
                    "size_bytes": item["size_bytes"],
                }
            )
        )
    return tuple(artifacts)


@dataclass(frozen=True, slots=True, init=False)
class WarehouseW3TerminalReport:
    launch_id: str
    authority_sha256: str
    installation_sha256: str
    installed_acceptance_sha256: str
    start_issue_sha256: str
    start_outcome: str
    start_outcome_sha256: str | None
    manager: Mapping[str, str]
    run_properties: Mapping[str, object]
    close_properties: Mapping[str, object]
    nonce_claim_state: str
    nonce_claim_sha256: str
    terminal_state: str
    evidence_count: int
    row_count: int
    classification: str
    artifacts: tuple[Mapping[str, object], ...]
    replay_receipt_sha256: str | None
    raw: bytes
    raw_sha256: str

    def __new__(cls) -> "WarehouseW3TerminalReport":
        del cls
        raise TypeError("WarehouseW3TerminalReport must be parsed from exact bytes")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("WarehouseW3TerminalReport is final")

    @classmethod
    def from_bytes(cls, raw: bytes) -> "WarehouseW3TerminalReport":
        value = _decode(raw, label="Warehouse W3 terminal report")
        expected = frozenset(
            {
                "schema",
                "launch_id",
                "authority_sha256",
                "installation_sha256",
                "installed_acceptance_sha256",
                "start_issue_sha256",
                "start_outcome",
                "start_outcome_sha256",
                "manager",
                "run_properties",
                "close_properties",
                "nonce_claim_state",
                "nonce_claim_sha256",
                "terminal_state",
                "evidence_count",
                "row_count",
                "classification",
                "artifacts",
                "replay_receipt_sha256",
                "retry",
                "resume",
                "reuse",
            }
        )
        if (
            frozenset(value) != expected
            or value["schema"] != "scion.w3-terminal-report.v1"
            or value["retry"] is not False
            or value["resume"] is not False
            or value["reuse"] is not False
        ):
            raise WarehouseW3TerminalAcceptanceError(
                "Warehouse W3 terminal report fields differ"
            )
        manager = value["manager"]
        if (
            type(manager) is not dict
            or frozenset(manager) != {"unique_owner", "boot_id", "version"}
            or type(manager["unique_owner"]) is not str
            or _UNIQUE_OWNER_RE.fullmatch(manager["unique_owner"]) is None
            or type(manager["boot_id"]) is not str
            or _BOOT_ID_RE.fullmatch(manager["boot_id"]) is None
            or type(manager["version"]) is not str
            or not (
                manager["version"] == "255" or manager["version"].startswith("255.")
            )
            or len(manager["version"].encode("utf-8", "strict")) > 256
            or type(value["evidence_count"]) is not int
            or not 0 <= value["evidence_count"] <= 172
            or type(value["row_count"]) is not int
            or not 0 <= value["row_count"] <= value["evidence_count"]
            or type(value["classification"]) is not str
            or value["classification"]
            not in _TERMINAL_CLASSIFICATIONS | {"PENDING", "INTEGRITY_HOLD"}
            or type(value["start_outcome"]) is not str
            or value["start_outcome"] not in _START_OUTCOMES
            or value["nonce_claim_state"] not in {"ABSENT", "CLAIMED"}
            or type(value["terminal_state"]) is not str
            or not value["terminal_state"]
            or len(value["terminal_state"].encode("utf-8", "strict")) > 256
        ):
            raise WarehouseW3TerminalAcceptanceError(
                "Warehouse W3 terminal report value types differ"
            )
        run = _validate_report_properties(
            value["run_properties"],
            field="run_properties",
        )
        close = _validate_report_properties(
            value["close_properties"],
            field="close_properties",
        )
        artifacts = _validate_report_artifacts(value["artifacts"])
        optional = value["start_outcome_sha256"]
        replay = value["replay_receipt_sha256"]
        outcome_sha = (
            None if optional is None else _sha(optional, field="start_outcome_sha256")
        )
        replay_sha = (
            None if replay is None else _sha(replay, field="replay_receipt_sha256")
        )
        classification = value["classification"]
        if (
            (
                value["start_outcome"] in {"START_RETURNED", "START_REJECTED"}
                and outcome_sha is None
            )
            or (
                classification == "CLOSED_ACCEPTED"
                and (
                    value["terminal_state"] != "CLOSED"
                    or value["nonce_claim_state"] != "CLAIMED"
                    or value["evidence_count"] != 172
                    or value["row_count"] != 172
                    or len(artifacts) != 3
                    or replay_sha is None
                )
            )
            or (
                classification == "INCOMPLETE_PRESERVED"
                and (
                    value["terminal_state"] != "INCOMPLETE"
                    or value["nonce_claim_state"] != "CLAIMED"
                    or artifacts
                    or replay_sha is not None
                )
            )
            or (
                classification == "START_DISPATCH_REJECTED"
                and (
                    value["start_outcome"] != "START_REJECTED"
                    or value["terminal_state"] != "ABSENT"
                    or value["nonce_claim_state"] != "ABSENT"
                    or value["evidence_count"] != 0
                    or value["row_count"] != 0
                    or artifacts
                    or replay_sha is not None
                )
            )
            or (
                classification.startswith("PRECLAIM_")
                and (
                    value["terminal_state"] != "ABSENT"
                    or value["nonce_claim_state"] != "ABSENT"
                    or value["evidence_count"] != 0
                    or value["row_count"] != 0
                    or artifacts
                    or replay_sha is not None
                )
            )
        ):
            raise WarehouseW3TerminalAcceptanceError(
                "Warehouse W3 terminal report classification differs"
            )
        fields = {
            "launch_id": _launch_id(value["launch_id"]),
            "authority_sha256": _sha(
                value["authority_sha256"],
                field="authority_sha256",
            ),
            "installation_sha256": _sha(
                value["installation_sha256"],
                field="installation_sha256",
            ),
            "installed_acceptance_sha256": _sha(
                value["installed_acceptance_sha256"],
                field="installed_acceptance_sha256",
            ),
            "start_issue_sha256": _sha(
                value["start_issue_sha256"],
                field="start_issue_sha256",
            ),
            "start_outcome": value["start_outcome"],
            "start_outcome_sha256": outcome_sha,
            "manager": MappingProxyType(dict(manager)),
            "run_properties": run,
            "close_properties": close,
            "nonce_claim_state": value["nonce_claim_state"],
            "nonce_claim_sha256": _sha(
                value["nonce_claim_sha256"],
                field="nonce_claim_sha256",
            ),
            "terminal_state": value["terminal_state"],
            "evidence_count": value["evidence_count"],
            "row_count": value["row_count"],
            "classification": classification,
            "artifacts": artifacts,
            "replay_receipt_sha256": replay_sha,
            "raw": raw,
            "raw_sha256": hashlib.sha256(raw).hexdigest(),
        }
        instance = object.__new__(cls)
        for name, item in fields.items():
            object.__setattr__(instance, name, item)
        return instance


def _inspect_w3_terminal_pinned(
    normalized: str,
    installed: RootInstalledAcceptanceAuthority,
    reader: WarehouseW3TerminalManager,
) -> WarehouseW3TerminalReport:
    if type(installed) is not RootInstalledAcceptanceAuthority:
        raise TypeError("installed must be exact RootInstalledAcceptanceAuthority")
    if type(reader) is not WarehouseW3TerminalManager:
        raise TypeError("reader must be exact WarehouseW3TerminalManager")
    initial_verification = installed.chain.selected_candidate.root_staging_verification
    initial_authority = initial_verification.authority
    initial_installation = initial_verification.installation
    with acquire_w3_issued_start_gate(
        expected_launch_id=normalized,
        expected_authority_sha256=initial_authority.authority_sha256,
        expected_installation_sha256=initial_installation.installation_sha256,
        expected_unit=initial_installation.run_unit,
    ) as start:
        chain = installed.chain
        verification = chain.selected_candidate.root_staging_verification
        authority = verification.authority
        installation = verification.installation
        if verification != initial_verification:
            raise WarehouseW3TerminalAcceptanceError(
                "installed verification changed before terminal inspection"
            )
        with _stable_installed_snapshot(installed, initial_verification):
            manager = Systemd255Acquirer(reader).acquire_manager_identity()
            if (
                manager.unique_owner != start.gate.manager_unique_owner
                or manager.boot_id != start.gate.boot_id
                or manager.version != start.gate.manager_version
            ):
                raise WarehouseW3TerminalAcceptanceError(
                    "systemd manager identity changed after START_ISSUED"
                )
            policy_claim = NonceClaimFact.create(authority, installation)
            policy = TerminalPolicy(
                authority_sha256=authority.authority_sha256,
                manifest_sha256=authority.manifest_sha256,
                invocation_nonce=authority.nonce,
                expected_rows=authority.expected_rows,
                artifact_names=authority.artifact_names,
                nonce_claim_sha256=policy_claim.claim_sha256,
            )
            terminal_root = Path(installation.terminal_root)
            terminal = _terminal_inspection(terminal_root, policy)
            claim_state, claim_sha = _claim_state(authority, installation)
            run = _unit_properties(reader, installation.run_unit)
            close = _unit_properties(reader, installation.close_unit)
            outcome, outcome_sha = _start_outcome(
                normalized,
                expected_issue_sha256=start.gate.issue_sha256,
            )
            classification = "PENDING"
            artifacts: tuple[dict[str, object], ...] = ()
            replay_sha: str | None = None
            units_terminal = _unit_is_terminal(run) and _unit_is_terminal(close)
            projection = installation.projection_root

            def acquire_run_final():
                invocation_id = run["InvocationID"]
                if (
                    type(invocation_id) is not str
                    or invocation_id == _EMPTY_INVOCATION_ID
                ):
                    raise WarehouseW3TerminalAcceptanceError(
                        "terminal W3 run invocation identity differs"
                    )
                return Systemd255Acquirer(reader).acquire_unit_final(
                    expected_unit=installation.run_unit,
                    expected_invocation_id=invocation_id,
                    expected_exec_path=f"{projection}/environment/bin/python",
                    expected_argv=(
                        f"{projection}/environment/bin/python",
                        "-I",
                        "-B",
                        f"{projection}/sealed/bin/scion-w3-tool",
                        "seal-unit-drained",
                        normalized,
                    ),
                )

            if terminal.state == "UNKNOWN_INTEGRITY_HOLD":
                classification = "INTEGRITY_HOLD"
            elif terminal.state == "CLOSED":
                if (
                    claim_state != "CLAIMED"
                    or terminal.evidence_count != authority.expected_rows
                    or terminal.row_count != authority.expected_rows
                    or outcome == "START_REJECTED"
                ):
                    raise WarehouseW3TerminalAcceptanceError(
                        "closed terminal predecessor facts differ"
                    )
                if units_terminal:
                    lineage = load_invocation_lineage(terminal_root, policy)
                    final = acquire_run_final()
                    if (
                        final.handoff.invocation_id != lineage.invocation_id
                        or final.handoff.result != "success"
                        or not _closer_succeeded(close)
                    ):
                        raise WarehouseW3TerminalAcceptanceError(
                            "closed W3 unit pair did not succeed"
                        )
                    artifacts, replay_sha = _successful_artifacts(
                        chain,
                        terminal_root,
                    )
                    verify_live_w3_environment(installed, phase="completion")
                    verify_live_w3_projection(installed)
                    classification = "CLOSED_ACCEPTED"
            elif terminal.state == "INCOMPLETE":
                if claim_state != "CLAIMED":
                    raise WarehouseW3TerminalAcceptanceError(
                        "incomplete terminal lacks exact nonce claim"
                    )
                if outcome == "START_REJECTED":
                    raise WarehouseW3TerminalAcceptanceError(
                        "incomplete terminal contradicts rejected dispatch"
                    )
                if units_terminal:
                    acquire_run_final()
                    verify_live_w3_environment(installed, phase="completion")
                    verify_live_w3_projection(installed)
                    classification = "INCOMPLETE_PRESERVED"
            elif terminal.state == "ABSENT" and claim_state == "ABSENT":
                if outcome == "START_REJECTED":
                    if not (
                        _prestart_unit_is_absent(run)
                        and _prestart_unit_is_absent(close)
                    ):
                        raise WarehouseW3TerminalAcceptanceError(
                            "rejected dispatch changed the W3 unit pair"
                        )
                    classification = "START_DISPATCH_REJECTED"
                elif units_terminal:
                    acquire_run_final()
                    if (
                        run.get("Result") == "exit-code"
                        and run.get("ExecMainCode") == 1
                        and run.get("ExecMainStatus") in _PRECLAIM_STATUSES
                    ):
                        classification = _PRECLAIM_STATUSES[int(run["ExecMainStatus"])]
                    else:
                        classification = "PRECLAIM_TERMINATION_UNKNOWN"
            if classification in _TERMINAL_CLASSIFICATIONS:
                _terminal_cgroup_absent(chain, installation.run_unit)

            configured = _acquire_w3_configured_readback(
                reader,
                installation,
                run_template_raw=(
                    installed.bundle.installed_replay_inputs.run_template_raw
                ),
                close_template_raw=(
                    installed.bundle.installed_replay_inputs.close_template_raw
                ),
            )
            if configured != chain.configured_pair_readback:
                raise WarehouseW3TerminalAcceptanceError(
                    "terminal configured-pair readback differs"
                )
            manager_after = Systemd255Acquirer(reader).acquire_manager_identity()
            if manager_after != manager:
                raise WarehouseW3TerminalAcceptanceError(
                    "systemd manager identity changed during terminal inspection"
                )
            installed.revalidate()
            start.revalidate()
            value = {
                "schema": "scion.w3-terminal-report.v1",
                "launch_id": normalized,
                "authority_sha256": authority.authority_sha256,
                "installation_sha256": installation.installation_sha256,
                "installed_acceptance_sha256": (chain.installed_acceptance.raw_sha256),
                "start_issue_sha256": start.gate.issue_sha256,
                "start_outcome": outcome,
                "start_outcome_sha256": outcome_sha,
                "manager": {
                    "unique_owner": manager.unique_owner,
                    "boot_id": manager.boot_id,
                    "version": manager.version,
                },
                "run_properties": run,
                "close_properties": close,
                "nonce_claim_state": claim_state,
                "nonce_claim_sha256": claim_sha,
                "terminal_state": terminal.state,
                "evidence_count": terminal.evidence_count,
                "row_count": terminal.row_count,
                "classification": classification,
                "artifacts": list(artifacts),
                "replay_receipt_sha256": replay_sha,
                "retry": False,
                "resume": False,
                "reuse": False,
            }
            return WarehouseW3TerminalReport.from_bytes(_canonical_json(value))


def inspect_w3_terminal(launch_id: str) -> WarehouseW3TerminalReport:
    """Reacquire one canonical manager-pinned terminal-chain report."""

    normalized = _launch_id(launch_id)
    with RootInstalledAcceptanceAuthority.acquire(normalized) as installed:
        installation = (
            installed.chain.selected_candidate.root_staging_verification.installation
        )
        with _pinned_unit_reader(
            installation.run_unit,
            installation.close_unit,
        ) as reader:
            return _inspect_w3_terminal_pinned(
                normalized,
                installed,
                reader,
            )


@dataclass(frozen=True, slots=True, init=False)
class WarehouseW3TerminalAcceptance:
    launch_id: str
    report_sha256: str
    classification: str
    installed_acceptance_sha256: str
    start_issue_sha256: str
    raw: bytes
    raw_sha256: str

    def __new__(cls) -> "WarehouseW3TerminalAcceptance":
        del cls
        raise TypeError("WarehouseW3TerminalAcceptance must be parsed from exact bytes")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("WarehouseW3TerminalAcceptance is final")

    @classmethod
    def from_bytes(cls, raw: bytes) -> "WarehouseW3TerminalAcceptance":
        value = _decode(raw, label="Warehouse W3 terminal acceptance")
        if (
            frozenset(value)
            != {
                "schema",
                "launch_id",
                "report_sha256",
                "classification",
                "installed_acceptance_sha256",
                "start_issue_sha256",
                "retry",
                "resume",
                "reuse",
            }
            or value["schema"] != "scion.w3-terminal-acceptance.v1"
            or value["retry"] is not False
            or value["resume"] is not False
            or value["reuse"] is not False
            or value["classification"] not in _TERMINAL_CLASSIFICATIONS
        ):
            raise WarehouseW3TerminalAcceptanceError(
                "Warehouse W3 terminal acceptance fields differ"
            )
        instance = object.__new__(cls)
        for name, item in (
            ("launch_id", _launch_id(value["launch_id"])),
            (
                "report_sha256",
                _sha(value["report_sha256"], field="report_sha256"),
            ),
            ("classification", value["classification"]),
            (
                "installed_acceptance_sha256",
                _sha(
                    value["installed_acceptance_sha256"],
                    field="installed_acceptance_sha256",
                ),
            ),
            (
                "start_issue_sha256",
                _sha(value["start_issue_sha256"], field="start_issue_sha256"),
            ),
            ("raw", raw),
            ("raw_sha256", hashlib.sha256(raw).hexdigest()),
        ):
            object.__setattr__(instance, name, item)
        return instance


def accept_w3_terminal(launch_id: str) -> WarehouseW3TerminalAcceptance:
    """Persist one independently reacquired root-owned terminal classification."""

    if os.geteuid() != 0:
        raise PermissionError("W3 terminal acceptance requires effective UID zero")
    normalized = _launch_id(launch_id)
    report = inspect_w3_terminal(normalized)
    if report.classification not in _TERMINAL_CLASSIFICATIONS:
        raise WarehouseW3TerminalAcceptanceError(
            "W3 terminal report is not acceptably terminal"
        )
    terminal_root = _LAUNCH_ROOT / normalized / "terminal"
    with DurableReceiptDirectory(terminal_root) as writer:
        writer.write_no_replace(_REPORT_LEAF, report.raw)
        reopened_report = WarehouseW3TerminalReport.from_bytes(
            writer.read(_REPORT_LEAF)
        )
        live = inspect_w3_terminal(normalized)
        if live != reopened_report:
            raise WarehouseW3TerminalAcceptanceError(
                "live terminal facts changed after report publication"
            )
        acceptance = WarehouseW3TerminalAcceptance.from_bytes(
            _canonical_json(
                {
                    "schema": "scion.w3-terminal-acceptance.v1",
                    "launch_id": normalized,
                    "report_sha256": reopened_report.raw_sha256,
                    "classification": reopened_report.classification,
                    "installed_acceptance_sha256": (
                        reopened_report.installed_acceptance_sha256
                    ),
                    "start_issue_sha256": reopened_report.start_issue_sha256,
                    "retry": False,
                    "resume": False,
                    "reuse": False,
                }
            )
        )
        writer.write_no_replace(_ACCEPTANCE_LEAF, acceptance.raw)
        reopened = WarehouseW3TerminalAcceptance.from_bytes(
            writer.read(_ACCEPTANCE_LEAF)
        )
        if reopened != acceptance:
            raise WarehouseW3TerminalAcceptanceError(
                "root terminal acceptance differs after reopen"
            )
    descriptor = os.open(
        terminal_root,
        os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW,
    )
    try:
        os.fchmod(descriptor, 0o555)
        os.fsync(descriptor)
        metadata = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    if (
        stat.S_IMODE(metadata.st_mode) != 0o555
        or metadata.st_uid != 0
        or metadata.st_gid != 0
    ):
        raise WarehouseW3TerminalAcceptanceError(
            "root terminal acceptance directory did not seal"
        )
    return acceptance


__all__ = [
    "WarehouseW3TerminalAcceptance",
    "WarehouseW3TerminalAcceptanceError",
    "WarehouseW3TerminalReport",
    "accept_w3_terminal",
    "inspect_w3_terminal",
]
