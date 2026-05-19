"""Compatibility facade for solver-design runtime smoke helpers."""

from __future__ import annotations

from typing import Any

from .audit import (
    _compact_runtime_audit_failure,
    _compact_runtime_smoke_payload,
    _problem_spec_for_runtime_audit,
    _runtime_smoke_audit_failure,
)
from .benchmark import (
    _compare_solver_design_raw_outputs,
    _compact_solver_design_micro_benchmark,
    _solver_design_micro_benchmark_issue,
    _solver_design_micro_benchmark_result,
)
from .cases import (
    _first_int,
    _load_runtime_smoke_yaml,
    _normalize_runtime_smoke_safe_roots,
    _resolve_smoke_instance_path,
    _resolve_smoke_instance,
    _runtime_smoke_audited_manifest_ref,
    _runtime_smoke_candidate_within_root,
    _runtime_smoke_case_public_payload,
    _runtime_smoke_case_source,
    _runtime_smoke_cases,
    _runtime_smoke_payload_provenance,
    _runtime_smoke_relative_path,
    _runtime_smoke_safe_data_roots,
    _runtime_smoke_safe_data_roots_from_manifest,
    _runtime_smoke_stage_arguments,
    _runtime_smoke_stage_value,
    _select_runtime_smoke_screening_cases,
    _string_list,
)
from .constants import (
    _ALGORITHM_SMOKE_DEFAULT_SEED,
    _ALGORITHM_SMOKE_LOW_EFFORT_MAX_ATTEMPTS,
    _ALGORITHM_SMOKE_LOW_EFFORT_MAX_ITERATIONS,
    _ALGORITHM_SMOKE_LOW_EFFORT_MAX_RUNTIME_RATIO,
    _ALGORITHM_SMOKE_LOW_EFFORT_MIN_CASES,
    _ALGORITHM_SMOKE_LOW_EFFORT_STOP_REASONS,
    _ALGORITHM_SMOKE_MAX_SCREENING_CASES,
    _ALGORITHM_SMOKE_TIMEOUT_SEC,
    _ALGORITHM_SMOKE_TIME_LIMIT_SEC,
)
from .effort import (
    _nonnegative_int,
    _runtime_stop_reason,
    _solver_design_low_effort_issue,
    _solver_design_patch_claims_search_effort,
    _solver_design_patch_paths,
    _solver_design_smoke_runtime_underspent,
    _solver_design_zero_effort_issue,
)
from .guidance import _solver_design_smoke_repair_guidance
from .models import _RuntimeSmokeCase
from .preview import _runtime_algorithm_smoke_preview
from .provider import _solver_design_smoke_provider
from .runner import (
    _redact_runtime_smoke_paths,
    _run_solver_design_smoke,
    _solver_run_failure_detail,
)
from .utils import (
    _attr,
    _float_or_none,
    _limit_text,
    _normalize_rel_path,
    _normalize_solver_design_surface,
)
from .workspace import (
    _apply_file_change_to_runtime_smoke_workspace,
    _apply_patch_to_runtime_smoke_workspace,
    _ensure_runtime_smoke_path_writable,
    _is_solver_design_runtime_patch_path,
    _runtime_smoke_base_workspace,
)

ProposalToolContext = Any

__all__ = [
    "_ALGORITHM_SMOKE_DEFAULT_SEED",
    "_ALGORITHM_SMOKE_LOW_EFFORT_MAX_ATTEMPTS",
    "_ALGORITHM_SMOKE_LOW_EFFORT_MAX_ITERATIONS",
    "_ALGORITHM_SMOKE_LOW_EFFORT_MAX_RUNTIME_RATIO",
    "_ALGORITHM_SMOKE_LOW_EFFORT_MIN_CASES",
    "_ALGORITHM_SMOKE_LOW_EFFORT_STOP_REASONS",
    "_ALGORITHM_SMOKE_MAX_SCREENING_CASES",
    "_ALGORITHM_SMOKE_TIMEOUT_SEC",
    "_ALGORITHM_SMOKE_TIME_LIMIT_SEC",
    "_RuntimeSmokeCase",
    "_apply_file_change_to_runtime_smoke_workspace",
    "_apply_patch_to_runtime_smoke_workspace",
    "_attr",
    "_compact_runtime_audit_failure",
    "_compact_runtime_smoke_payload",
    "_compact_solver_design_micro_benchmark",
    "_compare_solver_design_raw_outputs",
    "_ensure_runtime_smoke_path_writable",
    "_first_int",
    "_float_or_none",
    "_is_solver_design_runtime_patch_path",
    "_limit_text",
    "_load_runtime_smoke_yaml",
    "_normalize_runtime_smoke_safe_roots",
    "_nonnegative_int",
    "_normalize_rel_path",
    "_normalize_solver_design_surface",
    "_problem_spec_for_runtime_audit",
    "_redact_runtime_smoke_paths",
    "_resolve_smoke_instance",
    "_resolve_smoke_instance_path",
    "_run_solver_design_smoke",
    "_runtime_algorithm_smoke_preview",
    "_runtime_smoke_base_workspace",
    "_runtime_smoke_audited_manifest_ref",
    "_runtime_smoke_cases",
    "_runtime_smoke_audit_failure",
    "_runtime_smoke_candidate_within_root",
    "_runtime_smoke_case_public_payload",
    "_runtime_smoke_case_source",
    "_runtime_smoke_payload_provenance",
    "_runtime_smoke_relative_path",
    "_runtime_smoke_safe_data_roots",
    "_runtime_smoke_safe_data_roots_from_manifest",
    "_runtime_smoke_stage_arguments",
    "_runtime_smoke_stage_value",
    "_runtime_stop_reason",
    "_select_runtime_smoke_screening_cases",
    "_solver_design_low_effort_issue",
    "_solver_design_micro_benchmark_issue",
    "_solver_design_micro_benchmark_result",
    "_solver_design_patch_claims_search_effort",
    "_solver_design_patch_paths",
    "_solver_design_smoke_provider",
    "_solver_design_smoke_repair_guidance",
    "_solver_design_smoke_runtime_underspent",
    "_solver_design_zero_effort_issue",
    "_solver_run_failure_detail",
    "_string_list",
]
