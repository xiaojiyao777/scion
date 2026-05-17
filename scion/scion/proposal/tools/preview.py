"""Draft and contract preview proposal tools."""

from __future__ import annotations

import ast
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
    PatchFileChange,
    PatchProposal,
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
    _limit_text,
    _model_payload,
    _normalize_rel_path,
    _strip_forbidden_value,
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

        payload = _drop_internal_preview_objects(payload)
        issue_summary = _contract_preview_issue_summary(payload)
        if issue_summary:
            payload["issue_summary"] = issue_summary
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
                    f"{issue_summary}"
                    if issue_summary
                    else "Algorithm smoke found issues."
                )
            ),
            structured_payload=payload,
            exposure_level=ProposalExposureLevel.PUBLIC_SPEC,
        )

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
        novelty_signature=dict(value.novelty_signature or {}),
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
        validated = DraftPatchInput.model_validate(dict(raw))
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
    c1_checks = [check for check in result.checks if check.name == "C1_schema"]
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
        "forced_surface_constraint": _forced_surface_constraint_payload(context),
        "novelty_signature_guidance": novelty_guidance,
    }

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
