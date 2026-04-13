"""CampaignResearchLog — Campaign Research Journal for LLM context (v3).

Three-layer information architecture:
  Layer 1 — Research snapshot (where are we now)
  Layer 2 — Full branch trajectories (what was tried, complete, untruncated)
  Champion evolution bridges Layer 1 and Layer 2.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import json
import os
import sqlite3


@dataclass
class BranchTrajectory:
    branch_id: str
    operator_name: str
    hypothesis_text: str          # full text, no truncation
    stages: List[Dict]            # [{stage, wr, md, decision}, ...]
    outcome: str                  # promoted / failed_frozen / failed_validation / abandoned
    screening_rounds: int         # how many screening events
    best_screening_wr: Optional[float]


# Legacy alias
BranchSummary = BranchTrajectory


class CampaignResearchLog:
    """Reads from SQLite experiment_events to build a Campaign Research Journal.

    Exposure rules:
    - Screening results: full (wr + median_delta)
    - Validation results: aggregate wr only (no per-case)
    - Frozen results: pass/fail only (NO wr, NO median_delta)
    """

    def __init__(self, campaign_dir: str) -> None:
        self._db_path = os.path.join(campaign_dir, "scion.db")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def render(self, available_tokens: Optional[int] = None) -> str:
        """Render complete Campaign Research Journal for LLM context injection.

        No character/token limits by default (available_tokens=None).
        If available_tokens is set (future use), compress by dropping
        low-wr abandoned branches first.

        Structure:
          1. Research snapshot (Layer 1: where are we now)
          2. Champion evolution (what innovations were made)
          3. Full branch trajectories (what was tried, complete, untruncated)
        """
        if not os.path.exists(self._db_path):
            return ""
        try:
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row

            sections: List[str] = ["## Campaign Research Journal\n"]

            # Layer 1: Research snapshot
            snapshot = self._build_research_snapshot(conn)
            if snapshot:
                sections.append(f"### 研究进展快照\n{snapshot}")

            # Champion evolution
            evolution = self._build_champion_evolution(conn)
            if evolution:
                sections.append(f"### Champion 演化轨迹\n{evolution}")

            # Layer 2: Full branch trajectories
            trajectories = self._build_full_branch_trajectories(conn)
            if trajectories:
                sections.append(f"### 所有实验 Branch 轨迹\n{trajectories}")

            conn.close()

            result = "\n\n".join(sections).rstrip()
            # If only header, return empty
            if result.strip() == "## Campaign Research Journal":
                return ""
            return result

        except Exception:
            return ""

    def build(self) -> List[BranchTrajectory]:
        """Build branch trajectories from SQLite. Legacy compat."""
        if not os.path.exists(self._db_path):
            return []
        try:
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            result = self._query_all_branches(conn)
            conn.close()
            return result
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Layer 1: Research Snapshot
    # ------------------------------------------------------------------

    def _build_research_snapshot(self, conn: sqlite3.Connection) -> str:
        """Layer 1: Research orientation snapshot. Computed from DB."""
        parts: List[str] = []

        # Champion version count
        try:
            champ_row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM champions"
            ).fetchone()
            champion_count = champ_row['cnt'] if champ_row else 0
        except Exception:
            champion_count = 0

        # Total branches + experiments
        try:
            stats_row = conn.execute("""
                SELECT COUNT(DISTINCT branch_id) AS n_branches,
                       COUNT(*) AS n_experiments
                FROM experiment_events
                WHERE event_kind = 'experiment'
            """).fetchone()
            n_branches = stats_row['n_branches'] if stats_row else 0
            n_experiments = stats_row['n_experiments'] if stats_row else 0
        except Exception:
            n_branches = 0
            n_experiments = 0

        if champion_count > 0 or n_branches > 0:
            parts.append(
                f"Champion 当前版本：v{champion_count}，共 {champion_count} 次晋升\n"
                f"搜索进度：{n_branches} 个 branch，{n_experiments} 轮实验"
            )

        # Operator weights from latest weight_optimizations
        weight_lines = self._build_weight_feedback(conn)
        if weight_lines:
            parts.append("算子池权重（当前 champion）：\n" + "\n".join(weight_lines))

        # Coverage gaps: locus/action combinations with < 5 attempts
        gap_lines = self._build_coverage_gaps(conn)
        if gap_lines:
            parts.append("尚未探索的方向：\n" + "\n".join(gap_lines))

        return "\n\n".join(parts)

    def _build_coverage_gaps(self, conn: sqlite3.Connection) -> List[str]:
        """Find locus/action combinations with < 5 attempts."""
        lines: List[str] = []
        try:
            rows = conn.execute("""
                SELECT h.change_locus, h.action, COUNT(*) AS cnt
                FROM experiment_events e
                JOIN hypotheses h ON e.hypothesis_id = h.hypothesis_id
                WHERE e.event_kind = 'experiment'
                  AND h.change_locus IS NOT NULL
                  AND h.action IS NOT NULL
                GROUP BY h.change_locus, h.action
                ORDER BY cnt ASC
            """).fetchall()
        except Exception:
            return lines

        for row in rows:
            cnt = row['cnt']
            if cnt < 5:
                locus = row['change_locus']
                action = row['action']
                if cnt < 2:
                    severity = "← 严重不足"
                else:
                    severity = "← 不足"
                lines.append(f"  {locus}/{action}: {cnt}次 {severity}")

        return lines

    # ------------------------------------------------------------------
    # Champion Evolution
    # ------------------------------------------------------------------

    def _build_champion_evolution(self, conn: sqlite3.Connection) -> str:
        """Build champion evolution with hypothesis text for each promoted operator."""
        lines: List[str] = []
        try:
            rows = conn.execute(
                "SELECT version, code_snapshot_path, promotion_experiment_id "
                "FROM champions ORDER BY version ASC"
            ).fetchall()
        except Exception:
            return ""

        if not rows:
            return ""

        prev_ops: set = set()
        for row in rows:
            version = row['version']
            snap_path = row['code_snapshot_path']
            ops_dir = os.path.join(snap_path, 'operators') if snap_path else None

            current_ops: set = set()
            if ops_dir and os.path.isdir(ops_dir):
                for f in os.listdir(ops_dir):
                    if f.endswith('.py') and f not in ('__init__.py', 'base.py'):
                        current_ops.add(f.replace('.py', ''))

            if version == 1 or not prev_ops:
                if current_ops:
                    op_list = ", ".join(sorted(current_ops))
                    lines.append(f"v{version} base pool: {{{op_list}}}")
            else:
                new_ops = current_ops - prev_ops
                if new_ops:
                    for op in sorted(new_ops):
                        lines.append(f"v{version} 新增: {op}")
                        # Get promotion hypothesis + screening info
                        promo_detail = self._get_promotion_detail(conn, op)
                        if promo_detail:
                            lines.append(promo_detail)
                else:
                    lines.append(f"v{version} → (weight optimization only)")

            if current_ops:
                prev_ops = current_ops

        return "\n".join(lines)

    def _get_promotion_detail(self, conn: sqlite3.Connection, operator_name: str) -> str:
        """Get full hypothesis text + screening wr + frozen result for a promoted operator."""
        try:
            row = conn.execute("""
                SELECT e.hypothesis_text,
                       e.screening_win_rate
                FROM experiment_events e
                WHERE e.event_kind = 'experiment'
                  AND e.decision = 'promote'
                  AND (e.patch_file LIKE ? OR e.patch_file LIKE ?)
                ORDER BY e.created_at DESC LIMIT 1
            """, (f"%{operator_name}%", f"%{operator_name}%")).fetchone()

            if not row:
                return ""

            parts: List[str] = []
            hyp = row['hypothesis_text'] or ''
            if hyp:
                parts.append(f'  "{hyp}"')

            wr = row['screening_win_rate']
            if wr is not None:
                parts.append(f"  → scr={wr:.2f} → frozen=PASS")
            else:
                parts.append("  → frozen=PASS")

            return "\n".join(parts)
        except Exception:
            return ""

    # ------------------------------------------------------------------
    # Layer 2: Full Branch Trajectories
    # ------------------------------------------------------------------

    def _build_full_branch_trajectories(self, conn: sqlite3.Connection) -> str:
        """Layer 2: All branch trajectories, ordered by outcome priority, untruncated."""
        trajectories = self._query_all_branches(conn)
        if not trajectories:
            return ""

        # Categorise
        promoted = [t for t in trajectories if t.outcome == 'promoted']
        failed_frozen = [t for t in trajectories if t.outcome == 'failed_frozen']
        failed_val = [t for t in trajectories if t.outcome == 'failed_validation']
        abandoned = [t for t in trajectories if t.outcome == 'abandoned']

        # Sort abandoned by best_screening_wr descending (None → -1)
        abandoned.sort(
            key=lambda t: t.best_screening_wr if t.best_screening_wr is not None else -1,
            reverse=True,
        )

        lines: List[str] = []
        idx = 1

        for group in [promoted, failed_frozen, failed_val, abandoned]:
            for t in group:
                lines.extend(self._render_branch(t, idx))
                lines.append("")
                idx += 1

        return "\n".join(lines).rstrip()

    def _query_all_branches(self, conn: sqlite3.Connection) -> List[BranchTrajectory]:
        """Query all branches with full info from experiment_events + hypotheses."""
        try:
            rows = conn.execute("""
                SELECT
                    e.branch_id,
                    e.stage,
                    e.screening_win_rate,
                    e.screening_median_delta,
                    e.decision,
                    COALESCE(e.patch_file, h.target_file) AS resolved_file,
                    e.hypothesis_text,
                    e.created_at
                FROM experiment_events e
                LEFT JOIN hypotheses h ON e.hypothesis_id = h.hypothesis_id
                WHERE e.event_kind = 'experiment'
                ORDER BY e.branch_id, e.created_at
            """).fetchall()
        except Exception:
            return []

        branch_data: dict = defaultdict(list)
        for r in rows:
            branch_data[r['branch_id']].append({
                'stage': r['stage'],
                'wr': r['screening_win_rate'],
                'md': r['screening_median_delta'],
                'decision': r['decision'],
                'file': r['resolved_file'],
                'hyp': r['hypothesis_text'],
            })

        trajectories = []
        for bid, steps in branch_data.items():
            # Operator name from file path
            op_name = ''
            for s in steps:
                if s['file']:
                    op_name = s['file'].split('/')[-1].replace('.py', '')
                    break
            # Fallback: extract class name from hypothesis text
            if not op_name:
                for s in steps:
                    if s['hyp']:
                        m = re.search(r'"([A-Z][A-Za-z0-9]+)"', s['hyp'] or '')
                        if m:
                            op_name = m.group(1)
                            break

            # Full hypothesis text — NO truncation
            hyp_text = ''
            for s in steps:
                if s['hyp']:
                    hyp_text = s['hyp']
                    break

            # Build stages list
            stage_list = []
            for s in steps:
                stage_list.append({
                    'stage': s['stage'],
                    'wr': s['wr'],
                    'md': s['md'],
                    'decision': s['decision'],
                })

            # Count screening rounds
            screening_rounds = sum(1 for s in steps if s['stage'] == 'screening')

            # Best screening wr
            scr_wrs = [s['wr'] for s in steps if s['stage'] == 'screening' and s['wr'] is not None]
            best_scr = max(scr_wrs) if scr_wrs else None

            # Determine outcome
            final = steps[-1]
            has_frozen = any(s['stage'] == 'frozen' for s in steps)
            has_val = any(s['stage'] == 'validation' for s in steps)

            if final['decision'] == 'promote':
                outcome = 'promoted'
            elif has_frozen and final['decision'] == 'abandon':
                outcome = 'failed_frozen'
            elif has_val and final['decision'] == 'abandon':
                outcome = 'failed_validation'
            else:
                outcome = 'abandoned'

            trajectories.append(BranchTrajectory(
                branch_id=bid,
                operator_name=op_name,
                hypothesis_text=hyp_text,
                stages=stage_list,
                outcome=outcome,
                screening_rounds=screening_rounds,
                best_screening_wr=best_scr,
            ))

        return trajectories

    def _render_branch(self, t: BranchTrajectory, idx: int) -> List[str]:
        """Render a single branch trajectory."""
        lines: List[str] = []
        bid_short = t.branch_id[:8]

        # Header
        lines.append(f"--- Branch {idx} [{bid_short}] → {t.outcome} ---")
        lines.append(f"算子: {t.operator_name}")

        # Full hypothesis text
        if t.hypothesis_text:
            lines.append(f'假设: "{t.hypothesis_text}"')

        # Stage trajectory
        traj_parts: List[str] = []
        screening_idx = 0
        for s in t.stages:
            stage = s['stage']
            if stage == 'frozen':
                # Only PASS/FAIL, no wr, no md
                if s.get('decision') == 'promote':
                    traj_parts.append("  frozen: PASS")
                else:
                    traj_parts.append("  frozen: FAIL")
            elif stage == 'screening':
                screening_idx += 1
                wr = s.get('wr')
                md = s.get('md')
                decision = s.get('decision', '')
                wr_str = f"scr={wr:.2f}" if wr is not None else "scr=?"
                md_str = f" [md={int(md)}]" if md is not None else ""
                traj_parts.append(
                    f"  Round {screening_idx}: {wr_str}{md_str} → {decision}"
                )
            elif stage == 'validation':
                wr = s.get('wr')
                decision = s.get('decision', '')
                wr_str = f"val={wr:.2f}" if wr is not None else "val=?"
                traj_parts.append(f"  validation: {wr_str} → {decision}")

        if traj_parts:
            lines.append("轨迹:")
            lines.extend(traj_parts)

        return lines

    # ------------------------------------------------------------------
    # Weight Feedback (shared by snapshot + legacy)
    # ------------------------------------------------------------------

    def _build_weight_feedback(self, conn: sqlite3.Connection) -> List[str]:
        """Build weight feedback from latest weight_optimizations record."""
        lines: List[str] = []
        try:
            row = conn.execute(
                "SELECT best_weights_json FROM weight_optimizations "
                "ORDER BY timestamp DESC LIMIT 1"
            ).fetchone()
        except Exception:
            return lines

        if not row or not row['best_weights_json']:
            return lines

        try:
            weights: Dict[str, float] = json.loads(row['best_weights_json'])
        except (json.JSONDecodeError, TypeError):
            return lines

        if not weights:
            return lines

        # Sort by weight descending
        sorted_weights = sorted(weights.items(), key=lambda x: x[1], reverse=True)
        for name, w in sorted_weights:
            if w > 1.0:
                annotation = "← 高贡献（核心算子）"
            elif w >= 0.3:
                annotation = "（中等）"
            else:
                annotation = "← 低贡献（改进机会？）"
            lines.append(f"  {name}: {w:.2f} {annotation}")

        return lines
