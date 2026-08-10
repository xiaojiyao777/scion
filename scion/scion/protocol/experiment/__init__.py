from __future__ import annotations

from .facade import ExperimentProtocol
from .selection import SeedLedger, SplitManager, _select_evenly_spaced_cases
from .types import CaseLevelResult, PairedExecutionSpec
from .feedback import (
    _aggregate_case_feedback,
    _aggregate_pairs_to_case_level,
    _build_pattern_summary,
    _extract_case_features,
    _pair_feedback_counts,
)
from .runtime_observation import (
    _build_runtime_stats,
    _candidate_runtime_observation,
    _format_runtime_summary,
    _merge_runtime_observation,
    _record_runtime_sample,
    _runtime_audit_summary,
    _runtime_fields,
)
from .surface_runtime import (
    _finalize_surface_runtime_summary,
    _record_surface_runtime_sample,
    _surface_runtime_summary_template,
    _surface_runtime_summary_with_diagnostics,
)
from .failures import (
    _candidate_audit_failure_category,
    _candidate_process_failure_category,
    _format_runtime_failure_categories,
    _runtime_failure_summary,
    _runtime_failure_summary_from_audit,
)
from .surface_runtime import (
    _is_empty_runtime_evidence_value,
    _is_runtime_error_count_field,
    _is_runtime_true_evidence_field,
    _numeric_mapping_summary,
    _numeric_scalar_summary,
    _parse_surface_runtime_value,
    _surface_runtime_numeric_summary,
    _surface_runtime_value_key,
)
from .values import (
    _as_int,
    _as_truthy,
    _coerce_number,
    _increment_category,
    _is_json_scalar,
    _json_value,
    _parse_int,
    _round_runtime_number,
    _safe_int,
    _text_value,
)

__all__ = [
    "CaseLevelResult",
    "ExperimentProtocol",
    "PairedExecutionSpec",
    "SeedLedger",
    "SplitManager",
]
