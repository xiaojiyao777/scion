from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from scion.core.evidence_recorder import EvidenceRecorder
from scion.core.models import (
    ChampionState,
    Decision,
    HypothesisProposal,
    StepRecord,
)
from scion.core.public_refs import contains_absolute_path
from scion.evidence import (
    CvrpEvidencePackageResult,
    FinalQualityPackage,
    attach_final_evidence_package,
    build_final_evidence_refs,
)
from scion.evidence.final_evidence_refs import (
    FINAL_EVIDENCE_CLOSURE_SCHEMA,
    FINAL_EVIDENCE_REASON_NORMAL_COMPLETION,
    FINAL_EVIDENCE_STATUS_NON_FORMAL_CLOSED,
)


_ARTIFACT_KEYS = (
    "manifest",
    "final_quality_json",
    "final_quality_csv",
    "per_case_quality_csv",
    "runtime_summary",
    "failure_summary",
)


def _manifest(**overrides: object) -> dict[str, object]:
    manifest: dict[str, object] = {
        "schema": "scion.final_quality_manifest.v1",
        "package_type": "final_quality",
        "problem_id": "cvrp",
        "campaign_id": "camp-1",
        "baseline_label": "baseline-v0",
        "candidate_label": "candidate-v1",
        "n_cases": 3,
    }
    manifest.update(overrides)
    return manifest


def _artifact_paths(root: Path) -> dict[str, Path]:
    return {
        "manifest": root / "evidence_manifest.json",
        "final_quality_json": root / "final_quality.json",
        "final_quality_csv": root / "final_quality.csv",
        "per_case_quality_csv": root / "per_case_quality.csv",
        "runtime_summary": root / "runtime_summary.json",
        "failure_summary": root / "failure_summary.json",
    }


def _package_result(
    root: Path,
    *,
    manifest: dict[str, object] | None = None,
    artifacts: dict[str, object] | None = None,
) -> CvrpEvidencePackageResult:
    package = FinalQualityPackage(
        manifest=manifest or _manifest(),
        final_quality={},
        per_case_quality=(),
        runtime_summary={},
        failure_summary={},
    )
    return CvrpEvidencePackageResult(
        package=package,
        artifacts=artifacts if artifacts is not None else _artifact_paths(root),
    )


def _step() -> StepRecord:
    return StepRecord(
        round_num=1,
        branch_id="branch-1",
        hypothesis=HypothesisProposal(
            hypothesis_text="Improve route merge scoring.",
            change_locus="local_search",
            action="modify",
            target_file="operators/local_search.py",
        ),
        patch=None,
        contract_passed=True,
        verification_passed=True,
        protocol_result=None,
        decision=Decision.ABANDON,
        failure_stage=None,
        failure_detail=None,
    )


def _champion() -> ChampionState:
    return ChampionState(
        version=1,
        operator_pool={},
        solver_config_hash="solver-hash",
        code_snapshot_path="/tmp/champion",
        code_snapshot_hash="code-hash",
    )


def test_payload_contains_metadata_and_string_artifact_refs(tmp_path: Path) -> None:
    result = _package_result(tmp_path)

    payload = build_final_evidence_refs(result)

    refs = payload["final_quality"]
    assert refs["schema"] == "scion.final_quality_manifest.v1"
    assert refs["package_type"] == "final_quality"
    assert refs["problem_id"] == "cvrp"
    assert refs["campaign_id"] == "camp-1"
    assert refs["baseline_label"] == "baseline-v0"
    assert refs["candidate_label"] == "candidate-v1"
    assert refs["n_cases"] == 3
    assert set(refs["artifacts"]) == set(_ARTIFACT_KEYS)
    assert not refs["artifacts"]["manifest"].startswith("/")
    assert "evidence_manifest.json" in refs["artifacts"]["manifest"]
    assert all(isinstance(value, str) for value in refs["artifacts"].values())


def test_missing_manifest_fields_keep_stable_metadata_and_artifact_keys(
    tmp_path: Path,
) -> None:
    result = _package_result(
        tmp_path,
        manifest={"problem_id": "cvrp", "campaign_id": "camp-missing"},
        artifacts={"manifest": tmp_path / "evidence_manifest.json"},
    )

    payload = build_final_evidence_refs(result)

    refs = payload["final_quality"]
    assert refs["problem_id"] == "cvrp"
    assert refs["campaign_id"] == "camp-missing"
    assert refs["schema"] is None
    assert refs["package_type"] is None
    assert refs["baseline_label"] is None
    assert refs["candidate_label"] is None
    assert refs["n_cases"] is None
    assert set(refs["artifacts"]) == set(_ARTIFACT_KEYS)
    assert not refs["artifacts"]["manifest"].startswith("/")
    assert "evidence_manifest.json" in refs["artifacts"]["manifest"]
    assert refs["artifacts"]["final_quality_json"] is None
    assert refs["artifacts"]["final_quality_csv"] is None
    assert refs["artifacts"]["per_case_quality_csv"] is None
    assert refs["artifacts"]["runtime_summary"] is None
    assert refs["artifacts"]["failure_summary"] is None


def test_custom_label_nests_payload_under_that_label(tmp_path: Path) -> None:
    result = _package_result(tmp_path)

    payload = build_final_evidence_refs(result, label="cvrp_frozen_final")

    assert set(payload) == {"cvrp_frozen_final"}
    assert payload["cvrp_frozen_final"]["problem_id"] == "cvrp"


def test_attach_helper_updates_summary_refs_without_changing_step_schema(
    tmp_path: Path,
) -> None:
    recorder = EvidenceRecorder(campaign_id="camp-1", campaign_dir=tmp_path)
    result = _package_result(tmp_path / "evidence")
    before = recorder.write_campaign_summary(
        step_history=[_step()],
        round_num=1,
        champion=_champion(),
        stopped_reason="max_rounds_exhausted",
    )
    assert before["formal_readiness"] == {
        "formal_ready": False,
        "missing": [],
        "status": FINAL_EVIDENCE_STATUS_NON_FORMAL_CLOSED,
        "reason_code": FINAL_EVIDENCE_REASON_NORMAL_COMPLETION,
    }
    assert before["final_evidence_refs"]["schema"] == FINAL_EVIDENCE_CLOSURE_SCHEMA
    assert before["final_evidence_refs"]["status"] == (
        FINAL_EVIDENCE_STATUS_NON_FORMAL_CLOSED
    )
    assert before["final_evidence_refs"]["reason_code"] == (
        FINAL_EVIDENCE_REASON_NORMAL_COMPLETION
    )
    assert before["final_evidence_refs"]["required_for_formal_readiness"] is False
    assert "non-formal final evidence closure" in before["final_evidence_refs"]["reason"]
    assert not contains_absolute_path(before["final_evidence_refs"])
    before_step_keys = set(before["steps"][0])

    payload = attach_final_evidence_package(recorder, result)
    after = recorder.write_campaign_summary(
        step_history=[_step()],
        round_num=1,
        champion=_champion(),
    )

    assert payload == {"final_quality": after["final_evidence_refs"]["final_quality"]}
    assert after["final_evidence_refs"]["final_quality"]["artifacts"]["manifest"] == (
        "evidence/evidence_manifest.json"
    )
    assert after["formal_readiness"]["formal_ready"] is True
    assert after["formal_readiness"]["missing"] == []
    assert after["formal_readiness"]["status"] == "formal_ready"
    assert set(after["steps"][0]) == before_step_keys
    assert "final_evidence_refs" not in after["steps"][0]


def test_multiple_attach_calls_merge_labels_without_overwriting_other_labels(
    tmp_path: Path,
) -> None:
    recorder = EvidenceRecorder(campaign_id="camp-1", campaign_dir=tmp_path)
    final_result = _package_result(tmp_path / "final", manifest=_manifest(n_cases=2))
    frozen_result = _package_result(
        tmp_path / "frozen",
        manifest=_manifest(candidate_label="candidate-v2", n_cases=5),
    )

    attach_final_evidence_package(recorder, final_result, label="final_quality")
    attach_final_evidence_package(recorder, frozen_result, label="frozen_quality")
    summary = recorder.write_campaign_summary(
        step_history=[_step()],
        round_num=1,
        champion=_champion(),
    )

    refs = summary["final_evidence_refs"]
    assert set(refs) == {"final_quality", "frozen_quality"}
    assert refs["final_quality"]["n_cases"] == 2
    assert refs["final_quality"]["candidate_label"] == "candidate-v1"
    assert refs["frozen_quality"]["n_cases"] == 5
    assert refs["frozen_quality"]["candidate_label"] == "candidate-v2"


def test_extra_artifact_keys_are_preserved(tmp_path: Path) -> None:
    result = SimpleNamespace(
        package=SimpleNamespace(manifest=_manifest()),
        artifacts={**_artifact_paths(tmp_path), "notes": tmp_path / "notes.txt"},
    )

    payload = build_final_evidence_refs(result)

    assert not payload["final_quality"]["artifacts"]["notes"].startswith("/")
    assert "notes.txt" in payload["final_quality"]["artifacts"]["notes"]


def test_manual_final_evidence_refs_are_redacted_in_summary(tmp_path: Path) -> None:
    recorder = EvidenceRecorder(campaign_id="camp-1", campaign_dir=tmp_path)
    diagnostic_report = tmp_path / "diagnostics" / "final.json"

    summary = recorder.write_campaign_summary(
        step_history=[_step()],
        round_num=1,
        champion=_champion(),
        final_evidence_refs={
            "final_quality": {
                "problem_id": "cvrp",
                "n_cases": 1,
                "artifacts": {"manifest": tmp_path / "evidence_manifest.json"},
                "diagnostics": {
                    "report_path": diagnostic_report,
                    "report_uri": f"file://{diagnostic_report.as_posix()}",
                    "summary": (
                        f"report:{diagnostic_report}; "
                        f"uri=file://localhost{diagnostic_report.as_posix()}"
                    ),
                },
            }
        },
    )

    assert not contains_absolute_path(summary["final_evidence_refs"])
    manifest_ref = summary["final_evidence_refs"]["final_quality"]["artifacts"][
        "manifest"
    ]
    diagnostic_ref = summary["final_evidence_refs"]["final_quality"]["diagnostics"][
        "report_path"
    ]
    diagnostic_uri_ref = summary["final_evidence_refs"]["final_quality"][
        "diagnostics"
    ]["report_uri"]
    diagnostic_summary = summary["final_evidence_refs"]["final_quality"][
        "diagnostics"
    ]["summary"]
    assert manifest_ref == "evidence_manifest.json"
    assert not manifest_ref.startswith("/")
    assert diagnostic_ref == "diagnostics/final.json"
    assert diagnostic_uri_ref == "diagnostics/final.json"
    assert diagnostic_summary == (
        "report:diagnostics/final.json; uri=diagnostics/final.json"
    )
