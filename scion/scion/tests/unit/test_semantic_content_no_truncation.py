from __future__ import annotations

from scion.contract.gate import _syntax_source_detail
from scion.protocol.experiment.failures import (
    _format_runtime_failure_categories,
    _runtime_failure_summary,
)
from scion.protocol.experiment.phase_telemetry import _format_phase_telemetry_summary
from scion.protocol.experiment.runtime_observation import (
    _format_runtime_counter_summary,
)
from scion.protocol.experiment.values import _json_value
from scion.verification.state_mutation import _legacy_result_reasons


def test_semantic_text_and_collections_preserve_long_tail() -> None:
    long_text = "semantic-content-" + "x" * 1200 + "-complete-tail"
    values = [f"value-{index}" for index in range(30)]
    mapping = {f"field-{index}": index for index in range(30)}

    projected = _json_value(
        {
            "long_text": long_text,
            "values": values,
            "mapping": mapping,
        }
    )

    assert projected["long_text"] == long_text
    assert projected["values"] == values
    assert projected["mapping"] == mapping
    assert _runtime_failure_summary(
        category="runtime_error",
        code="complete-code",
        surface="solver_design",
        component="solver",
        detail_summary=long_text,
    )["detail_summary"] == long_text


def test_semantic_lists_and_rendered_details_preserve_every_item() -> None:
    reasons = [f"reason-{index}" for index in range(12)]
    source_lines = [f"line-{index}-" + "x" * 150 for index in range(8)]
    source = "\n".join(source_lines)
    counters = {f"declared_counter_{index}": index + 1 for index in range(16)}
    buckets = {f"bucket-{index}": {"count": index} for index in range(12)}
    categories = {f"category-{index}": index + 1 for index in range(12)}

    assert _legacy_result_reasons({"reasons": reasons}) == reasons
    source_detail = _syntax_source_detail(source)
    assert source_lines[-1] in source_detail
    counter_summary = _format_runtime_counter_summary(counters)
    assert "declared_counter_15:16" in counter_summary
    phase_summary = _format_phase_telemetry_summary(
        {"runtime_observed_pairs": 1, "buckets": buckets}
    )
    assert "bucket-11" in phase_summary
    failure_summary = _format_runtime_failure_categories(categories)
    assert "category-11:12" in failure_summary
