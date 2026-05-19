from __future__ import annotations

from scion.tests.unit.agentic_feedback_test_support import *

def test_runtime_diagnosis_tags_zero_phase_and_recovery_only_patterns(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(tmp_path)
    runtime_step = replace(
        context.step_history[0],
        hypothesis=HypothesisProposal(
            hypothesis_text="Accepted moves do not refresh phase best.",
            change_locus="solver_design",
            action="modify",
            target_file="policies/baseline_algorithm.py",
        ),
        protocol_result=ProtocolResult(
            stage=ExperimentStage.SCREENING,
            stats=_stats(wins=0, losses=0, ties=2, win_rate=0.0),
            gate_outcome="fail",
            reason_codes=("SCREENING_FAIL_WIN_RATE",),
            exposed_summary="screening safe summary",
            raw_metrics_ref="/SECRET/raw/metrics/SECRET_RAW_REF.json",
            selected_surface="solver_design",
            candidate_surface_runtime_summary={
                "selected_surface": "solver_design",
                "required_runtime_fields": [
                    "main_search_component_accepted_delta_sum",
                    "main_search_component_recovery_delta_sum",
                    "main_search_component_phase_delta_sum",
                ],
                "fields": {
                    "main_search_component_accepted_delta_sum": {
                        "present": 2,
                        "missing": 0,
                        "empty": 0,
                        "failed": 0,
                        "numeric_summary": {
                            "mapping": {
                                "route_pair_swap": {
                                    "observed_count": 2,
                                    "weighted_sum": 12.0,
                                    "nonzero_count": 2,
                                }
                            }
                        },
                    },
                    "main_search_component_recovery_delta_sum": {
                        "present": 2,
                        "missing": 0,
                        "empty": 0,
                        "failed": 0,
                        "numeric_summary": {
                            "mapping": {
                                "route_pair_swap": {
                                    "observed_count": 2,
                                    "weighted_sum": 12.0,
                                    "nonzero_count": 2,
                                }
                            }
                        },
                    },
                    "main_search_component_phase_delta_sum": {
                        "present": 2,
                        "missing": 0,
                        "empty": 0,
                        "failed": 0,
                        "numeric_summary": {
                            "mapping": {
                                "route_pair_swap": {
                                    "observed_count": 2,
                                    "weighted_sum": 0.0,
                                    "nonzero_count": 0,
                                }
                            }
                        },
                    },
                },
            },
        ),
    )
    context = replace(context, step_history=(runtime_step,))

    observation = registry.call("feedback.query_runtime", {}, context)
    diagnosis = observation.structured_payload["research_diagnosis"]

    assert "zero_phase_delta" in diagnosis["failure_mode_tags"]
    assert "accepted_signal_without_phase_delta" in diagnosis["failure_mode_tags"]
    assert "recovery_only_accepted_moves" in diagnosis["failure_mode_tags"]
    assert diagnosis["runtime_signal_rows"][0]["zero_phase_delta_fields"] == [
        "main_search_component_phase_delta_sum"
    ]


def test_forced_runtime_feedback_omits_conflicting_surface_guidance(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(tmp_path)
    runtime_step = replace(
        context.step_history[0],
        hypothesis=HypothesisProposal(
            hypothesis_text="Local move surface produced no accepted moves.",
            change_locus="route_local",
            action="create_new",
            target_file="operators/local_new.py",
        ),
        protocol_result=ProtocolResult(
            stage=ExperimentStage.SCREENING,
            stats=_stats(wins=0, losses=0, ties=2, win_rate=0.0),
            gate_outcome="continue",
            reason_codes=("tie_dominated",),
            exposed_summary="screening safe summary",
            raw_metrics_ref="/safe/screening.json",
            candidate_runtime_failure_categories={"no_accepted_moves": 2},
            candidate_operator_attempts=24,
            candidate_operator_accepted=0,
        ),
    )
    context = replace(
        context,
        forced_surface="route_local",
        forced_action="create_new",
        step_history=(runtime_step,),
    )

    observation = registry.call(
        "feedback.query_runtime",
        {"surface": "route_local"},
        context,
    )
    guidance = observation.structured_payload["runtime_failure_guidance"]

    assert "forced_surface_constraint: keep surface route_local" in guidance
    assert "recommended_surfaces: search_policy" not in guidance
    assert "discouraged_surfaces: route_local" not in guidance
    assert "declared budget surface" not in guidance


def test_feedback_query_screening_bounds_large_compact_payload_without_error(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(tmp_path)
    protocol = context.step_history[0].protocol_result
    assert protocol is not None
    large_runtime_summary = {
        f"component_{idx}": "accepted route-pair evidence " * 200 for idx in range(60)
    }
    large_step = replace(
        context.step_history[0],
        protocol_result=replace(
            protocol,
            candidate_surface_runtime_summary=large_runtime_summary,
        ),
    )
    context = replace(context, step_history=(large_step,))

    observation = registry.call("feedback.query_screening", {}, context)
    rendered = json.dumps(observation.structured_payload, sort_keys=True, default=str)

    assert observation.is_error is False
    assert observation.failure_code is None
    assert observation.structured_payload["payload_truncated"] is True
    assert len(rendered) <= registry.get("feedback.query_screening").max_result_chars
    assert "raw_metrics_ref" not in rendered


def test_feedback_query_defaults_to_campaign_scope_across_branches(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(tmp_path)
    current_branch = Branch(
        branch_id="branch-current",
        state=BranchState.EXPLORE,
        base_champion_id=7,
        base_champion_hash="code-hash",
    )
    older_step = replace(context.step_history[0], branch_id="branch-older")
    context = replace(
        context,
        branch=current_branch,
        step_history=(older_step,),
    )

    observation = registry.call("feedback.query_screening", {}, context)
    branch_scoped = registry.call(
        "feedback.query_screening",
        {"branch_id": "branch-current"},
        context,
    )

    assert observation.structured_payload["available_screening_step_count"] == 1
    assert observation.structured_payload["matched_screening_step_count"] == 1
    assert (
        observation.structured_payload["screening_steps"][0]["branch_id"]
        == "branch-older"
    )
    assert branch_scoped.structured_payload["matched_screening_step_count"] == 0
    assert branch_scoped.structured_payload["screening_steps"] == []


def test_runtime_feedback_exposes_compact_surface_attribution(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(tmp_path)
    protocol = context.step_history[0].protocol_result
    assert protocol is not None
    main_search_hypothesis = replace(
        _hyp("solver_design"),
        target_file="policies/baseline_algorithm.py",
    )
    attributed_step = replace(
        context.step_history[0],
        hypothesis=main_search_hypothesis,
        protocol_result=replace(
            protocol,
            candidate_surface_runtime_summary={
                "selected_surface": "solver_design",
                "fields": {
                    "main_search_component_accepted": {
                        "present": 2,
                        "missing": 0,
                        "empty": 0,
                        "failed": 0,
                        "numeric_summary": {
                            "mapping": {
                                "route_pair_swap": {
                                    "observed_count": 2,
                                    "weighted_sum": 43.0,
                                    "nonzero_count": 1,
                                    "positive_count": 1,
                                    "zero_count": 1,
                                }
                            }
                        },
                        "values": [
                            {
                                "value": "{'route_pair_swap': 43, 'bounded_destroy_repair': 11}",
                                "count": 1,
                            }
                        ],
                    },
                    "main_search_objective_delta_by_phase": {
                        "present": 2,
                        "missing": 0,
                        "empty": 0,
                        "failed": 0,
                        "values": [{"value": "{'improvement_loop': 0.0}", "count": 2}],
                    },
                },
            },
        ),
    )
    context = replace(context, step_history=(attributed_step,))

    screening = registry.call("feedback.query_screening", {}, context)
    runtime = registry.call("feedback.query_runtime", {}, context)
    rendered = json.dumps(
        [screening.structured_payload, runtime.structured_payload],
        sort_keys=True,
        default=str,
    )

    assert "candidate_surface_runtime_attribution" in rendered
    assert "screening_runtime_attribution" in runtime.structured_payload
    assert "main_search_component_accepted" in rendered
    assert "numeric_summary" in rendered
    assert "nonzero_count" in rendered
    assert "main_search_objective_delta_by_phase" in rendered
    assert "raw_metrics_ref" not in rendered


def test_runtime_feedback_prioritizes_phase_attribution_over_modal_fields(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(tmp_path)
    protocol = context.step_history[0].protocol_result
    assert protocol is not None
    low_priority_fields = {
        f"main_search_low_priority_{index}_active": {
            "present": 2,
            "missing": 0,
            "empty": 0,
            "failed": 0,
            "values": [{"value": "true", "count": 2}],
        }
        for index in range(20)
    }
    fields = {
        **low_priority_fields,
        "main_search_component_accepted_delta_sum": {
            "present": 2,
            "missing": 0,
            "empty": 0,
            "failed": 0,
            "numeric_summary": {
                "mapping": {
                    "route_pair_swap": {
                        "observed_count": 2,
                        "weighted_sum": 507.0,
                        "positive_count": 2,
                    }
                }
            },
            "values": [{"value": "{'route_pair_swap': 507.0}", "count": 1}],
        },
        "main_search_component_phase_delta_sum": {
            "present": 2,
            "missing": 0,
            "empty": 0,
            "failed": 0,
            "numeric_summary": {
                "mapping": {
                    "route_pair_swap": {
                        "observed_count": 2,
                        "weighted_sum": 0.0,
                        "zero_count": 2,
                    }
                }
            },
            "values": [{"value": "{'route_pair_swap': 0.0}", "count": 2}],
        },
        "main_search_component_recovery_delta_sum": {
            "present": 2,
            "missing": 0,
            "empty": 0,
            "failed": 0,
            "numeric_summary": {
                "mapping": {
                    "route_pair_swap": {
                        "observed_count": 2,
                        "weighted_sum": 507.0,
                        "positive_count": 2,
                    }
                }
            },
            "values": [{"value": "{'route_pair_swap': 507.0}", "count": 1}],
        },
        "main_search_objective_delta_by_phase": {
            "present": 2,
            "missing": 0,
            "empty": 0,
            "failed": 0,
            "numeric_summary": {
                "mapping": {
                    "improvement_loop": {
                        "observed_count": 2,
                        "weighted_sum": 0.0,
                        "zero_count": 2,
                    }
                }
            },
            "values": [{"value": "{'improvement_loop': 0.0}", "count": 2}],
        },
    }
    attributed_step = replace(
        context.step_history[0],
        hypothesis=replace(
            _hyp("solver_design"),
            target_file="policies/baseline_algorithm.py",
        ),
        protocol_result=replace(
            protocol,
            candidate_surface_runtime_summary={
                "selected_surface": "solver_design",
                "fields": fields,
            },
        ),
    )
    context = replace(context, step_history=(attributed_step,))

    runtime = registry.call("feedback.query_runtime", {}, context)
    rendered = json.dumps(runtime.structured_payload, sort_keys=True, default=str)

    assert "main_search_component_accepted_delta_sum" in rendered
    assert "main_search_component_phase_delta_sum" in rendered
    assert "main_search_component_recovery_delta_sum" in rendered
    assert "main_search_objective_delta_by_phase" in rendered
    assert "weighted_sum" in rendered
    assert rendered.index("main_search_objective_delta_by_phase") < rendered.index(
        "main_search_low_priority_0_active"
    )


def test_runtime_feedback_surfaces_solver_algorithm_noop_motion(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(tmp_path)
    protocol = context.step_history[0].protocol_result
    assert protocol is not None
    fields = {
        "solver_algorithm_move_attempts": {
            "present": 16,
            "missing": 0,
            "empty": 0,
            "failed": 0,
            "numeric_summary": {
                "scalar": {
                    "observed_count": 16,
                    "weighted_sum": 7194.0,
                    "positive_count": 16,
                    "zero_count": 0,
                }
            },
            "values": [{"value": "125", "count": 2}],
        },
        "solver_algorithm_accepted_moves": {
            "present": 16,
            "missing": 0,
            "empty": 0,
            "failed": 0,
            "numeric_summary": {
                "scalar": {
                    "observed_count": 16,
                    "weighted_sum": 1.0,
                    "positive_count": 1,
                    "zero_count": 15,
                }
            },
            "values": [{"value": "0", "count": 15}],
        },
        "solver_algorithm_best_delta": {
            "present": 16,
            "missing": 0,
            "empty": 0,
            "failed": 0,
            "numeric_summary": {
                "scalar": {
                    "observed_count": 16,
                    "weighted_sum": 1.0,
                    "positive_count": 1,
                    "zero_count": 15,
                }
            },
            "values": [{"value": "0.0", "count": 15}],
        },
        "solver_algorithm_search_iterations": {
            "present": 16,
            "missing": 0,
            "empty": 0,
            "failed": 0,
            "numeric_summary": {
                "scalar": {
                    "observed_count": 16,
                    "weighted_sum": 0.0,
                    "positive_count": 0,
                    "zero_count": 16,
                }
            },
            "values": [{"value": "0", "count": 16}],
        },
    }
    attributed_step = replace(
        context.step_history[0],
        hypothesis=replace(
            _hyp("solver_design"),
            target_file="policies/baseline_algorithm.py",
        ),
        protocol_result=replace(
            protocol,
            candidate_surface_runtime_summary={
                "selected_surface": "solver_design",
                "fields": fields,
            },
        ),
    )
    context = replace(context, step_history=(attributed_step,))

    runtime = registry.call("feedback.query_runtime", {}, context)
    rendered = json.dumps(runtime.structured_payload, sort_keys=True, default=str)

    assert "solver_algorithm_move_attempts" in rendered
    assert "solver_algorithm_accepted_moves" in rendered
    assert "solver_algorithm_best_delta" in rendered
    assert "solver_algorithm_search_iterations" in rendered
    assert "zero_count" in rendered
