from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from random import Random
from types import SimpleNamespace
from typing import Any

import highspy
import pytest

from scion.problems.warehouse_delivery import w2_preservation as preservation_module
from scion.problems.warehouse_delivery import locked_group_probe as probe_module
from scion.problems.warehouse_delivery.locked_group_probe import (
    DESIGN_SHA256,
    FIXTURE_IDS,
    NON_APPLICABLE_REASONS,
    RECEIPT_PATH,
    RECEIPT_SCHEMA,
    REPORT_PATH,
    SCHEMA,
    SOURCE_OWNER_PATHS,
    WarehouseLockedGroupProbeError,
    build_probe_artifacts,
    classify_native_milp_result,
    directed_fixtures,
    formal_check_deserialized_candidate,
    render_artifact,
    validate_receipt,
    validate_report,
    verify_existing_artifact_bytes,
)
from scion.problems.warehouse_delivery.w2_preservation import (
    WarehouseW2PreservationError,
    acceptance_toolchain,
    canonical_sha256,
    docstring_stripped_ast_sha256,
    load_unique_yaml,
    repository_root,
    sha256_bytes,
    verify_w2_preservation,
)
from scion.problems.warehouse_delivery.protocol_population import (
    reconcile_warehouse_protocol_population_from_paths,
)


@pytest.fixture(scope="module")
def probe_artifacts() -> tuple[bytes, bytes, dict[str, Any], dict[str, Any]]:
    return build_probe_artifacts()


def test_preservation_and_owner_equivalence_pass_on_frozen_checkout() -> None:
    result = verify_w2_preservation()
    assert result["passed"] is True
    assert result["manifest_sha256"] == (
        "0ee66091942583c2f499f83338a96abeff51e53b9583afe03fce3356a890dfc9"
    )
    assert result["toolchain"] == acceptance_toolchain()
    assert result["toolchain"]["pulp_version"] == "3.3.0"
    assert result["toolchain"]["highspy_distribution_version"] == "1.14.0"
    assert result["r3_database_access"] == "raw_bytes_only_no_sqlite_open"
    assert result["exact_protected_count"] == 49


def test_toolchain_mismatch_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(preservation_module.platform, "python_version", lambda: "0.0.0")
    with pytest.raises(WarehouseW2PreservationError, match="toolchain mismatch"):
        acceptance_toolchain()


def test_yaml_loader_and_exact_scalar_contract_fail_closed() -> None:
    with pytest.raises(WarehouseW2PreservationError, match="duplicate YAML key"):
        load_unique_yaml(b"a: 1\na: 2\n", label="duplicate fixture")

    valid = {
        "research_surfaces": [
            {"prompt": {"implementation_guidance": "one"}},
            {"prompt": {"implementation_guidance": "two"}},
        ]
    }
    sentinel = {"$allowed_scalar": "warehouse_locked_group_guidance_v1"}
    with pytest.raises(WarehouseW2PreservationError, match="exact contract path set"):
        preservation_module._mask_yaml_guidance(
            copy.deepcopy(valid),
            sentinel,
            allowed_scalar_paths=[
                "research_surfaces[0].prompt.implementation_guidance",
                "research_surfaces[2].prompt.implementation_guidance",
            ],
        )
    invalid_scalar = copy.deepcopy(valid)
    invalid_scalar["research_surfaces"][1]["prompt"]["implementation_guidance"] = None
    with pytest.raises(WarehouseW2PreservationError, match="YAML string scalar"):
        preservation_module._mask_yaml_guidance(
            invalid_scalar,
            sentinel,
            allowed_scalar_paths=[
                "research_surfaces[0].prompt.implementation_guidance",
                "research_surfaces[1].prompt.implementation_guidance",
            ],
        )


def test_docstring_ast_and_adapter_reverse_proofs_reject_code_drift(
    tmp_path: Path,
) -> None:
    source = '"""old"""\ndef f():\n    """first"""\n    return 1\n'
    doc_only = '"""new"""\ndef f():\n    """second"""\n    return 1\n'
    code_drift = '"""new"""\ndef f():\n    """second"""\n    return 2\n'
    assert docstring_stripped_ast_sha256(source) == docstring_stripped_ast_sha256(doc_only)
    assert docstring_stripped_ast_sha256(source) != docstring_stripped_ast_sha256(code_drift)

    root = repository_root()
    manifest = json.loads(
        (root / "scion/contracts/warehouse_w2_preservation_manifest.v1.json").read_text(
            encoding="utf-8"
        )
    )
    owners = manifest["allowed_semantic_text_owners"]
    entries = (
        owners["python_docstring_only"]
        + owners["python_exact_code_plus_docstrings"]
        + owners["yaml_guidance_only"]
        + owners["markdown"]
        + [owners["adapter_exact_reverse_replacement"]]
    )
    for entry in entries:
        destination = tmp_path / entry["path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / entry["path"], destination)
    adapter_path = tmp_path / owners["adapter_exact_reverse_replacement"]["path"]
    adapter_path.write_bytes(adapter_path.read_bytes() + b"\nUNREVIEWED_EXECUTABLE = True\n")
    with pytest.raises(WarehouseW2PreservationError, match="adapter reverse-normalized"):
        preservation_module._verify_allowed_owners(tmp_path, manifest)


def test_r3_hash_drift_fails_without_opening_sqlite(tmp_path: Path) -> None:
    root = repository_root()
    manifest = json.loads(
        (root / "scion/contracts/warehouse_w2_preservation_manifest.v1.json").read_text(
            encoding="utf-8"
        )
    )
    manifest["r3"]["evidence_files"][0]["sha256"] = "0" * 64
    manifest_path = tmp_path / "tampered-preservation.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(WarehouseW2PreservationError, match="R3 .* hash mismatch"):
        verify_w2_preservation(manifest_path)


def test_directed_fixture_contract_is_exact_and_covers_required_milp_rows() -> None:
    fixtures = directed_fixtures()
    assert tuple(fixture["fixture_id"] for fixture in fixtures) == FIXTURE_IDS
    by_id = {fixture["fixture_id"]: fixture for fixture in fixtures}
    required = {
        "02_multi_group_whole_move",
        "03_group_merge_free",
        "04_two_groups_merge",
        "05_singleton_group_move",
        "06_empty_string_group_phase2",
        "07_group_split",
        "08_group_partial_move",
        "16_hazard_h5_h8_family",
        "17_amount_limit_h6",
    }
    assert all(by_id[fixture_id]["milp_contract"]["applicable"] for fixture_id in required)
    assert {
        fixture_id: by_id[fixture_id]["milp_contract"]["reason"]
        for fixture_id in NON_APPLICABLE_REASONS
    } == NON_APPLICABLE_REASONS
    assert by_id["06_empty_string_group_phase2"]["instance"]["orders"][0][
        "locked_vehicle_id"
    ] == ""
    assert by_id["17_amount_limit_h6"]["instance"]["amount_limits"] == {
        "DE,SEA": 1000.0
    }


def test_w1_exact_31_case_population_greedy_solutions_remain_feasible() -> None:
    root = repository_root()
    config = root / "scion/problems/warehouse_delivery"
    population = reconcile_warehouse_protocol_population_from_paths(
        config / "protocol_prod.yaml",
        config / "split_manifest_prod.yaml",
    )
    runtime = probe_module._load_runtime()
    case_count = 0
    order_count = 0
    for stage in population["populations"]:
        for case in stage["cases"]:
            instance = runtime.adapter.load_instance(case["resolved_path"])
            solution = runtime.greedy_init.greedy_init(instance, Random(20260718))
            result = runtime.oracle.check_feasibility(
                solution,
                instance,
                phase=instance.phase,
            )
            assert result.is_feasible, (case["stable_case_id"], result.violations)
            case_count += 1
            order_count += len(instance.orders)
    assert (case_count, order_count) == (31, 8387)


def test_every_non_authoritative_native_status_is_indeterminate() -> None:
    authoritative = {
        highspy.HighsModelStatus.kOptimal,
        highspy.HighsModelStatus.kInfeasible,
    }
    statuses = [
        getattr(highspy.HighsModelStatus, name)
        for name in dir(highspy.HighsModelStatus)
        if name.startswith("k")
    ]
    for status in statuses:
        result, incumbent_valid, issues = classify_native_milp_result(
            highspy, status, []
        )
        if status in authoritative:
            continue
        assert result == "fixed_candidate_indeterminate"
        assert incumbent_valid is None
        assert "native_status_non_authoritative" in issues

    result, incumbent_valid, issues = classify_native_milp_result(
        highspy,
        highspy.HighsModelStatus.kOptimal,
        ["x_fixed_value_mismatch"],
    )
    assert (result, incumbent_valid, issues) == (
        "fixed_candidate_indeterminate",
        False,
        ["x_fixed_value_mismatch"],
    )
    result, incumbent_valid, issues = classify_native_milp_result(
        highspy,
        highspy.HighsModelStatus.kInfeasible,
        ["solver_exception"],
    )
    assert (result, incumbent_valid, issues) == (
        "fixed_candidate_indeterminate",
        None,
        ["solver_exception"],
    )


def test_nonfinite_and_nonnumeric_incumbent_values_fail_closed() -> None:
    runtime = SimpleNamespace(pulp=SimpleNamespace(value=lambda variable: variable))
    variables = {
        "x": {(0, 0): float("nan")},
        "y": {0: float("inf")},
        "z": {(0, "T3"): "not-a-number"},
    }
    fixed = {
        "x": [{"order_id": "O1", "slot": 0, "value": 1}],
        "y": [{"slot": 0, "value": 1}],
        "z": [{"slot": 0, "vehicle_type": "T3", "value": 1}],
    }
    issues = probe_module._incumbent_issue_codes(
        runtime,
        variables,
        fixed,
        {"O1": 0},
    )
    assert issues == [
        "x_incumbent_value_non_finite",
        "y_incumbent_value_non_finite",
        "z_incumbent_value_non_numeric",
    ]
    result, incumbent_valid, classified = classify_native_milp_result(
        highspy,
        highspy.HighsModelStatus.kOptimal,
        issues,
    )
    assert result == "fixed_candidate_indeterminate"
    assert incumbent_valid is False
    assert classified == issues


def test_adapter_deserialized_formal_path_passes_actual_phase_two() -> None:
    observed: list[tuple[object, object, int]] = []

    def check(solution: object, instance: object, *, phase: int) -> str:
        observed.append((solution, instance, phase))
        return "formal-result"

    solution = object()
    instance = SimpleNamespace(phase=2)
    runtime = SimpleNamespace(oracle=SimpleNamespace(check_feasibility=check))
    artifact = SimpleNamespace(normalized_solution=solution)
    assert formal_check_deserialized_candidate(runtime, artifact, instance) == (
        "formal-result"
    )
    assert observed == [(solution, instance, 2)]


def test_probe_cross_owner_and_native_fixed_candidate_milp_agree(
    probe_artifacts: tuple[bytes, bytes, dict[str, Any], dict[str, Any]],
) -> None:
    _report_bytes, _receipt_bytes, report, receipt = probe_artifacts
    validate_report(report)
    assert report["schema"] == SCHEMA
    assert report["passed"] is True
    assert report["row_count"] == 17
    assert tuple(report["source_owner_hashes"]) == SOURCE_OWNER_PATHS
    rows = {row["fixture_id"]: row for row in report["rows"]}
    for row in rows.values():
        assert row["passed"] is True
        assert all(row["checks"].values())
        assert "elapsed_seconds" not in row["fixed_candidate_milp"]
        assert "error" not in row["fixed_candidate_milp"]
    assert rows["06_empty_string_group_phase2"]["phase2_initialization"]["passed"] is True
    assert rows["16_hazard_h5_h8_family"]["oracle"] == {
        "feasible": False,
        "constraint_family": "H5/H8",
    }
    for fixture_id in (
        "02_multi_group_whole_move",
        "03_group_merge_free",
        "04_two_groups_merge",
        "05_singleton_group_move",
        "06_empty_string_group_phase2",
    ):
        milp = rows[fixture_id]["fixed_candidate_milp"]
        assert milp["result"] == "fixed_candidate_feasible"
        assert milp["incumbent_valid"] is True
        assert milp["solver"]["native_status"] == "HighsModelStatus.kOptimal"
    for fixture_id in ("07_group_split", "08_group_partial_move", "17_amount_limit_h6"):
        milp = rows[fixture_id]["fixed_candidate_milp"]
        assert milp["result"] == "fixed_candidate_infeasible"
        assert milp["incumbent_valid"] is None
        assert milp["solver"]["native_status"] == "HighsModelStatus.kInfeasible"
    assert receipt["design_sha256"] == DESIGN_SHA256
    assert receipt["schema"] == RECEIPT_SCHEMA


def test_receipted_report_excludes_observational_noise(
    probe_artifacts: tuple[bytes, bytes, dict[str, Any], dict[str, Any]],
) -> None:
    report_bytes, _receipt_bytes, report, _receipt = probe_artifacts
    forbidden_keys = {
        "elapsed_seconds",
        "violations",
        "reasons",
        "error",
        "exception",
        "output_path",
        "preservation",
        "adapter_guidance",
    }

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            assert forbidden_keys.isdisjoint(value)
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(report)
    assert report_bytes.endswith(b"\n") and not report_bytes.endswith(b"\n\n")


def test_closed_report_and_receipt_schemas_reject_unknown_fields(
    probe_artifacts: tuple[bytes, bytes, dict[str, Any], dict[str, Any]],
) -> None:
    report_bytes, _receipt_bytes, report, receipt = probe_artifacts
    bad_report = copy.deepcopy(report)
    bad_report["unexpected"] = True
    with pytest.raises(WarehouseLockedGroupProbeError, match="closed schema"):
        validate_report(bad_report)
    bad_receipt = copy.deepcopy(receipt)
    bad_receipt["unexpected"] = True
    with pytest.raises(WarehouseLockedGroupProbeError, match="closed schema"):
        validate_receipt(bad_receipt, report, report_bytes)


def test_self_consistent_fabricated_report_and_receipt_fail_complete_replay(
    probe_artifacts: tuple[bytes, bytes, dict[str, Any], dict[str, Any]],
) -> None:
    _report_bytes, _receipt_bytes, report, receipt = probe_artifacts
    fabricated_report = copy.deepcopy(report)
    fabricated_report["rows"][0]["candidate"]["vehicle_types"]["LOCK-A"] = "T5"
    fabricated_report["aggregate_sha256"] = canonical_sha256(
        {"domain": SCHEMA, "items": fabricated_report["rows"]}
    )
    validate_report(fabricated_report)
    fabricated_report_bytes = render_artifact(fabricated_report)
    fabricated_receipt = copy.deepcopy(receipt)
    fabricated_receipt["aggregate_sha256"] = fabricated_report["aggregate_sha256"]
    fabricated_receipt["report_raw_sha256"] = sha256_bytes(fabricated_report_bytes)
    validate_receipt(fabricated_receipt, fabricated_report, fabricated_report_bytes)
    with pytest.raises(WarehouseLockedGroupProbeError, match="complete current-state replay"):
        verify_existing_artifact_bytes(
            fabricated_report_bytes,
            render_artifact(fabricated_receipt),
        )


def test_tracked_probe_and_receipt_byte_replay_current_authority(
    probe_artifacts: tuple[bytes, bytes, dict[str, Any], dict[str, Any]],
) -> None:
    report_bytes, receipt_bytes, report, receipt = probe_artifacts
    root = repository_root()
    assert (root / REPORT_PATH).read_bytes() == report_bytes
    assert (root / RECEIPT_PATH).read_bytes() == receipt_bytes
    result = verify_existing_artifact_bytes(report_bytes, receipt_bytes)
    assert result["passed"] is True
    assert result["aggregate_sha256"] == report["aggregate_sha256"]
    assert result["report_raw_sha256"] == receipt["report_raw_sha256"]


def test_cli_rejects_caller_selected_acceptance_paths() -> None:
    root = repository_root()
    completed = subprocess.run(
        [
            sys.executable,
            str(root / "scion/tools/warehouse_locked_group_probe.py"),
            "--generate",
            "--output",
            "/tmp/not-authority.json",
        ],
        cwd=root,
        env={**os.environ, "PYTHONPATH": str(root / "scion")},
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode != 0
    assert "unrecognized arguments: --output" in completed.stderr
