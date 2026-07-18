"""Sealed, problem-owned comparison closer for the one-time CVRP B1 matrix.

This module only reads the frozen B1 artifacts and emits diagnostic CVRP
evidence.  It has no dependency on campaign, scheduling, promotion, or generic
decision code.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import stat
import statistics
from typing import Any, Iterable, Mapping, Sequence

from scion.problems.cvrp.evidence import b0_runner_contract as b0_contract

REPORT_SCHEMA = "scion.cvrp_b1_comparison_report.v1"
RECEIPT_SCHEMA = "scion.cvrp_b1_comparison_receipt.v1"
AUTHORITY = "cvrp_problem_owned_diagnostic_evidence_only"
MATRIX_CONTRACT = "scion.cvrp_b0_runner_contract.v3"
ROOT_NAME = "v04-cvrp-b1-mechanism-matrix-20260718T074653Z-claw"
CANONICAL_INPUT_ROOT = f"/home/clawd/research/scion-experiments/{ROOT_NAME}"
DESIGN_PATH = "scion/docs/planning/v0.4/" "v0.4-cvrp-b1-postrun-contract-20260718.md"
DESIGN_SHA256 = "32b38dda34b1c87d6c0bcf41fc92e4782ae0f496aa9817aa32903e122aabbfd6"
INFLIGHT_PATH = (
    "scion/docs/experiments/v0.4/" "v04-cvrp-b1-mechanism-matrix-inflight-20260718.md"
)
INFLIGHT_SHA256 = "03be02d4f8b60456f668b51b617c9d1ea0e1124d0c506e94750bbfc3e8ac3b7d"
MANIFEST_SHA256 = "8e9bf79c58ce1a5b9aa1e18d1d02d828fe2c32823ea2662bd99c96b22a1589b9"
RESULTS_SHA256 = "0e3107c1ff544b0ddfad9578f1f4bc96e1aeac2af42ade05802f12ebd13d3fc0"
CLOSED_RECEIPT_SHA256 = (
    "9b0b0b5eb17b7fed8fb9f38e3013e70038cbe0d2c2d13b056a63caa34a1a2a0c"
)
REPORT_NAME = "cvrp_b1_comparison_report.v1.json"
RECEIPT_NAME = "cvrp_b1_comparison_receipt.v1.json"
CLOSER_SOURCE_PATHS = (
    "scion/scion/problems/cvrp/evidence/b1_comparison.py",
    "scion/scion/problems/cvrp/evidence/b0_runner_contract.py",
    "scion/tools/cvrp_b1_comparison.py",
)

PROFILES = (
    "canonical_alns_vns",
    "pure_alns_no_polish",
    "embedded_vns_disabled",
    "initial_vns_disabled",
)
COMPARISON_PROFILES = PROFILES[1:]
MAIN_COMPARISON_PROFILES = (
    "pure_alns_no_polish",
    "embedded_vns_disabled",
)
VIEW_ORDER = (
    "full_256",
    "normal_priority_boundary_excluded_248",
    "conservative_clean_212",
    "normal_overlap_balanced_32",
)
VIEW_EXPECTED_ROWS = {
    "full_256": 256,
    "normal_priority_boundary_excluded_248": 248,
    "conservative_clean_212": 212,
    "normal_overlap_balanced_32": 32,
}
VERDICTS = (
    "integrity_reject",
    "accepted_conservative_scope",
    "diagnostic_subset_only",
)

_IDENTITY_FIELDS = (
    "matrix_contract",
    "job_identity_sha256",
    "stage",
    "selected_surface",
    "profile_id",
    "profile_config",
    "resolved_time_limit_sec",
    "execution_ordinal",
    "execution_position",
    "rotation_offset",
    "order_contract",
    "outer_timeout_padding_sec",
    "runtime_snapshot_sha256",
    "protocol_identity_sha256",
    "case_manifest_identity_sha256",
    "input_snapshot_identity_sha256",
    "profile_config_sha256",
    "profile_manifest_sha256",
    "import_probe_identity_sha256",
    "dependency_identity_sha256",
    "python_runtime_identity_sha256",
    "input_case_sha256",
)


class CvrpB1ComparisonError(RuntimeError):
    """Raised when sealed B1 evidence or comparison replay is invalid."""


def integrity_reject_verdict(error: BaseException) -> dict[str, Any]:
    """Render the sole fail-closed outcome; rejected inputs emit no artifacts."""

    return {
        "passed": False,
        "classification": "integrity_reject",
        "f1_unlocked": False,
        "comparison_artifacts_emitted": False,
        "error_type": type(error).__name__,
        "error": str(error),
    }


@dataclass(frozen=True)
class ComparisonArtifacts:
    report: dict[str, Any]
    receipt: dict[str, Any]
    report_bytes: bytes
    receipt_bytes: bytes


def repository_root() -> Path:
    return Path(__file__).resolve().parents[5]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    try:
        return sha256_bytes(path.read_bytes())
    except OSError as exc:
        raise CvrpB1ComparisonError(f"cannot read sealed artifact: {path}") from exc


def render_artifact(value: Mapping[str, Any]) -> bytes:
    try:
        return (
            json.dumps(
                value,
                ensure_ascii=False,
                allow_nan=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CvrpB1ComparisonError(
            "comparison artifact is not canonical JSON"
        ) from exc


def _canonical_identity_sha256(domain: str, items: Any) -> str:
    data = json.dumps(
        {"domain": domain, "items": items},
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256_bytes(data)


def _canonical_sha256(value: Any) -> str:
    return sha256_bytes(
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )


def _snapshot_identity(path: Path, *, label: str) -> str:
    try:
        return b0_contract._inventory_sha256(b0_contract._snapshot_inventory(path))
    except (OSError, ValueError) as exc:
        raise CvrpB1ComparisonError(f"{label} snapshot is missing or drifted") from exc


def _reject_json_constant(value: str) -> None:
    raise CvrpB1ComparisonError(f"non-finite JSON constant is forbidden: {value}")


def _load_json_bytes(data: bytes, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(data, parse_constant=_reject_json_constant)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CvrpB1ComparisonError(f"{label} is invalid JSON") from exc
    if not isinstance(value, dict):
        raise CvrpB1ComparisonError(f"{label} must be a JSON object")
    return value


def _load_bound_json(path: Path, expected_sha256: str, *, label: str) -> dict[str, Any]:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise CvrpB1ComparisonError(f"cannot read {label}: {path}") from exc
    observed = sha256_bytes(data)
    if observed != expected_sha256:
        raise CvrpB1ComparisonError(
            f"{label} raw SHA-256 drift: expected {expected_sha256}, observed {observed}"
        )
    return _load_json_bytes(data, label=label)


def _require_mapping(value: Any, *, label: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise CvrpB1ComparisonError(f"{label} must be an object")
    return value


def _require_list(value: Any, *, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise CvrpB1ComparisonError(f"{label} must be a list")
    return value


def _finite_number(value: Any, *, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CvrpB1ComparisonError(f"{label} must be numeric")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise CvrpB1ComparisonError(f"{label} must be finite")
    return numeric


def _exact_int(value: Any, *, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise CvrpB1ComparisonError(f"{label} must be an integer")
    return value


def _profile(row: Mapping[str, Any]) -> str:
    value = row.get("profile_id")
    if value not in PROFILES:
        raise CvrpB1ComparisonError(f"unknown B1 profile: {value!r}")
    return str(value)


def _case_seed(row: Mapping[str, Any]) -> tuple[str, int]:
    case = _require_mapping(row.get("case"), label="job.case")
    case_id = case.get("case_id")
    if not isinstance(case_id, str) or not case_id:
        raise CvrpB1ComparisonError("job case_id is invalid")
    seed = _exact_int(row.get("seed"), label=f"{case_id}.seed")
    return case_id, seed


def overlap_regime(execution_ordinal: int) -> str:
    if 0 <= execution_ordinal <= 173:
        return "clean_before"
    if 174 <= execution_ordinal <= 211:
        return "normal_priority_overlap"
    if 212 <= execution_ordinal <= 215:
        return "reduced_priority_end_unknown"
    if 216 <= execution_ordinal <= 255:
        return "clean_after"
    raise CvrpB1ComparisonError(f"execution ordinal outside B1: {execution_ordinal}")


def _view_quartets(
    rows_by_quartet: Mapping[tuple[str, int], Mapping[str, Mapping[str, Any]]],
) -> dict[str, tuple[tuple[str, int], ...]]:
    all_quartets = tuple(sorted(rows_by_quartet))
    views: dict[str, tuple[tuple[str, int], ...]] = {
        "full_256": all_quartets,
        "normal_priority_boundary_excluded_248": tuple(
            key for key in all_quartets if key not in {("CMT3", 59), ("M-n200-k17", 11)}
        ),
        "conservative_clean_212": tuple(
            key
            for key in all_quartets
            if not any(
                174 <= _exact_int(row["execution_ordinal"], label="ordinal") <= 215
                for row in rows_by_quartet[key].values()
            )
        ),
        "normal_overlap_balanced_32": tuple(
            key for key in all_quartets if key[0] in {"CMT4", "M-n151-k12"}
        ),
    }
    for view_id, quartets in views.items():
        observed = len(quartets) * 4
        if observed != VIEW_EXPECTED_ROWS[view_id]:
            raise CvrpB1ComparisonError(
                f"fixed view {view_id} has {observed} rows, expected "
                f"{VIEW_EXPECTED_ROWS[view_id]}"
            )
    return views


def _validate_integrity(
    root: Path,
    manifest: Mapping[str, Any],
    results: Mapping[str, Any],
    closed_receipt: Mapping[str, Any],
) -> tuple[
    list[Mapping[str, Any]],
    dict[tuple[str, int], dict[str, Mapping[str, Any]]],
    list[dict[str, str]],
]:
    if manifest.get("matrix_contract") != MATRIX_CONTRACT:
        raise CvrpB1ComparisonError("manifest matrix contract drift")
    if manifest.get("dry_run") is not False or results.get("dry_run") is not False:
        raise CvrpB1ComparisonError("B1 closer requires a completed non-dry-run root")
    if manifest.get("output_root") != CANONICAL_INPUT_ROOT:
        raise CvrpB1ComparisonError("manifest does not name the accepted B1 root")
    if results.get("matrix_contract") != MATRIX_CONTRACT:
        raise CvrpB1ComparisonError("results matrix contract drift")
    if results.get("snapshot_verification") != {"status": "passed"}:
        raise CvrpB1ComparisonError("results snapshot verification is not passed")

    execution = _require_list(manifest.get("execution_jobs"), label="execution_jobs")
    jobs = _require_list(manifest.get("jobs"), label="manifest.jobs")
    result_rows = _require_list(results.get("jobs"), label="results.jobs")
    receipt_rows = _require_list(
        closed_receipt.get("raw_results"), label="closed_receipt.raw_results"
    )
    if not all(
        len(items) == 256 for items in (execution, jobs, result_rows, receipt_rows)
    ):
        raise CvrpB1ComparisonError("B1 requires exactly 256 jobs in every authority")

    execution_by_id: dict[str, Mapping[str, Any]] = {}
    for index, raw in enumerate(execution):
        row = _require_mapping(raw, label=f"execution_jobs[{index}]")
        job_id = row.get("job_id")
        if not isinstance(job_id, str) or job_id in execution_by_id:
            raise CvrpB1ComparisonError("execution job id is missing or duplicated")
        if row.get("execution_ordinal") != index:
            raise CvrpB1ComparisonError("execution ordinals are not continuous 0..255")
        job_preimage = {
            "schema": "scion.cvrp_b0_job_identity.v2",
            "matrix_contract": MATRIX_CONTRACT,
            "job_id": job_id,
            "case": row.get("case"),
            "seed": row.get("seed"),
            "profile_id": row.get("profile_id"),
            "selected_surface": row.get("selected_surface"),
            "resolved_time_limit_sec": row.get("resolved_time_limit_sec"),
            "protocol_identity_sha256": row.get("protocol_identity_sha256"),
            "case_manifest_identity_sha256": row.get("case_manifest_identity_sha256"),
            "runtime_snapshot_sha256": row.get("runtime_snapshot_sha256"),
            "profile_config_sha256": row.get("profile_config_sha256"),
            "profile_manifest_sha256": row.get("profile_manifest_sha256"),
            "import_probe_identity_sha256": row.get("import_probe_identity_sha256"),
            "dependency_identity_sha256": row.get("dependency_identity_sha256"),
            "python_runtime_identity_sha256": row.get("python_runtime_identity_sha256"),
            "input_snapshot_identity_sha256": row.get("input_snapshot_identity_sha256"),
            "input_case_sha256": row.get("input_case_sha256"),
            "execution_ordinal": row.get("execution_ordinal"),
            "execution_position": row.get("execution_position"),
            "rotation_offset": row.get("rotation_offset"),
            "order_contract": row.get("order_contract"),
            "outer_timeout_padding_sec": row.get("outer_timeout_padding_sec"),
        }
        if _canonical_sha256(job_preimage) != row.get("job_identity_sha256"):
            raise CvrpB1ComparisonError(f"job identity derivation drift: {job_id}")
        execution_by_id[job_id] = row

    manifest_by_id: dict[str, Mapping[str, Any]] = {}
    for raw in jobs:
        row = _require_mapping(raw, label="manifest job")
        job_id = row.get("job_id")
        if not isinstance(job_id, str) or job_id in manifest_by_id:
            raise CvrpB1ComparisonError("manifest job id is missing or duplicated")
        manifest_by_id[job_id] = row
    if set(manifest_by_id) != set(execution_by_id):
        raise CvrpB1ComparisonError("manifest and execution job identities differ")
    for job_id, row in execution_by_id.items():
        if manifest_by_id[job_id] != row:
            raise CvrpB1ComparisonError(f"manifest job payload drift: {job_id}")

    if closed_receipt.get("schema") != "scion.cvrp_b0_matrix_receipt.v1":
        raise CvrpB1ComparisonError("closed receipt schema drift")
    expected_receipt_scalars = {
        "status": "closed",
        "matrix_contract": MATRIX_CONTRACT,
        "job_count": 256,
        "manifest_sha256": MANIFEST_SHA256,
        "results_sha256": RESULTS_SHA256,
    }
    if any(
        closed_receipt.get(key) != value
        for key, value in expected_receipt_scalars.items()
    ):
        raise CvrpB1ComparisonError("closed receipt authority scalar drift")
    authority = _require_mapping(manifest.get("authority"), label="manifest.authority")
    protocol_authority = _require_mapping(
        authority.get("protocol"), label="manifest.authority.protocol"
    )
    case_authority = _require_mapping(
        authority.get("case_manifest"), label="manifest.authority.case_manifest"
    )
    snapshot_authority = _require_mapping(
        authority.get("authority_snapshot"), label="manifest.authority.snapshot"
    )
    input_authority = _require_mapping(
        authority.get("input_snapshot"), label="manifest.authority.input"
    )
    source_authority = _require_mapping(
        authority.get("source_package"), label="manifest.authority.source_package"
    )
    python_runtime = _require_mapping(
        manifest.get("python_runtime"), label="manifest.python_runtime"
    )
    authority_receipt_pairs = {
        "protocol_identity_sha256": protocol_authority.get("sha256"),
        "case_manifest_identity_sha256": case_authority.get("sha256"),
        "authority_snapshot_identity_sha256": snapshot_authority.get("sha256"),
        "input_snapshot_identity_sha256": input_authority.get("sha256"),
        "python_runtime_identity_sha256": python_runtime.get("runtime_identity_sha256"),
    }
    if any(
        closed_receipt.get(field) != expected
        for field, expected in authority_receipt_pairs.items()
    ):
        raise CvrpB1ComparisonError("closed receipt does not bind manifest authorities")
    profile_rows = _require_list(manifest.get("profiles"), label="manifest.profiles")
    if len(profile_rows) != 4:
        raise CvrpB1ComparisonError("manifest must have exactly four profiles")
    profile_by_id: dict[str, Mapping[str, Any]] = {}
    workspaces: set[str] = set()
    package_roots: set[str] = set()
    for raw_profile in profile_rows:
        profile_row = _require_mapping(raw_profile, label="manifest profile")
        profile_id = profile_row.get("profile_id")
        workspace = profile_row.get("workspace")
        package_root = profile_row.get("package_root")
        if (
            profile_id not in PROFILES
            or profile_id in profile_by_id
            or not isinstance(workspace, str)
            or not isinstance(package_root, str)
        ):
            raise CvrpB1ComparisonError("manifest profile identity is invalid")
        profile_by_id[str(profile_id)] = profile_row
        workspaces.add(workspace)
        package_roots.add(package_root)
    if (
        set(profile_by_id) != set(PROFILES)
        or len(workspaces) != 4
        or len(package_roots) != 4
    ):
        raise CvrpB1ComparisonError("profile workspace reuse or profile identity drift")
    expected_profiles = {
        profile.profile_id: profile for profile in b0_contract.B0_PROFILES
    }
    for profile_id in PROFILES:
        profile_row = profile_by_id[profile_id]
        expected_profile = expected_profiles[profile_id]
        if (
            profile_row.get("config_assignments") != expected_profile.config_assignments
            or profile_row.get("mechanism_family") != expected_profile.mechanism_family
            or profile_row.get("mechanism_slice") != expected_profile.mechanism_slice
        ):
            raise CvrpB1ComparisonError(
                f"profile scientific definition drift: {profile_id}"
            )
    dependency_identities = _require_mapping(
        closed_receipt.get("dependency_identities"),
        label="closed_receipt.dependency_identities",
    )
    if dict(dependency_identities) != {
        profile: profile_by_id[profile].get("dependency_identity_sha256")
        for profile in PROFILES
    }:
        raise CvrpB1ComparisonError("closed receipt dependency identities drift")
    expected_authority_paths = {
        "authority_snapshot": str(Path(CANONICAL_INPUT_ROOT) / "authority_snapshot"),
        "input_snapshot": str(Path(CANONICAL_INPUT_ROOT) / "input_snapshot"),
        "protocol": str(
            Path(CANONICAL_INPUT_ROOT) / "authority_snapshot" / "protocol.yaml"
        ),
        "case_manifest": str(
            Path(CANONICAL_INPUT_ROOT) / "authority_snapshot" / "screening.json"
        ),
    }
    if (
        snapshot_authority.get("path") != expected_authority_paths["authority_snapshot"]
        or input_authority.get("path") != expected_authority_paths["input_snapshot"]
        or protocol_authority.get("snapshot_path")
        != expected_authority_paths["protocol"]
        or case_authority.get("snapshot_path")
        != expected_authority_paths["case_manifest"]
    ):
        raise CvrpB1ComparisonError("manifest snapshot paths drift from accepted root")
    if (
        _snapshot_identity(root / "authority_snapshot", label="authority")
        != snapshot_authority.get("sha256")
        or sha256_file(root / "authority_snapshot" / "protocol.yaml")
        != protocol_authority.get("sha256")
        or sha256_file(root / "authority_snapshot" / "screening.json")
        != case_authority.get("sha256")
        or _snapshot_identity(root / "input_snapshot", label="input")
        != input_authority.get("sha256")
    ):
        raise CvrpB1ComparisonError("authority or input snapshot digest drift")
    input_case_hashes = _require_mapping(
        input_authority.get("case_sha256"), label="input case SHA-256 map"
    )
    cases = _require_list(manifest.get("cases"), label="manifest.cases")
    observed_case_hashes: dict[str, str] = {}
    for raw_case in cases:
        case = _require_mapping(raw_case, label="manifest case")
        case_id = case.get("case_id")
        relative_path = case.get("path")
        if not isinstance(case_id, str) or not isinstance(relative_path, str):
            raise CvrpB1ComparisonError("manifest case identity is invalid")
        observed_case_hashes[case_id] = sha256_file(
            root / "input_snapshot" / relative_path
        )
    if observed_case_hashes != dict(input_case_hashes):
        raise CvrpB1ComparisonError("input case byte identities drift")
    for profile in PROFILES:
        profile_row = profile_by_id[profile]
        package_root = root / "runtime_snapshots" / profile / "package"
        workspace = package_root / "scion" / "problems" / "cvrp"
        config_path = workspace / "policies" / "baseline_modules" / "config.py"
        if (
            profile_row.get("package_root")
            != str(
                Path(CANONICAL_INPUT_ROOT) / "runtime_snapshots" / profile / "package"
            )
            or profile_row.get("workspace")
            != str(
                Path(CANONICAL_INPUT_ROOT)
                / "runtime_snapshots"
                / profile
                / "package"
                / "scion"
                / "problems"
                / "cvrp"
            )
            or profile_row.get("config_path")
            != str(
                Path(CANONICAL_INPUT_ROOT)
                / "runtime_snapshots"
                / profile
                / "package"
                / "scion"
                / "problems"
                / "cvrp"
                / "policies"
                / "baseline_modules"
                / "config.py"
            )
        ):
            raise CvrpB1ComparisonError(f"profile snapshot path drift: {profile}")
        if _snapshot_identity(
            package_root / "scion", label=f"runtime {profile}"
        ) != profile_row.get("runtime_snapshot_sha256") or sha256_file(
            config_path
        ) != profile_row.get(
            "config_sha256"
        ):
            raise CvrpB1ComparisonError(
                f"profile runtime/config digest drift: {profile}"
            )
        import_probe = _require_mapping(
            profile_row.get("import_probe"), label=f"{profile}.import_probe"
        )
        if _canonical_sha256(import_probe) != profile_row.get(
            "import_probe_identity_sha256"
        ):
            raise CvrpB1ComparisonError(
                f"profile import-probe identity drift: {profile}"
            )
        try:
            dependency_identity = b0_contract._dependency_identity_sha256(import_probe)
        except ValueError as exc:
            raise CvrpB1ComparisonError(
                f"profile dependency identity is invalid: {profile}"
            ) from exc
        if dependency_identity != profile_row.get("dependency_identity_sha256"):
            raise CvrpB1ComparisonError(f"profile dependency identity drift: {profile}")
        expected_profile_manifest = _canonical_sha256(
            {
                "schema": "scion.cvrp_b0_profile.v3",
                "profile_id": profile,
                "source_package_identity_sha256": source_authority.get("sha256"),
                "runtime_snapshot_sha256": profile_row.get("runtime_snapshot_sha256"),
                "config_sha256": profile_row.get("config_sha256"),
                "config_assignments": profile_row.get("config_assignments"),
                "python_runtime_identity_sha256": python_runtime.get(
                    "runtime_identity_sha256"
                ),
                "import_probe_identity_sha256": profile_row.get(
                    "import_probe_identity_sha256"
                ),
                "dependency_identity_sha256": profile_row.get(
                    "dependency_identity_sha256"
                ),
            }
        )
        if expected_profile_manifest != profile_row.get("profile_manifest_sha256"):
            raise CvrpB1ComparisonError(f"profile manifest derivation drift: {profile}")

    for job_id, row in execution_by_id.items():
        profile_id = row.get("profile_id")
        if profile_id not in profile_by_id:
            raise CvrpB1ComparisonError(f"job profile is not declared: {job_id}")
        profile_authority = profile_by_id[str(profile_id)]
        case_id, _seed = _case_seed(row)
        job_authority_fields = {
            "matrix_contract": MATRIX_CONTRACT,
            "stage": "screening",
            "selected_surface": "solver_design",
            "profile_config": profile_authority.get("config_assignments"),
            "runtime_snapshot_sha256": profile_authority.get("runtime_snapshot_sha256"),
            "protocol_identity_sha256": protocol_authority.get("sha256"),
            "case_manifest_identity_sha256": case_authority.get("sha256"),
            "input_snapshot_identity_sha256": input_authority.get("sha256"),
            "profile_config_sha256": profile_authority.get("config_sha256"),
            "profile_manifest_sha256": profile_authority.get("profile_manifest_sha256"),
            "import_probe_identity_sha256": profile_authority.get(
                "import_probe_identity_sha256"
            ),
            "dependency_identity_sha256": profile_authority.get(
                "dependency_identity_sha256"
            ),
            "python_runtime_identity_sha256": python_runtime.get(
                "runtime_identity_sha256"
            ),
            "input_case_sha256": input_case_hashes.get(case_id),
            "order_contract": "scion.cvrp_b0_latin_rotation.v1",
            "outer_timeout_padding_sec": 60,
        }
        if any(
            row.get(field) != expected
            for field, expected in job_authority_fields.items()
        ):
            raise CvrpB1ComparisonError(f"job authority cross-check drift: {job_id}")
        if row.get("time_budget_sec") != row.get("resolved_time_limit_sec"):
            raise CvrpB1ComparisonError(f"job scientific limit alias drift: {job_id}")

    result_by_id: dict[str, Mapping[str, Any]] = {}
    raw_identities: list[dict[str, str]] = []
    receipt_by_id: dict[str, Mapping[str, Any]] = {}
    for item in receipt_rows:
        receipt_row = _require_mapping(item, label="closed receipt raw result")
        job_id = receipt_row.get("job_id")
        if not isinstance(job_id, str) or job_id in receipt_by_id:
            raise CvrpB1ComparisonError(
                "closed receipt job id is missing or duplicated"
            )
        receipt_by_id[job_id] = receipt_row

    for raw_result in result_rows:
        row = _require_mapping(raw_result, label="result job")
        job_id = row.get("job_id")
        if not isinstance(job_id, str) or job_id in result_by_id:
            raise CvrpB1ComparisonError("result job id is missing or duplicated")
        planned = execution_by_id.get(job_id)
        receipt_row = receipt_by_id.get(job_id)
        if planned is None or receipt_row is None:
            raise CvrpB1ComparisonError(f"unplanned or unreceipted result: {job_id}")
        for field in _IDENTITY_FIELDS:
            if row.get(field) != planned.get(field):
                raise CvrpB1ComparisonError(f"result identity drift {job_id}: {field}")
        if row.get("mechanism_id") != planned.get("mechanism_id"):
            raise CvrpB1ComparisonError(f"mechanism identity drift: {job_id}")
        if row.get("case") != planned.get("case") or row.get("seed") != planned.get(
            "seed"
        ):
            raise CvrpB1ComparisonError(f"case/seed identity drift: {job_id}")
        if row.get("status") != "completed" or row.get("returncode") != 0:
            raise CvrpB1ComparisonError(f"job did not complete successfully: {job_id}")

        output_path = planned.get("output_path")
        if (
            not isinstance(output_path, str)
            or Path(output_path).name != f"{job_id}.json"
        ):
            raise CvrpB1ComparisonError(f"raw output path drift: {job_id}")
        raw_path = root / "raw" / f"{job_id}.json"
        try:
            raw_mode = raw_path.lstat().st_mode
            if not stat.S_ISREG(raw_mode):
                raise CvrpB1ComparisonError(
                    f"raw result is not a regular non-symlink file: {job_id}"
                )
            raw_bytes = raw_path.read_bytes()
        except OSError as exc:
            raise CvrpB1ComparisonError(f"missing raw result: {job_id}") from exc
        raw_sha = sha256_bytes(raw_bytes)
        expected_raw_identity = {
            "job_id": job_id,
            "job_identity_sha256": planned.get("job_identity_sha256"),
            "raw_sha256": raw_sha,
        }
        if dict(receipt_row) != expected_raw_identity:
            raise CvrpB1ComparisonError(f"raw receipt identity drift: {job_id}")
        raw_payload = _load_json_bytes(raw_bytes, label=f"raw result {job_id}")
        if raw_payload.get("job_identity_sha256") != planned.get("job_identity_sha256"):
            raise CvrpB1ComparisonError(f"raw job identity drift: {job_id}")
        if raw_payload.get("matrix_contract") != MATRIX_CONTRACT:
            raise CvrpB1ComparisonError(f"raw matrix contract drift: {job_id}")
        raw_job = _require_mapping(raw_payload.get("b0_job"), label=f"{job_id}.b0_job")
        expected_raw_job = {field: planned.get(field) for field in _IDENTITY_FIELDS}
        if dict(raw_job) != expected_raw_job:
            raise CvrpB1ComparisonError(f"raw frozen job payload drift: {job_id}")
        if raw_payload.get("feasible") is not True:
            raise CvrpB1ComparisonError(f"raw solution is not feasible: {job_id}")
        raw_objective = _require_mapping(
            raw_payload.get("objective"), label=f"{job_id}.objective"
        )
        quality = _require_mapping(row.get("quality"), label=f"{job_id}.quality")
        if quality.get("objective") != raw_objective:
            raise CvrpB1ComparisonError(f"result/raw objective mismatch: {job_id}")
        fleet = _finite_number(quality.get("fleet_violation"), label=f"{job_id}.fleet")
        if (
            fleet != 0.0
            or _finite_number(raw_objective.get("fleet_violation"), label="raw fleet")
            != 0.0
        ):
            raise CvrpB1ComparisonError(f"fleet violation is nonzero: {job_id}")
        for field in ("total_distance", "bks", "bks_gap_pct"):
            _finite_number(quality.get(field), label=f"{job_id}.quality.{field}")
        _exact_int(quality.get("route_count"), label=f"{job_id}.route_count")
        runtime = _require_mapping(
            row.get("runtime_phase_split"), label=f"{job_id}.runtime_phase_split"
        )
        if (
            runtime.get("solver_algorithm_stop_reason") != "time_limit"
            or runtime.get("solver_algorithm_runtime_budget_hit") is not True
        ):
            raise CvrpB1ComparisonError(
                f"internal solver stop contract drift: {job_id}"
            )
        _finite_number(runtime.get("runtime_elapsed_sec"), label=f"{job_id}.runtime")
        _finite_number(
            runtime.get("solver_algorithm_elapsed_ms"), label=f"{job_id}.solver_ms"
        )
        _validate_telemetry(row, job_id=job_id)
        result_by_id[job_id] = row
        raw_identities.append(expected_raw_identity)

    if set(result_by_id) != set(execution_by_id):
        raise CvrpB1ComparisonError("result identity set differs from manifest")
    if [row.get("job_id") for row in result_rows] != [
        row.get("job_id") for row in receipt_rows
    ]:
        raise CvrpB1ComparisonError("result and raw receipt order differs")
    expected_raw_names = {f"{job_id}.json" for job_id in execution_by_id}
    try:
        raw_entries = list((root / "raw").iterdir())
    except OSError as exc:
        raise CvrpB1ComparisonError("raw directory is missing or unreadable") from exc
    observed_raw_names = {path.name for path in raw_entries}
    if observed_raw_names != expected_raw_names:
        raise CvrpB1ComparisonError("raw directory has missing or extra entries")
    if any(not stat.S_ISREG(path.lstat().st_mode) for path in raw_entries):
        raise CvrpB1ComparisonError("raw directory contains a non-regular entry")

    profile_counts = Counter(_profile(row) for row in result_by_id.values())
    if profile_counts != Counter({profile: 64 for profile in PROFILES}):
        raise CvrpB1ComparisonError("profile cardinality is not exactly 64 each")
    position_counts = Counter(
        (_profile(row), _exact_int(row.get("execution_position"), label="position"))
        for row in result_by_id.values()
    )
    if position_counts != Counter(
        {(profile, position): 16 for profile in PROFILES for position in range(4)}
    ):
        raise CvrpB1ComparisonError("profile-position Latin balance is invalid")
    limits = Counter(
        _exact_int(row.get("resolved_time_limit_sec"), label="resolved limit")
        for row in result_by_id.values()
    )
    if limits != Counter({30: 192, 45: 64}):
        raise CvrpB1ComparisonError("scientific limit cardinality drift")

    rows_by_quartet: dict[tuple[str, int], dict[str, Mapping[str, Any]]] = defaultdict(
        dict
    )
    for row in result_by_id.values():
        key = _case_seed(row)
        profile = _profile(row)
        if profile in rows_by_quartet[key]:
            raise CvrpB1ComparisonError(f"duplicate profile in quartet: {key}")
        rows_by_quartet[key][profile] = row
    if len(rows_by_quartet) != 64 or any(
        tuple(items) != PROFILES for items in rows_by_quartet.values()
    ):
        # Dict insertion order is not authority; the set check below is.
        if any(set(items) != set(PROFILES) for items in rows_by_quartet.values()):
            raise CvrpB1ComparisonError("case-seed quartets are incomplete")
    if any(len(items) != 4 for items in rows_by_quartet.values()):
        raise CvrpB1ComparisonError("case-seed quartets are not exactly four profiles")
    return list(result_by_id.values()), dict(rows_by_quartet), raw_identities


def _validate_telemetry(row: Mapping[str, Any], *, job_id: str) -> None:
    accepted = _require_mapping(row.get("accepted_moves"), label=f"{job_id}.accepted")
    for field in (
        "total",
        "move_attempts",
        "improving_moves",
        "neutral_accepted_moves",
    ):
        value = _exact_int(accepted.get(field), label=f"{job_id}.accepted.{field}")
        if value < 0:
            raise CvrpB1ComparisonError(f"negative accepted-move telemetry: {job_id}")
    best = _require_mapping(row.get("best_update_telemetry"), label=f"{job_id}.best")
    if _exact_int(best.get("best_update_count"), label=f"{job_id}.best count") < 0:
        raise CvrpB1ComparisonError(f"negative best-update telemetry: {job_id}")
    phase = _require_mapping(row.get("phase_telemetry"), label=f"{job_id}.phase")
    trace = _require_list(phase.get("alns_iteration_trace"), label=f"{job_id}.trace")
    for index, item in enumerate(trace):
        point = _require_mapping(item, label=f"{job_id}.trace[{index}]")
        _exact_int(point.get("iteration"), label=f"{job_id}.trace.iteration")
        _finite_number(point.get("q"), label=f"{job_id}.trace.q")
        if point.get("accepted") not in {True, False} or point.get(
            "best_improved"
        ) not in {True, False}:
            raise CvrpB1ComparisonError(f"invalid acceptance trace boolean: {job_id}")
        if not isinstance(point.get("acceptance_reason"), str):
            raise CvrpB1ComparisonError(f"invalid acceptance reason: {job_id}")


def _stats(values: Iterable[float]) -> dict[str, float | int | None]:
    items = [float(value) for value in values]
    if not items:
        return {"count": 0, "mean": None, "median": None, "min": None, "max": None}
    if not all(math.isfinite(value) for value in items):
        raise CvrpB1ComparisonError("aggregate input contains a non-finite value")
    return {
        "count": len(items),
        "mean": statistics.fmean(items),
        "median": statistics.median(items),
        "min": min(items),
        "max": max(items),
    }


def _row_measurements(row: Mapping[str, Any]) -> dict[str, Any]:
    quality = _require_mapping(row["quality"], label="quality")
    runtime = _require_mapping(row["runtime_phase_split"], label="runtime")
    phase_ms = _require_mapping(
        runtime.get("phase_runtime_ms"), label="phase_runtime_ms"
    )
    accepted = _require_mapping(row["accepted_moves"], label="accepted_moves")
    best = _require_mapping(row["best_update_telemetry"], label="best updates")
    trace = _require_list(
        _require_mapping(row["phase_telemetry"], label="phase telemetry").get(
            "alns_iteration_trace"
        ),
        label="iteration trace",
    )
    solver_sec = (
        _finite_number(runtime["solver_algorithm_elapsed_ms"], label="solver ms")
        / 1000.0
    )
    if solver_sec <= 0:
        raise CvrpB1ComparisonError("solver elapsed time must be positive")
    iterations = len(trace)
    move_attempts = _exact_int(accepted["move_attempts"], label="move attempts")
    best_count = _exact_int(best["best_update_count"], label="best update count")
    initial_ms = _finite_number(phase_ms.get("vns_initial", 0), label="initial VNS ms")
    embedded_ms = _finite_number(
        phase_ms.get("vns_embedded", 0), label="embedded VNS ms"
    )
    residual_alns_ms = _finite_number(
        phase_ms.get("alns_core", 0), label="ALNS core ms"
    )
    return {
        "total_distance": _finite_number(quality["total_distance"], label="distance"),
        "bks_gap_pct": _finite_number(quality["bks_gap_pct"], label="BKS gap"),
        "route_count": _exact_int(quality["route_count"], label="route count"),
        "bks_routes": _exact_int(quality["bks_routes"], label="BKS routes"),
        "fleet_violation": _finite_number(
            quality["fleet_violation"], label="fleet violation"
        ),
        "solver_elapsed_sec": solver_sec,
        "alns_iterations": iterations,
        "alns_iterations_per_sec": iterations / solver_sec,
        "move_attempts": move_attempts,
        "move_attempts_per_sec": move_attempts / solver_sec,
        "initial_vns_ms": initial_ms,
        "embedded_vns_ms": embedded_ms,
        "residual_alns_ms": residual_alns_ms,
        "best_update_count": best_count,
        "best_updates_per_1000_iterations": (
            1000.0 * best_count / iterations if iterations else 0.0
        ),
        "accepted_moves": _exact_int(accepted["total"], label="accepted total"),
        "improving_moves": _exact_int(
            accepted["improving_moves"], label="improving moves"
        ),
        "acceptance_rate": (
            _exact_int(accepted["total"], label="accepted total") / move_attempts
            if move_attempts
            else 0.0
        ),
        "improving_rate": (
            _exact_int(accepted["improving_moves"], label="improving moves")
            / move_attempts
            if move_attempts
            else 0.0
        ),
        "trace": trace,
    }


def _compact_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    measured = [_row_measurements(row) for row in rows]
    reasons: Counter[str] = Counter()
    trace_accepted = 0
    trace_best = 0
    q_values: list[float] = []
    for item in measured:
        for point in item["trace"]:
            reasons[str(point["acceptance_reason"])] += 1
            trace_accepted += int(point["accepted"] is True)
            trace_best += int(point["best_improved"] is True)
            q_values.append(float(point["q"]))
    return {
        "row_count": len(rows),
        "bks_gap_pct": _stats(item["bks_gap_pct"] for item in measured),
        "total_distance": _stats(item["total_distance"] for item in measured),
        "feasible_route_fleet_count": len(rows),
        "route_count_within_bks_count": sum(
            item["route_count"] <= item["bks_routes"] for item in measured
        ),
        "fleet_valid_count": sum(item["fleet_violation"] == 0 for item in measured),
        "alns_iterations": _stats(item["alns_iterations"] for item in measured),
        "alns_iterations_per_sec": _stats(
            item["alns_iterations_per_sec"] for item in measured
        ),
        "move_attempts_per_sec": _stats(
            item["move_attempts_per_sec"] for item in measured
        ),
        "initial_vns_ms": _stats(item["initial_vns_ms"] for item in measured),
        "embedded_vns_ms": _stats(item["embedded_vns_ms"] for item in measured),
        "residual_alns_ms": _stats(item["residual_alns_ms"] for item in measured),
        "best_update_count": _stats(item["best_update_count"] for item in measured),
        "best_updates_per_1000_iterations": _stats(
            item["best_updates_per_1000_iterations"] for item in measured
        ),
        "accepted_moves": _stats(item["accepted_moves"] for item in measured),
        "improving_moves": _stats(item["improving_moves"] for item in measured),
        "acceptance_rate": _stats(item["acceptance_rate"] for item in measured),
        "improving_rate": _stats(item["improving_rate"] for item in measured),
        "trajectory": {
            "trace_point_count": sum(len(item["trace"]) for item in measured),
            "accepted_trace_point_count": trace_accepted,
            "best_improved_trace_point_count": trace_best,
            "acceptance_reason_counts": dict(sorted(reasons.items())),
            "destroy_size_q": _stats(q_values),
            "sa_note": (
                "The sealed trace exposes iteration-based acceptance outcomes but "
                "not temperature values; profile throughput therefore changes the "
                "iteration/temperature path and is not a pure wall-time VNS effect."
            ),
        },
    }


def _profile_group_value(row: Mapping[str, Any], dimension: str) -> str:
    case = _require_mapping(row["case"], label="case")
    if dimension == "case":
        return str(case["case_id"])
    if dimension == "size":
        return str(case["case_slice"])
    if dimension == "seed":
        return str(row["seed"])
    if dimension == "execution_position":
        return str(row["execution_position"])
    if dimension == "exposure_regime":
        return overlap_regime(int(row["execution_ordinal"]))
    raise AssertionError(dimension)


def _profile_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    summary = _compact_summary(rows)
    heterogeneity: dict[str, dict[str, Any]] = {}
    for dimension in ("case", "size", "seed", "execution_position", "exposure_regime"):
        grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
        for row in rows:
            grouped[_profile_group_value(row, dimension)].append(row)
        heterogeneity[dimension] = {
            key: _compact_summary(items) for key, items in sorted(grouped.items())
        }
    summary["heterogeneity"] = heterogeneity
    return summary


def _lexicographic_quality_outcome(
    canonical_quality: Mapping[str, Any],
    profile_quality: Mapping[str, Any],
) -> str:
    """Compare the exact CVRP objective: fleet(0.0), then distance(0.001)."""

    canonical_fleet = _finite_number(
        canonical_quality.get("fleet_violation"), label="canonical fleet violation"
    )
    profile_fleet = _finite_number(
        profile_quality.get("fleet_violation"), label="profile fleet violation"
    )
    if profile_fleet < canonical_fleet:
        return "profile_better"
    if profile_fleet > canonical_fleet:
        return "canonical_better"
    canonical_distance = _finite_number(
        canonical_quality.get("total_distance"), label="canonical distance"
    )
    profile_distance = _finite_number(
        profile_quality.get("total_distance"), label="profile distance"
    )
    distance_delta = profile_distance - canonical_distance
    if distance_delta < -0.001:
        return "profile_better"
    if distance_delta > 0.001:
        return "canonical_better"
    return "tie"


def _pair_measurement(
    canonical: Mapping[str, Any], candidate: Mapping[str, Any]
) -> dict[str, Any]:
    left = _row_measurements(canonical)
    right = _row_measurements(candidate)
    outcome = _lexicographic_quality_outcome(
        _require_mapping(canonical["quality"], label="canonical quality"),
        _require_mapping(candidate["quality"], label="profile quality"),
    )
    return {
        "case": str(_require_mapping(candidate["case"], label="case")["case_id"]),
        "size": str(_require_mapping(candidate["case"], label="case")["case_slice"]),
        "seed": str(candidate["seed"]),
        "candidate_execution_position": str(candidate["execution_position"]),
        "canonical_execution_position": str(canonical["execution_position"]),
        "exposure_regime": (
            f"canonical={overlap_regime(int(canonical['execution_ordinal']))};"
            f"candidate={overlap_regime(int(candidate['execution_ordinal']))}"
        ),
        "outcome": outcome,
        "distance_delta_candidate_minus_canonical": (
            right["total_distance"] - left["total_distance"]
        ),
        "bks_gap_delta_candidate_minus_canonical": (
            right["bks_gap_pct"] - left["bks_gap_pct"]
        ),
        "iterations_per_sec_delta_candidate_minus_canonical": (
            right["alns_iterations_per_sec"] - left["alns_iterations_per_sec"]
        ),
        "attempts_per_sec_delta_candidate_minus_canonical": (
            right["move_attempts_per_sec"] - left["move_attempts_per_sec"]
        ),
    }


def _paired_compact(items: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    outcomes = Counter(str(item["outcome"]) for item in items)
    return {
        "pair_count": len(items),
        "lexicographic_outcomes": {
            "canonical_better": outcomes["canonical_better"],
            "profile_better": outcomes["profile_better"],
            "ties": outcomes["tie"],
        },
        "distance_delta_candidate_minus_canonical": _stats(
            float(item["distance_delta_candidate_minus_canonical"]) for item in items
        ),
        "bks_gap_delta_candidate_minus_canonical": _stats(
            float(item["bks_gap_delta_candidate_minus_canonical"]) for item in items
        ),
        "iterations_per_sec_delta_candidate_minus_canonical": _stats(
            float(item["iterations_per_sec_delta_candidate_minus_canonical"])
            for item in items
        ),
        "attempts_per_sec_delta_candidate_minus_canonical": _stats(
            float(item["attempts_per_sec_delta_candidate_minus_canonical"])
            for item in items
        ),
    }


def _case_estimands(items: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for item in items:
        grouped[str(item["case"])].append(item)
    estimates: list[dict[str, Any]] = []
    for case_id, pairs in sorted(grouped.items()):
        ordered = sorted(pairs, key=lambda item: int(str(item["seed"])))
        outcomes = Counter(str(item["outcome"]) for item in ordered)
        canonical = outcomes["canonical_better"]
        profile = outcomes["profile_better"]
        outcome = (
            "canonical_better"
            if canonical > profile
            else "profile_better" if profile > canonical else "tie"
        )
        estimates.append(
            {
                "case_id": case_id,
                "retained_seeds": [int(str(item["seed"])) for item in ordered],
                "seed_outcomes": {
                    "canonical_better": canonical,
                    "profile_better": profile,
                    "ties": outcomes["tie"],
                },
                "case_outcome": outcome,
                "median_distance_delta_profile_minus_canonical": statistics.median(
                    float(item["distance_delta_candidate_minus_canonical"])
                    for item in ordered
                ),
                "median_bks_gap_delta_profile_minus_canonical": statistics.median(
                    float(item["bks_gap_delta_candidate_minus_canonical"])
                    for item in ordered
                ),
            }
        )
    return estimates


def _case_equal_weighted(estimates: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    outcomes = Counter(str(item["case_outcome"]) for item in estimates)
    canonical = outcomes["canonical_better"]
    profile = outcomes["profile_better"]
    median_distance = statistics.median(
        float(item["median_distance_delta_profile_minus_canonical"])
        for item in estimates
    )
    difference = canonical - profile
    direction = (
        "canonical_better"
        if difference > 0 or (difference == 0 and median_distance > 0)
        else (
            "profile_better"
            if difference < 0 or (difference == 0 and median_distance < 0)
            else "tie"
        )
    )
    return {
        "case_count": len(estimates),
        "case_canonical_better": canonical,
        "case_profile_better": profile,
        "case_ties": outcomes["tie"],
        "canonical_case_win_rate": canonical / len(estimates),
        "median_case_distance_delta_profile_minus_canonical": median_distance,
        "median_case_bks_gap_delta_profile_minus_canonical": statistics.median(
            float(item["median_bks_gap_delta_profile_minus_canonical"])
            for item in estimates
        ),
        "fixed_quality_direction": direction,
    }


def _paired_summary(
    quartets: Sequence[tuple[str, int]],
    rows_by_quartet: Mapping[tuple[str, int], Mapping[str, Mapping[str, Any]]],
    candidate_profile: str,
) -> dict[str, Any]:
    pairs = [
        _pair_measurement(
            rows_by_quartet[key]["canonical_alns_vns"],
            rows_by_quartet[key][candidate_profile],
        )
        for key in quartets
    ]
    estimates = _case_estimands(pairs)
    result = {
        "primary_unit": "case",
        "case_estimands": estimates,
        "case_equal_weighted": _case_equal_weighted(estimates),
        "seed_pooled_diagnostics_only": _paired_compact(pairs),
    }
    heterogeneity: dict[str, dict[str, Any]] = {}
    for dimension in (
        "case",
        "size",
        "seed",
        "candidate_execution_position",
        "canonical_execution_position",
        "exposure_regime",
    ):
        grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
        for item in pairs:
            grouped[str(item[dimension])].append(item)
        heterogeneity[dimension] = {
            key: _paired_compact(items) for key, items in sorted(grouped.items())
        }
    result["heterogeneity"] = heterogeneity
    return result


def _view_payload(
    view_id: str,
    quartets: Sequence[tuple[str, int]],
    rows_by_quartet: Mapping[tuple[str, int], Mapping[str, Mapping[str, Any]]],
) -> dict[str, Any]:
    rows = [rows_by_quartet[key][profile] for key in quartets for profile in PROFILES]
    job_ids = [
        str(row["job_id"])
        for row in sorted(rows, key=lambda row: int(row["execution_ordinal"]))
    ]
    return {
        "view_id": view_id,
        "row_count": len(rows),
        "quartet_count": len(quartets),
        "quartet_identities": [
            {"case_id": case_id, "seed": seed} for case_id, seed in quartets
        ],
        "ordered_job_ids": job_ids,
        "profile_summaries": {
            profile: _profile_summary(
                [rows_by_quartet[key][profile] for key in quartets]
            )
            for profile in PROFILES
        },
        "paired_vs_canonical": {
            profile: _paired_summary(quartets, rows_by_quartet, profile)
            for profile in COMPARISON_PROFILES
        },
    }


def _acceptance_assessment(views: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    sensitivity_ids = VIEW_ORDER[:3]
    directions: dict[str, dict[str, str]] = {}
    consistent = True
    for profile in MAIN_COMPARISON_PROFILES:
        by_view = {
            view_id: str(
                views[view_id]["paired_vs_canonical"][profile]["case_equal_weighted"][
                    "fixed_quality_direction"
                ]
            )
            for view_id in sensitivity_ids
        }
        directions[profile] = by_view
        consistent = consistent and len(set(by_view.values())) == 1
    balanced_directions = {
        profile: str(
            views["normal_overlap_balanced_32"]["paired_vs_canonical"][profile][
                "case_equal_weighted"
            ]["fixed_quality_direction"]
        )
        for profile in MAIN_COMPARISON_PROFILES
    }
    balanced_reversal = any(
        {balanced_directions[profile], directions[profile]["full_256"]}
        == {"canonical_better", "profile_better"}
        for profile in MAIN_COMPARISON_PROFILES
    )
    conditions_met = consistent and not balanced_reversal
    verdict = (
        "accepted_conservative_scope" if conditions_met else "diagnostic_subset_only"
    )
    return {
        "verdict": verdict,
        "integrity_closure": "passed",
        "main_direction_by_view": directions,
        "main_direction_sensitivity_consistent": consistent,
        "normal_overlap_balanced_direction": balanced_directions,
        "normal_overlap_failure_or_timeout_cliff": False,
        "normal_overlap_reversed_main_interaction": balanced_reversal,
        "known_host_overlap": True,
        "absolute_overlap_throughput_potentially_biased": True,
        "f1_unlocked_by_closer_verdict": verdict == "accepted_conservative_scope",
        "independent_review_status": "pending_integrity_and_science_reviews",
        "production_improvement_proven": False,
        "promotion_authorized": False,
    }


def build_comparison_artifacts(input_root: str | Path) -> ComparisonArtifacts:
    root = Path(input_root).expanduser().resolve(strict=True)
    canonical_root = Path(CANONICAL_INPUT_ROOT).resolve(strict=True)
    if root != canonical_root:
        raise CvrpB1ComparisonError("input root is not the exact accepted B1 root")
    repo = repository_root()
    if sha256_file(repo / DESIGN_PATH) != DESIGN_SHA256:
        raise CvrpB1ComparisonError("B1 comparison design SHA-256 drift")
    if sha256_file(repo / INFLIGHT_PATH) != INFLIGHT_SHA256:
        raise CvrpB1ComparisonError("B1 inflight overlap record SHA-256 drift")
    manifest = _load_bound_json(
        root / "manifest.json", MANIFEST_SHA256, label="B1 manifest"
    )
    results = _load_bound_json(
        root / "results.json", RESULTS_SHA256, label="B1 results"
    )
    closed_receipt = _load_bound_json(
        root / "matrix.closed.receipt.json",
        CLOSED_RECEIPT_SHA256,
        label="B1 closed receipt",
    )
    rows, rows_by_quartet, raw_identities = _validate_integrity(
        root, manifest, results, closed_receipt
    )
    view_quartets = _view_quartets(rows_by_quartet)
    view_payloads = {
        view_id: _view_payload(view_id, view_quartets[view_id], rows_by_quartet)
        for view_id in VIEW_ORDER
    }
    exposure_counts = Counter(
        overlap_regime(int(row["execution_ordinal"])) for row in rows
    )
    report: dict[str, Any] = {
        "schema": REPORT_SCHEMA,
        "authority": AUTHORITY,
        "passed": True,
        "scope": (
            "One-time CVRP diagnostic matrix with known host overlap; not clean-host "
            "evidence, not a production improvement, and not promotion authority."
        ),
        "input_root_identity": CANONICAL_INPUT_ROOT,
        "integrity": {
            "status": "passed",
            "job_count": 256,
            "quartet_count": 64,
            "profile_counts": {profile: 64 for profile in PROFILES},
            "profile_position_counts": {
                profile: {str(position): 16 for position in range(4)}
                for profile in PROFILES
            },
            "resolved_time_limit_counts": {"30": 192, "45": 64},
            "completed_returncode_zero_count": 256,
            "feasible_zero_fleet_violation_count": 256,
            "internal_time_limit_stop_count": 256,
            "raw_identity_count": len(raw_identities),
            "duplicate_job_count": 0,
            "extra_raw_file_count": 0,
            "retry_resume_workspace_reuse_evidence": False,
        },
        "host_overlap": {
            "clean_host_claim": False,
            "process": "Warehouse W2 slow MILP pytest process PID 3791879",
            "normal_priority_started_utc": "2026-07-18T08:56:08Z",
            "reniced_and_idle_io_utc": "2026-07-18T09:17:50Z",
            "natural_end_exact_time_captured": False,
            "ordinal_regimes": {
                "clean_before": {"first": 0, "last": 173},
                "normal_priority_overlap": {"first": 174, "last": 211},
                "reduced_priority_end_unknown": {"first": 212, "last": 215},
                "clean_after": {"first": 216, "last": 255},
            },
            "row_counts": dict(sorted(exposure_counts.items())),
            "inflight_record_path": INFLIGHT_PATH,
            "inflight_record_raw_sha256": INFLIGHT_SHA256,
            "throughput_caveat": (
                "Absolute throughput in overlap regimes may be host-contention biased."
            ),
        },
        "views": view_payloads,
    }
    report["acceptance_assessment"] = _acceptance_assessment(view_payloads)
    report_bytes = render_artifact(report)
    closer_source_hashes = {
        path: sha256_file(repo / path) for path in CLOSER_SOURCE_PATHS
    }
    receipt: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "authority": AUTHORITY,
        "passed": True,
        "design_path": DESIGN_PATH,
        "design_raw_sha256": DESIGN_SHA256,
        "inflight_record_path": INFLIGHT_PATH,
        "inflight_record_raw_sha256": INFLIGHT_SHA256,
        "input_root_identity": CANONICAL_INPUT_ROOT,
        "input_artifacts": {
            "manifest.json": MANIFEST_SHA256,
            "results.json": RESULTS_SHA256,
            "matrix.closed.receipt.json": CLOSED_RECEIPT_SHA256,
        },
        "ordered_raw_identities": raw_identities,
        "overlap_classification": report["host_overlap"],
        "view_membership": {
            view_id: {
                "row_count": view_payloads[view_id]["row_count"],
                "quartet_identities": view_payloads[view_id]["quartet_identities"],
                "ordered_job_ids": view_payloads[view_id]["ordered_job_ids"],
            }
            for view_id in VIEW_ORDER
        },
        "report_path": REPORT_NAME,
        "report_raw_sha256": sha256_bytes(report_bytes),
        "closer_source_hashes": closer_source_hashes,
        "closer_source_identity_sha256": _canonical_identity_sha256(
            "scion.cvrp_b1_comparison_closer_sources.v1",
            [
                {"path": path, "raw_sha256": closer_source_hashes[path]}
                for path in CLOSER_SOURCE_PATHS
            ],
        ),
        "acceptance_verdict": report["acceptance_assessment"]["verdict"],
        "f1_unlocked_by_closer_verdict": report["acceptance_assessment"][
            "f1_unlocked_by_closer_verdict"
        ],
    }
    receipt_bytes = render_artifact(receipt)
    return ComparisonArtifacts(
        report=report,
        receipt=receipt,
        report_bytes=report_bytes,
        receipt_bytes=receipt_bytes,
    )


def verify_existing_artifact_bytes(
    input_root: str | Path,
    actual_report: bytes,
    actual_receipt: bytes,
) -> dict[str, Any]:
    expected = build_comparison_artifacts(input_root)
    if actual_report != expected.report_bytes:
        raise CvrpB1ComparisonError(
            "existing B1 comparison report differs from sealed byte replay"
        )
    if actual_receipt != expected.receipt_bytes:
        raise CvrpB1ComparisonError(
            "existing B1 comparison receipt differs from sealed byte replay"
        )
    return {
        "passed": True,
        "report_raw_sha256": sha256_bytes(actual_report),
        "receipt_raw_sha256": sha256_bytes(actual_receipt),
        "acceptance_verdict": expected.receipt["acceptance_verdict"],
        "f1_unlocked_by_closer_verdict": expected.receipt[
            "f1_unlocked_by_closer_verdict"
        ],
    }
