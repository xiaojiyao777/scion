"""CampaignResearchLog — cross-branch experimental trajectory for LLM context (v2)."""
from __future__ import annotations

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
    hypothesis_text: str          # up to 200 chars
    stages: List[Dict]            # [{stage, wr, decision}, ...]
    outcome: str                  # promoted / failed_frozen / failed_validation / abandoned
    screening_rounds: int         # how many screening events
    best_screening_wr: Optional[float]


# Legacy alias
BranchSummary = BranchTrajectory


class CampaignResearchLog:
    """Reads from SQLite experiment_events to build a cross-branch research log.

    Exposure rules:
    - Screening results: full (wr + median_delta)
    - Validation results: aggregate wr only (no per-case)
    - Frozen results: pass/fail only (NO wr, NO median_delta)
    """

    def __init__(self, campaign_dir: str) -> None:
        self._db_path = os.path.join(campaign_dir, "scion.db")

    def render(self, available_tokens: Optional[int] = None) -> str:
        """Render cross-branch research log for LLM injection."""
        if not os.path.exists(self._db_path):
            return ""
        try:
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row

            trajectories = self._build_full_trajectory(conn)
            if not trajectories:
                conn.close()
                return ""

            champion_evo = self._build_champion_evolution(conn)
            weight_section = self._build_weight_feedback(conn)
            conn.close()

            # Categorise
            promoted = [t for t in trajectories if t.outcome == 'promoted']
            failed_frozen = [t for t in trajectories if t.outcome == 'failed_frozen']
            failed_val = [t for t in trajectories if t.outcome == 'failed_validation']
            abandoned = [t for t in trajectories if t.outcome == 'abandoned']

            # Sort abandoned by best_screening_wr descending (None → -1)
            abandoned.sort(key=lambda t: t.best_screening_wr if t.best_screening_wr is not None else -1, reverse=True)

            lines: List[str] = ["## Campaign Research Log\n"]

            # Section 1: Champion evolution
            if champion_evo:
                lines.append("### Champion 演化（算子级别）")
                lines.extend(champion_evo)
                lines.append("")

            # Section 2: Weight feedback
            if weight_section:
                lines.append("### 当前 Champion Pool 算子权重")
                lines.extend(weight_section)
                lines.append("")

            # Section 3: All branch trajectories
            lines.append("### 所有实验 Branch 轨迹\n")

            # Priority 1-2: Promoted (never trimmed)
            for t in promoted:
                lines.extend(self._render_branch(t))
                lines.append("")

            # Priority 3: Failed at validation
            for t in failed_frozen:
                lines.extend(self._render_branch(t))
                lines.append("")

            # Priority 3: Failed at validation stage
            for t in failed_val:
                lines.extend(self._render_branch(t))
                lines.append("")

            # Priority 4-5: Abandoned
            if abandoned:
                lines.append(f"\nFailed at Screening ({len(abandoned)} branches)")

            if len(abandoned) > 20:
                top_abandoned = abandoned[:20]
                batch_abandoned = abandoned[20:]
                for t in top_abandoned:
                    lines.extend(self._render_branch(t))
                    lines.append("")
                # Batch display for remaining
                batch_names = [t.operator_name or t.hypothesis_text[:30] for t in batch_abandoned]
                lines.append(f"[ABANDONED x{len(batch_abandoned)} more, wr≤{batch_abandoned[0].best_screening_wr or 0:.2f}]")
                for i in range(0, len(batch_names), 3):
                    lines.append("  " + " | ".join(batch_names[i:i+3]))
                self._append_pattern_analysis(lines, abandoned)
            else:
                for t in abandoned:
                    lines.extend(self._render_branch(t))
                    lines.append("")
                self._append_pattern_analysis(lines, abandoned)

            return "\n".join(lines).rstrip()

        except Exception:
            return ""

    def _render_branch(self, t: BranchTrajectory) -> List[str]:
        """Render a single branch trajectory."""
        lines = []
        # Header line
        if t.outcome == 'promoted':
            label = f"[PROMOTED] {t.operator_name}"
        elif t.outcome == 'failed_frozen':
            label = f"[FAILED frozen] {t.operator_name}"
        elif t.outcome == 'failed_validation':
            label = f"[FAILED at validation] {t.operator_name}"
        else:
            rounds_str = f" ({t.screening_rounds} rounds)" if t.screening_rounds > 1 else ""
            label = f"[ABANDONED] {t.operator_name}{rounds_str}"

        lines.append(label)

        # Hypothesis text
        if t.hypothesis_text:
            lines.append(f'  "{t.hypothesis_text}"')

        # Stage path
        path_parts = []
        for s in t.stages:
            stage = s['stage']
            if stage == 'frozen':
                # Only PASS/FAIL, no wr
                if s.get('decision') == 'promote':
                    path_parts.append("frozen=PASS")
                else:
                    path_parts.append("frozen=FAIL")
            elif stage == 'screening':
                wr = s.get('wr')
                if wr is not None:
                    path_parts.append(f"scr={wr:.2f}")
                else:
                    path_parts.append("scr=?")
            elif stage == 'validation':
                wr = s.get('wr')
                if wr is not None:
                    path_parts.append(f"val={wr:.2f}")
                else:
                    path_parts.append("val=?")

        if path_parts:
            lines.append(f"  {' → '.join(path_parts)}")

        return lines

    @staticmethod
    def _append_pattern_analysis(lines: List[str], abandoned: List[BranchTrajectory]) -> None:
        """Append pattern analysis warnings for abandoned branches."""
        scr_wrs = [t.best_screening_wr for t in abandoned if t.best_screening_wr is not None]
        if scr_wrs:
            max_scr = max(scr_wrs)
            if max_scr < 0.20:
                lines.append(f"  → All wr < 0.20: these directions show no signal — avoid repeating them")
            elif max_scr < 0.35:
                lines.append(f"  → Best screening wr={max_scr:.2f}: weak signal — consider fundamentally different approaches")

    def _build_champion_evolution(self, conn: sqlite3.Connection) -> List[str]:
        """Build champion evolution section by diffing operator dirs across versions."""
        lines = []
        try:
            rows = conn.execute(
                "SELECT version, code_snapshot_path, promotion_experiment_id "
                "FROM champions ORDER BY version ASC"
            ).fetchall()
        except Exception:
            return lines

        if not rows:
            return lines

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
                    lines.append(f"  v{version} → base pool: {op_list}")
            else:
                new_ops = current_ops - prev_ops
                if new_ops:
                    for op in sorted(new_ops):
                        # Try to find promotion info from experiment_events
                        promo_info = self._get_promotion_info(conn, op)
                        if promo_info:
                            lines.append(f"  v{version} → added {op} ({promo_info})")
                        else:
                            lines.append(f"  v{version} → added {op}")
                else:
                    lines.append(f"  v{version} → (weight optimization only)")

            if current_ops:
                prev_ops = current_ops

        return lines

    def _get_promotion_info(self, conn: sqlite3.Connection, operator_name: str) -> str:
        """Get round number and screening wr for a promoted operator."""
        try:
            row = conn.execute("""
                SELECT e.screening_win_rate,
                       (SELECT COUNT(*) FROM experiment_events e2
                        WHERE e2.branch_id = e.branch_id
                        AND e2.event_kind = 'experiment') AS round_count
                FROM experiment_events e
                WHERE e.event_kind = 'experiment'
                  AND e.decision = 'promote'
                  AND (e.patch_file LIKE ? OR e.patch_file LIKE ?)
                ORDER BY e.created_at DESC LIMIT 1
            """, (f"%{operator_name}%", f"%{operator_name}%")).fetchone()
            if row and row['screening_win_rate'] is not None:
                return f"R{row['round_count']}, scr={row['screening_win_rate']:.2f}"
        except Exception:
            pass
        return ""

    def _build_weight_feedback(self, conn: sqlite3.Connection) -> List[str]:
        """Build weight feedback from latest weight_optimizations record."""
        lines = []
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
                annotation = "← 低贡献"
            lines.append(f"  {name}: {w:.2f} {annotation}")

        return lines

    def _build_full_trajectory(self, conn: sqlite3.Connection) -> List[BranchTrajectory]:
        """Build full trajectory for all branches from experiment_events."""
        try:
            rows = conn.execute("""
                SELECT e.branch_id,
                       e.stage,
                       e.screening_win_rate,
                       e.decision,
                       COALESCE(e.patch_file, h.target_file) AS resolved_file,
                       e.hypothesis_text
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

            # Hypothesis text (up to 200 chars)
            hyp_text = ''
            for s in steps:
                if s['hyp']:
                    hyp_text = (s['hyp'] or '')[:200]
                    break

            # Build stages list
            stage_list = []
            for s in steps:
                stage_list.append({
                    'stage': s['stage'],
                    'wr': s['wr'],
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

    # Legacy compat
    def build(self) -> List[BranchTrajectory]:
        """Build branch trajectories from SQLite."""
        if not os.path.exists(self._db_path):
            return []
        try:
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            result = self._build_full_trajectory(conn)
            conn.close()
            return result
        except Exception:
            return []
