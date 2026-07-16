"""Atomic completion for finalized pre-Protocol research rejections.

This owner is deliberately separate from Decision completion: Contract and
Verification rejection have no Protocol result or Decision.  A committed row
proves that the durable provider attempt, rejected hypothesis, exact clean
branch base, typed lineage event, and (when present) candidate cleanup all
converged before another provider call may be scheduled.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping

from scion.core.decision_completion_transaction import (
    _branch_payload_from_row,
    _hypothesis_payload_from_row,
    _upsert_branch,
    branch_from_payload,
)
from scion.core.execution_outcome import (
    AttemptDisposition,
    ExecutionOutcome,
    ExecutionOutcomeRecord,
    ResearchRejectionDisposition,
)
from scion.core.models import BranchState
from scion.core.proposal_pipeline.attempts import ProposalAttemptRecorder
from scion.core.research_rejection_evidence import (
    upsert_and_validate_research_rejection_event,
)
from scion.core.research_rejection_intent import (
    RESEARCH_REJECTION_COMPLETION_SCHEMA,
    VALID_RESEARCH_REJECTION_PHASES,
    ResearchRejectionCompletionIntent,
    canonical_json,
    completion_id_for_payload,
    intent_from_row,
    jsonable_mapping,
    stable_digest,
    validated_clean_parent,
    validated_rejected_candidate,
    validated_sha256,
)


_VALID_PHASES = VALID_RESEARCH_REJECTION_PHASES
_PHASE_TO_ATTEMPT_PHASE = {
    "hypothesis_contract": "hypothesis",
    "patch_contract": "code",
    "verification": "code",
}


class ResearchRejectionCompletionStore:
    """SQLite owner for exact-once pre-Protocol rejection completion."""

    def __init__(
        self,
        db_path: str | Path,
        *,
        fault_hook: Callable[
            [str, ResearchRejectionCompletionIntent], None
        ]
        | None = None,
    ) -> None:
        self.db_path = str(db_path)
        self.fault_hook = fault_hook
        self._ensure_table()

    def prepare(
        self,
        *,
        campaign_id: str,
        proposal_attempt_ref: Mapping[str, Any],
        branch_id: str,
        hypothesis_id: str,
        rejection_phase: str,
        reason_code: str,
        failed_check: str,
        diagnostic_metadata: Mapping[str, Any],
        clean_code_parent: Mapping[str, Any],
        rejected_candidate: Mapping[str, Any] | None,
        rejected_patch_digest: str | None,
        execution_outcome: ExecutionOutcomeRecord,
        identity_validator: Callable[
            [Mapping[str, Any], Mapping[str, Any] | None], None
        ],
    ) -> ResearchRejectionCompletionIntent:
        """Persist an immutable intent after proving every durable owner."""

        if rejection_phase not in _VALID_PHASES:
            raise ValueError("unsupported research rejection phase")
        if execution_outcome.outcome is not ExecutionOutcome.RESEARCH_REJECTED:
            raise ValueError("research rejection completion requires rejected outcome")
        if not str(campaign_id or "").strip():
            raise ValueError("research rejection campaign identity is required")
        branch_id = str(branch_id or "").strip()
        hypothesis_id = str(hypothesis_id or "").strip()
        if not branch_id or not hypothesis_id:
            raise ValueError("research rejection Branch/H identity is required")
        reason_code = str(reason_code or "").strip()
        failed_check = str(failed_check or "").strip()
        if not reason_code or not failed_check:
            raise ValueError("research rejection reason and failed check are required")

        clean_parent = validated_clean_parent(clean_code_parent)
        candidate = validated_rejected_candidate(rejected_candidate)
        if rejection_phase == "patch_contract":
            patch_contract_digest = validated_sha256(
                rejected_patch_digest,
                "patch Contract rejected patch",
            )
        else:
            if rejected_patch_digest is not None:
                raise ValueError(
                    "only patch Contract rejection may own rejected patch identity"
                )
            patch_contract_digest = None
        if candidate is None:
            if rejection_phase == "verification":
                raise ValueError("verification rejection requires candidate identity")
            workspace_disposition = "none"
        else:
            if rejection_phase != "verification":
                raise ValueError("only verification rejection may own a candidate")
            workspace_disposition = "archive_cleanup"
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            conn.execute("BEGIN IMMEDIATE")
            transition = self._validate_proposal_transition(
                conn,
                campaign_id=campaign_id,
                proposal_attempt_ref=proposal_attempt_ref,
                branch_id=branch_id,
                hypothesis_id=hypothesis_id,
                rejection_phase=rejection_phase,
            )
            persisted_branch = conn.execute(
                "SELECT * FROM branches WHERE branch_id = ?",
                (branch_id,),
            ).fetchone()
            if persisted_branch is None:
                raise RuntimeError(
                    "research rejection source branch is not the persisted owner"
                )
            source_branch_payload = _branch_payload_from_row(persisted_branch)
            if (
                source_branch_payload["state"] != BranchState.EXPLORE.value
                or source_branch_payload["branch_code_status"] != "clean"
            ):
                raise RuntimeError(
                    "research rejection source branch is not a clean creative owner"
                )
            _validate_clean_parent_against_branch(
                clean_parent,
                source_branch_payload,
            )
            _validate_transition_anchors_against_branch(
                transition["anchors"],
                source_branch_payload,
            )
            persisted_hypothesis = conn.execute(
                "SELECT * FROM hypotheses WHERE hypothesis_id = ?",
                (hypothesis_id,),
            ).fetchone()
            if persisted_hypothesis is None:
                raise RuntimeError(
                    "research rejection source hypothesis is not the persisted owner"
                )
            source_hypothesis = _hypothesis_payload_from_row(persisted_hypothesis)
            if (
                source_hypothesis["branch_id"] != branch_id
                or source_hypothesis["status"] != "active"
            ):
                raise RuntimeError(
                    "research rejection source hypothesis is not active/owned"
                )
            proposal_digest = validated_sha256(
                persisted_hypothesis["proposal_digest"],
                "research rejection durable hypothesis proposal",
            )
            if proposal_digest != transition["hypothesis_digest"]:
                raise RuntimeError(
                    "research rejection durable hypothesis proposal identity conflict"
                )
            if (
                patch_contract_digest is not None
                and patch_contract_digest != transition["patch_digest"]
            ):
                raise RuntimeError(
                    "patch Contract rejected patch identity conflict"
                )
            if candidate is not None:
                if candidate["patch_digest"] != transition["patch_digest"]:
                    raise RuntimeError(
                        "research rejection candidate patch identity conflict"
                    )
                if candidate["hypothesis_id"] != hypothesis_id:
                    raise RuntimeError(
                        "research rejection candidate hypothesis conflict"
                    )
            target_branch_payload = dict(source_branch_payload)
            target_branch_payload["screening_expand_count"] = 0
            target_branch_payload["validation_expand_count"] = 0
            target_hypothesis = dict(source_hypothesis)
            target_hypothesis["status"] = "research_rejected"
            core_payload: dict[str, Any] = {
                "schema_version": RESEARCH_REJECTION_COMPLETION_SCHEMA,
                "campaign_id": str(campaign_id),
                "provider_attempt": transition,
                "branch_id": branch_id,
                "hypothesis_id": hypothesis_id,
                "rejection_phase": rejection_phase,
                "reason_code": reason_code,
                "failed_check": failed_check,
                "diagnostic_metadata": jsonable_mapping(diagnostic_metadata),
                "clean_code_parent": clean_parent,
                "rejected_candidate": candidate,
                "rejected_patch_digest": patch_contract_digest,
                "hypothesis_proposal_digest": proposal_digest,
                "workspace_disposition": workspace_disposition,
                "target_branch_state": target_branch_payload["state"],
                "typed_execution_outcome": execution_outcome.to_primitive(),
                "source_branch": source_branch_payload,
                "source_branch_sha256": stable_digest(source_branch_payload),
                "target_branch": target_branch_payload,
                "target_branch_sha256": stable_digest(target_branch_payload),
                "source_hypothesis": source_hypothesis,
                "source_hypothesis_sha256": stable_digest(source_hypothesis),
                "target_hypothesis": target_hypothesis,
                "target_hypothesis_sha256": stable_digest(target_hypothesis),
            }
            completion_id = completion_id_for_payload(core_payload)
            archive_ref = (
                f"archive/research-rejection-{completion_id}"
                if candidate is not None
                else None
            )
            payload = {
                **core_payload,
                "completion_id": completion_id,
                "archive_ref": archive_ref,
            }
            intent_sha256 = stable_digest(payload)
            attempt_id = str(transition["attempt_id"])
            existing_row = conn.execute(
                """
                SELECT * FROM research_rejection_completion_intents
                WHERE campaign_id = ? AND provider_attempt_id = ?
                """,
                (str(campaign_id), attempt_id),
            ).fetchone()
            if existing_row is not None:
                existing = intent_from_row(existing_row)
                if existing.payload != payload:
                    raise RuntimeError(
                        "provider attempt already owns a different rejection completion"
                    )
                conn.commit()
                return existing
            identity_validator(clean_parent, candidate)
            now = datetime.now().isoformat()
            conn.execute(
                """
                INSERT INTO research_rejection_completion_intents
                (completion_id, schema_version, campaign_id, provider_attempt_id,
                 branch_id, hypothesis_id, rejection_phase, intent_json,
                 intent_sha256, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'prepared', ?, ?)
                """,
                (
                    completion_id,
                    RESEARCH_REJECTION_COMPLETION_SCHEMA,
                    str(campaign_id),
                    attempt_id,
                    branch_id,
                    hypothesis_id,
                    rejection_phase,
                    canonical_json(payload),
                    intent_sha256,
                    now,
                    now,
                ),
            )
            conn.commit()
        intent = self.load(completion_id)
        if intent is None or intent.payload != payload:
            raise RuntimeError("research rejection intent identity conflict")
        self._fault("after_prepare", intent)
        return intent

    def load(
        self,
        completion_id: str,
    ) -> ResearchRejectionCompletionIntent | None:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT * FROM research_rejection_completion_intents
                WHERE completion_id = ?
                """,
                (completion_id,),
            ).fetchone()
        return intent_from_row(row) if row is not None else None

    def load_for_attempt(
        self,
        campaign_id: str,
        provider_attempt_id: str,
    ) -> ResearchRejectionCompletionIntent | None:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT * FROM research_rejection_completion_intents
                WHERE campaign_id = ? AND provider_attempt_id = ?
                """,
                (str(campaign_id), str(provider_attempt_id)),
            ).fetchone()
        return intent_from_row(row) if row is not None else None

    def pending(self) -> list[ResearchRejectionCompletionIntent]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT * FROM research_rejection_completion_intents
                WHERE status != 'committed'
                ORDER BY created_at ASC, completion_id ASC
                """
            ).fetchall()
        return [intent_from_row(row) for row in rows]

    def commit_state(self, intent: ResearchRejectionCompletionIntent) -> None:
        """Atomically commit H, clean Branch, event, and state_committed."""

        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            conn.execute("BEGIN IMMEDIATE")
            current = self._current_intent(conn, intent.completion_id)
            if current.payload != intent.payload:
                raise RuntimeError("research rejection intent changed")
            if current.status in {"state_committed", "committed"}:
                _validate_committed_state(conn, current)
                conn.commit()
                return

            branch_row = conn.execute(
                "SELECT * FROM branches WHERE branch_id = ?",
                (current.branch_id,),
            ).fetchone()
            if branch_row is None:
                raise RuntimeError("research rejection branch is unavailable")
            branch_digest = stable_digest(_branch_payload_from_row(branch_row))
            if branch_digest not in {
                current.payload["source_branch_sha256"],
                current.payload["target_branch_sha256"],
            }:
                raise RuntimeError("research rejection branch identity conflict")

            hypothesis_row = conn.execute(
                "SELECT * FROM hypotheses WHERE hypothesis_id = ?",
                (current.hypothesis_id,),
            ).fetchone()
            if hypothesis_row is None:
                raise RuntimeError("research rejection hypothesis is unavailable")
            hypothesis_digest = stable_digest(
                _hypothesis_payload_from_row(hypothesis_row)
            )
            if hypothesis_digest not in {
                current.payload["source_hypothesis_sha256"],
                current.payload["target_hypothesis_sha256"],
            }:
                raise RuntimeError("research rejection hypothesis identity conflict")
            _validate_durable_hypothesis_proposal(hypothesis_row, current)
            _validate_provider_bindings(current)

            self._fault("before_hypothesis_update", current)
            conn.execute(
                "UPDATE hypotheses SET status = 'research_rejected' "
                "WHERE hypothesis_id = ?",
                (current.hypothesis_id,),
            )
            self._fault("after_hypothesis_update", current)
            _upsert_branch(
                conn,
                branch_from_payload(current.payload["target_branch"]),
            )
            self._fault("after_branch_upsert", current)
            upsert_and_validate_research_rejection_event(conn, current)
            self._fault("after_typed_event", current)
            conn.execute(
                """
                UPDATE research_rejection_completion_intents
                SET status = 'state_committed', updated_at = ?
                WHERE completion_id = ?
                """,
                (datetime.now().isoformat(), current.completion_id),
            )
            self._fault("before_state_commit", current)
            conn.commit()

    def complete(
        self,
        intent: ResearchRejectionCompletionIntent,
        *,
        cleanup: Callable[[ResearchRejectionCompletionIntent], None],
        ownership_validator: Callable[
            [ResearchRejectionCompletionIntent, bool], None
        ],
    ) -> ResearchRejectionCompletionIntent:
        """Converge one intent through cleanup and final committed marker."""

        ownership_validator(intent, False)
        self.commit_state(intent)
        refreshed = self.load(intent.completion_id)
        if refreshed is None:
            raise RuntimeError("research rejection intent disappeared")
        self._fault("before_cleanup", refreshed)
        if refreshed.workspace_disposition != "none":
            cleanup(refreshed)
        self._fault("after_cleanup", refreshed)
        ownership_validator(refreshed, True)
        self.mark_committed(refreshed)
        committed = self.load(intent.completion_id)
        if committed is None or committed.status != "committed":
            raise RuntimeError("research rejection completion did not commit")
        return committed

    def mark_committed(self, intent: ResearchRejectionCompletionIntent) -> None:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            current = self._current_intent(conn, intent.completion_id)
            if current.payload != intent.payload:
                raise RuntimeError("research rejection intent changed")
            _validate_committed_state(conn, current)
            if current.status == "committed":
                return
            if current.status != "state_committed":
                raise RuntimeError("research rejection state is not committed")
            self._fault("before_final_mark", current)
            conn.execute(
                """
                UPDATE research_rejection_completion_intents
                SET status = 'committed', updated_at = ?
                WHERE completion_id = ?
                """,
                (datetime.now().isoformat(), current.completion_id),
            )
        committed = self.load(intent.completion_id)
        if committed is None:
            raise RuntimeError("research rejection committed intent disappeared")
        self._fault("after_final_mark", committed)

    def recover_pending(
        self,
        *,
        cleanup: Callable[[ResearchRejectionCompletionIntent], None],
        ownership_validator: Callable[
            [ResearchRejectionCompletionIntent, bool], None
        ],
    ) -> tuple[str, ...]:
        """Recover using each intent's own persisted campaign identity."""

        recovered: list[str] = []
        for intent in self.pending():
            self.complete(
                intent,
                cleanup=cleanup,
                ownership_validator=ownership_validator,
            )
            recovered.append(intent.completion_id)
        return tuple(recovered)

    def verify_committed(
        self,
        marker: ResearchRejectionDisposition,
        *,
        ownership_validator: Callable[
            [ResearchRejectionCompletionIntent, bool], None
        ],
    ) -> bool:
        """Control-grade read-only authorization for scheduler continuation."""

        if (
            not isinstance(marker, ResearchRejectionDisposition)
            or marker.disposition
            is not AttemptDisposition.ATTEMPT_REJECT_TO_BASE
        ):
            return False
        intent = self.load(marker.completion_id)
        if (
            intent is None
            or intent.status != "committed"
            or intent.campaign_id != marker.campaign_id
            or intent.provider_attempt_id != marker.provider_attempt_id
            or intent.rejection_phase != marker.rejection_phase
        ):
            return False
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            conn.execute("BEGIN")
            _validate_committed_state(conn, intent)
            provider = intent.payload["provider_attempt"]
            ref = {
                "attempt_id": provider["attempt_id"],
                "lineage_event_id": provider["event_id"],
                "started_lineage_event_id": provider["started_event_id"],
                "phase": provider["phase"],
                "status": provider["status"],
            }
            if provider.get("continuation_of_attempt_id"):
                ref["hypothesis_attempt_id"] = provider[
                    "continuation_of_attempt_id"
                ]
            transition = self._validate_proposal_transition(
                conn,
                campaign_id=intent.campaign_id,
                proposal_attempt_ref=ref,
                branch_id=intent.branch_id,
                hypothesis_id=intent.hypothesis_id,
                rejection_phase=intent.rejection_phase,
            )
            if transition != provider:
                raise RuntimeError(
                    "committed research rejection provider identity conflict"
                )
            conn.rollback()
        ownership_validator(intent, True)
        return True

    def durable_counts(
        self,
        campaign_id: str,
        *,
        archive_validator: Callable[[ResearchRejectionCompletionIntent], None],
    ) -> dict[str, Any]:
        """Return exact committed audit counts for one durable campaign."""

        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT * FROM research_rejection_completion_intents
                WHERE campaign_id = ? AND status = 'committed'
                ORDER BY created_at ASC, completion_id ASC
                """,
                (str(campaign_id),),
            ).fetchall()
        phase_counts: dict[str, int] = {}
        reason_counts: dict[str, int] = {}
        completion_ids: list[str] = []
        for row in rows:
            intent = intent_from_row(row)
            with self._connect() as conn:
                conn.row_factory = sqlite3.Row
                conn.execute("BEGIN")
                _validate_durable_completion(conn, intent, store=self)
                conn.rollback()
            archive_validator(intent)
            payload = intent.payload
            phase = str(payload["rejection_phase"])
            reason = str(payload["reason_code"])
            phase_counts[phase] = phase_counts.get(phase, 0) + 1
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
            completion_ids.append(str(payload["completion_id"]))
        return {
            "total": len(rows),
            "by_phase": phase_counts,
            "by_reason": reason_counts,
            "completion_ids": completion_ids,
        }

    def _validate_proposal_transition(
        self,
        conn: sqlite3.Connection,
        *,
        campaign_id: str,
        proposal_attempt_ref: Mapping[str, Any],
        branch_id: str,
        hypothesis_id: str,
        rejection_phase: str,
    ) -> dict[str, Any]:
        attempt_id = str(proposal_attempt_ref.get("attempt_id") or "")
        event_id = str(proposal_attempt_ref.get("lineage_event_id") or "")
        expected_phase = _PHASE_TO_ATTEMPT_PHASE[rejection_phase]
        if not attempt_id or not event_id:
            raise ValueError("research rejection proposal attempt identity is incomplete")
        parent_attempt_ref = (
            str(proposal_attempt_ref.get("hypothesis_attempt_id") or "")
            if expected_phase == "code"
            else ""
        )
        rows = conn.execute(
            """
            SELECT rowid, event_id, campaign_id, branch_id, hypothesis_id,
                   event_kind, stage, audit_payload_json
            FROM experiment_events
            WHERE event_kind = 'proposal_attempt_transition'
            ORDER BY rowid ASC
            """,
        ).fetchall()
        grouped, parent_group = _claimed_proposal_transition_groups(
            rows,
            campaign_id=str(campaign_id),
            branch_id=branch_id,
            hypothesis_id=hypothesis_id,
            attempt_id=attempt_id,
            expected_phase=expected_phase,
            event_ids={
                event_id,
                str(proposal_attempt_ref.get("started_lineage_event_id") or ""),
            },
            parent_attempt_id=parent_attempt_ref,
        )
        if len(grouped) != 2:
            raise RuntimeError(
                "research rejection proposal transition group is incomplete/ambiguous"
            )
        started_row, started = grouped[0]
        terminal_row, terminal = grouped[1]
        common = {
            "attempt_id": attempt_id,
            "campaign_id": str(campaign_id),
            "branch_id": branch_id,
            "phase": expected_phase,
            "runtime_mode": "direct_v3",
        }
        if any(
            payload.get(key) != value
            for payload in (started, terminal)
            for key, value in common.items()
        ):
            raise RuntimeError("research rejection proposal transition ownership conflict")
        if (
            started.get("status") != "started"
            or terminal.get("status") != "generated"
            or started_row["campaign_id"] != str(campaign_id)
            or started_row["branch_id"] != branch_id
            or started_row["hypothesis_id"] != started.get("hypothesis_id")
            or started_row["stage"] != f"proposal_{expected_phase}"
            or terminal_row["event_id"] != event_id
            or terminal_row["campaign_id"] != str(campaign_id)
            or terminal_row["branch_id"] != branch_id
            or terminal_row["hypothesis_id"] != hypothesis_id
            or terminal_row["stage"] != f"proposal_{expected_phase}"
            or terminal.get("hypothesis_id") != hypothesis_id
            or proposal_attempt_ref.get("phase") != expected_phase
            or proposal_attempt_ref.get("status") != "generated"
            or proposal_attempt_ref.get("attempt_id") != attempt_id
            or proposal_attempt_ref.get("lineage_event_id") != event_id
            or proposal_attempt_ref.get("started_lineage_event_id")
            != started_row["event_id"]
        ):
            raise RuntimeError("research rejection proposal transition ownership conflict")
        for key in ("attempt_kind", "continuation_of_attempt_id"):
            if started.get(key) != terminal.get(key):
                raise RuntimeError(
                    "research rejection proposal transition sequence conflicts"
                )
        if started.get("anchors") != terminal.get("anchors"):
            raise RuntimeError("research rejection proposal anchors changed")
        started_prompt = started.get("prompt_call") or {}
        terminal_prompt = terminal.get("prompt_call") or {}
        if any(
            started_prompt.get(key) != terminal_prompt.get(key)
            for key in ("context_digest", "prompt_hash")
        ):
            raise RuntimeError("research rejection proposal call identity changed")
        if expected_phase == "hypothesis":
            if (
                started.get("attempt_kind") != "initial"
                or started.get("continuation_of_attempt_id") is not None
                or started.get("hypothesis_id") is not None
                or started_row["hypothesis_id"] is not None
                or started.get("hypothesis_digest") is not None
                or started.get("patch_digest") is not None
                or terminal.get("patch_digest") is not None
            ):
                raise RuntimeError("hypothesis attempt transition shape is invalid")
        else:
            parent_attempt_id = str(terminal.get("continuation_of_attempt_id") or "")
            if (
                not parent_attempt_id
                or started.get("hypothesis_id") != hypothesis_id
                or started_row["hypothesis_id"] != hypothesis_id
                or started.get("hypothesis_digest")
                != terminal.get("hypothesis_digest")
                or started.get("patch_digest") is not None
                or not str(terminal.get("hypothesis_digest") or "")
                or not str(terminal.get("patch_digest") or "")
                or proposal_attempt_ref.get("hypothesis_attempt_id")
                != parent_attempt_id
                or started.get("proposal_fingerprint")
                != terminal.get("proposal_fingerprint")
            ):
                raise RuntimeError("code attempt parent identity is incomplete")
            parent = _validated_generated_hypothesis_parent(
                parent_group,
                campaign_id=str(campaign_id),
                branch_id=branch_id,
                hypothesis_id=hypothesis_id,
                attempt_id=parent_attempt_id,
            )
            if (
                parent["hypothesis_digest"] != terminal.get("hypothesis_digest")
                or parent["attempt_id"] != started.get("continuation_of_attempt_id")
                or parent["anchors"] != terminal.get("anchors")
            ):
                raise RuntimeError("code attempt hypothesis parent identity conflicts")
        return {
            "attempt_id": attempt_id,
            "event_id": event_id,
            "started_event_id": str(started_row["event_id"]),
            "phase": expected_phase,
            "status": "generated",
            "patch_digest": terminal.get("patch_digest"),
            "hypothesis_digest": terminal.get("hypothesis_digest"),
            "continuation_of_attempt_id": terminal.get(
                "continuation_of_attempt_id"
            ),
            "anchors": terminal["anchors"],
            "transition_group_sha256": stable_digest([started, terminal]),
        }

    def _current_intent(
        self,
        conn: sqlite3.Connection,
        completion_id: str,
    ) -> ResearchRejectionCompletionIntent:
        row = conn.execute(
            """
            SELECT * FROM research_rejection_completion_intents
            WHERE completion_id = ?
            """,
            (completion_id,),
        ).fetchone()
        if row is None:
            raise RuntimeError("research rejection intent is unavailable")
        return intent_from_row(row)

    def _fault(
        self,
        phase: str,
        intent: ResearchRejectionCompletionIntent,
    ) -> None:
        if self.fault_hook is not None:
            self.fault_hook(phase, intent)

    def _ensure_table(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS research_rejection_completion_intents (
                    completion_id TEXT PRIMARY KEY,
                    schema_version TEXT NOT NULL,
                    campaign_id TEXT NOT NULL,
                    provider_attempt_id TEXT NOT NULL,
                    branch_id TEXT NOT NULL,
                    hypothesis_id TEXT NOT NULL,
                    rejection_phase TEXT NOT NULL,
                    intent_json TEXT NOT NULL,
                    intent_sha256 TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE (campaign_id, provider_attempt_id)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_research_rejection_status
                ON research_rejection_completion_intents(status, created_at)
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=FULL")
        return conn


def _validate_committed_state(
    conn: sqlite3.Connection,
    intent: ResearchRejectionCompletionIntent,
) -> None:
    branch_row = conn.execute(
        "SELECT * FROM branches WHERE branch_id = ?",
        (intent.branch_id,),
    ).fetchone()
    if (
        branch_row is None
        or stable_digest(_branch_payload_from_row(branch_row))
        != intent.payload["target_branch_sha256"]
    ):
        raise RuntimeError("committed research rejection branch identity conflict")
    hypothesis_row = conn.execute(
        "SELECT * FROM hypotheses WHERE hypothesis_id = ?",
        (intent.hypothesis_id,),
    ).fetchone()
    if (
        hypothesis_row is None
        or stable_digest(_hypothesis_payload_from_row(hypothesis_row))
        != intent.payload["target_hypothesis_sha256"]
    ):
        raise RuntimeError("committed research rejection hypothesis identity conflict")
    _validate_durable_hypothesis_proposal(hypothesis_row, intent)
    _validate_provider_bindings(intent)
    event_id = f"research-rejection-completion:{intent.completion_id}"
    event = conn.execute(
        "SELECT event_id FROM experiment_events WHERE event_id = ?",
        (event_id,),
    ).fetchone()
    if event is None:
        raise RuntimeError("committed research rejection event is unavailable")
    # Re-run the exact event projection check; it is idempotent and detects
    # mutation of any typed payload column.
    upsert_and_validate_research_rejection_event(conn, intent)


def _validate_durable_completion(
    conn: sqlite3.Connection,
    intent: ResearchRejectionCompletionIntent,
    *,
    store: ResearchRejectionCompletionStore,
) -> None:
    """Validate immutable history without requiring its old mutable code base."""

    hypothesis_row = conn.execute(
        "SELECT * FROM hypotheses WHERE hypothesis_id = ?",
        (intent.hypothesis_id,),
    ).fetchone()
    if (
        hypothesis_row is None
        or stable_digest(_hypothesis_payload_from_row(hypothesis_row))
        != intent.payload["target_hypothesis_sha256"]
    ):
        raise RuntimeError("durable research rejection hypothesis identity conflict")
    _validate_durable_hypothesis_proposal(hypothesis_row, intent)
    _validate_provider_bindings(intent)
    event_id = f"research-rejection-completion:{intent.completion_id}"
    if conn.execute(
        "SELECT event_id FROM experiment_events WHERE event_id = ?",
        (event_id,),
    ).fetchone() is None:
        raise RuntimeError("durable research rejection event is unavailable")
    upsert_and_validate_research_rejection_event(conn, intent)
    provider = intent.payload["provider_attempt"]
    ref = {
        "attempt_id": provider["attempt_id"],
        "lineage_event_id": provider["event_id"],
        "started_lineage_event_id": provider["started_event_id"],
        "phase": provider["phase"],
        "status": provider["status"],
    }
    if provider.get("continuation_of_attempt_id"):
        ref["hypothesis_attempt_id"] = provider["continuation_of_attempt_id"]
    transition = store._validate_proposal_transition(
        conn,
        campaign_id=intent.campaign_id,
        proposal_attempt_ref=ref,
        branch_id=intent.branch_id,
        hypothesis_id=intent.hypothesis_id,
        rejection_phase=intent.rejection_phase,
    )
    if transition != provider:
        raise RuntimeError("durable research rejection attempt identity conflict")


def _validate_durable_hypothesis_proposal(
    hypothesis_row: sqlite3.Row,
    intent: ResearchRejectionCompletionIntent,
) -> None:
    try:
        proposal_digest = validated_sha256(
            hypothesis_row["proposal_digest"],
            "durable hypothesis proposal",
        )
    except (IndexError, ValueError) as exc:
        raise RuntimeError(
            "durable research rejection hypothesis proposal identity is unavailable"
        ) from exc
    if proposal_digest != intent.payload.get("hypothesis_proposal_digest"):
        raise RuntimeError(
            "durable research rejection hypothesis proposal identity conflict"
        )


def _validate_provider_bindings(
    intent: ResearchRejectionCompletionIntent,
) -> None:
    provider = intent.payload.get("provider_attempt") or {}
    if (
        intent.payload.get("hypothesis_proposal_digest")
        != provider.get("hypothesis_digest")
    ):
        raise RuntimeError("research rejection provider hypothesis identity conflict")
    rejected_patch_digest = intent.payload.get("rejected_patch_digest")
    if intent.rejection_phase == "patch_contract":
        if rejected_patch_digest != provider.get("patch_digest"):
            raise RuntimeError("research rejection provider patch identity conflict")
    elif rejected_patch_digest is not None:
        raise RuntimeError("research rejection provider patch identity is unexpected")


def _validate_clean_parent_against_branch(
    clean_parent: Mapping[str, Any],
    source_branch: Mapping[str, Any],
) -> None:
    last_clean = str(source_branch.get("last_clean_code_hash") or "")
    current = str(source_branch.get("current_code_hash") or "")
    if last_clean or current:
        expected = last_clean or current
        if clean_parent.get("kind") != "branch_workspace":
            raise RuntimeError("durable clean branch lost its workspace parent")
        if clean_parent.get("code_hash") != expected or current not in {"", expected}:
            raise RuntimeError("clean code parent does not match durable branch")
    else:
        if clean_parent.get("kind") != "champion_snapshot":
            raise RuntimeError("fresh branch clean parent is not its champion")
        if clean_parent.get("snapshot_hash") != source_branch.get(
            "base_champion_hash"
        ):
            raise RuntimeError("clean champion parent does not match branch anchor")


def _validate_transition_anchors_against_branch(
    anchors: Mapping[str, Any],
    source_branch: Mapping[str, Any],
) -> None:
    if (
        anchors.get("branch_base_champion_id")
        != source_branch.get("base_champion_id")
        or anchors.get("branch_base_champion_hash")
        != source_branch.get("base_champion_hash")
    ):
        raise RuntimeError("research rejection proposal branch anchor conflicts")


def _claimed_proposal_transition_groups(
    rows: list[sqlite3.Row],
    *,
    campaign_id: str,
    branch_id: str,
    hypothesis_id: str,
    attempt_id: str,
    expected_phase: str,
    event_ids: set[str],
    parent_attempt_id: str,
) -> tuple[
    list[tuple[sqlite3.Row, dict[str, Any]]],
    list[tuple[sqlite3.Row, dict[str, Any]]],
]:
    """Select current owner rows before applying strict transition validation.

    Historical rows are allowed to use older or malformed payloads.  A row is
    in scope only when its payload claims the exact attempt, its event ID is an
    exact current ref, or an otherwise-unidentifiable row claims the current
    Branch/H and phase through its outer columns.
    """

    current_event_ids = {value for value in event_ids if value}
    target_group: list[tuple[sqlite3.Row, dict[str, Any]]] = []
    parent_group: list[tuple[sqlite3.Row, dict[str, Any]]] = []
    for row in rows:
        try:
            decoded = json.loads(row["audit_payload_json"] or "")
        except (TypeError, ValueError):
            decoded = None
        payload = decoded if isinstance(decoded, dict) else None
        payload_attempt_id = str(
            (payload or {}).get("attempt_id") or ""
        ).strip()
        target_claim = (
            payload_attempt_id == attempt_id
            or str(row["event_id"]) in current_event_ids
        )
        parent_claim = bool(
            parent_attempt_id and payload_attempt_id == parent_attempt_id
        )
        if not payload_attempt_id:
            outer_h_owner = bool(
                row["campaign_id"] == campaign_id
                and row["branch_id"] == branch_id
                and row["hypothesis_id"] == hypothesis_id
            )
            if outer_h_owner and row["stage"] == f"proposal_{expected_phase}":
                target_claim = True
            if (
                parent_attempt_id
                and outer_h_owner
                and row["stage"] == "proposal_hypothesis"
            ):
                parent_claim = True
        if not target_claim and not parent_claim:
            continue
        label = (
            "research rejection proposal transition"
            if target_claim
            else "hypothesis parent transition"
        )
        if payload is None:
            raise RuntimeError(f"{label} is invalid")
        try:
            ProposalAttemptRecorder.validate_transition(payload)
        except (TypeError, ValueError) as exc:
            raise RuntimeError(f"{label} is invalid") from exc
        if target_claim:
            target_group.append((row, payload))
        if parent_claim:
            parent_group.append((row, payload))
    return target_group, parent_group


def _validated_generated_hypothesis_parent(
    group: list[tuple[sqlite3.Row, dict[str, Any]]],
    *,
    campaign_id: str,
    branch_id: str,
    hypothesis_id: str,
    attempt_id: str,
) -> dict[str, Any]:
    if len(group) != 2:
        raise RuntimeError("hypothesis parent transition group is incomplete/ambiguous")
    started_row, started = group[0]
    terminal_row, terminal = group[1]
    if (
        started.get("attempt_id") != attempt_id
        or terminal.get("attempt_id") != attempt_id
        or started.get("status") != "started"
        or terminal.get("status") != "generated"
        or started.get("phase") != "hypothesis"
        or terminal.get("phase") != "hypothesis"
        or started.get("campaign_id") != campaign_id
        or terminal.get("campaign_id") != campaign_id
        or started_row["campaign_id"] != campaign_id
        or terminal_row["campaign_id"] != campaign_id
        or started.get("branch_id") != branch_id
        or terminal.get("branch_id") != branch_id
        or started_row["branch_id"] != branch_id
        or terminal_row["branch_id"] != branch_id
        or started_row["stage"] != "proposal_hypothesis"
        or terminal_row["stage"] != "proposal_hypothesis"
        or started.get("attempt_kind") != "initial"
        or terminal.get("attempt_kind") != "initial"
        or started.get("continuation_of_attempt_id") is not None
        or terminal.get("continuation_of_attempt_id") is not None
        or started.get("hypothesis_id") is not None
        or started_row["hypothesis_id"] is not None
        or started.get("hypothesis_digest") is not None
        or started.get("patch_digest") is not None
        or terminal.get("hypothesis_id") != hypothesis_id
        or terminal_row["hypothesis_id"] != hypothesis_id
        or started_row["event_id"] == terminal_row["event_id"]
        or not str(terminal.get("hypothesis_digest") or "")
        or terminal.get("patch_digest") is not None
        or started.get("anchors") != terminal.get("anchors")
        or (started.get("prompt_call") or {}).get("context_digest")
        != (terminal.get("prompt_call") or {}).get("context_digest")
        or (started.get("prompt_call") or {}).get("prompt_hash")
        != (terminal.get("prompt_call") or {}).get("prompt_hash")
    ):
        raise RuntimeError("hypothesis parent transition identity conflicts")
    return {
        "attempt_id": attempt_id,
        "hypothesis_digest": terminal["hypothesis_digest"],
        "anchors": terminal["anchors"],
    }


__all__ = [
    "RESEARCH_REJECTION_COMPLETION_SCHEMA",
    "ResearchRejectionCompletionIntent",
    "ResearchRejectionCompletionStore",
]
