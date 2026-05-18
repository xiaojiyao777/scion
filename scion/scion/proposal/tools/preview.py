"""Draft and contract preview proposal tools."""

from __future__ import annotations

import ast
from dataclasses import replace
import hashlib
import json
import uuid
from typing import Any, Mapping

from pydantic import ValidationError

from scion.contract.gate import ContractGate
from scion.core.models import (
    ChampionState,
    ContractResult,
    HypothesisProposal,
    MechanismChange,
    PatchFileChange,
    PatchProposal,
    mechanism_changes,
    patch_file_changes,
)
from scion.core.paths import normalize_relative_patch_path
from scion.problem.bridge import legacy_problem_spec_from_v1
from scion.proposal.context_manager import _get_adapter_problem_spec
from scion.proposal import solver_design_smoke as _solver_design_smoke
from scion.proposal.schemas import HypothesisProposalInput, PatchProposalInput
from scion.proposal.tools.base import _BaseReadOnlyTool
from scion.proposal.tools.models import (
    AlgorithmSmokeInput,
    ContractPreviewInput,
    DraftHypothesisInput,
    DraftPatchInput,
    InterfacePreviewInput,
    ProposalExposureLevel,
    ProposalObservation,
    ProposalToolContext,
    ProposalToolFailureCode,
    ProposalToolPermission,
    SchemaPreviewInput,
    TargetPermissionPreviewInput,
)
from scion.proposal.tools.surface import (
    _coerce_compact_list,
    _compact_mapping_payload,
    _drop_empty_items,
    _find_surface,
    _surface_allowed_actions,
    _surface_for_hypothesis,
    _surface_for_selected_or_patch_path,
    _surface_function_signatures,
    _surface_novelty_signature_requirement,
    _surface_payload,
    _surface_permission_summary,
    _surface_required_functions,
    _surface_return_values,
    _surface_target_files,
    _target_declared,
)
from scion.proposal.tools.utils import (
    _attr,
    _json_size,
    _limit_text,
    _model_payload,
    _normalize_rel_path,
    _strip_forbidden_value,
)
from scion.runtime.telemetry_guard import (
    EXPECTED_TELEMETRY_CATEGORIES,
    declared_mechanism_runtime_probes,
    declared_surface_telemetry_fields,
    normalize_expected_telemetry,
)

_COMPACT_FEEDBACK_LIST_ITEMS = 8
_ALGORITHM_SMOKE_TIME_LIMIT_SEC = _solver_design_smoke._ALGORITHM_SMOKE_TIME_LIMIT_SEC
_ALGORITHM_SMOKE_TIMEOUT_SEC = _solver_design_smoke._ALGORITHM_SMOKE_TIMEOUT_SEC
_ALGORITHM_SMOKE_DEFAULT_SEED = _solver_design_smoke._ALGORITHM_SMOKE_DEFAULT_SEED
_ALGORITHM_SMOKE_MAX_SCREENING_CASES = _solver_design_smoke._ALGORITHM_SMOKE_MAX_SCREENING_CASES
_ALGORITHM_SMOKE_LOW_EFFORT_MIN_CASES = _solver_design_smoke._ALGORITHM_SMOKE_LOW_EFFORT_MIN_CASES
_ALGORITHM_SMOKE_LOW_EFFORT_MAX_ITERATIONS = _solver_design_smoke._ALGORITHM_SMOKE_LOW_EFFORT_MAX_ITERATIONS
_ALGORITHM_SMOKE_LOW_EFFORT_MAX_ATTEMPTS = _solver_design_smoke._ALGORITHM_SMOKE_LOW_EFFORT_MAX_ATTEMPTS
_ALGORITHM_SMOKE_LOW_EFFORT_MAX_RUNTIME_RATIO = _solver_design_smoke._ALGORITHM_SMOKE_LOW_EFFORT_MAX_RUNTIME_RATIO
_ALGORITHM_SMOKE_LOW_EFFORT_STOP_REASONS = _solver_design_smoke._ALGORITHM_SMOKE_LOW_EFFORT_STOP_REASONS
_RuntimeSmokeCase = _solver_design_smoke._RuntimeSmokeCase
_runtime_algorithm_smoke_preview = _solver_design_smoke._runtime_algorithm_smoke_preview
_runtime_smoke_base_workspace = _solver_design_smoke._runtime_smoke_base_workspace
_is_solver_design_runtime_patch_path = _solver_design_smoke._is_solver_design_runtime_patch_path
_apply_patch_to_runtime_smoke_workspace = _solver_design_smoke._apply_patch_to_runtime_smoke_workspace
_apply_file_change_to_runtime_smoke_workspace = _solver_design_smoke._apply_file_change_to_runtime_smoke_workspace
_ensure_runtime_smoke_path_writable = _solver_design_smoke._ensure_runtime_smoke_path_writable
_runtime_smoke_cases = _solver_design_smoke._runtime_smoke_cases
_runtime_smoke_stage_value = _solver_design_smoke._runtime_smoke_stage_value
_runtime_smoke_stage_arguments = _solver_design_smoke._runtime_smoke_stage_arguments
_select_runtime_smoke_screening_cases = _solver_design_smoke._select_runtime_smoke_screening_cases
_load_runtime_smoke_yaml = _solver_design_smoke._load_runtime_smoke_yaml
_first_int = _solver_design_smoke._first_int
_string_list = _solver_design_smoke._string_list
_resolve_smoke_instance_path = _solver_design_smoke._resolve_smoke_instance_path
_run_solver_design_smoke = _solver_design_smoke._run_solver_design_smoke
_solver_run_failure_detail = _solver_design_smoke._solver_run_failure_detail
_runtime_smoke_audit_failure = _solver_design_smoke._runtime_smoke_audit_failure
_problem_spec_for_runtime_audit = _solver_design_smoke._problem_spec_for_runtime_audit
_compact_runtime_smoke_payload = _solver_design_smoke._compact_runtime_smoke_payload
_compact_runtime_audit_failure = _solver_design_smoke._compact_runtime_audit_failure
_solver_design_micro_benchmark_result = _solver_design_smoke._solver_design_micro_benchmark_result
_compare_solver_design_raw_outputs = _solver_design_smoke._compare_solver_design_raw_outputs
_solver_design_micro_benchmark_issue = _solver_design_smoke._solver_design_micro_benchmark_issue
_solver_design_zero_effort_issue = _solver_design_smoke._solver_design_zero_effort_issue
_solver_design_low_effort_issue = _solver_design_smoke._solver_design_low_effort_issue
_solver_design_smoke_runtime_underspent = _solver_design_smoke._solver_design_smoke_runtime_underspent
_runtime_stop_reason = _solver_design_smoke._runtime_stop_reason
_solver_design_patch_claims_search_effort = _solver_design_smoke._solver_design_patch_claims_search_effort
_solver_design_patch_paths = _solver_design_smoke._solver_design_patch_paths
_nonnegative_int = _solver_design_smoke._nonnegative_int
_compact_solver_design_micro_benchmark = _solver_design_smoke._compact_solver_design_micro_benchmark
_float_or_none = _solver_design_smoke._float_or_none
_solver_design_smoke_repair_guidance = _solver_design_smoke._solver_design_smoke_repair_guidance
_PREVIEW_CHECK_DETAIL_CHARS = 900
_PREVIEW_FAILURE_REASON_CHARS = 1200
_PREVIEW_MAX_CHECKS = 12
_PREVIEW_PROBLEM_ISSUE_CHARS = 500
_PREVIEW_PROBLEM_MAX_CHECKS = 8
_ALGORITHM_SMOKE_AGENT_SCHEMA = "scion.algorithm_smoke.agent_feedback.v1"
_ALGORITHM_SMOKE_AGENT_TEXT_CHARS = 900
_ALGORITHM_SMOKE_AGENT_TAIL_CHARS = 900
_ALGORITHM_SMOKE_AGENT_LIST_ITEMS = 8
_ALGORITHM_SMOKE_AGENT_COUNTER_ITEMS = 16
_SEMANTIC_SIGNATURE_SCALAR_STRING_CHARS = 120
_NONEMPTY_SEQUENCE_NOVELTY_FIELDS = frozenset(
    {
        "selected_components",
        "deep_components_selected",
    }
)

class DraftHypothesisTool(_BaseReadOnlyTool):
    name = "proposal.draft_hypothesis"
    input_schema = DraftHypothesisInput
    permission = ProposalToolPermission.DRAFT_PATCH
    max_result_chars = 24000

    def call(
        self,
        args: DraftHypothesisInput,
        context: ProposalToolContext,
    ) -> ProposalObservation:
        hypothesis = _hypothesis_from_input(args)
        forced_violation = _forced_hypothesis_violation(context, hypothesis)
        if forced_violation is not None:
            return self._error(
                context,
                failure_code=ProposalToolFailureCode.SCHEMA_ERROR,
                summary="Hypothesis draft violates forced research-surface constraint.",
                structured_payload={
                    "passed": False,
                    "failure_reason": forced_violation,
                    "forced_surface_constraint": _forced_surface_constraint_payload(
                        context
                    ),
                    "hypothesis": _model_payload(hypothesis),
                    "workspace_materialized": False,
                },
                repair_hint="Draft only the forced surface/action/target.",
            )
        schema_result = _hypothesis_schema_preview(context, hypothesis)
        if not schema_result["passed"]:
            return self._error(
                context,
                failure_code=ProposalToolFailureCode.SCHEMA_ERROR,
                summary="Hypothesis draft failed schema preview.",
                structured_payload=schema_result,
                repair_hint="Repair structured hypothesis fields before drafting.",
            )

        artifact_id = _artifact_id("hypothesis", hypothesis)
        payload = {
            "artifact_kind": "hypothesis_draft",
            "artifact_id": artifact_id,
            "hypothesis": _model_payload(hypothesis),
            "schema_preview": schema_result,
            "workspace_materialized": False,
        }
        return self._observation(
            context,
            observation_type="hypothesis_draft",
            summary="Returned tainted hypothesis draft artifact.",
            structured_payload=payload,
            artifact_ref=f"proposal-artifact://{context.session_id}/{artifact_id}",
            exposure_level=ProposalExposureLevel.SCRATCH,
        )

class DraftPatchTool(_BaseReadOnlyTool):
    name = "proposal.draft_patch"
    input_schema = DraftPatchInput
    permission = ProposalToolPermission.DRAFT_PATCH
    max_result_chars = 80000

    def call(
        self,
        args: DraftPatchInput,
        context: ProposalToolContext,
    ) -> ProposalObservation:
        patch = _patch_from_input(args)
        path_error = _patch_path_error(patch.file_path)
        if path_error is not None:
            return self._error(
                context,
                failure_code=ProposalToolFailureCode.PERMISSION_DENIED,
                summary="Patch draft target path is unsafe.",
                structured_payload={
                    "file_path": patch.file_path,
                    "path_error": path_error,
                    "workspace_materialized": False,
                },
                repair_hint="Use a normalized POSIX path relative to the candidate root.",
            )

        artifact_id = _artifact_id("patch", patch)
        payload = {
            "artifact_kind": "patch_draft",
            "artifact_id": artifact_id,
            "patch": _model_payload(patch),
            "workspace_materialized": False,
        }
        return self._observation(
            context,
            observation_type="patch_draft",
            summary="Returned tainted patch draft artifact without workspace writes.",
            structured_payload=payload,
            artifact_ref=f"proposal-artifact://{context.session_id}/{artifact_id}",
            exposure_level=ProposalExposureLevel.SCRATCH,
        )

class SchemaPreviewTool(_BaseReadOnlyTool):
    name = "proposal.schema_preview"
    input_schema = SchemaPreviewInput
    permission = ProposalToolPermission.CONTRACT_PREVIEW
    max_result_chars = 24000

    def call(
        self,
        args: SchemaPreviewInput,
        context: ProposalToolContext,
    ) -> ProposalObservation:
        payload: dict[str, Any] = {
            "passed": True,
            "hypothesis": None,
            "patch": None,
            "workspace_materialized": False,
        }
        if args.hypothesis is None and args.patch is None:
            payload["passed"] = False
            payload["errors"] = ["Provide hypothesis and/or patch payload."]
        if args.hypothesis is not None:
            payload["hypothesis"] = _schema_preview_hypothesis_payload(
                context,
                args.hypothesis,
            )
            payload["passed"] = payload["passed"] and bool(
                payload["hypothesis"]["passed"]
            )
        if args.patch is not None:
            payload["patch"] = _schema_preview_patch_payload(args.patch)
            payload["passed"] = payload["passed"] and bool(payload["patch"]["passed"])
        payload = _drop_internal_preview_objects(payload)
        summary = _schema_preview_summary(payload)

        return self._observation(
            context,
            observation_type="schema_preview",
            summary=summary,
            structured_payload=payload,
            exposure_level=ProposalExposureLevel.PUBLIC_SPEC,
        )

def _schema_preview_summary(payload: Mapping[str, Any]) -> str:
    if bool(payload.get("passed")):
        return "Schema preview passed."
    details: list[str] = []
    for section_name in ("hypothesis", "patch"):
        section = payload.get(section_name)
        if not isinstance(section, Mapping):
            continue
        reason = section.get("failure_reason")
        if reason:
            details.append(str(reason))
        errors = section.get("errors")
        if isinstance(errors, list):
            for error in errors:
                if isinstance(error, Mapping):
                    loc = ".".join(str(part) for part in error.get("loc", ()) or ())
                    message = error.get("msg") or error.get("message") or error
                    details.append(f"{loc}: {message}" if loc else str(message))
                elif error:
                    details.append(str(error))
    if not details:
        return "Schema preview found issues."
    compact = "; ".join(dict.fromkeys(details))
    return "Schema preview found issues: " + _limit_text(compact, 420)

class TargetPermissionPreviewTool(_BaseReadOnlyTool):
    name = "proposal.target_permission_preview"
    input_schema = TargetPermissionPreviewInput
    permission = ProposalToolPermission.CONTRACT_PREVIEW
    max_result_chars = 24000

    def call(
        self,
        args: TargetPermissionPreviewInput,
        context: ProposalToolContext,
    ) -> ProposalObservation:
        surface = _find_surface(context, args.change_locus)
        declared_targets = _surface_target_files(surface) if surface is not None else []
        allowed_actions = _surface_allowed_actions(surface)
        target_error = None
        if args.target_file:
            target_error = _patch_path_error(args.target_file)

        passed = surface is not None
        issues: list[str] = []
        if surface is None:
            issues.append(f"unknown research surface: {args.change_locus}")
        if args.action not in {"modify", "create_new", "remove"}:
            passed = False
            issues.append(f"invalid hypothesis action: {args.action}")
        elif surface is not None and args.action not in allowed_actions:
            passed = False
            issues.append(
                f"action '{args.action}' is not allowed for surface "
                f"'{args.change_locus}'"
            )
        if args.action in {"modify", "remove"} and not args.target_file:
            passed = False
            issues.append(f"action '{args.action}' requires target_file")
        if target_error is not None:
            passed = False
            issues.append(target_error)
        elif args.target_file and surface is not None:
            if not _target_declared(args.target_file, declared_targets):
                passed = False
                issues.append(
                    f"target_file '{args.target_file}' is not declared for surface "
                    f"'{args.change_locus}'"
                )
        forced_violation = _forced_action_target_violation(
            context,
            change_locus=args.change_locus,
            action=args.action,
            target_file=args.target_file,
        )
        if forced_violation is not None:
            passed = False
            issues.append(forced_violation)
        boundary_violation = _active_problem_boundary_violation(
            context,
            change_locus=args.change_locus,
        )
        if boundary_violation is not None:
            passed = False
            issues.append(boundary_violation)

        payload = {
            "passed": passed,
            "surface": (
                _surface_permission_summary(
                    surface,
                    allowed_actions=allowed_actions,
                    declared_targets=declared_targets,
                )
                if surface is not None
                else None
            ),
            "requested": {
                "change_locus": args.change_locus,
                "action": args.action,
                "target_file": args.target_file,
            },
            "allowed_actions": allowed_actions,
            "declared_targets": declared_targets,
            "forced_surface_constraint": _forced_surface_constraint_payload(context),
            "active_problem_boundary_constraint": (
                _active_problem_boundary_constraint_payload(context)
            ),
            "permission": {
                "surface_known": surface is not None,
                "action_allowed": bool(
                    surface is not None and args.action in allowed_actions
                ),
                "target_required": args.action in {"modify", "remove"},
                "target_path_safe": target_error is None,
                "target_declared": bool(
                    args.target_file
                    and surface is not None
                    and _target_declared(args.target_file, declared_targets)
                ),
            },
            "issues": issues,
            "workspace_materialized": False,
        }
        return self._observation(
            context,
            observation_type="target_permission_preview",
            summary=(
                "Target/action permission preview passed."
                if passed
                else "Target/action permission preview found issues."
            ),
            structured_payload=payload,
            exposure_level=ProposalExposureLevel.PUBLIC_SPEC,
        )

class InterfacePreviewTool(_BaseReadOnlyTool):
    name = "proposal.interface_preview"
    input_schema = InterfacePreviewInput
    permission = ProposalToolPermission.CONTRACT_PREVIEW
    max_result_chars = 36000

    def call(
        self,
        args: InterfacePreviewInput,
        context: ProposalToolContext,
    ) -> ProposalObservation:
        patch_payload = {
            "file_path": args.file_path,
            "action": args.action,
            "code_content": args.code_content,
        }
        patch_preview = _schema_preview_patch_payload(patch_payload)
        if not patch_preview["passed"]:
            payload = {
                "passed": False,
                "patch_schema": patch_preview,
                "workspace_materialized": False,
            }
            return self._observation(
                context,
                observation_type="interface_preview",
                summary="Interface preview found schema issues.",
                structured_payload=payload,
                exposure_level=ProposalExposureLevel.PUBLIC_SPEC,
            )

        patch = patch_preview["patch_object"]
        gate = _contract_gate(context)
        result = gate.validate_patch(
            patch,
            selected_surface=args.selected_surface,
        )
        interface_checks = [
            check for check in result.checks if check.name == "C7_interface"
        ]
        surface = _surface_for_selected_or_patch_path(
            context,
            patch.file_path,
            args.selected_surface,
        )
        interface_passed = bool(
            interface_checks and all(check.passed for check in interface_checks)
        )
        passed = interface_passed and result.passed
        if not interface_checks:
            passed = False
        problem_preview = None
        if passed:
            problem_preview = _problem_surface_preview(context, patch, surface)
            if problem_preview is not None:
                passed = passed and bool(problem_preview.get("passed"))
        payload = {
            "passed": passed,
            "surface": _surface_payload(surface) if surface is not None else None,
            "required_functions": _surface_required_functions(surface),
            "declared_function_signatures": _surface_function_signatures(surface),
            "declared_return_values": _surface_return_values(surface),
            "present_functions": _module_level_functions(args.code_content),
            "present_classes": _module_classes(args.code_content),
            "checks": _checks_payload(result.checks),
            "problem_preview": problem_preview,
            "workspace_materialized": False,
        }
        return self._observation(
            context,
            observation_type="interface_preview",
            summary=(
                "Interface preview passed."
                if passed
                else "Interface preview found issues."
            ),
            structured_payload=payload,
            exposure_level=ProposalExposureLevel.PUBLIC_SPEC,
        )

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

class AlgorithmSmokeTool(_BaseReadOnlyTool):
    name = "proposal.algorithm_smoke"
    input_schema = AlgorithmSmokeInput
    permission = ProposalToolPermission.CONTRACT_PREVIEW
    max_result_chars = 60000

    def call(
        self,
        args: AlgorithmSmokeInput,
        context: ProposalToolContext,
    ) -> ProposalObservation:
        payload: dict[str, Any] = {
            "passed": True,
            "hypothesis": None,
            "patch": None,
            "static_contract": None,
            "problem_preview": None,
            "runtime_smoke": None,
            "non_promotional": True,
            "tainted_debug": True,
            "workspace_materialized": False,
            "verification_run": False,
            "protocol_run": False,
            "decision_run": False,
        }
        gate = _contract_gate(context)
        if args.hypothesis is None or args.patch is None:
            payload["passed"] = False
            payload["errors"] = [
                "Provide both approved hypothesis and patch payload for algorithm smoke."
            ]
        hypothesis_object = None
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
                if result.passed:
                    hypothesis_object = hypothesis_preview["hypothesis_object"]
            payload["hypothesis"] = hypothesis_preview
            payload["passed"] = payload["passed"] and bool(hypothesis_preview["passed"])

        if args.patch is not None:
            patch_preview = _schema_preview_patch_payload(args.patch)
            if patch_preview["passed"]:
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
                payload["static_contract"] = _contract_summary_payload(result)
                if result.passed and hypothesis_object is not None:
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
                    if problem_preview is None:
                        problem_preview = {
                            "passed": True,
                            "checks": [],
                            "issues": [],
                            "skipped": True,
                            "workspace_materialized": False,
                            "verification_run": False,
                        }
                    compact_preview = _compact_problem_preview(problem_preview)
                    patch_preview["problem_preview"] = compact_preview
                    payload["problem_preview"] = compact_preview
                    patch_preview["passed"] = bool(patch_preview["passed"]) and bool(
                        problem_preview.get("passed")
                    )
                    if patch_preview["passed"]:
                        smoke_preview = _runtime_algorithm_smoke_preview(
                            context,
                            patch_preview["patch_object"],
                            selected_surface,
                            hypothesis_object,
                        )
                        if smoke_preview is not None:
                            payload["runtime_smoke"] = smoke_preview
                            patch_preview["runtime_smoke"] = smoke_preview
                            payload["workspace_materialized"] = bool(
                                smoke_preview.get("workspace_materialized")
                            )
                            patch_preview["passed"] = bool(
                                patch_preview["passed"]
                            ) and bool(smoke_preview.get("passed"))
                elif result.passed:
                    patch_preview["passed"] = False
                    patch_preview["needs_hypothesis"] = True
                    payload["needs_hypothesis"] = True
            payload["patch"] = patch_preview
            payload["passed"] = payload["passed"] and bool(patch_preview["passed"])

        raw_payload = _drop_internal_preview_objects(payload)
        issue_summary = _contract_preview_issue_summary(raw_payload)
        if issue_summary:
            raw_payload["issue_summary"] = issue_summary
        payload = _algorithm_smoke_agent_payload(raw_payload)
        primary_issue = str(payload.get("primary_issue") or issue_summary or "")
        return self._observation(
            context,
            observation_type="algorithm_smoke",
            summary=(
                (
                    "Algorithm smoke passed on tainted runtime preview."
                    if payload.get("runtime_smoke")
                    else "Algorithm smoke passed on tainted synthetic preview."
                )
                if payload["passed"]
                else (
                    "Algorithm smoke found issues: "
                    f"{primary_issue}"
                    if primary_issue
                    else "Algorithm smoke found issues."
                )
            ),
            structured_payload=payload,
            exposure_level=ProposalExposureLevel.PUBLIC_SPEC,
        )

def compact_algorithm_smoke_observation_for_agent(
    observation: ProposalObservation,
) -> ProposalObservation | None:
    """Return a registry-safe agent-facing smoke observation when possible."""
    if observation.tool_name != "proposal.algorithm_smoke" or observation.is_error:
        return None
    if not isinstance(observation.structured_payload, Mapping):
        return None
    payload = _algorithm_smoke_agent_payload(observation.structured_payload)
    return replace(
        observation,
        summary=(
            "Algorithm smoke passed on compact tainted preview."
            if payload.get("passed")
            else "Algorithm smoke found issues in compact tainted preview."
        ),
        structured_payload=payload,
        repair_hint=None,
    )


def _algorithm_smoke_agent_payload(raw_payload: Mapping[str, Any]) -> dict[str, Any]:
    runtime_smoke = _mapping_or_none(raw_payload.get("runtime_smoke"))
    telemetry_guard = _compact_algorithm_smoke_telemetry_guard(
        runtime_smoke.get("telemetry_guard") if runtime_smoke else None
    )
    runtime_counters = _compact_algorithm_smoke_runtime_counters(
        runtime_smoke.get("runtime") if runtime_smoke else None
    )
    subprocess_tail = _compact_algorithm_smoke_subprocess(
        runtime_smoke.get("run") if runtime_smoke else None
    )
    runtime_comparison = _compact_algorithm_smoke_runtime_comparison(runtime_smoke)
    primary_issue = _algorithm_smoke_primary_issue(
        raw_payload,
        runtime_smoke=runtime_smoke,
        telemetry_guard=telemetry_guard,
        subprocess_tail=subprocess_tail,
    )
    passed = bool(raw_payload.get("passed"))
    status = "passed" if passed else "failed"
    failure_class = _algorithm_smoke_failure_class(
        passed=passed,
        raw_payload=raw_payload,
        runtime_smoke=runtime_smoke,
        telemetry_guard=telemetry_guard,
        primary_issue=primary_issue,
        subprocess_tail=subprocess_tail,
    )
    repair_hints = _algorithm_smoke_repair_hints(
        raw_payload,
        runtime_smoke=runtime_smoke,
        telemetry_guard=telemetry_guard,
    )
    failed_checks = _algorithm_smoke_failed_checks(
        raw_payload,
        runtime_smoke=runtime_smoke,
        primary_issue=primary_issue,
        failure_class=failure_class,
    )
    selected_surface = _algorithm_smoke_selected_surface(raw_payload, runtime_smoke)
    case_count = _algorithm_smoke_case_count(runtime_smoke)
    non_promotional = raw_payload.get("non_promotional", True)
    tainted_debug = raw_payload.get("tainted_debug", True)
    agent_summary = _drop_empty_items(
        {
            "passed": passed,
            "status": status,
            "failure_class": failure_class,
            "primary_issue": primary_issue,
            "selected_surface": selected_surface,
            "case_count": case_count,
            "non_promotional": non_promotional,
            "tainted_debug": tainted_debug,
            "repair_hints": repair_hints,
            "failed_checks": failed_checks,
        }
    )
    compact_payload: dict[str, Any] = _drop_empty_items(
        {
            "schema": _ALGORITHM_SMOKE_AGENT_SCHEMA,
            "passed": passed,
            "status": status,
            "failure_class": failure_class,
            "primary_issue": primary_issue,
            "selected_surface": selected_surface,
            "case_count": case_count,
            "non_promotional": non_promotional,
            "tainted_debug": tainted_debug,
            "workspace_materialized": raw_payload.get("workspace_materialized"),
            "verification_run": raw_payload.get("verification_run"),
            "protocol_run": raw_payload.get("protocol_run"),
            "decision_run": raw_payload.get("decision_run"),
            "agent_summary": agent_summary,
            "repair_hints": repair_hints,
            "failed_checks": failed_checks,
            "telemetry_guard": telemetry_guard,
            "runtime_comparison": runtime_comparison,
            "subprocess": subprocess_tail,
            "static_preview": _algorithm_smoke_static_preview(raw_payload),
            "hypothesis": _algorithm_smoke_preview_section(
                raw_payload.get("hypothesis")
            ),
            "patch": _algorithm_smoke_preview_section(raw_payload.get("patch")),
            "problem_preview": _algorithm_smoke_problem_preview(
                raw_payload.get("problem_preview")
            ),
            "runtime_smoke": _algorithm_smoke_runtime_agent_section(
                runtime_smoke,
                telemetry_guard=telemetry_guard,
                runtime_counters=runtime_counters,
                subprocess_tail=subprocess_tail,
                runtime_comparison=runtime_comparison,
                repair_hints=repair_hints,
            ),
            "issue_summary": _limit_text(
                str(raw_payload.get("issue_summary") or ""),
                _ALGORITHM_SMOKE_AGENT_TEXT_CHARS,
            ),
            "audit": {
                "agent_payload_schema": _ALGORITHM_SMOKE_AGENT_SCHEMA,
                "raw_payload_digest": _algorithm_smoke_digest(raw_payload),
                "raw_payload_chars": _json_size(raw_payload),
                "full_runtime_payload_omitted": True,
                "raw_payload_omitted_from_agent": True,
            },
        }
    )
    compact_payload["audit"]["agent_payload_digest"] = _algorithm_smoke_digest(
        {
            key: value
            for key, value in compact_payload.items()
            if key != "audit"
        }
    )
    compact_payload["audit"]["summary_ref"] = (
        "algorithm-smoke-summary:"
        f"{_algorithm_smoke_digest(compact_payload.get('agent_summary'))}"
    )
    return compact_payload


def _mapping_or_none(value: Any) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _algorithm_smoke_digest(value: Any) -> str:
    rendered = json.dumps(
        _strip_forbidden_value(value),
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()[:16]


def _algorithm_smoke_selected_surface(
    raw_payload: Mapping[str, Any],
    runtime_smoke: Mapping[str, Any] | None,
) -> str | None:
    if runtime_smoke is not None and runtime_smoke.get("selected_surface"):
        return str(runtime_smoke.get("selected_surface"))
    problem_preview = _mapping_or_none(raw_payload.get("problem_preview"))
    if problem_preview is not None and problem_preview.get("surface"):
        return str(problem_preview.get("surface"))
    hypothesis = _mapping_or_none(raw_payload.get("hypothesis"))
    hypothesis_summary = (
        _mapping_or_none(hypothesis.get("hypothesis")) if hypothesis else None
    )
    if hypothesis_summary is not None and hypothesis_summary.get("change_locus"):
        return str(hypothesis_summary.get("change_locus"))
    return None


def _algorithm_smoke_case_count(runtime_smoke: Mapping[str, Any] | None) -> int | None:
    if runtime_smoke is None:
        return None
    value = runtime_smoke.get("case_count")
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _algorithm_smoke_primary_issue(
    raw_payload: Mapping[str, Any],
    *,
    runtime_smoke: Mapping[str, Any] | None,
    telemetry_guard: Mapping[str, Any] | None,
    subprocess_tail: Mapping[str, Any] | None,
) -> str:
    candidates: list[Any] = []
    if runtime_smoke is not None:
        issues = runtime_smoke.get("issues")
        if isinstance(issues, (list, tuple)):
            candidates.extend(issues)
        elif issues:
            candidates.append(issues)
        audit = _mapping_or_none(runtime_smoke.get("runtime_audit_failure"))
        if audit is not None:
            candidates.extend(
                [
                    audit.get("detail"),
                    _runtime_event_text(audit.get("solver_algorithm_events")),
                    audit.get("error_category"),
                ]
            )
        runtime = _mapping_or_none(runtime_smoke.get("runtime"))
        if runtime is not None:
            candidates.extend(
                [
                    _runtime_event_text(runtime.get("solver_algorithm_events")),
                    (
                        f"solver_algorithm_errors={runtime.get('solver_algorithm_errors')}"
                        if runtime.get("solver_algorithm_errors") not in (None, "")
                        else None
                    ),
                ]
            )
    telemetry_issue = _telemetry_guard_primary_issue(telemetry_guard)
    if telemetry_issue:
        candidates.append(telemetry_issue)
    if subprocess_tail is not None:
        candidates.extend(
            [
                subprocess_tail.get("detail"),
                subprocess_tail.get("stderr_tail"),
                subprocess_tail.get("stdout_tail"),
            ]
        )
    candidates.extend(
        [
            raw_payload.get("issue_summary"),
            raw_payload.get("errors"),
        ]
    )
    for candidate in candidates:
        text = _compact_agent_text(candidate)
        if text:
            return text
    return ""


def _algorithm_smoke_failure_class(
    *,
    passed: bool,
    raw_payload: Mapping[str, Any],
    runtime_smoke: Mapping[str, Any] | None,
    telemetry_guard: Mapping[str, Any] | None,
    primary_issue: str,
    subprocess_tail: Mapping[str, Any] | None,
) -> str:
    if passed:
        return "passed"
    if telemetry_guard is not None and telemetry_guard.get("triggered"):
        return "telemetry_guard_failure"
    if runtime_smoke is not None:
        if runtime_smoke.get("runtime_audit_failure") not in (None, "", {}, []):
            return "runtime_audit_failure"
        run = _mapping_or_none(runtime_smoke.get("run"))
        if run is not None and run.get("success") is False:
            return "runtime_execution_failure"
    if subprocess_tail is not None and subprocess_tail.get("error_category"):
        return "runtime_execution_failure"
    lowered = primary_issue.lower()
    if "zero active search" in lowered:
        return "zero_search_effort"
    if "low active search" in lowered or "under-spent" in lowered:
        return "low_search_effort"
    if "micro-benchmark" in lowered or "objective regression" in lowered:
        return "objective_regression"
    if _algorithm_smoke_failed_checks(
        raw_payload,
        runtime_smoke=runtime_smoke,
        primary_issue="",
        failure_class="static_contract_failure",
    ):
        return "static_contract_failure"
    return "algorithm_smoke_failure"


def _algorithm_smoke_repair_hints(
    raw_payload: Mapping[str, Any],
    *,
    runtime_smoke: Mapping[str, Any] | None,
    telemetry_guard: Mapping[str, Any] | None,
) -> list[str]:
    hints: list[str] = []
    if runtime_smoke is not None:
        hints.extend(_compact_agent_text_list(runtime_smoke.get("repair_guidance")))
    for section_name in ("patch", "hypothesis", "problem_preview"):
        section = _mapping_or_none(raw_payload.get(section_name))
        if section is None:
            continue
        hints.extend(_compact_agent_text_list(section.get("repair_guidance")))
        hints.extend(_compact_agent_text_list(section.get("repair_hints")))
    if telemetry_guard is not None and telemetry_guard.get("triggered"):
        first_failure = _first_mapping(telemetry_guard.get("failures"))
        field = str(first_failure.get("field") or "").strip() if first_failure else ""
        mechanism = (
            str(first_failure.get("mechanism") or "").strip()
            if first_failure
            else ""
        )
        hint = "Ensure the candidate emits positive runtime evidence"
        if mechanism:
            hint += f" for declared mechanism {mechanism}"
        if field:
            hint += f" via {field}"
        hints.append(hint + ".")
    return list(dict.fromkeys(hints))[:_ALGORITHM_SMOKE_AGENT_LIST_ITEMS]


def _algorithm_smoke_failed_checks(
    raw_payload: Mapping[str, Any],
    *,
    runtime_smoke: Mapping[str, Any] | None,
    primary_issue: str,
    failure_class: str,
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for section_name in ("hypothesis", "patch", "problem_preview"):
        section = _mapping_or_none(raw_payload.get(section_name))
        checks.extend(_failed_check_summaries(section, prefix=section_name))
    if runtime_smoke is not None:
        telemetry = _mapping_or_none(runtime_smoke.get("telemetry_guard"))
        if telemetry is not None and telemetry.get("passed") is False:
            first_failure = _first_mapping(telemetry.get("failures"))
            checks.append(
                _drop_empty_items(
                    {
                        "name": "runtime_smoke.telemetry_guard",
                        "passed": False,
                        "detail": _telemetry_guard_primary_issue(
                            _compact_algorithm_smoke_telemetry_guard(telemetry)
                        ),
                        "code": first_failure.get("code") if first_failure else None,
                    }
                )
            )
    if not checks and primary_issue:
        checks.append(
            {
                "name": failure_class or "algorithm_smoke",
                "passed": False,
                "detail": _limit_text(primary_issue, _ALGORITHM_SMOKE_AGENT_TEXT_CHARS),
            }
        )
    return checks[:_ALGORITHM_SMOKE_AGENT_LIST_ITEMS]


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


def _algorithm_smoke_runtime_agent_section(
    runtime_smoke: Mapping[str, Any] | None,
    *,
    telemetry_guard: Mapping[str, Any] | None,
    runtime_counters: Mapping[str, Any] | None,
    subprocess_tail: Mapping[str, Any] | None,
    runtime_comparison: Mapping[str, Any] | None,
    repair_hints: list[str],
) -> dict[str, Any] | None:
    if runtime_smoke is None:
        return None
    compact = _drop_empty_items(
        {
            "passed": runtime_smoke.get("passed"),
            "runtime_smoke_run": runtime_smoke.get("runtime_smoke_run"),
            "workspace_materialized": runtime_smoke.get("workspace_materialized"),
            "selected_surface": runtime_smoke.get("selected_surface"),
            "case": runtime_smoke.get("case"),
            "case_path_ref": runtime_smoke.get("case_path_ref"),
            "data_root_source": runtime_smoke.get("data_root_source"),
            "data_root_status": runtime_smoke.get("data_root_status"),
            "provenance": _compact_runtime_provenance(runtime_smoke.get("provenance")),
            "seed": runtime_smoke.get("seed"),
            "case_count": runtime_smoke.get("case_count"),
            "issues": _compact_agent_text_list(runtime_smoke.get("issues")),
            "repair_guidance": repair_hints,
            "runtime_audit_failure": _compact_runtime_audit_failure_for_agent(
                runtime_smoke.get("runtime_audit_failure")
            ),
            "telemetry_guard": telemetry_guard,
            "runtime_counters": runtime_counters,
            "subprocess": subprocess_tail,
            "micro_benchmark": runtime_comparison,
        }
    )
    return compact or None


def _compact_runtime_provenance(value: Any) -> dict[str, Any] | None:
    provenance = _mapping_or_none(value)
    if provenance is None:
        return None
    return _drop_empty_items(
        {
            "source": provenance.get("source"),
            "case_ref": provenance.get("case_ref"),
            "data_root_source": provenance.get("data_root_source"),
            "data_root_status": provenance.get("data_root_status"),
            "absolute_paths_exposed": provenance.get("absolute_paths_exposed"),
        }
    )


def _compact_runtime_audit_failure_for_agent(value: Any) -> dict[str, Any] | None:
    audit = _mapping_or_none(value)
    if audit is None:
        text = _compact_agent_text(value)
        return {"detail": text} if text else None
    event_text = _runtime_event_text(audit.get("solver_algorithm_events"))
    compact = _drop_empty_items(
        {
            "error_category": _compact_agent_text(
                audit.get("error_category"),
                max_chars=160,
            ),
            "detail": _compact_agent_text(audit.get("detail")),
            "failed_runtime_fields": _compact_agent_text_list(
                audit.get("failed_runtime_fields")
            ),
            "solver_algorithm_errors": audit.get("solver_algorithm_errors"),
            "event_tail": event_text,
        }
    )
    return compact or None


def _compact_algorithm_smoke_runtime_counters(value: Any) -> dict[str, Any] | None:
    runtime = _mapping_or_none(value)
    if runtime is None:
        return None
    keys = (
        "solver_algorithm_path",
        "solver_algorithm_loaded",
        "solver_algorithm_active",
        "solver_algorithm_errors",
        "solver_algorithm_elapsed_ms",
        "solver_algorithm_solution_valid",
        "solver_algorithm_total_distance",
        "solver_algorithm_fleet_violation",
        "solver_algorithm_baseline_calls",
        "solver_algorithm_baseline_errors",
        "solver_algorithm_search_iterations",
        "solver_algorithm_move_attempts",
        "solver_algorithm_accepted_moves",
        "solver_algorithm_improving_moves",
        "solver_algorithm_best_delta",
        "solver_algorithm_phase_delta_sum",
        "solver_algorithm_stop_reason",
    )
    compact: dict[str, Any] = {}
    for key in keys:
        if key not in runtime:
            continue
        if key == "solver_algorithm_path":
            path = str(runtime.get(key) or "")
            if path.startswith("/"):
                continue
            compact[key] = path
            continue
        compact[key] = runtime.get(key)
        if len(compact) >= _ALGORITHM_SMOKE_AGENT_COUNTER_ITEMS:
            break
    return _drop_empty_items(compact) or None


def _compact_algorithm_smoke_subprocess(value: Any) -> dict[str, Any] | None:
    run = _mapping_or_none(value)
    if run is None:
        return None
    compact = _drop_empty_items(
        {
            "success": run.get("success"),
            "exit_code": run.get("exit_code"),
            "elapsed_ms": run.get("elapsed_ms"),
            "error_category": _compact_agent_text(
                run.get("error_category"),
                max_chars=160,
            ),
            "detail": _compact_agent_text(run.get("detail")),
            "stderr_tail": _tail_text(run.get("stderr")),
            "stdout_tail": _tail_text(run.get("stdout")),
        }
    )
    return compact or None


def _compact_algorithm_smoke_runtime_comparison(
    runtime_smoke: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    if runtime_smoke is None:
        return None
    benchmark = _mapping_or_none(runtime_smoke.get("micro_benchmark"))
    if benchmark is None:
        return None
    representative = _representative_micro_result(
        benchmark.get("results"),
        runtime_smoke.get("runs"),
    )
    compact = _drop_empty_items(
        {
            "non_promotional": benchmark.get("non_promotional", True),
            "tainted_debug": benchmark.get("tainted_debug", True),
            "comparable_cases": benchmark.get("comparable_cases"),
            "wins": benchmark.get("wins"),
            "losses": benchmark.get("losses"),
            "ties": benchmark.get("ties"),
            "representative_case": representative,
        }
    )
    return compact or None


def _representative_micro_result(results: Any, runs: Any) -> dict[str, Any] | None:
    selected: Mapping[str, Any] | None = None
    if isinstance(results, (list, tuple)):
        for item in results:
            if isinstance(item, Mapping) and item.get("comparison") == "loss":
                selected = item
                break
        if selected is None:
            selected = next((item for item in results if isinstance(item, Mapping)), None)
    raw_run_micro: Mapping[str, Any] | None = None
    raw_objective: Mapping[str, Any] | None = None
    if isinstance(runs, (list, tuple)):
        for run in runs:
            if not isinstance(run, Mapping):
                continue
            micro = _mapping_or_none(run.get("micro_benchmark"))
            if selected is None and micro is not None:
                selected = micro
            if selected is not None and micro is not None:
                raw_run_micro = micro
                raw_objective = _mapping_or_none(run.get("objective"))
                break
    if selected is None:
        return None
    raw_run_micro = raw_run_micro or selected
    compact = _drop_empty_items(
        {
            "label": selected.get("label"),
            "case": selected.get("case"),
            "seed": selected.get("seed"),
            "comparison": selected.get("comparison"),
            "delta": selected.get("delta"),
            "decisive_metric": selected.get("decisive_metric"),
            "runtime_delta_ms": selected.get("runtime_delta_ms"),
            "candidate_objective": _compact_objective(
                raw_run_micro.get("candidate_objective") or raw_objective
            ),
            "champion_objective": _compact_objective(
                raw_run_micro.get("champion_objective")
            ),
        }
    )
    return compact or None


def _compact_objective(value: Any) -> dict[str, Any] | None:
    objective = _mapping_or_none(value)
    if objective is None:
        return None
    return _drop_empty_items(
        {
            key: objective.get(key)
            for key in ("fleet_violation", "total_distance")
            if key in objective
        }
    ) or None


def _compact_algorithm_smoke_telemetry_guard(value: Any) -> dict[str, Any] | None:
    guard = _mapping_or_none(value)
    if guard is None:
        return None
    failures = _compact_telemetry_issues(guard.get("failures"))
    warnings = _compact_telemetry_issues(guard.get("warnings"), limit=3)
    first_failure = failures[0] if failures else None
    compact = _drop_empty_items(
        {
            "triggered": bool(failures),
            "passed": guard.get("passed"),
            "selected_surface": guard.get("selected_surface"),
            "failure_code": first_failure.get("code") if first_failure else None,
            "mechanism": first_failure.get("mechanism") if first_failure else None,
            "category": first_failure.get("category") if first_failure else None,
            "field": first_failure.get("field") if first_failure else None,
            "counters": first_failure.get("counters") if first_failure else None,
            "candidate_runs": guard.get("candidate_runs"),
            "champion_runs": guard.get("champion_runs"),
            "expected_telemetry_present": guard.get("expected_telemetry_present"),
            "implicit_activity_claim": guard.get("implicit_activity_claim"),
            "declared_mechanisms": _compact_agent_text_list(
                guard.get("declared_mechanisms")
            ),
            "failures": failures,
            "warnings": warnings,
        }
    )
    return compact or None


def _compact_telemetry_issues(value: Any, *, limit: int = 4) -> list[dict[str, Any]]:
    if not isinstance(value, (list, tuple)):
        return []
    issues: list[dict[str, Any]] = []
    for item in value[:limit]:
        if not isinstance(item, Mapping):
            continue
        counters = {
            key: item.get(key)
            for key in (
                "candidate_positive",
                "candidate_present",
                "candidate_missing",
                "champion_positive",
            )
            if key in item
        }
        issues.append(
            _drop_empty_items(
                {
                    "code": item.get("code"),
                    "severity": item.get("severity"),
                    "mechanism": item.get("mechanism"),
                    "category": item.get("category"),
                    "field": item.get("field"),
                    "counters": counters,
                }
            )
        )
    return issues


def _telemetry_guard_primary_issue(value: Mapping[str, Any] | None) -> str | None:
    if value is None:
        return None
    first = _first_mapping(value.get("failures"))
    if not first:
        return None
    parts = ["telemetry guard failed"]
    for label, key in (
        ("code", "code"),
        ("mechanism", "mechanism"),
        ("category", "category"),
        ("field", "field"),
    ):
        if first.get(key):
            parts.append(f"{label}={first.get(key)}")
    counters = _mapping_or_none(first.get("counters"))
    if counters:
        parts.extend(f"{key}={counters[key]}" for key in sorted(counters))
    return _limit_text("; ".join(parts), _ALGORITHM_SMOKE_AGENT_TEXT_CHARS)


def _first_mapping(value: Any) -> Mapping[str, Any] | None:
    if isinstance(value, (list, tuple)):
        for item in value:
            if isinstance(item, Mapping):
                return item
    return None


def _runtime_event_text(value: Any) -> str:
    if value in (None, "", [], {}):
        return ""
    return _limit_text(
        json.dumps(_strip_forbidden_value(value), sort_keys=True, default=str),
        _ALGORITHM_SMOKE_AGENT_TEXT_CHARS,
    )


def _compact_agent_text_list(
    value: Any,
    *,
    limit: int = _ALGORITHM_SMOKE_AGENT_LIST_ITEMS,
) -> list[str]:
    if value in (None, "", [], {}):
        return []
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, Mapping):
        values = [
            json.dumps(_strip_forbidden_value(value), sort_keys=True, default=str)
        ]
    else:
        try:
            values = list(value)
        except TypeError:
            values = [value]
    compact: list[str] = []
    for item in values:
        text = _compact_agent_text(item)
        if text and text not in compact:
            compact.append(text)
        if len(compact) >= limit:
            break
    return compact


def _compact_agent_text(
    value: Any,
    *,
    max_chars: int = _ALGORITHM_SMOKE_AGENT_TEXT_CHARS,
) -> str:
    if value in (None, "", [], {}):
        return ""
    if isinstance(value, str):
        text = value
    else:
        text = json.dumps(_strip_forbidden_value(value), sort_keys=True, default=str)
    return _limit_text(text.strip(), max_chars)


def _tail_text(value: Any, *, max_chars: int = _ALGORITHM_SMOKE_AGENT_TAIL_CHARS) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    return "[tail]\n" + text[-max_chars:]


def _hypothesis_from_input(value: HypothesisProposalInput) -> HypothesisProposal:
    return HypothesisProposal(
        hypothesis_text=value.hypothesis_text,
        change_locus=value.change_locus,
        action=value.action,  # type: ignore[arg-type]
        target_file=value.target_file or None,
        predicted_direction=value.predicted_direction,  # type: ignore[arg-type]
        target_weakness=value.target_weakness,
        expected_effect=value.expected_effect,
        suggested_weight=value.suggested_weight,
        target_objectives=tuple(value.target_objectives or ()),
        protected_objectives=tuple(value.protected_objectives or ()),
        objective_tradeoff_policy=value.objective_tradeoff_policy,
        no_op_condition=value.no_op_condition,
        risk_to_higher_priority=value.risk_to_higher_priority,
        target_runtime_effect=value.target_runtime_effect,
        complexity_claim=value.complexity_claim,
        runtime_budget_strategy=value.runtime_budget_strategy,
        expected_telemetry=dict(value.expected_telemetry or {}),
        novelty_signature=dict(value.novelty_signature or {}),
        mechanism_changes=tuple(
            MechanismChange(id=change.id, change_type=change.change_type)
            for change in value.mechanism_changes
        ),
    )

def _patch_from_input(value: PatchProposalInput) -> PatchProposal:
    return PatchProposal(
        file_path=value.file_path,
        action=value.action,  # type: ignore[arg-type]
        code_content=value.code_content,
        test_hint=value.test_hint or None,
        additional_changes=tuple(
            PatchFileChange(
                file_path=change.file_path,
                action=change.action,  # type: ignore[arg-type]
                code_content=change.code_content,
                test_hint=change.test_hint or None,
            )
            for change in value.additional_changes
        ),
        premise_check=value.premise_check,
        premise_check_reason=value.premise_check_reason,
        mechanism_changes=tuple(
            MechanismChange(id=change.id, change_type=change.change_type)
            for change in value.mechanism_changes
        ),
    )

def _schema_preview_hypothesis_payload(
    context: ProposalToolContext,
    raw: Mapping[str, Any],
) -> dict[str, Any]:
    try:
        validated = DraftHypothesisInput.model_validate(dict(raw))
    except ValidationError as exc:
        return {
            "passed": False,
            "errors": exc.errors(include_url=False),
        }
    hypothesis = _hypothesis_from_input(validated)
    schema_result = _hypothesis_schema_preview(context, hypothesis)
    return {
        **schema_result,
        "hypothesis": _hypothesis_preview_summary(hypothesis),
        "hypothesis_object": hypothesis,
    }

def _hypothesis_preview_summary(
    hypothesis: HypothesisProposal,
) -> dict[str, Any]:
    novelty_signature = (
        hypothesis.novelty_signature
        if isinstance(hypothesis.novelty_signature, Mapping)
        else {}
    )
    novelty_payload: dict[str, Any] = {}
    for idx, (key, value) in enumerate(
        sorted(novelty_signature.items(), key=lambda item: str(item[0]))
    ):
        if idx >= _PREVIEW_MAX_CHECKS:
            break
        novelty_payload[str(key)] = _compact_preview_value(value)
    return _drop_empty_items(
        {
            "change_locus": hypothesis.change_locus,
            "action": hypothesis.action,
            "target_file": hypothesis.target_file,
            "predicted_direction": hypothesis.predicted_direction,
            "target_objectives": list(hypothesis.target_objectives),
            "protected_objectives": list(hypothesis.protected_objectives),
            "target_runtime_effect": hypothesis.target_runtime_effect,
            "suggested_weight": hypothesis.suggested_weight,
            "novelty_signature_keys": [
                str(key)
                for key in sorted(novelty_signature.keys(), key=str)[
                    :_PREVIEW_MAX_CHECKS
                ]
            ],
            "novelty_signature": novelty_payload,
            "hypothesis_text_chars": len(hypothesis.hypothesis_text or ""),
            "expected_effect_chars": len(hypothesis.expected_effect or ""),
            "runtime_budget_strategy_chars": len(
                hypothesis.runtime_budget_strategy or ""
            ),
            "expected_telemetry": _compact_preview_value(
                getattr(hypothesis, "expected_telemetry", {}) or {}
            ),
            "mechanism_changes": _compact_preview_value(
                [
                    {"id": change.id, "change_type": change.change_type}
                    for change in getattr(hypothesis, "mechanism_changes", ()) or ()
                ]
            ),
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

def _schema_preview_patch_payload(raw: Mapping[str, Any]) -> dict[str, Any]:
    try:
        payload = dict(raw)
        payload.pop("repair_attribution", None)
        validated = DraftPatchInput.model_validate(payload)
    except ValidationError as exc:
        return {
            "passed": False,
            "errors": exc.errors(include_url=False),
        }
    patch = _patch_from_input(validated)
    path_errors = []
    for index, change in enumerate(patch_file_changes(patch)):
        path_error = _patch_path_error(change.file_path)
        if path_error is not None:
            loc = ("file_path",) if index == 0 else (
                "additional_changes",
                index - 1,
                "file_path",
            )
            path_errors.append({"loc": loc, "msg": path_error})
    patch_summary = _patch_preview_summary(patch)
    if path_errors:
        return {
            "passed": False,
            "errors": path_errors,
            "patch": patch_summary,
        }
    return {
        "passed": True,
        "errors": [],
        "patch": patch_summary,
        "patch_object": patch,
    }

def _hypothesis_schema_preview(
    context: ProposalToolContext,
    hypothesis: HypothesisProposal,
) -> dict[str, Any]:
    result = _contract_gate(context).validate_hypothesis(
        hypothesis,
        [],
        [],
        current_champion_version=_champion_version(context.champion),
    )
    schema_check_names = {
        "C1_schema",
        "C11_expected_telemetry",
        "C12_mechanism_binding",
    }
    c1_checks = [check for check in result.checks if check.name in schema_check_names]
    c11_check = next(
        (check for check in result.checks if check.name == "C11_expected_telemetry"),
        None,
    )
    c12_check = next(
        (check for check in result.checks if check.name == "C12_mechanism_binding"),
        None,
    )
    novelty_guidance = _semantic_signature_preview_guidance(context, hypothesis)
    passed = bool(c1_checks and all(check.passed for check in c1_checks))
    forced_violation = _forced_hypothesis_violation(context, hypothesis)
    if forced_violation is not None:
        passed = False
    if novelty_guidance.get("required") and (
        novelty_guidance.get("missing_fields")
        or novelty_guidance.get("invalid_fields")
    ):
        passed = False
    return {
        "passed": passed,
        "checks": _checks_payload(
            c1_checks,
            detail_chars=_PREVIEW_CHECK_DETAIL_CHARS,
            max_checks=4,
        ),
        "failure_reason": (
            None
            if passed
            else (
                forced_violation
                if forced_violation is not None
                else (
                    novelty_guidance.get("detail")
                    if (
                        novelty_guidance.get("missing_fields")
                        or novelty_guidance.get("invalid_fields")
                    )
                    else _limit_text(
                        _first_failure(c1_checks) or "", _PREVIEW_FAILURE_REASON_CHARS
                    )
                )
            )
        ),
        "expected_telemetry_contract": _expected_telemetry_contract_preview(
            context,
            hypothesis,
            c11_check,
        ),
        "mechanism_binding": _mechanism_binding_preview(hypothesis, c12_check),
        "forced_surface_constraint": _forced_surface_constraint_payload(context),
        "novelty_signature_guidance": novelty_guidance,
    }


def _expected_telemetry_contract_preview(
    context: ProposalToolContext,
    hypothesis: HypothesisProposal,
    c11_check: Any | None,
) -> dict[str, Any]:
    expected = getattr(hypothesis, "expected_telemetry", {}) or {}
    requested_categories: list[str] = []
    invalid_categories: list[str] = []
    if isinstance(expected, Mapping):
        for raw_category in expected:
            category = str(raw_category or "").strip().lower()
            if not category:
                continue
            requested_categories.append(category)
            if category not in EXPECTED_TELEMETRY_CATEGORIES and category not in {
                "mechanism",
                "mechanisms",
                "declared_mechanism",
                "declared_mechanisms",
                "declared_mechanism_change",
                "declared_mechanism_changes",
                "mechanism_change",
                "mechanism_changes",
            }:
                invalid_categories.append(category)

    surface = _surface_for_hypothesis(context, hypothesis)
    declared_fields = sorted(declared_surface_telemetry_fields(surface))
    try:
        problem_spec = _contract_problem_spec(context)
    except Exception:
        problem_spec = None
    mechanism_fields = sorted(
        {
            probe.field
            for probe in declared_mechanism_runtime_probes(
                problem_spec=problem_spec,
                surface=surface,
                declared_mechanisms=mechanism_changes(hypothesis),
            )
        }
    )
    claims = normalize_expected_telemetry(expected)
    requested_fields = {
        category: list(fields)
        for category, fields in sorted(claims.items())
        if fields
    }
    passed = None if c11_check is None else bool(_attr(c11_check, "passed"))
    detail = "" if c11_check is None or passed else str(_attr(c11_check, "detail", ""))
    return _drop_empty_items(
        {
            "name": "C11_expected_telemetry",
            "passed": passed,
            "detail": _limit_text(detail, _PREVIEW_FAILURE_REASON_CHARS),
            "requested_categories": requested_categories,
            "invalid_categories": sorted(dict.fromkeys(invalid_categories)),
            "allowed_categories": sorted(EXPECTED_TELEMETRY_CATEGORIES),
            "requested_fields": requested_fields,
            "declared_runtime_fields": declared_fields[:_PREVIEW_MAX_CHECKS * 4],
            "declared_mechanism_runtime_fields": mechanism_fields[
                : _PREVIEW_MAX_CHECKS * 4
            ],
            "repair_hint": (
                "Use only allowed expected_telemetry categories and runtime keys "
                "declared by the selected research surface evidence contract."
                if not passed
                else ""
            ),
        }
    )


def _mechanism_binding_preview(
    hypothesis: HypothesisProposal,
    c12_check: Any | None,
) -> dict[str, Any]:
    passed = None if c12_check is None else bool(_attr(c12_check, "passed"))
    detail = "" if c12_check is None or passed else str(_attr(c12_check, "detail", ""))
    return _drop_empty_items(
        {
            "name": "C12_mechanism_binding",
            "passed": passed,
            "detail": _limit_text(detail, _PREVIEW_FAILURE_REASON_CHARS),
            "mechanism_changes": _compact_preview_value(
                [
                    {"id": change.id, "change_type": change.change_type}
                    for change in mechanism_changes(hypothesis)
                ]
            ),
            "repair_hint": (
                "Declare mechanism_changes that match the selected surface "
                "mechanism telemetry and echo them in the patch."
                if not passed
                else ""
            ),
        }
    )

def _semantic_signature_preview_guidance(
    context: ProposalToolContext,
    hypothesis: HypothesisProposal,
) -> dict[str, Any]:
    surface = _surface_for_hypothesis(context, hypothesis)
    novelty = _attr(surface, "novelty") if surface is not None else None
    strategy = str(_attr(novelty, "strategy", "") or "")
    fields = _coerce_compact_list(_attr(novelty, "signature_fields", []))
    if strategy != "semantic_signature" or not fields:
        return {}

    missing: list[str] = []
    invalid_sequence: list[str] = []
    invalid_scalar: list[str] = []
    unsupported: list[str] = []
    for field in fields:
        name = str(field).strip()
        if not name:
            continue
        if not ContractGate.supports_semantic_signature_field(name):
            unsupported.append(name)
            continue
        if name in {"predicted_direction", "target_objectives", "protected_objectives"}:
            value = getattr(hypothesis, name, None)
            if value in (None, "", [], (), {}):
                missing.append(name)
            continue
        values = hypothesis.novelty_signature
        if (
            not isinstance(values, dict)
            or name not in values
            or _semantic_signature_value_missing(values[name])
        ):
            missing.append(name)
            continue
        if (
            name in _NONEMPTY_SEQUENCE_NOVELTY_FIELDS
            and not _is_nonempty_text_sequence(values[name])
        ):
            invalid_sequence.append(name)
        if (
            isinstance(values.get(name), str)
            and len(values[name].strip()) > _SEMANTIC_SIGNATURE_SCALAR_STRING_CHARS
        ):
            invalid_scalar.append(
                f"{name} > {_SEMANTIC_SIGNATURE_SCALAR_STRING_CHARS} chars"
            )

    detail = ""
    if missing:
        detail = (
            "missing structured novelty_signature identity for semantic_signature "
            f"surface '{hypothesis.change_locus}': {', '.join(missing)}"
        )
    elif invalid_sequence:
        detail = (
            "invalid structured novelty_signature identity for semantic_signature "
            f"surface '{hypothesis.change_locus}': {', '.join(invalid_sequence)} "
            "must be non-empty arrays of component names"
        )
    elif invalid_scalar:
        detail = (
            "invalid structured novelty_signature identity for semantic_signature "
            f"surface '{hypothesis.change_locus}': {', '.join(invalid_scalar)}. "
            "Use compact tokens or short phrases and put rationale in "
            "hypothesis_text."
        )
    elif unsupported:
        detail = (
            "unsupported novelty.signature_fields for semantic_signature surface "
            f"'{hypothesis.change_locus}': {', '.join(unsupported)}"
        )
    else:
        detail = (
            "semantic_signature identity is present; contract preview/C10 will "
            "still reject duplicate structured values."
        )
    return _drop_empty_items(
        {
            "required": True,
            "strategy": strategy,
            "signature_fields": fields,
            "missing_fields": missing,
            "invalid_fields": [*invalid_sequence, *invalid_scalar],
            "nonempty_sequence_fields": [
                field for field in fields if field in _NONEMPTY_SEQUENCE_NOVELTY_FIELDS
            ],
            "unsupported_fields": unsupported,
            "detail": detail,
        }
    )

def _semantic_signature_value_missing(value: Any) -> bool:
    if value is None or value is False:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, set, frozenset, dict)):
        return len(value) == 0
    return False

def _is_nonempty_text_sequence(value: Any) -> bool:
    if not isinstance(value, (list, tuple, set, frozenset)) or not value:
        return False
    return all(isinstance(item, str) and bool(item.strip()) for item in value)

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
                next_context = key_text if key_text in {"hypothesis", "patch"} else context
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

def _forced_surface_constraint_payload(
    context: ProposalToolContext,
) -> dict[str, Any] | None:
    surface = str(context.forced_surface or "").strip()
    if not surface:
        return None
    return _drop_empty_items(
        {
            "surface": surface,
            "action": str(context.forced_action or "").strip() or None,
            "target_file": str(context.forced_target_file or "").strip() or None,
            "rule": (
                "Hypothesis outputs and proposal previews must use exactly this "
                "research surface"
                + (", action" if context.forced_action else "")
                + (", and target_file" if context.forced_target_file else "")
                + ". Off-surface hypotheses fail closed before code generation."
            ),
        }
    )

def _active_problem_boundary_constraint_payload(
    context: ProposalToolContext,
) -> dict[str, Any] | None:
    surfaces = [
        str(surface or "").strip()
        for surface in context.active_problem_boundary_surfaces
        if str(surface or "").strip()
    ]
    if not surfaces:
        return None
    novelty_requirements = _active_boundary_novelty_requirements(context, surfaces)
    return {
        "surfaces": surfaces,
        "rule": (
            "Hypothesis outputs must keep change_locus on the active "
            "problem-object boundary. Component policies may appear only as "
            "implementation hooks or attribution evidence, not replacement "
            "research goals."
        ),
        "novelty_signature_requirements": novelty_requirements,
    }

def _active_boundary_novelty_requirements(
    context: ProposalToolContext,
    surfaces: list[str],
) -> dict[str, Any]:
    requirements: dict[str, Any] = {}
    for surface_name in surfaces:
        surface = _find_surface(context, surface_name)
        requirement = _surface_novelty_signature_requirement(surface)
        if requirement:
            requirements[surface_name] = requirement
    return requirements

def _forced_hypothesis_violation(
    context: ProposalToolContext,
    hypothesis: HypothesisProposal,
) -> str | None:
    forced = _forced_action_target_violation(
        context,
        change_locus=hypothesis.change_locus,
        action=hypothesis.action,
        target_file=hypothesis.target_file,
    )
    if forced is not None:
        return forced
    return _active_problem_boundary_violation(
        context,
        change_locus=hypothesis.change_locus,
    )

def _active_problem_boundary_violation(
    context: ProposalToolContext,
    *,
    change_locus: str | None,
) -> str | None:
    if context.forced_surface:
        return None
    boundary = [
        str(surface or "").strip()
        for surface in context.active_problem_boundary_surfaces
        if str(surface or "").strip()
    ]
    if not boundary:
        return None
    actual = str(change_locus or "").strip()
    if actual in set(boundary):
        return None
    return (
        "active_problem_boundary_constraint: change_locus must stay within "
        f"{boundary!r}; got {actual!r}. Component policies are implementation "
        "hooks or attribution evidence, not replacement research goals."
    )

def _forced_action_target_violation(
    context: ProposalToolContext,
    *,
    change_locus: str | None,
    action: str | None,
    target_file: str | None,
) -> str | None:
    forced_surface = str(context.forced_surface or "").strip()
    if not forced_surface:
        return None
    actual_surface = str(change_locus or "").strip()
    if actual_surface != forced_surface:
        return (
            "forced_surface_constraint: change_locus must be "
            f"{forced_surface!r}, got {actual_surface!r}"
        )
    forced_action = str(context.forced_action or "").strip()
    if forced_action and str(action or "").strip() != forced_action:
        return (
            "forced_surface_constraint: action must be "
            f"{forced_action!r}, got {str(action or '').strip()!r}"
        )
    forced_target = str(context.forced_target_file or "").strip()
    if forced_target:
        actual_target = str(target_file or "").strip()
        if _normalize_rel_path(actual_target) != _normalize_rel_path(forced_target):
            return (
                "forced_surface_constraint: target_file must be "
                f"{forced_target!r}, got {actual_target!r}"
            )
    return None

def _hypothesis_selected_surface(
    hypothesis: HypothesisProposal | None,
) -> str | None:
    if hypothesis is None:
        return None
    value = str(getattr(hypothesis, "change_locus", "") or "").strip()
    return value or None

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

__all__ = [
    "AlgorithmSmokeTool",
    "ContractPreviewTool",
    "DraftHypothesisTool",
    "DraftPatchTool",
    "InterfacePreviewTool",
    "SchemaPreviewTool",
    "TargetPermissionPreviewTool",
    "compact_algorithm_smoke_observation_for_agent",
    "_ALGORITHM_SMOKE_DEFAULT_SEED",
    "_ALGORITHM_SMOKE_LOW_EFFORT_MAX_ATTEMPTS",
    "_ALGORITHM_SMOKE_LOW_EFFORT_MAX_ITERATIONS",
    "_ALGORITHM_SMOKE_LOW_EFFORT_MAX_RUNTIME_RATIO",
    "_ALGORITHM_SMOKE_LOW_EFFORT_MIN_CASES",
    "_ALGORITHM_SMOKE_LOW_EFFORT_STOP_REASONS",
    "_ALGORITHM_SMOKE_MAX_SCREENING_CASES",
    "_ALGORITHM_SMOKE_TIMEOUT_SEC",
    "_ALGORITHM_SMOKE_TIME_LIMIT_SEC",
    "_NONEMPTY_SEQUENCE_NOVELTY_FIELDS",
    "_PREVIEW_CHECK_DETAIL_CHARS",
    "_PREVIEW_FAILURE_REASON_CHARS",
    "_PREVIEW_MAX_CHECKS",
    "_PREVIEW_PROBLEM_ISSUE_CHARS",
    "_PREVIEW_PROBLEM_MAX_CHECKS",
    "_RuntimeSmokeCase",
    "_SEMANTIC_SIGNATURE_SCALAR_STRING_CHARS",
    "_active_boundary_novelty_requirements",
    "_active_problem_boundary_constraint_payload",
    "_active_problem_boundary_violation",
    "_apply_file_change_to_runtime_smoke_workspace",
    "_apply_patch_to_runtime_smoke_workspace",
    "_artifact_id",
    "_champion_version",
    "_checks_payload",
    "_compact_preview_value",
    "_compact_problem_preview",
    "_compact_problem_preview_checks",
    "_compact_runtime_audit_failure",
    "_compact_runtime_smoke_payload",
    "_compact_solver_design_micro_benchmark",
    "_compare_solver_design_raw_outputs",
    "_contract_gate",
    "_contract_preview_issue_strings",
    "_contract_preview_issue_summary",
    "_contract_problem_spec",
    "_contract_result_payload",
    "_contract_summary_payload",
    "_drop_internal_preview_objects",
    "_ensure_runtime_smoke_path_writable",
    "_first_failure",
    "_first_int",
    "_float_or_none",
    "_forced_action_target_violation",
    "_forced_hypothesis_violation",
    "_forced_surface_constraint_payload",
    "_hypothesis_from_input",
    "_hypothesis_preview_summary",
    "_hypothesis_schema_preview",
    "_hypothesis_selected_surface",
    "_is_nonempty_text_sequence",
    "_is_solver_design_runtime_patch_path",
    "_load_runtime_smoke_yaml",
    "_module_classes",
    "_module_level_functions",
    "_nonnegative_int",
    "_operator_execute_signature",
    "_patch_file_change_preview_summary",
    "_patch_from_input",
    "_patch_path_error",
    "_patch_preview_summary",
    "_preview_max_checks_for_patch",
    "_problem_preview_issues",
    "_problem_spec_for_runtime_audit",
    "_problem_surface_preview",
    "_resolve_smoke_instance_path",
    "_run_solver_design_smoke",
    "_runtime_algorithm_smoke_preview",
    "_runtime_smoke_audit_failure",
    "_runtime_smoke_base_workspace",
    "_runtime_smoke_cases",
    "_runtime_smoke_stage_arguments",
    "_runtime_smoke_stage_value",
    "_runtime_stop_reason",
    "_schema_preview_hypothesis_payload",
    "_schema_preview_patch_payload",
    "_schema_preview_summary",
    "_select_runtime_smoke_screening_cases",
    "_semantic_signature_preview_guidance",
    "_semantic_signature_value_missing",
    "_solver_design_low_effort_issue",
    "_solver_design_micro_benchmark_issue",
    "_solver_design_micro_benchmark_result",
    "_solver_design_patch_claims_search_effort",
    "_solver_design_patch_paths",
    "_solver_design_smoke_repair_guidance",
    "_solver_design_smoke_runtime_underspent",
    "_solver_design_zero_effort_issue",
    "_solver_run_failure_detail",
    "_string_list",
]
