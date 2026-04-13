"""CampaignResearchLog — cross-branch experimental trajectory for LLM context (J1-patch)."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import List, Optional
import os
import sqlite3


@dataclass
class BranchSummary:
    branch_id_short: str
    operator_name: str          # file_path basename
    hypothesis_snippet: str     # first 80 chars of hypothesis_text
    screening_wr: Optional[float]
    validation_wr: Optional[float]  # None if not reached
    frozen_passed: Optional[bool]   # True/False/None; never expose frozen wr or md
    outcome: str                # "promoted" | "abandoned_frozen" | "abandoned_validation" | "abandoned_screening"


class CampaignResearchLog:
    """Reads from SQLite experiment_events to build a cross-branch research log.

    Exposure rules:
    - Screening results: full (wr + median_delta)
    - Validation results: aggregate wr only (no per-case)
    - Frozen results: pass/fail only (NO wr, NO median_delta)
    """

    def __init__(self, campaign_dir: str) -> None:
        self._db_path = os.path.join(campaign_dir, "scion.db")

    def build(self) -> List[BranchSummary]:
        """Build branch summaries from SQLite. Returns most recent 30 branches."""
        if not os.path.exists(self._db_path):
            return []
        try:
            conn = sqlite3.connect(self._db_path)
            result = self._query_branches(conn)
            conn.close()
            return result
        except Exception:
            return []

    def _query_branches(self, conn: sqlite3.Connection) -> List[BranchSummary]:
        rows = conn.execute("""
            SELECT branch_id,
                   stage,
                   screening_win_rate,
                   decision,
                   patch_file,
                   hypothesis_text
            FROM experiment_events
            WHERE event_kind = 'experiment'
            ORDER BY branch_id, created_at
        """).fetchall()

        branch_data: dict = defaultdict(list)
        for r in rows:
            branch_data[r[0]].append({
                'stage': r[1], 'wr': r[2],
                'decision': r[3], 'file': r[4], 'hyp': r[5],
            })

        summaries = []
        for bid, steps in branch_data.items():
            scr = next((s for s in steps if s['stage'] == 'screening'), None)
            val = next((s for s in steps if s['stage'] == 'validation'), None)
            fro = next((s for s in steps if s['stage'] == 'frozen'), None)
            final = steps[-1]

            op_name = ''
            for s in steps:
                if s['file']:
                    op_name = s['file'].split('/')[-1].replace('.py', '')
                    break

            hyp_snippet = ''
            for s in steps:
                if s['hyp']:
                    hyp_snippet = (s['hyp'] or '')[:80]
                    break

            # Determine outcome
            if final['decision'] == 'promote':
                outcome = 'promoted'
            elif fro is not None and final['decision'] == 'abandon':
                outcome = 'abandoned_frozen'
            elif val is not None and final['decision'] == 'abandon':
                outcome = 'abandoned_validation'
            else:
                outcome = 'abandoned_screening'

            # Frozen: only pass/fail, never wr or md
            frozen_passed = None
            if fro is not None:
                frozen_passed = (final['decision'] == 'promote')

            summaries.append(BranchSummary(
                branch_id_short=bid[:8],
                operator_name=op_name,
                hypothesis_snippet=hyp_snippet,
                screening_wr=scr['wr'] if scr else None,
                validation_wr=val['wr'] if val else None,
                frozen_passed=frozen_passed,
                outcome=outcome,
            ))

        return summaries[-30:]  # cap at 30 most recent branches

    def render(self, available_tokens: Optional[int] = None) -> str:
        """Render cross-branch research log for LLM injection."""
        summaries = self.build()
        if not summaries:
            return ""

        promoted = [s for s in summaries if s.outcome == 'promoted']
        failed_frozen = [s for s in summaries if s.outcome == 'abandoned_frozen']
        failed_val = [s for s in summaries if s.outcome == 'abandoned_validation']
        failed_scr = [s for s in summaries if s.outcome == 'abandoned_screening']

        lines = ["## Campaign Research Log\n"]

        if promoted:
            lines.append("### Promoted Branches")
            for s in promoted:
                path = f"scr={s.screening_wr:.2f}" if s.screening_wr is not None else "scr=?"
                if s.validation_wr is not None:
                    path += f" \u2192 val={s.validation_wr:.2f}"
                path += " \u2192 frozen=PASS"
                lines.append(f"  [PROMOTED] {s.operator_name}: {path}")

        if failed_frozen:
            lines.append("\n### Reached Validation (not promoted)")
            for s in failed_frozen:
                path = f"scr={s.screening_wr:.2f}" if s.screening_wr is not None else ""
                if s.validation_wr is not None:
                    path += f" \u2192 val={s.validation_wr:.2f}"
                path += " \u2192 frozen=FAIL"
                lines.append(f"  [FAILED frozen] {s.operator_name}: {path}")
                lines.append(f"    \u21b3 Passed validation but failed frozen \u2014 approach may not generalise")

        if failed_val:
            lines.append("\n### Failed at Validation")
            for s in failed_val:
                path = f"scr={s.screening_wr:.2f}" if s.screening_wr is not None else ""
                if s.validation_wr is not None:
                    path += f" \u2192 val={s.validation_wr:.2f} (FAIL)"
                lines.append(f"  [FAILED val] {s.operator_name}: {path}")

        if failed_scr:
            lines.append(f"\n### Failed at Screening ({len(failed_scr)} branches)")
            entries = []
            for s in failed_scr:
                wr_str = f"wr={s.screening_wr:.2f}" if s.screening_wr is not None else "wr=?"
                name = s.operator_name or s.hypothesis_snippet[:40]
                entries.append(f"{name}({wr_str})")
            for i in range(0, len(entries), 3):
                lines.append("  " + " | ".join(entries[i:i + 3]))

            # Pattern analysis
            scr_wrs = [s.screening_wr for s in failed_scr if s.screening_wr is not None]
            if scr_wrs:
                max_scr = max(scr_wrs)
                if max_scr < 0.4:
                    lines.append(f"  \u2192 All screening failures: max_wr={max_scr:.2f} \u2014 these directions are exhausted")

        return "\n".join(lines)
