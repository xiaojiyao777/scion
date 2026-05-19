"""Focused tests split from test_research_surfaces_solver_design_integration.py."""

from .research_surfaces_solver_design_support import *  # noqa: F401,F403

def test_solver_design_accepts_declared_per_mechanism_telemetry() -> None:
    spec = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    gate = ContractGate(legacy_problem_spec_from_v1(spec))
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "Run bounded route repair using mechanism repair_probe and record "
            "its activation and best-delta evidence."
        ),
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/local_search.py",
        expected_telemetry={
            "activation": [
                "solver_algorithm_context_records.{mechanism}_iterations",
                "solver_algorithm_phase_runtime_ms.{mechanism}",
            ],
            "effect": [
                "solver_algorithm_phase_improvement_counts.{mechanism}",
                "solver_algorithm_phase_best_delta.{mechanism}",
            ],
        },
    )

    result = gate.validate_hypothesis(hypothesis, [], [])

    c11 = next(
        check for check in result.checks if check.name == "C11_expected_telemetry"
    )
    assert c11.passed


def test_contract_gate_allows_inherited_solver_module_identity_message(
    tmp_path: Path,
) -> None:
    spec = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    champion = tmp_path / "champion"
    target = champion / "policies" / "baseline_modules" / "scheduler.py"
    target.parent.mkdir(parents=True)
    code = (_CVRP_ROOT / "policies" / "baseline_modules" / "scheduler.py").read_text(
        encoding="utf-8"
    )
    target.write_text(code, encoding="utf-8")
    gate = ContractGate(
        legacy_problem_spec_from_v1(spec),
        champion_snapshot_path=str(champion),
    )

    result = gate.validate_patch(
        PatchProposal(
            file_path="policies/baseline_modules/scheduler.py",
            action="modify",
            code_content=code,
        ),
        selected_surface="solver_design",
    )

    c9d = next(
        check for check in result.checks if check.name == "C9d_surface_instance_identity"
    )
    assert c9d.passed


def test_contract_gate_uses_dynamic_champion_snapshot_provider(
    tmp_path: Path,
) -> None:
    spec = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    champion = tmp_path / "champion"
    target = champion / "policies" / "baseline_modules" / "scheduler.py"
    target.parent.mkdir(parents=True)
    code = (_CVRP_ROOT / "policies" / "baseline_modules" / "scheduler.py").read_text(
        encoding="utf-8"
    )
    target.write_text(code, encoding="utf-8")
    current_champion = {"path": str(champion)}
    gate = ContractGate(
        legacy_problem_spec_from_v1(spec),
        champion_snapshot_provider=lambda: current_champion["path"],
    )

    result = gate.validate_patch(
        PatchProposal(
            file_path="policies/baseline_modules/scheduler.py",
            action="modify",
            code_content=code,
        ),
        selected_surface="solver_design",
    )

    c9d = next(
        check for check in result.checks if check.name == "C9d_surface_instance_identity"
    )
    assert c9d.passed


def test_contract_gate_rejects_new_solver_module_identity_branch(
    tmp_path: Path,
) -> None:
    spec = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    champion = tmp_path / "champion"
    target = champion / "policies" / "baseline_modules" / "scheduler.py"
    target.parent.mkdir(parents=True)
    base_code = (
        _CVRP_ROOT / "policies" / "baseline_modules" / "scheduler.py"
    ).read_text(encoding="utf-8")
    target.write_text(base_code, encoding="utf-8")
    code = base_code.replace(
        "    def solve(self, instance, rng):\n",
        "    def solve(self, instance, rng):\n"
        "        if instance.name == 'case-a':\n"
        "            return self._initial_solution(instance, 0.05)\n",
        1,
    )
    gate = ContractGate(
        legacy_problem_spec_from_v1(spec),
        champion_snapshot_path=str(champion),
    )

    result = gate.validate_patch(
        PatchProposal(
            file_path="policies/baseline_modules/scheduler.py",
            action="modify",
            code_content=code,
        ),
        selected_surface="solver_design",
    )

    c9d = next(
        check for check in result.checks if check.name == "C9d_surface_instance_identity"
    )
    assert not c9d.passed
    assert "if instance.name == 'case-a'" in c9d.detail


def test_contract_gate_rejects_inert_solver_design_helper(
    tmp_path: Path,
) -> None:
    spec = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    champion = tmp_path / "champion"
    target = champion / "policies" / "baseline_modules" / "local_search.py"
    target.parent.mkdir(parents=True)
    base_code = (
        _CVRP_ROOT / "policies" / "baseline_modules" / "local_search.py"
    ).read_text(encoding="utf-8")
    target.write_text(base_code, encoding="utf-8")
    code = (
        base_code
        + "\n\n"
        + "def _adaptive_vns(solution, operators, max_no_improve, context, reserve):\n"
        + "    return False\n"
    )
    gate = ContractGate(
        legacy_problem_spec_from_v1(spec),
        champion_snapshot_path=str(champion),
    )

    result = gate.validate_patch(
        PatchProposal(
            file_path="policies/baseline_modules/local_search.py",
            action="modify",
            code_content=code,
        ),
        selected_surface="solver_design",
    )

    c9e = next(
        check for check in result.checks if check.name == "C9e_solver_design_integration"
    )
    assert not c9e.passed
    assert "_adaptive_vns" in c9e.detail
    assert "additional_changes" in c9e.detail
    assert "_ALNSVNSSolver.solve" in c9e.detail


def test_contract_gate_rejects_solver_design_helper_dead_load_reference(
    tmp_path: Path,
) -> None:
    spec = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    champion = tmp_path / "champion"
    target = champion / "policies" / "baseline_modules" / "local_search.py"
    target.parent.mkdir(parents=True)
    base_code = (
        _CVRP_ROOT / "policies" / "baseline_modules" / "local_search.py"
    ).read_text(encoding="utf-8")
    target.write_text(base_code, encoding="utf-8")
    code = base_code.replace(
        "def _vns(solution, operators, max_no_improve, context, reserve):\n",
        "def _vns(solution, operators, max_no_improve, context, reserve):\n"
        "    unused = _adaptive_vns\n",
        1,
    )
    code += (
        "\n\n"
        "def _adaptive_vns(solution, operators, max_no_improve, context, reserve):\n"
        "    return False\n"
    )
    gate = ContractGate(
        legacy_problem_spec_from_v1(spec),
        champion_snapshot_path=str(champion),
    )

    result = gate.validate_patch(
        PatchProposal(
            file_path="policies/baseline_modules/local_search.py",
            action="modify",
            code_content=code,
        ),
        selected_surface="solver_design",
    )

    c9e = next(
        check for check in result.checks if check.name == "C9e_solver_design_integration"
    )
    assert not c9e.passed
    assert "_adaptive_vns" in c9e.detail
    assert "inert_helpers" in c9e.detail


def test_contract_gate_rejects_inert_solver_design_class_method(
    tmp_path: Path,
) -> None:
    spec = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    champion = tmp_path / "champion"
    target = champion / "policies" / "baseline_modules" / "acceptance.py"
    target.parent.mkdir(parents=True)
    base_code = (
        _CVRP_ROOT / "policies" / "baseline_modules" / "acceptance.py"
    ).read_text(encoding="utf-8")
    target.write_text(base_code, encoding="utf-8")
    code = (
        base_code
        + "\n\n"
        + "    def notify_segment_end(self):\n"
        + "        self.temperature = self.start_temp\n"
    )
    gate = ContractGate(
        legacy_problem_spec_from_v1(spec),
        champion_snapshot_path=str(champion),
    )

    result = gate.validate_patch(
        PatchProposal(
            file_path="policies/baseline_modules/acceptance.py",
            action="modify",
            code_content=code,
        ),
        selected_surface="solver_design",
    )

    c9e = next(
        check for check in result.checks if check.name == "C9e_solver_design_integration"
    )
    assert not c9e.passed
    assert "notify_segment_end" in c9e.detail
    assert "inert_helpers" in c9e.detail


def test_contract_gate_rejects_getattr_context_baseline_in_baseline_algorithm(
    tmp_path: Path,
) -> None:
    baseline_path = "policies/baseline_algorithm.py"
    gate, _codes = _gate_with_cvrp_champion(tmp_path, (baseline_path,))
    code = (
        "def solve(instance, rng, time_limit_sec, context):\n"
        "    return getattr(context, 'baseline')(\n"
        "        time_budget_sec=context.remaining_time()\n"
        "    )\n"
    )

    result = gate.validate_patch(
        PatchProposal(
            file_path=baseline_path,
            action="modify",
            code_content=code,
        ),
        selected_surface="solver_design",
    )

    c9 = next(check for check in result.checks if check.name == "C9_sensitive_api")
    assert not c9.passed
    assert "getattr(context, 'baseline')" in c9.detail


def test_contract_gate_rejects_context_baseline_alias_in_baseline_algorithm(
    tmp_path: Path,
) -> None:
    baseline_path = "policies/baseline_algorithm.py"
    gate, _codes = _gate_with_cvrp_champion(tmp_path, (baseline_path,))
    code = (
        "def solve(instance, rng, time_limit_sec, context):\n"
        "    ctx = context\n"
        "    run_baseline = ctx.baseline\n"
        "    return run_baseline(time_budget_sec=context.remaining_time())\n"
    )

    result = gate.validate_patch(
        PatchProposal(
            file_path=baseline_path,
            action="modify",
            code_content=code,
        ),
        selected_surface="solver_design",
    )

    c9 = next(check for check in result.checks if check.name == "C9_sensitive_api")
    assert not c9.passed
    assert "context.baseline alias" in c9.detail
