"""Static mechanism telemetry preview for algorithm smoke."""

from __future__ import annotations

import ast
from typing import Any, Mapping

from scion.core.models import (
    HypothesisProposal,
    PatchProposal,
    mechanism_changes,
    patch_file_changes,
)
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
_ACTIVATION_HELPERS = frozenset({"record_iteration", "record_phase"})
_ACTIVATION_KEYWORDS: dict[str, tuple[str, ...]] = {
    "record_phase": ("name",),
    "record_iteration": ("phase",),
    "record_move": ("phase",),
}
_ISSUE_MISSING_ACTIVATION = "DECLARED_MECHANISM_ACTIVATION_MISSING"
_ISSUE_ZERO_PHASE_RUNTIME = "DECLARED_MECHANISM_PHASE_RUNTIME_ZERO"
_ISSUE_MISSING_RUNTIME = "DECLARED_MECHANISM_RUNTIME_MISSING"
_ISSUE_MISSING_EFFECT = "DECLARED_MECHANISM_EFFECT_MISSING"


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
    issue_codes: list[str] = []
    for mechanism in mechanisms:
        code_text = code_by_mechanism.get(mechanism, "")
        calls = _mechanism_call_evidence(code_text, mechanism)
        mechanism_activation_fields: list[str] = []
        mechanism_budget_fields: list[str] = []
        mechanism_effect_fields: list[str] = []
        for category, fields in sorted(explicit_fields.items()):
            for field in fields:
                field_text = str(field or "").strip()
                if not field_text or mechanism not in field_text:
                    continue
                checked_fields.append(field_text)
                lower_field = field_text.lower()
                if category == "activation" and (
                    "_iterations" in lower_field
                    or "phase_runtime" in lower_field
                    or "activation" in lower_field
                ):
                    mechanism_activation_fields.append(field_text)
                if category == "budget" and (
                    "phase_runtime" in lower_field
                    or "runtime" in lower_field
                    or "elapsed" in lower_field
                    or "budget" in lower_field
                ):
                    mechanism_budget_fields.append(field_text)
                if category == "effect" and (
                    "improvement_counts" in lower_field
                    or "best_delta" in lower_field
                    or "delta" in lower_field
                ):
                    mechanism_effect_fields.append(field_text)
        if mechanism_activation_fields and not any(
            calls.get(name) for name in _ACTIVATION_HELPERS
        ):
            issue_codes.append(_ISSUE_MISSING_ACTIVATION)
            issues.append(
                "Declared mechanism "
                f"{mechanism!r} requires direct activation instrumentation via "
                f"context.record_iteration('{mechanism}', positive_count) or "
                f"context.record_phase('{mechanism}', positive_elapsed_ms); "
                "context.record_move alone is effect telemetry, not activation."
            )
            _add_required_call(
                required_calls,
                mechanism,
                f"context.record_iteration('{mechanism}', positive_count)",
            )
            _add_required_call(
                required_calls,
                mechanism,
                f"context.record_phase('{mechanism}', positive_elapsed_ms)",
            )
        if calls.get("record_phase_zero_literal") and not calls.get(
            "record_phase_runtime_evidence"
        ):
            issue_codes.append(_ISSUE_ZERO_PHASE_RUNTIME)
            issues.append(
                "Declared mechanism "
                f"{mechanism!r} records context.record_phase with a literal "
                "zero/non-positive elapsed_ms value; phase/runtime evidence must "
                "use the measured positive duration of the mechanism path."
            )
            _add_required_call(
                required_calls,
                mechanism,
                f"context.record_phase('{mechanism}', positive_elapsed_ms)",
            )
        if mechanism_budget_fields and not calls.get("record_phase_runtime_evidence"):
            issue_codes.append(_ISSUE_MISSING_RUNTIME)
            issues.append(
                "Declared mechanism "
                f"{mechanism!r} requires context.record_phase('{mechanism}', "
                "positive_elapsed_ms) as budget/runtime evidence."
            )
            _add_required_call(
                required_calls,
                mechanism,
                f"context.record_phase('{mechanism}', positive_elapsed_ms)",
            )
        if mechanism_effect_fields and not calls.get("record_move"):
            issue_codes.append(_ISSUE_MISSING_EFFECT)
            issues.append(
                "Declared mechanism "
                f"{mechanism!r} requires context.record_move('{mechanism}', ..., "
                "delta=..., best_improved=...) for effect telemetry."
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
            "issue_codes": list(dict.fromkeys(issue_codes)),
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
    return bool(_mechanism_call_evidence(code_text, mechanism).get(method_name))


def _mechanism_call_evidence(code_text: str, mechanism: str) -> dict[str, bool]:
    evidence = {
        "record_phase": False,
        "record_phase_runtime_evidence": False,
        "record_phase_zero_literal": False,
        "record_iteration": False,
        "record_move": False,
    }
    if not str(code_text or "").strip():
        return evidence
    try:
        tree = ast.parse(code_text)
    except SyntaxError:
        return evidence
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        helper_name = _context_helper_call_name(node)
        if helper_name is None:
            continue
        if not _call_uses_declared_mechanism(node, helper_name, mechanism):
            continue
        evidence[helper_name] = True
        if helper_name == "record_phase":
            elapsed = _record_phase_elapsed_argument(node)
            literal = _literal_number(elapsed)
            if literal is not None and literal <= 0.0:
                evidence["record_phase_zero_literal"] = True
            elif elapsed is not None:
                evidence["record_phase_runtime_evidence"] = True
        elif helper_name == "record_iteration":
            evidence["record_iteration"] = True
        elif helper_name == "record_move":
            evidence["record_move"] = True
    return evidence


def _call_uses_declared_mechanism(
    node: ast.Call,
    helper_name: str,
    mechanism: str,
) -> bool:
    mechanism_text = str(mechanism or "").strip()
    if not mechanism_text:
        return False
    if node.args and _literal_string(node.args[0]) == mechanism_text:
        return True
    for keyword in node.keywords:
        if keyword.arg in _ACTIVATION_KEYWORDS.get(helper_name, ()):
            if _literal_string(keyword.value) == mechanism_text:
                return True
    return False


def _record_phase_elapsed_argument(node: ast.Call) -> ast.AST | None:
    if len(node.args) >= 2:
        return node.args[1]
    for keyword in node.keywords:
        if keyword.arg == "elapsed_ms":
            return keyword.value
    return None


def _literal_string(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _literal_number(node: ast.AST | None) -> float | None:
    if node is None:
        return None
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        if isinstance(node.value, bool):
            return None
        return float(node.value)
    if (
        isinstance(node, ast.UnaryOp)
        and isinstance(node.op, (ast.USub, ast.UAdd))
        and isinstance(node.operand, ast.Constant)
        and isinstance(node.operand.value, (int, float))
        and not isinstance(node.operand.value, bool)
    ):
        value = float(node.operand.value)
        return -value if isinstance(node.op, ast.USub) else value
    return None


__all__ = [
    "_combined_patch_code_for_mechanism",
    "_mechanism_telemetry_static_preview",
    "_patch_records_mechanism_call",
]
