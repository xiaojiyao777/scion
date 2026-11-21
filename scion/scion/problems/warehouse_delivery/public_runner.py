"""Fixed Warehouse entry binding the actual copied config and registry."""
from dataclasses import asdict
from pathlib import Path

from scion.observation.wire import emit, read_request


def main():
    # These imports occur only inside /subject in the isolated process.
    from config import Config
    from models import Instance, Order, SPU
    from solver import solve

    request = read_request()
    data = request["instance"]
    instance = Instance(
        orders={o["order_id"]: Order(**{**o, "spu_list": [SPU(**s) for s in o["spu_list"]]}) for o in data["orders"]},
        amount_limits=data["amount_limits"], phase=1,
    )
    cfg = Config()
    cfg.random_seed = request["seed"]
    cfg.time_limit_seconds = request["public_args"]["time_limit_sec"]
    cfg.max_iterations = request["public_args"]["max_iterations"]
    mode = request["source_config"]["operator_selection"]
    registry = Path("/subject/registry.yaml")
    if (mode == "registry") != registry.is_file():
        raise ValueError("source configuration unavailable")
    try:
        solution = solve(instance, cfg, registry_path=registry if mode == "registry" else None)
        payload = {"vehicles": {key: asdict(value) for key, value in solution.vehicles.items()},
                   "assignment": dict(solution.assignment)}
        emit({"schema_version": 1, "outcome": "returned", "solution": payload,
              "reported_objective": asdict(solution.objective) if solution.objective else {},
              "diagnostics": {"config": asdict(cfg), "operator_selection": mode,
                              "runtime": getattr(solution, "_scion_runtime", {})}})
    except Exception as error:
        emit({"schema_version": 1, "outcome": "algorithm_error", "solution": None,
              "reported_objective": {}, "diagnostics": {"exception_kind": type(error).__name__}})


if __name__ == "__main__":
    main()
