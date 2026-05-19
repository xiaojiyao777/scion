from __future__ import annotations

from scion.tests.unit.agentic_solver_design_test_support import *

def test_solver_design_code_prompt_omits_duplicate_champion_policy_bundle() -> None:
    client = CapturingToolClient()
    creative = CreativeLayer(client)

    creative.generate_code(
        {
            "problem_summary": "CVRP.",
            "research_surface_name": "solver_design",
            "research_surface_kind": "solver_design",
            "change_locus": "solver_design",
            "hypothesis_detail": "Implement a direct solver body.",
            "operator_interface_spec": "def solve(instance, rng, time_limit_sec, context)",
            "import_whitelist": "math, random, time",
            "champion_operators_code": (
                "### policies/search_policy.py\n"
                "def baseline_time_fraction(instance, time_limit_sec):\n"
                "    return 0.75\n"
            ),
            "target_file_code": (
                "def solve(instance, rng, time_limit_sec, context):\n"
                "    return None\n"
            ),
            "reference_operators": "",
            "editable_patterns": "policies/*.py",
            "frozen_patterns": "solver.py, adapter.py",
        }
    )

    rendered_system = json.dumps(client.system_blocks, sort_keys=True)
    rendered_prompt = "\n".join(client.prompts)

    assert "baseline_time_fraction" not in rendered_system
    assert "Target File" in rendered_prompt
    assert "def solve(instance, rng, time_limit_sec, context):" in rendered_prompt


def test_solver_design_code_prompt_enforces_compact_single_mechanism_scope() -> None:
    client = CapturingToolClient()
    creative = CreativeLayer(client)

    creative.generate_code(
        {
            "problem_summary": "CVRP.",
            "research_surface_name": "solver_design",
            "research_surface_kind": "solver_design",
            "change_locus": "solver_design",
            "code_generation_mode": "compact_timeout_retry",
            "hypothesis_detail": (
                "Implement a hybrid ALNS/VNS route-pool destroy-repair "
                "population portfolio."
            ),
            "agentic_code_scope_control": {
                "mode": "compact_timeout_retry",
                "detected_broad_terms": [
                    "hybrid",
                    "alns",
                    "destroy",
                    "repair",
                    "portfolio",
                ],
                "failure_detail": "code_generation_timeout",
            },
            "solver_design_api_manifest": (
                "Approved target_file: policies/baseline_modules/destroy_repair.py\n"
                "- policies/baseline_modules/construction.py: exports "
                "def _clarke_wright_savings(instance, target_routes); "
                "def _nearest_neighbor(instance)\n"
                "Target-specific rule for destroy_repair.py: scheduler.py "
                "may only import exact new symbols from .destroy_repair."
            ),
            "solver_design_branch_current_integration_files": (
                "### policies/baseline_algorithm.py\n"
                "Provenance: branch_workspace; readable=True\n"
                "```python\n"
                "def solve(instance, rng, time_limit_sec, context):\n"
                "    solver = _ALNSVNSSolver(context=context)\n"
                "    return solver.solve(instance, rng)\n"
                "```\n"
                "### policies/baseline_modules/scheduler.py\n"
                "Provenance: branch_workspace; readable=True\n"
                "```python\n"
                "class _ALNSVNSSolver:\n"
                "    def solve(self, instance, rng):\n"
                "        return None\n"
                "```"
            ),
            "operator_interface_spec": "def solve(instance, rng, time_limit_sec, context)",
            "import_whitelist": "math, random, time",
            "champion_operators_code": "",
            "target_file_code": (
                "def solve(instance, rng, time_limit_sec, context):\n"
                "    return None\n"
            ),
            "reference_operators": "",
            "editable_patterns": "policies/*.py",
            "frozen_patterns": "solver.py, adapter.py",
        }
    )

    rendered_system = "\n".join(
        block["text"] for blocks in client.system_blocks for block in blocks
    )
    rendered_prompt = "\n".join(client.prompts)

    assert "Compact Solver-Design Implementation Scope" in rendered_system
    assert "one primary mechanism" in rendered_system
    assert "around 180 lines or less" in rendered_system
    assert (
        "Do not implement more than two move/neighborhood families" in rendered_system
    )
    assert "target file should own the mechanism" in rendered_system
    assert "stable runtime contract" in rendered_system
    assert "Approved Target File Full Current Content" in rendered_prompt
    assert "Branch-Current Integration Files" in rendered_prompt
    assert "branch_workspace" in rendered_prompt
    assert "smallest necessary wiring edits" in rendered_prompt
    assert "_ALNSVNSSolver(...).solve(instance, rng)" in rendered_system
    assert "scheduler as orchestration" in rendered_system
    assert "_ALNSVNSSolver.__init__(self, *" in rendered_system
    assert "_ALNSVNSSolver.solve(self, instance, rng)" in rendered_system
    assert "initial-state hooks inside scheduler methods" in rendered_system
    assert "zero iterations and zero move attempts" in rendered_system
    assert "_default_vns_operators()" in rendered_system
    assert "detached `_run`/`run`" in rendered_system
    assert "do not implement a full portfolio" in rendered_system
    assert "_Solution.routes" in rendered_system
    assert "not `list[list[int]]`" in rendered_system
    assert "from_public" in rendered_system
    assert "from_cvrp_solution" in rendered_system
    assert "context.make_solution(solution.routes_as_tuples())" in rendered_system
    assert "Do not edit `policies/baseline_modules/state.py`" in rendered_prompt
    assert "complete contents of the target algorithm module" in rendered_prompt
    assert "Solver-Design Module API Manifest" in rendered_prompt
    assert "_clarke_wright_savings" in rendered_prompt
    assert "may only import exact new symbols from .destroy_repair" in rendered_prompt


def test_latest_preview_failure_detail_uses_latest_preview_not_stale_smoke() -> None:
    smoke = ProposalObservation(
        observation_id="smoke-1",
        session_id="session-1",
        tool_name="proposal.algorithm_smoke",
        tool_call_id="call-1",
        observation_type="tool_result",
        summary="Algorithm smoke failed.",
        structured_payload={
            "passed": False,
            "runtime_smoke": {
                "issues": ["old runtime failure"],
            },
        },
    )
    contract = ProposalObservation(
        observation_id="contract-1",
        session_id="session-1",
        tool_name="proposal.contract_preview",
        tool_call_id="call-2",
        observation_type="tool_result",
        summary="Contract preview failed.",
        structured_payload={
            "passed": False,
            "issue_summary": "new object model API misuse",
        },
    )

    detail = _latest_preview_failure_detail([smoke, contract])

    assert detail is not None
    assert "contract preview did not pass" in detail
    assert "new object model API misuse" in detail
    assert "old runtime failure" not in detail


def test_solver_run_failure_detail_includes_category_exit_and_stdout() -> None:
    detail = _solver_run_failure_detail(
        RunResult(
            success=False,
            exit_code=-9,
            stdout="last solver line",
            stderr="",
            elapsed_ms=12034,
            output_path=None,
            error_category="timeout",
        )
    )

    assert "solver run failed" in detail
    assert "exit_code=-9" in detail
    assert "error_category=timeout" in detail
    assert "elapsed_ms=12034" in detail
    assert "stdout=last solver line" in detail


def test_compact_algorithm_smoke_observation_preserves_pass_signal() -> None:
    observation = ProposalObservation(
        observation_id="smoke-1",
        session_id="session-1",
        tool_name="proposal.algorithm_smoke",
        tool_call_id="tool-10",
        observation_type="algorithm_smoke",
        summary="Algorithm smoke passed on tainted synthetic preview.",
        structured_payload={
            "passed": True,
            "non_promotional": True,
            "tainted_debug": True,
            "workspace_materialized": False,
            "verification_run": False,
            "protocol_run": False,
            "decision_run": False,
            "hypothesis": {
                "passed": True,
                "hypothesis_text": "x" * 8000,
                "contract": {"passed": True, "check_count": 6},
                "checks": [{"name": "C2_locus", "passed": True}],
            },
            "patch": {
                "passed": True,
                "code_content": "x" * 48000,
                "contract": {"passed": True, "check_count": 10},
                "checks": [{"name": "C7_interface", "passed": True}],
                "problem_preview": {
                    "passed": True,
                    "surface": "solver_design",
                    "checks": [{"name": "preview", "passed": True}],
                    "workspace_materialized": False,
                },
            },
            "problem_preview": {
                "passed": True,
                "surface": "solver_design",
                "checks": [{"name": "preview", "passed": True}],
                "workspace_materialized": False,
            },
            "runtime_smoke": {
                "passed": False,
                "runtime_smoke_run": True,
                "workspace_materialized": True,
                "case": "controlled/data/canary.vrp",
                "seed": 77,
                "case_count": 1,
                "issues": ["runtime audit failed"],
                "runtime_audit_failure": {
                    "error_category": "solver_algorithm_errors",
                    "detail": "'_Route' object is not subscriptable",
                    "solver_algorithm_errors": 1,
                    "solver_algorithm_events": [
                        {"type": "error", "message": "'_Route' object is not subscriptable"}
                    ],
                },
                "runtime": {
                    "solver_algorithm_loaded": True,
                    "solver_algorithm_active": True,
                    "solver_algorithm_errors": 1,
                    "solver_algorithm_events": [
                        {"type": "error", "message": "'_Route' object is not subscriptable"}
                    ],
                },
                "micro_benchmark": {
                    "non_promotional": True,
                    "tainted_debug": True,
                    "comparable_cases": 1,
                    "wins": 0,
                    "losses": 1,
                    "ties": 0,
                    "results": [
                        {
                            "label": "canary",
                            "case": "controlled/data/canary.vrp",
                            "comparison": "loss",
                            "delta": -3.0,
                            "decisive_metric": "total_distance",
                            "runtime_delta_ms": -100,
                        }
                    ],
                },
                "run": {"success": True, "detail": "solver smoke completed"},
            },
        },
    )

    compact = _compact_algorithm_smoke_observation(observation)

    assert compact is not None
    assert compact.is_error is False
    assert _json_size(_observation_prompt_payload(compact)) < 2200
    assert compact.structured_payload["passed"] is True
    assert compact.structured_payload["patch"]["contract"]["check_count"] == 10
    assert compact.structured_payload["problem_preview"]["passed"] is True
    assert compact.structured_payload["runtime_smoke"]["runtime"][
        "solver_algorithm_errors"
    ] == 1
    assert "_Route" in compact.structured_payload["runtime_smoke"][
        "runtime_audit_failure"
    ]["detail"]
    assert compact.structured_payload["runtime_smoke"]["micro_benchmark"][
        "losses"
    ] == 1
    assert compact.structured_payload["compact_due_to_budget"] is True


def test_code_prompt_observation_payload_preserves_algorithm_smoke_runtime_detail() -> None:
    observation = ProposalObservation(
        observation_id="smoke-runtime",
        session_id="session-1",
        tool_name="proposal.algorithm_smoke",
        tool_call_id="tool-12",
        observation_type="algorithm_smoke",
        summary="Algorithm smoke found issues.",
        structured_payload={
            "passed": False,
            "runtime_smoke": {
                "passed": False,
                "runtime_smoke_run": True,
                "case": "controlled/data/canary.vrp",
                "issues": ["solver runtime audit reported solver_algorithm_errors=1"],
                "runtime_audit_failure": {
                    "detail": "solver runtime audit reported solver_algorithm_errors=1",
                    "solver_algorithm_errors": 1,
                    "solver_algorithm_events": [
                        {
                            "type": "error",
                            "message": "NameError: DESTROY_RATIO_LOW is not defined",
                        }
                    ],
                },
                "runtime": {
                    "solver_algorithm_errors": 1,
                    "solver_algorithm_events": [
                        {
                            "type": "error",
                            "message": "NameError: DESTROY_RATIO_LOW is not defined",
                        }
                    ],
                },
                "run": {
                    "success": True,
                    "detail": "solver smoke completed",
                    "stderr": "",
                },
            },
        },
    )

    selected = _code_prompt_observations([observation])
    compact = _code_observation_prompt_payload(selected[0])
    detail = _algorithm_smoke_failure_detail([observation])
    rendered = json.dumps(compact, sort_keys=True, default=str)

    assert selected == [observation]
    assert "DESTROY_RATIO_LOW" in rendered
    assert detail is not None
    assert "DESTROY_RATIO_LOW" in detail


def test_algorithm_smoke_failure_detail_includes_repair_guidance() -> None:
    observation = ProposalObservation(
        observation_id="smoke-runtime",
        session_id="session-1",
        tool_name="proposal.algorithm_smoke",
        tool_call_id="tool-12",
        observation_type="algorithm_smoke",
        summary="Algorithm smoke found issues.",
        structured_payload={
            "passed": False,
            "runtime_smoke": {
                "passed": False,
                "issues": ["solver runtime audit reported solver_algorithm_errors=1"],
                "runtime": {
                    "solver_algorithm_errors": 1,
                    "solver_algorithm_events": [
                        {
                            "policy": "policies/baseline_algorithm.py",
                            "status": "error",
                            "detail": "solve failed: '_Solution' object has no attribute '_instance'",
                        }
                    ],
                },
                "repair_guidance": [
                    "Specific fix: replace solution._instance with solution.instance.",
                    "_Solution.routes contains _Route objects.",
                ],
            },
        },
    )

    detail = _algorithm_smoke_failure_detail([observation])

    assert detail is not None
    assert "_Solution" in detail
    assert "solution.instance" in detail


def test_algorithm_smoke_compacts_to_fit_remaining_observation_budget(
    tmp_path: Path,
) -> None:
    context = _context(tmp_path, policy=_tool_enabled_policy())
    config = AgenticToolLoopConfig(max_observation_chars=64000)
    state = AgenticProposalSessionState(
        session_id="session-smoke-budget",
        campaign_id="camp-1",
        branch_id="branch-1",
        observation_chars_used=62400,
    )
    session = AgenticProposalSession(
        FakeCreative(),
        tool_registry=ProposalToolRegistry.default_read_only(),
        tool_loop_config=config,
    )
    observation = ProposalObservation(
        observation_id="smoke-2",
        session_id=state.session_id,
        tool_name="proposal.algorithm_smoke",
        tool_call_id="tool-11",
        observation_type="algorithm_smoke",
        summary="Algorithm smoke passed on tainted synthetic preview.",
        structured_payload={
            "passed": True,
            "non_promotional": True,
            "tainted_debug": True,
            "workspace_materialized": False,
            "verification_run": False,
            "protocol_run": False,
            "decision_run": False,
            "patch": {
                "passed": True,
                "code_content": "x" * 48000,
                "contract": {"passed": True, "check_count": 10},
                "problem_preview": {"passed": True, "surface": "solver_design"},
            },
            "problem_preview": {"passed": True, "surface": "solver_design"},
        },
    )

    compact = session._enforce_observation_budget(context, state, observation)

    assert compact.is_error is False
    assert compact.failure_code is None
    assert compact.structured_payload["passed"] is True
    assert compact.structured_payload["compact_due_to_budget"] is True
    assert _json_size(_observation_prompt_payload(compact)) <= (
        config.max_observation_chars - state.observation_chars_used
    )
