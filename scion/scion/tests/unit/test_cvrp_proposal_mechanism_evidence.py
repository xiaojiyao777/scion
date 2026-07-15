from __future__ import annotations

from scion.problems.cvrp.proposal_mechanism_evidence import (
    CvrpProposalMechanismEvidenceProvider,
)


def _event(
    repair: str,
    *,
    accepted: bool = False,
    best: bool = False,
    reason: str = "rejected",
    before: object = 10,
    after: object = 20,
) -> dict[str, object]:
    return {
        "repair_operator": repair,
        "accepted": accepted,
        "best_improved": best,
        "acceptance_reason": reason,
        "elapsed_ms_before": before,
        "elapsed_ms_after": after,
    }


def test_cvrp_proposal_evidence_aggregates_every_repair_without_truncation() -> None:
    repairs = [f"repair_{index:02d}" for index in range(12)]
    candidate_trace = [_event(name) for name in repairs]
    candidate_trace.extend(
        [
            _event("pair", accepted=True, best=True, reason="route_limit", before=5, after=15),
            _event("pair", accepted=True, reason="repair_error", before=20, after=50),
            _event("pair", before=50, after=40),
            {"repair_operator": "pair", "elapsed_ms_before": "bad"},
        ]
    )
    champion_trace = [
        _event("greedy", reason="route_limit"),
        _event("greedy", reason="route_limit"),
    ]
    provider = CvrpProposalMechanismEvidenceProvider()

    payload = provider.summarize_proposal_mechanism_evidence(
        stage="screening",
        selected_surface="solver_design",
        runtime_pairs=[
            {
                "candidate_runtime": {
                    "solver_algorithm_alns_iteration_trace": candidate_trace
                },
                "champion_runtime": {
                    "solver_algorithm_alns_iteration_trace": champion_trace
                },
                "champion_result_source": "cached",
            }
        ],
    )

    assert set(payload["candidate"]["repairs"]) == {*repairs, "pair"}
    pair = payload["candidate"]["repairs"]["pair"]
    assert pair["attempts"] == 4
    assert pair["accepted"] == 2
    assert pair["best_updates"] == 1
    assert pair["route_limit"] == 1
    assert pair["repair_error"] == 1
    assert pair["elapsed_ms"] == {"observed": 2, "total": 40, "mean": 20.0}
    assert payload["candidate"]["route_limit"] == 1
    assert payload["candidate"]["repair_error"] == 1
    assert payload["comparison"]["route_limit"]["candidate_minus_champion"] == -1
    assert payload["comparison"]["repair_error"]["candidate_minus_champion"] == 1
    assert payload["trace_coverage"]["champion_result_sources"] == {"cached": 1}


def test_cvrp_proposal_evidence_ignores_non_screening_and_missing_trace() -> None:
    provider = CvrpProposalMechanismEvidenceProvider()
    assert provider.summarize_proposal_mechanism_evidence(
        stage="validation",
        selected_surface="solver_design",
        runtime_pairs=[],
    ) == {}
    assert provider.summarize_proposal_mechanism_evidence(
        stage="screening",
        selected_surface="solver_design",
        runtime_pairs=[{"candidate_runtime": {"unrelated": []}}],
    ) == {}
