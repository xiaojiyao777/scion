"""Closed CVRP B0 launch contract and staged runtime materialization.

This module owns the scientific population, profile configuration, Protocol
time-limit resolution, Latin execution order, immutable runtime/input
snapshots, import probes, and per-job identities.  The CLI tool consumes the
resulting :class:`B0LaunchPlan`; it does not reinterpret these authorities.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import stat
import subprocess
import sys
from typing import Any, Mapping, Sequence

import yaml

from scion.config.protocol_config import ProtocolConfig
from scion.problems.cvrp.evidence.mechanism_matrix import (
    CvrpMatrixCase,
    CvrpMatrixJob,
    CvrpMechanismSpec,
    build_jobs,
    case_slice_for_dimension,
)


B0_CONTRACT = "scion.cvrp_b0_runner_contract.v3"
B0_STAGE = "screening"
B0_SEEDS = (11, 29, 43, 59)
B0_OUTER_TIMEOUT_PADDING_SEC = 60
B0_ORDER_CONTRACT = "scion.cvrp_b0_latin_rotation.v1"
B0_SELECTED_SURFACE = "solver_design"
_PROFILE_FLAG_NAMES = (
    "USE_VNS",
    "ENABLE_INITIAL_VNS",
    "ENABLE_EMBEDDED_VNS",
    "ENABLE_SIZE70_TWO_OPT_FALLBACK",
)
_SOLVER_VARIANT = "alns_vns"
_SNAPSHOT_IGNORED_PARTS = frozenset({"__pycache__", ".pytest_cache"})
_SOURCE_TOP_LEVEL_EXCLUDES = frozenset({"tests"})


@dataclass(frozen=True)
class B0Profile:
    """One immutable B0 mechanism profile and its rendered config authority."""

    profile_id: str
    label: str
    mechanism_family: str
    mechanism_slice: str
    description: str
    use_vns: bool
    enable_initial_vns: bool
    enable_embedded_vns: bool
    enable_size70_two_opt_fallback: bool

    @property
    def config_assignments(self) -> dict[str, Any]:
        return {
            "SOLVER_VARIANT": _SOLVER_VARIANT,
            "USE_VNS": self.use_vns,
            "ENABLE_INITIAL_VNS": self.enable_initial_vns,
            "ENABLE_EMBEDDED_VNS": self.enable_embedded_vns,
            "ENABLE_SIZE70_TWO_OPT_FALLBACK": (
                self.enable_size70_two_opt_fallback
            ),
        }

    def render_config(self, source: str) -> str:
        rendered = _replace_string_assignment(
            source,
            "SOLVER_VARIANT",
            _SOLVER_VARIANT,
        )
        for name in _PROFILE_FLAG_NAMES:
            rendered = _replace_boolean_assignment(
                rendered,
                name,
                bool(self.config_assignments[name]),
            )
        return rendered

    def mechanism_spec(self) -> CvrpMechanismSpec:
        return CvrpMechanismSpec(
            mechanism_id=self.profile_id,
            label=self.label,
            mechanism_family=self.mechanism_family,
            mechanism_slice=self.mechanism_slice,
            description=self.description,
            overlays=(),
        )


B0_PROFILES = (
    B0Profile(
        profile_id="canonical_alns_vns",
        label="canonical ALNS+VNS",
        mechanism_family="canonical",
        mechanism_slice="alns_vns",
        description="Canonical construction, ALNS, initial VNS, and embedded VNS.",
        use_vns=True,
        enable_initial_vns=True,
        enable_embedded_vns=True,
        enable_size70_two_opt_fallback=True,
    ),
    B0Profile(
        profile_id="pure_alns_no_polish",
        label="pure ALNS without polish",
        mechanism_family="diagnostic_probe",
        mechanism_slice="pure_alns_no_polish",
        description="ALNS with VNS and the size-70 two-opt fallback disabled.",
        use_vns=False,
        enable_initial_vns=False,
        enable_embedded_vns=False,
        enable_size70_two_opt_fallback=False,
    ),
    B0Profile(
        profile_id="embedded_vns_disabled",
        label="embedded VNS disabled",
        mechanism_family="diagnostic_probe",
        mechanism_slice="disable_embedded_vns",
        description="Initial VNS enabled and embedded VNS disabled.",
        use_vns=True,
        enable_initial_vns=True,
        enable_embedded_vns=False,
        enable_size70_two_opt_fallback=True,
    ),
    B0Profile(
        profile_id="initial_vns_disabled",
        label="initial VNS disabled",
        mechanism_family="diagnostic_probe",
        mechanism_slice="disable_initial_vns",
        description="Initial VNS disabled and embedded VNS enabled.",
        use_vns=True,
        enable_initial_vns=False,
        enable_embedded_vns=True,
        enable_size70_two_opt_fallback=True,
    ),
)


@dataclass(frozen=True)
class B0ProfileRuntime:
    profile: B0Profile
    package_root: Path
    workspace: Path
    config_path: Path
    pythonpath_entries: tuple[str, ...]
    runtime_snapshot_sha256: str
    config_sha256: str
    profile_manifest_sha256: str
    import_probe_json: str
    import_probe_identity_sha256: str
    dependency_identity_sha256: str

    @property
    def import_probe(self) -> Mapping[str, Any]:
        payload = json.loads(self.import_probe_json)
        if not isinstance(payload, dict):
            raise AssertionError("frozen import probe is not an object")
        return payload

    def manifest_payload(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile.profile_id,
            "label": self.profile.label,
            "mechanism_family": self.profile.mechanism_family,
            "mechanism_slice": self.profile.mechanism_slice,
            "description": self.profile.description,
            "config_assignments": self.profile.config_assignments,
            "package_root": str(self.package_root),
            "workspace": str(self.workspace),
            "config_path": str(self.config_path),
            "pythonpath_entries": list(self.pythonpath_entries),
            "runtime_snapshot_sha256": self.runtime_snapshot_sha256,
            "config_sha256": self.config_sha256,
            "profile_manifest_sha256": self.profile_manifest_sha256,
            "import_probe": dict(self.import_probe),
            "import_probe_identity_sha256": self.import_probe_identity_sha256,
            "dependency_identity_sha256": self.dependency_identity_sha256,
        }


@dataclass(frozen=True)
class B0PythonRuntime:
    """Exact Python executable and build authority used by every B0 child."""

    executable_path: Path
    executable_sha256: str
    build_identity_json: str
    runtime_identity_sha256: str

    @property
    def build_identity(self) -> Mapping[str, Any]:
        payload = json.loads(self.build_identity_json)
        if not isinstance(payload, dict):
            raise AssertionError("frozen Python build identity is not an object")
        return payload

    def manifest_payload(self) -> dict[str, Any]:
        return {
            "executable_path": str(self.executable_path),
            "executable_sha256": self.executable_sha256,
            "build_identity": dict(self.build_identity),
            "runtime_identity_sha256": self.runtime_identity_sha256,
        }


@dataclass(frozen=True)
class B0PlannedJob:
    job: CvrpMatrixJob
    execution_ordinal: int
    execution_position: int
    rotation_offset: int
    runtime: B0ProfileRuntime
    protocol_identity_sha256: str
    case_manifest_identity_sha256: str
    input_snapshot_identity_sha256: str
    input_case_sha256: str
    python_executable_path: Path
    python_runtime_identity_sha256: str
    job_identity_sha256: str

    def contract_payload(self) -> dict[str, Any]:
        return {
            "matrix_contract": B0_CONTRACT,
            "job_identity_sha256": self.job_identity_sha256,
            "stage": B0_STAGE,
            "selected_surface": B0_SELECTED_SURFACE,
            "profile_id": self.runtime.profile.profile_id,
            "profile_config": self.runtime.profile.config_assignments,
            "resolved_time_limit_sec": self.job.time_budget_sec,
            "execution_ordinal": self.execution_ordinal,
            "execution_position": self.execution_position,
            "rotation_offset": self.rotation_offset,
            "order_contract": B0_ORDER_CONTRACT,
            "outer_timeout_padding_sec": B0_OUTER_TIMEOUT_PADDING_SEC,
            "runtime_snapshot_sha256": self.runtime.runtime_snapshot_sha256,
            "protocol_identity_sha256": self.protocol_identity_sha256,
            "case_manifest_identity_sha256": self.case_manifest_identity_sha256,
            "input_snapshot_identity_sha256": self.input_snapshot_identity_sha256,
            "profile_config_sha256": self.runtime.config_sha256,
            "profile_manifest_sha256": self.runtime.profile_manifest_sha256,
            "import_probe_identity_sha256": (
                self.runtime.import_probe_identity_sha256
            ),
            "dependency_identity_sha256": (
                self.runtime.dependency_identity_sha256
            ),
            "python_runtime_identity_sha256": (
                self.python_runtime_identity_sha256
            ),
            "input_case_sha256": self.input_case_sha256,
        }

    def manifest_payload(self) -> dict[str, Any]:
        return {**self.job.to_payload(), **self.contract_payload()}


@dataclass(frozen=True)
class B0LaunchPlan:
    output_root: Path
    source_package_root: Path
    input_root: Path
    protocol_path: Path
    case_manifest_path: Path
    authority_root: Path
    protocol_snapshot_path: Path
    case_manifest_snapshot_path: Path
    protocol_identity_sha256: str
    case_manifest_identity_sha256: str
    authority_snapshot_identity_sha256: str
    source_package_identity_sha256: str
    input_snapshot_identity_sha256: str
    input_case_identities: tuple[tuple[str, str], ...]
    profiles: tuple[B0ProfileRuntime, ...]
    execution_jobs: tuple[B0PlannedJob, ...]
    summary_jobs: tuple[B0PlannedJob, ...]
    cases: tuple[CvrpMatrixCase, ...]
    time_limit_policy_json: str
    python_runtime: B0PythonRuntime
    selected_surface: str
    dry_run: bool

    @property
    def profile_workspaces(self) -> dict[str, Path]:
        return {
            runtime.profile.profile_id: runtime.workspace
            for runtime in self.profiles
        }

    @property
    def planned_by_job_id(self) -> dict[str, B0PlannedJob]:
        return {planned.job.job_id: planned for planned in self.execution_jobs}

    @property
    def time_limit_policy(self) -> Mapping[str, Any]:
        payload = json.loads(self.time_limit_policy_json)
        if not isinstance(payload, dict):
            raise AssertionError("frozen time-limit policy is not an object")
        return payload

    @property
    def python(self) -> str:
        return str(self.python_runtime.executable_path)

    def manifest_payload(self) -> dict[str, Any]:
        return {
            "schema_version": "scion.cvrp_mechanism_matrix.v1",
            "matrix_contract": B0_CONTRACT,
            "problem_id": "cvrp",
            "stage": B0_STAGE,
            "dry_run": self.dry_run,
            "output_root": str(self.output_root),
            "python": self.python,
            "python_runtime": self.python_runtime.manifest_payload(),
            "selected_surface": self.selected_surface,
            "outer_timeout_padding_sec": B0_OUTER_TIMEOUT_PADDING_SEC,
            "order_contract": B0_ORDER_CONTRACT,
            "authority": {
                "protocol": {
                    "source_path": str(self.protocol_path),
                    "snapshot_path": str(self.protocol_snapshot_path),
                    "sha256": self.protocol_identity_sha256,
                },
                "case_manifest": {
                    "source_path": str(self.case_manifest_path),
                    "snapshot_path": str(self.case_manifest_snapshot_path),
                    "sha256": self.case_manifest_identity_sha256,
                },
                "authority_snapshot": {
                    "path": str(self.authority_root),
                    "sha256": self.authority_snapshot_identity_sha256,
                },
                "source_package": {
                    "path": str(self.source_package_root),
                    "sha256": self.source_package_identity_sha256,
                    "scope": "production_scion_package_excluding_tests_and_caches",
                },
                "input_snapshot": {
                    "path": str(self.input_root),
                    "sha256": self.input_snapshot_identity_sha256,
                    "case_sha256": dict(self.input_case_identities),
                },
            },
            "scientific_time_limit_policy": dict(self.time_limit_policy),
            "profiles": [runtime.manifest_payload() for runtime in self.profiles],
            "cases": [case.to_payload() for case in self.cases],
            "seeds": list(B0_SEEDS),
            "execution_jobs": [
                planned.manifest_payload() for planned in self.execution_jobs
            ],
            "jobs": [planned.manifest_payload() for planned in self.summary_jobs],
        }


def prepare_b0_launch_plan(
    *,
    source_package_root: str | Path,
    source_data_root: str | Path,
    protocol_path: str | Path,
    case_manifest_path: str | Path,
    output_root: str | Path,
    python: str,
    selected_surface: str,
    outer_timeout_padding_sec: int,
    dry_run: bool,
) -> B0LaunchPlan:
    """Materialize and close one fresh B0 launch plan."""

    if int(outer_timeout_padding_sec) != B0_OUTER_TIMEOUT_PADDING_SEC:
        raise ValueError(
            "CVRP B0 outer timeout padding drift: "
            f"expected {B0_OUTER_TIMEOUT_PADDING_SEC}, got {outer_timeout_padding_sec}"
        )
    if str(selected_surface or "").strip() != B0_SELECTED_SURFACE:
        raise ValueError(
            "CVRP B0 selected surface is frozen at "
            f"{B0_SELECTED_SURFACE!r}"
        )
    _validate_profiles(B0_PROFILES)
    package_source = Path(source_package_root).expanduser().resolve(strict=True)
    data_source = Path(source_data_root).expanduser().resolve(strict=True)
    protocol_source = Path(protocol_path).expanduser().absolute()
    manifest_source = Path(case_manifest_path).expanduser().absolute()
    output = _create_fresh_output_root(output_root)
    canonical_workspace = package_source / "problems" / "cvrp"
    _validate_authority_paths(
        canonical_workspace=canonical_workspace,
        protocol_path=protocol_source,
        manifest_path=manifest_source,
    )
    _reject_nested_output(
        output=output,
        protected_roots=(package_source, data_source),
    )

    protocol, protocol_bytes = _capture_regular_file_bytes(
        protocol_source,
        label="Protocol authority",
    )
    manifest, manifest_bytes = _capture_regular_file_bytes(
        manifest_source,
        label="case-manifest authority",
    )
    protocol_sha256 = _sha256_bytes(protocol_bytes)
    manifest_sha256 = _sha256_bytes(manifest_bytes)
    protocol_config = _parse_protocol_authority(protocol_bytes)
    authority_payload = _parse_case_manifest_authority(manifest_bytes)
    cases = _cases_from_authority_payload(authority_payload)
    authority_entries, authority_payload = _validate_case_authority(
        cases=cases,
        payload=authority_payload,
        protocol=protocol_config,
    )
    limits = _resolve_scientific_time_limits(cases, protocol_config)
    (
        authority_root,
        protocol_snapshot,
        manifest_snapshot,
        authority_snapshot_identity,
    ) = _materialize_authority_snapshot(
        output_root=output,
        protocol_bytes=protocol_bytes,
        protocol_sha256=protocol_sha256,
        manifest_bytes=manifest_bytes,
        manifest_sha256=manifest_sha256,
    )

    source_inventory = _snapshot_inventory(
        package_source,
        exclude_top_level=_SOURCE_TOP_LEVEL_EXCLUDES,
    )
    source_identity = _inventory_sha256(source_inventory)
    python_runtime = _capture_python_runtime(python)
    _validate_launcher_python(python_runtime)
    dependency_paths = _discover_python_dependency_paths(
        python=python_runtime.executable_path,
        forbidden_roots=(package_source, output),
    )
    runtime_root = output / "runtime_snapshots"
    runtimes = tuple(
        _materialize_profile_runtime(
            source_package_root=package_source,
            source_inventory=source_inventory,
            source_identity_sha256=source_identity,
            runtime_root=runtime_root,
            profile=profile,
            python_runtime=python_runtime,
            dependency_paths=dependency_paths,
        )
        for profile in B0_PROFILES
    )
    if _inventory_sha256(
        _snapshot_inventory(
            package_source,
            exclude_top_level=_SOURCE_TOP_LEVEL_EXCLUDES,
        )
    ) != source_identity:
        raise ValueError("CVRP B0 source package changed during materialization")

    input_root, input_case_ids, input_identity = _materialize_input_snapshot(
        cases=cases,
        authority_entries=authority_entries,
        source_data_root=data_source,
        output_root=output,
    )
    execution_jobs, summary_jobs = _build_planned_jobs(
        cases=cases,
        limits=limits,
        runtimes=runtimes,
        input_case_ids=dict(input_case_ids),
        output_root=output,
        protocol_sha256=protocol_sha256,
        manifest_sha256=manifest_sha256,
        input_snapshot_sha256=input_identity,
        python_runtime=python_runtime,
    )
    plan = B0LaunchPlan(
        output_root=output,
        source_package_root=package_source,
        input_root=input_root,
        protocol_path=protocol,
        case_manifest_path=manifest,
        authority_root=authority_root,
        protocol_snapshot_path=protocol_snapshot,
        case_manifest_snapshot_path=manifest_snapshot,
        protocol_identity_sha256=protocol_sha256,
        case_manifest_identity_sha256=manifest_sha256,
        authority_snapshot_identity_sha256=authority_snapshot_identity,
        source_package_identity_sha256=source_identity,
        input_snapshot_identity_sha256=input_identity,
        input_case_identities=input_case_ids,
        profiles=runtimes,
        execution_jobs=execution_jobs,
        summary_jobs=summary_jobs,
        cases=cases,
        time_limit_policy_json=_canonical_json(
            protocol_config.runtime.time_limits.summary(
                stage=B0_STAGE,
                cases=[case.source_path for case in cases],
                fallback_time_limit_sec=(
                    protocol_config.runtime.time_limits.stage_defaults[B0_STAGE]
                ),
            )
        ),
        python_runtime=python_runtime,
        selected_surface=B0_SELECTED_SURFACE,
        dry_run=bool(dry_run),
    )
    verify_b0_launch_plan(plan)
    if authority_payload.get("problem_id") != "cvrp":
        raise AssertionError("validated authority changed unexpectedly")
    return plan


def verify_b0_launch_plan(plan: B0LaunchPlan) -> None:
    """Verify fixed authorities, runtime, interpreter, and dependencies."""

    observed_authority = _inventory_sha256(
        _snapshot_inventory(plan.authority_root)
    )
    if observed_authority != plan.authority_snapshot_identity_sha256:
        raise ValueError("CVRP B0 authority snapshot drift")
    if _sha256_file(plan.protocol_snapshot_path) != plan.protocol_identity_sha256:
        raise ValueError("CVRP B0 Protocol authority snapshot drift")
    if (
        _sha256_file(plan.case_manifest_snapshot_path)
        != plan.case_manifest_identity_sha256
    ):
        raise ValueError("CVRP B0 case-manifest authority snapshot drift")
    _assert_read_only_tree(plan.authority_root)
    observed_python = _capture_python_runtime(plan.python)
    _validate_launcher_python(observed_python)
    if observed_python != plan.python_runtime:
        raise ValueError("CVRP B0 Python executable/build identity drift")
    observed_input = _inventory_sha256(_snapshot_inventory(plan.input_root))
    if observed_input != plan.input_snapshot_identity_sha256:
        raise ValueError("CVRP B0 input snapshot drift")
    for runtime in plan.profiles:
        package_dir = runtime.package_root / "scion"
        observed_runtime = _inventory_sha256(_snapshot_inventory(package_dir))
        if observed_runtime != runtime.runtime_snapshot_sha256:
            raise ValueError(
                f"CVRP B0 runtime snapshot drift: {runtime.profile.profile_id}"
            )
        if _sha256_file(runtime.config_path) != runtime.config_sha256:
            raise ValueError(
                f"CVRP B0 config snapshot drift: {runtime.profile.profile_id}"
            )
        observed_probe = _run_import_probe(
            python_runtime=plan.python_runtime,
            package_root=runtime.package_root,
            workspace=runtime.workspace,
            profile=runtime.profile,
            expected_runtime_sha256=runtime.runtime_snapshot_sha256,
            expected_config_sha256=runtime.config_sha256,
            dependency_paths=runtime.pythonpath_entries[1:],
        )
        if _canonical_sha256(observed_probe) != runtime.import_probe_identity_sha256:
            raise ValueError(
                f"CVRP B0 import/dependency identity drift: "
                f"{runtime.profile.profile_id}"
            )
        if (
            _dependency_identity_sha256(observed_probe)
            != runtime.dependency_identity_sha256
        ):
            raise ValueError(
                f"CVRP B0 dependency identity drift: {runtime.profile.profile_id}"
            )
        _assert_read_only_tree(package_dir)
    _assert_read_only_tree(plan.input_root)


def _validate_profiles(profiles: Sequence[B0Profile]) -> None:
    expected_ids = (
        "canonical_alns_vns",
        "pure_alns_no_polish",
        "embedded_vns_disabled",
        "initial_vns_disabled",
    )
    if tuple(profile.profile_id for profile in profiles) != expected_ids:
        raise ValueError("CVRP B0 profile population or order drift")
    fingerprints: set[tuple[tuple[str, Any], ...]] = set()
    for profile in profiles:
        assignments = profile.config_assignments
        if set(assignments) != {"SOLVER_VARIANT", *_PROFILE_FLAG_NAMES}:
            raise ValueError(f"CVRP B0 profile flag drift: {profile.profile_id}")
        if assignments["SOLVER_VARIANT"] != _SOLVER_VARIANT:
            raise ValueError(f"CVRP B0 solver variant drift: {profile.profile_id}")
        if any(type(assignments[name]) is not bool for name in _PROFILE_FLAG_NAMES):
            raise ValueError(f"CVRP B0 non-boolean profile flag: {profile.profile_id}")
        fingerprint = tuple(sorted(assignments.items()))
        if fingerprint in fingerprints:
            raise ValueError(f"CVRP B0 duplicate profile: {profile.profile_id}")
        fingerprints.add(fingerprint)


def _create_fresh_output_root(value: str | Path) -> Path:
    path = Path(value).expanduser().resolve(strict=False)
    if path.is_symlink():
        raise ValueError(f"CVRP B0 output root may not be a symlink: {path}")
    if path.exists():
        if not path.is_dir():
            raise ValueError(f"CVRP B0 output root is not a directory: {path}")
        if any(path.iterdir()):
            raise ValueError(f"CVRP B0 output root must be fresh/empty: {path}")
    else:
        path.mkdir(parents=True)
    return path.resolve(strict=True)


def _reject_nested_output(*, output: Path, protected_roots: Sequence[Path]) -> None:
    for root in protected_roots:
        try:
            output.relative_to(root)
        except ValueError:
            continue
        raise ValueError(f"CVRP B0 output root is inside protected source: {root}")


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root.resolve(strict=True))
    except ValueError:
        return False
    return True


def _validate_authority_paths(
    *,
    canonical_workspace: Path,
    protocol_path: Path,
    manifest_path: Path,
) -> None:
    expected_protocol = (canonical_workspace / "formal" / "protocol.yaml").resolve(
        strict=True
    )
    expected_manifest = (
        canonical_workspace / "formal" / "manifests" / "screening.json"
    ).resolve(strict=True)
    if protocol_path != expected_protocol:
        raise ValueError("CVRP B0 protocol authority path drift")
    if manifest_path != expected_manifest:
        raise ValueError("CVRP B0 screening authority path drift")


def _capture_regular_file_bytes(path: Path, *, label: str) -> tuple[Path, bytes]:
    """Capture one regular, non-symlink source through a stable descriptor."""

    absolute = path.expanduser().absolute()
    _assert_no_symlink_components(absolute, label=label)
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(absolute, flags)
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise ValueError(f"CVRP B0 {label} is not a regular file: {absolute}")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    stable_fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
    if any(getattr(before, field) != getattr(after, field) for field in stable_fields):
        raise ValueError(f"CVRP B0 {label} changed during descriptor capture")
    captured = b"".join(chunks)
    if len(captured) != before.st_size:
        raise ValueError(f"CVRP B0 {label} size changed during descriptor capture")
    final = absolute.lstat()
    if stat.S_ISLNK(final.st_mode) or (final.st_dev, final.st_ino) != (
        before.st_dev,
        before.st_ino,
    ):
        raise ValueError(f"CVRP B0 {label} changed after descriptor capture")
    return absolute.resolve(strict=True), captured


def _assert_no_symlink_components(path: Path, *, label: str) -> None:
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current = current / part
        try:
            mode = current.lstat().st_mode
        except FileNotFoundError as exc:
            raise ValueError(f"CVRP B0 {label} does not exist: {path}") from exc
        if stat.S_ISLNK(mode):
            raise ValueError(f"CVRP B0 {label} contains a symlink: {current}")


def _parse_protocol_authority(captured: bytes) -> ProtocolConfig:
    payload = yaml.safe_load(captured.decode("utf-8"))
    return ProtocolConfig.model_validate(payload)


def _parse_case_manifest_authority(captured: bytes) -> Mapping[str, Any]:
    payload = json.loads(captured.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("CVRP B0 case-manifest authority must be an object")
    return payload


def _cases_from_authority_payload(
    payload: Mapping[str, Any],
) -> tuple[CvrpMatrixCase, ...]:
    raw_cases = payload.get("cases")
    if not isinstance(raw_cases, list):
        raise ValueError("CVRP B0 case-manifest authority has no cases list")
    cases: list[CvrpMatrixCase] = []
    for raw in raw_cases:
        if not isinstance(raw, dict):
            raise ValueError("CVRP B0 case entry must be an object")
        source_path = str(raw.get("source_path") or raw.get("path") or "").strip()
        case_id = str(raw.get("case_id") or "").strip() or Path(source_path).stem
        if not case_id or not source_path:
            raise ValueError("CVRP B0 case identity is incomplete")
        dimension = _optional_int(raw.get("dimension"))
        family = str(raw.get("subset") or _case_family(source_path)).strip()
        cases.append(
            CvrpMatrixCase(
                case_id=case_id,
                source_path=source_path,
                case_family=family or "unknown",
                case_slice=case_slice_for_dimension(dimension),
                dimension=dimension,
                bks=_optional_float(raw.get("bks")),
                bks_routes=_optional_int(raw.get("bks_routes")),
            )
        )
    if not cases:
        raise ValueError("CVRP B0 case-manifest authority selected no cases")
    return tuple(cases)


def _case_family(source_path: str) -> str:
    parts = Path(source_path).parts
    if len(parts) >= 3 and parts[-3] == "cvrplib":
        return parts[-2]
    return parts[-2] if len(parts) >= 2 else ""


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def _validate_case_authority(
    *,
    cases: Sequence[CvrpMatrixCase],
    payload: Mapping[str, Any],
    protocol: ProtocolConfig,
) -> tuple[dict[str, Mapping[str, Any]], Mapping[str, Any]]:
    if not isinstance(payload, dict) or payload.get("problem_id") != "cvrp":
        raise ValueError("CVRP B0 case authority identity drift")
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict) or metadata.get("stage") != B0_STAGE:
        raise ValueError("CVRP B0 case authority stage drift")
    raw_cases = payload.get("cases")
    if not isinstance(raw_cases, list):
        raise ValueError("CVRP B0 case authority has no cases list")
    expected_population = max(
        int(protocol.screening.expand_to_modify),
        int(protocol.screening.expand_to_create),
    )
    if len(cases) != expected_population or len(raw_cases) != expected_population:
        raise ValueError("CVRP B0 Protocol population drift")
    config = payload.get("config")
    manifest_seeds = config.get("seeds") if isinstance(config, dict) else None
    if manifest_seeds != list(B0_SEEDS):
        raise ValueError("CVRP B0 seed authority drift")
    entries: dict[str, Mapping[str, Any]] = {}
    source_paths: set[str] = set()
    for raw in raw_cases:
        if not isinstance(raw, dict):
            raise ValueError("CVRP B0 case entry must be an object")
        case_id = str(raw.get("case_id") or "").strip()
        source_path = str(raw.get("source_path") or "").strip()
        if not case_id or not source_path:
            raise ValueError("CVRP B0 case identity is incomplete")
        if case_id in entries or source_path in source_paths:
            raise ValueError("CVRP B0 case identities must be unique")
        entries[case_id] = raw
        source_paths.add(source_path)
    loaded = {case.case_id: case.source_path for case in cases}
    authoritative = {
        case_id: str(raw["source_path"]) for case_id, raw in entries.items()
    }
    if loaded != authoritative:
        raise ValueError("CVRP B0 loaded cases differ from stage authority")
    return entries, payload


def _resolve_scientific_time_limits(
    cases: Sequence[CvrpMatrixCase],
    protocol: ProtocolConfig,
) -> dict[str, int]:
    defaults = protocol.runtime.time_limits.stage_defaults
    if B0_STAGE not in defaults:
        raise ValueError("CVRP B0 Protocol has no screening time-limit default")
    return {
        case.case_id: protocol.runtime.time_limits.resolve(
            stage=B0_STAGE,
            case_path=case.source_path,
            fallback_time_limit_sec=defaults[B0_STAGE],
        )
        for case in cases
    }


def _materialize_authority_snapshot(
    *,
    output_root: Path,
    protocol_bytes: bytes,
    protocol_sha256: str,
    manifest_bytes: bytes,
    manifest_sha256: str,
) -> tuple[Path, Path, Path, str]:
    root = output_root / "authority_snapshot"
    root.mkdir()
    protocol_path = root / "protocol.yaml"
    manifest_path = root / "screening.json"
    _write_captured_bytes(protocol_path, protocol_bytes)
    _write_captured_bytes(manifest_path, manifest_bytes)
    if _sha256_file(protocol_path) != protocol_sha256:
        raise ValueError("CVRP B0 Protocol authority snapshot copy drift")
    if _sha256_file(manifest_path) != manifest_sha256:
        raise ValueError("CVRP B0 case-manifest authority snapshot copy drift")
    identity = _inventory_sha256(_snapshot_inventory(root))
    _make_tree_read_only(root)
    return root, protocol_path, manifest_path, identity


def _write_captured_bytes(path: Path, captured: bytes) -> None:
    with path.open("xb") as handle:
        handle.write(captured)
        handle.flush()
        os.fsync(handle.fileno())


def _resolve_python_executable(value: str | Path) -> Path:
    text = str(value).strip()
    if not text:
        raise ValueError("CVRP B0 Python executable is empty")
    candidate = shutil.which(text)
    if candidate is None:
        candidate = str(Path(text).expanduser())
    resolved = Path(candidate).expanduser().resolve(strict=True)
    if not resolved.is_file() or not os.access(resolved, os.X_OK):
        raise ValueError(f"CVRP B0 Python executable is invalid: {resolved}")
    return resolved


def _capture_python_runtime(value: str | Path) -> B0PythonRuntime:
    executable = _resolve_python_executable(value)
    executable, executable_bytes = _capture_regular_file_bytes(
        executable,
        label="Python executable",
    )
    executable_sha256 = _sha256_bytes(executable_bytes)
    script = r'''
import json, platform, sys
from pathlib import Path
payload = {
    "abiflags": sys.abiflags,
    "build": list(platform.python_build()),
    "cache_tag": sys.implementation.cache_tag,
    "compiler": platform.python_compiler(),
    "executable_path": str(Path(sys.executable).resolve()),
    "implementation": sys.implementation.name,
    "implementation_version": list(sys.implementation.version),
    "version": sys.version,
    "version_info": list(sys.version_info),
}
print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
'''
    completed = subprocess.run(
        [str(executable), "-S", "-c", script],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )
    if completed.returncode != 0:
        raise ValueError(
            "CVRP B0 cannot inspect Python build identity: "
            f"{completed.stderr.strip()}"
        )
    build = json.loads(completed.stdout)
    if not isinstance(build, dict):
        raise ValueError("CVRP B0 Python build probe returned invalid data")
    if build.get("executable_path") != str(executable):
        raise ValueError("CVRP B0 Python executable realpath drift")
    if _sha256_file(executable) != executable_sha256:
        raise ValueError("CVRP B0 Python executable changed during identity capture")
    identity = _canonical_sha256(
        {
            "schema": "scion.cvrp_b0_python_runtime.v1",
            "executable_sha256": executable_sha256,
            "build_identity": build,
        }
    )
    return B0PythonRuntime(
        executable_path=executable,
        executable_sha256=executable_sha256,
        build_identity_json=_canonical_json(build),
        runtime_identity_sha256=identity,
    )


def _validate_launcher_python(python_runtime: B0PythonRuntime) -> None:
    launcher = Path(sys.executable).resolve(strict=True)
    if launcher != python_runtime.executable_path:
        raise ValueError(
            "CVRP B0 launcher Python must exactly match --python: "
            f"launcher={launcher}, child={python_runtime.executable_path}"
        )
    if _sha256_file(launcher) != python_runtime.executable_sha256:
        raise ValueError("CVRP B0 launcher Python executable hash drift")
    launcher_build = {
        "abiflags": sys.abiflags,
        "build": list(platform.python_build()),
        "cache_tag": sys.implementation.cache_tag,
        "compiler": platform.python_compiler(),
        "executable_path": str(launcher),
        "implementation": sys.implementation.name,
        "implementation_version": list(sys.implementation.version),
        "version": sys.version,
        "version_info": list(sys.version_info),
    }
    if _canonical_json(launcher_build) != python_runtime.build_identity_json:
        raise ValueError("CVRP B0 launcher Python build identity drift")


def _discover_python_dependency_paths(
    *,
    python: str | Path,
    forbidden_roots: Sequence[Path],
) -> tuple[str, ...]:
    completed = subprocess.run(
        [
            str(Path(python)),
            "-c",
            "import json,sys; print(json.dumps(sys.path))",
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )
    if completed.returncode != 0:
        raise ValueError(f"CVRP B0 cannot inspect Python dependency paths: {completed.stderr}")
    raw = json.loads(completed.stdout)
    if not isinstance(raw, list):
        raise ValueError("CVRP B0 Python path probe returned invalid data")
    paths: list[str] = []
    for value in raw:
        text = str(value or "").strip()
        if not text or not (
            "site-packages" in text or "dist-packages" in text
        ):
            continue
        candidate = Path(text).expanduser()
        if not candidate.is_dir():
            continue
        resolved = candidate.resolve(strict=True)
        if any(_is_within(resolved, root) for root in forbidden_roots):
            raise ValueError(f"CVRP B0 dependency path mixes protected source: {resolved}")
        resolved_text = str(resolved)
        if resolved_text not in paths:
            paths.append(resolved_text)
    if not paths:
        raise ValueError("CVRP B0 found no isolated Python dependency paths")
    return tuple(paths)


def _materialize_profile_runtime(
    *,
    source_package_root: Path,
    source_inventory: Sequence[tuple[str, str]],
    source_identity_sha256: str,
    runtime_root: Path,
    profile: B0Profile,
    python_runtime: B0PythonRuntime,
    dependency_paths: Sequence[str],
) -> B0ProfileRuntime:
    package_root = runtime_root / profile.profile_id / "package"
    staged_package = package_root / "scion"
    _copy_inventory(
        source_root=source_package_root,
        target_root=staged_package,
        inventory=source_inventory,
    )
    config_path = (
        staged_package
        / "problems"
        / "cvrp"
        / "policies"
        / "baseline_modules"
        / "config.py"
    )
    source_config = config_path.read_text(encoding="utf-8")
    rendered = profile.render_config(source_config)
    config_path.write_text(rendered, encoding="utf-8")
    config_sha256 = _sha256_file(config_path)
    runtime_sha256 = _inventory_sha256(_snapshot_inventory(staged_package))
    _make_tree_read_only(staged_package)
    workspace = staged_package / "problems" / "cvrp"
    probe = _run_import_probe(
        python_runtime=python_runtime,
        package_root=package_root,
        workspace=workspace,
        profile=profile,
        expected_runtime_sha256=runtime_sha256,
        expected_config_sha256=config_sha256,
        dependency_paths=dependency_paths,
    )
    probe_identity = _canonical_sha256(probe)
    dependency_identity = _dependency_identity_sha256(probe)
    profile_manifest_sha256 = _canonical_sha256(
        {
            "schema": "scion.cvrp_b0_profile.v3",
            "profile_id": profile.profile_id,
            "source_package_identity_sha256": source_identity_sha256,
            "runtime_snapshot_sha256": runtime_sha256,
            "config_sha256": config_sha256,
            "config_assignments": profile.config_assignments,
            "python_runtime_identity_sha256": (
                python_runtime.runtime_identity_sha256
            ),
            "import_probe_identity_sha256": probe_identity,
            "dependency_identity_sha256": dependency_identity,
        }
    )
    if _inventory_sha256(_snapshot_inventory(staged_package)) != runtime_sha256:
        raise ValueError(f"CVRP B0 import probe mutated runtime: {profile.profile_id}")
    return B0ProfileRuntime(
        profile=profile,
        package_root=package_root,
        workspace=workspace,
        config_path=config_path,
        pythonpath_entries=(str(package_root), *tuple(dependency_paths)),
        runtime_snapshot_sha256=runtime_sha256,
        config_sha256=config_sha256,
        profile_manifest_sha256=profile_manifest_sha256,
        import_probe_json=_canonical_json(probe),
        import_probe_identity_sha256=probe_identity,
        dependency_identity_sha256=dependency_identity,
    )


def _run_import_probe(
    *,
    python_runtime: B0PythonRuntime,
    package_root: Path,
    workspace: Path,
    profile: B0Profile,
    expected_runtime_sha256: str,
    expected_config_sha256: str,
    dependency_paths: Sequence[str],
) -> Mapping[str, Any]:
    script = r'''
import hashlib, importlib.metadata, json, os, stat, sys
from pathlib import Path
import scion
from scion.problems.cvrp import solver
from scion.problems.cvrp.policies.baseline_modules import config

root = Path(os.environ["B0_PACKAGE_ROOT"]).resolve()
package = (root / "scion").resolve()
dependency_roots = [Path(os.path.abspath(value)) for value in
                    json.loads(os.environ["B0_DEPENDENCY_ROOTS_JSON"])]
def inside(path):
    Path(path).resolve().relative_to(root)
def dependency_root(path):
    lexical = Path(os.path.abspath(path))
    for dependency in dependency_roots:
        try:
            lexical.relative_to(dependency)
            return dependency
        except ValueError:
            pass
    return None
def lstat_identity(path):
    observed = os.lstat(path)
    return {
        "device": observed.st_dev,
        "inode": observed.st_ino,
        "mode": observed.st_mode,
        "size": observed.st_size,
        "mtime_ns": observed.st_mtime_ns,
        "ctime_ns": observed.st_ctime_ns,
        "is_symlink": stat.S_ISLNK(observed.st_mode),
    }
def symlink_chain(path):
    lexical = Path(os.path.abspath(path))
    current = Path(lexical.anchor)
    rows = []
    for part in lexical.parts[1:]:
        current = current / part
        identity = lstat_identity(current)
        if identity["is_symlink"]:
            rows.append({
                "path": str(current),
                "link_target": os.readlink(current),
                "lstat": identity,
            })
    return rows
def inventory_sha256():
    rows = []
    for path in sorted(package.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_file():
            rows.append({
                "path": path.relative_to(package).as_posix(),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            })
    raw = json.dumps(rows, ensure_ascii=False, allow_nan=False, sort_keys=True,
                     separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
package_distributions = importlib.metadata.packages_distributions()
dependency_modules = []
for name, module in sorted(sys.modules.items()):
    module_file = getattr(module, "__file__", None)
    if not module_file:
        continue
    lexical_file = Path(os.path.abspath(module_file))
    matched_root = dependency_root(lexical_file)
    resolved_file = lexical_file.resolve()
    if matched_root is None or not resolved_file.is_file():
        continue
    try:
        resolved_file.relative_to(root)
    except ValueError:
        pass
    else:
        raise SystemExit(
            f"dependency module resolves into staged Scion runtime: {name}"
        )
    top_level = name.partition(".")[0]
    distributions = []
    for distribution in sorted(package_distributions.get(top_level, ())):
        try:
            version = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            version = None
        distributions.append({"name": distribution, "version": version})
    module_version = getattr(module, "__version__", None)
    if not isinstance(module_version, (str, int, float, bool, type(None))):
        module_version = str(module_version)
    dependency_modules.append({
        "module": name,
        "lexical_file": str(lexical_file),
        "lexical_lstat": lstat_identity(lexical_file),
        "symlink_chain": symlink_chain(lexical_file),
        "file": str(resolved_file),
        "resolved_target_file": str(resolved_file),
        "file_sha256": hashlib.sha256(resolved_file.read_bytes()).hexdigest(),
        "dependency_root": str(matched_root),
        "module_version": module_version,
        "distributions": distributions,
    })
scion_locations = [str(Path(value).resolve()) for value in scion.__path__]
if scion_locations != [str(package)]:
    raise SystemExit(f"probe namespace mixing: {scion_locations!r}")
for value in scion_locations:
    inside(value)
inside(solver.__file__)
inside(config.__file__)
observed = {
    "python_executable_path": str(Path(sys.executable).resolve()),
    "scion_locations": scion_locations,
    "sys_path": [str(Path(value).resolve()) if value else "" for value in sys.path],
    "solver_file": str(Path(solver.__file__).resolve()),
    "config_file": str(Path(config.__file__).resolve()),
    "SOLVER_VARIANT": config.SOLVER_VARIANT,
    "USE_VNS": config.USE_VNS,
    "ENABLE_INITIAL_VNS": config.ENABLE_INITIAL_VNS,
    "ENABLE_EMBEDDED_VNS": config.ENABLE_EMBEDDED_VNS,
    "ENABLE_SIZE70_TWO_OPT_FALLBACK": config.ENABLE_SIZE70_TWO_OPT_FALLBACK,
    "config_sha256": hashlib.sha256(Path(config.__file__).read_bytes()).hexdigest(),
    "runtime_snapshot_sha256": inventory_sha256(),
    "dependency_modules": dependency_modules,
}
if observed["python_executable_path"] != os.environ["B0_EXPECTED_PYTHON_PATH"]:
    raise SystemExit("probe Python executable realpath mismatch")
expected = json.loads(os.environ["B0_EXPECTED_CONFIG_JSON"])
for key, value in expected.items():
    if observed.get(key) != value:
        raise SystemExit(f"probe mismatch {key}: {observed.get(key)!r} != {value!r}")
if observed["config_sha256"] != os.environ["B0_EXPECTED_CONFIG_SHA256"]:
    raise SystemExit("probe config hash mismatch")
if observed["runtime_snapshot_sha256"] != os.environ["B0_EXPECTED_RUNTIME_SHA256"]:
    raise SystemExit("probe runtime hash mismatch")
print(json.dumps(observed, sort_keys=True, separators=(",", ":")))
'''
    env = os.environ.copy()
    pythonpath_entries = (str(package_root), *tuple(dependency_paths))
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_entries)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["B0_PACKAGE_ROOT"] = str(package_root)
    env["B0_EXPECTED_CONFIG_JSON"] = json.dumps(
        profile.config_assignments,
        sort_keys=True,
        separators=(",", ":"),
    )
    env["B0_EXPECTED_CONFIG_SHA256"] = expected_config_sha256
    env["B0_EXPECTED_RUNTIME_SHA256"] = expected_runtime_sha256
    env["B0_EXPECTED_PYTHON_PATH"] = str(python_runtime.executable_path)
    env["B0_DEPENDENCY_ROOTS_JSON"] = json.dumps(list(dependency_paths))
    completed = subprocess.run(
        [str(python_runtime.executable_path), "-S", "-c", script],
        cwd=str(workspace),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=60,
    )
    if completed.returncode != 0:
        raise ValueError(
            f"CVRP B0 import probe failed for {profile.profile_id}: "
            f"{completed.stderr.strip() or completed.stdout.strip()}"
        )
    payload = json.loads(completed.stdout)
    if not isinstance(payload, dict):
        raise ValueError("CVRP B0 import probe did not return an object")
    return payload


def _dependency_identity_sha256(probe: Mapping[str, Any]) -> str:
    dependencies = probe.get("dependency_modules")
    if not isinstance(dependencies, list):
        raise ValueError("CVRP B0 import probe omitted dependency modules")
    return _canonical_sha256(
        {
            "schema": "scion.cvrp_b0_dependency_identity.v1",
            "modules": dependencies,
        }
    )


def _materialize_input_snapshot(
    *,
    cases: Sequence[CvrpMatrixCase],
    authority_entries: Mapping[str, Mapping[str, Any]],
    source_data_root: Path,
    output_root: Path,
) -> tuple[Path, tuple[tuple[str, str], ...], str]:
    input_root = output_root / "input_snapshot"
    identities: list[tuple[str, str]] = []
    for case in cases:
        relative = Path(case.source_path)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"CVRP B0 input path is unsafe: {relative}")
        current = source_data_root
        for part in relative.parts:
            current = current / part
            if current.is_symlink():
                raise ValueError(
                    f"CVRP B0 input path contains a symlink: {current}"
                )
        source = source_data_root / relative
        source_resolved = source.resolve(strict=True)
        try:
            source_resolved.relative_to(source_data_root)
        except ValueError as exc:
            raise ValueError(f"CVRP B0 input escapes data root: {relative}") from exc
        if not source_resolved.is_file():
            raise ValueError(f"CVRP B0 input is not a regular file: {source}")
        before = _sha256_file(source_resolved)
        target = input_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_resolved, target)
        after = _sha256_file(source_resolved)
        copied = _sha256_file(target)
        if before != after or copied != before:
            raise ValueError(f"CVRP B0 input changed during copy: {case.case_id}")
        if str(authority_entries[case.case_id]["source_path"]) != relative.as_posix():
            raise ValueError(f"CVRP B0 input authority drift: {case.case_id}")
        identities.append((case.case_id, copied))
    _make_tree_read_only(input_root)
    input_identity = _inventory_sha256(_snapshot_inventory(input_root))
    return input_root, tuple(identities), input_identity


def _build_planned_jobs(
    *,
    cases: Sequence[CvrpMatrixCase],
    limits: Mapping[str, int],
    runtimes: Sequence[B0ProfileRuntime],
    input_case_ids: Mapping[str, str],
    output_root: Path,
    protocol_sha256: str,
    manifest_sha256: str,
    input_snapshot_sha256: str,
    python_runtime: B0PythonRuntime,
) -> tuple[tuple[B0PlannedJob, ...], tuple[B0PlannedJob, ...]]:
    runtime_by_id = {runtime.profile.profile_id: runtime for runtime in runtimes}
    mechanisms = tuple(runtime.profile.mechanism_spec() for runtime in runtimes)
    summary: list[B0PlannedJob] = []
    execution: list[B0PlannedJob] = []
    ordinal = 0
    for case in cases:
        for seed_index, seed in enumerate(B0_SEEDS):
            jobs = build_jobs(
                cases=(case,),
                mechanisms=mechanisms,
                seeds=(seed,),
                time_budget_sec=limits[case.case_id],
                output_dir=output_root,
            )
            rotation = seed_index % len(mechanisms)
            rotated = jobs[rotation:] + jobs[:rotation]
            planned_for_pair: dict[str, B0PlannedJob] = {}
            for position, job in enumerate(rotated):
                runtime = runtime_by_id[job.mechanism.mechanism_id]
                preimage = {
                    "schema": "scion.cvrp_b0_job_identity.v2",
                    "matrix_contract": B0_CONTRACT,
                    "job_id": job.job_id,
                    "case": job.case.to_payload(),
                    "seed": job.seed,
                    "profile_id": runtime.profile.profile_id,
                    "selected_surface": B0_SELECTED_SURFACE,
                    "resolved_time_limit_sec": job.time_budget_sec,
                    "protocol_identity_sha256": protocol_sha256,
                    "case_manifest_identity_sha256": manifest_sha256,
                    "runtime_snapshot_sha256": runtime.runtime_snapshot_sha256,
                    "profile_config_sha256": runtime.config_sha256,
                    "profile_manifest_sha256": runtime.profile_manifest_sha256,
                    "import_probe_identity_sha256": runtime.import_probe_identity_sha256,
                    "dependency_identity_sha256": runtime.dependency_identity_sha256,
                    "python_runtime_identity_sha256": (
                        python_runtime.runtime_identity_sha256
                    ),
                    "input_snapshot_identity_sha256": input_snapshot_sha256,
                    "input_case_sha256": input_case_ids[case.case_id],
                    "execution_ordinal": ordinal,
                    "execution_position": position,
                    "rotation_offset": rotation,
                    "order_contract": B0_ORDER_CONTRACT,
                    "outer_timeout_padding_sec": B0_OUTER_TIMEOUT_PADDING_SEC,
                }
                planned = B0PlannedJob(
                    job=job,
                    execution_ordinal=ordinal,
                    execution_position=position,
                    rotation_offset=rotation,
                    runtime=runtime,
                    protocol_identity_sha256=protocol_sha256,
                    case_manifest_identity_sha256=manifest_sha256,
                    input_snapshot_identity_sha256=input_snapshot_sha256,
                    input_case_sha256=input_case_ids[case.case_id],
                    python_executable_path=python_runtime.executable_path,
                    python_runtime_identity_sha256=(
                        python_runtime.runtime_identity_sha256
                    ),
                    job_identity_sha256=_canonical_sha256(preimage),
                )
                execution.append(planned)
                planned_for_pair[job.mechanism.mechanism_id] = planned
                ordinal += 1
            summary.extend(
                planned_for_pair[mechanism.mechanism_id]
                for mechanism in mechanisms
            )
    if len(execution) != 256 or len(summary) != 256:
        raise ValueError("CVRP B0 job population drift")
    return tuple(execution), tuple(summary)


def _snapshot_inventory(
    root: Path,
    *,
    exclude_top_level: frozenset[str] = frozenset(),
) -> tuple[tuple[str, str], ...]:
    resolved = root.resolve(strict=True)
    rows: list[tuple[str, str]] = []
    for path in sorted(resolved.rglob("*"), key=lambda item: item.as_posix()):
        relative = path.relative_to(resolved)
        if relative.parts and relative.parts[0] in exclude_top_level:
            continue
        if any(part in _SNAPSHOT_IGNORED_PARTS for part in relative.parts):
            continue
        if path.is_symlink():
            raise ValueError(f"CVRP B0 snapshot rejects symlink: {relative}")
        if not path.is_file() or path.suffix == ".pyc":
            continue
        rows.append((relative.as_posix(), _sha256_file(path)))
    if not rows:
        raise ValueError(f"CVRP B0 snapshot contains no files: {root}")
    return tuple(rows)


def _copy_inventory(
    *,
    source_root: Path,
    target_root: Path,
    inventory: Sequence[tuple[str, str]],
) -> None:
    for relative_text, expected_sha256 in inventory:
        relative = Path(relative_text)
        source = source_root / relative
        if source.is_symlink():
            raise ValueError(f"CVRP B0 source became a symlink: {relative}")
        before = _sha256_file(source)
        if before != expected_sha256:
            raise ValueError(f"CVRP B0 source changed before copy: {relative}")
        target = target_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        after = _sha256_file(source)
        if after != before or _sha256_file(target) != before:
            raise ValueError(f"CVRP B0 source changed during copy: {relative}")


def _inventory_sha256(inventory: Sequence[tuple[str, str]]) -> str:
    return _canonical_sha256(
        [{"path": path, "sha256": digest} for path, digest in inventory]
    )


def _make_tree_read_only(root: Path) -> None:
    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        if path.is_file():
            path.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
        elif path.is_dir():
            path.chmod(
                stat.S_IRUSR
                | stat.S_IXUSR
                | stat.S_IRGRP
                | stat.S_IXGRP
                | stat.S_IROTH
                | stat.S_IXOTH
            )
    root.chmod(
        stat.S_IRUSR
        | stat.S_IXUSR
        | stat.S_IRGRP
        | stat.S_IXGRP
        | stat.S_IROTH
        | stat.S_IXOTH
    )


def _assert_read_only_tree(root: Path) -> None:
    for path in (root, *root.rglob("*")):
        if path.stat().st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH):
            raise ValueError(f"CVRP B0 immutable snapshot is writable: {path}")


def _replace_boolean_assignment(text: str, name: str, value: bool) -> str:
    lines = text.splitlines()
    matches = [
        index
        for index, line in enumerate(lines)
        if line in (f"{name} = True", f"{name} = False")
    ]
    if len(matches) != 1:
        raise ValueError(f"CVRP B0 boolean config drift: {name}")
    lines[matches[0]] = f"{name} = {'True' if value else 'False'}"
    return "\n".join(lines) + "\n"


def _replace_string_assignment(text: str, name: str, value: str) -> str:
    lines = text.splitlines()
    prefix = f'{name} = "'
    matches = [
        index
        for index, line in enumerate(lines)
        if line.startswith(prefix) and line.endswith('"')
    ]
    if len(matches) != 1:
        raise ValueError(f"CVRP B0 string config drift: {name}")
    lines[matches[0]] = f'{name} = "{value}"'
    return "\n".join(lines) + "\n"


def _canonical_sha256(payload: Any) -> str:
    raw = _canonical_json(payload).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _canonical_json(payload: Any) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_bytes(captured: bytes) -> str:
    return hashlib.sha256(captured).hexdigest()


__all__ = (
    "B0_CONTRACT",
    "B0_ORDER_CONTRACT",
    "B0_OUTER_TIMEOUT_PADDING_SEC",
    "B0_PROFILES",
    "B0_SEEDS",
    "B0_SELECTED_SURFACE",
    "B0_STAGE",
    "B0LaunchPlan",
    "B0PlannedJob",
    "B0Profile",
    "B0ProfileRuntime",
    "B0PythonRuntime",
    "prepare_b0_launch_plan",
    "verify_b0_launch_plan",
)
