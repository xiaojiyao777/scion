"""ContextManager — builds LLM input contexts with exposure control (§5.3)."""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from scion.core.models import (
    Branch,
    ChampionState,
    HypothesisProposal,
    HypothesisRecord,
    PatchProposal,
    StepRecord,
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
    │ code_context            │ experiment stats, branch history        │
    │ fix_context             │ experiment stats, branch history        │
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
        step_history: Optional[List[StepRecord]] = None,
        branch_workspace: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Context for generate_hypothesis (Round 1).

        Includes full problem summary, champion operator code, branch experiment
        history, and blacklist. Deliberately excludes validation/frozen data.

        If branch_workspace is provided and differs from the champion snapshot,
        branch_code shows the modified operators so the LLM can build on them.
        """
        problem_summary = _build_problem_summary(problem_spec)
        champion_operators_code = _read_champion_operators(champion)
        experiment_history = _build_experiment_history(
            step_history or [], branch.branch_id
        )
        blacklist_summary = _summarise_blacklist(blacklist)
        sibling_summary = _summarise_siblings(sibling_branches or [])
        champion_stats = _build_champion_stats(champion)
        branch_code = (
            _read_branch_code(branch_workspace, champion)
            if branch_workspace
            else None
        )

        return {
            "problem_summary": problem_summary,
            "operator_categories": ", ".join(problem_spec.operator_categories),
            "champion_operators_code": champion_operators_code,
            "champion_stats": champion_stats,
            "experiment_history": experiment_history,
            "blacklist_summary": blacklist_summary,
            "sibling_summary": sibling_summary,
            "branch_code": branch_code,
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

        Contains problem summary, hypothesis details, target file content,
        operator interface spec, and import whitelist.
        Does NOT contain experiment stats or branch history.
        """
        problem_summary = _build_problem_summary(problem_spec)
        hypothesis_detail = _format_hypothesis(hypothesis)
        if hypothesis.action == "create_new":
            target_file_code = "(new file — will be created)"
        else:
            target_file_code = _read_target_file(champion, hypothesis.target_file)
        champion_operators_code = _read_champion_operators(champion)
        # Always provide reference operators as style/interface reference
        reference_operators = _read_reference_operators(
            champion, hypothesis.change_locus, problem_spec
        )
        operator_interface_spec = _build_operator_interface_spec(problem_spec)
        import_whitelist = "\n".join(
            f"  - {imp}" for imp in problem_spec.search_space.import_whitelist
        )

        return {
            "problem_summary": problem_summary,
            "hypothesis_detail": hypothesis_detail,
            "target_file_code": target_file_code,
            "champion_operators_code": champion_operators_code,
            "reference_operators": reference_operators,
            "operator_interface_spec": operator_interface_spec,
            "import_whitelist": import_whitelist,
            "editable_patterns": ", ".join(problem_spec.search_space.editable),
            "frozen_patterns": ", ".join(problem_spec.search_space.frozen),
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

        Contains the failed patch, failure details, and operator interface spec.
        Does NOT contain experiment stats.
        """
        problem_summary = _build_problem_summary(problem_spec)
        failed_checks = [c for c in verification_result.checks if not c.passed]
        failure_detail = (
            f"Severity: {verification_result.failure_severity or 'unknown'}\n"
            f"First failure: {verification_result.first_failure or 'N/A'}\n"
            "Details:\n"
            + "\n".join(
                f"  [{c.name}] ({c.severity}) {c.detail}" for c in failed_checks
            )
        ) or "No detail available."

        operator_interface_spec = _build_operator_interface_spec(problem_spec)
        import_whitelist = "\n".join(
            f"  - {imp}" for imp in problem_spec.search_space.import_whitelist
        )

        return {
            "problem_summary": problem_summary,
            "original_code": (
                f"File: {patch.file_path}\nAction: {patch.action}\n"
                f"```python\n{patch.code_content}\n```"
            ),
            "failure_detail": failure_detail,
            "operator_interface_spec": operator_interface_spec,
            "import_whitelist": import_whitelist,
            "editable_patterns": ", ".join(problem_spec.search_space.editable),
            "frozen_patterns": ", ".join(problem_spec.search_space.frozen),
        }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _build_problem_summary(spec: ProblemSpec) -> str:
    """Build a structured summary of the problem specification."""
    lines = [
        f"Name: {spec.name}",
    ]
    if spec.description:
        lines.append(f"Description: {spec.description}")
    lines += [
        f"Operator categories: {', '.join(spec.operator_categories)}",
        f"Editable files: {', '.join(spec.search_space.editable)}",
        f"Frozen files (do not modify): {', '.join(spec.search_space.frozen)}",
    ]
    return "\n".join(lines)


def _read_champion_operators(champion: ChampionState) -> str:
    """Read all operator .py files from the champion snapshot directory."""
    operators_dir = os.path.join(champion.code_snapshot_path, "operators")
    if not os.path.isdir(operators_dir):
        return "(operators directory not found at champion snapshot path)"

    sections: List[str] = []
    try:
        filenames = sorted(
            f for f in os.listdir(operators_dir)
            if f.endswith(".py") and f not in ("__init__.py", "base.py")
        )
    except OSError as exc:
        return f"(could not list operators directory: {exc})"

    for fname in filenames:
        fpath = os.path.join(operators_dir, fname)
        try:
            with open(fpath, encoding="utf-8") as fh:
                content = fh.read()
            sections.append(f"### operators/{fname}\n```python\n{content}\n```")
        except OSError as exc:
            sections.append(f"### operators/{fname}\n(unreadable: {exc})")

    return "\n\n".join(sections) if sections else "(no operator files found)"


def _build_champion_stats(champion: ChampionState) -> str:
    """Return champion version and pool summary."""
    lines = [f"Champion version: {champion.version}"]
    if champion.operator_pool:
        lines.append("Operator pool:")
        for name, op in champion.operator_pool.items():
            w = getattr(op, "weight", "?")
            cat = getattr(op, "category", "?")
            fp = getattr(op, "file_path", "?")
            lines.append(f"  - {name} [{cat}] weight={w}  file={fp}")
    else:
        lines.append("Operator pool: (not yet loaded from registry)")
    if champion.promoted_at:
        lines.append(f"Last promoted: {champion.promoted_at}")
    return "\n".join(lines)


def _build_experiment_history(
    step_history: List[StepRecord], branch_id: str
) -> str:
    """Build structured experiment history with case-level feedback.

    Recent 3 rounds: aggregate + pattern + selected cases.
    Older rounds (4-8): aggregate only.
    """
    branch_steps = [s for s in step_history if s.branch_id == branch_id]
    if not branch_steps:
        return "(no prior experiment rounds on this branch)"

    recent = branch_steps[-8:]  # Last 8 rounds
    lines: List[str] = []
    n_recent = len(recent)

    for idx, s in enumerate(recent):
        is_detailed = idx >= max(0, n_recent - 3)  # Last 3 get case detail
        status = "FAILED" if s.failure_stage else s.decision.value.upper()
        line = f"  Round {s.round_num} [{status}]"
        line += f"  hypothesis: {s.hypothesis.change_locus}/{s.hypothesis.action}"
        if s.hypothesis.target_file:
            line += f" → {s.hypothesis.target_file}"
        line += f"\n    hypothesis_text: {s.hypothesis.hypothesis_text[:120]}"
        if s.failure_stage:
            line += f"\n    failed_at: {s.failure_stage}"
            if s.failure_detail:
                line += f" — {s.failure_detail[:120]}"
        if s.protocol_result is not None:
            pr = s.protocol_result
            st = pr.stats
            line += (
                f"\n    screening: win_rate={st.win_rate:.2f}"
                f"  median_delta={st.median_delta:.4f}"
                f"  outcome={pr.gate_outcome}"
            )
            # Case-level feedback for recent rounds
            if is_detailed and pr.pattern_summary:
                line += "\n" + _render_pattern_summary(pr.pattern_summary)
            if is_detailed and pr.case_feedback:
                selected = _select_cases_for_prompt(pr.case_feedback, max_cases=4)
                for cf in selected:
                    line += "\n" + _render_case_feedback(cf)
        lines.append(line)

    return "\n".join(lines)


def _render_pattern_summary(pattern) -> str:
    """Render ScreeningPatternSummary as compact prompt text."""
    lines = [
        f"    pattern: cases={pattern.total_cases}"
        f" win={pattern.winning_cases} loss={pattern.losing_cases} mixed={pattern.mixed_cases}",
    ]
    if pattern.wins_by_decisive_objective:
        lines.append(f"      wins by objective: {pattern.wins_by_decisive_objective}")
    if pattern.losses_by_decisive_objective:
        lines.append(f"      losses by objective: {pattern.losses_by_decisive_objective}")
    if pattern.key_observations:
        for obs in pattern.key_observations:
            lines.append(f"      • {obs}")
    return "\n".join(lines)


def _render_case_feedback(cf) -> str:
    """Render a single CaseAggregateFeedback as compact prompt text."""
    splits_str = f"{cf.median_delta_subcategory_splits:+.1f}" if cf.median_delta_subcategory_splits is not None else "NA"
    cost_str = f"{cf.median_delta_total_cost:+.1f}" if cf.median_delta_total_cost is not None else "NA"
    size = cf.case_features.get("size_bucket", "?")
    return (
        f"      {cf.case_id}: {cf.dominant_result}"
        f" (W/L/T={cf.wins}/{cf.losses}/{cf.ties}, consistency={cf.seed_consistency:.2f})"
        f"\n        decisive={cf.dominant_decisive_objective}"
        f"  deltas: splits={splits_str}, cost={cost_str}"
        f"  size={size}"
    )


def _select_cases_for_prompt(cases, max_cases: int = 4) -> list:
    """Select most informative cases for prompt inclusion."""
    scored = []
    seen_sizes: set = set()
    for c in cases:
        score = 0.0
        if c.dominant_result == "loss":
            score += 5
        elif c.dominant_result == "win":
            score += 4
        elif c.dominant_result == "mixed":
            score += 4
        if c.seed_consistency >= 0.99:
            score += 2
        if c.dominant_decisive_objective == "business_aggregation":
            score += 2
        bucket = c.case_features.get("size_bucket", "unknown")
        if bucket not in seen_sizes:
            score += 2
            seen_sizes.add(bucket)
        score += min(abs(c.median_delta_total_cost or 0) / 100, 3)
        scored.append((score, c))
    scored.sort(key=lambda x: -x[0])
    return [c for _, c in scored[:max_cases]]


def _summarise_blacklist(blacklist: List[HypothesisRecord]) -> str:
    if not blacklist:
        return "(none)"
    lines = []
    for h in blacklist[:10]:  # Cap at 10
        lines.append(
            f"  - {h.change_locus}/{h.action}"
            + (f" → {h.target_file}" if h.target_file else "")
        )
    return "\n".join(lines)


def _summarise_siblings(siblings: List[Branch]) -> str:
    if not siblings:
        return "(no active sibling branches)"
    lines = []
    for b in siblings[:5]:
        lines.append(f"  - branch {b.branch_id[:8]} state={b.state.value}")
    return "\n".join(lines)


def _format_hypothesis(hypothesis: HypothesisProposal) -> str:
    """Format hypothesis fields for Round 2 prompt."""
    lines = [
        f"hypothesis_text: {hypothesis.hypothesis_text}",
        f"change_locus: {hypothesis.change_locus}",
        f"action: {hypothesis.action}",
        f"target_file: {hypothesis.target_file or 'N/A'}",
        f"predicted_direction: {hypothesis.predicted_direction}",
        f"target_weakness: {hypothesis.target_weakness}",
        f"expected_effect: {hypothesis.expected_effect}",
    ]
    if hypothesis.suggested_weight is not None:
        lines.append(f"suggested_weight: {hypothesis.suggested_weight}")
    return "\n".join(lines)


def _read_reference_operators(
    champion: ChampionState, change_locus: str, problem_spec: ProblemSpec
) -> str:
    """Read same-category operators as reference for create_new actions."""
    operators_dir = os.path.join(champion.code_snapshot_path, "operators")
    if not os.path.isdir(operators_dir):
        return ""

    # Map operator files to categories via pool config, or fall back to reading all
    sections: List[str] = []
    filenames = sorted(
        f for f in os.listdir(operators_dir)
        if f.endswith(".py") and f not in ("__init__.py", "base.py")
    )
    # Read up to 2 reference operators
    count = 0
    for fname in filenames:
        if count >= 2:
            break
        fpath = os.path.join(operators_dir, fname)
        try:
            with open(fpath, encoding="utf-8") as fh:
                content = fh.read()
            sections.append(f"### operators/{fname} (reference)\n```python\n{content}\n```")
            count += 1
        except OSError:
            pass
    return "\n\n".join(sections)


def _read_target_file(champion: ChampionState, target_file: Optional[str]) -> str:
    """Read the target file from the champion snapshot."""
    if not target_file or not champion.code_snapshot_path:
        return "(no target file specified)"
    candidate = os.path.join(champion.code_snapshot_path, target_file.lstrip("/"))
    try:
        with open(candidate, encoding="utf-8") as fh:
            content = fh.read()
        return f"File: {target_file}\n```python\n{content}\n```"
    except OSError as exc:
        return f"(could not read {target_file}: {exc})"


def _read_branch_code(branch_workspace: str, champion: ChampionState) -> Optional[str]:
    """Read branch operators that differ from champion, for Round 1 context (§4.9).

    Returns a formatted string showing the modified operator files, or None if
    no differences are found or the workspace is unavailable.
    """
    branch_ops_dir = os.path.join(branch_workspace, "operators")
    champ_ops_dir = os.path.join(champion.code_snapshot_path, "operators")

    if not os.path.isdir(branch_ops_dir):
        return None

    try:
        filenames = sorted(
            f for f in os.listdir(branch_ops_dir)
            if f.endswith(".py") and f not in ("__init__.py", "base.py")
        )
    except OSError:
        return None

    sections: List[str] = []
    for fname in filenames:
        branch_path = os.path.join(branch_ops_dir, fname)
        champ_path = os.path.join(champ_ops_dir, fname)

        try:
            with open(branch_path, encoding="utf-8") as fh:
                branch_content = fh.read()
        except OSError:
            continue

        try:
            with open(champ_path, encoding="utf-8") as fh:
                champ_content = fh.read()
        except OSError:
            champ_content = None

        if champ_content is None or branch_content != champ_content:
            sections.append(
                f"### operators/{fname} (branch version)\n```python\n{branch_content}\n```"
            )

    return "\n\n".join(sections) if sections else None


def _build_operator_interface_spec(spec: ProblemSpec) -> str:
    """Build the operator interface specification including base class and data models."""
    # Try to read base.py from the problem's root_dir
    base_py_path = os.path.join(spec.root_dir, "operators", "base.py")
    base_class_src = ""
    try:
        with open(base_py_path, encoding="utf-8") as fh:
            base_class_src = fh.read()
    except OSError:
        base_class_src = (
            "class Operator(ABC):\n"
            "    @abstractmethod\n"
            "    def execute(self, solution: Solution, rng: Random) -> Solution:\n"
            "        ..."
        )

    return f"""\
### Operator Base Class (from operators/base.py)
```python
{base_class_src}
```

### Key Data Structures (from models.py)
- `Solution`: contains `vehicles: dict[str, Vehicle]` and `assignment: dict[str, str]` (order_id → vehicle_id)
  - Call `solution.deep_copy()` to get a deep copy before modifying
  - `solution.remove_empty_vehicles()` to clean up empty vehicles in-place
- `Vehicle`: `vehicle_id`, `vehicle_type` (HQ40_DG|HQ40|T10|T5|T3), `region`, `order_ids: list[str]`
- `Order`: `order_id`, `locked_vehicle_id` (None = freely assignable), `hazard_flag`, `spu_list`, etc.
- `Instance`: passed as a frozen context; accessed via `solution.vehicles` / `solution.assignment`

### Critical Constraints
1. **Deep copy first**: always call `new_sol = solution.deep_copy()` before any modification
2. **Locked orders**: never move orders where `order.locked_vehicle_id is not None`
3. **rng**: use `rng` (a `random.Random` instance) for all randomness — do NOT import `random` directly
4. **Return value**: return the modified solution (or the original if no valid move was found)
5. **Imports**: only use modules from the import whitelist; no external packages

### Feasibility Constraints (MUST NOT violate — will cause immediate rejection)
6. **Every order assigned**: every order in the instance MUST appear in exactly one vehicle's order_ids AND in the assignment dict. Never drop or duplicate orders.
7. **Consistency**: `solution.assignment[order_id] == vehicle_id` must match `order_id in vehicle.order_ids` for ALL orders. After any modification, update BOTH.
8. **Vehicle capacity**: respect vehicle type constraints (use existing patterns from champion operators)
9. **Hazardous goods**: orders with `hazard_flag=True` MUST be in a vehicle with `vehicle_type='HQ40_DG'`
10. **No empty vehicles**: after modifications, call `new_sol.remove_empty_vehicles()` to clean up\
"""
