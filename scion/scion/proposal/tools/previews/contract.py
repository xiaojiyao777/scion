"""Static contract preview tool and payload helpers."""

from __future__ import annotations

from typing import Any, Mapping

from scion.core.models import ContractResult, PatchProposal, patch_file_changes
from scion.proposal.tools.base import _BaseReadOnlyTool
from scion.proposal.tools.models import (
    ContractPreviewInput,
    ProposalExposureLevel,
    ProposalObservation,
    ProposalToolContext,
    ProposalToolPermission,
)
from scion.proposal.tools.previews.common import (
    _PREVIEW_CHECK_DETAIL_CHARS,
    _PREVIEW_FAILURE_REASON_CHARS,
    _PREVIEW_HYPOTHESIS_BOUND_CHECKS,
    _PREVIEW_MAX_CHECKS,
    _PREVIEW_STATEFUL_CHECKS_EXCLUDED,
    _compact_problem_preview,
    _compact_preview_value,
    _contract_gate,
    _drop_internal_preview_objects,
    _champion_version,
    _hypothesis_selected_surface,
    _problem_surface_preview,
)
from scion.proposal.tools.surface import (
    _drop_empty_items,
    _surface_for_selected_or_patch_path,
)
from scion.proposal.tools.utils import _attr, _limit_text

class ContractPreviewTool(_BaseReadOnlyTool):
    name = "proposal.contract_preview"
    input_schema = ContractPreviewInput
    permission = ProposalToolPermission.CONTRACT_PREVIEW
    max_result_chars = 60000

    def call(
        self,
        args: ContractPreviewInput,
        context: ProposalToolContext,
    ) -> ProposalObservation:
        from scion.proposal.tools.previews.schema import (
            _schema_preview_hypothesis_payload,
            _schema_preview_patch_payload,
        )

        payload: dict[str, Any] = {
            "passed": True,
            "hypothesis": None,
            "patch": None,
            "static_only": True,
            "workspace_materialized": False,
            "verification_run": False,
            "protocol_run": False,
            "decision_run": False,
            "validation_mode": "preview",
            "stateful_checks_excluded": list(_PREVIEW_STATEFUL_CHECKS_EXCLUDED),
            "hypothesis_bound_checks_skipped": [],
            "preview_degraded": False,
        }
        gate = _contract_gate(context)
        if args.hypothesis is None and args.patch is None:
            payload["passed"] = False
            payload["errors"] = ["Provide hypothesis and/or patch payload."]
        if args.hypothesis is not None:
            hypothesis_preview = _schema_preview_hypothesis_payload(
                context,
                args.hypothesis,
            )
            if hypothesis_preview["passed"]:
                result = gate.validate_hypothesis(
                    hypothesis_preview["hypothesis_object"],
                    [],
                    [],
                    current_champion_version=_champion_version(context.champion),
                )
                hypothesis_preview["contract"] = _contract_summary_payload(result)
                hypothesis_preview["validation_mode"] = "preview"
                hypothesis_preview["stateful_checks_excluded"] = list(
                    _PREVIEW_STATEFUL_CHECKS_EXCLUDED
                )
                hypothesis_preview["checks"] = _checks_payload(
                    result.checks,
                    detail_chars=_PREVIEW_CHECK_DETAIL_CHARS,
                    max_checks=_PREVIEW_MAX_CHECKS,
                )
                repair_templates = _repair_templates_payload(result.checks)
                if repair_templates:
                    hypothesis_preview["repair_templates"] = repair_templates
                hypothesis_preview["passed"] = result.passed
            payload["hypothesis"] = hypothesis_preview
            payload["passed"] = payload["passed"] and bool(hypothesis_preview["passed"])
        if args.patch is not None:
            patch_preview = _schema_preview_patch_payload(args.patch, context)
            if patch_preview["passed"]:
                hypothesis_object = None
                if (
                    args.hypothesis is not None
                    and payload["hypothesis"] is not None
                    and payload["hypothesis"].get("passed")
                ):
                    hypothesis_object = payload["hypothesis"].get("hypothesis_object")
                result = gate.validate_patch(
                    patch_preview["patch_object"],
                    approved_hypothesis=hypothesis_object,
                    validation_mode="preview",
                )
                contract_payload = _contract_result_payload(
                    result,
                    detail_chars=_PREVIEW_CHECK_DETAIL_CHARS,
                    max_checks=_preview_max_checks_for_patch(
                        patch_preview["patch_object"]
                    ),
                )
                patch_preview["contract"] = _contract_summary_payload(result)
                patch_preview["validation_mode"] = "preview"
                patch_preview["checks"] = contract_payload["checks"]
                skipped_checks = _preview_skipped_checks(result)
                degraded_diagnostics = _preview_degraded_diagnostics(result)
                patch_preview["hypothesis_bound_checks_skipped"] = list(
                    skipped_checks
                )
                if degraded_diagnostics:
                    patch_preview["preview_degraded"] = True
                    patch_preview["degraded_diagnostics"] = degraded_diagnostics
                    payload["preview_degraded"] = True
                for skipped in skipped_checks:
                    skipped_list = payload["hypothesis_bound_checks_skipped"]
                    if skipped not in skipped_list:
                        skipped_list.append(skipped)
                if contract_payload.get("repair_templates"):
                    patch_preview["repair_templates"] = contract_payload[
                        "repair_templates"
                    ]
                patch_preview["passed"] = result.passed
                if result.passed:
                    selected_surface = _hypothesis_selected_surface(hypothesis_object)
                    surface = _surface_for_selected_or_patch_path(
                        context,
                        patch_preview["patch_object"].file_path,
                        selected_surface,
                    )
                    problem_preview = _problem_surface_preview(
                        context,
                        patch_preview["patch_object"],
                        surface,
                    )
                    if problem_preview is not None:
                        patch_preview["problem_preview"] = _compact_problem_preview(
                            problem_preview
                        )
                        patch_preview["passed"] = bool(
                            patch_preview["passed"]
                        ) and bool(problem_preview.get("passed"))
                        payload["static_only"] = False
                if args.hypothesis is None:
                    patch_preview["needs_hypothesis"] = True
                    for skipped in _PREVIEW_HYPOTHESIS_BOUND_CHECKS:
                        if skipped not in patch_preview[
                            "hypothesis_bound_checks_skipped"
                        ]:
                            patch_preview[
                                "hypothesis_bound_checks_skipped"
                            ].append(skipped)
                        if skipped not in payload["hypothesis_bound_checks_skipped"]:
                            payload["hypothesis_bound_checks_skipped"].append(skipped)
                    patch_preview["passed"] = False
                    payload["incomplete"] = True
                    payload["needs_hypothesis"] = True
                else:
                    patch_preview["needs_hypothesis"] = False
            payload["patch"] = patch_preview
            payload["passed"] = payload["passed"] and bool(patch_preview["passed"])
        payload = _drop_internal_preview_objects(payload)
        issue_summary = _contract_preview_issue_summary(payload)
        if issue_summary:
            payload["issue_summary"] = issue_summary
        return self._observation(
            context,
            observation_type="contract_preview",
            summary=(
                "Static contract preview passed."
                if payload["passed"]
                else (
                    "Static contract preview needs an approved hypothesis."
                    if payload.get("needs_hypothesis")
                    else (
                        "Static contract preview found issues: "
                        f"{issue_summary}"
                        if issue_summary
                        else "Static contract preview found issues."
                    )
                )
            ),
            structured_payload=payload,
            exposure_level=ProposalExposureLevel.PUBLIC_SPEC,
        )


def _contract_result_payload(
    result: ContractResult,
    *,
    detail_chars: int = 2000,
    max_checks: int | None = None,
) -> dict[str, Any]:
    return {
        "passed": result.passed,
        "failure_reason": (
            _limit_text(
                str(result.failure_reason or ""),
                max(detail_chars, _PREVIEW_FAILURE_REASON_CHARS),
            )
            if result.failure_reason
            else None
        ),
        "checks": _checks_payload(
            result.checks,
            detail_chars=detail_chars,
            max_checks=max_checks,
        ),
        "repair_templates": _repair_templates_payload(result.checks),
    }


def _preview_max_checks_for_patch(patch: PatchProposal) -> int:
    return _PREVIEW_MAX_CHECKS * max(1, len(patch_file_changes(patch)))


def _contract_summary_payload(result: ContractResult) -> dict[str, Any]:
    failed_checks = [
        str(_attr(check, "name"))
        for check in result.checks
        if not bool(_attr(check, "passed"))
    ]
    return _drop_empty_items(
        {
            "passed": result.passed,
            "failure_reason": (
                _limit_text(
                    str(result.failure_reason or ""),
                    _PREVIEW_FAILURE_REASON_CHARS,
                )
                if result.failure_reason
                else None
            ),
            "check_count": len(result.checks),
            "failed_checks": failed_checks[:_PREVIEW_MAX_CHECKS],
            "preview_degraded": bool(_preview_degraded_diagnostics(result)),
            "hypothesis_bound_checks_skipped": list(_preview_skipped_checks(result)),
            "repair_templates": _repair_templates_payload(result.checks),
        }
    )


def _preview_skipped_checks(result: ContractResult) -> tuple[str, ...]:
    skipped: list[str] = []
    for check in result.checks:
        metadata = _attr(check, "metadata", {}) or {}
        if not isinstance(metadata, Mapping):
            continue
        if not metadata.get("preview_skipped"):
            continue
        name = str(metadata.get("skipped_check") or _attr(check, "name") or "").strip()
        if name and name not in skipped:
            skipped.append(name)
    return tuple(skipped)


def _preview_degraded_diagnostics(result: ContractResult) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    for check in result.checks:
        metadata = _attr(check, "metadata", {}) or {}
        if not isinstance(metadata, Mapping) or not metadata.get("preview_degraded"):
            continue
        diagnostics.append(
            {
                "name": _attr(check, "name"),
                "reason_code": metadata.get("reason_code"),
                "surface": metadata.get("surface"),
                "detail": _limit_text(
                    str(_attr(check, "detail", "")),
                    _PREVIEW_FAILURE_REASON_CHARS,
                ),
            }
        )
    return diagnostics


def _contract_preview_issue_summary(payload: Mapping[str, Any]) -> str:
    issues = _contract_preview_issue_strings(payload)
    if not issues:
        return ""
    return "; ".join(issues[:5])


def _contract_preview_issue_strings(value: Any) -> list[str]:
    issues: list[str] = []

    def add(text: Any) -> None:
        item = _limit_text(str(text or "").strip(), 700)
        if item and item not in issues:
            issues.append(item)

    def visit(item: Any, *, context: str = "") -> None:
        if isinstance(item, Mapping):
            failure_reason = item.get("failure_reason")
            if failure_reason:
                add(f"{context}: {failure_reason}" if context else failure_reason)
            for key in ("errors", "issues"):
                raw_values = item.get(key)
                if isinstance(raw_values, list):
                    for raw in raw_values:
                        if isinstance(raw, Mapping):
                            location = ".".join(
                                str(part) for part in raw.get("loc", ()) or ()
                            )
                            message = raw.get("msg") or raw.get("message") or raw
                            add(f"{location}: {message}" if location else message)
                        else:
                            add(raw)
                elif raw_values:
                    add(raw_values)
            name = item.get("name")
            if name and item.get("passed") is False:
                detail = item.get("detail")
                add(f"{name}: {detail}" if detail else name)
            contract = item.get("contract")
            if isinstance(contract, Mapping):
                failed_checks = contract.get("failed_checks")
                if isinstance(failed_checks, list):
                    for check_name in failed_checks:
                        add(check_name)
            for key, child in item.items():
                key_text = str(key)
                next_context = (
                    key_text if key_text in {"hypothesis", "patch"} else context
                )
                if key_text in {"hypothesis_object", "patch_object", "code_content"}:
                    continue
                visit(child, context=next_context)
        elif isinstance(item, list):
            for child in item:
                visit(child, context=context)

    visit(value)
    return issues


def _checks_payload(
    checks: Any,
    *,
    detail_chars: int = 2000,
    max_checks: int | None = None,
) -> list[dict[str, Any]]:
    check_list = list(checks)
    if max_checks is not None:
        check_list = check_list[:max_checks]
    payloads: list[dict[str, Any]] = []
    for check in check_list:
        metadata = _attr(check, "metadata", {}) or {}
        repair_template = (
            metadata.get("repair_template") if isinstance(metadata, Mapping) else None
        )
        payload = {
            "name": _attr(check, "name"),
            "passed": bool(_attr(check, "passed")),
            "severity": _attr(check, "severity"),
            "detail": _limit_text(str(_attr(check, "detail", "")), detail_chars),
            "elapsed_ms": _attr(check, "elapsed_ms"),
        }
        preview_metadata = _preview_check_metadata(metadata)
        if preview_metadata:
            payload["metadata"] = preview_metadata
        if repair_template:
            payload["repair_template"] = _compact_preview_value(
                repair_template,
                max_chars=360,
            )
        payloads.append(payload)
    return payloads


def _preview_check_metadata(metadata: Any) -> dict[str, Any]:
    if not isinstance(metadata, Mapping):
        return {}
    keys = (
        "validation_mode",
        "reason_code",
        "skipped_check",
        "required_check",
        "surface",
        "preview_skipped",
        "preview_degraded",
    )
    payload = {
        key: _compact_preview_value(metadata.get(key), max_chars=240)
        for key in keys
        if key in metadata
    }
    return {key: value for key, value in payload.items() if value not in (None, "")}


def _repair_templates_payload(checks: Any) -> list[dict[str, Any]]:
    templates: list[dict[str, Any]] = []
    for check in checks:
        metadata = _attr(check, "metadata", {}) or {}
        if not isinstance(metadata, Mapping):
            continue
        template = metadata.get("repair_template")
        if not isinstance(template, Mapping):
            continue
        templates.append(_compact_preview_value(template, max_chars=360))
        if len(templates) >= _PREVIEW_MAX_CHECKS:
            break
    return templates


def _first_failure(checks: Any) -> str | None:
    for check in checks:
        if not _attr(check, "passed"):
            return f"{_attr(check, 'name')}: {_attr(check, 'detail')}"
    return None


__all__ = [
    "ContractPreviewTool",
    "_checks_payload",
    "_contract_preview_issue_strings",
    "_contract_preview_issue_summary",
    "_contract_result_payload",
    "_contract_summary_payload",
    "_first_failure",
    "_preview_max_checks_for_patch",
    "_repair_templates_payload",
]
