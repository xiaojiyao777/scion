"""ContextManager — builds LLM input contexts with exposure control (§5.3)."""
from __future__ import annotations

import os
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

from scion.core.models import (
    Branch,
    ChampionState,
    Decision,
    ExperimentStage,
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

    def __init__(self, *, adapter=None):
        self._adapter = adapter

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
        problem_summary = _build_problem_summary(problem_spec, adapter=self._adapter)
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
        strategy_guidance = _build_strategy_guidance(families, problem_spec) if families else ""

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

        # Objective policy/guidance is generic: lexicographic protection or
        # weighted-sum scalar improvement, plus recent screening tendencies.
        adapter_spec = _get_adapter_problem_spec(self._adapter)
        objective_policy_guidance = _build_objective_policy_guidance(adapter_spec)
        objective_feedback = _build_recent_objective_feedback(
            step_history or [], branch.branch_id, adapter_spec
        )
        objective_opportunity_profile = _build_objective_opportunity_profile(
            step_history or [], adapter_spec
        )
        objective_guidance = _build_objective_guidance(
            saturation_signals, objective_feedback=objective_feedback
        )
        search_control_guidance = _build_search_control_guidance(
            families, step_history or [], adapter_spec
        )

        # W10: Weight optimization feedback (coarse-grained operator signals)
        weight_opt_block = ""
        if weight_opt_result is not None:
            from scion.proposal.weight_feedback import render_weight_feedback
            weight_opt_block = render_weight_feedback(weight_opt_result)

        # J-patch: Render research log (cross-branch trajectory)
        research_log_block = ""
        if research_log is not None:
            research_log_block = research_log.render()

        return {
            "problem_summary": problem_summary,
            "branch_id": branch.branch_id,
            "champion_version": champion.version,
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
            "objective_policy_guidance": objective_policy_guidance,
            "objective_opportunity_profile": objective_opportunity_profile,
            "objective_guidance": objective_guidance,
            "search_control_guidance": search_control_guidance,
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
        problem_summary = _build_problem_summary(problem_spec, adapter=self._adapter)
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
        operator_interface_spec = _build_operator_interface_spec(problem_spec, adapter=self._adapter)
        import_whitelist = "\n".join(
            f"  - {imp}" for imp in problem_spec.search_space.import_whitelist
        )

        ctx: Dict[str, Any] = {
            "problem_summary": problem_summary,
            "branch_id": branch.branch_id,
            "champion_version": champion.version,
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
        problem_summary = _build_problem_summary(problem_spec, adapter=self._adapter)
        failed_checks = [c for c in verification_result.checks if not c.passed]
        failure_detail = (
            f"Severity: {verification_result.failure_severity or 'unknown'}\n"
            f"First failure: {verification_result.first_failure or 'N/A'}\n"
            "Details:\n"
            + "\n".join(
                f"  [{c.name}] ({c.severity}) {c.detail}" for c in failed_checks
            )
        ) or "No detail available."

        operator_interface_spec = _build_operator_interface_spec(problem_spec, adapter=self._adapter)
        import_whitelist = "\n".join(
            f"  - {imp}" for imp in problem_spec.search_space.import_whitelist
        )

        failure_pattern_warning = _build_failure_pattern_warning(failure_streak or {})

        ctx = {
            "problem_summary": problem_summary,
            "branch_id": branch.branch_id,
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

def _build_objective_guidance(saturation_signals, *, objective_feedback: str = "") -> str:
    """Build tendency-based objective guidance from signals and recent feedback."""
    lines = []
    if objective_feedback:
        lines.append(objective_feedback)
    if not saturation_signals:
        return "\n\n".join(lines)
    signal_lines = []
    for s in saturation_signals:
        if getattr(s, "at_absolute_minimum", False):
            signal_lines.append(
                f"- {s.objective}: at or near its theoretical minimum. "
                f"Further direct improvement on this dimension is unlikely. "
                f"Search can target other objectives when this objective is preserved."
            )
        elif s.saturation_level == "high":
            pct = int(s.improvement_ratio * 100)
            signal_lines.append(
                f"- {s.objective}: improvement has reached high saturation ({pct}% from baseline). "
                f"Exploring other objectives is valuable when {s.objective} is stable."
            )
        elif s.saturation_level == "low":
            signal_lines.append(
                f"- {s.objective}: has significant room for improvement. "
                f"This is a promising search direction."
            )
    if signal_lines:
        lines.append("\n## Objective Improvement Guidance\n" + "\n".join(signal_lines))
    return "\n\n".join(lines)


def _get_adapter_problem_spec(adapter) -> Any:
    """Return optional ProblemSpecV1 exposed by an adapter."""
    if adapter is None:
        return None
    spec = getattr(adapter, "spec", None)
    if spec is not None:
        return spec
    return getattr(adapter, "_spec", None)


def _build_objective_policy_guidance(adapter_spec: Any) -> str:
    """Render generic objective semantics for hypothesis generation."""
    if adapter_spec is None:
        return ""

    objectives = list(getattr(adapter_spec, "objectives", []) or [])
    policy = getattr(adapter_spec, "objective_policy", None)
    mode = getattr(policy, "mode", "lexicographic")
    ordered = sorted(objectives, key=lambda s: getattr(s, "priority", 0))
    if not ordered:
        return ""

    lines = ["## Objective Policy"]
    if mode == "weighted_sum":
        lines.append(
            "Evaluation uses a single weighted aggregate objective. Any positive "
            "weighted-score improvement is valuable, regardless of which component "
            "created the gain."
        )
        if getattr(policy, "expose_weights_to_llm", False):
            lines.append("Component weights exposed for marginal-value guidance:")
            for obj in ordered:
                lines.append(
                    f"- {obj.name}: direction={obj.direction}, "
                    f"weight={getattr(obj, 'weight', None)}, "
                    f"tie_tolerance={obj.tie_tolerance}"
                )
        else:
            lines.append(
                "Component weights are hidden by policy; reason about measurable "
                "aggregate improvement without assuming unlisted weights."
            )
        lines.append(
            "A good hypothesis should state which component(s) it improves and why "
            "the weighted aggregate should improve."
        )
    elif mode == "single":
        obj = ordered[0]
        lines.append(
            f"Evaluation has one decision objective: {obj.name} "
            f"({obj.direction}, tie_tolerance={obj.tie_tolerance}). "
            "Any measurable improvement on this objective is valuable."
        )
    else:
        lines.append(
            "Evaluation is lexicographic by priority. A lower-priority gain is "
            "valuable when all higher-priority objectives are preserved within "
            "their tie tolerances."
        )
        for obj in ordered:
            lines.append(
                f"- priority {obj.priority}: {obj.name} "
                f"({obj.direction}, tie_tolerance={obj.tie_tolerance})"
            )
        lines.append(
            "A good hypothesis may target any objective, but must explicitly name "
            "the higher-priority objectives it protects and its no-op condition "
            "when that protection cannot be maintained."
        )
    return "\n".join(lines)


def _build_recent_objective_feedback(
    step_history: List[StepRecord],
    branch_id: str,
    adapter_spec: Any,
) -> str:
    """Summarize recent screening objective tendencies without exposing holdouts."""
    branch_steps = [
        s for s in step_history
        if s.branch_id == branch_id
        and s.protocol_result is not None
        and s.protocol_result.stage == ExperimentStage.SCREENING
    ]
    if not branch_steps:
        return ""

    ordered_names = [
        obj.name for obj in sorted(
            list(getattr(adapter_spec, "objectives", []) or []),
            key=lambda s: getattr(s, "priority", 0),
        )
    ]
    last = branch_steps[-1].protocol_result
    feedback = list(last.case_feedback or ())
    if not feedback:
        return ""

    lines = ["## Recent Objective Feedback"]
    lines.append(
        f"Last screening outcome={last.gate_outcome}, "
        f"win_rate={last.stats.win_rate:.2f}, "
        f"median_delta={last.stats.median_delta:.4f}."
    )

    names = ordered_names or sorted({
        name for cf in feedback for name in getattr(cf, "median_deltas", {}).keys()
    })
    for name in names:
        vals = [
            float(cf.median_deltas[name])
            for cf in feedback
            if getattr(cf, "median_deltas", None) and name in cf.median_deltas
        ]
        if not vals:
            continue
        pos = sum(1 for v in vals if v > 0)
        neg = sum(1 for v in vals if v < 0)
        tie = len(vals) - pos - neg
        med = sorted(vals)[len(vals) // 2]
        lines.append(
            f"- {name}: positive_cases={pos}, negative_cases={neg}, "
            f"tie_cases={tie}, median_case_delta={med:+.4f}"
        )

    lines.append(
        "Use this as a tendency signal only: propose mechanisms that preserve "
        "objectives already stable and address the weakest measurable component."
    )
    return "\n".join(lines)


def _build_objective_opportunity_profile(
    step_history: List[StepRecord],
    adapter_spec: Any,
) -> str:
    """Aggregate recent screening signals across branches for objective guidance."""
    screening_steps = [
        s for s in step_history
        if s.protocol_result is not None
        and s.protocol_result.stage == ExperimentStage.SCREENING
    ][-12:]
    if not screening_steps:
        return ""

    objective_specs = sorted(
        list(getattr(adapter_spec, "objectives", []) or []),
        key=lambda s: getattr(s, "priority", 0),
    )
    policy = getattr(adapter_spec, "objective_policy", None)
    mode = getattr(policy, "mode", "lexicographic")
    expose_weights = bool(getattr(policy, "expose_weights_to_llm", False))
    spec_by_name = {obj.name: obj for obj in objective_specs}

    values_by_metric: dict[str, list[float]] = {}
    decisive_wins: Counter[str] = Counter()
    decisive_losses: Counter[str] = Counter()
    gate_counts: Counter[str] = Counter()
    target_counts: Counter[str] = Counter()

    for step in screening_steps:
        pr = step.protocol_result
        gate_counts[pr.gate_outcome] += 1
        for obj in getattr(step.hypothesis, "target_objectives", ()) or ():
            target_counts[obj] += 1
        if pr.pattern_summary is not None:
            decisive_wins.update(pr.pattern_summary.wins_by_decisive_objective)
            decisive_losses.update(pr.pattern_summary.losses_by_decisive_objective)
        for cf in pr.case_feedback or ():
            for name, val in (cf.median_deltas or {}).items():
                values_by_metric.setdefault(name, []).append(float(val))

    ordered_names = [obj.name for obj in objective_specs] or sorted(values_by_metric)
    if mode == "weighted_sum" and "weighted_sum" in values_by_metric:
        ordered_names = ["weighted_sum"] + [n for n in ordered_names if n != "weighted_sum"]

    lines = ["## Objective Opportunity Profile (screening only)"]
    lines.append(
        "Recent screening gates: "
        + ", ".join(f"{k}={v}" for k, v in sorted(gate_counts.items()))
    )
    for name in ordered_names:
        vals = values_by_metric.get(name, [])
        if not vals:
            continue
        pos = sum(1 for v in vals if v > 0)
        neg = sum(1 for v in vals if v < 0)
        tie = len(vals) - pos - neg
        med = _median(vals)
        spec = spec_by_name.get(name)
        descriptor = ""
        if spec is not None:
            descriptor = f" priority={spec.priority}"
            if mode == "weighted_sum" and expose_weights:
                descriptor += f" weight={spec.weight}"
        lines.append(
            f"- {name}:{descriptor} positive_cases={pos} "
            f"negative_cases={neg} tie_cases={tie} "
            f"median_case_delta={med:+.4f} "
            f"decisive_wins={decisive_wins.get(name, 0)} "
            f"decisive_losses={decisive_losses.get(name, 0)} "
            f"targeted_recently={target_counts.get(name, 0)}"
        )

    if not values_by_metric:
        return ""
    lines.append(
        "Interpretation: positive deltas are observed marginal gains; negative "
        "deltas identify protected objectives or mechanisms that need no-op guards. "
        "Use this profile to balance exploiting proven signals with exploring "
        "under-tested objective/locus combinations."
    )
    return "\n".join(lines)


def _build_search_control_guidance(
    families: List[HypothesisFamily],
    step_history: List[StepRecord],
    adapter_spec: Any,
) -> str:
    """Render generic exploration/exploitation guidance from campaign evidence."""
    recent_screening = [
        s for s in step_history[-12:]
        if s.protocol_result is not None
        and s.protocol_result.stage == ExperimentStage.SCREENING
    ]
    if not recent_screening and not families:
        return ""

    policy = getattr(adapter_spec, "objective_policy", None)
    mode = getattr(policy, "mode", "lexicographic")
    recent_pass_or_expand = sum(
        1 for s in recent_screening
        if s.protocol_result.gate_outcome in ("pass", "expand")
    )
    recent_fail = sum(
        1 for s in recent_screening
        if s.protocol_result.gate_outcome == "fail"
    )
    repeated_fail_families = [
        fam.family_id for fam in families
        if _count_trailing_failures(fam.statuses) >= 2
    ][:4]

    lines = ["## Exploration / Exploitation Control"]
    if recent_pass_or_expand:
        lines.append(
            f"- Exploit: {recent_pass_or_expand} recent screening attempt(s) "
            "were pass/expand. Prefer refinements that keep the same proven "
            "mechanism but add tighter feasibility and protected-objective guards."
        )
    if recent_fail:
        lines.append(
            f"- Explore: {recent_fail} recent screening attempt(s) failed. "
            "Avoid repeating the same mechanism without a new capability, target "
            "condition, or objective tradeoff policy."
        )
    if repeated_fail_families:
        lines.append(
            "- Avoid saturated failure families: "
            + ", ".join(repeated_fail_families)
        )
    if mode == "weighted_sum":
        lines.append(
            "- Weighted objective: exploit high-weight components when they offer "
            "large aggregate gain; explore lower-weight components only when the "
            "weighted aggregate still improves."
        )
    elif mode == "single":
        lines.append(
            "- Single objective: exploration should create a genuinely new move "
            "type; exploitation should make the best observed move more reliable."
        )
    else:
        lines.append(
            "- Lexicographic objective: exploit high-priority gains when available. "
            "When higher-priority objectives are tied or saturated, explore "
            "lower-priority gains with explicit higher-priority protection."
        )
    return "\n".join(lines)


def _median(values: List[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2 == 0:
        return (ordered[mid - 1] + ordered[mid]) / 2.0
    return ordered[mid]


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


def _build_problem_summary(spec: ProblemSpec, *, adapter=None) -> str:
    """Build a structured summary of the problem specification.

    Delegates to adapter.render_problem_summary() when an adapter is available.
    Falls back to a generic minimal summary for legacy ProblemSpec without adapter.
    """
    if adapter is not None and hasattr(adapter, 'render_problem_summary'):
        return adapter.render_problem_summary()
    # Legacy fallback: generic summary from ProblemSpec fields only
    lines = [f"Name: {spec.name}"]
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

    # Build directional description using generic metric deltas
    metric = cf.decisive_metric if hasattr(cf, 'decisive_metric') else getattr(cf, 'dominant_decisive_objective', 'tie')
    deltas = cf.median_deltas if hasattr(cf, 'median_deltas') and cf.median_deltas else {}

    delta_parts = []
    for name, val in sorted(deltas.items()):
        direction = "↓" if val > 0 else "↑"
        delta_parts.append(f"{name} {direction}{abs(val):.1f} (Δ={val:+.1f})")

    if delta_parts:
        decisive_str = f"Decisive: {metric} — " + ", ".join(delta_parts)
    else:
        decisive_str = f"Decisive: {metric}"

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
        # Boost cases where decisive metric is the highest-priority objective
        dm = c.decisive_metric if hasattr(c, 'decisive_metric') else ""
        if dm and dm != "tie":
            score += 2
        bucket = c.case_features.get("size_bucket", "unknown")
        if bucket not in seen_sizes:
            score += 2
            seen_sizes.add(bucket)
        # Use largest absolute median delta across all metrics
        deltas = c.median_deltas if hasattr(c, 'median_deltas') and c.median_deltas else {}
        max_delta = max((abs(v) for v in deltas.values()), default=0)
        score += min(max_delta / 100, 3)
        scored.append((score, c))
    scored.sort(key=lambda x: -x[0])
    return [c for _, c in scored[:max_cases]]


_VERIFICATION_SUGGESTIONS: dict = {
    "V6_feasibility": (
        "检查 operator_interface_spec 中定义的可行性约束，确保输出满足问题适配器的 feasibility oracle。"
    ),
    "V5_solution_consistency": (
        "检查 operator_interface_spec 中定义的解结构一致性约束，确保 solver 输出可被问题适配器正确反序列化和校验。"
    ),
    "V8_nondeterminism": (
        "同 seed 两次 solver run 产出了不同的 objective。常见非确定性来源："
        "(1) 禁止使用 uuid.uuid4() 或系统熵；"
        "(2) 禁止 list(set(...)) 或遍历 set/dict 时依赖顺序，必须 sorted()；"
        "(3) 所有随机性必须来自 operator execute 的 rng 参数；"
        "(4) 避免依赖文件系统、时间、全局状态或未排序容器顺序"
    ),
    "V2_interface": (
        "确保类和 execute 方法签名严格符合 operator_interface_spec。"
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
        # Extract V-code prefix like V6_feasibility
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


def _extract_mechanism_label(hypothesis_text: str, taxonomy: Optional[list] = None) -> str:
    """Extract mechanism label from hypothesis text using keyword matching."""
    text_lower = hypothesis_text.lower()
    if taxonomy:
        for label in taxonomy:
            if label.lower() in text_lower:
                return label
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


def _build_strategy_guidance(families: List[HypothesisFamily], spec: Optional[ProblemSpec] = None) -> str:
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
    all_loci = (
        set(spec.operator_categories)
        if spec and hasattr(spec, 'operator_categories') and spec.operator_categories
        else set()
    )
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

    # Aggregate champion metrics per case from pair_feedback
    from collections import defaultdict as _defaultdict
    case_champ_metrics: dict = _defaultdict(lambda: _defaultdict(list))
    for pair in last_with_pairs.protocol_result.pair_feedback:
        oc = getattr(pair, 'objective_comparison', None)
        if oc and hasattr(oc, 'metrics') and oc.metrics:
            for m in oc.metrics:
                case_champ_metrics[pair.case_id][m.name].append(m.champion_value)

    if not case_champ_metrics:
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
    for case_id, metrics in sorted(case_champ_metrics.items()):
        parts = []
        for metric_name, vals in sorted(metrics.items()):
            avg = sum(vals) / len(vals)
            parts.append(f"{metric_name}={avg:.1f}")
        lines.append(f"- {case_id}: {', '.join(parts)}")

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
    if hypothesis.target_objectives:
        lines.append(f"target_objectives: {', '.join(hypothesis.target_objectives)}")
    if hypothesis.protected_objectives:
        lines.append(f"protected_objectives: {', '.join(hypothesis.protected_objectives)}")
    if hypothesis.objective_tradeoff_policy:
        lines.append(f"objective_tradeoff_policy: {hypothesis.objective_tradeoff_policy}")
    if hypothesis.no_op_condition:
        lines.append(f"no_op_condition: {hypothesis.no_op_condition}")
    if hypothesis.risk_to_higher_priority:
        lines.append(f"risk_to_higher_priority: {hypothesis.risk_to_higher_priority}")
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


def _build_operator_interface_spec(spec: ProblemSpec, *, adapter=None) -> str:
    """Build the operator interface specification.

    Delegates to adapter.render_operator_interface() when an adapter is available.
    Falls back to reading operators/base.py for legacy ProblemSpec without adapter.
    """
    if adapter is not None and hasattr(adapter, 'render_operator_interface'):
        return adapter.render_operator_interface()
    # Legacy fallback: read base.py only
    base_py_path = os.path.join(spec.root_dir, "operators", "base.py")
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
    return f"### Operator Base Class (from operators/base.py)\n```python\n{base_class_src}\n```"
