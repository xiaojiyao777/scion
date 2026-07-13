from __future__ import annotations

import json
import shutil
from pathlib import Path

import yaml
from typer.testing import CliRunner

from scion.cli.main import app
from scion.config.problem import ProblemSpec, SearchSpace
from scion.config.split_manifest import SplitManifest
from scion.external_ingest import (
    ExternalProposalIngestor,
    ExternalProposalManifest,
    run_mock_smoke,
)
from scion.lineage.registry import LineageRegistry


def _write_base_workspace(root: Path) -> Path:
    workspace = root / "base"
    (workspace / "policies").mkdir(parents=True)
    (workspace / "policies" / "dispatch.py").write_text(
        "def choose(instance):\n"
        "    return 'baseline'\n",
        encoding="utf-8",
    )
    return workspace


def _problem_spec(base_workspace: Path) -> ProblemSpec:
    return ProblemSpec(
        name="external-ingest-toy",
        root_dir=str(base_workspace),
        operator_categories=["dispatch_policy"],
        search_space=SearchSpace(
            editable=["policies/*.py"],
            frozen=[],
            import_whitelist=[],
        ),
    )


def _manifest_payload(base_workspace: Path, external_workspace: Path) -> dict:
    return {
        "schema_version": "scion.external_proposal.v1",
        "hypothesis": {
            "hypothesis_text": "Try a dispatch policy change from an external agent.",
            "change_locus": "dispatch_policy",
            "action": "modify",
            "target_file": "policies/dispatch.py",
            "predicted_direction": "exploratory",
        },
        "source": {
            "type": "workspace",
            "workspace_path": str(external_workspace),
            "changed_files": ["policies/dispatch.py"],
        },
        "base_champion": {
            "champion_id": "champion_v1",
            "workspace_path": str(base_workspace),
            "branch_id": "external_branch",
            "lineage_id": "external_lineage",
        },
        "provenance": {
            "external_agent": "external-aps",
            "run_id": "run-001",
            "source_uri": "file:///external/run",
        },
        "declared_boundary": {
            "objective_digest": "sha256:objective",
            "constraint_digest": "sha256:constraints",
            "problem_spec_digest": "sha256:problem",
        },
    }


def _write_external_workspace(base_workspace: Path, root: Path) -> Path:
    external = root / "external"
    shutil.copytree(base_workspace, external)
    (external / "policies" / "dispatch.py").write_text(
        "def choose(instance):\n"
        "    return 'external'\n",
        encoding="utf-8",
    )
    return external


def _write_split_manifest(root: Path) -> Path:
    data_root = root / "data"
    data_root.mkdir()
    split_dir = root / "config"
    split_dir.mkdir()
    split_path = split_dir / "split_manifest.yaml"
    split_path.write_text(
        yaml.safe_dump(
            {
                "version": "test",
                "screening": [],
                "validation": [],
                "frozen": [],
                "canary": [],
                "safe_data_roots": ["../data"],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return split_path


def test_external_workspace_ingest_generates_canonical_audit_and_mock_smoke(
    tmp_path: Path,
) -> None:
    base_workspace = _write_base_workspace(tmp_path)
    external_workspace = _write_external_workspace(base_workspace, tmp_path)
    split = SplitManifest.from_yaml(_write_split_manifest(tmp_path))
    manifest = ExternalProposalManifest.model_validate(
        _manifest_payload(base_workspace, external_workspace)
    )

    ingestor = ExternalProposalIngestor(
        problem_spec=_problem_spec(base_workspace),
        output_dir=tmp_path / "out",
        split_manifest=split,
    )
    result = ingestor.ingest(manifest, smoke_runner=run_mock_smoke)

    assert result.passed
    assert result.hypothesis_contract.passed
    assert result.patch_contract.passed
    assert result.smoke_result is not None and result.smoke_result.passed
    assert result.patch.file_path == "policies/dispatch.py"
    assert "return 'external'" in result.patch.code_content

    audit = json.loads(Path(result.audit_manifest_path).read_text(encoding="utf-8"))
    assert audit["provenance"]["external_agent"] == "external-aps"
    assert audit["declared_boundary"]["constraint_digest"] == "sha256:constraints"
    assert audit["canonical_files"][0]["content_after_ref"].startswith(
        "content_after/"
    )
    assert audit["resolved_safe_data_roots"] == [str((tmp_path / "data").resolve())]

    diff = Path(result.canonical_diff_path).read_text(encoding="utf-8")
    assert "--- base/policies/dispatch.py" in diff
    assert "+++ candidate/policies/dispatch.py" in diff
    assert "+    return 'external'" in diff

    workspace_manifest = (
        Path(result.workspace_path)
        / ".scion"
        / "external_ingest"
        / "workspace_manifest.json"
    )
    workspace_audit = json.loads(workspace_manifest.read_text(encoding="utf-8"))
    assert workspace_audit["safe_data_roots"] == [str((tmp_path / "data").resolve())]


def test_external_ingest_cli_records_lineage_event(tmp_path: Path) -> None:
    base_workspace = _write_base_workspace(tmp_path)
    external_workspace = _write_external_workspace(base_workspace, tmp_path)
    problem_yaml = tmp_path / "problem.yaml"
    problem_yaml.write_text(
        "\n".join(
            [
                "name: external-ingest-toy",
                f"root_dir: {base_workspace}",
                "description: External ingest CLI test",
                "operator_categories:",
                "  - dispatch_policy",
                "search_space:",
                "  editable:",
                "    - policies/*.py",
                "  frozen: []",
                "  import_whitelist: []",
            ]
        ),
        encoding="utf-8",
    )
    manifest_path = tmp_path / "external_manifest.yaml"
    manifest_payload = _manifest_payload(base_workspace, external_workspace)
    hypothesis_text = "External source-grounded hypothesis. " * 20 + "complete-tail"
    manifest_payload["hypothesis"]["hypothesis_text"] = hypothesis_text
    manifest_path.write_text(
        yaml.safe_dump(
            manifest_payload,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    split_path = _write_split_manifest(tmp_path)
    campaign_dir = tmp_path / "campaign"
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "external-ingest",
            str(manifest_path),
            "--problem",
            str(problem_yaml),
            "--split",
            str(split_path),
            "--output-dir",
            str(tmp_path / "out"),
            "--campaign-dir",
            str(campaign_dir),
            "--record-lineage",
            "--mock-smoke",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "External ingest:" in result.output
    assert "passed: True" in result.output

    events = LineageRegistry(str(campaign_dir / "scion.db")).query_by_branch(
        "external_branch"
    )
    assert len(events) == 1
    assert events[0]["event_kind"] == "external_proposal_ingest"
    assert events[0]["hypothesis_text"] == hypothesis_text
    audit_payload = json.loads(events[0]["audit_payload_json"])
    assert audit_payload["provenance"]["run_id"] == "run-001"
    assert audit_payload["resolved_safe_data_roots"] == [
        str((tmp_path / "data").resolve())
    ]
