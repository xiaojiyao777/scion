"""Memory and experiment-feedback proposal tools.

This package preserves the historical ``scion.proposal.tools.feedback`` import
path while splitting memory, screening, holdout, runtime attribution, diagnosis,
scope/provenance, and payload compaction responsibilities.
"""

from __future__ import annotations

from scion.proposal.tools.feedback.attribution import (
    _compact_runtime_attribution_values,
    _runtime_attribution_field_is_interesting,
    _runtime_attribution_sort_key,
    _runtime_highlight_has_nonzero_numeric,
    _runtime_highlight_is_all_zero_numeric,
    _runtime_numeric_leaf_summaries,
    _safe_positive_int,
    _surface_runtime_attribution_payload,
)
from scion.proposal.tools.feedback.compaction import (
    _bound_compact_feedback_payload,
    _compact_feedback_value,
    _sanitize_memory_text,
)
from scion.proposal.tools.feedback.constants import (
    _COMPACT_FEEDBACK_LIST_ITEMS,
    _COMPACT_FEEDBACK_MAP_ITEMS,
    _COMPACT_FEEDBACK_PAYLOAD_CHARS,
    _COMPACT_FEEDBACK_STRING_CHARS,
    _COMPACT_FEEDBACK_TEXT_CHARS,
    _RUNTIME_ATTRIBUTION_PRIORITY_SUFFIXES,
    _RUNTIME_ATTRIBUTION_SUFFIXES,
)
from scion.proposal.tools.feedback.diagnosis import (
    _declared_mechanism_surface_names,
    _declared_solver_design_surface_names,
    _diagnostic_surface_priorities,
    _mechanism_surface_names_from_surfaces,
    _pre_protocol_failed_solver_design_surface_names,
    _research_diagnosis_payload,
    _screening_failed_solver_design_surface_names,
)
from scion.proposal.tools.feedback.holdout import FeedbackQueryHoldoutSummaryTool
from scion.proposal.tools.feedback.memory import MemoryQueryTool
from scion.proposal.tools.feedback.rows import (
    _holdout_step_payload,
    _screening_step_payload,
)
from scion.proposal.tools.feedback.runtime import FeedbackQueryRuntimeTool
from scion.proposal.tools.feedback.scope import (
    _FeedbackBoundaryScope,
    _feedback_boundary_scope,
    _feedback_payload_provenance,
    _feedback_step_provenance,
    _with_feedback_provenance,
)
from scion.proposal.tools.feedback.screening import FeedbackQueryScreeningTool
from scion.proposal.tools.feedback.stats import _eval_stats_payload, _screening_pair_stats

__all__ = [
    "FeedbackQueryHoldoutSummaryTool",
    "FeedbackQueryRuntimeTool",
    "FeedbackQueryScreeningTool",
    "MemoryQueryTool",
    "_COMPACT_FEEDBACK_LIST_ITEMS",
    "_COMPACT_FEEDBACK_MAP_ITEMS",
    "_COMPACT_FEEDBACK_PAYLOAD_CHARS",
    "_COMPACT_FEEDBACK_STRING_CHARS",
    "_COMPACT_FEEDBACK_TEXT_CHARS",
    "_RUNTIME_ATTRIBUTION_PRIORITY_SUFFIXES",
    "_RUNTIME_ATTRIBUTION_SUFFIXES",
    "_FeedbackBoundaryScope",
    "_feedback_boundary_scope",
    "_feedback_payload_provenance",
    "_feedback_step_provenance",
    "_with_feedback_provenance",
    "_bound_compact_feedback_payload",
    "_compact_feedback_value",
    "_sanitize_memory_text",
    "_compact_runtime_attribution_values",
    "_runtime_attribution_field_is_interesting",
    "_runtime_attribution_sort_key",
    "_runtime_highlight_has_nonzero_numeric",
    "_runtime_highlight_is_all_zero_numeric",
    "_runtime_numeric_leaf_summaries",
    "_safe_positive_int",
    "_surface_runtime_attribution_payload",
    "_eval_stats_payload",
    "_screening_pair_stats",
    "_screening_step_payload",
    "_holdout_step_payload",
    "_declared_mechanism_surface_names",
    "_declared_solver_design_surface_names",
    "_diagnostic_surface_priorities",
    "_mechanism_surface_names_from_surfaces",
    "_pre_protocol_failed_solver_design_surface_names",
    "_research_diagnosis_payload",
    "_screening_failed_solver_design_surface_names",
]
