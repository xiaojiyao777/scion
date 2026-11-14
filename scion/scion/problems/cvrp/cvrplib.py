"""Small CVRPLIB parser owned by the Scion CVRP adapter boundary."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

from scion.problems.cvrp.models import CvrpInstance, CvrpNode

_SECTION_NAMES = {
    "EDGE_WEIGHT_SECTION",
    "NODE_COORD_SECTION",
    "DEMAND_SECTION",
    "DEPOT_SECTION",
}
_ROUTE_RE = re.compile(r"^\s*Route\s*#?\s*\d+\s*:\s*(?P<route>.*?)\s*$", re.IGNORECASE)
_COST_RE = re.compile(
    r"^\s*Cost\s*(?::|=)?\s*(?P<cost>[+-]?\d+(?:\.\d+)?)\s*$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class CvrplibSolution:
    routes: tuple[tuple[int, ...], ...]
    cost: float | None


def load_cvrplib_instance(path: str | Path) -> CvrpInstance:
    """Load a supported CVRPLIB ``.vrp`` file into Scion's zero-based model."""
    vrp_path = Path(path)
    header, sections = _read_vrp_file(vrp_path)

    name = _required_field(header, "NAME")
    dimension = _parse_positive_int(_required_field(header, "DIMENSION"), "DIMENSION")
    capacity = _parse_positive_int(_required_field(header, "CAPACITY"), "CAPACITY")
    edge_weight_type = _required_field(header, "EDGE_WEIGHT_TYPE").upper()
    if edge_weight_type not in {"EUC_2D", "EXPLICIT"}:
        raise ValueError(
            "unsupported CVRPLIB EDGE_WEIGHT_TYPE "
            f"{edge_weight_type!r}; supported types are EUC_2D and "
            "EXPLICIT/LOWER_ROW"
        )

    demands = _parse_demands(_required_section(sections, "DEMAND_SECTION"))
    depot_ids = _parse_depots(_required_section(sections, "DEPOT_SECTION"))
    if len(demands) != dimension:
        raise ValueError(
            f"CVRPLIB DIMENSION is {dimension}, but DEMAND_SECTION has "
            f"{len(demands)} nodes"
        )
    if len(depot_ids) != 1:
        raise ValueError("CVRPLIB parser supports exactly one depot")

    raw_depot_id = depot_ids[0]
    if raw_depot_id not in demands:
        raise ValueError(f"CVRPLIB depot id {raw_depot_id} is not in DEMAND_SECTION")

    edge_weights = None
    if edge_weight_type == "EUC_2D":
        coords = _parse_node_coords(
            _required_section(sections, "NODE_COORD_SECTION")
        )
        if len(coords) != dimension:
            raise ValueError(
                f"CVRPLIB DIMENSION is {dimension}, but NODE_COORD_SECTION has "
                f"{len(coords)} nodes"
            )
        if set(coords) != set(demands):
            raise ValueError(
                "CVRPLIB NODE_COORD_SECTION and DEMAND_SECTION node ids differ"
            )
    else:
        edge_weight_format = _required_field(header, "EDGE_WEIGHT_FORMAT").upper()
        if edge_weight_format != "LOWER_ROW":
            raise ValueError(
                "unsupported CVRPLIB EDGE_WEIGHT_FORMAT "
                f"{edge_weight_format!r}; only LOWER_ROW is supported"
            )
        raw_ids = tuple(sorted(demands))
        if raw_ids != tuple(range(1, dimension + 1)):
            raise ValueError(
                "EXPLICIT/LOWER_ROW CVRPLIB node ids must be consecutive from 1"
            )
        raw_matrix = _parse_lower_row(
            _required_section(sections, "EDGE_WEIGHT_SECTION"), dimension
        )
        if "NODE_COORD_SECTION" in sections:
            coords = _parse_node_coords(sections["NODE_COORD_SECTION"])
            if set(coords) != set(demands):
                raise ValueError(
                    "CVRPLIB NODE_COORD_SECTION and DEMAND_SECTION node ids differ"
                )
        else:
            coords = {raw_id: (0.0, 0.0) for raw_id in raw_ids}

    raw_ids = tuple(sorted(demands))
    id_map = _build_zero_based_id_map(raw_ids, raw_depot_id)
    if edge_weight_type == "EXPLICIT":
        edge_weights = _reorder_edge_weights(raw_matrix, raw_ids, id_map)
    nodes = tuple(
        CvrpNode(
            id=id_map[raw_id],
            x=coords[raw_id][0],
            y=coords[raw_id][1],
            demand=demands[raw_id],
        )
        for raw_id in sorted(coords, key=lambda node_id: id_map[node_id])
    )
    use_integer_cost = edge_weights is not None or all(
        x.is_integer() and y.is_integer() for x, y in coords.values()
    )

    bks = None
    bks_routes = None
    solution_path = vrp_path.with_suffix(".sol")
    if solution_path.exists():
        solution = parse_cvrplib_solution(
            solution_path,
            customer_count=dimension - 1,
        )
        bks = solution.cost
        bks_routes = len(solution.routes)

    return CvrpInstance(
        name=name,
        capacity=capacity,
        depot=0,
        nodes=nodes,
        allowed_routes=None,
        bks=bks,
        bks_routes=bks_routes,
        use_integer_cost=use_integer_cost,
        edge_weights=edge_weights,
    )


def parse_cvrplib_solution(
    path: str | Path,
    *,
    customer_count: int,
) -> CvrplibSolution:
    """Parse normalized CVRPLIB solution customer ids into Scion routes."""
    routes: list[tuple[int, ...]] = []
    cost: float | None = None
    with open(path, encoding="utf-8") as f:
        for line_number, raw_line in enumerate(f, start=1):
            line = raw_line.strip()
            if not line or line.upper() == "EOF":
                continue
            route_match = _ROUTE_RE.match(line)
            if route_match:
                routes.append(
                    _parse_solution_route(
                        route_match.group("route"),
                        customer_count=customer_count,
                        line_number=line_number,
                    )
                )
                continue
            cost_match = _COST_RE.match(line)
            if cost_match:
                cost = float(cost_match.group("cost"))

    return CvrplibSolution(routes=tuple(routes), cost=cost)


def _read_vrp_file(path: Path) -> tuple[dict[str, str], dict[str, list[str]]]:
    header: dict[str, str] = {}
    sections: dict[str, list[str]] = {}
    current_section: str | None = None

    with open(path, encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue
            upper = line.upper()
            if upper == "EOF":
                break
            if upper in _SECTION_NAMES:
                current_section = upper
                sections[current_section] = []
                continue
            if current_section is not None:
                sections[current_section].append(line)
                continue
            key, value = _parse_header_line(line)
            header[key] = value

    return header, sections


def _parse_header_line(line: str) -> tuple[str, str]:
    if ":" in line:
        key, value = line.split(":", 1)
    else:
        parts = line.split(None, 1)
        if len(parts) != 2:
            raise ValueError(f"invalid CVRPLIB header line: {line!r}")
        key, value = parts
    return key.strip().upper(), value.strip()


def _required_field(header: dict[str, str], name: str) -> str:
    value = header.get(name)
    if value is None or value == "":
        raise ValueError(f"missing required CVRPLIB field {name}")
    return value


def _required_section(sections: dict[str, list[str]], name: str) -> list[str]:
    try:
        return sections[name]
    except KeyError as exc:
        raise ValueError(f"missing required CVRPLIB section {name}") from exc


def _parse_positive_int(value: str, field_name: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"CVRPLIB field {field_name} must be an integer") from exc
    if parsed <= 0:
        raise ValueError(f"CVRPLIB field {field_name} must be positive")
    return parsed


def _parse_node_coords(lines: list[str]) -> dict[int, tuple[float, float]]:
    coords: dict[int, tuple[float, float]] = {}
    for line in lines:
        parts = line.split()
        if len(parts) != 3:
            raise ValueError(f"invalid CVRPLIB NODE_COORD_SECTION line: {line!r}")
        raw_id = _parse_node_id(parts[0], "NODE_COORD_SECTION")
        if raw_id in coords:
            raise ValueError(f"duplicate CVRPLIB node id {raw_id}")
        coords[raw_id] = (float(parts[1]), float(parts[2]))
    return coords


def _parse_demands(lines: list[str]) -> dict[int, int]:
    demands: dict[int, int] = {}
    for line in lines:
        parts = line.split()
        if len(parts) != 2:
            raise ValueError(f"invalid CVRPLIB DEMAND_SECTION line: {line!r}")
        raw_id = _parse_node_id(parts[0], "DEMAND_SECTION")
        if raw_id in demands:
            raise ValueError(f"duplicate CVRPLIB demand node id {raw_id}")
        demands[raw_id] = int(parts[1])
    return demands


def _parse_depots(lines: list[str]) -> tuple[int, ...]:
    depots: list[int] = []
    for line in lines:
        for token in line.split():
            raw_id = int(token)
            if raw_id == -1:
                return tuple(depots)
            depots.append(raw_id)
    return tuple(depots)


def _parse_lower_row(
    lines: list[str], dimension: int
) -> tuple[tuple[float, ...], ...]:
    values: list[float] = []
    for line in lines:
        for token in line.split():
            try:
                value = float(token)
            except ValueError as exc:
                raise ValueError(
                    f"invalid CVRPLIB EDGE_WEIGHT_SECTION value: {token!r}"
                ) from exc
            if not math.isfinite(value) or value < 0:
                raise ValueError(
                    f"invalid CVRPLIB EDGE_WEIGHT_SECTION value: {token!r}"
                )
            values.append(value)
    expected = dimension * (dimension - 1) // 2
    if len(values) != expected:
        raise ValueError(
            f"CVRPLIB LOWER_ROW expects {expected} weights, got {len(values)}"
        )
    matrix = [[0.0 for _ in range(dimension)] for _ in range(dimension)]
    cursor = 0
    for row in range(1, dimension):
        for column in range(row):
            value = values[cursor]
            cursor += 1
            matrix[row][column] = value
            matrix[column][row] = value
    return tuple(tuple(row) for row in matrix)


def _reorder_edge_weights(
    raw_matrix: tuple[tuple[float, ...], ...],
    raw_ids: tuple[int, ...],
    id_map: dict[int, int],
) -> tuple[tuple[float, ...], ...]:
    dimension = len(raw_ids)
    normalized = [[0.0 for _ in range(dimension)] for _ in range(dimension)]
    for raw_row_index, raw_row_id in enumerate(raw_ids):
        for raw_column_index, raw_column_id in enumerate(raw_ids):
            normalized[id_map[raw_row_id]][id_map[raw_column_id]] = raw_matrix[
                raw_row_index
            ][raw_column_index]
    return tuple(tuple(row) for row in normalized)


def _parse_node_id(value: str, section_name: str) -> int:
    raw_id = int(value)
    if raw_id <= 0:
        raise ValueError(f"CVRPLIB {section_name} node ids must be positive")
    return raw_id


def _build_zero_based_id_map(raw_ids: tuple[int, ...], raw_depot_id: int) -> dict[int, int]:
    id_map = {raw_depot_id: 0}
    next_id = 1
    for raw_id in raw_ids:
        if raw_id == raw_depot_id:
            continue
        id_map[raw_id] = next_id
        next_id += 1
    return id_map


def _parse_solution_route(
    route_text: str,
    *,
    customer_count: int,
    line_number: int,
) -> tuple[int, ...]:
    route: list[int] = []
    for token in route_text.split():
        try:
            customer_id = int(token)
        except ValueError as exc:
            raise ValueError(
                "CVRPLIB solution route has invalid customer id "
                f"{token!r} on line {line_number}"
            ) from exc
        if customer_id < 1 or customer_id > customer_count:
            raise ValueError(
                "CVRPLIB solution route references customer id "
                f"{customer_id} outside 1..{customer_count} on line {line_number}"
            )
        route.append(customer_id)
    if not route:
        raise ValueError(f"CVRPLIB solution route on line {line_number} has no customers")
    return tuple(route)
