"""Tool-specific receipt projections for agentic prompt observations."""

from __future__ import annotations

import json
from typing import Any

from scion.proposal.engine.prompt.formatting import (
    _bounded_list,
    _drop_empty,
    _limit_text,
    _stable_short_digest,
)

_PREVIEW_TOOL_NAMES = frozenset(
    {
        "proposal.schema_preview",
        "proposal.target_permission_preview",
        "proposal.contract_preview",
        "proposal.algorithm_smoke",
    }
)


def _compact_preview_tool_payload(
    *,
    tool_name: str,
    payload: dict[str, Any],
    observation_summary: str,
    observation_failure_code: str,
    observation_repair_hint: str,
) -> dict[str, Any]:
    passed = _preview_passed(payload)
    failed_checks = _preview_failed_checks(payload)
    failure_reason = _preview_failure_reason(payload)
    compact = {
        "projection_kind": "preview_tool_receipt.v1",
        "tool_payload_omitted_from_generic_observations": True,
        "tool_name": tool_name,
        "passed": passed,
        "failure_code": observation_failure_code or payload.get("failure_code"),
        "summary": _limit_text(observation_summary, 360),
        "failure_reason": _limit_text(failure_reason, 700),
        "failed_checks": failed_checks[:10],
        "repair_templates": _preview_repair_templates(payload),
        "repair_hint": _limit_text(
            observation_repair_hint or str(payload.get("repair_hint") or ""),
            700,
        ),
        "payload_digest": _stable_short_digest(payload),
        "payload_sections_present": [
            str(key)
            for key in payload
            if key not in {"hypothesis_object", "patch_object"}
        ][:16],
        "requested": _compact_preview_requested(payload),
        "permission": _compact_preview_permission(payload),
        "workspace_materialized": payload.get("workspace_materialized"),
        "static_only": payload.get("static_only"),
        "dedicated_feedback_section": _preview_feedback_section(tool_name),
        "audit_ref": (
            "Full preview payload is omitted from the agent-facing observation; "
            "use the raw observation ledger/session artifact for audit detail."
        ),
    }
    return _drop_empty(compact)


def _compact_list_surfaces_payload(payload: dict[str, Any]) -> dict[str, Any]:
    surfaces = payload.get("surfaces")
    compact_surfaces: list[dict[str, Any]] = []
    if isinstance(surfaces, list):
        for surface in surfaces[:16]:
            if not isinstance(surface, dict):
                continue
            targets = (
                surface.get("targets")
                if isinstance(surface.get("targets"), dict)
                else {}
            )
            compact_surfaces.append(
                _drop_empty(
                    {
                        "name": surface.get("name"),
                        "kind": surface.get("kind"),
                        "target_files": surface.get("target_files")
                        or targets.get("files"),
                        "allowed_actions": targets.get("allowed_actions"),
                    }
                )
            )
    return _drop_empty(
        {
            "projection_kind": "surface_list_receipt.v1",
            "tool_payload_omitted_from_generic_observations": True,
            "surface_count": payload.get("surface_count")
            or len(compact_surfaces),
            "total_declared_surface_count": payload.get(
                "total_declared_surface_count"
            ),
            "surfaces": compact_surfaces,
            "forced_surface_constraint": payload.get("forced_surface_constraint"),
            "active_problem_boundary_constraint": payload.get(
                "active_problem_boundary_constraint"
            ),
            "payload_digest": _stable_short_digest(payload),
        }
    )


def _compact_read_problem_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return _drop_empty(
        {
            "projection_kind": "problem_context_receipt.v1",
            "tool_payload_omitted_from_generic_observations": True,
            "problem_id": payload.get("problem_id"),
            "problem_spec_hash": payload.get("problem_spec_hash"),
            "summary": _limit_text(str(payload.get("summary") or ""), 700),
            "problem_object_chars": len(str(payload.get("problem_object") or "")),
            "solver_mechanics_chars": len(str(payload.get("solver_mechanics") or "")),
            "problem_object_omitted_from_generic_observations": bool(
                payload.get("problem_object")
            ),
            "solver_mechanics_omitted_from_generic_observations": bool(
                payload.get("solver_mechanics")
            ),
            "dedicated_context_sections": [
                "problem_summary",
                "problem_object",
                "research_surfaces",
            ],
            "payload_digest": _stable_short_digest(payload),
        }
    )


def _compact_surface_payload(
    payload: dict[str, Any],
    *,
    active_digest: str,
) -> dict[str, Any]:
    surface = payload.get("surface")
    surface_payload = surface if isinstance(surface, dict) else {}
    current_artifact = _artifact_receipt(payload.get("current_artifact"))
    support_artifacts = [
        artifact
        for artifact in (
            _artifact_receipt(item)
            for item in _bounded_list(payload.get("support_artifacts"), 64)
        )
        if artifact
    ]
    readable_support_count = sum(
        1 for artifact in support_artifacts if artifact.get("readable") is True
    )
    unreadable_support_count = sum(
        1 for artifact in support_artifacts if artifact.get("readable") is False
    )
    compact: dict[str, Any] = {
        "projection_kind": "surface_interface_receipt.v1",
        "tool_payload_omitted_from_generic_observations": True,
        "dedicated_context_sections": [
            "active_algorithm_facts",
            "solver_design_full_algorithm_file_reads",
        ],
        "surface": _drop_empty(
            {
                "id": surface_payload.get("id") or payload.get("surface_id"),
                "name": surface_payload.get("name") or payload.get("name"),
                "kind": surface_payload.get("kind") or payload.get("kind"),
                "section": surface_payload.get("section") or payload.get("section"),
                "selected": surface_payload.get("selected")
                or payload.get("selected"),
                "active": surface_payload.get("active") or payload.get("active"),
            }
        ),
        "target_file": payload.get("target_file")
        or current_artifact.get("file_path"),
        "declared_targets": payload.get("declared_targets"),
        "surface_digest": _stable_short_digest(
            _drop_empty(
                {
                    "surface": _surface_identity(payload),
                    "surface_contract": payload.get("surface_contract"),
                    "declared_targets": payload.get("declared_targets"),
                    "target_file": payload.get("target_file"),
                }
            )
        ),
        "provenance": payload.get("provenance"),
        "active_algorithm_facts_ref": {
            "fact_packet_digest": active_digest,
            "omitted_from_raw_observation": (
                "deduplicated; see Active Algorithm Facts and full algorithm "
                "file read sections"
            ),
        },
        "current_artifact": _drop_empty(
            {
                "file_path": current_artifact.get("file_path"),
                "readable": current_artifact.get("readable"),
                "source": current_artifact.get("source"),
            }
        ),
        "support_artifact_count": len(support_artifacts),
        "support_artifact_paths": [
            artifact["file_path"]
            for artifact in support_artifacts
            if artifact.get("file_path")
        ],
        "support_artifact_readable_count": readable_support_count,
        "support_artifact_unreadable_count": unreadable_support_count,
        "source_pointer": (
            "Full solver-design source and active facts are projected in "
            "dedicated cacheable prompt sections; artifact previews and API "
            "summaries are omitted from generic tool observations."
        ),
    }
    contract = payload.get("surface_contract")
    if isinstance(contract, dict):
        compact["surface_contract"] = _drop_empty(
            {
                "schema_version": contract.get("schema_version"),
                "detail": contract.get("detail"),
                "section": contract.get("section"),
                "available_sections": contract.get("available_sections"),
                "target_preview": _target_preview_receipt(
                    contract.get("target_preview")
                ),
            }
        )
    return _drop_empty(compact)


def _surface_identity(payload: dict[str, Any]) -> dict[str, str]:
    raw_surface = payload.get("surface")
    surface = raw_surface if isinstance(raw_surface, dict) else {}
    candidates = {
        "id": surface.get("id") or payload.get("surface_id"),
        "name": surface.get("name") or payload.get("name"),
        "kind": surface.get("kind") or payload.get("kind"),
    }
    if isinstance(raw_surface, str):
        candidates["surface"] = raw_surface
    summary = payload.get("interface_summary")
    if (
        isinstance(summary, str)
        and "Declared Research Surface: solver_design" in summary
    ):
        candidates["interface_summary_surface"] = "solver_design"
    return {
        key: str(value).strip()
        for key, value in candidates.items()
        if str(value or "").strip()
    }


def _artifact_receipt(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {
        key: item
        for key, item in {
            "file_path": value.get("file_path") or value.get("path"),
            "readable": value.get("readable"),
            "source": value.get("source"),
            "read_receipt": "content/API summary omitted; see dedicated source sections",
        }.items()
        if item not in (None, "", (), [], {})
    }


def _target_preview_receipt(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {
        key: item
        for key, item in {
            "file_path": value.get("file_path"),
            "readable": value.get("readable"),
            "read_receipt": "target preview omitted; see dedicated source sections",
        }.items()
        if item not in (None, "", (), [], {})
    }


def _preview_feedback_section(tool_name: str) -> str:
    if tool_name == "proposal.schema_preview":
        return "hypothesis_schema_telemetry_retry_feedback"
    if tool_name in {"proposal.contract_preview", "proposal.algorithm_smoke"}:
        return "latest_preview_repair_feedback"
    if tool_name == "proposal.target_permission_preview":
        return "hypothesis_schema_telemetry_retry_feedback"
    return ""


def _preview_passed(payload: Any) -> bool | None:
    if isinstance(payload, dict) and "passed" in payload:
        return bool(payload.get("passed"))
    return None


def _preview_failed_checks(value: Any) -> list[str]:
    failed: list[str] = []

    def visit(item: Any) -> None:
        if len(failed) >= 20:
            return
        if isinstance(item, dict):
            name = item.get("name")
            if name and item.get("passed") is False:
                failed.append(str(name))
            contract = item.get("contract")
            if isinstance(contract, dict):
                raw_failed = contract.get("failed_checks")
                if isinstance(raw_failed, list):
                    failed.extend(str(check) for check in raw_failed[:20])
            for child in item.values():
                visit(child)
        elif isinstance(item, list):
            for child in item[:40]:
                visit(child)

    visit(value)
    return list(dict.fromkeys(item for item in failed if item))[:20]


def _preview_repair_templates(value: Any) -> list[dict[str, Any]]:
    templates: list[dict[str, Any]] = []

    def visit(item: Any) -> None:
        if len(templates) >= 4:
            return
        if isinstance(item, dict):
            raw_templates = item.get("repair_templates")
            if isinstance(raw_templates, list):
                for template in raw_templates:
                    if isinstance(template, dict):
                        templates.append(_compact_preview_repair_template(template))
                        if len(templates) >= 4:
                            return
            raw_template = item.get("repair_template")
            if isinstance(raw_template, dict):
                templates.append(_compact_preview_repair_template(raw_template))
                if len(templates) >= 4:
                    return
            for child in item.values():
                visit(child)
        elif isinstance(item, list):
            for child in item[:40]:
                visit(child)

    visit(value)
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for template in templates:
        key = json.dumps(template, sort_keys=True, default=str)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(template)
    return deduped[:4]


def _compact_preview_repair_template(template: dict[str, Any]) -> dict[str, Any]:
    return _drop_empty(
        {
            "repair_type": template.get("repair_type"),
            "check": template.get("check"),
            "severity": template.get("severity"),
            "missing_fields": template.get("missing_fields"),
            "observed": template.get("observed"),
            "required_template": template.get("required_template"),
            "recommended_shape": template.get("recommended_shape"),
            "agent_instruction": template.get("agent_instruction"),
        }
    )


def _preview_failure_reason(value: Any) -> str:
    reasons: list[str] = []

    def add(text: Any) -> None:
        reason = str(text or "").strip()
        if reason and reason not in reasons:
            reasons.append(reason)

    def visit(item: Any) -> None:
        if len(reasons) >= 8:
            return
        if isinstance(item, dict):
            for key in ("failure_reason", "issue_summary", "repair_hint"):
                value_for_key = item.get(key)
                add(value_for_key)
            errors = item.get("errors")
            if isinstance(errors, list):
                for error in errors[:4]:
                    if isinstance(error, dict):
                        add(error.get("msg") or error.get("message") or error)
                    else:
                        add(error)
            issues = item.get("issues")
            if isinstance(issues, list):
                for issue in issues[:4]:
                    add(issue)
            for child in item.values():
                visit(child)
        elif isinstance(item, list):
            for child in item[:20]:
                visit(child)

    visit(value)
    return "; ".join(reasons[:6])


def _compact_preview_requested(payload: dict[str, Any]) -> dict[str, Any]:
    requested = payload.get("requested")
    if isinstance(requested, dict):
        return _drop_empty(
            {
                "change_locus": requested.get("change_locus"),
                "action": requested.get("action"),
                "target_file": requested.get("target_file"),
            }
        )
    hypothesis = payload.get("hypothesis")
    if isinstance(hypothesis, dict):
        summary = hypothesis.get("hypothesis")
        if isinstance(summary, dict):
            return _drop_empty(
                {
                    "change_locus": summary.get("change_locus"),
                    "action": summary.get("action"),
                    "target_file": summary.get("target_file"),
                    "mechanism_changes": summary.get("mechanism_changes"),
                }
            )
    patch = payload.get("patch")
    if isinstance(patch, dict):
        summary = patch.get("patch")
        if isinstance(summary, dict):
            return _drop_empty(
                {
                    "file_path": summary.get("file_path"),
                    "action": summary.get("action"),
                }
            )
    return {}


def _compact_preview_permission(payload: dict[str, Any]) -> dict[str, Any]:
    permission = payload.get("permission")
    if not isinstance(permission, dict):
        return {}
    return _drop_empty(
        {
            "surface_known": permission.get("surface_known"),
            "action_allowed": permission.get("action_allowed"),
            "target_required": permission.get("target_required"),
            "target_path_safe": permission.get("target_path_safe"),
            "target_declared": permission.get("target_declared"),
        }
    )
