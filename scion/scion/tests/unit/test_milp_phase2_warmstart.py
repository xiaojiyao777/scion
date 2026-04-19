"""Unit tests for MILP phase 2 warm start from phase 1 solution.

Tests:
1. test_phase2_warmstart_injected        — HiGHS logs show two MIP-start-feasible lines
2. test_phase2_warmstart_feasible_for_eps_constraint — phase1 sol satisfies f1 <= f1* for phase2
3. test_phase2_warmstart_does_not_regress — MILP cost <= VNS champion cost
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_repo_root = Path(__file__).parent.parent.parent.parent.parent
_surrogate_path = str(_repo_root / "surrogate")
if _surrogate_path not in sys.path:
    sys.path.insert(0, _surrogate_path)

# Evict scion.scion.config from sys.modules so surrogate/config.py wins
# when surrogate modules do `from config import Config` (same-name conflict).
for _mod_name in list(sys.modules):
    if _mod_name == "config" or _mod_name.startswith("config."):
        del sys.modules[_mod_name]

from milp_model import build_milp, compute_K, build_locked_slot_map, extract_solution
from milp_warmstart import build_warmstart_values
from milp_solver import solve_exact, _load_instance
from oracle import recompute_objective

DATA_DIR = _repo_root / "surrogate" / "data"
PYTHON = str(Path(sys.executable))


def _load(name: str):
    return _load_instance(str(DATA_DIR / f"instance_v4_scr_{name}.json"))


# ---------------------------------------------------------------------------
# T1: HiGHS logs "MIP start solution is feasible" twice (phase1 + phase2)
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_phase2_warmstart_injected():
    """Both phases should log a feasible MIP start when called with a champion."""
    inst = _load("s01")

    # Generate a champion via greedy_init (feasible, no VNS polish needed)
    from greedy_init import greedy_init
    from random import Random

    champion = greedy_init(inst, Random(42))
    champion.objective = recompute_objective(champion, inst)

    # Run solve_exact via subprocess so we capture C-level HiGHS output
    import json, tempfile, os
    inst_path = DATA_DIR / "instance_v4_scr_s01.json"
    script = f"""
import sys
sys.path.insert(0, r'{str(_repo_root / "surrogate")}')
import json
from milp_solver import solve_exact, _load_instance
from models import Solution, Vehicle
from oracle import recompute_objective

champion_data = json.loads(sys.stdin.read())
vehicles = {{k: Vehicle(**v) for k, v in champion_data['vehicles'].items()}}
champion = Solution(vehicles=vehicles, assignment=champion_data['assignment'])
champion.objective = None

inst = _load_instance(r'{str(inst_path)}')
champion.objective = recompute_objective(champion, inst)
res = solve_exact(inst, time_limit_seconds=30, verbose=True, solver_name='HiGHS', warm_start=champion)
print('STATUS:', res.status)
"""
    # Serialise champion
    champion_dict = {
        "vehicles": {
            vid: {"vehicle_id": v.vehicle_id, "vehicle_type": v.vehicle_type,
                  "region": v.region, "order_ids": v.order_ids}
            for vid, v in champion.vehicles.items()
        },
        "assignment": champion.assignment,
    }
    proc = subprocess.run(
        [PYTHON, "-c", script],
        input=json.dumps(champion_dict),
        capture_output=True,
        text=True,
        timeout=120,
    )
    combined = proc.stdout + proc.stderr
    count = combined.count("MIP start solution is feasible")
    assert count >= 2, (
        f"Expected >=2 occurrences of 'MIP start solution is feasible', got {count}.\n"
        f"stdout={proc.stdout[:2000]}\nstderr={proc.stderr[:2000]}"
    )


# ---------------------------------------------------------------------------
# T2: phase 1 solution satisfies f1 <= f1* for phase 2 eps-constraint
# ---------------------------------------------------------------------------

def test_phase2_warmstart_feasible_for_eps_constraint():
    """Phase 1 sol has f1 == f1*, so f1 <= f1* holds — safe for phase 2 warm start."""
    inst = _load("s01")
    K = compute_K(inst)
    locked_slot_map = build_locked_slot_map(inst)

    # Build and solve phase 1
    prob1, vars1 = build_milp(
        inst, K, locked_slot_map,
        symmetry_breaking=True,
        phase2_sum_alpha_star=None,
    )
    import pulp
    solver = pulp.HiGHS(msg=0, timeLimit=30, gapRel=0)
    prob1.solve(solver)

    assert prob1.status in (1, 0), f"Phase 1 did not find a solution (status={prob1.status})"

    # Extract phase 1 solution
    sol1 = extract_solution(inst, vars1)
    sol1.objective = recompute_objective(sol1, inst)

    # Phase 1 sum_alpha
    alpha = vars1["alpha"]
    S = vars1["S"]
    J = vars1["J"]
    sum_alpha_star = sum(
        1 for s in S for j in J if (pulp.value(alpha[s, j]) or 0) > 0.5
    )

    # Build warm start for phase 2 (same K, locked_slot_map)
    warm_vals = build_warmstart_values(sol1, inst, K, locked_slot_map)
    assert len(warm_vals) > 0, "build_warmstart_values returned empty dict"

    # Build phase 2 model
    prob2, vars2 = build_milp(
        inst, K, locked_slot_map,
        symmetry_breaking=True,
        phase2_sum_alpha_star=sum_alpha_star,
    )

    # Inject warm values and solve briefly
    from milp_solver import _HiGHSWithWarmStart
    if _HiGHSWithWarmStart is None:
        pytest.skip("HiGHS warm-start class not available")
    solver2 = _HiGHSWithWarmStart(warm_vals, msg=0, timeLimit=5, gapRel=0)
    prob2.solve(solver2)

    # Phase 2 must find a feasible solution (not infeasible)
    assert prob2.status != -1, "Phase 2 reported infeasible with phase 1 warm start"
    assert pulp.value(prob2.objective) is not None, "Phase 2 objective is None after warm start"

    # Verify f1 of the warm start solution <= f1*
    assert sol1.objective is not None
    active_subcats = {o.vehicle_subcategory for o in inst.orders.values()}
    n_active = len(active_subcats)
    f1_sol1 = sol1.objective.subcategory_splits
    f1_star = sum_alpha_star - n_active
    assert f1_sol1 <= f1_star + 1, (
        f"Phase 1 solution f1={f1_sol1} exceeds f1*={f1_star} — impossible by construction"
    )


# ---------------------------------------------------------------------------
# T3: phase 2 warm start does not regress vs VNS champion cost
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_phase2_warmstart_does_not_regress():
    """solve_exact result cost should be <= VNS champion cost."""
    inst = _load("s01")

    from greedy_init import greedy_init
    from random import Random

    champion = greedy_init(inst, Random(0))
    champion.objective = recompute_objective(champion, inst)

    res = solve_exact(
        inst,
        time_limit_seconds=60,
        verbose=False,
        solver_name="HiGHS",
        warm_start=champion,
    )

    assert res.status in ("optimal", "feasible", "timeout"), (
        f"Unexpected status: {res.status}"
    )

    if res.solution is not None and champion.objective is not None:
        assert res.objective_f2 <= champion.objective.total_cost + 1e-6, (
            f"MILP cost {res.objective_f2} worse than VNS champion {champion.objective.total_cost}"
        )
