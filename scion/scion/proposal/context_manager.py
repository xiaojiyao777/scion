"""ContextManager — builds LLM input contexts with exposure control (§5.3)."""
from __future__ import annotations

import ast
import os
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

from scion.core.models import (
    Branch,
    ChampionState,
    ExperimentStage,
    HypothesisFamily,
    HypothesisProposal,
    HypothesisRecord,
    PatchProposal,
    StepRecord,
    VerificationResult,
    mechanism_change_dicts,
)
from scion.config.problem import ProblemSpec
from scion.core.forced_surface import (
    surface_target_files,
    validate_forced_surface_request,
)
from scion.proposal.context_builders.feedback_memory import (
    _build_agent_quality_feedback,
    _build_champion_baselines,
    _build_consecutive_failure_diagnosis,
    _build_experiment_history,
    _build_what_worked_section,
    _filter_hypothesis_prompt_steps,
    _first_line,
    _is_safe_pre_protocol_failure_step,
    _render_case_feedback,
)
from scion.proposal.context_builders.problem_adapter import (
    _build_operator_interface_spec,
    _build_problem_object,
    _build_problem_summary,
    _build_solver_mechanics,
    _get_adapter_problem_spec,
)
from scion.proposal.context_builders.research_surfaces import (
    _build_forced_surface_constraint,
    _build_forced_surface_novelty_guidance,
    _build_inactive_surface_exclusion_block,
    _build_research_surface_interface_spec,
    _build_research_surfaces_block,
    _coerce_text_list,
    _find_research_surface,
    _get_research_surfaces,
    _hypothesis_visible_research_surfaces,
    _include_operator_files_for_research_code,
    _is_solver_design_context_surface,
    _solver_design_surface_names,
    _surface_file_targets,
    _surface_target_files_for_names,
)
from scion.proposal.mechanism_labels import extract_mechanism_label


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

    def __init__(self, *, adapter=None, runtime_slow_threshold: float = 2.0):
        self._adapter = adapter
        self._runtime_slow_threshold = runtime_slow_threshold

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
        forced_action: Optional[str] = None,
        forced_target_file: Optional[str] = None,
        forced_surface_diagnostic: bool = False,
        rejected_hypotheses: Optional[List[HypothesisRecord]] = None,
        search_memory: Optional[Any] = None,
        saturation_signals: Optional[List[Any]] = None,
        weight_opt_result: Optional[Any] = None,
        research_log: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Context for generate_hypothesis (Round 1).

        Includes full problem summary, champion research code, branch experiment
        history, and blacklist. Deliberately excludes validation/frozen data.

        If branch_workspace is provided and differs from the champion snapshot,
        branch_code shows the modified research-surface files so the LLM can
        build on them.

        If failure_streak is provided, injects a failure pattern warning when
        any failure code has a streak >= 2.
        """
        problem_summary = _build_problem_summary(problem_spec, adapter=self._adapter)
        problem_object = _build_problem_object(adapter=self._adapter)
        solver_mechanics = _build_solver_mechanics(adapter=self._adapter)
        adapter_spec = _get_adapter_problem_spec(self._adapter)
        research_surfaces = _get_research_surfaces(problem_spec, adapter_spec)
        forced_request = (
            validate_forced_surface_request(
                problem_spec,
                forced_locus,
                action=forced_action,
                target_file=forced_target_file,
                adapter_spec=adapter_spec,
            )
            if forced_locus
            else None
        )
        declared_problem_boundary_surfaces = _solver_design_surface_names(
            research_surfaces
        )
        active_problem_boundary_surfaces = (
            []
            if forced_request is not None
            else declared_problem_boundary_surfaces
        )
        visible_research_surfaces = _hypothesis_visible_research_surfaces(
            research_surfaces,
            forced_surface=forced_request.surface if forced_request else None,
            active_problem_boundary_surfaces=active_problem_boundary_surfaces,
        )
        research_surfaces_block = _build_research_surfaces_block(
            visible_research_surfaces
        )
        legacy_surface_exclusion = _build_inactive_surface_exclusion_block(
            research_surfaces,
            visible_research_surfaces=visible_research_surfaces,
            active_problem_boundary_surfaces=active_problem_boundary_surfaces,
        )
        if legacy_surface_exclusion:
            research_surfaces_block = "\n".join(
                block
                for block in (research_surfaces_block, legacy_surface_exclusion)
                if block
            )
        champion_operators_code = _read_champion_research_code(
            champion,
            research_surfaces=visible_research_surfaces,
            include_operator_files=_include_operator_files_for_research_code(
                visible_research_surfaces
            ),
        )
        family_taxonomy = (
            _get_family_taxonomy(problem_spec)
            or _get_family_taxonomy(adapter_spec)
        )
        safe_hypothesis_steps = _filter_hypothesis_prompt_steps(step_history or [])
        experiment_history = _build_experiment_history(
            safe_hypothesis_steps, branch.branch_id, taxonomy=family_taxonomy
        )
        blacklist_summary = _summarise_blacklist(blacklist)
        solver_design_boundary_guidance = _build_solver_design_boundary_guidance(
            safe_hypothesis_steps,
            research_surfaces=research_surfaces,
            blacklist=blacklist,
            rejected_hypotheses=rejected_hypotheses or [],
        )
        sibling_summary = _summarise_siblings(sibling_branches or [])
        champion_stats = _build_champion_stats(champion)
        branch_code = (
            _read_branch_code(
                branch_workspace,
                champion,
                research_surfaces=visible_research_surfaces,
                include_operator_files=_include_operator_files_for_research_code(
                    visible_research_surfaces
                ),
            )
            if branch_workspace
            else None
        )
        branch_direction = _build_branch_direction_prompt(branch)

        # T07: Build family tracking and coverage (J-patch: use global step_history)
        all_steps = safe_hypothesis_steps
        targetable_operator_files = _list_champion_operator_files(champion)
        targetable_surface_files = _list_champion_surface_files(
            champion,
            research_surfaces=research_surfaces,
        )
        active_boundary_declared_target_files = _surface_target_files_for_names(
            research_surfaces,
            active_problem_boundary_surfaces,
        )
        active_boundary_target_files = _expand_surface_targets_for_champion(
            champion,
            active_boundary_declared_target_files,
        )
        effective_operator_categories = (
            active_problem_boundary_surfaces
            if active_problem_boundary_surfaces
            else list(problem_spec.operator_categories)
        )
        effective_targetable_files = (
            active_boundary_target_files
            if active_boundary_target_files
            else sorted(set(targetable_operator_files) | set(targetable_surface_files))
        )
        available_actions = _available_hypothesis_actions(
            targetable_operator_files,
            targetable_policy_files=targetable_surface_files,
        )
        forced_surface_name = (
            forced_request.surface
            if forced_request is not None and forced_surface_diagnostic
            else None
        )
        forced_action_name = (
            forced_request.action
            if forced_request is not None and forced_surface_diagnostic
            else None
        )
        effective_available_actions = (
            {forced_action_name}
            if forced_action_name
            else available_actions
        )
        families = _extract_families_from_steps(all_steps, taxonomy=family_taxonomy)
        exploration_coverage = (
            build_exploration_coverage(
                families,
                available_actions=effective_available_actions,
                forced_action=forced_action_name,
            )
            if families
            else ""
        )

        # T08: Build strategy guidance from family data (J-patch: global)
        strategy_guidance = (
            _build_strategy_guidance(
                families,
                problem_spec,
                available_actions=effective_available_actions,
                forced_surface=forced_surface_name,
                forced_action=forced_action_name,
                active_problem_boundary_surfaces=active_problem_boundary_surfaces,
            )
            if families
            else ""
        )

        # T10: Champion baseline hints from most recent screening experiment
        champion_baselines = _build_champion_baselines(safe_hypothesis_steps)

        # Sprint H2 T5: Failure pattern warning
        failure_pattern_warning = _build_failure_pattern_warning(failure_streak or {})

        # I3: Forced locus diversification / diagnostic surface constraint
        locus_constraint = ""
        if forced_request is not None:
            surface = _find_research_surface(
                research_surfaces,
                forced_request.surface,
            )
            locus_constraint = _build_forced_surface_constraint(
                surface=surface,
                surface_name=forced_request.surface,
                action=forced_request.action,
                target_file=forced_request.target_file,
                diagnostic=forced_surface_diagnostic,
                blocking_hypotheses=[
                    *(active_hypotheses or []),
                    *(blacklist or []),
                    *(rejected_hypotheses or []),
                ],
            )

        # J1: Render search memory (cross-branch search history)
        search_memory_block = ""
        if search_memory is not None:
            search_memory_block = search_memory.render(view="hypothesis")

        # J2: Render saturation signals
        saturation_block = ""
        if saturation_signals:
            from scion.proposal.saturation import render_saturation_signals
            saturation_block = render_saturation_signals(saturation_signals)

        # Objective policy/guidance is generic: lexicographic protection or
        # weighted-sum scalar improvement, plus recent screening tendencies.
        objective_policy_guidance = _build_objective_policy_guidance(adapter_spec)
        objective_feedback = _build_recent_objective_feedback(
            safe_hypothesis_steps, branch.branch_id, adapter_spec
        )
        objective_opportunity_profile = _build_objective_opportunity_profile(
            safe_hypothesis_steps, adapter_spec
        )
        objective_guidance = _build_objective_guidance(
            saturation_signals, objective_feedback=objective_feedback
        )
        search_control_guidance = _build_search_control_guidance(
            families,
            safe_hypothesis_steps,
            adapter_spec,
            forced_surface=forced_surface_name,
        )
        runtime_feedback = _build_runtime_feedback(
            safe_hypothesis_steps,
            slow_case_threshold=self._runtime_slow_threshold,
        )
        runtime_failure_guidance = _build_runtime_failure_guidance(
            safe_hypothesis_steps,
            problem_spec=problem_spec,
            adapter_spec=adapter_spec,
            forced_surface=forced_surface_name,
        )
        agent_quality_feedback = _build_agent_quality_feedback(
            safe_hypothesis_steps,
            branch.branch_id,
        )

        # W10: Weight optimization feedback (coarse-grained operator signals)
        weight_opt_block = ""
        if weight_opt_result is not None:
            from scion.proposal.weight_feedback import render_weight_feedback
            weight_opt_block = render_weight_feedback(weight_opt_result)

        # J-patch: Render research log (cross-branch trajectory)
        research_log_block = ""
        if research_log is not None:
            research_log_block = research_log.render(view="hypothesis")

        return {
            "problem_summary": problem_summary,
            "problem_object": problem_object,
            "solver_mechanics": solver_mechanics,
            "branch_id": branch.branch_id,
            "champion_version": champion.version,
            "operator_categories": ", ".join(effective_operator_categories),
            "research_surfaces": research_surfaces_block,
            "available_actions": ", ".join(sorted(available_actions)),
            "targetable_files": ", ".join(effective_targetable_files),
            "active_problem_boundary_surfaces": ", ".join(
                active_problem_boundary_surfaces
            ),
            "champion_operators_code": champion_operators_code,
            "champion_stats": champion_stats,
            "experiment_history": experiment_history,
            "blacklist_summary": blacklist_summary,
            "solver_design_boundary_guidance": solver_design_boundary_guidance,
            "sibling_summary": sibling_summary,
            "branch_code": branch_code,
            "branch_direction": branch_direction,
            "exploration_coverage": exploration_coverage,
            "strategy_guidance": strategy_guidance,
            "champion_baselines": champion_baselines,
            "failure_pattern_warning": failure_pattern_warning,
            "locus_constraint": locus_constraint,
            "forced_surface": forced_request.surface if forced_request else "",
            "forced_action": forced_request.action if forced_request else "",
            "forced_target_file": (
                forced_request.target_file if forced_request else ""
            ),
            "objective_policy_guidance": objective_policy_guidance,
            "objective_opportunity_profile": objective_opportunity_profile,
            "objective_guidance": objective_guidance,
            "search_control_guidance": search_control_guidance,
            "runtime_feedback": runtime_feedback,
            "runtime_failure_guidance": runtime_failure_guidance,
            "agent_quality_feedback": agent_quality_feedback,
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
        branch_workspace: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Context for generate_code (Round 2).

        Contains problem summary, hypothesis details, target file content,
        research-surface interface spec, and import whitelist.
        Does NOT contain experiment stats or branch history.
        If prior_failure is set, a previous code generation attempt failed for
        this hypothesis — the failure detail is included so the LLM can learn.
        If branch_workspace is set for a previously verified branch, read the
        current branch research-object code rather than falling back to the
        champion snapshot.
        """
        problem_summary = _build_problem_summary(problem_spec, adapter=self._adapter)
        problem_object = _build_problem_object(adapter=self._adapter)
        solver_mechanics = _build_solver_mechanics(adapter=self._adapter)
        hypothesis_detail = _format_hypothesis(hypothesis)
        adapter_spec = _get_adapter_problem_spec(self._adapter)
        research_surfaces = _get_research_surfaces(problem_spec, adapter_spec)
        surface = _find_research_surface(research_surfaces, hypothesis.change_locus)
        source_root = (
            branch_workspace
            if branch_workspace and os.path.isdir(branch_workspace)
            else champion.code_snapshot_path
        )
        if hypothesis.action == "create_new":
            target_file_code = "(new file — will be created)"
        else:
            target_file_code = _read_target_file_from_root(
                source_root,
                hypothesis.target_file,
            )
        champion_operators_code = _read_champion_research_code(
            champion,
            research_surfaces=research_surfaces,
        )
        # Operator surfaces get reference operators as style/interface reference.
        reference_operators = _read_reference_operators(
            champion,
            hypothesis.change_locus,
            problem_spec,
            research_surfaces=research_surfaces,
        )
        operator_interface_spec = _build_operator_interface_spec(
            problem_spec,
            adapter=self._adapter,
            surface_name=hypothesis.change_locus,
        )
        import_whitelist = "\n".join(
            f"  - {imp}" for imp in problem_spec.search_space.import_whitelist
        )

        ctx: Dict[str, Any] = {
            "problem_summary": problem_summary,
            "problem_object": problem_object,
            "solver_mechanics": solver_mechanics,
            "branch_id": branch.branch_id,
            "champion_version": champion.version,
            "hypothesis_detail": hypothesis_detail,
            "target_file": hypothesis.target_file,
            "target_file_code": target_file_code,
            "champion_operators_code": champion_operators_code,
            "reference_operators": reference_operators,
            "operator_interface_spec": operator_interface_spec,
            "research_surface_name": hypothesis.change_locus,
            "research_surface_kind": getattr(surface, "kind", "operator"),
            "import_whitelist": import_whitelist,
            "editable_patterns": ", ".join(problem_spec.search_space.editable),
            "frozen_patterns": ", ".join(problem_spec.search_space.frozen),
        }
        if _is_solver_design_context_surface(hypothesis.change_locus, surface):
            ctx["solver_design_api_manifest"] = _build_solver_design_api_manifest(
                source_root=source_root,
                champion_root=champion.code_snapshot_path,
                target_file=hypothesis.target_file,
            )
            ctx["solver_design_branch_current_integration_files"] = (
                _build_solver_design_branch_current_integration_files(
                    source_root=source_root,
                    champion_root=champion.code_snapshot_path,
                    target_file=hypothesis.target_file,
                )
            )
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
        problem_object = _build_problem_object(adapter=self._adapter)
        solver_mechanics = _build_solver_mechanics(adapter=self._adapter)
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
            "problem_object": problem_object,
            "solver_mechanics": solver_mechanics,
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


def _read_champion_research_code(
    champion: ChampionState,
    *,
    research_surfaces: list[Any],
    include_operator_files: bool = True,
) -> str:
    sections: list[str] = []
    if include_operator_files:
        operator_code = _read_champion_operators(champion)
        if operator_code:
            sections.append(operator_code)

    for file_rel in _list_champion_surface_files(
        champion,
        research_surfaces=research_surfaces,
    ):
        sections.append(
            _read_surface_file(champion, file_rel, label="research surface")
        )
    return "\n\n".join(sections) if sections else "(no research-surface files found)"


def _read_surface_file(champion: ChampionState, file_rel: str, *, label: str) -> str:
    fpath = os.path.join(champion.code_snapshot_path, file_rel)
    try:
        with open(fpath, encoding="utf-8") as fh:
            content = fh.read()
        return f"### {file_rel} ({label})\n```python\n{content}\n```"
    except OSError as exc:
        return f"### {file_rel}\n(unreadable: {exc})"


def _build_champion_stats(champion: ChampionState) -> str:
    """Return hypothesis-facing champion baseline summary."""
    lines = ["Champion baseline: current selected solver state"]
    if champion.operator_pool:
        lines.append("Operator pool:")
        for name, op in champion.operator_pool.items():
            w = getattr(op, "weight", "?")
            cat = getattr(op, "category", "?")
            fp = getattr(op, "file_path", "?")
            lines.append(f"  - {name} [{cat}] weight={w}  file={fp}")
    else:
        lines.append("Operator pool: (not yet loaded from registry)")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# T07: Hypothesis Family Tracking
# ---------------------------------------------------------------------------

def _extract_mechanism_label(
    hypothesis_text: str,
    taxonomy: Optional[list] = None,
    preferred_label: Optional[str] = None,
) -> str:
    """Extract mechanism label from hypothesis text using problem taxonomy."""
    return extract_mechanism_label(
        hypothesis_text,
        taxonomy=taxonomy,
        preferred_label=preferred_label,
    )


def _make_family_id(mechanism_label: str, action_pattern: str, locus_pattern: str) -> str:
    return f"{mechanism_label}/{action_pattern}/{locus_pattern}"


def _get_step_status(step: StepRecord) -> str:
    """Derive a compact status string from a StepRecord."""
    if (
        step.protocol_result is not None
        and step.protocol_result.stage == ExperimentStage.SCREENING
    ):
        return f"screening_{step.protocol_result.gate_outcome}"
    if _is_safe_pre_protocol_failure_step(step):
        return f"failed_{step.failure_stage}"
    return ""


def _extract_families_from_steps(
    steps: List[StepRecord],
    taxonomy: Optional[list] = None,
) -> List[HypothesisFamily]:
    """Build the family list from step history (rebuilt each call — no persistence needed)."""
    family_map: Dict[str, HypothesisFamily] = {}
    for step in _filter_hypothesis_prompt_steps(steps):
        h = step.hypothesis
        mechanism = _extract_mechanism_label(
            h.hypothesis_text or "",
            taxonomy=taxonomy,
            preferred_label=h.change_locus,
        )
        family_id = _make_family_id(mechanism, h.action, h.change_locus)
        status = _get_step_status(step)
        if not status:
            continue
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


def assign_family_id(
    hypothesis_text: str,
    action: str,
    change_locus: str,
    taxonomy: Optional[list] = None,
) -> str:
    """Public helper: compute family_id for a hypothesis (for HypothesisRecord.family_id)."""
    mechanism = _extract_mechanism_label(
        hypothesis_text,
        taxonomy=taxonomy,
        preferred_label=change_locus,
    )
    return _make_family_id(mechanism, action, change_locus)


def build_exploration_coverage(
    families: List[HypothesisFamily],
    *,
    available_actions: Optional[set[str]] = None,
    forced_action: Optional[str] = None,
) -> str:
    """Return a formatted string showing family coverage across attempts (T07)."""
    if not families:
        return ""
    lines = ["## Exploration Coverage"]
    for fam in families:
        status_counts = Counter(fam.statuses)
        parts: List[str] = []
        for status in (
            "screening_pass",
            "screening_expand",
            "screening_continue",
            "screening_fail",
            "screening_unclear",
        ):
            count = status_counts.get(status, 0)
            if count:
                parts.append(f"{status}={count}")
        pre_protocol_failed = sum(
            count
            for status, count in status_counts.items()
            if status.startswith("failed_")
        )
        if pre_protocol_failed:
            parts.append(f"pre_protocol_failed={pre_protocol_failed}")
        status_summary = " ".join(parts) if parts else "screening_seen=0"
        lines.append(
            f"  {fam.family_id}: n={fam.evidence_count} [{status_summary}]"
        )
    # Show unexplored action/locus combos
    explored_actions = {f.action_pattern for f in families}
    all_actions = available_actions or {"create_new", "modify", "remove"}
    unexplored_actions = all_actions - explored_actions
    if unexplored_actions and not forced_action:
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


def _list_champion_operator_files(champion: ChampionState) -> list[str]:
    files: set[str] = set()
    for op in (champion.operator_pool or {}).values():
        file_path = getattr(op, "file_path", "")
        if file_path:
            files.add(file_path)

    operators_dir = os.path.join(champion.code_snapshot_path, "operators")
    if os.path.isdir(operators_dir):
        try:
            for fname in os.listdir(operators_dir):
                if fname.endswith(".py") and fname not in ("__init__.py", "base.py"):
                    files.add(f"operators/{fname}")
        except OSError:
            pass
    return sorted(files)


def _list_champion_surface_files(
    champion: ChampionState,
    *,
    research_surfaces: list[Any],
) -> list[str]:
    files: set[str] = set()
    for surface in research_surfaces:
        if getattr(surface, "kind", None) == "operator":
            continue
        for target in surface_target_files(surface):
            if "*" in str(target):
                continue
            file_rel = str(target).lstrip("/")
            if os.path.isfile(os.path.join(champion.code_snapshot_path, file_rel)):
                files.add(file_rel)
    return sorted(files)


def _available_hypothesis_actions(
    targetable_operator_files: List[str],
    *,
    targetable_policy_files: Optional[List[str]] = None,
) -> set[str]:
    actions = {"create_new"}
    if targetable_operator_files or targetable_policy_files:
        actions.add("modify")
    if targetable_operator_files:
        actions.add("remove")
    return actions


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


def _build_runtime_feedback(
    steps: List[StepRecord],
    max_items: int = 4,
    *,
    slow_case_threshold: float = 2.0,
) -> str:
    """Render bounded runtime-guard feedback for proposal context.

    This is proposal guidance only. It is intentionally derived from bounded
    verification and screening aggregates. Validation/frozen per-case data is
    never rendered here.
    """
    items: list[str] = []
    summaries: list[str] = []
    slow_cases: list[str] = []
    failure_cases: list[str] = []
    failure_causes: list[str] = []
    contract_failures: list[str] = []
    for step in reversed(steps):
        detail = step.verification_detail or step.failure_detail or ""
        target = (
            step.patch.file_path
            if step.patch is not None
            else step.hypothesis.target_file
            or step.hypothesis.change_locus
        )
        if (
            step.protocol_result is None
            and step.failure_stage in {"hypothesis_contract", "patch_contract"}
            and len(contract_failures) < max_items
        ):
            contract_failures.append(
                f"- R{step.round_num} target={target}: "
                f"stage={step.failure_stage} detail={_first_line(detail)}"
            )
        if "V9_perf_guard" in detail and len(items) < max_items:
            check_line = _extract_runtime_guard_line(detail)
            items.append(f"- R{step.round_num} target={target}: {check_line}")
        if (
            step.protocol_result is not None
            and step.protocol_result.stage == ExperimentStage.SCREENING
        ):
            if step.protocol_result.stats.runtime_pairs > 0 and len(summaries) < max_items:
                st = step.protocol_result.stats
                summaries.append(
                    f"- R{step.round_num} target={target}: "
                    f"median_ratio={_fmt_runtime(st.runtime_ratio_median)}x "
                    f"median_delta_ms={_fmt_runtime(st.runtime_delta_median_ms)} "
                    f"regression_rate={_fmt_runtime(st.runtime_regression_rate)} "
                    f"pairs={st.runtime_pairs}"
                )
            (
                raw_failures,
                raw_slow_cases,
                raw_failure_causes,
            ) = _extract_screening_runtime_structured_feedback(
                step,
                target=target,
                max_items=max_items,
                slow_case_threshold=slow_case_threshold,
            )
            for line in raw_failure_causes:
                if len(failure_causes) < max_items:
                    failure_causes.append(line)
            for line in raw_failures:
                if len(failure_cases) < max_items:
                    failure_cases.append(line)
            for line in raw_slow_cases:
                if len(slow_cases) < max_items:
                    slow_cases.append(line)
        if (
            len(items) >= max_items
            and len(summaries) >= max_items
            and len(failure_causes) >= max_items
            and len(contract_failures) >= max_items
            and len(slow_cases) >= max_items
            and len(failure_cases) >= max_items
        ):
            break
    if (
        not items
        and not summaries
        and not failure_cases
        and not slow_cases
        and not failure_causes
        and not contract_failures
    ):
        return ""
    sections: list[str] = []
    if failure_causes:
        sections.append(
            "Recent screening failure causes:\n"
            + "\n".join(reversed(failure_causes))
        )
    if contract_failures:
        sections.append(
            "Recent contract failures:\n" + "\n".join(reversed(contract_failures))
        )
    if summaries:
        sections.append(
            "Recent screening runtime summary:\n" + "\n".join(reversed(summaries))
        )
    if failure_cases:
        sections.append(
            "Recent screening runtime failure categories:\n"
            + "\n".join(reversed(failure_cases))
        )
    if slow_cases:
        sections.append(
            "Recent slow screening cases:\n" + "\n".join(reversed(slow_cases))
        )
    if items:
        sections.append("Recent runtime guard failures:\n" + "\n".join(reversed(items)))
    sections.append(
        "Prefer bounded neighborhoods, top-k candidate filters, and early no-op exits."
    )
    return "\n".join(sections)


def _build_runtime_failure_guidance(
    steps: List[StepRecord],
    *,
    problem_spec: Any,
    adapter_spec: Any = None,
    max_items: int = 4,
    forced_surface: str | None = None,
) -> str:
    """Render problem-declared steering for structured runtime failure categories."""
    guidance_specs = _get_runtime_failure_guidance_specs(problem_spec, adapter_spec)
    if not guidance_specs:
        return ""

    safe_steps = [
        step
        for step in _filter_hypothesis_prompt_steps(steps)
        if (
            step.protocol_result is not None
            and step.protocol_result.stage == ExperimentStage.SCREENING
        )
    ][-12:]
    if not safe_steps:
        return ""

    surfaces = _get_research_surfaces(problem_spec, adapter_spec)
    kind_by_surface = {
        str(getattr(surface, "name", "")): str(getattr(surface, "kind", ""))
        for surface in surfaces
    }
    rendered: list[str] = []
    for spec in guidance_specs:
        categories = _coerce_text_list(getattr(spec, "failure_categories", None))
        if not categories:
            continue
        profile = _runtime_guidance_profile(
            safe_steps,
            categories=categories,
            applies_to_surfaces=_coerce_text_list(
                getattr(spec, "applies_to_surfaces", None)
            ),
            applies_to_surface_kinds=_coerce_text_list(
                getattr(spec, "applies_to_surface_kinds", None)
            ),
            kind_by_surface=kind_by_surface,
        )
        matched = profile["matched_count"]
        total = profile["total_count"]
        if total <= 0 or matched <= 0:
            continue
        min_count = max(1, _as_int(getattr(spec, "min_count", 1)))
        try:
            min_fraction = float(getattr(spec, "min_category_fraction", 0.5))
        except (TypeError, ValueError):
            min_fraction = 0.5
        fraction = matched / total
        if matched < min_count or fraction < min_fraction:
            continue

        lines = [
            (
                f"- Runtime categories {', '.join(categories)} dominate recent "
                f"matching screening evidence ({matched}/{total}, "
                f"fraction={fraction:.2f})."
            )
        ]
        surfaces_seen = sorted(profile["surfaces"])[:max_items]
        if surfaces_seen:
            lines.append(f"  observed_surfaces: {', '.join(surfaces_seen)}")
        recommended = _coerce_text_list(getattr(spec, "recommended_surfaces", None))
        discouraged = _coerce_text_list(getattr(spec, "discouraged_surfaces", None))
        forced_conflict = bool(
            forced_surface
            and (
                (recommended and forced_surface not in recommended)
                or forced_surface in discouraged
            )
        )
        if recommended and not forced_conflict:
            lines.append(f"  recommended_surfaces: {', '.join(recommended)}")
        safe_discouraged = [
            surface for surface in discouraged if surface != forced_surface
        ]
        if safe_discouraged and not forced_conflict:
            lines.append(f"  discouraged_surfaces: {', '.join(safe_discouraged)}")
        if forced_surface:
            lines.append(
                f"  forced_surface_constraint: keep surface {forced_surface}"
            )
        guidance = str(getattr(spec, "guidance", "") or "").strip()
        if guidance and not forced_conflict:
            lines.append(f"  guidance: {guidance}")
        rendered.append("\n".join(lines))

    if not rendered:
        return ""
    return (
        "Problem-declared runtime-failure steering (screening only):\n"
        + "\n".join(rendered[:max_items])
    )


def _get_runtime_failure_guidance_specs(
    problem_spec: Any,
    adapter_spec: Any = None,
) -> list[Any]:
    for spec in (problem_spec, adapter_spec):
        hints = getattr(spec, "runtime_failure_guidance", None)
        if hints:
            return list(hints)
        hints = getattr(spec, "failure_response_hints", None)
        if hints:
            return list(hints)
    return []


def _runtime_guidance_profile(
    steps: list[StepRecord],
    *,
    categories: list[str],
    applies_to_surfaces: list[str],
    applies_to_surface_kinds: list[str],
    kind_by_surface: dict[str, str],
) -> dict[str, Any]:
    category_set = set(categories)
    surface_set = set(applies_to_surfaces)
    kind_set = set(applies_to_surface_kinds)
    matched_count = 0
    total_count = 0
    surfaces_seen: set[str] = set()
    for step in steps:
        surface = str(step.hypothesis.change_locus or "")
        kind = kind_by_surface.get(surface, "")
        if surface_set and surface not in surface_set:
            continue
        if kind_set and kind not in kind_set:
            continue
        counts = {
            category: count
            for category, count in _runtime_failure_categories(step).items()
            if count > 0
        }
        if not counts:
            continue
        step_total = sum(counts.values())
        total_count += step_total
        matched_count += sum(
            count for category, count in counts.items() if category in category_set
        )
        if surface:
            surfaces_seen.add(surface)
    return {
        "matched_count": matched_count,
        "total_count": total_count,
        "surfaces": surfaces_seen,
    }


def _extract_screening_runtime_structured_feedback(
    step: StepRecord,
    *,
    target: str,
    max_items: int,
    slow_case_threshold: float = 2.0,
) -> tuple[list[str], list[str], list[str]]:
    """Extract bounded screening-only runtime feedback from structured summaries."""
    protocol = step.protocol_result
    if protocol is None or protocol.stage != ExperimentStage.SCREENING:
        return [], [], []

    failure_cause = _build_screening_failure_cause_line(step, target, {})
    failure_causes = [failure_cause] if failure_cause else []
    failure_lines: list[str] = []
    categories = _runtime_failure_categories(step)
    first = _first_runtime_failure(step)
    for category, count in sorted(categories.items()):
        if count <= 0:
            continue
        detail = ""
        if first and first.get("category") == category:
            code = first.get("code") or "unknown"
            component = first.get("component") or "unknown"
            summary = first.get("detail_summary") or ""
            detail = f" first_code={code} component={component} detail={_first_line(str(summary))}"
        failure_lines.append(
            f"- R{step.round_num} target={target}: "
            f"candidate_failure_category={category} count={count}{detail}"
        )
        if len(failure_lines) >= max_items:
            break

    return failure_lines, [], failure_causes


def _build_screening_failure_cause_line(
    step: StepRecord,
    target: str,
    payload: dict[str, Any],
) -> str:
    protocol = step.protocol_result
    if protocol is None:
        return ""
    stats = protocol.stats
    operator_attempts = _structured_runtime_count(
        step,
        "candidate_operator_attempts",
        payload,
        "candidate_runtime",
        "operator_attempts",
    )
    operator_accepted = _structured_runtime_count(
        step,
        "candidate_operator_accepted",
        payload,
        "candidate_runtime",
        "operator_accepted",
    )
    operator_errors = _structured_runtime_count(
        step,
        "candidate_operator_errors",
        payload,
        "candidate_runtime",
        "operator_errors",
    )
    invalid_outputs = _structured_runtime_count(
        step,
        "candidate_operator_invalid_outputs",
        payload,
        "candidate_runtime",
        "operator_invalid_outputs",
    )
    stop_reasons = _runtime_stop_reasons(step) or _operator_stop_reason_counts(payload)
    failed_pairs = _count_field(stats.failed_pairs, payload, "failed_pairs")
    candidate_failed = _count_field(
        stats.candidate_failed_pairs,
        payload,
        "candidate_failed_pairs",
    )
    champion_failed = _count_field(
        stats.champion_failed_pairs,
        payload,
        "champion_failed_pairs",
    )
    gate_failed = protocol.gate_outcome in {"fail", "unclear", "continue"}
    has_runtime_or_operator_signal = any(
        value > 0
        for value in (
            failed_pairs,
            candidate_failed,
            champion_failed,
            operator_attempts,
            operator_accepted,
            operator_errors,
            invalid_outputs,
        )
    )
    if not gate_failed and not has_runtime_or_operator_signal:
        return ""

    reason_codes = ",".join(protocol.reason_codes) if protocol.reason_codes else "none"
    total_pairs = _count_field(stats.total_pairs, payload, "total_pairs")
    valid_pairs = _count_field(stats.valid_pairs, payload, "valid_pairs")
    runtime_ratio = (
        stats.runtime_ratio_median
        if stats.runtime_ratio_median is not None
        else _runtime_stat(payload, "runtime_ratio_median")
    )
    quality_notes: list[str] = []
    if operator_attempts > 0 and operator_accepted == 0:
        quality_notes.append("no accepted operator moves despite attempted moves")
    if stats.ties > max(stats.wins, stats.losses) and stats.ties > 0:
        quality_notes.append("tie-dominated screening evidence")
    if stop_reasons:
        reason_text = ",".join(
            f"{reason}:{count}" for reason, count in sorted(stop_reasons.items())
        )
        quality_notes.append(f"operator_stop_reason={reason_text}")
        if "no_improvement_round" in stop_reasons:
            quality_notes.append(
                "no_improvement_round indicates weak/no-op search behavior, not schema/runtime failure"
            )
    surface_runtime_note = _surface_runtime_summary_note(protocol)
    if surface_runtime_note:
        quality_notes.append(surface_runtime_note)
    if (
        quality_notes
        and failed_pairs == 0
        and candidate_failed == 0
        and champion_failed == 0
        and operator_errors == 0
        and invalid_outputs == 0
    ):
        quality_notes.append("no schema/runtime failure detected")

    quality_suffix = ""
    if quality_notes:
        quality_suffix = " quality_notes=" + "; ".join(quality_notes)

    return (
        f"- R{step.round_num} target={target}: gate={protocol.gate_outcome} "
        f"reasons={reason_codes} total_pairs={total_pairs} valid_pairs={valid_pairs} "
        f"wins={stats.wins} losses={stats.losses} ties={stats.ties} "
        f"failed_pairs={failed_pairs} candidate_failed_pairs={candidate_failed} "
        f"champion_failed_pairs={champion_failed} "
        f"runtime_ratio_median={_fmt_runtime(runtime_ratio)}x "
        f"operator_attempts={operator_attempts} operator_accepted={operator_accepted} "
        f"operator_errors={operator_errors} invalid_outputs={invalid_outputs}"
        f"{quality_suffix}"
    )


def _surface_runtime_summary_note(protocol: Any) -> str:
    summary = getattr(protocol, "candidate_surface_runtime_summary", None)
    if not isinstance(summary, dict):
        return ""
    surface = str(summary.get("selected_surface") or "").strip()
    fields = summary.get("fields")
    if not surface or not isinstance(fields, dict):
        return ""

    candidates: list[tuple[tuple[int, int, str], str]] = []
    guard_note = _telemetry_guard_summary_note(summary)
    if guard_note:
        candidates.append(((0, -1, "telemetry_guard"), guard_note))
    for field, field_summary in fields.items():
        if not isinstance(field_summary, dict):
            continue
        field_name = str(field)
        if not _surface_runtime_field_interesting(field_name, field_summary):
            continue
        values = field_summary.get("values")
        value_text = ""
        if isinstance(values, list) and values:
            first = values[0]
            if isinstance(first, dict):
                raw_value = str(first.get("value", ""))[:120]
                count = _as_int(first.get("count", 0))
                value_text = f" value={raw_value} count={count}"
        numeric_text = _surface_runtime_numeric_note(field_summary)
        failed = _as_int(field_summary.get("failed", 0))
        missing = _as_int(field_summary.get("missing", 0))
        suffix = value_text + numeric_text
        if failed or missing:
            suffix += f" failed={failed} missing={missing}"
        candidates.append(
            (
                _surface_runtime_sort_key(field_name, field_summary),
                f"{field_name}:{suffix.strip()}",
            )
        )
    candidates.sort(key=lambda item: item[0])
    interesting = [text for _sort_key, text in candidates[:8]]
    if not interesting:
        return ""
    return f"selected_surface_runtime[{surface}]=" + "; ".join(interesting)


def _telemetry_guard_summary_note(summary: dict[str, Any]) -> str:
    guard = summary.get("telemetry_guard")
    if not isinstance(guard, dict):
        return ""
    failures = guard.get("failures")
    warnings = guard.get("warnings")
    parts: list[str] = []
    if isinstance(failures, list) and failures:
        codes = [
            str(item.get("code"))
            for item in failures
            if isinstance(item, dict) and item.get("code")
        ]
        if codes:
            parts.append("fail=" + ",".join(codes[:4]))
    if isinstance(warnings, list) and warnings:
        codes = [
            str(item.get("code"))
            for item in warnings
            if isinstance(item, dict) and item.get("code")
        ]
        if codes:
            parts.append("warn=" + ",".join(codes[:4]))
    if not parts:
        return ""
    return "telemetry_guard(" + ";".join(parts) + ")"


_SURFACE_RUNTIME_PRIORITY_SUFFIXES = (
    "_objective_trace",
    "_delta_by_phase",
    "_phase_delta_sum",
    "_phase_best_delta",
    "_phase_improvement_counts",
    "_recovery_delta_sum",
    "_recovery_best_delta",
    "_recovery_counts",
    "_accepted_moves",
    "_move_attempts",
    "_search_iterations",
    "_elapsed_ms",
    "_phase_runtime_ms",
    "_accepted_delta_sum",
    "_accepted_best_delta",
    "_accepted_positive_counts",
    "_accepted",
    "_attempts",
    "_skip_reasons",
    "_best_delta",
    "_improvement_counts",
    "_coverage_status",
    "_stop_reason",
    "_errors",
    "_active",
    "_loaded",
    "_use_vns",
    "_destroy_ratio",
    "_baseline_time_fraction",
    "_max_destroy_customers",
)


def _surface_runtime_sort_key(
    field_name: str,
    field_summary: dict[str, Any],
) -> tuple[int, int, str]:
    has_issue = any(
        _as_int(field_summary.get(key, 0)) > 0
        for key in ("failed", "missing", "empty")
    )
    priority = len(_SURFACE_RUNTIME_PRIORITY_SUFFIXES)
    for index, suffix in enumerate(_SURFACE_RUNTIME_PRIORITY_SUFFIXES):
        if field_name.endswith(suffix):
            priority = index
            break
    return (0 if has_issue else 1, priority, field_name)


def _surface_runtime_numeric_note(field_summary: dict[str, Any]) -> str:
    numeric = field_summary.get("numeric_summary")
    if not isinstance(numeric, dict):
        return ""
    parts: list[str] = []
    scalar = numeric.get("scalar")
    if isinstance(scalar, dict):
        parts.append(_surface_runtime_numeric_stats_text("scalar", scalar))
    mapping = numeric.get("mapping")
    if isinstance(mapping, dict):
        for key, stats in list(mapping.items())[:3]:
            if isinstance(stats, dict):
                parts.append(_surface_runtime_numeric_stats_text(str(key), stats))
    parts = [part for part in parts if part]
    if not parts:
        return ""
    return " numeric=" + "|".join(parts)


def _surface_runtime_numeric_stats_text(label: str, stats: dict[str, Any]) -> str:
    selected = []
    for key in (
        "observed_count",
        "weighted_sum",
        "nonzero_count",
        "positive_count",
        "zero_count",
    ):
        if key in stats:
            selected.append(f"{key}={stats[key]}")
    if not selected:
        return ""
    return f"{label}(" + ",".join(selected) + ")"


def _surface_runtime_field_interesting(
    field_name: str,
    field_summary: dict[str, Any],
) -> bool:
    if any(
        _as_int(field_summary.get(key, 0)) > 0
        for key in ("failed", "missing", "empty")
    ):
        return True
    return any(
        field_name.endswith(suffix)
        for suffix in _SURFACE_RUNTIME_PRIORITY_SUFFIXES
    )


def _runtime_failure_categories(step: StepRecord) -> dict[str, int]:
    categories = dict(getattr(step, "candidate_runtime_failure_categories", {}) or {})
    protocol = step.protocol_result
    if protocol is not None:
        categories.update(
            dict(getattr(protocol, "candidate_runtime_failure_categories", {}) or {})
        )
    return {str(key): _as_int(value) for key, value in categories.items()}


def _first_runtime_failure(step: StepRecord) -> dict[str, Any]:
    protocol = step.protocol_result
    first = getattr(protocol, "candidate_first_runtime_failure", None) if protocol else None
    if first is None:
        first = getattr(step, "candidate_first_runtime_failure", None)
    return dict(first or {})


def _runtime_stop_reasons(step: StepRecord) -> dict[str, int]:
    reasons = dict(getattr(step, "candidate_runtime_stop_reasons", {}) or {})
    protocol = step.protocol_result
    if protocol is not None:
        reasons.update(dict(getattr(protocol, "candidate_runtime_stop_reasons", {}) or {}))
    return {str(key): _as_int(value) for key, value in reasons.items()}


def _structured_runtime_count(
    step: StepRecord,
    attr_name: str,
    payload: dict[str, Any],
    runtime_key: str,
    field: str,
) -> int:
    protocol = step.protocol_result
    value = getattr(protocol, attr_name, 0) if protocol is not None else 0
    if _as_int(value) > 0:
        return _as_int(value)
    step_value = getattr(step, attr_name, 0)
    if _as_int(step_value) > 0:
        return _as_int(step_value)
    return _sum_runtime_field(payload, runtime_key, field)


def _sum_runtime_field(payload: dict[str, Any], runtime_key: str, field: str) -> int:
    total = 0
    for pair in payload.get("pairs", []) or []:
        if not isinstance(pair, dict):
            continue
        counted_pair_runtime = False
        runtime = pair.get(runtime_key)
        if isinstance(runtime, dict):
            total += _as_int(runtime.get(field))
            counted_pair_runtime = True
        failure = pair.get("failure")
        if isinstance(failure, dict):
            audit = failure.get("runtime_audit")
            if (
                isinstance(audit, dict)
                and runtime_key.startswith("candidate")
                and not counted_pair_runtime
            ):
                total += _as_int(audit.get(field))
    return total


def _operator_stop_reason_counts(payload: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for pair in payload.get("pairs", []) or []:
        if not isinstance(pair, dict):
            continue
        runtime = pair.get("candidate_runtime")
        if not isinstance(runtime, dict):
            continue
        reason = str(runtime.get("operator_stop_reason") or "").strip()
        if not reason:
            continue
        counts[reason] = counts.get(reason, 0) + 1
    return counts


def _count_field(stats_value: int, payload: dict[str, Any], field: str) -> int:
    return stats_value if stats_value > 0 else _as_int(payload.get(field))


def _runtime_stat(payload: dict[str, Any], field: str) -> float | None:
    runtime_stats = payload.get("runtime_stats")
    if not isinstance(runtime_stats, dict):
        return None
    value = runtime_stats.get(field)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return 0


def _fmt_runtime(value: float | None) -> str:
    if value is None:
        return "NA"
    return f"{value:.2f}"


def _extract_runtime_guard_line(detail: str) -> str:
    for line in detail.splitlines():
        if "[V9_perf_guard]" in line:
            cleaned = re.sub(r"^\s*\[V9_perf_guard\]\s*\(heavy\)\s*", "", line)
            return cleaned.strip()
    for line in detail.splitlines():
        if "V9_perf_guard" in line:
            return line.replace("V9_perf_guard", "runtime guard").strip()
    return "runtime guard failed"


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


def _expand_surface_targets_for_champion(
    champion: ChampionState,
    targets: list[str],
) -> list[str]:
    if not targets:
        return []
    root_text = str(getattr(champion, "code_snapshot_path", "") or "").strip()
    root = Path(root_text).expanduser() if root_text else None
    concrete: list[str] = []
    patterns: list[str] = []
    for raw_target in targets:
        target = str(raw_target or "").strip().lstrip("/")
        if not target:
            continue
        if "*" not in target:
            _append_unique(concrete, target)
            continue
        if root is not None and root.is_dir():
            try:
                for path in sorted(root.glob(target)):
                    if not path.is_file():
                        continue
                    try:
                        rel = path.relative_to(root).as_posix()
                    except ValueError:
                        continue
                    if rel.endswith("/__init__.py"):
                        continue
                    _append_unique(concrete, rel)
            except OSError:
                pass
        _append_unique(patterns, target)
    return concrete + [pattern for pattern in patterns if pattern not in concrete]


def _append_unique(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


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
    if hypothesis.target_runtime_effect:
        lines.append(f"target_runtime_effect: {hypothesis.target_runtime_effect}")
    if hypothesis.complexity_claim:
        lines.append(f"complexity_claim: {hypothesis.complexity_claim}")
    if hypothesis.runtime_budget_strategy:
        lines.append(f"runtime_budget_strategy: {hypothesis.runtime_budget_strategy}")
    if getattr(hypothesis, "mechanism_changes", None):
        lines.append(
            "mechanism_changes: "
            + json.dumps(
                mechanism_change_dicts(hypothesis),
                sort_keys=True,
                separators=(",", ":"),
            )
        )
    expected_telemetry = getattr(hypothesis, "expected_telemetry", None)
    if expected_telemetry:
        lines.append(
            "expected_telemetry: "
            + json.dumps(
                expected_telemetry,
                sort_keys=True,
                separators=(",", ":"),
            )
        )
    if hypothesis.novelty_signature:
        lines.append(
            "hypothesis_metadata_novelty_signature: "
            + json.dumps(
                hypothesis.novelty_signature,
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        lines.append(
            "novelty_signature_implementation_rule: use this only as proposal "
            "identity; do not copy novelty_signature into code or returned "
            "policy/config dictionaries unless the surface interface explicitly "
            "declares that key."
        )
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
    champion: ChampionState,
    change_locus: str,
    problem_spec: ProblemSpec,
    *,
    research_surfaces: Optional[list[Any]] = None,
) -> str:
    """Read same-surface operators as reference for create_new actions."""
    surface = _find_research_surface(research_surfaces or [], change_locus)
    if surface is not None and getattr(surface, "kind", "operator") != "operator":
        return ""
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
    return _read_target_file_from_root(champion.code_snapshot_path, target_file)


def _read_target_file_from_root(root: str, target_file: Optional[str]) -> str:
    if not target_file or not root:
        return "(no target file specified)"
    candidate = os.path.join(root, target_file.lstrip("/"))
    try:
        with open(candidate, encoding="utf-8") as fh:
            content = fh.read()
        return f"File: {target_file}\n```python\n{content}\n```"
    except OSError as exc:
        return f"(could not read {target_file}: {exc})"


_SOLVER_DESIGN_API_MODULES = (
    "policies/baseline_algorithm.py",
    "policies/baseline_modules/scheduler.py",
    "policies/baseline_modules/construction.py",
    "policies/baseline_modules/destroy_repair.py",
    "policies/baseline_modules/local_search.py",
    "policies/baseline_modules/acceptance.py",
    "policies/baseline_modules/state.py",
    "policies/baseline_modules/config.py",
)

_SOLVER_DESIGN_INTEGRATION_FULL_FILES = (
    "policies/baseline_algorithm.py",
    "policies/baseline_modules/scheduler.py",
    "policies/baseline_modules/state.py",
)

_SOLVER_DESIGN_INTEGRATION_SUMMARY_FILES = (
    "policies/baseline_modules/construction.py",
    "policies/baseline_modules/destroy_repair.py",
    "policies/baseline_modules/local_search.py",
    "policies/baseline_modules/acceptance.py",
    "policies/baseline_modules/config.py",
)


def _build_solver_design_api_manifest(
    *,
    source_root: str,
    champion_root: str,
    target_file: Optional[str],
) -> str:
    root = Path(source_root or champion_root).expanduser()
    fallback_root = Path(champion_root).expanduser()
    normalized_target = str(target_file or "").replace("\\", "/").lstrip("/")
    lines = [
        f"Approved target_file: {normalized_target or '(none)'}",
        (
            "Exact importable module API from the current branch snapshot. "
            "Use these names instead of inventing sibling helper imports."
        ),
    ]
    for rel in _SOLVER_DESIGN_API_MODULES:
        path = root / rel
        if not path.is_file() and fallback_root != root:
            path = fallback_root / rel
        summary = _python_api_manifest_for_file(path)
        if summary:
            lines.append(f"- {rel}: {summary}")
    target_guidance = _solver_design_target_api_guidance(normalized_target)
    if target_guidance:
        lines.append(target_guidance)
    return "\n".join(lines)


def _build_solver_design_branch_current_integration_files(
    *,
    source_root: str,
    champion_root: str,
    target_file: Optional[str],
) -> str:
    normalized_target = str(target_file or "").replace("\\", "/").lstrip("/")
    lines = [
        (
            "These files are branch-current integration context for "
            "solver_design additional_changes. The approved target full "
            "content remains the Target File section; use this section only "
            "for minimal necessary wiring based on current content."
        ),
        f"Approved target_file: {normalized_target or '(none)'}",
    ]
    for rel in _SOLVER_DESIGN_INTEGRATION_FULL_FILES:
        artifact = _read_solver_design_context_artifact(
            rel,
            source_root=source_root,
            champion_root=champion_root,
        )
        lines.append(
            f"### {rel}\n"
            f"Provenance: {artifact['source']}; readable={artifact['readable']}\n"
            f"```python\n{artifact['content']}\n```"
        )
    summary_lines: list[str] = []
    for rel in _SOLVER_DESIGN_INTEGRATION_SUMMARY_FILES:
        artifact = _read_solver_design_context_artifact(
            rel,
            source_root=source_root,
            champion_root=champion_root,
        )
        summary = _python_api_manifest_for_file(Path(str(artifact["path"])))
        if not summary:
            summary = artifact["reason"]
        summary_lines.append(
            f"- {rel}: provenance={artifact['source']}; {summary}"
        )
    if summary_lines:
        lines.append(
            "### Compact sibling API summaries\n" + "\n".join(summary_lines)
        )
    return "\n\n".join(lines)


def _read_solver_design_context_artifact(
    rel: str,
    *,
    source_root: str,
    champion_root: str,
) -> dict[str, Any]:
    normalized = rel.replace("\\", "/").lstrip("/")
    roots: list[tuple[Path, str]] = []
    if source_root:
        source = Path(source_root).expanduser()
        champion = Path(champion_root).expanduser() if champion_root else None
        source_kind = (
            "branch_workspace"
            if champion is not None and source.resolve() != champion.resolve()
            else "champion_snapshot"
        )
        roots.append((source, source_kind))
    if champion_root:
        fallback = Path(champion_root).expanduser()
        if not roots or fallback.resolve() != roots[0][0].resolve():
            roots.append((fallback, "champion_snapshot_fallback"))
    for root, source_kind in roots:
        path = root / normalized
        try:
            if not path.is_file() or path.is_symlink():
                continue
            return {
                "path": path,
                "source": source_kind,
                "readable": True,
                "reason": "ok",
                "content": path.read_text(encoding="utf-8"),
            }
        except OSError:
            continue
    return {
        "path": Path(source_root or champion_root or "") / normalized,
        "source": "missing",
        "readable": False,
        "reason": "not_found",
        "content": f"# could not read {normalized}",
    }


def _python_api_manifest_for_file(path: Path) -> str:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return ""
    exports: list[str] = []
    imports: list[str] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            exports.append("def " + _python_signature_text(node))
        elif isinstance(node, ast.ClassDef):
            methods = [
                _python_signature_text(child)
                for child in node.body
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]
            if methods:
                exports.append(f"class {node.name}: " + "; ".join(methods[:8]))
            else:
                exports.append(f"class {node.name}")
        elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = list(node.targets) if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                exports.extend(sorted(_assigned_names_for_manifest(target)))
        elif isinstance(node, ast.ImportFrom) and node.level > 0:
            imported = ", ".join(
                alias.asname or alias.name
                for alias in node.names
                if alias.name != "*"
            )
            if imported:
                dots = "." * int(node.level or 0)
                imports.append(f"from {dots}{node.module or ''} import {imported}")
    parts: list[str] = []
    if exports:
        parts.append("exports " + "; ".join(exports[:14]))
    if imports:
        parts.append("current imports " + "; ".join(imports[:8]))
    return " | ".join(parts)


def _python_signature_text(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    args = node.args
    parts: list[str] = []
    for arg in [*args.posonlyargs, *args.args]:
        parts.append(arg.arg)
    if args.vararg is not None:
        parts.append("*" + args.vararg.arg)
    elif args.kwonlyargs:
        parts.append("*")
    for arg in args.kwonlyargs:
        parts.append(arg.arg)
    if args.kwarg is not None:
        parts.append("**" + args.kwarg.arg)
    return f"{node.name}({', '.join(parts)})"


def _assigned_names_for_manifest(node: ast.AST) -> set[str]:
    if isinstance(node, ast.Name):
        return {node.id}
    if isinstance(node, (ast.Tuple, ast.List)):
        names: set[str] = set()
        for item in node.elts:
            names.update(_assigned_names_for_manifest(item))
        return names
    return set()


def _solver_design_target_api_guidance(target_file: str) -> str:
    if target_file == "policies/baseline_modules/destroy_repair.py":
        return (
            "Target-specific rule for destroy_repair.py: make destroy/repair "
            "operators the primary mechanism in this file. A scheduler.py "
            "additional_change may only import newly defined destroy/repair "
            "symbols from .destroy_repair and add them to destroy_ops or "
            "repair_ops. Do not add scheduler imports from construction.py "
            "while destroy_repair.py is the approved target, unless the same "
            "patch also changes construction.py and defines that exact symbol. "
            "Existing construction exports are _clarke_wright_savings, "
            "_nearest_neighbor, _sweep_construction, and "
            "_capacity_balanced_construction; names like _clarke_wright, "
            "_clarke_wright_solution, _nearest_neighbor_solution, "
            "_nearest_neighbor_construction, _savings_solution, and "
            "_savings_construction do not exist. Prefer bounded for-loops or "
            "while loops with a visibly incremented counter cap."
        )
    if target_file == "policies/baseline_modules/construction.py":
        return (
            "Target-specific rule for construction.py: construction helpers "
            "must return internal _Solution objects. Wire new seed helpers "
            "through scheduler.py only by importing the exact new symbol from "
            ".construction and calling it inside _ALNSVNSSolver methods."
        )
    if target_file == "policies/baseline_modules/local_search.py":
        return (
            "Target-specific rule for local_search.py: integrate new moves "
            "through _default_vns_operators() or the existing _vns(...) call "
            "path. Scheduler.py should keep calling _vns(candidate, "
            "_default_vns_operators(), ...)."
        )
    return ""


def _read_branch_code(
    branch_workspace: str,
    champion: ChampionState,
    *,
    research_surfaces: Optional[list[Any]] = None,
    include_operator_files: bool = True,
) -> Optional[str]:
    """Read branch research-surface files that differ from champion.

    Returns a formatted string showing modified files, or None if no
    differences are found or the workspace is unavailable.
    """
    sections: List[str] = []
    if include_operator_files:
        branch_ops_dir = os.path.join(branch_workspace, "operators")
        champ_ops_dir = os.path.join(champion.code_snapshot_path, "operators")
    else:
        branch_ops_dir = ""
        champ_ops_dir = ""

    if include_operator_files and os.path.isdir(branch_ops_dir):
        try:
            filenames = sorted(
                f for f in os.listdir(branch_ops_dir)
                if f.endswith(".py") and f not in ("__init__.py", "base.py")
            )
        except OSError:
            filenames = []

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

    for file_rel in _surface_file_targets(research_surfaces or []):
        branch_path = os.path.join(branch_workspace, file_rel)
        champ_path = os.path.join(champion.code_snapshot_path, file_rel)
        if not os.path.isfile(branch_path):
            continue
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
                f"### {file_rel} (branch research-surface version)\n"
                f"```python\n{branch_content}\n```"
            )

    return "\n\n".join(sections) if sections else None
