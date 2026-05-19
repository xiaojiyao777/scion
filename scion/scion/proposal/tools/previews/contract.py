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
    _PREVIEW_MAX_CHECKS,
    _compact_problem_preview,
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
                hypothesis_preview["checks"] = _checks_payload(
                    result.checks,
                    detail_chars=_PREVIEW_CHECK_DETAIL_CHARS,
                    max_checks=_PREVIEW_MAX_CHECKS,
                )
                hypothesis_preview["passed"] = result.passed
            payload["hypothesis"] = hypothesis_preview
            payload["passed"] = payload["passed"] and bool(hypothesis_preview["passed"])
        if args.patch is not None:
            patch_preview = _schema_preview_patch_payload(args.patch)
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
                )
                contract_payload = _contract_result_payload(
                    result,
                    detail_chars=_PREVIEW_CHECK_DETAIL_CHARS,
                    max_checks=_preview_max_checks_for_patch(
                        patch_preview["patch_object"]
                    ),
                )
                patch_preview["contract"] = _contract_summary_payload(result)
                patch_preview["checks"] = contract_payload["checks"]
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
        }
    )


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
    return [
        {
            "name": _attr(check, "name"),
            "passed": bool(_attr(check, "passed")),
            "severity": _attr(check, "severity"),
            "detail": _limit_text(str(_attr(check, "detail", "")), detail_chars),
            "elapsed_ms": _attr(check, "elapsed_ms"),
        }
        for check in check_list
    ]


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
]
