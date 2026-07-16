from __future__ import annotations

import json
from types import SimpleNamespace

from scion.core.screening_visibility import mechanism_evidence_for_protocol
from scion.problems.cvrp.evidence import search_allocation
from scion.problems.cvrp.models import CvrpInstance, CvrpNode
from scion.problems.cvrp.proposal_mechanism_evidence import (
    CvrpProposalMechanismEvidenceProvider,
)
from scion.protocol.experiment.proposal_evidence import (
    problem_proposal_mechanism_evidence,
)


def _event(
    repair: str,
    *,
    destroy: str = "shaw",
    accepted: bool = False,
    best: bool = False,
    reason: str = "rejected",
    before: object = 10,
    after: object = 20,
    repair_distance: object | None = None,
    polish_distance: object | None = None,
    iteration: object = 1,
) -> dict[str, object]:
    event: dict[str, object] = {
        "iteration": iteration,
        "destroy_operator": destroy,
        "repair_operator": repair,
        "accepted": accepted,
        "best_improved": best,
        "acceptance_reason": reason,
        "elapsed_ms_before": before,
        "elapsed_ms_after": after,
    }
    if repair_distance is not None:
        event["candidate_after_repair_distance"] = repair_distance
    if polish_distance is not None:
        event["candidate_after_polish_distance"] = polish_distance
    return event


def _runtime(
    *,
    elapsed: int,
    phase_runtime: dict[str, int],
    trace: list[object],
    attempted: dict[str, int] | None = None,
    accepted: dict[str, int] | None = None,
    improvements: dict[str, int] | None = None,
    delta_sum: dict[str, float] | None = None,
    best_delta: dict[str, float] | None = None,
) -> dict[str, object]:
    return {
        "solver_algorithm_elapsed_ms": elapsed,
        "solver_algorithm_phase_runtime_ms": phase_runtime,
        "solver_algorithm_alns_iteration_trace": trace,
        "solver_algorithm_phase_move_attempts": attempted or {},
        "solver_algorithm_phase_accepted_moves": accepted or {},
        "solver_algorithm_phase_improvement_counts": improvements or {},
        "solver_algorithm_phase_delta_sum": delta_sum or {},
        "solver_algorithm_phase_best_delta": best_delta or {},
    }


def test_search_allocation_aggregates_runtime_lifecycle_and_paired_math() -> None:
    repairs = [f"repair_{index:02d}" for index in range(12)]
    candidate_trace: list[object] = [
        _event(name, repair_distance=100, polish_distance=100)
        for name in repairs
    ]
    candidate_trace.extend(
        [
            _event(
                "regret3",
                accepted=True,
                best=True,
                reason="new_best",
                before=5,
                after=15,
                repair_distance=120,
                polish_distance=100,
            ),
            _event(
                "regret3",
                destroy="route",
                reason="destroy_empty",
                before=20,
                after=50,
            ),
            _event("greedy", destroy="random", reason="repair_error"),
        ]
    )
    champion_trace: list[object] = [
        _event(
            "greedy",
            reason="route_limit",
            repair_distance=100,
            polish_distance=100,
        )
    ]
    provider = CvrpProposalMechanismEvidenceProvider()

    payload = provider.summarize_proposal_mechanism_evidence(
        stage="screening",
        selected_surface="solver_design",
        runtime_pairs=[
            {
                "candidate_runtime": _runtime(
                    elapsed=100,
                    phase_runtime={"alns_core": 30, "vns_embedded": 60},
                    trace=candidate_trace,
                    attempted={"alns": 16, "vns_embedded": 12},
                    accepted={"alns": 1, "vns_embedded": 8},
                    improvements={"vns_embedded": 7},
                    delta_sum={"vns_embedded": 20.5},
                    best_delta={"vns_embedded": 8.0},
                ),
                "champion_runtime": _runtime(
                    elapsed=80,
                    phase_runtime={"alns_core": 30, "vns_embedded": 40},
                    trace=champion_trace,
                    attempted={"alns": 1, "vns_embedded": 10},
                    accepted={"vns_embedded": 6},
                    improvements={"vns_embedded": 4},
                    delta_sum={"vns_embedded": 10.0},
                    best_delta={"vns_embedded": 5.0},
                ),
                "champion_result_source": "cached",
            }
        ],
    )

    assert payload["schema_version"] == "scion.cvrp.search_allocation_evidence.v1"
    assert payload["gate_influence"] is False
    assert payload["candidate"]["solver_algorithm_elapsed_ms"] == 100
    assert payload["candidate"]["phase_runtime_share"] == {
        "alns_core": 0.3,
        "vns_embedded": 0.6,
    }
    assert payload["candidate"]["runtime_residual_ms"] == 10
    assert payload["comparison"]["runtime_residual_ms"] == {
        "candidate": 10,
        "champion": 10,
        "candidate_minus_champion": 0,
        "observed_pairs": 1,
    }
    assert set(payload["candidate"]["repair_operators"]) >= {
        *repairs,
        "regret3",
        "greedy",
    }
    route = payload["candidate"]["destroy_operators"]["route"]
    assert (route["selected"], route["nonempty"], route["empty"]) == (1, 0, 1)
    repair = payload["candidate"]["repair_operators"]["regret3"]
    assert (repair["selected"], repair["invoked"], repair["completed"]) == (2, 1, 1)
    assert repair["accepted"] == repair["best_updates"] == 1
    pair = payload["candidate"]["destroy_repair_pairs"]["route__regret3"]
    assert (pair["selected"], pair["nonempty"], pair["invoked"]) == (1, 0, 0)
    assert pair["selected_iteration_elapsed_ms"] == {
        "observed": 1,
        "total": 30,
        "mean": 30.0,
    }
    assert payload["candidate"]["post_repair_polish"] == {
        "observed": 13,
        "improved": 1,
        "unchanged": 12,
        "worsened": 0,
        "delta_sum": 20.0,
    }
    move = payload["candidate"]["move_phases"]["vns_embedded"]
    assert move == {
        "attempted": 12,
        "accepted": 8,
        "improvement_count": 7,
        "delta_sum": 20.5,
        "best_delta": 8.0,
        "coverage": {
            "attempted": 1,
            "accepted": 1,
            "improvement_count": 1,
            "delta_sum": 1,
            "best_delta": 1,
        },
    }
    assert payload["comparison"]["move_phases"]["vns_embedded"]["attempted"] == {
        "candidate": 12,
        "champion": 10,
        "candidate_minus_champion": 2,
        "observed_pairs": 1,
    }
    assert payload["coverage"]["candidate"]["malformed_trace_events"] == 0
    assert (
        payload["coverage"]["runtime_accounting"][
            "move_phase_counters_are_additive_phase_runtime"
        ]
        is False
    )


def test_search_allocation_missing_and_malformed_are_unavailable_not_zero() -> None:
    provider = CvrpProposalMechanismEvidenceProvider()
    payload = provider.summarize_proposal_mechanism_evidence(
        stage="screening",
        selected_surface="solver_design",
        runtime_pairs=[
            {
                "candidate_runtime": {
                    "solver_algorithm_elapsed_ms": "100",
                    "solver_algorithm_phase_runtime_ms": {
                        "valid_phase": 8,
                        "bad_phase": "9",
                    },
                    "solver_algorithm_alns_iteration_trace": "not-a-list",
                    "solver_algorithm_phase_move_attempts": {
                        "valid_phase": 2,
                        "bad_phase": "3",
                    },
                }
            }
        ],
    )

    assert payload["candidate"]["solver_algorithm_elapsed_ms"] is None
    assert payload["candidate"]["runtime_residual_ms"] is None
    assert payload["candidate"]["phase_runtime_ms"] == {"valid_phase": 8}
    assert payload["candidate"]["phase_runtime_share"] == {}
    assert payload["candidate"]["alns"]["iterations"] is None
    assert payload["candidate"]["move_phases"]["valid_phase"]["attempted"] == 2
    assert "bad_phase" not in payload["candidate"]["move_phases"]
    assert payload["coverage"]["candidate"]["trace_pairs"] == 0
    assert payload["coverage"]["candidate"]["phase_accounting_pairs"] == 0
    assert payload["coverage"]["missing_semantics"] == "unavailable_not_zero"


def test_r11c_acceptance_fixture_and_instance_feasibility(monkeypatch) -> None:
    candidate_trace = [
        _event("regret3_existing", destroy="route", reason="destroy_empty")
        for _ in range(511)
    ] + [
        _event(
            "regret3",
            destroy="shaw",
            repair_distance=100,
            polish_distance=99,
        )
        for _ in range(1789)
    ]
    champion_trace = [
        _event(
            "regret3",
            destroy="shaw",
            repair_distance=100,
            polish_distance=99,
        )
        for _ in range(1589)
    ]
    instances = {
        f"/private/case-{index}.vrp": _instance(reference_routes=3 if index == 7 else 2)
        for index in range(8)
    }
    monkeypatch.setattr(
        search_allocation,
        "load_cvrplib_instance",
        lambda path: instances[str(path)],
    )
    runtime_pairs = []
    for index, path in enumerate(instances):
        runtime_pairs.append(
            {
                "case_path": path,
                "case": f"secret-case-{index}",
                "seed": index,
                "candidate_runtime": (
                    _runtime(
                        elapsed=800_000,
                        phase_runtime={"vns_embedded": 662_010},
                        trace=candidate_trace,
                        attempted={"vns": 36_185},
                    )
                    if index == 0
                    else {}
                ),
                "champion_runtime": (
                    _runtime(
                        elapsed=810_000,
                        phase_runtime={"vns_embedded": 701_990},
                        trace=champion_trace,
                        attempted={"vns": 36_448},
                    )
                    if index == 0
                    else {}
                ),
            }
        )

    payload = CvrpProposalMechanismEvidenceProvider().summarize_proposal_mechanism_evidence(
        stage="screening",
        selected_surface="solver_design",
        runtime_pairs=runtime_pairs,
    )

    assert payload["candidate"]["alns"]["iterations"] == 2300
    assert payload["champion"]["alns"]["iterations"] == 1589
    destroy = payload["candidate"]["destroy_operators"]["route"]
    assert (destroy["selected"], destroy["nonempty"], destroy["empty"]) == (511, 0, 511)
    repair = payload["candidate"]["repair_operators"]["regret3_existing"]
    assert (repair["selected"], repair["invoked"], repair["completed"]) == (511, 0, 0)
    pair = payload["candidate"]["destroy_repair_pairs"]["route__regret3_existing"]
    assert (pair["selected"], pair["invoked"]) == (511, 0)
    assert payload["candidate"]["post_repair_polish"]["observed"] == 1789
    assert payload["champion"]["post_repair_polish"]["observed"] == 1589
    assert payload["candidate"]["phase_runtime_ms"]["vns_embedded"] == 662_010
    assert payload["champion"]["phase_runtime_ms"]["vns_embedded"] == 701_990
    assert payload["candidate"]["move_phases"]["vns"]["attempted"] == 36_185
    assert payload["champion"]["move_phases"]["vns"]["attempted"] == 36_448
    feasibility = payload["instance_feasibility"]
    assert feasibility["coverage"]["observed_cases"] == 8
    assert feasibility["summary"]["min_route_slack"]["min"] == 0
    assert feasibility["summary"]["min_route_slack"]["max"] == 1
    assert feasibility["one_route_reduction"]["capacity_feasible_cases"] == 1
    assert feasibility["one_route_reduction"]["capacity_infeasible_cases"] == 7
    rendered = json.dumps(payload, sort_keys=True)
    assert "/private/" not in rendered
    assert "secret-case" not in rendered
    assert '"seed"' not in rendered


def test_instance_feasibility_prefers_allowed_routes_and_hides_failures(
    monkeypatch,
) -> None:
    instances = {
        "/secret/allowed.vrp": _instance(reference_routes=4, allowed_routes=3),
        "/secret/bks.vrp": _instance(reference_routes=2),
    }

    def load(path: str):
        if path == "/secret/broken.vrp":
            raise ValueError("private load error /secret/broken.vrp")
        return instances[path]

    monkeypatch.setattr(search_allocation, "load_cvrplib_instance", load)
    payload = search_allocation.build_search_allocation_evidence(
        [
            {"case_path": path, "candidate_runtime": {_ELAPSED_FOR_TEST: 1}}
            for path in (*instances, "/secret/broken.vrp")
        ]
    )
    feasibility = payload["instance_feasibility"]
    assert feasibility["coverage"] == {
        "requested_cases": 3,
        "observed_cases": 2,
        "unavailable_cases": 1,
        "reference_route_cases": 2,
        "reference_route_source_counts": {"allowed_routes": 1, "bks_routes": 1},
    }
    assert feasibility["summary"]["reference_route_count"] == {
        "min": 2,
        "median": 2.5,
        "max": 3,
    }
    rendered = json.dumps(payload, sort_keys=True)
    assert "/secret/" not in rendered
    assert "private load error" not in rendered


def test_trace_absence_empty_and_field_missing_remain_distinct() -> None:
    payload = search_allocation.build_search_allocation_evidence(
        [
            {
                "candidate_runtime": {"solver_algorithm_elapsed_ms": 10},
                "champion_runtime": {
                    "solver_algorithm_elapsed_ms": 10,
                    "solver_algorithm_alns_iteration_trace": [],
                },
            }
        ]
    )

    assert payload["candidate"]["alns"]["iterations"] is None
    assert payload["candidate"]["post_repair_polish"]["observed"] is None
    assert payload["candidate"]["destroy_operators"] == {}
    assert payload["champion"]["alns"] == {
        "iterations": 0,
        "iterations_per_second": 0.0,
        "accepted": 0,
        "best_updates": 0,
        "route_limit": 0,
        "repair_error": 0,
    }
    assert payload["champion"]["post_repair_polish"]["observed"] == 0
    assert payload["comparison"]["alns"]["iterations"]["observed_pairs"] == 0


def test_valid_trace_rows_with_missing_fields_never_render_as_zero() -> None:
    incomplete = {
        "iteration": 1,
        "destroy_operator": "shaw",
        "repair_operator": "regret3",
        "private_ref": "raw-secret",
    }
    complete = _event(
        "regret3",
        repair_distance=100,
        polish_distance=90,
    )
    payload = search_allocation.build_search_allocation_evidence(
        [
            {
                "candidate_runtime": {
                    "solver_algorithm_alns_iteration_trace": [incomplete]
                },
                "champion_runtime": {
                    "solver_algorithm_alns_iteration_trace": [complete]
                },
            }
        ]
    )

    candidate = payload["candidate"]
    assert candidate["alns"]["iterations"] == 1
    for field_name in ("accepted", "best_updates", "route_limit", "repair_error"):
        assert candidate["alns"][field_name] is None
        assert payload["comparison"]["alns"][field_name] == {
            "candidate": None,
            "champion": None,
            "candidate_minus_champion": None,
            "observed_pairs": 0,
        }
    assert candidate["post_repair_polish"] == {
        "observed": None,
        "improved": None,
        "unchanged": None,
        "worsened": None,
        "delta_sum": None,
    }
    repair = candidate["repair_operators"]["regret3"]
    assert repair["selected"] == 1
    assert repair["invoked"] is None
    assert repair["accepted"] is None
    assert repair["selected_iteration_elapsed_ms"] == {
        "observed": 0,
        "total": None,
        "mean": None,
    }
    coverage = payload["coverage"]["candidate"]
    assert coverage["destroy_operator_events"] == 1
    assert coverage["repair_operator_events"] == 1
    assert coverage["pair_operator_events"] == 1
    assert coverage["acceptance_reason_events"] == 0
    assert coverage["accepted_events"] == 0
    assert coverage["best_improved_events"] == 0
    assert "raw-secret" not in json.dumps(payload, sort_keys=True)


def test_invalid_iteration_and_unknown_reason_reduce_trace_coverage() -> None:
    trace = [
        _event("regret3", iteration=0),
        _event("regret3", iteration=True),
        {"repair_operator": "regret3"},
        _event("regret3", reason="provider_invented_reason", iteration=2),
    ]
    payload = search_allocation.build_search_allocation_evidence(
        [{"candidate_runtime": {"solver_algorithm_alns_iteration_trace": trace}}]
    )

    assert payload["candidate"]["alns"]["iterations"] == 1
    assert payload["candidate"]["alns"]["route_limit"] is None
    coverage = payload["coverage"]["candidate"]
    assert coverage["malformed_trace_events"] == 3
    assert coverage["trace_events"] == 1
    assert coverage["acceptance_reason_events"] == 0
    assert coverage["trace_field_complete_pairs"]["iteration"] == 0
    assert coverage["trace_field_complete_pairs"]["acceptance_reason"] == 0


def test_polish_comparison_uses_field_level_paired_intersection() -> None:
    payload = search_allocation.build_search_allocation_evidence(
        [
            {
                "candidate_runtime": {
                    "solver_algorithm_alns_iteration_trace": [
                        _event("regret3", repair_distance=100, polish_distance=90)
                    ]
                },
                "champion_runtime": {
                    "solver_algorithm_alns_iteration_trace": [
                        _event("regret3", repair_distance=100, polish_distance=95)
                    ]
                },
            },
            {
                "candidate_runtime": {
                    "solver_algorithm_alns_iteration_trace": [_event("regret3")]
                },
                "champion_runtime": {
                    "solver_algorithm_alns_iteration_trace": [
                        _event("regret3", repair_distance=100, polish_distance=80)
                    ]
                },
            },
            {
                "candidate_runtime": {
                    "solver_algorithm_alns_iteration_trace": [
                        _event("regret3", destroy="route", reason="destroy_empty")
                    ]
                },
                "champion_runtime": {
                    "solver_algorithm_alns_iteration_trace": [
                        _event("regret3", destroy="route", reason="destroy_empty")
                    ]
                },
            },
        ]
    )

    assert payload["candidate"]["post_repair_polish"]["observed"] is None
    comparison = payload["comparison"]["post_repair_polish"]
    assert comparison["observed"] == {
        "candidate": 1,
        "champion": 1,
        "candidate_minus_champion": 0,
        "observed_pairs": 2,
    }
    assert comparison["delta_sum"] == {
        "candidate": 10.0,
        "champion": 5.0,
        "candidate_minus_champion": 5.0,
        "observed_pairs": 2,
    }


def test_operator_comparison_respects_identity_and_timing_coverage() -> None:
    payload = search_allocation.build_search_allocation_evidence(
        [
            {
                "candidate_runtime": {
                    "solver_algorithm_alns_iteration_trace": [
                        _event("regret3", destroy="shaw", before=10, after=20)
                    ]
                },
                "champion_runtime": {
                    "solver_algorithm_alns_iteration_trace": [
                        _event("regret3", destroy="random", before=10, after=30)
                    ]
                },
            },
            {
                "candidate_runtime": {
                    "solver_algorithm_alns_iteration_trace": [
                        {
                            **_event("regret3", destroy="shaw"),
                            "destroy_operator": "",
                        }
                    ]
                },
                "champion_runtime": {
                    "solver_algorithm_alns_iteration_trace": [
                        _event("regret3", destroy="shaw")
                    ]
                },
            },
        ]
    )

    shaw = payload["comparison"]["destroy_operators"]["shaw"]
    assert shaw["selected"] == {
        "candidate": 1,
        "champion": 0,
        "candidate_minus_champion": 1,
        "observed_pairs": 1,
    }
    timing = shaw["selected_iteration_elapsed_ms"]
    assert timing["observed"] == {
        "candidate": 1,
        "champion": 0,
        "candidate_minus_champion": 1,
        "observed_pairs": 1,
    }
    assert timing["total"] == {
        "candidate": 10,
        "champion": 0,
        "candidate_minus_champion": 10,
        "observed_pairs": 1,
    }
    assert timing["mean"]["champion"] is None
    assert timing["mean"]["candidate_minus_champion"] is None


def test_operator_comparison_rejects_partial_identity_even_when_record_exists() -> None:
    candidate_missing_destroy = _event("regret3", destroy="shaw")
    candidate_missing_destroy.pop("destroy_operator")
    champion_second = _event("regret3", destroy="shaw", iteration=2)
    candidate_missing_destroy["iteration"] = 2

    payload = search_allocation.build_search_allocation_evidence(
        [
            {
                "candidate_runtime": {
                    "solver_algorithm_alns_iteration_trace": [
                        _event("regret3", destroy="shaw"),
                        candidate_missing_destroy,
                    ]
                },
                "champion_runtime": {
                    "solver_algorithm_alns_iteration_trace": [
                        _event("regret3", destroy="shaw"),
                        champion_second,
                    ]
                },
            }
        ]
    )

    destroy = payload["comparison"]["destroy_operators"]["shaw"]
    pair = payload["comparison"]["destroy_repair_pairs"]["shaw__regret3"]
    repair = payload["comparison"]["repair_operators"]["regret3"]
    for record in (destroy, pair):
        assert record["selected"]["observed_pairs"] == 0
        assert record["nonempty"]["observed_pairs"] == 0
        assert record["selected_iteration_elapsed_ms"]["total"]["observed_pairs"] == 0
    assert repair["selected"] == {
        "candidate": 2,
        "champion": 2,
        "candidate_minus_champion": 0,
        "observed_pairs": 1,
    }

    candidate_missing_repair = _event("regret3", destroy="shaw", iteration=2)
    candidate_missing_repair.pop("repair_operator")
    payload = search_allocation.build_search_allocation_evidence(
        [
            {
                "candidate_runtime": {
                    "solver_algorithm_alns_iteration_trace": [
                        _event("regret3", destroy="shaw"),
                        candidate_missing_repair,
                    ]
                },
                "champion_runtime": {
                    "solver_algorithm_alns_iteration_trace": [
                        _event("regret3", destroy="shaw"),
                        champion_second,
                    ]
                },
            }
        ]
    )

    destroy = payload["comparison"]["destroy_operators"]["shaw"]
    repair = payload["comparison"]["repair_operators"]["regret3"]
    pair = payload["comparison"]["destroy_repair_pairs"]["shaw__regret3"]
    assert destroy["selected"]["observed_pairs"] == 1
    for record in (repair, pair):
        assert record["selected"]["observed_pairs"] == 0
        assert record["selected_iteration_elapsed_ms"]["total"]["observed_pairs"] == 0


def test_operator_comparison_uses_field_specific_trace_coverage() -> None:
    candidate_missing_reason = _event("regret3", iteration=2)
    candidate_missing_reason.pop("acceptance_reason")
    payload = search_allocation.build_search_allocation_evidence(
        [
            {
                "candidate_runtime": {
                    "solver_algorithm_alns_iteration_trace": [
                        _event("regret3"),
                        candidate_missing_reason,
                    ]
                },
                "champion_runtime": {
                    "solver_algorithm_alns_iteration_trace": [
                        _event("regret3"),
                        _event("regret3", iteration=2),
                    ]
                },
            }
        ]
    )

    destroy = payload["comparison"]["destroy_operators"]["shaw"]
    repair = payload["comparison"]["repair_operators"]["regret3"]
    assert destroy["selected"]["observed_pairs"] == 1
    assert destroy["nonempty"]["observed_pairs"] == 0
    assert repair["invoked"]["observed_pairs"] == 0
    assert repair["accepted"]["observed_pairs"] == 0
    assert repair["selected_iteration_elapsed_ms"]["total"]["observed_pairs"] == 1


def test_pair_identity_key_is_injective_for_separator_and_percent_names() -> None:
    payload = search_allocation.build_search_allocation_evidence(
        [
            {
                "candidate_runtime": {
                    "solver_algorithm_alns_iteration_trace": [
                        _event("c", destroy="a__b"),
                        _event("b__c", destroy="a", iteration=2),
                        _event("c", destroy="a%5F%5Fb", iteration=3),
                    ]
                }
            }
        ]
    )

    pairs = payload["candidate"]["destroy_repair_pairs"]
    assert payload["coverage"]["destroy_repair_pair_key_encoding"] == (
        "component:%=>%25,__=>%5F%5F;join:__"
    )
    assert set(pairs) == {
        "a%5F%5Fb__c",
        "a__b%5F%5Fc",
        "a%255F%255Fb__c",
    }
    assert all(record["selected"] == 1 for record in pairs.values())


def test_destroy_empty_does_not_claim_uninvoked_repair_outcomes() -> None:
    payload = search_allocation.build_search_allocation_evidence(
        [
            {
                "candidate_runtime": {
                    "solver_algorithm_alns_iteration_trace": [
                        _event(
                            "regret3",
                            destroy="route",
                            reason="destroy_empty",
                            accepted=False,
                            best=False,
                        )
                    ]
                }
            }
        ]
    )

    repair = payload["candidate"]["repair_operators"]["regret3"]
    pair = payload["candidate"]["destroy_repair_pairs"]["route__regret3"]
    for record in (repair, pair):
        assert record["selected"] == 1
        assert record["invoked"] == 0
        assert record["completed"] == 0
        assert record["accepted"] == 0
        assert record["best_updates"] == 0
        assert record["coverage"]["accepted"] == 0
        assert record["coverage"]["best_updates"] == 0


def test_partial_phase_and_move_maps_expose_mapping_coverage() -> None:
    payload = search_allocation.build_search_allocation_evidence(
        [
            {
                "candidate_runtime": {
                    "solver_algorithm_phase_runtime_ms": {
                        "shared": 8,
                        "malformed": "bad",
                    },
                    "solver_algorithm_phase_move_attempts": {
                        "shared": 3,
                        "malformed": "bad",
                    },
                },
                "champion_runtime": {
                    "solver_algorithm_phase_runtime_ms": {
                        "shared": 4,
                        "champion_only": 2,
                    },
                    "solver_algorithm_phase_move_attempts": {
                        "shared": 1,
                        "champion_only": 5,
                    },
                },
            }
        ]
    )

    candidate_coverage = payload["coverage"]["candidate"]
    assert candidate_coverage["phase_runtime_ms_mapping_coverage"] == {
        "observed": 1,
        "complete": 0,
        "malformed": 1,
    }
    assert candidate_coverage["move_field_mapping_coverage"]["attempted"] == {
        "observed": 1,
        "complete": 0,
        "malformed": 1,
    }
    assert payload["comparison"]["phase_runtime_ms"]["shared"][
        "observed_pairs"
    ] == 1
    assert payload["comparison"]["phase_runtime_ms"]["champion_only"] == {
        "candidate": None,
        "champion": None,
        "candidate_minus_champion": None,
        "observed_pairs": 0,
    }
    assert payload["comparison"]["move_phases"]["champion_only"]["attempted"][
        "observed_pairs"
    ] == 0


def test_path_only_inputs_produce_static_evidence_without_runtime_pollution(
    monkeypatch,
) -> None:
    instances = {
        "/private/one.vrp": _instance(reference_routes=2),
        "/private/two.vrp": _instance(reference_routes=3),
    }
    monkeypatch.setattr(
        search_allocation,
        "load_cvrplib_instance",
        lambda path: instances[str(path)],
    )

    payload = CvrpProposalMechanismEvidenceProvider().summarize_proposal_mechanism_evidence(
        stage="screening",
        selected_surface="solver_design",
        runtime_pairs=[{"case_path": path} for path in instances],
    )

    assert payload["coverage"]["provider_inputs"] == 2
    assert payload["coverage"]["runtime_pairs"] == 0
    assert payload["coverage"]["candidate"]["runtime_mapping_pairs"] == 0
    assert payload["candidate"]["alns"]["iterations"] is None
    assert payload["instance_feasibility"]["coverage"]["observed_cases"] == 2
    assert "/private/" not in json.dumps(payload, sort_keys=True)


_ELAPSED_FOR_TEST = "solver_algorithm_elapsed_ms"


def _instance(
    *,
    reference_routes: int,
    allowed_routes: int | None = None,
) -> CvrpInstance:
    return CvrpInstance(
        name="private-name",
        capacity=10,
        depot=0,
        nodes=(
            CvrpNode(id=0, x=0, y=0, demand=0),
            CvrpNode(id=1, x=1, y=0, demand=10),
            CvrpNode(id=2, x=2, y=0, demand=10),
        ),
        allowed_routes=allowed_routes,
        bks_routes=reference_routes,
    )


def test_problem_owned_search_allocation_envelope_remains_proposal_only() -> None:
    envelope = problem_proposal_mechanism_evidence(
        stage="screening",
        selected_surface="solver_design",
        runtime_pairs=[
            {
                "candidate_runtime": {
                    "solver_algorithm_alns_iteration_trace": [_event("regret2")]
                },
                "champion_runtime": {
                    "solver_algorithm_alns_iteration_trace": [_event("greedy")]
                },
            }
        ],
        adapter=SimpleNamespace(
            proposal_mechanism_evidence_provider=(
                lambda: CvrpProposalMechanismEvidenceProvider()
            )
        ),
    )

    projected = mechanism_evidence_for_protocol(
        SimpleNamespace(mechanism_evidence=envelope)
    )

    assert projected == envelope
    assert envelope["proposal_visibility_only"] is True
    assert envelope["decision_features_excluded"] is True
    assert envelope["gate_influence"] is False
    assert envelope["evidence"]["gate_influence"] is False
    assert "activation_evidence_status" not in projected
    assert "objective_effect_status" not in projected


def test_legacy_mechanism_shape_keeps_activation_and_effect_derivation() -> None:
    projected = mechanism_evidence_for_protocol(
        SimpleNamespace(
            mechanism_evidence={
                "primary_activation_status": "observed",
                "primary_effect_status": "positive",
            },
            stats=SimpleNamespace(wins=1, losses=0, median_delta=2.0),
        )
    )

    assert projected["activation_evidence_status"] == "observed"
    assert projected["objective_effect_status"] == "positive"


def test_search_allocation_ignores_non_screening_and_unrelated_runtime() -> None:
    provider = CvrpProposalMechanismEvidenceProvider()
    assert (
        provider.summarize_proposal_mechanism_evidence(
            stage="validation",
            selected_surface="solver_design",
            runtime_pairs=[],
        )
        == {}
    )
    assert (
        provider.summarize_proposal_mechanism_evidence(
            stage="screening",
            selected_surface="solver_design",
            runtime_pairs=[{"candidate_runtime": {"unrelated": []}}],
        )
        == {}
    )
