"""Warehouse-owned W3 composition over the generic execution authorities."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from scion.problems.warehouse_delivery.w3_analysis import replay_artifacts
from scion.problems.warehouse_delivery.w3_fixed_arm import (
    WarehouseW3Error,
    inventory_regular_tree,
    process_spec_for_job,
    read_regular,
    render_json,
)
from scion.problems.warehouse_delivery.w3_validation import (
    validate_closed_observation,
)
from scion.runtime.execution.cgroup_v2 import ServiceCgroup
from scion.runtime.execution.invocation_terminal import (
    InvocationWriter,
    TerminalPolicy,
    accept_invocation,
    load_invocation_lineage,
    observe_unit_final,
    prepare_terminal_root,
    publish_opaque_artifact_bundle,
    seal_unit_drained,
)
from scion.runtime.execution.launch_authority import (
    AcceptedLaunchAuthority,
    InstallationRecord,
    LaunchAuthorityError,
    NonceClaimFact,
    NonceClaimOwner,
    inspect_nonce_claim,
)
from scion.runtime.execution.model import (
    BackendOpenFailure,
    ContainedSpawnFailure,
    JobCgroupKey,
    PreHandleFailure,
)
from scion.runtime.execution.spawn_backend import (
    SettledJob,
    SpawnBackend,
)
from scion.runtime.execution.systemd255 import (
    ConfiguredUnitProperties,
    UnitRole,
)
from scion.runtime.execution.systemd_acquisition import (
    ConfiguredPairFact,
    Systemd255Acquirer,
    SystemdAcquisitionError,
    SystemdDbusPropertyReader,
    UnitTemplate,
    parse_unit_template,
)

EXPECTED_SOURCE_COMMIT = "b879bbc1e73550234c863e829ddaecd877f6876e"
EXPECTED_MANIFEST_NAME = "warehouse_w3_fixed_arm_manifest.v1.json"
EXPECTED_MANIFEST_SHA256 = (
    "ad69364623cd817cc74be968528823b7bd08bf3ddef4f019476f769332ea0212"
)
EXPECTED_ROWS = 172
EXPECTED_SOURCE_TREE_IDENTITY_SHA256 = (
    "2a51526eb2771710922c519dd5972c91072b0adbe4215731177f4f906f277f15"
)
EXPECTED_ARTIFACT_NAMES = (
    "warehouse_w3_fixed_arm_results.v1.json",
    "warehouse_w3_fixed_arm_report.v1.md",
    "warehouse_w3_fixed_arm_receipt.v1.json",
)
EXPECTED_NONCE_LEDGER_PARENT = "/var/lib/scion/runs/w3/.nonce-ledger/claims"
EXPECTED_SCIENTIFIC_DESIGN_SHA256 = (
    "5538a81b6d7980888cf594b07244a0b4863c57db85f3a04beb8f84555ad4bb35"
)
EXPECTED_CORRECTION_DESIGN_SHA256 = (
    "8e2a610eeec15ca1bb118d7affa855b753b320be1ae055b2e517613731d10945"
)
EXPECTED_NATIVE_ACCEPTANCE_CONTRACT_SHA256 = (
    "afaa0b7e60b820e168d1300ecdf8a0f2085e5dad7461e7f7bbc1edbf88524f27"
)
EXPECTED_NATIVE_ACCEPTANCE_RECORD_SHA256 = (
    "51948ccda6b9a24811c05e4fd3795ddefcf1b62ac2e1604297e70ede91700de7"
)
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")

_RUN_READ_ONLY = (
    "/var/lib/scion/projections/w3/%i/installation.json "
    "/var/lib/scion/projections/w3/%i/authority.json "
    "/var/lib/scion/projections/w3/%i/sealed "
    "/var/lib/scion/projections/w3/%i/environment"
)
_RUN_READ_WRITE = (
    "/var/lib/scion/projections/w3/%i/run "
    "/var/lib/scion/projections/w3/%i/nonce-claims"
)
_RUN_EXEC = (
    "/var/lib/scion/projections/w3/%i/environment/bin/python -I -B "
    "/var/lib/scion/projections/w3/%i/sealed/bin/scion-w3-tool run %i"
)
_STOP_EXEC = (
    "/var/lib/scion/projections/w3/%i/environment/bin/python -I -B "
    "/var/lib/scion/projections/w3/%i/sealed/bin/scion-w3-tool "
    "seal-unit-drained %i"
)
_CLOSE_EXEC = (
    "/var/lib/scion/projections/w3/%i/environment/bin/python -I -B "
    "/var/lib/scion/projections/w3/%i/sealed/bin/scion-w3-tool close %i"
)
_RUN_UNIT_SECTION = {
    "Description": "Scion Warehouse W3 fixed-arm run %i",
    "OnSuccess": "scion-w3-close@%i.service",
    "OnFailure": "scion-w3-close@%i.service",
    "CollectMode": "inactive",
}
_RUN_SERVICE_SECTION = {
    "Type": "exec",
    "User": "clawd",
    "Group": "clawd",
    "UMask": "0077",
    "ExecStart": _RUN_EXEC,
    "ExecStopPost": _STOP_EXEC,
    "Restart": "no",
    "ExitType": "main",
    "KillMode": "control-group",
    "SendSIGKILL": "yes",
    "TimeoutStopSec": "infinity",
    "OOMPolicy": "stop",
    "Delegate": "pids",
    "DelegateSubgroup": "supervisor",
    "NoNewPrivileges": "yes",
    "PrivateTmp": "yes",
    "PrivateMounts": "yes",
    "ProtectSystem": "strict",
    "ProtectHome": "read-only",
    "ProtectControlGroups": "no",
    "ProtectProc": "invisible",
    "ProcSubset": "all",
    "ReadOnlyPaths": _RUN_READ_ONLY,
    "ReadWritePaths": _RUN_READ_WRITE,
}
_CLOSE_UNIT_SECTION = {
    "Description": "Scion Warehouse W3 fixed-arm close %i",
    "After": "scion-w3@%i.service",
    "CollectMode": "inactive",
}
_CLOSE_SERVICE_SECTION = {
    "Type": "oneshot",
    "User": "clawd",
    "Group": "clawd",
    "UMask": "0077",
    "ExecStart": _CLOSE_EXEC,
    "Restart": "no",
    "TimeoutStartSec": "infinity",
    "NoNewPrivileges": "yes",
    "PrivateTmp": "yes",
    "ProtectSystem": "strict",
    "ProtectHome": "read-only",
    "ReadOnlyPaths": _RUN_READ_ONLY,
    "ReadWritePaths": _RUN_READ_WRITE,
}


class WarehouseW3CompositionError(RuntimeError):
    """The W3 authority, installation, or fixed composition is invalid."""


@dataclass(frozen=True, slots=True)
class _InstalledMaterials:
    authority: AcceptedLaunchAuthority
    installation: InstallationRecord
    run_template: UnitTemplate
    close_template: UnitTemplate
    run_template_raw: bytes
    close_template_raw: bytes
    terminal_policy: TerminalPolicy


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json(value: object) -> bytes:
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


def _source_hashes() -> tuple[str, str, str]:
    composition = Path(__file__).read_bytes()
    tool = Path(__file__).resolve().parents[2] / "tools" / "scion_w3_tool.py"
    tool_bytes = tool.read_bytes()
    composition_sha256 = _sha256(composition)
    return (
        composition_sha256,
        _sha256(tool_bytes),
        composition_sha256,
    )


def _required_launch_inputs() -> dict[str, str]:
    package_root = Path(__file__).resolve().parents[2]
    project_root = package_root.parent
    paths = (
        package_root / "problems" / "warehouse_delivery" / "w2_preservation.py",
        package_root / "problems" / "warehouse_delivery" / "w3_counter_fixtures.py",
        package_root / "problems" / "warehouse_delivery" / "w3_composition.py",
        package_root / "problems" / "warehouse_delivery" / "w3_candidate_gate.py",
        package_root / "problems" / "warehouse_delivery" / "w3_candidate_ingress.py",
        package_root
        / "problems"
        / "warehouse_delivery"
        / "w3_candidate_coordinator.py",
        package_root / "problems" / "warehouse_delivery" / "w3_environment.py",
        package_root / "problems" / "warehouse_delivery" / "w3_environment_receipts.py",
        package_root / "problems" / "warehouse_delivery" / "w3_installation.py",
        package_root / "problems" / "warehouse_delivery" / "w3_installed_replay.py",
        package_root / "problems" / "warehouse_delivery" / "w3_prestart_facts.py",
        package_root / "problems" / "warehouse_delivery" / "w3_root_coordinator.py",
        package_root / "problems" / "warehouse_delivery" / "w3_root_installation.py",
        package_root / "problems" / "warehouse_delivery" / "w3_root_selection.py",
        package_root / "problems" / "warehouse_delivery" / "w3_root_staging.py",
        package_root / "problems" / "warehouse_delivery" / "w3_start_authorization.py",
        package_root / "problems" / "warehouse_delivery" / "w3_start_gate.py",
        package_root / "problems" / "warehouse_delivery" / "w3_start_store.py",
        package_root / "problems" / "warehouse_delivery" / "w3_terminal_acceptance.py",
        package_root / "problems" / "warehouse_delivery" / "w3_terminal_manager.py",
        package_root / "problems" / "warehouse_delivery" / "w3_wheel.py",
        package_root / "tools" / "scion_w3_tool.py",
        package_root / "tools" / "scion_w3_install.py",
        package_root
        / "problems"
        / "warehouse_delivery"
        / "systemd"
        / "scion-w3@.service",
        package_root
        / "problems"
        / "warehouse_delivery"
        / "systemd"
        / "scion-w3-close@.service",
        package_root / "runtime" / "execution" / "launch_authority.py",
        package_root / "runtime" / "execution" / "systemd_acquisition.py",
        package_root / "runtime" / "execution" / "invocation_terminal.py",
        package_root / "runtime" / "execution" / "spawn_backend.py",
        package_root / "runtime" / "execution" / "cgroup_v2.py",
        package_root / "runtime" / "execution" / "environment_integrity.py",
        package_root / "runtime" / "execution" / "external_installation.py",
        package_root / "runtime" / "execution" / "external_linux.py",
        package_root / "runtime" / "execution" / "systemd255.py",
        package_root / "runtime" / "execution" / "model.py",
        package_root / "problems" / "warehouse_delivery" / "w3_fixed_arm.py",
        package_root / "problems" / "warehouse_delivery" / "w3_validation.py",
        package_root / "problems" / "warehouse_delivery" / "w3_analysis.py",
    )
    return {
        str(path.relative_to(project_root)): _sha256(path.read_bytes())
        for path in paths
    }


def _require_launch_inputs(
    authority: AcceptedLaunchAuthority,
) -> None:
    declared = {item.logical_path: item.sha256 for item in authority.inputs}
    required = _required_launch_inputs()
    if any(declared.get(path) != digest for path, digest in required.items()):
        raise WarehouseW3CompositionError("launch source input closure differs")


def _tree_identity(root: Path) -> str:
    entries: list[dict[str, object]] = []
    for path in sorted(
        root.rglob("*"),
        key=lambda item: str(item.relative_to(root)).encode("utf-8"),
    ):
        relative = str(path.relative_to(root))
        metadata = path.lstat()
        if stat.S_ISLNK(metadata.st_mode):
            raise WarehouseW3CompositionError(
                f"source root contains a symlink: {relative}"
            )
        if stat.S_ISDIR(metadata.st_mode):
            entries.append(
                {
                    "path": relative,
                    "kind": "directory",
                    "mode": stat.S_IMODE(metadata.st_mode),
                }
            )
        elif stat.S_ISREG(metadata.st_mode):
            snapshot = read_regular(path)
            entries.append(
                {
                    "path": relative,
                    "kind": "file",
                    "mode": stat.S_IMODE(metadata.st_mode),
                    "sha256": snapshot.sha256,
                    "size_bytes": snapshot.size_bytes,
                }
            )
        else:
            raise WarehouseW3CompositionError(
                f"source root contains a special file: {relative}"
            )
    return _sha256(b"scion.warehouse-w3-source-tree.v1\x00" + _canonical_json(entries))


def _verify_accepted_dry_root_static(
    root: Path,
    manifest: Mapping[str, object],
    manifest_sha256: str,
) -> dict[str, object]:
    if (
        render_json(manifest) != (root / EXPECTED_MANIFEST_NAME).read_bytes()
        or manifest_sha256 != EXPECTED_MANIFEST_SHA256
        or manifest.get("schema") != "scion.warehouse_w3_fixed_arm_manifest.v1"
        or manifest.get("formal_jobs_started") != 0
        or manifest.get("formal_execution_authorized") is not False
        or len(manifest.get("cells", ())) != 43
        or len(manifest.get("jobs", ())) != EXPECTED_ROWS
        or manifest.get("output_root")
        != {
            "path": str(root),
            "absent_before_creation": True,
            "parent_device": os.stat(root.parent).st_dev,
        }
    ):
        raise WarehouseW3CompositionError("accepted dry-root manifest contract differs")
    source = manifest.get("source")
    if (
        type(source) is not dict
        or source.get("source_commit") != EXPECTED_SOURCE_COMMIT
        or source.get("formal_jobs_started") != 0
    ):
        raise WarehouseW3CompositionError("accepted dry-root source receipt differs")
    sidecar = read_regular(root / "warehouse_w3_fixed_arm_manifest.v1.sha256").data
    marker = read_regular(root / "PREPARED_NO_FORMAL_JOBS").data
    if (
        sidecar != f"{EXPECTED_MANIFEST_SHA256}\n".encode("ascii")
        or marker != b"W3 dry manifest accepted; formal solver jobs started: 0\n"
    ):
        raise WarehouseW3CompositionError("accepted dry-root sidecar or marker differs")
    base = manifest.get("prepared_closure_inventory")
    if type(base) is not dict:
        raise WarehouseW3CompositionError("accepted prepared inventory is absent")
    expected = {
        "directories": list(base["directories"]),
        "files": sorted(
            [
                *base["files"],
                "PREPARED_NO_FORMAL_JOBS",
                EXPECTED_MANIFEST_NAME,
                "warehouse_w3_fixed_arm_manifest.v1.sha256",
            ],
            key=lambda value: value.encode("utf-8"),
        ),
    }
    if inventory_regular_tree(root) != expected:
        raise WarehouseW3CompositionError("accepted dry-root inventory differs")
    return {
        "passed": True,
        "manifest_sha256": EXPECTED_MANIFEST_SHA256,
        "source_commit": EXPECTED_SOURCE_COMMIT,
        "cell_count": 43,
        "job_count": EXPECTED_ROWS,
        "formal_jobs_started": 0,
        "formal_execution_authorized": False,
        "filesystem_mutated": False,
    }


def _require_template(
    template: UnitTemplate,
    *,
    unit_section: Mapping[str, str],
    service_section: Mapping[str, str],
    label: str,
) -> None:
    if tuple(section.name for section in template.sections) != (
        "Unit",
        "Service",
    ):
        raise WarehouseW3CompositionError(f"{label} template section inventory differs")
    if dict(template.section("Unit")) != dict(unit_section) or dict(
        template.section("Service")
    ) != dict(service_section):
        raise WarehouseW3CompositionError(f"{label} template semantic wiring differs")


def _expanded(value: str, launch_id: str) -> str:
    return value.replace("%i", launch_id)


def configured_pair_for_installation(
    launch_id: str,
    run_template: UnitTemplate,
    close_template: UnitTemplate,
) -> ConfiguredPairFact:
    """Derive the one installation-bound configured pair from exact templates."""

    if _SHA256_RE.fullmatch(launch_id) is None:
        raise WarehouseW3CompositionError("launch id is not one SHA-256 value")
    if (
        type(run_template) is not UnitTemplate
        or type(close_template) is not UnitTemplate
    ):
        raise TypeError("run_template and close_template must be exact UnitTemplate")
    _require_template(
        run_template,
        unit_section=_RUN_UNIT_SECTION,
        service_section=_RUN_SERVICE_SECTION,
        label="run",
    )
    _require_template(
        close_template,
        unit_section=_CLOSE_UNIT_SECTION,
        service_section=_CLOSE_SERVICE_SECTION,
        label="closer",
    )
    run_unit = f"scion-w3@{launch_id}.service"
    close_unit = f"scion-w3-close@{launch_id}.service"
    run = ConfiguredUnitProperties.from_receipts(
        UnitRole.RUN,
        {
            "Delegate": "pids",
            "DelegateSubgroup": "supervisor",
            "CollectMode": "inactive",
            "Restart": "no",
            "KillMode": "control-group",
            "TimeoutStopSec": "infinity",
            "OnSuccess": close_unit,
            "OnFailure": close_unit,
        },
        {
            "Id": run_unit,
            "Delegate": "yes",
            "DelegateControllers": "pids",
            "DelegateSubgroup": "supervisor",
            "CollectMode": "inactive",
            "Restart": "no",
            "KillMode": "control-group",
            "TimeoutStopUSec": "infinity",
            "OnSuccess": close_unit,
            "OnFailure": close_unit,
        },
        expected_unit=run_unit,
        expected_peer=close_unit,
    )
    closer = ConfiguredUnitProperties.from_receipts(
        UnitRole.CLOSER,
        {
            "CollectMode": "inactive",
            "Restart": "no",
            "TimeoutStartSec": "infinity",
            "After": run_unit,
        },
        {
            "Id": close_unit,
            "CollectMode": "inactive",
            "Restart": "no",
            "TimeoutStartUSec": "infinity",
            "After": run_unit,
        },
        expected_unit=close_unit,
        expected_peer=run_unit,
    )
    return ConfiguredPairFact.create(run, closer)


def _require_configured_pair(
    pair: ConfiguredPairFact,
    installation: InstallationRecord,
) -> None:
    if type(pair) is not ConfiguredPairFact:
        raise TypeError("pair must be exact ConfiguredPairFact")
    run_unit = f"scion-w3@{installation.launch_id}.service"
    close_unit = f"scion-w3-close@{installation.launch_id}.service"
    expected_run = tuple(
        sorted(
            {
                "CollectMode": "inactive",
                "Delegate": "pids",
                "DelegateSubgroup": "supervisor",
                "KillMode": "control-group",
                "OnFailure": close_unit,
                "OnSuccess": close_unit,
                "Restart": "no",
                "TimeoutStopSec": "infinity",
            }.items()
        )
    )
    expected_close = tuple(
        sorted(
            {
                "After": run_unit,
                "CollectMode": "inactive",
                "Restart": "no",
                "TimeoutStartSec": "infinity",
            }.items()
        )
    )
    if (
        pair.run.unit != run_unit
        or pair.run.peer_unit != close_unit
        or pair.closer.unit != close_unit
        or pair.closer.peer_unit != run_unit
        or pair.run.configured_directives != expected_run
        or pair.closer.configured_directives != expected_close
        or pair.configured_pair_sha256 != installation.configured_pair_sha256
        or pair != installation.configured_pair
    ):
        raise WarehouseW3CompositionError(
            "configured property pair differs from templates or installation"
        )


def _lstat_or_none(path: Path) -> os.stat_result | None:
    try:
        return os.lstat(path)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise WarehouseW3CompositionError(
            f"cannot inspect external installation path {path}"
        ) from exc


def _require_absent(path: Path, *, label: str) -> None:
    if _lstat_or_none(path) is not None:
        raise WarehouseW3CompositionError(f"{label} is already present")


def _same_directory(left: Path, right: Path) -> bool:
    left_stat = os.stat(left, follow_symlinks=False)
    right_stat = os.stat(right, follow_symlinks=False)
    return (
        stat.S_ISDIR(left_stat.st_mode)
        and stat.S_ISDIR(right_stat.st_mode)
        and (left_stat.st_dev, left_stat.st_ino)
        == (right_stat.st_dev, right_stat.st_ino)
    )


def _read_exact_regular(path: Path, expected: bytes) -> None:
    metadata = os.lstat(path)
    if not stat.S_ISREG(metadata.st_mode) or path.read_bytes() != expected:
        raise WarehouseW3CompositionError(f"installed immutable file differs: {path}")


def _external_installation_ready(
    authority: AcceptedLaunchAuthority,
    installation: InstallationRecord,
) -> bool:
    installation_path = Path(
        f"/var/lib/scion/installations/w3/{installation.launch_id}.json"
    )
    authority_path = Path(installation.authority_path)
    projection = Path(installation.projection_root)
    candidates = (installation_path, authority_path, projection)
    present = tuple(_lstat_or_none(path) is not None for path in candidates)
    if not any(present):
        return False
    if not all(present):
        raise WarehouseW3CompositionError("external installation is partial")
    try:
        _read_exact_regular(installation_path, installation.raw)
        _read_exact_regular(authority_path, authority.raw)
        if tuple(sorted(path.name for path in projection.iterdir())) != (
            "authority.json",
            "environment",
            "installation.json",
            "nonce-claims",
            "run",
            "sealed",
        ):
            raise WarehouseW3CompositionError("projection inventory differs")
        _read_exact_regular(
            projection / "installation.json",
            installation.raw,
        )
        _read_exact_regular(
            projection / "authority.json",
            authority.raw,
        )
        pairs = (
            (projection / "run", Path(installation.run_root)),
            (projection / "sealed", Path(installation.sealed_root)),
            (
                projection / "environment",
                Path(installation.environment_root),
            ),
            (
                projection / "nonce-claims",
                Path(installation.nonce_ledger_parent),
            ),
        )
        if any(not _same_directory(left, right) for left, right in pairs):
            raise WarehouseW3CompositionError("projection bind identity differs")
    except OSError as exc:
        raise WarehouseW3CompositionError(
            "external installation cannot be verified"
        ) from exc
    return True


@dataclass(frozen=True, slots=True)
class WarehouseW3LaunchReadyFact:
    state: str
    authority: AcceptedLaunchAuthority
    installation: InstallationRecord
    run_template: UnitTemplate
    close_template: UnitTemplate
    terminal_policy: TerminalPolicy
    source_tree_identity_sha256: str
    external_installation_required: bool
    formal_execution_authorized: bool
    filesystem_mutated: bool
    _authority_raw: bytes
    _installation_raw: bytes
    _run_template_raw: bytes
    _close_template_raw: bytes
    _live_configured_pair: ConfiguredPairFact | None

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("WarehouseW3LaunchReadyFact is final")


def inspect_w3_launch_readiness(
    accepted_root: Path,
    authority_raw: bytes,
    installation_raw: bytes,
    run_template_raw: bytes,
    close_template_raw: bytes,
    *,
    live_configured_pair: ConfiguredPairFact | None = None,
) -> WarehouseW3LaunchReadyFact:
    """Reverify the accepted dry root and composition without mutation."""

    root = Path(os.path.abspath(accepted_root))
    try:
        if root.resolve(strict=True) != root:
            raise WarehouseW3CompositionError(
                "accepted root is not one direct canonical path"
            )
        before = _tree_identity(root)
        manifest_snapshot = read_regular(root / EXPECTED_MANIFEST_NAME)
        manifest = json.loads(manifest_snapshot.data)
        if type(manifest) is not dict:
            raise WarehouseW3CompositionError("accepted manifest is not a mapping")
        dry = _verify_accepted_dry_root_static(
            root,
            manifest,
            manifest_snapshot.sha256,
        )
        after = _tree_identity(root)
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        WarehouseW3Error,
    ) as exc:
        raise WarehouseW3CompositionError(
            "accepted W3 dry root does not reverify"
        ) from exc
    if before != after:
        raise WarehouseW3CompositionError("dry-root verification mutated source bytes")
    if before != EXPECTED_SOURCE_TREE_IDENTITY_SHA256:
        raise WarehouseW3CompositionError("accepted source-tree identity differs")
    try:
        authority = AcceptedLaunchAuthority.from_bytes(authority_raw)
        installation = InstallationRecord.from_bytes(
            installation_raw,
            authority,
        )
        run_template = parse_unit_template(run_template_raw)
        close_template = parse_unit_template(close_template_raw)
    except (
        LaunchAuthorityError,
        SystemdAcquisitionError,
    ) as exc:
        raise WarehouseW3CompositionError(
            "authority, installation, or template decoding failed"
        ) from exc
    guardian_sha, tool_sha, closer_sha = _source_hashes()
    if (
        dry
        != {
            "passed": True,
            "manifest_sha256": EXPECTED_MANIFEST_SHA256,
            "source_commit": EXPECTED_SOURCE_COMMIT,
            "cell_count": 43,
            "job_count": EXPECTED_ROWS,
            "formal_jobs_started": 0,
            "formal_execution_authorized": False,
            "filesystem_mutated": False,
        }
        or manifest_snapshot.sha256 != EXPECTED_MANIFEST_SHA256
        or authority.problem_kind != "warehouse-w3"
        or authority.manifest_path != EXPECTED_MANIFEST_NAME
        or authority.manifest_sha256 != EXPECTED_MANIFEST_SHA256
        or authority.manifest_size_bytes != manifest_snapshot.size_bytes
        or authority.root_basename != root.name
        or authority.nonce_ledger_parent != EXPECTED_NONCE_LEDGER_PARENT
        or authority.expected_rows != EXPECTED_ROWS
        or authority.artifact_names != EXPECTED_ARTIFACT_NAMES
        or authority.scientific_design_sha256 != EXPECTED_SCIENTIFIC_DESIGN_SHA256
        or authority.correction_design_sha256 != EXPECTED_CORRECTION_DESIGN_SHA256
        or authority.native_acceptance_contract_sha256
        != EXPECTED_NATIVE_ACCEPTANCE_CONTRACT_SHA256
        or authority.native_acceptance_record_sha256
        != EXPECTED_NATIVE_ACCEPTANCE_RECORD_SHA256
        or authority.run_template_sha256 != run_template.raw_sha256
        or authority.close_template_sha256 != close_template.raw_sha256
        or authority.guardian_source_sha256 != guardian_sha
        or authority.thin_tool_source_sha256 != tool_sha
        or authority.closer_source_sha256 != closer_sha
        or installation.run_root != str(root)
        or installation.nonce_ledger_parent != EXPECTED_NONCE_LEDGER_PARENT
        or installation.authority_path
        != f"/var/lib/scion/authorities/w3/{authority.authority_sha256}.json"
        or installation.sealed_root
        != f"/var/lib/scion/sealed/w3/{EXPECTED_MANIFEST_SHA256}"
        or installation.projection_root
        != f"/var/lib/scion/projections/w3/{installation.launch_id}"
        or installation.run_unit != f"scion-w3@{installation.launch_id}.service"
        or installation.close_unit != f"scion-w3-close@{installation.launch_id}.service"
    ):
        raise WarehouseW3CompositionError(
            "W3 authority or installation identity differs"
        )
    _require_launch_inputs(authority)
    _require_template(
        run_template,
        unit_section=_RUN_UNIT_SECTION,
        service_section=_RUN_SERVICE_SECTION,
        label="run",
    )
    _require_template(
        close_template,
        unit_section=_CLOSE_UNIT_SECTION,
        service_section=_CLOSE_SERVICE_SECTION,
        label="closer",
    )
    _require_configured_pair(
        installation.configured_pair,
        installation,
    )
    if live_configured_pair is not None:
        _require_configured_pair(live_configured_pair, installation)
    claim = NonceClaimFact.create(authority, installation)
    policy = TerminalPolicy(
        authority_sha256=authority.authority_sha256,
        manifest_sha256=authority.manifest_sha256,
        invocation_nonce=authority.nonce,
        expected_rows=authority.expected_rows,
        artifact_names=authority.artifact_names,
        nonce_claim_sha256=claim.claim_sha256,
    )
    _require_absent(
        Path(installation.nonce_ledger_parent) / f"{authority.nonce}.claim.json",
        label="external nonce claim",
    )
    _require_absent(
        Path(installation.terminal_root),
        label="source terminal root",
    )
    _require_absent(
        Path(installation.projected_terminal_root),
        label="projected terminal root",
    )
    installed = _external_installation_ready(authority, installation)
    external_required = not installed or live_configured_pair is None
    return WarehouseW3LaunchReadyFact(
        state=(
            "COMPOSITION_READY_EXTERNAL_INSTALLATION_REQUIRED"
            if external_required
            else "LAUNCH_READY"
        ),
        authority=authority,
        installation=installation,
        run_template=run_template,
        close_template=close_template,
        terminal_policy=policy,
        source_tree_identity_sha256=before,
        external_installation_required=external_required,
        formal_execution_authorized=False,
        filesystem_mutated=False,
        _authority_raw=authority_raw,
        _installation_raw=installation_raw,
        _run_template_raw=run_template_raw,
        _close_template_raw=close_template_raw,
        _live_configured_pair=live_configured_pair,
    )


def prepare_w3_invocation(
    readiness: WarehouseW3LaunchReadyFact,
) -> InvocationWriter:
    """Claim one externally installed launch and publish generic STARTED."""

    if type(readiness) is not WarehouseW3LaunchReadyFact:
        raise TypeError("readiness must be exact WarehouseW3LaunchReadyFact")
    if (
        readiness.external_installation_required
        or readiness.state != "LAUNCH_READY"
        or readiness._live_configured_pair is None
    ):
        raise WarehouseW3CompositionError(
            "external installation acceptance is still required"
        )
    refreshed = inspect_w3_launch_readiness(
        Path(readiness.installation.run_root),
        readiness._authority_raw,
        readiness._installation_raw,
        readiness._run_template_raw,
        readiness._close_template_raw,
        live_configured_pair=readiness._live_configured_pair,
    )
    if refreshed != readiness:
        raise WarehouseW3CompositionError("launch readiness changed before claim")
    terminal_root = Path(readiness.installation.projected_terminal_root)
    prepare_terminal_root(terminal_root)
    claim = NonceClaimOwner(
        readiness.authority,
        readiness.installation,
    ).claim()
    if claim.claim_sha256 != readiness.terminal_policy.nonce_claim_sha256:
        raise WarehouseW3CompositionError(
            "published nonce claim differs from terminal policy"
        )
    return InvocationWriter.open_claimed(
        terminal_root,
        readiness.terminal_policy,
    )


def _sealed_input_bytes(
    authority: AcceptedLaunchAuthority,
    installation: InstallationRecord,
    logical_path: str,
) -> bytes:
    matches = [item for item in authority.inputs if item.logical_path == logical_path]
    if len(matches) != 1:
        raise WarehouseW3CompositionError(
            f"installed authority lacks one exact {logical_path}"
        )
    item = matches[0]
    snapshot = read_regular(
        Path(installation.projected_sealed_root) / item.sealed_path,
        expected_sha256=item.sha256,
    )
    if snapshot.size_bytes != item.size_bytes:
        raise WarehouseW3CompositionError(
            f"installed sealed input size differs: {logical_path}"
        )
    return snapshot.data


def _installed_materials(
    launch_id: str,
    *,
    require_claim: bool,
) -> _InstalledMaterials:
    projection = Path("/var/lib/scion/projections/w3") / launch_id
    try:
        authority_raw = read_regular(projection / "authority.json").data
        authority = AcceptedLaunchAuthority.from_bytes(authority_raw)
        installation_raw = read_regular(projection / "installation.json").data
        installation = InstallationRecord.from_bytes(
            installation_raw,
            authority,
        )
        if (
            installation.launch_id != launch_id
            or installation.projection_root != str(projection)
            or not _external_installation_ready(
                authority,
                installation,
            )
        ):
            raise WarehouseW3CompositionError("external installation identity differs")
        run_template_raw = _sealed_input_bytes(
            authority,
            installation,
            ("scion/problems/warehouse_delivery/systemd/" "scion-w3@.service"),
        )
        close_template_raw = _sealed_input_bytes(
            authority,
            installation,
            ("scion/problems/warehouse_delivery/systemd/" "scion-w3-close@.service"),
        )
        run_template = parse_unit_template(run_template_raw)
        close_template = parse_unit_template(close_template_raw)
    except (
        OSError,
        WarehouseW3Error,
        LaunchAuthorityError,
        SystemdAcquisitionError,
    ) as exc:
        raise WarehouseW3CompositionError(
            "external root-owned installation acceptance is required"
        ) from exc
    guardian_sha, tool_sha, closer_sha = _source_hashes()
    if (
        authority.problem_kind != "warehouse-w3"
        or authority.manifest_sha256 != EXPECTED_MANIFEST_SHA256
        or authority.expected_rows != EXPECTED_ROWS
        or authority.artifact_names != EXPECTED_ARTIFACT_NAMES
        or authority.scientific_design_sha256 != EXPECTED_SCIENTIFIC_DESIGN_SHA256
        or authority.correction_design_sha256 != EXPECTED_CORRECTION_DESIGN_SHA256
        or authority.native_acceptance_contract_sha256
        != EXPECTED_NATIVE_ACCEPTANCE_CONTRACT_SHA256
        or authority.native_acceptance_record_sha256
        != EXPECTED_NATIVE_ACCEPTANCE_RECORD_SHA256
        or authority.nonce_ledger_parent != EXPECTED_NONCE_LEDGER_PARENT
        or authority.run_template_sha256 != run_template.raw_sha256
        or authority.close_template_sha256 != close_template.raw_sha256
        or authority.guardian_source_sha256 != guardian_sha
        or authority.thin_tool_source_sha256 != tool_sha
        or authority.closer_source_sha256 != closer_sha
    ):
        raise WarehouseW3CompositionError("installed authority identity differs")
    _require_launch_inputs(authority)
    _require_template(
        run_template,
        unit_section=_RUN_UNIT_SECTION,
        service_section=_RUN_SERVICE_SECTION,
        label="run",
    )
    _require_template(
        close_template,
        unit_section=_CLOSE_UNIT_SECTION,
        service_section=_CLOSE_SERVICE_SECTION,
        label="closer",
    )
    _require_configured_pair(
        installation.configured_pair,
        installation,
    )
    claim = NonceClaimFact.create(authority, installation)
    policy = TerminalPolicy(
        authority_sha256=authority.authority_sha256,
        manifest_sha256=authority.manifest_sha256,
        invocation_nonce=authority.nonce,
        expected_rows=authority.expected_rows,
        artifact_names=authority.artifact_names,
        nonce_claim_sha256=claim.claim_sha256,
    )
    if require_claim:
        try:
            actual_claim = inspect_nonce_claim(
                authority,
                installation,
            )
        except (OSError, LaunchAuthorityError) as exc:
            raise WarehouseW3CompositionError(
                "installed invocation claim is absent or invalid"
            ) from exc
        if actual_claim != claim:
            raise WarehouseW3CompositionError("installed invocation claim differs")
    return _InstalledMaterials(
        authority=authority,
        installation=installation,
        run_template=run_template,
        close_template=close_template,
        run_template_raw=run_template_raw,
        close_template_raw=close_template_raw,
        terminal_policy=policy,
    )


def _live_configured_pair(
    materials: _InstalledMaterials,
    acquirer: Systemd255Acquirer,
) -> ConfiguredPairFact:
    launch_id = materials.installation.launch_id
    run_unit = dict(materials.run_template.section("Unit"))
    run_service = dict(materials.run_template.section("Service"))
    close_unit = dict(materials.close_template.section("Unit"))
    close_service = dict(materials.close_template.section("Service"))
    run_directives = {
        key: _expanded(
            (run_unit[key] if key in run_unit else run_service[key]),
            launch_id,
        )
        for key in (
            "Delegate",
            "DelegateSubgroup",
            "CollectMode",
            "Restart",
            "KillMode",
            "TimeoutStopSec",
            "OnSuccess",
            "OnFailure",
        )
    }
    close_directives = {
        key: _expanded(
            (close_unit[key] if key in close_unit else close_service[key]),
            launch_id,
        )
        for key in (
            "CollectMode",
            "Restart",
            "TimeoutStartSec",
            "After",
        )
    }
    run_wiring = {
        key: _expanded(run_service[key], launch_id)
        for key in (
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
    }
    close_wiring = {
        key: _expanded(close_service[key], launch_id)
        for key in (
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
    }
    pair = acquirer.acquire_configured_pair(
        run_unit=materials.installation.run_unit,
        close_unit=materials.installation.close_unit,
        run_directives=run_directives,
        close_directives=close_directives,
        run_wiring=run_wiring,
        close_wiring=close_wiring,
    )
    _require_configured_pair(pair, materials.installation)
    return pair


def _systemd_environment(*names: str) -> dict[str, str]:
    values = {}
    for name in names:
        value = os.environ.get(name)
        if value is None:
            raise WarehouseW3CompositionError(f"systemd environment lacks {name}")
        values[name] = value
    return values


def _open_capture_directory(root: Path) -> int:
    flags = (
        os.O_RDONLY
        | os.O_DIRECTORY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        descriptor = os.open(root, flags)
        metadata = os.fstat(descriptor)
        if not stat.S_ISDIR(metadata.st_mode):
            raise WarehouseW3CompositionError("capture path is not a directory")
        return descriptor
    except Exception:
        if "descriptor" in locals():
            os.close(descriptor)
        raise


def _mark_run_incomplete(
    writer: InvocationWriter,
    backend: SpawnBackend | None,
    reason_code: str,
) -> None:
    writer.mark_incomplete(reason_code)
    if backend is not None:
        state = backend.state
        if state == "IDLE":
            backend.close_idle()
        elif state not in {"CLOSED", "POISONED_CLOSED"}:
            raise WarehouseW3CompositionError(
                "spawn backend is not terminal after failure"
            )


def _require_live_issued_start_gate(
    materials: _InstalledMaterials,
    acquirer: Systemd255Acquirer,
    lineage: object,
) -> object:
    """Consume the fixed root-owned issued gate before any nonce publication."""

    # Local import avoids a module cycle: the W3 receipt replay modules use the
    # fixed composition constants as their problem-owned inventory authority.
    from .w3_start_gate import (
        WarehouseW3EnvironmentIntegrityRefused,
        WarehouseW3InstalledIdentityRefused,
        WarehouseW3StartPermitRefused,
        WarehouseW3SystemdLineageRefused,
    )
    from .w3_start_store import acquire_w3_issued_start_gate

    try:
        manager = acquirer.acquire_manager_identity()
    except Exception as exc:
        raise WarehouseW3SystemdLineageRefused(
            "live systemd manager identity cannot be acquired"
        ) from exc
    try:
        context = acquire_w3_issued_start_gate(
            expected_launch_id=materials.installation.launch_id,
            expected_authority_sha256=materials.authority.authority_sha256,
            expected_installation_sha256=(materials.installation.installation_sha256),
            expected_unit=materials.installation.run_unit,
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
            "fixed root-owned issued start identity differs"
        ) from exc
    try:
        gate = context.gate
    except AttributeError as exc:
        raise WarehouseW3InstalledIdentityRefused(
            "fixed root-owned start context differs"
        ) from exc
    try:
        lineage_boot_id = lineage.boot_id
    except AttributeError as exc:
        raise WarehouseW3SystemdLineageRefused(
            "installed invocation lineage lacks a boot identity"
        ) from exc
    if (
        gate.manager_unique_owner != manager.unique_owner
        or gate.boot_id != manager.boot_id
        or gate.manager_version != manager.version
        or gate.boot_id != lineage_boot_id
    ):
        raise WarehouseW3SystemdLineageRefused(
            "issued start gate differs from the live systemd manager"
        )
    return context


def _revalidate_live_start_context(
    start_context: object,
    acquirer: Systemd255Acquirer,
    lineage: object,
) -> None:
    """Recheck manager and environment immediately before nonce publication."""

    from .w3_start_gate import (
        WarehouseW3EnvironmentIntegrityRefused,
        WarehouseW3InstalledIdentityRefused,
        WarehouseW3SystemdLineageRefused,
    )

    try:
        gate = start_context.gate
        current = acquirer.acquire_manager_identity()
        lineage_boot_id = lineage.boot_id
    except WarehouseW3EnvironmentIntegrityRefused:
        raise
    except Exception as exc:
        raise WarehouseW3SystemdLineageRefused(
            "live systemd manager identity cannot be reacquired"
        ) from exc
    if (
        current.unique_owner != gate.manager_unique_owner
        or current.boot_id != gate.boot_id
        or current.version != gate.manager_version
        or current.boot_id != lineage_boot_id
    ):
        raise WarehouseW3SystemdLineageRefused(
            "systemd manager identity changed before nonce claim"
        )
    try:
        start_context.verify_environment("preclaim")
    except WarehouseW3EnvironmentIntegrityRefused:
        raise
    except Exception as exc:
        raise WarehouseW3InstalledIdentityRefused(
            "installed start context cannot revalidate the environment"
        ) from exc


def _complete_installed_run(
    writer: InvocationWriter,
    backend: SpawnBackend,
    start_context: object,
) -> None:
    """Commit raw completion only after the final environment rehash."""

    try:
        start_context.verify_environment("completion")
    except Exception as exc:
        _mark_run_incomplete(
            writer,
            backend,
            "ENVIRONMENT_COMPLETION_REFUSED",
        )
        raise WarehouseW3CompositionError(
            "completion environment integrity differs"
        ) from exc
    writer.finish_raw()
    backend.close_idle()


def _run_installed(materials: _InstalledMaterials) -> None:
    from .w3_start_gate import (
        WarehouseW3InstalledIdentityRefused,
        WarehouseW3SystemdLineageRefused,
    )

    reader = SystemdDbusPropertyReader()
    acquirer = Systemd255Acquirer(reader)
    try:
        live_pair = _live_configured_pair(materials, acquirer)
    except Exception as exc:
        raise WarehouseW3InstalledIdentityRefused(
            "live configured unit pair differs"
        ) from exc
    try:
        invocation_id = _systemd_environment("INVOCATION_ID")["INVOCATION_ID"]
        lineage = acquirer.acquire_self_lineage(
            expected_unit=materials.installation.run_unit,
            expected_invocation_id=invocation_id,
        )
    except Exception as exc:
        raise WarehouseW3SystemdLineageRefused(
            "installed invocation lineage differs"
        ) from exc
    start_context = _require_live_issued_start_gate(
        materials,
        acquirer,
        lineage,
    )
    try:
        readiness = inspect_w3_launch_readiness(
            Path(materials.installation.run_root),
            materials.authority.raw,
            materials.installation.raw,
            materials.run_template_raw,
            materials.close_template_raw,
            live_configured_pair=live_pair,
        )
    except Exception as exc:
        start_context.close()
        raise WarehouseW3InstalledIdentityRefused(
            "installed launch readiness differs"
        ) from exc
    try:
        _revalidate_live_start_context(start_context, acquirer, lineage)
    except Exception:
        start_context.close()
        raise
    try:
        writer = prepare_w3_invocation(readiness)
    except Exception as exc:
        start_context.close()
        raise WarehouseW3CompositionError(
            "installed invocation claim could not be prepared"
        ) from exc
    backend: SpawnBackend | None = None
    service: ServiceCgroup | None = None
    try:
        try:
            writer.bind_invocation_lineage(lineage)
        except Exception as exc:
            writer.mark_incomplete("LINEAGE_BIND_FAILED")
            raise WarehouseW3CompositionError(
                "invocation lineage could not be bound"
            ) from exc
        try:
            service = ServiceCgroup.open_current(
                live_pair.run,
                lineage,
            )
        except Exception as exc:
            writer.mark_incomplete("SERVICE_CGROUP_FAILED")
            raise WarehouseW3CompositionError(
                "delegated service cgroup could not be acquired"
            ) from exc
        try:
            capture_fd = _open_capture_directory(
                Path(materials.installation.projected_terminal_root) / "evidence"
            )
        except Exception as exc:
            service.close_unconsumed()
            service = None
            writer.mark_incomplete("CAPTURE_DIRECTORY_FAILED")
            raise WarehouseW3CompositionError(
                "terminal capture directory could not be pinned"
            ) from exc
        try:
            service_for_backend = service
            service = None
            try:
                opened = SpawnBackend.open(
                    service_for_backend,
                    capture_fd,
                )
            finally:
                os.close(capture_fd)
        except Exception as exc:
            writer.mark_incomplete("BACKEND_OPEN_FAILED")
            raise WarehouseW3CompositionError(
                "generic spawn backend open raised"
            ) from exc
        if type(opened) is BackendOpenFailure:
            writer.mark_incomplete("BACKEND_OPEN_FAILED")
            raise WarehouseW3CompositionError("generic spawn backend failed to open")
        if type(opened) is not SpawnBackend:
            raise WarehouseW3CompositionError(
                "generic spawn backend returned an unknown result"
            )
        backend = opened
        try:
            manifest_snapshot = read_regular(
                Path(materials.installation.run_root) / EXPECTED_MANIFEST_NAME,
                expected_sha256=EXPECTED_MANIFEST_SHA256,
            )
            manifest = json.loads(manifest_snapshot.data)
        except Exception as exc:
            _mark_run_incomplete(
                writer,
                backend,
                "MANIFEST_REOPEN_FAILED",
            )
            raise WarehouseW3CompositionError(
                "installed W3 manifest could not be reopened"
            ) from exc
        if type(manifest) is not dict or len(manifest.get("jobs", ())) != EXPECTED_ROWS:
            _mark_run_incomplete(
                writer,
                backend,
                "MANIFEST_REOPEN_FAILED",
            )
            raise WarehouseW3CompositionError(
                "installed W3 manifest differs before execution"
            )
        for ordinal, job in enumerate(manifest["jobs"]):
            if type(job) is not dict or job.get("job_ordinal") != ordinal:
                _mark_run_incomplete(
                    writer,
                    backend,
                    "SCHEDULE_IDENTITY_FAILED",
                )
                raise WarehouseW3CompositionError("installed W3 job schedule differs")
            key = JobCgroupKey.create(
                ordinal=ordinal,
                invocation_nonce=materials.authority.nonce,
            )
            try:
                spec = process_spec_for_job(
                    Path(materials.installation.run_root),
                    manifest,
                    job,
                )
            except Exception as exc:
                _mark_run_incomplete(
                    writer,
                    backend,
                    "PROCESS_SPEC_FAILED",
                )
                raise WarehouseW3CompositionError(
                    f"W3 job {ordinal} process fact differs"
                ) from exc
            started = backend.start_blocked(key, spec)
            if type(started) in (
                PreHandleFailure,
                ContainedSpawnFailure,
            ):
                _mark_run_incomplete(
                    writer,
                    backend,
                    "SPAWN_START_FAILED",
                )
                raise WarehouseW3CompositionError(
                    f"W3 job {ordinal} did not reach blocked start"
                )
            settled = backend.release_and_collect(started)
            if type(settled) is ContainedSpawnFailure:
                _mark_run_incomplete(
                    writer,
                    backend,
                    "SPAWN_SETTLEMENT_FAILED",
                )
                raise WarehouseW3CompositionError(f"W3 job {ordinal} did not settle")
            if type(settled) is not SettledJob:
                raise WarehouseW3CompositionError(
                    "generic spawn backend returned an unknown job result"
                )
            observation = settled.observation
            observation_commit = writer.record_observation(
                ordinal,
                observation,
            )
            try:
                row = validate_closed_observation(
                    Path(materials.installation.run_root),
                    manifest,
                    EXPECTED_MANIFEST_SHA256,
                    job,
                    observation,
                )
            except Exception as exc:
                incomplete = writer.mark_incomplete("WAREHOUSE_VALIDATION_FAILED")
                backend.remove_after_incomplete_commit(
                    settled,
                    observation_commit,
                    incomplete,
                )
                backend.close_idle()
                raise WarehouseW3CompositionError(
                    f"W3 job {ordinal} failed scientific validation"
                ) from exc
            row_commit = writer.commit_opaque_row(
                ordinal,
                observation.observation_sha256,
                row,
            )
            backend.remove_after_opaque_commit(
                settled,
                row_commit,
            )
        _complete_installed_run(writer, backend, start_context)
    except Exception:
        if service is not None:
            service.close_unconsumed()
        raise
    finally:
        start_context.close()


def _seal_installed_unit_drained(
    materials: _InstalledMaterials,
) -> None:
    acquirer = Systemd255Acquirer(SystemdDbusPropertyReader())
    root = Path(materials.installation.projected_terminal_root)
    lineage = load_invocation_lineage(
        root,
        materials.terminal_policy,
    )
    environment = acquirer.acquire_stop_post_environment(
        _systemd_environment(
            "INVOCATION_ID",
            "SERVICE_RESULT",
            "EXIT_CODE",
            "EXIT_STATUS",
        )
    )
    topology = acquirer.acquire_stop_post_topology(
        lineage=lineage,
        environment=environment,
    )
    seal_unit_drained(
        root,
        materials.terminal_policy,
        lineage,
        environment,
        topology,
    )


def _read_rows(
    materials: _InstalledMaterials,
) -> tuple[tuple[bytes, ...], tuple[dict[str, object], ...]]:
    raw_root = Path(materials.installation.projected_terminal_root) / "raw"
    rows = []
    identities = []
    for ordinal in range(EXPECTED_ROWS):
        snapshot = read_regular(raw_root / f"{ordinal:06d}.opaque")
        rows.append(snapshot.data)
        identities.append(
            {
                "job_ordinal": ordinal,
                "opaque_publication_key": (f"warehouse-w3-row-{ordinal:03d}"),
                "sha256": snapshot.sha256,
                "size_bytes": snapshot.size_bytes,
            }
        )
    return tuple(rows), tuple(identities)


def _close_installed(materials: _InstalledMaterials) -> None:
    acquirer = Systemd255Acquirer(SystemdDbusPropertyReader())
    root = Path(materials.installation.projected_terminal_root)
    lineage = load_invocation_lineage(
        root,
        materials.terminal_policy,
    )
    projection = materials.installation.projection_root
    python = f"{projection}/environment/bin/python"
    tool = f"{projection}/sealed/bin/scion-w3-tool"
    expected_argv = (
        python,
        "-B",
        "-s",
        tool,
        "seal-unit-drained",
        materials.installation.launch_id,
    )
    final = acquirer.acquire_unit_final(
        expected_unit=materials.installation.run_unit,
        expected_invocation_id=lineage.invocation_id,
        expected_exec_path=python,
        expected_argv=expected_argv,
    )
    observe_unit_final(
        root,
        materials.terminal_policy,
        final.handoff,
    )
    manifest_snapshot = read_regular(
        Path(materials.installation.run_root) / EXPECTED_MANIFEST_NAME,
        expected_sha256=EXPECTED_MANIFEST_SHA256,
    )
    manifest = json.loads(manifest_snapshot.data)
    if type(manifest) is not dict:
        raise WarehouseW3CompositionError("installed W3 manifest differs at close")
    rows, identities = _read_rows(materials)
    results, report, receipt, _report_value = replay_artifacts(
        manifest,
        EXPECTED_MANIFEST_SHA256,
        rows,
        identities,
    )
    complete = accept_invocation(
        root,
        materials.terminal_policy,
        _sha256(receipt),
    )
    publish_opaque_artifact_bundle(
        root,
        materials.terminal_policy,
        complete,
        (
            (EXPECTED_ARTIFACT_NAMES[0], results),
            (EXPECTED_ARTIFACT_NAMES[1], report),
            (EXPECTED_ARTIFACT_NAMES[2], receipt),
        ),
    )


def dispatch_installed_launch(command: str, launch_id: str) -> None:
    """Run one fixed installed command; this surface cannot start a unit."""

    if command not in {"run", "seal-unit-drained", "close"}:
        raise WarehouseW3CompositionError("unknown W3 launch command")
    if _SHA256_RE.fullmatch(launch_id) is None:
        raise WarehouseW3CompositionError(
            "launch id is not 64 lowercase hexadecimal characters"
        )
    if command == "run":
        from .w3_start_gate import WarehouseW3InstalledIdentityRefused

        try:
            materials = _installed_materials(
                launch_id,
                require_claim=False,
            )
        except WarehouseW3CompositionError as exc:
            raise WarehouseW3InstalledIdentityRefused(
                "fixed installed launch materials differ"
            ) from exc
        _run_installed(materials)
    else:
        materials = _installed_materials(
            launch_id,
            require_claim=True,
        )
        if command == "seal-unit-drained":
            _seal_installed_unit_drained(materials)
        else:
            _close_installed(materials)


__all__ = [
    "EXPECTED_ARTIFACT_NAMES",
    "EXPECTED_CORRECTION_DESIGN_SHA256",
    "EXPECTED_MANIFEST_SHA256",
    "EXPECTED_NATIVE_ACCEPTANCE_CONTRACT_SHA256",
    "EXPECTED_NATIVE_ACCEPTANCE_RECORD_SHA256",
    "EXPECTED_NONCE_LEDGER_PARENT",
    "EXPECTED_ROWS",
    "EXPECTED_SCIENTIFIC_DESIGN_SHA256",
    "EXPECTED_SOURCE_COMMIT",
    "WarehouseW3CompositionError",
    "WarehouseW3LaunchReadyFact",
    "configured_pair_for_installation",
    "dispatch_installed_launch",
    "inspect_w3_launch_readiness",
    "prepare_w3_invocation",
]
