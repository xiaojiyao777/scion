"""BranchStore + HypothesisStore — Branch/Hypothesis state persistence."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import List, Optional, TYPE_CHECKING

from scion.core.models import Branch, BranchState, HypothesisRecord

if TYPE_CHECKING:
    from scion.lineage.registry import LineageRegistry


class BranchStore:
    def __init__(self, registry: "LineageRegistry") -> None:
        self.registry = registry

    def save(self, branch: Branch) -> None:
        with sqlite3.connect(self.registry.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO branches
                (branch_id, state, base_champion_id, base_champion_hash,
                 current_code_hash, last_clean_code_hash, retry_count,
                 failure_codes, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    branch.branch_id,
                    branch.state.value,
                    branch.base_champion_id,
                    branch.base_champion_hash,
                    branch.current_code_hash,
                    branch.last_clean_code_hash,
                    branch.retry_count,
                    json.dumps(branch.failure_codes),
                    branch.created_at.isoformat(),
                    branch.updated_at.isoformat(),
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
        """Return all branches not in terminal states (PROMOTED, ABANDONED, STALE)."""
        terminal = ("promoted", "abandoned")
        with sqlite3.connect(self.registry.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                f"SELECT * FROM branches WHERE state NOT IN ({','.join('?'*len(terminal))})",
                terminal,
            ).fetchall()
            return [self._row_to_branch(r) for r in rows]

    @staticmethod
    def _row_to_branch(row: sqlite3.Row) -> Branch:
        d = dict(row)
        return Branch(
            branch_id=d["branch_id"],
            state=BranchState(d["state"]),
            base_champion_id=d["base_champion_id"],
            base_champion_hash=d["base_champion_hash"],
            current_code_hash=d.get("current_code_hash"),
            last_clean_code_hash=d.get("last_clean_code_hash"),
            retry_count=d.get("retry_count", 0),
            failure_codes=json.loads(d["failure_codes"]) if d.get("failure_codes") else [],
            created_at=datetime.fromisoformat(d["created_at"]),
            updated_at=datetime.fromisoformat(d["updated_at"]),
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
                 family_id, family_source, taxonomy_version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            rows = conn.execute(
                "SELECT * FROM hypotheses WHERE status = ? ORDER BY created_at ASC",
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
                "hypothesis_text": (h.hypothesis_text or "")[:200],
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
        )
