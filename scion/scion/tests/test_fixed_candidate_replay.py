from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from scion.core.models import CanaryResult, EvalStats, ExperimentStage, ProtocolResult
from scion.cli.main import app
from scion.core.fixed_candidate_replay import (
    COMPARISON_SCHEMA_VERSION,
    SCHEMA_VERSION,
    build_fixed_candidate_replay_manifest,
    execute_fixed_candidate_replay,
    materialize_candidate_workspace,
)


runner = CliRunner()


def test_builds_manifest_from_recorded_screening_candidate(tmp_path: Path) -> None:
    campaign_dir = tmp_path / "campaign"
    index_path = campaign_dir / "artifacts" / "formal_candidates" / "index.jsonl"
    artifact_ref = _write_candidate_artifact(campaign_dir, "candidate-a")
    _append_index_row(
        index_path,
        {
            "candidate_id": "candidate-a",
            "branch_id": "branch-a",
            "hypothesis_id": "hyp-a",
            "stage": "screening",
            "patch_digest": "patch-digest-a",
            "artifact_ref": artifact_ref,
            "artifact_status": "recorded",
            "replay_identity_status": "complete",
            "missing_replay_identity_keys": [],
        },
    )

    manifest = build_fixed_candidate_replay_manifest(
        campaign_dir,
        source_arm="record_only",
        comparison_id="cmp-001",
        generated_at="2026-06-12T00:00:00+00:00",
    )

    assert manifest["schema_version"] == SCHEMA_VERSION
    assert manifest["comparison_id"] == "cmp-001"
    assert manifest["source_arm"] == "record_only"
    assert manifest["candidate_count"] == 1
    assert manifest["causal_candidate_pairing"] is True
    assert manifest["replay_arms"] == ["on", "record_only"]
    assert manifest["omitted_rows"] == []

    candidate = manifest["candidates"][0]
    assert candidate == {
        "candidate_order_index": 0,
        "candidate_id": "candidate-a",
        "branch_id": "branch-a",
        "lineage_id": "lineage-a",
        "hypothesis_id": "hyp-a",
        "stage": "screening",
        "artifact_ref": artifact_ref,
        "target_files": ["solver.py"],
        "selected_surface": "repair",
        "hypothesis_action": "modify",
        "patch_digest": "patch-digest-a",
        "patch_hash": "patch-digest-a",
        "code_hash": "code-hash-a",
        "base_champion_id": "champion-1",
        "base_champion_hash": "champion-hash-a",
        "problem_spec_hash": "problem-hash-a",
        "split_manifest_hash": "split-hash-a",
        "seed_ledger_hash": "seed-hash-a",
        "protocol_version": "protocol-v3",
        "raw_metrics_ref": "metrics/screening.json",
        "source_raw_metrics_ref": "metrics/screening.json",
        "decision": "continue_explore",
        "decision_reason_codes": ["SCREENING_FAIL_WIN_RATE"],
        "audit_flags": {
            "decision_features_excluded": True,
            "proposal_text_excluded": True,
            "replay_materialized_from_artifact": True,
        },
    }
    rendered = json.dumps(manifest, sort_keys=True)
    assert "code_content" not in rendered
    assert "TAINTED" not in rendered
    assert "bks_gap" not in rendered
    assert "aa_rows" not in rendered


def test_omits_candidates_without_replayable_screening_artifacts(
    tmp_path: Path,
) -> None:
    campaign_dir = tmp_path / "campaign"
    index_path = campaign_dir / "artifacts" / "formal_candidates" / "index.jsonl"
    missing_artifact_ref = (
        "artifacts/formal_candidates/missing/candidate.patch.json"
    )
    missing_identity_ref = _write_candidate_artifact(
        campaign_dir,
        "candidate-missing-identity",
        identity_overrides={
            "identity_status": "degraded",
            "status": "degraded",
            "seed_ledger_hash": "unknown",
            "missing_identity_keys": ["seed_ledger_hash"],
            "missing_keys": ["seed_ledger_hash"],
        },
    )
    validation_ref = _write_candidate_artifact(
        campaign_dir,
        "candidate-validation",
        stage="validation",
    )
    _append_index_row(
        index_path,
        {
            "candidate_id": "candidate-missing-artifact",
            "branch_id": "branch-missing-artifact",
            "hypothesis_id": "hyp-missing-artifact",
            "stage": "screening",
            "artifact_ref": missing_artifact_ref,
            "artifact_status": "recorded",
            "replay_identity_status": "complete",
            "missing_replay_identity_keys": [],
        },
    )
    _append_index_row(
        index_path,
        {
            "candidate_id": "candidate-missing-identity",
            "branch_id": "branch-missing-identity",
            "hypothesis_id": "hyp-missing-identity",
            "stage": "screening",
            "artifact_ref": missing_identity_ref,
            "artifact_status": "recorded",
            "replay_identity_status": "degraded",
            "missing_replay_identity_keys": ["seed_ledger_hash"],
        },
    )
    _append_index_row(
        index_path,
        {
            "candidate_id": "candidate-validation",
            "branch_id": "branch-validation",
            "hypothesis_id": "hyp-validation",
            "stage": "validation",
            "artifact_ref": validation_ref,
            "artifact_status": "recorded",
            "replay_identity_status": "complete",
            "missing_replay_identity_keys": [],
        },
    )
    _append_index_row(
        index_path,
        {
            "candidate_id": "candidate-omitted",
            "branch_id": "branch-omitted",
            "hypothesis_id": "hyp-omitted",
            "stage": "screening",
            "artifact_ref": None,
            "artifact_status": "omitted",
            "artifact_omitted_reason": "missing_replay_identity",
            "replay_identity_status": "degraded",
            "missing_replay_identity_keys": ["problem_spec_hash"],
        },
    )

    manifest = build_fixed_candidate_replay_manifest(
        index_path,
        source_arm="on",
        comparison_id="cmp-omit",
        generated_at="2026-06-12T00:00:00+00:00",
    )

    assert manifest["candidate_count"] == 0
    assert manifest["causal_candidate_pairing"] is False
    assert [row["candidate_id"] for row in manifest["omitted_rows"]] == [
        "candidate-missing-artifact",
        "candidate-missing-identity",
        "candidate-validation",
        "candidate-omitted",
    ]
    reasons_by_id = {
        row["candidate_id"]: row["reasons"] for row in manifest["omitted_rows"]
    }
    assert reasons_by_id["candidate-missing-artifact"] == ["candidate_patch_missing"]
    assert reasons_by_id["candidate-missing-identity"] == [
        "replay_identity_not_complete",
        "missing_replay_identity_keys",
    ]
    assert reasons_by_id["candidate-validation"] == ["non_screening_stage"]
    assert reasons_by_id["candidate-omitted"] == [
        "missing_replay_identity",
        "missing_artifact_ref",
        "replay_identity_not_complete",
        "missing_replay_identity_keys",
    ]


def test_cli_writes_fixed_candidate_replay_manifest(tmp_path: Path) -> None:
    campaign_dir = tmp_path / "campaign"
    index_path = campaign_dir / "artifacts" / "formal_candidates" / "index.jsonl"
    artifact_ref = _write_candidate_artifact(campaign_dir, "candidate-cli")
    _append_index_row(
        index_path,
        {
            "candidate_id": "candidate-cli",
            "branch_id": "branch-cli",
            "hypothesis_id": "hyp-cli",
            "stage": "screening",
            "patch_digest": "patch-digest-a",
            "artifact_ref": artifact_ref,
            "artifact_status": "recorded",
            "replay_identity_status": "complete",
            "missing_replay_identity_keys": [],
        },
    )
    output_path = tmp_path / "manifest.json"

    result = runner.invoke(
        app,
        [
            "report",
            "fixed-candidate-replay-manifest",
            "--source",
            str(campaign_dir),
            "--source-arm",
            "record_only",
            "--comparison-id",
            "cmp-cli",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0, result.output
    summary = json.loads(result.output)
    assert summary["candidate_count"] == 1
    assert summary["omitted_row_count"] == 0
    assert summary["manifest_path"] == str(output_path)
    manifest = json.loads(output_path.read_text(encoding="utf-8"))
    assert manifest["comparison_id"] == "cmp-cli"
    assert manifest["candidates"][0]["candidate_id"] == "candidate-cli"


def test_materializes_candidate_workspace_and_rejects_path_traversal(
    tmp_path: Path,
) -> None:
    campaign_dir = tmp_path / "campaign"
    base_workspace = campaign_dir / "workspaces" / "champion"
    base_workspace.mkdir(parents=True)
    (base_workspace / "solver.py").write_text("BASE = True\n", encoding="utf-8")
    operators_dir = base_workspace / "operators"
    operators_dir.mkdir()
    readonly_target = operators_dir / "existing.py"
    readonly_target.write_text("VALUE = 'base'\n", encoding="utf-8")
    readonly_target.chmod(0o400)
    operators_dir.chmod(0o500)
    code_content = "BASE = False\n"
    operator_code = "VALUE = 'candidate'\n"
    candidate = {"candidate_id": "candidate-safe"}
    candidate_patch = {
        "base": {"base_workspace_ref": "workspaces/champion"},
        "patch": {
            "files": [
                {
                    "file_path": "solver.py",
                    "code_content": code_content,
                    "code_sha256": _sha256(code_content),
                },
                {
                    "file_path": "operators/existing.py",
                    "code_content": operator_code,
                    "code_sha256": _sha256(operator_code),
                }
            ]
        },
    }

    workspace = materialize_candidate_workspace(
        candidate=candidate,
        candidate_patch=candidate_patch,
        source_campaign_dir=campaign_dir,
        output_dir=tmp_path / "replay",
        arm="on",
    )

    assert (workspace / "solver.py").read_text(encoding="utf-8") == code_content
    assert (
        workspace / "operators" / "existing.py"
    ).read_text(encoding="utf-8") == operator_code

    unsafe_patch = {
        "base": {"base_workspace_ref": "workspaces/champion"},
        "patch": {
            "files": [
                {
                    "file_path": "../escape.py",
                    "code_content": "bad = True\n",
                }
            ]
        },
    }
    try:
        materialize_candidate_workspace(
            candidate=candidate,
            candidate_patch=unsafe_patch,
            source_campaign_dir=campaign_dir,
            output_dir=tmp_path / "replay",
            arm="record_only",
        )
    except ValueError as exc:
        assert "unsafe patch file path" in str(exc)
    else:
        raise AssertionError("path traversal patch should have been rejected")


def test_executor_writes_two_arm_rows_with_distinct_measurement_governance(
    tmp_path: Path,
) -> None:
    campaign_dir = tmp_path / "campaign"
    _write_base_workspace(campaign_dir)
    index_path = campaign_dir / "artifacts" / "formal_candidates" / "index.jsonl"
    artifact_ref = _write_candidate_artifact(
        campaign_dir,
        "candidate-exec",
        base_workspace_ref="workspaces/champion",
        patch_code_content="VALUE = 'candidate'\n",
    )
    _append_index_row(
        index_path,
        {
            "candidate_id": "candidate-exec",
            "branch_id": "branch-a",
            "hypothesis_id": "hyp-a",
            "stage": "screening",
            "patch_digest": "patch-digest-a",
            "artifact_ref": artifact_ref,
            "artifact_status": "recorded",
            "replay_identity_status": "complete",
            "missing_replay_identity_keys": [],
        },
    )
    manifest = build_fixed_candidate_replay_manifest(
        campaign_dir,
        source_arm="record_only",
        comparison_id="cmp-exec",
        generated_at="2026-06-12T00:00:00+00:00",
    )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    comparison_path = execute_fixed_candidate_replay(
        manifest_path,
        problem_yaml_path=tmp_path / "problem-v1.yaml",
        output_dir=tmp_path / "replay",
        protocol_factory=_fake_protocol_factory,
    )

    comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
    assert comparison["schema_version"] == COMPARISON_SCHEMA_VERSION
    assert comparison["decision_features_excluded"] is True
    assert comparison["promotion_state_mutated"] is False
    assert comparison["campaign_state_mutated"] is False
    rows = comparison["rows"]
    assert len(rows) == 2
    assert {row["candidate_id"] for row in rows} == {"candidate-exec"}
    assert {row["patch_digest"] for row in rows} == {"patch-digest-a"}
    assert {row["measurement_governance"] for row in rows} == {
        "on",
        "off_record_only",
    }
    assert all(row["status"] == "completed" for row in rows)
    assert all(row["canary"]["passed"] is True for row in rows)
    rendered = json.dumps(comparison, sort_keys=True)
    assert "code_content" not in rendered
    assert "TAINTED" not in rendered
    assert "bks_gap" not in rendered
    assert "aa_rows" not in rendered


def test_cli_executes_fixed_candidate_replay_with_row_error_summary(
    tmp_path: Path,
) -> None:
    campaign_dir = tmp_path / "campaign"
    index_path = campaign_dir / "artifacts" / "formal_candidates" / "index.jsonl"
    artifact_ref = _write_candidate_artifact(
        campaign_dir,
        "candidate-cli-exec",
        base_workspace_ref="workspaces/missing-champion",
        patch_code_content="VALUE = 'candidate'\n",
    )
    _append_index_row(
        index_path,
        {
            "candidate_id": "candidate-cli-exec",
            "branch_id": "branch-a",
            "hypothesis_id": "hyp-a",
            "stage": "screening",
            "patch_digest": "patch-digest-a",
            "artifact_ref": artifact_ref,
            "artifact_status": "recorded",
            "replay_identity_status": "complete",
            "missing_replay_identity_keys": [],
        },
    )
    manifest = build_fixed_candidate_replay_manifest(
        campaign_dir,
        source_arm="record_only",
        comparison_id="cmp-cli-exec",
        generated_at="2026-06-12T00:00:00+00:00",
    )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    output_dir = tmp_path / "replay-cli"

    result = runner.invoke(
        app,
        [
            "report",
            "fixed-candidate-replay",
            "--manifest",
            str(manifest_path),
            "--problem",
            str(Path(__file__).resolve().parents[1] / "problems" / "cvrp" / "problem-v1.yaml"),
            "--protocol",
            str(Path(__file__).resolve().parents[1] / "problems" / "cvrp" / "protocol.yaml"),
            "--split",
            str(Path(__file__).resolve().parents[1] / "problems" / "cvrp" / "split_manifest.yaml"),
            "--seeds",
            str(Path(__file__).resolve().parents[1] / "problems" / "cvrp" / "seed_ledger.yaml"),
            "--output-dir",
            str(output_dir),
            "--time-limit-sec",
            "1",
        ],
    )

    assert result.exit_code == 0, result.output
    summary = json.loads(result.output)
    assert summary["row_count"] == 2
    assert summary["error_count"] == 2
    assert summary["schema_version"] == COMPARISON_SCHEMA_VERSION
    comparison = json.loads(Path(summary["comparison_path"]).read_text(encoding="utf-8"))
    assert len(comparison["rows"]) == 2
    assert {row["status"] for row in comparison["rows"]} == {"error"}


def _write_candidate_artifact(
    campaign_dir: Path,
    candidate_id: str,
    *,
    stage: str = "screening",
    identity_overrides: dict[str, object] | None = None,
    base_workspace_ref: str = "workspaces/champion",
    patch_code_content: str = "TAINTED patch body should not be copied",
) -> str:
    artifact_ref = (
        f"artifacts/formal_candidates/branch-a/{candidate_id}/candidate.patch.json"
    )
    metadata_path = campaign_dir / artifact_ref
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    replay_identity = {
        "schema": "scion.formal_replay_identity.v1",
        "problem_spec_hash": "problem-hash-a",
        "split_manifest_hash": "split-hash-a",
        "seed_ledger_hash": "seed-hash-a",
        "patch_digest": "patch-digest-a",
        "patch_hash": "patch-digest-a",
        "selected_surface": "repair",
        "protocol_version": "protocol-v3",
        "raw_metrics_ref": "metrics/screening.json",
        "code_hash": "code-hash-a",
        "identity_status": "complete",
        "status": "complete",
        "missing_identity_keys": [],
        "missing_keys": [],
    }
    replay_identity.update(identity_overrides or {})
    metadata = {
        "schema": "scion.formal_candidate_patch_artifact.v1",
        "candidate_id": candidate_id,
        "branch_id": "branch-a",
        "lineage_id": "lineage-a",
        "hypothesis_id": "hyp-a",
        "stage": stage,
        "decision": "continue_explore",
        "decision_reason_codes": ["SCREENING_FAIL_WIN_RATE"],
        "target_files": ["solver.py"],
        "base": {
            "base_champion_id": "champion-1",
            "base_champion_hash": "champion-hash-a",
            "base_workspace_ref": base_workspace_ref,
        },
        "patch": {
            "patch_digest": "patch-digest-a",
            "files": [
                {
                    "file_path": "solver.py",
                    "action": "modify",
                    "code_sha256": _sha256(patch_code_content),
                    "code_content": patch_code_content,
                }
            ],
        },
        "replay_identity": replay_identity,
        "replay_metadata": {
            "raw_metrics_ref": "metrics/screening.json",
            "selected_surface": "repair",
        },
        "hypothesis": {
            "action": "modify",
            "rationale_text": "TAINTED hypothesis text should not be copied",
        },
        "prompt_text": "TAINTED prompt text should not be copied",
        "raw_measurement_diagnostics": {
            "bks_gap": 0.1,
            "aa_rows": [{"case": "raw"}],
        },
    }
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    return artifact_ref


class _FakeProtocol:
    def __init__(self, arm: str) -> None:
        self._arm = arm

    def run_canary(
        self,
        candidate_ws: str,
        champion_ws: str,
        *,
        selected_surface: str | None = None,
    ) -> CanaryResult:
        return CanaryResult(passed=True, reason=None)

    def run_experiment(
        self,
        stage: ExperimentStage,
        candidate_ws: str,
        champion_ws: str,
        hypothesis_action: str,
        **kwargs: object,
    ) -> ProtocolResult:
        assert stage is ExperimentStage.SCREENING
        assert hypothesis_action == "modify"
        return ProtocolResult(
            stage=ExperimentStage.SCREENING,
            stats=EvalStats(
                n_cases=1,
                wins=1,
                losses=0,
                ties=0,
                win_rate=1.0,
                median_delta=0.1,
                ci_low=0.0,
                ci_high=0.2,
            ),
            gate_outcome="pass",
            reason_codes=("SCREENING_PASS",),
            exposed_summary="filtered summary",
            raw_metrics_ref=f"metrics/{self._arm}/screening.json",
            objective_semantics="declared_objectives_lexicographic",
        )


def _fake_protocol_factory(**kwargs: object) -> _FakeProtocol:
    return _FakeProtocol(str(kwargs["arm"]))


def _write_base_workspace(campaign_dir: Path) -> None:
    workspace = campaign_dir / "workspaces" / "champion"
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "solver.py").write_text("VALUE = 'champion'\n", encoding="utf-8")


def _sha256(value: str) -> str:
    import hashlib

    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _append_index_row(index_path: Path, row: dict[str, object]) -> None:
    index_path.parent.mkdir(parents=True, exist_ok=True)
    with index_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")
