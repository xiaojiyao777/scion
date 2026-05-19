"""Static contract/problem section summaries for algorithm-smoke feedback."""

from __future__ import annotations

from typing import Any, Mapping

from scion.proposal.tools.previews.algorithm_smoke_feedback_text import (
    _ALGORITHM_SMOKE_AGENT_LIST_ITEMS,
    _ALGORITHM_SMOKE_AGENT_TEXT_CHARS,
    _compact_agent_text,
    _compact_agent_text_list,
    _mapping_or_none,
)
from scion.proposal.tools.previews.common import _compact_preview_value
from scion.proposal.tools.surface import _drop_empty_items
from scion.proposal.tools.utils import _limit_text


def _algorithm_smoke_static_preview(
    raw_payload: Mapping[str, Any],
) -> dict[str, Any] | None:
    static_contract = _algorithm_smoke_contract_summary(
        raw_payload.get("static_contract")
    )
    problem_preview = _algorithm_smoke_problem_preview(raw_payload.get("problem_preview"))
    compact = _drop_empty_items(
        {
            "contract": static_contract,
            "problem": problem_preview,
        }
    )
    return compact or None


def _algorithm_smoke_telemetry_static_preview(value: Any) -> dict[str, Any] | None:
    preview = _mapping_or_none(value)
    if preview is None:
        return None
    return _drop_empty_items(
        {
            "passed": preview.get("passed"),
            "issues": _compact_agent_text_list(preview.get("issues")),
            "warnings": _compact_agent_text_list(preview.get("warnings")),
            "repair_hints": _compact_agent_text_list(preview.get("repair_hints")),
            "declared_mechanisms": _compact_agent_text_list(
                preview.get("declared_mechanisms")
            ),
            "checked_fields": _compact_agent_text_list(preview.get("checked_fields")),
            "required_calls": _compact_preview_value(preview.get("required_calls")),
        }
    )


def _algorithm_smoke_preview_section(value: Any) -> dict[str, Any] | None:
    section = _mapping_or_none(value)
    if section is None:
        return None
    compact = _drop_empty_items(
        {
            "passed": section.get("passed"),
            "contract": _algorithm_smoke_contract_summary(section.get("contract")),
            "failed_checks": _failed_check_summaries(section, prefix="section"),
            "errors": _compact_agent_text_list(section.get("errors")),
            "issues": _compact_agent_text_list(section.get("issues")),
            "patch": _algorithm_smoke_patch_summary(section.get("patch")),
            "hypothesis": _algorithm_smoke_hypothesis_summary(
                section.get("hypothesis")
            ),
            "problem_preview": _algorithm_smoke_problem_preview(
                section.get("problem_preview")
            ),
            "needs_hypothesis": section.get("needs_hypothesis"),
        }
    )
    return compact or None


def _algorithm_smoke_contract_summary(value: Any) -> dict[str, Any] | None:
    contract = _mapping_or_none(value)
    if contract is None:
        return None
    compact = _drop_empty_items(
        {
            "passed": contract.get("passed"),
            "check_count": contract.get("check_count"),
            "failed_checks": _compact_agent_text_list(
                contract.get("failed_checks")
            ),
            "failure_reason": _compact_agent_text(contract.get("failure_reason")),
        }
    )
    return compact or None


def _algorithm_smoke_problem_preview(value: Any) -> dict[str, Any] | None:
    preview = _mapping_or_none(value)
    if preview is None:
        return None
    compact = _drop_empty_items(
        {
            "passed": preview.get("passed"),
            "surface": preview.get("surface"),
            "issues": _compact_agent_text_list(preview.get("issues")),
            "failed_checks": _failed_check_summaries(preview, prefix="problem"),
            "workspace_materialized": preview.get("workspace_materialized"),
            "verification_run": preview.get("verification_run"),
        }
    )
    return compact or None


def _algorithm_smoke_patch_summary(value: Any) -> dict[str, Any] | None:
    patch = _mapping_or_none(value)
    if patch is None:
        return None
    compact_changes: list[dict[str, Any]] = []
    changes = patch.get("additional_changes")
    if isinstance(changes, (list, tuple)):
        for item in changes[:_ALGORITHM_SMOKE_AGENT_LIST_ITEMS]:
            if not isinstance(item, Mapping):
                continue
            compact_changes.append(
                _drop_empty_items(
                    {
                        "file_path": item.get("file_path"),
                        "action": item.get("action"),
                        "code_char_count": item.get("code_char_count"),
                        "code_digest": item.get("code_digest"),
                        "functions": _compact_agent_text_list(item.get("functions")),
                        "classes": _compact_agent_text_list(item.get("classes")),
                    }
                )
            )
    compact = _drop_empty_items(
        {
            "file_path": patch.get("file_path"),
            "action": patch.get("action"),
            "code_char_count": patch.get("code_char_count"),
            "code_digest": patch.get("code_digest"),
            "functions": _compact_agent_text_list(patch.get("functions")),
            "classes": _compact_agent_text_list(patch.get("classes")),
            "additional_change_count": patch.get("additional_change_count"),
            "additional_changes": compact_changes,
            "mechanism_changes": _compact_preview_value(
                patch.get("mechanism_changes")
            ),
        }
    )
    return compact or None


def _algorithm_smoke_hypothesis_summary(value: Any) -> dict[str, Any] | None:
    hypothesis = _mapping_or_none(value)
    if hypothesis is None:
        return None
    compact = _drop_empty_items(
        {
            "change_locus": hypothesis.get("change_locus"),
            "action": hypothesis.get("action"),
            "target_file": hypothesis.get("target_file"),
            "predicted_direction": hypothesis.get("predicted_direction"),
            "target_runtime_effect": hypothesis.get("target_runtime_effect"),
            "novelty_signature_keys": _compact_agent_text_list(
                hypothesis.get("novelty_signature_keys")
            ),
            "expected_telemetry": _compact_preview_value(
                hypothesis.get("expected_telemetry")
            ),
            "mechanism_changes": _compact_preview_value(
                hypothesis.get("mechanism_changes")
            ),
        }
    )
    return compact or None


def _failed_check_summaries(
    section: Mapping[str, Any] | None,
    *,
    prefix: str,
) -> list[dict[str, Any]]:
    if section is None:
        return []
    failed: list[dict[str, Any]] = []
    checks = section.get("checks")
    if isinstance(checks, (list, tuple)):
        for item in checks:
            if not isinstance(item, Mapping) or item.get("passed") is not False:
                continue
            failed.append(
                _drop_empty_items(
                    {
                        "name": f"{prefix}.{item.get('name')}",
                        "passed": False,
                        "severity": item.get("severity"),
                        "detail": _limit_text(
                            str(item.get("detail") or ""),
                            _ALGORITHM_SMOKE_AGENT_TEXT_CHARS,
                        ),
                    }
                )
            )
    existing = section.get("failed_checks")
    if isinstance(existing, (list, tuple)):
        for item in existing:
            text = _compact_agent_text(item)
            if text:
                failed.append({"name": f"{prefix}.{text}", "passed": False})
    return failed


__all__ = [
    "_algorithm_smoke_problem_preview",
    "_algorithm_smoke_preview_section",
    "_algorithm_smoke_static_preview",
    "_algorithm_smoke_telemetry_static_preview",
    "_failed_check_summaries",
]
