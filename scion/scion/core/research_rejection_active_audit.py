"""Startup ownership audit for active direct-v3 proposal attempts."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Any, Mapping

from scion.core.decision_completion_transaction import (
    DecisionCompletionStore,
    branch_to_payload,
)
from scion.core.execution_outcome import (
    ExecutionOutcome,
    ExecutionOutcomeRecord,
    branch_has_execution_hold,
    install_branch_execution_hold,
    record_execution_outcome_event,
)
from scion.core.models import Branch, BranchState, HypothesisRecord
from scion.core.proposal_pipeline.attempts import ProposalAttemptRecorder
from scion.core.verified_candidate_commit import (
    VERIFIED_CANDIDATE_COMMIT_REF_SCHEMA,
    VERIFIED_CANDIDATE_COMMIT_SCHEMA,
)


_STALE_STATES = frozenset({BranchState.STALE, BranchState.STALE_WEIGHT_UPDATE})


@dataclass(frozen=True)
class ActiveAttemptHold:
    branch_id: str
    hypothesis_id: str | None
    attempt_id: str
    reason: str


def audit_unowned_active_attempts(
    *,
    db_path: str,
    campaign_id: str,
    branches: tuple[Branch, ...],
    active_hypotheses: tuple[HypothesisRecord, ...],
    branch_store: Any,
    registry: Any,
    prevalidated_candidate_owners: Mapping[str, str] | None = None,
) -> tuple[ActiveAttemptHold, ...]:
    """Install one conservative hold per genuinely unowned active H graph."""

    transitions = _load_transitions(db_path, campaign_id=campaign_id)
    active_h_by_branch: dict[str, list[HypothesisRecord]] = {}
    for hypothesis in active_hypotheses:
        active_h_by_branch.setdefault(hypothesis.branch_id, []).append(hypothesis)
    holds: list[ActiveAttemptHold] = []
    for branch in branches:
        if branch.state in _STALE_STATES or branch_has_execution_hold(branch):
            continue
        branch_transitions = [
            item for item in transitions if item["branch_id"] == branch.branch_id
        ]
        hypotheses = active_h_by_branch.get(branch.branch_id, [])
        hold = _unowned_hold_for_branch(
            branch,
            hypotheses=hypotheses,
            transitions=branch_transitions,
            db_path=db_path,
            campaign_id=campaign_id,
            prevalidated_hypothesis_id=(
                (prevalidated_candidate_owners or {}).get(branch.branch_id)
            ),
        )
        if hold is None:
            continue
        record = ExecutionOutcomeRecord(
            outcome=ExecutionOutcome.NOT_EVALUATED,
            reason_code="UNOWNED_ACTIVE_PROPOSAL_ATTEMPT",
            detail=hold.reason,
            provenance={
                "owner": "research_rejection_active_audit",
                "stage": "startup_recovery",
                "attempt_id": hold.attempt_id,
                "hypothesis_id": hold.hypothesis_id,
            },
        )
        install_branch_execution_hold(branch, record)
        branch_store.save(branch)
        record_execution_outcome_event(
            registry=registry,
            campaign_id=campaign_id,
            branch_id=branch.branch_id,
            hypothesis_id=hold.hypothesis_id,
            record=record,
            event_kind="unowned_active_attempt_hold",
        )
        holds.append(hold)
    return tuple(holds)


def _unowned_hold_for_branch(
    branch: Branch,
    *,
    hypotheses: list[HypothesisRecord],
    transitions: list[dict[str, Any]],
    db_path: str,
    campaign_id: str,
    prevalidated_hypothesis_id: str | None,
) -> ActiveAttemptHold | None:
    groups = _attempt_groups(transitions)
    started_h_without_terminal = [
        group
        for group in groups.values()
        if group[0].get("phase") == "hypothesis"
        and _group_statuses(group) == ("started",)
    ]
    if not hypotheses:
        orphan = _orphan_hold_without_active_h(
            branch,
            groups=groups,
            db_path=db_path,
        )
        if orphan is not None:
            return orphan
        if len(started_h_without_terminal) == 1:
            attempt = started_h_without_terminal[0][0]
            return ActiveAttemptHold(
                branch_id=branch.branch_id,
                hypothesis_id=None,
                attempt_id=str(attempt["attempt_id"]),
                reason="started hypothesis attempt has no terminal transition",
            )
        if started_h_without_terminal:
            return ActiveAttemptHold(
                branch_id=branch.branch_id,
                hypothesis_id=None,
                attempt_id="ambiguous",
                reason="multiple unowned hypothesis attempts are ambiguous",
            )
        return None
    if len(hypotheses) != 1:
        return ActiveAttemptHold(
            branch_id=branch.branch_id,
            hypothesis_id=None,
            attempt_id="ambiguous",
            reason="multiple active hypotheses own one branch",
        )
    hypothesis = hypotheses[0]
    if prevalidated_hypothesis_id == hypothesis.hypothesis_id:
        return None
    if _has_current_committed_decision_owner(
        db_path,
        branch=branch,
        hypothesis=hypothesis,
    ):
        return None
    if _has_verified_candidate_owner(branch, hypothesis=hypothesis):
        # Composition restores only physically validated verified-candidate
        # owners.  Their exact current Branch/H identity is authoritative over
        # historical transition damage and pre-proposal_digest H rows.
        return None
    invalid_groups = [
        group
        for group in groups.values()
        if any(item.get("invalid") for item in group)
        and _group_claims_hypothesis(group, hypothesis.hypothesis_id)
    ]
    if invalid_groups:
        return ActiveAttemptHold(
            branch_id=branch.branch_id,
            hypothesis_id=hypothesis.hypothesis_id,
            attempt_id=str(invalid_groups[0][0].get("attempt_id") or "ambiguous"),
            reason="proposal transition evidence is malformed or misbound",
        )
    h_groups = [
        group
        for group in groups.values()
        if group[-1].get("phase") == "hypothesis"
        and group[-1].get("hypothesis_id") == hypothesis.hypothesis_id
    ]
    if len(h_groups) != 1 or _group_statuses(h_groups[0]) != (
        "started",
        "generated",
    ):
        return ActiveAttemptHold(
            branch_id=branch.branch_id,
            hypothesis_id=hypothesis.hypothesis_id,
            attempt_id=(
                str(h_groups[0][0].get("attempt_id") or "ambiguous")
                if h_groups
                else "missing"
            ),
            reason="active hypothesis transition ownership is incomplete/ambiguous",
        )
    h_terminal = h_groups[0][-1]
    if (
        not _valid_sha256(hypothesis.proposal_digest)
        or hypothesis.proposal_digest != h_terminal.get("hypothesis_digest")
    ):
        return ActiveAttemptHold(
            branch_id=branch.branch_id,
            hypothesis_id=hypothesis.hypothesis_id,
            attempt_id=str(h_terminal["attempt_id"]),
            reason="active hypothesis proposal digest conflicts with its provider owner",
        )
    anchors = h_terminal.get("anchors") or {}
    if (
        anchors.get("branch_base_champion_id") != branch.base_champion_id
        or anchors.get("branch_base_champion_hash") != branch.base_champion_hash
    ):
        return ActiveAttemptHold(
            branch_id=branch.branch_id,
            hypothesis_id=hypothesis.hypothesis_id,
            attempt_id=str(h_terminal["attempt_id"]),
            reason="active hypothesis champion anchor drifted",
        )
    h_attempt_id = str(h_terminal["attempt_id"])
    code_groups = [
        group
        for group in groups.values()
        if group[-1].get("phase") == "code"
        and group[-1].get("continuation_of_attempt_id") == h_attempt_id
        and group[-1].get("hypothesis_id") == hypothesis.hypothesis_id
    ]
    if not code_groups:
        return ActiveAttemptHold(
            branch_id=branch.branch_id,
            hypothesis_id=hypothesis.hypothesis_id,
            attempt_id=h_attempt_id,
            reason="generated hypothesis has no code child owner",
        )
    if len(code_groups) != 1:
        return ActiveAttemptHold(
            branch_id=branch.branch_id,
            hypothesis_id=hypothesis.hypothesis_id,
            attempt_id="ambiguous",
            reason="active hypothesis has ambiguous code children",
        )
    code_group = code_groups[0]
    code_attempt_id = str(code_group[0]["attempt_id"])
    statuses = _group_statuses(code_group)
    if statuses == ("started",):
        return ActiveAttemptHold(
            branch_id=branch.branch_id,
            hypothesis_id=hypothesis.hypothesis_id,
            attempt_id=code_attempt_id,
            reason="started code attempt has no terminal transition",
        )
    if statuses != ("started", "generated"):
        return ActiveAttemptHold(
            branch_id=branch.branch_id,
            hypothesis_id=hypothesis.hypothesis_id,
            attempt_id=code_attempt_id,
            reason="code attempt transition ownership is ambiguous",
        )
    if any(
        item.get("hypothesis_digest") != hypothesis.proposal_digest
        for item in code_group
    ):
        return ActiveAttemptHold(
            branch_id=branch.branch_id,
            hypothesis_id=hypothesis.hypothesis_id,
            attempt_id=code_attempt_id,
            reason="code attempt hypothesis digest conflicts with its durable H owner",
        )
    if _code_attempt_has_rejection_owner(
        db_path,
        campaign_id=campaign_id,
        attempt_id=code_attempt_id,
    ):
        return ActiveAttemptHold(
            branch_id=branch.branch_id,
            hypothesis_id=hypothesis.hypothesis_id,
            attempt_id=code_attempt_id,
            reason="committed rejection still has an active hypothesis",
        )
    return ActiveAttemptHold(
        branch_id=branch.branch_id,
        hypothesis_id=hypothesis.hypothesis_id,
        attempt_id=code_attempt_id,
        reason="generated code has no rejection or verified-candidate owner",
    )


def _load_transitions(db_path: str, *, campaign_id: str) -> list[dict[str, Any]]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT rowid, event_id, campaign_id, branch_id, hypothesis_id,
                   event_kind, stage, audit_payload_json
            FROM experiment_events
            WHERE event_kind = 'proposal_attempt_transition'
              AND campaign_id = ?
            ORDER BY rowid ASC
            """,
            (campaign_id,),
        ).fetchall()
    transitions: list[dict[str, Any]] = []
    for row in rows:
        try:
            payload = json.loads(row["audit_payload_json"] or "")
        except (TypeError, ValueError):
            payload = None
        if (
            not isinstance(payload, dict)
            or row["event_kind"] != "proposal_attempt_transition"
            or payload.get("campaign_id") != row["campaign_id"]
            or payload.get("campaign_id") != campaign_id
            or payload.get("branch_id") != row["branch_id"]
            or payload.get("hypothesis_id") != row["hypothesis_id"]
            or row["stage"] != f"proposal_{payload.get('phase')}"
        ):
            transitions.append(_malformed_transition(row, payload))
            continue
        try:
            ProposalAttemptRecorder.validate_transition(payload)
        except (TypeError, ValueError):
            transitions.append(_malformed_transition(row, payload))
            continue
        transitions.append({**payload, "event_id": row["event_id"]})
    return transitions


def _attempt_groups(
    transitions: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for transition in transitions:
        groups.setdefault(str(transition.get("attempt_id") or "ambiguous"), []).append(
            transition
        )
    return groups


def _malformed_transition(
    row: sqlite3.Row,
    payload: Mapping[str, Any] | None,
) -> dict[str, Any]:
    claimed_hypothesis_ids = {
        str(value)
        for value in (
            row["hypothesis_id"],
            payload.get("hypothesis_id") if isinstance(payload, Mapping) else None,
        )
        if str(value or "")
    }
    return {
        "attempt_id": str(
            payload.get("attempt_id") if isinstance(payload, Mapping) else ""
        )
        or "ambiguous",
        "branch_id": row["branch_id"],
        "hypothesis_id": row["hypothesis_id"],
        "claimed_hypothesis_ids": tuple(sorted(claimed_hypothesis_ids)),
        "continuation_of_attempt_id": (
            payload.get("continuation_of_attempt_id")
            if isinstance(payload, Mapping)
            else None
        ),
        "phase": str(
            payload.get("phase") if isinstance(payload, Mapping) else "invalid"
        )
        or "invalid",
        "status": "invalid",
        "invalid": True,
    }


def _group_claims_hypothesis(
    group: list[dict[str, Any]],
    hypothesis_id: str,
) -> bool:
    return any(
        item.get("hypothesis_id") == hypothesis_id
        or hypothesis_id in item.get("claimed_hypothesis_ids", ())
        for item in group
    )


def _valid_sha256(value: Any) -> bool:
    digest = str(value or "")
    return len(digest) == 64 and all(char in "0123456789abcdef" for char in digest)


def _group_statuses(group: list[dict[str, Any]]) -> tuple[str, ...]:
    return tuple(str(item.get("status") or "") for item in group)


def _code_attempt_has_rejection_owner(
    db_path: str,
    *,
    campaign_id: str,
    attempt_id: str,
) -> bool:
    try:
        with sqlite3.connect(db_path) as conn:
            row = conn.execute(
                """
                SELECT status FROM research_rejection_completion_intents
                WHERE campaign_id = ? AND provider_attempt_id = ?
                """,
                (campaign_id, attempt_id),
            ).fetchone()
    except sqlite3.OperationalError as exc:
        if "no such table" not in str(exc):
            raise
        return False
    return row is not None and row[0] == "committed"


def _orphan_hold_without_active_h(
    branch: Branch,
    *,
    groups: Mapping[str, list[dict[str, Any]]],
    db_path: str,
) -> ActiveAttemptHold | None:
    statuses = _hypothesis_statuses(db_path, branch_id=branch.branch_id)
    for attempt_id, group in groups.items():
        phase = str(group[-1].get("phase") or "")
        group_statuses = _group_statuses(group)
        if phase == "hypothesis" and group_statuses == ("started", "generated"):
            hypothesis_id = str(group[-1].get("hypothesis_id") or "")
            if not hypothesis_id or hypothesis_id not in statuses:
                return ActiveAttemptHold(
                    branch_id=branch.branch_id,
                    hypothesis_id=hypothesis_id or None,
                    attempt_id=attempt_id,
                    reason="generated hypothesis has no durable H row owner",
                )
            if statuses[hypothesis_id] == "active":
                return ActiveAttemptHold(
                    branch_id=branch.branch_id,
                    hypothesis_id=hypothesis_id,
                    attempt_id=attempt_id,
                    reason="active H row is missing from startup ownership input",
                )
        if phase == "code" and group_statuses in {
            ("started",),
            ("started", "generated"),
        }:
            hypothesis_id = str(group[-1].get("hypothesis_id") or "")
            if not hypothesis_id or hypothesis_id not in statuses:
                return ActiveAttemptHold(
                    branch_id=branch.branch_id,
                    hypothesis_id=hypothesis_id or None,
                    attempt_id=attempt_id,
                    reason="code attempt has no durable H row owner",
                )
    return None


def _hypothesis_statuses(db_path: str, *, branch_id: str) -> dict[str, str]:
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT hypothesis_id, status FROM hypotheses WHERE branch_id = ?",
            (branch_id,),
        ).fetchall()
    return {str(row[0]): str(row[1]) for row in rows}


def _has_current_committed_decision_owner(
    db_path: str,
    *,
    branch: Branch,
    hypothesis: HypothesisRecord,
) -> bool:
    store = DecisionCompletionStore(db_path)
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT transaction_id
            FROM decision_completion_intents
            WHERE branch_id = ? AND hypothesis_id = ? AND status = 'committed'
            ORDER BY updated_at DESC, transaction_id DESC
            """,
            (branch.branch_id, hypothesis.hypothesis_id),
        ).fetchall()
    live_branch = branch_to_payload(branch)
    for row in rows:
        intent = store.load(str(row[0]))
        if intent is None:
            continue
        if (
            intent.payload.get("target_branch") == live_branch
            and intent.payload.get("target_hypothesis", {}).get("status") == "active"
            and store.verify_committed(intent.transaction_id)
        ):
            return True
    return False


def _has_verified_candidate_owner(
    branch: Branch,
    *,
    hypothesis: HypothesisRecord,
) -> bool:
    marker = (branch.branch_evidence_summary or {}).get("verified_candidate_commit")
    if not isinstance(marker, Mapping):
        return False
    required = (
        "artifact_ref",
        "artifact_sha256",
        "verified_code_hash",
        "executable_snapshot_hash",
        "patch_digest",
        "commit_kind",
    )
    commit_kind = str(marker.get("commit_kind") or "")
    return bool(
        marker.get("schema_version") == VERIFIED_CANDIDATE_COMMIT_REF_SCHEMA
        and marker.get("artifact_schema") == VERIFIED_CANDIDATE_COMMIT_SCHEMA
        and marker.get("hypothesis_id") == hypothesis.hypothesis_id
        and marker.get("promotion_status") == "committed"
        and marker.get("evaluation_status") in {"pending", "completed"}
        and commit_kind in {"explore", "reconcile"}
        and all(str(marker.get(key) or "") for key in required)
        and marker.get("verified_code_hash") == branch.current_code_hash
        and marker.get("verified_code_hash") == branch.last_clean_code_hash
    )


__all__ = ["ActiveAttemptHold", "audit_unowned_active_attempts"]
