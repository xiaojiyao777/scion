"""Static mechanism telemetry preview for algorithm smoke."""

from __future__ import annotations

import ast
from typing import Any, Mapping

from scion.core.models import HypothesisProposal, PatchProposal, mechanism_changes, patch_file_changes
from scion.proposal.tools.models import ProposalToolContext
from scion.proposal.tools.previews.common import _contract_problem_spec
from scion.proposal.tools.surface import _drop_empty_items
from scion.runtime.audit import normalize_surface_name
from scion.runtime.telemetry_guard import (
    declared_mechanism_runtime_probes,
    find_research_surface,
    normalize_expected_telemetry,
)

_CONTEXT_HELPER_ALLOWED_KEYWORDS: dict[str, frozenset[str]] = {
    "record_phase": frozenset({"name", "elapsed_ms"}),
    "record_iteration": frozenset({"phase", "count"}),
    "record_move": frozenset(
        {"phase", "attempted", "accepted", "delta", "best_improved"}
    ),
}


def _mechanism_telemetry_static_preview(
    context: ProposalToolContext,
    hypothesis: HypothesisProposal,
    patch: PatchProposal,
) -> dict[str, Any] | None:
    mechanisms = [change.id for change in mechanism_changes(hypothesis)]
    signature_issues = _context_helper_signature_issues(patch)
    if not mechanisms:
        if not signature_issues:
            return None
        return _drop_empty_items(
            {
                "passed": False,
                "issues": signature_issues,
                "repair_hints": _telemetry_repair_hints(),
            }
        )
    explicit_fields = _explicit_and_declared_mechanism_fields(
        context,
        hypothesis,
        mechanisms,
    )
    if not explicit_fields and not signature_issues:
        return None

    code_by_mechanism = {
        mechanism: _combined_patch_code_for_mechanism(patch, mechanism)
        for mechanism in mechanisms
    }
    issues: list[str] = list(signature_issues)
    warnings: list[str] = []
    checked_fields: list[str] = []
    required_calls: dict[str, list[str]] = {}
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
                        _add_required_call(
                            required_calls,
                            mechanism,
                            f"context.record_phase('{mechanism}', positive_elapsed_ms)",
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
                        _add_required_call(
                            required_calls,
                            mechanism,
                            f"context.record_iteration('{mechanism}', positive_count)",
                        )
                if category == "budget" and "phase_runtime" in lower_field:
                    if not _patch_records_mechanism_call(
                        code_text,
                        "record_phase",
                        mechanism,
                    ):
                        issues.append(
                            f"{field_text} requires context.record_phase('{mechanism}', positive_elapsed) as budget/runtime evidence."
                        )
                        _add_required_call(
                            required_calls,
                            mechanism,
                            f"context.record_phase('{mechanism}', positive_elapsed_ms)",
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
                        issues.append(
                            f"{field_text} requires context.record_move('{mechanism}', ..., delta=..., best_improved=...) evidence."
                        )
                        _add_required_call(
                            required_calls,
                            mechanism,
                            (
                                f"context.record_move('{mechanism}', attempted=1, "
                                "accepted=accepted_flag, delta=objective_delta, "
                                "best_improved=best_improved_flag)"
                            ),
                        )
    if not checked_fields and not issues:
        return None
    return _drop_empty_items(
        {
            "passed": not issues,
            "declared_mechanisms": mechanisms,
            "checked_fields": list(dict.fromkeys(checked_fields)),
            "required_calls": {
                mechanism: list(dict.fromkeys(calls))
                for mechanism, calls in required_calls.items()
                if calls
            },
            "issues": list(dict.fromkeys(issues)),
            "warnings": list(dict.fromkeys(warnings)),
            "repair_hints": _telemetry_repair_hints() if issues else [],
        }
    )


def _explicit_and_declared_mechanism_fields(
    context: ProposalToolContext,
    hypothesis: HypothesisProposal,
    mechanisms: list[str],
) -> dict[str, tuple[str, ...]]:
    claims = normalize_expected_telemetry(
        getattr(hypothesis, "expected_telemetry", {}) or {}
    )
    fields: dict[str, list[str]] = {
        category: list(values)
        for category, values in claims.items()
        if values
    }
    problem_spec = _contract_problem_spec(context)
    surface_name = normalize_surface_name(getattr(hypothesis, "change_locus", None))
    surface = find_research_surface(problem_spec, surface_name)
    if surface is not None:
        for probe in declared_mechanism_runtime_probes(
            problem_spec=problem_spec,
            surface=surface,
            declared_mechanisms=mechanisms,
        ):
            fields.setdefault(probe.category, []).append(probe.field)
    return {
        category: tuple(dict.fromkeys(str(field) for field in values if str(field)))
        for category, values in fields.items()
        if values
    }


def _context_helper_signature_issues(patch: PatchProposal) -> list[str]:
    issues: list[str] = []
    for change in patch_file_changes(patch):
        code = str(change.code_content or "")
        if not code.strip():
            continue
        try:
            tree = ast.parse(code)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            helper_name = _context_helper_call_name(node)
            if helper_name is None:
                continue
            allowed = _CONTEXT_HELPER_ALLOWED_KEYWORDS[helper_name]
            unsupported = [
                str(keyword.arg)
                for keyword in node.keywords
                if keyword.arg is not None and keyword.arg not in allowed
            ]
            if any(keyword.arg is None for keyword in node.keywords):
                unsupported.append("**kwargs")
            if not unsupported:
                continue
            issues.append(
                f"{change.file_path}: context.{helper_name} does not accept keyword(s): "
                f"{', '.join(dict.fromkeys(unsupported))}."
            )
    return list(dict.fromkeys(issues))


def _add_required_call(
    target: dict[str, list[str]],
    mechanism: str,
    call: str,
) -> None:
    target.setdefault(mechanism, []).append(call)


def _context_helper_call_name(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Attribute) and func.attr in _CONTEXT_HELPER_ALLOWED_KEYWORDS:
        return func.attr
    if isinstance(func, ast.Name) and func.id in _CONTEXT_HELPER_ALLOWED_KEYWORDS:
        return func.id
    return None


def _telemetry_repair_hints() -> list[str]:
    return [
        (
            "Add the missing telemetry record call using the exact declared "
            "mechanism id before rerunning algorithm smoke."
        ),
        (
            "Preserve records that already satisfied activation/effect/budget; "
            "do not replace a passed category while fixing another one."
        ),
        (
            "Use context.record_phase(name, elapsed_ms), "
            "context.record_iteration(phase='search', count=1), and "
            "context.record_move(phase='search', attempted=1, accepted=0, "
            "delta=None, best_improved=0)."
        ),
    ]


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
