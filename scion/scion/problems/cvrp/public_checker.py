"""Independent CVRP reference check; no editable solver modules are imported."""
from scion.observation.wire import emit, read_request
from scion.problem.contracts import SolverArtifact
from scion.problems.cvrp.models import CvrpInstance, CvrpNode, CvrpSolution
from scion.problems.cvrp.solution_checks import check_solution_consistency, check_feasibility, recompute_objective


def check(value, solution):
    result = {"schema_version": 1, "consistency": "fail", "feasibility": "not_evaluated",
              "recomputed_objective": None, "reason_codes": ["ROUTES_INVALID"]}
    if type(solution) is not dict or set(solution) != {"routes"} or type(solution["routes"]) is not list:
        return result
    routes = solution["routes"]
    if any(type(route) is not list or any(type(n) is not int for n in route) for route in routes):
        return result
    instance = CvrpInstance(**{**value, "nodes": tuple(CvrpNode(**node) for node in value["nodes"])})
    # Placeholders only let the existing structural checker inspect routes;
    # no placeholder is returned as an objective or used as scientific evidence.
    artifact = SolverArtifact({}, {"fleet_violation": 0, "total_distance": 0}, False,
                              CvrpSolution(tuple(tuple(route) for route in routes)))
    if not check_solution_consistency(artifact, instance).passed:
        return result
    objective = dict(recompute_objective(artifact, instance))
    artifact = SolverArtifact({}, objective, False, artifact.normalized_solution)
    feasible = check_feasibility(artifact, instance).passed
    return {"schema_version": 1, "consistency": "pass", "feasibility": "pass" if feasible else "fail",
            "recomputed_objective": objective, "reason_codes": [] if feasible else ["CAPACITY_EXCEEDED"]}


if __name__ == "__main__":
    request = read_request()
    emit(check(request["instance"], request["solution"]))
