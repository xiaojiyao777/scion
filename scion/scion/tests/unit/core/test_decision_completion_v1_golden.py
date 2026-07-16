from __future__ import annotations

import copy
import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

from scion.core.decision_completion_transaction import DecisionCompletionStore
from scion.core.models import (
    Branch,
    BranchState,
    Decision,
    EvalStats,
    ExperimentStage,
    HypothesisRecord,
    ProtocolResult,
)
from scion.lineage.branch_store import BranchStore, HypothesisStore
from scion.lineage.registry import LineageRegistry

_FIXTURE_ROOT = Path(__file__).parents[2] / "fixtures"


def _source_branch(*, typed_commit: bool) -> Branch:
    summary = {"fixture": "decision-completion-v1"}
    if typed_commit:
        summary["verified_candidate_commit"] = {
            "schema_version": "verified-candidate-commit-ref.v1",
            "artifact_schema": "verified-candidate-commit.v1",
            "artifact_ref": "artifacts/verified_candidate_commits/branch-1/h-1.json",
            "artifact_sha256": "a" * 64,
            "hypothesis_id": "hypothesis-1",
            "verified_code_hash": "c" * 64,
            "executable_snapshot_hash": "b" * 64,
            "patch_digest": "d" * 64,
            "promotion_status": "committed",
            "evaluation_status": "pending",
            "commit_kind": "explore",
        }
    return Branch(
        branch_id="branch-1",
        state=BranchState.VALIDATING,
        base_champion_id=7,
        base_champion_hash="e" * 64,
        lineage_id="lineage-1",
        current_code_hash="c" * 64,
        last_clean_code_hash="c" * 64,
        screening_expand_count=1,
        validation_expand_count=0,
        failure_codes=["prior-safe-failure"],
        created_at=datetime(2026, 1, 2, 3, 4, 5),
        updated_at=datetime(2026, 1, 2, 3, 4, 6),
        direction="local_search: deterministic fixture",
        weight_revision=3,
        branch_code_status="clean",
        branch_evidence_summary=summary,
        infra_block_count=0,
    )


def _hypothesis() -> HypothesisRecord:
    return HypothesisRecord(
        hypothesis_id="hypothesis-1",
        branch_id="branch-1",
        change_locus="local_search",
        action="modify",
        status="active",
        target_file="operators/op.py",
        parent_hypothesis_id="hypothesis-0",
        suggested_weight=0.25,
        hypothesis_text="Use a deterministic local-search fixture.",
        family_id="local-search",
        family_source="manual",
        taxonomy_version="v1",
        created_at=datetime(2026, 1, 2, 3, 4, 7),
        base_champion_version=7,
        predicted_direction="improve",
        proposal_digest="f" * 64,
    )


def _protocol_result() -> ProtocolResult:
    return ProtocolResult(
        stage=ExperimentStage.VALIDATION,
        stats=EvalStats(
            n_cases=4,
            wins=1,
            losses=3,
            ties=0,
            win_rate=0.25,
            median_delta=-1.5,
            ci_low=-2.0,
            ci_high=-0.5,
            statistical_status="negative",
            statistical_metric="total_cost",
            total_pairs=8,
            attempted_pairs=8,
            valid_pairs=8,
            pair_wins=2,
            pair_losses=6,
        ),
        gate_outcome="fail",
        reason_codes=("VALIDATION_NEGATIVE",),
        exposed_summary="deterministic fixture",
        raw_metrics_ref="metrics/validation-fixture.json",
        objective_semantics="minimize total_cost",
        case_ids=("case-a", "case-b"),
        seed_set=(11, 13),
        selected_surface="local_search",
    )


def _canonical_projection(tmp_path: Path, *, typed_commit: bool) -> dict[str, object]:
    db_path = tmp_path / "scion.db"
    registry = LineageRegistry(str(db_path))
    source = _source_branch(typed_commit=typed_commit)
    target = copy.deepcopy(source)
    target.state = BranchState.EXPLORE
    target.updated_at = datetime(2026, 1, 2, 3, 4, 8)
    if typed_commit:
        target.branch_evidence_summary["verified_candidate_commit"][
            "evaluation_status"
        ] = "completed"
    hypothesis = _hypothesis()
    BranchStore(registry).save(source)
    HypothesisStore(registry).save(hypothesis)
    store = DecisionCompletionStore(db_path)

    intent = store.prepare(
        source_branch=source,
        target_branch=target,
        hypothesis_record=hypothesis,
        target_hypothesis_status="rejected",
        decision=Decision.CONTINUE_EXPLORE,
        reason_codes=("VALIDATION_NEGATIVE", "VALIDATION_NEGATIVE"),
        protocol_result=_protocol_result(),
    )
    statuses = [intent.status]
    store.commit_state(intent)
    state_committed = store.load(intent.transaction_id)
    assert state_committed is not None
    statuses.append(state_committed.status)

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        intent_row = conn.execute(
            """
            SELECT transaction_id, schema_version, branch_id, hypothesis_id,
                   decision, intent_json, intent_sha256
            FROM decision_completion_intents WHERE transaction_id = ?
            """,
            (intent.transaction_id,),
        ).fetchone()
        event_row = conn.execute(
            """
            SELECT event_id, branch_id, hypothesis_id, event_kind, code_hash,
                   stage, case_ids, seed_set, raw_metrics_ref, decision,
                   decision_reason, audit_payload_json
            FROM experiment_events WHERE event_id = ?
            """,
            (f"decision-completion:{intent.transaction_id}",),
        ).fetchone()
    assert intent_row is not None
    assert event_row is not None

    store.mark_committed(state_committed)
    committed = store.load(intent.transaction_id)
    assert committed is not None
    statuses.append(committed.status)
    intent_values = dict(intent_row)
    event_values = dict(event_row)
    intent_json = str(intent_values.pop("intent_json"))
    audit_payload_json = str(event_values.pop("audit_payload_json"))
    assert (
        json.dumps(json.loads(intent_json), sort_keys=True, separators=(",", ":"))
        == intent_json
    )
    assert (
        json.dumps(
            json.loads(audit_payload_json), sort_keys=True, separators=(",", ":")
        )
        == audit_payload_json
    )
    intent_values["intent_json_sha256"] = hashlib.sha256(
        intent_json.encode("utf-8")
    ).hexdigest()
    intent_values["intent_json"] = intent_json
    event_values["audit_payload_json_sha256"] = hashlib.sha256(
        audit_payload_json.encode("utf-8")
    ).hexdigest()
    event_values["audit_payload_json"] = audit_payload_json
    return {
        "statuses": statuses,
        "intent": intent_values,
        "event": event_values,
    }


@pytest.mark.parametrize(
    ("typed_commit", "fixture_name"),
    (
        (True, "decision_completion_v1_typed_golden.json"),
        (False, "decision_completion_v1_historical_fallback_golden.json"),
    ),
)
def test_decision_completion_v1_matches_canonical_golden(
    tmp_path: Path,
    typed_commit: bool,
    fixture_name: str,
) -> None:
    expected = json.loads((_FIXTURE_ROOT / fixture_name).read_text(encoding="utf-8"))

    actual = _canonical_projection(tmp_path, typed_commit=typed_commit)

    assert actual == expected
    assert actual["statuses"] == ["prepared", "state_committed", "committed"]
