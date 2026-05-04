"""Small CVRPLIB parser owned by the Scion CVRP adapter boundary."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from scion.problems.cvrp.models import CvrpInstance, CvrpNode


_SECTION_NAMES = {
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
    """Load an EUC_2D CVRPLIB ``.vrp`` file into Scion's zero-based model."""
    vrp_path = Path(path)
    header, sections = _read_vrp_file(vrp_path)

    name = _required_field(header, "NAME")
    dimension = _parse_positive_int(_required_field(header, "DIMENSION"), "DIMENSION")
    capacity = _parse_positive_int(_required_field(header, "CAPACITY"), "CAPACITY")
    edge_weight_type = _required_field(header, "EDGE_WEIGHT_TYPE").upper()
    if edge_weight_type != "EUC_2D":
        raise ValueError(
            "unsupported CVRPLIB EDGE_WEIGHT_TYPE "
            f"{edge_weight_type!r}; only EUC_2D is supported"
        )

    coords = _parse_node_coords(_required_section(sections, "NODE_COORD_SECTION"))
    demands = _parse_demands(_required_section(sections, "DEMAND_SECTION"))
    depot_ids = _parse_depots(_required_section(sections, "DEPOT_SECTION"))

    if len(coords) != dimension:
        raise ValueError(
            f"CVRPLIB DIMENSION is {dimension}, but NODE_COORD_SECTION has {len(coords)} nodes"
        )
    if set(coords) != set(demands):
        raise ValueError("CVRPLIB NODE_COORD_SECTION and DEMAND_SECTION node ids differ")
    if len(depot_ids) != 1:
        raise ValueError("CVRPLIB parser supports exactly one depot")

    raw_depot_id = depot_ids[0]
    if raw_depot_id not in coords:
        raise ValueError(f"CVRPLIB depot id {raw_depot_id} is not in NODE_COORD_SECTION")

    id_map = _build_zero_based_id_map(tuple(sorted(coords)), raw_depot_id)
    nodes = tuple(
        CvrpNode(
            id=id_map[raw_id],
            x=coords[raw_id][0],
            y=coords[raw_id][1],
            demand=demands[raw_id],
        )
        for raw_id in sorted(coords, key=lambda node_id: id_map[node_id])
    )
    use_integer_cost = all(
        x.is_integer() and y.is_integer()
        for x, y in coords.values()
    )

    bks = None
    bks_routes = None
    solution_path = vrp_path.with_suffix(".sol")
    if solution_path.exists():
        solution = parse_cvrplib_solution(
            solution_path,
            id_map=id_map,
            raw_depot_id=raw_depot_id,
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
    )


def parse_cvrplib_solution(
    path: str | Path,
    *,
    id_map: dict[int, int],
    raw_depot_id: int,
) -> CvrplibSolution:
    """Parse a CVRPLIB ``.sol`` file and map routes to Scion node ids."""
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
                        id_map=id_map,
                        raw_depot_id=raw_depot_id,
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
    id_map: dict[int, int],
    raw_depot_id: int,
    line_number: int,
) -> tuple[int, ...]:
    route: list[int] = []
    for token in route_text.split():
        raw_id = int(token)
        if raw_id == raw_depot_id:
            continue
        try:
            route.append(id_map[raw_id])
        except KeyError as exc:
            raise ValueError(
                "CVRPLIB solution route references unknown node "
                f"{raw_id} on line {line_number}"
            ) from exc
    if not route:
        raise ValueError(f"CVRPLIB solution route on line {line_number} has no customers")
    return tuple(route)
