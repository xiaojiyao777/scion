"""Hypothesis, objective, and strategy guidance helpers."""
from __future__ import annotations

from collections import Counter
from typing import Any, List, Optional

from scion.config.problem import ProblemSpec
from scion.core.models import (
    ExperimentStage,
    HypothesisFamily,
    HypothesisRecord,
    StepRecord,
)
from scion.proposal.context.feedback import (
    _filter_hypothesis_prompt_steps,
    _first_line,
)
from scion.proposal.context.surfaces import (
    _build_forced_surface_novelty_guidance,
    _find_research_surface,
    _solver_design_surface_names,
)

from .history import _count_trailing_failures

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

def _get_family_taxonomy(spec: Any) -> Any | None:
    taxonomy = getattr(spec, "family_taxonomy", None)
    families = getattr(taxonomy, "families", taxonomy)
    if not families:
        return None
    return taxonomy

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
        f"case_win_rate={last.stats.win_rate:.2f}, "
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
    objective_stats: dict[str, dict[str, float]] = {}
    for name in ordered_names:
        vals = values_by_metric.get(name, [])
        if not vals:
            continue
        pos = sum(1 for v in vals if v > 0)
        neg = sum(1 for v in vals if v < 0)
        tie = len(vals) - pos - neg
        med = _median(vals)
        objective_stats[name] = {
            "n": float(len(vals)),
            "pos": float(pos),
            "neg": float(neg),
            "tie": float(tie),
            "median": float(med),
            "decisive_wins": float(decisive_wins.get(name, 0)),
            "decisive_losses": float(decisive_losses.get(name, 0)),
            "targeted_recently": float(target_counts.get(name, 0)),
        }
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
    steering = _build_objective_steering(
        objective_specs=objective_specs,
        objective_stats=objective_stats,
        mode=mode,
    )
    if steering:
        lines.append(steering)
    lines.append(
        "Interpretation: positive deltas are observed marginal gains; negative "
        "deltas identify protected objectives or mechanisms that need no-op guards. "
        "Use this profile to balance exploiting proven signals with exploring "
        "under-tested objective/locus combinations."
    )
    return "\n".join(lines)

def _build_objective_steering(
    *,
    objective_specs: List[Any],
    objective_stats: dict[str, dict[str, float]],
    mode: str,
) -> str:
    """Render generic target/protect guidance from observed marginal movement."""
    if not objective_specs:
        return ""

    if mode == "lexicographic":
        protected: list[str] = []
        recommended = ""
        for obj in objective_specs:
            stats = objective_stats.get(obj.name)
            if not stats:
                continue
            n = max(stats.get("n", 0.0), 1.0)
            moved = (
                stats.get("pos", 0.0)
                + stats.get("neg", 0.0)
                + stats.get("decisive_wins", 0.0)
                + stats.get("decisive_losses", 0.0)
            )
            tie_ratio = stats.get("tie", 0.0) / n
            is_stable = tie_ratio >= 0.8 and moved == 0.0
            if is_stable:
                protected.append(obj.name)
                continue
            if protected:
                recommended = obj.name
                break
            recommended = obj.name
            break
        if protected and recommended:
            return (
                "Objective Steering: recent screening suggests "
                f"{', '.join(protected)} is acting like a protected/stable "
                f"higher-priority dimension. Prefer hypotheses targeting "
                f"{recommended} while preserving {', '.join(protected)}; avoid "
                "more direct protected-objective mechanisms unless they introduce "
                "a genuinely new capability."
            )

    if mode == "weighted_sum":
        weighted = objective_stats.get("weighted_sum")
        if weighted and weighted.get("n", 0.0) > 0:
            return (
                "Objective Steering: optimize the weighted aggregate directly. "
                "A component-level change is valuable only when it improves the "
                "aggregate score after tradeoffs."
            )

    return ""

def _build_search_control_guidance(
    families: List[HypothesisFamily],
    step_history: List[StepRecord],
    adapter_spec: Any,
    *,
    forced_surface: Optional[str] = None,
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
    recent_winless_solver_design = [
        s
        for s in recent_screening[-4:]
        if s.protocol_result.gate_outcome == "fail"
        and (s.protocol_result.stats.win_rate or 0.0) <= 0.0
        and str(s.protocol_result.selected_surface or "") == "solver_design"
    ]
    repeated_fail_families = [
        fam.family_id for fam in families
        if _count_trailing_failures(fam.statuses) >= 2
        and not (forced_surface and fam.locus_pattern == forced_surface)
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
    if len(recent_winless_solver_design) >= 2:
        target_counts = Counter(
            str(s.hypothesis.target_file or "").strip()
            for s in recent_winless_solver_design
            if str(s.hypothesis.target_file or "").strip()
        )
        lines.append(
            "- Solver-design plateau: recent full-algorithm candidates reached "
            "screening with case_win_rate=0. Do not submit another shallow scheduler "
            "variant, budget tweak, or post-processing polish. The next hypothesis "
            "must name the failed mechanism pattern, explain why the new algorithm "
            "body is materially different, and either modify the stable algorithm "
            "entrypoint or include explicit scheduler/entrypoint integration for "
            "any helper-module changes."
        )
        if target_counts:
            common_targets = ", ".join(
                f"{target} x{count}"
                for target, count in target_counts.most_common(3)
            )
            lines.append(
                "- Solver-design target diversity: recent winless target files "
                f"were {common_targets}. If the failed pattern is scheduler-only, "
                "target a concrete mechanism module such as construction.py, "
                "destroy_repair.py, local_search.py, or acceptance.py, and use "
                "scheduler/entrypoint edits only as integration wiring."
            )
    if forced_surface:
        lines.append(
            "- Forced-surface diagnostic: keep exploration on "
            f"{forced_surface}; use evidence to vary the mechanism within that surface."
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

def _build_strategy_guidance(
    families: List[HypothesisFamily],
    spec: Optional[ProblemSpec] = None,
    *,
    available_actions: Optional[set[str]] = None,
    forced_surface: Optional[str] = None,
    forced_action: Optional[str] = None,
    active_problem_boundary_surfaces: Optional[List[str]] = None,
) -> str:
    """Build strategy shift guidance when same mechanism fails repeatedly (T08)."""
    if not families:
        return ""
    allowed_actions = available_actions or {"create_new", "modify", "remove"}
    active_boundaries = {
        str(surface).strip()
        for surface in (active_problem_boundary_surfaces or [])
        if str(surface).strip()
    }
    guidance_parts: List[str] = []

    # Rule 1: Same family failed 3+ consecutive times → force switch
    for fam in families:
        consecutive_fails = _count_trailing_failures(fam.statuses)
        if consecutive_fails >= 3:
            if forced_surface and fam.locus_pattern == forced_surface:
                guidance_parts.append(
                    f"Family '{fam.mechanism_label}' on forced surface "
                    f"'{forced_surface}' has failed {consecutive_fails} "
                    "consecutive times. Keep the forced surface/action/target, "
                    "but use a distinct mechanism or runtime-evidence diagnosis."
                )
            elif fam.locus_pattern in active_boundaries:
                guidance_parts.append(
                    f"Family '{fam.mechanism_label}' on active problem boundary "
                    f"'{fam.locus_pattern}' has failed {consecutive_fails} "
                    "consecutive times. Keep the problem boundary, but abandon "
                    "the failed mechanism pattern and propose a materially "
                    "different full-algorithm body."
                )
            else:
                guidance_parts.append(
                    f"⚠️ Family '{fam.mechanism_label}' "
                    f"({fam.action_pattern}/{fam.locus_pattern}) has failed "
                    f"{consecutive_fails} consecutive times. AVOID this approach."
                )

    # Rule 2: All recent hypotheses same action → suggest alternative
    recent_actions = [f.action_pattern for f in families[-5:]]
    if (
        not forced_action
        and len(set(recent_actions)) == 1
        and len(recent_actions) >= 3
    ):
        alt = "modify" if recent_actions[0] == "create_new" else "create_new"
        if alt in allowed_actions:
            guidance_parts.append(
                f"Consider trying action='{alt}' — all recent attempts used '{recent_actions[0]}'."
            )
        elif recent_actions[0] == "create_new":
            guidance_parts.append(
                "Do not force an action switch to modify/remove yet: no champion "
                "operator file is available as a removable target. Continue create_new "
                "or modify a declared singleton policy file when one exists, but "
                "change the mechanism, locus, or objective tradeoff policy."
            )

    # Rule 3: Unexplored locus → suggest
    explored_loci = {f.locus_pattern for f in families}
    all_loci = (
        set(spec.operator_categories)
        if spec and hasattr(spec, 'operator_categories') and spec.operator_categories
        else set()
    )
    unexplored = all_loci - explored_loci
    if unexplored and active_boundaries and not forced_surface:
        guidance_parts.append(
            "Active problem-boundary control is in force: do not switch the "
            "top-level research target to unexplored component surfaces. Use "
            f"{sorted(active_boundaries)} as the research surface and treat "
            "component policies only as implementation hooks or attribution "
            "evidence."
        )
    elif unexplored and not forced_surface:
        guidance_parts.append(
            f"Unexplored research surfaces: {sorted(unexplored)}. Consider targeting these."
        )
    elif forced_surface:
        guidance_parts.append(
            "Forced-surface diagnostic is active: keep the hypothesis on "
            f"research surface '{forced_surface}' and vary only in-surface "
            "mechanism details."
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
    return "\n".join(lines)

def _build_solver_design_boundary_guidance(
    steps: List[StepRecord],
    *,
    research_surfaces: List[Any],
    blacklist: List[HypothesisRecord],
    rejected_hypotheses: List[HypothesisRecord],
) -> str:
    solver_design_names = _solver_design_surface_names(research_surfaces)
    if not solver_design_names:
        return ""
    failed_solver_design_steps = [
        step
        for step in _filter_hypothesis_prompt_steps(steps)
        if (
            step.hypothesis.change_locus in solver_design_names
            and step.failure_stage in {"verification", "patch_contract", "workspace"}
        )
    ]
    blacklisted_solver_design = [
        item.change_locus
        for item in blacklist
        if item.change_locus in solver_design_names
    ]
    rejected_solver_design = [
        item.change_locus
        for item in rejected_hypotheses
        if item.change_locus in solver_design_names
    ]
    names = ", ".join(solver_design_names)
    lines = [
        "## Solver-Design Boundary Control",
        (
            "The declared solver-design surface is the problem-level research "
            f"boundary: {names}."
        ),
    ]
    if failed_solver_design_steps:
        latest = failed_solver_design_steps[-1]
        detail = latest.verification_detail or latest.failure_detail or "pre-protocol failure"
        lines.append(
            "A prior solver-design candidate failed before screening "
            f"(round {latest.round_num}, stage={latest.failure_stage}, "
            f"detail={_first_line(detail)})."
        )
    if blacklisted_solver_design:
        lines.append(
            "If a solver-design entry appears in the global blacklist, treat "
            "that as a failed candidate implementation, not as evidence that "
            "the solver-design boundary is retired."
        )
    elif rejected_solver_design:
        lines.append(
            "Rejected solver-design entries are candidate implementations only; "
            "they do not retire the solver-design boundary."
        )
    if failed_solver_design_steps or blacklisted_solver_design or rejected_solver_design:
        lines.append(
            "For the next hypothesis, retry the solver-design boundary with a "
            "materially different full-algorithm implementation. Do not treat "
            "isolated component policies as replacement research goals."
        )
    else:
        lines.append(
            "For the next hypothesis, use the solver-design boundary for the "
            "problem-level algorithm body. Do not express the research target "
            "as an isolated component policy."
        )
    lines.append(
        "Component policies may be used as implementation hooks or attribution "
        "evidence, but they are not replacement research goals for this diagnostic."
    )
    blocking_hypotheses = [*(blacklist or []), *(rejected_hypotheses or [])]
    for surface_name in solver_design_names:
        surface = _find_research_surface(research_surfaces, surface_name)
        lines.extend(
            _build_forced_surface_novelty_guidance(
                surface=surface,
                surface_name=surface_name,
                blocking_hypotheses=blocking_hypotheses,
            )
        )
    return "\n".join(lines)

