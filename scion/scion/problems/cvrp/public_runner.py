"""Fixed CVRP subject entry. Execute only inside the observation sandbox."""
from random import Random
import time

from scion.observation.wire import emit, read_request
from scion.problems.cvrp.adapter import CvrpAdapter
from scion.problems.cvrp.models import CvrpInstance, CvrpNode
from scion.problems.cvrp.solver_runtime.algorithm_runtime import load_baseline_algorithm


def main():
    request = read_request()
    value = request["instance"]
    instance = CvrpInstance(**{**value, "nodes": tuple(CvrpNode(**node) for node in value["nodes"])})
    solution, audit = load_baseline_algorithm(
        workspace_root="/subject", instance=instance, instance_path="/input/instance.json",
        seed=request["seed"], rng=Random(request["seed"]),
        time_limit_sec=request["public_args"]["time_limit_sec"], start_time=time.perf_counter(),
        adapter=CvrpAdapter(None),
    )
    if solution is None:
        outcome = "invalid_solution" if audit.get("solver_algorithm_stop_reason") in {"invalid_solution", "invalid_output"} else "algorithm_error"
        emit({"schema_version": 1, "outcome": outcome, "solution": None,
              "reported_objective": {}, "diagnostics": audit})
        return
    emit({"schema_version": 1, "outcome": "returned", "solution": {"routes": [list(route) for route in solution.routes]},
          "reported_objective": {}, "diagnostics": audit})


if __name__ == "__main__":
    main()
