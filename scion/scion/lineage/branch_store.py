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
                 target_file, parent_hypothesis_id, suggested_weight, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    hyp.created_at.isoformat(),
                ),
            )
