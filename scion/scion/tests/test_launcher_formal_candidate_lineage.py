from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import pytest

from scion.launcher.resume import ResumePreparationError, prepare_resumed_campaign


def test_resume_flattens_inherited_index_across_hops(tmp_path: Path) -> None:
    source = tmp_path / "source" / "campaign"
    row = _write_candidate(source, "candidate-a")
    _write_index(source, [row])

    middle_root = tmp_path / "middle"
    prepare_resumed_campaign(
        resume_source=source,
        campaign_dir=middle_root / "campaign",
        run_root=middle_root,
    )
    final_root = tmp_path / "final"
    final = prepare_resumed_campaign(
        resume_source=middle_root / "campaign",
        campaign_dir=final_root / "campaign",
        run_root=final_root,
    )

    assert _read_snapshot_rows(middle_root) == [row]
    assert _read_snapshot_rows(final_root) == [row]
    assert not _live_index_path(final_root / "campaign").exists()
    item = _candidate_index_manifest_item(final.manifest_path)
    assert item["ownership_scope"] == "inherited_lineage_union"
    assert item["source_row_count"] == 1
    assert item["merged_row_count"] == 1
    assert [source["source_kind"] for source in item["source_indexes"]] == [
        "source_inherited_snapshot"
    ]


def test_resume_merges_inherited_and_live_indexes_with_stable_provenance(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source" / "campaign"
    inherited_row = _write_candidate(source, "candidate-a")
    _write_index(source, [inherited_row])
    middle_root = tmp_path / "middle"
    prepare_resumed_campaign(
        resume_source=source,
        campaign_dir=middle_root / "campaign",
        run_root=middle_root,
    )

    middle_campaign = middle_root / "campaign"
    live_row = _write_candidate(middle_campaign, "candidate-b")
    middle_live_index = _write_index(middle_campaign, [inherited_row, live_row])
    final_root = tmp_path / "final"
    preparation = prepare_resumed_campaign(
        resume_source=middle_campaign,
        campaign_dir=final_root / "campaign",
        run_root=final_root,
    )

    assert _read_snapshot_rows(final_root) == [inherited_row, live_row]
    item = _candidate_index_manifest_item(preparation.manifest_path)
    assert item["source_row_count"] == 3
    assert item["merged_row_count"] == 2
    assert [source["source_kind"] for source in item["source_indexes"]] == [
        "source_inherited_snapshot",
        "source_campaign_live",
    ]
    assert item["source_indexes"][1]["source_ref"] == str(middle_live_index)
    assert middle_live_index.is_file()
    assert not _live_index_path(final_root / "campaign").exists()


def test_resume_preserves_distinct_omission_reasons_across_hops(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source" / "campaign"
    source.mkdir(parents=True)
    rows = [
        _omitted_row("candidate-a", "contract_failed"),
        _omitted_row("candidate-a", "verification_failed"),
    ]
    _write_index(source, rows)
    middle_root = tmp_path / "middle"
    prepare_resumed_campaign(
        resume_source=source,
        campaign_dir=middle_root / "campaign",
        run_root=middle_root,
    )
    _write_index(middle_root / "campaign", [rows[0]])
    final_root = tmp_path / "final"
    prepare_resumed_campaign(
        resume_source=middle_root / "campaign",
        campaign_dir=final_root / "campaign",
        run_root=final_root,
    )

    assert _read_snapshot_rows(final_root) == rows


def test_resume_preserves_legacy_recorded_row_without_status(tmp_path: Path) -> None:
    source = tmp_path / "source" / "campaign"
    row = _write_candidate(source, "candidate-a")
    row.pop("artifact_status")
    _write_index(source, [row])
    run_root = tmp_path / "run"

    prepare_resumed_campaign(
        resume_source=source,
        campaign_dir=run_root / "campaign",
        run_root=run_root,
    )

    assert _read_snapshot_rows(run_root) == [row]


def test_resume_rejects_same_candidate_bound_to_different_artifacts(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source" / "campaign"
    inherited_row = _write_candidate(source, "candidate-a", artifact_label="first")
    _write_index(source, [inherited_row])
    middle_root = tmp_path / "middle"
    prepare_resumed_campaign(
        resume_source=source,
        campaign_dir=middle_root / "campaign",
        run_root=middle_root,
    )
    conflicting_row = _write_candidate(
        middle_root / "campaign",
        "candidate-a",
        artifact_label="second",
    )
    _write_index(middle_root / "campaign", [conflicting_row])

    with pytest.raises(
        ResumePreparationError,
        match="conflicting formal candidate index rows for recorded candidate_id",
    ):
        prepare_resumed_campaign(
            resume_source=middle_root / "campaign",
            campaign_dir=tmp_path / "final" / "campaign",
            run_root=tmp_path / "final",
        )


def test_resume_rejects_conflicting_rows_for_same_artifact(tmp_path: Path) -> None:
    source = tmp_path / "source" / "campaign"
    inherited_row = _write_candidate(source, "candidate-a")
    _write_index(source, [inherited_row])
    middle_root = tmp_path / "middle"
    prepare_resumed_campaign(
        resume_source=source,
        campaign_dir=middle_root / "campaign",
        run_root=middle_root,
    )
    conflicting_row = dict(inherited_row, stage="different-stage")
    _write_index(middle_root / "campaign", [conflicting_row])

    with pytest.raises(
        ResumePreparationError,
        match="conflicting formal candidate index rows for artifact_ref",
    ):
        prepare_resumed_campaign(
            resume_source=middle_root / "campaign",
            campaign_dir=tmp_path / "final" / "campaign",
            run_root=tmp_path / "final",
        )


def test_resume_rejects_noncanonical_artifact_ref(tmp_path: Path) -> None:
    source = tmp_path / "source" / "campaign"
    row = _write_candidate(source, "candidate-a")
    row["artifact_ref"] = row["artifact_ref"].replace(
        "branch-a/",
        "branch-a/../branch-a/",
    )
    _write_index(source, [row])

    with pytest.raises(ResumePreparationError, match="artifact_ref is not canonical"):
        prepare_resumed_campaign(
            resume_source=source,
            campaign_dir=tmp_path / "run" / "campaign",
            run_root=tmp_path / "run",
        )


def test_resume_rejects_recorded_row_without_artifact_ref(tmp_path: Path) -> None:
    source = tmp_path / "source" / "campaign"
    source.mkdir(parents=True)
    _write_index(
        source,
        [
            {
                "artifact_status": "recorded",
                "artifact_ref": None,
                "candidate_id": "candidate-a",
            }
        ],
    )

    with pytest.raises(ResumePreparationError, match="lacks artifact_ref"):
        prepare_resumed_campaign(
            resume_source=source,
            campaign_dir=tmp_path / "run" / "campaign",
            run_root=tmp_path / "run",
        )


def test_resume_rejects_artifact_ref_outside_formal_root(tmp_path: Path) -> None:
    source = tmp_path / "source" / "campaign"
    artifact_ref = "other/candidate.patch.json"
    artifact_path = source / artifact_ref
    artifact_path.parent.mkdir(parents=True)
    artifact_path.write_text(
        json.dumps(
            {
                "candidate_id": "candidate-a",
                "branch_id": "branch-a",
                "hypothesis_id": "hypothesis-a",
            }
        ),
        encoding="utf-8",
    )
    _write_index(
        source,
        [
            {
                "artifact_status": "recorded",
                "artifact_ref": artifact_ref,
                "candidate_id": "candidate-a",
                "branch_id": "branch-a",
                "hypothesis_id": "hypothesis-a",
            }
        ],
    )

    with pytest.raises(ResumePreparationError, match="artifact_ref is not canonical"):
        prepare_resumed_campaign(
            resume_source=source,
            campaign_dir=tmp_path / "run" / "campaign",
            run_root=tmp_path / "run",
        )


def test_resume_rejects_tampered_inherited_index(tmp_path: Path) -> None:
    source = tmp_path / "source" / "campaign"
    row = _write_candidate(source, "candidate-a")
    _write_index(source, [row])
    middle_root = tmp_path / "middle"
    prepare_resumed_campaign(
        resume_source=source,
        campaign_dir=middle_root / "campaign",
        run_root=middle_root,
    )
    snapshot_index = _snapshot_index_path(middle_root)
    snapshot_index.write_text(
        snapshot_index.read_text(encoding="utf-8") + "{}\n",
        encoding="utf-8",
    )

    with pytest.raises(ResumePreparationError, match="size mismatch"):
        prepare_resumed_campaign(
            resume_source=middle_root / "campaign",
            campaign_dir=tmp_path / "final" / "campaign",
            run_root=tmp_path / "final",
        )


def test_resume_rejects_mismatched_inherited_manifest(tmp_path: Path) -> None:
    source = tmp_path / "source" / "campaign"
    row = _write_candidate(source, "candidate-a")
    _write_index(source, [row])
    middle_root = tmp_path / "middle"
    preparation = prepare_resumed_campaign(
        resume_source=source,
        campaign_dir=middle_root / "campaign",
        run_root=middle_root,
    )
    manifest = json.loads(preparation.manifest_path.read_text(encoding="utf-8"))
    manifest["campaign_dir"] = str(tmp_path / "different-campaign")
    preparation.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ResumePreparationError, match="campaign_dir does not match"):
        prepare_resumed_campaign(
            resume_source=middle_root / "campaign",
            campaign_dir=tmp_path / "final" / "campaign",
            run_root=tmp_path / "final",
        )


def test_resume_rejects_snapshot_ref_escape(tmp_path: Path) -> None:
    source = tmp_path / "source" / "campaign"
    row = _write_candidate(source, "candidate-a")
    _write_index(source, [row])
    middle_root = tmp_path / "middle"
    preparation = prepare_resumed_campaign(
        resume_source=source,
        campaign_dir=middle_root / "campaign",
        run_root=middle_root,
    )
    manifest = json.loads(preparation.manifest_path.read_text(encoding="utf-8"))
    item = next(
        item
        for item in manifest["terminal_artifacts"]
        if item["original_ref"] == "artifacts/formal_candidates/index.jsonl"
    )
    item["snapshot_ref"] = "../outside/index.jsonl"
    preparation.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ResumePreparationError, match="snapshot_ref mismatch"):
        prepare_resumed_campaign(
            resume_source=middle_root / "campaign",
            campaign_dir=tmp_path / "final" / "campaign",
            run_root=tmp_path / "final",
        )


def test_resume_rejects_candidate_artifacts_without_index(tmp_path: Path) -> None:
    source = tmp_path / "source" / "campaign"
    _write_candidate(source, "candidate-a")

    with pytest.raises(
        ResumePreparationError,
        match="artifacts exist without a trusted lineage index",
    ):
        prepare_resumed_campaign(
            resume_source=source,
            campaign_dir=tmp_path / "run" / "campaign",
            run_root=tmp_path / "run",
        )


def test_resume_rejects_unindexed_candidate_metadata(tmp_path: Path) -> None:
    source = tmp_path / "source" / "campaign"
    indexed_row = _write_candidate(source, "candidate-a")
    _write_candidate(source, "candidate-b")
    _write_index(source, [indexed_row])

    with pytest.raises(ResumePreparationError, match="coverage mismatch"):
        prepare_resumed_campaign(
            resume_source=source,
            campaign_dir=tmp_path / "run" / "campaign",
            run_root=tmp_path / "run",
        )


def test_resume_rejects_metadata_identity_mismatch(tmp_path: Path) -> None:
    source = tmp_path / "source" / "campaign"
    row = _write_candidate(source, "candidate-a")
    row["hypothesis_id"] = "different-hypothesis"
    _write_index(source, [row])

    with pytest.raises(ResumePreparationError, match="metadata identity mismatch"):
        prepare_resumed_campaign(
            resume_source=source,
            campaign_dir=tmp_path / "run" / "campaign",
            run_root=tmp_path / "run",
        )


def _write_candidate(
    campaign: Path,
    candidate_id: str,
    *,
    artifact_label: str | None = None,
) -> dict[str, str]:
    label = artifact_label or candidate_id
    artifact_ref = (
        "artifacts/formal_candidates/branch-a/" f"{label}/candidate.patch.json"
    )
    artifact_path = campaign / artifact_ref
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        json.dumps(
            {
                "candidate_id": candidate_id,
                "branch_id": "branch-a",
                "hypothesis_id": "hypothesis-a",
            }
        ),
        encoding="utf-8",
    )
    return {
        "artifact_ref": artifact_ref,
        "artifact_status": "recorded",
        "branch_id": "branch-a",
        "candidate_id": candidate_id,
        "hypothesis_id": "hypothesis-a",
    }


def _omitted_row(candidate_id: str, reason: str) -> dict[str, object]:
    return {
        "artifact_ref": None,
        "artifact_status": "omitted",
        "artifact_omitted_reason": reason,
        "candidate_id": candidate_id,
    }


def _write_index(campaign: Path, rows: list[dict[str, object]]) -> Path:
    path = _live_index_path(campaign)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    return path


def _live_index_path(campaign: Path) -> Path:
    return campaign / "artifacts" / "formal_candidates" / "index.jsonl"


def _snapshot_index_path(run_root: Path) -> Path:
    return (
        run_root
        / "resume_snapshot"
        / "campaign"
        / "artifacts"
        / "formal_candidates"
        / "index.jsonl"
    )


def _read_snapshot_rows(run_root: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in _snapshot_index_path(run_root)
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]


def _candidate_index_manifest_item(manifest_path: Path) -> dict[str, object]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    item = next(
        item
        for item in manifest["terminal_artifacts"]
        if item["original_ref"] == "artifacts/formal_candidates/index.jsonl"
    )
    snapshot_path = manifest_path.parents[1] / item["snapshot_ref"]
    assert item["size_bytes"] == snapshot_path.stat().st_size
    assert item["sha256"] == sha256(snapshot_path.read_bytes()).hexdigest()
    return item
