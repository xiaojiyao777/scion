from __future__ import annotations

import json

from scion.config.problem import ProblemSpec, SearchSpace
from scion.core.models import PatchProposal, RunResult, SolverOutput
from scion.problem.contracts import CheckReport, SolverArtifact
from scion.runtime.audit import runtime_audit_issue_blocks_execution
from scion.verification.gate import VerificationGate


class _PassingAdapter:
    def load_instance(self, instance_path: str) -> object:
        return object()

    def deserialize_solver_output(self, raw_output, instance) -> SolverArtifact:
        return SolverArtifact(
            raw_output=raw_output,
            objective=dict(raw_output["objective"]),
            feasible=bool(raw_output["feasible"]),
            normalized_solution=raw_output.get("solution"),
        )

    def check_solution_consistency(self, artifact, instance) -> CheckReport:
        return CheckReport(passed=True)

    def check_feasibility(self, artifact, instance) -> CheckReport:
        return CheckReport(passed=artifact.feasible)

    def recompute_objective(self, artifact, instance):
        return dict(artifact.objective)


class _CountingRunner:
    def __init__(self, raw: dict) -> None:
        self.raw = raw
        self.calls: list[dict] = []

    def run_solver(
        self,
        workdir,
        instance_path,
        seed,
        time_limit_sec,
        registry_path,
        selected_surface=None,
    ) -> RunResult:
        self.calls.append(
            {
                "workdir": workdir,
                "instance_path": instance_path,
                "seed": seed,
                "selected_surface": selected_surface,
            }
        )
        output_path = f"{workdir}/shared-canary-{len(self.calls)}.json"
        with open(output_path, "w", encoding="utf-8") as handle:
            json.dump(self.raw, handle)
        return RunResult(
            success=True,
            exit_code=0,
            stdout="",
            stderr="",
            elapsed_ms=10,
            output=SolverOutput(
                objective=dict(self.raw["objective"]),
                feasible=bool(self.raw["feasible"]),
                runtime=dict(self.raw["runtime"]),
                solution_payload={"solution": self.raw["solution"]},
            ),
            output_path=output_path,
        )


def _spec(tmp_path) -> ProblemSpec:
    canary = tmp_path / "case.json"
    canary.write_text("{}", encoding="utf-8")
    return ProblemSpec(
        name="shared-canary-test",
        root_dir=str(tmp_path),
        canary_case_path=str(canary),
        operator_categories=["search_policy"],
        search_space=SearchSpace(
            editable=["operators/*.py"],
            frozen=[],
            import_whitelist=["__future__"],
        ),
        research_surfaces=[
            {
                "name": "search_policy",
                "kind": "operator",
                "target_files": ["operators/*.py"],
                "evidence": {
                    "required_runtime_fields": [
                        "policy_loaded",
                        "policy_errors",
                        "policy_elapsed_ms",
                        "policy_phase_runtime_ms",
                    ]
                },
            }
        ],
    )


def _patch() -> PatchProposal:
    return PatchProposal(
        file_path="operators/my_op.py",
        action="create",
        code_content=(
            "class MyOp:\n"
            "    def execute(self, solution, rng):\n"
            "        return solution\n"
        ),
    )


def test_verification_shares_one_candidate_run_and_only_repeats_for_determinism(
    tmp_path,
) -> None:
    raw = {
        "objective": {"score": 1},
        "feasible": True,
        "solution": {"value": 1},
        # Missing policy_loaded plus inconsistent phase attribution are
        # diagnostics, not correctness failures.
        "runtime": {
            "policy_errors": 0,
            "policy_elapsed_ms": 1,
            "policy_phase_runtime_ms": {"search": 100_000},
        },
    }
    runner = _CountingRunner(raw)
    gate = VerificationGate(
        problem_spec=_spec(tmp_path),
        runner=runner,
        adapter=_PassingAdapter(),
        strict_runtime_checks=True,
        require_adapter_for_runtime=True,
    )

    result = gate.run(
        str(tmp_path),
        str(tmp_path / "unused-champion"),
        _patch(),
        selected_surface="search_policy",
    )

    assert result.passed is True
    assert [check.name for check in result.checks][-4:] == [
        "V5_solution_consistency",
        "V6_feasibility",
        "V7_objective",
        "V8_nondeterminism",
    ]
    assert len(runner.calls) == 2
    assert [call["seed"] for call in runner.calls] == [77, 77]
    assert {call["workdir"] for call in runner.calls} == {str(tmp_path)}


def test_runtime_audit_gate_boundary_keeps_execution_failures() -> None:
    assert not runtime_audit_issue_blocks_execution(
        {
            "error_category": "surface_runtime_contract_error",
            "missing_runtime_fields": ("policy_loaded",),
        }
    )
    assert not runtime_audit_issue_blocks_execution(
        {"error_category": "policy_runtime_telemetry_error"}
    )
    assert runtime_audit_issue_blocks_execution(
        {"error_category": "policy_runtime_error"}
    )
    assert runtime_audit_issue_blocks_execution(
        {"error_category": "surface_runtime_fallback"}
    )
    assert runtime_audit_issue_blocks_execution(
        {
            "error_category": "surface_runtime_contract_error",
            "detail": "selected research surface is not declared",
        }
    )
