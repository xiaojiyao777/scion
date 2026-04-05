"""HypothesisStore — 假设存储、状态管理与 blacklist 机制。

Features:
- 保存/查询 HypothesisRecord
- 标记假设状态（active → weakened / rejected / promoted）
- Blacklist 机制：scope_tags + evidence_count + expiry_round
- 过期机制：blacklist_expiry_round 到期后自动解除
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Literal, Optional

from scion.core.models import HypothesisRecord


class HypothesisStore:
    """假设记录持久化层，含 blacklist 过期机制。

    Args:
        db_path: SQLite 数据库文件路径。
    """

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)
        self._conn = self._connect()
        self._ensure_table()

    def _connect(self) -> sqlite3.Connection:
        """建立 SQLite 连接，启用 WAL 模式。"""
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_table(self) -> None:
        """确保 hypotheses 表存在（幂等）。"""
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS hypotheses (
                hypothesis_id           TEXT PRIMARY KEY,
                branch_id               TEXT NOT NULL,
                parent_hypothesis_id    TEXT,
                change_locus            TEXT NOT NULL,
                action                  TEXT NOT NULL,
                target_file             TEXT,
                touched_symbols         TEXT,
                predicted_direction     TEXT,
                target_weakness         TEXT,
                rationale_text          TEXT,
                status                  TEXT NOT NULL,
                suggested_weight        REAL,
                blacklist_scope_tags    TEXT,
                blacklist_evidence_count INTEGER,
                blacklist_expiry_round  INTEGER,
                created_at              TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_hyp_branch
                ON hypotheses(branch_id);
            CREATE INDEX IF NOT EXISTS idx_hyp_status
                ON hypotheses(status);
            CREATE INDEX IF NOT EXISTS idx_hyp_blacklist
                ON hypotheses(blacklist_expiry_round)
                WHERE blacklist_expiry_round IS NOT NULL;
        """)
        self._conn.commit()

    # ──────────────────────────────────────────────────────────────────────
    # 写入接口
    # ──────────────────────────────────────────────────────────────────────

    def save(self, record: HypothesisRecord) -> None:
        """保存假设记录（INSERT OR REPLACE）。

        Args:
            record: 要持久化的 HypothesisRecord 对象。
        """
        sql = """
            INSERT OR REPLACE INTO hypotheses (
                hypothesis_id, branch_id, parent_hypothesis_id,
                change_locus, action, target_file,
                touched_symbols, predicted_direction, target_weakness,
                rationale_text, status, suggested_weight,
                blacklist_scope_tags, blacklist_evidence_count,
                blacklist_expiry_round, created_at
            ) VALUES (
                :hypothesis_id, :branch_id, :parent_hypothesis_id,
                :change_locus, :action, :target_file,
                :touched_symbols, :predicted_direction, :target_weakness,
                :rationale_text, :status, :suggested_weight,
                :blacklist_scope_tags, :blacklist_evidence_count,
                :blacklist_expiry_round, :created_at
            )
        """
        params = {
            "hypothesis_id": record.hypothesis_id,
            "branch_id": record.branch_id,
            "parent_hypothesis_id": record.parent_hypothesis_id,
            "change_locus": record.change_locus,
            "action": record.action,
            "target_file": record.target_file,
            "touched_symbols": json.dumps(record.touched_symbols),
            "predicted_direction": record.predicted_direction,
            "target_weakness": record.target_weakness,
            "rationale_text": record.rationale_text,
            "status": record.status,
            "suggested_weight": record.suggested_weight,
            "blacklist_scope_tags": json.dumps(record.blacklist_scope_tags)
            if record.blacklist_scope_tags is not None
            else None,
            "blacklist_evidence_count": record.blacklist_evidence_count,
            "blacklist_expiry_round": record.blacklist_expiry_round,
            "created_at": record.created_at,
        }
        with self._conn:
            self._conn.execute(sql, params)

    def mark_status(
        self,
        hypothesis_id: str,
        status: Literal["active", "weakened", "rejected", "promoted"],
    ) -> None:
        """标记假设状态（UPDATE status 字段）。

        Args:
            hypothesis_id: 假设 UUID。
            status: 新状态值。

        Raises:
            ValueError: 假设 ID 不存在时抛出。
        """
        result = self._conn.execute(
            "SELECT hypothesis_id FROM hypotheses WHERE hypothesis_id = ?",
            (hypothesis_id,),
        ).fetchone()
        if result is None:
            raise ValueError(f"假设 ID 不存在: {hypothesis_id}")
        with self._conn:
            self._conn.execute(
                "UPDATE hypotheses SET status = ? WHERE hypothesis_id = ?",
                (status, hypothesis_id),
            )

    def add_to_blacklist(
        self,
        hypothesis_id: str,
        scope_tags: list[str],
        evidence_count: int,
        expiry_round: int,
    ) -> None:
        """将假设加入 blacklist。

        Args:
            hypothesis_id: 假设 UUID。
            scope_tags: blacklist 适用的范围标签。
            evidence_count: 支持 blacklist 的证据数量。
            expiry_round: blacklist 过期轮次（到期后 expire_blacklist 可解除）。
        """
        with self._conn:
            self._conn.execute(
                """
                UPDATE hypotheses SET
                    status = 'rejected',
                    blacklist_scope_tags = ?,
                    blacklist_evidence_count = ?,
                    blacklist_expiry_round = ?
                WHERE hypothesis_id = ?
                """,
                (
                    json.dumps(scope_tags),
                    evidence_count,
                    expiry_round,
                    hypothesis_id,
                ),
            )

    def expire_blacklist(self, current_round: int) -> int:
        """解除已过期的 blacklist 条目。

        将 blacklist_expiry_round <= current_round 的记录从 'rejected'
        改回 'weakened'（允许重新探索，但保留失败记忆）。

        Args:
            current_round: 当前 campaign 轮次。

        Returns:
            解除的条目数量。
        """
        with self._conn:
            cursor = self._conn.execute(
                """
                UPDATE hypotheses SET
                    status = 'weakened',
                    blacklist_scope_tags = NULL,
                    blacklist_evidence_count = NULL,
                    blacklist_expiry_round = NULL
                WHERE status = 'rejected'
                  AND blacklist_expiry_round IS NOT NULL
                  AND blacklist_expiry_round <= ?
                """,
                (current_round,),
            )
            return cursor.rowcount

    # ──────────────────────────────────────────────────────────────────────
    # 查询接口
    # ──────────────────────────────────────────────────────────────────────

    def get(self, hypothesis_id: str) -> Optional[HypothesisRecord]:
        """按 hypothesis_id 获取单条记录。

        Args:
            hypothesis_id: 假设 UUID。

        Returns:
            HypothesisRecord 对象；不存在时返回 None。
        """
        row = self._conn.execute(
            "SELECT * FROM hypotheses WHERE hypothesis_id = ?", (hypothesis_id,)
        ).fetchone()
        return self._row_to_record(row) if row else None

    def get_by_branch(self, branch_id: str) -> list[HypothesisRecord]:
        """返回指定分支的所有假设，按创建时间排序。

        Args:
            branch_id: 分支 UUID。

        Returns:
            假设记录列表。
        """
        rows = self._conn.execute(
            "SELECT * FROM hypotheses WHERE branch_id = ? ORDER BY created_at ASC",
            (branch_id,),
        ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def get_structural_summary(
        self,
        branch_id: Optional[str] = None,
        include_global_blacklist: bool = False,
    ) -> list[HypothesisRecord]:
        """获取假设的结构化摘要（用于 LLM 上下文构建）。

        仅返回非 tainted 的结构化字段（排除 rationale_text、target_weakness 等）。
        实际上返回完整 record，由调用方决定用哪些字段。

        Args:
            branch_id: 若指定，只返回该分支的假设；None 则返回所有非 blacklisted 假设。
            include_global_blacklist: 是否包含全局 blacklisted 假设（状态 = 'rejected'）。

        Returns:
            假设记录列表。
        """
        conditions = []
        params: list = []

        if branch_id:
            conditions.append("branch_id = ?")
            params.append(branch_id)

        if not include_global_blacklist:
            # 排除已永久 blacklisted 的（无 expiry_round 的 rejected）
            conditions.append(
                "(status != 'rejected' OR blacklist_expiry_round IS NOT NULL)"
            )

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        sql = f"SELECT * FROM hypotheses WHERE {where_clause} ORDER BY created_at ASC"
        rows = self._conn.execute(sql, params).fetchall()
        return [self._row_to_record(r) for r in rows]

    def get_blacklisted(self) -> list[HypothesisRecord]:
        """返回所有当前处于 blacklist 中的假设（status='rejected' 且有 blacklist 信息）。

        Returns:
            Blacklisted 假设记录列表。
        """
        rows = self._conn.execute(
            """
            SELECT * FROM hypotheses
            WHERE status = 'rejected'
              AND blacklist_scope_tags IS NOT NULL
            ORDER BY created_at ASC
            """
        ).fetchall()
        return [self._row_to_record(r) for r in rows]

    # ──────────────────────────────────────────────────────────────────────
    # 内部辅助
    # ──────────────────────────────────────────────────────────────────────

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> HypothesisRecord:
        """将数据库行转换为 HypothesisRecord 对象。"""
        d = dict(row)
        d["touched_symbols"] = (
            json.loads(d["touched_symbols"]) if d.get("touched_symbols") else []
        )
        d["blacklist_scope_tags"] = (
            json.loads(d["blacklist_scope_tags"])
            if d.get("blacklist_scope_tags")
            else None
        )
        # evidence_refs 不存储在该表，由 ExperimentEvent 表关联
        d["evidence_refs"] = []
        return HypothesisRecord(
            hypothesis_id=d["hypothesis_id"],
            branch_id=d["branch_id"],
            parent_hypothesis_id=d.get("parent_hypothesis_id"),
            change_locus=d["change_locus"],
            action=d["action"],
            status=d["status"],
            created_at=d["created_at"],
            target_file=d.get("target_file"),
            touched_symbols=d["touched_symbols"],
            predicted_direction=d.get("predicted_direction"),
            target_weakness=d.get("target_weakness"),
            rationale_text=d.get("rationale_text"),
            evidence_refs=d["evidence_refs"],
            suggested_weight=d.get("suggested_weight"),
            blacklist_scope_tags=d["blacklist_scope_tags"],
            blacklist_evidence_count=d.get("blacklist_evidence_count"),
            blacklist_expiry_round=d.get("blacklist_expiry_round"),
        )

    def close(self) -> None:
        """关闭数据库连接。"""
        self._conn.close()

    def __enter__(self) -> "HypothesisStore":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
