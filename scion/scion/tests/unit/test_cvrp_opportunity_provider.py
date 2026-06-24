from __future__ import annotations

import json
from pathlib import Path

from scion.problem.bridge import load_problem_spec_v1_from_yaml
from scion.problems.cvrp.adapter import CvrpAdapter
from scion.problems.cvrp.opportunity import CvrpOpportunityProvider


_CVRP_PROBLEM = (
    Path(__file__).resolve().parents[2] / "problems" / "cvrp" / "problem-v1.yaml"
)


def test_cvrp_opportunity_provider_builds_proposal_only_summary() -> None:
    spec = load_problem_spec_v1_from_yaml(_CVRP_PROBLEM)
    adapter = CvrpAdapter(spec)

    payload = (
        CvrpOpportunityProvider(problem_spec=spec, adapter=adapter)
        .build_opportunity_summary()
        .to_payload()
    )

    assert payload["schema_version"] == "scion.problem_opportunity_summary.v1"
    assert payload["problem_family"] == "cvrp"
    assert payload["objective"] == "total_distance"
    assert payload["proposal_visibility_only"] is True
    assert payload["decision_features_excluded"] is True
    assert payload["measurement"]["runtime_model"] == "budget_exhausting"
    assert payload["measurement"]["effect_metric"] == "total_distance"
    assert payload["measurement"]["decision_features_excluded"] is True
    assert "calibration_ref" not in json.dumps(payload, sort_keys=True)
    assert "pair_evidence" not in json.dumps(payload, sort_keys=True)
    assert "bks" not in json.dumps(payload, sort_keys=True).lower()


def test_cvrp_opportunity_provider_preserves_problem_owned_signals() -> None:
    spec = load_problem_spec_v1_from_yaml(_CVRP_PROBLEM)
    adapter = CvrpAdapter(spec)

    payload = (
        CvrpOpportunityProvider(problem_spec=spec, adapter=adapter)
        .build_opportunity_summary()
        .to_payload()
    )

    mechanism_families = {
        item["mechanism_family"] for item in payload["mechanism_evidence"]
    }
    protected_cases = {item["case_id"] for item in payload["protected_cases"]}
    default_avoid = {
        item["mechanism_family"] for item in payload["default_avoid"]
    }
    reason_codes = {
        code
        for item in payload["mechanism_evidence"]
        for code in item.get("reason_codes", [])
    }

    assert "large_instance_intra_route_two_opt_seed" in mechanism_families
    assert {"CMT2", "CMT4"} <= protected_cases
    assert "broad_vns_removal" in default_avoid
    assert "CVRP_LARGE_INSTANCE_TWO_OPT_SEED" in reason_codes
