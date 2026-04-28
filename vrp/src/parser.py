from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np

from .distance import DIST_MATRIX_THRESHOLD, compute_distance_matrix
from .models import Instance


def parse_vrp(filepath: str) -> Instance:
    """Parse a .vrp file into an Instance. Only supports EUC_2D."""
    with open(filepath) as f:
        lines = f.readlines()

    header: dict[str, str] = {}
    coords_raw: dict[int, tuple[float, float]] = {}
    demands_raw: dict[int, int] = {}
    depot_vrp_id = 1
    section = "HEADER"
    has_decimal_coords = False

    for line in lines:
        line = line.strip()
        if not line or line == "EOF":
            continue

        if line.endswith("SECTION") or line == "DEPOT_SECTION":
            section = line.replace("_SECTION", "").replace(" ", "")
            continue

        if section == "HEADER":
            if ":" in line:
                key, _, val = line.partition(":")
                header[key.strip().upper()] = val.strip()
            continue

        if section == "NODE_COORD":
            parts = line.split()
            nid = int(parts[0])
            coords_raw[nid] = (float(parts[1]), float(parts[2]))
            if not has_decimal_coords and ("." in parts[1] or "." in parts[2]):
                has_decimal_coords = True

        elif section == "DEMAND":
            parts = line.split()
            demands_raw[int(parts[0])] = int(parts[1])

        elif section == "DEPOT":
            val = int(line.split()[0])
            if val != -1:
                depot_vrp_id = val

    edge_type = header.get("EDGE_WEIGHT_TYPE", "").strip()
    if edge_type != "EUC_2D":
        raise ValueError(f"Unsupported EDGE_WEIGHT_TYPE: {edge_type}")

    dimension = int(header["DIMENSION"])
    capacity = int(header["CAPACITY"])
    name = header.get("NAME", Path(filepath).stem)

    coords = np.zeros((dimension, 2), dtype=np.float64)
    demands = np.zeros(dimension, dtype=np.int32)

    for vrp_id in range(1, dimension + 1):
        idx = vrp_id - 1
        coords[idx] = coords_raw[vrp_id]
        demands[idx] = demands_raw.get(vrp_id, 0)

    comment = header.get("COMMENT", "")
    comment_has_float = False
    for token in comment.replace(",", " ").split():
        try:
            val = float(token)
            if "." in token and val != int(val):
                comment_has_float = True
                break
        except ValueError:
            pass

    use_integer_cost = not has_decimal_coords and not comment_has_float

    dist_matrix = None
    if dimension <= DIST_MATRIX_THRESHOLD:
        dist_matrix = compute_distance_matrix(coords, use_integer_cost)

    depot = depot_vrp_id - 1

    return Instance(
        name=name,
        dimension=dimension,
        capacity=capacity,
        coords=coords,
        demands=demands,
        dist_matrix=dist_matrix,
        use_integer_cost=use_integer_cost,
        depot=depot,
    )


def parse_sol(filepath: str) -> tuple[list[list[int]], float]:
    """
    Parse a .sol file.
    Returns (routes, cost) where each route is a list of 0-based internal node indices.
    """
    routes: list[list[int]] = []
    cost = 0.0

    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith("Route"):
                _, _, customers_str = line.partition(":")
                customers = [int(x) for x in customers_str.split()]
                routes.append(customers)
            elif line.startswith("Cost") or line.startswith("cost"):
                cost = float(line.split()[-1])

    return routes, cost


def find_instances(
    data_dir: str,
    subsets: Optional[list[str]] = None,
    euc_2d_only: bool = True,
) -> list[str]:
    """Discover .vrp files, optionally filtering by subset."""
    data_path = Path(data_dir)
    results = []

    if data_path.is_file() and data_path.suffix == ".vrp":
        candidates = [data_path]
    elif subsets is None:
        direct = sorted(data_path.glob("*.vrp"))
        dirs = sorted(p for p in data_path.iterdir() if p.is_dir())
        candidates = direct
        for subset_dir in dirs:
            candidates.extend(sorted(subset_dir.glob("*.vrp")))
    else:
        candidates = []
        for subset in subsets:
            subset_dir = data_path / subset
            if subset_dir.is_dir():
                candidates.extend(sorted(subset_dir.glob("*.vrp")))

    for vrp_file in candidates:
        if euc_2d_only:
            with open(vrp_file) as f:
                content = f.read(500)
            if "EUC_2D" not in content:
                continue
        results.append(str(vrp_file))

    return results
