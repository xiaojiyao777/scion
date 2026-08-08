from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from typer.testing import CliRunner

from scion.cli.main import app
from scion.core.fixed_candidate_replay import (
    COMPARISON_SCHEMA_VERSION,
    SCHEMA_VERSION,
    build_fixed_candidate_replay_manifest,
    execute_fixed_candidate_replay,
    materialize_candidate_workspace,
    resolve_candidate_base_workspace,
)


runner = CliRunner()


def test_manifest_selects_historical_v3_shape_without_identity_or_hash_gates(
    tmp_path: Path,
) -> None:
    campaign = _write_campaign(tmp_path)
    artifact = _artifact_path(campaign)
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    payload["replay_identity"] = {
        "identity_status": "degraded",
        "missing_keys": ["all_old_identity_fields"],
        "patch_digest": "intentionally-wrong",
        "code_hash": "intentionally-wrong",
    }
    payload["replay_materialization"].update(
        {
            "patch_digest": "intentionally-wrong",
            "base_identity_manifest": {"invalid": True},
            "candidate_identity_manifest": {"invalid": True},
        }
    )
    artifact.write_text(json.dumps(payload), encoding="utf-8")

    manifest = build_fixed_candidate_replay_manifest(
        campaign,
        source_arm="on",
        comparison_id="warehouse-r3-s1",
        candidate_ids=["candidate-a"],
        max_candidates=1,
        stages=["screening", "validation", "frozen"],
        replay_arms=["on"],
        conditional_stage_progression=True,
        expand_screening=True,
        generated_at="2026-08-08T00:00:00+00:00",
    )

    assert manifest["schema_version"] == SCHEMA_VERSION
    assert manifest["source_arm"] == "on"
    assert manifest["replay_arms"] == ["on"]
    assert manifest["source_candidate_count"] == 1
    assert manifest["candidate_count"] == 3
    assert manifest["omitted_rows"] == []
    assert [row["stage"] for row in manifest["candidates"]] == [
        "screening",
        "validation",
        "frozen",
    ]
    assert {row["candidate_id"] for row in manifest["candidates"]} == {
        "candidate-a"
    }
    rendered = json.dumps(manifest, sort_keys=True)
    assert "replay_identity" not in rendered
    assert "digest" not in rendered
    assert "hash" not in rendered
    assert "attribution" not in rendered


@pytest.mark.parametrize("field", ["candidate_id", "hypothesis_id", "branch_id"])
def test_manifest_requires_plain_index_and_artifact_fields_to_match(
    tmp_path: Path,
    field: str,
) -> None:
    campaign = _write_campaign(tmp_path)
    artifact = _artifact_path(campaign)
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    payload[field] = "different"
    artifact.write_text(json.dumps(payload), encoding="utf-8")

    manifest = build_fixed_candidate_replay_manifest(
        campaign,
        source_arm="on",
        comparison_id="mismatch",
    )

    assert manifest["candidate_count"] == 0
    assert manifest["omitted_rows"][0]["reasons"] == [
        f"candidate_patch_{field}_mismatch"
    ]


def test_manifest_rejects_artifact_outside_source_campaign(tmp_path: Path) -> None:
    campaign = _write_campaign(tmp_path)
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    index = campaign / "artifacts" / "formal_candidates" / "index.jsonl"
    row = json.loads(index.read_text(encoding="utf-8"))
    row["artifact_ref"] = str(outside)
    index.write_text(json.dumps(row) + "\n", encoding="utf-8")

    manifest = build_fixed_candidate_replay_manifest(
        campaign,
        source_arm="on",
        comparison_id="outside",
    )

    assert manifest["candidate_count"] == 0
    assert manifest["omitted_rows"][0]["reasons"] == [
        "artifact_path_outside_campaign"
    ]


def test_fixed_replay_accepts_only_one_on_arm(tmp_path: Path) -> None:
    campaign = _write_campaign(tmp_path)
    with pytest.raises(ValueError, match="source_arm must be on"):
        build_fixed_candidate_replay_manifest(
            campaign,
            source_arm="record_only",
            comparison_id="bad-source-arm",
        )
    with pytest.raises(ValueError, match="supports only the on arm"):
        build_fixed_candidate_replay_manifest(
            campaign,
            source_arm="on",
            comparison_id="bad-replay-arm",
            replay_arms=["on", "record_only"],
        )


def test_materialization_uses_cumulative_files_and_ignores_identity_noise(
    tmp_path: Path,
) -> None:
    campaign = _write_campaign(tmp_path)
    artifact = json.loads(_artifact_path(campaign).read_text(encoding="utf-8"))
    artifact["patch"]["files"][0]["code_content"] = "proposal-only\n"
    artifact["replay_materialization"].update(
        {
            "patch_digest": "wrong",
            "base_identity_manifest": {"invalid": True},
            "candidate_identity_manifest": {"invalid": True},
        }
    )
    candidate = _candidate_manifest_row(campaign)

    workspace = materialize_candidate_workspace(
        candidate=candidate,
        candidate_patch=artifact,
        source_campaign_dir=campaign,
        output_dir=tmp_path / "out",
        arm="on",
    )

    assert (workspace / "solver.py").read_text(encoding="utf-8") == "candidate\n"
    assert (workspace / "unchanged.txt").read_text(encoding="utf-8") == "base\n"


def test_legacy_patch_files_remain_readable(tmp_path: Path) -> None:
    campaign = _write_campaign(tmp_path)
    artifact = json.loads(_artifact_path(campaign).read_text(encoding="utf-8"))
    artifact.pop("replay_materialization")
    artifact["patch"] = {
        "files": [
            {
                "file_path": "solver.py",
                "action": "modify",
                "code_content": "legacy\n",
                "code_sha256": "ignored",
            }
        ]
    }

    workspace = materialize_candidate_workspace(
        candidate=_candidate_manifest_row(campaign),
        candidate_patch=artifact,
        source_campaign_dir=campaign,
        output_dir=tmp_path / "out",
        arm="on",
    )

    assert (workspace / "solver.py").read_text(encoding="utf-8") == "legacy\n"


@pytest.mark.parametrize(
    "base_ref",
    ["../outside", "/tmp/outside", "workspaces/branch-a", "champions/not-a-version"],
)
def test_base_is_limited_to_source_campaign_champion_snapshots(
    tmp_path: Path,
    base_ref: str,
) -> None:
    campaign = _write_campaign(tmp_path)
    artifact = json.loads(_artifact_path(campaign).read_text(encoding="utf-8"))
    artifact["base"]["base_workspace_ref"] = base_ref

    with pytest.raises(ValueError, match="champions/champion_vN"):
        resolve_candidate_base_workspace(
            artifact,
            source_campaign_dir=campaign,
        )


def test_materialization_rejects_unsafe_path_action_and_missing_content(
    tmp_path: Path,
) -> None:
    campaign = _write_campaign(tmp_path)
    base = json.loads(_artifact_path(campaign).read_text(encoding="utf-8"))
    cases = [
        ({"file_path": "../escape.py", "action": "modify", "code_content": "x"}, "unsafe"),
        ({"file_path": "solver.py", "action": "chmod", "code_content": "x"}, "unsupported"),
        ({"file_path": "solver.py", "action": "modify"}, "code_content"),
    ]
    for index, (entry, message) in enumerate(cases):
        artifact = dict(base)
        artifact["replay_materialization"] = {
            "representation": "cumulative_full_file_replacement",
            "files": [entry],
        }
        with pytest.raises(ValueError, match=message):
            materialize_candidate_workspace(
                candidate=_candidate_manifest_row(campaign),
                candidate_patch=artifact,
                source_campaign_dir=campaign,
                output_dir=tmp_path / f"out-{index}",
                arm="on",
            )


def test_conditional_protocol_chain_expands_screening_and_validation_once(
    tmp_path: Path,
) -> None:
    campaign = _write_campaign(tmp_path)
    manifest_path = _write_manifest(
        campaign,
        tmp_path,
        stages=["screening", "validation", "frozen"],
        conditional=True,
        expand_screening=True,
    )
    protocol = _FakeProtocol(
        outcomes={
            ("screening", True): "pass",
            ("validation", False): "expand",
            ("validation", True): "pass",
            ("frozen", False): "pass",
        }
    )

    comparison_path = execute_fixed_candidate_replay(
        manifest_path,
        problem_yaml_path=tmp_path / "unused-problem.yaml",
        output_dir=tmp_path / "result",
        protocol_factory=lambda **_: protocol,
    )
    comparison = json.loads(comparison_path.read_text(encoding="utf-8"))

    assert comparison["schema_version"] == COMPARISON_SCHEMA_VERSION
    assert comparison["replay_arm"] == "on"
    assert comparison["evaluation_only"] is True
    assert comparison["candidate_count"] == 3
    assert comparison["row_count"] == 4
    assert [(row["stage"], row["expanded"]) for row in comparison["rows"]] == [
        ("screening", True),
        ("validation", False),
        ("validation", True),
        ("frozen", False),
    ]
    assert [row["gate_outcome"] for row in comparison["rows"]] == [
        "pass",
        "expand",
        "pass",
        "pass",
    ]
    assert protocol.calls == [
        ("screening", True),
        ("validation", False),
        ("validation", True),
        ("frozen", False),
    ]


def test_conditional_failure_skips_later_stages(tmp_path: Path) -> None:
    campaign = _write_campaign(tmp_path)
    manifest_path = _write_manifest(
        campaign,
        tmp_path,
        stages=["screening", "validation", "frozen"],
        conditional=True,
        expand_screening=True,
    )
    protocol = _FakeProtocol(outcomes={("screening", True): "fail"})

    comparison_path = execute_fixed_candidate_replay(
        manifest_path,
        problem_yaml_path=tmp_path / "unused-problem.yaml",
        output_dir=tmp_path / "result",
        protocol_factory=lambda **_: protocol,
    )
    comparison = json.loads(comparison_path.read_text(encoding="utf-8"))

    assert [row["status"] for row in comparison["rows"]] == [
        "completed",
        "skipped",
        "skipped",
    ]
    assert all(
        row.get("skip_reason") == "PREVIOUS_STAGE_NOT_PASSED"
        for row in comparison["rows"][1:]
    )
    assert protocol.calls == [("screening", True)]


def test_cli_builds_single_arm_conditional_manifest(tmp_path: Path) -> None:
    campaign = _write_campaign(tmp_path)
    output = tmp_path / "manifest.json"

    result = runner.invoke(
        app,
        [
            "report",
            "fixed-candidate-replay-manifest",
            "--source",
            str(campaign),
            "--source-arm",
            "on",
            "--comparison-id",
            "cli-s1",
            "--candidate-id",
            "candidate-a",
            "--max-candidates",
            "1",
            "--stage",
            "screening",
            "--stage",
            "validation",
            "--stage",
            "frozen",
            "--replay-arm",
            "on",
            "--conditional-stages",
            "--expand-screening",
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    summary = json.loads(result.output)
    assert summary["candidate_count"] == 3
    assert summary["replay_arms"] == ["on"]
    assert summary["conditional_stage_progression"] is True
    assert summary["expand_screening"] is True


def _write_campaign(tmp_path: Path) -> Path:
    campaign = tmp_path / "campaign"
    champion = campaign / "champions" / "champion_v1"
    champion.mkdir(parents=True)
    (champion / "solver.py").write_text("champion\n", encoding="utf-8")
    (champion / "unchanged.txt").write_text("base\n", encoding="utf-8")
    artifact = (
        campaign
        / "artifacts"
        / "formal_candidates"
        / "branch-a"
        / "candidate.patch.json"
    )
    artifact.parent.mkdir(parents=True)
    artifact.write_text(
        json.dumps(
            {
                "schema": "scion.formal_candidate_patch_artifact.v3",
                "candidate_id": "candidate-a",
                "hypothesis_id": "hypothesis-a",
                "branch_id": "branch-a",
                "lineage_id": "branch-a",
                "stage": "screening",
                "hypothesis_action": "modify",
                "base": {
                    "base_champion_id": 1,
                    "base_workspace_ref": "champions/champion_v1",
                    "base_champion_hash": "ignored",
                },
                "patch": {
                    "patch_digest": "ignored",
                    "files": [
                        {
                            "file_path": "solver.py",
                            "action": "modify",
                            "code_content": "proposal\n",
                            "code_sha256": "ignored",
                            "source_attribution": {"ignored": True},
                        }
                    ],
                },
                "replay_materialization": {
                    "schema_version": "scion.replay_materialization.v1",
                    "representation": "cumulative_full_file_replacement",
                    "files": [
                        {
                            "file_path": "solver.py",
                            "action": "modify",
                            "code_content": "candidate\n",
                            "code_sha256": "ignored",
                            "base_sha256": "ignored",
                            "source_attribution": {"ignored": True},
                            "candidate_attribution": {"ignored": True},
                        }
                    ],
                },
                "replay_metadata": {"selected_surface": "repair"},
            }
        ),
        encoding="utf-8",
    )
    index = campaign / "artifacts" / "formal_candidates" / "index.jsonl"
    index.write_text(
        json.dumps(
            {
                "candidate_id": "candidate-a",
                "hypothesis_id": "hypothesis-a",
                "branch_id": "branch-a",
                "stage": "screening",
                "artifact_status": "recorded",
                "artifact_ref": str(artifact.relative_to(campaign)),
                "replay_identity_status": "degraded",
                "patch_digest": "ignored",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return campaign


def _artifact_path(campaign: Path) -> Path:
    return (
        campaign
        / "artifacts"
        / "formal_candidates"
        / "branch-a"
        / "candidate.patch.json"
    )


def _candidate_manifest_row(campaign: Path) -> dict[str, Any]:
    manifest = build_fixed_candidate_replay_manifest(
        campaign,
        source_arm="on",
        comparison_id="materialize",
    )
    return manifest["candidates"][0]


def _write_manifest(
    campaign: Path,
    tmp_path: Path,
    *,
    stages: list[str],
    conditional: bool,
    expand_screening: bool,
) -> Path:
    manifest = build_fixed_candidate_replay_manifest(
        campaign,
        source_arm="on",
        comparison_id="execute",
        stages=stages,
        replay_arms=["on"],
        conditional_stage_progression=conditional,
        expand_screening=expand_screening,
        generated_at="2026-08-08T00:00:00+00:00",
    )
    path = tmp_path / "fixed_candidate_replay_manifest.v1.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


class _FakeProtocol:
    def __init__(self, *, outcomes: dict[tuple[str, bool], str]) -> None:
        self.outcomes = outcomes
        self.calls: list[tuple[str, bool]] = []

    def run_canary(
        self,
        candidate_workspace: str,
        champion_workspace: str,
        *,
        selected_surface: str | None,
    ) -> Any:
        assert candidate_workspace != champion_workspace
        assert selected_surface == "repair"
        return SimpleNamespace(passed=True, reason=None)

    def run_experiment(
        self,
        stage: Any,
        candidate_workspace: str,
        champion_workspace: str,
        hypothesis_action: str,
        *,
        expand: bool,
        selected_surface: str | None,
    ) -> Any:
        del candidate_workspace, champion_workspace
        stage_name = str(getattr(stage, "value", stage))
        self.calls.append((stage_name, expand))
        outcome = self.outcomes.get((stage_name, expand), "fail")
        return SimpleNamespace(
            raw_metrics_ref=f"metrics/{stage_name}-{expand}.json",
            stats=SimpleNamespace(
                n_cases=1,
                wins=1 if outcome == "pass" else 0,
                losses=0 if outcome == "pass" else 1,
                ties=0,
                win_rate=1.0 if outcome == "pass" else 0.0,
                median_delta=1.0 if outcome == "pass" else -1.0,
                ci_low=0.5 if outcome == "pass" else -1.5,
                ci_high=1.5 if outcome == "pass" else -0.5,
            ),
            gate_outcome=outcome,
            reason_codes=(outcome.upper(),),
            objective_semantics="lower_is_better",
            hypothesis_action=hypothesis_action,
            selected_surface=selected_surface,
        )
