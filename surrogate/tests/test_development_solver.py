"""Ordinary public development smoke test for bounded code research."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import Config
from oracle import check_feasibility
from solver import load_instance, solve


def test_public_development_instance_is_solved_feasibly() -> None:
    instance_path = Path(__file__).parent.parent / "data/instance_development.json"
    instance = load_instance(instance_path, phase=1)
    solution = solve(
        instance,
        Config(
            pool_size=3,
            max_iterations=2,
            no_improve_limit=1,
            random_seed=17,
            time_limit_seconds=0.05,
        ),
    )

    report = check_feasibility(solution, instance, phase=1)
    assert report.is_feasible
    assert set(solution.assignment) == set(instance.orders)
