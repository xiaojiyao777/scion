"""AgenticSessionCodeGuidance mixin."""
from __future__ import annotations

from scion.proposal.agentic_session_common import *


class AgenticSessionCodeGuidanceMixin:
    def _code_phase_allowed_tools(
            self,
            context: ProposalToolContext,
        ) -> tuple[str, ...]:
            if self.tool_registry is None:
                return ()
            return self.tool_registry.allowed_tools_for_phase(context, "code_planning")

    def _code_phase_allowed_tool_specs(
            self,
            context: ProposalToolContext,
        ) -> tuple[dict[str, Any], ...]:
            if self.tool_registry is None:
                return ()
            return self.tool_registry.allowed_tool_specs_for_phase(
                context,
                "code_planning",
            )

    def _code_phase_budget_reserved(
            self,
            state: AgenticProposalSessionState,
        ) -> bool:
            return self._code_phase_wall_time_reserved(
                state
            ) or _code_phase_budget_reserved_for_config(
                self._tool_loop_config,
                state,
            )

    def _code_phase_wall_time_reserved(
            self,
            state: AgenticProposalSessionState,
        ) -> bool:
            max_wall_time = max(0.0, float(self._tool_loop_config.max_wall_time_sec))
            if max_wall_time <= 0:
                return self._session_timeout_reached(state)
            reserve = min(
                _FINAL_PREVIEW_WALL_TIME_RESERVE_SEC,
                max_wall_time / 4.0,
            )
            return self._remaining_wall_time_sec(state) <= reserve

    def _code_tool_arg_guidance(
            self,
            context: ProposalToolContext,
            hypothesis: HypothesisProposal,
            observations: list[ProposalObservation],
            code_context: Mapping[str, Any] | None = None,
        ) -> dict[str, Any]:
            feedback_args = _feedback_query_args(context)
            if hypothesis.change_locus and "surface" not in feedback_args:
                feedback_args["surface"] = hypothesis.change_locus
            solver_design_target = _is_solver_design_algorithm_target(
                hypothesis.target_file,
                context=context,
                surface=hypothesis.change_locus,
            )
            solver_design_surface = str(hypothesis.change_locus or "").strip() in {
                "solver_design",
                "solver_algorithm",
            }
            read_surface_args: dict[str, Any] = {
                "surface": hypothesis.change_locus,
                "detail": "full",
                "max_code_chars": (
                    _APS_SOLVER_DESIGN_CODE_SURFACE_READ_CODE_CHARS
                    if solver_design_target or solver_design_surface
                    else _APS_CODE_SURFACE_READ_CODE_CHARS
                ),
            }
            if hypothesis.target_file:
                read_surface_args["target_file"] = hypothesis.target_file
            if solver_design_target:
                read_surface_args["section"] = "target_preview"
            if _is_solver_design_support_module_target(
                hypothesis.target_file,
                context=context,
                surface=hypothesis.change_locus,
            ):
                read_surface_args["max_code_chars"] = (
                    _APS_CODE_MODULE_SURFACE_READ_CODE_CHARS
                )
            guidance = {
                "context.read_surface": {
                    "purpose": (
                        "Inspect the full approved research object before writing "
                        "the patch. This is the code phase, so a full target-surface "
                        "read is allowed within budget."
                    ),
                    "recommended_args": read_surface_args,
                    "already_has_code_phase_surface_read": _has_code_phase_surface_read(
                        observations,
                        hypothesis,
                    ),
                },
                "context.read_branch_state": {
                    "recommended_args": {},
                    "purpose": "Check retry/failure state before deciding implementation risk.",
                },
                "memory.query": {
                    "recommended_args": {
                        "surface": hypothesis.change_locus,
                        "query": (
                            "implementation lessons, failed mechanisms, and useful "
                            f"history for {hypothesis.change_locus}"
                        ),
                    },
                },
                "feedback.query_screening": {
                    "recommended_args": feedback_args,
                    "scope_rule": "Use screening feedback to avoid repeating failed mechanisms.",
                },
                "feedback.query_runtime": {
                    "recommended_args": feedback_args,
                    "scope_rule": "Use runtime feedback to tune algorithmic work and time budgets.",
                },
                "context.read_problem": {"recommended_args": {}},
                "context.read_objective_policy": {"recommended_args": {}},
                "context.read_champion_summary": {"recommended_args": {}},
            }
            if _is_solver_design_hypothesis(hypothesis):
                algorithm_file_guidance = _algorithm_file_path_guidance(
                    context,
                    observations,
                )
                visibility_context = _code_phase_source_visibility_context(
                    hypothesis,
                    observations,
                    code_context=code_context,
                )
                recommended_file_path = _recommended_algorithm_file_path(
                    algorithm_file_guidance,
                    hypothesis.target_file,
                )
                map_context = _active_solver_map_context(
                    observations,
                    target_file=hypothesis.target_file,
                )
                recommended_registry_id = str(
                    map_context.get("recommended_registry_id")
                    or "<registry_id from context.read_active_solver_map.operator_registries>"
                )
                recommended_slice_id = str(
                    map_context.get("recommended_slice_id")
                    or "<slice_id from context.read_active_solver_map.algorithm_slices>"
                )
                guidance["context.read_active_solver_map"] = {
                    "recommended_args": {
                        "surface": hypothesis.change_locus,
                    },
                    "purpose": (
                        "Read the provider-declared active solver map when "
                        "operator registries, scheduler integrations, or "
                        "algorithm slice ids are needed."
                    ),
                    "map_to_source_sequence": (
                        "Default code-phase path is map -> registry/slice -> "
                        "targeted full target/integration source only if needed."
                    ),
                    "already_has_grounding": _has_successful_tool(
                        observations,
                        "context.read_active_solver_map",
                    ),
                    "available_registry_ids": map_context.get("available_registry_ids"),
                    "available_slice_ids": map_context.get("available_slice_ids"),
                }
                guidance["context.read_operator_registry"] = {
                    "recommended_args": {
                        "surface": hypothesis.change_locus,
                        "registry_id": recommended_registry_id,
                    },
                    "purpose": (
                        "Read one provider-declared operator registry after the "
                        "active solver map exposes its registry_id."
                    ),
                    "available_registry_ids": map_context.get("available_registry_ids"),
                    "recommended_registry": map_context.get("recommended_registry"),
                }
                guidance["context.read_algorithm_slice"] = {
                    "recommended_args": {
                        "surface": hypothesis.change_locus,
                        "slice_id": recommended_slice_id,
                        "max_chars": _APS_CODE_ALGORITHM_SLICE_READ_CHARS,
                    },
                    "purpose": (
                        "Read one bounded algorithm slice after the active solver "
                        "map exposes its slice_id."
                    ),
                    "available_slice_ids": map_context.get("available_slice_ids"),
                    "algorithm_slices": map_context.get("algorithm_slices"),
                    "recommended_slice": map_context.get("recommended_slice"),
                }
                guidance["context.read_active_solver_design"] = {
                    "recommended_args": {
                        "surface": "solver_design",
                        "include_file_previews": False,
                    },
                    "purpose": (
                        "Ground solver_design implementation against the active "
                        "branch/champion solver entrypoint and mechanism summary."
                    ),
                    "already_has_grounding": _has_successful_tool(
                        observations,
                        "context.read_active_solver_design",
                    ),
                }
                guidance["context.read_solver_call_graph"] = {
                    "recommended_args": {"surface": "solver_design"},
                    "purpose": (
                        "Confirm the active solver_design call chain before choosing "
                        "where the implementation belongs."
                    ),
                    "already_has_grounding": _has_successful_solver_call_graph_grounding(
                        observations
                    ),
                }
                guidance["context.list_algorithm_files"] = {
                    "recommended_args": {
                        "surface": "solver_design",
                        "include_inactive": True,
                    },
                    "purpose": "List allowlisted active solver files before targeted reads.",
                    "consumer_tools": [
                        "context.read_algorithm_file",
                        "context.read_algorithm_symbol",
                    ],
                    "already_has_file_list": _has_successful_tool(
                        observations,
                        "context.list_algorithm_files",
                    ),
                }
                guidance["context.read_algorithm_file"] = {
                    **algorithm_file_guidance,
                    **visibility_context,
                    "recommended_args": {
                        "surface": "solver_design",
                        "file_path": recommended_file_path,
                        "max_chars": _APS_TARGET_ALGORITHM_FILE_READ_CHARS,
                    },
                    "purpose": (
                        "Read one allowlisted active solver file when full source "
                        "is needed. Code phase has a small full-file read budget; "
                        "use context.read_algorithm_symbol for extra symbols after "
                        "the approved target and owning integration files are clear."
                    ),
                    "pre_full_read_rule": (
                        "Prefer an active-map registry or algorithm slice before "
                        "additional broad full-file reads. Full files remain "
                        "allowed for the approved target/integration body when "
                        "the bounded slice is insufficient."
                    ),
                    "duplicate_read_rule": (
                        "If file_read_receipts or mandatory_visible_files already "
                        "show the same file as full-source visible, do not read it "
                        "again. Use context.read_branch_state for branch/diff state "
                        "or context.read_algorithm_symbol for a different symbol."
                    ),
                }
                guidance["context.read_algorithm_symbol"] = {
                    **algorithm_file_guidance,
                    **visibility_context,
                    "recommended_args": {
                        "surface": "solver_design",
                        "file_path": recommended_file_path,
                        "symbol": "solve",
                        "max_chars": _APS_CODE_MODULE_SURFACE_READ_CODE_CHARS,
                    },
                    "purpose": "Read one symbol from an allowlisted active solver file.",
                }
            return guidance

    def _code_phase_source_visibility_context(
            self,
            hypothesis: HypothesisProposal,
            observations: list[ProposalObservation],
            *,
            code_context: Mapping[str, Any] | None = None,
        ) -> dict[str, Any]:
            return _code_phase_source_visibility_context(
                hypothesis,
                observations,
                code_context=code_context,
            )


def _code_phase_source_visibility_context(
    hypothesis: HypothesisProposal,
    observations: list[ProposalObservation],
    *,
    code_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    target = str(getattr(hypothesis, "target_file", "") or "").strip()
    integration_paths = _integration_file_paths_from_code_context(code_context or {})
    mandatory_files: list[dict[str, Any]] = []
    if target:
        mandatory_files.append(
            {
                "file_path": target,
                "role": "approved_hypothesis_target",
                "visibility": "mandatory_visible_in_final_code_prompt",
            }
        )
    for path in integration_paths:
        if path == target:
            continue
        mandatory_files.append(
            {
                "file_path": path,
                "role": "solver_design_integration",
                "visibility": "mandatory_visible_in_final_code_prompt",
            }
        )
    receipts = _code_phase_file_read_receipts(observations)
    ordered_priority = [item["file_path"] for item in mandatory_files]
    for path in receipts:
        if path not in ordered_priority:
            ordered_priority.append(path)
    return _drop_empty_dict(
        {
            "mandatory_visible_files": mandatory_files,
            "already_visible_file_receipts": [
                {
                    "file_path": path,
                    "visibility": "already_read_or_visible",
                    "guidance": (
                        "Do not re-read this file unless exact source coverage is "
                        "insufficient for a specific symbol or branch-state check."
                    ),
                }
                for path in receipts
            ],
            "target_aware_read_priority": ordered_priority,
            "target_aware_policy": (
                "Prefer approved target_file, declared additional_changes, "
                "integration files, branch current files, and recent failure files "
                "before unrelated algorithm files. Reading other allowlisted files "
                "remains allowed when the mechanism needs them."
            ),
        }
    )


def _code_phase_file_read_receipts(
    observations: list[ProposalObservation],
) -> list[str]:
    paths: list[str] = []
    for observation in observations:
        if observation.is_error or observation.tool_name not in {
            "context.read_algorithm_file",
            "context.read_surface",
        }:
            continue
        payload = observation.structured_payload
        if not isinstance(payload, Mapping):
            continue
        path = str(
            payload.get("file_path") or payload.get("target_file") or ""
        ).strip()
        if path and path not in paths:
            paths.append(path)
    return paths


def _integration_file_paths_from_code_context(
    code_context: Mapping[str, Any],
) -> list[str]:
    text = str(code_context.get("solver_design_branch_current_integration_files") or "")
    paths: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("### "):
            continue
        path = stripped[4:].strip().strip("`")
        if path and path.endswith(".py") and "/" in path and path not in paths:
            paths.append(path)
    return paths
