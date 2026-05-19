"""Compatibility facade for proposal context assembly.

Historically this API lived in ``scion.proposal.context_manager`` as a single
module. Keep re-exporting the public and test-facing helpers from the package
root so existing imports continue to work.
"""
from __future__ import annotations

from scion.proposal.context.feedback import (
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
from scion.proposal.context.problem_adapter import (
    _build_operator_interface_spec,
    _build_problem_object,
    _build_problem_summary,
    _build_solver_mechanics,
    _get_adapter_problem_spec,
)
from scion.proposal.context.surfaces import (
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
    _build_objective_steering,
    _build_recent_objective_feedback,
    _build_search_control_guidance,
    _build_solver_design_boundary_guidance,
    _build_strategy_guidance,
    _get_family_taxonomy,
    _median,
)
from .history import (
    _build_branch_direction_prompt,
    _count_trailing_failures,
    _extract_families_from_steps,
    _extract_mechanism_label,
    _get_step_status,
    _make_family_id,
    _summarise_active_hypotheses,
    _summarise_blacklist,
    _summarise_siblings,
    assign_family_id,
    build_exploration_coverage,
)
from .io import (
    _append_unique,
    _assigned_names_for_manifest,
    _available_hypothesis_actions,
    _build_champion_stats,
    _expand_surface_targets_for_champion,
    _list_champion_operator_files,
    _list_champion_surface_files,
    _python_api_manifest_for_file,
    _python_signature_text,
    _read_branch_code,
    _read_champion_operators,
    _read_solver_design_context_artifact,
    _read_surface_file,
    _read_target_file,
    _read_target_file_from_root,
)
from .manager import ContextManager
from .rendering import _format_hypothesis
from .runtime import (
    _SURFACE_RUNTIME_PRIORITY_SUFFIXES,
    _as_int,
    _build_runtime_feedback,
    _build_runtime_failure_guidance,
    _build_screening_failure_cause_line,
    _count_field,
    _extract_runtime_guard_line,
    _extract_screening_runtime_structured_feedback,
    _first_runtime_failure,
    _fmt_runtime,
    _get_runtime_failure_guidance_specs,
    _operator_stop_reason_counts,
    _runtime_failure_categories,
    _runtime_guidance_profile,
    _runtime_stat,
    _runtime_stop_reasons,
    _structured_runtime_count,
    _sum_runtime_field,
    _surface_runtime_field_interesting,
    _surface_runtime_numeric_note,
    _surface_runtime_numeric_stats_text,
    _surface_runtime_sort_key,
    _surface_runtime_summary_note,
    _telemetry_guard_summary_note,
)

__all__ = [
    name for name in globals()
    if name == "ContextManager"
    or (name.startswith("_") and not name.startswith("__"))
]
__all__.extend(["assign_family_id", "build_exploration_coverage"])
