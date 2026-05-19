"""Static mechanism telemetry preview for algorithm smoke."""

from __future__ import annotations

from typing import Any

from scion.core.models import HypothesisProposal, PatchProposal, mechanism_changes, patch_file_changes
from scion.proposal.tools.surface import _drop_empty_items
from scion.runtime.telemetry_guard import normalize_expected_telemetry

def _mechanism_telemetry_static_preview(
    hypothesis: HypothesisProposal,
    patch: PatchProposal,
) -> dict[str, Any] | None:
    mechanisms = [change.id for change in mechanism_changes(hypothesis)]
    if not mechanisms:
        return None
    claims = normalize_expected_telemetry(
        getattr(hypothesis, "expected_telemetry", {}) or {}
    )
    explicit_fields = {
        category: tuple(fields)
        for category, fields in claims.items()
        if fields
    }
    if not explicit_fields:
        return None

    code_by_mechanism = {
        mechanism: _combined_patch_code_for_mechanism(patch, mechanism)
        for mechanism in mechanisms
    }
    issues: list[str] = []
    warnings: list[str] = []
    checked_fields: list[str] = []
    for mechanism in mechanisms:
        code_text = code_by_mechanism.get(mechanism, "")
        for category, fields in sorted(explicit_fields.items()):
            for field in fields:
                field_text = str(field or "").strip()
                if not field_text or mechanism not in field_text:
                    continue
                checked_fields.append(field_text)
                lower_field = field_text.lower()
                if category == "activation" and "phase_runtime" in lower_field:
                    if not _patch_records_mechanism_call(
                        code_text,
                        "record_phase",
                        mechanism,
                    ):
                        issues.append(
                            f"{field_text} requires context.record_phase('{mechanism}', positive_elapsed) on the active path."
                        )
                if category == "activation" and "_iterations" in lower_field:
                    if not _patch_records_mechanism_call(
                        code_text,
                        "record_iteration",
                        mechanism,
                    ):
                        issues.append(
                            f"{field_text} requires context.record_iteration('{mechanism}', positive_count) on the active path."
                        )
                if category == "effect" and (
                    "improvement_counts" in lower_field
                    or "best_delta" in lower_field
                    or "delta" in lower_field
                ):
                    if not _patch_records_mechanism_call(
                        code_text,
                        "record_move",
                        mechanism,
                    ):
                        warnings.append(
                            f"{field_text} usually needs context.record_move('{mechanism}', ..., delta=..., best_improved=...) evidence."
                        )
    if not checked_fields:
        return None
    return _drop_empty_items(
        {
            "passed": not issues,
            "declared_mechanisms": mechanisms,
            "checked_fields": list(dict.fromkeys(checked_fields)),
            "issues": list(dict.fromkeys(issues)),
            "warnings": list(dict.fromkeys(warnings)),
            "repair_hints": [
                "Add the missing telemetry record call using the exact declared mechanism id before rerunning algorithm smoke."
            ]
            if issues
            else [],
        }
    )

def _combined_patch_code_for_mechanism(
    patch: PatchProposal,
    mechanism: str,
) -> str:
    chunks: list[str] = []
    mechanism_token = str(mechanism or "").strip()
    for change in patch_file_changes(patch):
        code = str(change.code_content or "")
        if not mechanism_token or mechanism_token in code:
            chunks.append(code)
    return "\n\n".join(chunks)

def _patch_records_mechanism_call(
    code_text: str,
    method_name: str,
    mechanism: str,
) -> bool:
    needle = f".{method_name}("
    if needle not in code_text and f"{method_name}(" not in code_text:
        return False
    call_targets = (
        f'"{mechanism}"',
        f"'{mechanism}'",
    )
    return any(target in code_text for target in call_targets)


__all__ = [
    "_combined_patch_code_for_mechanism",
    "_mechanism_telemetry_static_preview",
    "_patch_records_mechanism_call",
]
