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


def _solver_design_hypothesis(**overrides) -> HypothesisProposal:
    return HypothesisProposal(
        **_valid_hypothesis_payload(
            change_locus="solver_design",
            target_file="policies/baseline_modules/local_search.py",
            mechanism_changes=[
                {
                    "id": "tail_swap_probe",
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
        _solver_design_hypothesis(expected_telemetry={}),
        _patch(
            "def apply(context):\n"
            "    context.record_move('tail_swap_probe', attempted=1, "
            "accepted=1, delta=-1.0, best_improved=1)\n"
        ),
    )

    assert preview is not None
    assert preview["passed"] is False
    assert "solver_algorithm_context_records.tail_swap_probe_iterations" in (
        preview["checked_fields"]
    )
    assert "context.record_iteration('tail_swap_probe', positive_count)" in (
        preview["required_calls"]["tail_swap_probe"]
    )
    assert any("record_iteration('tail_swap_probe'" in issue for issue in preview["issues"])


def test_static_preview_accepts_complete_mechanism_records(tmp_path) -> None:
    preview = _mechanism_telemetry_static_preview(
        _cvrp_context(tmp_path),
        _solver_design_hypothesis(expected_telemetry={}),
        _patch(
            "def apply(context):\n"
            "    context.record_phase('tail_swap_probe', 1)\n"
            "    context.record_iteration('tail_swap_probe', 1)\n"
            "    context.record_move('tail_swap_probe', attempted=1, "
            "accepted=1, delta=-1.0, best_improved=1)\n"
        ),
    )

    assert preview is not None
    assert preview["passed"] is True
    assert preview.get("issues", []) == []


def test_static_preview_rejects_unknown_context_helper_keywords(tmp_path) -> None:
    preview = _mechanism_telemetry_static_preview(
        _cvrp_context(tmp_path),
        _solver_design_hypothesis(expected_telemetry={}),
        _patch(
            "def apply(context):\n"
            "    context.record_phase('tail_swap_probe', 1, extra={'x': 1})\n"
            "    context.record_iteration('tail_swap_probe', 1)\n"
            "    context.record_move('tail_swap_probe', attempted=1, "
            "accepted=1, delta=-1.0, best_improved=1)\n"
        ),
    )

    assert preview is not None
    assert preview["passed"] is False
    assert any("does not accept keyword(s): extra" in issue for issue in preview["issues"])
