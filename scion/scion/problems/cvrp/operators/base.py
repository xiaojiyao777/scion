"""Base CVRP operator used for interface documentation."""
from __future__ import annotations

import random

from scion.problems.cvrp.models import CvrpInstance, CvrpSolution


class CvrpOperator:
    name = "base"
    category = "route_local"

    def execute(
        self,
        solution: CvrpSolution,
        instance: CvrpInstance,
        rng: random.Random,
    ) -> CvrpSolution:
        return solution

