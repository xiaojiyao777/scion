"""CVRP-owned prepared prompt bridge metadata."""

from __future__ import annotations

from scion.postrun.handoff.prompt_context_readiness import ProblemPromptBridgeSpec


CVRP_PROBLEM_MEASUREMENT_DIAGNOSTICS_PROMPT_MARKERS = {
    "adapter_hook": (
        "scion/scion/problems/cvrp/adapter.py",
        "def render_problem_measurement_diagnostics",
    ),
    "context_payload": (
        "scion/scion/proposal/context_manager/manager.py",
        "problem_measurement_diagnostics",
    ),
    "profile_projection": (
        "scion/scion/proposal/engine/hypothesis_context_profiles.py",
        "mechanism_effect_ranking",
    ),
    "prompt_renderer": (
        "scion/scion/proposal/engine/hypothesis_prompts.py",
        "Problem Measurement Diagnostics",
    ),
}
CVRP_ACTIVE_SUBJECT_CODE_CONSTRAINT_MARKERS = {
    "provider_hook": (
        "scion/scion/problems/cvrp/solver_design_provider.py",
        "def active_subject_code_constraints",
    ),
    "large_twoopt_runtime_guard": (
        "scion/scion/problems/cvrp/solver_design_provider.py",
        "large_instance_two_opt_runtime_guard",
    ),
    "unbounded_twoopt_reject": (
        "scion/scion/problems/cvrp/solver_design_provider.py",
        "UNBOUNDED_TWO_OPT_DEFAULT_REJECT",
    ),
}
CVRP_PROMPT_BRIDGE_SPEC = ProblemPromptBridgeSpec(
    problem_family="cvrp",
    problem_v1_candidates=("scion/scion/problems/cvrp/problem-v1.yaml",),
    measurement_signal_name="cvrp_problem_measurement_diagnostics_prompt_bridge",
    measurement_failure_prefix="cvrp_problem_measurement_diagnostics_bridge",
    measurement_source_markers=CVRP_PROBLEM_MEASUREMENT_DIAGNOSTICS_PROMPT_MARKERS,
    measurement_bridge_scope="mechanism effect ranking",
    active_subject_signal_name="cvrp_active_subject_code_constraints_prompt_bridge",
    active_subject_failure_prefix="cvrp_active_subject_code_constraints_bridge",
    active_subject_surface="solver_design",
    active_subject_provider_markers=CVRP_ACTIVE_SUBJECT_CODE_CONSTRAINT_MARKERS,
)
