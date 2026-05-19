from __future__ import annotations

from scion.tests.unit.agentic_solver_design_test_support import *

def test_solver_design_low_effort_issue_rejects_search_bearing_under_spend() -> None:
    patch = PatchProposal(
        file_path="policies/baseline_modules/construction.py",
        action="modify",
        code_content="def seed_pool(instance):\n    return []\n",
        additional_changes=(
            SimpleNamespace(
                file_path="policies/baseline_modules/scheduler.py",
                action="modify",
                code_content="class _ALNSVNSSolver:\n    def solve(self, instance, rng):\n        return instance\n",
            ),
        ),
    )
    hypothesis = HypothesisProposal(
        hypothesis_text="Improve ALNS/VNS search by changing construction seeds.",
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/construction.py",
    )
    runs = [
        {
            "case": "cvrplib/A/A-n32-k5.vrp",
            "seed": 11,
            "passed": True,
            "runtime": {
                "solver_algorithm_search_iterations": 4,
                "solver_algorithm_move_attempts": 24,
                "solver_algorithm_stop_reason": "no_improvement",
                "solver_algorithm_elapsed_ms": 120,
            },
            "run": {"elapsed_ms": 130},
        },
        {
            "case": "cvrplib/B/B-n31-k5.vrp",
            "seed": 11,
            "passed": True,
            "runtime": {
                "solver_algorithm_search_iterations": 1,
                "solver_algorithm_move_attempts": 6,
                "solver_algorithm_stop_reason": "no_improvement",
                "solver_algorithm_elapsed_ms": 90,
            },
            "run": {"elapsed_ms": 100},
        },
    ]
    micro_results = [
        {
            "case": "cvrplib/A/A-n32-k5.vrp",
            "seed": 11,
            "comparison": "tie",
            "candidate_elapsed_ms": 130,
            "champion_elapsed_ms": 3000,
        },
        {
            "case": "cvrplib/B/B-n31-k5.vrp",
            "seed": 11,
            "comparison": "loss",
            "candidate_elapsed_ms": 100,
            "champion_elapsed_ms": 3000,
        },
    ]

    issue = _solver_design_low_effort_issue(
        patch=patch,
        hypothesis=hypothesis,
        runs=runs,
        micro_results=micro_results,
    )

    assert issue is not None
    assert "low active search effort" in issue
    assert "no smoke micro-benchmark win" in issue
    assert "policies/baseline_modules/scheduler.py" in issue


def test_solver_design_low_effort_issue_allows_smoke_micro_win() -> None:
    patch = PatchProposal(
        file_path="policies/baseline_modules/construction.py",
        action="modify",
        code_content="def seed_pool(instance):\n    return []\n",
    )
    hypothesis = HypothesisProposal(
        hypothesis_text="Improve ALNS search from better construction seeds.",
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/construction.py",
    )
    runs = [
        {
            "case": "cvrplib/A/A-n32-k5.vrp",
            "seed": 11,
            "passed": True,
            "runtime": {
                "solver_algorithm_search_iterations": 2,
                "solver_algorithm_move_attempts": 12,
                "solver_algorithm_stop_reason": "no_improvement",
            },
            "run": {"elapsed_ms": 100},
        },
        {
            "case": "cvrplib/B/B-n31-k5.vrp",
            "seed": 11,
            "passed": True,
            "runtime": {
                "solver_algorithm_search_iterations": 2,
                "solver_algorithm_move_attempts": 12,
                "solver_algorithm_stop_reason": "no_improvement",
            },
            "run": {"elapsed_ms": 100},
        },
    ]
    micro_results = [
        {
            "case": "cvrplib/A/A-n32-k5.vrp",
            "seed": 11,
            "comparison": "win",
            "candidate_elapsed_ms": 100,
            "champion_elapsed_ms": 3000,
        }
    ]

    assert (
        _solver_design_low_effort_issue(
            patch=patch,
            hypothesis=hypothesis,
            runs=runs,
            micro_results=micro_results,
        )
        is None
    )


def test_algorithm_smoke_runs_screening_case_preview(
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
                    "    if instance.customer_count > 4:\n"
                    "        raise RuntimeError('screening case only')\n"
                    "    solution = context.make_solution(context.nearest_neighbor())\n"
                    "    context.record_iteration('seed', 1)\n"
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
    assert payload["runtime_smoke"]["case_count"] == 3
    assert "data/tiny_6.json" in rendered
    assert "screening case only" in rendered


def test_algorithm_smoke_uses_active_formal_split_over_workspace_tiny_split(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = replace(
        _cvrp_context(tmp_path),
        split_manifest=SplitManifest(
            version="test-active-formal",
            canary=["controlled/data/synthetic_controlled_canary_5.vrp"],
            screening=[
                "controlled/data/synthetic_screening_micro_5.vrp",
                "controlled/data/synthetic_screening_split_6.vrp",
                "controlled/data/synthetic_validation_micro_5.vrp",
                "controlled/data/synthetic_validation_split_6.vrp",
                "controlled/data/synthetic_frozen_micro_5.vrp",
                "controlled/data/synthetic_frozen_split_6.vrp",
                "controlled/data/synthetic_final_micro_5.vrp",
                "controlled/data/synthetic_final_split_6.vrp",
            ],
        ),
        seed_ledger=SeedLedgerConfig(
            screening=[11, 29],
            validation=[47],
            frozen=[61],
            canary=[101],
        ),
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
                    "    return solution\n"
                ),
            },
        },
        context,
    )

    payload = observation.structured_payload
    rendered = json.dumps(payload, sort_keys=True)
    assert observation.is_error is False
    assert payload["runtime_smoke"]["case_count"] == 5
    assert "controlled/data/synthetic_controlled_canary_5.vrp" in rendered
    assert "controlled/data/synthetic_screening_micro_5.vrp" not in rendered
    assert "controlled/data/synthetic_validation_micro_5.vrp" not in rendered
    assert "controlled/data/synthetic_frozen_split_6.vrp" not in rendered
    assert "controlled/data/synthetic_final_split_6.vrp" not in rendered
    assert "data/tiny_6.json" not in rendered
    assert '"seed": 101' in rendered


def test_runtime_smoke_does_not_resolve_ambient_env_data_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    base_workspace = tmp_path / "base"
    data_root = tmp_path / "problem_data"
    workspace.mkdir()
    base_workspace.mkdir()
    case = data_root / "cvrplib" / "A" / "A-n32-k5.vrp"
    case.parent.mkdir(parents=True)
    case.write_text("NAME : A-n32-k5\n", encoding="utf-8")
    monkeypatch.setenv("SCION_PROBLEM_DATA_ROOT", str(data_root))

    resolved = _resolve_smoke_instance_path(
        workspace=workspace,
        base_workspace=base_workspace,
        case_rel="cvrplib/A/A-n32-k5.vrp",
    )

    assert resolved is None


def test_runtime_smoke_resolves_explicit_safe_data_root(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    base_workspace = tmp_path / "base"
    data_root = tmp_path / "problem_data"
    workspace.mkdir()
    base_workspace.mkdir()
    case = data_root / "cvrplib" / "A" / "A-n32-k5.vrp"
    case.parent.mkdir(parents=True)
    case.write_text("NAME : A-n32-k5\n", encoding="utf-8")

    resolved = _resolve_smoke_instance_path(
        workspace=workspace,
        base_workspace=base_workspace,
        case_rel="cvrplib/A/A-n32-k5.vrp",
        safe_data_roots=(data_root,),
    )

    assert resolved == case


def test_runtime_smoke_rejects_absolute_case_path(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    base_workspace = tmp_path / "base"
    workspace.mkdir()
    base_workspace.mkdir()
    case = tmp_path / "absolute.vrp"
    case.write_text("NAME : absolute\n", encoding="utf-8")

    resolved = _resolve_smoke_instance_path(
        workspace=workspace,
        base_workspace=base_workspace,
        case_rel=str(case),
        safe_data_roots=(tmp_path,),
    )

    assert resolved is None


def test_algorithm_smoke_rejects_preferred_solver_design_baseline_wrapper(
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
                    "    return context.baseline()\n"
                ),
            },
        },
        context,
    )

    rendered = json.dumps(observation.structured_payload, sort_keys=True)
    assert observation.is_error is False
    assert observation.structured_payload["passed"] is False
    assert "must not call context.baseline" in rendered
