from __future__ import annotations

from scion.core.models import HypothesisProposal, PatchProposal
from scion.proposal.tools.previews.telemetry_static import (
    _mechanism_telemetry_static_preview,
)
from scion.tests.unit.test_agentic_proposal_tools_helpers import (
    _cvrp_context,
    _valid_hypothesis_payload,
    _valid_policy_patch_payload,
)


def _solver_design_hypothesis(
    mechanism_id: str = "tail_swap_probe",
    **overrides,
) -> HypothesisProposal:
    return HypothesisProposal(
        **_valid_hypothesis_payload(
            change_locus="solver_design",
            target_file="policies/baseline_modules/local_search.py",
            mechanism_changes=[
                {
                    "id": mechanism_id,
                    "change_type": "modify",
                }
            ],
            **overrides,
        )
    )


def _patch(code: str) -> PatchProposal:
    return PatchProposal(
        **_valid_policy_patch_payload(
            file_path="policies/baseline_modules/local_search.py",
            code_content=code,
        )
    )


def test_static_preview_expands_adapter_declared_mechanism_probes(tmp_path) -> None:
    preview = _mechanism_telemetry_static_preview(
        _cvrp_context(tmp_path),
        _solver_design_hypothesis(
            mechanism_id="vns_local_search",
            expected_telemetry={},
        ),
        _patch(
            "def apply(context):\n"
            "    context.record_move('vns_local_search', attempted=1, "
            "accepted=1, delta=1.0, best_improved=1)\n"
        ),
    )

    assert preview is not None
    assert preview["passed"] is False
    assert "DECLARED_MECHANISM_ACTIVATION_MISSING" in preview["issue_codes"]
    assert "solver_algorithm_context_records.vns_local_search_iterations" in (
        preview["checked_fields"]
    )
    assert "context.record_iteration('vns_local_search', positive_count)" in (
        preview["required_calls"]["vns_local_search"]
    )
    assert any("record_move alone" in issue for issue in preview["issues"])
    assert any(
        "do not unconditionally trigger" in hint.lower()
        for hint in preview["repair_hints"]
    )
    assert any(
        "guarantee-positive fallback" in hint.lower()
        for hint in preview["repair_hints"]
    )
    assert any("max(iterations, 1)" in hint for hint in preview["repair_hints"])
    assert any(
        "natural condition" in hint.lower()
        for hint in preview["repair_hints"]
    )


def test_static_preview_accepts_direct_iteration_activation(tmp_path) -> None:
    preview = _mechanism_telemetry_static_preview(
        _cvrp_context(tmp_path),
        _solver_design_hypothesis(expected_telemetry={}),
        _patch(
            "def apply(context):\n"
            "    context.record_iteration('tail_swap_probe', 1)\n"
            "    context.record_move('tail_swap_probe', attempted=1, "
            "accepted=1, delta=1.0, best_improved=1)\n"
        ),
    )

    assert preview is not None
    assert preview["passed"] is True
    assert preview.get("issues", []) == []


def test_static_preview_accepts_local_mechanism_alias(tmp_path) -> None:
    preview = _mechanism_telemetry_static_preview(
        _cvrp_context(tmp_path),
        _solver_design_hypothesis(expected_telemetry={}),
        _patch(
            "def apply(context, before, after):\n"
            "    mech_id = 'tail_swap_probe'\n"
            "    objective_delta = max(0.0, before - after)\n"
            "    context.record_iteration(mech_id, 1)\n"
            "    context.record_phase(mech_id, 2)\n"
            "    context.record_move(mech_id, attempted=1, accepted=1, "
            "delta=objective_delta, best_improved=objective_delta > 0)\n"
        ),
    )

    assert preview is not None
    assert preview["passed"] is True
    assert preview.get("issues", []) == []
    assert preview["helper_evidence"]["tail_swap_probe"]["record_iteration"] is True
    assert preview["helper_evidence"]["tail_swap_probe"]["record_phase"] is True
    assert preview["helper_evidence"]["tail_swap_probe"]["record_move"] is True


def test_static_preview_rejects_unknown_mechanism_alias(tmp_path) -> None:
    preview = _mechanism_telemetry_static_preview(
        _cvrp_context(tmp_path),
        _solver_design_hypothesis(expected_telemetry={}),
        _patch(
            "def apply(context, mech_id):\n"
            "    context.record_iteration(mech_id, 1)\n"
            "    context.record_move('tail_swap_probe', attempted=1, "
            "accepted=1, delta=1.0, best_improved=1)\n"
        ),
    )

    assert preview is not None
    assert preview["passed"] is False
    assert "DECLARED_MECHANISM_ACTIVATION_MISSING" in preview["issue_codes"]


def test_static_preview_rejects_dynamic_mechanism_alias(tmp_path) -> None:
    preview = _mechanism_telemetry_static_preview(
        _cvrp_context(tmp_path),
        _solver_design_hypothesis(expected_telemetry={}),
        _patch(
            "def apply(context, suffix):\n"
            "    mech_id = f'tail_{suffix}'\n"
            "    context.record_iteration(mech_id, 1)\n"
            "    context.record_move('tail_swap_probe', attempted=1, "
            "accepted=1, delta=1.0, best_improved=1)\n"
        ),
    )

    assert preview is not None
    assert preview["passed"] is False
    assert "DECLARED_MECHANISM_ACTIVATION_MISSING" in preview["issue_codes"]


def test_static_preview_accepts_direct_phase_activation(tmp_path) -> None:
    preview = _mechanism_telemetry_static_preview(
        _cvrp_context(tmp_path),
        _solver_design_hypothesis(expected_telemetry={}),
        _patch(
            "def apply(context):\n"
            "    context.record_phase('tail_swap_probe', 3)\n"
            "    context.record_move('tail_swap_probe', attempted=1, "
            "accepted=1, delta=1.0, best_improved=1)\n"
        ),
    )

    assert preview is not None
    assert preview["passed"] is True
    assert preview.get("issues", []) == []


def test_static_preview_allows_cache_mechanism_without_direct_effect(
    tmp_path,
) -> None:
    preview = _mechanism_telemetry_static_preview(
        _cvrp_context(tmp_path),
        _solver_design_hypothesis(
            mechanism_id="neighbor_list_cache",
            expected_telemetry={
                "activation": [
                    "solver_algorithm_context_records.neighbor_list_cache_iterations",
                ],
                "budget": [
                    "solver_algorithm_phase_runtime_ms.neighbor_list_cache",
                ],
            },
        ),
        _patch(
            "def apply(context):\n"
            "    context.record_iteration('neighbor_list_cache', 1)\n"
            "    context.record_phase('neighbor_list_cache', 2)\n"
        ),
    )

    assert preview is not None
    assert preview["passed"] is True
    assert preview.get("issues", []) == []
    assert "neighbor_list_cache" not in preview.get("required_calls", {})


def test_static_preview_rejects_literal_zero_phase_runtime(tmp_path) -> None:
    preview = _mechanism_telemetry_static_preview(
        _cvrp_context(tmp_path),
        _solver_design_hypothesis(expected_telemetry={}),
        _patch(
            "def apply(context):\n"
            "    context.record_iteration('tail_swap_probe', 1)\n"
            "    context.record_phase('tail_swap_probe', 0.0)\n"
            "    context.record_move('tail_swap_probe', attempted=1, "
            "accepted=1, delta=1.0, best_improved=1)\n"
        ),
    )

    assert preview is not None
    assert preview["passed"] is False
    assert "DECLARED_MECHANISM_PHASE_RUNTIME_ZERO" in preview["issue_codes"]
    assert any("literal zero/non-positive" in issue for issue in preview["issues"])


def test_static_preview_rejects_unknown_context_helper_keywords(tmp_path) -> None:
    preview = _mechanism_telemetry_static_preview(
        _cvrp_context(tmp_path),
        _solver_design_hypothesis(expected_telemetry={}),
        _patch(
            "def apply(context):\n"
            "    context.record_phase('tail_swap_probe', 1, extra={'x': 1})\n"
            "    context.record_iteration('tail_swap_probe', 1)\n"
            "    context.record_move('tail_swap_probe', attempted=1, "
            "accepted=1, delta=1.0, best_improved=1)\n"
        ),
    )

    assert preview is not None
    assert preview["passed"] is False
    assert any("does not accept keyword(s): extra" in issue for issue in preview["issues"])


def test_static_preview_rejects_best_delta_record_move_with_none_delta(tmp_path) -> None:
    preview = _mechanism_telemetry_static_preview(
        _cvrp_context(tmp_path),
        _solver_design_hypothesis(
            expected_telemetry={
                "effect": ["solver_algorithm_phase_best_delta.tail_swap_probe"],
            },
        ),
        _patch(
            "def apply(context):\n"
            "    context.record_iteration('tail_swap_probe', 1)\n"
            "    context.record_phase('tail_swap_probe', 2)\n"
            "    context.record_move('tail_swap_probe', attempted=1, "
            "accepted=1, delta=None, best_improved=1)\n"
        ),
    )

    assert preview is not None
    assert preview["passed"] is False
    assert "DECLARED_MECHANISM_DELTA_EVIDENCE_MISSING" in preview["issue_codes"]
    rendered = " ".join(preview["issues"])
    assert "best_delta" in rendered
    assert "delta=None" in rendered
    action = preview["actionable_telemetry_feedback"][0]
    assert action["failure_code"] == "DECLARED_MECHANISM_DELTA_EVIDENCE_MISSING"
    assert action["failure_mechanism_id"] == "tail_swap_probe"
    assert action["expected_call_pattern"] == (
        "context.record_move('tail_swap_probe', attempted=1, accepted=1, "
        "delta=<positive_improvement_delta>, best_improved=True)"
    )
    invalid_call = action["invalid_call_summaries"][0]
    assert "delta=None" in invalid_call["call"]
    assert invalid_call["delta_status"] == "none"
    assert "expected_telemetry" in action["declaration_alternative"]
    assert preview["helper_evidence"]["tail_swap_probe"][
        "record_move_delta_none_literal"
    ] is True


def test_static_preview_allows_best_delta_record_move_with_delta_variable(
    tmp_path,
) -> None:
    preview = _mechanism_telemetry_static_preview(
        _cvrp_context(tmp_path),
        _solver_design_hypothesis(
            expected_telemetry={
                "effect": ["solver_algorithm_phase_best_delta.tail_swap_probe"],
            },
        ),
        _patch(
            "def apply(context, before, after):\n"
            "    objective_delta = max(0.0, before - after)\n"
            "    context.record_iteration('tail_swap_probe', 1)\n"
            "    context.record_phase('tail_swap_probe', 2)\n"
            "    context.record_move('tail_swap_probe', attempted=1, "
            "accepted=1, delta=objective_delta, "
            "best_improved=objective_delta > 0)\n"
        ),
    )

    assert preview is not None
    assert preview["passed"] is True
    assert preview.get("issues", []) == []
    assert preview["helper_evidence"]["tail_swap_probe"][
        "record_move_delta_evidence"
    ] is True
