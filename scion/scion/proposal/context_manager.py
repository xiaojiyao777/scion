"""ContextManager — builds LLM input contexts with exposure control (§5.3)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from scion.core.models import (
    Branch,
    ChampionState,
    HypothesisProposal,
    HypothesisRecord,
    PatchProposal,
    VerificationResult,
)
from scion.config.problem import ProblemSpec


class ContextManager:
    """Constructs context dicts for CreativeLayer calls.

    Exposure-control matrix (§5.3):
    ┌─────────────────────────┬─────────────────────────────────────────┐
    │ Context type            │ Excluded fields                         │
    ├─────────────────────────┼─────────────────────────────────────────┤
    │ hypothesis_context      │ validation/frozen results, raw metrics  │
    │ code_context            │ screening/validation/frozen stats       │
    │ fix_context             │ screening/validation/frozen stats       │
    └─────────────────────────┴─────────────────────────────────────────┘
    """

    # ------------------------------------------------------------------
    # Round 1 — hypothesis context
    # ------------------------------------------------------------------

    def build_hypothesis_context(
        self,
        branch: Branch,
        champion: ChampionState,
        problem_spec: ProblemSpec,
        active_hypotheses: List[HypothesisRecord],
        blacklist: List[HypothesisRecord],
        sibling_branches: Optional[List[Branch]] = None,
    ) -> Dict[str, Any]:
        """Context for generate_hypothesis (Round 1).

        Deliberately excludes validation / frozen experiment data.
        """
        pool_summary = _summarise_pool(champion.operator_pool)
        branch_history = _summarise_hypothesis_history(active_hypotheses, branch.branch_id)
        blacklist_summary = _summarise_blacklist(blacklist)
        sibling_summary = _summarise_siblings(sibling_branches or [])

        return {
            "problem_name": problem_spec.name,
            "operator_categories": ", ".join(problem_spec.operator_categories),
            "pool_summary": pool_summary,
            "branch_history": branch_history,
            "blacklist_summary": blacklist_summary,
            "sibling_summary": sibling_summary,
        }

    # ------------------------------------------------------------------
    # Round 2 — code context
    # ------------------------------------------------------------------

    def build_code_context(
        self,
        branch: Branch,
        hypothesis: HypothesisProposal,
        champion: ChampionState,
        problem_spec: ProblemSpec,
    ) -> Dict[str, Any]:
        """Context for generate_code (Round 2).

        Contains hypothesis details and champion code reference.
        Does NOT contain any experimental stats.
        """
        return {
            "problem_name": problem_spec.name,
            "editable_patterns": ", ".join(problem_spec.search_space.editable),
            "frozen_patterns": ", ".join(problem_spec.search_space.frozen),
            "import_whitelist": ", ".join(problem_spec.search_space.import_whitelist),
            "hypothesis_text": hypothesis.hypothesis_text,
            "change_locus": hypothesis.change_locus,
            "action": hypothesis.action,
            "target_file": hypothesis.target_file or "N/A",
            "champion_code": _summarise_champion_code(champion, hypothesis),
        }

    # ------------------------------------------------------------------
    # Fix context — after light verification failure
    # ------------------------------------------------------------------

    def build_fix_context(
        self,
        branch: Branch,
        patch: PatchProposal,
        verification_result: VerificationResult,
        problem_spec: ProblemSpec,
    ) -> Dict[str, Any]:
        """Context for fix_code (after a light verification failure).

        Contains the failed patch and detailed failure information.
        Does NOT contain experimental stats.
        """
        failed_checks = [c for c in verification_result.checks if not c.passed]
        failure_details = "\n".join(
            f"  [{c.name}] ({c.severity}) {c.detail}" for c in failed_checks
        )

        return {
            "problem_name": problem_spec.name,
            "editable_patterns": ", ".join(problem_spec.search_space.editable),
            "frozen_patterns": ", ".join(problem_spec.search_space.frozen),
            "import_whitelist": ", ".join(problem_spec.search_space.import_whitelist),
            "file_path": patch.file_path,
            "action": patch.action,
            "code_content": patch.code_content,
            "failure_severity": verification_result.failure_severity or "unknown",
            "first_failure": verification_result.first_failure or "N/A",
            "failure_details": failure_details or "No detail available.",
        }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _summarise_pool(pool: Dict[str, Any]) -> str:
    if not pool:
        return "(empty pool)"
    lines = []
    for name, op in pool.items():
        w = getattr(op, "weight", "?")
        cat = getattr(op, "category", "?")
        fp = getattr(op, "file_path", "?")
        lines.append(f"  - {name} [{cat}] weight={w} file={fp}")
    return "\n".join(lines)


def _summarise_hypothesis_history(
    hypotheses: List[HypothesisRecord], branch_id: str
) -> str:
    branch_hyps = [h for h in hypotheses if h.branch_id == branch_id]
    if not branch_hyps:
        return "(no prior hypotheses on this branch)"
    lines = []
    for h in branch_hyps[-5:]:  # Last 5
        lines.append(
            f"  - [{h.status}] {h.change_locus}/{h.action}"
            + (f" → {h.target_file}" if h.target_file else "")
        )
    return "\n".join(lines)


def _summarise_blacklist(blacklist: List[HypothesisRecord]) -> str:
    if not blacklist:
        return "(none)"
    lines = []
    for h in blacklist[:10]:  # Cap at 10
        lines.append(f"  - {h.change_locus}/{h.action}" + (f" → {h.target_file}" if h.target_file else ""))
    return "\n".join(lines)


def _summarise_siblings(siblings: List[Branch]) -> str:
    if not siblings:
        return "(no active sibling branches)"
    return f"  {len(siblings)} sibling branch(es) currently active."


def _summarise_champion_code(champion: ChampionState, hypothesis: HypothesisProposal) -> str:
    """Return a brief summary of the relevant champion code."""
    import os
    target = hypothesis.target_file
    if target and champion.code_snapshot_path:
        candidate = os.path.join(champion.code_snapshot_path, target.lstrip("/"))
        try:
            with open(candidate) as f:
                content = f.read()
            # Truncate if too long
            if len(content) > 3000:
                content = content[:3000] + "\n... [truncated]"
            return f"File: {target}\n```python\n{content}\n```"
        except OSError:
            pass
    return f"(champion code for '{target}' not readable)"
