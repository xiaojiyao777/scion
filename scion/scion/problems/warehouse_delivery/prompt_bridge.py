"""Warehouse-owned prepared prompt bridge metadata."""

from __future__ import annotations

from scion.postrun.handoff.prompt_context_readiness import ProblemPromptBridgeSpec


WAREHOUSE_PROBLEM_MEASUREMENT_DIAGNOSTICS_PROMPT_MARKERS = {
    "adapter_hook": (
        "scion/scion/problems/warehouse_delivery/adapter.py",
        "def render_problem_measurement_diagnostics",
    ),
    "context_payload": (
        "scion/scion/proposal/context_manager/manager.py",
        "problem_measurement_diagnostics",
    ),
    "profile_projection": (
        "scion/scion/proposal/engine/hypothesis_context_profiles.py",
        "adapter_diagnostics",
    ),
    "prompt_renderer": (
        "scion/scion/proposal/engine/hypothesis_prompts.py",
        "Problem Measurement Diagnostics",
    ),
}
WAREHOUSE_ACTIVE_SUBJECT_CODE_CONSTRAINT_MARKERS = {
    "provider_hook": (
        "scion/scion/problems/warehouse_delivery/adapter.py",
        "def active_subject_code_constraints",
    ),
    "diagnostics_contract": (
        "scion/scion/problems/warehouse_delivery/adapter.py",
        "self.validation_transfer_diagnostics",
    ),
    "bounded_scan_guard": (
        "scion/scion/problems/warehouse_delivery/adapter.py",
        "unbounded full vehicle-pair scans",
    ),
    "lexicographic_guard": (
        "scion/scion/problems/warehouse_delivery/adapter.py",
        "lexicographic",
    ),
}
WAREHOUSE_PROMPT_BRIDGE_SPEC = ProblemPromptBridgeSpec(
    problem_family="warehouse_delivery",
    problem_v1_candidates=(
        "scion/problems/warehouse_delivery/problem-v1.yaml",
        "scion/scion/problems/warehouse_delivery/problem-v1.yaml",
    ),
    measurement_signal_name="warehouse_problem_measurement_diagnostics_prompt_bridge",
    measurement_failure_prefix="warehouse_problem_measurement_diagnostics_bridge",
    measurement_source_markers=WAREHOUSE_PROBLEM_MEASUREMENT_DIAGNOSTICS_PROMPT_MARKERS,
    measurement_bridge_scope="validation-transfer follow-up diagnostics",
    active_subject_signal_name=(
        "warehouse_active_subject_code_constraints_prompt_bridge"
    ),
    active_subject_failure_prefix="warehouse_active_subject_code_constraints_bridge",
    active_subject_surface="order_level",
    active_subject_provider_markers=WAREHOUSE_ACTIVE_SUBJECT_CODE_CONSTRAINT_MARKERS,
)
