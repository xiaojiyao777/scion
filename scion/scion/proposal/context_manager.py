"""ContextManager — builds LLM input contexts with exposure control (§5.3)."""
from __future__ import annotations

import os
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

from scion.core.models import (
    Branch,
    ChampionState,
    Decision,
    HypothesisFamily,
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
        failure_streak: Optional[Dict[str, int]] = None,
        forced_locus: Optional[str] = None,
        search_memory: Optional[Any] = None,
        saturation_signals: Optional[List[Any]] = None,
        weight_opt_result: Optional[Any] = None,
        research_log: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Context for generate_hypothesis (Round 1).

        Includes full problem summary, champion operator code, branch experiment
        history, and blacklist. Deliberately excludes validation/frozen data.

        If branch_workspace is provided and differs from the champion snapshot,
        branch_code shows the modified operators so the LLM can build on them.

        If failure_streak is provided, injects a failure pattern warning when
        any failure code has a streak >= 2.
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
        branch_direction = _build_branch_direction_prompt(branch)

        # T07: Build family tracking and coverage (J-patch: use global step_history)
        all_steps = step_history or []
        families = _extract_families_from_steps(all_steps)
        exploration_coverage = build_exploration_coverage(families) if families else ""

        # T08: Build strategy guidance from family data (J-patch: global)
        strategy_guidance = _build_strategy_guidance(families) if families else ""

        # T10: Champion baseline hints from most recent screening experiment
        champion_baselines = _build_champion_baselines(step_history or [])

        # Sprint H2 T5: Failure pattern warning
        failure_pattern_warning = _build_failure_pattern_warning(failure_streak or {})

        # I3: Forced locus diversification constraint
        locus_constraint = ""
        if forced_locus:
            locus_constraint = (
                f"\n## MANDATORY SEARCH CONSTRAINT\n"
                f"Your hypothesis MUST target `{forced_locus}` operators.\n"
                f"The campaign has detected saturation in the current search direction.\n"
                f"Exploring `{forced_locus}` is required to find further improvements.\n"
            )

        # J1: Render search memory (cross-branch search history)
        search_memory_block = ""
        if search_memory is not None:
            search_memory_block = search_memory.render()

        # J2: Render saturation signals
        saturation_block = ""
        if saturation_signals:
            from scion.proposal.saturation import render_saturation_signals
            saturation_block = render_saturation_signals(saturation_signals)

        # J6: Weight optimization result feedback
        weight_opt_block = ""
        if weight_opt_result is not None and hasattr(weight_opt_result, 'best_weights'):
            lines = ["## 当前算子贡献估计（weight optimization 结果）"]
            sorted_weights = sorted(
                weight_opt_result.best_weights.items(),
                key=lambda x: -x[1],
            )
            for name, w in sorted_weights:
                if w >= 2.0:
                    level = "高贡献"
                elif w >= 0.5:
                    level = "中等贡献"
                else:
                    level = "低贡献"
                lines.append(f"  {name}: {level}（权重 {w:.2f}）")
            weight_opt_block = "\n".join(lines)

        # J-patch: Render research log (cross-branch trajectory)
        research_log_block = ""
        if research_log is not None:
            research_log_block = research_log.render()

        return {
            "problem_summary": problem_summary,
            "operator_categories": ", ".join(problem_spec.operator_categories),
            "champion_operators_code": champion_operators_code,
            "champion_stats": champion_stats,
            "experiment_history": experiment_history,
            "blacklist_summary": blacklist_summary,
            "sibling_summary": sibling_summary,
            "branch_code": branch_code,
            "branch_direction": branch_direction,
            "exploration_coverage": exploration_coverage,
            "strategy_guidance": strategy_guidance,
            "champion_baselines": champion_baselines,
            "failure_pattern_warning": failure_pattern_warning,
            "locus_constraint": locus_constraint,
            "search_memory": search_memory_block,
            "saturation_signal": saturation_block,
            "weight_opt_feedback": weight_opt_block,
            "research_log": research_log_block,
            "active_hyp_summary": _summarise_active_hypotheses(active_hypotheses),
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
        prior_failure: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Context for generate_code (Round 2).

        Contains problem summary, hypothesis details, target file content,
        operator interface spec, and import whitelist.
        Does NOT contain experiment stats or branch history.
        If prior_failure is set, a previous code generation attempt failed for
        this hypothesis — the failure detail is included so the LLM can learn.
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

        ctx: Dict[str, Any] = {
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
        if prior_failure is not None:
            ctx["prior_code_failure"] = prior_failure
        return ctx

    # ------------------------------------------------------------------
    # Fix context — after light verification failure
    # ------------------------------------------------------------------

    def build_fix_context(
        self,
        branch: Branch,
        patch: PatchProposal,
        verification_result: VerificationResult,
        problem_spec: ProblemSpec,
        failure_streak: Optional[Dict[str, int]] = None,
    ) -> Dict[str, Any]:
        """Context for fix_code (after a light verification failure).

        Contains the failed patch, failure details, and operator interface spec.
        Does NOT contain experiment stats.
        If failure_streak is provided, injects a failure pattern warning.
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

        failure_pattern_warning = _build_failure_pattern_warning(failure_streak or {})

        ctx = {
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
        if failure_pattern_warning:
            ctx["failure_pattern_warning"] = failure_pattern_warning
        return ctx


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _build_branch_direction_prompt(branch: Branch) -> Optional[str]:
    """Build branch direction guidance if a direction has been established."""
    if not branch.direction:
        return None
    return (
        f"## Branch Direction\n"
        f"This branch is exploring: {branch.direction}\n"
        f"Continue building on this direction. Propose improvements or refinements "
        f"to the current approach.\n"
        f"Only switch to a fundamentally different approach if the last 3+ screening "
        f"results show no progress."
    )


def _build_problem_summary(spec: ProblemSpec) -> str:
    """Build a structured summary of the problem specification."""
    lines = [
        f"Name: {spec.name}",
    ]
    if spec.description:
        lines.append(f"Description: {spec.description}")
    lines += [
        "",
        "### Objective Function (lexicographic — minimize all three in order):",
        "1. subcategory_splits: For each unique `vehicle_subcategory` value across all orders,",
        "   count how many distinct vehicles contain orders of that subcategory, subtract 1,",
        "   then sum. Formula: sum(len(vehicles_containing_subcat) - 1 for each subcategory)",
        "2. total_cost: sum(VEHICLE_TYPES[v.vehicle_type].cost for all non-empty vehicles)",
        "   Vehicle costs: T3=800, T5=1200, T10=1800, HQ40=3300, HQ40_DG=6600",
        "3. solve_time_ms: wall-clock time (external, not operator-controlled)",
        "",
        "Key implication: ANY increase in subcategory_splits makes the solution strictly worse,",
        "regardless of cost improvement. Cost only matters when splits are equal.",
        "",
        "### How the Initial Solution is Built (greedy_init)",
        "Orders are grouped by (vehicle_category, vehicle_subcategory, pickup_city).",
        "Within each group, orders are packed sequentially into vehicles using first-fit.",
        "When a vehicle reaches capacity (pallet limit), a new vehicle is opened for the same group.",
        "Subcategory splits occur when a subcategory group's total pallets exceed one vehicle's capacity.",
        "Example: if subcategory 3 has 50 pallets and HQ40 capacity is 40, it needs 2 vehicles -> 1 split.",
        "",
        "To reduce splits, an operator must consolidate orders so a subcategory fits in fewer vehicles.",
        "This typically means: merging two partially-filled vehicles of the SAME vehicle_subcategory,",
        "or moving orders between vehicles to free up space for same-subcategory consolidation.",
        "Random order moves between arbitrary vehicles are unlikely to improve splits.",
        "",
        "### Worked Example (Small Instance)",
        "Instance: 6 orders, 2 subcategories, all Shenzhen region",
        "  Orders: A1(subcat=1,8plt), A2(subcat=1,6plt), A3(subcat=1,10plt),",
        "          A4(subcat=1,12plt), B1(subcat=2,5plt), B2(subcat=2,4plt)",
        "  Vehicle types: T10(cap=14,cost=1800), HQ40(cap=40,cost=3300)",
        "",
        "Greedy init (groups by subcategory, first-fit):",
        "  V1[T10]: A1(8)+A2(6)=14plt -> full",
        "  V2[T10]: A3(10) -> 10plt (A4 won't fit: 10+12=22 > 14)",
        "  V3[T10]: A4(12) -> 12plt",
        "  V4[T10]: B1(5)+B2(4)=9plt",
        "  Objective: splits=2 (subcat 1 in V1,V2,V3 -> split=2; subcat 2 in V4 -> split=0)",
        "             cost=4*1800=7200",
        "",
        "Improved (merge subcat-1 vehicles into HQ40):",
        "  V1[HQ40]: A1+A2+A3+A4=36plt",
        "  V4[T10]: B1+B2=9plt",
        "  Objective: splits=0, cost=3300+1800=5100 -> BETTER on both objectives",
        "",
        "The key move: merging V2+V3 orders into V1 (upgrading to HQ40).",
        "This is what a good subcategory-consolidation operator should do.",
        "",
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

    T26: Includes "What Worked" section before "What Failed" to prevent
    the model from becoming overly conservative after many failures.

    Recent 3 rounds: aggregate + pattern + selected cases.
    Older rounds (4-8): aggregate only.
    Consecutive 3+ same-type verification failures → inject diagnosis block.
    """
    branch_steps = [s for s in step_history if s.branch_id == branch_id]
    if not branch_steps:
        return "(no prior experiment rounds on this branch)"

    # T26: Build "What Worked" section from promoted steps
    what_worked = _build_what_worked_section(branch_steps)

    recent = branch_steps[-8:]  # Last 8 rounds
    lines: List[str] = []
    n_recent = len(recent)

    # T26: Prepend "What Worked" if available
    if what_worked:
        lines.append(what_worked)

    for idx, s in enumerate(recent):
        is_detailed = idx >= max(0, n_recent - 3)  # Last 3 get case detail
        status = "FAILED" if s.failure_stage else s.decision.value.upper()
        line = f"  Round {s.round_num} [{status}]"
        line += f"  hypothesis: {s.hypothesis.change_locus}/{s.hypothesis.action}"
        if s.hypothesis.target_file:
            line += f" → {s.hypothesis.target_file}"
        line += f"\n    hypothesis_text: {s.hypothesis.hypothesis_text}"
        if s.failure_stage:
            line += f"\n    failed_at: {s.failure_stage}"
            if s.failure_stage == "verification" and s.verification_detail:
                # Use richer verification_detail for LLM diagnosis
                detail_str = s.verification_detail[:200]
                line += f" — {detail_str}"
            elif s.failure_detail:
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

    # Consecutive failure diagnosis injection
    diagnosis = _build_consecutive_failure_diagnosis(branch_steps)
    if diagnosis:
        lines.append(diagnosis)

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
    """Render a single CaseAggregateFeedback with directional language (T09)."""
    size = cf.case_features.get("size_bucket", "?")
    n_orders = cf.case_features.get("n_orders", "?")
    result_upper = cf.dominant_result.upper()

    # Build directional description for the decisive objective
    obj = cf.dominant_decisive_objective
    splits_delta = cf.median_delta_subcategory_splits  # positive = candidate better (fewer splits)
    cost_delta = cf.median_delta_total_cost            # positive = candidate better (lower cost)

    if obj in ("business_aggregation", "mixed") and splits_delta is not None:
        direction = "↓" if splits_delta > 0 else "↑"
        abs_splits = abs(splits_delta)
        decisive_str = f"Decisive: {obj} — candidate {direction}{abs_splits:.1f} splits (Δ={splits_delta:+.1f})"
        if cost_delta is not None:
            decisive_str += f", cost Δ={cost_delta:+.0f}"
    elif obj == "cost" and cost_delta is not None:
        direction = "↓" if cost_delta > 0 else "↑"
        abs_cost = abs(cost_delta)
        decisive_str = f"Decisive: {obj} — candidate cost {direction}{abs_cost:.0f} (Δ={cost_delta:+.0f})"
        if splits_delta is not None:
            decisive_str += f", splits Δ={splits_delta:+.1f}"
    else:
        # Fallback: show raw deltas
        splits_str = f"{splits_delta:+.1f}" if splits_delta is not None else "NA"
        cost_str = f"{cost_delta:+.0f}" if cost_delta is not None else "NA"
        decisive_str = f"Decisive: {obj}  splits Δ={splits_str}, cost Δ={cost_str}"

    # Champion baseline hint from case_features if available
    champ_splits = cf.case_features.get("champion_splits")
    baseline_note = ""
    if champ_splits is not None:
        baseline_note = f"\n        Champion baseline: ~{champ_splits} splits on this case"

    return (
        f"      {cf.case_id} ({n_orders} orders, size={size}): {result_upper}"
        f" (W/L/T={cf.wins}/{cf.losses}/{cf.ties}, consistency={cf.seed_consistency:.2f})"
        f"\n        {decisive_str}"
        f"{baseline_note}"
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


_VERIFICATION_SUGGESTIONS: dict = {
    "V3_feasibility": (
        "确保 assignment dict 和 vehicle.order_ids 完全一致，不丢失/重复任何订单，"
        "危险品必须在 HQ40_DG 车型"
    ),
    "V5_state_mutation": (
        "算子修改了输入 solution（state 污染）。"
        "确保先调用 solution.deep_copy() 再操作，不要引用原始 solution 的任何可变子对象（list、dict）。"
        "检查 assignment dict 和 vehicle.order_ids 是否一致。"
    ),
    "V8_nondeterminism": (
        "同 seed 两次 solver run 产出了不同的 objective。常见非确定性来源："
        "(1) 禁止使用 uuid.uuid4()，必须用 generate_vehicle_id(rng) 生成车辆 ID；"
        "(2) 禁止 list(set(...)) 或遍历 set/dict 时依赖顺序，必须 sorted()；"
        "(3) 所有随机性必须来自 rng 参数，不要 import random 或使用任何系统熵源；"
        "(4) 确保只修改 deep_copy 后的对象"
    ),
    "V2_interface": (
        "确保类继承 Operator 基类，且有 execute(self, solution, rng) -> Solution 方法"
    ),
    "V1_syntax": "检查 Python 语法是否正确",
}


def _build_consecutive_failure_diagnosis(branch_steps: List[StepRecord]) -> str:
    """Inject a diagnosis block when 3+ consecutive same-type verification failures occur."""
    if len(branch_steps) < 3:
        return ""
    # Walk backwards through all steps to find current consecutive-failure streak
    streak_steps = []
    for s in reversed(branch_steps):
        if s.failure_stage == "verification" and s.failure_detail:
            streak_steps.append(s)
        else:
            break
    if len(streak_steps) < 3:
        return ""

    # Determine dominant failure type from first_failure / failure_detail
    failure_types: List[str] = []
    details: List[str] = []
    for s in streak_steps:
        fd = s.failure_detail or ""
        # Extract V-code prefix like V3_feasibility
        vcode = fd.split(":")[0].strip() if ":" in fd else fd.split()[0] if fd else ""
        failure_types.append(vcode)
        if s.verification_detail:
            details.append(s.verification_detail[:150])
        elif fd:
            details.append(fd[:150])

    # Use the most common failure type
    dominant_type = Counter(failure_types).most_common(1)[0][0] if failure_types else ""
    suggestion = _VERIFICATION_SUGGESTIONS.get(dominant_type, "仔细检查验证失败的原因并修改代码")
    aggregated = " | ".join(dict.fromkeys(details))[:300]  # deduplicate, cap length

    return (
        f"\n## ⚠️ Consecutive Failure Diagnosis\n"
        f"The last {len(streak_steps)} attempts all failed at verification.\n"
        f"Common failure details: {aggregated}\n"
        f"Suggested approach: {suggestion}"
    )


# ---------------------------------------------------------------------------
# T07: Hypothesis Family Tracking
# ---------------------------------------------------------------------------

# Keyword → mechanism_label mapping (ordered by specificity)
_MECHANISM_KEYWORDS: List[Tuple[List[str], str]] = [
    (["destroy", "rebuild"], "destroy_rebuild"),
    (["subcategor", "consolidat", "merge"], "subcategory_consolidation"),
    (["swap"], "order_swap"),
    (["redistribute", "rebalance"], "rebalance"),
    (["split"], "split_operator"),
    (["cost", "downsize", "vehicle type", "upgrade"], "cost_reduction"),
]
_DEFAULT_MECHANISM = "generic"


def _extract_mechanism_label(hypothesis_text: str) -> str:
    """Extract mechanism label from hypothesis text using keyword matching."""
    text_lower = hypothesis_text.lower()
    for keywords, label in _MECHANISM_KEYWORDS:
        if any(kw in text_lower for kw in keywords):
            return label
    return _DEFAULT_MECHANISM


def _make_family_id(mechanism_label: str, action_pattern: str, locus_pattern: str) -> str:
    return f"{mechanism_label}/{action_pattern}/{locus_pattern}"


def _get_step_status(step: StepRecord) -> str:
    """Derive a compact status string from a StepRecord."""
    if step.failure_stage:
        return f"failed_{step.failure_stage}"
    if step.decision == Decision.PROMOTE:
        return "promoted"
    if step.protocol_result is not None:
        return f"gate_{step.protocol_result.gate_outcome}"
    return step.decision.value


def _extract_families_from_steps(steps: List[StepRecord]) -> List[HypothesisFamily]:
    """Build the family list from step history (rebuilt each call — no persistence needed)."""
    family_map: Dict[str, HypothesisFamily] = {}
    for step in steps:
        h = step.hypothesis
        mechanism = _extract_mechanism_label(h.hypothesis_text or "")
        family_id = _make_family_id(mechanism, h.action, h.change_locus)
        status = _get_step_status(step)
        if family_id in family_map:
            existing = family_map[family_id]
            family_map[family_id] = HypothesisFamily(
                family_id=existing.family_id,
                mechanism_label=existing.mechanism_label,
                action_pattern=existing.action_pattern,
                locus_pattern=existing.locus_pattern,
                evidence_count=existing.evidence_count + 1,
                statuses=existing.statuses + [status],
            )
        else:
            family_map[family_id] = HypothesisFamily(
                family_id=family_id,
                mechanism_label=mechanism,
                action_pattern=h.action,
                locus_pattern=h.change_locus,
                evidence_count=1,
                statuses=[status],
            )
    # Return in insertion order (order of first encounter)
    return list(family_map.values())


def assign_family_id(hypothesis_text: str, action: str, change_locus: str) -> str:
    """Public helper: compute family_id for a hypothesis (for HypothesisRecord.family_id)."""
    mechanism = _extract_mechanism_label(hypothesis_text)
    return _make_family_id(mechanism, action, change_locus)


def build_exploration_coverage(families: List[HypothesisFamily]) -> str:
    """Return a formatted string showing family coverage across attempts (T07)."""
    if not families:
        return ""
    lines = ["## Exploration Coverage"]
    for fam in families:
        promoted = sum(1 for s in fam.statuses if s == "promoted")
        failed = sum(1 for s in fam.statuses if s.startswith("failed_"))
        passed = sum(1 for s in fam.statuses if "pass" in s)
        status_summary = f"promoted={promoted} failed={failed} passed={passed}"
        lines.append(
            f"  {fam.family_id}: n={fam.evidence_count} [{status_summary}]"
        )
    # Show unexplored action/locus combos
    explored_actions = {f.action_pattern for f in families}
    all_actions = {"create_new", "modify", "remove"}
    unexplored_actions = all_actions - explored_actions
    if unexplored_actions:
        lines.append(f"  Unexplored actions: {sorted(unexplored_actions)}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# T08: Strategy-shift Guidance
# ---------------------------------------------------------------------------

def _count_trailing_failures(statuses: List[str]) -> int:
    """Count consecutive trailing failures in statuses list."""
    count = 0
    for s in reversed(statuses):
        if s.startswith("failed_") or "fail" in s:
            count += 1
        else:
            break
    return count


def _build_strategy_guidance(families: List[HypothesisFamily]) -> str:
    """Build strategy shift guidance when same mechanism fails repeatedly (T08)."""
    if not families:
        return ""
    guidance_parts: List[str] = []

    # Rule 1: Same family failed 3+ consecutive times → force switch
    for fam in families:
        consecutive_fails = _count_trailing_failures(fam.statuses)
        if consecutive_fails >= 3:
            guidance_parts.append(
                f"⚠️ Family '{fam.mechanism_label}' ({fam.action_pattern}/{fam.locus_pattern}) "
                f"has failed {consecutive_fails} consecutive times. AVOID this approach."
            )

    # Rule 2: All recent hypotheses same action → suggest alternative
    recent_actions = [f.action_pattern for f in families[-5:]]
    if len(set(recent_actions)) == 1 and len(recent_actions) >= 3:
        alt = "modify" if recent_actions[0] == "create_new" else "create_new"
        guidance_parts.append(
            f"Consider trying action='{alt}' — all recent attempts used '{recent_actions[0]}'."
        )

    # Rule 3: Unexplored locus → suggest
    explored_loci = {f.locus_pattern for f in families}
    all_loci = {"vehicle_level", "order_level"}
    unexplored = all_loci - explored_loci
    if unexplored:
        guidance_parts.append(
            f"Unexplored operator categories: {sorted(unexplored)}. Consider targeting these."
        )

    return "\n".join(guidance_parts)


def _build_failure_pattern_warning(failure_streak: Dict[str, int]) -> str:
    """Build a failure pattern warning string for the LLM context.

    Returns an empty string if no failure has a streak >= 2.
    """
    significant = {k: v for k, v in failure_streak.items() if v >= 2}
    if not significant:
        return ""

    lines = ["## Failure Pattern Warning"]
    for code, streak in sorted(significant.items(), key=lambda x: -x[1]):
        lines.append(
            f"This campaign has failed '{code}' {streak} consecutive time(s)."
        )
        # Provide category-specific hints
        if "verification" in code.lower():
            lines.append(
                "  Common causes: import errors, missing attributes, "
                "incorrect operator interface. Consider a fundamentally different approach."
            )
        elif code in ("proposal", "contract"):
            lines.append(
                "  Common causes: malformed JSON, schema violations. "
                "Double-check output format requirements."
            )
        elif code == "evaluation":
            lines.append(
                "  Common causes: solver crash, environment issues. "
                "Ensure operator code is robust and handles edge cases."
            )
    return "\n".join(lines)# ---------------------------------------------------------------------------
# T26: What Worked section for experiment history
# ---------------------------------------------------------------------------

def _build_what_worked_section(branch_steps: List[StepRecord]) -> str:
    """Build 'What Worked' section from promoted steps (T26).

    Storing confirmations prevents the model from becoming overly conservative
    after seeing many failures (CC analysis #12).
    """
    promoted_steps = [
        s for s in branch_steps
        if s.decision == Decision.PROMOTE
    ]
    high_wr_steps = [
        s for s in branch_steps
        if (
            s.protocol_result is not None
            and s.protocol_result.stats.win_rate >= 0.8
            and s.decision != Decision.PROMOTE
        )
    ]
    successes = promoted_steps + high_wr_steps
    if not successes:
        return ""

    lines = ["## What Worked (learn from these)"]
    for s in successes[:5]:  # Cap at 5 to avoid bloating context
        h = s.hypothesis
        mechanism = _extract_mechanism_label(h.hypothesis_text or "")
        tag = "(promoted)" if s.decision == Decision.PROMOTE else "(high win_rate)"
        wr_str = ""
        if s.protocol_result:
            wr_str = f", wr={s.protocol_result.stats.win_rate:.2f}"
        lines.append(
            f"- {mechanism} ({h.change_locus}/{h.action}) {tag}{wr_str}: "
            f"{(h.hypothesis_text or '')[:100]}"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# T10: Champion Baseline Hints
# ---------------------------------------------------------------------------

def _build_champion_baselines(step_history: List[StepRecord]) -> str:
    """Build champion baseline section from most recent screening experiment (T10).

    Extracts per-case champion objective values from the last screening step's
    pair_feedback. If no experiment data exists, returns empty string.
    """
    # Find most recent step with pair_feedback (screening results)
    last_with_pairs = None
    for step in reversed(step_history):
        if (
            step.protocol_result is not None
            and step.protocol_result.pair_feedback
        ):
            last_with_pairs = step
            break

    if last_with_pairs is None:
        return ""

    # Aggregate champion splits per case from pair_feedback
    from collections import defaultdict as _defaultdict
    case_champ_splits: dict = _defaultdict(list)
    for pair in last_with_pairs.protocol_result.pair_feedback:
        ob = pair.objective_breakdown
        if ob.champion_subcategory_splits is not None:
            case_champ_splits[pair.case_id].append(ob.champion_subcategory_splits)

    if not case_champ_splits:
        # Fallback: use case_feedback if available but no per-pair breakdown
        if last_with_pairs.protocol_result.case_feedback:
            lines = ["## Champion Performance (screening cases)"]
            for cf in last_with_pairs.protocol_result.case_feedback[:8]:
                n_orders = cf.case_features.get("n_orders", "?")
                size = cf.case_features.get("size_bucket", "?")
                lines.append(f"- {cf.case_id} ({n_orders} orders, {size}): champion baseline not available in aggregate")
            return "\n".join(lines)
        return ""

    lines = ["## Champion Performance (screening cases)"]
    for case_id, champ_vals in sorted(case_champ_splits.items()):
        min_val = min(champ_vals)
        max_val = max(champ_vals)
        if min_val == max_val:
            splits_str = f"~{min_val:.0f} splits"
        else:
            splits_str = f"~{min_val:.0f}-{max_val:.0f} splits"
        avg = sum(champ_vals) / len(champ_vals)
        if avg <= 2:
            note = "— splits already near optimal"
        elif avg <= 10:
            note = "— some room to improve"
        else:
            note = "— significant room on splits"
        lines.append(f"- {case_id}: {splits_str} {note}")

    return "\n".join(lines)


def _summarise_active_hypotheses(active_hypotheses: List[HypothesisRecord]) -> str:
    """Summarise currently active hypotheses so the LLM avoids proposing duplicates."""
    if not active_hypotheses:
        return "(none)"
    lines = []
    for h in active_hypotheses:
        key_str = f"{h.change_locus}/{h.action}"
        if h.target_file:
            key_str += f" → {h.target_file}"
        lines.append(f"  - {key_str}  [OCCUPIED — C10 will reject any duplicate]")
    return "\n".join(lines)


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
- `Order` (complete field list — use these EXACT attribute names):
  - `order_id: str` — unique identifier
  - `vehicle_category: int` — large category (feasibility H4: same vehicle must have same category)
  - `vehicle_subcategory: int` — sub-category (**PRIMARY optimization target**: minimize splits of this across vehicles)
  - `urgent: bool` — urgency flag
  - `hazard_flag: bool` — True if order contains hazardous goods
  - `hazard_quantity: int` — hazardous goods quantity in pcs (>1800 requires HQ40_DG)
  - `pickup_name: str` — pickup point name (constraint H3: max pickups per vehicle per region)
  - `pickup_city: str` — "Dongguan" or "Shenzhen" (constraint H2: same region per vehicle)
  - `declaration_amount: float` — customs declaration amount (constraint H6)
  - `lsp: str` — logistics service provider
  - `ship_method: str` — shipping method (H6 grouping key with destination_country)
  - `destination_country: str` — destination country (H6 grouping key with ship_method)
  - `spu_list: list[SPU]` — packing units; use `calc_pallets(order.spu_list)` from models.py
  - `locked_vehicle_id: Optional[str]` — None = freely assignable; non-None = MUST stay in that vehicle
- `Instance`: accessed via `self.instance` (set in __init__); contains `orders: dict[str, Order]`, `amount_limits: dict[str, float]`
- Helper: `select_minimum_vehicle_type(total_pallets, total_hazard) -> str` from models.py
- Helper: `get_max_pickups(region) -> int` from models.py (Dongguan=2, Shenzhen=3)

### Critical Constraints
1. **Deep copy first**: always call `new_sol = solution.deep_copy()` before any modification
2. **Locked orders**: never move orders where `order.locked_vehicle_id is not None`
3. **rng**: use `rng` (a `random.Random` instance) for all randomness — do NOT import `random` directly
4. **Determinism**: NEVER use `uuid.uuid4()` or any system entropy source. Generate vehicle IDs with `generate_vehicle_id(rng)` from `operators.base`. NEVER use `list(set(...))` or iterate over `set`/`dict` in an order-dependent way. Use `sorted()` when you need a stable order from sets or dict keys/values. The solver runs twice with the same seed to verify determinism — any non-deterministic output causes rejection.
5. **Return value**: return the modified solution (or the original if no valid move was found)
6. **Imports**: only use modules from the import whitelist; no external packages

### Feasibility Constraints (MUST NOT violate — will cause immediate rejection)
7. **Every order assigned**: every order in the instance MUST appear in exactly one vehicle's order_ids AND in the assignment dict. Never drop or duplicate orders.
8. **Consistency**: `solution.assignment[order_id] == vehicle_id` must match `order_id in vehicle.order_ids` for ALL orders. After any modification, update BOTH.
9. **Vehicle capacity**: total pallets in a vehicle must not exceed its type's capacity
10. **Hazardous goods**: orders with `hazard_flag=True` and total hazard_quantity > 1800 MUST be in HQ40_DG
11. **No empty vehicles**: after modifications, call `new_sol.remove_empty_vehicles()` to clean up
12. **Same region**: all orders in a vehicle must have the same `pickup_city` region
13. **Same category**: all orders in a vehicle must have the same `vehicle_category`
14. **Pickup limit**: number of distinct `pickup_name` values in a vehicle must not exceed `get_max_pickups(region)`\
"""
