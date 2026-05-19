"""Shared helpers for proposal preview tools."""

from __future__ import annotations

import ast
import hashlib
import json
import uuid
from typing import Any, Mapping

from scion.contract.gate import ContractGate
from scion.core.models import (
    ChampionState,
    PatchFileChange,
    PatchProposal,
    patch_file_changes,
)
from scion.core.paths import normalize_relative_patch_path
from scion.problem.bridge import legacy_problem_spec_from_v1
from scion.proposal.context_manager import _get_adapter_problem_spec
from scion.proposal.tools.models import ProposalToolContext
from scion.proposal.tools.surface import _drop_empty_items
from scion.proposal.tools.utils import _attr, _limit_text, _model_payload, _strip_forbidden_value

_COMPACT_FEEDBACK_LIST_ITEMS = 8
_PREVIEW_CHECK_DETAIL_CHARS = 900
_PREVIEW_FAILURE_REASON_CHARS = 1200
_PREVIEW_MAX_CHECKS = 12
_PREVIEW_PROBLEM_ISSUE_CHARS = 500
_PREVIEW_PROBLEM_MAX_CHECKS = 8
_SEMANTIC_SIGNATURE_SCALAR_STRING_CHARS = 120
_NONEMPTY_SEQUENCE_NOVELTY_FIELDS = frozenset(
    {
        "selected_components",
        "deep_components_selected",
    }
)

def _compact_preview_value(value: Any, *, max_chars: int = 160) -> Any:
    value = _strip_forbidden_value(value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return _limit_text(value, max_chars)
    if isinstance(value, Mapping):
        compact: dict[str, Any] = {}
        for idx, (key, item) in enumerate(
            sorted(value.items(), key=lambda pair: str(pair[0]))
        ):
            if idx >= _COMPACT_FEEDBACK_LIST_ITEMS:
                break
            compact[str(key)] = _compact_preview_value(item, max_chars=max_chars)
        return compact
    if isinstance(value, (list, tuple)):
        return [
            _compact_preview_value(item, max_chars=max_chars)
            for item in list(value)[:_COMPACT_FEEDBACK_LIST_ITEMS]
        ]
    return _limit_text(str(value), max_chars)

def _contract_gate(context: ProposalToolContext) -> ContractGate:
    spec = _contract_problem_spec(context)
    return ContractGate(
        spec,
        operator_execute_signature=_operator_execute_signature(context),
        champion_snapshot_path=str(_attr(context.champion, "code_snapshot_path") or "")
        or None,
    )

def _contract_problem_spec(context: ProposalToolContext) -> Any:
    spec = _get_adapter_problem_spec(context.adapter) or context.problem_spec
    if spec is None:
        raise ValueError("proposal tool context has no problem_spec")
    if hasattr(spec, "operator_categories"):
        return spec
    if _attr(spec, "spec_version") == "problem-v1" or hasattr(
        spec, "operator_interface"
    ):
        return legacy_problem_spec_from_v1(spec)
    return spec

def _operator_execute_signature(context: ProposalToolContext) -> str | None:
    adapter_spec = _get_adapter_problem_spec(context.adapter)
    for spec in (adapter_spec, context.problem_spec):
        operator_interface = _attr(spec, "operator_interface")
        execute_signature = _attr(operator_interface, "execute_signature")
        if execute_signature:
            return str(execute_signature)
    return None

def _drop_internal_preview_objects(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _drop_internal_preview_objects(item)
            for key, item in value.items()
            if str(key) not in {"hypothesis_object", "patch_object"}
        }
    if isinstance(value, list):
        return [_drop_internal_preview_objects(item) for item in value]
    return value

def _patch_path_error(file_path: str) -> str | None:
    try:
        normalize_relative_patch_path(file_path)
    except ValueError as exc:
        return str(exc)
    return None

def _patch_preview_summary(patch: PatchProposal) -> dict[str, Any]:
    code_content = str(patch.code_content or "")
    additional = [
        _patch_file_change_preview_summary(change)
        for change in patch_file_changes(patch)[1:]
    ]
    return {
        "file_path": patch.file_path,
        "action": patch.action,
        "code_char_count": len(code_content),
        "code_digest": hashlib.sha256(code_content.encode("utf-8")).hexdigest(),
        "functions": _module_level_functions(code_content),
        "classes": _module_classes(code_content),
        "additional_change_count": len(additional),
        "additional_changes": additional,
        "mechanism_changes": _compact_preview_value(
            [
                {"id": change.id, "change_type": change.change_type}
                for change in getattr(patch, "mechanism_changes", ()) or ()
            ]
        ),
        "checks": [],
    }

def _patch_file_change_preview_summary(change: PatchFileChange) -> dict[str, Any]:
    code_content = str(change.code_content or "")
    return {
        "file_path": change.file_path,
        "action": change.action,
        "code_char_count": len(code_content),
        "code_digest": hashlib.sha256(code_content.encode("utf-8")).hexdigest(),
        "functions": _module_level_functions(code_content),
        "classes": _module_classes(code_content),
    }

def _compact_problem_preview(
    preview: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    if preview is None:
        return None
    return {
        "passed": bool(preview.get("passed")),
        "surface": preview.get("surface"),
        "issues": _problem_preview_issues(preview),
        "checks": _compact_problem_preview_checks(preview.get("checks")),
        "workspace_materialized": bool(preview.get("workspace_materialized", False)),
        "verification_run": bool(preview.get("verification_run", False)),
    }

def _problem_preview_issues(preview: Mapping[str, Any]) -> list[str]:
    issues = preview.get("issues", [])
    if isinstance(issues, str):
        values = [issues]
    else:
        try:
            values = [str(issue) for issue in issues if str(issue)]
        except TypeError:
            values = []
    return [
        _limit_text(issue, _PREVIEW_PROBLEM_ISSUE_CHARS)
        for issue in values[:_PREVIEW_PROBLEM_MAX_CHECKS]
    ]

def _compact_problem_preview_checks(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    checks: list[dict[str, Any]] = []
    for item in value[:_PREVIEW_PROBLEM_MAX_CHECKS]:
        if not isinstance(item, Mapping):
            continue
        checks.append(
            {
                "name": item.get("name"),
                "passed": bool(item.get("passed")),
                "detail": _limit_text(
                    str(item.get("detail", "")),
                    _PREVIEW_PROBLEM_ISSUE_CHARS,
                ),
            }
        )
    return checks

def _problem_surface_preview(
    context: ProposalToolContext,
    patch: PatchProposal,
    surface: Any | None,
) -> dict[str, Any] | None:
    adapter = context.adapter
    preview = getattr(adapter, "preview_research_surface_patch", None)
    if not callable(preview):
        return None
    try:
        payload = preview(patch=patch, surface=surface)
    except Exception as exc:
        return {
            "passed": False,
            "issues": [f"problem preview hook failed: {exc}"],
            "workspace_materialized": False,
            "verification_run": False,
        }
    if not isinstance(payload, Mapping):
        return {
            "passed": False,
            "issues": ["problem preview hook returned non-mapping payload"],
            "workspace_materialized": False,
            "verification_run": False,
        }
    normalized = dict(payload)
    normalized.setdefault("passed", False)
    normalized.setdefault("workspace_materialized", False)
    normalized.setdefault("verification_run", False)
    return normalized

def _module_level_functions(code_content: str) -> list[str]:
    import ast

    try:
        tree = ast.parse(code_content)
    except SyntaxError:
        return []
    return [
        node.name
        for node in getattr(tree, "body", [])
        if isinstance(node, ast.FunctionDef)
    ]

def _module_classes(code_content: str) -> list[str]:
    import ast

    try:
        tree = ast.parse(code_content)
    except SyntaxError:
        return []
    return [
        node.name
        for node in getattr(tree, "body", [])
        if isinstance(node, ast.ClassDef)
    ]

def _artifact_id(kind: str, value: Any) -> str:
    payload = json.dumps(_model_payload(value), sort_keys=True, default=str)
    digest = uuid.uuid5(uuid.NAMESPACE_URL, f"{kind}:{payload}").hex[:16]
    return f"{kind}-{digest}"

def _champion_version(champion: ChampionState | None) -> int:
    return int(_attr(champion, "version", 0) or 0)

def _hypothesis_selected_surface(
    hypothesis: HypothesisProposal | None,
) -> str | None:
    if hypothesis is None:
        return None
    value = str(getattr(hypothesis, "change_locus", "") or "").strip()
    return value or None


__all__ = [
    "_COMPACT_FEEDBACK_LIST_ITEMS",
    "_NONEMPTY_SEQUENCE_NOVELTY_FIELDS",
    "_PREVIEW_CHECK_DETAIL_CHARS",
    "_PREVIEW_FAILURE_REASON_CHARS",
    "_PREVIEW_MAX_CHECKS",
    "_PREVIEW_PROBLEM_ISSUE_CHARS",
    "_PREVIEW_PROBLEM_MAX_CHECKS",
    "_SEMANTIC_SIGNATURE_SCALAR_STRING_CHARS",
    "_artifact_id",
    "_champion_version",
    "_compact_preview_value",
    "_compact_problem_preview",
    "_compact_problem_preview_checks",
    "_contract_gate",
    "_contract_problem_spec",
    "_drop_internal_preview_objects",
    "_hypothesis_selected_surface",
    "_module_classes",
    "_module_level_functions",
    "_operator_execute_signature",
    "_patch_file_change_preview_summary",
    "_patch_path_error",
    "_patch_preview_summary",
    "_problem_preview_issues",
    "_problem_surface_preview",
]
