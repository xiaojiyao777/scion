"""CampaignJournal — structured champion evolution and cross-branch history (W9).

Derives all views from lineage queries (persist facts, rebuild views).
Used by ContextManager to inject structured history into LLM prompts.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from scion.lineage.registry import LineageRegistry


@dataclass(frozen=True)
class ChampionEpoch:
    version: int
    promoted_at: str
    code_hash: str
    n_branches_explored: int
    n_hypotheses: int
    n_promoted: int


@dataclass(frozen=True)
class JournalSnapshot:
    champion_epochs: tuple[ChampionEpoch, ...]
    total_experiments: int
    total_branches: int
    family_distribution: Dict[str, int]


class CampaignJournal:
    """Builds structured journal views from lineage."""

    def __init__(self, registry: LineageRegistry) -> None:
        self._registry = registry

    def build_snapshot(self) -> JournalSnapshot:
        import sqlite3
        db = self._registry.db_path

        with sqlite3.connect(db) as conn:
            conn.row_factory = sqlite3.Row

            epochs = []
            for row in conn.execute("""
                SELECT version, code_snapshot_path, code_snapshot_hash, promoted_at
                FROM champions ORDER BY version
            """).fetchall():
                d = dict(row)
                ver = d["version"]
                n_branches = conn.execute(
                    "SELECT COUNT(DISTINCT branch_id) FROM hypotheses WHERE base_champion_version = ?",
                    (ver,),
                ).fetchone()[0]
                n_hyps = conn.execute(
                    "SELECT COUNT(*) FROM hypotheses WHERE base_champion_version = ?",
                    (ver,),
                ).fetchone()[0]
                n_promoted = conn.execute(
                    "SELECT COUNT(*) FROM hypotheses WHERE base_champion_version = ? AND status = 'promoted'",
                    (ver,),
                ).fetchone()[0]
                epochs.append(ChampionEpoch(
                    version=ver,
                    promoted_at=d.get("promoted_at") or "",
                    code_hash=d.get("code_snapshot_hash") or "",
                    n_branches_explored=n_branches,
                    n_hypotheses=n_hyps,
                    n_promoted=n_promoted,
                ))

            total_experiments = conn.execute(
                "SELECT COUNT(*) FROM experiment_events WHERE event_kind = 'experiment'"
            ).fetchone()[0]
            total_branches = conn.execute(
                "SELECT COUNT(DISTINCT branch_id) FROM branches"
            ).fetchone()[0]

            family_dist: Dict[str, int] = {}
            for row in conn.execute(
                "SELECT family_id, COUNT(*) as cnt FROM hypotheses WHERE family_id IS NOT NULL GROUP BY family_id"
            ).fetchall():
                family_dist[row["family_id"]] = row["cnt"]

        return JournalSnapshot(
            champion_epochs=tuple(epochs),
            total_experiments=total_experiments,
            total_branches=total_branches,
            family_distribution=family_dist,
        )

    def render_for_llm(self, max_epochs: int = 5) -> str:
        snap = self.build_snapshot()
        lines = [f"## Campaign Journal ({snap.total_experiments} experiments, {snap.total_branches} branches)"]

        if snap.champion_epochs:
            lines.append("\n### Champion Evolution")
            for e in snap.champion_epochs[-max_epochs:]:
                lines.append(
                    f"  v{e.version}: {e.n_branches_explored} branches, "
                    f"{e.n_hypotheses} hypotheses, {e.n_promoted} promoted"
                )

        if snap.family_distribution:
            lines.append("\n### Family Distribution")
            for fam, cnt in sorted(snap.family_distribution.items(), key=lambda x: -x[1])[:8]:
                lines.append(f"  {fam}: {cnt}")

        return "\n".join(lines)
