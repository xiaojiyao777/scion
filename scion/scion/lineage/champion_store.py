"""ChampionStore — champion 状态持久化。

保存/加载/历史查询 + 代码快照路径管理。
所有写操作为 INSERT only（append-only 原则）。
"""

from __future__ import annotations

import json
import hashlib
import math
import sqlite3
import weakref
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Optional

from scion.core.models import ChampionState, OperatorConfig
from scion.lineage import sqlite_connection as _sqlite
from scion.lineage import owner_transaction as _owner
from scion.lineage.durable_owner import (
    DurableOwnerIntegrityError,
    RevisionedBranchRecord,
)

_CHAMPION_COLUMNS: Final[tuple[str, ...]] = (
    "version",
    "weight_revision",
    "operator_pool_json",
    "solver_config_hash",
    "code_snapshot_path",
    "code_snapshot_hash",
    "promotion_experiment_id",
    "promotion_dossier_ref",
    "promoted_at",
)

_CURRENT_CHAMPION_SELECT_SQL: Final[str] = """
SELECT version,
       weight_revision,
       operator_pool_json,
       solver_config_hash,
       code_snapshot_path,
       code_snapshot_hash,
       promotion_experiment_id,
       promotion_dossier_ref,
       promoted_at
FROM champions
ORDER BY version DESC, weight_revision DESC
LIMIT 1
"""

_EXACT_CHAMPION_SELECT_SQL: Final[str] = """
SELECT version,
       weight_revision,
       operator_pool_json,
       solver_config_hash,
       code_snapshot_path,
       code_snapshot_hash,
       promotion_experiment_id,
       promotion_dossier_ref,
       promoted_at
FROM champions
WHERE version = ? AND weight_revision = ?
"""

_OPERATOR_CONFIG_KEYS: Final[frozenset[str]] = frozenset(
    {"name", "file_path", "category", "weight", "class_name"}
)


def _canonical_json_bytes(value: object, *, field: str) -> bytes:
    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, RecursionError, UnicodeEncodeError) as exc:
        raise DurableOwnerIntegrityError(f"{field} is not canonical JSON") from exc
    return encoded


def _duplicate_rejecting_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DurableOwnerIntegrityError(
                "Champion operator JSON contains a duplicate object key"
            )
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise DurableOwnerIntegrityError(
        f"Champion operator JSON contains non-finite constant {value!r}"
    )


def _required_text(value: object, *, field: str) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise DurableOwnerIntegrityError(f"{field} must be a non-empty exact string")
    return value


def _optional_text(value: object, *, field: str) -> str | None:
    if value is not None and type(value) is not str:
        raise DurableOwnerIntegrityError(f"{field} must be an exact string or null")
    return value


def _nonnegative_sqlite_integer(value: object, *, field: str) -> int:
    if type(value) is not int or value < 0:
        raise DurableOwnerIntegrityError(
            f"{field} must be a non-negative SQLite integer"
        )
    return value


def _decode_operator_pool_json(raw_json: object) -> dict[str, OperatorConfig]:
    if type(raw_json) is not str:
        raise DurableOwnerIntegrityError("Champion operator pool must be JSON text")
    try:
        decoded = json.loads(
            raw_json,
            object_pairs_hook=_duplicate_rejecting_object,
            parse_constant=_reject_json_constant,
        )
    except DurableOwnerIntegrityError:
        raise
    except (TypeError, ValueError, RecursionError) as exc:
        raise DurableOwnerIntegrityError(
            "Champion operator pool contains malformed JSON"
        ) from exc
    if type(decoded) is not dict:
        raise DurableOwnerIntegrityError(
            "Champion operator pool JSON must contain an object"
        )

    result: dict[str, OperatorConfig] = {}
    for operator_key, raw_config in decoded.items():
        key = _required_text(operator_key, field="Champion operator key")
        if type(raw_config) is not dict:
            raise DurableOwnerIntegrityError(
                f"Champion operator {key!r} config must be an object"
            )
        if frozenset(raw_config) != _OPERATOR_CONFIG_KEYS:
            raise DurableOwnerIntegrityError(
                f"Champion operator {key!r} config has incomplete or unexpected fields"
            )
        weight = raw_config["weight"]
        if isinstance(weight, bool) or not isinstance(weight, (int, float)):
            raise DurableOwnerIntegrityError(
                f"Champion operator {key!r} weight must be a finite number"
            )
        try:
            normalized_weight = float(weight)
        except (OverflowError, ValueError) as exc:
            raise DurableOwnerIntegrityError(
                f"Champion operator {key!r} weight must be a finite number"
            ) from exc
        if not math.isfinite(normalized_weight):
            raise DurableOwnerIntegrityError(
                f"Champion operator {key!r} weight must be finite"
            )
        result[key] = OperatorConfig(
            name=_required_text(
                raw_config["name"],
                field=f"Champion operator {key!r} name",
            ),
            file_path=_required_text(
                raw_config["file_path"],
                field=f"Champion operator {key!r} file path",
            ),
            category=_required_text(
                raw_config["category"],
                field=f"Champion operator {key!r} category",
            ),
            weight=0.0 if normalized_weight == 0.0 else normalized_weight,
            class_name=_required_text(
                raw_config["class_name"],
                field=f"Champion operator {key!r} class name",
            ),
        )
    return result


def _champion_storage_payload(values: tuple[object, ...]) -> dict[str, object]:
    if len(values) != len(_CHAMPION_COLUMNS):
        raise DurableOwnerIntegrityError(
            "Champion row does not contain the complete frozen storage schema"
        )
    (
        version,
        weight_revision,
        operator_pool_json,
        solver_config_hash,
        code_snapshot_path,
        code_snapshot_hash,
        promotion_experiment_id,
        promotion_dossier_ref,
        promoted_at,
    ) = values
    _decode_operator_pool_json(operator_pool_json)
    return {
        "version": _nonnegative_sqlite_integer(version, field="Champion version"),
        "weight_revision": _nonnegative_sqlite_integer(
            weight_revision,
            field="Champion weight revision",
        ),
        # Deliberately retain the exact database TEXT. Semantically equivalent
        # operator JSON with different stored bytes is a different storage fact.
        "operator_pool_json": operator_pool_json,
        "solver_config_hash": _required_text(
            solver_config_hash,
            field="Champion solver config hash",
        ),
        "code_snapshot_path": _required_text(
            code_snapshot_path,
            field="Champion code snapshot path",
        ),
        "code_snapshot_hash": _required_text(
            code_snapshot_hash,
            field="Champion code snapshot hash",
        ),
        "promotion_experiment_id": _optional_text(
            promotion_experiment_id,
            field="Champion promotion experiment ID",
        ),
        "promotion_dossier_ref": _optional_text(
            promotion_dossier_ref,
            field="Champion promotion dossier reference",
        ),
        "promoted_at": _optional_text(
            promoted_at,
            field="Champion promotion time",
        ),
    }


def _decode_canonical_storage_payload(payload_json: object) -> dict[str, object]:
    if type(payload_json) is not bytes:
        raise DurableOwnerIntegrityError(
            "Champion storage payload must be immutable canonical bytes"
        )
    try:
        decoded = json.loads(
            payload_json.decode("utf-8"),
            object_pairs_hook=_duplicate_rejecting_object,
            parse_constant=_reject_json_constant,
        )
    except DurableOwnerIntegrityError:
        raise
    except (TypeError, ValueError, UnicodeDecodeError, RecursionError) as exc:
        raise DurableOwnerIntegrityError(
            "Champion canonical storage payload is malformed"
        ) from exc
    if type(decoded) is not dict or tuple(sorted(decoded)) != tuple(
        sorted(_CHAMPION_COLUMNS)
    ):
        raise DurableOwnerIntegrityError(
            "Champion canonical storage payload has incomplete or unexpected fields"
        )
    payload = _champion_storage_payload(
        tuple(decoded[key] for key in _CHAMPION_COLUMNS)
    )
    if _canonical_json_bytes(payload, field="Champion storage payload") != payload_json:
        raise DurableOwnerIntegrityError(
            "Champion storage payload bytes are not canonical"
        )
    return payload


@dataclass(frozen=True)
class StoredChampionRecord:
    """Immutable token for one exact champion row storage fact."""

    version: int
    weight_revision: int
    canonical_storage_payload_json: bytes
    storage_sha256: str

    @classmethod
    def _from_storage_values(cls, values: tuple[object, ...]) -> "StoredChampionRecord":
        payload = _champion_storage_payload(values)
        payload_json = _canonical_json_bytes(payload, field="Champion storage payload")
        return cls(
            version=payload["version"],  # type: ignore[arg-type]
            weight_revision=payload["weight_revision"],  # type: ignore[arg-type]
            canonical_storage_payload_json=payload_json,
            storage_sha256=hashlib.sha256(payload_json).hexdigest(),
        )

    def value(self) -> ChampionState:
        """Decode a new detached public Champion value on every call."""

        version = _nonnegative_sqlite_integer(self.version, field="Champion version")
        weight_revision = _nonnegative_sqlite_integer(
            self.weight_revision,
            field="Champion weight revision",
        )
        payload = _decode_canonical_storage_payload(self.canonical_storage_payload_json)
        if (
            payload["version"] != version
            or payload["weight_revision"] != weight_revision
        ):
            raise DurableOwnerIntegrityError(
                "Champion token identity conflicts with its storage payload"
            )
        if (
            type(self.storage_sha256) is not str
            or hashlib.sha256(self.canonical_storage_payload_json).hexdigest()
            != self.storage_sha256
        ):
            raise DurableOwnerIntegrityError(
                "Champion storage payload digest does not match its bytes"
            )
        return ChampionState(
            version=version,
            weight_revision=weight_revision,
            operator_pool=_decode_operator_pool_json(payload["operator_pool_json"]),
            solver_config_hash=payload["solver_config_hash"],  # type: ignore[arg-type]
            code_snapshot_path=payload["code_snapshot_path"],  # type: ignore[arg-type]
            code_snapshot_hash=payload["code_snapshot_hash"],  # type: ignore[arg-type]
            promotion_experiment_id=payload["promotion_experiment_id"],  # type: ignore[arg-type]
            promotion_dossier_ref=payload["promotion_dossier_ref"],  # type: ignore[arg-type]
            promoted_at=payload["promoted_at"],  # type: ignore[arg-type]
        )


def _decode_current_champion_rows(
    rows: tuple[object, ...],
) -> StoredChampionRecord | None:
    return _decode_single_champion_rows(rows, query_label="Current champion")


def _decode_exact_champion_rows(
    rows: tuple[object, ...],
) -> StoredChampionRecord | None:
    return _decode_single_champion_rows(rows, query_label="Exact champion")


def _decode_single_champion_rows(
    rows: tuple[object, ...],
    *,
    query_label: str,
) -> StoredChampionRecord | None:
    if not rows:
        return None
    if len(rows) != 1:
        raise DurableOwnerIntegrityError(
            f"{query_label} query returned more than one storage fact"
        )
    row = rows[0]
    try:
        columns = tuple(row.keys())  # type: ignore[attr-defined]
        values = tuple(row)  # type: ignore[arg-type]
    except (AttributeError, TypeError, ValueError) as exc:
        raise DurableOwnerIntegrityError(
            f"{query_label} row is not a named materialized SQLite row"
        ) from exc
    if columns != _CHAMPION_COLUMNS:
        raise DurableOwnerIntegrityError(
            f"{query_label} query returned incomplete or unexpected columns"
        )
    return StoredChampionRecord._from_storage_values(values)


@dataclass(frozen=True, slots=True)
class _BranchCreationOutcomeProjection:
    champion: StoredChampionRecord
    target: RevisionedBranchRecord


@dataclass(frozen=True, slots=True)
class _BoundBranchCreationOutcome:
    authorization: _owner._OwnerCreationAuthorization
    projection: _BranchCreationOutcomeProjection


class ConnectionScopedChampionStore:
    """Dormant strict champion reader bound to one Campaign database authority."""

    __slots__ = (
        "__creation_authorizer",
        "__database_authority",
        "__outcome_projections",
        "__pending_outcomes",
        "__pending_projections",
    )

    def __init__(
        self,
        database_authority: _sqlite.CampaignDatabaseAuthority,
    ) -> None:
        # Lookup is intentional: constructing the participant proves the
        # authority was issued by the SQLite boundary, without opening a DB.
        _sqlite._lookup_authority_state(database_authority)
        self.__database_authority = database_authority
        self.__creation_authorizer = _owner._issue_branch_creation_authorizer_authority(
            database_authority
        )
        self.__pending_projections: weakref.WeakKeyDictionary[
            _owner._OwnerCreationAuthorization,
            _BranchCreationOutcomeProjection,
        ] = weakref.WeakKeyDictionary()
        self.__pending_outcomes: weakref.WeakKeyDictionary[
            _owner.SemanticCreationOutcomeWitness,
            _BranchCreationOutcomeProjection,
        ] = weakref.WeakKeyDictionary()
        # Classification receives only the opaque witness and authorization.
        # Complete semantic projections therefore remain strongly participant-
        # owned instead of being reconstructed through a weak lookup.
        self.__outcome_projections: dict[
            _owner.SemanticCreationOutcomeWitness,
            _BoundBranchCreationOutcome,
        ] = {}

    def load_current_in(
        self,
        transaction: _sqlite.ImmediateTransaction,
    ) -> StoredChampionRecord | None:
        result = _sqlite._execute_participant(
            transaction,
            self.__database_authority,
            _CURRENT_CHAMPION_SELECT_SQL,
        )
        if (
            tuple(column[0] for column in (result.description or ()))
            != _CHAMPION_COLUMNS
        ):
            raise DurableOwnerIntegrityError(
                "Current champion SELECT did not return the frozen columns"
            )
        return _decode_current_champion_rows(result.fetchall())

    def _load_current_from_snapshot(
        self,
        snapshot: _sqlite._IndependentReadSnapshot,
    ) -> StoredChampionRecord | None:
        rows = _sqlite._execute_read_snapshot(
            snapshot,
            self.__database_authority,
            _CURRENT_CHAMPION_SELECT_SQL,
        )
        return _decode_current_champion_rows(rows)

    def _load_exact_from_snapshot(
        self,
        snapshot: _sqlite._IndependentReadSnapshot,
        version: int,
        weight_revision: int,
    ) -> StoredChampionRecord | None:
        """Load one captured append-only champion identity from one read snapshot."""

        exact_version = _nonnegative_sqlite_integer(
            version,
            field="Champion version",
        )
        exact_weight_revision = _nonnegative_sqlite_integer(
            weight_revision,
            field="Champion weight revision",
        )
        rows = _sqlite._execute_read_snapshot(
            snapshot,
            self.__database_authority,
            _EXACT_CHAMPION_SELECT_SQL,
            (exact_version, exact_weight_revision),
        )
        token = _decode_exact_champion_rows(rows)
        if token is not None and (
            token.version != exact_version
            or token.weight_revision != exact_weight_revision
        ):
            raise DurableOwnerIntegrityError(
                "Exact champion query returned another storage identity"
            )
        return token

    @staticmethod
    def _require_branch_anchor(
        champion: StoredChampionRecord,
        target: RevisionedBranchRecord,
    ) -> None:
        if type(champion) is not StoredChampionRecord:
            raise DurableOwnerIntegrityError(
                "Branch creation requires an exact stored champion token"
            )
        if type(target) is not RevisionedBranchRecord or target.owner_revision != 0:
            raise DurableOwnerIntegrityError(
                "Branch creation requires an exact revision-zero Branch token"
            )
        champion_value = champion.value()
        target_value = target.value()
        if (
            target_value.base_champion_id != champion_value.version
            or target_value.weight_revision != champion_value.weight_revision
            or target_value.base_champion_hash != champion_value.code_snapshot_hash
        ):
            raise DurableOwnerIntegrityError(
                "Branch creation target does not match the exact champion anchor"
            )

    def _authorize_branch_creation_in(
        self,
        transaction: _sqlite.ImmediateTransaction,
        ledger: _owner._OwnerReceiptLedger,
        champion: StoredChampionRecord,
        target: RevisionedBranchRecord,
    ) -> _owner._OwnerCreationAuthorization:
        """Register one Branch authorization after a same-transaction read."""

        self._require_branch_anchor(champion, target)
        current = self.load_current_in(transaction)
        if current is None or current != champion:
            raise DurableOwnerIntegrityError(
                "Branch creation champion is not the exact durable current row"
            )
        # Revalidate both tokens after equality: dataclass equality alone does
        # not authenticate caller-constructed canonical bytes.
        current.value()
        champion.value()
        authorization = _owner._register_branch_creation_authorization(
            self.__creation_authorizer,
            transaction,
            ledger,
            target.branch_id,
            target.payload_sha256,
        )
        self.__pending_projections[authorization] = _BranchCreationOutcomeProjection(
            champion=champion,
            target=target,
        )
        return authorization

    def _complete_branch_creation_in(
        self,
        transaction: _sqlite.ImmediateTransaction,
        ledger: _owner._OwnerReceiptLedger,
        authorization: _owner._OwnerCreationAuthorization,
        receipt: _owner.OwnerCreationReceipt,
    ) -> _owner.SemanticCreationOutcomeWitness:
        """Revalidate semantic facts and irreversibly complete authorization."""

        if type(authorization) is not _owner._OwnerCreationAuthorization:
            raise DurableOwnerIntegrityError(
                "Branch creation completion requires its exact authorization"
            )
        projection = self.__pending_projections.get(authorization)
        if projection is None:
            raise DurableOwnerIntegrityError(
                "Branch creation authorization has no captured champion source"
            )
        champion = projection.champion
        target = projection.target
        self._require_branch_anchor(champion, target)
        current = self.load_current_in(transaction)
        if current is None or current != champion:
            raise DurableOwnerIntegrityError(
                "Branch creation champion changed before authorization completion"
            )
        current.value()
        champion.value()
        outcome_witness = _owner._issue_branch_semantic_creation_outcome_witness(
            self.__creation_authorizer,
            transaction,
            ledger,
            authorization,
        )
        # Materialize the semantic projection before generic completion, but
        # keep it weakly keyed until completion succeeds. An interruption then
        # rolls back and cannot leave an unreachable permanent strong entry.
        self.__pending_outcomes[outcome_witness] = projection
        _owner._complete_branch_creation_authorization(
            self.__creation_authorizer,
            transaction,
            ledger,
            authorization,
            receipt,
            outcome_witness,
        )
        self.__outcome_projections[outcome_witness] = _BoundBranchCreationOutcome(
            authorization=authorization,
            projection=projection,
        )
        del self.__pending_outcomes[outcome_witness]
        del self.__pending_projections[authorization]
        return outcome_witness

    def _require_branch_creation_outcome(
        self,
        outcome_witness: _owner.SemanticCreationOutcomeWitness,
        authorization: _owner._OwnerCreationAuthorization,
    ) -> None:
        """Validate opaque identity without exposing semantic projections."""

        if type(outcome_witness) is not _owner.SemanticCreationOutcomeWitness:
            raise DurableOwnerIntegrityError(
                "Branch classification requires an exact semantic outcome witness"
            )
        bound = self.__outcome_projections.get(outcome_witness)
        if bound is None or bound.authorization is not authorization:
            raise DurableOwnerIntegrityError(
                "Branch semantic outcome witness has another authorization"
            )
        self._require_branch_anchor(
            bound.projection.champion,
            bound.projection.target,
        )

    def _settle_branch_creation_outcome(
        self,
        outcome_witness: _owner.SemanticCreationOutcomeWitness,
        authorization: _owner._OwnerCreationAuthorization,
    ) -> None:
        """Release one inert projection after Registry outcome settlement."""

        self._require_branch_creation_outcome(outcome_witness, authorization)
        del self.__outcome_projections[outcome_witness]

    def _discard_branch_creation_outcome(
        self,
        authorization: _owner._OwnerCreationAuthorization,
    ) -> None:
        """Release a promoted projection when rollback precedes witness handoff."""

        if type(authorization) is not _owner._OwnerCreationAuthorization:
            raise DurableOwnerIntegrityError(
                "Branch outcome discard requires an exact authorization"
            )
        matches = tuple(
            outcome_witness
            for outcome_witness, bound in self.__outcome_projections.items()
            if bound.authorization is authorization
        )
        if len(matches) != 1:
            raise DurableOwnerIntegrityError(
                "Branch authorization has no exact unsettled outcome"
            )
        del self.__outcome_projections[matches[0]]


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
        exists = self._conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='champions'"
        ).fetchone()
        if exists is not None:
            self._migrate_champions_table_if_needed()
            return

        self._conn.execute("""
            CREATE TABLE champions (
                version                 INTEGER NOT NULL,
                weight_revision         INTEGER NOT NULL DEFAULT 0,
                operator_pool_json      TEXT NOT NULL,
                solver_config_hash      TEXT NOT NULL,
                code_snapshot_path      TEXT NOT NULL,
                code_snapshot_hash      TEXT NOT NULL,
                promotion_experiment_id TEXT,
                promotion_dossier_ref    TEXT,
                promoted_at             TEXT,
                PRIMARY KEY (version, weight_revision)
            )
        """)
        self._conn.commit()

    def _migrate_champions_table_if_needed(self) -> None:
        """Migrate legacy champions(version PRIMARY KEY) to revision-aware schema."""
        rows = self._conn.execute("PRAGMA table_info(champions)").fetchall()
        columns = {row["name"]: row for row in rows}
        version_pk = columns["version"]["pk"] if "version" in columns else 0
        revision_pk = (
            columns["weight_revision"]["pk"] if "weight_revision" in columns else 0
        )
        if version_pk > 0 and revision_pk > 0:
            if "promotion_dossier_ref" not in columns:
                with self._conn:
                    self._conn.execute(
                        "ALTER TABLE champions ADD COLUMN promotion_dossier_ref TEXT"
                    )
            return

        with self._conn:
            self._conn.execute("ALTER TABLE champions RENAME TO champions_legacy")
            self._conn.execute("""
                CREATE TABLE champions (
                    version                 INTEGER NOT NULL,
                    weight_revision         INTEGER NOT NULL DEFAULT 0,
                    operator_pool_json      TEXT NOT NULL,
                    solver_config_hash      TEXT NOT NULL,
                    code_snapshot_path      TEXT NOT NULL,
                    code_snapshot_hash      TEXT NOT NULL,
                    promotion_experiment_id TEXT,
                    promotion_dossier_ref    TEXT,
                    promoted_at             TEXT,
                    PRIMARY KEY (version, weight_revision)
                )
            """)
            legacy_cols = {
                row["name"]
                for row in self._conn.execute("PRAGMA table_info(champions_legacy)")
            }
            revision_expr = (
                "COALESCE(weight_revision, 0)"
                if "weight_revision" in legacy_cols
                else "0"
            )
            dossier_expr = (
                "promotion_dossier_ref"
                if "promotion_dossier_ref" in legacy_cols
                else "NULL"
            )
            self._conn.execute(f"""
                INSERT OR IGNORE INTO champions (
                    version, weight_revision, operator_pool_json,
                    solver_config_hash, code_snapshot_path, code_snapshot_hash,
                    promotion_experiment_id, promotion_dossier_ref, promoted_at
                )
                SELECT
                    version, {revision_expr}, operator_pool_json,
                    solver_config_hash, code_snapshot_path, code_snapshot_hash,
                    promotion_experiment_id, {dossier_expr}, promoted_at
                FROM champions_legacy
            """)
            self._conn.execute("DROP TABLE champions_legacy")
            return

    # ──────────────────────────────────────────────────────────────────────
    # 写入接口（INSERT only）
    # ──────────────────────────────────────────────────────────────────────

    def promote(self, new_champion: ChampionState) -> None:
        """保存新 champion（INSERT only）。

        Args:
            new_champion: 新的 ChampionState 对象。

        Raises:
            sqlite3.IntegrityError: version + weight_revision 重复时抛出。
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
                version, weight_revision, operator_pool_json, solver_config_hash,
                code_snapshot_path, code_snapshot_hash,
                promotion_experiment_id, promotion_dossier_ref, promoted_at
            ) VALUES (
                :version, :weight_revision, :operator_pool_json, :solver_config_hash,
                :code_snapshot_path, :code_snapshot_hash,
                :promotion_experiment_id, :promotion_dossier_ref, :promoted_at
            )
        """
        params = {
            "version": new_champion.version,
            "weight_revision": new_champion.weight_revision,
            "operator_pool_json": operator_pool_json,
            "solver_config_hash": new_champion.solver_config_hash,
            "code_snapshot_path": new_champion.code_snapshot_path,
            "code_snapshot_hash": new_champion.code_snapshot_hash,
            "promotion_experiment_id": new_champion.promotion_experiment_id,
            "promotion_dossier_ref": new_champion.promotion_dossier_ref,
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
            "SELECT * FROM champions "
            "ORDER BY version DESC, weight_revision DESC LIMIT 1"
        ).fetchone()
        return self._row_to_champion(row) if row else None

    def get_by_version(self, version: int) -> Optional[ChampionState]:
        """按版本号获取最新 weight revision 的 champion。

        Args:
            version: champion 版本号。

        Returns:
            ChampionState 对象；不存在时返回 None。
        """
        row = self._conn.execute(
            "SELECT * FROM champions WHERE version = ? "
            "ORDER BY weight_revision DESC LIMIT 1",
            (version,),
        ).fetchone()
        return self._row_to_champion(row) if row else None

    def get_by_version_revision(
        self, version: int, weight_revision: int
    ) -> Optional[ChampionState]:
        """按版本号和权重 revision 精确获取 champion。"""
        row = self._conn.execute(
            "SELECT * FROM champions WHERE version = ? AND weight_revision = ?",
            (version, weight_revision),
        ).fetchone()
        return self._row_to_champion(row) if row else None

    def get_history(self) -> list[ChampionState]:
        """返回所有 champion 历史记录，按版本升序排列。

        Returns:
            ChampionState 列表。
        """
        rows = self._conn.execute(
            "SELECT * FROM champions ORDER BY version ASC, weight_revision ASC"
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
            promotion_dossier_ref=d.get("promotion_dossier_ref"),
            weight_revision=d.get("weight_revision", 0),
        )

    def close(self) -> None:
        """关闭数据库连接。"""
        self._conn.close()

    def __enter__(self) -> "ChampionStore":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
