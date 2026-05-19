"""Algorithm smoke preview orchestration."""

from __future__ import annotations

import sys
from typing import Any

from scion.proposal import solver_design_smoke as _solver_design_smoke
from scion.proposal.tools.base import _BaseReadOnlyTool
from scion.proposal.tools.models import (
    AlgorithmSmokeInput,
    ProposalExposureLevel,
    ProposalObservation,
    ProposalToolContext,
    ProposalToolPermission,
)
from scion.proposal.tools.previews.algorithm_smoke_feedback import _algorithm_smoke_agent_payload
from scion.proposal.tools.previews.common import (
    _PREVIEW_CHECK_DETAIL_CHARS,
    _PREVIEW_MAX_CHECKS,
    _champion_version,
    _compact_problem_preview,
    _contract_gate,
    _drop_internal_preview_objects,
    _hypothesis_selected_surface,
    _problem_surface_preview,
)
from scion.proposal.tools.previews.contract import (
    _checks_payload,
    _contract_preview_issue_summary,
    _contract_result_payload,
    _contract_summary_payload,
    _preview_max_checks_for_patch,
)
from scion.proposal.tools.previews.schema import (
    _schema_preview_hypothesis_payload,
    _schema_preview_patch_payload,
)
from scion.proposal.tools.previews.telemetry_static import _mechanism_telemetry_static_preview
from scion.proposal.tools.surface import _surface_for_selected_or_patch_path

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


def _runtime_algorithm_smoke_preview_for_tool(*args: Any, **kwargs: Any) -> Any:
    facade = sys.modules.get("scion.proposal.tools.preview")
    preview_func = getattr(facade, "_runtime_algorithm_smoke_preview", None)
    if preview_func is None:
        preview_func = _runtime_algorithm_smoke_preview
    return preview_func(*args, **kwargs)

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
                    telemetry_static_preview = _mechanism_telemetry_static_preview(
                        context,
                        hypothesis_object,
                        patch_preview["patch_object"],
                    )
                    if telemetry_static_preview is not None:
                        patch_preview["telemetry_static_preview"] = (
                            telemetry_static_preview
                        )
                        payload["telemetry_static_preview"] = telemetry_static_preview
                        patch_preview["passed"] = bool(patch_preview["passed"]) and bool(
                            telemetry_static_preview.get("passed")
                        )
                    if patch_preview["passed"]:
                        smoke_preview = _runtime_algorithm_smoke_preview_for_tool(
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



__all__ = [
    "AlgorithmSmokeTool",
    "_ALGORITHM_SMOKE_DEFAULT_SEED",
    "_ALGORITHM_SMOKE_LOW_EFFORT_MAX_ATTEMPTS",
    "_ALGORITHM_SMOKE_LOW_EFFORT_MAX_ITERATIONS",
    "_ALGORITHM_SMOKE_LOW_EFFORT_MAX_RUNTIME_RATIO",
    "_ALGORITHM_SMOKE_LOW_EFFORT_MIN_CASES",
    "_ALGORITHM_SMOKE_LOW_EFFORT_STOP_REASONS",
    "_ALGORITHM_SMOKE_MAX_SCREENING_CASES",
    "_ALGORITHM_SMOKE_TIMEOUT_SEC",
    "_ALGORITHM_SMOKE_TIME_LIMIT_SEC",
    "_RuntimeSmokeCase",
    "_apply_file_change_to_runtime_smoke_workspace",
    "_apply_patch_to_runtime_smoke_workspace",
    "_compact_runtime_audit_failure",
    "_compact_runtime_smoke_payload",
    "_compact_solver_design_micro_benchmark",
    "_compare_solver_design_raw_outputs",
    "_ensure_runtime_smoke_path_writable",
    "_first_int",
    "_float_or_none",
    "_is_solver_design_runtime_patch_path",
    "_load_runtime_smoke_yaml",
    "_nonnegative_int",
    "_problem_spec_for_runtime_audit",
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
    "_select_runtime_smoke_screening_cases",
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
