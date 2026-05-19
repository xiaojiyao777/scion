from scion.proposal.tools import (
    ContextReadSurfaceTool,
    FeedbackQueryHoldoutSummaryTool,
    FeedbackQueryRuntimeTool,
    FeedbackQueryScreeningTool,
    MemoryQueryTool,
    ProposalToolRegistry,
)
from scion.proposal.tools.feedback import (
    _bound_compact_feedback_payload,
    _diagnostic_surface_priorities,
    _surface_runtime_attribution_payload,
)
from scion.proposal.tools.surface import (
    _drop_empty_items,
    _read_code_file_from_root,
    _surface_for_selected_or_patch_path,
)


def test_feedback_surface_package_facades_preserve_registry_compatibility() -> None:
    registry = ProposalToolRegistry.default_read_only()

    assert ContextReadSurfaceTool.name == "context.read_surface"
    assert MemoryQueryTool.name == "memory.query"
    assert FeedbackQueryScreeningTool.name == "feedback.query_screening"
    assert FeedbackQueryHoldoutSummaryTool.name == "feedback.query_holdout_summary"
    assert FeedbackQueryRuntimeTool.name == "feedback.query_runtime"
    assert "context.read_surface" in registry.list_tools()
    assert "feedback.query_runtime" in registry.list_tools()

    assert callable(_drop_empty_items)
    assert callable(_read_code_file_from_root)
    assert callable(_surface_for_selected_or_patch_path)
    assert callable(_bound_compact_feedback_payload)
    assert callable(_diagnostic_surface_priorities)
    assert callable(_surface_runtime_attribution_payload)
