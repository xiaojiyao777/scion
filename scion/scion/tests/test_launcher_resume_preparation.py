from __future__ import annotations

import json
from pathlib import Path

from scion.launcher.resume import prepare_launcher_campaign, prepare_resumed_campaign


def test_prepare_resumed_campaign_quarantines_terminal_artifacts(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source-campaign"
    run_root = tmp_path / "run"
    campaign_dir = run_root / "campaign"
    (source / "champions" / "champion_v1").mkdir(parents=True)
    (source / "champions" / "champion_v1" / "registry.yaml").write_text(
        "operators: {}\n",
        encoding="utf-8",
    )
    (source / "artifacts" / "branch_evidence").mkdir(parents=True)
    (source / "artifacts" / "branch_evidence" / "branch-a.json").write_text(
        "{}",
        encoding="utf-8",
    )
    (source / "artifacts" / "formal_candidates").mkdir(parents=True)
    (source / "artifacts" / "formal_candidates" / "index.jsonl").write_text(
        '{"branch_id":"branch-a"}\n',
        encoding="utf-8",
    )
    (source / "scion.db").write_text("db", encoding="utf-8")
    (source / "run_status.json").write_text('{"status":"finished"}', encoding="utf-8")
    (source / "status.json").write_text('{"stopped":true}', encoding="utf-8")
    (source / "campaign_summary.json").write_text(
        '{"run_complete":true}',
        encoding="utf-8",
    )
    (source / "exit.txt").write_text("WRAPPER_EXIT_STATUS:0\n", encoding="utf-8")

    preparation = prepare_resumed_campaign(
        resume_source=source,
        campaign_dir=campaign_dir,
        run_root=run_root,
    )

    assert (campaign_dir / "scion.db").read_text(encoding="utf-8") == "db"
    assert (campaign_dir / "champions" / "champion_v1" / "registry.yaml").is_file()
    assert (
        campaign_dir / "artifacts" / "branch_evidence" / "branch-a.json"
    ).is_file()
    for ref in (
        "run_status.json",
        "status.json",
        "campaign_summary.json",
        "exit.txt",
        "artifacts/formal_candidates/index.jsonl",
    ):
        assert not (campaign_dir / ref).exists()
        assert (run_root / "resume_snapshot" / "campaign" / ref).is_file()

    manifest = json.loads(preparation.manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "scion.launcher_resume_preparation.v1"
    assert manifest["resume_from_campaign"] == str(source)
    assert preparation.manifest_ref(run_root) == (
        "resume_snapshot/resume_source_manifest.v1.json"
    )
    assert preparation.source_had("run_status.json") is True
    assert preparation.source_had("campaign_summary.json") is True
    assert {
        item["original_ref"] for item in manifest["terminal_artifacts"]
    } == {
        "run_status.json",
        "status.json",
        "campaign_summary.json",
        "exit.txt",
        "artifacts/formal_candidates/index.jsonl",
    }


def test_prepare_launcher_campaign_returns_shared_resume_env(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source-campaign"
    run_root = tmp_path / "run"
    campaign_dir = run_root / "campaign"
    source.mkdir()
    (source / "scion.db").write_text("db", encoding="utf-8")
    (source / "run_status.json").write_text("{}", encoding="utf-8")
    (source / "campaign_summary.json").write_text("{}", encoding="utf-8")

    state = prepare_launcher_campaign(
        resume_from_campaign=source,
        campaign_dir=campaign_dir,
        run_root=run_root,
    )

    assert state.env() == {
        "RESUME_FROM_CAMPAIGN": str(source.resolve()),
        "RESUME_SNAPSHOT_MANIFEST_REF": (
            "resume_snapshot/resume_source_manifest.v1.json"
        ),
        "RESUME_COPIED_CAMPAIGN_STATUS_PRESENT": 1,
        "RESUME_COPIED_CAMPAIGN_SUMMARY_PRESENT": 1,
    }
    assert (campaign_dir / "scion.db").is_file()
    assert not (campaign_dir / "run_status.json").exists()
    assert (run_root / "resume_snapshot" / "campaign" / "run_status.json").is_file()
