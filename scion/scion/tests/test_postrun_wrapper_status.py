from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


SCION_DIR = Path(__file__).resolve().parents[2]
TOOL = SCION_DIR / "tools" / "write_postrun_wrapper_status.py"


def _load_tool_module():
    spec = importlib.util.spec_from_file_location("write_postrun_wrapper_status", TOOL)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_status_preserves_existing_resume_snapshot_metadata(
    tmp_path: Path,
) -> None:
    tool = _load_tool_module()

    status = tool.build_status(
        {
            "schema": "outer-wrapper.v1",
            "status": "running",
            "resume_from_campaign": "/tmp/source-campaign",
            "resume_snapshot_ref": "resume_snapshot/resume_source_manifest.v1.json",
            "copied_campaign_status_present": True,
            "copied_campaign_summary_present": True,
        },
        wrapper_exit_code=0,
        campaign_exit_code=0,
        postrun_reports_exit_code=0,
        postrun_readiness_exit_code=0,
        postrun_report_dir=tmp_path / "postrun_acceptance",
        postrun_readiness_path=tmp_path / "ready.json",
    )

    assert status["postrun_acceptance_status"] == "ready"
    assert status["resume_from_campaign"] == "/tmp/source-campaign"
    assert (
        status["resume_snapshot_ref"]
        == "resume_snapshot/resume_source_manifest.v1.json"
    )
    assert status["copied_campaign_status_present"] is True
    assert status["copied_campaign_summary_present"] is True


def test_build_status_restores_resume_snapshot_metadata_after_campaign_status_copy(
    tmp_path: Path,
) -> None:
    tool = _load_tool_module()

    status = tool.build_status(
        {"schema": "scion.run_wrapper_audit.v1", "status": "finished"},
        wrapper_exit_code=0,
        campaign_exit_code=0,
        postrun_reports_exit_code=0,
        postrun_readiness_exit_code=0,
        postrun_report_dir=tmp_path / "postrun_acceptance",
        postrun_readiness_path=tmp_path / "ready.json",
        resume_from_campaign="/tmp/source-campaign",
        resume_snapshot_ref="resume_snapshot/resume_source_manifest.v1.json",
        copied_campaign_status_present=True,
        copied_campaign_summary_present=True,
    )

    assert status["resume_from_campaign"] == "/tmp/source-campaign"
    assert (
        status["resume_snapshot_ref"]
        == "resume_snapshot/resume_source_manifest.v1.json"
    )
    assert status["copied_campaign_status_present"] is True
    assert status["copied_campaign_summary_present"] is True


def test_write_status_cli_projects_resume_snapshot_metadata(tmp_path: Path) -> None:
    output = tmp_path / "run_status.json"
    output.write_text(
        json.dumps({"schema": "scion.run_wrapper_audit.v1", "status": "finished"}),
        encoding="utf-8",
    )
    tool = _load_tool_module()

    rc = tool.main(
        [
            "--output",
            str(output),
            "--wrapper-exit-code",
            "0",
            "--campaign-exit-code",
            "0",
            "--postrun-reports-exit-code",
            "0",
            "--postrun-readiness-exit-code",
            "0",
            "--postrun-report-dir",
            str(tmp_path / "postrun_acceptance"),
            "--postrun-readiness-path",
            str(tmp_path / "ready.json"),
            "--resume-from-campaign",
            "/tmp/source-campaign",
            "--resume-snapshot-ref",
            "resume_snapshot/resume_source_manifest.v1.json",
            "--copied-campaign-status-present",
            "1",
            "--copied-campaign-summary-present",
            "1",
        ]
    )

    assert rc == 0
    status = json.loads(output.read_text(encoding="utf-8"))
    assert status["resume_from_campaign"] == "/tmp/source-campaign"
    assert (
        status["resume_snapshot_ref"]
        == "resume_snapshot/resume_source_manifest.v1.json"
    )
    assert status["copied_campaign_status_present"] is True
    assert status["copied_campaign_summary_present"] is True
