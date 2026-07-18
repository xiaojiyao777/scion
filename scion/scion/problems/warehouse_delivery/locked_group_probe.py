"""One-shot, no-LLM Warehouse locked-group semantic probes.

This problem-owned module is diagnostic scientific evidence.  Nothing in the
agent, proposal, scheduling, verification, or promotion hot path imports it.
"""

from __future__ import annotations

import importlib.util
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from random import Random
from typing import Any

from scion.problem.bridge import load_problem_spec_v1_from_yaml
from scion.problem.loader import load_problem_adapter
from scion.problems.warehouse_delivery.locked_group_fixtures import (
    FIXTURE_SCHEMA,
    directed_fixtures,
)
from scion.problems.warehouse_delivery.w2_preservation import (
    acceptance_toolchain,
    canonical_sha256,
    repository_root,
    sha256_bytes,
    verify_w2_preservation,
)


SCHEMA = "scion.warehouse_locked_group_probe.v1"
RECEIPT_SCHEMA = "scion.warehouse_locked_group_probe_receipt.v1"
AUTHORITY = "diagnostic_scientific_evidence_only"
DESIGN_PATH = (
    "scion/docs/planning/v0.4/"
    "v0.4-warehouse-w2-locked-group-semantics-20260718.md"
)
DESIGN_SHA256 = "c0d85d60c8bbdac94d274962a51cf3892a7e072798a9f7aba25b95eb0671fc7a"
PRESERVATION_MANIFEST_PATH = (
    "scion/contracts/warehouse_w2_preservation_manifest.v1.json"
)
PRESERVATION_MANIFEST_SHA256 = (
    "0ee66091942583c2f499f83338a96abeff51e53b9583afe03fce3356a890dfc9"
)
REPORT_PATH = "scion/contracts/warehouse_w2_locked_group_probe.v1.json"
RECEIPT_PATH = (
    "scion/contracts/warehouse_w2_locked_group_probe_receipt.v1.json"
)
FIXTURE_IDS = (
    "01_group_initial_vehicle",
    "02_multi_group_whole_move",
    "03_group_merge_free",
    "04_two_groups_merge",
    "05_singleton_group_move",
    "06_empty_string_group_phase2",
    "07_group_split",
    "08_group_partial_move",
    "09_order_lost",
    "10_order_duplicated",
    "11_assignment_disagrees",
    "12_capacity_exceeded",
    "13_region_mixed",
    "14_pickup_limit",
    "15_phase1_category_mixed",
    "16_hazard_h5_h8_family",
    "17_amount_limit_h6",
)
SOURCE_OWNER_PATHS = (
    "scion/contracts/warehouse_w1_population_receipt.v1.json",
    "scion/contracts/warehouse_w2_preservation_manifest.v1.json",
    "scion/docs/reference/milp-model.md",
    "scion/problems/warehouse_delivery/problem-v1.yaml",
    "scion/scion/problems/warehouse_delivery/adapter.py",
    "scion/scion/problems/warehouse_delivery/locked_group_fixtures.py",
    "scion/scion/problems/warehouse_delivery/locked_group_probe.py",
    "scion/scion/problems/warehouse_delivery/problem-v1.yaml",
    "scion/scion/problems/warehouse_delivery/w2_preservation.py",
    "scion/tools/warehouse_locked_group_probe.py",
    "surrogate/MILP_SOLVER_NOTES.md",
    "surrogate/greedy_init.py",
    "surrogate/milp_model.py",
    "surrogate/models.py",
    "surrogate/operators/base.py",
    "surrogate/oracle.py",
    "surrogate/surrogate-problem-spec-v1.md",
)
NON_APPLICABLE_REASONS = {
    "09_order_lost": "total_assignment_unrepresentable",
    "10_order_duplicated": "duplicate_membership_unrepresentable",
    "11_assignment_disagrees": "dual_representation_disagreement_unrepresentable",
}

_REPORT_FIELDS = {
    "schema",
    "authority",
    "passed",
    "fixture_schema",
    "fixture_bundle_sha256",
    "row_count",
    "aggregate_sha256",
    "source_owner_hashes",
    "rows",
}
_ROW_FIELDS = {
    "fixture_id",
    "fixture_content_sha256",
    "phase",
    "candidate",
    "expected",
    "oracle",
    "adapter",
    "fixed_candidate_milp",
    "phase2_initialization",
    "source_owner_hashes",
    "checks",
    "passed",
}
_APPLICABLE_MILP_FIELDS = {
    "applicable",
    "result",
    "K",
    "compute_K",
    "used_vehicle_count",
    "vehicle_to_slot",
    "prefix_symmetry_retained",
    "phase2_exact_subcategory_spread",
    "fixed_variable_counts",
    "fixed_variable_digests",
    "solver",
    "incumbent_valid",
    "incumbent_issue_codes",
}
_RECEIPT_FIELDS = {
    "schema",
    "authority",
    "passed",
    "design_path",
    "design_sha256",
    "preservation_manifest_path",
    "preservation_manifest_sha256",
    "fixture_schema",
    "fixture_bundle_sha256",
    "row_count",
    "aggregate_sha256",
    "report_path",
    "report_raw_sha256",
    "source_owner_hashes",
    "toolchain",
}


class WarehouseLockedGroupProbeError(RuntimeError):
    """Raised when a directed probe cannot produce accepted evidence."""


@dataclass(frozen=True)
class _Runtime:
    adapter: Any
    models: Any
    oracle: Any
    greedy_init: Any
    milp_model: Any
    pulp: Any
    highspy: Any


def _load_file_module(directory: Path, filename: str, key: str) -> Any:
    path = directory / filename
    saved = list(sys.path)
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))
    try:
        spec = importlib.util.spec_from_file_location(key, path)
        if spec is None or spec.loader is None:
            raise WarehouseLockedGroupProbeError(f"cannot load module: {path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[key] = module
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path[:] = saved


def _load_runtime() -> _Runtime:
    import highspy

    root = repository_root()
    spec = load_problem_spec_v1_from_yaml(
        root / "scion/scion/problems/warehouse_delivery/problem-v1.yaml"
    )
    adapter = load_problem_adapter(spec)
    adapter._ensure_modules()  # Problem-owned probe needs the exact adapter owners.
    surrogate = root / "surrogate"
    greedy = _load_file_module(surrogate, "greedy_init.py", "_wd_w2_greedy_init")
    milp = _load_file_module(surrogate, "milp_model.py", "_wd_w2_milp_model")
    return _Runtime(
        adapter=adapter,
        models=adapter._models_mod,
        oracle=adapter._oracle_mod,
        greedy_init=greedy,
        milp_model=milp,
        pulp=milp.pulp,
        highspy=highspy,
    )


def _instance(runtime: _Runtime, fixture: dict[str, Any]) -> Any:
    orders: dict[str, Any] = {}
    for raw in fixture["instance"]["orders"]:
        values = dict(raw)
        values["spu_list"] = [runtime.models.SPU(**spu) for spu in raw["spu_list"]]
        order = runtime.models.Order(**values)
        orders[order.order_id] = order
    return runtime.models.Instance(
        orders=orders,
        amount_limits=dict(fixture["instance"]["amount_limits"]),
        phase=int(fixture["instance"]["phase"]),
    )


def _solution(runtime: _Runtime, fixture: dict[str, Any]) -> Any:
    candidate = fixture["candidate"]
    vehicles = {
        vehicle_id: runtime.models.Vehicle(
            vehicle_id=raw["vehicle_id"],
            vehicle_type=raw["vehicle_type"],
            region=raw["region"],
            order_ids=list(raw["order_ids"]),
        )
        for vehicle_id, raw in candidate["vehicles"].items()
    }
    return runtime.models.Solution(
        vehicles=vehicles,
        assignment=dict(candidate["assignment"]),
    )


def _family(violations: list[str] | tuple[str, ...]) -> str:
    if not violations:
        return "feasible"
    prefix = str(violations[0]).split(":", 1)[0]
    return "H5/H8" if prefix in {"H5", "H8"} else prefix


def _fixed_values_digest(items: list[dict[str, Any]]) -> str:
    return canonical_sha256(
        {"domain": "scion.warehouse_fixed_candidate_values.v1", "items": items}
    )


def classify_native_milp_result(
    highspy_module: Any,
    native_status: Any,
    incumbent_issue_codes: list[str],
) -> tuple[str, bool | None, list[str]]:
    """Map only authoritative native HiGHS statuses to evidence."""

    issues = sorted(set(incumbent_issue_codes))
    if native_status == highspy_module.HighsModelStatus.kOptimal:
        if issues:
            return "fixed_candidate_indeterminate", False, issues
        return "fixed_candidate_feasible", True, []
    if native_status == highspy_module.HighsModelStatus.kInfeasible:
        if issues:
            return "fixed_candidate_indeterminate", None, issues
        return "fixed_candidate_infeasible", None, []
    if "native_status_non_authoritative" not in issues:
        issues.append("native_status_non_authoritative")
        issues.sort()
    return "fixed_candidate_indeterminate", None, issues


def _fixed_variable_pairs(
    variables: dict[str, Any],
    items: list[dict[str, Any]],
    family: str,
    order_index: dict[str, int],
) -> list[tuple[dict[str, Any], Any]]:
    pairs: list[tuple[dict[str, Any], Any]] = []
    for item in items:
        if family == "x":
            variable = variables["x"][order_index[item["order_id"]], item["slot"]]
        elif family == "y":
            variable = variables["y"][item["slot"]]
        else:
            variable = variables["z"][item["slot"], item["vehicle_type"]]
        pairs.append((item, variable))
    return pairs


def _incumbent_issue_codes(
    runtime: _Runtime,
    variables: dict[str, Any],
    fixed: dict[str, list[dict[str, Any]]],
    order_index: dict[str, int],
) -> list[str]:
    issues: set[str] = set()
    for family in ("x", "y", "z"):
        for item, variable in _fixed_variable_pairs(
            variables, fixed[family], family, order_index
        ):
            actual = runtime.pulp.value(variable)
            if actual is None:
                issues.add(f"{family}_incumbent_value_missing")
                continue
            try:
                numeric = float(actual)
            except (TypeError, ValueError, OverflowError):
                issues.add(f"{family}_incumbent_value_non_numeric")
                continue
            if not math.isfinite(numeric):
                issues.add(f"{family}_incumbent_value_non_finite")
            elif abs(numeric - item["value"]) > 1e-6:
                issues.add(f"{family}_fixed_value_mismatch")
    return sorted(issues)


def _fixed_candidate_milp(
    runtime: _Runtime,
    fixture: dict[str, Any],
    instance: Any,
) -> dict[str, Any]:
    contract = fixture["milp_contract"]
    if not contract["applicable"]:
        return {
            "applicable": False,
            "result": "not_applicable_by_contract",
            "contract_reason_code": contract["reason"],
        }

    candidate = fixture["candidate"]
    vehicle_ids = sorted(candidate["vehicles"], key=lambda value: value.encode("utf-8"))
    vehicle_to_slot = {vehicle_id: index for index, vehicle_id in enumerate(vehicle_ids)}
    used = len(vehicle_ids)
    compute_k = runtime.milp_model.compute_K(instance)
    K = max(compute_k, used)
    phase2_spread: int | None = None
    if instance.phase == 2:
        by_subcategory: dict[int, set[str]] = {}
        for order_id, vehicle_id in candidate["assignment"].items():
            subcategory = instance.orders[order_id].vehicle_subcategory
            by_subcategory.setdefault(subcategory, set()).add(vehicle_id)
        phase2_spread = sum(len(values) for values in by_subcategory.values())

    problem, variables = runtime.milp_model.build_milp(
        instance,
        K,
        symmetry_breaking=True,
        phase2_sum_alpha_star=phase2_spread,
    )
    order_index = {order.order_id: index for index, order in enumerate(variables["orders"])}
    fixed: dict[str, list[dict[str, Any]]] = {"x": [], "y": [], "z": []}
    for order_id, index in sorted(order_index.items()):
        assigned_vehicle = candidate["assignment"][order_id]
        for slot in variables["J"]:
            value = int(slot == vehicle_to_slot[assigned_vehicle])
            variable = variables["x"][index, slot]
            variable.setInitialValue(value)
            variable.fixValue()
            fixed["x"].append({"order_id": order_id, "slot": slot, "value": value})
    for slot in variables["J"]:
        value = int(slot < used)
        variable = variables["y"][slot]
        variable.setInitialValue(value)
        variable.fixValue()
        fixed["y"].append({"slot": slot, "value": value})
        vehicle_id = vehicle_ids[slot] if slot < used else None
        selected_type = (
            candidate["vehicles"][vehicle_id]["vehicle_type"]
            if vehicle_id is not None
            else None
        )
        for vehicle_type in variables["T"]:
            type_value = int(vehicle_type == selected_type)
            variable = variables["z"][slot, vehicle_type]
            variable.setInitialValue(type_value)
            variable.fixValue()
            fixed["z"].append(
                {"slot": slot, "vehicle_type": vehicle_type, "value": type_value}
            )

    native_status: Any = None
    issue_codes: list[str] = []
    try:
        problem.solve(runtime.pulp.HiGHS(msg=False))
        solver_model = getattr(problem, "solverModel", None)
        if solver_model is None or not hasattr(solver_model, "getModelStatus"):
            issue_codes.append("native_status_unavailable")
        else:
            native_status = solver_model.getModelStatus()
            if native_status == runtime.highspy.HighsModelStatus.kOptimal:
                issue_codes.extend(
                    _incumbent_issue_codes(runtime, variables, fixed, order_index)
                )
    except Exception:  # Diagnostics are deliberately excluded from receipted rows.
        issue_codes.append("solver_exception")

    result, incumbent_valid, issue_codes = classify_native_milp_result(
        runtime.highspy, native_status, issue_codes
    )
    native_status_literal = (
        str(native_status) if native_status is not None else "native_status_unavailable"
    )
    return {
        "applicable": True,
        "result": result,
        "K": K,
        "compute_K": compute_k,
        "used_vehicle_count": used,
        "vehicle_to_slot": vehicle_to_slot,
        "prefix_symmetry_retained": True,
        "phase2_exact_subcategory_spread": phase2_spread,
        "fixed_variable_counts": {
            family: len(items) for family, items in fixed.items()
        },
        "fixed_variable_digests": {
            family: _fixed_values_digest(items) for family, items in fixed.items()
        },
        "solver": {
            "name": "HiGHS",
            "version": "1.14.0",
            "native_status": native_status_literal,
        },
        "incumbent_valid": incumbent_valid,
        "incumbent_issue_codes": issue_codes,
    }


def _phase2_init_result(
    runtime: _Runtime,
    fixture: dict[str, Any],
    instance: Any,
) -> dict[str, Any] | None:
    if not fixture["assert_phase2_empty_group_init"]:
        return None
    initial = runtime.greedy_init.greedy_init(instance, Random(20260718))
    orders = sorted(initial.vehicles.get("").order_ids) if "" in initial.vehicles else []
    return {
        "assignment": dict(sorted(initial.assignment.items())),
        "empty_string_group_orders": orders,
        "empty_string_vehicle_present": "" in initial.vehicles,
        "passed": "" in initial.vehicles and orders == ["E1", "E2"],
    }


def formal_check_deserialized_candidate(
    runtime: _Runtime,
    artifact: Any,
    instance: Any,
) -> Any:
    """Run the canonical Oracle on adapter-deserialized state at the real phase."""

    solution = artifact.normalized_solution
    if solution is None:
        raise WarehouseLockedGroupProbeError(
            "adapter deserialization produced no normalized solution"
        )
    return runtime.oracle.check_feasibility(
        solution,
        instance,
        phase=instance.phase,
    )


def _row(
    runtime: _Runtime,
    fixture: dict[str, Any],
    source_owner_hashes: dict[str, str],
) -> dict[str, Any]:
    instance = _instance(runtime, fixture)
    solution = _solution(runtime, fixture)
    oracle = runtime.oracle.check_feasibility(solution, instance, phase=instance.phase)
    artifact = runtime.adapter.deserialize_solver_output(fixture["candidate"], instance)
    adapter = formal_check_deserialized_candidate(runtime, artifact, instance)
    milp = _fixed_candidate_milp(runtime, fixture, instance)
    init_result = _phase2_init_result(runtime, fixture, instance)
    expected = fixture["expected"]
    expected_milp = (
        "fixed_candidate_feasible" if expected["feasible"] else "fixed_candidate_infeasible"
    )
    oracle_family = _family(oracle.violations)
    adapter_family = _family(adapter.violations)
    expected_reason = NON_APPLICABLE_REASONS.get(fixture["fixture_id"])
    checks = {
        "oracle_matches_expected": (
            oracle.is_feasible == expected["feasible"]
            and oracle_family == expected["constraint_family"]
        ),
        "adapter_matches_expected": (
            adapter.is_feasible == expected["feasible"]
            and adapter_family == expected["constraint_family"]
        ),
        "oracle_adapter_agree": (
            oracle.is_feasible == adapter.is_feasible and oracle_family == adapter_family
        ),
        "milp_matches_expected": (
            milp["result"] == expected_milp
            if milp["applicable"]
            else milp.get("contract_reason_code") == expected_reason
        ),
        "phase2_empty_group_init": init_result is None or init_result["passed"],
    }
    fixture_content = {key: value for key, value in fixture.items() if key != "fixture_id"}
    return {
        "fixture_id": fixture["fixture_id"],
        "fixture_content_sha256": canonical_sha256(fixture_content),
        "phase": fixture["instance"]["phase"],
        "candidate": {
            "assignment": fixture["candidate"]["assignment"],
            "vehicle_order_ids": {
                vehicle_id: raw["order_ids"]
                for vehicle_id, raw in sorted(fixture["candidate"]["vehicles"].items())
            },
            "vehicle_types": {
                vehicle_id: raw["vehicle_type"]
                for vehicle_id, raw in sorted(fixture["candidate"]["vehicles"].items())
            },
        },
        "expected": expected,
        "oracle": {"feasible": oracle.is_feasible, "constraint_family": oracle_family},
        "adapter": {"feasible": adapter.is_feasible, "constraint_family": adapter_family},
        "fixed_candidate_milp": milp,
        "phase2_initialization": init_result,
        "source_owner_hashes": source_owner_hashes,
        "checks": checks,
        "passed": all(checks.values()),
    }


def _exact_fixture_bundle() -> list[dict[str, Any]]:
    fixtures = directed_fixtures()
    fixture_ids = tuple(fixture.get("fixture_id") for fixture in fixtures)
    if fixture_ids != FIXTURE_IDS or len(set(fixture_ids)) != len(FIXTURE_IDS):
        raise WarehouseLockedGroupProbeError(
            "directed fixture set differs from the exact 17-fixture contract"
        )
    return fixtures


def _source_owner_hashes() -> dict[str, str]:
    root = repository_root()
    return {
        relative: sha256_bytes((root / relative).read_bytes())
        for relative in SOURCE_OWNER_PATHS
    }


def build_probe_report() -> dict[str, Any]:
    preservation = verify_w2_preservation()
    if preservation["manifest_sha256"] != PRESERVATION_MANIFEST_SHA256:
        raise WarehouseLockedGroupProbeError("unexpected preservation manifest identity")
    root = repository_root()
    if sha256_bytes((root / DESIGN_PATH).read_bytes()) != DESIGN_SHA256:
        raise WarehouseLockedGroupProbeError("unexpected W2 design identity")
    acceptance_toolchain()
    runtime = _load_runtime()
    source_hashes = _source_owner_hashes()
    fixtures = _exact_fixture_bundle()
    rows = [_row(runtime, fixture, source_hashes) for fixture in fixtures]
    aggregate = canonical_sha256({"domain": SCHEMA, "items": rows})
    report = {
        "schema": SCHEMA,
        "authority": AUTHORITY,
        "passed": all(row["passed"] for row in rows),
        "fixture_schema": FIXTURE_SCHEMA,
        "fixture_bundle_sha256": canonical_sha256(
            {"domain": FIXTURE_SCHEMA, "items": fixtures}
        ),
        "row_count": len(rows),
        "aggregate_sha256": aggregate,
        "source_owner_hashes": source_hashes,
        "rows": rows,
    }
    validate_report(report)
    return report


def render_artifact(value: dict[str, Any]) -> bytes:
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


def build_probe_receipt(report: dict[str, Any], report_bytes: bytes) -> dict[str, Any]:
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "authority": AUTHORITY,
        "passed": True,
        "design_path": DESIGN_PATH,
        "design_sha256": DESIGN_SHA256,
        "preservation_manifest_path": PRESERVATION_MANIFEST_PATH,
        "preservation_manifest_sha256": PRESERVATION_MANIFEST_SHA256,
        "fixture_schema": FIXTURE_SCHEMA,
        "fixture_bundle_sha256": report["fixture_bundle_sha256"],
        "row_count": 17,
        "aggregate_sha256": report["aggregate_sha256"],
        "report_path": REPORT_PATH,
        "report_raw_sha256": sha256_bytes(report_bytes),
        "source_owner_hashes": report["source_owner_hashes"],
        "toolchain": acceptance_toolchain(),
    }
    validate_receipt(receipt, report, report_bytes)
    return receipt


def build_probe_artifacts() -> tuple[bytes, bytes, dict[str, Any], dict[str, Any]]:
    report = build_probe_report()
    report_bytes = render_artifact(report)
    receipt = build_probe_receipt(report, report_bytes)
    receipt_bytes = render_artifact(receipt)
    return report_bytes, receipt_bytes, report, receipt


def verify_existing_artifact_bytes(
    actual_report: bytes,
    actual_receipt: bytes,
) -> dict[str, Any]:
    """Rebuild from current authority and byte-compare both acceptance files."""

    expected_report, expected_receipt, report, receipt = build_probe_artifacts()
    if actual_report != expected_report:
        raise WarehouseLockedGroupProbeError(
            "fixed report bytes differ from a complete current-state replay"
        )
    if actual_receipt != expected_receipt:
        raise WarehouseLockedGroupProbeError(
            "fixed receipt bytes differ from a complete current-state replay"
        )
    return {
        "passed": True,
        "aggregate_sha256": report["aggregate_sha256"],
        "report_raw_sha256": receipt["report_raw_sha256"],
        "receipt_raw_sha256": sha256_bytes(actual_receipt),
    }


def _require_exact_fields(value: Any, fields: set[str], *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        actual = sorted(value) if isinstance(value, dict) else type(value).__name__
        raise WarehouseLockedGroupProbeError(
            f"{label} fields differ from closed schema: {actual}"
        )
    return value


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(
        char in "0123456789abcdef" for char in value
    )


def validate_report(report: dict[str, Any]) -> None:
    _require_exact_fields(report, _REPORT_FIELDS, label="report")
    if (
        report["schema"] != SCHEMA
        or report["authority"] != AUTHORITY
        or report["passed"] is not True
        or report["fixture_schema"] != FIXTURE_SCHEMA
        or report["row_count"] != 17
        or not _is_sha256(report["fixture_bundle_sha256"])
    ):
        raise WarehouseLockedGroupProbeError("report authority constants are invalid")
    source_hashes = _require_exact_fields(
        report["source_owner_hashes"], set(SOURCE_OWNER_PATHS), label="source_owner_hashes"
    )
    if not all(_is_sha256(value) for value in source_hashes.values()):
        raise WarehouseLockedGroupProbeError("source owner hash is not SHA-256")
    rows = report["rows"]
    if not isinstance(rows, list) or tuple(row.get("fixture_id") for row in rows) != FIXTURE_IDS:
        raise WarehouseLockedGroupProbeError("probe rows differ from exact fixture order")
    for fixture_id, raw_row in zip(FIXTURE_IDS, rows, strict=True):
        row = _require_exact_fields(raw_row, _ROW_FIELDS, label=f"row {fixture_id}")
        if (
            row["fixture_id"] != fixture_id
            or not _is_sha256(row["fixture_content_sha256"])
            or row["phase"] not in {1, 2}
            or row["source_owner_hashes"] != source_hashes
            or row["passed"] is not True
        ):
            raise WarehouseLockedGroupProbeError(f"row identity invalid: {fixture_id}")
        _require_exact_fields(
            row["candidate"],
            {"assignment", "vehicle_order_ids", "vehicle_types"},
            label=f"candidate {fixture_id}",
        )
        candidate = row["candidate"]
        if (
            not isinstance(candidate["assignment"], dict)
            or not all(
                isinstance(key, str) and isinstance(value, str)
                for key, value in candidate["assignment"].items()
            )
            or not isinstance(candidate["vehicle_order_ids"], dict)
            or not all(
                isinstance(key, str)
                and isinstance(value, list)
                and all(isinstance(order_id, str) for order_id in value)
                for key, value in candidate["vehicle_order_ids"].items()
            )
            or not isinstance(candidate["vehicle_types"], dict)
            or not all(
                isinstance(key, str) and isinstance(value, str)
                for key, value in candidate["vehicle_types"].items()
            )
            or set(candidate["vehicle_order_ids"]) != set(candidate["vehicle_types"])
        ):
            raise WarehouseLockedGroupProbeError(
                f"candidate scalar/map shape invalid: {fixture_id}"
            )
        for field in ("expected", "oracle", "adapter"):
            _require_exact_fields(
                row[field], {"feasible", "constraint_family"}, label=f"{field} {fixture_id}"
            )
            if (
                not isinstance(row[field]["feasible"], bool)
                or not isinstance(row[field]["constraint_family"], str)
            ):
                raise WarehouseLockedGroupProbeError(
                    f"{field} scalar shape invalid: {fixture_id}"
                )
        if row["oracle"] != row["expected"] or row["adapter"] != row["expected"]:
            raise WarehouseLockedGroupProbeError(
                f"cross-owner semantic result invalid: {fixture_id}"
            )
        checks = _require_exact_fields(
            row["checks"],
            {
                "oracle_matches_expected",
                "adapter_matches_expected",
                "oracle_adapter_agree",
                "milp_matches_expected",
                "phase2_empty_group_init",
            },
            label=f"checks {fixture_id}",
        )
        if any(value is not True for value in checks.values()):
            raise WarehouseLockedGroupProbeError(f"row check failed: {fixture_id}")
        init = row["phase2_initialization"]
        if fixture_id == "06_empty_string_group_phase2":
            _require_exact_fields(
                init,
                {
                    "assignment",
                    "empty_string_group_orders",
                    "empty_string_vehicle_present",
                    "passed",
                },
                label="phase2 initialization",
            )
            if init["passed"] is not True:
                raise WarehouseLockedGroupProbeError("empty-string initialization failed")
        elif init is not None:
            raise WarehouseLockedGroupProbeError(
                f"unexpected phase2 initialization payload: {fixture_id}"
            )
        milp = row["fixed_candidate_milp"]
        if fixture_id in NON_APPLICABLE_REASONS:
            _require_exact_fields(
                milp,
                {"applicable", "result", "contract_reason_code"},
                label=f"MILP {fixture_id}",
            )
            if milp != {
                "applicable": False,
                "result": "not_applicable_by_contract",
                "contract_reason_code": NON_APPLICABLE_REASONS[fixture_id],
            }:
                raise WarehouseLockedGroupProbeError(
                    f"non-applicable MILP contract invalid: {fixture_id}"
                )
        else:
            _require_exact_fields(milp, _APPLICABLE_MILP_FIELDS, label=f"MILP {fixture_id}")
            if milp["applicable"] is not True:
                raise WarehouseLockedGroupProbeError(f"MILP applicability invalid: {fixture_id}")
            _require_exact_fields(
                milp["fixed_variable_counts"], {"x", "y", "z"}, label="MILP counts"
            )
            digests = _require_exact_fields(
                milp["fixed_variable_digests"], {"x", "y", "z"}, label="MILP digests"
            )
            if not all(_is_sha256(value) for value in digests.values()):
                raise WarehouseLockedGroupProbeError("MILP digest is not SHA-256")
            if (
                not isinstance(milp["K"], int)
                or not isinstance(milp["compute_K"], int)
                or not isinstance(milp["used_vehicle_count"], int)
                or not isinstance(milp["vehicle_to_slot"], dict)
                or not all(
                    isinstance(key, str) and isinstance(value, int)
                    for key, value in milp["vehicle_to_slot"].items()
                )
                or milp["prefix_symmetry_retained"] is not True
                or not all(isinstance(value, int) for value in milp["fixed_variable_counts"].values())
                or not isinstance(milp["incumbent_issue_codes"], list)
                or any(not isinstance(code, str) for code in milp["incumbent_issue_codes"])
                or milp["incumbent_issue_codes"] != sorted(set(milp["incumbent_issue_codes"]))
            ):
                raise WarehouseLockedGroupProbeError(
                    f"MILP scalar/map shape invalid: {fixture_id}"
                )
            solver = _require_exact_fields(
                milp["solver"], {"name", "version", "native_status"}, label="MILP solver"
            )
            if solver["name"] != "HiGHS" or solver["version"] != "1.14.0":
                raise WarehouseLockedGroupProbeError("MILP solver identity invalid")
            if milp["result"] == "fixed_candidate_feasible":
                expected_state = ("HighsModelStatus.kOptimal", True)
            elif milp["result"] == "fixed_candidate_infeasible":
                expected_state = ("HighsModelStatus.kInfeasible", None)
            else:
                raise WarehouseLockedGroupProbeError(
                    f"indeterminate MILP result cannot be accepted: {fixture_id}"
                )
            if (
                solver["native_status"],
                milp["incumbent_valid"],
            ) != expected_state or milp["incumbent_issue_codes"] != []:
                raise WarehouseLockedGroupProbeError(
                    f"MILP native status/incumbent contract invalid: {fixture_id}"
                )
            if row["phase"] == 1 and milp["phase2_exact_subcategory_spread"] is not None:
                raise WarehouseLockedGroupProbeError(
                    f"Phase-1 row carries Phase-2 spread: {fixture_id}"
                )
    actual = canonical_sha256({"domain": SCHEMA, "items": rows})
    if actual != report["aggregate_sha256"]:
        raise WarehouseLockedGroupProbeError(
            f"aggregate digest mismatch: expected {report['aggregate_sha256']}, got {actual}"
        )


def validate_receipt(
    receipt: dict[str, Any],
    report: dict[str, Any],
    report_bytes: bytes,
) -> None:
    _require_exact_fields(receipt, _RECEIPT_FIELDS, label="receipt")
    expected_constants = {
        "schema": RECEIPT_SCHEMA,
        "authority": AUTHORITY,
        "passed": True,
        "design_path": DESIGN_PATH,
        "design_sha256": DESIGN_SHA256,
        "preservation_manifest_path": PRESERVATION_MANIFEST_PATH,
        "preservation_manifest_sha256": PRESERVATION_MANIFEST_SHA256,
        "fixture_schema": FIXTURE_SCHEMA,
        "row_count": 17,
        "report_path": REPORT_PATH,
    }
    if any(receipt.get(key) != value for key, value in expected_constants.items()):
        raise WarehouseLockedGroupProbeError("receipt authority constants are invalid")
    if (
        receipt["fixture_bundle_sha256"] != report["fixture_bundle_sha256"]
        or receipt["aggregate_sha256"] != report["aggregate_sha256"]
        or receipt["report_raw_sha256"] != sha256_bytes(report_bytes)
        or receipt["source_owner_hashes"] != report["source_owner_hashes"]
        or receipt["toolchain"] != acceptance_toolchain()
    ):
        raise WarehouseLockedGroupProbeError("receipt does not bind the exact report/runtime")


__all__ = [
    "AUTHORITY",
    "DESIGN_PATH",
    "DESIGN_SHA256",
    "FIXTURE_IDS",
    "FIXTURE_SCHEMA",
    "NON_APPLICABLE_REASONS",
    "PRESERVATION_MANIFEST_PATH",
    "PRESERVATION_MANIFEST_SHA256",
    "RECEIPT_PATH",
    "RECEIPT_SCHEMA",
    "REPORT_PATH",
    "SCHEMA",
    "SOURCE_OWNER_PATHS",
    "WarehouseLockedGroupProbeError",
    "build_probe_artifacts",
    "build_probe_receipt",
    "build_probe_report",
    "classify_native_milp_result",
    "directed_fixtures",
    "formal_check_deserialized_candidate",
    "render_artifact",
    "validate_receipt",
    "validate_report",
    "verify_existing_artifact_bytes",
]
