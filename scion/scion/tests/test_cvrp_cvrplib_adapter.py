"""Synthetic CVRPLIB input tests for the Scion CVRP adapter."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from scion.problems.cvrp.adapter import CvrpAdapter
from scion.problems.cvrp.cvrplib import parse_cvrplib_solution
from scion.problems.cvrp.models import CvrpInstance

CVRPLIB_ROOT = Path(__file__).resolve().parents[2].parent / "vrp" / "cvrplib"


class _Spec:
    pass


@pytest.fixture
def cvrp_adapter() -> CvrpAdapter:
    return CvrpAdapter(_Spec())  # type: ignore[arg-type]


def _write_vrp(
    tmp_path: Path,
    *,
    name: str = "synthetic-cvrp",
    edge_weight_type: str = "EUC_2D",
    decimal_coords: bool = False,
) -> Path:
    path = tmp_path / f"{name}.vrp"
    x2 = "10.5" if decimal_coords else "10"
    path.write_text(
        "\n".join(
            [
                f"NAME : {name}",
                "TYPE : CVRP",
                "COMMENT : synthetic fixture only",
                "DIMENSION : 4",
                f"EDGE_WEIGHT_TYPE : {edge_weight_type}",
                "CAPACITY : 10",
                "NODE_COORD_SECTION",
                "1 0 0",
                f"2 {x2} 0",
                "3 10 10",
                "4 0 10",
                "DEMAND_SECTION",
                "1 0",
                "2 4",
                "3 3",
                "4 2",
                "DEPOT_SECTION",
                "1",
                "-1",
                "EOF",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return path


def _write_sol(vrp_path: Path, text: str) -> Path:
    path = vrp_path.with_suffix(".sol")
    path.write_text(text, encoding="utf-8")
    return path


def _write_explicit_vrp(tmp_path: Path) -> Path:
    path = tmp_path / "synthetic-explicit.vrp"
    path.write_text(
        """NAME : synthetic-explicit
TYPE : CVRP
DIMENSION : 4
EDGE_WEIGHT_TYPE : EXPLICIT
EDGE_WEIGHT_FORMAT : LOWER_ROW
CAPACITY : 10
EDGE_WEIGHT_SECTION
7
8 9
10 11 12
DEMAND_SECTION
1 4
2 3
3 0
4 2
DEPOT_SECTION
3
-1
EOF
""",
        encoding="utf-8",
    )
    return path


def _raw_solution(
    routes: list[list[int]],
    *,
    total_distance: float = 40.0,
) -> dict[str, Any]:
    return {
        "routes": routes,
        "objective": {
            "fleet_violation": 0,
            "total_distance": total_distance,
            "routes": len(routes),
        },
        "feasible": True,
    }


def test_vrp_loads_into_zero_based_cvrp_instance(
    tmp_path: Path,
    cvrp_adapter: CvrpAdapter,
) -> None:
    vrp_path = _write_vrp(tmp_path)

    instance = cvrp_adapter.load_instance(str(vrp_path))

    assert isinstance(instance, CvrpInstance)
    assert instance.name == "synthetic-cvrp"
    assert instance.capacity == 10
    assert instance.depot == 0
    assert instance.node_ids == (0, 1, 2, 3)
    assert instance.customer_ids == (1, 2, 3)
    assert [instance.demand(node_id) for node_id in instance.node_ids] == [0, 4, 3, 2]
    assert instance.use_integer_cost is True
    assert instance.distance(0, 1) == 10.0


def test_decimal_coordinates_disable_integer_distance_rounding(
    tmp_path: Path,
    cvrp_adapter: CvrpAdapter,
) -> None:
    vrp_path = _write_vrp(tmp_path, decimal_coords=True)

    instance = cvrp_adapter.load_instance(str(vrp_path))

    assert instance.use_integer_cost is False
    assert instance.distance(0, 1) == 10.5


def test_explicit_lower_row_loads_without_coordinate_approximation(
    tmp_path: Path,
    cvrp_adapter: CvrpAdapter,
) -> None:
    instance = cvrp_adapter.load_instance(str(_write_explicit_vrp(tmp_path)))

    assert instance.node_ids == (0, 1, 2, 3)
    assert instance.edge_weights is not None
    # Raw node 3 is the depot, so this also verifies matrix reindexing rather
    # than merely parsing LOWER_ROW values in their source order.
    assert instance.distance(0, 1) == 8.0
    assert instance.distance(1, 2) == 7.0
    assert instance.distance(2, 3) == 11.0
    assert instance.route_distance((1, 2, 3)) == 38.0
    with pytest.raises(KeyError, match="unknown node id: -1"):
        instance.distance(-1, 0)


def test_explicit_matrix_format_fails_closed_when_not_lower_row(
    tmp_path: Path,
    cvrp_adapter: CvrpAdapter,
) -> None:
    path = _write_explicit_vrp(tmp_path)
    path.write_text(
        path.read_text(encoding="utf-8").replace("LOWER_ROW", "FULL_MATRIX"),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="EDGE_WEIGHT_FORMAT.*LOWER_ROW"):
        cvrp_adapter.load_instance(str(path))


@pytest.mark.parametrize(
    ("relative_path", "declared_cost"),
    [
        ("E/E-n31-k7.vrp", 379.0),
        ("DIMACS/Loggi-n401-k23.vrp", 336_903.0),
        ("DIMACS/ORTEC-n242-k12.vrp", 123_750.0),
    ],
)
def test_real_explicit_routes_recompute_to_declared_cost_without_solver(
    relative_path: str,
    declared_cost: float,
    cvrp_adapter: CvrpAdapter,
) -> None:
    path = CVRPLIB_ROOT / relative_path
    instance = cvrp_adapter.load_instance(str(path))
    solution = parse_cvrplib_solution(
        path.with_suffix(".sol"),
        customer_count=instance.customer_count,
    )

    assert instance.edge_weights is not None
    assert solution.cost == declared_cost
    assert instance.bks == declared_cost
    assert instance.bks_routes == len(solution.routes)
    assert sum(instance.route_distance(route) for route in solution.routes) == (
        declared_cost
    )


def test_vrp_with_sibling_sol_populates_bks_and_route_count(
    tmp_path: Path,
    cvrp_adapter: CvrpAdapter,
) -> None:
    vrp_path = _write_vrp(tmp_path)
    _write_sol(
        vrp_path,
        "Route #1: 1 2\nRoute #2: 3\nCost 40\n",
    )

    instance = cvrp_adapter.load_instance(str(vrp_path))

    assert instance.bks == 40.0
    assert instance.bks_routes == 2


def test_vrp_missing_sibling_sol_leaves_reference_fields_unknown(
    tmp_path: Path,
    cvrp_adapter: CvrpAdapter,
) -> None:
    vrp_path = _write_vrp(tmp_path)

    instance = cvrp_adapter.load_instance(str(vrp_path))

    assert instance.bks is None
    assert instance.bks_routes is None


def test_unsupported_edge_weight_type_fails_closed(
    tmp_path: Path,
    cvrp_adapter: CvrpAdapter,
) -> None:
    vrp_path = _write_vrp(tmp_path, edge_weight_type="GEO")

    with pytest.raises(ValueError, match="EDGE_WEIGHT_TYPE.*EUC_2D.*EXPLICIT"):
        cvrp_adapter.load_instance(str(vrp_path))


def test_adapter_validates_route_solution_for_parsed_vrp(
    tmp_path: Path,
    cvrp_adapter: CvrpAdapter,
) -> None:
    vrp_path = _write_vrp(tmp_path)
    instance = cvrp_adapter.load_instance(str(vrp_path))
    artifact = cvrp_adapter.deserialize_solver_output(_raw_solution([[1, 2, 3]]), instance)

    assert cvrp_adapter.check_solution_consistency(artifact, instance).passed is True
    assert cvrp_adapter.check_feasibility(artifact, instance).passed is True
    assert cvrp_adapter.recompute_objective(artifact, instance) == {
        "fleet_violation": 0,
        "total_distance": 40.0,
        "routes": 1,
    }


def test_sol_route_ids_are_normalized_customer_ids_not_raw_vrp_node_ids(
    tmp_path: Path,
) -> None:
    vrp_path = _write_vrp(tmp_path)
    sol_path = _write_sol(
        vrp_path,
        "Route #1: 1 2\nRoute #2: 3\nCost : 40\n",
    )

    solution = parse_cvrplib_solution(
        sol_path,
        customer_count=3,
    )

    assert solution.routes == ((1, 2), (3,))
    assert solution.cost == 40.0
    assert all(0 not in route for route in solution.routes)


def test_sol_empty_and_out_of_range_routes_fail_closed(tmp_path: Path) -> None:
    vrp_path = _write_vrp(tmp_path)
    sol_path = _write_sol(vrp_path, "Route #1:\nCost : 0\n")

    with pytest.raises(ValueError, match="route on line 1 has no customers"):
        parse_cvrplib_solution(sol_path, customer_count=3)

    sol_path = _write_sol(vrp_path, "Route #1: 4\nCost : 0\n")
    with pytest.raises(ValueError, match=r"outside 1\.\.3"):
        parse_cvrplib_solution(sol_path, customer_count=3)
