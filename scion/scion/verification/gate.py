"""VerificationGate: fail-fast orchestrator for V1–V8 correctness checks.

Checks (in order):
  V1_syntax                light   AST parse of patch code
  V1b_undefined_names      light   unresolved-name scan of candidate modules
  V2_interface             light   Operator subclass + execute signature
  V3_unit_tests            light   pytest unit tests in candidate workspace
  V4_regression_tests      light   pytest regression/solver tests in candidate workspace
  V5_solution_consistency  heavy   solver output consistency hook (W11)
  V6_feasibility           heavy   adapter feasibility check on canary run
  V7_objective             heavy   adapter recomputation matches solver output
  V8_nondeterminism        heavy   two identical-seed runs produce identical output

V5 and V8 are separate concerns:
  - V5_solution_consistency: does the solver output satisfy declared consistency checks?
  - V8_nondeterminism: is the solver deterministic? (uuid, set iteration, entropy)

``VerificationGate()`` is a structural/static-check shell. Runtime and
problem-aware gates are composed from one ``ProblemAdapter``; its ``spec`` and
operator interface are the only public source of problem semantics.

Test checks (V3, V4) are skipped when runner is None or no test file is found.
"""

from __future__ import annotations

import os
from dataclasses import replace
from typing import TYPE_CHECKING

from scion.config.problem import ProblemSpec
from scion.core.models import CheckResult, PatchProposal, VerificationResult
from scion.runtime.runner import Runner
from scion.verification.candidate_canary import run_candidate_canary
from scion.verification.feasibility import (
    _registry_path,
    check_feasibility,
    resolve_problem_path,
)
from scion.verification.interface import check_interface
from scion.verification.nondeterminism import check_nondeterminism
from scion.verification.objective import check_objective
from scion.verification.requirements import requires_adapter_for_runtime
from scion.verification.state_mutation import check_state_mutation
from scion.verification.syntax import check_syntax
from scion.verification.tests import (
    check_regression_tests,
    check_unit_tests,
    verification_pytest_preflight_reasons,
)
from scion.verification.undefined_names import check_undefined_names

if TYPE_CHECKING:
    from scion.problem.contracts import ProblemAdapter


_DEFAULT_RUNTIME_TIME_LIMIT_SEC = 30


class VerificationGate:
    """Full Verification Gate — runs V1–V8 checks in fail-fast order.

    Args:
        runner:       Runner for executing the solver in subprocesses.
        adapter:      ProblemAdapter owning the spec and execute signature.

    ``VerificationGate()`` may be used as a problem-free structural shell. A
    gate with a runner or strict runtime checks must receive an adapter.
    """

    def __init__(
        self,
        runner: Runner | None = None,
        metrics_dir: str | None = None,
        *,
        adapter: ProblemAdapter | None = None,
        strict_runtime_checks: bool = False,
        max_runtime_ratio: float | None = None,
        runtime_time_limit_sec: float | None = None,
    ) -> None:
        if adapter is None and (runner is not None or strict_runtime_checks):
            raise TypeError(
                "VerificationGate with a runner or strict runtime checks requires "
                "a problem adapter"
            )
        problem_spec = getattr(adapter, "spec", None)
        if adapter is not None and problem_spec is None:
            raise TypeError("problem adapter must expose its problem spec")
        self._spec = problem_spec
        self._runner = runner
        self._metrics_dir = metrics_dir
        self._adapter = adapter
        spec_requires_adapter = requires_adapter_for_runtime(problem_spec)
        self._strict_runtime_checks = strict_runtime_checks or spec_requires_adapter
        self._require_adapter_for_runtime = adapter is not None
        self._operator_execute_signature = _adapter_execute_signature(problem_spec)
        self._max_runtime_ratio = max_runtime_ratio
        self._runtime_time_limit_sec = _positive_int_or_default(
            runtime_time_limit_sec,
            _DEFAULT_RUNTIME_TIME_LIMIT_SEC,
        )

    def bind_runtime_policy(
        self,
        *,
        max_runtime_ratio: float | None = None,
        runtime_time_limit_sec: float | None = None,
    ) -> None:
        """Bind protocol-derived runtime policy to an accepted custom gate.

        Production composition may receive an already-built ``VerificationGate``.
        The gate is still campaign-owned at that point. Runtime time limits are
        shared by V5-V8; comparative slowdown policy belongs to Protocol.
        """

        if max_runtime_ratio is not None:
            self._max_runtime_ratio = max_runtime_ratio
        if runtime_time_limit_sec is not None:
            self._runtime_time_limit_sec = _positive_int_or_default(
                runtime_time_limit_sec,
                self._runtime_time_limit_sec,
            )

    def bind_problem_adapter(
        self,
        adapter: ProblemAdapter,
    ) -> None:
        """Bind correctness checks to the adapter-owned problem definition."""

        problem_spec = getattr(adapter, "spec", None)
        if problem_spec is None:
            raise TypeError("problem adapter must expose its problem spec")
        self._spec = problem_spec
        self._adapter = adapter
        self._strict_runtime_checks = True
        self._require_adapter_for_runtime = True
        self._operator_execute_signature = _adapter_execute_signature(problem_spec)

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

        Light checks (V1, V2) are static candidate checks.
        Heavy checks (V3–V8) execute correctness and runtime validation.
        """
        checks: list[CheckResult] = []
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

        # --- V1b: undefined names (light) ---
        # Python symtable-based scan of primary and additional module sources.
        r = check_undefined_names(patch)
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
                adapter=self._adapter,
                require_adapter_for_runtime=self._require_adapter_for_runtime,
            )
            if r is not None:
                checks.append(r)
                return _fail(checks, r)

        canary_path = resolve_problem_path(
            self._spec,
            self._spec.canary_case_path,
        )
        canary_execution = None
        if canary_path and os.path.isfile(canary_path):
            canary_execution = run_candidate_canary(
                self._runner,
                candidate_workspace=candidate_workspace,
                case_path=canary_path,
                registry_path=_registry_path(candidate_workspace),
                selected_surface=surface_name,
                runtime_time_limit_sec=self._runtime_time_limit_sec,
            )

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
            canary_execution=canary_execution,
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
            canary_execution=canary_execution,
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
            canary_execution=canary_execution,
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
            first_execution=canary_execution,
        )
        r = _with_runtime_budget_metadata(r, self._runtime_time_limit_sec)
        checks.append(r)
        if not r.passed:
            return _fail(checks, r)

        return VerificationResult(passed=True, checks=tuple(checks))


def _fail(checks: list[CheckResult], failed: CheckResult) -> VerificationResult:
    return VerificationResult(
        passed=False,
        checks=tuple(checks),
        failure_severity=failed.severity,
        first_failure=failed.name,
    )


def _validate_runtime_config(
    problem_spec: ProblemSpec,
    *,
    adapter: ProblemAdapter | None = None,
    require_adapter_for_runtime: bool = False,
) -> CheckResult | None:
    canary = resolve_problem_path(problem_spec, problem_spec.canary_case_path)
    if not canary:
        return _runtime_config_failure("canary_case_path is required")
    if not os.path.isfile(canary):
        return _runtime_config_failure(f"canary file not found: {canary}")
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


def _positive_int_or_default(value: float | None, default: int) -> int:
    if isinstance(value, bool) or value is None:
        return default
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return default
    if numeric <= 0:
        return default
    return max(1, int(numeric))


def _adapter_execute_signature(problem_spec: object) -> str | None:
    operator_interface = getattr(problem_spec, "operator_interface", None)
    value = getattr(operator_interface, "execute_signature", None)
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


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
