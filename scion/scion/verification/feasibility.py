"""Feasibility check: run solver on canary case, verify output via oracle.check_feasibility."""
from __future__ import annotations

import json
import os
import sys
import time
from typing import TYPE_CHECKING, Any, Optional

from scion.config.problem import ProblemSpec
from scion.core.models import CheckResult
from scion.runtime.runner import Runner

if TYPE_CHECKING:
    from scion.problem.contracts import ProblemAdapter


def check_feasibility(
    problem_spec: ProblemSpec,
    runner: Runner,
    candidate_workspace: str,
    *,
    adapter: Optional[ProblemAdapter] = None,
) -> CheckResult:
    """V3_feasibility: solver output must pass oracle.check_feasibility on the canary case."""
    t0 = time.monotonic_ns()

    canary = problem_spec.canary_case_path
    if not canary:
        return _cr(True, "heavy", "skipped: no canary_case_path configured", t0)

    if not os.path.isfile(canary):
        return _cr(True, "heavy", f"skipped: canary file not found: {canary}", t0)

    # Run solver in candidate workspace with canary case.
    try:
        result = runner.run_solver(
            workdir=candidate_workspace,
            instance_path=canary,
            seed=42,
            time_limit_sec=30,
            registry_path=_registry_path(candidate_workspace),
        )
    except Exception as exc:
        return _cr(False, "heavy", f"runner error: {exc}", t0)

    if not result.success:
        return _cr(
            False, "heavy",
            f"solver failed (exit={result.exit_code}, "
            f"category={result.error_category}): {result.stderr[:200]}",
            t0,
        )

    if result.output_path is None:
        return _cr(False, "heavy", "solver produced no output file", t0)

    # Load output JSON.
    try:
        with open(result.output_path, encoding="utf-8") as f:
            raw = json.load(f)
    except Exception as exc:
        return _cr(False, "heavy", f"cannot read solver output: {exc}", t0)

    # --- Adapter-based path (v0.3+) ---
    if adapter is not None:
        return _check_via_adapter(adapter, raw, canary, t0)

    # --- Legacy path (direct oracle import) ---
    oracle_dir = os.path.dirname(os.path.abspath(
        os.path.join(problem_spec.root_dir, problem_spec.oracle_path)
    ))
    try:
        solution, instance = _load_solution_and_instance(raw, canary, oracle_dir)
    except Exception as exc:
        return _cr(False, "heavy", f"cannot reconstruct solution/instance: {exc}", t0)

    try:
        oracle = _import_oracle(oracle_dir)
        feas = oracle.check_feasibility(solution, instance, phase=1)
    except Exception as exc:
        return _cr(False, "heavy", f"oracle.check_feasibility error: {exc}", t0)

    if feas.is_feasible:
        return _cr(True, "heavy", "feasibility ok", t0)
    return _cr(
        False, "heavy",
        f"infeasible: {'; '.join(feas.violations[:3])}",
        t0,
    )


def _check_via_adapter(
    adapter: ProblemAdapter, raw: dict, canary: str, t0: int,
) -> CheckResult:
    try:
        instance = adapter.load_instance(canary)
        artifact = adapter.deserialize_solver_output(raw, instance)
    except Exception as exc:
        return _cr(False, "heavy", f"adapter deserialize error: {exc}", t0)

    try:
        consistency = adapter.check_solution_consistency(artifact, instance)
        if not consistency.passed:
            return _cr(
                False, "heavy",
                f"consistency failed: {'; '.join(consistency.reasons[:3])}",
                t0,
            )
    except Exception as exc:
        return _cr(False, "heavy", f"consistency check error: {exc}", t0)

    try:
        feas = adapter.check_feasibility(artifact, instance)
    except Exception as exc:
        return _cr(False, "heavy", f"adapter.check_feasibility error: {exc}", t0)

    if feas.passed:
        return _cr(True, "heavy", "feasibility ok", t0)
    return _cr(
        False, "heavy",
        f"infeasible: {'; '.join(feas.reasons[:3])}",
        t0,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _registry_path(workspace: str) -> str:
    """Return registry path if it exists, else an empty string (solver uses defaults)."""
    rp = os.path.join(workspace, "registry.yaml")
    return rp if os.path.isfile(rp) else ""


def _import_oracle(oracle_dir: str) -> Any:
    """Import oracle module from oracle_dir, temporarily adjusting sys.path."""
    import importlib.util
    oracle_path = os.path.join(oracle_dir, "oracle.py")
    if not os.path.isfile(oracle_path):
        raise FileNotFoundError(f"oracle.py not found at {oracle_path}")

    saved = list(sys.path)
    if oracle_dir not in sys.path:
        sys.path.insert(0, oracle_dir)
    try:
        spec = importlib.util.spec_from_file_location("_scion_oracle", oracle_path)
        mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        sys.modules["_scion_oracle"] = mod  # Required for dataclass introspection
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return mod
    finally:
        sys.path[:] = saved


def _load_solution_and_instance(raw: dict, instance_path: str, oracle_dir: str):
    """Reconstruct Solution and Instance from solver output JSON and instance file."""
    import importlib.util

    saved = list(sys.path)
    if oracle_dir not in sys.path:
        sys.path.insert(0, oracle_dir)
    try:
        models_path = os.path.join(oracle_dir, "models.py")
        if not os.path.isfile(models_path):
            raise FileNotFoundError(f"models.py not found at {models_path}")

        spec = importlib.util.spec_from_file_location("_scion_models", models_path)
        models = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        sys.modules["_scion_models"] = models  # Required for dataclass introspection
        spec.loader.exec_module(models)  # type: ignore[union-attr]

        # Reconstruct vehicles.
        vehicles = {}
        for vid, vdata in raw.get("vehicles", {}).items():
            vehicles[vid] = models.Vehicle(
                vehicle_id=vdata["vehicle_id"],
                vehicle_type=vdata["vehicle_type"],
                region=vdata["region"],
                order_ids=list(vdata["order_ids"]),
            )
        solution = models.Solution(
            vehicles=vehicles,
            assignment=dict(raw.get("assignment", {})),
        )

        # Load instance from JSON.
        with open(instance_path, encoding="utf-8") as f:
            idata = json.load(f)
        orders = {}
        for o in idata["orders"]:
            spu_list = [
                models.SPU(packing_type=s["packing_type"], quantity=s["quantity"])
                for s in o["spu_list"]
            ]
            order = models.Order(
                order_id=o["order_id"],
                vehicle_category=o["vehicle_category"],
                vehicle_subcategory=o["vehicle_subcategory"],
                urgent=o["urgent"],
                hazard_flag=o["hazard_flag"],
                hazard_quantity=o["hazard_quantity"],
                pickup_name=o["pickup_name"],
                pickup_province=o["pickup_province"],
                pickup_city=o["pickup_city"],
                declaration_amount=o["declaration_amount"],
                lsp=o["lsp"],
                ship_method=o["ship_method"],
                destination_country=o["destination_country"],
                spu_list=spu_list,
                locked_vehicle_id=o.get("locked_vehicle_id"),
            )
            orders[order.order_id] = order
        amount_limits = idata.get("amount_limits", {})
        instance = models.Instance(
            orders=orders,
            amount_limits=amount_limits,
            phase=1,
        )
        return solution, instance
    finally:
        sys.path[:] = saved


def _cr(passed: bool, severity: str, detail: str, t0: int) -> CheckResult:
    elapsed = int((time.monotonic_ns() - t0) / 1_000_000)
    return CheckResult(
        name="V3_feasibility",
        passed=passed,
        severity=severity,  # type: ignore[arg-type]
        detail=detail,
        elapsed_ms=elapsed,
    )
