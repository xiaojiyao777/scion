"""VerificationGate: fail-fast orchestrator for all V1–V8 checks.

Checks (in order):
  V1_syntax           light   AST parse of patch code
  V2_interface        light   Operator subclass + execute signature
  V3_unit_tests       light   pytest unit tests in candidate workspace
  V4_regression_tests light   pytest regression/solver tests in candidate workspace
  V5_feasibility      heavy   oracle.check_feasibility on canary run
  V6_objective        heavy   oracle.recompute_objective matches solver output
  V7_state_leak       heavy   two identical-seed runs produce identical output
  V8_perf_guard       heavy   candidate ≤ champion × 5 wall-clock

Runtime checks (V5–V8) are skipped when:
  - runner is None, OR
  - problem_spec is None, OR
  - problem_spec.canary_case_path is empty

Test checks (V3, V4) are skipped when runner is None or no test file is found.
"""
from __future__ import annotations

from typing import List, Optional

from scion.config.problem import ProblemSpec
from scion.core.models import CheckResult, PatchProposal, VerificationResult
from scion.runtime.runner import Runner
from scion.verification.syntax import check_syntax
from scion.verification.interface import check_interface
from scion.verification.tests import check_unit_tests, check_regression_tests
from scion.verification.feasibility import check_feasibility
from scion.verification.objective import check_objective
from scion.verification.state_leak import check_state_leak
from scion.verification.perf_guard import check_perf


class VerificationGate:
    """Full Verification Gate — runs V1–V6 checks in fail-fast order.

    Args:
        problem_spec: ProblemSpec with canary_case_path, oracle_path, root_dir.
        runner:       Runner for executing the solver in subprocesses.

    When problem_spec is None or runner is None (e.g., in unit tests), runtime
    checks V3–V6 are automatically skipped and return passed=True.
    """

    def __init__(
        self,
        problem_spec: Optional[ProblemSpec] = None,
        runner: Optional[Runner] = None,
    ) -> None:
        self._spec = problem_spec
        self._runner = runner

    def run(
        self,
        candidate_workspace: str,
        champion_workspace: str,
        patch: PatchProposal,
    ) -> VerificationResult:
        """Execute all checks in fail-fast order; return VerificationResult.

        Light checks (V1, V2): LLM may attempt to fix these.
        Heavy checks (V3–V6): not fixable; branch is abandoned or blacklisted.
        """
        checks: List[CheckResult] = []

        # --- V1: syntax (light) ---
        r = check_syntax(patch)
        checks.append(r)
        if not r.passed:
            return _fail(checks, r)

        # --- V2: interface (light) ---
        r = check_interface(patch, candidate_workspace)
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

        # --- Runtime checks (skipped when runner/spec unavailable) ---
        if self._runner is None or self._spec is None:
            return VerificationResult(passed=True, checks=tuple(checks))

        # --- V5: feasibility (heavy) ---
        r = check_feasibility(self._spec, self._runner, candidate_workspace)
        checks.append(r)
        if not r.passed:
            return _fail(checks, r)

        # --- V6: objective (heavy) ---
        r = check_objective(self._spec, self._runner, candidate_workspace)
        checks.append(r)
        if not r.passed:
            return _fail(checks, r)

        # --- V7: state_leak (heavy) ---
        r = check_state_leak(self._spec, self._runner, candidate_workspace)
        checks.append(r)
        if not r.passed:
            return _fail(checks, r)

        # --- V8: perf_guard (heavy) ---
        r = check_perf(
            self._spec, self._runner, candidate_workspace, champion_workspace
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
