from __future__ import annotations
import os
import shutil
from scion.core.models import ChampionState, Branch

class ChampionStore:
    def __init__(self, db_path: str, snapshot_dir: str):
        self.db_path = db_path
        self.snapshot_dir = snapshot_dir
        os.makedirs(self.snapshot_dir, exist_ok=True)

    def save_snapshot(self, version: int, source_dir: str) -> str:
        target_dir = os.path.join(self.snapshot_dir, f"v{version}")
        if os.path.exists(target_dir):
            shutil.rmtree(target_dir)
        shutil.copytree(source_dir, target_dir)
        # 设为只读保护
        for root, dirs, files in os.walk(target_dir):
            for d in dirs:
                os.chmod(os.path.join(root, d), 0o555)
            for f in files:
                os.chmod(os.path.join(root, f), 0o444)
        return target_dir

class BranchStore:
    def __init__(self, registry: 'LineageRegistry'):
        self.registry = registry

    def save(self, branch: Branch):
        import sqlite3
        import json
        with sqlite3.connect(self.registry.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO branches 
                (branch_id, state, base_champion_id, base_champion_hash, 
                 current_code_hash, last_clean_code_hash, retry_count, 
                 failure_codes, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                branch.branch_id,
                branch.state.value,
                branch.base_champion_id,
                branch.base_champion_hash,
                branch.current_code_hash,
                branch.last_clean_code_hash,
                branch.retry_count,
                json.dumps(branch.failure_codes),
                branch.created_at.isoformat(),
                branch.updated_at.isoformat()
            ))

    def load(self, branch_id: str) -> Optional[Branch]:
        import sqlite3
        import json
        from scion.core.models import BranchState
        from datetime import datetime
        with sqlite3.connect(self.registry.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM branches WHERE branch_id = ?", (branch_id,)).fetchone()
            if not row:
                return None
            return Branch(
                branch_id=row['branch_id'],
                state=BranchState(row['state']),
                base_champion_id=row['base_champion_id'],
                base_champion_hash=row['base_champion_hash'],
                current_code_hash=row['current_code_hash'],
                last_clean_code_hash=row['last_clean_code_hash'],
                retry_count=row['retry_count'],
                failure_codes=json.loads(row['failure_codes']),
                created_at=datetime.fromisoformat(row['created_at']),
                updated_at=datetime.fromisoformat(row['updated_at'])
            )

class HypothesisStore:
    def __init__(self, registry: 'LineageRegistry'):
        self.registry = registry

    def save(self, hyp: 'HypothesisRecord'):
        import sqlite3
        with sqlite3.connect(self.registry.db_path) as conn:
            # Note: We need a hypotheses table
            conn.execute("CREATE TABLE IF NOT EXISTS hypotheses (hypothesis_id TEXT PRIMARY KEY, branch_id TEXT, change_locus TEXT, action TEXT, status TEXT, target_file TEXT, parent_hypothesis_id TEXT, suggested_weight REAL, created_at TEXT)")
            conn.execute("""
                INSERT OR REPLACE INTO hypotheses 
                (hypothesis_id, branch_id, change_locus, action, status, 
                 target_file, parent_hypothesis_id, suggested_weight, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                hyp.hypothesis_id,
                hyp.branch_id,
                hyp.change_locus,
                hyp.action,
                hyp.status,
                hyp.target_file,
                hyp.parent_hypothesis_id,
                hyp.suggested_weight,
                hyp.created_at.isoformat()
            ))
