"""ChampionStore — champion 状态持久化。

保存/加载/历史查询 + 代码快照路径管理。
所有写操作为 INSERT only（append-only 原则）。
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from scion.core.models import ChampionState, OperatorConfig


class ChampionStore:
    """Champion 状态持久化层。

    使用 champions 表（SQLite），每次晋升 INSERT 一条记录。
    get_current() 返回 version 最大的记录。

    Args:
        db_path: SQLite 数据库文件路径（与 LineageRegistry 共享同一个 db）。
        snapshot_dir: champion 代码快照目录的根路径。
    """

    def __init__(self, db_path: str | Path, snapshot_dir: str | Path) -> None:
        self._db_path = str(db_path)
        self._snapshot_dir = Path(snapshot_dir)
        self._conn = self._connect()
        self._ensure_table()

    def _connect(self) -> sqlite3.Connection:
        """建立 SQLite 连接，启用 WAL 模式。"""
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_table(self) -> None:
        """确保 champions 表存在（幂等）。"""
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS champions (
                version                 INTEGER PRIMARY KEY,
                operator_pool_json      TEXT NOT NULL,
                solver_config_hash      TEXT NOT NULL,
                code_snapshot_path      TEXT NOT NULL,
                code_snapshot_hash      TEXT NOT NULL,
                promotion_experiment_id TEXT,
                promoted_at             TEXT
            )
        """)
        self._conn.commit()

    # ──────────────────────────────────────────────────────────────────────
    # 写入接口（INSERT only）
    # ──────────────────────────────────────────────────────────────────────

    def promote(self, new_champion: ChampionState) -> None:
        """保存新 champion（INSERT only）。

        Args:
            new_champion: 新的 ChampionState 对象。

        Raises:
            sqlite3.IntegrityError: version 重复时抛出。
        """
        operator_pool_json = json.dumps(
            {
                name: {
                    "name": cfg.name,
                    "file_path": cfg.file_path,
                    "category": cfg.category,
                    "weight": cfg.weight,
                    "class_name": cfg.class_name,
                }
                for name, cfg in new_champion.operator_pool.items()
            }
        )
        sql = """
            INSERT INTO champions (
                version, operator_pool_json, solver_config_hash,
                code_snapshot_path, code_snapshot_hash,
                promotion_experiment_id, promoted_at
            ) VALUES (
                :version, :operator_pool_json, :solver_config_hash,
                :code_snapshot_path, :code_snapshot_hash,
                :promotion_experiment_id, :promoted_at
            )
        """
        params = {
            "version": new_champion.version,
            "operator_pool_json": operator_pool_json,
            "solver_config_hash": new_champion.solver_config_hash,
            "code_snapshot_path": new_champion.code_snapshot_path,
            "code_snapshot_hash": new_champion.code_snapshot_hash,
            "promotion_experiment_id": new_champion.promotion_experiment_id,
            "promoted_at": new_champion.promoted_at,
        }
        with self._conn:
            self._conn.execute(sql, params)

    # ──────────────────────────────────────────────────────────────────────
    # 查询接口
    # ──────────────────────────────────────────────────────────────────────

    def get_current(self) -> Optional[ChampionState]:
        """返回当前 champion（version 最大的记录）。

        Returns:
            ChampionState 对象；如果没有任何 champion 则返回 None。
        """
        row = self._conn.execute(
            "SELECT * FROM champions ORDER BY version DESC LIMIT 1"
        ).fetchone()
        return self._row_to_champion(row) if row else None

    def get_by_version(self, version: int) -> Optional[ChampionState]:
        """按版本号获取 champion。

        Args:
            version: champion 版本号。

        Returns:
            ChampionState 对象；不存在时返回 None。
        """
        row = self._conn.execute(
            "SELECT * FROM champions WHERE version = ?", (version,)
        ).fetchone()
        return self._row_to_champion(row) if row else None

    def get_history(self) -> list[ChampionState]:
        """返回所有 champion 历史记录，按版本升序排列。

        Returns:
            ChampionState 列表。
        """
        rows = self._conn.execute(
            "SELECT * FROM champions ORDER BY version ASC"
        ).fetchall()
        return [self._row_to_champion(r) for r in rows]

    def snapshot_path_for(self, version: int) -> Path:
        """返回指定版本 champion 的代码快照目录路径（不检查是否存在）。

        Args:
            version: champion 版本号。

        Returns:
            快照目录路径。
        """
        return self._snapshot_dir / f"v{version}"

    # ──────────────────────────────────────────────────────────────────────
    # 内部辅助
    # ──────────────────────────────────────────────────────────────────────

    @staticmethod
    def _row_to_champion(row: sqlite3.Row) -> ChampionState:
        """将数据库行转换为 ChampionState 对象。"""
        d = dict(row)
        # 还原 operator_pool JSON
        pool_raw: dict = json.loads(d["operator_pool_json"])
        operator_pool = {
            name: OperatorConfig(
                name=cfg["name"],
                file_path=cfg["file_path"],
                category=cfg["category"],
                weight=cfg["weight"],
                class_name=cfg["class_name"],
            )
            for name, cfg in pool_raw.items()
        }
        return ChampionState(
            version=d["version"],
            operator_pool=operator_pool,
            solver_config_hash=d["solver_config_hash"],
            code_snapshot_path=d["code_snapshot_path"],
            code_snapshot_hash=d["code_snapshot_hash"],
            promotion_experiment_id=d.get("promotion_experiment_id"),
            promoted_at=d.get("promoted_at"),
        )

    def close(self) -> None:
        """关闭数据库连接。"""
        self._conn.close()

    def __enter__(self) -> "ChampionStore":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
