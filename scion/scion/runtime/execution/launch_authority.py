"""Problem-neutral external launch authority, installation, and nonce owners."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Mapping

from .systemd_acquisition import (
    ConfiguredPairFact,
    SystemdAcquisitionError,
)

_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_GIT_OID_RE = re.compile(r"[0-9a-f]{40}\Z")
_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_UNIT_RE = re.compile(r"[A-Za-z0-9:_.@-]+\.service\Z")
_AUTHORITY_SCHEMA = "scion.generic-launch-authority.v1"
_INSTALLATION_SCHEMA = "scion.generic-launch-installation.v1"
_CLAIM_SCHEMA = "scion.generic-invocation-claim.v1"


class LaunchAuthorityError(RuntimeError):
    """An external authority, installation, or nonce claim is invalid."""


def _reject_nonfinite(item: str) -> object:
    raise LaunchAuthorityError(f"nonfinite JSON value: {item}")


def _reject_duplicate_keys(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise LaunchAuthorityError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


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
        raise LaunchAuthorityError("value is not canonical JSON data") from exc


def _decode_canonical(raw: bytes, *, label: str) -> dict[str, object]:
    if type(raw) is not bytes:
        raise TypeError(f"{label} must be exact bytes")
    try:
        value = json.loads(
            raw,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_nonfinite,
        )
    except LaunchAuthorityError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LaunchAuthorityError(f"{label} is invalid JSON") from exc
    if type(value) is not dict or _canonical_json(value) != raw:
        raise LaunchAuthorityError(f"{label} is not one canonical mapping")
    return value


def _exact_keys(
    value: Mapping[str, object],
    expected: frozenset[str],
    *,
    label: str,
) -> None:
    if frozenset(value) != expected:
        raise LaunchAuthorityError(f"{label} fields differ")


def _text(value: object, *, field: str) -> str:
    if type(value) is not str or not value or "\x00" in value:
        raise LaunchAuthorityError(f"{field} must be nonempty exact text")
    return value


def _sha256(value: object, *, field: str) -> str:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        raise LaunchAuthorityError(
            f"{field} must be 64 lowercase hexadecimal characters"
        )
    return value


def _git_oid(value: object, *, field: str) -> str:
    if type(value) is not str or _GIT_OID_RE.fullmatch(value) is None:
        raise LaunchAuthorityError(
            f"{field} must be 40 lowercase hexadecimal characters"
        )
    return value


def _uint(value: object, *, field: str, positive: bool = False) -> int:
    minimum = 1 if positive else 0
    if type(value) is not int or value < minimum or value > (1 << 64) - 1:
        raise LaunchAuthorityError(f"{field} must be an integer in [{minimum}, 2^64-1]")
    return value


def _token(value: object, *, field: str) -> str:
    text = _text(value, field=field)
    if _TOKEN_RE.fullmatch(text) is None or text in {".", ".."}:
        raise LaunchAuthorityError(f"{field} is not a canonical token")
    return text


def _unit(value: object, *, field: str) -> str:
    text = _text(value, field=field)
    if _UNIT_RE.fullmatch(text) is None:
        raise LaunchAuthorityError(f"{field} is not a canonical service unit")
    return text


def _relative_path(value: object, *, field: str) -> str:
    text = _text(value, field=field)
    path = PurePosixPath(text)
    if (
        path.is_absolute()
        or path.as_posix() != text
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise LaunchAuthorityError(f"{field} is not a canonical relative path")
    return text


def _absolute_path(value: object, *, field: str) -> str:
    text = _text(value, field=field)
    path = PurePosixPath(text)
    if (
        not path.is_absolute()
        or path.as_posix() != text
        or text == "/"
        or any(part in {"", ".", ".."} for part in path.parts[1:])
    ):
        raise LaunchAuthorityError(f"{field} is not a canonical absolute path")
    return text


def _false_controls(value: Mapping[str, object], *, label: str) -> None:
    if any(value.get(name) is not False for name in ("retry", "resume", "reuse")):
        raise LaunchAuthorityError(f"{label} enables retry, resume, or reuse")


@dataclass(frozen=True, slots=True)
class AuthorityInput:
    logical_path: str
    sealed_path: str
    sha256: str
    size_bytes: int
    provenance_kind: str
    provenance: tuple[tuple[str, object], ...]

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("AuthorityInput is final")

    @classmethod
    def from_mapping(
        cls,
        value: object,
        *,
        source_commit: str,
    ) -> "AuthorityInput":
        if type(value) is not dict:
            raise LaunchAuthorityError("authority input is not a mapping")
        _exact_keys(
            value,
            frozenset(
                {
                    "logical_path",
                    "sealed_path",
                    "sha256",
                    "size_bytes",
                    "provenance",
                }
            ),
            label="authority input",
        )
        logical_path = _relative_path(value["logical_path"], field="input.logical_path")
        sealed_path = _relative_path(value["sealed_path"], field="input.sealed_path")
        if not sealed_path.startswith("sealed/"):
            raise LaunchAuthorityError("input.sealed_path must be below sealed/")
        digest = _sha256(value["sha256"], field="input.sha256")
        size = _uint(value["size_bytes"], field="input.size_bytes")
        raw_provenance = value["provenance"]
        if type(raw_provenance) is not dict:
            raise LaunchAuthorityError("input.provenance is not a mapping")
        kind = raw_provenance.get("kind")
        if kind == "git_blob":
            _exact_keys(
                raw_provenance,
                frozenset({"kind", "commit", "path", "blob_oid"}),
                label="git_blob provenance",
            )
            if (
                _git_oid(raw_provenance["commit"], field="provenance.commit")
                != source_commit
            ):
                raise LaunchAuthorityError(
                    "git_blob provenance commit differs from authority"
                )
            if (
                _relative_path(raw_provenance["path"], field="provenance.path")
                != logical_path
            ):
                raise LaunchAuthorityError(
                    "git_blob provenance path differs from logical_path"
                )
            _git_oid(raw_provenance["blob_oid"], field="provenance.blob_oid")
        elif kind == "external_evidence":
            _exact_keys(
                raw_provenance,
                frozenset({"kind", "source_path", "device", "inode"}),
                label="external_evidence provenance",
            )
            _absolute_path(
                raw_provenance["source_path"],
                field="provenance.source_path",
            )
            _uint(
                raw_provenance["device"],
                field="provenance.device",
                positive=True,
            )
            _uint(
                raw_provenance["inode"],
                field="provenance.inode",
                positive=True,
            )
        elif kind == "generated":
            _exact_keys(
                raw_provenance,
                frozenset(
                    {
                        "kind",
                        "generator_sha256",
                        "input_sha256",
                        "rule_sha256",
                    }
                ),
                label="generated provenance",
            )
            _sha256(
                raw_provenance["generator_sha256"],
                field="provenance.generator_sha256",
            )
            inputs = raw_provenance["input_sha256"]
            if type(inputs) is not list or not inputs:
                raise LaunchAuthorityError(
                    "generated provenance input_sha256 is not a nonempty array"
                )
            for item in inputs:
                _sha256(item, field="provenance.input_sha256")
            _sha256(
                raw_provenance["rule_sha256"],
                field="provenance.rule_sha256",
            )
        else:
            raise LaunchAuthorityError("unknown authority provenance kind")
        frozen = tuple(
            (
                key,
                (
                    tuple(raw_provenance[key])
                    if type(raw_provenance[key]) is list
                    else raw_provenance[key]
                ),
            )
            for key in sorted(raw_provenance)
        )
        return cls(
            logical_path=logical_path,
            sealed_path=sealed_path,
            sha256=digest,
            size_bytes=size,
            provenance_kind=kind,
            provenance=frozen,
        )

    def to_mapping(self) -> dict[str, object]:
        provenance = {
            key: list(value) if type(value) is tuple else value
            for key, value in self.provenance
        }
        return {
            "logical_path": self.logical_path,
            "sealed_path": self.sealed_path,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "provenance": provenance,
        }


@dataclass(frozen=True, slots=True)
class AcceptedLaunchAuthority:
    problem_kind: str
    source_commit: str
    source_tree: str
    manifest_path: str
    manifest_sha256: str
    manifest_size_bytes: int
    root_basename: str
    nonce: str
    nonce_ledger_parent: str
    expected_rows: int
    artifact_names: tuple[str, ...]
    scientific_design_sha256: str
    correction_design_sha256: str
    native_acceptance_contract_sha256: str
    native_acceptance_record_sha256: str
    sealed_store_aggregate_sha256: str
    environment_receipt_sha256: str
    run_template_sha256: str
    close_template_sha256: str
    guardian_source_sha256: str
    thin_tool_source_sha256: str
    closer_source_sha256: str
    inputs: tuple[AuthorityInput, ...]
    authority_sha256: str
    raw: bytes

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("AcceptedLaunchAuthority is final")

    @classmethod
    def from_bytes(cls, raw: bytes) -> "AcceptedLaunchAuthority":
        value = _decode_canonical(raw, label="launch authority")
        _exact_keys(
            value,
            frozenset(
                {
                    "schema",
                    "problem_kind",
                    "source_commit",
                    "source_tree",
                    "manifest",
                    "root_basename",
                    "nonce",
                    "nonce_ledger_parent",
                    "expected_rows",
                    "artifact_names",
                    "scientific_design_sha256",
                    "correction_design_sha256",
                    "native_acceptance_contract_sha256",
                    "native_acceptance_record_sha256",
                    "sealed_store_aggregate_sha256",
                    "environment_receipt_sha256",
                    "run_template_sha256",
                    "close_template_sha256",
                    "guardian_source_sha256",
                    "thin_tool_source_sha256",
                    "closer_source_sha256",
                    "inputs",
                    "retry",
                    "resume",
                    "reuse",
                }
            ),
            label="launch authority",
        )
        if value["schema"] != _AUTHORITY_SCHEMA:
            raise LaunchAuthorityError("launch authority schema differs")
        _false_controls(value, label="launch authority")
        problem_kind = _token(value["problem_kind"], field="authority.problem_kind")
        source_commit = _git_oid(
            value["source_commit"], field="authority.source_commit"
        )
        source_tree = _git_oid(value["source_tree"], field="authority.source_tree")
        manifest = value["manifest"]
        if type(manifest) is not dict:
            raise LaunchAuthorityError("authority.manifest is not a mapping")
        _exact_keys(
            manifest,
            frozenset({"path", "sha256", "size_bytes"}),
            label="authority.manifest",
        )
        manifest_path = _relative_path(
            manifest["path"], field="authority.manifest.path"
        )
        manifest_sha256 = _sha256(manifest["sha256"], field="authority.manifest.sha256")
        manifest_size = _uint(
            manifest["size_bytes"],
            field="authority.manifest.size_bytes",
            positive=True,
        )
        root_basename = _token(value["root_basename"], field="authority.root_basename")
        nonce = _sha256(value["nonce"], field="authority.nonce")
        ledger = _absolute_path(
            value["nonce_ledger_parent"],
            field="authority.nonce_ledger_parent",
        )
        expected_rows = _uint(
            value["expected_rows"],
            field="authority.expected_rows",
            positive=True,
        )
        raw_names = value["artifact_names"]
        if type(raw_names) is not list or not raw_names:
            raise LaunchAuthorityError(
                "authority.artifact_names is not a nonempty array"
            )
        artifact_names = tuple(
            _token(item, field="authority.artifact_names") for item in raw_names
        )
        if len(set(artifact_names)) != len(artifact_names):
            raise LaunchAuthorityError("authority.artifact_names contains a duplicate")
        raw_inputs = value["inputs"]
        if type(raw_inputs) is not list or not raw_inputs:
            raise LaunchAuthorityError("authority.inputs is not a nonempty array")
        inputs = tuple(
            AuthorityInput.from_mapping(item, source_commit=source_commit)
            for item in raw_inputs
        )
        sealed_paths = tuple(item.sealed_path for item in inputs)
        if sealed_paths != tuple(
            sorted(sealed_paths, key=lambda item: item.encode("utf-8"))
        ):
            raise LaunchAuthorityError("authority.inputs is not sorted by sealed_path")
        if len(set(sealed_paths)) != len(sealed_paths) or len(
            {item.logical_path for item in inputs}
        ) != len(inputs):
            raise LaunchAuthorityError("authority.inputs contains a duplicate path")
        manifest_matches = [
            item
            for item in inputs
            if item.logical_path == manifest_path
            and item.sha256 == manifest_sha256
            and item.size_bytes == manifest_size
        ]
        if len(manifest_matches) != 1:
            raise LaunchAuthorityError("authority manifest is not one exact input")
        return cls(
            problem_kind=problem_kind,
            source_commit=source_commit,
            source_tree=source_tree,
            manifest_path=manifest_path,
            manifest_sha256=manifest_sha256,
            manifest_size_bytes=manifest_size,
            root_basename=root_basename,
            nonce=nonce,
            nonce_ledger_parent=ledger,
            expected_rows=expected_rows,
            artifact_names=artifact_names,
            scientific_design_sha256=_sha256(
                value["scientific_design_sha256"],
                field="authority.scientific_design_sha256",
            ),
            correction_design_sha256=_sha256(
                value["correction_design_sha256"],
                field="authority.correction_design_sha256",
            ),
            native_acceptance_contract_sha256=_sha256(
                value["native_acceptance_contract_sha256"],
                field="authority.native_acceptance_contract_sha256",
            ),
            native_acceptance_record_sha256=_sha256(
                value["native_acceptance_record_sha256"],
                field="authority.native_acceptance_record_sha256",
            ),
            sealed_store_aggregate_sha256=_sha256(
                value["sealed_store_aggregate_sha256"],
                field="authority.sealed_store_aggregate_sha256",
            ),
            environment_receipt_sha256=_sha256(
                value["environment_receipt_sha256"],
                field="authority.environment_receipt_sha256",
            ),
            run_template_sha256=_sha256(
                value["run_template_sha256"],
                field="authority.run_template_sha256",
            ),
            close_template_sha256=_sha256(
                value["close_template_sha256"],
                field="authority.close_template_sha256",
            ),
            guardian_source_sha256=_sha256(
                value["guardian_source_sha256"],
                field="authority.guardian_source_sha256",
            ),
            thin_tool_source_sha256=_sha256(
                value["thin_tool_source_sha256"],
                field="authority.thin_tool_source_sha256",
            ),
            closer_source_sha256=_sha256(
                value["closer_source_sha256"],
                field="authority.closer_source_sha256",
            ),
            inputs=inputs,
            authority_sha256=hashlib.sha256(raw).hexdigest(),
            raw=raw,
        )


@dataclass(frozen=True, slots=True)
class InstallationRecord:
    launch_id: str
    authority_sha256: str
    authority_path: str
    manifest_sha256: str
    run_root: str
    terminal_root: str
    nonce: str
    nonce_ledger_parent: str
    sealed_root: str
    sealed_store_aggregate_sha256: str
    environment_root: str
    environment_receipt_sha256: str
    projection_root: str
    run_template_sha256: str
    close_template_sha256: str
    run_unit: str
    close_unit: str
    configured_pair: ConfiguredPairFact
    configured_pair_sha256: str
    installation_sha256: str
    raw: bytes

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("InstallationRecord is final")

    @classmethod
    def from_bytes(
        cls,
        raw: bytes,
        authority: AcceptedLaunchAuthority,
    ) -> "InstallationRecord":
        if type(authority) is not AcceptedLaunchAuthority:
            raise TypeError("authority must be exact AcceptedLaunchAuthority")
        value = _decode_canonical(raw, label="installation record")
        _exact_keys(
            value,
            frozenset(
                {
                    "schema",
                    "launch_id",
                    "authority_sha256",
                    "authority_path",
                    "problem_kind",
                    "manifest_sha256",
                    "run_root",
                    "terminal_root",
                    "nonce",
                    "nonce_ledger_parent",
                    "sealed_root",
                    "sealed_store_aggregate_sha256",
                    "environment_root",
                    "environment_receipt_sha256",
                    "projection_root",
                    "run_template_sha256",
                    "close_template_sha256",
                    "run_unit",
                    "close_unit",
                    "configured_pair",
                    "configured_pair_sha256",
                    "retry",
                    "resume",
                    "reuse",
                }
            ),
            label="installation record",
        )
        if value["schema"] != _INSTALLATION_SCHEMA:
            raise LaunchAuthorityError("installation schema differs")
        _false_controls(value, label="installation record")
        launch_id = _sha256(value["launch_id"], field="installation.launch_id")
        authority_sha256 = _sha256(
            value["authority_sha256"],
            field="installation.authority_sha256",
        )
        authority_path = _absolute_path(
            value["authority_path"],
            field="installation.authority_path",
        )
        run_root = _absolute_path(value["run_root"], field="installation.run_root")
        terminal_root = _absolute_path(
            value["terminal_root"], field="installation.terminal_root"
        )
        projection_root = _absolute_path(
            value["projection_root"],
            field="installation.projection_root",
        )
        if PurePosixPath(authority_path).name != f"{authority_sha256}.json":
            raise LaunchAuthorityError(
                "installation authority path is not digest-derived"
            )
        if PurePosixPath(run_root).name != authority.root_basename:
            raise LaunchAuthorityError(
                "installation run root basename differs from authority"
            )
        if terminal_root != f"{run_root}/control/invocation":
            raise LaunchAuthorityError(
                "installation terminal root is not mechanically derived"
            )
        if PurePosixPath(projection_root).name != launch_id:
            raise LaunchAuthorityError(
                "installation projection root is not launch-id-derived"
            )
        cross_bindings = (
            (
                value["problem_kind"],
                authority.problem_kind,
                "problem_kind",
            ),
            (
                authority_sha256,
                authority.authority_sha256,
                "authority_sha256",
            ),
            (
                value["manifest_sha256"],
                authority.manifest_sha256,
                "manifest_sha256",
            ),
            (value["nonce"], authority.nonce, "nonce"),
            (
                value["nonce_ledger_parent"],
                authority.nonce_ledger_parent,
                "nonce_ledger_parent",
            ),
            (
                value["sealed_store_aggregate_sha256"],
                authority.sealed_store_aggregate_sha256,
                "sealed_store_aggregate_sha256",
            ),
            (
                value["environment_receipt_sha256"],
                authority.environment_receipt_sha256,
                "environment_receipt_sha256",
            ),
            (
                value["run_template_sha256"],
                authority.run_template_sha256,
                "run_template_sha256",
            ),
            (
                value["close_template_sha256"],
                authority.close_template_sha256,
                "close_template_sha256",
            ),
        )
        for actual, expected, field in cross_bindings:
            if actual != expected:
                raise LaunchAuthorityError(
                    f"installation {field} differs from authority"
                )
        nonce_ledger_parent = _absolute_path(
            value["nonce_ledger_parent"],
            field="installation.nonce_ledger_parent",
        )
        sealed_root = _absolute_path(
            value["sealed_root"], field="installation.sealed_root"
        )
        environment_root = _absolute_path(
            value["environment_root"],
            field="installation.environment_root",
        )
        directory_paths = (
            run_root,
            terminal_root,
            nonce_ledger_parent,
            sealed_root,
            environment_root,
            projection_root,
        )
        if len(set(directory_paths)) != len(directory_paths):
            raise LaunchAuthorityError(
                "installation directory identities are not distinct"
            )
        try:
            configured_pair = ConfiguredPairFact.from_mapping(value["configured_pair"])
        except SystemdAcquisitionError as exc:
            raise LaunchAuthorityError("installation configured pair differs") from exc
        configured_pair_sha256 = _sha256(
            value["configured_pair_sha256"],
            field="installation.configured_pair_sha256",
        )
        if configured_pair.configured_pair_sha256 != configured_pair_sha256:
            raise LaunchAuthorityError("installation configured pair digest differs")
        return cls(
            launch_id=launch_id,
            authority_sha256=authority_sha256,
            authority_path=authority_path,
            manifest_sha256=authority.manifest_sha256,
            run_root=run_root,
            terminal_root=terminal_root,
            nonce=authority.nonce,
            nonce_ledger_parent=nonce_ledger_parent,
            sealed_root=sealed_root,
            sealed_store_aggregate_sha256=authority.sealed_store_aggregate_sha256,
            environment_root=environment_root,
            environment_receipt_sha256=authority.environment_receipt_sha256,
            projection_root=projection_root,
            run_template_sha256=authority.run_template_sha256,
            close_template_sha256=authority.close_template_sha256,
            run_unit=_unit(value["run_unit"], field="installation.run_unit"),
            close_unit=_unit(value["close_unit"], field="installation.close_unit"),
            configured_pair=configured_pair,
            configured_pair_sha256=configured_pair_sha256,
            installation_sha256=hashlib.sha256(raw).hexdigest(),
            raw=raw,
        )

    @property
    def projected_run_root(self) -> str:
        return f"{self.projection_root}/run"

    @property
    def projected_terminal_root(self) -> str:
        return f"{self.projected_run_root}/control/invocation"

    @property
    def projected_sealed_root(self) -> str:
        return f"{self.projection_root}/sealed"

    @property
    def projected_environment_root(self) -> str:
        return f"{self.projection_root}/environment"

    @property
    def projected_nonce_ledger_parent(self) -> str:
        return f"{self.projection_root}/nonce-claims"


@dataclass(frozen=True, slots=True)
class NonceClaimFact:
    authority_sha256: str
    installation_sha256: str
    launch_id: str
    manifest_sha256: str
    run_root: str
    terminal_root: str
    nonce: str
    claim_sha256: str
    raw: bytes

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("NonceClaimFact is final")

    @classmethod
    def create(
        cls,
        authority: AcceptedLaunchAuthority,
        installation: InstallationRecord,
    ) -> "NonceClaimFact":
        if type(authority) is not AcceptedLaunchAuthority:
            raise TypeError("authority must be exact AcceptedLaunchAuthority")
        if type(installation) is not InstallationRecord:
            raise TypeError("installation must be exact InstallationRecord")
        if installation.authority_sha256 != authority.authority_sha256:
            raise LaunchAuthorityError("installation does not bind the authority")
        value = {
            "schema": _CLAIM_SCHEMA,
            "authority_sha256": authority.authority_sha256,
            "installation_sha256": installation.installation_sha256,
            "launch_id": installation.launch_id,
            "manifest_sha256": authority.manifest_sha256,
            "run_root": installation.run_root,
            "terminal_root": installation.terminal_root,
            "nonce": authority.nonce,
            "retry": False,
            "resume": False,
            "reuse": False,
        }
        raw = _canonical_json(value)
        return cls(
            authority_sha256=authority.authority_sha256,
            installation_sha256=installation.installation_sha256,
            launch_id=installation.launch_id,
            manifest_sha256=authority.manifest_sha256,
            run_root=installation.run_root,
            terminal_root=installation.terminal_root,
            nonce=authority.nonce,
            claim_sha256=hashlib.sha256(raw).hexdigest(),
            raw=raw,
        )


def _open_directory(path: Path) -> int:
    absolute = Path(os.path.abspath(path))
    if absolute == Path(absolute.anchor):
        raise LaunchAuthorityError("filesystem root cannot be a claim directory")
    flags = (
        os.O_RDONLY
        | os.O_DIRECTORY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        descriptor = os.open(absolute.anchor, flags)
    except OSError as exc:
        raise LaunchAuthorityError(
            f"cannot open claim directory anchor {absolute.anchor}"
        ) from exc
    try:
        for component in absolute.parts[1:]:
            next_descriptor = os.open(component, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_descriptor
        result = descriptor
        descriptor = -1
        return result
    except OSError as exc:
        raise LaunchAuthorityError(
            f"cannot open claim directory component in {absolute}"
        ) from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _write_all(descriptor: int, raw: bytes) -> None:
    view = memoryview(raw)
    while view:
        written = os.write(descriptor, view)
        if written <= 0:
            raise OSError("short nonce-claim write")
        view = view[written:]


def _publish_exclusive(
    directory_fd: int,
    name: str,
    raw: bytes,
) -> None:
    descriptor = os.open(
        name,
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0),
        0o600,
        dir_fd=directory_fd,
    )
    try:
        _write_all(descriptor, raw)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    os.fsync(directory_fd)


def _read_claim(directory_fd: int, name: str) -> bytes:
    descriptor = os.open(
        name,
        os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0),
        dir_fd=directory_fd,
    )
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise LaunchAuthorityError("nonce claim is not a regular file")
        chunks = []
        while True:
            chunk = os.read(descriptor, 64 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(descriptor)
        try:
            named = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        except OSError as exc:
            raise LaunchAuthorityError("nonce claim name changed while read") from exc
    finally:
        os.close(descriptor)
    if (
        (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
        or (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
        )
        != (
            named.st_dev,
            named.st_ino,
            named.st_size,
            named.st_mtime_ns,
        )
        or sum(len(item) for item in chunks) != after.st_size
    ):
        raise LaunchAuthorityError("nonce claim changed while read")
    return b"".join(chunks)


class NonceClaimOwner:
    """One-process, one-use external-first nonce publication owner."""

    __slots__ = (
        "_authority",
        "_installation",
        "_creator_pid",
        "_state",
    )

    def __init__(
        self,
        authority: AcceptedLaunchAuthority,
        installation: InstallationRecord,
    ) -> None:
        if type(authority) is not AcceptedLaunchAuthority:
            raise TypeError("authority must be exact AcceptedLaunchAuthority")
        if type(installation) is not InstallationRecord:
            raise TypeError("installation must be exact InstallationRecord")
        if installation.authority_sha256 != authority.authority_sha256:
            raise LaunchAuthorityError("installation does not bind the authority")
        self._authority = authority
        self._installation = installation
        self._creator_pid = os.getpid()
        self._state = "OPEN"

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("NonceClaimOwner is final")

    @property
    def expected_claim(self) -> NonceClaimFact:
        if os.getpid() != self._creator_pid or self._state != "OPEN":
            raise LaunchAuthorityError("nonce claim owner is not open")
        return NonceClaimFact.create(self._authority, self._installation)

    def claim(self) -> NonceClaimFact:
        claim = self.expected_claim
        self._state = "CONSUMED"
        ledger_fd = _open_directory(
            Path(self._installation.projected_nonce_ledger_parent)
        )
        try:
            try:
                _publish_exclusive(
                    ledger_fd,
                    f"{self._authority.nonce}.claim.json",
                    claim.raw,
                )
            except OSError as exc:
                raise LaunchAuthorityError("external nonce publication failed") from exc
        finally:
            os.close(ledger_fd)
        control_fd = _open_directory(
            Path(self._installation.projected_terminal_root) / "control"
        )
        try:
            try:
                _publish_exclusive(
                    control_fd,
                    "invocation_claimed.v1.json",
                    claim.raw,
                )
            except OSError as exc:
                raise LaunchAuthorityError(
                    "invocation nonce publication failed"
                ) from exc
        finally:
            os.close(control_fd)
        return claim

    def __copy__(self) -> object:
        raise TypeError("NonceClaimOwner is not copyable")

    def __deepcopy__(self, _memo: object) -> object:
        raise TypeError("NonceClaimOwner is not copyable")

    def __reduce__(self) -> object:
        raise TypeError("NonceClaimOwner is not serializable")

    def __reduce_ex__(self, _protocol: object) -> object:
        raise TypeError("NonceClaimOwner is not serializable")


def inspect_nonce_claim(
    authority: AcceptedLaunchAuthority,
    installation: InstallationRecord,
) -> NonceClaimFact:
    """Require byte-identical external and invocation claims."""

    expected = NonceClaimFact.create(authority, installation)
    ledger_fd = _open_directory(Path(installation.projected_nonce_ledger_parent))
    control_fd = _open_directory(Path(installation.projected_terminal_root) / "control")
    try:
        external = _read_claim(ledger_fd, f"{authority.nonce}.claim.json")
        invocation = _read_claim(control_fd, "invocation_claimed.v1.json")
    finally:
        os.close(control_fd)
        os.close(ledger_fd)
    if external != expected.raw or invocation != expected.raw:
        raise LaunchAuthorityError("nonce claim bytes differ")
    return expected


__all__ = [
    "AcceptedLaunchAuthority",
    "AuthorityInput",
    "InstallationRecord",
    "LaunchAuthorityError",
    "NonceClaimFact",
    "NonceClaimOwner",
    "inspect_nonce_claim",
]
