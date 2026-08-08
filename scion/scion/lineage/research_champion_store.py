"""Append-only champion values for fresh V3 research campaigns."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Optional

from scion.core.models import ChampionState, OperatorConfig


class ChampionStore:
    """Persist plain champion state without authority or legacy migration."""

    _COLUMNS = {
        "version",
        "weight_revision",
        "operator_pool_json",
        "solver_config_hash",
        "code_snapshot_path",
        "code_snapshot_hash",
        "promotion_experiment_id",
        "promotion_dossier_ref",
        "promoted_at",
    }

    def __init__(self, db_path: str | Path, snapshot_dir: str | Path) -> None:
        self._snapshot_dir = Path(snapshot_dir)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.row_factory = sqlite3.Row
        self._ensure_fresh_schema()

    def _ensure_fresh_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS champions (
                version                 INTEGER NOT NULL,
                weight_revision         INTEGER NOT NULL DEFAULT 0,
                operator_pool_json      TEXT NOT NULL,
                solver_config_hash      TEXT NOT NULL,
                code_snapshot_path      TEXT NOT NULL,
                code_snapshot_hash      TEXT NOT NULL,
                promotion_experiment_id TEXT,
                promotion_dossier_ref   TEXT,
                promoted_at             TEXT,
                PRIMARY KEY (version, weight_revision)
            )
            """
        )
        rows = self._conn.execute("PRAGMA table_info(champions)").fetchall()
        columns = {str(row["name"]): row for row in rows}
        if set(columns) != self._COLUMNS:
            raise RuntimeError(
                "existing champions table is not the fresh V3 research schema"
            )
        if columns["version"]["pk"] != 1 or columns["weight_revision"]["pk"] != 2:
            raise RuntimeError(
                "existing champions table lacks the V3 composite primary key"
            )
        self._conn.commit()

    def promote(self, champion: ChampionState) -> None:
        pool = {
            name: {
                "name": config.name,
                "file_path": config.file_path,
                "category": config.category,
                "weight": config.weight,
                "class_name": config.class_name,
            }
            for name, config in champion.operator_pool.items()
        }
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO champions (
                    version, weight_revision, operator_pool_json,
                    solver_config_hash, code_snapshot_path, code_snapshot_hash,
                    promotion_experiment_id, promotion_dossier_ref, promoted_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    champion.version,
                    champion.weight_revision,
                    json.dumps(pool, sort_keys=True),
                    champion.solver_config_hash,
                    champion.code_snapshot_path,
                    champion.code_snapshot_hash,
                    champion.promotion_experiment_id,
                    champion.promotion_dossier_ref,
                    champion.promoted_at,
                ),
            )

    def get_current(self) -> Optional[ChampionState]:
        row = self._conn.execute(
            "SELECT * FROM champions "
            "ORDER BY version DESC, weight_revision DESC LIMIT 1"
        ).fetchone()
        return self._decode(row)

    def get_by_version(self, version: int) -> Optional[ChampionState]:
        row = self._conn.execute(
            "SELECT * FROM champions WHERE version = ? "
            "ORDER BY weight_revision DESC LIMIT 1",
            (version,),
        ).fetchone()
        return self._decode(row)

    def get_by_version_revision(
        self,
        version: int,
        weight_revision: int,
    ) -> Optional[ChampionState]:
        row = self._conn.execute(
            "SELECT * FROM champions WHERE version = ? AND weight_revision = ?",
            (version, weight_revision),
        ).fetchone()
        return self._decode(row)

    def get_history(self) -> list[ChampionState]:
        rows = self._conn.execute(
            "SELECT * FROM champions ORDER BY version, weight_revision"
        ).fetchall()
        return [value for row in rows if (value := self._decode(row)) is not None]

    def snapshot_path_for(self, version: int) -> Path:
        return self._snapshot_dir / f"v{version}"

    @staticmethod
    def _decode(row: sqlite3.Row | None) -> Optional[ChampionState]:
        if row is None:
            return None
        value = dict(row)
        pool = json.loads(value["operator_pool_json"])
        return ChampionState(
            version=value["version"],
            weight_revision=value["weight_revision"],
            operator_pool={
                name: OperatorConfig(**config) for name, config in pool.items()
            },
            solver_config_hash=value["solver_config_hash"],
            code_snapshot_path=value["code_snapshot_path"],
            code_snapshot_hash=value["code_snapshot_hash"],
            promotion_experiment_id=value["promotion_experiment_id"],
            promotion_dossier_ref=value["promotion_dossier_ref"],
            promoted_at=value["promoted_at"],
        )

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "ChampionStore":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


__all__ = ["ChampionStore"]
