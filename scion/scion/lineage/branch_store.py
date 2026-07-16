"""BranchStore + HypothesisStore — Branch/Hypothesis state persistence."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import List, Optional, TYPE_CHECKING

from scion.core.models import (
    Branch,
    BranchState,
    HypothesisRecord,
)

if TYPE_CHECKING:
    from scion.lineage.registry import LineageRegistry

_REJECTED_STATUS_ALIASES = (
    "rejected",
    "contract_failed",
    "smoke_failed",
    "screening_no_effect",
)


def _json_mapping(raw: object) -> dict:
    if not raw:
        return {}
    try:
        value = json.loads(str(raw))
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _strict_json_mapping(raw: object) -> dict:
    """Decode a durable mapping without hiding non-empty corruption."""

    if not raw:
        return {}
    try:
        value = json.loads(str(raw))
    except (TypeError, ValueError) as exc:
        raise ValueError("branch evidence summary JSON is invalid") from exc
    if not isinstance(value, dict):
        raise ValueError("branch evidence summary JSON is not a mapping")
    return value


class BranchStore:
    def __init__(self, registry: "LineageRegistry") -> None:
        self.registry = registry

    def save(self, branch: Branch) -> None:
        with sqlite3.connect(self.registry.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO branches
                (branch_id, state, base_champion_id, base_champion_hash,
                 lineage_id, current_code_hash, last_clean_code_hash,
                 screening_expand_count, validation_expand_count,
                 failure_codes, created_at, updated_at, direction,
                 weight_revision, branch_code_status,
                 branch_evidence_summary_json,
                 infra_block_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    branch.branch_id,
                    branch.state.value,
                    branch.base_champion_id,
                    branch.base_champion_hash,
                    branch.lineage_id or branch.branch_id,
                    branch.current_code_hash,
                    branch.last_clean_code_hash,
                    branch.screening_expand_count,
                    branch.validation_expand_count,
                    json.dumps(branch.failure_codes),
                    branch.created_at.isoformat(),
                    branch.updated_at.isoformat(),
                    branch.direction,
                    branch.weight_revision,
                    branch.branch_code_status,
                    json.dumps(dict(branch.branch_evidence_summary or {})),
                    branch.infra_block_count,
                ),
            )

    def load(self, branch_id: str) -> Optional[Branch]:
        with sqlite3.connect(self.registry.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM branches WHERE branch_id = ?", (branch_id,)
            ).fetchone()
            if not row:
                return None
            return self._row_to_branch(row)

    def load_all_active(self) -> List[Branch]:
        """Return branches that remain in the active scheduling pool."""
        terminal = ("promoted", "abandoned", "parked_lineage")
        terminal_placeholders = ",".join("?" * len(terminal))
        with sqlite3.connect(self.registry.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                (
                    "SELECT * FROM branches "
                    f"WHERE state NOT IN ({terminal_placeholders})"
                ),
                terminal,
            ).fetchall()
            return [self._row_to_branch(r) for r in rows]

    def load_all(self) -> List[Branch]:
        """Return every campaign branch in stable creation order.

        Proposal context needs the screening records owned by terminal branches
        as well as active ones.  This is intentionally separate from
        ``load_all_active`` so scheduling semantics remain unchanged.
        """

        with sqlite3.connect(self.registry.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM branches ORDER BY created_at ASC, branch_id ASC"
            ).fetchall()
            return [
                self._row_to_branch(r, strict_evidence_summary=True)
                for r in rows
            ]

    @staticmethod
    def _row_to_branch(
        row: sqlite3.Row,
        *,
        strict_evidence_summary: bool = False,
    ) -> Branch:
        d = dict(row)
        raw_evidence_summary = d.get("branch_evidence_summary_json")
        return Branch(
            branch_id=d["branch_id"],
            state=BranchState(d["state"]),
            base_champion_id=d["base_champion_id"],
            base_champion_hash=d["base_champion_hash"],
            lineage_id=d.get("lineage_id") or d["branch_id"],
            current_code_hash=d.get("current_code_hash"),
            last_clean_code_hash=d.get("last_clean_code_hash"),
            screening_expand_count=d.get("screening_expand_count") or 0,
            validation_expand_count=d.get("validation_expand_count") or 0,
            failure_codes=json.loads(d["failure_codes"]) if d.get("failure_codes") else [],
            created_at=datetime.fromisoformat(d["created_at"]),
            updated_at=datetime.fromisoformat(d["updated_at"]),
            direction=d.get("direction"),
            weight_revision=d.get("weight_revision") or 0,
            branch_code_status=d.get("branch_code_status") or "clean",
            branch_evidence_summary=(
                _strict_json_mapping(raw_evidence_summary)
                if strict_evidence_summary
                else _json_mapping(raw_evidence_summary)
            ),
            infra_block_count=d.get("infra_block_count") or 0,
        )


class HypothesisStore:
    def __init__(self, registry: "LineageRegistry") -> None:
        self.registry = registry

    def save(self, hyp: HypothesisRecord) -> None:
        with sqlite3.connect(self.registry.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO hypotheses
                (hypothesis_id, branch_id, change_locus, action, status,
                 target_file, parent_hypothesis_id, suggested_weight,
                 hypothesis_text, created_at, base_champion_version,
                 family_id, family_source, taxonomy_version,
                 predicted_direction, proposal_digest)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    hyp.hypothesis_id,
                    hyp.branch_id,
                    hyp.change_locus,
                    hyp.action,
                    hyp.status,
                    hyp.target_file,
                    hyp.parent_hypothesis_id,
                    hyp.suggested_weight,
                    hyp.hypothesis_text,
                    hyp.created_at.isoformat(),
                    hyp.base_champion_version,
                    hyp.family_id,
                    hyp.family_source,
                    hyp.taxonomy_version,
                    hyp.predicted_direction,
                    hyp.proposal_digest,
                ),
            )

    def mark_status(self, hypothesis_id: str, status: str) -> None:
        """Update the status of a hypothesis record in the database."""
        with sqlite3.connect(self.registry.db_path) as conn:
            conn.execute(
                "UPDATE hypotheses SET status = ? WHERE hypothesis_id = ?",
                (status, hypothesis_id),
            )

    def get_by_status(self, status: str) -> List[HypothesisRecord]:
        """Return all hypotheses with the given status."""
        with sqlite3.connect(self.registry.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if status == "rejected":
                placeholders = ",".join("?" for _ in _REJECTED_STATUS_ALIASES)
                rows = conn.execute(
                    "SELECT * FROM hypotheses "
                    f"WHERE status IN ({placeholders}) "
                    "ORDER BY created_at ASC",
                    _REJECTED_STATUS_ALIASES,
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM hypotheses WHERE status = ? "
                    "ORDER BY created_at ASC",
                    (status,),
                ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def get_by_branch(self, branch_id: str) -> List[HypothesisRecord]:
        """Return all hypotheses for a branch, ordered by creation time."""
        with sqlite3.connect(self.registry.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM hypotheses WHERE branch_id = ? ORDER BY created_at ASC",
                (branch_id,),
            ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def get_one(self, hypothesis_id: str) -> Optional[HypothesisRecord]:
        """Return a single hypothesis record by ID, or None."""
        with sqlite3.connect(self.registry.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM hypotheses WHERE hypothesis_id = ?",
                (hypothesis_id,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_record(row)

    def get_structural_summary(
        self,
        branch_id: str,
        *,
        include_global_blacklist: bool = True,
    ) -> dict:
        """Return a structured dict summarising hypotheses for LLM context.

        Includes:
          - branch_hypotheses: all records for this branch (all statuses)
          - blacklisted: globally blacklisted hypotheses (if include_global_blacklist)
        Blacklist scope_tags / evidence_count / expiry_round are not implemented (v0.1).
        """
        branch_hyps = self.get_by_branch(branch_id)
        blacklisted = self.get_by_status("blacklisted") if include_global_blacklist else []

        def _fmt(h: HypothesisRecord) -> dict:
            return {
                "hypothesis_id": h.hypothesis_id,
                "action": h.action,
                "change_locus": h.change_locus,
                "target_file": h.target_file,
                "status": h.status,
                "hypothesis_text": h.hypothesis_text or "",
            }

        return {
            "branch_hypotheses": [_fmt(h) for h in branch_hyps],
            "blacklisted": [_fmt(h) for h in blacklisted],
        }

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> HypothesisRecord:
        d = dict(row)
        return HypothesisRecord(
            hypothesis_id=d["hypothesis_id"],
            branch_id=d.get("branch_id") or "",
            change_locus=d.get("change_locus") or "",
            action=d.get("action") or "modify",
            status=d.get("status") or "active",
            target_file=d.get("target_file"),
            parent_hypothesis_id=d.get("parent_hypothesis_id"),
            suggested_weight=d.get("suggested_weight"),
            hypothesis_text=d.get("hypothesis_text"),
            family_id=d.get("family_id"),
            family_source=d.get("family_source"),
            taxonomy_version=d.get("taxonomy_version"),
            created_at=datetime.fromisoformat(d["created_at"]) if d.get("created_at") else datetime.now(),
            base_champion_version=d.get("base_champion_version") or 0,
            predicted_direction=d.get("predicted_direction") or "exploratory",
            proposal_digest=d.get("proposal_digest"),
        )

    # ---------------------------------------------------------------
    # W5: Lineage-derived family views
    # ---------------------------------------------------------------

    def get_family_stats(self) -> List[dict]:
        """Derive family statistics from lineage (persist facts, rebuild views).

        Returns list of dicts with: family_id, total_attempts, statuses,
        promoted_count, rejected_count, active_count.
        """
        with sqlite3.connect(self.registry.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT
                    family_id,
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'promoted' THEN 1 ELSE 0 END) as promoted,
                    SUM(CASE WHEN status IN ('rejected', 'abandoned', 'blacklisted', 'contract_failed', 'smoke_failed', 'screening_no_effect') THEN 1 ELSE 0 END) as rejected,
                    SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active
                FROM hypotheses
                WHERE family_id IS NOT NULL
                GROUP BY family_id
                ORDER BY total DESC
            """).fetchall()
        return [dict(r) for r in rows]

    def get_failure_summary(self) -> List[dict]:
        """Derive failure summary from hypothesis statuses in lineage.

        Returns list of dicts with: status, count.
        """
        with sqlite3.connect(self.registry.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT status, COUNT(*) as count
                FROM hypotheses
                GROUP BY status
                ORDER BY count DESC
            """).fetchall()
        return [dict(r) for r in rows]
