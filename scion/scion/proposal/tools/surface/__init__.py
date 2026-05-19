"""Surface discovery and read helpers for proposal tools.

This package preserves the historical ``scion.proposal.tools.surface`` import
path while keeping metadata, payload compaction, code reads, and solver-design
support artifacts in focused modules.
"""

from __future__ import annotations

from scion.proposal.tools.surface.compaction import (
    _coerce_compact_list,
    _compact_mapping_payload,
    _compact_text,
    _drop_empty_items,
)
from scion.proposal.tools.surface.constants import (
    _COMPACT_SURFACE_CODE_CHARS,
    _COMPACT_SURFACE_HINT_CHARS,
    _COMPACT_SURFACE_INTERFACE_CHARS,
    _COMPACT_SURFACE_LIST_ITEMS,
    _COMPACT_SURFACE_MAP_ITEMS,
    _COMPACT_SURFACE_SECTIONS,
    _COMPACT_SURFACE_TEXT_CHARS,
    _FULL_SURFACE_CODE_CHARS,
    _NONEMPTY_SEQUENCE_NOVELTY_FIELDS,
    _SEMANTIC_SIGNATURE_SCALAR_STRING_CHARS,
)
from scion.proposal.tools.surface.metadata import (
    _allowed_surface_names_for_context,
    _find_surface,
    _first_concrete_target,
    _surface_allowed_actions,
    _surface_for_hypothesis,
    _surface_for_patch_path,
    _surface_for_selected_or_patch_path,
    _surface_function_signatures,
    _surface_list_for_context,
    _surface_name,
    _surface_novelty_signature_requirement,
    _surface_permission_summary,
    _surface_read_boundary_violation,
    _surface_required_functions,
    _surface_return_values,
    _surface_target_files,
    _surfaces,
    _target_declared,
)
from scion.proposal.tools.surface.payloads import (
    _compact_surface_interface_summary,
    _surface_contract_metadata,
    _surface_interface_summary,
    _surface_listing_payload,
    _surface_payload,
    _surface_read_payload,
    _surface_section_paths,
    _target_artifact_preview,
)
from scion.proposal.tools.surface.readers import (
    _path_has_symlink_component,
    _read_champion_file,
    _read_code_file_from_root,
    _surface_code_read_root,
)
from scion.proposal.tools.surface.support_artifacts import (
    _python_api_summary_for_file,
    _python_function_signature,
    _read_solver_design_support_artifacts,
    _solver_design_support_candidate_paths,
)
from scion.proposal.tools.surface.tool import (
    ContextReadSurfaceTool,
    _surface_code_char_limit,
)

__all__ = [
    "ContextReadSurfaceTool",
    "_COMPACT_SURFACE_CODE_CHARS",
    "_FULL_SURFACE_CODE_CHARS",
    "_COMPACT_SURFACE_TEXT_CHARS",
    "_COMPACT_SURFACE_HINT_CHARS",
    "_COMPACT_SURFACE_INTERFACE_CHARS",
    "_COMPACT_SURFACE_LIST_ITEMS",
    "_COMPACT_SURFACE_MAP_ITEMS",
    "_SEMANTIC_SIGNATURE_SCALAR_STRING_CHARS",
    "_NONEMPTY_SEQUENCE_NOVELTY_FIELDS",
    "_COMPACT_SURFACE_SECTIONS",
    "_coerce_compact_list",
    "_compact_mapping_payload",
    "_compact_text",
    "_drop_empty_items",
    "_allowed_surface_names_for_context",
    "_find_surface",
    "_first_concrete_target",
    "_surface_allowed_actions",
    "_surface_for_hypothesis",
    "_surface_for_patch_path",
    "_surface_for_selected_or_patch_path",
    "_surface_function_signatures",
    "_surface_list_for_context",
    "_surface_name",
    "_surface_novelty_signature_requirement",
    "_surface_permission_summary",
    "_surface_read_boundary_violation",
    "_surface_required_functions",
    "_surface_return_values",
    "_surface_target_files",
    "_surfaces",
    "_target_declared",
    "_surface_payload",
    "_surface_listing_payload",
    "_surface_read_payload",
    "_surface_interface_summary",
    "_surface_contract_metadata",
    "_compact_surface_interface_summary",
    "_surface_section_paths",
    "_target_artifact_preview",
    "_surface_code_char_limit",
    "_read_champion_file",
    "_read_code_file_from_root",
    "_surface_code_read_root",
    "_path_has_symlink_component",
    "_read_solver_design_support_artifacts",
    "_solver_design_support_candidate_paths",
    "_python_api_summary_for_file",
    "_python_function_signature",
]
