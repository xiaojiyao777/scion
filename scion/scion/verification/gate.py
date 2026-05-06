"""VerificationGate: fail-fast orchestrator for all V1–V9 checks.

Checks (in order):
  V1_syntax                light   AST parse of patch code
  V2_interface             light   Operator subclass + execute signature
  V3_unit_tests            light   pytest unit tests in candidate workspace
  V4_regression_tests      light   pytest regression/solver tests in candidate workspace
  V5_solution_consistency  heavy   solver output assignment/vehicle integrity (W11)
  V6_feasibility           heavy   oracle.check_feasibility on canary run
  V7_objective             heavy   oracle.recompute_objective matches solver output
  V8_nondeterminism        heavy   two identical-seed runs produce identical output
  V9_perf_guard            heavy   candidate ≤ champion × 5 wall-clock

V5 and V8 are separate concerns:
  - V5_solution_consistency: does the solver output have consistent assignment / vehicle_ids? (data integrity)
  - V8_nondeterminism: is the solver deterministic? (uuid, set iteration, entropy)

Runtime checks (V5–V9) are skipped when:
  - runner is None, OR
  - problem_spec is None, OR
  - problem_spec.canary_case_path is empty
unless strict_runtime_checks=True, in which case missing runtime verification
    configuration fails closed. Production callers can also set
    require_adapter_for_runtime=True so V5-V9 never fall back to legacy
    direct-oracle reconstruction.

Test checks (V3, V4) are skipped when runner is None or no test file is found.
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING, List, Optional

from scion.config.problem import ProblemSpec
from scion.core.models import CheckResult, PatchProposal, VerificationResult
from scion.runtime.runner import Runner
from scion.verification.syntax import check_syntax
from scion.verification.interface import check_interface
from scion.verification.tests import check_unit_tests, check_regression_tests
from scion.verification.feasibility import resolve_problem_path
from scion.verification.state_mutation import check_state_mutation
from scion.verification.feasibility import check_feasibility
from scion.verification.objective import check_objective
from scion.verification.nondeterminism import check_nondeterminism
from scion.verification.perf_guard import check_perf

if TYPE_CHECKING:
    from scion.problem.contracts import ProblemAdapter


class VerificationGate:
    """Full Verification Gate — runs V1–V9 checks in fail-fast order.

    Args:
        problem_spec: ProblemSpec with canary_case_path, oracle_path, root_dir.
        runner:       Runner for executing the solver in subprocesses.
        adapter:      Optional ProblemAdapter; when provided, V6/V7 use adapter
                      instead of direct oracle imports.

    When problem_spec is None or runner is None (e.g., in unit tests), runtime
    checks V3–V9 are automatically skipped and return passed=True.
    """

    def __init__(
        self,
        problem_spec: Optional[ProblemSpec] = None,
        runner: Optional[Runner] = None,
        metrics_dir: Optional[str] = None,
        *,
        adapter: Optional[ProblemAdapter] = None,
        strict_runtime_checks: bool = False,
        require_adapter_for_runtime: bool = False,
        operator_execute_signature: str | None = None,
        max_runtime_ratio: float | None = None,
    ) -> None:
        self._spec = problem_spec
        self._runner = runner
        self._metrics_dir = metrics_dir
        self._adapter = adapter
        self._strict_runtime_checks = strict_runtime_checks
        self._require_adapter_for_runtime = require_adapter_for_runtime
        self._operator_execute_signature = operator_execute_signature
        self._max_runtime_ratio = max_runtime_ratio

    def run(
        self,
        candidate_workspace: str,
        champion_workspace: str,
        patch: PatchProposal,
        *,
        selected_surface: str | None = None,
        hypothesis: object | None = None,
    ) -> VerificationResult:
        """Execute all checks in fail-fast order; return VerificationResult.

        Light checks (V1, V2): LLM may attempt to fix these.
        Heavy checks (V3–V9): not fixable; branch is abandoned or blacklisted.
        """
        checks: List[CheckResult] = []
        surface_name = _selected_surface_name(
            selected_surface=selected_surface,
            hypothesis=hypothesis,
        )

        # --- V1: syntax (light) ---
        # V1_syntax: AST parse of patch code
        r = check_syntax(patch)
        checks.append(r)
        if not r.passed:
            return _fail(checks, r)

        # --- V2: interface (light) ---
        # V2_interface: Operator subclass + execute signature
        r = check_interface(
            patch,
            candidate_workspace,
            operator_execute_signature=self._operator_execute_signature,
        )
        checks.append(r)
        if not r.passed:
            return _fail(checks, r)

        # --- V3: unit tests (light) ---
        if self._runner is not None and self._spec is not None:
            r = check_unit_tests(self._spec, self._runner, candidate_workspace)
            checks.append(r)
            if not r.passed:
                return _fail(checks, r)

        # --- V4: regression tests (light) ---
        if self._runner is not None and self._spec is not None:
            r = check_regression_tests(self._spec, self._runner, candidate_workspace)
            checks.append(r)
            if not r.passed:
                return _fail(checks, r)

        # --- Runtime checks (skipped when runner/spec unavailable unless strict) ---
        if self._runner is None or self._spec is None:
            if self._strict_runtime_checks:
                r = _runtime_config_failure("runner and problem_spec are required")
                checks.append(r)
                return _fail(checks, r)
            return VerificationResult(passed=True, checks=tuple(checks))

        if self._strict_runtime_checks:
            r = _validate_runtime_config(
                self._spec,
                champion_workspace,
                adapter=self._adapter,
                require_adapter_for_runtime=self._require_adapter_for_runtime,
            )
            if r is not None:
                checks.append(r)
                return _fail(checks, r)

        # --- V5: state_mutation (heavy) ---
        # V5_solution_consistency: solution consistency after solver run.
        # NOTE: Current implementation is a proxy consistency check (not a true
        # input-mutation harness). Rename target: V5_solution_consistency in v0.3.
        r = check_state_mutation(
            self._spec,
            self._runner,
            candidate_workspace,
            adapter=self._adapter,
            selected_surface=surface_name,
        )
        checks.append(r)
        if not r.passed:
            return _fail(checks, r)

        # --- V6: feasibility (heavy) ---
        r = check_feasibility(
            self._spec,
            self._runner,
            candidate_workspace,
            adapter=self._adapter,
            selected_surface=surface_name,
        )
        checks.append(r)
        if not r.passed:
            return _fail(checks, r)

        # --- V7: objective (heavy) ---
        r = check_objective(
            self._spec,
            self._runner,
            candidate_workspace,
            adapter=self._adapter,
            selected_surface=surface_name,
        )
        checks.append(r)
        if not r.passed:
            return _fail(checks, r)

        # --- V8: nondeterminism (heavy) ---
        # V8_nondeterminism: two identical-seed runs must produce identical output.
        # This is the authoritative determinism check (replaces deprecated state_leak.py).
        r = check_nondeterminism(
            self._spec,
            self._runner,
            candidate_workspace,
            metrics_dir=self._metrics_dir,
            selected_surface=surface_name,
        )
        checks.append(r)
        if not r.passed:
            return _fail(checks, r)

        # --- V9: perf_guard (heavy) ---
        r = check_perf(
            self._spec,
            self._runner,
            candidate_workspace,
            champion_workspace,
            max_slowdown=self._max_runtime_ratio or 5.0,
            selected_surface=surface_name,
        )
        checks.append(r)
        if not r.passed:
            return _fail(checks, r)

        return VerificationResult(passed=True, checks=tuple(checks))


def _fail(checks: List[CheckResult], failed: CheckResult) -> VerificationResult:
    return VerificationResult(
        passed=False,
        checks=tuple(checks),
        failure_severity=failed.severity,
        first_failure=failed.name,
    )


def _validate_runtime_config(
    problem_spec: ProblemSpec,
    champion_workspace: str,
    *,
    adapter: ProblemAdapter | None = None,
    require_adapter_for_runtime: bool = False,
) -> CheckResult | None:
    if require_adapter_for_runtime and adapter is None:
        return _runtime_config_failure("problem adapter is required for runtime verification")
    canary = resolve_problem_path(problem_spec, problem_spec.canary_case_path)
    if not canary:
        return _runtime_config_failure("canary_case_path is required")
    if not os.path.isfile(canary):
        return _runtime_config_failure(f"canary file not found: {canary}")
    if not champion_workspace or not os.path.isdir(champion_workspace):
        return _runtime_config_failure("champion workspace is required")
    return None


def _runtime_config_failure(detail: str) -> CheckResult:
    return CheckResult(
        name="V_runtime_config",
        passed=False,
        severity="heavy",
        detail=detail,
        elapsed_ms=0,
    )


def _selected_surface_name(
    *,
    selected_surface: str | None,
    hypothesis: object | None,
) -> str | None:
    if selected_surface is not None:
        surface = selected_surface.strip()
        return surface or None
    if hypothesis is None:
        return None
    surface = getattr(hypothesis, "change_locus", None)
    if not isinstance(surface, str):
        return None
    surface = surface.strip()
    return surface or None
