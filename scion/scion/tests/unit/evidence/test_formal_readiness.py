from __future__ import annotations

from pathlib import Path

from scion.evidence.final_evidence_refs import (
    FINAL_EVIDENCE_REASON_NORMAL_COMPLETION,
    FINAL_EVIDENCE_REASON_PENDING_EXTERNAL,
    FINAL_EVIDENCE_STATUS_NON_FORMAL_CLOSED,
    FINAL_EVIDENCE_STATUS_PENDING_EXTERNAL,
    build_final_evidence_closure_refs,
)
from scion.evidence.formal_readiness import validate_formal_readiness


def _complete_refs(root: Path) -> dict[str, object]:
    return {
        "final_quality": {
            "schema": "scion.final_quality_manifest.v1",
            "package_type": "final_quality",
            "problem_id": "cvrp",
            "campaign_id": "camp-1",
            "baseline_label": "baseline-v0",
            "candidate_label": "candidate-v1",
            "n_cases": 3,
            "artifacts": {
                "manifest": str(root / "evidence_manifest.json"),
                "final_quality_json": str(root / "final_quality.json"),
                "final_quality_csv": str(root / "final_quality.csv"),
                "per_case_quality_csv": str(root / "per_case_quality.csv"),
                "runtime_summary": str(root / "runtime_summary.json"),
                "failure_summary": str(root / "failure_summary.json"),
            },
        }
    }


def test_no_final_evidence_refs_is_not_formal_ready() -> None:
    report = validate_formal_readiness({})

    assert report.formal_ready is False
    assert report.missing == ("final_evidence_refs",)
    assert report.status == "missing_final_evidence_refs"


def test_non_formal_closure_is_closed_without_missing_package() -> None:
    refs = build_final_evidence_closure_refs(
        reason="short stress validation completed without formal final evaluation",
        reason_code=FINAL_EVIDENCE_REASON_NORMAL_COMPLETION,
    )

    report = validate_formal_readiness(refs)

    assert report.formal_ready is False
    assert report.missing == ()
    assert report.status == FINAL_EVIDENCE_STATUS_NON_FORMAL_CLOSED
    assert report.reason_code == FINAL_EVIDENCE_REASON_NORMAL_COMPLETION


def test_pending_external_closure_still_requires_formal_package() -> None:
    refs = build_final_evidence_closure_refs(
        reason="formal final evaluation has not run",
        reason_code=FINAL_EVIDENCE_REASON_PENDING_EXTERNAL,
        status=FINAL_EVIDENCE_STATUS_PENDING_EXTERNAL,
        required_for_formal_readiness=True,
    )

    report = validate_formal_readiness(refs)

    assert report.formal_ready is False
    assert report.missing == ("final_evidence_refs.package",)
    assert report.status == "missing_final_evidence_package"


def test_missing_one_required_artifact_is_not_formal_ready(tmp_path: Path) -> None:
    refs = _complete_refs(tmp_path)
    refs["final_quality"]["artifacts"]["runtime_summary"] = None  # type: ignore[index]

    report = validate_formal_readiness(refs)

    assert report.formal_ready is False
    assert report.missing == ("final_quality.artifacts.runtime_summary",)
    assert report.status == "incomplete_final_evidence_package"


def test_complete_final_evidence_package_is_formal_ready(tmp_path: Path) -> None:
    refs = _complete_refs(tmp_path)

    report = validate_formal_readiness(refs)

    assert report.formal_ready is True
    assert report.missing == ()
    assert report.status == "formal_ready"
    assert report.refs == refs
