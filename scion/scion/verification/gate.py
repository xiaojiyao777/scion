"""VerificationGate: fail-fast orchestrator for all V1–V9 checks.

Checks (in order):
  V1_syntax                light   AST parse of patch code
  V2_interface             light   Operator subclass + execute signature
  V3_unit_tests            light   pytest unit tests in candidate workspace
  V4_regression_tests      light   pytest regression/solver tests in candidate workspace
  V5_solution_consistency  heavy   solver output consistency hook (W11)
  V6_feasibility           heavy   oracle.check_feasibility on canary run
  V7_objective             heavy   oracle.recompute_objective matches solver output
  V8_nondeterminism        heavy   two identical-seed runs produce identical output
  V9_perf_guard            heavy   candidate ≤ champion × 5 wall-clock

V5 and V8 are separate concerns:
  - V5_solution_consistency: does the solver output satisfy declared consistency checks?
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
from dataclasses import replace
from typing import TYPE_CHECKING, List, Optional

from scion.config.problem import ProblemSpec
from scion.core.models import CheckResult, PatchProposal, VerificationResult
from scion.runtime.runner import Runner
from scion.verification.syntax import check_syntax
from scion.verification.interface import check_interface
from scion.verification.tests import (
    check_regression_tests,
    check_unit_tests,
    verification_pytest_preflight_reasons,
)
from scion.verification.feasibility import resolve_problem_path
from scion.verification.state_mutation import check_state_mutation
from scion.verification.feasibility import check_feasibility
from scion.verification.objective import check_objective
from scion.verification.nondeterminism import check_nondeterminism
from scion.verification.perf_guard import check_perf
from scion.verification.requirements import requires_adapter_for_runtime

if TYPE_CHECKING:
    from scion.problem.contracts import ProblemAdapter


_DEFAULT_RUNTIME_TIME_LIMIT_SEC = 30


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
        allow_adapter_runtime_fallback: bool = False,
        operator_execute_signature: str | None = None,
        max_runtime_ratio: float | None = None,
        runtime_time_limit_sec: int | float | None = None,
    ) -> None:
        self._spec = problem_spec
        self._runner = runner
        self._metrics_dir = metrics_dir
        self._adapter = adapter
        spec_requires_adapter = (
            False
            if allow_adapter_runtime_fallback
            else requires_adapter_for_runtime(problem_spec)
        )
        self._strict_runtime_checks = strict_runtime_checks or spec_requires_adapter
        self._require_adapter_for_runtime = (
            require_adapter_for_runtime
            or spec_requires_adapter
        )
        self._operator_execute_signature = operator_execute_signature
        self._max_runtime_ratio = max_runtime_ratio
        self._runtime_time_limit_sec = _positive_int_or_default(
            runtime_time_limit_sec,
            _DEFAULT_RUNTIME_TIME_LIMIT_SEC,
        )

    def bind_runtime_policy(
        self,
        *,
        max_runtime_ratio: float | None = None,
        runtime_time_limit_sec: int | float | None = None,
    ) -> None:
        """Bind protocol-derived runtime policy to an accepted custom gate.

        Production composition may receive an already-built ``VerificationGate``.
        The gate is still campaign-owned at that point, so binding the protocol
        runtime policy keeps V5-V9 coherent with the evidence harness instead
        of falling back to constructor defaults.
        """

        if max_runtime_ratio is not None:
            self._max_runtime_ratio = max_runtime_ratio
        if runtime_time_limit_sec is not None:
            self._runtime_time_limit_sec = _positive_int_or_default(
                runtime_time_limit_sec,
                self._runtime_time_limit_sec,
            )

    def run_preflight(self) -> None:
        """Fail fast on verification-runner dependencies before proposal work."""

        if self._runner is None or self._spec is None:
            return
        reasons = verification_pytest_preflight_reasons(self._spec)
        if not reasons:
            return
        from scion.problem.preflight import RuntimeDependencyPreflightError

        raise RuntimeDependencyPreflightError(reasons)

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
            problem_spec=self._spec,
            selected_surface=surface_name,
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
            require_adapter_for_runtime=self._require_adapter_for_runtime,
            runtime_time_limit_sec=self._runtime_time_limit_sec,
        )
        r = _with_runtime_budget_metadata(r, self._runtime_time_limit_sec)
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
            require_adapter_for_runtime=self._require_adapter_for_runtime,
            runtime_time_limit_sec=self._runtime_time_limit_sec,
        )
        r = _with_runtime_budget_metadata(r, self._runtime_time_limit_sec)
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
            require_adapter_for_runtime=self._require_adapter_for_runtime,
            runtime_time_limit_sec=self._runtime_time_limit_sec,
        )
        r = _with_runtime_budget_metadata(r, self._runtime_time_limit_sec)
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
            adapter=self._adapter,
            require_adapter_for_runtime=self._require_adapter_for_runtime,
            runtime_time_limit_sec=self._runtime_time_limit_sec,
        )
        r = _with_runtime_budget_metadata(r, self._runtime_time_limit_sec)
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
            timeout_sec=self._runtime_time_limit_sec,
            strict_runtime_checks=self._strict_runtime_checks,
        )
        r = _with_runtime_budget_metadata(r, self._runtime_time_limit_sec)
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
    canary = resolve_problem_path(problem_spec, problem_spec.canary_case_path)
    if not canary:
        return _runtime_config_failure("canary_case_path is required")
    if not os.path.isfile(canary):
        return _runtime_config_failure(f"canary file not found: {canary}")
    if not champion_workspace or not os.path.isdir(champion_workspace):
        return _runtime_config_failure("champion workspace is required")
    if require_adapter_for_runtime and adapter is None:
        return _runtime_config_failure(
            "problem adapter is required for runtime verification; "
            "legacy runtime fallback disabled"
        )
    return None


def _runtime_config_failure(detail: str) -> CheckResult:
    return CheckResult(
        name="V_runtime_config",
        passed=False,
        severity="heavy",
        detail=detail,
        elapsed_ms=0,
    )


def _positive_int_or_default(value: int | float | None, default: int) -> int:
    if isinstance(value, bool) or value is None:
        return default
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return default
    if numeric <= 0:
        return default
    return max(1, int(numeric))


def _with_runtime_budget_metadata(
    check: CheckResult,
    runtime_time_limit_sec: int,
) -> CheckResult:
    metadata = dict(check.metadata)
    metadata.setdefault("verification_time_limit_sec", runtime_time_limit_sec)
    metadata.setdefault("runtime_time_limit_source", "verification_gate")
    return replace(check, metadata=metadata)


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
