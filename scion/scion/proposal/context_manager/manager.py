"""ContextManager orchestration for proposal prompt contexts."""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from scion.config.problem import ProblemSpec
from scion.core.forced_surface import validate_forced_surface_request
from scion.core.models import (
    Branch,
    ChampionState,
    HypothesisProposal,
    HypothesisRecord,
    PatchProposal,
    StepRecord,
    VerificationResult,
)
from scion.problem.providers import resolve_solver_design_prompt_provider
from scion.proposal.context.feedback import (
    _build_agent_quality_feedback,
    _build_champion_baselines,
    _build_experiment_history,
    _filter_hypothesis_prompt_steps,
)
from scion.proposal.context.problem_adapter import (
    _build_operator_interface_spec,
    _build_problem_object,
    _build_problem_summary,
    _build_solver_mechanics,
    _get_adapter_problem_spec,
)
from scion.proposal.context.surfaces import (
    _build_forced_surface_constraint,
    _build_inactive_surface_exclusion_block,
    _build_research_surfaces_block,
    _find_research_surface,
    _get_research_surfaces,
    _hypothesis_visible_research_surfaces,
    _include_operator_files_for_research_code,
    _is_solver_design_context_surface,
    _solver_design_surface_names,
    _surface_target_files_for_names,
)

from .code_context import (
    _build_solver_design_api_manifest,
    _build_solver_design_branch_current_integration_files,
    _read_champion_research_code,
    _read_reference_operators,
)
from .guidance import (
    _build_failure_pattern_warning,
    _build_objective_guidance,
    _build_objective_opportunity_profile,
    _build_objective_policy_guidance,
    _build_recent_objective_feedback,
    _build_search_control_guidance,
    _build_solver_design_boundary_guidance,
    _build_strategy_guidance,
    _get_family_taxonomy,
)
from .history import (
    _build_branch_direction_prompt,
    _extract_families_from_steps,
    _summarise_active_hypotheses,
    _summarise_blacklist,
    _summarise_siblings,
    build_exploration_coverage,
)
from .io import (
    _available_hypothesis_actions,
    _build_champion_stats,
    _expand_surface_targets_for_champion,
    _list_champion_operator_files,
    _list_champion_surface_files,
    _read_branch_code,
    _read_target_file_from_root,
)
from .rendering import _format_hypothesis
from .runtime import _build_runtime_feedback, _build_runtime_failure_guidance

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
            solver_design_prompt_provider = resolve_solver_design_prompt_provider(
                problem_spec=problem_spec,
                adapter=self._adapter,
            )
            ctx["solver_design_api_manifest"] = _build_solver_design_api_manifest(
                source_root=source_root,
                champion_root=champion.code_snapshot_path,
                target_file=hypothesis.target_file,
                provider=solver_design_prompt_provider,
            )
            ctx["solver_design_branch_current_integration_files"] = (
                _build_solver_design_branch_current_integration_files(
                    source_root=source_root,
                    champion_root=champion.code_snapshot_path,
                    target_file=hypothesis.target_file,
                    provider=solver_design_prompt_provider,
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
