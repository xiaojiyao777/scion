from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys

import pytest

from scion.problems.cvrp.evidence import b1_comparison as closer

TOOL_PATH = Path(__file__).resolve().parents[4] / "tools" / "cvrp_b1_comparison.py"
SEALED_ROOT = Path(closer.CANONICAL_INPUT_ROOT)


def _load_tool():
    module_name = f"cvrp_b1_comparison_tool_{id(object())}"
    spec = importlib.util.spec_from_file_location(module_name, TOOL_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _require_sealed_root() -> Path:
    if not SEALED_ROOT.is_dir():
        pytest.skip("sealed CVRP B1 root is not present on this host")
    return SEALED_ROOT


def _linked_evidence_root(tmp_path: Path) -> Path:
    source = _require_sealed_root()
    target = tmp_path / closer.ROOT_NAME
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        source,
        target,
        copy_function=os.link,
        ignore=shutil.ignore_patterns(closer.REPORT_NAME, closer.RECEIPT_NAME),
    )
    return target


def _validate_replica(root: Path) -> None:
    manifest = json.loads((root / "manifest.json").read_text())
    results = json.loads((root / "results.json").read_text())
    receipt = json.loads((root / "matrix.closed.receipt.json").read_text())
    closer._validate_integrity(root, manifest, results, receipt)


def test_sealed_b1_build_closes_integrity_and_fixed_case_major_views() -> None:
    artifacts = closer.build_comparison_artifacts(_require_sealed_root())
    report = artifacts.report

    assert report["integrity"]["status"] == "passed"
    assert report["integrity"]["job_count"] == 256
    assert {
        view_id: view["row_count"] for view_id, view in report["views"].items()
    } == closer.VIEW_EXPECTED_ROWS
    assert report["host_overlap"]["clean_host_claim"] is False
    assert report["host_overlap"]["row_counts"] == {
        "clean_after": 40,
        "clean_before": 174,
        "normal_priority_overlap": 38,
        "reduced_priority_end_unknown": 4,
    }

    for view_id in closer.VIEW_ORDER:
        contrasts = report["views"][view_id]["paired_vs_canonical"]
        assert set(contrasts) == set(closer.COMPARISON_PROFILES)
        for contrast in contrasts.values():
            assert contrast["primary_unit"] == "case"
            assert contrast["case_equal_weighted"]["case_count"] == len(
                contrast["case_estimands"]
            )
            assert "seed_pooled_diagnostics_only" in contrast

    assessment = report["acceptance_assessment"]
    assert assessment["verdict"] == "accepted_conservative_scope"
    assert assessment["f1_unlocked_by_closer_verdict"] is True
    assert assessment["main_direction_sensitivity_consistent"] is True
    assert assessment["normal_overlap_reversed_main_interaction"] is False
    assert set(assessment["main_direction_by_view"]) == set(
        closer.MAIN_COMPARISON_PROFILES
    )
    assert artifacts.receipt["acceptance_verdict"] == "accepted_conservative_scope"
    assert artifacts.receipt["report_raw_sha256"] == closer.sha256_bytes(
        artifacts.report_bytes
    )
    assert set(artifacts.receipt["closer_source_hashes"]) == set(
        closer.CLOSER_SOURCE_PATHS
    )
    assert len(artifacts.receipt["closer_source_identity_sha256"]) == 64
    assert len(artifacts.receipt["ordered_raw_identities"]) == 256
    assert b"DecisionFeatures" not in artifacts.report_bytes


def test_lexicographic_quality_ignores_route_count_and_uses_exact_tolerances() -> None:
    canonical = {"fleet_violation": 0.0, "route_count": 8, "total_distance": 100.0}
    more_routes_but_shorter = {
        "fleet_violation": 0.0,
        "route_count": 99,
        "total_distance": 99.0,
    }
    assert (
        closer._lexicographic_quality_outcome(canonical, more_routes_but_shorter)
        == "profile_better"
    )
    assert (
        closer._lexicographic_quality_outcome(
            canonical,
            {"fleet_violation": 0.0, "route_count": 1, "total_distance": 100.0005},
        )
        == "tie"
    )
    assert (
        closer._lexicographic_quality_outcome(
            canonical,
            {"fleet_violation": 1e-12, "route_count": 1, "total_distance": 1.0},
        )
        == "canonical_better"
    )


def test_fixed_view_membership_is_whole_quartets() -> None:
    artifacts = closer.build_comparison_artifacts(_require_sealed_root())
    views = artifacts.receipt["view_membership"]

    boundary = {
        (item["case_id"], item["seed"])
        for item in views["normal_priority_boundary_excluded_248"]["quartet_identities"]
    }
    assert ("CMT3", 59) not in boundary
    assert ("M-n200-k17", 11) not in boundary
    assert ("M-n200-k17", 29) in boundary

    clean = views["conservative_clean_212"]
    assert clean["row_count"] == 212
    manifest = json.loads((SEALED_ROOT / "manifest.json").read_text())
    ordinal_by_job = {
        row["job_id"]: row["execution_ordinal"] for row in manifest["execution_jobs"]
    }
    assert not any(
        174 <= ordinal_by_job[job_id] <= 215 for job_id in clean["ordered_job_ids"]
    )
    balanced = {
        item["case_id"]
        for item in views["normal_overlap_balanced_32"]["quartet_identities"]
    }
    assert balanced == {"CMT4", "M-n151-k12"}


def test_raw_digest_tamper_fails_closed(tmp_path: Path) -> None:
    root = _linked_evidence_root(tmp_path)
    raw_path = next((root / "raw").iterdir())
    original = raw_path.read_bytes()
    raw_path.unlink()
    raw_path.write_bytes(original + b"\n")

    with pytest.raises(
        closer.CvrpB1ComparisonError, match="raw receipt identity drift"
    ):
        _validate_replica(root)
    try:
        _validate_replica(root)
    except closer.CvrpB1ComparisonError as exc:
        rejected = closer.integrity_reject_verdict(exc)
    assert rejected == {
        "passed": False,
        "classification": "integrity_reject",
        "f1_unlocked": False,
        "comparison_artifacts_emitted": False,
        "error_type": "CvrpB1ComparisonError",
        "error": rejected["error"],
    }


def test_missing_snapshot_and_extra_raw_directory_fail_closed(tmp_path: Path) -> None:
    missing = _linked_evidence_root(tmp_path / "missing")
    for directory in (
        missing / "authority_snapshot",
        *(
            path
            for path in (missing / "authority_snapshot").rglob("*")
            if path.is_dir()
        ),
    ):
        directory.chmod(0o700)
    shutil.rmtree(missing / "authority_snapshot")
    with pytest.raises(closer.CvrpB1ComparisonError, match="authority snapshot"):
        _validate_replica(missing)

    extra = _linked_evidence_root(tmp_path / "extra")
    (extra / "raw").chmod(0o700)
    retry = extra / "raw" / "retry-evidence"
    retry.mkdir()
    (retry / "duplicate.json").write_text("{}\n")
    with pytest.raises(closer.CvrpB1ComparisonError, match="extra entries"):
        _validate_replica(extra)


def test_byte_replay_rejects_report_or_receipt_drift() -> None:
    artifacts = closer.build_comparison_artifacts(_require_sealed_root())
    accepted = closer.verify_existing_artifact_bytes(
        SEALED_ROOT, artifacts.report_bytes, artifacts.receipt_bytes
    )
    assert accepted["acceptance_verdict"] == "accepted_conservative_scope"

    with pytest.raises(closer.CvrpB1ComparisonError, match="report differs"):
        closer.verify_existing_artifact_bytes(
            SEALED_ROOT, artifacts.report_bytes + b"\n", artifacts.receipt_bytes
        )
    with pytest.raises(closer.CvrpB1ComparisonError, match="receipt differs"):
        closer.verify_existing_artifact_bytes(
            SEALED_ROOT, artifacts.report_bytes, artifacts.receipt_bytes + b"\n"
        )


def test_publication_is_no_replace_and_recovers_exact_report_only_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = _load_tool()
    artifacts = closer.build_comparison_artifacts(_require_sealed_root())
    monkeypatch.setattr(tool, "build_comparison_artifacts", lambda _root: artifacts)
    monkeypatch.setattr(
        tool,
        "verify_existing_artifact_bytes",
        lambda _root, _report, _receipt: {"passed": True},
    )
    root = _linked_evidence_root(tmp_path / "first")
    published = tool._publish(root)
    assert published["publication"] == "report_then_receipt_published_no_replace"
    assert tool._check_existing(root)["passed"] is True
    with pytest.raises(closer.CvrpB1ComparisonError, match="already exist"):
        tool._publish(root)
    assert tool.main(["--input-root", str(root), "--check-existing"]) == 2

    recovery_root = _linked_evidence_root(tmp_path / "recovery")
    (recovery_root / closer.REPORT_NAME).write_bytes(artifacts.report_bytes)
    recovered = tool._publish(recovery_root)
    assert recovered["publication"] == "receipt_recovered_after_exact_report_replay"
    assert tool._check_existing(recovery_root)["passed"] is True


def test_partial_report_and_receipt_without_report_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tool = _load_tool()
    artifacts = closer.build_comparison_artifacts(_require_sealed_root())
    monkeypatch.setattr(tool, "build_comparison_artifacts", lambda _root: artifacts)
    partial_root = _linked_evidence_root(tmp_path / "partial")
    (partial_root / closer.REPORT_NAME).write_bytes(b"partial")
    with pytest.raises(closer.CvrpB1ComparisonError, match="partial or differs"):
        tool._publish(partial_root)

    orphan_root = _linked_evidence_root(tmp_path / "orphan")
    (orphan_root / closer.RECEIPT_NAME).write_bytes(b"orphan")
    with pytest.raises(
        closer.CvrpB1ComparisonError, match="without its comparison report"
    ):
        tool._publish(orphan_root)

    symlink_root = _linked_evidence_root(tmp_path / "symlink")
    target = symlink_root / "outside-report.json"
    target.write_bytes(artifacts.report_bytes)
    (symlink_root / closer.REPORT_NAME).symlink_to(target)
    with pytest.raises(closer.CvrpB1ComparisonError, match="not a regular file"):
        tool._publish(symlink_root)
