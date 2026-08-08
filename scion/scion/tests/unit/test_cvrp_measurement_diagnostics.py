from __future__ import annotations

import json
from pathlib import Path

from scion.problem.bridge import (
    legacy_problem_spec_from_v1,
    load_problem_spec_v1_from_yaml,
)
from scion.problems.cvrp.adapter import CvrpAdapter
from scion.proposal.context_manager.manager import _problem_measurement_diagnostics


_CVRP_PROBLEM = (
    Path(__file__).resolve().parents[2] / "problems" / "cvrp" / "problem-v1.yaml"
)


def _adapter() -> tuple[object, CvrpAdapter]:
    spec = load_problem_spec_v1_from_yaml(_CVRP_PROBLEM)
    return spec, CvrpAdapter(spec)


def test_cvrp_adapter_renders_current_measurement_and_attribution() -> None:
    _spec, adapter = _adapter()
    payload = adapter.render_problem_measurement_diagnostics()

    assert payload["schema_version"] == "scion.cvrp_measurement_guidance.v3"
    assert payload["proposal_visibility_only"] is True
    assert payload["decision_features_excluded"] is True
    assert payload["measurement_context"]["metric"] == "total_distance"
    assert payload["measurement_context"]["objective"] == "minimize"
    assert payload["feasibility"]["required"] is True
    assert "route count" in payload["feasibility"]["observations"]
    assert payload["typed_attribution"]["observations"] == [
        "attempted change",
        "accepted route-state transition",
        "direct objective change when observable",
        "downstream search effect",
        "final total_distance",
    ]


def test_cvrp_adapter_guidance_contains_no_historical_target_noise() -> None:
    _spec, adapter = _adapter()
    rendered = json.dumps(
        adapter.render_problem_measurement_diagnostics(),
        sort_keys=True,
    ).lower()

    for forbidden in (
        "successor",
        "cmt2",
        "cmt4",
        "nearest reviewed",
        "default_avoid",
        "denylist",
        "target_file",
        "next_required_direction",
        "recommended_min_seeds",
        "mechanism_effect_ranking",
        "top_opportunity_recipe",
    ):
        assert forbidden not in rendered


def test_context_manager_projects_complete_current_cvrp_guidance() -> None:
    spec, adapter = _adapter()
    legacy = legacy_problem_spec_from_v1(spec)

    projected = _problem_measurement_diagnostics(legacy, adapter=adapter)
    problem_owned = projected["problem_owned_diagnostics"]

    assert problem_owned["schema_version"] == "scion.cvrp_measurement_guidance.v3"
    assert problem_owned["measurement_context"]["metric"] == "total_distance"
    assert problem_owned["feasibility"]["required"] is True
    assert problem_owned["typed_attribution"]["observations"] == [
        "attempted change",
        "accepted route-state transition",
        "direct objective change when observable",
        "downstream search effect",
        "final total_distance",
    ]


def test_adapter_projection_redacts_raw_or_hidden_measurement_rows() -> None:
    class _Spec:
        measurement = None

    class _Adapter:
        def render_problem_measurement_diagnostics(self) -> dict[str, object]:
            return {
                "schema_version": "test.measurement.v1",
                "proposal_visibility_only": True,
                "decision_features_excluded": True,
                "proposal_visible_fields": [
                    "safe_note",
                    "operator_telemetry",
                    "raw_pair_rows",
                    "validation_case_details",
                    "frozen_case_details",
                    "holdout_rows",
                    "bks_gap_details",
                    "llm_text",
                ],
                "safe_note": "keep",
                "operator_telemetry": {
                    "mechanism_activation": "keep structured diagnostic"
                },
                "unlisted_note": "must stay hidden",
                "raw_pair_rows": [{"case": "hidden"}],
                "pair_evidence": [{"case": "hidden"}],
                "validation_case_details": "hidden",
                "frozen_case_details": "hidden",
                "holdout_rows": "hidden",
                "bks_gap_details": "hidden",
                "llm_text": "hidden",
            }

    payload = _problem_measurement_diagnostics(
        _Spec(), adapter=_Adapter()  # type: ignore[arg-type]
    )
    rendered = json.dumps(payload, sort_keys=True)

    assert "keep" in rendered
    assert "operator_telemetry" in rendered
    assert "mechanism_activation" in rendered
    assert "keep structured diagnostic" in rendered
    assert "unlisted_note" not in rendered
    assert "must stay hidden" not in rendered
    for forbidden in (
        "raw_pair_rows",
        "pair_evidence",
        "validation_case_details",
        "frozen_case_details",
        "holdout_rows",
        "bks_gap_details",
        "llm_text",
        "hidden",
    ):
        assert forbidden not in rendered
