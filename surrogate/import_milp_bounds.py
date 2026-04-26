"""Convert CPLEX final result JSON files into the milp_bounds/ format
expected by WarehouseDeliveryAdapter.estimate_lower_bound().

Reads from: cplex-final-20260426/{production,synthetic}/instance_*.json
Writes to:  milp_bounds/<instance_stem>.json

Output format:
    {
        "subcategory_splits": <int>,   # milp_f1
        "total_cost": <int>,           # milp_f2
        "status": "optimal" | "feasible" | "timeout",
        "gap": <float|null>,           # phase2_gap if finite
        "solver_time_sec": <float>,
        "solver": "CPLEX",
        "milp_status": <raw solver status>,
        "milp_exact": <bool>,
        "milp_verified": <bool>
    }

Skipped: infeasible instances, instances with null f1/f2.
Non-exact feasible/timeout incumbents are retained as report-only references,
but downstream reporting must not treat them as exact optima.
"""
import json
import os
import glob
import math

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCE_PACKAGE = "cplex-final-20260426"
RESULTS_DIRS = [
    os.path.join(SCRIPT_DIR, SOURCE_PACKAGE, "production"),
    os.path.join(SCRIPT_DIR, SOURCE_PACKAGE, "synthetic"),
]
OUT_DIR = os.path.join(SCRIPT_DIR, "milp_bounds")

os.makedirs(OUT_DIR, exist_ok=True)

written = skipped_infeasible = skipped_null = 0


def _finite_or_none(value):
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


for d in RESULTS_DIRS:
    for path in sorted(glob.glob(os.path.join(d, "instance_*.json"))):
        with open(path) as f:
            data = json.load(f)

        status = data.get("milp_status", "unknown")
        if status == "infeasible":
            skipped_infeasible += 1
            continue

        f1 = data.get("milp_f1")
        f2 = data.get("milp_f2")
        if f1 is None or f2 is None:
            skipped_null += 1
            continue

        if data.get("milp_exact"):
            compact_status = "optimal"
        elif status == "timeout":
            compact_status = "timeout"
        else:
            compact_status = "feasible"

        out = {
            "subcategory_splits": int(f1),
            "total_cost": int(f2),
            "status": compact_status,
            "gap": _finite_or_none(data.get("phase2_gap")),
            "solver_time_sec": data.get("elapsed_s"),
            "solver": data.get("solver", "CPLEX"),
            "provider": data.get("provider", "milp"),
            "source_package": SOURCE_PACKAGE,
            "source_result": os.path.relpath(path, SCRIPT_DIR),
            "milp_status": status,
            "milp_exact": bool(data.get("milp_exact")),
            "milp_verified": bool(data.get("milp_verified")),
            "oracle_feasible": data.get("oracle_feasible"),
            "n_orders": data.get("n_orders"),
            "scale": data.get("scale"),
        }

        stem = os.path.splitext(os.path.basename(path))[0]
        out_path = os.path.join(OUT_DIR, f"{stem}.json")
        with open(out_path, "w") as f:
            json.dump(out, f, indent=2)
        written += 1

print(f"Written: {written}  |  Skipped infeasible: {skipped_infeasible}  |  Skipped null f1/f2: {skipped_null}")
print(f"Output dir: {OUT_DIR}")
