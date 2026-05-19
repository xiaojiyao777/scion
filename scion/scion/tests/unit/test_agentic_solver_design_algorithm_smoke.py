from __future__ import annotations

from scion.proposal.tools.previews.algorithm_smoke_feedback import (
    _algorithm_smoke_agent_payload,
)
from scion.tests.unit.agentic_solver_design_test_support import *


def test_algorithm_smoke_runs_tainted_synthetic_preview_without_promotion(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _cvrp_context(tmp_path)
    before = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))

    observation = registry.call(
        "proposal.algorithm_smoke",
        {
            "hypothesis": _valid_hypothesis_payload(
                change_locus="solver_design",
                target_file="policies/baseline_algorithm.py",
            ),
            "patch": {
                "file_path": "policies/baseline_algorithm.py",
                "action": "modify",
                "code_content": (
                    "def solve(instance, rng, time_limit_sec, context):\n"
                    "    solution = context.make_solution(context.nearest_neighbor())\n"
                    "    context.record_iteration('seed', 1)\n"
                    "    context.record_move('seed', attempted=1, accepted=1)\n"
                    "    return solution\n"
                ),
            },
        },
        context,
    )

    after = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
    payload = observation.structured_payload
    assert observation.is_error is False
    assert payload["passed"] is True
    assert payload["non_promotional"] is True
    assert payload["tainted_debug"] is True
    assert payload["workspace_materialized"] is True
    assert payload["verification_run"] is False
    assert payload["protocol_run"] is False
    assert payload["decision_run"] is False
    assert payload["problem_preview"]["passed"] is True
    assert payload["runtime_smoke"]["passed"] is True
    assert payload["runtime_smoke"]["runtime_smoke_run"] is True
    assert payload["runtime_smoke"]["runtime_counters"]["solver_algorithm_path"] == (
        "policies/baseline_algorithm.py"
    )
    assert payload["runtime_smoke"]["data_root_source"] in {
        "workspace",
        "base_workspace",
        "safe_data_root",
        "audited_problem_data_manifest",
    }
    assert payload["runtime_smoke"]["data_root_status"] in {
        "safe_root_relative",
        "audited_manifest_relative",
    }
    assert payload["runtime_smoke"]["provenance"]["absolute_paths_exposed"] is False
    assert str(tmp_path) not in json.dumps(payload["runtime_smoke"], sort_keys=True)
    assert after == before


def test_algorithm_smoke_normalizes_solver_algorithm_surface_alias(
    tmp_path: Path,
) -> None:
    context = _cvrp_context(tmp_path)
    patch = PatchProposal(
        file_path="policies/baseline_algorithm.py",
        action="modify",
        code_content=(
            "def solve(instance, rng, time_limit_sec, context):\n"
            "    solution = context.make_solution(context.nearest_neighbor())\n"
            "    context.record_iteration('seed', 1)\n"
            "    context.record_move('seed', attempted=1, accepted=1)\n"
            "    return solution\n"
        ),
    )

    payload = _runtime_algorithm_smoke_preview(
        context,
        patch,
        "solver_algorithm",
    )

    assert payload is not None
    assert payload["selected_surface"] == "solver_design"
    assert payload["runtime_smoke_run"] is True
    assert payload["resolved_case_path"]


def test_algorithm_smoke_runs_solver_design_module_patch_through_entrypoint(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _cvrp_context(tmp_path)
    before = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
    module_code = (
        _CVRP_ROOT / "policies" / "baseline_modules" / "config.py"
    ).read_text(encoding="utf-8")

    observation = registry.call(
        "proposal.algorithm_smoke",
        {
            "hypothesis": _valid_hypothesis_payload(
                change_locus="solver_design",
                target_file="policies/baseline_modules/config.py",
            ),
            "patch": {
                "file_path": "policies/baseline_modules/config.py",
                "action": "modify",
                "code_content": module_code,
            },
        },
        context,
    )

    after = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
    payload = observation.structured_payload
    assert observation.is_error is False
    assert payload["passed"] is True
    assert payload["workspace_materialized"] is True
    assert payload["problem_preview"]["passed"] is True
    assert payload["runtime_smoke"]["passed"] is True
    assert payload["runtime_smoke"]["runtime_smoke_run"] is True
    assert payload["runtime_smoke"]["runtime_counters"]["solver_algorithm_path"] == (
        "policies/baseline_algorithm.py"
    )
    assert after == before


def test_algorithm_smoke_accepts_legacy_problem_v1_runtime_audit_spec(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _cvrp_context(tmp_path)
    context = replace(
        context,
        problem_spec=legacy_problem_spec_from_v1(context.problem_spec),
    )
    module_code = (
        _CVRP_ROOT / "policies" / "baseline_modules" / "config.py"
    ).read_text(encoding="utf-8")

    observation = registry.call(
        "proposal.algorithm_smoke",
        {
            "hypothesis": _valid_hypothesis_payload(
                change_locus="solver_design",
                target_file="policies/baseline_modules/config.py",
            ),
            "patch": {
                "file_path": "policies/baseline_modules/config.py",
                "action": "modify",
                "code_content": module_code,
            },
        },
        context,
    )

    payload = observation.structured_payload
    assert observation.is_error is False
    assert payload["passed"] is True
    assert payload["runtime_smoke"]["passed"] is True


def test_algorithm_smoke_runs_multi_file_solver_design_patch(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _cvrp_context(tmp_path)
    before = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
    baseline_code = (_CVRP_ROOT / "policies" / "baseline_algorithm.py").read_text(
        encoding="utf-8"
    )
    baseline_code = baseline_code.replace(
        "from .baseline_modules.scheduler import _ALNSVNSSolver\n",
        "from .baseline_modules.scheduler import _ALNSVNSSolver\n"
        "from .baseline_modules.intensification import intensify\n",
        1,
    ).replace(
        "    context.set_stop_reason(solution.stop_reason)\n"
        "    return context.make_solution(solution.routes_as_tuples())\n",
        "    solution = intensify(solution, instance, context)\n"
        "    context.set_stop_reason(solution.stop_reason)\n"
        "    return context.make_solution(solution.routes_as_tuples())\n",
        1,
    )
    helper_code = (
        "def intensify(solution, instance, context):\n"
        "    context.record_phase('intensification', 0.0)\n"
        "    return solution\n"
    )

    observation = registry.call(
        "proposal.algorithm_smoke",
        {
            "hypothesis": _valid_hypothesis_payload(
                change_locus="solver_design",
                action="create_new",
                target_file="policies/baseline_modules/intensification.py",
            ),
            "patch": {
                "file_path": "policies/baseline_modules/intensification.py",
                "action": "create",
                "code_content": helper_code,
                "additional_changes": [
                    {
                        "file_path": "policies/baseline_algorithm.py",
                        "action": "modify",
                        "code_content": baseline_code,
                    }
                ],
            },
        },
        context,
    )

    after = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
    payload = observation.structured_payload
    patch_payload = payload["patch"]

    assert observation.is_error is False
    assert payload["passed"] is True
    assert patch_payload["patch"]["additional_change_count"] == 1
    assert patch_payload["contract"]["passed"] is True
    assert patch_payload.get("failed_checks", []) == []
    assert payload["runtime_smoke"]["passed"] is True
    assert payload["runtime_smoke"]["runtime_smoke_run"] is True
    assert after == before


def test_algorithm_smoke_materializes_readonly_champion_snapshot(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _cvrp_context(tmp_path)
    champion_root = tmp_path / "readonly_cvrp_champion"
    shutil.copytree(
        _CVRP_ROOT,
        champion_root,
        ignore=shutil.ignore_patterns(
            "__pycache__",
            "*.pyc",
            ".pytest_cache",
            ".mypy_cache",
            ".ruff_cache",
        ),
    )
    for path in sorted(champion_root.rglob("*"), reverse=True):
        path.chmod(0o555 if path.is_dir() else 0o444)
    champion_root.chmod(0o555)
    context = replace(
        context,
        champion=ChampionState(
            version=1,
            operator_pool={},
            solver_config_hash="solver-hash",
            code_snapshot_path=str(champion_root),
            code_snapshot_hash="code-hash",
        ),
    )

    try:
        observation = registry.call(
            "proposal.algorithm_smoke",
            {
                "hypothesis": _valid_hypothesis_payload(
                    change_locus="solver_design",
                    target_file="policies/baseline_algorithm.py",
                ),
                "patch": {
                    "file_path": "policies/baseline_algorithm.py",
                    "action": "modify",
                    "code_content": (
                        "def solve(instance, rng, time_limit_sec, context):\n"
                        "    solution = context.make_solution(context.nearest_neighbor())\n"
                        "    context.record_iteration('seed', 1)\n"
                        "    return solution\n"
                    ),
                },
            },
            context,
        )
    finally:
        for path in sorted(champion_root.rglob("*"), reverse=True):
            path.chmod(0o755 if path.is_dir() else 0o644)
        champion_root.chmod(0o755)

    payload = observation.structured_payload
    assert observation.is_error is False
    assert payload["passed"] is True
    assert payload["runtime_smoke"]["passed"] is True
    assert payload["runtime_smoke"]["runtime_smoke_run"] is True


def test_algorithm_smoke_rejects_solver_design_runtime_error(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _cvrp_context(tmp_path)

    observation = registry.call(
        "proposal.algorithm_smoke",
        {
            "hypothesis": _valid_hypothesis_payload(
                change_locus="solver_design",
                target_file="policies/baseline_algorithm.py",
            ),
            "patch": {
                "file_path": "policies/baseline_algorithm.py",
                "action": "modify",
                    "code_content": (
                        "def solve(instance, rng, time_limit_sec, context):\n"
                        "    solution = context.nearest_neighbor()\n"
                        "    context.record_iteration('runtime_error_probe', 1)\n"
                        "    context.record_move('runtime_error_probe', attempted=1, accepted=0)\n"
                        "    if time_limit_sec < 4:\n"
                        "        raise RuntimeError('runtime smoke only')\n"
                        "    return solution\n"
                ),
            },
        },
        context,
    )

    payload = observation.structured_payload
    rendered = json.dumps(payload, sort_keys=True)
    assert observation.is_error is False
    assert payload["passed"] is False
    assert payload["workspace_materialized"] is True
    assert payload["runtime_smoke"]["passed"] is False
    assert "solver_algorithm_errors" in rendered
    assert "runtime smoke only" in rendered
    assert "policies/baseline_algorithm.py" in rendered


def test_algorithm_smoke_rejects_zero_search_solver_design_candidate(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _cvrp_context(tmp_path)

    observation = registry.call(
        "proposal.algorithm_smoke",
        {
            "hypothesis": _valid_hypothesis_payload(
                change_locus="solver_design",
                target_file="policies/baseline_algorithm.py",
            ),
            "patch": {
                "file_path": "policies/baseline_algorithm.py",
                "action": "modify",
                "code_content": (
                    "def solve(instance, rng, time_limit_sec, context):\n"
                    "    return context.nearest_neighbor()\n"
                ),
            },
        },
        context,
    )

    payload = observation.structured_payload
    rendered = json.dumps(payload, sort_keys=True)
    assert observation.is_error is False
    assert payload["passed"] is False
    assert "runtime_smoke" not in payload
    assert "active search telemetry" in rendered


def test_algorithm_smoke_rejects_missing_declared_mechanism_evidence(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _cvrp_context(tmp_path)
    mechanism = {"id": "vns_local_search", "change_type": "modify"}

    observation = registry.call(
        "proposal.algorithm_smoke",
        {
            "hypothesis": _valid_hypothesis_payload(
                change_locus="solver_design",
                target_file="policies/baseline_algorithm.py",
                mechanism_changes=[mechanism],
            ),
            "patch": {
                "file_path": "policies/baseline_algorithm.py",
                "action": "modify",
                "code_content": (
                    "def solve(instance, rng, time_limit_sec, context):\n"
                    "    solution = context.make_solution(context.nearest_neighbor())\n"
                    "    context.record_iteration('seed', 1)\n"
                    "    context.record_move('seed', attempted=1, accepted=1)\n"
                    "    context.record_move('vns_local_search', attempted=1, accepted=0)\n"
                    "    return solution\n"
                ),
                "mechanism_changes": [mechanism],
            },
        },
        context,
    )

    payload = observation.structured_payload
    rendered = json.dumps(payload, sort_keys=True)
    assert observation.is_error is False
    assert payload["passed"] is False
    assert "runtime_smoke" not in payload
    assert "telemetry_static_preview" in payload
    assert "vns_local_search" in rendered
    assert "DECLARED_MECHANISM_ACTIVATION_MISSING" in rendered
    assert "record_move alone" in rendered


def test_algorithm_smoke_agent_payload_compacts_large_runtime_without_result_too_large(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _cvrp_context(tmp_path)
    huge_stdout = "FULL_STDOUT_BEGIN\n" + ("stdout line\n" * 9000) + "FULL_STDOUT_END"
    huge_stderr = "FULL_STDERR_BEGIN\n" + ("stderr line\n" * 9000) + "FULL_STDERR_END"
    huge_events = [
        {
            "type": "error",
            "message": "NameError: DESTROY_RATIO_LOW is not defined",
            "payload": "x" * 200,
        }
        for _ in range(700)
    ]

    def fake_runtime_smoke(context, patch, selected_surface, hypothesis):
        del context, patch, selected_surface, hypothesis
        return {
            "passed": False,
            "runtime_smoke_run": True,
            "workspace_materialized": True,
            "selected_surface": "solver_design",
            "case": "controlled/data/canary.vrp",
            "case_count": 2,
            "issues": ["NameError: DESTROY_RATIO_LOW is not defined"],
            "run": {
                "success": False,
                "exit_code": 1,
                "elapsed_ms": 1234,
                "error_category": "runtime_exception",
                "detail": "solver run failed",
                "stdout": huge_stdout,
                "stderr": huge_stderr,
            },
            "runtime": {
                "solver_algorithm_path": "policies/baseline_algorithm.py",
                "solver_algorithm_errors": 1,
                "solver_algorithm_events": huge_events,
                "solver_algorithm_search_iterations": 0,
                "solver_algorithm_move_attempts": 0,
            },
            "runtime_audit_failure": {
                "error_category": "solver_algorithm_errors",
                "detail": "solver runtime audit reported solver_algorithm_errors=1",
                "solver_algorithm_errors": 1,
                "solver_algorithm_events": huge_events,
            },
            "telemetry_guard": {
                "passed": False,
                "selected_surface": "solver_design",
                "candidate_runs": 2,
                "champion_runs": 2,
                "expected_telemetry_present": True,
                "declared_mechanisms": ["missing_probe"],
                "failures": [
                    {
                        "code": "TELEMETRY_MECHANISM_ACTIVATION_NOT_OBSERVED",
                        "severity": "fail",
                        "mechanism": "missing_probe",
                        "category": "activation",
                        "field": "solver_algorithm_events",
                        "candidate_positive": 0,
                        "candidate_present": 2,
                        "candidate_missing": 0,
                        "champion_positive": 1,
                    }
                ],
                "fields": {"solver_algorithm_events": {"examples": huge_events}},
            },
            "runs": [
                {
                    "case": f"case-{idx}.vrp",
                    "runtime": {"solver_algorithm_events": huge_events},
                    "run": {"stdout": huge_stdout, "stderr": huge_stderr},
                    "micro_benchmark": {
                        "comparison": "loss",
                        "delta": -3.0,
                        "decisive_metric": "total_distance",
                        "runtime_delta_ms": 47,
                        "candidate_objective": {"total_distance": 103.0},
                        "champion_objective": {"total_distance": 100.0},
                    },
                }
                for idx in range(50)
            ],
            "micro_benchmark": {
                "non_promotional": True,
                "tainted_debug": True,
                "comparable_cases": 2,
                "wins": 0,
                "losses": 1,
                "ties": 1,
                "results": [
                    {
                        "label": "canary",
                        "case": "controlled/data/canary.vrp",
                        "comparison": "loss",
                        "delta": -3.0,
                        "decisive_metric": "total_distance",
                        "runtime_delta_ms": 47,
                    }
                ],
            },
        }

    monkeypatch.setattr(
        preview_tools,
        "_runtime_algorithm_smoke_preview",
        fake_runtime_smoke,
    )

    observation = registry.call(
        "proposal.algorithm_smoke",
        {
            "hypothesis": _valid_hypothesis_payload(
                change_locus="solver_design",
                target_file="policies/baseline_algorithm.py",
            ),
            "patch": {
                "file_path": "policies/baseline_algorithm.py",
                "action": "modify",
                "code_content": (
                    "def solve(instance, rng, time_limit_sec, context):\n"
                    "    solution = context.make_solution(context.nearest_neighbor())\n"
                    "    context.record_iteration('seed', 1)\n"
                    "    context.record_move('seed', attempted=1, accepted=1)\n"
                    "    return solution\n"
                ),
            },
        },
        context,
    )

    payload = observation.structured_payload
    rendered = json.dumps(payload, sort_keys=True)
    guard = payload["telemetry_guard"]

    assert observation.is_error is False
    assert observation.failure_code is None
    assert _json_size(payload) < 60000
    assert payload["agent_summary"]["primary_issue"] == (
        "NameError: DESTROY_RATIO_LOW is not defined"
    )
    assert payload["failure_class"] == "telemetry_guard_failure"
    assert "runs" not in payload["runtime_smoke"]
    assert "run" not in payload["runtime_smoke"]
    assert "runtime" not in payload["runtime_smoke"]
    assert "runtime_smoke" not in payload["patch"]
    assert "code_content" not in rendered
    assert "FULL_STDOUT_BEGIN" not in rendered
    assert "FULL_STDERR_BEGIN" not in rendered
    assert len(payload["subprocess"]["stderr_tail"]) < 1000
    assert guard["failure_code"] == "TELEMETRY_MECHANISM_ACTIVATION_NOT_OBSERVED"
    assert guard["mechanism"] == "missing_probe"
    assert guard["category"] == "activation"
    assert guard["field"] == "solver_algorithm_events"
    assert guard["counters"]["candidate_positive"] == 0
    assert payload["runtime_comparison"]["losses"] == 1
    assert payload["runtime_comparison"]["representative_case"]["delta"] == -3.0


def test_algorithm_smoke_feedback_separates_mechanism_telemetry_statuses() -> None:
    payload = _algorithm_smoke_agent_payload(
        {
            "passed": False,
            "runtime_smoke": {
                "passed": False,
                "runtime_smoke_run": True,
                "selected_surface": "solver_design",
                "case_count": 2,
                "issues": [
                    "telemetry guard observed no activation evidence for declared "
                    "mechanism vns_local_search"
                ],
                "telemetry_guard": {
                    "passed": False,
                    "selected_surface": "solver_design",
                    "candidate_runs": 2,
                    "champion_runs": 2,
                    "expected_telemetry_present": True,
                    "declared_mechanisms": ["vns_local_search"],
                    "mechanism_diagnostics": [
                        {
                            "mechanism": "vns_local_search",
                            "activation_status": "missing",
                            "runtime_status": "missing",
                            "effect_status": "zero",
                            "activation_observed": False,
                            "runtime_observed": False,
                            "effect_observed": False,
                            "activation": {
                                "status": "missing",
                                "fields": [
                                    "solver_algorithm_context_records."
                                    "vns_local_search_iterations",
                                    "solver_algorithm_phase_runtime_ms."
                                    "vns_local_search",
                                ],
                                "candidate_positive": 0,
                                "candidate_present": 0,
                                "candidate_zero": 0,
                                "candidate_missing": 4,
                            },
                            "runtime": {
                                "status": "missing",
                                "fields": [
                                    "solver_algorithm_phase_runtime_ms."
                                    "vns_local_search"
                                ],
                                "candidate_positive": 0,
                                "candidate_present": 0,
                                "candidate_zero": 0,
                                "candidate_missing": 2,
                            },
                            "effect": {
                                "status": "zero",
                                "fields": [
                                    "solver_algorithm_phase_improvement_counts."
                                    "vns_local_search",
                                    "solver_algorithm_phase_best_delta."
                                    "vns_local_search",
                                ],
                                "candidate_positive": 0,
                                "candidate_present": 4,
                                "candidate_zero": 4,
                                "candidate_missing": 0,
                            },
                            "repair_guidance": [
                                "Add direct activation telemetry for declared "
                                "mechanism vns_local_search."
                            ],
                        }
                    ],
                    "failures": [
                        {
                            "code": "TELEMETRY_MECHANISM_ACTIVATION_NOT_OBSERVED",
                            "severity": "fail",
                            "mechanism": "vns_local_search",
                            "category": "activation",
                            "field": (
                                "solver_algorithm_context_records."
                                "vns_local_search_iterations,"
                                "solver_algorithm_phase_runtime_ms.vns_local_search"
                            ),
                            "candidate_positive": 0,
                            "candidate_present": 0,
                            "candidate_zero": 0,
                            "candidate_missing": 4,
                            "champion_positive": 0,
                        }
                    ],
                    "warnings": [
                        {
                            "code": "TELEMETRY_MECHANISM_EFFECT_NOT_OBSERVED",
                            "severity": "warn",
                            "mechanism": "vns_local_search",
                            "category": "effect",
                            "field": (
                                "solver_algorithm_phase_improvement_counts."
                                "vns_local_search,"
                                "solver_algorithm_phase_best_delta.vns_local_search"
                            ),
                            "candidate_positive": 0,
                            "candidate_present": 4,
                            "candidate_zero": 4,
                            "candidate_missing": 0,
                            "champion_positive": 0,
                        }
                    ],
                },
            },
        }
    )

    diagnostic = payload["telemetry_guard"]["mechanism_diagnostics"][0]
    assert diagnostic["mechanism"] == "vns_local_search"
    assert diagnostic["activation_status"] == "missing"
    assert diagnostic["runtime_status"] == "missing"
    assert diagnostic["effect_status"] == "zero"
    assert diagnostic["effect"]["counters"]["candidate_zero"] == 4
    assert "Add direct activation telemetry" in payload["repair_hints"][0]
