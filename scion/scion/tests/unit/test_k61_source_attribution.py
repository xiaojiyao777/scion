from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from scion.core.branch import BranchController
from scion.core.fixed_candidate_replay import (
    build_fixed_candidate_replay_manifest,
    materialize_candidate_workspace,
)
from scion.core.formal_candidate_artifacts import (
    FormalCandidatePatchArtifactRecorder,
)
from scion.core.models import (
    CanaryResult,
    ChampionState,
    ContractResult,
    Decision,
    EvalStats,
    ExperimentStage,
    HypothesisProposal,
    HypothesisRecord,
    ProtocolResult,
    VerificationResult,
)
from scion.proposal.context_manager.code_context import _validate_source_ledger
from scion.proposal.edit_protocol.source_discovery import source_digest_for_content
from scion.proposal.engine.parsing import _parse_patch


def _source_ledger(primary: str, integration: str) -> dict[str, object]:
    return {
        "schema_version": "proposal-source-ledger.v2",
        "approved_target": "solver.py",
        "entries": [
            {
                "path": "solver.py",
                "content": primary,
                "digest": source_digest_for_content(primary),
                "owner": "approved_target",
                "provenance": "champion_snapshot",
                "visibility": "full_current",
                "reason": "ok",
            },
            {
                "path": "scheduler.py",
                "content": integration,
                "digest": source_digest_for_content(integration),
                "owner": "branch_current_integration",
                "provenance": "branch_workspace",
                "visibility": "full_current",
                "reason": "ok",
            },
        ],
        "views": {
            "champion_research": [],
            "reference": [],
            "api_reference": ["solver.py"],
            "integration_full": ["solver.py", "scheduler.py"],
            "integration_summary": [],
            "branch_current": ["scheduler.py"],
            "required_full": [],
        },
        "target_api_guidance": "",
    }


def _multi_file_patch(primary: str, integration: str):
    return _parse_patch(
        {
            "file_path": "solver.py",
            "action": "modify",
            "edit_intent": "exact_replace",
            "source_digest": source_digest_for_content(primary),
            "old_string": "return 1",
            "new_string": "return 2",
            "replace_all": False,
            "content_after": None,
            "full_file_reason": "",
            "evidence_refs": [],
            "additional_changes": [
                {
                    "file_path": "scheduler.py",
                    "action": "modify",
                    "edit_intent": "exact_replace",
                    "source_digest": source_digest_for_content(integration),
                    "old_string": "return 1",
                    "new_string": "return 3",
                    "replace_all": False,
                    "content_after": None,
                    "full_file_reason": "",
                    "evidence_refs": [],
                }
            ],
            "test_hint": None,
        },
        context={"proposal_source_ledger": _source_ledger(primary, integration)},
    )


def test_source_ledger_requires_one_valid_owner_for_every_file() -> None:
    primary = "def solve():\n    return 1\n"
    integration = "def schedule():\n    return 1\n"
    ledger = _source_ledger(primary, integration)

    assert {
        entry["path"]: entry["owner"] for entry in ledger["entries"]  # type: ignore[index]
    } == {
        "solver.py": "approved_target",
        "scheduler.py": "branch_current_integration",
    }
    _validate_source_ledger(ledger)

    missing_owner = deepcopy(ledger)
    del missing_owner["entries"][0]["owner"]  # type: ignore[index]
    with pytest.raises(ValueError, match="unknown or missing keys"):
        _validate_source_ledger(missing_owner)

    invalid_owner = deepcopy(ledger)
    invalid_owner["entries"][0]["owner"] = "renderer_guess"  # type: ignore[index]
    with pytest.raises(ValueError, match="invalid source ledger owner"):
        _validate_source_ledger(invalid_owner)

    wrong_target_owner = deepcopy(ledger)
    wrong_target_owner["entries"][0]["owner"] = "champion_api_support"  # type: ignore[index]
    with pytest.raises(ValueError, match="approved target has invalid owner"):
        _validate_source_ledger(wrong_target_owner)


def test_direct_multi_file_source_attribution_survives_artifact_and_fixed_replay(
    tmp_path: Path,
) -> None:
    campaign_dir = tmp_path / "campaign"
    base_workspace = campaign_dir / "workspaces" / "champion"
    candidate_workspace = campaign_dir / "workspaces" / "candidate"
    base_workspace.mkdir(parents=True)
    candidate_workspace.mkdir(parents=True)
    primary = "def solve():\n    return 1\n"
    integration = "def schedule():\n    return 1\n"
    (base_workspace / "solver.py").write_text(primary, encoding="utf-8")
    (base_workspace / "scheduler.py").write_text(integration, encoding="utf-8")
    patch = _multi_file_patch(primary, integration)
    patch.repair_attribution = (
        *patch.repair_attribution,
        {
            "repair_kind": "typed_edit_noop_dropped",
            "file_path": "scheduler.py",
            "reason": "exact_replace_noop",
        },
    )
    (candidate_workspace / "solver.py").write_text(
        patch.code_content,
        encoding="utf-8",
    )
    (candidate_workspace / "scheduler.py").write_text(
        patch.additional_changes[0].code_content,
        encoding="utf-8",
    )

    controller = BranchController()
    branch = controller.create_branch(
        ChampionState(
            version=1,
            operator_pool={},
            solver_config_hash="solver-hash",
            code_snapshot_path=str(base_workspace),
            code_snapshot_hash="champion-hash",
        )
    )
    branch.current_code_hash = "candidate-code-hash"
    hypothesis = HypothesisProposal(
        hypothesis_text="Coordinate construction and scheduling.",
        change_locus="solver_design",
        action="modify",
        target_file="solver.py",
    )
    h_record = HypothesisRecord(
        hypothesis_id="h-multi-file",
        branch_id=branch.branch_id,
        change_locus="solver_design",
        action="modify",
        status="running",
        target_file="solver.py",
    )
    protocol_result = ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=EvalStats(
            n_cases=2,
            wins=1,
            losses=0,
            ties=1,
            win_rate=0.5,
            median_delta=1.0,
            ci_low=0.0,
            ci_high=2.0,
        ),
        gate_outcome="expand",
        reason_codes=("SCREENING_EXPAND",),
        exposed_summary="multi-file screening",
        raw_metrics_ref="metrics/screening.json",
    )
    recorder = FormalCandidatePatchArtifactRecorder(
        campaign_dir,
        protocol_version="protocol-v3",
        problem_spec_hash="problem-hash",
        split_manifest_hash="split-hash",
        seed_ledger_hash="seed-hash",
    )
    artifact_ref = recorder.record(
        branch=branch,
        hypothesis=hypothesis,
        h_record=h_record,
        patch=patch,
        protocol_result=protocol_result,
        canary_result=CanaryResult(passed=True),
        contract_result=ContractResult(passed=True, checks=()),
        verification_result=VerificationResult(passed=True, checks=()),
        decision=Decision.EXPAND_SCREENING,
        decision_reason_codes=("SCREENING_EXPAND",),
        workspace=str(candidate_workspace),
        base_workspace=str(base_workspace),
    )

    assert artifact_ref
    artifact_path = campaign_dir / artifact_ref
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert artifact["schema"] == "scion.formal_candidate_patch_artifact.v2"
    normalization_events = artifact["patch"]["normalization_events"]
    assert {
        event["repair_kind"] for event in normalization_events
    } == {"typed_edit_normalization", "typed_edit_noop_dropped"}
    assert any(
        event == {
            "repair_kind": "typed_edit_noop_dropped",
            "file_path": "scheduler.py",
            "reason": "exact_replace_noop",
        }
        for event in normalization_events
    )
    files = {item["file_path"]: item for item in artifact["patch"]["files"]}
    assert files["solver.py"]["source_attribution"] == {
        "schema_version": "formal-file-source-attribution.v1",
        "origin": "proposal_source_ledger",
        "source_ledger_owner": "approved_target",
        "source_provenance": "champion_snapshot",
        "source_visibility": "full_current",
        "source_digest": source_digest_for_content(primary),
    }
    assert files["scheduler.py"]["source_attribution"] == {
        "schema_version": "formal-file-source-attribution.v1",
        "origin": "proposal_source_ledger",
        "source_ledger_owner": "branch_current_integration",
        "source_provenance": "branch_workspace",
        "source_visibility": "full_current",
        "source_digest": source_digest_for_content(integration),
    }

    manifest = build_fixed_candidate_replay_manifest(
        campaign_dir,
        source_arm="record_only",
        comparison_id="multi-file-source-attribution",
        generated_at="2026-07-13T00:00:00+00:00",
    )
    candidate = manifest["candidates"][0]
    assert candidate["file_source_attributions"] == [
        {"file_path": "solver.py", **files["solver.py"]["source_attribution"]},
        {
            "file_path": "scheduler.py",
            **files["scheduler.py"]["source_attribution"],
        },
    ]

    replay_workspace = materialize_candidate_workspace(
        candidate=candidate,
        candidate_patch=artifact,
        source_campaign_dir=campaign_dir,
        output_dir=tmp_path / "replay",
        arm="record_only",
    )
    assert (replay_workspace / "solver.py").read_text(encoding="utf-8") == (
        patch.code_content
    )
    assert (replay_workspace / "scheduler.py").read_text(encoding="utf-8") == (
        patch.additional_changes[0].code_content
    )

    corrupted = deepcopy(artifact)
    corrupted["patch"]["files"][1]["source_attribution"][
        "source_ledger_owner"
    ] = "renderer_guess"
    with pytest.raises(ValueError, match="invalid source ledger owner"):
        materialize_candidate_workspace(
            candidate=candidate,
            candidate_patch=corrupted,
            source_campaign_dir=campaign_dir,
            output_dir=tmp_path / "invalid-replay",
            arm="record_only",
        )
