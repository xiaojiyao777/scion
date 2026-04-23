"""Convert sprint-f4-milp-results JSON files into the milp_bounds/ format
expected by WarehouseDeliveryAdapter.estimate_lower_bound().

Reads from: sprint-f4-milp-results/{production,synthetic}/instance_*.json
Writes to:  milp_bounds/<instance_stem>.json

Output format:
    {
        "subcategory_splits": <int>,   # milp_f1
        "total_cost": <int>,           # milp_f2
        "status": "optimal" | "feasible",
        "gap": <float>,                # phase2_gap
        "solver_time_sec": <float>
    }

Skipped: infeasible instances, instances with null f1/f2.
"""
import json
import os
import glob

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIRS = [
    os.path.join(SCRIPT_DIR, "sprint-f4-milp-results", "production"),
    os.path.join(SCRIPT_DIR, "sprint-f4-milp-results", "synthetic"),
]
OUT_DIR = os.path.join(SCRIPT_DIR, "milp_bounds")

os.makedirs(OUT_DIR, exist_ok=True)

written = skipped_infeasible = skipped_null = 0

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

        out = {
            "subcategory_splits": int(f1),
            "total_cost": int(f2),
            "status": "optimal" if data.get("milp_exact") else "feasible",
            "gap": data.get("phase2_gap") or 0.0,
            "solver_time_sec": data.get("elapsed_s"),
        }

        stem = os.path.splitext(os.path.basename(path))[0]
        out_path = os.path.join(OUT_DIR, f"{stem}.json")
        with open(out_path, "w") as f:
            json.dump(out, f, indent=2)
        written += 1

print(f"Written: {written}  |  Skipped infeasible: {skipped_infeasible}  |  Skipped null f1/f2: {skipped_null}")
print(f"Output dir: {OUT_DIR}")
